# 弧盘效率表：每件弧盘在单人循环中不计入或按假设计算的部分（人工维护，不影响伤害数值）。
"""Hand-kept notes of the arc efficiency table (Global).

What the one-member reviewed rotation cannot show for each arc, as badge codes (reviewed against every arc's R1-R5
description in the 2.3.1 static DB).  The notes never change a damage number, so this module is not part of
the efficiency table's engine fingerprint (``arc_efficiency_service.engine_fingerprint``).

Codes
  support_skill            the effect needs support skills (援护技); a solo run enters as "opener", without one
  teammate                 teammate actions / the part given to teammates (only the wearer's own part counts)
  team_comp                a team makeup condition (number of elements ...)
  cycle_intensity          cycle intensity (环合强度) / break intensity (倾陷强度): no cycle reaction, no break solo
  target_state             boss, broken or status-affected enemies (the dummy is none of them)
  taken_dodge_kill_shield  taking hits, perfect dodges, kills, shields
  energy_cd                energy / charge / cooldown (the rotation is fixed: no extra casts)
  active_arc               an active arc skill (调弧) - not part of any reviewed rotation
  element:<code>           part of the effect only works for one element; shown only when the wearer differs
                           (codes as team_cycle_reactions: cosmos nature incantation chaos psyche lakshana)
  assumed                  computed with the calculator's default assumption (stacks, HP, enemy HP)
  engine_gap               part of the effect is not modelled by the battle engine
  non_damage               healing, shields, defense, damage taken: no damage effect
  data_error               a static-data error (焰魂狂飙: its permanent Lakshana bonus uses the wrong parameter)

Every arc of the static DB must have an entry (``()`` = nothing to add); an arc without one is shown as
"not annotated" and fails the build test (test_arc_eff_notes).  Regular characters without an exclusive arc are not
in the table (user decision U1, 2026-10-07), so there is no basis table for them.
"""
from __future__ import annotations

CODES = ("support_skill", "teammate", "team_comp", "cycle_intensity", "target_state", "taken_dodge_kill_shield",
         "energy_cd", "active_arc", "element", "assumed", "engine_gap", "non_damage", "data_error")

NOTES: dict[str, tuple[str, ...]] = {
    # ── type 1 (固态) ──
    "fork_BitGame": ("teammate", "element:psyche"),          # back-row part needs a controlled teammate
    "fork_BlastCandy": (),
    "fork_Butterfly": ("element:nature",),
    "fork_Crowbar": ("cycle_intensity", "non_damage"),       # break intensity; its 调弧 opens locks
    "fork_Nakupeda": ("non_damage",),
    "fork_PoliceRat": ("target_state", "active_arc"),        # boss damage; summoned rat
    "fork_Time": ("teammate", "support_skill"),              # 荒时 stacks from teammates' skills / support skills
    "fork_nonos": (),
    "fork_rishi": ("active_arc", "taken_dodge_kill_shield", "energy_cd"),
    "fork_worldrain": ("cycle_intensity", "element:cosmos"),
    "fork_wuhuakuang": ("assumed",),                         # HP above 50 %
    # ── type 2 (液态) ──
    "fork_BlackBook": ("support_skill", "active_arc", "cycle_intensity"),
    "fork_Castle": ("non_damage",),
    "fork_Door": ("teammate", "element:nature"),             # healing: Anima damage for the wearer, teammates' part
    "fork_MotorCandy": (),
    "fork_PaperPlane": ("element:nature",),
    "fork_Rose": ("engine_gap",),                            # break extension not modelled
    "fork_appliance": (),
    "fork_jiaojuan": ("cycle_intensity", "target_state"),
    "fork_lingganzhongjiezhe": ("energy_cd",),
    "fork_prism": ("element:lakshana",),                     # conditional part priced as a Global supplement (B4)
    # ── type 3 (等离子) ──
    "fork_BoxingCandy": ("assumed",),                        # enemy HP tier
    "fork_GoldRecord": ("support_skill",),
    "fork_Prokaryon": (),
    "fork_TigerTally": ("active_arc", "target_state"),       # 司令虎符: boss damage
    "fork_Whale": ("target_state", "taken_dodge_kill_shield"),
    "fork_moon": ("element:psyche",),
    "fork_oulaquantao": (),
    "fork_wushoutieyu": ("data_error", "element:lakshana"),
    "fork_yaodao": ("engine_gap",),                          # counter attacks are not on the axis
    # ── type 4 (气态) ──
    "fork_DemonBlade": ("element:incantation",),
    "fork_Kite": ("target_state", "element:lakshana"),       # 延滞 / 浸染 targets
    "fork_NestBird": ("non_damage",),
    "fork_ThiefCandy": ("taken_dodge_kill_shield",),
    "fork_bopu": ("support_skill",),
    "fork_mamen": ("assumed", "element:cosmos"),             # 10 stacks of 方斯
    "fork_mofeikesi": ("teammate", "energy_cd"),
    "fork_spider": ("teammate",),
    "fork_twinbirds": ("cycle_intensity", "teammate", "element:psyche", "engine_gap"),   # NightCrow variant
    "fork_vine": ("taken_dodge_kill_shield", "non_damage"),
    # ── type 5 (聚合) ──
    "fork_Arachne": (),
    "fork_BitterCake": ("taken_dodge_kill_shield", "non_damage"),
    "fork_GoldWool": ("element:lakshana",),
    "fork_KnightCandy": ("engine_gap",),                     # critical-hit events: second replay pass not run
    "fork_LunarPhase": ("element:cosmos",),
    "fork_dustbin": ("cycle_intensity",),
    "fork_jingmotingyuan": ("assumed", "active_arc"),
    "fork_koinobori": ("team_comp",),
    "fork_snowman": ("taken_dodge_kill_shield",),
    "fork_tuansanlang": ("team_comp", "cycle_intensity"),
    "fork_yuren": ("non_damage",),
}


