---
name: teamdoc
description: TeamDoc 知识库命令行工具(td)。安装或升级 td、用命令行操作知识库(令牌登录、项目列表/详情/自助加入与退出、文档创建/读取/编辑/删除/搜索、云空间文件上传下载、最近动态、API 透传)时使用。涉及 td 命令、TeamDoc CLI、知识库终端操作时触发。
---

# TeamDoc CLI(td)

TeamDoc 知识库(自部署)的命令行工具,通过 PAT(访问令牌)调用服务端 REST API。

## 安装 / 升级

td 源码就在本 skill 文件夹的 `teamdoc-cli/` 里(skill 加载时给定的 base directory 即本目录),用 uv 安装为全局工具:

1. 先探测是否已安装:`td --help`(或 `uv tool list` 找 teamdoc-cli)。
2. 未安装则:`uv tool install "<base>/teamdoc-cli"`(Windows 注意给路径加引号)。
3. skill 内代码更新后,升级用:`uv tool install --reinstall "<base>/teamdoc-cli"`(**装的是源码快照**:改完 `src/` 不 reinstall,`td` 跑的还是旧代码)。

## 登录(一次性)

1. 浏览器打开 TeamDoc → 左侧边栏底部点开你的用户菜单 →「个人设置」→「访问令牌」→ 新建,作用域选 **read,write**(只读令牌无法执行任何写命令),令牌明文只显示一次。
2. `td login`,按提示输入服务器地址(如 `http://192.168.x.x:8000`)和令牌。配置存在 `~/.teamdoc/config.json`。
3. 脚本/CI 可跳过配置文件:环境变量 `TD_SERVER` + `TD_PAT`。

## 命令速查

```
td login [--server URL] [--token tdp_...]   # 登录(验证并保存)
td whoami                                   # 当前身份与令牌权限
td logout                                   # 删除本地令牌(吊销去网页端)
td project ls [--public|--all]              # 我参加的项目 / 可加入的公开项目 / 全站(管理员)
td project show <项目ID|名称>                # 项目详情(可见性 / 我的角色 / 规模)
td project join <项目ID|名称>                # 自助加入公开项目
td project leave <项目ID|名称>               # 退出项目
td doc ls <项目ID>                          # 文档树
td doc show <文档ID> [-o 文件] [--meta]     # 读正文(stdout/文件)
td doc new <项目ID> <标题> [--parent ID] [--file 路径|-]   # 建文档,可带正文
td doc edit <文档ID> [--file 路径|-] [--append]            # 覆盖/追加正文
td doc rm <文档ID> [--yes]                  # 删除(进回收站)
td search <关键词> [--type docs|files]      # 全文搜索(文档 + 文件,跨项目)
td file ls <项目ID> [--folder 文件夹ID]      # 文件列表(自动翻页)
td file up <项目ID> <本地路径> [--folder ID]  # 上传(raw body 流式)
td file down <文件ID> [-o 输出路径]         # 下载
td file mkdir <项目ID> <名称> [--folder 父夹ID]             # 建文件夹
td file rename <文件ID> <新名> [--is-folder]                # 重命名
td file mv <文件ID> --to <项目ID> [--folder 目标夹ID] [--is-folder]  # 移动(项目内/跨项目)
td file rm <文件ID> [--is-folder] [--permanent] [--yes]     # 删除(默认进回收站)
td recent [--limit N]                       # 我参与项目的最近动态
td api GET /api/... [--data JSON] [--raw]   # 任意接口透传(逃生舱)
```

