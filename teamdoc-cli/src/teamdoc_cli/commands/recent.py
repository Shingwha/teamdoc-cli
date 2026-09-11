"""td recent:我参与项目的最近动态(文件 + 文档)。"""

from __future__ import annotations

import typer

from ..client import Client
from ..output import fmt_size, fmt_time, handle, print_json, table


@handle
def recent(limit: int = typer.Option(20, "--limit", "-n", help="每类条数上限(1-100)"),
           json_out: bool = typer.Option(False, "--json")):
    """我参与项目的最近文件与文档"""
    r = Client().json("GET", "/api/recent", params={"limit": max(1, min(limit, 100))})
    if json_out:
        print_json(r)
        return
    if r.get("files"):
        print("== 最近文件 ==")
        table(["ID", "文件名", "项目", "大小", "时间"],
              [[f["id"], f["name"], f.get("projectName", ""), fmt_size(f.get("size")),
                fmt_time(f.get("createdAt"))] for f in r["files"]])
    if r.get("docs"):
        print("== 最近文档 ==")
        table(["ID", "标题", "项目", "更新"],
              [[d["id"], d["title"], d.get("projectName", ""), fmt_time(d.get("updatedAt"))]
               for d in r["docs"]])
    if not r.get("files") and not r.get("docs"):
        print("(没有动态——加入项目或上传文件后这里会有内容)")
