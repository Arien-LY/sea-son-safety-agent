# 验证记录

## 2026-08-31：Windows 比赛客户包

正式发布结果：

- 干净提交`d423026227390cdc6811df59164f824597724359`构建，`dirty_build=false`；标签
  `v0.1.0-beta.1`固定在该提交，本段后补文档不会改动标签或发行文件。
- 最终ZIP为45,105,575字节；4131文件散列复核、原生启动器、包内运行时、无开发工具PATH、Mock流式协议、
  安全/后勤两类闭环和重启持久恢复再次全部通过，真实模型调用0次。
- ZIP SHA256：`cb09b26afa956f13617f63f5855ef0dfff5246c7ca80bd9684fd50aa97a30e10`。
- 已上传ZIP和SHA256SUMS.txt到GitHub，重新下载文件复算散列与本地一致；2026-08-31发布为非草稿的
  prerelease，仓库仍为PRIVATE。Release：
  https://github.com/Arien-LY/sea-son-safety-agent/releases/tag/v0.1.0-beta.1 。
- 维护PR #26描述包含范围、教程依据、测试、限制和人工重点；未自动合并。

范围：基于已合并PR #25的main 4ae12d1创建`release/windows-portable-beta`；冻结
`docs/windows-release-contract.md` P01–P10。用户确认仅比赛上传，不建设生产身份或隐私平台。

实现：

- C#原生启动窗口与模型设置；内置官方CPython3.12.10 x64和41个锁定运行依赖；Vue生产页面由
  同一个FastAPI进程托管，不需要客户安装Python/Node/Git或使用终端。客户模式关闭API开发文档及教程元数据。
- 设置窗口密码遮挡、Windows当前用户DPAPI加密，密钥只进入本机子进程环境，不写URL/命令行/日志；
  不读取/复制仓库.env。软件升级与LocalAppData/SeaSon工单数据分离。
- 客户界面去掉Phase编号、HMAC、revision、内部工具函数名和英文状态；称呼不冒充真实登录。
  风险、人工确认、未启用AI提示与身份未核验限制仍保留。运行时包仅根目录EXE、使用说明、许可和内部资源。
- 内部许可保留hello-agents CC-BY-NC-SA-4.0、CPython及全部前端运行依赖许可；缺失于npm包的
  @vue/devtools-api6.6.4许可从vuejs/devtools-v6对应标签补全，来源随文件记录。不会宣称已获商业许可。

验证：

- `scripts/verify.ps1`：447项Python、35项前端行为测试、vue-tsc与Vite构建（67 modules）通过；
  保留1条既有Pydantic警告。新增pytest.ini将收集范围明确为tests，避免把release-output里的第三方测试收集进来。
- 演练包重新解压至独立Temp路径，4129文件散列核验通过；PATH不含Python/Node/Git仍成功运行。
  原生启动器与合成密钥DPAPI往返通过；同源页面、未启用AI的NDJSON流、安全/后勤两类工单均从草稿到
  revision6关闭，并重启包内服务验证持久恢复。所有模型调用0次。
- 使用Browser技能验收真实解压包（非开发服务器）：首页、你好即时入消息区、AI未启用提示、后勤申请、
  确认保存、中文详情和最近工单通过。1280宽与390×844实测scrollWidth=clientWidth；截图检查完成。
  页面无Phase/HMAC/revision/Mock/内部工具名，控制台error/warn为0。本轮为应用内浏览器，不冒称Chrome。
- 打包演练先后发现构建配置缺Node类型、上游npm缺许可文件、嵌套许可目录被误判以及Windows短路径比较问题，
  均已修复后重跑；未把这些失败记录当成功证据。最终正式产物还会在干净提交后重建并验证。

遗留：真实模型/现场效果和第二台物理电脑未验收；未签名Windows程序可能触发系统信誉提示；
官方CPython3.12.10二进制及既有依赖后续安全更新需独立维护。本包只用于比赛非商业试用，不改变仓库私有性。

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

### 2026-08-30：局域网发送卡住、真实步骤与等待时间

诊断与审计方法：按diagnose建立真实Vue组件反馈环；code-quality-workflow执行全项目分面只读扫描，
只将“文字请求生命周期”进入Local Fix门禁；先冻结`docs/chat-progress-contract.md`，不重写Agent。
基于已合并PR #15的`bb4206f`创建独立`fix/chat-progress`，未把新主题加到旧PR。

确认根因（P1）：

- 最初localhost延迟Fake可正常显示消息，但只显示静态“正在回复”；无法据此判定用户标签页版本。
- 用户指定Chrome DevTools MCP后，在用户已有局域网HTTP页面只读观察到：`isSecureContext=false`、
  `typeof crypto.randomUUID === 'undefined'`，输入仍为“你好”、等待文字仍存在。
- 代码在`busy=true`之后、try之前直接调用randomUUID；因此准备阶段抛错，输入未清空、HTTP请求尚未
  发出，finally也未执行。这不是模型正在长时间生成答案。工具连接时没有捕获历史console记录，
  不把“无历史console”当成未发生异常；缺API真实页面状态与Vue组件失败测试共同构成证据。
