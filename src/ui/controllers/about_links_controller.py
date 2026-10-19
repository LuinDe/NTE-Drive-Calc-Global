# 관련 링크 믹스인: 원본 프로젝트 출처 링크(크레딧)와 Global 저장소 링크, https 전용 URL 열기 (NTE Drive Calc Global)
"""About / credit links of the main window (replaces the removed upstream update controller's link methods).

The original project's links (GitHub home page, Bilibili, support, QQ / Discord notice) stay as attribution.  The
Global repository, its issue tracker and its releases page are the only update / download / feedback targets.
``_open_url`` accepts https URLs only and opens them through ``QDesktopServices``; no shell-open or browser-module
call is ever made with a string that came from the network.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from urllib.parse import urlsplit

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.app.constants import (
    BILIBILI_HOME_URL,
    DISCORD_GROUP_URL,
    GITHUB_HOME_URL,
    GROUP_CHAT_DEVELOPER_HINT,
    GROUP_CHAT_DISCORD_HINT,
    QQ_GROUP_NUMBER,
    SUPPORT_US_URL,
)
from src.app.global_release import GLOBAL_ISSUES_URL, GLOBAL_PROJECT_URL, GLOBAL_RELEASES_URL
from src.app.theme import themed_style
from src.app.window_geometry import fit_dialog_to_available_screen
from src.utils.logger import logger


def open_https_url(url: str) -> bool:
    """Opens ``url`` in the default browser when it is an https URL; anything else is logged and ignored."""
    try:
        parts = urlsplit(str(url))
    except ValueError:
        parts = None
    if parts is None or parts.scheme != "https" or not parts.netloc:
        logger.warning(f"about_links: refused to open a non-https url ({str(url)[:60]!r})")
        return False
    return bool(QDesktopServices.openUrl(QUrl(str(url))))


def _open_url(self, url):
    return open_https_url(url)


def _open_bilibili_homepage(self):
    self._open_url(BILIBILI_HOME_URL)


def _open_project_homepage(self):
    """The original project (attribution)."""
    self._open_url(GITHUB_HOME_URL)


def _open_support_homepage(self):
    self._open_url(SUPPORT_US_URL)


def _open_discord_group(self):
    self._open_url(DISCORD_GROUP_URL)


def _open_global_repository(self):
    self._open_url(GLOBAL_PROJECT_URL)


def _open_global_issues(self):
    self._open_url(GLOBAL_ISSUES_URL)


def _open_global_releases(self):
    self._open_url(GLOBAL_RELEASES_URL)


def _show_group_chat_notice(self):
    dialog = QDialog(self)
    dialog.setWindowTitle(_L('加入群聊'))
    dialog.setMinimumSize(410, 245)
    if hasattr(self, "_current_style_sheet"):
        dialog.setStyleSheet(self._current_style_sheet())
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(11)
    intro = QLabel(_L('遇到问题，或想交流计算器的使用体验？'))
    intro.setWordWrap(True)
    intro.setStyleSheet(themed_style("color:#8b949e"))
    layout.addWidget(intro)

    def add_option(title: str, detail: str, action: QPushButton, number: str = ""):
        card = QFrame()
        card.setObjectName("groupChatOption")
        card.setStyleSheet(themed_style(
            "QFrame#groupChatOption{background:#161b22;border:1px solid #30363d;border-radius:8px}"
        ))
        row = QHBoxLayout(card)
        row.setContentsMargins(15, 12, 15, 12)
        row.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(5)
        title_label = QLabel(title)
        title_label.setStyleSheet(themed_style("font-size:14px;font-weight:600;color:#f0f6fc"))
        text.addWidget(title_label)
        if number:
            number_label = QLabel(number)
            number_label.setObjectName("groupChatNumber")
            number_label.setStyleSheet(themed_style("font-size:18px;font-weight:600;color:#58a6ff"))
            text.addWidget(number_label)
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(themed_style("color:#8b949e"))
        text.addWidget(detail_label)
        row.addLayout(text, 1)
        row.addWidget(action, 0, Qt.AlignVCenter)
        layout.addWidget(card)

    copy_button = QPushButton(_L('复制群号'))

    def copy_group_number():
        QApplication.clipboard().setText(QQ_GROUP_NUMBER)
        copy_button.setText(_L('已复制'))

    copy_button.clicked.connect(copy_group_number)
    add_option(_L('QQ 交流群'), GROUP_CHAT_DEVELOPER_HINT, copy_button, QQ_GROUP_NUMBER)

    discord_button = QPushButton(_L('加入 Discord'))
    discord_button.setObjectName("btnNew")

    def open_discord_group():
        self._open_discord_group()
        dialog.accept()

    discord_button.clicked.connect(open_discord_group)
    add_option(_L('Discord 群组'), GROUP_CHAT_DISCORD_HINT, discord_button)
    fit_dialog_to_available_screen(dialog, QSize(490, 285))
    dialog.exec()
    return dialog


class AboutLinksMixin:
    _open_url = _open_url
    _open_bilibili_homepage = _open_bilibili_homepage
    _open_project_homepage = _open_project_homepage
    _open_support_homepage = _open_support_homepage
    _open_discord_group = _open_discord_group
    _open_global_repository = _open_global_repository
    _open_global_issues = _open_global_issues
    _open_global_releases = _open_global_releases
    _show_group_chat_notice = _show_group_chat_notice
