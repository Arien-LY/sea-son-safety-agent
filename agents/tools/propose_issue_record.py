"""只生成待用户确认提案的问题记录工具。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from agents.schemas import IssueAnalysis, RecommendedRoute
from agents.tools.base import AgentTool, ToolRegistry, ToolResult


class IssueRecordProposal(BaseModel):
    """尚未保存、派单或进入业务工作流的问题记录提案。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    proposal_type: Literal["issue_record"] = "issue_record"
    status: Literal["awaiting_user_confirmation"] = "awaiting_user_confirmation"
    analysis: IssueAnalysis
    requires_user_confirmation: Literal[True] = True
    persisted: Literal[False] = False
    dispatched: Literal[False] = False


class ProposeIssueRecordTool(AgentTool):
    """把已校验的问题分析转换为无副作用的待确认提案。"""

    name = "propose_issue_record"
    description = (
        "根据完整且需要留痕或人工跟进的 IssueAnalysis 生成待用户确认的问题记录提案；"
        "本工具不保存、不派单，也不改变任何业务状态。"
    )

    def to_openai_schema(self) -> dict[str, Any]:
        """生成原生 Function Calling 使用的唯一工具 Schema。"""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": IssueAnalysis.model_json_schema(),
            },
        }

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            raw_arguments = json.dumps(dict(arguments), ensure_ascii=False)
            analysis = IssueAnalysis.model_validate_json(raw_arguments, strict=True)
        except (TypeError, ValueError, ValidationError):
            return ToolResult(
                tool_name=self.name,
                ok=False,
                summary="问题记录提案参数不符合 IssueAnalysis 契约。",
                recoverable=True,
                error_code="invalid_arguments",
            )

        eligible_routes = {
            RecommendedRoute.PROPOSE_WORKFLOW,
            RecommendedRoute.HUMAN_REVIEW,
        }
        if analysis.recommended_route not in eligible_routes:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                summary="当前分析不需要创建问题记录提案。",
                recoverable=True,
                error_code="issue_not_eligible_for_proposal",
            )

        proposal = IssueRecordProposal(analysis=analysis)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            summary="已生成待用户补充和确认的问题记录提案，尚未保存或派单。",
            data={"proposal": proposal.model_dump(mode="json")},
        )


def build_issue_proposal_registry() -> ToolRegistry:
    """建立只包含问题记录提案工具的最小注册表。"""

    return ToolRegistry([ProposeIssueRecordTool()])
