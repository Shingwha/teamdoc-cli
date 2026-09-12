"""文档:td doc ls / show / new / edit / rm / search。"""

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
        table(["字段", "值"], [
            ["ID", d["id"]], ["项目", d["projectId"]], ["标题", d["title"]],
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
        content_arg: str = typer.Argument("", help="`-` 表示正文从 stdin 读;也可给正文文件路径"),
        parent: str = typer.Option("", "--parent", help="父文档 ID(建子文档)"),
        file: str = typer.Option("", "--file", "-f", help="正文来源:路径或 `-`(stdin);缺省建空文档"),
        json_out: bool = typer.Option(False, "--json")):
    """新建文档(可同时写入正文,支持 cat xx.md | td doc new 项目 "标题" -)"""
    if content_arg:
        if file:
            typer.secho("正文来源重复:位置参数 - 与 --file 二选一", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        file = content_arg
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
         content_arg: str = typer.Argument("", help="`-` 表示正文从 stdin 读;也可给正文文件路径"),
         file: str = typer.Option("", "--file", "-f", help="正文来源:路径或 `-`(stdin)"),
         append: bool = typer.Option(False, "--append", help="追加而非覆盖"),
         json_out: bool = typer.Option(False, "--json")):
    """写入正文(覆盖,或 --append 追加;支持 cat xx.md | td doc edit 文档ID -)"""
    if content_arg:
        if file:
            typer.secho("正文来源重复:位置参数 - 与 --file 二选一", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        file = content_arg
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


@app.command("search")
@handle
def search(q: str = typer.Argument(..., help="关键词"),
           type_: str = typer.Option("all", "--type", help="all | docs | files"),
           json_out: bool = typer.Option(False, "--json")):
    """全文搜索(含已参加项目与公开项目)"""
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
