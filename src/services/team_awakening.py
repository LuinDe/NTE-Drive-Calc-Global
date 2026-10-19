# 队伍模拟：觉醒（韩文界面「돌파」）选择模型——觉醒等级 + 自由选择的普通觉醒效果集合（纯逻辑，不导入 Qt 与引擎）。
"""Awakening selection of a team-simulator member (Global; Korean UI label "돌파").

The game's state is (level L in 0..6, a set S of the six ordinary effects ``Effect1..Effect6``, |S| <= L).  The
effects are chosen freely and in any order (a path such as 3, 5, 1, 2, 4 only matters through the set it reaches);
the two resonances ``resonance_3`` / ``resonance_6`` and the skill-level bonus follow the level alone (L >= 3 / 6),
whatever effects are selected.  The upstream profile keeps the same model (``awakening_level`` +
``selected_awaken_effect_ids`` + ``awakening_selection_initialized``).

Compatibility rule (design_final §2.1, user decision 2026-10-18): a level without a set (an old save, an old caller
passing ``MemberSpec(awakening_level=N)``) means the first N effects ``Effect1..EffectN`` - exactly what the simulator
did before, so those results stay byte-identical.  A missing level and set means the graduation template's own
selection (today all 24 templates: level 6, ``Effect1..Effect6``).

Persistent ids (``"Effect3"``, ``"resonance_6"``) are plain ``str`` and are never translated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

NODE_IDS = ("Effect1", "Effect2", "Effect3", "Effect4", "Effect5", "Effect6")
RESONANCE_IDS = ("resonance_3", "resonance_6")
RESONANCE_LEVEL = {"resonance_3": 3, "resonance_6": 6}
MAX_LEVEL = 6
CIRCLED = ("①", "②", "③", "④", "⑤", "⑥")
_NODE_RE = re.compile(r"^effect([1-6])$", re.IGNORECASE)


@dataclass(frozen=True)
class AwakeningSel:
    """``level`` = awakenings made (0..6: resonances, skill +1); ``effects`` = selected ordinary effects, in ordinal
    order, no duplicates, ``len(effects) <= level``.  Build it with :func:`normalize` / :func:`legacy` / :func:`coerce`
    (the constructor does not repair its input)."""
    level: int
    effects: tuple = ()

    @property
    def count(self) -> int:
        return len(self.effects)

    def has(self, node) -> bool:
        return unlocked(self, node)

    def numbers(self) -> tuple:
        """Selected effect numbers (1..6) in order."""
        return tuple(i for i in (node_number(e) for e in self.effects) if i is not None)

    def is_legacy_prefix(self) -> bool:
        """True when the selection is exactly what a bare level means (Effect1..Effect<level>)."""
        return self.effects == NODE_IDS[:self.level]

    def as_json(self) -> dict:
        """The persistent pair (plain str ids)."""
        return {"awakening_level": int(self.level), "selected_awaken_effect_ids": [str(e) for e in self.effects]}


TEMPLATE = AwakeningSel(MAX_LEVEL, NODE_IDS)
EMPTY = AwakeningSel(0, ())


def node_number(node) -> int | None:
    """``"Effect3"`` / ``3`` / ``"3"`` -> 3; anything else (resonance ids included) -> None."""
    if isinstance(node, bool):
        return None
    if isinstance(node, int):
        return node if 1 <= node <= 6 else None
    text = str(node or "").strip()
    if text.isdigit():
        value = int(text)
        return value if 1 <= value <= 6 else None
    match = _NODE_RE.match(text)
    return int(match.group(1)) if match else None


def node_id(node) -> str | None:
    """Canonical id of an ordinary effect (``"Effect3"``) or a resonance (``"resonance_3"``); None if neither."""
    number = node_number(node)
    if number is not None:
        return NODE_IDS[number - 1]
    text = str(node or "").strip().lower()
    return text if text in RESONANCE_LEVEL else None


def _clamp_level(level) -> int:
    try:
        value = int(level or 0)
    except (TypeError, ValueError, OverflowError):
        value = 0
    return max(0, min(MAX_LEVEL, value))


def legacy(level) -> AwakeningSel:
    """A bare level (old saves / calls): ``Effect1..Effect<level>`` - the upstream compatibility rule."""
    value = _clamp_level(level)
    return AwakeningSel(value, NODE_IDS[:value])


def normalize(level, effects, valid_ids: Iterable[str] | None = None) -> AwakeningSel:
    """``effects`` None -> :func:`legacy` (``level``).  Otherwise unknown ids (not an ordinary effect, or not in
    ``valid_ids`` when given) are dropped, duplicates removed, the rest sorted by ordinal; the level is
    ``max(len(effects), level)`` clamped to 0..6 (an empty slot may be left open: level > count is allowed)."""
    if effects is None:
        return legacy(level)
    if isinstance(effects, (str, bytes)):
        effects = (effects,)
    allowed = None
    if valid_ids is not None:
        allowed = {e for e in (node_id(v) for v in valid_ids) if e in NODE_IDS}
    picked = set()
    for item in effects if isinstance(effects, Iterable) else ():
        canonical = node_id(item)
        if canonical in NODE_IDS and (allowed is None or canonical in allowed):
            picked.add(canonical)
    chosen = tuple(e for e in NODE_IDS if e in picked)
    return AwakeningSel(max(len(chosen), _clamp_level(level)), chosen)


def from_profile(profile: Mapping | None) -> AwakeningSel:
    """A template / account profile: its stored set when ``awakening_selection_initialized`` is true, else the
    legacy reading of its level (the upstream rule for profiles without the flag)."""
    profile = profile or {}
    level = profile.get("awakening_level", 0)
    if profile.get("awakening_selection_initialized"):
        return normalize(level, list(profile.get("selected_awaken_effect_ids") or ()))
    return legacy(level)


def coerce(value, default: AwakeningSel | None = None) -> AwakeningSel:
    """int (legacy level) | AwakeningSel | {"awakening_level", "selected_awaken_effect_ids"} or {"level", "effects"}
    | (level, effects) -> AwakeningSel.  None (or something unreadable) -> ``default`` (TEMPLATE when not given)."""
    if isinstance(value, AwakeningSel):
        return value
    if value is None:
        return TEMPLATE if default is None else default
    if isinstance(value, bool):
        return TEMPLATE if default is None else default
    if isinstance(value, int):
        return legacy(value)
    if isinstance(value, Mapping):
        if "selected_awaken_effect_ids" in value or "awakening_level" in value:
            ids = value.get("selected_awaken_effect_ids")
            return normalize(value.get("awakening_level"), ids if isinstance(ids, (list, tuple)) else None)
        if "effects" in value or "level" in value:
            ids = value.get("effects")
            return normalize(value.get("level"), ids if isinstance(ids, (list, tuple)) else None)
        return TEMPLATE if default is None else default
    if isinstance(value, (list, tuple)) and len(value) == 2 and not isinstance(value[1], (str, bytes)):
        return normalize(value[0], value[1])
    try:
        return legacy(int(value))
    except (TypeError, ValueError, OverflowError):
        return TEMPLATE if default is None else default


def resolve_spec(level, effects, template_profile: Mapping | None, valid_ids: Iterable[str] | None = None
                 ) -> AwakeningSel:
    """The selection of one ``MemberSpec``: nothing given -> the template profile's own selection; a level only ->
    legacy; a set -> that set (level = max(level, count))."""
    if level is None and effects is None:
        return from_profile(template_profile)
    if effects is None:
        return legacy(level)
    return normalize(level, effects, valid_ids)


def unlocked(sel, node) -> bool:
    """Is ``node`` active for the selection?  None -> True (no requirement); an int n / ``"Effect<n>"`` -> the effect
    is selected (team_resource_data rules store the node number n = Effect n, design A8); ``"resonance_3"`` /
    ``"resonance_6"`` -> level >= 3 / 6.  ``sel`` may be anything :func:`coerce` reads."""
    if node is None:
        return True
    sel = coerce(sel, EMPTY)
    canonical = node_id(node)
    if canonical in RESONANCE_LEVEL:
        return sel.level >= RESONANCE_LEVEL[canonical]
    if canonical in NODE_IDS:
        return canonical in sel.effects
    return False


def circled(node) -> str:
    """①..⑥ for an ordinary effect, '' otherwise."""
    number = node_number(node)
    return CIRCLED[number - 1] if number else ""


def compact_label(sel) -> str:
    """Language-neutral short label: ``"A6"`` (all six), ``"A0"``, ``"A1 · ⑥"``, ``"A3 · ①③⑤"``; a level above the
    count shows the count of selected effects after the level only through the circles (``"A3 · ①"``)."""
    sel = coerce(sel, EMPTY)
    if sel.level == MAX_LEVEL and sel.effects == NODE_IDS:
        return "A6"
    if not sel.effects and sel.level == 0:
        return "A0"
    marks = "".join(circled(e) for e in sel.effects)
    return f"A{sel.level} · {marks}" if marks else f"A{sel.level}"


def to_json_row(sel) -> dict:
    """Team-row fields of a saved custom cycle (``awakening_level`` = level, ``selected_awaken_effect_ids``)."""
    return coerce(sel, EMPTY).as_json()


def from_json_row(row: Mapping | None, valid_ids: Iterable[str] | None = None,
                  template: AwakeningSel | None = None) -> AwakeningSel:
    """A saved team row: a list under ``selected_awaken_effect_ids`` -> that set (unknown ids dropped); no key (an
    old save) -> legacy ``Effect1..awakening_level``; a malformed value -> ``template`` (TEMPLATE when not given)."""
    template = TEMPLATE if template is None else template
    if not isinstance(row, Mapping):
        return template
    level = row.get("awakening_level")
    if level is not None:
        try:
            level = int(level)
        except (TypeError, ValueError, OverflowError):
            return template
        if not 0 <= level <= MAX_LEVEL:
            return template
    if "selected_awaken_effect_ids" in row:
        ids = row.get("selected_awaken_effect_ids")
        if not isinstance(ids, (list, tuple)) or not all(isinstance(x, str) for x in ids):
            return template
        return normalize(level or 0, ids, valid_ids)
    if level is None:
        return template
    return legacy(level)


def selections_of(characters: Iterable[Mapping]) -> dict:
    """{character id: AwakeningSel} of ``team_simulation_service._build_characters`` entries."""
    out: dict[int, AwakeningSel] = {}
    for c in characters or ():
        sel = c.get("_awakening")
        if not isinstance(sel, AwakeningSel):
            sel = from_profile(c.get("profile") or {"awakening_level": c.get("awakening_level")})
        out[int(c["character_id"])] = sel
    return out


def describe(sel: Any) -> str:
    """Debug text (``level=3 effects=Effect1,Effect3``)."""
    sel = coerce(sel, EMPTY)
    return f"level={sel.level} effects={','.join(sel.effects) or '-'}"
