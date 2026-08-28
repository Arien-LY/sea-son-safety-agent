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
