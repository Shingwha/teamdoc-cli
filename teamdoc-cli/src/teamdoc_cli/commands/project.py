"""项目:td project ls / show / join / leave。

也提供"按引用解析项目"(数字 ID 或唯一名称)给 doc/file 命令复用 —— 它是**所有命令
与项目打交道时唯一的出口**,所以"拒绝时补下一句"也集中在这里,补一处全站生效。
"""

from __future__ import annotations

import typer

from ..client import ApiError, Client
from ..output import fmt_time, handle, print_json, table

app = typer.Typer(no_args_is_help=True, help="项目")


def _marks(p: dict) -> str:
    """标记列(个人 / 公开):两处列表共用,免得各拼一份。"""
    return " ".join(filter(None, [
        "个人" if p.get("isPersonal") else "",
        "公开" if p.get("isPublic") else "",
    ]))


@app.command("ls")
@handle
def ls(public: bool = typer.Option(False, "--public", help="列可加入的公开项目(发现广场)"),
       all_: bool = typer.Option(False, "--all", help="管理员视角列全站项目(含未加入的)"),
       json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """项目列表(默认我参加的)"""
    c = Client()
    if public:
        # 只列未加入的:已加入的公开项目在默认列表里已有「公开」标记,重复列出是噪音
        rows = [p for p in (c.json("GET", "/api/discover/projects") or [])
                if not p.get("isMember")]
    else:
        rows = c.json("GET", "/api/projects", params={"all": "1"} if all_ else None)
    if json_out:
        print_json(rows)
        return
    if public:
        if not rows:
            print("(没有可加入的公开项目)")
            return
        table(["ID", "名称", "加入后角色", "成员数", "文档数", "最近活跃"],
              [[p["id"], p["name"], p.get("joinRole") or "-", str(p.get("memberCount", "-")),
                str(p.get("docCount", "-")), fmt_time(p.get("lastUpdatedAt"))] for p in rows])
        return
    table(
        ["ID", "名称", "我的角色", "文档数", "最近活跃", "标记"],
        [[p["id"], p["name"], p.get("myRole") or "-", str(p.get("docCount", "-")),
          fmt_time(p.get("lastUpdatedAt")), _marks(p)] for p in rows],
    )


@app.command("show")
@handle
def show(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
         json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """项目详情(可见性 / 我的角色 / 规模)"""
    p = resolve_project(Client(), project_ref)
    if json_out:
        print_json(p)
        return
    print(f"{p['name']}({p['id']})")
    print("可见性  : " + ("公开(任何登录用户可发现并自助加入)" if p.get("isPublic")
                      else "私有(仅项目成员可见)"))
    if p.get("isPublic") and not p.get("isMember"):
        print(f"加入后  : {p.get('joinRole') or '-'}(自助加入拿到的角色)")
    print(f"我的角色: {p.get('myRole') or '-'}" + ("(成员)" if p.get("isMember") else ""))
    print(f"规模    : {p.get('memberCount', '-')} 成员 · {p.get('docCount', '-')} 文档"
          f" · 最近活跃 {fmt_time(p.get('lastUpdatedAt'))}")
    if p.get("description"):
        print(f"描述    : {p['description']}")


def resolve_project(client: Client, ref: str, *, include_public: bool = False) -> dict:
    """把项目引用(ID 或名称)解析成项目对象。

    **不猜引用格式**:直接按 ID 打一次,服务端说了算 ——
      400 = 不是合法 ID(如中文名) / 404 = ID 不存在(如数字恰好是项目名),
    两种情况都回落到名称唯一匹配;403 等真实错误原样抛出,不掩盖权限问题。
    ID 的格式归服务端定义(整数化前后变过一次),CLI 不复制这份知识。

    include_public=True 时,名称兜底也会查**发现广场** —— 未加入的公开项目不在
    /api/projects 里,少了这条路 `td project join <项目名>` 恰好会找不到。

    两种"拒绝"在这里补下一句(所有命令共用的唯一出口):
    未加入的公开项目指向 `td project join`,找不到名字时指向 `td project ls --public`。
    """
    try:
        return client.json("GET", f"/api/projects/{ref}")
    except ApiError as e:
        if e.status not in (400, 404):
            if e.code == "JOIN_REQUIRED":
                raise ApiError(e.status, e.code,
                               f"{e.message};用 `td project join {ref}` 加入后再试") from e
            raise
    rows = client.json("GET", "/api/projects")
    if include_public:
        plaza = client.json("GET", "/api/discover/projects") or []
        seen = {p["id"] for p in rows}
        rows += [p for p in plaza if p["id"] not in seen]
    hits = [p for p in rows if p["name"] == ref]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ApiError(400, "VALIDATION", f"项目名「{ref}」有 {len(hits)} 个同名项目,请用 ID 区分")
    raise ApiError(404, "NOT_FOUND",
                   f"找不到项目「{ref}」(未参加或名字不符;`td project ls` 看我的项目,"
                   f"`td project ls --public` 看可加入的公开项目)")


@app.command("join")
@handle
def join(project_ref: str = typer.Argument(..., help="项目 ID 或名称(公开项目)"),
         json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """自助加入公开项目(加入前看不到内容;角色由项目设置决定)"""
    c = Client()
    # 先按 ID 直接打端点,不预查存在性 —— 公开项目对未加入者本就 403,预查只会把
    # 服务端那句"该项目未公开,无法自助加入"换成一句含糊的权限错误
    try:
        p = c.json("POST", f"/api/projects/{project_ref}/join")
    except ApiError as e:
        if e.status not in (400, 404):   # 400=不是合法 ID,404=ID 不存在 → 回落到名称
            raise
        p = c.json("POST", f"/api/projects/{resolve_project(c, project_ref, include_public=True)['id']}/join")
    if json_out:
        print_json(p)
        return
    print(f"已加入:{p['name']}({p['id']})· 我的角色 {p.get('myRole') or '-'}")
    print(f"下一步:td doc ls {p['id']}")


@app.command("leave")
@handle
def leave(project_ref: str = typer.Argument(..., help="项目 ID 或名称"),
          json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """退出项目(末代所有者需先在网页端转让所有权)"""
    c = Client()
    p = resolve_project(c, project_ref)
    r = c.json("POST", f"/api/projects/{p['id']}/leave")
    if json_out:
        print_json(r)
        return
    print(f"已退出:{p['name']}({p['id']})——文档、云空间与回收站不再可见")
