"""create_ticket → 生成工单 → 人工确认 → 正式工单 的完整流程边界。"""

from test_product_text import decision_payload, propose, send, text_client


def test_create_ticket_only_creates_a_draft_after_the_click(tmp_path):
    client, service, workflow, fake = text_client(tmp_path, [decision_payload("safety", "medium")])
    result = send(client, intent="auto", input={"message": "二层楼梯口临边护栏缺失"})
    assert result["ticket_decision"]["status"] == "create_ticket"
    assert result["can_propose"] and result["analysis_status"] == "validated"
    # 点击前不创建正式工单
    assert workflow.store.snapshot() == ()
    preview = propose(client, result).json()
    assert preview["ok"]
    assert preview["data"]["proposal"]["analysis"]["category"] == "safety"
    assert preview["data"]["proposal"]["persisted"] is False
    assert workflow.store.snapshot() == ()
    assert len(fake.messages) == 1


def test_confirmed_ticket_saves_a_draft_and_keeps_six_state_workflow(tmp_path):
    client, service, workflow, _ = text_client(tmp_path, [decision_payload("quality", "medium")])
    result = send(client, intent="auto")
    data = propose(client, result).json()["data"]
    confirmation = client.post("/api/issue-proposals/confirm", json={
        **data, "edited_fields": {**data["proposal"]["review_fields"], "area": "二层"},
        "confirmed": True})
    assert confirmation.status_code == 200
    created = client.post("/api/issue-records", json={
        "confirmation": confirmation.json(), "idempotency_key": "ticket-flow-create",
        "actor": {"actor_id": "reporter-flow", "role": "reporter"}})
    assert created.status_code == 200
    record = created.json()["record"]
    assert record["status"] == "draft" and record["disposition"] == "active"
    submitted = client.post(f"/api/issue-records/{record['record_id']}/actions", json={
        "action": "submit", "actor": {"actor_id": record["reporter_id"], "role": "reporter"},
        "expected_revision": record["revision"]})
    assert submitted.status_code == 200 and submitted.json()["status"] == "submitted"


def test_user_cannot_lower_the_risk_of_a_ticket(tmp_path):
    client, service, workflow, _ = text_client(tmp_path, [decision_payload("safety", "high")])
    result = send(client, intent="auto")
    assert result["reply"]["analysis"]["risk_level"] == "high"
    data = propose(client, result).json()["data"]
    tampered = {**data["proposal"], "analysis": {
        **data["proposal"]["analysis"], "risk_level": "low", "requires_human_review": False}}
    response = client.post("/api/issue-proposals/confirm", json={
        "proposal": tampered, "proposal_token": data["proposal_token"],
        "edited_fields": tampered["review_fields"], "confirmed": True})
    assert response.status_code == 400
    assert workflow.store.snapshot() == ()
