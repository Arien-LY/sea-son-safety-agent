"""只生成待用户确认提案的问题记录工具。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from threading import Lock
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agents.schemas import IssueAnalysis, RecommendedRoute
from agents.tools.audit import ToolAuditLog, summarize_arguments
from agents.tools.base import AgentTool, ToolRegistry, ToolResult


class IssueRecordReviewFields(BaseModel):
    """用户可以补充或修订的记录展示字段，不得覆盖风险与路由。"""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    record_title: str = Field(min_length=1, max_length=100)
    record_description: str = Field(min_length=1, max_length=1_000)
    project: str | None = Field(default=None, min_length=1, max_length=100)
    area: str | None = Field(default=None, min_length=1, max_length=200)
    reporter_note: str | None = Field(default=None, min_length=1, max_length=500)


class IssueRecordProposal(BaseModel):
    """尚未保存、派单或进入业务工作流的问题记录提案。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    proposal_type: Literal["issue_record"] = "issue_record"
    status: Literal["awaiting_user_confirmation"] = "awaiting_user_confirmation"
    analysis: IssueAnalysis
    review_fields: IssueRecordReviewFields
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

    def __init__(
        self,
        *,
        audit_log: ToolAuditLog | None = None,
        proposal_factory: Callable[[IssueAnalysis], IssueRecordProposal] | None = None,
    ) -> None:
        self.audit_log = audit_log or ToolAuditLog()
        self._proposal_factory = proposal_factory or self._build_proposal
        self._completed_digests: set[str] = set()
        self._duplicate_lock = Lock()

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
            return self._complete(arguments, ToolResult(
                tool_name=self.name,
                ok=False,
                summary="问题记录提案参数不符合 IssueAnalysis 契约。",
                recoverable=True,
                error_code="invalid_arguments",
            ))

        eligible_routes = {
            RecommendedRoute.PROPOSE_WORKFLOW,
            RecommendedRoute.HUMAN_REVIEW,
        }
        if analysis.recommended_route not in eligible_routes:
            return self._complete(arguments, ToolResult(
                tool_name=self.name,
                ok=False,
                summary="当前分析不需要创建问题记录提案。",
                recoverable=True,
                error_code="issue_not_eligible_for_proposal",
            ))

        _keys, argument_digest = summarize_arguments(
            analysis.model_dump(mode="json")
        )
        with self._duplicate_lock:
            if argument_digest in self._completed_digests:
                return self._complete(arguments, ToolResult(
                    tool_name=self.name,
                    ok=False,
                    summary="相同的问题记录提案调用已经成功处理。",
                    recoverable=True,
                    error_code="duplicate_call",
                ))
            self._completed_digests.add(argument_digest)

        try:
            proposal = self._proposal_factory(analysis)
        except Exception:
            with self._duplicate_lock:
                self._completed_digests.discard(argument_digest)
            return self._complete(arguments, ToolResult(
                tool_name=self.name,
                ok=False,
                summary="问题记录提案生成时发生内部错误。",
                error_code="internal_error",
            ))

        return self._complete(arguments, ToolResult(
            tool_name=self.name,
            ok=True,
            summary="已生成待用户补充和确认的问题记录提案，尚未保存或派单。",
            data={"proposal": proposal.model_dump(mode="json")},
        ))

    @staticmethod
    def _build_proposal(analysis: IssueAnalysis) -> IssueRecordProposal:
        return IssueRecordProposal(
            analysis=analysis,
            review_fields=IssueRecordReviewFields(
                record_title=analysis.issue_type,
                record_description=analysis.summary,
            ),
        )

    def _complete(
        self, arguments: Mapping[str, Any], result: ToolResult
    ) -> ToolResult:
        self.audit_log.record(
            tool_name=self.name,
            arguments=arguments,
            result=result,
        )
        return result


def build_issue_proposal_registry() -> ToolRegistry:
    """建立只包含问题记录提案工具的最小注册表。"""

    return ToolRegistry([ProposeIssueRecordTool()])
