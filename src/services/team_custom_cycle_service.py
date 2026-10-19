# 队伍模拟「直接输入」模式：把用户输入的循环排到动作轴上，复用已审核模式的引擎路径计算伤害、环合反应与 DPS。
"""Custom-cycle mode of the team simulator ("직접 입력").

The user writes one flat team sequence (``team_custom_notation``), e.g.::

    제로 서포트 > 제로 E > 제로 평타x3 > 일로이 교체 > 일로이 Q > 일로이 E > 일로이 평타

``simulate_custom`` lays exactly that sequence on the simulator axis and runs the same pipeline the approved mode
runs (``team_simulation_service``: damage-over-time ticks, reaction rows, replay engine, owner pass, ``_collect``),
so every number comes from the same formula.  Esper Cycle reactions are always computed.

Entry types: ``support`` = the member enters with its support skill and the reaction of the outgoing / incoming
element pair fires; ``swap`` (or just naming another member) = a plain swap: no support skill, no reaction.

One timeline walker (``_Walker``) owns the custom-mode logic - who is on the field, entry decisions, gauge reads
and consumption, chain positions and transformation states, cooldowns, inserted waits, notes - and two measurers
place the actions: ``_PaletteMeasure`` (generated numbers, no database: the live preview of the page) and
``_AxisMeasure`` (hit rows from the static database for the engine).  The walker decides swaps itself and never
calls ``CycleGauge.on_swap`` (which would consume the gauge on every adjacent swap).

Options (``CustomOptions``): repeat count, gauge mode and starting gauge, cooldown / energy numbers and check
mode, inferred buffs switched off, manual buffs, enemy numbers, swap time.

Awakening (A9-A11, Global): the cards' node sets (``team_awakening.AwakeningSel``; an int is a legacy level =
Effect1..level, None = the template's ``TEMPLATE_SELECTION``) unlock the cooldown rules of team_resource_data (the rule
field is the node number n = Effect n) in the preview, the strict walk and the engine run.  Awakening node rules
(``awakening_node_rules``) add their resource rows to those rules, run their gate / placed hooks through the shared
``_AxisWriter``, may make a typed support entry free of the gauge (``free_support``) and write explanation items.
"""
from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services import team_awakening
from src.services import team_custom_notation as notation
from src.services.team_custom_notation import ENTRY_ACTIONS, RAW_ACTION, SLOT_ACTIONS, CustomStep

GAUGE_MODES = ("as_typed", "check")
# strict = the reviewed mode's policy (team_resources): a short ultimate-energy pool skips the ultimate, a cooldown
# that is not ready is waited for (cd_wait_max_s / 60 s guard: skipped beyond it) - except in a team (user decision D3,
# 2026-10-14): a press that is not ready swaps the member out at once when another member is typed after it (the
# member's remaining inputs up to that step are not run); with nobody typed after it the old wait / skip applies
RESOURCE_CHECKS = ("off", "warn", "wait", "strict")
CD_WAIT_GUARD_S = 60.0
MANUAL_BUFF_KINDS = ("atk_pct", "atk_flat", "crit_rate", "crit_dmg", "dmg_all", "dmg_element", "def_ignore",
                     "res_down", "mag")
PERCENT_BUFF_KINDS = frozenset(("atk_pct", "crit_rate", "crit_dmg", "dmg_all", "dmg_element", "def_ignore",
                                "res_down"))
ELEMENT_BUFF_KINDS = frozenset(("dmg_element", "res_down"))
ELEMENTS = ("cosmos", "nature", "incantation", "chaos", "psyche", "lakshana", "psychically")
MANUAL_BUFF_LIMIT = 1e6            # |value| of a manual buff
MANUAL_BUFF_RANGES = {"def_ignore": (0.0, 100.0)}      # percent of the defence: more than all of it is no buff
MAX_REPEAT, MAX_STEPS, MAX_ACTIONS = 10, notation.MAX_STEPS, notation.MAX_ACTIONS
MAX_SWAP_TIME_S = 2.0
STATE_TOLERANCE_US = 1000          # the approved mode's overrun tolerance (1 ms)
CD_TOLERANCE_US = 1000
MAX_ENEMIES = 10                   # TargetOptions.enemy_count range (node rules only)
TEMPLATE_AWAKENING = 6             # every graduation template is awakening 6 (preview without the cards' levels)
# A10: the node set used without the cards' selection (the graduation templates: level 6, Effect1..Effect6)
TEMPLATE_SELECTION = team_awakening.TEMPLATE

_BUFF_PROPERTY = {"atk_pct": "AtkUp", "atk_flat": "AtkAdd", "crit_rate": "CritBase", "crit_dmg": "CritDamageBase",
                  "dmg_all": "DamageUpGeneralBase", "def_ignore": "DefIgnore", "mag": "MagBase"}
_TRACE_SLOT = {"support": "qte", "basic": "basic", "skill": "skill", "skill_hold": "skill", "ult": "ultimate",
               "entry_attack": "entry"}
_RESISTANCE_KEYS = ("chaos", "cosmos", "incantation", "lakshana", "nature", "normal", "psyche", "psychically")
_LISTED_SCOPES = ("team", "team_others", "target")


# ── options ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MemberResource:
    e_cd_s: float | None = None
    q_cd_s: float | None = None
    q_cost: float | None = None
    start_energy: float | None = None      # None = q_cost (the first ultimate is available)
    charge_eff: float | None = None        # fraction (0.18 = +18%); None = automatic


@dataclass(frozen=True)
class ManualBuff:
    kind: str
    value: float                           # percent kinds: percent as typed (20 = 20%)
    target: Any = "team"                   # "team" | character id | "enemy" (res_down)
    element: str | None = None             # dmg_element / res_down: element code; None = all (res_down only)
    start_s: float | None = None           # wall seconds from the battle start; None = from the start
    end_s: float | None = None             # None = to the end of the fight
    enabled: bool = True


@dataclass(frozen=True)
class TargetOptions:
    enemy_level: int = 80
    resistance: float = 0.2
    defense_reduction: float = 0.0
    vulnerability: float = 0.0
    boss: bool = False                     # a boss enemy (awakening node rules: Sagiri ⑤ / 共鸣6, Hathor ③ ...)
    enemy_count: int = 1                   # enemies hit (node rules with a 'single enemy' condition: Mint ④)


@dataclass(frozen=True)
class CustomOptions:
    repeat: int = 1
    gauge_mode: str = "as_typed"
    start_gauge: Mapping = field(default_factory=dict)       # character id -> 0..100 (missing member = 100)
    gauge_reset_each_repeat: bool = False
    resource_check: str = "warn"
    resources: Mapping = field(default_factory=dict)         # character id -> MemberResource
    disabled_buffs: frozenset = frozenset()                  # team_simulation_service.buff_key values
    manual_buffs: tuple = ()
    target: TargetOptions = TargetOptions()
    swap_time_s: float = 0.0
    # resource level the defaults come from (team_resources.RESOURCE_MODELS; None = DEFAULT_RESOURCE_MODEL) and the
    # longest cooldown wait the "wait" / "strict" checks insert (None = up to the 60 s guard); optional saved keys
    resource_model: str | None = None
    cd_wait_max_s: float | None = None


@dataclass(frozen=True)
class CustomPreview:
    """Result of preview_custom: resolved steps on the palette clock (damage and hits are 0)."""

    steps: tuple = ()                       # tuple[CustomStepTrace, ...]
    wall_time_s: float = 0.0
    active_time_s: float = 0.0
    warnings: int = 0


class CustomCycleError(ValueError):
    """The sequence cannot be simulated; ``issues`` holds the ParseIssue list."""

    def __init__(self, issues) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{i.code}{list(i.args)}" for i in self.issues) or "invalid custom cycle")


