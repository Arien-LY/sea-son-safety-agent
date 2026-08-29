from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agents.schemas import IssueAnalysis
from agents.tools import IssueRecordProposal, IssueRecordReviewFields
from backend.app.proposals import (
    ConfirmedIssueProposal,
    Phase2ProposalService,
    ProposalConfirmationRequest,
    ProposalPreviewRequest,
)
from backend.app.workflow import IssueWorkflowService, WorkflowRuleError
from backend.app.workflow_models import (
    ActorRole,
    CreateIssueRecordRequest,
    RecordDisposition,
    ResponsibleRole,
    WorkflowAction,
    WorkflowActor,
    WorkflowStatus,
    WorkflowTransitionRequest,
)
from backend.app.workflow_store import (
    IdempotencyConflictError,
    JsonIssueRecordStore,
    RevisionConflictError,
    StoreError,
)


def analysis_for(category: str, risk_level: str = "medium") -> IssueAnalysis:
    high_risk = risk_level in {"high", "emergency"}
    issue_type = "临边防护缺失" if category == "safety" else "宿舍门锁损坏"
    summary = (
        "作业层临边缺少防护栏杆。"
        if category == "safety"
        else "宿舍门锁损坏，无法正常锁闭。"
    )
    return IssueAnalysis.model_validate(
        {
            "category": category,
            "issue_type": issue_type,
            "summary": summary,
            "observed_facts": [summary],
            "uncertainties": [],
            "missing_fields": [],
            "risk_level": risk_level,
            "immediate_actions": ["立即远离危险区域并通知专业人员"] if high_risk else [],
            "suggested_actions": ["安排现场人员核实并跟进"],
            "recommended_route": "human_review" if high_risk else "propose_workflow",
            "requires_human_review": high_risk,
            "confidence": 0.9,
        }
    )


def confirmation_for(
    proposal_service: Phase2ProposalService,
    *,
    category: str,
    risk_level: str = "medium",
    invocation_id: str,
) -> ConfirmedIssueProposal:
    preview = proposal_service.preview(
        ProposalPreviewRequest(
            invocation_id=invocation_id,
            analysis=analysis_for(category, risk_level),
        )
    )
    assert preview.ok is True
    proposal = IssueRecordProposal.model_validate(preview.data["proposal"])
    edited = IssueRecordReviewFields(
        **{
            **proposal.review_fields.model_dump(),
            "project": "验收项目",
            "area": "验收区域",
        }
    )
    return proposal_service.confirm(
        ProposalConfirmationRequest(
            proposal=proposal,
            proposal_token=preview.data["proposal_token"],
            edited_fields=edited,
            confirmed=True,
        )
    )


def actor(actor_id: str, role: ActorRole) -> WorkflowActor:
    return WorkflowActor(actor_id=actor_id, role=role)


def action(
    name: WorkflowAction,
    record_revision: int,
    action_actor: WorkflowActor,
    *,
    note: str | None = None,
    assignee_id: str | None = None,
    assignee_role: ResponsibleRole | None = None,
) -> WorkflowTransitionRequest:
    return WorkflowTransitionRequest(
        action=name,
        actor=action_actor,
        expected_revision=record_revision,
        note=note,
        assignee_id=assignee_id,
        assignee_role=assignee_role,
    )


def workflow_pair(tmp_path: Path) -> tuple[Phase2ProposalService, IssueWorkflowService]:
    proposal_service = Phase2ProposalService(integrity_key=b"p" * 32)
    workflow = IssueWorkflowService(
        JsonIssueRecordStore(tmp_path / "issue-records.json"),
        confirmation_verifier=proposal_service.verify_confirmation,
    )
    return proposal_service, workflow


def create_record(
    proposal_service: Phase2ProposalService,
    workflow: IssueWorkflowService,
    *,
    category: str,
    risk_level: str,
    key: str,
) -> tuple[CreateIssueRecordRequest, object]:
    request = CreateIssueRecordRequest(
        confirmation=confirmation_for(
            proposal_service,
            category=category,
            risk_level=risk_level,
            invocation_id=f"preview-{key}",
        ),
        idempotency_key=f"create-{key}",
        actor=actor("reporter-1", ActorRole.REPORTER),
    )
    return request, workflow.create_draft(request).record


