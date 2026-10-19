# 队伍模拟与弧盘效率表共用的弧盘引擎修正（Global）：B1 面板同步、B2 常驻效果去重、B3「罪与罚」、B4「月的对跖点」。
"""Global corrections to the battle engine's arc (fork) modelling.

Shared by the team simulation (``team_simulation_service``) and the arc efficiency table, so the efficiency
table's 100 % value and a one-member team simulation are the same number.  The upstream engine files
(``battle_*``) are not changed: the battle report runs the same engine.

B1  Arc swap reaches the panel.  The stat reconstruction (``official_role_attribute_service._fork_property_stats``)
    reads the arc from ``profile["fork_id"/"fork_refinement_level"]``; :func:`sync_profile` keeps the profile in
    step with the member's selection (``team_simulation_service._build_characters``).
B2  No double counting of always-on arc bonuses.  A ``fork_star:*`` interval with trigger ``STATIC_EQUIPPED_SOURCE``
    whose modifier (property, value) equals a ``fork_permanent_property`` row of the arc in the member's panel loses
    that modifier (the panel already holds the bonus); an interval left without modifiers is removed.  Only
    properties the per-hit damage projection consumes are removed (the engine's own list): a non-damage duplicate
    (好狗狗走四方 ChargeGetEfficiencyBase) never reached the damage formula and is the only source of the custom-cycle
    energy model's automatic charge efficiency, so it stays.
B3  「罪与罚」 (fork_twinbirds).  The engine opens ``Buff_Fork_TwinBirds_Effect_CritUp`` (whole team) and
    ``..._CritUp2`` (wearer) at ``BUFF_EVENT_Q_SKILL_BEGIN`` but cannot price them (CustomCalculationClass,
    magnitude None).  B3 fills ``buff_TwinBirds_CritUp1`` / ``buff_TwinBirds_CritUp3`` of the arc's refinement
    (value confidence 中: the projection drops 低 values), gives the team part the team scope, and ends each window
    ``buff_TwinBirds_CritUp1_CD`` seconds of active time after its start (a re-trigger refreshes: the projection keeps
    the latest window of the same buff).  ``...NightCrow...`` variants are never filled (no double count).
B4  「月的对跖点」 (fork_prism).  No buff link reaches the engine (combat_effect_buff_link.target_available = 0), so
    the windows are built from the wearer's hits: (1) normal-attack damage -> skill (E) damage +``DamageUp1`` per
    stack (max 4, at most one stack per 0.3 s, ``DamageUp1_CD`` seconds, a new stack refreshes); (2) E cast ->
    normal-attack damage +``DamageUp2`` for ``DamageUp2_CD`` seconds (a re-cast refreshes); (3) both at once ->
    Lakshana damage +``LakshanaUp``.  "Normal attack" is the engine's own ``State.Damage.NormalAttack`` test
    (``battle_buff_projection_rules._confirmed_source_tags_apply``); 4 stacks / 0.3 s are the description's numbers.
    Release mode (``PRISM_MODES``; the Global live overlay's DB, group arc_release): (1) Skill damage +DamageUp1 x 4 for
    the whole fight, (2) as above, (3) Lakshana damage inside every (2) window.
B3 and B4 are Global modelling from the description text and the DB parameters (upstream 2.3.1 models Raven only in
its native core).  Their intervals carry ``source_kind = "global_fork_supplement"``.

Clock: every B3 / B4 duration runs on the active clock (time stops excluded), exactly like the engine's own buff
windows (``battle_buff_interval_support._interval_end``: ``project_timeline_time_us`` / ``unproject_timeline_time_us``
with the analysis' ``time_stop_intervals`` and ``battle_end_us``).

Switch (tests and the regression baseline): ``ENABLED`` (default: b1-b4), read at import from the environment
variable ``NTE_TEAM_FORK_CORRECTIONS`` = ``off`` | ``on`` | a comma list such as ``b2,b3``.  With everything off the
team simulation is the shipped one, number for number.
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

ALL = ("b1", "b2", "b3", "b4")
ENV = "NTE_TEAM_FORK_CORRECTIONS"
SOURCE_KIND = "global_fork_supplement"
NAME_PREFIX = "Global supplement: "
STATIC_TRIGGER = "STATIC_EQUIPPED_SOURCE"
FORK_STAR = "fork_star:"
SUPPLEMENT_CONFIDENCE = "中"            # the projection accepts 中 / 高 values only

# B3 「罪与罚」: engine buff name -> (value parameter, target scope)
TWINBIRDS_FORK = "fork_twinbirds"
TWINBIRDS = {
    "Buff_Fork_TwinBirds_Effect_CritUp": ("buff_TwinBirds_CritUp1", "team"),     # 全队角色暴击伤害提高{2}
    "Buff_Fork_TwinBirds_Effect_CritUp2": ("buff_TwinBirds_CritUp3", "self"),    # 装备者额外提高{3}
}
TWINBIRDS_DURATION = "buff_TwinBirds_CritUp1_CD"                                  # 持续{4}秒

# B4 「月的对跖点」
PRISM_FORK = "fork_prism"
PRISM_PARAMETERS = ("buff_Prism_DamageUp1", "buff_Prism_DamageUp2", "buff_Prism_LakshanaUp",
                    "buff_Prism_DamageUp1_CD", "buff_Prism_DamageUp2_CD")
PRISM_STACK_MAX = 4                     # 这个效果最多可叠加4次
PRISM_STACK_INTERVAL_US = 300_000       # 每0.3秒最多叠加一次
PRISM_KINDS = ("skill_damage", "normal_damage", "lakshana_damage")
# "db": the 9-24 description (stacks / both effects at once); "release": the CN release text (global_live_overlay
# arc_release, only for the overlay's DB): (1) Skill damage +DamageUp1 x 4 for the whole fight, (2) unchanged, (3)
# Lakshana damage +LakshanaUp inside the (2) window
PRISM_MODES = ("db", "release")


def parse_switch(value: str | None) -> set[str]:
    """``NTE_TEAM_FORK_CORRECTIONS`` value -> enabled codes (unset / "on" = all, "off" = none)."""
    text = str(value or "").strip().casefold()
    if text in ("", "on", "all", "1", "true", "yes"):
        return set(ALL)
    if text in ("off", "none", "0", "false", "no"):
        return set()
    return {token.strip() for token in text.replace(";", ",").split(",") if token.strip() in ALL}


ENABLED: set[str] = parse_switch(os.environ.get(ENV))


def enabled(code: str) -> bool:
    return code in ENABLED


# ── B1 ─────────────────────────────────────────────────────────────────────

def sync_profile(profile: dict, fork_id: Any, refinement: Any) -> None:
    """B1: the panel reads the arc from the profile; write the member's selected arc and refinement into it."""
    if "b1" in ENABLED and isinstance(profile, dict) and fork_id:
        profile["fork_id"] = fork_id
        profile["fork_refinement_level"] = refinement


