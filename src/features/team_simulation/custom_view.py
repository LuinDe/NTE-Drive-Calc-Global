# 队伍模拟「直接输入」模式：错误/提示文本与结果下方的「输入的循环步骤」表。
"""Texts and result rendering of the team simulator's custom-cycle mode.

* ``issue_text(issue)``: a parser / validation issue (``team_custom_notation.ParseIssue``) as display text.
* code -> text helpers for the panel (gauge mode, check mode, manual buff kinds, elements, action tooltips).
* ``render_custom_header`` / ``render_custom_steps``: the custom parts of the explanation panel - header chips
  and the step table "输入的循环步骤" with one row per executed step (time, member, action, hits, damage, cycle
  gauge, notes).

Visible words go through _L / _LF with Chinese keys.  Notation tokens and member names inside the notation come
from ``team_custom_notation`` (they must round-trip through the parser), game names stay Chinese and are
translated by the display layer.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.app.theme import themed_style
from src.services import team_custom_notation as notation
from src.services import team_simulation_explanation as tx

ELEMENT_NAMES = {"cosmos": "光", "nature": "灵", "incantation": "咒", "chaos": "暗", "psyche": "魂",
                 "lakshana": "相", "psychically": "心灵"}      # game terms: the display layer translates them
WARNING_COLOR = "#e3b341"
# Every row of the result panel is a handful of widgets built on the UI thread (about 2 ms a step row, 8 ms a
# visit chip plus swap row), on every result, language switch and mode switch.  A long custom cycle is therefore
# listed up to these counts; the rest is counted in the totals and named in one line.
MAX_STEP_ROWS = 300             # rows of the step table
MAX_SECTION_ROWS = 60           # visit chips / swap-grid rows
MAX_MEMBER_ROWS = 120           # one member's step rows (the whole reviewed run has up to 60)


def current_lang() -> str:
    try:
        from src import i18n_runtime

        return i18n_runtime.get_language()
    except Exception:
        return "ko"


def _name_zh(character_id) -> str:
    try:
        from src.services import team_custom_actions as data

        return (data.PALETTE.get(int(character_id)) or {}).get("name_zh") or str(character_id)
    except Exception:
        return str(character_id)


def token_text(action: str, lang: str | None = None) -> str:
    return notation.canonical_token(action, lang or current_lang())


def _joined(items, sep: str = ", ") -> str:
    out = None
    for item in items:
        if item is None or item == "":
            continue
        out = item if out is None else out + sep + item
    return out or ""


# ── parser / validation issues ─────────────────────────────────────────────
def issue_text(issue, lang: str | None = None, *, with_segment: bool = True) -> str:
    """Display text of a ParseIssue; with its segment number in front when it has one."""
    lang = lang or current_lang()
    code, args = issue.code, tuple(issue.args)

    def arg(i, default=""):
        return args[i] if len(args) > i else default

    def hint(suggestions) -> str:
        names = _joined(str(s) for s in (suggestions or ()))
        return _LF('是不是：{0}？').format(names) if names else ""

    if code == "empty":
        text = _L('请先输入循环。')
    elif code == "no_character":
        text = _L('第一段需要写角色名。')
    elif code == "unknown_character":
        text = _LF('无法识别「{0}」。{1}').format(str(arg(0)), hint(arg(1, ())))
    elif code == "not_in_team":
        text = _LF('队伍中没有「{0}」。').format(str(arg(0)))
    elif code == "ambiguous_character":
        text = _LF('「{0}」对应多名队员：{1}').format(str(arg(0)), _joined(str(n) for n in arg(1, ())))
    elif code == "unknown_action":
        suggestions = hint(arg(2, ()))
        if not suggestions:
            suggestions = _LF('可用动作：{0}').format(_joined(str(t) for t in arg(3, ())))
        text = _LF('{0}：无法识别动作「{1}」。{2}').format(_name_zh(arg(0)), str(arg(1)), suggestions)
    elif code == "action_unavailable":
        text = _LF('{0} 没有「{1}」的数据。').format(_name_zh(arg(0)), token_text(str(arg(1)), lang))
    elif code == "bad_position":
        text = _LF('{0} 的「{1}」只有 {2} 个，不能选第 {3} 个。').format(
            _name_zh(arg(0)), token_text(str(arg(1)), lang) if arg(1) else "#", int(arg(3, 0) or 0),
            int(arg(2, 0) or 0))
    elif code == "bad_repeat":
        text = _LF('重复次数必须在 1–{0} 之间。').format(notation.MAX_STEP_REPEAT)
    elif code == "bad_wait":
        text = _LF('等待需要写秒数（最多 {0} 秒）。').format(f"{notation.MAX_WAIT_S:g}")
    elif code == "entry_on_field":
        text = _LF('{0} 已在场上，不能再用援护/切换登场。').format(_name_zh(arg(0)))
    elif code == "entry_not_first":
        text = _L('援护/切换必须写在该段的最前面。')
    elif code == "bad_raw":
        text = _LF('未知的动作标识 [{0}]。').format(str(arg(0)))
    elif code == "too_long":
        text = _LF('步骤过多（最多 {0} 步）。').format(int(arg(0, notation.MAX_STEPS) or notation.MAX_STEPS))
    elif code == "implicit_swap":
        text = _L('未写登场方式，按普通切换处理')
    else:
        text = code
    segment = int(getattr(issue, "segment", 0) or 0)
    if with_segment and segment > 0:
        return _LF('第 {0} 段：{1}').format(segment, text)
    return text


# ── code -> text ───────────────────────────────────────────────────────────
def action_tip(action: str) -> str:
    """Tooltip of a palette button ("" when the token needs no explanation)."""
    return {
        "support": _L('援护技登场：与切出队员属性相邻时触发环合反应'),
        "swap": _L('普通切换：不放援护技，不触发环合反应'),
        "basic": _L('普通攻击：连续输入会依次打出各段'),
        "heavy": _L('重击（长按普通攻击）'),
        "skill": "变轨技能",
        "skill_hold": _L('变轨技能长按'),
        "ult": "极轨终结",
        "counter": "极限反击",
        "dodge": _L('闪避（只占用时间）'),
        "plunge": _L('下落攻击'),
        "entry_attack": _L('登场攻击'),
        "special": _L('特殊动作'),
        "wait": _L('等待'),
    }.get(action, "")


def gauge_mode_text(code: str) -> str:
    return {tx.GAUGE_AS_TYPED: _L('按输入执行'), tx.GAUGE_CHECK: _L('检查环合值')}.get(code, code)


def resource_check_text(code: str) -> str:
    return {"off": _L('不检查'), "warn": _L('仅警告'), "wait": _L('插入等待')}.get(code, code)


def buff_kind_text(kind: str) -> str:
    return {
        "atk_pct": _L('攻击力 %'), "atk_flat": _L('攻击力（固定值）'), "crit_rate": _L('暴击率 %'),
        "crit_dmg": _L('暴击伤害 %'), "dmg_all": _L('伤害增强 %（全部）'), "dmg_element": _L('属性伤害增强 %'),
        "def_ignore": _L('防御无视 %'), "res_down": _L('敌人抗性降低 %'), "mag": _L('环合强度（数值）'),
    }.get(kind, kind)


def element_text(code) -> str:
    return ELEMENT_NAMES.get(str(code or ""), "") or _L('全部属性')


def buff_target_text(target, names=None) -> str:
    """"全队" / "敌人" / the member's Chinese name (translated by the display layer)."""
    if target == "team":
        return _L('全队')
    if target == "enemy":
        return _L('敌人')
    try:
        cid = int(target)
    except (TypeError, ValueError):
        return str(target)
    return (names or {}).get(cid) or _name_zh(cid)


