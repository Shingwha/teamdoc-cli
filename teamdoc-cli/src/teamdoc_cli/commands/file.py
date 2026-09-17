"""云空间文件:td file ls / up / down / mkdir / rename / mv / share / unshare / rm。

文件与文件夹在服务端是两套编号,而用户手里只有一个 ID —— 改名 / 移动 / 删除都走
refs.item 自动判类型,CLI 里不存在 --is-folder 这种"替服务端回答内部问题"的参数。
下载与分享是**文件专属**(文件夹没有这两个端点),所以直接打文件端点、不做回落。
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from .. import refs
from ..cli import JSON, emit, guarded
from ..client import CHUNK, Client, filename_from_disposition
from ..console import fmt_size, fmt_time, table
from ..errors import InputError

app = typer.Typer(no_args_is_help=True, help="云空间文件")


def _embeddable(f: dict) -> bool:
    """能不能写进正文当图片内嵌:图片类型 **且** 服务端 inline 白名单放行。

    只看 mime 会栽在"服务端不内联的图片类型"上(写进正文就是裂图),只看扩展名更糟
    —— mime 由服务端按文件名判定,客户端不该另猜一套。导入 Markdown 时按它决定
    写 `![]()` 还是 `[]()`。
    """
    return str(f.get("mime") or "").startswith("image/") and bool(f.get("canInline"))


@app.command("ls")
@guarded
def ls(project: str = typer.Argument(..., help="项目 ID 或名称"),
       folder: str = typer.Option("", "--folder", help="文件夹 ID(缺省看根目录)"),
       json_out: bool = JSON):
    """文件列表(自动翻页取全)"""
    c = Client()
    p = refs.project(c, project)
    params: dict = {"project_id": p["id"], "limit": 500}   # 这个端点用下划线参数名
    if folder:
        params["folder_id"] = folder
    page = c.json("GET", "/api/files", params=params)
    folders, files = page.get("folders", []), page.get("files", [])
    while page.get("hasMore"):      # 文件夹不分页(服务端每页都回同一份),只有文件要翻
        params["offset"] = len(files)
        page = c.json("GET", "/api/files", params=params)
        files += page.get("files", [])
    lines = [f"项目「{p['name']}」:文件夹 {len(folders)} · 文件 {len(files)}"]
    if folders:
        lines += table(["ID", "文件夹"], [[f["id"], f["name"]] for f in folders])
    if files:
        if folders:
            lines.append("")
        lines += table(["ID", "文件名", "大小", "上传时间", "标记"],
                       [[f["id"], f["name"], fmt_size(f.get("size")), fmt_time(f.get("createdAt")),
                         " ".join(filter(None, ["被引用" if f.get("referenced") else "",
                                                "已分享" if f.get("shared") else "",
                                                "可内嵌" if _embeddable(f) else ""]))]
                        for f in files])
    emit(json_out, {"folders": folders, "files": files}, lines)


@app.command("up")
@guarded
def up(project: str = typer.Argument(..., help="项目 ID 或名称"),
       path: str = typer.Argument(..., help="本地文件路径"),
       folder: str = typer.Option("", "--folder", help="目标文件夹 ID(缺省根目录)"),
       json_out: bool = JSON):
    """上传文件(raw body 流式直传;同目录重名服务端自动加后缀)"""
    local = Path(path)
    if not local.is_file():
        raise InputError(f"本地文件不存在:{path}")
    c = Client()
    p = refs.project(c, project)
    params = {"projectId": p["id"], "name": local.name}
    if folder:
        params["folderId"] = folder
    f = c.upload("/api/files/upload", params, str(local))
    emit(json_out, f, [f"已上传:{f['name']}({f['id']},{fmt_size(f.get('size'))})"])


@app.command("down")
@guarded
def down(file_id: str = typer.Argument(..., help="文件 ID"),
         out: str = typer.Option("", "-o", "--output", help="输出路径(目录则用服务端文件名)"),
         json_out: bool = JSON):
    """下载文件"""
    c = Client()
    # 服务端没有 HEAD,所以直接流式 GET,从响应头里取文件名
    with c.stream("GET", f"/api/files/{file_id}/download") as resp:
        name = filename_from_disposition(resp.headers.get("content-disposition"),
                                         f"{file_id}.download")
        target = os.path.join(out, name) if os.path.isdir(out or "") else (out or name)
        tmp = target + ".part"     # 先写 .part,下载完再改名:半截文件不冒充成品
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(CHUNK):
                f.write(chunk)
    os.replace(tmp, target)
    # 缺省文件名由服务端决定(重名会自动加后缀),脚本自己算不出来,所以给 --json
    emit(json_out, {"path": target, "name": name}, [f"已下载:{target}"])


@app.command("mkdir")
@guarded
def mkdir(project: str = typer.Argument(..., help="项目 ID 或名称"),
          name: str = typer.Argument(..., help="文件夹名称"),
          folder: str = typer.Option("", "--folder", help="父文件夹 ID(缺省建在根目录)"),
          json_out: bool = JSON):
    """新建文件夹"""
    c = Client()
    p = refs.project(c, project)
    body: dict = {"projectId": p["id"], "name": name}
    if folder:
        body["parentId"] = folder
    d = c.json("POST", "/api/files/folders", json_body=body)
    emit(json_out, d, [f"已建文件夹:{d['name']}({d['id']})"])


@app.command("rename")
@guarded
def rename(item_id: str = typer.Argument(..., help="文件或文件夹 ID(自动识别)"),
           name: str = typer.Argument(..., help="新名称"),
           json_out: bool = JSON):
    """重命名文件 / 文件夹(同目录重名 409,与网页端一致)"""
    r = refs.item(Client(), "PATCH", item_id, body={"name": name})
    emit(json_out, r, [f"已重命名为:{r.get('name', name)}"])


@app.command("mv")
@guarded
def mv(item_id: str = typer.Argument(..., help="文件或文件夹 ID(自动识别;文件夹整棵子树一起动)"),
       to: str = typer.Option(..., "--to", help="目标项目 ID 或名称"),
       folder: str = typer.Option("", "--folder", help="目标文件夹 ID(缺省落在目标项目根目录)"),
       json_out: bool = JSON):
    """移动文件 / 文件夹(项目内整理或跨项目转移;只改归属,不复制数据)

    跨项目移动需要源项目 ADMIN + 目标项目 EDITOR。
    """
    c = Client()
    p = refs.project(c, to)
    r = refs.item(c, "POST", item_id, suffix="/move", body=refs.move_body(p["id"], folder))
    where = f" / 文件夹 {folder}" if folder else " 根目录"
    emit(json_out, r, [f"已移动到「{p['name']}」{where}"])


@app.command("share")
@guarded
def share(file_id: str = typer.Argument(..., help="文件 ID"),
          expire: int = typer.Option(0, "--expire", help="有效天数(缺省 0 = 长期有效)"),
          json_out: bool = JSON):
    """建立分享链接(持有链接的人无需登录即可下载;重复调用换新链接,旧的立刻失效)"""
    c = Client()
    r = c.json("POST", f"/api/files/{file_id}/share",
               json_body={"expireDays": expire} if expire else {})
    url = c.server + r["url"]
    emit(json_out, {**r, "url": url},
         [f"分享链接:{url}",
          f"有效期  : {r['expiresAt'] or '长期有效'}",
          f"吊销    : td file unshare {file_id}"])


@app.command("unshare")
@guarded
def unshare(file_id: str = typer.Argument(..., help="文件 ID"),
            json_out: bool = JSON):
    """吊销分享链接(已发出的链接立刻失效;文件本身不受影响)"""
    r = Client().json("DELETE", f"/api/files/{file_id}/share")
    emit(json_out, r, ["已吊销分享链接(此前发出的链接已失效)"])


@app.command("rm")
@guarded
def rm(item_id: str = typer.Argument(..., help="文件或文件夹 ID(自动识别)"),
       permanent: bool = typer.Option(False, "--permanent",
                                      help="彻底删除(仅回收站中的可删;不可恢复)"),
       yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
       json_out: bool = JSON):
    """删除文件 / 文件夹(默认进项目回收站;文件夹连同整棵子树)"""
    tip = (f"彻底删除 {item_id}?不可恢复(仅回收站中的可删;文件夹连同整棵子树)" if permanent
           else f"删除 {item_id}?(文件或文件夹;文件夹连同整棵子树,进项目回收站可恢复)")
    if not yes and not typer.confirm(tip):
        raise typer.Abort()
    r = refs.item(Client(), "DELETE", item_id, suffix="/permanent" if permanent else "")
    emit(json_out, r, ["已彻底删除" if permanent else "已删除(可在项目回收站恢复)"])
