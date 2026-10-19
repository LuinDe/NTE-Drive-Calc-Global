# 队伍模拟：觉醒（돌파）效果规则——角色组 g2（黑羽 「零」 浔 达芙蒂尔 九原 明音凛）。只在本文件登记本组角色的规则。
"""Awakening-node rules of group g2: characters 1042, 1051, 1052, 1054, 1055, 1057 (Korean UI "돌파").

Source of every rule: ``awaken/specs/group_2.json`` after the 10-18 adversarial review (``group_2_review.md``); the
numbers are read from the static DB in ``prepare`` (curve rows named below), never typed in.  Edit only this file.

======================  ===========  ======================================================================
node                    hook         rule
======================  ===========  ======================================================================
1042 ① 叛逃者           evidence     渡世死焰 (GE_Player_BlackBird_Evolve_Skill_Damage) coefficient x(1+1.5)
1042 ② 漫游记           evidence     葬羽冥 (GE_Player_BlackBird_Skill_Damage) coefficient x(1+1.0)
1042 ④ 坏骨头           intervals    team DamageUpGeneralBase +0.12, 25 s active from the witch transform
1042 ⑤ 烂柯人           buff_rules   target Psyche / Lakshana / Chaos resistance -0.08, 25 s after every hit
1042 ⑥ 死与生           intervals    self DamageUpPsycheBase +0.25, 25 s active from the witch transform
1042 共鸣3              evidence     恳请众魂安息 x(1+1.0), 万火归一 x(1+0.5) (skill level +1 is the engine's)
1042 共鸣6              buff_rules   team CritDamageBase +0.30 (replaces the self rule without a value)
1051 base kit (①⑥)      gate         one extra 「铭隙鉴刻」 hit per E (the axis laid out six): lv2 GE with ⑥; none
                                     when the run's target is above Zero's level (custom enemy level)
1051 ④ 未决迷数         buff_rules   Q damage +min(0.001 x (character + arc base ATK), 0.25)
1052 ① 欣欣渐行         placed +     +0.12 damage per teammate recorded in the 5 s after her E, in the next
                        intervals    time stop (team only)
1052 ② 忆昔告远         intervals    self DamageUpGeneralBase +0.20 in her time stop
1052 ⑤ 独窥全相         buff_rules   team DamageUpGeneralBase +0.15 (scope fix: HTGlobal component + text)
1052 ⑥ 时轮啮雪         intervals    self DefIgnore +0.30 in her time stop
1052 共鸣6              buff_rules   team AtkUp +0.30 (scope fix)
1055 ① 知晓与制衡       intervals    self AtkUp +0.05 while the dummy holds 「致命玫约」 (after her E)
1055 ⑤ 掌握底细的优越   intervals +  self DamageUpGeneralBase +0.08 in the same window (the generic static
                        buff_rules   rule, which never reached a hit, is dropped)
1055 共鸣6              intervals    target Nature resistance -0.10 in the same window
======================  ===========  ======================================================================

Already priced by the engine (metadata only): 1051 ②③⑤ 共鸣3 共鸣6, 1052 共鸣3, 1054 ①⑥ 共鸣3, 1055 共鸣3.  Not
priced (marked 'needs measurement' / 'not computable', never 0 %): 1042 ③, 1052 ③④, 1054 ②③④⑤ 共鸣6,
1055 ②③④⑥.  Akane 1057: CN release data (global_live_overlay, active only for its DB): 烁星激昂 (base kit), ②④⑥
共鸣3 共鸣6, the 9-24 ① / 共鸣3 buffs off; ③⑤ unpriced (G6 / G7), ① no damage effect.

``READINGS`` holds the reviewed alternative readings (group_2_review.md §3); the defaults are the spec's.  Tests set
them to reproduce the alternative measurements and restore them.
"""
from __future__ import annotations

import dataclasses
import json
import os

from src.services.awakening_node_rules.core import NAME_PREFIX, SOURCE_KIND, SUPPLEMENT_CONFIDENCE, RuleSet

RAVEN, ZERO, HOTORI, DAFFODILL, KUHARA, AKANE = 1042, 1051, 1052, 1054, 1055, 1057
RULES = RuleSet("g2", (RAVEN, ZERO, HOTORI, DAFFODILL, KUHARA, AKANE))

READINGS = {
    "zero_equal_level": "kept",         # kept: extra hit at A0 vs an equal-level target (upstream audit) | strict
    "hotori_window_start": "after_q",   # after_q: after the Q's 10 hits (text) | enter_time_stop (montage notify)
    "hotori_finisher": "in",            # in: the tachi finisher hit is inside the stop | out
    "kuhara_window": "fight",           # fight: the contract lasts to the end | until_q: ends with her next Q
    "raven_anchor": "transform",        # transform: Q start + the witch transform marker | q_start
}

_ADD = "EGameplayModOp::Additive"
_STATIC = "STATIC_EQUIPPED_SOURCE"
_RULE_CONFIDENCE = "高"                 # DB values (the spec's rule-layer confidence; intervals use 中)

# ── static DB (read once per database file) ────────────────────────────────────
# curves (DT_<character>EffectFigure rows); the property a value feeds is read from the buff modifier using the row
_CURVES = {
    RAVEN: {
        "e1_coef": "Buff_BlackBird042_Level1_Skill_Coef",
        "e2_coef": "BlackBird042_Skill_Bird_CofeAdd_Level2",
        "e4_dmg": "Buff_BlackBird042_Evolve_UltraSkill_DamUP_Level4",
        "e4_time": "Buff_BlackBird042_Evolve_UltraSkill_AtkUP_Level4_Time",
        "e5_psyche": "Buff_BlackBird042_Level5_CutDef_DamageResistPsycheBase",
        "e5_lakshana": "Buff_BlackBird042_Level5_CutDef_DamageResistLakshanaBase",
        "e5_chaos": "Buff_BlackBird042_Level5_CutDef_DamageResistIncantationBase",   # row name says Incantation;
        "e5_time": "Buff_BlackBird042_Level5_CutDef_Time",                           # its buff feeds Chaos (暗)
        "e6_dmg": "Buff_BlackBird042_Level6_DamUP_DamageUpPsycheBase",
        "e6_time": "Buff_BlackBird042_Level6_DamUP_Time",
        "r3_q": "Buff_BlackBird042_Level3_Extra_UltraSkill_CofeAdd",
        "r3_witch_q": "Buff_BlackBird042_Level3_Extra_UltraSkillEvolve_CofeAdd",
        "r6_crit_dmg": "Buff_BlackBird042_Level6_extra",
    },
    ZERO: {
        "e3_crit": "Female051_LV3",      # read for the Q source tags only (Effect4 has none in the DB)
        "e4_rate": "Female051_LV4_2",
        "e4_cap": "Female051_LV4_3",
    },
    HOTORI: {
        "e1_dmg": "Jin_lv1_Damup",
        "e2_dmg": "Jin_lv2_TimeDamUp",
        "e5_dmg": "Jin_lv5_SingleDamUp",
        "e6_def": "Jin_lv6_TimeDef",
        "r6_atk": "Jin_lvExtra_AtkUp",
    },
    KUHARA: {
        "e1_atk": "Buff_Kuhara_Seed_AtkUp",
        "e5_dmg": "Kuhara_DmgUp_L5",
        "r6_res": "Kuhara_DmgResistDownNature",
    },
}
# curves a calculation class reads: the property comes from the buff whose modifier uses that class
_CURVE_BUFF = {"Jin_lv1_Damup": "Buff_Jin_CaluELV1"}               # Calu_Jin_QDamupLV1 -> DamageUpGeneralBase
# property when no buff modifier row carries the curve (Buff_Kuhara055_Level6_extra has no modifier; text 灵 = Nature)
_FALLBACK_PROPERTY = {"Kuhara_DmgResistDownNature": "DamageResistNatureBase"}
# skill-coefficient nodes: (damage GE, CoefModify calculation class in the DB, curve key)
_RAVEN_COEF = {
    "Effect1": (("GE_Player_BlackBird_Evolve_Skill_Damage", "Calc_BlackBird_Level1_SkillEvolveCofe", "e1_coef"),),
    "Effect2": (("GE_Player_BlackBird_Skill_Damage", "Calc_BlackBird_Level2_SkillCofeAdd", "e2_coef"),),
    "resonance_3": (("GE_Player_BlackBird_UltraSkill_Damage", "Calc_BlackBird_Level3Extra_UltraSkillCofeAdd", "r3_q"),
                    ("GE_Player_BlackBird_Evolve_UltraSkill_Damage", "Calc_BlackBird_Level3Extra_UltraSkillEvolveCofeAdd",
                     "r3_witch_q")),
}
_BUFF_DURATIONS = {"hotori_stop_cap": "Buff_Jin052_DamUpLv2"}       # the node buffs' 20 s life (her time stop)
_NOTIFY = {
    "record": "Event.Montage.Player.Common.JinRecordSkill",            # a teammate's E / support montage records
    "record_open": "Event.Montage.Player.Skill.Jin.RecordOtherSkill",  # Hotori's E opens the 5 s record window
    "enter_stop": "Event.Montage.Player.UltraSkill.Jin.EnterTimeStop",  # Q montage (READINGS hotori_window_start)
}
ZERO_KILL = ("GE_Player_Female051_Skill_Kill_Damage_lv1", "GE_Player_Female051_Skill_Kill_Damage_lv2")
ZERO_E = "GA_Female051_Skill"
HOTORI_E, HOTORI_Q, HOTORI_FINISHER = "GA_Jin_Skill", "GA_Jin_UltraSkill", "ultraskillmelee6"
HOTORI_RECORD_S = 5.0          # GA_Jin_Skill text: 记录队友接下来5秒内发动的「援护技」和「变轨技能」
HOTORI_RECORD_MAX = 3          # GA_Jin_Skill text: 一次最多记录3个…每个角色最多被记录一次
KUHARA_E = "GA_Kuhara_Skill"
KUHARA_SEED_S = 5.0            # Buff_Kuhara_Seed_Duration (READINGS kuhara_window until_q without a Q)

