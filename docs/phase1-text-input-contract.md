# Phase 1 文字咨询输入契约

## 任务边界

目标：定义单条文字咨询输入及可选上下文的严格契约，为后续基础对话提供稳定、无副作用的入口。

教程依据：Hello-Agents V1.0.3 第 4、7、12、16 章，以及仓库“先基础对话、后工具”的阶段门禁。

当前行为：`TextConsultationInput` 只校验和规范化内存中的输入数据。当前没有对话 API、Agent、Prompt、
模型调用、记录创建或任务状态变化。

验收条件：只允许消息、项目标签、区域标签和咨询者角色四个字段；消息必填；可选字段可省略或为
`null`；所有字符串去除首尾空白后必须满足长度；额外字段、错误类型、空白值和图片/文件字段被拒绝；
冻结 Schema 与 Pydantic 模型一致；测试离线且确定性。

允许修改：输入 Pydantic 契约、对应 JSON Schema、契约测试、领域词汇、任务清单与验证记录。

禁止修改：API 路由、Agent、Prompt、Function Calling、任务/整改工作流、RAG、图片上传、多智能体
和前端交互；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_text_consultation_input.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：产品负责人确认字段名称和长度是否满足比赛演示；安全/质量人员确认可选上下文不会被
误解为已核实现场事实。后续引入项目 ID、区域 ID、登录身份或权限时，必须使用独立契约和授权校验。

## 冻结字段

| 字段 | 必填 | 类型 | 长度 | 语义 |
|---|---:|---|---:|---|
| `message` | 是 | string | 1～1000 | 一条咨询或现场问题描述。 |
| `project` | 否 | string/null | 1～100 | 用户提供、未经核实的项目标签。 |
| `area` | 否 | string/null | 1～200 | 用户提供、未经核实的区域标签。 |
| `requester_role` | 否 | string/null | 1～50 | 用户自报的咨询者角色，不代表权限或责任。 |

所有字符串先去除首尾空白再校验。可选字段省略或显式传 `null` 都表示“未提供”；显式空字符串或
纯空白表示非法输入，不会静默转换为 `null`。模型启用严格类型和 `extra="forbid"`，因此数字、
布尔值、bytes，以及 `image`、`file`、`image_binary` 等未声明字段均被拒绝。

## 安全边界

- 项目、区域和咨询者角色均为用户陈述，不是可信身份、权限或正式业务主数据。
- 输入校验成功不等于现场事实成立，不得据此自动归责、派单、创建记录或改变状态。
- 本契约不承载图片、文件、二进制内容、API Key、个人联系方式或隐藏模型上下文。
- 对图片的格式、大小、存储和证据边界将在 Phase 5 单独设计，不通过扩展本契约提前加入。

冻结机器契约位于 `contracts/phase1_text_consultation_input.v1.schema.json`。任何字段增删、语义变化或
长度边界变化都属于契约变更，必须同步 Schema、测试、固定案例和验证记录。
