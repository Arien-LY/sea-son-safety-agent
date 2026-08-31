from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest

from desktop.build_release import archive_tree, extract_checked, source_files, validate_customer_tree
from desktop.server import create_desktop_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def desktop_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MODE", "mock")
    monkeypatch.setenv("ISSUE_STORE_PATH", str(tmp_path / "data/records.json"))
    monkeypatch.setenv("PHOTO_STORE_PATH", str(tmp_path / "uploads"))
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>海之子</html>", encoding="utf-8")
    (web / "assets/app.js").write_text("window.test=true", encoding="utf-8")
    (web / ".env").write_text("SYNTHETIC_SECRET=not-public", encoding="utf-8")
    with TestClient(create_desktop_app(web), base_url="http://127.0.0.1") as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/chat", "/consult", "/submit", "/records", "/records/ISS-012345ABCDEF"])
def test_customer_spa_routes(desktop_client, path):
    response = desktop_client.get(path)
    assert response.status_code == 200 and "海之子" in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/.env", "/docs", "/redoc", "/openapi.json", "/api/missing", "/data/records.json", "/assets/%2e%2e/.env", "/assets/not-found.js", "/desktop/server.py"])
def test_customer_service_never_exposes_private_files_or_api_docs(desktop_client, path):
    response = desktop_client.get(path)
    assert response.status_code == 404 and "SYNTHETIC_SECRET" not in response.text


def test_customer_assets_and_metadata(desktop_client):
    assert desktop_client.get("/assets/app.js").text == "window.test=true"
    assert desktop_client.get("/api/runtime").json() == {"agent_mode": "mock"}
    assert desktop_client.get("/health").json() == {"status": "ok"}
    assert desktop_client.get("/api/issue-records").json()["total"] == 0
    assert desktop_client.get("/chat", headers={"Host": "attacker.example"}).status_code == 400
    assert desktop_client.get("/chat", headers={"Origin": "https://attacker.example"}).status_code == 403


def test_allowlist_does_not_copy_secrets_runtime_or_developer_files(tmp_path):
    for filename in ("agents/module.py", "backend/app/main.py", "desktop/__init__.py", "desktop/server.py", "knowledge/catalog.v1.json", ".env", "data/records.json", "uploads/private.jpg", "docs/tutorial.md"):
        file = tmp_path / filename
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("synthetic", encoding="utf-8")
    included = [p.relative_to(tmp_path).as_posix() for p in source_files(tmp_path)]
    assert included == ["agents/module.py", "backend/app/main.py", "desktop/__init__.py", "desktop/server.py", "knowledge/catalog.v1.json"]


def test_archive_rejects_escape_and_is_repeatable(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../escape.txt", "no")
    with pytest.raises(ValueError, match="escapes"):
        extract_checked(bad, tmp_path / "target")
    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.txt").write_text("你好", encoding="utf-8")
    archive_tree(source, tmp_path / "first.zip")
    archive_tree(source, tmp_path / "second.zip")
    assert (tmp_path / "first.zip").read_bytes() == (tmp_path / "second.zip").read_bytes()


def test_customer_package_rejects_unknown_root_entries(tmp_path):
    (tmp_path / "AGENTS.md").touch()
    with pytest.raises(ValueError, match="Unexpected"):
        validate_customer_tree(tmp_path)


def test_customer_notices_are_internal_and_required(tmp_path):
    for name in ("海之子.exe", "使用说明.txt"):
        (tmp_path / name).touch()
    for name in ("agents", "backend", "desktop", "knowledge", "web"):
        (tmp_path / "_internal/app" / name).mkdir(parents=True)
    with pytest.raises(ValueError, match="Missing internal"):
        validate_customer_tree(tmp_path)
    notices = tmp_path / "_internal/licenses/第三方许可.txt"
    notices.parent.mkdir()
    notices.write_text("synthetic notices", encoding="utf-8")
    validate_customer_tree(tmp_path)
    (tmp_path / "第三方许可.txt").touch()
    with pytest.raises(ValueError, match="Unexpected"):
        validate_customer_tree(tmp_path)


def test_customer_templates_have_no_developer_labels():
    for file in (ROOT / "frontend/src").rglob("*.vue"):
        text = file.read_text(encoding="utf-8")
        template = text.split("<template>", 1)[-1]
        for forbidden in ("Phase ", "Hello-Agents", "HMAC", "revision", "propose_issue_record", "Mock", "tutorial_baseline", "framework_version"):
            assert forbidden not in template, (file.name, forbidden)
    guide = (ROOT / "desktop/USER-GUIDE.txt").read_text(encoding="utf-8")
    assert "密钥" in guide and "高风险" in guide and "内部非商业试用" in guide
    assert "教程" not in guide and "pytest" not in guide


def test_launcher_keeps_credentials_off_cli_and_supports_local_user_encryption():
    text = (ROOT / "desktop/Launcher.cs").read_text(encoding="utf-8")
    assert "DataProtectionScope.CurrentUser" in text
    assert "UseSystemPasswordChar = true" in text
    assert "IPAddress.Loopback" in text
    assert 'info.EnvironmentVariables["LLM_API_KEY"]' in text
    argument_line = next(line for line in text.splitlines() if "info.Arguments =" in line)
    assert "Key" not in argument_line
