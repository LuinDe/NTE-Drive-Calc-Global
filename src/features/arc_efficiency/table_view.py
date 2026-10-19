# 弧盘效率表的表格：数值排序、百分比条形图（精炼 1 实心、满精炼浅色延伸、100% 参考线）。
"""Table widget of the arc efficiency page: items that sort by their numeric value and a delegate that draws the
refinement-1 bar, a light extension up to the max-refinement value and the 100 % reference line under the text."""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

import html
import re

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
)

from src.app.theme import theme_color

SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
BAR_ROLE = int(Qt.ItemDataRole.UserRole) + 2      # (r1 %, max % or None, scale %, colour)
KEY_ROLE = int(Qt.ItemDataRole.UserRole) + 3      # (fork_id, refinement) of the cell
_HAN = re.compile("[一-鿿]")            # what the display layer's term pass looks for


# Rich text that QToolTip shows exactly as given (moved to src/ui/rich_tooltip.py for the team simulation's cards too;
# review UX F3): the Han characters become character references, line breaks <br>; Qt renders the original.
from src.ui.rich_tooltip import shown_as_is  # noqa: E402,F401


class SortItem(QTableWidgetItem):
    """Sorts by ``SORT_ROLE`` (numbers), falls back to the text."""

    def __lt__(self, other) -> bool:  # noqa: D105
        a, b = self.data(SORT_ROLE), other.data(SORT_ROLE)
        if a is not None and b is not None:
            try:
                return a < b
            except TypeError:
                pass
        return super().__lt__(other)


class BarDelegate(QStyledItemDelegate):
    """Percentage bar behind the cell text."""

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: D102
        bar = index.data(BAR_ROLE)
        if not bar:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        r1, rmax, scale, colour = bar
        rect = QRectF(opt.rect).adjusted(4, 6, -4, -6)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        base = QColor(colour)
        if scale and scale > 0 and r1 is not None:
            width = rect.width()
            if rmax is not None and rmax > r1:
                ext = QColor(base)
                ext.setAlphaF(0.16)
                painter.fillRect(QRectF(rect.left(), rect.top(), width * min(rmax, scale) / scale, rect.height()), ext)
            solid = QColor(base)
            solid.setAlphaF(0.42)
            painter.fillRect(QRectF(rect.left(), rect.top(), width * min(max(r1, 0.0), scale) / scale, rect.height()),
                             solid)
            line = QColor(theme_color("#8b949e"))
            painter.setPen(QPen(line, 1, Qt.PenStyle.DashLine))
            x = rect.left() + width * min(100.0, scale) / scale
            painter.drawLine(int(x), int(rect.top()) - 3, int(x), int(rect.bottom()) + 3)
        painter.restore()
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        pen = foreground.color() if hasattr(foreground, "color") else opt.palette.text().color()
        painter.save()
        painter.setPen(pen)
        font = opt.font
        if index.data(Qt.ItemDataRole.FontRole) is not None:
            font = index.data(Qt.ItemDataRole.FontRole)
        painter.setFont(font)
        painter.drawText(QRectF(opt.rect).adjusted(6, 0, -8, 0), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                         text)
        painter.restore()


class ArcTable(QTableWidget):
    """Read-only, row selection, header click handled by the page (it sorts the rows itself)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("arcEffTable")
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(34)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setSortingEnabled(False)
        self.bar_delegate = BarDelegate(self)
        self.tooltip_provider = None          # (row, column) -> text (active language) or None, on hover

    def viewportEvent(self, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.ToolTip and self.tooltip_provider is not None:
            index = self.indexAt(event.pos())
            text = self.tooltip_provider(index.row(), index.column()) if index.isValid() else None
            if text:                          # the provider returns the text in the active language
                QToolTip.showText(event.globalPos(), shown_as_is(text), self.viewport())
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().viewportEvent(event)
