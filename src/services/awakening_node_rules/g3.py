# 队伍模拟：觉醒（돌파）效果规则——角色组 g3（海月 卡厄斯 灵可 小吱 伊洛伊 真红）。只在本文件登记本组角色的规则。
"""Awakening-node rules of group g3: characters 1070, 1071, 1072, 1073, 1075, 1076.

Edit only this file (see the package docstring for the recipe and core for the hook kinds).  Reviewed numbers and
hooks: ``work_g231/awaken/specs/group_3.json`` / ``group_3_review.md``; report ``awaken/reports/impl/group_3.md``.

Modelled here (every value is read from the static DB in the ``prepare`` hooks; nothing numeric is hard-coded):

========  ===========  =================================================================================
1070      ① ③ 공명6    「华彩」 windows (E damage hit − montage lead, 12 s active, refresh) -> ① CritBase,
                       ③ DamageUpGeneralBase on State.Damage.UltraSkill, 공명6 team DamageUpPsycheBase 15 s
1070      ②            team only: a support-skill entry opens 「华彩」 for 5 s / extends it by 5 s (cap 12 s)
1071      ② ⑤ 공명6    「追缉许可」 mark windows per target (E / Q mark notify before the first damage hit,
                       15 s active, refresh) -> ② DefIgnore, ⑤ DamageUpGeneralBase (single marked target),
                       공명6 target DamageResistLakshanaBase
1071      ③            CritDamageBase 20 s active from each Q start (refresh)
1072      ④            one Level4 AOE hit row per co-attack row inside the resonance domain (rows hook)
1072      ⑤            DamageUpGeneralBase on the co-attack the E calls (solo: 小贞; team: the carry cannot react)
1072      ⑥            (1) CritBase on Linko's co-attack hits, whole fight; (2) team: teammates' support-skill
                       hits inside the domain (fix: the engine's linko-coattack context never occurs)
1072      공명6        team DamageUpNatureBase + DamageUpIncantationBase, [Linko Q stop, +13 s active]
1073      ⑥            fill: the engine's unpriced Effect6 interval = DamageUpGeneralBase on the coin GEs
1075      공명3        fix: fill the engine's unpriced party DefUp interval (team, Infinite)
1075      공명6        fill: the engine's unpriced CritDamageBase interval (team; 「退行」 part 0)
========  ===========  =================================================================================

Every other node of the group is declared with its metadata only (``RULES.node``): already priced by the engine,
needs a measurement, or not computable on the single immortal dummy.  A node the engine already prices
(``character_awaken:<cid>:<node>`` interval with a value that reaches a hit) is never priced twice.
"""
from __future__ import annotations

import dataclasses
import json

from src.services.awakening_node_rules.core import NAME_PREFIX, SOURCE_KIND, SUPPLEMENT_CONFIDENCE, RuleSet

RULES = RuleSet("g3", (1070, 1071, 1072, 1073, 1075, 1076))

MITSUKI, CHAOS, LINKO, CHIICHAN, ILOI, SHINKU = 1070, 1071, 1072, 1073, 1075, 1076

# game identifiers (names, not values)
MITSUKI_E = "GA_Mitsuki_Skill"
MITSUKI_CADENZA_BUFF = "Buff_Mitsuki_Skill"                       # 「华彩」
MITSUKI_E_DAMAGE = "GE_Player_Mitsuki_Skill_Damage"
MITSUKI_ULT_DMG_BUFF = "Buff_Mitsuki070_Level3_DmgUp"             # ③ (source tag State.Damage.UltraSkill)
CHAOS_E, CHAOS_Q = "GA_Chaos071_Skill", "GA_Chaos071_UltraSkill"
CHAOS_MARK_BUFF = "Buff_Chaos_DddHuntMark"                        # applies 「追缉许可」
CHAOS_E_DAMAGE, CHAOS_Q_DAMAGE = "GE_Player_Chaos_Skill1_Damage", "GE_Player_Chaos_UltraSkill1_Damage"
CHAOS_RES_BUFF = "Buff_Chaos_LevelEX_DmgResistDown"               # 공명6 (coefficient −1 × curve)
LINKO_Q, LINKO_E = "GA_Radio072_UltraSkill", "GA_Radio072_Skill"
LINKO_COATTACK = "GA_Radio072_QTE_BackToLTE"                      # 「同频合击」 (the axis places GE_..._LTE_Damage)
LINKO_COATTACK_GE_PREFIX = "GE_Player_Radio072_LTE"
LINKO_LEVEL4_GE = "GE_Player_Radio072_UltralSkillLTE_AOE_Level4_Damage"
LINKO_DOMAIN_BUFF = "Buff_PlayerRadio072_UltraDelayDelete"       # domain after the overload (base)
LINKO_DOMAIN_BUFF_R6 = "Buff_PlayerRadio072_UltraDelayDelete_Extra2"
LINKO_COATTACK_CONTEXT = "linko_coattack:"                        # the engine's own E6 requirement context
CHIICHAN_COIN_GES = ("GE_Player_Chiichan073_Skill1_CoinDamage", "GE_Player_Chiichan073_Skill2_CoinDamage")
# matching tolerance (not a game value): the co-attack Linko's E calls lands 0.82 s after the E action on the axis
LINKO_E_COATTACK_WITHIN_US = 3_000_000

_US = 1_000_000


# ── static DB readers (prepare hooks; the connection is read-only) ──────────

def _curve(con, table: str, curve_id: str) -> float | None:
    row = con.execute(
        "SELECT value FROM combat_curve_point WHERE curve_id=? AND curve_table_asset_path LIKE ? "
        "ORDER BY source_time, ordinal LIMIT 1", (curve_id, "%/" + table)).fetchone()
    return None if row is None else float(row[0])


def _modifier(con, asset: str, prop: str):
    """(coefficient, source tags) of one buff / GE modifier (``magnitude_value`` multiplies the curve)."""
    row = con.execute(
        "SELECT magnitude_value, source_require_tags_json FROM buff_modifier WHERE asset_path LIKE ? AND property_id=? "
        "ORDER BY ordinal LIMIT 1", ("%/" + asset, prop)).fetchone()
    if row is None:
        return None, ()
    try:
        tags = tuple(json.loads(row[1] or "[]"))
    except (TypeError, ValueError):
        tags = ()
    return (None if row[0] is None else float(row[0])), tags


