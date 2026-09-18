"""Product text API contracts; frozen Phase 1 input stays unchanged."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.schemas import TextConsultationInput
from agents.text_assistant import TextReply, ChatInput, ChatReply
from agents.chat_settings import CHAT_MAX_TURNS


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    intent: Literal["chat", "consult", "auto"] = "consult"
    thinking_mode: Literal["fast", "deep"] = "fast"
    tools_enabled: bool = False
    model: str | None = Field(default=None, min_length=1, max_length=100,
                              pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    input: ChatInput
    consultation_id: str | None = Field(default=None, pattern=r"^TXT-[a-f0-9]{32}$")
    expected_turn: int = Field(default=0, ge=0, le=CHAT_MAX_TURNS)
    allow_external: bool = False
    photo_id: str | None = Field(default=None, pattern=r"^PHOTO-[A-F0-9]{24}$")
    allow_image_external: bool = False

    @model_validator(mode="before")
    @classmethod
    def image_only_message(cls, value):
        if isinstance(value, dict) and value.get("photo_id") and isinstance(value.get("input"), dict):
            message = value["input"].get("message", "")
            if isinstance(message, str) and not message.strip():
                return {**value, "input": {**value["input"], "message": "请描述这张图片中的可见内容；不确定的地方请说明。"}}
        return value

    @model_validator(mode="after")
    def turn_matches_session(self) -> "TextRequest":
        if self.photo_id and self.intent == "consult":
            raise ValueError("Images use chat or auto intent.")
        if self.intent == "consult":
            TextConsultationInput.model_validate(self.input.model_dump())
            if self.expected_turn > 6:
                raise ValueError("Consultation is limited to six turns.")
        if (self.consultation_id is None) != (self.expected_turn == 0):
            raise ValueError("Initial requests use turn zero; follow-ups require a session.")
        return self


class TextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    consultation_id: str
    turn: int
    mode: Literal["mock", "real"]
    model: str
    reply: TextReply | ChatReply
    can_propose: bool
    risk_retained: bool
    remaining_turns: int
    photo_id: str | None = Field(default=None, pattern=r"^PHOTO-[A-F0-9]{24}$")
    context_trimmed: bool = False
    analysis_status: Literal["validated", "unavailable", "not_requested"] = "validated"
    sources: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    tool_results: list[dict] = Field(default_factory=list, max_length=4)


class TextProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_turn: int = Field(ge=1, le=6)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirm(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("Confirmation must be a JSON boolean.")
        return value
