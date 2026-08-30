import pytest

from test_phase3_api import confirmed_payload, phase3_client, post_action


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")
    def forbidden(*args, **kwargs): raise AssertionError("Paid model not allowed")
    monkeypatch.setattr("agents.text_assistant.OpenAI", forbidden)


def create_record(client, n, category="logistics", risk="low"):
    confirmation = confirmed_payload(client, category=category, risk_level=risk, suffix=f"record-list-{n:04d}")
    response = client.post("/api/issue-records", json={"confirmation": confirmation, "idempotency_key": f"record-create-{n:04d}",
                                                     "actor": {"actor_id": "historical-reporter", "role": "reporter"}})
    assert response.status_code == 200
    return response.json()["record"]


def test_empty_paginated_filtered_list_and_reopen(tmp_path):
    client = phase3_client(tmp_path)
    assert client.get("/api/issue-records").json() == {"total": 0, "offset": 0, "limit": 20, "items": []}
    records = [create_record(client, n, "safety" if n % 2 else "logistics") for n in range(23)]
    before = (tmp_path / "api-records.json").read_bytes()
    first = client.get("/api/issue-records").json()
    second = client.get("/api/issue-records?offset=20").json()
    assert first["total"] == 23 and len(first["items"]) == 20 and len(second["items"]) == 3
    ids = [r["record_id"] for r in first["items"] + second["items"]]
    assert len(set(ids)) == 23 and ids[0] == records[-1]["record_id"]
    assert all("events" not in r and "analysis" not in r for r in first["items"])
    filtered = client.get("/api/issue-records", params={"category": "safety", "status": "draft", "disposition": "active", "q": "API 验收项目"}).json()
    assert filtered["total"] == 11
    assert client.get("/api/issue-records", params={"q": records[0]["record_id"].lower()}).json()["total"] == 1
    assert client.get("/api/issue-records?q=absent").json()["items"] == []
    assert (tmp_path / "api-records.json").read_bytes() == before
    restarted = phase3_client(tmp_path)
    assert restarted.get("/api/issue-records").json() == first
    assert restarted.get(f"/api/issue-records/{records[0]['record_id']}").json() == records[0]


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=100001", "offset=1.2", "category=unknown",
                                 "status=deleted", "disposition=closed", "other=x", "limit=1&limit=2", "q=" + "x" * 101],
                         ids=["zero", "large", "negative", "offset-large", "fraction", "category", "status", "disposition", "extra", "duplicate", "long-search"])
def test_invalid_query(tmp_path, query):
    assert phase3_client(tmp_path).get("/api/issue-records?" + query).status_code == 400


def test_historical_record_continues_workflow_and_stale_revision_rejected(tmp_path):
    client = phase3_client(tmp_path)
    record = create_record(client, 1)
    reloaded = phase3_client(tmp_path)
    current = reloaded.get(f"/api/issue-records/{record['record_id']}").json()
    current = post_action(reloaded, current, "submit", current["reporter_id"], "reporter")
    current = post_action(reloaded, current, "assign", "coordinator", "coordinator", assignee_id="historical-rectifier", assignee_role="facilities_staff")
    current = post_action(reloaded, current, "start_rectification", current["assigned_to"], "rectifier")
    current = post_action(reloaded, current, "submit_rectification", current["assigned_to"], "rectifier", note="合成整改说明")
    current = post_action(reloaded, current, "close", "reviewer", "reviewer", note="合成复查通过")
    assert current["revision"] == 6
    assert reloaded.get("/api/issue-records?status=closed").json()["total"] == 1
    stale = client.post(f"/api/issue-records/{record['record_id']}/actions", json={"action": "submit", "actor": {"actor_id": record["reporter_id"], "role": "reporter"}, "expected_revision": 1})
    assert stale.status_code == 409


def test_list_store_error_is_not_empty_success(tmp_path):
    client = phase3_client(tmp_path)
    (tmp_path / "api-records.json").write_text("PRIVATE broken store", encoding="utf-8")
    response = client.get("/api/issue-records")
    assert response.status_code == 500 and "PRIVATE" not in response.text
    assert (tmp_path / "api-records.json").read_text() == "PRIVATE broken store"
