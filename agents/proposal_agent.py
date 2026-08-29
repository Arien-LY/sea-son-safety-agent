"""经严格校验的 IssueAnalysis 到原生 Function Calling 的受控边界。"""

from __future__ import annotations

import json
from typing import Any, cast

from hello_agents import FunctionCallAgent, HelloAgentsLLM
from hello_agents import ToolRegistry as HelloAgentsToolRegistry
from hello_agents.tools import Tool, ToolParameter
from pydantic import ValidationError

from agents.schemas import IssueAnalysis, RecommendedRoute
from agents.tools import ProposeIssueRecordTool, ToolResult


ELIGIBLE_PROPOSAL_ROUTES = frozenset(
    {RecommendedRoute.PROPOSE_WORKFLOW, RecommendedRoute.HUMAN_REVIEW}
)

ISSUE_PROPOSAL_SYSTEM_PROMPT = """你只能处理系统提供的、已经校验通过的 IssueAnalysis。
当且仅当该分析需要留痕或人工跟进时，调用 propose_issue_record 一次。
工具参数必须逐字段原样复制输入 JSON，不得补充、改写、删减或猜测任何事实。
工具只生成待用户确认的提案，不代表已经保存、派单或改变业务状态。
不要输出或记录隐藏思维链。"""


class _BoundProposalTool(Tool):
    """把原生工具调用绑定到一个不可被模型改写的已校验分析。"""

    def __init__(self, expected_analysis: IssueAnalysis) -> None:
        self._controlled_tool = ProposeIssueRecordTool()
        self._expected_analysis = expected_analysis
        self.last_result: ToolResult | None = None
        super().__init__(
            name=self._controlled_tool.name,
            description=self._controlled_tool.description,
        )

    def get_parameters(self) -> list[ToolParameter]:
        """供 Hello-Agents 发现字段；严格 Schema 由 Agent 覆盖提供。"""

        return [
            ToolParameter(
                name=name,
                type="raw",
                description="必须与已校验 IssueAnalysis 中的同名字段完全一致。",
            )
            for name in IssueAnalysis.model_fields
        ]

    def run(self, parameters: dict[str, Any]) -> str:
        try:
            candidate_json = json.dumps(parameters, ensure_ascii=False)
            candidate = IssueAnalysis.model_validate_json(candidate_json, strict=True)
        except (TypeError, ValueError, ValidationError):
            result = self._controlled_tool.run(parameters)
            self.last_result = result
            return result.model_dump_json()

        if candidate != self._expected_analysis:
            result = ToolResult(
                tool_name=self.name,
                ok=False,
                summary="工具参数与已校验的问题分析不一致。",
                recoverable=True,
                error_code="analysis_mismatch",
            )
            self.last_result = result
            return result.model_dump_json()

        result = self._controlled_tool.run(parameters)
        self.last_result = result
        return result.model_dump_json()


class _StrictIssueFunctionCallAgent(FunctionCallAgent):
    """在固定版本 Hello-Agents 上保留完整 Schema 与严格 JSON 类型。"""

    def __init__(self, *args: Any, function_schema: dict[str, Any], **kwargs: Any):
        self._function_schema = function_schema
        super().__init__(*args, **kwargs)

    def _build_tool_schemas(self) -> list[dict[str, Any]]:
        return [self._function_schema]

    def _execute_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        if not self.tool_registry:
            return "工具注册表未配置。"
        tool = self.tool_registry.get_tool(tool_name)
        if tool is None:
            return f"工具 {tool_name} 未注册。"
        return tool.run(arguments)


class IssueProposalAgent:
    """只为需要跟进的已校验分析执行单轮原生工具调用。"""

    def __init__(self, llm: HelloAgentsLLM) -> None:
        self._llm = llm

    def propose(self, analysis: IssueAnalysis) -> ToolResult | None:
        if not isinstance(analysis, IssueAnalysis):
            raise TypeError("IssueProposalAgent 只接受已校验的 IssueAnalysis。")
        if analysis.recommended_route not in ELIGIBLE_PROPOSAL_ROUTES:
            return None

        bound_tool = _BoundProposalTool(analysis)
        registry = HelloAgentsToolRegistry()
        registry.register_tool(bound_tool)
        function_schema = ProposeIssueRecordTool().to_openai_schema()
        agent = _StrictIssueFunctionCallAgent(
            name="sea-son-issue-proposal-agent",
            llm=cast(HelloAgentsLLM, self._llm),
            system_prompt=ISSUE_PROPOSAL_SYSTEM_PROMPT,
            tool_registry=registry,
            enable_tool_calling=True,
            default_tool_choice={
                "type": "function",
                "function": {"name": ProposeIssueRecordTool.name},
            },
            max_tool_iterations=1,
            function_schema=function_schema,
        )
        agent.run(analysis.model_dump_json())

        if bound_tool.last_result is None:
            return ToolResult(
                tool_name=ProposeIssueRecordTool.name,
                ok=False,
                summary="模型未执行要求的问题记录提案工具调用。",
                recoverable=True,
                error_code="tool_not_called",
            )
        return bound_tool.last_result
