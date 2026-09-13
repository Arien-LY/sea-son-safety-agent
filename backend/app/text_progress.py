"""Bounded, content-free execution events; never model reasoning or fake progress."""

import asyncio
import json
import time
from concurrent.futures import TimeoutError as FutureTimeout
from threading import Event
from collections.abc import Callable
from contextlib import suppress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from agents.text_assistant import TextError

Stage = Literal["queued", "preparing", "model_running", "validating", "tool_running", "tool_completed", "responding", "completed"]
ProgressSink = Callable[[Stage, str | None], None]


def ignore_progress(stage: Stage, tool: str | None = None) -> None:
    pass


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["progress"] = "progress"
    seq: int = Field(ge=1)
    elapsed_ms: int = Field(ge=0)
    stage: Stage
    tool: Literal["propose_issue_record", "web_search", "read_webpage", "current_time", "search_knowledge", "calculate"] | None = None


class ContentDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["content_delta"] = "content_delta"
    index: int = Field(ge=1, le=64000)
    text: str = Field(min_length=1, max_length=1000)


def stream_operation(action, *args, stream_answer: bool = False) -> StreamingResponse:
    async def generate():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=128)
        started, sequence, closed = time.monotonic(), 0, False
        stopped = Event()
        delta_index, delta_chars = 0, 0

        def publish(event: dict):
            if stopped.is_set():
                raise TextError("text_cancelled", "已停止接收回答。")
            future = asyncio.run_coroutine_threadsafe(queue.put(event), loop)
            while True:
                try:
                    return future.result(timeout=0.1)
                except FutureTimeout:
                    if stopped.is_set() or time.monotonic() - started > 185:
                        future.cancel()
                        raise TextError("text_cancelled", "已停止接收回答。")

        def progress(stage: Stage, tool: str | None = None):
            nonlocal sequence
            if closed:
                return
            # Completion is emitted after any validated answer deltas have been delivered.
            if stage == "completed":
                return
            sequence += 1
            event = ProgressEvent(seq=sequence, elapsed_ms=int((time.monotonic() - started) * 1000),
                                  stage=stage, tool=tool)
            publish(event.model_dump(mode="json"))

        def on_text(text: str):
            nonlocal delta_index, delta_chars
            if not delta_index:
                progress("responding")
            delta_chars += len(text)
            if delta_chars > 64000:
                raise TextError("invalid_text_output", "文字流超出容量上限。")
            for offset in range(0, len(text), 1000):
                delta_index += 1
                publish(ContentDeltaEvent(index=delta_index, text=text[offset:offset + 1000]).model_dump(mode="json"))

        async def execute():
            nonlocal sequence
            try:
                options = {"progress": progress}
                if stream_answer:
                    options["on_text"] = on_text
                result = await run_in_threadpool(action, *args, **options)
                if stream_answer and not delta_index:
                    answer = result.reply.answer
                    sequence += 1
                    await queue.put(ProgressEvent(
                        seq=sequence, elapsed_ms=int((time.monotonic() - started) * 1000),
                        stage="responding", tool=None,
                    ).model_dump(mode="json"))
                    chunk_size = 1000
                    for index, offset in enumerate(range(0, len(answer), chunk_size), start=1):
                        await queue.put(ContentDeltaEvent(
                            index=index, text=answer[offset:offset + chunk_size],
                        ).model_dump(mode="json"))
                sequence += 1
                await queue.put(ProgressEvent(
                    seq=sequence, elapsed_ms=int((time.monotonic() - started) * 1000),
                    stage="completed", tool=None,
                ).model_dump(mode="json"))
                event = {"type": "result", "data": result.model_dump(mode="json")}
            except TextError as exc:
                event = {"type": "error", "error_code": exc.code, "message": exc.message}
            except Exception:
                event = {"type": "error", "error_code": "text_internal_error", "message": "文字请求暂时失败，请手动重试。"}
            await queue.put(event)

        task = asyncio.create_task(execute())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in {"result", "error"}:
                    break
        finally:
            closed = True
            stopped.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(generate(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
