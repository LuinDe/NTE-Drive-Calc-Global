# 队伍模拟：结果下方的「使用的循环」说明面板（出场顺序、每次切换的环合值与反应、各队员步骤、假设与限制）。
"""Explanation panel shown under the team-simulation result.

``render_explanation(layout, expl, open_state)`` appends one QFrame (objectName ``teamSimExplain``)
to ``layout``:

1. "🔁 使用的循环" header with chips: order mode and the order, gauge rule, the loops that start with
   every gauge at 100 (FULL_GAUGE_LOOPS; the opening gauge for older results), loops, battle time
   without time stops and wall time;
2. the planner's choice (order mode "plan"): one row per candidate order (adjacency, reactions,
   form-window buff cover, loop-2 support-skill entry, simulated team DPS) and the reasons;
3. the visit flow, one row per loop with a "gauge refilled / carried over" pill (entry type,
   reaction on entry, gauge in -> out, the form window used: name, duration, seconds, rounds);
4. one grid row per swap (also swaps that did not react: same element / not adjacent / gauge
   short) plus combination reactions (盈蓄 / 失谐) and a full-width row where a loop refills every
   gauge, with a count / total footer, or a message when no pair of members is adjacent;
5. collapsible per-member steps (form steps cut by the window, extra rounds, overruns); the expanded
   state lives in ``open_state`` (a dict owned by the page) so it survives the page's re-render on a
   language switch;
6. assumptions and limits, mapped from codes.

A custom cycle (``expl.custom``, order mode "custom") shows its own header chips (gauge mode, starting gauge,
repeat count, cooldown check) and, between the visit flow and the swap grid, the step table of the typed
sequence (``custom_view.render_custom_steps``); member sections read "direct input · N steps".  The texts of
the custom mode are built in ``custom_view``.

Visible words go through _L / _LF.  Game names - characters, elements as single characters
光/灵/咒/暗/魂/相, reactions, skill slot terms - are passed as their Chinese originals so the display
layer (tr) translates them.  QFrame styles are scoped by objectName because QLabel is a QFrame too.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF
from src.i18n_runtime import CStr, has_provenance

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.app.theme import current_theme_name, theme_color, theme_rgba, themed_style
from src.services import team_simulation_explanation as tx

ELEMENT_COLORS = {
    "cosmos": "#e3b341", "nature": "#56d364", "incantation": "#bc8cff",
    "chaos": "#f85149", "psyche": "#58a6ff", "lakshana": "#39c5cf",
}
REACTION_COLORS = {
    "创生": "#8fd14f", "覆纹": "#a371f7", "浊燃": "#f0883e", "黯星": "#79c0ff",
    "浸染": "#39c5cf", "延滞": "#e3b341", "盈蓄": "#ffa726", "失谐": "#ff7b72",
}
# skill slot -> official game term (translated by the display layer)
SLOT_TERMS = {"qte": "援护技", "skill": "变轨技能", "ultimate": "极轨终结", "basic": "普通攻击"}

_MUTED = "color:#8b949e;font-size:11px"
_TEXT = "color:#c9d1d9;font-size:12px"


# ── code -> text (built at render time so the active language applies) ─────
def _entry_text(code: str) -> str:
    return {
        tx.ENTRY_OPENER: _L('先手登场'),
        tx.ENTRY_SUPPORT_SKILL: _L('援护技登场'),
        tx.ENTRY_NORMAL: _L('普通切换'),
    }.get(code, code)


def _outcome_text(swap) -> str:
    if swap.outcome == tx.OUTCOME_SAME_ELEMENT:
        return _L('无反应：同属性')
    if swap.outcome == tx.OUTCOME_NOT_ADJACENT:
        return _L('无反应：属性不相邻')
    if swap.outcome == tx.OUTCOME_GAUGE_SHORT:
        return _LF('无反应：环合值不足（{0:.0f}/100）').format(float(swap.gauge or 0.0))
    if swap.outcome == tx.OUTCOME_PLAIN_SWAP:      # custom cycle: the user typed a plain swap
        from src.features.team_simulation.custom_view import plain_swap_text

        return plain_swap_text()
    return swap.outcome


def _owner_basis_text(code: str) -> str:
    if code in tx.OWNER_PER_HIT_CODES:
        return _L('各命中所属队员')
    return {
        tx.OWNER_ZANKOU: _L('残虹在队，浊燃归残虹'),
        tx.OWNER_FINAL_EFFECT: _L('归最终效果更高的队员'),
        tx.OWNER_TIE_INCOMING: _L('效果相同，归切入队员'),
        tx.OWNER_INCOMING: _L('归切入队员'),
        tx.OWNER_INCOMING_PROVISIONAL: _L('归切入队员'),
    }.get(code, "")


def _order_mode_text(code: str) -> str:
    return {tx.ORDER_AUTO: _L('自动（环合最多）'), tx.ORDER_SLOT: _L('按编队顺序'),
            tx.ORDER_PLAN: _L('自动（变身输出优先）')}.get(code, code)


def _gauge_rule_text(code: str) -> str:
    return {tx.GAUGE_GAME: _L('按环合值（实测拟合）'), tx.GAUGE_IDEAL: _L('理想：每次相邻切换都触发')}.get(code, code)


def _verdict_text(code: str) -> str:
    return {"confirmed": _L('已确认'), "corrected": _L('已修正'), "disputed": _L('有异议')}.get(code, code)


def _confidence_text(code: str) -> str:
    return {"high": _L('可信度高'), "medium": _L('可信度中'), "low": _L('可信度低')}.get(code, code)


def _role_text(code: str) -> str:
    return {"support": _L('辅助'), "sub": _L('副输出'), "main": _L('主输出')}.get(code, code)


def _slot_text(code: str) -> str:
    if code == tx.SLOT_ENTRY:
        return _L('登场动作')
    return SLOT_TERMS.get(code) or _L('其他动作')


def _step_status_text(code: str) -> str:
    return {
        tx.STEP_TIME_ONLY: _L('仅计时（未模拟伤害）'),
        tx.STEP_TIME_DEFAULT: _L('仅计时（时长按 1 秒估算）'),
        tx.STEP_MISSING: _L('缺少动画数据，未计伤害'),
        tx.STEP_SKIPPED: _L('普通切换，跳过援护技'),
        tx.STEP_FORM_CUT: _L('形态时间不足，未执行'),
    }.get(code, "")


def _form_overrun_text(form) -> str:
    """"超出形态时间 +4.2s" when approved form steps were kept past the window (warn policy), else ""."""
    over = float(getattr(form, "overrun_s", 0.0) or 0.0)
    return _L('超出形态时间') + f" +{over:.1f}s" if over > 0 else ""


def _form_text(form, overrun: bool = True) -> str:
    """"形态 8 秒：使用 5.4 秒（1 组）" for a FormTrace; "（2/4 组）" when approved rounds were cut, plus the
    seconds kept past the window (warn policy) unless ``overrun`` is False (the visit chip shows them apart)."""
    duration, used = f"{float(form.duration_s):g}", f"{float(form.used_s):.1f}"
    groups, approved = int(form.groups), int(getattr(form, "groups_approved", 0) or 0)
    if 0 < approved and groups < approved:
        text = _LF('形态 {0} 秒：使用 {1} 秒（{2}/{3} 组）').format(duration, used, groups, approved)
    else:
        text = _LF('形态 {0} 秒：使用 {1} 秒（{2} 组）').format(duration, used, groups)
    over = _form_overrun_text(form) if overrun else ""
    if over:
        text = text + " · " + over
    return text


def _form_tip(form) -> str:
    """Tooltip: the form's rules from game data and what the visit did with the window."""
    lines = [tx.form_name_text(form.code, form.name_zh) + " · " + _form_text(form)]
    if form.fills:
        lines.append(_L('形态时间有余，追加执行') + f" ×{int(form.fills)}")
    if form.cut_steps:
        lines.append(_L('形态时间不足，未执行') + f" ×{int(form.cut_steps)}")
    if form.overrun_s:
        lines.append(_form_overrun_text(form))
    if form.window and form.exit_s is not None:
        lines.append(f"{float(form.exit_s):.1f}s ({float(form.window[0]):g}–{float(form.window[1]):g}s)")
    text = lines[0]
    for line in lines[1:]:
        text = text + "\n" + line
    return text


