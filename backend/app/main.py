from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from agents.runtime import runtime_info
from agents.tools import ProposeIssueRecordTool, ToolResult
from backend.app.proposals import (
    ConfirmedIssueProposal,
    Phase2ProposalService,
    ProposalConfirmationRequest,
    ProposalPreviewRequest,
)


def create_app(
    *, proposal_service: Phase2ProposalService | None = None
) -> FastAPI:
    proposal_boundary = proposal_service or Phase2ProposalService()
    app = FastAPI(
        title="海之子 · 安全质量 Agent API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def get_runtime() -> dict[str, str]:
        mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
        if mode not in {"mock", "real"}:
            mode = "mock"
        return {"agent_mode": mode, **runtime_info()}

    @app.post("/api/issue-proposals/preview", response_model=ToolResult)
    def preview_issue_proposal(payload: dict[str, Any]) -> ToolResult:
        try:
            request = ProposalPreviewRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False), strict=True
            )
        except (TypeError, ValueError, ValidationError):
            return ToolResult(
                tool_name=ProposeIssueRecordTool.name,
                ok=False,
                summary="提案预览请求参数无效。",
                recoverable=True,
                error_code="invalid_arguments",
            )
        return proposal_boundary.preview(request)

    @app.post(
        "/api/issue-proposals/confirm",
        response_model=ConfirmedIssueProposal,
    )
    def confirm_issue_proposal(
        payload: dict[str, Any],
    ) -> ConfirmedIssueProposal:
        try:
            request = ProposalConfirmationRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False), strict=True
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=400,
                detail="提案确认请求参数无效。",
            ) from exc
        try:
            return proposal_boundary.confirm(request)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="提案完整性校验失败。",
            ) from exc

    return app


app = create_app()
