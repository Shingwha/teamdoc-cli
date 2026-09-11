"""输出辅助:人类可读表格/时间本地化;--json 原样输出;统一错误出口。"""

from __future__ import annotations

import functools
import json
import sys
from datetime import datetime, timezone

import typer

from .client import ApiError
from .config import ConfigError


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def fmt_time(iso: str | None) -> str:
    """服务端时间是 naive-UTC 的 isoformat,转本地时区展示。"""
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def fmt_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def table(headers: list[str], rows: list[list[str]]) -> None:
    """简易对齐表格(GBK 控制台不严格对齐中文宽度,但内容完整可读)。"""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))


def read_text_input(file: str | None, *, required: bool = False) -> str | None:
    """正文来源:--file 路径 / `-` 或管道 stdin / 省略。"""
    if file == "-":
        return sys.stdin.read()
    if file:
        from pathlib import Path
        try:
            return Path(file).read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigError(f"读不到正文文件({file}):{e}") from e
    if not sys.stdin.isatty():  # 管道直传:cat xx.md | td doc edit id -
        return sys.stdin.read()
    if required:
        raise ConfigError("需要正文:用 --file 路径、`-`,或管道传入")
    return None


def handle(fn):
    """统一错误出口:ApiError → 1,ConfigError → 2。所有命令注册前包一层。"""

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except ApiError as e:
            typer.secho(f"API 错误 {e}", fg=typer.colors.RED, err=True)
            if e.needs_write_scope:
                typer.secho("提示:当前令牌可能只有 read 权限。到网页「个人设置 → 访问令牌」"
                            "创建 read,write 令牌后重新 td login。", fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(1)
        except ConfigError as e:
            typer.secho(str(e), fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(2)
        except OSError as e:
            # 本地文件读写失败(路径不存在/无权限/磁盘满等):干净报错,不甩 traceback
            typer.secho(f"本地文件错误:{e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        except BrokenPipeError:
            raise typer.Exit(0)

    return wrapper


def ensure_utf8() -> None:
    """GBK 控制台兜底:无法编码的字符替换而不是崩掉。"""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc and enc not in ("utf-8", "utf8"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
