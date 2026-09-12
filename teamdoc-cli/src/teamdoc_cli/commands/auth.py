"""登录与身份:td login / logout / whoami。

它们是**顶层命令**(在 main.py 注册),刻意不另设 `td auth` 子命令组 ——
同一份函数注册两遍,`td --help` 里就会出现两套名字指同一件事。
"""

from __future__ import annotations

import httpx
import typer

from .. import config
from ..client import Client
from ..output import handle, print_json


@handle
def login(server: str = typer.Option("", "--server", "-s", help="服务器地址,如 http://192.168.1.10:8000"),
          token: str = typer.Option("", "--token", "-t", help="访问令牌(tdp_ 开头,网页端创建);缺省交互输入")):
    """验证令牌并保存到 ~/.teamdoc/config.json"""
    server = (server or typer.prompt("服务器地址")).rstrip("/")
    token = token or typer.prompt("访问令牌(tdp_ 开头)", hide_input=True)
    if not token.startswith("tdp_"):
        typer.secho("令牌应以 tdp_ 开头(网页「个人设置 → 访问令牌」创建)", fg=typer.colors.YELLOW)
    try:
        resp = httpx.get(server.rstrip("/") + "/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"}, timeout=15)
    except httpx.HTTPError as e:
        typer.secho(f"连不上 {server}:{e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if resp.status_code == 401:
        typer.secho("令牌无效(401):确认粘贴完整、未吊销", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if resp.status_code >= 400:
        typer.secho(f"服务器返回 HTTP {resp.status_code}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    me = resp.json()
    user = me["user"]
    scopes = me.get("auth", {}).get("scopes", [])
    config.save(server, token, {"email": user["email"], "name": user["name"]})
    typer.secho(f"已登录:{user['name']} <{user['email']}> @ {server}", fg=typer.colors.GREEN)
    if "write" not in scopes:
        typer.secho("注意:当前令牌只有 read 权限,写命令(建文档/上传等)会 403;"
                    "需要的话到网页端创建 read,write 令牌后重新登录。", fg=typer.colors.YELLOW)


@handle
def logout():
    """删除本地保存的令牌(令牌本身的吊销在网页端操作)"""
    if config.clear():
        print("已清除本地配置。注意:令牌本身仍然有效,如需吊销请到网页「个人设置 → 访问令牌」。")
    else:
        print("本地本就没有保存的配置。")


@handle
def whoami(json_out: bool = typer.Option(False, "--json", help="输出原始 JSON")):
    """当前登录身份与令牌权限"""
    me = Client().json("GET", "/api/auth/me")
    if json_out:
        print_json(me)
        return
    u = me["user"]
    a = me.get("auth", {})
    print(f"{u['name']} <{u['email']}>")
    print(f"服务器 : {Client().server}")
    print(f"认证   : {a.get('via', '?')}(scopes: {','.join(a.get('scopes', [])) or '-'})")
    if u.get("isAdmin"):
        typer.secho("管理员", fg=typer.colors.CYAN)
