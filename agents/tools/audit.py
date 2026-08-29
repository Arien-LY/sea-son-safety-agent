"""不记录原始参数或思维链的受控工具审计。"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agents.tools.base import ToolResult


class ToolAuditEvent(BaseModel):
    """一次工具结果的最小、脱敏、可审核记录。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    occurred_at: datetime
    tool_name: str = Field(min_length=1, max_length=100)
    argument_keys: tuple[str, ...]
    argument_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ok: bool
    result_summary: str = Field(min_length=1, max_length=500)
    error_code: str | None = None


def summarize_arguments(arguments: Mapping[str, Any]) -> tuple[tuple[str, ...], str]:
    """只返回字段名和稳定摘要，不返回字段值。"""

    keys = tuple(sorted(str(key) for key in arguments))
    canonical = json.dumps(
        dict(arguments),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda _value: "<non-json-value>",
    ).encode("utf-8")
    return keys, f"sha256:{hashlib.sha256(canonical).hexdigest()}"


class ToolAuditLog:
    """容量受限的进程内审计缓冲区；不是业务记录持久化。"""

    def __init__(
        self,
        *,
        max_events: int = 500,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_events < 1:
            raise ValueError("审计缓冲区容量必须大于零。")
        self._events: deque[ToolAuditEvent] = deque(maxlen=max_events)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = Lock()

    def record(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        result: ToolResult,
    ) -> ToolAuditEvent:
        argument_keys, argument_digest = summarize_arguments(arguments)
        occurred_at = self._clock()
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        event = ToolAuditEvent(
            occurred_at=occurred_at,
            tool_name=tool_name,
            argument_keys=argument_keys,
            argument_digest=argument_digest,
            ok=result.ok,
            result_summary=result.summary,
            error_code=result.error_code,
        )
        with self._lock:
            self._events.append(event)
        return event

    def snapshot(self) -> tuple[ToolAuditEvent, ...]:
        with self._lock:
            return tuple(self._events)
