# Global 업데이트 대화상자: 릴리스 노트 → 다운로드 진행 → 설치 준비 → 오류 (한 창, 네 페이지; 읽기 전용 "변경 사항" 모드)
"""The one window-modal update dialog (design_final §8.3–§8.4, §10.3; review r5 F2 / F3 / F6 / M3 / M5 / M9 / L2 /
L3 / L7 / L11).

Pages: notes (new version + release notes in the user's language), progress (background download, hideable),
ready (explicit install step), error (inline failure text with the fitting next step).  ``read_only`` shows the
notes of the version that was just installed.  Enter = the primary action, Esc / title-bar close = 나중에; "이 버전
건너뛰기" is never the default button.  The notes view never loads a resource (no image of any kind) and opens only
links into the Global repository.  Every label that can show text from a file, the network or an exception is plain
text.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedLayout,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.app.global_release import GLOBAL_VERSION
from src.app.theme import theme_color, themed_style
from src.app.window_geometry import fit_dialog_to_available_screen
from src.features.home.global_update_banner import PRIMARY_BUTTON_STYLE
from src.features.settings.global_update_texts import (
    duration_text, error_sentence, github_anchor_allowed, launch_sentence, local_time_text, manual_install_sentence,
    mb_text, needs_redownload, tooltip_text,
)
from src.ui.controllers.about_links_controller import open_https_url

NOTES_FEATURES = QTextDocument.MarkdownFeatures(
    QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML)


class NotesBrowser(QTextBrowser):
    """Release notes view that never loads a resource: no local file, no network share, no ``data:`` image (review
    r5 F2).  Links are reported through ``anchorClicked`` and never followed by the widget itself."""

    def loadResource(self, kind, url):  # noqa: N802 - Qt override
        return None

    def set_notes(self, markdown: str) -> None:
        self.document().setMarkdown(markdown, NOTES_FEATURES)
        _colour_links(self.document(), theme_color("#58a6ff"))


def _colour_links(document: QTextDocument, colour: str) -> None:
    """The Markdown importer takes the link colour from the application palette (dark blue on the dark themes);
    recolour every anchor of the notes document (review r5 M5)."""
    ranges = []
    block = document.begin()
    while block.isValid():
        for item in block.textFormats():
            if item.format.isAnchor():
                ranges.append((block.position() + item.start, item.length))
        block = block.next()
    if not ranges:
        return
    link = QTextCharFormat()
    link.setForeground(QColor(colour))
    link.setFontUnderline(True)
    cursor = QTextCursor(document)
    for start, length in ranges:
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(link)


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.PlainText)
    return label


class GlobalUpdateDialog(QDialog):
    PAGE_NOTES, PAGE_PROGRESS, PAGE_READY, PAGE_ERROR = range(4)

    def __init__(self, window, controller, *, read_only: bool = False) -> None:
        super().__init__(window)
        self.controller = controller
        self._read_only = read_only
        self._closing_by_code = False
        self.setObjectName("globalUpdateDialog")
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumSize(620, 480)
        base = window._current_style_sheet() if hasattr(window, "_current_style_sheet") else ""
        self.setStyleSheet((base or "") + themed_style(PRIMARY_BUTTON_STYLE))
        self._build()
        controller.state_changed.connect(self.render)
        self.render(controller.view)
        fitted = fit_dialog_to_available_screen(self, QSize(780, 600))
        self.notes.setMinimumHeight(min(300, max(140, fitted.height() - 300)))

    # ── construction ──
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        self.title = _plain(QLabel())
        self.title.setObjectName("gupTitle")
        self.title.setStyleSheet(themed_style("font-size:21px;font-weight:600;color:#f0f6fc"))
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.versions = _plain(QLabel())
        self.versions.setObjectName("gupVersions")
        self.versions.setStyleSheet(themed_style("color:#8b949e"))
        layout.addWidget(self.versions)
        meta_row = QHBoxLayout()
        self.meta = _plain(QLabel())
        self.meta.setObjectName("gupMeta")
        self.meta.setStyleSheet(themed_style("color:#8b949e"))
        meta_row.addWidget(self.meta)
        meta_row.addStretch()
        self.release_link = QPushButton(_L('在 GitHub 上查看此发布 ↗'))
        self.release_link.setObjectName("gupReleaseLink")
        self.release_link.setFlat(True)
        self.release_link.setAutoDefault(False)          # review r5 L7: Enter never opens GitHub
        self.release_link.setCursor(Qt.PointingHandCursor)
        self.release_link.setStyleSheet(themed_style("QPushButton{border:none;color:#58a6ff;padding:0 4px;background:transparent}"
                                                     "QPushButton:hover{text-decoration:underline}"))
        self.release_link.clicked.connect(self.controller.open_release_html)
        meta_row.addWidget(self.release_link)
        layout.addLayout(meta_row)

        self.pages = QStackedLayout()
        layout.addLayout(self.pages, 1)
        self.pages.addWidget(self._build_notes_page())
        self.pages.addWidget(self._build_progress_page())
        self.pages.addWidget(self._build_ready_page())
        self.pages.addWidget(self._build_error_page())

        self.blocker = _plain(QLabel())
        self.blocker.setObjectName("gupBlocker")
        self.blocker.setWordWrap(True)
        self.blocker.setStyleSheet(themed_style("color:#d29922"))
        self.blocker.hide()
        layout.addWidget(self.blocker)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(themed_style("color:#30363d"))
        layout.addWidget(separator)
        footer = QHBoxLayout()
        footer.setSpacing(10)

        def button(label, name, slot, primary=False):
            widget = QPushButton(label)
            widget.setObjectName(name)
            widget.setAutoDefault(False)
            if primary:
                widget.setProperty("class", "btnPrimary")
            widget.clicked.connect(slot)
            return widget

        self.skip_button = button(_L('跳过此版本'), "gupSkip", self._on_skip)
        footer.addWidget(self.skip_button)
        self.open_releases_button = button(_L('打开发布页 ↗'), "gupOpenReleases", self.controller.open_releases_page)
        footer.addWidget(self.open_releases_button)
        self.log_button = button(_L('查看安装日志'), "gupInstallLog", self.controller.open_install_log)
        footer.addWidget(self.log_button)
        footer.addStretch()
        self.later_button = button(_L('稍后'), "gupLater", self._on_later)
        footer.addWidget(self.later_button)
        self.hide_button = button(_L('隐藏'), "gupHide", self._on_hide)
        footer.addWidget(self.hide_button)
        self.cancel_button = button(_L('取消'), "gupCancel", self._on_cancel)
        footer.addWidget(self.cancel_button)
        self.close_button = button(_L('关闭'), "gupClose", self._on_close_clicked)
        footer.addWidget(self.close_button)
        self.retry_button = button(_L('重试'), "gupRetry", self._on_retry, primary=True)
        footer.addWidget(self.retry_button)
        self.redownload_button = button(_L('重新下载'), "gupRedownload", self.controller.redownload, primary=True)
        footer.addWidget(self.redownload_button)
        self.update_button = button(_L('立即更新'), "gupUpdateNow", self.controller.start_download, primary=True)
        footer.addWidget(self.update_button)
        self.install_button = button(_L('立即安装并重启'), "gupInstallNow", self._on_install, primary=True)
        footer.addWidget(self.install_button)
        layout.addLayout(footer)

    def _build_notes_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        card = QFrame()
        card.setObjectName("updateNotesCard")
        card.setStyleSheet(themed_style("QFrame#updateNotesCard{background:#161b22;border:1px solid #30363d;border-radius:8px}"))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(8)
        heading = QLabel(_L('更新内容'))
        heading.setStyleSheet(themed_style("font-size:15px;font-weight:600;color:#f0f6fc"))
        card_layout.addWidget(heading)
        self.notes = NotesBrowser()
        self.notes.setObjectName("gupNotes")
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(180)
        self.notes.setFrameShape(QFrame.NoFrame)
        self.notes.setStyleSheet(themed_style("background:#161b22;border:none;color:#c9d1d9"))
        self.notes.document().setDocumentMargin(2)
        self.notes.setOpenLinks(False)
        self.notes.setOpenExternalLinks(False)
        self.notes.setSearchPaths([])
        self.notes.anchorClicked.connect(self._on_anchor)
        self.notes.setTextInteractionFlags(Qt.TextBrowserInteraction)
        card_layout.addWidget(self.notes, 1)
        box.addWidget(card, 1)
        self.info = _plain(QLabel(_L('更新会下载经签名验证的 Global 安装程序，并以管理员权限在当前文件夹中静默安装；账号、设置和数据会保留。安装时程序会关闭并自动重新启动。')))
        self.info.setObjectName("gupInfo")
        self.info.setWordWrap(True)
        self.info.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        box.addWidget(self.info)
        self.manual = _plain(QLabel())
        self.manual.setObjectName("gupManual")
        self.manual.setWordWrap(True)
        self.manual.setStyleSheet(themed_style("color:#d29922"))
        self.manual.hide()
        box.addWidget(self.manual)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 24, 0, 0)
        box.setSpacing(10)
        self.progress_text = _plain(QLabel())
        self.progress_text.setObjectName("gupProgressText")
        self.progress_text.setWordWrap(True)
        box.addWidget(self.progress_text)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("gupProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)          # review r5 L11: the percentage is in the sentence
        box.addWidget(self.progress_bar)
        self.speed = _plain(QLabel())
        self.speed.setObjectName("gupSpeed")
        self.speed.setStyleSheet(themed_style("color:#8b949e"))
        box.addWidget(self.speed)
        box.addStretch()
        return page

    def _build_ready_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 24, 0, 0)
        box.setSpacing(10)
        self.ready_text = _plain(QLabel(_L('更新已准备好。安装时程序会关闭并自动重新启动。')))
        self.ready_text.setObjectName("gupReadyText")
        self.ready_text.setWordWrap(True)
        box.addWidget(self.ready_text)
        self.ready_sync = _plain(QLabel())
        self.ready_sync.setObjectName("gupReadySync")
        self.ready_sync.setWordWrap(True)
        self.ready_sync.setStyleSheet(themed_style("color:#8b949e"))
        self.ready_sync.hide()
        box.addWidget(self.ready_sync)
        box.addStretch()
        return page

    def _build_error_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 24, 0, 0)
        box.setSpacing(10)
        self.error_text = _plain(QLabel())
        self.error_text.setObjectName("gupErrorText")
        self.error_text.setWordWrap(True)
        self.error_text.setStyleSheet(themed_style("color:#f85149"))
        box.addWidget(self.error_text)
        box.addStretch()
        return page

    # ── rendering ──
    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only
        self.render(self.controller.view)

    def _meta_text(self, state) -> str:
        published, size = self.controller.candidate_meta()
        size_text = mb_text(size or state.size)
        when = local_time_text(published) or str(published or "")[:10]
        if when:
            return _LF('发布于 {0} · 安装包 {1} MB').format((when), (size_text))
        return _LF('安装包 {0} MB').format((size_text))       # review r5 L3: no empty date

    def render(self, state) -> None:
        phase = state.phase
        version = state.version_text or state.tag[1:]
        if self._read_only or phase == "updated":
            self.setWindowTitle(_LF('更新内容（{0}）').format((version)))
            self.title.setText(_LF('更新内容（{0}）').format((version)))
            self.versions.setText(_LF('NTE Drive Calc Global {0}').format((version)))
            self.meta.setText("")
            self.release_link.hide()
            self.notes.set_notes(self.controller.notes_markdown())
            self.info.hide()
            self.manual.hide()
            self.pages.setCurrentIndex(self.PAGE_NOTES)
            self._buttons(close=True)
            self.close_button.setDefault(True)
            self.blocker.hide()
            return
        self.info.show()
        self.manual.hide()
        self.setWindowTitle(_L('有新版本可用'))
        self.title.setText(_L('有新版本可用'))
        self.versions.setText(_LF('当前 {0}  →  新版本 {1}').format((GLOBAL_VERSION), (version)))
        self.meta.setText(self._meta_text(state))
        candidate = self.controller.candidate
        self.release_link.setVisible(bool(candidate is not None and candidate.tag == state.tag))
        if state.blocker_text:
            self.blocker.setText(_LF('当前无法更新：{0}').format((state.blocker_text)))
            self.blocker.show()
        else:
            self.blocker.hide()
        self.error_text.setToolTip(tooltip_text(state.error_detail))
        if phase in ("downloading", "verifying"):
            self.pages.setCurrentIndex(self.PAGE_PROGRESS)
            total = state.size or 1
            if phase == "verifying":
                self.progress_text.setText(_L('正在校验下载文件（SHA-256）…'))
                self.speed.setText("")
            else:
                self.progress_text.setText(_LF('正在下载更新… {0} / {1} MB（{2}%）').format(
                    (mb_text(state.downloaded)), (mb_text(total)), (state.progress)))
                if state.speed_bps > 0 and state.eta_seconds >= 0:
                    self.speed.setText(_LF('{0} MB/s · 约 {1}后完成').format(
                        (f"{state.speed_bps / (1024 * 1024):.1f}"), (duration_text(state.eta_seconds))))
                else:
                    self.speed.setText("")
            self.progress_bar.setValue(max(0, min(100, int(state.progress))))
            self._buttons(hide=True, cancel=True)
        elif phase == "ready" or phase == "installing":
            self.pages.setCurrentIndex(self.PAGE_READY)
            sync_text = self.controller.sync_running_text()
            self.ready_sync.setText(sync_text)
            self.ready_sync.setVisible(bool(sync_text))
            if phase == "installing":
                self.ready_text.setText(_L('正在关闭程序并启动安装程序…'))
                self._buttons()
            else:
                self.ready_text.setText(_L('更新已准备好。安装时程序会关闭并自动重新启动。'))
                self._buttons(later=True, install=True)
                self.install_button.setDefault(True)
        elif phase == "download_failed":
            self.pages.setCurrentIndex(self.PAGE_ERROR)
            self.error_text.setText(error_sentence(state.error_code, state.error_detail, state.retry_after_utc))
            self._buttons(open_releases=True, retry=True, close=True)
            self.retry_button.setDefault(True)
        elif phase == "launch_failed":
            self.pages.setCurrentIndex(self.PAGE_ERROR)
            self.error_text.setText(launch_sentence(state.error_code))
            if needs_redownload(state.error_code):
                self._buttons(redownload=True, close=True)
                self.redownload_button.setDefault(True)
            else:
                self._buttons(retry=True, close=True)
                self.retry_button.setDefault(True)
        elif phase == "not_completed":
            self.pages.setCurrentIndex(self.PAGE_ERROR)
            self.error_text.setText(_LF('更新未完成（当前仍是 {0}）。').format((GLOBAL_VERSION)))
            self._buttons(retry=True, log=bool((state.extra or {}).get("install_log")), close=True)
            self.retry_button.setDefault(True)
        elif phase == "manual_required":
            # review r5 M3: a signed release this build may not install in-app: say so before anything is downloaded
            self.pages.setCurrentIndex(self.PAGE_NOTES)
            self.notes.set_notes(self.controller.notes_markdown())
            self.info.hide()
            self.manual.setText(manual_install_sentence(state.manual_min))
            self.manual.show()
            self._buttons(skip=True, later=True, open_releases=True)
            self.open_releases_button.setDefault(True)
        else:   # available / skipped / checking / idle while the dialog is open
            self.pages.setCurrentIndex(self.PAGE_NOTES)
            self.notes.set_notes(self.controller.notes_markdown())
            self._buttons(skip=True, later=True, update=True)
            self.update_button.setDefault(True)
            self.update_button.setEnabled(phase != "checking")

    def _buttons(self, **visible) -> None:
        for name, button in (("skip", self.skip_button), ("open_releases", self.open_releases_button),
                             ("log", self.log_button), ("later", self.later_button), ("hide", self.hide_button),
                             ("cancel", self.cancel_button), ("close", self.close_button), ("retry", self.retry_button),
                             ("redownload", self.redownload_button), ("update", self.update_button),
                             ("install", self.install_button)):
            button.setVisible(bool(visible.get(name)))
            button.setDefault(False)

    # ── actions ──
    def _on_anchor(self, url: QUrl) -> None:
        if github_anchor_allowed(url.toString()):
            open_https_url(url.toString())

    def _on_skip(self) -> None:
        self.controller.skip()
        self._closing_by_code = True
        self.close()

    def _on_later(self) -> None:
        self.controller.later()
        self._closing_by_code = True
        self.close()

    def _on_hide(self) -> None:
        self._closing_by_code = True
        self.close()

    def _on_cancel(self) -> None:
        self.controller.cancel_download()

    def _on_retry(self) -> None:
        if self.controller.view.phase == "download_failed":
            self.controller.start_download()
        else:
            self.controller.request_install(relaunch=True)

    def _on_close_clicked(self) -> None:
        if self.controller.view.phase == "updated":
            self.controller.acknowledge_updated()
        self._closing_by_code = True
        self.close()

    def _on_install(self) -> None:
        self.controller.request_install(relaunch=True)

    def reject(self) -> None:   # Esc
        self._handle_user_close()
        super().reject()

    def closeEvent(self, event) -> None:   # title-bar ✕
        if not self._closing_by_code:
            self._handle_user_close()
        super().closeEvent(event)

    def _handle_user_close(self) -> None:
        if self._closing_by_code:
            return
        self._closing_by_code = True
        if self.controller.view.phase == "updated" and not self._read_only:
            self.controller.acknowledge_updated()
        elif not self._read_only:
            self.controller.dialog_closed_by_user()


class InstallLogDialog(QDialog):
    """Setup's log shown inside the program (review r5 I1: the elevated process hands no file to the shell)."""

    def __init__(self, parent, text: str) -> None:
        super().__init__(parent)
        self.setObjectName("gupInstallLogDialog")
        self.setWindowTitle(_L('安装日志'))
        self.setMinimumSize(640, 420)
        if hasattr(parent, "_current_style_sheet"):
            self.setStyleSheet(parent._current_style_sheet())
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setObjectName("gupInstallLogText")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.text.setFont(font)
        self.text.setPlainText(text)
        self.text.moveCursor(QTextCursor.End)
        layout.addWidget(self.text, 1)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton(_L('关闭'))
        close.setObjectName("gupInstallLogClose")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)


def show_install_log(parent, text: str) -> InstallLogDialog:
    dialog = InstallLogDialog(parent, text)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.show()
    return dialog