_DB_CACHE: dict = {}


def _db_identity(con):
    try:
        rows = con.execute("PRAGMA database_list").fetchall()
        path = next((str(r[2]) for r in rows if str(r[1]) == "main"), "")
        if not path:
            return None
        st = os.stat(path)
        return os.path.normcase(os.path.abspath(path)), int(st.st_size), int(st.st_mtime_ns)
    except Exception:
        return None


def _row_name(magnitude_json) -> str:
    try:
        data = json.loads(magnitude_json or "{}")
    except ValueError:
        return ""
    return str(((data.get("ScalableFloatMagnitude") or {}).get("Curve") or {}).get("RowName") or "")


def _tags(text) -> tuple:
    try:
        value = json.loads(text or "[]")
    except ValueError:
        return ()
    return tuple(str(t) for t in value) if isinstance(value, list) else ()


def _read_tables(con) -> dict:
    """Every number group g2 needs, from the static DB (read only)."""
    names = sorted({c for table in _CURVES.values() for c in table.values()})
    curves: dict = {}
    for name in names:
        row = con.execute("SELECT value FROM combat_curve_point WHERE curve_id = ? ORDER BY curve_table_asset_path, "
                          "ordinal LIMIT 1", (name,)).fetchone()
        if row is not None:
            curves[name] = float(row[0])
    props: dict = {}
    tags: dict = {}
    for name in names:
        for asset, prop, magnitude, src_tags in con.execute(
                "SELECT asset_path, property_id, magnitude_json, source_require_tags_json FROM buff_modifier "
                "WHERE magnitude_json LIKE ? ORDER BY asset_path, ordinal", (f'%"RowName":"{name}"%',)):
            if _row_name(magnitude) == name and name not in props:
                props[name] = str(prop)
                tags[name] = _tags(src_tags)
    for name, buff in _CURVE_BUFF.items():
        row = con.execute("SELECT property_id, source_require_tags_json FROM buff_modifier WHERE asset_path LIKE ? "
                          "ORDER BY ordinal LIMIT 1", (f"%/{buff}",)).fetchone()
        if row is not None and name not in props:
            props[name] = str(row[0])
            tags[name] = _tags(row[1])
    coef = set()
    for asset, calc in con.execute("SELECT asset_path, calculation_asset_path FROM buff_modifier "
                                   "WHERE property_id = 'CoefModify' AND asset_path LIKE '%BlackBird%'"):
        coef.add((str(asset).rsplit("/", 1)[-1].casefold(), str(calc or "").rsplit("/", 1)[-1].casefold()))
    durations: dict = {}
    for key, buff in _BUFF_DURATIONS.items():
        row = con.execute("SELECT duration_magnitude_json FROM buff_definition WHERE asset_path LIKE ? LIMIT 1",
                          (f"%/{buff}",)).fetchone()
        try:
            sf = (json.loads(row[0] or "{}").get("ScalableFloatMagnitude") or {}) if row else {}
        except ValueError:
            sf = {}
        if sf.get("Value"):
            durations[key] = float(sf["Value"])
    notify: dict = {}
    for key, tag in _NOTIFY.items():
        table: dict = {}
        for asset, start in con.execute("SELECT asset_path, start_seconds FROM combat_montage_notify WHERE event_tag = ? "
                                        "ORDER BY asset_path, start_seconds", (tag,)):
            name = str(asset).rsplit("/", 1)[-1].casefold()
            table.setdefault(name, float(start))
        notify[key] = table
    return {"curves": curves, "props": props, "tags": tags, "coef": coef, "durations": durations, "notify": notify}


def tables(con) -> dict:
    """The g2 DB tables of the connection's database, cached per file (path, size, mtime)."""
    key = _db_identity(con)
    got = _DB_CACHE.get(key) if key is not None else None
    if got is None:
        got = _read_tables(con)
        if key is not None:
            if len(_DB_CACHE) >= 4:
                _DB_CACHE.clear()
            _DB_CACHE[key] = got
    return got


def _params(t: dict, cid: int) -> dict:
    """{key: (property or None, value)} of one character (value None when the curve is missing)."""
    out = {}
    for key, curve in _CURVES.get(cid, {}).items():
        out[key] = (t["props"].get(curve) or _FALLBACK_PROPERTY.get(curve), t["curves"].get(curve))
    return out


def _value(data, key):
    item = (data or {}).get(key)
    return None if item is None else item[1]


def _prop(data, key):
    item = (data or {}).get(key)
    return None if item is None else item[0]


# ── shared builders ─────────────────────────────────────────────────────────

def _modifier(prop: str, value: float, tags=(), confidence: str = SUPPLEMENT_CONFIDENCE):
    from src.domain.battle_report import BattleBuffModifierEvidence

    return BattleBuffModifierEvidence(property_id=str(prop), modifier_operation=_ADD, magnitude_kind=SOURCE_KIND,
                                      magnitude_value=float(value), calculation_asset_path="",
                                      value_confidence=confidence, source_require_tags=tuple(tags))


def _rule(cid: int, node: str, name: str, scope: str, event: str, seconds, mods, index: int = 0):
    """A rule-layer buff in the shape BattleBuffInferenceService.load_rules returns (Global, 高 values)."""
    from src.domain.battle_buff_rule import BattleStaticBuffRule

    def_id = f"character_awaken:{cid}:{node}"
    return BattleStaticBuffRule(
        rule_id=f"{def_id}:global-awakening:{index}", source_effect_definition_id=def_id, source_kind=SOURCE_KIND,
        source_character_id=int(cid), source_character_name=str(name), source_asset_path=f"global-awakening:{def_id}",
        target_asset_path=f"global-awakening:{def_id}:{index}", target_name=f"{NAME_PREFIX}{def_id}",
        target_scope=scope, event_type=event, effect_type="ADD",
        duration_policy="HasDuration" if seconds else "Equipped", duration_seconds=seconds, stack_count=1,
        modifiers=tuple(_modifier(p, v, t, _RULE_CONFIDENCE) for p, v, t in mods),
        stacking_type="AggregateByTarget", stack_limit_count=1)


def _replace_rules(rules, new: list) -> tuple:
    """Drop the generic rules of the replaced definitions, append the Global ones."""
    replaced = {r.source_effect_definition_id for r in new}
    return tuple(r for r in tuple(rules) if r.source_effect_definition_id not in replaced) + tuple(new)


def _name(build: dict, cid: int) -> str:
    for c in (build or {}).get("characters") or ():
        if int(c.get("character_id") or 0) == cid:
            return str(c.get("observed_name") or cid)
    return str(cid)


def _interval(cid: int, node: str, index: int, start: int, end: int, props, scope: str = "self", target_id: str = ""):
    from src.domain.battle_report import BattleInferredBuffInterval

    return BattleInferredBuffInterval(
        interval_id=f"global:awk:{cid}:{node}:{index}", buff_asset_path=f"global-awakening:{cid}:{node}",
        buff_name=f"{NAME_PREFIX}{cid} {node}", source_effect_definition_id=f"character_awaken:{cid}:{node}",
        source_kind=SOURCE_KIND, source_character_id=int(cid), source_character_name="", target_scope=scope,
        start_us=int(start), end_us=int(end), stacks=1, duration_policy="HasDuration",
        state_confidence=SUPPLEMENT_CONFIDENCE, value_confidence=SUPPLEMENT_CONFIDENCE,
        inference_basis="Global awakening rule (group_2 spec, DB values, built from the run's actions / hits)",
        trigger_event_type="GLOBAL_AWAKENING", evidence_action_ids=(), evidence_event_ids=(),
        modifiers=tuple(_modifier(p, v, t) for p, v, t in props), target_id=target_id)


