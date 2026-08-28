# Phase 1 IssueAnalysis JSON Schema 输出

## 任务边界

目标：冻结 `IssueAnalysis` 的机器可读 JSON Schema，并提供只接受严格 JSON 对象的确定性解析边界。

教程依据：Hello-Agents V1.0.3 第 7 章结构化 Agent 边界、第 12 章评估，以及仓库“模型输出必须
通过 Pydantic/JSON Schema 校验”的强制规范。

当前行为：`parse_issue_analysis` 把模型返回的 JSON 字符串解析为 `IssueAnalysis`。当前没有模型
分析 Prompt、自动分类、风险策略、HTTP API、真实模型调用或业务状态变化。

验收条件：12 个字段全部显式存在；枚举、字符串、数组、布尔值和置信度类型严格；额外字段、缺失
字段、空白列表项、超长列表项、Markdown 围栏、尾随文本和非法 JSON 被拒绝；冻结 Schema 与
Pydantic 生成结果一致；解析错误使用稳定代码且不回显原始模型输出。

允许修改：`IssueAnalysis` 字段约束、冻结 Schema、结构化解析器、契约测试、架构和验证文档。

禁止修改：模型分析 Prompt、自动分类/风险策略、API、前端、Function Calling、工作流、RAG、
图片上传、多智能体和真实模型配置；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_issue_analysis_output.py tests/test_agent_contract.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：安全/质量人员在后续任务中复核类别、风险、路由和立即行动之间的跨字段规则；Agent
接入方必须调用 `parse_issue_analysis`，不能只依赖模型声称输出了 JSON。

## 冻结字段

| 字段 | 类型 | 边界 |
|---|---|---|
| `category` | enum | `safety/quality/management/logistics/consultation/unknown` |
| `issue_type` | string | 1～100 字符 |
| `summary` | string | 1～500 字符 |
| `observed_facts` | string[] | 0～20 项，每项 1～300 字符 |
| `uncertainties` | string[] | 0～20 项，每项 1～300 字符 |
| `missing_fields` | string[] | 0～20 项，每项 1～300 字符 |
| `risk_level` | enum | `undetermined/low/medium/high/emergency` |
| `immediate_actions` | string[] | 0～10 项，每项 1～300 字符 |
| `suggested_actions` | string[] | 0～10 项，每项 1～300 字符 |
| `recommended_route` | enum | `direct_answer/collect_more_info/propose_workflow/human_review` |
| `requires_human_review` | boolean | 严格布尔值，不接受字符串替代 |
| `confidence` | number | 0～1，不接受数字字符串 |

所有字段均为必填；空数组必须显式输出，不能依赖默认值。模型只能返回一个 JSON 对象，禁止使用
Markdown 代码围栏、解释性前缀或尾随文字。额外字段由 `extra="forbid"` 拒绝。

## 解析错误

- `invalid_output_type`：输入不是字符串，例如 bytes、对象或数组。
- `empty_output`：字符串为空或只有空白。
- `invalid_json`：JSON 语法错误、代码围栏或尾随文字。
- `schema_validation_failed`：JSON 合法，但缺失字段、字段额外、枚举/类型/长度或跨字段规则失败。

冻结契约位于 `contracts/phase1_issue_analysis.v1.schema.json`。静态 Schema描述字段形状；Pydantic
解析器还执行高风险必须人工复核且必须具有立即行动等跨字段规则。因此生产调用方必须以
`parse_issue_analysis` 的结果作为唯一有效结构化输出，不能绕过解析器直接信任 JSON。

本任务只冻结词汇和结构，不证明模型会正确选择类别、风险或路由；这些行为分别由后续固定案例和
安全门禁任务验收。