- 新增回归在修复前稳定失败：`'你好' !== ''`及`TypeError: crypto.randomUUID is not a function`。
  修复后，优先randomUUID，局域网HTTP改用getRandomValues生成128位ID；编号准备纳入try/finally，
  随机源失败也恢复输入、释放busy并显示安全错误，不用时间戳制造幂等键。
- 并发Fake还复现文字全局锁无限等待：第二个请求2秒未完成。现锁竞争最多1秒，繁忙明确text_busy；
  并不宣称后端变为并行模型服务，也不把此风险混称为截图直接原因。

实现与边界：

- 保留两个原JSON端点，新增文字与文字提案的`/stream`端点，输入复用严格契约。
- 服务端NDJSON进度字段只有seq、elapsed_ms、白名单stage/tool；终态为原契约result或安全error。
  工具名仅在已通过提案资格且实际调用preview工具路径时出现，普通聊天/咨询回复tool为null。
- 浏览器展示“已等待N秒”、真实阶段和可展开步骤；完成后保留用时及步骤。计时器只算时间，
  不定时编造“思考/检索/派单”，不泄漏隐藏思维链。模型仍在完整结果通过校验后才展示回答。
- 客户端校验递增序列、时间及工具/阶段对应，限制总字节262144与16事件；UTF-8分块正确解码。
  断流、非法事件、超时明确失败；不自动降级重新调用付费接口。35秒截止覆盖连接与正文读取。
- DevTools发现一次成功消费result后立即cancel reader会把网络标成ERR_ABORTED；已改为读至EOF后
  正常完成，并加入成功流不调用cancel的回归，修后网络响应正文可完整观察。
- runtime徽标改为“模型已配置/Mock已配置”，不再暗示凭据已实调验证；runtime读取5秒截止。
- 模式切换/卸载释放计时器、监听与等待；晚到进度和回答不回填新会话。取消不保证供应商停止计算/计费。

验证：

- 修改前文字/工作台专项49 passed；原前端7项通过。新增缺随机API/准备错误2项先失败后通过。
- 新增Python5项涵盖事件顺序、幂等无重复模型、错误脱敏、锁队列上限、提案工具及原确认资格。
- 最终`powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`：367 passed，1条既有
  Hello-Agents Pydantic弃用警告；前端21项行为测试通过；vue-tsc/Vite构建通过（45 modules）。
- 前端覆盖非安全上下文、准备异常、发送即显、失败复用请求ID、卸载/模式切换、计时停止、晚到事件，
  以及UTF-8单字节分块、断流/非法事件/伪工具/乱序/负时间/未知步骤、错误事件和正文超时。
- git diff --check及完整默认视图范围检查通过；预算16文件/1100行，不包含依赖、.env或业务状态Schema。

Chrome DevTools MCP隔离浏览器：

- 使用临时Store、8018 Fake后端与5178前端，局域网HTTP复制原故障条件；实际调用真实模型0次。
  用户原5173/8000服务未停止，.env未读取/修改；原端点OpenAPI只读检查确认热重载已包含stream路由。
- 同样`randomUUID=undefined`时，“你好，模拟加载”立即成为用户气泡，composer为空；等待先显示
  model_running、随后显示已等待1/2/3秒。4秒Fake响应后显示用时4秒，无业务工具调用。
- DevTools网络记录显示约3ms取得头、约4010ms完成（一次Fake样本）；正文依次含queued、preparing、
  model_running、validating、completed、result。该数据不代表DeepSeek真实性能。
- 专业咨询首轮信息不足不建单；补充合成高风险后出现提案；人工点击产生tool_running /
  propose_issue_record，随后展示待确认提案和“尚未保存”。未创建正式工单。
- 390×844模拟设备下clientWidth/scrollWidth均为390；等待、消息和composer可见，切换/提交入口可用。
  初次窗口resize受浏览器缩放影响测得502宽，未将其当作390验收；改用明确设备模拟后重新验收。
- Fake错误显示安全错误码并恢复原输入，busy=false；控制台无error/warn。
- 最终范围检查：16文件、678行变化（检查时）；无未知二进制、无预算警告。隔离浏览器页面已关闭，
  8018/5178验收进程已停止；原用户页面保留，未在其中发送真实消息。

全项目扫描的其余发现（既有P2、独立待办，本补丁不修）：

| 位置 | 可复现实证 | 后续门禁 |
|---|---|---|
| backend/app/workflow_models.py:188；frontend/src/views/HomeView.vue:458 | note允许2000字；request_more_info的501字和close的1001字实测500，保存字段分别只允500/1000字 | 按动作验证上限并同步UI，不能静默截断 |
| backend/app/proposals.py:42 | 旧确认接口confirmed:1实测200并user_confirmed=true；不等于绕过生产身份认证 | 精确布尔验证与回归 |
| backend/app/photos.py:70/79、123/134；photo_store.py:118 | 阻塞Fake证实视觉调用持全库锁时图片读取等待；关联先持workflow锁再等photo锁可扩大影响 | 独立缩短锁范围并验证照片结果提交一致性 |

