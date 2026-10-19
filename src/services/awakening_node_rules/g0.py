# 队伍模拟：觉醒（돌파）效果规则——角色组 g0（早雾 安魂曲 翳 娜娜莉 薄荷 哈尼娅）。只在本文件登记本组角色的规则。
"""Awakening-node rules of group g0: characters 1003, 1004, 1008, 1010, 1019, 1020.

Edit only this file (see the package docstring for the recipe and core for the hook kinds).  Specs: work_g231
``awaken/specs/group_0.json`` (reviewed numbers, ``group_0_review.md``); user decisions 2026-10-18 (free node sets,
Lacrimosa ③ = settlement reading A, conditions the simulator cannot reproduce = expected value, low-confidence nodes
show their assumption sentence, unpriced nodes are marked, never 0 %).  Every number comes from the static DB
(``prepare``: curve rows / buff stack limits, read only); the only constant is the measured damage ratio of Mint ⑥'s
expected value.

=========  =========================================================================================================
1003 早雾   ⑤ long-press E (selector Skill2) that floats the dummy clears the Q cooldown (``e_resets_q`` rule row:
           reviewed layouts and custom cycles; not against a boss).  共鸣6 +3 % damage per known target debuff, cap 12 %: Q suppression (3 s, 6 s with ①), passive-2
           DEF down (20 s), teammates' target debuffs, DoT / reaction states; a debuff counts from the hit after the one
           that applied it (intervals, after the other hooks).
1004 安魂曲 ③ reading A: at each 5th-basic settlement every live nightmare layer pays all its remaining ticks at once
           and is removed (dot_rows: the nightmare ticks of the cleared stack - its 1 s grid stops at a settlement
           and restarts 1 s after the next application, so settled layers drive no tick effect; post: each tick
           re-priced from the engine's layer count to the cleared count, the remaining ticks x the per-layer value).
           ⑥ swap into Lacrimosa from a 黯星 / 浊燃 partner within 5 s after her E: support entry without the gauge,
           ICD 5 s (placed + free_support).
1008 翳     ② crit +10 % for 15 s from each E.  ③ +4 % +4 % (single locked target) and 共鸣6 lakshana resistance
           -2 % x 3 fangs on the target while the fangs are locked: from the last hit of the E's 6-hit round to the end
           of 尾追 (6 s, 12 s with ④).  ⑥ skill coefficient x1.2 on the 啮逐潜影 contact extra attacks (evidence).
1010 娜娜莉 ③ one extra hit (GE_Nanally010_Lv3_Damage) per Nanally hit in 一代目 (12 s, 15 s with ⑥; ends on swap /
           E re-press), ICD 1 s (rows).  ⑤ ATK +2 % per follow-up, 10 stacks, until swap-out (intervals).  ① +2.5
           energy per follow-up, ICD 1 s (display only: the Q cost is unknown; placed).
1019 薄荷   ② +40 % damage bonus on E hits.  ③ (team fix) ATK +15 % for 15 s from each 创生 / 覆纹 trigger.  ④ crit
           +12 % after her first hit (single enemy).  ⑥ expected value +15 % x share of time below 40 % HP.  共鸣6 +2
           Cycle gauge per E (placed).
1020 哈尼娅 ③ crit +20 %, ⑤ psyche damage +30 % (cut at her swap-out) and 共鸣6 team crit damage +12 % inside the
           超异科王牌 window (the engine's GA_Haniel_UltraSkill interval).
=========  =========================================================================================================

Nodes the engine already prices (resonance 3 skill levels, Lacrimosa ①②④共鸣6, Sagiri ④, Mint ①⑤, Haniel ②⑥,
Nanally 共鸣6) have no hook; their NodeInfo carries the efficiency class.  Nodes that need a base-kit hit the simulator
does not place (Skia ①, Nanally ②④, Haniel ①④) or a value that is in no data (Sagiri ②) are ``measure``; nodes
without a damage effect on the dummy are ``not_computable``.
"""
from __future__ import annotations

import dataclasses

from src.services.awakening_node_rules.core import (
    NAME_PREFIX,
    SOURCE_KIND,
    SUPPLEMENT_CONFIDENCE,
    PostIncrement,
    RuleSet,
)

RULES = RuleSet("g0", (1003, 1004, 1008, 1010, 1019, 1020))

SAGIRI, LACRIMOSA, SKIA, NANALLY, MINT, HANIEL = 1003, 1004, 1008, 1010, 1019, 1020
PERIOD_US = 1_000_000                       # DoT tick grid (team_simulation_service.DOT_TICK_S)

# Mint ⑥: k = damage ratio of Mint's hits with +15 % on every hit (engine runs, review R3: 1.0776 at A0, 1.0731 at A6).
# The share of TIME below 40 % HP is f = (t / k) / (1 - t + t / k) (t = the HP threshold, a DB value); the expected
# bonus is bonus x f (+5.74 %), equal to the kill-time DPS ratio 1 / (1 - t + t / k) within 0.01 %.
MINT_E6_DAMAGE_RATIO = 1.0753

# DB curve rows (combat_curve_point) per character: key -> curve id
_CURVES = {
    SAGIRI: {"suppress_s": "Sagiri_Suppress", "suppress_e1_s": "Sagiri_lv1_Suppress",
             "def_down_s": "Sagiri_Pas1_DefUpAddDur", "r6_per_debuff": "Sagiri_lvExtra_Damup",
             "r6_cap": "Sagiri_lvExtra_DamupMax"},
    LACRIMOSA: {"e6_window_s": "Lacrimosa_Lv1TriggerReactionDur", "e6_icd_s": "Lacrimosa_Lv1CD"},
    SKIA: {"e2_crit": "Skia_Leve2CritBase", "e2_s": "Skia_Leve2Duaration",
           "e3_locked": "Skia_Leve3DamageUpGeneralBase1", "e3_single": "Skia_Leve3DamageUpGeneralBase2",
           "tail_s": "Skia_ShadowControlDuaration", "tail_e4_s": "Skia_ShadowControlDuaration_Level4",
           "r6_per_fang": "Skia_LevelExtraDamageResistLakshanaBase", "e6_coef": "Skia_Leve6CoefModify"},
    NANALLY: {"e3_icd_s": "Nanally_Lv3CD", "walk_s": "Nanally_WalkDur", "walk_e6_s": "Nanally_Lv6_BattleWalkDur",
              "e5_atk": "Nanally_Lv5_AtkUp", "e1_energy": "Nanally_Pas2Charge", "e1_icd_s": "Nanally_Pas2CD"},
    MINT: {"e2_bonus": "Mint_Adcance_2_1", "e3_atk": "Mint_Adcance_3_1", "e3_s": "Mint_Adcance_3_2",
           "e4_crit": "Mint_Adcance_4_1", "e6_threshold": "Mint_Adcance_6_1", "e6_bonus": "Mint_Adcance_6_2",
           "r6_gauge": "Mint_Adcance_6_AddEnergy"},
    HANIEL: {"e3_crit": "Haniel_Level3_CritAdd", "e5_psyche": "Haniel_Level5_DamageUpPsycheBase",
             "r6_crit_damage": "Haniel_LevelEtra_CritDamageUp"},
}
# buff stack limits (buff_definition.stack_limit_count)
_STACKS = {SKIA: {"r6_fangs": "Buff_Skia008_LevelExtra_1"}, NANALLY: {"e5_stacks": "Buff_Nanally010_Lv5_AtkUp"}}

# game ids the rules look for (team_rotation_data / skill_damage)
SAGIRI_E, SAGIRI_FLOAT_SELECTOR = "GA_Sagiri_Skill", "Skill2"
SAGIRI_FLOAT_GE = "ge_player_sagiri_skill4_damage"
LACRIMOSA_E = "GA_Lacrimosa_Skill"
LACRIMOSA_E6_REACTIONS = ("黯星", "浊燃", "失谐")
SKIA_E = "GA_Skia_Skill"
SKIA_CONTACT = "ge_player_skia_skillshadowatk_damage"
NANALLY_E = "GA_Nanally_Skill"
NANALLY_E3_GE = "GE_Nanally010_Lv3_Damage"
MINT_E = "GA_Mint019_Skill"
MINT_E3_REACTIONS = ("创生", "覆纹")
HANIEL_Q_WINDOW = "character_skill:1020:GA_Haniel_UltraSkill"

_DATA_KEY = "g0"


# ── data (prepare) ───────────────────────────────────────────────────────────

