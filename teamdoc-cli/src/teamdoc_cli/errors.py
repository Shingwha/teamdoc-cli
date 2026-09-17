"""失败分类与退出码。

退出码(全站一致,命令层不自定义):
    0  成功
    1  服务端拒绝(ApiError),或本地文件读写失败(OSError)
    2  用错了 / 环境没准备好(ConfigError 未登录或配置损坏,InputError 正文来源不可用)

"哪里抛"与"翻成几号退出码"各只有一处(cli.guarded),命令体里因此没有任何 try/except。
"""

from __future__ import annotations

from dataclasses import dataclass, field

EXIT_OK = 0
EXIT_API = 1     # 服务端拒绝 / 本地 I/O 失败
EXIT_USAGE = 2   # 未登录 / 输入不可用


class ConfigError(Exception):
    """凭据缺失或损坏:没登录、配置文件读不了、环境变量只给了一半。"""


class InputError(Exception):
    """本地输入不可用:--file 路径读不到,或该给正文时既没给文件也没有管道。"""


@dataclass
class ApiError(Exception):
    """服务端契约错误。

    detail 是响应里的原始 detail 字典:code 与 message 之外还可能有现场数据 ——
    目前只有 409 CONFLICT(文档正文基线不匹配)会附 currentVersion / currentContent / by,
    错误出口据此多给一句人话。
    status 为 0 表示连不上服务端,没有 HTTP 状态码可言。
    """

    status: int
    code: str
    message: str = ""
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(f"[{self.code}] {self.message}")

    @property
    def needs_write_scope(self) -> bool:
        """403 分码:只读令牌发起了写操作(判 code,不嗅 message 文案)。"""
        return self.status == 403 and self.code == "READ_ONLY_TOKEN"