def test_workflow_statuses_are_frozen() -> None:
    assert {status.value for status in WorkflowStatus} == {
        "draft",
        "submitted",
        "assigned",
        "rectifying",
        "pending_review",
        "closed",
    }


def test_high_risk_safety_record_requires_independent_professional_close(
    tmp_path: Path,
) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="safety",
        risk_level="high",
        key="safety-high-001",
    )
    assert record.status is WorkflowStatus.DRAFT
    assert record.suggested_responsible_role is ResponsibleRole.SAFETY_OFFICER
    assert record.assigned_to is None
    assert record.assignment_confirmed_by_human is False

    record = workflow.transition(
        record.record_id,
        action(WorkflowAction.SUBMIT, record.revision, actor("reporter-1", ActorRole.REPORTER)),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.ASSIGN,
            record.revision,
            actor("coordinator-1", ActorRole.COORDINATOR),
            assignee_id="rectifier-1",
            assignee_role=ResponsibleRole.SITE_MANAGER,
        ),
    )
    assert record.assigned_role is ResponsibleRole.SITE_MANAGER
    assert record.assignment_confirmed_by_human is True
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.START_RECTIFICATION,
            record.revision,
            actor("rectifier-1", ActorRole.RECTIFIER),
        ),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.SUBMIT_RECTIFICATION,
            record.revision,
            actor("rectifier-1", ActorRole.RECTIFIER),
            note="已恢复临边防护并完成现场自检。",
        ),
    )

    with pytest.raises(WorkflowRuleError) as submitter_close:
        workflow.transition(
            record.record_id,
            action(
                WorkflowAction.CLOSE,
                record.revision,
                actor("reporter-1", ActorRole.PROFESSIONAL_REVIEWER),
                note="提交人试图自行关闭。",
            ),
        )
    assert submitter_close.value.code == "submitter_cannot_close_high_risk"

    with pytest.raises(WorkflowRuleError) as ordinary_review:
        workflow.transition(
            record.record_id,
            action(
                WorkflowAction.CLOSE,
                record.revision,
                actor("reviewer-1", ActorRole.REVIEWER),
                note="普通复查人尝试关闭高风险问题。",
            ),
        )
    assert ordinary_review.value.code == "professional_review_required"

    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.CLOSE,
            record.revision,
            actor("professional-1", ActorRole.PROFESSIONAL_REVIEWER),
            note="专业复查确认防护恢复，允许关闭。",
        ),
    )
    assert record.status is WorkflowStatus.CLOSED
    assert record.review_note == "专业复查确认防护恢复，允许关闭。"
    assert [event.sequence for event in record.events] == list(range(1, 7))
    assert [event.action for event in record.events] == [
        WorkflowAction.CREATE_DRAFT,
        WorkflowAction.SUBMIT,
        WorkflowAction.ASSIGN,
        WorkflowAction.START_RECTIFICATION,
        WorkflowAction.SUBMIT_RECTIFICATION,
        WorkflowAction.CLOSE,
    ]


def test_logistics_reuses_lifecycle_with_facilities_role(tmp_path: Path) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="logistics",
        risk_level="low",
        key="logistics-low-001",
    )
    assert record.suggested_responsible_role is ResponsibleRole.FACILITIES_STAFF
    steps = [
        action(WorkflowAction.SUBMIT, 1, actor("reporter-1", ActorRole.REPORTER)),
        action(
            WorkflowAction.ASSIGN,
            2,
            actor("coordinator-1", ActorRole.COORDINATOR),
            assignee_id="facilities-1",
            assignee_role=ResponsibleRole.FACILITIES_STAFF,
        ),
        action(
            WorkflowAction.START_RECTIFICATION,
            3,
            actor("facilities-1", ActorRole.RECTIFIER),
        ),
        action(
            WorkflowAction.SUBMIT_RECTIFICATION,
            4,
            actor("facilities-1", ActorRole.RECTIFIER),
            note="已更换门锁并测试锁闭。",
        ),
        action(
            WorkflowAction.CLOSE,
            5,
            actor("reviewer-1", ActorRole.REVIEWER),
            note="复查门锁功能正常。",
        ),
    ]
    for transition in steps:
        record = workflow.transition(record.record_id, transition)
    assert record.status is WorkflowStatus.CLOSED
    assert record.analysis.category.value == "logistics"
    reloaded = JsonIssueRecordStore(tmp_path / "issue-records.json").get(record.record_id)
    assert reloaded == record


