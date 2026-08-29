"""受控 Agent 工具。"""

from agents.tools.base import AgentTool, ToolRegistry, ToolResult
from agents.tools.propose_issue_record import (
    IssueRecordProposal,
    ProposeIssueRecordTool,
    build_issue_proposal_registry,
)

__all__ = [
    "AgentTool",
    "IssueRecordProposal",
    "ProposeIssueRecordTool",
    "ToolRegistry",
    "ToolResult",
    "build_issue_proposal_registry",
]