def plain_swap_text() -> str:
    """Swap outcome of a typed plain swap (explanation_view._outcome_text)."""
    return _L('无反应：普通切换')


def moved_aside_text(path) -> str:
    """Status line when the account's cycle file could not be read and was renamed (store.load)."""
    from pathlib import Path

    return _LF('保存的循环文件无法读取，已改名保留为 {0}，保存列表从空白开始。').format(Path(str(path)).name)


def manual_skipped_text() -> str:
    """Mark of a manual buff the run left out because of its time window (result buff list)."""
    return _L('（未计入：时间范围无效或在战斗结束之后）')


# ── explanation panel: header and step table ───────────────────────────────
def _view():
    from src.features.team_simulation import explanation_view

    return explanation_view


def hidden_rows_label(count: int) -> QLabel:
    """The line under a capped list of a long custom cycle."""
    view = _view()
    label = view._label(_LF('其余 {0} 项未显示（已计入合计）').format(int(count)), view._MUTED)
    label.setObjectName("teamSimCustomHidden")
    return label


def render_custom_header(flow, expl, ctx) -> None:
    """Header chips of a custom cycle (instead of the order mode / gauge rule / loop chips)."""
    view = _view()
    custom = expl.custom
    order = view._join((ctx.name(cid) for cid in expl.order), " → ")
    flow.addWidget(view._info_chip(_L('直接输入'), order or "—"))
    mode_tip = (_L('援护始终按输入以援护技登场；环合值不足 100 时在该步骤显示警告。')
                if custom.gauge_mode == tx.GAUGE_AS_TYPED
                else _L('环合值不足 100 或属性不相邻时，援护改为普通切换。'))
    flow.addWidget(view._info_chip(_L('环合值模式'), gauge_mode_text(custom.gauge_mode), tip=mode_tip))
    gauges = view._join((view._piece(ctx.name(cid)) + f" {float(value):.0f}" for cid, value in custom.start_gauge),
                        " · ")
    flow.addWidget(view._info_chip(_L('开始时环合值'), gauges or "—"))
    flow.addWidget(view._info_chip(_L('重复次数'), str(int(custom.repeat))))
    flow.addWidget(view._info_chip(_L('冷却与能量'), resource_check_text(custom.resource_check)))


