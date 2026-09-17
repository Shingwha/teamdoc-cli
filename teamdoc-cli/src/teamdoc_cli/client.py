"""HTTP 客户端:Bearer 注入、错误构造、流式上传与流式响应。

服务端错误契约:HTTP >= 400 时响应体是 {"detail": {"code": ..., "message": ..., ...}},
成功则直接返回 JSON,没有信封。判分支一律看 code,不嗅 message 文案:
    READ_ONLY_TOKEN  403,只读令牌发起写操作 —— 出路是换一个 read,write 令牌
    JOIN_REQUIRED    403,公开项目还没加入 —— 出路是 td project join
    CONFLICT         409,文档正文基线不匹配 —— detail 里带现场数据(见下)
    NOT_FOUND        404,不存在,或存在但对调用方不可见(两种情况不区分)
409 的 currentVersion / currentContent / by 原样装进 ApiError.detail,一路带到错误出口。
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import unquote

import httpx

from . import config
from .errors import ApiError

CHUNK = 1024 * 1024
TIMEOUT = 60.0


class Client:
    """一条命令通常只建一个。凭据缺省读配置文件,也可以显式传入(登录时验证令牌用)。"""

    def __init__(self, server: str | None = None, token: str | None = None,
                 timeout: float = TIMEOUT):
        if server is None or token is None:
            server, token = config.credentials()
        self.server = server.rstrip("/")
        self.token = token
        self.http = httpx.Client(base_url=self.server, timeout=timeout,
                                 headers={"Authorization": f"Bearer {token}"})

    def request(self, method: str, path: str, *, params: dict | None = None,
                json_body=None, content=None, headers: dict | None = None) -> httpx.Response:
        try:
            resp = self.http.request(method, path, params=params, json=json_body,
                                     content=content, headers=headers)
        except httpx.HTTPError as e:
            raise ApiError(0, "NETWORK", f"无法连接 {self.server}:{e}") from e
        if resp.status_code >= 400:
            raise error_from(resp)
        return resp

    def json(self, method: str, path: str, **kw) -> dict | list:
        return self.request(method, path, **kw).json()

    @contextmanager
    def stream(self, method: str, path: str, **kw) -> Iterator[httpx.Response]:
        """流式响应(下载文件、只取响应头)。

        **与 request 同一个错误出口**:错误体先读完再解析,否则调用方看到的是 httpx 的
        ResponseNotRead 裸异常,而不是服务端的 code/message。
        """
        with self.http.stream(method, path, **kw) as resp:
            if resp.status_code >= 400:
                resp.read()
                raise error_from(resp)
            yield resp

    def upload(self, path: str, params: dict, file_path: str) -> dict:
        """raw body 直传(文件字节就是请求体),带 Content-Length 让服务端先做空间预检。"""
        def chunks():
            with open(file_path, "rb") as f:
                while chunk := f.read(CHUNK):
                    yield chunk

        resp = self.request("POST", path, params=params, content=chunks(),
                            headers={"Content-Length": str(os.path.getsize(file_path))})
        return resp.json()


def error_from(resp: httpx.Response) -> ApiError:
    """响应 → ApiError(全项目唯一的构造点)。解析不了信封时退回状态码 + 响应文本片段。"""
    try:
        detail = resp.json().get("detail")
        if isinstance(detail, dict):
            return ApiError(resp.status_code, detail.get("code", "ERROR"),
                            str(detail.get("message", ""))[:300],
                            {k: v for k, v in detail.items() if k not in ("code", "message")})
    except ValueError:
        pass
    return ApiError(resp.status_code, "ERROR", f"HTTP {resp.status_code}:{resp.text[:200]}")


def filename_from_disposition(header: str | None, fallback: str) -> str:
    """从 Content-Disposition 取文件名(服务端用 Starlette 默认格式,中文名走 filename*)。"""
    if not header:
        return fallback
    m = re.search(r"filename\*=UTF-8''([^;]+)", header)
    if m:
        return unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', header)
    return m.group(1) if m else fallback
