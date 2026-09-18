---
name: teamdoc
description: TeamDoc 知识库命令行工具(td)。安装或升级 td、用命令行操作知识库(令牌登录、项目列表/详情/自助加入与退出、文档创建/读取/编辑/移动/删除/搜索、云空间文件上传下载分享移动、最近动态)时使用。涉及 td 命令、TeamDoc CLI、知识库终端操作时触发。
---

# TeamDoc CLI(td)

自部署 TeamDoc 知识库的命令行工具,用 PAT(访问令牌)调 REST API。源码就在本 skill 的
`teamdoc-cli/`(skill 加载时给的 base directory 即本目录),改完源码要重装才生效。

## 安装 / 升级

```bash
td --help                                         # 先探测是否已装(或 uv tool list)
uv tool install "<base>/teamdoc-cli"              # 安装(Windows 给路径加引号)
uv tool install --reinstall "<base>/teamdoc-cli"  # 改过 src/ 之后:装的是源码快照,不重装跑的还是旧代码
```

## 登录(一次性)

1. 网页 → 左下角用户菜单 →「个人设置」→「访问令牌」→ 新建,作用域选 **read,write**
   (只读令牌做不了任何写操作),令牌明文只显示一次。
2. `td login`,按提示输入服务器地址(如 `http://192.168.1.10:8000`)与令牌;配置存 `~/.teamdoc/config.json`。
3. 脚本 / CI 可跳过配置:`TD_SERVER=http://host:8000 TD_PAT=tdp_xxx td project ls`。

## 命令

```
td login [--server URL] [--token tdp_...]   td whoami   td logout
td project ls [--public|--all]              td project show <项目>
td project join <项目>                      td project leave <项目>
td doc ls <项目>                            td doc show <文档ID> [-o 文件] [--meta]
td doc new <项目> <标题> [--parent 父文档ID] [--file 路径|-]
td doc edit <文档ID> [--file 路径|-] [--append] [--if-version N]
td doc mv <文档ID> --to <项目> [--parent 父文档ID]     td doc rm <文档ID> [-y]
td search <关键词> [--type docs|files]      td recent [-n 条数]
td file ls <项目> [--folder 文件夹ID]        td file up <项目> <本地路径> [--folder ID]
td file down <文件ID> [-o 路径]             td file mkdir <项目> <名称> [--folder 父夹ID]
td file rename <文件或文件夹ID> <新名>       td file mv <条目ID> --to <项目> [--folder 目标夹ID]
td file share <文件ID> [--expire 天数]      td file unshare <文件ID>
td file rm <文件或文件夹ID> [--permanent] [-y]
```

- 结构 = 三个资源组(project / doc / file)+ 顶层的身份命令与**跨资源**能力(search / recent 同时涉及
  文档与文件)。`td <组> --help` 有完整参数说明。
- `--json` 输出原始 JSON 给脚本解析;human 视图里表格按显示宽度对齐。
- 正文只有一个来源通道:`--file 路径|-`,或裸管道(`cat x.md | td doc edit <id>`)。
- 项目参数给 **ID** 或**名称**(需唯一);云空间条目只给 ID,CLI 自己认文件还是文件夹。
- 退出码:0 成功;1 API 错误(stderr 打 `API 错误 [CODE]: message`);2 未登录 / 用法或输入错误。
  分支一律按服务端的 **code** 判,别嗅探 message 文案:403 `READ_ONLY_TOKEN`(令牌只读)、
  403 `JOIN_REQUIRED`(公开项目未加入)、409 `CONFLICT`(正文基线不匹配)。
- `--if-version N` = 只在服务端仍是第 N 版时写入,否则报错且不改动(脚本做读-改-写时防覆盖别人);
  `--append` 不接受它(追加本身是读-改-写,没有基线可言)。
- `td file rm` 默认软删(项目回收站可恢复),`--permanent` 只对回收站中的条目有效;
  跨项目移动需要**源项目 ADMIN** + **目标项目 EDITOR**。

## 写正文前必读:引用格式

引用是**功能性依赖** —— 服务端在正文里精确匹配这些链接来判定"被引用"与反向链接(云空间的被引用徽标、
删除警告、文档反链都靠它)。引用里只出现资源自己的 ID,不含项目。往正文里写 Markdown 时必须用下面四种,
**不要保留本地相对引用**(`![](./assets/x.png)` 在 TeamDoc 里是死链):

| 引用什么 | 格式 |
|---|---|
| 图片(站内显示) | `![名称](/api/files/{文件ID}/download?inline=1)` |
| 附件(点击下载) | `[名称](/api/files/{文件ID}/download)` |
| 引用另一篇文档 | `[@标题](teamdoc://doc/{文档ID})` |
| 引用另一个文件 | `[@名称](teamdoc://file/{文件ID})` |

