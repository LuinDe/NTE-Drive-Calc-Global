"""Generate src/services/team_resource_data.py (team simulator resources) from the four reviewed data chunks.

usage (Python 3.11, PYTHONUTF8=1):
    gen_team_resource_data.py <dev src dir> [--check] [--out <file>] [--static <game_static.sqlite3>]

Inputs (read-only):
    teamsim_energy/data/chunk_0.json .. chunk_3.json   reviewed per-character data (four schemas, normalised here)
    <src>/services/team_rotation_data.py               approved rotations (STEP_CLASS snapshot, time-only credits)
    <src>/services/team_form_actions.py                form rules (form-start abilities)
    <src>/services/team_custom_actions.py              shipped custom-mode RESOURCES (consistency check)
    static DB (optional, mode=ro&immutable=1)           re-validates every "data:<curve>" number the module carries

Rules (design_final.md §3, data reviews of chunks 0-3):
    * every value is a cell (value | None, source, confidence); unknown stays None
    * confidence vocabulary CONFIDENCES; ENFORCED lists what each resource level enforces
    * Lacrimosa's E 15 / Q 30 / cost 45 come from DT_GlobalValueLacrimosaData, a legacy table no blueprint references
      (chunk 0 review R3): they are kept with confidence "db_legacy" (never enforced unless the policy allows contested
      values); the prydwen E 15 / Q 30 stay as community_low cells
    * community costs (100 / 120) are display only; GameWith-only / mysqil-only cooldowns are community_very_low
      (tooltip only); a measured bound never becomes a value
    * STEP_CLASS is computed with the same ordered rules as team_resources.classify_step (test_team_resources pins
      both); TIME_ONLY_CREDIT credits gauge only, where the research record names the action
Deterministic: two runs give the same bytes; --check compares with the file on disk and exits 1 on a difference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import pprint
import re
import sqlite3
import sys

assert sys.version_info[:2] == (3, 11), "run with Python 3.11"

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
DATA = E / "data"
GENERATOR = "teamsim_energy/tools/gen_team_resource_data.py"
DATASET_ID = "cn_retail_20260924_9030b45b"
CONFIDENCES = ("db_value", "db_text", "db_struct_none", "measured_value", "db_legacy", "inference",
               "community_low", "community_very_low", "measured_bound", "unknown", "user")
ENFORCED = {
    "legacy": (),
    "data": ("db_value", "db_text", "db_struct_none", "measured_value"),
    "community": ("db_value", "db_text", "db_struct_none", "measured_value", "community_low"),
}
# a Q cost is enforced only from game data or a converged measurement (community 100 / 120 never)
COST_ENFORCED = ("db_value", "db_text", "measured_value")
CONTESTED = ("db_legacy",)
LEGACY_TABLE = "DT_GlobalValueLacrimosaData"
TEMPLATES = (1003, 1004, 1008, 1010, 1019, 1020, 1021, 1023, 1025, 1033, 1036, 1039, 1042, 1051, 1052, 1054,
             1055, 1057, 1070, 1071, 1072, 1073, 1075, 1076)


class GenError(RuntimeError):
    pass


def die(msg: str) -> None:
    raise GenError(msg)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cell(value, source, confidence):
    if confidence not in CONFIDENCES:
        die(f"unknown confidence {confidence!r} ({source})")
    if value is not None and not isinstance(value, (int, float)):
        die(f"non-numeric cell value {value!r} ({source})")
    v = None if value is None else round(float(value), 6)
    if v is None and confidence not in ("unknown", "measured_bound", "inference", "db_text", "community_very_low"):
        die(f"a {confidence} cell needs a value ({source})")
    return (v, str(source), str(confidence))


def short(text, n: int = 240) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def num(value):
    if isinstance(value, (int, float)):
        return float(value)
    return None


# ── per-chunk normalisers ────────────────────────────────────────────────────
# Each returns {cid: {"name_zh", "name_ko", "element", "fields": {name: {value, confidence, source, extra}},
#                     "alts": {"E": [(v, label)], "Q": [...], "cost": [...]}, "bounds": {kind: (wall, active, n)},
#                     "loop": (energy, gauge), "offsets": {kind: s}, "raw": <character dict>}}

_DATE = re.compile(r"(20\d\d-\d\d-\d\d)")


def _site_label(site, date) -> str:
    m = _DATE.search(str(date or ""))
    return f"{site} {m.group(1)}" if m else str(site)


def norm_chunk0(doc) -> dict:
    out = {}
    for c in doc["characters"]:
        cid = int(c["id"])
        ue, cds = c["ultimate_energy"], c["cooldowns"]
        fields = {}
        for f in c["plan_fields"]:
            fields[f["field"]] = {"value": f.get("value"), "confidence": f.get("confidence"),
                                  "source": f.get("note") or f.get("result_status") or "", "extra": f}
        qc = ue.get("q_cost") or {}
        fields["q_cost"]["source"] = qc.get("source") or fields["q_cost"]["source"]
        fields["q_cost"]["legacy"] = LEGACY_TABLE in str(qc.get("source") or "")
        for kind, key in (("E", "e_cd"), ("Q", "q_cd")):
            src = cds.get(kind) or {}
            fields[key]["source"] = src.get("source") or fields[key]["source"]
            page_date = src.get("snapshot_updatedAt")
            if page_date and str(page_date) not in fields[key]["source"]:      # the page's own date (review R1)
                fields[key]["source"] = f"{fields[key]['source']} [page {page_date}]"
            fields[key]["legacy"] = LEGACY_TABLE in str(src.get("source") or "")
            fields[key]["community"] = src.get("community") or []
        for kind, key in (("QTE", "support_cd"), ("counter", "counter_cd")):
            fields[key]["source"] = (cds.get(kind) or {}).get("source") or fields[key]["source"]
        alts = {"E": [], "Q": [], "cost": []}
        for kind in ("E", "Q"):
            for alt in (cds.get(kind) or {}).get("community") or []:
                site = str(alt.get("source", "")).split(":")[0]
                date = alt.get("snapshot_updatedAt") or alt.get("snapshot_dateModified") or alt.get("fetched") or ""
                alts[kind].append((num(alt.get("value")), _site_label(site, date), alt.get("confidence")))
        for alt in qc.get("community_display") or []:
            site = str(alt.get("source", "")).split(":")[0]
            alts["cost"].append((num(alt.get("value")), _site_label(site, alt.get("date")),
                                 "community_very_low"))
        bounds = {}
        meas = c.get("measured") or {}
        for kind, key in (("E", "e"), ("Q", "q"), ("QTE", "support_skill")):
            b = meas.get(key)
            if isinstance(b, dict) and b.get("le_wall_s") is not None:
                bounds[kind] = (float(b["le_wall_s"]), float(b["le_active_s"]), int(b.get("n_intervals") or 0))
        # intervals that do not contain the member's own Q press (a Q-driven reset cannot shorten them)
        clean = {}
        for kind in ("E", "Q"):
            mc = (cds.get(kind) or {}).get("measured_clean")
            if isinstance(mc, dict) and mc.get("clean_min_active_s") is not None:
                clean[kind] = {"wall_s": float(mc["clean_min_wall_s"]), "active_s": float(mc["clean_min_active_s"]),
                               "n": int(mc.get("n_clean") or 0),
                               "spanning_own_q": len(mc.get("spanning_own_Q") or ())}
        mb = qc.get("measured_bound") or {}
        loop = c["approved_rotation_per_loop"]["palette"]
        out[cid] = {"name_zh": c["name_zh"], "name_ko": c["name_ko"], "element": c["element"], "fields": fields,
                    "alts": alts, "bounds": bounds, "cost_bound": num(mb.get("cost_le_if_own_hits_only")),
                    "loop": (float(loop["energy"]), float(loop["gauge"])), "offsets": {}, "raw": c, "chunk": 0,
                    "clean": clean}
    return out


def norm_chunk1(doc) -> dict:
    out = {}
    for key, c in doc["characters"].items():
        cid = int(key)
        fields = {f["field"]: {"value": f.get("value"), "confidence": f.get("confidence"),
                               "source": f.get("source") or "", "extra": f} for f in c["fields"]}
        alts = {"E": [], "Q": [], "cost": []}
        for row in c.get("community") or []:
            site, label, value = row.get("site"), str(row.get("label") or ""), row.get("value")
            date = row.get("date")
            skill = str(row.get("skill") or "")
            kind = None
            if label in ("E cooldown s",) or (site == "prydwen" and skill == "Skill" and label == "CD"):
                kind = "E"
            elif label in ("Q cooldown s",) or (site == "prydwen" and skill == "Ultimate" and label == "CD"):
                kind = "Q"
            elif label.startswith("Q energy cost") or label == "Costs Ultimate Energy":
                kind = "cost"
            if kind is None:
                continue
            v = num(value) if not isinstance(value, str) else num(float(re.sub(r"[^0-9.]", "", value) or "nan"))
            if v is None or v != v:
                continue
            conf = "community_low" if site == "prydwen" and kind != "cost" else "community_very_low"
            alts[kind].append((v, _site_label(site, date), conf))
        bounds = {}
        for kind, name in (("E", "e_cd"), ("Q", "q_cd")):
            b = (fields.get(name) or {}).get("extra", {}).get("measured_bound")
            if isinstance(b, dict) and b.get("le_wall_s") is not None:
                bounds[kind] = (float(b["le_wall_s"]), float(b["le_active_s"]), int(b.get("n") or 0))
        mb = (fields.get("q_cost") or {}).get("extra", {}).get("measured_bound") or {}
        offsets = {}
        for kind, name in (("E", "e_cd"),):
            off = (fields.get(name) or {}).get("extra", {}).get("trigger_offset_s")
            if isinstance(off, dict) and off.get("value") is not None:
                offsets[kind] = float(off["value"])
        loop = c["energy_gauge"]["approved_loop"]
        out[cid] = {"name_zh": c["name_zh"], "name_ko": c["name_ko"], "element": c["element"], "fields": fields,
                    "alts": alts, "bounds": bounds, "cost_bound": num(mb.get("cost_le_if_own_hits_only")),
                    "loop": (float(loop["energy"]), float(loop["gauge"])), "offsets": offsets, "raw": c, "chunk": 1}
    return out


def norm_chunk2(doc) -> dict:
    out = {}
    for c in doc["characters"]:
        cid = int(c["id"])
        cds = c["cooldowns"]
        fields = {f["field"]: {"value": f.get("value"), "confidence": f.get("confidence"),
                               "source": f.get("note") or "", "extra": f} for f in c["field_status"]}
        for kind, name in (("E", "e_cd"), ("Q", "q_cd"), ("QTE", "support_cd"), ("counter", "counter_cd")):
            src = cds.get(kind) or {}
            if src.get("source"):
                fields[name]["source"] = src["source"]
        q = c.get("q_cost") or {}
        db = q.get("db")
        fields["q_cost"]["source"] = "; ".join(db) if isinstance(db, list) else (db or fields["q_cost"]["source"])
        alts = {"E": [], "Q": [], "cost": []}
        sources = c.get("sources") or {}
        for kind in ("E", "Q"):
            text = str((cds.get(kind) or {}).get("source") or "")
            m = re.search(r"gamewith_jp:(\d+)", text)
            if m and (cds.get(kind) or {}).get("value") is not None:
                gw = sources.get("gamewith_jp") or {}
                alts[kind].append((num((cds.get(kind) or {}).get("value")),
                                   _site_label("gamewith_jp", gw.get("dateModified")),
                                   "community_very_low"))
        disp = q.get("community_display") or {}
        if disp.get("value") is not None:
            alts["cost"].append((num(disp["value"]), "/".join(disp.get("sites") or ()), "community_very_low"))
        offsets = {}
        for kind in ("E", "Q"):
            off = (cds.get(kind) or {}).get("cooldown_starts_at_s")
            if off is not None:
                offsets[kind] = float(off)
        ar = c["approved_rotation"]
        loop = ar.get("per_loop_catalog") or ar.get("per_loop_db_corrected")
        out[cid] = {"name_zh": c["name_zh"], "name_ko": c["name_ko"], "element": c["element"], "fields": fields,
                    "alts": alts, "bounds": {}, "cost_bound": None,
                    "loop": (float(loop["energy"]), float(loop["gauge"])), "offsets": offsets, "raw": c, "chunk": 2}
    return out


def norm_chunk3(doc) -> dict:
    out = {}
    for c in doc["characters"]:
        cid = int(c["id"])
        fields = {f["field"]: {"value": f.get("value"), "confidence": f.get("confidence"),
                               "source": f.get("source") or "", "extra": f} for f in c["field_results"]}
        for name, spec in (c["fields"].get("specific") or {}).items():
            if name not in fields and isinstance(spec, dict):
                fields[name] = {"value": spec.get("value"), "confidence": spec.get("confidence"),
                                "source": spec.get("source") or "", "extra": spec}
        alts = {"E": [], "Q": [], "cost": []}
        cand = (c.get("community") or {}).get("candidates") or {}
        for kind, name in (("E", "e_cd"), ("Q", "q_cd"), ("cost", "q_cost")):
            for row in cand.get(name) or []:
                site = row.get("site")
                conf = "community_low" if site == "prydwen" and kind != "cost" else "community_very_low"
                alts[kind].append((num(row.get("value")), _site_label(site, row.get("date")), conf))
        offsets = {}
        for key, value in (c.get("cooldown_start_offsets_s") or {}).items():
            if key.split("/")[0].endswith("_Skill") and "E" not in offsets:
                offsets["E"] = float(value)
        ar = c["approved_rotation"]
        loop = ar["palette_sum"]
        out[cid] = {"name_zh": c["name_zh"], "name_ko": c["name_ko"], "element": c["element"], "fields": fields,
                    "alts": alts, "bounds": {}, "cost_bound": None,
                    "loop": (float(loop["energy"]), float(loop["gauge"])), "offsets": offsets, "raw": c, "chunk": 3}
    return out


# ── assembling one record ────────────────────────────────────────────────────

def field_cell(n: dict, name: str, *, legacy_ok: bool = True):
    f = n["fields"].get(name)
    if f is None:
        return None
    value, conf, src = f.get("value"), f.get("confidence"), short(f.get("source"))
    if conf in ("mixed", None):
        conf = "unknown"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        value = None
    if f.get("legacy") and legacy_ok:
        conf = "db_legacy"
        src = f"{src} [legacy table {LEGACY_TABLE}: no blueprint references it; contested by the chunk-0 review R3]"
    if value is None and conf not in ("unknown", "inference", "db_text", "community_very_low", "measured_bound"):
        conf = "unknown"
    return cell(value, src, conf)


def community_low_cell(n: dict, kind: str):
    """The prydwen value of this skill (community_low) when the best cell is something else."""
    for value, label, conf in n["alts"].get(kind) or ():
        if conf == "community_low" and value is not None and label.startswith("prydwen"):
            return cell(value, f"prydwen ({label})", "community_low")
    return None


def build_record(cid: int, n: dict, rot, forms) -> dict:
    raw = n["raw"]
    rec: dict = {"name_zh": n["name_zh"], "name_ko": n["name_ko"], "element": n["element"], "chunk": n["chunk"]}

    # ── cooldowns ──
    cd: dict = {}
    for kind, name in (("E", "e_cd"), ("Q", "q_cd")):
        best = field_cell(n, name)
        cells = [best] if best is not None else []
        if best is not None and best[2] in ("db_legacy",):
            alt = community_low_cell(n, kind)
            if alt is not None:
                cells.append(alt)
        cd[kind] = tuple(c for c in cells if c is not None) or (cell(None, "no source", "unknown"),)
    cd["QTE"] = (field_cell(n, "support_cd"),)
    counter = field_cell(n, "counter_cd")
    if counter is not None and counter[0] == 0.9:          # the chunks list the shared evade timer under counter
        counter = cell(0.0, "struct: no cooldown reference on the perfect-evade ability (shares the evade timer)",
                       "db_struct_none")
    cd["counter"] = (counter,)
    cd["evade"] = (cell(0.9, "data:GE_CoolDown_Evade (TriggerCoolDown on every GA_*_Evade)", "db_value"),)
    for name, f in sorted(n["fields"].items()):
        if name.startswith("form_cd:"):
            code = name.split(":", 1)[1]
            extra = f.get("extra") or {}
            unit = str(extra.get("unit") or "")
            if "duration" in unit or "window" in unit:
                # the chunk value is a state duration / follow-up window, not a cooldown
                own = extra.get("cooldown") or extra.get("own_cooldown") or extra.get("rage_E") or {}
                if own.get("confidence") == "db_struct_none":
                    c = cell(0.0, short(own.get("source")), "db_struct_none")
                else:
                    c = cell(None, f"no cooldown value ({short(f.get('source'))} is a {unit})", "unknown")
            else:
                c = field_cell(n, name)
                if c[2] == "db_struct_none" and c[0] is None:
                    c = cell(0.0, c[1], "db_struct_none")
            cd["form:" + code] = (c,)
    rec["cd"] = cd
    rec["cd_offset_s"] = dict(sorted(n["offsets"].items()))
    rec["cd_bound"] = {k: v for k, v in sorted(n["bounds"].items())}
    rec["cd_conflict"] = measured_veto(cid, cd, rec["cd_bound"], n.get("clean") or {})
    alts = {}
    for kind in ("E", "Q"):
        rows = []
        for value, label, conf in n["alts"].get(kind) or ():
            if value is None:
                continue
            rows.append((round(float(value), 3), label, conf))
        alts[kind] = tuple(sorted(set(rows), key=lambda r: (r[1], r[0])))
    rec["cd_alt"] = alts

    # ── energy ──
    cost = field_cell(n, "q_cost")
    kind = "ultimate"
    if cid == 1052:
        kind = "own_clock"
    elif cid == 1076:
        kind = "own_meter"
    display = []
    for value, label, _conf in n["alts"].get("cost") or ():
        if value is not None:
            display.append((round(float(value), 3), label))
    energy = {"kind": kind, "cost": cost, "cost_display": tuple(sorted(set(display), key=lambda r: (r[1], r[0]))),
              "cost_bound": n.get("cost_bound"), "start": cell(None, "start = cost (design D20; all recorded first "
                                                                  "presses came early in the battle)", "inference"),
              "own_eff": None, "events": (), "clock": None, "meter": None}
    rec["energy"] = energy
    rec["gauge"] = {"loop": round(n["loop"][1], 3), "loop_energy": round(n["loop"][0], 3),
                    "fallback": False, "fallback_reason": ""}
    rec["e_charges"] = None
    rec["rules"] = ()
    rec["free_ultimates"] = ()
    rec["ability_kinds"] = {}
    rec["unmodelled"] = ()
    rec["open"] = ()
    return rec


def measured_veto(cid: int, cd: dict, bounds: dict, clean: dict | None = None) -> dict:
    """V6 (design §3.2 rule 4): a recorded interval between two uses is an upper bound of the cooldown.  A community
    value above the WALL bound is demoted to community_very_low (reason kept); a value above the ACTIVE bound only is
    kept and returned as a conflict (does the cooldown run during time stops? - G1); game data above the wall bound
    aborts (data error).  ``clean`` (chunk ``measured_clean``): the shortest intervals that do not contain the
    member's own Q press - a conflict carries them, so the runtime can drop it for a build whose Q resets the
    cooldown (Linko A3, ``q_resets_e``; validation F1)."""
    clean = clean or {}
    conflicts = {}
    for kind in ("E", "Q"):
        bound = bounds.get(kind)
        if not bound:
            continue
        wall, active = float(bound[0]), float(bound[1])
        cells = []
        for c in cd.get(kind, ()):
            if c is None or c[0] is None:
                cells.append(c)
                continue
            if c[0] > wall + 1e-9:
                if c[2] in ("db_value", "db_text", "measured_value"):
                    die(f"V6: {cid} {kind} {c[0]} ({c[2]}) is longer than the recorded interval {wall} s")
                if c[2] == "community_low":
                    c = cell(c[0], f"{c[1]} [measured veto: two uses {wall:g} s apart in the records]",
                             "community_very_low")
            elif c[0] > active + 1e-9 and c[2] in ("community_low", "db_value", "db_text", "db_legacy"):
                conflicts[kind] = {"value_s": c[0], "active_le_s": active, "wall_le_s": wall}
                cl = clean.get(kind)
                if cl:          # the bound once intervals spanning the member's own Q are left out
                    conflicts[kind].update({"active_le_s_no_own_q": cl["active_s"], "wall_le_s_no_own_q": cl["wall_s"],
                                            "n_no_own_q": cl["n"], "spanning_own_q": cl["spanning_own_q"]})
            cells.append(c)
        cd[kind] = tuple(cells)
    return conflicts


# ── overlays: character facts the runtime models (values read from the chunks, asserted) ─────────────────

def expect(value, wanted, what):
    if value is None or abs(float(value) - float(wanted)) > 1e-6:
        die(f"{what}: chunk value {value!r} != expected {wanted!r} (re-check the overlay)")
    return float(wanted)


def overlays(records: dict, norm: dict) -> None:
    # Lacrimosa: extra E after 5 basics (breakthrough 4, templates are 6), A6 support skill unmodelled
    n = norm[1004]
    rule = next(r for r in n["raw"]["cooldowns"]["rules"] if "ExtraERequireMeleeCount" in r["source"])
    count = expect(rule["value"], 5.0, "1004 extra E basics")
    records[1004]["rules"] = (("extra_e_after_basics", "E", count, None, rule["confidence"], short(rule["source"])),)
    records[1004]["unmodelled"] = ("lacrimosa_a6_support", "lacrimosa_e_steal_variant")
    records[1004]["energy"]["cost_note"] = "contested"
    # Linko: A3 Q start clears the E timer
    rule = next(r for r in norm[1072]["raw"]["cooldowns"]["rules"] if "Effect3" in r["source"])
    records[1072]["rules"] = (("q_resets_e", "E", None, 3, rule["confidence"], short(rule["source"])),)
    records[1072]["unmodelled"] = ("linko_a6_coattack_charge", "linko_a5_coattack_reaction")
    # Hotori: own clock (all numbers db_value)
    oc = norm[1052]["raw"]["ultimate_energy"]["own_clock"]
    clock = {"name_zh": oc["name_zh"],
             "cap": cell(expect(oc["cap"]["value"], 120.0, "1052 cap"), oc["cap"]["source"], "db_value"),
             "regen_per_s": cell(expect(oc["regen_per_s"]["value"], 6.0, "1052 regen"), oc["regen_per_s"]["source"],
                                 "db_value"),
             "e_cost": cell(expect(oc["E_cost"]["value"], 60.0, "1052 E cost"), short(oc["E_cost"]["source"]), "db_value"),
             "q_needs": cell(expect(oc["Q_needs"]["value"], 120.0, "1052 Q"), short(oc["Q_needs"]["source"]), "db_value"),
             "drain_per_s": cell(expect(oc["drain_in_time_stop_per_s"]["value"], 10.0, "1052 drain"),
                                 short(oc["drain_in_time_stop_per_s"]["source"]), "db_value"),
             "start": cell(120.0, short(oc["start"]["source"]), "inference"),
             "drain_reading": "from the Q start, no regeneration while the tachi state lasts, remainder kept "
                              "(stricter of the two data-consistent readings; chunk 0 open items)",
             "time_stop_community": cell(10.0, "prydwen / mysqil 时停时长 10 s (the simulator has no measured stop)",
                                         "community_low")}
    e = records[1052]["energy"]
    e["clock"] = clock
    e["cost"] = cell(120.0, "data:Jin_UltraSkillCost (Q needs a full clock)", "db_value")
    records[1052]["unmodelled"] = ("hotori_a3_refund", "hotori_a4_per_kill", "hotori_e_extra_drain")
    records[1052]["interlude_steps"] = (3,)
    # Shinku: own meter (tracked, not gated: gain unit unresolved)
    f = norm[1076]["fields"]["own:meter_unit"]["extra"]
    gains = f["gains"]
    meter = {"name_zh": "桀骜斗志",
             "cap": cell(60.0, "data:DT_ShinkuEffectFigure.ShinkuUltraEnergyMax", "db_value"),
             "cost": cell(60.0, "cost = cap (text: consumes all 桀骜斗志)", "inference"),
             "gain_melee": cell(expect(gains["basic"]["value"], 18.0, "1076 melee"), gains["basic"]["source"], "db_value"),
             "gain_skill": cell(expect(gains["E"]["value"], 5.0, "1076 E"), gains["E"]["source"], "db_value"),
             "gain_counter": cell(expect(gains["perfect evade"]["value"], 3.0, "1076 evade"),
                                  gains["perfect evade"]["source"], "db_value"),
             "gain_unit": cell(None, "per press / per hit / per combo not in the DB (protocol S)", "unknown"),
             "reading": "per press (display only)"}
    records[1076]["energy"]["meter"] = meter
    records[1076]["energy"]["cost"] = meter["cost"]
    records[1076]["free_ultimates"] = ("GA_Shinku_UltraSkill_Rage", "GA_Shinku_UltraSkill_Rage_Pre")
    # Zankou: Force Q free after a Magic Q (5 s window, db_value)
    f = norm[1036]["fields"]["form_cd:magic_force_Q"]
    expect(f["value"], 5.0, "1036 force window")
    records[1036]["free_ultimates"] = ("GA_Zankou_UltraSkillForce",)
    records[1036]["cd"]["form:magic_force_Q"] = (cell(0.0, "GA_Zankou_UltraSkillForce: no CooldownDuration "
                                                           "reference; follow-up window 5 s (ZankouGiveUltraForceTime)",
                                                      "db_struct_none"),)
    # Raven: witch finisher free; Akane: SonicBoom2 (Q stage 2) free;
    records[1042]["free_ultimates"] = ("GA_BlackBird_Evolve_UltraSkill",)
    records[1057]["free_ultimates"] = ("GA_Akane_UltraSkill_End",)
    # Chaos: short-press E 2.0 s (db_value; binding open -> custom palette only)
    f = norm[1071]["fields"]["cd:E_short_2s"]
    records[1071]["cd"]["E_short"] = (cell(expect(f["value"], 2.0, "1071 E short"), short(f["source"]), "db_value"),)
    # Cang: the SkillA redirect (seq 5) has its own 14 s timer (噤念 / 如此罪状), independent of 天地之心
    alt = norm[1023]["raw"]["cooldowns"]["E_alt"]
    records[1023]["cd"]["E_alt"] = (cell(expect(alt["value"], 14.0, "1023 E_alt"), short(alt["source"]),
                                         alt["confidence"]),)
    records[1023]["ability_kinds"] = {"GA_Cang_SkillA": "E_alt"}
    records[1023]["unmodelled"] = ("cang_a1_cd_cut",)
    # Chiichan: E stores 3 uses (charges), own charge efficiency +0.20
    st = norm[1073]["raw"]["cooldowns"]["E"]
    charges = st["charges"]
    records[1073]["e_charges"] = cell(expect(charges["value"], 3, "1073 charges"), short(charges["source"]),
                                      charges["confidence"])
    ev = next(e for e in norm[1073]["raw"]["energy_events"] if e["key"] == "passive2_charge_eff")
    records[1073]["energy"]["own_eff"] = cell(expect(ev["value"], 0.2, "1073 eff"), short(ev["source"]),
                                              ev["confidence"])
    # Haniel: A6 -4 s on E (base 20 replaces the shipped hint 16)
    rule = next(r for r in norm[1020]["raw"]["cooldowns"]["rules"] if "A6" in r["key"] or "6" in r["key"])
    records[1020]["rules"] = (("e_cd_add", "E", expect(rule["value"], -4.0, "1020 A6"), 6, rule["confidence"],
                               short(rule["source"])),)
    # Mint: A1 counter resets E (custom mode only), resonance 6 +2 gauge after E (display)
    rule = next(r for r in norm[1019]["raw"]["cooldowns"]["rules"] if "A1" in r["key"])
    records[1019]["rules"] = (("counter_resets_e", "E", None, 1, rule["confidence"], short(rule["source"])),)
    # Adler: gauge fallback (catalog gap: the E's spawned damage-trigger hit carries the 6.7 gauge)
    fb = norm[1033]["raw"].get("gauge_fallback") or {}
    records[1033]["gauge"]["fallback"] = True
    records[1033]["gauge"]["fallback_reason"] = short(fb.get("reason") or fb.get("cause") or fb.get("note") or
                                                     "approved loop places no gauge (catalog gap: the E's spawned hit "
                                                     "with 6.7 gauge is missing)")
    # Edgar E: base 16 (community_low) + extension per channel segment (approved press = 1 segment)
    records[1021]["unmodelled"] = ("edgar_e_channel_extension", "edgar_passive_charge_120")
    # energy events (after:E / after:Q are modelled; the rest are listed)
    ev = []
    f = norm[1051]["fields"]["event:A2_plus_8"]
    ev.append(("zero_a2", 1051, "after:E", expect(f["value"], 8.0, "1051 A2"), 2, f["confidence"], "modelled"))
    records[1051]["energy"]["events"] = (("after:E", expect(f["value"], 8.0, "1051 A2"), 2, f["confidence"],
                                          "data:Female051_LV2 (awakening 2)"),)
    adler = None
    for e in norm[1033]["raw"].get("energy_events") or []:
        if e.get("value") == 20.0 or "lv5" in str(e.get("key", "")).lower() or "a5" in str(e.get("key", "")).lower():
            adler = e
    if adler is None:
        die("1033 A5 +20 after Q not found in chunk 2")
    records[1033]["energy"]["events"] = (("after:Q", expect(adler["value"], 20.0, "1033 A5"), 5, adler["confidence"],
                                          short(adler.get("source") or "data:Adler_lv5")),)
    unmod = {
        1010: ("nanally_a1_follow_up_energy",),
        1025: ("hathor_speed_stack_energy",),
        1055: ("kuhara_bud_boom_energy",),
        1075: ("iloi_a6_energy",),
        1003: ("sagiri_a5_float_refill",),
        1054: ("daffodill_a2_refill",),
        1039: ("fadia_threshold_refill",),
        1073: ("chiichan_charge_passive",),
        1057: ("akane_release_pending",),
        1008: ("skia_shadow_exit_variant",),
        1070: (),
        1071: ("chaos_e_short_binding",),
        1042: ("raven_witch_q_row",),
        1036: ("zankou_a4_magic_q",),
    }
    for cid, items in unmod.items():
        records[cid]["unmodelled"] = tuple(dict.fromkeys(tuple(records[cid]["unmodelled"]) + tuple(items)))


# ── step classification (same ordered rules as team_resources.classify_step) ──────────────────────────

def classify_steps(records: dict, rot, forms) -> dict:
    form_start = {int(cid): rule["start"][0] for cid, rule in forms.FORMS.items() if rule.get("start")}
    out = {}
    for cid in sorted(rot.CHARACTERS):
        steps = rot.CHARACTERS[cid]["variants"]["approved"]["steps"]
        rec = records[cid]
        free = set(rec["free_ultimates"])
        kinds = rec["ability_kinds"]
        prev = None
        last_paid_q = None
        for s in steps:
            slot, ab, sel = s.get("slot"), s.get("ability_id"), s.get("selector") or ""
            role = s.get("form_role")
            req = None
            if not s.get("sim"):
                k, cost, reason = None, None, "own_clock_wait" if s["seq"] in rec.get("interlude_steps", ()) \
                    else "time_only"
            elif ab in free:
                k, cost, reason, req = None, None, "free_ultimate", last_paid_q
            elif ab in kinds:
                k, cost, reason = kinds[ab], None, "ability_kind"
            elif slot == "ultimate":
                k, cost, reason = "Q", "q_cost", "ultimate"
            elif s.get("combo") and slot in ("skill", "basic"):
                k, cost, reason = None, None, f"form_{role}"
            elif role == "exit" and ab == form_start.get(cid):
                k, cost, reason = None, None, "form_exit"
            elif (slot == "skill" and prev is not None and prev.get("ability_id") == ab
                  and (prev.get("selector") or "") != sel and sel.endswith("End")):
                k, cost, reason = None, None, "continuation"
            elif slot == "skill":
                k, cost, reason = "E", ("e_cost" if rec["energy"]["kind"] == "own_clock" else None), "skill"
            elif slot == "qte":
                k, cost, reason = ("QTE", None, "entry") if s.get("entry_only") else (None, None, "qte_in_visit")
            elif ab and ab.endswith("_PerfectEvade"):
                k, cost, reason = "counter", None, "perfect_evade"
            elif slot == "other":
                k, cost, reason = None, None, ("other_skill_unclassified" if ab and "_Skill" in ab else "other")
            else:
                k, cost, reason = None, None, slot or "none"
            if cost is None and k == "Q":
                cost = "q_cost"
            out[(cid, int(s["seq"]))] = (k, cost, reason, req)
            if s.get("sim"):
                prev = s
            if k == "Q":
                last_paid_q = int(s["seq"])
    return out


def time_only_credits(norm: dict, rot) -> dict:
    """Gauge credit of approved time-only steps whose research record names the action (design §3.6, J6)."""
    out = {}
    # Skia #12 = basic 4 (DB rows of the 4th segment)
    skia = next(a for a in norm[1008]["raw"]["actions"] if a["key"] == "basic_chain")
    seg4 = skia["segments"][3]
    out[(1008, 12)] = cell(seg4["gauge"], "basic attack 4: " + "+".join(seg4["rows"]) + " (heterochrome_add)",
                           "inference")
    # Cang #2 / #13 = E 天地之心 (or the redirect, same 5.6), #9 = basic 3 inside the field
    cang = {a["key"]: a for a in norm[1023]["raw"]["actions"]}
    e_heart = cang["e_heart"]["gauge_per_use"]["value"]
    out[(1023, 2)] = cell(e_heart, "E 天地之心 per use (heterochrome_add)", "inference")
    out[(1023, 13)] = cell(e_heart, "E re-use (天地之心 / 如此罪状 both 5.6)", "inference")
    melee3 = next(h for h in cang["basic_chain"]["hits"] if h["ge"] == "GE_Player_Cang_Melee3_Damage")
    out[(1023, 9)] = cell(melee3["gauge_per_hit"] * melee3["count"], "basic attack 3: GE_Player_Cang_Melee3_Damage",
                          "inference")
    # Daffodill #4: phantom step x2 (value given for both repeats)
    f = norm[1054]["fields"]["counter_cd"]["extra"]
    ph = f.get("phantom_step") or {}
    tc = (ph.get("time_only_credit") or {}).get("value")
    if tc is None:
        die("1054 phantom step credit missing")
    out[(1054, 4)] = cell(round(float(tc) / 2.0, 6), "phantom step 承轨反击 per repeat (chunk 1, 2 x per-use gauge)",
                          "inference")
    # Mitsuki #4 = counter while riding (4 jellyfish bullets)
    f = norm[1070]["fields"]["time_only:counter_credit"]
    out[(1070, 4)] = cell(f["value"]["gauge"], "counter while riding: 4 x GE_Player_Mitsuki_PerfectAtkBullet_Damage",
                          "inference")
    for key in out:
        steps = {int(s["seq"]): s for s in rot.CHARACTERS[key[0]]["variants"]["approved"]["steps"]}
        if key[1] not in steps or steps[key[1]].get("sim"):
            die(f"time-only credit {key} is not a time-only approved step")
    return dict(sorted(out.items()))


def hit_credits(norm: dict, rot) -> dict:
    """Approved actions whose animation lays out no hit although the game hits with them (spawned summons / zone
    actors; validation F2, review F12): (cid, ability, selector) -> (raw charge_add per use | None, heterochrome_add
    per use | None, hits per use | None, source, confidence).  Only energy and gauge are credited - the damage of
    these hits stays outside the simulator (LIMIT_SUMMONS_DOT).  ``None`` values = the hit count per use is unknown:
    the action is only flagged."""
    out = {}
    # Iloi E: the sheep's hits (chunk 0 reconstruction = DB rows x the recorded composition, 2 casts x 10 hits)
    e = norm[1075]["raw"]["gain_per_action_type"]["E"]
    if e.get("ability_id") != "GA_Oneiroi_Skill":
        die(f"1075 E reconstruction names {e.get('ability_id')!r}")
    energy = expect(e["energy"]["value"], 14.798, "1075 E energy per use")
    gauge = expect(e["gauge"]["value"], 7.998, "1075 E gauge per use")
    cross = " / ".join(str(x.get("b") or "") for x in norm[1075]["raw"].get("cross_checks") or ()
                       if "14.798" in str(x.get("b") or ""))
    if not cross:
        die("1075 E: the record cross-check (per-cast DB sum 14.798) is missing")
    out[(1075, "GA_Oneiroi_Skill", "Skill")] = (
        energy, gauge, 10, short(f"{e['energy']['source']}; records: 10 hits per cast ({cross})"), "measured_value")
    # Akane E tap: GE_Player_Akane_Skill_Damage x1 (DB level hint count), palette lays no hit
    acts = {a["key"]: a for a in norm[1057]["raw"]["actions"]}
    tap = acts["E_tap"]
    seg = tap["segments"][0]
    if seg["rows"] != ["GE_Player_Akane_Skill_Damage"] or seg["counts"] != [1] or (tap.get("palette") or {}).get("hits"):
        die("1057 E_tap changed (rows / count / palette hits)")
    out[(1057, "GA_Akane_Skill", "Skill")] = (
        expect(tap["energy_per_use"], 1.7, "1057 E tap energy"), expect(tap["gauge_per_use"], 2.8, "1057 E tap gauge"),
        1, short(f"skill_damage GE_Player_Akane_Skill_Damage x1 ({seg['hit_count_source']})"), "db_value")
    # Hathor E hold (Power): one hit per charge stage, the number of stages per hold is unknown -> flagged only
    acts = {a["key"]: a for a in norm[1025]["raw"]["actions"]}
    tick = acts["E_hold_tick"]
    if "unknown" not in str(tick.get("label") or "") or (tick.get("palette") or {}).get("hits"):
        die("1025 E_hold_tick changed (count now known, or the palette lays hits)")
    out[(1025, "GA_Hathor_Skill", "Power")] = (
        None, None, None, short(f"GE_Player_Hathor_Skill1Power_Damage {tick['energy_per_use']:g} / "
                                f"{tick['gauge_per_use']:g} per charge stage; stages per hold unknown"), "unknown")
    for (cid, ability, selector) in out:
        steps = rot.CHARACTERS[cid]["variants"]["approved"]["steps"]
        if not any(s.get("sim") and s.get("ability_id") == ability and (s.get("selector") or "") == selector
                   for s in steps):
            die(f"hit credit {(cid, ability, selector)} is not a simulated approved step")
    return dict(sorted(out.items()))


# ── static DB re-validation of data: tags ────────────────────────────────────

DATA_TAG = re.compile(r"data:(?:(DT_\w+)\.)?([A-Za-z_][\w]*)")


def validate_db(records: dict, static: pathlib.Path | None) -> dict:
    report = {"checked": 0, "unresolved": [], "mismatch": []}
    if static is None or not static.exists():
        report["skipped"] = "no static DB given"
        return report
    con = sqlite3.connect(static.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        def curve(name):
            rows = con.execute("SELECT p.value FROM combat_curve_point p WHERE p.curve_id = ? ORDER BY p.ordinal",
                               (name,)).fetchall()
            return [r[0] for r in rows]

        def walk(obj, where):
            if isinstance(obj, tuple) and len(obj) == 3 and isinstance(obj[1], str) and obj[2] in CONFIDENCES:
                value, source, conf = obj
                if conf in ("db_value", "db_legacy") and value is not None:
                    for m in DATA_TAG.finditer(source):
                        name = m.group(2)
                        values = curve(name)
                        if not values:
                            report["unresolved"].append(f"{where}: {name}")
                            continue
                        report["checked"] += 1
                        if not any(abs(abs(float(v)) - abs(float(value))) < 1e-4 for v in values):
                            report["mismatch"].append(f"{where}: {name} {values[:3]} != {value}")
                        break
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    walk(v, f"{where}.{k}")
            elif isinstance(obj, (tuple, list)):
                for i, v in enumerate(obj):
                    walk(v, f"{where}[{i}]")

        for cid, rec in records.items():
            walk(rec, str(cid))
    finally:
        con.close()
    if report["mismatch"]:
        die("static DB disagrees: " + "; ".join(report["mismatch"]))
    report["unresolved"] = sorted(set(report["unresolved"]))
    return report


# ── checks ───────────────────────────────────────────────────────────────────

def validate(records: dict, step_class: dict, custom) -> dict:
    if tuple(sorted(records)) != TEMPLATES:
        die(f"V1: template set differs: {sorted(records)}")
    counts = {}
    for level in ("data", "community"):
        allowed = ENFORCED[level]
        counts[level] = {k: sum(1 for r in records.values()
                                if any(c[0] is not None and c[2] in allowed for c in r["cd"].get(k, ())))
                         for k in ("E", "Q")}
    for cid, rec in records.items():
        for kind, cells in rec["cd"].items():
            for c in cells:
                if c[2] == "community_low" and "prydwen" not in c[1] and kind not in ("E_alt",):
                    die(f"V3: {cid} {kind} community_low without prydwen: {c}")
                if c[2] == "community_very_low" and c is cells[0] and len(cells) == 1 and c[0] is not None:
                    pass   # tooltip-only cell kept as the best known value; never enforced
    # V4: the shipped custom-mode table keeps its numbers (the legacy level still uses it)
    for cid, row in custom.RESOURCES.items():
        rec = records[int(cid)]
        for key, (value, _src) in row.items():
            kind = {"e_cd_s": "E", "q_cd_s": "Q"}.get(key)
            got = [c[0] for c in rec["cd"].get(kind, ())] if kind else [rec["energy"]["cost"][0]]
            if float(value) not in [g for g in got if g is not None]:
                die(f"V4: custom RESOURCES {cid} {key}={value} not in the data {got}")
    if tuple(custom.OWN_RESOURCE) != (1052, 1076):
        die("V4: OWN_RESOURCE changed")
    kinds = {}
    for value in step_class.values():
        kinds[value[0]] = kinds.get(value[0], 0) + 1
    hints_changed = []
    for cid, row in custom.RESOURCE_HINTS.items():
        rec = records[int(cid)]
        for key, value in row.items():
            kind = {"e_cd_s": "E", "q_cd_s": "Q"}[key]
            best = next((c for c in rec["cd"][kind] if c[0] is not None), None)
            if best is None or abs(best[0] - float(value)) > 1e-9:
                hints_changed.append((int(cid), kind, float(value), None if best is None else best[0]))
    return {"enforced": counts, "step_kinds": {str(k): v for k, v in sorted(kinds.items(), key=lambda kv: str(kv[0]))},
            "hints_changed": hints_changed}


# ── rendering ────────────────────────────────────────────────────────────────

HEADER = '''# 队伍模拟：终结能量、环合值与冷却数据（由 teamsim_energy/tools/gen_team_resource_data.py 生成，勿手改）
# GENERATED FILE - DO NOT EDIT.  Regenerate with {generator}
{inputs}"""Team simulator resources per template character (generated, do not edit).