def _buff_seconds(con, asset: str, table: str | None = None) -> float | None:
    """A buff's HasDuration magnitude: a plain value, or ``Value`` × the named curve row."""
    row = con.execute("SELECT duration_magnitude_json FROM buff_definition WHERE asset_path LIKE ?",
                      ("%/" + asset,)).fetchone()
    if row is None or not row[0]:
        return None
    try:
        mag = json.loads(row[0]).get("ScalableFloatMagnitude") or {}
    except (TypeError, ValueError):
        return None
    value = mag.get("Value")
    curve = (mag.get("Curve") or {}).get("RowName")
    if curve and table:
        point = _curve(con, table, curve)
        return None if point is None or value is None else float(value) * point
    return None if value is None else float(value)


def _montage_lead_us(con, ability: str, before: str, after: str) -> int | None:
    """µs between the montage event that applies ``before`` and the first event that applies ``after`` (the
    ability's default montage; combat_ability_effect_binding + combat_montage_notify)."""
    montage = con.execute(
        "SELECT montage_asset_path FROM combat_ability_montage_binding WHERE ability_asset_path LIKE ? "
        "AND selector_key <> 'DissolveMontage' ORDER BY ordinal LIMIT 1", ("%/" + ability,)).fetchone()
    if montage is None:
        return None

    def first(effect: str) -> float | None:
        row = con.execute(
            "SELECT MIN(n.start_seconds) FROM combat_ability_effect_binding b JOIN combat_montage_notify n "
            "ON n.event_tag = b.event_tag AND n.asset_path = ? WHERE b.ability_asset_path LIKE ? AND b.effect_id = ?",
            (montage[0], "%/" + ability, effect)).fetchone()
        return None if row is None or row[0] is None else float(row[0])

    t_before, t_after = first(before), first(after)
    if t_before is None or t_after is None or t_after < t_before:
        return None
    return int(round((t_after - t_before) * _US))


def _ge_exists(con, ge: str) -> bool:
    return con.execute("SELECT 1 FROM skill_damage WHERE damage_id=? LIMIT 1", (ge,)).fetchone() is not None


# ── interval helpers (active clock = team_fork_corrections, time stops excluded) ──

def _tfc():
    from src.services import team_fork_corrections as tfc

    return tfc


def _windows(analysis, starts) -> list:
    """[(wall start, seconds)] -> merged refresh windows [(start, end)] on the active clock (a start inside a window
    refreshes it), capped at the battle end."""
    tfc = _tfc()
    end_cap = int(analysis.battle_end_us)
    wins: list[list[int]] = []
    for s, sec in sorted(starts):
        e = min(end_cap, tfc.active_window_end(analysis, int(s), float(sec)))
        if wins and s <= wins[-1][1]:
            wins[-1][1] = max(wins[-1][1], e)
        elif e > s:
            wins.append([int(s), int(e)])
    return [(a, b) for a, b in wins if b > a]


def _interval(cid: int, node: str, key: str, index: int, start: int, end: int, prop: str, value: float, *,
              scope: str = "self", tags: tuple = (), req: str = "", target_id: str = "", source: int | None = None,
              basis: str = ""):
    from src.domain.battle_report import BattleBuffModifierEvidence, BattleInferredBuffInterval

    owner = int(source if source is not None else cid)
    return BattleInferredBuffInterval(
        interval_id=f"global:awaken:{cid}:{key}:{owner}:{index}", buff_asset_path=f"global-awakening:{cid}:{key}",
        buff_name=f"{NAME_PREFIX}{cid} {node} {key}", source_effect_definition_id=f"global_awakening:{cid}:{node}",
        source_kind=SOURCE_KIND, source_character_id=owner, source_character_name="", target_scope=scope,
        start_us=int(start), end_us=int(end), stacks=1, duration_policy="HasDuration",
        state_confidence=SUPPLEMENT_CONFIDENCE, value_confidence=SUPPLEMENT_CONFIDENCE,
        inference_basis=basis or "Global awakening rule g3 (description + DB values)",
        trigger_event_type="GLOBAL_SUPPLEMENT", evidence_action_ids=(), evidence_event_ids=(), target_id=target_id,
        modifiers=(BattleBuffModifierEvidence(
            property_id=prop, modifier_operation="EGameplayModOp::Additive", magnitude_kind=SOURCE_KIND,
            magnitude_value=float(value), calculation_asset_path="", value_confidence=SUPPLEMENT_CONFIDENCE,
            application_requirement_asset_path=req, source_require_tags=tuple(tags)),))


def _engine_priced(analysis, cid: int, node: str) -> bool:
    """The engine already produced a valued interval for this node (then the rule stays out: no double count)."""
    sid = f"character_awaken:{cid}:{node}"
    return any(str(iv.source_effect_definition_id or "") == sid
               and any(m.magnitude_value is not None for m in iv.modifiers)
               for iv in analysis.buff_intervals or ())


def _apply(analysis, extra: list, replace: dict | None = None):
    """New analysis: ``replace`` {interval id: interval} in both interval lists, ``extra`` appended to both."""
    replace = replace or {}
    if not extra and not replace:
        return analysis

    def edit(seq) -> tuple:
        return tuple(replace.get(iv.interval_id, iv) for iv in seq or ())

    return dataclasses.replace(analysis, buff_intervals=edit(analysis.buff_intervals) + tuple(extra),
                               timeline_buff_intervals=edit(analysis.timeline_buff_intervals) + tuple(extra))


def _fill(analysis, cid: int, node: str, values: dict, *, scope: str | None = None, req: str | None = None,
          basis: str = "") -> dict:
    """{interval id: filled interval} for the engine's unpriced ``character_awaken:<cid>:<node>`` intervals:
    ``values`` {property: value} (other properties dropped), optional scope / application requirement."""
    sid = f"character_awaken:{cid}:{node}"
    out = {}
    for iv in analysis.buff_intervals or ():
        if str(iv.source_effect_definition_id or "") != sid or not iv.modifiers:
            continue
        if any(m.magnitude_value is not None for m in iv.modifiers):
            continue                                    # the engine priced it: leave it
        mods = tuple(dataclasses.replace(
            m, magnitude_value=float(values[m.property_id]), magnitude_kind=SOURCE_KIND,
            value_confidence=SUPPLEMENT_CONFIDENCE,
            application_requirement_asset_path=m.application_requirement_asset_path if req is None else req)
            for m in iv.modifiers if values.get(m.property_id) is not None)
        if not mods:
            continue
        changes = {"modifiers": mods, "source_kind": SOURCE_KIND,
                   "inference_basis": basis or "Global awakening rule g3: value filled from the DB curve"}
        if scope is not None:
            changes["target_scope"] = scope
        out[iv.interval_id] = dataclasses.replace(iv, **changes)
    return out


