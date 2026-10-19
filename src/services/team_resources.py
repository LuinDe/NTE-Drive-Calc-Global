# 队伍模拟：终结能量、环合值补满规则与冷却（纯逻辑，不导入战报引擎）。
"""Ultimate energy, the Esper-Cycle gauge refill rule and cooldowns of the team simulator.

Pure module (no engine, no database): ``team_simulation_service`` (reviewed rotations) and
``team_custom_cycle_service`` (custom cycles) drive one :class:`ResourceState` per layout.  The numbers come from
the generated ``team_resource_data`` (cells ``(value | None, source, confidence)``).

Resource levels (``RESOURCE_MODELS``):

* ``legacy``    - the old rule, bit for bit: no energy / cooldown check, every gauge refilled at the start of the
                  loops in ``team_cycle_reactions.FULL_GAUGE_LOOPS`` (1 and 3).  The service passes no state at all.
* ``data``      - game data only (DB values, DB text, "no cooldown of its own" by structure, converged measurements).
* ``community`` - ``data`` plus prydwen cooldowns (``community_low``), the recommended default.

Per step (reviewed and custom mode alike, :meth:`ResourceState.gate`): energy first (a pool that is short skips the
ultimate - waiting never fills it; an own clock that is short is waited for), then one combined wait for the cooldown
and the own resource on the policy clock (``active`` = battle time without time stops, ``wall`` = real time), a guard
(``max_wait_guard_s``, or the custom ``cd_wait_max_s``) turning longer waits into skips.  What a layout does with a step
that is not ready is ``ResourcePolicy.not_ready`` (user decision D3, 2026-10-14): in a team the member swaps out at once
(``swap``; the rest of the visit is not run), alone there is nobody to swap to and it waits (``wait``); when every member
is blocked the layout waits for the earliest ready one (``first_block_us``).  A Q cost is enforced only
from game data (``team_resource_data.COST_ENFORCED``); unknown costs leave the ultimate unchecked and the energy
gain is still tracked for display.  Gauge: hits add ``heterochrome_add`` (``CycleGauge``) as before; only members in
the fallback set (no gauge data in the approved loop, or steps without an animation match) are refilled at the old
refill loops - everyone else keeps the accumulated gauge.

Awakening (design A7/A8, Global): ``ResourceState(awakening=...)`` takes each member's node set (team_awakening
``AwakeningSel``; an int is a legacy level = Effect1..level).  The integer ``awakening`` field of the generated
``team_resource_data`` rules / energy events is the **node number** n = ``Effect<n>`` (Mint E1 counter -> E reset,
Haniel E6 E cooldown -4 s, Adler E5 +20 after Q, 「零」 E2 +8 after E, Linko E3 Q -> E reset); a resonance rule would
say ``"resonance_3"``.  ``unlocked`` reads them against the selected set.  Awakening node rules
(``awakening_node_rules``) add rows of the same shapes (``extra_rules`` / ``extra_events``) and callable hooks
(``hooks``: ``begin`` / ``after``, reviewed layouts).  Reset rules: ``q_resets_e`` (a Q clears the E cooldown),
``counter_resets_e`` (a counter clears it; internal cooldown = the row's value in seconds or a ``reset_icd`` row) and
``e_resets_q`` (an E of the named selectors clears the Q cooldown, ``reset_matches``; not on a boss when the row says
so).  ``ResourceState.target`` = the run's target dict (None = DEFAULT_TARGET: one non-boss Lv80 enemy).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

RESOURCE_MODELS = ("legacy", "data", "community")
SHIPPED_RESOURCE_MODEL = "community"     # user request 2026-10-13 ("전부 다 적용"); design D4 recommendation
# NTE_TEAM_RESOURCE_MODEL=legacy|data|community overrides the default (regression runs; like
# NTE_TEAM_FORK_CORRECTIONS=off for team_fork_corrections)
DEFAULT_RESOURCE_MODEL = (os.environ.get("NTE_TEAM_RESOURCE_MODEL", "").strip().lower()
                          if os.environ.get("NTE_TEAM_RESOURCE_MODEL", "").strip().lower() in RESOURCE_MODELS
                          else SHIPPED_RESOURCE_MODEL)
CLOCKS = ("active", "wall")
ENERGY_POLICIES = ("skip", "warn", "off")
COOLDOWN_POLICIES = ("wait", "warn", "off")
INTERLUDE_POLICIES = ("auto", "credit", "wait", "strict")
# a step that is not ready (cooldown / own clock, or a known ultimate cost the pool cannot pay) - user decision D3
# (2026-10-14): auto = swap out at once in a team, wait when alone (nobody to swap to); swap / wait force one reading
NOT_READY_POLICIES = ("auto", "swap", "wait")
# user decision 2026-10-18: with the swap rule a cooldown that has LESS than this much battle time (policy clock) left
# is waited for and the skill cast; 0.3 s or more swaps out at once.  Cooldowns only (an energy-short ultimate cannot be
# waited for; Hotori's clock and the guard keep their rule); alone the member always waits.
SWAP_MIN_WAIT_S = 0.3
TOLERANCE_US = 1000                      # 1 ms (the layout's overrun tolerance)
ENERGY_EPS = 1e-6


def reset_matches(value, selector, target=None) -> bool:
    """Does an ``e_resets_q`` row fire for an E with ``selector``?  ``value`` None = any E; a dict
    ``{"selectors": (...), "not_on_boss": bool}`` (a tuple / list = the selectors).  ``target`` = the run's target
    dict (``boss`` true = a boss enemy; team_custom_cycle_service.TargetOptions)."""
    if value is None:
        return True
    if isinstance(value, Mapping):
        selectors = value.get("selectors")
        if value.get("not_on_boss") and bool((target or {}).get("boss")):
            return False
    else:
        selectors = value
    if selectors is None:
        return True
    if isinstance(selectors, str):
        selectors = (selectors,)
    return str(selector or "") in {str(s) for s in selectors}


def reset_icd_s(rows, code: str, value=None, unlocked=None) -> float:
    """Internal cooldown (seconds) of a reset rule: its own numeric value, else a ``reset_icd`` row naming ``code``
    (``unlocked(node)`` gates the row; None = always), else 0."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 0:
        return float(value)
    for row in rows or ():
        if (row[0] == "reset_icd" and row[1] == code and isinstance(row[2], (int, float))
                and not isinstance(row[2], bool) and float(row[2]) > 0 and (unlocked is None or unlocked(row[3]))):
            return float(row[2])
    return 0.0
CHARGES_KIND = "E"
# approved time-only steps that build no gauge in the game (waits, idle stacking, a plain evade)
TIME_ONLY_NO_GAUGE = frozenset(((1052, 3), (1076, 1), (1023, 4)))


