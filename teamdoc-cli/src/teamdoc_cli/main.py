"""typer 应用与命令注册(入口:console script `td` 或 `python -m teamdoc_cli`)。

命令结构 = 三个资源组(project / doc / file)+ 顶层的身份命令与跨资源能力。
组是**资源域**,身份与跨资源能力都不属于某个资源组,所以挂顶层 ——
search 与 recent 同时涉及文档与文件,挂进 `td doc` 就是错的。
"""

from __future__ import annotations

import typer

from .commands import auth, doc, file, project, search
from .console import ensure_utf8

ensure_utf8()

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="TeamDoc 知识库命令行工具(PAT 认证;td login 后使用)",
)

app.add_typer(project.app, name="project", help="项目")
app.add_typer(doc.app, name="doc", help="文档")
app.add_typer(file.app, name="file", help="云空间文件")

app.command()(auth.login)
app.command()(auth.logout)
app.command()(auth.whoami)
app.command()(search.search)
app.command()(search.recent)


if __name__ == "__main__":
    app()
