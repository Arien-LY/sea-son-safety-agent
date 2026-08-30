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


def test_text_composer_optimistically_moves_message_and_has_no_confirmation_modal() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    api = source("frontend/src/api.ts")
    assert "允许本次外发" not in panel
    assert "本次允许将问题、背景标签及同一会话" not in panel
    assert 'aria-label="选择模型"' in panel
    assert "confirmExternal" not in panel and "确认并发送" not in panel
    send_body = panel[panel.index("async function send"):panel.index("function onComposerKeydown")]
    assert "pendingMessage.value = input.message" in send_body
    assert send_body.index('form.message = ""') < send_body.index("await api.sendText")
    assert "api.sendText(pending, requestController.signal, receiveProgress)" in send_body
    assert 'intent: props.mode' in send_body
    assert "最多约 35 秒" in panel
    assert "35_000" in api and "AbortController" in api


def test_text_analysis_does_not_block_route_navigation() -> None:
    home = source("frontend/src/views/HomeView.vue")
    assert "routeBlocking" in home
    route_guard = home[home.index("const routeBlocking"):home.index("const proposal")]
    assert "textBusy" not in route_guard


def test_sidebar_has_local_demo_login_and_avatar_state() -> None:
    shell = source("frontend/src/components/AppShell.vue")
    assert "登录演示身份" in shell
    assert "user-avatar-shell signed-in" in shell
    assert "sea-son-demo-user" in shell
    assert "不代表真实账号、项目权限或审批资质" in shell


def test_conversation_breaks_out_of_the_form_width_limit() -> None:
    home = source("frontend/src/views/HomeView.vue")
    styles = source("frontend/src/styles.css")
    assert "'conversation-fields': isConversation" in home
    assert ".workspace-fields.conversation-fields { width: 100%; max-width: none; }" in styles
    assert ".conversation-workspace { width: 100%;" in styles


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
