# Phase 1 六类结构化问题分析

## 任务边界

目标：让单 Agent 结构化分析协议支持 `safety/quality/management/logistics/consultation/unknown`
六个主类别，并以严格 `IssueAnalysis` 解析结果作为唯一有效输出。

教程依据：Hello-Agents V1.0.3 第 4 章单 Agent 范式、第 7 章 `SimpleAgent` 和结构化输出，以及
第 12 章固定案例评估原则。

当前行为：`IssueAnalyzer` 接收 `TextConsultationInput`，通过注入的模型接口运行无工具
`SimpleAgent`；系统提示冻结六类定义并嵌入 `IssueAnalysis` JSON Schema；模型返回在写入框架历史
前经 `parse_issue_analysis` 校验。当前没有 HTTP API、前端入口或真实模型调用。

验收条件：六个枚举值均能通过 Fake LLM 端到端往返；非法第七类被拒绝；`unknown` 具有明确保守
语义；类别与风险独立；可选上下文标记为未经核实；每次分析无共享历史；工具调用、Markdown 和
非 JSON 输出被拒绝；模型超时和错误使用稳定代码。

允许修改：结构化分析 Agent、分类系统提示、分类协议测试、领域词汇、架构和验证文档。

禁止修改：真实模型配置、分类准确率阈值、风险策略、信息不足/高风险专项行为、API、前端、
Function Calling、工作流、RAG、图片上传和多智能体；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analysis_categories.py tests/test_basic_dialog.py tests/test_issue_analysis_output.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：产品、安全、质量、管理和后勤代表共同复核分类定义及交叉场景；接入真实模型后，必须
用 20 条固定案例单独记录准确率和失败案例，不能用本任务的 Fake 协议测试代替行为验收。

## 六类定义

| 类别 | 主归口 |
|---|---|
| `consultation` | 询问一般方法、要求或假设场景，未明确报告已发生的具体问题。 |
| `safety` | 施工或作业现场的人身伤害、坠落、消防、临时用电、个人防护等安全隐患。 |
| `quality` | 构件、材料或施工成品的开裂、渗漏、空鼓、尺寸偏差、损坏等质量问题。 |
| `management` | 材料堆放与标识、检查记录、审批流程、现场秩序或违规行为等管理问题。 |
| `logistics` | 宿舍、生活区供电漏水、卫生、空调、门锁等后勤保障问题。 |
| `unknown` | 文字不足、含义不清或无法确定唯一主类别；不得猜测补全。 |

类别表达用户主诉的业务归口，不等同于风险等级。例如，咨询可以涉及高风险做法，生活区后勤问题
也可能达到紧急风险。施工现场作业危险优先归安全；宿舍和生活区保障归后勤；审批、记录和秩序问题
归管理。最终规则仍以固定案例的团队人工确认结果为准。

## 执行边界

- 每次 `analyze` 创建新的 `SimpleAgent`，不在无会话 ID 的情况下共享历史。
- `tool_registry=None` 且 `enable_tool_calling=False`，结构化分析不能创建记录或改变状态。
- `_StructuredOutputGuard` 在框架保存模型消息前完成严格 JSON 解析和规范化。
- 非法类别由 `IssueCategory` 枚举拒绝；模型服务异常与结构化输出错误使用不同错误类型。
- 系统提示动态嵌入 Pydantic JSON Schema，字段契约变化会同时影响提示和冻结 Schema测试。

本任务证明六类协议可运行，不证明任何真实模型已经正确分类，也不完成风险、信息不足或高风险
专项策略。
