"""本地 JSON 问题记录 Store，提供进程内并发和原子替换保证。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Lock, RLock
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.workflow_models import IssueRecord


class StoredIdempotencyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: str
    payload_digest: str


class IssueRecordStoreDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["phase3-issue-record-store-v1"] = (
        "phase3-issue-record-store-v1"
    )
    records: dict[str, IssueRecord] = Field(default_factory=dict)
    idempotency_keys: dict[str, StoredIdempotencyEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_store_references(self) -> "IssueRecordStoreDocument":
        if any(key != record.record_id for key, record in self.records.items()):
            raise ValueError("Store 记录键必须与 record_id 一致。")
        if any(
            entry.record_id not in self.records
            for entry in self.idempotency_keys.values()
        ):
            raise ValueError("Store 幂等索引必须指向现有记录。")
        return self


class StoreError(RuntimeError):
    """Store 基础错误。"""


class RecordNotFoundError(StoreError):
    pass


class RevisionConflictError(StoreError):
    pass


class IdempotencyConflictError(StoreError):
    pass


_PATH_LOCKS: dict[str, RLock] = {}
_PATH_LOCKS_GUARD = Lock()
MutationResult = TypeVar("MutationResult")


def _lock_for(path: Path) -> RLock:
    key = str(path.resolve()).casefold()
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, RLock())


class JsonIssueRecordStore:
    """以单个本地 JSON 文件作为问题记录唯一事实来源。"""

    def __init__(
        self,
        path: Path,
        *,
        replace: Callable[[str, str], None] = os.replace,
    ) -> None:
        self.path = path.resolve()
        self._replace = replace
        self._lock = _lock_for(self.path)

    def get(self, record_id: str) -> IssueRecord:
        with self._lock:
            document = self._load()
            record = document.records.get(record_id)
            if record is None:
                raise RecordNotFoundError(record_id)
            return record.model_copy(deep=True)

    def create(
        self,
        record: IssueRecord,
        *,
        idempotency_key: str,
        payload_digest: str,
    ) -> tuple[IssueRecord, bool]:
        def mutation(
            document: IssueRecordStoreDocument,
        ) -> tuple[tuple[IssueRecord, bool], bool]:
            previous = document.idempotency_keys.get(idempotency_key)
            if previous is not None:
                if previous.payload_digest != payload_digest:
                    raise IdempotencyConflictError(idempotency_key)
                return (document.records[previous.record_id].model_copy(deep=True), False), False
            if record.record_id in document.records:
                raise IdempotencyConflictError(record.record_id)
            document.records[record.record_id] = record
            document.idempotency_keys[idempotency_key] = StoredIdempotencyEntry(
                record_id=record.record_id,
                payload_digest=payload_digest,
            )
            return (record.model_copy(deep=True), True), True

        return self._mutate(mutation)

    def update(
        self,
        record_id: str,
        *,
        expected_revision: int,
        transform: Callable[[IssueRecord], IssueRecord],
    ) -> IssueRecord:
        def mutation(
            document: IssueRecordStoreDocument,
        ) -> tuple[IssueRecord, bool]:
            current = document.records.get(record_id)
            if current is None:
                raise RecordNotFoundError(record_id)
            if current.revision != expected_revision:
                raise RevisionConflictError(record_id)
            updated = transform(current.model_copy(deep=True))
            if updated.record_id != current.record_id:
                raise StoreError("记录更新不能改变 record_id。")
            if updated.revision != current.revision + 1:
                raise StoreError("记录更新必须且只能递增一个 revision。")
            document.records[record_id] = updated
            return updated.model_copy(deep=True), True

        return self._mutate(mutation)

    def snapshot(self) -> tuple[IssueRecord, ...]:
        with self._lock:
            document = self._load()
            return tuple(
                document.records[key].model_copy(deep=True)
                for key in sorted(document.records)
            )

    def _load(self) -> IssueRecordStoreDocument:
        if not self.path.exists():
            return IssueRecordStoreDocument(records={}, idempotency_keys={})
        try:
            raw = self.path.read_text(encoding="utf-8")
            return IssueRecordStoreDocument.model_validate_json(raw, strict=True)
        except (OSError, ValueError) as exc:
            raise StoreError("问题记录 Store 无法读取或校验。") from exc

    def _mutate(
        self,
        mutation: Callable[
            [IssueRecordStoreDocument],
            tuple[MutationResult, bool],
        ],
    ) -> MutationResult:
        with self._lock:
            document = self._load()
            result, changed = mutation(document)
            if changed:
                self._atomic_write(document)
            return result

    def _atomic_write(self, document: IssueRecordStoreDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(
                    document.model_dump(mode="json"),
                    temporary,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            self._replace(temporary_path, str(self.path))
        except OSError as exc:
            raise StoreError("问题记录 Store 原子写入失败。") from exc
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)
