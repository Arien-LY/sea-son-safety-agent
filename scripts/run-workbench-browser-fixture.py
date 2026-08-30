"""Run an isolated deterministic UI fixture. Never constructs a real model client."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.text_assistant import TextAssistant, TextError
from backend.app.main import create_app
from backend.app.proposals import Phase2ProposalService
from backend.app.text_consultations import TextConsultationService
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_store import JsonIssueRecordStore


def analysis(category: str, risk: str, *, missing: bool = False) -> dict[str, object]:
    high = risk in {"high", "emergency"}
    return {
        "category": category,
        "issue_type": "临时用电" if category == "safety" else "一般咨询",
        "summary": "配电箱附近存在人员暴露风险，需由现场专业人员立即核实。" if high else "Fake 预设结果，仅用于界面验收。",
        "observed_facts": ["用户称三层配电箱冒火花且有人在附近"] if high else [],
        "uncertainties": ["尚未核实断电和警戒状态"] if high or missing else [],
        "missing_fields": ["具体楼层、当前危险状态和人员暴露情况"] if missing else [],
        "risk_level": risk,
        "immediate_actions": ["立即远离配电箱并通知现场专业人员断电处置，禁止自行触碰或带电测试。"] if high else [],
        "suggested_actions": ["安排有资格人员核实并记录处置结果"] if category != "consultation" else ["结合项目制度由专业人员核对"],
        "recommended_route": "human_review" if high else "collect_more_info" if missing else "direct_answer",
        "requires_human_review": high or missing,
        "confidence": 0.92 if high else 0.5,
    }


class WorkbenchFakeBackend:
    def invoke(self, messages: list[dict[str, str]], **_: object) -> str:
        content = messages[-1]["content"]
        if "模拟错误" in content:
            raise TextError("fixture_error", "Fake 验收错误：本次请求未执行模型调用。")
        if "模拟加载" in content:
            time.sleep(2)
        if "三层" in content or "冒火花" in content:
            payload = {
                "answer": "已识别到同一问题的高风险补充。请立即保持距离并联系现场专业人员。",
                "follow_up_questions": [],
                "analysis": analysis("safety", "high"),
            }
        elif "配电箱" in content:
            payload = {
                "answer": "信息还不足，先不要靠近设备。请在安全位置补充现场情况。",
                "follow_up_questions": ["配电箱位于哪里？是否冒火花或有人仍在附近？"],
                "analysis": analysis("unknown", "undetermined", missing=True),
            }
        else:
            payload = {
                "answer": "这是 Fake 预设的一般回答，用于验证普通聊天界面；未执行真实模型理解。",
                "follow_up_questions": [],
                "analysis": analysis("consultation", "low"),
            }
        return json.dumps(payload, ensure_ascii=False)


def app():
    fixture_root = Path(os.environ["WORKBENCH_FIXTURE_DIR"]).resolve()
    proposals = Phase2ProposalService(integrity_key=b"browser-fixture-integrity-key-32")
    workflow = IssueWorkflowService(
        JsonIssueRecordStore(fixture_root / "records.json"),
        confirmation_verifier=proposals.verify_confirmation,
    )
    backend = WorkbenchFakeBackend()
    texts = TextConsultationService(
        proposals,
        assistant_factory=lambda _mode: TextAssistant(backend),
    )
    return create_app(proposal_service=proposals, workflow_service=workflow, text_service=texts)


if __name__ == "__main__":
    os.environ["AGENT_MODE"] = "mock"
    os.environ["PHOTO_STORE_PATH"] = str(Path(os.environ["WORKBENCH_FIXTURE_DIR"]) / "photos")
    uvicorn.run(app(), host="127.0.0.1", port=8000, log_level="warning")