def _curve(con, curve_id: str) -> float | None:
    row = con.execute("SELECT value FROM combat_curve_point WHERE curve_id=? ORDER BY ordinal LIMIT 1",
                      (curve_id,)).fetchone()
    return None if row is None or row[0] is None else float(row[0])


def _stack_limit(con, definition_id: str) -> int | None:
    row = con.execute("SELECT stack_limit_count FROM buff_definition WHERE definition_id=?",
                      (definition_id,)).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def load_data(con, character_id: int) -> dict | None:
    """The DB values a character's rules use (None when one is missing: the rules then change nothing)."""
    cid = int(character_id)
    out: dict = {}
    for key, curve_id in (_CURVES.get(cid) or {}).items():
        value = _curve(con, curve_id)
        if value is None:
            return None
        out[key] = value
    for key, definition_id in (_STACKS.get(cid) or {}).items():
        value = _stack_limit(con, definition_id)
        if value is None:
            return None
        out[key] = value
    return out


def _prepare(ctx):
    return load_data(ctx.con, ctx.character_id)


for _cid in RULES.characters:       # base kit: the DB values of every member (read once per context)
    RULES.hook("prepare", _cid, name=f"g0_data_{_cid}")(_prepare)


# ── shared helpers ───────────────────────────────────────────────────────────

def _interval(cid: int, node: str, index: int, start: int, end: int, prop: str, value: float, *,
              scope: str = "self", tags: tuple = (), target_id: str = "", part: str = ""):
    """A Global awakening buff interval (supplement, 中 confidence; ``target`` scope needs the hit's target id)."""
    from src.domain.battle_report import BattleBuffModifierEvidence, BattleInferredBuffInterval

    code = f"{node}{':' + part if part else ''}"
    return BattleInferredBuffInterval(
        interval_id=f"global:awakening:{cid}:{code}:{index}", buff_asset_path=f"global-awakening:{cid}:{code}",
        buff_name=f"{NAME_PREFIX}{cid} {code}", source_effect_definition_id=f"global_awakening:{cid}:{code}",
        source_kind=SOURCE_KIND, source_character_id=int(cid), source_character_name="", target_scope=scope,
        start_us=int(start), end_us=int(end), stacks=1, duration_policy="HasDuration",
        state_confidence=SUPPLEMENT_CONFIDENCE, value_confidence=SUPPLEMENT_CONFIDENCE,
        inference_basis="Global awakening supplement (description + DB parameters, group g0)",
        trigger_event_type="GLOBAL_SUPPLEMENT", evidence_action_ids=(), evidence_event_ids=(), target_id=target_id,
        modifiers=(BattleBuffModifierEvidence(
            property_id=prop, modifier_operation="EGameplayModOp::Additive", magnitude_kind=SOURCE_KIND,
            magnitude_value=float(value), calculation_asset_path="", value_confidence=SUPPLEMENT_CONFIDENCE,
            source_require_tags=tuple(tags)),))


def _replace(analysis, drop: set, add: list):
    """The analysis without the engine intervals of ``drop`` (source effect ids), plus ``add`` (new objects)."""
    if not drop and not add:
        return analysis
    keep = tuple(x for x in analysis.buff_intervals if x.source_effect_definition_id not in drop)
    keep_t = tuple(x for x in analysis.timeline_buff_intervals if x.source_effect_definition_id not in drop)
    return dataclasses.replace(analysis, buff_intervals=keep + tuple(add), timeline_buff_intervals=keep_t + tuple(add))


def _window_end(analysis, start_us: int, seconds: float) -> int:
    from src.services.team_fork_corrections import active_window_end

    return min(int(analysis.battle_end_us), active_window_end(analysis, int(start_us), float(seconds)))


def _windows(analysis, starts, seconds: float) -> list:
    """Windows of ``seconds`` active time from each start; a start inside a window extends it (refresh)."""
    out: list = []
    for s in sorted(int(x) for x in starts):
        e = _window_end(analysis, s, seconds)
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        elif e > s:
            out.append([s, e])
    return out


def _visits(run, cid: int) -> list:
    return [(int(v.start_us), int(v.end_us)) for v in run.layout.visits if int(v.character_id) == int(cid)]


def _clip_to_visit(run, cid: int, start: int, end: int) -> int:
    for vs, ve in _visits(run, cid):
        if vs <= start < ve:
            return min(int(end), ve)
    return int(end)


def _hits(analysis, cid: int) -> list:
    return [h for h in analysis.hits if int(h.character_id) == int(cid)]


def _target_id(analysis, cid: int) -> str:
    return next((str(h.target_id) for h in analysis.hits if int(h.character_id) == int(cid)), "")


# ── 1003 早雾 ────────────────────────────────────────────────────────────────

# ⑤ 失觉性的崩落: a long-press E (Skill2) that floats the target clears the Q cooldown at once (the float fails on a
# boss; the energy refill is not tracked - Sagiri's cost is unknown).  A data row, so the custom walker runs it too.
RULES.resource_rule(SAGIRI, ("e_resets_q", "Q", {"selectors": (SAGIRI_FLOAT_SELECTOR,), "not_on_boss": True}, 5,
                             "db_text", "text 1003:Effect5 (失觉性的崩落): a floating long-press E clears the Q cooldown"))
# Mint ① 特遣行动: the counter -> E reset has an internal cooldown (DB curve, 3 s)
RULES.resource_rule(MINT, ("reset_icd", "counter_resets_e", "curve:Mint_Adcance_1_1_CD", None, "db_value",
                           "data:DT_MintEffectFigure.Mint_Adcance_1_1_CD (internal cooldown of the 1019:Effect1 reset)"))


def _tick_presence(run, cid_exclude: int) -> list:
    """(key, start, end) presence windows of the DoT states on the target from their tick rows (a state lives from
    1 s before each tick to the tick) - members other than ``cid_exclude``."""
    out = []
    for row in run.dot_rows or ():
        label = str(row.get("damage_component") or "")
        if not label or int(row["character_id"]) == int(cid_exclude):
            continue
        t = int(row["relative_time_us"])
        start = int(run.to_wall(max(0, int(run.to_active(t)) - PERIOD_US)))
        out.append((f"dot:{label}", start, t))
    return out


def _reaction_presence(run, analysis) -> list:
    """(key, start, end) of the reaction states on the target: 覆纹 / 浸染 / 延滞 windows and 浊燃 ticks."""
    out = []
    sched = run.sched
    if sched is None:
        return out
    try:
        for w in sched.windows(("覆纹", "浸染", "延滞")):
            out.append((f"reaction:{w.reaction_zh}", int(w.start_us), int(w.end_us)))
    except Exception:
        pass
    try:
        origins = sched.event_origins()
    except Exception:
        origins = {}
    for h in analysis.hits:
        origin = origins.get(h.event_id)
        if origin is not None and str(getattr(origin, "kind", "")) == "reaction:浊燃":
            t = int(h.relative_time_us)
            out.append(("reaction:浊燃", int(run.to_wall(max(0, int(run.to_active(t)) - PERIOD_US))), t))
    return out


@RULES.hook("intervals", SAGIRI, nodes=("resonance_6",), order=10, name="sagiri_r6_debuff_count")
def _sagiri_r6(ctx, run, analysis):
    """共鸣6 薄雾通彻: +3 % per distinct known debuff on the target (cap 12 %), as piecewise-constant segments; the
    engine's interval (magnitude None, Cau_Sagiri_LevelExtra) is replaced.  Runs after the other intervals hooks so
    teammates' Global target debuffs count too."""
    data = ctx.data
    if not data:
        return analysis
    hits = _hits(analysis, SAGIRI)
    q_first = []
    for a in analysis.inferred_actions:
        if int(a.character_id) == SAGIRI and a.input_kind == "Q":
            qh = sorted(int(h.relative_time_us) for h in hits if a.start_us <= h.relative_time_us <= a.end_us)
            if qh:
                q_first.append(qh[0])
    floats = [int(h.relative_time_us) for h in hits if h.gameplay_effect_id.casefold() == SAGIRI_FLOAT_GE]
    boss = bool((getattr(run.ctx, "target_condition", None) or {}).get("boss"))
    keyed: list = []
    if not boss:     # the suppression does not hold on bosses (description)
        seconds = data["suppress_e1_s"] if ctx.member.has("Effect1") else data["suppress_s"]
        keyed += [("sagiri:suppress", s, e) for s, e in _windows(analysis, [t + 1 for t in q_first], seconds)]
    keyed += [("sagiri:def_down", s, e)
              for s, e in _windows(analysis, sorted(t + 1 for t in floats + q_first), data["def_down_s"])]
    for x in analysis.buff_intervals:       # teammates' debuffs on the target (engine and Global supplements)
        if x.target_scope == "target" and int(x.source_character_id) != SAGIRI and x.end_us > x.start_us:
            keyed.append((f"buff:{x.source_character_id}:{x.buff_asset_path}", int(x.start_us), int(x.end_us)))
    keyed += _tick_presence(run, SAGIRI) + _reaction_presence(run, analysis)
    end = int(analysis.battle_end_us)
    edges = sorted({0, end} | {min(max(0, int(v)), end) for _k, s, e in keyed for v in (s, e)})
    segments: list = []                     # [start, end, value], equal neighbours merged
    for a, b in zip(edges, edges[1:]):
        if b <= a:
            continue
        mid = (a + b) // 2
        n = len({k for k, s, e in keyed if s <= mid < e})
        value = min(data["r6_cap"], data["r6_per_debuff"] * n) if n else 0.0
        if segments and segments[-1][1] == a and segments[-1][2] == value:
            segments[-1][1] = b
        else:
            segments.append([a, b, value])
    add = [_interval(SAGIRI, "resonance_6", i, s, e, "DamageUpGeneralBase", v)
           for i, (s, e, v) in enumerate(x for x in segments if x[2] > 0)]
    return _replace(analysis, {"character_awaken:1003:resonance_6"}, add)