# ── per-member arc data (read once per simulation context) ───────────────────

@dataclass(frozen=True)
class MemberArc:
    character_id: int
    fork_id: str                        # selected arc (buff rules use it)
    refinement: int
    panel_fork_id: str                  # arc in the panel (profile)
    panel_refinement: int
    permanent: tuple[tuple[str, float], ...] = ()      # fork_permanent_property rows of the panel arc


@dataclass(frozen=True)
class Change:
    """One thing a correction did (for the explanation, the efficiency table flags and the tests)."""
    code: str                           # "b2" | "b3" | "b4"; "b2_kept" = non-damage duplicate left in place
    character_id: int
    fork_id: str
    refinement: int
    interval_id: str
    buff_name: str
    property_id: str
    value: float | None
    start_us: int = 0
    end_us: int = 0
    detail: str = ""                    # b2: "removed" | "modifier"; b4: kind; b3: target scope


@dataclass(frozen=True)
class CorrectionReport:
    changes: tuple[Change, ...] = ()
    enabled: tuple[str, ...] = ()

    def of(self, code: str) -> tuple[Change, ...]:
        return tuple(c for c in self.changes if c.code == code)

    def characters(self, *codes: str) -> tuple[int, ...]:
        wanted = set(codes)
        return tuple(dict.fromkeys(c.character_id for c in self.changes if c.code in wanted))

    def forks(self, *codes: str) -> tuple[str, ...]:
        wanted = set(codes)
        return tuple(dict.fromkeys(c.fork_id for c in self.changes if c.code in wanted))

    @property
    def supplement(self) -> bool:
        return any(c.code in ("b3", "b4") for c in self.changes)

    @property
    def dedup(self) -> bool:
        return any(c.code == "b2" for c in self.changes)


EMPTY_REPORT = CorrectionReport()


def _rows(con, sql: str, args: tuple = ()) -> list:
    try:
        return list(con.execute(sql, args))
    except Exception:                    # older static schema without the table: nothing to correct
        return []


