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
"""
from __future__ import annotations

import dataclasses
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.services import team_custom_notation as notation
from src.services.team_custom_notation import ENTRY_ACTIONS, RAW_ACTION, SLOT_ACTIONS, CustomStep

GAUGE_MODES = ("as_typed", "check")
RESOURCE_CHECKS = ("off", "warn", "wait")
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


def default_resources(character_id: int) -> MemberResource:
    """E / Q cooldown and Q cost the static data has for the member (blank otherwise)."""
    from src.services import team_custom_actions as data

    row = data.RESOURCES.get(int(character_id)) or {}
    return MemberResource(**{k: float(v[0]) for k, v in row.items() if k in ("e_cd_s", "q_cd_s", "q_cost")})


def default_options(team_ids: Sequence[int]) -> CustomOptions:
    """Start gauge 100, data-backed E / Q numbers, everything else default."""
    team = [int(c) for c in team_ids]
    return CustomOptions(start_gauge={cid: 100.0 for cid in team},
                         resources={cid: default_resources(cid) for cid in team})


def normalise_options(options: CustomOptions | None, team_ids: Sequence[int]) -> CustomOptions:
    """Clamp every number to its range; members without a value get the defaults."""
    team = [int(c) for c in team_ids]
    base = default_options(team)
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
                             vulnerability=_clamp(target.vulnerability, 0.0, 2.0, 0.0)),
        swap_time_s=_clamp(options.swap_time_s, 0.0, MAX_SWAP_TIME_S, 0.0))


def options_to_json(options: CustomOptions) -> dict:
    return {
        "repeat": int(options.repeat), "gauge_mode": options.gauge_mode,
        "start_gauge": {str(cid): float(v) for cid, v in (options.start_gauge or {}).items()},
        "gauge_reset_each_repeat": bool(options.gauge_reset_each_repeat),
        "resource_check": options.resource_check,
        "resources": {str(cid): dataclasses.asdict(r) for cid, r in (options.resources or {}).items()},
        "disabled_buffs": sorted(options.disabled_buffs or ()),
        "manual_buffs": [dataclasses.asdict(b) for b in (options.manual_buffs or ())],
        "target": dataclasses.asdict(options.target or TargetOptions()),
        "swap_time_s": float(options.swap_time_s),
    }


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
                             vulnerability=target.get("vulnerability", 0.0)),
        swap_time_s=obj.get("swap_time_s", 0.0))
    if team:
        return normalise_options(options, team)
    # no team given: clamp what does not depend on it
    members = sorted(set(options.start_gauge) | set(options.resources))
    return normalise_options(options, members)


def target_condition(target: TargetOptions) -> dict:
    """The engine's target dict; with the defaults it equals team_simulation_service.DEFAULT_TARGET."""
    out = {"confirmed": True, "enemy_level": int(target.enemy_level), "scene": "outer_realm",
           "resistances": {k: float(target.resistance) for k in _RESISTANCE_KEYS}}
    if target.defense_reduction:
        out["defense_reduction"] = float(target.defense_reduction)
    if target.vulnerability:
        out["vulnerability"] = float(target.vulnerability)
    return out


# ── walker ─────────────────────────────────────────────────────────────────
@dataclass
class _Measured:
    length_us: int
    hits: int = 0
    energy: float = 0.0
    status: str = "ok"                    # ok | missing_candidate


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
    cd_kind: str = ""


@dataclass
class _Walk:
    layout: Any                           # team_simulation_service._Layout
    records: list
    waited_us: int = 0
    states_entered: bool = False
    own_resource: tuple = ()              # OWN_RESOURCE members that used their ultimate
    plain_swaps: int = 0
    unchecked_cd: tuple = ()              # ((character id, "E" | "Q"), ...) used again with a blank cooldown


class _PaletteMeasure:
    """Numbers from the generated palette: no database, no hit rows (preview and conversion)."""

    def __init__(self, gauge, stops: list) -> None:
        from src.services import team_custom_actions as data
        from src.services import team_simulation_service as svc

        self._data, self._svc, self.gauge, self.stops = data, svc, gauge, stops
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
        return _Measured(self._svc._us(action["length_s"]), int(action["hits"]), float(action["energy"]))


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
        return _Measured(int(length), len(rows), energy)


