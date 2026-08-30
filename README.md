# 海之子 · 安全质量 Agent

面向施工现场安全、质量、管理和后勤问题的轻量 Agent。用户可以描述问题或咨询处理方法；
也可以上传单张现场照片。Agent 先正常回答，只有问题需要留痕、整改或复查时才建议进入
受控工作流。

当前仓库是从 `sea-son-agent` 的 `main` 选择性迁移得到的干净起点，不包含旧 MiC 数据、
旧演示任务和复杂后台 Agent job。当前已完成 Phase 1–4 的离线分析契约、受控提案、
本地整改工作流和只读知识检索，并完成 Phase 5 单图证据能力、文字/历史工单产品补齐及会话工作台体验重构。
文字与图片均有独立模型入口和逐次外发确认；真实文字调用尚未独立冒烟，现场效果仍需专业验收。
当前是本机受控演示产品，不是具备生产身份鉴权的上线系统。

## 当前能力

- Vue 3 + TypeScript + Vite 会话工作台、响应式侧栏、历史工单列表和可刷新详情。
- FastAPI 健康检查和运行时信息接口。
- Hello-Agents V1.0.3 教程兼容依赖基线（框架包固定为 `hello-agents==0.2.9`）。
- Pydantic 安全质量问题结构化契约。
- 受控工具统一返回协议。
- 六状态本地整改工作流、人工派工与复查事件。
- 2 份公开法规、8 条可追溯释义；模型建议、检索依据和人工结论分开展示。
- 单图安全上传、EXIF清理、最多5个待人工核对候选，整改前后照片关联。
- 自然语言文字回答/分析、最多6轮补充追问、高风险跨轮保留和最新服务端分析提案。
- 历史记录搜索、类别/状态/处置筛选、分页、详情恢复和继续人工整改。
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
- [Phase 4 知识契约](docs/phase4-knowledge-contract.md)
- [知识目录维护](knowledge/README.md)
- [Phase 5 图片契约](docs/phase5-image-contract.md)
- [图片人工复核表](docs/phase5-human-review.md)
- [文字入口与历史工单契约](docs/product-text-records-contract.md)
- [会话工作台体验契约](docs/conversation-workbench-contract.md)
- [聊天提示词位置与修改方法](docs/chat-prompt-guide.md)

## 文字咨询与历史工单

启动前后端后，左侧“新建聊天”用于一般问答且不提供工单动作；“新建咨询”接收自然语言，
先提取信息、追问和判断风险；“提交工单”用于信息已较完整的结构化受控路径。
real模式右下角持续显示目标模型；每次点击发送箭头即确认将当前消息、标签及本会话历次用户补充
发给DeepSeek并承担费用，不形成后续消息的持续授权，也不再显示额外确认弹窗。
文字沿用 `LLM_MODEL=deepseek-v4-flash`（也支持已核验的v4-pro）及现有密钥/官方HTTPS端点；
普通聊天10秒超时/最多256输出token，专业咨询30秒超时/最多4096输出token；均零自动重试、每轮一次请求。
无需改变VISION_MODEL。

普通聊天只回答；咨询信息不足时显示追问；四类明确需跟进问题才提供“生成待确认提案”。
同一问题已出现高风险后，后续描述不能自行降级；仍须专业复核。生成提案后会话停止补充，
按“确认提案 → 保存为正式草稿”操作，保存后跳到 `/records/ISS-…` 详情。

“历史工单”位于 `/records`，可搜索、筛选、翻页、重新打开工单；详情刷新及后端重启后，已保存记录
仍从本地Store恢复。确认后修改展示字段需重新确认。详情内可继续整改、查依据和关联照片。

每个咨询最多6轮；服务端最多200个内存会话，30分钟不活跃后惰性过期。未保存咨询在页面刷新/离开
后不恢复，后端重启会丢失会话与待确认凭据；已经保存的工单不丢失。不要在搜索词中填写敏感个人资料，
列表筛选会进入浏览器URL和服务访问日志。系统尚无生产级身份与项目隔离。

Mock模式明确不执行真实文字理解；如只需离线演示流程，可从“提交工单”进入结构化路径（不调用模型）。
本轮自动/浏览器测试均用Fake或Mock，没有实调付费文字模型，不宣称真实文字准确率已达标。

## 只读知识演示

获得文字/图片分析提案或打开工单后，在“建议、依据与人工结论”区输入关键词，人工确认适用地区后检索。
首批只有中国内地建设工程资料；可用“临边”“消防通道”“隐蔽工程”“生活区”等关键词。
未知/境外地区或无匹配材料时明确显示无依据，不作合规或责任认定。检索不额外调用模型。

关闭知识库：在启动后端的 PowerShell 中先执行 `$env:KNOWLEDGE_ENABLED = 'false'`，再运行
`scripts/start-backend.ps1`；恢复时设为 `'true'` 并重启。此开关不改变已有分析或整改记录。
启动脚本现在会加载 `.env`，已有进程环境变量仍优先；修改后需要重启后端。

## 单张图片与 real 模式

图片模型单独配置 `VISION_MODEL=deepseek-v4-flash-vision-exp`；原 `LLM_MODEL=deepseek-v4-flash`
保留用于文字能力，不自动拿不支持图片的模型代替。端点目前仅支持 DeepSeek 官方 HTTPS API。

更新依赖并重启后端，确保 `.env` 被加载：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

页面流程：先打码并确认上传授权 → 上传一张JPEG/PNG（5MiB/4096边长上限）→ 核对脱敏预览 →
逐次勾选外发及费用确认后分析 → 人工纠正、采纳或驳回候选 → 按原流程确认提案和保存草稿。
前照片在整改开始前关联，后照片由整改人在整改中或待复查阶段关联；关联不会自动关闭记录。

上传本身只写本地 `uploads/`；只有显式分析且real模式时才发送脱敏JPEG和补充文字到DeepSeek。
EXIF清除不等于像素打码。没有生产身份/所有权鉴权，请仅在本机受控演示，不要暴露公网。
Mock不识别真实图片，只返回明确的待人工核对提示。图片失败时仍可使用原文字结构化入口。

独立真实冒烟脚本 `scripts/verify-vision-live.py` 默认拒绝联网，必须另获费用授权才传 `--confirm-paid`；
普通 `verify.ps1` 不执行它。本轮真实验证记录见 `docs/phase5-live-smoke.json`，不能代表真实工地准确率。

## 能力边界

- AI 结论不能替代项目安全员、质量人员或其他专业人员的正式判断。
- 高风险事项必须提供立即避险提示，并进入人工审核。
- 创建任务、派单、整改、复查和关闭由确定性程序控制，不由模型直接改状态。
- Mock、真实模型、演示数据和真实业务数据必须明确隔离。
- 未完成的能力不得在页面、文档或演示中表述为已经实现。
