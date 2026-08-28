import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.schemas import TextConsultationInput


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase1_text_consultation_input.v1.schema.json"
)


def test_message_only_is_valid_and_trimmed() -> None:
    input_data = TextConsultationInput(message="  安全帽下颏带怎么检查？  ")

    assert input_data.message == "安全帽下颏带怎么检查？"
    assert input_data.project is None
    assert input_data.area is None
    assert input_data.requester_role is None


def test_optional_context_is_trimmed_but_remains_user_supplied_text() -> None:
    input_data = TextConsultationInput(
        message="二层西侧临边护栏被拆了。",
        project="  海景花园项目  ",
        area="  2 号楼西侧  ",
        requester_role="  安全员  ",
    )

    assert input_data.model_dump() == {
        "message": "二层西侧临边护栏被拆了。",
        "project": "海景花园项目",
        "area": "2 号楼西侧",
        "requester_role": "安全员",
    }


def test_optional_context_accepts_explicit_null() -> None:
    input_data = TextConsultationInput.model_validate(
        {
            "message": "空调不制冷。",
            "project": None,
            "area": None,
            "requester_role": None,
        }
    )

    assert input_data.project is None
    assert input_data.area is None
    assert input_data.requester_role is None


@pytest.mark.parametrize("message", ["", " \t\r\n "])
def test_empty_or_whitespace_only_message_is_rejected(message: str) -> None:
    with pytest.raises(ValidationError):
        TextConsultationInput(message=message)


@pytest.mark.parametrize("value", [123, True, b"binary text"])
def test_message_uses_strict_string_type(value: object) -> None:
    with pytest.raises(ValidationError):
        TextConsultationInput.model_validate({"message": value})


@pytest.mark.parametrize("field", ["project", "area", "requester_role"])
@pytest.mark.parametrize("value", ["", "   "])
def test_present_optional_context_must_not_be_blank(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TextConsultationInput.model_validate({"message": "测试消息", field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("message", "消" * 1_001),
        ("project", "项" * 101),
        ("area", "区" * 201),
        ("requester_role", "角" * 51),
    ],
)
def test_length_limits_are_enforced(field: str, value: str) -> None:
    payload = {"message": "测试消息", field: value}

    with pytest.raises(ValidationError):
        TextConsultationInput.model_validate(payload)


@pytest.mark.parametrize(
    "forbidden_field",
    ["image", "images", "file", "image_binary", "project_id", "permissions"],
)
def test_extra_fields_including_images_and_authority_are_rejected(
    forbidden_field: str,
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TextConsultationInput.model_validate(
            {"message": "测试消息", forbidden_field: "not-accepted"}
        )


def test_frozen_json_schema_matches_the_pydantic_contract() -> None:
    frozen_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert frozen_schema.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert frozen_schema.pop("$id").endswith(
        "/phase1-text-consultation-input-v1.schema.json"
    )
    assert frozen_schema == TextConsultationInput.model_json_schema()
