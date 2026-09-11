"""云空间文件:td file ls / up / down。"""

from __future__ import annotations

import typer

from ..client import Client, filename_from_disposition
from ..output import fmt_size, fmt_time, handle, print_json, table
from .project import resolve_project

app = typer.Typer(no_args_is_help=True, help="云空间文件")


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
    folders: list = []
    files: list = []
    while True:
        page = c.json("GET", "/api/files", params=params)
        folders += page.get("folders", [])
        files += page.get("files", [])
        if not page.get("hasMore"):
            break
        params["offset"] = len(files)
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
    from pathlib import Path
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
            from ..client import ApiError
            code, message = parse_error(resp)
            raise ApiError(resp.status_code, code, message)
        target = out or filename_from_disposition(resp.headers.get("content-disposition"),
                                                  f"{file_id}.download")
        import os
        if os.path.isdir(target):
            target = os.path.join(target, filename_from_disposition(
                resp.headers.get("content-disposition"), f"{file_id}.download"))
        tmp = target + ".part"
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(1024 * 1024):
                f.write(chunk)
    import os
    os.replace(tmp, target)
    print(f"已下载:{target}")
