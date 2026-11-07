# Global 实时数据覆盖层的数据：明音凛（1057）国服正式上线（10-15）后的数值与文字（只在数据集与数据库 sha 一致时使用）。
"""Data of the Global live overlay (``global_live_overlay``): Akane Rin (明音凛, 1057) as released on the CN server
(2026-10-15), over the calculator's 9-24 pre-release static DB.

Source: ``work_g231/awaken/akane_cn/akane_overlay_spec.json`` (77 fields; user decision 2026-10-18 "아카네 린은 중국
데이터 기반으로"; a value changes only when two independent post-release CN-server source clusters agree - S1 game
screens, J = kamigame / appmedia "中国版" transcriptions, C1 ...).  Hand-written; the overlay is active only while the
running static DB is the one below (``OVERLAY_KEY``: manifest dataset id AND file sha256), so an upstream DB update
turns it off by itself.

Numbers here are release values that the DB does not hold (or holds differently).  Values the DB still holds are read
from it at run time (the arc's DamageUp1 x 4, durations of unchanged buffs).
"""
from __future__ import annotations

FORMAT = 1
OVERLAY_KEY = {
    "dataset_id": "cn_retail_20260924_9030b45b",
    # design_final.md wrote "…5C5D"; the spec corrected it (the file and the manifest end in …7C5D)
    "static_sha256": "AF810B5A8ADB82625BD023B11D2B348948B8649CE79D14E039ADA018F5217C5D",
}
# The Elyms-only migration preserves the Akane data that these corrections supplement.
COMPATIBLE_DATABASES = {
    (OVERLAY_KEY["dataset_id"], OVERLAY_KEY["static_sha256"]),
    ("cn_retail_20260924_9030b45b_elyms_154", "9E273398C732141D3BF34D039F7424AC091C6EBB92EC52CE292996466B97DF5A"),
}
AKANE = 1057

# switch groups (env NTE_GLOBAL_OVERLAY = off | on | comma list); built = the group changes something
GROUPS = {
    "release_status": {"default": True, "built": True},     # classification / release dates / explanation code
    "text": {"default": True, "built": True},               # DB description texts (DAO post-processing)
    "awakening": {"default": True, "built": True},          # Akane ②④⑥ / 共鸣3 / 共鸣6 rules, DB awakening buffs off
    "passive2": {"default": True, "built": True},           # 烁星激昂 (ATK +20 %, 20 s)
    "ult_window": {"default": True, "built": True},         # 音障爆鸣 stage 2 from 4 s into 华彩连段
    "arc_release": {"default": True, "built": True},        # 「月的对跖点」 release structure (B4 release mode)
    "passive1_remora": {"default": False, "built": False},  # 绝对音准 re-application damage: separate task (not built)
    "unverified_candidates": {"default": False, "built": False},  # arc R1 15 % / 20 % trial values: never shipped
}

# ── release status (field release.*) ──────────────────────────────────────────
CHARACTER_RELEASE = {
    AKANE: {
        "classification": "available_character",            # DB: scheduled_character
        "quality": "S",
        "acquisition_type": "limited",
        "mainland_release_date": "2026-10-15",
        "global_release_date": "2026-10-21",
        "release_source_kind": "official",
        "quality_source_kind": "official",
        "acquisition_source_kind": "official",
        "evidence_key": "official_wanmei_maintenance_notice_2026_10_14",
        "source_url": "https://yh.wanmei.com/news/gamebroad/20261014/264537.html",
        "observed_at": "2026-10-17",
    },
}
# team simulator explanation code (team_resource_data keeps the generated code; it is shown as this one)
UNMODELLED_CODE_MAP = {"akane_release_pending": "akane_values_unverified"}