非文字后台独立检查168项相关pytest通过；没有发现需重写整个后台的证据，没有做无关删减。
生产鉴权、照片所有权、跨进程锁、专业现场评估和真实模型性能依旧未验收，不能把本次扫描说成完整上线审计。

修改文件：backend/app/{product_routes.py,text_consultations.py,text_progress.py}；
frontend/src/{api.ts,types.ts,styles.css,components/TextPanel.vue}；
frontend/tests/{api.test.cjs,text-panel.test.cjs}；tests/{test_chat_progress.py,test_frontend_workbench.py}；
scripts/run-workbench-browser-fixture.py；docs/{chat-progress-contract.md,architecture.md,verification.md}；TASKS.md。

## 2026-08-30：极简消息与普通聊天提示词修订

范围与基线：`style/minimal-chat`基于9d87720 / `fix/chat-progress`，PR #16仍未合并；
本主题冻结在会话工作台契约M01–M06，不重写Agent、不改专业咨询JSON或工单权限。

提示词诊断与限制：

- 用户截图提供了重复“中文日常问答助手”和自称“DeepSeek最新版”的实际样本。
- 排查顺序为system角色称呼、上轮回答延续、前端固定拼接；代码排除前端拼接。
  Fake SDK捕获实际answer_brief请求，确认旧system确有该称呼且未提供模型标识，last_answer亦带入旧回答。
- 按diagnose建立请求边界回归；修前两个模型参数案例及两个布局契约检查失败（4 failed / 48 passed），
  修后52 passed。该反馈环验证请求构造和布局约束，不声称复现真实模型生成的概率或建立完整因果实验。
- 新CHAT_SYSTEM_PROMPT禁止主动自我介绍/规则复述，不沿用历史中的型号猜测；日期和模型标识由服务端追加，
  用户陈述与上轮回答仍只放在user资料。没有以删词、关键词应答或前端替换的方式篡改模型输出。
- 保留无工具、10秒超时、256输出token、零重试与原安全边界；没有读取/修改.env、模型配置或任何密钥。

界面与Chrome DevTools验收：

- 取消消息头像、助手标题、轮数和会话网格背景；用户气泡靠右、助手正文靠左；保留无视觉噪声的可访问消息分组。
- “用时N秒”是默认折叠的原生details入口，展开后显示实际服务端步骤、工具和Mock说明。
  等待仍显示实际经过时间与服务端阶段；仅真正调用业务工具时单独显示工具名，没有伪造思考过程。
- 使用独立临时Store、8018 Fake服务和5178前端；用户原5173/8000服务未停止，未在real页面发送消息。
- 桌面CSS视口2048×962：延迟Fake发送后输入立即为空、pending气泡立即靠右，头像数量0；
  4秒后显示用时4秒，展开可见queued/preparing/model_running/validating/completed对应文案。
  连续两轮用户消息全部靠右、助手左对齐，所有历史步骤默认折叠，无横向溢出。
- 390×844设备模拟：较长中文消息换行且靠右，clientWidth/scrollWidth均390；时间折叠项可点击展开。
  4秒为人为Fake延迟，不能代表真实供应商速度；移动消息/输入框截图已人工检查。
- 专业咨询Fake错误恢复原输入，发送按钮重新可用；合成高风险回复仍显示必须人工复核和立即避险。
  人工点击提案后出现propose_issue_record已完成/尚未保存提示及确认界面，没有创建正式工单。
- 验收页控制台无error/warn；文字和提案流HTTP200，错误场景仍通过流内error事件明确失败。

验证结果：`scripts/verify.ps1`通过，370项Python、21项前端行为测试、vue-tsc/Vite构建（45 modules）；
1条既有Hello-Agents/Pydantic弃用警告；git diff --check通过。真实文字/图片模型调用均0次。

修改文件：agents/text_assistant.py；frontend/src/{components/TextPanel.vue,styles.css}；
tests/{test_product_text.py,test_frontend_workbench.py}；docs/{conversation-workbench-contract.md,
chat-prompt-guide.md,verification.md}；TASKS.md；README.md。

遗留风险：真实模型可能仍重复或幻觉；型号标识是程序配置而非供应商内部运行版本证明。生产鉴权、
现场效果与此前三项独立P2不在本修订范围。提示词编辑后的新会话比较、重载丢失未保存上下文、
Mock不执行真实提示词等注意事项已写入编辑指南。PR依赖#16，未自动合并。

收尾：本轮创建的隔离浏览器页已关闭，8018/5178验收服务已停止；原用户页面和服务保持不变。

## 2026-08-30：普通聊天重复回答的逐轮上下文修复

基线dc6216c，独立分支`fix/chat-turn-history`，依赖仍开放的PR #17。
实现前冻结`docs/chat-turn-history-contract.md`（H01–H06）。本轮不改前端视觉、公共Schema或工单流程。

依据与复现：

- 复用紧邻诊断轮的Chrome DevTools只读证据：用户三轮“你是谁→今天几号了→围栏断裂”，对应三次POST；
  第三轮原始result.answer已经包含身份和日期，DOM与接口一致，排除重复发送与前端拼接。
