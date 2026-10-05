"""Generate ``src/services/team_form_actions.py``: transformation / form-state actions for the team simulator.

Form-state attacks (Zankou's 幻境形态, Raven's 救世的魔女, Shinku's 升腾之赤, Hathor's 紧急派送, Akane's 华彩连段
second stage, Skia's 啮逐潜影 contact, Hotori's time-stop tachi, Fadia's 敌神者 chase) are granted abilities that
are missing from ``character_combat_ability_binding``, so ``BattleAnimationWindowService.load_candidates`` never
sees them and the approved rotations kept those steps time-only (no damage).

This generator turns each form step into a placeable action ``(ability_id, "Form:<Name>")`` with an explicit hit
timeline ``((ge, logged_ability_id, (offset_s, ...)), ...)`` and a length:

* montage parts come from the engine's own ``load_candidates`` run over a read-only DAO view that adds the form
  abilities' bindings (asset paths from ``combat_blueprint_asset``);
* explicit parts cover damage that a spawned damage actor deals (no montage notify): Raven's 祭火五段 actor,
  Shinku's 赤红的处决 / 处决的龙炎, Akane's 同调共振 (no montage) and Skia's mode contact (periodic buff).

Strict validation (any error aborts before writing):

* every form ability exists as an ``ability`` asset inside the owner's ability folder;
* every montage part resolves to exactly one candidate, every damage hit lies inside the part's length;
* every emitted GE has a ``skill_damage`` row with a non-zero ATK / DEF / HP rate, so replay prices it;
* explicit hit counts equal the level-hint multiplier ``{0}%*N`` of the GE where the game states one;
* form durations, periods and window limits are read from ``combat_curve_point`` / ``buff_definition``;
* every form start marker is an effect of the entry candidate at the stated offset;
* form-step overlays point at existing actions and approved steps (checked again by gen_team_rotation_data.py);
* every form GE the replay cannot level (no level-hint / FollowSkill owner among the character's skills, and
  logged under an ability that is not a character skill) has a LEVEL_PARENTS entry: the character skill whose
  level it uses (Hathor's 轮转打击 = E, Hotori's tachi finisher = ultimate).  The parent must be one of the
  character's skills and must level a sibling GE of the same logged ability (or name the GE in its level hint).

usage: gen_team_form_actions.py [--check] [--out PATH]
Run with the Python 3.11 interpreter (PYTHONUTF8=1).  Reads the static DB read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

SP = Path(__file__).resolve().parent.parent          # scratchpad/v230
WORK = SP / "work"
ROOT = WORK / "l10n_root"
STATIC = ROOT / "data" / "game_static.sqlite3"
OUT = ROOT / "src" / "services" / "team_form_actions.py"
INTERNAL = SP / "app_test" / "_internal"

SCHEMA_VERSION = 1
EPS = 1e-6

# ── form abilities (granted while a form is active; not bound to an input slot) ──────────────────────────
FORM_ABILITIES = {
    1036: ("GA_Zankou_MeleeMagic", "GA_Zankou_UltraSkillMagic", "GA_Zankou_UltraSkillForce"),
    1042: ("GA_BlackBird_Evolve_Melee", "GA_BlackBird_Evolve_Skill", "GA_BlackBird_Evolve_UltraSkill"),
    1076: ("GA_Shinku_Melee_Rage", "GA_Shinku_Skill_Rage", "GA_Shinku_UltraSkill_Rage_Pre", "GA_Shinku_UltraSkill_Rage"),
    1025: ("GA_Hathor_Skill2",),
    1057: ("GA_Akane_UltraSkill_End", "GA_Akane_Skill_instead"),
    1052: ("GA_Jin_UltraSkill_Melee",),
    1039: ("GA_Fadia_UltraSkill_Melee",),
}
# DoT application markers, malice extras the engine cannot price (atk 0 + blueprint CoefAdd), an
# uncategorised level check, and the plain finisher replaced by its passive-2 variant: never direct hits.
DROP_GES = frozenset((
    "GE_Player_Zankou_DotDamage", "GE_Player_Zankou_DotUltraDamage",
    "GE_Player_BlackBird_Evolve_UltraSkill_Damage_checkLV1", "GE_Player_Jin_UltraSkillMelee6_Damage",
))
DROP_SUFFIXES = ("_Extra_Damage",)


def M(ability: str, selector: str, length_s: float | None = None, extra=()):
    """Montage part: hits of candidate (ability, selector); length None = its trigger end."""
    return {"kind": "montage", "ability": ability, "selector": selector, "length_s": length_s, "extra": tuple(extra)}


def X(label: str, length_s: float, hits, hint=None):
    """Explicit part: ((ge, (offset_s, ...)), ...) placed by data the montage tables cannot express.
    hint = (level-hint ability_id, ordinal, {ge: hits per part}) checked against '{0}%*N'."""
    return {"kind": "explicit", "label": label, "length_s": length_s, "hits": tuple(hits), "hint": hint}


def ticks(start: float, period: float, count: int) -> tuple:
    return tuple(round(start + period * k, 3) for k in range(count))


# ── actions: name -> definition (key = (ability, "Form:<name>")) ──────────────────────────────────────────
ZK_REC = "recorded cadence (captures 1/2/4 medians: MM1 0.265-0.278, MM2 0.718-0.726, Branch2 1.397-1.46, " \
         "MM3 1.111-1.125, MM4 0.897-0.923, MM1 0.317)"
ACTIONS = {
    # 残虹 幻境形态: 魇舞 1-2, 落月 (hold), 魇舞 3-4, 魇舞 1 (17 hits, GE order of capture 2 @98.33-102.72)
    "MagicChain": dict(cid=1036, ability="GA_Zankou_MeleeMagic", form="zankou_fantasy", confidence="high",
                       timing="recorded", source=ZK_REC, parts=[
                           M("GA_Zankou_MeleeMagic", "MagicMelee1", 0.27), M("GA_Zankou_MeleeMagic", "MagicMelee2", 0.725),
                           M("GA_Zankou_MeleeMagic", "Branch2", 1.42), M("GA_Zankou_MeleeMagic", "MagicMelee3", 1.12),
                           M("GA_Zankou_MeleeMagic", "MagicMelee4", 0.91), M("GA_Zankou_MeleeMagic", "MagicMelee1", 0.32)]),
    # 血宴入梦时 (magic Q) and the free 焚天烬灭舞 (force Q); lengths = recorded next action (5.725-5.745 / 4.82-4.855)
    "MagicQ": dict(cid=1036, ability="GA_Zankou_UltraSkillMagic", form="zankou_fantasy", confidence="high",
                   timing="recorded", source="montage hits; length = recorded next action 5.725-5.745 s",
                   parts=[M("GA_Zankou_UltraSkillMagic", "UltraskillMagic", 5.73)]),
    "ForceQ": dict(cid=1036, ability="GA_Zankou_UltraSkillForce", form="zankou_fantasy", confidence="high",
                   timing="recorded", source="montage hits; length = recorded next action 4.82-4.855 s",
                   parts=[M("GA_Zankou_UltraSkillForce", "UltraSkillForce", 4.84)]),
    # 黑羽 救世的魔女: 祭火 3-5 right after the transform; 祭火五段 damage comes from DamageActorBlackBirdMelee5
    # (spawn Melee.5 @0.337 s, 6 hits per level hint 「祭火」五段 *6; 0.1 s tick spacing assumed)
    "WitchA3to5": dict(cid=1042, ability="GA_BlackBird_Evolve_Melee", form="raven_witch", confidence="medium",
                       timing="montage", source="trigger ends; 祭火五段 actor ticks every 0.1 s (assumed)", parts=[
                           M("GA_BlackBird_Evolve_Melee", "Melee3"), M("GA_BlackBird_Evolve_Melee", "Melee4"),
                           M("GA_BlackBird_Evolve_Melee", "Melee5", extra=[
                               ("GE_Player_BlackBird_Evolve_Melee5_Damage", ticks(0.437, 0.1, 6))])]),
    "WitchA1to5": dict(cid=1042, ability="GA_BlackBird_Evolve_Melee", form="raven_witch", confidence="medium",
                       timing="montage", source="trigger ends; 祭火五段 actor ticks every 0.1 s (assumed)", parts=[
                           M("GA_BlackBird_Evolve_Melee", "Melee1"), M("GA_BlackBird_Evolve_Melee", "Melee2"),
                           M("GA_BlackBird_Evolve_Melee", "Melee3"), M("GA_BlackBird_Evolve_Melee", "Melee4"),
                           M("GA_BlackBird_Evolve_Melee", "Melee5", extra=[
                               ("GE_Player_BlackBird_Evolve_Melee5_Damage", ticks(0.437, 0.1, 6))])]),
    "WitchSkill": dict(cid=1042, ability="GA_BlackBird_Evolve_Skill", form="raven_witch", confidence="high",
                       timing="montage", source="trigger end", parts=[M("GA_BlackBird_Evolve_Skill", "Default")]),
    # 万火归一: no trigger end; EndAbilitySkill 4.05 s, first CanBreakSkill 4.083 s
    "WitchFinisher": dict(cid=1042, ability="GA_BlackBird_Evolve_UltraSkill", form="raven_witch", confidence="medium",
                          timing="montage", source="first CanBreakSkill 4.083 s (no trigger end)",
                          parts=[M("GA_BlackBird_Evolve_UltraSkill", "Default", 4.08)]),
    # 真红 升腾之赤: 惊骇急袭 1-2 per set, 天降赤锋
    "RageMelee": dict(cid=1076, ability="GA_Shinku_Melee_Rage", form="shinku_rage", confidence="medium",
                      timing="montage", source="trigger ends; two presses per set (community 'AA变')",
                      parts=[M("GA_Shinku_Melee_Rage", "Melee1"), M("GA_Shinku_Melee_Rage", "Melee2")]),
    "RageSkill": dict(cid=1076, ability="GA_Shinku_Skill_Rage", form="shinku_rage", confidence="high",
                      timing="montage", source="trigger end", parts=[M("GA_Shinku_Skill_Rage", "Skill")]),
    # 赤红的处决: DamageActor_ShinkuUltraSkillPreRage spawned at UltraSkill.1 (0.167 s Default montage, 0.333 s
    # Combo montages), 4 hits per press (level hint *4), 0.1 s spacing (recorded actor ticks 0.087-0.125 s)
    "RageExecution1": dict(cid=1076, ability="GA_Shinku_UltraSkill_Rage_Pre", form="shinku_rage", confidence="medium",
                           timing="assumed", source="spawned damage actor; 0.1 s tick spacing assumed", parts=[
                               X("Default", 0.701, [("GE_Player_Shinku_UltraSkillPre_Rage_Damage", ticks(0.167, 0.1, 4))],
                                 hint=("GA_Shinku_UltraSkill", 2, {"GE_Player_Shinku_UltraSkillPre_Rage_Damage": 4}))]),
    "RageExecution2": dict(cid=1076, ability="GA_Shinku_UltraSkill_Rage_Pre", form="shinku_rage", confidence="medium",
                           timing="assumed", source="spawned damage actor; 0.1 s tick spacing assumed", parts=[
                               X("Combo", 0.867, [("GE_Player_Shinku_UltraSkillPre_Rage_Damage", ticks(0.333, 0.1, 4))],
                                 hint=("GA_Shinku_UltraSkill", 2, {"GE_Player_Shinku_UltraSkillPre_Rage_Damage": 4}))]),
    "RageExecution3": dict(cid=1076, ability="GA_Shinku_UltraSkill_Rage_Pre", form="shinku_rage", confidence="medium",
                           timing="assumed", source="spawned damage actor; 0.1 s tick spacing assumed", parts=[
                               X("Combo1", 0.867, [("GE_Player_Shinku_UltraSkillPre_Rage_Damage", ticks(0.333, 0.1, 4))],
                                 hint=("GA_Shinku_UltraSkill", 2, {"GE_Player_Shinku_UltraSkillPre_Rage_Damage": 4}))]),
    # 处决的龙炎: DamageActor_ShinkuUltraSkillRage @3.45 s (x10, level hint *10) and ...Rage1 @4.45 s
    "RageDragonflame": dict(cid=1076, ability="GA_Shinku_UltraSkill_Rage", form="shinku_rage", confidence="medium",
                            timing="assumed", source="spawned damage actors; 0.1 s tick spacing assumed; length = "
                                                     "trigger end 5.3 s", parts=[
                                X("Default", 5.3, [("GE_Player_Shinku_UltraSkill_Rage_Damage", ticks(3.45, 0.1, 10)),
                                                   ("GE_Player_Shinku_UltraSkill2_Rage_Damage", (4.45,))],
                                  hint=("GA_Shinku_UltraSkill", 3, {"GE_Player_Shinku_UltraSkill_Rage_Damage": 10}))]),
    # 哈索尔 紧急派送: 轮转打击 1-3
    "Cyclone1": dict(cid=1025, ability="GA_Hathor_Skill2", form="hathor_dispatch", confidence="high", timing="montage",
                     source="trigger end", parts=[M("GA_Hathor_Skill2", "Skill2_1")]),
    "Cyclone2": dict(cid=1025, ability="GA_Hathor_Skill2", form="hathor_dispatch", confidence="high", timing="montage",
                     source="trigger end", parts=[M("GA_Hathor_Skill2", "Skill2_2")]),
    "Cyclone3": dict(cid=1025, ability="GA_Hathor_Skill2", form="hathor_dispatch", confidence="high", timing="montage",
                     source="trigger end", parts=[M("GA_Hathor_Skill2", "Skill2_3")]),
    # 明音凛: 音障爆鸣 (second stage) and 同调共振 (NoMontage enhanced skill, length provisional)
    "SonicBoom2": dict(cid=1057, ability="GA_Akane_UltraSkill_End", form="akane_cadenza", confidence="high",
                       timing="montage", source="trigger end", parts=[M("GA_Akane_UltraSkill_End", "Default")]),
    "Resonance": dict(cid=1057, ability="GA_Akane_Skill_instead", form="akane_cadenza", confidence="medium",
                      timing="assumed", source="NoMontage ability (Event.NoMontage.Skill.Damage.1); 0.3 s provisional",
                      parts=[X("NoMontage", 0.3, [("GE_Player_Akane_UpgradeSkill_Damage", (0.0,))])]),
    # 浔 time-stop tachi: lengths = first CanBreakSkill after the last damage notify (trigger ends overflow the stop)
    "TachiSet": dict(cid=1052, ability="GA_Jin_UltraSkill_Melee", form="jin_tachi", confidence="medium",
                     timing="montage", source="first CanBreakSkill after the last damage notify", parts=[
                         M("GA_Jin_UltraSkill_Melee", "UltraMelee1", 0.317), M("GA_Jin_UltraSkill_Melee", "UltraMelee2", 0.45),
                         M("GA_Jin_UltraSkill_Melee", "UltraMelee3", 0.667), M("GA_Jin_UltraSkill_Melee", "UltraMelee4", 1.342),
                         M("GA_Jin_UltraSkill_Melee", "UltraMelee5", 0.389)]),
    "TachiFinisher": dict(cid=1052, ability="GA_Jin_UltraSkill_Melee", form="jin_tachi", confidence="low",
                          timing="montage", source="passive-2 finisher GE; first CanBreakSkill 2.12 s",
                          parts=[M("GA_Jin_UltraSkill_Melee", "UltraMelee6", 2.12)]),
    # 法帝娅 敌神者 chase 1-5
    "GodfoeChase": dict(cid=1039, ability="GA_Fadia_UltraSkill_Melee", form="fadia_godfoe", confidence="high",
                        timing="montage", source="trigger ends", parts=[
                            M("GA_Fadia_UltraSkill_Melee", f"UltraMelee{i}") for i in range(1, 6)]),
    # 翳 啮逐潜影 contact: filled by FORMS[1008] (period / window from data), see _skia_contact()
}

# ── forms: rules the simulator applies inside a visit ─────────────────────────────────────────────────────
# start = (ability, selector, marker effect on that candidate); duration from a curve or a buff definition.
FORMS = {
    1036: dict(code="zankou_fantasy", name_zh="幻境形态", buff="Buff_Zankou_MagicDur",
               start=("GA_Zankou_Skill", "PowerSkill1", "GE_Player_Zankou_Skill1_1_Damage"),
               duration=("curve", "ZankouMagicDur"), ends_on_swap=True, pauses_off_field=False,
               policy="check", body_seqs=(5,), exit_seq=6, exit_remain=("curve", "ZankouMagicSkillRemainTime")),
    1042: dict(code="raven_witch", name_zh="救世的魔女", buff="Buff_BlackBird042_UltraSkill_Transform",
               start=("GA_BlackBird_UltraSkill", "Default", "Buff_BlackBird042_Evolve_UltraSkill_AtkUP"),
               duration=("curve", "Buff_BlackBird042_UltraSkill_Transform"), ends_on_swap=False, pauses_off_field=True,
               policy="size", body_seqs=(4, 5), groups={4: 1, 5: 1}, terminal_seq=6,
               fill=dict(after_seq=5, actions=("WitchA1to5", "WitchSkill"), max=3)),
    1076: dict(code="shinku_rage", name_zh="升腾之赤", buff="Buff_Shinku_Rage",
               start=("GA_Shinku_UltraSkill", "Default", "Buff_Shinku_Rage"),
               duration=("curve", "Shinku_Rage_Duration"), ends_on_swap=True, pauses_off_field=False,
               policy="size", body_seqs=(10, 11, 12, 13, 14, 15, 16, 17),
               groups={10: 1, 11: 1, 12: 2, 13: 2, 14: 3, 15: 3, 16: 4, 17: 4},
               tail_seq=18, tail_per_group=1, tail_max=3, after_seqs=(19,)),
    1025: dict(code="hathor_dispatch", name_zh="紧急派送", buff="Buff_HathorAngerActive",
               start=("GA_Hathor_UltraSkill", "Default", "Buff_HathorAngerActive"),
               duration=("curve", "Buff_HathorAngerActive_Duration"), ends_on_swap=True, pauses_off_field=False,
               policy="warn", body_seqs=(5, 6, 7)),
    1057: dict(code="akane_cadenza", name_zh="华彩连段", buff="Buff_Akane_Show_UltraSkillUI",
               start=("GA_Akane_UltraSkill", "Default", None),
               duration=("buff", "Buff_Akane_Show_UltraSkillUI"), ends_on_swap=False, pauses_off_field=False,
               policy="window", window_seq=21, window_from=("buff", "Buff_Akane_Skill_UltraSkill_Begin"),
               body_seqs=(21,)),
    1008: dict(code="skia_shadow", name_zh="啮逐潜影", buff="Buff_Skia_ShadowControl",
               start=("GA_Skia_Skill", "Default", "Buff_Skia_ShadowControl"),
               duration=("curve", "Skia_SneakDuaration"), ends_on_swap=True, pauses_off_field=False,
               policy="check", body_seqs=(6,), period=("curve", "Skia_SkillSneakAtkPeriod")),
}

# ── team buffs the order planner wants over a form window: (ability, selector, marker effect, BEGIN = step start
# or None = step end, duration).  Only used to rank visit orders; the damage replay infers the real buffs itself.
BEGIN = "<step start>"
TEAM_BUFFS = {
    # 「零」 LevelExtra passive: ATK up for the team when her support skill begins (BUFF_EVENT_QTE_BEGIN)
    1051: (("GA_Female051_QTE", "QTE", BEGIN, ("buff", "Buff_Female051_LevelExtra1_1")),),
    1003: (("GA_Sagiri_UltraSkill", "Default", None, ("curve", "Sagiri_QDamUp_AtkAddDur")),),
    1020: (("GA_Haniel_UltraSkill", "Default", "Buff_Haniel_UltraSkill_Atkup", ("buff", "Buff_Haniel_UltraSkill_Atkup")),),
    1042: (("GA_BlackBird_UltraSkill", "Default", "Buff_BlackBird042_Evolve_UltraSkill_AtkUP",
            ("curve", "Buff_BlackBird042_Evolve_UltraSkill_AtkUP_Time")),),
    1075: (("GA_Oneiroi_Skill", "Skill", "Buff_Oneiroi_Skill_AtkUP", ("curve", "Oneiroi_Skill_AtkAdd_Time")),),
}

# ── logged abilities of form GEs that the replay engine cannot level -> the character skill they follow ──
LEVEL_PARENTS = {
    1025: {"GA_Hathor_Skill2": "GA_Hathor_Skill"},          # 轮转打击 replaces the E while 紧急派送 lasts
    1052: {"GA_Jin_UltraSkill_Melee": "GA_Jin_UltraSkill"},  # tachi finisher (passive-2 GE has no level hint)
}

# ── approved steps that become form actions (applied by gen_team_rotation_data.py) ────────────────────────
# (cid, seq) -> (action names run in order, slot, repeat, role, group); role: body | terminal | tail | free |
# after | window.  replaces_runnable: the approved step already runs a bound action that is not the form one.
FORM_STEPS = {
    (1036, 5): (("MagicChain",), "basic", 1, "body", None),
    (1036, 7): (("MagicQ",), "ultimate", 1, "after", None),
    (1036, 8): (("ForceQ",), "ultimate", 1, "after", None),
    (1042, 4): (("WitchA3to5",), "basic", 1, "body", 1),
    (1042, 5): (("WitchSkill",), "skill", 1, "body", 1),
    (1042, 6): (("WitchFinisher",), "ultimate", 1, "terminal", None),
    (1076, 10): (("RageMelee",), "basic", 1, "body", 1),
    (1076, 11): (("RageSkill",), "skill", 1, "body", 1),
    (1076, 12): (("RageMelee",), "basic", 1, "body", 2),
    (1076, 13): (("RageSkill",), "skill", 1, "body", 2),
    (1076, 14): (("RageMelee",), "basic", 1, "body", 3),
    (1076, 15): (("RageSkill",), "skill", 1, "body", 3),
    (1076, 16): (("RageMelee",), "basic", 1, "body", 4),
    (1076, 17): (("RageSkill",), "skill", 1, "body", 4),
    (1076, 18): (("RageExecution1", "RageExecution2", "RageExecution3"), "ultimate", 1, "tail", None),
    (1076, 19): (("RageDragonflame",), "ultimate", 1, "after", None),
    (1025, 5): (("Cyclone1",), "skill", 1, "body", None),
    (1025, 6): (("Cyclone2",), "skill", 1, "body", None),
    (1025, 7): (("Cyclone3",), "skill", 1, "body", None),
    (1057, 16): (("Resonance",), "skill", 1, "free", None),
    (1057, 21): (("SonicBoom2",), "ultimate", 1, "window", None),
    (1052, 6): (("TachiSet",), "basic", 2, "body", None),
    (1052, 7): (("TachiFinisher",), "basic", 1, "body", None),
    (1039, 4): (("GodfoeChase",), "basic", 1, "body", None),
    (1008, 6): (("ShadowContact",), "skill", 1, "body", None),
}
REPLACES_RUNNABLE = {(1036, 8): ("GA_Zankou_UltraSkill", "UltraSkill")}   # plain Q never recorded: force Q


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────
def _bootstrap() -> None:
    for p in (str(ROOT),):
        if p not in sys.path:
            sys.path.insert(0, p)
    if INTERNAL.is_dir() and str(INTERNAL) not in sys.path:
        sys.path.append(str(INTERNAL))


def _is_damage_effect(ge: str) -> bool:      # same rule as team_simulation_service._is_damage_effect
    return ge.endswith("Damage") or "_Damage" in ge


def _dropped(ge: str) -> bool:
    return ge in DROP_GES or ge.endswith(DROP_SUFFIXES)


def _rates(row: dict) -> float:
    total = 0.0
    for key in ("atk_rate_base_json", "def_rate_base_json", "hp_rate_base_json"):
        values = json.loads(row.get(key) or "[]")
        total += sum(abs(float(v)) for v in values)
    return total


class _BindingView:
    """Read-only DAO view that adds the form abilities to the character bindings (no SQL writes)."""

    def __init__(self, inner, paths: dict[int, dict[str, str]]) -> None:
        self._inner, self._paths = inner, paths

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def list_character_combat_bindings(self, character_id):
        return [{"character_id": int(character_id), "binding_kind": "form", "ordinal": 900 + i, "input_id": None,
                 "ability_id": ab, "ability_asset_path": path}
                for i, (ab, path) in enumerate(self._paths.get(int(character_id), {}).items())]


def _curve(con, curve_id: str) -> float | None:
    rows = con.execute("SELECT value FROM combat_curve_point WHERE curve_id=? ORDER BY ordinal", (curve_id,)).fetchall()
    return float(rows[0][0]) if rows else None


def _buff_duration(con, buff_id: str) -> float | None:
    row = con.execute("SELECT duration_magnitude_json FROM buff_definition WHERE definition_id=?", (buff_id,)).fetchone()
    if not row or not row[0]:
        return None
    data = json.loads(row[0])
    magnitude = data.get("ScalableFloatMagnitude") or {}
    value = magnitude.get("Value")
    if value is None:
        return None
    row_name = ((magnitude.get("Curve") or {}).get("RowName") or "None")
    if row_name != "None":                      # ScalableFloat with a curve row: Value x curve (level 1 point)
        curve = _curve(con, row_name)
        return None if curve is None else float(value) * curve
    return float(value)


def _value(con, spec) -> tuple[float | None, str]:
    kind, ident = spec
    if kind == "curve":
        return _curve(con, ident), f"curve {ident}"
    return _buff_duration(con, ident), f"buff {ident}"


def _hint_count(con, ability: str, ordinal: int, ge: str) -> int | None:
    row = con.execute("SELECT value_description_zh, damage_effect_ids_json FROM gameplay_ability_level_hint "
                      "WHERE ability_id=? AND ordinal=?", (ability, ordinal)).fetchone()
    if not row or ge not in json.loads(row[1] or "[]"):
        return None
    ids = json.loads(row[1] or "[]")
    parts = [p.strip() for p in str(row[0] or "").split("+")]
    if len(parts) != len(ids):
        return None
    m = re.search(r"\*(\d+)$", parts[ids.index(ge)])
    return int(m.group(1)) if m else 1


def build(static: Path = STATIC) -> tuple[str, list[str], list[str]]:
    """Return (module text, errors, summary lines); text is empty when validation failed."""
    _bootstrap()
    from src.services.battle_animation_window_service import BattleAnimationWindowService
    from src.storage.sqlite.static_game_data_dao import StaticGameDataDao

    errors: list[str] = []
    info: list[str] = []
    con = sqlite3.connect(f"file:{static.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        asset_paths = {r["asset_name"]: r["asset_path"] for r in con.execute(
            "SELECT asset_name, asset_path FROM combat_blueprint_asset WHERE asset_kind='ability'")}
        skill_damage = {r["damage_id"]: dict(r) for r in con.execute("SELECT * FROM skill_damage")}
        ability_names = {r["ability_id"]: r["name_zh"] for r in con.execute(
            "SELECT ability_id, name_zh FROM gameplay_ability_catalog")}
        buff_ids = {r[0] for r in con.execute("SELECT definition_id FROM buff_definition")}
        characters = {int(r[0]) for r in con.execute("SELECT character_id FROM character")}

        # 1. form ability assets
        paths: dict[int, dict[str, str]] = defaultdict(dict)
        for cid, abilities in FORM_ABILITIES.items():
            if cid not in characters:
                errors.append(f"FORM_ABILITIES {cid}: unknown character")
            folder = f"Ability_{cid % 1000:03d}_"
            for ab in abilities:
                path = asset_paths.get(ab)
                if path is None:
                    errors.append(f"FORM_ABILITIES {cid}: {ab} is not an ability asset")
                    continue
                if folder not in path:
                    errors.append(f"FORM_ABILITIES {cid}: {ab} lives outside {folder}* ({path})")
                paths[cid][ab] = path

        # 2. candidates of the form abilities and of the entry abilities (engine's own loader)
        with StaticGameDataDao(static) as dao:
            form_cands = {}
            for c in BattleAnimationWindowService.load_candidates(_BindingView(dao, paths), character_ids=list(paths)):
                form_cands[(c.ability_id, c.selector_key)] = c
            bound = {}
            for c in BattleAnimationWindowService.load_candidates(dao, character_ids=sorted(set(FORMS) | set(TEAM_BUFFS))):
                bound[(c.ability_id, c.selector_key)] = c

        def check_ge(where: str, ge: str) -> dict | None:
            row = skill_damage.get(ge)
            if row is None:
                errors.append(f"{where}: {ge} has no skill_damage row (replay could not price it)")
                return None
            if _rates(row) <= 0:
                errors.append(f"{where}: {ge} has no ATK/DEF/HP rate")
                return None
            if not row.get("ability_id"):
                errors.append(f"{where}: {ge} has no logged ability (skill_damage.ability_id)")
                return None
            return row

        # 3. Skia contact: periodic buff ticks inside the mode window (period and window from data)
        skia = FORMS[1008]
        period, _src = _value(con, skia["period"])
        mode_s, _src = _value(con, skia["duration"])
        skill = bound.get(("GA_Skia_Skill", "Default"))
        if period and mode_s and skill is not None and skill.trigger_end_offsets_us:
            marker = dict(skill.effect_hit_offsets_us).get(skia["start"][2])
            te = skill.trigger_end_offsets_us[0] / 1e6
            start = marker[0] / 1e6 if marker else None
            if start is None:
                errors.append("1008: mode marker missing from GA_Skia_Skill/Default")
            else:
                mode_end = start + mode_s
                length = round(mode_end - te, 3)
                tick_abs = [start + period * k for k in range(1, 100) if start + period * k < mode_end - EPS]
                offs = tuple(round(t - te, 3) for t in tick_abs if t >= te - EPS)
                ACTIONS["ShadowContact"] = dict(
                    cid=1008, ability="GA_Skia_Skill", form="skia_shadow", confidence="medium", timing="periodic",
                    source=f"periodic buff Buff_Skia_ShadowAtk every {period:g} s inside the {mode_s:g} s mode "
                           f"(started {start:.3f} s into the skill); one tick per target assumed",
                    parts=[X("Mode", length, [("GE_Player_Skia_SkillShadowAtk_Damage", offs)])])
        else:
            errors.append("1008: cannot derive the contact window (period / duration / skill candidate)")

        # 4. actions
        actions: dict[tuple[str, str], dict] = {}
        for name, spec in ACTIONS.items():
            key = (spec["ability"], f"Form:{name}")
            where = f"action {name}"
            cid = spec["cid"]
            ability_path = asset_paths.get(spec["ability"]) or ""
            if f"Ability_{cid % 1000:03d}_" not in ability_path:
                errors.append(f"{where}: {spec['ability']} is not an ability asset of {cid}")
            hits: dict[str, list[float]] = defaultdict(list)
            parts_out = []
            t0 = 0.0
            for part in spec["parts"]:
                if part["kind"] == "montage":
                    cand = form_cands.get((part["ability"], part["selector"]))
                    if cand is None:
                        errors.append(f"{where}: NO CANDIDATE {part['ability']}/{part['selector']}")
                        continue
                    te = cand.trigger_end_offsets_us[0] / 1e6 if cand.trigger_end_offsets_us else None
                    length = part["length_s"] if part["length_s"] is not None else te
                    if length is None:
                        errors.append(f"{where}: {part['ability']}/{part['selector']} has no trigger end; give a length")
                        continue
                    timeline = [(ge, [o / 1e6 for o in offs]) for ge, offs in cand.effect_hit_offsets_us]
                    timeline += [(ge, list(offs)) for ge, offs in part["extra"]]
                    for ge, offs in timeline:
                        if not _is_damage_effect(ge) or _dropped(ge):
                            continue
                        if check_ge(where, ge) is None:
                            continue
                        for off in offs:
                            if off > length + EPS:
                                errors.append(f"{where}: {ge} hit at {off:.3f} s after the part length {length:.3f} s")
                                continue
                            hits[ge].append(round(t0 + off, 3))
                    parts_out.append((part["ability"], part["selector"], round(float(length), 3)))
                else:
                    length = float(part["length_s"])
                    for ge, offs in part["hits"]:
                        if check_ge(where, ge) is None:
                            continue
                        if any(o < -EPS or o > length + EPS for o in offs):
                            errors.append(f"{where}: explicit {ge} offsets {offs} outside 0..{length}")
                        hits[ge].extend(round(t0 + o, 3) for o in offs)
                    if part["hint"]:
                        hab, ordinal, counts = part["hint"]
                        for ge, n in counts.items():
                            want = _hint_count(con, hab, ordinal, ge)
                            got = sum(len(o) for g, o in part["hits"] if g == ge)
                            if want is None:
                                errors.append(f"{where}: level hint {hab}#{ordinal} does not name {ge}")
                            elif want != n or got != n:
                                errors.append(f"{where}: {ge} x{got} vs level hint {hab}#{ordinal} *{want}")
                    parts_out.append((spec["ability"], part["label"], round(length, 3)))
                t0 += length
            if not hits:
                errors.append(f"{where}: no damage hit")
            ordered = tuple((ge, skill_damage[ge]["ability_id"], tuple(sorted(v))) for ge, v in sorted(hits.items()))
            gauge = round(sum(float(skill_damage[ge].get("heterochrome_add") or 0.0) * len(v)
                              for ge, _lg, v in ordered), 3)
            actions[key] = {
                "name": name, "character_id": cid, "form": spec["form"], "length_s": round(t0, 3),
                "hits": ordered, "hit_count": sum(len(v) for _g, _l, v in ordered), "gauge_total": gauge,
                "parts": tuple(parts_out), "timing": spec["timing"], "confidence": spec["confidence"],
                "source": spec["source"], "name_zh": ability_names.get(spec["ability"]) or "",
            }

        # 5. forms
        forms: dict[int, dict] = {}
        for cid, f in FORMS.items():
            where = f"FORMS {cid}"
            if f["buff"] not in buff_ids:
                errors.append(f"{where}: buff {f['buff']} not in buff_definition")
            duration, dsource = _value(con, f["duration"])
            if not duration:
                errors.append(f"{where}: no duration from {f['duration']}")
                continue
            ab, sel, marker = f["start"]
            cand = bound.get((ab, sel))
            if cand is None:
                errors.append(f"{where}: entry candidate {ab}/{sel} missing")
                continue
            if marker is None:
                offset = 0.0
            else:
                offs = dict(cand.effect_hit_offsets_us).get(marker)
                if not offs:
                    errors.append(f"{where}: marker {marker} is not an effect of {ab}/{sel}")
                    continue
                offset = round(offs[0] / 1e6, 3)
            rule = {"code": f["code"], "name_zh": f["name_zh"], "buff": f["buff"], "duration_s": float(duration),
                    "duration_source": dsource, "start": (ab, sel, offset), "ends_on_swap": f["ends_on_swap"],
                    "pauses_off_field": f["pauses_off_field"], "policy": f["policy"],
                    "body_seqs": tuple(f.get("body_seqs") or ())}
            if f["policy"] == "check" and "exit_seq" in f:
                remain, _s = _value(con, f["exit_remain"])
                if remain is None:
                    errors.append(f"{where}: no exit remain value")
                    continue
                rule["exit_seq"] = f["exit_seq"]
                rule["exit_window_s"] = (round(duration - remain, 3), float(duration))
            if f["policy"] == "size":
                rule["groups"] = dict(f["groups"])
                for k in ("terminal_seq", "tail_seq", "tail_per_group", "tail_max"):
                    if k in f:
                        rule[k] = f[k]
                rule["after_seqs"] = tuple(f.get("after_seqs") or ())
                if "fill" in f:
                    fill = f["fill"]
                    keys = []
                    for n in fill["actions"]:
                        k = next((k for k in actions if actions[k]["name"] == n), None)
                        if k is None:
                            errors.append(f"{where}: fill action {n} unknown")
                        keys.append(k)
                    rule["fill"] = {"after_seq": fill["after_seq"], "actions": tuple(keys), "max": int(fill["max"])}
            if f["policy"] == "window":
                start_s, _s = _value(con, f["window_from"])
                if start_s is None:
                    errors.append(f"{where}: no window start")
                    continue
                rule["window_seq"] = f["window_seq"]
                rule["window_s"] = (float(start_s), float(duration))
            if f["policy"] == "check" and "period" in f:
                rule["period_s"], _s = _value(con, f["period"])
            forms[cid] = rule

        # 6. team buffs for the planner
        team_buffs: dict[int, tuple] = {}
        for cid, specs in TEAM_BUFFS.items():
            rows = []
            for ab, sel, marker, dur in specs:
                where = f"TEAM_BUFFS {cid} {ab}/{sel}"
                cand = bound.get((ab, sel))
                duration, dsource = _value(con, dur)
                if cand is None or not duration:
                    errors.append(f"{where}: candidate or duration missing")
                    continue
                offset = None
                if marker == BEGIN:
                    offset = 0.0
                elif marker is not None:
                    offs = dict(cand.effect_hit_offsets_us).get(marker)
                    if not offs:
                        errors.append(f"{where}: marker {marker} not on the candidate")
                        continue
                    offset = round(offs[0] / 1e6, 3)
                rows.append((ab, sel, offset, float(duration), dsource))
            team_buffs[cid] = tuple(rows)

        # 7. skill levels: form GEs without a levelled owner need a parent skill
        level_parents: dict[int, dict[str, str]] = {}
        skills = defaultdict(set)
        for r in con.execute("SELECT character_id, skill_id FROM character_skill"):
            skills[int(r[0])].add(r[1])
        with StaticGameDataDao(static) as dao:
            owners = {}
            for key, a in actions.items():
                cid = a["character_id"]
                for ge, logged, _offs in a["hits"]:
                    owners[(cid, ge)] = (logged, tuple(dao.list_skill_level_ability_candidates(cid, ge)))
            need = {(cid, logged) for (cid, ge), (logged, cands) in owners.items()
                    if not cands and logged not in skills[cid]}
            for cid, logged in sorted(need):
                parent = (LEVEL_PARENTS.get(cid) or {}).get(logged)
                if parent is None:
                    errors.append(f"LEVEL_PARENTS {cid}: {logged} has unlevelled form GEs and no parent skill")
                    continue
                if parent not in skills[cid]:
                    errors.append(f"LEVEL_PARENTS {cid}: {parent} is not a skill of the character")
                    continue
                siblings = {ge for (c, ge), (lg, cands) in owners.items() if c == cid and lg == logged and parent in cands}
                hinted = {g for (c, g), (lg, _c) in owners.items() if c == cid and lg == logged} & {
                    ge for (ge,) in con.execute(
                        "SELECT d.value FROM gameplay_ability_level_hint h, json_each(h.damage_effect_ids_json) d "
                        "WHERE h.ability_id=?", (parent,))}
                if not siblings and not hinted:
                    errors.append(f"LEVEL_PARENTS {cid}: {parent} levels no GE logged under {logged}")
                    continue
                level_parents.setdefault(cid, {})[logged] = parent
            for cid, mapping in LEVEL_PARENTS.items():
                for logged in mapping:
                    if (cid, logged) not in need:
                        errors.append(f"LEVEL_PARENTS {cid}: {logged} does not need a parent")

        # 8. form steps
        steps: dict[tuple[int, int], dict] = {}
        name_to_key = {v["name"]: k for k, v in actions.items()}
        for (cid, seq), (names, slot, repeat, role, group) in FORM_STEPS.items():
            keys = []
            for n in names:
                if n not in name_to_key:
                    errors.append(f"FORM_STEPS {cid}#{seq}: unknown action {n}")
                    continue
                if actions[name_to_key[n]]["character_id"] != cid:
                    errors.append(f"FORM_STEPS {cid}#{seq}: action {n} belongs to another character")
                keys.append(name_to_key[n])
            if slot not in ("basic", "skill", "ultimate", "qte", "other"):
                errors.append(f"FORM_STEPS {cid}#{seq}: slot {slot}")
            steps[(cid, seq)] = {"actions": tuple(keys), "slot": slot, "repeat": int(repeat), "role": role,
                                 "group": group, "replaces": REPLACES_RUNNABLE.get((cid, seq))}
            rule = forms.get(cid)
            if rule and role in ("body", "terminal", "tail", "window") and seq not in (
                    set(rule["body_seqs"]) | {rule.get("terminal_seq"), rule.get("tail_seq"), rule.get("window_seq")}):
                errors.append(f"FORM_STEPS {cid}#{seq}: role {role} but FORMS does not list the step")
    finally:
        con.close()

    info += [f"form abilities {sum(len(v) for v in paths.values())} for {len(paths)} characters",
             f"actions {len(actions)}: " + ", ".join(f"{v['name']}={v['hit_count']}h/{v['length_s']}s"
                                                     for v in actions.values()),
             f"forms {sorted(forms)} | form steps {len(steps)}"]
    if errors:
        return "", errors, info
    text = render(paths, actions, forms, steps, team_buffs, level_parents)
    compile(text, "team_form_actions.py", "exec")
    ns: dict = {}
    exec(text, ns)  # noqa: S102 - round-trip check of our own generated data
    if ns["FORM_ACTIONS"] != actions or ns["FORMS"] != forms or ns["FORM_STEPS"] != steps             or ns["TEAM_BUFFS"] != team_buffs or ns["LEVEL_PARENTS"] != level_parents:
        errors.append("round-trip of the generated module does not reproduce the data")
        return "", errors, info
    return text, errors, info


def _lit(value) -> str:
    return repr(value)


def render(paths, actions, forms, steps, team_buffs, level_parents) -> str:
    gen_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = [
        "# 队伍模拟：变身/形态中的动作（由 tools/gen_team_form_actions.py 生成，勿手改）",
        "# GENERATED FILE - DO NOT EDIT.  Regenerate with scratchpad/v230/tools/gen_team_form_actions.py",
        f"# generator sha256 {gen_sha}",
        '"""Form-state actions for the team simulator (generated, do not edit).',
        "",
        "FORM_ACTIONS[(ability_id, 'Form:<Name>')] = {name, character_id, form, length_s, hits, hit_count,",
        "gauge_total, parts, timing, confidence, source, name_zh}.  ``hits`` = ((ge, logged_ability_id,",
        "(offset_s, ...)), ...): rows carry the logged ability (skill_damage.ability_id), as the game logs them.",
        "FORMS[cid] = the form window rule (duration from game data, start marker, policy).",
        "FORM_STEPS[(cid, seq)] = {actions, slot, repeat, role, group, replaces}: approved steps that run form",
        "actions (applied by gen_team_rotation_data.py).",
        "TEAM_BUFFS[cid] = ((ability, selector, offset_s or None = step end, duration_s, source), ...): team buffs",
        "the visit-order planner wants over a form window (ranking only).",
        "LEVEL_PARENTS[cid] = {logged ability: character skill}: form GEs the replay cannot level use that skill's",
        "level (the simulator adds the logged ability to the build's skill levels).",
        '"""',
        "",
        f"SCHEMA_VERSION = {SCHEMA_VERSION}",
        "",
        "FORM_ABILITY_PATHS = {",
    ]
    for cid, abilities in sorted(paths.items()):
        out.append(f"    {cid}: {{")
        for ab, path in abilities.items():
            out.append(f"        {ab!r}: {path!r},")
        out.append("    },")
    out += ["}", "", f"DROP_GES = {_lit(tuple(sorted(DROP_GES)))}",
            f"DROP_SUFFIXES = {_lit(DROP_SUFFIXES)}", "", "FORM_ACTIONS = {"]
    for key, a in actions.items():
        out.append(f"    {key!r}: {{")
        for k in ("name", "character_id", "form", "length_s", "hit_count", "gauge_total", "timing", "confidence",
                  "name_zh", "source", "parts"):
            out.append(f"        {k!r}: {a[k]!r},")
        out.append("        'hits': (")
        for h in a["hits"]:
            out.append(f"            {h!r},")
        out.append("        ),")
        out.append("    },")
    out += ["}", "", "FORMS = {"]
    for cid, f in forms.items():
        out.append(f"    {cid}: {{")
        for k, v in f.items():
            out.append(f"        {k!r}: {v!r},")
        out.append("    },")
    out += ["}", "", "FORM_STEPS = {"]
    for key, s in steps.items():
        out.append(f"    {key!r}: {s!r},")
    out += ["}", "", "TEAM_BUFFS = {"]
    for cid, rows in team_buffs.items():
        out.append(f"    {cid}: {rows!r},")
    out += ["}", "", f"LEVEL_PARENTS = {level_parents!r}", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="do not write; fail if the output is stale")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if INTERNAL.is_dir():
        for d in (INTERNAL, INTERNAL / "PySide6", INTERNAL / "shiboken6"):
            if d.is_dir():
                os.add_dll_directory(str(d))
    text, errors, info = build()
    for line in info:
        print(line)
    if errors:
        print(f"\nVALIDATION FAILED ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 2
    data = text.encode("utf-8")
    if args.check:
        current = args.out.read_bytes() if args.out.is_file() else b""
        if current != data:
            print(f"STALE: {args.out} differs from the generated module", file=sys.stderr)
            return 1
        print(f"up to date: {args.out}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"wrote {args.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
