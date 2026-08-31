"""Explicit allowlist packager. Run only on the Windows x64 build host."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_files(root: Path) -> list[Path]:
    files = []
    for folder in ("agents", "backend/app"):
        files.extend(p for p in (root / folder).rglob("*.py") if "__pycache__" not in p.parts)
    files += [root / "desktop/__init__.py", root / "desktop/server.py", root / "knowledge/catalog.v1.json"]
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Refusing source link outside build root")
    return sorted(files)


def extract_checked(archive: Path, destination: Path) -> None:
    base = destination.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for info in zipped.infolist():
            if "\\" in info.filename or not (base / info.filename).resolve().is_relative_to(base):
                raise ValueError("Archive path escapes destination")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive contains symlink")
        zipped.extractall(base)


def validate_customer_tree(root: Path) -> None:
    if {p.name for p in root.iterdir()} != {"海之子.exe", "使用说明.txt", "第三方许可.txt", "_internal"}:
        raise ValueError("Unexpected customer root entry")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing package symlink")
        if path.name in {".env", "settings.json", ".git", "node_modules", "TASKS.md", "AGENTS.md"}:
            raise ValueError("Private or developer file in customer package")
    app = root / "_internal/app"
    if {p.name for p in app.iterdir()} != {"agents", "backend", "desktop", "knowledge", "web"}:
        raise ValueError("Unexpected application directory")
    if (app / "web/.env").exists() or (app / "web/index.html").is_symlink():
        raise ValueError("Invalid customer web output")


def archive_tree(root: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo((Path(root.name) / path.relative_to(root)).as_posix(), (2026, 8, 31, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def build(version: str, *, allow_dirty: bool = False) -> Path:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("Build requires Windows and Python 3.12")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+", version):
        raise ValueError("Only explicitly versioned Beta builds are supported")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).decode().strip()
    if dirty and not allow_dirty:
        raise RuntimeError("Release build requires a clean committed tree")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    base = ROOT / "release-output"
    cache = base / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    embedded = cache / "python-3.12.10-embed-amd64.zip"
    if not embedded.exists():
        urllib.request.urlretrieve(PYTHON_URL, embedded)
    if digest(embedded) != PYTHON_SHA256:
        raise ValueError("Python runtime checksum mismatch")
    # A fresh staging directory is never reused or recursively deleted.
    staging = base / (version + "-" + commit[:7] + "-" + uuid.uuid4().hex[:8])
    bundle = staging / ("SeaSon-" + version)
    internal = bundle / "_internal"
    runtime = internal / "python"
    app = internal / "app"
    runtime.mkdir(parents=True)
    extract_checked(embedded, runtime)
    (runtime / "python312._pth").write_text("python312.zip\n.\nsite-packages\n../app\nimport site\n", encoding="ascii")
    wheel_cache = cache / "wheels"
    wheel_cache.mkdir(exist_ok=True)
    run(sys.executable, "-m", "pip", "download", "--quiet", "--only-binary=:all:", "--index-url", "https://pypi.org/simple",
        "--dest", str(wheel_cache), "-r", str(ROOT / "desktop/requirements.lock"))
    run(sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--find-links", str(wheel_cache),
        "--only-binary=:all:", "--no-compile", "--target", str(runtime / "site-packages"), "-r", str(ROOT / "desktop/requirements.lock"))
    for source in source_files(ROOT):
        target = app / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Vite .env is disabled in customer mode; drop inherited public build variables as well.
    env = {k: v for k, v in os.environ.items() if not k.startswith("VITE_")}
    subprocess.run(["npm.cmd", "run", "build", "--", "--mode", "customer"], cwd=ROOT / "frontend", env=env, check=True)
    web = app / "web"
    web.mkdir()
    for source in (ROOT / "frontend/dist").rglob("*"):
        if source.is_file() and source.suffix in {".html", ".js", ".css"} and not source.is_symlink():
            relative = source.relative_to(ROOT / "frontend/dist")
            if relative.as_posix() != "index.html" and relative.parts[0] != "assets":
                raise ValueError("Unexpected frontend asset")
            target = web / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    run(str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/utf8output",
        "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll", "/reference:System.Security.dll",
        "/reference:System.Web.Extensions.dll", "/out:" + str(bundle / "海之子.exe"), str(ROOT / "desktop/Launcher.cs"))
    shutil.copyfile(ROOT / "desktop/USER-GUIDE.txt", bundle / "使用说明.txt")
    licenses = internal / "licenses"
    licenses.mkdir()
    shutil.copyfile(runtime / "LICENSE.txt", licenses / "CPython.txt")
    notices = ["第三方许可声明\n本版仅供内部非商业试用。hello-agents 的许可含非商业与相同方式共享限制。\n完整许可见本目录的 _internal/licenses 和各组件附带的许可文件。\n"]
    inventory = []
    for distribution in sorted(importlib.metadata.distributions(path=[str(runtime / "site-packages")]), key=lambda d: d.metadata["Name"].lower()):
        name, number = distribution.metadata["Name"], distribution.version
        inventory.append({"name": name, "version": number})
        notices.append(f"\n{name} {number}\n")
        for entry in distribution.files or []:
            if re.match(r"(?i)(license|copying|notice)", Path(str(entry)).name):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = licenses / name / str(entry)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    # Include complete license texts for every frontend runtime package (not dev dependencies).
    frontend_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    for relative, item in frontend_lock["packages"].items():
        if not relative or item.get("dev"):
            continue
        folder = ROOT / "frontend" / relative
        name = relative.rsplit("node_modules/", 1)[-1]
        notices.append(f"\n{name} {item['version']} — {item.get('license', 'see included license')}\n")
        found = False
        for source in folder.iterdir():
            if source.is_file() and re.match(r"(?i)(license|copying|notice)", source.name):
                target = licenses / "frontend" / (name + "-" + item["version"]) / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                found = True
        if not found and name == "@vue/devtools-api" and item["version"] == "6.6.4":
            shutil.copyfile(ROOT / "desktop/licenses/vue-devtools-api-6.6.4.txt", licenses / "vue-devtools-api-6.6.4.txt")
            found = True
        if not found:
            raise ValueError("Missing frontend license: " + name)
    (bundle / "第三方许可.txt").write_text("".join(notices), encoding="utf-8-sig")
    validate_customer_tree(bundle)
    manifest = {"version": version, "source_commit": commit, "dirty_build": bool(dirty),
                "python_sha256": PYTHON_SHA256, "packages": inventory,
                "wheels": {p.name: digest(p) for p in sorted(wheel_cache.glob("*.whl"))},
                "files": {p.relative_to(bundle).as_posix(): digest(p) for p in sorted(bundle.rglob("*")) if p.is_file()}}
    (internal / "build-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    archive = staging / ("SeaSon-" + version + "-windows-x64.zip")
    archive_tree(bundle, archive)
    (staging / "SHA256SUMS.txt").write_text(digest(archive) + "  " + archive.name + "\n", encoding="ascii")
    print("RELEASE_ARTIFACT=" + str(archive), flush=True)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--allow-dirty", action="store_true", help="local rehearsal only; never publish")
    options = parser.parse_args()
    build(options.version, allow_dirty=options.allow_dirty)
