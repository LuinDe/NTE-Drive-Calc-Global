# 첫 화면의 Global 업데이트 배너: 비차단 한 줄 안내 + 상태별 버튼 (NTE Drive Calc Global 추가 모듈)
"""Home-page update banner of the Global updater (design_final §10.3; review r5 M1 / M8 / L2 / L11 / F6).

One sentence plus the buttons of the phase; never grabs focus; the glyph and the sentence carry the state so colour
is never the only signal.  ``banner_texts`` is pure (shared with the offscreen tests): it returns ``None`` when the
banner must be hidden, else ``(tone, sentence, [(object name, label, action name)])``.  The first button of a phase
is its primary action (emphasised); a ✕ hides the banner for this session.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.app.global_release import GLOBAL_VERSION
from src.app.theme import themed_style
from src.features.settings.global_update_texts import (
    error_sentence, kind_sentence, launch_sentence, needs_redownload, tooltip_text,
)

_STYLE_BY_TONE = {
    "info": "QFrame#homeUpdateBanner{background:#10243f;border:1px solid #1f6feb;border-radius:8px}",
    "ok": "QFrame#homeUpdateBanner{background:#0f2a1a;border:1px solid #2ea043;border-radius:8px}",
    "warn": "QFrame#homeUpdateBanner{background:#2a2112;border:1px solid #d29922;border-radius:8px}",
}
_GLYPH_BY_TONE = {"info": ("⬆", "#58a6ff"), "ok": ("✓", "#3fb950"), "warn": ("⚠", "#d29922")}
PRIMARY_BUTTON_STYLE = ("QPushButton[class=\"btnPrimary\"]{background:#238636;color:#ffffff;border:1px solid #2ea043;"
                        "font-weight:600}"
                        "QPushButton[class=\"btnPrimary\"]:hover{background:#2ea043}"
                        "QPushButton[class=\"btnPrimary\"]:disabled{background:#1b3a24;color:#6e7681}")
PRIMARY_ACTIONS = ("start_download", "request_install", "redownload")
_DISMISS = ("homeUpdateDismiss", "✕", "later")


def banner_texts(state):
    """``None`` (hidden) or ``(tone, sentence, buttons)``; ``buttons`` = ``[(object name, label, action)]``."""
    phase = state.phase
    version = state.version_text or state.tag[1:]
    extra = state.extra or {}
    hidden = bool(extra.get("banner_hidden"))
    if phase == "checking" and state.tag:
        # [업데이트] / [자세히 보기] on a remembered release re-validates it first (review r5 M1)
        return ("info", _L('正在检查 Global 更新…'), [])
    if phase == "available" and not hidden:
        if state.error_code and not extra.get("quiet_error"):
            sentence = _LF('有新版本 Global {0} 可用（{1}）。').format(
                (version), (error_sentence(state.error_code, state.error_detail, state.retry_after_utc)))
        else:
            sentence = _LF('有新版本 Global {0} 可用。').format((version))
        return ("info", sentence,
                [("homeUpdateDetails", _L('查看详情'), "show_dialog"), ("homeUpdateNow", _L('立即更新'), "start_download"),
                 _DISMISS])
    if phase == "manual_required" and not hidden:
        return ("info", _LF('有新版本 Global {0}，需要从发布页手动安装。').format((version)),
                [("homeUpdateDetails", _L('查看详情'), "show_dialog"),
                 ("homeUpdateReleases", _L('打开发布页 ↗'), "open_releases_page"), _DISMISS])
    if phase == "downloading":
        return ("info", _LF('正在下载更新… {0}%').format((state.progress)),
                [("homeUpdateCancel", _L('取消'), "cancel_download"), ("homeUpdateDetails", _L('查看详情'), "show_dialog")])
    if phase == "verifying":
        return ("info", _L('正在校验下载文件（SHA-256）…'), [("homeUpdateDetails", _L('查看详情'), "show_dialog")])
    if phase == "ready":
        return ("info", _LF('更新 {0} 已准备好安装。').format((version)),
                [("homeUpdateInstall", _L('立即安装并重启'), "request_install"),
                 ("homeUpdateDetails", _L('查看详情'), "show_dialog")])
    if phase == "installing":
        return ("info", _L('正在关闭程序并启动安装程序…'), [])
    if phase == "updated":
        return ("ok", _LF('已更新到 Global {0}。').format((version)),
                [("homeUpdateNotes", _L('更新内容'), "show_notes"), ("homeUpdateDismiss", _L('关闭'), "acknowledge_updated")])
    if phase == "launch_failed" and not hidden:
        first = (("homeUpdateRedownload", _L('重新下载'), "redownload") if needs_redownload(state.error_code)
                 else ("homeUpdateRetry", _L('重试'), "request_install"))
        return ("warn", launch_sentence(state.error_code),
                [first, ("homeUpdateDelete", _L('删除下载内容'), "delete_download"), _DISMISS])
    if phase == "not_completed" and not hidden:
        buttons = [("homeUpdateRetry", _L('重试'), "request_install")]
        if extra.get("install_log"):
            buttons.append(("homeUpdateLog", _L('查看安装日志'), "open_install_log"))
        buttons += [("homeUpdateDelete", _L('删除下载内容'), "delete_download"), _DISMISS]
        return ("warn", _LF('更新未完成（当前仍是 {0}）。').format((GLOBAL_VERSION)), buttons)
    if phase == "download_failed" and not hidden:
        return ("warn", error_sentence(state.error_code, state.error_detail, state.retry_after_utc),
                [("homeUpdateRetry", _L('重试'), "start_download"), ("homeUpdateReleases", _L('打开发布页 ↗'), "open_releases_page"),
                 _DISMISS])
    return None


def _action(controller, name: str):
    if name == "show_dialog":
        return lambda: controller.show_dialog()
    if name == "show_notes":
        return lambda: controller.show_dialog(read_only=True)
    if name == "request_install":
        return lambda: controller.request_install(relaunch=True)
    return getattr(controller, name)


def build_home_update_banner(parent, controller) -> QFrame:
    banner = QFrame(parent)
    banner.setObjectName("homeUpdateBanner")
    row = QHBoxLayout(banner)
    row.setContentsMargins(16, 12, 16, 12)
    row.setSpacing(10)
    glyph = QLabel("⬆", banner)
    glyph.setObjectName("homeUpdateGlyph")
    glyph.setTextFormat(Qt.PlainText)
    row.addWidget(glyph)
    sentence = QLabel("", banner)
    sentence.setObjectName("homeUpdateSentence")
    sentence.setWordWrap(True)
    sentence.setTextFormat(Qt.PlainText)
    sentence.setTextInteractionFlags(Qt.TextSelectableByMouse)
    row.addWidget(sentence, 1)
    buttons: list[QPushButton] = []
    handlers: dict = {}
    for _ in range(4):
        button = QPushButton("", banner)
        button.setFocusPolicy(Qt.StrongFocus)
        button.hide()
        row.addWidget(button)
        buttons.append(button)
    banner.hide()

    def render(state) -> None:
        texts = banner_texts(state)
        for button in buttons:
            button.hide()
        if texts is None:
            banner.hide()
            return
        tone, text, specs = texts
        banner.setStyleSheet(themed_style(_STYLE_BY_TONE[tone] + PRIMARY_BUTTON_STYLE))
        mark, colour = _GLYPH_BY_TONE[tone]
        glyph.setText(mark)
        glyph.setStyleSheet(themed_style(f"font-size:16px;font-weight:700;color:{colour}"))
        sentence.setText(text)
        sentence.setToolTip(tooltip_text(state.error_code if state.error_code else ""))
        for button, (object_name, label, action) in zip(buttons, specs):
            button.setObjectName(object_name)
            button.setText(label)
            button.setAccessibleName(label if label != "✕" else _L('关闭'))
            button.setProperty("class", "btnPrimary" if action in PRIMARY_ACTIONS else "")
            button.style().unpolish(button)
            button.style().polish(button)
            old = handlers.get(button)
            if old is not None:
                try:
                    button.clicked.disconnect(old)
                except RuntimeError:
                    pass
            handler = _action(controller, action)
            button.clicked.connect(handler)
            handlers[button] = handler
            button.show()
        banner.show()

    controller.state_changed.connect(render)
    render(controller.view)
    banner.render_update_state = render
    return banner


__all__ = ["banner_texts", "build_home_update_banner", "PRIMARY_BUTTON_STYLE", "kind_sentence"]
