# 队伍模拟（演示版）：按已审核的角色循环排出出场顺序、援护技与环合反应，在合成动作轴上复用战报引擎估算伤害与 DPS。
"""Team simulation (preview).

Each member is built from the static graduation template (profile + equipment + fork), with the
user's awakening / fork / refinement / cartridge-set choices applied on top.  Every member acts by
its approved rotation (``team_rotation_data``, strict ``(ability_id, selector)`` animation match,
no fallback).  The team runs ``loops`` full passes (default 3, ``DEFAULT_LOOPS``).  The visit order is
chosen by the planner (``order_mode="plan"``, the page default: orders with the most adjacent-element
swaps, the transformation damage dealer first or last, ranked by reactions and team-buff cover of its
form window, the best few compared by simulated DPS), automatically (``"auto"``: most adjacent pairs,
the member with the longest field time last) or kept in slot order.

Cycle gauge: every member's gauge is 100 at the start of the loops in
``team_cycle_reactions.FULL_GAUGE_LOOPS`` (1 and 3; loop 1 follows ``opening_gauge`` and is "zero" when the
constant leaves it out); the other loops keep what the members built up (heterochrome_add per hit,
gauge-setting skills, the outgoing member's gauge reset to 0 when its reaction fires).  The swap into a
refill loop is judged on the gauge its outgoing member built up in the previous loop; the refill follows it,
so every member enters the refill loop at 100.  At every swap the gauge (rule "game" fitted on a recorded
battle, or "ideal") decides whether the incoming member enters with the support skill and fires the
pair's reaction.  Reactions are always computed: 浊燃 / 黯星 / 创生 (and the 延滞 suit marker) are injected as
hit rows for the replay engine, 覆纹 / 浸染 are added after replay by their own formula, 延滞 / 盈蓄 / 失谐
are effects only.  Measured ultimate time stops are put on the axis and DPS divides by the battle time
without them.  Zankou's erosion / venom and Lacrimosa's nightmare damage-over-time ticks run every 1 s
of active time while their states live (their application GEs never become direct hits); with Zankou in
the team they also activate and refresh Zankou's Scorch, and the explanation credits them to the
owner's visits.

Transformation / form states (``team_form_actions``, generated): the attacks a member makes inside its
form (Zankou 幻境形态, Raven 救世的魔女, Shinku 升腾之赤, Hathor 紧急派送, Akane's second stage, Skia's
啮逐潜影 contact, Hotori's tachi, Fadia's chase) are placed from explicit hit timelines; rows carry the
ability the game logs.  Form windows use game-data durations on the active clock: steps that do not fit
are cut, a window with time left gets extra rounds (Raven), exit steps are checked against their window.

The axis runs through the same services the battle report uses (buff inference, skill damage
evidence, per-hit replay, Zankou / Shinku form configs), so every number is an expected-damage
estimate from the real formula.  ``TeamResult.explanation`` (``team_simulation_explanation``) records
the rotation, the loop / gauge rule, the form windows and the planner's choice.  Known limits: no
cooldown / energy check, summons and damage-over-time effects other than Zankou's / Lacrimosa's are
missing, buffs the engine cannot resolve are skipped, fixed Lv80 / 20% resistance dummy.

Custom-cycle mode: ``team_custom_cycle_service.simulate_custom`` lays a sequence the user typed on the same axis
(``_AxisWriter``), runs the same pipeline (``_run_axis``: ticks, reaction rows, engine, owner pass) inside the
same context (``_open_context``) and collects with ``_collect``; its options reach the engine through
``_Ctx.target_condition`` (enemy numbers) and ``_Ctx.buff_edit`` (buffs switched off / added by hand).  With the
defaults of those two fields the approved mode is unchanged.

Arc corrections (Global, ``team_fork_corrections``): the selected arc / refinement is written into the member's
profile so the panel follows it (B1, ``_build_characters``); right after ``analyze`` and before ``buff_edit`` the
engine's arc intervals are corrected (B2 always-on bonuses counted once, B3 「罪与罚」 and B4 「月的对跖点」 priced as
Global supplement rules on the active clock; ``_Ctx.fork_corrections``, report in ``_Run.corrections``).  The
explanation names the members they touched.  ``team_fork_corrections.ENABLED`` / ``NTE_TEAM_FORK_CORRECTIONS=off``
switch them off (the shipped numbers).  ``solo_session`` runs one member with many arc / refinement choices on one
shared context (the arc efficiency table); ``_open_context`` is built on the same session code.

Awakening selection (Global, ``team_awakening``; Korean UI "돌파"): a member is (level 0..6, a freely chosen set of
the ordinary effects ``Effect1..Effect6``); the resonances and the skill-level bonus follow the level alone.
``MemberSpec.awakening_effects`` carries the set; a spec with a level only means ``Effect1..level`` (old saves / calls,
byte-identical results) and an empty spec the graduation template's own selection.  Node rules
(``awakening_node_rules``: one registry, one module per character group) are prepared per context
(``_Ctx.node_rules``) and called at fixed points: buff rules after ``load_rules``, the axis writer's gate / placed
hooks (both modes), the swap rule (free support entries), DoT / extra hit rows before the engine, intervals right after
the arc corrections, evidence after the Scorch patch, increments after replay (``_collect``), and the resource state's
rule rows / hooks.  ``_with_node_notes`` writes their explanation items.  Without an active rule every path is the
selection model alone.
"""
from __future__ import annotations

import contextlib
import dataclasses
import itertools
import json
import re
import shutil
import sqlite3
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.services.team_cycle_reactions import FULL_GAUGE_LOOPS

DEFAULT_TARGET = {
    "confirmed": True,
    "enemy_level": 80,
    "scene": "outer_realm",
    "resistances": {k: 0.2 for k in ("chaos", "cosmos", "incantation", "lakshana", "nature",
                                      "normal", "psyche", "psychically")},
}
START_US = 500_000

ORDER_MODES = ("auto", "slot", "plan")
GAUGE_RULES = ("game", "ideal")
OPENING_GAUGES = ("full", "zero")
DEFAULT_LOOPS = 3              # user rule 2026-10-04: three loops (3바퀴)
MAX_LOOPS = 8
PLAN_MAX_RUNS = 4              # planner: candidates simulated in full (stage 2)
DEFAULT_STEP_S = 1.0           # time-only step without an estimate (brief §3)
TIME_STOP_PAUSE_MASK = 8       # Q time stop (battle_time_stop_projection_service.Q_PAUSE_TYPE_MASK)
# With no stop interval at all the engine falls back to inferred Q-action windows
# (BattleTimeStopProjectionService.resolve, source "inferred_q_action"): its clock would then have stops
# that the simulator's clock, explanation and DPS do not.  A 1 ms plain clock pause (not Q bits 2-4, not
# the Linko bit 6) after the last hit keeps the engine on "measured, no stop inside the axis".
NO_STOP_PAUSE_MASK = 1
NO_STOP_AFTER_END_US = 1_000_000

# Phase 1b damage-over-time ticks (brief §3): one tick per 1.00 s of active time while the state lives
# (measured 1.001 / 0.998 / 1.002 s).  Application rules mirror battle_dot_stack_state_service.
DOT_TICK_S = 1.0
ZANKOU_ID = 1036
LACRIMOSA_ID = 1004
RAVEN_ID = 1042
ZANKOU_DOT_DURATION_S = 30.0   # ZankouDotDamageDur (engine: erosion / venom 30 s)
DOT_STACK_LIMIT = 10
EROSION_GE = "GE_Player_Zankou_DotDamage"
VENOM_GE = "GE_Player_Zankou_DotUltraDamage"
NIGHTMARE_GE = "GE_Player_Lacrimosa_Blood_Damage"
NIGHTMARE_GE_ENHANCED = "GE_Player_Lacrimosa_Blood_Damage_LV6"
# Montages bind these tick effects at the moment the state is applied (an application marker, recorded
# rows only appear on the 1 s tick grid): they are never laid out as direct hits, _dot_tick_rows places them.
DOT_TICK_GES = frozenset((EROSION_GE, VENOM_GE, NIGHTMARE_GE, NIGHTMARE_GE_ENHANCED))
_DOT_LABELS = {"erosion": "蚀心", "venom": "鸩火", "nightmare": "「噩梦」"}
# Lacrimosa A3 settles every nightmare layer on these hits; the engine cannot replay a nightmare tick
# inside the following 0.5 s (battle_dot_stack_state_service), so no tick is placed there.
NIGHTMARE_SETTLE_GES = ("ge_player_lacrimosa_melee5_damage", "ge_player_lacrimosa_b_melee8_damage")
NIGHTMARE_SETTLE_WINDOW_US = 500_000
_TAG = re.compile(r"<[^>]*>")


@dataclass
class MemberSpec:
    character_id: int
    awakening_level: int | None = None
    fork_id: str | None = None
    fork_refinement_level: int | None = None
    suit_id: str | None = None
    # A1: selected ordinary awakening effects ("Effect1".."Effect6", any order; team_awakening).  None: a level alone
    # means Effect1..level (old saves / calls), no level either = the graduation template's own selection
    awakening_effects: tuple | None = None


@dataclass
class MemberResult:
    character_id: int
    name_zh: str
    fork_id: str
    fork_refinement_level: int
    awakening_level: int
    suit_id: str | None
    damage: float = 0.0             # direct damage, including the member's own damage-over-time ticks
    time_s: float = 0.0             # time on the field, time stops excluded
    hits: int = 0
    missing_actions: list[str] = field(default_factory=list)
    reaction_damage: float = 0.0    # cycle reactions credited to this member (覆纹 / 浸染 increments included)
    visits: int = 0
    team_time_s: float = 0.0        # battle time without time stops (the DPS denominator)
    element: str = ""
    role: str = ""
    awakening_effects: tuple = ()   # A1: the selected ordinary effects (team_awakening order)

    @property
    def total_damage(self) -> float:
        return self.damage + self.reaction_damage

    @property
    def dps(self) -> float:
        t = self.team_time_s if self.team_time_s > 0 else self.time_s
        return self.total_damage / t if t > 0 else 0.0


@dataclass
class TeamResult:
    members: list[MemberResult]
    team_buffs: list[dict]          # source_character_id, scope, modifiers, windows [(start_s, end_s)], start_s / end_s,
                                    # count (buffs with the same modifiers and windows shown as one line)
    replay_status: dict
    reaction_damage: float = 0.0
    reaction_breakdown: dict = field(default_factory=dict)   # reaction_zh -> damage
    wall_time_s: float = 0.0
    active_time_s: float = 0.0
    explanation: Any = None                                   # TeamExplanation

    @property
    def direct_damage(self) -> float:
        return sum(m.damage for m in self.members)

    @property
    def total_damage(self) -> float:
        return sum(m.damage + m.reaction_damage for m in self.members)

    @property
    def total_time_s(self) -> float:
        if self.active_time_s > 0:
            return self.active_time_s
        return sum(m.time_s for m in self.members)

    @property
    def reaction_share(self) -> float:
        total = self.total_damage
        return self.reaction_damage / total if total > 0 else 0.0

    @property
    def dps(self) -> float:
        t = self.total_time_s
        return self.total_damage / t if t > 0 else 0.0


# ── catalog helpers for the page ──────────────────────────────────────────

def _ro_uri(path) -> str:
    """Read-only SQLite URI for a database file.

    Path.as_uri() percent-encodes the path (spaces, '#', '%', '?', non-ASCII) the way the rest of the
    application opens the static database; a raw f"file:{path}" is cut at the first '#' or '?'.
    """
    return f"{Path(path).absolute().as_uri()}?mode=ro"


def list_template_characters(static_path: Path) -> list[dict]:
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        rows = con.execute(
            "SELECT g.character_id, c.name_zh, g.fork_id, g.fork_refinement_level, g.core_suit_id, g.profile_json "
            "FROM character_graduation_template g JOIN character c USING(character_id) ORDER BY g.character_id"
        ).fetchall()
    finally:
        con.close()
    from src.services import team_awakening

    out = []
    for cid, name, fork_id, refine, suit, profile_json in rows:
        profile = json.loads(profile_json or "{}")
        selection = team_awakening.from_profile(profile)
        out.append({"character_id": cid, "name_zh": name, "fork_id": fork_id,
                    "fork_refinement_level": refine or 1, "suit_id": suit,
                    "awakening_level": int(profile.get("awakening_level", 0) or 0),
                    # A3: the template's own node selection (the card default; read, never hard-coded)
                    "selected_awaken_effect_ids": list(selection.effects)})
    return out


def awaken_effect_catalog(static_path: Path, character_ids=None) -> dict[int, list[dict]]:
    """{character id: [node, ...]} for the member cards' tooltips: ``effect_id``, ``ordinal``, ``awaken_type``
    (Awaken_Effect | Awaken_Resonance), ``title_zh``, ``description_zh`` (raw, markup kept: the display layer
    translates the exact text) and ``values`` {placeholder index: number text} rendered at the graduation template's
    skill levels (``official_role_awakening_service.render_awaken_effect_description``)."""
    from src.services.official_role_awakening_service import _description_damage_value
    from src.storage.sqlite.static_game_data_dao import StaticGameDataDao

    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        profiles = {int(c): json.loads(p or "{}") for c, p in
                    con.execute("SELECT character_id, profile_json FROM character_graduation_template")}
    finally:
        con.close()
    wanted = sorted(profiles) if character_ids is None else [int(c) for c in character_ids]
    out: dict[int, list[dict]] = {}
    with StaticGameDataDao(Path(static_path)) as static:
        for cid in wanted:
            effects = list(static.list_character_awaken_effects(cid))
            profile = dict(profiles.get(cid) or {})
            rows = []
            for effect in effects:
                values = {}
                for i, damage in enumerate(effect.get("description_damage_entries") or ()):
                    try:
                        value = _description_damage_value(damage, profile, effects)
                    except Exception:
                        value = None
                    if value is not None:
                        values[i] = f"{value:.6f}".rstrip("0").rstrip(".")
                rows.append({"effect_id": str(effect.get("effect_id") or ""), "ordinal": int(effect.get("ordinal") or 0),
                             "awaken_type": str(effect.get("awaken_type") or ""),
                             "title_zh": str(effect.get("title_zh") or ""),
                             "description_zh": str(effect.get("description_zh") or ""), "values": values})
            out[cid] = rows
    return out


def list_forks_for(static_path: Path, template_fork_id: str, character_id: int) -> list[dict]:
    """Forks usable by the character: same fork type as the template fork, exclusive ones only for their owner."""
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        row = con.execute("SELECT fork_type_id FROM fork_item WHERE fork_id=?", (template_fork_id,)).fetchone()
        if row is None:
            return []
        rows = con.execute(
            "SELECT fork_id, name_zh, quality, exclusive_character_ids_json FROM fork_item "
            "WHERE fork_type_id=? ORDER BY quality DESC, fork_id", (row[0],)
        ).fetchall()
    finally:
        con.close()
    forks = []
    for fork_id, name, quality, exclusive in rows:
        owners = {str(o) for o in (json.loads(exclusive or "[]") if exclusive else [])}
        if owners and str(character_id) not in owners:   # ids are stored as strings
            continue
        forks.append({"fork_id": fork_id, "name_zh": name, "quality": quality})
    return forks


def equippable_forks(static_path: Path, character_id: int, *, include_foreign: bool = True) -> list[dict]:
    """Arcs the character can equip under the only rule in the data (rule A, as the official 2.3.1
    ``_compatible_forks``): ``fork_item.raw_group_type == character.group_type``.  Other characters' exclusive arcs
    are kept and flagged (``foreign_exclusive``, ``owner_ids`` / ``owner_names_zh``) unless ``include_foreign`` is
    False.  Exclusive owner ids are stored as JSON strings.  Order as ``list_forks_for`` (quality DESC, fork_id)."""
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        row = con.execute("SELECT group_type FROM character WHERE character_id=?", (int(character_id),)).fetchone()
        if row is None or row[0] in (None, ""):
            return []
        names = {str(c): n for c, n in con.execute("SELECT character_id, name_zh FROM character")}
        rows = con.execute(
            "SELECT fork_id, name_zh, quality, exclusive_character_ids_json FROM fork_item "
            "WHERE raw_group_type=? ORDER BY quality DESC, fork_id", (row[0],)
        ).fetchall()
    finally:
        con.close()
    out = []
    for fork_id, name, quality, exclusive in rows:
        owners = tuple(dict.fromkeys(str(o) for o in (json.loads(exclusive or "[]") if exclusive else [])))
        own = str(character_id) in owners
        foreign = bool(owners) and not own
        if foreign and not include_foreign:
            continue
        out.append({"fork_id": fork_id, "name_zh": name, "quality": quality,
                    "owner_ids": tuple(int(o) for o in owners if o.isdigit()),
                    "owner_names_zh": tuple(dict.fromkeys(names.get(o, o) for o in owners)),
                    "own_exclusive": own, "foreign_exclusive": foreign})
    return out


def attribute_names(static_path: Path) -> dict[str, tuple[str, bool]]:
    """property id -> (Chinese display name, shown as percent)."""
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        return {a: (n, bool(p)) for a, n, p in
                con.execute("SELECT attribute_id, display_name_zh, show_percent FROM equipment_attribute")}
    finally:
        con.close()


def list_suits(static_path: Path) -> list[dict]:
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        return [{"suit_id": s, "name_zh": n} for s, n in
                con.execute("SELECT suit_id, name_zh FROM equipment_suit ORDER BY suit_id")]
    finally:
        con.close()


# ── simulation: members ───────────────────────────────────────────────────

