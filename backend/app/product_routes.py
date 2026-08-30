"""Thin text routes and a read-only paginated record index."""

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from agents.text_assistant import TextError
from backend.app.text_consultations import TextConsultationService, text_runtime
from backend.app.text_models import TextProposalRequest, TextRequest, TextResponse
from backend.app.text_progress import stream_operation
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_models import RecordDisposition, WorkflowStatus
from backend.app.workflow_store import StoreError


class RecordQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    q: str = Field(default="", max_length=100)
    category: Literal["safety", "quality", "management", "logistics"] | None = None
    status: WorkflowStatus | None = None
    disposition: RecordDisposition | None = None
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=20, ge=1, le=50)


def list_records(workflow: IssueWorkflowService, query: RecordQuery) -> dict:
    records = list(workflow.store.snapshot())
    if query.category:
        records = [r for r in records if r.analysis.category == query.category]
    if query.status:
        records = [r for r in records if r.status == query.status]
    if query.disposition:
        records = [r for r in records if r.disposition == query.disposition]
    if query.q:
        records = [r for r in records if query.q.casefold() in " ".join([
            r.record_id, r.review_fields.record_title, r.review_fields.record_description,
            r.review_fields.project or "", r.review_fields.area or "",
        ]).casefold()]
    records.sort(key=lambda r: r.record_id)
    records.sort(key=lambda r: r.updated_at, reverse=True)
    return {"total": len(records), "offset": query.offset, "limit": query.limit, "items": [
        {"record_id": r.record_id, "title": r.review_fields.record_title, "project": r.review_fields.project,
         "area": r.review_fields.area, "category": r.analysis.category, "risk_level": r.analysis.risk_level,
         "status": r.status, "disposition": r.disposition, "revision": r.revision, "updated_at": r.updated_at}
        for r in records[query.offset:query.offset + query.limit]]}


def create_product_router(texts: TextConsultationService, workflow: IssueWorkflowService) -> APIRouter:
    router = APIRouter()

    def parse(model, payload):
        try:
            return model.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, detail={"error_code": "invalid_arguments", "message": "文字请求参数无效。"}) from exc

    def call(action, *args):
        try:
            return action(*args)
        except TextError as exc:
            raise HTTPException(exc.status, detail={"error_code": exc.code, "message": exc.message}) from exc

    @router.get("/api/text/runtime")
    def runtime():
        return text_runtime()

    @router.post("/api/text-consultations", response_model=TextResponse)
    def send(payload: dict):
        return call(texts.send, parse(TextRequest, payload))

    @router.post("/api/text-consultations/stream")
    def send_stream(payload: dict):
        return stream_operation(texts.send, parse(TextRequest, payload))

    @router.post("/api/text-consultations/{consultation_id}/proposal/stream")
    def propose_stream(consultation_id: str, payload: dict):
        return stream_operation(texts.propose, consultation_id, parse(TextProposalRequest, payload))

    @router.post("/api/text-consultations/{consultation_id}/proposal")
    def propose(consultation_id: str, payload: dict):
        return call(texts.propose, consultation_id, parse(TextProposalRequest, payload))

    @router.get("/api/issue-records")
    def records(request: Request):
        try:
            values = dict(request.query_params)
            if len(request.query_params.multi_items()) != len(values):
                raise ValueError("Repeated query keys")
            query = RecordQuery.model_validate(values)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, detail={"error_code": "invalid_query", "message": "列表筛选参数无效。"}) from exc
        try:
            return list_records(workflow, query)
        except StoreError as exc:
            raise HTTPException(500, detail={"error_code": "store_error", "message": "工单列表暂时无法读取。"}) from exc

    return router
