# 角色觉醒（돌파）效率表：人工维护的参考值与行标记（只用于显示，不影响伤害数值）。
"""Hand-kept notes of the character awakening efficiency table (Global; Korean UI "돌파 효율").

Display only: nothing here changes a number the table computes, so this module is not part of either efficiency
table's engine fingerprint (``arc_efficiency_service.FP_EXCLUDE``).

``REFERENCE[(cid, node)]``: numbers the current engine does NOT compute for an "upper bound" or "under review" node,
measured on the node specification's prototype (``work_g231/awaken/specs/awakening_node_specs.json`` ``measured``,
10-18; graduation template, Puka Boot Camp Lv 0, solo reviewed rotation).  The table shows an upper bound in the cell
("≤ +x%") and every other reference value in the tooltip only, always labelled as a specification measurement.
  kind      upper_bound | provisional | estimate
  add / remove   {loops: value %} or {loops: (low %, high %)} for that basis (missing = no value for that basis)
  time      the value comes with a changed cycle length (time-changed mark)
  note      code of the reading (``NOTE_TEXTS``)

``BADGES[cid]``: row badge codes (``badge_text``).
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

REFERENCE: dict[tuple[int, str], dict] = {
    # Sagiri ② (bound): LV2 hit x (1 + min(mass, 199)); the target's mass is not in the data -> the cap only
    (1003, "Effect2"): {"kind": "upper_bound", "add": {1: 23.71, 3: 23.13}, "note": "mass_cap"},
    # Hotori ③ (review): the clock refund's refill timing is not in the data -> instant-refund upper bound
    (1052, "Effect3"): {"kind": "upper_bound", "add": {1: 19.86, 3: 14.47}, "remove": {1: 19.86, 3: 14.47},
                        "time": True, "note": "instant_refund"},
    # Hathor ① (review): 闪送之力 stacks counted through ⑤ only; ATK per stack during 紧急派送 unconfirmed
    (1025, "Effect1"): {"kind": "provisional", "add": {1: 0.0, 3: 0.0}, "remove": {1: 3.37, 3: 3.37},
                        "note": "hathor_stacks"},
    # Hathor ② (review): its 3 stacks land inside 紧急派送 in the reviewed rotation (0 solo)
    (1025, "Effect2"): {"kind": "provisional", "add": {1: 0.0, 3: 0.0}, "remove": {1: 0.0, 3: 0.0},
                        "note": "hathor_gaze"},
    # Fadia ② (review): burst = 25 % of max HP when 破灭体验 expires; the damage formula is unconfirmed
    (1039, "Effect2"): {"kind": "estimate", "add": {1: 0.0, 3: (9.99, 10.73)}, "note": "fadia_burst"},
}

BADGES: dict[int, tuple[str, ...]] = {
    1071: ("crit_cap",),            # graduation template crit rate is already 100 % (awakening_data.md)
}


def note_text(code: str):
    return {
        "mass_cap": _L('目标质量不在数据中：按质量 199 以上（效果上限）计算的上限值'),
        "instant_refund": _L('时计能量的返还时间不在数据中：按立即返还计算的上限值'),
        "hathor_stacks": _L('「闪送之力」只计入觉醒效果 ⑤ 的部分；紧急派送中每层攻击力加成未确认'),
        "hathor_gaze": _L('已审核循环中该效果给予的层数都落在紧急派送内（单人为 0），只有队伍中先结束紧急派送时才有值'),
        "fadia_burst": _L('「破灭体验」结束时按最大生命值 25% 造成伤害；伤害公式未确认（1 轮时战斗在结束前就已结束）'),
    }.get(str(code), str(code))


def badge_text(code: str):
    return {
        "crit_cap": _L('毕业模板暴击率已达 100%：暴击率类效果为 0% 属正常'),
    }.get(str(code), str(code))


def kind_text(kind: str):
    return {
        "upper_bound": _L('上限值'),
        "provisional": _L('暂定值'),
        "estimate": _L('估算值'),
    }.get(str(kind), str(kind))


def reference_value(reference, basis: str, loops: int):
    """The reference value of one basis and loop count (a number, a (low, high) pair, or None)."""
    if not reference:
        return None
    key = "add" if basis == "add_one" else "remove"
    table = reference.get(key) or {}
    return table.get(int(loops))


def format_value(value) -> str:
    """"+x.x%" / "+x.x–y.y%" (never "+0.0%": a zero reads "0")."""
    if value is None:
        return ""
    if isinstance(value, tuple):
        return f"+{value[0]:.1f}–{value[1]:.1f}%"
    if abs(float(value)) < 0.05:
        return "0"
    return f"{float(value):+.1f}%"


def reference_line(reference, loops_choices=(1, 3)):
    """One tooltip line: "<kind> (specification measurement, 10-18): add one 1 loop … / 3 loops … · remove one …"."""
    if not reference:
        return ""
    parts = []
    for key, label in (("add", _L('只加一个')), ("remove", _L('从全部觉醒中去掉一个'))):
        table = reference.get(key) or {}
        if not table:
            continue
        values = " / ".join(_LF('{0} 轮 {1}').format(loops, format_value(table[loops]))
                            for loops in loops_choices if loops in table)
        if values:
            parts.append(label + " " + values)
    if not parts:
        return ""
    head = _LF('{0}（规格阶段实测，10-18，未用当前引擎重新计算）').format(kind_text(reference.get("kind", "")))
    out = head + ": " + parts[0]
    for part in parts[1:]:
        out = out + " · " + part
    if reference.get("time"):
        out = out + " " + _L('（循环时长改变）')
    return out