def _form_tone(form) -> str:
    return {tx.FORM_OK: "#bc8cff", tx.FORM_CUT: "#e3b341", tx.FORM_OVERRUN: "#e3b341",
            tx.FORM_WINDOW_MISSED: "#f85149"}.get(form.status, "#bc8cff")


# ── small helpers ───────────────────────────────────────────────────────────
def _accent(color: str) -> str:
    """theme_color, plus a darker shade on the white theme for pastel accents it does not map."""
    mapped = theme_color(color)
    if mapped == color and current_theme_name() == "light":
        return QColor(color).darker(150).name()
    return mapped


def _page():
    # lazy: page.py imports this module
    from src.features.team_simulation import page

    return page


def _piece(text):
    """A plain game name as its own concatenation piece, so the display layer translates it alone.

    Merged with a neighbouring separator into one plain string, the English path of tr() would
    strip the separator's spaces ("Mint ·Main DPS")."""
    if not isinstance(text, str) or not text or has_provenance(text):
        return text
    return CStr(text, (text,))


def _join(parts, sep: str = " · ") -> str:
    """Join with `+` so translation provenance survives (str.join drops it)."""
    out = None
    for part in parts:
        if part is None or part == "":
            continue
        part = _piece(part)
        out = part if out is None else out + sep + part
    return "" if out is None else out


def _span(start_s: float, end_s: float) -> str:
    return f"{start_s:.1f}–{end_s:.1f}s"


def _circled(n: int) -> str:
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else f"{n}."


def _label(text, style: str = _TEXT, *, wrap: bool = False, tip=None, align=None) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(themed_style(style))
    if wrap:
        label.setWordWrap(True)
    if tip:
        label.setToolTip(tip)
    if align is not None:
        label.setAlignment(align)
    return label


def _pill(text: str, color: str, *, bold: bool = True, size: int = 11) -> QLabel:
    pill = QLabel(text)
    pill.setStyleSheet(f"background:{theme_rgba(color, 0.18)};color:{_accent(color)};"
                       f"border:1px solid {theme_rgba(color, 0.55)};border-radius:4px;padding:0px 5px;"
                       f"font-size:{size}px;font-weight:{800 if bold else 600}")
    pill.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return pill


def _element_badge(element) -> QLabel | None:
    code = tx.element_code(element)
    char = tx.ELEMENT_LABELS.get(code)
    if not char:
        return None
    return _pill(char, ELEMENT_COLORS.get(code, "#8b949e"))


def _reaction_badge(reaction_zh: str) -> QLabel:
    return _pill(reaction_zh, REACTION_COLORS.get(reaction_zh, "#58a6ff"), size=12)


