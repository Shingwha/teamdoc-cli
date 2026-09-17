"""httpx 客户端:Bearer 注入、服务端错误解析、流式上传/下载。

服务端错误契约(lite/server/auth.py 的 err()):HTTP >= 400 时
JSON 为 {"detail": {"code": "...", "message": "...", ...}};成功无信封直接返回 JSON。
**403 分码**(HANDOFF §8):`READ_ONLY_TOKEN` = 只读令牌发起写操作,`JOIN_REQUIRED` =
公开项目未加入,其余权限不足是 `FORBIDDEN`。判分支一律看 code,不看 message 文案。
409 `CONFLICT`(文档正文基线不匹配)会在同一个 detail 里附现场数据
`currentVersion` / `currentContent` / `by` —— 它们随 ApiError.detail 一路带到错误出口。
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

import httpx

from .config import resolve

CHUNK = 1024 * 1024


@dataclass
class ApiError(Exception):
    """服务端契约错误。detail 是原始 detail 字典:code/message 之外还可能有现场数据
    (目前只有 409 冲突;见模块 docstring),错误出口据此多给一句人话。"""

    status: int
    code: str
    message: str = field(default="")
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__init__(f"[{self.code}] {self.message}")

    @property
    def needs_write_scope(self) -> bool:
        return self.status == 403 and self.code == "READ_ONLY_TOKEN"


def api_error(resp: httpx.Response) -> ApiError:
    """由响应构造 ApiError(全项目唯一出口:request / stream 两条路径共用)。"""
    code, message, detail = parse_error(resp)
    return ApiError(resp.status_code, code, message, detail)


def raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise api_error(resp)


class Client:
    def __init__(self, timeout: float = 60.0):
        self.server, self.token = resolve()
        self.http = httpx.Client(
            base_url=self.server,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    # ---- 基础请求 ----

    def request(self, method: str, path: str, *, params=None, json_body=None,
                content=None, headers=None) -> httpx.Response:
        try:
            resp = self.http.request(method, path, params=params, json=json_body,
                                     content=content, headers=headers)
        except httpx.HTTPError as e:
            raise ApiError(0, "NETWORK", f"无法连接 {self.server}:{e}") from e
        raise_for_status(resp)
        return resp

    def json(self, method: str, path: str, **kw):
        return self.request(method, path, **kw).json()

    @contextmanager
    def stream(self, method: str, path: str, **kw) -> Iterator[httpx.Response]:
        """流式响应(下载/取响应头):**与 request 同一个错误出口**,调用方不必自己解析错误。

        逐字节搬的路径尤其不能把异常留给 httpx 裸抛:那会让人看到 traceback 而不是
        服务端的 code/message。
        """
        with self.http.stream(method, path, **kw) as resp:
            raise_for_status(resp)
            yield resp

    # ---- 流式上传(raw body;带 Content-Length 让服务端能做空间预检) ----

    def upload(self, path: str, params: dict, file_path: str) -> dict:
        size = os.path.getsize(file_path)

        def gen():
            with open(file_path, "rb") as f:
                while chunk := f.read(CHUNK):
                    yield chunk

        resp = self.request("POST", path, params=params, content=gen(),
                            headers={"Content-Length": str(size)})
        return resp.json()

    # ---- 流式下载 ----

    def download(self, path: str, out_path: str) -> None:
        with self.stream("GET", path) as resp:
            tmp = out_path + ".part"
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(CHUNK):
                    f.write(chunk)
        os.replace(tmp, out_path)


def parse_error(resp: httpx.Response) -> tuple[str, str, dict]:
    """(code, message, detail)。detail 原样带上 —— 409 冲突的现场数据不能在这里丢掉。"""
    try:
        detail = resp.json().get("detail")
        if isinstance(detail, dict):
            return (detail.get("code", "ERROR"), str(detail.get("message", ""))[:300],
                    {k: v for k, v in detail.items() if k not in ("code", "message")})
    except ValueError:
        pass
    return "ERROR", f"HTTP {resp.status_code}:{resp.text[:200]}", {}


def filename_from_disposition(header: str | None, fallback: str) -> str:
    """从 Content-Disposition 取文件名;服务端用 Starlette 默认格式,UTF-8 名走 filename*。"""
    if not header:
        return fallback
    m = re.search(r"filename\*=UTF-8''([^;]+)", header)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', header)
    return m.group(1) if m else fallback