def load_permanent(con, fork_id: str, refinement: int) -> tuple[tuple[str, float], ...]:
    return tuple((str(p), float(v)) for p, v in _rows(
        con, "SELECT property_id, property_value FROM fork_permanent_property WHERE fork_id=? AND refinement_level=? "
             "ORDER BY property_id", (fork_id, int(refinement))) if v is not None)


def load_parameters(con, fork_id: str, refinement: int) -> dict[str, float]:
    return {str(n): float(v) for n, v in _rows(
        con, "SELECT p.name_id, v.value FROM fork_item f "
             "JOIN fork_star_parameter p ON p.star_pack_id = f.star_pack_id "
             "JOIN fork_refinement_parameter_value v ON v.name_id = p.name_id AND v.refinement_level = p.star_level "
             "WHERE f.fork_id=? AND p.star_level=?", (fork_id, int(refinement))) if v is not None}


def prepare(con, characters: Iterable[Mapping]) -> "ForkCorrections":
    """Read what the corrections need for these members (static DB connection, read-only)."""
    star_packs = {str(sp): str(fid) for fid, sp in _rows(con, "SELECT fork_id, star_pack_id FROM fork_item") if sp}
    prism_mode = "db"
    try:            # Global live overlay: 「月的对跖点」 as released (CN 10-15) on the overlay's DB only
        from src.services import global_live_overlay

        if global_live_overlay.active_for_con(con, "arc_release"):
            prism_mode = "release"
    except Exception:
        prism_mode = "db"
    members: dict[int, MemberArc] = {}
    parameters: dict[tuple[str, int], dict[str, float]] = {}
    for character in characters:
        cid = int(character["character_id"])
        profile = character.get("profile") or {}
        fork_id = str(character.get("fork_id") or "")
        refinement = int(character.get("fork_refinement_level") or 0)
        panel_fork = str(profile.get("fork_id") or "")
        panel_refinement = int(profile.get("fork_refinement_level") or 0)
        members[cid] = MemberArc(cid, fork_id, refinement, panel_fork, panel_refinement,
                                 load_permanent(con, panel_fork, panel_refinement) if panel_fork else ())
        if fork_id and refinement > 0 and (fork_id, refinement) not in parameters:
            parameters[(fork_id, refinement)] = load_parameters(con, fork_id, refinement)
    return ForkCorrections(members, star_packs, parameters, prism_mode=prism_mode)


# ── the active clock (as battle_buff_interval_support._interval_end) ─────────

def active_us(analysis, wall_us: int) -> int:
    from src.services.battle_timeline_time_service import ACTIVE_TIME_MODE, project_timeline_time_us

    return project_timeline_time_us(int(wall_us), battle_start_us=0,
                                    intervals=tuple(analysis.time_stop_intervals or ()), mode=ACTIVE_TIME_MODE)


def wall_end_us(analysis, active_end: int) -> int:
    """Wall time at which ``active_end`` µs of active time have passed (the back edge of a stop plateau)."""
    from src.services.battle_timeline_time_service import ACTIVE_TIME_MODE, unproject_timeline_time_us

    return unproject_timeline_time_us(int(active_end), battle_start_us=0, battle_end_us=int(analysis.battle_end_us),
                                      intervals=tuple(analysis.time_stop_intervals or ()), mode=ACTIVE_TIME_MODE,
                                      prefer_interval_end=True)


def active_window_end(analysis, start_us: int, seconds: float) -> int:
    return wall_end_us(analysis, active_us(analysis, start_us) + int(round(float(seconds) * 1_000_000)))


# ── helpers ────────────────────────────────────────────────────────────────

def is_fork_interval(interval) -> bool:
    return str(getattr(interval, "source_effect_definition_id", "") or "").startswith(FORK_STAR)


def star_identity(interval) -> tuple[str, int] | None:
    """``fork_star:<star pack>:<refinement>:...`` -> (star pack, refinement)."""
    parts = str(getattr(interval, "source_effect_definition_id", "") or "").split(":")
    if len(parts) < 3 or parts[0] != "fork_star":
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def damage_property(property_id: str) -> bool:
    """True when the per-hit damage projection consumes the property (the engine's own list)."""
    from src.services.battle_buff_projection_rules import (
        _SAFE_ADDITIVE_PROPERTIES,
        normalize_battle_buff_property_id,
    )

    return normalize_battle_buff_property_id(str(property_id)) in _SAFE_ADDITIVE_PROPERTIES