命令结构:三个资源组(project / doc / file)+ 顶层的身份三命令与**跨资源**能力(search / recent / api;
search 同时搜文档与文件,所以不挂在 `td doc` 下)。
通用:`--json` 输出原始 JSON 供脚本解析;正文只有一个来源通道 —— `--file 路径|-`,或裸管道
(`cat xx.md | td doc edit <id>`)。
项目参数既可给 **ID**(`td project ls` 打印的数字,原样回填即可)也可给**名称**(需唯一);项目内定位一律用选项
(`--parent` / `--folder`)。**文件与文件夹是两套独立编号**,对文件夹操作要加 `--is-folder`(走错表会提示)。
**公开项目加入前看不到任何内容**(搜索也搜不到):`td project ls --public` 找、`td project join` 加入,
加入后的角色由项目设置决定(只读成员 / 编辑者)。
`td file rm` 默认软删(项目回收站可恢复);`--permanent` 只对回收站中的条目有效且不可恢复。跨项目移动需要**源项目 ADMIN** + 目标项目 EDITOR。
退出码:0 成功;1 API 错误(stderr 输出 `API 错误 [CODE]: message`);2 未登录/配置缺失。
注意:用户无关的 WS 协同不走 CLI;令牌丢失只能回网页端重新创建。

## Windows / Git Bash 注意

Git Bash(MSYS)会把**以 `/` 开头**的参数当成 POSIX 路径改写好再生效:`td api GET /api/projects` 实际拿到的是 `C:/Program Files/Git/api/projects`,于是报"路径必须以 `/` 开头"(报错里会直接点明这一点)。三种解法任选:

- 加环境变量前缀(**推荐,只作用于这一条命令**):`MSYS_NO_PATHCONV=1 td api GET /api/projects`
- 改用 PowerShell / CMD(不做这类改写)
- MSYS2 官方变量:`MSYS2_ARG_CONV_EXCL='*'`

两个反例:**不要**用 `//api/projects` 双斜杠"绕过"——参数确实不被改写,但请求路径变成 `//api/...`,服务端回 404;**也不要**把 `MSYS_NO_PATHCONV=1` 导出到整个会话——`td file up <路径>`、`td doc new --file <路径>` 这些本地路径参数正是靠这层转换才能用,关掉会变成"文件不存在"。其它子命令不受影响(它们的参数是 ID / 名称 / flag,不是 URL 路径)。

## 文档引用格式规范(写入正文前必读)

TeamDoc 的引用是**功能性依赖**——服务端在正文里精确匹配 `/api/files/{id}/download` 来判定"被引用"(云空间的被引用徽标、删除警告都靠它)。往文档里写 Markdown 时必须用以下格式,**不要保留本地相对引用**(`![](./assets/x.png)` 之类在 TeamDoc 里是死链):

| 引用什么 | 格式 |
|---|---|
| 图片(站内显示) | `![名称](/api/files/{文件ID}/download?inline=1)` |
| 附件(点击下载) | `[名称](/api/files/{文件ID}/download)` |
| 引用另一篇文档 | `[@标题](teamdoc://doc/{项目ID}/{文档ID})` |
| 引用另一个文件 | `[@名称](teamdoc://file/{文件ID})` |

用 `td file up --json` 拿文件 ID;`td search` 查文档 ID。外部 http(s) 链接保持原样即可。

## 带附件的 Markdown 导入(编排手册)

外部 Markdown 常带本地相对引用(`![](./assets/a.png)`)。导入流程 = 逐个上传附件 → 改写引用 → 建文档,一步都不要省:

1. **扫描**:读 md,列出所有本地相对引用(`![]()` 与 `[]()` 的目标);排除 `http(s)://`、`teamdoc://`、`/api/`、`mailto:`、`#` 锚点。本地文件不存在的引用:警告并保留原样。
2. **上传**:对每个存在的文件 `td file up <项目> <路径> --json` → 记下返回的 `id`。
3. **改写**:图片(扩展名/mime 为图片)→ `![alt](/api/files/{id}/download?inline=1)`;其余 → `[文字](/api/files/{id}/download)`。同目录重名上传会自动加后缀 `(2)`,以返回的 `name` 为准。
4. **建文档**:`td doc new <项目> <标题> --file -`,改写后的正文从 stdin 灌入;追加到既有文档用 `td doc edit <id> --append`。
5. **验证**:`td file ls <项目>` 确认每个附件的"标记"列出现 **被引用**;`td doc show <id>` 抽查图片链接格式。

多篇文档共享同一批附件时,附件只传一次,复用同一个文件 ID 即可。
