# 队伍模拟：环合（元素环、环合值规则、反应排程、覆纹/浸染重放后公式）。
"""Esper Cycle (环合) model for the team simulator.

Every simulated swap goes through :class:`CycleGauge`; every reaction that fires is
scheduled by :class:`ReactionScheduler`, which turns it into synthetic battle-axis hit
rows (浊燃 / 黯星 / 创生 and the 延滞 suit marker) for the existing replay engine, plus
the 覆纹 / 浸染 windows whose damage is added after replay by :func:`apply_hexed` /
:func:`apply_stain`.  Reactions are always computed; there is deliberately no switch.
With Zankou in the team the simulator also passes its damage-over-time ticks
(:meth:`ReactionScheduler.set_dot_ticks`): Zankou's Scorch waits for a DoT tick and every DoT
tick refreshes it, as in the game and the replay engine.

Clocks: every reaction timer runs on the *active* clock (time stops excluded).  The
scheduler receives two callables, ``to_active(wall_us)`` and ``to_wall(active_us)``,
which are evaluated lazily (when rows / windows are produced), so time stops appended
after a trigger are still honoured.  :func:`make_clock` builds them from stop intervals.

Facts come from ``reaction_definition`` / ``combat_effect_constant`` /
``combat_level_curve_point`` / ``gameplay_ability_description`` with fallbacks (see
:func:`load_rules`).  Hand-entered: the brief's five constants below, the reaction names
by element pair (the database has no name column), and model defaults that are not in
the database at all (Blossom flower schedule, plant cap, gauge cap, Discord topple share).

Explanation objects store only codes and Chinese game names; nothing here is translated.
The module imports engine services lazily and never imports Qt.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from math import floor
from pathlib import Path
from typing import Any

# ── brief §4: the only hand-entered numbers besides the fallbacks ─────────
LINKO_HEXED_EXTENSION = 0.13          # 覆纹 extension with Linko passive 1 (data: 1.33K−1)
LINKO_PASSIVE_ID = "PASSIVE-1072-GA_Radio072_Passive_1"
RAVEN_PASSIVE_ID = "PASSIVE-1042-GA_BlackBird_Passive_1"
STAIN_SCOPE = ("psyche", "lakshana")  # 浸染 scope (constant text "浸染魂/相伤害基础提升")
SCORCH_TICK_S = 0.99                  # Reaction_ZhouAn_Period (1 s) × blueprint 0.99
# Zankou's Scorch stays dormant until a non-Scorch damage-over-time tick arrives; the first Scorch tick
# follows that DoT tick by 0.027 s (battle 1) / 0.082 s (battle 2) of active time (measured).
ZANKOU_SCORCH_ACTIVATION_S = 0.03

# identities used by the rules below (character ids / passive ids are data keys)
ZANKOU_ID = 1036
KUHARA_PASSIVE_ID = "PASSIVE-1055-GA_Kuhara_Passive_1"
HATHOR_PASSIVE_ID = "PASSIVE-1025-GA_Hathor_Passive_1"
REMORA_MARKER_GE = "Buff_Reaction_3_new"   # 延滞 buff (Reaction3 folder); no damage curve
REMORA_MARKER_OFFSET_S = 5.0               # suit rule SUIT_TEAM_REACTION_AFTER|reaction_remora:5

RING = ("cosmos", "nature", "incantation", "chaos", "psyche", "lakshana")
ELEMENT_ZH = {"cosmos": "光", "nature": "灵", "incantation": "咒",
              "chaos": "暗", "psyche": "魂", "lakshana": "相"}

# reaction names keyed by the unordered element pair (reaction_definition has no name column)
_PAIR_NAMES = {
    frozenset(("cosmos", "nature")): ("创生", "blossom"),
    frozenset(("nature", "incantation")): ("覆纹", "hexed"),
    frozenset(("incantation", "chaos")): ("浊燃", "scorch"),
    frozenset(("chaos", "psyche")): ("黯星", "nova"),
    frozenset(("psyche", "lakshana")): ("浸染", "stain"),
    frozenset(("lakshana", "cosmos")): ("延滞", "remora"),
}
COMBOS = {"盈蓄": ("charge", ("创生", "延滞")), "失谐": ("discord", ("浊燃", "黯星"))}
CODE_BY_ZH = {**{zh: code for zh, code in _PAIR_NAMES.values()},
              **{zh: code for zh, (code, _parts) in COMBOS.items()}}

# used only when the static database cannot be read (verified rows 42238–42243)
_FALLBACK_DEFINITIONS = (
    ("REACTION_RESULT_TYPE_1", "cosmos", "nature", "GE_ActorReaction_1_Damage"),
    ("REACTION_RESULT_TYPE_2", "nature", "incantation", None),
    ("REACTION_RESULT_TYPE_3", "incantation", "chaos", "Buff_Reaction_5_new"),
    ("REACTION_RESULT_TYPE_4", "chaos", "psyche", "Buff_Reaction_4_new"),
    ("REACTION_RESULT_TYPE_5", "psyche", "lakshana", None),
    ("REACTION_RESULT_TYPE_6", "lakshana", "cosmos", None),
)
_FALLBACK_CONSTANTS = {
    "Reaction_ZhouAn_BuffTime": 15.0,
    "Reaction_ZhouAn_Period": 1.0,
    "Reaction_AnHun_BuffTime": 5.0,
    "Reaction_LingZhou_BuffTime": 12.0,
    "LingZhouCopyCoef": 0.2,
    "Reaction_HunXiang_BuffTime": 12.0,
    "Reaction_HunXiang_DamageUP": 0.2,
    "Reaction_HunXiang1_Time_1042": 8.0,
    "Reaction_GuangXiang_BuffTime": 5.0,
    "Reaction_GuangXiang5_TimeAdd_1025": 7.0,
    "Reaction_GuangLingXiang_Charge": 10.0,
    "Reaction_GuangLingXiang_ChargeCD": 0.8,
}
_FALLBACK_CURVES = {   # Lv80 tier only; full 16-tier curves come from the database
    "Buff_Reaction_5_new": 2700.0, "Buff_Reaction_5_new_1036": 2700.0,
    "Buff_Reaction_4_new": 45000.0, "GE_ActorReaction_1_Damage": 9000.0,
}
# model values that the static database does not hold (brief §1.4, reaction-rules)
_MODEL_DEFAULTS = {
    "gauge_cap": 100.0,
    "blossom_flowers": 5,
    "blossom_interval_s": 2.0,       # inference: flowers at +2, 4, 6, 8, 10 s
    "blossom_plant_limit": 3,
    "discord_topple_reduction": 0.15,  # project default, not in the data
    "raven_stain_damage_up": 0.3,    # GA_BlackBird_Passive_1 text (parsed when present)
    "kuhara_plant_limit": 6,         # GA_Kuhara_Passive_1 text (parsed when present)
    "zankou_opening_gauge": 100.0,   # GA_Zankou_Passive2 text (parsed when present)
}
_GAUGE_EPS = 1e-6
# User rule (2026-10-04, "사이클 수치는 1,3바퀴만 100"): every member's cycle gauge is set to 100 at the start of
# these loops (1-based); every other loop keeps the gauge the members built up (game rule).
FULL_GAUGE_LOOPS = (1, 3)
OWNER_RULE_CODES = frozenset(("scorch", "nova", "blossom"))
ENGINE_LABELS = {"scorch": "浊燃", "nova": "黯星", "blossom": "创生", "remora": "延滞"}
SUPPORT_SKILL_REACTION_LABELS = frozenset(("浊燃", "浸染", "创生"))

# brief §1.5: known exclusions per reaction → (character, limit code); plus the reaction passives the
# simulator does not compute (gameplay_ability_description texts; derived_hit / target_state passives of
# battle_character_passive_service only attribute recorded hits), so none of them is dropped silently.
_NANALLY_FOLLOW_UP = (1010, "reaction_followup")      # GA_Nanally_Passive_2: follow-up per cycle damage
_EXCLUSIONS = {
    "scorch": ((1033, "scorch_adler_variant"), (1023, "scorch_cang_reapply"), _NANALLY_FOLLOW_UP),
    "discord": ((1054, "discord_daffodill_topple"), (1004, "discord_lacrimosa_hit")),
    "charge": ((1021, "charge_passive"), (1073, "charge_passive"), (1076, "charge_passive")),
    "nova": ((1020, "nova_extra"), (1039, "nova_extra"), (1042, "nova_extra"), (1070, "nova_extra"),
             _NANALLY_FOLLOW_UP),
    "blossom": ((1075, "blossom_copy_curve"), (1019, "blossom_copy_curve"), (1010, "blossom_volley"),
                (1055, "blossom_rose_settlement"), (1052, "blossom_time_stop"), _NANALLY_FOLLOW_UP),
    "hexed": ((1072, "hexed_linko_bonus"), _NANALLY_FOLLOW_UP),
    "remora": ((1071, "remora_end_damage"), (1057, "remora_reapply_damage"), (1025, "remora_crit_bonus")),
}


# ── elements and rules ─────────────────────────────────────────────────────

def normalize_element(value: Any) -> str:
    """'ECharacterElementType::CHARACTER_ELEMENT_TYPE_CHAOS' -> 'chaos'."""
    text = str(value or "").strip()
    if not text:
        return ""
    return text.rsplit("::", 1)[-1].rsplit("_", 1)[-1].casefold()


def is_adjacent(e1: str, e2: str) -> bool:
    if e1 not in RING or e2 not in RING or e1 == e2:
        return False
    return (RING.index(e1) - RING.index(e2)) % len(RING) in (1, len(RING) - 1)


def element_of(con, character_id: int) -> str:
    """Element code of one character from ``character.element_type`` ('' when unknown)."""
    with _connection(con) as db:
        if db is None:
            return ""
        row = db.execute("SELECT element_type FROM character WHERE character_id=?",
                         (int(character_id),)).fetchone()
    return normalize_element(row[0]) if row else ""


@dataclass(frozen=True, slots=True)
class ReactionDef:
    reaction_type: str           # REACTION_RESULT_TYPE_n ('' for combos)
    zh: str                      # 创生 / 覆纹 / 浊燃 / 黯星 / 浸染 / 延滞
    code: str                    # blossom / hexed / scorch / nova / stain / remora
    elements: tuple[str, str]
    damage_effect_id: str | None


@dataclass(frozen=True)
class ReactionRules:
    reactions: tuple[ReactionDef, ...]
    constants: Mapping[str, float]
    elements: Mapping[int, str] = field(default_factory=dict)
    level_curves: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    model: Mapping[str, float] = field(default_factory=lambda: dict(_MODEL_DEFAULTS))
    source: str = "fallback"                 # database | fallback
    fallbacks: tuple[str, ...] = ()          # constant ids that used the fallback value

    # lookups
    def reaction_for(self, e1: str, e2: str) -> ReactionDef | None:
        key = frozenset((normalize_element(e1), normalize_element(e2)))
        return next((r for r in self.reactions if frozenset(r.elements) == key), None)

    def by_zh(self, zh: str) -> ReactionDef | None:
        return next((r for r in self.reactions if r.zh == zh), None)

    def element(self, character_id: int | None) -> str:
        return self.elements.get(int(character_id), "") if character_id is not None else ""

    def constant(self, constant_id: str) -> float:
        if constant_id in self.constants:
            return float(self.constants[constant_id])
        return float(_FALLBACK_CONSTANTS[constant_id])

    def level_value(self, curve_id: str, character_level: float = 80.0) -> float | None:
        curve = self.level_curves.get(curve_id)
        if not curve:
            return _FALLBACK_CURVES.get(curve_id)
        level = int(max(1, min(80, round(float(character_level or 80)))))
        return float(curve[min(len(curve) - 1, (level - 1) // 5)])

    # derived values (seconds unless stated)
    @property
    def gauge_cap(self) -> float:
        return float(self.model["gauge_cap"])

    @property
    def scorch_duration_s(self) -> float:
        return self.constant("Reaction_ZhouAn_BuffTime")

    @property
    def scorch_tick_s(self) -> float:
        return SCORCH_TICK_S * self.constant("Reaction_ZhouAn_Period")

    @property
    def nova_delay_s(self) -> float:
        return self.constant("Reaction_AnHun_BuffTime")

    @property
    def hexed_duration_s(self) -> float:
        return self.constant("Reaction_LingZhou_BuffTime")

    @property
    def hexed_copy_coef(self) -> float:
        return self.constant("LingZhouCopyCoef")

    @property
    def stain_duration_s(self) -> float:
        return self.constant("Reaction_HunXiang_BuffTime")

    @property
    def stain_damage_up(self) -> float:
        return self.constant("Reaction_HunXiang_DamageUP")

    @property
    def raven_stain_duration_s(self) -> float:
        return self.stain_duration_s + self.constant("Reaction_HunXiang1_Time_1042")

    @property
    def raven_stain_damage_up(self) -> float:
        return float(self.model["raven_stain_damage_up"])

    @property
    def remora_duration_s(self) -> float:
        return self.constant("Reaction_GuangXiang_BuffTime")

    @property
    def hathor_remora_duration_s(self) -> float:
        return self.remora_duration_s + self.constant("Reaction_GuangXiang5_TimeAdd_1025")

    @property
    def charge_energy(self) -> float:
        return self.constant("Reaction_GuangLingXiang_Charge")

    @property
    def charge_cd_s(self) -> float:
        return self.constant("Reaction_GuangLingXiang_ChargeCD")


class _connection:
    """Accept a sqlite3 connection, a database path, a StaticGameDataDao, or None (fallback)."""

    def __init__(self, con):
        self._given = con
        self._own = None

    def __enter__(self):
        con = self._given
        if con is None:
            return None
        if not hasattr(con, "execute") and getattr(con, "database_path", None) is not None:
            con = con.database_path          # StaticGameDataDao: open a private read-only handle
        if isinstance(con, (str, Path)):
            path = Path(con)
            if not path.exists():
                return None
            self._own = sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)
            return self._own
        return con

    def __exit__(self, *exc):
        if self._own is not None:
            self._own.close()
        return False


def _fallback_reactions() -> tuple[ReactionDef, ...]:
    out = []
    for rtype, e1, e2, ge in _FALLBACK_DEFINITIONS:
        zh, code = _PAIR_NAMES[frozenset((e1, e2))]
        out.append(ReactionDef(rtype, zh, code, (e1, e2), ge))
    return tuple(out)


def _parse_number(pattern: str, text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def load_rules(con=None) -> ReactionRules:
    """Reaction pairs, constants, level curves and character elements from the static DB.

    ``con`` may be a sqlite3 connection, a database path or None.  Every value that is
    missing falls back to the verified defaults and is listed in ``rules.fallbacks``.
    """
    with _connection(con) as db:
        if db is None:
            return ReactionRules(reactions=_fallback_reactions(), constants=dict(_FALLBACK_CONSTANTS),
                                 source="fallback", fallbacks=tuple(sorted(_FALLBACK_CONSTANTS)))
        reactions: list[ReactionDef] = []
        try:
            rows = db.execute("SELECT reaction_type, element_type_1, element_type_2, default_damage_effect_id "
                              "FROM reaction_definition ORDER BY reaction_type").fetchall()
        except sqlite3.Error:
            rows = []
        for rtype, e1, e2, ge in rows:
            pair = (normalize_element(e1), normalize_element(e2))
            names = _PAIR_NAMES.get(frozenset(pair))
            if names is None:
                continue
            reactions.append(ReactionDef(str(rtype), names[0], names[1], pair, ge or None))
        if len(reactions) != len(_PAIR_NAMES):
            reactions = list(_fallback_reactions())
        constants: dict[str, float] = {}
        try:
            for cid, value in db.execute("SELECT constant_id, value FROM combat_effect_constant "
                                         "WHERE constant_id LIKE 'Reaction%' OR constant_id LIKE 'LingZhou%'"):
                if value is not None:
                    constants[str(cid)] = float(value)
        except sqlite3.Error:
            pass
        fallbacks = tuple(sorted(k for k in _FALLBACK_CONSTANTS if k not in constants))
        for key in fallbacks:
            constants[key] = _FALLBACK_CONSTANTS[key]
        elements: dict[int, str] = {}
        try:
            for cid, et in db.execute("SELECT character_id, element_type FROM character"):
                elements[int(cid)] = normalize_element(et)
        except sqlite3.Error:
            pass
        curves: dict[str, list[tuple[int, float]]] = {}
        try:
            for curve_id, tier, value in db.execute(
                    "SELECT curve_id, source_tier, value FROM combat_level_curve_point "
                    "WHERE curve_id LIKE 'reaction:%' ORDER BY curve_id, ordinal"):
                curves.setdefault(str(curve_id).removeprefix("reaction:"), []).append((int(tier), float(value)))
        except sqlite3.Error:
            pass
        level_curves = {k: tuple(v for _t, v in sorted(rows)) for k, rows in curves.items()}
        model = dict(_MODEL_DEFAULTS)
        texts: dict[str, str] = {}
        try:
            for ability, text in db.execute(
                    "SELECT ability_id, description_zh FROM gameplay_ability_description WHERE ordinal=0 AND "
                    "ability_id IN ('GA_BlackBird_Passive_1','GA_Kuhara_Passive_1','GA_Zankou_Passive2')"):
                texts[str(ability)] = str(text or "")
        except sqlite3.Error:
            pass
        raven_up = _parse_number(r"「浸染」的基础增伤效果提升至\D*?(\d+(?:\.\d+)?)%", texts.get("GA_BlackBird_Passive_1"))
        if raven_up is not None:
            model["raven_stain_damage_up"] = raven_up / 100.0
        kuhara_cap = _parse_number(r"存在上限提升至\D*?(\d+)\D*?株", texts.get("GA_Kuhara_Passive_1"))
        if kuhara_cap is not None:
            model["kuhara_plant_limit"] = int(kuhara_cap)
        zankou_gauge = _parse_number(r"「环合值」为\D*?(\d+(?:\.\d+)?)", texts.get("GA_Zankou_Passive2"))
        if zankou_gauge is not None:
            model["zankou_opening_gauge"] = zankou_gauge
    return ReactionRules(reactions=tuple(reactions), constants=constants, elements=elements,
                         level_curves=level_curves, model=model, source="database", fallbacks=fallbacks)


DEFAULT_RULES = load_rules(None)


def reaction_for(e1: str, e2: str, rules: ReactionRules | None = None) -> ReactionDef | None:
    """The reaction of an unordered adjacent pair, or None (same element / not adjacent)."""
    return (rules or DEFAULT_RULES).reaction_for(e1, e2)


def support_skill_attack_type(reaction: ReactionDef | str | None, first_damage_hit: bool) -> str:
    """Label for a support-skill hit (brief §2.1): only the first damage hit of a 浊燃 /
    浸染 / 创生 entry carries ``环合·<名>``; every other support-skill hit is plain ``环合``."""
    zh = reaction.zh if isinstance(reaction, ReactionDef) else (reaction or "")
    if first_damage_hit and zh in SUPPORT_SKILL_REACTION_LABELS:
        return f"环合·{zh}"
    return "环合"


# ── formulas (pure; the engine computes the injected reactions itself) ─────

def weave_strength_multiplier(ring_strength: float) -> float:
    """K = 1 + 0.2·M/(M+180) (same as damage_calculation_service.calculate_weave_strength_multiplier)."""
    m = max(0.0, float(ring_strength or 0.0))
    return 1.0 + 0.20 * m / (m + 180.0)


def window_damage_factor(ring_strength: float, extra_ratio: float) -> float:
    """Hexed / Stain increment per unit of the hit's final damage: (1 + c)·K − 1."""
    return (1.0 + float(extra_ratio)) * weave_strength_multiplier(ring_strength) - 1.0


