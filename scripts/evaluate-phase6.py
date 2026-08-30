"""Generate a deterministic Phase 6 report from an explicit observation file."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import build_report, load_run, render_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="strict evaluation run JSON")
    parser.add_argument("--output", required=True, type=Path, help="report JSON path")
    parser.add_argument(
        "--cases", type=Path,
        default=PROJECT_ROOT / "tests" / "fixtures" / "phase1_acceptance_cases.v1.json",
    )
    args = parser.parse_args()
    report = render_report(build_report(load_run(args.run), args.cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent,
            prefix=".phase6-report-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(report)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, args.output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(f"Phase 6 report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
