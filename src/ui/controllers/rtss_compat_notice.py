# Loader 시작·D3D 배포 직전 RTSS 호환성 안내 (NTE Drive Calc Global 추가 모듈)
"""Non-blocking reminder shown right before the calculator injects into the game (Loader start / D3D deploy).

Only a 'risk' result shows it; 'ok' and 'unknown' continue silently (the environment check lists the risk too).
The user may fix RTSS and check again, continue anyway, cancel, or turn the reminder off for the current account.
The calculator never changes RTSS settings, and a failing reminder never blocks the user's own operation.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from typing import Callable

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from src.app.theme import theme_color
from src.app.window_geometry import fit_dialog_to_available_screen
from src.services.rtss_compat import (
    STATUS_RISK, RtssCompatResult, RtssNoticePreference, current_rtss_compat,
)
from src.services.rtss_compat_guidance import (
    rtss_alternative_text, rtss_evidence, rtss_fix_steps, rtss_recheck_message, rtss_risk_summary,
)

METHOD_LOADER = "loader"
METHOD_D3D = "d3d"
_AMBER = "#d29922"
_GREEN = "#3fb950"
_GREY = "#8b949e"
# The dialog opens 640 px wide and as tall as its word-wrapped text needs at that width (a fixed 640 x 520 cut off
# the bottom of the fix-step box: 22-62 px with the Windows fonts, in Japanese the "Use Microsoft Detours API hooking"
# step).  The height is capped here and by the screen's work area; whatever does not fit then scrolls.
_PREFERRED_WIDTH = 640
_MAX_HEIGHT = 860


def _continue_label(method: str) -> str:
    return _L('仍然启动 Loader') if method == METHOD_LOADER else _L('仍然部署组件')


def _headline_style(color: str) -> str:
    return f"color:{theme_color(color)};font-size:16px;font-weight:700"


class RtssCompatDialog(QDialog):
    """Explain the RTSS conflict and the exact RTSS steps; Accepted = continue the injecting operation."""

    def __init__(self, parent, result: RtssCompatResult, *, game_executable: str, method: str,
                 recheck: Callable[[], RtssCompatResult]) -> None:
        super().__init__(parent)
        self._recheck = recheck
        self._game_executable = game_executable
        self._method = method
        self.result = result
        self.setObjectName("rtssCompatDialog")
        self.setWindowTitle(_L('RTSS 兼容性提醒'))
        self.setWindowModality(Qt.WindowModal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(10)

        # The texts sit in a frameless scroll area: it scrolls only when the screen is too small for the dialog's
        # full height (see _fit_to_contents); the "don't remind" box and the buttons below it always stay visible.
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("rtssCompatScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("rtssCompatBody")
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        self.headline = QLabel(_L('游戏可能在启动时崩溃：请先调整 RTSS 设置'), self.body)
        self.headline.setObjectName("rtssCompatHeadline")
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet(_headline_style(_AMBER))
        body.addWidget(self.headline)

        self.summary = QLabel(rtss_risk_summary(), self.body)
        self.summary.setObjectName("rtssCompatSummary")
        self.summary.setWordWrap(True)
        body.addWidget(self.summary)

        steps_title = QLabel(_L('解决方法（只需设置一次）：'), self.body)
        steps_title.setStyleSheet("font-weight:700")
        body.addWidget(steps_title)
        self.steps = QLabel("\n".join(rtss_fix_steps(game_executable)), self.body)
        self.steps.setObjectName("rtssCompatSteps")
        self.steps.setTextFormat(Qt.PlainText)
        self.steps.setWordWrap(True)
        self.steps.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.steps.setStyleSheet(
            f"background:{theme_color('#161b22')};border:1px solid {theme_color('#30363d')};"
            f"border-left:3px solid {theme_color(_AMBER)};border-radius:6px;padding:10px"
        )
        body.addWidget(self.steps)

        self.recheck_hint = QLabel(_LF('设置完成后点击“{0}”确认。').format(_L('重新检查 RTSS')), self.body)
        self.recheck_hint.setObjectName("rtssCompatRecheckHint")
        self.recheck_hint.setWordWrap(True)
        body.addWidget(self.recheck_hint)

        note = QLabel(
            _L('此设置只作用于 HTGame.exe，其他游戏的 RTSS 设置不变。Calc 只读取 RTSS 设置，不会修改。') + "\n"
            + rtss_alternative_text(),
            self.body,
        )
        note.setObjectName("rtssCompatNote")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{theme_color(_GREY)};font-size:12px")
        body.addWidget(note)

        self.evidence = QLabel(rtss_evidence(result), self.body)
        self.evidence.setObjectName("rtssCompatEvidence")
        self.evidence.setWordWrap(True)
        self.evidence.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.evidence.setStyleSheet(f"color:{theme_color(_GREY)};font-size:11px")
        body.addWidget(self.evidence)

        self.status = QLabel("", self.body)
        self.status.setObjectName("rtssCompatRecheckStatus")
        self.status.setWordWrap(True)
        self.status.hide()
        body.addWidget(self.status)
        body.addStretch(1)      # spare height (after "check again" hides the warning) stays below the texts
        self.scroll_area.setWidget(self.body)
        # setWidget() turns on the body's background fill; keep the dialog's own background behind the texts
        self.body.setAutoFillBackground(False)
        self.scroll_area.viewport().setAutoFillBackground(False)
        layout.addWidget(self.scroll_area, 1)

        self.dont_show = QCheckBox(_L('此账号不再提醒（检测详情中仍会显示）'), self)
        self.dont_show.setObjectName("rtssCompatDontShow")
        layout.addWidget(self.dont_show)

        actions = QHBoxLayout()
        self.recheck_button = QPushButton(_L('重新检查 RTSS'), self)
        self.recheck_button.setObjectName("rtssCompatRecheck")
        self.recheck_button.setAutoDefault(False)
        self.recheck_button.clicked.connect(self._check_again)
        actions.addWidget(self.recheck_button)
        actions.addStretch()
        self.cancel_button = QPushButton(_L('取消'), self)
        self.cancel_button.setObjectName("rtssCompatCancel")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.continue_button = QPushButton(_continue_label(method), self)
        self.continue_button.setObjectName("rtssCompatContinue")
        self.continue_button.setDefault(True)
        self.continue_button.clicked.connect(self.accept)
        actions.addWidget(self.continue_button)
        layout.addLayout(actions)
        self._actions = actions
        self._fitted_on_show = False
        self._fit_to_contents()
        self.continue_button.setFocus()

    def _text_width(self, width: int) -> int:
        margins = self.layout().contentsMargins()
        return max(1, width - margins.left() - margins.right() - 2 * self.scroll_area.frameWidth())

    def _height_for_width(self, width: int) -> int:
        """Dialog height that shows every text without scrolling at this dialog width (word wrap included)."""
        outer = self.layout()
        margins = outer.contentsMargins()
        texts = self.body.layout()
        inner = self._text_width(width)
        content = texts.totalHeightForWidth(inner) if texts.hasHeightForWidth() else texts.totalSizeHint().height()
        fixed = [self.dont_show.sizeHint().height(), self._actions.sizeHint().height()]
        return (margins.top() + 2 * self.scroll_area.frameWidth() + content + sum(fixed) + outer.spacing() * len(fixed)
                + margins.bottom())

    def _update_scroll_policy(self) -> None:
        # The vertical bar is turned off while the texts fit: otherwise a bar shown once (while the dialog was being
        # built at a smaller size) narrows the texts, they wrap into more lines and the bar never goes away again.
        if getattr(self, "_actions", None) is None:
            return
        fits = (self.height() >= self._height_for_width(self.width())
                and self._text_width(self.width()) >= self.body.minimumSizeHint().width())
        policy = Qt.ScrollBarAlwaysOff if fits else Qt.ScrollBarAsNeeded
        if self.scroll_area.verticalScrollBarPolicy() != policy:
            self.scroll_area.setVerticalScrollBarPolicy(policy)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scroll_policy()

    def _fit_to_contents(self, *, grow_only: bool = False, available_geometry: QRect | None = None) -> QSize:
        """Size the dialog to its texts (at most _MAX_HEIGHT and the screen's work area; the rest scrolls).

        grow_only: keep the current size unless the texts now need more height (after "check again")."""
        self.ensurePolished()               # fonts and style-sheet paddings decide the wrapped heights
        width = self.width() if grow_only else _PREFERRED_WIDTH
        needed = min(_MAX_HEIGHT, self._height_for_width(width))
        if grow_only and needed <= self.height():
            self._update_scroll_policy()
            return self.size()
        target = fit_dialog_to_available_screen(self, QSize(width, needed), available_geometry=available_geometry)
        if target.width() < width:          # a narrow screen: the texts wrap into more lines at the capped width
            needed = min(_MAX_HEIGHT, self._height_for_width(target.width()))
            target = fit_dialog_to_available_screen(self, QSize(target.width(), needed),
                                                    available_geometry=available_geometry)
        self._update_scroll_policy()        # also for a hidden dialog, whose resize event is still pending
        return target

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._fitted_on_show:
            # The app re-applies its theme style sheet to a dialog when it is shown; measure again with the final fonts.
            self._fitted_on_show = True
            self._fit_to_contents()

    def _check_again(self) -> None:
        try:
            result = self._recheck()
        except Exception as error:      # the check never raises; a test double might
            result = RtssCompatResult("unknown", "check_failed", detail=type(error).__name__)
        self.result = result
        tone, text = rtss_recheck_message(result)
        if result.use_detours is not None:
            # The profiles were read again: show the new values (also when fixed, so the line matches the headline).
            self.evidence.setText(rtss_evidence(result))
        if tone == "ok":
            # Fixed (or RTSS gone): the confirmation replaces the warning instead of sitting under it.
            self.headline.setText(text)
            self.headline.setStyleSheet(_headline_style(_GREEN))
            self.summary.hide()
            self.recheck_hint.hide()
            self.status.hide()
            self.continue_button.setText(_L('继续'))
            self._update_scroll_policy()
            return
        self.headline.setText(_L('游戏可能在启动时崩溃：请先调整 RTSS 设置'))
        self.headline.setStyleSheet(_headline_style(_AMBER))
        self.summary.show()
        self.recheck_hint.show()
        self.status.setStyleSheet(f"color:{theme_color(_AMBER if tone == 'risk' else _GREY)};font-weight:700")
        self.status.setText(text)
        self.status.show()
        self.continue_button.setText(_continue_label(self._method))
        self._fit_to_contents(grow_only=True)      # the status line adds height; never cut it off

    def dont_show_again(self) -> bool:
        return self.dont_show.isChecked()


def _account_config_dir(window):
    try:
        return window.app_context.account.user_config_dir
    except AttributeError:
        return None


def confirm_rtss_before_injection(
    window, *, method: str,
    check: Callable[..., RtssCompatResult] = current_rtss_compat,
    exec_dialog: Callable[[RtssCompatDialog], int] | None = None,
) -> bool:
    """True = go on with the injecting operation (no risk, reminder off, the user continued, or the reminder
    itself failed).  False only when the user chose Cancel / closed the reminder.

    Low-risk / offline modes never reach an injecting entry; the explicit capability test keeps it that way.
    """
    try:
        policy = getattr(window, "work_mode_service", None)
        if policy is not None and not policy.allowed("native_load"):
            return True
        preference = RtssNoticePreference(_account_config_dir(window))
        if preference.suppressed():
            return True
        result = check(force=True)
        if result.status != STATUS_RISK:
            return True
        executable = ""
        if policy is not None:
            executable = str(getattr(policy.settings, "game_executable", "") or "")
    except Exception:
        return True     # a reminder must never block the user's own operation
    try:
        dialog = RtssCompatDialog(window, result, game_executable=executable, method=method,
                                  recheck=lambda: check(force=True))
    except Exception:
        return True
    try:
        accepted = (exec_dialog or (lambda d: d.exec()))(dialog) == QDialog.Accepted
        try:
            if dialog.dont_show_again():
                preference.set_suppressed(True)
        except Exception:
            pass
        return accepted
    except Exception:
        return True
    finally:
        try:
            dialog.deleteLater()
        except Exception:
            pass
