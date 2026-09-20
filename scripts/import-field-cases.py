#!/usr/bin/env python
"""把公开施工现场问题案例库导入独立 SQLite。

这些数据是公开案例 + Agent 评估案例，不是正式工单、规范知识或专业裁决结果。

用法：
    python scripts/import-field-cases.py <源目录> [--db data/field-cases.sqlite3]
                                              [--images data/field-case-images]

导入使用单个 SQLite 事务，可重复运行且保持 100 条；不修改源目录、聊天数据库或正式工单 Store。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "field-cases.sqlite3"
DEFAULT_IMAGES = REPO_ROOT / "data" / "field-case-images"

CASE_COLUMNS = (
    "id", "number", "source_type", "category", "category_key", "topic", "title",
    "original_excerpt", "excerpt_is_complete", "summary", "source_id", "website",
    "source_url", "source_title", "published_date", "retrieved_date", "locator",
    "reported_outcome", "adjudication_status", "evidence_status", "image_status",
    "split_group", "raw_json",
)
IMAGE_COLUMNS = (
    "case_id", "url", "alt", "status", "local_path", "attachment_id", "http_status", "reason",
)
CATEGORY_KEYS = {"安全": "safety", "质量": "quality", "管理": "management", "后勤": "logistics"}
EXPECTED_CATEGORIES = {"safety": 40, "quality": 43, "management": 12, "logistics": 5}

SCHEMA = """
CREATE TABLE IF NOT EXISTS field_cases (
    id TEXT PRIMARY KEY,
    number INTEGER NOT NULL,
    source_type TEXT,
    category TEXT,
    category_key TEXT,
    topic TEXT,
    title TEXT,
    original_excerpt TEXT,
    excerpt_is_complete INTEGER,
    summary TEXT,
    source_id TEXT,
    website TEXT,
    source_url TEXT,
    source_title TEXT,
    published_date TEXT,
    retrieved_date TEXT,
    locator TEXT,
    reported_outcome TEXT,
    adjudication_status TEXT,
    evidence_status TEXT,
    image_status TEXT,
    split_group TEXT,
    raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS field_case_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES field_cases(id) ON DELETE CASCADE,
    url TEXT,
    alt TEXT,
    status TEXT,
    local_path TEXT,
    attachment_id TEXT,
    http_status TEXT,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_field_cases_category ON field_cases(category_key);
CREATE INDEX IF NOT EXISTS idx_field_case_images_case ON field_case_images(case_id);
"""


class FieldCaseImportError(RuntimeError):
    pass


def load_cases(source_dir: Path) -> list[dict[str, Any]]:
    dataset = source_dir / "dataset.jsonl"
    if not dataset.is_file():
        raise FieldCaseImportError(f"缺少 dataset.jsonl：{dataset}")
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(dataset.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FieldCaseImportError(f"第{line_number}行不是合法JSON：{exc}") from exc
        if not isinstance(value, dict):
            raise FieldCaseImportError(f"第{line_number}行不是JSON对象")
        cases.append(value)
    if len(cases) != 100:
        raise FieldCaseImportError(f"案例总数应为100，实际为{len(cases)}")
    if [str(case.get("id", "")) for case in cases] != [f"SSQ-{i:03d}" for i in range(1, 101)]:
        raise FieldCaseImportError("案例ID必须为连续的 SSQ-001 ～ SSQ-100")
    if [case.get("number") for case in cases] != list(range(1, 101)):
        raise FieldCaseImportError("案例 number 必须为连续的 1 ～ 100")
    counts: dict[str, int] = {}
    for case in cases:
        key = CATEGORY_KEYS.get(str(case.get("category", "")))
        if key is None:
            raise FieldCaseImportError(f"未知类别：{case.get('category')!r}")
        counts[key] = counts.get(key, 0) + 1
    if counts != EXPECTED_CATEGORIES:
        raise FieldCaseImportError(f"类别数量不符合预期：{counts}")
    return cases


def _case_row(case: dict[str, Any]) -> tuple:
    return (
        str(case["id"]), int(case["number"]), case.get("source_type"), case.get("category"),
        CATEGORY_KEYS[str(case["category"])], case.get("topic"), case.get("title"),
        case.get("original_excerpt"), 1 if case.get("excerpt_is_complete") else 0,
        case.get("summary"), case.get("source_id"), case.get("website"), case.get("source_url"),
        case.get("source_title"), case.get("published_date"), case.get("retrieved_date"),
        case.get("locator"), case.get("reported_outcome"), case.get("adjudication_status"),
        case.get("evidence_status"), case.get("image_status"), case.get("split_group"),
        json.dumps(case, ensure_ascii=False),
    )


def _image_rows(case: dict[str, Any], source_dir: Path, images_dir: Path) -> list[tuple]:
    rows: list[tuple] = []
    for image in case.get("images") or []:
        if not isinstance(image, dict):
            continue
        local_path = None
        relative = image.get("path")
        if isinstance(relative, str) and relative:
            source_file = source_dir / relative
            if source_file.is_file():
                images_dir.mkdir(parents=True, exist_ok=True)
                target = images_dir / source_file.name
                if not target.is_file() or target.stat().st_size != source_file.stat().st_size:
                    shutil.copy2(source_file, target)
                local_path = f"{images_dir.name}/{target.name}"
        rows.append((
            str(case["id"]), image.get("url"), image.get("alt"), image.get("status"),
            local_path, image.get("attachment_id"), image.get("http_status"), image.get("reason"),
        ))
    return rows


def import_cases(source_dir: Path, db_path: Path, images_dir: Path) -> dict[str, Any]:
    """校验后在一个事务里重建案例表；失败整体回滚。"""

    cases = load_cases(source_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        connection.commit()
        with connection:
            connection.execute("DELETE FROM field_case_images")
            connection.execute("DELETE FROM field_cases")
            for case in cases:
                connection.execute(
                    f"INSERT INTO field_cases ({', '.join(CASE_COLUMNS)}) "
                    f"VALUES ({', '.join('?' * len(CASE_COLUMNS))})", _case_row(case))
                for row in _image_rows(case, source_dir, images_dir):
                    connection.execute(
                        f"INSERT INTO field_case_images ({', '.join(IMAGE_COLUMNS)}) "
                        f"VALUES ({', '.join('?' * len(IMAGE_COLUMNS))})", row)
        total = int(connection.execute("SELECT COUNT(*) FROM field_cases").fetchone()[0])
        images = int(connection.execute("SELECT COUNT(*) FROM field_case_images").fetchone()[0])
    finally:
        connection.close()
    return {"total": total, "images": images}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入公开施工现场问题案例库")
    parser.add_argument("source", type=Path, help="源目录（包含 dataset.jsonl 和 images/）")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    args = parser.parse_args(argv)
    db_path = args.db.resolve()
    if db_path.name == "chat-sessions.sqlite3" or "issue-records" in db_path.name:
        print("拒绝写入聊天数据库或正式工单 Store。", file=sys.stderr)
        return 2
    try:
        result = import_cases(args.source.resolve(), db_path, args.images.resolve())
    except FieldCaseImportError as exc:
        print(f"导入失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps({"db": str(db_path), **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
