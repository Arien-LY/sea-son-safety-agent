"""TicketDecision 契约的离线自动化测试（覆盖 A ～ G）。"""

import json

import pytest

from agents.schemas import TicketStatus
from agents.text_assistant import TextAssistant, TextError, parse_reply
from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from backend.app.text_models import TextProposalRequest, TextRequest, TicketRejudgeRequest
from test_product_text import FakeTextBackend, decision_payload


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")


def build_service(responses):
    # 复用同一个 FakeTextBackend，重新判断才会读到下一个预设响应。
    backend = FakeTextBackend(responses)
    return TextConsultationService(
        Phase2ProposalService(integrity_key=b"d" * 32),
        assistant_factory=lambda *_: TextAssistant(backend),
    )


def auto_request(n=1, previous=None, message="现场问题"):
    return TextRequest(
        request_id=f"ticket-decision-{n:04d}", intent="auto", input={"message": message},
        consultation_id=previous.consultation_id if previous else None,
        expected_turn=previous.turn if previous else 0,
    )


def test_a_plain_consultation_is_no_ticket():
    app = build_service([decision_payload("consultation", "low", status="no_ticket")])
    result = app.send(auto_request(message="安全帽下颏带怎么检查？"))
    assert result.ticket_decision.status is TicketStatus.NO_TICKET
    assert result.analysis_status == "validated"
    assert not result.can_propose
    assert result.reply.analysis.recommended_route == "direct_answer"
    assert result.reply.answer


def test_b_missing_context_asks_a_simple_follow_up():
    app = build_service([decision_payload("unknown", "undetermined", status="need_more_info")])
    result = app.send(auto_request(message="二楼有点问题"))
    assert result.ticket_decision.status is TicketStatus.NEED_MORE_INFO
    assert result.reply.follow_up_questions
    assert not result.can_propose
    assert result.reply.answer


@pytest.mark.parametrize("category", ["safety", "quality", "management", "logistics"])
def test_cde_defined_field_issue_can_generate_a_ticket(category):
    app = build_service([decision_payload(category, "medium")])
    result = app.send(auto_request(message="厂房二层现场问题，需要持续跟进"))
    assert result.ticket_decision.status is TicketStatus.CREATE_TICKET
    assert result.can_propose
    assert result.reply.analysis.category == category
    assert result.reply.analysis.recommended_route in {"propose_workflow", "human_review"}


def test_f_emergency_is_forced_to_ticket_with_immediate_action():
    app = build_service([decision_payload(
        "safety", "emergency", immediate="立即远离配电箱并通知现场专业人员，不要自行处置。")])
    result = app.send(auto_request(message="配电箱持续冒火花，旁边有人施工"))
    assert result.ticket_decision.status is TicketStatus.CREATE_TICKET
    assert result.can_propose
    assert result.ticket_decision.requires_human_review
    assert result.reply.analysis.risk_level == "emergency"
    assert result.reply.analysis.requires_human_review
    assert result.reply.analysis.immediate_actions
    assert "远离" in result.reply.analysis.immediate_actions[0]


def test_high_risk_cannot_be_downgraded_by_the_model():
    payload = decision_payload("safety", "high", status="no_ticket", review=False)
    parsed = parse_reply(json.dumps(payload, ensure_ascii=False), unified=True)
    assert parsed.ticket_decision.status is TicketStatus.CREATE_TICKET
    assert parsed.ticket_decision.requires_human_review
    assert parsed.analysis.risk_level == "high"


def test_retained_high_risk_cannot_lose_the_ticket_option():
    app = build_service([decision_payload("safety", "high"),
                         decision_payload("safety", "low", status="no_ticket", review=False)])
    first = app.send(auto_request(1, message="配电箱持续冒火花，旁边有人施工"))
    assert first.can_propose and not first.risk_retained
    second = app.send(auto_request(2, first, message="已经处理过了，应该没事"))
    assert second.risk_retained and second.can_propose
    assert second.ticket_decision.status is TicketStatus.CREATE_TICKET
    assert second.reply.analysis.risk_level == "high"
    assert second.reply.analysis.requires_human_review


def test_json_field_order_does_not_change_the_decision():
    payload = decision_payload("quality", "medium")
    ordered = {"ticket_decision": payload["ticket_decision"], "follow_up_questions": [],
               "answer": payload["answer"]}
    app = build_service([ordered])
    result = app.send(auto_request(message="墙面抹灰强度不足"))
    assert result.can_propose and result.reply.analysis.category == "quality"


def test_g_invalid_decision_keeps_answer_and_offers_one_manual_rejudge():
    invalid = {"answer": "回答依然保留", "ticket_decision": {
        "status": "create_ticket", "category": "consultation", "summary": "矛盾的判断"}}
    app = build_service([invalid, decision_payload("safety", "medium")])
    result = app.send(auto_request(message="二层楼梯口临边护栏缺失"))
    assert result.reply.answer == "回答依然保留"
    assert result.analysis_status == "unavailable" and not result.can_propose
    assert result.ticket_decision is None and result.rejudge_available
    fixed = app.rejudge(result.consultation_id, TicketRejudgeRequest(expected_turn=1, confirmed=True))
    assert fixed.turn == 1 and fixed.analysis_status == "validated" and fixed.can_propose
    assert fixed.reply.answer == "回答依然保留"
    assert fixed.ticket_decision.status is TicketStatus.CREATE_TICKET
    assert len(app._sessions[result.consultation_id].inputs) == 1


def test_g_failed_rejudge_is_not_retried_forever():
    invalid = {"answer": "回答依然保留", "ticket_decision": {
        "status": "create_ticket", "category": "consultation", "summary": "矛盾的判断"}}
    app = build_service([invalid])
    result = app.send(auto_request())
    again = app.rejudge(result.consultation_id, TicketRejudgeRequest(expected_turn=1, confirmed=True))
    assert again.analysis_status == "unavailable" and not again.can_propose
    assert again.analysis_retry_used and not again.rejudge_available
    with pytest.raises(TextError) as error:
        app.rejudge(result.consultation_id, TicketRejudgeRequest(expected_turn=1, confirmed=True))
    assert error.value.code == "text_rejudge_used"


def test_rejudge_requires_an_unavailable_decision():
    app = build_service([decision_payload("safety", "medium")])
    result = app.send(auto_request())
    with pytest.raises(TextError) as error:
        app.rejudge(result.consultation_id, TicketRejudgeRequest(expected_turn=1, confirmed=True))
    assert error.value.code == "text_rejudge_not_needed"


def test_unavailable_is_never_treated_as_create_ticket():
    app = build_service([{"answer": "回答依然保留", "ticket_decision": {}}])
    result = app.send(auto_request())
    assert result.analysis_status == "unavailable" and not result.can_propose
    with pytest.raises(TextError) as error:
        app.propose(result.consultation_id, TextProposalRequest(expected_turn=1, confirmed=True))
    assert error.value.code == "text_not_proposable"
