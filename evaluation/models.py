"""Strict, privacy-minimizing contracts for Phase 6 traces and reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TraceEvent(EvaluationModel):
    sequence: int = Field(ge=1, le=20)
    stage: Literal[
        "input_validated", "model_called", "output_validated", "tool_called", "completed", "failed"
    ]
    elapsed_ms: int = Field(ge=0, le=300_000)
    tool_name: Literal["propose_issue_record"] | None = None
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,63}$")

    @model_validator(mode="after")
    def stage_fields_match(self) -> "TraceEvent":
        if (self.stage == "tool_called") != (self.tool_name is not None):
            raise ValueError("tool_name is required only for tool_called events")
        if (self.stage == "failed") != (self.error_code is not None):
            raise ValueError("error_code is required only for failed events")
        return self


class EvaluationCaseTrace(EvaluationModel):
    trace_id: str = Field(pattern=r"^TRACE-[A-Z0-9-]{8,48}$")
    case_id: str = Field(pattern=r"^(CONS|SAFE|QUAL|MGMT|LOGI)-00[1-4]$")
    input_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["success", "failure"]
    duration_ms: int = Field(ge=0, le=300_000)
    events: list[TraceEvent] = Field(min_length=2, max_length=20)
    actual_category: Literal[
        "consultation", "safety", "quality", "management", "logistics", "unknown"
    ] | None = None
    actual_risk: Literal["undetermined", "low", "medium", "high", "emergency"] | None = None
    actual_route: Literal[
        "direct_answer", "collect_more_info", "propose_workflow", "human_review"
    ] | None = None
    actual_human_review: bool | None = None
    captured_point_keys: list[str] = Field(default_factory=list, max_length=30)
    tool_behavior: Literal[
        "not_called", "proposal_only", "unexpected_call", "unauthorized_state_change", "not_observed"
    ]
    false_citation_count: int = Field(default=0, ge=0, le=100)
    unauthorized_state_change_count: int = Field(default=0, ge=0, le=100)
    privacy_leak_count: int = Field(default=0, ge=0, le=100)
    workflow_closed: bool | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    cost_micro_usd: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,63}$")

    @model_validator(mode="after")
    def trace_is_consistent(self) -> "EvaluationCaseTrace":
        if [event.sequence for event in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError("trace event sequences must be contiguous")
        elapsed = [event.elapsed_ms for event in self.events]
        if elapsed != sorted(elapsed) or elapsed[-1] > self.duration_ms:
            raise ValueError("trace elapsed time must be monotonic and within duration")
        if self.events[0].stage != "input_validated":
            raise ValueError("trace must begin with input validation")
        final_stage = self.events[-1].stage
        stages = {event.stage for event in self.events}
        output = (self.actual_category, self.actual_risk, self.actual_route, self.actual_human_review)
        if self.status == "success":
            if final_stage != "completed" or self.error_code is not None or any(value is None for value in output):
                raise ValueError("successful traces require validated output and a completed event")
            if not {"model_called", "output_validated"} <= stages or self.tool_behavior == "not_observed":
                raise ValueError("successful traces require model and output validation stages")
            if ("tool_called" in stages) != (self.tool_behavior != "not_called"):
                raise ValueError("tool event and tool behavior must agree")
        elif final_stage != "failed" or self.error_code is None or any(value is not None for value in output):
            raise ValueError("failed traces require an error and no scored output")
        elif self.events[-1].error_code != self.error_code or self.captured_point_keys \
                or self.tool_behavior != "not_observed" or self.workflow_closed is not None:
            raise ValueError("failed trace fields must match the terminal error")
        if len(self.captured_point_keys) != len(set(self.captured_point_keys)):
            raise ValueError("captured point keys must be unique")
        return self


class EvaluationRun(EvaluationModel):
    schema_version: Literal["phase6-evaluation-run-v1"]
    run_id: str = Field(pattern=r"^RUN-[A-Z0-9-]{8,48}$")
    run_kind: Literal["synthetic_protocol", "real_model", "human_adjudicated"]
    evaluated_at: datetime
    suite_id: Literal["phase1-fixed-text-v1"]
    cases: list[EvaluationCaseTrace] = Field(min_length=20, max_length=20)

    @model_validator(mode="after")
    def case_and_trace_ids_are_unique(self) -> "EvaluationRun":
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must include an explicit timezone")
        if len({case.case_id for case in self.cases}) != 20:
            raise ValueError("a run must contain 20 unique cases")
        if len({case.trace_id for case in self.cases}) != 20:
            raise ValueError("trace IDs must be unique")
        return self


class RateMetric(EvaluationModel):
    status: Literal["measured", "not_measured"]
    direction: Literal["minimum", "maximum"] | None = None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=1)
    basis_points: int | None = Field(default=None, ge=0, le=10_000)
    threshold_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    passed: bool | None = None

    @model_validator(mode="after")
    def measurement_is_consistent(self) -> "RateMetric":
        values = (self.numerator, self.denominator, self.basis_points, self.direction)
        if self.status == "not_measured":
            if any(value is not None for value in values) or self.threshold_basis_points is not None or self.passed is not None:
                raise ValueError("not_measured rates cannot contain a value or verdict")
            return self
        if any(value is None for value in values):
            raise ValueError("measured rates require numerator, denominator, basis points and direction")
        expected = (self.numerator * 10_000 + self.denominator // 2) // self.denominator
        if self.basis_points != expected:
            raise ValueError("rate basis points do not match numerator and denominator")
        if self.threshold_basis_points is None:
            if self.passed is not None:
                raise ValueError("informational rates cannot have a verdict")
        else:
            expected_pass = self.basis_points >= self.threshold_basis_points \
                if self.direction == "minimum" else self.basis_points <= self.threshold_basis_points
            if self.passed is not expected_pass:
                raise ValueError("rate verdict does not match threshold direction")
        return self


class CountMetric(EvaluationModel):
    value: int = Field(ge=0)
    maximum_allowed: int = Field(ge=0)
    passed: bool


class LatencyMetric(EvaluationModel):
    status: Literal["measured", "not_measured"]
    p50_ms: int | None = Field(default=None, ge=0)
    p95_ms: int | None = Field(default=None, ge=0)
    max_ms: int | None = Field(default=None, ge=0)


class UsageMetric(EvaluationModel):
    status: Literal["measured", "not_measured"]
    total: int | None = Field(default=None, ge=0)
    unit: Literal["tokens", "micro_usd"]


class QualityMetrics(EvaluationModel):
    classification_accuracy: RateMetric
    field_completeness: RateMetric
    high_risk_recall: RateMetric
    workflow_route_accuracy: RateMetric
    tool_call_accuracy: RateMetric


class SafetyMetrics(EvaluationModel):
    false_citations: CountMetric
    high_risk_misses: CountMetric
    unauthorized_state_changes: CountMetric
    privacy_leaks: CountMetric


class EngineeringMetrics(EvaluationModel):
    response_time: LatencyMetric
    failure_rate: RateMetric
    token_usage: UsageMetric
    call_cost: UsageMetric
    task_closure_rate: RateMetric


class EvaluationReport(EvaluationModel):
    schema_version: Literal["phase6-evaluation-report-v1"]
    run_id: str
    run_kind: Literal["synthetic_protocol", "real_model", "human_adjudicated"]
    evaluated_at: datetime
    suite_id: Literal["phase1-fixed-text-v1"]
    total_cases: Literal[20]
    successful_cases: int = Field(ge=0, le=20)
    failed_cases: int = Field(ge=0, le=20)
    quality: QualityMetrics
    safety: SafetyMetrics
    engineering: EngineeringMetrics
    overall_passed: bool
    limitations: list[str] = Field(min_length=1, max_length=10)
