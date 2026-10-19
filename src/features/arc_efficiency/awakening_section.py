# 角色觉醒（韩文界面「돌파」）效率表区块：位于弧盘效率表页面下方，按单人循环 DPS 变化显示每个觉醒效果、共鸣与全部觉醒。
"""Character awakening efficiency section (Global; Korean UI "돌파 효율"), under the arc efficiency table.

Rows: every character with a graduation template and an approved rotation (the arc table's eleven first).  Columns:
awakening effects ①-⑥, resonance 3, resonance 6, all six (+ the A0 / A6 damage when the page shows damage).  Cells:
DPS change in % (``awakening_efficiency_service.build_matrix``) for the basis "add one" (awakening 0 + that effect,
default) or "remove one" (all six without it); a node the simulator does not price shows its class instead (team
only, needs measurement, not computable, under review, upper bound) - never 0 %.  Loops and the graduation
template's Puka Boot Camp level follow the arc table above (``set_context``); the basis, the collapsed state and the
splitter sizes are kept in ``<config>/awakening_efficiency_preferences.json``.

Layers as the arc table: precomputed seed, this PC's cache, or a background recomputation (WorkerThread, the
selected character first, cancel within one run; the arc service's computation lock is shared).  Nothing is read
while the page is built: the first show of the (expanded) section loads the catalog.  All text goes through
_L() / _LF(); game names and descriptions stay Chinese pieces for the display layer; a language switch re-renders.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.app.theme import theme_color, theme_rgba, themed_style
from src.app.workers import WorkerThread
from src.features.arc_efficiency.table_view import KEY_ROLE, SORT_ROLE, ArcTable, SortItem
from src.services import arc_efficiency_service as aes
from src.services import awakening_efficiency_notes as notes
from src.services import awakening_efficiency_service as awk
from src.services import team_awakening as ta

COL_CHAR = 0
COLUMN_OF = {node: i + 1 for i, node in enumerate(awk.COLUMNS)}       # Effect1..6 -> 1..6, R3 7, R6 8, full 9
COL_FULL = COLUMN_OF["full"]
COL_D0, COL_D6 = COL_FULL + 1, COL_FULL + 2
POSITIVE = "#3fb950"
NEGATIVE = "#f85149"
MUTED = "#8b949e"
CLASS_COLORS = {
    awk.CLASS_EXPECTED: "#d2a8ff",
    awk.CLASS_TEAM: "#58a6ff",
    awk.CLASS_MEASURE: "#e3b341",
    awk.CLASS_NOT_COMPUTABLE: MUTED,
    awk.CLASS_REVIEW: "#e3b341",
    awk.CLASS_BOUND: "#d2a8ff",
}
UNPRICED = (awk.CLASS_MEASURE, awk.CLASS_REVIEW, awk.CLASS_BOUND)


def _tr(text):
    from src.i18n_display import tr

    return tr(text)


def _language() -> str:
    try:
        from src import i18n_runtime

        return str(i18n_runtime.get_language() or "zh")
    except Exception:
        return "zh"


def _lines(pieces) -> str:
    out = None
    for piece in pieces:
        if piece is None or piece == "":
            continue
        out = piece if out is None else out + "\n" + piece
    return out if out is not None else ""


def _toggle_button(text) -> QPushButton:
    button = QPushButton(text)
    button.setCheckable(True)
    button.setMinimumHeight(26)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(themed_style(
        "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
        "padding:2px 10px;font-weight:700}"
        "QPushButton:checked{background:#4f46e5;color:white;border-color:#4f46e5}"))
    return button


# ── texts (language of the moment) ────────────────────────────────────────────

def class_label(cls: str):
    """Short cell label of a class that shows no number."""
    return {
        awk.CLASS_EXPECTED: _L('期望值'),
        awk.CLASS_TEAM: _L('仅队伍'),
        awk.CLASS_MEASURE: _L('需要实测'),
        awk.CLASS_NOT_COMPUTABLE: _L('无法计算'),
        awk.CLASS_REVIEW: _L('⚠ 审核中'),
        awk.CLASS_BOUND: _L('上限值'),
    }.get(cls, cls)


def class_explanation(cls: str):
    return {
        awk.CLASS_DAMAGE: _L('伤害：单人模拟中计算的 DPS 变化'),
        awk.CLASS_EXPECTED: _L('期望值：模拟器无法再现该条件，按期望值计算'),
        awk.CLASS_TEAM: _L('仅队伍：需要队友、环合反应、援护技入场或能量与冷却（在队伍模拟中计算），单人为 0'),
        awk.CLASS_MEASURE: _L('需要实测：计算器尚未计入（不是 0%）'),
        awk.CLASS_NOT_COMPUTABLE: _L('无法计算：在木桩单人模拟中不改变伤害（治疗、生存、击败、受击、倾陷、多目标等）'),
        awk.CLASS_REVIEW: _L('审核中：模型待确认，数值只在提示中显示'),
        awk.CLASS_BOUND: _L('上限值：只能给出上限（≤）'),
    }.get(cls, cls)


def basis_label(basis: str):
    return _L('只加一个') if basis == "add_one" else _L('从全部觉醒中去掉一个')


def pct_text(value: float) -> str:
    """"+x.x%" for |x| >= 0.05, "≈0" below (never "+0.0%")."""
    if value is None:
        return "…"
    if abs(value) < awk.ZERO_PCT:
        return "≈0"
    return f"{value:+.1f}%"


def cell_display(cell: awk.Cell, basis: str) -> tuple:
    """(text, colour or None, sort value or None) of one cell."""
    if cell.pending:
        return "…", None, None
    value = cell.value
    reference = notes.reference_value(cell.reference, basis, cell.loops) if cell.reference else None
    if cell.cls in awk.NUMERIC_CLASSES or cell.column == "full":
        if value.pct is None:
            return "–", MUTED, None
        text = pct_text(value.pct)
        if value.shown and value.time_changed:
            text = "⏱" + text
        if cell.cls == awk.CLASS_EXPECTED and value.shown:
            text = text + " (" + class_label(awk.CLASS_EXPECTED) + ")"
        if cell.partial_nodes and value.shown:
            text = text + "*"
        if cell.mismatch:
            text = text + "?"
        colour = CLASS_COLORS.get(awk.CLASS_EXPECTED) if cell.cls == awk.CLASS_EXPECTED else (
            MUTED if not value.shown else (POSITIVE if value.pct > 0 else NEGATIVE))
        return text, colour, value.pct
    if cell.column == "resonance_3" and value.shown:          # the skill level +1 part is always priced
        text = ("⏱" if value.time_changed else "") + pct_text(value.pct)
        if cell.cls in UNPRICED:
            text = text + "*"
        return text, (POSITIVE if value.pct > 0 else NEGATIVE), value.pct
    if cell.mismatch and value.shown:                         # the class says "not priced" but a number moved
        return pct_text(value.pct) + "?", CLASS_COLORS.get(cell.cls), value.pct
    if cell.cls == awk.CLASS_BOUND and reference is not None and not isinstance(reference, tuple):
        return "≤ " + notes.format_value(reference), CLASS_COLORS[awk.CLASS_BOUND], None
    return class_label(cell.cls), CLASS_COLORS.get(cell.cls, MUTED), None


def legend_text():
    pieces = [
        "⏱ " + _L('循环时长改变（按 DPS 比较）'),
        "* " + _L('部分效果未计入（需要实测 / 审核中 / 上限值）'),
        "≈0 " + _L('变化小于 0.05%'),
        "? " + _L('分类需要确认'),
        "ⓘ " + _L('行备注'),
    ]
    for cls in (awk.CLASS_EXPECTED, awk.CLASS_TEAM, awk.CLASS_MEASURE, awk.CLASS_NOT_COMPUTABLE, awk.CLASS_REVIEW,
                awk.CLASS_BOUND):
        pieces.append(class_explanation(cls))
    out = None
    for piece in pieces:
        out = piece if out is None else out + "   " + piece
    return out


# ── the section ───────────────────────────────────────────────────────────────

class AwakeningEfficiencySection(QFrame):
    """The 돌파 efficiency table under the arc table (see the module docstring)."""

    character_activated = Signal(int)       # a row was clicked (the page selects the character above when it can)
    collapsed_changed = Signal(bool)

    def __init__(self, static_path, config_dir=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("awakenEffSection")
        self._static_path = Path(static_path)
        self._cache = awk.Cache(Path(config_dir) / awk.CACHE_FILE if config_dir else None)
        self._prefs_path = Path(config_dir) / awk.PREFERENCES_FILE if config_dir else None
        self._prefs = awk.load_preferences(self._prefs_path)
        self._loops = awk.DEFAULT_LOOPS
        self._template_level = 0
        self._show_damage = False
        self._selected: int | None = None       # highlighted row (the arc table's choice or a click here)
        self._page_selected: int | None = None  # the arc table's selected character as last handed over
        self._loaded = False
        self._load_error = ""
        self._catalog: list = []
        self._entries: dict = {}
        self._node_texts: dict | None = None
        self._fork_names: dict = {}
        self._states: dict = {}                 # template level -> rows / sources / stamps / failed / resolved / identity
        self._worker = None
        self._computation = None
        self._computation_key = None            # (loops, template level) of the running computation
        self._generation = 0
        self._paused = False
        self._sort = None                       # (column, ascending) or None = the default order
        self._shown: list = []                  # MatrixRow per table row
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(60)
        self._refresh_timer.timeout.connect(self._render)
        self._build()
        try:
            from src import i18n_runtime

            i18n_runtime.add_listener(lambda _code: self._on_language_changed())
        except Exception:
            pass
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(lambda: self.stop_computation(wait_ms=3000))

    # ── skeleton (no data access) ─────────────────────────────────────────
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 6, 0, 0)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel()
        self.title.setObjectName("awakenEffTitle")
        self.title.setStyleSheet(themed_style("font-size:16px;font-weight:800;color:#f0f6fc"))
        head.addWidget(self.title)
        head.addStretch()
        self.source_label = QLabel()
        self.source_label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        head.addWidget(self.source_label)
        self.collapse_btn = QPushButton()
        self.collapse_btn.setObjectName("awakenEffCollapse")
        self.collapse_btn.setCheckable(True)
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.setStyleSheet(themed_style(
            "QPushButton{background:transparent;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
            "padding:2px 10px;font-weight:700}"))
        self.collapse_btn.toggled.connect(self._on_collapse)
        head.addWidget(self.collapse_btn)
        outer.addLayout(head)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        body.addWidget(self.subtitle)
        options = QHBoxLayout()
        options.setSpacing(8)
        self.basis_caption = QLabel()
        self.basis_caption.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        options.addWidget(self.basis_caption)
        self.basis_group = QButtonGroup(self)
        self.basis_buttons = {}
        for index, basis in enumerate(awk.BASES):
            button = _toggle_button("")
            self.basis_group.addButton(button, index)
            self.basis_buttons[basis] = button
            options.addWidget(button)
        self.basis_group.idClicked.connect(self._on_basis)
        options.addStretch()
        body.addLayout(options)
        self.table = ArcTable()
        self.table.setObjectName("awakenEffTable")
        self.table.setSelectionBehavior(ArcTable.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header)
        self.table.tooltip_provider = self.tooltip_for
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setMinimumHeight(120)
        body.addWidget(self.table, 1)
        self.legend = QLabel()
        self.legend.setWordWrap(True)
        self.legend.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
        body.addWidget(self.legend)
        status_row = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        status_row.addWidget(self.status, 1)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        status_row.addWidget(self.cancel_btn)
        body.addLayout(status_row)
        # review UX F1: the body scrolls inside the section, so a short splitter share never squeezes the table
        # under the legend and the section's minimum height stays small (the page keeps the arc table readable)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("awakenEffScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea#awakenEffScroll{background:transparent;border:none}")
        self.scroll.viewport().setAutoFillBackground(False)
        self.body.setAutoFillBackground(False)
        self.scroll.setWidget(self.body)
        self.scroll.setMinimumHeight(60)
        outer.addWidget(self.scroll, 1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._apply_static_texts()
        self._apply_collapsed(bool(self._prefs.get("collapsed")), save=False)

    def _apply_static_texts(self) -> None:
        self.title.setText(_L('角色觉醒效率 (Beta)'))
        self.subtitle.setText(_lines([
            _L('每个觉醒效果、共鸣与全部觉醒在单人已审核循环中带来的 DPS 变化（%）。'),
            _L('毕业模板、基准弧盘精炼 1（有专属弧盘时为专属弧盘，与上表 100% 相同）；循环轮数与噗卡特训设置跟随上方表格。'),
        ]))
        self.basis_caption.setText(_L('比较基准'))
        self.basis_buttons["add_one"].setText(_L('只加一个（觉醒 0 + 该效果）'))
        self.basis_buttons["remove_one"].setText(_L('从全部觉醒中去掉一个'))
        self.basis_buttons["add_one"].setToolTip(_L('觉醒 0 时只选择该效果，与觉醒 0 相比的 DPS 变化'))
        self.basis_buttons["remove_one"].setToolTip(_L('全部觉醒与去掉该效果（其余五个与共鸣保留）相比的 DPS 变化'))
        self.cancel_btn.setText(_L('取消'))
        self.legend.setText(legend_text())
        self._sync_collapse_text()
        self.basis_group.blockSignals(True)
        self.basis_buttons[self._prefs["basis"]].setChecked(True)
        self.basis_group.blockSignals(False)

    def _sync_collapse_text(self) -> None:
        collapsed = bool(self._prefs.get("collapsed"))
        self.collapse_btn.setText(_L('▼ 展开') if collapsed else _L('▲ 收起'))

    # ── page interface ───────────────────────────────────────────────────
    @property
    def collapsed(self) -> bool:
        return bool(self._prefs.get("collapsed"))

    def preferences(self) -> dict:
        return dict(self._prefs)

    def has_saved_preferences(self) -> bool:
        """The preferences file exists (the user has toggled, sorted the basis or moved the split before)."""
        try:
            return self._prefs_path is not None and Path(self._prefs_path).is_file()
        except OSError:
            return False

    def set_collapsed(self, collapsed: bool, save: bool = False) -> None:
        """Collapse / expand from the page (``save`` False: a default for a small page, not a user choice)."""
        if bool(collapsed) != self.collapsed:
            self._apply_collapsed(bool(collapsed), save=save)
            if collapsed:
                self.stop_computation()

    def collapsed_height(self) -> int:
        """Height of the collapsed section (the header row only)."""
        return int(self.title.sizeHint().height() + 24)

    def save_split(self, sizes) -> None:
        values = [int(v) for v in list(sizes)[:2]]
        if len(values) == 2 and all(v >= 0 for v in values) and not self.collapsed:
            self._prefs["split"] = values
            awk.save_preferences(self._prefs_path, self._prefs)

    def set_context(self, loops: int, template_level: int, show_damage: bool = False, selected: int | None = None
                    ) -> None:
        """The arc table's options (loops, template Puka level, damage columns) and its selected character."""
        loops, level = int(loops), int(template_level or 0)
        changed = (loops, level) != (self._loops, self._template_level)
        redraw = changed or bool(show_damage) != self._show_damage
        self._show_damage = bool(show_damage)
        if changed:
            self.stop_computation()
            self._loops, self._template_level = loops, level
            self._paused = False
            if self._loaded:
                self._resolve_all()
        if selected is not None and selected != self._page_selected:     # follow the arc table's selection changes
            self._page_selected = int(selected)
            self._selected = int(selected)
            if self._computation is not None:
                self._computation.prioritize(self._selected)
            if not redraw:
                self.highlight(self._selected)
        if redraw and self._loaded:
            self._render()
        if changed:
            self._maybe_start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self.collapsed:
            QTimer.singleShot(0, self._first_load)

    def _first_load(self) -> None:
        try:
            if not self.isVisible() or self.collapsed:
                return
            self.ensure_loaded()
            self._maybe_start()
        except RuntimeError:
            pass

    def ensure_loaded(self) -> None:
        """Catalog, identity and the layer decision of both loop counts (idempotent)."""
        if self._loaded:
            return
        self._loaded = True
        try:
            self._catalog = awk.order_entries(awk.eligible_characters(self._static_path))
            self._entries = {e.character_id: e for e in self._catalog}
            self._fork_names = awk.fork_names(self._static_path, {e.fork_id for e in self._catalog})
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._render()
            return
        self._resolve_all()
        self._render()

    def _state(self, level: int | None = None) -> dict:
        level = self._template_level if level is None else int(level)
        state = self._states.get(level)
        if state is None:
            state = {"rows": {}, "sources": {}, "stamps": {}, "failed": {}, "resolved": set(),
                     "identity": awk.current_identity(self._static_path, template_level=level)}
            self._states[level] = state
        return state

    def _resolve_all(self) -> None:
        for loops in awk.LOOP_CHOICES:
            self._resolve(loops)

    def _resolve(self, loops: int) -> None:
        state = self._state()
        if loops in state["resolved"] or not self._catalog:
            return
        state["resolved"].add(loops)
        result = awk.resolve(self._static_path, self._catalog, loops, self._cache, state["identity"])
        state["rows"].update(result.rows)
        for cid, source in result.sources.items():
            state["sources"][(cid, loops)] = source
        for cid, stamp in result.computed_at.items():
            state["stamps"][(cid, loops)] = stamp

    def node_texts(self) -> dict:
        """{cid: {node: effect row}} for the tooltips (read once, on the first tooltip)."""
        if self._node_texts is None:
            try:
                self._node_texts = awk.load_node_catalog(self._static_path, list(self._entries))
            except Exception:  # noqa: BLE001 - tooltips only
                self._node_texts = {}
        return self._node_texts

    # ── background recomputation ─────────────────────────────────────────
    def _stale(self) -> list[int]:
        sources = self._state()["sources"]
        return [e.character_id for e in self._catalog if sources.get((e.character_id, self._loops)) == aes.SOURCE_STALE]

    def computing(self) -> bool:
        return self._computation is not None and self._worker is not None and self._worker.isRunning()

    def _maybe_start(self) -> None:
        if not self._loaded or self.collapsed or self._paused or not self.isVisible():
            return
        if self._worker is not None and self._worker.isRunning():
            return
        stale = self._stale()
        if not stale:
            return
        state = self._state()
        loops, level = self._loops, self._template_level
        pending = {}
        for cid in stale:
            jobs = [v for v in awk.jobs_of(self._entries[cid]) if awk.row_key(cid, v, loops) not in state["rows"]]
            if jobs:
                pending[cid] = jobs
                state["sources"][(cid, loops)] = "computing"
        for cid in stale:
            if cid not in pending:                  # every row known (an interrupted run), the cache not saved
                self._finish_character(cid, loops, True, "", level)
        if not pending:
            self._render()
            return
        self._generation += 1
        generation = self._generation
        selected = self._selected if self._selected in pending else None
        order = ([selected] if selected is not None else []) + [c for c in stale if c in pending and c != selected]
        worker_ref: list = []

        def on_row(key, row) -> None:
            if worker_ref:
                worker_ref[0].progress.emit(("row", generation, key, row, level))

        def on_character(cid, ok, message) -> None:
            if worker_ref:
                worker_ref[0].progress.emit(("character", generation, cid, loops, ok, message, level))

        computation = awk.Computation(self._static_path, self._entries, loops, pending, self._cache,
                                      state["identity"], on_row=on_row, on_character=on_character, order=order,
                                      generation=generation)
        computation.prioritize(self._selected)
        self._computation = computation
        self._computation_key = (loops, level)
        worker = WorkerThread(computation.run, self)
        worker_ref.append(worker)
        worker.progress.connect(self._on_progress)
        worker.result_ready.connect(lambda _rows, g=generation: self._on_worker_done(g, ""))
        worker.error.connect(lambda message, g=generation: self._on_worker_done(g, message))
        self._worker = worker
        worker.start()
        self._render()

    def stop_computation(self, wait_ms: int = 0) -> None:
        if self._computation is not None:
            self._computation.cancel()
        if wait_ms and self._worker is not None:
            try:
                self._worker.wait(int(wait_ms))
            except RuntimeError:
                pass

    def _on_progress(self, payload) -> None:
        kind, generation, level = payload[0], payload[1], payload[-1]
        if generation != self._generation:
            return
        state = self._states.get(level)
        if state is None:
            return
        if kind == "row":
            _kind, _g, key, row, _level = payload
            state["rows"][key] = row
        elif kind == "character":
            _kind, _g, cid, loops, ok, message, _level = payload
            self._finish_character(cid, loops, ok, message, level)
        self._refresh_timer.start()

    def _finish_character(self, cid: int, loops: int, ok: bool, message: str, level: int) -> None:
        state = self._state(level)
        if ok:
            state["sources"][(cid, loops)] = aes.SOURCE_CACHE
            state["stamps"][(cid, loops)] = self._cache.computed_at(state["identity"], awk.row_key(cid, "A6", loops))
        else:
            state["sources"][(cid, loops)] = "failed"
            state["failed"][(cid, loops)] = message

    def _on_worker_done(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._computation = None
        loops, level = self._computation_key or (self._loops, self._template_level)
        sources = self._state(level)["sources"]
        for cid in self._entries:
            if sources.get((cid, loops)) == "computing":
                sources[(cid, loops)] = aes.SOURCE_STALE        # interrupted (cancel, loops / template switch)
        if message:
            self.status.setText(_LF('计算失败：{0}').format(message))
        self._render()
        if not self._paused:
            QTimer.singleShot(0, self._maybe_start)

    def _on_cancel(self) -> None:
        self._paused = True
        self.stop_computation()
        self._render()

    # ── options ─────────────────────────────────────────────────────────
    def _on_basis(self, index: int) -> None:
        self._prefs["basis"] = awk.BASES[index]
        awk.save_preferences(self._prefs_path, self._prefs)
        self._render()

    def set_basis(self, basis: str) -> None:
        if basis in awk.BASES:
            self.basis_buttons[basis].setChecked(True)
            self._on_basis(awk.BASES.index(basis))

    def _on_collapse(self, checked: bool) -> None:
        self._apply_collapsed(bool(checked), save=True)
        if not checked:
            QTimer.singleShot(0, self._first_load)
        else:
            self.stop_computation()

    def _apply_collapsed(self, collapsed: bool, save: bool) -> None:
        self._prefs["collapsed"] = bool(collapsed)
        self.collapse_btn.blockSignals(True)
        self.collapse_btn.setChecked(bool(collapsed))
        self.collapse_btn.blockSignals(False)
        self.scroll.setVisible(not collapsed)
        self.setMaximumHeight(self.collapsed_height() if collapsed else 16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed if collapsed else QSizePolicy.Expanding)
        self._sync_collapse_text()
        if save:
            awk.save_preferences(self._prefs_path, self._prefs)
        self.collapsed_changed.emit(bool(collapsed))

    def _on_header(self, column: int) -> None:
        if column == COL_CHAR and self._sort is None:
            return
        if self._sort is not None and self._sort[0] == column:
            self._sort = (column, not self._sort[1]) if column != COL_CHAR else None
        else:
            self._sort = (column, False)
        self._render_table()

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._shown):
            cid = self._shown[row].entry.character_id
            self._selected = cid
            self.highlight(cid)
            if self._computation is not None:
                self._computation.prioritize(cid)
            if self._paused and self._state()["sources"].get((cid, self._loops)) == aes.SOURCE_STALE:
                self._paused = False            # looking at a character that still needs numbers resumes the work
                QTimer.singleShot(0, self._maybe_start)
            self.character_activated.emit(cid)

    def highlight(self, cid: int | None) -> None:
        index = next((i for i, m in enumerate(self._shown) if m.entry.character_id == cid), -1)
        if index < 0:
            return
        self.table.blockSignals(True)
        self.table.setCurrentCell(index, max(0, self.table.currentColumn()))
        self.table.blockSignals(False)
        item = self.table.item(index, COL_CHAR)
        if item is not None:
            self.table.scrollToItem(item)

    # ── rendering ───────────────────────────────────────────────────────
    def _on_language_changed(self) -> None:
        try:
            self._apply_static_texts()
            self._render()
        except RuntimeError:
            pass

    def matrix(self, loops: int | None = None, basis: str | None = None) -> list:
        """MatrixRow of every character in the default order (catalog order)."""
        rows = self._state()["rows"]
        loops = self._loops if loops is None else int(loops)
        basis = basis or self._prefs["basis"]
        return [awk.build_matrix(entry, rows, loops, basis) for entry in self._catalog]

    def _sorted(self, matrix: list) -> list:
        if self._sort is None:
            return matrix
        column, ascending = self._sort
        basis = self._prefs["basis"]

        def key(m):
            if column in (COL_D0, COL_D6):
                row = m.a0 if column == COL_D0 else m.a6
                value = row.damage if row is not None else None
            else:
                name = next((n for n, c in COLUMN_OF.items() if c == column), None)
                cell = m.cells.get(name)
                value = cell_display(cell, basis)[2] if cell is not None else None
            return (value is None, (value if value is not None else 0.0) * (1 if ascending else -1),
                    m.entry.character_id)

        return sorted(matrix, key=key)

    def _render(self) -> None:
        if self._load_error:
            self.status.setText(_LF('加载失败：{0}').format(self._load_error))
            return
        if not self._loaded:
            return
        self._render_table()
        self._render_status()

    def _headers(self) -> list:
        labels = [_L('角色')] + [ta.circled(n) for n in awk.NODES] + [
            _LF('共鸣{0}').format(3), _LF('共鸣{0}').format(6), _L('全部觉醒')]
        if self._show_damage:
            labels += [_L('觉醒 0 伤害'), _L('全部觉醒伤害')]
        return labels

    def _render_table(self) -> None:
        widget = self.table
        keep = self._selected
        basis = self._prefs["basis"]
        matrix = self._sorted(self.matrix())
        self._shown = matrix
        headers = self._headers()
        widget.clearContents()
        widget.setColumnCount(len(headers))
        widget.setHorizontalHeaderLabels(headers)
        for column, tip in self._header_tips().items():
            item = widget.horizontalHeaderItem(column)
            if item is not None:
                item.setToolTip(tip)
        widget.setRowCount(len(matrix))
        for i, m in enumerate(matrix):
            self._fill_row(i, m, basis)
        header = widget.horizontalHeader()
        if self._sort is not None:
            header.setSortIndicator(self._sort[0], Qt.AscendingOrder if self._sort[1] else Qt.DescendingOrder)
        else:
            header.setSortIndicator(-1, Qt.AscendingOrder)
        widget.resizeColumnsToContents()
        if keep is not None:
            self.highlight(keep)

    def _header_tips(self) -> dict:
        tips = {}
        for node in awk.NODES:
            tips[COLUMN_OF[node]] = _LF('觉醒效果 {0}（每个角色不同：名称与说明见单元格提示）').format(ta.circled(node)) \
                + "\n" + basis_label(self._prefs["basis"])
        tips[COLUMN_OF["resonance_3"]] = _L('共鸣3：觉醒 3 次时生效（与所选效果无关）：技能等级 +1 与共鸣效果，相对觉醒 0；两种基准相同')
        tips[COLUMN_OF["resonance_6"]] = _L('共鸣6：觉醒 6 次时生效（与所选效果无关），相对觉醒 3 次（只有共鸣3）；两种基准相同')
        tips[COL_FULL] = _L('全部觉醒（毕业模板的 6 个效果与两个共鸣）相对觉醒 0；两种基准相同')
        return tips

    def _item(self, text, sort=None, align=Qt.AlignVCenter | Qt.AlignRight) -> SortItem:
        item = SortItem(text)
        item.setData(SORT_ROLE, sort)
        item.setTextAlignment(int(align))
        return item

    def _fill_row(self, i: int, m: awk.MatrixRow, basis: str) -> None:
        widget = self.table
        cid = m.entry.character_id
        badges = self._badges(m.entry)
        name = self._item(m.entry.name_zh + (" ⓘ" if badges else ""), m.entry.character_id,
                          Qt.AlignVCenter | Qt.AlignLeft)
        if m.entry.exclusive:
            font = QFont(name.font())
            font.setBold(True)
            name.setFont(font)
        name.setData(KEY_ROLE, (cid, "name"))
        widget.setItem(i, COL_CHAR, name)
        for column_name, column in COLUMN_OF.items():
            cell = m.cells.get(column_name)
            if cell is None:
                continue
            text, colour, sort = cell_display(cell, basis)
            item = self._item(text, sort, Qt.AlignVCenter | Qt.AlignHCenter)
            if colour:
                item.setForeground(QBrush(QColor(theme_color(colour))))
            if column_name == "full":
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            item.setData(KEY_ROLE, (cid, column_name))
            widget.setItem(i, column, item)
        if self._show_damage:
            for column, row in ((COL_D0, m.a0), (COL_D6, m.a6)):
                item = self._item(f"{row.damage:,.1f}" if row is not None else "…", row.damage if row else None)
                item.setData(KEY_ROLE, (cid, "damage"))
                widget.setItem(i, column, item)

    def _badges(self, entry: awk.AwakeningEntry) -> list:
        out = []
        cid = entry.character_id
        if any(getattr(awk.node_info(cid, n), "pre_release", False) for n in awk.NODES + awk.RESONANCES):
            note = None
            try:
                from src.services import global_live_overlay

                note = global_live_overlay.unverified_note(self._static_path)
            except Exception:
                note = None
            out.append(note or _L('上线前数据（9-24），数值可能与正式版不同'))
        for code in notes.BADGES.get(cid, ()):
            out.append(notes.badge_text(code))
        return out

    def _render_status(self) -> None:
        state = self._state()
        loops = self._loops
        sources = [state["sources"].get((e.character_id, loops)) for e in self._catalog]
        computing = self.computing()
        self.cancel_btn.setVisible(computing)
        identity = state["identity"]
        head, _sep, tail = str(identity.dataset_id or "").rpartition("_")
        dataset = head if head and len(tail) == 8 else str(identity.dataset_id or "")
        if sources and all(s == aes.SOURCE_SEED for s in sources):
            self.source_label.setText(_LF('预先计算的结果（数据 {0}）').format(dataset))
        elif sources and all(s in (aes.SOURCE_SEED, aes.SOURCE_CACHE) for s in sources):
            stamps = [v for (c, lp), v in state["stamps"].items() if lp == loops and v]
            self.source_label.setText(_LF('本机计算的结果（{0}）').format(max(stamps) if stamps else dataset))
        else:
            self.source_label.setText("")
        if computing:
            total = done = 0
            for e in self._catalog:
                if state["sources"].get((e.character_id, loops)) in ("computing", aes.SOURCE_STALE):
                    jobs = awk.jobs_of(e)
                    total += len(jobs)
                    done += sum(1 for v in jobs if awk.row_key(e.character_id, v, loops) in state["rows"])
            self.status.setText(_LF('数据已变更，正在重新计算…（{0}/{1}）').format(done, total))
        elif "failed" in sources:
            failed = [e.name_zh for e in self._catalog if state["sources"].get((e.character_id, loops)) == "failed"]
            self.status.setText(_LF('计算失败：{0}').format("、".join(str(_tr(n)) for n in failed)))
        elif aes.SOURCE_STALE in sources:
            self.status.setText(_L('等待计算'))
        else:
            self.status.setText("")

    # ── tooltips ────────────────────────────────────────────────────────
    def tooltip_for(self, r: int, c: int) -> str | None:
        """Tooltip of a cell in the active language (game names translated once, here)."""
        if not (0 <= r < len(self._shown)):
            return None
        m = self._shown[r]
        if c == COL_CHAR:
            return self._character_tooltip(m)
        name = next((n for n, col in COLUMN_OF.items() if col == c), None)
        if name is None:
            if c in (COL_D0, COL_D6):
                return _LF('{0} 轮 · 循环 {1} 秒（不含时停）').format(
                    m.loops, f"{(m.a6 or m.a0).active_us / 1e6:.1f}" if (m.a6 or m.a0) else "…")
            return None
        cell = m.cells.get(name)
        if cell is None:
            return None
        if name == "full":
            return self._full_tooltip(m, cell)
        return self._node_tooltip(m, cell)

    def _effect(self, cid: int, node: str) -> dict:
        return (self.node_texts().get(int(cid)) or {}).get(node) or {}

    def _node_title(self, cid: int, node: str) -> str:
        effect = self._effect(cid, node)
        title = str(_tr(str(effect.get("title_zh") or ""))) if effect.get("title_zh") else ""
        if node in awk.RESONANCES:
            caption = _LF('共鸣{0}').format(int(node[-1]))
        else:
            caption = _LF('觉醒效果 {0}').format(ta.circled(node))
        return f"{caption}「{title}」" if title else str(caption)

    def _values_line(self, m: awk.MatrixRow, cell: awk.Cell, basis: str) -> str:
        """"<basis>: 1 loop +x% · 3 loops +y%" from the rows known now."""
        rows = self._state()["rows"]
        parts = []
        for loops in sorted(awk.LOOP_CHOICES):
            other = awk.build_matrix(m.entry, rows, loops, basis).cells.get(cell.column)
            if other is None or other.pending or other.value.pct is None:
                continue
            parts.append(_LF('{0} 轮 {1}').format(loops, pct_text(other.value.pct)))
        return (basis_label(basis) + ": " + " · ".join(parts)) if parts else ""

    def _node_tooltip(self, m: awk.MatrixRow, cell: awk.Cell) -> str:
        from src.features.team_simulation.awakening_text import description, info_lines

        cid = m.entry.character_id
        lines = [str(_tr(m.entry.name_zh)) + " · " + self._node_title(cid, cell.column)]
        effect = self._effect(cid, cell.column)
        text = description(effect) if effect else ""
        if text:
            lines.append(text)
        info = cell.info
        # the class line, unless the node rules' own mark already says it (needs measuring / not computable /
        # expected value - review UX F10: Mint ⑥ said 기대값 twice)
        if not ((cell.cls in (awk.CLASS_MEASURE, awk.CLASS_NOT_COMPUTABLE) and info is not None
                 and info.bucket in ("measure", "not_computable"))
                or (cell.cls == awk.CLASS_EXPECTED and info is not None and info.expected_value)):
            lines.append(class_explanation(cell.cls))
        extra = info_lines(info) if info is not None else []
        if cell.cls == awk.CLASS_REVIEW:        # '검토 중' is the class; 'needs measuring' would contradict it
            measure = str(_L('需要实测：模拟中未计入伤害（不是 0%）'))
            extra = [x for x in extra if str(x) != measure]
        lines.extend(extra)
        if info is not None and info.confidence != "low" and not info.expected_value and info.bucket == "now":
            # medium / high: the reading behind the number, only when written in the active language (low and
            # expected-value nodes always show theirs, Korean as the fallback - info_lines)
            assumption = str((info.assumption or {}).get(_language()) or "")
            if assumption:
                lines.append(_LF('假设：{0}').format(assumption))
        show_values = (cell.cls in awk.NUMERIC_CLASSES or cell.mismatch or cell.column == "resonance_3"
                       or (cell.cls == awk.CLASS_REVIEW and (cell.value.shown or (cell.other and cell.other.shown))))
        if show_values:
            if cell.cls == awk.CLASS_REVIEW:
                lines.append(_L('当前引擎已计算的部分（只在提示中显示）：'))
            for basis in (awk.BASES if cell.column in awk.NODES else (self._prefs["basis"],)):
                line = self._values_line(m, cell, basis)
                if line:
                    lines.append(line)
        if cell.column == "resonance_3":
            lines.append(_L('包含共鸣3 的技能等级 +1（引擎始终计入）'))
        value = cell.value
        if value.pct is not None and (value.time_changed or (value.damage_pct is not None
                                                              and abs(value.damage_pct - value.pct) >= 0.05)):
            lines.append(_LF('伤害 {0} · 循环时长 {1} 秒（按 DPS 比较）').format(
                pct_text(value.damage_pct) if value.damage_pct is not None else "…",
                f"{value.end_delta_s:+.2f}" if value.end_delta_s is not None else "…"))
        if cell.reference:
            line = notes.reference_line(cell.reference)
            if line and not (show_values and self._reference_shown(m, cell)):
                lines.append(line)
            if cell.reference.get("note"):
                lines.append(notes.note_text(cell.reference["note"]))
        if cell.mismatch:
            lines.append(_L('分类需要确认：分类与单人模拟的数值不一致'))
        return _lines(lines)

    def _reference_shown(self, m: awk.MatrixRow, cell: awk.Cell) -> bool:
        """The specification reference values equal the engine values the tooltip already shows (both bases and
        loop counts present, within 0.05 pp) - the reference line would only repeat them (review UX F10)."""
        rows = self._state()["rows"]
        seen = 0
        for basis in awk.BASES:
            for loops in sorted(awk.LOOP_CHOICES):
                ref = notes.reference_value(cell.reference, basis, loops)
                if ref is None:
                    continue
                if isinstance(ref, tuple):
                    return False
                other = awk.build_matrix(m.entry, rows, loops, basis).cells.get(cell.column)
                if other is None or other.pending or other.value.pct is None:
                    return False
                if abs(float(other.value.pct) - float(ref)) >= awk.ZERO_PCT:
                    return False
                seen += 1
        return seen > 0

    def _full_tooltip(self, m: awk.MatrixRow, cell: awk.Cell) -> str:
        lines = [str(_tr(m.entry.name_zh)) + " · " + _L('全部觉醒（毕业模板的 6 个效果与两个共鸣）相对觉醒 0；两种基准相同')]
        if m.a0 is not None and m.a6 is not None:
            lines.append(_LF('伤害 {0} → {1}（{2} 轮）').format(f"{m.a0.damage:,.1f}", f"{m.a6.damage:,.1f}", m.loops))
        line = self._values_line(m, cell, self._prefs["basis"])
        if line:
            lines.append(line)
        if m.sum_single is not None and cell.value.pct is not None:
            lines.append(_LF('各效果单独相加 {0} / 实际 {1}（效果相乘并含共鸣，因此不同）').format(
                pct_text(m.sum_single), pct_text(cell.value.pct)))
        if m.entry.exclusive:
            lines.append(_L('与上方弧盘效率表的专属弧盘精炼 1 行为同一次计算'))
        if cell.partial_nodes:
            marks = "".join(ta.circled(n) if n in awk.NODES else _LF('共鸣{0}').format(int(n[-1]))
                            for n in cell.partial_nodes)
            lines.append(_LF('未计入：{0}（需要实测 / 审核中 / 上限值）').format(marks))
        expected = [n for n in awk.NODES if m.cells[n].cls == awk.CLASS_EXPECTED and n in m.entry.template]
        if expected:
            lines.append(_LF('按期望值计算：{0}').format("".join(ta.circled(n) for n in expected)))
        return _lines(lines)

    def _character_tooltip(self, m: awk.MatrixRow) -> str:
        cid = m.entry.character_id
        fork = self._fork_names.get(m.entry.fork_id) or m.entry.fork_id
        relation = _L('专属') if m.entry.exclusive else _L('毕业模板')
        lines = [str(_tr(m.entry.name_zh)),
                 _LF('基准弧盘：{0}（{1}）精炼 1').format(str(_tr(fork)), relation)]
        for node in awk.NODES + awk.RESONANCES:
            lines.append(self._node_title(cid, node))
        lines.extend(self._badges(m.entry))
        return _lines(lines)
