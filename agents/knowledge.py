"""Small, offline knowledge catalog: validation, filtering and deterministic citations."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.schemas import IssueCategory

CATALOG_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "catalog.v1.json"
Jurisdiction = Literal["unknown", "cn_mainland", "overseas"]


class KnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class KnowledgeSource(KnowledgeModel):
    source_id: str = Field(pattern=r"^SRC-[A-Z0-9-]{1,60}$")
    title: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=200)
    updated_on: date
    authorization: Literal["public_legal_text"]

    @field_validator("url")
    @classmethod
    def official_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in {"hbj.nea.gov.cn", "www.samr.gov.cn"}
            or not parsed.path.endswith(".html")
            or parsed.query or parsed.fragment
        ):
            raise ValueError("Source must use an approved official HTTPS origin.")
        return value


class KnowledgeEntry(KnowledgeModel):
    entry_id: str = Field(pattern=r"^KB-[A-Z]{3}-[0-9]{3}$")
    source_id: str = Field(pattern=r"^SRC-[A-Z0-9-]{1,60}$")
    locator: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=500)
    content_kind: Literal["paraphrase"]
    categories: list[IssueCategory] = Field(min_length=1, max_length=6)
    scope: str = Field(min_length=1, max_length=300)
    jurisdiction: Literal["cn_mainland"]
    keywords: list[str] = Field(min_length=1, max_length=20)
    reviewed_on: date
    review_due_on: date
    status: Literal["active", "withdrawn"]

    @field_validator("keywords")
    @classmethod
    def bounded_keywords(cls, words: list[str]) -> list[str]:
        normalized = [normalize(word.strip()) for word in words]
        if any(not 2 <= len(word) <= 50 for word in normalized):
            raise ValueError("Keywords must contain 2 to 50 characters.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate keywords.")
        return normalized

    @model_validator(mode="after")
    def review_window(self) -> "KnowledgeEntry":
        if self.review_due_on <= self.reviewed_on:
            raise ValueError("Review deadline must follow the ingestion review.")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("Duplicate categories.")
        return self


class KnowledgeCatalog(KnowledgeModel):
    schema_version: Literal["phase4-knowledge-v1"]
    sources: list[KnowledgeSource] = Field(min_length=1, max_length=20)
    entries: list[KnowledgeEntry] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def references(self) -> "KnowledgeCatalog":
        sources = {source.source_id: source for source in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("Duplicate source ID.")
        if len({entry.entry_id for entry in self.entries}) != len(self.entries):
            raise ValueError("Duplicate entry ID.")
        for entry in self.entries:
            if entry.source_id not in sources:
                raise ValueError("Unknown source ID.")
            if sources[entry.source_id].updated_on > entry.reviewed_on:
                raise ValueError("Source version is newer than its review.")
        return self


class SearchKnowledgeRequest(KnowledgeModel):
    query: str = Field(min_length=1, max_length=1_000)
    category: IssueCategory | None = None
    jurisdiction: Jurisdiction = "unknown"
    limit: int = Field(default=3, ge=1, le=3)


class KnowledgeCitation(KnowledgeModel):
    entry: KnowledgeEntry
    source: KnowledgeSource
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class KnowledgeSearchData(KnowledgeModel):
    status: Literal["matched", "no_results"]
    citations: list[KnowledgeCitation] = Field(max_length=3)
    excluded_count: int = Field(ge=0)
    as_of: date


class HumanConclusion(KnowledgeModel):
    status: Literal["not_reviewed", "reviewed"] = "not_reviewed"
    record_id: str | None = None
    revision: int | None = Field(default=None, ge=1)
    actor_id: str | None = None
    actor_role: str | None = None
    occurred_at: datetime | None = None
    note: str | None = None

    @model_validator(mode="after")
    def complete_review(self) -> "HumanConclusion":
        fields = (self.record_id, self.revision, self.actor_id, self.actor_role,
                  self.occurred_at, self.note)
        if self.status == "reviewed" and not all(fields):
            raise ValueError("Reviewed conclusion requires an authoritative event.")
        if self.status == "not_reviewed" and any(value is not None for value in fields):
            raise ValueError("Unreviewed conclusion cannot contain review claims.")
        return self


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def load_catalog(path: Path = CATALOG_PATH) -> KnowledgeCatalog:
    # Bound memory even if the operator accidentally selects a very large file.
    with path.open("rb") as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Knowledge catalog exceeds the local size limit.")
    return KnowledgeCatalog.model_validate_json(raw)


def make_citation(entry: KnowledgeEntry, source: KnowledgeSource) -> KnowledgeCitation:
    canonical = json.dumps(
        {"entry": entry.model_dump(mode="json"), "source": source.model_dump(mode="json")},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return KnowledgeCitation(
        entry=entry, source=source,
        content_digest=f"sha256:{hashlib.sha256(canonical).hexdigest()}",
    )


def retrieve(
    catalog: KnowledgeCatalog, request: SearchKnowledgeRequest, *, as_of: date,
) -> KnowledgeSearchData:
    query = normalize(request.query)
    matches: list[tuple[int, KnowledgeEntry]] = []
    excluded = 0
    for entry in catalog.entries:
        if (
            entry.status != "active"
            or not entry.reviewed_on <= as_of < entry.review_due_on
            or request.jurisdiction != entry.jurisdiction
            or (request.category is not None and request.category not in entry.categories)
        ):
            excluded += 1
            continue
        score = sum(word in query for word in entry.keywords)
        if score:
            matches.append((score, entry))
    matches.sort(key=lambda item: (-item[0], item[1].entry_id))
    sources = {source.source_id: source for source in catalog.sources}
    citations = [make_citation(entry, sources[entry.source_id])
                 for _, entry in matches[:request.limit]]
    return KnowledgeSearchData(
        status="matched" if citations else "no_results", citations=citations,
        excluded_count=excluded, as_of=as_of,
    )
