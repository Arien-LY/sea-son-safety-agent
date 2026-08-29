import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from hello_agents import HelloAgentsLLM

from agents.proposal_agent import IssueProposalAgent
from agents.schemas import IssueAnalysis


def issue_payload(
    *, recommended_route: str = "propose_workflow", risk_level: str = "medium"
) -> dict[str, Any]:
    high_risk = risk_level in {"high", "emergency"}
    return {
        "category": "safety",
        "issue_type": "临边防护",
        "summary": "用户报告作业层临边防护缺失，需要现场跟进。",
        "observed_facts": ["用户报告作业层临边没有防护栏杆"],
        "uncertainties": ["具体范围仍需现场核实"],
        "missing_fields": ["具体区域和影响范围"],
        "risk_level": risk_level,
        "immediate_actions": ["立即远离临边并提醒周边人员"] if high_risk else [],
        "suggested_actions": ["安排有资格的现场人员核实防护状态"],
        "recommended_route": recommended_route,
        "requires_human_review": high_risk,
        "confidence": 0.8,
    }


def response(*, content: str = "", tool_calls: list[Any] | None = None) -> Any:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments: dict[str, Any] | str) -> Any:
    raw_arguments = (
        arguments
        if isinstance(arguments, str)
        else json.dumps(arguments, ensure_ascii=False)
    )
    function = SimpleNamespace(
        name="propose_issue_record", arguments=raw_arguments
    )
    return SimpleNamespace(id="call-1", type="function", function=function)


class FakeCompletions:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("Fake 原生模型响应不足。")
        return self._responses.pop(0)


class FakeNativeLLM:
    def __init__(self, responses: list[Any]) -> None:
        self.completions = FakeCompletions(responses)
        self._client = SimpleNamespace(
            chat=SimpleNamespace(completions=self.completions)
        )
        self.model = "fake-native-function-model"
        self.temperature = 0.0
        self.max_tokens = 500


def proposal_agent(fake: FakeNativeLLM) -> IssueProposalAgent:
    return IssueProposalAgent(cast(HelloAgentsLLM, fake))


def test_ordinary_consultation_does_not_call_model_or_tool() -> None:
    payload = issue_payload(recommended_route="direct_answer", risk_level="low")
    payload.update(
        category="consultation",
        issue_type="安全帽佩戴咨询",
        summary="用户咨询安全帽下颏带如何检查。",
        observed_facts=["用户询问安全帽下颏带检查方法"],
        uncertainties=[],
        missing_fields=[],
    )
    analysis = IssueAnalysis.model_validate(payload)
    fake = FakeNativeLLM([])

    result = proposal_agent(fake).propose(analysis)

    assert result is None
    assert fake.completions.calls == []


def test_validated_follow_up_analysis_calls_only_native_proposal_tool() -> None:
    payload = issue_payload()
    analysis = IssueAnalysis.model_validate(payload)
    fake = FakeNativeLLM(
        [
            response(tool_calls=[tool_call(payload)]),
            response(content="已生成待确认提案。"),
        ]
    )

    result = proposal_agent(fake).propose(analysis)

    assert result is not None
    assert result.ok is True
    proposal = result.data["proposal"]
    assert proposal["analysis"] == payload
    assert proposal["requires_user_confirmation"] is True
    assert proposal["persisted"] is False
    assert proposal["dispatched"] is False

    first_call = fake.completions.calls[0]
    assert first_call["tool_choice"] == {
        "type": "function",
        "function": {"name": "propose_issue_record"},
    }
    assert [item["function"]["name"] for item in first_call["tools"]] == [
        "propose_issue_record"
    ]
    assert first_call["tools"][0]["function"]["parameters"] == (
        IssueAnalysis.model_json_schema()
    )
    assert fake.completions.calls[1]["tool_choice"] == "none"


def test_high_risk_validated_analysis_keeps_human_review_fields() -> None:
    payload = issue_payload(recommended_route="human_review", risk_level="high")
    analysis = IssueAnalysis.model_validate(payload)
    fake = FakeNativeLLM(
        [response(tool_calls=[tool_call(payload)]), response(content="完成")]
    )

    result = proposal_agent(fake).propose(analysis)

    assert result is not None and result.ok is True
    proposed_analysis = result.data["proposal"]["analysis"]
    assert proposed_analysis["risk_level"] == "high"
    assert proposed_analysis["recommended_route"] == "human_review"
    assert proposed_analysis["requires_human_review"] is True


def test_model_cannot_rewrite_validated_analysis_before_tool() -> None:
    payload = issue_payload()
    analysis = IssueAnalysis.model_validate(payload)
    tampered = {**payload, "summary": "模型擅自改写后的结论"}
    fake = FakeNativeLLM(
        [response(tool_calls=[tool_call(tampered)]), response(content="完成")]
    )

    result = proposal_agent(fake).propose(analysis)

    assert result is not None
    assert result.ok is False
    assert result.error_code == "analysis_mismatch"
    assert result.data == {}
    assert "模型擅自改写后的结论" not in result.summary


def test_native_boundary_does_not_coerce_invalid_json_types() -> None:
    payload = issue_payload()
    analysis = IssueAnalysis.model_validate(payload)
    invalid = {**payload, "confidence": "0.8"}
    fake = FakeNativeLLM(
        [response(tool_calls=[tool_call(invalid)]), response(content="完成")]
    )

    result = proposal_agent(fake).propose(analysis)

    assert result is not None
    assert result.ok is False
    assert result.error_code == "invalid_arguments"
    assert result.data == {}


def test_malformed_function_arguments_are_safely_rejected() -> None:
    analysis = IssueAnalysis.model_validate(issue_payload())
    fake = FakeNativeLLM(
        [response(tool_calls=[tool_call("{bad-json}")]), response(content="完成")]
    )

    result = proposal_agent(fake).propose(analysis)

    assert result is not None
    assert result.ok is False
    assert result.error_code == "invalid_arguments"


def test_missing_forced_tool_call_returns_stable_error() -> None:
    analysis = IssueAnalysis.model_validate(issue_payload())
    fake = FakeNativeLLM([response(content="模型没有调用工具")])

    result = proposal_agent(fake).propose(analysis)

    assert result is not None
    assert result.ok is False
    assert result.error_code == "tool_not_called"
    assert fake.completions.calls[0]["tool_choice"]["function"]["name"] == (
        "propose_issue_record"
    )


def test_unvalidated_mapping_is_rejected_before_native_model_call() -> None:
    fake = FakeNativeLLM([])

    with pytest.raises(TypeError, match="只接受已校验"):
        proposal_agent(fake).propose(cast(Any, issue_payload()))

    assert fake.completions.calls == []
