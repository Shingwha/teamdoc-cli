# TeamDoc CLI(`td`)

自部署 TeamDoc 知识库的命令行工具:令牌登录、项目、文档读写、云空间文件、全文搜索与最近动态。
通过 PAT 调 REST API,**服务端零特殊改动**。完整用法与写正文的规范见上级目录的 `SKILL.md`。

## 安装

本包随 skill 分发(skill 目录里的 `teamdoc-cli/` 就是本包):

```bash
uv tool install "<skill目录>/teamdoc-cli"             # 安装
uv tool install --reinstall "<skill目录>/teamdoc-cli" # 改过源码后升级
```

要求 Python 3.12+,依赖 typer + httpx(装进隔离环境)。

## 登录(一次性)

网页 →「个人设置」→「访问令牌」→ 新建,作用域选 **read,write**(只读令牌做不了写操作),
令牌明文只显示一次:

```bash
td login --server http://192.168.1.10:8000 --token tdp_xxxxxxxx
TD_SERVER=http://host:8000 TD_PAT=tdp_xxx td search 关键词   # 脚本 / CI 可跳过配置文件
```

配置存 `~/.teamdoc/config.json`。

## 命令

| 命令 | 说明 |
|---|---|
| `td login` / `logout` / `whoami` | 登录、删本地令牌、当前身份与令牌权限 |
| `td project ls [--public\|--all]` / `show` / `join` / `leave` | 项目列表(我参加的 / 可加入的 / 全站)、详情、自助加入、退出 |
| `td doc ls` / `show` / `new` / `edit` / `mv` / `rm` | 文档树、读正文(`--meta` 只看元数据)、新建、写正文、移动、删除 |
| `td search <关键词>` / `td recent` | 全文搜索(文档 + 文件)/ 最近动态 |
| `td file ls` / `up` / `down` / `mkdir` / `rename` / `mv` / `share` / `unshare` / `rm` | 云空间:上传下载、文件夹、移动、分享链接、删除 |

完整参数:`td <组> --help`(如 `td file --help`)。通用约定:

- `--json` 输出原始 JSON 给脚本解析,默认是人话视图(表格按显示宽度对齐,时间是本地时区)。
- 项目参数给 **ID** 或**名称**(需唯一);云空间条目只给 ID,CLI 自己认文件还是文件夹。
- 正文只有一个来源通道:`--file 路径|-`,或裸管道 `cat x.md | td doc edit <id>`。
- `td doc edit --if-version N`:只在服务端仍是第 N 版时写入(否则报错、不改动)。
- 退出码:`0` 成功;`1` API 错误(stderr 打 `API 错误 [CODE]: message`);`2` 未登录或用法/输入错误。

管道示例:

```bash
cat 会议.md | td doc new 我的项目 "周会纪要" --file -   # 从 stdin 建文档
td doc show <id> -o local.md                            # 拉到本地改
td doc edit <id> --append --file 补记.md                 # 追加回去
```

## 测试

`tests/smoke_cli.py`:零依赖脚本,对运行中的临时服务跑全流程断言(登录、项目、文档、文件、
搜索、权限与退出码)。需要一台隔离实例:

```bash
cd lite/server && TEAMDOC_DATA_DIR=/tmp/td_test PORT=8123 uv run python main.py  # 终端 A
cd teamdoc-cli && .venv/Scripts/python tests/smoke_cli.py                        # 终端 B(本包 venv)
```
