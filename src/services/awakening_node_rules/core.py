# 队伍模拟：觉醒（돌파）效果规则登记处——各角色组模块（g0…g3）在此登记钩子与节点说明，主流程按所选觉醒调用（纯逻辑，不导入 Qt）。
"""Awakening-node rule registry (Global; Korean UI "돌파").  See the package docstring for the group-module recipe.

Vocabulary: *node* = an ordinary awakening effect ``Effect1..Effect6`` (selected freely) or a resonance
``resonance_3`` / ``resonance_6`` (on at awakening level 3 / 6, whatever is selected).  A *registration* binds a
callable (a *hook*) to one character and the nodes it models; the framework calls it only when that character is in
the team **and** at least one of the nodes is active for the member (``team_awakening.unlocked``).  ``nodes=()``
means "base kit": called whenever the character is in the team (a base-kit gap a node needs, priced at A0 too).

Hook kinds (call sites in ``team_simulation_service`` unless noted; ``ctx`` = :class:`HookCtx`):

=================  =====================================================================================
``prepare``        ``f(ctx) -> data``.  Once per context (``_open_session.make``), static DB open read-only:
                   ``ctx.con`` (sqlite3), ``ctx.static`` (StaticGameDataDao).  The return value is ``ctx.data`` in
                   every later hook of the same rule set and character (read DB curves here, never hard-code).
``buff_rules``     ``f(ctx, static, build, rules) -> rules``.  Right after ``BattleBuffInferenceService.load_rules``.
``gate``           ``f(ctx, ev: GateEvent) -> effect_hit_offsets``.  ``_AxisWriter.place`` before the hit loop,
                   for the rule's own character only (both modes): which bound damage GEs the action lays out.
``placed``         ``f(ctx, ev: PlacedAction) -> None``.  After every action ``_AxisWriter.place`` laid out (both
                   modes); ``members="all"`` also passes the other members' actions.  ``ev.writer`` gives the gauge.
``free_support``   ``f(ctx, ev: SwapEvent) -> bool``.  At a swap into the rule's character: True = the support entry
                   needs no Cycle gauge and does not consume it (approved ``_layout_axis`` and the custom walker).
``dot_rows``       ``f(ctx, run: RunInfo, dot_rows: list) -> list``.  ``_run_axis`` after ``_dot_tick_rows``.
``rows``           ``f(ctx, run) -> list[dict]``.  Extra hit rows (``run.row(...)``), credited like DoT ticks to
                   the owner's latest visit; ``dot_ticks=True`` also feeds them to Zankou's Scorch as DoT ticks.
``intervals``      ``f(ctx, run, analysis) -> analysis``.  ``_run_engine`` after the arc corrections, before the
                   custom ``buff_edit`` (supplement / replace / fill buff intervals; ``SOURCE_KIND``, 中 confidence).
``evidence``       ``f(ctx, run, evidence) -> evidence``.  ``_run_engine`` after ``patch_ordinary_scorch_evidence``.
``post``           ``f(ctx, run, pairs) -> iterable[PostIncrement]``.  ``_collect`` after replay
                   (``pairs`` = [(analysis hit, replay)]); increments add to the member's direct damage.
``resource_begin`` ``f(ctx, ev: ResourceEvent) -> None``.  ``team_resources.ResourceState.begin`` (reviewed mode).
``resource_after`` ``f(ctx, ev) -> list[(code, amount)] | None``.  ``ResourceState.after`` (reviewed mode).
=================  =====================================================================================

Data declarations (no callable): ``RuleSet.resource_rule`` / ``resource_event`` add rows in the
``team_resource_data`` tuple shapes (``(code, kind, value, node, confidence, source)`` /
``(when, amount, node, confidence, source)``); ``node`` = ``"Effect5"`` / ``5`` / ``"resonance_6"`` / None.  They are
merged into ``ResourceState`` and the custom walker's cooldown rules and gated there by the selection.  A value
``"curve:<curve id>"`` is read from the static DB when the context is prepared (``CURVE_PREFIX``; None when missing).
Rule codes the framework itself runs (team_resources / the custom walker): ``q_resets_e``, ``counter_resets_e``
(value = internal cooldown in seconds, or a ``reset_icd`` row ``("reset_icd", <reset code>, seconds, None, ...)``),
``e_resets_q`` (after an E: value None = any E, or ``{"selectors": (...), "not_on_boss": bool}``).
``RuleSet.node`` declares the node's display / efficiency metadata (:class:`NodeInfo`); ``RuleSet.text`` the
explanation text of a note code the group emits (``ctx.note``; codes start with ``awakening_<group>_``).

Switch: ``NTE_TEAM_AWAKENING_RULES`` = ``off`` (no hook runs: the selection model alone) | ``on`` (default) | a comma
list of groups (``g0,g2``).  ``ENABLED_GROUPS`` (None = all) can also be set by tests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from src.services import team_awakening as ta

ENV = "NTE_TEAM_AWAKENING_RULES"
SOURCE_KIND = "global_awakening_supplement"     # buff intervals built by node rules (explanation lists them)
NAME_PREFIX = "Global awakening: "
SUPPLEMENT_CONFIDENCE = "中"                    # the projection accepts 中 / 高 values only
CURVE_PREFIX = "curve:"         # resource row values read from the static DB (combat_curve_point)
INACTIVE_KEY = "_rules_inactive"  # prepare data {INACTIVE_KEY: True}: the character's rules do nothing in this context

HOOK_KINDS = ("prepare", "buff_rules", "gate", "placed", "free_support", "dot_rows", "rows", "intervals",
              "evidence", "post", "resource_begin", "resource_after")
LAYOUT_KINDS = ("gate", "placed", "free_support")
RUN_KINDS = ("dot_rows", "rows", "intervals", "evidence", "post")
RESOURCE_KINDS = ("resource_begin", "resource_after")
MODES = ("approved", "custom")
# efficiency-table cell classes (design_final §3.3; 'bound' = upper bound only, shown like 'review')
CATEGORIES = ("damage", "time", "resource", "team", "rotation", "unmodelled", "review", "none", "bound", "cap")
BUCKETS = ("now", "measure", "not_computable")
CONFIDENCES = ("high", "medium", "low")
LANGS = ("ko", "zh", "en", "ja")


def parse_switch(value) -> set | None:
    """``NTE_TEAM_AWAKENING_RULES`` -> enabled groups (None = all, empty = none)."""
    text = str(value or "").strip().casefold()
    if text in ("", "on", "all", "1", "true", "yes"):
        return None
    if text in ("off", "none", "0", "false", "no"):
        return set()
    return {t.strip() for t in text.replace(";", ",").split(",") if t.strip()}


ENABLED_GROUPS: set | None = parse_switch(os.environ.get(ENV))


def group_enabled(group: str) -> bool:
    return ENABLED_GROUPS is None or group in ENABLED_GROUPS


# ── declarations ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NodeInfo:
    """What the UI and the efficiency table show for one node (declared by the group that owns the character).

    ``category``: efficiency cell class (CATEGORIES).  ``bucket``: now | measure | not_computable (a node that is not
    'now' is marked, never shown as 0 %).  ``expected_value``: a condition the simulator cannot reproduce, priced as an
    expected value (UI mark '기대값').  ``assumption`` / ``reason``: {lang: sentence} ('ko' required when given; the
    UI shows the assumption of low-confidence and expected-value nodes in the node tooltip).  ``unmodelled_codes``:
    team_resource_data ``unmodelled`` codes bound to this node (shown only when the node is selected).
    ``resolves_codes``: limit / unmodelled codes this node's rules make obsolete (dropped while the node is selected
    and its group is enabled), e.g. ``lacrimosa_a6_support`` once the Lacrimosa ⑥ swap rule exists.
    ``rotation_assumed``: the approved rotation already assumes the node (a limit is shown when it is NOT selected)."""
    character_id: int
    node: str
    category: str
    bucket: str
    group: str = ""
    confidence: str = "high"
    expected_value: bool = False
    assumption: Mapping = field(default_factory=dict)
    reason: Mapping = field(default_factory=dict)
    unmodelled_codes: tuple = ()
    resolves_codes: tuple = ()
    rotation_assumed: bool = False
    pre_release: bool = False
    scope: str = ""                 # now: solo_team | team_only | resource_only

    def text(self, which: str, lang: str = "ko") -> str:
        """``assumption`` / ``reason`` sentence in ``lang`` (falls back to ko, then zh, then '')."""
        table = self.assumption if which == "assumption" else self.reason
        for code in (lang, "ko", "zh"):
            value = (table or {}).get(code)
            if value:
                return str(value)
        return ""


@dataclass(frozen=True)
class Registration:
    group: str
    kind: str
    character_id: int
    nodes: tuple
    func: Callable
    name: str
    order: int = 0
    members: str = "self"           # placed: "self" | "all" (actions of every member)
    modes: tuple = MODES            # layout kinds: the layout modes that call the hook
    dot_ticks: bool = False         # rows: the rows also count as DoT ticks (Zankou's Scorch)

    @property
    def key(self) -> tuple:
        return (self.group, self.character_id)


class RuleSet:
    """One group module's rules (characters it owns, hooks, data rows, node metadata, note texts).  Creating it
    registers it; a group module keeps exactly one (module attribute ``RULES``)."""

    def __init__(self, group: str, characters: Iterable[int], *, title: str = "") -> None:
        if not group or not str(group).isidentifier():
            raise ValueError(f"bad group name {group!r}")
        self.group = str(group)
        self.characters = tuple(int(c) for c in characters)
        self.title = title
        self.registrations: list[Registration] = []
        self.infos: dict[tuple[int, str], NodeInfo] = {}
        self.rules: dict[int, list[tuple]] = {}
        self.events: dict[int, list[tuple]] = {}
        self.texts: dict[str, Callable] = {}
        _register(self)

    # helpers -----------------------------------------------------------------
    def _own(self, character_id) -> int:
        cid = int(character_id)
        if cid not in self.characters:
            raise ValueError(f"group {self.group} does not own character {cid}")
        return cid

    @staticmethod
    def _nodes(nodes) -> tuple:
        if nodes is None:
            return ()
        if isinstance(nodes, (str, int)):
            nodes = (nodes,)
        out = []
        for n in nodes:
            canonical = ta.node_id(n)
            if canonical is None:
                raise ValueError(f"unknown node {n!r}")
            out.append(canonical)
        return tuple(dict.fromkeys(out))

    # declarations ------------------------------------------------------------
    def hook(self, kind: str, character_id: int, *, nodes=(), name: str | None = None, order: int = 0,
             members: str = "self", modes: Iterable[str] = MODES, dot_ticks: bool = False):
        """Decorator: register ``func`` as a ``kind`` hook of ``character_id`` for ``nodes`` (() = base kit)."""
        if kind not in HOOK_KINDS:
            raise ValueError(f"unknown hook kind {kind!r}")
        if members not in ("self", "all"):
            raise ValueError("members must be 'self' or 'all'")
        cid = self._own(character_id)
        node_ids = self._nodes(nodes)
        mode_ids = tuple(m for m in modes if m in MODES)

        def wrap(func: Callable) -> Callable:
            self.registrations.append(Registration(self.group, kind, cid, node_ids, func,
                                                   name or getattr(func, "__name__", kind), int(order), members,
                                                   mode_ids or MODES, bool(dot_ticks)))
            return func

        return wrap

    def resource_rule(self, character_id: int, rule: tuple) -> None:
        """A cooldown rule ``(code, kind, value, node, confidence, source)`` (team_resource_data shape)."""
        cid = self._own(character_id)
        if len(tuple(rule)) != 6:
            raise ValueError("resource rule = (code, kind, value, node, confidence, source)")
        self.rules.setdefault(cid, []).append(tuple(rule))

    def resource_event(self, character_id: int, event: tuple) -> None:
        """An energy event ``(when, amount, node, confidence, source)`` (team_resource_data shape)."""
        cid = self._own(character_id)
        if len(tuple(event)) != 5:
            raise ValueError("resource event = (when, amount, node, confidence, source)")
        self.events.setdefault(cid, []).append(tuple(event))

    def node(self, character_id: int, node, *, category: str, bucket: str, confidence: str = "high",
             expected_value: bool = False, assumption: Mapping | str | None = None, reason: Mapping | str | None = None,
             unmodelled_codes: Iterable[str] = (), resolves_codes: Iterable[str] = (), rotation_assumed: bool = False,
             pre_release: bool = False, scope: str = "") -> NodeInfo:
        cid = self._own(character_id)
        canonical = ta.node_id(node)
        if canonical is None:
            raise ValueError(f"unknown node {node!r}")
        if category not in CATEGORIES:
            raise ValueError(f"unknown category {category!r}")
        if bucket not in BUCKETS:
            raise ValueError(f"unknown bucket {bucket!r}")
        if confidence not in CONFIDENCES:
            raise ValueError(f"unknown confidence {confidence!r}")
        if (cid, canonical) in self.infos:
            raise ValueError(f"node {cid}:{canonical} declared twice")
        info = NodeInfo(cid, canonical, category, bucket, self.group, confidence, bool(expected_value),
                        _lang_map(assumption), _lang_map(reason), tuple(unmodelled_codes), tuple(resolves_codes),
                        bool(rotation_assumed), bool(pre_release), str(scope or ""))
        self.infos[(cid, canonical)] = info
        return info

    def text(self, code: str, builder: Callable) -> None:
        """Explanation text of a note code this group emits: ``builder(args, names) -> str`` (use _L / _LF)."""
        prefix = f"awakening_{self.group}_"
        if not str(code).startswith(prefix):
            raise ValueError(f"note codes of group {self.group} start with {prefix!r}")
        self.texts[str(code)] = builder


def _lang_map(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, str):
        return {"ko": value}
    return {str(k): str(v) for k, v in dict(value).items() if v}


REGISTRY: dict[str, RuleSet] = {}


def _register(ruleset: RuleSet) -> None:
    if ruleset.group in REGISTRY:
        raise ValueError(f"rule set {ruleset.group!r} registered twice")
    for other in REGISTRY.values():
        shared = set(other.characters) & set(ruleset.characters)
        if shared:
            raise ValueError(f"characters {sorted(shared)} owned by {other.group} and {ruleset.group}")
    REGISTRY[ruleset.group] = ruleset


def rulesets(enabled_only: bool = True) -> list[RuleSet]:
    return [r for r in REGISTRY.values() if not enabled_only or group_enabled(r.group)]


def owner_of(character_id: int) -> RuleSet | None:
    return next((r for r in REGISTRY.values() if int(character_id) in r.characters), None)


def node_info(character_id: int, node) -> NodeInfo | None:
    canonical = ta.node_id(node)
    for r in REGISTRY.values():
        info = r.infos.get((int(character_id), canonical))
        if info is not None:
            return info
    return None


def nodes_of(character_id: int) -> dict:
    """{node id: NodeInfo} declared for the character (any group, enabled or not)."""
    out = {}
    for r in REGISTRY.values():
        for (cid, node), info in r.infos.items():
            if cid == int(character_id):
                out[node] = info
    return out


def all_node_info() -> dict:
    out = {}
    for r in REGISTRY.values():
        out.update(r.infos)
    return out


def note_text(code: str, args: tuple, names: Mapping | None = None) -> str | None:
    """Text of a group note code (``awakening_<group>_...``), None when no group knows it."""
    for r in REGISTRY.values():
        build = r.texts.get(str(code))
        if build is not None:
            return build(tuple(args), names)
    return None


def registrations(kind: str | None = None, enabled_only: bool = True) -> list[Registration]:
    out = []
    for r in rulesets(enabled_only):
        out.extend(reg for reg in r.registrations if kind is None or reg.kind == kind)
    return sorted(out, key=lambda reg: (reg.order, reg.group, reg.character_id, reg.name))


# ── run time ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Member:
    """One team member as the hooks see it.  ``character`` is the ``_build_characters`` entry (profile, equipment,
    fork ...): read it, never change it."""
    character_id: int
    selection: ta.AwakeningSel
    character: Mapping = field(default_factory=dict, compare=False, repr=False)

    def has(self, node) -> bool:
        return ta.unlocked(self.selection, node)

    @property
    def level(self) -> int:
        return self.selection.level

    @property
    def profile(self) -> Mapping:
        return self.character.get("profile") or {}


@dataclass
class PlacedAction:
    """One action ``_AxisWriter.place`` laid out."""
    character_id: int
    action: tuple                   # (ability_id, selector)
    slot: str                       # the step's slot (basic / skill / ultimate / qte / entry ...)
    start_us: int
    length_us: int
    rows: tuple                     # the hit rows placed for it (dicts; read only)
    visit_index: int
    step_index: int
    writer: Any = None              # team_simulation_service._AxisWriter (gauge, resources, deferred gauge queue)
    layout: Any = None              # LayoutHooks of the layout (``layout.scratch`` = per-layout state, ``placed``)

    @property
    def end_us(self) -> int:
        return int(self.start_us) + int(self.length_us)

    def gain_gauge(self, amount: float, t_us: int | None = None) -> None:
        """Add Cycle gauge to the acting member at ``t_us`` (default: the action's end) through the writer, so the
        resource levels' deferred gauge queue keeps hit-time order (team_simulation_service._AxisWriter.add_gauge)."""
        if self.writer is not None and hasattr(self.writer, "add_gauge"):
            self.writer.add_gauge(int(self.character_id), float(amount), self.end_us if t_us is None else int(t_us))

    def gain_energy(self, amount: float, code: str = "node_rule", t_us: int | None = None) -> None:
        """Add ultimate energy (an event: not scaled by the charge efficiency) to the acting member through the writer:
        the reviewed layouts' ResourceState, or the custom walker's pools and step record
        (team_simulation_service._AxisWriter.add_energy)."""
        if self.writer is not None and hasattr(self.writer, "add_energy"):
            self.writer.add_energy(int(self.character_id), float(amount), str(code),
                                   self.end_us if t_us is None else int(t_us))


@dataclass
class GateEvent:
    character_id: int
    action: tuple
    slot: str
    start_us: int
    effect_hit_offsets: tuple       # ((ge, (offset_us, ...)), ...) of the bound animation candidate
    layout: Any = None              # LayoutHooks
    target: Any = None              # the run's target dict (DEFAULT_TARGET in approved runs; custom: the enemy options)


@dataclass
class SwapEvent:
    out_id: int | None
    in_id: int
    t_us: int
    mode: str                       # approved | custom
    layout: Any = None              # LayoutHooks (``layout.placed`` = the actions so far)
    pair: Any = None                # team_cycle_reactions.ReactionDef of the two elements (adjacent pair)
    decision: Any = None            # approved: the gauge's SwapDecision (outcome "gauge_short"); custom: None


@dataclass
class ResourceEvent:
    state: Any                      # team_resources.ResourceState
    character_id: int
    step_class: Any                 # team_resources.StepClass
    step: Mapping | None
    t_us: int
    gate: Any = None                # begin only: the ResourceGate of the step
    target: Any = None              # the run's target dict (ResourceState.target; None = DEFAULT_TARGET)


@dataclass(frozen=True)
class PostIncrement:
    """Damage added after replay to ``character_id``'s direct damage (credited to its visit at ``t_us``)."""
    character_id: int
    t_us: int
    damage: float
    label_zh: str = ""
    node: str = ""


@dataclass
class RunInfo:
    """One engine run as the run-level hooks see it (built in ``_run_axis``)."""
    ctx: Any                        # team_simulation_service._Ctx
    layout: Any                     # _Layout (rows, side, visits, swaps, stops, stop_owners, end_us ...)
    to_active: Callable
    to_wall: Callable
    sched: Any
    applications: dict              # _dot_applications(layout.rows, build)
    placed: tuple = ()              # PlacedAction log of the layout
    hits: list = field(default_factory=list)       # numbered hits of the engine call in progress
    dot_rows: list = field(default_factory=list)   # DoT rows after the dot_rows hooks
    extra_rows: list = field(default_factory=list)  # rows hooks' rows
    scratch: dict = field(default_factory=dict)     # shared by this run's hooks (key it by your group)

    @property
    def static(self):
        return self.ctx.static

    @property
    def build(self) -> dict:
        return self.ctx.build

    @property
    def names(self) -> dict:
        return self.ctx.names

    @property
    def team_ids(self) -> list:
        return list(self.ctx.team_ids)

    def row(self, character_id: int, t_us: int, ability_id: str | None, ge: str, attribute: str,
            component: str = "") -> dict:
        """A hit row in the simulator's axis shape (``team_simulation_service._row``)."""
        from src.services.team_simulation_service import _row

        row = _row(int(character_id), self.ctx.names[int(character_id)], int(t_us), ability_id, ge, attribute)
        if component:
            row["damage_component"] = component
        return row


@dataclass
class HookCtx:
    """What every hook receives first."""
    member: Member
    prepared: "Prepared"
    registration: Registration
    con: Any = None                 # prepare only: sqlite3 connection (static DB, read-only)
    static: Any = None              # prepare / buff_rules: StaticGameDataDao
    sink: list | None = None        # where ctx.note() collects (the current layout / run / context)

    @property
    def data(self):
        return self.prepared.data.get(self.registration.key)

    @property
    def character_id(self) -> int:
        return self.member.character_id

    @property
    def selection(self) -> ta.AwakeningSel:
        return self.member.selection

    @property
    def members(self) -> dict:
        return self.prepared.members

    def note(self, code: str, *args, kind: str = "assume") -> None:
        """Add an explanation item (``kind`` assume | limit) to the result of this run / layout / context."""
        if kind not in ("assume", "limit"):
            raise ValueError("kind must be 'assume' or 'limit'")
        target = self.sink if self.sink is not None else self.prepared.notes
        item = (kind, str(code), tuple(args))
        if item not in target:
            target.append(item)


def _active(reg: Registration, member: Member | None) -> bool:
    if member is None:
        return False
    return not reg.nodes or any(member.has(n) for n in reg.nodes)


class Prepared:
    """The rules active for one simulation context (``_Ctx.node_rules``).  Empty when nothing applies, so a run
    without active rules takes exactly the old code path."""

    def __init__(self, members: Mapping[int, Member]) -> None:
        self.members: dict[int, Member] = dict(members)
        self.data: dict[tuple, Any] = {}
        self.notes: list = []
        self._active: dict[str, list[tuple[Registration, Member]]] = {k: [] for k in HOOK_KINDS}
        for reg in registrations():
            member = self.members.get(reg.character_id)
            if _active(reg, member):
                self._active[reg.kind].append((reg, member))
        self.extra_rules: dict[int, tuple] = {}
        self.extra_events: dict[int, tuple] = {}
        for r in rulesets():
            for cid, rows in r.rules.items():
                if cid in self.members:
                    self.extra_rules[cid] = self.extra_rules.get(cid, ()) + tuple(rows)
            for cid, rows in r.events.items():
                if cid in self.members:
                    self.extra_events[cid] = self.extra_events.get(cid, ()) + tuple(rows)

    # queries ------------------------------------------------------------------
    def active(self, kind: str) -> list:
        return list(self._active.get(kind) or ())

    def has(self, *kinds: str) -> bool:
        return any(self._active.get(k) for k in kinds)

    @property
    def empty(self) -> bool:
        return not any(self._active.values()) and not self.extra_rules and not self.extra_events

    def selection(self, character_id: int) -> ta.AwakeningSel:
        member = self.members.get(int(character_id))
        return member.selection if member is not None else ta.EMPTY

    def selections(self) -> dict:
        return {cid: m.selection for cid, m in self.members.items()}

    def applied(self) -> dict:
        """{character id: nodes} whose node rules (any hook with nodes, or data rows) are active for the member."""
        out: dict[int, list] = {}

        def add(cid: int, node) -> None:
            canonical = ta.node_id(node)
            member = self.members.get(int(cid))
            if canonical is None or member is None or not member.has(canonical):
                return
            out.setdefault(int(cid), [])
            if canonical not in out[int(cid)]:
                out[int(cid)].append(canonical)

        for kind in HOOK_KINDS:
            for reg, _member in self._active[kind]:
                data = self.data.get(reg.key)
                if isinstance(data, Mapping) and data.get(INACTIVE_KEY):
                    continue            # its prepare hook said the rules do not apply here (e.g. the overlay is off)
                for node in reg.nodes:
                    add(reg.character_id, node)
        for cid, rows in self.extra_rules.items():
            for row in rows:
                add(cid, row[3])
        for cid, rows in self.extra_events.items():
            for row in rows:
                add(cid, row[2])
        return {cid: tuple(_ordered(nodes)) for cid, nodes in out.items()}

    def ctx(self, reg: Registration, member: Member, sink: list | None = None, **extra) -> HookCtx:
        return HookCtx(member=member, prepared=self, registration=reg, sink=sink, **extra)

    # context-level calls ----------------------------------------------------------
    def run_prepare(self, con, static) -> None:
        for reg, member in self.active("prepare"):
            self.data[reg.key] = reg.func(self.ctx(reg, member, con=con, static=static))

    def extend_buff_rules(self, static, build, rules):
        for reg, member in self.active("buff_rules"):
            rules = reg.func(self.ctx(reg, member, static=static), static, build, rules)
        return rules

    def layout(self, mode: str = "approved") -> "LayoutHooks | None":
        """Per-layout hooks (None when no layout-level hook is active in ``mode``)."""
        regs = {k: [(r, m) for r, m in self.active(k) if mode in r.modes] for k in LAYOUT_KINDS}
        if not any(regs.values()):
            return None
        return LayoutHooks(self, mode, regs)

    def run(self, info: RunInfo) -> "RunHooks | None":
        if not self.has(*RUN_KINDS):
            return None
        return RunHooks(self, info)

    def resource_rules(self, character_id: int) -> tuple:
        return tuple(self.extra_rules.get(int(character_id), ()))

    def resource_events(self, character_id: int) -> tuple:
        return tuple(self.extra_events.get(int(character_id), ()))

    def resource_hooks(self) -> "ResourceHooks | None":
        if not self.has(*RESOURCE_KINDS):
            return None
        return ResourceHooks(self)

    def resolve_values(self, con=None) -> None:
        """Replace ``"curve:<id>"`` values of the data rows by the static DB's number (``con``; None = the application's
        static DB, cached per process); a missing curve gives None (the rule then acts without it)."""
        for table, index in ((self.extra_rules, 2), (self.extra_events, 1)):
            for cid, rows in list(table.items()):
                table[cid] = tuple(_resolve_row(row, index, con) for row in rows)


def _ordered(nodes: Iterable[str]) -> list:
    order = {n: i for i, n in enumerate(ta.NODE_IDS + ta.RESONANCE_IDS)}
    return sorted(dict.fromkeys(nodes), key=lambda n: order.get(n, 99))


class LayoutHooks:
    """Hooks of one layout (approved ``_layout_axis`` or the custom walker); ``placed`` is the action log."""

    def __init__(self, prepared: Prepared, mode: str, regs: Mapping[str, list]) -> None:
        self.prepared = prepared
        self.mode = mode
        self._regs = {k: list(v) for k, v in regs.items()}
        self.placed: list[PlacedAction] = []
        self.notes: list = []
        self.scratch: dict = {}
        self.target_condition: Mapping | None = None    # set by team_simulation_service._layout_hooks

    def gate(self, character_id: int, action: tuple, slot: str, start_us: int, effect_hit_offsets):
        regs = [(r, m) for r, m in self._regs.get("gate") or () if r.character_id == int(character_id)]
        if not regs:
            return effect_hit_offsets
        offsets = tuple(effect_hit_offsets)
        for reg, member in regs:
            ev = GateEvent(int(character_id), tuple(action), str(slot or ""), int(start_us), offsets, self,
                           self.target_condition)
            got = reg.func(self.prepared.ctx(reg, member, self.notes), ev)
            if got is not None:
                offsets = tuple(got)
        return offsets

    def on_placed(self, ev: PlacedAction) -> None:
        ev.layout = self
        self.placed.append(ev)
        for reg, member in self._regs.get("placed") or ():
            if reg.members == "self" and reg.character_id != ev.character_id:
                continue
            reg.func(self.prepared.ctx(reg, member, self.notes), ev)

    def free_support(self, out_id, in_id: int, t_us: int, pair=None, decision=None) -> bool:
        """Asked only for a swap into an adjacent element whose gauge is short (approved) / a typed support entry with
        a short gauge (custom); True = the support entry plays and fires the pair's reaction without the gauge."""
        free = False
        for reg, member in self._regs.get("free_support") or ():
            if reg.character_id != int(in_id):
                continue
            ev = SwapEvent(None if out_id is None else int(out_id), int(in_id), int(t_us), self.mode, self, pair,
                           decision)
            if reg.func(self.prepared.ctx(reg, member, self.notes), ev):
                free = True
        return free


class RunHooks:
    """Hooks of one engine run (``_run_axis``): rows before the engine, intervals / evidence inside it, increments
    after replay."""

    def __init__(self, prepared: Prepared, info: RunInfo) -> None:
        self.prepared = prepared
        self.info = info
        self.notes: list = []

    def _each(self, kind: str):
        for reg, member in self.prepared.active(kind):
            yield reg, self.prepared.ctx(reg, member, self.notes)

    def dot_rows(self, dot_rows: list) -> list:
        for reg, ctx in self._each("dot_rows"):
            got = reg.func(ctx, self.info, list(dot_rows))
            if got is not None:
                dot_rows = list(got)
        self.info.dot_rows = list(dot_rows)
        return dot_rows

    def rows(self) -> tuple[list, list]:
        """(extra rows, those that are also DoT ticks)."""
        rows, ticks = [], []
        for reg, ctx in self._each("rows"):
            got = list(reg.func(ctx, self.info) or ())
            rows.extend(got)
            if reg.dot_ticks:
                ticks.extend(got)
        self.info.extra_rows = list(rows)
        return rows, ticks

    def intervals(self, analysis):
        for reg, ctx in self._each("intervals"):
            got = reg.func(ctx, self.info, analysis)
            if got is not None:
                analysis = got
        return analysis

    def evidence(self, evidence):
        for reg, ctx in self._each("evidence"):
            got = reg.func(ctx, self.info, evidence)
            if got is not None:
                evidence = got
        return evidence

    def post(self, pairs) -> list:
        out: list[PostIncrement] = []
        for reg, ctx in self._each("post"):
            for inc in reg.func(ctx, self.info, pairs) or ():
                if not isinstance(inc, PostIncrement):
                    raise TypeError("post hooks return PostIncrement items")
                out.append(inc)
        return out


class ResourceHooks:
    """Callable resource hooks handed to ``team_resources.ResourceState`` (reviewed layouts)."""

    def __init__(self, prepared: Prepared) -> None:
        self.prepared = prepared
        self.notes: list = []

    def begin(self, state, character_id: int, cls, step, t_us: int, gate) -> None:
        for reg, member in self.prepared.active("resource_begin"):
            if reg.character_id != int(character_id):
                continue
            reg.func(self.prepared.ctx(reg, member, self.notes),
                     ResourceEvent(state, int(character_id), cls, step, int(t_us), gate, getattr(state, "target", None)))

    def after(self, state, character_id: int, cls, step, t_us: int) -> list:
        new = []
        for reg, member in self.prepared.active("resource_after"):
            if reg.character_id != int(character_id):
                continue
            got = reg.func(self.prepared.ctx(reg, member, self.notes),
                           ResourceEvent(state, int(character_id), cls, step, int(t_us), None,
                                         getattr(state, "target", None)))
            new.extend(got or ())
        return new


def _is_curve(value) -> bool:
    return isinstance(value, str) and value.startswith(CURVE_PREFIX)


def curve_value(curve_id: str, con=None) -> float | None:
    """First point of a static-DB curve (``combat_curve_point``): ``con`` or the application's static DB."""
    if con is not None:
        try:
            row = con.execute("SELECT value FROM combat_curve_point WHERE curve_id=? ORDER BY ordinal LIMIT 1",
                              (str(curve_id),)).fetchone()
        except Exception:
            return None
        return None if row is None or row[0] is None else float(row[0])
    if curve_id in _DEFAULT_CURVES:
        return _DEFAULT_CURVES[curve_id]
    value = None
    try:
        import sqlite3

        from src.storage.sqlite.static_game_data_dao import resolve_static_database

        path = resolve_static_database()
        own = sqlite3.connect(f"{Path(path).absolute().as_uri()}?mode=ro", uri=True)
        try:
            value = curve_value(curve_id, own)
        finally:
            own.close()
    except Exception:
        value = None
    _DEFAULT_CURVES[curve_id] = value
    return value


_DEFAULT_CURVES: dict = {}


def _resolve_row(row: tuple, index: int, con) -> tuple:
    if not _is_curve(row[index]):
        return tuple(row)
    value = curve_value(str(row[index])[len(CURVE_PREFIX):], con)
    return tuple(row[:index]) + (value,) + tuple(row[index + 1:])


EMPTY_PREPARED_MEMBERS: dict = {}


def prepare(con, static, characters: Iterable[Mapping]) -> Prepared:
    """The rules of one context: members from ``_build_characters`` entries, then every active ``prepare`` hook."""
    members = {}
    for c in characters or ():
        cid = int(c["character_id"])
        sel = c.get("_awakening")
        if not isinstance(sel, ta.AwakeningSel):
            sel = ta.from_profile(c.get("profile") or {})
        members[cid] = Member(cid, sel, c)
    prepared = Prepared(members)
    prepared.resolve_values(con)
    prepared.run_prepare(con, static)
    return prepared


def for_selections(selections: Mapping[int, Any]) -> Prepared:
    """Rules for a member -> selection map without a database (custom preview, tests): no ``prepare`` hook runs; curve
    values of the data rows come from the application's static DB."""
    prepared = Prepared({int(c): Member(int(c), ta.coerce(s)) for c, s in dict(selections or {}).items()})
    prepared.resolve_values(None)
    return prepared
