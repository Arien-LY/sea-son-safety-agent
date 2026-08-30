"""Photo metadata, human decisions and associations, separate from issue state."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from agents.vision import VisionAnalysis, VisionModel
from backend.app.workflow_models import WorkflowActor


class PhotoMetadata(VisionModel):
    photo_id: str = Field(pattern=r"^PHOTO-[A-F0-9]{24}$")
    content_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    media_type: Literal["image/jpeg"] = "image/jpeg"
    byte_size: int = Field(gt=0, le=5 * 1024 * 1024)
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    metadata_removed: Literal[True] = True
    created_at: datetime


class AnalyzePhotoRequest(VisionModel):
    context: str = Field(default="请初步核对图片中的可见情况。", min_length=1, max_length=1000)
    allow_external: bool = False


class PhotoAnalysisRecord(VisionModel):
    analysis_id: str = Field(pattern=r"^VIS-[A-F0-9]{24}$")
    photo_id: str = Field(pattern=r"^PHOTO-[A-F0-9]{24}$")
    mode: Literal["mock", "real"]
    model: str
    result: VisionAnalysis
    created_at: datetime


class CandidateDecisionRequest(VisionModel):
    candidate_id: str = Field(pattern=r"^CAND-[1-5]$")
    decision: Literal["accept", "reject"]
    corrected_summary: str | None = Field(default=None, min_length=1, max_length=500)
    note: str = Field(min_length=1, max_length=300)
    confirmed: Literal[True]


class CandidateDecision(VisionModel):
    analysis_id: str
    request: CandidateDecisionRequest
    created_at: datetime


class LinkPhotoRequest(VisionModel):
    photo_id: str = Field(pattern=r"^PHOTO-[A-F0-9]{24}$")
    stage: Literal["before", "after"]
    actor: WorkflowActor
    expected_revision: int = Field(ge=1)
    confirmed: Literal[True]


class PhotoLink(VisionModel):
    record_id: str = Field(pattern=r"^ISS-[A-F0-9]{12}$")
    photo_id: str = Field(pattern=r"^PHOTO-[A-F0-9]{24}$")
    stage: Literal["before", "after"]
    actor: WorkflowActor
    record_revision: int = Field(ge=1)
    created_at: datetime


class PhotoDocument(VisionModel):
    schema_version: Literal["phase5-photo-store-v1"] = "phase5-photo-store-v1"
    photos: dict[str, PhotoMetadata] = Field(default_factory=dict, max_length=200)
    analyses: dict[str, PhotoAnalysisRecord] = Field(default_factory=dict, max_length=2000)
    decisions: list[CandidateDecision] = Field(default_factory=list, max_length=10_000)
    links: dict[str, PhotoLink] = Field(default_factory=dict, max_length=200)

    @model_validator(mode="after")
    def references(self) -> "PhotoDocument":
        if any(key != photo.photo_id for key, photo in self.photos.items()):
            raise ValueError("Photo key mismatch.")
        if any(key != item.analysis_id or item.photo_id not in self.photos for key, item in self.analyses.items()):
            raise ValueError("Invalid analysis reference.")
        if any(key != link.photo_id or key not in self.photos for key, link in self.links.items()):
            raise ValueError("Invalid photo link.")
        seen = set()
        for item in self.decisions:
            record = self.analyses.get(item.analysis_id)
            key = (item.analysis_id, item.request.candidate_id)
            if record is None or key in seen or not any(
                candidate.candidate_id == item.request.candidate_id for candidate in record.result.candidates
            ):
                raise ValueError("Invalid or duplicate human decision reference.")
            seen.add(key)
        if any(sum(item.photo_id == photo_id for item in self.analyses.values()) > 10 for photo_id in self.photos):
            raise ValueError("Too many analyses for one photo.")
        return self
