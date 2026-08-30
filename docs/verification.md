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

## 2026-08-29：Phase 2 提案审阅闭环完成

范围：

- 完成 Phase 2 剩余四项：页面建议记录与用户确认、确认前后差异、统一错误矩阵、脱敏工具审计。
- 保留冻结的提案 v1，新增含五个用户可编辑展示字段的 v2 契约，避免无声破坏已有版本。
- 新增无持久化 FastAPI 预览/确认边界和 Vue 提案审阅页面。
- 未实现真实模型、正式记录 Store、数据库、记录编号、派单或整改工作流。

Git 启动审计：

- PR #9 已通过 squash merge 合入 `main`，本任务基线为 `f744a94`。
- 从更新后的 `main` 创建独立分支 `phase2-complete-proposal-review`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_contract.py tests/test_tool_errors_and_audit.py tests/test_propose_issue_record_tool.py tests/test_validated_analysis_proposal.py tests/test_api.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- 工具错误/审计、提案契约、原生调用和 API 专项测试：39 tests passed。
- Python 完整测试：145 tests passed；保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 未读取 API Key，未创建真实服务商客户端，未调用真实或付费模型。

本地浏览器验收：

- 桌面页面成功完成建议生成、三项用户补充差异和确认。
- 确认结果显示 `confirmed_pending_persistence`、`persisted=false`、`dispatched=false`。
- 390×844 移动视口下单列布局正常；浏览器控制结束前已恢复默认视口。
- 只访问 `http://127.0.0.1:5173/` 与本地 FastAPI，未访问外部站点。

确定性门禁：

- 用户只能编辑 `review_fields`，确认接口拒绝额外的风险、路由或人工复核字段。
- 预览响应使用进程级 HMAC-SHA256 令牌保护原提案；回传时篡改锁定分析会使确认失败。
- 服务端重算差异；前端不能伪造确认变更清单。
- `ToolResult` 强制成功/错误字段一致，并覆盖 `invalid_arguments/duplicate_call/internal_error`。
- 同一工具实例重复成功参数以及重复 API 调用标识都返回 `duplicate_call`。
- 提案构造异常返回脱敏 `internal_error`，不暴露异常详情。
- 审计只记录 UTC 时间、工具名、参数键名和 SHA-256 摘要、结果摘要与错误码。

已知限制和遗留风险：

- 页面使用手工构造的结构化验收输入，明确不是自然语言真实模型分析入口。
- API 的重复调用标识和工具审计只存在进程内，重启或多进程之间不共享；正式幂等和持久化属于 Phase 3。
- 完整性令牌只在当前进程有效且不表达提案所有权；Phase 3 落库前仍需增加身份、所有权和持久化幂等。
- 审计缓冲区不是持久化审计系统；进程退出后记录消失。
- 真实模型工具选择、成本、延迟和服务商错误尚未单独授权验证。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-29：Phase 3 整改和后勤工作流完成

范围：

- 冻结六个主状态、独立取消处置以及补充信息、驳回和重新整改路径。
- 新增本地原子 JSON Store、持久化幂等键、revision 乐观并发和完整业务事件轨迹。
- 新增责任角色建议和人工派工边界；建议不会自动填写责任人或改变状态。
- 新增安全、质量、管理、后勤共用工作流 API 和 Vue 本地验收页面。
- 未新增 Agent 工具、Prompt、RAG、图片、多智能体、外部派单、通知或真实/付费模型调用。

Git 启动审计：

- PR #10 已通过 squash merge 合入 `main`，本任务基线为 `7df7963`。
- 从更新后的 `main` 创建独立分支 `phase3-deterministic-workflow`，没有叠加未合入提交。

执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_contract.py tests/test_phase3_workflow.py tests/test_phase3_api.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

结果：

- Phase 3 契约、状态机、Store 和 API 专项测试：18 tests passed。
- Python 完整测试：163 tests passed；保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- Vue：TypeScript 检查和 Vite 生产构建通过，32 modules transformed。
- 验证过程未读取 API Key，未创建真实服务商客户端，未调用真实或付费模型。

本地浏览器验收：

- 高风险安全问题从提案确认、正式草稿、提交、人工派工、整改、待复查走到专业复查关闭；最终
  revision 为 6，轨迹为 6 个连续事件。
- 低风险后勤门锁工单复用相同六步闭环，责任角色建议和人工指派均为后勤维修人员。
- 页面明确区分责任建议与人工指派；记录状态、revision 和事件轨迹均来自服务端响应。
- 390×844 移动视口下单列布局正常；验收结束前恢复默认视口。
- 浏览器控制台无 error/warning；只访问本地 Vue 与 FastAPI 服务。
- 浏览器验收 Store 位于操作系统临时目录，没有写入仓库；本地服务已停止。

