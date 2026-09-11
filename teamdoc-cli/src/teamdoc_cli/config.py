"""配置管理:~/.teamdoc/config.json,环境变量 TD_SERVER / TD_PAT 优先(CI/脚本用)。"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

CONFIG_PATH = Path.home() / ".teamdoc" / "config.json"


class ConfigError(Exception):
    """配置缺失或损坏 → CLI 退出码 2。"""


def load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"配置文件损坏({CONFIG_PATH}):{e}") from e


def save(server: str, token: str, account: dict | None = None) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"server": server.rstrip("/"), "token": token}
    if account:
        data["account"] = account
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name == "posix":  # 令牌等同密码:仅本人可读写(Windows 无此语义,靠目录权限)
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)


def clear() -> bool:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        return True
    return False


def resolve() -> tuple[str, str]:
    """返回 (server, token)。环境变量优先于配置文件;缺任一 → ConfigError。"""
    env_server = os.environ.get("TD_SERVER", "").rstrip("/")
    env_token = os.environ.get("TD_PAT", "")
    if env_server and env_token:
        return env_server, env_token
    data = load()
    server = env_server or data.get("server", "")
    token = env_token or data.get("token", "")
    if not server or not token:
        missing = []
        if not server:
            missing.append("服务器地址(td login 或环境变量 TD_SERVER)")
        if not token:
            missing.append("访问令牌(td login 或环境变量 TD_PAT)")
        raise ConfigError("尚未配置:" + ";".join(missing))
    return server, token
