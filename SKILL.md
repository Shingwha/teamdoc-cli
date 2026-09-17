---
name: teamdoc
description: TeamDoc 知识库命令行工具(td)。安装或升级 td、用命令行操作知识库(令牌登录、项目列表/详情/自助加入与退出、文档创建/读取/编辑/移动/删除/搜索、云空间文件上传下载分享移动、最近动态)时使用。涉及 td 命令、TeamDoc CLI、知识库终端操作时触发。
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
td doc mv <文档ID> --to <项目ID|名称> [--parent 父文档ID]   # 移动(项目内/跨项目)
td doc rm <文档ID> [--yes]                  # 删除(进回收站)
td search <关键词> [--type docs|files]      # 全文搜索(文档 + 文件,跨项目)
td file ls <项目ID> [--folder 文件夹ID]      # 文件列表(自动翻页)
td file up <项目ID> <本地路径> [--folder ID]  # 上传(raw body 流式)
td file down <文件ID> [-o 输出路径]         # 下载
td file mkdir <项目ID> <名称> [--folder 父夹ID]             # 建文件夹
td file rename <文件ID> <新名> [--is-folder]                # 重命名
td file mv <文件ID> --to <项目ID> [--folder 目标夹ID] [--is-folder]  # 移动(项目内/跨项目)
td file share <文件ID> [--expire 天数]      # 建立分享链接(无需登录即可下载)
td file unshare <文件ID>                   # 吊销分享链接
td file rm <文件ID> [--is-folder] [--permanent] [--yes]     # 删除(默认进回收站)
td recent [--limit N]                       # 我参与项目的最近动态
```

命令结构:三个资源组(project / doc / file)+ 顶层的身份三命令与**跨资源**能力(search / recent;
search 同时搜文档与文件,所以不挂在 `td doc` 下)。
通用:`--json` 输出原始 JSON 供脚本解析;正文只有一个来源通道 —— `--file 路径|-`,或裸管道
(`cat xx.md | td doc edit <id>`)。
项目参数既可给 **ID**(`td project ls` 打印的那串字符,原样回填即可)也可给**名称**(需唯一);项目内定位一律用选项
(`--parent` / `--folder`)。**文件与文件夹是两套独立编号**,对文件夹操作要加 `--is-folder`(走错表会提示)。
**公开项目加入前看不到任何内容**(搜索也搜不到):`td project ls --public` 找、`td project join` 加入,
加入后的角色由项目设置决定(只读成员 / 编辑者)。
`td file rm` 默认软删(项目回收站可恢复);`--permanent` 只对回收站中的条目有效且不可恢复。跨项目移动需要**源项目 ADMIN** + 目标项目 EDITOR。`td doc mv` 跨项目时只搬文档,**不会带走附件**(正文引用的文件留在原项目),命令会先打印「哪些文件会留下」再让你确认。
退出码:0 成功;1 API 错误(stderr 输出 `API 错误 [CODE]: message`);2 未登录/配置缺失。
注意:用户无关的 WS 协同不走 CLI;令牌丢失只能回网页端重新创建。

## 文档引用格式规范(写入正文前必读)

TeamDoc 的引用是**功能性依赖**——服务端在正文里精确匹配这些链接来判定"被引用"与反向链接(云空间的被引用徽标、删除警告、文档反链都靠它)。引用里只出现资源自己的 ID,不含项目。往文档里写 Markdown 时必须用以下格式,**不要保留本地相对引用**(`![](./assets/x.png)` 之类在 TeamDoc 里是死链):

| 引用什么 | 格式 |
|---|---|
| 图片(站内显示) | `![名称](/api/files/{文件ID}/download?inline=1)` |
| 附件(点击下载) | `[名称](/api/files/{文件ID}/download)` |
| 引用另一篇文档 | `[@标题](teamdoc://doc/{文档ID})` |
| 引用另一个文件 | `[@名称](teamdoc://file/{文件ID})` |

用 `td file up --json` 拿文件 ID;`td search` 查文档 ID。外部 http(s) 链接保持原样即可。

## 正文支持的 Markdown(写入前必读)

渲染只发生在 TeamDoc 网页端(CLI 只传原文,**不渲染也不校验**)。完整规格见 TeamDoc 仓库的
`lite/MARKDOWN.md`;与"标准 GFM"不同的就下面几条,**写错不会报错,只会显示成源码或纯文本**:

| 写法 | 结果 / 注意 |
|---|---|
| `$E=mc^2$`、`$$…$$` | 行内 / 显示公式(KaTeX)。**行内公式的 `$` 内侧不紧贴空白、闭 `$` 后不跟数字**,否则整段按普通文本显示 —— `价格 $5 和 $6 之间`、`US$5` 就是靠这条不被当成公式 |
| ` ```mermaid ` 围栏 | 流程图 / 时序图 / 类图 / 状态图 / ER / 甘特 / 饼图 / 思维导图等(Mermaid 11)。语法写错时页面上是"源码 + 错误原因",正文不受影响 |
| `[^1]` + 文末 `[^1]: 说明` | 脚注;编号按**引用**出现的先后,定义可跨行(续行缩进两格) |
| `==高亮==`、`~下标~`、`^上标^` | 分隔符内侧不紧贴空白(所以 `a == b`、`3 ~ 5` 不受影响) |
| 表格(含 `:---:` 对齐)、`- [ ]` 任务列表、围栏代码块 | 标准 GFM,原样可用 |
| `<div>` `<details>` `<br>` 等**内联 HTML** | **一律当文本转义**(安全立场),写了不生效 —— 要块级能力用上面的扩展语法 |
| `\(…\)`、`\[…\]` | 不支持:数学定界只认 `$…$` 与 `$$…$$` |

图表与公式是**按需加载**的:正文里出现 ` ```mermaid ` 围栏 / 公式时,网页端才会去取对应的库,
没有的文档不受影响。图表里的文字不进全文搜索(搜索只搜 Markdown 原文)。

## 带附件的 Markdown 导入(编排手册)

外部 Markdown 常带本地相对引用(`![](./assets/a.png)`)。导入流程 = 逐个上传附件 → 改写引用 → 建文档,一步都不要省:

1. **扫描**:读 md,列出所有本地相对引用(`![]()` 与 `[]()` 的目标);排除 `http(s)://`、`teamdoc://`、`/api/`、`mailto:`、`#` 锚点。本地文件不存在的引用:警告并保留原样。
2. **上传**:对每个存在的文件 `td file up <项目> <路径> --json` → 记下返回的 `id`、`mime`、`canInline`、`name`。
3. **改写**:判"能不能当图片内嵌"用**服务端返回的字段** —— `mime` 以 `image/` 开头 **且** `canInline` 为真 → `![alt](/api/files/{id}/download?inline=1)`,否则 → `[文字](/api/files/{id}/download)`。别按本地扩展名猜(`canInline` 是服务端的 inline 白名单,猜错就是正文里的裂图)。同目录重名上传会自动加后缀 `(2)`,以返回的 `name` 为准。
4. **建文档**:`td doc new <项目> <标题> --file -`,改写后的正文从 stdin 灌入;追加到既有文档用 `td doc edit <id> --append`。
5. **验证**:`td file ls <项目>` 确认每个附件的"标记"列出现 **被引用**(`可内嵌` 则说明它能当图片写);`td doc show <id>` 抽查图片链接格式。

若正文里有公式或图表,顺手按上一节核对写法(行内 `$…$` 内侧不贴空白、` ```mermaid ` 围栏),
这两处写错的典型症状是"页面上原样显示源码"。

多篇文档共享同一批附件时,附件只传一次,复用同一个文件 ID 即可。