- 离线捕获answer_brief确认：只有system/user两条消息，user内有全部user_statements和last_answer。
  上轮只约束语气的修订未改该结构，不能消除旧问题被当成本轮输入的诱因。
- diagnose回归走HTTP（JSON和NDJSON）→真实服务与适配器→Fake SDK，逐轮捕获消息，而非只检查提示词字串。
  测试开发时曾误将错误码视为顶层字段；按既有detail.error_code协议修正测试后，修前稳定14 failed /
  5 passed；第三轮得到2条消息而非6条，非法历史也未在外发前拒绝。未将测试自身错误算作产品故障。

实现：

- chat改为system、逐轮user/assistant、最后一条当前user；每个user是独立TextConsultationInput的JSON，
  保留背景标签。历史assistant只含成功回复answer，不含analysis或隐藏推理，仍不成为系统指令。
- 从既有session.responses按turn读取答案，与inputs配对；不新增历史存储。失败不提交历史，幂等重放
  直接返回原响应；最大6轮/12条消息。历史数量不符、空/非字符串/超长答案在构造SDK客户端前拒绝。
- system明确只回答最新user，相关指代/明确回顾仍可使用历史；不通过删词或强制固定答案掩盖模型行为。
- consult的累计事实/上轮追问、高风险保留和人工确认不变；chat仍无工具/无提案权限，10秒/256token/零重试。
- 更新提示词指南、产品契约、教程映射、架构和README，说明历史答案也会作为上下文发送。

验证：

- 新增19项：三轮JSON/NDJSON角色与当前问题、代词追问及伪role标签、失败重试/旧新幂等重放、会话隔离、
  6轮上限、伪造客户端历史拒绝、9类非法历史，以及空/超长/截断/工具/超时结果处理。
- `pytest tests/test_chat_turn_history.py tests/test_product_text.py tests/test_chat_progress.py -q`：65 passed。
- `scripts/verify.ps1`：389 passed，1条既有Hello-Agents/Pydantic弃用警告；21项前端行为测试和
  vue-tsc/Vite生产构建（45 modules）通过；git diff --check通过。
- Fake答案只验证透传和历史配对，不将预设“无重复”文本当作真实模型质量证据。本轮未新发浏览器模型请求，
  未读取/修改.env或密钥；真实文字/图片模型调用均0次，也未启动额外后台服务。

遗留与人工验证：需在后端重载后清空旧问题，主动重新发送固定三轮检查真实重复行为；不承诺所有生成
完全无重复。历史最多增加4条更早答案，相比旧结构可能增加输入成本/耗时（未实测），仍有6轮与每条
1000字上限。重载丢失未保存会话的既有规则不变；生产身份、现场评估及此前三项P2仍为独立待办。

修改文件：agents/text_assistant.py；backend/app/text_consultations.py；
tests/{test_chat_turn_history.py,test_product_text.py}；docs/{chat-turn-history-contract.md,chat-prompt-guide.md,
product-text-records-contract.md,architecture.md,tutorial-compliance.md,verification.md}；TASKS.md；README.md。

## 2026-08-31：普通聊天深度思考与容量升级

基线：main 09b4f62（此前PR #16/#17/#18已合并），独立分支feat/expanded-chat。
先冻结docs/deep-chat-contract.md D01–D07，再实现；依据Hello-Agents V1.0.3第7/9/12章和Extra09。

原限制与变化：

- 代码原先关闭思考，只有256输出token、10秒模型等待、1000字输入/答案、6轮；这限制了复杂聊天能力。
  本轮不是声称“每次快答都没有思考”，而是移除已证实的快捷短答配置限制。
- 普通chat使用thinking enabled/reasoning_effort high、32768token、180秒SDK/190秒页面截止。
  预算不要求写满，简单问题仍可快速回答；专业consult的disabled/4096/30秒和风险规则不变。
- 新ChatInput/ChatReply、产品v2快照支持16000字输入、64000字最终答案、50轮；不改Phase1/3/v1冻结文件。
- 只向模型发送最近最多12对完整历史且正文≤120000字，当前输入始终保留；context_trimmed向页面说明省略。
  每次调用前累计会话输入/答案加当前输入≤400000字，已生成答案照常保存；超过后下一轮拒绝，旧请求重放仍成功。
- 非空预算截断答案保留并明确提示可继续；无最终答案、超长、意外工具和超时仍失败，零自动重试。
  只读content，测试用reasoning_content访问即报错的Fake对象证明没有读取隐藏推理。
- 停止等待恢复原输入及请求ID，晚到回调不回填；外层表单只按业务操作禁用，内部业务fieldset仍按所有忙碌状态禁用。
  Chrome首次验收发现旧外层fieldset连停止按钮也禁用，已修复并补布局契约回归；单组件测试不能替代真实DOM验收。

验证证据：

- 适配旧限制的测试最初11 failed/54 passed，属于新契约替代旧容量断言；同步契约并新增10项D系列后，
  `pytest tests/test_product_text.py tests/test_chat_turn_history.py tests/test_chat_progress.py tests/test_deep_chat.py -q`：75 passed。
