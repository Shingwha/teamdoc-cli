"""终端 I/O:人话视图怎么排,正文与文件怎么读进来。

这里的函数只管"显示成什么样",不决定"失败了算几号退出码"(那是 cli.guarded);
格式化函数是纯函数(返回字符串/行列表),打印只在 cli.emit 一处发生。
"""

from __future__ import annotations

import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .errors import InputError


def json_text(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def fmt_time(iso: str | None) -> str:
    """服务端时间是 naive-UTC 的 isoformat,展示时转本地时区。"""
    if not iso:
        return "-"
    try:
        return (datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
                .astimezone().strftime("%Y-%m-%d %H:%M"))
    except ValueError:
        return iso


def fmt_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _width(s: str) -> int:
    """显示宽度:中文与全角标点占两格。按字符数算的话每一列都是参差的。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """对齐的表格(返回行,打印交给 emit)。"""
    widths = [max([_width(str(h))] + [_width(str(r[i])) for r in rows])
              for i, h in enumerate(headers)]

    def line(cells) -> str:
        return "  ".join(str(c) + " " * (widths[i] - _width(str(c)))
                         for i, c in enumerate(cells))

    return [line(headers), "  ".join("-" * w for w in widths)] + [line(r) for r in rows]


def read_text(file: str | None, *, required: bool = False) -> str | None:
    """正文来源:`--file 路径` / `-`(stdin)/ 裸管道 / 什么都没给。

    `--file` 优先于管道;两者都没有时,required 决定是报错还是返回 None(建空文档)。
    """
    if file == "-":
        return sys.stdin.read()
    if file:
        try:
            return Path(file).read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"读不到正文文件({file}):{e}") from e
    if not sys.stdin.isatty():
        return sys.stdin.read()
    if required:
        raise InputError("需要正文:用 --file 路径、`-`,或管道传入")
    return None


def ensure_utf8() -> None:
    """GBK 控制台兜底:编不出来的字符替换掉,而不是让命令崩在最后一步。"""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc and enc not in ("utf-8", "utf8"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
