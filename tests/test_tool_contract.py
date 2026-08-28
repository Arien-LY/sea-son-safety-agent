from collections.abc import Mapping
from typing import Any

from agents.tools import AgentTool, ToolRegistry, ToolResult


class EchoTool(AgentTool):
    name = "echo"

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            ok=True,
            summary="已接收测试参数。",
            data={"value": arguments.get("value")},
        )


def test_tool_registry_returns_uniform_result() -> None:
    registry = ToolRegistry([EchoTool()])

    result = registry.execute("echo", {"value": "ok"})

    assert result.ok is True
    assert result.data == {"value": "ok"}


def test_unknown_tool_returns_stable_error_code() -> None:
    registry = ToolRegistry()

    result = registry.execute("missing", {})

    assert result.ok is False
    assert result.error_code == "tool_not_found"

