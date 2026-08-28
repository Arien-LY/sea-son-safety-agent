# 海之子 · 安全质量 Agent

面向施工现场安全、质量、管理和后勤问题的轻量 Agent。用户可以描述问题或咨询处理方法；
后续阶段将支持上传现场照片。Agent 先正常回答，只有问题需要留痕、整改或复查时才建议进入
受控工作流。

当前仓库是从 `sea-son-agent` 的 `main` 选择性迁移得到的干净起点，不包含旧 MiC 数据、
旧演示任务和复杂后台 Agent job。当前只交付可安装、可启动、可测试的工程骨架，尚未宣称
实现问题识别、图片分析或整改闭环。

## 当前能力

- Vue 3 + TypeScript + Vite 前端骨架。
- FastAPI 健康检查和运行时信息接口。
- Hello-Agents V1.0.3 教程兼容依赖基线（框架包固定为 `hello-agents==0.2.9`）。
- Pydantic 安全质量问题结构化契约。
- 受控工具统一返回协议。
- Windows 安装、启动和验证脚本。
- 教程约束、迁移清单、架构决策和阶段任务清单。

## 环境要求

- Windows 10/11
- Python 3.12
- Node.js 20+
- Git

## 首次安装

在仓库根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

## 启动

终端 1：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

终端 2：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

## 文档入口

- [任务清单](TASKS.md)
- [架构](docs/architecture.md)
- [Hello-Agents 教程符合性](docs/tutorial-compliance.md)
- [旧项目复用清单](docs/reuse-inventory.md)
- [Codex harness 架构决策](docs/decisions/0001-codex-harness.md)
- [验证记录](docs/verification.md)

## 能力边界

- AI 结论不能替代项目安全员、质量人员或其他专业人员的正式判断。
- 高风险事项必须提供立即避险提示，并进入人工审核。
- 创建任务、派单、整改、复查和关闭由确定性程序控制，不由模型直接改状态。
- Mock、真实模型、演示数据和真实业务数据必须明确隔离。
- 未完成的能力不得在页面、文档或演示中表述为已经实现。
