"""Read-only native-function tool, with bounded, redacted audit records."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from agents.knowledge import CATALOG_PATH, SearchKnowledgeRequest, load_catalog, retrieve
from agents.tools.audit import ToolAuditLog
from agents.tools.base import AgentTool, ToolRegistry, ToolResult


class SearchKnowledgeTool(AgentTool):
    name = "search_knowledge"

    def __init__(
        self, *, catalog_path: Path = CATALOG_PATH, enabled: bool = True,
        clock: Callable[[], date] = date.today, audit_log: ToolAuditLog | None = None,
    ) -> None:
        self._path = catalog_path
        self._enabled = enabled
        self._clock = clock
        self.audit_log = audit_log or ToolAuditLog()

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "只读查询已核验目录中的候选依据。必须明确地区；不得据此归责或推进状态。",
                "parameters": SearchKnowledgeRequest.model_json_schema(),
            },
        }

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            request = SearchKnowledgeRequest.model_validate_json(
                json.dumps(dict(arguments), ensure_ascii=False, allow_nan=False),
            )
        except (TypeError, ValueError):
            result = self._error("invalid_arguments", "知识检索参数无效。")
        else:
            if not self._enabled:
                result = self._error("knowledge_disabled", "知识库已关闭，核心咨询仍可使用。")
            else:
                try:
                    data = retrieve(load_catalog(self._path), request, as_of=self._clock())
                    result = ToolResult(
                        tool_name=self.name, ok=True,
                        summary=f"检索到 {len(data.citations)} 条候选依据，适用性须由专业人员核实。",
                        data=data.model_dump(mode="json"),
                    )
                except Exception:
                    result = self._error("knowledge_unavailable", "知识库暂不可用，未生成引用。")
        self.audit_log.record(tool_name=self.name, arguments=arguments, result=result)
        return result

    def _error(self, code: str, summary: str) -> ToolResult:
        return ToolResult(tool_name=self.name, ok=False, summary=summary,
                          recoverable=True, error_code=code)


def build_knowledge_registry(tool: SearchKnowledgeTool | None = None) -> ToolRegistry:
    """Keep this read-only capability separate from the Phase 2 proposal registry."""
    return ToolRegistry([tool or SearchKnowledgeTool()])