# ── 1004 安魂曲 ──────────────────────────────────────────────────────────────

def lacrimosa_settlement(adds: list, settles: list, layer_us: int, end_active: int, limit: int = 10) -> dict:
    """Reading A of ③ on the active clock (pure; ``adds`` / ``settles`` = active µs of the application hits and the
    settlement hits).  The stack is the cleared one: each settlement removes every layer (the settlement hit adds its
    own layer first, as the engine), the stack's 1 s tick grid stops there and restarts 1 s after the next
    application (the simulator's rule for an emptied stack, ``_dot_tick_rows``; review N-F1).  Returns ``grid`` (the
    tick times while at least one layer lives, up to ``end_active``), ``count(g)`` (layers alive at ``g``),
    ``remaining`` [(settle, ticks)] (the grid points every live layer would still have ticked, the grid continued past
    the run end) and ``windows`` (each settlement + 0.5 s; no grid point falls inside one, because the next tick comes
    1 s after a later application)."""
    from src.services.team_simulation_service import NIGHTMARE_SETTLE_WINDOW_US

    layer_us = int(layer_us)
    events = sorted([(int(t), 0) for t in adds] + [(int(t), 1) for t in settles])
    grid: list = []
    remaining: list = []
    alive: list = []
    nxt = None
    i = 0
    while True:
        t_ev = events[i][0] if i < len(events) else None
        lim = end_active if t_ev is None else t_ev
        while nxt is not None and nxt <= lim and nxt <= end_active:
            if any(e > nxt for e in alive):
                grid.append(nxt)
                nxt += PERIOD_US
            else:
                nxt = None
        if t_ev is None:
            break
        t, kind = events[i]
        i += 1
        alive = [e for e in alive if e > t]
        if kind == 0:
            if len(alive) < limit:
                alive.append(t + layer_us)
            if nxt is None and alive:
                nxt = t + PERIOD_US
            continue
        n = 0
        for e in alive:
            g = nxt
            while g is not None and g < e:
                if g > t:
                    n += 1
                g += PERIOD_US
        remaining.append((t, n))
        alive = []
        nxt = None

    def count(at: int) -> int:
        live: list = []
        for t, kind in events:
            if t > at:
                break
            live = [e for e in live if e > t]
            if kind == 0:
                if len(live) < limit:
                    live.append(t + layer_us)
            else:
                live = []
        return sum(1 for e in live if e > at)

    windows = [(int(t), int(t) + NIGHTMARE_SETTLE_WINDOW_US) for t in settles]
    return {"grid": grid, "count": count, "remaining": remaining, "windows": windows}


def _lacrimosa_model(run):
    """(nightmare setup, settlement wall times, lacrimosa_settlement model) of one run, None without a settlement."""
    nightmare = getattr(run.ctx, "nightmare", None)
    applications = run.applications or {}
    settle_walls = [int(t) for t, _op, _n in applications.get("nightmare_settle", ())]
    if not nightmare or not settle_walls:
        return None
    to_active, end_us = run.to_active, int(run.layout.end_us)
    adds = [int(to_active(t)) for t, op, _n in applications.get("nightmare", ()) if op == "add"]
    settles = [int(to_active(t)) for t in settle_walls]
    model = lacrimosa_settlement(adds, settles, int(round(float(nightmare[1]) * 1e6)), int(to_active(end_us)))
    return nightmare, settle_walls, settles, model


@RULES.hook("dot_rows", LACRIMOSA, nodes=("Effect3",), name="lacrimosa_e3_cleared_ticks")
def _lacrimosa_e3_rows(ctx, run, dot_rows):
    """③ reading A on the axis (review N-F1): Lacrimosa's nightmare tick rows are rebuilt from the cleared stack
    (``lacrimosa_settlement``: a settlement removes every layer and stops the grid, which restarts 1 s after the next
    application).  A settled layer no longer ticks, so the tick-driven effects of its ticks (「最后一朵玫瑰」 stacks,
    Zankou's Scorch refresh in teams) go with it.  The other DoT rows are kept in place."""
    got = _lacrimosa_model(run)
    if got is None or LACRIMOSA not in run.names:
        return None
    nightmare, _walls, _settles, model = got
    from src.services.team_simulation_service import _DOT_LABELS, NIGHTMARE_GE, NIGHTMARE_GE_ENHANCED

    ge = str(nightmare[0])
    dmg = run.static.get_skill_damage(ge)
    if not dmg:
        return None
    ids = {NIGHTMARE_GE.casefold(), NIGHTMARE_GE_ENHANCED.casefold()}

    def is_nightmare(row) -> bool:
        return (int(row["character_id"]) == LACRIMOSA
                and str(row.get("gameplay_effect_name") or "").casefold() in ids)

    end_us = int(run.layout.end_us)
    attribute = str(dmg.get("damage_type") or "").lower()
    rows = []
    for g in model["grid"]:
        wall = int(run.to_wall(g))
        if wall <= end_us:
            rows.append(run.row(LACRIMOSA, wall, dmg.get("ability_id"), ge, attribute, _DOT_LABELS["nightmare"]))
    first = next((i for i, row in enumerate(dot_rows) if is_nightmare(row)), len(dot_rows))
    others = [row for row in dot_rows if not is_nightmare(row)]
    head = sum(1 for row in dot_rows[:first] if not is_nightmare(row))
    return others[:head] + rows + others[head:]


@RULES.hook("post", LACRIMOSA, nodes=("Effect3",), name="lacrimosa_e3_settlement")
def _lacrimosa_e3(ctx, run, pairs):
    """③ 冰淇淋在烈阳中融化, reading A (user decision 2026-10-18), settled after replay.

    The axis carries the cleared stack's ticks (``lacrimosa_e3_cleared_ticks``), while the engine still counts the
    layers as if nothing were settled.  Per-layer tick value = a tick's replayed damage / the engine's layer count.
    Increments: each tick re-priced from the engine's layer count to the cleared count; each settlement pays every
    live layer's remaining ticks (the grid continued past the run end) at the value of the nearest tick.  No tick
    falls inside a settlement window (the grid restarts 1 s after a later application).  Credited to Lacrimosa's
    visit at each time."""
    got = _lacrimosa_model(run)
    if got is None:
        return []
    _nightmare, settle_walls, settles, model = got
    from src.services.team_simulation_service import NIGHTMARE_GE, NIGHTMARE_GE_ENHANCED

    to_active = run.to_active
    count = model["count"]
    nightmare_ids = {NIGHTMARE_GE.casefold(), NIGHTMARE_GE_ENHANCED.casefold()}
    ticks, out = [], []
    for hit, replay in pairs:
        if (replay is None or int(hit.character_id) != LACRIMOSA
                or hit.gameplay_effect_id.casefold() not in nightmare_ids or not replay.expected_damage):
            continue
        wall = int(hit.relative_time_us)
        active = int(to_active(wall))
        engine = float(next((f.value for f in replay.factors if f.factor_id == "state_coefficient"), 1.0) or 1.0)
        per_layer = float(replay.expected_damage) / max(1.0, engine)
        ticks.append((active, per_layer))
        cleared = count(active)
        if abs(cleared - engine) > 1e-9:
            out.append(PostIncrement(LACRIMOSA, wall, (cleared - engine) * per_layer, "「噩梦」", "Effect3"))
    if not ticks:
        return out
    ticks.sort()

    def value_at(active: int) -> float:
        return min(ticks, key=lambda x: abs(x[0] - active))[1]

    for i, (_t, n) in enumerate(model["remaining"]):
        if n > 0:
            out.append(PostIncrement(LACRIMOSA, settle_walls[i], n * value_at(settles[i]), "「噩梦」提前结算",
                                     "Effect3"))
    return out


