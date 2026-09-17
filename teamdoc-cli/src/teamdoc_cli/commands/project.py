"""项目:td project ls / show / join / leave。"""

from __future__ import annotations

import typer

from .. import refs
from ..cli import JSON, emit, guarded
from ..client import Client
from ..console import fmt_time, table
from ..errors import ApiError

app = typer.Typer(no_args_is_help=True, help="项目")


def _marks(p: dict) -> str:
    return " ".join(filter(None, ["个人" if p.get("isPersonal") else "",
                                  "公开" if p.get("isPublic") else ""]))


@app.command("ls")
@guarded
def ls(public: bool = typer.Option(False, "--public", help="列可加入的公开项目(发现广场)"),
       all_: bool = typer.Option(False, "--all", help="管理员视角列全站项目(含未加入的)"),
       json_out: bool = JSON):
    """项目列表(默认我参加的)"""
    c = Client()
    if public:
        # 只列还没加入的:已加入的公开项目在默认列表里就带「公开」标记,再列一遍是噪音
        rows = [p for p in (c.json("GET", "/api/discover/projects") or [])
                if not p.get("isMember")]
        lines = (table(["ID", "名称", "加入后角色", "成员数", "文档数", "最近活跃"],
                       [[p["id"], p["name"], p.get("joinRole") or "-",
                         str(p.get("memberCount", "-")), str(p.get("docCount", "-")),
                         fmt_time(p.get("lastUpdatedAt"))] for p in rows]) if rows
                 else ["(没有可加入的公开项目)"])
    else:
        rows = c.json("GET", "/api/projects", params={"all": "1"} if all_ else None)
        lines = table(["ID", "名称", "我的角色", "文档数", "最近活跃", "标记"],
                      [[p["id"], p["name"], p.get("myRole") or "-", str(p.get("docCount", "-")),
                        fmt_time(p.get("lastUpdatedAt")), _marks(p)] for p in rows])
    emit(json_out, rows, lines)


@app.command("show")
@guarded
def show(project: str = typer.Argument(..., help="项目 ID 或名称"),
         json_out: bool = JSON):
    """项目详情(可见性 / 我的角色 / 规模)"""
    p = refs.project(Client(), project)
    lines = [f"{p['name']}({p['id']})",
             "可见性  : " + ("公开(任何登录用户可发现并自助加入)" if p.get("isPublic")
                           else "私有(仅项目成员可见)")]
    if p.get("isPublic") and not p.get("isMember"):
        lines.append(f"加入后  : {p.get('joinRole') or '-'}(自助加入拿到的角色)")
    lines.append(f"我的角色: {p.get('myRole') or '-'}" + ("(成员)" if p.get("isMember") else ""))
    lines.append(f"规模    : {p.get('memberCount', '-')} 成员 · {p.get('docCount', '-')} 文档"
                 f" · 最近活跃 {fmt_time(p.get('lastUpdatedAt'))}")
    if p.get("description"):
        lines.append(f"描述    : {p['description']}")
    emit(json_out, p, lines)


@app.command("join")
@guarded
def join(project: str = typer.Argument(..., help="项目 ID 或名称(公开项目)"),
         json_out: bool = JSON):
    """自助加入公开项目(加入前看不到内容;角色由项目设置决定)"""
    c = Client()
    try:
        # 先按 ID 直打端点,不预查存在性:公开项目对未加入者本就 403,预查只会把服务端
        # 那句"该项目未公开,无法自助加入"换成一句含糊的权限错误
        p = c.json("POST", f"/api/projects/{project}/join")
    except ApiError as e:
        if e.status not in (400, 404):   # 400 = 不是合法 ID,404 = ID 不存在 → 回落到名称
            raise
        p = c.json("POST", f"/api/projects/{refs.project(c, project, include_public=True)['id']}/join")
    emit(json_out, p, [f"已加入:{p['name']}({p['id']})· 我的角色 {p.get('myRole') or '-'}",
                       f"下一步:td doc ls {p['id']}"])


@app.command("leave")
@guarded
def leave(project: str = typer.Argument(..., help="项目 ID 或名称"),
          json_out: bool = JSON):
    """退出项目(末代所有者需先在网页端转让所有权)"""
    c = Client()
    p = refs.project(c, project)
    r = c.json("POST", f"/api/projects/{p['id']}/leave")
    emit(json_out, r, [f"已退出:{p['name']}({p['id']})——文档、云空间与回收站不再可见"])