- D系列覆盖16000字输入/56000字答案的JSON与NDJSON透传、专业咨询拒绝超长、64000字截断末尾提示、
  字符容量裁剪与最新输入、累计会话超限仍可重放、v1原界限不变。原逐轮测试升级为50轮/51轮拒绝。
- 前端新增4项行为回归：190/35秒正文截止、64000个中文字符流解码、停止等待/原ID重试与晚到响应、按intent输入限制。
- 最终`scripts/verify.ps1`：400 passed；25项Node行为测试、vue-tsc与Vite生产构建（45 modules）通过。
  保留1条既有Hello-Agents/Pydantic弃用警告；git diff --check通过。
- Chrome DevTools使用隔离Mock/Fake临时Store（8018/5178），未在real服务发送消息。
  桌面1146像素宽：停止按钮可点、输入恢复；稍后手动重试获得已完成的幂等答案；
  2006字输入和6448字回复完整显示、头像0、scrollWidth=clientWidth=1146。
- 同一浏览器会话连续14轮成功，第14轮显示“本轮仅参考最近的部分对话”，旧消息仍在页面。
  390×844设备模拟：6448字回答正常换行、输入框仍在视口内，scrollWidth=clientWidth=390；截图已检查。
  手机页控制台无error/warn，文字流HTTP200。模拟4秒延迟不代表真实推理速度。

遗留风险和人工确认：

- 本轮真实文字/图片调用0次，未读取/修改.env或密钥；官方参数核对来源写在任务契约。
  协议通过不等于真实质量、延迟或成本通过；更大预算可能增加时间和费用，不保证与商业聊天网页全部功能一致。
- 当前仍最终答案一次显示，不逐token输出、不显示隐藏推理、不提供普通聊天业务工具。
  页面停止等待不保证服务端或供应商停算/停费；SDK timeout也不是严格的总计费上限。
- 既有服务使用单进程全局文字锁，长请求期间其他文字请求可能收到text_busy；生产并发优化需独立任务。
- 最近历史会省略，30分钟惰性过期、刷新/重启丢失未保存会话的规则不变；专业现场评估、生产身份和此前3项P2仍待办。

修改文件：agents/{chat_settings.py,text_assistant.py}；backend/app/{text_models.py,text_consultations.py}；
contracts/product_text_{request,response}.v2.schema.json；frontend/src/{api.ts,types.ts,components/TextPanel.vue,views/HomeView.vue}；
frontend/tests/{api.test.cjs,text-panel.test.cjs}；tests/{test_deep_chat.py,test_chat_turn_history.py,test_product_text.py,test_frontend_workbench.py}；
scripts/run-workbench-browser-fixture.py；docs/{deep-chat-contract.md,chat-prompt-guide.md,chat-turn-history-contract.md,
product-text-records-contract.md,architecture.md,tutorial-compliance.md,verification.md}；TASKS.md；README.md。

收尾：加上工作台契约的最终专项87 passed；本次隔离浏览器页和8018/5178进程已关闭，原8000/5173服务未停止。

## 2026-08-31：工作流动作说明长度预校验

范围与门禁：`fix/workflow-note-validation`基于已合并PR #20的main 6075169。按代码质量工作流选择
`Local Fix` / `Local Fix Only`；行为契约先写入TASKS。本任务只改变过长动作说明的拒绝时点和错误类型，
不改状态迁移、角色权限、Store字段、API成功响应、前端、依赖或模型配置。

审计结论与失败基线：

- TASKS原列3项P2；`confirmed: 1`在main已经由严格Pydantic和`test_chat_progress.py`拒绝为400，
  属于过期待办，已同步勾选，不重复修改。
- `WorkflowTransitionRequest.note`统一允许2000字，但request_more_info和supplement_information最终字段为500字，
  reject_review和close最终字段为1000字。请求校验与持久字段契约矛盾，可能在状态更新时变成500。
- 新API回归在不存在的合成record_id上先检查请求边界：精确上限通过解析后为404，超1字必须在读取记录前400。
  修复前9项Phase3 API中4项失败、5项通过，精确定位为上述4个动作；2000字动作原行为正确。

实现与验证：

- `WorkflowTransitionRequest`按目标字段增加确定性上限：请求补充/补充信息500，驳回/关闭1000，
  提交整改/取消2000。空值要求、角色、状态和通用2000字上限不变。
- 专项`pytest tests/test_phase3_api.py tests/test_phase3_contract.py tests/test_phase3_workflow.py -q`：24 passed。
- `scripts/verify.ps1`：407项Python、30项前端行为测试、vue-tsc和Vite生产构建（66 modules）通过；
  保留1条既有Hello-Agents/Pydantic弃用警告。无外部或付费模型调用。
- 原local-fix默认2文件预算因仓库强制TASKS记录产生1条文件数警告；任务门禁预先声明自定义4文件/120行。
  最终在写验证记录前为3文件59行、无未知文件；完成记录后重新执行最终范围门禁。

遗留：前端仍显示通用2000字计数，超出动作上限会得到明确API错误但不按动作提前提示；这是独立体验改进，
不影响服务端安全边界。PhotoStore视觉调用持锁、Phase6真实指标/双机/演示发布材料及Phase0队员复现仍待完成。

