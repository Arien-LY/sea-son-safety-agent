"""Thin HTTP routes; image processing and model invocation stay in services."""

import json

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from agents.vision import VisionError
from backend.app.photo_models import AnalyzePhotoRequest, CandidateDecisionRequest, LinkPhotoRequest
from backend.app.photo_store import MAX_PHOTO_BYTES, PhotoError
from backend.app.photos import PhotoService, runtime_vision_info
from backend.app.workflow_store import RecordNotFoundError, RevisionConflictError, StoreError


def create_photo_router(service: PhotoService) -> APIRouter:
    router = APIRouter()

    def call(action, *args):
        try:
            return action(*args)
        except (PhotoError, VisionError) as exc:
            raise HTTPException(status_code=getattr(exc, "status", 503),
                                detail={"error_code": exc.code, "message": exc.message}) from exc
        except RecordNotFoundError as exc:
            raise HTTPException(404, detail={"error_code": "record_not_found", "message": "问题记录不存在。"}) from exc
        except RevisionConflictError as exc:
            raise HTTPException(409, detail={"error_code": "revision_conflict", "message": "记录已变化，请刷新后重试。"}) from exc
        except StoreError as exc:
            raise HTTPException(500, detail={"error_code": "store_error", "message": "记录存储暂不可用。"}) from exc

    def parse(model: type[BaseModel], payload: dict):
        try:
            return model.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, detail={"error_code": "invalid_arguments", "message": "图片请求参数无效。"}) from exc

    @router.get("/api/vision/runtime")
    def vision_runtime():
        return runtime_vision_info()

    @router.post("/api/photos")
    async def upload_photo(request: Request):
        if request.headers.get("x-upload-authorized") != "true":
            raise HTTPException(403, detail={"error_code": "upload_consent_required", "message": "请确认图片已脱敏且有权上传。"})
        media_type = request.headers.get("content-type", "").split(";")[0]
        if media_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(415, detail={"error_code": "unsupported_image_type", "message": "只接收一张JPEG或PNG原始图片。"})
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_PHOTO_BYTES:
                raise HTTPException(413, detail={"error_code": "image_size_limit", "message": "图片不得超过5MiB。"})
            raw.extend(chunk)
        return await run_in_threadpool(call, service.store.upload, bytes(raw), media_type)

    @router.get("/api/photos/{photo_id}/content")
    def photo_content(photo_id: str):
        _, jpeg = call(service.store.read, photo_id)
        return Response(jpeg, media_type="image/jpeg", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="sanitized-photo.jpg"',
        })

    @router.post("/api/photos/{photo_id}/analysis")
    def analyze_photo(photo_id: str, payload: dict):
        return call(service.analyze, photo_id, parse(AnalyzePhotoRequest, payload))

    @router.post("/api/photo-analyses/{analysis_id}/decisions")
    def decide_candidate(analysis_id: str, payload: dict):
        return call(service.decide, analysis_id, parse(CandidateDecisionRequest, payload))

    @router.post("/api/issue-records/{record_id}/photos")
    def link_photo(record_id: str, payload: dict):
        return call(service.link, record_id, parse(LinkPhotoRequest, payload))

    @router.get("/api/issue-records/{record_id}/photos")
    def list_photos(record_id: str):
        return call(service.linked, record_id)

    return router
