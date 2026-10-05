"""Generate ``src/services/team_custom_actions.py`` (the action palette of the custom-cycle mode).

The custom-cycle mode ("직접 입력") of the team simulator lets the user write a flat team sequence such as
``제로 서포트 > 제로 E > 제로 평타x3 > 일로이 교체 > 일로이 Q``.  Generic tokens (basic / heavy / E / Q ...)
resolve through the table generated here: per character "state -> slot -> chain or variants of
(ability_id, selector) combos", plus length / hits / gauge / energy per action, display names in four languages,
named-action aliases and the cooldown / energy numbers the static DB has.

Inputs (all read-only):
  work/rotation_research/action_catalog.json     animation candidates per character
  work/l10n_root/data/game_static.sqlite3        skill_damage (gauge / energy per hit), ability names, curves
  src/services/team_form_actions.py              FORM_ACTIONS / FORMS (executed from the file, no src import)
  src/services/team_rotation_data.py             approved steps (est_s, gauge_set), NORMAL_ENTRY, Q_TIME_STOP_S
  src/services/team_custom_notation.py           TOKEN_ALIASES (literal; alias collision checks only)
  src/i18n_display.py, src/i18n_data_{en,ja}.py  display names (literal tables)

The hand table HAND below adds what the catalog cannot tell: which selector is the E / hold E / heavy attack,
chains, combos and transformation states.  Slots filled automatically: support (QTE), basic (Melee1..N),
counter (PerfectEvade/Atk), plunge (AirAttackEnd), entry_attack (Appear/AirAttackEnd), ult (single candidate
or Default).  Append-only rule for ``special`` and for variant positions: new entries go to the end so saved
cycles keep their meaning.

Run order: gen_team_form_actions.py -> gen_team_rotation_data.py -> gen_team_custom_actions.py.
Any validation error aborts before anything is written.

usage: gen_team_custom_actions.py [--check] [--out PATH]
  --check   write nothing; exit 1 when the module on disk differs from what would be generated
  --out     output path (default: work/l10n_root/src/services/team_custom_actions.py)

Run with the Python 3.11 interpreter (PYTHONUTF8=1).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

SP = Path(__file__).resolve().parent.parent          # scratchpad/v230
WORK = SP / "work"
CATALOG = WORK / "rotation_research" / "action_catalog.json"
STATIC = WORK / "l10n_root" / "data" / "game_static.sqlite3"
SRC = WORK / "l10n_root" / "src"
OUT = SRC / "services" / "team_custom_actions.py"
FORM_MODULE = SRC / "services" / "team_form_actions.py"
ROTATION_MODULE = SRC / "services" / "team_rotation_data.py"
NOTATION_MODULE = SRC / "services" / "team_custom_notation.py"

SCHEMA_VERSION = 1
DODGE_S = 0.5                    # approved Cang step "일반 회피"
DEFAULT_STEP_S = 1.0             # team_simulation_service.DEFAULT_STEP_S (time-only entry without an estimate)
LANGS = ("zh", "ko", "en", "ja")
DOT_TICK_GES = {"GE_Player_Zankou_DotDamage", "GE_Player_Zankou_DotUltraDamage",
                "GE_Player_Lacrimosa_Blood_Damage", "GE_Player_Lacrimosa_Blood_Damage_LV6"}
QUOTES = "「」『』“”\"'"
TAG = re.compile(r"<[^>]*>")

# E / Q cooldown and Q cost the static DB holds: cid -> {field: curve id}
RESOURCE_CURVES = {
    1004: {"e_cd_s": "Lacrimosa_Skill_cooldown_1", "q_cd_s": "Lacrimosa_UltraSkilll_cooldown_1",
           "q_cost": "Lacrimosa_UltraSkill_ChargeCost_1"},
    1071: {"q_cd_s": "Chaos_UltraskillCD"},
}
RESOURCE_VALUES = {1004: {"e_cd_s": 15.0, "q_cd_s": 30.0, "q_cost": 45.0}, 1071: {"q_cd_s": 20.0}}
# community numbers: tooltip hints on empty fields only, never used in a calculation
RESOURCE_HINTS = {1051: {"e_cd_s": 16.0, "q_cd_s": 15.0}, 1020: {"e_cd_s": 16.0},
                  1023: {"e_cd_s": 14.0, "q_cd_s": 20.0}, 1019: {"e_cd_s": 6.0}}
OWN_RESOURCE = (1052, 1076)      # Hotori's clock, Shinku's own resource: no ultimate-energy check
STATE_CURVES = {"chaos_ultra": ("Chaos_Ultraskill_Duration", 12.0)}


def A(ab, sel):
    return (ab, sel)


def T(est, label):
    """Time-only entry (no animation data): est seconds (None = DEFAULT_STEP_S)."""
    return ("@time", est, label)


def chain(*entries, loop_from=0):
    return {"mode": "chain", "entries": [list(e) if isinstance(e, list) else [e] for e in entries],
            "loop_from": loop_from}


def variants(*entries):
    return {"mode": "variants", "entries": [list(e) if isinstance(e, list) else [e] for e in entries],
            "loop_from": 0}


# cid -> {"base": {slot: chain | variants}, "states": {code: {...}}, "basic_after": {key: hit}, "time_only": {hit: s}}
HAND = {
    1003: {"base": {"skill": variants(A("GA_Sagiri_Skill", "Skill1")),
                    "skill_hold": variants(A("GA_Sagiri_Skill", "Skill2"))}},
    1004: {"base": {"skill": variants(A("GA_Lacrimosa_Skill", "Skill1")),
                    "ult": variants(A("GA_Lacrimosa_UltraSkill", "UltraSkillB")),
                    "heavy": variants(A("GA_Lacrimosa_Melee", "Fire")),
                    "special": variants(A("GA_Lacrimosa_SwitchSkill", "SwitchModA"))},
           "basic_after": {("GA_Lacrimosa_Skill", "Skill1"): 5}},
    1008: {"base": {"skill": variants(A("GA_Skia_Skill", "Default"))},
           "states": {"skia_shadow": {"start": ("GA_Skia_Skill", "Default"), "slots": {
               "special": variants(A("GA_Skia_Skill", "Form:ShadowContact")),
               "basic": chain(A("GA_Skia_ShadowEvadeEnd", "ShadowEvadeEnd"))},
               "exit": [("GA_Skia_ShadowEvadeEnd", "ShadowEvadeEnd")]}},
           "time_only": {4: 1.51}},
    1010: {"base": {"skill": variants(A("GA_Nanally_Skill", "Skill")),
                    "heavy": chain(A("GA_Nanally_Melee", "ExtraAttack1"), A("GA_Nanally_Melee", "ExtraAttack2"),
                                   A("GA_Nanally_Melee", "ExtraAttack3")),
                    "special": variants(A("GA_Nanally_Melee", "Fire"))}},
    1019: {"base": {"skill": variants(A("GA_Mint019_Skill", "Skill")),
                    "special": variants(A("GA_Mint019_Melee", "Begin"))}},
    1020: {"base": {"skill": variants(A("GA_Haniel_Skill", "Skill1")),
                    "heavy": variants(A("GA_Haniel_Melee", "Branch1"))}},
    1021: {"base": {"skill": variants(A("GA_Edgar_Skill", "Skill"))}},
    1023: {"base": {"skill": variants(T(0.892, "公平之心"), A("GA_Cang_SkillA", "SkillA")),
                    "heavy": variants(A("GA_Cang_Melee", "Branch1"), A("GA_Cang_Melee", "Branch2"))},
           "time_only": {3: 0.9}},
    1025: {"base": {"skill": variants(A("GA_Hathor_Skill", "Short")),
                    "skill_hold": variants([A("GA_Hathor_Skill", "Power"), A("GA_Hathor_Skill", "PowerEnd")]),
                    "heavy": variants(A("GA_Hathor_Melee", "BranchEnd"))},
           "states": {"hathor_dispatch": {"start": ("GA_Hathor_UltraSkill", "Default"), "slots": {
               "skill": chain(A("GA_Hathor_Skill2", "Form:Cyclone1"), A("GA_Hathor_Skill2", "Form:Cyclone2"),
                              A("GA_Hathor_Skill2", "Form:Cyclone3"))}}}},
    1033: {"base": {"skill": variants(A("GA_Adler_Skill", "Default")),
                    "heavy": variants(A("GA_Adler_Melee", "Branch")),
                    "special": variants(A("GA_Adler_Melee", "Fire"))}},
    1036: {"base": {"skill": variants(A("GA_Zankou_Skill", "PowerSkill1"), A("GA_Zankou_Skill", "Skill1")),
                    "ult": chain(A("GA_Zankou_UltraSkillMagic", "Form:MagicQ"),
                                 A("GA_Zankou_UltraSkillForce", "Form:ForceQ")),
                    "heavy": variants(A("GA_Zankou_Melee", "Branch1")),
                    "special": variants(A("GA_Zankou_UltraSkill", "UltraSkill"))},
           "states": {"zankou_fantasy": {"start": ("GA_Zankou_Skill", "PowerSkill1"), "slots": {
               "basic": chain(A("GA_Zankou_MeleeMagic", "Form:MagicChain")),
               "skill": variants(A("GA_Zankou_Skill", "PowerSkill2"), A("GA_Zankou_Skill", "Skill2"))},
               "exit": [("GA_Zankou_Skill", "PowerSkill2")]}}},
    1039: {"base": {"skill": variants(A("GA_Fadia_Skill", "Skill"))},
           "states": {"fadia_godfoe": {"start": ("GA_Fadia_UltraSkill", "UltraSkill"), "slots": {
               "basic": chain(A("GA_Fadia_UltraSkill_Melee", "Form:GodfoeChase"))}}}},
    1042: {"base": {"skill": variants(A("GA_BlackBird_Skill", "Default")),
                    "heavy": chain(A("GA_BlackBird_Melee", "Branch1"), A("GA_BlackBird_Melee", "Branch2"),
                                   A("GA_BlackBird_Melee", "Branch3"))},
           "states": {"raven_witch": {"start": ("GA_BlackBird_UltraSkill", "Default"), "slots": {
               "basic": chain(A("GA_BlackBird_Evolve_Melee", "Form:WitchA3to5"),
                              A("GA_BlackBird_Evolve_Melee", "Form:WitchA1to5"), loop_from=1),
               "skill": variants(A("GA_BlackBird_Evolve_Skill", "Form:WitchSkill")),
               "ult": variants(A("GA_BlackBird_Evolve_UltraSkill", "Form:WitchFinisher")),
               "support": variants(A("GA_BlackBird_QTE", "QTE_tran")),
               "counter": variants(A("GA_BlackBird_PerfectEvade", "Atk_tran")),
               "plunge": variants(A("GA_BlackBird_Appear", "AirAttackEnd_tran"))},
               "exit": [("GA_BlackBird_Evolve_UltraSkill", "Form:WitchFinisher")]}}},
    1051: {"base": {"skill": variants(A("GA_Female051_Skill", "Default"))}},
    1052: {"base": {"skill": variants(A("GA_Jin_Skill", "Skill")),
                    "heavy": variants(A("GA_Jin_Melee", "Branch1"))},
           "states": {"jin_tachi": {"start": ("GA_Jin_UltraSkill", "UltraSkill"), "slots": {
               "basic": chain(A("GA_Jin_UltraSkill_Melee", "Form:TachiSet"),
                              A("GA_Jin_UltraSkill_Melee", "Form:TachiSet"),
                              A("GA_Jin_UltraSkill_Melee", "Form:TachiFinisher"))},
               "exit": [("GA_Jin_UltraSkill_Melee", "Form:TachiFinisher")]}}},
    1054: {"base": {"skill": variants(A("GA_Daffodill_Skill", "Skill1"), A("GA_Daffodill_Skill", "Skill2")),
                    "ult": variants(A("GA_Daffodill_UltraSkill", "Ultraskill")),
                    "heavy": variants(A("GA_Daffodill_Melee", "Branch1"))}},
    1055: {"base": {"skill": variants(A("GA_Kuhara_Skill", "Skill")),
                    "heavy": variants(A("GA_Kuhara_Melee", "BranchPower"), A("GA_Kuhara_Melee", "BranchPowerShort"))}},
    1057: {"base": {"skill": variants(A("GA_Akane_Skill", "Skill")),
                    "skill_hold": variants(A("GA_Akane_Skill", "Skillhold"))},
           "states": {"akane_cadenza": {"start": ("GA_Akane_UltraSkill", "Default"), "slots": {
               "ult": variants(A("GA_Akane_UltraSkill_End", "Form:SonicBoom2")),
               "special": variants(A("GA_Akane_Skill_instead", "Form:Resonance"))},
               "exit": [("GA_Akane_UltraSkill_End", "Form:SonicBoom2")]}}},
    1070: {"base": {"skill": variants(A("GA_Mitsuki_Skill", "Default")),
                    "special": variants(A("GA_Mitsuki_Evade", "EvadeBranchEntry"))}},
    1071: {"base": {"skill": variants(A("GA_Chaos071_Skill", "Skill")),
                    "heavy": chain(A("GA_Chaos071_Melee", "Branch1"), A("GA_Chaos071_Melee", "Branch2"))},
           "states": {"chaos_ultra": {"start": ("GA_Chaos071_UltraSkill", "Default"), "start_at_end": True,
                                      "slots": {
               "basic": chain(*(A("GA_Chaos071_Melee", f"Melee{i}_Ultra") for i in range(1, 6))),
               "heavy": chain(A("GA_Chaos071_Melee", "Branch1_Ultra"), A("GA_Chaos071_Melee", "Branch2_Ultra")),
               "plunge": variants(A("GA_Chaos071_Melee", "AirAttackEnd_Ultra"))}}}},
    1072: {"base": {"skill": variants(A("GA_Radio072_Skill", "Skill1")),
                    "heavy": variants(A("GA_Radio072_Melee", "Branch")),
                    "special": variants(A("GA_Radio072_QTE_BackToLTE", "QTE"))}},
    1073: {"base": {"skill": variants(A("GA_Chiichan073_Skill", "Skill1"), A("GA_Chiichan073_Skill", "Skill2"),
                                      A("GA_Chiichan073_Skill", "Skill3")),
                    "skill_hold": variants(A("GA_Chiichan073_Skill", "LoopHold")),
                    "heavy": variants(A("GA_Chiichan073_Melee", "Branch1"))}},
    1075: {"base": {"skill": variants(A("GA_Oneiroi_Skill", "Skill")),
                    "heavy": variants(A("GA_Oneiroi_Melee", "Branch33"), A("GA_Oneiroi_Melee", "Branch5"))}},
    1076: {"base": {"skill": variants(A("GA_Shinku_Skill", "Skill")),
                    "heavy": variants(A("GA_Shinku_Melee", "Branch1"))},
           "states": {"shinku_rage": {"start": ("GA_Shinku_UltraSkill", "Default"), "slots": {
               "basic": chain(A("GA_Shinku_Melee_Rage", "Form:RageMelee")),
               "skill": variants(A("GA_Shinku_Skill_Rage", "Form:RageSkill")),
               "ult": chain(A("GA_Shinku_UltraSkill_Rage_Pre", "Form:RageExecution1"),
                            A("GA_Shinku_UltraSkill_Rage_Pre", "Form:RageExecution2"),
                            A("GA_Shinku_UltraSkill_Rage_Pre", "Form:RageExecution3"),
                            A("GA_Shinku_UltraSkill_Rage", "Form:RageDragonflame"))},
               "exit": [("GA_Shinku_UltraSkill_Rage", "Form:RageDragonflame")]}}},
}
SLOT_ORDER = ("support", "basic", "heavy", "skill", "skill_hold", "ult", "counter", "plunge", "entry_attack",
              "special")


def norm(text: str) -> str:
    """Alias / name normal form: NFKC, casefold, quotes dropped, whitespace collapsed."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = "".join(" " if ch in QUOTES else ch for ch in text)
    return " ".join(text.casefold().split())


