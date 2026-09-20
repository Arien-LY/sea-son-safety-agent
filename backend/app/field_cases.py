"""100 条公开施工现场案例库的只读访问层。

这些案例来自公开提问与官方案例，是评估用案例库，不是规范答案、不是正式工单，
也不是专业裁决结果，禁止当作标准答案、自动处理依据或准确率金标准。
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(os.getenv("FIELD_CASES_DB", "data/field-cases.sqlite3"))

CATEGORY_KEYS = {
    "安全": "safety", "质量": "quality", "管理": "management", "后勤": "logistics",
    "safety": "safety", "quality": "quality", "management": "management", "logistics": "logistics",
}


class FieldCaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FieldCaseImage:
    case_id: str
    url: str | None
    alt: str | None
    status: str | None
    local_path: str | None
    attachment_id: str | None
    http_status: str | None
    reason: str | None


class FieldCaseRepository:
    """只读查询：count / get_by_id / list by category，不接入聊天回答。"""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise FieldCaseError(f"案例数据库不存在：{self.path}")
        connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM field_cases").fetchone()[0])

    def get_by_id(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM field_cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                return None
            case = dict(row)
            case["images"] = [dict(image) for image in connection.execute(
                "SELECT * FROM field_case_images WHERE case_id = ? ORDER BY id", (case_id,)).fetchall()]
            return case

    def list_by_category(self, category: str, *, limit: int = 100,
                         offset: int = 0) -> list[dict[str, Any]]:
        key = CATEGORY_KEYS.get(category, category)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM field_cases WHERE category_key = ? ORDER BY number LIMIT ? OFFSET ?",
                (key, min(max(limit, 1), 100), max(offset, 0))).fetchall()
            return [dict(row) for row in rows]

    def count_by_category(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT category_key, COUNT(*) AS total FROM field_cases GROUP BY category_key").fetchall()
            return {row["category_key"]: int(row["total"]) for row in rows}

    def count_images(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM field_case_images").fetchone()[0])

    def local_images(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id, local_path FROM field_case_images "
                "WHERE local_path IS NOT NULL ORDER BY case_id, id").fetchall()
            return [dict(row) for row in rows]