def _merge(windows) -> list:
    out: list = []
    for s, e in sorted(windows):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        elif e > s:
            out.append([s, e])
    return out


def _add_intervals(analysis, extra: list):
    if not extra:
        return analysis
    extra = tuple(extra)
    return dataclasses.replace(analysis, buff_intervals=tuple(analysis.buff_intervals) + extra,
                               timeline_buff_intervals=tuple(analysis.timeline_buff_intervals) + extra)


def _priced(analysis, cid: int, node: str) -> bool:
    """True when the engine already built a valued interval for the node (then the rule stays out)."""
    def_id = f"character_awaken:{cid}:{node}"
    return any(iv.source_effect_definition_id == def_id and iv.source_kind != SOURCE_KIND
               and any(m.magnitude_value for m in iv.modifiers) for iv in analysis.buff_intervals)


def _active_end(analysis, start_us: int, seconds: float) -> int:
    from src.services.team_fork_corrections import active_window_end

    return active_window_end(analysis, int(start_us), float(seconds))


def _target(analysis) -> str:
    return next((h.target_id for h in sorted(analysis.hits, key=lambda h: h.relative_time_us)
                 if h.direction == "outgoing" and h.target_id), "")


def _actions(analysis) -> list:
    return sorted(analysis.inferred_actions, key=lambda a: a.start_us)


# ── 1042 Raven (黑羽) ─────────────────────────────────────────────────────────
_RAVEN_NODES = ("Effect1", "Effect2", "Effect4", "Effect5", "Effect6", "resonance_3", "resonance_6")


@RULES.hook("prepare", RAVEN, nodes=_RAVEN_NODES)
def _raven_prepare(ctx):
    t = tables(ctx.con)
    data = _params(t, RAVEN)
    coef = {}
    for node, items in _RAVEN_COEF.items():
        coef[node] = tuple((ge, _value(data, key)) for ge, calc, key in items
                           if (ge.casefold(), calc.casefold()) in t["coef"] and _value(data, key) is not None)
    data["coef"] = coef
    return data


@RULES.hook("buff_rules", RAVEN, nodes=("Effect5", "resonance_6"))
def _raven_rules(ctx, static, build, rules):
    data, new = ctx.data, []
    name = _name(build, RAVEN)
    if ctx.member.has("Effect5") and _value(data, "e5_time"):
        mods = [(_prop(data, k), _value(data, k), ()) for k in ("e5_psyche", "e5_lakshana", "e5_chaos")]
        mods = [m for m in mods if m[0] and m[1] is not None]
        if mods:   # every Raven hit: 25 s on the hit target, a new hit refreshes (AggregateByTarget, limit 1)
            new.append(_rule(RAVEN, "Effect5", name, "target", "EBuffEventType::BUFF_EVENT_SKILL_AFTER_HIT",
                             _value(data, "e5_time"), mods))
    if ctx.member.has("resonance_6") and _prop(data, "r6_crit_dmg") and _value(data, "r6_crit_dmg") is not None:
        new.append(_rule(RAVEN, "resonance_6", name, "team", _STATIC, None,
                         [(_prop(data, "r6_crit_dmg"), _value(data, "r6_crit_dmg"), ())]))
    return _replace_rules(rules, new) if new else rules


@RULES.hook("intervals", RAVEN, nodes=("Effect4", "Effect6"))
def _raven_windows(ctx, run, analysis):
    from src.services.team_form_actions import FORMS

    data = ctx.data
    ability, _selector, offset_s = FORMS[RAVEN]["start"]       # GA_BlackBird_UltraSkill +3.167 s = witch transform
    off = int(round(float(offset_s) * 1_000_000)) if READINGS["raven_anchor"] == "transform" else 0
    end = int(analysis.battle_end_us)
    starts = [a.start_us + off for a in _actions(analysis) if a.character_id == RAVEN and a.action_name == ability]
    extra = []
    for node, key, time_key, scope in (("Effect4", "e4_dmg", "e4_time", "team"), ("Effect6", "e6_dmg", "e6_time", "self")):
        prop, value, seconds = _prop(data, key), _value(data, key), _value(data, time_key)
        if not ctx.member.has(node) or not prop or value is None or not seconds or _priced(analysis, RAVEN, node):
            continue
        windows = _merge([(q, min(end, _active_end(analysis, q, seconds))) for q in starts])
        extra.extend(_interval(RAVEN, node, i, s, e, ((prop, value, ()),), scope=scope)
                     for i, (s, e) in enumerate(windows))
    return _add_intervals(analysis, extra)


@RULES.hook("evidence", RAVEN, nodes=("Effect1", "Effect2", "resonance_3"))
def _raven_coefficients(ctx, run, evidence):
    factors: dict = {}
    for node, items in ((ctx.data or {}).get("coef") or {}).items():
        if ctx.member.has(node):
            for ge, add in items:
                factors[ge.casefold()] = factors.get(ge.casefold(), 1.0) * (1.0 + float(add))
    if not factors:
        return evidence
    return tuple(dataclasses.replace(e, multiplier_coefficient=e.multiplier_coefficient * factors[e.damage_id.casefold()])
                 if e.damage_id.casefold() in factors and (e.source_character_id or RAVEN) == RAVEN else e
                 for e in evidence)


# ── 1051 「零」 ───────────────────────────────────────────────────────────────

@RULES.hook("gate", ZERO, name="zero_extra_hit")
def _zero_extra_hit(ctx, ev):
    """Base kit: ONE extra hit per 「铭隙鉴刻」 cast at the earliest Kill offset (the axis binds lv1 and lv2 to all
    three Skill notifies = six hits at every level); Effect6 makes it the 300 % lv2 GE."""
    if ev.action[0] != ZERO_E:
        return None
    offsets = [min(offs) for ge, offs in ev.effect_hit_offsets if ge in ZERO_KILL and offs]
    if not offsets:
        return None
    hits = tuple((ge, offs) for ge, offs in ev.effect_hit_offsets if ge not in ZERO_KILL)
    if zero_target_too_high(ev.target, ctx.member):
        return hits                  # both texts: no extra hit vs a target of a higher level than Zero
    if READINGS["zero_equal_level"] == "strict" and not ctx.member.has("Effect1"):
        return hits                  # base text 等级低于: no hit vs an equal-level target without Effect1
    keep = ZERO_KILL[1] if ctx.member.has("Effect6") else ZERO_KILL[0]
    return hits + ((keep, (min(offsets),)),)


def zero_target_too_high(target, member) -> bool:
    """Both texts: no extra hit vs a target of a higher level than Zero (custom cycles allow enemy levels 1-100).
    ``target`` = the run's target dict (GateEvent.target; None = DEFAULT_TARGET, Lv80)."""
    member_level = int(member.character.get("character_level") or member.profile.get("character_level") or 80)
    return int((target or {}).get("enemy_level") or 80) > member_level


def zero_q_bonus(build: dict, rate: float, cap: float) -> float | None:
    """Effect4: min(rate x (character base ATK + arc base ATK), cap) from the enriched build (upstream audit
    AWAKEN-1046-Effect4); None when the build shows no base ATK."""
    for c in (build or {}).get("characters") or ():
        if int(c.get("character_id") or 0) != ZERO:
            continue
        stats = list(c.get("stats") or ())
        base = sum(float(r.get("value") or 0.0) for r in stats
                   if r.get("property_id") == "AtkBase" and r.get("source_group") in ("character", "fork"))
        if base <= 0.0:
            base = sum(float(r.get("value") or 0.0) for r in stats
                       if r.get("property_id") == "AtkBase" and r.get("source_group") == "resolved")
        return min(float(rate) * base, float(cap)) if base > 0.0 else None
    return None


@RULES.hook("prepare", ZERO, nodes=("Effect1", "Effect4", "Effect6"))
def _zero_prepare(ctx):
    """Effect4's numbers; its nodes also name ① / ⑥ in the explanation's applied rules (the base-kit gate above
    lays out ⑥'s lv2 hit and carries ①'s fix)."""
    t = tables(ctx.con)
    data = _params(t, ZERO)
    data["q_tags"] = t["tags"].get(_CURVES[ZERO]["e3_crit"], ())    # Effect3 / passive 2: Zero's Q hits
    return data