# ── rules (team simulator / efficiency tables) ────────────────────────────────
# 烁星激昂 (passive 2, unlocked at breakthrough stage 4 = every Lv80 build): from the start of each stage-1 ultimate
PASSIVE2 = {"property": "AtkUp", "value": 0.20, "duration_s": 20.0, "trigger": "GA_Akane_UltraSkill"}
SYNCED_RESONANCE_GE = "GE_Player_Akane_UpgradeSkill_Damage"         # 同调共振 (both forms)
ULT_STAGE2_GE = "GE_Player_Akane_UltraSkill2_Damage"                # 音障爆鸣 stage 2
TAP_E = ("GA_Akane_Skill", "Skill")                                 # 泛音列 (tap)
HOLD_E = ("GA_Akane_Skill", "Skillhold")                            # 音域 (hold; custom cycles)
AWAKEN = {
    # ② targets with 泛音列 / inside 音域: Lakshana resistance -12 % for 25 s from each tap / hold E (team-wide target
    # debuff); the release text removed the front-row damage +12.5 %
    "Effect2": {"property": "DamageResistLakshanaBase", "value": -0.12, "duration_s": 25.0, "scope": "target"},
    # ④ crit damage +30 % for 15 s from each 同调共振 (start: just before its hit; alternative 'after' in the tests)
    "Effect4": {"property": "CritDamageBase", "value": 0.30, "duration_s": 15.0, "scope": "self"},
    # ⑥ DEF ignore +16 % while 烁星激昂 lasts (the party damage +10 % was removed)
    "Effect6": {"property": "DefIgnore", "value": 0.16, "scope": "self"},
    # 共鸣3: skill level +1 stays the DB's; ATK +20 % removed; fixed multipliers added to the hit's rate (not scaled)
    "resonance_3": {"fixed_rate": {SYNCED_RESONANCE_GE: 8.0, ULT_STAGE2_GE: 10.0}},
    # 共鸣6: crit damage +64 % for 25 s from each 同调共振 (弦能 refund / full start: 弦能 is not tracked)
    "resonance_6": {"property": "CritDamageBase", "value": 0.64, "duration_s": 25.0, "scope": "self"},
}
START_READING = "before"          # ④ / 共鸣6 window start: "before" the 同调共振 hit (default) | "after" it
# DB rules the overlay switches off (double counting / removed by the release): definition id -> properties dropped
SUPPRESS_RULES = {
    f"character_awaken:{AKANE}:Effect1": ("CritBase",),
    f"character_awaken:{AKANE}:resonance_3": ("AtkUp",),
}
# hidden DT_AkaneEffectFigure curves of the 9-24 DB that must not be read while the overlay is on (nothing in the Global
# simulator reads them; listed for the tests and the battle-report notice)
SUPPRESS_CURVES = (
    "Player_Akane_Level1_CritBase", "Player_Akane_DamageRseistBase", "Player_Akane_Level2_DamageUP",
    "Player_Akane_Level3_DamageUP", "Player_Akane_Level3EX_DamageUP", "Player_Akane_Level4_DamageUP",
    "Player_Akane_Level4_DamageUP_CD", "Player_Akane_Level6_GlobleDamageUP", "Player_Akane_Level6_GlobleDamageUP_CD",
    "Player_Akane_Level6EX_CritDamageUP", "Player_Akane_Passive2_UltraskillDamageUp",
    "Player_Akane_Passive2_UltraskillDamageUp_CD", "Skill_Short_DamageUp_Level3", "Skill_Long_AtkDamageUp_Level5",
)
# 音障爆鸣 stage 2: allowed from 4 s into 华彩连段 (DB text: the second half = 10-20 s); the reviewed stage 2 is at
# about 16.9 s, so only custom cycles change
ULT_STAGE2_WINDOW_S = (4.0, 20.0)
FORM_CODE = "akane_cadenza"

# 「月的对跖点」 (fork_prism) release mode (team_fork_corrections B4): (1) Skill damage +DamageUp1 x 4 for the whole
# fight (no stacks); (2) E cast -> basic attacks +DamageUp2 for DamageUp2_CD s (unchanged); (3) Lakshana damage
# +LakshanaUp in the same window (no "both at once" condition).  R1 confirmed by 3 clusters; R2-R5 derived (x 4).
PRISM_FORK = "fork_prism"
PRISM_PACK = "upgradestar_pack_fork_prism"
PRISM_STATIC_FACTOR = 4
PRISM_STATIC_EXPECTED = (0.28, 0.35, 0.42, 0.49, 0.56)    # DB DamageUp1 x 4, R1..R5 (tests)