def _clamp(value, lo, hi, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return max(lo, min(hi, number))


def _optional(value, lo, hi):
    if value is None or value == "":
        return None
    out = _clamp(value, lo, hi, None)
    return out


def manual_buff_range(kind: str) -> tuple[float, float]:
    """(lowest, highest) value a manual buff of this kind can have."""
    return MANUAL_BUFF_RANGES.get(kind, (-MANUAL_BUFF_LIMIT, MANUAL_BUFF_LIMIT))


def _clean_manual(buffs) -> tuple:
    """Manual buffs with their values clamped to the kind's range; a value that is not a number drops the buff."""
    out = []
    for buff in buffs or ():
        if not isinstance(buff, ManualBuff):
            continue
        value = _clamp(buff.value, *manual_buff_range(buff.kind), None)
        if value is not None:
            out.append(buff if value == buff.value else dataclasses.replace(buff, value=value))
    return tuple(out)


def resource_model_of(options: CustomOptions | None) -> str:
    from src.services.team_resources import DEFAULT_RESOURCE_MODEL, RESOURCE_MODELS

    model = getattr(options, "resource_model", None) if options is not None else None
    return model if model in RESOURCE_MODELS else DEFAULT_RESOURCE_MODEL


def default_resources(character_id: int, model: str | None = None) -> MemberResource:
    """E / Q cooldown and Q cost of the member at a resource level (blank = unknown / not enforced there).

    ``legacy`` keeps the shipped custom-mode table (team_custom_actions.RESOURCES); ``data`` / ``community`` read
    team_resource_data: the cooldown cells that level enforces and a Q cost from game data only (members with an
    own resource - Hotori's clock, Shinku's meter - have no ultimate-energy cost)."""
    from src.services import team_resources as tr

    model = model if model in tr.RESOURCE_MODELS else tr.DEFAULT_RESOURCE_MODEL
    cid = int(character_id)
    if model == "legacy":
        from src.services import team_custom_actions as data

        row = data.RESOURCES.get(cid) or {}
        return MemberResource(**{k: float(v[0]) for k, v in row.items() if k in ("e_cd_s", "q_cd_s", "q_cost")})
    policy = tr.policy_for(model)
    values = {}
    for key, kind in (("e_cd_s", "E"), ("q_cd_s", "Q")):
        cell = tr.cd_cell(cid, kind, policy)
        if cell is not None and float(cell[0]) > 0:
            values[key] = float(cell[0])
    rec = tr.record(cid)
    if (rec.get("energy") or {}).get("kind", "ultimate") == "ultimate":
        cost = tr.cost_cell(cid, policy)
        if cost is not None:
            values["q_cost"] = float(cost[0])
    return MemberResource(**values)


def default_options(team_ids: Sequence[int], model: str | None = None) -> CustomOptions:
    """Start gauge 100, data-backed E / Q numbers of the resource level, everything else default."""
    team = [int(c) for c in team_ids]
    model = resource_model_of(CustomOptions(resource_model=model))
    return CustomOptions(start_gauge={cid: 100.0 for cid in team},
                         resources={cid: default_resources(cid, model) for cid in team}, resource_model=model)


def normalise_options(options: CustomOptions | None, team_ids: Sequence[int]) -> CustomOptions:
    """Clamp every number to its range; members without a value get the defaults."""
    team = [int(c) for c in team_ids]
    model = resource_model_of(options)          # a saved cycle without the key follows the default level
    base = default_options(team, model)
    if options is None:
        return base
    start = {cid: _clamp((options.start_gauge or {}).get(cid, 100.0), 0.0, 100.0, 100.0) for cid in team}
    resources = {}
    for cid in team:
        r = (options.resources or {}).get(cid)
        if r is None:
            resources[cid] = base.resources[cid]
            continue
        resources[cid] = MemberResource(
            e_cd_s=_optional(r.e_cd_s, 0.0, 600.0), q_cd_s=_optional(r.q_cd_s, 0.0, 600.0),
            q_cost=_optional(r.q_cost, 0.0, 100000.0), start_energy=_optional(r.start_energy, 0.0, 100000.0),
            charge_eff=_optional(r.charge_eff, -1.0, 10.0))
    target = options.target or TargetOptions()
    manual = _clean_manual(options.manual_buffs)
    return CustomOptions(
        repeat=int(_clamp(options.repeat, 1, MAX_REPEAT, 1)),
        gauge_mode=options.gauge_mode if options.gauge_mode in GAUGE_MODES else "as_typed",
        start_gauge=start, gauge_reset_each_repeat=bool(options.gauge_reset_each_repeat),
        resource_check=options.resource_check if options.resource_check in RESOURCE_CHECKS else "warn",
        resources=resources, disabled_buffs=frozenset(str(k) for k in (options.disabled_buffs or ())),
        manual_buffs=manual,
        target=TargetOptions(enemy_level=int(_clamp(target.enemy_level, 1, 100, 80)),
                             resistance=_clamp(target.resistance, -1.0, 1.0, 0.2),
                             defense_reduction=_clamp(target.defense_reduction, 0.0, 1.0, 0.0),
                             vulnerability=_clamp(target.vulnerability, 0.0, 2.0, 0.0),
                             boss=bool(getattr(target, "boss", False)),
                             enemy_count=int(_clamp(getattr(target, "enemy_count", 1), 1, MAX_ENEMIES, 1))),
        swap_time_s=_clamp(options.swap_time_s, 0.0, MAX_SWAP_TIME_S, 0.0),
        resource_model=model, cd_wait_max_s=_optional(getattr(options, "cd_wait_max_s", None), 0.0, CD_WAIT_GUARD_S))


def options_to_json(options: CustomOptions) -> dict:
    out = {
        "repeat": int(options.repeat), "gauge_mode": options.gauge_mode,
        "start_gauge": {str(cid): float(v) for cid, v in (options.start_gauge or {}).items()},
        "gauge_reset_each_repeat": bool(options.gauge_reset_each_repeat),
        "resource_check": options.resource_check,
        "resources": {str(cid): dataclasses.asdict(r) for cid, r in (options.resources or {}).items()},
        "disabled_buffs": sorted(options.disabled_buffs or ()),
        "manual_buffs": [dataclasses.asdict(b) for b in (options.manual_buffs or ())],
        "target": _target_json(options.target or TargetOptions()),
        "swap_time_s": float(options.swap_time_s),
    }
    # optional keys (store VERSION unchanged: older builds ignore them, files without them load as before)
    if getattr(options, "resource_model", None):
        out["resource_model"] = options.resource_model
    if getattr(options, "cd_wait_max_s", None) is not None:
        out["cd_wait_max_s"] = float(options.cd_wait_max_s)
    return out


def _target_json(target: TargetOptions) -> dict:
    """The saved target: the four numbers always, boss / enemy_count only when not the default (store VERSION unchanged:
    files of default options are byte-identical to older builds, older builds ignore the keys)."""
    out = {"enemy_level": target.enemy_level, "resistance": target.resistance,
           "defense_reduction": target.defense_reduction, "vulnerability": target.vulnerability}
    if getattr(target, "boss", False):
        out["boss"] = True
    if int(getattr(target, "enemy_count", 1) or 1) != 1:
        out["enemy_count"] = int(target.enemy_count)
    return out


def options_from_json(obj, team_ids: Sequence[int] = ()) -> CustomOptions:
    """Saved options -> CustomOptions.  Never raises: unknown fields are ignored, numbers clamped."""
    team = [int(c) for c in team_ids]
    if not isinstance(obj, dict):
        return default_options(team)

    def int_keys(value) -> dict:
        out = {}
        for key, item in (value.items() if isinstance(value, dict) else ()):
            try:
                out[int(key)] = item
            except (TypeError, ValueError):
                continue
        return out

    resources = {}
    for cid, row in int_keys(obj.get("resources")).items():
        if isinstance(row, dict):
            resources[cid] = MemberResource(**{k: row.get(k) for k in ("e_cd_s", "q_cd_s", "q_cost", "start_energy",
                                                                       "charge_eff")})
    manual = []
    for row in obj.get("manual_buffs") if isinstance(obj.get("manual_buffs"), list) else ():
        if not isinstance(row, dict) or row.get("kind") not in MANUAL_BUFF_KINDS:
            continue
        value = _clamp(row.get("value"), *manual_buff_range(row["kind"]), None)
        if value is None:
            continue
        target = row.get("target", "team")
        if target not in ("team", "enemy"):
            try:
                target = int(target)
            except (TypeError, ValueError):
                target = "team"
        element = row.get("element") if row.get("element") in ELEMENTS else None
        manual.append(ManualBuff(kind=row["kind"], value=value, target=target, element=element,
                                 start_s=_optional(row.get("start_s"), 0.0, 36000.0),
                                 end_s=_optional(row.get("end_s"), 0.0, 36000.0),
                                 enabled=bool(row.get("enabled", True))))
    target = obj.get("target") if isinstance(obj.get("target"), dict) else {}
    options = CustomOptions(
        repeat=obj.get("repeat", 1), gauge_mode=obj.get("gauge_mode", "as_typed"),
        start_gauge=int_keys(obj.get("start_gauge")),
        gauge_reset_each_repeat=bool(obj.get("gauge_reset_each_repeat", False)),
        resource_check=obj.get("resource_check", "warn"), resources=resources,
        disabled_buffs=frozenset(k for k in (obj.get("disabled_buffs") if isinstance(obj.get("disabled_buffs"), list)
                                             else ()) if isinstance(k, str)),
        manual_buffs=tuple(manual),
        target=TargetOptions(enemy_level=target.get("enemy_level", 80), resistance=target.get("resistance", 0.2),
                             defense_reduction=target.get("defense_reduction", 0.0),
                             vulnerability=target.get("vulnerability", 0.0), boss=bool(target.get("boss", False)),
                             enemy_count=target.get("enemy_count", 1)),
        swap_time_s=obj.get("swap_time_s", 0.0),
        resource_model=obj.get("resource_model") if isinstance(obj.get("resource_model"), str) else None,
        cd_wait_max_s=obj.get("cd_wait_max_s"))
    if "resource_model" not in obj and options.resources:
        # saved by a build before the resource levels: its fields that still hold that build's defaults (the legacy
        # custom table, e.g. Lacrimosa's contested 45) follow the current level's defaults, typed values stay
        options = dataclasses.replace(options, resources=_migrate_legacy_defaults(options.resources))
    if team:
        return normalise_options(options, team)
    # no team given: clamp what does not depend on it
    members = sorted(set(options.start_gauge) | set(options.resources))
    return normalise_options(options, members)


def _migrate_legacy_defaults(resources: Mapping) -> dict:
    """Resource rows of a cycle saved before the resource levels: a field equal to the legacy table's default is
    replaced by the default of the current level (review F5); anything else is the user's own number."""
    out = {}
    for cid, row in (resources or {}).items():
        try:
            key = int(cid)
            old, new = default_resources(key, "legacy"), default_resources(key, None)
        except Exception:
            out[cid] = row
            continue
        values = {}
        for name in ("e_cd_s", "q_cd_s", "q_cost"):
            value = getattr(row, name)
            try:
                same = (value is None and getattr(old, name) is None) or (
                    value is not None and getattr(old, name) is not None and float(value) == float(getattr(old, name)))
            except (TypeError, ValueError):
                same = False
            values[name] = getattr(new, name) if same else value
        out[cid] = dataclasses.replace(row, **values)
    return out


def target_condition(target: TargetOptions) -> dict:
    """The engine's target dict; with the defaults it equals team_simulation_service.DEFAULT_TARGET."""
    out = {"confirmed": True, "enemy_level": int(target.enemy_level), "scene": "outer_realm",
           "resistances": {k: float(target.resistance) for k in _RESISTANCE_KEYS}}
    if target.defense_reduction:
        out["defense_reduction"] = float(target.defense_reduction)
    if target.vulnerability:
        out["vulnerability"] = float(target.vulnerability)
    if getattr(target, "boss", False):          # node rules only (the engine ignores the key)
        out["boss"] = True
    if int(getattr(target, "enemy_count", 1) or 1) != 1:
        out["enemy_count"] = int(target.enemy_count)
    return out


# ── walker ─────────────────────────────────────────────────────────────────
@dataclass
class _Measured:
    length_us: int
    hits: int = 0
    energy: float = 0.0
    status: str = "ok"                    # ok | missing_candidate
    credit: Any = None                    # team_resource_data.HIT_CREDIT cell applied (summon hits not laid out)
    event_energy: float = 0.0             # node-rule energy events of the action (not scaled by the efficiency)


@dataclass
class _Member:
    last: tuple | None = None             # (table id, slot, index) of the previous slot action
    last_key: tuple | None = None         # previous action key (basic_after)
    state: str = ""                       # transformation state code ("" = none); may have run out
    state_start_us: int = 0               # wall µs of the state start
    state_paused_us: int = 0              # active µs spent off the field (pauses_off_field states)
    off_since_us: int | None = None       # wall µs of the last swap out
    cd: dict = field(default_factory=dict)        # "E" / "Q" -> wall µs of the last use
    form: dict | None = None              # the visit's form summary this state fills (FORMS-backed states)
    charge_ready: dict = field(default_factory=dict)   # kind -> active µs at which spent charges are back (E x3)
    energy: float | None = None           # strict check: online ultimate-energy pool (None = cost unknown)


@dataclass
class _Resolved:
    table_id: str                         # state code, "" = base
    index: int
    entry: tuple
    table: dict
    notes: list
    expired: bool = False                 # the member's state ran out: it is cleared when the step runs


@dataclass
class _Rec:
    index: int
    source_index: int
    repeat_index: int
    character_id: int
    action: str
    pos: int | None = None
    state: str = ""
    slot: str = "other"
    keys: tuple = ()
    name_zh: str = ""
    start_us: int = 0
    end_us: int = 0
    wait_before_us: int = 0
    hits: int = 0
    status: str = "ok"
    entry: str = ""
    swap_index: int | None = None
    reaction_zh: str = ""
    gauge_before: float = 0.0
    gauge_after: float = 0.0
    out_gauge: float | None = None
    out_character_id: int | None = None
    energy_after: float | None = None
    notes: list = field(default_factory=list)
    visit_index: int = 0
    step_index: int | None = None
    energy_gain: float = 0.0
    energy_event: float = 0.0             # awakening node-rule energy (events: not scaled by the charge efficiency)
    cd_kind: str = ""
    energy_gained: float | None = None    # ultimate energy since the member's last ultimate (cost unknown: display)
    clock_after: float | None = None      # own clock (Hotori) after the step (resource levels)


@dataclass
class _Walk:
    layout: Any                           # team_simulation_service._Layout
    records: list
    waited_us: int = 0
    states_entered: bool = False
    own_resource: tuple = ()              # OWN_RESOURCE members that used their ultimate
    plain_swaps: int = 0
    unchecked_cd: tuple = ()              # ((character id, "E" | "Q"), ...) used again with a blank cooldown
    skipped_energy: int = 0               # strict: ultimates skipped for energy
    skipped_cd: int = 0                   # wait / strict: presses skipped beyond the longest wait
    strict_eff: dict = field(default_factory=dict)   # strict: the charge efficiency the online pool used
    clock_members: tuple = ()             # own-clock members (Hotori) whose clock the walk checked
    clock_waits: int = 0                  # waits inserted for the own clock
    rules_used: dict = field(default_factory=dict)      # cid -> sorted rule codes applied (resource levels)
    clock_interludes: dict = field(default_factory=dict)   # cid -> (seconds credited, per-ultimate seconds)
    hit_credited: dict = field(default_factory=dict)    # cid -> uses whose summon hits were credited
    hit_unknown: tuple = ()               # members that used an action with summon hits of unknown count
    early_swaps: int = 0                  # strict, team (D3): presses not ready -> the member swapped out at once
    swap_dropped: int = 0                 # typed inputs of those members not run after their early swap


class _PaletteMeasure:
    """Numbers from the generated palette: no database, no hit rows (preview and conversion)."""

    def __init__(self, gauge, stops: list, hit_credits=None) -> None:
        from src.services import team_custom_actions as data
        from src.services import team_simulation_service as svc

        self._data, self._svc, self.gauge, self.stops = data, svc, gauge, stops
        self.hit_credits = hit_credits        # resource levels: team_resource_data.HIT_CREDIT
        self.rows: list = []
        self.side: dict = {}
        self.stop_owners: list = []
        self.unknown_stop: set = set()
        self.form_actions: dict = defaultdict(lambda: defaultdict(int))
        self.missing: dict = defaultdict(list)

    def action(self, cid: int, key: tuple, t0: int, vi: int, si: int, run) -> _Measured:
        action = self._data.ACTIONS.get(tuple(key))
        if action is None:
            self.missing[cid].append(f"{key[0]}:{key[1]}")
            return _Measured(0, 0, 0.0, "missing_candidate")
        if action["time_stop_s"]:
            self._svc._add_stop(self.stops, self.stop_owners, t0, action["time_stop_s"], (cid, key[0]))
        elif run.slot == "ultimate":
            self.unknown_stop.add(cid)
        self.gauge.gain(cid, action["gauge"])
        energy, credit = float(action["energy"]), None
        if self.hit_credits is not None and not int(action["hits"]):
            cell = self.hit_credits.get((int(cid), str(key[0]), str(key[1] or "")))
            if cell is not None:
                credit = cell
                if cell[0] is not None:
                    self.gauge.gain(cid, cell[1])
                    energy += float(cell[0])
        return _Measured(self._svc._us(action["length_s"]), int(action["hits"]), energy, credit=credit)


class _AxisMeasure:
    """Hit rows on the simulator axis, exactly as the approved layout places them (lengths, gauge and energy
    gains come from the static database, not from the generated numbers)."""

    def __init__(self, ctx, writer) -> None:
        from src.services import team_custom_actions as data
        from src.services import team_simulation_service as svc

        self._data, self._svc, self.ctx, self.writer = data, svc, ctx, writer
        self.rows, self.side = writer.rows, writer.side
        self.stop_owners, self.unknown_stop = writer.stop_owners, writer.unknown_stop
        self.form_actions = writer.form_actions
        self.missing: dict = defaultdict(list)

    def action(self, cid: int, key: tuple, t0: int, vi: int, si: int, run) -> _Measured:
        key = tuple(key)
        action = self._data.ACTIONS.get(key) or {}
        if key not in self.ctx.by_key:        # a static database newer than the generated palette
            self.missing[cid].append(f"{key[0]}:{key[1]}")
            return _Measured(self._svc._us(action.get("length_s") or 0.0), 0, 0.0, "missing_candidate")
        before = len(run.rows)
        length = self.writer.place(cid, vi, si, run, key, t0, action.get("est_s"))
        if length <= 0 and action.get("length_source") == "last_hit":
            length = self._svc._us(action["length_s"])    # channel montage: _step_length_us has no length for it
        rows = run.rows[before:]
        energy = sum(float((self.writer.skill_damage(r["gameplay_effect_name"]) or {}).get("charge_add") or 0.0)
                     for r in rows)
        credit = self.writer.last_credit
        if credit is not None:                # summon hits the animation does not lay out (writer gained the gauge)
            energy += float(credit[0])
        elif not rows and self.writer.hit_credits is not None:
            credit = self.writer.hit_credits.get((int(cid), str(key[0]), str(key[1] or "")))   # unknown count: named
        event = self.writer.take_node_energy(cid) if hasattr(self.writer, "take_node_energy") else 0.0
        return _Measured(int(length), len(rows), energy, credit=credit, event_energy=event)


class _Walker:
    """Executes custom steps on one timeline (see the module docstring)."""

    def __init__(self, team_ids, elements, rules, options: CustomOptions, measure, gauge, stops: list,
                 sched=None, awakening: Mapping | None = None, eff_override: Mapping | None = None,
                 node_rules=None, layout_hooks=None) -> None:
        from src.services import team_custom_actions as data
        from src.services import team_simulation_explanation as tx
        from src.services import team_simulation_service as svc
        from src.services.team_form_actions import FORMS

        self.data, self.tx, self.svc = data, tx, svc
        self.team = [int(c) for c in team_ids]
        self.elements = {int(c): str(e or "") for c, e in dict(elements).items()}
        self.rules, self.options, self.measure, self.gauge = rules, options, measure, gauge
        self.stops, self.sched = stops, sched
        self.form_codes = {str(r["code"]) for r in FORMS.values()}
        self.t = svc.START_US
        self.rep = 0
        self.seq = 0
        self.on_field: int | None = None
        self.visit = None
        self.visits: list = []
        self.swaps: list = []
        self.records: list[_Rec] = []
        self.members = {cid: _Member() for cid in self.team}
        self.waited_us = 0
        self.plain_swaps = 0
        self.states_entered = False
        self.own_resource: set = set()
        self.unchecked_cd: set = set()
        self.used_default = self.used_gauge_set = self.used_normal = False
        self.extra_missing: dict = defaultdict(list)
        self.skipped_energy = 0               # strict: ultimates skipped for energy
        self.skipped_cd = 0                   # wait / strict: presses skipped beyond the longest wait
        self._charges = {cid: self._charge_count(cid) for cid in self.team}
        self.clock_waits = 0
        # D3 (strict, team): the member that swapped out early (its inputs are dropped until another member's step)
        self._swap_out: int | None = None
        self._judge_entry = False             # the next swap follows an early swap: judged by the gauge (review F5)
        self._resumed_left = None             # cooldown left after an all-blocked wait, under the threshold (10-18)
        self._other_ahead = False             # a later typed step belongs to another member (someone to swap to)
        self._seq_steps: list = []            # the typed steps and the position of the step running (run())
        self._src, self._reps = 0, 1
        self.early_swaps = 0
        self.swap_dropped = 0
        # team_resource_data rules (awakening / skill effects on cooldowns) at the resource levels (review F-A)
        self.model = resource_model_of(options)
        self.rules_on = self.model != "legacy"
        # A11: {cid: team_awakening.AwakeningSel} (an int = legacy level Effect1..level)
        self.awakening = {int(c): team_awakening.coerce(v, team_awakening.EMPTY)
                          for c, v in dict(awakening or {}).items()}
        self.node_rules = node_rules          # awakening_node_rules.Prepared: extra resource rows (None = none)
        self.layout_hooks = layout_hooks      # awakening_node_rules.LayoutHooks: free_support (None = none)
        self.rules_used: dict = defaultdict(set)
        self._basics: dict = defaultdict(int)          # basic presses since the member's last E
        self._extra_used: dict = defaultdict(bool)     # the extra E after the basics was used since that E
        self.hit_credited: dict = defaultdict(int)
        self.hit_unknown: set = set()
        self._last_reset: dict = {}                    # (cid, reset code) -> active µs it last fired (ICD)
        # the static DB of the run (None in the preview: the application's DB) - Global live overlay windows
        self._static_path = getattr(getattr(getattr(measure, "ctx", None), "static", None), "database_path", None)
        self._clock, self._clock_members = self._new_clock()
        self._eff = {}
        if options.resource_check == "strict":
            for cid in self.team:
                r = (options.resources or {}).get(cid)
                if r is None or r.q_cost is None or cid in data.OWN_RESOURCE:
                    continue
                start = float(r.q_cost) if r.start_energy is None else float(r.start_energy)
                self.members[cid].energy = max(0.0, min(float(r.q_cost), start))
                # the build's charge efficiency once the engine has shown it (review F-C); a typed value wins
                self._eff[cid] = float(r.charge_eff) if r.charge_eff is not None else (
                    self._own_eff(cid) + float((eff_override or {}).get(cid, 0.0) or 0.0))

    def _new_clock(self):
        """Hotori's own clock as a team_resources state (resource levels with a check), else None."""
        model = resource_model_of(self.options)
        if model == "legacy" or self.options.resource_check == "off":
            return None, ()
        from src.services import team_resources as tr

        own = tuple(c for c in self.team if (tr.record(c).get("energy") or {}).get("kind") == "own_clock")
        if not own:
            return None, ()
        policy = tr.policy_for(model, cooldown="off")      # cooldowns stay the walker's own (typed values)
        # the whole team: ResourceState treats a one-member list as solo (Hotori's interlude would then be a wait)
        return tr.ResourceState(list(self.team), policy=policy, stops=self.stops, solo=len(self.team) < 2,
                                awakening=self.awakening), own

    def _rules(self, cid: int, code: str, kind: str | None = None) -> list:
        """team_resource_data rules of the member unlocked at its awakening (resource levels only)."""
        if not self.rules_on:
            return []
        from src.services import team_resources as tr

        # A9: the rule's node (number n = Effect n) against the card's node set (template set without a card)
        selection = self.awakening.get(int(cid), TEMPLATE_SELECTION)
        rows = tuple(tr.record(cid).get("rules") or ())
        if self.node_rules is not None:
            rows += self.node_rules.resource_rules(cid)
        return [r for r in rows
                if r[0] == code and (kind is None or r[1] == kind) and team_awakening.unlocked(selection, r[3])]

    def _cd_offset_us(self, cid: int, kind: str) -> int:
        """The cooldown starts this long after the press (team_resource_data cd_offset_s; resource levels)."""
        if not self.rules_on or not kind:
            return 0
        from src.services import team_resources as tr

        offset = (tr.record(cid).get("cd_offset_s") or {}).get(kind)
        return self.svc._us(float(offset)) if offset else 0

    def _reset_cd(self, cid: int, code: str, selectors=None) -> None:
        """A rule that refreshes a cooldown (Linko A3 Q -> E, Mint A1 counter -> E, Sagiri ⑤ held E -> Q) fired.
        ``selectors`` = the selectors of the E press (e_resets_q); an internal cooldown (team_resources.reset_icd_s)
        keeps a reset from firing again too soon (active clock)."""
        from src.services import team_resources as tr

        m = self.members[cid]
        target = target_condition(self.options.target or TargetOptions())
        now = self._active(0, self.t)
        for rule in self._rules(cid, code):
            if code == "e_resets_q" and not any(tr.reset_matches(rule[2], s, target) for s in (selectors or ())):
                continue
            icd = tr.reset_icd_s(self._rules(cid, "reset_icd", code), code, rule[2])
            last = self._last_reset.get((cid, code))
            if icd and last is not None and now - last < self.svc._us(icd):
                continue                        # inside the reset's internal cooldown (Mint ① 3 s)
            self._last_reset[(cid, code)] = now
            m.cd.pop(rule[1], None)
            m.charge_ready.pop(rule[1], None)
            self.rules_used[cid].add(code)

    def _swap_ok(self) -> bool:
        """D3 (2026-10-14): the strict check swaps the member out at once when a press is not ready - if another
        member is typed after it; alone (or at the end of the cycle) it waits / skips as before."""
        return self.options.resource_check == "strict" and len(self.team) > 1 and self._other_ahead

    def _short_wait(self, remaining_us: int) -> bool:
        """User decision 2026-10-18: with the strict swap rule a cooldown with less than SWAP_MIN_WAIT_S (0.3 s) of
        battle time left is waited for and the press made (no swap); alone it waits anyway."""
        from src.services.team_resources import SWAP_MIN_WAIT_S

        return self._swap_ok() and int(remaining_us) < self.svc._us(SWAP_MIN_WAIT_S)

    def _upcoming(self) -> list:
        """Typed steps after the one running: the rest of this pass, then the next pass (if any)."""
        out = list(self._seq_steps[self._src + 1:])
        if self.rep + 1 < self._reps:
            out += list(self._seq_steps)
        return out

    def _press_kind(self, step: CustomStep) -> str:
        """Cooldown kind ("E" / "Q" / "") a typed press would check now (pure; as _press resolves it)."""
        cid, action = int(step.character_id), step.action
        if action in ENTRY_ACTIONS or action in ("wait", "dodge"):
            return ""
        if action == RAW_ACTION:
            where = self.data.ACTION_INDEX.get(tuple(step.raw or ("", "")))
            if where and where[0] == "":
                return "E" if where[1] in ("skill", "skill_hold") else ("Q" if where[1] == "ult" and where[2] == 1
                                                                        else "")
            return ""
        resolved = self.resolve(cid, action, step.pos, self.t)
        if resolved is None:
            return ""
        kind = str(resolved.table.get("cd") or "")
        return "" if kind == "Q" and resolved.index != 0 else kind

    def _next_presses(self, cid: int) -> list:
        """[(member, kind)] in typed order: every other member typed later, with the cooldown kind of the first press
        of its next stint that has one ("" = that stint has none: the member can act at once)."""
        result: dict = {}
        prev, current = cid, None
        for step in self._upcoming():
            c = int(step.character_id)
            if c not in self.members:
                continue
            if c != prev:                       # a new stint; only the first stint of each other member counts
                prev = c
                current = c if (c != cid and c not in result) else None
                if current is not None:
                    result[c] = ""
            if current is None or result[current]:
                continue
            result[current] = self._press_kind(step)
        return list(result.items())

    def _press_remaining(self, cid: int, kind: str, t_us: int) -> int | None:
        """Active µs until a strict press of ``kind`` by the member could run at ``t_us`` (0 = ready; None = never by
        waiting: a typed ultimate cost its pool cannot pay).  The checks of _press, without their effects."""
        m = self.members[cid]
        res = (self.options.resources or {}).get(cid)
        if (kind == "Q" and m.energy is not None and res is not None and res.q_cost is not None
                and m.energy + 1e-6 < float(res.q_cost)):
            return None
        remaining = 0
        value = self._cd_value(cid, kind, note=False)
        charges = self._charges.get(cid, 1) if kind == "E" else 1
        if kind and value is not None:
            if charges > 1:
                now_pc = self._active(0, t_us)
                pending = [r for r in m.charge_ready.get(kind, ()) if r > now_pc]
                if len(pending) >= charges:
                    remaining = min(pending) - now_pc
            elif kind in m.cd:
                remaining = self.svc._us(value) - self._active(m.cd[kind], t_us)
        if kind == "E" and remaining > CD_TOLERANCE_US:
            for rule in self._rules(cid, "extra_e_after_basics", "E"):
                if not self._extra_used[cid] and self._basics[cid] >= int(rule[2] or 0):
                    remaining = 0
                break
        if self._clock is not None and cid in self._clock_members and kind in ("E", "Q"):
            from src.services.team_resources import StepClass

            cls = StepClass(None, "q_cost" if kind == "Q" else "e_cost", "custom")
            state = self._clock.members.get(cid)
            clock = self._clock.peek_remaining(cid, cls, t_us, interlude=bool(state and state.interlude_pending))
            if clock is None:
                return None
            remaining = max(remaining, int(clock))
        return int(remaining) if remaining > CD_TOLERANCE_US else 0

    def _choice(self, cid: int, own_us) -> tuple:
        """D3 in a strict team cycle (the reviewed layout's rule): ("swap", 0, None) when a member typed later could
        act at once; every one of them blocked too: ("run", 0, cid) this member is ready first (its own wait),
        ("wait_swap", active µs, other) wait for ``other`` then swap out, ("keep", 0, None) nothing gets ready within
        the longest wait (the old wait / skip)."""
        rems = []
        for other, kind in self._next_presses(cid):
            r = self._press_remaining(other, kind, self.t) if kind else 0
            if r is not None and r <= CD_TOLERANCE_US:
                return "swap", 0, None
            rems.append((r, other))
        cands = [(r, i, c) for i, (r, c) in enumerate([(own_us, cid)] + rems) if r is not None]
        if not cands:
            return "keep", 0, None
        r, _i, who = min(cands)
        limit = self.options.cd_wait_max_s
        limit = CD_WAIT_GUARD_S if limit is None else min(float(limit), CD_WAIT_GUARD_S)
        if r > self.svc._us(limit) + CD_TOLERANCE_US:
            return "keep", 0, None
        if who == cid:
            return ("keep", 0, None) if own_us is None else ("run", 0, cid)
        return "wait_swap", int(r), who

    def _not_ready(self, src: int, cid: int, action: str, slot: str, info: dict | None, notes: list, reason: str,
                   kind: str, own_us, energy=None, cost=None) -> bool:
        """A strict press that is not ready (D3).  True: replaced by an early swap (after waiting for the earliest
        ready member when every typed member is blocked).  False: the old wait / skip goes on - alone, nobody typed
        after it, or this member is the earliest ready one (``self._blocked_wait`` names it for the wait note)."""
        self._blocked_wait = None
        if not self._swap_ok():
            return False
        how, wait_us, other = self._choice(cid, own_us)
        if how == "run":
            self._blocked_wait = cid
            return False
        if how == "keep":
            return False
        left = own_us
        if how == "wait_swap":               # every typed member blocked: wait for the earliest ready one, then swap
            wall = self._advance(self.t, wait_us) - self.t
            rec = self._time_step(-1, cid, "wait", wall)
            rec.notes.append(self.tx.note(self.tx.NOTE_CUSTOM_ALL_BLOCKED, round(wall / 1e6, 3), other))
            self.waited_us += wall
            self.seq += 1
            left = None if own_us is None else max(0, int(own_us) - int(wait_us))
            if reason == "cd" and left is not None and self._short_wait(left):
                self._resumed_left = left        # now under the threshold: wait it out and press (2026-10-18)
                return False
        self._swap_out_now(src, cid, action, slot, info, notes, reason, kind, left, energy, cost)
        return True

    def _swap_out_now(self, src: int, cid: int, action: str, slot: str, info: dict | None, notes: list, reason: str,
                      kind: str, remaining_us, energy=None, cost=None) -> None:
        """The press is not ready (strict, team): no time, no hits; the member's next inputs are dropped until
        another member's step - that step's entry (as typed) is the swap."""
        tx = self.tx
        self._skip(src, cid, action, slot, info, notes, tx.STEP_SWAP_OUT,
                   tx.note(tx.NOTE_CUSTOM_SWAP_OUT, reason, kind or "", round(max(0, int(remaining_us or 0)) / 1e6, 3),
                           None if energy is None else round(float(energy), 3), cost))
        self._swap_out = cid
        self.early_swaps += 1
        if kind == "Q" and reason == "clock" and cid in self.data.OWN_RESOURCE:
            self.own_resource.add(cid)          # the ultimate was checked against the member's own clock

    def _drop(self, step: CustomStep, src: int) -> None:
        """A typed input of the member that swapped out early (D3): listed, not run."""
        tx, cid = self.tx, int(step.character_id)
        rec = self._new_rec(src, cid, step.action)
        rec.slot, rec.status = _TRACE_SLOT.get(step.action, "other"), tx.STEP_SWAP_DROPPED
        rec.notes.append(tx.note(tx.NOTE_CUSTOM_SWAP_DROPPED))
        rec.gauge_after = rec.gauge_before
        self.records.append(rec)
        self.swap_dropped += 1

    def _clock_gate(self, cid: int, cd_kind: str, src: int, notes: list, decide=None):
        """Own clock before an E / Q press: (class, gate) or (None, None); inserts the wait (wait / strict).
        ``decide(own µs) -> bool``: D3 - True when the press swapped the member out instead (gate returned, no wait)."""
        if self._clock is None or cid not in self._clock_members or cd_kind not in ("E", "Q"):
            return None, None
        from src.services.team_resources import StepClass

        cls = StepClass(None, "q_cost" if cd_kind == "Q" else "e_cost", "custom")
        gate = self._clock.gate(cid, cls, self.t)
        if gate.wait_us > CD_TOLERANCE_US:
            seconds = round(gate.wait_us / 1e6, 3)       # the inserted (wall) seconds (review F-E)
            if decide is not None and decide(int(gate.remaining_us)):
                return cls, gate                         # D3: swapped out instead (the caller returns)
            if self.options.resource_check in ("wait", "strict"):
                self._time_step(-1, cid, "wait", int(gate.wait_us))
                self.waited_us += int(gate.wait_us)
                self.seq += 1
                self.clock_waits += 1
                notes.append(self.tx.note(self.tx.NOTE_CUSTOM_CLOCK_WAITED, seconds))
                if getattr(self, "_blocked_wait", None) is not None:     # every member blocked, this one first
                    notes.append(self.tx.note(self.tx.NOTE_CUSTOM_ALL_BLOCKED, seconds, cid))
            else:
                need = 120.0 if cd_kind == "Q" else 60.0
                notes.append(self.tx.note(self.tx.NOTE_CUSTOM_CLOCK_SHORT, round(float(gate.energy_before or 0.0), 3),
                                          need, seconds))
        return cls, gate

    def _charge_count(self, cid: int) -> int:
        """E charges of the member at the options' resource level (Chiichan stores 3 uses); 1 otherwise."""
        try:
            from src.services import team_resources as tr

            model = resource_model_of(self.options)
            if model == "legacy":
                return 1
            cell = tr.record(cid).get("e_charges")
            allowed = tr.enforced_confidences(tr.policy_for(model))
            if cell and cell[0] is not None and cell[2] in allowed:
                return max(1, int(cell[0]))
        except Exception:
            return 1
        return 1

    @staticmethod
    def _own_eff(cid: int) -> float:
        try:
            from src.services import team_resources as tr

            own = (tr.record(cid).get("energy") or {}).get("own_eff")
            return float(own[0]) if own and own[0] is not None else 0.0
        except Exception:
            return 0.0

    # clocks ---------------------------------------------------------------
    def _active(self, a_us: int, b_us: int) -> int:
        return self.svc._active_between(self.stops, a_us, b_us)

    def _advance(self, t_us: int, active_us: int) -> int:
        """Wall time at which ``active_us`` of active time has passed since ``t_us``."""
        wall, left = int(t_us), int(active_us)
        for start, end in sorted(self.stops):
            if end <= wall:
                continue
            if start > wall:
                gap = start - wall
                if left <= gap:
                    return wall + left
                left -= gap
            wall = end
        return wall + left

    # states ---------------------------------------------------------------
    def _state(self, cid: int) -> dict | None:
        m = self.members[cid]
        return (self.data.PALETTE[cid]["states"].get(m.state) if m.state else None)

    def _elapsed(self, cid: int, t_us: int) -> int:
        """Active µs of the member's state clock at ``t_us`` (off-field time left out for pausing states)."""
        m, st = self.members[cid], self._state(cid)
        if st is None:
            return 0
        elapsed = self._active(m.state_start_us, t_us) - m.state_paused_us
        if m.off_since_us is not None and st["pauses_off_field"]:
            elapsed -= self._active(max(m.off_since_us, m.state_start_us), t_us)
        return max(0, elapsed)

    def _alive(self, cid: int, t_us: int) -> bool:
        st = self._state(cid)
        if st is None:
            return False
        if st["duration_s"] is None:
            return True
        return self._elapsed(cid, t_us) <= self.svc._us(st["duration_s"]) + STATE_TOLERANCE_US

    def _end_state(self, cid: int) -> None:
        m = self.members[cid]
        m.state, m.form, m.state_paused_us = "", None, 0

    def _state_note(self, code: str, cid: int, state_code: str, *args):
        st = self.data.PALETTE[cid]["states"].get(state_code) or {}
        return self.tx.note(code, state_code, st.get("name_zh") or "", *args)

    # token resolution -------------------------------------------------------
    def resolve(self, cid: int, slot: str, pos: int | None, t_us: int) -> _Resolved | None:
        """What a slot press of the member places at ``t_us`` (pure; spec §2.4)."""
        p = self.data.PALETTE.get(cid)
        if p is None:
            return None
        tx, m = self.tx, self.members[cid]
        st = self._state(cid)
        code = m.state if st is not None else ""
        alive = bool(code) and self._alive(cid, t_us)
        # a chain inside a state's table finishes there, even when the state timer ran out in between (only the
        # exit action or a swap breaks it: both clear m.last)
        if pos is None and m.last is not None and m.last[0] and m.last[1] == slot:
            held = p["states"].get(m.last[0])
            table = held["slots"].get(slot) if held is not None else None
            if table is not None and table["mode"] == "chain" and m.last[2] + 1 < len(table["entries"]):
                return _Resolved(m.last[0], m.last[2] + 1, table["entries"][m.last[2] + 1], table, [])
        tables = []
        if alive and slot in st["slots"]:
            tables.append((code, st["slots"][slot]))
        if slot in p["base"]:
            tables.append(("", p["base"][slot]))
        for other, state in p["states"].items():
            if not (alive and other == code) and slot in state["slots"]:
                tables.append((other, state["slots"][slot]))
        if not tables:
            return None
        if pos is not None:
            chosen = next(((tid, table, int(pos) - 1) for tid, table in tables
                           if 1 <= int(pos) <= len(table["entries"])), None)
            if chosen is None:
                return None
            tid, table, index = chosen
        else:
            tid, table = tables[0]
            index = 0
            if table["mode"] == "chain":
                if m.last is not None and m.last[0] == tid and m.last[1] == slot:
                    index = m.last[2] + 1
                    if index >= len(table["entries"]):
                        index = int(table.get("loop_from") or 0)
                elif slot == "basic" and tid == "" and m.last_key is not None:
                    jump = p["basic_after"].get(tuple(m.last_key))
                    if jump:
                        index = int(jump) - 1
        notes = []
        expired = bool(code) and not alive and slot in st["slots"]
        if tid and not (alive and tid == code):
            notes.append(self._state_note(tx.NOTE_CUSTOM_STATE_INACTIVE, cid, tid))
        elif expired:
            notes.append(self._state_note(tx.NOTE_CUSTOM_STATE_EXPIRED, cid, code))
        return _Resolved(tid, index, table["entries"][index], table, notes, expired)

    def peek(self, cid: int, slot: str, pos: int | None = None) -> tuple | None:
        """Action keys a slot press would place now, or None (time-only entries give ())."""
        if cid != self.on_field and self.on_field is not None:
            return None
        got = self.resolve(cid, slot, pos, self.t)
        if got is None:
            return None
        return () if got.entry and got.entry[0] == "@time" else tuple(tuple(k) for k in got.entry)

    # visits and swaps -------------------------------------------------------
    def _open_visit(self, cid: int, entry: str) -> None:
        t = self.t
        out = self.on_field
        if self.visit is not None:
            self.visit.end_us = t
            self.visit.gauge_out = self.gauge.value(self.visit.character_id)
        if out is not None:
            mo = self.members[out]
            mo.last = mo.last_key = None
            if self._clock is not None and out in self._clock_members:
                self._clock.visit_end(out, t)       # the clock's drain in his ultimate ends with the visit
            st = self._state(out)
            if st is not None:
                if st["ends_on_swap"]:
                    self._end_state(out)
                else:
                    mo.off_since_us = t
        m = self.members[cid]
        if m.off_since_us is not None:
            st = self._state(cid)
            if st is not None and st["pauses_off_field"]:
                m.state_paused_us += self._active(max(m.off_since_us, m.state_start_us), t)
            m.off_since_us = None
        self.visit = self.svc._VisitRun(len(self.visits), self.rep, cid, entry, t, t, self.gauge.value(cid))
        self.visits.append(self.visit)
        self.on_field = cid

    def _swap(self, cid: int, tok: str | None) -> dict:
        """Bring ``cid`` in with entry token ``tok`` (support / swap / None = implicit); spec §2.2."""
        tx = self.tx
        out = self.on_field
        info = {"entry": tx.ENTRY_OPENER, "play": False, "fired": None, "skipped": False, "notes": [],
                "swap_index": None, "out_gauge": None, "out": out}
        if out is None:                    # first step of the fight: nobody leaves, so nothing can react
            if tok == "support":
                info["play"] = True
                info["notes"].append(tx.note(tx.NOTE_CUSTOM_OPENER))
            self._open_visit(cid, tx.ENTRY_OPENER)
            return info
        eo, ei = self.elements.get(out, ""), self.elements.get(cid, "")
        pair = self.rules.reaction_for(eo, ei) if eo and ei and eo != ei else None
        gauge = float(self.gauge.value(out))
        full = gauge >= float(self.gauge.cap) - 1e-6
        # awakening node rule (free_support): a typed support entry that needs no gauge and does not consume it
        free = bool(tok == "support" and pair is not None and not full and self.layout_hooks is not None
                    and self.layout_hooks.free_support(out, cid, self.t, pair, None))
        judged, self._judge_entry = bool(getattr(self, "_judge_entry", False)), False
        # D3 (strict): the entry after an early swap follows the gauge rule like the reviewed mode (review F5)
        as_typed = self.options.gauge_mode != "check" and not judged
        entry, outcome = tx.ENTRY_NORMAL, tx.OUTCOME_PLAIN_SWAP
        if tok == "support":
            if pair is None:
                outcome = tx.OUTCOME_SAME_ELEMENT if eo == ei else tx.OUTCOME_NOT_ADJACENT
                if as_typed:               # the support skill plays, but nothing reacts
                    entry, info["play"] = tx.ENTRY_SUPPORT_SKILL, True
                    info["notes"].append(tx.note(tx.NOTE_CUSTOM_SUPPORT_NO_REACTION))
                else:
                    info["skipped"] = True
                    info["notes"].append(tx.note(tx.NOTE_CUSTOM_DOWNGRADED_ELEMENT))
            elif full or as_typed or free:
                entry, outcome = tx.ENTRY_SUPPORT_SKILL, tx.OUTCOME_REACTION
                info["play"], info["fired"] = True, pair
                if not full and not free:
                    info["notes"].append(tx.note(tx.NOTE_CUSTOM_GAUGE_SHORT, round(gauge, 3)))
            else:
                outcome, info["skipped"] = tx.OUTCOME_GAUGE_SHORT, True
                info["notes"].append(tx.note(tx.NOTE_CUSTOM_DOWNGRADED_GAUGE, round(gauge, 3)))
        elif tok is None:
            info["notes"].append(tx.note(tx.NOTE_CUSTOM_IMPLICIT_SWAP))
        self.swaps.append(self.svc._SwapRun(len(self.swaps), self.t, out, cid, eo, ei, gauge, outcome, None))
        info.update(entry=entry, swap_index=len(self.swaps) - 1, out_gauge=gauge)
        if info["fired"] is not None and not free:
            self.gauge.set_value(out, 0.0)             # the reaction consumes the outgoing member's gauge
        self._open_visit(cid, entry)
        if not info["play"]:
            self.plain_swaps += 1
            self.t += self.svc._us(self.options.swap_time_s)
        return info

    def _new_rec(self, src: int, cid: int, action: str) -> _Rec:
        return _Rec(index=len(self.records), source_index=src, repeat_index=self.rep, character_id=cid,
                    action=action, start_us=self.t, end_us=self.t, gauge_before=float(self.gauge.value(cid)),
                    visit_index=self.visit.index if self.visit is not None else 0)

    def _apply_info(self, rec: _Rec, info: dict) -> None:
        rec.entry = info["entry"]
        rec.swap_index = info["swap_index"]
        rec.out_gauge = info["out_gauge"]
        rec.out_character_id = info["out"]
        rec.notes = list(info["notes"]) + rec.notes
        rec.visit_index = self.visit.index

    def _entry_step(self, step: CustomStep, src: int) -> None:
        tx, cid, tok = self.tx, int(step.character_id), step.action
        self.seq += 1
        if self.on_field == cid:           # only at a repeat boundary (the parser rejects it inside one pass)
            rec = self._new_rec(src, cid, tok)
            rec.status = tx.STEP_SKIPPED
            rec.notes.append(tx.note(tx.NOTE_CUSTOM_ENTRY_SKIPPED, cid))
            rec.gauge_after = rec.gauge_before
            self.records.append(rec)
            return
        start = self.t
        info = self._swap(cid, tok)
        rec = self._new_rec(src, cid, tok)
        rec.start_us = start
        self._apply_info(rec, info)
        resolved = self.resolve(cid, "support", None, self.t) if (info["play"] or info["skipped"]) else None
        key = tuple(resolved.entry[0]) if resolved is not None and resolved.entry and resolved.entry[0] != "@time" \
            else None
        if key is not None:
            rec.slot, rec.keys = tx.SLOT_QTE, (key,)
            rec.name_zh = (self.data.ACTIONS.get(key) or {}).get("name_zh") or ""
            rec.state = resolved.table_id
        if info["play"] and key is not None:
            run = self.svc._StepRun(self.seq, "qte", key[0], key[1], self.t, self.t, "ok")
            rec.step_index = len(self.visit.steps)
            self.visit.steps.append(run)
            measured = self.measure.action(cid, key, self.t, self.visit.index, rec.step_index, run)
            self.t += measured.length_us
            run.end_us, run.actions, run.status = self.t, (key,), measured.status
            rec.hits, rec.energy_gain, rec.status = measured.hits, measured.energy, measured.status
            from src.services.team_cycle_reactions import support_skill_attack_type

            fired = info["fired"]
            rows = sorted(run.rows, key=lambda r: r["relative_time_us"])
            for i, row in enumerate(rows):
                row["attack_type"] = support_skill_attack_type(fired, i == 0)
            if fired is not None:
                rec.reaction_zh = fired.zh
                if self.sched is not None:
                    trigger_us = rows[0]["relative_time_us"] if rows else run.start_us
                    self.swaps[-1].reaction_index = self.sched.trigger(
                        trigger_us, info["out"], cid, fired, visit_index=self.visit.index, source_rows=rows)
            m = self.members[cid]
            m.last, m.last_key = None, key
        elif info["skipped"] and key is not None:
            rec.step_index = len(self.visit.steps)
            self.visit.steps.append(self.svc._StepRun(self.seq, "qte", key[0], key[1], self.t, self.t,
                                                     "skipped_entry"))
            rec.status = tx.STEP_SKIPPED
        rec.end_us = self.t
        rec.gauge_after = float(self.gauge.value(cid))
        self.records.append(rec)

    # actions ---------------------------------------------------------------
    def _time_step(self, src: int, cid: int, action: str, wall_us: int) -> _Rec:
        rec = self._new_rec(src, cid, action)
        run = self.svc._StepRun(self.seq, "other", None, None, self.t, self.t + int(wall_us), "time_only")
        rec.step_index = len(self.visit.steps)
        self.visit.steps.append(run)
        self.t += int(wall_us)
        rec.end_us, rec.status = self.t, self.tx.STEP_TIME_ONLY
        rec.gauge_after = rec.gauge_before
        self.records.append(rec)
        return rec

    def _cd_value(self, cid: int, kind: str, *, note: bool = True) -> float | None:
        """The cooldown in use: the typed (or default) base value plus the awakening changes of team_resource_data
        (Haniel A6 -4 s; resource levels)."""
        resource = (self.options.resources or {}).get(cid)
        if resource is None or not kind:
            return None
        value = resource.e_cd_s if kind == "E" else resource.q_cd_s
        if value is not None:
            for rule in self._rules(cid, "e_cd_add", kind):
                value = max(0.0, float(value) + float(rule[2]))
                if note:
                    self.rules_used[cid].add("e_cd_add")
        return value

    def _press(self, step: CustomStep, src: int, k: int, info: dict | None) -> None:
        tx, data, svc = self.tx, self.data, self.svc
        cid = int(step.character_id)
        m = self.members[cid]
        self.seq += 1
        action = step.action
        if action in ("wait", "dodge"):
            seconds = float(step.seconds or 0.0) if action == "wait" else float(data.DODGE_S)
            rec = self._time_step(src, cid, action, svc._us(seconds))
            if info is not None:
                self._apply_info(rec, info)
            m.last = m.last_key = None
            if action == "wait" and self._clock is not None and cid in self._clock_members:
                # Hotori's "wait for the clock" step of the reviewed rotation (D15: credited in a team)
                self._clock.note_interlude(cid)
                rec.clock_after = self._clock.snapshot(cid, self.t)
            return
        notes: list = []
        resolved = None
        cd_kind = ""
        where = None
        if action == RAW_ACTION:
            keys = (tuple(step.raw or ("", "")),)
            where = data.ACTION_INDEX.get(keys[0])
            trace_slot = _TRACE_SLOT.get(where[1], "other") if where else "other"
            if where and where[0] == "":
                cd_kind = "E" if where[1] in ("skill", "skill_hold") else ("Q" if where[1] == "ult" and where[2] == 1
                                                                           else "")
        else:
            resolved = self.resolve(cid, action, step.pos if k == 0 else None, self.t)
            trace_slot = _TRACE_SLOT.get(action, "other")
            if resolved is None:           # a stale saved cycle: nothing to place
                rec = self._new_rec(src, cid, action)
                rec.status, rec.slot = tx.STEP_MISSING, trace_slot
                rec.gauge_after = rec.gauge_before
                if info is not None:
                    self._apply_info(rec, info)
                self.extra_missing[cid].append(f"{action}:{step.pos or ''}")
                self.records.append(rec)
                return
            cd_kind = str(resolved.table.get("cd") or "")
            if cd_kind == "Q" and resolved.index != 0:
                cd_kind = ""               # later chain entries follow state rules the data does not give
        # cooldown (active clock, keeps running while the member is off the field)
        wait_before = 0
        value = self._cd_value(cid, cd_kind)
        check = self.options.resource_check
        if check == "strict" and cd_kind == "Q" and m.energy is not None:
            # energy first (team_resources check order): a short pool skips the ultimate, no wait fills it
            cost = float(self.options.resources[cid].q_cost)
            if m.energy + 1e-6 < cost:
                if self._not_ready(src, cid, action, trace_slot, info, notes, "energy", "Q", None, m.energy, cost):
                    return                              # D3: swapped out instead of skipping the ultimate
                self._skip(src, cid, action, trace_slot, info, notes, tx.STEP_ENERGY_SHORT,
                           tx.note(tx.NOTE_CUSTOM_ENERGY_SKIPPED, round(m.energy, 3), cost))
                self.skipped_energy += 1
                return
        swapped: list = []

        def decide(own_us: int) -> bool:
            if self._not_ready(src, cid, action, trace_slot, info, notes, "clock", cd_kind, own_us):
                swapped.append(True)
            return bool(swapped)

        self._blocked_wait = None
        clock_cls, clock_gate = self._clock_gate(cid, cd_kind, src, notes, decide)
        if swapped:
            return
        if clock_gate is not None and clock_gate.wait_us > CD_TOLERANCE_US and resolved is not None \
                and check in ("wait", "strict"):
            resolved = self.resolve(cid, action, step.pos if k == 0 else None, self.t) or resolved
        charges = self._charges.get(cid, 1) if cd_kind == "E" else 1
        if cd_kind and value is None and check != "off" and cd_kind in m.cd:
            self.unchecked_cd.add((cid, cd_kind))          # nothing to check against: listed under the limits
        remaining = 0
        if cd_kind and value is not None and check != "off":
            if charges > 1:             # stored uses (Chiichan): a use is back cd seconds after it was spent
                now_pc = self._active(0, self.t)
                pending = [r for r in m.charge_ready.get(cd_kind, ()) if r > now_pc]
                if len(pending) >= charges:
                    remaining = min(pending) - now_pc
            elif cd_kind in m.cd:
                remaining = svc._us(value) - self._active(m.cd[cd_kind], self.t)
        free_extra = False
        if cd_kind == "E" and remaining > CD_TOLERANCE_US:
            for rule in self._rules(cid, "extra_e_after_basics", "E"):     # Lacrimosa: an extra E after 5 basics
                if not self._extra_used[cid] and self._basics[cid] >= int(rule[2] or 0):
                    remaining, free_extra = 0, True
                    self.rules_used[cid].add("extra_e_after_basics")
                break
        short = remaining > CD_TOLERANCE_US and self._short_wait(remaining)   # < 0.3 s left: wait (10-18)
        if remaining > CD_TOLERANCE_US and not short and self._not_ready(src, cid, action, trace_slot, info, notes,
                                                                         "cd", cd_kind, remaining):
            return                                  # D3: swapped out at once (no wait, no skip)
        resumed, self._resumed_left = getattr(self, "_resumed_left", None), None
        if resumed is not None:         # waited for the earliest ready member, now under the threshold (10-18)
            remaining, short = int(resumed), True
        if remaining > CD_TOLERANCE_US:
            limit = self.options.cd_wait_max_s          # wait: only when set; strict: also the 60 s guard
            if check == "strict":
                limit = CD_WAIT_GUARD_S if limit is None else min(float(limit), CD_WAIT_GUARD_S)
            if check in ("wait", "strict") and limit is not None and remaining > svc._us(limit) + CD_TOLERANCE_US:
                self._skip(src, cid, action, trace_slot, info, notes, tx.STEP_CD_SKIP,
                           tx.note(tx.NOTE_CUSTOM_CD_SKIPPED, round(remaining / 1e6, 3)))
                self.skipped_cd += 1
                return
            if check in ("wait", "strict"):
                target = self._advance(self.t, remaining)
                wait_before = target - self.t
                self._time_step(-1, cid, "wait", wait_before)
                self.waited_us += wait_before
                self.seq += 1
                if short:                   # under the swap threshold: waited, no swap (2026-10-18)
                    from src.services.team_resources import SWAP_MIN_WAIT_S

                    notes.append(tx.note(tx.NOTE_CUSTOM_SHORT_WAIT, round(remaining / 1e6, 3), SWAP_MIN_WAIT_S))
                else:
                    notes.append(tx.note(tx.NOTE_CUSTOM_CD_WAITED, round(wait_before / 1e6, 3)))
                if getattr(self, "_blocked_wait", None) is not None:     # every member blocked, this one first
                    notes.append(tx.note(tx.NOTE_CUSTOM_ALL_BLOCKED, round(wait_before / 1e6, 3), cid))
                if resolved is not None:
                    resolved = self.resolve(cid, action, step.pos if k == 0 else None, self.t) or resolved
            else:
                notes.append(tx.note(tx.NOTE_CUSTOM_CD_NOT_READY, round(remaining / 1e6, 3)))
        rec = self._new_rec(src, cid, action)
        rec.wait_before_us, rec.slot, rec.cd_kind = wait_before, trace_slot, cd_kind
        if info is not None:
            self._apply_info(rec, info)
        tid = ""
        if resolved is not None:
            tid = resolved.table_id
            notes += resolved.notes
            rec.pos, rec.state = resolved.index + 1, tid
            if resolved.expired:
                self._end_state(cid)
            entry = resolved.entry
            m.last = (tid, action, resolved.index)
        else:
            entry = keys
            m.last = None
        start = self.t
        if cd_kind and free_extra:
            self._extra_used[cid] = True        # the extra E keeps the running E cooldown (no restart)
        elif cd_kind:
            offset = self._cd_offset_us(cid, cd_kind) if value is not None else 0
            m.cd[cd_kind] = start + offset
            if charges > 1 and value is not None:
                now_pc = self._active(0, start + offset)
                pending = sorted(r for r in m.charge_ready.get(cd_kind, ()) if r > now_pc)
                pending.append(max([now_pc] + pending) + svc._us(value))
                m.charge_ready[cd_kind] = pending
            if offset:
                self.rules_used[cid].add("cd_offset")
            if cd_kind == "E":
                self._basics[cid], self._extra_used[cid] = 0, False
        if cd_kind == "Q":
            self._reset_cd(cid, "q_resets_e")           # Linko A3: the ultimate refreshes the E cooldown
        if self.rules_on and (action == "counter" or (action == RAW_ACTION and str((step.raw or ("",))[0]).endswith(
                "_PerfectEvade"))):
            self._reset_cd(cid, "counter_resets_e")     # Mint A1: a counter refreshes the E cooldown
        if check == "strict" and cd_kind == "Q" and m.energy is not None:
            m.energy = max(0.0, m.energy - float(self.options.resources[cid].q_cost))
        if clock_cls is not None:                  # Hotori: spend the clock (E 60 / Q from full, drain)
            self._clock.begin(cid, clock_cls, start, clock_gate)
        if entry and entry[0] == "@time":                  # a chain hit without animation data: time only
            _tag, seconds, label, source = entry
            run = svc._StepRun(self.seq, trace_slot, None, None, start, start + svc._us(seconds), "time_only")
            rec.step_index = len(self.visit.steps)
            self.visit.steps.append(run)
            self.t = run.end_us
            rec.status = tx.STEP_TIME_ONLY
            rec.name_zh = "" if str(label).startswith("Melee") else str(label)
            notes.append(tx.note(tx.NOTE_CUSTOM_NO_ANIMATION))
            self.extra_missing[cid].append(f"{action}:{label}")
            if source == "default_1s":
                self.used_default = True
            m.last_key = None
        else:
            keys = tuple(tuple(key) for key in entry)
            st = self._state(cid)
            in_state = bool(tid) and tid == m.state
            role = ""
            if st is not None and any(key in st["exit"] for key in keys):
                role = tx.FORM_ROLE_EXIT
            elif in_state:
                role = tx.FORM_ROLE_BODY
            run = svc._StepRun(self.seq, trace_slot, keys[0][0], keys[0][1], start, start, "ok", form_role=role)
            rec.step_index = len(self.visit.steps)
            self.visit.steps.append(run)
            rec.keys = keys
            rec.name_zh = (data.ACTIONS.get(keys[0]) or {}).get("name_zh") or ""
            m.last_key = keys[-1]
            for key in keys:
                t0 = self.t
                measured = self.measure.action(cid, key, t0, self.visit.index, rec.step_index, run)
                self.t += measured.length_us
                rec.hits += measured.hits
                rec.energy_gain += measured.energy
                rec.energy_event += measured.event_energy
                if measured.credit is not None:
                    if measured.credit[0] is None:
                        self.hit_unknown.add(cid)
                    else:
                        self.hit_credited[cid] += 1
                if m.energy is not None:           # strict: the online pool (capped at the cost)
                    m.energy = min(float(self.options.resources[cid].q_cost),
                                   m.energy + float(measured.energy) * (1.0 + self._eff.get(cid, 0.0))
                                   + float(measured.event_energy))
                if measured.status != "ok":
                    run.status = measured.status
                gauge_set = (data.ACTIONS.get(key) or {}).get("gauge_set")
                if gauge_set is not None:
                    self.gauge.set_value(cid, float(gauge_set))
                    self.used_gauge_set = True
                self._after_key(cid, key, t0, notes)
            run.end_us, run.actions = self.t, keys
            rec.status = run.status
            if action == "entry_attack":
                self.used_normal = True
            if cd_kind == "Q" and cid in data.OWN_RESOURCE:
                self.own_resource.add(cid)
            if self.rules_on and cd_kind == "E":         # Sagiri ⑤: the held E clears the Q cooldown (e_resets_q)
                self._reset_cd(cid, "e_resets_q", tuple(str(k[1] or "") for k in keys))
            self._after_step(cid, tid, start, notes)
            if self.rules_on and (action == "basic" or (action == RAW_ACTION and where and where[1] == "basic")):
                self._basics[cid] += 1
        if self._clock is not None and cid in self._clock_members:
            rec.clock_after = self._clock.snapshot(cid, self.t)
        rec.end_us = self.t
        rec.gauge_after = float(self.gauge.value(cid))
        rec.notes += notes
        self.records.append(rec)

    def _skip(self, src: int, cid: int, action: str, slot: str, info: dict | None, notes: list, status: str,
              note) -> None:
        """A press the check skipped (strict energy / longest wait): no time, no hits, its own record."""
        rec = self._new_rec(src, cid, action)
        rec.slot, rec.status = slot, status
        if info is not None:
            self._apply_info(rec, info)
        rec.notes += list(notes) + [note]
        rec.gauge_after = rec.gauge_before
        self.records.append(rec)

    def _after_key(self, cid: int, key: tuple, t0: int, notes: list) -> None:
        """State exit / start markers of one placed action."""
        tx, svc, m = self.tx, self.svc, self.members[cid]
        st = self._state(cid)
        if st is not None and key in st["exit"]:
            elapsed = self._elapsed(cid, t0)
            from src.services import global_live_overlay   # Akane stage 2 from 4 s (CN release)

            window = global_live_overlay.form_window(cid, m.state, st["window_s"], self._static_path)
            missed = False
            if window is not None and self._state_running(cid, t0) is not None:
                lo, hi = svc._us(window[0]), svc._us(window[1])
                if not (lo - STATE_TOLERANCE_US <= elapsed <= hi + STATE_TOLERANCE_US):
                    missed = True
                    notes.append(self._state_note(tx.NOTE_CUSTOM_STATE_WINDOW, cid, m.state,
                                                  round(elapsed / 1e6, 3), float(window[0]), float(window[1])))
            if m.form is not None:
                m.form["exit_s"] = elapsed / 1e6
                m.form["window"] = tuple(window or ())
                if missed:
                    m.form["status"] = tx.FORM_WINDOW_MISSED
            self._end_state(cid)
            m.last = None
            if self._clock is not None and cid in self._clock_members:
                self._clock.end_drain(cid, self.t)     # the clock regenerates again once the state ends (F-B)
            return
        for code, state in self.data.PALETTE[cid]["states"].items():
            if tuple(state["start"]) != key:
                continue
            self._end_state(cid)
            m.state = code
            m.state_start_us = t0 + svc._us(state["start_offset_s"])
            m.state_paused_us, m.off_since_us, m.last = 0, None, None
            self.states_entered = True
            notes.append(self._state_note(tx.NOTE_CUSTOM_STATE_ENTERED, cid, code))
            if code in self.form_codes and self.visit.form is None and state["duration_s"] is not None:
                m.form = {"code": code, "name_zh": state["name_zh"], "duration_s": float(state["duration_s"]),
                          "start_us": m.state_start_us, "used_s": 0.0, "groups": 0, "groups_approved": 0,
                          "fills": 0, "cut_steps": 0, "overrun_s": 0.0, "status": tx.FORM_OK,
                          "pauses_off_field": bool(state["pauses_off_field"]),
                          "ends_on_swap": bool(state["ends_on_swap"]), "exit_s": None, "window": ()}
                self.visit.form = m.form
            return

    def _state_running(self, cid: int, t_us: int):
        """The member's state when its clock has started at ``t_us`` (None otherwise)."""
        m = self.members[cid]
        return self._state(cid) if m.state and t_us >= m.state_start_us else None

    def _after_step(self, cid: int, tid: str, start_us: int, notes: list) -> None:
        """Overrun note and form summary for a step resolved in the member's state table."""
        m, st = self.members[cid], self._state(cid)
        if st is None or not tid or tid != m.state:
            return
        elapsed = self._elapsed(cid, self.t)
        over = 0
        if st["duration_s"] is not None:
            over = elapsed - self.svc._us(st["duration_s"])
            if over > STATE_TOLERANCE_US:
                notes.append(self._state_note(self.tx.NOTE_CUSTOM_STATE_OVERRUN, cid, m.state,
                                              round(over / 1e6, 3)))
        if m.form is not None:
            m.form["groups"] += 1
            m.form["groups_approved"] = m.form["groups"]
            m.form["used_s"] = min(float(m.form["duration_s"]), elapsed / 1e6)
            if over > STATE_TOLERANCE_US:
                m.form["overrun_s"] = max(m.form["overrun_s"], over / 1e6)
                if m.form["status"] == self.tx.FORM_OK:
                    m.form["status"] = self.tx.FORM_OVERRUN

    def _action_step(self, step: CustomStep, src: int) -> None:
        cid = int(step.character_id)
        info = self._swap(cid, None) if cid != self.on_field else None
        for k in range(max(1, int(step.repeat or 1))):
            if self._swap_out == cid:          # D3: an earlier press of this step swapped the member out
                break
            self._press(step, src, k, info if k == 0 else None)

    # driving ----------------------------------------------------------------
    def reset_gauges(self) -> None:
        for cid in self.team:
            self.gauge.set_value(cid, _clamp((self.options.start_gauge or {}).get(cid, 100.0), 0.0, 100.0, 100.0))

    def step(self, step: CustomStep, src: int) -> None:
        if int(step.character_id) not in self.members:
            return
        if self._swap_out is not None:
            if int(step.character_id) == self._swap_out:    # D3: swapped out early - this input is not run
                self._drop(step, src)
                return
            self._swap_out = None              # another member's step: its entry is the swap, judged by
            self._judge_entry = True           # the gauge rule (support skill only when the gauge allows, F5)
        if step.action in ENTRY_ACTIONS:
            self._entry_step(step, src)
        else:
            self._action_step(step, src)

    def run(self, steps: Sequence[CustomStep]) -> _Walk:
        self.reset_gauges()
        steps = list(steps)
        reps = max(1, int(self.options.repeat))
        ids = [int(s.character_id) if int(s.character_id) in self.members else None for s in steps]
        self._seq_steps, self._reps = steps, reps
        for rep in range(reps):
            self.rep = rep
            if rep and self.options.gauge_reset_each_repeat:
                self.reset_gauges()
            for src, step in enumerate(steps):
                cid = ids[src]
                # D3: somebody typed later to swap to (the rest of this pass, or any later pass)
                self._other_ahead = cid is not None and (
                    any(c is not None and c != cid for c in ids[src + 1:])
                    or (rep + 1 < reps and any(c is not None and c != cid for c in ids)))
                self._src = src
                self.step(step, src)
        return self.finish()

    def finish(self) -> _Walk:
        if self.visit is not None:
            self.visit.end_us = self.t
            self.visit.gauge_out = self.gauge.value(self.visit.character_id)
        missing: dict = defaultdict(list)
        for source in (self.measure.missing, self.extra_missing):
            for cid, items in source.items():
                missing[cid].extend(items)
        layout = self.svc._Layout(
            self.measure.rows, self.measure.side, self.visits, self.swaps, self.stops, self.measure.stop_owners,
            self.t, dict(missing), self.measure.unknown_stop, self.used_default, self.used_gauge_set,
            self.used_normal, (), {cid: dict(v) for cid, v in self.measure.form_actions.items()})
        interludes = {}
        for cid in self._clock_members:
            summary = self._clock.member_summary(cid)
            if summary.get("interlude_s"):
                interludes[cid] = (float(summary["interlude_s"]), tuple(summary.get("interludes_s") or ()))
        return _Walk(layout, self.records, self.waited_us, self.states_entered, tuple(sorted(self.own_resource)),
                     self.plain_swaps, tuple(sorted(self.unchecked_cd)), self.skipped_energy, self.skipped_cd,
                     dict(self._eff), tuple(self._clock_members), self.clock_waits,
                     {cid: tuple(sorted(codes)) for cid, codes in self.rules_used.items() if codes}, interludes,
                     dict(self.hit_credited), tuple(sorted(self.hit_unknown)), self.early_swaps, self.swap_dropped)


def _walk(steps, team_ids, elements, rules, options, measure, gauge, stops, stop_owners=None, sched=None, *,
          awakening=None, eff_override=None, node_rules=None, layout_hooks=None) -> _Walk:
    """Lay the custom steps out: returns the engine layout plus the per-step records."""
    return _Walker(team_ids, elements, rules, options, measure, gauge, stops, sched, awakening=awakening,
                   eff_override=eff_override, node_rules=node_rules, layout_hooks=layout_hooks).run(steps)


def _hit_credits(options: CustomOptions):
    """team_resource_data.HIT_CREDIT at the resource levels (None at the legacy level)."""
    if resource_model_of(options) == "legacy":
        return None
    from src.services import team_resource_data

    return getattr(team_resource_data, "HIT_CREDIT", None) or {}


# ── energy (never changes the timeline: a pass over the step records) ──────
def _energy_pass(records: list, team_ids, options: CustomOptions, auto_eff: Mapping | None = None,
                 fixed_eff: Mapping | None = None) -> None:
    from src.services import team_custom_actions as data
    from src.services import team_simulation_explanation as tx

    energy: dict = {}
    cost: dict = {}
    eff: dict = {}
    gained: dict = {}                               # cost unknown: energy since the last ultimate (display)
    resourced = resource_model_of(options) != "legacy"
    for cid in team_ids:
        resource = (options.resources or {}).get(cid)
        if cid in data.OWN_RESOURCE:
            continue
        if resource is None or resource.q_cost is None:
            if resourced:
                own = _Walker._own_eff(cid)
                gained[cid] = (0.0, float(resource.charge_eff) if resource is not None and resource.charge_eff is not None
                               else own + float((auto_eff or {}).get(cid, 0.0)))
            continue
        cost[cid] = float(resource.q_cost)
        start = cost[cid] if resource.start_energy is None else float(resource.start_energy)
        energy[cid] = max(0.0, min(cost[cid], start))
        eff[cid] = float(resource.charge_eff) if resource.charge_eff is not None \
            else (_Walker._own_eff(cid) if resourced else 0.0) + float((auto_eff or {}).get(cid, 0.0))
        if fixed_eff and cid in fixed_eff:          # strict: the value the online check used
            eff[cid] = float(fixed_eff[cid])
    for rec in records:
        cid = rec.character_id
        if cid in gained:
            total, rate = gained[cid]
            if rec.cd_kind == "Q":
                total = 0.0
            total += float(rec.energy_gain or 0.0) * (1.0 + rate) + float(rec.energy_event or 0.0)
            gained[cid] = (total, rate)
            rec.energy_gained = total
        if cid not in energy:
            rec.energy_after = None
            continue
        if rec.cd_kind == "Q":
            if energy[cid] + 1e-6 < cost[cid] and options.resource_check != "off":
                rec.notes.append(tx.note(tx.NOTE_CUSTOM_ENERGY_SHORT, round(energy[cid], 3), cost[cid]))
            energy[cid] = max(0.0, energy[cid] - cost[cid])
        energy[cid] = min(cost[cid], energy[cid] + float(rec.energy_gain or 0.0) * (1.0 + eff[cid])
                          + float(rec.energy_event or 0.0))
        rec.energy_after = energy[cid]


def _traces(records: list, layout, expl=None) -> tuple:
    """Step records -> CustomStepTrace (damage and hits copied from the visit steps when an explanation exists)."""
    from src.services import team_simulation_explanation as tx
    from src.services.team_simulation_service import _seconds

    visits = {v.index: v for v in (expl.visits if expl is not None else ())}
    out = []
    for rec in records:
        damage, hits = 0.0, int(rec.hits)
        visit = visits.get(rec.visit_index)
        if visit is not None and rec.step_index is not None and rec.step_index < len(visit.steps):
            trace = visit.steps[rec.step_index]
            damage, hits = float(trace.damage or 0.0), int(trace.hits or 0)
        reaction_index = None
        if rec.swap_index is not None and rec.swap_index < len(layout.swaps):
            reaction_index = layout.swaps[rec.swap_index].reaction_index
        out.append(tx.CustomStepTrace(
            index=rec.index, source_index=rec.source_index, repeat_index=rec.repeat_index,
            character_id=rec.character_id, action=rec.action, pos=rec.pos, state=rec.state, slot=rec.slot,
            keys=tuple(rec.keys), name_zh=rec.name_zh, start_s=_seconds(rec.start_us),
            duration_s=(rec.end_us - rec.start_us) / 1e6, wait_before_s=rec.wait_before_us / 1e6, hits=hits,
            damage=damage, status=rec.status, entry=rec.entry, swap_index=rec.swap_index,
            reaction_index=reaction_index, gauge_before=rec.gauge_before, gauge_after=rec.gauge_after,
            out_gauge=rec.out_gauge, energy_after=rec.energy_after, notes=tuple(rec.notes),
            visit_index=rec.visit_index, step_index=rec.step_index, reaction_zh=rec.reaction_zh,
            out_character_id=rec.out_character_id, energy_gained=rec.energy_gained, clock_after=rec.clock_after))
    return tuple(out)


def executed_actions(steps, repeat: int = 1) -> int:
    """Actions the walk executes: every step's repeat count times the repeat of the whole list."""
    return sum(max(1, int(s.repeat or 1)) for s in steps) * max(1, int(repeat))


def _as_steps(sequence, team_ids, lang: str = "ko") -> tuple:
    """A typed text or a step list -> validated steps (CustomCycleError when it cannot be simulated)."""
    if isinstance(sequence, str):
        parsed = notation.parse(sequence, team_ids, lang)
        if parsed.errors:
            raise CustomCycleError(parsed.errors)
        return tuple(parsed.steps)
    steps = tuple(sequence or ())
    errors, _warnings = notation.check_steps(steps, team_ids)
    if not steps:
        errors = [notation.ParseIssue("empty")]
    if errors:
        raise CustomCycleError(errors)
    return steps


# ── preview (no database, no engine) ───────────────────────────────────────
def _palette_walker(team_ids, options: CustomOptions, awakening: Mapping | None = None):
    from src.services import team_custom_actions as data
    from src.services import team_cycle_reactions as tcr

    team = [int(c) for c in team_ids]
    elements = {cid: (data.PALETTE.get(cid) or {}).get("element", "") for cid in team}
    rules = tcr.DEFAULT_RULES
    gauge = tcr.CycleGauge("game", "full", team, elements, rules=rules)
    stops: list = []
    node_rules = None
    try:            # awakening node rules' resource rows (no database: no prepare hook runs in the preview)
        from src.services import awakening_node_rules

        cards = dict(awakening or {})
        node_rules = awakening_node_rules.for_selections(
            {cid: cards.get(cid, TEMPLATE_SELECTION) for cid in team})
        if node_rules.empty:
            node_rules = None
    except Exception:
        node_rules = None
    return _Walker(team, elements, rules, options, _PaletteMeasure(gauge, stops, _hit_credits(options)), gauge, stops,
                   None, awakening=awakening, node_rules=node_rules)


def preview_custom(team_ids: Sequence[int], sequence: Sequence[CustomStep],
                   options: CustomOptions | None = None, *, awakening: Mapping | None = None) -> CustomPreview:
    """No database, no engine: resolved actions, start times, the gauge track and the cooldown / energy / state
    notes from the generated palette.  Steps of members outside the team are left out; damage and hits are 0.
    ``awakening`` = {character id: node set} of the cards - a ``team_awakening.AwakeningSel``, a
    {"awakening_level", "selected_awaken_effect_ids"} dict or a legacy level (Effect1..level); None = the templates'
    selection (``TEMPLATE_SELECTION``)."""
    from src.services import team_simulation_service as svc

    team = [int(c) for c in team_ids]
    options = normalise_options(options, team)
    walker = _palette_walker(team, options, awakening)
    walk = walker.run([s for s in sequence if int(s.character_id) in team])
    _energy_pass(walk.records, team, options, None, walk.strict_eff)
    traces = _traces(walk.records, walk.layout, None)
    end = walk.layout.end_us
    return CustomPreview(steps=traces, wall_time_s=svc._seconds(end),
                         active_time_s=svc._active_between(walk.layout.stops, svc.START_US, end) / 1e6,
                         warnings=sum(1 for t in traces if t.warned))


# ── buffs ──────────────────────────────────────────────────────────────────
def manual_buff_modifiers(buff: ManualBuff) -> tuple:
    """((property id, value), ...) of one manual buff; () when it cannot be applied."""
    if buff.kind not in MANUAL_BUFF_KINDS:
        return ()
    value = float(buff.value) / 100.0 if buff.kind in PERCENT_BUFF_KINDS else float(buff.value)
    if buff.kind == "dmg_element":
        if buff.element not in ELEMENTS:
            return ()
        return ((f"DamageUp{buff.element.capitalize()}Base", value),)
    if buff.kind == "res_down":
        elements = (buff.element,) if buff.element in ELEMENTS else ELEMENTS
        return tuple((f"DamageResist{e.capitalize()}Add", -abs(value)) for e in elements)
    return ((_BUFF_PROPERTY[buff.kind], value),)


def _manual_scope(buff: ManualBuff, team_ids) -> tuple[str, str] | None:
    """(target scope, target id) of a manual buff; None when its target is not usable."""
    if buff.kind == "res_down":
        return "target", "dummy"
    if buff.target == "team":
        return "team", ""
    try:
        cid = int(buff.target)
    except (TypeError, ValueError):
        return None
    return (f"character:{cid}", "") if cid in [int(c) for c in team_ids] else None


def manual_buff_intervals(buffs, team_ids, end_us: int) -> tuple:
    """Manual buffs as engine intervals (built like the battle report's witch-blessing interval)."""
    from src.domain.battle_report import BattleBuffModifierEvidence, BattleInferredBuffInterval
    from src.services.team_simulation_service import START_US, _us

    out = []
    for i, buff in enumerate(buffs or ()):
        if not buff.enabled:
            continue
        modifiers = manual_buff_modifiers(buff)
        scope = _manual_scope(buff, team_ids)
        if not modifiers or scope is None:
            continue
        start_us = 0 if buff.start_s is None else START_US + _us(buff.start_s)
        stop_us = int(end_us) + 1 if buff.end_s is None else START_US + _us(buff.end_s)
        if stop_us <= start_us or start_us > int(end_us):  # empty window, or one that starts after the fight
            continue
        out.append(BattleInferredBuffInterval(
            interval_id=f"custom:manual:{i}", buff_asset_path=f"user-custom:manual:{i}",
            buff_name=f"manual:{buff.kind}", source_effect_definition_id=f"custom:manual:{i}",
            source_kind="user_confirmed_external_buff", source_character_id=0, source_character_name="",
            target_scope=scope[0], start_us=int(start_us), end_us=int(stop_us), stacks=1,
            duration_policy="battle_condition", state_confidence="高", value_confidence="高", inference_basis="",
            trigger_event_type="USER_CONFIRMED_BATTLE_CONDITION", evidence_action_ids=(), evidence_event_ids=(),
            target_id=scope[1],
            modifiers=tuple(BattleBuffModifierEvidence(
                property_id=prop, modifier_operation="EGameplayModOp::Additive", magnitude_kind="static_catalog",
                magnitude_value=value, calculation_asset_path="", value_confidence="高")
                for prop, value in modifiers)))
    return tuple(out)


class _BuffEdit:
    """Applied to the analysis right after buff inference: drops the switched-off team / target buffs and adds
    the manual ones.  Remembers what it dropped so the result can list it."""

    def __init__(self, options: CustomOptions, team_ids, holder: dict) -> None:
        self.options, self.team_ids, self.holder = options, list(team_ids), holder
        self.dropped: tuple = ()
        self.manual: tuple = ()

    def __call__(self, analysis):
        from src.services.team_simulation_service import buff_key

        disabled = self.options.disabled_buffs or frozenset()

        def off(iv) -> bool:
            return iv.target_scope in _LISTED_SCOPES and buff_key(iv) in disabled

        self.dropped = tuple(iv for iv in analysis.buff_intervals if off(iv))
        self.manual = manual_buff_intervals(self.options.manual_buffs, self.team_ids,
                                            int(self.holder.get("end_us") or 0))
        if not self.dropped and not self.manual:
            return analysis
        keep = tuple(iv for iv in analysis.buff_intervals if not off(iv))
        timeline = tuple(iv for iv in analysis.timeline_buff_intervals if not off(iv))
        return dataclasses.replace(analysis, buff_intervals=keep + self.manual,
                                   timeline_buff_intervals=timeline + self.manual)


def _buff_entries(intervals, enabled: bool) -> list[dict]:
    """Team / target buff lines in the shape of TeamResult.team_buffs (one line per buff, windows merged)."""
    from src.services.team_simulation_service import _seconds, buff_key

    lines: list[dict] = []
    by_buff: dict = {}
    for iv in intervals:
        if iv.target_scope not in _LISTED_SCOPES or str(iv.interval_id).startswith("custom:manual:"):
            continue
        mods = tuple((m.property_id, m.magnitude_value) for m in iv.modifiers)
        key = (iv.source_character_id, iv.source_effect_definition_id or iv.buff_asset_path, mods)
        if key not in by_buff:
            by_buff[key] = {"source_character_id": iv.source_character_id, "scope": iv.target_scope,
                            "modifiers": [{"property_id": p, "value": v} for p, v in mods], "_spans": [],
                            "key": buff_key(iv), "enabled": enabled, "manual": False}
            lines.append(by_buff[key])
        by_buff[key]["_spans"].append((max(0.0, _seconds(iv.start_us)), max(0.0, _seconds(iv.end_us))))
    collapsed: dict = {}
    for line in lines:
        windows: list[list[float]] = []
        for a, b in sorted(line.pop("_spans")):
            if windows and a <= windows[-1][1] + 1e-6:
                windows[-1][1] = max(windows[-1][1], b)
            else:
                windows.append([a, b])
        line["windows"] = [tuple(w) for w in windows]
        line["start_s"], line["end_s"] = line["windows"][0]
        look = (line["source_character_id"], tuple((m["property_id"], m["value"]) for m in line["modifiers"]),
                tuple(line["windows"]))
        if look in collapsed:
            collapsed[look]["count"] += 1
            if line["key"] not in collapsed[look]["keys"]:
                collapsed[look]["keys"].append(line["key"])
        else:
            line["count"], line["keys"] = 1, [line["key"]]
            collapsed[look] = line
    return list(collapsed.values())


def _manual_entries(options: CustomOptions, team_ids, end_us: int) -> list[dict]:
    from src.services.team_simulation_service import _seconds

    out = []
    intervals = {iv.interval_id: iv for iv in manual_buff_intervals(options.manual_buffs, team_ids, end_us)}
    for i, buff in enumerate(options.manual_buffs or ()):
        iv = intervals.get(f"custom:manual:{i}")
        if iv is None:
            scope = _manual_scope(buff, team_ids)
            modifiers = manual_buff_modifiers(buff)
            if buff.enabled and scope is not None and modifiers:       # only its time window kept it out
                start = max(0.0, float(buff.start_s or 0.0))
                end = max(0.0, _seconds(end_us) if buff.end_s is None else float(buff.end_s))
                out.append({"source_character_id": 0, "scope": scope[0],
                            "modifiers": [{"property_id": p, "value": v} for p, v in modifiers],
                            "windows": [(start, end)], "start_s": start, "end_s": end, "count": 1,
                            "key": f"custom:manual:{i}", "keys": [f"custom:manual:{i}"], "enabled": False,
                            "manual": True, "skipped": True, "kind": buff.kind, "target": buff.target,
                            "element": buff.element, "value": float(buff.value)})
            continue
        start, end = max(0.0, _seconds(iv.start_us)), max(0.0, min(_seconds(iv.end_us), _seconds(end_us)))
        out.append({"source_character_id": 0, "scope": iv.target_scope,
                    "modifiers": [{"property_id": m.property_id, "value": m.magnitude_value} for m in iv.modifiers],
                    "windows": [(start, end)], "start_s": start, "end_s": end, "count": 1,
                    "key": f"custom:manual:{i}", "keys": [f"custom:manual:{i}"], "enabled": True, "manual": True,
                    "kind": buff.kind, "target": buff.target, "element": buff.element, "value": float(buff.value)})
    return out


def _auto_charge_eff(analysis, team_ids, start_us: int, end_us: int) -> dict:
    """ChargeGetEfficiencyBase of each member's whole-fight self buffs (fork, cartridge set).  The engine ends
    whole-fight intervals at its own battle end (the last hit), so "whole fight" = from the start to the latest
    interval end.  The rule lives in team_resources (the reviewed mode uses it too)."""
    from src.services.team_resources import charge_eff_from_analysis

    return charge_eff_from_analysis(analysis, team_ids, start_us, end_us)


# ── simulate ───────────────────────────────────────────────────────────────
def simulate_custom(static_path, user_db_path, account_id, specs, sequence, options: CustomOptions | None = None,
                    *, lang: str = "ko"):
    """Simulate a custom cycle; returns a team_simulation_service.TeamResult.

    ``sequence`` is a CustomStep list or a typed text (parsed first; problems raise CustomCycleError)."""
    from src.services import team_simulation_explanation as tx
    from src.services import team_simulation_service as svc

    team_ids = [int(s.character_id) for s in specs]
    if len(set(team_ids)) != len(team_ids):
        raise ValueError("a character can only be in the team once")
    options = normalise_options(options, team_ids)
    steps = _as_steps(sequence, team_ids, lang)
    if executed_actions(steps, options.repeat) > MAX_ACTIONS:
        raise CustomCycleError([notation.ParseIssue("too_long", (MAX_ACTIONS,))])
    order = tuple(dict.fromkeys(int(s.character_id) for s in steps))
    holder: dict = {}
    with svc._open_context(static_path, user_db_path, account_id, specs, loops=options.repeat, gauge_rule="game",
                           opening_gauge="full") as ctx:
        ctx.target_condition = target_condition(options.target)
        edit = _BuffEdit(options, team_ids, holder)
        ctx.buff_edit = edit
        awakening = team_awakening.selections_of(ctx.characters)      # A11: the cards' node sets
        credits = _hit_credits(options)

        def lay(stops, gauge, sched):
            layout_hooks = svc._layout_hooks(ctx, "custom")              # awakening node rules (layout level)
            writer = svc._AxisWriter(ctx.static, ctx.by_key, ctx.names, gauge, stops, hit_credits=credits,
                                     node_hooks=layout_hooks)
            walk = _walk(steps, team_ids, ctx.elements, ctx.rules, options, _AxisMeasure(ctx, writer), gauge, stops,
                         writer.stop_owners, sched, awakening=awakening, eff_override=holder.get("eff"),
                         node_rules=ctx.node_rules, layout_hooks=layout_hooks)
            holder["walk"], holder["end_us"] = walk, walk.layout.end_us
            walk.layout.node_hooks = layout_hooks
            return walk.layout

        run = svc._run_axis(ctx, lay, order)
        walk: _Walk = holder["walk"]
        if walk.strict_eff:         # strict pools: walk again with the build's charge efficiency (review F-C)
            build_eff = _auto_charge_eff(run.analysis, team_ids, svc.START_US, run.layout.end_us)
            typed = {cid for cid, r in (options.resources or {}).items() if r.charge_eff is not None}
            if any(cid not in typed and abs(_Walker._own_eff(cid) + build_eff.get(cid, 0.0) - eff) > 1e-9
                   for cid, eff in walk.strict_eff.items()):
                holder["eff"] = build_eff
                run = svc._run_axis(ctx, lay, order)
                walk = holder["walk"]
        result = svc._collect(team_ids, ctx.characters, order, options.repeat, tx.ORDER_CUSTOM, "game", "full",
                              run.layout, run.dot_rows, run.reaction_rows, run.analysis, run.replays, run.sched,
                              run.to_active, ctx.elements, ctx.ability_names, {}, None)
        result = svc._with_fork_notes(result, run.corrections)       # Global arc corrections (B2-B4)
        result = svc._with_node_notes(result, run, ctx)              # awakening node rules
        auto_eff = _auto_charge_eff(run.analysis, team_ids, svc.START_US, run.layout.end_us)
        _energy_pass(walk.records, team_ids, options, auto_eff, walk.strict_eff)
        result.explanation = _custom_explanation(result.explanation, walk, steps, options, team_ids, edit, tx)
        result.team_buffs = (_buff_entries(run.analysis.buff_intervals, True)
                             + _buff_entries(edit.dropped, False)
                             + _manual_entries(options, team_ids, run.layout.end_us))
        return result


def _custom_explanation(expl, walk: _Walk, steps, options: CustomOptions, team_ids, edit, tx):
    """The approved-mode explanation re-labelled for a custom cycle (notes, member lines, the step table)."""
    traces = _traces(walk.records, walk.layout, expl)
    dropped_notes = {tx.ASSUME_APPROVED_ROTATIONS, tx.ASSUME_ORDER_AUTO, tx.ASSUME_ORDER_SLOT, tx.ASSUME_ORDER_PLAN,
                     tx.ASSUME_OPENING_FULL, tx.ASSUME_OPENING_ZERO, tx.ASSUME_FULL_GAUGE_LOOPS,
                     tx.ASSUME_GAUGE_GAME, tx.ASSUME_GAUGE_IDEAL, tx.ASSUME_NORMAL_ENTRY,
                     tx.ASSUME_ENERGY_NOT_GATED,
                     # form windows are not sized in this mode: the step notes and custom_form_free say so
                     tx.ASSUME_FORM_WINDOW, tx.LIMIT_FORM_CUT, tx.LIMIT_FORM_OVERRUN, tx.LIMIT_FORM_WINDOW_MISSED,
                     # the typed cycle is not the approved rotation (its awakening premise does not apply)
                     tx.LIMIT_ROTATION_ASSUMES_AWAKENING}
    as_typed = options.gauge_mode != "check"
    if as_typed:
        dropped_notes.add(tx.LIMIT_GAUGE_FIT)
    start_gauge = tuple((cid, float((options.start_gauge or {}).get(cid, 100.0))) for cid in team_ids)
    assumptions = [tx.note(tx.ASSUME_CUSTOM_SEQUENCE, options.repeat),
                   tx.note(tx.ASSUME_CUSTOM_AS_TYPED if as_typed else tx.ASSUME_CUSTOM_CHECK),
                   tx.note(tx.ASSUME_CUSTOM_START_GAUGE, *[x for pair in start_gauge for x in pair])]
    if options.resource_check == "off":
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_CD_OFF))
    elif options.resource_check == "wait":
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_CD_WAIT, round(walk.waited_us / 1e6, 3)))
    elif options.resource_check == "strict" and len(team_ids) > 1:     # D3: swap out at once in a team
        from src.services.team_resources import SWAP_MIN_WAIT_S

        assumptions.append(tx.note(tx.ASSUME_CUSTOM_STRICT_SWAP, int(getattr(walk, "early_swaps", 0) or 0),
                                   round(walk.waited_us / 1e6, 3), walk.skipped_energy, walk.skipped_cd,
                                   SWAP_MIN_WAIT_S))
    elif options.resource_check == "strict":
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_STRICT, round(walk.waited_us / 1e6, 3), walk.skipped_energy,
                                   walk.skipped_cd))
    else:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_CD_WARN))
    assumptions.append(tx.note(tx.ASSUME_CUSTOM_MODEL, resource_model_of(options)))
    disabled = sorted({_key_of(iv) for iv in edit.dropped})
    if disabled:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_BUFF_OFF, len(disabled)))
    if edit.manual:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_MANUAL_BUFF, len(edit.manual)))
    target = options.target
    if target != TargetOptions():
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_TARGET, target.enemy_level, target.resistance,
                                   target.defense_reduction, target.vulnerability))
    if getattr(target, "boss", False) or int(getattr(target, "enemy_count", 1) or 1) != 1:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_TARGET_KIND, int(bool(target.boss)), int(target.enemy_count)))
    assumptions += [item for item in expl.assumptions if tx.split_note(item)[0] not in dropped_notes]
    limits = [item for item in expl.limits if tx.split_note(item)[0] not in dropped_notes]
    custom_limits = []
    resources = options.resources or {}
    if options.resource_check != "off":
        custom_limits.append(tx.note(tx.LIMIT_CUSTOM_CD_DATA))
        if any(r.q_cost is not None for r in resources.values()):
            custom_limits.append(tx.note(tx.LIMIT_CUSTOM_ENERGY_MODEL))
        for cid in walk.own_resource:
            if cid in walk.clock_members:          # Hotori's clock was checked (resource levels)
                assumptions.append(tx.note(tx.ASSUME_OWN_RESOURCE, cid, "非闭合时计"))
                custom_limits.append(tx.note(tx.LIMIT_OWN_RESOURCE_DRAIN, cid, "非闭合时计"))
            else:
                custom_limits.append(tx.note(tx.LIMIT_CUSTOM_OWN_RESOURCE, cid))
        for cid in dict.fromkeys(c for c, _kind in walk.unchecked_cd):
            custom_limits.append(tx.note(tx.LIMIT_CUSTOM_CD_BLANK, cid,
                                         "/".join(kind for c, kind in walk.unchecked_cd if c == cid)))
        for cid in team_ids:            # awakening / skill rules applied to the cooldowns (review F-A)
            codes = tuple(c for c in (getattr(walk, "rules_used", {}) or {}).get(cid, ()) if c != "cd_offset")
            if codes:
                assumptions.append(tx.note(tx.ASSUME_CUSTOM_CD_RULES, cid, *codes))
        for cid, (seconds, per_visit) in (getattr(walk, "clock_interludes", {}) or {}).items():
            assumptions.append(tx.note(tx.ASSUME_HOTORI_INTERLUDE, cid, "非闭合时计", round(seconds, 2),
                                       "/".join(f"{s:.1f}" for s in per_visit)))
    hits = _hit_credits(options) or {}
    for cid in team_ids:                # summon hits not laid out (review F12)
        if (getattr(walk, "hit_credited", {}) or {}).get(cid):
            cell = next((c for (k, _a, _s), c in sorted(hits.items()) if k == cid and c[0] is not None), None)
            if cell is not None:
                custom_limits.append(tx.note(tx.LIMIT_HIT_CREDIT, cid, round(float(cell[0]), 3),
                                             round(float(cell[1]), 3), int(cell[2] or 0), str(cell[4])))
        if cid in (getattr(walk, "hit_unknown", ()) or ()):
            custom_limits.append(tx.note(tx.LIMIT_HIT_UNKNOWN, cid))
    if as_typed:
        custom_limits.append(tx.note(tx.LIMIT_CUSTOM_SUPPORT_FREE))
    custom_limits.append(tx.note(tx.LIMIT_CUSTOM_CHAIN_RESET))
    if walk.states_entered:
        custom_limits.append(tx.note(tx.LIMIT_CUSTOM_FORM_FREE))
    if walk.plain_swaps and not options.swap_time_s:
        custom_limits.append(tx.note(tx.LIMIT_CUSTOM_SWAP_TIME))
    members = []
    for member in expl.members:
        own = [t for t in traces if t.character_id == member.character_id and t.source_index >= 0]
        members.append(dataclasses.replace(
            member, variant_id=tx.VARIANT_CUSTOM, verdict="", confidence="", steps_total=len(own),
            steps_simulated=sum(1 for t in own if t.status == tx.STEP_OK and t.keys),
            steps_time_only=sum(1 for t in own if t.status == tx.STEP_TIME_ONLY)))
    trace = tx.CustomCycleTrace(
        steps=traces, sequence=tuple(steps), repeat=options.repeat, gauge_mode=options.gauge_mode,
        start_gauge=start_gauge, resource_check=options.resource_check,
        resources=tuple((cid, r.e_cd_s, r.q_cd_s, r.q_cost) for cid, r in resources.items()),
        waited_s=walk.waited_us / 1e6, warnings=sum(1 for t in traces if t.warned),
        target=(target.enemy_level, target.resistance, target.defense_reduction, target.vulnerability),
        buffs_disabled=tuple(disabled), buffs_manual=len(edit.manual))
    return dataclasses.replace(
        expl, order_mode=tx.ORDER_CUSTOM, gauge_rule=options.gauge_mode, opening_gauge=tx.OPENING_CUSTOM,
        loops=options.repeat, assumptions=tuple(assumptions), limits=tuple(limits + custom_limits),
        members=tuple(members), full_gauge_loops=(), custom=trace)