def _outgoing(hit) -> bool:
    return getattr(hit, "direction", "outgoing") == "outgoing"


def _q_stops(layout, cid: int, ability: str) -> list:
    """The layout's time stops owned by ``cid``'s ``ability`` (approved and custom layouts keep them in step)."""
    stops, owners = list(getattr(layout, "stops", ()) or ()), list(getattr(layout, "stop_owners", ()) or ())
    return [(int(s), int(e)) for (s, e), owner in zip(stops, owners)
            if owner and int(owner[0]) == int(cid) and str(owner[1]) == ability]


# ── 1070 海月 (Mitsuki): 「华彩」 ─────────────────────────────────────────────

_MITSUKI_NODES = ("Effect1", "Effect2", "Effect3", "resonance_6")


@RULES.hook("prepare", MITSUKI, nodes=_MITSUKI_NODES)
def _mitsuki_prepare(ctx):
    con, table = ctx.con, "DT_MitsukiEffectFigure"
    _coef, ult_tags = _modifier(con, MITSUKI_ULT_DMG_BUFF, "DamageUpGeneralBase")
    return {"cadenza_s": _curve(con, table, "Mitsuki_SkillBuffDur"),
            "lead_us": _montage_lead_us(con, MITSUKI_E, MITSUKI_CADENZA_BUFF, MITSUKI_E_DAMAGE),
            "crit": _curve(con, table, "Mitsuki_Star1_CritUp"),
            "extend_s": _curve(con, table, "Mitsuki_Star2_Dur"),
            "ult_dmg": _curve(con, table, "Mitsuki_Star3_DmgUp"), "ult_tags": ult_tags,
            "psyche": _curve(con, table, "Mitsuki_Star6extra_DmgUp"),
            "psyche_s": _curve(con, table, "Mitsuki_Star6exra_DmgUpDur")}


def mitsuki_events(analysis, data: dict, with_effect2: bool) -> list:
    """「华彩」 events [(wall time, kind)]: 'E' = each E (montage lead before its damage hit: the E hit is inside),
    'X' = with ② each support-skill (QTE) entry and each perfect-evade action of 1070."""
    lead = int(data.get("lead_us") or 0)
    events = [(int(h.relative_time_us) - lead, "E") for h in analysis.hits
              if h.character_id == MITSUKI and _outgoing(h) and h.gameplay_effect_id == MITSUKI_E_DAMAGE]
    if with_effect2:
        events += [(int(a.start_us), "X") for a in analysis.inferred_actions
                   if a.character_id == MITSUKI and (a.input_kind == "QTE" or "PerfectEvade" in str(a.action_name))]
    return sorted(set(events))


def mitsuki_cadenza(analysis, events: list, full_s: float, extend_s: float | None) -> list:
    """「华彩」 windows [(start, end)]: an E sets the remaining time to ``full_s``; an 'X' event (②) opens a
    ``extend_s`` window or extends the running one by ``extend_s`` (remaining time capped at ``full_s``)."""
    tfc = _tfc()
    end_cap = int(analysis.battle_end_us)
    wins: list[list[int]] = []
    for t, kind in events:
        inside = bool(wins) and t <= wins[-1][1]
        if kind == "E":
            e = min(end_cap, tfc.active_window_end(analysis, t, full_s))
            if inside:
                wins[-1][1] = max(wins[-1][1], e)
            elif e > t:
                wins.append([t, e])
        elif extend_s:
            if inside:
                cur = wins[-1][1]
                longer = tfc.wall_end_us(analysis, tfc.active_us(analysis, cur) + int(round(extend_s * _US)))
                cap = tfc.active_window_end(analysis, t, full_s)
                wins[-1][1] = min(end_cap, max(cur, min(longer, cap)))
            else:
                e = min(end_cap, tfc.active_window_end(analysis, t, extend_s))
                if e > t:
                    wins.append([t, e])
    return [(a, b) for a, b in wins if b > a]


@RULES.hook("intervals", MITSUKI, nodes=_MITSUKI_NODES)
def _mitsuki_intervals(ctx, run, analysis):
    data, member = ctx.data or {}, ctx.member
    if not data.get("cadenza_s") or data.get("lead_us") is None:
        return analysis
    e2 = member.has("Effect2") and data.get("extend_s")
    events = mitsuki_events(analysis, data, bool(e2))
    if not events:
        return analysis
    cadenza = mitsuki_cadenza(analysis, events, data["cadenza_s"], data.get("extend_s") if e2 else None)
    out = []
    if member.has("Effect1") and data.get("crit") and not _engine_priced(analysis, MITSUKI, "Effect1"):
        out += [_interval(MITSUKI, "Effect1", "E1", i, s, e, "CritBase", data["crit"])
                for i, (s, e) in enumerate(cadenza)]
    if member.has("Effect3") and data.get("ult_dmg") and not _engine_priced(analysis, MITSUKI, "Effect3"):
        out += [_interval(MITSUKI, "Effect3", "E3", i, s, e, "DamageUpGeneralBase", data["ult_dmg"],
                          tags=tuple(data.get("ult_tags") or ("State.Damage.UltraSkill",)))
                for i, (s, e) in enumerate(cadenza)]
    if (member.has("resonance_6") and data.get("psyche") and data.get("psyche_s")
            and not _engine_priced(analysis, MITSUKI, "resonance_6")):
        wins = _windows(analysis, [(t, data["psyche_s"]) for t, _kind in events])
        out += [_interval(MITSUKI, "resonance_6", "R6", i, s, e, "DamageUpPsycheBase", data["psyche"], scope="team")
                for i, (s, e) in enumerate(wins)]
    return _apply(analysis, out)


# ── 1071 卡厄斯 (Chaos): 「追缉许可」 ──────────────────────────────────────────

_CHAOS_NODES = ("Effect2", "Effect3", "Effect5", "resonance_6")