def _build_characters(con: sqlite3.Connection, specs: list[MemberSpec]) -> list[dict]:
    names = {r[0]: r[1] for r in con.execute("SELECT character_id, name_zh FROM character")}
    characters = []
    for spec in specs:
        row = con.execute("SELECT profile_json, equipment_json, fork_id, fork_refinement_level, core_suit_id "
                          "FROM character_graduation_template WHERE character_id=?", (spec.character_id,)).fetchone()
        if row is None:
            raise ValueError(f"no graduation template for {spec.character_id}")
        profile = json.loads(row[0])
        equipment = json.loads(row[1])
        suit_id = spec.suit_id or row[4]
        for item in equipment:
            stats = []
            for group in ("main", "sub"):
                for ordinal, st in enumerate(item.get(f"{group}_stats") or ()):
                    stats.append({"stat_group": group, "ordinal": ordinal, "property_id": st["property_id"],
                                  "value": st["value"], "is_percent": st.get("percent", False)})
            item["stats"] = stats
            if item.get("kind") == "core" and suit_id:
                item["suit_id"] = suit_id
        shapes = sorted({r[0] for r in con.execute(
            "SELECT shape_id FROM equipment_suit_required_shape WHERE suit_id=?", (suit_id,))}) if suit_id else []
        for item in equipment:
            if item.get("kind") == "module":
                item["graduation_assumed_shape_ids"] = shapes
        # A2: the member's node set (team_awakening): a level alone = Effect1..level (old saves / calls), nothing =
        # the template's own selection, a set = that set in any order (level = max(level, count))
        from src.services import team_awakening

        effects = getattr(spec, "awakening_effects", None)
        valid = None
        if effects is not None:
            valid = [r[0] for r in con.execute(
                "SELECT effect_id FROM character_awaken_effect WHERE character_id=? AND awaken_type='Awaken_Effect'",
                (spec.character_id,))] or None
        selection = team_awakening.resolve_spec(spec.awakening_level, effects, profile, valid)
        awakening = selection.level
        profile["awakening_level"] = awakening
        # buff inference reads the selected list, not the level (brief §0): keep them in step
        profile["awakening_selection_initialized"] = True
        profile["selected_awaken_effect_ids"] = list(selection.effects)
        fork_id = spec.fork_id or row[2]
        refine = spec.fork_refinement_level or row[3] or 1
        # B1: the panel (stat reconstruction) reads the arc from the profile, the buff rules from the columns below
        from src.services.team_fork_corrections import sync_profile

        sync_profile(profile, fork_id, refine)
        skills =[{"skill_id": k, "skill_level": v} for k, v in (profile.get("skill_levels") or {}).items()]
        characters.append({
            "character_id": spec.character_id, "observed_name": names[spec.character_id],
            "character_level": profile.get("character_level", 80), "awakening_level": awakening,
            "fork_id": fork_id, "fork_refinement_level": refine, "profile": profile, "equipment": equipment,
            "skills": skills,
            "_suit_id": suit_id,
            "_awakening": selection,        # team_awakening.AwakeningSel (kept out of the engine build: "_" key)
        })
    return characters


def _add_form_skill_levels(static, build: dict) -> None:
    """Form GEs the replay cannot level (no level-hint owner, team_form_actions.LEVEL_PARENTS: Hathor's 轮转打击 =
    her E, Hotori's tachi finisher = her ultimate) take their parent skill's effective level, awakening bonus
    included; without this the engine prices them at level 1."""
    from src.services.official_role_awakening_service import awaken_skill_level_delta
    from src.services.team_form_actions import LEVEL_PARENTS

    for character in build.get("characters") or ():
        parents = LEVEL_PARENTS.get(int(character["character_id"])) or {}
        if not parents:
            continue
        skills = character.setdefault("skills", [])
        levels = {str(s.get("skill_id")): int(s.get("skill_level") or 1) for s in skills}
        profile = dict(character.get("profile") or {})
        profile.setdefault("awakening_level", int(character.get("awakening_level") or 0))
        effects = tuple(static.list_character_awaken_effects(int(character["character_id"])))
        for logged, parent in parents.items():
            if logged in levels or parent not in levels:
                continue
            level = (levels[parent] + awaken_skill_level_delta(profile, effects, parent)
                     - awaken_skill_level_delta(profile, effects, logged))
            skills.append({"skill_id": logged, "skill_level": int(level)})


def _approved_steps(character_id: int) -> list[dict]:
    from src.services.team_rotation_data import CHARACTERS

    data = CHARACTERS.get(int(character_id))
    if not data:
        raise ValueError(f"no approved rotation for {character_id}")
    return [dict(step) for step in data["variants"]["approved"]["steps"]]   # copies: never reorder the data


def _cyclic_adjacency(order, elements: dict[int, str]) -> int:
    from src.services.team_cycle_reactions import is_adjacent

    n = len(order)
    if n < 2:
        return 0
    return sum(is_adjacent(elements.get(order[i], ""), elements.get(order[(i + 1) % n], "")) for i in range(n))


def _visit_order(team_ids: list[int], elements: dict[int, str], order_mode: str) -> tuple[int, ...]:
    """'slot': 1→2→3→4.  'auto': most adjacent pairs around the loop (closing swap included), then the
    member with the longest approved field time last, then slot order (stable).  ('plan' is chosen by
    _plan_order; this returns its 'auto' starting point.)"""
    from src.services.team_rotation_data import CHARACTERS

    if order_mode == "slot" or len(team_ids) < 2:
        return tuple(team_ids)

    def field_time(cid: int) -> float:
        return float((CHARACTERS.get(cid) or {}).get("field_time_s") or 0.0)

    def key(order: tuple[int, ...]):
        return (-_cyclic_adjacency(order, elements), -field_time(order[-1]))

    return min(itertools.permutations(team_ids), key=key)   # min() keeps the first (slot-order) best


def _effective_opening(opening_gauge: str, full_gauge_loops=FULL_GAUGE_LOOPS) -> str:
    """Loop 1 starts with every gauge at 100 only when FULL_GAUGE_LOOPS lists it; otherwise the opening is "zero"."""
    return opening_gauge if 1 in {int(n) for n in full_gauge_loops} else "zero"


def _visit_plan(character_id: int, entry: str, normal_entry: dict) -> list[tuple[dict, str]]:
    """Steps of one visit as (step, mode); mode 'run' or 'skipped' (support skill dropped on a normal swap)."""
    from src.services.team_rotation_data import QTE_SEQ_OVERRIDE

    steps = _approved_steps(character_id)
    qte_seq = QTE_SEQ_OVERRIDE.get(int(character_id), 1)
    entry_step = next((s for s in steps if s.get("entry_only")), None)
    if entry == "support_skill":
        if entry_step is None:
            return [(s, "run") for s in steps]
        rest = [s for s in steps if s is not entry_step and not (qte_seq != 1 and s["seq"] == 1)]
        return [(entry_step, "run")] + [(s, "run") for s in rest]
    plan = []
    if entry == "normal":
        sub = normal_entry.get(int(character_id))
        if sub:
            plan.append(({"seq": 0, "slot": "entry", "ability_id": sub[0], "selector": sub[1], "repeat": 1,
                          "entry_only": False, "sim": True, "est_s": None, "gauge_set": None}, "run"))
        if entry_step is not None:
            plan.append((entry_step, "skipped"))
    plan += [(s, "run") for s in steps if s is not entry_step]
    return plan


# ── form actions (generated team_form_actions) ────────────────────────────

def _us(seconds: float) -> int:
    return int(round(float(seconds) * 1_000_000))


def _form_candidates(team_ids) -> dict:
    """(form ability, "Form:<Name>") -> synthetic animation candidate for the layout (never for the engine)."""
    from src.services.battle_action_inference_service import BattleActionAnimationCandidate
    from src.services.team_form_actions import FORM_ACTIONS

    team = {int(c) for c in team_ids}
    out = {}
    for key, action in FORM_ACTIONS.items():
        if int(action["character_id"]) not in team:
            continue
        length = _us(action["length_s"])
        out[tuple(key)] = BattleActionAnimationCandidate(
            ability_id=key[0], selector_key=key[1], montage_asset_path=f"synthetic:{key[0]}:{key[1]}",
            effect_hit_offsets_us=tuple((ge, tuple(_us(o) for o in offs)) for ge, _logged, offs in action["hits"]),
            trigger_end_offsets_us=(length,), end_event_offsets_us=(length,), section_end_offsets_us=(length,),
            duration_us=length)
    return out


def _form_logged() -> dict[str, str]:
    """GE of a form action -> the ability the game logs its rows under (skill_damage.ability_id)."""
    from src.services.team_form_actions import FORM_ACTIONS

    return {ge: logged for action in FORM_ACTIONS.values() for ge, logged, _offs in action["hits"]}


def _load_candidates(static, team_ids) -> tuple[tuple, dict]:
    """(engine candidates, layout lookup).  The engine gets the bound candidates only, exactly as for a recorded
    battle (the battle report replays recorded form hits without form candidates); the layout lookup also holds
    the generated form actions.  Strict (ability_id, selector) keys, no fallback."""
    from src.services.battle_animation_window_service import BattleAnimationWindowService

    bound = tuple(BattleAnimationWindowService.load_candidates(static, character_ids=list(team_ids)))
    by_key = {(c.ability_id, c.selector_key): c for c in bound}
    for key, cand in _form_candidates(team_ids).items():
        if key in by_key:
            raise ValueError(f"form action {key} collides with a bound animation candidate")
        by_key[key] = cand
    return bound, by_key


def _form_members(team_ids) -> set[int]:
    """Members with form-state actions (transformation damage dealers and form users)."""
    from src.services.team_form_actions import FORM_ACTIONS, FORMS

    owners = {int(a["character_id"]) for a in FORM_ACTIONS.values()} | {int(c) for c in FORMS}
    return {int(c) for c in team_ids} & owners


# ── simulation: axis layout ───────────────────────────────────────────────

@dataclass
class _StepRun:
    seq: int
    slot: str
    ability_id: str | None
    selector: str | None
    start_us: int
    end_us: int
    status: str
    rows: list = field(default_factory=list)
    form_role: str = ""
    actions: tuple = ()             # (ability, selector) actions laid out (form combos may be cut short)
    # resources (team_resources; defaults = the legacy level, nothing checked)
    cd_kind: str = ""               # cooldown kind of the step (E / Q / QTE / counter / E_alt), "" = none
    energy_before: float | None = None   # pool energy / own clock before the step (None = not modelled)
    energy_after: float | None = None
    cost: float | None = None       # enforced cost the step was checked against
    remaining_us: int = 0           # cooldown / resource time left when reached (waits, skips, warn notes)
    note: str = ""                  # energy_short | cd_not_ready (warn) | extra_e | form_not_entered | too_long
    events: tuple = ()              # ((code, amount), ...) energy events after the step
    credit: float = 0.0             # gauge credited to a time-only step
    energy_raw: float = 0.0         # sum of charge_add of the step's hits (scaled by the efficiency at the end)
    energy_events: float = 0.0      # energy events after the step (after:E / after:Q)
    gauge_after: float | None = None    # the member's cycle gauge after the step (resource levels)
    gauge_gain: float = 0.0         # gauge built by the step (hits, credit, set values)
    cd_s: float | None = None       # cooldown of the step's kind the check used (None = unknown / not enforced)
    cd_conf: str = ""               # confidence of that cooldown cell (team_resource_data)
    cd_source: str = ""             # short source tag of that cell
    dropped: int = 0                # swap_out (D3): approved steps of the visit not run after it
    wait_for: int | None = None     # wait row "all_blocked": the member whose readiness was waited for


@dataclass
class _VisitRun:
    index: int
    loop_index: int
    character_id: int
    entry: str
    start_us: int
    end_us: int
    gauge_in: float
    gauge_out: float = 0.0
    steps: list = field(default_factory=list)
    refilled: bool = False
    form: dict | None = None        # form window summary (see _FormRun.summary)
    energy_in: float | None = None  # pool energy / own clock when entering (None = not modelled)
    energy_out: float | None = None
    waited_us: int = 0              # cooldown / resource waits inserted in this visit
    energy_gain: float = 0.0        # ultimate energy gained in this visit (also for unknown costs)
    energy_raw: float = 0.0         # charge_add of the visit's hits (the explanation applies the efficiency)
    energy_events: float = 0.0      # energy events of the visit
    early_swap: tuple = ()          # D3: (seq, kind, seconds left | None, reason, steps not run) when it ended early


@dataclass
class _SwapRun:
    index: int
    time_us: int
    out_character_id: int
    in_character_id: int
    out_element: str
    in_element: str
    gauge: float
    outcome: str
    reaction_index: int | None


@dataclass
class _Layout:
    rows: list                      # direct hit dicts
    side: dict                      # id(row) -> (visit_idx, step_idx)
    visits: list
    swaps: list
    stops: list                     # disjoint (start_us, end_us), time order
    stop_owners: list               # (character_id, ability_id) per stop
    end_us: int
    missing: dict                   # cid -> ["ability:selector", ...]
    unknown_stop: set               # cids with an ultimate step and no measured stop
    used_default_time: bool
    used_gauge_set: bool
    used_normal_entry: bool
    refill_loops: tuple = ()        # 1-based loops that started with every gauge at the cap
    form_actions: dict = field(default_factory=dict)   # cid -> {(ability, selector): runs}
    refills: tuple = ()             # ((1-based loop, character id), ...) gauge-fallback refills (resource levels)
    resources: Any = None           # team_resources.ResourceState of the layout (None = legacy level)
    waited_us: int = 0              # cooldown / resource waits inserted in total
    hit_credited: dict = field(default_factory=dict)   # cid -> uses whose unplaced hits were credited (HIT_CREDIT)
    charge_done: bool = False       # the 盈蓄 energy grants were credited to the visits (once per layout)
    charge_energy: float = 0.0      # 盈蓄 ultimate energy credited in total
    charge_grants: int = 0
    node_hooks: Any = None          # awakening_node_rules.LayoutHooks of the layout (None = no layout-level rule)
    run_hooks: Any = None           # awakening_node_rules.RunHooks of the engine run on this layout (_collect: post)
    node_gauge: tuple = ()          # (t_us, cid, amount): Cycle-gauge gains of awakening node rules (add_gauge)


def _row(cid: int, name: str, t_us: int, ability_id: str | None, ge: str, attribute: str) -> dict:
    return {
        "sequence_text": "0", "sequence_order": 0, "relative_time_us": int(t_us),
        "character_id": cid, "character_name": name, "character_known": 1,
        "direction": "outgoing", "damage": 1.0, "follow_up_damage": 0,
        "ability_name": ability_id, "gameplay_effect_name": ge,
        "damage_attribute": attribute, "attack_type": "", "target_id": "dummy", "target_name": "dummy",
        "follow_up_labels": [],
    }


def _is_damage_effect(ge: str) -> bool:
    return ge.endswith("Damage") or "_Damage" in ge


def _step_length_us(cand, est_s: float | None) -> int:
    """Animation trigger end; a montage without one is only its full length (idle tail included,
    e.g. Oneiroi Branch5 9.37 s for "cast, then swap at once"), so the approved estimate is used there."""
    if cand.trigger_end_offsets_us:
        return int(cand.trigger_end_offsets_us[0] or 0)
    if est_s is not None:
        return int(round(float(est_s) * 1_000_000))
    return int(cand.duration_us or 0)


def _add_stop(stops: list, owners: list, start_us: int, duration_s: float, owner: tuple) -> None:
    """Append one measured stop, clipped so the intervals stay disjoint (Linko's 11 s stop can overlap)."""
    end_us = int(start_us + round(duration_s * 1_000_000))
    start_us = max(int(start_us), stops[-1][1] if stops else int(start_us))
    if end_us <= start_us:
        return
    stops.append((start_us, end_us))
    owners.append(owner)


def _active_between(stops: list, a_us: int, b_us: int) -> int:
    """Active µs between two wall times (time stops excluded)."""
    if b_us <= a_us:
        return 0
    total = b_us - a_us
    for s, e in stops:
        lo, hi = max(a_us, s), min(b_us, e)
        if hi > lo:
            total -= hi - lo
    return total


