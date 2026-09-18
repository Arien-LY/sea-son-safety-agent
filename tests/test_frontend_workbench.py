from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workbench_uses_one_ai_chat_entry_and_keeps_legacy_consult_redirect() -> None:
    router = source("frontend/src/router.ts")
    assert '{ path: "/", redirect: "/chat" }' in router
    assert '{ path: "/consult", redirect: "/chat" }' in router
    for path, name in (
        ("/chat", "chat"),
        ("/submit", "submit"),
        ("/records", "records"),
    ):
        assert f'path: "{path}"' in router
        assert f'name: "{name}"' in router


def test_sidebar_exposes_unified_chat_submit_and_history() -> None:
    shell = source("frontend/src/components/AppShell.vue")
    assert 'to="/chat"' in shell and "新建聊天" in shell
    assert 'to="/consult"' not in shell and "新建咨询" not in shell
    assert 'to="/submit"' in shell and "提交工单" in shell
    assert 'to="/records"' in shell and "查看全部历史" in shell
    assert "api.listRecords" in shell


def test_unified_chat_routes_eligible_analysis_to_a_human_controlled_ticket_form() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    home = source("frontend/src/views/HomeView.vue")
    assert 'intent: "auto"' in panel
    assert 'emit("ticket", result.reply.analysis)' in panel
    assert "openTicketFromAnalysis" in home
    assert 'router.push({ name: "submit", query: { source: "ai" } })' in home
    assert "createIssueRecord" in home and "确认提案" in home


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
    assert "api.sendText(pending, requestController.signal, receiveProgress, receiveDelta)" in send_body
    assert 'intent: "auto"' in send_body
    assert "最多约 190 秒" in panel
    assert "35_000" in api and "AbortController" in api


def test_text_analysis_does_not_block_route_navigation() -> None:
    home = source("frontend/src/views/HomeView.vue")
    assert "routeBlocking" in home
    route_guard = home[home.index("const routeBlocking"):home.index("const proposal")]
    assert "textBusy" not in route_guard


def test_chat_cancel_is_outside_the_busy_business_fieldset() -> None:
    home = source("frontend/src/views/HomeView.vue")
    assert ':disabled="routeBlocking || loadingRecord"' in home
    business = '<fieldset class="business-fields" :disabled="working || loadingRecord"'
    assert home.index("<TextPanel ") < home.index(business)


def test_sidebar_has_local_demo_login_and_avatar_state() -> None:
    shell = source("frontend/src/components/AppShell.vue")
    assert "设置你的称呼" in shell
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
    assert "信息已确认，尚未保存" in home
    assert "createIssueRecord" in home
    assert "保存为正式草稿" in home


def test_frozen_contract_names_required_browser_scenarios() -> None:
    contract = source("docs/conversation-workbench-contract.md")
    for scenario in ("W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08", "W09", "W10"):
        assert scenario in contract
    assert "真实文字与图片模型调用为 0" in contract


def test_minimal_message_template_has_no_avatars_and_keeps_pending_role() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    assert "message-avatar" not in panel and "message-meta" not in panel
    assert panel.count('class="message-row user-row" aria-label="你的消息"') == 2
    assert 'class="message-row assistant-row" aria-label="助手回复"' in panel
    assert '`用时 ${turn.seconds} 秒`' in panel and "已保存的回复" in panel
    assert "turn.thinking === 'deep'" in panel
    assert 'class="execution-history" open' not in panel
    assert "第 {{ turn.result.turn }} 轮" not in panel
    assert "AI 服务未启用，本次未进行智能分析" in panel
    assert "step.tool" in panel and "activeStepLabel" in panel
    assert 'class="markdown-body" v-html="renderAssistantMarkdown(turn.result.mode' in panel
    assert "streaming-answer" in panel
    assert "preserve-lines" not in panel


def test_model_picker_is_server_described_and_supports_a_custom_model_id() -> None:
    panel = source("frontend/src/components/TextPanel.vue")
    request = source("backend/app/text_models.py")
    assert 'value="__custom__"' in panel
    assert 'aria-label="自定义模型标识"' in panel
    assert "available_models" in panel
    # Text and Mock turns use the picker; only a real image turn switches to the image model.
    assert 'model: hasAttachment.value && runtime.value?.mode === "real" ? runtime.value.image_model || null : selectedModel.value || null' in panel
    assert "AI 服务未启用，图片仅在本机校验和保存" in panel
    assert "model: str | None" in request


def test_minimal_message_styles_align_user_right_without_avatar_gutter() -> None:
    styles = source("frontend/src/styles.css")
    assert ".user-row { justify-content: flex-end; }" in styles
    assert ".assistant-message { width: 100%;" in styles
    assert ".conversation > li" in styles
    assert ".message-avatar" not in styles and ".message-meta" not in styles
    assert ".workspace:has(.conversation-workspace) { background: #fff; }" in styles


def test_readable_chat_contract_keeps_a_shared_axis_and_safe_markdown_styles() -> None:
    styles = source("frontend/src/styles.css")
    markdown = source("frontend/src/markdown.ts")
    contract = source("docs/chat-visual-contract.md")
    assert "width: min(860px, 100%)" in styles
    assert ".conversation-header-inner" in styles
    assert ".assistant-message { width: 100%; color: #202124; font-size: 17px; line-height: 1.78; }" in styles
    assert ".composer { border: 1px solid #d6d8da; border-radius: 22px" in styles
    assert ".markdown-body pre { max-width: 100%" in styles
    assert 'html: false' in markdown
    assert 'SAFE_LINK_PROTOCOL = /^(https?:|mailto:)/i' in markdown
    assert 'markdown.renderer.rules.image' in markdown
    for scenario in ("V01", "V10", "S01", "S06"):
        assert scenario in contract
