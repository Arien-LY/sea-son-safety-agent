import type { ActorRole, IssueCategory, RecommendedRoute, RiskLevel, WorkflowAction, WorkflowStatus } from "./types";

export const categoryNames: Record<IssueCategory, string> = { safety: "安全", quality: "质量", management: "管理", logistics: "后勤", consultation: "一般咨询", unknown: "待确认" };
export const riskNames: Record<RiskLevel, string> = { undetermined: "待判断", low: "低", medium: "中", high: "高", emergency: "紧急" };
export const routeNames: Record<RecommendedRoute, string> = { direct_answer: "直接答复", collect_more_info: "补充信息", propose_workflow: "申请工单", human_review: "人工复核" };
export const statusNames: Record<WorkflowStatus, string> = { draft: "草稿", submitted: "已提交", assigned: "已派工", rectifying: "整改中", pending_review: "待复查", closed: "已关闭" };
export const actorNames: Record<ActorRole, string> = { reporter: "报告人", coordinator: "协调员", rectifier: "整改人", reviewer: "复查人", professional_reviewer: "专业复查人" };
export const actionNames: Record<WorkflowAction | "create_draft", string> = { create_draft: "创建草稿", submit: "提交工单", request_more_info: "要求补充", supplement_information: "补充信息", assign: "人工派工", start_rectification: "开始整改", submit_rectification: "提交整改", reject_review: "驳回复查", close: "复查关闭", cancel: "取消工单" };