@RULES.hook("buff_rules", ZERO, nodes=("Effect4",))
def _zero_rules(ctx, static, build, rules):
    data = ctx.data or {}
    rate, cap, tags = _value(data, "e4_rate"), _value(data, "e4_cap"), tuple(data.get("q_tags") or ())
    value = zero_q_bonus(build, rate, cap) if rate is not None and cap is not None else None
    if value is None or not tags:
        return rules
    return _replace_rules(rules, [_rule(ZERO, "Effect4", _name(build, ZERO), "self", _STATIC, None,
                                        [("DamageUpGeneralBase", value, tags)])])


# ── 1052 Hotori (浔) ──────────────────────────────────────────────────────────
_HOTORI_NODES = ("Effect1", "Effect2", "Effect5", "Effect6", "resonance_6")


@RULES.hook("prepare", HOTORI, nodes=_HOTORI_NODES)
def _hotori_prepare(ctx):
    t = tables(ctx.con)
    data = _params(t, HOTORI)
    data["stop_cap_s"] = t["durations"].get("hotori_stop_cap")
    data["notify"] = t["notify"]
    return data


@RULES.hook("buff_rules", HOTORI, nodes=("Effect5", "resonance_6"))
def _hotori_rules(ctx, static, build, rules):
    """⑤ and 共鸣6 to the whole team (DB HTGlobalGameplayEffectComponent + text 全队); the 'single enemy' condition
    of ⑤ is the efficiency / team target itself."""
    data, new = ctx.data, []
    name = _name(build, HOTORI)
    for node, key in (("Effect5", "e5_dmg"), ("resonance_6", "r6_atk")):
        if ctx.member.has(node) and _prop(data, key) and _value(data, key) is not None:
            new.append(_rule(HOTORI, node, name, "team", _STATIC, None, [(_prop(data, key), _value(data, key), ())]))
    return _replace_rules(rules, new) if new else rules


def _montage_offset_us(run, action, table: dict) -> int | None:
    cand = run.ctx.by_key.get(tuple(action)) if run is not None else None
    path = str(getattr(cand, "montage_asset_path", "") or "").rsplit("/", 1)[-1].casefold()
    seconds = table.get(path) if path else None
    return None if seconds is None else int(round(float(seconds) * 1_000_000))


def hotori_stop_windows(analysis, cap_s: float, enter_offset_us: int | None = None) -> list:
    """[(Q action, start, end)] of her time stop per Q: from the end of GA_Jin_UltraSkill (text: the 10 hits, then the
    stop; READINGS enter_time_stop: Q start + ``enter_offset_us``, the Q montage's EnterTimeStop notify) to the tachi
    finisher hit (READINGS in / out), capped at the node buffs' life (active clock) and the fight end."""
    end = int(analysis.battle_end_us)
    hits = sorted(analysis.hits, key=lambda h: h.relative_time_us)
    out = []
    for a in _actions(analysis):
        if a.character_id != HOTORI or a.action_name != HOTORI_Q:
            continue
        s = a.end_us + 1
        if READINGS["hotori_window_start"] == "enter_time_stop" and enter_offset_us is not None:
            s = a.start_us + int(enter_offset_us)
        fin = next((h for h in hits if h.character_id == HOTORI and h.relative_time_us > s
                    and HOTORI_FINISHER in str(h.gameplay_effect_id).casefold()), None)
        e = (fin.relative_time_us + (1 if READINGS["hotori_finisher"] == "in" else 0)) if fin is not None else end
        out.append((a, s, min(e, _active_end(analysis, s, cap_s), end + 1)))
    return out


def hotori_record_counts(e_windows, q_starts, records, cap: int = HOTORI_RECORD_MAX) -> list:
    """Effect1: recorded teammates per Q.  ``e_windows`` = [(E start, window start, window end)] of her E casts,
    ``q_starts`` = her Q starts, ``records`` = [(teammate id, record time)].  A Q replays the records of the last E
    cast before it (and after the previous Q; a new E overwrites the earlier records); a teammate counts once, at
    most ``cap``, only for record times inside that E's window and before the Q."""
    counts = []
    previous = None
    for q in sorted(q_starts):
        casts = [w for w in e_windows if w[0] < q and (previous is None or w[0] > previous)]
        previous = q
        if not casts:
            counts.append(0)
            continue
        _e, ws, we = max(casts)
        seen = {int(cid) for cid, t in records if int(cid) != HOTORI and ws <= t <= we and t < q}
        counts.append(min(len(seen), int(cap)))
    return counts


@RULES.hook("placed", HOTORI, nodes=("Effect1",), members="all", name="hotori_action_log")
def _hotori_log(ctx, ev):
    """No-op: keeps the layout's action log (run.placed) for the Effect1 record window."""
    return None


@RULES.hook("intervals", HOTORI, nodes=("Effect1", "Effect2", "Effect6"))
def _hotori_windows(ctx, run, analysis):
    data = ctx.data or {}
    cap_s = data.get("stop_cap_s")
    if not cap_s:
        return analysis
    notify = data.get("notify") or {}
    enter = None
    if READINGS["hotori_window_start"] == "enter_time_stop":
        q_key = next((k for k in run.ctx.by_key if k[0] == HOTORI_Q), None)
        enter = _montage_offset_us(run, q_key, notify.get("enter_stop") or {}) if q_key is not None else None
    stops = hotori_stop_windows(analysis, cap_s, enter)
    extra = []
    merged = _merge([(s, e) for _a, s, e in stops])
    for node, key in (("Effect2", "e2_dmg"), ("Effect6", "e6_def")):
        prop, value = _prop(data, key), _value(data, key)
        if ctx.member.has(node) and prop and value is not None and not _priced(analysis, HOTORI, node):
            extra.extend(_interval(HOTORI, node, i, s, e, ((prop, value, ()),)) for i, (s, e) in enumerate(merged))
    prop, value = _prop(data, "e1_dmg"), _value(data, "e1_dmg")
    if ctx.member.has("Effect1") and prop and value is not None and stops and not _priced(analysis, HOTORI, "Effect1"):
        e_windows, records = [], []
        for pa in run.placed:
            if pa.character_id == HOTORI and pa.action[0] == HOTORI_E:
                opened = _montage_offset_us(run, pa.action, notify.get("record_open") or {}) or 0
                ws = pa.start_us + opened
                e_windows.append((pa.start_us, ws, _active_end(analysis, ws, HOTORI_RECORD_S)))
            elif pa.character_id != HOTORI:
                at = _montage_offset_us(run, pa.action, notify.get("record") or {})
                if at is not None:                  # only E / support montages carry the record notify
                    records.append((pa.character_id, pa.start_us + at))
        counts = hotori_record_counts(e_windows, [a.start_us for a, _s, _e in stops], records)
        for i, ((_a, s, e), n) in enumerate(zip(stops, counts)):
            if n and e > s:
                extra.append(_interval(HOTORI, "Effect1", i, s, e, ((prop, value * n, ()),)))
    return _add_intervals(analysis, extra)


# ── 1055 Kuhara (九原) ────────────────────────────────────────────────────────

@RULES.hook("prepare", KUHARA, nodes=("Effect1", "Effect5", "resonance_6"))
def _kuhara_prepare(ctx):
    return _params(tables(ctx.con), KUHARA)


@RULES.hook("buff_rules", KUHARA, nodes=("Effect5",))
def _kuhara_rules(ctx, static, build, rules):
    """⑤'s generic static rule (requirement Con_Kuhara_TargetHaveAttachment) never reaches a hit (the upstream hit
    service rejects the requirement: 0 before this rule); the contract-window interval replaces it."""
    def_id = f"character_awaken:{KUHARA}:Effect5"
    return tuple(r for r in tuple(rules) if r.source_effect_definition_id != def_id)


def kuhara_contract_windows(analysis) -> list:
    """[start, end] of 「致命玫约」 on the dummy (Buff_Kuhara_Attachment, Infinite): from the end of each E to the end
    of the fight (READINGS until_q: to the end of her next Q, else the 5 s seed)."""
    end = int(analysis.battle_end_us)
    acts = _actions(analysis)
    windows = []
    for a in acts:
        if a.character_id != KUHARA or a.action_name != KUHARA_E:
            continue
        s = a.end_us + 1
        if READINGS["kuhara_window"] == "fight":
            e = end + 1
        else:
            q = next((b for b in acts if b.character_id == KUHARA and b.input_kind == "Q" and b.start_us > a.start_us),
                     None)
            e = (q.end_us + 1) if q is not None else min(end + 1, _active_end(analysis, s, KUHARA_SEED_S))
        windows.append((s, e))
    return _merge(windows)