def test_more_information_rejection_and_re_rectification_paths(tmp_path: Path) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="logistics",
        risk_level="medium",
        key="rework-001",
    )
    record = workflow.transition(
        record.record_id,
        action(WorkflowAction.SUBMIT, record.revision, actor("reporter-1", ActorRole.REPORTER)),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.REQUEST_MORE_INFO,
            record.revision,
            actor("coordinator-1", ActorRole.COORDINATOR),
            note="请补充具体房间位置。",
        ),
    )
    assert record.status is WorkflowStatus.DRAFT
    assert record.information_request == "请补充具体房间位置。"
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.SUPPLEMENT_INFORMATION,
            record.revision,
            actor("reporter-1", ActorRole.REPORTER),
            note="位于 2 号宿舍楼 203 室。",
        ),
    )
    assert record.status is WorkflowStatus.SUBMITTED
    assert record.information_request is None
    assert record.review_fields.reporter_note == "位于 2 号宿舍楼 203 室。"
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.ASSIGN,
            record.revision,
            actor("coordinator-1", ActorRole.COORDINATOR),
            assignee_id="facilities-1",
            assignee_role=ResponsibleRole.FACILITIES_STAFF,
        ),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.START_RECTIFICATION,
            record.revision,
            actor("facilities-1", ActorRole.RECTIFIER),
        ),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.SUBMIT_RECTIFICATION,
            record.revision,
            actor("facilities-1", ActorRole.RECTIFIER),
            note="第一次整改完成。",
        ),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.REJECT_REVIEW,
            record.revision,
            actor("reviewer-1", ActorRole.REVIEWER),
            note="锁舌仍有卡滞，请重新整改。",
        ),
    )
    assert record.status is WorkflowStatus.RECTIFYING
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.SUBMIT_RECTIFICATION,
            record.revision,
            actor("facilities-1", ActorRole.RECTIFIER),
            note="已调整锁舌并重复测试。",
        ),
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.CLOSE,
            record.revision,
            actor("reviewer-1", ActorRole.REVIEWER),
            note="复查通过。",
        ),
    )
    assert record.status is WorkflowStatus.CLOSED
    assert [event.action for event in record.events].count(
        WorkflowAction.SUBMIT_RECTIFICATION
    ) == 2
    assert any(
        event.action is WorkflowAction.REJECT_REVIEW
        and event.note == "锁舌仍有卡滞，请重新整改。"
        for event in record.events
    )


def test_cancel_is_terminal_without_adding_a_seventh_primary_status(tmp_path: Path) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="logistics",
        risk_level="low",
        key="cancel-001",
    )
    record = workflow.transition(
        record.record_id,
        action(
            WorkflowAction.CANCEL,
            record.revision,
            actor("reporter-1", ActorRole.REPORTER),
            note="重复上报，取消本草稿。",
        ),
    )
    assert record.status is WorkflowStatus.DRAFT
    assert record.disposition is RecordDisposition.CANCELLED
    assert record.cancellation_reason == "重复上报，取消本草稿。"
    with pytest.raises(WorkflowRuleError) as cancelled:
        workflow.transition(
            record.record_id,
            action(
                WorkflowAction.SUBMIT,
                record.revision,
                actor("reporter-1", ActorRole.REPORTER),
            ),
        )
    assert cancelled.value.code == "record_cancelled"


def test_high_risk_reporter_cannot_cancel_with_professional_role_claim(
    tmp_path: Path,
) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="safety",
        risk_level="high",
        key="cancel-high-001",
    )
    with pytest.raises(WorkflowRuleError) as rejected:
        workflow.transition(
            record.record_id,
            action(
                WorkflowAction.CANCEL,
                record.revision,
                actor("reporter-1", ActorRole.PROFESSIONAL_REVIEWER),
                note="提交人试图自行取消高风险问题。",
            ),
        )
    assert rejected.value.code == "submitter_cannot_cancel_high_risk"


