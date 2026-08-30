"""Read-only application composition with authoritative Phase 3 review events."""

from agents.knowledge import HumanConclusion
from agents.knowledge_answer import KnowledgeAnswer, KnowledgeAnswerBuilder, KnowledgeAnswerRequest, RecordKnowledgeRequest
from backend.app.workflow import IssueWorkflowService
from backend.app.workflow_models import WorkflowAction, WorkflowStatus


def answer_for_record(
    record_id: str, request: RecordKnowledgeRequest, *,
    workflow: IssueWorkflowService, builder: KnowledgeAnswerBuilder,
) -> KnowledgeAnswer:
    record = workflow.get(record_id)
    answer = builder.build(KnowledgeAnswerRequest(
        analysis=record.analysis, query=request.query, jurisdiction=request.jurisdiction,
    ))
    if record.status is WorkflowStatus.CLOSED:
        event = next((event for event in reversed(record.events)
                      if event.action is WorkflowAction.CLOSE), None)
        if event is not None:
            answer.human_conclusion = HumanConclusion(
                status="reviewed", record_id=record.record_id, revision=record.revision,
                actor_id=event.actor_id, actor_role=event.actor_role.value,
                occurred_at=event.occurred_at, note=event.note,
            )
    return answer
