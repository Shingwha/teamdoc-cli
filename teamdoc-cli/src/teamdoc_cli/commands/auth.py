"""身份:td login / logout / whoami(注册在顶层,见 main.py)。"""

from __future__ import annotations

import typer

from .. import config
from ..cli import JSON, emit, guarded
from ..client import Client
from ..errors import EXIT_API, ApiError


@guarded
def login(server: str = typer.Option("", "--server", "-s", help="服务器地址,如 http://192.168.1.10:8000"),
          token: str = typer.Option("", "--token", "-t", help="访问令牌(tdp_ 开头,网页端创建);缺省交互输入")):
    """验证令牌并保存到 ~/.teamdoc/config.json"""
    server = (server or typer.prompt("服务器地址")).rstrip("/")
    token = token or typer.prompt("访问令牌(tdp_ 开头)", hide_input=True)
    if not token.startswith("tdp_"):
        typer.secho("令牌应以 tdp_ 开头(网页「个人设置 → 访问令牌」创建)", fg=typer.colors.YELLOW)
    try:
        me = Client(server, token, timeout=15).json("GET", "/api/auth/me")
    except ApiError as e:
        # 此刻还没有可用凭据,失败就是"这次登录没成" —— 比通用错误出口具体
        why = (f"连不上 {server}:{e.message}" if e.status == 0
               else f"令牌无效或已吊销({e.code}:{e.message})")
        typer.secho(f"登录失败:{why}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_API) from e
    user, scopes = me["user"], me.get("auth", {}).get("scopes", [])
    config.save(server, token)
    typer.secho(f"已登录:{user['name']} <{user['email']}> @ {server}", fg=typer.colors.GREEN)
    if "write" not in scopes:
        typer.secho("注意:当前令牌只有 read 权限,写命令(建文档/上传等)会 403;"
                    "需要的话到网页端创建 read,write 令牌后重新登录。", fg=typer.colors.YELLOW)


@guarded
def logout():
    """删除本地保存的令牌(令牌本身的吊销在网页端操作)"""
    print("已清除本地配置。注意:令牌本身仍然有效,如需吊销请到网页「个人设置 → 访问令牌」。"
          if config.clear() else "本地本就没有保存的配置。")


@guarded
def whoami(json_out: bool = JSON):
    """当前登录身份与令牌权限"""
    c = Client()
    me = c.json("GET", "/api/auth/me")
    u, a = me["user"], me.get("auth", {})
    lines = [f"{u['name']} <{u['email']}>",
             f"服务器 : {c.server}",
             f"认证   : {a.get('via', '?')}(scopes: {','.join(a.get('scopes', [])) or '-'})"]
    if u.get("isAdmin"):
        lines.append("管理员")   # 人话视图是纯文本行:带色字符串在管道里会变成 ANSI 噪音
    emit(json_out, me, lines)