class _Walker:
    """Executes custom steps on one timeline (see the module docstring)."""

    def __init__(self, team_ids, elements, rules, options: CustomOptions, measure, gauge, stops: list,
                 sched=None) -> None:
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
        as_typed = self.options.gauge_mode != "check"
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
            elif full or as_typed:
                entry, outcome = tx.ENTRY_SUPPORT_SKILL, tx.OUTCOME_REACTION
                info["play"], info["fired"] = True, pair
                if not full:
                    info["notes"].append(tx.note(tx.NOTE_CUSTOM_GAUGE_SHORT, round(gauge, 3)))
            else:
                outcome, info["skipped"] = tx.OUTCOME_GAUGE_SHORT, True
                info["notes"].append(tx.note(tx.NOTE_CUSTOM_DOWNGRADED_GAUGE, round(gauge, 3)))
        elif tok is None:
            info["notes"].append(tx.note(tx.NOTE_CUSTOM_IMPLICIT_SWAP))
        self.swaps.append(self.svc._SwapRun(len(self.swaps), self.t, out, cid, eo, ei, gauge, outcome, None))
        info.update(entry=entry, swap_index=len(self.swaps) - 1, out_gauge=gauge)
        if info["fired"] is not None:
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

    def _cd_value(self, cid: int, kind: str) -> float | None:
        resource = (self.options.resources or {}).get(cid)
        if resource is None or not kind:
            return None
        return resource.e_cd_s if kind == "E" else resource.q_cd_s

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
            return
        notes: list = []
        resolved = None
        cd_kind = ""
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
        if cd_kind and value is None and check != "off" and cd_kind in m.cd:
            self.unchecked_cd.add((cid, cd_kind))          # nothing to check against: listed under the limits
        if cd_kind and value is not None and check != "off" and cd_kind in m.cd:
            remaining = svc._us(value) - self._active(m.cd[cd_kind], self.t)
            if remaining > CD_TOLERANCE_US:
                if check == "wait":
                    target = self._advance(self.t, remaining)
                    wait_before = target - self.t
                    self._time_step(-1, cid, "wait", wait_before)
                    self.waited_us += wait_before
                    self.seq += 1
                    notes.append(tx.note(tx.NOTE_CUSTOM_CD_WAITED, round(remaining / 1e6, 3)))
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
        if cd_kind:
            m.cd[cd_kind] = start
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
            self._after_step(cid, tid, start, notes)
        rec.end_us = self.t
        rec.gauge_after = float(self.gauge.value(cid))
        rec.notes += notes
        self.records.append(rec)

    def _after_key(self, cid: int, key: tuple, t0: int, notes: list) -> None:
        """State exit / start markers of one placed action."""
        tx, svc, m = self.tx, self.svc, self.members[cid]
        st = self._state(cid)
        if st is not None and key in st["exit"]:
            elapsed = self._elapsed(cid, t0)
            window = st["window_s"]
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
            self._press(step, src, k, info if k == 0 else None)

    # driving ----------------------------------------------------------------
    def reset_gauges(self) -> None:
        for cid in self.team:
            self.gauge.set_value(cid, _clamp((self.options.start_gauge or {}).get(cid, 100.0), 0.0, 100.0, 100.0))

    def step(self, step: CustomStep, src: int) -> None:
        if int(step.character_id) not in self.members:
            return
        if step.action in ENTRY_ACTIONS:
            self._entry_step(step, src)
        else:
            self._action_step(step, src)

    def run(self, steps: Sequence[CustomStep]) -> _Walk:
        self.reset_gauges()
        for rep in range(max(1, int(self.options.repeat))):
            self.rep = rep
            if rep and self.options.gauge_reset_each_repeat:
                self.reset_gauges()
            for src, step in enumerate(steps):
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
        return _Walk(layout, self.records, self.waited_us, self.states_entered, tuple(sorted(self.own_resource)),
                     self.plain_swaps, tuple(sorted(self.unchecked_cd)))


def _walk(steps, team_ids, elements, rules, options, measure, gauge, stops, stop_owners=None, sched=None) -> _Walk:
    """Lay the custom steps out: returns the engine layout plus the per-step records."""
    return _Walker(team_ids, elements, rules, options, measure, gauge, stops, sched).run(steps)


# ── energy (never changes the timeline: a pass over the step records) ──────
def _energy_pass(records: list, team_ids, options: CustomOptions, auto_eff: Mapping | None = None) -> None:
    from src.services import team_custom_actions as data
    from src.services import team_simulation_explanation as tx

    energy: dict = {}
    cost: dict = {}
    eff: dict = {}
    for cid in team_ids:
        resource = (options.resources or {}).get(cid)
        if resource is None or resource.q_cost is None or cid in data.OWN_RESOURCE:
            continue
        cost[cid] = float(resource.q_cost)
        start = cost[cid] if resource.start_energy is None else float(resource.start_energy)
        energy[cid] = max(0.0, min(cost[cid], start))
        eff[cid] = float(resource.charge_eff) if resource.charge_eff is not None \
            else float((auto_eff or {}).get(cid, 0.0))
    for rec in records:
        cid = rec.character_id
        if cid not in energy:
            rec.energy_after = None
            continue
        if rec.cd_kind == "Q":
            if energy[cid] + 1e-6 < cost[cid] and options.resource_check != "off":
                rec.notes.append(tx.note(tx.NOTE_CUSTOM_ENERGY_SHORT, round(energy[cid], 3), cost[cid]))
            energy[cid] = max(0.0, energy[cid] - cost[cid])
        energy[cid] = min(cost[cid], energy[cid] + float(rec.energy_gain or 0.0) * (1.0 + eff[cid]))
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
            out_character_id=rec.out_character_id))
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
def _palette_walker(team_ids, options: CustomOptions):
    from src.services import team_custom_actions as data
    from src.services import team_cycle_reactions as tcr

    team = [int(c) for c in team_ids]
    elements = {cid: (data.PALETTE.get(cid) or {}).get("element", "") for cid in team}
    rules = tcr.DEFAULT_RULES
    gauge = tcr.CycleGauge("game", "full", team, elements, rules=rules)
    stops: list = []
    return _Walker(team, elements, rules, options, _PaletteMeasure(gauge, stops), gauge, stops, None)


