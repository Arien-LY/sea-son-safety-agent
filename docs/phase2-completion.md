# Phase 2 提案审阅闭环与完成验收

## 任务边界

目标：完成 Phase 2 剩余四项，让页面显示“建议创建记录”，允许用户补充展示字段、查看确认前后差异
并确认；完善统一错误结果和脱敏工具审计，同时保证整个阶段没有正式记录持久化或派单副作用。

教程依据：Hello-Agents V1.0.3 第 7 章 `FunctionCallAgent`、工具参数校验和 `ToolRegistry`，以及
Extra09 的最小闭环、统一协议、失败留痕和可观测性原则。

当前行为：FastAPI 接收已校验 `IssueAnalysis` 进行提案预览；Vue 页面明确标注这是结构化验收入口，
不是已经接入真实模型的自然语言产品链。用户只能编辑五个记录展示字段，确认接口保留原始分析并返回
服务端差异。确认结果固定为 `confirmed_pending_persistence`。

验收条件：页面出现“建议创建记录”；用户可补充标题、描述、项目、区域和说明；风险、路由和人工复核
不可编辑；修改前后值可见；确认前后均 `persisted=false/dispatched=false`；参数错误、重复调用和内部
错误使用统一 `ToolResult`；每次工具结果记录脱敏摘要、时间和错误码且不包含原文或思维链。

允许修改：提案 v2 契约、工具错误与审计边界、无持久化 API、Vue 提案审阅页面、测试和阶段文档。

禁止修改：真实模型、API Key、正式问题 Store、数据库、记录编号、派单、整改状态机、RAG、图片上传
和多智能体；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_contract.py tests/test_tool_errors_and_audit.py tests/test_propose_issue_record_tool.py tests/test_validated_analysis_proposal.py tests/test_api.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：产品、安全和工程代表确认可编辑字段不会覆盖专业分析；确认“用户已确认”不会被误解为已
建单；确认差异表、错误提示和审计字段满足演示与安全要求；确认正式落库和派单继续留在 Phase 3。

## 页面与确认契约

```text
已校验 IssueAnalysis
  → POST /api/issue-proposals/preview
  → 建议创建记录（awaiting_user_confirmation）
  → 用户补充 review_fields
  → 实时显示确认前后差异
  → POST /api/issue-proposals/confirm
  → confirmed_pending_persistence
       persisted=false
       dispatched=false
```

- `review_fields` 包含 `record_title/record_description/project/area/reporter_note`。
- 确认请求不能携带额外字段；尝试在可编辑区域加入 `risk_level` 等字段会被服务端拒绝。
- 服务端差异按五个可编辑字段重新计算，不信任页面自行声明的变更清单。
- 预览响应携带进程级 HMAC-SHA256 完整性令牌；确认时重新验签，客户端改写原分析或原展示字段会
  被拒绝。
- 确认接口不创建记录 ID，不写文件或数据库，也不调用派单器。
- 页面明确标注当前为 mock 结构化验收入口，避免把手工构造分析冒充真实模型能力。

## 统一错误矩阵

| 场景 | `ok` | `recoverable` | `error_code` |
|---|---:|---:|---|
| 参数缺失、额外字段、错误 JSON 类型 | false | true | `invalid_arguments` |
| 不需要留痕或仅待补充信息 | false | true | `issue_not_eligible_for_proposal` |
| 模型改写已校验分析 | false | true | `analysis_mismatch` |
| 要求工具但模型未调用 | false | true | `tool_not_called` |
| 同一实例重复成功调用或重复调用标识 | false | true | `duplicate_call` |
| 提案构造内部异常 | false | false | `internal_error` |

`ToolResult` 的确定性校验要求：成功时不得带错误码或可恢复标记；失败时必须带稳定错误码。服务商或
内部异常细节不写入对外摘要。

## 脱敏审计

每个实际工具结果记录：

- UTC 时间 `occurred_at`；
- `tool_name`；
- 参数键名 `argument_keys`；
- 规范化参数的 SHA-256 摘要 `argument_digest`；
- `ok`、安全的 `result_summary` 和 `error_code`。

审计缓冲区容量默认 500 条，只存在当前进程内。它不包含参数值、用户正文、Prompt、模型完整上下文、
隐藏思维链或业务记录正文，也不是 Phase 3 的持久化 Store。

## 本地浏览器验收

- 桌面页面成功生成“建议创建记录”，展示类别、风险、路由和人工复核锁定字段。
- 补充项目、区域和说明后，差异表实时显示 3 项“修改前/修改后”。
- 点击确认后显示 `confirmed_pending_persistence`、`persisted=false`、`dispatched=false`。
- 390×844 移动视口下页面转为单列，标题、运行状态和提案入口可读。

本次浏览器验收只访问 `127.0.0.1` 本地服务，使用演示文本，没有访问外部系统或产生业务副作用。

## 剩余门禁

Phase 2 实现清单已完成，但仍未证明真实模型工具选择、成本或延迟。自然语言咨询到提案页面的真实模型
链必须在明确授权后单独验收。正式记录、幂等持久化、权限、派单、整改和关闭全部属于 Phase 3；在此
之前不能把已确认提案称为已上报问题。