def step_action_text(step, lang: str | None = None) -> str:
    """Action column: canonical token plus the game's ability name; "普通攻击第 N 段" for a basic chain hit."""
    lang = lang or current_lang()
    if step.action == "wait":
        return token_text("wait", lang) + f" {float(step.duration_s):g}s"
    if step.action == notation.RAW_ACTION:
        key = step.keys[0] if step.keys else ("", "")
        if step.name_zh:
            return _LF('{0}「{1}」').format(f"[{key[0]}/{key[1]}]", step.name_zh)
        return f"[{key[0]}/{key[1]}]"
    token = token_text(step.action, lang)
    if step.action == "basic" and not step.state and step.pos:
        return _LF('普通攻击第 {0} 段').format(int(step.pos))
    if step.pos and step.pos > 1 and step.action in notation.SLOT_ACTIONS:
        token = f"{token}#{int(step.pos)}"
    if step.name_zh and (step.keys or step.status == tx.STEP_TIME_ONLY):
        return _LF('{0}「{1}」').format(token, step.name_zh)
    return token


def _note_parts(step, expl, ctx) -> list[tuple[str, bool]]:
    """[(text, is warning)] of the notes column."""
    view = _view()
    parts: list[tuple[str, bool]] = []
    swap = None
    if step.swap_index is not None:
        swap = next((s for s in expl.swaps if s.index == step.swap_index), None)
    reaction = expl.reaction_by_index().get(step.reaction_index) if step.reaction_index is not None else None
    if swap is not None and swap.outcome == tx.OUTCOME_PLAIN_SWAP:
        parts.append((plain_swap_text(), False))
    elif swap is not None and swap.outcome != tx.OUTCOME_REACTION:
        parts.append((view._outcome_text(swap), False))
    if step.out_character_id is not None and step.out_gauge is not None:
        parts.append((_LF('切出队员 {0} 的环合值 {1:.0f}').format(ctx.name(step.out_character_id),
                                                           float(step.out_gauge)), False))
    if reaction is not None and reaction.status != tx.REACTION_EFFECT_ONLY:
        parts.append((_L('环合反应') + " " + ctx.fmt(reaction.damage or 0.0), False))
    status = view._step_status_text(step.status)
    has_note = {tx.split_note(item)[0] for item in step.notes}
    if status and not (step.status == tx.STEP_TIME_ONLY and (tx.NOTE_CUSTOM_NO_ANIMATION in has_note
                                                             or step.action in ("wait", "dodge"))) \
            and not (step.status == tx.STEP_SKIPPED and has_note):
        parts.append((status, step.status == tx.STEP_MISSING))
    for item in step.notes:
        parts.append((tx.note_text(item, ctx.names), tx.split_note(item)[0] in tx.WARNING_NOTES))
    return parts