## 2026-08-31：聊天阅读与 Markdown 安全重构

范围与契约：

- 基线为已合并 PR #19 的 `origin/main`（a9d6b20）；从最新主线创建独立
  `style/readable-chat-workbench`，没有覆盖深度思考、长回复、16000字输入、50轮、停止等待或上下文裁剪。
- 实现前冻结 `docs/chat-visual-contract.md` 的 V01–V10 / S01–S06；不改 `.env`、密钥、
  `CHAT_SYSTEM_PROMPT`、DeepSeek运行时、专业咨询Schema、工单权限、状态机或人工确认。
- 核对OpenAI官方文章和公开仓库：Codex开源harness/仓库为Apache-2.0，核心是对话状态、工具、审批、
  沙箱和执行事件，不符合本次Vue消息呈现范围；未复制Codex App未公开UI、品牌资源、提示词或隐藏提示词，
  未引入CLI、App Server、SDK、Shell、权限或工具系统，只参考截图的通用排版关系。

实现与安全：

- 页头、消息、执行状态和composer共享约860px阅读轴；助手正文使用中文系统字体栈、17px/1.78行高，
  无头像、名称、卡片、底色或阴影。用户消息保持右侧16px浅灰气泡；composer为底部圆角浮动面板。
- 新增`markdown-it` 15.0.1（MIT）唯一直接运行时依赖，用于CommonMark标题、粗体、段落、列表、引用、
  行内代码、代码块、表格和链接；不增加语法高亮或其它重量级插件。
- `html:false`关闭原始HTML；链接进一步只允许`http:`、`https:`、`mailto:`，外部链接固定
  `target=_blank`及`rel="noopener noreferrer"`；远程图片只显示转义后的alt文本，不发起资源请求。
- 新增5项Markdown/XSS测试，覆盖脚本/iframe/事件属性、危险及混淆协议、协议相对/相对URL、
  属性逃逸、远程图片、换行、代码和安全链接。完整MIT归属见`THIRD_PARTY_NOTICES.md`；运行时传递依赖
  的许可证标识保留在lockfile（PSF-2.0、BSD-2-Clause、MIT）。

自动验证：

- `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1`：401 passed；保留1条既有
  Hello-Agents/Pydantic弃用警告。新增1项Python源契约检查，原400项基线不回退。
- `npm test --prefix frontend`：30 passed（原25项行为 + 5项Markdown/XSS）。
- `vue-tsc -b`与Vite生产构建通过：66 modules transformed；`git diff --check`通过。
- `npm ls markdown-it --depth=1`确认15.0.1。npm官方审计报告2项既有工具链告警：
  `postcss@8.5.22`（moderate）与其`nanoid@3.3.16`（high）；两版本均已存在于基线lockfile，
  不来自markdown-it依赖链。本主题不夹带依赖升级，后续应单独评估修复。

隔离浏览器（本地Mock/Fake，8018/5178）：

- 1280×720实测header/composer宽860px；助手正文17px、行高30.26px（1.78），透明无卡片背景；
  用户气泡16px、浅灰`rgb(241,241,241)`且靠右。页面`clientWidth=scrollWidth=1280`。
- Fake Markdown回答实际生成标题、粗体、列表、行内/块代码及安全链接；`window.fixtureXss`未定义，
  `.markdown-body script`与`img`数量均为0，安全链接具备目标和rel属性，远程图片未加载。
- 专业咨询首轮信息不足时提案按钮0个；补充合成高风险后按钮1个，并继续显示必须人工复核、立即避险、
  追问、分析详情和知识区。未点击生成提案，未创建正式工单。
- 390×844长回答下文档`clientWidth=scrollWidth=390`，message-stage内部滚动，代码块自身无溢出，
  composer底边为844；侧栏保持移动抽屉。控制台warning/error为0。
- 真实文字/图片模型调用0次；没有读取/修改`.env`或密钥。隔离浏览器和两个服务已停止；验收临时目录为空。

已知限制：模型不一定总输出规范Markdown；无语法高亮、复制按钮、逐token流式显示或持久聊天。
停止等待仍不保证供应商停止计算/计费；真实回答质量、延迟、费用、现场专业判断和生产身份仍需独立验收。

修改文件：`frontend/package{,-lock}.json`、`frontend/src/{markdown.ts,styles.css}`、
`frontend/src/components/TextPanel.vue`、`frontend/tests/{markdown,text-panel}.test.cjs`、
`tests/test_frontend_workbench.py`、`scripts/run-workbench-browser-fixture.py`、`docs/chat-visual-contract.md`、
`THIRD_PARTY_NOTICES.md`、`TASKS.md`、`README.md`、`docs/verification.md`。

## 2026-08-31：PhotoStore 视觉调用锁范围修复

范围与失败基线：

- 分支 `fix/photo-store-lock-scope` 基于已合并 PR #21 的 `main`（a7e0503）。契约先冻结于
  `TASKS.md`；不改视觉 Prompt/Schema、供应商配置、授权、人工候选确认、工作流或前端。
