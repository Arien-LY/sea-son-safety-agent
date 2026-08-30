from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workbench_routes_are_distinct_and_root_defaults_to_consultation() -> None:
    router = source("frontend/src/router.ts")
    assert '{ path: "/", redirect: "/consult" }' in router
    for path, name in (
        ("/chat", "chat"),
        ("/consult", "consult"),
        ("/submit", "submit"),
        ("/records", "records"),
    ):
        assert f'path: "{path}"' in router
        assert f'name: "{name}"' in router


def test_sidebar_exposes_new_chat_consult_submit_and_history() -> None:
    shell = source("frontend/src/components/AppShell.vue")
    assert 'to="/chat"' in shell and "新建聊天" in shell
    assert 'to="/consult"' in shell and "新建咨询" in shell
    assert 'to="/submit"' in shell and "提交工单" in shell
    assert 'to="/records"' in shell and "查看全部历史" in shell
    assert "api.listRecords" in shell


def test_plain_chat_cannot_enter_the_proposal_api_path() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    assert 'props.mode === "consult" && latest.value?.can_propose' in panel
    assert "if (!canCreateProposal.value" in panel
    assert "api.proposeText" in panel
    assert "一般问答，不会在此模式生成或提交工单" in panel


def test_text_composer_uses_compact_consent_and_bounded_wait() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    api = source("frontend/src/api.ts")
    assert "允许本次外发" in panel
    assert "本次允许将问题、背景标签及同一会话" not in panel
    assert "最多约 35 秒" in panel
    assert "35_000" in api and "AbortController" in api


def test_direct_submission_keeps_preview_confirm_and_save_steps() -> None:
    home = source("frontend/src/views/HomeView.vue")
    assert "生成待确认提案" in home
    assert "confirmIssueProposal" in home
    assert "HMAC 完整性凭据已生成" in home
    assert "createIssueRecord" in home
    assert "保存为正式草稿" in home


def test_frozen_contract_names_required_browser_scenarios() -> None:
    contract = source("docs/conversation-workbench-contract.md")
    for scenario in ("W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08", "W09", "W10"):
        assert scenario in contract
    assert "真实文字与图片模型调用为 0" in contract
