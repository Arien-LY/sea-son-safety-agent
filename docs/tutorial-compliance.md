# Hello-Agents V1.0.3 教程符合性

本项目以 Datawhale Hello-Agents V1.0.3 为学习和实现基线。本文件把教程原则转换为可检查的工程规则，
避免只在文档中声称“参考教程”。

## 章节映射

| 教程内容 | 本项目采用方式 | 当前阶段 |
|---|---|---|
| 第 4 章 ReAct | 理解“思考—工具—观察”循环，但 V0 不暴露思维链 | 规划中 |
| 第 4 章 Plan-and-Solve | 用于拆解整改步骤；状态仍由确定性代码推进 | Phase 3 |
| 第 7 章 SimpleAgent | 先完成普通咨询和单 Agent | Phase 1 |
| 第 7 章 FunctionCallAgent | 正式工具调用优先采用原生 Function Calling | Phase 2 |
| 第 7 章 ToolRegistry | 工具注册、参数校验、统一返回 | 已建立底座 |
| 第 8 章 RAG | 在文字和工作流稳定后再加入知识检索 | Phase 4 |
| 第 9 章上下文工程 | 红线常驻、会话有限、按需检索、保留任务焦点 | Phase 4 |
| 第 12 章评估 | 固定案例、工具调用、人工验证和成本指标 | Phase 1 起 |
| 第 16 章毕业设计 | README、依赖、示例、测试和 PR 自检 | 持续 |
| Extra09 | 最小闭环、少工具、统一协议、Trace、失败留痕 | 持续 |

## 可机械检查的规则

- Python 固定 3.12；依赖必须锁定或给出明确兼容范围。
- `hello-agents==0.2.9` 与本地 V1.0.3 教程示例兼容；升级必须单独 PR 验证 API 变化。
- Pydantic 模型默认 `extra="forbid"`，阻止模型偷偷扩展字段。
- 工具统一返回 `ToolResult`，错误包含稳定 `error_code`。
- Agent 最大步骤、超时和重试必须有上限。
- 测试默认 Fake/Mock；普通 `verify.ps1` 不访问外部模型。
- 每个阶段在 `TASKS.md` 具有固定输入、输出、验收和禁止范围。
- 新增 RAG、图片或多智能体前必须有前一阶段的验证记录。

## 教程源码

- 上游仓库：https://github.com/datawhalechina/hello-agents
- 本项目开发机参考副本：`../hello-agents-1.0.3参考教程/hello-agents-1.0.3/`

相对路径仅用于本地学习，不作为运行时依赖。
