import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.models import EvaluationCaseTrace, EvaluationReport, EvaluationRun
from evaluation.scoring import build_report, load_run, render_report


ROOT = Path(__file__).resolve().parents[1]
SUCCESS = ROOT / "tests" / "fixtures" / "phase6_protocol_run.v1.json"
FAILURE = ROOT / "tests" / "fixtures" / "phase6_failure_run.v1.json"


def raw_run(path: Path = SUCCESS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json_run(payload: dict) -> EvaluationRun:
    return EvaluationRun.model_validate_json(json.dumps(payload, ensure_ascii=False), strict=True)


def test_frozen_phase6_schemas_match_strict_models() -> None:
    schemas = {
        "phase6_evaluation_trace.v1.schema.json": EvaluationCaseTrace.model_json_schema(),
        "phase6_evaluation_run.v1.schema.json": EvaluationRun.model_json_schema(),
        "phase6_evaluation_report.v1.schema.json": EvaluationReport.model_json_schema(),
    }
    for filename, expected in schemas.items():
        actual = json.loads((ROOT / "contracts" / filename).read_text(encoding="utf-8"))
        assert actual == expected
        assert actual["additionalProperties"] is False


def test_synthetic_success_report_passes_protocol_gates_without_claiming_real_metrics() -> None:
    run = load_run(SUCCESS)
    report = build_report(run)
    assert len(run.cases) == 20 and all(trace.status == "success" for trace in run.cases)
    assert report.overall_passed is True
    assert report.successful_cases == 20 and report.failed_cases == 0
    assert all(metric.basis_points == 10_000 for metric in (
        report.quality.classification_accuracy, report.quality.field_completeness,
        report.quality.high_risk_recall, report.quality.workflow_route_accuracy,
        report.quality.tool_call_accuracy,
    ))
    assert report.engineering.failure_rate.basis_points == 0
    assert report.engineering.failure_rate.passed is True
    assert report.engineering.token_usage.status == "not_measured"
    assert report.engineering.call_cost.status == "not_measured"
    assert report.engineering.task_closure_rate.status == "not_measured"
    assert any("不代表真实模型" in limitation for limitation in report.limitations)
    assert render_report(report) == (ROOT / "docs" / "phase6-protocol-report.v1.json").read_text(encoding="utf-8")


def test_saved_failure_trace_is_reproducible_and_fails_high_risk_gate() -> None:
    run = load_run(FAILURE)
    failed = [trace for trace in run.cases if trace.status == "failure"]
    assert len(failed) == 1
    assert failed[0].events[-1].stage == "failed"
    assert failed[0].error_code == "model_timeout"
    report = build_report(run)
    assert report.failed_cases == 1
    assert report.safety.high_risk_misses.value == 1
    assert report.quality.high_risk_recall.passed is False
    assert report.engineering.failure_rate.basis_points == 500
    assert report.engineering.failure_rate.passed is True
    assert report.overall_passed is False
    assert render_report(report) == (ROOT / "docs" / "phase6-failure-report.v1.json").read_text(encoding="utf-8")


def test_trace_contract_rejects_raw_output_extra_fields_and_inconsistent_events() -> None:
    payload = raw_run()
    payload["cases"][0]["raw_model_output"] = "PRIVATE-secret-model-content"
    with pytest.raises(ValidationError):
        validate_json_run(payload)

    payload = raw_run()
    payload["cases"][0]["events"][1]["sequence"] = 9
    with pytest.raises(ValidationError):
        validate_json_run(payload)

    payload = raw_run()
    payload["cases"][0]["status"] = "failure"
    with pytest.raises(ValidationError):
        validate_json_run(payload)


def test_run_rejects_duplicate_cases_and_scorer_rejects_digest_or_point_forgery() -> None:
    payload = raw_run()
    payload["cases"][-1] = deepcopy(payload["cases"][0])
    payload["cases"][-1]["trace_id"] = "TRACE-DUPLICATE-999"
    with pytest.raises(ValidationError):
        validate_json_run(payload)

    payload = raw_run()
    payload["cases"][0]["input_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="input digest mismatch"):
        build_report(validate_json_run(payload))

    payload = raw_run()
    payload["cases"][0]["captured_point_keys"].append("invented_point")
    with pytest.raises(ValueError, match="unknown captured point"):
        build_report(validate_json_run(payload))


def test_usage_cost_and_closure_are_measured_only_when_complete() -> None:
    payload = raw_run()
    payload["run_id"] = "RUN-COMPLETE-ENGINEERING-001"
    for trace in payload["cases"]:
        trace["prompt_tokens"], trace["completion_tokens"], trace["cost_micro_usd"] = 10, 5, 0
        if trace["tool_behavior"] == "proposal_only":
            trace["workflow_closed"] = True
    report = build_report(validate_json_run(payload))
    assert report.engineering.token_usage.status == "measured"
    assert report.engineering.token_usage.total == 300
    assert report.engineering.call_cost.status == "measured"
    assert report.engineering.call_cost.total == 0
    assert report.engineering.task_closure_rate.basis_points == 10_000


def test_cli_generates_the_same_report_without_model_or_network(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [str(ROOT / ".venv" / "Scripts" / "python.exe"),
         str(ROOT / "scripts" / "evaluate-phase6.py"),
         "--run", str(SUCCESS), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.read_bytes() == (ROOT / "docs" / "phase6-protocol-report.v1.json").read_bytes()
    source = (ROOT / "scripts" / "evaluate-phase6.py").read_text(encoding="utf-8")
    assert "OpenAI" not in source and ".env" not in source and "http" not in source
