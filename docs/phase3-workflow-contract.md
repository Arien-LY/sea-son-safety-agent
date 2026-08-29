# Phase 3 整改和后勤工作流契约

## 任务模板

目标：

- 把 Phase 2 经用户确认且通过完整性校验的提案保存为本地正式草稿。
- 用确定性状态机完成上报、人工派工、整改、复查、驳回重改和关闭。
- 让安全问题与后勤问题复用同一生命周期并保留完整事件轨迹。

教程依据：

- Hello-Agents V1.0.3 第 4 章 Plan-and-Solve 的分步思想。
- Agent 只产生分析和提案；权限、持久化和状态推进由程序负责。
- Extra09 的最小闭环、失败留痕和可观测性原则。

当前行为：

- Phase 2 确认结果包含进程级 HMAC-SHA256 完整性凭据，但仍未持久化或派单。
- 页面没有正式记录、责任人、整改说明、复查或关闭状态。

验收条件：

- 主状态严格为 `draft → submitted → assigned → rectifying → pending_review → closed`。
- 补充信息走 `submitted → draft → submitted`；驳回走 `pending_review → rectifying`。
- 取消不增加第七个主状态，而是把 `disposition` 设为终止的 `cancelled`。
- 本地 Store 原子替换写入，并以共享路径锁和 revision 防止进程内并发丢失更新。
- 责任角色只是按类别生成的建议；协调员必须明确选择责任人和角色后才进入 `assigned`。
- 整改人必须提交说明；复查人必须提交结论；高风险提交人不能自行关闭。
- 一条安全问题和一条后勤问题均可完整关闭，所有动作有时间、人员、前后状态和说明。

允许修改：

- `backend/app/` 下确定性工作流、Store、API。
- Phase 3 契约、测试、页面验收入口和相关文档。

禁止修改：

- 不新增 Agent 工具、Prompt、RAG、图片、多智能体或真实/付费模型调用。
- 不自动归责、处罚、关闭、外部派单或发送通知。
- 不把演示 actor ID 当作生产鉴权或真实身份。

测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_contract.py tests/test_phase3_workflow.py tests/test_phase3_api.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

人工确认点：

- 专业人员复核角色名称、关闭权限和高风险取消规则。
- 产品负责人确认“取消使用独立 disposition、主状态不变”的展示语义。
- 部署前补充真实登录身份、项目权限和跨进程文件锁或数据库事务。

## 状态和例外路径

主状态只有六个，机器契约见 `contracts/phase3_workflow.v1.json`。

```text
draft → submitted → assigned → rectifying → pending_review → closed
  ↑         │                         │
  └─ 补充信息退回                      └─ 驳回复查 → rectifying
```

- `request_more_info`：协调员把 `submitted` 退回 `draft` 并写明问题。
- `supplement_information`：原报告人补充说明后从 `draft` 重新提交。
- `reject_review`：复查人写明原因，从 `pending_review` 回到 `rectifying`；可重复整改。
- `cancel`：保留当时主状态，把 `disposition` 从 `active` 改为 `cancelled`，之后禁止推进。

## 角色和责任边界

| 动作 | 允许角色 | 额外条件 |
|---|---|---|
| 保存草稿、提交、补充 | 报告人 | 必须是原报告人 |
| 要求补充、派工 | 协调员 | 派工必须人工填写责任人和责任角色 |
| 开始整改、提交整改 | 整改人 | 必须等于已指派人员，整改提交必须有说明 |
| 驳回、普通关闭 | 复查人/专业复查人 | 必须有复查说明 |
| 高风险关闭 | 专业复查人 | 不能与原报告人是同一 actor ID |

类别映射只产生建议：安全→安全管理人员、质量→质量检查人员、管理→现场管理人员、后勤→后勤维修
人员。建议不会填写 `assigned_to`，也不会把记录推进到 `assigned`。

## Store 与一致性

- 默认文件为 `data/issue-records.json`，该运行数据被 Git 忽略。
- 每次修改在同目录写临时文件、`flush + fsync` 后调用 `os.replace` 原子替换。
- 同一路径的 Store 实例共享进程内可重入锁；每次修改都重新加载文件。
- 创建使用持久化幂等键和请求摘要；同键同请求返回原记录，同键不同请求冲突。
- 更新必须携带 `expected_revision`，并发请求只有一个可以从同一 revision 成功。
- Store 文件解析或校验失败时拒绝读取和覆盖，不以空文件静默恢复。

## 已知边界

- 当前本地 JSON Store 适合单机演示，不提供跨进程/跨主机锁、备份、数据库事务或灾难恢复。
- HMAC 完整性密钥和提案确认凭据仍为进程级，后端重启后未保存提案需要重新确认。
- 演示页面使用固定角色标识；真实鉴权、项目成员关系和角色授权属于部署前独立安全任务。
- 工作流事件保存业务动作说明，不保存隐藏思维链、模型上下文或 Agent 内部推理。