@RULES.hook("prepare", CHAOS, nodes=_CHAOS_NODES)
def _chaos_prepare(ctx):
    con, table = ctx.con, "DT_ChaosEffectFigure"
    res_coef, _tags = _modifier(con, CHAOS_RES_BUFF, "DamageResistLakshanaBase")
    res = _curve(con, table, "Chaos_StarExtra2ResDown")
    return {"mark_e_s": _curve(con, table, "Chaos_HuntMark_Duration"),
            "mark_q_s": _curve(con, table, "Chaos_UltraskillHuntMarkDuration"),
            "lead_e_us": _montage_lead_us(con, CHAOS_E, CHAOS_MARK_BUFF, CHAOS_E_DAMAGE),
            "lead_q_us": _montage_lead_us(con, CHAOS_Q, CHAOS_MARK_BUFF, CHAOS_Q_DAMAGE),
            "def_ignore": _curve(con, table, "Chaos_Star2DefIgnore"),
            "crit_dmg": _curve(con, table, "Chaos_Star3CritDamageUp"),
            "crit_dmg_s": _curve(con, table, "Chaos_Star3Duration"),
            "dmg": _curve(con, table, "Chaos_Star5DamageUp"),
            "res": None if res is None or res_coef is None else res_coef * res}


def chaos_marks(analysis, data: dict) -> dict:
    """{target id: mark windows}: each Chaos E / Q marks its target at the montage notify that applies
    Buff_Chaos_DddHuntMark (before the cast's first damage hit, so that hit is marked); 15 s active, refresh."""
    hits = sorted((h for h in analysis.hits if h.character_id == CHAOS and _outgoing(h)),
                  key=lambda h: h.relative_time_us)
    starts: dict[str, set] = {}
    for a in analysis.inferred_actions:
        if a.character_id != CHAOS or a.input_kind not in ("E", "Q"):
            continue
        ge, lead, sec = ((CHAOS_E_DAMAGE, data.get("lead_e_us"), data.get("mark_e_s")) if a.input_kind == "E"
                         else (CHAOS_Q_DAMAGE, data.get("lead_q_us"), data.get("mark_q_s")))
        if lead is None or not sec:
            continue
        first = next((h for h in hits if h.gameplay_effect_id == ge and a.start_us <= h.relative_time_us <= a.end_us),
                     None)
        if first is not None:
            starts.setdefault(str(first.target_id or ""), set()).add((int(first.relative_time_us) - int(lead), sec))
    return {target: _windows(analysis, sorted(s)) for target, s in starts.items()}


@RULES.hook("intervals", CHAOS, nodes=_CHAOS_NODES)
def _chaos_intervals(ctx, run, analysis):
    data, member = ctx.data or {}, ctx.member
    out = []
    marks = chaos_marks(analysis, data) if any(member.has(n) for n in ("Effect2", "Effect5", "resonance_6")) else {}
    for target, wins in sorted(marks.items()):
        req = f"battle-hit-target|id={target}"
        tag = target or "target"
        if member.has("Effect2") and data.get("def_ignore") and not _engine_priced(analysis, CHAOS, "Effect2"):
            out += [_interval(CHAOS, "Effect2", f"E2:{tag}", i, s, e, "DefIgnore", data["def_ignore"], req=req)
                    for i, (s, e) in enumerate(wins)]
        # ⑤ "only one marked target left": every mark window of a single-target run (the simulator's dummy)
        if (member.has("Effect5") and data.get("dmg") and len(marks) == 1
                and not _engine_priced(analysis, CHAOS, "Effect5")):
            out += [_interval(CHAOS, "Effect5", f"E5:{tag}", i, s, e, "DamageUpGeneralBase", data["dmg"], req=req)
                    for i, (s, e) in enumerate(wins)]
        if member.has("resonance_6") and data.get("res") and not _engine_priced(analysis, CHAOS, "resonance_6"):
            out += [_interval(CHAOS, "resonance_6", f"R6:{tag}", i, s, e, "DamageResistLakshanaBase", data["res"],
                              scope="target", target_id=target)
                    for i, (s, e) in enumerate(wins)]
    if member.has("Effect3") and data.get("crit_dmg") and data.get("crit_dmg_s") \
            and not _engine_priced(analysis, CHAOS, "Effect3"):
        q = sorted({int(a.start_us) for a in analysis.inferred_actions
                    if a.character_id == CHAOS and a.input_kind == "Q"})      # one Q may be inferred twice
        wins = _windows(analysis, [(s, data["crit_dmg_s"]) for s in q])
        out += [_interval(CHAOS, "Effect3", "E3", i, s, e, "CritDamageBase", data["crit_dmg"])
                for i, (s, e) in enumerate(wins)]
    return _apply(analysis, out)


# ── 1072 灵可 (Linko): domain, co-attacks ───────────────────────────────────

_LINKO_NODES = ("Effect4", "Effect5", "Effect6", "resonance_6")


@RULES.hook("prepare", LINKO, nodes=_LINKO_NODES)
def _linko_prepare(ctx):
    con, table = ctx.con, "DT_LinkoEffectFigure"
    return {"domain_s": _buff_seconds(con, LINKO_DOMAIN_BUFF),
            "domain_r6_s": _buff_seconds(con, LINKO_DOMAIN_BUFF_R6, table),
            "level4_ge": LINKO_LEVEL4_GE if _ge_exists(con, LINKO_LEVEL4_GE) else None,
            "coattack_dmg": _curve(con, table, "LinkoLevel3_DamageUpGeneralBase"),
            "coattack_crit": _curve(con, table, "LinkoLevel6_CritBase"),
            "nature": _curve(con, table, "LinkoLevel_Extra2_Ling"),
            "incantation": _curve(con, table, "LinkoLevel_Extra2_Zhou")}


def _linko_domain_s(member, data: dict):
    return data.get("domain_r6_s") if member.has("resonance_6") else data.get("domain_s")


def linko_domains_axis(run, seconds) -> list:
    """Resonance-domain windows on the layout clock (before the engine): [Linko Q stop start, + ``seconds`` of
    active time] — the simulator keeps the whole overload inside the Q stop, so this is 'overload end + n s'."""
    from src.services.battle_timeline_time_service import (
        ACTIVE_TIME_MODE,
        project_timeline_time_us,
        unproject_timeline_time_us,
    )

    stops = tuple((int(s), int(e)) for s, e in getattr(run.layout, "stops", ()) or ())
    end = int(run.layout.end_us)
    wins = []
    for s, _e in _q_stops(run.layout, LINKO, LINKO_Q):
        a = project_timeline_time_us(s - 1, battle_start_us=0, intervals=stops, mode=ACTIVE_TIME_MODE)
        b = unproject_timeline_time_us(int(a) + int(round(float(seconds) * _US)), battle_start_us=0,
                                       battle_end_us=end, intervals=stops, mode=ACTIVE_TIME_MODE,
                                       prefer_interval_end=True)
        if wins and s - 1 <= wins[-1][1]:
            wins[-1][1] = max(wins[-1][1], min(end, int(b)))
        else:
            wins.append([s - 1, min(end, int(b))])
    return [(a, b) for a, b in wins if b > a]


