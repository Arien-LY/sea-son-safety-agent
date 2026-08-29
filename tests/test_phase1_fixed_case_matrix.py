import json
from pathlib import Path
from typing import Any

from agents.analysis import IssueAnalyzer
from agents.schemas import TextConsultationInput


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "phase1_acceptance_cases.v1.json"
RISK_ORDER = ("undetermined", "low", "medium", "high", "emergency")


class FixedCaseFakeLLM:
    """按固定案例返回预设协议结果，只验证离线闭环而非模型能力。"""

    def __init__(self, output: str) -> None:
        self._output = output
        self.calls: list[list[dict[str, str]]] = []

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        self.calls.append([message.copy() for message in messages])
        return self._output


def select_risk(case: dict[str, Any]) -> str:
    interval = case["expected_risk_interval"]
    if "high_risk" in case["challenge_tags"]:
        return interval["maximum"]
    return interval["minimum"]


def fake_analysis_payload(case: dict[str, Any]) -> dict[str, Any]:
    extract_points = [
        point["description"]
        for point in case["required_points"]
        if point["action"] == "extract"
    ]
    ask_points = [
        point["description"]
        for point in case["required_points"]
        if point["action"] == "ask"
    ]
    risk_level = select_risk(case)
    high_or_emergency = risk_level in {"high", "emergency"}
    uncertainties = [f"尚未获得：{description}" for description in ask_points]
    if risk_level == "undetermined" and not uncertainties:
        uncertainties = ["现有文字不足以判断风险"]
        ask_points = ["完成风险判断所需的现场信息"]

    return {
        "category": case["category"],
        "issue_type": "固定案例协议验收",
        "summary": case["user_input"],
        "observed_facts": extract_points,
        "uncertainties": uncertainties,
        "missing_fields": ask_points,
        "risk_level": risk_level,
        "immediate_actions": ["立即降低人员暴露并联系现场专业人员复核"]
        if high_or_emergency
        else [],
        "suggested_actions": [],
        "recommended_route": case["expected_route"],
        "requires_human_review": case["requires_human_review"],
        "confidence": 0.8,
    }


def test_all_twenty_fixed_cases_pass_offline_protocol_thresholds() -> None:
    suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    scores = {
        "category": 0,
        "risk_interval": 0,
        "route": 0,
        "human_review": 0,
        "required_points": 0,
        "no_tool_side_effect": 0,
    }

    for case in suite["cases"]:
        payload = fake_analysis_payload(case)
        fake_llm = FixedCaseFakeLLM(json.dumps(payload, ensure_ascii=False))
        result = IssueAnalyzer(fake_llm).analyze(
            TextConsultationInput(message=case["user_input"])
        )

        scores["category"] += result.category.value == case["category"]
        risk_rank = RISK_ORDER.index(result.risk_level.value)
        minimum_rank = RISK_ORDER.index(case["expected_risk_interval"]["minimum"])
        maximum_rank = RISK_ORDER.index(case["expected_risk_interval"]["maximum"])
        scores["risk_interval"] += minimum_rank <= risk_rank <= maximum_rank
        scores["route"] += result.recommended_route.value == case["expected_route"]
        scores["human_review"] += (
            result.requires_human_review == case["requires_human_review"]
        )

        output_points = set(result.observed_facts + result.missing_fields)
        expected_points = {
            point["description"] for point in case["required_points"]
        }
        scores["required_points"] += expected_points <= output_points

        messages = fake_llm.calls[0]
        scores["no_tool_side_effect"] += (
            [message["role"] for message in messages] == ["system", "user"]
            and all("tool" not in message["role"] for message in messages)
        )

    assert len(suite["cases"]) == 20
    assert scores == {metric: 20 for metric in scores}