def ring_strength_multiplier(ring_strength: float) -> float:
    return 1.0 + max(0.0, float(ring_strength or 0.0)) / 600.0


def scorch_tick_value(base: float, *, layers: int = 1, ring_strength: float = 0.0, defense: float = 1.0,
                      resistance: float = 1.0, vulnerability: float = 1.0, dot_final: float = 1.0,
                      crit_damage: float | None = None) -> float:
    """floor(base × layers × (1+Mag/600) × def × res × vuln × dot_final [× (1+crit dmg)])."""
    raw = (base * layers * ring_strength_multiplier(ring_strength) * defense * resistance
           * vulnerability * max(1.0, dot_final))
    if crit_damage is not None:
        raw *= 1.0 + crit_damage
    return float(floor(max(0.0, raw)))


def nova_value(base: float, *, ring_strength: float = 0.0, resistance: float = 1.0,
               vulnerability: float = 1.0) -> float:
    """floor(base × (1+Mag/600) × psychically resistance × vuln); no defense, no crit."""
    return float(floor(max(0.0, base * ring_strength_multiplier(ring_strength) * resistance * vulnerability)))


def blossom_value(base: float, *, ring_strength: float = 0.0, defense: float = 1.0, resistance: float = 1.0,
                  vulnerability: float = 1.0) -> float:
    """floor(base × (1+Mag/600) × def × res × vuln); no crit."""
    return float(floor(max(0.0, base * ring_strength_multiplier(ring_strength) * defense
                           * resistance * vulnerability)))


