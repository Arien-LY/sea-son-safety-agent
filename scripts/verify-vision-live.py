"""Explicit, one-call paid smoke; never imported by pytest/verify.ps1."""

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import dotenv_values
from PIL import Image, ImageDraw

from agents.vision import (
    DeepSeekVisionBackend, SingleImageAnalyzer, VisionAnalysis, VisionConfig,
    VisionError, VISION_SYSTEM_PROMPT,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="One authorized synthetic-image smoke, <=1024 output tokens, no retries.")
    parser.add_argument("--confirm-paid", action="store_true")
    options = parser.parse_args()
    if not options.confirm_paid:
        print("拒绝联网：需显式 --confirm-paid 并获得用户费用授权。")
        return 2
    config_values = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    config = VisionConfig(
        api_key=config_values.get("LLM_API_KEY") or "",
        model=config_values.get("VISION_MODEL") or "",
        base_url=config_values.get("LLM_BASE_URL") or "",
        max_output_tokens=1024,
    )
    picture = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(picture)
    draw.rectangle((40, 40, 220, 220), fill="red")
    draw.ellipse((290, 290, 460, 460), fill="blue")
    buffer = io.BytesIO()
    picture.save(buffer, "JPEG")
    jpeg = buffer.getvalue()
    context = "这是一张纯几何合成测试图，不是真实工地。请描述可见形状和颜色，不创建施工问题。"
    # Conservative upper estimate: one text token per UTF-8 byte + max 384 image tokens.
    prompt_bytes = len((VISION_SYSTEM_PROMPT + "\nJSON Schema:\n" + json.dumps(
        VisionAnalysis.model_json_schema(), ensure_ascii=False) + "用户补充（未经核实）：\n" + context).encode("utf-8"))
    estimated_max_usd = (prompt_bytes + 384) * 0.44 / 1_000_000 + 1024 * 1.32 / 1_000_000
    if estimated_max_usd > 0.01:
        print(json.dumps({"ok": False, "error_code": "smoke_budget_limit"}))
        return 2
    started = time.monotonic()
    backend = DeepSeekVisionBackend(config)
    report = {"model": config.model, "synthetic_image_sha256": hashlib.sha256(jpeg).hexdigest(),
              "max_output_tokens": 1024, "max_retries": 0, "worst_case_usd_estimate": round(estimated_max_usd, 6)}
    try:
        result = SingleImageAnalyzer(backend).analyze(jpeg, context, low_resolution=False)
        report.update(ok=not result.candidates and any(item.status == "observed" for item in result.observations),
                      candidate_count=len(result.candidates),
                      observation_statuses=[item.status for item in result.observations],
                      preliminary_only=result.preliminary_only, requires_human_review=result.requires_human_review)
    except VisionError as exc:
        report.update(ok=False, error_code=exc.code)
    report.update(usage=backend.usage, elapsed_seconds=round(time.monotonic() - started, 2))
    if backend.usage:
        report["peak_price_usd_estimate"] = round(
            backend.usage["prompt_tokens"] * 0.44 / 1_000_000
            + backend.usage["completion_tokens"] * 1.32 / 1_000_000, 6,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
