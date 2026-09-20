"""Atomic local conversation snapshots; no model-owned business state."""

import sqlite3
from contextlib import closing
from pathlib import Path

from agents.text_assistant import TextError


class ChatStore:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=1)
        connection.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        return connection

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute("SELECT id, body FROM sessions LIMIT 201").fetchall()
                if len(rows) > 200 or any(len(body) > 2_000_000 for _, body in rows):
                    raise ValueError("Conversation store exceeds bounds")
                return dict(rows)
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise TextError("chat_store_error", "聊天历史无法读取，请检查本地数据文件；原数据未覆盖。") from exc

    def save(self, key: str, body: str):
        try:
            if len(body) > 2_000_000:
                raise ValueError("Conversation exceeds bounds")
            with closing(self._connect()) as connection, connection:
                connection.execute("INSERT INTO sessions VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (key, body))
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise TextError("chat_store_error", "回答未能保存，请检查磁盘空间后重试。") from exc

    def delete(self, key: str):
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("DELETE FROM sessions WHERE id = ?", (key,))
        except (OSError, sqlite3.Error) as exc:
            raise TextError("chat_store_error", "聊天未能删除，请检查本地存储后重试。") from exc