# ── texts (DB description_zh, post-processed; translations: i18n DESC rows of the same zh text) ───────────────
_HM = '<hot textstyle="TextEXPL" param="nouns&AkaneHarmonicMark">「泛音列」</>'
_SF = '<hot textstyle="TextEXPL" param="nouns&AkaneSoundField">「音域」</>'
_CE = '<hot textstyle="TextEXPL" param="nouns&AkaneChordEnergy">「弦能」</>'
AWAKEN_TEXT = {      # whole-text replacements (S1 reading; DB markup put back)
    "Effect1": "每次释放强化变轨技能「同调共振」时，立即回复一次相当于明音凛<NumGreen>1000%</>基础攻击力的生命值，并且明音凛的防御力提升"
               "<NumGreen>50%</>，抗打断能力提升<NumGreen>60%</>，持续<NumGreen>15</>秒。",
    "Effect2": f"被{_HM}附着，或者处于{_SF}内的敌人相属性抗性降低<NumGreen>12%</>。",
    "Effect3": f"点按「变轨技能：律动音浪」释放{_HM}时，该技能增加<NumGreen>1000%</>的固定倍率；{_SF}的半径扩大<NumGreen>30%</>，"
               f"且长按「变轨技能：律动音浪」释放{_SF}时，吸附范围内的敌人。",
    "Effect4": "释放强化变轨技能「同调共振」后，明音凛暴击伤害提升<NumGreen>30%</>，持续<NumGreen>15</>秒。",
    "Effect5": f"{_HM}传导普通攻击的倍率提升效果提高至<NumGreen>64%</>；{_SF}传导普通攻击的伤害提升效果提高至<NumGreen>90%</>。",
    "Effect6": "「烁星激昂」额外使明音凛获得<NumGreen>16%</>的无视防御。",
    "resonance_3": f"明音凛的普通攻击、变轨技能、极轨终结的技能等级提高<NumGreen>1</>级；进入战斗时立即充满{_CE}。强化变轨技能「同调共振」"
                   f"增加<NumGreen>800%</>的固定倍率。「极轨终结：音障爆鸣」第二段增加<NumGreen>1000%</>的固定倍率。",
    "resonance_6": f"每次释放强化变轨技能「同调共振」后返还<NumGreen>10</>点{_CE}。释放强化变轨技能「同调共振」后，明音凛暴击伤害提升"
                   f"<NumGreen>64%</>，持续<NumGreen>25</>秒。",
}
# ability descriptions: (ability id, field) -> ordered edits (kind, old, new); kind "find" = literal (once), "regex"
_CADENZA = r'(<hot textstyle="TextEXPL" param="nouns&AkaneCadenza">「华彩连段」</>)'
ABILITY_EDITS = {
    ("GA_Akane_Passive_1", "description_zh"): (
        ("find", "每隔<NumGreen>X</>秒", "每隔<NumGreen>3</>秒"),
        ("find", "<NumGreen>X%</>攻击力", "<NumGreen>150%</>攻击力"),
        ("find", "整体提升<NumGreen>X%</>", "整体提升<NumGreen>20%</>"),
        ("find", "最多提升<NumGreen>X%</>", "最多提升<NumGreen>160%</>"),
        ("find", "同一目标每<NumGreen>X</>秒", "同一目标每<NumGreen>1</>秒"),
        ("find", "<Xiang>相属性异能伤害</>。每剩余", "<Xiang>相属性异能伤害</>，该伤害视为「变轨技能」伤害。每剩余"),
    ),
    ("GA_Akane_Passive_2", "description_zh"): (
        ("find", "自身造成的伤害提升", "自身攻击力提升"),
        ("find", "持续<NumGreen>25</>秒", "持续<NumGreen>20</>秒"),
    ),
    ("GA_Akane_Passive_2", "short_description_zh"): (
        ("find", "造成的伤害提升", "攻击力提升"),
        ("find", "持续<NumGreen>25</>秒", "持续<NumGreen>20</>秒"),
    ),
    ("GA_Akane_UltraSkill", "description_zh"): (
        ("find", "第一段时，明音凛对目标范围内的敌人造成<NumGreen>1</>次高额", "第一段时，明音凛对目标范围内的敌人造成多次"),
        ("find", "</>状态。\n在", "</>状态，状态期间明音凛的抗打断能力提升。\n在"),
        ("regex", "在" + _CADENZA + "持续时间的后半段", r"在\1持续<NumGreen>4</>秒后"),
    ),
    ("GA_Akane_UltraSkill", "short_description_zh"): (
        ("find", "状态持续时间的后半段", "状态持续4秒后"),
    ),
    ("GA_Akane_UltraSkill_End", "description_zh"): (
        ("regex", "在" + _CADENZA + "持续时间的后半段", r"在\1持续<NumGreen>4</>秒后"),
    ),
    ("GA_Akane_UltraSkill_End", "short_description_zh"): (
        ("regex", "在" + _CADENZA + "持续时间的后半段", r"在\1持续<NumGreen>4</>秒后"),
    ),
}
# fork_prism star text (every refinement): {S} = the static Skill bonus DamageUp1 x 4 of that refinement, written out
PRISM_TEXT = ("暴击率提升<lv>{0}</>。\r\n装备者的「变轨技能」造成的伤害提高<lv>{S}</>；装备者在释放「变轨技能」后，自身「普通攻击」造成的"
              "伤害提高<lv>{2}</>，并获得<lv>{3}</>相属性伤害提升，持续<lv>{5}</>秒。")
