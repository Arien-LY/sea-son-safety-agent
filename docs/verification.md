# 验证记录

## 2026-08-28：Phase 0 本机基线

环境：

- Windows
- Python 3.12.10
- Node.js 24.13.0
- hello-agents 0.2.9
- openai 1.109.1

执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "from hello_agents import FunctionCallAgent, HelloAgentsLLM, SimpleAgent, ToolRegistry"
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 依赖解析和 `pip check` 通过。
- Hello-Agents 教程所需四个核心 API 导入通过。
- Python：9 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。

已知警告：

- `hello-agents==0.2.9` 内部仍使用 Pydantic V2 已弃用的 class-based Config，测试产生 1 条
  `PydanticDeprecatedSince20` 警告。该警告来自第三方包，不影响 V0；升级 Pydantic 或
  Hello-Agents 前必须单独验证。

未完成：

- 尚未进行另一位队员电脑上的全新克隆安装测试。
- 尚未调用真实收费模型；普通验证不会读取 API Key 或访问模型服务。
- 当前没有对话、问题识别、工作流或图片功能，不能据此宣称业务能力已完成。

## 2026-08-28：Phase 1 固定文字验收案例

范围：

- 仅完成 Phase 1 第一项，冻结 `phase1-fixed-text-v1` 案例契约和验收说明。
- 建立 20 条机器可读固定文字案例，普通咨询、安全、质量、管理、后勤各 4 条。
- 案例覆盖正常、信息不足、高风险和容易误判的表达；未实现 Agent、Prompt、Function Calling、
  工作流、RAG、图片上传或多智能体。

Git 启动审计：

- 委派输入称仓库为“尚无提交的独立 Git 仓库”，但现场只读检查显示 `HEAD` 已存在并指向
  `72320ed（初始化）`，工作区干净，当前分支为 `main`。
- 因存在安全的固定起点，按 `AGENTS.md` 从该提交创建 `phase1-fixed-acceptance-cases` 分支；未在
  `main` 直接开发。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase1_acceptance_cases.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 案例专项校验：7 tests passed。
- Python 完整测试：16 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 测试仅加载本地 JSON、Schema 和既有工程模块；未读取 API Key，未访问或调用任何真实/付费模型。

确定性门禁：

- Schema 和案例禁止未声明字段，版本、套件 ID、字段名与枚举固定。
- 恰好 20 条稳定 ID，五个类别各 4 条，输入和每条案例的必须要点 key 唯一。
- 风险上下界顺序有效；信息不足案例必须包含追问和不确定性约束。
- 高风险案例必须路由人工复核、标记人工复核，并禁止遗漏立即避险提示。

已知限制和遗留风险：

- 当前测试证明案例资产完整一致，不证明尚未实现的 Agent 能正确分类、提取、追问或路由。
- 风险区间、立即行动和必须要点仍需安全员/质量员专业复核；自由文本语义不能只靠结构校验。
- `propose_workflow` 只是未来路由预期，本阶段不创建记录、不派单、不改变业务状态。
- 行为验收的团队阈值要在单 Agent 接入前另行冻结；高风险漏掉人工复核或立即避险必须单例失败。
- 保留 Phase 0 已记录的第三方 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-28：Phase 1 文字咨询输入契约

范围：

- 仅完成 Phase 1 第二项，定义一条纯文字咨询消息及可选项目、区域和咨询者角色上下文。
- 使用 `grill-with-docs` 明确领域语义并新增根目录 `CONTEXT.md`：输入不是上报表单；咨询者角色
  不代表权限或责任；项目和区域只是用户提供、未经核实的文字标签。
- 未实现 API 路由、Agent、Prompt、Function Calling、工作流、RAG、图片上传、多智能体或前端交互。

Git 启动审计：

- 本任务启动时，上一任务分支 `phase1-fixed-acceptance-cases` 尚未合入 `main`，因此本任务分支
  `phase1-text-input-contract` 最初从上一任务提交创建。
- 上一任务经 squash merge 合入 `main` 后，其补丁 ID 与原提交相同但提交身份改变，导致 GitHub
  最初报告 `TASKS.md` 和本文件冲突。本分支随后跳过等价旧提交并变基到最新 `origin/main`；
  `git merge-tree --write-tree origin/main HEAD` 返回 0，当前 PR 不再叠加或重复上一任务提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_text_consultation_input.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 输入契约专项测试：25 tests passed。