@RULES.hook("placed", LACRIMOSA, nodes=("Effect6",), name="lacrimosa_e6_track_e")
def _lacrimosa_e6_track(ctx, ev):
    """⑥: remember when Lacrimosa's E ends (the 5 s window of the free support entry) and the layout's stop list."""
    if ev.action and ev.action[0] == LACRIMOSA_E and ev.layout is not None:
        ev.layout.scratch[_DATA_KEY + ":lacrimosa_e"] = (int(ev.end_us), getattr(ev.writer, "stops", None))


@RULES.hook("free_support", LACRIMOSA, nodes=("Effect6",), name="lacrimosa_e6_free_support")
def _lacrimosa_e6(ctx, ev):
    """⑥ 早起出勤之咏: a swap into Lacrimosa from a member she reacts with by 黯星 / 浊燃 (失谐 = both) within 5 s of
    active time after her E needs no Cycle gauge and does not use it; once per 5 s."""
    data = ctx.data
    scratch = getattr(ev.layout, "scratch", None)
    if not data or scratch is None or getattr(ev.pair, "zh", "") not in LACRIMOSA_E6_REACTIONS:
        return False
    last_e = scratch.get(_DATA_KEY + ":lacrimosa_e")
    if last_e is None or last_e[0] > ev.t_us:
        return False
    from src.services.team_simulation_service import _active_between

    stops = last_e[1] or []
    if _active_between(stops, last_e[0], ev.t_us) > int(round(data["e6_window_s"] * 1e6)):
        return False
    previous = scratch.get(_DATA_KEY + ":lacrimosa_free")
    if previous is not None and _active_between(stops, previous, ev.t_us) < int(round(data["e6_icd_s"] * 1e6)):
        return False
    scratch[_DATA_KEY + ":lacrimosa_free"] = int(ev.t_us)
    return True


# ── 1008 翳 ──────────────────────────────────────────────────────────────────

def skia_lock_windows(analysis, tail_s: float) -> list:
    """[start, end] of the fangs' lock: from the last hit of each E's 6-hit damage round (+1 µs, before the first
    contact extra attack) to the end of 尾追 (E start + ``tail_s`` active)."""
    starts = [int(a.start_us) for a in analysis.inferred_actions if int(a.character_id) == SKIA and a.input_kind == "E"]
    hits = _hits(analysis, SKIA)
    rounds = sorted(int(h.relative_time_us) for h in hits
                    if str(h.ability_id) == SKIA_E and SKIA_CONTACT not in h.gameplay_effect_id.casefold())
    contacts = sorted(int(h.relative_time_us) for h in hits if SKIA_CONTACT in h.gameplay_effect_id.casefold())
    out = []
    for s0, e0 in _windows(analysis, starts, tail_s):
        first_contact = next((t for t in contacts if s0 <= t < e0), None)
        rnd = [t for t in rounds if s0 <= t < e0 and (first_contact is None or t < first_contact)]
        lock = (max(rnd) + 1) if rnd else (first_contact if first_contact is not None else s0)
        if lock < e0:
            out.append([lock, e0])
    return out


@RULES.hook("intervals", SKIA, nodes=("Effect2", "Effect3", "Effect4", "resonance_6"), name="skia_windows")
def _skia(ctx, run, analysis):
    """② crit +10 % for 15 s from each E (a re-cast refreshes).  ③ +4 % (locked) +4 % (the only locked target) and
    共鸣6 lakshana resistance -2 % x 3 fangs on the target, both inside the lock windows (④: 尾追 12 s instead of 6 s);
    the engine's ③ interval (Con_Skia_Level3_*, unresolved) is replaced."""
    data = ctx.data
    if not data:
        return analysis
    member = ctx.member
    add, drop = [], set()
    if member.has("Effect2"):
        starts = [int(a.start_us) for a in analysis.inferred_actions
                  if int(a.character_id) == SKIA and a.input_kind == "E"]
        for i, (s, e) in enumerate(_windows(analysis, starts, data["e2_s"])):
            add.append(_interval(SKIA, "Effect2", i, s, e, "CritBase", data["e2_crit"]))
    if member.has("Effect3") or member.has("resonance_6"):
        lock = skia_lock_windows(analysis, data["tail_e4_s"] if member.has("Effect4") else data["tail_s"])
        if member.has("Effect3"):
            drop.add("character_awaken:1008:Effect3")
            for i, (s, e) in enumerate(lock):
                add.append(_interval(SKIA, "Effect3", i, s, e, "DamageUpGeneralBase",
                                     data["e3_locked"] + data["e3_single"]))
        if member.has("resonance_6"):
            target = _target_id(analysis, SKIA)
            for i, (s, e) in enumerate(lock):
                add.append(_interval(SKIA, "resonance_6", i, s, e, "DamageResistLakshanaAdd",
                                     data["r6_per_fang"] * data["r6_fangs"], scope="target", target_id=target))
    return _replace(analysis, drop, add)


@RULES.hook("evidence", SKIA, nodes=("Effect6",), name="skia_e6_contact_coefficient")
def _skia_e6(ctx, run, evidence):
    """⑥ 无谓形貌的立身: the 啮逐潜影 contact extra attacks (GE_Player_Skia_SkillShadowAtk_Damage, all from contact)
    get skill coefficient x (1 + CoefModify 0.2) - the DB puts the CoefModify on exactly this GE."""
    data = ctx.data
    if not data:
        return evidence
    factor = 1.0 + data["e6_coef"]
    return tuple(dataclasses.replace(e, multiplier_coefficient=e.multiplier_coefficient * factor)
                 if str(e.damage_id).casefold() == SKIA_CONTACT else e for e in evidence)


# ── 1010 娜娜莉 ──────────────────────────────────────────────────────────────

def nanally_windows(visits, walk_s: float, to_active, to_wall) -> list:
    """一代目的权柄 windows [start, end) (wall µs) of Nanally's visits: from each E step to min(+``walk_s`` active, the
    visit end); an E pressed while the state lives only ends it (no new window)."""
    out = []
    for v in visits:
        if int(v.character_id) != NANALLY:
            continue
        current = None
        for st in v.steps:
            if st.ability_id != NANALLY_E or st.status != "ok":
                continue
            if current is not None and int(st.start_us) < current[1]:
                current[1] = int(st.start_us)            # re-press: the state ends
                current = None
                continue
            end = min(int(to_wall(int(to_active(int(st.start_us))) + int(round(walk_s * 1e6)))), int(v.end_us))
            if end > int(st.start_us):
                current = [int(st.start_us), end]
                out.append(current)
            else:
                current = None
    return [tuple(w) for w in out]


def nanally_followups(run_or_layout, data: dict, has_e6: bool, to_active, to_wall) -> list:
    """Wall µs of Nanally's own hits that trigger ③'s extra hit (one per ICD on the active clock, inside 一代目)."""
    layout = getattr(run_or_layout, "layout", run_or_layout)
    windows = nanally_windows(layout.visits, data["walk_e6_s"] if has_e6 else data["walk_s"], to_active, to_wall)
    times = sorted(int(r["relative_time_us"]) for r in layout.rows if int(r["character_id"]) == NANALLY)
    icd = int(round(data["e3_icd_s"] * 1e6))
    out, last = [], None
    for ws, we in windows:
        for t in times:
            if not ws <= t < we:
                continue
            a = int(to_active(t))
            if last is not None and a - last < icd:
                continue
            last = a
            out.append(t)
    return out


@RULES.hook("rows", NANALLY, nodes=("Effect3", "Effect6"), name="nanally_e3_extra_hits")
def _nanally_e3(ctx, run):
    """③ 要叫大姐头: in 一代目 each Nanally hit adds one GE_Nanally010_Lv3_Damage hit 1 µs later (basic-attack skill
    level, nature), at most once per 1 s; ⑥ makes the state 15 s instead of 12 s.  Credited to Nanally's visit."""
    data = ctx.data
    if not data or not ctx.member.has("Effect3") or NANALLY not in run.names:
        return []
    dmg = run.static.get_skill_damage(NANALLY_E3_GE)
    if not dmg:
        return []
    from src.services.team_simulation_service import _row

    attribute = str(dmg.get("damage_type") or "").lower()
    name = run.names[NANALLY]
    return [_row(NANALLY, name, t + 1, dmg.get("ability_id"), NANALLY_E3_GE, attribute)
            for t in nanally_followups(run, data, ctx.member.has("Effect6"), run.to_active, run.to_wall)]


