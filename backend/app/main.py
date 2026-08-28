from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.runtime import runtime_info


def create_app() -> FastAPI:
    app = FastAPI(
        title="海之子 · 安全质量 Agent API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def get_runtime() -> dict[str, str]:
        mode = os.getenv("AGENT_MODE", "mock").strip().casefold()
        if mode not in {"mock", "real"}:
            mode = "mock"
        return {"agent_mode": mode, **runtime_info()}

    return app


app = create_app()

