from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_materials_are_linked_and_keep_manual_gates_visible() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    tasks = (ROOT / "TASKS.md").read_text(encoding="utf-8")
    for filename in (
        "phase6-release-checklist.md", "demo-script.md", "competition-showcase.md", "known-limitations.md",
    ):
        assert (ROOT / "docs" / filename).is_file()
        assert f"docs/{filename}" in readme
    assert "- [x] 完成 README、演示脚本、已知限制和比赛展示材料。" in tasks
    assert "- [ ] 完成 Windows 双机安装测试和浏览器全流程验收。" in tasks
    assert "另一位队员的物理 Windows 电脑尚未执行和签字" in tasks


def test_clean_clone_script_has_bounded_cleanup_and_secret_guards() -> None:
    source = (ROOT / "scripts" / "verify-clean-clone.ps1").read_text(encoding="utf-8")
    for required in (
        "[Parameter(Mandatory = $true)]", "sea-son-clean-clone-", "Refusing to remove",
        'Join-Path $CloneRoot ".env"', 'Join-Path $CloneRoot "uploads"',
        'Join-Path $CloneRoot "scripts\\setup.ps1"', 'Join-Path $CloneRoot "scripts\\verify.ps1"',
        "Remove-Item -LiteralPath $Resolved -Recurse -Force",
    ):
        assert required in source
    assert "--mirror" not in source and "reset --hard" not in source


def test_showcase_forbids_overclaiming_real_or_production_results() -> None:
    showcase = (ROOT / "docs" / "competition-showcase.md").read_text(encoding="utf-8")
    limitations = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "phase6-release-checklist.md").read_text(encoding="utf-8")
    assert "禁止使用的宣传语" in showcase and "真实工地识别准确率100%" in showcase
    assert "不能对外宣称已经完成" in limitations and "真实文字模型的20案例准确率" in limitations
    assert "两台不同物理电脑" in checklist
    assert "阻塞/未通过" in checklist
