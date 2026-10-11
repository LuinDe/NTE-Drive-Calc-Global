# 弧盘效率表页面（Global，演示版）：按单人已审核循环伤害比较角色可装备的弧盘，专属弧盘精炼 1 = 100%。
"""Arc efficiency table page (Global, preview).

Left: the characters with an exclusive arc (status chip, best alternative).  Right: the selected character's arcs
(rank, arc, refinement 1 %, max refinement %, refinement gain, notes; optional raw damage columns), a percentage
bar, header badges (support / sub, low rotation confidence, Global supplement rule, DPS fallback), the legend and
"open in team simulation".  Options: loops (3 default / 1), basis (exclusive R1 = 100 % / same refinement), other
characters' exclusive arcs (†) shown or hidden, damage columns.  Options are kept in
``<config>/arc_efficiency_preferences.json`` (account independent).

Nothing is read or computed while the main window is built: the first show loads the catalog and decides per
character which layer serves it (``arc_efficiency_service.resolve``: precomputed seed, this PC's cache, or a
background recomputation in a WorkerThread with the viewed character first).  All text goes through _L() / _LF();
game names and descriptions stay Chinese data pieces for the display layer; a language switch re-renders, it never
recomputes.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.app.theme import theme_color, theme_rgba, themed_style
from src.app.workers import WorkerThread
from src.features.arc_efficiency.table_view import BAR_ROLE, KEY_ROLE, SORT_ROLE, ArcTable, SortItem
from src.services import arc_efficiency_notes as notes
from src.services import arc_efficiency_service as aes

QUALITY_COLORS = {"ORANGE": "#f0883e", "PURPLE": "#d2a8ff", "BLUE": "#58a6ff"}
ACCENT = "#3fb950"
ABOVE = "#e3b341"
NARROW_WIDTH = 980
COL_RANK, COL_ARC, COL_R1, COL_MAX, COL_GAIN, COL_NOTES, COL_D1, COL_DMAX = range(8)


class _Final(str):
    """A tooltip already in the active language (shown as it is)."""


def _tr(text):
    from src.i18n_display import tr

    return tr(text)


def _join(pieces, sep: str = "\n"):
    """Concatenate provenance strings with ``+`` (str.join drops the provenance a language switch needs)."""
    out = None
    for piece in pieces:
        if piece is None or piece == "":
            continue
        out = piece if out is None else out + sep + piece
    return out if out is not None else ""


def _pill(text, color: str) -> QLabel:
    pill = QLabel(text)
    pill.setStyleSheet(f"background:{theme_rgba(color, 0.16)};color:{theme_color(color)};"
                       f"border:1px solid {theme_rgba(color, 0.5)};border-radius:4px;padding:1px 7px;"
                       "font-size:11px;font-weight:700")
    pill.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return pill


def _toggle_button(text) -> QPushButton:
    button = QPushButton(text)
    button.setCheckable(True)
    button.setMinimumHeight(28)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(themed_style(
        "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
        "padding:3px 12px;font-weight:700}"
        "QPushButton:checked{background:#4f46e5;color:white;border-color:#4f46e5}"))
    return button


def _dataset_short(dataset_id: str) -> str:
    head, _sep, tail = str(dataset_id or "").rpartition("_")
    return head if head and len(tail) == 8 else str(dataset_id or "")


def flag_marks(row: aes.TableRow) -> list[str]:
    marks = []
    if row.flat:
        marks.append("=R")
    if row.flags & aes.FLAG_NO_HIT:
        marks.append("○")
    if row.flags & aes.FLAG_UNRESOLVED:
        marks.append("✕")
    if row.flags & aes.FLAG_DEDUP:
        marks.append("⚖")
    if row.flags & aes.FLAG_SUPPLEMENT:
        marks.append("✚")
    if row.flags & aes.FLAG_AXIS:
        marks.append("≈DPS")
    if row.flags & aes.FLAG_MISSING:
        marks.append("⚠")
    return marks


def mark_text(mark: str):
    return {
        "★": _L('专属'),
        "†": _L('其他角色的专属弧盘'),
        "▲": _L('高于专属弧盘'),
        "=R": _L('精炼效果未体现在单人计算中'),
        "○": _L('条件效果未作用于任何一击'),
        "✕": _L('存在引擎未能解析数值的增益'),
        "⚖": _L('已修正常驻效果的重复计算'),
        "✚": _L('Global 补充规则（依据说明文与数据库数值）'),
        "≈DPS": _L('循环时长不同，按 DPS 比较'),
        "⚠": _L('部分动作缺少动画数据，未计入伤害（结果偏低）'),
        "=": _L('并列'),
    }.get(mark, mark)


def _review_text(status: str | None):
    return {
        "resolved_permanent": _L('常驻效果：已确认'),
        "confirmed_no_permanent": _L('常驻效果：确认为无'),
        "conditional_only": _L('常驻效果：仅条件效果'),
    }.get(str(status or ""), None)


class _CharacterRow(QWidget):
    """One line of the character list: icon, name, status chip, best alternative."""

    def __init__(self, pixmap: QPixmap | None, name_zh: str) -> None:
        super().__init__()
        self.setObjectName("arcEffCharRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)
        self.avatar = QLabel()
        self.avatar.setFixedSize(34, 34)
        if pixmap is not None and not pixmap.isNull():
            self.avatar.setPixmap(pixmap)
        lay.addWidget(self.avatar)
        text = QVBoxLayout()
        text.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.name = QLabel(name_zh)
        self.name.setStyleSheet(themed_style("font-weight:700;color:#f0f6fc"))
        top.addWidget(self.name)
        top.addStretch()
        self.chip = QLabel("")
        top.addWidget(self.chip)
        text.addLayout(top)
        self.best = QLabel("")
        self.best.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
        text.addWidget(self.best)
        lay.addLayout(text, 1)

    def set_status(self, text, color: str) -> None:
        self.chip.setText(text)
        self.chip.setStyleSheet(f"background:{theme_rgba(color, 0.16)};color:{theme_color(color)};"
                                "border-radius:4px;padding:0px 6px;font-size:10px;font-weight:700")


class ArcEfficiencyPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        paths = window.app_context.paths
        self._static_path = Path(paths.static_database_path)
        self._asset_root = getattr(paths, "game_ui_asset_root", None)
        config_dir = getattr(paths, "config_dir", None)
        self._cache = aes.Cache(Path(config_dir) / aes.CACHE_FILE if config_dir else None)
        self._prefs_path = Path(config_dir) / aes.PREFERENCES_FILE if config_dir else None
        self._prefs = aes.load_preferences(self._prefs_path)
        self._ready = False
        self._load_error = ""
        self._catalog: list = []
        self._entries: dict = {}
        self._identity = None
        self._rows: dict = {}                 # L3: every known row (seed / cache / computed now)
        self._sources: dict = {}              # (cid, loops) -> seed | cache | stale | computing | failed
        self._stamps: dict = {}               # (cid, loops) -> computed at (cache)
        self._failed: dict = {}               # (cid, loops) -> message
        self._resolved_loops: set = set()
        self._worker = None
        self._computation = None
        self._generation = 0
        self._paused = False                  # the user cancelled: no automatic restart until they ask
        self._sort = None                     # (column, ascending) or None = the table's own order
        self._table = None                    # aes.Table shown
        self._catalog_icons = None
        self._list_rows: dict = {}
        self._star_texts: dict = {}
        self._fork_icons: dict = {}
        self._shown_rows: list = []
        self._shown_cid = None
        self._pixmaps: dict = {}
        self._computation_loops = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(50)
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
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(10)
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setStyleSheet(themed_style("font-size:22px;font-weight:800;color:#f0f6fc"))
        head.addWidget(self.title)
        self.preview = QLabel()
        self.preview.setStyleSheet(themed_style(
            "background:#3d2f00;color:#e3b341;border:1px solid #9e6a03;border-radius:4px;padding:2px 8px;"
            "font-size:11px;font-weight:700"))
        head.addWidget(self.preview)
        head.addStretch()
        self.source_label = QLabel()
        self.source_label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        head.addWidget(self.source_label)
        outer.addLayout(head)
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(themed_style("color:#8b949e"))
        outer.addWidget(self.subtitle)

        notice = QFrame()
        notice.setObjectName("card")
        nl = QVBoxLayout(notice)
        nl.setContentsMargins(14, 8, 14, 8)
        self.notice_toggle = QPushButton()
        self.notice_toggle.setCheckable(True)
        self.notice_toggle.setStyleSheet(themed_style(
            "QPushButton{background:transparent;border:none;color:#e3b341;font-weight:800;text-align:left;"
            "font-size:13px}"))
        nl.addWidget(self.notice_toggle)
        self.notice_body = QLabel()
        self.notice_body.setWordWrap(True)
        self.notice_body.setStyleSheet(themed_style("color:#c9d1d9;line-height:150%"))
        self.notice_body.setVisible(False)
        self.notice_toggle.toggled.connect(self.notice_body.setVisible)
        nl.addWidget(self.notice_body)
        outer.addWidget(notice)

        options = QHBoxLayout()
        options.setSpacing(8)
        self.loops_caption = QLabel()
        self.loops_caption.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        options.addWidget(self.loops_caption)
        self.loops_group = QButtonGroup(self)
        self.loops_buttons = {}
        for loops in aes.LOOP_CHOICES:
            button = _toggle_button("")
            self.loops_group.addButton(button, loops)
            self.loops_buttons[loops] = button
            options.addWidget(button)
        self.loops_group.idClicked.connect(self._on_loops)
        options.addSpacing(12)
        self.basis_caption = QLabel()
        self.basis_caption.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        options.addWidget(self.basis_caption)
        self.basis_group = QButtonGroup(self)
        self.basis_buttons = {}
        for index, basis in enumerate(aes.BASES):
            button = _toggle_button("")
            self.basis_group.addButton(button, index)
            self.basis_buttons[basis] = button
            options.addWidget(button)
        self.basis_group.idClicked.connect(self._on_basis)
        options.addSpacing(12)
        self.foreign_check = QCheckBox()
        self.foreign_check.toggled.connect(self._on_foreign)
        options.addWidget(self.foreign_check)
        self.damage_check = QCheckBox()
        self.damage_check.toggled.connect(self._on_damage)
        options.addWidget(self.damage_check)
        options.addStretch()
        outer.addLayout(options)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.char_list = QListWidget()
        self.char_list.setObjectName("arcEffCharList")
        self.char_list.setFixedWidth(270)
        self.char_list.setIconSize(QSize(1, 1))
        self.char_list.currentRowChanged.connect(self._on_list_row)
        body.addWidget(self.char_list)
        right = QVBoxLayout()
        right.setSpacing(6)
        self.char_combo = QComboBox()
        self.char_combo.setVisible(False)
        self.char_combo.currentIndexChanged.connect(self._on_combo)
        right.addWidget(self.char_combo)
        title_row = QHBoxLayout()
        self.char_title = QLabel()
        self.char_title.setStyleSheet(themed_style("font-size:16px;font-weight:800;color:#f0f6fc"))
        title_row.addWidget(self.char_title)
        self.basis_title = QLabel()
        self.basis_title.setStyleSheet(themed_style("font-size:14px;font-weight:700;color:#c9d1d9"))
        title_row.addWidget(self.basis_title)
        title_row.addStretch()
        right.addLayout(title_row)
        self.char_sub = QLabel()
        self.char_sub.setWordWrap(True)
        self.char_sub.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        right.addWidget(self.char_sub)
        self.badge_row = QHBoxLayout()
        self.badge_row.setSpacing(6)
        right.addLayout(self.badge_row)
        self.table = ArcTable()
        self.table.horizontalHeader().sectionClicked.connect(self._on_header)
        self.table.tooltip_provider = self.tooltip_for
        self.table.currentCellChanged.connect(lambda *_a: self._update_open_button())
        right.addWidget(self.table, 1)
        self.legend = QLabel()
        self.legend.setWordWrap(True)
        self.legend.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
        right.addWidget(self.legend)
        actions = QHBoxLayout()
        self.cancel_btn = QPushButton()
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        actions.addWidget(self.cancel_btn)
        actions.addStretch()
        self.open_btn = QPushButton()
        self.open_btn.setMinimumHeight(32)
        self.open_btn.setStyleSheet(themed_style(
            "QPushButton{background:#4f46e5;color:white;border:none;border-radius:6px;font-weight:700;padding:4px 14px}"
            "QPushButton:hover{background:#6366f1}QPushButton:disabled{background:#30363d;color:#8b949e}"))
        self.open_btn.clicked.connect(self.open_in_team_simulation)
        actions.addWidget(self.open_btn)
        right.addLayout(actions)
        body.addLayout(right, 1)
        outer.addLayout(body, 1)
        self.status = QLabel("")
        self.status.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        outer.addWidget(self.status)
        self._apply_static_texts()

    def _apply_static_texts(self) -> None:
        self.title.setText(_L('弧盘效率表 (Beta)'))
        self.preview.setText(_L('未完成'))
        self.subtitle.setText(_L('按单人循环伤害比较角色可装备的弧盘。专属弧盘精炼 1 = 100%。'))
        self.notice_toggle.setText(_L('⚠ 注意事项'))
        self.notice_body.setText(self._notice_text())
        self.loops_caption.setText(_L('循环轮数'))
        for loops, button in self.loops_buttons.items():
            button.setText(_LF('{0} 轮').format(loops))
        self.basis_caption.setText(_L('比较基准'))
        self.basis_buttons["exclusive_r1"].setText(_L('专属弧盘精炼 1 = 100%'))
        self.basis_buttons["same_refine"].setText(_L('同精炼对比'))
        self.foreign_check.setText(_L('显示其他角色的专属弧盘'))
        self.damage_check.setText(_L('显示伤害数值'))
        self.cancel_btn.setText(_L('取消'))
        self.open_btn.setText(_L('在队伍模拟中打开'))
        self._sync_option_widgets()

    def _sync_option_widgets(self) -> None:
        for widget in (self.foreign_check, self.damage_check):
            widget.blockSignals(True)
        self.loops_buttons[self._prefs["loops"]].setChecked(True)
        self.basis_buttons[self._prefs["basis"]].setChecked(True)
        self.foreign_check.setChecked(bool(self._prefs["show_foreign"]))
        self.damage_check.setChecked(bool(self._prefs["show_damage"]))
        for widget in (self.foreign_check, self.damage_check):
            widget.blockSignals(False)

    @staticmethod
    def _notice_text():
        lines = (
            _L('效率表只比较弧盘，不代表实战结果。'),
            _L('角色按官方毕业模板计算，只更换弧盘与精炼。'),
            _L('只有角色本人按已审核循环行动，没有队友、换人与环合反应。'),
            _L('依赖援护技、队友、队伍构成、环合强度或倾陷强度的弧盘效果按 0 计算。'),
            _L('目标为 80 级木桩（非首领、未倾陷、不受击），能量与冷却不影响循环。'),
            _L('叠层效果每次从 0 层开始；3 轮可看到延续的层数。'),
            _L('「罪与罚」「月的对跖点」的条件效果按 Global 补充规则（依据说明文与数据库数值）计算；常驻效果的重复计算已修正。'),
            _L('标 † 的弧盘按计算器的同类型规则列出，未在游戏内实测。'),
            _L('所有弧盘的循环时长相同，因此伤害比 = DPS 比。'),
            _L('没有专属弧盘的角色不在此表中。'),
        )
        return _join(["- " + line for line in lines])

    # ── first show: catalog, layers, background work ───────────────────────
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._ready:
            self._ready = True
            self.ensure_loaded()

    def ensure_loaded(self) -> None:
        """Catalog + identity + layer decision for the current loops (idempotent)."""
        if self._identity is None:
            try:
                self._catalog = aes.eligible_characters(self._static_path)
                self._entries = {e.character_id: e for e in self._catalog}
                self._identity = aes.current_identity(self._static_path)
                self._star_texts = aes.load_star_texts(
                    self._static_path, {a.fork_id for e in self._catalog for a in e.arcs})
            except Exception as exc:  # noqa: BLE001
                self._load_error = f"{type(exc).__name__}: {exc}"
                self._render()
                return
            self._fill_character_widgets()
        self._resolve(self._prefs["loops"])
        self._render()
        self._maybe_start()

    def _resolve(self, loops: int) -> None:
        if loops in self._resolved_loops or self._identity is None:
            return
        self._resolved_loops.add(loops)
        result = aes.resolve(self._static_path, self._catalog, loops, self._cache, self._identity)
        self._rows.update(result.rows)
        for cid, source in result.sources.items():
            self._sources[(cid, loops)] = source
        for cid, stamp in result.computed_at.items():
            self._stamps[(cid, loops)] = stamp

    def _stale(self, loops: int) -> list[int]:
        return [e.character_id for e in self._catalog if self._sources.get((e.character_id, loops)) == aes.SOURCE_STALE]

    def _maybe_start(self) -> None:
        """Start the background recomputation of the current loops' stale characters (viewed one first)."""
        if self._paused or (self._worker is not None and self._worker.isRunning()):
            return
        loops = self._prefs["loops"]
        stale = self._stale(loops)
        if not stale:
            return
        pending = {}
        for cid in stale:
            entry = self._entries[cid]
            pending[cid] = [(f, r) for f, r in aes.job_order(entry)
                            if aes.row_key(cid, f, r, loops) not in self._rows]
            if not pending[cid]:
                del pending[cid]
            self._sources[(cid, loops)] = "computing" if cid in pending else aes.SOURCE_STALE
        for cid in stale:
            if cid not in pending:          # every row is known (an interrupted run) but the cache was not saved
                self._finish_character(cid, loops, True, "")
        if not pending:
            self._render()
            return
        self._generation += 1
        generation = self._generation
        selected = self.selected_character()
        order = ([selected] if selected in pending else []) + [c for c in stale if c in pending and c != selected]
        worker_ref: list = []

        def on_row(key, row) -> None:
            if worker_ref:
                worker_ref[0].progress.emit(("row", generation, key, row))

        def on_character(cid, ok, message) -> None:
            if worker_ref:
                worker_ref[0].progress.emit(("character", generation, cid, loops, ok, message))

        computation = aes.Computation(self._static_path, self._entries, loops, pending, self._cache, self._identity,
                                      on_row=on_row, on_character=on_character, order=order, generation=generation)
        computation.prioritize(selected)
        self._computation = computation
        self._computation_loops = loops
        worker = WorkerThread(computation.run, self)
        worker_ref.append(worker)
        worker.progress.connect(self._on_progress)
        worker.result_ready.connect(lambda _rows, g=generation: self._on_worker_done(g, ""))
        worker.error.connect(lambda message, g=generation: self._on_worker_done(g, message))
        self._worker = worker
        worker.start()
        self._render()

    def stop_computation(self, wait_ms: int = 0) -> None:
        """Cancel the background work (it stops after the current run, at most about half a second); with
        ``wait_ms`` wait for the thread (application exit: a running QThread must not be destroyed)."""
        if self._computation is not None:
            self._computation.cancel()
        if wait_ms and self._worker is not None:
            try:
                self._worker.wait(int(wait_ms))
            except RuntimeError:
                pass

    def _on_progress(self, payload) -> None:
        kind, generation = payload[0], payload[1]
        if generation != self._generation:
            return                          # a late result of an abandoned computation
        if kind == "row":
            _kind, _g, key, row = payload
            self._rows[key] = row
        elif kind == "character":
            _kind, _g, cid, loops, ok, message = payload
            self._finish_character(cid, loops, ok, message)
        self._refresh_timer.start()

    def _finish_character(self, cid: int, loops: int, ok: bool, message: str) -> None:
        if ok:
            self._sources[(cid, loops)] = aes.SOURCE_CACHE
            self._stamps[(cid, loops)] = self._cache.computed_at(self._identity, aes.row_key(
                cid, self._entries[cid].exclusive_fork_id, 1, loops)) if self._identity is not None else ""
        else:
            self._sources[(cid, loops)] = "failed"
            self._failed[(cid, loops)] = message

    def _on_worker_done(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._computation = None
        loops = self._computation_loops if self._computation_loops is not None else self._prefs["loops"]
        for cid in self._entries:
            if self._sources.get((cid, loops)) == "computing":
                self._sources[(cid, loops)] = aes.SOURCE_STALE        # interrupted (cancel)
        if message:
            self.status.setText(_LF('计算失败：{0}').format(message))
        self._render()
        if not self._paused:
            QTimer.singleShot(0, self._maybe_start)                    # loops switched meanwhile

    def _on_cancel(self) -> None:
        self._paused = True
        self.stop_computation()
        self._render()

    # ── options ─────────────────────────────────────────────────────────
    def _save_prefs(self) -> None:
        aes.save_preferences(self._prefs_path, self._prefs)

    def _on_loops(self, loops: int) -> None:
        if loops == self._prefs["loops"]:
            return
        self._prefs["loops"] = int(loops)
        self._save_prefs()
        self.stop_computation()             # the other loops' rows are computed only when shown
        self._paused = False
        if self._identity is not None:
            self._resolve(loops)
        self._render()
        self._maybe_start()

    def _on_basis(self, index: int) -> None:
        self._prefs["basis"] = aes.BASES[index]
        self._save_prefs()
        self._render()

    def _on_foreign(self, checked: bool) -> None:
        self._prefs["show_foreign"] = bool(checked)
        self._save_prefs()
        self._render()

    def _on_damage(self, checked: bool) -> None:
        self._prefs["show_damage"] = bool(checked)
        self._save_prefs()
        self._render()

    def _on_header(self, column: int) -> None:
        if column in (COL_NOTES,):
            return
        if self._sort is not None and self._sort[0] == column:
            self._sort = (column, not self._sort[1])
        else:
            self._sort = (column, column in (COL_RANK, COL_ARC))
        self._render_table()

    # ── character selection ─────────────────────────────────────────────
    def selected_character(self) -> int | None:
        cid = self._prefs.get("character")
        if cid in self._entries:
            return cid
        return self._catalog[0].character_id if self._catalog else None

    def select_character(self, cid: int) -> None:
        if cid not in self._entries:
            return
        self._prefs["character"] = int(cid)
        self._save_prefs()
        self._sort = None
        if self._computation is not None:
            self._computation.prioritize(cid)
        if self._paused and self._sources.get((cid, self._prefs["loops"])) == aes.SOURCE_STALE:
            self._paused = False            # looking at a character that still needs numbers resumes the work
            QTimer.singleShot(0, self._maybe_start)
        self._render()

    def _on_list_row(self, row: int) -> None:
        if 0 <= row < len(self._catalog) and self._catalog[row].character_id != self.selected_character():
            self.select_character(self._catalog[row].character_id)

    def _on_combo(self, index: int) -> None:
        cid = self.char_combo.itemData(index)
        if cid is not None and cid != self.selected_character():
            self.select_character(int(cid))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        narrow = self.width() < NARROW_WIDTH
        self.char_list.setVisible(not narrow)
        self.char_combo.setVisible(narrow)

    # ── icons ───────────────────────────────────────────────────────────
    def _icons(self):
        if self._catalog_icons is None and self._asset_root is not None:
            try:
                from src.services.game_ui_asset_catalog import GameUiAssetCatalog

                self._catalog_icons = GameUiAssetCatalog(self._asset_root)
            except Exception:
                self._catalog_icons = False
        return self._catalog_icons or None

    def _character_icon(self, cid: int):
        icons = self._icons()
        try:
            return icons.character_icon(int(cid)) if icons else None
        except Exception:
            return None

    def _fork_icon(self, fork_id: str):
        icons = self._icons()
        try:
            return icons.fork_icon(fork_id) if icons else None
        except Exception:
            return None

    def _fill_character_widgets(self) -> None:
        self.char_list.blockSignals(True)
        self.char_combo.blockSignals(True)
        self.char_list.clear()
        self.char_combo.clear()
        self._list_rows = {}
        for entry in self._catalog:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry.character_id)
            row = _CharacterRow(None, entry.name_zh)
            item.setSizeHint(QSize(250, 52))
            self.char_list.addItem(item)
            self.char_list.setItemWidget(item, row)
            self._list_rows[entry.character_id] = row
            self.char_combo.addItem(entry.name_zh, entry.character_id)
        self.char_list.blockSignals(False)
        self.char_combo.blockSignals(False)
        QTimer.singleShot(0, self._load_pictures)      # the numbers first, the pictures right after

    def _load_pictures(self) -> None:
        try:
            for index, entry in enumerate(self._catalog):
                path = self._character_icon(entry.character_id)
                pixmap = QPixmap(str(path)) if path else QPixmap()
                if pixmap.isNull():
                    continue
                pixmap = pixmap.scaled(34, 34, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                self._pixmaps[entry.character_id] = pixmap
                row = self._list_rows.get(entry.character_id)
                if row is not None:
                    row.avatar.setPixmap(pixmap)
                self.char_combo.setItemIcon(index, QIcon(pixmap))
            for fork_id in sorted({a.fork_id for e in self._catalog for a in e.arcs}):
                path = self._fork_icon(fork_id)
                self._fork_icons[fork_id] = QIcon(str(path)) if path else QIcon()
            for r, row in enumerate(self._shown_rows):
                item = self.table.item(r, COL_ARC)
                icon = self._fork_icons.get(row.arc.fork_id)
                if item is not None and icon is not None and not icon.isNull():
                    item.setIcon(icon)
        except RuntimeError:
            pass

    # ── rendering ───────────────────────────────────────────────────────
    def _on_language_changed(self) -> None:
        try:
            self._apply_static_texts()
            if self._identity is not None:
                for entry in self._catalog:            # names in the list / combo follow the display layer
                    row = self._list_rows.get(entry.character_id)
                    if row is not None:
                        row.name.setText(entry.name_zh)
                for index, entry in enumerate(self._catalog):
                    self.char_combo.setItemText(index, entry.name_zh)
            self._render()
        except RuntimeError:                           # widgets already gone
            pass

    def table_for(self, cid: int, loops: int | None = None) -> aes.Table | None:
        entry = self._entries.get(cid)
        if entry is None:
            return None
        return aes.build_table(entry, self._rows, loops or self._prefs["loops"], self._prefs["basis"],
                               bool(self._prefs["show_foreign"]))

    def _status_chip(self, cid: int, loops: int):
        source = self._sources.get((cid, loops))
        entry = self._entries[cid]
        jobs = aes.job_order(entry)
        done = sum(1 for f, r in jobs if aes.row_key(cid, f, r, loops) in self._rows)
        if source == aes.SOURCE_SEED:
            return _L('预先计算'), "#3fb950"
        if source == aes.SOURCE_CACHE:
            return _L('本机计算'), "#58a6ff"
        if source == "failed":
            return _L('无法计算'), "#f85149"
        if source == "computing" and self._computation is not None:
            return _LF('计算中 {0}/{1}').format(done, len(jobs)), "#e3b341"
        return _L('等待计算'), "#8b949e"

    def _render(self) -> None:
        if self._load_error:
            self.status.setText(_LF('加载失败：{0}').format(self._load_error))
            return
        if self._identity is None:
            return
        loops = self._prefs["loops"]
        cid = self.selected_character()
        for index, entry in enumerate(self._catalog):
            row = self._list_rows.get(entry.character_id)
            if row is None:
                continue
            text, color = self._status_chip(entry.character_id, loops)
            row.set_status(text, color)
            best = self.table_for(entry.character_id)
            alt = best.best_alternative() if best is not None and not best.failed else None
            if alt is not None and alt.pct_r1 is not None:
                row.best.setText(_LF('最佳替代 {0} {1}').format(alt.marker + alt.arc.name_zh, f"{alt.pct_r1:.1f}%"))
            else:
                row.best.setText("")
        if cid is not None:
            index = next((i for i, e in enumerate(self._catalog) if e.character_id == cid), -1)
            self.char_list.blockSignals(True)
            self.char_list.setCurrentRow(index)
            self.char_list.blockSignals(False)
            self.char_combo.blockSignals(True)
            self.char_combo.setCurrentIndex(index)
            self.char_combo.blockSignals(False)
        self._render_header()
        self._render_table()
        self._render_status()

    def _render_header(self) -> None:
        cid = self.selected_character()
        while self.badge_row.count():
            item = self.badge_row.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()                    # gone at once; deleted when control returns to the loop
                item.widget().deleteLater()
        if cid is None:
            self.char_title.setText("")
            self.basis_title.setText("")
            self.char_sub.setText("")
            return
        entry = self._entries[cid]
        table = self.table_for(cid)
        self._table = table
        loops = self._prefs["loops"]
        self.char_title.setText(entry.name_zh)
        basis = entry.arc(entry.exclusive_fork_id)
        if self._prefs["basis"] == "same_refine":
            self.basis_title.setText(_L('同精炼对比'))
        else:
            self.basis_title.setText(_LF('100% = ★{0} 精炼 {1}').format(basis.name_zh if basis else "", 1))
        if table is not None and table.basis_damage:
            self.char_sub.setText(_LF('单人 {0} 轮 · 循环 {1} 秒（不含时停） · 毕业模板 · 基准伤害 {2}').format(
                loops, f"{table.active_s:.1f}", f"{table.basis_damage:,.0f}"))
        else:
            self.char_sub.setText(_L('先计算专属弧盘…') if self._sources.get((cid, loops)) == "computing" else "")
        badges = []
        if entry.role in ("support", "sub"):
            badges.append((_L('辅助/副位：单人循环较短，不反映队伍贡献'), "#58a6ff"))
        if entry.confidence == "low":
            badges.append((_L('循环可信度低'), "#e3b341"))
        if table is not None:
            ex_rows = [r for r in table.rows if r.arc.fork_id == entry.exclusive_fork_id]
            if any(r.flags & aes.FLAG_SUPPLEMENT for r in ex_rows):
                badges.append((_L('Global 补充规则（依据说明文与数据库数值）'), "#d2a8ff"))
            if table.dps_mode:
                badges.append((_L('循环时长不同，按 DPS 比较'), "#e3b341"))
            if table.failed or self._sources.get((cid, loops)) == "failed":
                badges.append((_L('无法计算'), "#f85149"))
        for text, color in badges:
            self.badge_row.addWidget(_pill(text, color))
        self.badge_row.addStretch()

    def _headers(self, max_star: int) -> list:
        labels = [_L('排名'), _L('弧盘'), _L('精炼 1'), _LF('满精炼（{0}）').format(max_star), _L('精炼提升'),
                  _L('备注')]
        if self._prefs["show_damage"]:
            labels += [_L('精炼 1 伤害'), _LF('满精炼（{0}）伤害').format(max_star)]
        return labels

    def _sorted_rows(self, table: aes.Table) -> list:
        rows = list(table.rows)
        if self._sort is None:
            return rows
        column, ascending = self._sort
        same = self._prefs["basis"] == "same_refine"

        def number(value):
            return value if value is not None else float("-inf")

        keys = {
            COL_RANK: lambda r: (r.rank or 10 ** 6,),
            COL_ARC: lambda r: (r.arc.name_zh, r.arc.fork_id),
            COL_R1: lambda r: (number(r.pct_r1),),
            COL_MAX: lambda r: (number(r.pct_max_same if same else r.pct_max),),
            COL_GAIN: lambda r: (number(r.gain),),
            COL_D1: lambda r: (number(r.damage_r1),),
            COL_DMAX: lambda r: (number(r.damage_max),),
        }
        key = keys.get(column)
        if key is None:
            return rows
        return sorted(rows, key=key, reverse=not ascending)

    def _render_table(self) -> None:
        table = self._table
        widget = self.table
        keep = None                                     # the selected cell survives a re-render (same character)
        if widget.currentRow() >= 0 and 0 <= widget.currentRow() < len(self._shown_rows) \
                and self._shown_cid == self.selected_character():
            keep = (self._shown_rows[widget.currentRow()].arc.fork_id, widget.currentColumn())
        widget.clearContents()
        cid = self.selected_character()
        if table is None or cid is None:
            widget.setRowCount(0)
            return
        loops = self._prefs["loops"]
        same = self._prefs["basis"] == "same_refine"
        top = max((r.max_star for r in table.rows), default=5)
        headers = self._headers(top)
        widget.setColumnCount(len(headers))
        widget.setHorizontalHeaderLabels(headers)
        widget.setItemDelegateForColumn(COL_R1, widget.bar_delegate)
        rows = self._sorted_rows(table)
        widget.setRowCount(len(rows))
        scale = max([100.0] + [v for r in rows for v in (r.pct_r1, r.pct_max)
                               if v is not None]) * 1.04
        entry = self._entries[cid]
        self._shown_rows = rows
        self._shown_cid = cid
        for i, row in enumerate(rows):
            self._fill_row(i, row, table, entry, loops, same, scale)
        # selection: kept across re-renders, else the exclusive arc's row (the button opens it at refinement 1)
        target = keep or (entry.exclusive_fork_id, COL_ARC)
        index = next((i for i, r in enumerate(rows) if r.arc.fork_id == target[0]), -1)
        if index >= 0:
            widget.blockSignals(True)
            widget.setCurrentCell(index, max(0, min(target[1], widget.columnCount() - 1)))
            widget.blockSignals(False)
        header = widget.horizontalHeader()
        if self._sort is not None:
            header.setSortIndicator(self._sort[0], Qt.AscendingOrder if self._sort[1] else Qt.DescendingOrder)
        else:
            header.setSortIndicator(-1, Qt.AscendingOrder)
        widget.resizeColumnsToContents()
        widget.setColumnWidth(COL_R1, max(widget.columnWidth(COL_R1), 150))
        self.legend.setText(self._legend())
        self._update_open_button()

    def _item(self, text, sort=None, align=Qt.AlignVCenter | Qt.AlignRight) -> SortItem:
        item = SortItem(text)
        item.setData(SORT_ROLE, sort)
        item.setTextAlignment(int(align))
        return item

    def _fill_row(self, i: int, row: aes.TableRow, table: aes.Table, entry, loops: int, same: bool, scale: float) -> None:
        widget = self.table
        exclusive = row.marker == "★"
        pending = "…"
        rank = self._item((str(row.rank) + ("=" if row.tied else "")) if row.rank else pending, row.rank,
                          Qt.AlignVCenter | Qt.AlignHCenter)
        widget.setItem(i, COL_RANK, rank)

        name = row.arc.name_zh if not row.marker else row.marker + " " + row.arc.name_zh
        arc = self._item(name, row.arc.name_zh, Qt.AlignVCenter | Qt.AlignLeft)
        icon = self._fork_icons.get(row.arc.fork_id)       # loaded right after the first table (_load_pictures)
        if icon is not None and not icon.isNull():
            arc.setIcon(icon)
        arc.setForeground(QBrush(QColor(theme_color(QUALITY_COLORS.get(row.arc.quality, "#c9d1d9")))))
        if exclusive:
            font = QFont(arc.font())
            font.setBold(True)
            arc.setFont(font)
        arc.setData(KEY_ROLE, (row.arc.fork_id, 1))
        widget.setItem(i, COL_ARC, arc)

        second = row.pct_max_same if same else row.pct_max
        for column, value, damage, refine in ((COL_R1, row.pct_r1, row.damage_r1, 1),
                                              (COL_MAX, second, row.damage_max, row.max_star)):
            if value is None:
                item = self._item(pending, None)
            else:
                above = (not exclusive) and value > 100.0 + 1e-9
                item = self._item(("▲ " if above else "") + f"{value:.1f}%", value)
                if above:
                    item.setForeground(QBrush(QColor(theme_color(ABOVE))))
                elif column == COL_MAX and row.flat:
                    item.setForeground(QBrush(QColor(theme_color("#6e7681"))))
            if column == COL_R1:
                item.setData(BAR_ROLE, (row.pct_r1, row.pct_max, scale, theme_color(
                    QUALITY_COLORS.get(row.arc.quality, ACCENT))) if row.pct_r1 is not None else None)
            item.setData(KEY_ROLE, (row.arc.fork_id, refine))
            widget.setItem(i, column, item)

        if row.gain is None:
            gain = self._item(pending, None)
        elif row.flat:
            gain = self._item("=R", 1.0)
            gain.setForeground(QBrush(QColor(theme_color("#6e7681"))))
        else:
            gain = self._item(f"×{row.gain:.2f}", row.gain)
        gain.setData(KEY_ROLE, (row.arc.fork_id, row.max_star))
        widget.setItem(i, COL_GAIN, gain)

        notes_text, _tip = self._notes(row, entry, tips=False)
        notes = self._item(notes_text, None, Qt.AlignVCenter | Qt.AlignLeft)
        notes.setData(KEY_ROLE, (row.arc.fork_id, 1))
        widget.setItem(i, COL_NOTES, notes)

        if self._prefs["show_damage"]:
            for column, value, refine in ((COL_D1, row.damage_r1, 1), (COL_DMAX, row.damage_max, row.max_star)):
                item = self._item(f"{value:,.1f}" if value is not None else pending, value)
                item.setData(KEY_ROLE, (row.arc.fork_id, refine))
                widget.setItem(i, column, item)

    def _notes(self, row: aes.TableRow, entry, tips: bool = True):
        marks = flag_marks(row)
        if row.above:
            marks.insert(0, "▲")
        codes = notes.codes_for(row.arc.fork_id, entry.element)
        if codes is None:
            codes = ("unannotated",)
        text = None
        lines = []
        for mark in marks:
            text = mark if text is None else text + "  " + mark
            if tips:
                lines.append(mark + " " + mark_text(mark))
        for code in codes:
            label = notes.label(code)
            text = label if text is None else text + " · " + label
            if tips:
                lines.append(label + " — " + notes.explanation(code))
        return (text or ""), _join(lines)

    def tooltip_for(self, r: int, c: int) -> str | None:
        """Tooltip of a table cell in the active language, built when the mouse rests on it.  Every piece goes
        through the display layer exactly once (an effect description is translated before its numbers are filled
        in; running the term table over it again would double-translate its kept terms)."""
        text = self._tooltip_source(r, c)
        if text is None or isinstance(text, _Final):
            return text
        return str(_tr(text))

    def _tooltip_source(self, r: int, c: int):
        if not (0 <= r < len(self._shown_rows)) or self._table is None:
            return None
        row = self._shown_rows[r]
        entry = self._entries.get(self.selected_character())
        if entry is None:
            return None
        loops = self._prefs["loops"]
        same = self._prefs["basis"] == "same_refine"
        if c == COL_RANK:
            return mark_text("=") if row.tied else None
        if c == COL_ARC:
            return self._arc_tooltip(row, entry)
        if c == COL_R1 and row.pct_r1 is not None:
            return self._pct_tooltip(row, self._table, loops, 1, row.damage_r1, same)
        if c == COL_MAX and (row.pct_max_same if same else row.pct_max) is not None:
            return self._pct_tooltip(row, self._table, loops, row.max_star, row.damage_max, same)
        if c == COL_GAIN and row.flat:
            return mark_text("=R")
        if c == COL_NOTES:
            return self._notes(row, entry)[1] or None
        return None

    def _pct_tooltip(self, row: aes.TableRow, table: aes.Table, loops: int, refine: int, damage, same: bool):
        basis = table.basis_damage_max if (same and refine != 1) else table.basis_damage
        lines = [_LF('伤害 {0} · {1} 轮 · 基准 {2}').format(
            f"{damage:,.1f}" if damage is not None else "…", loops, f"{basis:,.1f}" if basis else "…")]
        if refine != 1:
            if same and row.pct_max is not None:
                lines.append(_LF('专属弧盘精炼 1 = 100%：{0}').format(f"{row.pct_max:.1f}%"))
            elif not same and row.pct_max_same is not None:
                lines.append(_LF('同精炼对比：{0}').format(f"{row.pct_max_same:.1f}%"))
        if row.marker == "★" and refine != 1:
            lines.append(_L('专属'))
        return _join(lines)

    def _arc_tooltip(self, row: aes.TableRow, entry):
        arc = row.arc
        if arc.own_exclusive:
            relation = _L('专属')
        elif arc.foreign_exclusive:
            relation = _LF('{0} 专属').format("、".join(arc.owner_names_zh))
        else:
            relation = _L('同类型')
        # each piece on its own: the English term pass strips the spaces at the ends of a translated piece
        lines = [" · ".join(str(_tr(piece)) for piece in (arc.name_zh, arc.type_name_zh, relation) if piece)]
        review = _review_text(arc.review)
        if review is not None:
            lines.append(str(_tr(review)))
        for refine in arc.refines:
            star = self._star_texts.get((arc.fork_id, refine))
            text = aes.render_star_text(*star) if star else ""
            if text:                            # translated template; the description is final text already
                lines.append(str.format(str(_LF('精炼 {0}：{1}')), refine, text))
        return _Final("\n".join(lines))

    def _legend(self):
        pieces = []
        for mark in ("★", "†", "▲", "=R", "○", "✕", "⚖", "✚"):
            pieces.append(mark + " " + mark_text(mark))
        return _join(pieces, "   ")

    def _render_status(self) -> None:
        loops = self._prefs["loops"]
        cid = self.selected_character()
        computing = self._computation is not None and self._worker is not None and self._worker.isRunning()
        self.cancel_btn.setVisible(computing)
        dataset = _dataset_short(self._identity.dataset_id) if self._identity is not None else ""
        source = self._sources.get((cid, loops)) if cid is not None else None
        if source == aes.SOURCE_SEED:
            self.source_label.setText(_LF('预先计算的结果（数据 {0}）').format(dataset))
        elif source == aes.SOURCE_CACHE:
            self.source_label.setText(_LF('本机计算的结果（{0}）').format(self._stamps.get((cid, loops)) or dataset))
        else:
            self.source_label.setText("")
        if computing:
            total = done = 0
            for c in self._entries:
                if self._sources.get((c, loops)) in ("computing", aes.SOURCE_STALE):
                    jobs = aes.job_order(self._entries[c])
                    total += len(jobs)
                    done += sum(1 for f, r in jobs if aes.row_key(c, f, r, loops) in self._rows)
            self.status.setText(_LF('数据已变更，正在重新计算…（{0}/{1}）').format(done, total))
        elif source == "failed":
            self.status.setText(_LF('计算失败：{0}').format(self._failed.get((cid, loops)) or "-"))
        elif source == aes.SOURCE_STALE:
            self.status.setText(_L('等待计算'))
        else:
            self.status.setText("")

    def _update_open_button(self) -> None:
        target = getattr(self._window, "team_simulation_page", None)
        self.open_btn.setEnabled(self.current_choice() is not None and hasattr(target, "apply_team"))

    # ── open in team simulation ─────────────────────────────────────────
    def current_choice(self) -> tuple[str, int] | None:
        """(arc, refinement) of the selected cell (the max-refinement / gain columns choose the max refinement)."""
        item = self.table.currentItem()
        if item is None:
            row = self.table.currentRow()
            item = self.table.item(row, COL_ARC) if row >= 0 else None
        if item is None:
            return None
        value = item.data(KEY_ROLE)
        return (str(value[0]), int(value[1])) if value else None

    def open_in_team_simulation(self) -> bool:
        cid = self.selected_character()
        choice = self.current_choice()
        target = getattr(self._window, "team_simulation_page", None)
        if cid is None or choice is None or not hasattr(target, "apply_team"):
            return False
        fork_id, refine = choice
        team = target.team_json()
        ids = [row.get("character_id") for row in team]
        template = target.template(cid) or {}
        first = {"character_id": cid, "awakening_level": template.get("awakening_level"), "fork_id": fork_id,
                 "fork_refinement_level": refine, "suit_id": template.get("suit_id")}
        if cid in ids[1:]:                  # the character sits in another slot: swap with slot 1
            team[ids.index(cid)] = team[0]
        team[0] = first
        if hasattr(target, "set_mode"):
            target.set_mode("approved")
        target.apply_team(team)
        go = getattr(self._window, "_go", None)
        if callable(go):
            go("team_sim")
        return True
