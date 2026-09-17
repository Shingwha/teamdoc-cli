"""文档:td doc ls / show / new / edit / rm(跨资源的全文搜索是顶层 `td search`)。"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ..client import Client
from ..output import fmt_time, handle, print_json, read_text_input, table
from .project import resolve_project

app = typer.Typer(no_args_is_help=True, help="文档")


def _walk_tree(nodes, depth: int, lines: list[str]) -> None:
    for n in nodes:
        lines.append("  " * depth + f"{n['title']}  ({n['id']})")
        _walk_tree(n.get("children") or [], depth + 1, lines)


@app.command("ls")
@handle
def ls(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
       json_out: bool = typer.Option(False, "--json")):
    """文档树"""
    c = Client()
    p = resolve_project(c, project_ref)
    tree = c.json("GET", f"/api/projects/{p['id']}/docs/tree")
    if json_out:
        print_json(tree)
        return
    if not tree:
        print("(空文档树)")
        return
    lines: list[str] = []
    _walk_tree(tree, 0, lines)
    print("\n".join(lines))


@app.command("show")
@handle
def show(doc_id: str = typer.Argument(..., help="文档 ID"),
         out: str = typer.Option("", "-o", "--output", help="写到文件而非 stdout"),
         meta: bool = typer.Option(False, "--meta", help="只看元数据,不输出正文"),
         json_out: bool = typer.Option(False, "--json")):
    """读取文档"""
    d = Client().json("GET", f"/api/docs/{doc_id}")
    if json_out:
        print_json(d)
        return
    if meta:
        # 位置走服务端的 location 契约 {projectId, projectName, path[]}(HANDOFF §8):
        # 与网页端浮层是同一份数据,别自己在客户端拼路径
        loc = d.get("location") or {}
        where = " / ".join([str(loc.get("projectName") or d["projectId"])]
                           + [str(x) for x in (loc.get("path") or [])])
        table(["字段", "值"], [
            ["ID", d["id"]], ["项目", d["projectId"]], ["标题", d["title"]],
            ["位置", where],
            ["字数", str(d.get("contentChars", "-"))],
            ["版本(保存次数)", str(d.get("version", "-"))],
            ["创建", fmt_time(d.get("createdAt"))], ["更新", fmt_time(d.get("updatedAt"))],
        ])
        return
    if out:
        Path(out).write_text(d.get("content") or "", encoding="utf-8")
        print(f"已写入 {out}")
    else:
        sys.stdout.write(d.get("content") or "")


@app.command("new")
@handle
def new(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
        title: str = typer.Argument(..., help="标题"),
        parent: str = typer.Option("", "--parent", help="父文档 ID(建子文档)"),
        file: str = typer.Option("", "--file", "-f", help="正文来源:路径或 `-`(stdin);裸管道同样生效;缺省建空文档"),
        json_out: bool = typer.Option(False, "--json")):
    """新建文档(可同时写入正文:cat xx.md | td doc new 项目 "标题" --file -)"""
    # 先读正文、再建文档:反过来时正文读失败(路径写错、磁盘错误)会留下**一篇空文档**
    content = read_text_input(file)
    c = Client()
    p = resolve_project(c, project_ref)
    body = {"title": title}
    if parent:
        body["parentId"] = parent
    d = c.json("POST", f"/api/projects/{p['id']}/docs", json_body=body)
    if content is not None:
        c.json("PUT", f"/api/docs/{d['id']}/content", json_body={"content": content})
    if json_out:
        print_json(d)
    else:
        web = f"{c.server}/#/p/{p['id']}/docs/{d['id']}"
        print(f"已创建:{d['title']}({d['id']})\n{web}")


@app.command("edit")
@handle
def edit(doc_id: str = typer.Argument(..., help="文档 ID"),
         file: str = typer.Option("", "--file", "-f", help="正文来源:路径或 `-`(stdin);裸管道同样生效"),
         append: bool = typer.Option(False, "--append", help="追加而非覆盖"),
         json_out: bool = typer.Option(False, "--json")):
    """写入正文(覆盖,或 --append 追加:cat xx.md | td doc edit 文档ID)"""
    content = read_text_input(file, required=True)
    c = Client()
    if append:
        r = c.json("POST", f"/api/docs/{doc_id}/append", json_body={"content": content})
    else:
        r = c.json("PUT", f"/api/docs/{doc_id}/content", json_body={"content": content})
    if json_out:
        print_json(r)
    else:
        action = "已追加" if append else "已保存"
        print(f"{action}(版本计数:{r.get('version', '-')})")


@app.command("rm")
@handle
def rm(doc_id: str = typer.Argument(..., help="文档 ID(整个子树一起进回收站)"),
       yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认")):
    """删除文档(软删除,可在项目回收站恢复)"""
    if not yes and not typer.confirm(f"确定删除文档 {doc_id}?(子树一起进回收站,可恢复)"):
        raise typer.Abort()
    Client().request("DELETE", f"/api/docs/{doc_id}")
    print("已删除(可在项目回收站恢复)")