# the reviewed rotation's Korean step tooltip (team_rotation_data label_ko, generated): term map only
LABEL_KO = {(AKANE, 2): (("자기 피해 +20%(25초)", "공격력 +20%(20초)"),)}

# ── unverified / unknown (marked, never shown as release values) ─────────────────
UNVERIFIED = (       # KEEP fields: DB value kept and marked '미확인'
    "base.lv80", "skill.multipliers", "skill.conduction_base", "ult.cadenza_duration", "ult.stage2_ends_state",
    "ult.offfield_energy", "skill.synced_resonance_invuln", "melee.stage_dive_height", "melee.counter_combo_keep",
    "arc.R1.lakshana", "arc.R1.crit", "arc.R2_R5_other", "template.graduation", "weights.recommendation",
    "names.ko_en_ja",
)
DERIVED = ("arc.redirect_value",)        # R2-R5 = DB DamageUp1 x 4 (one cluster at most): marked as derived
UNKNOWN = ("skill.cooldown_E", "skill.cooldown_Q", "ult.energy_cost")     # team_resource_data 1057 stays unknown
UNVERIFIED_CANDIDATES = {"arc.R1.crit": 0.15, "arc.R1.lakshana": 0.20}  # S1 equip screen / L1 (group off, never used)
BASE_KIT_GAPS = {"Effect3": "G6", "Effect5": "G7", "resonance_3.chord_full_start": "G9", "resonance_6.refund": "G9",
                 "passive1": "G10"}