Every number is a cell ``(value | None, source, confidence)``; ``None`` = unknown (never guessed).  Confidence
vocabulary ``CONFIDENCES``; ``ENFORCED[level]`` lists what the resource level enforces (``team_resources``):
``legacy`` (the old rule: nothing), ``data`` (game data), ``community`` (game data + prydwen cooldowns).
``COST_ENFORCED``: confidences a Q cost needs to gate the ultimate (community 100 / 120 never do).  ``db_legacy``
cells (Lacrimosa's DT_GlobalValueLacrimosaData, contested by the data review) are used only when the policy allows
contested values.

RESOURCES[cid]: name_zh, name_ko, element, chunk (data chunk), energy {{kind (ultimate | own_clock | own_meter), cost,
cost_display ((value, site date), ...), cost_bound (measured upper bound, never a value), start, own_eff, events
((trigger, value, awakening, confidence, source), ...), clock (Hotori), meter (Shinku)}}, gauge {{loop, loop_energy,
fallback, fallback_reason}}, cd {{kind: (cell, ...) in priority order}} (kinds E, Q, QTE, counter, evade, E_alt,
E_short, form:<code>), cd_alt {{E / Q: ((value, site date, confidence), ...)}} (tooltip), cd_offset_s, cd_bound
{{kind: (wall s, active s, n)}} (measured bounds), cd_conflict {{kind: {{value_s, active_le_s, wall_le_s[,
active_le_s_no_own_q, wall_le_s_no_own_q, n_no_own_q, spanning_own_q]}}}} (a value longer than a recorded interval of
battle time without time stops: the cooldown-clock question; the *_no_own_q bound leaves out intervals that contain
the member's own Q, which a q_resets_e rule explains), e_charges, rules
((code, kind, value, awakening, confidence,
source), ...), free_ultimates, ability_kinds, unmodelled, open.
STEP_CLASS[(cid, seq)] = (cd kind | None, cost ref | None, reason, required seq | None) for every approved step.
TIME_ONLY_CREDIT[(cid, seq)] = gauge cell credited when that time-only step runs.
HIT_CREDIT[(cid, ability, selector)] = (charge_add per use | None, heterochrome_add per use | None, hits per use | None,
source, confidence): an approved action whose animation lays out no hit (spawned summon / zone hits); energy and gauge
are credited when it runs (the damage is not), None = hit count unknown (flagged only).
"""
'''


def render(records, step_class, credits, globals_, summary, inputs, hits=None) -> str:
    lines = [HEADER.format(generator=GENERATOR,
                           inputs="".join(f"# input {k} sha256 {v}\n" for k, v in inputs.items()))]
    pp = lambda obj: pprint.pformat(obj, width=118, sort_dicts=True)  # noqa: E731
    lines.append(f"SCHEMA_VERSION = 1\nGENERATOR = {GENERATOR!r}\nDATASET_ID = {DATASET_ID!r}\n")
    lines.append(f"SOURCE_SHA256 = {pp(inputs)}\n")
    lines.append(f"CONFIDENCES = {CONFIDENCES!r}\n")
    lines.append(f"ENFORCED = {pp(ENFORCED)}\n")
    lines.append(f"COST_ENFORCED = {COST_ENFORCED!r}\nCONTESTED = {CONTESTED!r}\n")
    lines.append(f"GLOBAL = {pp(globals_)}\n")
    lines.append(f"RESOURCES = {pp(records)}\n")
    lines.append(f"STEP_CLASS = {pp(step_class)}\n")
    lines.append(f"TIME_ONLY_CREDIT = {pp(credits)}\n")
    lines.append(f"HIT_CREDIT = {pp(hits or {})}\n")
    lines.append(f"SUMMARY = {pp(summary)}\n")
    return "\n".join(lines)


def global_values(doc0) -> dict:
    g = doc0["global_values"]
    rc = g["reaction_charge_盈蓄"]
    return {
        "gauge_cap": cell(100.0, "ReactionRules gauge_cap / texts", "db_text"),
        "qte_gauge_cost": cell(100.0, "the full gauge of the swap rule (HTAbilityHeterochromeCost amount not imported)",
                               "inference"),
        "evade_cd": cell(g["evade_cooldown"]["value"], g["evade_cooldown"]["source"], "db_value"),
        "reaction_charge": cell(rc["value"], rc["source"], "db_value"),
        "reaction_charge_icd_s": cell(rc["icd_s"], "data:Reaction_GuangLingXiang_ChargeCD", "db_value"),
        "perfect_evade_energy": cell(None, g["perfect_evade_energy"]["source"], "unknown"),
        "parry_energy": cell(None, g["parry_energy"]["source"], "unknown"),
        "charge_eff_rule": cell(None, "gain x (1 + charge efficiency): inherited engine assumption (G2)", "inference"),
        "energy_scale": cell(None, "whether skill_damage.charge_add is on the scale of the in-game 消耗终结能量 (100 / 120)"
                                   " is open until G0 (fresh capture with chargeCurrent / chargeMax)", "unknown"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=pathlib.Path)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--static", type=pathlib.Path)
    ap.add_argument("--data", type=pathlib.Path, help="chunk folder (default teamsim_energy/data; tests plant copies)")
    args = ap.parse_args(argv)
    src = args.src.resolve()
    out = args.out or (src / "services" / "team_resource_data.py")
    data_dir = args.data or DATA
    chunk_paths = [data_dir / f"chunk_{i}.json" for i in range(4)]
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in chunk_paths]
    norm = {}
    for fn, doc in zip((norm_chunk0, norm_chunk1, norm_chunk2, norm_chunk3), docs):
        part = fn(doc)
        dup = set(part) & set(norm)
        if dup:
            die(f"character in two chunks: {sorted(dup)}")
        norm.update(part)
    if tuple(sorted(norm)) != TEMPLATES:
        die(f"V1: the chunks cover {sorted(norm)}, not the 24 template characters")
    rot_path = src / "services" / "team_rotation_data.py"
    forms_path = src / "services" / "team_form_actions.py"
    custom_path = src / "services" / "team_custom_actions.py"
    rot = load_module("_g_trd", rot_path)
    forms = load_module("_g_tfa", forms_path)
    custom = load_module("_g_tca", custom_path)
    if set(rot.CHARACTERS) != set(TEMPLATES):
        die("approved rotations do not cover the 24 templates")
    records = {cid: build_record(cid, norm[cid], rot, forms) for cid in sorted(norm)}
    overlays(records, norm)
    for cid, rec in records.items():
        rec.setdefault("interlude_steps", ())
        rec["energy"].setdefault("cost_note", "")
        if rot.CHARACTERS[cid]["element"] != rec["element"]:
            die(f"{cid}: element {rec['element']} != rotation {rot.CHARACTERS[cid]['element']}")
    step_class = classify_steps(records, rot, forms)
    credits = time_only_credits(norm, rot)
    hits = hit_credits(norm, rot)
    static = args.static or (src.parent / "data" / "game_static.sqlite3")
    db_report = validate_db(records, static)
    checks = validate(records, step_class, custom)
    inputs = {f"chunk_{i}": sha(p) for i, p in enumerate(chunk_paths)}
    inputs.update({"team_rotation_data": sha(rot_path), "team_form_actions": sha(forms_path),
                   "team_custom_actions": sha(custom_path)})
    if static.exists():
        inputs["game_static"] = sha(static)
    summary = {"characters": len(records), "steps": len(step_class), **checks,
               "db_checked": db_report.get("checked", 0), "db_unresolved": len(db_report.get("unresolved", ())),
               "q_cost_enforceable": sorted(cid for cid, r in records.items()
                                            if r["energy"]["cost"][0] is not None
                                            and r["energy"]["cost"][2] in COST_ENFORCED),
               "q_cost_contested": sorted(cid for cid, r in records.items() if r["energy"]["cost"][2] in CONTESTED),
               "gauge_fallback": sorted(cid for cid, r in records.items() if r["gauge"]["fallback"]),
               "cd_conflicts": sorted((cid, kind) for cid, r in records.items() for kind in r.get("cd_conflict") or {}),
               "cd_vetoed": sorted((cid, kind) for cid, r in records.items() for kind in ("E", "Q")
                                   for c in r["cd"].get(kind, ()) if c and "measured veto" in c[1]),
               "time_only_credits": len(credits),
               "hit_credits": sorted(f"{cid}:{ab}/{sel}" for (cid, ab, sel), c in hits.items() if c[0] is not None),
               "hit_unknown": sorted(f"{cid}:{ab}/{sel}" for (cid, ab, sel), c in hits.items() if c[0] is None)}
    text = render(records, step_class, credits, global_values(docs[0]), summary, inputs, hits)
    compile(text, str(out), "exec")
    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != text:
            print(f"DIFFERS: {out}")
            return 1
        print(f"OK {out} ({len(text)} bytes)")
        return 0
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text)} bytes)")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if db_report.get("unresolved"):
        print("unresolved data: tags (not curves):", len(db_report["unresolved"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GenError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