- Python 完整测试：41 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 测试仅使用 Pydantic 和本地文件；未读取 API Key，未访问或调用任何真实/付费模型。

确定性门禁：

- `message` 必填，去除首尾空白后长度为 1～1000；空字符串、纯空白、错误类型和超长输入被拒绝。
- `project`、`area`、`requester_role` 可省略或为 `null`；显式空白值和超长值被拒绝。
- 模型启用严格类型和 `extra="forbid"`；图片、文件、二进制、正式 ID 和权限字段均不能混入。
- 冻结 JSON Schema 与 Pydantic 生成 Schema 逐项一致，字段或边界漂移会使测试失败。

已知限制和遗留风险：

- 当前契约只在模型层校验内存数据；尚未接入 HTTP API、Agent 或前端，不能宣称已经可以对话。
- 项目、区域和咨询者角色都是未核实的用户陈述；后续不得将其直接用于授权、派单或归责。
- 当前不收集登录身份、联系方式、项目/区域正式 ID；这些能力需在权限和持久化边界明确后单独设计。
- 字段名和长度仍需产品负责人确认；若修改，必须同步模型、Schema、固定案例和验证记录。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-28：Phase 1 单 Agent 基础对话

范围：

- 仅完成 Phase 1 第三项，使用 Hello-Agents `SimpleAgent` 建立普通文字咨询的最小直接回答闭环。
- 每次请求创建一个无 ToolRegistry、`enable_tool_calling=False`、无共享历史的单 Agent；模型接口
  必须由调用方注入，普通测试只使用 Fake LLM。
- 模型回答通过 `BasicDialogReply` Pydantic 契约，空响应、超时、模型错误、超长响应和伪工具调用
  映射为稳定错误码。
- 未实现对话 API、前端入口、真实模型、问题分类、风险判断、`IssueAnalysis` 输出、Function Calling、
  工作流、RAG、图片上传或多智能体。

Git 启动审计：

- PR #2 已通过 squash merge 合入 `main`，远端基线为 `e7c488d`。
- 本任务从更新后的 `main` 创建独立分支 `phase1-single-agent-dialog`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_basic_dialog.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 基础对话专项测试：11 tests passed。
- Python 完整测试：52 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 所有对话测试使用本地预设 Fake LLM；未读取 API Key，未创建模型客户端，未访问或调用真实/付费模型。

确定性门禁：

- 普通咨询返回去除首尾空白、长度 1～4000 的 `BasicDialogReply.answer`。
- 项目、区域和咨询者角色在模型消息中明确标注为用户自报且未经核实。
- 每次 `reply` 创建独立 `SimpleAgent`，第二次调用不会携带第一次调用的用户或模型消息。
- 响应守卫在 Hello-Agents 写入内部历史前拦截 `None`、空白响应和旧式工具调用标记。
- `empty_response`、`invalid_response`、`model_timeout`、`model_error`、`unsupported_tool_call`
  为稳定错误码，服务商异常细节不写入对外消息。
- 冻结 JSON Schema 与 Pydantic 生成 Schema 一致，漂移会使专项测试失败。

已知限制和遗留风险：

- 当前只是 Python 模型边界，没有 HTTP 或页面入口，不能从浏览器进行真实对话。
- 当前刻意不保留多轮历史；引入历史前必须先定义会话 ID、用户隔离、清理策略和隐私期限。
- 系统提示中的安全要求仍由模型遵循，尚未经过 `IssueAnalysis` 的确定性分类和风险路由，不能据此
  宣称高风险案例已经通过。
- 真实 `HelloAgentsLLM` 会封装服务商异常；其超时映射和真实连通性需要在独立、明确授权的冒烟测试中验证。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-28：Phase 1 IssueAnalysis JSON Schema 输出

范围：

- 仅完成 Phase 1 第四项，冻结 `IssueAnalysis` JSON Schema 并增加严格 JSON 解析器。
- 12 个字段全部改为显式必填；五个列表允许为空，但不能省略，列表项必须为 1～300 字符。
- 解析器使用 `model_validate_json(..., strict=True)`，拒绝额外/缺失字段、类型强制转换、Markdown
  围栏、尾随文字和非法 JSON，并使用稳定错误码。
- 未实现模型分析 Prompt、分类准确率、风险策略、API、真实模型、Function Calling、工作流、RAG、
  图片上传或多智能体。

Git 启动审计：

