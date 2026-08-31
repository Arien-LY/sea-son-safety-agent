"""Serve the customer workbench and existing API from one loopback process."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware


def create_desktop_app(web_root: Path):
    from backend.app.main import create_app

    root = web_root.resolve(strict=True)
    if not (root / "index.html").is_file():
        raise ValueError("Missing customer interface")
    app = create_app(customer_mode=True)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != f"http://{request.headers.get('host')}":
            return JSONResponse({"detail": "此请求不是来自当前工作台。"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def customer_page(path: str):
        # Never use arbitrary path fallback: /api/missing and /.env must not return HTML.
        if path in {"", "chat", "consult", "submit", "records"} or (
            path.startswith("records/ISS-")
            and len(path) == len("records/ISS-") + 12
            and all(c in "0123456789ABCDEF" for c in path[len("records/ISS-"):])
        ):
            return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})
        parts = path.split("/")
        if path.startswith("assets/") and not any(p.startswith(".") or "\\" in p for p in parts):
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return FileResponse(candidate)
        raise HTTPException(status_code=404, detail="页面不存在。")

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user-data", type=Path, required=True)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("invalid local port")
    data = args.user_data.resolve()
    data.mkdir(parents=True, exist_ok=True)
    os.chdir(data)
    os.environ["ISSUE_STORE_PATH"] = str(data / "data" / "issue-records.json")
    os.environ["PHOTO_STORE_PATH"] = str(data / "uploads")
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    import uvicorn

    app = create_desktop_app(Path(__file__).resolve().parents[1] / "web")
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1,
                access_log=False, log_level="error", timeout_graceful_shutdown=5)


if __name__ == "__main__":
    main()
