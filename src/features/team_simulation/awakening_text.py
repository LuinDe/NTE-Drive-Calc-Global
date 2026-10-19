# 队伍模拟队员卡的觉醒（韩文界面「돌파」）文字：数量标题、效果与共鸣的提示（不导入 Qt，便于测试）。
"""Texts of the member cards' awakening selection (Korean UI "돌파").  Qt-free.

``count_caption`` (the level = the number of selected effects), ``node_tooltip`` (name, description at the template's
skill levels, the node rules' marks: needs measurement / not computable - never shown as 0 % -, expected value,
pre-release data, the assumption sentence of low-confidence and expected-value nodes), ``resonance_tooltip``.
Game names and descriptions stay Chinese pieces that the display layer translates (``i18n_display.tr``); every
sentence is an ``_L`` / ``_LF`` key so a language switch can rebuild it.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

import re

from src.services import team_awakening

_TAG = re.compile(r"<[^>]*>")


def _game(text: str) -> str:
    try:
        from src.i18n_display import tr

        return tr(text)
    except Exception:
        return text


def _language() -> str:
    try:
        from src import i18n_runtime

        return str(i18n_runtime.get_language() or "zh")
    except Exception:
        return "zh"


def count_caption(count: int) -> str:
    """Card caption: awakenings made = selected effects (ko "돌파 n/6")."""
    return _LF('觉醒 {0}/6').format(int(count))


def resonance_caption(level: int) -> str:
    return _LF('共鸣{0}').format(int(level))


def display_label(sel) -> str:
    """Translated short label of a selection for the result cards (review UX F11): ko "돌파 3 · ①③⑤", "돌파 6" (all
    six), "돌파 0"; ``team_awakening.compact_label`` ("A3 · ①③⑤") stays the language-neutral form for saves."""
    sel = team_awakening.coerce(sel, team_awakening.EMPTY)
    head = _LF('觉醒 {0}').format(int(sel.level))
    if not sel.effects or (sel.level == team_awakening.MAX_LEVEL and sel.effects == team_awakening.NODE_IDS):
        return str(head)
    return f"{head} · {''.join(team_awakening.circled(e) for e in sel.effects)}"


def node_caption(node) -> str:
    """Awakening effect ③ (ko: 돌파 효과 ③); a resonance id gives its resonance caption."""
    canonical = team_awakening.node_id(node)
    if canonical in team_awakening.RESONANCE_LEVEL:
        return resonance_caption(team_awakening.RESONANCE_LEVEL[canonical])
    return _LF('觉醒效果 {0}').format(team_awakening.circled(node) or str(node))


def description(effect: dict) -> str:
    """The node's description: the exact DB text translated, the template's numbers in its placeholders, no markup."""
    raw = str(effect.get("description_zh") or "")
    text = str(_game(raw)) if raw else ""
    for index, value in sorted((effect.get("values") or {}).items(), key=lambda kv: int(kv[0])):
        text = text.replace("{" + str(int(index)) + "}", str(value))
    return _TAG.sub("", text).replace("\r\n", "\n").strip()


def info_lines(info, lang: str | None = None) -> list:
    """Marks of the node rules' metadata (awakening_node_rules.NodeInfo; None = nothing declared)."""
    if info is None:
        return []
    lang = lang or _language()
    out = []
    if info.bucket == "measure":
        out.append(_L('需要实测：模拟中未计入伤害（不是 0%）'))
    elif info.bucket == "not_computable":
        out.append(_L('无法计算：木桩模拟中不改变伤害'))
    if info.expected_value:
        out.append(_L('期望值：模拟器无法再现该条件，按期望值计算'))
    if info.pre_release:
        overlay = None
        try:            # Global live overlay on: the release data replaces the 9-24 values (some unverified)
            from src.services import global_live_overlay

            overlay = global_live_overlay.unverified_note()
        except Exception:
            overlay = None
        out.append(overlay or _L('上线前数据（9-24），数值可能与正式版不同'))
    if info.confidence == "low" or info.expected_value:
        text = info.text("assumption", lang)
        if text:
            out.append(_LF('假设：{0}').format(text))
    elif info.bucket != "now":
        text = info.text("reason", lang) or info.text("assumption", lang)
        if text:
            out.append(_LF('原因：{0}').format(text))
    return out


def node_tooltip(effect: dict, info=None, lang: str | None = None) -> str:
    """Tooltip of one effect toggle: "Awakening effect ③「name」", the description, the metadata marks."""
    node = str(effect.get("effect_id") or "")
    title = str(effect.get("title_zh") or "")
    lines = [_LF('觉醒效果 {0}「{1}」').format(team_awakening.circled(node) or node, _game(title))]
    text = description(effect)
    if text:
        lines.append(text)
    lines.extend(info_lines(info, lang))
    out = None
    for line in lines:
        out = line if out is None else out + "\n" + line
    return out or ""


def resonance_tooltip(effect: dict, level: int, active: bool, info=None, lang: str | None = None) -> str:
    """Tooltip of a resonance dot: name, "on at n awakenings, whatever effects are selected", state, description."""
    title = str(effect.get("title_zh") or "")
    lines = [_LF('共鸣{0}「{1}」').format(int(level), _game(title)),
             _LF('觉醒 {0} 次时生效，与所选效果无关').format(int(level)),
             _L('已激活') if active else _LF('未激活（需要觉醒 {0} 次）').format(int(level))]
    text = description(effect)
    if text:
        lines.append(text)
    lines.extend(info_lines(info, lang))
    out = None
    for line in lines:
        out = line if out is None else out + "\n" + line
    return out or ""


def menu_texts() -> dict:
    """The card's quick-selection menu (all / none / the graduation template)."""
    return {"all": _L('全选'), "none": _L('取消全选'), "template": _L('按毕业模板'), "tip": _L('觉醒效果快速选择')}