@dataclass(frozen=True)
class ResourcePolicy:
    model: str = SHIPPED_RESOURCE_MODEL
    energy: str = "skip"                 # skip | warn | off      (pool energy short before a paid ultimate)
    cooldown: str = "wait"               # wait | warn | off      (cooldown / own resource not ready)
    cd_wait_max_s: float | None = None   # None = unbounded (design D3); custom option
    max_wait_guard_s: float = 60.0       # a longer wait is a data error: the step is skipped and listed
    gauge_refill: str = "fallback"       # fallback | all | none  (refill loops of FULL_GAUGE_LOOPS)
    clock: str = "active"                # active | wall          (design D5)
    own_clock_interlude: str = "auto"    # auto | credit | wait | strict  (Hotori's "swap out and wait", D15)
    shinku_meter: str = "track"          # track | gate           (gain unit unresolved, D12)
    contested: bool = False              # enforce contested DB values (Lacrimosa's legacy table) - chunk 0 review R3
    time_only_credit: bool = True        # gauge of time-only steps whose action is known (design §3.6)
    not_ready: str = "auto"              # auto | swap | wait  (D3: team swaps out at once, solo waits)
    swap_min_wait_s: float = SWAP_MIN_WAIT_S     # swap rule: a cooldown with less left is waited for (2026-10-18)

    @property
    def legacy(self) -> bool:
        return self.model == "legacy"


LEGACY = ResourcePolicy(model="legacy", energy="off", cooldown="off", gauge_refill="all", time_only_credit=False)


def policy_for(model: str | None = None, **overrides) -> ResourcePolicy:
    """The policy of a resource level (``None`` = DEFAULT_RESOURCE_MODEL); keyword overrides for tests / options."""
    model = DEFAULT_RESOURCE_MODEL if model is None else str(model)
    if model not in RESOURCE_MODELS:
        raise ValueError(f"unknown resource model {model!r}")
    base = LEGACY if model == "legacy" else ResourcePolicy(model=model)
    return replace(base, **overrides) if overrides else base


def _data():
    from src.services import team_resource_data

    return team_resource_data


# ── cells ─────────────────────────────────────────────────────────────────

def record(cid: int, data=None) -> dict:
    return (data or _data()).RESOURCES.get(int(cid)) or {}


def enforced_confidences(policy: ResourcePolicy, data=None) -> tuple:
    data = data or _data()
    allowed = tuple(data.ENFORCED.get(policy.model, ()))
    if policy.contested and allowed:
        allowed += tuple(data.CONTESTED)
    return allowed


def cd_cell(cid: int, kind: str, policy: ResourcePolicy, data=None):
    """The enforced cooldown cell of a kind at the policy's level, or None (unknown / not enforced)."""
    allowed = enforced_confidences(policy, data)
    for c in (record(cid, data).get("cd") or {}).get(kind, ()):
        if c and c[0] is not None and c[2] in allowed:
            return c
    return None


def best_cd_cell(cid: int, kind: str, data=None):
    """The best known cell of a kind (display; may be unenforced)."""
    cells = (record(cid, data).get("cd") or {}).get(kind, ())
    return next((c for c in cells if c and c[0] is not None), cells[0] if cells else None)


def cost_cell(cid: int, policy: ResourcePolicy, data=None):
    """The enforced Q cost cell (pool ultimates), or None."""
    data = data or _data()
    c = (record(cid, data).get("energy") or {}).get("cost")
    if not c or c[0] is None or policy.legacy:
        return None
    allowed = tuple(data.COST_ENFORCED) + (tuple(data.CONTESTED) if policy.contested else ())
    return c if c[2] in allowed else None


_SITE = ("prydwen", "gamewith_jp", "mysqil", "namu", "inven", "biligame")


def source_tag(cell) -> str:
    """Short ASCII tag of a cell's source for tooltips ("prydwen 2026-09-07", "DT_ChaosEffectFigure.Chaos_UltraskillCD",
    "GA_Jin_Skill"): the raw sources quote game / site text in several languages.  No English words: the confidence
    pill next to it already says "description text" / "game data" in the reader's language (review F10)."""
    import re

    if not cell or len(cell) < 3:
        return ""
    source, conf = str(cell[1] or ""), str(cell[2] or "")
    if conf.startswith("community") or any(site in source for site in _SITE):
        site = next((s for s in _SITE if s in source), "")
        date = re.search(r"20\d\d-\d\d-\d\d", source)
        return " ".join(p for p in (site, date.group(0) if date else "") if p)
    data = re.search(r"data:([A-Za-z0-9_.]+)", source)
    if data:
        return data.group(1)
    ability = re.search(r"\b(GA_[A-Za-z0-9_]+)", source)
    return ability.group(1) if ability else ""


def confidence_group(conf: str) -> str:
    """Display group of a confidence: data | text | measured | community | inference | unknown."""
    return {"db_value": "data", "db_struct_none": "data", "db_text": "text", "measured_value": "measured",
            "db_legacy": "contested", "inference": "inference", "community_low": "community",
            "community_very_low": "community_tip", "measured_bound": "unknown", "user": "user"}.get(conf, "unknown")


# ── clocks ────────────────────────────────────────────────────────────────

def active_between(stops, a_us: int, b_us: int) -> int:
    """Active µs between two wall times (time stops excluded); = team_simulation_service._active_between."""
    if b_us <= a_us:
        return 0
    total = b_us - a_us
    for s, e in stops:
        lo, hi = max(a_us, s), min(b_us, e)
        if hi > lo:
            total -= hi - lo
    return total


def advance_active(t_us: int, active_us: int, stops) -> int:
    """Wall time at which ``active_us`` of active time has passed since ``t_us`` (= the custom walker's _advance)."""
    wall, left = int(t_us), int(active_us)
    for start, end in sorted(stops):
        if end <= wall:
            continue
        if start > wall:
            gap = start - wall
            if left <= gap:
                return wall + left
            left -= gap
        wall = end
    return wall + left


# ── charge efficiency of the build ──────────────────────────────────────────

def charge_eff_from_analysis(analysis, team_ids, start_us: int, end_us: int) -> dict:
    """ChargeGetEfficiencyBase of each member's whole-fight self buffs (arc, cartridge set) in an engine analysis.

    The engine ends whole-fight intervals at its own battle end (the last hit), so "whole fight" = from the start to
    the latest interval end.  Same rule as the custom-cycle mode's energy pass."""
    out = {int(cid): 0.0 for cid in team_ids}
    intervals = list(getattr(analysis, "buff_intervals", ()) or ())
    last = min(int(end_us), max((int(iv.end_us) for iv in intervals), default=int(end_us)))
    for iv in intervals:
        cid = int(iv.source_character_id or 0)
        if iv.target_scope != "self" or cid not in out:
            continue
        if int(iv.start_us) > int(start_us) or int(iv.end_us) < last:
            continue
        for mod in iv.modifiers:
            if mod.property_id == "ChargeGetEfficiencyBase" and mod.magnitude_value:
                out[cid] += float(mod.magnitude_value) * max(1, int(iv.stacks or 1))
    return out


