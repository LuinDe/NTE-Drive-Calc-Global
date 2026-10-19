# 管理主窗口的全局主题和账号界面偏好。
"""Global theme and account-scoped UI preference methods."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import ctypes
import subprocess
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.app.theme import (
    apply_app_theme,
    current_style_sheet,
    refresh_inline_theme_styles,
    theme_color,
    theme_preference,
)


class MainWindowThemeMixin:
    def _load_ui_preferences(self):
        return self._account_settings.load("ui")

    def _save_ui_preferences(self):
        self._ui_preferences = self._account_settings.save("ui", self._ui_preferences)

    def _load_theme_preference(self, legacy_theme=None):
        return self._global_theme_settings.load(legacy_theme=legacy_theme)

    def _save_theme_preference(self):
        self._theme_preference = self._global_theme_settings.save(
            self._theme_preference
        )

    def _current_style_sheet(self):
        return current_style_sheet(QApplication.instance())

    def _apply_theme_preference(self):
        theme = getattr(self, "_theme_preference", "black")
        apply_app_theme(QApplication.instance(), theme)
        refresh_inline_theme_styles(self, QApplication.instance())
        if hasattr(self, "status_lbl"):
            self.status_lbl.setStyleSheet(f"color:{theme_color('#6e7681')};font-size:12px")

    def _set_theme_preference(self, theme):
        normalized = theme_preference(theme)
        if getattr(self, "_theme_preference", "black") == normalized:
            return True
        if not self._prompt_restart_for_theme_change():
            return False
        previous = getattr(self, "_theme_preference", "black")
        self._theme_preference = normalized
        self._save_theme_preference()
        if not self._restart_application_as_admin():
            self._theme_preference = previous
            self._save_theme_preference()
            return False
        return True

    def _prompt_restart_for_theme_change(self):
        box = QMessageBox(self)
        box.setWindowTitle(_L('重启生效'))
        box.setText(_L('切换主题需要重启应用，是否现在重启并应用？'))
        ok_button = box.addButton(_L('好的'), QMessageBox.AcceptRole)
        box.addButton(_L('取消'), QMessageBox.RejectRole)
        box.setDefaultButton(ok_button)
        box.exec()
        return box.clickedButton() is ok_button

    def _restart_application_as_admin(self):
        QApplication.processEvents()
        # Global 업데이트: 새 인스턴스를 띄우기 전에 다운로드 중이면 취소 여부를 묻는다. [계속 다운로드]면 재시작을
        # 하지 않는다(두 인스턴스가 남지 않게). 설치 준비 상태에서는 종료 시 설치를 묻지 않는다(재시작이 Setup을 띄우지 않게).
        gup_controller = getattr(self, "global_update_controller", None)
        if gup_controller is not None and gup_controller.close_decision(offer_install=False) == "cancel":
            return False
        program = sys.executable
        args = sys.argv[:]
        parameters = ""
        if not getattr(sys, "frozen", False):
            parameters = subprocess.list2cmdline(args)
        elif len(args) > 1:
            parameters = subprocess.list2cmdline(args[1:])
        if sys.platform == "win32":
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                program,
                parameters,
                str(self.app_context.paths.app_dir),
                1,
            )
            if result <= 32:
                if gup_controller is not None:
                    gup_controller.reset_close_decision()
                QMessageBox.warning(self, _L('重启失败'), _L('未能以管理员方式重启应用，主题设置已取消。'))
                return False
            QApplication.quit()
            return True
        if gup_controller is not None:
            gup_controller.reset_close_decision()
        QMessageBox.warning(self, _L('重启失败'), _L('当前系统不支持自动管理员重启，主题设置已取消。'))
        return False