# every spec field -> (decision, overlay group or "" = nothing to change, where it acts)
FIELDS = {
    "release.classification": ("APPLY", "release_status", "dao"),
    "release.mainland_date": ("APPLY", "release_status", "dao"),
    "release.global_date": ("APPLY", "release_status", "profile"),
    "base.lv80": ("KEEP", "", "unverified"),
    "base.likeability10": ("SAME", "", "none"),
    "skill.max_level": ("SAME", "", "none"),
    "skill.multipliers": ("KEEP", "", "unverified"),
    "skill.chord_energy": ("SAME", "", "none"),
    "skill.form_duration": ("SAME", "", "none"),
    "skill.conduction_base": ("KEEP", "", "unverified"),
    "skill.cooldown_E": ("UNKNOWN", "", "unknown"),
    "skill.cooldown_Q": ("UNKNOWN", "", "unknown"),
    "ult.energy_cost": ("UNKNOWN", "", "unknown"),
    "ult.cadenza_duration": ("KEEP", "", "unverified"),
    "ult.stage2_min_delay": ("APPLY", "ult_window", "window+text"),
    "ult.stage1_hits": ("APPLY", "text", "text"),
    "ult.cadenza_interrupt_resist": ("APPLY", "text", "text"),
    "ult.stage2_ends_state": ("KEEP", "", "unverified"),
    "ult.offfield_energy": ("KEEP", "", "unverified"),
    "skill.synced_resonance_invuln": ("KEEP", "", "unverified"),
    "melee.stage_dive_height": ("KEEP", "", "unverified"),
    "melee.counter_combo_keep": ("KEEP", "", "unverified"),
    "passive1.interval_s": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive1.atk_pct": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive1.per_remaining_s_pct": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive1.max_pct": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive1.per_target_icd_s": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive1.counts_as_skill_damage": ("APPLY", "text", "text (rule: passive1_remora, not built)"),
    "passive2.stat": ("APPLY", "passive2", "interval+text"),
    "passive2.value": ("SAME", "passive2", "interval"),
    "passive2.duration_s": ("APPLY", "passive2", "interval+text"),
    "passive.unlock_stage": ("SAME", "", "none"),
    "awaken.Effect1.crit": ("APPLY", "awakening", "suppress"),
    "awaken.Effect1.heal": ("APPLY", "text", "text"),
    "awaken.Effect1.def_up": ("APPLY", "text", "text"),
    "awaken.Effect1.interrupt_resist": ("APPLY", "text", "text"),
    "awaken.Effect1.text": ("APPLY", "text", "text"),
    "awaken.Effect2.res": ("APPLY", "awakening", "interval"),
    "awaken.Effect2.field_dmg": ("APPLY", "awakening", "not built (removed)"),
    "awaken.Effect2.text": ("APPLY", "text", "text"),
    "awaken.Effect3.tap_multiplier": ("APPLY", "awakening", "gap G6 (0, unpriced)"),
    "awaken.Effect3.radius": ("APPLY", "text", "text"),
    "awaken.Effect3.text": ("APPLY", "text", "text"),
    "awaken.Effect4.stat": ("APPLY", "awakening", "interval"),
    "awaken.Effect4.duration_s": ("APPLY", "awakening", "interval"),
    "awaken.Effect4.text": ("APPLY", "text", "text"),
    "awaken.Effect5.overtone": ("APPLY", "awakening", "gap G7 (0, unpriced)"),
    "awaken.Effect5.field": ("APPLY", "awakening", "gap G7 (0, unpriced)"),
    "awaken.Effect5.text": ("APPLY", "text", "text"),
    "awaken.Effect6.team_dmg": ("APPLY", "awakening", "not built (removed)"),
    "awaken.Effect6.def_ignore": ("APPLY", "awakening", "interval"),
    "awaken.Effect6.text": ("APPLY", "text", "text"),
    "awaken.R3.skill_level": ("SAME", "", "none"),
    "awaken.R3.atk": ("APPLY", "awakening", "suppress"),
    "awaken.R3.synced_fixed": ("APPLY", "awakening", "evidence"),
    "awaken.R3.ult2_fixed": ("APPLY", "awakening", "evidence"),
    "awaken.R3.chord_full_start": ("APPLY", "awakening", "gap G9 (text only)"),
    "awaken.R3.text": ("APPLY", "text", "text"),
    "awaken.R6.chord_full_start": ("APPLY", "text", "text"),
    "awaken.R6.refund": ("SAME", "", "gap G9"),
    "awaken.R6.crit_dmg": ("APPLY", "awakening", "interval"),
    "awaken.R6.duration_s": ("SAME", "awakening", "interval"),
    "awaken.R6.text": ("APPLY", "text", "text"),
    "awaken.selection_model": ("SAME", "", "none"),
    "awaken.title_names": ("SAME", "", "none"),
    "arc.redirect_structure": ("APPLY", "arc_release", "b4"),
    "arc.redirect_value": ("APPLY", "arc_release", "b4 (R2-R5 derived)"),
    "arc.lakshana_condition": ("APPLY", "arc_release", "b4"),
    "arc.R1.lakshana": ("KEEP", "", "unverified"),
    "arc.R1.crit": ("KEEP", "", "unverified"),
    "arc.basic_after_redirect": ("SAME", "arc_release", "b4"),
    "arc.R2_R5_other": ("KEEP", "", "unverified"),
    "arc.base_stats": ("SAME", "", "none"),
    "arc.text": ("APPLY", "text", "text"),
    "template.graduation": ("KEEP", "", "unverified"),
    "weights.recommendation": ("KEEP", "", "unverified"),
    "names.ko_en_ja": ("KEEP", "", "unverified"),
}
