"""Rebuild deterministic, synthetic-only Phase 6 fixtures, schemas and reports."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.models import EvaluationCaseTrace, EvaluationReport, EvaluationRun  # noqa: E402
from evaluation.scoring import build_report, render_report  # noqa: E402

CASES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "phase1_acceptance_cases.v1.json"
SUCCESS_RUN_PATH = PROJECT_ROOT / "tests" / "fixtures" / "phase6_protocol_run.v1.json"
FAILURE_RUN_PATH = PROJECT_ROOT / "tests" / "fixtures" / "phase6_failure_run.v1.json"
EVALUATED_AT = datetime.fromisoformat("2026-08-31T12:00:00+08:00")


def success_trace(case: dict, index: int) -> dict:
    workflow_expected = case["expected_route"] in {"propose_workflow", "human_review"}
    events = [
        {"sequence": 1, "stage": "input_validated", "elapsed_ms": 0},
        {"sequence": 2, "stage": "model_called", "elapsed_ms": 5 + index},
        {"sequence": 3, "stage": "output_validated", "elapsed_ms": 10 + index},
    ]
    if workflow_expected:
        events.append({
            "sequence": 4, "stage": "tool_called", "elapsed_ms": 11 + index,
            "tool_name": "propose_issue_record",
        })
    events.append({
        "sequence": len(events) + 1, "stage": "completed", "elapsed_ms": 12 + index,
    })
    risk = case["expected_risk_interval"]["maximum"] \
        if "high_risk" in case["challenge_tags"] else case["expected_risk_interval"]["minimum"]
    return {
        "trace_id": f"TRACE-PROTOCOL-{index:03d}", "case_id": case["id"],
        "input_digest": "sha256:" + hashlib.sha256(case["user_input"].encode("utf-8")).hexdigest(),
        "status": "success", "duration_ms": 12 + index, "events": events,
        "actual_category": case["category"], "actual_risk": risk,
        "actual_route": case["expected_route"],
        "actual_human_review": case["requires_human_review"],
        "captured_point_keys": [point["key"] for point in case["required_points"]],
        "tool_behavior": "proposal_only" if workflow_expected else "not_called",
        "false_citation_count": 0, "unauthorized_state_change_count": 0,
        "privacy_leak_count": 0, "workflow_closed": None,
        "prompt_tokens": None, "completion_tokens": None, "cost_micro_usd": None,
        "error_code": None,
    }


def build_run(*, failed: bool) -> EvaluationRun:
    suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    traces = [success_trace(case, index) for index, case in enumerate(suite["cases"], 1)]
    if failed:
        failure_index = next(
            index for index, case in enumerate(suite["cases"])
            if "high_risk" in case["challenge_tags"]
        )
        trace = traces[failure_index]
        trace.update(
            trace_id="TRACE-FAILURE-001", status="failure", duration_ms=7,
            events=[
                {"sequence": 1, "stage": "input_validated", "elapsed_ms": 0},
                {"sequence": 2, "stage": "model_called", "elapsed_ms": 5},
                {"sequence": 3, "stage": "failed", "elapsed_ms": 7, "error_code": "model_timeout"},
            ],
            actual_category=None, actual_risk=None, actual_route=None, actual_human_review=None,
            captured_point_keys=[], tool_behavior="not_observed", error_code="model_timeout",
        )
    return EvaluationRun.model_validate({
        "schema_version": "phase6-evaluation-run-v1",
        "run_id": "RUN-PROTOCOL-FAILURE-001" if failed else "RUN-PROTOCOL-SUCCESS-001",
        "run_kind": "synthetic_protocol", "evaluated_at": EVALUATED_AT,
        "suite_id": "phase1-fixed-text-v1", "cases": traces,
    }, strict=True)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    success, failure = build_run(failed=False), build_run(failed=True)
    SUCCESS_RUN_PATH.write_text(success.model_dump_json(indent=2) + "\n", encoding="utf-8")
    FAILURE_RUN_PATH.write_text(failure.model_dump_json(indent=2) + "\n", encoding="utf-8")
    write_json(PROJECT_ROOT / "contracts" / "phase6_evaluation_trace.v1.schema.json",
               EvaluationCaseTrace.model_json_schema())
    write_json(PROJECT_ROOT / "contracts" / "phase6_evaluation_run.v1.schema.json",
               EvaluationRun.model_json_schema())
    write_json(PROJECT_ROOT / "contracts" / "phase6_evaluation_report.v1.schema.json",
               EvaluationReport.model_json_schema())
    (PROJECT_ROOT / "docs" / "phase6-protocol-report.v1.json").write_text(
        render_report(build_report(success)), encoding="utf-8",
    )
    (PROJECT_ROOT / "docs" / "phase6-failure-report.v1.json").write_text(
        render_report(build_report(failure)), encoding="utf-8",
    )
    print("Rebuilt Phase 6 synthetic protocol fixtures, schemas, and reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
