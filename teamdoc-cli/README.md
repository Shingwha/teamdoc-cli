# TeamDoc CLI(`td`)

TeamDoc 知识库(自部署)的命令行工具:令牌登录、项目、文档读写、云空间文件上传下载、全文搜索、API 透传。通过 PAT 调用服务端 REST API,**服务端零特殊改动**。

## 安装

本包随 ZCode skill 分发(skill 目录里的 `teamdoc-cli/` 就是本包):

```bash
uv tool install "<skill目录>/teamdoc-cli"             # 安装
uv tool install --reinstall "<skill目录>/teamdoc-cli" # skill 更新后升级
uv tool list                                          # 查看已装工具
```

要求:Python 3.12+(uv 会自动准备),依赖 typer + httpx(装进隔离环境)。

## 登录(一次性)

1. 浏览器打开 TeamDoc → 左侧边栏底部点开你的用户菜单 →「个人设置」→「访问令牌」→ 新建:
   - 作用域 **read,write**(只读令牌无法执行任何写命令)
   - 令牌明文**只显示一次**,立即保存
2. `td login` 按提示输入服务器地址与令牌;或一步到位:
   ```bash
   td login --server http://192.168.1.10:8000 --token tdp_xxxxxxxx
   ```

配置保存在 `~/.teamdoc/config.json`。脚本/CI 可不用配置文件,直接:

```bash
TD_SERVER=http://host:8000 TD_PAT=tdp_xxx td doc search 关键词
```

## 命令

| 命令 | 说明 |
|---|---|
| `td login` / `td logout` / `td whoami` | 登录 / 清除本地令牌 / 当前身份 |
| `td project ls [--all]` | 项目列表(管理员 `--all`) |
| `td doc ls <项目>` | 文档树(项目支持 ID 或名称) |
| `td doc show <文档ID> [-o 文件] [--meta]` | 读正文;`--meta` 只看元数据 |
| `td doc new <项目> <标题> [-f 路径\|-] [--parent ID]` | 建文档,可同时写正文 |
| `td doc edit <文档ID> [-f 路径\|-] [--append]` | 覆盖 / 追加正文 |
| `td doc rm <文档ID> [--yes]` | 删除(进回收站,可恢复) |
| `td doc search <关键词> [--type docs\|files]` | 全文搜索 |
| `td file ls <项目> [文件夹ID]` | 文件列表(自动翻页) |
| `td file up <项目> <本地路径> [--folder ID]` | 上传(raw body 流式) |
| `td file down <文件ID> [-o 路径]` | 下载 |
| `td recent [-n N]` | 我参与项目的最近动态 |
| `td api <METHOD> /api/... [-d JSON] [--raw]` | 任意接口透传(逃生舱) |

管道示例:

```bash
cat meeting.md | td doc new 我的项目 "周会纪要" -     # stdin 建文档
td doc show <id> -o local.md                          # 拉到本地改
td doc edit <id> -f local.md                          # 推回去
```

## 带附件的 Markdown 怎么导入

TeamDoc 的正文引用是功能性依赖(被引用徽标、删除警告都靠精确匹配 `/api/files/{id}/download`),本地相对引用(`![](./x.png)`)贴进去是死链。手动编排四步:

1. 扫描 md 里的本地相对引用(排除 http(s)、teamdoc://、/api/、mailto:、# 锚点);
2. 逐个上传并记录 ID:`td file up <项目> ./assets/a.png --json`;
3. 改写引用:图片 `![a](/api/files/{id}/download?inline=1)`,附件 `[a](/api/files/{id}/download)`;
4. 建文档并验证:`td doc new <项目> "标题" -` → `td file ls <项目>` 看附件"标记"列出现 **被引用**。

`--json` 输出原始 JSON 方便脚本改写;引用 `td doc search` 可查文档 ID(teamdoc:// 引用格式见 SKILL.md)。

## 通用约定

- `--json`:输出原始 JSON(供脚本 `jq` 解析);默认人类可读表格,时间是本地时区。
- 退出码:`0` 成功;`1` API 错误(stderr 输出 `API 错误 [CODE]: message`);`2` 未登录或配置缺失。
- 403 且提示含 write:令牌只有 read 权限,去网页端建 `read,write` 令牌重新 `td login`。

## 边界说明

- 令牌的**创建与吊销只能在网页端**(服务端设计),CLI 只负责使用。
- WebSocket 实时协同是 Cookie 会话专属,CLI 不涉及。
- `td logout` 只删本地副本,不吊销令牌本身。

## 测试

`tests/smoke_cli.py`:对临时服务(参照 `lite/tests/README.md` 起服务)跑全流程断言:

```bash
TEAMDOC_DATA_DIR=/tmp/td_test PORT=8123 uv run python main.py   # lite/server 下
# 另一个终端(已 uv sync 本包):
.venv/Scripts/python tests/smoke_cli.py
```