@RULES.hook("rows", LINKO, nodes=("Effect4",))
def _linko_level4_rows(ctx, run):
    """④: one Level4 AOE hit (Q skill level) 1 µs after every Linko co-attack hit inside the domain."""
    data = ctx.data or {}
    seconds = _linko_domain_s(ctx.member, data)
    if not data.get("level4_ge") or not seconds:
        return []
    domains = linko_domains_axis(run, seconds)
    out = []
    for r in run.layout.rows:
        if (int(r.get("character_id") or 0) != LINKO or r.get("ability_name") != LINKO_COATTACK
                or not str(r.get("gameplay_effect_name") or "").startswith(LINKO_COATTACK_GE_PREFIX)):
            continue
        t = int(r["relative_time_us"])
        if any(a <= t <= b for a, b in domains):
            out.append(run.row(LINKO, t + 1, LINKO_Q, data["level4_ge"], str(r.get("damage_attribute") or "nature")))
    return out


def linko_e_coattacks(analysis) -> list:
    """The co-attack hit each Linko E calls: the first co-attack hit of 1072 at most 3 s after the E action end."""
    hits = sorted((h for h in analysis.hits if h.character_id == LINKO and _outgoing(h)
                   and h.ability_id == LINKO_COATTACK), key=lambda h: h.relative_time_us)
    out = []
    for a in sorted(analysis.inferred_actions, key=lambda a: a.start_us):
        if a.character_id != LINKO or a.action_name != LINKO_E:
            continue
        first = next((h for h in hits if 0 <= h.relative_time_us - a.end_us <= LINKO_E_COATTACK_WITHIN_US), None)
        if first is not None and first not in out:
            out.append(first)
    return out


def linko_partner_reacts(run) -> bool:
    """Team rule of ⑤: the E's partner = the approved cycle's choice (the main damage dealer, ``_carry``); True when
    its element can react (环合) with Linko's.  Solo / Linko as the carry: 小贞 (Linko's own element) never reacts."""
    from src.services import team_cycle_reactions as tcr
    from src.services.team_simulation_service import _carry

    team = [int(c) for c in run.team_ids]
    if len(team) < 2:
        return False
    partner, _why = _carry(team)
    if partner is None or int(partner) == LINKO:
        return False
    elements = dict(getattr(run.ctx, "elements", {}) or {})
    return tcr.is_adjacent(str(elements.get(int(partner)) or ""), str(elements.get(LINKO) or ""))


def _linko_engine_e6(analysis) -> bool:
    """The engine's own ⑥ interval reaches a hit only through a 'linko_coattack:' formula context."""
    return _engine_priced(analysis, LINKO, "Effect6") and any(
        str(getattr(h, "formula_context_kind", "") or "").startswith(LINKO_COATTACK_CONTEXT) for h in analysis.hits)


@RULES.hook("intervals", LINKO, nodes=("Effect5", "Effect6", "resonance_6"))
def _linko_intervals(ctx, run, analysis):
    data, member = ctx.data or {}, ctx.member
    out = []
    coattack_req = f"battle-passive|ability-prefix-any={LINKO_COATTACK}"
    qstops = _q_stops(run.layout, LINKO, LINKO_Q)
    if member.has("resonance_6") and not _engine_priced(analysis, LINKO, "resonance_6") \
            and data.get("domain_r6_s"):
        wins = _windows(analysis, [(s - 1, data["domain_r6_s"]) for s, _e in qstops])
        for i, (s, e) in enumerate(wins):
            if data.get("nature"):
                out.append(_interval(LINKO, "resonance_6", "R6n", i, s, e, "DamageUpNatureBase", data["nature"],
                                     scope="team"))
            if data.get("incantation"):
                out.append(_interval(LINKO, "resonance_6", "R6i", i, s, e, "DamageUpIncantationBase",
                                     data["incantation"], scope="team"))
    if member.has("Effect6") and data.get("coattack_crit") and not _linko_engine_e6(analysis):
        # (1) the co-attack GEs carry the crit themselves (Con_Radio072_isAwake_CritUp): any time, solo and team
        out.append(_interval(LINKO, "Effect6", "E6", 0, 0, int(analysis.battle_end_us), "CritBase",
                             data["coattack_crit"], req=coattack_req))
        # (2) team: inside the domain a teammate's support-skill hits count as co-attacks (Buff_Radio072_CritUp)
        seconds = _linko_domain_s(member, data)
        if seconds:
            domains = _windows(analysis, [(s - 1, seconds) for s, _e in qstops])
            for mate in sorted(int(c) for c in run.team_ids if int(c) != LINKO):
                out += [_interval(LINKO, "Effect6", "E6qte", i, s, e, "CritBase", data["coattack_crit"],
                                  tags=("State.Damage.QTE",), source=mate)
                        for i, (s, e) in enumerate(domains)]
    if member.has("Effect5") and data.get("coattack_dmg") and not _engine_priced(analysis, LINKO, "Effect5") \
            and not linko_partner_reacts(run):
        out += [_interval(LINKO, "Effect5", "E5", i, int(h.relative_time_us), int(h.relative_time_us) + 1,
                          "DamageUpGeneralBase", data["coattack_dmg"], req=coattack_req)
                for i, h in enumerate(linko_e_coattacks(analysis))]
    return _apply(analysis, out)


# ── 1073 小吱 (Chiichan): ⑥ value fill ──────────────────────────────────────

@RULES.hook("prepare", CHIICHAN, nodes=("Effect6",))
def _chiichan_prepare(ctx):
    return {"coin": _curve(ctx.con, "DT_ChiichanEffectFigure", "Chiichan_Coin_DmgUP")}


@RULES.hook("intervals", CHIICHAN, nodes=("Effect6",))
def _chiichan_intervals(ctx, run, analysis):
    value = (ctx.data or {}).get("coin")
    if not value:
        return analysis
    filled = _fill(analysis, CHIICHAN, "Effect6", {"DamageUpGeneralBase": value},
                   req="battle-passive|ge-prefix-any=" + ",".join(CHIICHAN_COIN_GES),
                   basis="Global awakening rule g3: Chiichan_Coin_DmgUP added to the damage-bonus pool of the 金谷 hits")
    return _apply(analysis, [], filled)


# ── 1075 伊洛伊 (Iloi): resonance fills ───────────────────────────────────────