def _key_of(interval) -> str:
    from src.services.team_simulation_service import buff_key

    return buff_key(interval)


# ── reviewed rotation -> custom sequence ───────────────────────────────────
def _entry_index(character_id: int) -> dict:
    """action key (or tuple of keys for a combo) -> [(state code, slot, 1-based position)]."""
    from src.services import team_custom_actions as data

    p = data.PALETTE[int(character_id)]
    out: dict = {}
    tables = [("", p["base"])] + [(code, st["slots"]) for code, st in p["states"].items()]
    for tid, table in tables:
        for slot, spec in table.items():
            for i, entry in enumerate(spec["entries"], 1):
                if not entry or entry[0] == "@time":
                    continue
                keys = tuple(tuple(k) for k in entry)
                out.setdefault(keys[0] if len(keys) == 1 else keys, []).append((tid, slot, i))
    return out


def layout_as_sequence(layout, team_ids) -> tuple:
    """One approved layout as custom steps.  A palette walker runs alongside, so every emitted token is known to
    resolve to exactly the action the approved run placed: a plain token where it does, ``slot#N`` where only the
    position does, a raw key otherwise.  Time-only steps become waits; skipped and cut steps are left out."""
    team = [int(c) for c in team_ids]
    walker = _palette_walker(team, CustomOptions(resource_check="off"))
    walker.reset_gauges()
    out: list[CustomStep] = []

    def emit(step: CustomStep) -> None:
        out.append(step)
        walker.step(step, len(out) - 1)

    def flush(cid: int, flat: list) -> None:
        index = _entry_index(cid)
        i = 0
        while i < len(flat):
            done = False
            for width in (2, 1):
                if i + width > len(flat):
                    continue
                want = tuple(flat[i:i + width])
                candidates = [c for c in index.get(want if width > 1 else want[0], ()) if c[1] != "support"]
                for explicit in (False, True):
                    for _tid, slot, pos in candidates:
                        if walker.peek(cid, slot, pos if explicit else None) == want:
                            emit(CustomStep(cid, slot, pos if explicit else None))
                            done = True
                            break
                    if done:
                        break
                if done:
                    i += width
                    break
            if not done:
                emit(CustomStep(cid, RAW_ACTION, None, 1, None, tuple(flat[i])))
                i += 1

    for visit in layout.visits:
        cid = int(visit.character_id)
        runs = [s for s in visit.steps if s.status not in ("skipped_entry", "form_cut", "cd_skip", "energy_short",
                                                           "swap_out", "swap_dropped")]
        if visit.entry == "support_skill":
            emit(CustomStep(cid, "support"))
            runs = runs[1:]                        # the support-skill step itself
        elif visit.entry == "normal":
            emit(CustomStep(cid, "swap"))
        flat: list = []
        for run in runs:
            if run.status in ("time_only", "time_default", "missing_candidate") or not run.actions:
                flush(cid, flat)
                flat = []
                seconds = (int(run.end_us) - int(run.start_us)) / 1e6
                while seconds > 1e-9:
                    part = min(seconds, notation.MAX_WAIT_S)
                    emit(CustomStep(cid, "wait", None, 1, round(part, 6)))
                    seconds -= part
                continue
            flat.extend(tuple(a) for a in run.actions)
        flush(cid, flat)
    return notation.merge_steps(out)


