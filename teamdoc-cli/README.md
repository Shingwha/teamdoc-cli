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
TD_SERVER=http://host:8000 TD_PAT=tdp_xxx td search 关键词
```

## 命令

三个资源组 + 顶层的身份三命令与跨资源能力(`search` / `recent` / `api`):

| 命令 | 说明 |
|---|---|
| `td login` / `td logout` / `td whoami` | 登录 / 清除本地令牌 / 当前身份 |
| `td project ls [--public\|--all]` | 我参加的项目 / 可加入的公开项目 / 全站(管理员) |
| `td project show <项目>` | 项目详情(可见性、我的角色、成员数与文档数) |
| `td project join <项目>` | 自助加入公开项目 |
| `td project leave <项目>` | 退出项目 |
| `td doc ls <项目>` | 文档树(项目支持 ID 或名称) |
| `td doc show <文档ID> [-o 文件] [--meta]` | 读正文;`--meta` 只看元数据 |
| `td doc new <项目> <标题> [--parent ID] [--file 路径\|-]` | 建文档,可同时写正文 |
| `td doc edit <文档ID> [--file 路径\|-] [--append]` | 覆盖 / 追加正文 |
| `td doc mv <文档ID> --to <项目> [--parent 父文档ID]` | 移动文档(项目内 / 跨项目) |
| `td doc rm <文档ID> [--yes]` | 删除(进回收站,可恢复) |
| `td search <关键词> [--type docs\|files]` | 全文搜索(文档 + 文件) |
| `td file ls <项目> [--folder 文件夹ID]` | 文件列表(自动翻页) |
| `td file up <项目> <本地路径> [--folder ID]` | 上传(raw body 流式) |
| `td file down <文件ID> [-o 路径]` | 下载 |
| `td file mkdir / rename / mv / rm` | 建文件夹 / 重命名 / 移动 / 删除(文件夹加 `--is-folder`) |
| `td file share / unshare <文件ID> [--expire 天数]` | 建立 / 吊销分享链接(无需登录即可下载) |
| `td recent [-n N]` | 我参与项目的最近动态 |

管道示例:

```bash
cat meeting.md | td doc new 我的项目 "周会纪要" --file -   # stdin 建文档
td doc show <id> -o local.md                               # 拉到本地改
td doc edit <id> -f local.md                               # 推回去
```

## 正文用什么 Markdown

CLI 只传原始文本,**不渲染也不校验** —— 渲染在 TeamDoc 网页端,完整规格见 TeamDoc 仓库的
`lite/MARKDOWN.md`。与标准 GFM 不同的几条(写错不会报错,只会显示成源码或纯文本):

| 写法 | 说明 |
|---|---|
| `$E=mc^2$` / `$$…$$` | 行内 / 显示公式(KaTeX)。**行内公式的 `$` 内侧不紧贴空白、闭 `$` 后不跟数字** —— `价格 $5 和 $6`、`US$5` 因此不会被误判成公式 |
| ` ```mermaid ` 围栏 | 流程图 / 时序图 / 类图 / 甘特 / 饼图 / 思维导图等(Mermaid 11);写错时显示"源码 + 错误原因" |
| `[^1]` + 文末 `[^1]: 说明` | 脚注(编号按引用先后) |
| `==高亮==` / `~下标~` / `^上标^` | 分隔符内侧不紧贴空白 |
| `<div>` `<details>` 等内联 HTML | **一律当文本转义**,写了不生效(安全立场) |
| `\(…\)` / `\[…\]` | 不支持,数学定界只认 `$` / `$$` |

表格对齐 `:---:`、任务列表 `- [ ]`、围栏代码块高亮、图片内嵌都与 GFM 一致。

## 带附件的 Markdown 怎么导入

TeamDoc 的正文引用是功能性依赖(被引用徽标、删除警告都靠精确匹配 `/api/files/{id}/download`),本地相对引用(`![](./x.png)`)贴进去是死链。手动编排四步:

1. 扫描 md 里的本地相对引用(排除 http(s)、teamdoc://、/api/、mailto:、# 锚点);
2. 逐个上传并记录 ID 与文件属性:`td file up <项目> ./assets/a.png --json`;
3. 改写引用,**能不能当图片内嵌看服务端返回的字段**(`mime` 以 `image/` 开头且 `canInline` 为真):
   图片写成 `![a](/api/files/{id}/download?inline=1)`,其余写成 `[a](/api/files/{id}/download)` ——
   别按本地扩展名猜,猜错就是正文里的裂图;
4. 建文档并验证:`td doc new <项目> "标题" --file -` → `td file ls <项目>` 看附件"标记"列出现 **被引用**
   (`可内嵌` 表示它能当图片写)。

`--json` 输出原始 JSON 方便脚本改写;引用 `td search` 可查文档 ID(teamdoc:// 引用格式见 SKILL.md)。

## 通用约定

- 命令结构 = 三个资源组(project / doc / file)+ 顶层的身份三命令与跨资源能力(search / recent / api):
  **跨资源的东西不进资源组**(`td search` 同时搜文档与文件,所以不叫 `td doc search`)。
- **同一件事只有一个入口**:正文只有一个来源通道(`--file 路径|-`,或裸管道 `cat x.md | td doc edit <id>`);
  项目内定位一律用选项(`--parent` / `--folder`),不用位置参数。
- `--json`:输出原始 JSON(供脚本 `jq` 解析);默认人类可读表格,时间是本地时区。
- 退出码:`0` 成功;`1` API 错误(stderr 输出 `API 错误 [CODE]: message`);`2` 未登录或配置缺失。
- 错误分支按**服务端的 code 判**,不嗅探文案:403 `READ_ONLY_TOKEN` = 令牌只有 read 权限(CLI 会提示去建
  `read,write` 令牌),403 `JOIN_REQUIRED` = 公开项目还没加入,409 `CONFLICT` = 正文基线不匹配
  (服务端会随错误回 `currentVersion`/`by`,CLI 打印出来)。
- 公开项目**加入前看不到任何内容**(搜索也搜不到):`td project ls --public` 找、`td project join` 加入;
  加入后的角色由项目设置决定,`td project leave` 退出。
- 被拒时 CLI 会补"下一句":未加入的公开项目提示 `td project join`,找不到名字时提示 `td project ls --public`。

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
