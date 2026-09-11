"""td api:任意接口透传(lark-cli 风格的逃生舱),覆盖 v1 子命令没做的能力。"""

from __future__ import annotations

import json
import sys

import typer

from ..client import Client
from ..output import handle, print_json

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


@handle
def api(method: str = typer.Argument(..., help="HTTP 方法:GET/POST/PUT/PATCH/DELETE"),
        path: str = typer.Argument(..., help="接口路径,以 / 开头,如 /api/projects"),
        data: str = typer.Option("", "--data", "-d", help="JSON 请求体(字符串)"),
        raw: bool = typer.Option(False, "--raw", help="原样输出响应字节(下载类接口用)")):
    """直接调用服务端接口(带令牌认证)"""
    m = method.upper()
    if m not in METHODS:
        typer.secho(f"不支持的方法 {method},可用:{'/'.join(sorted(METHODS))}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if not path.startswith("/"):
        typer.secho("路径必须以 / 开头,如 /api/projects", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    json_body = None
    if data:
        try:
            json_body = json.loads(data)
        except json.JSONDecodeError as e:
            typer.secho(f"--data 不是合法 JSON:{e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    resp = Client().request(m, path, json_body=json_body)
    if raw:
        sys.stdout.buffer.write(resp.content)
        return
    try:
        print_json(resp.json())
    except ValueError:
        print(resp.text)
