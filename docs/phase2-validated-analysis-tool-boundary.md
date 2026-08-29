# Phase 2 已校验分析工具调用边界

## 任务边界

目标：把已通过 Pydantic 跨字段校验的 `IssueAnalysis` 接入 Hello-Agents 原生 Function Calling，
确保普通咨询不调用工具，需要跟进的问题只能原样进入 `propose_issue_record`，且全链路不保存、不派单。

教程依据：Hello-Agents V1.0.3 第 7 章 `FunctionCallAgent` 原生函数调用、工具参数 Schema 和
`ToolRegistry`；结合项目“模型只提交提案、确定性代码守住副作用”的强制规范。

当前行为：`IssueProposalAgent` 只接受 `IssueAnalysis` 实例。`direct_answer/collect_more_info` 在模型
调用前直接返回；`propose_workflow/human_review` 使用只含一个工具的临时注册表和强制函数选择执行
单轮原生工具调用。每次请求独立创建 Agent 和注册表，不共享历史。

验收条件：普通咨询不调用模型或工具；需要跟进的分析只暴露 `propose_issue_record`；函数参数使用
完整冻结 Schema；模型参数与已校验分析逐字段一致才执行；改写、非法类型、非法 JSON 和未调用工具
均返回稳定错误；成功结果始终要求用户确认并声明未保存、未派单。

允许修改：FunctionCallAgent 适配边界、严格参数一致性守卫、Fake 原生函数调用测试、架构、任务与
验证文档。

禁止修改：真实模型、API、页面、用户确认、确认前后差异、持久化、派单、重复调用控制、审计日志、
工作流、RAG、图片上传和多智能体；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validated_analysis_proposal.py tests/test_propose_issue_record_tool.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：产品、安全和工程代表确认以 `recommended_route` 作为工具资格门禁；确认模型不得修改已
校验分析；确认单轮工具迭代上限及后续一次无工具最终响应符合成本和安全要求。

## 调用与安全边界

```text
IssueAnalysis（已校验）
  ├─ direct_answer / collect_more_info → 不调用模型，不调用工具
  └─ propose_workflow / human_review
       → 临时 FunctionCallAgent（max_tool_iterations=1）
       → 唯一原生函数 propose_issue_record
       → 参数与原 IssueAnalysis 严格逐字段比对
       → ToolResult 包装的待确认提案
```

- 函数 Schema 使用完整 `IssueAnalysis.model_json_schema()`，不依赖自然语言或正则解析工具参数。
- Hello-Agents 默认参数类型转换在本边界被关闭，字符串布尔值或置信度不能被静默转换为合法类型。
- 模型即使给出另一个合法 `IssueAnalysis`，只要与输入不完全一致，也返回 `analysis_mismatch`。
- 工具未执行时返回 `tool_not_called`；非法 JSON 或字段返回 `invalid_arguments`。
- Agent 最终自然语言响应不作为事实来源；调用方只接收捕获的统一 `ToolResult`。
- 运行时没有 Store、数据库、派单器或工作流依赖，成功提案仍固定 `persisted=false`、
  `dispatched=false`。