def preview_custom(team_ids: Sequence[int], sequence: Sequence[CustomStep],
                   options: CustomOptions | None = None) -> CustomPreview:
    """No database, no engine: resolved actions, start times, the gauge track and the cooldown / energy / state
    notes from the generated palette.  Steps of members outside the team are left out; damage and hits are 0."""
    from src.services import team_simulation_service as svc

    team = [int(c) for c in team_ids]
    options = normalise_options(options, team)
    walker = _palette_walker(team, options)
    walk = walker.run([s for s in sequence if int(s.character_id) in team])
    _energy_pass(walk.records, team, options, None)
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
    interval end."""
    out = {int(cid): 0.0 for cid in team_ids}
    intervals = list(getattr(analysis, "buff_intervals", ()) or ())
    last = min(int(end_us), max((int(iv.end_us) for iv in intervals), default=int(end_us)))
    for iv in intervals:
        cid = int(iv.source_character_id or 0)
        if iv.target_scope != "self" or cid not in out:
            continue
        if int(iv.start_us) > int(start_us) or int(iv.end_us) < last:
            continue
        for m in iv.modifiers:
            if m.property_id == "ChargeGetEfficiencyBase" and m.magnitude_value:
                out[cid] += float(m.magnitude_value) * max(1, int(iv.stacks or 1))
    return out


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

        def lay(stops, gauge, sched):
            writer = svc._AxisWriter(ctx.static, ctx.by_key, ctx.names, gauge, stops)
            walk = _walk(steps, team_ids, ctx.elements, ctx.rules, options, _AxisMeasure(ctx, writer), gauge, stops,
                         writer.stop_owners, sched)
            holder["walk"], holder["end_us"] = walk, walk.layout.end_us
            return walk.layout

        run = svc._run_axis(ctx, lay, order)
        walk: _Walk = holder["walk"]
        result = svc._collect(team_ids, ctx.characters, order, options.repeat, tx.ORDER_CUSTOM, "game", "full",
                              run.layout, run.dot_rows, run.reaction_rows, run.analysis, run.replays, run.sched,
                              run.to_active, ctx.elements, ctx.ability_names, {}, None)
        result = svc._with_fork_notes(result, run.corrections)       # Global arc corrections (B2-B4)
        auto_eff = _auto_charge_eff(run.analysis, team_ids, svc.START_US, run.layout.end_us)
        _energy_pass(walk.records, team_ids, options, auto_eff)
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
                     tx.ASSUME_FORM_WINDOW, tx.LIMIT_FORM_CUT, tx.LIMIT_FORM_OVERRUN, tx.LIMIT_FORM_WINDOW_MISSED}
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
    else:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_CD_WARN))
    disabled = sorted({_key_of(iv) for iv in edit.dropped})
    if disabled:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_BUFF_OFF, len(disabled)))
    if edit.manual:
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_MANUAL_BUFF, len(edit.manual)))
    target = options.target
    if target != TargetOptions():
        assumptions.append(tx.note(tx.ASSUME_CUSTOM_TARGET, target.enemy_level, target.resistance,
                                   target.defense_reduction, target.vulnerability))
    assumptions += [item for item in expl.assumptions if tx.split_note(item)[0] not in dropped_notes]
    limits = [item for item in expl.limits if tx.split_note(item)[0] not in dropped_notes]
    custom_limits = []
    resources = options.resources or {}
    if options.resource_check != "off":
        custom_limits.append(tx.note(tx.LIMIT_CUSTOM_CD_DATA))
        if any(r.q_cost is not None for r in resources.values()):
            custom_limits.append(tx.note(tx.LIMIT_CUSTOM_ENERGY_MODEL))
        for cid in walk.own_resource:
            custom_limits.append(tx.note(tx.LIMIT_CUSTOM_OWN_RESOURCE, cid))
        for cid in dict.fromkeys(c for c, _kind in walk.unchecked_cd):
            custom_limits.append(tx.note(tx.LIMIT_CUSTOM_CD_BLANK, cid,
                                         "/".join(kind for c, kind in walk.unchecked_cd if c == cid)))
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
        runs = [s for s in visit.steps if s.status not in ("skipped_entry", "form_cut")]
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
                         order_mode: str = "auto", whole_run: bool = False) -> tuple:
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
        if order and sorted(int(c) for c in order) == sorted(team_ids):
            chosen = tuple(int(c) for c in order)
        else:
            chosen = svc._visit_order(team_ids, ctx.elements, "slot" if order_mode == "slot" else "auto")
        layout, _sched, _to_active = svc._dry_layout(ctx, chosen)
    return layout_as_sequence(layout, team_ids)
