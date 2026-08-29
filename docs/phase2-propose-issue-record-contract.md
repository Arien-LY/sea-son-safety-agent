# Phase 2 问题记录提案工具契约

## 任务边界

目标：只增加一个名为 `propose_issue_record` 的受控工具，冻结其原生 Function Calling 参数和待确认
提案返回契约，为后续 Agent 接入、页面补充确认和错误审计建立稳定边界。

教程依据：Hello-Agents V1.0.3 第 7 章 `FunctionCallAgent`、工具基类、参数定义与
`ToolRegistry`；遵循最小工具集、自描述 JSON Schema 和统一执行协议原则。

当前行为：Phase 1 的 `IssueAnalyzer` 仍不注册任何工具。本任务新增独立工具与最小注册表工厂，但不把
它接入 Agent、API 或页面。工具只接受完整 `IssueAnalysis` 参数，输出 `ToolResult` 包装的待确认提案。

验收条件：注册表中只有 `propose_issue_record`；Function Calling 参数严格复用冻结的 Phase 1
`IssueAnalysis` Schema；只有 `propose_workflow/human_review` 路由可生成提案；返回值明确要求用户
确认并声明尚未保存、尚未派单；缺失、错误类型、额外字段及普通咨询路由被安全拒绝。

允许修改：受控工具实现与导出、提案 JSON Schema、工具契约测试、领域词汇、架构、任务和验证文档。

禁止修改：Phase 1 Agent、真实模型、Agent 工具循环、API、页面、确认流程、持久化、派单、重复调用
控制、审计日志、工作流、RAG、图片上传和多智能体；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_propose_issue_record_tool.py tests/test_tool_contract.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：产品、安全和工程代表确认工具名称及描述不会让模型误以为已建单；确认提案字段足以支持
后续页面补充；确认 `propose_workflow/human_review` 是当前唯一允许生成提案的两类路由。

## 契约决策

- 工具参数直接复用 `contracts/phase1_issue_analysis.v1.schema.json`，不复制或重命名问题字段。
- `IssueAnalysis` 必须重新经过严格 JSON 校验，不能信任模型或调用方声称“已经校验”。
- `direct_answer` 和 `collect_more_info` 即使误调用工具，也返回
  `issue_not_eligible_for_proposal`，不生成提案。
- `IssueRecordProposal.status` 固定为 `awaiting_user_confirmation`。
- `requires_user_confirmation` 固定为 `true`；`persisted` 和 `dispatched` 固定为 `false`。
- 输出不包含正式记录 ID、责任人、派单对象或业务工作流状态，避免把建议误表示为已执行动作。

本任务只冻结并实现唯一工具本身。把经过校验的分析接入原生 `FunctionCallAgent`、呈现页面、处理确认、
重复调用和审计日志，仍需按 `TASKS.md` 后续条目分别实现与验收。

## 契约演进

- `phase2_issue_record_proposal.v1.schema.json` 保留最初冻结的只读提案结构，不再修改。
- 页面补充与确认需要可编辑的记录展示字段，因此新增
  `phase2_issue_record_proposal.v2.schema.json`，增加 `review_fields`。
- v2 只允许标题、描述、项目、区域和补充说明；`analysis` 仍完整保留，风险、路由和人工复核不可由
  用户编辑。
- 当前 API 与页面使用 v2；保留 v1 是为了避免已经冻结的契约发生无声破坏性漂移。