def is_normal_attack(hit) -> bool:
    """The engine's ``State.Damage.NormalAttack`` source-tag test, unchanged."""
    from src.services.battle_buff_projection_rules import _confirmed_source_tags_apply

    probe = _TagProbe(("State.Damage.NormalAttack",))
    try:
        return bool(_confirmed_source_tags_apply(None, probe, hit)[0])
    except Exception:
        return False


@dataclass(frozen=True)
class _TagProbe:
    source_require_tags: tuple[str, ...]
    target_require_tags: tuple[str, ...] = ()


def unresolved_fork_buffs(analysis, panel_properties: Iterable[str] = ()) -> tuple[str, ...]:
    """Arc buffs whose value the engine could not resolve (every modifier None), without the always-on source
    intervals whose properties the panel's permanent rows already cover (e.g. Buff_Fork_TwinBirds_Lv1)."""
    covered = set(panel_properties)
    out = []
    for interval in getattr(analysis, "buff_intervals", ()) or ():
        if not is_fork_interval(interval) or not interval.modifiers:
            continue
        if any(m.magnitude_value is not None for m in interval.modifiers):
            continue
        if interval.trigger_event_type == STATIC_TRIGGER and {m.property_id for m in interval.modifiers} <= covered:
            continue
        out.append(interval.buff_name)
    return tuple(sorted(set(out)))


# ── the corrections ────────────────────────────────────────────────────────

