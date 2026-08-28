"""Agent 运行配置。密钥只从环境变量读取。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class AgentConfigurationError(ValueError):
    """运行配置缺失或格式错误。"""


@dataclass(frozen=True, slots=True)
class AgentConfig:
    api_key: str = field(repr=False)
    model: str
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2
    max_output_tokens: int = 4_096
    max_steps: int = 4

    @classmethod
    def from_env(cls, dotenv_path: str | Path | None = ".env") -> "AgentConfig":
        """加载本地 ``.env``（若存在），再读取当前进程环境变量。"""

        if dotenv_path is not None:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "AgentConfig":
        api_key = values.get("LLM_API_KEY", "").strip()
        model = values.get("LLM_MODEL", "").strip()
        if not api_key:
            raise AgentConfigurationError(
                "缺少 LLM_API_KEY；请复制 .env.example 为 .env 后填写。"
            )
        if not model:
            raise AgentConfigurationError("缺少 LLM_MODEL；请填写服务商提供的模型名。")

        timeout_seconds = _parse_positive_float(
            values.get("LLM_TIMEOUT_SECONDS", "60"), "LLM_TIMEOUT_SECONDS"
        )
        max_retries = _parse_non_negative_int(
            values.get("LLM_MAX_RETRIES", "2"), "LLM_MAX_RETRIES"
        )
        max_output_tokens = _parse_positive_int(
            values.get("LLM_MAX_OUTPUT_TOKENS", "4096"),
            "LLM_MAX_OUTPUT_TOKENS",
        )
        max_steps = _parse_bounded_int(
            values.get("AGENT_MAX_STEPS", "4"),
            "AGENT_MAX_STEPS",
            minimum=1,
            maximum=10,
        )
        return cls(
            api_key=api_key,
            model=model,
            base_url=values.get("LLM_BASE_URL", "").strip() or None,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            max_steps=max_steps,
        )


def _parse_positive_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise AgentConfigurationError(f"{name} 必须是数字。") from exc
    if value <= 0:
        raise AgentConfigurationError(f"{name} 必须大于 0。")
    return value


def _parse_non_negative_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise AgentConfigurationError(f"{name} 必须是整数。") from exc
    if value < 0:
        raise AgentConfigurationError(f"{name} 不能小于 0。")
    return value


def _parse_positive_int(raw: str, name: str) -> int:
    value = _parse_non_negative_int(raw, name)
    if value == 0:
        raise AgentConfigurationError(f"{name} 必须大于 0。")
    return value


def _parse_bounded_int(
    raw: str, name: str, *, minimum: int, maximum: int
) -> int:
    value = _parse_non_negative_int(raw, name)
    if not minimum <= value <= maximum:
        raise AgentConfigurationError(
            f"{name} 必须在 {minimum}～{maximum} 之间。"
        )
    return value
