"""httpx 客户端:Bearer 注入、服务端错误解析、流式上传/下载。

服务端错误契约(lite/server/auth.py err()):HTTP >= 400 时
JSON 为 {"detail": {"code": "...", "message": "..."}};成功无信封直接返回 JSON。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx

from .config import resolve

CHUNK = 1024 * 1024


@dataclass
class ApiError(Exception):
    status: int
    code: str
    message: str = field(default="")

    def __post_init__(self):
        super().__init__(f"[{self.code}] {self.message}")

    @property
    def needs_write_scope(self) -> bool:
        # 两种来源:令牌作用域不足(require_write 的 403),或项目角色不够
        return self.status == 403 and "write" in self.message.lower()


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
        if resp.status_code >= 400:
            code, message = parse_error(resp)
            raise ApiError(resp.status_code, code, message)
        return resp

    def json(self, method: str, path: str, **kw):
        return self.request(method, path, **kw).json()

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
        with self.http.stream("GET", path) as resp:
            if resp.status_code >= 400:
                code, message = parse_error(resp)
                raise ApiError(resp.status_code, code, message)
            tmp = out_path + ".part"
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(CHUNK):
                    f.write(chunk)
        os.replace(tmp, out_path)


def parse_error(resp: httpx.Response) -> tuple[str, str]:
    try:
        detail = resp.json().get("detail")
        if isinstance(detail, dict):
            return detail.get("code", "ERROR"), str(detail.get("message", ""))[:300]
    except ValueError:
        pass
    return "ERROR", f"HTTP {resp.status_code}:{resp.text[:200]}"


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
