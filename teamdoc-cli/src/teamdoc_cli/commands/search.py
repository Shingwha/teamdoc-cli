"""搜索与最近动态:td search / td recent。

两者在服务端是同一个端点(`GET /api/search`):不带 q 就是最近动态,范围收窄成
"我参加的项目"、按时间倒序。CLI 保留两个名字,因为"搜关键词"与"看我最近在动什么"
是两个意图;行渲染共用一份,差别只有列。
"""

from __future__ import annotations

import typer

from ..cli import JSON, emit, guarded
from ..client import Client
from ..console import fmt_size, fmt_time, table


def _render(r: dict, *, snippet: bool, size: bool, head: str, empty: str) -> list[str]:
    """结果行:文档一段、文件一段。snippet 显示命中片段(搜索),否则显示时间(最近)。"""
    lines: list[str] = []
    if r.get("docs"):
        lines += [f"== {head}文档 =="] + table(
            ["ID", "标题", "项目", "片段" if snippet else "更新"],
            [[d["id"], d["title"], d.get("projectName", ""),
              (d.get("snippet") or "").replace("\n", " ") if snippet
              else fmt_time(d.get("updatedAt"))] for d in r["docs"]]) + [""]
    if r.get("files"):
        lines += [f"== {head}文件 =="] + table(
            ["ID", "文件名", "项目"] + (["大小", "上传"] if size else []),
            [[f["id"], f["name"], f.get("projectName", "")]
             + ([fmt_size(f.get("size")), fmt_time(f.get("createdAt"))] if size else [])
             for f in r["files"]]) + [""]
    return lines[:-1] if lines else [empty]


@guarded
def search(q: str = typer.Argument(..., help="关键词"),
           type_: str = typer.Option("all", "--type", help="all | docs | files"),
           json_out: bool = JSON):
    """全文搜索(范围 = 已参加的项目;公开项目需先加入才搜得到)"""
    r = Client().json("GET", "/api/search", params={"q": q, "type": type_})
    emit(json_out, r, _render(r, snippet=True, size=False, head="", empty="(无结果)"))


@guarded
def recent(limit: int = typer.Option(20, "--limit", "-n", help="每类条数上限(最多 100)"),
           json_out: bool = JSON):
    """我参与项目的最近文件与文档"""
    r = Client().json("GET", "/api/search", params={"limit": limit})
    emit(json_out, r, _render(r, snippet=False, size=True, head="最近",
                              empty="(没有动态——加入项目或上传文件后这里会有内容)"))