确定性门禁：

- 主状态枚举严格为 `draft/submitted/assigned/rectifying/pending_review/closed`；取消只改变独立
  `disposition` 并终止后续推进。
- 提案确认结果带 HMAC-SHA256 凭据；正式创建重新校验凭据，篡改风险或正文会失败。
- 创建幂等键及请求摘要持久化；同键同请求返回原记录，同键不同请求冲突。
- 同路径 Store 实例共享进程锁；修改前重读，临时文件 `flush + fsync` 后原子替换。
- 原子替换失败测试证明旧文件保持逐字节不变；24 个并发创建无记录丢失。
- 损坏的记录键或悬空幂等索引会使 Store 拒绝读取，且不会覆盖原文件。
- 更新必须携带最新 revision；两个相同 revision 并发提交只有一个成功。
- 整改动作只允许人工指派的整改人；整改提交、复查、驳回、补充和取消必须保留说明。
- 高风险关闭只允许独立专业复查人，原报告人即使声明专业复查角色也不能自行关闭。
- 所有事件包含顺序、UTC 时间、动作人、角色、前后状态/处置和业务说明，不含隐藏思维链。

已知限制和遗留风险：

- JSON Store 只适合单机演示；共享锁只覆盖当前 Python 进程，不提供跨进程、跨主机事务、备份或
  灾难恢复。正式部署应迁移到有事务和唯一约束的数据库。
- HMAC 密钥仍为当前进程随机生成；后端重启后尚未保存的确认提案需要重新预览和确认。
- API 和页面使用演示 actor ID，没有登录、身份真实性、项目成员关系或权限令牌；不能直接用于生产。
- 当前派工只写本地记录，不调用外部工单、消息或通知系统。
- 专业人员仍需复核责任角色名称、状态语义、高风险关闭/取消规则和安全/后勤验收措辞。
- Phase 0 的双机全新克隆验证仍未完成；本机 163 条测试不能替代队友电脑验收。
- 保留既有 `hello-agents==0.2.9` 的 Pydantic 弃用警告；本任务未升级依赖。

## 2026-08-30：Phase 4 知识检索与依据引用完成

范围与教程依据：

- 先冻结 `docs/phase4-knowledge-contract.md`、8 条资料及15个固定检索案例，再实现检索与接口。
- Hello-Agents V1.0.3 第8章：本地小规模检索；第9章：有限候选上下文且不提升为系统指令；
  第7章：原生工具 Schema、严格参数和统一返回；Extra09：有限容量脱敏审计。
- 两份政府官网公开行政法规短释义：安全条例第27/28/29/31/32条，质量条例第29/30/32条。
  官方来源 URL、版本、更新时间、适用范围、条号和入库核对信息均保留；不含内部项目资料。
- 不新增向量库、嵌入服务、第二个模型调用、图片、多智能体、外部派单或业务状态权限变化。

Git 启动审计：

- PR #11 已 squash merge 合入 main，基线为 `5cd9d7c`；从更新后的 main 创建
  `phase4-readonly-knowledge`，没有叠加未合入的 Phase 3 分支。
- 目标 `Arien-LY/sea-son-safety-agent` 经 GitHub CLI 只读核对仍为私人仓库。
- 当前仓库已有提交，最初 unborn main 的启动限制不再适用；没有直接在 main 开发。

