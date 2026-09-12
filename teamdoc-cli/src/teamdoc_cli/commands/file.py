"""云空间文件:td file ls / up / down / mkdir / rename / mv / rm。"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from ..client import ApiError, Client, filename_from_disposition
from ..output import fmt_size, fmt_time, handle, print_json, table
from .project import resolve_project

app = typer.Typer(no_args_is_help=True, help="云空间文件")


def _path(item_id: str, is_folder: bool, suffix: str = "") -> str:
    """文件与文件夹在服务端是两套独立编号的端点,只差这一段前缀。

    改端点只改这里一处;各命令也不用手写"文件还是文件夹"的分支拼串。
    """
    return ("/api/files/folders/" if is_folder else "/api/files/") + str(item_id) + suffix


def _with_dir_hint(e: ApiError, is_folder: bool) -> ApiError:
    """文件夹与文件是两套编号,走错表的表现就是 404「不存在」:补一句提示再原样抛。"""
    if e.status == 404 and not is_folder:
        typer.secho("提示:若该 ID 其实是文件夹,请加 --is-folder(文件与文件夹各有独立编号,td file ls 可查)",
                    fg=typer.colors.YELLOW, err=True)
    return e


@app.command("ls")
@handle
def ls(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
       folder: str = typer.Argument("", help="文件夹 ID(缺省看根目录)"),
       json_out: bool = typer.Option(False, "--json")):
    """文件列表(自动翻页取全)"""
    c = Client()
    p = resolve_project(c, project_ref)
    params: dict = {"project_id": p["id"], "limit": 500}
    if folder:
        params["folder_id"] = folder
    # 文件夹**不分页**(服务端每页都回同一份):只在第一页取,否则文件超过一页时会重复累加
    page = c.json("GET", "/api/files", params=params)
    folders: list = page.get("folders", [])
    files: list = page.get("files", [])
    while page.get("hasMore"):
        params["offset"] = len(files)
        page = c.json("GET", "/api/files", params=params)
        files += page.get("files", [])
    if json_out:
        print_json({"folders": folders, "files": files})
        return
    print(f"项目「{p['name']}」:文件夹 {len(folders)} · 文件 {len(files)}")
    if folders:
        table(["ID", "文件夹"], [[f["id"], f["name"]] for f in folders])
    if files:
        table(["ID", "文件名", "大小", "上传时间", "标记"],
              [[f["id"], f["name"], fmt_size(f.get("size")), fmt_time(f.get("createdAt")),
                " ".join(filter(None, [
                    "被引用" if f.get("referenced") else "",
                    "公开" if f.get("isPublic") else "",
                ]))] for f in files])
    if not folders and not files:
        print("(空)")


@app.command("up")
@handle
def up(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
       path: str = typer.Argument(..., help="本地文件路径"),
       folder: str = typer.Option("", "--folder", help="目标文件夹 ID(缺省根目录)"),
       json_out: bool = typer.Option(False, "--json")):
    """上传文件(raw body 流式直传;同目录重名服务端自动加后缀)"""
    local = Path(path)
    if not local.is_file():
        typer.secho(f"本地文件不存在:{path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    c = Client()
    p = resolve_project(c, project_ref)
    params = {"projectId": p["id"], "name": local.name}
    if folder:
        params["folderId"] = folder
    f = c.upload("/api/files/upload", params, str(local))
    if json_out:
        print_json(f)
    else:
        print(f"已上传:{f['name']}({f['id']},{fmt_size(f.get('size'))})")


@app.command("down")
@handle
def down(file_id: str = typer.Argument(..., help="文件 ID"),
         out: str = typer.Option("", "-o", "--output", help="输出路径;缺省用服务端文件名")):
    """下载文件"""
    c = Client()
    # 先拿一次响应头决定文件名(发 HEAD 不划算——服务端没实现,直接流式 GET)
    with c.http.stream("GET", f"/api/files/{file_id}/download") as resp:
        if resp.status_code >= 400:
            from ..client import parse_error
            code, message = parse_error(resp)
            raise ApiError(resp.status_code, code, message)
        fallback = f"{file_id}.download"
        name = filename_from_disposition(resp.headers.get("content-disposition"), fallback)
        target = os.path.join(out, name) if os.path.isdir(out or "") else (out or name)
        tmp = target + ".part"
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(1024 * 1024):
                f.write(chunk)
    os.replace(tmp, target)
    print(f"已下载:{target}")


@app.command("mkdir")
@handle
def mkdir(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
          name: str = typer.Argument(..., help="文件夹名称"),
          folder: str = typer.Option("", "--folder", help="父文件夹 ID(缺省建在根目录)"),
          json_out: bool = typer.Option(False, "--json")):
    """新建文件夹"""
    c = Client()
    p = resolve_project(c, project_ref)
    body: dict = {"projectId": p["id"], "name": name}
    if folder:
        body["parentId"] = folder
    d = c.json("POST", "/api/files/folders", json_body=body)
    if json_out:
        print_json(d)
    else:
        print(f"已建文件夹:{d['name']}({d['id']})")


@app.command("rename")
@handle
def rename(item_id: str = typer.Argument(..., help="文件 ID(文件夹加 --is-folder)"),
           name: str = typer.Argument(..., help="新名称"),
           is_folder: bool = typer.Option(False, "--is-folder", help="ID 指文件夹(不是文件)"),
           json_out: bool = typer.Option(False, "--json")):
    """重命名文件 / 文件夹(同目录重名 409,与网页端一致)"""
    c = Client()
    try:
        r = c.json("PATCH", _path(item_id, is_folder), json_body={"name": name})
    except ApiError as e:
        raise _with_dir_hint(e, is_folder) from e
    if json_out:
        print_json(r)
    else:
        print(f"已重命名为:{r.get('name', name)}")


@app.command("mv")
@handle
def mv(item_id: str = typer.Argument(..., help="文件 ID(文件夹加 --is-folder)"),
       to: str = typer.Option(..., "--to", help="目标项目 ID 或名称"),
       folder: str = typer.Option("", "--folder", help="目标文件夹 ID(缺省落在目标项目根目录)"),
       is_folder: bool = typer.Option(False, "--is-folder",
                                      help="ID 指文件夹(不是文件);跨项目移动需源项目 ADMIN"),
       json_out: bool = typer.Option(False, "--json")):
    """移动文件 / 文件夹(项目内整理或跨项目转移;只改归属,不复制数据)"""
    c = Client()
    p = resolve_project(c, to)
    body: dict = {"projectId": p["id"]}
    if folder:
        # 服务端两侧字段名不同,且文件的 folderId 只接受字符串(见 files.py move_file)
        body["parentId" if is_folder else "folderId"] = folder if is_folder else str(folder)
    try:
        r = c.json("POST", _path(item_id, is_folder, "/move"), json_body=body)
    except ApiError as e:
        raise _with_dir_hint(e, is_folder) from e
    if json_out:
        print_json(r)
    else:
        print(f"已移动到「{p['name']}」" + (f" / 文件夹 {folder}" if folder else " 根目录"))


@app.command("rm")
@handle
def rm(item_id: str = typer.Argument(..., help="文件 ID(文件夹加 --is-folder,连同整棵子树)"),
       is_folder: bool = typer.Option(False, "--is-folder", help="ID 指文件夹(连同整棵子树)"),
       permanent: bool = typer.Option(False, "--permanent",
                                      help="彻底删除(仅回收站中的可删;不可恢复)"),
       yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认")):
    """删除文件 / 文件夹(默认进项目回收站,可恢复)"""
    what = "文件夹及其整棵子树" if is_folder else "文件"
    tip = (f"彻底删除{what} {item_id}?不可恢复(仅回收站中的可删)" if permanent
           else f"删除{what} {item_id}?(进项目回收站,可恢复)")
    if not yes and not typer.confirm(tip):
        raise typer.Abort()
    c = Client()
    try:
        c.request("DELETE", _path(item_id, is_folder, "/permanent" if permanent else ""))
    except ApiError as e:
        raise _with_dir_hint(e, is_folder) from e
    print("已彻底删除" if permanent else "已删除(可在项目回收站恢复)")