# ── step classification ───────────────────────────────────────────────────

@dataclass(frozen=True)
class StepClass:
    cd_kind: str | None                  # E | E_alt | Q | QTE | counter | None
    cost_ref: str | None                 # q_cost | e_cost (own clock E) | None
    reason: str
    requires_seq: int | None = None      # free ultimate: the paid Q it follows (same visit)


NO_CLASS = StepClass(None, None, "none")


def classify_rotation(cid: int, steps: Sequence[Mapping], data=None) -> dict[int, StepClass]:
    """Every approved step of a member -> StepClass (the ordered rules of design §3.5; snapshot STEP_CLASS)."""
    from src.services.team_form_actions import FORMS

    rec = record(cid, data)
    free = set(rec.get("free_ultimates") or ())
    kinds = dict(rec.get("ability_kinds") or {})
    own_clock = (rec.get("energy") or {}).get("kind") == "own_clock"
    interlude = set(rec.get("interlude_steps") or ())
    rule = FORMS.get(int(cid)) or {}
    form_start = (rule.get("start") or (None,))[0]
    out: dict[int, StepClass] = {}
    prev = None
    last_paid_q = None
    for s in steps:
        slot, ab, sel = s.get("slot"), s.get("ability_id"), s.get("selector") or ""
        role = s.get("form_role")
        req = None
        if not s.get("sim"):
            k, cost, reason = None, None, ("own_clock_wait" if int(s.get("seq") or 0) in interlude else "time_only")
        elif ab in free:
            k, cost, reason, req = None, None, "free_ultimate", last_paid_q
        elif ab in kinds:
            k, cost, reason = kinds[ab], None, "ability_kind"
        elif slot == "ultimate":
            k, cost, reason = "Q", "q_cost", "ultimate"
        elif s.get("combo") and slot in ("skill", "basic"):
            k, cost, reason = None, None, f"form_{role}"
        elif role == "exit" and ab == form_start:
            k, cost, reason = None, None, "form_exit"
        elif (slot == "skill" and prev is not None and prev.get("ability_id") == ab
              and (prev.get("selector") or "") != sel and sel.endswith("End")):
            k, cost, reason = None, None, "continuation"
        elif slot == "skill":
            k, cost, reason = "E", ("e_cost" if own_clock else None), "skill"
        elif slot == "qte":
            k, cost, reason = ("QTE", None, "entry") if s.get("entry_only") else (None, None, "qte_in_visit")
        elif ab and str(ab).endswith("_PerfectEvade"):
            k, cost, reason = "counter", None, "perfect_evade"
        elif slot == "other":
            k, cost, reason = None, None, ("other_skill_unclassified" if ab and "_Skill" in str(ab) else "other")
        else:
            k, cost, reason = None, None, slot or "none"
        out[int(s.get("seq") or 0)] = StepClass(k, cost, reason, req)
        if s.get("sim"):
            prev = s
        if k == "Q":
            last_paid_q = int(s.get("seq") or 0)
    return out


def snapshot_class(cid: int, seq: int, data=None) -> StepClass | None:
    row = (data or _data()).STEP_CLASS.get((int(cid), int(seq)))
    return None if row is None else StepClass(*row)


# ── per-member state ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Gate:
    """Result of :meth:`ResourceState.gate` for one step."""
    action: str                          # run | energy_short | cd_skip | form_cut
    wait_us: int = 0                     # wall µs to insert before the step (0 = none)
    wait_kind: str = ""                  # cd_wait | res_wait
    cd_kind: str | None = None
    energy_before: float | None = None
    cost: float | None = None
    remaining_us: int = 0                # cooldown / resource time left when the step was reached
    note: str = ""                       # warn mode: energy_short | cd_not_ready
    reason: str = ""


@dataclass
class _Member:
    cid: int
    kind: str                            # ultimate | own_clock | own_meter
    cost: float | None                   # enforced pool cost
    cost_cell: Any
    eff: float                           # charge efficiency the hits use: own_eff + build_eff
    energy: float | None                 # pool energy (None = not modelled)
    own_eff: float = 0.0                 # the member's own passive (Chiichan +0.20)
    build_eff: float = 0.0               # whole-fight build bonus (arc / cartridge), from the engine run
    raw: float = 0.0                     # sum of charge_add of the placed hits (before the efficiency)
    event_gain: float = 0.0              # energy events (after:E / after:Q), not scaled by the efficiency
    gained_since_q: float = 0.0
    # own clock (Hotori)
    clock: float | None = None
    clock_t: int = 0
    drain_from: int | None = None
    clock_v0: float = 0.0
    interlude_pending: bool = False
    interlude_us: int = 0
    interludes: list = field(default_factory=list)   # µs credited per ultimate (one entry per credited visit)
    # own meter (Shinku, tracked only)
    meter: float | None = None
    meter_short: int = 0
    # cooldowns: kind -> list of policy-clock µs at which a spent use is back
    ready: dict = field(default_factory=dict)
    used: dict = field(default_factory=dict)
    basics_since_e: int = 0
    extra_e_used: bool = False
    # statistics
    q_planned: int = 0
    q_cast: int = 0
    q_skipped: list = field(default_factory=list)
    waited_us: int = 0
    cd_waits: int = 0
    res_waits: int = 0
    cd_skips: int = 0
    unchecked: set = field(default_factory=set)
    credited_gauge: float = 0.0
    credits: list = field(default_factory=list)
    partial_time_only: int = 0
    partial_seqs: list = field(default_factory=list)
    events: list = field(default_factory=list)
    missing: bool = False
    # D3 swap rule: (1-based loop, seq, kind, reason, seconds left, steps not run) per early swap; all-blocked waits
    early_swaps: list = field(default_factory=list)
    all_blocked: list = field(default_factory=list)  # (1-based loop, seq, wall seconds waited, member waited for)
    # (1-based loop, seq, kind, wall seconds waited, policy seconds left) cooldowns under SWAP_MIN_WAIT_S waited for
    short_waits: list = field(default_factory=list)
    charge_energy: float = 0.0           # 盈蓄 energy credited after the layout (display)
    last_reset: dict = field(default_factory=dict)   # reset rule code -> policy-clock µs it last fired (ICD)