验证命令与结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase4_knowledge.py tests/test_phase4_api.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
git diff --check
```

- Phase 4 专项：66 tests passed。
- 完整 Python：229 tests passed，1 条既有 Hello-Agents Pydantic 弃用警告。
- TypeScript 与 Vite 生产构建通过：35 modules transformed。
- 15 个冻结案例全部达到预期精确 ID 集合；所有返回引用逐字段与目录核对，SHA-256 独立重算一致。
- `git diff --check` 无空白错误；Windows Git 的 LF/CRLF 提示不影响测试。
- 验证没有初始化真实服务商客户端、读取 API Key 或调用真实/付费模型；无新增依赖。

确定性门禁：

- 严格拒绝多余参数、日期/开关覆盖、字符串布尔/整数、伪造来源、引用或人工结论。
- 未知/境外地区不引用；按服务器日期剔除撤回、尚未到核对日期和已到复核截止日的资料。
- `2026-11-29` 可命中、`2026-11-30` 停止本批引用；截止日不是法律失效日。
- 来源缺失、重复 ID、未授权、非法域名、版本晚于核对、无效日期、坏 JSON、超大文件均安全降级。
- 关键词命中数排序，稳定 ID 决定同分顺序，最多3条；重复调用确定性一致，每次重新读取目录。
- 关闭知识库先于文件读取；缺失/损坏/关闭/无命中时保留同一次 Fake 分析的风险、立即行动和人工标记。
- 普通咨询可以按关键词跨领域检索，但不会改成工作流类别或改变原 direct_answer 路由。
- 不给模型自由编写证据字段；用户恶意查询和原分析建议里的任意条号不能创建引用或人工结论。
- 检索前后目录和已持久化记录逐字节相同；人工结论仅取关闭事件，附记录 ID、revision、操作者、角色和时间。
- 工具审计不含原始查询、个人文本或隐藏思维链；仅参数键、摘要、结果数量/错误码和时间。

本地浏览器验收（browser 技能）：

- 未确认地区检索显示无依据；选择内地后得到安全条例第28条释义、官方原文链接、范围和版本日期。
- 改为境外地区立即清空旧引用，再检索仍无依据；记录状态变化同样清空旧回答，避免错用旧结论。
- 高风险安全演示记录走完六步工作流；待复查时无人工结论，关闭后显示专业复查事件，revision=6。
- 关闭 `KNOWLEDGE_ENABLED` 并重启后端后，页面无引用且显示 knowledge_disabled，保留高风险避险提示
  和已经存在的人工复查结论。
- 桌面和390×844移动视口检查通过；修正移动端标题与标签挤占问题，引用长元数据换行，无横向溢出。
- 控制台无 warning/error；测试只访问本地服务，未从页面打开外部来源。
- 临时视口已恢复，临时浏览器页关闭，本次前后端服务已停止；合成工作流数据在系统临时目录，不在仓库。

修改文件分组：

- 数据/契约：`knowledge/catalog.v1.json`、`knowledge/README.md`、`contracts/phase4_*.schema.json`。
- Agent：`agents/knowledge.py`、`agents/knowledge_answer.py`、`agents/tools/search_knowledge.py`。
- 后端：`backend/app/knowledge.py`、`backend/app/main.py`。
- 前端：`frontend/src/components/KnowledgePanel.vue`、`AppShell.vue`、`views/HomeView.vue`、`api.ts`、`types.ts`。
- 测试：`tests/test_phase4_knowledge.py`、`tests/test_phase4_api.py`、`tests/fixtures/phase4_knowledge_cases.v1.json`。
- 文档/配置：`.env.example`、`README.md`、`CONTEXT.md`、`TASKS.md`、`docs/phase4-knowledge-contract.md`、
  `docs/architecture.md`、`docs/tutorial-compliance.md`、本验证记录。

遗留风险和人工评审重点：

- 8 条释义只覆盖极小范围，词法命中不理解否定、同义或完整法律适用；固定案例全通过不是开放域召回率。
- 2026-08-30入库核对不等于专业法律复核或“截至今日完整现行法规”的保证；请专业人员确认摘编和项目适用，
  复核截止前经评审更新版本/日期。境外项目目前没有可引用材料。
- SHA-256 仅证明本次目录内容一致，不提供官方数字签名；资料维护依赖 Git 人工评审。
- 程序保证引用字段不接受模型伪造，原模型建议仍是未经事实核验的自由文本，不能当规范原文或法律意见。
  页面使用结构化演示输入，没有完整自然语言模型入口；真实模型准确率、工具选择和成本均未验收。
- 审计缓冲区在内存中，检索快照不写业务记录；不是生产级持久化证据链。
- 保留 Phase 3 的无真实身份认证、单机/单进程 Store 限制，以及 Phase 0 双机验证和专业人工验收门禁。

## 2026-08-30：Phase 5 单张图片上传与分析完成

范围与教程依据：

- 先冻结 `docs/phase5-image-contract.md`、12 个场景和严格视觉/照片索引 Schema，再实现单图路径。
- 遵循 Hello-Agents V1.0.3 第7/9/12章及 Extra09：单 Agent、一次有限调用、原生图像消息、严格输出
  校验、有限上下文、脱敏审计、人工确认；没有增加多智能体或赋予模型业务状态写权限。
- 支持 JPEG/PNG 安全上传、元数据清除、多候选人工纠正/采纳/驳回，以及同一问题的整改前后照片关联。
- 仅新增独立视觉模型配置；文字页面仍为结构化验收入口，不宣称已接通自然语言文字聊天。

Git 与配置审计：

- Phase 4 PR #12 已 squash merge，基线为 `db08fcf81cab0aca857baa24266ba4a2d1647aaf`。
- 从更新后的 main 创建 `phase5-single-image-analysis`；不在 main 开发，不自动合并 PR。
- GitHub 目标 `Arien-LY/sea-son-safety-agent` 为私人仓库；原 unborn main 启动限制已不适用。
- 经用户明确确认，仅在本地已忽略的 `.env` 新增 `VISION_MODEL=deepseek-v4-flash-vision-exp`；
  原有文字模型与密钥不变。`git check-ignore .env` 命中，`git ls-files .env` 无输出。
- 修正启动脚本没有加载 `.env` 的问题：有文件时通过 uvicorn `--env-file` 加载；已有进程环境优先。
  用户已运行的服务未被停止或重启，需要自行重启后端才会加载新配置。
- 新增必要的固定依赖 `Pillow==12.3.0`；复用既有模型 SDK，不增加 multipart、向量库或其他模型服务。

验证命令与结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_images.py tests/test_phase5_api.py tests/test_phase5_transport.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
git diff --check
git check-ignore .env
git ls-files .env
```