@RULES.hook("intervals", NANALLY, nodes=("Effect5",), name="nanally_e5_follow_up_stacks")
def _nanally_e5(ctx, run, analysis):
    """⑤ 小弟遍天下: ATK +2 % per follow-up (today the ③ extra hits), 10 stacks, lost at swap-out (no 15 s expiry:
    the description has none); counted from the hit after the follow-up (+1 µs)."""
    data = ctx.data
    if not data:
        return analysis
    follow = sorted(int(h.relative_time_us) for h in _hits(analysis, NANALLY)
                    if h.gameplay_effect_id.casefold() == NANALLY_E3_GE.casefold())
    segs, count, visit_end = [], 0, None
    for t in follow:
        ve = _clip_to_visit(run, NANALLY, t, int(analysis.battle_end_us))
        if visit_end is None or ve != visit_end:
            count, visit_end = 0, ve
        count = min(int(data["e5_stacks"]), count + 1)
        segs.append([t + 1, ve, count])
    for a, b in zip(segs, segs[1:]):
        if b[1] == a[1]:
            a[1] = min(a[1], b[0])
    add = [_interval(NANALLY, "Effect5", i, s, e, "AtkUp", data["e5_atk"] * c)
           for i, (s, e, c) in enumerate(segs) if e > s]
    return _replace(analysis, set(), add)


@RULES.hook("placed", NANALLY, nodes=("Effect1",), name="nanally_e1_follow_up_energy")
def _nanally_e1(ctx, ev):
    """① 帮派初建成: +2.5 ultimate energy per follow-up (today the ③ extra hits), at most once per 1 s.  Display only:
    Nanally's Q cost is unknown, so the energy never gates (reviewed resource levels; the custom walker keeps its own
    energy)."""
    data = ctx.data
    writer, layout = ev.writer, ev.layout
    if not data or writer is None or layout is None or not ctx.member.has("Effect3"):
        return
    from src.services.team_simulation_service import _active_between

    stops = getattr(writer, "stops", None) or []
    state = layout.scratch.setdefault(_DATA_KEY + ":nanally", {"window": None, "visit": None, "last": None,
                                                              "energy": None})
    walk_us = int(round((data["walk_e6_s"] if ctx.member.has("Effect6") else data["walk_s"]) * 1e6))
    if state["visit"] != ev.visit_index:          # the state ends at swap-out
        state["window"], state["visit"] = None, ev.visit_index
    if ev.action and ev.action[0] == NANALLY_E:
        window = state["window"]
        if window is not None and _active_between(stops, window, ev.start_us) < walk_us:
            state["window"] = None                 # re-press: the state ends
        else:
            state["window"] = int(ev.start_us)
    icd = int(round(data["e3_icd_s"] * 1e6))
    energy_icd = int(round(data["e1_icd_s"] * 1e6))
    for row in sorted(ev.rows, key=lambda r: r["relative_time_us"]):
        t = int(row["relative_time_us"])
        start = state["window"]
        if start is None or t < start or _active_between(stops, start, t) >= walk_us:
            continue
        if state["last"] is not None and _active_between(stops, state["last"], t) < icd:
            continue
        state["last"] = t
        if state["energy"] is None or _active_between(stops, state["energy"], t) >= energy_icd:
            state["energy"] = t
            ev.gain_energy(float(data["e1_energy"]), "follow_up", t)   # reviewed: ResourceState; custom: walker


# ── 1019 薄荷 ────────────────────────────────────────────────────────────────

def mint_e6_expected(threshold: float, bonus: float, ratio: float = MINT_E6_DAMAGE_RATIO) -> float:
    """⑥ expected value: ``bonus`` x the share of time below ``threshold`` HP (HP falls in proportion to damage, the
    damage there is ``ratio`` times higher)."""
    below = threshold / ratio
    return bonus * below / ((1.0 - threshold) + below)


@RULES.hook("intervals", MINT, nodes=("Effect2", "Effect3", "Effect4", "Effect6"), name="mint_buffs")
def _mint(ctx, run, analysis):
    """② +40 % damage bonus on her E hits (DamageUpGeneralBase, source tag State.Damage.Skill: Q and basic attacks
    excluded).  ③ ATK +15 % for 15 s from each 创生 / 覆纹 trigger, whoever fires it (replaces the engine's
    flower-hit windows: 覆纹 has no hit row and every flower refreshed the window).  ④ crit +12 % from just after her
    first hit to the end (one enemy).  ⑥ the expected value of +15 % below 40 % target HP, on all her hits."""
    data = ctx.data
    if not data:
        return analysis
    member = ctx.member
    end = int(analysis.battle_end_us)
    add, drop = [], set()
    if member.has("Effect2"):
        add.append(_interval(MINT, "Effect2", 0, 0, end, "DamageUpGeneralBase", data["e2_bonus"],
                             tags=("State.Damage.Skill",)))
    if member.has("Effect3"):
        drop.add("character_awaken:1019:Effect3")
        triggers = [int(t) for _i, t, zh, _o, _n in (run.sched.triggers if run.sched is not None else ())
                    if zh in MINT_E3_REACTIONS]
        for i, (s, e) in enumerate(_windows(analysis, triggers, data["e3_s"])):
            add.append(_interval(MINT, "Effect3", i, s, e, "AtkUp", data["e3_atk"]))
    single = int((getattr(run.ctx, "target_condition", None) or {}).get("enemy_count") or 1) <= 1
    if member.has("Effect4"):
        drop.add("character_awaken:1019:Effect4")
        first = min((int(h.relative_time_us) for h in _hits(analysis, MINT)), default=None)
        if first is not None and first + 1 < end and single:      # ④ needs exactly one enemy (custom: enemy count)
            add.append(_interval(MINT, "Effect4", 0, first + 1, end, "CritBase", data["e4_crit"]))
    if member.has("Effect6"):
        drop.add("character_awaken:1019:Effect6")
        add.append(_interval(MINT, "Effect6", 0, 0, end, "DamageUpGeneralBase",
                             mint_e6_expected(data["e6_threshold"], data["e6_bonus"])))
    return _replace(analysis, drop, add)


@RULES.hook("placed", MINT, nodes=("resonance_6",), name="mint_r6_gauge")
def _mint_r6(ctx, ev):
    """共鸣6 蓬绒绒慕斯: +2 Cycle gauge after each E (text: 环合值; the DB curve says 'Energy'), through the writer's
    gauge queue so the resource levels keep hit-time order."""
    data = ctx.data
    if data and ev.action and ev.action[0] == MINT_E:
        ev.gain_gauge(float(data["r6_gauge"]))


# ── 1020 哈尼娅 ──────────────────────────────────────────────────────────────

@RULES.hook("intervals", HANIEL, nodes=("Effect3", "Effect5", "resonance_6"), name="haniel_ace_window")
def _haniel(ctx, run, analysis):
    """Inside each 超异科王牌 window (the engine's GA_Haniel_UltraSkill interval, Q start + 2.867 s, 10 s): ③ crit
    +20 % (self), ⑤ psyche damage +30 % (self, cut when she leaves the field), 共鸣6 crit damage +12 % (team, survives
    her swap-out: removed with the 10 s buff)."""
    data = ctx.data
    if not data:
        return analysis
    member = ctx.member
    wins = [(int(x.start_us), int(x.end_us)) for x in analysis.buff_intervals
            if x.source_effect_definition_id == HANIEL_Q_WINDOW]
    add = []
    for i, (s, e) in enumerate(wins):
        if member.has("Effect3"):
            add.append(_interval(HANIEL, "Effect3", i, s, e, "CritBase", data["e3_crit"]))
        if member.has("Effect5"):
            add.append(_interval(HANIEL, "Effect5", i, s, _clip_to_visit(run, HANIEL, s, e), "DamageUpPsycheBase",
                                 data["e5_psyche"]))
        if member.has("resonance_6"):
            add.append(_interval(HANIEL, "resonance_6", i, s, e, "CritDamageBase", data["r6_crit_damage"],
                                 scope="team"))
    return _replace(analysis, set(), add)


# ── node metadata (UI marks, efficiency-table classes, assumption sentences) ──────────────────────────────────────
# ko: the reviewed sentence (Korean UI term 돌파); en / ja / zh where the tooltip shows it (low confidence, expected
# value, not 'now').

