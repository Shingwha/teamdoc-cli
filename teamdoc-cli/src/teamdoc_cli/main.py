"""typer 应用与子命令注册。console script 入口:teamdoc_cli.main:app。"""

from __future__ import annotations

import typer

from .commands import api as api_mod
from .commands import auth as auth_mod
from .commands import doc as doc_mod
from .commands import file as file_mod
from .commands import project as project_mod
from .commands import recent as recent_mod
from .commands import search as search_mod
from .output import ensure_utf8

ensure_utf8()

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="TeamDoc 知识库命令行工具(PAT 认证;td login 后使用;td api 可透传任意接口)",
)

app.add_typer(project_mod.app, name="project", help="项目")
app.add_typer(doc_mod.app, name="doc", help="文档")
app.add_typer(file_mod.app, name="file", help="云空间文件")

# 顶层:身份三命令与跨资源能力(search / recent 同时涉及文档与文件;api 是逃生舱)。
# 刻意**不再**另挂一个 auth 组 —— 同一份函数注册两遍会让 help 面出现两套名字指同一件事
app.command()(auth_mod.login)
app.command()(auth_mod.logout)
app.command()(auth_mod.whoami)
app.command()(search_mod.search)
app.command()(recent_mod.recent)
app.command()(api_mod.api)


if __name__ == "__main__":
    app()