def codes_for(fork_id: str, wearer_element: str = "") -> tuple[str, ...] | None:
    """Badge codes shown for ``fork_id`` on a wearer of ``wearer_element`` (None = the arc has no entry).
    ``element:<code>`` is kept only when the wearer's element differs."""
    codes = NOTES.get(str(fork_id))
    if codes is None:
        return None
    out = []
    for code in codes:
        if code.startswith("element:") and code.split(":", 1)[1] == str(wearer_element or ""):
            continue
        out.append(code)
    return tuple(out)


def label(code: str):
    """Short badge text (active language; Chinese source keys)."""
    from src.i18n_runtime import L as _L, LF as _LF
    from src.services.team_simulation_explanation import element_label

    if code.startswith("element:"):
        return _LF('属性不符（{0}）').format(element_label(code.split(":", 1)[1]))
    return {
        "support_skill": _L('援护技'),
        "teammate": _L('队友'),
        "team_comp": _L('队伍构成'),
        "cycle_intensity": _L('环合/倾陷强度'),
        "target_state": _L('目标状态'),
        "taken_dodge_kill_shield": _L('受击/闪避/击杀/护盾'),
        "energy_cd": _L('能量/冷却'),
        "active_arc": _L('调弧技能'),
        "assumed": _L('默认假设'),
        "engine_gap": _L('引擎未反映'),
        "non_damage": _L('与伤害无关'),
        "data_error": _L('数据库数值错误'),
        "unannotated": _L('尚未编写说明'),
    }.get(code, code)


def explanation(code: str):
    """One sentence: what the badge means for the solo number."""
    from src.i18n_runtime import L as _L, LF as _LF
    from src.services.team_simulation_explanation import element_label

    if code.startswith("element:"):
        return _LF('该弧盘的部分效果只作用于{0}属性伤害，与角色属性不同，按 0 计算。').format(
            element_label(code.split(":", 1)[1]))
    return {
        "support_skill": _L('依赖援护技（入场或释放）的效果在单人循环中不触发，按 0 计算。'),
        "teammate": _L('队友的行动或给队友的效果在单人循环中不存在，只计入装备者自身的部分。'),
        "team_comp": _L('需要特定队伍构成（属性数量等）的效果按 0 计算。'),
        "cycle_intensity": _L('单人循环没有环合反应与倾陷，环合强度与倾陷强度的提升按 0 计算。'),
        "target_state": _L('只对首领、倾陷状态或受异常状态影响的敌人生效的部分不计入（木桩不是首领，也不会倾陷）。'),
        "taken_dodge_kill_shield": _L('依赖受击、极限闪避、击杀或护盾的效果在单人循环中不触发。'),
        "energy_cd": _L('循环固定，充能、终结能量与冷却缩短不会增加释放次数，按 0 计算。'),
        "active_arc": _L('调弧（主动弧盘技能）不在已审核循环中，按 0 计算。'),
        "assumed": _L('按计算器的默认假设计算（层数、生命值、敌人生命值等），实战可能不同。'),
        "engine_gap": _L('战斗引擎未模拟该弧盘的部分效果，按 0 计算。'),
        "non_damage": _L('回复、护盾、防御或减伤等效果不影响伤害。'),
        "data_error": _L('数据库中该弧盘的常驻相属性伤害取了错误的参数（10%~20%，说明为 15%~25%），面板偏低 5 个百分点。'),
        "unannotated": _L('这件弧盘还没有约束说明（新数据），可能缺少注意事项。'),
    }.get(code, code)
