# TicketDecision 契约（聊天回答 → 是否生成工单）

## 目标

把"聊天回答"和"是否生成工单"解耦：模型先正常回答用户，服务端只用一份最小、
可测试的判断决定是否显示"生成工单"。模型不再被要求一次返回完整 IssueAnalysis。

## 一次模型返回

统一聊天（`intent=auto` / `chat`+图片）只输出：

```json
{
  "answer": "自然语言回答",
  "follow_up_questions": ["可选追问"],
  "ticket_decision": {
    "status": "no_ticket | need_more_info | create_ticket",
    "category": "safety | quality | management | logistics | consultation | unknown",
    "issue_type": "问题类型",
    "summary": "问题摘要",
    "risk_level": "undetermined | low | medium | high | emergency",
    "requires_human_review": false,
    "missing_information": ["需要在安全条件下补充的现场信息"],
    "immediate_action": "高风险时的一句立即避险提示"
  }
}
```

不新增第二次模型调用。

## 界面行为

| status | 回答 | 追问 | 生成工单按钮 |
| --- | --- | --- | --- |
| `no_ticket` | 正常回答 | 无 | 不显示 |
| `need_more_info` | 正常回答 | 显示 | 不显示 |
| `create_ticket` | 正常回答 | 需要时显示 | 显示 |

高风险 / 紧急（`high` / `emergency`）：服务端强制 `create_ticket`、
`requires_human_review=true`，并保留一句立即避险提示；模型不能降级。

## 服务端转换

模型不生成 IssueAnalysis。服务端用 `decision_to_analysis()` 把 TicketDecision
确定性地转换成现有 IssueAnalysis，再进入未改动的：

`Proposal → HMAC 提案完整性 → 用户核对 → 人工确认 → 正式 IssueRecord → 六状态工作流`。

浏览器不能自行构造分析、降低风险或取消人工复核。

## 判断失败时

自然语言回答校验成功、TicketDecision 校验失败时：

- 保留已经展示的回答；
- `analysis_status = "unavailable"`，`can_propose = false`，不伪造工单；
- 页面显示"本次工单判断失败，可重新判断"，并提供一次人工 `[重新判断工单]`；
- 重新判断复用已保存的用户输入，不新增用户消息，不自动重试，每轮最多一次。

## 100 条公开案例库

`data/field-cases.sqlite3`（脚本 `scripts/import-field-cases.py`，只读层
`backend/app/field_cases.py`）是评估案例库，不是工单、规范答案或专业裁决结果，
不接入聊天回答、不作 RAG 或自动处理依据。