- PR #3 已通过 squash merge 合入 `main`，远端基线为 `272d43e`。
- 本任务从更新后的 `main` 创建独立分支 `phase1-issue-analysis-schema`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_issue_analysis_output.py tests/test_agent_contract.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 结构化输出与既有 Agent 契约测试：24 tests passed，其中新增结构化输出测试 20 项。
- Python 完整测试：72 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 测试只解析本地预设字符串和 Schema；未读取 API Key，未创建模型客户端，未访问或调用真实/付费模型。

确定性门禁：

- JSON Schema 与 Pydantic 生成 Schema 一致，字段、必填集合、枚举或长度漂移会使测试失败。
- 非字符串、空输出、非法 JSON 与契约校验失败分别返回稳定错误码，对外摘要不包含原始模型内容。
- 字符串形式的布尔值/置信度、非数组列表、额外责任人字段、缺失列表和空白/超长列表项均被拒绝。
- 既有高风险跨字段校验仍由 Pydantic 解析执行，不能只验证静态 Schema 后绕过解析器。

已知限制和遗留风险：

- 当前没有 Agent 分析 Prompt 或模型调用接入，不能据此宣称模型已经能够生成正确 `IssueAnalysis`。
- Schema 已固定类别和风险词汇，但尚未运行 20 条案例验证模型选择是否正确，因此 TASKS 中对应行为项
  仍保持未完成。
- JSON Schema本身未表达全部 Pydantic 跨字段验证；所有调用方必须使用 `parse_issue_analysis`。
- 解析错误目前只在 Python 边界返回，尚未映射为 HTTP 错误响应或前端提示。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-28：Phase 1 六类结构化问题分析

范围：

- 仅完成 Phase 1 第五项，新增无工具、无共享历史的 `IssueAnalyzer`，支持六个主类别协议。
- 分类系统提示冻结各类别定义，强调类别表示业务归口且与风险等级独立，并嵌入当前
  `IssueAnalysis` JSON Schema。
- 模型 JSON 在写入 Hello-Agents 内部历史前通过严格解析守卫；非法类别、Markdown、旧式工具调用
  和非 JSON 输出均被拒绝。
- 未实现真实模型准确率验收、风险策略、信息不足/高风险专项行为、API、前端、Function Calling、
  工作流、RAG、图片上传或多智能体。

Git 启动审计：

- PR #4 已通过 squash merge 合入 `main`，远端基线为 `22c173b`。
- 本任务从更新后的 `main` 创建独立分支 `phase1-analysis-categories`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analysis_categories.py tests/test_basic_dialog.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 分类、基础对话和结构化输出相关测试：45 tests passed，其中新增分类测试 14 项。
- Python 完整测试：86 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 全部分类测试使用预设 Fake LLM；未读取 API Key，未创建真实模型客户端，未访问或调用付费模型。

确定性门禁：

- `consultation/safety/quality/management/logistics/unknown` 六类均经 `IssueAnalyzer` 和
  `parse_issue_analysis` 端到端往返。
- 未声明的 `environment` 类别被 Schema 校验拒绝，无法静默降级或扩展枚举。
- 系统提示固定类别定义、`unknown` 保守语义及类别/风险分离规则，并包含当前 JSON Schema。
- 项目、区域和咨询者角色仍明确标记为未经核实；连续两次分析不共享用户或模型历史。
- 模型超时、一般模型错误和结构化输出错误保持独立稳定错误边界，不向外暴露服务商细节。

已知限制和遗留风险：

- Fake LLM 只证明协议和校验路径支持六类，不证明真实模型分类准确率，也没有达到团队行为阈值。
- 类别交叉场景仍需团队人工复核，尤其是高风险咨询、生活区用电和审批违规等表达。
- 风险等级、信息不足和高风险行为仍是后续独立任务，不能因当前提示包含相关字段而提前勾选。
- `IssueAnalyzer` 尚未接入 API 或前端；真实模型连通性、成本、延迟和服务商错误封装未验证。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-28：Phase 1 五级风险分析协议

范围：

- 仅完成 Phase 1 第六项，在结构化分析提示中冻结五级风险定义和判断边界。
- 明确 `undetermined` 不是低风险，类别、风险和置信度相互独立，`emergency` 只用于正在发生或
  人员立即暴露的紧迫危险。
- Fake LLM 测试覆盖五个合法等级、非法 `critical`、高风险既有人工复核/立即行动门禁，以及高风险
  咨询和紧急后勤交叉组合。
