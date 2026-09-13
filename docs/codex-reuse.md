# Codex 公开实现参考记录

核验日期：2026-09-11。固定参考 OpenAI Codex `rust-v0.114.0`，解引用提交
`b9904c0ae4ecb773549efd6ea3fb05229402fdb9`；不是对最新版的声明。

| 官方文件 | 本项目采用的设计思想 |
| --- | --- |
| [prompt.md](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/codex-rs/core/prompt.md) | 系统规则、交互表达、工具边界分开；本项目独立编写中文工程业务提示 |
| [history.rs](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/codex-rs/core/src/context_manager/history.rs) | 保持完整问答/工具调用配对，区分持久历史与本次模型上下文 |
| [registry.rs](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/codex-rs/core/src/tools/registry.rs) | 名称注册、统一结果、按调用标识回填；复用项目已有 Hello-Agents 工具底座 |
| [spec.rs](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/codex-rs/core/src/tools/spec.rs) | 类型化工具声明；其中托管搜索声明不等于可移植的搜索后端 |

这是设计参考和独立 Python/Vue 实现，没有复制 Rust 代码、整段系统提示、非公开提示、账号凭据或 Codex 托管服务。
联网采用独立 Tavily API 与本机公开 HTTPS 文字读取器，仍是一个 Agent 的原生 function calling。

按本项目选择的工具集（2026-09-13补齐）：

| 工具 | 项目用途与接入方式 |
| --- | --- |
| search_knowledge | 复用现有审核规范目录，按明确地区、类别、复核有效期过滤；原生模型调用，返回原始出处与释义标记 |
| calculate | 独立实现有限十进制四则计算，处理数量/面积/比例；不使用 eval 或 shell，不做单位和工程安全校核 |
| web_search | Tavily 公开资料检索，独立密钥，返回实际来源 |
| read_webpage | 有界公开HTTPS文字读取，拒绝内网、重定向和脚本执行 |
| current_time | 代码读取北京时间和星期，不靠模型猜日期 |

以上五项共享调用标识、参数校验、ToolResult、进度与预算；这才是对 Codex 工具分发设计的项目适配。
calculate 是项目自主实现，不声称复制自 Codex。search_knowledge 沿用现有项目底座，不重复建立知识库。
照片分析继续逐次外发确认；propose_issue_record 继续由已校验分析和人工操作驱动；二者不是可任意调用的自动执行工具。
工单历史当前通过页面读取，没有向模型开放无范围数据库浏览。Codex 的任意终端执行、文件修改、通用桌面控制不进入业务工具集。

该提交顶层 [LICENSE](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/LICENSE)
为 Apache-2.0；[NOTICE](https://github.com/openai/codex/blob/b9904c0ae4ecb773549efd6ea3fb05229402fdb9/NOTICE)
保留 OpenAI 和上游声明。原件存于 `desktop/licenses/codex-apache-2.0.txt` 与 `codex-NOTICE.txt`，
打包器将其复制到内部许可目录。此记录不改变 Hello-Agents 自身许可，也不表示 OpenAI 背书。

接口依据：

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)：真实 assistant tool_calls → tool_call_id 结果回填。
- [OpenAI web search](https://developers.openai.com/api/docs/guides/tools-web-search)：明确托管能力与自建工具的区别。
- [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/) 与 [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)：深度工具轮次需回传供应商 opaque reasoning_content。本实现仅在同一次请求的 SDK 消息中短暂保留，禁止进度展示、日志和持久化；普通无工具路径维持原有隔离。
- [Tavily search](https://docs.tavily.com/documentation/api-reference/endpoint/search)：独立密钥，basic、最多5条、不请求生成答案或完整原文，不自动重试。

配置有效不等于真实服务能力已验收。此次未进行付费模型/Tavily 调用；腾讯供应商分支没有合并，未知 `LLM_PROVIDER` 会拒绝启用文字服务。