- Phase 5 图片、API、原生传输专项：70 tests passed。
- 完整 Python：299 tests passed，1 条既有 Hello-Agents Pydantic 弃用警告。
- TypeScript 检查与 Vite 生产构建通过：38 modules transformed。
- `git diff --check` 无空白错误；Windows LF/CRLF 提示不影响验证。
- 常规 pytest/verify 使用 Fake/Mock，`.env=real` 不会使这些测试调用真实模型；真实冒烟独立执行。

确定性门禁：

- 每次仅一张 JPEG/PNG，最多5MiB、每边4096像素、总计1600万像素；核对实际格式、完整解码，拒绝
  MIME伪造、坏图、多帧和超限。EXIF方向归一、透明铺白、重新编码，清除EXIF/GPS/ICC/文本等元数据。
- 随机 PHOTO-ID，不接受客户端路径、原文件名或外部图片URL；读取校验路径、符号链接和内容摘要。
- 索引原子替换失败不会破坏旧数据；失败时仅清理本次新增图片；并发上传、损坏索引及容量边界有回归。
- 视觉结果拒绝多余字段和伪造布尔确认；最多5个候选、20项观察；未观察到不能作为确有问题的依据。
- 低分辨率有确定性补充标记；有局限必须追问。所有候选保留不确定性、缺失字段及人工复核路由，
  高风险保留立即避险提示。Mock 明确未执行识别，不生成貌似真实的施工隐患。
- real 模式每次须确认外发才可调用；只允许已核验的官方 HTTPS 端点和视觉模型，30秒超时、零自动重试。
- 原生消息使用 user content 的 image_url/base64；JSON响应校验后才保存；不读取或记录隐藏思维链，
  错误只返回安全代码，审计不保存图片、用户上下文、原始响应或密钥。
- 采纳只生成既有待确认提案，纠正不能降低原风险/复核要求；驳回不建单；原候选与人工说明保留。
  提案生成失败不消耗候选决定，重复决定被拒绝，未确认不会创建正式工作流记录。
- 前后关联校验记录存在、角色、阶段和revision；同图不可换记录或阶段，关联不推进状态或revision。
  关闭/取消后不得追加关联；高风险关闭仍须既有专业人工复查流程。
- 模型超时、非法输出和上传失败不影响原文字提案/工作流路径。

独立真实模型冒烟（用户明确授权后执行）：

- 授权上限为2次合成图请求、每次1024输出token、总预算US$0.01；实际仅执行1次，无重试。
- 使用程序生成的512×512白底红色方块/蓝色圆形，无现场资料或个人信息；只向 DeepSeek 官方接口发送。
- 模型 `deepseek-v4-flash-vision-exp` 返回3项 observed、0个问题候选；结构校验通过，
  `preliminary_only=true`、`requires_human_review=true`。
- 实测4.48秒；prompt 1679、completion 140 tokens；按官网高峰价格保守估算US$0.000924，
  不是账户实际账单。请求前最坏情况估算US$0.003794，低于授权总预算。
- 可复现脚本 `scripts/verify-vision-live.py` 必须显式付费确认；普通验证不执行它。
- 脱敏结果、图片摘要及价格来源见 `docs/phase5-live-smoke.json`。此次仅证明连接与结构化输出，
  不能证明施工现场识别准确率、高风险召回率或专业工程判断正确。

本地浏览器验收（browser 技能）：

- 隔离端口8015/5175、临时目录 Store 与明确 Fake 视觉后端；没有使用用户现有8000/5173服务的数据。
- 未勾选上传授权不能上传；上传后显示服务器重新编码的512×512图片与元数据清除提示。
- 两个预设高风险候选：第一项修改摘要并填写说明后采纳，第二项填写说明后驳回；风险与复核要求不变。
- 采纳转入既有提案确认，补齐项目/区域后人工保存草稿；整改前照片在revision1关联，整改后照片在
  revision4关联同一记录；人工提交/派工/整改/复查后到revision6关闭，没有自动状态变化。
