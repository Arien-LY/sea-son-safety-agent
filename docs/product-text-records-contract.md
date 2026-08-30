# 产品补齐：文字入口与历史工单 v1

目标：把已有文字分析、提案与工作流连接为可操作入口，并支持历史记录查询、详情直达和刷新恢复。
教程依据：Hello-Agents V1.0.3 第7章单Agent/严格工具边界、第9章有限上下文、第12章固定验收及Extra09审计。
当前行为：基线为已合并PR #13（ffe217b）；文字首页手动填写类别/风险，已有分析模块尚无产品API；
工作流按ID可读取，但没有列表或可刷新的详情路由。图片链路已接通。
验收条件：普通咨询不产生提案；信息不足可继续补充；每次真实请求须外发/费用确认；高风险跨轮不降级；
只有最新服务端分析可生成提案，仍须人工确认再保存；历史列表搜索/筛选/分页、详情刷新和继续整改有效。
允许修改：独立文字输出/会话契约、模型适配、服务及API、列表只读查询、Vue入口/导航/详情、测试文档。
禁止修改：已有Phase1/3冻结Schema和工作流规则、自动建单/归责/关闭、多智能体、生产鉴权/数据库和Phase6指标。
测试命令：专项 `pytest tests/test_product_text.py tests/test_product_records.py`；`scripts/verify.ps1`。
人工确认点：逐次外发付费、最新分析生成提案、展示字段补充及正式保存；真实文字准确率需另行授权与专业验收。

## 文字调用与上下文

- POST `/api/text-consultations`：`request_id`（8–100安全字符）、`input`（复用TextConsultationInput）、
  `intent`（`chat/consult`，默认consult）、`consultation_id`（可空）、`expected_turn`（首次0，后续当前轮次）、
  严格布尔`allow_external`（默认false）。不同intent不能共用同一会话。
- 不接受客户端assistant/system历史、分析、权限、工具参数或配置覆盖。每个新问题创建随机不可猜测ID；
  同一问题最多6轮，每轮message最多1000字，服务端保留用户原文和已校验回复，仅存内存。
  续轮同时提供上轮由服务端保存的追问，帮助理解“是/不是”等回答，不接受客户端伪造追问或历史。
- 最多200个会话，30分钟不活跃后过期（惰性清理）；重启丢失未保存会话，不丢已保存工单。无持久聊天历史。
- 同一request_id与同一请求在会话有效期内重放成功响应，不再次计费；同键不同请求409；旧轮次409。
  失败不推进轮次、不自动重试。前端失败保留输入，明确由用户选择重试或开始新问题。
- `chat` 每轮使用同一模型的轻量直答：10秒超时、0重试、最多256输出token，不要求JSON；服务器日期注入
  system语境；按 `system → user → assistant → … → 当前user` 排列最多6轮对话，历史仅作语境。
  assistant答案从已有成功responses按turn读取；当前user只含本轮输入和标签，不把历史重新打包为本轮问题。
  具体边界见 `docs/chat-turn-history-contract.md`。返回中的analysis为代码生成的保守
  unknown/undetermined占位，不用于工单、风险认定或提案。
- `consult` 每轮使用临时SimpleAgent一次，无工具循环；JSON为answer、follow_up_questions、analysis。
  用既有IssueAnalysis校验风险结构；补充提问必须覆盖缺失信息；模型输入不含隐藏思维链或业务权限。
- 新页面仅支持已核验DeepSeek官方HTTPS端点、deepseek-v4-flash/pro文字模型，沿用LLM_MODEL和密钥；
  专业咨询30秒/4096token，日常聊天10秒/256token，均为0重试。不修改.env，不执行付费验证。
- [官方JSON输出](https://api-docs.deepseek.com/guides/json_mode/)与
  [thinking设置](https://api-docs.deepseek.com/guides/thinking_mode/)于2026-08-30核对：json_object、
  明示JSON Schema，thinking disabled；只读取最终content，截断/空输出/工具调用/无效结构均失败。
- 同一问题已出现high/emergency时，后续分析不能降低风险、取消人工复核或丢失立即行动；后续自由回答
  被确定性安全提示替代，避免一边保留高风险一边给出“已安全”文案。新问题需显式新建会话。
- Mock明确不运行真实文字理解，只返回unknown/undetermined和人工补充提示；不把关键词规则伪装成模型。
- 审计只记录摘要哈希、错误码、耗时和结果摘要；不记录原文、密钥或隐藏思维链。会话不是登录身份。

## 提案与历史

- POST `/api/text-consultations/{id}/proposal`：expected_turn、confirmed=true；只取最新服务端分析，
  不接收客户端分析。四类问题且路由propose_workflow/human_review才可提案；consultation/unknown不得建单。
- 提案沿用Phase2ProposalService确定性工具路径，不为强制执行已知工具增加第二次模型调用；不修改原生
  FunctionCallAgent模块。重复提案返回同一凭据，成功提案后冻结该会话的补充，防止旧低风险提案继续流转。
- GET `/api/issue-records`：q最多100字；category/status/disposition枚举筛选；offset0–100000、limit1–50。
  快照内按updated_at降序、record_id升序稳定排序。只返回列表摘要和total，不返回完整事件或模型上下文。
- `/records`列表、`/records/:recordId`详情，刷新始终从现有Store读取。详情有记录展示字段、完整分析、
  状态轨迹、知识依据、照片和原有人工动作；无效ID/缺失/失败提供明确状态，不显示旧记录。
- 页面角色仍为演示角色，详情操作使用记录中的报告人/整改人ID而非固定示例ID；不是登录或权限真实性。
- URL只带record_id/列表筛选，不写用户咨询、模型响应、密钥到localStorage；表单演示入口单独折叠标注。

## 冻结验收场景

T01普通咨询不提案；T02信息不足补充后四类问题提案；T03高风险补充不可降级；T04非法/越权输入；
T05模型空/坏JSON/截断/超时错误；T06真实授权门禁与脱敏配置；T07幂等重放/并发/旧轮次；
T08会话上限/过期/6轮及重启；T09提案失败可重试/成功冻结；T10工具无建单副作用及原确认链；
R01空/多页列表；R02搜索和组合筛选；R03稳定排序/重启读取；R04非法查询/坏Store；
R05详情刷新/人工整改/revision冲突；R06文字失败后图片与已有工单可继续；移动端和键盘操作。

这属于用户授权的产品补齐任务，不将Phase6或真实模型效果验收提前勾选完成。
