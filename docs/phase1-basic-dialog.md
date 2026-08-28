# Phase 1 单 Agent 基础对话

## 任务边界

目标：使用 Hello-Agents `SimpleAgent` 建立最小、无工具、无业务副作用的文字咨询闭环，使普通问题
能够返回经过契约校验的直接回答。

教程依据：Hello-Agents V1.0.3 第 4 章单 Agent 范式、第 7 章 `SimpleAgent`，以及 Extra09 的
最小闭环、统一协议和失败留痕原则。

当前行为：`BasicConsultationDialog` 接收已经校验的 `TextConsultationInput`，通过注入的模型接口
调用一个 `SimpleAgent`，返回 `BasicDialogReply`。仓库没有对话 API、前端入口或真实模型冒烟。

验收条件：普通咨询得到非空直接回答；系统提示与用户消息角色正确；可选上下文被明确标记为用户
自报且未经核实；每次请求没有共享历史；工具调用被禁用；空响应、超时、模型错误、超长响应和伪
工具调用使用稳定错误码；所有自动测试仅使用 Fake LLM。

允许修改：Agent 对话边界、最小系统提示、基础回复契约及 Schema、Fake 测试、架构和验证文档。

禁止修改：API 路由、前端、Function Calling、任务/整改工作流、RAG、图片上传、多智能体、数据库
和真实模型配置；禁止调用真实或付费模型。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_basic_dialog.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：安全/质量人员复核系统提示中的不确定性和紧急避险表述；产品负责人确认单轮无历史
行为符合本阶段演示。接入多轮历史前必须先定义会话 ID、隔离边界、清理策略和隐私保留期限。

## 调用边界

```text
TextConsultationInput
  → 格式化未核实的可选上下文
  → SimpleAgent（enable_tool_calling=False，无 ToolRegistry）
  → 模型文字
  → BasicDialogReply Pydantic 校验
```

每次 `reply` 都创建新的 `SimpleAgent`。当前输入契约没有会话 ID，如果复用框架内部历史，可能把
不同用户的消息混入同一上下文，因此本阶段明确采用无共享历史的单轮对话。

## 回复与错误契约

- `BasicDialogReply.answer`：去除首尾空白后 1～4000 字符，不携带工具、记录或状态动作。
- `empty_response`：模型返回 `None`、空字符串或纯空白。
- `invalid_response`：回答未通过 Pydantic 契约，例如超过长度上限。
- `model_timeout`：模型接口报告超时。
- `model_error`：其他模型接口错误，对外不泄露服务商异常细节。
- `unsupported_tool_call`：回答包含 Hello-Agents 旧式工具调用标记；当前阶段拒绝且不执行。

冻结机器契约位于 `contracts/phase1_basic_dialog_reply.v1.schema.json`。本阶段不声称已完成问题分类、
风险判断或 `IssueAnalysis` 输出，高风险和信息不足的确定性路由仍属于后续任务。
