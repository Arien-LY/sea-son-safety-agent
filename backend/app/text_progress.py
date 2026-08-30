"""Bounded, content-free execution events; never model reasoning or fake progress."""

import asyncio
import json
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from agents.text_assistant import TextError

Stage = Literal["queued", "preparing", "model_running", "validating", "tool_running", "completed"]
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


def stream_operation(action, *args) -> StreamingResponse:
    async def generate():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        started, sequence, closed = time.monotonic(), 0, False

        def progress(stage: Stage, tool: str | None = None):
            nonlocal sequence
            if closed:
                return
            sequence += 1
            event = ProgressEvent(seq=sequence, elapsed_ms=int((time.monotonic() - started) * 1000),
                                  stage=stage, tool=tool)
            # At most six fixed events per operation, never input-dependent iteration.
            with suppress(RuntimeError):
                loop.call_soon_threadsafe(queue.put_nowait, event.model_dump(mode="json"))

        async def execute():
            try:
                result = await run_in_threadpool(action, *args, progress=progress)
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
                if event["type"] != "progress":
                    break
        finally:
            closed = True
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(generate(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