def approved_as_sequence(static_path, user_db_path, account_id, specs, *, order: Sequence[int] | None = None,
                         order_mode: str = "auto", whole_run: bool = False, resource_model: str | None = None) -> tuple:
    """The reviewed rotations as a custom sequence (the page's "load approved rotation").

    Default: one loop, to be extended with the repeat count (repeating it is not the reviewed run: the typed
    entries are repeated as they are and no gauge is refilled).  ``whole_run``: every loop of the reviewed run
    (``DEFAULT_LOOPS``), entry by entry; simulated with repeat 1 and the default options it gives the reviewed
    result of the same visit order."""
    from src.services import team_simulation_service as svc

    team_ids = [int(s.character_id) for s in specs]
    for cid in team_ids:
        svc._approved_steps(cid)
    loops = svc.DEFAULT_LOOPS if whole_run else 1
    with svc._open_context(static_path, user_db_path, account_id, specs, loops=loops, gauge_rule="game",
                           opening_gauge=svc._effective_opening("full")) as ctx:
        ctx.policy = svc.resolve_policy(resource_model)    # waits / skipped ultimates of the reviewed run
        if order and sorted(int(c) for c in order) == sorted(team_ids):
            chosen = tuple(int(c) for c in order)
        else:
            chosen = svc._visit_order(team_ids, ctx.elements, "slot" if order_mode == "slot" else "auto")
        layout, _sched, _to_active = svc._dry_layout(ctx, chosen)
    return layout_as_sequence(layout, team_ids)