def render_custom_steps(lay: QVBoxLayout, expl, ctx) -> None:
    """The step table "输入的循环步骤": one row per executed step, a separator row per repeat."""
    custom = getattr(expl, "custom", None)
    if custom is None or not custom.steps:
        return
    view = _view()
    lang = current_lang()
    lay.addWidget(view._caption(_L('输入的循环步骤')))
    box = QFrame()
    box.setObjectName("teamSimCustomSteps")
    box.setStyleSheet(themed_style("QFrame#teamSimCustomSteps{background:#161b22;border:1px solid #21262d;"
                                   "border-radius:6px}"))
    grid = QGridLayout(box)
    grid.setContentsMargins(10, 8, 10, 8)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(4)
    heads = ("#", _L('时间'), _L('队员'), _L('动作'), _L('命中'), _L('伤害'), _L('环合值'), _L('备注'))
    for c, text in enumerate(heads):
        grid.addWidget(view._label(text, "color:#8b949e;font-size:11px;font-weight:700"), 0, c)
    reactions = expl.reaction_by_index()
    r = 1
    number = 0
    last_repeat = None
    for step in custom.steps[:MAX_STEP_ROWS]:
        if custom.repeat > 1 and step.repeat_index != last_repeat:
            tag = view._label(_LF('第 {0} 轮').format(step.repeat_index + 1),
                              "color:#8b949e;font-size:11px;font-weight:700;margin-top:4px")
            tag.setObjectName("teamSimCustomRepeat")
            grid.addWidget(tag, r, 0, 1, len(heads))
            r += 1
        last_repeat = step.repeat_index
        inserted = step.source_index < 0
        muted = inserted or step.status in (tx.STEP_SKIPPED, tx.STEP_TIME_ONLY)
        text_style = view._MUTED if muted else view._TEXT
        if not inserted:
            number += 1
        index_label = view._label("·" if inserted else str(number), view._MUTED)
        index_label.setObjectName("teamSimCustomStepIndex")
        grid.addWidget(index_label, r, 0, Qt.AlignTop)
        grid.addWidget(view._label(f"{step.start_s:.1f}s", view._MUTED), r, 1, Qt.AlignTop)
        grid.addWidget(ctx.name_label(step.character_id), r, 2, Qt.AlignTop)
        action = QWidget()
        action_row = QHBoxLayout(action)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(5)
        action_row.addWidget(view._label(step_action_text(step, lang), text_style))
        reaction = reactions.get(step.reaction_index) if step.reaction_index is not None else None
        if reaction is not None:
            action_row.addWidget(view._reaction_badge(reaction.reaction_zh))
        action_row.addStretch()
        grid.addWidget(action, r, 3, Qt.AlignTop)
        grid.addWidget(view._label(str(step.hits) if step.hits else "—", view._MUTED), r, 4, Qt.AlignTop)
        grid.addWidget(view._label(ctx.fmt(step.damage) if step.damage else "—",
                                   "color:#c9d1d9;font-size:12px;font-weight:700" if step.damage else view._MUTED),
                       r, 5, Qt.AlignTop)
        grid.addWidget(view._label(f"{float(step.gauge_after):.0f}", view._MUTED), r, 6, Qt.AlignTop)
        parts = _note_parts(step, expl, ctx)
        if parts:
            notes = QWidget()
            notes_col = QVBoxLayout(notes)
            notes_col.setContentsMargins(0, 0, 0, 0)
            notes_col.setSpacing(1)
            for text, warn in parts:
                tone = view._accent(WARNING_COLOR) if warn else None
                style = f"color:{tone};font-size:11px" if tone else view._MUTED
                label = view._label(text, style, wrap=True)
                label.setObjectName("teamSimCustomWarn" if warn else "teamSimCustomNote")
                notes_col.addWidget(label)
            grid.addWidget(notes, r, 7, Qt.AlignTop)
        r += 1
    grid.setColumnStretch(7, 1)
    lay.addWidget(box)
    if len(custom.steps) > MAX_STEP_ROWS:
        lay.addWidget(hidden_rows_label(len(custom.steps) - MAX_STEP_ROWS))
    if custom.warnings:
        lay.addWidget(view._label(_L('警告') + f" {int(custom.warnings)}",
                                  f"color:{view._accent(WARNING_COLOR)};font-size:12px;font-weight:700",
                                  align=Qt.AlignRight))


def member_toggle_text(member, ctx, opened: bool) -> str:
    """Member section title of a custom cycle: "직접 입력 · N단계" instead of verdict and confidence."""
    view = _view()
    return view._join((
        ("▼ " if opened else "▶ ") + view._piece(ctx.name(member.character_id)),
        view._role_text(member.role),
        _L('直接输入'),
        _LF('{0} 个步骤').format(int(member.steps_total)),
    ))


def result_buff_label(buff: dict, names=None) -> str:
    """Source column of a manual buff line in the result's buff list."""
    target = buff_target_text(buff.get("target", "team"), names)
    text = _L('手动') + " · " + buff_kind_text(str(buff.get("kind") or "")) + " · " + target
    if buff.get("element"):
        text = text + " · " + element_text(buff.get("element"))
    return text


def result_buff_value(buff: dict) -> str:
    """Value column of a manual buff line: the number as typed ("+20%", "10%" for a reduction, "+500")."""
    kind = str(buff.get("kind") or "")
    value = float(buff.get("value") or 0.0)
    if kind == "res_down":
        return f"{abs(value):g}%"
    return f"{value:+g}%" if kind in ("atk_pct", "crit_rate", "crit_dmg", "dmg_all", "dmg_element",
                                      "def_ignore") else f"{value:+g}"