_TEXT = {
    (SAGIRI, "Effect1"): {
        "ko": "이동 불가 시간만 늘어나 피해와 무관하므로 효율표에는 '계산 불가'로 표시하고, 공명6의 디버프 개수에만 "
              "3초→6초로 반영합니다.",
        "en": "Only lengthens the immobilisation (3 s -> 6 s), which deals no damage: shown as 'Not computable' in "
              "the efficiency table and used only for the debuff count of Resonance 6.",
        "ja": "移動不能の時間が延びるだけでダメージには関係しないため効率表では「計算不可」と表示し、共鳴6のデバフ数"
              "にだけ3秒→6秒で反映します。",
        "zh": "只延长无法移动的时间（3→6 秒），与伤害无关：效率表显示「无法计算」，只计入共鸣6 的负面效果数量。"},
    (SAGIRI, "Effect2"): {
        "ko": "대상 질량이 데이터에 없어 계산하지 않고 '최대 +23.7%(질량 199 이상일 때)'를 상한으로만 보여 주며, "
              "공식(배율×(1+min(질량,199)))은 커브 이름에서 추정한 것입니다.",
        "en": "The target's mass is not in the data, so this is not priced: only the upper bound (+23.7 % at mass "
              "199 or more) is shown, and the formula (coefficient x (1 + min(mass, 199))) is inferred from the "
              "curve names.",
        "ja": "対象の質量がデータにないため計算せず、上限（質量199以上で最大+23.7%）だけを示します。式（倍率×(1+min(質量,199))）は"
              "カーブ名からの推定です。",
        "zh": "数据中没有目标质量，因此不计算，只显示上限（质量 199 以上时最高 +23.7%）；公式（倍率×(1+min(质量,199))）由曲线名推断。"},
    (SAGIRI, "Effect3"): {
        "ko": "효율표·팀 시뮬의 대상은 쓰러지지 않는 단일 목각인형이라 처치 이벤트가 없으므로 '계산 불가'로 "
              "표시합니다.",
        "en": "The target of the efficiency table and the team simulation is a single dummy that never dies, so "
              "there is no kill event: shown as 'Not computable'.",
        "ja": "効率表とチームシミュの対象は倒れない単体の木人で撃破イベントがないため、「計算不可」と表示します。",
        "zh": "效率表与队伍模拟的目标是不会被击败的单个木桩，没有击败事件，显示「无法计算」。"},
    (SAGIRI, "Effect4"): {"ko": "이미 계산되며 사키리 본인은 제외되므로 효율표에는 '팀 전용'으로 표시합니다."},
    (SAGIRI, "Effect5"): {
        "ko": "길게 누른 E가 목각인형을 띄우는 데 매번 성공한다고 보고(보스·강적이면 0) E 직후 Q 쿨타임을 0으로 만들며, "
              "게이지·사이클 순서는 그대로 두고 쿨타임 대기만 줄입니다."},
    (SAGIRI, "Effect6"): {
        "ko": "약한 적을 삼키는 편의 효과라 단일 목각인형 피해와 무관하므로 '계산 불가'로 표시합니다.",
        "en": "A convenience effect (swallowing weak enemies) with no damage on a single dummy: shown as 'Not "
              "computable'.",
        "ja": "弱い敵を呑み込む利便性の効果で、単体の木人へのダメージには関係しないため「計算不可」と表示します。",
        "zh": "吞噬弱小敌人的便利效果，与单个木桩的伤害无关，显示「无法计算」。"},
    (SAGIRI, "resonance_3"): {"ko": "이미 계산됩니다(가정 없음)."},
    (SAGIRI, "resonance_6"): {
        "ko": "'부정 효과'를 계산기가 아는 것(Q 압제 3초/6초, 패시브2 방어 −10% 20초, 팀원이 대상에 건 디버프와 "
              "DoT·사이클 반응 상태)으로만 세고, 디버프는 그것을 건 타격 바로 다음 타격부터 세며, 공중 부양 자체는 "
              "지속 시간을 몰라 세지 않습니다.",
        "en": "Only the debuffs the calculator knows are counted (Q suppression 3 s / 6 s, passive-2 DEF -10 % for "
              "20 s, teammates' debuffs on the target and DoT / Esper-Cycle states); a debuff counts from the hit "
              "after the one that applied it, and the float itself is not counted (its duration is unknown).",
        "ja": "「負面効果」は計算機が知っているもの（Q の制圧 3秒/6秒、パッシブ2 の防御 −10% 20秒、チームメイトが対象に付けたデバフと "
              "DoT・サイクル反応の状態）だけを数え、デバフはそれを付与した攻撃の次の攻撃から数えます。浮遊そのものは持続時間が"
              "不明なため数えません。",
        "zh": "「负面效果」只计计算器已知的（Q 压制 3/6 秒、被动 2 防御 −10% 20 秒、队友施加于目标的减益与持续伤害、环合状态）；"
              "减益从施加它的那一击之后的下一击开始计算；浮空本身持续时间未知，不计。"},
    (LACRIMOSA, "Effect1"): {"ko": "이미 계산됩니다(설명문의 {0} 대신 게임 데이터의 LV6 틱 계수를 씁니다)."},
    (LACRIMOSA, "Effect2"): {"ko": "이미 계산되며 1인 사이클에는 서포트 스킬 입장이 없어 효율표에는 '팀 전용'입니다."},
    (LACRIMOSA, "Effect3"): {
        "ko": "'일괄 정산'은 5타가 적중할 때 살아 있는 「악몽」 층마다 남은 틱을 전부 한 번에 주고 그 층을 지우는 것으로 계산합니다. "
              "지워진 층은 더 이상 틱을 주지 않으므로, 그 틱으로 쌓이던 「마지막 장미」 중첩과 팀에서의 잔홍 스코치 갱신도 함께 "
              "없어집니다. 1바퀴 이득의 일부는 전투가 끝난 뒤에 나왔을 틱을 앞당긴 몫이고, 5타 자신이 건 층도 함께 정산된다고 봅니다.",
        "en": "'Settles everything at once' is priced like this: at the 5th basic hit every live Nightmare layer pays "
              "all its remaining ticks at once and is removed. A removed layer no longer ticks, so the stacks of The "
              "Last Rose that its ticks would build and, in teams, Zankou's Scorch refresh are lost too. In 1 loop "
              "part of the gain is ticks that would have come after the battle, and the 5th hit's own new layer is "
              "settled too.",
        "ja": "「一括精算」は次のように計算します。5段目の命中時に生きている「悪夢」の各層が残りのティックをすべて一度に与え、その層は"
              "消えます。消えた層はそれ以上ティックを与えないため、そのティックで溜まる「最後の薔薇」のスタックと、チームでの残虹の"
              "濁燃の更新もなくなります。1周の利得の一部は戦闘終了後に来るはずのティックの前倒し分で、5段目自身が付与した層も一緒に"
              "精算されるとみなします。",
        "zh": "「一次性结算」按如下方式计算：第 5 段命中时，每层存活的「噩梦」一次结清全部剩余跳伤并移除该层；被移除的层不再跳伤，"
              "因此这些跳伤原本叠加的「最后一朵玫瑰」层数以及队伍中残虹的浊燃刷新也随之消失。1 轮中部分收益是本应在战斗结束后"
              "出现的跳伤被提前，第 5 段自身施加的层也一并结算。"},
    (LACRIMOSA, "Effect4"): {"ko": "이미 계산됩니다(가정 없음)."},
    (LACRIMOSA, "Effect5"): {
        "ko": "최대 생명 삭감은 '피해'가 아니라서 DPS에 넣지 않고(처치 시간 단축 효과는 무시) '계산 불가'로 "
              "표시합니다.",
        "en": "Cutting the target's max HP is not damage, so it is not in the DPS (the shorter kill time is "
              "ignored): shown as 'Not computable'.",
        "ja": "最大HPの削減は「ダメージ」ではないためDPSに入れず（撃破時間の短縮は無視）、「計算不可」と表示します。",
        "zh": "削减生命上限不是「伤害」，不计入 DPS（忽略缩短击败时间的作用），显示「无法计算」。"},
    (LACRIMOSA, "Effect6"): {
        "ko": "E 종료 뒤 5초(시간 정지 제외) 안에 스코치·노바 짝 속성 캐릭터에서 교대해 들어올 때만 게이지를 쓰지 "
              "않고 서포트 스킬 입장·사이클 반응을 발동시키며, 검수 사이클에는 그런 교대가 없어 효과는 직접 입력 "
              "사이클에서만 나타납니다."},
    (LACRIMOSA, "resonance_3"): {"ko": "이미 계산됩니다(비행 스태미나는 피해와 무관)."},
    (LACRIMOSA, "resonance_6"): {"ko": "이미 계산됩니다(가정 없음)."},
    (SKIA, "Effect1"): {
        "ko": "이 돌파 효과는 「그림자 송곳니」 자체 공격(ShadowAtk)에만 붙는데 그 타격이 아직 시뮬레이션 타임라인에 "
              "없어, 기본 키트(송곳니 타격)를 먼저 넣기 전에는 '측정 필요'로 표시합니다.",
        "en": "This effect applies only to the fangs' own attack (ShadowAtk), which is not in the simulation "
              "timeline yet: unmeasured until the base kit (the fang hits) is modelled.",
        "ja": "この効果は「獣牙影刺」自身の攻撃（ShadowAtk）にだけ付きますが、その攻撃がまだシミュレーションの時間軸"
              "にないため、基本キット（牙の攻撃）を入れるまでは「要実測」と表示します。",
        "zh": "该效果只作用于「兽牙影刺」自身的攻击（ShadowAtk），而这些命中尚未放到时间轴上：在补上基础机制（兽牙命中）之前不计入。"},
    (SKIA, "Effect2"): {"ko": "E 시전 시작부터 15초(시간 정지 제외) 동안 치명타 확률 +10%를 주고, 다시 쓰면 그때부터 15초로 갱신합니다."},
    (SKIA, "Effect3"): {
        "ko": "대상이 하나뿐이라 두 조건(+4%+4%)이 함께 켜지고, '고정됨'은 E의 6타가 끝나 송곳니가 붙은 뒤부터 "
              "「미행」이 끝날 때까지(E 시작부터 6초, 돌파 효과 ④면 12초)로만 보며 일반 공격 송곳니의 짧은 고정은 "
              "무시합니다."},
    (SKIA, "Effect4"): {
        "ko": "12초로 늘어난 「미행」은 돌파 효과 ③·공명6 구간에 바로 반영하고, '부착 1초당 +2%'는 송곳니 타격이 "
              "시뮬레이션 타임라인에 생길 때까지 반영하지 않습니다(그래서 단독 추가 값은 0)."},
    (SKIA, "Effect5"): {
        "ko": "질량·이동 속도만 바꾸므로 '계산 불가'로 표시합니다.",
        "en": "Changes only the target's mass and movement speed: shown as 'Not computable'.",
        "ja": "質量と移動速度を変えるだけなので「計算不可」と表示します。",
        "zh": "只改变目标质量与移动速度，显示「无法计算」。"},
    (SKIA, "Effect6"): {"ko": "물어 쫓는 잠영 접촉으로 생기는 송곳니 추가 공격(SkillShadowAtk) 전부의 계수를 1.2배로 "
                              "봅니다(게임 데이터가 바로 이 타격에 CoefModify 0.2를 둠)."},
    (SKIA, "resonance_3"): {"ko": "이미 계산됩니다(가정 없음)."},
    (SKIA, "resonance_6"): {"ko": "E의 6타가 끝난 뒤 붙은 송곳니 3개가 「미행」이 끝날 때까지 고정돼 상속성 저항 "
                                  "−6%를 유지한다고 보고, 일반 공격 송곳니의 짧은 고정은 무시합니다."},
    (NANALLY, "Effect1"): {"ko": "추가 공격(지금은 돌파 효과 ③ 추가타만 존재)마다 에너지 2.5를 1초 간격 제한으로 더하지만, 나나리 궁극기 비용을 "
                                 "몰라 DPS에는 영향이 없고 표시만 됩니다."},
    (NANALLY, "Effect2"): {
        "ko": "이인자 고양이의 공격이 아직 시뮬레이션 타임라인에 없어 지속 6→9초를 반영할 대상이 없으므로, 고양이 "
              "타격(기본 키트)을 먼저 넣을 때까지 '측정 필요'입니다.",
        "en": "The Sidekick cat's attacks are not in the simulation timeline yet, so the longer duration (6 s -> 9 "
              "s) has nothing to act on: unmeasured until the cat hits (base kit) are modelled.",
        "ja": "サブ（猫）の攻撃がまだシミュレーションの時間軸にないため、持続 "
              "6→9秒を反映する対象がありません。猫の攻撃（基本キット）を入れるまでは「要実測」です。",
        "zh": "副手（猫）的攻击尚未放到时间轴上，持续时间 6→9 秒没有作用对象：在补上猫的命中（基础机制）之前不计入。"},
    (NANALLY, "Effect3"): {
        "ko": "「초대 가주의 권능」 상태(E부터 12초, 돌파 효과 ⑥이면 15초, 교대하거나 E를 다시 누르면 종료) 안에서 "
              "나나리 타격마다 1초에 한 번 추가타를 같은 시각에 넣고, 이 추가타 자신은 다시 발동시키지 않는다고 "
              "봅니다."},
    (NANALLY, "Effect4"): {
        "ko": "이인자 고양이 타격이 생기면 그 타격에만 피해 +100%를 주되, 지금은 타격이 없어 '측정 필요'입니다.",
        "en": "Once the Sidekick cat's hits exist they get +100 % damage; there are none yet, so this is unmeasured.",
        "ja": "サブ（猫）の攻撃ができればその攻撃にだけダメージ+100%を与えますが、今は攻撃がないため「要実測」です。",
        "zh": "副手（猫）的命中出现后只对这些命中伤害 +100%；目前没有这些命中，不计入。"},
    (NANALLY, "Effect5"): {
        "ko": "추가 공격 1회마다 공격력 +2%(최대 10층)가 쌓여 교대할 때까지 유지되며(게임 데이터의 15초 값은 "
              "설명문에 없어 쓰지 않음), 지금 1인에서는 돌파 효과 ③ 추가타만 추가 공격이라 단독 효과는 0입니다."},
    (NANALLY, "Effect6"): {
        "ko": "상태가 15초로 길어져도 검수 사이클(행동 순서)은 바꾸지 않고, 돌파 효과 ③ 추가타가 나올 수 있는 구간만 늘립니다"
              "(사이클을 바꾸는 이득은 반영하지 않음)."},
    (NANALLY, "resonance_3"): {"ko": "이미 계산됩니다(가정 없음; 돌파 효과 ③ 추가타 계수도 Lv11이 됨)."},
    (NANALLY, "resonance_6"): {"ko": "이미 계산됩니다(커브 이름의 'FarTarget' 조건은 설명문·게임 데이터 조건에 없어 "
                                     "상시로 둡니다)."},
    (MINT, "Effect1"): {
        "ko": "검수 사이클에 극한 반격이 없어 1인 효과는 0이며, 반격을 넣은 직접 입력 사이클에서만 E 쿨타임 초기화가 나타납니다"
              "(3초 제한은 아직 규칙에 없음)."},
    (MINT, "Effect2"): {"ko": "게임 데이터가 E 타격에 '피해 증가(DamageUpGeneralBase) +0.40'으로 붙이므로 계수 "
                              "×1.4가 아니라 다른 피해 증가와 더하는 방식으로 넣습니다."},
    (MINT, "Effect3"): {
        "ko": "블라썸·헥스 사이클 반응이 '발동한 시각'부터 15초로 보고(누가 발동해도 됨: 설명문 기준), 지금 빠져 "
              "있는 헥스 발동도 넣으며 블라썸 꽃이 떨어질 때마다 늘어나던 기존 방식은 고칩니다. 게임 데이터는 '민트 "
              "자신의 서포트 스킬 입장' 때만 켜지도록 되어 있어, 그 해석이라면 값이 더 작아집니다."},
    (MINT, "Effect4"): {"ko": "효율표·팀 시뮬의 대상이 적 1명이므로 민트의 첫 타격 이후 계속 치명타 확률 +12%로 봅니다."},
    (MINT, "Effect5"): {"ko": "이미 계산됩니다(시작을 E 시전 대신 E 타격으로 잡는 기존 방식 유지)."},
    (MINT, "Effect6"): {
        "ko": "대상 생명이 피해에 비례해 줄어든다고 보고, 생명 40% 미만에서 보내는 시간 비율(약 38%, +15%로 더 빨리 "
              "깎이는 몫 반영)만큼 +15%를 평균 내 상시 +5.7%로 넣습니다.",
        "en": "The target's HP is taken to fall in proportion to the damage: +15 % is averaged over the share of "
              "time spent below 40 % HP (about 38 %, allowing for the faster drop the +15 % itself causes) and "
              "applied as a constant +5.7 %.",
        "ja": "対象のHPはダメージに比例して減るとみなし、HP40%未満で過ごす時間の割合（約38%、+15%で速く削れる分を反映"
              "）だけ+15%を平均して常時+5.7%として入れます。",
        "zh": "假设目标生命按伤害比例下降：按生命低于 40% 的时间占比（约 38%，已计入 +15% 使其下降更快的部分）把 "
              "+15% 平均为常驻 +5.7%。"},
    (MINT, "resonance_3"): {"ko": "이미 계산됩니다(가정 없음)."},
    (MINT, "resonance_6"): {"ko": "E를 쓸 때마다 민트의 사이클 수치를 2 더하며(설명문 기준, 게임 데이터 커브 이름의 "
                                  "'Energy'는 무시), 1인 효율에는 영향이 없고 팀 시뮬의 사이클 반응 발동 시점만 "
                                  "바뀝니다."},
    (HANIEL, "Effect1"): {
        "ko": "주인공 오라는 '합주'로만 쌓이고 마법포는 검수 사이클에 없으며 튕김은 대상이 여럿이어야 하므로, "
              "합주·마법포를 모델링하기 전에는 '측정 필요'입니다.",
        "en": "Protagonist Halo stacks only through Ensemble, the magic cannon is not in the reviewed rotation and "
              "its bounces need several targets: unmeasured until Ensemble and the cannon are modelled.",
        "ja": "主人公オーラは「合奏」でしか溜まらず、魔法砲は審査済みサイクルになく、跳ね返りには複数の対象が必要なた"
              "め、合奏と魔法砲をモデル化するまでは「要実測」です。",
        "zh": "「主角光环」只由合奏累积，魔法炮不在已审核循环中，弹射需要多个目标：在合奏与魔法炮建模之前不计入。"},
    (HANIEL, "Effect2"): {"ko": "이미 계산되며 1인 피해는 변하지 않아 '팀 전용'입니다(초이능학과 에이스 동안 구구새 "
                                "시간이 멈추는 기본 규칙은 별도 미반영)."},
    (HANIEL, "Effect3"): {"ko": "초이능학과 에이스 상태 창은 엔진의 전체 공격력 버프 창(Q 시작 2.867초 뒤부터 "
                                "10초)과 같다고 보고 그 동안 하니엘 치명타 확률 +20%를 줍니다."},
    (HANIEL, "Effect4"): {
        "ko": "합주(「4부 화음」 4층)와 그 추가 타격 자체가 아직 계산기에 없어, 합주를 기본 키트로 먼저 넣기 전에는 "
              "'측정 필요'로 표시합니다.",
        "en": "Ensemble (4 Four-Part Harmony stacks) and its extra hit are not in the calculator yet: unmeasured "
              "until Ensemble is modelled as base kit.",
        "ja": "合奏（四声体和声4層）とその追加攻撃自体がまだ計算機にないため、合奏を基本キットとして入れるまでは「要"
              "実測」と表示します。",
        "zh": "合奏（四部和声 4 层）及其追加命中尚未加入计算器：在合奏作为基础机制建模之前不计入。"},
    (HANIEL, "Effect5"): {"ko": "돌파 효과 ③과 같은 창에서 혼속성 피해 +30%를 주되, 상태가 교대 시 사라지므로 하니엘이 퇴장(1인 사이클의 재입장 "
                                "포함)하는 순간 끊습니다."},
    (HANIEL, "Effect6"): {"ko": "이미 계산되며 선택한 돌파 효과 기준으로 적용됩니다(커뮤니티 쿨타임 20초 전제)."},
    (HANIEL, "resonance_3"): {"ko": "이미 계산됩니다(가정 없음)."},
    (HANIEL, "resonance_6"): {"ko": "초이능학과 에이스 창(10초) 동안 하니엘을 포함한 팀 전체 치명타 피해 +12%를 "
                                    "주며, 게임 데이터상 이 버프는 10초 버프가 끝날 때 지워지므로 하니엘이 교대해도 "
                                    "남깁니다."},
}

