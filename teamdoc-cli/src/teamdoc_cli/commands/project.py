"""项目:td project ls。也提供"按引用解析项目"(ID 或唯一名称)给 doc/file 命令复用。"""

from __future__ import annotations

import re

import typer

from ..client import ApiError, Client
from ..output import fmt_time, handle, print_json, table

app = typer.Typer(no_args_is_help=True, help="项目")

_ID_RE = re.compile(r"^[0-9a-f]{16}$")


@app.command("ls")
@handle
def ls(all_: bool = typer.Option(False, "--all", help="管理员视角列全部项目(含未加入的)"),
       json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """项目列表"""
    rows = Client().json("GET", "/api/projects", params={"all": "1"} if all_ else None)
    if json_out:
        print_json(rows)
        return
    table(
        ["ID", "名称", "我的角色", "文档数", "最近活跃", "标记"],
        [[p["id"], p["name"], p.get("myRole") or "-", str(p.get("docCount", "-")),
          fmt_time(p.get("lastUpdatedAt")),
          " ".join(filter(None, [
              "个人" if p.get("isPersonal") else "",
              "公开" if p.get("isPublic") else "",
          ]))] for p in rows],
    )


def resolve_project(client: Client, ref: str) -> dict:
    """按 ID 精确取;否则按名称唯一匹配(方便人敲命令)。返回项目 JSON(含 id)。"""
    if _ID_RE.match(ref):
        try:
            return client.json("GET", f"/api/projects/{ref}")
        except ApiError as e:
            if e.status != 404:
                raise
            # 16 位十六进制也可能恰好是名字,继续走名称匹配
    rows = client.json("GET", "/api/projects")
    hits = [p for p in rows if p["name"] == ref]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ApiError(400, "VALIDATION", f"项目名「{ref}」有 {len(hits)} 个同名项目,请用 ID 区分")
    raise ApiError(404, "NOT_FOUND", f"找不到项目「{ref}」(未参加或名字不符,td project ls 查看)")