- 旧实现从 `PhotoStore.mutate` 回调内执行视觉 Fake；阻塞 Fake 未释放时，同库 `read` 在
  0.5 秒确定性门限内超时。该单测修复前失败，证明模型等待持有了全库锁。

实现与边界：

- PhotoStore 为每个已存在图片提供共享逐图分析锁；模型调用只持有该图片锁，不持有全库索引锁。
- 分析前在逐图锁内重新读取图片并检查每图 10 次上限；模型成功后只在原子写入阶段短暂持有全库锁，
  写入回调再次防御性检查上限。模型失败仍不保存分析。
- 逐图锁以存储根目录共享，因此同进程内多个 `PhotoStore` 实例也不能并发分析同一图片；本地容量
  最多 200 张，锁表同样有界。该机制不宣称提供跨进程分布式锁。

验证：

- 修复前：`test_slow_vision_call_does_not_block_photo_reads` 为 1 failed，读取抛出
  `concurrent.futures.TimeoutError`。
- Phase 5 专项：`pytest tests/test_phase5_images.py tests/test_phase5_api.py -q` 为 68 passed。
- 完整 `scripts/verify.ps1`：409 项 Python、30 项 Node 前端行为测试、`vue-tsc` 和 Vite 生产构建
  （66 modules）全部通过；保留 1 条既有 Hello-Agents/Pydantic 弃用警告。
- `git diff --check` 通过；所有模型响应均来自 Fake/Mock，真实或付费模型调用 0 次。

遗留：真实视觉供应商延迟、多进程/多主机并发与生产级共享锁仍需独立压测和部署设计。Phase 6
指标、可复现 Trace、双机安装/全流程浏览器验收与演示发布材料在后续独立主题中完成。
## 2026-08-31：Phase 6 离线评估与脱敏 Trace

范围与契约：

- 分支`feat/phase6-evaluation-traces`基于已合并PR #21的main（a7e0503）；与并行PR #22的
  PhotoStore锁修复相互独立。先在`TASKS.md`与`docs/phase6-evaluation-contract.md`冻结口径。
- 只新增纯离线评估模型、计算器、显式路径CLI、合成协议fixture和报告；不改Agent、Prompt、模型、
  API、前端、工作流、知识库、`.env`或密钥，普通验证不联网。

数据与安全边界：

- 冻结单案例Trace、20案例运行及报告3份JSON Schema，全部Pydantic strict/`extra=forbid`。
  Trace只允许案例ID、输入SHA-256、枚举裁决、要点key、计数、usage及单调阶段事件；没有原始输入、
  模型回答、Prompt、请求头、任意metadata或隐藏推理字段。
- 运行必须恰好覆盖20个冻结ID；摘要不匹配、案例重复/缺失、未知要点、事件乱序、成功/失败终态矛盾
  均失败关闭。Token与费用必须每个案例都有供应商数据才测量，否则为`not_measured`。
- 成功合成回放为20/20；失败回放把首个高风险案例保存为`model_timeout`，报告得到高风险召回
  6/7、1次高风险漏报并`overall_passed=false`，证明失败没有被静默排除。

指标结果与限制：

- 合成协议报告：分类20/20、必需要点70/70、高风险7/7、路由20/20、工具20/20；四项安全计数0，
  失败率0/20。`overall_passed=true`只表示评估协议基线通过。
- 合成事件时间报告p50=22ms、p95=31ms、max=32ms；这是fixture值，不是供应商性能。
  Token、费用和任务闭环率因无真实usage/账单/闭环裁决均为`not_measured`。
- 报告`run_kind=synthetic_protocol`且包含中文限制，不能宣传为真实模型准确率或专业工程结论。

自动验证：

- Phase 6与原20案例专项：15 passed；覆盖Schema快照、成功/失败报告、摘要/要点伪造、重复案例、
  多余原始输出字段、事件矛盾、完整usage/费用/闭环计算和CLI逐字节确定性。
- 原分支`scripts/verify.ps1`为414项Python；重放到已合并PR #22的main后复验为416项Python、
  30项前端行为测试、`vue-tsc`与Vite生产构建（66 modules）全部通过；保留1条既有
  Hello-Agents/Pydantic弃用警告。真实/付费模型调用0次。

遗留：真实模型20案例运行需要明确费用授权和专业标注；另一台物理Windows电脑安装、浏览器全流程、
演示脚本和比赛展示材料仍在后续独立发布主题完成。

## 2026-08-31：Phase 6 发布验收包

范围：分支`docs/phase6-release-kit`叠加评估PR #23，后续PR以main为目标并明确依赖；只新增发布文档、
全新克隆验证脚本和文档静态检查，不改Agent、Prompt、模型、API、前端、Schema、工作流、依赖或`.env`。

已完成：

- 新增约8分钟演示脚本、比赛8页展示提纲、集中已知限制/上线门禁、双机及浏览器发布验收表；README
  提供统一入口。宣传数字明确限定为`synthetic_protocol`，列出禁止使用的真实准确率/自动归责/生产上线表述。
