"""Deterministic evidence assembly; the model never authors citation metadata."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from agents.analysis import IssueAnalyzer
from agents.knowledge import (
    HumanConclusion, Jurisdiction, KnowledgeCitation, KnowledgeModel,
    KnowledgeSearchData, SearchKnowledgeRequest,
)
from agents.schemas import IssueAnalysis, IssueCategory, TextConsultationInput
from agents.tools.search_knowledge import SearchKnowledgeTool

NO_EVIDENCE = "未找到可用依据，请由专业人员核对；不得据此认定合规或编造条款。"


class KnowledgeAnswerRequest(KnowledgeModel):
    analysis: IssueAnalysis
    query: str = Field(min_length=1, max_length=1_000)
    jurisdiction: Jurisdiction = "unknown"


class RecordKnowledgeRequest(KnowledgeModel):
    query: str = Field(min_length=1, max_length=1_000)
    jurisdiction: Jurisdiction = "unknown"


class KnowledgeAnswer(KnowledgeModel):
    schema_version: Literal["phase4-knowledge-answer-v1"] = "phase4-knowledge-answer-v1"
    analysis: IssueAnalysis
    model_suggestions: list[str]
    suggestion_notice: str = "以下是未核验建议，不是规范原文、检索依据或人工结论。"
    retrieved_evidence: list[KnowledgeCitation] = Field(max_length=3)
    evidence_notice: str
    human_conclusion: HumanConclusion = Field(default_factory=HumanConclusion)
    knowledge_status: Literal["matched", "no_results", "unavailable"]
    knowledge_error_code: str | None = None


class KnowledgeAnswerBuilder:
    def __init__(self, tool: SearchKnowledgeTool) -> None:
        self.tool = tool

    def build(self, request: KnowledgeAnswerRequest) -> KnowledgeAnswer:
        # A general consultation is not a knowledge domain. Let the bounded query
        # match domain material, without rewriting the original analysis category.
        category = request.analysis.category
        if category in {IssueCategory.CONSULTATION, IssueCategory.UNKNOWN}:
            category = None
        search = SearchKnowledgeRequest(
            query=request.query, category=category,
            jurisdiction=request.jurisdiction,
        )
        result = self.tool.run(search.model_dump(mode="json"))
        data = KnowledgeSearchData.model_validate_json(
            json.dumps(result.data, ensure_ascii=False)
        ) if result.ok else None
        citations = data.citations if data else []
        return KnowledgeAnswer(
            analysis=request.analysis,
            model_suggestions=request.analysis.suggested_actions,
            retrieved_evidence=citations,
            evidence_notice=(
                "以下为候选法规释义摘编，不是逐字原文；命中不代表违法、合规或责任认定。"
                if citations else NO_EVIDENCE
            ),
            knowledge_status=data.status if data else "unavailable",
            knowledge_error_code=result.error_code,
        )


class KnowledgeAssistedAnalyzer:
    """One existing analysis call, then offline retrieval; no new model loop."""

    def __init__(self, analyzer: IssueAnalyzer, builder: KnowledgeAnswerBuilder) -> None:
        self._analyzer = analyzer
        self._builder = builder

    def analyze(
        self, input_data: TextConsultationInput, *, jurisdiction: Jurisdiction = "unknown",
    ) -> KnowledgeAnswer:
        analysis = self._analyzer.analyze(input_data)
        return self._builder.build(KnowledgeAnswerRequest(
            analysis=analysis, query=input_data.message, jurisdiction=jurisdiction,
        ))