class _AxisWriter:
    """Lays the hit rows of one action on the simulator axis: the rows, the row -> (visit, step) side table,
    measured time stops, gauge gain per hit and form-action counts.  Shared by the approved layout
    (_layout_axis) and the custom-cycle walker (team_custom_cycle_service)."""

    def __init__(self, static, by_key, names, gauge, stops: list, resources=None, hit_credits=None,
                 node_hooks=None) -> None:
        from src.services.team_form_actions import FORM_ACTIONS
        from src.services.team_rotation_data import Q_TIME_STOP_S

        self.node_hooks = node_hooks    # awakening_node_rules.LayoutHooks: gate / placed hooks (None = none)
        self.static = static
        self.by_key = by_key
        self.names = names
        self.gauge = gauge
        self.stops = stops
        self.resources = resources      # team_resources.ResourceState: ultimate energy per hit (None = legacy)
        # custom cycles at a resource level (no ResourceState): team_resource_data.HIT_CREDIT for the gauge
        self.hit_credits = hit_credits
        self.credited: dict[int, int] = defaultdict(int)    # cid -> uses whose unplaced hits were credited
        self.last_credit = None         # HIT_CREDIT cell of the last place() call (None = nothing credited)
        # reviewed layout at the resource levels: gauge gains wait in time order until the axis reaches the hit
        # (flush), so a hit landing after its member left the field is not counted towards that swap (review F-G)
        self.defer_gauge = False
        self._pending: list[tuple[int, int, int, float]] = []    # (hit µs, order, cid, heterochrome_add)
        self._pending_n = 0
        self.rows: list[dict] = []
        self.side: dict[int, tuple[int, int]] = {}
        self.stop_owners: list[tuple] = []
        self.unknown_stop: set[int] = set()
        self.form_actions: dict[int, dict] = defaultdict(lambda: defaultdict(int))
        self._damage_cache: dict[str, dict | None] = {}
        self.node_energy: dict[int, list] = defaultdict(list)   # custom cycles: node-rule energy not yet measured
        self.node_gauge: list[tuple[int, int, float]] = []      # node-rule Cycle-gauge gains (t_us, cid, amount)
        self._form_logged = _form_logged()
        self._form_keys = {tuple(k) for k in FORM_ACTIONS}
        self._time_stops = Q_TIME_STOP_S

    def skill_damage(self, ge: str):
        if ge not in self._damage_cache:
            self._damage_cache[ge] = self.static.get_skill_damage(ge) or None
        return self._damage_cache[ge]

    def action_len(self, action, est_s=None) -> int:
        cand = self.by_key.get(action)
        return 0 if cand is None else _step_length_us(cand, est_s)

    def place(self, cid: int, vi: int, si: int, run: "_StepRun", action: tuple, t0: int, est_s) -> int:
        """Lay out one action's hits from t0; returns its length (µs)."""
        cand = self.by_key[action]
        ability = action[0]
        if ability in self._time_stops:
            _add_stop(self.stops, self.stop_owners, t0, self._time_stops[ability], (cid, ability))
        elif run.slot == "ultimate":
            self.unknown_stop.add(cid)
        is_form = action in self._form_keys
        if is_form:
            self.form_actions[cid][action] += 1
        placed = len(run.rows)
        effect_offsets = cand.effect_hit_offsets_us
        if self.node_hooks is not None:     # awakening node rules: the bound GEs this action lays out (gate)
            effect_offsets = self.node_hooks.gate(cid, action, run.slot, t0, effect_offsets)
        for ge, offsets in effect_offsets:
            if not _is_damage_effect(ge) or ge in DOT_TICK_GES:
                continue
            dmg = self.skill_damage(ge)
            if not dmg:
                continue
            attribute = str(dmg.get("damage_type") or "").lower()
            logged = self._form_logged.get(ge, ability) if is_form else ability
            for off in offsets:
                row = _row(cid, self.names[cid], t0 + int(off), logged, ge, attribute)
                self.rows.append(row)
                self.side[id(row)] = (vi, si)
                run.rows.append(row)
                if self.defer_gauge:
                    self._pending_n += 1
                    self._pending.append((t0 + int(off), self._pending_n, int(cid),
                                          float(dmg.get("heterochrome_add") or 0.0)))
                else:
                    self.gauge.gain(cid, dmg.get("heterochrome_add"))
                if self.resources is not None:
                    self.resources.gain_hit(cid, dmg)
        self.last_credit = None
        if len(run.rows) == placed:     # the animation laid out no hit: summon / zone hits credited (resource levels)
            credit = None
            if self.resources is not None:
                credit = self.resources.hit_credit(cid, action)
            elif self.hit_credits is not None:
                cell = self.hit_credits.get((int(cid), str(action[0]), str(action[1] or "")))
                credit = cell if cell is not None and cell[0] is not None else None
            if credit is not None:
                self.gauge.gain(cid, credit[1])
                if self.resources is not None:
                    self.resources.gain_raw(cid, credit[0])
                self.credited[int(cid)] += 1
                self.last_credit = credit
        length = _step_length_us(cand, est_s)
        if self.node_hooks is not None:     # awakening node rules: the action log / placed hooks
            from src.services.awakening_node_rules.core import PlacedAction

            self.node_hooks.on_placed(PlacedAction(int(cid), tuple(action), str(run.slot or ""), int(t0), int(length),
                                                   tuple(run.rows[placed:]), int(vi), int(si), self))
        return length

    def add_gauge(self, cid: int, amount: float, t_us: int) -> None:
        """A Cycle-gauge gain at ``t_us`` outside the hit loop (awakening node rules): queued like the hits' gains
        at the resource levels (``defer_gauge``, review F-G), applied at once otherwise."""
        if not amount:
            return
        self.node_gauge.append((int(t_us), int(cid), float(amount)))     # kept for checks / diagnostics
        if self.defer_gauge:
            self._pending_n += 1
            self._pending.append((int(t_us), self._pending_n, int(cid), float(amount)))
        else:
            self.gauge.gain(cid, amount)

    def add_energy(self, cid: int, amount: float, code: str, t_us: int) -> None:
        """Ultimate energy from an awakening node rule (an event: not scaled by the charge efficiency).  Reviewed
        layouts: the ResourceState event; custom cycles: kept until the walker's measure takes it
        (``take_node_energy``) into its pools and the step record."""
        if not amount:
            return
        if self.resources is not None:
            self.resources.add_energy(int(cid), float(amount), str(code))
        else:
            self.node_energy[int(cid)].append((str(code), float(amount), int(t_us)))

    def take_node_energy(self, cid: int) -> float:
        """Node-rule energy of ``cid`` since the last call (custom walker), then forgotten."""
        items = self.node_energy.pop(int(cid), None) or ()
        return float(sum(amount for _code, amount, _t in items))

    def flush(self, t_us: int | None = None) -> None:
        """Apply the deferred gauge gains of hits at or before ``t_us`` (None = all), in time order."""
        if not self._pending:
            return
        self._pending.sort()
        keep = []
        for item in self._pending:
            if t_us is None or item[0] <= t_us:
                self.gauge.gain(item[2], item[3])
            else:
                keep.append(item)
        self._pending = keep

    def late_gauge(self) -> dict[int, float]:
        """Deferred gauge per member not yet applied (hits after the current axis time)."""
        out: dict[int, float] = defaultdict(float)
        for _t, _n, cid, amount in self._pending:
            out[cid] += amount
        return dict(out)


class _FormRun:
    """One form window inside a visit (rule = team_form_actions.FORMS[cid]); every clock is active time."""

    def __init__(self, rule: dict, start_us: int, stops: list, groups_approved: int) -> None:
        self.rule = rule
        self.start_us = int(start_us)
        self.stops = stops
        self.duration_us = _us(rule["duration_s"])
        self.groups_approved = groups_approved
        self.kept: list[int] = []
        self.decided: dict[int, bool] = {}
        self.fills = 0
        self.cut_steps = 0
        self.overrun_us = 0
        self.exit_us: int | None = None
        self.window: tuple = ()
        self.status = "ok"
        self.last_us = self.start_us
        self.closed = False
        self.body_run = 0

    def elapsed(self, t_us: int) -> int:
        return _active_between(self.stops, self.start_us, t_us)

    def inside(self, t_us: int) -> bool:
        return not self.closed and self.elapsed(t_us) < self.duration_us

    def mark(self, status: str) -> None:
        order = ("ok", "cut", "overrun", "window_missed")
        if order.index(status) > order.index(self.status):
            self.status = status

    def summary(self) -> dict:
        rule = self.rule
        used = min(self.duration_us, self.exit_us if self.exit_us is not None else self.elapsed(self.last_us))
        policy = rule.get("policy")
        if policy == "size":
            groups = len(self.kept) + self.fills
        else:
            groups = self.body_run
        return {"code": rule["code"], "name_zh": rule["name_zh"], "duration_s": float(rule["duration_s"]),
                "start_us": self.start_us, "used_s": max(0, used) / 1e6, "groups": groups,
                "groups_approved": self.groups_approved, "fills": self.fills, "cut_steps": self.cut_steps,
                "overrun_s": self.overrun_us / 1e6, "status": self.status,
                "pauses_off_field": bool(rule.get("pauses_off_field")), "ends_on_swap": bool(rule.get("ends_on_swap")),
                "exit_s": None if self.exit_us is None else self.exit_us / 1e6, "window": tuple(self.window)}


def _swap_reason(gate) -> str:
    """Why a step was not ready: cd (cooldown) | energy (a known ultimate cost) | clock (Hotori's own clock)."""
    if gate.action == "energy_short":
        return "energy" if gate.reason == "energy_short" else "clock"
    return "clock" if gate.wait_kind == "res_wait" else "cd"


def _not_ready_choice(resources, cid: int, gate, t_us: int, order, approved_of: dict) -> tuple:
    """User decision D3 (2026-10-14) for a team member whose step is not ready at ``t_us``.

    ``("swap", 0, None)``: another member could act at once - swap out now.  When every member is blocked the
    earliest ready one is waited for (no endless swapping): ``("run", 0, cid)`` this member itself (its own wait, then
    the step), ``("wait_swap", policy-clock µs, other)`` wait for ``other``, then swap out; ``("keep", 0, None)``
    nothing gets ready by waiting within the guard (the skip / wait of the gate applies).  Readiness of the others is
    judged at ``t_us`` (their entry time is not counted); ties go to this member, then to the visiting order."""
    from src.services.team_resources import TOLERANCE_US

    ring = list(dict.fromkeys(int(c) for c in order))
    k = ring.index(int(cid))
    others = [ring[(k + i) % len(ring)] for i in range(1, len(ring))]
    remaining = []
    for other in others:
        r = resources.first_block_us(other, approved_of.get(other) or _approved_steps(other), t_us)
        if r is not None and r <= TOLERANCE_US:
            return "swap", 0, None
        remaining.append((r, other))
    own = None if gate.action == "energy_short" else int(gate.remaining_us)
    cands = [(r, i, c) for i, (r, c) in enumerate([(own, int(cid))] + remaining) if r is not None]
    if not cands:
        return "keep", 0, None
    r, _i, who = min(cands)
    if r > resources.guard_us() + TOLERANCE_US:
        return "keep", 0, None
    if who == int(cid):
        return ("keep", 0, None) if gate.action in ("energy_short", "cd_skip") else ("run", 0, who)
    return "wait_swap", int(r), who


