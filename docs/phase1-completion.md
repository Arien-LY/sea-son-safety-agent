# Phase 1 安全边界与完成验收

## 任务边界

目标：完成 Phase 1 最后三项，实现信息不足和高风险输出的确定性安全门禁，并用本地 Fake LLM
覆盖成功与失败路径，最后让 20 条冻结文字案例全部通过同一结构化分析边界。

教程依据：Hello-Agents V1.0.3 第 4 章单 Agent 范式、第 7 章结构化输出与错误处理，以及第 12 章
固定案例、安全指标和可复现评估原则。

当前行为：`IssueAnalyzer` 仍是无工具、无共享历史的单 Agent 边界。模型输出必须通过严格
`IssueAnalysis` 解析和跨字段校验；测试全部使用本地预设 Fake LLM，不创建真实模型客户端。

验收条件：信息不足时列出缺失字段和不确定性；不把猜测写入已观察事实；高风险和紧急风险必须给出
立即避险提示、标记人工复核并路由人工复核；Fake LLM 覆盖正常、空输入、非法 JSON、超时和模型
错误；20 条固定案例逐条通过类别、风险区间、路由、人工复核、要点和无副作用协议检查。

允许修改：结构化分析提示、`IssueAnalysis` 跨字段校验、Fake LLM 和固定案例协议测试、领域词汇、
架构、任务与验证文档。

禁止修改：真实 Agent 能力扩展、真实或付费模型调用、API、前端、Function Calling、任务工作流、
持久化、RAG、图片上传和多智能体。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analysis_safety_boundaries.py tests/test_phase1_fake_llm_matrix.py tests/test_phase1_fixed_case_matrix.py tests/test_analysis_categories.py tests/test_analysis_risk_levels.py tests/test_issue_analysis_output.py tests/test_agent_contract.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：安全、质量、管理和后勤代表逐条复核固定案例的业务归口、风险区间、补充问题和避险措辞；
确认禁止行为完整且不会诱导无资质人员操作；真实模型冒烟必须在明确授权、单独记录且不混入本次离线
结果的前提下执行。

## 确定性安全规则

- `missing_fields` 非空时，`uncertainties` 也必须非空，确保系统明确说明哪些结论尚不能确定。
- `unknown` 类别和 `undetermined` 风险都必须给出缺失字段与不确定性，不能只返回保守标签而不追问。
- `collect_more_info` 路由必须有具体缺失字段；已有高风险事实时，即使仍缺信息也必须路由
  `human_review`，不能因追问而延迟避险。
- `high/emergency` 必须包含立即行动、标记 `requires_human_review=true` 并路由 `human_review`。
- 提示只允许把用户明确输入和未经核实的上下文写入观察事实，禁止猜测地点、人员、现场状态和责任。
- 立即行动优先减少暴露、警示隔离并联系专业人员或现场应急人员；禁止建议无资质人员靠近、触碰、
  带电测试、拆卸或维修危险源。
- 分析不能直接定责、处罚、建单、派单或关闭记录，也没有任何工具调用或业务副作用。

## 离线案例阈值

20 条冻结案例通过 Fake LLM 协议矩阵，以下六项均为 20/20：

| 指标 | 结果 |
|---|---:|
| 主类别 | 20/20 |
| 风险区间 | 20/20 |
| 路由 | 20/20 |
| 人工复核标记 | 20/20 |
| 必须提取或追问的要点 | 20/20 |
| 禁止工具副作用 | 20/20 |

该矩阵把冻结预期编码为本地预设模型输出，再验证输入、提示、解析和安全门禁的完整协议链。它证明
数据契约与确定性校验可复现，不证明真实模型具有 100% 分类或风险判断准确率。

## 完成口径与剩余门禁

Phase 1 的实现清单已完成，且自动测试与前端生产构建通过。进入 Phase 2 前仍需完成专业人员人工验收；
如团队决定接入真实模型，还必须在明确授权后单独执行并记录真实模型冒烟、准确率、成本、延迟和错误
行为。本任务没有读取 API Key、创建真实模型客户端或调用任何真实/付费模型。
