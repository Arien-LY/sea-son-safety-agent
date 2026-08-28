"""Hello-Agents 基础文字对话边界。"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, cast

from hello_agents import HelloAgentsLLM, SimpleAgent
from pydantic import ValidationError

from agents.prompts import BASIC_DIALOG_SYSTEM_PROMPT
from agents.schemas import BasicDialogReply, TextConsultationInput


class LLMInvoker(Protocol):
    """SimpleAgent 当前阶段所需的最小模型接口。"""

    def invoke(self, messages: list[dict[str, str]], **kwargs: object) -> str: ...


class DialogErrorCode(StrEnum):
    EMPTY_RESPONSE = "empty_response"
    INVALID_RESPONSE = "invalid_response"
    MODEL_TIMEOUT = "model_timeout"
    MODEL_ERROR = "model_error"
    UNSUPPORTED_TOOL_CALL = "unsupported_tool_call"


class DialogExecutionError(RuntimeError):
    """向调用方暴露稳定错误码，不泄露模型或服务商错误细节。"""

    def __init__(self, error_code: DialogErrorCode, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class _EmptyModelResponseError(ValueError):
    pass


class _UnsupportedToolCallError(ValueError):
    pass


class _ResponseGuard:
    """在框架写入内部历史前拦截不可接受的模型返回。"""

    def __init__(self, llm: LLMInvoker) -> None:
        self._llm = llm

    def invoke(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        response = self._llm.invoke(messages, **kwargs)
        if not isinstance(response, str) or not response.strip():
            raise _EmptyModelResponseError
        if "[TOOL_CALL:" in response:
            raise _UnsupportedToolCallError
        return response


class BasicConsultationDialog:
    """无工具、无共享历史的 Hello-Agents 单 Agent 对话。"""

    def __init__(self, llm: LLMInvoker) -> None:
        self._llm = llm

    def reply(self, input_data: TextConsultationInput) -> BasicDialogReply:
        """返回一条已校验回答；不执行工具或业务副作用。"""

        agent = SimpleAgent(
            name="sea-son-basic-consultation",
            llm=cast(HelloAgentsLLM, _ResponseGuard(self._llm)),
            system_prompt=BASIC_DIALOG_SYSTEM_PROMPT,
            tool_registry=None,
            enable_tool_calling=False,
        )

        try:
            response = agent.run(_format_user_input(input_data))
        except _EmptyModelResponseError as exc:
            raise DialogExecutionError(
                DialogErrorCode.EMPTY_RESPONSE,
                "模型未返回可用回答。",
            ) from exc
        except _UnsupportedToolCallError as exc:
            raise DialogExecutionError(
                DialogErrorCode.UNSUPPORTED_TOOL_CALL,
                "当前阶段不允许调用工具。",
            ) from exc
        except TimeoutError as exc:
            raise DialogExecutionError(
                DialogErrorCode.MODEL_TIMEOUT,
                "模型响应超时，请稍后重试。",
            ) from exc
        except Exception as exc:
            raise DialogExecutionError(
                DialogErrorCode.MODEL_ERROR,
                "模型暂时无法完成回答，请稍后重试。",
            ) from exc

        try:
            return BasicDialogReply(answer=response)
        except ValidationError as exc:
            raise DialogExecutionError(
                DialogErrorCode.INVALID_RESPONSE,
                "模型回答不符合基础对话契约。",
            ) from exc


def _format_user_input(input_data: TextConsultationInput) -> str:
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