@RULES.hook("prepare", ILOI, nodes=("resonance_3", "resonance_6"))
def _iloi_prepare(ctx):
    table = "DT_OneiroiEffectFigure"
    return {"def": _curve(ctx.con, table, "Oneiroi_Awaken2_DefUP"),
            "crit_dmg": _curve(ctx.con, table, "Buff_Oneiroi075_Level6_extra")}


@RULES.hook("intervals", ILOI, nodes=("resonance_3", "resonance_6"))
def _iloi_intervals(ctx, run, analysis):
    data, member = ctx.data or {}, ctx.member
    filled = {}
    if member.has("resonance_3") and data.get("def"):
        filled.update(_fill(analysis, ILOI, "resonance_3", {"DefUp": data["def"]}, scope="team",
                            basis="Global awakening rule g3: party DEF +30 % while Iloi is in the team (Infinite)"))
    if member.has("resonance_6") and data.get("crit_dmg"):
        filled.update(_fill(analysis, ILOI, "resonance_6", {"CritDamageBase": data["crit_dmg"]}, scope="team",
                            basis="Global awakening rule g3: party crit damage while Iloi is in the team"))
    return _apply(analysis, [], filled)


# ── node metadata (all 48 nodes of the group) ────────────────────────────────

def _node(cid, node, category, bucket, confidence="high", *, scope="", assumption=None, reason=None):
    RULES.node(cid, node, category=category, bucket=bucket, confidence=confidence, scope=scope,
               assumption=assumption, reason=reason)


_DONE_KO = "이미 계산되고 있음을 확인했습니다."

# 1070 海月
_node(MITSUKI, "Effect1", "damage", "now", "medium", scope="solo_team", assumption=(
    "「화채」는 게임 데이터대로 E 피해 판정보다 약 6ms 먼저 걸리므로 E 타격부터 포함해 전투 시간(시간 정지 제외)으로 "
    "12초 유지된다고 가정합니다(E 타격을 빼면 이 칸이 약 0.8%p 작아집니다)."))
_node(MITSUKI, "Effect2", "team", "now", "medium", scope="team_only", assumption=(
    "서포트 스킬을 시작하는 순간 「화채」가 5초 켜지고(켜져 있으면 5초 연장, 남은 시간 최대 12초) E를 쓰면 다시 12초로 "
    "채워진다고 가정하며, 1인 검수 사이클에는 서포트 스킬·극한 회피가 없어 1인 효과는 0입니다."))
_node(MITSUKI, "Effect3", "damage", "now", "medium", scope="solo_team", assumption=(
    "돌파 효과 ①과 같은 「화채」 시간창을 쓰고, 피해 증가는 울티메이트 타격에만 붙는다고 가정합니다."))
_node(MITSUKI, "Effect4", "none", "not_computable", reason={
    "ko": "방어력 증가는 피해 계산에 쓰이지 않습니다(피해 무관).",
    "zh": "防御力提升不参与伤害计算（与伤害无关）。",
    "en": "A DEF increase does not enter the damage formula (no damage effect).",
    "ja": "防御力アップはダメージ計算に使われません（ダメージに無関係）。"})
_node(MITSUKI, "Effect5", "damage", "now", scope="solo_team", assumption=(
    "이미 계산되고 있으며 울티메이트 타격에만 붙는 것을 엔진 코드로 확인했습니다."))
_node(MITSUKI, "Effect6", "damage", "now", scope="solo_team", assumption=(
    "E 직후 10층 부분은 이미 계산되고, 20층 상한은 해파리탄(검수 사이클에 없음)이 있을 때만 의미가 있습니다."))
