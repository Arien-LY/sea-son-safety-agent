import json
from pathlib import Path
from typing import Any

import pytest

from agents.dialog import (
    BasicConsultationDialog,
    DialogErrorCode,
    DialogExecutionError,
)
from agents.prompts import BASIC_DIALOG_SYSTEM_PROMPT
from agents.schemas import BasicDialogReply, TextConsultationInput


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase1_basic_dialog_reply.v1.schema.json"
)


class FakeLLM:
    """只返回预设结果，不创建客户端、不访问网络或读取密钥。"""

    def __init__(self, *results: str | None | Exception) -> None:
        self._results = list(results)
        self.calls: list[list[dict[str, str]]] = []

    def invoke(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> Any:
        self.calls.append([message.copy() for message in messages])
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_ordinary_consultation_returns_validated_direct_answer() -> None:
    fake_llm = FakeLLM("  下颏带应贴合下颌，佩戴后检查是否容易松脱。  ")
    dialog = BasicConsultationDialog(fake_llm)

    reply = dialog.reply(TextConsultationInput(message="安全帽下颏带怎么检查？"))

    assert reply == BasicDialogReply(
        answer="下颏带应贴合下颌，佩戴后检查是否容易松脱。"
    )
    assert fake_llm.calls == [
        [
            {"role": "system", "content": BASIC_DIALOG_SYSTEM_PROMPT},
            {"role": "user", "content": "安全帽下颏带怎么检查？"},
        ]
    ]


def test_optional_context_is_labeled_as_unverified_user_statement() -> None:
    fake_llm = FakeLLM("请先确认空调是否有异响、异味或漏水。")
    dialog = BasicConsultationDialog(fake_llm)

    dialog.reply(
        TextConsultationInput(
            message="空调不制冷怎么办？",
            project="海景花园项目",
            area="宿舍 3 楼 305",
            requester_role="管理员",
        )
    )

    user_message = fake_llm.calls[0][-1]
    assert user_message["role"] == "user"
    assert "用户自报且未经核实" in user_message["content"]
    assert "项目标签：海景花园项目" in user_message["content"]
    assert "区域标签：宿舍 3 楼 305" in user_message["content"]
    assert "咨询者角色：管理员" in user_message["content"]
    assert user_message["content"].endswith("用户消息：\n空调不制冷怎么办？")


def test_each_reply_uses_one_agent_without_shared_history() -> None:
    fake_llm = FakeLLM("第一次回答。", "第二次回答。")
    dialog = BasicConsultationDialog(fake_llm)

    dialog.reply(TextConsultationInput(message="第一个问题"))
    dialog.reply(TextConsultationInput(message="第二个问题"))

    assert len(fake_llm.calls) == 2
    assert [message["role"] for message in fake_llm.calls[0]] == ["system", "user"]
    assert [message["role"] for message in fake_llm.calls[1]] == ["system", "user"]
    assert fake_llm.calls[1][-1]["content"] == "第二个问题"
    assert "第一次回答" not in str(fake_llm.calls[1])


@pytest.mark.parametrize("response", [None, "", " \t\r\n "])
def test_empty_model_response_has_stable_error(response: str | None) -> None:
    dialog = BasicConsultationDialog(FakeLLM(response))

    with pytest.raises(DialogExecutionError) as captured:
        dialog.reply(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == DialogErrorCode.EMPTY_RESPONSE
    assert str(captured.value) == "模型未返回可用回答。"


def test_timeout_has_stable_error_without_provider_details() -> None:
    dialog = BasicConsultationDialog(FakeLLM(TimeoutError("provider detail")))

    with pytest.raises(DialogExecutionError) as captured:
        dialog.reply(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == DialogErrorCode.MODEL_TIMEOUT
    assert "provider detail" not in str(captured.value)


def test_model_failure_has_stable_error_without_provider_details() -> None:
    dialog = BasicConsultationDialog(FakeLLM(RuntimeError("secret provider detail")))

    with pytest.raises(DialogExecutionError) as captured:
        dialog.reply(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == DialogErrorCode.MODEL_ERROR
    assert "secret provider detail" not in str(captured.value)


def test_tool_call_marker_is_rejected_and_never_executed() -> None:
    dialog = BasicConsultationDialog(FakeLLM("[TOOL_CALL:create_task:title=测试]"))

    with pytest.raises(DialogExecutionError) as captured:
        dialog.reply(TextConsultationInput(message="帮我创建任务"))

    assert captured.value.error_code == DialogErrorCode.UNSUPPORTED_TOOL_CALL


def test_overlong_model_response_is_rejected() -> None:
    dialog = BasicConsultationDialog(FakeLLM("答" * 4_001))

    with pytest.raises(DialogExecutionError) as captured:
        dialog.reply(TextConsultationInput(message="测试消息"))

    assert captured.value.error_code == DialogErrorCode.INVALID_RESPONSE


def test_frozen_reply_schema_matches_pydantic_contract() -> None:
    frozen_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert frozen_schema.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert frozen_schema.pop("$id").endswith(
        "/phase1-basic-dialog-reply-v1.schema.json"
    )
    assert frozen_schema == BasicDialogReply.model_json_schema()