文件 ID 用 `td file up --json` 拿,文档 ID 用 `td doc ls` / `td search` 查。外部 http(s) 链接原样保留。

## 写正文前必读:Markdown 差异

渲染只发生在网页端(CLI 只传原文,**不渲染也不校验**);完整规格见 TeamDoc 仓库的 `lite/MARKDOWN.md`。
与标准 GFM 不同的就下面几条,**写错不报错,只显示成源码或纯文本**:

| 写法 | 结果 / 注意 |
|---|---|
| `$E=mc^2$`、`\(E=mc^2\)` | 行内公式(KaTeX),两种定界符等价。**内侧不紧贴空白、闭定界符后不跟数字**,否则按原样显示(`价格 $5 和 $6`、`US$5` 靠这条不被当成公式) |
| `$$…$$`、`\[…\]` | 显示公式。独占一行(开闭各自成行,或整条自占一行);`\[…\]` **只认独占一行**,段中的不认 |
| ` ```mermaid ` 围栏 | 流程图 / 时序图 / 类图 / 状态图 / ER / 甘特 / 饼图 / 思维导图(Mermaid 11)。语法写错时页面上是"源码 + 错误原因",正文不受影响 |
| `[^1]` + 文末 `[^1]: 说明` | 脚注;编号按**引用**出现的先后,定义可跨行(续行缩进两格) |
| `==高亮==`、`~下标~`、`^上标^` | 分隔符内侧不紧贴空白(所以 `a == b`、`3 ~ 5` 不受影响) |
| 表格(含 `:---:` 对齐)、`- [ ]` 任务列表、围栏代码块 | 标准 GFM,原样可用 |
| `<div>`、`<details>`、`<br>` 等内联 HTML | **一律当文本转义**(安全立场),写了不生效 —— 要块级能力用上面的扩展语法 |
| 行内代码里的定界符 | 反引号里的一切都是字面量:`` `$…$` ``、`` `a==b` `` 里的定界符既不开公式/高亮,也不会被前面的定界符当成闭合 —— 讲写法时放心写 |

公式与图表是按需加载的(正文里出现才去取对应的库),图表里的文字**不进全文搜索**(搜索只搜 Markdown 原文)。

## 带附件的 Markdown 导入

外部 md 常带本地相对引用,导入 = 扫描 → 上传 → 改写 → 建文档 → 验证,一步都别省:

1. **扫描**:列出所有本地相对引用(`![]()` 与 `[]()` 的目标),排除 `http(s)://`、`teamdoc://`、`/api/`、
   `mailto:`、`#` 锚点;本地文件不存在的引用:警告并保留原样。
2. **上传**:`td file up <项目> <路径> --json` → 记下返回的 `id`、`mime`、`canInline`、`name`。
3. **改写**:能不能当图片内嵌用**服务端返回的字段**判 —— `mime` 以 `image/` 开头 **且** `canInline` 为真 →
   `![alt](/api/files/{id}/download?inline=1)`,否则 → `[文字](/api/files/{id}/download)`。别按本地扩展名猜
   (`canInline` 是服务端的 inline 白名单,猜错就是正文里的裂图)。同目录重名上传会自动加后缀 `(2)`,以返回的 `name` 为准。
4. **建文档**:`td doc new <项目> <标题> --file -`,改写后的正文从 stdin 灌入;追加到既有文档用 `td doc edit <id> --append`。
5. **验证**:`td file ls <项目>` 确认每个附件的"标记"列出现 **被引用**(**可内嵌** 则说明它能当图片写),
   `td doc show <id>` 抽查图片链接格式。

多篇文档共享同一批附件时,附件只传一次,复用同一个文件 ID。正文里有公式或图表时,顺手按上一节核对写法
(行内 `$…$` 内侧不贴空白、` ```mermaid ` 围栏)—— 这两处写错的典型症状就是"页面上原样显示源码"。

## 边界

- 公开项目**加入前看不到任何内容**(搜索也搜不到):`td project ls --public` 找、`td project join` 加入,
  加入后的角色由项目设置决定(只读成员 / 编辑者)。
- `td doc mv` 跨项目只搬文档,**不带走附件**(正文引用的文件留在原项目);命令会先列出哪些文件会留下再让你确认。
- 令牌的创建与吊销只能在网页端(`td logout` 只删本地副本,不吊销令牌本身)。
- WebSocket 实时协同是网页会话专属,CLI 不涉及。
