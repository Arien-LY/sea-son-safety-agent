# Phase 4：只读知识与依据契约 v1

目标：小规模本地检索，引用可追溯，无依据不编造，关闭知识库不影响文字分析或工作流。

教程依据：Hello-Agents V1.0.3 第 8 章检索/增强，第 9 章上下文边界，
第 7 章原生工具 Schema，Extra09 脱敏可观测性。

当前行为：Phase 3 已合并；`knowledge/` 为空占位，文字分析和确定性工作流独立运行。

验收条件：固定案例命中与预期 ID 集合完全一致；每条引用的正文、来源、条号、版本及摘要与
目录一致；未知/境外地区、无命中、到期/撤回资料均不生成引用；关闭/损坏知识库安全降级；
无新增收费调用、无业务状态写入；既有测试与生产构建通过。

允许修改：知识目录、检索与回答契约、只读工具、应用服务/API、展示组件、相关测试和文档。

禁止修改：既有状态机权限、模型适配协议、图片、多智能体、向量库、外部派单或自动归责。

测试命令：`.venv\Scripts\python.exe -m pytest tests/test_phase4_knowledge.py tests/test_phase4_api.py`；
`powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`。

人工确认点：专业人员复核摘编准确性、现行适用性及项目地域；正式身份认证仍沿用 Phase 3 限制。
本阶段用户授权推进不替代此前双机验证、专业验收或真实模型授权门禁。

## 资料与授权

`knowledge/catalog.v1.json` 首批仅收录 2 份政府官网公开行政法规的 8 条短释义摘编；
不复制商业标准全文，不收录企业/个人资料。`authorization=public_legal_text` 表示公开法规材料，
不是项目内部制度授权书；`content_kind=paraphrase`，不得展示为逐字原文。

来源固定 ID、标题、官方发布者、原文 HTTPS URL、版本、版本更新时间；条目固定 ID、来源 ID、
条号、标题、释义、类别、适用范围、地区、关键词、复核日期、下次复核日期和 active/withdrawn 状态。
来源 URL 仅允许首批核验的政府域名，无运行时联网抓取。ID 不得重用给其他条款；修订须更新版本和日期。
发布网页时间不等于法规版本时间。`reviewed_on` 是入库核对日期，不是法律意见；`review_due_on`
是内部复核截止日（到当日即停止引用），不是法规失效日期。新日期不能由终端用户提交。

本批范围限定中国内地建设工程，不自动套用到香港、澳门或其他境外项目；检索地区默认 unknown，
必须由人明确选择 cn_mainland 才可提供本批资料。适用范围只是候选检索过滤，不代表已确认违法。

## 检索 v1

`SearchKnowledgeRequest`：query（1–1000 字符）、category（可空）、jurisdiction
（unknown/cn_mainland/overseas，默认 unknown）、limit（1–3，默认 3）。严格类型、拒绝多余字段。
每次读取并校验目录；先排除撤回、未到复核日期、已到复核截止日、地区和类别不匹配条目。
NFKC + casefold 后按收录的关键词子串命中数降序，同分按稳定 ID 排序。不做语义理解、否定识别
或法条适用认定；“没有临边危险”也可能命中相关资料，不得据此判风险。
回答组装时 consultation/unknown 不作为知识领域过滤条件，按查询词检索；不改变原分析类别或路由。

`search_knowledge` 是单一只读工具，提供原生 Function Calling Schema，返回统一 ToolResult。
成功 data 含 status（matched/no_results）、citations、excluded_count、as_of；无命中也是成功。
失败码：invalid_arguments、knowledge_disabled、knowledge_unavailable；不泄露路径、查询原文或异常。
审计仅字段名/摘要/时间/结果数量或错误码。`KNOWLEDGE_ENABLED=false` 在启动时关闭检索。

引用包含完整来源、条目 ID/条号/释义/范围/复核信息和 SHA-256（规范 JSON 条目+来源）；
摘要证明本次内容一致，不证明官方签名或法律效力。目录必须经 Git 评审维护。

## 回答与边界

三部分固定分离：model_suggestions（经校验分析中的未核验建议）、retrieved_evidence（只来自工具）、
human_conclusion（默认未复查）。API 不接受调用者提供引用或人工结论。
模型建议不是规范原文，不能作为出处；不让模型撰写带自由条号的“依据回答”，不把检索内容作为
系统指令或触发第二次模型调用。原有分析/风险/人工标记保持原样。无引用一律显示“未找到可用依据，
请由专业人员核对；不得据此认定合规或编造条款”。
这保证引用字段不接受模型伪造，不等于对原分析自由文本进行了事实核验；原建议必须保留未核验标签，
不可把其中的条号或来源陈述当作证据。正式法律意见与真实模型质量评估仍需独立专业验收。

`KnowledgeAssistedAnalyzer` 先调用已有 IssueAnalyzer 一次，再确定性检索/组装；知识库失败不影响
已完成分析。分析本身失败仍沿用原错误，不伪造降级分析。通用 BasicConsultationDialog 保持独立。

`POST /api/knowledge/search` 是工具验收入口；`POST /api/knowledge/answer` 接收已校验分析用于无模型
演示；`POST /api/issue-records/{id}/knowledge` 读取持久化记录分析，查询字段只收 query/jurisdiction。
只有已关闭记录中的 CLOSE 事件可作为人工结论，附记录 ID/revision/操作者/角色/时间/复查说明；
不保存该检索快照，不推进任何状态，不宣称演示角色已通过身份认证。

## 固定评估

`tests/fixtures/phase4_knowledge_cases.v1.json` 在实现前冻结：8 条正例，未知/境外/无关/否定表达，
到期边界、到期前一天、关闭知识库。期望精确 ID 集合；所有返回引用必须与目录内容一致。
另测撤回/未来日期/非法来源/损坏目录/上限排序/重复/无副作用/伪造字段/API 人工结论与高风险降级。
确定性阈值为 100%；这不是开放自然语言召回率或真实模型准确率，专业法律适用仍需人工验收。
