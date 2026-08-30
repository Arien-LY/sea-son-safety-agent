# 聊天阅读与 Markdown 安全契约（2026-08-31）

目标：在保留海之子品牌、侧栏入口和既有业务闭环的前提下，把普通聊天与专业咨询的消息区重构为
安静、可读、适合长回答的会话界面；参考用户提供的 Codex 截图中的通用排版关系，不复制 Codex App
未公开界面代码、品牌资源、内部提示词或隐藏提示词。

教程依据：Hello-Agents V1.0.3 第7章单 Agent、第9章有限上下文、第12章固定验收与 Extra09
真实进度/失败留痕。公开来源边界依据 `docs/decisions/0001-codex-harness.md`：Codex harness 是
Apache-2.0 的编码 Agent 执行系统，不作为本项目运行时；本任务不引入其 CLI、App Server、SDK、
Shell、沙箱、工具或权限模型。

当前行为：用户消息已经靠右、助手没有头像，但回答仍以 `white-space: pre-wrap` 的单个纯文本段落展示；
标题、粗体、列表、代码块和链接不能结构化呈现。消息正文最大宽度过宽，页头、消息和 composer 没有共享
稳定阅读轴；长回答的字号、行高、段落节奏和移动端留白不足。

验收条件：V01–V10 与 S01–S06 全部通过；Fake/Mock 验证不调用真实或付费模型。

允许修改：Vue 消息模板、局部 Markdown 渲染辅助、前端样式、前端测试、浏览器 Fake fixture、README、
TASKS 与验证文档。仅当安全 Markdown 无法以现有依赖可靠实现时，允许增加一个成熟的小型解析依赖，
并锁定版本、核对许可证和记录来源。

禁止修改：`.env`、密钥、DeepSeek 运行时、`CHAT_SYSTEM_PROMPT`（本任务不需要改）、专业咨询 Schema、
Phase 1/3 冻结契约、工单权限与状态机、人工确认、高风险复核、图片授权、RAG、多智能体、自动工单、
Codex harness/App Server/CLI/工具系统，以及任何隐藏思维链的读取或展示。

测试命令：`npm test --prefix frontend`、`npm run build --prefix frontend`、相关 `pytest`、
`powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`、桌面与 390×844 隔离浏览器验收。

人工确认点：Markdown 只改变回答呈现，不改变模型原文、风险字段或工单资格；停止等待不承诺停止供应商
计算或计费；真实模型的 Markdown 遵循率、回答质量、延迟和费用仍需用户主动另行验收。

## 冻结视觉验收

- V01 桌面消息正文共享居中阅读轴，最大可读宽度约 860px（允许 800–900px），页头与 composer 对齐。
- V02 中文系统字体栈优先，助手正文为 17px 左右、行高约 1.75；长段落、标题和列表层级清晰。
- V03 用户消息保持右侧浅灰气泡，无头像、名称或卡片标题；长文本可换行且不压满全宽。
- V04 助手回答无头像、名称、外框、底色或卡片阴影，以纯正文呈现；执行用时继续为低干扰折叠入口。
- V05 composer 在消息区下方形成悬浮圆角输入面板，工具、模型、计数和发送动作均保留且可键盘操作。
- V06 普通聊天与专业咨询共用消息排版；咨询的风险、追问、人工复核和提案入口仍清晰可辨。
- V07 长回答、16000字输入、上下文裁剪提示、等待真实阶段、停止等待和错误恢复均不回退。
- V08 左侧新建聊天、新建咨询、提交工单、最近工单和全部历史入口不变，海之子蓝色品牌标识不变。
- V09 桌面 1280×720 及更宽视口无页面级横向溢出；消息滚动与 composer 布局稳定。
- V10 390×844 下 `scrollWidth == clientWidth`，消息、代码块、链接、风险提示和 composer 无横向溢出。

## 冻结 Markdown 与安全验收

- S01 使用成熟 CommonMark 解析器展示标题、粗体、段落、有序/无序列表、引用、行内代码、代码块和链接。
- S02 原始 HTML 必须关闭；`<script>`、事件处理器、`iframe` 等输入只作为文本，不产生可执行 DOM。
- S03 链接只允许 `http:`、`https:` 与 `mailto:`；拒绝 `javascript:`、`vbscript:`、`file:`、`data:`、
  协议相对地址和其它未知协议。外部链接添加 `target="_blank"` 与 `rel="noopener noreferrer"`。
- S04 不渲染远程图片，避免模型回答触发第三方像素、隐私泄漏或破坏布局；图片 Markdown 只显示替代文本。
- S05 单换行安全换行，连续空行形成段落；代码块可在自身区域横向滚动，不让页面横向溢出。
- S06 自动测试覆盖正常 Markdown、HTML 注入、危险/混淆协议、属性逃逸、图片和安全链接边界。

## 依赖与来源决定

- 采用 `markdown-it` 15.0.1，MIT License。项目主页声明其遵循 CommonMark、可配置且默认关闭 HTML；
  API 文档说明默认拒绝 `javascript:`、`vbscript:`、`file:` 和大多数 `data:` URL。本项目进一步收紧协议、
  禁用图片并自定义外部链接属性。
- 不复用 OpenAI Codex 仓库的 UI 代码。公开 Codex 仓库及其 harness 采用 Apache-2.0；官方文章把可复用
  核心定义为对话状态、工具、审批、沙箱和事件执行系统，这些均不符合本次 Vue 消息呈现范围。
- 来源：<https://github.com/markdown-it/markdown-it>、<https://markdown-it.github.io/markdown-it/>、
  <https://github.com/openai/codex>、<https://developers.openai.com/blog/codex-as-a-platform>。