- `verify-clean-clone.ps1`只接受显式仓库和分支，在系统临时目录创建带GUID的有界路径；克隆后拒绝
  `.env`、`uploads/`或`data/*.json`，执行setup+verify，成功时仅清理再次验证过的临时目标，失败保留现场。
- Windows 11专业版10.0.26200、Python3.12.10、Node24.13.0、Git2.53.0上从本地显式分支全新克隆
  e452fc7；全新安装成功，414项Python、30项前端行为测试和生产构建通过；密钥/运行数据均未复制，
  临时克隆成功清理。这证明当前一台开发机，不等于第二位队员电脑。
- 发布包提交50eb259随后再次从同一显式分支全新克隆，精确commit为
  50eb25900b75bf14abfeaaa238d9b8f7722d347a；417项Python、30项前端行为测试及构建通过，
  `env_copied=false`、`runtime_data_copied=false`，临时克隆由脚本安全清理。
- 发布材料专项3 passed；发布分支重放到已合并PR #22且包含评估PR #23后，组合工作区
  `scripts/verify.ps1`为419项Python、30项前端行为测试、`vue-tsc`与Vite生产构建（66 modules）
  通过，保留1条既有Pydantic弃用警告。该419项结果不是全新克隆；精确全新克隆证据仍为上方
  50eb259的417项。付费模型调用0次。

浏览器阻塞证据：

- Chrome正在运行，原生消息主机配置正常，但选中Profile 4没有ChatGPT/Codex浏览器扩展。
- 用户随后明确允许Chrome DevTools MCP；隔离Fake后端/前端在8018/5178正常启动，但DevTools MCP的
  “新建页面”和“列出页面”最小调用均持续无响应并被终止。未使用别的结果冒充本轮Chrome全流程通过。
- 隔离服务已停止；两个为空的验收临时目录因当前命令策略拒绝删除而保留在系统Temp，不含模型、用户或
  业务数据。该清理限制不影响仓库，但应由环境维护时移除。

仍未完成：另一位队员在另一台物理Windows电脑执行并签字；当前机Chrome桌面/390×844全流程；
真实模型与现场专业验收。`TASKS.md`的双机/浏览器总项保持未勾选。

## 2026-08-31：统一聊天、AI 工单交接与安全流式输出

范围与契约：

- 独立分支`feat/unified-chat-ticket-streaming`基于已合并Phase 6发布PR #24；契约见
  `docs/unified-chat-routing-contract.md` U01–U08。合并“新建聊天/新建咨询”，旧`/consult`仅兼容跳转。
- 新增产品文字请求v3：`intent=auto`和可选模型标识。旧v1/v2快照不改；模型仍只调用一次并返回严格
  `ChatReply/IssueAnalysis`，保留180秒、32768 token、64000字答案和有界上下文预算。
- `can_propose=true`且类别属于安全/质量/管理/后勤时，前端把服务端已校验分析交接到
  `/submit?source=ai`并锁定分析字段。该导航不调用提案工具、不确认、不落库、不派工；后续仍须人工生成、
  核对、确认和保存。Fake后勤案例证明协议路径，不声称真实模型必然正确分类。
- NDJSON在完整结构化结果通过Schema和安全边界后发送`responding`及最多120个有序
  `content_delta`；拼接文字必须等于最终`result.reply.answer`。这是真实的逐段页面展示，不是供应商原始
  token直通，也不改善模型首字等待；没有输出未完成JSON、隐藏reasoning或随后可能被覆盖的未校验文字。
- `/api/text/runtime`只公开建议型号和是否允许自定义；页面可选`LLM_MODEL_OPTIONS`或填写合法DeepSeek
  model ID。浏览器不能覆盖密钥、官方HTTPS端点、超时、重试、Schema或业务权限；Mock不可自定义。

自动验证：

- `scripts/verify.ps1`：426项Python全部通过；35项实际Vue/API/Markdown前端行为测试通过；
  `vue-tsc`与Vite生产构建（66 modules）通过。保留1条既有Pydantic弃用警告。
- 专项覆盖统一长输入/严格model ID、后勤路由无副作用、深度JSON传输预算、运行信息脱敏、delta重建、
  索引/大小/断流失败关闭、自动工单交接、模型切换、旧契约兼容及人工确认边界。
- `.env`和真实密钥未读取或修改；仅更新`.env.example`说明。真实/付费文字及图片模型调用0次。

Chrome与外部门禁：

- 隔离Mock后端/前端在8020/5180启动，`/chat`返回HTTP 200，文字runtime仅返回Mock配置；服务随后停止。
- 按用户指定连接Chrome：Chrome进程正在运行，原生消息主机清单与注册表正确；但选中Profile 4的
  ChatGPT浏览器扩展`installed=false`、`enabled=false`，浏览器运行时返回`Browser is not available: chrome`。
  因此桌面和390×844本轮未冒充通过。安装并启用扩展后须重跑U01–U08。
- 自定义模型是否存在、真实分类/回答质量、首字等待、费用，以及现场专业结论仍需用户授权的真实抽样；
  第二台物理Windows电脑验收仍是全项目独立发布门禁。
