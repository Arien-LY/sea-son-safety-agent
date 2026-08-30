"""Bounded image normalization and atomic local photo index (never raw originals)."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, RLock
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.photo_models import PhotoDocument, PhotoMetadata

MAX_PHOTO_BYTES = 5 * 1024 * 1024
_LOCKS: dict[str, RLock] = {}
_GUARD = Lock()


class PhotoError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def normalize_photo(raw: bytes, media_type: str) -> tuple[bytes, int, int]:
    if media_type not in {"image/jpeg", "image/png"}:
        raise PhotoError("unsupported_image_type", "只允许单张JPEG或PNG图片。")
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise PhotoError("image_size_limit", "图片不能为空，且不得超过5MiB。", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                expected = {"image/jpeg": "JPEG", "image/png": "PNG"}[media_type]
                if source.format != expected or getattr(source, "n_frames", 1) != 1:
                    raise PhotoError("invalid_image", "实际图片格式不匹配或包含多帧。")
                if max(source.size) > 4096 or source.width * source.height > 16_000_000:
                    raise PhotoError("image_dimensions_limit", "图片每边不得超过4096像素，总计不得超过1600万像素。", 413)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                rgba = oriented.convert("RGBA")
                clean = Image.new("RGB", rgba.size, "white")
                clean.paste(rgba, mask=rgba.getchannel("A"))
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=90)
                normalized = output.getvalue()
                if len(normalized) > MAX_PHOTO_BYTES:
                    raise PhotoError("image_size_limit", "标准化后图片超过5MiB。", 413)
                return normalized, clean.width, clean.height
    except PhotoError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise PhotoError("invalid_image", "图片无法安全解码，请重新选择。") from exc


class PhotoStore:
    def __init__(self, root: Path, *, replace: Callable = os.replace) -> None:
        self.root = root.resolve()
        self.index_path = self.root / "index.json"
        self._replace = replace
        with _GUARD:
            self._lock = _LOCKS.setdefault(str(self.root).casefold(), RLock())

    def _path(self, photo_id: str) -> Path:
        # Validate before joining any user-supplied identifier to a filesystem path.
        import re
        if not re.fullmatch(r"PHOTO-[A-F0-9]{24}", photo_id):
            raise PhotoError("photo_not_found", "图片不存在。", 404)
        path = self.root / f"{photo_id}.jpg"
        if path.resolve().parent != self.root or path.is_symlink():
            raise PhotoError("photo_storage_error", "图片存储路径无效。", 500)
        return path

    def _load(self) -> PhotoDocument:
        if not self.index_path.exists():
            return PhotoDocument()
        try:
            if self.index_path.is_symlink() or self.index_path.resolve().parent != self.root:
                raise ValueError("Unexpected index path")
            with self.index_path.open("rb") as stream:
                raw = stream.read(25_000_001)
            if len(raw) > 25_000_000:
                raise ValueError("Index too large")
            return PhotoDocument.model_validate_json(raw, strict=True)
        except (OSError, ValueError) as exc:
            raise PhotoError("photo_storage_error", "图片索引无法读取或校验。", 500) from exc

    def _write(self, document: PhotoDocument) -> None:
        temporary_path = None
        try:
            validated = PhotoDocument.model_validate_json(document.model_dump_json(), strict=True)
            serialized = validated.model_dump_json(indent=2)
            if len(serialized.encode("utf-8")) > 25_000_000:
                raise ValueError("Photo index capacity exceeded")
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                             prefix=".photo-index-", suffix=".tmp", delete=False) as stream:
                temporary_path = Path(stream.name)
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            self._replace(str(temporary_path), str(self.index_path))
        except (OSError, ValueError) as exc:
            raise PhotoError("photo_storage_error", "图片索引无法安全保存。", 500) from exc
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    def mutate(self, action: Callable[[PhotoDocument], object]) -> object:
        with self._lock:
            document = self._load()
            result = action(document)
            self._write(document)
            return result

    def snapshot(self) -> PhotoDocument:
        with self._lock:
            return self._load()

    def upload(self, raw: bytes, media_type: str) -> PhotoMetadata:
        jpeg, width, height = normalize_photo(raw, media_type)
        photo = PhotoMetadata(
            photo_id="PHOTO-" + uuid4().hex[:24].upper(),
            content_digest="sha256:" + hashlib.sha256(jpeg).hexdigest(),
            byte_size=len(jpeg), width=width, height=height, created_at=datetime.now(UTC),
        )
        with self._lock:
            document = self._load()
            if len(document.photos) >= 200:
                raise PhotoError("photo_capacity_limit", "本地演示图片容量已满。", 409)
            self.root.mkdir(parents=True, exist_ok=True)
            path = self._path(photo.photo_id)
            created = False
            try:
                with path.open("xb") as stream:
                    created = True
                    stream.write(jpeg)
                    stream.flush()
                    os.fsync(stream.fileno())
                document.photos[photo.photo_id] = photo
                self._write(document)
            except (OSError, PhotoError) as exc:
                if created:
                    path.unlink(missing_ok=True)
                if isinstance(exc, PhotoError):
                    raise
                raise PhotoError("photo_storage_error", "图片无法保存。", 500) from exc
        return photo

    def read(self, photo_id: str) -> tuple[PhotoMetadata, bytes]:
        path = self._path(photo_id)
        with self._lock:
            photo = self._load().photos.get(photo_id)
            if photo is None:
                raise PhotoError("photo_not_found", "图片不存在。", 404)
            try:
                with path.open("rb") as stream:
                    jpeg = stream.read(MAX_PHOTO_BYTES + 1)
                if len(jpeg) != photo.byte_size or "sha256:" + hashlib.sha256(jpeg).hexdigest() != photo.content_digest:
                    raise ValueError("Image digest mismatch")
            except (OSError, ValueError) as exc:
                raise PhotoError("photo_storage_error", "图片完整性校验失败。", 500) from exc
            return photo, jpeg
