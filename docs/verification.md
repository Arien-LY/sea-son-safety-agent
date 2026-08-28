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

