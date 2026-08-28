"""Hello-Agents 结构化问题分析边界。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, cast

from hello_agents import HelloAgentsLLM, SimpleAgent

from agents.prompts import ISSUE_ANALYSIS_SYSTEM_PROMPT
from agents.schemas import IssueAnalysis, TextConsultationInput
from agents.structured_output import AnalysisOutputError, parse_issue_analysis


class AnalysisLLMInvoker(Protocol):
    """结构化分析当前阶段所需的最小模型接口。"""

    def invoke(self, messages: list[dict[str, str]], **kwargs: object) -> str: ...


class AnalysisExecutionErrorCode(StrEnum):
    MODEL_TIMEOUT = "model_timeout"
    MODEL_ERROR = "model_error"


class AnalysisExecutionError(RuntimeError):
    """模型执行失败；结构化输出错误由 ``AnalysisOutputError`` 表达。"""

    def __init__(
        self, error_code: AnalysisExecutionErrorCode, message: str
    ) -> None:
        super().__init__(message)
        self.error_code = error_code


class _StructuredOutputGuard:
    """在 SimpleAgent 写入内部历史前校验并规范化模型 JSON。"""

    def __init__(self, llm: AnalysisLLMInvoker) -> None:
        self._llm = llm

    def invoke(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        raw_output: Any = self._llm.invoke(messages, **kwargs)
        analysis = parse_issue_analysis(raw_output)
        return analysis.model_dump_json()


class IssueAnalyzer:
    """无工具、无共享历史、严格结构化输出的单 Agent 分析器。"""

    def __init__(self, llm: AnalysisLLMInvoker) -> None:
        self._llm = llm

    def analyze(self, input_data: TextConsultationInput) -> IssueAnalysis:
        agent = SimpleAgent(
            name="sea-son-issue-analyzer",
            llm=cast(HelloAgentsLLM, _StructuredOutputGuard(self._llm)),
            system_prompt=ISSUE_ANALYSIS_SYSTEM_PROMPT,
            tool_registry=None,
            enable_tool_calling=False,
        )

        try:
            raw_output = agent.run(_format_analysis_input(input_data))
        except AnalysisOutputError:
            raise
        except TimeoutError as exc:
            raise AnalysisExecutionError(
                AnalysisExecutionErrorCode.MODEL_TIMEOUT,
                "模型分析超时，请稍后重试。",
            ) from exc
        except Exception as exc:
            raise AnalysisExecutionError(
                AnalysisExecutionErrorCode.MODEL_ERROR,
                "模型暂时无法完成结构化分析，请稍后重试。",
            ) from exc

        return parse_issue_analysis(raw_output)


def _format_analysis_input(input_data: TextConsultationInput) -> str:
    context = [
        ("项目标签", input_data.project),
        ("区域标签", input_data.area),
        ("咨询者角色", input_data.requester_role),
    ]
    provided_context = [f"- {label}：{value}" for label, value in context if value]
    if not provided_context:
        return input_data.message

    context_text = "\n".join(provided_context)
    return (
        "以下上下文由用户自报且未经核实，不代表权限、责任或正式业务主数据：\n"
        f"{context_text}\n\n"
        f"用户消息：\n{input_data.message}"
    )