def _layout_axis(static, order, loops, by_key, gauge, sched, names, elements, stops: list, *,
                 opening_gauge: str = "full", full_gauge_loops=FULL_GAUGE_LOOPS, resources=None,
                 node_hooks=None) -> _Layout:
    """Visits and steps on one timeline: gauge accumulation (refills at FULL_GAUGE_LOOPS), support-skill labels,
    form windows, time stops and triggers.

    ``resources`` (team_resources.ResourceState, None = the legacy level): ultimate energy per hit, the energy /
    cooldown / own-resource check of every step (skips and inserted waits), gauge credits of time-only steps, and
    the refill loops of FULL_GAUGE_LOOPS after loop 1 refill only the gauge-fallback members.  A team member whose
    step is not ready swaps out at once (``ResourceState.not_ready_mode``, D3): the visit ends with a ``swap_out`` row
    and the next member enters by the normal rules (support skill when the gauge allows); visits per loop do not
    change.  Alone the member waits."""
    from src.services.team_cycle_reactions import support_skill_attack_type
    from src.services.team_form_actions import FORMS
    from src.services.team_rotation_data import NORMAL_ENTRY

    writer = _AxisWriter(static, by_key, names, gauge, stops, resources,   # rows, side table, stops, gauge gain
                         node_hooks=node_hooks)                            # awakening node rules (gate / placed)
    writer.defer_gauge = resources is not None      # hit-time gauge at the resource levels (review F-G)
    flush = writer.flush
    rows, side, stop_owners = writer.rows, writer.side, writer.stop_owners
    unknown_stop, form_actions = writer.unknown_stop, writer.form_actions
    action_len, place = writer.action_len, writer.place
    visits: list[_VisitRun] = []
    swaps: list[_SwapRun] = []
    missing: dict[int, list[str]] = defaultdict(list)
    used_default = used_gauge_set = used_normal = False
    # loop 1 is full when the (effective, see _effective_opening) opening is "full"
    refill_loops: list[int] = [1] if opening_gauge == "full" else []
    member_refills: list[tuple[int, int]] = []      # (1-based loop, cid) fallback refills (resource levels)
    waited_total = 0
    swap_mode = resources is not None and resources.not_ready_mode() == "swap"      # D3 (teams)
    approved_of = {int(c): _approved_steps(c) for c in dict.fromkeys(order)} if swap_mode else {}

    t_us = START_US
    previous: int | None = None
    for loop_index in range(loops):
        refill_now = loop_index > 0 and gauge.refills_at(loop_index + 1, full_gauge_loops)
        refilled = (loop_index == 0 and opening_gauge == "full") or refill_now
        refilled_members: set[int] = set()
        for pos, cid in enumerate(order):
            vi = len(visits)
            # the boundary swap into a loop is judged on the gauges the previous loop built up (its outgoing
            # member belongs to that loop); a refill loop then starts with every member at 100, like loop 1
            flush(t_us)                 # hits up to the swap (later ones count after the decision, review F-G)
            decision = gauge.on_swap(previous, cid)
            if (node_hooks is not None and decision.outcome == "gauge_short" and decision.pair_reaction is not None
                    and node_hooks.free_support(previous, cid, t_us, decision.pair_reaction, decision)):
                # awakening node rule (free_support): the support entry needs no gauge and does not consume it
                decision = dataclasses.replace(decision, entry="support_skill", outcome="reaction",
                                               reaction=decision.pair_reaction)
            if refill_now and pos == 0:
                if resources is None:
                    gauge.refill_all()
                    refill_loops.append(loop_index + 1)
                else:       # resource levels: only members without gauge data keep the fixed refill (fallback)
                    for member in order:
                        if resources.gauge_fallback(member):
                            gauge.set_full(member)
                            refilled_members.add(member)
                            member_refills.append((loop_index + 1, member))
            entry = "opener" if previous is None else decision.entry
            if previous is not None:
                swaps.append(_SwapRun(len(swaps), t_us, previous, cid, decision.out_element or elements.get(previous, ""),
                                      decision.in_element or elements.get(cid, ""), float(decision.gauge),
                                      decision.outcome, None))
            if resources is not None:
                refilled = (loop_index == 0 and opening_gauge == "full") or cid in refilled_members
            visit = _VisitRun(vi, loop_index, cid, entry, t_us, t_us, gauge.value(cid), refilled=refilled)
            if resources is not None:
                visit.energy_in = resources.snapshot(cid, t_us)
                gained_in = resources.gained(cid)
                raw_in, events_in = resources.raw_gain(cid), resources.event_total(cid)
                approved = None if resources.has_record(cid) else _approved_steps(cid)
            skipped_seqs: set[int] = set()   # steps skipped by the resource check in this visit
            form_skipped = False             # the step that starts the member's form was skipped
            qte_rows: list[dict] = []
            rule = FORMS.get(cid)
            form: _FormRun | None = None
            plan = _visit_plan(cid, entry, NORMAL_ENTRY)
            group_steps: dict[int, list[dict]] = defaultdict(list)
            if rule and rule.get("policy") == "size":
                for st, md in plan:
                    if md == "run" and st.get("group") is not None and st.get("seq") in (rule.get("groups") or {}):
                        group_steps[int(st["group"])].append(st)
            approved_groups = (len(group_steps) if rule and rule.get("policy") == "size"
                               else len([1 for st, md in plan if rule and md == "run"
                                         and st.get("seq") in rule.get("body_seqs", ())]))
            tail_step = next((st for st, md in plan if rule and md == "run" and st.get("seq") == rule.get("tail_seq")),
                             None)
            tail_lens = [action_len(tuple(a)) for a in (tail_step.get("combo") or ())] if tail_step else []

            def run_actions(run: _StepRun, si: int, actions, repeat: int, est_s, form_role: str = "") -> None:
                nonlocal t_us
                done = []
                for _rep in range(repeat):
                    for k, action in enumerate(actions):
                        if form is not None and form_role == "tail" and not form.inside(t_us):
                            form.cut_steps += len(actions) - k   # presses past the window are not made
                            form.mark("cut")
                            break
                        t_us += place(cid, vi, si, run, action, t_us, est_s)
                        done.append(action)
                run.actions = tuple(done)

            for pi, (step, mode) in enumerate(plan):
                ability_id, selector = step.get("ability_id"), step.get("selector")
                repeat = max(1, int(step.get("repeat") or 1))
                role = str(step.get("form_role") or "")
                seq = int(step.get("seq") or 0)
                cls = gate = None
                if resources is not None and mode != "skipped":
                    cls = resources.classify(cid, step, approved)
                    actions0 = [tuple(a) for a in (step.get("combo") or ((ability_id, selector),))]
                    runnable0 = bool(step.get("sim")) and all(a in by_key for a in actions0)
                    if runnable0:
                        cut = ((cls.requires_seq is not None and cls.requires_seq in skipped_seqs)
                               or (form_skipped and role and form is None))
                        if cut:     # the form (or the paid ultimate this free one follows) did not happen
                            run = _StepRun(seq, str(step.get("slot") or "other"), ability_id, selector, t_us, t_us,
                                           "form_cut", form_role=role, note="form_not_entered")
                            visit.steps.append(run)
                            skipped_seqs.add(seq)
                            continue
                        gate = resources.gate(cid, cls, t_us)
                        blocked_note, blocked_for = "", None
                        if swap_mode and resources.short_wait(gate):  # < 0.3 s of cooldown left: wait, cast (10-18)
                            blocked_note = "short_wait"
                        elif swap_mode and (gate.action in ("energy_short", "cd_skip") or gate.wait_us > 0):
                            how, wait_pc, other = _not_ready_choice(resources, cid, gate, t_us, order, approved_of)
                            if how == "run":            # every member blocked and this one is ready first: it waits
                                blocked_note, blocked_for = "all_blocked", cid
                            elif how in ("swap", "wait_swap"):
                                if how == "wait_swap":  # every member blocked: wait for the earliest ready one
                                    end = resources.wall_after(t_us, wait_pc)
                                    visit.steps.append(_StepRun(seq, "wait", None, None, t_us, end, "cd_wait",
                                                                cd_kind=cls.cd_kind or "", remaining_us=int(wait_pc),
                                                                note="all_blocked", wait_for=other))
                                    resources.waited(cid, dataclasses.replace(gate, wait_us=end - t_us,
                                                                              wait_kind="blocked_wait"))
                                    resources.all_blocked_wait(cid, loop_index, seq, end - t_us, other)
                                    visit.waited_us += end - t_us
                                    waited_total += end - t_us
                                    t_us = end
                                left = resources.peek_remaining(cid, cls, t_us)
                                reason = _swap_reason(gate)
                                if how == "wait_swap" and reason == "cd" and resources.short_left(left):
                                    # after waiting for the earliest ready member less than the threshold is left:
                                    # the rest is waited out and the skill cast, no swap (2026-10-18)
                                    gate = dataclasses.replace(gate, action="run", wait_kind="cd_wait",
                                                               wait_us=resources.wall_after(t_us, int(left)) - t_us,
                                                               remaining_us=int(left))
                                    blocked_note = "short_wait"
                                else:
                                    dropped = sum(1 for _st, md in plan[pi + 1:] if md == "run")
                                    for st, md in plan[pi + 1:]:    # ultimates not reached: planned, not cast (F1)
                                        acts = [tuple(a) for a in (st.get("combo")
                                                                   or ((st.get("ability_id"), st.get("selector")),))]
                                        if (md == "run" and st.get("sim") and all(a in by_key for a in acts)
                                                and resources.classify(cid, st, approved).cost_ref == "q_cost"):
                                            resources.dropped_q(cid)
                                    run = _StepRun(seq, str(step.get("slot") or "other"), ability_id, selector, t_us,
                                                   t_us, "swap_out", form_role=role, cd_kind=cls.cd_kind or "",
                                                   energy_before=gate.energy_before, cost=gate.cost,
                                                   remaining_us=int(left or 0), note=reason, dropped=dropped)
                                    run.cd_s, run.cd_conf, run.cd_source = resources.cd_info(cid, cls.cd_kind)
                                    visit.steps.append(run)
                                    resources.early_swap(cid, loop_index, seq, cls.cd_kind, reason, left, dropped)
                                    visit.early_swap = (seq, cls.cd_kind or "", None if left is None
                                                        else round(int(left) / 1e6, 3), reason, dropped)
                                    break       # the rest of this visit is not run; the next member enters
                        if gate.action in ("energy_short", "cd_skip"):
                            run = _StepRun(seq, str(step.get("slot") or "other"), ability_id, selector, t_us, t_us,
                                           gate.action, form_role=role, cd_kind=cls.cd_kind or "",
                                           energy_before=gate.energy_before, cost=gate.cost,
                                           remaining_us=int(gate.remaining_us), note=gate.reason)
                            visit.steps.append(run)
                            resources.skipped(cid, gate, loop_index)
                            skipped_seqs.add(seq)
                            if rule and (ability_id, selector) == tuple(rule["start"][:2]):
                                form_skipped = True
                            continue
                        if gate.wait_us > 0:
                            wait = _StepRun(seq, "wait", None, None, t_us, t_us + int(gate.wait_us), gate.wait_kind,
                                            cd_kind=cls.cd_kind or "", remaining_us=int(gate.remaining_us),
                                            energy_before=gate.energy_before, cost=gate.cost, note=blocked_note,
                                            wait_for=blocked_for)
                            visit.steps.append(wait)
                            resources.waited(cid, gate)
                            if blocked_note == "all_blocked":
                                resources.all_blocked_wait(cid, loop_index, seq, int(gate.wait_us), cid)
                            elif blocked_note == "short_wait":      # under the swap threshold (2026-10-18)
                                resources.short_wait_done(cid, loop_index, seq, cls.cd_kind, int(gate.wait_us),
                                                          int(gate.remaining_us))
                            t_us += int(gate.wait_us)
                            visit.waited_us += int(gate.wait_us)
                            waited_total += int(gate.wait_us)
                si = len(visit.steps)
                run = _StepRun(seq, str(step.get("slot") or "other"), ability_id, selector,
                               t_us, t_us, "ok", form_role=role)
                visit.steps.append(run)
                if mode == "skipped":
                    run.status = "skipped_entry"
                    continue
                if step.get("slot") == "entry":
                    used_normal = True
                actions = [tuple(a) for a in (step.get("combo") or ((ability_id, selector),))]
                runnable = bool(step.get("sim")) and all(a in by_key for a in actions)
                if not runnable:
                    # time-only step, or a runnable step without an exact animation match (no fallback):
                    # only the research estimate advances the clock
                    est = step.get("est_s")
                    if step.get("sim"):
                        run.status = "missing_candidate"
                        missing[cid].append(f"{ability_id or step.get('seq')}:{selector or ''}")
                        est = float(est or 0.0)
                        if resources is not None:
                            resources.mark_missing(cid)
                    elif est is None:
                        run.status = "time_default"
                        used_default = True
                        est = DEFAULT_STEP_S
                    else:
                        run.status = "time_only"
                    if resources is not None and not step.get("sim"):
                        if cls is not None and cls.reason == "own_clock_wait":
                            resources.note_interlude(cid)
                        credit = resources.time_only_credit(cid, seq)
                        flush(t_us)
                        if credit:              # the research record names the action: its gauge is credited
                            g0 = float(gauge.value(cid))
                            gauge.gain(cid, credit * repeat)
                            added = float(gauge.value(cid)) - g0      # capped at the gauge cap (review F-D)
                            run.credit = added
                            resources.note_credit(cid, seq, added)
                            run.gauge_gain = added
                        elif resources.partial_time_only(cid, seq):
                            resources.note_partial(cid, seq)
                        run.gauge_after = float(gauge.value(cid))
                    t_us += int(round(float(est) * repeat * 1_000_000))
                    run.end_us = t_us
                    continue
                # ── form window rules (before the step runs) ──
                if form is not None and not form.closed and role:
                    policy = rule.get("policy")
                    group = step.get("group")
                    if policy == "size" and role == "body" and group is not None:
                        g = int(group)
                        if g not in form.decided:
                            need = sum(action_len(tuple(a)) * max(1, int(s.get("repeat") or 1))
                                       for s in group_steps.get(g, ()) for a in (s.get("combo") or ()))
                            presses = (min(int(rule.get("tail_max") or 0), (len(form.kept) + 1)
                                           * int(rule.get("tail_per_group") or 0)) if tail_lens else 0)
                            need += sum(tail_lens[:max(0, presses - 1)])
                            keep = not form.kept or form.elapsed(t_us) + need < form.duration_us
                            form.decided[g] = keep
                            if keep:
                                form.kept.append(g)
                        if not form.decided[g]:
                            run.status = "form_cut"
                            form.cut_steps += 1
                            form.mark("cut")
                            continue
                    elif policy == "size" and role == "terminal":
                        if not form.inside(t_us):
                            run.status = "form_cut"
                            form.cut_steps += 1
                            form.mark("cut")
                            continue
                    elif policy == "size" and role == "tail":
                        allowed = min(int(rule.get("tail_max") or 0), len(form.kept) * int(rule.get("tail_per_group") or 0))
                        if allowed < len(actions):
                            form.cut_steps += len(actions) - allowed
                            form.mark("cut")
                            actions = actions[:allowed]
                        if not actions or not form.inside(t_us):
                            run.status = "form_cut"
                            form.cut_steps += len(actions)
                            form.mark("cut")
                            continue
                    elif role == "exit" or (policy == "window" and role == "window"):
                        e = form.elapsed(t_us)
                        from src.services import global_live_overlay   # Akane stage 2 from 4 s (CN release)

                        lo, hi = (global_live_overlay.form_window(cid, rule.get("code"), rule.get("exit_window_s")
                                                                  or rule.get("window_s"),
                                                                  getattr(static, "database_path", None))
                                  or (0.0, rule["duration_s"]))
                        form.exit_us = e
                        form.window = (float(lo), float(hi))
                        if not (_us(lo) <= e <= _us(hi)):
                            form.mark("window_missed")
                    elif policy == "warn" and role == "body" and not form.inside(t_us):
                        form.mark("overrun")

                if gate is not None:            # the step runs: spend energy / clock, start its cooldown (F11)
                    run.cd_kind = cls.cd_kind or ""
                    run.cost = gate.cost
                    run.note = gate.note or (gate.reason if gate.reason == "extra_e" else "")
                    run.remaining_us = int(gate.remaining_us) if gate.note == "cd_not_ready" else 0
                    run.energy_before = resources.begin(cid, cls, t_us, gate, step)
                    if run.energy_before is None:
                        run.energy_before = resources.snapshot(cid, t_us)
                    run.cd_s, run.cd_conf, run.cd_source = resources.cd_info(cid, cls.cd_kind)
                    raw0, events0 = resources.raw_gain(cid), resources.event_total(cid)
                    flush(t_us)
                    gauge0 = float(gauge.value(cid))
                run_actions(run, si, actions, repeat, step.get("est_s"), role)
                run.end_us = t_us
                flush(t_us)                     # the step's hits up to its end (no-op at the legacy level)
                if gate is not None:
                    run.events = tuple(resources.after(cid, cls, step, t_us, presses=len(run.actions) or 1))
                    if step.get("slot") == "basic":
                        resources.note_basic(cid)
                    run.energy_after = resources.snapshot(cid, t_us)
                if gauge.apply_step(cid, step):
                    used_gauge_set = True
                if gate is not None:            # per-step energy / gauge trace (resource levels)
                    run.energy_raw = resources.raw_gain(cid) - raw0
                    run.energy_events = resources.event_total(cid) - events0
                    run.gauge_after = float(gauge.value(cid))
                    run.gauge_gain = run.gauge_after - gauge0
                if entry == "support_skill" and step.get("entry_only"):
                    qte_rows = sorted(run.rows, key=lambda r: r["relative_time_us"])

                # ── form bookkeeping (after the step ran) ──
                if rule and form is None and (ability_id, selector) == tuple(rule["start"][:2]):
                    form = _FormRun(rule, run.start_us + _us(rule["start"][2]), stops, approved_groups)
                    continue
                if form is None or form.closed or not role:
                    continue
                policy = rule.get("policy")
                if role in ("body", "terminal", "tail", "window", "fill"):
                    form.last_us = t_us
                    if role in ("body", "window"):
                        form.body_run += 1
                if role == "exit":
                    form.closed = True
                elif policy in ("check", "warn") and role == "body":
                    over = form.elapsed(t_us) - form.duration_us
                    if over > 1000:
                        form.overrun_us = max(form.overrun_us, over)
                        form.mark("overrun")
                elif policy == "size" and role == "after":
                    form.closed = True
                fill = rule.get("fill") if policy == "size" else None
                if fill and role == "body" and run.seq == int(fill["after_seq"]):
                    fill_actions = [tuple(a) for a in fill["actions"]]
                    fill_len = sum(action_len(a) for a in fill_actions)
                    while form.fills < int(fill["max"]) and form.elapsed(t_us) + fill_len < form.duration_us:
                        fsi = len(visit.steps)
                        frun = _StepRun(run.seq, "basic", fill_actions[0][0], fill_actions[0][1], t_us, t_us, "ok",
                                        form_role="fill")
                        visit.steps.append(frun)
                        run_actions(frun, fsi, fill_actions, 1, None, "fill")
                        frun.end_us = t_us
                        form.fills += 1
                        form.last_us = t_us
            if entry == "support_skill":
                for i, row in enumerate(qte_rows):
                    row["attack_type"] = support_skill_attack_type(decision.reaction, i == 0)
                first_entry_step = next((s for s in visit.steps if s.status != "skipped_entry"), None)
                t_trigger = (qte_rows[0]["relative_time_us"] if qte_rows
                             else (first_entry_step.start_us if first_entry_step else visit.start_us))
                index = sched.trigger(t_trigger, previous, cid, decision.reaction, visit_index=vi,
                                      source_rows=qte_rows)
                swaps[-1].reaction_index = index
            visit.end_us = t_us
            flush(t_us)
            visit.gauge_out = gauge.value(cid)
            if resources is not None:
                resources.visit_end(cid, t_us)
                visit.energy_out = resources.snapshot(cid, t_us)
                visit.energy_gain = resources.gained(cid) - gained_in
                visit.energy_raw = resources.raw_gain(cid) - raw_in
                visit.energy_events = resources.event_total(cid) - events_in
            if form is not None:
                if rule.get("policy") == "warn":
                    over = form.elapsed(form.last_us) - form.duration_us
                    if over > 1000:
                        form.overrun_us = max(form.overrun_us, over)
                visit.form = form.summary()
            visits.append(visit)
            previous = cid
    flush(None)
    return _Layout(rows, side, visits, swaps, stops, stop_owners, t_us, dict(missing), unknown_stop,
                   used_default, used_gauge_set, used_normal, tuple(refill_loops),
                   {cid: dict(v) for cid, v in form_actions.items()}, tuple(member_refills), resources, waited_total,
                   hit_credited=dict(writer.credited), node_hooks=node_hooks, node_gauge=tuple(writer.node_gauge))


# ── Phase 1b: damage-over-time ticks ──────────────────────────────────────

class _DotState:
    """One target's stack (mirrors battle_dot_stack_state_service._Stack on the active clock)."""

    def __init__(self, duration_us: int, independent: bool) -> None:
        self.duration_us = duration_us
        self.independent = independent
        self.count = 0
        self.expires_at: int | None = None
        self.expiries: list[int] = []

    def alive(self, active_us: int) -> bool:
        if self.independent:
            return any(e > active_us for e in self.expiries)
        return self.count > 0 and self.expires_at is not None and active_us < self.expires_at

    def add(self, amount: int, active_us: int) -> None:
        if self.independent:
            self.expiries = [e for e in self.expiries if e > active_us]
            accepted = min(max(0, DOT_STACK_LIMIT - len(self.expiries)), max(0, amount))
            self.expiries.extend(active_us + self.duration_us for _ in range(accepted))
            return
        if not self.alive(active_us):
            self.count = 0
        self.count = min(DOT_STACK_LIMIT, self.count + max(0, amount))
        if self.count:
            self.expires_at = active_us + self.duration_us

    def refresh(self, active_us: int) -> None:
        if not self.independent and self.alive(active_us):
            self.expires_at = active_us + self.duration_us


def _dot_applications(rows: list[dict], build: dict) -> dict[str, list[tuple[int, str, int]]]:
    """kind -> [(wall_us, op, amount)] from the simulated direct rows (engine application rules)."""
    out: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    ordered = sorted(rows, key=lambda r: r["relative_time_us"])
    venom_hits = [r for r in ordered if r["character_id"] == ZANKOU_ID
                  and "zankou_magicultraskill" in str(r["gameplay_effect_name"]).casefold()]
    burst: list[dict] = []
    for row in venom_hits:     # the final hit of each burst applies 5 venom layers (_burst_final_markers)
        if burst and row["relative_time_us"] - burst[-1]["relative_time_us"] > 2_000_000:
            out["venom"].append((burst[-1]["relative_time_us"], "add", 5))
            burst = []
        burst.append(row)
    if burst:
        out["venom"].append((burst[-1]["relative_time_us"], "add", 5))
    nightmare_ids = {NIGHTMARE_GE.casefold(), NIGHTMARE_GE_ENHANCED.casefold()}
    for row in ordered:
        cid = row["character_id"]
        ge = str(row["gameplay_effect_name"]).casefold()
        ability = str(row.get("ability_name") or "").casefold()
        t = row["relative_time_us"]
        if cid == ZANKOU_ID:       # _is_erosion_application / _is_zankou_magic_melee
            if "zankou_magicmelee" in ge or "zankou_magicbranch" in ge:
                out["erosion"].append((t, "add", 1))
                if "zankou_magicmelee" in ge:
                    out["venom"].append((t, "refresh", 0))
            elif ge in ("ge_player_zankou_skill1_1_damage", "ge_player_zankou_skill2_1_damage"):
                out["erosion"].append((t, "add", 5))
        elif cid == LACRIMOSA_ID:  # _is_nightmare_application: direct, not QTE / steal / the tick itself
            if ge in NIGHTMARE_SETTLE_GES:
                out["nightmare_settle"].append((t, "settle", 0))
            if (ge not in nightmare_ids and "qte" not in ge and "qte" not in ability and "steal" not in ge
                    and ability != "ga_lacrimosa_steal"):
                out["nightmare"].append((t, "add", 1))
    for kind in out:
        out[kind].sort(key=lambda e: e[0])
    return dict(out)


def _nightmare_setup(con: sqlite3.Connection, build: dict) -> tuple[str, float, bool]:
    """(tick effect, layer duration s, A3 early settlement) for Lacrimosa from the selected awakenings."""
    profile = next((c.get("profile") or {} for c in build["characters"] if c["character_id"] == LACRIMOSA_ID), {})
    selected = set(profile.get("selected_awaken_effect_ids") or ())
    enhanced_by = {r[0] for r in con.execute(
        "SELECT effect_id FROM character_awaken_effect WHERE character_id=? AND gameplay_effect_ids_json LIKE ?",
        (LACRIMOSA_ID, f'%"{NIGHTMARE_GE_ENHANCED}"%'))}
    ge = NIGHTMARE_GE_ENHANCED if selected & enhanced_by else NIGHTMARE_GE
    try:
        from src.services.battle_dot_stack_state_service import _nightmare_duration_seconds   # engine's own rule
        duration = float(_nightmare_duration_seconds(build))
    except Exception:  # pragma: no cover - keep the engine's documented values
        duration = 6.0 if "Effect4" in selected else 3.0
    return ge, duration, "Effect3" in selected


def _dot_tick_rows(applications, static, names, to_active, to_wall, end_us, nightmare) -> list[dict]:
    """Tick rows every DOT_TICK_S of active time from 1 s after a state starts, while it lives."""
    nightmare_ge, nightmare_s, early_settlement = nightmare
    settle_windows = [(to_active(t), to_active(t) + NIGHTMARE_SETTLE_WINDOW_US)
                      for t, _op, _n in applications.get("nightmare_settle", ())] if early_settlement else []
    kinds = {
        "erosion": (ZANKOU_ID, EROSION_GE, _DotState(int(ZANKOU_DOT_DURATION_S * 1e6), False)),
        "venom": (ZANKOU_ID, VENOM_GE, _DotState(int(ZANKOU_DOT_DURATION_S * 1e6), False)),
        "nightmare": (LACRIMOSA_ID, nightmare_ge, _DotState(int(nightmare_s * 1e6), True)),
    }
    period = int(DOT_TICK_S * 1_000_000)
    end_active = to_active(end_us)
    out: list[dict] = []
    for kind, events in applications.items():
        if kind not in kinds:
            continue
        owner, ge, state = kinds[kind]
        if owner not in names:
            continue
        dmg = static.get_skill_damage(ge)
        if not dmg:
            continue
        attribute = str(dmg.get("damage_type") or "").lower()
        ability = dmg.get("ability_id")
        ticks: list[int] = []
        next_tick: int | None = None
        for wall_us, op, amount in list(events) + [(None, "end", 0)]:
            a = end_active if wall_us is None else to_active(wall_us)
            while next_tick is not None and next_tick <= a and next_tick <= end_active:
                if state.alive(next_tick):
                    ticks.append(next_tick)
                    next_tick += period
                else:
                    next_tick = None
            if wall_us is None:
                break
            if op == "add":
                state.add(amount, a)
            else:
                state.refresh(a)
            if next_tick is None and state.alive(a):
                next_tick = a + period
        for tick in ticks:
            if kind == "nightmare" and any(lo <= tick <= hi for lo, hi in settle_windows):
                continue
            wall = to_wall(tick)
            if wall > end_us:
                continue
            row = _row(owner, names[owner], wall, ability, ge, attribute)
            row["damage_component"] = _DOT_LABELS[kind]
            out.append(row)
    return out


