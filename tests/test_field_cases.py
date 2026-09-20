"""100 条公开案例库：导入校验、事务、幂等与只读查询。"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from backend.app.field_cases import FieldCaseError, FieldCaseRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SOURCE = Path(os.getenv(
    "FIELD_CASES_SOURCE",
    r"C:\Users\Administrator\Desktop\海之子杯\sea-son-field-questions-codex100"))
CATEGORY_LABELS = {"safety": "安全", "quality": "质量", "management": "管理", "logistics": "后勤"}
EXPECTED = {"safety": 40, "quality": 43, "management": 12, "logistics": 5}


def load_importer():
    spec = importlib.util.spec_from_file_location(
        "import_field_cases", REPO_ROOT / "scripts" / "import-field-cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_rows():
    rows, index = [], 0
    for key, total in EXPECTED.items():
        for _ in range(total):
            index += 1
            rows.append({"number": index, "id": f"SSQ-{index:03d}", "category": CATEGORY_LABELS[key],
                         "title": f"公开案例{index}", "summary": f"案例{index}摘要", "images": []})
    return rows


def write_source(root: Path, rows) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return root


def test_importer_validates_and_imports_atomically(tmp_path):
    module = load_importer()
    rows = build_rows()
    rows[-1]["images"] = [{"case_id": "SSQ-100", "url": "https://example.com/a.png",
                           "alt": "现场照片", "status": "downloaded", "path": "images/SSQ-100-01.png"}]
    source = write_source(tmp_path / "source", rows)
    (source / "images").mkdir()
    (source / "images" / "SSQ-100-01.png").write_bytes(b"png-bytes")
    db, images = tmp_path / "db" / "field-cases.sqlite3", tmp_path / "db" / "field-case-images"

    result = module.import_cases(source, db, images)
    assert result == {"total": 100, "images": 1}

    repository = FieldCaseRepository(db)
    assert repository.count() == 100
    assert repository.count_by_category() == EXPECTED
    assert repository.get_by_id("SSQ-001")["title"] == "公开案例1"
    assert repository.get_by_id("SSQ-100")["images"][0]["local_path"] == "field-case-images/SSQ-100-01.png"
    assert len(repository.list_by_category("safety")) == 40
    assert len(repository.list_by_category("后勤")) == 5
    assert (images / "SSQ-100-01.png").read_bytes() == b"png-bytes"
    # 幂等：重复运行不会变成 200 条
    assert module.import_cases(source, db, images)["total"] == 100
    assert repository.count() == 100 and repository.count_images() == 1


def test_failed_insert_rolls_back(tmp_path, monkeypatch):
    module = load_importer()
    source = write_source(tmp_path / "source", build_rows())
    db, images = tmp_path / "db" / "field-cases.sqlite3", tmp_path / "db" / "img"
    module.import_cases(source, db, images)
    original, calls = module._case_row, {"count": 0}

    def flaky(case):
        calls["count"] += 1
        if calls["count"] == 50:
            raise RuntimeError("boom")
        return original(case)

    monkeypatch.setattr(module, "_case_row", flaky)
    with pytest.raises(RuntimeError):
        module.import_cases(source, db, images)
    assert FieldCaseRepository(db).count() == 100  # 回滚后仍是上次成功结果


def test_unknown_category_is_rejected_before_writing(tmp_path):
    module = load_importer()
    rows = build_rows()
    rows[0]["category"] = "未知类别"
    source = write_source(tmp_path / "source", rows)
    db = tmp_path / "db" / "field-cases.sqlite3"
    with pytest.raises(module.FieldCaseImportError):
        module.import_cases(source, db, tmp_path / "db" / "img")
    assert not db.exists() or FieldCaseRepository(db).count() == 0


def test_wrong_case_count_is_rejected(tmp_path):
    module = load_importer()
    source = write_source(tmp_path / "source", build_rows()[:99])
    with pytest.raises(module.FieldCaseImportError):
        module.import_cases(source, tmp_path / "db.sqlite3", tmp_path / "img")


def test_repository_rejects_a_missing_database(tmp_path):
    with pytest.raises(FieldCaseError):
        FieldCaseRepository(tmp_path / "missing.sqlite3").count()


@pytest.mark.skipif(not REAL_SOURCE.is_dir(), reason="本地公开案例库源目录不存在")
def test_real_public_dataset(tmp_path):
    module = load_importer()
    db, images = tmp_path / "field-cases.sqlite3", tmp_path / "field-case-images"
    result = module.import_cases(REAL_SOURCE, db, images)
    assert result["total"] == 100
    repository = FieldCaseRepository(db)
    assert repository.count() == 100
    assert repository.count_by_category() == EXPECTED
    assert repository.get_by_id("SSQ-001") is not None
    assert repository.get_by_id("SSQ-100") is not None
    assert [row["id"] for row in repository.list_by_category("safety")][:1] == ["SSQ-001"]
    expected_images = sorted(path.name for path in (REAL_SOURCE / "images").glob("*.png"))
    local = sorted(Path(row["local_path"]).name for row in repository.local_images())
    assert local == expected_images
    assert len(local) == 8
    assert module.import_cases(REAL_SOURCE, db, images)["total"] == 100
