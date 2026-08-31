"""Bounded, content-free execution events; never model reasoning or fake progress."""

import asyncio
import json
import math
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from agents.text_assistant import TextError

Stage = Literal["queued", "preparing", "model_running", "validating", "tool_running", "responding", "completed"]
ProgressSink = Callable[[Stage, str | None], None]


def ignore_progress(stage: Stage, tool: str | None = None) -> None:
    pass


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["progress"] = "progress"
    seq: int = Field(ge=1)
    elapsed_ms: int = Field(ge=0)
    stage: Stage
    tool: Literal["propose_issue_record"] | None = None


class ContentDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["content_delta"] = "content_delta"
    index: int = Field(ge=1, le=120)
    text: str = Field(min_length=1, max_length=1000)


def stream_operation(action, *args, stream_answer: bool = False) -> StreamingResponse:
    async def generate():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        started, sequence, closed = time.monotonic(), 0, False

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
            # At most six fixed events per operation, never input-dependent iteration.
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(queue.put_nowait, event.model_dump(mode="json"))

        async def execute():
            nonlocal sequence
            try:
                result = await run_in_threadpool(action, *args, progress=progress)
                if stream_answer:
                    answer = result.reply.answer
                    sequence += 1
                    await queue.put(ProgressEvent(
                        seq=sequence, elapsed_ms=int((time.monotonic() - started) * 1000),
                        stage="responding", tool=None,
                    ).model_dump(mode="json"))
                    chunk_size = min(1000, max(12, math.ceil(len(answer) / 120)))
                    for index, offset in enumerate(range(0, len(answer), chunk_size), start=1):
                        await queue.put(ContentDeltaEvent(
                            index=index, text=answer[offset:offset + chunk_size],
                        ).model_dump(mode="json"))
                        # Yield to the transport and renderer; this is validated presentation output,
                        # not a fabricated model step or hidden reasoning.
                        await asyncio.sleep(0.01)
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
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(generate(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