_node(MITSUKI, "resonance_3", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(MITSUKI, "resonance_6", "damage", "now", "medium", scope="solo_team", assumption=(
    "「화채」에 들어가는 순간(E 피해 판정 약 6ms 전, 그래서 E 타격 포함)부터 15초 동안 파티 전원의 혼속성 피해가 8% 오르고 "
    "다시 들어가면 15초로 갱신된다고 가정합니다."))

# 1071 卡厄斯
_node(CHAOS, "Effect1", "unmodelled", "measure", reason={
    "ko": "「죄목」 자원과 그에 따른 추가 「재단」 2단을 계산기가 아직 추적하지 않아 '측정 필요'입니다.",
    "zh": "计算器尚未追踪「罪状」资源及其带来的额外第二段攻击，暂未计入。",
    "en": "The calculator does not track Chaos's Crimes resource or the extra second-stage attacks it allows yet, so "
          "this is unmeasured.",
    "ja": "「罪状」リソースとそれによる追加の2段目攻撃をまだ計算機が追跡していないため、未反映です。"})
_node(CHAOS, "Effect2", "damage", "now", "medium", scope="solo_team", assumption=(
    "「추적 허가」는 게임 데이터의 몽타주 시점대로 E 첫 타격 약 15ms 전, 울티메이트 시작 2.7초 뒤(첫 타격 약 0.1초 전)에 "
    "붙어 전투 시간 15초 유지되고(다시 붙으면 갱신) 단일 목각인형에 항상 붙는다고 가정합니다."))
_node(CHAOS, "Effect3", "damage", "now", scope="solo_team", assumption=(
    "치명타 피해 증가는 울티메이트 시전 순간부터 전투 시간 20초 동안 유지된다고 가정합니다."))
_node(CHAOS, "Effect4", "none", "not_computable", reason={
    "ko": "대상은 처치되지 않는 단일 목각인형이라 표식 전이가 일어나지 않습니다(피해 무관).",
    "zh": "目标为不会被击败的单个木桩，标记不会传递（与伤害无关）。",
    "en": "The target is a single dummy that is never defeated, so the mark never transfers (no damage effect).",
    "ja": "対象は倒されない単体の木人なので、マークの移動は起きません（ダメージに無関係）。"})
_node(CHAOS, "Effect5", "damage", "now", "medium", scope="solo_team", assumption=(
    "대상(단일 목각인형)이 표식 상태면 '표식 대상 1명' 조건이 항상 참이라고 가정합니다."))
_node(CHAOS, "Effect6", "rotation", "measure", "medium", reason={
    "ko": "「죄목」 즉시 보충은 사이클 자체를 바꾸는 효과라 숫자 대신 '측정 필요'로 표시하며, 검수 사이클이 이 "
          "효과를 전제로 하는지는 게임에서 확인해야 합니다.",
    "zh": "「罪状」立即补满会改变循环本身，因此标为“需要实测”；已审核循环是否以此为前提需在游戏中确认。",
    "en": "Refilling Crimes at once changes the rotation itself, so it is marked as unmeasured; whether the reviewed "
          "rotation already assumes it must be checked in game.",
    "ja": "「罪状」の即時補充はサイクル自体を変えるため「要実測」と表示します。審査済みサイクルがこれを前提にしている"
          "かはゲーム内で確認が必要です。"})
_node(CHAOS, "resonance_3", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(CHAOS, "resonance_6", "damage", "now", "medium", scope="solo_team", assumption=(
    "저항 감소는 「추적 허가」와 같은 시간창(E 첫 타격 직전·울티메이트 시작 2.7초 뒤부터 15초, 갱신 가능) 동안만 "
    "유지된다고 가정합니다."))

# 1072 灵可
_node(LINKO, "Effect1", "team", "measure", reason={
    "ko": "링코가 후방에 있을 때의 소정 공격과 표식이 계산기에 아직 없어 미반영입니다(팀 효과).",
    "zh": "灵可在后台时的小贞攻击与标记尚未模拟，暂未计入（队伍效果）。",
    "en": "Xiaozhen's attacks and marks while Linko is off-field are not simulated yet, so this team effect is not "
          "priced.",
    "ja": "リンコが控えにいる間の小貞の攻撃とマークはまだ計算機にないため、未反映です（チーム効果）。"})
_node(LINKO, "Effect2", "rotation", "measure", reason={
    "ko": "울티메이트 폭발 피해 타격이 검수 사이클에서 아직 '시뮬 안 함' 단계라, 그 단계를 검수해 넣기 전까지 미반영입니다.",
    "zh": "终结技的爆发伤害在已审核循环中仍是“未模拟”步骤，审核加入前暂未计入。",
    "en": "The ultimate's burst hit is still an unsimulated step of the reviewed rotation; it is not priced until that "
          "step is reviewed and placed.",
    "ja": "アルティメットの爆発ダメージは審査済みサイクルでまだ「未シミュレート」の段階のため、その段階を審査して入れ"
          "るまで未反映です。"})
_node(LINKO, "Effect3", "resource", "now", scope="team_only", assumption=(
    "쿨타임(자원) 계산에서 이미 반영되며 1인 검수 사이클의 DPS는 바꾸지 않습니다."))
_node(LINKO, "Effect4", "damage", "now", "medium", scope="solo_team", assumption=(
    "모든 동기화 협공(울티메이트 영역 안 3회 + E 협동 공격 1회)에 추가타가 1회씩 붙고, 기본 영역 추가타와는 별개로 "
    "더해지며, 이 추가타가 다시 표식을 깨서 생기는 연쇄 협동 공격은 없다고 가정합니다."))
_node(LINKO, "Effect5", "damage", "now", "medium", scope="solo_team", assumption=(
    "E로 부른 협동 공격 1회(1인은 소정, 팀은 메인 딜러)의 대상이 링코와 사이클 반응을 일으킬 수 없으면 피해 +50%가 "
    "붙는다고 가정하며, 1인 시뮬레이션은 소정의 협동 공격을 팀원 협동 공격 공식(LTE_Damage)으로 대신 놓고 있어 이 "
    "값은 그 근사 위에서 계산됩니다."))
_node(LINKO, "Effect6", "damage", "now", "medium", scope="solo_team", assumption=(
    "협동 공격 효과 자체에 붙은 치명타 확률 +25%는 1인(소정의 협동 공격 포함)·팀 모두 항상 적용되고, 영역 안에서 "
    "팀원이 서포트 스킬로 들어오면 그 타격에도 +25%가 붙는다고 가정하며, 팀원 충전 효과는 양이 데이터에 없어 "
    "미반영으로 둡니다."))
_node(LINKO, "resonance_3", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(LINKO, "resonance_6", "damage", "now", "medium", scope="solo_team", assumption=(
    "게임 데이터대로 과부하 시작부터 과부하 종료 후 13초까지 효과가 있고, 계산기는 과부하를 울티메이트 시간 정지(11초) 안에 "
    "두므로 '울티메이트 시작부터 전투 시간 13초'와 같다고 가정합니다(실제 과부하가 정지 밖으로 길어지면 그만큼 더 깁니다)."))

# 1073 小吱
_COIN = {
    "zh": "计算器尚未模拟「金谷」资源（金谷追加伤害按固定倍率计算），暂未计入。",
    "en": "The Golden Grain (coin) resource is not simulated yet (coin hits use a fixed multiplier), so this is "
          "unmeasured.",
    "ja": "「金谷」リソースはまだ計算機にありません（金谷の追加ダメージは固定倍率で計算）。そのため未反映です。"}
_node(CHIICHAN, "Effect1", "unmodelled", "measure", reason={
    "ko": "「금곡」 자원이 계산기에 없고 금곡 추가 피해가 고정 배율로 계산되므로 미반영입니다.", **_COIN})
_node(CHIICHAN, "Effect2", "unmodelled", "measure", reason={
    "ko": "「금곡」 이자는 금곡 자원 모델이 생긴 뒤에 계산할 수 있어 미반영입니다.", **_COIN})
_node(CHIICHAN, "Effect3", "unmodelled", "measure", reason={
    "ko": "「금곡 시세」는 확률 시장이라 기대값 모델과 금곡 자원 모델이 모두 필요해 미반영입니다.", **_COIN})
_node(CHIICHAN, "Effect4", "unmodelled", "measure", reason={
    "ko": "금곡 획득량이 피해로 바뀌는 식이 확인되지 않아 미반영입니다.", **_COIN})
_node(CHIICHAN, "Effect5", "unmodelled", "measure", reason={
    "ko": "전투 진입 시 금곡 가득은 금곡 자원 모델이 있어야 계산할 수 있어 미반영입니다.", **_COIN})
_node(CHIICHAN, "Effect6", "damage", "now", "medium", scope="solo_team", assumption=(
    "커스텀 계산(Calc_ChiiChan_SkillDamUp)이 금곡 추가 피해(CoinDamage) 타격에만 피해 증가 +15%p를 기존 피해 증가 "
    "합계에 더한다고 가정합니다(별도 ×1.15 곱이라면 이 칸은 +0.74%가 아니라 약 +1.5%입니다; 커브 행 이름은 게임 "
    "데이터에 없어 Chiichan_Coin_DmgUP=0.15로 봅니다)."))
_node(CHIICHAN, "resonance_3", "unmodelled", "measure", reason={
    "ko": "치즈의 공명3은 스킬 레벨이 아니라 「금곡」 획득 효율 효과라 금곡 자원 모델 전에는 미반영입니다.", **_COIN})
_node(CHIICHAN, "resonance_6", "damage", "now", scope="solo_team", assumption=_DONE_KO)

# 1075 伊洛伊
_node(ILOI, "Effect1", "rotation", "measure", "medium", reason={
    "ko": "검수 사이클의 첫 울티메이트(상아의 문)가 입장 시 「망상」 가득(이 효과)을 전제로 할 수 있어, 게임에서 "
          "확인하기 전까지 '측정 필요'로 표시합니다.",
    "zh": "已审核循环的首个终结技（象牙之门）可能以入场时「臆想」全满（本效果）为前提，游戏内确认前标为“需要实测”。",
    "en": "The reviewed rotation's first ultimate (Ivory Gate) may assume a full Reverie bar on entry (this effect); "
          "it is marked as unmeasured until checked in game.",
    "ja": "審査済みサイクルの最初のアルティメット（象牙の門）が入場時の「臆想」満タン（この効果）を前提にしている可能"
          "性があり、ゲーム内で確認するまで「要実測」と表示します。"})
_node(ILOI, "Effect2", "team", "measure", "low", assumption={
    "ko": "팀원의 E(그리고 확인되면 울티메이트·서포트 스킬)마다 5초에 한 번 일로이 공격력 200%의 영속성 피해가 난다고 "
          "가정하지만, 타격 데이터가 없어 게임에서 확인한 뒤에 넣습니다.",
    "zh": "假设队友每次释放技能（E；若确认则含终结技与援护技）时，每5秒最多一次造成伊洛伊攻击力200%的灵属性伤害；"
          "该攻击没有命中数据，需在游戏中确认后再计入。",
    "en": "Assumes each teammate skill (E; ultimate and support skill if confirmed) triggers one nature hit of 200 % of "
          "Iloi's ATK, at most once per 5 s; the hit has no data, so it is added only after an in-game check.",
    "ja": "チームメイトのスキル（E、確認できればアルティメット・支援スキルも）ごとに5秒に1回、イロイの攻撃力200%の霊"
          "属性ダメージが発生すると仮定しますが、ヒットデータがないためゲーム内で確認してから反映します。"})
_node(ILOI, "Effect3", "none", "not_computable", reason={
    "ko": "치료량은 피해와 무관합니다.",
    "zh": "治疗量与伤害无关。",
    "en": "Healing does not change damage.",
    "ja": "回復量はダメージに無関係です。"})
_node(ILOI, "Effect4", "team", "measure", reason={
    "ko": "검수 사이클은 E 탭이라 「퇴행」 상태가 생기지 않아 미반영입니다(팀·사이클 변형 필요).",
    "zh": "已审核循环为短按 E，不会产生「退行」状态，暂未计入（需队伍或循环变体）。",
    "en": "The reviewed rotation taps E, so the Regression state never occurs; unmeasured (needs a team or rotation "
          "variant).",
    "ja": "審査済みサイクルはEタップのため「退行」状態が発生せず、未反映です（チーム・サイクル変形が必要）。"})
_node(ILOI, "Effect5", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(ILOI, "Effect6", "none", "not_computable", reason={
    "ko": "시뮬레이션에서는 아무도 쓰러지지 않으므로 부활 보너스는 피해와 무관합니다.",
    "zh": "模拟中没有角色倒下，复活加成与伤害无关。",
    "en": "Nobody is knocked out in the simulation, so the revive bonus has no damage effect.",
    "ja": "シミュレーションでは誰も倒れないため、復活ボーナスはダメージに無関係です。"})
_node(ILOI, "resonance_3", "damage", "now", scope="solo_team", assumption=(
    "스킬 레벨 +1은 이미 계산되고, 파티 방어력 +30%는 일로이가 파티에 있는 동안 상시이며 방어력 비례 피해(현재 아들러)에만 "
    "영향을 준다고 가정합니다."))
_node(ILOI, "resonance_6", "damage", "now", scope="solo_team", assumption=(
    "파티 치명타 피해 +25%는 일로이가 파티에 있으면 상시이고, 「퇴행」 팀원 보너스는 검수 사이클에 퇴행이 없어 0으로 둡니다."))

# 1076 真红
_node(SHINKU, "Effect1", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(SHINKU, "Effect2", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(SHINKU, "Effect3", "team", "measure", reason={
    "ko": "「위압적 응시」 추가 피해 타격이 아직 시뮬레이션 타임라인에 없어서, 그 기본 타격을 넣기 전까지 '측정 "
          "필요'입니다(팀 효과).",
    "zh": "「威压凝视」的追加伤害命中尚未放入时间轴，加入该基础命中前暂未计入（队伍效果）。",
    "en": "The extra hit of the base kit's gaze is not in the simulation timeline yet, so this team effect is "
          "unmeasured until it is added.",
    "ja": "「威圧の凝視」の追加ダメージがまだタイムラインにないため、その基本ヒットを入れるまで未反映です（チーム効果）。"})
_node(SHINKU, "Effect4", "unmodelled", "measure", reason={
    "ko": "16층은 17초 이상 공격하지 않거나 후방 축적(돌파 효과 ③)이 있어야 닿으므로 1인 검수 사이클에서는 0이고, 기본 응시 "
          "타격을 넣기 전까지 미반영입니다.",
    "zh": "16层需17秒以上不攻击或后台累积（觉醒效果③）才能达到，单人已审核循环中为0；加入基础凝视命中前暂未计入。",
    "en": "16 stacks need 17 s without attacking or off-field build-up (Awakening Effect ③), so the solo rotation never "
          "reaches them; not priced until the base gaze hit is added.",
    "ja": "16層は17秒以上攻撃しないか控えでの蓄積（覚醒効果③）が必要で、単独の審査済みサイクルでは0です。基本の凝視ヒットを"
          "入れるまで未反映です。"})
_node(SHINKU, "Effect5", "none", "not_computable", reason={
    "ko": "생존 효과라 피해와 무관합니다.",
    "zh": "生存类效果，与伤害无关。",
    "en": "A survival effect with no damage effect.",
    "ja": "生存系の効果でダメージに無関係です。"})
_node(SHINKU, "Effect6", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(SHINKU, "resonance_3", "damage", "now", scope="solo_team", assumption=_DONE_KO)
_node(SHINKU, "resonance_6", "damage", "now", scope="solo_team", assumption=_DONE_KO)