def load_module(path: Path) -> tuple[dict, str]:
    """A generated data module as a namespace (executed from its file; no src import)."""
    raw = path.read_bytes()
    ns: dict = {}
    exec(compile(raw.decode("utf-8"), str(path), "exec"), ns)  # noqa: S102 - our own generated data
    return ns, hashlib.sha256(raw).hexdigest()


def literal_tables(path: Path, names: tuple[str, ...]) -> dict:
    """Top-level literal assignments of a source file (ast only: i18n_display imports PySide6)."""
    out: dict = {}
    if not path.is_file():
        return out
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target, value = node.target.id, node.value
        if target in names:
            try:
                out[target] = ast.literal_eval(value)
            except Exception:
                pass
    return out


def build() -> tuple[str, list[str], list[str]]:
    """Return (module text, errors, summary lines); text is empty when validation failed."""
    errors: list[str] = []
    info: list[str] = []
    raw_cat = CATALOG.read_bytes()
    catalog = {int(c["character_id"]): c for c in json.loads(raw_cat) if c.get("has_graduation_template")}
    forms_ns, form_sha = load_module(FORM_MODULE)
    rot_ns, rot_sha = load_module(ROTATION_MODULE)
    form_actions, forms = forms_ns["FORM_ACTIONS"], forms_ns["FORMS"]
    characters, normal_entry, q_stop = rot_ns["CHARACTERS"], rot_ns["NORMAL_ENTRY"], rot_ns["Q_TIME_STOP_S"]

    con = sqlite3.connect(f"{STATIC.absolute().as_uri()}?mode=ro", uri=True)
    try:
        damage = {r[0]: (float(r[1] or 0.0), float(r[2] or 0.0)) for r in con.execute(
            "SELECT damage_id, heterochrome_add, charge_add FROM skill_damage")}
        ability_names = {a: TAG.sub("", n).strip() for a, n in con.execute(
            "SELECT ability_id, name_zh FROM gameplay_ability_catalog") if n}
        curves: dict[str, list[float]] = {}
        for curve_id, value in con.execute("SELECT curve_id, value FROM combat_curve_point ORDER BY curve_id, ordinal"):
            curves.setdefault(curve_id, []).append(float(value))
        templates = {int(r[0]) for r in con.execute("SELECT character_id FROM character_graduation_template")}
    finally:
        con.close()
    damage_sha = hashlib.sha256(json.dumps(sorted((k, v[0], v[1]) for k, v in damage.items())).encode()).hexdigest()

    ko_tables = literal_tables(SRC / "i18n_display.py", ("CHARACTERS", "OFFICIAL_TERMS", "EXTRA_TERMS", "NATIVE_TERMS"))
    display = {lang: literal_tables(SRC / f"i18n_data_{lang}.py", ("DISPLAY",)).get("DISPLAY", {}) for lang in ("en", "ja")}
    token_aliases = literal_tables(NOTATION_MODULE, ("TOKEN_ALIASES",)).get("TOKEN_ALIASES", {})
    if not token_aliases:
        errors.append(f"TOKEN_ALIASES not found as a literal in {NOTATION_MODULE.name}")
    generic = {norm(a) for per_lang in token_aliases.values() for aliases in per_lang.values() for a in aliases}

    def translate(zh: str, lang: str) -> str:
        if lang == "zh":
            return zh
        if lang == "ko":
            for table in ("CHARACTERS", "OFFICIAL_TERMS", "EXTRA_TERMS", "NATIVE_TERMS"):
                hit = ko_tables.get(table, {}).get(zh)
                if hit:
                    return hit
            return ""
        return display[lang].get(zh) or ""

    # approved keys, estimates and gauge-setting actions
    approved_est: dict[tuple, float] = {}
    approved_keys: dict[int, set] = {}
    gauge_set: dict[tuple, float] = {}
    for cid, c in characters.items():
        keys = approved_keys.setdefault(int(cid), set())
        for st in c["variants"]["approved"]["steps"]:
            for key in (st.get("combo") or ((st.get("ability_id"), st.get("selector")),)):
                key = tuple(key)
                if not key[0]:
                    continue
                keys.add(key)
                if st.get("est_s") is not None and not st.get("combo"):
                    approved_est.setdefault(key, float(st["est_s"]))
                if st.get("gauge_set") is not None and not st.get("combo"):
                    gauge_set[key] = float(st["gauge_set"])
        if int(cid) in normal_entry:
            keys.add(tuple(normal_entry[int(cid)]))
    if set(catalog) != templates:
        errors.append(f"catalog template characters != graduation templates: {sorted(set(catalog) ^ templates)}")
    if set(catalog) != {int(c) for c in characters}:
        errors.append(f"catalog template characters != approved rotations: {sorted(set(catalog) ^ set(characters))}")

    # ── every placeable action ──
    actions: dict[tuple, dict] = {}
    for cid, c in sorted(catalog.items()):
        for cand in c["animation_candidates"]:
            key = (cand["ability_id"], cand["selector"])
            hits = [(e["ge"], int(e["hits"])) for e in cand["damage_effects"]]
            trigger = list(cand.get("trigger_end_s") or ())
            last_hit = max((max(e["at_s"]) for e in cand["damage_effects"] if e.get("at_s")), default=0.0)
            if trigger and trigger[0]:                       # the rule of team_simulation_service._step_length_us
                length, source = float(trigger[0]), "trigger_end"
            elif trigger:                                    # trigger end 0.0 (channel montage): _step_length_us = 0
                length, source = round(last_hit + 0.1, 3), "last_hit"
            elif key in approved_est:
                length, source = approved_est[key], "approved_est"
            else:
                length, source = float(cand["duration_s"]), "duration"
            counted = [(ge, n) for ge, n in hits if ge in damage and ge not in DOT_TICK_GES]
            if key in actions:
                errors.append(f"{cid}: duplicate action key {key}")
            actions[key] = {
                "character_id": cid, "name_zh": ability_names.get(key[0], ""), "length_s": round(length, 3),
                "length_source": source, "est_s": approved_est.get(key),
                "hits": sum(n for _ge, n in counted),
                "gauge": round(sum(damage[ge][0] * n for ge, n in counted), 3),
                "energy": round(sum(damage[ge][1] * n for ge, n in counted), 3),
                "gauge_set": gauge_set.get(key), "time_stop_s": q_stop.get(key[0]), "form": ""}
    for key, fa in form_actions.items():
        key = tuple(key)
        cid = int(fa["character_id"])
        if cid not in catalog:
            continue
        if key in actions:
            errors.append(f"{cid}: form action {key} collides with a catalog candidate")
        counted = [(ge, len(offs)) for ge, _logged, offs in fa["hits"] if ge in damage and ge not in DOT_TICK_GES]
        actions[key] = {
            "character_id": cid, "name_zh": fa.get("name_zh") or ability_names.get(key[0], ""),
            "length_s": round(float(fa["length_s"]), 3), "length_source": "form", "est_s": None,
            "hits": sum(n for _ge, n in counted),
            "gauge": round(sum(damage[ge][0] * n for ge, n in counted), 3),
            "energy": round(sum(damage[ge][1] * n for ge, n in counted), 3),
            "gauge_set": gauge_set.get(key), "time_stop_s": q_stop.get(key[0]), "form": str(fa.get("form") or "")}
    for key, value in gauge_set.items():
        if key not in actions:
            errors.append(f"gauge_set key {key} is not an action")

    # ── slot tables ──
    palette: dict[int, dict] = {}
    dropped_aliases: list[str] = []
    named: dict[int, dict] = {}
    names: dict[int, dict] = {}
    action_index: dict[tuple, tuple] = {}
    stats = {"entries": 0, "time_only": 0, "states": 0}

    def entry_of(cid: int, combo: list) -> tuple:
        if len(combo) == 1 and combo[0][0] == "@time":
            _tag, est, label = combo[0]
            stats["time_only"] += 1
            return ("@time", float(DEFAULT_STEP_S if est is None else est), str(label),
                    "default_1s" if est is None else "research_est")
        keys = []
        for key in combo:
            key = tuple(key)
            if key[0] == "@time":
                errors.append(f"{cid}: a time-only entry cannot be part of a combo")
                continue
            action = actions.get(key)
            if action is None or action["character_id"] != cid:
                errors.append(f"{cid}: {key} is not a catalog candidate or form action of this character")
                continue
            if action["hits"] and action["length_s"] <= 0:
                errors.append(f"{cid}: {key} has hits but no length")
            keys.append(key)
        return tuple(keys)

    def table_of(cid: int, slot: str, spec: dict, base: bool) -> dict:
        entries = tuple(entry_of(cid, combo) for combo in spec["entries"])
        stats["entries"] += len(entries)
        cd = None
        if base and slot in ("skill", "skill_hold"):
            cd = "E"
        elif base and slot == "ult":
            cd = "Q"
        return {"mode": spec["mode"], "loop_from": int(spec.get("loop_from") or 0), "cd": cd, "entries": entries}

    for cid, c in sorted(catalog.items()):
        slots = c["skill_slots"]
        have = {(a["ability_id"], a["selector"]) for a in c["animation_candidates"]}
        hand = HAND.get(cid, {})
        base: dict = {}
        qte = (slots["4"], "QTE")
        if qte not in have:
            errors.append(f"{cid}: no support skill candidate {qte}")
        base["support"] = variants(qte)
        melee = slots["1"]
        present = sorted(int(s[5:]) for ab, s in have if ab == melee and len(s) == 6 and s.startswith("Melee")
                         and s[5:].isdigit() and s[5:] != "0")
        time_only = hand.get("time_only", {})
        if present:
            base["basic"] = chain(*(A(melee, f"Melee{i}") if i in present else T(time_only.get(i), f"Melee{i}")
                                    for i in range(1, max(present) + 1)))
        for hit in time_only:
            if hit in present:
                errors.append(f"{cid}: time_only hit {hit} has an animation candidate")
        counter = next(((ab, s) for ab, s in sorted(have) if ab.endswith("PerfectEvade") and s == "Atk"), None)
        if counter:
            base["counter"] = variants(counter)
        if (melee, "AirAttackEnd") in have:
            base["plunge"] = variants((melee, "AirAttackEnd"))
        appear = next(((ab, s) for ab, s in sorted(have) if ab.endswith("_Appear") and s == "AirAttackEnd"), None)
        if appear:
            base["entry_attack"] = variants(appear)
        ults = sorted((ab, s) for ab, s in have if ab == slots["3"])
        if len(ults) == 1:
            base["ult"] = variants(ults[0])
        elif "ult" not in hand.get("base", {}):
            pick = next((u for u in ults if u[1] == "Default"), None)
            if pick is None:
                errors.append(f"{cid}: the ultimate needs a hand entry {ults}")
            else:
                base["ult"] = variants(pick)
        base.update(hand.get("base", {}))
        if cid in normal_entry:
            entry_table = base.get("entry_attack")
            if not entry_table or tuple(entry_table["entries"][0][0]) != tuple(normal_entry[cid]):
                errors.append(f"{cid}: NORMAL_ENTRY {normal_entry[cid]} is not the entry_attack slot")

        states: dict = {}
        for code, st in hand.get("states", {}).items():
            rule = next((r for owner, r in forms.items() if r["code"] == code), None)
            start = tuple(st["start"])
            if start not in actions or actions[start]["character_id"] != cid:
                errors.append(f"{cid}: state {code} start {start} is not an action of this character")
                continue
            if rule is not None:
                if tuple(rule["start"][:2]) != start:
                    errors.append(f"{cid}: state {code} start {start} != FORMS start {rule['start'][:2]}")
                offset, duration, source = float(rule["start"][2]), float(rule["duration_s"]), str(rule["duration_source"])
                name_zh = str(rule["name_zh"])
                ends, pauses = bool(rule["ends_on_swap"]), bool(rule["pauses_off_field"])
                window = rule.get("exit_window_s") or rule.get("window_s")
            else:
                offset = actions[start]["length_s"] if st.get("start_at_end") else 0.0
                duration, source = None, "none"
                if code in STATE_CURVES:
                    curve_id, value = STATE_CURVES[code]
                    if curves.get(curve_id, [None])[0] != value:
                        errors.append(f"{cid}: state {code} curve {curve_id} is {curves.get(curve_id)}, expected {value}")
                    duration, source = value, f"curve {curve_id}"
                name_zh = actions[start]["name_zh"]       # no game name for the state: the ability that starts it
                ends, pauses, window = False, False, None
            exits = tuple(tuple(k) for k in st.get("exit", ()))
            for k in exits:
                if k not in actions:
                    errors.append(f"{cid}: state {code} exit {k} is not an action")
            states[code] = {
                "name_zh": name_zh, "start": start, "start_offset_s": round(offset, 3), "duration_s": duration,
                "duration_source": source, "ends_on_swap": ends, "pauses_off_field": pauses, "exit": exits,
                "window_s": None if window is None else (float(window[0]), float(window[1])),
                "slots": {slot: table_of(cid, slot, spec, False)
                          for slot, spec in sorted(st["slots"].items(), key=lambda kv: SLOT_ORDER.index(kv[0]))}}
            stats["states"] += 1
        for slot in list(base) + [s for st in hand.get("states", {}).values() for s in st["slots"]]:
            if slot not in SLOT_ORDER:
                errors.append(f"{cid}: unknown slot {slot!r}")
        basic_after = {}
        for key, hit in hand.get("basic_after", {}).items():
            if tuple(key) not in actions or "basic" not in base or not (1 <= hit <= len(base["basic"]["entries"])):
                errors.append(f"{cid}: basic_after {key} -> {hit} is not valid")
            basic_after[tuple(key)] = int(hit)
        palette[cid] = {
            "name_zh": str(c["name_zh"]), "element": str(c["element"]),
            "base": {slot: table_of(cid, slot, base[slot], True) for slot in SLOT_ORDER if slot in base},
            "states": states, "basic_after": basic_after}

        # reverse lookup: first slot entry of every key (base before states)
        tables = [("", palette[cid]["base"])] + [(code, st["slots"]) for code, st in states.items()]
        for state_code, table in tables:
            for slot, spec in table.items():
                for i, entry in enumerate(spec["entries"], 1):
                    if entry and entry[0] == "@time":
                        continue
                    for key in entry:
                        action_index.setdefault(tuple(key), (state_code, slot, i))

        # display names (the first of a language is what the formatter writes)
        zh_name = str(c["name_zh"])
        per_lang: dict = {}
        for lang in LANGS:
            shown = translate(zh_name, lang) or (str(c.get("name_ko") or "") if lang == "ko" else "")
            if not shown:
                errors.append(f"{cid}: no {lang} display name for {zh_name}")
                continue
            bare = "".join(ch for ch in shown if ch not in QUOTES).strip()
            ordered = (shown, bare) if lang == "zh" else (bare, shown)
            per_lang[lang] = tuple(dict.fromkeys(n for n in ordered if n))
        names[cid] = per_lang

        # named-action aliases (input sugar): ability / form-action names in four languages
        aliases: dict = {}
        owner: dict = {}
        for state_code, table in tables:
            for slot, spec in table.items():
                for i, entry in enumerate(spec["entries"], 1):
                    if entry and entry[0] == "@time":
                        labels = [entry[2]] if not str(entry[2]).startswith("Melee") else []
                    else:
                        labels = [actions[tuple(key)]["name_zh"] for key in entry[:1]]
                    for zh in labels:
                        if not zh:
                            continue
                        for lang in LANGS:
                            text = norm(translate(zh, lang))
                            if not text or len(text) < 2:
                                continue
                            target = (slot, i, state_code)
                            if text in generic:
                                dropped_aliases.append(f"{cid} {text!r}: equals a generic alias")
                                continue
                            if text in aliases:
                                if owner[text] != zh and aliases[text] != target:
                                    dropped_aliases.append(f"{cid} {text!r}: {aliases[text]} kept, {target} dropped")
                                continue
                            aliases[text] = target
                            owner[text] = zh
        named[cid] = aliases

    # ── cross checks ──
    for cid, keys in approved_keys.items():
        for key in sorted(keys):
            if key not in actions:
                errors.append(f"{cid}: approved key {key} is not in ACTIONS")
    seen_names: dict = {}
    for cid, per_lang in names.items():
        if set(per_lang) != set(LANGS):
            errors.append(f"{cid}: display names missing for {sorted(set(LANGS) - set(per_lang))}")
        for lang, shown in per_lang.items():
            for name in shown:
                n = norm(name)
                if n in generic:
                    errors.append(f"{cid}: name {name!r} equals a generic action alias")
                other = seen_names.setdefault(n, cid)
                if other != cid:
                    errors.append(f"{cid}: name {name!r} is also a name of {other}")
    resources: dict = {}
    for cid, fields in RESOURCE_CURVES.items():
        row = {}
        for field, curve_id in fields.items():
            value = RESOURCE_VALUES[cid][field]
            points = curves.get(curve_id)
            if not points or any(abs(p - value) > 1e-9 for p in points):
                errors.append(f"RESOURCES {cid}.{field}: curve {curve_id} is {points}, expected {value}")
            row[field] = (float(value), f"data:{curve_id}")
        resources[cid] = row
    for cid in list(RESOURCE_HINTS) + list(OWN_RESOURCE):
        if cid not in palette:
            errors.append(f"resource table: {cid} is not a template character")

    sources = {"action_catalog": hashlib.sha256(raw_cat).hexdigest(), "team_form_actions": form_sha,
               "team_rotation_data": rot_sha, "skill_damage": damage_sha}
    raw_only = sorted(k for keys in approved_keys.values() for k in keys if k not in action_index)
    info += [
        f"characters {len(palette)} | actions {len(actions)} (form {sum(1 for a in actions.values() if a['form'])})",
        f"slot entries {stats['entries']} (time-only {stats['time_only']}) | states {stats['states']}",
        f"approved keys reachable only as raw actions: {raw_only}",
        f"named aliases {sum(len(v) for v in named.values())} | dropped {len(dropped_aliases)}",
        *(f"  dropped alias {line}" for line in dropped_aliases),
        f"resources from data: {resources}",
    ]
    if errors:
        return "", errors, info
    text = render(sources, actions, palette, action_index, names, named, resources)
    compile(text, "team_custom_actions.py", "exec")
    ns: dict = {}
    exec(text, ns)  # noqa: S102 - round-trip check of our own generated data
    if ns["ACTIONS"] != actions or ns["PALETTE"] != palette or ns["ACTION_INDEX"] != action_index \
            or ns["NAMES"] != names or ns["NAMED"] != named or ns["RESOURCES"] != resources:
        errors.append("round-trip of the generated module does not reproduce the data")
    return text, errors, info