@RULES.hook("intervals", KUHARA, nodes=("Effect1", "Effect5", "resonance_6"))
def _kuhara_windows(ctx, run, analysis):
    data = ctx.data
    windows = kuhara_contract_windows(analysis)
    if not windows:
        return analysis
    target = _target(analysis)
    extra = []
    for node, key, scope in (("Effect1", "e1_atk", "self"), ("Effect5", "e5_dmg", "self"),
                             ("resonance_6", "r6_res", "target")):
        prop, value = _prop(data, key), _value(data, key)
        if not ctx.member.has(node) or not prop or value is None or _priced(analysis, KUHARA, node):
            continue
        extra.extend(_interval(KUHARA, node, i, s, e, ((prop, value, ()),), scope=scope,
                               target_id=target if scope == "target" else "") for i, (s, e) in enumerate(windows))
    return _add_intervals(analysis, extra)


# ── 1057 Akane Rin (明音凛): CN release data (global_live_overlay) ──────────────────────
# Every rule runs only while the overlay is on for the run's DB (dataset id + sha); otherwise the 9-24 DB rules stay
# and nothing here changes a number.  Values: global_live_overlay_data (release values; DB values read where unchanged).
_AKANE_NODES = ("Effect2", "Effect4", "Effect6", "resonance_6")


@RULES.hook("prepare", AKANE, name="akane_release_overlay")
def _akane_prepare(ctx):
    """Base kit: the overlay groups on for this DB.  Off: core.INACTIVE_KEY keeps her rules out of the explanation."""
    from src.services import global_live_overlay as glo
    from src.services.awakening_node_rules.core import INACTIVE_KEY

    awakening = glo.active_for_con(ctx.con, "awakening")
    return {"awakening": awakening, "passive2": glo.active_for_con(ctx.con, "passive2"), INACTIVE_KEY: not awakening}


@RULES.hook("buff_rules", AKANE, name="akane_release_db_buffs_off")
def _akane_db_buffs_off(ctx, static, build, rules):
    """The 9-24 DB awakening buffs the release removed (① crit, 共鸣3 ATK) are dropped; the skill level +1 of 共鸣3 is
    not a buff rule (character_awaken_skill_level_bonus) and stays."""
    from src.services.global_live_overlay_data import SUPPRESS_RULES

    if not (ctx.data or {}).get("awakening"):
        return rules
    out = []
    for rule in tuple(rules):
        drop = SUPPRESS_RULES.get(rule.source_effect_definition_id)
        if drop is None:
            out.append(rule)
            continue
        kept = tuple(m for m in rule.modifiers if m.property_id not in drop)
        if kept:
            out.append(dataclasses.replace(rule, modifiers=kept))
    return tuple(out)


def akane_ult_starts(analysis) -> list:
    """Stage-1 ultimate (GA_Akane_UltraSkill) cast starts: the 烁星激昂 triggers."""
    from src.services.global_live_overlay_data import PASSIVE2

    return [a.start_us for a in _actions(analysis) if a.character_id == AKANE and a.action_name == PASSIVE2["trigger"]]


def akane_synced_hits(analysis) -> list:
    """Hit times of 同调共振 (GE_Player_Akane_UpgradeSkill_Damage; both forms)."""
    from src.services.global_live_overlay_data import SYNCED_RESONANCE_GE

    ge = SYNCED_RESONANCE_GE.casefold()
    return sorted(int(h.relative_time_us) for h in analysis.hits
                  if h.character_id == AKANE and str(h.gameplay_effect_id).casefold() == ge)


def akane_e_starts(layout) -> list:
    """Tap / hold E casts of the layout (泛音列 / 音域; the tapped E has no damage row on the axis, G6)."""
    from src.services.global_live_overlay_data import HOLD_E, TAP_E

    keys = {TAP_E, HOLD_E}
    return sorted(int(s.start_us) for v in getattr(layout, "visits", ()) or () if v.character_id == AKANE
                  for s in v.steps if (s.ability_id, s.selector) in keys and s.status == "ok")


def akane_windows(analysis, starts, seconds: float) -> list:
    """Merged windows of ``seconds`` active time from each start (a new start refreshes)."""
    end = int(analysis.battle_end_us)
    return _merge([(int(s), min(end, _active_end(analysis, int(s), float(seconds)))) for s in starts if s < end])


def _akane_interval(node: str, index: int, start: int, end: int, prop: str, value: float, scope: str = "self",
                    target_id: str = "", kind: str = SOURCE_KIND):
    iv = _interval(AKANE, node, index, start, end, ((prop, value, ()),), scope=scope, target_id=target_id)
    if kind != SOURCE_KIND:
        iv = dataclasses.replace(iv, source_kind=kind, interval_id=f"global:passive:{AKANE}:{node}:{index}",
                                 buff_asset_path=f"global-passive:{AKANE}:{node}",
                                 buff_name=f"Global passive: {AKANE} {node}",
                                 source_effect_definition_id=f"character_passive:{AKANE}:{node}")
    return dataclasses.replace(iv, inference_basis="Global live overlay: CN release data (2026-10-15), "
                                                   "work_g231/awaken/akane_cn/akane_overlay_spec.json")


@RULES.hook("intervals", AKANE, name="akane_release_passive2")
def _akane_passive2(ctx, run, analysis):
    """Base kit: 烁星激昂 self ATK +20 % for 20 s from each stage-1 ultimate start (breakthrough 4: every Lv80 build)."""
    from src.services.global_live_overlay_data import PASSIVE2

    if not (ctx.data or {}).get("passive2"):
        return analysis
    windows = akane_windows(analysis, akane_ult_starts(analysis), PASSIVE2["duration_s"])
    extra = [_akane_interval("Passive_2", i, s, e, PASSIVE2["property"], PASSIVE2["value"],
                             kind="global_passive_supplement") for i, (s, e) in enumerate(windows)]
    return _add_intervals(analysis, extra)


@RULES.hook("intervals", AKANE, nodes=_AKANE_NODES, name="akane_release_nodes", order=1)
def _akane_nodes(ctx, run, analysis):
    """② / ④ / ⑥ / 共鸣6 windows (CN release values)."""
    from src.services.global_live_overlay_data import AWAKEN, PASSIVE2, START_READING

    if not (ctx.data or {}).get("awakening"):
        return analysis
    member = ctx.member
    extra = []
    synced = akane_synced_hits(analysis)
    shift = 0 if START_READING == "before" else 1          # "after": the 同调共振 hit itself is not covered
    for node in ("Effect4", "resonance_6"):
        rule = AWAKEN[node]
        if member.has(node):
            windows = akane_windows(analysis, [t + shift for t in synced], rule["duration_s"])
            extra.extend(_akane_interval(node, i, s, e, rule["property"], rule["value"])
                         for i, (s, e) in enumerate(windows))
    if member.has("Effect6"):
        rule = AWAKEN["Effect6"]
        windows = akane_windows(analysis, akane_ult_starts(analysis), PASSIVE2["duration_s"])
        extra.extend(_akane_interval("Effect6", i, s, e, rule["property"], rule["value"])
                     for i, (s, e) in enumerate(windows))
    if member.has("Effect2"):
        rule = AWAKEN["Effect2"]
        windows = akane_windows(analysis, akane_e_starts(run.layout), rule["duration_s"])
        target = _target(analysis)
        extra.extend(_akane_interval("Effect2", i, s, e, rule["property"], rule["value"], scope="target",
                                     target_id=target) for i, (s, e) in enumerate(windows))
    return _add_intervals(analysis, extra)


@RULES.hook("evidence", AKANE, nodes=("resonance_3",), name="akane_release_fixed_rates")
def _akane_fixed_rates(ctx, run, evidence):
    """共鸣3: fixed multipliers added to the hit's rate (同调共振 +8.0, stage 2 +10.0; not scaled by the skill level)."""
    from src.services.global_live_overlay_data import AWAKEN

    if not (ctx.data or {}).get("awakening"):
        return evidence
    add = {ge.casefold(): float(v) for ge, v in AWAKEN["resonance_3"]["fixed_rate"].items()}
    return tuple(dataclasses.replace(e, scaling_multiplier=float(e.scaling_multiplier) + add[e.damage_id.casefold()])
                 if e.damage_id.casefold() in add and (e.source_character_id or AKANE) == AKANE else e
                 for e in evidence)


