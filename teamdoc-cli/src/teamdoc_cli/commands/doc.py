"""文档:td doc ls / show / new / edit / mv / rm。"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from .. import refs
from ..cli import JSON, emit, guarded
from ..client import Client
from ..console import fmt_time, read_text, table
from ..errors import InputError

app = typer.Typer(no_args_is_help=True, help="文档")


def _tree_lines(nodes, depth: int = 0) -> list[str]:
    lines: list[str] = []
    for n in nodes:
        lines.append("  " * depth + f"{n['title']}  ({n['id']})")
        lines += _tree_lines(n.get("children") or [], depth + 1)
    return lines


@app.command("ls")
@guarded
def ls(project: str = typer.Argument(..., help="项目 ID 或名称"),
       json_out: bool = JSON):
    """文档树"""
    c = Client()
    tree = c.json("GET", f"/api/projects/{refs.project(c, project)['id']}/docs/tree")
    emit(json_out, tree, _tree_lines(tree) or ["(空文档树)"])


@app.command("show")
@guarded
def show(doc_id: str = typer.Argument(..., help="文档 ID"),
         out: str = typer.Option("", "-o", "--output", help="写到文件而非 stdout"),
         meta: bool = typer.Option(False, "--meta", help="只看元数据,不输出正文"),
         json_out: bool = JSON):
    """读取文档"""
    d = Client().json("GET", f"/api/docs/{doc_id}")

    def write_content() -> None:
        if out:
            Path(out).write_text(d.get("content") or "", encoding="utf-8")
            print(f"已写入 {out}")
        else:
            sys.stdout.write(d.get("content") or "")

    if meta:
        # 位置用服务端的 location 契约 {projectId, projectName, path[]}(与文件详情同形),
        # 不在客户端自己拼路径
        loc = d.get("location") or {}
        where = " / ".join([str(loc.get("projectName") or d["projectId"])]
                           + [str(x) for x in (loc.get("path") or [])])
        human = table(["字段", "值"], [
            ["ID", d["id"]], ["项目", d["projectId"]], ["标题", d["title"]], ["位置", where],
            ["字数", str(d.get("contentChars", "-"))],
            ["版本(保存次数)", str(d.get("version", "-"))],
            ["创建", fmt_time(d.get("createdAt"))], ["更新", fmt_time(d.get("updatedAt"))],
        ])
    else:
        human = write_content
    emit(json_out, d, human)


@app.command("new")
@guarded
def new(project: str = typer.Argument(..., help="项目 ID 或名称"),
        title: str = typer.Argument(..., help="标题"),
        parent: str = typer.Option("", "--parent", help="父文档 ID(建子文档)"),
        file: str = typer.Option("", "--file", "-f",
                                 help="正文来源:路径或 `-`(stdin);裸管道同样生效;缺省建空文档"),
        json_out: bool = JSON):
    """新建文档(可同时写入正文:cat xx.md | td doc new 项目 "标题" --file -)"""
    # 正文先读、文档后建:反过来的话,正文读失败会留下**一篇空文档**
    content = read_text(file)
    c = Client()
    p = refs.project(c, project)
    body = {"title": title}
    if parent:
        body["parentId"] = parent
    d = c.json("POST", f"/api/projects/{p['id']}/docs", json_body=body)
    if content is not None:
        c.json("PUT", f"/api/docs/{d['id']}/content", json_body={"content": content})
    emit(json_out, d, [f"已创建:{d['title']}({d['id']})",
                       f"{c.server}/#/p/{p['id']}/docs/{d['id']}"])


@app.command("edit")
@guarded
def edit(doc_id: str = typer.Argument(..., help="文档 ID"),
         file: str = typer.Option("", "--file", "-f",
                                  help="正文来源:路径或 `-`(stdin);裸管道同样生效"),
         append: bool = typer.Option(False, "--append", help="追加而非覆盖"),
         if_version: int = typer.Option(0, "--if-version",
                                        help="只在服务端仍是这一版时写入(不匹配则报错,不改动);仅覆盖写入有效"),
         json_out: bool = JSON):
    """写入正文(覆盖,或 --append 追加:cat xx.md | td doc edit 文档ID)"""
    content = read_text(file, required=True)
    c = Client()
    if append:
        if if_version:
            # 追加是"读当下再拼",没有"基于哪一版"的形状,基线在这里没有意义
            raise InputError("--append 是追加(读-改-写),不接受 --if-version;要卡基线请用覆盖写入")
        r = c.json("POST", f"/api/docs/{doc_id}/append", json_body={"content": content})
    else:
        body = {"content": content}
        if if_version:
            body["baseVersion"] = if_version   # 服务端字段名是 baseVersion
        r = c.json("PUT", f"/api/docs/{doc_id}/content", json_body=body)
    emit(json_out, r, [f"{'已追加' if append else '已保存'}(版本计数:{r.get('version', '-')})"])


@app.command("mv")
@guarded
def mv(doc_id: str = typer.Argument(..., help="文档 ID(整棵子树一起移动)"),
       to: str = typer.Option(..., "--to", help="目标项目 ID 或名称"),
       parent: str = typer.Option("", "--parent", help="目标父文档 ID(缺省落在目标项目根)"),
       yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认(跨项目时的提示)"),
       json_out: bool = JSON):
    """移动文档(项目内调整位置或跨项目转移;只改归属,不复制内容)

    跨项目移动**不会带走附件**:文件按自己的项目归属,正文引用的文件仍留在原项目。
    所以先用 move-check 问清服务端"有多少篇文档跟着走、哪些文件会留下",确认后再动手
    —— 不这么做,用户看到的是"搬过去之后附件全打不开了"。
    """
    c = Client()
    p = refs.project(c, to)
    chk = c.json("GET", f"/api/docs/{doc_id}/move-check",
                 params={"projectId": p["id"], "parentId": parent or ""})
    body: dict = {"projectId": p["id"]}
    if parent:
        body["parentId"] = parent
    if not json_out:
        print(f"将移动到「{p['name']}」" + (f" / 文档 {parent}" if parent else " 根目录")
              + f",共 {chk.get('docs', 1)} 篇文档(含子文档)")
        left = chk.get("foreignFiles") or []
        if left:
            names = "、".join(f"「{x['name']}」" for x in left[:3])
            more = f" 等 {len(left)} 个" if len(left) > 3 else ""
            print(f"注意:正文引用的 {names}{more}文件仍留在原项目(移动不会带走附件)")
        if not yes and not typer.confirm("确认移动?"):
            raise typer.Abort()
    r = c.json("POST", f"/api/docs/{doc_id}/move", json_body=body)
    emit(json_out, r, [f"已移动:{r.get('title', doc_id)}({r.get('movedDocs', 1)} 篇文档)"])


@app.command("rm")
@guarded
def rm(doc_id: str = typer.Argument(..., help="文档 ID(整个子树一起进回收站)"),
       yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
       json_out: bool = JSON):
    """删除文档(软删除,可在项目回收站恢复)"""
    if not yes and not typer.confirm(f"确定删除文档 {doc_id}?(子树一起进回收站,可恢复)"):
        raise typer.Abort()
    r = Client().json("DELETE", f"/api/docs/{doc_id}")
    emit(json_out, r, ["已删除(可在项目回收站恢复)"])