- 关闭后关联请求被409拒绝；据浏览器检查清除过期成功提示，并禁用关闭/取消及阶段不匹配的关联按钮。
- 390×844移动视口有效内容宽度375像素，scrollWidth同为375，无横向溢出；合成图片缩略图正常。
- real环境通过 `.env` 加载验证，页面显示独立视觉模型和逐次费用提醒；未勾选外发确认时分析按钮禁用。
  此项仍使用Fake后端，没有额外真实推理调用。
- 浏览器控制台无 warning/error；临时视口已恢复、页面已关闭，本次隔离服务均停止。
  用户原有服务未被停止，临时合成图片和工作流记录未写入仓库。

修改文件分组：

- Agent：`agents/vision.py`。
- 后端：`backend/app/photo_models.py`、`photo_store.py`、`photos.py`、`photo_routes.py`、`main.py`、
  `workflow_store.py`（仅增加持锁快照，不改冻结状态和记录Schema）。
- 前端：`frontend/src/components/ImagePanel.vue`、`AppShell.vue`、`KnowledgePanel.vue`、
  `views/HomeView.vue`、`api.ts`、`types.ts`。
- 契约/测试：`contracts/phase5_*.schema.json`、`tests/fixtures/phase5_image_cases.v1.json`、
  `tests/test_phase5_images.py`、`test_phase5_api.py`、`test_phase5_transport.py`。
- 配置/脚本：`.env.example`、`backend/requirements.txt`、`scripts/start-backend.ps1`、
  `scripts/verify-vision-live.py`；本地 `.env` 不提交。
- 文档：`README.md`、`CONTEXT.md`、`TASKS.md`、`docs/architecture.md`、`tutorial-compliance.md`、
  `phase5-image-contract.md`、`phase5-human-review.md`、`phase5-live-smoke.json`、本验证记录。

遗留风险和人工评审重点：

- 视觉模型为实验型号；固定12场景与Fake测试验证协议和边界，不是实际现场图片标注集。
  `docs/phase5-human-review.md` 的专业现场复核仍待填写，不宣称模型效果达到比赛或生产指标。
- 元数据清除不等于像素打码；人脸、工牌、铭牌和项目细节须用户自行遮盖并确认上传/外发授权。
- 无生产登录、照片所有权、真实资质、速率限制和按用户配额；不可直接暴露公网。候选自由文本仍需核验，
  单张照片不能形成最终安全、质量或责任认定。
- 工作流和照片为本地独立Store；锁仅覆盖同一Python进程，不是跨进程事务。异常进程退出仍可能留下
  未入索引的图片；上限200张/每张10份分析，无自动保留期、删除界面、备份与灾难恢复。
- 文字页面仍为结构化演示，不是自然语言真实模型聊天入口；Phase 6 的指标、比赛材料和发布验收未启动。
- 保留 Phase 0 双机全新克隆未完成、既有Pydantic警告，以及资料专业复核和生产身份安全门禁。

## 2026-08-30：产品补齐——文字入口与历史工单完成

任务和Git边界：

- 用户确认先补齐真实文字入口、受控追问、历史工单列表和详情，再开展Phase 6。
- 先冻结 `docs/product-text-records-contract.md` 的任务模板、T01–T10/R01–R06验收场景，再实现接口。
- Phase 5 PR #13已合并，基线 `ffe217b95909e55e71c6489a1e7867ac249087d0`；更新main后创建
  `product-text-and-records` 独立分支，不直接在main开发、不自动合并PR。
- 未修改.env、密钥、依赖或既有Phase1/3冻结Schema；.env仍被忽略且未跟踪。

实现与教程符合性：

- 一个临时SimpleAgent每轮一次文字调用，同时给出answer、follow_up_questions及IssueAnalysis；
  严格JSON校验后才进入内存。DeepSeek官方JSON/thinking协议已核对，30秒超时、零重试、4096输出token。
- 服务端至多200个会话，每问题最多6轮、30分钟不活跃后惰性过期；只接收用户输入，不接受伪造的
  assistant/system历史、模型配置、分析或工具参数。上轮已校验追问用于理解后续“是/不是”。
- 实际模型调用前必须逐次确认外发与费用。幂等成功重放不再次调用；失败不推进轮次、不自动重试。
- 同一问题已有high/emergency不可被后续低风险输出覆盖；保留避险要求和人工复核，后续自由回答用
  确定性保守提示替代。普通咨询/unknown不提案，信息不足转补充；不会把unknown等同于low。
- 提案只取服务端最新分析，复用既有确定性工具边界，不新增第二次模型调用。提案不自动落库，成功后
  会话冻结，避免更高风险补充与旧提案混用；确认与保存继续复用HMAC和工作流规则。