def hexed_extra_ratio(rules: ReactionRules | None, passive_ids: Iterable[str]) -> float:
    rules = rules or DEFAULT_RULES
    return rules.hexed_copy_coef + (LINKO_HEXED_EXTENSION if LINKO_PASSIVE_ID in set(passive_ids) else 0.0)


def stain_parameters(rules: ReactionRules | None, passive_ids: Iterable[str]) -> tuple[float, float]:
    """(window seconds, extra ratio) for 浸染; Raven's passive gives 20 s and 30 %."""
    rules = rules or DEFAULT_RULES
    if RAVEN_PASSIVE_ID in set(passive_ids):
        return rules.raven_stain_duration_s, rules.raven_stain_damage_up
    return rules.stain_duration_s, rules.stain_damage_up


# ── passives and clocks ────────────────────────────────────────────────────

def _build_rows(build: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return [row for row in ((build or {}).get("characters") or ()) if isinstance(row, Mapping)]


def _stage(character: Mapping[str, Any]) -> int | None:
    profile = character.get("profile") if isinstance(character.get("profile"), Mapping) else {}
    if "breakthrough_stage" not in character and "breakthrough_stage" not in profile:
        return None
    return max(int(character.get("breakthrough_stage") or 0), int(profile.get("breakthrough_stage") or 0))


def team_passive_ids(build: Mapping[str, Any] | None, baselines: Iterable[Any] = ()) -> frozenset[str]:
    """Enabled team passive ids: the engine catalog (as baselines carry them) plus Raven.

    Raven's passive is not in ``BattleCharacterPassiveService``'s catalog (verified), so
    it is added here with the catalog's Passive_1 unlock rule (breakthrough stage >= 2).
    """
    ids: set[str] = set()
    try:
        from src.services.battle_character_passive_service import BattleCharacterPassiveService
        ids.update(row.definition.passive_id for row in BattleCharacterPassiveService.enabled_passives(build))
    except Exception:  # pragma: no cover - engine missing; fall back to stage checks below
        for character in _build_rows(build):
            cid = int(character.get("character_id") or 0)
            for pid in (LINKO_PASSIVE_ID, KUHARA_PASSIVE_ID, HATHOR_PASSIVE_ID):
                if pid.split("-")[1] == str(cid) and (_stage(character) or 0) >= 2:
                    ids.add(pid)
    for baseline in baselines or ():
        ids.update(getattr(baseline, "enabled_team_passive_ids", ()) or ())
    raven_id = int(RAVEN_PASSIVE_ID.split("-")[1])
    for character in _build_rows(build):
        if int(character.get("character_id") or 0) == raven_id and (_stage(character) or 0) >= 2:
            ids.add(RAVEN_PASSIVE_ID)
    return frozenset(ids)


def zankou_variant_active(build: Mapping[str, Any] | None) -> bool:
    """True when every 浊燃 becomes Zankou's ``_1036`` variant (engine rule, stage >= 2)."""
    try:
        from src.services.battle_dot_stack_state_service import zankou_scorch_variant_for_build
        return zankou_scorch_variant_for_build(build) == "zankou"
    except Exception:  # pragma: no cover
        for character in _build_rows(build):
            if int(character.get("character_id") or 0) == ZANKOU_ID:
                stage = _stage(character)
                return stage is not None and stage >= 2
        return False


_FAR_END_US = 10 ** 13


def _stop_pairs(stops: Iterable[Any]) -> tuple[tuple[int, int], ...]:
    """Accept (start_us, end_us) pairs or evidence dicts with ``raw_interval`` seconds."""
    out = []
    for stop in stops or ():
        if isinstance(stop, Mapping):
            raw = stop.get("raw_interval") if isinstance(stop.get("raw_interval"), Mapping) else stop
            start, end = raw.get("start_offset_seconds"), raw.get("end_offset_seconds")
            if start is None or end is None:
                continue
            out.append((int(round(float(start) * 1e6)), int(round(float(end) * 1e6))))
        else:
            start, end = stop
            if start is None or end is None:
                continue
            out.append((int(start), int(end)))
    return tuple(out)


def make_clock(stops: Sequence[Any], *, battle_start_us: int = 0
               ) -> tuple[Callable[[int], int], Callable[[int], int]]:
    """``(to_active, to_wall)`` over a (possibly still growing) list of stop intervals.

    Uses ``battle_timeline_time_service`` in ACTIVE mode with the engine's origin 0; the
    list is re-read on every call, so stops appended later are honoured.
    """
    from src.services.battle_timeline_time_service import (
        ACTIVE_TIME_MODE, project_timeline_time_us, unproject_timeline_time_us,
    )

    def to_active(wall_us: int) -> int:
        return int(project_timeline_time_us(int(wall_us), battle_start_us=battle_start_us,
                                            intervals=_stop_pairs(stops), mode=ACTIVE_TIME_MODE))

    def to_wall(active_us: int) -> int:
        return int(unproject_timeline_time_us(int(active_us), battle_start_us=battle_start_us,
                                              battle_end_us=_FAR_END_US, intervals=_stop_pairs(stops),
                                              mode=ACTIVE_TIME_MODE))

    return to_active, to_wall


def _identity(value: int) -> int:
    return int(value)


# ── gauge ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SwapDecision:
    entry: str                 # support_skill | normal
    outcome: str               # reaction | same_element | not_adjacent | gauge_short | opener
    gauge: float               # outgoing member's gauge at the swap (before any reset)
    reaction: ReactionDef | None = None       # set only when the reaction fires
    pair_reaction: ReactionDef | None = None  # the pair's reaction even when it does not fire
    out_element: str = ""
    in_element: str = ""

    @property
    def fires(self) -> bool:
        return self.entry == "support_skill"


class CycleGauge:
    """One 环合值 per member, capped at 100 (brief §1.2).

    ``gauge_rule="game"`` (fitted on recorded battle 1): an adjacent swap fires the
    reaction only when the outgoing member's own gauge is full, and consumes it.
    ``gauge_rule="ideal"``: every adjacent swap fires and nothing is consumed.
    ``opening="full"``: every gauge starts at 100; ``"zero"``: 0 except members that
    start full (Zankou's passive, from ``team_rotation_data`` when available).
    Loops listed in ``FULL_GAUGE_LOOPS`` (1-based, (1, 3)) start with :meth:`refill_all`; the
    simulator calls it right after the boundary swap into that loop (the swap is judged on the
    outgoing member's built-up gauge), other loops keep the built-up gauges.
    """

    def __init__(self, gauge_rule: str = "game", opening: str = "full", team: Iterable[int] = (),
                 elements: Mapping[int, str] | None = None, *, rules: ReactionRules | None = None,
                 starts_full: Iterable[int] | None = None) -> None:
        if gauge_rule not in ("game", "ideal"):
            raise ValueError(f"unknown gauge_rule {gauge_rule!r}")
        if opening not in ("full", "zero"):
            raise ValueError(f"unknown opening {opening!r}")
        self.rules = rules or DEFAULT_RULES
        self.gauge_rule = gauge_rule
        self.opening = opening
        self.team = tuple(int(c) for c in team)
        self.elements = {int(c): normalize_element(e) for c, e in (elements or {}).items()}
        for cid in self.team:
            self.elements.setdefault(cid, self.rules.element(cid))
        self.cap = self.rules.gauge_cap
        full = set(self._starts_full(self.team) if starts_full is None else (int(c) for c in starts_full))
        self.starts_full = frozenset(full & set(self.team))
        opening_value = self.rules.model.get("zankou_opening_gauge", self.cap)
        self._g: dict[int, float] = {}
        for cid in self.team:
            if opening == "full":
                self._g[cid] = self.cap
            else:
                self._g[cid] = min(self.cap, float(opening_value)) if cid in self.starts_full else 0.0

    @staticmethod
    def _starts_full(team: Sequence[int]) -> set[int]:
        try:
            from src.services.team_rotation_data import CHARACTERS
            return {cid for cid in team if (CHARACTERS.get(cid) or {}).get("starts_full_gauge")}
        except Exception:
            return {ZANKOU_ID} & set(team)

    def value(self, character_id: int) -> float:
        return self._g.get(int(character_id), 0.0)

    def values(self) -> dict[int, float]:
        return dict(self._g)

    def gain(self, character_id: int, amount: float | None) -> float:
        """Add one simulated hit's ``heterochrome_add`` for the on-field member."""
        cid = int(character_id)
        self._g[cid] = min(self.cap, self._g.get(cid, 0.0) + max(0.0, float(amount or 0.0)))
        return self._g[cid]

    def set_value(self, character_id: int, value: float) -> None:
        self._g[int(character_id)] = max(0.0, min(self.cap, float(value)))

    def set_full(self, character_id: int) -> None:
        self.set_value(character_id, self.cap)

    def refill_all(self) -> None:
        """Every member's gauge to the cap (start of a loop listed in FULL_GAUGE_LOOPS)."""
        for cid in self.team:
            self._g[cid] = self.cap

    @staticmethod
    def refills_at(loop_number: int, full_gauge_loops: Iterable[int] = FULL_GAUGE_LOOPS) -> bool:
        """True when the 1-based loop starts with every gauge refilled (loop 1 follows the opening)."""
        return int(loop_number) in {int(n) for n in full_gauge_loops}

    def apply_step(self, character_id: int, step: Mapping[str, Any]) -> bool:
        """Gauge-setting skills (Zero / Raven E, rotation field ``gauge_set``)."""
        value = (step or {}).get("gauge_set")
        if value is None:
            return False
        self.set_value(character_id, float(value))
        return True

    def on_swap(self, out_character_id: int | None, in_character_id: int) -> SwapDecision:
        cin = int(in_character_id)
        ei = self.elements.get(cin) or self.rules.element(cin)
        if out_character_id is None:
            return SwapDecision("normal", "opener", 0.0, None, None, "", ei)
        cout = int(out_character_id)
        eo = self.elements.get(cout) or self.rules.element(cout)
        gauge = self.value(cout)
        if eo == ei:
            return SwapDecision("normal", "same_element", gauge, None, None, eo, ei)
        pair = self.rules.reaction_for(eo, ei)
        if pair is None:
            return SwapDecision("normal", "not_adjacent", gauge, None, None, eo, ei)
        if self.gauge_rule == "ideal" or gauge >= self.cap - _GAUGE_EPS:
            if self.gauge_rule == "game":
                self._g[cout] = 0.0
            return SwapDecision("support_skill", "reaction", gauge, pair, pair, eo, ei)
        return SwapDecision("normal", "gauge_short", gauge, None, pair, eo, ei)


# ── scheduler ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RowOrigin:
    reaction_index: int
    kind: str                 # reaction:浊燃 | reaction:黯星 | reaction:创生 | marker
    owner_character_id: int | None


@dataclass(frozen=True, slots=True)
class CycleWindow:
    index: int
    reaction_zh: str          # 覆纹 | 浸染
    code: str                 # hexed | stain
    start_us: int             # wall clock of the simulator axis
    end_us: int
    start_active_us: int
    end_active_us: int
    extra_ratio: float        # c (覆纹) or s (浸染)
    scope: tuple[str, ...]    # eligible damage attributes
    reaction_indices: tuple[int, ...]
    trigger_active_us: tuple[int, ...]
    trigger_event_ids: frozenset[str] = frozenset()

    def contains(self, time_us: int, *, active: bool = False) -> bool:
        if active:
            return self.start_active_us <= time_us <= self.end_active_us
        return self.start_us <= time_us <= self.end_us

    def reaction_at(self, active_us: int) -> int:
        current = self.reaction_indices[0]
        for idx, a in zip(self.reaction_indices, self.trigger_active_us):
            if a <= active_us:
                current = idx
        return current


@dataclass(frozen=True, slots=True)
class CycleReactionEvent:
    index: int
    time_us: int                      # wall clock of the simulator axis
    active_us: int
    reaction_zh: str
    code: str
    out_character_id: int | None
    in_character_id: int | None
    owner_character_id: int | None
    owner_basis: str                  # zankou_variant | incoming_provisional | final_effect | tie_incoming |
    #                                   incoming | hit_character | combo
    hits: int                         # synthetic engine rows (markers excluded)
    status: str                       # computed | effect_only
    effects: tuple[tuple[str, tuple], ...] = ()
    parents: tuple[int, ...] = ()
    visit_index: int | None = None


@dataclass(frozen=True, slots=True)
class OwnerQuery:
    reaction_index: int
    reaction_zh: str
    out_character_id: int | None
    in_character_id: int | None
    hit: Any                          # BattleAnalysisHit of the reaction's first synthetic row


@dataclass(frozen=True, slots=True)
class OwnerChoice:
    character_id: int
    basis: str                        # final_effect | tie_incoming | zankou_variant | incoming_provisional
    scores: tuple[tuple[int, float], ...] = ()


@dataclass(slots=True)
class _Trigger:
    index: int
    t_us: int
    a_us: int
    reaction: ReactionDef
    out_cid: int | None
    in_cid: int | None
    visit_index: int | None
    source_rows: tuple[dict, ...]


@dataclass(slots=True)
class _Planned:
    a_us: int
    index: int
    kind: str
    ge: str
    label: str
    attribute: str
    owner: int | None


@dataclass(slots=True)
class _Plan:
    planned: list[_Planned]
    owners: dict[int, tuple[int | None, str]]
    effects: dict[int, list[tuple[str, tuple]]]
    hits: dict[int, int]
    combos: list[dict]
    windows: list[dict]
    truncated: int


_FROM_ELEMENTS = object()   # trigger(): derive the reaction from the two members' elements


def _event_id(row: Mapping[str, Any]) -> str | None:
    seq = int(row.get("sequence_order") or 0)
    return f"{seq}:primary" if seq > 0 else None


class ReactionScheduler:
    """Turns fired reactions into synthetic rows, windows and explanation traces.

    Call :meth:`trigger` in time order (wall µs of the support skill's first damage hit).
    :meth:`rows` returns new hit dicts in the simulator's row shape (brief §2.1); the
    simulator numbers them in place, after which :meth:`event_origins`,
    :meth:`owner_queries`, :meth:`windows` and :meth:`ordinary_scorch_attributes` can
    resolve event ids.  Owners: pass ``"incoming"`` first, then the dict from
    :func:`choose_owners` (brief §1.3 two-pass rule).
    """

    def __init__(self, rules: ReactionRules | None, team: Iterable[int], build: Mapping[str, Any] | None = None,
                 to_active: Callable[[int], int] | None = None, to_wall: Callable[[int], int] | None = None, *,
                 elements: Mapping[int, str] | None = None, names: Mapping[int, str] | None = None,
                 passive_ids: Iterable[str] | None = None, kuhara_extra_plant: bool | None = None) -> None:
        self.rules = rules or DEFAULT_RULES
        self.team = tuple(int(c) for c in team)
        self.build = build or {}
        self._to_active = to_active or _identity
        self._to_wall = to_wall or _identity
        self.elements = {int(c): normalize_element(e) for c, e in (elements or {}).items()}
        for cid in self.team:
            self.elements.setdefault(cid, self.rules.element(cid))
        observed = {int(row.get("character_id") or 0): str(row.get("observed_name") or "")
                    for row in _build_rows(self.build)}
        self.names = {cid: (names or {}).get(cid) or observed.get(cid) or str(cid) for cid in self.team}
        self.passive_ids = frozenset(passive_ids) if passive_ids is not None else team_passive_ids(self.build)
        self.zankou_variant = ZANKOU_ID in self.team and zankou_variant_active(self.build)
        kuhara_on = KUHARA_PASSIVE_ID in self.passive_ids
        self.kuhara_extra_plant = kuhara_on if kuhara_extra_plant is None else bool(kuhara_extra_plant)
        self.plant_limit = int(self.rules.model["kuhara_plant_limit"] if kuhara_on
                               else self.rules.model["blossom_plant_limit"])
        self.hexed_extra_ratio = hexed_extra_ratio(self.rules, self.passive_ids)
        self.stain_duration_s, self.stain_extra_ratio = stain_parameters(self.rules, self.passive_ids)
        self.remora_duration_s = (self.rules.hathor_remora_duration_s if HATHOR_PASSIVE_ID in self.passive_ids
                                  else self.rules.remora_duration_s)
        self._triggers: list[_Trigger] = []
        self._owner_source: Any = "incoming"
        self._horizon_us: int | None = None
        self._dot_ticks_us: tuple[int, ...] | None = None     # wall µs of non-Scorch DoT ticks (None = unknown)
        self._last_rows: list[tuple[dict, RowOrigin]] = []

    # recording ---------------------------------------------------------------
    def trigger(self, t_us: int, out_character_id: int | None, in_character_id: int | None,
                reaction: Any = _FROM_ELEMENTS, *, visit_index: int | None = None,
                source_rows: Iterable[dict] = ()) -> int | None:
        """Record one fired reaction; returns its reaction index (None when nothing fires).

        ``reaction`` is a :class:`ReactionDef` or its Chinese name (pass ``SwapDecision.reaction``,
        which is None unless the swap fires); omit it to derive the pair from the elements.
        ``source_rows`` are the support-skill hit dicts of this entry (the same objects
        the simulator numbers later); they are excluded from 覆纹 / 浸染 increments.
        """
        if reaction is _FROM_ELEMENTS:
            reaction = None
            if out_character_id is not None and in_character_id is not None:
                reaction = self.rules.reaction_for(self.elements.get(int(out_character_id), ""),
                                                   self.elements.get(int(in_character_id), ""))
        elif isinstance(reaction, str):
            reaction = self.rules.by_zh(reaction)
        if reaction is None:
            return None
        if self._triggers and int(t_us) < self._triggers[-1].t_us:
            raise ValueError("cycle reactions must be triggered in time order")
        index = len(self._triggers)
        a_us = int(self._to_active(int(t_us)))       # refreshed on every plan (stops may be added later)
        self._triggers.append(_Trigger(index, int(t_us), a_us, reaction,
                                       None if out_character_id is None else int(out_character_id),
                                       None if in_character_id is None else int(in_character_id),
                                       visit_index, tuple(source_rows)))
        return index

    def set_horizon(self, end_us: int | None) -> None:
        """Drop synthetic rows after this wall time (None keeps every scheduled row)."""
        self._horizon_us = None if end_us is None else int(end_us)

    def set_dot_ticks(self, times_us: Iterable[int] | None) -> None:
        """Wall times of the non-Scorch damage-over-time ticks on the axis (Zankou erosion / venom,
        Lacrimosa nightmare), converted to the active clock when planning.

        With Zankou's variant they drive the Scorch (GA_Zankou_Passive1, engine
        ``_ScorchState.apply_dot_hit``): a trigger stores a dormant Scorch that the next DoT tick
        activates, and every DoT tick on a Scorched target refreshes its 15 s.  ``None`` (never set)
        keeps the earlier model: activation at the trigger, expiry extended by triggers only."""
        self._dot_ticks_us = None if times_us is None else tuple(sorted(int(t) for t in times_us))

    @property
    def triggers(self) -> tuple[tuple[int, int, str, int | None, int | None], ...]:
        return tuple((t.index, t.t_us, t.reaction.zh, t.out_cid, t.in_cid) for t in self._triggers)

    @property
    def dot_driven_scorch(self) -> bool:
        """Zankou's Scorch is activated and refreshed by the DoT ticks given to :meth:`set_dot_ticks`."""
        return self.zankou_variant and self._dot_ticks_us is not None

    def needs_owner(self, index: int) -> bool:
        trig = self._triggers[index]
        return trig.reaction.code in OWNER_RULE_CODES and not (trig.reaction.code == "scorch" and self.zankou_variant)

    # owners --------------------------------------------------------------------
    def _owner_map(self, provisional_owner) -> dict[int, OwnerChoice]:
        owners: dict[int, OwnerChoice] = {}
        explicit = provisional_owner if isinstance(provisional_owner, Mapping) else {}
        side = provisional_owner if isinstance(provisional_owner, str) else "incoming"
        for trig in self._triggers:
            code = trig.reaction.code
            if code == "scorch" and self.zankou_variant:
                owners[trig.index] = OwnerChoice(ZANKOU_ID, "zankou_variant")
            elif code in OWNER_RULE_CODES:
                given = explicit.get(trig.index)
                if isinstance(given, OwnerChoice):
                    owners[trig.index] = given
                elif given is not None:
                    owners[trig.index] = OwnerChoice(int(given), "final_effect")
                else:
                    cid = trig.out_cid if side == "outgoing" and trig.out_cid is not None else trig.in_cid
                    owners[trig.index] = OwnerChoice(int(cid), "incoming_provisional")
            elif code == "remora":
                owners[trig.index] = OwnerChoice(int(trig.in_cid or 0), "incoming")
        return owners

    # planning --------------------------------------------------------------------
    def _plan(self) -> _Plan:
        """Resolve every schedule from the recorded triggers (cheap; recomputed on each call)."""
        rules = self.rules
        for trig in self._triggers:
            trig.a_us = int(self._to_active(trig.t_us))
        owners = self._owner_map(self._owner_source)
        effects: dict[int, list[tuple[str, tuple]]] = {t.index: [] for t in self._triggers}
        planned: list[_Planned] = []
        by_code: dict[str, list[_Trigger]] = {}
        for trig in self._triggers:
            by_code.setdefault(trig.reaction.code, []).append(trig)
        us = lambda seconds: int(round(seconds * 1_000_000))  # noqa: E731

        # 浊燃: NeverReset tick phase; a re-trigger only extends expiry to t + 15 s.  Zankou's variant with the
        # DoT ticks known (set_dot_ticks): the trigger's Scorch stays dormant until the next non-Scorch DoT tick
        # (first Scorch tick ZANKOU_SCORCH_ACTIVATION_S later), and every DoT tick before expiry refreshes it
        # to that tick + 15 s (GA_Zankou_Passive1; engine _ScorchState.prepare_application / apply_dot_hit).
        scorch_def = rules.by_zh("浊燃")
        scorch_ge = (scorch_def.damage_effect_id if scorch_def else None) or "Buff_Reaction_5_new"
        zankou_ge = f"{scorch_ge}_{ZANKOU_ID}"
        tick_us, scorch_dur = us(rules.scorch_tick_s), us(rules.scorch_duration_s)
        dot_driven = self.dot_driven_scorch
        events = [(trig.a_us, 0, trig) for trig in by_code.get("scorch", ())]
        if dot_driven:
            events += [(int(self._to_active(t)), 1, None) for t in self._dot_ticks_us]
        events.sort(key=lambda e: (e[0], e[1]))           # a trigger before a DoT tick at the same instant
        sequences: list[dict] = []
        for a_us, kind, trig in events:
            seq = sequences[-1] if sequences else None
            if kind == 0:
                if seq is not None and seq["expiry"] >= a_us:
                    seq["expiry"] = max(seq["expiry"], a_us + scorch_dur)
                    seq["triggers"].append(trig)
                    effects[trig.index].append(("scorch_refresh", (seq["triggers"][0].index,)))
                else:
                    sequences.append({"start": a_us, "first": None if dot_driven else a_us + tick_us,
                                      "activated_at": None, "expiry": a_us + scorch_dur, "triggers": [trig]})
            elif seq is not None and seq["start"] <= a_us < seq["expiry"]:
                seq["expiry"] = max(seq["expiry"], a_us + scorch_dur)
                if seq["first"] is None:
                    seq["first"], seq["activated_at"] = a_us + us(ZANKOU_SCORCH_ACTIVATION_S), a_us
        scorch_spans = []
        dormant_triggers: set[int] = set()
        for seq in sequences:
            if dot_driven:
                if seq["first"] is None:         # no DoT tick before it expired: stored, never activated
                    dormant_triggers.update(t.index for t in seq["triggers"])
                    scorch_spans.append((seq["start"], seq["expiry"], [t.index for t in seq["triggers"]]))
                    continue
                before = [t for t in seq["triggers"] if t.a_us <= seq["activated_at"]]
                lead = before[-1]                # earlier ones were refreshed before any DoT tick came
                dormant_triggers.update(t.index for t in before[:-1])
                effects[lead.index].append(("scorch_activated_after_s",
                                            (round((seq["first"] - lead.a_us) / 1e6, 2),)))
            k = 0
            while seq["first"] + k * tick_us <= seq["expiry"]:
                tick = seq["first"] + k * tick_us
                source = seq["triggers"][0]
                for trig in seq["triggers"]:
                    if trig.a_us < tick:
                        source = trig
                owner = owners[source.index].character_id
                if self.zankou_variant:
                    ge, attr = zankou_ge, self.elements.get(ZANKOU_ID) or "incantation"
                else:
                    ge, attr = scorch_ge, self.elements.get(owner, "")
                planned.append(_Planned(tick, source.index, "reaction:浊燃", ge, "浊燃", attr, owner))
                k += 1
            scorch_spans.append((seq["start"], seq["expiry"], [t.index for t in seq["triggers"]]))
        if self.zankou_variant:
            for trig in by_code.get("scorch", ()):
                effects[trig.index].append(("scorch_zankou_variant", ()))

        # 黯星: settle at t + 5 s; same owner refreshes, different owners all settle together
        nova_def = rules.by_zh("黯星")
        nova_ge = (nova_def.damage_effect_id if nova_def else None) or "Buff_Reaction_4_new"
        nova_delay = us(rules.nova_delay_s)
        pending: list[list] = []      # [trigger, owner, settle_a]
        nova_spans = []

        def settle(item):
            trig, owner, settle_a = item
            planned.append(_Planned(settle_a, trig.index, "reaction:黯星", nova_ge, "黯星", "psychically", owner))
            effects[trig.index].append(("settle_after_s", (round((settle_a - trig.a_us) / 1e6, 2),)))
            nova_spans.append((trig.a_us, settle_a, trig.index))

        for trig in by_code.get("nova", ()):
            owner = owners[trig.index].character_id
            for item in [p for p in pending if p[2] <= trig.a_us]:
                settle(item)
            pending = [p for p in pending if p[2] > trig.a_us]
            for item in [p for p in pending if p[1] == owner]:
                effects[item[0].index].append(("nova_replaced", (trig.index,)))
                nova_spans.append((item[0].a_us, trig.a_us, item[0].index))
            pending = [p for p in pending if p[1] != owner]
            new_settle = trig.a_us + nova_delay
            for item in pending:
                if item[2] != new_settle:
                    effects[item[0].index].append(("nova_retimed", (trig.index,)))
                    item[2] = new_settle
            pending.append([trig, owner, new_settle])
        for item in pending:
            settle(item)

        # 创生: one plant (two with Kuhara's passive) of 5 flowers at +2…+10 s; capped plants
        blossom_def = rules.by_zh("创生")
        blossom_ge = (blossom_def.damage_effect_id if blossom_def else None) or "GE_ActorReaction_1_Damage"
        flowers_n = int(rules.model["blossom_flowers"])
        interval = us(float(rules.model["blossom_interval_s"]))
        plants: list[dict] = []
        for trig in by_code.get("blossom", ()):
            count = 2 if self.kuhara_extra_plant else 1
            for _ in range(count):
                alive = [p for p in plants if any(f > trig.a_us for f in p["flowers"])]
                if len(alive) >= self.plant_limit:
                    oldest = alive[0]
                    dropped = [f for f in oldest["flowers"] if f > trig.a_us]
                    oldest["flowers"] = [f for f in oldest["flowers"] if f <= trig.a_us]
                    effects[oldest["index"]].append(("blossom_flowers_dropped", (len(dropped),)))
                plants.append({"index": trig.index,
                               "flowers": [trig.a_us + k * interval for k in range(1, flowers_n + 1)]})
            effects[trig.index].append(("blossom_plants", (count, flowers_n)))
        flower_times: list[tuple[int, int]] = []
        for plant in plants:
            owner = owners[plant["index"]].character_id
            for f in plant["flowers"]:
                planned.append(_Planned(f, plant["index"], "reaction:创生", blossom_ge, "创生",
                                        self.elements.get(owner, ""), owner))
                flower_times.append((f, plant["index"]))

        # 延滞: marker at t + 5 s (suit rule shifts it back), 5 s state (12 s with Hathor)
        remora_spans = []
        for trig in by_code.get("remora", ()):
            planned.append(_Planned(trig.a_us + us(REMORA_MARKER_OFFSET_S), trig.index, "marker",
                                    REMORA_MARKER_GE, "延滞", "", owners[trig.index].character_id))
            remora_spans.append((trig.a_us, trig.a_us + us(self.remora_duration_s), trig.index))
            effects[trig.index].append(("remora_duration_s", (self.remora_duration_s,)))

        # 覆纹 / 浸染 windows: [t, t + D] on the active clock, extended by re-triggers
        windows: list[dict] = []
        for code, zh, duration, ratio, scope in (
                ("hexed", "覆纹", rules.hexed_duration_s, self.hexed_extra_ratio,
                 tuple((rules.by_zh("覆纹") or ReactionDef("", "覆纹", "hexed", ("nature", "incantation"), None)).elements)),
                ("stain", "浸染", self.stain_duration_s, self.stain_extra_ratio, STAIN_SCOPE)):
            current = None
            for trig in by_code.get(code, ()):
                if current is not None and current["end"] >= trig.a_us:
                    current["end"] = max(current["end"], trig.a_us + us(duration))
                    current["triggers"].append(trig)
                else:
                    current = {"code": code, "zh": zh, "start": trig.a_us, "end": trig.a_us + us(duration),
                               "ratio": ratio, "scope": scope, "triggers": [trig]}
                    windows.append(current)
                effects[trig.index].append(("window_s", (duration,)))
                effects[trig.index].append((f"{code}_ratio", (ratio,)))

        # combinations: 盈蓄 (flower lands on a 延滞 target), 失谐 (浊燃 and 黯星 overlap)
        combos: list[dict] = []
        charge_hits: dict[tuple[int, int], list[int]] = {}
        for f, b_index in sorted(flower_times):
            for r_start, r_end, r_index in remora_spans:
                if r_start <= f <= r_end:
                    charge_hits.setdefault((b_index, r_index), []).append(f)
                    break
        last_energy_at = None
        energy_by_pair: dict[tuple[int, int], int] = {}
        for f, pair in sorted((f, pair) for pair, fs in charge_hits.items() for f in fs):
            if last_energy_at is None or f - last_energy_at >= us(rules.charge_cd_s):
                energy_by_pair[pair] = energy_by_pair.get(pair, 0) + 1
                last_energy_at = f
        for pair, fs in charge_hits.items():
            combos.append({"zh": "盈蓄", "code": "charge", "a_us": min(fs), "parents": pair,
                           "effects": [("charge_energy", (rules.charge_energy * energy_by_pair.get(pair, 0), len(fs)))]})
        seen_discord = set()
        for s_start, s_end, s_indices in scorch_spans:
            for n_start, n_end, n_index in nova_spans:
                if s_start <= n_start <= s_end:
                    at = n_start                       # 黯星 lands on a target that already has 浊燃
                elif n_start < s_start < n_end:
                    at = s_start                       # 浊燃 lands while 黯星 is pending
                else:
                    continue
                s_index = s_indices[0]
                for idx in s_indices:
                    if self._triggers[idx].a_us <= at:
                        s_index = idx
                key = (s_index, n_index)
                if key in seen_discord:
                    continue
                seen_discord.add(key)
                combos.append({"zh": "失谐", "code": "discord", "a_us": at, "parents": key,
                               "effects": [("discord_topple_reduction",
                                            (float(rules.model["discord_topple_reduction"]),))]})
        combos.sort(key=lambda c: (c["a_us"], c["parents"]))

        truncated = 0
        if self._horizon_us is not None:
            kept, dropped_by_index = [], {}
            for item in planned:
                if self._to_wall(item.a_us) > self._horizon_us:
                    dropped_by_index[item.index] = dropped_by_index.get(item.index, 0) + 1
                else:
                    kept.append(item)
            for index, count in dropped_by_index.items():
                effects[index].append(("truncated_at_end", (count,)))
            truncated = sum(dropped_by_index.values())
            planned = kept
        planned.sort(key=lambda p: (p.a_us, p.index))
        hits: dict[int, int] = {}
        for item in planned:
            if item.kind != "marker":
                hits[item.index] = hits.get(item.index, 0) + 1
        for trig in self._triggers:
            if trig.reaction.code == "scorch":
                effects[trig.index].append(("scorch_ticks", (hits.get(trig.index, 0),)))
                if trig.index in dormant_triggers:
                    effects[trig.index].append(("scorch_dormant", ()))
        return _Plan(planned, {k: (v.character_id, v.basis) for k, v in owners.items()}, effects, hits,
                     combos, windows, truncated)

    # outputs ---------------------------------------------------------------------
    def rows_with_origin(self, provisional_owner: Any = "incoming", *, include_markers: bool = True
                         ) -> list[tuple[dict, RowOrigin]]:
        self._owner_source = dict(provisional_owner) if isinstance(provisional_owner, Mapping) else provisional_owner
        plan = self._plan()
        out: list[tuple[dict, RowOrigin]] = []
        for item in plan.planned:
            if item.kind == "marker" and not include_markers:
                continue
            owner = item.owner
            row = {
                "sequence_text": "0", "sequence_order": 0, "relative_time_us": int(self._to_wall(item.a_us)),
                "character_id": owner, "character_name": self.names.get(owner, str(owner)), "character_known": 1,
                "direction": "outgoing", "damage": 1.0, "follow_up_damage": 0, "ability_name": None,
                "gameplay_effect_name": item.ge, "damage_name": item.label, "damage_component": item.label,
                "attack_type": item.label, "damage_attribute": item.attribute, "target_id": "dummy",
                "target_name": "dummy", "follow_up_labels": [],
            }
            out.append((row, RowOrigin(item.index, item.kind, owner)))
        self._last_rows = out
        return out

    def rows(self, provisional_owner: Any = "incoming", *, include_markers: bool = True) -> list[dict]:
        """Synthetic hit dicts (brief §2.1).  ``provisional_owner``: ``"incoming"`` or a
        ``{reaction_index: OwnerChoice | character_id}`` mapping from :func:`choose_owners`."""
        return [row for row, _origin in self.rows_with_origin(provisional_owner, include_markers=include_markers)]

    def event_origins(self) -> dict[str, RowOrigin]:
        """``event_id -> RowOrigin`` for the last rows, once the simulator has numbered them."""
        out = {}
        for row, origin in self._last_rows:
            event_id = _event_id(row)
            if event_id:
                out[event_id] = origin
        return out

    def ordinary_scorch_attributes(self) -> dict[str, str]:
        """Event ids of ordinary (non-Zankou) 浊燃 rows → owner element, for the evidence patch."""
        if self.zankou_variant:
            return {}
        out = {}
        for row, origin in self._last_rows:
            event_id = _event_id(row)
            if event_id and origin.kind == "reaction:浊燃" and row.get("damage_attribute"):
                out[event_id] = str(row["damage_attribute"])
        return out

    def owner_queries(self, analysis: Any) -> tuple[OwnerQuery, ...]:
        """One query per owner-rule reaction, using its first synthetic row in ``analysis.hits``."""
        hits = {h.event_id: h for h in getattr(analysis, "hits", ())}
        first: dict[int, Any] = {}
        for row, origin in self._last_rows:
            if origin.kind == "marker" or origin.reaction_index in first:
                continue
            if not self.needs_owner(origin.reaction_index):
                continue
            hit = hits.get(_event_id(row) or "")
            if hit is not None:
                first[origin.reaction_index] = hit
        out = []
        for index, hit in sorted(first.items()):
            trig = self._triggers[index]
            out.append(OwnerQuery(index, trig.reaction.zh, trig.out_cid, trig.in_cid, hit))
        return tuple(out)

    def trigger_event_ids(self, codes: Iterable[str] | None = None) -> frozenset[str]:
        wanted = None if codes is None else set(codes)
        ids = set()
        for trig in self._triggers:
            if wanted is not None and trig.reaction.code not in wanted and trig.reaction.zh not in wanted:
                continue
            for row in trig.source_rows:
                event_id = _event_id(row)
                if event_id:
                    ids.add(event_id)
        return frozenset(ids)

    def windows(self, kinds: Iterable[str] = ("覆纹", "浸染")) -> tuple[CycleWindow, ...]:
        wanted = set(kinds)
        out = []
        for raw in self._plan().windows:
            if raw["zh"] not in wanted and raw["code"] not in wanted:
                continue
            ids = set()
            for trig in raw["triggers"]:
                ids.update(e for e in (_event_id(r) for r in trig.source_rows) if e)
            out.append(CycleWindow(
                index=len(out), reaction_zh=raw["zh"], code=raw["code"],
                start_us=int(self._to_wall(raw["start"])), end_us=int(self._to_wall(raw["end"])),
                start_active_us=raw["start"], end_active_us=raw["end"], extra_ratio=float(raw["ratio"]),
                scope=tuple(raw["scope"]), reaction_indices=tuple(t.index for t in raw["triggers"]),
                trigger_active_us=tuple(t.a_us for t in raw["triggers"]), trigger_event_ids=frozenset(ids)))
        return tuple(out)

    def traces(self) -> tuple[CycleReactionEvent, ...]:
        """Base reactions (indices = trigger order) followed by 盈蓄 / 失谐 combinations."""
        plan = self._plan()
        effects = {k: list(v) for k, v in plan.effects.items()}
        combo_events = []
        base = len(self._triggers)
        for offset, combo in enumerate(plan.combos):
            index = base + offset
            parents = tuple(combo["parents"])
            for parent in parents:
                effects[parent].append((combo["code"], (index,)))
            later = max(parents, key=lambda i: self._triggers[i].a_us)
            trig = self._triggers[later]
            combo_events.append(CycleReactionEvent(
                index=index, time_us=int(self._to_wall(combo["a_us"])), active_us=int(combo["a_us"]),
                reaction_zh=combo["zh"], code=combo["code"], out_character_id=trig.out_cid,
                in_character_id=trig.in_cid, owner_character_id=None, owner_basis="combo", hits=0,
                status="effect_only", effects=tuple(combo["effects"]), parents=parents,
                visit_index=trig.visit_index))
        events = []
        for trig in self._triggers:
            code = trig.reaction.code
            owner, basis = plan.owners.get(trig.index, (None, "hit_character"))
            hits = plan.hits.get(trig.index, 0)
            if code in ("hexed", "stain"):
                status = "computed"
            elif code in OWNER_RULE_CODES:
                status = "computed" if hits else "effect_only"
            else:
                status = "effect_only"
            events.append(CycleReactionEvent(
                index=trig.index, time_us=trig.t_us, active_us=trig.a_us, reaction_zh=trig.reaction.zh,
                code=code, out_character_id=trig.out_cid, in_character_id=trig.in_cid,
                owner_character_id=owner, owner_basis=basis, hits=hits, status=status,
                effects=tuple(effects.get(trig.index, ())), visit_index=trig.visit_index))
        return tuple(events) + tuple(combo_events)

    def limits(self) -> tuple[tuple[str, tuple], ...]:
        """Assumption / limit codes for the reactions that occurred (brief §1.5, §6)."""
        plan = self._plan()
        codes = {t.reaction.code for t in self._triggers} | {c["code"] for c in plan.combos}
        out: list[tuple[str, tuple]] = []
        if "scorch" in codes and self.dot_driven_scorch:
            # the engine stacks the layers from the DoT ticks itself; the activation rule is a model note
            out += [("scorch_zankou_dot_driven", ()), ("scorch_crit_low", ())]
        elif "scorch" in codes and self.zankou_variant:
            out += [("scorch_zankou_one_layer", ()), ("scorch_zankou_activation_at_trigger", ()),
                    ("scorch_crit_low", ())]
        if "hexed" in codes:
            out.append(("hexed_immediate", ()))
            if LINKO_PASSIVE_ID not in self.passive_ids:
                out.append(("hexed_without_linko_unconfirmed", ()))
        if "stain" in codes:
            out.append(("stain_scope", STAIN_SCOPE))
        if "nova" in codes:
            out.append(("nova_stacking_unconfirmed", ()))
        if "blossom" in codes:
            out.append(("blossom_schedule_inferred", ()))
        if "charge" in codes:
            out.append(("charge_energy_not_counted", ()))
        if "discord" in codes:
            out.append(("discord_topple_not_counted", ()))
        if plan.truncated:
            out.append(("reaction_rows_after_end", (plan.truncated,)))
        for code in sorted(codes):
            for cid, limit in _EXCLUSIONS.get(code, ()):
                if cid in self.team and (limit, (cid,)) not in out:
                    out.append((limit, (cid,)))
        return tuple(out)


# ── owner choice (brief §1.3) ─────────────────────────────────────────────

def _baseline_map(analysis: Any, baselines: Any) -> dict[int, Any]:
    if baselines is None:
        baselines = getattr(analysis, "baselines", ()) or ()
    if isinstance(baselines, Mapping):
        return {int(k): v for k, v in baselines.items()}
    return {int(b.character_id): b for b in baselines}


def _frozen_values(baseline: Any) -> dict[str, float]:
    if baseline is None:
        return {}
    if isinstance(baseline, Mapping):
        return {str(k): float(v) for k, v in baseline.items()}
    return {row.property_id: float(row.value) for row in getattr(baseline, "stats", ())}


class _StatsAtHit:
    """Baseline stats of a member plus buffs projected at a hit (the replay's own path)."""

    def __init__(self, analysis: Any, baselines: Any = None) -> None:
        self.analysis = analysis
        self.baselines = _baseline_map(analysis, baselines)
        self._index = None
        self._cache: dict[tuple[str, int], dict[str, float]] = {}

    def _intervals(self):
        if self._index is None:
            intervals = tuple(getattr(self.analysis, "buff_intervals", ()) or ())
            try:
                from src.services.battle_buff_interval_index import BattleBuffIntervalIndex
                self._index = BattleBuffIntervalIndex(intervals)
            except Exception:  # pragma: no cover
                self._index = intervals
        return self._index

    def __call__(self, hit: Any, character_id: int | None = None) -> dict[str, float]:
        cid = int(hit.character_id if character_id is None else character_id)
        key = (str(getattr(hit, "event_id", id(hit))), cid)
        if key in self._cache:
            return self._cache[key]
        values = _frozen_values(self.baselines.get(cid))
        try:
            from src.services.battle_buff_attribute_projection_service import BattleBuffAttributeProjectionService
            probe = hit if hit.character_id == cid else replace(hit, character_id=cid)
            projection = BattleBuffAttributeProjectionService.project_hit(probe, self._intervals())
            values = BattleBuffAttributeProjectionService.apply_additive(values, projection)
        except Exception:
            pass
        self._cache[key] = values
        return values


def hit_stats(analysis: Any, hit: Any, character_id: int | None = None, baselines: Any = None) -> dict[str, float]:
    return _StatsAtHit(analysis, baselines)(hit, character_id)


def make_mag_lookup(analysis: Any, baselines: Any = None) -> Callable[[Any], float]:
    """``hit -> MagBase`` of the hit's own character at hit time (cached per event)."""
    stats = _StatsAtHit(analysis, baselines)

    def mag_of(hit: Any) -> float:
        if hit.character_id is None:
            return 0.0
        return float(stats(hit).get("MagBase", 0.0) or 0.0)

    return mag_of


def _owner_score(rules: ReactionRules, code: str, level: float, stats: Mapping[str, float]) -> float:
    curve = {"scorch": "Buff_Reaction_5_new", "nova": "Buff_Reaction_4_new",
             "blossom": "GE_ActorReaction_1_Damage"}[code]
    base = rules.level_value(curve, level) or 0.0
    score = base * ring_strength_multiplier(float(stats.get("MagBase", 0.0) or 0.0))
    if code == "scorch":
        score *= 1.0 + 0.5 * float(stats.get("CritDamageBase", 0.5) or 0.0)
    return score


def choose_owners(analysis: Any, baselines: Any = None, triggers: Any = (), *, rules: ReactionRules | None = None,
                  stats_of: Callable[[Any, int], Mapping[str, float]] | None = None) -> dict[int, OwnerChoice]:
    """Reaction owner = participant with the higher final effect (brief §1.3).

    Score = base(level) × (1 + Mag/600) × (1 + 0.5·CritDamageBase for 浊燃); a tie keeps
    the incoming member.  ``triggers`` is a sequence of :class:`OwnerQuery` or the
    :class:`ReactionScheduler` itself.  ``stats_of(hit, character_id)`` defaults to the
    replay's own baseline + projected-buff values.
    """
    rules = rules or getattr(triggers, "rules", None) or DEFAULT_RULES
    queries = triggers.owner_queries(analysis) if hasattr(triggers, "owner_queries") else tuple(triggers or ())
    base_map = _baseline_map(analysis, baselines)
    stats_of = stats_of or _StatsAtHit(analysis, baselines)
    out: dict[int, OwnerChoice] = {}
    for query in queries:
        code = CODE_BY_ZH.get(query.reaction_zh, "")
        if code not in OWNER_RULE_CODES:
            continue
        incoming = query.in_character_id
        candidates = [c for c in (incoming, query.out_character_id) if c is not None]
        if not candidates:
            continue
        scores = []
        for cid in candidates:
            baseline = base_map.get(int(cid))
            level = float(getattr(baseline, "character_level", 80.0) or 80.0) if baseline is not None else 80.0
            scores.append((int(cid), _owner_score(rules, code, level, stats_of(query.hit, int(cid)))))
        best = max(score for _cid, score in scores)
        winners = [cid for cid, score in scores if abs(score - best) <= 1e-9 * max(1.0, abs(best))]
        if incoming is not None and int(incoming) in winners:
            winner, basis = int(incoming), ("tie_incoming" if len(winners) > 1 else "final_effect")
        else:
            winner, basis = winners[0], "final_effect"
        out[query.reaction_index] = OwnerChoice(winner, basis, tuple(scores))
    return out


# ── post-replay formulas (brief §2.2) ─────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CycleIncrement:
    event_id: str
    character_id: int | None
    reaction_zh: str            # 覆纹 | 浸染
    window_index: int
    reaction_index: int
    base_damage: float          # the hit's expected damage
    ring_strength: float        # M of the hit's own character
    multiplier: float           # K
    factor: float               # (1 + c)·K − 1
    increment: float            # base_damage × factor (not floored: expected value)


_REACTION_TEXT = frozenset(("创生", "创生花", "覆纹", "覆纹追加攻击", "延滞", "黯星", "浊燃", "浸染", "盈蓄", "失谐",
                            "环合伤害"))


def is_reaction_or_topple(hit: Any) -> bool:
    """Reaction rows and topple never receive 覆纹 / 浸染 (engine lane, with a fallback)."""
    try:
        from src.services.battle_damage_composition_service import classify_battle_hit_channel
        channel = classify_battle_hit_channel(hit)[0]
        if channel.startswith("reaction_") or channel in ("other_topple", "special_daffodill_extra_topple"):
            return True
    except Exception:  # pragma: no cover
        pass
    if getattr(hit, "classification", "") in ("reaction", "weave", "topple"):
        return True
    effect = str(getattr(hit, "gameplay_effect_id", "") or "").casefold()
    if effect.startswith(("buff_reaction_", "ge_actorreaction_")) or effect == "buff_tenacity_damage":
        return True
    labels = {str(getattr(hit, name, "") or "").strip() for name in ("damage_name", "damage_component", "attack_type")}
    return bool(labels & _REACTION_TEXT)


def _apply_window_formula(code: str, pairs: Iterable[tuple[Any, Any]], windows: Iterable[CycleWindow],
                          mag_of: Callable[[Any], float], *, excluded_event_ids: Iterable[str],
                          to_active: Callable[[int], int] | None, extra_ratio: float | None,
                          scope: Sequence[str] | None) -> tuple[CycleIncrement, ...]:
    selected = [w for w in windows if w.code == code]
    if not selected:
        return ()
    excluded = set(excluded_event_ids or ())
    out = []
    for hit, replay in pairs:
        if replay is None or getattr(hit, "direction", "outgoing") != "outgoing":
            continue
        expected = getattr(replay, "expected_damage", None)
        if expected is None or float(expected) <= 0.0:
            continue
        if hit.event_id in excluded:
            continue
        attribute = str(getattr(replay, "formula_damage_attribute", "") or getattr(hit, "damage_attribute", "")
                        or "").casefold()
        time_us = int(hit.relative_time_us)
        active_us = int(to_active(time_us)) if to_active is not None else None
        window = next((w for w in selected
                       if (w.contains(active_us, active=True) if active_us is not None else w.contains(time_us))),
                      None)
        if window is None or hit.event_id in window.trigger_event_ids:
            continue
        if attribute not in tuple(scope if scope is not None else window.scope):
            continue
        if is_reaction_or_topple(hit):
            continue
        mag = max(0.0, float(mag_of(hit) or 0.0))
        ratio = window.extra_ratio if extra_ratio is None else float(extra_ratio)
        k = weave_strength_multiplier(mag)
        factor = (1.0 + ratio) * k - 1.0
        position = active_us if active_us is not None else window.start_active_us + max(0, time_us - window.start_us)
        out.append(CycleIncrement(hit.event_id, hit.character_id, window.reaction_zh, window.index,
                                  window.reaction_at(position), float(expected), mag, k, factor,
                                  float(expected) * factor))
    return tuple(out)


def apply_hexed(pairs: Iterable[tuple[Any, Any]], windows: Iterable[CycleWindow], mag_of: Callable[[Any], float], *,
                excluded_event_ids: Iterable[str] = (), to_active: Callable[[int], int] | None = None,
                extra_ratio: float | None = None) -> tuple[CycleIncrement, ...]:
    """覆纹: every replayed nature / incantation hit inside a window gets E × ((1 + c)·K − 1).

    ``pairs`` are ``(analysis hit, replay result)``; reaction rows, topple and the window's
    own triggering support-skill hits are skipped.  ``c`` comes from the window (0.20, or
    0.33 with Linko's passive) unless ``extra_ratio`` overrides it.  Increments are credited
    to the hit's character and are not floored.
    """
    return _apply_window_formula("hexed", pairs, windows, mag_of, excluded_event_ids=excluded_event_ids,
                                 to_active=to_active, extra_ratio=extra_ratio, scope=None)


def apply_stain(pairs: Iterable[tuple[Any, Any]], windows: Iterable[CycleWindow], mag_of: Callable[[Any], float], *,
                excluded_event_ids: Iterable[str] = (), to_active: Callable[[int], int] | None = None,
                extra_ratio: float | None = None, scope: Sequence[str] = STAIN_SCOPE) -> tuple[CycleIncrement, ...]:
    """浸染: hits in scope (psyche / lakshana by default) inside a window get E × ((1 + s)·K − 1)."""
    return _apply_window_formula("stain", pairs, windows, mag_of, excluded_event_ids=excluded_event_ids,
                                 to_active=to_active, extra_ratio=extra_ratio, scope=tuple(scope))


def increments_by_character(increments: Iterable[CycleIncrement]) -> dict[int, float]:
    out: dict[int, float] = {}
    for inc in increments:
        if inc.character_id is not None:
            out[int(inc.character_id)] = out.get(int(inc.character_id), 0.0) + inc.increment
    return out


def patch_ordinary_scorch_evidence(evidence: Iterable[Any], attributes_by_event: Mapping[str, str]) -> tuple:
    """Give ordinary 浊燃 evidence the owner's element (brief §2.1 evidence patch)."""
    if not attributes_by_event:
        return tuple(evidence)
    return tuple(replace(e, damage_attribute=attributes_by_event[e.event_id])
                 if getattr(e, "event_id", None) in attributes_by_event else e for e in evidence)