def _caption(text) -> QLabel:
    return _label(text, "color:#c9d1d9;font-size:13px;font-weight:800;margin-top:4px")


class _FlowLayout(QLayout):
    """Left-to-right layout that wraps to a new line (chips and visit cards)."""

    def __init__(self, parent=None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802 - Qt override
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._arrange(rect, False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _arrange(self, rect, test_only: bool) -> int:
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x > area.x() and x + hint.width() > area.right() + 1:
                x, y, line = area.x(), y + line + self._gap, 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line = max(line, hint.height())
        return y + line - rect.y() + m.bottom()


def _flow(spacing: int = 6) -> tuple[QWidget, _FlowLayout]:
    host = QWidget()
    flow = _FlowLayout(host, spacing)
    return host, flow


class _Ctx:
    """Per-render lookups: names, slot colours, amount formatting."""

    def __init__(self, expl) -> None:
        page = _page()
        self.expl = expl
        self.fmt = page._fmt_amount
        ids = [m.character_id for m in expl.members] or list(expl.order)
        colors = page.SLOT_COLORS
        self.slot_color = {cid: colors[i % len(colors)] for i, cid in enumerate(ids)}
        self.names = {cid: expl.name_of(cid) for cid in ids}
        self.first_visit = min((v.index for v in expl.visits), default=None)

    def name(self, cid) -> str:
        if cid is None:
            return ""
        return self.names.get(cid) or self.expl.name_of(cid)

    def entry(self, visit) -> str:
        """Entry code to show: the battle's first visit is the opener even when traced as "normal"."""
        if visit.index == self.first_visit and visit.entry == tx.ENTRY_NORMAL:
            return tx.ENTRY_OPENER
        return visit.entry

    def color(self, cid) -> str:
        return self.slot_color.get(cid, "#c9d1d9")

    def name_label(self, cid, size: int = 12) -> QLabel:
        return _label(self.name(cid), f"color:{_accent(self.color(cid))};font-size:{size}px;font-weight:700")


# ── sections ────────────────────────────────────────────────────────────────
def _info_chip(caption, value, tip=None) -> QFrame:
    chip = QFrame()
    chip.setObjectName("teamSimExplainChip")
    # rgba(): an 8-digit hex is read by Qt as #AARRGGBB
    chip.setStyleSheet(f"QFrame#teamSimExplainChip{{background:{theme_rgba('#1f6feb', 0.2)};border-radius:4px}}")
    row = QHBoxLayout(chip)
    row.setContentsMargins(10, 4, 10, 4)
    row.setSpacing(6)
    row.addWidget(_label(caption, "color:#8b949e;font-size:12px"))
    row.addWidget(_label(value, "color:#c9d1d9;font-size:12px;font-weight:700"))
    if tip:
        chip.setToolTip(tip)
    return chip


def _approved_header_chips(flow, expl, ctx: _Ctx) -> None:
    order = _join((ctx.name(cid) for cid in expl.order), " → ")
    flow.addWidget(_info_chip(_order_mode_text(expl.order_mode), order or "—"))
    flow.addWidget(_info_chip(_L('环合值规则'), _gauge_rule_text(expl.gauge_rule)))
    refills = tuple(getattr(expl, "full_gauge_loops", ()) or ())
    if refills:          # loops that start with every gauge at 100 (FULL_GAUGE_LOOPS)
        flow.addWidget(_info_chip(_L('环合值 100 的轮次'), tx.loops_text(refills),
                                  tip=tx.note_text(tx.note(tx.ASSUME_FULL_GAUGE_LOOPS, *refills))))
    else:                # results from before the loop rule: the opening gauge
        opening = "100" if expl.opening_gauge == tx.OPENING_FULL else "0"
        flow.addWidget(_info_chip(_L('开场环合值'), opening,
                                  tip=tx.note_text(tx.ASSUME_OPENING_FULL if expl.opening_gauge == tx.OPENING_FULL
                                                   else tx.ASSUME_OPENING_ZERO)))
    flow.addWidget(_info_chip(_L('轮数'), str(expl.loops)))


def _header(lay: QVBoxLayout, expl, ctx: _Ctx) -> None:
    lay.addWidget(_label(_L('🔁 使用的循环'), "font-size:15px;font-weight:800;color:#f0f6fc"))
    host, flow = _flow(6)
    if getattr(expl, "custom", None) is not None:      # custom cycle: its own chips before the two time chips
        from src.features.team_simulation.custom_view import render_custom_header

        render_custom_header(flow, expl, ctx)
    else:
        _approved_header_chips(flow, expl, ctx)
    flow.addWidget(_info_chip(_L('扣除时停'), f"{expl.active_time_s:.1f}s",
                              tip=tx.note_text(tx.ASSUME_TIME_STOPS)))
    stops = len(expl.time_stops)
    tip = _LF('{0} 次时停，共 {1:.1f}s').format(stops, expl.time_stop_s) if stops else None
    flow.addWidget(_info_chip(_L('包含时停'), f"{expl.wall_time_s:.1f}s", tip=tip))
    lay.addWidget(host)


def _swap_into_visit(expl) -> dict:
    """visit.index -> the SwapTrace that brought that member in (the first visit has none)."""
    visits = sorted(expl.visits, key=lambda v: v.index)
    swaps = sorted(expl.swaps, key=lambda s: (s.time_s, s.index))
    later = visits[1:]
    if len(swaps) == len(later) and all(s.in_character_id == v.character_id for s, v in zip(swaps, later)):
        return {v.index: s for s, v in zip(swaps, later)}
    out: dict = {}
    for visit in later:       # irregular traces: nearest swap into this member around the visit start
        near = [s for s in swaps if s.in_character_id == visit.character_id and abs(s.time_s - visit.start_s) <= 2.0]
        if near:
            out[visit.index] = min(near, key=lambda s: abs(s.time_s - visit.start_s))
    return out


def _visit_dot(visit) -> tuple[float, int]:
    """(damage, ticks) of the member's damage-over-time ticks credited to this visit (0 for old traces)."""
    return float(getattr(visit, "dot_damage", 0.0) or 0.0), int(getattr(visit, "dot_hits", 0) or 0)


def _visit_total(visit) -> float:
    """Step damage plus damage-over-time ticks: a member's visits add up to its direct damage."""
    return float(visit.damage or 0.0) + _visit_dot(visit)[0]


def _visit_chip(visit, swap, reaction, ctx: _Ctx) -> QFrame:
    color = ctx.color(visit.character_id)
    chip = QFrame()
    chip.setObjectName("teamSimVisitChip")
    chip.setStyleSheet(themed_style("QFrame#teamSimVisitChip{background:#161b22;border:1px solid #30363d;"
                                    "border-radius:6px}")
                       + f"QFrame#teamSimVisitChip{{border-left:3px solid {_accent(color)}}}")
    chip.setMinimumWidth(150)
    col = QVBoxLayout(chip)
    col.setContentsMargins(9, 5, 10, 6)
    col.setSpacing(2)
    top = QHBoxLayout()
    top.setSpacing(5)
    top.addWidget(_label(_circled(visit.index + 1), f"color:{_accent(color)};font-size:13px;font-weight:800"))
    top.addWidget(ctx.name_label(visit.character_id, 13))
    badge = _element_badge(visit.element)
    if badge is not None:
        top.addWidget(badge)
    top.addStretch()
    col.addLayout(top)
    col.addWidget(_label(f"{_span(visit.start_s, visit.end_s)} · {ctx.fmt(_visit_total(visit))}", _MUTED))
    dot, dot_hits = _visit_dot(visit)
    if dot_hits:
        col.addWidget(_label(_LF('含持续伤害 {0}（{1} 跳）').format(ctx.fmt(dot), dot_hits), _MUTED))
    code = ctx.entry(visit)
    entry = _entry_text(code)
    if code == tx.ENTRY_SUPPORT_SKILL and reaction is not None:
        tone = REACTION_COLORS.get(reaction.reaction_zh, "#58a6ff")
        entry = _join((entry, reaction.reaction_zh))
    elif code == tx.ENTRY_SUPPORT_SKILL:
        tone = "#58a6ff"
    elif code == tx.ENTRY_OPENER:
        tone = "#e3b341"
    else:
        tone = "#8b949e"
    col.addWidget(_label(entry, f"color:{_accent(tone)};font-size:12px;font-weight:700"))
    gauge = _L('环合值') + f" {visit.gauge_in:.0f} → {visit.gauge_out:.0f}"
    col.addWidget(_label(gauge, _MUTED))
    form = getattr(visit, "form", None)
    if form is not None:
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(_pill(tx.form_name_text(form.code, form.name_zh), _form_tone(form)))
        row.addWidget(_label(_form_text(form, overrun=False), _MUTED, tip=_form_tip(form)))
        row.addStretch()
        col.addLayout(row)
        over = _form_overrun_text(form)
        if over:                        # own line: keeps the chip narrow
            col.addWidget(_label(over, f"color:{_accent('#e3b341')};font-size:11px", tip=_form_tip(form)))
    if swap is not None and swap.outcome != tx.OUTCOME_REACTION:
        chip.setToolTip(_outcome_text(swap))
    return chip


def _custom_cap(expl, member: bool = False) -> int | None:
    """Rows a section lists for a custom cycle (custom_view.MAX_SECTION_ROWS, MAX_MEMBER_ROWS for one member's
    steps); None = no cap (reviewed mode)."""
    if getattr(expl, "custom", None) is None:
        return None
    from src.features.team_simulation import custom_view

    return custom_view.MAX_MEMBER_ROWS if member else custom_view.MAX_SECTION_ROWS


def _hidden_rows(lay: QVBoxLayout, count: int) -> None:
    if count > 0:
        from src.features.team_simulation.custom_view import hidden_rows_label

        lay.addWidget(hidden_rows_label(count))


def _visit_flow(lay: QVBoxLayout, expl, ctx: _Ctx) -> None:
    if not expl.visits:
        return
    lay.addWidget(_caption(_L('出场顺序')))
    into = _swap_into_visit(expl)
    reactions = expl.reaction_by_index()
    loops: dict = {}
    visits = sorted(expl.visits, key=lambda v: v.index)
    cap = _custom_cap(expl)
    hidden = 0 if cap is None else max(0, len(visits) - cap)
    for visit in visits if cap is None else visits[:cap]:
        loops.setdefault(visit.loop_index, []).append(visit)
    for loop_index in sorted(loops):
        row = QHBoxLayout()
        row.setSpacing(8)
        tag = _label(_LF('第 {0} 轮').format(loop_index + 1), "color:#8b949e;font-size:12px;font-weight:700",
                     align=Qt.AlignLeft | Qt.AlignTop)
        tag.setMinimumWidth(56)
        refills = tuple(getattr(expl, "full_gauge_loops", ()) or ())
        if refills:          # per-loop gauge rule pill under the loop tag
            head = QVBoxLayout()
            head.setSpacing(3)
            head.addWidget(tag)
            if (loop_index + 1) in {int(n) for n in refills}:
                pill = _pill(_L('环合值补满'), "#3fb950")
                pill.setToolTip(tx.note_text(tx.note(tx.ASSUME_FULL_GAUGE_LOOPS, *refills)))
            else:
                pill = _pill(_L('环合值累积'), "#8b949e")
                pill.setToolTip(_L('沿用上一轮结束时累积的环合值'))
            head.addWidget(pill)
            head.addStretch()
            row.addLayout(head)
        else:
            row.addWidget(tag, 0, Qt.AlignTop)
        host, flow = _flow(6)
        for i, visit in enumerate(loops[loop_index]):
            swap = into.get(visit.index)
            reaction = reactions.get(swap.reaction_index) if swap is not None else None
            chip = _visit_chip(visit, swap, reaction, ctx)
            if i:
                pair = QWidget()
                pair_row = QHBoxLayout(pair)
                pair_row.setContentsMargins(0, 0, 0, 0)
                pair_row.setSpacing(6)
                pair_row.addWidget(_label("→", "color:#8b949e;font-size:14px;padding-top:22px"), 0, Qt.AlignTop)
                pair_row.addWidget(chip)
                flow.addWidget(pair)
            else:
                flow.addWidget(chip)
        row.addWidget(host, 1)
        lay.addLayout(row)
    _hidden_rows(lay, hidden)


def _swap_cell(swap, ctx: _Ctx) -> QWidget:
    cell = QWidget()
    row = QHBoxLayout(cell)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    for i, (cid, element) in enumerate(((swap.out_character_id, swap.out_element),
                                         (swap.in_character_id, swap.in_element))):
        if i:
            row.addWidget(_label("→", "color:#8b949e;font-size:12px"))
        row.addWidget(ctx.name_label(cid))
        badge = _element_badge(element)
        if badge is not None:
            row.addWidget(badge)
    row.addStretch()
    return cell


def _reaction_cells(reaction, ctx: _Ctx) -> tuple:
    """(owner widget, damage widget, effects widget) for one reaction."""
    if reaction.owner_basis in tx.OWNER_PER_HIT_CODES:
        owner = _label(_owner_basis_text(reaction.owner_basis), _MUTED, wrap=True)
    elif reaction.owner_character_id is None or reaction.owner_basis in tx.OWNER_NOBODY_CODES:
        owner = _label("—", _MUTED)
    else:
        owner = ctx.name_label(reaction.owner_character_id)
        basis = _owner_basis_text(reaction.owner_basis)
        if basis:
            owner.setToolTip(basis)
    if reaction.status == tx.REACTION_EFFECT_ONLY:
        damage = _label(_L('仅效果，无伤害'), _MUTED)
    else:
        tone = "#e3b341" if reaction.status == tx.REACTION_PARTIAL else "#f0f6fc"
        damage = _label(ctx.fmt(reaction.damage or 0.0), f"color:{_accent(tone)};font-size:12px;font-weight:800")
    items = tx.merge_effects(reaction.effects)
    if reaction.status == tx.REACTION_EFFECT_ONLY:     # the damage column already says so
        items = [e for e in items if e[0] != tx.EFFECT_EFFECT_ONLY]
    effects = _join(tx.effect_text(e) for e in items)   # hidden codes render "" and are skipped
    return owner, damage, _label(effects or "", _MUTED, wrap=True)


_REFILL_ROW = 0.5      # swap-grid event kind: sorts after the swap (0) at the same time, before combo rows (1)


def _swap_grid(lay: QVBoxLayout, expl, ctx: _Ctx) -> None:
    lay.addWidget(_caption(_L('环合反应')))
    if not expl.has_adjacent_pair():
        lay.addWidget(_label(_L('本队伍没有相邻属性组合，不会触发环合反应。'),
                             "color:#e3b341;font-size:12px", wrap=True))
        return
    reactions = expl.reaction_by_index()
    linked = {s.reaction_index for s in expl.swaps if s.reaction_index is not None}
    events = [(s.time_s, 0, i, s) for i, s in enumerate(expl.swaps)]
    events += [(r.time_s, 1, i, r) for i, r in enumerate(expl.reactions) if r.index not in linked]
    refills = {int(n) for n in (getattr(expl, "full_gauge_loops", ()) or ())}
    for loop in sorted(refills):       # loops after the first that refill every gauge: one row right after the
        # boundary swap into them (that swap is judged on the gauge built up in the previous loop)
        first = min((v for v in expl.visits if v.loop_index + 1 == loop), key=lambda v: v.index, default=None)
        if loop > 1 and first is not None:
            events.append((first.start_s, _REFILL_ROW, loop, loop))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    cap = _custom_cap(expl)
    hidden = 0 if cap is None else max(0, len(events) - cap)
    if hidden:
        events = events[:cap]

    box = QFrame()
    box.setObjectName("teamSimSwapGrid")
    box.setStyleSheet(themed_style("QFrame#teamSimSwapGrid{background:#161b22;border:1px solid #21262d;border-radius:6px}"))
    grid = QGridLayout(box)
    grid.setContentsMargins(10, 8, 10, 8)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(6)
    heads = (_L('时间'), _L('切出') + " → " + _L('切入'), _L('环合值'), _L('环合反应'),
             _L('归属'), _L('伤害'), _L('效果'))
    for c, text in enumerate(heads):
        grid.addWidget(_label(text, "color:#8b949e;font-size:11px;font-weight:700"), 0, c)
    line = QFrame()
    line.setObjectName("teamSimSwapRule")
    line.setFixedHeight(1)
    line.setStyleSheet(themed_style("QFrame#teamSimSwapRule{background:#30363d;border:none}"))
    grid.addWidget(line, 1, 0, 1, len(heads))

    r = 2
    for time_s, kind, _i, obj in events:
        grid.addWidget(_label(f"{time_s:.1f}s", "color:#c9d1d9;font-size:12px"), r, 0, Qt.AlignTop)
        if kind == _REFILL_ROW:
            refill = _label(_LF('第 {0} 轮开始：所有队员环合值补满 100').format(int(obj)),
                            f"color:{_accent('#3fb950')};font-size:12px;font-weight:700")
            refill.setToolTip(tx.note_text(tx.note(tx.ASSUME_FULL_GAUGE_LOOPS, *sorted(refills))))
            grid.addWidget(refill, r, 1, 1, len(heads) - 1, Qt.AlignTop)
            r += 1
            continue
        if kind == 0:
            swap = obj
            grid.addWidget(_swap_cell(swap, ctx), r, 1, Qt.AlignTop)
            if swap.gauge is None:
                gauge = _label("—", _MUTED)
            else:
                # green: spent on a reaction, amber: too low to react, grey: the gauge did not matter
                tone = {tx.OUTCOME_REACTION: "#3fb950", tx.OUTCOME_GAUGE_SHORT: "#e3b341"}.get(swap.outcome, "#8b949e")
                gauge = _label(f"{float(swap.gauge):.0f}", f"color:{_accent(tone)};font-size:12px;font-weight:700")
            grid.addWidget(gauge, r, 2, Qt.AlignTop)
            reaction = reactions.get(swap.reaction_index) if swap.outcome == tx.OUTCOME_REACTION else None
            if reaction is None:
                reason = _outcome_text(swap) if swap.outcome != tx.OUTCOME_REACTION else "—"
                grid.addWidget(_label(reason, _MUTED), r, 3, 1, len(heads) - 3, Qt.AlignTop)
                r += 1
                continue
        else:
            reaction = obj
            grid.addWidget(_label("—", _MUTED), r, 1, Qt.AlignTop)
            grid.addWidget(_label("", _MUTED), r, 2, Qt.AlignTop)
        grid.addWidget(_reaction_badge(reaction.reaction_zh), r, 3, Qt.AlignTop | Qt.AlignLeft)
        owner, damage, effects = _reaction_cells(reaction, ctx)
        grid.addWidget(owner, r, 4, Qt.AlignTop)
        grid.addWidget(damage, r, 5, Qt.AlignTop)
        grid.addWidget(effects, r, 6, Qt.AlignTop)
        r += 1
    grid.setColumnStretch(6, 1)
    lay.addWidget(box)
    _hidden_rows(lay, hidden)
    n_swap = sum(1 for s in expl.swaps if s.outcome == tx.OUTCOME_REACTION)
    n_combo = len(expl.reactions) - n_swap
    if n_combo > 0:
        total = _LF('{0} 次切换反应 + {1} 次组合反应，共 {2}').format(n_swap, n_combo, ctx.fmt(expl.reaction_damage))
    else:
        total = _LF('{0} 次，共 {1}').format(len(expl.reactions), ctx.fmt(expl.reaction_damage))
    lay.addWidget(_label(total, "color:#c9d1d9;font-size:12px;font-weight:700", align=Qt.AlignRight))


def _plan_section(lay: QVBoxLayout, expl, ctx: _Ctx) -> None:
    """Order mode "plan": every candidate order with its ranking inputs and simulated DPS, then the reasons."""
    plan = getattr(expl, "plan", None)
    if plan is None or not plan.candidates:
        return
    lay.addWidget(_caption(_L('出场顺序的选择')))
    box = QFrame()
    box.setObjectName("teamSimPlanGrid")
    box.setStyleSheet(themed_style("QFrame#teamSimPlanGrid{background:#161b22;border:1px solid #21262d;border-radius:6px}"))
    grid = QGridLayout(box)
    grid.setContentsMargins(10, 8, 10, 8)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(5)
    heads = (_L('候选顺序'), _L('相邻组合'), _L('反应次数'), _L('形态增益覆盖'), _L('第 2 轮援护技登场'),
             _L('队伍 DPS'), "")
    for c, text in enumerate(heads):
        grid.addWidget(_label(text, "color:#8b949e;font-size:11px;font-weight:700"), 0, c)
    for r, cand in enumerate(plan.candidates, 1):
        tone = "color:#f0f6fc;font-size:12px;font-weight:800" if cand.chosen else _TEXT
        grid.addWidget(_label(_join((ctx.name(cid) for cid in cand.order), " → "), tone), r, 0)
        grid.addWidget(_label(str(int(cand.adjacency)), _MUTED), r, 1)
        grid.addWidget(_label(str(int(cand.reactions)), _MUTED), r, 2)
        form_s = float(getattr(cand, "form_s", 0.0) or 0.0)
        cover = f"{float(cand.coverage_s):.1f}/{form_s:.1f}s" if form_s > 0 else f"{float(cand.coverage_s):.1f}s"
        grid.addWidget(_label(cover, _MUTED), r, 3)
        grid.addWidget(_label("✓" if cand.loop2_support_entry else "—", _MUTED), r, 4)
        grid.addWidget(_label(ctx.fmt(cand.dps) if cand.dps is not None else "—", tone), r, 5)
        if cand.chosen:
            grid.addWidget(_pill(_L('已选'), "#3fb950"), r, 6, Qt.AlignLeft)
    grid.setColumnStretch(6, 1)
    lay.addWidget(box)
    for item in plan.reasons:
        lay.addWidget(_label("• " + tx.note_text(item, ctx.names), "color:#8b949e;font-size:12px", wrap=True))


def _toggle_text(member, ctx: _Ctx, opened: bool) -> str:
    if member.variant_id == tx.VARIANT_CUSTOM:     # custom cycle: no verdict / confidence of a reviewed rotation
        from src.features.team_simulation.custom_view import member_toggle_text

        return member_toggle_text(member, ctx, opened)
    return _join((
        ("▼ " if opened else "▶ ") + _piece(ctx.name(member.character_id)),
        _role_text(member.role),
        _verdict_text(member.verdict),
        _confidence_text(member.confidence),
        _LF('计算了 {0}/{1} 个步骤').format(member.steps_simulated, member.steps_total),
    ))


def _label_ko_tips(character_id) -> dict:
    """seq -> Korean step description; a Korean-only tooltip (never shown in zh / en / ja)."""
    try:
        from src import i18n_runtime

        if i18n_runtime.get_language() != "ko":
            return {}
    except Exception:
        return {}
    data = tx.rotation_character(character_id)
    try:
        steps = data["variants"]["approved"]["steps"]
    except (KeyError, TypeError):
        return {}
    return {s.get("seq"): s.get("label_ko") for s in steps if s.get("label_ko")}


def _step_label(step) -> str:
    """Slot term plus the game's ability name; a step without a catalog name shows the slot term only
    (its internal id goes to the tooltip, see _step_ident)."""
    slot = _slot_text(step.slot)
    if step.ability_name_zh:
        return _LF('{0}「{1}」').format(slot, step.ability_name_zh)
    return slot


def _step_ident(step) -> str:
    """Internal "ability_id · selector" of a step without a catalog name ("" otherwise)."""
    if step.ability_name_zh or not step.ability_id:
        return ""
    return step.ability_id + (f" · {step.selector}" if step.selector else "")


# step form roles that run inside the form window ("after" runs once it has ended)
_IN_FORM_ROLES = frozenset((tx.FORM_ROLE_BODY, tx.FORM_ROLE_WINDOW, tx.FORM_ROLE_FREE, tx.FORM_ROLE_EXIT,
                            tx.FORM_ROLE_TERMINAL, tx.FORM_ROLE_TAIL, tx.FORM_ROLE_FILL))


def _member_body(member, visits, ctx: _Ctx, cap: int | None = None) -> QFrame:
    body = QFrame()
    body.setObjectName("teamSimMemberSteps")
    body.setStyleSheet(themed_style("QFrame#teamSimMemberSteps{background:#0d1117;border:1px solid #21262d;"
                                    "border-radius:6px}"))
    col = QVBoxLayout(body)
    col.setContentsMargins(10, 8, 10, 8)
    col.setSpacing(6)
    grid = QGridLayout()
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(3)
    heads = ("#", _L('动作'), _L('时间'), _L('时长'), _L('命中'), _L('伤害'), "")
    for c, text in enumerate(heads):
        grid.addWidget(_label(text, "color:#8b949e;font-size:11px;font-weight:700"), 0, c)
    # the Korean step descriptions belong to the reviewed rotation's seq numbers: not for a custom cycle
    tips = {} if member.variant_id == tx.VARIANT_CUSTOM else _label_ko_tips(member.character_id)
    r = 1
    listed = 0                          # step rows drawn (``cap``: a long custom cycle lists the first ones only)
    for visit in visits:
        if cap is not None and listed >= cap:
            break
        head = _join((
            _LF('第 {0} 轮').format(visit.loop_index + 1),
            _entry_text(ctx.entry(visit)),
            _span(visit.start_s, visit.end_s),
            _L('环合值') + f" {visit.gauge_in:.0f} → {visit.gauge_out:.0f}",
            _L('伤害') + " " + ctx.fmt(_visit_total(visit)),
        ))
        grid.addWidget(_label(head, f"color:{_accent(ctx.color(member.character_id))};font-size:12px;"
                                    "font-weight:700;margin-top:4px"), r, 0, 1, len(heads))
        r += 1
        form = getattr(visit, "form", None)
        form_at = None                  # the form line goes right before the first step run inside the form
        if form is not None:
            form_at = next((i for i, s in enumerate(visit.steps) if getattr(s, "form_role", "") in _IN_FORM_ROLES), 0)
        for i, step in enumerate(visit.steps):
            if cap is not None and listed >= cap:
                break
            listed += 1
            if i == form_at:            # the form window this visit used (game-data duration)
                line = _join((tx.form_name_text(form.code, form.name_zh), _form_text(form)))
                grid.addWidget(_label(line, f"color:{_accent(_form_tone(form))};font-size:11px;font-weight:700",
                                      tip=_form_tip(form)), r, 0, 1, len(heads))
                r += 1
            ok = step.status == tx.STEP_OK
            text_style = _TEXT if ok else "color:#8b949e;font-size:12px"
            tip = "\n".join(t for t in (tips.get(step.seq), _step_ident(step)) if t) or None
            name = _label(_step_label(step), text_style, tip=tip)
            grid.addWidget(_label(str(step.seq) if step.seq else "·", _MUTED), r, 0)
            grid.addWidget(name, r, 1)
            grid.addWidget(_label(f"{step.start_s:.1f}s", _MUTED), r, 2)
            grid.addWidget(_label(f"{step.duration_s:.2f}s", _MUTED), r, 3)
            grid.addWidget(_label(str(step.hits) if step.hits else "—", _MUTED), r, 4)
            grid.addWidget(_label(ctx.fmt(step.damage) if step.damage else "—",
                                  "color:#c9d1d9;font-size:12px;font-weight:700" if step.damage else _MUTED), r, 5)
            note = _step_status_text(step.status)
            tone = "#e3b341" if step.status in (tx.STEP_MISSING, tx.STEP_FORM_CUT) else "#8b949e"
            if not note and getattr(step, "form_role", "") == tx.FORM_ROLE_FILL:
                note = _L('形态时间有余，追加执行')
            elif not note and form is not None and getattr(step, "form_role", "") in _IN_FORM_ROLES:
                note, tone = tx.form_name_text(form.code, form.name_zh), "#bc8cff"   # step run inside the form
            if note:
                grid.addWidget(_label(note, f"color:{_accent(tone)};font-size:11px"), r, 6)
            r += 1
        dot, dot_hits = _visit_dot(visit)
        if dot_hits:                    # the member's own DoT ticks after this entry (not part of any step)
            grid.addWidget(_label("·", _MUTED), r, 0)
            grid.addWidget(_label(_L('持续伤害跳（每 1 秒）'), _TEXT), r, 1)
            grid.addWidget(_label("—", _MUTED), r, 2)
            grid.addWidget(_label("—", _MUTED), r, 3)
            grid.addWidget(_label(str(dot_hits), _MUTED), r, 4)
            grid.addWidget(_label(ctx.fmt(dot), "color:#c9d1d9;font-size:12px;font-weight:700"), r, 5)
            r += 1
    grid.setColumnStretch(6, 1)
    col.addLayout(grid)
    if cap is not None:
        _hidden_rows(col, sum(len(v.steps) for v in visits) - listed)
    if member.missing:
        warn = _L('部分动作缺少动画数据，未计入伤害（结果偏低）') + ": " + ", ".join(map(str, member.missing))
        col.addWidget(_label(warn, "color:#e3b341;font-size:11px", wrap=True))
    return body


def _member_steps(lay: QVBoxLayout, expl, ctx: _Ctx, open_state: dict) -> None:
    if not expl.members:
        return
    lay.addWidget(_caption(_L('各队员循环')))
    by_member: dict = {}
    for visit in sorted(expl.visits, key=lambda v: v.index):
        by_member.setdefault(visit.character_id, []).append(visit)
    for member in expl.members:
        key = f"member:{member.character_id}"
        opened = bool(open_state.get(key, False))
        toggle = QPushButton(_toggle_text(member, ctx, opened))
        toggle.setObjectName("teamSimExplainToggle")
        toggle.setCheckable(True)
        toggle.setChecked(opened)
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.setStyleSheet(
            "QPushButton#teamSimExplainToggle{background:transparent;border:none;text-align:left;padding:2px 0px;"
            f"color:{_accent(ctx.color(member.character_id))};font-size:12px;font-weight:700}}")
        body = _member_body(member, by_member.get(member.character_id, ()), ctx, _custom_cap(expl, member=True))
        body.setVisible(opened)

        def on_toggled(checked, *, _key=key, _body=body, _btn=toggle, _member=member):
            open_state[_key] = bool(checked)
            _body.setVisible(bool(checked))
            _btn.setText(_toggle_text(_member, ctx, bool(checked)))

        toggle.toggled.connect(on_toggled)
        lay.addWidget(toggle)
        lay.addWidget(body)


def _unique(items) -> list:
    seen, out = set(), []
    for item in items:
        code, args = tx.split_note(item)
        key = (code, tuple(map(str, args)))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _notes(lay: QVBoxLayout, expl, ctx: _Ctx) -> None:
    assumptions, limits = _unique(expl.assumptions), _unique(expl.limits)
    if not assumptions and not limits:
        return
    lay.addWidget(_caption(_L('假设与限制')))
    for item in assumptions:
        lay.addWidget(_label("• " + tx.note_text(item, ctx.names), "color:#8b949e;font-size:12px", wrap=True))
    for item in limits:
        lay.addWidget(_label("⚠ " + tx.note_text(item, ctx.names), "color:#e3b341;font-size:12px", wrap=True))


# ── entry point ─────────────────────────────────────────────────────────────
def render_explanation(layout, expl, open_state: dict | None = None):
    """Append the explanation panel for ``expl`` (a TeamExplanation) to ``layout``; returns the frame.

    ``open_state`` is a dict owned by the caller; member sections store their expanded state
    under ``"member:<character_id>"`` so a re-render keeps them open.  ``expl=None`` (legacy
    result) adds nothing."""
    if expl is None:
        return None
    if open_state is None:
        open_state = {}
    ctx = _Ctx(expl)
    root = QFrame()
    root.setObjectName("teamSimExplain")
    root.setStyleSheet(themed_style("QFrame#teamSimExplain{background:#0d1117;border:1px solid #21262d;"
                                    "border-radius:8px}"))
    lay = QVBoxLayout(root)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    _header(lay, expl, ctx)
    _plan_section(lay, expl, ctx)
    _visit_flow(lay, expl, ctx)
    if getattr(expl, "custom", None) is not None:
        from src.features.team_simulation.custom_view import render_custom_steps

        render_custom_steps(lay, expl, ctx)
    _swap_grid(lay, expl, ctx)
    _member_steps(lay, expl, ctx, open_state)
    _notes(lay, expl, ctx)
    layout.addWidget(root)
    return root
