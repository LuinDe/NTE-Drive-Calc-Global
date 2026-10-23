# 构建队伍模拟页面（演示版）：四人队伍设置、出场顺序选项（固定 3 轮、第 1、3 轮环合值 100）、假设说明、伤害/DPS 结果与「使用的循环」说明。
"""Team simulation page (preview).

Four member cards (character, awakening = six freely chosen effects whose count is the level - Korean UI "돌파" -,
fork, refinement, cartridge set), a notice listing the
simulation assumptions, the visit-order option (planner "transformation damage dealer first" by
default, most reactions, or slot order) and a fixed loop rule (three loops; every member's cycle gauge
is 100 at the start of loops 1 and 3, loop 2 keeps the built-up gauge), and a result panel: team totals (damage, battle time without time stops, DPS, cycle reaction
damage), per-member rows (element, role, visits, direct / reaction damage, on-field time, DPS share
of the team DPS), the team
buffs, and the explanation panel of the rotation and cycle used (explanation_view).  Esper Cycle
reactions are always computed; there is deliberately no switch to turn them off.
The calculation runs in a WorkerThread through src.services.team_simulation_service.

Two modes share the member cards, the calculate button, the status line and the result box: "已审核循环" (the
reviewed rotations, default) and "直接输入" (custom cycle: the user builds or types one flat team sequence,
custom_panel.CustomCyclePanel, calculated by team_custom_cycle_service.simulate_custom).  Each mode keeps its
own last result.  The custom panel is built the first time the mode is used.
All visible text goes through _L() with a Chinese key so the language switcher can re-render it;
game names are passed as their Chinese originals and translated by the display layer.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Signal  # member cards: awakening_changed (own line: keeps the Puka patch's context)

from src.ui.rich_tooltip import translated_as_is  # review UX F3
from src.app.theme import theme_color, theme_rgba, themed_style
from src.app.workers import WorkerThread
from src.ui.dashboard_widgets import metric_card

SLOT_COLORS = ("#e3b341", "#39c5cf", "#8fd14f", "#d2a8ff")
TEAM_SIZE = 4
REACTION_COLOR = "#f0883e"


def _fmt_amount(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def _chip(text: str) -> QLabel:
    chip = QLabel(text)
    chip.setStyleSheet(themed_style(
        "background:#1f2a44;color:#c9d1d9;border-radius:4px;padding:4px 10px;font-size:12px;font-weight:600"))
    return chip


def _role_text(code: str) -> str:
    return {"support": _L('辅助'), "sub": _L('副输出'), "main": _L('主输出')}.get(code, code)


def _option_caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
    return label


from PySide6.QtCore import QEvent  # the member card's character combo (own line: keeps the Puka patch's context)
from PySide6.QtWidgets import QStyle, QStyleOptionComboBox, QStylePainter, QToolTip  # character combo (own line)


class _CharacterCombo(QComboBox):
    """Character choice of a member card (2.3.2).  The card's avatar sits right next to it, so the closed
    combo draws the name without the list icon (the popup list keeps the icons) and with tighter padding: names such
    as "라크리모사", "ダフォディル" or "Akane Rin" fit a 230 px card (they were clipped, e.g. "라크리모").  A name that
    still does not fit (a larger system font) ends with "…" and shows in full as the tooltip."""

    STYLE = ("QComboBox#teamSimCharacterCombo{padding:7px 4px 7px 8px}"
             "QComboBox#teamSimCharacterCombo::drop-down{width:14px}")

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("teamSimCharacterCombo")
        self.setStyleSheet(self.STYLE)
        self._elided = False

    def shown_name(self) -> str:
        """The name as shown (display role: the translated name)."""
        value = self.itemData(self.currentIndex(), Qt.ItemDataRole.DisplayRole)
        return "" if value is None else str(value)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        opt.currentIcon = QIcon()
        field = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, opt,
                                            QStyle.SubControl.SC_ComboBoxEditField, self)
        full = opt.currentText
        opt.currentText = self.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight, max(0, field.width() - 2))
        self._elided = opt.currentText != full
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ToolTip and self._elided:
            QToolTip.showText(event.globalPos(), self.shown_name(), self)
            return True
        return super().event(event)


class _MemberCard(QFrame):
    """One team slot: character, awakening (six effects chosen freely - any order, any subset; the count is the level
    and decides the resonances), fork, refinement 1-5, cartridge set."""

    awakening_changed = Signal()            # an effect toggle / the quick menu / a team load changed the selection

    def __init__(self, page: "TeamSimulationPage", slot: int) -> None:
        super().__init__()
        self._page = page
        self.slot = slot
        self.setObjectName("card")
        self.setMinimumWidth(230)
        color = SLOT_COLORS[slot]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        badge = QLabel(f"{slot + 1}P")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(38, 26)
        badge.setStyleSheet(f"background:{theme_rgba(color, 0.18)};color:{theme_color(color)};"
                            f"border:1px solid {theme_color(color)};border-radius:6px;font-weight:800")
        head.addWidget(badge)
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        head.addWidget(self.avatar)
        self.character_combo = _CharacterCombo()
        self.character_combo.currentIndexChanged.connect(self._on_character_changed)
        head.addWidget(self.character_combo, 1)
        lay.addLayout(head)

        # awakening (A13; Korean UI "돌파"): the count of the six non-exclusive effect toggles is the level
        from src.features.team_simulation import awakening_text as awt

        awk = QHBoxLayout()
        awk.setSpacing(6)
        self.awakening_caption = self._caption(awt.count_caption(0))
        awk.addWidget(self.awakening_caption)
        # review UX F2: the resonance labels sit on their own row under the toggles (en cut them at 242 px)
        resonance_row = QHBoxLayout()
        resonance_row.setSpacing(10)
        self.resonance_labels: dict[int, QLabel] = {}
        for level in (3, 6):
            label = QLabel()
            label.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
            resonance_row.addWidget(label)
            self.resonance_labels[level] = label
        resonance_row.addStretch()
        awk.addStretch()
        self.awakening_menu_btn = QToolButton()
        self.awakening_menu_btn.setText("⋯")
        self.awakening_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.awakening_menu = QMenu(self.awakening_menu_btn)
        self._menu_actions = {}
        for key in ("all", "none", "template"):
            action = self.awakening_menu.addAction(awt.menu_texts()[key])
            action.triggered.connect(lambda _checked=False, k=key: self._menu_pick(k))
            self._menu_actions[key] = action
        self.awakening_menu_btn.setMenu(self.awakening_menu)
        awk.addWidget(self.awakening_menu_btn)
        lay.addLayout(awk)
        self.awakening_group, row = self._node_row(color)
        self.awakening_group.idToggled.connect(self._on_node_toggled)
        lay.addLayout(row)
        lay.addLayout(resonance_row)

        lay.addWidget(self._caption(_L('弧盘')))
        self.fork_combo = QComboBox()
        lay.addWidget(self.fork_combo)
        lay.addWidget(self._caption(_L('精炼')))
        self.refine_group, row = self._level_row(range(1, 6), "#f0883e")
        lay.addLayout(row)

        lay.addWidget(self._caption(_L('卡带套装')))
        self.suit_combo = QComboBox()
        lay.addWidget(self.suit_combo)
        lay.addStretch()

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        return label

    @staticmethod
    def _node_row(color: str):
        """Six check toggles (ids 1..6 = Effect1..Effect6), several at once, in any order."""
        group = QButtonGroup()
        group.setExclusive(False)
        row = QHBoxLayout()
        row.setSpacing(4)
        for value in range(1, 7):
            btn = QPushButton(str(value))
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setMinimumWidth(24)
            btn.setStyleSheet(
                "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
                "padding:0px;min-width:0px;font-weight:700;}"
                f"QPushButton:checked{{background:{theme_color(color)};color:#0d1117;font-weight:800;"
                f"border-color:{theme_color(color)};}}")
            group.addButton(btn, value)
            row.addWidget(btn)
        return group, row

    # ── awakening selection ──
    def selection(self):
        """team_awakening.AwakeningSel of the toggles (level = count)."""
        from src.services import team_awakening

        effects = tuple(team_awakening.NODE_IDS[i - 1] for i in range(1, 7)
                        if self.awakening_group.button(i) is not None and self.awakening_group.button(i).isChecked())
        return team_awakening.AwakeningSel(len(effects), effects)

    def template_selection(self):
        """The graduation template's own selection (list_template_characters; never hard-coded)."""
        from src.services import team_awakening

        tpl = self._page.template(self.character_combo.currentData()) or {}
        ids = tpl.get("selected_awaken_effect_ids")
        return team_awakening.normalize(tpl.get("awakening_level", 0), ids if isinstance(ids, (list, tuple)) else None)

    def set_selection(self, selection, *, notify: bool = True) -> None:
        """Check exactly the selected effects (one change signal at the end)."""
        from src.services import team_awakening

        sel = team_awakening.coerce(selection, team_awakening.EMPTY)
        self.awakening_group.blockSignals(True)
        try:
            for i in range(1, 7):
                button = self.awakening_group.button(i)
                if button is not None:
                    button.setChecked(team_awakening.NODE_IDS[i - 1] in sel.effects)
        finally:
            self.awakening_group.blockSignals(False)
        self._refresh_awakening()
        if notify:
            self.awakening_changed.emit()

    def _on_node_toggled(self, _id: int, _on: bool) -> None:
        self._refresh_awakening()
        self.awakening_changed.emit()

    def _menu_pick(self, key: str) -> None:
        from src.services import team_awakening

        choice = {"all": team_awakening.TEMPLATE, "none": team_awakening.EMPTY}.get(key)
        self.set_selection(self.template_selection() if choice is None else choice)

    def _refresh_awakening(self) -> None:
        """Count caption and resonance dots (on at 3 / 6 selected effects, whatever they are)."""
        from src.features.team_simulation import awakening_text as awt

        count = self.selection().count
        self.awakening_caption.setText(awt.count_caption(count))
        effects = {str(e.get("effect_id")): e for e in self._page.awaken_effects(self.character_combo.currentData())}
        for level, label in self.resonance_labels.items():
            active = count >= level
            label.setText(awt.resonance_caption(level) + (" ●" if active else " ○"))
            label.setStyleSheet(themed_style("color:#3fb950;font-size:11px;font-weight:700" if active
                                             else "color:#8b949e;font-size:11px"))
            effect = effects.get(f"resonance_{level}")
            # review UX F3: rich text, so Qt word-wraps it (a plain-text tooltip is one line as wide as the text)
            label.setToolTip(translated_as_is(awt.resonance_tooltip(effect, level, active,
                                                                    self._node_info(f"resonance_{level}")))
                             if effect else "")

    def _node_info(self, node):
        try:
            from src.services.awakening_node_rules import node_info

            return node_info(int(self.character_combo.currentData()), node)
        except Exception:
            return None

    def retranslate(self) -> None:
        """Texts and tooltips again (character changes call it too); tooltips are rich text that wraps (UX F3)."""
        from src.features.team_simulation import awakening_text as awt

        menu = awt.menu_texts()
        for key, action in self._menu_actions.items():
            action.setText(menu[key])
        self.awakening_menu_btn.setToolTip(menu["tip"])
        effects = {str(e.get("effect_id")): e for e in self._page.awaken_effects(self.character_combo.currentData())}
        for i in range(1, 7):
            button = self.awakening_group.button(i)
            node = f"Effect{i}"
            effect = effects.get(node)
            if button is not None:
                button.setToolTip(translated_as_is(awt.node_tooltip(effect, self._node_info(node))) if effect
                                  else awt.node_caption(node))
        self._refresh_awakening()

    @staticmethod
    def _level_row(values, color: str):
        group = QButtonGroup()
        group.setExclusive(True)
        row = QHBoxLayout()
        row.setSpacing(4)
        for value in values:
            btn = QPushButton(str(value))
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setMinimumWidth(24)
            btn.setStyleSheet(
                "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
                "padding:0px;min-width:0px;font-weight:700;}"
                f"QPushButton:checked{{background:{theme_color(color)};color:#0d1117;font-weight:800;"
                f"border-color:{theme_color(color)};}}")
            group.addButton(btn, value)
            row.addWidget(btn)
        return group, row

    def load_characters(self, templates: list[dict], default_index: int) -> None:
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        for tpl in templates:
            icon_path = self._page.icon_path(tpl["character_id"])
            if icon_path:
                self.character_combo.addItem(QIcon(str(icon_path)), tpl["name_zh"], tpl["character_id"])
            else:
                self.character_combo.addItem(tpl["name_zh"], tpl["character_id"])
        self.character_combo.setCurrentIndex(default_index)
        self.character_combo.blockSignals(False)
        self._on_character_changed()

    def _on_character_changed(self) -> None:
        cid = self.character_combo.currentData()
        tpl = self._page.template(cid)
        if tpl is None:
            return
        icon_path = self._page.icon_path(cid)
        pix = QPixmap(str(icon_path)) if icon_path else QPixmap()
        self.avatar.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                              if not pix.isNull() else QPixmap())
        self.set_selection(self.template_selection())       # the template's own node set (A13)
        self.retranslate()
        self.refine_group.button(max(1, min(5, int(tpl["fork_refinement_level"])))).setChecked(True)
        self.fork_combo.clear()
        for fork in self._page.forks_for(tpl):
            self.fork_combo.addItem(self._fork_label(fork), fork["fork_id"])
        index = self.fork_combo.findData(tpl["fork_id"])
        self.fork_combo.setCurrentIndex(max(0, index))
        self.suit_combo.clear()
        for suit in self._page.suits:
            self.suit_combo.addItem(suit["name_zh"], suit["suit_id"])
        index = self.suit_combo.findData(tpl["suit_id"])
        self.suit_combo.setCurrentIndex(max(0, index))

    @staticmethod
    def _fork_label(fork: dict):
        """Arc name; another character's exclusive arc (rule A: same type) gets "(<owner> 专属)".  Game names stay
        Chinese data pieces, so the display layer translates them and the label re-renders on a language switch."""
        if not fork.get("foreign_exclusive"):
            return fork["name_zh"]
        owners = "、".join(fork.get("owner_names_zh") or ())
        label = _L('专属')
        for piece in (" ", owners, " (", fork["name_zh"]):      # prepended one by one: each name stays its own piece
            label = piece + label
        return label + ")"

    def spec(self):
        from src.services.team_simulation_service import MemberSpec

        selection = self.selection()
        return MemberSpec(
            character_id=int(self.character_combo.currentData()),
            awakening_level=selection.level,
            fork_id=self.fork_combo.currentData(),
            fork_refinement_level=self.refine_group.checkedId(),
            suit_id=self.suit_combo.currentData(),
            awakening_effects=tuple(selection.effects),
        )


