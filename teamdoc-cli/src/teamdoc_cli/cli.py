"""命令外壳:每条命令都套同一层壳。

    JSON    声明式 --json 选项(所有命令共用一个,帮助文本只有一份)
    emit    命令的唯一出口:--json 打原始数据,否则打人话视图
    guarded 错误 → 退出码的唯一翻译处(命令体里不写 try/except)

命令因此只有三件事:解析引用 → 调 API → emit。
"""

from __future__ import annotations

import functools
from typing import Callable

import typer

from . import console
from .errors import EXIT_API, EXIT_OK, EXIT_USAGE, ApiError, ConfigError, InputError


# 所有命令共用的 --json 选项:帮助文本只有这一份,加选项也只改这一处。
# (typer 注册命令时会 copy 一份 OptionInfo,所以模块级常量不会互相污染。)
JSON = typer.Option(False, "--json", help="输出原始 JSON(供脚本解析)")


def emit(json_out: bool, data=None, human: list[str] | Callable[[], None] = ()) -> None:
    """命令收尾。human 有两种形态:行列表(最常见),或一个自己打印的可调用 ——
    `td doc show` 要把正文写进 stdout / 文件,不是一个行列表能表达的。"""
    if json_out:
        print(console.json_text(data))
    elif callable(human):
        human()
    elif human:
        print("\n".join(human))


def guarded(fn):
    """把异常翻成退出码与提示。顺序要紧:BrokenPipeError 是 OSError 的子类,
    放后面就会被"本地文件错误"那条抢走(`td doc show x | head` 会打出一句噪音)。"""

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except ApiError as e:
            typer.secho(f"API 错误 {e}", fg=typer.colors.RED, err=True)
            for line in explain(e):
                typer.secho(line, fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(EXIT_API) from e
        except (ConfigError, InputError) as e:
            typer.secho(str(e), fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(EXIT_USAGE) from e
        except BrokenPipeError:   # 下游提前关掉管道(`| head`)
            raise typer.Exit(EXIT_OK)
        except OSError as e:      # 本地文件读写失败:路径不存在、无权限、磁盘满
            typer.secho(f"本地文件错误:{e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_API) from e

    return wrapper


def explain(e: ApiError) -> list[str]:
    """把拒绝翻译成"下一步做什么"。

    服务端把 code 与现场数据一起回过来了,就该用上:只说一句"已被他人修改"会让人
    无从下手,而 409 的 detail 里就带着当前版本与正文长度 —— 用不上也要看得见,
    所以未识别的字段按 k=v 兜底列出。
    """
    d = e.detail or {}
    if e.needs_write_scope:
        return ["当前令牌只有 read 权限:到网页「个人设置 → 访问令牌」创建 read,write 令牌,"
                "再 td login 一次。"]
    if e.code == "CONFLICT" and "currentVersion" in d:
        lines = [f"服务端当前版本:v{d['currentVersion']}"
                 + (f"(由 {d['by']} 保存)" if d.get("by") else "")]
        if isinstance(d.get("currentContent"), str):
            lines.append(f"服务端正文 {len(d['currentContent'])} 字;"
                         "先 `td doc show <文档ID> -o theirs.md` 取回来对比合并,再整体覆盖写入")
        return lines
    if e.code == "JOIN_REQUIRED":
        return ["这是公开项目,还没加入:先 `td project join <项目ID或名称>`"]
    return [f"{k}={str(v)[:80]}" for k, v in d.items()]
