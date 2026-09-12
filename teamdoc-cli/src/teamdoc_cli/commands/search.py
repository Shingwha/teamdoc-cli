"""搜索:td search —— 跨资源的全文搜索(文档 + 文件)。

一次查询同时返回文档与文件,所以它挂在顶层而不是 `td doc` 下:组 = 资源域,
跨资源的能力与 `td recent` 同层(此前叫 `td doc search`,`--type` 与父组名打架)。
"""

from __future__ import annotations

import typer

from ..client import Client
from ..output import handle, print_json, table


@handle
def search(q: str = typer.Argument(..., help="关键词"),
           type_: str = typer.Option("all", "--type", help="all | docs | files"),
           json_out: bool = typer.Option(False, "--json")):
    """全文搜索(范围 = 已参加的项目;公开项目需先加入才搜得到)"""
    r = Client().json("GET", "/api/search", params={"q": q, "type": type_})
    if json_out:
        print_json(r)
        return
    if r.get("docs"):
        print("== 文档 ==")
        table(["ID", "标题", "项目", "片段"],
              [[d["id"], d["title"], d.get("projectName", ""), (d.get("snippet") or "").replace("\n", " ")]
               for d in r["docs"]])
    if r.get("files"):
        print("== 文件 ==")
        table(["ID", "文件名", "项目"],
              [[f["id"], f["name"], f.get("projectName", "")] for f in r["files"]])
    if not r.get("docs") and not r.get("files"):
        print("(无结果)")