# ── simulation: engine ────────────────────────────────────────────────────

def _number(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda h: h["relative_time_us"])
    for i, h in enumerate(rows, 1):
        h["sequence_order"] = i
        h["sequence_text"] = str(i)
    return rows


def _stop_evidence(stops: list[tuple[int, int]], end_us: int = 0) -> list[dict]:
    rows = [{"pause_type_mask": TIME_STOP_PAUSE_MASK,
             "raw_interval": {"start_offset_seconds": s / 1e6, "end_offset_seconds": e / 1e6}}
            for s, e in stops]
    if not rows:               # no measured stop: block the engine's inferred Q-action stops (see NO_STOP_PAUSE_MASK)
        start = int(end_us) + NO_STOP_AFTER_END_US
        rows.append({"pause_type_mask": NO_STOP_PAUSE_MASK,
                     "raw_interval": {"start_offset_seconds": start / 1e6, "end_offset_seconds": (start + 1000) / 1e6}})
    return rows


def _form_configs(static, team_ids) -> dict:
    """Zankou / Shinku form buff configs, passed to the engine exactly as the battle report does."""
    configs: dict = {}
    if ZANKOU_ID in team_ids:
        from src.services.battle_zankou_form_buff_service import BattleZankouFormBuffService

        configs["zankou_form_config"] = BattleZankouFormBuffService.load_config(static)
    if 1076 in team_ids:
        from src.services.battle_shinku_rage_buff_service import BattleShinkuRageBuffService

        configs["shinku_rage_config"] = BattleShinkuRageBuffService.load_config(static)
    return configs


def _run_engine(static, build, candidates, buff_rules, hits: list[dict], stops: list[tuple[int, int]],
                ordinary_scorch: dict[str, str], form_configs: dict | None = None, *,
                target_condition: dict | None = None, buff_edit=None, fork_corrections=None, node_hooks=None):
    """``target_condition`` (None = DEFAULT_TARGET) and ``buff_edit`` (a function applied to the analysis right
    after buff inference: disabled / manual buffs) are the custom-cycle mode's options.  ``fork_corrections``
    (team_fork_corrections.ForkCorrections) runs first, so the custom mode can switch corrected buffs off too;
    ``node_hooks`` (awakening_node_rules.RunHooks) right after it (intervals) and after the Scorch patch (evidence)."""
    from src.services.battle_counterfactual_analysis_service import BattleCounterfactualAnalysisService
    from src.services.battle_hit_replay_service import BattleHitReplayService
    from src.services.battle_skill_damage_evidence_service import BattleSkillDamageEvidenceService
    from src.services.team_cycle_reactions import patch_ordinary_scorch_evidence

    analysis = BattleCounterfactualAnalysisService.analyze(
        battle_record_id=0,
        evidence={"axis_complete": True, "hits": hits,
                  "time_stop_intervals": _stop_evidence(stops, max((h["relative_time_us"] for h in hits), default=0)),
                  "contract_version": 5},
        build=build, capability_level="full", animation_candidates=candidates, buff_rules=buff_rules,
        target_condition=target_condition or DEFAULT_TARGET, infer_buffs=True, **(form_configs or {}),
    )
    if fork_corrections is not None:
        analysis = fork_corrections(analysis)
    if node_hooks is not None:          # awakening node rules: supplement / replace / fill buff intervals
        analysis = node_hooks.intervals(analysis)
    if buff_edit is not None:
        analysis = buff_edit(analysis)
    evidence = BattleSkillDamageEvidenceService.load(static, analysis, build)
    evidence = patch_ordinary_scorch_evidence(evidence, ordinary_scorch)
    if node_hooks is not None:          # awakening node rules: skill coefficients of named damage GEs
        evidence = node_hooks.evidence(evidence)
    replays = BattleHitReplayService.replay(analysis, evidence, apply_observed_refinements=False)
    return analysis, replays


def _owners_differ(sched, owners: dict) -> bool:
    incoming = {index: in_cid for index, _t, _zh, _out, in_cid in sched.triggers}
    return any(choice.character_id != incoming.get(index) for index, choice in owners.items()
               if sched.needs_owner(index))


def _adopt_numbering(old_rows: list[dict], new_rows: list[dict]) -> bool:
    """Carry sequence numbers over when the owner pass produced identical rows (no re-run needed)."""
    if len(old_rows) != len(new_rows):
        return False
    for old, new in zip(old_rows, new_rows):
        if (old["relative_time_us"], old["gameplay_effect_name"], old["character_id"]) != (
                new["relative_time_us"], new["gameplay_effect_name"], new["character_id"]):
            return False
    for old, new in zip(old_rows, new_rows):
        new["sequence_order"] = old["sequence_order"]
        new["sequence_text"] = old["sequence_text"]
    return True


@dataclass
class _Ctx:
    """Everything a run of one visit order needs (built once per simulate_team call)."""
    static: Any
    team_ids: list
    characters: list
    build: dict
    rules: Any
    nightmare: tuple
    ability_names: dict
    elements: dict
    names: dict
    candidates: tuple               # engine (bound animation candidates)
    by_key: dict                    # layout (bound + form actions)
    buff_rules: Any
    form_configs: dict
    loops: int
    gauge_rule: str
    opening_gauge: str
    target_condition: Any = None    # None = DEFAULT_TARGET (custom-cycle mode: the enemy options)
    buff_edit: Any = None           # analysis -> analysis after buff inference (custom-cycle mode)
    fork_corrections: Any = None    # team_fork_corrections.ForkCorrections (applied before buff_edit)
    policy: Any = None              # team_resources.ResourcePolicy of the reviewed layout (None = legacy level)
    node_rules: Any = None          # awakening_node_rules.Prepared: the selected-node rules of the members
    charge_eff: Any = None          # {cid: build charge efficiency} once an engine run has shown it (resources)


@dataclass
class _Run:
    order: tuple
    layout: _Layout
    dot_rows: list
    reaction_rows: list
    analysis: Any
    replays: Any
    sched: Any
    to_active: Any
    corrections: Any = None         # team_fork_corrections.CorrectionReport of the engine run kept
    node_hooks: Any = None          # awakening_node_rules.RunHooks of the engine run kept (post increments, notes)


def _new_axis(ctx: _Ctx):
    from src.services import team_cycle_reactions as tcr

    stops: list[tuple[int, int]] = []
    to_active, to_wall = tcr.make_clock(stops)
    gauge = tcr.CycleGauge(ctx.gauge_rule, ctx.opening_gauge, ctx.team_ids, ctx.elements, rules=ctx.rules)
    sched = tcr.ReactionScheduler(ctx.rules, ctx.team_ids, ctx.build, to_active, to_wall, elements=ctx.elements,
                                  names=ctx.names)
    return stops, to_active, to_wall, gauge, sched


def _new_resources(ctx: _Ctx, stops: list):
    """The ResourceState of one reviewed layout (None at the legacy level: the old rule, bit for bit)."""
    policy = ctx.policy
    if policy is None or getattr(policy, "legacy", True):
        return None
    from src.services import team_awakening
    from src.services.team_resources import ResourceState

    # A4: the members' node sets (rules store the node number n = Effect n, team_resources.ResourceState.unlocked)
    awakening = team_awakening.selections_of(ctx.characters)
    rules = ctx.node_rules
    extra = {}
    if rules is not None and not rules.empty:      # awakening node rules: resource rows and hooks
        extra = {"extra_rules": {c: rules.resource_rules(c) for c in ctx.team_ids},
                 "extra_events": {c: rules.resource_events(c) for c in ctx.team_ids},
                 "hooks": rules.resource_hooks()}
    state = ResourceState(ctx.team_ids, policy=policy, stops=stops, solo=len(ctx.team_ids) < 2, awakening=awakening,
                          charge_eff=ctx.charge_eff, **extra)
    state.target = ctx.target_condition or DEFAULT_TARGET     # resource hooks / e_resets_q see the enemy options
    from src.services import global_live_overlay      # explanation codes the Global live overlay replaces

    state.code_map = global_live_overlay.code_map(getattr(ctx.static, "database_path", None))
    return state


def _layout_hooks(ctx: _Ctx, mode: str = "approved"):
    """Per-layout awakening node hooks (gate / placed / free_support), None when no such rule is active."""
    rules = getattr(ctx, "node_rules", None)
    hooks = None if rules is None else rules.layout(mode)
    if hooks is not None:               # the gate sees the run's enemy (custom mode sets it before the layout)
        hooks.target_condition = ctx.target_condition or DEFAULT_TARGET
    return hooks


def _dry_layout(ctx: _Ctx, order) -> tuple[_Layout, Any, Any]:
    """Layout only (no engine): the planner's cheap first pass."""
    stops, to_active, _to_wall, gauge, sched = _new_axis(ctx)
    layout = _layout_axis(ctx.static, order, ctx.loops, ctx.by_key, gauge, sched, ctx.names, ctx.elements, stops,
                          opening_gauge=ctx.opening_gauge, resources=_new_resources(ctx, stops),
                          node_hooks=_layout_hooks(ctx))
    sched.set_horizon(layout.end_us)
    return layout, sched, to_active


def _run_order(ctx: _Ctx, order) -> _Run:
    return _run_axis(ctx, lambda stops, gauge, sched: _layout_axis(
        ctx.static, order, ctx.loops, ctx.by_key, gauge, sched, ctx.names, ctx.elements, stops,
        opening_gauge=ctx.opening_gauge, resources=_new_resources(ctx, stops), node_hooks=_layout_hooks(ctx)), order)


def _run_axis(ctx: _Ctx, lay, order=(), _regated: bool = False) -> _Run:
    """One full run: ``lay(stops, gauge, sched)`` lays the hits out (the approved rotations, or a custom cycle),
    then the damage-over-time ticks, the reaction rows, the engine and the owner pass."""
    stops, to_active, to_wall, gauge, sched = _new_axis(ctx)
    # the layout appends measured stops to the clock's own list (make_clock re-reads it lazily)
    layout = lay(stops, gauge, sched)
    sched.set_horizon(layout.end_us)
    applications = _dot_applications(layout.rows, ctx.build)
    dot_rows = _dot_tick_rows(applications, ctx.static, ctx.names, to_active, to_wall, layout.end_us, ctx.nightmare)
    node_hooks = _run_hooks(ctx, layout, to_active, to_wall, sched, applications)
    extra_rows: list = []
    tick_rows = dot_rows
    if node_hooks is not None:          # awakening node rules: DoT rows (dot_rows) and extra hit rows (rows)
        layout.run_hooks = node_hooks   # _collect reads the post hooks from the layout (its call shape is unchanged)
        dot_rows = node_hooks.dot_rows(dot_rows)
        extra_rows, extra_ticks = node_hooks.rows()
        tick_rows = dot_rows + extra_ticks
    # Zankou's Scorch waits for a DoT tick and every DoT tick refreshes it (GA_Zankou_Passive1)
    sched.set_dot_ticks(row["relative_time_us"] for row in tick_rows)
    if extra_rows:                      # credited like DoT ticks: the owner's latest visit (_collect)
        dot_rows = dot_rows + extra_rows
    reaction_rows = sched.rows("incoming")
    hits = _number(layout.rows + dot_rows + reaction_rows)
    options = {"target_condition": ctx.target_condition, "buff_edit": ctx.buff_edit,
               "fork_corrections": ctx.fork_corrections}
    if node_hooks is not None:
        options["node_hooks"] = node_hooks
        node_hooks.info.hits = hits
    analysis, replays = _run_engine(ctx.static, ctx.build, ctx.candidates, ctx.buff_rules, hits, stops,
                                    sched.ordinary_scorch_attributes(), ctx.form_configs, **options)
    from src.services import team_cycle_reactions as tcr

    owners = tcr.choose_owners(analysis, None, sched, rules=ctx.rules)
    if owners:
        rerun = _owners_differ(sched, owners)
        new_rows = sched.rows(owners)
        if rerun or not _adopt_numbering(reaction_rows, new_rows):
            hits = _number(layout.rows + dot_rows + new_rows)
            if node_hooks is not None:
                node_hooks.info.hits = hits
            analysis, replays = _run_engine(ctx.static, ctx.build, ctx.candidates, ctx.buff_rules, hits, stops,
                                            sched.ordinary_scorch_attributes(), ctx.form_configs, **options)
        reaction_rows = new_rows
    resources = getattr(layout, "resources", None)
    if resources is not None:
        # the build's whole-fight charge efficiency (arc / cartridge) is known only now: the energy gained follows
        # it at once; a member whose ultimate a pool gates is laid out again with it (design §4.4)
        from src.services.team_resources import charge_eff_from_analysis

        eff = charge_eff_from_analysis(analysis, ctx.team_ids, START_US, layout.end_us)
        regate = resources.set_build_eff(eff)
        ctx.charge_eff = eff
        if regate and not _regated:
            return _run_axis(ctx, lay, order, _regated=True)
    report = getattr(ctx.fork_corrections, "last_report", None) if ctx.fork_corrections is not None else None
    return _Run(tuple(order), layout, dot_rows, reaction_rows, analysis, replays, sched, to_active, report,
                node_hooks=node_hooks)


def _run_hooks(ctx: _Ctx, layout, to_active, to_wall, sched, applications):
    """awakening_node_rules.RunHooks of one engine run (None when no run-level rule is active)."""
    rules = getattr(ctx, "node_rules", None)
    if rules is None or not rules.has("dot_rows", "rows", "intervals", "evidence", "post"):
        return None
    from src.services.awakening_node_rules.core import RunInfo

    hooks = getattr(layout, "node_hooks", None)
    return rules.run(RunInfo(ctx, layout, to_active, to_wall, sched, applications,
                             tuple(hooks.placed) if hooks is not None else ()))


# ── visit-order planner (order_mode "plan") ───────────────────────────────

def _carry(team_ids) -> tuple[int | None, str]:
    """The member the order is planned around: the form (transformation) damage dealer with role main and the
    longest field time; without one the main with the longest field time; else the longest field time."""
    from src.services.team_rotation_data import CHARACTERS

    def field_time(cid: int) -> float:
        return float((CHARACTERS.get(cid) or {}).get("field_time_s") or 0.0)

    def role(cid: int) -> str:
        return str((CHARACTERS.get(cid) or {}).get("role") or "")

    if not team_ids:
        return None, "field_time"
    forms = _form_members(team_ids)
    ranked = sorted(team_ids, key=lambda c: (-field_time(c), list(team_ids).index(c)))
    for cid in ranked:
        if cid in forms and role(cid) == "main":
            return cid, "form"
    for cid in ranked:
        if role(cid) == "main":
            return cid, "main"
    return ranked[0], "field_time"


def _plan_candidates(team_ids, elements, carry) -> list[tuple[int, ...]]:
    """Every order with the most adjacent pairs around the loop, once per cycle class, carry first and last."""
    team = tuple(team_ids)
    if len(team) < 2 or carry is None:
        return [team]
    perms = list(itertools.permutations(team))
    best = max(_cyclic_adjacency(o, elements) for o in perms)
    out: list[tuple[int, ...]] = []
    seen = set()
    for o in perms:
        if _cyclic_adjacency(o, elements) != best:
            continue
        k = o.index(carry)
        first = o[k:] + o[:k]
        if first in seen:
            continue
        seen.add(first)
        for cand in (first, first[1:] + first[:1]):
            if cand not in out:
                out.append(cand)
    return out


def _union_overlap(segment: tuple[int, int], windows: list[tuple[int, int]]) -> int:
    lo, hi = segment
    cut = sorted((max(lo, a), min(hi, b)) for a, b in windows if min(hi, b) > max(lo, a))
    total, cur_a, cur_b = 0, None, None
    for a, b in cut:
        if cur_b is None or a > cur_b:
            if cur_b is not None:
                total += cur_b - cur_a
            cur_a, cur_b = a, b
        else:
            cur_b = max(cur_b, b)
    if cur_b is not None:
        total += cur_b - cur_a
    return total


def _coverage_s(layout: _Layout, sched, carry: int, to_active, elements: dict) -> tuple[float, float]:
    """(covered, total) seconds of the carry's form windows (its whole visit without a form): covered = under the
    team buffs the planner counts (team_form_actions.TEAM_BUFFS) and the 覆纹 / 浸染 windows whose scope holds the
    carry's element."""
    from src.services.team_form_actions import TEAM_BUFFS

    segments = []
    for v in layout.visits:
        if v.character_id != carry:
            continue
        if v.form and v.form.get("start_us") is not None:
            a = to_active(v.form["start_us"])
            segments.append((a, a + _us(v.form["used_s"])))
        else:
            segments.append((to_active(v.start_us), to_active(v.end_us)))
    windows = []
    for v in layout.visits:
        rows = TEAM_BUFFS.get(v.character_id) or ()
        if v.character_id == carry or not rows:
            continue
        for ab, sel, offset, duration, _src in rows:
            for s in v.steps:
                if (s.ability_id, s.selector) == (ab, sel) and s.status == "ok":
                    t0 = s.end_us if offset is None else s.start_us + _us(offset)
                    a = to_active(t0)
                    windows.append((a, a + _us(duration)))
    element = elements.get(carry, "")
    for w in sched.windows():
        if element in tuple(w.scope):
            windows.append((w.start_active_us, w.end_active_us))
    covered = sum(_union_overlap(seg, windows) for seg in segments) / 1e6
    return covered, sum(b - a for a, b in segments) / 1e6