# ── node metadata (efficiency-table class, bucket, confidence, flags, sentences) ──
# ko = the reviewed assumption sentence (group_2.json assumption_ko); the sentences a tooltip shows (low confidence:
# assumption; needs measurement / not computable: reason) carry zh / en / ja too.
_K = {
    (RAVEN, "Effect1"): "「속세를 건너는 죽음의 불꽃」 피해 배율 +150%는 기존 배율에 ×2.5를 곱하는 것으로 해석했고, "
                        "'악의 전부 소모' 부분은 계산기에 악의 시스템이 없어서 빠집니다.",
    (RAVEN, "Effect2"): "「장송의 깃털」 배율 +100%는 그 E의 피해 효과에 ×2를 곱하는 것으로 해석했습니다(게임 "
                        "데이터에서 이 돌파 효과의 계산 클래스가 바로 그 피해 효과에 붙어 있음).",
    (RAVEN, "Effect4"): "「모든 영혼에 안식을」 시전 후 마녀 변신 시점(시전 +3.167초)부터 25초(시간 정지 제외) 동안 팀 전체 피해 +12%로 계산하며, 기본 팀 공격력 +20% 버프는 계산기에 아직 없어서 '25초로 연장' 효과는 그 기본 버프를 넣은 뒤에야 반영됩니다.",
    (RAVEN, "Effect5"): "레이븐의 모든 타격 직후부터 25초 동안 대상의 혼·상·암 저항이 8% 내려가고, 다시 맞히면 25초가 갱신되는 것으로 계산합니다.",
    (RAVEN, "Effect6"): "「모든 영혼에 안식을」 시전 후(마녀 변신 시점) 25초 동안 레이븐 자신의 혼 속성 피해 +25%로 "
                        "계산하고, 「실낙조」 협동 공격의 악의 +4는 악의 시스템이 없어 빠집니다.",
    (RAVEN, "resonance_3"): "3회 공명의 두 궁극기 배율 증가(+100%·+50%)는 각 궁극기 피해 효과에 ×2·×1.5를 곱하는 "
                            "것으로 해석했고, 악의 +20은 악의 시스템이 없어 빠집니다.",
    (RAVEN, "resonance_6"): "레이븐이 팀에 있으면 전투 내내 팀 전원(자신 포함)의 치명타 피해 +30%로 계산합니다.",
    (ZERO, "Effect1"): "제로 E의 추가 피해는 E 1회에 1번(처음 맞은 대상)만 넣고(시뮬레이션 타임라인에는 원래 6번), "
                       "기본 E 설명은 '자신보다 레벨이 낮은 적'인데 돌파 효과 ①은 '레벨이 높지 않은 적'이라 레벨이 "
                       "같은 기본 대상(80 대 80)에서는 해석이 갈리므로, 돌파 0에도 200% 1회가 들어간다고 "
                       "계산했습니다(설명문 그대로면 돌파 0에서는 0회이고 이 효과 값이 +6.35%가 아니라 +19.59%).",
    (ZERO, "Effect2"): "E 성공 후 울티메이트 에너지 +8이며, 원본 계산기 분석은 '8×충전 효율'로 보지만 Global 자원 "
                       "계산은 이벤트 에너지에 충전 효율을 곱하지 않는 쪽으로 두었고, 제로의 Q 비용을 몰라 강제하지 "
                       "않으므로 지금은 1인·팀 DPS가 변하지 않습니다.",
    (ZERO, "Effect3"): "Q 치명타 확률 +50%(상한 100%)이며 이미 계산되고 있습니다.",
    (ZERO, "Effect4"): "제로의 기초 공격력이 80레벨에서 676이라 Q 피해 증가는 항상 상한 25%로 계산합니다.",
    (ZERO, "Effect5"): "서포트 스킬로 들어올 때만 켜지므로 1인 표에서는 0이 정상이고, 팀 시뮬은 게임 데이터 "
                       "트리거(QTE 시작)대로 그 QTE 자신에도 공격력 +10%를 주지만 원본 계산기 분석은 QTE가 끝난 "
                       "뒤부터로 보며, 검수 팀 사이클에는 제로의 서포트 스킬 입장이 없어 팀에서도 보통 0입니다.",
    (ZERO, "Effect6"): "돌파 효과 ⑥은 그 추가 피해 1회의 배율을 200%에서 300%로 바꿀 뿐 타격을 늘리지 않으며, ① 없이 "
                       "골라도 300%로 적용합니다(방어 무시는 ①이 있을 때만; 기본 E 설명대로 '레벨이 낮은 적'만 "
                       "맞는다고 보면 레벨이 같은 기본 대상에서는 ① 없이 ⑥만 고를 때 0).",
    (ZERO, "resonance_3"): "스킬 레벨 +1이며 추가 피해 1회는 레벨과 무관한 고정 배율입니다.",
    (ZERO, "resonance_6"): "팀 시뮬에서 제로의 서포트 스킬 입장은 항상 사이클 반응과 함께 일어나므로, 그 입장을 '빛 "
                           "관련 사이클 반응 발동'으로 보고 팀 공격력 +12%(20초)를 겁니다.",
    (HOTORI, "Effect1"): "호토리 E 시전 후 5초(시간 정지 제외) 안에 E나 서포트 스킬을 쓴 서로 다른 팀원 수(최대 3)만큼 다음 시간 정지 동안 호토리 피해 +12%씩 주며, 1인에서는 기록할 팀원이 없어 0입니다.",
    (HOTORI, "Effect5"): "설명문과 게임 데이터(팀 전체 적용 표시인 HTGlobal 구성요소)가 모두 팀 전체라서 팀원에게도 "
                         "+15%를 주며, '적이 하나뿐' 조건은 효율표 대상과 같아 항상 참으로 봅니다.",
    (HOTORI, "resonance_3"): "스킬 레벨 +1이며 이미 계산되고 있습니다.",
    (HOTORI, "resonance_6"): "설명문대로 팀 전원 공격력 +30%로 범위를 바꿉니다(지금 팀 시뮬은 호토리 자신만 받음).",
    (DAFFODILL, "Effect1"): "팀원의 서포트 스킬 스택이 있어야 켜지므로 1인 0이 정상이고, 붕괴 수치 부분은 계산기에 "
                            "붕괴가 없어 빠집니다.",
    (DAFFODILL, "Effect6"): "방어 15% 무시이며 이미 계산되고 있습니다.",
    (DAFFODILL, "resonance_3"): "스킬 레벨 +1이며 이미 계산되고 있습니다.",
    (KUHARA, "Effect1"): "목각인형 하나가 구원의 E 이후 전투 끝까지 계속 「위험한 장미의 약속」 상태라고 보고 공격력 "
                         "+5%(대상 1명)로 계산합니다.",
    (KUHARA, "Effect5"): "1번과 같은 부착 구간(E 이후 전투 끝까지) 동안 구원의 피해 +8%로 계산합니다.",
    (KUHARA, "resonance_3"): "스킬 레벨 +1이며 이미 계산되고 있습니다.",
    (KUHARA, "resonance_6"): "부착 구간(E 이후 전투 끝까지) 동안 대상의 령속성 저항 -10%로 계산합니다.",
    (AKANE, "Effect2"): "「배음렬」(탭 E)이나 「음역」(홀드 E)을 쓴 순간부터 25초(시간 정지 제외) 동안 대상의 상속성 "
                        "저항 -12%로 계산하며 팀원의 상속성 피해에도 적용합니다(CN 출시 데이터, 출시 전 게임 "
                        "데이터의 전 속성 -7.5%·음역 피해 +12.5%는 쓰지 않음).",
    (AKANE, "Effect4"): "「동조 공진」 타격 직전부터 15초(시간 정지 제외) 동안 치명타 피해 +30%로 계산하며 그 「동조 공진」 타격 자체에도 붙습니다(CN 출시 데이터; 타격 직후부터라면 그 1타가 빠집니다).",
    (AKANE, "Effect6"): "패시브 「반짝이는 별의 격정」 동안(울티메이트 1단 시전부터 20초, 시간 정지 제외) 아카네 린 "
                        "자신의 방어 무시 +16%로 계산합니다(CN 출시 데이터; 출시 전 게임 데이터의 파티 피해 +10%는 "
                        "삭제).",
    (AKANE, "resonance_3"): "스킬 레벨 +1(이미 계산)에 더해 「동조 공진」 배율 +800%·울티메이트 2단 배율 +1000%를 스킬 레벨과 무관한 고정값으로 더하고, 출시판에서 삭제된 공격력 +20%는 끕니다(CN 출시 데이터). 전투 시작 시 현 에너지 가득은 그 자원이 계산기에 없어 사이클을 바꾸지 않습니다.",
    (AKANE, "resonance_6"): "「동조 공진」 타격 직전부터 25초(시간 정지 제외) 동안 치명타 피해 +64%로 계산하고(CN "
                            "출시 데이터), 현 에너지 반환은 그 자원이 계산기에 없어 사이클을 바꾸지 않습니다.",
}
# shown in tooltips: {lang: sentence}
_SHOWN = {
    (RAVEN, "Effect3"): {
        "ko": "악의 획득·소모와 그 추가 피해 타격이 계산기에 없어서, 이 돌파 효과는 그 기본 메커니즘을 먼저 만들기 "
              "전에는 계산할 수 없습니다.",
        "zh": "计算器尚未模拟「恶意」的获取、消耗及其追加伤害，需先补上这一基础机制才能计算该效果。",
        "en": "The calculator does not track 「Malice」 gain / consumption or its extra-damage hits, so this effect "
              "cannot be computed until that base mechanic exists.",
        "ja": "「悪意」の獲得・消費とその追加ダメージが計算機にないため、この基本メカニズムを先に実装するまで計算できません。"},
    (HOTORI, "Effect2"): {
        "ko": "호토리의 시간 정지(이 효과가 켜지는 구간)는 설명문대로 궁극기 10타가 끝난 뒤부터 태도 종결 공격(포함, "
              "게임 데이터 몽타주에서 종결 타격이 시간 정지 해제 신호보다 앞섬)까지로 계산했지만, 게임 데이터 "
              "몽타주의 '시간 정지 진입' 신호는 10타보다 먼저(시전 2.18초)라 10타도 포함될 수 있고 그러면 값이 "
              "+4.37%에서 +8.07%로 커집니다.",
        "zh": "浔的时停（该效果生效的区间）按技能描述计为终结技10段命中结束后到太刀终结一击（含；游戏数据动画中终结一"
              "击早于解除时停信号）为止；但 游戏数据动画的「进入时停」信号早于10段命中（施放后2.18秒），若这10段也算"
              "在内，数值会从 +4.37% 升至 +8.07%。",
        "en": "Hotori's time stop (when this effect applies) is taken, as the description says, from the end of the "
              "ultimate's 10 hits up to and including the tachi finisher (in the game data montage the finisher hit "
              "comes before the stop-release notify). The game data montage's 'enter time stop' notify fires before "
              "the 10 hits (2.18 s into the cast), so they may count too, which would raise the value from +4.37% to "
              "+8.07%.",
        "ja": "浔の時間停止（この効果が有効な区間）は説明文どおりアルティメット10段ヒットの後から太刀の締め攻撃（含む"
              "。ゲームデータモンタージュでは締めのヒットが停止解除シグナルより先）までとしたが、ゲームデータモンター"
              "ジュの「時間停止開始」シグナルは10段ヒットより前（発動2.18秒）にあり、10段も含まれる場合は値が +4.37% "
              "から +8.07% に上がる。"},
    (HOTORI, "Effect3"): {
        "ko": "E로 쓴 시계 에너지 60을 기록이 끝난 뒤 돌려받지만(60초에 1번), 언제부터 얼마나 빨리 차는지가 데이터에 없어 지금은 '즉시 환급' 상한만 계산할 수 있습니다.",
        "zh": "记录完成后会返还变轨技能消耗的60点时计能量（每60秒一次），但何时开始、回复多快不在数据中，目前只能算出「立即返还」的上限。",
        "en": "The 60 clock energy her E spent comes back after the recording ends (once per 60 s), but when the "
              "refill starts and how fast it runs are not in the data, so only an 'instant refund' upper bound can "
              "be computed for now.",
        "ja": "記録完了後にスキルで消費した時計エネルギー60が戻る（60秒に1回）が、開始時点と回復速度がデータにないた"
              "め、現在は「即時返還」の上限しか計算できない。"},
    (HOTORI, "Effect4"): {
        "ko": "처치가 없는 단일 목각인형 기준이라 효과가 0입니다.",
        "zh": "计算对象是不会被击败的单个木桩，没有击败事件，因此该效果不改变伤害。",
        "en": "The target is a single dummy that is never defeated, so this effect never triggers.",
        "ja": "対象は倒されない単体の木人なので、撃破が発生せずこの効果は発動しない。"},
    (HOTORI, "Effect6"): {
        "ko": "돌파 효과 ②와 같은 시간 정지 구간(궁극기 10타 후 ~ 종결 공격 포함) 동안 방어 30% 무시로 계산하며, "
              "구간이 '시간 정지 진입'(10타 전)부터라면 값이 +9.45%에서 +17.44%로 커집니다.",
        "zh": "在与效果②相同的时停区间（终结技10段命中后至太刀终结一击，含）内计为无视30%防御；若区间从「进入时停」（10段命中前）开始，数值会从 +9.45% 升至 +17.44%。",
        "en": "Ignores 30% DEF during the same time stop as effect ② (after the ultimate's 10 hits up to and "
              "including the finisher); if the stop starts at the 'enter time stop' notify (before the 10 hits), "
              "the value rises from +9.45% to +17.44%.",
        "ja": "効果②と同じ時間停止区間（アルティメット10段ヒット後〜締め攻撃を含む）の間、防御30%無視とする。区間が「"
              "時間停止開始」（10段ヒット前）からなら値は +9.45% から +17.44% に上がる。"},
    (DAFFODILL, "Effect2"): {
        "ko": "반격 실패를 일부러 넣는 별도 사이클이 필요하고 그 고배율 타격 수치도 데이터에서 찾지 못해 계산하지 않습니다.",
        "zh": "需要一套故意让反击失败的独立循环，且该高倍率攻击的数值也未在数据中找到，因此不计算。",
        "en": "This needs a separate rotation that fails the counter on purpose, and the high-multiplier hit's "
              "value is not in the data, so it is not computed.",
        "ja": "反撃をわざと失敗させる別のローテーションが必要で、その高倍率攻撃の数値もデータにないため計算しない。"},
    (DAFFODILL, "Effect3"): {
        "ko": "통찰은 대상이 붕괴될 때만 의미가 있고 계산기 대상은 붕괴되지 않으므로 0입니다.",
        "zh": "「洞察」只在目标进入倾陷时才有意义，而计算对象不会倾陷，因此不改变伤害。",
        "en": "Insight only matters once the target is toppled, and the simulated target is never toppled.",
        "ja": "「洞察」は対象が崩壊（傾陥）したときだけ意味があり、計算対象は崩壊しないためダメージは変わらない。"},
    (DAFFODILL, "Effect4"): {
        "ko": "붕괴 피해에만 붙는데 계산기는 붕괴를 시뮬레이션하지 않으므로 0입니다.",
        "zh": "只作用于倾陷伤害，而计算器不模拟倾陷，因此不改变伤害。",
        "en": "It only boosts topple damage, and the calculator does not simulate topple.",
        "ja": "崩壊（傾陥）ダメージにのみ作用し、計算機は崩壊をシミュレーションしないためダメージは変わらない。"},
    (DAFFODILL, "Effect5"): {
        "ko": "대상이 붕괴에 들어갈 때만 발동하므로 0입니다.",
        "zh": "只在目标进入倾陷时触发，因此不改变伤害。",
        "en": "It only triggers when the target becomes toppled.",
        "ja": "対象が崩壊（傾陥）したときだけ発動するためダメージは変わらない。"},
    (DAFFODILL, "resonance_6"): {
        "ko": "붕괴 중에만 저항이 내려가므로 붕괴가 없는 계산기에서는 0입니다.",
        "zh": "只在目标倾陷期间降低抗性，计算器没有倾陷，因此不改变伤害。",
        "en": "The resistance only drops while the target is toppled, which the calculator never simulates.",
        "ja": "崩壊（傾陥）中にのみ耐性が下がり、計算機には崩壊がないためダメージは変わらない。"},
    (KUHARA, "Effect2"): {
        "ko": "장미 약속의 1초 주기 피해 자체가 시뮬레이션 타임라인에 없어서, 그 기본 피해를 먼저 넣어야 이 "
              "효과(×2)가 숫자로 나옵니다.",
        "zh": "「致命玫约」每秒一次的伤害本身尚未放入时间轴，需先补上这一基础伤害，该效果（×2）才会有数值。",
        "en": "The contract's 1 s periodic damage is not in the simulation timeline yet; that base damage has to be "
              "added before this effect (x2) shows a number.",
        "ja": "「致命玫約」の1秒ごとのダメージ自体がまだ時間軸にないため、その基本ダメージを先に入れないとこの効果（×2）は数値にならない。"},
    (KUHARA, "Effect3"): {
        "ko": "붕괴 수치만 깎으므로 붕괴가 없는 계산기에서는 0입니다.",
        "zh": "只削减倾陷值，计算器没有倾陷，因此不改变伤害。",
        "en": "It only removes topple value, which the calculator does not simulate.",
        "ja": "崩壊（傾陥）値を削るだけで、計算機には崩壊がないためダメージは変わらない。"},
    (KUHARA, "Effect4"): {
        "ko": "Q의 계약 청산 타격 자체가 시뮬레이션 타임라인에 없어서, 그 기본 타격을 먼저 넣어야 이 효과(+50%)가 "
              "숫자로 나옵니다.",
        "zh": "终结技触发的「致约清算」伤害本身尚未放入时间轴，需先补上这一基础伤害，该效果（+50%）才会有数值。",
        "en": "The settlement hits her ultimate triggers are not in the simulation timeline yet; they have to be "
              "added before this effect (+50%) shows a number.",
        "ja": "アルティメットで発動する「致約清算」のダメージ自体がまだ時間軸にないため、その基本ダメージを先に入れな"
              "いとこの効果（+50%）は数値にならない。"},
    (KUHARA, "Effect6"): {
        "ko": "적이 스킬을 쓸 때만 발동하는데 목각인형는 스킬을 쓰지 않으므로 0입니다.",
        "zh": "只在敌人释放技能时触发，而木桩不会释放技能，因此不改变伤害。",
        "en": "It only triggers when the enemy uses a skill, and the dummy never does.",
        "ja": "敵がスキルを使ったときだけ発動し、木人はスキルを使わないためダメージは変わらない。"},
    (AKANE, "Effect1"): {
        "ko": "CN 출시판 ①은 치명타 확률 +12%가 삭제되고 「동조 공진」 때의 회복·방어력 +50%·경직 저항 +60%(15초)만 "
              "남아 목각인형 피해가 바뀌지 않습니다(출시 전 게임 데이터의 치명타 버프는 끕니다).",
        "zh": "国服正式版的①删除了暴击率 +12%，只剩「同调共振」时的回复、防御力 +50% 与抗打断 +60%（15 秒），木桩伤害不变（上线前数据库的暴击 Buff 已关闭）。",
        "en": "In the CN release ① no longer gives +12% CRIT Rate; only healing, DEF +50% and interruption "
              "resistance +60% (15 s) on Synchronized Resonance remain, which do not change the damage on the dummy "
              "(the pre-release crit buff is switched off).",
        "ja": "中国版リリースの①は会心率 +12% が削除され、「同調共振」時の回復・防御力 +50%・中断耐性 "
              "+60%（15秒）のみとなるため、木人へのダメージは変わらない（リリース前ゲームデータの会心Buffは無効化）。"},
    (AKANE, "Effect3"): {
        "ko": "CN 출시판 ③은 탭 E에 고정 배율 +1000%(스킬 레벨 무관)를 더하지만, 탭 E의 피해 타격 자체가 시뮬레이션 "
              "타임라인에 없어(이벤트 태그 불일치) 그 기본 타격을 넣기 전에는 계산하지 않습니다.",
        "zh": "国服正式版的③为点按变轨技能增加 1000% 固定倍率（与技能等级无关），但点按变轨技能的伤害本身不在时间轴上（事件标签不一致），在补上这一基础伤害之前不计算。",
        "en": "In the CN release ③ adds a fixed +1000% multiplier (independent of the skill level) to the tapped E, "
              "but the tapped E's damage hit is not in the simulation timeline (event tag mismatch), so it is not "
              "computed until that base hit exists.",
        "ja": "中国版リリースの③はタップスキルに固定倍率 +1000%（スキルレベル無関係）を加えるが、タップスキルのダメー"
              "ジ自体が時間軸にない（イベントタグ不一致）ため、その基本ヒットを入れるまで計算しない。"},
    (AKANE, "Effect5"): {
        "ko": "CN 출시판 ⑤는 일반 공격 전도 배율을 64%(배음렬)·90%(음역)로 올리지만, 일반 공격 전도 자체가 계산기에 없어 기본 전도를 만들기 전에는 계산하지 않습니다.",
        "zh": "国服正式版的⑤把普通攻击传导提高到 64%（泛音列）与 90%（音域），但普通攻击的传导本身尚未模拟，在补上基础传导之前不计算。",
        "en": "In the CN release ⑤ raises the basic-attack transmission to 64% (Harmonic Series) and 90% (Sound "
              "Field), but the transmission itself is not simulated, so it is not computed until the base "
              "transmission exists.",
        "ja": "中国版リリースの⑤は通常攻撃の伝導を 64%（倍音列）・90%（音域）に引き上げるが、通常攻撃の伝導自体が計算"
              "機にないため、基本伝導を作るまで計算しない。"},
}

