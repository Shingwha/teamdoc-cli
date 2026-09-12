"""td api:任意接口透传(lark-cli 风格的逃生舱),覆盖 v1 子命令没做的能力。"""

from __future__ import annotations

import json
import sys

import typer

from ..client import Client
from ..output import handle, print_json

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _looks_like_msys_rewrite(path: str) -> bool:
    """判断参数是否已被 Git Bash(MSYS)改写成 Windows 路径。

    MSYS 会把"以 / 开头的参数"当 POSIX 路径翻译成 Windows 路径后再生效
    (`/api/projects` → `C:/Program Files/Git/api/projects`),程序拿到的已经是被改写过的串,
    代码里还原不了 —— 只能认出这个特征并告诉用户加 `MSYS_NO_PATHCONV=1`。
    判据:盘符开头 + 含接口段(正常用户不会这么敲路径)。
    """
    return path[1:3] == ":/" and ("/api/" in path or path.endswith("/api"))


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
        msg = "路径必须以 / 开头,如 /api/projects"
        if _looks_like_msys_rewrite(path):
            msg += (f"(实际收到的是 {path} —— Git Bash 把该参数改写成了 Windows 路径;"
                    "请改成 `MSYS_NO_PATHCONV=1 td api ...` 再执行,或改用 PowerShell / CMD)")
        typer.secho(msg, fg=typer.colors.RED, err=True)
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