def _plan_order(ctx: _Ctx, collect) -> tuple[_Run, Any, Any]:
    """Stage 1: rank the candidate orders by a layout pass; stage 2: simulate the best PLAN_MAX_RUNS and keep
    the highest team DPS (ties: stage-1 rank).  Deterministic.  Returns (chosen run, its result, PlanTrace)."""
    from src.services import team_simulation_explanation as tx

    carry, basis = _carry(ctx.team_ids)
    candidates = _plan_candidates(ctx.team_ids, ctx.elements, carry)
    slot_rank = {p: i for i, p in enumerate(itertools.permutations(ctx.team_ids))}
    scored = []
    for order in candidates:
        layout, sched, to_active = _dry_layout(ctx, order)
        reactions = sum(1 for s in layout.swaps if s.outcome == "reaction")
        loop2 = any(v.loop_index == 1 and v.character_id == carry and v.entry == "support_skill"
                    for v in layout.visits)
        covered, form_s = _coverage_s(layout, sched, carry, to_active, ctx.elements)
        coverage = round(covered, 1)
        first = bool(order) and order[0] == carry
        q_casts = sum(1 for v in layout.visits for s in v.steps if s.slot == "ultimate" and s.status == "ok")
        waited = round(layout.waited_us / 1e6, 2)
        if layout.resources is None:        # legacy level: the old key, unchanged
            key = (-reactions, -coverage, -int(loop2), 0 if first else 1, slot_rank.get(order, 0))
        else:                               # resources break ties after the existing priorities (design J12)
            key = (-reactions, -coverage, -int(loop2), -q_casts, waited, 0 if first else 1, slot_rank.get(order, 0))
        scored.append((key, order, reactions, coverage, loop2, first, round(form_s, 1), q_casts, waited))
    scored.sort(key=lambda r: r[0])
    simulated: dict[tuple, tuple[_Run, Any]] = {}
    for _key, order, *_rest in scored[:PLAN_MAX_RUNS]:
        run = _run_order(ctx, order)
        simulated[order] = (run, collect(run, None))
    best = None
    for rank, (_key, order, *_rest) in enumerate(scored):
        if order in simulated:
            dps = simulated[order][1].dps
            if best is None or dps > best[1] + 1e-9:
                best = (order, dps, rank)
    chosen = best[0]
    trace_rows = []
    resourced = any(r[0] and len(r[0]) == 7 for r in scored)
    for rank, (_key, order, reactions, coverage, loop2, first, form_s, q_casts, waited) in enumerate(scored):
        dps = simulated[order][1].dps if order in simulated else None
        extra = {"q_casts": q_casts, "waited_s": waited} if resourced else {}
        trace_rows.append(tx.PlanCandidate(order=order, adjacency=_cyclic_adjacency(order, ctx.elements),
                                           reactions=reactions, coverage_s=coverage, loop2_support_entry=loop2,
                                           carry_first=first, dps=dps, chosen=order == chosen, rank=rank,
                                           form_s=form_s, **extra))
    chosen_row = next(r for r in trace_rows if r.chosen)
    # reasons follow the data: the fixed "first / last" rationales only where they hold for this team
    best_cover = max((r.coverage_s for r in trace_rows if r.dps is not None), default=0.0)
    carry_trace = simulated[chosen][1].explanation.member(carry)
    carry_dot = bool(carry_trace is not None and carry_trace.dot_hits)
    reasons = [tx.note(tx.PLAN_CARRY if basis == tx.CARRY_FORM else tx.PLAN_CARRY_MAIN, carry)]
    reasons.append(tx.note(tx.PLAN_BEST_DPS, len(simulated)))
    if chosen_row.carry_first:
        reasons.append(tx.note(tx.PLAN_CARRY_FIRST if carry_dot else tx.PLAN_CARRY_FIRST_DPS, carry))
    else:
        full = best_cover > 0 and chosen_row.coverage_s >= best_cover - 0.05
        reasons.append(tx.note(tx.PLAN_CARRY_LAST if full else tx.PLAN_CARRY_LAST_DPS, carry))
    if chosen_row.coverage_s > 0:
        reasons.append(tx.note(tx.PLAN_COVERAGE, chosen_row.coverage_s, chosen_row.form_s))
    if chosen_row.coverage_s + 0.05 < best_cover:
        reasons.append(tx.note(tx.PLAN_COVER_TRADE, chosen_row.coverage_s, best_cover))
    if resourced:
        others = [r.q_casts for r in trace_rows if not r.chosen and r.dps is not None]
        if others and chosen_row.q_casts > max(others):
            reasons.append(tx.note(tx.PLAN_Q_CASTS, chosen_row.q_casts))
    plan = tx.PlanTrace(carry_character_id=carry, carry_basis=basis, candidates=tuple(trace_rows),
                        reasons=tuple(reasons))
    run, result = simulated[chosen]
    return run, result, plan


@contextlib.contextmanager
def _open_session(static_path: Path, user_db_path: Path | None, account_id: str, team_ids: list[int], *,
                  loops: int, gauge_rule: str, opening_gauge: str):
    """The parts of a context that do not depend on the members' choices (reaction rules, ability names, the private
    account copy, the static DAO, animation candidates, form configs), built once.  Yields ``make(specs) -> _Ctx``
    for specs of exactly these members (awakening / arc / refinement / set may differ per call).  Without
    ``user_db_path`` an empty account is created in the temp folder.  The DAO and the account copy live as long as
    the ``with`` block."""
    from src.services.battle_buff_inference_service import BattleBuffInferenceService
    from src.services.battle_build_stat_reconstruction_service import BattleBuildStatReconstructionService
    from src.services.battle_report_persistence_service import BattleReportPersistenceDependencies
    from src.services import awakening_node_rules
    from src.services import team_cycle_reactions as tcr
    from src.services import team_fork_corrections
    from src.storage.sqlite.static_game_data_dao import StaticGameDataDao

    static_path = Path(static_path)
    team_ids = [int(c) for c in team_ids]
    con = sqlite3.connect(_ro_uri(static_path), uri=True)
    try:
        rules = tcr.load_rules(con)
        ability_names = {a: _TAG.sub("", n).strip() for a, n in
                         con.execute("SELECT ability_id, name_zh FROM gameplay_ability_catalog") if n}
    finally:
        con.close()
    elements = {cid: rules.element(cid) for cid in team_ids}

    # the stat reconstruction reads the account database; work on a private copy so nothing can be written back.
    # A copy Windows still holds open while the folder is removed (WinError 145, seen once in ~900 efficiency-table
    # sessions) must not turn a finished calculation into an error: the folder is then left in %TEMP%.
    with tempfile.TemporaryDirectory(prefix="nte_team_sim_", ignore_cleanup_errors=True) as tmp:
        user_copy = Path(tmp) / "user_data.sqlite3"
        if user_db_path is None:
            from src.storage.sqlite.user_data_dao import UserDataDao

            UserDataDao(user_copy, account_id=account_id, account_name=account_id).close()
        elif Path(user_db_path).exists():
            shutil.copy2(user_db_path, user_copy)
        deps = BattleReportPersistenceDependencies(account_id=account_id, user_database_path=user_copy,
                                                   static_database_path=static_path, generation=0)

        with StaticGameDataDao(static_path) as static:
            candidates, by_key = _load_candidates(static, team_ids)
            form_configs = _form_configs(static, team_ids)

            def make(specs: list[MemberSpec]) -> _Ctx:
                if [int(s.character_id) for s in specs] != team_ids:
                    raise ValueError("a session runs the members it was opened for")
                con = sqlite3.connect(_ro_uri(static_path), uri=True)
                try:
                    characters = _build_characters(con, specs)
                    build = {"characters": [{k: v for k, v in c.items() if not k.startswith("_")}
                                            for c in characters]}
                    nightmare = _nightmare_setup(con, build)
                    corrections = team_fork_corrections.prepare(con, characters)
                    node_rules = awakening_node_rules.prepare(con, static, characters)   # selected-node rules
                finally:
                    con.close()
                names = {c["character_id"]: c["observed_name"] for c in characters}
                BattleBuildStatReconstructionService.enrich(build, deps)
                _add_form_skill_levels(static, build)
                buff_rules = BattleBuffInferenceService.load_rules(static, build)
                if node_rules.has("buff_rules"):
                    buff_rules = node_rules.extend_buff_rules(static, build, buff_rules)
                return _Ctx(static=static, team_ids=list(team_ids), characters=characters, build=build, rules=rules,
                            nightmare=nightmare, ability_names=ability_names, elements=elements, names=names,
                            candidates=candidates, by_key=by_key,
                            buff_rules=buff_rules,
                            form_configs=form_configs, loops=loops, gauge_rule=gauge_rule,
                            opening_gauge=opening_gauge, fork_corrections=corrections, node_rules=node_rules)

            yield make


@contextlib.contextmanager
def _open_context(static_path: Path, user_db_path: Path, account_id: str, specs: list[MemberSpec], *,
                  loops: int, gauge_rule: str, opening_gauge: str):
    """Everything a run needs (members from the graduation templates, reaction rules, the enriched build, animation
    candidates, buff rules, form configs, arc corrections) as a _Ctx.  The static DAO and the private copy of the
    account database live as long as the ``with`` block.  Used by simulate_team and by the custom-cycle service."""
    with _open_session(static_path, user_db_path, account_id, [s.character_id for s in specs], loops=loops,
                       gauge_rule=gauge_rule, opening_gauge=opening_gauge) as make:
        yield make(specs)


def _simulated_steps(team_ids, by_key) -> dict[int, int]:
    """Approved steps per member the simulator can run (every action of the step has an animation candidate)."""
    return {cid: sum(1 for s in _approved_steps(cid) if s.get("sim")
                     and all(tuple(a) in by_key for a in (s.get("combo")
                                                            or ((s.get("ability_id"), s.get("selector")),))))
            for cid in team_ids}


def _with_fork_notes(result: TeamResult, report) -> TeamResult:
    """Name the members whose arcs the corrections touched (explanation assumptions; Global rules B2-B4)."""
    if report is None or result is None or result.explanation is None:
        return result
    from src.services import team_simulation_explanation as tx

    notes = []
    supplement = report.characters("b3", "b4")
    if supplement:
        notes.append(tx.note(tx.ASSUME_FORK_SUPPLEMENT, *supplement))
    dedup = report.characters("b2")
    if dedup:
        notes.append(tx.note(tx.ASSUME_FORK_DEDUP, *dedup))
    if notes:
        result.explanation = dataclasses.replace(
            result.explanation, assumptions=tuple(result.explanation.assumptions) + tuple(notes))
    return result


def _with_node_notes(result: TeamResult, run: "_Run | None", ctx: "_Ctx | None") -> TeamResult:
    """Explanation items of the awakening node rules (awakening_node_rules; nothing when no rule / note applies):
    the nodes whose rules ran, expected-value nodes, selected nodes the simulator does not price (measure / not
    computable), the notes the hooks wrote, and limits that a selected node's rules make obsolete dropped."""
    if result is None or result.explanation is None or ctx is None or getattr(ctx, "node_rules", None) is None:
        return result
    from src.services import team_simulation_explanation as tx

    assume, limits, drop = tx.node_rule_notes(ctx.node_rules, run)
    if not assume and not limits and not drop:
        return result
    expl = result.explanation
    kept = tuple(item for item in expl.limits if tx.split_note(item)[0] not in drop)
    result.explanation = dataclasses.replace(expl, assumptions=tuple(expl.assumptions) + tuple(assume),
                                             limits=kept + tuple(limits))
    return result


def resolve_policy(resource_model: str | None = None, resource_policy=None):
    """The team_resources.ResourcePolicy a run uses: an explicit policy, else the level's defaults
    (``None`` = team_resources.DEFAULT_RESOURCE_MODEL)."""
    from src.services import team_resources

    if resource_policy is not None:
        return resource_policy
    return team_resources.policy_for(resource_model)


def simulate_team(static_path: Path, user_db_path: Path, account_id: str, specs: list[MemberSpec], *,
                  order_mode: str = "auto", loops: int = DEFAULT_LOOPS, gauge_rule: str = "game",
                  opening_gauge: str = "full", resource_model: str | None = None,
                  resource_policy=None) -> TeamResult:
    """Simulate the team with approved rotations; Esper Cycle reactions are always computed.

    ``resource_model`` ("legacy" | "data" | "community", None = team_resources.DEFAULT_RESOURCE_MODEL) or an explicit
    ``resource_policy`` (team_resources.ResourcePolicy) decides the ultimate-energy / cooldown checks and the gauge
    refill rule; "legacy" reproduces the old rule bit for bit."""
    policy = resolve_policy(resource_model, resource_policy)
    if order_mode not in ORDER_MODES:
        raise ValueError(f"unknown order_mode {order_mode!r}")
    if gauge_rule not in GAUGE_RULES:
        raise ValueError(f"unknown gauge_rule {gauge_rule!r}")
    if opening_gauge not in OPENING_GAUGES:
        raise ValueError(f"unknown opening_gauge {opening_gauge!r}")
    loops = max(1, min(MAX_LOOPS, int(loops)))
    opening_gauge = _effective_opening(opening_gauge)     # FULL_GAUGE_LOOPS decides loop 1 too
    team_ids = [s.character_id for s in specs]
    for cid in team_ids:
        _approved_steps(cid)                      # fail early for a member without an approved rotation
    with _open_context(static_path, user_db_path, account_id, specs, loops=loops, gauge_rule=gauge_rule,
                       opening_gauge=opening_gauge) as ctx:
        ctx.policy = policy
        characters, elements, ability_names, by_key = ctx.characters, ctx.elements, ctx.ability_names, ctx.by_key
        simulated = _simulated_steps(team_ids, by_key)

        def collect(run: _Run, plan) -> TeamResult:
            return _with_node_notes(_with_fork_notes(
                _collect(team_ids, characters, run.order, loops, order_mode, gauge_rule, opening_gauge,
                         run.layout, run.dot_rows, run.reaction_rows, run.analysis, run.replays, run.sched,
                         run.to_active, elements, ability_names, simulated, plan),
                run.corrections), run, ctx)

        if order_mode == "plan":
            run, _result, plan = _plan_order(ctx, collect)
        else:
            run, plan = _run_order(ctx, _visit_order(team_ids, elements, order_mode)), None
        # collected last for the chosen order (callers that wrap _collect see the run that is returned)
        return collect(run, plan)


@dataclass
class SoloRun:
    """One ``solo_session`` run: ``result`` is what simulate_team returns for this one member."""
    spec: MemberSpec
    result: TeamResult
    run: _Run
    seconds: float = 0.0

    @property
    def total_damage(self) -> float:
        return self.result.total_damage

    @property
    def end_us(self) -> int:
        return int(self.run.layout.end_us)

    @property
    def corrections(self):
        return self.run.corrections


@contextlib.contextmanager
def solo_session(static_path: Path, character_id: int, *, loops: int = DEFAULT_LOOPS, user_db_path: Path | None = None,
                 account_id: str = "solo_session", gauge_rule: str = "game", opening_gauge: str = "full",
                 resource_model: str | None = None, resource_policy=None):
    """One member, many arc / refinement / awakening / set choices on one shared context (the arc efficiency table).
    Awakening specs follow ``MemberSpec``: ``awakening_effects`` = any node set (level = max(level, count); a level
    above the count leaves slots open, the efficiency table's resonance-only variants), a level alone = Effect1..level.

    Yields ``run(spec) -> SoloRun``.  Every run gives exactly ``simulate_team(static_path, account, account_id, [spec],
    loops=loops)`` (order "auto", one member: first visit "opener", no swap, no reaction).  Without ``user_db_path``
    an empty account is created in the session's temp folder (a one-member result does not depend on the account).
    One session per thread."""
    if gauge_rule not in GAUGE_RULES:
        raise ValueError(f"unknown gauge_rule {gauge_rule!r}")
    if opening_gauge not in OPENING_GAUGES:
        raise ValueError(f"unknown opening_gauge {opening_gauge!r}")
    loops = max(1, min(MAX_LOOPS, int(loops)))
    opening_gauge = _effective_opening(opening_gauge)
    policy = resolve_policy(resource_model, resource_policy)
    cid = int(character_id)
    _approved_steps(cid)
    with _open_session(static_path, user_db_path, account_id, [cid], loops=loops, gauge_rule=gauge_rule,
                       opening_gauge=opening_gauge) as make:

        def run(spec: MemberSpec) -> SoloRun:
            if int(spec.character_id) != cid:
                raise ValueError(f"this session runs {cid}, not {spec.character_id}")
            started = time.perf_counter()
            ctx = make([spec])
            ctx.policy = policy
            order = _visit_order([cid], ctx.elements, "auto")
            done = _run_order(ctx, order)
            result = _with_node_notes(_with_fork_notes(
                _collect([cid], ctx.characters, done.order, loops, "auto", gauge_rule, opening_gauge, done.layout,
                         done.dot_rows, done.reaction_rows, done.analysis, done.replays, done.sched, done.to_active,
                         ctx.elements, ctx.ability_names, _simulated_steps([cid], ctx.by_key), None),
                done.corrections), done, ctx)
            return SoloRun(spec, result, done, time.perf_counter() - started)

        yield run


# ── simulation: results and explanation ───────────────────────────────────

def _seconds(us: int) -> float:
    return (int(us) - START_US) / 1e6


def buff_key(interval) -> str:
    """Stable id of an inferred buff (same across runs and languages): its source member and effect."""
    return f"{interval.source_character_id}|{interval.source_effect_definition_id or interval.buff_asset_path}"


