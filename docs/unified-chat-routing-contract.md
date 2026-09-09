# 统一聊天、工单交接与安全流式输出契约

目标：合并“新建聊天/新建咨询”，由同一次结构化 AI 回答判断是否需要工单；满足受控条件时自动打开
对应类别的工单申请页。回答采用逐段显示，模型选择可由页面切换或填写，但密钥和端点仍归服务端所有。

教程依据：Hello-Agents V1.0.3 第7章结构化输出与工具边界、第9章有界上下文、第12章固定验收，
以及 Extra09 的单 Agent、确定性状态和失败留痕。

当前行为：聊天和咨询是两个入口；普通聊天永不产生结构化工单判断；咨询满足条件后仍停留在原页等待
用户点击；NDJSON 只传阶段，完整答案在 result 中一次显示；模型选择器只展示服务端单一型号。

验收条件：见 U01–U08。

允许修改：文字产品 v3 请求契约、模型适配选择参数、NDJSON 展示事件、聊天路由/组件、工单表单交接、
服务端公开运行信息、Fake/Mock 回归和相应文档。

禁止修改：正式工单六状态机、HMAC、确认/保存/派工权限、图片授权、知识来源、真实密钥、模型业务写权限、
多 Agent 或未经授权的真实模型调用。

测试命令：相关 pytest、`npm test --prefix frontend`、`npm run build --prefix frontend`、
`powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`和隔离 Chrome 验收。

人工确认点：AI 只决定是否进入申请界面并提供锁定分析；用户仍须生成提案、核对展示字段、确认并保存。
自定义型号可能改变费用、速度和效果，真实调用须由使用者承担并单独抽样。

## 数据与路由

- 新页面入口是 `/chat`；`/consult`只做向后兼容重定向，不保留第二种会话事实来源。
- 前端发送`intent=auto`。它使用结构化`TextReply/IssueAnalysis`，输入/轮次采用产品长会话上限；
  旧`chat`和`consult`仍由 API 兼容，但不再由新侧栏创建。
- `auto`保留深度聊天的180秒供应商等待、32768输出token、64000字答案、16000字单轮和50轮上限；
  模型仍须一次返回严格JSON，服务端按最近12轮/120000字上下文和400000字会话总量裁剪或拒绝。
- 只有服务端返回`can_propose=true`且类别为`safety/quality/management/logistics`时，页面才把已校验
  `IssueAnalysis`交接到`/submit?source=ai`。
- 工单页锁定 AI 的类别、风险、类型和摘要；用户在下一步只编辑提案展示字段。自动导航不调用
  `propose_issue_record`，不确认、不落库、不派工。
- “宿舍空调坏了，帮我上报”在通过模型结构化校验并被判定可跟进时，进入`logistics`申请；Fake 测试
  只验证协议，不宣称真实模型必然分类正确。

## 流式输出

- 服务器先取得并校验完整结构化结果，再发送`responding`阶段和有序`content_delta`事件；前端逐段渲染，
  最后以`result`作为唯一最终事实。
- 该机制是“已校验答案的安全流式展示”，不是供应商原始 token 直通，因此不会改善模型首字等待时间；
  它避免把未完成 JSON、无效字段、隐藏 reasoning 或随后会被安全边界覆盖的文字提前展示。
- `content_delta`仅含`type/index/text`，最多120段、单段1000字符、合计64000字符；索引跳跃、超限、
  非法事件、断流或 result 缺失均失败关闭且不自动重发。
- `responding`表示传输已校验答案，不伪装成模型思考；真实模型阶段仍只来自服务端 progress。

## 模型选择

- `/api/text/runtime`公开`available_models`和`custom_model_allowed`，不返回 API Key、请求头或环境内容。
- 文字服务商由服务端 `LLM_PROVIDER` 选择：`deepseek`（默认）读取 `LLM_*`，
  `tencent_token_plan`（腾讯云 Token Plan）读取 `TENCENT_TOKEN_PLAN_*`；两者都只允许官方白名单端点。
- 当前服务商的 `*_MODEL`是默认值；`LLM_MODEL_OPTIONS`/`TENCENT_TOKEN_PLAN_MODEL_OPTIONS`提供建议列表。
  页面还允许填写最多100字符的当前服务商模型标识，只接受字母数字开头及字母数字、点、下划线、冒号、短横线。
- 自定义值仅替换本次文字请求的 model；官方 HTTPS 端点、密钥、超时、重试、输出上限和人工边界不能
  由浏览器覆盖。Mock 模式不可自定义，也不会调用外部模型。

## 固定验收

- U01：侧栏只有“新建聊天”和“提交工单”，旧`/consult`跳转`/chat`。
- U02：日常问题留在聊天页，`can_propose=false`时不出现或打开工单。
- U03：可跟进后勤问题自动打开后勤申请，预填字段来自服务端分析且无正式记录副作用。
- U04：安全/质量/管理同样按类别交接；unknown、consultation或信息不足不交接。
- U05：回答至少产生一个有序 delta，拼接结果严格等于最终 answer；非法 delta 失败关闭。
- U06：等待状态显示真实 model/validating/responding 阶段；不展示隐藏思维或虚假工具。
- U07：建议型号和合法自定义型号随请求发送；非法型号在模型调用前拒绝，密钥不出服务端。
- U08：桌面与390×844移动端可发送、看流式回答、自动进入申请、返回聊天和人工生成提案；无横向溢出。
