# 导入战报“与我的角色对比”：后台计算与结果窗口（只读，不写入任何战报数据）。
"""'Compare with my characters' for imported battle reports.

The controller refreshes the button whenever a record is opened, runs the comparison on a worker
thread with its own history-service instance (so the page's native cache and marginal session are
never touched), drops stale results, and shows a non-modal result window.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.app.theme import theme_color, themed_style
from src.app.workers import WorkerThread
from src.services.battle_import_comparison_service import BattleImportComparisonService
from src.services.battle_report_persistence_service import BattleReportPersistenceDependencies
from src.ui.dashboard_widgets import metric_card

_FIELD_LABELS = {
    "character_level": _L('等级'), "breakthrough_stage": _L('突破'), "awakening_level": _L('觉醒'),
    "selected_awaken_effect_ids": _L('觉醒效果'), "likeability_level_10_enabled": _L('好感度'),
    "fork_id": _L('弧盘'), "fork_level": _L('弧盘等级'), "fork_breakthrough_stage": _L('弧盘突破'),
    "fork_refinement_level": _L('精炼'), "selected_skill_id": _L('技能'), "skill_levels": _L('技能等级'),
}


def _fmt(value) -> str:
    return "—" if value is None else f"{value:,.0f}"


def _pct(value) -> str:
    return "—" if value is None else f"{value:+.2f}%"


class BattleMyBuildComparisonDialog(QDialog):
    rerun_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_L('与我的角色对比'))
        self.resize(1080, 720)
        root = QVBoxLayout(self)
        root.setSpacing(10)
        self.header = QLabel()
        self.header.setWordWrap(True)
        self.header.setStyleSheet(themed_style("font-size:15px;font-weight:700;color:#f0f6fc"))
        root.addWidget(self.header)
        notice = QLabel(_L('固定轴对比：动作、逐击、目标与时段沿用原战报；与我相同的角色换成我的养成与当前空幕/驱动，其他角色保留原玩家配置。结果为量化估计。'))
        notice.setWordWrap(True)
        notice.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        root.addWidget(notice)

        self.match_table = QTableWidget(0, 4)
        self.match_table.setHorizontalHeaderLabels([_L('角色'), _L('处理'), _L('养成来源'), _L('变化项')])
        self._setup_table(self.match_table, stretch=3)
        self.match_table.setMaximumHeight(170)
        root.addWidget(self.match_table)

        self.status = QLabel("")
        self.status.setStyleSheet(themed_style("color:#e3b341"))
        root.addWidget(self.status)

        cards = QHBoxLayout()
        self.cards = {}
        for key, title in (("original", _L('原玩家队伍伤害')), ("mine", _L('我的队伍伤害')), ("delta", _L('变化'))):
            frame, value, subtitle = metric_card(title)
            self.cards[key] = (value, subtitle)
            cards.addWidget(frame)
        root.addLayout(cards)

        self.result_table = QTableWidget(0, 7)
        self.result_table.setHorizontalHeaderLabels([
            _L('角色'), _L('处理'), _L('原玩家伤害'), _L('我的伤害'), _L('变化'), _L('原玩家 DPS'), _L('我的 DPS')])
        self._setup_table(self.result_table, stretch=1)   # the short "handling" column absorbs spare width
        root.addWidget(self.result_table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        rerun = QPushButton(_L('重新对比'))
        rerun.clicked.connect(self.rerun_requested)
        close = QPushButton(_L('关闭'))
        close.clicked.connect(self.close)
        buttons.addWidget(rerun)
        buttons.addWidget(close)
        root.addLayout(buttons)

    @staticmethod
    def _setup_table(table: QTableWidget, *, stretch: int) -> None:
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.Stretch if column == stretch else QHeaderView.ResizeToContents)

    def begin(self) -> None:
        self.header.setText(_L('正在计算…'))
        self.status.setText("")
        self.match_table.setRowCount(0)
        self.result_table.setRowCount(0)
        for value, subtitle in self.cards.values():
            value.setText("—")
            subtitle.setText("")

    def set_error(self, message: str) -> None:
        self.header.setText(_L('对比失败'))
        self.status.setText(message)

    def set_results(self, plan, scopes) -> None:
        self.header.setText(_LF('对比对象：{0} 的导入战报').format(plan.source_account_nickname or "—"))
        reasons = {"replaced": _L('替换为我的配置'),
                   "not_owned": _L('保留原玩家配置（当前账号没有该角色）'),
                   "no_current_equipment": _L('保留原玩家配置（我的该角色未装备空幕/驱动）')}
        sources = {"account": _L('角色页已录入'), "native_observed": _L('游戏同步'),
                   "template": _L('角色页未录入（毕业模板）')}
        self.match_table.setRowCount(len(plan.matches))
        for row, match in enumerate(plan.matches):
            changed = [_FIELD_LABELS.get(k, k) for k in match.changed_fields]
            if match.equipment_changed:
                changed.append(_L('空幕/驱动'))
            values = (match.character_name, reasons.get(match.reason, match.reason),
                      sources.get(match.cultivation_source, match.cultivation_source) if match.replaced else "—",
                      ", ".join(changed) if match.replaced else "—")
            for column, value in enumerate(values):
                self.match_table.setItem(row, column, QTableWidgetItem(str(value)))
        if plan.matches and all(m.cultivation_source == "template" for m in plan.matches if m.replaced):
            self.status.setText(_L('提示：当前账号的角色页尚未录入养成，等级/觉醒/技能按毕业模板计算；空幕/驱动使用当前装备。'))

        original = sum(s.original_damage for s in scopes)
        mine_values = [s.mine_damage for s in scopes]
        mine = None if any(v is None for v in mine_values) else sum(mine_values)
        delta = None if mine is None or original <= 0 else (mine / original - 1.0) * 100.0
        self.cards["original"][0].setText(_fmt(original))
        self.cards["original"][1].setText(_LF('DPS {0}').format(_fmt(sum(s.original_dps for s in scopes))))
        self.cards["mine"][0].setText(_fmt(mine))
        mine_dps = [s.mine_dps for s in scopes]
        self.cards["mine"][1].setText(_LF('DPS {0}').format(
            "—" if any(v is None for v in mine_dps) else _fmt(sum(mine_dps))))
        self.cards["delta"][0].setText(_pct(delta))
        color = "#3fb950" if (delta or 0) > 0 else "#f85149" if (delta or 0) < 0 else "#c9d1d9"
        self.cards["delta"][0].setStyleSheet(f"color:{theme_color(color)};font-size:24px;font-weight:800")
        status = {s.status for s in scopes}
        self.cards["delta"][1].setText(_L('部分量化') if "partial" in status else _L('完整量化'))

        rows = [row for scope in scopes for row in scope.rows]
        self.result_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            basis = {"exact": "", "known": _L('（已量化）'), "axis": _L('（原轴）')}.get(row.mine_basis, "")
            values = (row.character_name, _L('我的配置') if row.replaced else _L('原玩家配置'),
                      _fmt(row.original_damage), _fmt(row.mine_damage) + basis, _pct(row.delta_percent),
                      _fmt(row.original_dps), _fmt(row.mine_dps))
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column >= 2:
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                if column == 4 and row.delta_percent:
                    item.setForeground(Qt.green if row.delta_percent > 0 else Qt.red)
                self.result_table.setItem(index, column, item)


class BattleMyBuildComparisonController(QObject):
    def __init__(self, *, page, dialog_parent, app_context, history_factory, current_history,
                 record_id_provider, parent=None) -> None:
        super().__init__(parent)
        self._page = page
        self._dialog_parent = dialog_parent
        self._app_context = app_context
        self._history_factory = history_factory
        self._current_history = current_history
        self._record_id_provider = record_id_provider
        self._token = 0
        self._worker = None
        self._dialog = None
        page.my_build_comparison_requested.connect(self.open)

    def refresh(self, record_id) -> None:
        state = {"imported": False, "available": False, "source_account_nickname": ""}
        if record_id is not None:
            try:
                state = BattleImportComparisonService.state(self._current_history(), int(record_id))
            except Exception:
                pass
        self._page.set_my_build_comparison_state(
            visible=state["imported"], enabled=state["available"] and self._worker is None,
            tooltip=_LF('用我的同名角色养成与当前空幕/驱动替换 {0} 的配置，在同一固定轴上重算').format(
                state["source_account_nickname"] or "—"))

    def open(self) -> None:
        record_id = self._record_id_provider()
        if record_id is None or self._worker is not None:
            return
        self._token += 1
        token = self._token
        account = self._app_context.account
        captured = (account.active_account_id, self._app_context.generation, int(record_id))
        static_path = self._app_context.paths.static_database_path
        user_path = account.user_database_path
        history = self._history_factory(BattleReportPersistenceDependencies(
            account_id=account.active_account_id, user_database_path=user_path,
            generation=self._app_context.generation, static_database_path=static_path))
        if self._dialog is None:
            self._dialog = BattleMyBuildComparisonDialog(self._dialog_parent)
            self._dialog.rerun_requested.connect(self.open)
        self._dialog.begin()
        self._dialog.show()
        self._dialog.raise_()

        def job():
            plan = BattleImportComparisonService.prepare(history, int(record_id), user_database_path=user_path,
                                                         static_database_path=static_path)
            return plan, BattleImportComparisonService.compare(history, plan, static_database_path=static_path)

        worker = WorkerThread(job, self)
        worker.result_ready.connect(lambda result: self._ready(token, captured, result))
        worker.error.connect(lambda message: self._failed(token, message))
        worker.finished.connect(lambda: self._release(worker))
        self._worker = worker
        self._page.set_my_build_comparison_state(visible=True, enabled=False, tooltip=None)
        worker.start()

    def _still_current(self, token, captured) -> bool:
        account = self._app_context.account
        now = (account.active_account_id, self._app_context.generation, self._record_id_provider())
        return token == self._token and captured == (now[0], now[1], None if now[2] is None else int(now[2]))

    def _ready(self, token, captured, result) -> None:
        if not self._still_current(token, captured) or self._dialog is None:
            return
        plan, scopes = result
        self._dialog.set_results(plan, scopes)

    def _failed(self, token, message: str) -> None:
        if token == self._token and self._dialog is not None:
            self._dialog.set_error(message)

    def _release(self, worker) -> None:
        if self._worker is worker:
            self._worker = None
        self.refresh(self._record_id_provider())