- 未实现真实模型风险准确率、信息不足专项行为、高风险完整响应策略、API、前端、Function Calling、
  工作流、RAG、图片上传或多智能体。

Git 启动审计：

- PR #5 已通过 squash merge 合入 `main`，远端基线为 `8968440`。
- 本任务从更新后的 `main` 创建独立分支 `phase1-analysis-risk-levels`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analysis_risk_levels.py tests/test_analysis_categories.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 风险、分类和结构化输出相关测试：45 tests passed，其中新增风险测试 11 项。
- Python 完整测试：97 tests passed。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 所有风险测试使用预设 Fake LLM；未读取 API Key，未创建真实模型客户端，未访问或调用付费模型。

确定性门禁：

- `undetermined/low/medium/high/emergency` 五级均经 `IssueAnalyzer` 和严格解析端到端往返。
- 未声明的 `critical` 被枚举拒绝；证据不足不得在系统提示中降为 `low`。
- `confidence` 与风险语义分离；`consultation+high` 和 `logistics+emergency` 组合通过。
- `high` 缺少立即行动、`emergency` 缺少人工复核均被既有 Pydantic 跨字段规则拒绝。

已知限制和遗留风险：

- Fake LLM 只证明协议支持五级风险，不证明真实模型能正确判断严重性或紧迫度。
- 五级阈值和交叉案例仍需专业人员人工复核；尚未建立真实模型高风险召回指标。
- 信息不足和高风险完整行为分别是后续任务，不能因当前已有部分安全约束而提前勾选。
- `IssueAnalyzer` 尚未接入 API 或前端；真实模型的成本、延迟和错误行为未验证。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-29：Phase 1 实现清单完成

范围：

- 完成 Phase 1 最后三项：信息不足安全边界、高风险立即避险与人工复核边界，以及 Fake LLM
  成功/失败矩阵。
- `IssueAnalysis` 新增确定性跨字段门禁；系统提示同步冻结不猜测事实、高风险优先避险和禁止越权
  行为。
- 20 条冻结文字案例全部通过同一 `IssueAnalyzer`、严格 JSON 解析和安全校验路径。
- 未实现或修改 API、前端对话、Function Calling、任务工作流、持久化、RAG、图片上传或多智能体。

Git 启动审计：

- PR #6 已通过 squash merge 合入 `main`，本任务基线为 `59e97ee`。
- 从更新后的 `main` 创建独立分支 `phase1-completion-safety`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analysis_safety_boundaries.py tests/test_phase1_fake_llm_matrix.py tests/test_phase1_fixed_case_matrix.py tests/test_analysis_categories.py tests/test_analysis_risk_levels.py tests/test_issue_analysis_output.py tests/test_agent_contract.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- Phase 1 安全边界、失败矩阵、固定案例和既有契约专项测试：63 tests passed。
- Python 完整测试：111 tests passed；保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 全部新增测试使用本地预设 Fake LLM；未读取 API Key，未创建真实模型客户端，未访问或调用
  真实/付费模型。

固定案例离线协议阈值：

- 主类别、风险区间、路由、人工复核标记、必须提取或追问的要点、禁止工具副作用六项均为 20/20。
- 该结果验证冻结预期经过输入、Prompt、严格解析与确定性门禁的协议链，不代表真实模型准确率。

确定性门禁：

- 缺失字段必须伴随不确定性；`unknown` 和 `undetermined` 必须列出缺失字段与不确定性。
- `collect_more_info` 必须有可追问字段；已有高风险事实即使信息不全也必须路由人工复核。
- `high/emergency` 必须包含立即行动、人工复核标记和 `human_review` 路由。
- 系统提示禁止猜测地点、人员、状态和责任，并禁止诱导无资质人员靠近、触碰、带电测试、拆卸或
  维修危险源。
- `IssueAnalyzer` 未注册工具；测试确认分析协议不包含建单、派单、处罚或关闭等 Task 副作用。

已知限制和遗留风险：

- Fake LLM 协议矩阵不能证明真实模型的分类准确率、高风险召回率或提示遵循能力。
- 固定案例的业务归口、风险区间、追问和避险措辞仍需安全、质量、管理和后勤专业人员人工验收。
- 真实模型冒烟尚未执行；如需执行，必须明确授权并单独记录密钥边界、成本、延迟和服务商错误行为。
- 当前没有 HTTP 或页面入口，不能从浏览器体验文字咨询；这属于后续明确范围，不影响本次 Python
  协议验收。
