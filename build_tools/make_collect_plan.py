"""Build teamsim_energy/data/collect_plan.json: the data-collection work list of design_final.md §12.

4 chunks x 6 template characters.  For every character: the resource fields the simulator still needs (or must
confirm), their current value with source / confidence, the measured bounds from the 3 recorded battles, the community
values, the preferred sources per field (in the workflow's data priority: static DB > measurement > official text >
community) and the acceptance rule that turns a measurement into an enforceable value.

Inputs (read-only): data/db_extract.json (names, elements, evade cooldown, own resources), data/measured.json (bounds),
web_raw/prydwen_skills_parsed.json (prydwen E/Q cooldowns and Q cost).  GameWith / mysqil values, page ids and dates
are transcribed from reports/web_landscape.md §1 / §2 / §3A (numbers only, links not copies).  Character-specific
items (forms, events, own resources, cooldown rules) follow reports/design_final.md §3 / §4.

Python 3.11, stdlib only, deterministic (the output depends only on the inputs and --date).
usage: python -I -X utf8 tools/make_collect_plan.py [--date 2026-10-13] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

E = pathlib.Path(__file__).resolve().parents[1]
OUT = E / "data" / "collect_plan.json"
INPUTS = {"db_extract": E / "data" / "db_extract.json", "measured": E / "data" / "measured.json",
          "prydwen": E / "web_raw" / "prydwen_skills_parsed.json"}

# web_landscape.md §1 (ids), §2.1 (prydwen updatedAt)
IDS = {  # cid: (ko, prydwen slug, GameWith id, mysqil slug, namu.wiki title, inven esper id, prydwen updatedAt)
    1003: ("사키리", "sakiri", "555728", "zaowu", "사키리", 1, "2026-09-13"),
    1004: ("라크리모사", "lacrimosa", "559773", "anhunqu", "라크리모사(이환)", 2, "2026-09-13"),
    1008: ("스키아", "skia", "555735", "yi", "스키아", 13, "2026-09-07"),
    1010: ("나나리", "nanally", "555738", "nanali", "나나리(이환)", 3, "2026-09-09"),
    1019: ("민트", "mint", "555737", "bohe", "민트(이환)", 4, "2026-09-09"),
    1020: ("하니엘", "haniel", "555734", "haniya", "하니엘(이환)", 14, "2026-09-07"),
    1021: ("에드가", "edgar", "555733", "edjia", "에드가(이환)", 15, "2026-07-02"),
    1023: ("백장", "baicang", "555727", "baizang", "백장(이환)", 5, "2026-09-13"),
    1025: ("하토르", "hathor", "555731", "hasuoer", "하토르(이환)", 17, "2026-09-09"),
    1033: ("아들러", "adler", "555736", "adeler", "아들러(이환)", 16, "2026-09-07"),
    1036: ("잔홍", "zankou", "567583", "canhong", "잔홍", 22, "2026-09-13"),
    1039: ("파디아", "fadia", "555729", "fadiya", "파디아", 6, "2026-09-07"),
    1042: ("레이븐", "blackbird", "573339", "heiyu", "레이븐(이환)", 24, "2026-09-30"),
    1051: ("「제로」", "zero", "555725", "ling", "감정사(이환)", 7, "2026-09-09"),
    1052: ("호토리", "hotori", "559752", "xun", "호토리(이환)", 9, "2026-09-09"),
    1054: ("다포딜", "daffodil", "555726", "dafutier", "다포딜(이환)", 10, "2026-09-13"),
    1055: ("구원", "jiuyuan", "555730", "jiuyuan", "구원(이환)", 11, "2026-09-09"),
    1057: ("아카네 린", "akane-rin", "573344", "mingyin", "아카네 린(이환)", None, "2026-09-18"),
    1070: ("우미츠키", "aurelia", "557062", "haiyue", "우미츠키", 18, "2026-09-07"),
    1071: ("카오스", "chaos", "561676", "kaesi", "카오스(이환)", 19, "2026-09-09"),
    1072: ("링코", "linko", "567727", "lingke", "링코", 23, "2026-09-13"),
    1073: ("치즈", "chiz", "555732", "xiaozhi", "치즈(이환)", 12, "2026-07-02"),
    1075: ("일로이", "iroi", "563075", "yiluoyi", "일로이", 21, "2026-09-13"),
    1076: ("신쿠", "shinku", "562926", "zhenhong", "신쿠(이환)", 20, "2026-09-09"),
}
# web_landscape.md §3A, GameWith JP snapshots (dateModified 2026-10-07..10-13): (E cd s, Q cd s, Q cost display)
GAMEWITH = {1003: (16, 20, 120), 1004: (16, 20, 120), 1008: (15, 15, 100), 1010: (16, 15, 100),
            1019: (6, 15, 100), 1020: (20, 20, 120), 1021: (None, 20, 100), 1023: (14, 20, 120),
            1025: (16, 15, 100), 1033: (16, 20, 120), 1036: (5, 20, 120), 1039: (16, 20, 120),
            1042: (16, 20, 100), 1051: (16, 15, 100), 1052: (None, None, None), 1054: (16, 20, 120),
            1055: (16, 15, 100), 1057: (None, None, None), 1070: (15, 15, 120), 1071: (15, 15, 100),
            1072: (12, 20, 100), 1073: (3, 15, 100), 1075: (12, 16, 100), 1076: (3, 20, None)}
# web_landscape.md §3A mysqil sample (8 character pages fetched; None = page fetched, no value; absent = not fetched)
MYSQIL = {1003: {"e_cd": None, "q_cd": None, "q_cost": 120}, 1004: {"e_cd": 15, "q_cd": 30, "q_cost": 120},
          1020: {"e_cd": None, "q_cd": None, "q_cost": 120}, 1051: {"e_cd": None, "q_cd": None, "q_cost": 100},
          1052: {"e_cd": "无需冷却", "q_cd": "无需冷却", "q_cost": "own clock 120 / 6 per s / E 60"},
          1071: {"e_cd": None, "q_cd": None, "q_cost": 100}, 1072: {"e_cd": None, "q_cd": None, "q_cost": 100},
          1076: {"e_cd": None, "q_cd": None, "q_cost": "桀骜斗志 60"}}
ARC_TABLE = (1004, 1010, 1036, 1042, 1051, 1052, 1057, 1071, 1072, 1075, 1076)   # efficiency table (solo cycles)
DB_VALUES = {  # design_final.md §3.3 (db_value / db_text, all re-validated by the generator against the DB)
    (1004, "q_cost"): (45.0, "data:DT_GlobalValueLacrimosaData.Lacrimosa_UltraSkill_ChargeCost_1", "db_value"),
    (1004, "e_cd"): (15.0, "data:Lacrimosa_Skill_cooldown_1", "db_value"),
    (1004, "q_cd"): (30.0, "data:Lacrimosa_UltraSkilll_cooldown_1", "db_value"),
    (1071, "q_cd"): (20.0, "data:Chaos_UltraskillCD", "db_value"),
    (1052, "e_cd"): (0.0, "text:GA_Jin_Skill 无需冷却时间", "db_text"),
    (1052, "q_cd"): (0.0, "text:GA_Jin_UltraSkill 无需冷却时间和终结能量", "db_text"),
    (1052, "q_cost"): (120.0, "data:Jin_UltraSkillCost (own clock, needs a full clock)", "db_value"),
    (1076, "q_cost"): (60.0, "data:ShinkuUltraEnergyMax (own meter; cost = cap is an inference)", "inference"),
}
ADMISSION = ("community_low = a prydwen value for the same skill (prydwen matched the DB 2/2, GameWith 0/3); "
             "enforced only at the resource level 'game data + community' (design_final.md D4); "
             "GameWith-only / mysqil-only values = community_very_low (tooltip only)")

# character-specific items beyond the five generic fields (design_final.md §3.6 / §4.6 / §10)
EXTRA = {
    1003: [("event:A5_float_refill", "unknown", "A5: an E that floats the target fills the Q and clears its "
            "cooldown (text, no float state in the simulator)", ["P", "text"], "low")],
    1004: [("cd_rule:extra_E_after_5_basics", "db_value", "Lacrimosa_Lv4ExtraERequireMeleeCount 5 (passive 2): "
            "5 basics during the E cooldown grant one extra E that neither checks nor restarts the timer", ["B"], "medium"),
           ("anchor:charge_scale", "db_value", "cost 45 is the only DB cost: the G0 anchor (chargeMax = 45?) and the "
            "protocol-A sanity check (expected 45 +- the last hit)", ["G0", "A"], "high")],
    1008: [("form_cd:shadow", "unknown", "shadow form re-entry / ShadowContact (in-form skill, not an E press)",
            ["F"], "low")],
    1010: [("event:A1_follow_up_energy", "db_value", "Nanally_Pas2Charge +2.5 per follow-up (1 s icd); follow-ups "
            "are not simulated - confirm the amount per follow-up hit", ["G0"], "low")],
    1019: [("cd_rule:A1_counter_resets_E", "db_text", "a counter resets the E cooldown (every 3 s, "
            "Mint_Adcance_1_1_CD) - custom mode only", ["E"], "low")],
    1020: [("cd_rule:A6_minus_4s", "db_value", "Haniel_Level6_CD -4 s on her E (awakening 6)", ["B"], "low"),
           ("conflict:shipped_hint", "community", "the shipped tooltip hint says E 16 s; prydwen and GameWith "
            "both say 20 s (design_final.md §3.4)", ["B"], "medium")],
    1021: [("cd_rule:anim_time_E", "db_value", "E cooldown grows with channel time (GA_Skill_CD_AnimTimeRatio "
            "1.0, A2 cap +3 s); base unknown (prydwen 'Base CD 16s + 1s per instance' is a different formula): "
            "press E with the shortest and the longest channel", ["B"], "medium"),
           ("event:passive_charge_120", "db_value", "+120 energy once per 30 s to the support-charge trigger "
            "(盈蓄) - simulated in the reaction-energy pass", ["G0"], "low")],
    1023: [("cd_rule:redirect_SkillA_shares_E", "db_text", "GA_Cang_SkillA (slot other) shares the E cooldown "
            "(共享冷却); prydwen lists 14 s on both skill variants", ["B"], "medium"),
           ("cd_rule:A1_minus_4s", "db_value", "Buff_Cang023_Level1_SkillCDCut -4 s per 詈 word (not "
            "simulated)", ["B"], "low")],
    1025: [("form_cd:skill2_cyclone", "unknown", "Skill2 cyclone presses inside the dispatch form", ["F"], "low"),
           ("event:speed_stack_energy", "db_value", "Buff_Hathor025_AddQEnergy +5 per speed stack (cap 6); stacks "
            "not simulated", ["G0"], "low")],
    1036: [("form_cd:magic_force_Q", "unknown", "Magic Q -> free Force Q (6.2-7.7 s apart measured; "
            "ZankouGiveUltraForceTime 5 s db) - is Force available later than 5 s?", ["F"], "medium"),
           ("cd_rule:E_exit_PowerSkill2", "unknown", "does the 幻境 exit (PowerSkill2) share or restart the E "
            "cooldown?", ["B", "F"], "low")],
    1039: [("form_cd:chase", "unknown", "敌神者 chase follow-ups after the Q", ["F"], "low"),
           ("event:threshold_refill", "db_text", "破灭阈值 fills the Q (text, condition not simulated)", ["P"], "low")],
    1042: [("form_cd:witch_Q", "unknown", "witch-form Q = CoolDwonCurveTable[GA_BlackBird_UltraSkill] x1.0 / "
            "x0.25 (row value not imported): press the witch Q twice in one form", ["F"], "medium"),
           ("gauge:E_40_pool", "unknown", "Buff_BlackBird_AddEnergy 40: malice or cycle gauge?  E then an "
            "immediate support-skill swap at a known gauge", ["D"], "medium")],
    1051: [("event:A2_plus_8", "db_value", "Female051_LV2 +8 energy after E (awakening 2)", ["G0"], "low")],
    1052: [("own:clock_drain_start", "inference", "drain 10/s inside the Q time stop: from the Q (stricter, "
            "simulated) or from the tachi branch?  Q, do not press the finisher, time the stop", ["H"], "high"),
           ("own:clock_remainder", "inference", "is the clock remainder kept after the finisher?  read the clock "
            "gauge after the finisher", ["H"], "high"),
           ("own:regen_in_time_stops", "inference", "does the +6/s regeneration pause during other members' Q "
            "time stops (active clock)?", ["H", "G1"], "medium")],
    1054: [("event:A2_failed_counter_full_Q", "db_text", "a failed counter fills the Q (text; not simulated)",
            ["P"], "low")],
    1055: [("event:bud_boom_40", "db_value", "Kuhara_BudBoomAddQEnergy +40 (condition: unbalanced target; the "
            "dummy never topples)", ["G0"], "low")],
    1057: [("blocked:release", "unknown", "released 2026-10-21: no page has numbers; re-fetch GameWith 573344, "
            "mysqil mingyin, prydwen akane-rin after release (G4), then protocols A/B/C", ["G4"], "high"),
           ("own:string_energy", "unknown", "弦能 30 for 同调共振 (text); per-hit gain unknown", ["G0"], "low")],
    1070: [("time_only:counter_credit", "inference", "the approved counter step is time-only and credited with "
            "its Show value (simulator side, nothing to record)", [], "none")],
    1071: [("cd:E_short_2s", "db_value", "short-press shared cooldown 2.0 s (GE_CoolDownBase_Chaos); the full E "
            "cooldown row is not imported", ["B"], "medium"),
           ("form_cd:ultra_state", "unknown", "12 s ultra state after the Q (custom palette state)", ["F"], "low")],
    1072: [("cd_rule:A3_Q_resets_E", "db_text", "Q refreshes the E cooldown (awakening 3) - also the key to the "
            "clock decision G1", ["G1"], "high")],
    1073: [("event:passive1_plus_4", "db_text", "+4 energy to the on-field member on 盈蓄 (text)", ["G0"], "low"),
           ("charge_eff:passive2_0.20", "db_value", "Chiichan_Pas2 +0.20 charge efficiency on field", ["G2"],
            "low")],
    1075: [("event:A6_50_50", "db_text", "A6 +50 energy / +50 gauge (revive bonus, not simulated)", ["P"], "low"),
           ("own:imagination", "unknown", "臆想 per-hit gain (not an ultimate resource)", ["G0"], "low")],
    1076: [("own:meter_unit", "inference", "桀骜斗志 per-use gains 18 / 13 / 5 / 3: per press, per hit or per "
            "combo?  count presses until the Q lights (60 / 18 -> 4 presses if per press)", ["S"], "high"),
           ("form_cd:rage", "unknown", "rage ultimates (free) and rage E inside 升腾之赤", ["F"], "low")],
}

CHUNKS = [
    (1, "Arc-table members whose results move most + the clock decision",
     "Solo cycles of these six change by seconds per loop under the default model (design_final.md §11); Linko "
     "and Lacrimosa also carry the two global checks (G1 clock, G0 anchor).",
     (1004, 1072, 1052, 1051, 1075, 1042)),
    (2, "Remaining arc-table members + the recorded-team members",
     "Rest of the efficiency table (seed shipped) and the two members whose existing recordings give bounds.",
     (1010, 1036, 1071, 1076, 1003, 1054)),
    (3, "Short-cooldown supports and rule-driven cooldowns",
     "Intra-visit waits (Chiichan 3 s, Mint 6 s), fast-team supports (Haniel, Adler), Edgar's channel-time "
     "cooldown and Cang's shared/variant cooldown.",
     (1073, 1019, 1020, 1033, 1021, 1023)),
    (4, "Form characters and the rest (Akane Rin after release)",
     "Form cooldowns and event energies; Akane Rin is blocked until 2026-10-21.",
     (1008, 1025, 1039, 1055, 1070, 1057)),
]

PROTOCOLS = {
    "G0": "attribute check: open a hit of a fresh recording in the battle report (hit inspection -> '공격 측 "
          "능력치'); if '현재 충전' / '충전 상한' show numbers, the capture carries per-hit ultimate energy",
    "A": "press-when-lit (Q cost): target that does not attack, one member, no charge-efficiency gear, no 盈蓄 team; "
         "Q at t=0, then basics only, Q again the moment it lights; 3 cycles (about 2 min)",
    "B": "E spam (E cooldown): 90 s, press E the moment it lights, no Q and no swaps in between; the E must deal "
         "damage to be visible in the capture (otherwise B': E then one basic as a marker)",
    "C": "Q spam with full energy (Q cooldown): press Q as soon as both energy and icon allow; an interval equal to "
         "the energy refill time is an upper bound only",
    "D": "support-skill re-entry (support skill cooldown / gauge semantics): two adjacent-element members, keep the "
         "outgoing gauge full, re-enter with the support skill as soon as the button allows",
    "E": "counters against an attacking enemy (counter cooldown); shortest interval between perfect-evade counters",
    "F": "form entries / form ultimates twice in a row as early as allowed (form cooldowns)",
    "H": "Hotori clock: Q, then do NOT press the finisher - time the stop; then a normal Q + finisher and read the "
         "clock gauge right after the finisher",
    "S": "Shinku meter: count melee / ranged presses, E and perfect evades between two lit Q icons",
    "P": "semantics only - text describes a condition the simulator does not model; record only if convenient",
    "G1": "cooldown clock: Linko without awakening 3 presses E, then Q (about 11 s time stop), then E as soon as it "
          "lights; E back about 1 s after the stop -> wall clock, about 12 s after it -> active clock",
    "G2": "(1 + charge efficiency) rule: same member with and without a charge-efficiency fork, compare per-hit "
          "energy deltas (needs G0)",
    "G4": "community re-fetch (read-only, link only): prydwen / GameWith / mysqil when their dates move; a changed "
          "value only demotes",
    "text": "official description text in the static DB (zh) - already read; nothing to record",
}

ACCEPT = {
    "q_cost": "G0: chargeMax constant within a battle and equal to the drop at the Q press (+-0.5) -> measured_value; "
              "protocol A: interval (sum - last action gain, sum] over >= 3 cycles, enforced (upper end) when the "
              "width is <= 5 charge_add units and consistent with the recorded bounds",
    "e_cd": "three shortest same-skill intervals agree within 0.3 s (no time stop in between) -> measured_value = "
            "shortest interval (0.1 s); a community value within [shortest - 0.3, shortest] is confirmed, one "
            "larger than shortest + 0.3 is demoted to community_very_low",
    "q_cd": "as e_cd; intervals limited by the energy refill are upper bounds only",
    "support_cd": "a refused support skill at a full gauge reveals a cooldown; none refused in >= 5 re-entries "
                  "confirms 'no cooldown of its own' (db_struct_none)",
    "counter_cd": "shortest counter-to-counter interval >= 0.9 s (evade cooldown) and no refusal -> confirmed",
}

FIELD_CATALOG = {
    "q_cost": {"label_ko": "Q 에너지 소모", "unit": "charge_add units (skill_damage.charge_add scale; Lacrimosa 45)",
               "fills": "team_resource_data.RESOURCES[cid]['energy']['cost']",
               "effect": "the Q is cast only when the accumulated energy reaches it (skipped otherwise)",
               "sources": ["static DB: HTAbilityChargeCost amount (blocked - not imported for 23/24)",
                           "G0 attribute capture (chargeMax / drop at the Q press)",
                           "protocol A recording (measured_value after convergence)",
                           "community 100 / 120 (display only - unit conflicts with the DB's 45; never enforced)"]},
    "e_cd": {"label_ko": "E 쿨타임(초)", "unit": "s",
             "fills": "team_resource_data.RESOURCES[cid]['cd']['E']",
             "effect": "a wait is inserted before an E that is not ready",
             "sources": ["static DB: CoolDwonCurveTable row (blocked - 0 rows imported)",
                         "protocol B recording (measured_value)",
                         "prydwen (community_low, enforced at the 'game data + community' level)",
                         "GameWith JP (community_very_low, tooltip only)", "mysqil (sporadic, undated)"]},
    "q_cd": {"label_ko": "Q 쿨타임(초)", "unit": "s", "fills": "team_resource_data.RESOURCES[cid]['cd']['Q']",
             "effect": "a wait is inserted before a Q that is not ready",
             "sources": ["static DB: CoolDwonCurveTable row (blocked)", "protocol C recording (measured_value)",
                         "prydwen (community_low)", "GameWith JP (community_very_low)", "mysqil (sporadic)"]},
    "support_cd": {"label_ko": "서포트 스킬 쿨타임", "unit": "s",
                   "fills": "team_resource_data.RESOURCES[cid]['cd']['QTE']",
                   "effect": "none today (db_struct_none = no cooldown of its own; gated by the cycle gauge)",
                   "sources": ["static DB structure: no cooldown reference on any of the 27 QTE abilities",
                               "protocol D (confirm, sample)", "community: 0/24 sites list one"]},
    "counter_cd": {"label_ko": "극한 반격 쿨타임", "unit": "s",
                   "fills": "team_resource_data.RESOURCES[cid]['cd']['counter'] (+ shared evade 0.9 s)",
                   "effect": "custom mode only (no approved rotation contains a counter)",
                   "sources": ["static DB: GE_CoolDown_Evade 0.9 s (all), no counter reference",
                               "protocol E (confirm, low priority)", "community: 0/24"]},
}


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prydwen_values(p: dict, slug: str) -> dict:
    out = {"e_cd": [], "q_cd": [], "q_cost": None}
    for skill in (p.get(slug) or {}).get("skills") or []:
        for m in skill.get("multipliers") or []:
            name, value = m.get("name", ""), str(m.get("value", ""))
            if re.search(r"Ultimate Energy|Energy Cost", name):
                out["q_cost"] = value
            elif re.search(r"CD|Cooldown", name):
                kind = {"Skill": "e_cd", "Ultimate": "q_cd"}.get(skill.get("type"))
                if kind:
                    out[kind].append(f"{name}: {value}")
    return out


def seconds(entries: list) -> float | None:
    vals = {float(m.group(1)) for e in entries for m in [re.search(r":\s*([\d.]+)s$", e)] if m}
    return vals.pop() if len(vals) == 1 else None


def bound(measured: dict, cid: int, kind: str) -> dict | None:
    ch = measured["characters"].get(str(cid))
    if not ch:
        return None
    cd = (ch.get("cooldown") or {}).get(kind) or {}
    if not cd.get("n_intervals"):
        return None
    return {"cooldown_le_wall_s": cd.get("upper_bound_wall_s"), "cooldown_le_active_s": cd.get("upper_bound_active_s"),
            "n_intervals": cd.get("n_intervals"), "source": "measured.json (3 recorded battles), measured_bound"}


def cost_bound(measured: dict, cid: int) -> dict | None:
    ch = measured["characters"].get(str(cid))
    if not ch:
        return None
    cycles = [r for r in ch.get("q_cycles") or [] if r.get("cycle", "").startswith("Q")
              and r.get("db_charge_add_all_own_hits") is not None]
    presses = (ch.get("ultimate") or {}).get("per_battle") or []
    if any(p.get("form") == "force" for p in presses):   # Zankou: paid Magic Q, free Force Q -> Magic to Magic
        vals = []
        for battle in sorted({p["battle"] for p in presses}):
            magic = sorted(p["t_s"] for p in presses if p["battle"] == battle and p.get("form") == "magic")
            for a, b in zip(magic, magic[1:]):
                vals.append(sum(r["db_charge_add_all_own_hits"] for r in cycles if r["battle"] == battle
                                and r["from_s"] >= a - 1e-6 and r["to_s"] <= b + 1e-6))
        basis = "paid Magic Q -> next Magic Q (the Force Q in between is free)"
    else:
        vals = [r["db_charge_add_all_own_hits"] for r in cycles]
        basis = "consecutive Q presses"
    if not vals:
        return None
    return {"cost_le_if_own_hits_only": round(min(vals), 2), "max_seen": round(max(vals), 2), "n_cycles": len(vals),
            "basis": basis,
            "source": "measured.json: DB energy of all own hits between presses (an upper bound on the cost "
                      "only if nothing else charges)"}


def generic_fields(cid: int, pry: dict, measured: dict) -> list:
    gw_e, gw_q, gw_cost = GAMEWITH[cid]
    my = MYSQIL.get(cid, {})
    pe, pq = seconds(pry["e_cd"]), seconds(pry["q_cd"])
    fields = []

    def community(kind: str, p_entries, p_value, gw_value):
        c = {"prydwen": {"value": p_value, "raw": p_entries, "updatedAt": IDS[cid][6]} if p_entries else None,
             "gamewith_jp": {"value": gw_value, "snapshot": "2026-10-07..10-13"} if gw_value is not None else None}
        if kind in my:
            c["mysqil"] = {"value": my[kind], "fetched": "2026-10-13"}
        return {k: v for k, v in c.items() if v is not None}

    # q_cost
    db = DB_VALUES.get((cid, "q_cost"))
    if cid == 1052:
        st, act, prio = "known_own_resource", "resolve_semantics (see own:*)", "high"
    elif cid == 1076:
        st, act, prio = "own_resource_unit_unresolved", "resolve_semantics (see own:meter_unit)", "high"
    elif db:
        st, act, prio = "known_db", "verify (anchor)", "high"
    elif cid == 1057:
        st, act, prio = "unknown", "fill after release", "medium"
    else:
        st, act, prio = "unknown", "fill", "high"
    fields.append({"field": "q_cost", "status": st, "action": act, "priority": prio,
                   "current": dict(zip(("value", "source", "confidence"), db)) if db else None,
                   "measured_bound": cost_bound(measured, cid),
                   "community": community("q_cost", None, None, gw_cost) | (
                       {"prydwen": {"value": pry["q_cost"], "updatedAt": IDS[cid][6]}} if pry["q_cost"] else {}),
                   "protocols": ["G0", "A"] if cid not in (1052, 1076) else ["H" if cid == 1052 else "S"],
                   "acceptance": ACCEPT["q_cost"] if cid not in (1052, 1076) else
                   "own resource: the numbers are db_value; only the semantics fields own:* below are open"})
    # e_cd / q_cd
    for kind, p_entries, p_value, gw_value, proto in (("e_cd", pry["e_cd"], pe, gw_e, "B"),
                                                       ("q_cd", pry["q_cd"], pq, gw_q, "C")):
        db = DB_VALUES.get((cid, kind))
        if db:
            st, act, prio = ("known_db" if db[2] == "db_value" else "known_text"), "verify (incidental)", "low"
        elif kind == "e_cd" and cid == 1021:
            st, act, prio = "rule_db_base_unknown", "fill base (shortest and longest channel)", "medium"
        elif p_value is not None and cid != 1004:
            st, act, prio = "community_low", "confirm", "medium"
        elif p_entries and cid == 1023:
            st, act, prio = "community_low_variant_level", "confirm (which variant is the E)", "medium"
        elif cid == 1057:
            st, act, prio = "unknown", "fill after release", "medium"
        else:
            st, act, prio = "unknown", "fill", "high"
        fields.append({"field": kind, "status": st, "action": act, "priority": prio,
                       "current": dict(zip(("value", "source", "confidence"), db)) if db else (
                           {"value": p_value, "source": f"prydwen:{IDS[cid][1]} {IDS[cid][6]}",
                            "confidence": "community_low"} if p_value is not None else None),
                       "measured_bound": bound(measured, cid, "e" if kind == "e_cd" else "q"),
                       "community": community(kind, p_entries, p_value, gw_value),
                       "protocols": [proto] if cid != 1052 else ["H"],
                       "acceptance": ACCEPT[kind]})
    # support skill / counter
    fields.append({"field": "support_cd", "status": "db_struct_none", "action": "confirm (sample)",
                   "priority": "low", "current": {"value": 0.0, "source": "struct: no cooldown reference on the QTE "
                                                  "ability", "confidence": "db_struct_none"},
                   "measured_bound": bound(measured, cid, "support_skill"), "community": {},
                   "protocols": ["D"], "acceptance": ACCEPT["support_cd"]})
    fields.append({"field": "counter_cd", "status": "db_struct_none + evade 0.9 db", "action": "confirm (low)",
                   "priority": "low", "current": {"value": 0.9, "source": "data:GE_CoolDown_Evade (shared evade "
                                                  "timer); no counter reference", "confidence": "db_value"},
                   "measured_bound": bound(measured, cid, "counter"), "community": {},
                   "protocols": ["E"], "acceptance": ACCEPT["counter_cd"]})
    return fields


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-13")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    db = json.loads(INPUTS["db_extract"].read_text(encoding="utf-8"))
    measured = json.loads(INPUTS["measured"].read_text(encoding="utf-8"))
    pry = json.loads(INPUTS["prydwen"].read_text(encoding="utf-8"))
    coverage = db["coverage"]
    assert sorted(int(c) for c in coverage) == sorted(IDS), "template set changed"
    chunk_ids = [cid for _, _, _, ids in CHUNKS for cid in ids]
    assert sorted(chunk_ids) == sorted(IDS) and len(chunk_ids) == 24, "chunks must cover the 24 once"
    assert all(len(ids) == 6 for *_, ids in CHUNKS)

    chunks, n_fill, n_confirm = [], 0, 0
    for number, title, why, ids in CHUNKS:
        members = []
        for cid in ids:
            ko, slug, gw, my, namu, inven, _ = IDS[cid]
            cov = coverage[str(cid)]
            fields = generic_fields(cid, prydwen_values(pry, slug), measured)
            for fid, status, note, protocols, prio in EXTRA.get(cid, []):
                fields.append({"field": fid, "status": status, "action": "resolve" if status in (
                    "unknown", "inference") else "verify", "priority": prio, "note": note, "protocols": protocols})
            n_fill += sum(1 for f in fields if f["action"].startswith(("fill", "resolve")))
            n_confirm += sum(1 for f in fields if f["action"].startswith(("confirm", "verify")))
            links = {"prydwen": f"https://prydwen.gg/neverness-to-everness/characters/{slug}",
                     "gamewith_jp": f"https://gamewith.jp/nte/{gw}",
                     "mysqil": f"https://wiki.mysqil.com/characters/{my}",
                     "namu": f"https://namu.wiki/w/{namu}"}
            if inven:
                links["inven"] = f"https://nte.inven.co.kr/db/esper/{inven}"
            members.append({
                "id": cid, "name_zh": cov["name_zh"], "name_ko": ko, "slug_en": slug, "element": cov["element"],
                "arc_table": cid in ARC_TABLE,
                "in_recorded_battles": str(cid) in measured["characters"],
                "availability": ("released 2026-10-21 - blocked until then" if cid == 1057 else
                                 "needs the character on the account (owned or trial); otherwise community only"),
                "per_hit_energy_gauge": "known 24/24 (skill_damage.charge_add / heterochrome_add, db_value) - "
                                        "nothing to record; G0 would cross-check energy",
                "links": links, "fields": fields})
        chunks.append({"chunk": number, "title": title, "why": why, "characters": members,
                       "recording_estimate_min": 6 * 5,
                       "processing": "user records with the app's own capture; with the user's go-ahead a "
                                     "read-only copy of the account database is measured by "
                                     "tools/measure_records.py (protocol detectors to be added, design_final.md "
                                     "§12); results enter data/measured.json -> gen_team_resource_data.py"})

    plan = {
        "schema": "teamsim_energy.collect_plan/1",
        "generated_by": "teamsim_energy/tools/make_collect_plan.py",
        "generated_on": a.date,
        "design": "teamsim_energy/reports/design_final.md §12; ordered work in reports/plan.md step 12",
        "inputs_sha256": {k: sha(v) for k, v in INPUTS.items()},
        "rules": [
            "data priority: static DB > measurement > official text in the DB > community wikis; every value carries "
            "source + confidence; unknown stays unknown",
            "measured bounds (measured_bound) never become values; only a converged protocol result becomes "
            "measured_value (acceptance rules per field)",
            "a community value can only be demoted by a newer snapshot, never promoted",
            ADMISSION,
            "the user's account data is read-only; recordings are measured only on a read-only copy taken with the "
            "user's go-ahead; nothing from it is copied elsewhere",
            "community pages are read-only (link, do not copy); no login, no posting",
        ],
        "global_steps": [
            {"id": "G0", "priority": 1, "title": "Is there an energy axis in new captures?",
             "how": PROTOCOLS["G0"],
             "evidence": "official 2.3.1 NTE_PluginCombat.dll carries attackerAttributes / victimAttributes "
                         "snapshots with chargeCurrent / GetChargeCurrent and chargeMax / GetChargeMax (string scan, "
                         "scratch/final_g0_strings.txt); the app's hit inspection dialog labels them 当前充能 / "
                         "充能上限 (features/battle_report/hit_inspection_widget.py:21); the 3 existing records (core "
                         "0.4.4, contract v5) carry none (61 tables scanned, scratch/final_g0_account_scan.txt). No "
                         "cycle-gauge attribute is listed (only replication callbacks), so the gauge stays DB-based.",
             "if_yes": "protocol A collapses to one ordinary recording per character: per-hit energy deltas, the "
                       "maximum, the drop at each Q press and the start value; also settles G2 and G3",
             "if_no": "protocol A per character (about 2 min each)",
             "best_team": "include Lacrimosa (DB cost 45 is the anchor: chargeMax 45 means the attribute uses the "
                          "charge_add scale)"},
            {"id": "G1", "priority": 2, "title": "Cooldown clock: wall time or battle time without time stops",
             "how": PROTOCOLS["G1"],
             "why": "decides the fast-team waits and the solo Iloi / Linko / Lacrimosa waits (design_final.md §11, "
                    "D5); one policy constant in the code"},
            {"id": "G2", "priority": 4, "title": "(1 + charge efficiency) rule", "how": PROTOCOLS["G2"],
             "needs": "G0 positive"},
            {"id": "G3", "priority": 3, "title": "Start energy = full, energy after Q = 0, cap = cost",
             "how": "read from the G0 attributes (chargeCurrent at the first hit, after each Q press); without G0: "
                    "Lacrimosa protocol A (expected 45 +- the last hit)"},
            {"id": "G4", "priority": 5, "title": "Community re-fetch", "how": PROTOCOLS["G4"],
             "when": "Akane Rin after 2026-10-21; prydwen / GameWith whenever their dates move"},
            {"id": "G5", "priority": 6, "title": "Sum<Element>Efficiency (Hexed) semantics",
             "how": "same member against a Hexed and a plain target: hits needed for a full gauge (support-skill "
                    "timing against the G0 replay)"},
        ],
        "protocols": PROTOCOLS,
        "field_catalog": FIELD_CATALOG,
        "chunks": chunks,
        "summary": {"characters": 24, "chunks": 4, "per_chunk": 6,
                    "fields_resolve_or_fill": n_fill, "fields_confirm_or_verify": n_confirm,
                    "known_today": {"per_hit_energy_and_gauge": "24/24 db_value",
                                    "q_cost": "1 db (1004) + 2 own resources (1052 clock, 1076 meter, unit open)",
                                    "e_cd": "1 db (1004) + 15 community_low + Hotori none (text); 7 unknown",
                                    "q_cd": "2 db (1004, 1071) + 18 community_low + Hotori none; 3 unknown",
                                    "support_cd / counter_cd": "db_struct_none for all 24 (evade 0.9 s db)"}},
    }
    text = json.dumps(plan, ensure_ascii=False, indent=1) + "\n"
    if a.check:
        same = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        print("check:", "OK" if same else "DIFFERENT")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(text.encode('utf-8'))} bytes): 24 characters, fill/resolve {n_fill}, "
          f"confirm/verify {n_confirm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