# (cid, node, category, bucket, confidence, scope)  - group_2.json (efficiency_category / bucket after the review)
_NODES = (
    (RAVEN, "Effect1", "damage", "now", "medium", "solo_team"),
    (RAVEN, "Effect2", "damage", "now", "medium", "solo_team"),
    (RAVEN, "Effect3", "unmodelled", "measure", "high", ""),
    (RAVEN, "Effect4", "damage", "now", "medium", "solo_team"),
    (RAVEN, "Effect5", "damage", "now", "high", "solo_team"),
    (RAVEN, "Effect6", "damage", "now", "medium", "solo_team"),
    (RAVEN, "resonance_3", "damage", "now", "medium", "solo_team"),
    (RAVEN, "resonance_6", "damage", "now", "high", "solo_team"),
    (ZERO, "Effect1", "damage", "now", "medium", "solo_team"),
    (ZERO, "Effect2", "resource", "now", "medium", "team_only"),
    (ZERO, "Effect3", "damage", "now", "high", "solo_team"),
    (ZERO, "Effect4", "damage", "now", "high", "solo_team"),
    (ZERO, "Effect5", "team", "now", "medium", "team_only"),
    (ZERO, "Effect6", "damage", "now", "medium", "solo_team"),
    (ZERO, "resonance_3", "damage", "now", "high", "solo_team"),
    (ZERO, "resonance_6", "team", "now", "medium", "team_only"),
    (HOTORI, "Effect1", "team", "now", "medium", "team_only"),
    (HOTORI, "Effect2", "damage", "now", "low", "solo_team"),
    (HOTORI, "Effect3", "review", "measure", "low", ""),
    (HOTORI, "Effect4", "none", "not_computable", "high", ""),
    (HOTORI, "Effect5", "damage", "now", "high", "solo_team"),
    (HOTORI, "Effect6", "damage", "now", "low", "solo_team"),
    (HOTORI, "resonance_3", "damage", "now", "high", "solo_team"),
    (HOTORI, "resonance_6", "damage", "now", "high", "solo_team"),
    (DAFFODILL, "Effect1", "team", "now", "high", "team_only"),
    (DAFFODILL, "Effect2", "rotation", "measure", "high", ""),
    (DAFFODILL, "Effect3", "none", "not_computable", "high", ""),
    (DAFFODILL, "Effect4", "none", "not_computable", "high", ""),
    (DAFFODILL, "Effect5", "none", "not_computable", "high", ""),
    (DAFFODILL, "Effect6", "damage", "now", "high", "solo_team"),
    (DAFFODILL, "resonance_3", "damage", "now", "high", "solo_team"),
    (DAFFODILL, "resonance_6", "none", "not_computable", "high", ""),
    (KUHARA, "Effect1", "damage", "now", "medium", "solo_team"),
    (KUHARA, "Effect2", "unmodelled", "measure", "high", ""),
    (KUHARA, "Effect3", "none", "not_computable", "high", ""),
    (KUHARA, "Effect4", "unmodelled", "measure", "high", ""),
    (KUHARA, "Effect5", "damage", "now", "medium", "solo_team"),
    (KUHARA, "Effect6", "none", "not_computable", "high", ""),
    (KUHARA, "resonance_3", "damage", "now", "high", "solo_team"),
    (KUHARA, "resonance_6", "damage", "now", "medium", "solo_team"),
    # Akane: CN release data (global_live_overlay; spec awakening_efficiency_categories_1057); the DB is still the
    # 9-24 pre-release one (pre-release flag: the tooltip shows the overlay's data line while it is on)
    (AKANE, "Effect1", "none", "not_computable", "high", ""),
    (AKANE, "Effect2", "damage", "now", "high", "solo_team"),
    (AKANE, "Effect3", "unmodelled", "measure", "high", ""),
    (AKANE, "Effect4", "damage", "now", "medium", "solo_team"),
    (AKANE, "Effect5", "unmodelled", "measure", "high", ""),
    (AKANE, "Effect6", "damage", "now", "high", "solo_team"),
    (AKANE, "resonance_3", "damage", "now", "high", "solo_team"),
    (AKANE, "resonance_6", "damage", "now", "medium", "solo_team"),
)
for _cid, _node, _category, _bucket, _confidence, _scope in _NODES:
    _shown = _SHOWN.get((_cid, _node))
    _text = _shown if _shown is not None else {"ko": _K[(_cid, _node)]}
    RULES.node(_cid, _node, category=_category, bucket=_bucket, confidence=_confidence, assumption=_text,
               reason=_text if _bucket != "now" else None, pre_release=_cid == AKANE, scope=_scope)
del _cid, _node, _category, _bucket, _confidence, _scope, _shown, _text
