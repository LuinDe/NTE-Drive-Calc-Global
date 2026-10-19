# 队伍模拟「直接输入」模式的面板：循环构建器（队员/动作按钮 → 步骤块）、同步的文本输入、选项与保存/读取。
"""Custom-cycle panel of the team simulation page ("직접 입력").

The model is a list of ``CustomStep`` codes (``team_custom_notation``); chips and the notation text box are two
views of it:

* builder: pick a member, press an entry (support / swap) or action button -> a chip is appended after the
  selected chip; chips can be moved, repeated and removed;
* text box: the same sequence as text (``제로 서포트 > 제로 E > 제로 평타x3 ...``); edits are parsed after a short
  pause - a valid text replaces the model, an invalid one keeps the last valid model, shows the first error,
  underlines every error span and disables the calculation;
* options: cycle-gauge mode and starting gauge, cooldown / energy numbers and check mode, inferred team buffs
  on / off and manual buffs, repeat count and enemy numbers;
* saved cycles per account (``team_custom_cycle_store``) and "load the reviewed rotation" as a starting point.

Every model change runs ``preview_custom`` (generated palette numbers, no database) for the chip tooltips and
the summary line.  The text box is written through ``document().setPlainText`` because the display layer patches
``QPlainTextEdit.setPlainText`` (it would translate the notation).
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.app.theme import theme_color, theme_rgba, themed_style
from src.features.team_simulation import custom_view as view
from src.services import team_custom_cycle_service as cycle
from src.services import team_custom_cycle_store as store
from src.services import team_custom_notation as notation
from src.services import team_simulation_explanation as tx
from src.services.team_custom_notation import CustomStep

BLANK = -1.0                     # spin-box value shown as "—": the number is not set
WARN_COLOR = "#e3b341"
ERROR_COLOR = "#f85149"
_BUTTON = ("QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
           "padding:4px 10px;font-weight:700}"
           "QPushButton:hover{border-color:#58a6ff}"
           "QPushButton:disabled{color:#6e7681}")
_CAPTION = "color:#8b949e;font-size:12px"


def _caption(text) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(themed_style(_CAPTION))
    return label


def _button(text, tip=None) -> QPushButton:
    button = QPushButton(text)
    button.setStyleSheet(themed_style(_BUTTON))
    button.setCursor(Qt.PointingHandCursor)
    if tip:
        button.setToolTip(tip)
    return button


def _optional_spin(maximum: float, decimals: int = 1, step: float = 1.0) -> QDoubleSpinBox:
    """A number field that can be blank: the minimum (BLANK) is shown as "—"."""
    spin = QDoubleSpinBox()
    spin.setDecimals(decimals)
    spin.setRange(BLANK, maximum)
    spin.setSingleStep(step)
    spin.setSpecialValueText("—")
    spin.setValue(BLANK)
    spin.setMinimumWidth(78)
    return spin


def _optional_value(spin: QDoubleSpinBox):
    return None if spin.value() <= BLANK + 1e-9 else float(spin.value())


def _set_optional(spin: QDoubleSpinBox, value) -> None:
    spin.setValue(BLANK if value is None else float(value))


class _ManualBuffRow(QWidget):
    """One manual buff: kind, element, value, target, time window, enabled, remove."""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, panel: "CustomCyclePanel") -> None:
        super().__init__()
        self._panel = panel
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.enabled_box = QCheckBox()
        self.enabled_box.setChecked(True)
        row.addWidget(self.enabled_box)
        self.kind_combo = QComboBox()
        for kind in cycle.MANUAL_BUFF_KINDS:
            self.kind_combo.addItem(view.buff_kind_text(kind), kind)
        self.kind_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        row.addWidget(self.kind_combo)
        self.element_combo = QComboBox()
        row.addWidget(self.element_combo)
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setDecimals(1)
        self.value_spin.setRange(-100000.0, 100000.0)
        self.value_spin.setValue(20.0)
        self.value_spin.setMinimumWidth(84)
        row.addWidget(self.value_spin)
        row.addWidget(_caption(_L('对象')))
        self.target_combo = QComboBox()
        self.target_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        row.addWidget(self.target_combo)
        row.addWidget(_caption(_L('开始（秒）')))
        self.start_spin = _optional_spin(3600.0)
        self.start_spin.setToolTip(_L('留空则为整场战斗'))
        row.addWidget(self.start_spin)
        row.addWidget(_caption(_L('结束（秒）')))
        self.end_spin = _optional_spin(3600.0)
        self.end_spin.setToolTip(_L('留空则为整场战斗'))
        row.addWidget(self.end_spin)
        self.remove_btn = _button(_L('删除'))
        row.addWidget(self.remove_btn)
        row.addStretch()
        self.kind_combo.currentIndexChanged.connect(self._on_kind)
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        for signal in (self.enabled_box.toggled, self.element_combo.currentIndexChanged,
                       self.value_spin.valueChanged, self.target_combo.currentIndexChanged,
                       self.start_spin.valueChanged, self.end_spin.valueChanged):
            signal.connect(lambda *_a: self.changed.emit())
        self.refresh_targets()
        self._on_kind()

    def _on_kind(self) -> None:
        kind = self.kind_combo.currentData()
        wanted = self.element_combo.currentData()
        self.element_combo.blockSignals(True)
        self.element_combo.clear()
        if kind == "res_down":
            self.element_combo.addItem(_L('全部属性'), None)
        if kind in cycle.ELEMENT_BUFF_KINDS:
            for code in cycle.ELEMENTS:
                self.element_combo.addItem(view.ELEMENT_NAMES[code], code)
            index = self.element_combo.findData(wanted)
            self.element_combo.setCurrentIndex(max(0, index))
        self.element_combo.blockSignals(False)
        self.element_combo.setVisible(kind in cycle.ELEMENT_BUFF_KINDS)
        low, high = cycle.manual_buff_range(kind)       # e.g. defence ignore: 0-100 %
        self.value_spin.setRange(max(low, -100000.0), min(high, 100000.0))
        self.refresh_targets()
        self.changed.emit()

    def refresh_targets(self) -> None:
        """Target choices: the whole team or one member; the enemy for a resistance reduction."""
        kind = self.kind_combo.currentData()
        wanted = self.target_combo.currentData()
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        if kind == "res_down":
            self.target_combo.addItem(_L('敌人'), "enemy")
        else:
            self.target_combo.addItem(_L('全队'), "team")
            for cid, name in self._panel.team_names().items():
                self.target_combo.addItem(name, cid)
            index = self.target_combo.findData(wanted)
            self.target_combo.setCurrentIndex(max(0, index))
            if index < 0 and isinstance(wanted, int):
                self._target_lost()
        self.target_combo.setEnabled(kind != "res_down")
        self.target_combo.blockSignals(False)

    def _target_lost(self) -> None:
        """The targeted member is not in the team (any more): the row falls back to the whole team, so it is
        switched off - a buff typed for one member must not silently apply to everyone."""
        self.enabled_box.setChecked(False)

    def buff(self) -> cycle.ManualBuff:
        kind = self.kind_combo.currentData()
        return cycle.ManualBuff(
            kind=kind, value=float(self.value_spin.value()),
            target="enemy" if kind == "res_down" else self.target_combo.currentData(),
            element=self.element_combo.currentData() if kind in cycle.ELEMENT_BUFF_KINDS else None,
            start_s=_optional_value(self.start_spin), end_s=_optional_value(self.end_spin),
            enabled=self.enabled_box.isChecked())

    def set_buff(self, buff: cycle.ManualBuff) -> None:
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(buff.kind)))
        self._on_kind()
        if buff.kind in cycle.ELEMENT_BUFF_KINDS:
            self.element_combo.setCurrentIndex(max(0, self.element_combo.findData(buff.element)))
        self.value_spin.setValue(float(buff.value))
        found = 0
        if buff.kind != "res_down":
            found = self.target_combo.findData(buff.target)
            self.target_combo.setCurrentIndex(max(0, found))
        _set_optional(self.start_spin, buff.start_s)
        _set_optional(self.end_spin, buff.end_s)
        self.enabled_box.setChecked(bool(buff.enabled))
        if found < 0:
            self._target_lost()

    def retranslate(self) -> None:
        """Language switch: tooltips are translated when set, so the fixed ones are set again."""
        self.start_spin.setToolTip(_L('留空则为整场战斗'))
        self.end_spin.setToolTip(_L('留空则为整场战斗'))


class CustomCyclePanel(QFrame):
    """Builder, notation text, options and saved cycles of the custom-cycle mode."""

    changed = Signal()                    # the model or its validity changed
    load_approved_requested = Signal(int)     # "load the reviewed rotation": the number of loops to load
    status_message = Signal(str)          # text for the page's status line

    def __init__(self, page) -> None:
        super().__init__()
        self._page = page
        self.setObjectName("card")
        self._lang = view.current_lang()
        self._steps: list[CustomStep] = []
        self._selected = -1
        self._member_slot = 0
        self._text_issues: tuple = ()
        self._model_errors: list = []
        self._model_warnings: list = []
        self._load_error = ""
        self._preview = None
        self._updating_text = False
        self._loading = False
        self._current_name = ""
        self._store_path = None
        self._moved_aside = ""                # unreadable cycle file of this account that load() renamed
        self._file = store.CycleFile()
        self._result_buffs: list = []
        self._disabled_buffs: set = set()
        self._manual_rows: list[_ManualBuffRow] = []
        self._team_cache: list = []
        self._build()
        self._team_cache = self.team()
        self._reset_resources(range(len(self._team_cache)))
        self._rebuild_palette()
        self._model_changed()
        self.reload_store()

    # ── data from the page ─────────────────────────────────────────
    def team(self) -> list[int]:
        return [int(card.character_combo.currentData()) for card in self._page.cards]

    def team_names(self) -> dict:
        out = {}
        for cid in self.team():
            tpl = self._page.template(cid) or {}
            out[cid] = tpl.get("name_zh") or str(cid)
        return out

    def _slot_color(self, cid) -> str:
        from src.features.team_simulation.page import SLOT_COLORS

        team = self.team()
        return SLOT_COLORS[team.index(cid) % len(SLOT_COLORS)] if cid in team else "#8b949e"

    # ── construction ───────────────────────────────────────────────
    def _build(self) -> None:
        from src.features.team_simulation.explanation_view import _FlowLayout

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)
        hint = QLabel(_L('直接输入循环：按「角色 动作」的顺序用 > 连接。'))
        hint.setWordWrap(True)
        hint.setStyleSheet(themed_style("color:#c9d1d9;font-size:12px"))
        lay.addWidget(hint)

        saved = QHBoxLayout()
        saved.setSpacing(6)
        saved.addWidget(_caption(_L('保存的循环')))
        self.saved_combo = QComboBox()
        self.saved_combo.setMinimumWidth(180)
        saved.addWidget(self.saved_combo)
        self.load_btn = _button(_L('读取'))
        self.save_btn = _button(_L('保存'))
        self.save_as_btn = _button(_L('另存为…'))
        self.delete_btn = _button(_L('删除'))
        for button in (self.load_btn, self.save_btn, self.save_as_btn, self.delete_btn):
            saved.addWidget(button)
        saved.addStretch()
        self.approved_btn = _button(_L('读取已审核循环'))
        saved.addWidget(self.approved_btn)
        lay.addLayout(saved)
        self.load_btn.clicked.connect(self._on_load)
        self.save_btn.clicked.connect(self._on_save)
        self.save_as_btn.clicked.connect(self._on_save_as)
        self.delete_btn.clicked.connect(self._on_delete)
        self.approved_btn.clicked.connect(self._approved_menu)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        grid.addWidget(_caption(_L('队员')), 0, 0, Qt.AlignTop)
        members = QHBoxLayout()
        members.setSpacing(6)
        self.member_group = QButtonGroup(self)
        self.member_group.setExclusive(True)
        self.member_buttons: list[QPushButton] = []
        for slot in range(len(self._page.cards)):
            button = QPushButton("")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.member_group.addButton(button, slot)
            self.member_buttons.append(button)
            members.addWidget(button)
        members.addStretch()
        self.member_buttons[0].setChecked(True)
        self.member_group.idClicked.connect(self._on_member)
        grid.addLayout(members, 0, 1)

        grid.addWidget(_caption(_L('登场方式')), 1, 0, Qt.AlignTop)
        self.entry_row = QHBoxLayout()
        self.entry_row.setSpacing(6)
        grid.addLayout(self.entry_row, 1, 1)
        grid.addWidget(_caption(_L('动作')), 2, 0, Qt.AlignTop)
        self.action_host = QWidget()
        self.action_flow = _FlowLayout(self.action_host, 6)
        grid.addWidget(self.action_host, 2, 1)

        grid.addWidget(_caption(_L('循环步骤')), 3, 0, Qt.AlignTop)
        steps_col = QVBoxLayout()
        steps_col.setSpacing(6)
        self.chip_host = QWidget()
        self.chip_flow = _FlowLayout(self.chip_host, 6)
        steps_col.addWidget(self.chip_host)
        tools = QHBoxLayout()
        tools.setSpacing(6)
        self.prev_btn = _button("◀", _L('前移'))
        self.next_btn = _button("▶", _L('后移'))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, notation.MAX_STEP_REPEAT)
        self.repeat_spin.setPrefix("x")
        self.repeat_spin.setToolTip(_L('重复执行'))
        self.remove_btn = _button(_L('删除步骤'))
        self.clear_btn = _button(_L('清空全部'))
        for widget in (self.prev_btn, self.next_btn, _caption(_L('重复执行')), self.repeat_spin, self.remove_btn):
            tools.addWidget(widget)
        tools.addStretch()
        tools.addWidget(self.clear_btn)
        steps_col.addLayout(tools)
        self.summary = QLabel("")
        self.summary.setStyleSheet(themed_style(_CAPTION))
        steps_col.addWidget(self.summary)
        grid.addLayout(steps_col, 3, 1)
        self.prev_btn.clicked.connect(lambda: self.move_selected(-1))
        self.next_btn.clicked.connect(lambda: self.move_selected(1))
        self.repeat_spin.valueChanged.connect(self._on_repeat_spin)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_steps)
        for key, slot in ((QKeySequence(Qt.Key_Delete), self.remove_selected),
                          (QKeySequence(Qt.CTRL | Qt.Key_Left), lambda: self.move_selected(-1)),
                          (QKeySequence(Qt.CTRL | Qt.Key_Right), lambda: self.move_selected(1))):
            shortcut = QShortcut(key, self.chip_host)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        grid.addWidget(_caption(_L('文本输入')), 4, 0, Qt.AlignTop)
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_row = QHBoxLayout()
        text_row.setSpacing(6)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("teamSimCustomText")
        self.text_edit.setMinimumHeight(64)
        self.text_edit.setMaximumHeight(120)
        self.text_edit.setTabChangesFocus(True)
        self.text_edit.installEventFilter(self)
        text_row.addWidget(self.text_edit, 1)
        self.tidy_btn = _button(_L('整理文本'))
        text_row.addWidget(self.tidy_btn, 0, Qt.AlignTop)
        text_col.addLayout(text_row)
        self.error_label = QLabel("")
        self.error_label.setObjectName("teamSimCustomError")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color:{theme_color(ERROR_COLOR)};font-size:12px;font-weight:700")
        self.error_label.setVisible(False)
        text_col.addWidget(self.error_label)
        grid.addLayout(text_col, 4, 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self.apply_text_now)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.tidy_btn.clicked.connect(self.tidy_text)

        self.options_toggle = QPushButton("")
        self.options_toggle.setCheckable(True)
        self.options_toggle.setCursor(Qt.PointingHandCursor)
        self.options_toggle.setStyleSheet(themed_style(
            "QPushButton{background:transparent;border:none;color:#58a6ff;font-weight:800;text-align:left;"
            "font-size:13px;padding:2px 0px}"))
        lay.addWidget(self.options_toggle)
        self.options_box = QFrame()
        self.options_box.setObjectName("teamSimCustomOptions")
        self.options_box.setStyleSheet(themed_style(
            "QFrame#teamSimCustomOptions{background:#0d1117;border:1px solid #21262d;border-radius:6px}"))
        self.options_box.setVisible(False)
        lay.addWidget(self.options_box)
        self.options_toggle.toggled.connect(self._on_options_toggled)
        self._build_options()
        self._on_options_toggled(False)
        self._refresh_members()
        self._refresh_entry_row()

    def _section(self, parent: QVBoxLayout, title) -> QVBoxLayout:
        label = QLabel(title)
        label.setStyleSheet(themed_style("color:#c9d1d9;font-size:13px;font-weight:800;margin-top:4px"))
        parent.addWidget(label)
        col = QVBoxLayout()
        col.setSpacing(6)
        parent.addLayout(col)
        return col

    def _build_options(self) -> None:
        lay = QVBoxLayout(self.options_box)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        slots = range(len(self._page.cards))

        # 1. cycle gauge
        gauge = self._section(lay, _L('环合值模式'))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.gauge_as_typed = QRadioButton(_L('按输入执行'))
        self.gauge_as_typed.setToolTip(_L('援护始终按输入以援护技登场；环合值不足 100 时在该步骤显示警告。'))
        self.gauge_check = QRadioButton(_L('检查环合值'))
        self.gauge_check.setToolTip(_L('环合值不足 100 或属性不相邻时，援护改为普通切换。'))
        self.gauge_as_typed.setChecked(True)
        mode_row.addWidget(self.gauge_as_typed)
        mode_row.addWidget(self.gauge_check)
        mode_row.addStretch()
        gauge.addLayout(mode_row)
        start_row = QHBoxLayout()
        start_row.setSpacing(8)
        start_row.addWidget(_caption(_L('开始时环合值')))
        self.gauge_labels: list[QLabel] = []
        self.gauge_spins: list[QSpinBox] = []
        for _slot in slots:
            label = QLabel("")
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(100)
            self.gauge_labels.append(label)
            self.gauge_spins.append(spin)
            start_row.addWidget(label)
            start_row.addWidget(spin)
        start_row.addStretch()
        gauge.addLayout(start_row)
        self.gauge_reset_box = QCheckBox(_L('每次重复都重置为开始值'))
        gauge.addWidget(self.gauge_reset_box)

        # 2. cooldown and energy
        res = self._section(lay, _L('冷却与能量'))
        check_row = QHBoxLayout()
        check_row.setSpacing(8)
        check_row.addWidget(_caption(_L('检查方式')))
        self.resource_combo = QComboBox()
        for code in ("off", "warn", "wait", "strict"):
            self.resource_combo.addItem(view.resource_check_text(code), code)
        self.resource_combo.setCurrentIndex(1)
        self.resource_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        check_row.addWidget(self.resource_combo)
        check_row.addWidget(_caption(_L('最长等待（秒）')))
        self.cd_wait_max_spin = _optional_spin(60.0)
        self.cd_wait_max_spin.setToolTip(_L('留空：插入等待不限时，严格最多 60 秒；仅对插入等待/严格有效'))
        check_row.addWidget(self.cd_wait_max_spin)
        self.resource_defaults_btn = _button(_L('恢复默认值'))
        check_row.addWidget(self.resource_defaults_btn)
        check_row.addStretch()
        res.addLayout(check_row)
        res_grid = QGridLayout()
        res_grid.setHorizontalSpacing(10)
        res_grid.setVerticalSpacing(4)
        heads = ("", _L('E 冷却（秒）'), _L('Q 冷却（秒）'), _L('Q 能量消耗'), _L('开始能量'), _L('充能效率 %'))
        for c, text in enumerate(heads):
            res_grid.addWidget(_caption(text), 0, c)
        self.resource_labels: list[QLabel] = []
        self.resource_spins: list[dict] = []
        for slot in slots:
            label = QLabel("")
            self.resource_labels.append(label)
            res_grid.addWidget(label, slot + 1, 0)
            row = {"e_cd_s": _optional_spin(600.0), "q_cd_s": _optional_spin(600.0),
                   "q_cost": _optional_spin(100000.0), "start_energy": _optional_spin(100000.0),
                   "charge_eff": _optional_spin(1000.0)}
            for c, name in enumerate(("e_cd_s", "q_cd_s", "q_cost", "start_energy", "charge_eff"), 1):
                res_grid.addWidget(row[name], slot + 1, c)
            self.resource_spins.append(row)
        res_grid.setColumnStretch(6, 1)
        res.addLayout(res_grid)
        res.addWidget(_caption(_L('留空则不检查')))
        self.own_resource_caption = _caption("")       # own resources of the team (Hotori / Shinku)
        self.own_resource_caption.setWordWrap(True)
        self.own_resource_caption.setVisible(False)
        res.addWidget(self.own_resource_caption)
        self.resource_defaults_btn.clicked.connect(lambda: self._reset_resources(range(len(self._page.cards))))

        # 3. team buffs
        buffs = self._section(lay, _L('队伍 Buff'))
        buffs.addWidget(_caption(_L('引擎推算的队伍 Buff')))
        self.inferred_host = QWidget()
        self.inferred_col = QVBoxLayout(self.inferred_host)
        self.inferred_col.setContentsMargins(0, 0, 0, 0)
        self.inferred_col.setSpacing(2)
        buffs.addWidget(self.inferred_host)
        buffs.addWidget(_caption(_L('手动 Buff')))
        self.manual_host = QWidget()
        self.manual_col = QVBoxLayout(self.manual_host)
        self.manual_col.setContentsMargins(0, 0, 0, 0)
        self.manual_col.setSpacing(4)
        buffs.addWidget(self.manual_host)
        add_row = QHBoxLayout()
        self.add_buff_btn = _button(_L('添加 Buff'))
        add_row.addWidget(self.add_buff_btn)
        add_row.addStretch()
        buffs.addLayout(add_row)
        self.add_buff_btn.clicked.connect(lambda: self.add_manual_buff())

        # 4. numbers
        numbers = self._section(lay, _L('数值设定'))
        num_grid = QGridLayout()
        num_grid.setHorizontalSpacing(10)
        num_grid.setVerticalSpacing(4)
        self.repeat_count_spin = QSpinBox()
        self.repeat_count_spin.setRange(1, cycle.MAX_REPEAT)
        self.enemy_level_spin = QSpinBox()
        self.enemy_level_spin.setRange(1, 100)
        self.enemy_level_spin.setValue(80)
        self.resistance_spin = QDoubleSpinBox()
        self.resistance_spin.setRange(-100.0, 100.0)
        self.resistance_spin.setDecimals(1)
        self.resistance_spin.setValue(20.0)
        self.defense_spin = QDoubleSpinBox()
        self.defense_spin.setRange(0.0, 100.0)
        self.defense_spin.setDecimals(1)
        self.vulnerability_spin = QDoubleSpinBox()
        self.vulnerability_spin.setRange(0.0, 200.0)
        self.vulnerability_spin.setDecimals(1)
        self.swap_time_spin = QDoubleSpinBox()
        self.swap_time_spin.setRange(0.0, cycle.MAX_SWAP_TIME_S)
        self.swap_time_spin.setDecimals(2)
        self.swap_time_spin.setSingleStep(0.1)
        # awakening node rules with a boss / single-enemy condition (Sagiri ⑤ / 共鸣6, Hathor ③, Mint ④)
        self.boss_box = QCheckBox(_L('首领（Boss）'))
        self.boss_box.setToolTip(_L('觉醒效果的首领条件按此判断（例如浮空、压制对首领无效）'))
        self.enemy_count_spin = QSpinBox()
        self.enemy_count_spin.setRange(1, cycle.MAX_ENEMIES)
        self.enemy_count_spin.setValue(1)
        self.enemy_count_spin.setToolTip(_L('觉醒效果的「单个敌人」条件按此判断；伤害仍按一个目标计算'))
        fields = ((_L('重复次数'), self.repeat_count_spin), (_L('敌人等级'), self.enemy_level_spin),
                  (_L('敌人抗性 %'), self.resistance_spin), (_L('敌人防御降低 %'), self.defense_spin),
                  (_L('易伤 %'), self.vulnerability_spin), (_L('切换耗时（秒）'), self.swap_time_spin),
                  (_L('敌人数量'), self.enemy_count_spin), (_L('敌人类型'), self.boss_box))
        for i, (text, widget) in enumerate(fields):
            widget.setMinimumWidth(84)
            num_grid.addWidget(_caption(text), i // 3 * 2, i % 3)
            num_grid.addWidget(widget, i // 3 * 2 + 1, i % 3)
        num_grid.setColumnStretch(3, 1)
        numbers.addLayout(num_grid)

        # options that change the preview (gauge, cooldown, repeat, swap time) refresh it
        for signal in (self.gauge_as_typed.toggled, self.gauge_reset_box.toggled,
                       self.resource_combo.currentIndexChanged, self.repeat_count_spin.valueChanged,
                       self.swap_time_spin.valueChanged, self.cd_wait_max_spin.valueChanged,
                       self.boss_box.toggled):
            signal.connect(lambda *_a: self._options_changed())
        # the longest wait acts only where waits are inserted (review F-UX8)
        self.resource_combo.currentIndexChanged.connect(lambda *_a: self._sync_wait_max())
        self._sync_wait_max()
        for spin in self.gauge_spins:
            spin.valueChanged.connect(lambda *_a: self._options_changed())
        for row in self.resource_spins:
            for spin in row.values():
                spin.valueChanged.connect(lambda *_a: self._options_changed())
        self._render_inferred()

    def _on_options_toggled(self, checked: bool) -> None:
        self.options_box.setVisible(bool(checked))
        self.options_toggle.setText(("▼ " if checked else "▶ ") + _L('选项'))

    # ── members and palette ────────────────────────────────────────
    def _refresh_members(self) -> None:
        names = self.team_names()
        team = self.team()
        for slot, button in enumerate(self.member_buttons):
            cid = team[slot]
            color = self._slot_color(cid)
            button.setText(names.get(cid, str(cid)))
            button.setStyleSheet(
                "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;"
                f"color:{theme_color(color)};padding:4px 12px;font-weight:700}}"
                f"QPushButton:checked{{background:{theme_rgba(color, 0.22)};border-color:{theme_color(color)}}}")
            for label in (self.gauge_labels[slot], self.resource_labels[slot]):
                label.setText(names.get(cid, str(cid)))
                label.setStyleSheet(f"color:{theme_color(color)};font-size:12px;font-weight:700")
        for row in self._manual_rows:
            row.refresh_targets()
        self._refresh_own_resources(team, names)

    def _refresh_own_resources(self, team, names) -> None:
        """One line per team member with an own resource instead of ultimate energy (team_resource_data)."""
        caption = getattr(self, "own_resource_caption", None)
        if caption is None:
            return
        from src.services import team_resources as tr
        from src.services import team_simulation_explanation as tx

        text = None
        for cid in team:
            energy = tr.record(cid).get("energy") or {}
            name = names.get(cid, str(cid))
            line = None
            if energy.get("kind") == "own_clock":
                clock = energy.get("clock") or {}
                value = {k: float(v[0]) for k, v in clock.items() if isinstance(v, tuple) and v and v[0] is not None}
                line = _LF('{0}：「{1}」上限 {2:g}，每秒 +{3:g}，变轨技能消耗 {4:g}，极轨终结需蓄满（游戏数据；插入等待时等待蓄满；严格时与冷却相同：队伍中立即切换，单人时等待）').format(
                    name, tx.own_resource_text(clock.get("name_zh") or ""), value.get("cap", 120.0),
                    value.get("regen_per_s", 6.0), value.get("e_cost", 60.0))
            elif energy.get("kind") == "own_meter":
                meter = energy.get("meter") or {}
                cap = (meter.get("cap") or (60.0,))[0]
                line = _LF('{0}：「{1}」上限 {2:g}（每次获得量的单位未确认，只显示不检查）').format(
                    name, tx.own_resource_text(meter.get("name_zh") or ""), float(cap or 60.0))
            if line:
                text = line if text is None else text + "\n" + line
        caption.setText(text or "")
        caption.setVisible(bool(text))

    def _on_member(self, slot: int) -> None:
        self._member_slot = int(slot)
        self._rebuild_palette()

    def _clear_flow(self, flow) -> None:
        while flow.count():
            item = flow.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _refresh_entry_row(self) -> None:
        while self.entry_row.count():
            item = self.entry_row.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:           # keep the reference: setParent(None) can free an unreferenced widget
                widget.setParent(None)
                widget.deleteLater()
        self.entry_buttons: dict = {}
        for action in notation.ENTRY_ACTIONS:
            button = _button(view.token_text(action, self._lang), view.action_tip(action))
            button.clicked.connect(lambda _checked=False, a=action: self.append_action(a))
            self.entry_buttons[action] = button
            self.entry_row.addWidget(button)
        self.entry_row.addStretch()

    def _entry_names(self, cid: int, action: str) -> list[tuple[int, str]]:
        """[(position, "token#N  game name / name in a state")] of a slot over every table of the member."""
        from src.services import team_custom_actions as data

        from src.i18n_display import tr

        def game(name: str) -> str:
            # each game name on its own: the ja display layer leaves a whole line alone once it holds kana, so
            # "E長押し  律动音浪" kept the Chinese name (2.3.1-global.2)
            return str(tr(name)) if name else name

        token = view.token_text(action, self._lang)
        by_pos: dict = {}
        for code, table in notation.slot_tables(cid, action):
            state = data.PALETTE[cid]["states"].get(code) if code else None
            for i, entry in enumerate(table["entries"], 1):
                if entry and entry[0] == "@time":
                    name = "" if str(entry[2]).startswith("Melee") else game(str(entry[2]))
                else:
                    name = " + ".join(game((data.ACTIONS.get(tuple(k)) or {}).get("name_zh") or k[1]) for k in entry)
                if state is not None:
                    name = game(str(tx.form_name_text(code, state["name_zh"]))) + ": " + name
                by_pos.setdefault(i, [])
                if name:
                    by_pos[i].append(name)
        out = []
        for pos in sorted(by_pos):
            head = token if pos == 1 else f"{token}#{pos}"
            names = list(dict.fromkeys(by_pos[pos]))
            out.append((pos, head + ("  " + " / ".join(names) if names else "")))
        return out

    def _rebuild_palette(self) -> None:
        self._clear_flow(self.action_flow)
        self.action_buttons: dict = {}
        team = self.team()
        cid = team[min(self._member_slot, len(team) - 1)]
        for action in notation.available_actions(cid):
            if action in notation.ENTRY_ACTIONS:
                continue
            most = notation.slot_max(cid, action) if action in notation.SLOT_ACTIONS else 0
            text = view.token_text(action, self._lang)
            if action == "wait":
                text += "…"
            elif action == "special" and most > 1:
                text += " ▾"
            tip = view.action_tip(action)
            if most:
                from src.i18n_display import tr

                # each game-name line on its own: the joined string (its first line already translated) is left
                # alone by the ja display layer
                lines = [str(tr(label)) for _pos, label in self._entry_names(cid, action)]
                tip = "\n".join(([tip] if tip else []) + lines)
            button = _button(text, tip)
            if action == "wait":
                button.clicked.connect(self._on_wait)
            elif action == "special" and most > 1:
                button.clicked.connect(lambda _checked=False, b=button, a=action: self._variant_menu(b, a))
            else:
                button.clicked.connect(lambda _checked=False, a=action: self.append_action(a))
            if most > 1:
                button.setContextMenuPolicy(Qt.CustomContextMenu)
                button.customContextMenuRequested.connect(
                    lambda _pos, b=button, a=action: self._variant_menu(b, a))
            self.action_buttons[action] = button
            self.action_flow.addWidget(button)
        self.action_host.updateGeometry()

    def variant_menu(self, action: str) -> QMenu:
        """Menu of the positions of a slot with several entries ("E", "E#2" ...) with the game names."""
        from src.i18n_display import tr

        team = self.team()
        cid = team[min(self._member_slot, len(team) - 1)]
        menu = QMenu(self)
        for pos, label in self._entry_names(cid, action):
            entry = menu.addAction(tr(label))       # QMenu.addAction(str) is not covered by the display layer
            entry.triggered.connect(lambda _checked=False, p=pos: self.append_action(action, None if p == 1 else p))
        return menu

    def _variant_menu(self, button: QPushButton, action: str) -> None:
        self.variant_menu(action).exec(button.mapToGlobal(button.rect().bottomLeft()))

    def approved_menu(self) -> QMenu:
        """Choices of "load the reviewed rotation": one loop (to repeat), or the reviewed run itself."""
        from src.services.team_simulation_service import DEFAULT_LOOPS

        menu = QMenu(self)
        for loops, label in ((1, _L('读取 1 轮（可用重复次数延长）')),
                             (DEFAULT_LOOPS, _LF('读取 {0} 轮（与已审核循环模式相同的过程）').format(DEFAULT_LOOPS))):
            entry = menu.addAction(str(label))      # QMenu.addAction(str) is not covered by the display layer
            entry.triggered.connect(lambda _checked=False, n=loops: self.load_approved_requested.emit(n))
        return menu

    def _approved_menu(self) -> None:
        self.approved_menu().exec(self.approved_btn.mapToGlobal(self.approved_btn.rect().bottomLeft()))

    def _on_wait(self) -> None:
        seconds, ok = QInputDialog.getDouble(self, _L('等待…'), _L('等待秒数'), 1.0, 0.1, notation.MAX_WAIT_S, 1)
        if ok:
            self.add_wait(seconds)

    # ── model edits ────────────────────────────────────────────────
    def steps(self) -> tuple:
        return tuple(self._steps)

    def set_steps(self, steps) -> None:
        self._steps = list(steps)
        self._selected = len(self._steps) - 1
        self._load_error = ""
        self._text_issues = ()
        self._model_changed()

    def _text_blocks_edit(self) -> bool:
        """True while the text box holds a text with errors: a builder edit would rewrite the box from the last
        valid steps and the typed text would be lost.  The error is repeated on the status line instead."""
        if not self._text_issues:
            return False
        self.status_message.emit(self.first_error())
        return True

    def append_action(self, action: str, pos: int | None = None, seconds: float | None = None) -> None:
        if self._text_blocks_edit():
            return
        team = self.team()
        cid = team[min(self._member_slot, len(team) - 1)]
        at = self._selected + 1 if 0 <= self._selected < len(self._steps) else len(self._steps)
        prev = self._steps[at - 1] if at > 0 else None
        repeatable = action in notation.SLOT_ACTIONS or action == "dodge"
        if (prev is not None and repeatable and pos is None and prev.pos is None and prev.character_id == cid
                and prev.action == action and int(prev.repeat) < notation.MAX_STEP_REPEAT):
            self._steps[at - 1] = CustomStep(cid, action, None, int(prev.repeat) + 1)
            self._selected = at - 1
        else:
            self._steps.insert(at, CustomStep(cid, action, pos, 1, seconds))
            self._selected = at
        self._load_error = ""
        self._text_issues = ()
        self._model_changed()

    def add_wait(self, seconds: float) -> None:
        self.append_action("wait", None, round(float(seconds), 3))

    def select(self, index: int) -> None:
        self._selected = index if 0 <= index < len(self._steps) else -1
        self._render_chips()

    def move_selected(self, delta: int) -> None:
        i, j = self._selected, self._selected + int(delta)
        if not (0 <= i < len(self._steps)) or not (0 <= j < len(self._steps)) or self._text_blocks_edit():
            return
        self._steps[i], self._steps[j] = self._steps[j], self._steps[i]
        self._selected = j
        self._model_changed()

    def set_repeat(self, count: int) -> None:
        i = self._selected
        if not (0 <= i < len(self._steps)):
            return
        step = self._steps[i]
        if step.action in notation.ENTRY_ACTIONS or step.action == "wait":
            return
        count = max(1, min(notation.MAX_STEP_REPEAT, int(count)))
        if count != int(step.repeat) and self._text_blocks_edit():
            self._render_chips()            # puts the repeat box back to the step's count
            return
        if count != int(step.repeat):
            self._steps[i] = CustomStep(step.character_id, step.action, step.pos, count, step.seconds, step.raw)
            self._model_changed()

    def _on_repeat_spin(self, value: int) -> None:
        if not self._loading:
            self.set_repeat(value)

    def remove_selected(self) -> None:
        i = self._selected
        if 0 <= i < len(self._steps) and not self._text_blocks_edit():
            del self._steps[i]
            self._selected = min(i, len(self._steps) - 1)
            self._model_changed()

    def clear_steps(self) -> None:
        self._steps = []
        self._selected = -1
        self._load_error = ""
        self._text_issues = ()
        self._model_changed()

    def _validate(self) -> None:
        """Model errors: the static checks plus the action limit over all repeats."""
        self._model_errors, self._model_warnings = notation.check_steps(self._steps, self.team())
        if cycle.executed_actions(self._steps, self.repeat_count_spin.value()) > cycle.MAX_ACTIONS \
                and not any(issue.code == "too_long" for issue in self._model_errors):
            self._model_errors.append(notation.ParseIssue("too_long", (cycle.MAX_ACTIONS,)))

    def _model_changed(self, write_text: bool = True) -> None:
        self._validate()
        self._refresh_preview()
        self._render_chips()
        if write_text:
            self._write_text()
        self._refresh_messages()
        self.changed.emit()

    def _options_changed(self) -> None:
        if self._loading:
            return
        self._validate()
        self._refresh_preview()
        self._render_chips()
        self._refresh_messages()
        self.changed.emit()

    def _sync_wait_max(self) -> None:
        self.cd_wait_max_spin.setEnabled((self.resource_combo.currentData() or "warn") in ("wait", "strict"))

    def _awakening(self) -> dict:
        """{character id: team_awakening.AwakeningSel} of the member cards (cooldown rules unlocked by an awakening
        effect; review F-A, A12)."""
        out = {}
        for card in getattr(self._page, "cards", ()):
            try:
                out[int(card.character_combo.currentData())] = card.selection()
            except Exception:
                continue
        return out

    def on_awakening_changed(self) -> None:
        """A card's awakening changed: the preview's cooldown rules follow it."""
        self._refresh_preview()
        self._render_chips()
        self._refresh_messages()

    def _refresh_preview(self) -> None:
        if any(issue.code == "too_long" for issue in self._model_errors):
            self._preview = None            # not worth walking: the cycle cannot be calculated anyway
            return
        try:
            self._preview = cycle.preview_custom(self.team(), self._steps, self.options(),
                                                 awakening=self._awakening())
        except Exception:
            self._preview = None

    # ── chips ──────────────────────────────────────────────────────
    def _chip_text(self, index: int, step: CustomStep) -> str:
        from src.features.team_simulation.explanation_view import _circled

        text = f"{_circled(index + 1)} {notation.step_text(step, self._lang)}"
        prev = self._steps[index - 1] if index > 0 else None
        if prev is not None and prev.character_id != step.character_id and step.action not in notation.ENTRY_ACTIONS:
            text += f" ({view.token_text('swap', self._lang)})"      # an implicit plain swap
        return text

    def _chip_tip(self, index: int) -> str:
        traces = [t for t in (self._preview.steps if self._preview is not None else ())
                  if t.source_index == index and t.repeat_index == 0]
        lines = []
        names = self.team_names()
        for trace in traces:
            line = view.step_action_text(trace, self._lang)
            line = line + f" · {trace.start_s:.1f}s · " + _L('环合值') + f" {trace.gauge_after:.0f}"
            if trace.reaction_zh:
                line = line + " · " + trace.reaction_zh
            lines.append(line)
            for item in trace.notes:
                lines.append("  " + tx.note_text(item, names))
        for issue in self._model_errors:
            if int(issue.segment) == index + 1:
                lines.append(view.issue_text(issue, self._lang, with_segment=False))
        text = None
        for line in lines:
            text = line if text is None else text + "\n" + line
        return text or ""

    def _render_chips(self) -> None:
        self._clear_flow(self.chip_flow)
        self.chips: list[QPushButton] = []
        team = self.team()
        warned = set()
        for trace in (self._preview.steps if self._preview is not None else ()):
            if trace.warned and trace.source_index >= 0:
                warned.add(trace.source_index)
        bad = self._bad_indices()
        for index, step in enumerate(self._steps):
            color = self._slot_color(step.character_id)
            chip = QPushButton(self._chip_text(index, step))
            chip.setObjectName("teamSimCustomChip")
            chip.setCheckable(True)
            chip.setChecked(index == self._selected)
            chip.setCursor(Qt.PointingHandCursor)
            border = theme_color(ERROR_COLOR) if (index in bad or step.character_id not in team) else (
                theme_color(WARN_COLOR) if index in warned else theme_rgba(color, 0.55))
            chip.setStyleSheet(
                f"QPushButton#teamSimCustomChip{{background:{theme_rgba(color, 0.12)};color:{theme_color(color)};"
                f"border:1px solid {border};border-radius:4px;padding:3px 8px;font-size:12px;font-weight:700}}"
                f"QPushButton#teamSimCustomChip:checked{{background:{theme_rgba(color, 0.32)};"
                f"border:2px solid {border}}}")
            chip.setProperty("chipState", "error" if (index in bad or step.character_id not in team)
                             else ("warn" if index in warned else "ok"))
            tip = self._chip_tip(index)
            if tip:
                chip.setToolTip(tip)
            chip.clicked.connect(lambda _checked=False, i=index: self.select(i))
            self.chips.append(chip)
            self.chip_flow.addWidget(chip)
        self.chip_host.updateGeometry()
        selected = self._steps[self._selected] if 0 <= self._selected < len(self._steps) else None
        can_repeat = selected is not None and selected.action not in notation.ENTRY_ACTIONS \
            and selected.action != "wait"
        self._loading, was = True, self._loading
        self.repeat_spin.setValue(int(selected.repeat) if selected is not None else 1)
        self._loading = was
        self.repeat_spin.setEnabled(bool(can_repeat))
        self.prev_btn.setEnabled(selected is not None and self._selected > 0)
        self.next_btn.setEnabled(selected is not None and self._selected < len(self._steps) - 1)
        self.remove_btn.setEnabled(selected is not None)
        self.clear_btn.setEnabled(bool(self._steps))

    def _bad_indices(self) -> set:
        """Steps the validation rejects (member not in the team, entry on the field, missing slot ...)."""
        return {int(issue.segment) - 1 for issue in self._model_errors if int(issue.segment) > 0}

    # ── text box ───────────────────────────────────────────────────
    def text(self) -> str:
        return self.text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        """Replace the typed text (as if the user had typed it) and parse it at once."""
        self._put_text(text)
        self.apply_text_now()

    def _put_text(self, text: str) -> None:
        self._updating_text = True
        try:
            # QTextDocument is not patched by the display layer (QPlainTextEdit.setPlainText is)
            self.text_edit.document().setPlainText(text)
        finally:
            self._updating_text = False

    def _write_text(self) -> None:
        self._timer.stop()
        self._put_text(notation.format_steps(self._steps, self._lang))
        self._text_issues = ()
        self._underline(())

    def _on_text_changed(self) -> None:
        if not self._updating_text:
            self._timer.start()

    def apply_text_now(self) -> None:
        """Parse the text box: a valid text becomes the model, an invalid one keeps the last valid model."""
        self._timer.stop()
        text = self.text()
        parsed = notation.parse(text, self.team(), self._lang)
        if not text.strip():
            self._text_issues = ()
            self._steps, self._selected = [], -1
            self._load_error = ""
            self._underline(())
            self._model_changed(write_text=False)
            return
        if parsed.errors:
            self._text_issues = tuple(parsed.errors)
            self._underline(parsed.errors)
            self._refresh_messages()
            self.changed.emit()
            return
        self._text_issues = ()
        self._underline(())
        self._load_error = ""
        if tuple(parsed.steps) != tuple(self._steps):
            self._steps = list(parsed.steps)
            self._selected = len(self._steps) - 1
        self._model_changed(write_text=False)

    def tidy_text(self) -> None:
        self.apply_text_now()
        if not self._text_issues:
            self._write_text()

    def _underline(self, issues) -> None:
        selections = []
        for issue in issues:
            if issue.end <= issue.start:
                continue
            cursor = QTextCursor(self.text_edit.document())
            cursor.setPosition(int(issue.start))
            cursor.setPosition(int(issue.end), QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            fmt.setUnderlineColor(QColor(ERROR_COLOR))
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)
        self.text_edit.setExtraSelections(selections)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        try:
            if obj is self.text_edit and event.type() == QEvent.FocusOut:
                self.tidy_text()        # leaving the box with a valid text rewrites it in canonical form
        except RuntimeError:            # the page is being torn down
            pass
        return super().eventFilter(obj, event)

    # ── messages ───────────────────────────────────────────────────
    def first_error(self) -> str:
        if self._text_issues:
            return view.issue_text(self._text_issues[0], self._lang) + "  " + _L('输入有误，步骤保持上一次正确的内容。')
        if self._load_error:
            return self._load_error
        if self._model_errors:
            return view.issue_text(self._model_errors[0], self._lang, with_segment=False)
        return ""

    def is_valid(self) -> bool:
        return bool(self._steps) and not self._text_issues and not self._model_errors and not self._load_error

    def _refresh_messages(self) -> None:
        error = self.first_error()
        self.error_label.setText(("⚠ " + error) if error else "")
        self.error_label.setVisible(bool(error))
        if self._preview is not None and self._steps:
            count = sum(1 for t in self._preview.steps if t.source_index >= 0)
            self.summary.setText(_LF('预计 {0:.1f} 秒 · {1} 步 · 警告 {2} 条').format(
                float(self._preview.wall_time_s), count, int(self._preview.warnings)))
        else:
            self.summary.setText(_L('请先输入循环。') if not self._steps else "")

    # ── options ────────────────────────────────────────────────────
    def options(self) -> cycle.CustomOptions:
        team = self.team()
        resources = {}
        for slot, cid in enumerate(team):
            row = self.resource_spins[slot]
            eff = _optional_value(row["charge_eff"])
            resources[cid] = cycle.MemberResource(
                e_cd_s=_optional_value(row["e_cd_s"]), q_cd_s=_optional_value(row["q_cd_s"]),
                q_cost=_optional_value(row["q_cost"]), start_energy=_optional_value(row["start_energy"]),
                charge_eff=None if eff is None else eff / 100.0)
        options = cycle.CustomOptions(
            repeat=self.repeat_count_spin.value(),
            gauge_mode="check" if self.gauge_check.isChecked() else "as_typed",
            start_gauge={cid: float(self.gauge_spins[slot].value()) for slot, cid in enumerate(team)},
            gauge_reset_each_repeat=self.gauge_reset_box.isChecked(),
            resource_check=self.resource_combo.currentData() or "warn", resources=resources,
            disabled_buffs=frozenset(self._disabled_buffs),
            manual_buffs=tuple(row.buff() for row in self._manual_rows),
            target=cycle.TargetOptions(enemy_level=self.enemy_level_spin.value(),
                                       resistance=self.resistance_spin.value() / 100.0,
                                       defense_reduction=self.defense_spin.value() / 100.0,
                                       vulnerability=self.vulnerability_spin.value() / 100.0,
                                       boss=self.boss_box.isChecked(),
                                       enemy_count=self.enemy_count_spin.value()),
            swap_time_s=self.swap_time_spin.value(), resource_model=self._model(),
            cd_wait_max_s=_optional_value(self.cd_wait_max_spin))
        return cycle.normalise_options(options, team)

    def _model(self) -> str:
        """The page's resource model (team_resources): it decides the default cooldowns / costs."""
        getter = getattr(self._page, "resource_model", None)
        try:
            return getter() if callable(getter) else cycle.resource_model_of(None)
        except Exception:
            return cycle.resource_model_of(None)

    def on_resource_model_changed(self, model: str) -> None:
        """The page's model changed: fields still holding the old defaults follow the new ones."""
        team = self.team()
        old_model = getattr(self, "_defaults_model", None) or cycle.resource_model_of(None)
        was, self._loading = self._loading, True
        try:
            for slot, cid in enumerate(team):
                old = cycle.default_resources(cid, old_model)
                new = cycle.default_resources(cid, model)
                row = self.resource_spins[slot]
                for name in ("e_cd_s", "q_cd_s", "q_cost"):
                    if _optional_value(row[name]) == getattr(old, name):
                        _set_optional(row[name], getattr(new, name))
                self._set_resource_tips(slot)
        finally:
            self._loading = was
        self._defaults_model = model
        self._options_changed()

    def set_options(self, options: cycle.CustomOptions) -> None:
        team = self.team()
        options = cycle.normalise_options(options, team)
        self._loading = True
        try:
            self.repeat_count_spin.setValue(int(options.repeat))
            (self.gauge_check if options.gauge_mode == "check" else self.gauge_as_typed).setChecked(True)
            self.gauge_reset_box.setChecked(bool(options.gauge_reset_each_repeat))
            self.resource_combo.setCurrentIndex(max(0, self.resource_combo.findData(options.resource_check)))
            _set_optional(self.cd_wait_max_spin, getattr(options, "cd_wait_max_s", None))
            for slot, cid in enumerate(team):
                self.gauge_spins[slot].setValue(int(round(float(options.start_gauge.get(cid, 100.0)))))
                self._set_resource(slot, options.resources.get(cid) or cycle.default_resources(cid, self._model()))
            self._disabled_buffs = set(options.disabled_buffs)
            for row in list(self._manual_rows):
                self._remove_manual(row)
            for buff in options.manual_buffs:
                self.add_manual_buff(buff)
            self.enemy_level_spin.setValue(int(options.target.enemy_level))
            self.resistance_spin.setValue(options.target.resistance * 100.0)
            self.defense_spin.setValue(options.target.defense_reduction * 100.0)
            self.vulnerability_spin.setValue(options.target.vulnerability * 100.0)
            self.boss_box.setChecked(bool(getattr(options.target, "boss", False)))
            self.enemy_count_spin.setValue(int(getattr(options.target, "enemy_count", 1) or 1))
            self.swap_time_spin.setValue(float(options.swap_time_s))
        finally:
            self._loading = False
        self._render_inferred()
        self._options_changed()

    def _set_resource(self, slot: int, resource: cycle.MemberResource) -> None:
        row = self.resource_spins[slot]
        values = {"e_cd_s": resource.e_cd_s, "q_cd_s": resource.q_cd_s, "q_cost": resource.q_cost,
                  "start_energy": resource.start_energy,
                  "charge_eff": None if resource.charge_eff is None else resource.charge_eff * 100.0}
        for name, spin in row.items():
            _set_optional(spin, values[name])
        self._set_resource_tips(slot)

    def _set_resource_tips(self, slot: int) -> None:
        """Tooltips of a member's cooldown / energy fields: where the number comes from (team_resource_data cell:
        confidence + source, tooltip-only community values, measured bounds)."""
        from src.services import team_resources as tr
        from src.services import team_simulation_explanation as tx

        cid = self.team()[slot]
        model = self._model()
        if model == "legacy":
            from src.services import team_custom_actions as data

            from_data = data.RESOURCES.get(cid) or {}
            hints = data.RESOURCE_HINTS.get(cid) or {}
            for name, spin in self.resource_spins[slot].items():
                if name in from_data:
                    spin.setToolTip(_L('游戏数据'))
                elif name in hints:
                    spin.setToolTip(_LF('社区资料：{0}').format(f"{hints[name]:g}"))
                else:
                    spin.setToolTip(_L('留空则不检查'))
            return
        rec = tr.record(cid)
        policy = tr.policy_for(model)
        for name, spin in self.resource_spins[slot].items():
            lines = []
            if name in ("e_cd_s", "q_cd_s"):
                kind = "E" if name == "e_cd_s" else "Q"
                enforced = tr.cd_cell(cid, kind, policy)
                best = tr.best_cd_cell(cid, kind)
                cell = enforced or best
                tag = ""
                if cell is not None and cell[0] is not None:
                    tag = tr.source_tag(cell)
                    no_cd = float(cell[0]) == 0.0 and cell[2] in ("db_struct_none", "db_text")
                    shown = _L('无') if no_cd else f"{float(cell[0]):g}s"
                    lines.append(_LF('{0}：{1}').format(tx.confidence_label(cell[2]), shown) + (f" · {tag}" if tag else ""))
                for value, label, conf in (rec.get("cd_alt") or {}).get(kind, ()):
                    if cell is not None and label.split(" ")[0] == tag.split(" ")[0] and cell[0] == value:
                        continue                # the cell itself
                    lines.append(_LF('社区资料（可信度低）：{0}').format(f"{float(value):g}s · {label}"))
                bound = (rec.get("cd_bound") or {}).get(kind)
                if bound:
                    lines.append(_LF('实测上限 ≤ {0} 秒（不作为数值）').format(f"{float(bound[0]):g}"))
                rule_rows = list(rec.get("rules") or ())
                try:                        # awakening node rules' rows of the member (awakening_node_rules)
                    from src.services.awakening_node_rules import owner_of

                    owner = owner_of(cid)
                    rule_rows += list((owner.rules.get(int(cid)) or ()) if owner is not None else ())
                except Exception:
                    pass
                for code, rkind, _amount, level, _conf, _src in rule_rows:
                    if rkind == kind:       # applied when the card selects the node (review F-A; A12: the node)
                        from src.features.team_simulation.awakening_text import node_caption

                        lines.append(tx.cd_rule_text(code) + (f" ({node_caption(level)})" if level is not None else ""))
            elif name == "q_cost":
                energy = rec.get("energy") or {}
                cost = energy.get("cost")
                if cost and cost[0] is not None:
                    tag = tr.source_tag(cost)
                    lines.append(_LF('{0}：{1}').format(tx.confidence_label(cost[2]), f"{float(cost[0]):g}")
                                 + (f" · {tag}" if tag else ""))
                for value, label in energy.get("cost_display") or ():
                    lines.append(_LF('社区资料（可信度低）：{0}').format(f"{float(value):g} · {label}"))
            text = None
            for line in lines:
                text = line if text is None else text + "\n" + line
            spin.setToolTip(text or _L('留空则不检查'))

    def _reset_resources(self, slots) -> None:
        team = self.team()
        was, self._loading = self._loading, True
        try:
            for slot in slots:
                self._set_resource(slot, cycle.default_resources(team[slot], self._model()))
            self._defaults_model = self._model()
        finally:
            self._loading = was
        self._options_changed()

    def add_manual_buff(self, buff: cycle.ManualBuff | None = None) -> _ManualBuffRow:
        row = _ManualBuffRow(self)
        if buff is not None:
            row.set_buff(buff)
        row.removed.connect(self._remove_manual)
        self._manual_rows.append(row)
        self.manual_col.addWidget(row)
        return row

    def _remove_manual(self, row) -> None:
        if row in self._manual_rows:
            self._manual_rows.remove(row)
            self.manual_col.removeWidget(row)
            row.setParent(None)
            row.deleteLater()

    # inferred buffs (known after a run)
    def set_result_buffs(self, buffs) -> None:
        self._result_buffs = [dict(b) for b in (buffs or ()) if not b.get("manual")]
        self._render_inferred()

    def _render_inferred(self) -> None:
        while self.inferred_col.count():
            item = self.inferred_col.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:           # keep the reference: setParent(None) can free an unreferenced widget
                widget.setParent(None)
                widget.deleteLater()
        self.buff_boxes: list[QCheckBox] = []
        names = self.team_names()
        listed = set()
        for buff in self._result_buffs:
            source = buff.get("source_character_id")
            if source not in names:         # the last run's member is no longer on the cards
                names[source] = (self._page.template(source) or {}).get("name_zh") or str(source)
            keys = tuple(buff.get("keys") or (buff.get("key"),))
            listed.update(keys)
            box = QCheckBox()
            box.setText(self._page.buff_line(buff, names))
            box.setChecked(not all(k in self._disabled_buffs for k in keys))
            box.setProperty("buffKeys", list(keys))
            box.toggled.connect(lambda checked, ks=keys: self._toggle_buff(ks, checked))
            self.buff_boxes.append(box)
            self.inferred_col.addWidget(box)
        for key in sorted(self._disabled_buffs - listed):       # switched off earlier, not produced by the last run
            box = QCheckBox(str(key))
            box.setChecked(False)
            box.setStyleSheet(themed_style("color:#6e7681"))
            box.setProperty("buffKeys", [key])
            box.toggled.connect(lambda checked, ks=(key,): self._toggle_buff(ks, checked))
            self.buff_boxes.append(box)
            self.inferred_col.addWidget(box)
        if not self.buff_boxes:
            self.inferred_col.addWidget(_caption(_L('计算一次后可在此开关各 Buff。')))

    def _toggle_buff(self, keys, checked: bool) -> None:
        for key in keys:
            if checked:
                self._disabled_buffs.discard(key)
            else:
                self._disabled_buffs.add(key)
        for box in getattr(self, "buff_boxes", ()):     # two listed lines can share one buff key
            keys_of = box.property("buffKeys") or []
            box.blockSignals(True)
            box.setChecked(not all(k in self._disabled_buffs for k in keys_of))
            box.blockSignals(False)

    # ── team / language changes ────────────────────────────────────
    def on_team_changed(self) -> None:
        """A member card changed its character: relabel, reset that slot's numbers, re-validate the model."""
        team = self.team()
        changed = [slot for slot, cid in enumerate(team)
                   if slot >= len(self._team_cache) or self._team_cache[slot] != cid]
        self._team_cache = list(team)
        self._refresh_members()
        if changed:
            self._reset_resources(changed)
        self._rebuild_palette()
        self._render_inferred()
        self._model_changed(write_text=not self._text_issues)

    def retranslate(self) -> None:
        """Language switch: tokens and names are rebuilt from codes; a valid text is regenerated in the new
        language, a text with errors is kept exactly as typed (the parser accepts every language)."""
        self._lang = view.current_lang()
        self._refresh_entry_row()
        self._rebuild_palette()
        self._refresh_members()
        self._on_options_toggled(self.options_toggle.isChecked())
        self._retranslate_tooltips()
        if self._text_issues:
            self._render_chips()
            self._refresh_messages()
        else:
            self._model_changed()
        self._render_inferred()

    def _retranslate_tooltips(self) -> None:
        """The display layer re-renders texts on a language switch but not tooltips (they are translated when
        set): the fixed tooltips of the panel are set again."""
        self.prev_btn.setToolTip(_L('前移'))
        self.next_btn.setToolTip(_L('后移'))
        self.repeat_spin.setToolTip(_L('重复执行'))
        self.gauge_as_typed.setToolTip(_L('援护始终按输入以援护技登场；环合值不足 100 时在该步骤显示警告。'))
        self.gauge_check.setToolTip(_L('环合值不足 100 或属性不相邻时，援护改为普通切换。'))
        self.cd_wait_max_spin.setToolTip(_L('留空：插入等待不限时，严格最多 60 秒；仅对插入等待/严格有效'))
        # boss / enemy count (awakening node rules): tooltips set again on a language switch
        self.boss_box.setToolTip(_L('觉醒效果的首领条件按此判断（例如浮空、压制对首领无效）'))
        self.enemy_count_spin.setToolTip(_L('觉醒效果的「单个敌人」条件按此判断；伤害仍按一个目标计算'))
        for slot in range(len(self.resource_spins)):
            self._set_resource_tips(slot)
        for row in self._manual_rows:
            row.retranslate()

    # ── persistence ────────────────────────────────────────────────
    def cycle_dict(self) -> dict:
        """The working state as stored JSON: team (member cards), steps, options."""
        return {"team": self._page.team_json(), "steps": notation.steps_to_json(self._steps),
                "options": cycle.options_to_json(self.options())}

    def apply_cycle(self, entry: dict, *, set_team: bool = True) -> None:
        """Load a stored cycle; never raises (unknown steps are reported, numbers clamped)."""
        if set_team and entry.get("team"):
            self._page.apply_team(entry.get("team") or ())
            self._team_cache = self.team()
            self._refresh_members()
            self._rebuild_palette()
        steps, bad = notation.steps_from_json(entry.get("steps") or ())
        self.set_options(cycle.options_from_json(entry.get("options") or {}, self.team()))
        self._steps = list(steps)
        self._selected = len(self._steps) - 1
        self._text_issues = ()
        self._load_error = ""
        if bad:
            first = bad[0].get("a") if isinstance(bad[0], dict) else bad[0]
            self._load_error = _LF('未知的动作标识 [{0}]。').format(str(first))
        self._model_changed()

    def reload_store(self) -> None:
        """Read the account's cycle file again (page build, account switch)."""
        path = self._page.custom_store_path()
        if path != self._store_path:        # another account: its own names, its own notices
            self._current_name, self._moved_aside = "", ""
        self._store_path = path
        self._file = store.load(self._store_path) if self._store_path is not None else store.CycleFile()
        if self._file.moved_aside:          # remembered: the next load finds no file and has nothing to report
            self._moved_aside = self._file.moved_aside
        self._fill_saved()
        if self._file.read_only:
            self.status_message.emit(_L('该文件由更新的版本保存，只能读取。'))
        elif self._moved_aside:
            self.status_message.emit(view.moved_aside_text(self._moved_aside))

    def _fill_saved(self) -> None:
        wanted = self._current_name
        self.saved_combo.blockSignals(True)
        self.saved_combo.clear()
        for name in self._file.names():
            self.saved_combo.addItem(name, name)        # the real name is the item data
        index = self.saved_combo.findData(wanted)
        if index >= 0:
            self.saved_combo.setCurrentIndex(index)
        self.saved_combo.blockSignals(False)
        writable = self._store_path is not None and not self._file.read_only
        for button in (self.save_btn, self.save_as_btn, self.delete_btn):
            button.setEnabled(writable)
        self.load_btn.setEnabled(bool(self._file.cycles))

    def saved_names(self) -> list[str]:
        return self._file.names()

    def save_as(self, name: str) -> bool:
        if self._store_path is None:
            self.status_message.emit(_LF('保存失败：{0}').format("no account folder"))
            return False
        try:
            entry = dict(self.cycle_dict(), name=store.clean_name(name))
            self._file = store.save_cycle(self._store_path, entry)
        except store.StoreReadOnly:
            self.status_message.emit(_L('该文件由更新的版本保存，只能读取。'))
            return False
        except (OSError, ValueError) as error:
            self.status_message.emit(_LF('保存失败：{0}').format(str(error)))
            return False
        self._current_name = entry["name"]
        self._fill_saved()
        self.status_message.emit(_LF('已保存：{0}').format(entry["name"]))
        return True

    def load(self, name: str) -> bool:
        entry = self._file.get(name)
        if entry is None:
            return False
        self._current_name = name
        self.apply_cycle(entry, set_team=True)
        self._fill_saved()
        return True

    def delete(self, name: str) -> bool:
        if self._store_path is None or name not in self._file.names():
            return False
        try:
            self._file = store.delete_cycle(self._store_path, name)
        except store.StoreReadOnly:
            self.status_message.emit(_L('该文件由更新的版本保存，只能读取。'))
            return False
        except OSError as error:
            self.status_message.emit(_LF('保存失败：{0}').format(str(error)))
            return False
        if self._current_name == name:
            self._current_name = ""
        self._fill_saved()
        self.status_message.emit(_LF('已删除：{0}').format(name))
        return True

    def save_last(self, mode: str) -> bool:
        """Store the working state (called on every calculation); a failure is not fatal."""
        if self._store_path is None or self._file.read_only:
            return False
        try:
            self._file = store.save_last(self._store_path, {"mode": mode, "cycle": self.cycle_dict()})
        except (OSError, store.StoreReadOnly):
            return False
        return True

    def restore_last(self) -> str:
        """Apply the stored working state; returns its mode ("" when there is none)."""
        last = self._file.last
        if not isinstance(last, dict) or not isinstance(last.get("cycle"), dict):
            return ""
        self.apply_cycle(last["cycle"], set_team=True)
        return str(last.get("mode") or "")

    def _on_save(self) -> None:
        if self._current_name:
            self.save_as(self._current_name)
        else:
            self._on_save_as()

    def _on_save_as(self) -> None:
        name, ok = QInputDialog.getText(self, _L('另存为…'), _L('循环名称'), text=self._current_name)
        if not ok:
            return
        try:
            name = store.clean_name(name)
        except ValueError as error:
            self.status_message.emit(_LF('保存失败：{0}').format(str(error)))
            return
        if name in self._file.names() and name != self._current_name:
            answer = QMessageBox.question(self, _L('另存为…'), _LF('已存在同名循环「{0}」，是否覆盖？').format(name))
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.save_as(name)

    def _on_load(self) -> None:
        name = self.saved_combo.currentData()
        if name:
            self.load(str(name))

    def _on_delete(self) -> None:
        name = self.saved_combo.currentData()
        if not name:
            return
        answer = QMessageBox.question(self, _L('删除'), _LF('确定删除循环「{0}」吗？').format(str(name)))
        if answer == QMessageBox.StandardButton.Yes:
            self.delete(str(name))
