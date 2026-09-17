"""凭据:服务器地址与访问令牌。

存在 ~/.teamdoc/config.json;环境变量 TD_SERVER / TD_PAT 优先(CI / 脚本用)。
令牌等同密码,所以 posix 下把文件权限收到仅本人可读写。
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .errors import ConfigError

CONFIG_PATH = Path.home() / ".teamdoc" / "config.json"


def load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"配置文件损坏({CONFIG_PATH}):{e}") from e


def save(server: str, token: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"server": server.rstrip("/"), "token": token},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name == "posix":  # Windows 无此语义,靠目录权限
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)


def clear() -> bool:
    """删掉本地副本,返回此前是否存在(令牌本身的吊销只能去网页端)。"""
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        return True
    return False


def credentials() -> tuple[str, str]:
    """(server, token)。环境变量优先于配置文件;缺任一 → ConfigError。"""
    env_server = os.environ.get("TD_SERVER", "").rstrip("/")
    env_token = os.environ.get("TD_PAT", "")
    if env_server and env_token:
        return env_server, env_token
    data = load()
    server = env_server or data.get("server", "")
    token = env_token or data.get("token", "")
    if not server or not token:
        missing = [name for name, ok in (("服务器地址(td login 或环境变量 TD_SERVER)", server),
                                         ("访问令牌(td login 或环境变量 TD_PAT)", token)) if not ok]
        raise ConfigError("尚未配置:" + ";".join(missing))
    return server, token