def test_creation_is_idempotent_and_rejects_key_reuse(tmp_path: Path) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    request, first = create_record(
        proposal_service,
        workflow,
        category="logistics",
        risk_level="low",
        key="idem-001",
    )
    repeated = workflow.create_draft(request)
    assert repeated.created is False
    assert repeated.record.record_id == first.record_id

    different_request = CreateIssueRecordRequest(
        confirmation=confirmation_for(
            proposal_service,
            category="safety",
            risk_level="medium",
            invocation_id="preview-idem-002",
        ),
        idempotency_key=request.idempotency_key,
        actor=request.actor,
    )
    with pytest.raises(IdempotencyConflictError):
        workflow.create_draft(different_request)


def test_concurrent_creates_across_store_instances_do_not_lose_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "concurrent-records.json"
    proposal_service = Phase2ProposalService(integrity_key=b"c" * 32)
    workflows = [
        IssueWorkflowService(
            JsonIssueRecordStore(path),
            confirmation_verifier=proposal_service.verify_confirmation,
        )
        for _ in range(2)
    ]
    requests = [
        CreateIssueRecordRequest(
            confirmation=confirmation_for(
                proposal_service,
                category="logistics",
                risk_level="low",
                invocation_id=f"preview-concurrent-{index:03d}",
            ),
            idempotency_key=f"create-concurrent-{index:03d}",
            actor=actor(f"reporter-{index}", ActorRole.REPORTER),
        )
        for index in range(24)
    ]

    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(
            pool.map(
                lambda item: workflows[item[0] % 2].create_draft(item[1]).record,
                enumerate(requests),
            )
        )

    snapshot = JsonIssueRecordStore(path).snapshot()
    assert len(snapshot) == 24
    assert len({record.record_id for record in records}) == 24
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_atomic_replace_failure_keeps_previous_store_file(tmp_path: Path) -> None:
    path = tmp_path / "atomic-records.json"
    proposal_service = Phase2ProposalService(integrity_key=b"a" * 32)
    working = IssueWorkflowService(
        JsonIssueRecordStore(path),
        confirmation_verifier=proposal_service.verify_confirmation,
    )
    create_record(
        proposal_service,
        working,
        category="logistics",
        risk_level="low",
        key="atomic-001",
    )
    before = path.read_bytes()

    def fail_replace(_source: str, _target: str) -> None:
        raise OSError("simulated replace failure")

    failing = IssueWorkflowService(
        JsonIssueRecordStore(path, replace=fail_replace),
        confirmation_verifier=proposal_service.verify_confirmation,
    )
    request = CreateIssueRecordRequest(
        confirmation=confirmation_for(
            proposal_service,
            category="logistics",
            risk_level="low",
            invocation_id="preview-atomic-002",
        ),
        idempotency_key="create-atomic-002",
        actor=actor("reporter-2", ActorRole.REPORTER),
    )
    with pytest.raises(StoreError):
        failing.create_draft(request)
    assert path.read_bytes() == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupted_idempotency_index_is_rejected_without_overwrite(
    tmp_path: Path,
) -> None:
    path = tmp_path / "corrupted-records.json"
    corrupted = (
        '{"schema_version":"phase3-issue-record-store-v1",'
        '"records":{},"idempotency_keys":{"bad-key":'
        '{"record_id":"ISS-000000000000","payload_digest":"digest"}}}'
    )
    path.write_text(corrupted, encoding="utf-8")

    with pytest.raises(StoreError):
        JsonIssueRecordStore(path).snapshot()
    assert path.read_text(encoding="utf-8") == corrupted


def test_optimistic_revision_allows_only_one_concurrent_transition(
    tmp_path: Path,
) -> None:
    proposal_service, workflow = workflow_pair(tmp_path)
    _request, record = create_record(
        proposal_service,
        workflow,
        category="logistics",
        risk_level="low",
        key="revision-001",
    )
    second_workflow = IssueWorkflowService(
        JsonIssueRecordStore(tmp_path / "issue-records.json"),
        confirmation_verifier=proposal_service.verify_confirmation,
    )
    transition = action(
        WorkflowAction.SUBMIT,
        record.revision,
        actor("reporter-1", ActorRole.REPORTER),
    )

    def submit(service: IssueWorkflowService) -> str:
        try:
            service.transition(record.record_id, transition)
            return "ok"
        except RevisionConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [workflow, second_workflow]))
    assert sorted(results) == ["conflict", "ok"]
