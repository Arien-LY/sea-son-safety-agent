"""Agent 受控工具的统一调用契约。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    ok: bool
    summary: str = Field(min_length=1, max_length=500)
    data: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = False
    error_code: str | None = None

    @model_validator(mode="after")
    def enforce_result_consistency(self) -> "ToolResult":
        if self.ok and self.error_code is not None:
            raise ValueError("成功工具结果不能包含错误码。")
        if self.ok and self.recoverable:
            raise ValueError("成功工具结果不能标记为可恢复错误。")
        if not self.ok and self.error_code is None:
            raise ValueError("失败工具结果必须包含稳定错误码。")
        return self


class AgentTool(ABC):
    name: str

    @abstractmethod
    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        """执行一次受控调用并返回可审核结果。"""


class ToolRegistry:
    def __init__(self, tools: Iterable[AgentTool] = ()) -> None:
        self._tools: dict[str, AgentTool] = {}
        for tool in tools:
            self.register(tool)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def register(self, tool: AgentTool) -> None:
        if not tool.name.strip():
            raise ValueError("工具名称不能为空。")
        if tool.name in self._tools:
            raise ValueError(f"工具 {tool.name} 重复注册。")
        self._tools[tool.name] = tool

    def replace(self, tool: AgentTool) -> None:
        if not tool.name.strip():
            raise ValueError("工具名称不能为空。")
        self._tools[tool.name] = tool

    def execute(self, name: str, arguments: Mapping[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                ok=False,
                summary=f"工具 {name} 未注册。",
                error_code="tool_not_found",
            )
        try:
            result = tool.run(arguments)
        except Exception:
            return ToolResult(
                tool_name=name,
                ok=False,
                summary=f"工具 {name} 执行时发生内部错误。",
                error_code="tool_execution_error",
            )
        if result.tool_name != name:
            return ToolResult(
                tool_name=name,
                ok=False,
                summary=f"工具 {name} 返回了不匹配的工具名称。",
                error_code="invalid_tool_result",
            )
        return result