class TeamSimulationPage(QWidget):
    DEFAULT_TEAM = (1003, 1019, 1021, 1071)

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        context = window.app_context
        self._static_path = context.paths.static_database_path
        self._asset_root = context.paths.game_ui_asset_root
        self._worker = None
        self._last_result = None
        self._mode = "approved"             # "approved" | "custom"
        self._results = {"approved": None, "custom": None}      # each mode keeps its own last result
        self._result_puka = {"approved": None, "custom": None}  # Puka Boot Camp level each result was calculated at
        self._job_mode = "approved"
        self._job_puka_level = 0
        self._custom_panel = None           # built the first time the custom mode is used
        self._applying_team = False
        self._team_touched = False          # a member card changed its character in this session
        self._catalog = None
        self._fork_cache: dict = {}
        self._awaken_catalog = None         # {cid: awakening nodes} for the cards' tooltips (loaded on first use)
        self._attr_names = None
        self._explain_open: dict = {}       # expanded sections of the explanation panel, kept across re-renders

        from src.services import team_simulation_service as svc

        self.templates = svc.list_template_characters(self._static_path)
        self.suits = svc.list_suits(self._static_path)
        self._by_id = {t["character_id"]: t for t in self.templates}
        self._puka_level = self._puka_training_level()      # shown in the notes; the engine reads the same account

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(24, 18, 24, 24)
        lay.setSpacing(14)

        title = QLabel(_L('队伍模拟 (Beta)'))
        title.setStyleSheet(themed_style("font-size:22px;font-weight:800;color:#f0f6fc"))
        preview = QLabel(_L('未完成'))
        preview.setStyleSheet(themed_style(
            "background:#3d2f00;color:#e3b341;border:1px solid #9e6a03;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700"))
        head = QHBoxLayout()
        head.addWidget(title)
        head.addWidget(preview)
        head.addStretch()
        lay.addLayout(head)
        sub = QLabel(_L('直观查看整支队伍的模拟结果。'))
        sub.setStyleSheet(themed_style("color:#8b949e"))
        lay.addWidget(sub)
        beta = QLabel(_L('该功能尚未完成，角色循环的审核还不完善，结果可能与实战不同。'))
        beta.setWordWrap(True)
        beta.setStyleSheet(themed_style("color:#e3b341;font-weight:700"))
        lay.addWidget(beta)
        steps = QHBoxLayout()
        for i, text in enumerate((_L('1. 选择队员'), _L('2. 设置各队员'), _L('3. 计算队伍模拟'))):
            if i:
                arrow = QLabel("→")
                arrow.setStyleSheet(themed_style("color:#8b949e"))
                steps.addWidget(arrow)
            steps.addWidget(_chip(text))
        steps.addStretch()
        lay.addLayout(steps)
        note = QLabel(self._template_note_text())
        note.setStyleSheet(themed_style("color:#8b949e;font-size:12px;font-style:italic"))
        lay.addWidget(note)
        self._template_note = note

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = []
        for slot in range(TEAM_SIZE):
            card = _MemberCard(self, slot)
            grid.addWidget(card, 0, slot)
            self.cards.append(card)
        lay.addLayout(grid)
        ids = [t["character_id"] for t in self.templates]
        for slot, card in enumerate(self.cards):
            want = self.DEFAULT_TEAM[slot]
            card.load_characters(self.templates, ids.index(want) if want in ids else slot)
        for card in self.cards:
            card.character_combo.currentIndexChanged.connect(lambda *_a: self._on_team_changed())
            card.awakening_changed.connect(self._on_awakening_changed)

        lay.addWidget(self._build_notice())

        # mode switch: the reviewed rotations (default) or a cycle the user types
        modes = QHBoxLayout()
        modes.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.approved_mode_btn = QPushButton(_L('已审核循环'))
        self.custom_mode_btn = QPushButton(_L('直接输入'))
        for button, mode in ((self.approved_mode_btn, "approved"), (self.custom_mode_btn, "custom")):
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(themed_style(
                "QPushButton{background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;"
                "padding:4px 14px;font-weight:700}"
                "QPushButton:checked{background:#4f46e5;color:white;border-color:#4f46e5}"))
            self.mode_group.addButton(button)
            button.clicked.connect(lambda _checked=False, m=mode: self.set_mode(m))
            modes.addWidget(button)
        self.approved_mode_btn.setChecked(True)
        modes.addStretch()
        lay.addLayout(modes)

        # simulation options; cycle reactions are always computed, so there is no on/off control
        options = QHBoxLayout()
        options.setSpacing(8)
        self._order_caption = _option_caption(_L('出场顺序'))
        options.addWidget(self._order_caption)
        self.order_combo = QComboBox()
        self.order_combo.addItem(_L('自动（变身输出优先）'), "plan")
        self.order_combo.addItem(_L('自动（环合最多）'), "auto")
        self.order_combo.addItem(_L('按编队顺序'), "slot")
        options.addWidget(self.order_combo)
        # follow the item texts after a live language switch (the default keeps the first-show width)
        self.order_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        options.addStretch()
        lay.addLayout(options)
        # resource model (team_resources): ultimate energy / cooldown checks and the gauge refill rule; its own row,
        # so the order combo keeps its width after a language switch
        options = QHBoxLayout()
        options.setSpacing(8)
        self._resource_caption = _option_caption(_L('资源模型'))
        options.addWidget(self._resource_caption)
        self.resource_combo = QComboBox()
        self.resource_combo.addItem(_L('游戏数据 + 社区冷却'), "community")
        self.resource_combo.addItem(_L('游戏数据'), "data")
        self.resource_combo.addItem(_L('旧规则（第 1、3 轮补满，不检查能量与冷却）'), "legacy")
        from src.services.team_resources import DEFAULT_RESOURCE_MODEL

        self.resource_combo.setCurrentIndex(max(0, self.resource_combo.findData(DEFAULT_RESOURCE_MODEL)))
        self.resource_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.resource_combo.setToolTip(self._resource_tip())
        self.resource_combo.currentIndexChanged.connect(self._on_resource_model_changed)
        options.addWidget(self.resource_combo)
        options.addStretch()
        lay.addLayout(options)
        # three loops (team_simulation_service.DEFAULT_LOOPS); every gauge is 100 at the start of loops 1 and 3
        # (team_cycle_reactions.FULL_GAUGE_LOOPS), loop 2 keeps the built-up gauge: fixed, no control for it.
        # Its own line: the long translated caption must not squeeze the order combo.
        loop_rule = _option_caption(self._loop_rule_text())
        loop_rule.setWordWrap(True)
        lay.addWidget(loop_rule)
        self._loop_rule = loop_rule
        self._custom_slot = QVBoxLayout()       # the custom-cycle panel goes here when the mode is first used
        self._custom_slot.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self._custom_slot)

        actions = QHBoxLayout()
        self.calc_btn = QPushButton(_L('计算队伍'))
        self.calc_btn.setMinimumHeight(44)
        self.calc_btn.setStyleSheet(themed_style(
            "QPushButton{background:#4f46e5;color:white;border:none;border-radius:6px;font-size:15px;font-weight:700}"
            "QPushButton:hover{background:#6366f1}QPushButton:disabled{background:#30363d;color:#8b949e}"))
        self.calc_btn.clicked.connect(self._calculate)
        actions.addWidget(self.calc_btn, 1)
        lay.addLayout(actions)

        self.status = QLabel("")
        self.status.setStyleSheet(themed_style("color:#8b949e"))
        lay.addWidget(self.status)

        self.result_box = QFrame()
        self.result_box.setObjectName("card")
        self.result_layout = QVBoxLayout(self.result_box)
        self.result_layout.setContentsMargins(16, 14, 16, 16)
        self.result_layout.setSpacing(10)
        self.result_box.setVisible(False)
        lay.addWidget(self.result_box)
        lay.addStretch()

        try:
            from src import i18n_runtime

            i18n_runtime.add_listener(lambda _code: self._rerender())
        except Exception:
            pass
        try:        # saved cycles are per account
            subscribe = getattr(context, "subscribe_account_changed", None)
            if subscribe is not None:
                subscribe(lambda *_a: self._on_account_changed())
        except Exception:
            pass
        self._restore_last_mode()

    # ── custom-cycle mode ──────────────────────────────────────────
    def custom_store_path(self):
        """<account config dir>/team_custom_cycles.json, or None when the account has no config folder."""
        account = getattr(self._window.app_context, "account", None)
        config_dir = getattr(account, "user_config_dir", None)
        if not config_dir:
            return None
        from src.services.team_custom_cycle_store import path_for

        return path_for(config_dir)

    def team_json(self) -> list:
        """The four member cards as stored with a saved cycle (A14: the node set under ``selected_awaken_effect_ids``,
        plain str ids; ``awakening_level`` = its count, so an older version reads Effect1..count)."""
        out = []
        for card in self.cards:
            spec = card.spec()
            out.append({"character_id": spec.character_id, "awakening_level": spec.awakening_level,
                        "selected_awaken_effect_ids": [str(e) for e in spec.awakening_effects or ()],
                        "fork_id": spec.fork_id, "fork_refinement_level": spec.fork_refinement_level,
                        "suit_id": spec.suit_id})
        return out

    def apply_team(self, team) -> None:
        """Set the member cards from a saved cycle (unknown characters / forks keep the card's own value)."""
        def number(value, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError, OverflowError):
                return default

        self._applying_team = True
        try:
            for card, row in zip(self.cards, team if isinstance(team, (list, tuple)) else ()):
                if not isinstance(row, dict):
                    continue
                index = card.character_combo.findData(row.get("character_id"))
                if index < 0:
                    continue
                card.character_combo.setCurrentIndex(index)
                # A14: the saved node set; a row without one (older saves) = Effect1..awakening_level; a malformed
                # value keeps the template's selection (team_awakening.from_json_row)
                from src.services import team_awakening

                card.set_selection(team_awakening.from_json_row(row, template=card.template_selection()))
                button = card.refine_group.button(number(row.get("fork_refinement_level"), 1))
                if button is not None:
                    button.setChecked(True)
                for combo, key in ((card.fork_combo, "fork_id"), (card.suit_combo, "suit_id")):
                    found = combo.findData(row.get(key))
                    if found >= 0:
                        combo.setCurrentIndex(found)
        finally:
            self._applying_team = False
        self._on_team_changed()

    def _ensure_custom_panel(self):
        if self._custom_panel is None:
            from src.features.team_simulation.custom_panel import CustomCyclePanel

            panel = CustomCyclePanel(self)
            panel.changed.connect(self._update_calc_enabled)
            panel.status_message.connect(self.status.setText)
            panel.load_approved_requested.connect(self._load_approved)
            self._custom_slot.addWidget(panel)
            self._custom_panel = panel
            panel.reload_store()            # again, now that its messages reach the status line
        return self._custom_panel

    def resource_model(self) -> str:
        """The selected resource model (team_resources.RESOURCE_MODELS)."""
        combo = getattr(self, "resource_combo", None)
        value = combo.currentData() if combo is not None else None
        if value:
            return str(value)
        from src.services.team_resources import DEFAULT_RESOURCE_MODEL

        return DEFAULT_RESOURCE_MODEL

    @staticmethod
    def _resource_tip() -> str:
        """Tooltip of the resource-model combo (built at render time: a language switch re-sets it)."""
        return _L('资源模型决定检查哪些数值：\n· 游戏数据 + 社区冷却（默认）：游戏数据，加上社区资料（prydwen）的变轨技能与极轨终结冷却\n· 游戏数据：只用游戏数据（卡厄斯的极轨终结冷却、浔的时计等）\n· 旧规则：不检查冷却与能量，第 1、3 轮开始时环合值补满 100\n缺少数据的队员在结果说明中标出，不检查')  # noqa: E501

    def _loop_rule_text(self):
        if self.resource_model() == "legacy":
            return _L('3 轮循环 · 第 1、3 轮开始时所有队员环合值为 100（第 2 轮沿用累积值）')
        return _L('3 轮循环 · 第 1 轮开始时环合值为 100，之后按命中累积（缺少数据的队员第 3 轮补满）')

    def _on_resource_model_changed(self, *_args) -> None:
        if not getattr(self, "_restoring_model", False):
            self._save_resource_model()
        if hasattr(self, "_loop_rule"):
            self._loop_rule.setText(self._loop_rule_text())
        if hasattr(self, "_notice_body"):
            self._notice_body.setText(self._notice_text())
        if self._custom_panel is not None and hasattr(self._custom_panel, "on_resource_model_changed"):
            self._custom_panel.on_resource_model_changed(self.resource_model())

    def set_mode(self, mode: str) -> None:
        """Switch between the reviewed rotations and the custom cycle; each mode shows its own last result."""
        mode = "custom" if mode == "custom" else "approved"
        first_use = mode == "custom" and self._custom_panel is None
        if mode == "custom":
            panel = self._ensure_custom_panel()
            if first_use:       # continue the last working cycle: made for the team on the cards, or - while
                # no card was changed in this session - together with its own team (a restart shows the default
                # team, and the next calculation would overwrite a working cycle that was never shown)
                last = panel._file.last if isinstance(panel._file.last, dict) else None
                stored = (last or {}).get("cycle")
                stored = stored if isinstance(stored, dict) else {}
                rows = stored.get("team") if isinstance(stored.get("team"), list) else []
                cycle_team = [m.get("character_id") for m in rows if isinstance(m, dict)]
                try:
                    if cycle_team == panel.team():
                        panel.apply_cycle(stored, set_team=False)
                    elif cycle_team and stored.get("steps") and not self._team_touched:
                        panel.apply_cycle(stored, set_team=True)
                except Exception:       # a damaged working state never keeps the mode from opening
                    pass
        self._mode = mode
        (self.custom_mode_btn if mode == "custom" else self.approved_mode_btn).setChecked(True)
        approved = mode == "approved"
        for widget in (self._order_caption, self.order_combo, self._loop_rule):
            widget.setVisible(approved)
        if self._custom_panel is not None:
            self._custom_panel.setVisible(not approved)
        self._notice_body.setText(self._notice_text())
        self._last_result = self._results.get(mode)
        if self._last_result is not None:
            self._render(self._last_result)
        else:
            self._clear_results()
            self.result_box.setVisible(False)
        self._update_calc_enabled()

    def _save_resource_model(self) -> None:
        """Remember the resource model the user picked (working-state entry of the account's cycle file)."""
        try:
            if self._custom_panel is not None:
                self._custom_panel.save_last(self._mode)      # its options carry the model
            path = self.custom_store_path()
            if path is None:
                return
            from src.services import team_custom_cycle_store as store

            last = store.load(path).last if path.is_file() else None
            last = dict(last) if isinstance(last, dict) else {"mode": self._mode}
            last["resource_model"] = self.resource_model()
            store.save_last(path, last)
        except Exception:
            pass

    def _restore_resource_model(self, last) -> None:
        from src.services.team_resources import RESOURCE_MODELS

        if not isinstance(last, dict):
            return
        model = last.get("resource_model")
        if model is None and isinstance(last.get("cycle"), dict):
            model = (last["cycle"].get("options") or {}).get("resource_model")
        if model not in RESOURCE_MODELS or model == self.resource_model():
            return
        self._restoring_model = True
        try:
            self.resource_combo.setCurrentIndex(max(0, self.resource_combo.findData(model)))
        finally:
            self._restoring_model = False

    def _restore_account_model(self) -> None:
        """After an account switch: that account's remembered resource model, else the default."""
        from src.services.team_resources import DEFAULT_RESOURCE_MODEL

        last = None
        try:
            path = self.custom_store_path()
            if path is not None and path.is_file():
                from src.services import team_custom_cycle_store as store

                last = store.load(path).last
        except Exception:
            last = None
        model = None
        if isinstance(last, dict):
            model = last.get("resource_model")
            if model is None and isinstance(last.get("cycle"), dict):
                model = (last["cycle"].get("options") or {}).get("resource_model")
        self._restore_resource_model({"resource_model": model or DEFAULT_RESOURCE_MODEL})

    def _restore_last_mode(self) -> None:
        """Page build: come back in the custom mode with its working cycle when that is where the user left."""
        try:
            path = self.custom_store_path()
            if path is None or not path.is_file():
                return
            from src.services.team_custom_cycle_store import load

            file = load(path)
            self._restore_resource_model(file.last)
            if file.moved_aside:
                from src.features.team_simulation.custom_view import moved_aside_text

                self.status.setText(moved_aside_text(file.moved_aside))
            last = file.last
            if isinstance(last, dict) and last.get("mode") == "custom":
                self._ensure_custom_panel().restore_last()
                self.set_mode("custom")
        except Exception:
            pass

    def _on_account_changed(self) -> None:
        try:
            self._restore_account_model()   # the new account's resource model (review F7)
        except RuntimeError:        # the page's widgets are gone (the subscription outlives the page)
            pass
        try:
            if self._custom_panel is not None:
                self._custom_panel.reload_store()
            self._refresh_puka_note()       # the new account's level (showEvent does not fire on a switch)
        except RuntimeError:        # the page's widgets are gone (the subscription outlives the page)
            pass

    def _on_awakening_changed(self) -> None:
        """Custom cycles: cooldown rules unlocked by an awakening effect (Linko ③, Haniel ⑥, Mint ①) follow the
        cards' node sets."""
        try:
            if self._custom_panel is not None and hasattr(self._custom_panel, "on_awakening_changed"):
                self._custom_panel.on_awakening_changed()
        except RuntimeError:
            pass

    def _on_team_changed(self) -> None:
        if self._applying_team:
            return
        self._team_touched = True
        if self._custom_panel is not None:
            self._custom_panel.on_team_changed()
        self._update_calc_enabled()

    def _update_calc_enabled(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        ready = self._mode != "custom" or (self._custom_panel is not None and self._custom_panel.is_valid())
        self.calc_btn.setEnabled(bool(ready))

    def _load_approved(self, rounds: int = 1) -> None:
        """Custom mode: replace the sequence with the current team's reviewed rotation - one loop, or (more than
        one round asked for) the whole reviewed run: the same entries and reactions as the reviewed mode."""
        whole_run = int(rounds or 1) > 1
        if self._worker is not None and self._worker.isRunning():
            return
        specs = [card.spec() for card in self.cards]
        if len({s.character_id for s in specs}) < len(specs):
            self.status.setText(_L('同一角色不能重复编入队伍。'))
            return
        account = self._window.app_context.account
        static_path = self._static_path
        order_mode = self.order_combo.currentData() or "plan"
        resource_model = self.resource_model()
        approved = self._results.get("approved")
        order = None
        team = sorted(s.character_id for s in specs)
        if approved is not None and getattr(approved, "explanation", None) is not None \
                and sorted(approved.explanation.order) == team:
            order = tuple(approved.explanation.order)       # the order the reviewed mode last used for this team

        def job():
            from src.services.team_custom_cycle_service import approved_as_sequence

            return approved_as_sequence(static_path, account.user_database_path, account.active_account_id, specs,
                                        order=order, order_mode=order_mode, whole_run=whole_run,
                                        resource_model=resource_model)

        def done(steps) -> None:
            if whole_run:
                from src.services.team_simulation_service import DEFAULT_LOOPS

                self.status.setText(_LF('已读取 {0} 轮已审核循环（重复次数设为 1）；选项为默认值时结果与已审核循环模式相同。')
                                    .format(DEFAULT_LOOPS))
            else:
                self.status.setText(_L('已读取 1 轮已审核循环，可用重复次数延长。'))
            panel = self._ensure_custom_panel()
            panel.repeat_count_spin.setValue(1)
            panel.set_steps(steps)
            self._update_calc_enabled()

        self.calc_btn.setEnabled(False)
        self.status.setText(_L('正在计算…'))
        self._worker = WorkerThread(job, self)
        self._worker.result_ready.connect(done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _save_last_mode(self) -> None:
        """Remember that the reviewed mode was used last (only when a working cycle is stored already)."""
        try:
            if self._custom_panel is not None:
                self._custom_panel.save_last("approved")
                return
            path = self.custom_store_path()
            if path is None or not path.is_file():
                return
            from src.services import team_custom_cycle_store as store

            last = store.load(path).last
            if isinstance(last, dict) and last.get("mode") != "approved":
                store.save_last(path, dict(last, mode="approved"))
        except Exception:
            pass

    def buff_line(self, buff: dict, names: dict) -> str:
        """One line of the team buff list: source, modifiers, windows (custom mode: manual / switched-off marks)."""
        from src.i18n_display import tr

        mods = ", ".join(self._modifier_text(m["property_id"], m["value"])
                         for m in buff["modifiers"] if m["value"] is not None)
        if mods and int(buff.get("count") or 1) > 1:     # separate buffs with the same value and windows
            mods = f"{mods} ×{int(buff['count'])}"
        # every window the engine applied the buff in (older results: the first window only)
        windows = buff.get("windows") or [(buff["start_s"], buff["end_s"])]
        if buff.get("manual"):
            from src.features.team_simulation.custom_view import result_buff_label, result_buff_value

            source = result_buff_label(buff, names)
            mods = result_buff_value(buff)      # the label names the kind already: only the typed value
        else:
            source = tr(names.get(buff["source_character_id"], str(buff["source_character_id"])))
        text = _LF('{0}：{1}（{2}）').format(source, mods or "—", ", ".join(f"{a:.1f}s ~ {b:.1f}s" for a, b in windows))
        if buff.get("skipped"):
            from src.features.team_simulation.custom_view import manual_skipped_text

            text = text + " " + manual_skipped_text()
        elif buff.get("enabled") is False:
            text = text + " " + _L('（已关闭）')
        return text

    # ── data helpers ───────────────────────────────────────────────
    def template(self, cid):
        return self._by_id.get(cid)

    def awaken_effects(self, cid) -> list:
        """Awakening nodes of a character (effects + resonances) for the cards' tooltips, [] when unknown."""
        if getattr(self, "_awaken_catalog", None) is None:
            try:
                from src.services.team_simulation_service import awaken_effect_catalog

                self._awaken_catalog = awaken_effect_catalog(self._static_path)
            except Exception:
                self._awaken_catalog = {}
        try:
            return list(self._awaken_catalog.get(int(cid)) or ())
        except (TypeError, ValueError):
            return []

    def icon_path(self, cid):
        if self._catalog is None:
            from src.services.game_ui_asset_catalog import GameUiAssetCatalog

            self._catalog = GameUiAssetCatalog(self._asset_root)
        try:
            return self._catalog.character_icon(int(cid))
        except Exception:
            return None

    def forks_for(self, tpl):
        """Arcs the member can equip: same type as the character (rule A, as the official calculator), other
        characters' exclusive arcs included and labelled (the arc efficiency table's † arcs open here too)."""
        key = (tpl["character_id"], tpl["fork_id"])
        if key not in self._fork_cache:
            from src.services.team_simulation_service import equippable_forks, list_forks_for

            forks = equippable_forks(self._static_path, tpl["character_id"], include_foreign=True)
            if not any(f["fork_id"] == tpl["fork_id"] for f in forks):     # data without group types: old rule
                forks = list_forks_for(self._static_path, tpl["fork_id"], tpl["character_id"])
            self._fork_cache[key] = forks
        return self._fork_cache[key]

    # ── notice ─────────────────────────────────────────────────────
    def _build_notice(self) -> QFrame:
        box = QFrame()
        box.setObjectName("card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 12)
        toggle = QPushButton(_L('⚠ 注意事项'))
        toggle.setCheckable(True)
        toggle.setStyleSheet(themed_style(
            "QPushButton{background:transparent;border:none;color:#e3b341;font-weight:800;text-align:left;font-size:14px}"))
        lay.addWidget(toggle)
        body = QLabel(self._notice_text())
        body.setWordWrap(True)
        body.setStyleSheet(themed_style("color:#c9d1d9;line-height:150%"))
        body.setVisible(False)
        toggle.toggled.connect(body.setVisible)
        lay.addWidget(body)
        self._notice_body = body
        return box

    def _puka_training_level(self) -> int:
        """Puka Boot Camp level of the current account (the stat reconstruction reads the same account copy)."""
        try:
            from src.services.puka_training_settings_service import PukaTrainingSettingsService

            path = self._window.app_context.account.user_database_path
            if path is None or not Path(path).is_file():
                return 0
            return int(PukaTrainingSettingsService(path).load().level)
        except Exception:  # noqa: BLE001 - an unreadable account only loses the note, never the page
            return 0

    def _template_note_text(self):
        return _LF('（各队员的驱动与主/副词条按官方毕业模板计算；噗卡特训按账号 Lv.{0}）').format(self._puka_level)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # the level is entered on the character page: re-read it whenever the page comes back
        self._refresh_puka_note()

    def _refresh_puka_note(self) -> None:
        """Re-read the account level; on a change update the notes and flag a result calculated at another level."""
        level = self._puka_training_level()
        if level == self._puka_level:
            return
        self._puka_level = level
        self._template_note.setText(self._template_note_text())
        self._notice_body.setText(self._notice_text())
        if self._last_result is not None:
            self._render(self._last_result)
            shown = self._result_puka.get(self._mode)
            if shown is not None and shown != level:
                self.status.setText(_LF('噗卡特训等级已变为 Lv.{0}，当前结果按 Lv.{1} 计算，请重新计算。')
                                    .format(level, shown))

    def _notice_text(self) -> str:
        """The assumptions; the custom-cycle line is listed while that mode is active."""
        # built with `+`: str.join drops the translation provenance, so a live language switch would miss it
        legacy = self.resource_model() == "legacy"
        lines = (
            _L('队伍模拟仅用于粗略比较队伍强度，不代表实战结果。'),
            "",
            _L('基本假设：'),
            _L('- 敌人 80 级、抗性 20%，原地不动的训练木桩'),
            _L('- 驱动与主/副词条按官方毕业模板'),
            _LF('- 噗卡特训：按当前账号 Lv.{0} 计算（0 = 未录入，可在角色页录入）').format(self._puka_level),
            _L('- 动作：各队员按已审核的循环行动，出场顺序与登场方式见结果下方的说明'),
            (_L('- 不检查冷却时间与能量') if legacy
             else _L('- 冷却时间与极轨终结能量：只按游戏数据检查；缺少数据的队员在说明中标出（不检查）')
             if self.resource_model() == "data"
             else _L('- 冷却时间与极轨终结能量：按游戏数据检查（默认含社区冷却）；缺少数据的队员在说明中标出（不检查）')),
            _L('- 环合反应：切换到相邻属性队员时一并计算（创生、覆纹、浊燃、黯星、浸染、延滞及盈蓄、失谐）'),
            _L('- 环合值按每次命中累积，满 100 后切换才触发（规则待实战确认）'),
            (_L('- 循环：3 轮，第 1、3 轮开始时环合值补满 100，第 2 轮按累积的环合值判定') if legacy
             else _L('- 循环：3 轮，第 1 轮开始时环合值为 100，之后按命中累积（缺少数据的队员在第 3 轮开始时补满 100）')),
            _L('- 变身/形态角色：形态中的动作按动画数据计算伤害，形态时间按游戏数据'),
            _L('- 环合反应伤害由等级、环合强度与敌方防御/抗性决定，不受攻击力 Buff 影响'),
            _L('- 时间：极轨终结演出按实测时停扣除，DPS 按扣除时停后的战斗时间计算'),
            _L('- 召唤物与残虹、安魂曲以外的持续伤害未计入'),
            _L('- 战斗引擎无法解析的 Buff 不计入'),
        )
        if not legacy and getattr(self, "_mode", "approved") != "custom":     # D3 (custom: the strict label)
            from src.services.team_resources import SWAP_MIN_WAIT_S

            lines = lines + (_LF('- 技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员（冷却还差不到 {0:.1f} 秒时等待后使用）；单人时原地等待').format(
                SWAP_MIN_WAIT_S),)
        if getattr(self, "_mode", "approved") == "custom":
            lines = lines + (_L('- 直接输入模式：按输入的顺序行动，援护技、冷却、Buff 与数值可在选项中调整'),)
        text = lines[0]
        for line in lines[1:]:
            text = text + "\n" + line
        return text

    # ── calculation ────────────────────────────────────────────────
    def _calculate(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        specs = [card.spec() for card in self.cards]
        if len({s.character_id for s in specs}) < len(specs):
            self.status.setText(_L('同一角色不能重复编入队伍。'))
            return
        context = self._window.app_context
        account = context.account
        static_path = self._static_path
        if self._mode == "custom":
            self._calculate_custom(specs, account, static_path)
            return
        self._job_mode = "approved"
        self._job_puka_level = self._puka_training_level()     # the level the engine reads for this job
        self._save_last_mode()
        order_mode = self.order_combo.currentData() or "plan"
        resource_model = self.resource_model()
        from src.services.team_simulation_service import DEFAULT_LOOPS

        def job():
            from src.services.team_simulation_service import simulate_team

            return simulate_team(static_path, account.user_database_path, account.active_account_id, specs,
                                 order_mode=order_mode, loops=DEFAULT_LOOPS, gauge_rule="game", opening_gauge="full",
                                 resource_model=resource_model)

        self.calc_btn.setEnabled(False)
        self.status.setText(_L('正在计算…（比较出场顺序）') if order_mode == "plan" else _L('正在计算…'))
        self._worker = WorkerThread(job, self)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _calculate_custom(self, specs, account, static_path) -> None:
        """Custom mode: simulate the panel's sequence with its options (the same engine path)."""
        panel = self._ensure_custom_panel()
        panel.apply_text_now()              # a text edit still waiting for its pause
        if not panel.is_valid():
            self.status.setText(panel.first_error() or _L('请先输入循环。'))
            self._update_calc_enabled()
            return
        steps, options = panel.steps(), panel.options()
        import dataclasses

        if hasattr(options, "resource_model"):      # the page's resource model decides the data level
            options = dataclasses.replace(options, resource_model=self.resource_model())
        panel.save_last("custom")           # the working state survives a restart
        self._job_mode = "custom"
        self._job_puka_level = self._puka_training_level()

        def job():
            from src.services.team_custom_cycle_service import simulate_custom

            return simulate_custom(static_path, account.user_database_path, account.active_account_id, specs,
                                   steps, options)

        self.calc_btn.setEnabled(False)
        self.status.setText(_L('正在计算…'))
        self._worker = WorkerThread(job, self)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_error(self, message: str) -> None:
        self.calc_btn.setEnabled(True)
        self.status.setText(_LF('计算失败：{0}').format((message)))
        self._update_calc_enabled()

    def _on_result(self, result) -> None:
        self.calc_btn.setEnabled(True)
        self.status.setText("")
        mode = self._job_mode
        self._results[mode] = result
        self._result_puka[mode] = self._job_puka_level
        if self._job_puka_level != self._puka_level:     # changed on the character page while this page was shown
            self._puka_level = self._job_puka_level
            self._template_note.setText(self._template_note_text())
            self._notice_body.setText(self._notice_text())
        if mode == "custom" and self._custom_panel is not None:
            self._custom_panel.set_result_buffs(getattr(result, "team_buffs", ()))
        if mode == self._mode:
            self._last_result = result
            self._render(result)
        self._update_calc_enabled()

    def _rerender(self) -> None:
        if hasattr(self, "resource_combo"):     # Qt keeps a tooltip as plain text: set it again (review F-UX5)
            self.resource_combo.setToolTip(self._resource_tip())
        for card in getattr(self, "cards", ()):     # awakening captions / tooltips (plain text in Qt)
            try:
                card.retranslate()
            except RuntimeError:
                pass
        if self._custom_panel is not None:
            self._custom_panel.retranslate()
        if self._last_result is not None:
            self._render(self._last_result)

    # ── result rendering ───────────────────────────────────────────
    def _clear_results(self) -> None:
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _render(self, result) -> None:
        self._rendering = result            # the member rows read its resource traces
        self._clear_results()
        head = QLabel(_L('📊 结果'))
        head.setStyleSheet(themed_style("font-size:17px;font-weight:800;color:#f0f6fc"))
        self.result_layout.addWidget(head)
        result_level = self._result_puka.get(self._mode)
        if result_level is not None:
            stale = result_level != self._puka_level
            level_line = QLabel(_LF('结果按噗卡特训 Lv.{0} 计算').format(result_level))
            level_line.setObjectName("teamSimResultPukaLevel")
            level_line.setStyleSheet(themed_style("color:#d29922;font-size:12px" if stale
                                                  else "color:#8b949e;font-size:12px"))
            self.result_layout.addWidget(level_line)

        totals = QHBoxLayout()
        reaction_damage = float(getattr(result, "reaction_damage", 0.0) or 0.0)
        share = reaction_damage / result.total_damage * 100.0 if result.total_damage > 0 else 0.0
        wall_time = float(getattr(result, "wall_time_s", 0.0) or 0.0)
        for title, value, color, subtitle in (
            (_L('总伤害'), _fmt_amount(result.total_damage), "#f0f6fc", ""),
            # 总时间 = battle time without time stops (the DPS denominator); the wall time is the subtitle
            (_L('总时间'), f"{result.total_time_s:.1f}s", "#3fb950",
             (_L('包含时停') + f" {wall_time:.1f}s" if wall_time > 0 else "") + self._waited_suffix(result)),
            (_L('队伍 DPS'), _fmt_amount(result.dps), "#d2a8ff", ""),
            (_L('环合反应伤害'), _fmt_amount(reaction_damage), REACTION_COLOR,
             _LF('环合反应占总伤害 {0:.1f}%').format(share)),
        ):
            card, value_label, _sub = metric_card(title, value, subtitle)
            value_label.setStyleSheet(f"color:{theme_color(color)};font-size:24px;font-weight:800")
            totals.addWidget(card)
        self.result_layout.addLayout(totals)

        members = result.members
        for slot, member in enumerate(members):
            self.result_layout.addWidget(self._member_row(slot, member, members))

        if result.team_buffs:
            buffs = QLabel(_L('已计入的队伍 Buff'))
            buffs.setStyleSheet(themed_style("font-weight:700;color:#c9d1d9;margin-top:6px"))
            self.result_layout.addWidget(buffs)
            from src.i18n_display import tr

            names = {m.character_id: m.name_zh for m in members}
            for buff in result.team_buffs:
                line = QLabel()
                line.setObjectName("teamSimBuffLine")
                line.setText(self.buff_line(buff, names))
                line.setWordWrap(True)
                # custom mode: a buff the user switched off is listed greyed
                tone = "#6e7681" if buff.get("enabled") is False else "#8b949e"
                line.setStyleSheet(themed_style(f"color:{tone};font-size:12px"))
                self.result_layout.addWidget(line)

        from src.features.team_simulation.explanation_view import render_explanation

        render_explanation(self.result_layout, getattr(result, "explanation", None), self._explain_open)
        self.result_box.setVisible(True)

    def _member_row(self, slot: int, member, members) -> QFrame:
        color = SLOT_COLORS[slot]
        row = QFrame()
        row.setObjectName("teamSimMemberRow")   # scope the border so child labels do not inherit it
        row.setStyleSheet(f"QFrame#teamSimMemberRow{{background:{theme_rgba('#161b22', 1.0)};"
                          f"border-left:4px solid {theme_color(color)};border-radius:6px}}")
        lay = QVBoxLayout(row)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        top = QHBoxLayout()
        icon = self.icon_path(member.character_id)
        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        pix = QPixmap(str(icon)) if icon else QPixmap()
        if not pix.isNull():
            avatar.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        top.addWidget(avatar)
        # names are translated by the display layer (explicit tr() where they sit inside an f-string)
        from src.i18n_display import tr

        from src.services import team_awakening

        selection = team_awakening.AwakeningSel(int(member.awakening_level),
                                                tuple(getattr(member, "awakening_effects", ()) or ()))
        from src.features.team_simulation import awakening_text as awt

        # A15: the node set; review UX F11: translated ("돌파 3 · ①③⑤"), compact_label stays for saves
        name_line = QLabel(f"{tr(member.name_zh)} ({awt.display_label(selection)})")
        name_line.setStyleSheet(themed_style("font-weight:700;color:#f0f6fc"))
        fork_line = QLabel(f"{tr(self._fork_name(member.fork_id))} · R{member.fork_refinement_level}")
        fork_line.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        names = QVBoxLayout()
        names.addWidget(name_line)
        names.addWidget(fork_line)
        top.addLayout(names, 1)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        badge = self._element_badge(getattr(member, "element", ""))
        if badge is not None:
            tags.addWidget(badge)
        role = getattr(member, "role", "")
        if role:
            role_label = QLabel(_role_text(role))
            role_label.setStyleSheet(themed_style(
                "background:#1f2a44;color:#c9d1d9;border-radius:4px;padding:1px 8px;font-size:11px;font-weight:700"))
            tags.addWidget(role_label)
        visits = int(getattr(member, "visits", 0) or 0)
        if visits:
            visit_label = QLabel(_LF('出场 {0} 次').format(visits))
            visit_label.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
            tags.addWidget(visit_label)
        for text, tone, tip in self._resource_tags(member):
            tag = QLabel(text)
            tag.setStyleSheet(themed_style(f"color:{tone};font-size:11px;font-weight:700"))
            if tip:
                tag.setToolTip(tip)
            tags.addWidget(tag)
        top.addLayout(tags)
        lay.addLayout(top)

        stats = QHBoxLayout()
        # member DPS is a share of the team DPS: (damage + reactions) / team battle time, not / on-field time
        team_time = float(getattr(member, "team_time_s", 0.0) or 0.0) or member.time_s
        dps_tip = _LF('（伤害 + 环合反应）÷ 队伍战斗时间 {0:.1f}s').format(team_time)
        for title, value, tone, tip in (
            (_L('伤害'), _fmt_amount(member.damage), "#f0f6fc", None),
            (_L('环合反应'), _fmt_amount(float(getattr(member, "reaction_damage", 0.0) or 0.0)), REACTION_COLOR, None),
            (_L('在场时间'), f"{member.time_s:.1f}s", "#3fb950", None),
            (_L('DPS 贡献'), _fmt_amount(member.dps), "#d2a8ff", dps_tip),
        ):
            col = QVBoxLayout()
            t = QLabel(title)
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet(themed_style("color:#8b949e;font-size:11px"))
            v = QLabel(value)
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet(f"color:{theme_color(tone)};font-size:16px;font-weight:800")
            if tip:
                t.setToolTip(tip)
                v.setToolTip(tip)
            col.addWidget(t)
            col.addWidget(v)
            stats.addLayout(col)
        lay.addLayout(stats)
        if member.missing_actions:
            warn = QLabel(_L('部分动作缺少动画数据，未计入伤害（结果偏低）'))
            warn.setStyleSheet(themed_style("color:#e3b341;font-size:11px"))
            lay.addWidget(warn)
        return row

    def _waited_suffix(self, result) -> str:
        expl = getattr(result, "explanation", None)
        waited = float(getattr(expl, "waited_s", 0.0) or 0.0) if expl is not None else 0.0
        if not waited and expl is not None:     # a custom cycle keeps its waits in the custom trace (review F-UX8)
            waited = float(getattr(getattr(expl, "custom", None), "waited_s", 0.0) or 0.0)
        return (" · " + _LF('等待 {0:.1f}s').format(waited)) if waited > 0.005 else ""

    def _resource_tags(self, member) -> list:
        """(text, colour, tooltip) tags of a member row at a resource level: ultimates cast, waits, unchecked
        energy, the fixed gauge rule."""
        result = getattr(self, "_rendering", None) or self._last_result
        expl = getattr(result, "explanation", None) if result is not None else None
        r = expl.resource(member.character_id) if expl is not None and hasattr(expl, "resource") else None
        if r is None:
            return []
        from src.services import team_simulation_explanation as tx

        out = []
        names = {member.character_id: member.name_zh}
        if r.q_planned:
            tip = None
            if r.q_skipped:
                tip = tx.note_text(tx.note(tx.LIMIT_ENERGY_SHORT, r.character_id, len(r.q_skipped)), names)
            out.append((_LF('极轨终结 {0}/{1}').format(r.q_cast, r.q_planned),
                        "#f85149" if r.q_skipped else "#8b949e", tip))
        if r.waited_s > 0.005:
            out.append((_LF('等待 {0:.1f}s').format(r.waited_s), "#e3b341", None))
        early = tuple(getattr(r, "early_swaps", ()) or ())
        if early:                           # D3: swapped out at once when a step was not ready
            out.append((_LF('提前切换 {0} 次').format(len(early)), "#f0883e",
                        tx.note_text(tx.note(tx.LIMIT_EARLY_SWAP, r.character_id, len(early),
                                             len(early) + sum(int(x[5]) for x in early)), names)))
        if not r.cost_enforced:             # unknown cost, Shinku's unconfirmed meter (review F-UX4)
            note = (tx.note(tx.LIMIT_ENERGY_UNKNOWN, r.character_id) if r.energy_kind == "ultimate"
                    else tx.note(tx.LIMIT_OWN_RESOURCE_UNIT, r.character_id, r.own_name_zh))
            out.append((_L('能量未检查'), "#8b949e", tx.note_text(note, names)))
        unchecked = [row[0] for row in r.cd if row[0] in ("E", "Q", "E_alt") and row[1] is None]
        if unchecked:                       # a cooldown without an enforced value: shown, never waited for
            kinds = "/".join(dict.fromkeys("E" if k == "E_alt" else k for k in unchecked))
            out.append((_L('冷却未检查'), "#8b949e", tx.note_text(tx.note(tx.LIMIT_CD_UNKNOWN, r.character_id, kinds),
                                                               names)))
        if r.gauge_fallback:
            out.append((_L('固定环合值规则'), "#e3b341", None))
        return out

    @staticmethod
    def _element_badge(element: str) -> QLabel | None:
        """Single-character element badge (光/灵/咒/暗/魂/相, translated by the display layer)."""
        from src.features.team_simulation.explanation_view import ELEMENT_COLORS
        from src.services.team_simulation_explanation import element_code, element_label

        char = element_label(element)
        if not char:
            return None
        color = ELEMENT_COLORS.get(element_code(element), "#8b949e")
        badge = QLabel(char)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{theme_rgba(color, 0.18)};color:{theme_color(color)};"
                            f"border:1px solid {theme_rgba(color, 0.55)};border-radius:4px;padding:1px 6px;"
                            "font-size:12px;font-weight:800")
        return badge

    def _modifier_text(self, property_id: str, value: float) -> str:
        from src.i18n_display import tr

        if self._attr_names is None:
            from src.services.team_simulation_service import attribute_names

            self._attr_names = attribute_names(self._static_path)
        known = self._attr_names.get(property_id)
        if known is None:       # target-side modifiers ("DamageResistCosmosAdd"): the attribute table has the stem
            for suffix in ("Add", "Base"):
                if property_id.endswith(suffix) and property_id[:-len(suffix)] in self._attr_names:
                    known = (self._attr_names[property_id[:-len(suffix)]][0], True)
                    break
        name_zh, percent = known or (property_id, abs(value) < 5)
        amount = f"{value * 100:+.1f}%" if percent else f"{value:+.0f}"
        return f"{tr(name_zh)} {amount}"

    def _fork_name(self, fork_id: str) -> str:
        for forks in self._fork_cache.values():
            for fork in forks:
                if fork["fork_id"] == fork_id:
                    return fork["name_zh"]
        return fork_id


def _unavailable_page(error: BaseException) -> QWidget:
    """Placeholder for the navigation stack when the preview page cannot be built."""
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.setContentsMargins(24, 18, 24, 24)
    lay.setSpacing(14)
    title = QLabel(_L('队伍模拟 (Beta)'))
    title.setStyleSheet(themed_style("font-size:22px;font-weight:800;color:#f0f6fc"))
    lay.addWidget(title)
    note = QLabel(_L('功能暂不可用'))
    note.setStyleSheet(themed_style("color:#e3b341;font-weight:700"))
    lay.addWidget(note)
    detail = QLabel(_LF('加载失败：{0}').format((f"{type(error).__name__}: {error}")))
    detail.setWordWrap(True)
    detail.setStyleSheet(themed_style("color:#8b949e"))
    lay.addWidget(detail)
    lay.addStretch()
    return page


def build_team_sim_page(window) -> QWidget:
    # Every page is built inside the main-window constructor.  This one is a preview feature that
    # reads the static database while it is built, so a failure here (a changed table after a data
    # update, an unreadable file, ...) must not keep the whole application from starting.
    try:
        page = TeamSimulationPage(window)
    except Exception as error:
        try:
            from src.utils.logger import logger

            logger.opt(exception=True).warning("team simulation page unavailable")
        except Exception:
            pass
        page = _unavailable_page(error)
    window.team_simulation_page = page
    return page