def _collect(team_ids, characters, order, loops, order_mode, gauge_rule, opening_gauge, layout, dot_rows,
             reaction_rows, analysis, replays, sched, to_active, elements, ability_names, simulated,
             plan=None, *, node_hooks=None) -> TeamResult:
    """``node_hooks`` (awakening_node_rules.RunHooks of the run; default: ``layout.run_hooks``): damage its post
    hooks settle after replay is added to the members' direct damage and credited to their visits like DoT ticks."""
    if node_hooks is None:
        node_hooks = getattr(layout, "run_hooks", None)
    from src.services import team_awakening
    from src.services import team_cycle_reactions as tcr
    from src.services import team_simulation_explanation as tx
    from src.services.team_rotation_data import CHARACTERS

    replay_by_event = {r.event_id: r for r in replays}

    def event_of(row: dict) -> str:
        return f"{row['sequence_order']}:primary"

    selections = team_awakening.selections_of(characters)
    results = {c["character_id"]: MemberResult(
        character_id=c["character_id"], name_zh=c["observed_name"], fork_id=c["fork_id"],
        fork_refinement_level=c["fork_refinement_level"], awakening_level=c["awakening_level"],
        suit_id=c["_suit_id"], element=elements.get(c["character_id"], ""),
        role=str((CHARACTERS.get(c["character_id"]) or {}).get("role") or ""),
        awakening_effects=tuple(selections[int(c["character_id"])].effects)) for c in characters}

    status: dict[str, int] = defaultdict(int)
    unreplayable = 0
    step_damage: dict[tuple[int, int], float] = defaultdict(float)
    step_hits: dict[tuple[int, int], int] = defaultdict(int)
    # damage-over-time ticks belong to no step: credit each to its owner's latest visit started at or
    # before the tick, so a member's visits add up to its direct damage in the explanation
    dot_ids = {id(row) for row in dot_rows}
    visit_starts: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for visit in layout.visits:
        visit_starts[visit.character_id].append((visit.start_us, visit.index))
    dot_damage: dict[int, float] = defaultdict(float)
    dot_hits: dict[int, int] = defaultdict(int)

    def owner_visit(cid: int, t_us: int) -> int | None:
        starts = visit_starts.get(cid) or ()
        found = starts[0][1] if starts else None
        for start_us, index in starts:
            if start_us <= t_us:
                found = index
        return found

    for row in layout.rows + dot_rows:
        r = replay_by_event.get(event_of(row))
        if r is None:
            continue
        status[str(r.critical_state)] += 1
        if r.critical_state == "unreplayable":
            unreplayable += 1
        cid = row["character_id"]
        if cid in results and r.expected_damage:
            results[cid].damage += float(r.expected_damage)
            results[cid].hits += 1
            key = layout.side.get(id(row))
            if key is not None:
                step_damage[key] += float(r.expected_damage)
                step_hits[key] += 1
            elif id(row) in dot_ids:
                vi = owner_visit(cid, row["relative_time_us"])
                if vi is not None:
                    dot_damage[vi] += float(r.expected_damage)
                    dot_hits[vi] += 1

    # reaction rows: damage by reaction index, markers left out of damage, hits and status counts
    origins = sched.event_origins()
    reaction_damage: dict[int, float] = defaultdict(float)
    reaction_unreplayable: dict[int, int] = defaultdict(int)
    breakdown: dict[str, float] = defaultdict(float)
    scorch_layers = 0.0          # highest 浊燃 layer count the engine used (Phase 1b DoT ticks add layers)
    for row in reaction_rows:
        origin = origins.get(event_of(row))
        if origin is None or origin.kind == "marker":
            continue
        r = replay_by_event.get(event_of(row))
        if r is None:
            continue
        status[str(r.critical_state)] += 1
        if r.critical_state == "unreplayable" or r.expected_damage is None:
            reaction_unreplayable[origin.reaction_index] += 1
            unreplayable += 1
            continue
        value = float(r.expected_damage)
        if origin.kind == "reaction:浊燃":
            scorch_layers = max(scorch_layers, max((f.value for f in r.factors if f.factor_id == "state_coefficient"),
                                                   default=1.0))
        reaction_damage[origin.reaction_index] += value
        breakdown[origin.kind.split(":", 1)[1]] += value
        cid = row["character_id"]
        if cid in results:
            results[cid].reaction_damage += value

    # 覆纹 / 浸染: own formula after replay, credited to each boosted hit's member
    pairs = [(h, replay_by_event.get(h.event_id)) for h in analysis.hits]
    windows = sched.windows()
    mag_of = tcr.make_mag_lookup(analysis)
    increments = (tcr.apply_hexed(pairs, windows, mag_of, to_active=to_active)
                  + tcr.apply_stain(pairs, windows, mag_of, to_active=to_active))
    boosted: dict[int, int] = defaultdict(int)
    for inc in increments:
        reaction_damage[inc.reaction_index] += inc.increment
        boosted[inc.reaction_index] += 1
        breakdown[inc.reaction_zh] += inc.increment
        if inc.character_id in results:
            results[int(inc.character_id)].reaction_damage += inc.increment
    if node_hooks is not None:          # awakening node rules: damage settled after replay (post hooks)
        for settled in node_hooks.post(pairs):
            cid = int(settled.character_id)
            if cid in results and settled.damage:
                results[cid].damage += float(settled.damage)
                vi = owner_visit(cid, int(settled.t_us))
                if vi is not None:
                    dot_damage[vi] += float(settled.damage)

    # visits, on-field time and the battle clock
    wall_time_s = _seconds(layout.end_us)
    active_time_s = (to_active(layout.end_us) - to_active(START_US)) / 1e6
    for visit in layout.visits:
        member = results[visit.character_id]
        member.visits += 1
        member.time_s += (to_active(visit.end_us) - to_active(visit.start_us)) / 1e6
    for cid, missing in layout.missing.items():
        results[cid].missing_actions.extend(missing)
    for member in results.values():
        member.team_time_s = active_time_s

    # one entry per buff (source, effect, modifiers): two buffs with the same value stay apart, and every window
    # the engine applied is listed (overlapping / touching windows merged); start_s / end_s = the first window
    team_buffs = []
    by_buff: dict[tuple, dict] = {}
    for iv in analysis.buff_intervals:
        if iv.target_scope not in ("team", "team_others"):
            continue
        mods = tuple((m.property_id, m.magnitude_value) for m in iv.modifiers)
        key = (iv.source_character_id, iv.source_effect_definition_id or iv.buff_asset_path, mods)
        if key not in by_buff:
            by_buff[key] = {"source_character_id": iv.source_character_id, "scope": iv.target_scope,
                            "modifiers": [{"property_id": p, "value": v} for p, v in mods], "_spans": [],
                            "key": buff_key(iv)}
            team_buffs.append(by_buff[key])
        by_buff[key]["_spans"].append((max(0.0, _seconds(iv.start_us)), max(0.0, _seconds(iv.end_us))))
    for buff in team_buffs:
        windows: list[list[float]] = []
        for a, b in sorted(buff.pop("_spans")):
            if windows and a <= windows[-1][1] + 1e-6:
                windows[-1][1] = max(windows[-1][1], b)
            else:
                windows.append([a, b])
        buff["windows"] = [tuple(w) for w in windows]
        buff["start_s"], buff["end_s"] = buff["windows"][0]
    # different buffs of one member with the same modifiers and windows (Sagiri's skill and awakening ATK) read as
    # one line with a count: both apply, so the line must not look like a duplicate
    collapsed: dict[tuple, dict] = {}
    for buff in team_buffs:
        look = (buff["source_character_id"], tuple((m["property_id"], m["value"]) for m in buff["modifiers"]),
                tuple(buff["windows"]))
        if look in collapsed:
            collapsed[look]["count"] += 1
            if buff["key"] not in collapsed[look]["keys"]:
                collapsed[look]["keys"].append(buff["key"])
        else:
            buff["count"] = 1
            buff["keys"] = [buff["key"]]         # every buff shown on this line (custom mode: on / off per line)
            collapsed[look] = buff
    team_buffs = list(collapsed.values())

    explanation = _explain(team_ids, order, loops, order_mode, gauge_rule, opening_gauge, layout, sched,
                           reaction_damage, reaction_unreplayable, boosted, step_damage, step_hits, elements,
                           ability_names, results, wall_time_s, active_time_s, to_active, unreplayable, simulated,
                           scorch_layers, tx, dot_damage, dot_hits, plan)
    total_reactions = float(sum(breakdown.values()))
    return TeamResult(members=[results[cid] for cid in team_ids], team_buffs=team_buffs, replay_status=dict(status),
                      reaction_damage=total_reactions, reaction_breakdown=dict(breakdown),
                      wall_time_s=wall_time_s, active_time_s=active_time_s, explanation=explanation)


def _form_trace(tx, summary: dict | None, to_active):
    if not summary:
        return None
    start = summary.get("start_us")
    return tx.FormTrace(
        code=summary["code"], name_zh=summary["name_zh"], duration_s=float(summary["duration_s"]),
        start_s=None if start is None else _seconds(start), used_s=float(summary["used_s"]),
        groups=int(summary["groups"]), groups_approved=int(summary["groups_approved"]), fills=int(summary["fills"]),
        cut_steps=int(summary["cut_steps"]), overrun_s=float(summary["overrun_s"]), status=summary["status"],
        pauses_off_field=bool(summary["pauses_off_field"]), ends_on_swap=bool(summary["ends_on_swap"]),
        exit_s=summary.get("exit_s"), window=tuple(summary.get("window") or ()))


def _explain(team_ids, order, loops, order_mode, gauge_rule, opening_gauge, layout, sched, reaction_damage,
             reaction_unreplayable, boosted, step_damage, step_hits, elements, ability_names, results,
             wall_time_s, active_time_s, to_active, unreplayable, simulated, scorch_layers, tx,
             dot_damage=None, dot_hits=None, plan=None):
    from src.services.team_form_actions import FORM_ACTIONS, FORMS
    from src.services.team_rotation_data import CHARACTERS

    dot_damage, dot_hits = dot_damage or {}, dot_hits or {}

    resources = getattr(layout, "resources", None)
    if resources is not None:
        _credit_charge_energy(layout, sched, resources)
    visits = []
    for visit in layout.visits:
        steps = []
        for si, step in enumerate(visit.steps):
            name = ability_names.get(step.ability_id or "", "")
            if not name and (step.ability_id, step.selector) in FORM_ACTIONS:
                name = FORM_ACTIONS[(step.ability_id, step.selector)].get("name_zh") or ""
            extra = {}
            if resources is not None:
                extra = {"energy_before": step.energy_before, "energy_after": step.energy_after,
                         "cd_kind": step.cd_kind, "remaining_s": step.remaining_us / 1e6, "note": step.note,
                         "events": tuple(step.events), "credit": float(step.credit), "cost": step.cost,
                         "energy_gain": round(resources.scaled(visit.character_id, step.energy_raw,
                                                               step.energy_events), 3),
                         "gauge_after": step.gauge_after, "gauge_gain": round(float(step.gauge_gain), 3),
                         "cd_s": step.cd_s, "cd_conf": step.cd_conf, "cd_source": step.cd_source,
                         "dropped": int(getattr(step, "dropped", 0) or 0), "wait_for": getattr(step, "wait_for", None)}
            steps.append(tx.StepTrace(
                seq=step.seq, slot=step.slot, ability_id=step.ability_id, selector=step.selector,
                start_s=_seconds(step.start_us), duration_s=(step.end_us - step.start_us) / 1e6,
                hits=step_hits.get((visit.index, si), 0), damage=step_damage.get((visit.index, si), 0.0),
                status=step.status, ability_name_zh=name, form_role=step.form_role, **extra))
        extra = {}
        if resources is not None:
            extra = {"energy_in": visit.energy_in, "energy_out": visit.energy_out,
                     "waited_s": visit.waited_us / 1e6, "early_swap": tuple(getattr(visit, "early_swap", ()) or ()),
                     "energy_gain": round(resources.scaled(visit.character_id, visit.energy_raw,
                                                           visit.energy_events), 3)}
        visits.append(tx.VisitTrace(
            index=visit.index, loop_index=visit.loop_index, character_id=visit.character_id,
            element=elements.get(visit.character_id, ""), entry=visit.entry,
            start_s=_seconds(visit.start_us), end_s=_seconds(visit.end_us),
            active_s=(to_active(visit.end_us) - to_active(visit.start_us)) / 1e6,
            gauge_in=float(visit.gauge_in), gauge_out=float(visit.gauge_out), steps=tuple(steps),
            damage=sum(s.damage for s in steps), dot_damage=float(dot_damage.get(visit.index, 0.0)),
            dot_hits=int(dot_hits.get(visit.index, 0)), refilled=bool(visit.refilled),
            form=_form_trace(tx, visit.form, to_active), **extra))

    swaps = tuple(tx.SwapTrace(
        index=s.index, time_s=_seconds(s.time_us), out_character_id=s.out_character_id,
        in_character_id=s.in_character_id, out_element=s.out_element, in_element=s.in_element,
        gauge=s.gauge, outcome=s.outcome, reaction_index=s.reaction_index) for s in layout.swaps)

    reactions = []
    for event in sched.traces():
        effects = list(event.effects)
        hits = event.hits
        status = event.status
        if event.code in ("hexed", "stain"):
            hits = boosted.get(event.index, 0)
            effects.append(tx.effect(tx.EFFECT_BOOSTED_HITS, hits))
        bad = reaction_unreplayable.get(event.index, 0)
        if bad:
            effects.append(tx.effect(tx.EFFECT_UNREPLAYABLE, bad))
            status = tx.REACTION_PARTIAL
        reactions.append(tx.ReactionTrace(
            index=event.index, time_s=_seconds(event.time_us), reaction_zh=event.reaction_zh,
            out_character_id=event.out_character_id, in_character_id=event.in_character_id,
            owner_character_id=event.owner_character_id, owner_basis=event.owner_basis, hits=hits,
            damage=float(reaction_damage.get(event.index, 0.0)), status=status, effects=tuple(effects)))

    members = []
    for cid in team_ids:
        data = CHARACTERS.get(cid) or {}
        steps = data.get("variants", {}).get("approved", {}).get("steps", ())
        runnable = [s for s in steps if s.get("sim")]
        missing = tuple(dict.fromkeys(results[cid].missing_actions))
        own = [v for v in visits if v.character_id == cid]
        members.append(tx.MemberRotationTrace(
            character_id=cid, variant_id=tx.VARIANT_APPROVED, verdict=str(data.get("verdict") or ""),
            confidence=str(data.get("confidence") or ""), role=str(data.get("role") or ""),
            steps_total=len(steps), steps_simulated=int(simulated.get(cid, 0)),
            steps_time_only=len(steps) - len(runnable), missing=missing,
            name_zh=results[cid].name_zh, element=elements.get(cid, ""),
            dot_damage=sum(v.dot_damage for v in own), dot_hits=sum(v.dot_hits for v in own)))

    stops = tuple(tx.TimeStopTrace(start_s=_seconds(s), duration_s=(min(e, layout.end_us) - s) / 1e6,
                                   character_id=owner[0], ability_id=owner[1])
                  for (s, e), owner in zip(layout.stops, layout.stop_owners) if s < layout.end_us)

    codes = {e.reaction_zh for e in sched.traces()}
    scheduler_limits = list(sched.limits())
    refills = tuple(layout.refill_loops)
    order_note = {"auto": tx.ASSUME_ORDER_AUTO, "slot": tx.ASSUME_ORDER_SLOT}.get(order_mode, tx.ASSUME_ORDER_PLAN)
    assumptions = [tx.note(tx.ASSUME_APPROVED_ROTATIONS), tx.note(order_note)]
    if opening_gauge != "full":
        assumptions.append(tx.note(tx.ASSUME_OPENING_ZERO))
    if resources is not None:               # resource levels: accumulated gauge, fixed refill for fallback members
        if refills:
            assumptions.append(tx.note(tx.ASSUME_GAUGE_ACCUMULATED))
        by_loop: dict[int, list[int]] = defaultdict(list)
        for loop, cid in getattr(layout, "refills", ()) or ():
            by_loop[int(loop)].append(int(cid))
        for loop in sorted(by_loop):
            assumptions.append(tx.note(tx.ASSUME_GAUGE_FALLBACK, loop, *by_loop[loop]))
    elif refills:
        assumptions.append(tx.note(tx.ASSUME_FULL_GAUGE_LOOPS, *refills))
    assumptions.append(tx.note(tx.ASSUME_GAUGE_GAME if gauge_rule == "game" else tx.ASSUME_GAUGE_IDEAL))
    if layout.used_gauge_set:
        assumptions.append(tx.note(tx.ASSUME_GAUGE_SET_SKILLS))
    if layout.used_normal_entry or any(v.entry == "normal" for v in layout.visits):
        assumptions.append(tx.note(tx.ASSUME_NORMAL_ENTRY))
    if layout.stops:
        assumptions.append(tx.note(tx.ASSUME_TIME_STOPS))
    for member in members:                  # Phase 1b damage-over-time ticks that are in the result
        if member.dot_hits:
            assumptions.append(tx.note(tx.ASSUME_DOT_TICKS, member.character_id))
    form_used = layout.form_actions or {}
    for cid in team_ids:                    # form-state actions that ran, and the form windows entered
        if form_used.get(cid):
            assumptions.append(tx.note(tx.ASSUME_FORM_ACTIONS, cid))
        entered = [v.form for v in visits if v.character_id == cid and v.form is not None]
        if entered:
            assumptions.append(tx.note(tx.ASSUME_FORM_WINDOW, cid, entered[0].name_zh,
                                       f"{entered[0].duration_s:g}"))
    resource_traces, resource_assume, resource_limits = (), [], []
    if resources is None:
        assumptions.append(tx.note(tx.ASSUME_ENERGY_NOT_GATED))
    else:
        resource_traces, resource_assume, resource_limits = _resource_notes(tx, team_ids, layout, visits, codes,
                                                                            resources)
        assumptions.extend(resource_assume)
    for code in (tx.ASSUME_HEXED_IMMEDIATE, tx.ASSUME_SCORCH_DOT):   # scheduler model notes, not limits
        if any(c == code for c, _args in scheduler_limits):
            assumptions.append(tx.note(code))
    if codes & {"浊燃", "黯星", "创生"}:
        assumptions.append(tx.note(tx.ASSUME_REACTION_OWNER))

    dropped = {tx.ASSUME_HEXED_IMMEDIATE, tx.ASSUME_SCORCH_DOT}
    if resources is not None:               # the 盈蓄 energy is in the energy shown (validation F7)
        dropped.add(tx.LIMIT_CHARGE_ENERGY)
    if scorch_layers >= 2:       # the damage-over-time ticks already stack Zankou's Scorch past 1 layer
        dropped.add(tx.LIMIT_SCORCH_ONE_LAYER)
    limits = [tx.note(code, *args) for code, args in scheduler_limits if code not in dropped]
    if gauge_rule == "game":
        limits.append(tx.note(tx.LIMIT_GAUGE_FIT))
    if 1072 in team_ids:
        limits.append(tx.note(tx.LIMIT_LINKO_COATTACK))
    lacrimosa = next((c for c in results.values() if c.character_id == LACRIMOSA_ID), None)
    if lacrimosa is not None and "Effect6" in lacrimosa.awakening_effects:     # A5: the node, not the level
        limits.append(tx.note(tx.LIMIT_LACRIMOSA_A6))
    for assumed_by in results.values():     # the approved rotation assumes a node the member did not select
        for node in tx.rotation_assumed_nodes(assumed_by.character_id):
            if node not in assumed_by.awakening_effects:
                limits.append(tx.note(tx.LIMIT_ROTATION_ASSUMES_AWAKENING, assumed_by.character_id, node))
    limits.append(tx.note(tx.LIMIT_SUMMONS_DOT))
    for cid in team_ids:                    # form windows: cut rounds, overruns, missed exit windows
        own = [v.form for v in visits if v.character_id == cid and v.form is not None]
        cut = [f for f in own if f.status == tx.FORM_CUT or f.cut_steps]
        if cut:
            worst = min(cut, key=lambda f: f.groups)
            limits.append(tx.note(tx.LIMIT_FORM_CUT, cid, worst.groups, worst.groups_approved))
        over = max((f.overrun_s for f in own), default=0.0)
        if over > 0:
            limits.append(tx.note(tx.LIMIT_FORM_OVERRUN, cid, f"{over:.1f}"))
        missed = [f for f in own if f.status == tx.FORM_WINDOW_MISSED and f.window]
        if missed:
            f = missed[0]
            limits.append(tx.note(tx.LIMIT_FORM_WINDOW_MISSED, cid, f"{f.exit_s or 0.0:.1f}",
                                  f"{f.window[0]:g}", f"{f.window[1]:g}"))
        timing = {FORM_ACTIONS[k]["timing"] for k in (form_used.get(cid) or {}) if k in FORM_ACTIONS}
        if timing & {"assumed", "periodic"}:
            limits.append(tx.note(tx.LIMIT_FORM_TIMING_ASSUMED, cid))
    if form_used.get(RAVEN_ID):
        limits.append(tx.note(tx.LIMIT_RAVEN_MALICE))
    if any(layout.missing.values()):
        limits.append(tx.note(tx.LIMIT_MISSING_ACTIONS))
    if layout.used_default_time:
        limits.append(tx.note(tx.LIMIT_DEFAULT_STEP_TIME))
    for cid in team_ids:
        if cid in layout.unknown_stop:
            limits.append(tx.note(tx.LIMIT_TIME_STOP_UNKNOWN, cid))
    if unreplayable:
        limits.append(tx.note(tx.LIMIT_UNREPLAYABLE, unreplayable))
    limits.extend(resource_limits)
    limits.append(tx.note(tx.LIMIT_FIGHT_END))

    extra = {}
    if resources is not None:
        extra = {"resource_model": resources.policy.model, "gauge_refills": tuple(getattr(layout, "refills", ()) or ()),
                 "resources": resource_traces, "waited_s": getattr(layout, "waited_us", 0) / 1e6,
                 "resource_clock": resources.policy.clock, "not_ready": resources.not_ready_mode()}
    return tx.TeamExplanation(
        order_mode=order_mode, gauge_rule=gauge_rule, opening_gauge=opening_gauge, loops=loops, order=tuple(order),
        wall_time_s=wall_time_s, active_time_s=active_time_s, time_stops=stops, visits=tuple(visits), swaps=swaps,
        reactions=tuple(reactions), members=tuple(members), assumptions=tuple(assumptions), limits=tuple(limits),
        full_gauge_loops=refills, plan=plan, **extra)


