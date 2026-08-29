"""Phase 2 提案预览、用户补充和确认的无持久化服务。"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.schemas import IssueAnalysis
from agents.tools import (
    IssueRecordProposal,
    IssueRecordReviewFields,
    ProposeIssueRecordTool,
    ToolAuditEvent,
    ToolAuditLog,
    ToolResult,
)


class ProposalPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    invocation_id: str = Field(
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    analysis: IssueAnalysis


class ProposalConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    proposal: IssueRecordProposal
    proposal_token: str = Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$")
    edited_fields: IssueRecordReviewFields
    confirmed: Literal[True]


class ProposalFieldChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    field: str = Field(min_length=1, max_length=100)
    before: str | None
    after: str | None


class ConfirmedIssueProposal(BaseModel):
    """用户已确认但仍未进入 Phase 3 持久化的提案。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["confirmed_pending_persistence"] = (
        "confirmed_pending_persistence"
    )
    analysis: IssueAnalysis
    review_fields: IssueRecordReviewFields
    changes: list[ProposalFieldChange] = Field(max_length=5)
    user_confirmed: Literal[True] = True
    persisted: Literal[False] = False
    dispatched: Literal[False] = False


class Phase2ProposalService:
    """只保存幂等键和脱敏审计，不保存问题记录或提案正文。"""

    def __init__(
        self,
        *,
        audit_log: ToolAuditLog | None = None,
        integrity_key: bytes | None = None,
    ) -> None:
        self.audit_log = audit_log or ToolAuditLog()
        self._integrity_key = integrity_key or secrets.token_bytes(32)
        if len(self._integrity_key) < 32:
            raise ValueError("提案完整性密钥至少需要 32 字节。")
        self._seen_invocation_ids: set[str] = set()
        self._invocation_lock = Lock()

    def preview(self, request: ProposalPreviewRequest) -> ToolResult:
        arguments = request.analysis.model_dump(mode="json")
        audit_arguments = {
            "invocation_id": request.invocation_id,
            "analysis": arguments,
        }
        with self._invocation_lock:
            if request.invocation_id in self._seen_invocation_ids:
                result = ToolResult(
                    tool_name=ProposeIssueRecordTool.name,
                    ok=False,
                    summary="相同的提案调用标识已经处理。",
                    recoverable=True,
                    error_code="duplicate_call",
                )
                self.audit_log.record(
                    tool_name=ProposeIssueRecordTool.name,
                    arguments=audit_arguments,
                    result=result,
                )
                return result
            self._seen_invocation_ids.add(request.invocation_id)

        tool = ProposeIssueRecordTool(audit_log=self.audit_log)
        result = tool.run(arguments)
        if not result.ok:
            return result
        proposal = result.data["proposal"]
        return result.model_copy(
            update={
                "data": {
                    "proposal": proposal,
                    "proposal_token": self._sign_proposal(proposal),
                }
            }
        )

    def confirm(
        self, request: ProposalConfirmationRequest
    ) -> ConfirmedIssueProposal:
        expected_token = self._sign_proposal(
            request.proposal.model_dump(mode="json")
        )
        if not hmac.compare_digest(request.proposal_token, expected_token):
            raise ValueError("proposal_integrity_failed")
        before = request.proposal.review_fields.model_dump(mode="json")
        after = request.edited_fields.model_dump(mode="json")
        changes = [
            ProposalFieldChange(
                field=field,
                before=before[field],
                after=after[field],
            )
            for field in IssueRecordReviewFields.model_fields
            if before[field] != after[field]
        ]
        return ConfirmedIssueProposal(
            analysis=request.proposal.analysis,
            review_fields=request.edited_fields,
            changes=changes,
        )

    def audit_snapshot(self) -> tuple[ToolAuditEvent, ...]:
        return self.audit_log.snapshot()

    def _sign_proposal(self, proposal: dict[str, object]) -> str:
        canonical = json.dumps(
            proposal,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hmac.new(
            self._integrity_key,
            canonical,
            hashlib.sha256,
        ).hexdigest()
        return f"hmac-sha256:{digest}"