class ResourceState:
    """Energy pools, own resources and cooldown timers of one layout (one per axis)."""

    def __init__(self, team_ids: Sequence[int], *, policy: ResourcePolicy, stops: list, solo: bool = False,
                 awakening: Mapping[int, Any] | None = None, charge_eff: Mapping[int, float] | None = None,
                 data=None, opening_energy: str = "full", extra_rules: Mapping[int, Sequence] | None = None,
                 extra_events: Mapping[int, Sequence] | None = None, hooks=None) -> None:
        from src.services import team_awakening

        self.data = data or _data()
        self.policy = policy
        self.stops = stops
        self.team = [int(c) for c in team_ids]
        self.solo = bool(solo) or len(self.team) < 2
        # A7: {cid: team_awakening.AwakeningSel} (an int = legacy level Effect1..level; None = nothing selected)
        self.awakening = {int(k): team_awakening.coerce(v, team_awakening.EMPTY) for k, v in (awakening or {}).items()}
        # awakening node rules: extra rule / event rows (team_resource_data shapes) and begin / after hooks
        self.extra_rules = {int(k): tuple(tuple(r) for r in v) for k, v in (extra_rules or {}).items() if v}
        self.extra_events = {int(k): tuple(tuple(e) for e in v) for k, v in (extra_events or {}).items() if v}
        self.hooks = hooks
        self.target: Mapping | None = None      # the run's target dict (set by the layout; None = DEFAULT_TARGET)
        self.members: dict[int, _Member] = {}
        for cid in self.team:
            rec = record(cid, self.data)
            en = rec.get("energy") or {}
            kind = en.get("kind") or "ultimate"
            cc = cost_cell(cid, policy, self.data) if kind == "ultimate" else None
            own = en.get("own_eff")
            own_eff = float(own[0]) if own and own[0] is not None else 0.0
            build_eff = float((charge_eff or {}).get(cid, 0.0))
            cost = None if cc is None else float(cc[0])
            start = None
            if cost is not None:
                start = cost if opening_energy == "full" else 0.0
            m = _Member(cid, kind, cost, cc or en.get("cost"), own_eff + build_eff, start, own_eff=own_eff,
                        build_eff=build_eff)
            if kind == "own_clock":
                clock = en.get("clock") or {}
                m.clock = float((clock.get("start") or (120.0,))[0] or 0.0) if opening_energy == "full" else 0.0
            if kind == "own_meter":
                meter = en.get("meter") or {}
                m.meter = float((meter.get("cap") or (60.0,))[0]) if opening_energy == "full" else 0.0
            self.members[cid] = m

    # ── helpers ──
    def rec(self, cid: int) -> dict:
        return record(cid, self.data)

    def pc(self, t_us: int) -> int:
        """Policy-clock µs of a wall time (stops are only ever appended after the current time)."""
        return active_between(self.stops, 0, int(t_us)) if self.policy.clock == "active" else int(t_us)

    def wall_after(self, t_us: int, policy_us: int) -> int:
        if policy_us <= 0:
            return int(t_us)
        return advance_active(t_us, policy_us, self.stops) if self.policy.clock == "active" else int(t_us) + policy_us

    def awakening_of(self, cid: int) -> int:
        """The member's awakening level (0..6; resonances)."""
        return int(self.selection_of(cid).level)

    def selection_of(self, cid: int):
        """team_awakening.AwakeningSel of the member (EMPTY when unknown)."""
        from src.services import team_awakening

        return self.awakening.get(int(cid), team_awakening.EMPTY)

    def unlocked(self, cid: int, node) -> bool:
        """A rule's ``awakening`` field against the member's node set: None = always, int n / "Effect<n>" = that
        effect selected, "resonance_3/6" = level >= 3/6 (A7/A8)."""
        if node is None:
            return True
        from src.services import team_awakening

        return team_awakening.unlocked(self.selection_of(cid), node)

    def rules_of(self, cid: int) -> tuple:
        """team_resource_data rules of the member plus the awakening node rules' rows (gate with ``unlocked``)."""
        rows = tuple(self.rec(cid).get("rules") or ())
        extra = self.extra_rules.get(int(cid))
        return rows + extra if extra else rows

    def events_of(self, cid: int) -> tuple:
        """Energy events of the member plus the awakening node rules' rows."""
        rows = tuple((self.rec(cid).get("energy") or {}).get("events") or ())
        extra = self.extra_events.get(int(cid))
        return rows + extra if extra else rows

    def not_ready_mode(self) -> str:
        """``swap`` (a team: the member swaps out at once) or ``wait`` (alone - nobody to swap to -, the ``wait``
        policy, or a cooldown check that never waits)."""
        policy = self.policy
        if policy.legacy or policy.cooldown != "wait" or self.solo or policy.not_ready == "wait":
            return "wait"
        return "swap"

    def classify(self, cid: int, step: Mapping, steps: Sequence[Mapping] | None = None) -> StepClass:
        seq = int(step.get("seq") or 0)
        if seq == 0 or step.get("slot") == "entry":
            return NO_CLASS
        snap = snapshot_class(cid, seq, self.data)
        if snap is not None:
            return snap
        if steps is not None:           # no snapshot (a character newer than the data module): the same rules
            return classify_rotation(cid, steps, self.data).get(seq, NO_CLASS)
        return NO_CLASS

    def has_record(self, cid: int) -> bool:
        """The data module knows the member (False = resource data missing: flagged, old refill rule)."""
        return bool(self.rec(cid))

    # ── energy ──
    def energy(self, cid: int) -> float | None:
        m = self.members.get(int(cid))
        if m is None:
            return None
        if m.kind == "own_clock":
            return None
        return m.energy

    def gain_hit(self, cid: int, dmg: Mapping | None) -> float:
        """One placed hit of the member: ``charge_add x (1 + charge efficiency)``."""
        m = self.members.get(int(cid))
        if m is None or not dmg:
            return 0.0
        raw = max(0.0, float(dmg.get("charge_add") or 0.0))
        if raw <= 0:
            return 0.0
        amount = raw * (1.0 + m.eff)
        m.raw += raw
        m.gained_since_q += amount
        if m.energy is not None and m.cost is not None:
            m.energy = min(m.cost, m.energy + amount)
        return amount

    def hit_credit(self, cid: int, action) -> tuple | None:
        """HIT_CREDIT cell of an action that lays out no hit in the simulator (None = none, legacy level, or a
        credit whose hit count is unknown)."""
        if self.policy.legacy or not action:
            return None
        c = (getattr(self.data, "HIT_CREDIT", None) or {}).get((int(cid), str(action[0]), str(action[1] or "")))
        return None if c is None or c[0] is None else c

    def gain_raw(self, cid: int, raw: float) -> float:
        """Credited charge_add of hits the layout does not place (``charge_add x (1 + efficiency)``)."""
        m = self.members.get(int(cid))
        raw = max(0.0, float(raw or 0.0))
        if m is None or raw <= 0:
            return 0.0
        amount = raw * (1.0 + m.eff)
        m.raw += raw
        m.gained_since_q += amount
        if m.energy is not None and m.cost is not None:
            m.energy = min(m.cost, m.energy + amount)
        return amount

    def gained(self, cid: int) -> float:
        """Ultimate energy gained so far (hits x (1 + efficiency) + events); also for members whose cost is unknown."""
        m = self.members.get(int(cid))
        return 0.0 if m is None else float(m.raw * (1.0 + m.eff) + m.event_gain)

    def raw_gain(self, cid: int) -> float:
        """Sum of charge_add of the member's placed hits (before the charge efficiency)."""
        m = self.members.get(int(cid))
        return 0.0 if m is None else float(m.raw)

    def event_total(self, cid: int) -> float:
        m = self.members.get(int(cid))
        return 0.0 if m is None else float(m.event_gain)

    def eff_of(self, cid: int) -> float:
        m = self.members.get(int(cid))
        return 0.0 if m is None else float(m.eff)

    def scaled(self, cid: int, raw: float, events: float = 0.0) -> float:
        """Energy of ``raw`` charge_add at the member's current efficiency, plus unscaled events."""
        return float(raw) * (1.0 + self.eff_of(cid)) + float(events)

    def set_build_eff(self, eff: Mapping[int, float] | None) -> bool:
        """The whole-fight charge efficiency of the build (arc / cartridge buffs, read from the engine run).

        Display numbers (energy gained) follow at once.  Returns True when a member whose ultimate is gated by a pool
        got another efficiency than the layout used - the caller lays the run out again with the value known."""
        regate = False
        for cid, m in self.members.items():
            new = float((eff or {}).get(cid, 0.0) or 0.0)
            if abs(new - m.build_eff) <= 1e-9:
                continue
            if m.kind == "ultimate" and m.cost is not None and self.policy.energy != "off":
                regate = True
            m.build_eff = new
            m.eff = m.own_eff + new
        return regate

    def add_charge(self, cid: int, amount: float) -> None:
        """盈蓄 energy credited after the layout (display: the pool checks of the layout did not see it)."""
        m = self.members.get(int(cid))
        if m is None:
            return
        m.event_gain += float(amount)
        m.charge_energy += float(amount)

    def add_energy(self, cid: int, amount: float, code: str) -> None:
        m = self.members[int(cid)]
        m.event_gain += amount
        m.gained_since_q += amount
        if m.energy is not None and m.cost is not None:
            m.energy = min(m.cost, m.energy + amount)
        m.events.append((code, round(float(amount), 3)))

    # ── own clock (Hotori) ──
    def _clock_params(self, cid: int) -> dict:
        clock = (self.rec(cid).get("energy") or {}).get("clock") or {}
        return {k: float(v[0]) for k, v in clock.items() if isinstance(v, tuple) and v and v[0] is not None}

    def clock_at(self, cid: int, t_us: int) -> float | None:
        m = self.members.get(int(cid))
        if m is None or m.clock is None:
            return None
        p = self._clock_params(cid)
        if m.drain_from is not None:
            return max(0.0, m.clock_v0 - p.get("drain_per_s", 10.0) * max(0, int(t_us) - m.drain_from) / 1e6)
        elapsed = self.pc(t_us) - self.pc(m.clock_t) if t_us > m.clock_t else 0
        return min(p.get("cap", 120.0), m.clock + p.get("regen_per_s", 6.0) * elapsed / 1e6)

    def _set_clock(self, cid: int, t_us: int, value: float) -> None:
        m = self.members[int(cid)]
        m.clock, m.clock_t = float(value), int(t_us)

    def end_drain(self, cid: int, t_us: int) -> None:
        m = self.members.get(int(cid))
        if m is None or m.drain_from is None:
            return
        value = self.clock_at(cid, t_us)
        m.drain_from = None
        self._set_clock(cid, t_us, value)

    def note_interlude(self, cid: int) -> None:
        m = self.members.get(int(cid))
        if m is not None and m.clock is not None:
            m.interlude_pending = True

    def _interlude_mode(self) -> str:
        mode = self.policy.own_clock_interlude
        if mode == "auto":
            return "wait" if self.solo else "credit"
        return mode

    # ── cooldowns ──
    def cd_seconds(self, cid: int, kind: str) -> float | None:
        c = cd_cell(cid, kind, self.policy, self.data)
        if c is None:
            return None
        value = float(c[0])
        for code, rkind, amount, level, _conf, _src in self.rules_of(cid):
            if code == "e_cd_add" and rkind == kind and self.unlocked(cid, level):
                value = max(0.0, value + float(amount))
        return value

    def cd_info(self, cid: int, kind: str | None) -> tuple:
        """(seconds used | None, confidence, source tag) of a step's cooldown kind at the policy's level: the
        enforced cell, else the best known cell (shown, not enforced: seconds None)."""
        if not kind:
            return (None, "", "")
        seconds = self.cd_seconds(cid, kind)
        cell = cd_cell(cid, kind, self.policy, self.data)
        if cell is None:
            cell = best_cd_cell(cid, kind, self.data)
        if cell is None:
            return (seconds, "unknown", "")
        return (seconds, str(cell[2]), source_tag(cell))

    def cd_conflict(self, cid: int, kind: str) -> float | None:
        """Recorded battle-time interval (time stops excluded) shorter than the cooldown in use, or None.

        An interval that contains the member's own Q press does not count when a ``q_resets_e`` rule of the kind is
        unlocked at the build's awakening (Linko A3 refreshes her E on the Q): the bound without such intervals is used
        then (review F4)."""
        conflict = (self.rec(cid).get("cd_conflict") or {}).get(kind)
        used = self.cd_seconds(cid, kind)
        if not conflict or used is None:
            return None
        bound = float(conflict["active_le_s"])
        resets = any(code == "q_resets_e" and rkind == kind and self.unlocked(cid, level)
                     for code, rkind, _amount, level, _conf, _src in self.rules_of(cid))
        if resets and "active_le_s_no_own_q" in conflict:
            if not conflict.get("n_no_own_q"):
                return None
            bound = float(conflict["active_le_s_no_own_q"])
        return bound if used > bound + 1e-9 else None

    def charges(self, cid: int, kind: str) -> int:
        ch = self.rec(cid).get("e_charges")
        if kind == CHARGES_KIND and ch and ch[0] is not None and ch[2] in enforced_confidences(self.policy, self.data):
            return max(1, int(ch[0]))
        return 1

    def _extra_e_ready(self, cid: int, kind: str) -> bool:
        for code, rkind, amount, level, _conf, _src in self.rules_of(cid):
            if code == "extra_e_after_basics" and rkind == kind and self.unlocked(cid, level):
                m = self.members[int(cid)]
                return not m.extra_e_used and m.basics_since_e >= int(amount or 0)
        return False

    def cd_remaining_us(self, cid: int, kind: str | None, t_us: int, *, peek: bool = False) -> int:
        """Policy-clock µs until the kind is usable (0 = ready, unknown, off or never used).  ``peek``: no
        bookkeeping (the swap decision looks at members that are not on the field)."""
        if not kind or self.policy.cooldown == "off" or self.policy.legacy:
            return 0
        m = self.members.get(int(cid))
        if m is None:
            return 0
        seconds = self.cd_seconds(cid, kind)
        if seconds is None:
            if m.used.get(kind) and not peek:
                m.unchecked.add(kind)          # used again with no enforced value: listed, not checked
            return 0
        if seconds <= 0:
            return 0
        now = self.pc(t_us)
        pending = [r for r in m.ready.get(kind, ()) if r > now]
        if len(pending) < self.charges(cid, kind):
            return 0
        return max(0, min(pending) - now)

    def start_cd(self, cid: int, kind: str | None, t_us: int, *, free: bool = False) -> None:
        if not kind:
            return
        m = self.members.get(int(cid))
        if m is None:
            return
        m.used[kind] = m.used.get(kind, 0) + 1
        seconds = self.cd_seconds(cid, kind)
        if seconds is None or seconds <= 0 or free:
            return
        now = self.pc(t_us)
        pending = sorted(r for r in m.ready.get(kind, ()) if r > now)
        start = max([now] + pending) if self.charges(cid, kind) > 1 else now
        pending.append(start + int(round(seconds * 1e6)))
        m.ready[kind] = pending
        if kind == "E":
            m.basics_since_e, m.extra_e_used = 0, False

    def clear_cd(self, cid: int, kind: str) -> None:
        m = self.members.get(int(cid))
        if m is not None:
            m.ready[kind] = []

    def note_basic(self, cid: int) -> None:
        m = self.members.get(int(cid))
        if m is not None:
            m.basics_since_e += 1

    # ── the check of one step (design §4.7) ──
    def gate(self, cid: int, cls: StepClass, t_us: int, *, offset_s: float = 0.0) -> Gate:
        cid = int(cid)
        m = self.members.get(cid)
        if m is None or self.policy.legacy:
            return Gate("run", cd_kind=cls.cd_kind)
        policy = self.policy
        before = m.energy
        res_wait_pc = 0
        note = ""
        # energy first: a short pool skips the ultimate (no wait helps), an own clock is waitable
        if cls.cost_ref == "q_cost":
            m.q_planned += 1
            if m.kind == "ultimate" and m.cost is not None and policy.energy != "off":
                if (m.energy or 0.0) + ENERGY_EPS < m.cost:
                    if policy.energy == "skip":
                        return Gate("energy_short", cd_kind=cls.cd_kind, energy_before=m.energy, cost=m.cost,
                                    reason="energy_short")
                    note = "energy_short"
        if m.kind == "own_clock" and cls.cost_ref in ("q_cost", "e_cost") and policy.energy != "off":
            p = self._clock_params(cid)
            need = p.get("q_needs", 120.0) if cls.cost_ref == "q_cost" else p.get("e_cost", 60.0)
            value = self.clock_at(cid, t_us)
            before = value
            if value + ENERGY_EPS < need:
                deficit_s = (need - value) / max(1e-9, p.get("regen_per_s", 6.0))
                mode = self._interlude_mode()
                if cls.cost_ref == "q_cost" and m.interlude_pending and mode == "credit":
                    m.interlude_us += int(round(deficit_s * 1e6))
                    m.interludes.append(int(round(deficit_s * 1e6)))
                    self._set_clock(cid, t_us, need)
                    before = need
                elif cls.cost_ref == "q_cost" and m.interlude_pending and mode == "strict":
                    m.interlude_pending = False
                    return Gate("energy_short", cd_kind=cls.cd_kind, energy_before=value, cost=need,
                                reason="own_clock_short")
                else:
                    res_wait_pc = int(round(deficit_s * 1e6))
            if cls.cost_ref == "q_cost":
                m.interlude_pending = False
        # one combined wait: cooldown and own resource
        cd_pc = self.cd_remaining_us(cid, cls.cd_kind, t_us)
        free_extra = False
        if cd_pc > TOLERANCE_US and cls.cd_kind and self._extra_e_ready(cid, cls.cd_kind):
            cd_pc, free_extra = 0, True
        need_pc = max(cd_pc, res_wait_pc)
        if need_pc <= TOLERANCE_US:
            return Gate("run", cd_kind=cls.cd_kind, energy_before=before, cost=m.cost, note=note,
                        reason="extra_e" if free_extra else "")
        if policy.cooldown == "warn" and res_wait_pc <= TOLERANCE_US:
            return Gate("run", cd_kind=cls.cd_kind, energy_before=before, cost=m.cost, remaining_us=need_pc,
                        note="cd_not_ready")
        if policy.cooldown == "off" and res_wait_pc <= TOLERANCE_US:
            return Gate("run", cd_kind=cls.cd_kind, energy_before=before, cost=m.cost)
        limit = policy.max_wait_guard_s if policy.cd_wait_max_s is None else min(policy.cd_wait_max_s,
                                                                                 policy.max_wait_guard_s)
        if need_pc > int(round(limit * 1e6)) + TOLERANCE_US:
            return Gate("cd_skip", cd_kind=cls.cd_kind, energy_before=before, cost=m.cost, remaining_us=need_pc,
                        reason="too_long" if policy.cd_wait_max_s is None else "over_max")
        end = self.wall_after(t_us, need_pc)
        kind = "cd_wait" if cd_pc >= res_wait_pc else "res_wait"
        return Gate("run", wait_us=end - int(t_us), wait_kind=kind, cd_kind=cls.cd_kind, energy_before=before,
                    cost=m.cost, remaining_us=need_pc, note=note)

    def waited(self, cid: int, gate: Gate) -> None:
        m = self.members[int(cid)]
        m.waited_us += int(gate.wait_us)
        if gate.wait_kind == "res_wait":
            m.res_waits += 1
        elif gate.wait_kind != "blocked_wait":      # D3: waiting for another member is not its own cooldown wait
            m.cd_waits += 1

    def skipped(self, cid: int, gate: Gate, loop_index: int) -> None:
        m = self.members[int(cid)]
        if gate.action == "energy_short":
            m.q_skipped.append(int(loop_index))
        elif gate.action == "cd_skip":
            m.cd_skips += 1

    # ── D3: swap out when a step is not ready (teams) ──
    def peek_remaining(self, cid: int, cls: StepClass, t_us: int, *, interlude: bool = False) -> int | None:
        """Policy-clock µs until ``cls`` could run at ``t_us`` without any bookkeeping (0 = ready; None = never by
        waiting: an ultimate whose known cost the pool cannot pay).  Same order as :meth:`gate`; ``interlude`` = the
        member's visit passes its "swap out and wait for the clock" step before this one."""
        m = self.members.get(int(cid))
        policy = self.policy
        if m is None or policy.legacy:          # (cooldown "off": only the own clock - the walker's clock-only state)
            return 0
        if (cls.cost_ref == "q_cost" and m.kind == "ultimate" and m.cost is not None and policy.energy == "skip"
                and (m.energy or 0.0) + ENERGY_EPS < m.cost):
            return None
        res_pc = 0
        if m.kind == "own_clock" and cls.cost_ref in ("q_cost", "e_cost") and policy.energy != "off":
            p = self._clock_params(cid)
            need = p.get("q_needs", 120.0) if cls.cost_ref == "q_cost" else p.get("e_cost", 60.0)
            value = self.clock_at(cid, t_us)
            if value + ENERGY_EPS < need:
                mode = self._interlude_mode()
                if cls.cost_ref == "q_cost" and interlude and mode == "credit":
                    res_pc = 0
                elif cls.cost_ref == "q_cost" and interlude and mode == "strict":
                    return None
                else:
                    res_pc = int(round((need - value) / max(1e-9, p.get("regen_per_s", 6.0)) * 1e6))
        cd_pc = self.cd_remaining_us(cid, cls.cd_kind, t_us, peek=True)
        if cd_pc > TOLERANCE_US and cls.cd_kind and self._extra_e_ready(cid, cls.cd_kind):
            cd_pc = 0
        need_pc = max(cd_pc, res_pc)
        return 0 if need_pc <= TOLERANCE_US else need_pc

    def first_block_us(self, cid: int, steps: Sequence[Mapping], t_us: int) -> int | None:
        """Policy-clock µs until the first checked step of the member's next visit could run (0 = at once, None =
        never by waiting).  Judged at ``t_us``; the entry (support skill / entry action, no cooldown of its own) and
        the steps before that one are not counted."""
        interlude = False
        for s in steps:
            if s.get("entry_only"):
                continue
            cls = self.classify(cid, s, steps)
            if cls.reason == "own_clock_wait":
                interlude = True
                continue
            if not s.get("sim") or not (cls.cd_kind or cls.cost_ref):
                continue
            return self.peek_remaining(cid, cls, t_us, interlude=interlude)
        return 0

    def guard_us(self) -> int:
        """The longest wait the policy inserts (µs of the policy clock)."""
        p = self.policy
        limit = p.max_wait_guard_s if p.cd_wait_max_s is None else min(p.cd_wait_max_s, p.max_wait_guard_s)
        return int(round(limit * 1e6))

    def early_swap(self, cid: int, loop_index: int, seq: int, kind: str | None, reason: str, remaining_us,
                   dropped: int) -> None:
        m = self.members[int(cid)]
        m.early_swaps.append((int(loop_index) + 1, int(seq), str(kind or ""), str(reason),
                              None if remaining_us is None else round(int(remaining_us) / 1e6, 3), int(dropped)))

    def all_blocked_wait(self, cid: int, loop_index: int, seq: int, wait_us: int, other: int) -> None:
        m = self.members[int(cid)]
        m.all_blocked.append((int(loop_index) + 1, int(seq), round(int(wait_us) / 1e6, 3), int(other)))

    def short_left(self, remaining_us) -> bool:
        """``remaining_us`` (policy clock) is under the swap rule's threshold ``swap_min_wait_s`` (2026-10-18)."""
        return remaining_us is not None and int(remaining_us) < int(round(float(self.policy.swap_min_wait_s) * 1e6))

    def short_wait(self, gate: Gate) -> bool:
        """Swap rule (a team): the step's cooldown has less than ``swap_min_wait_s`` of battle time left - it is waited
        for and the skill cast instead of swapping out (user decision 2026-10-18).  Cooldown waits only: an
        energy-short ultimate, the own clock (``res_wait``) and a skip beyond the guard are not affected."""
        return (self.not_ready_mode() == "swap" and gate.action == "run" and gate.wait_kind == "cd_wait"
                and int(gate.wait_us) > 0 and self.short_left(gate.remaining_us))

    def short_wait_done(self, cid: int, loop_index: int, seq: int, kind: str | None, wait_us: int,
                        remaining_us: int) -> None:
        m = self.members[int(cid)]
        m.short_waits.append((int(loop_index) + 1, int(seq), str(kind or ""), round(int(wait_us) / 1e6, 3),
                              round(int(remaining_us) / 1e6, 3)))

    def dropped_q(self, cid: int) -> None:
        """An ultimate of the visit that an early swap left unreached (D3): planned, not cast (review F1)."""
        m = self.members.get(int(cid))
        if m is not None and not self.policy.legacy:
            m.q_planned += 1

    def begin(self, cid: int, cls: StepClass, t_us: int, gate: Gate, step: Mapping | None = None) -> float | None:
        """The step runs from ``t_us``: spend energy / clock, start its cooldown, apply start events.  Returns the
        energy (pool) or clock value before the step."""
        cid = int(cid)
        m = self.members.get(cid)
        if m is None or self.policy.legacy:
            return None
        # the value when the step starts (after an inserted wait the gate's value is out of date)
        before = self.clock_at(cid, t_us) if m.kind == "own_clock" else (m.energy if m.energy is not None
                                                                          else gate.energy_before)
        offsets = self.rec(cid).get("cd_offset_s") or {}
        kind = cls.cd_kind
        if cls.cost_ref == "q_cost":
            m.q_cast += 1
            if m.kind == "ultimate" and m.cost is not None and m.energy is not None:
                m.energy = max(0.0, m.energy - m.cost)
            m.gained_since_q = 0.0
            if m.kind == "own_clock":
                value = self.clock_at(cid, t_us)
                m.clock_v0, m.drain_from = value, int(t_us)
                self._set_clock(cid, t_us, value)
            if m.kind == "own_meter" and m.meter is not None:
                cap = float(((self.rec(cid).get("energy") or {}).get("meter") or {}).get("cap", (60.0,))[0])
                if m.meter + ENERGY_EPS < cap:
                    m.meter_short += 1
                m.meter = 0.0
            for code, rkind, _amount, level, _conf, _src in self.rules_of(cid):
                if code == "q_resets_e" and self.unlocked(cid, level):
                    self.clear_cd(cid, rkind)
                    m.events.append(("q_resets_e", 0.0))
        elif cls.cost_ref == "e_cost" and m.kind == "own_clock":
            self.end_drain(cid, t_us)
            p = self._clock_params(cid)
            value = self.clock_at(cid, t_us)
            self._set_clock(cid, t_us, max(0.0, value - p.get("e_cost", 60.0)))
        if kind:
            free = gate.reason == "extra_e"
            if free:
                m.extra_e_used = True
            start = int(t_us) + int(round(float(offsets.get(kind, 0.0)) * 1e6))
            self.start_cd(cid, kind, start, free=free)
        if kind == "counter":
            rows = self.rules_of(cid)
            now = self.pc(t_us)
            for code, rkind, value, level, _conf, _src in rows:
                if code == "counter_resets_e" and self.unlocked(cid, level):
                    icd = reset_icd_s(rows, code, value, lambda node: self.unlocked(cid, node))
                    last = m.last_reset.get(code)
                    if icd and last is not None and now - last < int(round(icd * 1e6)):
                        continue                # inside the reset's internal cooldown (Mint ① 3 s)
                    m.last_reset[code] = now
                    self.clear_cd(cid, rkind)
        if self.hooks is not None:      # awakening node rules (resource_begin)
            self.hooks.begin(self, cid, cls, step, t_us, gate)
        return before

    def after(self, cid: int, cls: StepClass, step: Mapping | None, t_end_us: int, *, presses: int = 1) -> list:
        """Events after the step ran (after:E / after:Q energy, Shinku meter gains); returns the new events."""
        cid = int(cid)
        m = self.members.get(cid)
        if m is None or self.policy.legacy:
            return []
        new = []
        rec = self.rec(cid)
        trigger = {"E": "after:E", "Q": "after:Q"}.get(cls.cd_kind or "")
        if cls.cost_ref == "q_cost":
            trigger = "after:Q"
        for when, amount, level, _conf, _src in self.events_of(cid):
            if when == trigger and self.unlocked(cid, level):
                self.add_energy(cid, float(amount), when)
                new.append((when, float(amount)))
        if cls.cd_kind == "E" and step is not None:     # e_resets_q (Sagiri ⑤): the E clears the Q cooldown
            selector = str(step.get("selector") or "")
            for code, rkind, value, level, _conf, _src in self.rules_of(cid):
                if code == "e_resets_q" and self.unlocked(cid, level) and reset_matches(value, selector, self.target):
                    self.clear_cd(cid, rkind)
                    m.events.append(("e_resets_q", 0.0))
                    new.append(("e_resets_q", 0.0))
        if self.hooks is not None:      # awakening node rules (resource_after): returns the events they added
            new.extend(self.hooks.after(self, cid, cls, step, t_end_us))
        if m.kind == "own_meter" and m.meter is not None and step is not None:
            meter = (rec.get("energy") or {}).get("meter") or {}
            slot = str(step.get("slot") or "")
            gain = 0.0
            if slot == "basic" and not step.get("form_role"):
                gain = float((meter.get("gain_melee") or (0.0,))[0] or 0.0) * max(1, presses)
            elif slot == "skill" and not step.get("form_role"):
                gain = float((meter.get("gain_skill") or (0.0,))[0] or 0.0)
            if gain:
                cap = float((meter.get("cap") or (60.0,))[0])
                m.meter = min(cap, m.meter + gain)
        return new

    def visit_end(self, cid: int, t_us: int) -> None:
        self.end_drain(cid, t_us)

    # ── gauge ──
    def time_only_credit(self, cid: int, seq: int) -> float | None:
        if not self.policy.time_only_credit or self.policy.legacy:
            return None
        c = self.data.TIME_ONLY_CREDIT.get((int(cid), int(seq)))
        return None if c is None or c[0] is None else float(c[0])

    def partial_time_only(self, cid: int, seq: int) -> bool:
        """A time-only step that builds gauge in the game but has no credited value (LIMIT_GAUGE_PARTIAL)."""
        if self.policy.legacy or (int(cid), int(seq)) in TIME_ONLY_NO_GAUGE:
            return False
        return (int(cid), int(seq)) not in self.data.TIME_ONLY_CREDIT

    def note_credit(self, cid: int, seq: int, amount: float) -> None:
        m = self.members[int(cid)]
        m.credited_gauge += float(amount)
        if seq not in m.credits:
            m.credits.append(int(seq))

    def note_partial(self, cid: int, seq: int | None = None) -> None:
        m = self.members[int(cid)]
        key = -1 if seq is None else int(seq)
        if key not in m.partial_seqs:           # distinct approved steps, not every visit's repeat
            m.partial_seqs.append(key)
            m.partial_time_only += 1

    def mark_missing(self, cid: int) -> None:
        m = self.members.get(int(cid))
        if m is not None:
            m.missing = True

    def gauge_fallback(self, cid: int) -> bool:
        if self.policy.gauge_refill == "all":
            return True
        if self.policy.gauge_refill == "none":
            return False
        m = self.members.get(int(cid))
        if not self.rec(cid):
            return True
        return bool((self.rec(cid).get("gauge") or {}).get("fallback")) or bool(m is not None and m.missing)

    def fallback_reason(self, cid: int) -> str:
        if not self.rec(cid):
            return "no_record"
        if (self.rec(cid).get("gauge") or {}).get("fallback"):
            return "data"
        m = self.members.get(int(cid))
        return "missing" if m is not None and m.missing else ""

    # ── traces ──
    def snapshot(self, cid: int, t_us: int) -> float | None:
        m = self.members.get(int(cid))
        if m is None:
            return None
        if m.kind == "own_clock":
            return self.clock_at(cid, t_us)
        if m.kind == "own_meter":
            return m.meter
        return m.energy if m.energy is not None else None

    def member_summary(self, cid: int) -> dict:
        m = self.members[int(cid)]
        rec = self.rec(cid)
        kinds = {}
        for kind in ("E", "Q", "QTE", "counter", "E_alt"):
            if kind not in (rec.get("cd") or {}):
                continue
            enforced = cd_cell(cid, kind, self.policy, self.data)
            best = best_cd_cell(cid, kind, self.data)
            kinds[kind] = (enforced, best, self.cd_seconds(cid, kind))
        return {"character_id": int(cid), "energy_kind": m.kind, "cost": m.cost, "cost_cell": m.cost_cell,
                "eff": m.eff, "gained": self.gained(cid), "q_planned": m.q_planned, "q_cast": m.q_cast,
                "q_skipped": tuple(m.q_skipped), "waited_s": m.waited_us / 1e6, "cd_waits": m.cd_waits,
                "res_waits": m.res_waits, "cd_skips": m.cd_skips, "interlude_s": m.interlude_us / 1e6,
                "interludes_s": tuple(round(us / 1e6, 3) for us in m.interludes),
                "unchecked": tuple(sorted(m.unchecked)), "credited_gauge": m.credited_gauge,
                "credits": tuple(m.credits), "partial_time_only": m.partial_time_only,
                "events": tuple(m.events), "meter_short": m.meter_short, "cd": kinds,
                "charge_energy": m.charge_energy, "early_swaps": tuple(m.early_swaps),
                "all_blocked": tuple(m.all_blocked), "short_waits": tuple(m.short_waits),
                "fallback": self.gauge_fallback(cid), "fallback_reason": self.fallback_reason(cid)}