def _credit_charge_energy(layout, sched, resources) -> None:
    """盈蓄 ultimate-energy grants (the member on the field at each grant, team_cycle_reactions.charge_grants) added to
    that member's energy, its visit and the step running then (display; the layout's checks did not use them).  Runs
    once per layout: plan mode collects the chosen run twice."""
    if layout.charge_done:
        return
    layout.charge_done = True
    grants = sched.charge_grants() if hasattr(sched, "charge_grants") else ()
    visits = sorted(layout.visits, key=lambda v: v.start_us)
    for t_us, amount in grants:
        visit = next((v for v in reversed(visits) if v.start_us <= t_us), None)
        if visit is None:
            continue
        resources.add_charge(visit.character_id, amount)
        visit.energy_events += amount
        step = next((s for s in visit.steps if s.start_us <= t_us < s.end_us and s.status == "ok"), None)
        if step is None:
            step = next((s for s in reversed(visit.steps) if s.status == "ok" and s.start_us <= t_us), None)
        if step is not None:
            step.energy_events += amount
            step.events = tuple(step.events) + (("charge", float(amount)),)
        layout.charge_energy += amount
        layout.charge_grants += 1


def _resource_notes(tx, team_ids, layout, visits, codes, resources):
    """MemberResourceTrace per member plus the assumption / limit items of a resource level (team_resources)."""
    from src.services import team_resources as tr

    policy = resources.policy
    data = resources.data
    traces, assume, limits = [], [], []
    assume.append(tx.note(tx.ASSUME_RESOURCE_MODEL, policy.model))
    assume.append(tx.note(tx.ASSUME_RESOURCE_CLOCK, policy.clock))
    assume.append(tx.note(tx.ASSUME_ENERGY_TRACKED))
    assume.append(tx.note(tx.ASSUME_CHARGE_EFF))
    if resources.not_ready_mode() == "swap":    # D3 (2026-10-14): a team swaps out at once (threshold: 2026-10-18)
        assume.append(tx.note(tx.ASSUME_NOT_READY_SWAP, float(policy.swap_min_wait_s)))
    elif resources.solo and policy.cooldown == "wait":     # nobody to swap to
        assume.append(tx.note(tx.ASSUME_NOT_READY_SOLO))
    used_kinds: dict[int, set] = defaultdict(set)
    skipped_too_long: list = []
    not_entered: list = []
    for v in visits:
        for s in v.steps:
            if s.cd_kind and s.status in ("ok", "cd_skip", "energy_short", "swap_out"):
                used_kinds[v.character_id].add(s.cd_kind)
            if s.status == "cd_skip":
                skipped_too_long.append((v.character_id, s.cd_kind or "?", round(s.remaining_s, 1)))
            if s.status == "form_cut" and s.note == "form_not_entered":
                not_entered.append((v.character_id, v.loop_index + 1))
    gated, unknown_cost, community_cd, struct_none = [], [], [], []
    swap_mode = resources.not_ready_mode() == "swap"
    blocked_total = 0.0                     # D3: seconds of all-blocked waits (told one by one, LIMIT_ALL_BLOCKED)
    short_total = 0.0                       # waits under the swap threshold (told per member, ASSUME_SHORT_WAIT)
    for cid in team_ids:
        summary = resources.member_summary(cid)
        rec = tr.record(cid, data)
        # A6: codes bound to an awakening node are shown only when the node is selected (team_simulation_explanation)
        member_codes = tuple((getattr(resources, "code_map", None) or {}).get(c, c)
                             for c in rec.get("unmodelled") or ())
        shown_unmodelled = tx.unmodelled_for(cid, member_codes, resources.selection_of(cid))
        energy = rec.get("energy") or {}
        cd_rows, alt_rows = [], []
        for kind in ("E", "E_alt", "Q", "QTE", "counter"):
            if kind not in (rec.get("cd") or {}):
                continue
            enforced = tr.cd_cell(cid, kind, policy, data)
            best = tr.best_cd_cell(cid, kind, data)
            used = resources.cd_seconds(cid, kind)
            cell = enforced or best or (None, "", "unknown")
            cd_rows.append((kind, used, None if best is None else best[0], str(cell[1]), str(cell[2])))
            for value, label, conf in (rec.get("cd_alt") or {}).get(kind, ()):
                alt_rows.append((kind, value, label, conf))
        own_name = ((energy.get("clock") or energy.get("meter") or {}).get("name_zh") or "")
        traces.append(tx.MemberResourceTrace(
            character_id=cid, energy_kind=summary["energy_kind"], cost=tuple(energy.get("cost") or ()),
            cost_enforced=summary["cost"] is not None or summary["energy_kind"] == "own_clock",
            cost_display=tuple(energy.get("cost_display") or ()), cost_bound=energy.get("cost_bound"),
            gauge_fallback=bool(summary["fallback"]), fallback_reason=summary["fallback_reason"], cd=tuple(cd_rows),
            cd_alt=tuple(alt_rows), q_planned=summary["q_planned"], q_cast=summary["q_cast"],
            q_skipped=summary["q_skipped"], waited_s=summary["waited_s"], cd_waits=summary["cd_waits"],
            res_waits=summary["res_waits"], cd_skips=summary["cd_skips"], interlude_s=summary["interlude_s"],
            interludes_s=tuple(summary.get("interludes_s") or ()),
            energy_gained=round(summary["gained"], 3), charge_eff=summary["eff"], events=summary["events"],
            unmodelled=tuple(shown_unmodelled), unchecked=summary["unchecked"],
            credited_gauge=round(summary["credited_gauge"], 3), own_name_zh=own_name,
            charges=resources.charges(cid, "E"), meter_short=summary["meter_short"],
            early_swaps=tuple(summary.get("early_swaps") or ()), all_blocked=tuple(summary.get("all_blocked") or ()),
            short_waits=tuple(summary.get("short_waits") or ())))
        if not resources.has_record(cid):      # data module older than the character (review F6)
            limits.append(tx.note(tx.LIMIT_RESOURCE_DATA_MISSING, cid))
        if summary["energy_kind"] == "ultimate":
            if summary["cost"] is not None:
                gated.append((cid, summary["cost"]))
            else:
                unknown_cost.append(cid)
                cost = energy.get("cost") or ()
                if cost and cost[2] in data.CONTESTED and cost[0] is not None:
                    limits.append(tx.note(tx.LIMIT_COST_CONTESTED, cid, cost[0]))
        else:
            assume.append(tx.note(tx.ASSUME_OWN_RESOURCE, cid, own_name))
            if summary["energy_kind"] == "own_clock":
                limits.append(tx.note(tx.LIMIT_OWN_RESOURCE_DRAIN, cid, own_name))
                if summary["interlude_s"] > 0:
                    per_visit = "/".join(f"{s:.1f}" for s in summary.get("interludes_s") or ())
                    assume.append(tx.note(tx.ASSUME_HOTORI_INTERLUDE, cid, own_name, round(summary["interlude_s"], 2),
                                          per_visit))
                if summary["res_waits"] and resources.solo:
                    limits.append(tx.note(tx.LIMIT_MIDVISIT_SWAP, cid))
            else:
                limits.append(tx.note(tx.LIMIT_OWN_RESOURCE_UNIT, cid, own_name))
        shown = []
        for kind in ("E", "E_alt", "Q"):
            if kind not in used_kinds[cid]:
                continue
            c = tr.cd_cell(cid, kind, policy, data)
            if c is None:
                continue
            if c[2] == "community_low":
                shown.append(f"{kind} {float(c[0]):g}s")
        if shown:
            community_cd.append((cid, " · ".join(shown)))
        unknown_kinds = [k for k in ("E", "E_alt", "Q") if k in used_kinds[cid] and resources.cd_seconds(cid, k) is None]
        if unknown_kinds:
            limits.append(tx.note(tx.LIMIT_CD_UNKNOWN, cid, "/".join(unknown_kinds)))
        if "QTE" in used_kinds[cid] or "counter" in used_kinds[cid]:
            qte = tr.cd_cell(cid, "QTE", policy, data)
            if qte is not None and qte[2] == "db_struct_none":
                struct_none.append(cid)
        if summary["q_skipped"]:
            limits.append(tx.note(tx.LIMIT_ENERGY_SHORT, cid, len(summary["q_skipped"])))
        blocked_s = sum(float(b[2]) for b in summary.get("all_blocked") or ()) if swap_mode else 0.0
        blocked_total += blocked_s
        short = tuple(summary.get("short_waits") or ()) if swap_mode else ()
        short_s = sum(float(x[3]) for x in short)
        short_total += short_s
        if short:                               # cooldowns under the swap threshold waited for (2026-10-18)
            assume.append(tx.note(tx.ASSUME_SHORT_WAIT, cid, len(short), round(sum(float(x[4]) for x in short), 3),
                                  float(policy.swap_min_wait_s)))
        own_wait_s = summary["waited_s"] - blocked_s - short_s
        if summary["cd_waits"] and (own_wait_s > 0.005 if swap_mode else summary["waited_s"] > 0):
            limits.append(tx.note(tx.LIMIT_CD_WAITED, cid, round(own_wait_s, 2)))
        swaps = tuple(summary.get("early_swaps") or ())
        if swaps:                               # D3: swapped out at once (each one is a row of the step table)
            # steps not run: the swapped-out steps themselves and the rest of their visits (review F2)
            limits.append(tx.note(tx.LIMIT_EARLY_SWAP, cid, len(swaps), len(swaps) + sum(int(s[5]) for s in swaps)))
        for _loop, _seq, seconds, other in summary.get("all_blocked") or ():
            limits.append(tx.note(tx.LIMIT_ALL_BLOCKED, cid, seconds, other))
        if summary["credits"]:
            limits.append(tx.note(tx.LIMIT_TIME_ONLY_CREDIT, cid))
        if summary["partial_time_only"]:
            limits.append(tx.note(tx.LIMIT_GAUGE_PARTIAL, cid, summary["partial_time_only"]))
        unmodelled = [c for c in shown_unmodelled if c]
        if unmodelled:
            limits.append(tx.note(tx.LIMIT_ENERGY_EVENT_UNMODELLED, cid, *unmodelled))
        if policy.clock == "active":           # a recorded interval shorter than the cooldown (V6, G1 open)
            for kind in sorted(rec.get("cd_conflict") or {}):
                bound = resources.cd_conflict(cid, kind)     # None when the build's rules explain it (review F4)
                if kind in used_kinds[cid] and bound is not None:
                    limits.append(tx.note(tx.LIMIT_CD_CLOCK_CONFLICT, cid, kind, resources.cd_seconds(cid, kind),
                                          bound))
        charges = resources.charges(cid, "E")
        if charges > 1 and resources.cd_seconds(cid, "E"):
            limits.append(tx.note(tx.LIMIT_CD_CHARGES, cid, charges, resources.cd_seconds(cid, "E")))
    for cid, cost in gated:
        assume.append(tx.note(tx.ASSUME_ENERGY_GATED, cid, cost))
    if gated:
        assume.append(tx.note(tx.ASSUME_START_ENERGY_FULL))
    inserted_s = getattr(layout, "waited_us", 0) / 1e6 - blocked_total - short_total
    if inserted_s > (0.01 if swap_mode else 0.0):      # D3: all-blocked waits are not "inserted cooldown waits"
        assume.append(tx.note(tx.ASSUME_CD_WAIT, round(inserted_s, 2)))
    if unknown_cost:
        limits.insert(0, tx.note(tx.LIMIT_ENERGY_UNKNOWN, *unknown_cost))
        limits.insert(1, tx.note(tx.LIMIT_ENERGY_SCALE))
    for cid, text in community_cd:
        limits.append(tx.note(tx.LIMIT_CD_COMMUNITY, cid, text))
    if struct_none:
        limits.append(tx.note(tx.LIMIT_CD_NONE_STRUCT, *struct_none))
    for cid, kind, seconds in skipped_too_long:
        limits.append(tx.note(tx.LIMIT_CD_WAIT_TOO_LONG, cid, kind, seconds))
    for cid, loop in dict.fromkeys(not_entered):
        limits.append(tx.note(tx.LIMIT_FORM_NOT_ENTERED, cid, loop))
    if gated and "盈蓄" in codes:
        limits.append(tx.note(tx.LIMIT_CHARGE_ENERGY_GATED))
    if getattr(layout, "charge_grants", 0):
        assume.append(tx.note(tx.ASSUME_CHARGE_ENERGY_SHOWN, round(float(layout.charge_energy), 3),
                              int(layout.charge_grants)))
    for cid in team_ids:                    # hits the animation does not lay out (summons / zones; review F12)
        ran = {(s.ability_id, s.selector or "") for v in visits if v.character_id == cid for s in v.steps
               if s.status == "ok"}
        table = getattr(data, "HIT_CREDIT", None) or {}
        for (hcid, ability, selector), cell in sorted(table.items()):
            if hcid != cid or (ability, selector) not in ran:
                continue
            if cell[0] is None:
                limits.append(tx.note(tx.LIMIT_HIT_UNKNOWN, cid, ability, selector))
            elif layout.hit_credited.get(cid):
                limits.append(tx.note(tx.LIMIT_HIT_CREDIT, cid, round(float(cell[0]), 3), round(float(cell[1]), 3),
                                      int(cell[2] or 0), str(cell[4])))
    if "覆纹" in codes:
        limits.append(tx.note(tx.LIMIT_GAUGE_EFFICIENCY))
    return tuple(traces), assume, limits
