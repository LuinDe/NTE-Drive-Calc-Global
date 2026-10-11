# 弧盘效率表（Global，演示版）页面入口：页面无法创建时显示占位页，不影响应用启动。
"""Arc efficiency table page (Global).  ``build_arc_efficiency_page(window)`` is the navigation builder
(``ui/main_window_mixins.ArcEfficiencyMixin``); the page module is imported lazily so a failure there never keeps the
application from starting."""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF


def _unavailable_page(error: BaseException):
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    from src.app.theme import themed_style

    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(24, 18, 24, 24)
    lay.setSpacing(14)
    title = QLabel(_L('弧盘效率表 (Beta)'))
    title.setStyleSheet(themed_style("font-size:22px;font-weight:800;color:#f0f6fc"))
    lay.addWidget(title)
    note = QLabel(_L('功能暂不可用'))
    note.setStyleSheet(themed_style("color:#e3b341;font-weight:700"))
    lay.addWidget(note)
    detail = QLabel(_LF('加载失败：{0}').format(f"{type(error).__name__}: {error}"))
    detail.setWordWrap(True)
    detail.setStyleSheet(themed_style("color:#8b949e"))
    lay.addWidget(detail)
    lay.addStretch()
    return page


def build_arc_efficiency_page(window):
    # Built in the main-window constructor like every page: nothing is read or computed until the page is shown.
    try:
        from src.features.arc_efficiency.page import ArcEfficiencyPage

        page = ArcEfficiencyPage(window)
    except Exception as error:
        try:
            from src.utils.logger import logger

            logger.opt(exception=True).warning("arc efficiency page unavailable")
        except Exception:
            pass
        page = _unavailable_page(error)
    window.arc_efficiency_page = page
    return page