- Phase 0 的双机安装复现仍待两位队员在各自电脑完成，不能由本机验证代替。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-29：Phase 2 唯一问题记录提案工具契约

范围：

- 只增加 `propose_issue_record` 一个工具及其最小注册表，参数复用冻结的 `IssueAnalysis` Schema。
- 冻结 `IssueRecordProposal`：等待用户确认、未保存、未派单，不包含正式记录 ID 或工作流状态。
- 工具仅接受 `propose_workflow/human_review` 路由；普通咨询和仅待补充信息的分析被确定性拒绝。
- 未接入 Agent、API、页面、确认流程、持久化、派单、重复调用控制或审计日志。

Git 启动审计：

- PR #7 已通过 squash merge 合入 `main`，本任务基线为 `bdc112a`。
- 从更新后的 `main` 创建独立分支 `phase2-propose-issue-record-contract`，没有叠加未合入提交。
- 老大已明确要求进入 Phase 2；Phase 1 专业人员逐条复核仍需补齐，不能视为已由自动测试替代。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_propose_issue_record_tool.py tests/test_tool_contract.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 工具、既有统一返回和 `IssueAnalysis` 契约专项测试：33 tests passed。
- Python 完整测试：122 tests passed；保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 验证过程未读取 API Key，未创建模型客户端，未调用真实或付费模型。

验收关注：

- 注册表工具名严格等于 `("propose_issue_record",)`，没有提前加入搜索、保存、派单或工作流工具。
- Function Calling 参数 Schema 与冻结的 Phase 1 `IssueAnalysis` 契约一致。
- 成功提案固定 `requires_user_confirmation=true`、`persisted=false`、`dispatched=false`。
- 非法参数返回 `invalid_arguments`；不需要留痕的路由返回
  `issue_not_eligible_for_proposal`，均不回显原始敏感字段。

已知限制和遗留风险：

- 当前工具尚未注册到真实 `FunctionCallAgent`，不能据此宣称模型工具选择或原生调用链已经通过。
- 当前没有用户确认、持久化或派单能力；提案只能作为 Python 内存中的受控返回值。
- 重复调用、内部异常、结构化审计和页面差异展示属于后续 Phase 2 条目。
- 所有测试使用本地确定性数据；未读取 API Key，未创建模型客户端，未调用真实或付费模型。

## 2026-08-29：Phase 2 已校验分析到原生工具调用

范围：

- 新增 `IssueProposalAgent`，只接受已构造成功的 `IssueAnalysis`。
- 普通咨询和仅待补充信息的分析在原生模型调用前停止；需要跟进时只暴露
  `propose_issue_record`，最大工具迭代为 1。
- 工具调用参数必须与输入分析逐字段一致；合法但被改写的分析返回 `analysis_mismatch`。
- 未接入 API、页面、确认差异、持久化、派单、重复调用控制或审计日志。

Git 启动审计：

- PR #8 已通过 squash merge 合入 `main`，本任务基线为 `3d06e35`。
- 从更新后的 `main` 创建独立分支 `phase2-validated-analysis-proposal`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_validated_analysis_proposal.py tests/test_propose_issue_record_tool.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 已校验分析、提案工具和结构化输出专项测试：39 tests passed。
- Python 完整测试：130 tests passed；保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 验证过程未读取 API Key，未创建真实服务商客户端，未调用真实或付费模型。

验收关注：

- `direct_answer/collect_more_info` 不调用 Fake 原生模型或工具。
- `propose_workflow/human_review` 强制选择唯一的 `propose_issue_record` 原生函数。
- 完整 `IssueAnalysis` JSON Schema 被发送给原生函数调用，且不执行宽松类型转换。
- 篡改、非法类型、非法 JSON 和未执行工具分别安全失败，不返回伪造提案。
- 成功输出仍固定等待用户确认、未保存、未派单。

已知限制和遗留风险：

- Fake 原生客户端只证明 FunctionCallAgent 协议与守卫，不证明真实模型能够稳定生成正确工具参数。
- 当前调用会在一次工具响应后请求一次无工具最终文本；最终文本不作为事实来源，但真实模型成本和
  延迟仍需单独授权验证。
- 当前没有 API 或页面入口，也没有确认、持久化或派单能力。
- 重复调用、内部异常、审计日志和页面差异展示属于后续 Phase 2 条目。
- 所有测试使用本地 Fake；未读取 API Key，未创建真实服务商客户端，未调用真实或付费模型。