def render(sources, actions, palette, action_index, names, named, resources) -> str:
    out = [
        "# 队伍模拟「直接输入」模式的动作表（由 tools/gen_team_custom_actions.py 生成，勿手改）",
        "# GENERATED FILE - DO NOT EDIT.  Regenerate with scratchpad/v230/tools/gen_team_custom_actions.py",
        *(f"# input {name} sha256 {sha}" for name, sha in sources.items()),
        '"""Action palette of the team simulator\'s custom-cycle mode (generated, do not edit).',
        "",
        "ACTIONS[(ability_id, selector)] = {character_id, name_zh, length_s, length_source (trigger_end | last_hit |",
        "approved_est | duration | form), est_s (approved estimate handed to _step_length_us), hits, gauge (cycle",
        "gauge per use), energy (ultimate energy per use), gauge_set, time_stop_s, form}: every placeable action.",
        "PALETTE[cid] = {name_zh, element, base: {slot: table}, states: {code: {..., slots: {slot: table}}},",
        "basic_after: {action key: basic hit}}; table = {mode: chain | variants, loop_from, cd: E | Q | None,",
        'entries}; an entry is a tuple of action keys (one press runs them in order) or ("@time", seconds,',
        "label_zh, source) for a hit without animation data.",
        "ACTION_INDEX[key] = (state code or \"\", slot, 1-based position) of the key's first slot entry.",
        "NAMES[cid][lang] = display names (the first one is what the formatter writes).",
        "NAMED[cid][normalised alias] = (slot, position, state code): ability / form names as input sugar.",
        "RESOURCES[cid][field] = (value, source): E / Q cooldown and Q cost found in the static DB;",
        "RESOURCE_HINTS = community values (tooltip only); OWN_RESOURCE = members whose ultimate uses its own resource.",
        '"""',
        "",
        f"SCHEMA_VERSION = {SCHEMA_VERSION}",
        "SOURCE_SHA256 = {",
        *(f"    {name!r}: {sha!r}," for name, sha in sources.items()),
        "}",
        f"DODGE_S = {DODGE_S!r}",
        "",
        "ACTIONS = {",
    ]
    for key, action in actions.items():
        out.append(f"    {key!r}: {action!r},")
    out += ["}", "", "PALETTE = {"]

    def table_lines(table: dict, pad: str) -> list[str]:
        lines = []
        for slot, spec in table.items():
            lines.append(f"{pad}{slot!r}: {{'mode': {spec['mode']!r}, 'loop_from': {spec['loop_from']!r}, "
                         f"'cd': {spec['cd']!r}, 'entries': (")
            for entry in spec["entries"]:
                lines.append(f"{pad}    {entry!r},")
            lines.append(f"{pad})}},")
        return lines

    for cid, p in palette.items():
        out.append(f"    {cid}: {{")
        out.append(f"        'name_zh': {p['name_zh']!r}, 'element': {p['element']!r},")
        out.append("        'base': {")
        out += table_lines(p["base"], "            ")
        out.append("        },")
        out.append("        'states': {")
        for code, st in p["states"].items():
            out.append(f"            {code!r}: {{")
            for field in ("name_zh", "start", "start_offset_s", "duration_s", "duration_source", "ends_on_swap",
                          "pauses_off_field", "exit", "window_s"):
                out.append(f"                {field!r}: {st[field]!r},")
            out.append("                'slots': {")
            out += table_lines(st["slots"], "                    ")
            out.append("                },")
            out.append("            },")
        out.append("        },")
        out.append(f"        'basic_after': {p['basic_after']!r},")
        out.append("    },")
    out += ["}", "", "ACTION_INDEX = {"]
    for key, where in action_index.items():
        out.append(f"    {key!r}: {where!r},")
    out += ["}", "", "NAMES = {"]
    for cid, per_lang in names.items():
        out.append(f"    {cid}: {per_lang!r},")
    out += ["}", "", "NAMED = {"]
    for cid, aliases in named.items():
        out.append(f"    {cid}: {{")
        for alias, where in aliases.items():
            out.append(f"        {alias!r}: {where!r},")
        out.append("    },")
    out += ["}", "",
            "# E / Q cooldown (s) and Q energy cost found in the static DB: (value, source)",
            f"RESOURCES = {resources!r}",
            "# community values: shown as a tooltip on empty fields, never used in a calculation",
            f"RESOURCE_HINTS = {RESOURCE_HINTS!r}",
            "# members whose ultimate uses its own resource (no ultimate-energy check)",
            f"OWN_RESOURCE = {OWN_RESOURCE!r}", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="do not write; fail if the output is stale")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
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
    args.out.write_bytes(data)                     # LF line endings, like the other generated modules
    print(f"wrote {args.out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
