from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from agents.runtime import runtime_info
from agents.tools import ProposeIssueRecordTool, ToolResult
from agents.knowledge_answer import (
    KnowledgeAnswer, KnowledgeAnswerBuilder, KnowledgeAnswerRequest, RecordKnowledgeRequest,
)
from agents.tools.search_knowledge import SearchKnowledgeTool
from backend.app.knowledge import answer_for_record
from backend.app.photo_routes import create_photo_router
from backend.app.photo_store import PhotoStore
from backend.app.photos import PhotoService
from backend.app.product_routes import create_product_router
from backend.app.text_consultations import TextConsultationService
from backend.app.proposals import (
    ConfirmedIssueProposal,
    Phase2ProposalService,
    ProposalConfirmationRequest,
    ProposalPreviewRequest,
)
from backend.app.workflow import IssueWorkflowService, WorkflowRuleError
from backend.app.workflow_models import (
    CreateIssueRecordRequest,
    CreateIssueRecordResponse,
    IssueRecord,
    WorkflowTransitionRequest,
)
from backend.app.workflow_store import (
    IdempotencyConflictError,
    JsonIssueRecordStore,
    RecordNotFoundError,
    RevisionConflictError,
    StoreError,
)


def create_app(
    *,
    proposal_service: Phase2ProposalService | None = None,
    workflow_service: IssueWorkflowService | None = None,
    knowledge_tool: SearchKnowledgeTool | None = None,
    photo_service: PhotoService | None = None,
    text_service: TextConsultationService | None = None,
    customer_mode: bool = False,
) -> FastAPI:
    proposal_boundary = proposal_service or Phase2ProposalService()
    workflow_boundary = workflow_service or IssueWorkflowService(
        JsonIssueRecordStore(
            Path(os.getenv("ISSUE_STORE_PATH", "data/issue-records.json"))
        ),
        confirmation_verifier=proposal_boundary.verify_confirmation,
    )
    knowledge_boundary = knowledge_tool or SearchKnowledgeTool(
        enabled=os.getenv("KNOWLEDGE_ENABLED", "true").strip().casefold() == "true",
    )
    knowledge_builder = KnowledgeAnswerBuilder(knowledge_boundary)
    app = FastAPI(
        title="海之子 · 安全质量 Agent API",
        version="0.1.0",
        docs_url=None if customer_mode else "/docs",
        redoc_url=None if customer_mode else "/redoc",
        openapi_url=None if customer_mode else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_photo_router(photo_service or PhotoService(
        PhotoStore(Path(os.getenv("PHOTO_STORE_PATH", "uploads"))),
        proposal_boundary, workflow_boundary,
    )))
    app.include_router(create_product_router(text_service or TextConsultationService(proposal_boundary), workflow_boundary))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def get_runtime() -> dict[str, str]:
        mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
        if mode not in {"mock", "real"}:
            mode = "mock"
        return {"agent_mode": mode, **({} if customer_mode else runtime_info())}

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

    @app.post("/api/knowledge/search", response_model=ToolResult)
    def search_knowledge(payload: dict[str, Any]) -> ToolResult:
        return knowledge_boundary.run(payload)

    @app.post("/api/knowledge/answer", response_model=KnowledgeAnswer)
    def knowledge_answer(payload: dict[str, Any]) -> KnowledgeAnswer:
        try:
            request = KnowledgeAnswerRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False), strict=True,
            )
        except (TypeError, ValueError) as exc:
            raise _workflow_http_error(400, "invalid_arguments", "知识回答请求无效。", exc)
        return knowledge_builder.build(request)

    @app.post("/api/issue-records/{record_id}/knowledge", response_model=KnowledgeAnswer)
    def record_knowledge(record_id: str, payload: dict[str, Any]) -> KnowledgeAnswer:
        try:
            request = RecordKnowledgeRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False), strict=True,
            )
        except (TypeError, ValueError) as exc:
            raise _workflow_http_error(400, "invalid_arguments", "记录依据请求无效。", exc)
        try:
            return answer_for_record(record_id, request, workflow=workflow_boundary,
                                     builder=knowledge_builder)
        except RecordNotFoundError as exc:
            raise _workflow_http_error(404, "record_not_found", "问题记录不存在。", exc)
        except StoreError as exc:
            raise _workflow_http_error(500, "store_error", "问题记录暂时无法读取。", exc)

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

    @app.post(
        "/api/issue-records",
        response_model=CreateIssueRecordResponse,
    )
    def create_issue_record(payload: dict[str, Any]) -> CreateIssueRecordResponse:
        try:
            request = CreateIssueRecordRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False),
                strict=True,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "invalid_arguments",
                    "message": "问题记录创建请求参数无效。",
                },
            ) from exc
        try:
            return workflow_boundary.create_draft(request)
        except IdempotencyConflictError as exc:
            raise _workflow_http_error(
                409,
                "idempotency_conflict",
                "相同幂等键不能用于不同的创建请求。",
                exc,
            )
        except WorkflowRuleError as exc:
            raise _workflow_http_error(400, exc.code, exc.message, exc)
        except StoreError as exc:
            raise _workflow_http_error(
                500,
                "store_error",
                "问题记录暂时无法保存。",
                exc,
            )

    @app.get(
        "/api/issue-records/{record_id}",
        response_model=IssueRecord,
    )
    def get_issue_record(record_id: str) -> IssueRecord:
        try:
            return workflow_boundary.get(record_id)
        except RecordNotFoundError as exc:
            raise _workflow_http_error(
                404,
                "record_not_found",
                "问题记录不存在。",
                exc,
            )
        except StoreError as exc:
            raise _workflow_http_error(
                500,
                "store_error",
                "问题记录暂时无法读取。",
                exc,
            )

    @app.post(
        "/api/issue-records/{record_id}/actions",
        response_model=IssueRecord,
    )
    def transition_issue_record(
        record_id: str,
        payload: dict[str, Any],
    ) -> IssueRecord:
        try:
            request = WorkflowTransitionRequest.model_validate_json(
                json.dumps(payload, ensure_ascii=False),
                strict=True,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "invalid_arguments",
                    "message": "工作流动作请求参数无效。",
                },
            ) from exc
        try:
            return workflow_boundary.transition(record_id, request)
        except RecordNotFoundError as exc:
            raise _workflow_http_error(
                404,
                "record_not_found",
                "问题记录不存在。",
                exc,
            )
        except RevisionConflictError as exc:
            raise _workflow_http_error(
                409,
                "revision_conflict",
                "记录已经变化，请刷新后重试。",
                exc,
            )
        except WorkflowRuleError as exc:
            status_code = 403 if exc.code == "permission_denied" else 409
            raise _workflow_http_error(
                status_code,
                exc.code,
                exc.message,
                exc,
            )
        except StoreError as exc:
            raise _workflow_http_error(
                500,
                "store_error",
                "问题记录暂时无法更新。",
                exc,
            )

    return app


def _workflow_http_error(
    status_code: int,
    error_code: str,
    message: str,
    cause: Exception,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message},
    )


app = create_app()
