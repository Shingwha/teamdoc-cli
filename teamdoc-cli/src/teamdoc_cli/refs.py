"""引用解析:用户手里的一串字符 → 服务端要的 ID。

    project()   项目:ID 或名称(名称需唯一)
    item()      云空间条目:文件或文件夹,用户只给一个 ID
    move_body() 移动请求体(文件与文件夹的父级字段名不同,这里一次填平)

所有命令与项目、与云空间条目打交道都从这里走 —— 所以"被拒时补一句出路"也只写在这里。
"""

from __future__ import annotations

from .client import Client
from .errors import ApiError


def project(client: Client, ref: str, *, include_public: bool = False) -> dict:
    """按 ID 或名称解析项目。

    **不猜引用格式**:先按 ID 打一次,由服务端说了算(400 = 不是合法 ID,404 = ID 不存在),
    两种情况才回落到按名称唯一匹配;403 之类的真实错误原样抛出,不把权限问题盖成"找不到"
    (JOIN_REQUIRED 的"下一句"由错误出口 cli.explain 统一补,这里不重复)。

    include_public=True 时名称兜底也查发现广场 —— 未加入的公开项目不在 /api/projects 里,
    少了这条路 `td project join <项目名>` 恰好会找不到。
    """
    try:
        return client.json("GET", f"/api/projects/{ref}")
    except ApiError as e:
        if e.status not in (400, 404):
            raise
    rows = client.json("GET", "/api/projects")
    if include_public:
        plaza = client.json("GET", "/api/discover/projects") or []
        seen = {p["id"] for p in rows}
        rows = rows + [p for p in plaza if p["id"] not in seen]
    hits = [p for p in rows if p["name"] == ref]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ApiError(400, "VALIDATION", f"项目名「{ref}」有 {len(hits)} 个同名项目,请改用 ID")
    raise ApiError(404, "NOT_FOUND",
                   f"找不到项目「{ref}」(未参加或名字不符;`td project ls` 看我的项目,"
                   f"`td project ls --public` 看可加入的公开项目)")


def item(client: Client, method: str, item_id: str, *, suffix: str = "",
         body: dict | None = None, params: dict | None = None) -> dict:
    """对"文件或文件夹"发一次请求(改名、移动、删除、彻底删除)。

    文件与文件夹在服务端是两张表两套编号,而用户手里只有一个 ID —— 让他回答
    "这是文件还是文件夹"没有道理。**先按文件打,只有 404 才换文件夹重试**:404 意味着
    这次请求什么都没做,换一张表重试是安全的。两边都 404 才是真的不存在;
    第二次的 403 之类要原样抛出 —— 那是真实原因,不能盖成"不存在"。
    (400 VALIDATION 说明 ID 本身形状非法,同样不触发回落。)
    """
    try:
        return client.json(method, f"/api/files/{item_id}{suffix}", json_body=body, params=params)
    except ApiError as e:
        if e.status != 404:
            raise
    try:
        return client.json(method, f"/api/files/folders/{item_id}{suffix}",
                           json_body=body, params=params)
    except ApiError as e:
        if e.status != 404:
            raise
        raise ApiError(404, "NOT_FOUND",
                       f"云空间里没有 ID 为 {item_id} 的文件或文件夹"
                       "(`td file ls <项目>` 列的是文件与文件夹各自的 ID)") from None


def move_body(project_id: str, parent: str | None) -> dict:
    """移动请求体。

    目标父级的字段名在服务端两张表里不同(文件用 folderId、文件夹用 parentId),
    值却只有一个 —— 两个键都带上,各自取所需,CLI 才不必先问用户条目是什么类型。
    """
    return {"projectId": project_id, "folderId": parent or None, "parentId": parent or None}
