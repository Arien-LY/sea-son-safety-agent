"""正式工单本地删除 API：明确错误、彻底消失、不影响其他工单。"""

from test_phase3_api import confirmed_payload, phase3_client


def create_record(client, suffix, category="safety", risk_level="medium"):
    confirmation = confirmed_payload(client, category=category, risk_level=risk_level, suffix=suffix)
    response = client.post("/api/issue-records", json={
        "confirmation": confirmation,
        "idempotency_key": f"create-{suffix}",
        "actor": {"actor_id": "reporter-delete", "role": "reporter"},
    })
    assert response.status_code == 200, response.text
    return response.json()["record"]


def test_delete_existing_record_removes_it_everywhere_but_keeps_others(tmp_path):
    client = phase3_client(tmp_path)
    first = create_record(client, "delete-first")
    second = create_record(client, "delete-second", category="quality")

    response = client.delete(f"/api/issue-records/{first['record_id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "record_id": first["record_id"]}

    assert client.get(f"/api/issue-records/{first['record_id']}").status_code == 404
    assert client.get(f"/api/issue-records/{first['record_id']}/export.docx").status_code == 404
    listing = client.get("/api/issue-records").json()
    assert listing["total"] == 1
    assert [item["record_id"] for item in listing["items"]] == [second["record_id"]]

    # 其他工单不受影响，仍可读取、导出、继续工作流。
    assert client.get(f"/api/issue-records/{second['record_id']}").status_code == 200
    assert client.get(f"/api/issue-records/{second['record_id']}/export.docx").status_code == 200
    submitted = client.post(f"/api/issue-records/{second['record_id']}/actions", json={
        "action": "submit", "actor": {"actor_id": "reporter-delete", "role": "reporter"},
        "expected_revision": second["revision"]})
    assert submitted.status_code == 200 and submitted.json()["status"] == "submitted"


def test_delete_missing_record_returns_explicit_error(tmp_path):
    client = phase3_client(tmp_path)
    kept = create_record(client, "delete-kept")
    response = client.delete("/api/issue-records/ISS-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "record_not_found"
    assert response.json()["detail"]["message"] == "问题记录不存在。"
    assert client.get("/api/issue-records").json()["total"] == 1
    assert client.get(f"/api/issue-records/{kept['record_id']}").status_code == 200


def test_delete_is_idempotent_for_missing_records_after_first_delete(tmp_path):
    client = phase3_client(tmp_path)
    record = create_record(client, "delete-twice")
    assert client.delete(f"/api/issue-records/{record['record_id']}").status_code == 200
    assert client.delete(f"/api/issue-records/{record['record_id']}").status_code == 404
    assert client.get("/api/issue-records").json()["total"] == 0


def test_deleted_record_stays_deleted_after_store_reload(tmp_path):
    client = phase3_client(tmp_path)
    record = create_record(client, "delete-reload")
    assert client.delete(f"/api/issue-records/{record['record_id']}").status_code == 200
    # 同一 Store 文件重新加载；若删除留下悬空幂等索引，这里会因校验失败而报 500。
    reopened = phase3_client(tmp_path)
    assert reopened.get(f"/api/issue-records/{record['record_id']}").status_code == 404
    assert reopened.get("/api/issue-records").json()["total"] == 0