class ForkCorrections:
    """``analysis -> analysis`` applied in team_simulation_service._run_engine right after ``analyze`` and before the
    custom-cycle ``buff_edit``.  ``last_report`` holds what the latest call changed."""

    def __init__(self, members: Mapping[int, MemberArc], star_packs: Mapping[str, str],
                 parameters: Mapping[tuple[str, int], Mapping[str, float]], *, prism_mode: str = "db") -> None:
        self.members = dict(members)
        self.star_packs = dict(star_packs)
        self.parameters = {k: dict(v) for k, v in parameters.items()}
        self.prism_mode = prism_mode if prism_mode in PRISM_MODES else "db"
        self.last_report: CorrectionReport = EMPTY_REPORT

    def __call__(self, analysis):
        analysis, self.last_report = self.apply(analysis)
        return analysis

    def apply(self, analysis, codes: Iterable[str] | None = None):
        active = set(ENABLED if codes is None else codes) & {"b2", "b3", "b4"}
        if not active or analysis is None:
            return analysis, CorrectionReport(enabled=tuple(sorted(active)))
        changes: list[Change] = []
        memo: dict[str, Any] = {}

        def edit(seq) -> tuple:
            out = []
            for interval in seq or ():
                key = interval.interval_id
                if key not in memo:
                    memo[key] = self._one(analysis, interval, active, changes)
                if memo[key] is not None:
                    out.append(memo[key])
            return tuple(out)

        buff_intervals = edit(analysis.buff_intervals)
        timeline = edit(analysis.timeline_buff_intervals)
        extra = self._prism(analysis, changes) if "b4" in active else ()
        report = CorrectionReport(changes=tuple(changes), enabled=tuple(sorted(active)))
        if not any(c.code in ("b2", "b3", "b4") for c in changes):
            return analysis, report          # nothing changed (b2_kept only notes a harmless duplicate)
        analysis = dataclasses.replace(analysis, buff_intervals=buff_intervals + extra,
                                       timeline_buff_intervals=timeline + extra)
        return analysis, report

    # B2 / B3 on one engine interval (None = remove it)
    def _one(self, analysis, interval, active: set, changes: list):
        if not is_fork_interval(interval):
            return interval
        if "b2" in active and interval.trigger_event_type == STATIC_TRIGGER:
            interval = self._dedupe(interval, changes)
            if interval is None:
                return None
        if "b3" in active and interval.buff_name in TWINBIRDS:
            interval = self._twinbirds(analysis, interval, changes)
        return interval

    def _identity(self, interval) -> tuple[str, int] | None:
        star = star_identity(interval)
        if star is None:
            return None
        fork_id = self.star_packs.get(star[0])
        return (fork_id, star[1]) if fork_id else None

    def _dedupe(self, interval, changes: list):
        identity = self._identity(interval)
        member = self.members.get(int(interval.source_character_id or 0))
        if identity is None or member is None or identity != (member.panel_fork_id, member.panel_refinement):
            return interval                  # the panel does not hold this arc: nothing is counted twice
        rows = member.permanent
        kept, dropped = [], []
        for m in interval.modifiers:
            dup = (m.magnitude_value is not None
                   and any(m.property_id == p and abs(float(m.magnitude_value) - v) < 1e-9 for p, v in rows))
            if dup and not damage_property(m.property_id):
                # a non-damage duplicate never reached the damage formula: keep it (custom-cycle energy model)
                changes.append(Change("b2_kept", member.character_id, identity[0], identity[1], interval.interval_id,
                                      interval.buff_name, m.property_id, float(m.magnitude_value),
                                      int(interval.start_us), int(interval.end_us), "non_damage"))
                dup = False
            (dropped if dup else kept).append(m)
        if not dropped:
            return interval
        detail = "removed" if not kept else "modifier"
        for m in dropped:
            changes.append(Change("b2", member.character_id, identity[0], identity[1], interval.interval_id,
                                  interval.buff_name, m.property_id, float(m.magnitude_value),
                                  int(interval.start_us), int(interval.end_us), detail))
        return dataclasses.replace(interval, modifiers=tuple(kept)) if kept else None

    def _twinbirds(self, analysis, interval, changes: list):
        identity = self._identity(interval)
        if identity is None or identity[0] != TWINBIRDS_FORK:
            return interval
        if not interval.modifiers or any(m.magnitude_value is not None for m in interval.modifiers):
            return interval                  # nothing to fill, or the engine priced it already
        params = self.parameters.get(identity) or {}
        name, scope = TWINBIRDS[interval.buff_name]
        value, seconds = params.get(name), params.get(TWINBIRDS_DURATION)
        if value is None or seconds is None:
            return interval
        end = min(int(interval.end_us), active_window_end(analysis, interval.start_us, seconds))
        if end <= int(interval.start_us):
            return interval
        modifiers = tuple(dataclasses.replace(m, magnitude_value=float(value), magnitude_kind=SOURCE_KIND,
                                              value_confidence=SUPPLEMENT_CONFIDENCE) for m in interval.modifiers)
        filled = dataclasses.replace(
            interval, modifiers=modifiers, end_us=end, target_scope=scope, source_kind=SOURCE_KIND,
            buff_name=NAME_PREFIX + interval.buff_name,
            inference_basis=(f"Global supplement (description + DB parameters): {name} = {value:g}, "
                             f"{TWINBIRDS_DURATION} = {seconds:g} s of active time from BUFF_EVENT_Q_SKILL_BEGIN"))
        for m in modifiers:
            changes.append(Change("b3", int(interval.source_character_id or 0), identity[0], identity[1],
                                  interval.interval_id, interval.buff_name, m.property_id, float(value),
                                  int(interval.start_us), end, scope))
        return filled

    # B4: built from the wearer's hits
    def _prism(self, analysis, changes: list) -> tuple:
        out: list = []
        for member in self.members.values():
            if member.fork_id != PRISM_FORK or member.refinement <= 0:
                continue
            params = self.parameters.get((member.fork_id, member.refinement)) or {}
            if any(k not in params for k in PRISM_PARAMETERS):
                continue
            if self._engine_models_prism(analysis, member):
                continue
            out.extend(self._prism_member(analysis, member, params, changes))
        return tuple(out)

    def _engine_models_prism(self, analysis, member: MemberArc) -> bool:
        """A later engine that infers the conditional prism buffs itself wins (no double count)."""
        for interval in analysis.timeline_buff_intervals or ():
            if (int(interval.source_character_id or 0) == member.character_id and is_fork_interval(interval)
                    and interval.trigger_event_type != STATIC_TRIGGER
                    and self._identity(interval) == (member.fork_id, member.refinement)):
                return True
        return False

    def _prism_member(self, analysis, member: MemberArc, p: Mapping[str, float], changes: list) -> list:
        cid = member.character_id
        battle_end = int(analysis.battle_end_us)
        hits = sorted((h for h in analysis.hits
                       if h.character_id == cid and getattr(h, "direction", "outgoing") == "outgoing"),
                      key=lambda h: (h.relative_time_us, h.event_id))
        release = self.prism_mode == "release"
        # (1) normal-attack damage -> E damage stacks (active clock: interval, duration and refresh)
        stack_s = float(p["buff_Prism_DamageUp1_CD"])
        segments: list[list[int]] = []          # [wall start, wall end, stacks]
        count, expiry_active, last_active = 0, None, None
        for hit in (() if release else hits):
            if not is_normal_attack(hit):
                continue
            t = int(hit.relative_time_us)
            ta = active_us(analysis, t)
            if last_active is not None and ta - last_active < PRISM_STACK_INTERVAL_US:
                continue
            count = 1 if expiry_active is None or ta > expiry_active else min(PRISM_STACK_MAX, count + 1)
            expiry_active = ta + int(round(stack_s * 1_000_000))
            last_active = ta
            segments.append([t + 1, min(battle_end, wall_end_us(analysis, expiry_active)), count])
        for a, b in zip(segments, segments[1:]):        # a stack change ends the previous segment
            a[1] = min(a[1], b[0])
        segments = [s for s in segments if s[1] > s[0]]
        # (2) E cast -> normal-attack damage (a re-cast inside the window refreshes it)
        window_s = float(p["buff_Prism_DamageUp2_CD"])
        windows: list[list[int]] = []
        casts = sorted(a.start_us for a in analysis.inferred_actions if a.character_id == cid and a.input_kind == "E")
        for start in casts:
            end = min(battle_end, active_window_end(analysis, start, window_s))
            if windows and start <= windows[-1][1]:
                windows[-1][1] = max(windows[-1][1], end)
            elif end > start:
                windows.append([int(start), end])
        out = []
        if release:                                     # (1) release: the whole fight, no stacks (x 4)
            from src.services.global_live_overlay_data import PRISM_STATIC_FACTOR

            segments = [[0, battle_end, PRISM_STATIC_FACTOR]] if battle_end > 0 else []
        for i, (s, e, c) in enumerate(segments):
            out.append(self._interval(member, PRISM_KINDS[0], i, s, e, "DamageUpGeneralBase",
                                      float(p["buff_Prism_DamageUp1"]) * c, ("State.Damage.Skill",), c))
        for i, (s, e) in enumerate(windows):
            out.append(self._interval(member, PRISM_KINDS[1], i, s, e, "DamageUpGeneralBase",
                                      float(p["buff_Prism_DamageUp2"]), ("State.Damage.NormalAttack",)))
        k = 0
        if release:                                     # (3) release: inside every E window
            for s, e in windows:
                out.append(self._interval(member, PRISM_KINDS[2], k, s, e, "DamageUpLakshanaBase",
                                          float(p["buff_Prism_LakshanaUp"])))
                k += 1
            segments = []
        for s1, e1, _c in segments:                     # (3) both effects -> Lakshana damage
            for s2, e2 in windows:
                s, e = max(s1, s2), min(e1, e2)
                if s < e:
                    out.append(self._interval(member, PRISM_KINDS[2], k, s, e, "DamageUpLakshanaBase",
                                              float(p["buff_Prism_LakshanaUp"])))
                    k += 1
        for interval in out:
            m = interval.modifiers[0]
            changes.append(Change("b4", cid, member.fork_id, member.refinement, interval.interval_id,
                                  interval.buff_name, m.property_id, m.magnitude_value, interval.start_us,
                                  interval.end_us, interval.buff_asset_path.rsplit(":", 1)[-1]))
        return out

    @staticmethod
    def _interval(member: MemberArc, kind: str, index: int, start: int, end: int, prop: str, value: float,
                  tags: tuple[str, ...] = (), stacks: int = 1):
        from src.domain.battle_report import BattleBuffModifierEvidence, BattleInferredBuffInterval

        return BattleInferredBuffInterval(
            interval_id=f"global:prism:{member.character_id}:{kind}:{index}",
            buff_asset_path=f"global-supplement:{PRISM_FORK}:{kind}",
            buff_name=f"{NAME_PREFIX}{PRISM_FORK} {kind}" + (f" x{stacks}" if kind == PRISM_KINDS[0] else ""),
            source_effect_definition_id=f"global_supplement:{PRISM_FORK}:{member.refinement}",
            source_kind=SOURCE_KIND, source_character_id=member.character_id, source_character_name="",
            target_scope="self", start_us=int(start), end_us=int(end), stacks=1, duration_policy="HasDuration",
            state_confidence=SUPPLEMENT_CONFIDENCE, value_confidence=SUPPLEMENT_CONFIDENCE,
            inference_basis="Global supplement (description + DB parameters, built from the wearer's hits)",
            trigger_event_type="GLOBAL_SUPPLEMENT", evidence_action_ids=(), evidence_event_ids=(),
            modifiers=(BattleBuffModifierEvidence(
                property_id=prop, modifier_operation="EGameplayModOp::Additive", magnitude_kind=SOURCE_KIND,
                magnitude_value=float(value), calculation_asset_path="", value_confidence=SUPPLEMENT_CONFIDENCE,
                source_require_tags=tuple(tags)),))