- 只读工单列表从单次Store快照检索，稳定排序、组合筛选和分页，不返回完整分析/事件。
- Vue新增文字首页、历史列表与可刷新详情；旧结构化表单折叠并标注演示。详情保留全部展示字段、分析、
  时间轨迹、知识、照片及原人工动作；使用已保存的报告人/整改人ID而非固定示例ID。
- 确认后再改字段会失效旧确认；同一次保存重试沿用幂等键；请求期间锁定操作区和应用内切换，避免交叉结果。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_product_text.py tests/test_product_records.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
git diff --check
git check-ignore .env
git ls-files .env
```

- 新增专项50 passed；完整349 passed，1条既有Hello-Agents Pydantic弃用警告。
- TypeScript和Vite生产构建通过，46 modules transformed；git diff --check无空白错误。
- 覆盖普通咨询、四类问题补充/提案/显式保存、高风险跨轮保留、非法输入、空/非法/超长输出、超时、
  脱敏错误、并发重复请求、旧轮次、过期/容量/轮次/重启、严格确认、提案失败重试及成功冻结。
- Fake SDK验证原生json_object、thinking disabled、零重试、token/timeout上限，拒绝截断/工具返回，
  隐藏思维链属性不可读取。Mock明确未执行文字理解。
- 列表覆盖空/多页、组合条件、大小写ID搜索、未知/重复/越界查询、坏Store、只读字节不变、重启读取、
  历史角色继续工作流和revision冲突；新增请求/响应Schema与Pydantic定义精确比对。

隔离浏览器验收（browser技能）：

- 临时端口8016/5176、临时Store、合成资料；runtime设real但文字注入明确标注的Fake后端，真实SDK
  构造被禁止。未使用真实.env或真实项目数据，文字/图片真实调用均为0，未沿用上轮付费授权。
- 未勾选逐次外发不能发送；普通咨询没有提案按钮；信息不足追问后给出高风险，再补充“没事了”仍保留
  high/人工复核与避险提示。未发送补充时禁用旧分析提案按钮。
- 生成提案后停止补充；确认后再改标题会隐藏保存按钮，重新确认后才可保存；保存跳转
  `/records/ISS-37056F2B345B`，刷新恢复记录及已关联合成照片。
- 该高风险记录从draft走完提交、人工派工、整改、待复查和独立专业关闭，revision=6。
- 22条合成历史记录验证20+2分页；标题与closed组合筛选得1条，刷新保留筛选；无匹配显示空状态。
- 重启隔离后端后仍能读取22条历史记录，并复测两轮文字补充；未保存会话不承诺跨重启恢复。
- 模拟超时显示安全错误、保留输入、无自动重试，历史工单仍可导航。
- 390×844下列表、文字及详情有效内容宽375、scrollWidth375，无横向溢出；桌面页首、导航及卡片检查通过。
- 浏览器控制台无warning/error；临时视口已恢复、验收页关闭，本次前后端隔离服务均停止。

修改文件分组：

- Agent/API：`agents/text_assistant.py`、`backend/app/text_models.py`、`text_consultations.py`、
  `product_routes.py`、`main.py`。
- 前端：`frontend/src/components/TextPanel.vue`、`AppShell.vue`、`ImagePanel.vue`、`views/RecordsView.vue`、
  `HomeView.vue`、`router.ts`、`api.ts`、`types.ts`。
- 契约/测试：`contracts/product_text_request.v1.schema.json`、`product_text_response.v1.schema.json`、
  `tests/test_product_text.py`、`test_product_records.py`。
- 文档：`docs/product-text-records-contract.md`、`architecture.md`、`tutorial-compliance.md`、本验证记录、
  `README.md`、`CONTEXT.md`、`TASKS.md`。

遗留限制：

- 本轮没有真实文字接口冒烟，不把Fake响应视为真实模型理解或分类正确率；首次实调、专业现场核验和
  Phase6指标需独立验收。已有图片真实记录仅为上一轮合成图连通性。
- 会话内存/单进程锁、一次一条模型请求，无流式回复或高并发调度；30分钟惰性清理不是定时物理清除。
  浏览器刷新/离开丢失未保存对话；进程重启会清除会话、幂等缓存和未保存提案凭据，不影响正式Store。
- “同一问题高风险保留”不等于识别所有危险；新会话不会自动关联旧咨询或原工单，模型自由建议仍需核验。
- 操作角色仍为演示身份，无生产鉴权、项目隔离、速率限制、数据库事务或备份；列表暴露本机Store摘要，
  不能直接公网部署。搜索词会进入URL及访问日志，请勿填写敏感个人信息。
- 继承Phase3本地Store和Phase5图片隐私/保留期限制；双机新克隆、专业资料复核、比赛材料及Phase6仍待完成。

## 2026-08-30：会话工作台前端体验重构

范围与冻结契约：

- 先新增 `docs/conversation-workbench-contract.md`，冻结信息架构、普通聊天/专业咨询/直接提交三种模式、
  状态迁移、工单出现条件及 W01–W10 桌面和移动验收场景，再修改 Vue。
- 左侧提供新建聊天、新建咨询、提交工单、最近正式工单和全部历史；主体改为消息流、空白引导、
  composer、图片/背景入口和明确发送状态。视觉采用独立中性工作台设计，不复制或冒充 Codex 品牌资产。
- 普通聊天前端永不调用提案接口；专业咨询只在服务端 `can_propose=true` 后显示生成提案；直接提交
  仍依次经过提案预览、字段核对、人工确认、HMAC 完整性和显式保存草稿。
- 没有修改 Phase 1/2/3/5 冻结 Schema、后端状态机、模型权限或高风险独立专业复查规则；没有新增
  Agent、RAG、多智能体、生产身份、数据库或依赖升级。

Git 与实现：

- PR #14 已合并到 `main`；本任务先 fast-forward 本地 `main` 到合并基线 `78fda2a`，再创建
  `feat/conversation-workbench`，没有继续修改 `product-text-and-records` 分支。
- 新增 `/chat`、`/consult`、`/submit` 路由，根路径转到专业咨询；详情与列表路由保持兼容。
- `AppShell` 增加响应式侧栏和最近工单快照；`TextPanel` 增加模式策略、消息流、键盘发送、加载/错误、
  图片与背景入口；`HomeView` 把工单链表达为三步受控流程；`RecordsView` 补齐加载、错误、空结果与移动布局。
- 新增 `scripts/run-workbench-browser-fixture.py`，只构造确定性 Fake 文字响应和临时 Store，
  不创建真实模型客户端；新增 `tests/test_frontend_workbench.py` 固定路由、侧栏、普通聊天无提案和确认链。

验证命令与结果：

```powershell
npm run build
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_workbench.py tests\test_product_text.py tests\test_product_records.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
git diff --check
```

- 工作台＋文字/历史专项：55 passed；完整 Python：354 passed，保留 1 条既有 Hello-Agents Pydantic 弃用警告。
- TypeScript 和 Vite 生产构建通过：45 modules transformed；`git diff --check` 通过。
- 全部自动验证使用本地 Fake/Mock；未读取真实 `.env`、未创建服务商客户端，文字/图片真实模型调用均为 0。

隔离浏览器验收：

- 本地端口 8000/5177、系统临时目录 Store 与明确 Fake 文字后端；没有使用真实项目或个人资料。
- 桌面空白页显示三种入口、最近工单、消息引导、图片/背景工具和 composer；普通聊天完成一轮回答，
  页面中生成提案按钮数量为 0。
- 专业咨询首轮返回信息不足和追问，生成提案按钮数量为 0；补充“三层配电箱冒火花且有人在附近”后，
  高风险、立即避险和人工复核可见，服务端允许后才出现生成待确认提案。
- 提案补齐项目/区域并确认后，再改标题使旧确认与保存按钮立即失效；重新确认后只保存 1 条正式草稿，
  自动进入详情，revision=1。侧栏同步显示该记录。
- 直接提交可生成待确认提案；未确认时最近正式工单仍为 1 条且没有保存按钮，证明未自动落库。
- 历史列表显示共 1 条记录，进入详情并刷新后标题、ID 和 revision=1 均恢复。
- “模拟加载”期间显示发送状态；“模拟错误”显示稳定 Fake 错误、未自动重试，输入值“模拟错误”保留。
- 图片入口可展开上传面板；未选择文件和勾选授权时上传按钮禁用，没有发送或上传任何图片。
- 390×844 下 `clientWidth=375`、`scrollWidth=375`，无横向溢出；移动顶栏和抽屉正常，最近工单可见。
- 浏览器控制台 warning/error 为 0；临时视口已恢复、验收页关闭，前后端临时服务已停止。

已知限制：

- 本轮是前端体验与信息架构重构，不增加流式响应、持久聊天、多会话账户隔离或生产权限。
- Fake 浏览器结果只证明交互、协议与安全边界，不证明真实模型理解、分类准确率或高风险召回率。
- 侧栏最近项只读取前 6 条正式工单；未保存会话按既有契约在刷新、过期或进程重启后丢失。
- 系统临时验收 Store 未写入仓库；生产数据库、备份、外部工单同步和 Windows 双机全新克隆仍待 Phase 6。

### 2026-08-30：首屏尺寸与视觉反馈修订

- 删除 composer 下方冗长说明、常驻“允许本次外发”标签及额外确认弹窗；右下角持续显示目标模型，
  用户每次点击发送箭头即确认该次文字外发，不形成持续授权。
- 主体与会话区改为 `100dvh` 固定首屏，消息区独立滚动，composer 不再用 sticky 叠加页面高度；桌面与移动端均无页面级溢出。
- 深蓝方格、细网格背景和方形状态符号借用中建企业形象的“方形、基石、海蓝”设计语言，不复制官方标志。
- 真实文字请求增加 35 秒浏览器等待上限；服务端仍保留原 30 秒、零重试规则，超时只恢复界面供人工重试。
- `npm run build` 通过（45 modules transformed）；专项 6 passed，完整回归 355 passed，保留 1 条既有 Pydantic 弃用警告。
- 浏览器被动验收使用当前本地服务，仅读取 runtime/健康状态，没有发送问题、图片或触发 DeepSeek 调用。
  1280×720 下页面 `scrollHeight=720`、composer 底边为 720；390×844 下 `scrollHeight=844`、composer 底边为 844。

### 2026-08-30：超宽屏、模型入口与演示登录修订

- 解除会话自身 860px 以及外层工单容器 980px 两层宽度限制；提案和结构化工单仍保留 980px 阅读宽度。
- composer 右下角增加当前服务端模型选择器。当前只能显示服务端安全配置的实际模型，不允许网页覆盖型号。
- 左下角改为本地演示登录；显示名仅保存在浏览器 localStorage，登录后显示首字头像，可退出，明确不代表生产账号、项目权限或审批资质。
- 2560×1200 下右侧可用工作区 2280px，会话/标题/composer 使用 2220px，页面无横向或纵向溢出；390×844 下 `scrollWidth=390`、composer 底边为 844，抽屉内登录入口可见。
- 浏览器完成登录、头像、退出和发送确认弹窗验收；未点击“确认并发送”，真实模型调用为 0。
- 前端专项 8 passed；完整回归 357 passed，Vue 类型检查与生产构建通过，保留 1 条既有 Pydantic 弃用警告。

### 2026-08-30：聊天延迟、乐观消息与可取消导航修订

- 根因一：原文字入口无意图区分，日常聊天也执行30秒/4096-token严格JSON风险分析。请求新增
  `intent=chat/consult`；chat改用同一DeepSeek型号的10秒/256-token轻量直答，consult保留原结构化路径。
- 根因二：`form.message`只在`await api.sendText`成功后清空。现改为请求发出前把用户消息写入消息区并清空
  composer；失败恢复原输入和同一幂等请求，成功后用服务端回答完成消息对。
- 根因三：路由守卫的`working`包含`textBusy`。现将文字等待从业务写操作守卫中移除；模式切换或组件卸载
  通过AbortController取消浏览器等待，提案确认、保存、状态推进和图片操作仍保留导航保护。
- 用户明确要求移除额外确认弹窗。右下角持续显示服务端模型；点击箭头即为该次文字外发动作，后续消息
  仍须再次点击，不形成持续授权。服务端`allow_external`门禁保留，图片授权不变。
- 2秒延迟Fake浏览器验收：聊天与咨询均在响应前显示用户气泡且输入为空；等待期间可进入`/submit`，
  加载状态随取消消失。Fake轻量聊天端到端约330ms，控制台0 error，真实模型调用为0。
- 补充复现：组件卸载时父页面仍可能保留`textBusy=true`，切换成功但工单字段继续禁用。
  Vue真实组件卸载测试先失败后通过；现在主动释放父级忙碌状态，提案生成另有导航保护。
- 再次隔离浏览器验证：聊天和咨询的2秒等待中均可进入`/submit`，问题类型输入框`enabled=true`且能填入
  测试文字。旧响应不会回填新页面，文字发送未出现额外弹窗；未保存任何工单。
- 普通8000端口用`allow_external=false`探测新`intent=chat`契约，返回预期403同意门禁，证明热重载已接受
  新接口，且未调用真实模型；不能只用OpenAPI缺少TextRequest判断版本，因为路由先接收dict再严格校验。
- 文字/工作台专项49 passed；完整回归362 passed，新增7项Node/Vue行为测试通过，Vue类型检查与生产构建
  通过，保留1条既有Pydantic弃用警告。`verify.ps1`现在同时执行前端行为测试。
- 限制：取消只终止浏览器等待，不保证服务端或供应商已取消计算/计费；服务端会话仍有6轮限制，
  模型调用在既有进程锁内串行执行。未增加流式输出，未测量真实模型响应时间或回答质量。