# (character, node): (category, bucket, confidence, scope, extra NodeInfo fields)
_NODES = {
    (SAGIRI, "Effect1"): ("none", "not_computable", "high", "", {}),
    (SAGIRI, "Effect2"): ("bound", "measure", "low", "", {}),
    (SAGIRI, "Effect3"): ("none", "not_computable", "high", "", {}),
    (SAGIRI, "Effect4"): ("team", "now", "high", "team_only", {}),
    (SAGIRI, "Effect5"): ("time", "now", "medium", "solo_team", {"resolves_codes": ("sagiri_a5_float_refill",)}),
    (SAGIRI, "Effect6"): ("none", "not_computable", "high", "", {}),
    (SAGIRI, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (SAGIRI, "resonance_6"): ("damage", "now", "low", "solo_team", {}),
    (LACRIMOSA, "Effect1"): ("damage", "now", "high", "solo_team", {}),
    (LACRIMOSA, "Effect2"): ("team", "now", "high", "team_only", {}),
    (LACRIMOSA, "Effect3"): ("damage", "now", "low", "solo_team", {}),
    (LACRIMOSA, "Effect4"): ("damage", "now", "high", "solo_team", {}),
    (LACRIMOSA, "Effect5"): ("none", "not_computable", "high", "", {}),
    (LACRIMOSA, "Effect6"): ("team", "now", "medium", "team_only", {"resolves_codes": ("lacrimosa_a6_support",)}),
    (LACRIMOSA, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (LACRIMOSA, "resonance_6"): ("damage", "now", "high", "solo_team", {}),
    (SKIA, "Effect1"): ("unmodelled", "measure", "medium", "", {}),
    (SKIA, "Effect2"): ("damage", "now", "high", "solo_team", {}),
    (SKIA, "Effect3"): ("damage", "now", "medium", "solo_team", {}),
    (SKIA, "Effect4"): ("damage", "now", "medium", "solo_team", {}),
    (SKIA, "Effect5"): ("none", "not_computable", "high", "", {}),
    (SKIA, "Effect6"): ("damage", "now", "high", "solo_team", {}),
    (SKIA, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (SKIA, "resonance_6"): ("damage", "now", "medium", "solo_team", {}),
    (NANALLY, "Effect1"): ("resource", "now", "medium", "resource_only",
                           {"resolves_codes": ("nanally_a1_follow_up_energy",)}),
    (NANALLY, "Effect2"): ("unmodelled", "measure", "low", "", {}),
    (NANALLY, "Effect3"): ("damage", "now", "medium", "solo_team", {}),
    (NANALLY, "Effect4"): ("unmodelled", "measure", "low", "", {}),
    (NANALLY, "Effect5"): ("damage", "now", "medium", "solo_team", {}),
    (NANALLY, "Effect6"): ("damage", "now", "medium", "solo_team", {}),
    (NANALLY, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (NANALLY, "resonance_6"): ("damage", "now", "high", "solo_team", {}),
    (MINT, "Effect1"): ("rotation", "now", "high", "team_only", {}),
    (MINT, "Effect2"): ("damage", "now", "high", "solo_team", {}),
    (MINT, "Effect3"): ("team", "now", "medium", "team_only", {}),
    (MINT, "Effect4"): ("damage", "now", "high", "solo_team", {}),
    (MINT, "Effect5"): ("damage", "now", "high", "solo_team", {}),
    (MINT, "Effect6"): ("damage", "now", "low", "solo_team", {"expected_value": True}),
    (MINT, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (MINT, "resonance_6"): ("team", "now", "medium", "team_only", {}),
    (HANIEL, "Effect1"): ("unmodelled", "measure", "medium", "", {}),
    (HANIEL, "Effect2"): ("team", "now", "high", "team_only", {}),
    (HANIEL, "Effect3"): ("damage", "now", "high", "solo_team", {}),
    (HANIEL, "Effect4"): ("unmodelled", "measure", "medium", "", {}),
    (HANIEL, "Effect5"): ("damage", "now", "high", "solo_team", {}),
    (HANIEL, "Effect6"): ("time", "now", "high", "solo_team", {}),
    (HANIEL, "resonance_3"): ("damage", "now", "high", "solo_team", {}),
    (HANIEL, "resonance_6"): ("damage", "now", "high", "solo_team", {}),
}

for (_cid, _node), (_category, _bucket, _confidence, _scope, _extra) in _NODES.items():
    RULES.node(_cid, _node, category=_category, bucket=_bucket, confidence=_confidence, scope=_scope,
               assumption=_TEXT.get((_cid, _node)), **_extra)
