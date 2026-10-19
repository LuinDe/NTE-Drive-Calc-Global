# 설정 페이지의 "소프트웨어 업데이트" 카드와 "관련 링크" 카드 (NTE Drive Calc Global)
"""Settings cards of the Global updater (design_final §10.3; review r5 L1 / L2 / L9 / L11 / I1 / F6, regression 4).

``build_global_update_card`` shows the Global version, the upstream base (information only), one state line that
mirrors the controller's projection, [업데이트 확인] [릴리스 페이지 열기 ↗] plus the contextual actions, the
auto-check switch, the update channel and how releases are verified (signing key fingerprint, silent installer with
administrator rights).  ``build_about_card`` holds the Global repository / issues links on one row and the original
project's attribution links on a second row (the page never needs to scroll sideways).
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton

from src.app.global_release import GLOBAL_VERSION, RELEASE_SIGNING_KEYS, UPSTREAM_BASE, signing_key_fingerprint
from src.app.theme import themed_style
from src.features.home.global_update_banner import PRIMARY_BUTTON_STYLE
from src.features.settings.global_update_texts import (
    error_sentence, kind_sentence, launch_sentence, local_time_text, manual_install_sentence, needs_redownload,
    ratelimit_active, tooltip_text,
)


def state_line(state) -> str:
    """The one sentence of the card for a projection (pure; shared with the tests)."""
    phase = state.phase
    checked = local_time_text(state.last_check_utc)
    version = state.version_text or state.tag[1:]
    if phase == "checking":
        return _L('正在检查 Global 更新…')
    if phase == "available":
        if state.error_code:
            return _LF('发现新版本 {0} · 检查更新失败：{1}').format(
                (version), (kind_sentence(state.error_code, state.error_detail, state.retry_after_utc)
                            if state.error_code.startswith("check.") else error_sentence(state.error_code)))
        return _LF('发现新版本 {0} · 上次检查：{1}').format((version), (checked))
    if phase == "manual_required":
        return manual_install_sentence(state.manual_min)
    if phase == "skipped":
        return _LF('已跳过版本 {0}').format((version))
    if phase == "downloading":
        return _LF('正在下载更新… {0}%').format((state.progress))
    if phase == "verifying":
        return _L('正在校验下载文件（SHA-256）…')
    if phase == "ready":
        return _LF('更新 {0} 已准备好安装。').format((version))
    if phase == "installing":
        return _L('正在关闭程序并启动安装程序…')
    if phase == "download_failed":
        return error_sentence(state.error_code, state.error_detail, state.retry_after_utc)
    if phase == "updated":
        return _LF('已更新到 Global {0}。').format((version))
    if phase == "launch_failed":
        return launch_sentence(state.error_code)
    if phase == "not_completed":
        return _LF('更新未完成（当前仍是 {0}）。').format((GLOBAL_VERSION))
    if phase == "check_failed":
        if state.error_code == "check.ratelimit":
            return kind_sentence(state.error_code, state.error_detail, state.retry_after_utc)
        reason = kind_sentence(state.error_code, state.error_detail)
        if checked:
            return _LF('检查更新失败（{0}）· 上次检查：{1}').format((reason), (checked))
        return _LF('检查更新失败（{0}）').format((reason))
    if phase == "up_to_date":
        if state.unusable_tag:
            # review r5 L9: a newer release exists but did not pass the in-app checks (it is not offered here)
            return _LF('已发现 Global {0}，但它未通过程序内校验，因此不会在此提供 · 上次检查：{1}').format(
                (state.unusable_tag[1:]), (checked))
        return _LF('已是最新版本 · 上次检查：{0}').format((checked))
    if not state.auto_check and checked:
        return _LF('自动检查已关闭 · 上次检查：{0}').format((checked))
    if checked:
        return _LF('已是最新版本 · 上次检查：{0}').format((checked))
    return _L('尚未检查更新')


def signing_line() -> str:
    """How releases are verified (review r5 I1).  No pinned key: in-app updates cannot install anything."""
    fingerprints = [signing_key_fingerprint(line) for _key_id, line in RELEASE_SIGNING_KEYS]
    fingerprints = [value for value in fingerprints if value]
    if not fingerprints:
        return _L('此版本未内置发布签名公钥，无法在程序内安装更新。')
    return _LF('发布由维护者的签名密钥验证（{0}）；安装程序会以管理员权限静默运行。').format((", ".join(fingerprints)))


def build_global_update_card(window, controller):
    card = window._card(_L('软件更新'))
    card.setObjectName("card")
    window._global_update_card = card
    version_label = QLabel(_LF('NTE Drive Calc Global {0}').format((GLOBAL_VERSION)))
    version_label.setObjectName("gupVersionLabel")
    version_label.setTextFormat(Qt.PlainText)
    version_label.setStyleSheet(themed_style("font-weight:700;font-size:14px"))
    card.layout().addWidget(version_label)
    base_label = QLabel(_LF('基于原版 NTE Drive Calc {0}').format((UPSTREAM_BASE)))
    base_label.setObjectName("gupBaseLabel")
    base_label.setTextFormat(Qt.PlainText)
    base_label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
    card.layout().addWidget(base_label)
    line = QLabel()
    line.setObjectName("gupStateLine")
    line.setWordWrap(True)
    line.setTextFormat(Qt.PlainText)
    card.layout().addWidget(line)
    window._update_status = line

    row = QHBoxLayout()
    row.setSpacing(10)
    check_button = QPushButton(_L('检查更新'))
    check_button.setObjectName("gupCheckButton")
    check_button.clicked.connect(lambda: controller.check(manual=True))
    window._check_update_btn = check_button
    row.addWidget(check_button)
    primary = QPushButton()
    primary.setObjectName("gupPrimaryButton")
    row.addWidget(primary)
    secondary = QPushButton()
    secondary.setObjectName("gupSecondaryButton")
    row.addWidget(secondary)
    tertiary = QPushButton()
    tertiary.setObjectName("gupTertiaryButton")
    row.addWidget(tertiary)
    releases_button = QPushButton(_L('打开发布页 ↗'))
    releases_button.setObjectName("gupReleasesButton")
    releases_button.clicked.connect(controller.open_releases_page)
    row.addWidget(releases_button)
    row.addStretch()
    card.layout().addLayout(row)
    for button in (primary, secondary, tertiary):
        button.setStyleSheet(themed_style(PRIMARY_BUTTON_STYLE))

    auto_check = QCheckBox(_L('启动时自动检查更新（每天至多一次）'))
    auto_check.setObjectName("gupAutoCheck")
    auto_check.setChecked(controller.state.auto_check)
    auto_check.toggled.connect(controller.set_auto_check)
    card.layout().addWidget(auto_check)
    channel = QLabel(_L('更新渠道：GitHub LuinDe/NTE-Drive-Calc-Global 的 Releases（仅 Global 版，与原项目的更新互不相关）'))
    channel.setObjectName("gupChannelLabel")
    channel.setWordWrap(True)
    channel.setTextFormat(Qt.PlainText)
    channel.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
    card.layout().addWidget(channel)
    signing = QLabel(signing_line())
    signing.setObjectName("gupSigningLabel")
    signing.setWordWrap(True)
    signing.setTextFormat(Qt.PlainText)
    signing.setTextInteractionFlags(Qt.TextSelectableByMouse)
    signing.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
    card.layout().addWidget(signing)

    actions = {"primary": primary, "secondary": secondary, "tertiary": tertiary}
    handlers: dict = {}
    # one re-render timer while the GitHub rate limit holds (re-enables [업데이트 확인] after the reset time)
    limit_timer = QTimer(card)
    limit_timer.setSingleShot(True)
    limit_timer.setInterval(60_000)
    limit_timer.timeout.connect(lambda: render(controller.view))

    def connect(button: QPushButton, label: str, handler, emphasised: bool = False) -> None:
        button.setText(label)
        old = handlers.get(button)
        if old is not None:
            try:
                button.clicked.disconnect(old)
            except RuntimeError:
                pass
        button.clicked.connect(handler)
        handlers[button] = handler
        button.setProperty("class", "btnPrimary" if emphasised else "")
        button.style().unpolish(button)
        button.style().polish(button)
        button.show()

    def render(state) -> None:
        line.setText(state_line(state))
        line.setToolTip(tooltip_text(state.error_detail) if state.error_code else "")
        for button in actions.values():
            button.hide()
        phase = state.phase
        busy = phase in ("checking", "downloading", "verifying", "installing")
        limited = state.error_code == "check.ratelimit" and ratelimit_active(state.retry_after_utc)
        check_button.setEnabled(not busy and not limited)
        if phase in ("available", "download_failed"):
            connect(primary, _L('立即更新'), controller.start_download, True)
            if phase == "available":
                connect(secondary, _L('查看详情'), lambda: controller.show_dialog())
        elif phase == "manual_required":
            connect(secondary, _L('查看详情'), lambda: controller.show_dialog())
        elif phase == "skipped":
            connect(primary, _L('重新显示'), controller.unskip)
        elif phase == "downloading":
            connect(primary, _L('取消'), controller.cancel_download)
            connect(secondary, _L('查看详情'), lambda: controller.show_dialog())
        elif phase == "ready":
            connect(primary, _L('立即安装并重启'), lambda: controller.request_install(relaunch=True), True)
            connect(secondary, _L('查看详情'), lambda: controller.show_dialog())
        elif phase == "updated":
            connect(primary, _L('更新内容'), lambda: controller.show_dialog(read_only=True))
            connect(secondary, _L('关闭'), controller.acknowledge_updated)
        elif phase == "launch_failed":
            if needs_redownload(state.error_code):
                connect(primary, _L('重新下载'), controller.redownload, True)
            else:
                connect(primary, _L('重试'), lambda: controller.request_install(relaunch=True), True)
            connect(tertiary, _L('删除下载内容'), controller.delete_download)
        elif phase == "not_completed":
            connect(primary, _L('重试'), lambda: controller.request_install(relaunch=True), True)
            if (state.extra or {}).get("install_log"):
                connect(secondary, _L('查看安装日志'), controller.open_install_log)
            connect(tertiary, _L('删除下载内容'), controller.delete_download)
        if limited and not limit_timer.isActive():
            limit_timer.start()
        if auto_check.isChecked() != state.auto_check:
            auto_check.blockSignals(True)
            auto_check.setChecked(state.auto_check)
            auto_check.blockSignals(False)

    controller.state_changed.connect(render)
    render(controller.view)
    card.render_update_state = render
    return card


def build_about_card(window):
    card = window._card(_L('关于我们'))
    # row 1: this build (the Global repository); row 2: credit to the original project (regression 4: six buttons
    # on one row made the settings page wider than a 1000 px window in en / ja)
    global_row = QHBoxLayout()
    global_row.setSpacing(10)
    repo_button = QPushButton(_L('Global 仓库'))
    repo_button.setObjectName("aboutGlobalRepo")
    repo_button.clicked.connect(window._open_global_repository)
    issues_button = QPushButton(_L('反馈问题（Global）'))
    issues_button.setObjectName("aboutGlobalIssues")
    issues_button.clicked.connect(window._open_global_issues)
    for button in (repo_button, issues_button):
        global_row.addWidget(button)
    global_row.addStretch()
    card.layout().addLayout(global_row)
    credit_row = QHBoxLayout()
    credit_row.setSpacing(10)
    project_button = QPushButton(_L('原项目（GitHub）'))
    project_button.setObjectName("aboutOriginalProject")
    project_button.clicked.connect(window._open_project_homepage)
    author_bilibili_btn = QPushButton(_L('作者B站'))
    author_bilibili_btn.clicked.connect(window._open_bilibili_homepage)
    support_btn = QPushButton(_L('支持我们'))
    support_btn.clicked.connect(window._open_support_homepage)
    group_chat_btn = QPushButton(_L('加入群聊'))
    group_chat_btn.clicked.connect(window._show_group_chat_notice)
    for button in (project_button, author_bilibili_btn, support_btn, group_chat_btn):
        credit_row.addWidget(button)
    credit_row.addStretch()
    card.layout().addLayout(credit_row)
    return card
