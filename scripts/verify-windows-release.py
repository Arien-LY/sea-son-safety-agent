"""Unzip a customer package and exercise only its own runtime, always offline Mock."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import zipfile


def verify(archive: Path) -> dict:
    target = Path(tempfile.mkdtemp(prefix="sea-son-package-")).resolve()
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError("Invalid package path")
        bundle.extractall(target)
    root, = target.iterdir()
    manifest = json.loads((root / "_internal/build-manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        assert actual == expected, name
    # An empty PATH and relocated directory demonstrate no developer Python/Node/Git dependency.
    env = dict(os.environ, AGENT_MODE="mock", LLM_API_KEY="", PYTHON_DOTENV_DISABLED="1", PATH=os.environ["WINDIR"] + "\\System32")
    native = subprocess.run([str(root / "海之子.exe"), "--smoke", str(target / "原生启动验证")], env=env, timeout=80)
    assert native.returncode == 0, f"Native launcher smoke exit={native.returncode}; retained {target}"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    opener = build_opener(ProxyHandler({}))
    base = f"http://127.0.0.1:{port}"
    data = target / "独立比赛验收数据"
    def request(path: str, payload=None, *, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = Request(base + path, data=body, headers={"Content-Type": "application/json"} if body else {})
        try:
            response = opener.open(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode("utf-8")
            assert response.status == status, (path, response.status)
            return json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw
    def start():
        process = subprocess.Popen([str(root / "_internal/python/python.exe"), "-B", "-m", "desktop.server", "--port", str(port), "--user-data", str(data)], cwd=target, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(f"Packaged server exited early; retained {target}")
            try:
                if request("/health") == {"status": "ok"}:
                    return process
            except (URLError, TimeoutError):
                time.sleep(0.25)
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError("Package startup timeout")
    server = start()
    try:
        assert "<html" in request("/chat")
        assert request("/api/runtime") == {"agent_mode": "mock"}
        for path in ("/.env", "/docs", "/openapi.json", "/api/not-found"):
            request(path, status=404)
        request("/api/issue-records")
        stream = request("/api/text-consultations/stream", {"request_id": "package-chat-0001", "intent": "auto", "input": {"message": "你好"}, "expected_turn": 0, "allow_external": False})
        events = [json.loads(line) for line in stream.splitlines()]
        result = events[-1]["data"]
        assert result["mode"] == "mock" and not result["can_propose"]
        assert "".join(e["text"] for e in events if e["type"] == "content_delta") == result["reply"]["answer"]
        ids = []
        for category, risk, responsible in (("logistics", "low", "facilities_staff"), ("safety", "high", "safety_officer")):
            high = risk == "high"
            analysis = {"category": category, "issue_type": "比赛验收合成问题", "summary": "用于验证软件工作流的合成信息。", "observed_facts": ["合成测试问题"], "uncertainties": [], "missing_fields": [], "risk_level": risk, "immediate_actions": ["立即远离危险区域并通知专业人员"] if high else [], "suggested_actions": ["安排专业人员核实"], "recommended_route": "human_review" if high else "propose_workflow", "requires_human_review": high, "confidence": 0.9}
            preview = request("/api/issue-proposals/preview", {"invocation_id": "package-" + category, "analysis": analysis})["data"]
            confirm = request("/api/issue-proposals/confirm", {"proposal": preview["proposal"], "proposal_token": preview["proposal_token"], "edited_fields": preview["proposal"]["review_fields"], "confirmed": True})
            record = request("/api/issue-records", {"confirmation": confirm, "idempotency_key": "package-save-" + category, "actor": {"actor_id": "test-reporter", "role": "reporter"}})["record"]
            for action, actor, role, extra in (
                ("submit", "test-reporter", "reporter", {}),
                ("assign", "test-coordinator", "coordinator", {"assignee_id": "test-rectifier", "assignee_role": responsible}),
                ("start_rectification", "test-rectifier", "rectifier", {}),
                ("submit_rectification", "test-rectifier", "rectifier", {"note": "合成整改说明"}),
                ("close", "test-reviewer", "professional_reviewer" if high else "reviewer", {"note": "合成复查结论"}),
            ):
                record = request(f"/api/issue-records/{record['record_id']}/actions", {"action": action, "actor": {"actor_id": actor, "role": role}, "expected_revision": record["revision"], **extra})
            assert record["status"] == "closed" and record["revision"] == 6
            ids.append(record["record_id"])
        server.terminate(); server.wait(timeout=10)
        server = start()
        for record_id in ids:
            assert request("/api/issue-records/" + record_id)["status"] == "closed"
        report = {"package": archive.name, "source_commit": manifest["source_commit"], "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "files_verified": len(manifest["files"]), "native_launcher": "passed", "dpapi_synthetic_roundtrip": "passed", "same_origin_spa": "passed", "mock_stream": "passed", "workflow_categories": ["logistics", "safety"], "restart_persistence": "passed", "real_model_calls": 0, "retained_test_directory": str(target)}
        (archive.parent / "package-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        if server.poll() is None:
            server.terminate(); server.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    print(json.dumps(verify(parser.parse_args().archive.resolve()), ensure_ascii=False, indent=2))
