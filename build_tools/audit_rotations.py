# Generator: teamsim_energy/tools/audit_rotations.py  (NTE Drive Calc Global - team simulator resources, plan step 8)
"""Rotation audit of the resource levels: what the energy / cooldown / gauge checks do to every approved rotation.

usage (Python 3.11, PYTHONUTF8=1, run with the source-run runtime so ``src`` imports):
    python -I scratch/impl/_boot.py <tree root> tools/audit_rotations.py <tree root> <out.json> <out.md>
           [--skip-scan] [--scan-limit N]

Parts (all deterministic: fixed team lists, sorted output, rounded numbers, no clock time in the files):
  A  solo, 3 loops, graduation template of each of the 24 characters: legacy, then data / community x active / wall
     clock - per step outcome (ran / wait s / energy_short / cd_skip / form_cut), waits and skips per loop, ultimate
     energy gained per loop, gauge built per loop, time-only credits, Hotori's interlude, cooldown kinds with their
     value and confidence, and the "needs re-review" flag (a step skipped or waited for, a credit applied, a step
     whose cooldown kind is not modelled).
  B  teams (the recorded teams, the custom-mode equivalence teams and the gating-test teams), order "plan", 3 loops,
     default level: per member waits / skips / early swaps / fallback refills and the totals against legacy and
     against the old "wait in place" rule (``not_ready="wait"``; user decision D3, 2026-10-14: a team member whose
     step is not ready swaps out at once) and against the swap rule without the 0.3 s threshold ("immediate swap",
     ``swap_min_wait_s=0``; user decision 2026-10-18: less than 0.3 s of cooldown left is waited for).
  C  every 4-member team of the 24 (10,626) as a dry layout (no engine) with the automatic order at the community
     level, active and wall clock: teams with an early swap / an inserted wait (all members blocked), per member-kind
     case; the active clock also at the old wait rule and at the immediate swap (no threshold) for comparison.
The test account copy is not read (an empty temporary account; one-member and team results do not depend on it for
the layout); the static DB is read-only.
"""
from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import pathlib
import statistics
import sys
import time

assert sys.version_info[:2] == (3, 11), "run with Python 3.11"

from src.services import team_resources as tr                     # noqa: E402
from src.services import team_simulation_explanation as tx         # noqa: E402
from src.services import team_simulation_service as svc            # noqa: E402
from src.services.team_resource_data import RESOURCES, STEP_CLASS  # noqa: E402
from src.services.team_rotation_data import CHARACTERS             # noqa: E402

TEMPLATES = tuple(sorted(RESOURCES))
LEVELS = (("data", "active"), ("data", "wall"), ("community", "active"), ("community", "wall"))
TEAMS = (
    # recorded battles (test_team_simulation_service item 5)
    (1036, 1004, 1054, 1003), (1036, 1072, 1054, 1003), (1036, 1072, 1075, 1003),
    # custom-mode equivalence teams (test_custom_cycle_service) and the whole-run teams
    (1051, 1075, 1003, 1071), (1042, 1008, 1020, 1039), (1076, 1051, 1072, 1010), (1025, 1057, 1052, 1055),
    (1019, 1021, 1010, 1020), (1033, 1023, 1071, 1004),
    # gating-test teams
    (1004, 1072, 1051, 1075), (1073, 1052, 1019, 1010), (1003, 1020, 1033, 1051),
)


def r3(x) -> float:
    return round(float(x or 0.0), 3)


def name(cid: int) -> str:
    rec = RESOURCES.get(int(cid)) or {}
    return f"{rec.get('name_ko', '')} {int(cid)}".strip()


def step_rows(expl, cid=None) -> list[dict]:
    out = []
    for v in expl.visits:
        if cid is not None and v.character_id != cid:
            continue
        for s in v.steps:
            row = {"loop": v.loop_index + 1, "member": v.character_id, "seq": s.seq, "slot": s.slot,
                   "status": s.status, "start_s": r3(s.start_s), "duration_s": r3(s.duration_s)}
            if s.status == tx.STEP_SWAP_OUT:     # D3: the time left and the approved steps not run
                row["remaining_s"] = r3(s.remaining_s)
                row["dropped"] = int(getattr(s, "dropped", 0) or 0)
            elif s.slot == tx.SLOT_WAIT and s.note == tx.STEP_NOTE_SHORT_WAIT:     # under the 0.3 s threshold (10-18)
                row["remaining_s"] = r3(s.remaining_s)
            if getattr(s, "wait_for", None) is not None:
                row["wait_for"] = int(s.wait_for)
            if s.cd_kind:
                row["cd_kind"] = s.cd_kind
            if s.note:
                row["note"] = s.note
            if s.energy_before is not None:
                row["energy_before"] = r3(s.energy_before)
            if s.energy_after is not None:
                row["energy_after"] = r3(s.energy_after)
            if s.credit:
                row["credit"] = r3(s.credit)
            out.append(row)
    return out


def summarise(result, cid=None) -> dict:
    expl = result.explanation
    rows = step_rows(expl, cid)
    waits = [(r["loop"], r["member"], r["seq"], r["status"], r.get("cd_kind", ""), r["duration_s"])
             for r in rows if r["slot"] == tx.SLOT_WAIT]
    skips = [(r["loop"], r["member"], r["seq"], r["status"], r.get("note", ""))
             for r in rows if r["status"] in (tx.STEP_ENERGY_SHORT, tx.STEP_CD_SKIP)
             or (r["status"] == tx.STEP_FORM_CUT and r.get("note") == tx.STEP_NOTE_FORM_NOT_ENTERED)]
    credits = sorted({(r["member"], r["seq"], r["credit"]) for r in rows if r.get("credit")})
    early = [(r["loop"], r["member"], r["seq"], r.get("cd_kind", ""), r.get("note", ""), r.get("remaining_s", 0.0),
              r.get("dropped", 0)) for r in rows if r["status"] == tx.STEP_SWAP_OUT]
    blocked = [(r["loop"], r["member"], r["seq"], r["duration_s"], r.get("wait_for"))
               for r in rows if r["slot"] == tx.SLOT_WAIT and r.get("note") == tx.STEP_NOTE_ALL_BLOCKED]
    short = [(r["loop"], r["member"], r["seq"], r.get("cd_kind", ""), r.get("remaining_s", 0.0))
             for r in rows if r["slot"] == tx.SLOT_WAIT and r.get("note") == tx.STEP_NOTE_SHORT_WAIT]
    per_loop = {}
    for v in expl.visits:
        if cid is not None and v.character_id != cid:
            continue
        loop = per_loop.setdefault(v.loop_index + 1, {"energy_gain": 0.0, "gauge_in": None, "gauge_out": 0.0,
                                                      "waited_s": 0.0})
        loop["energy_gain"] = r3(loop["energy_gain"] + float(getattr(v, "energy_gain", 0.0) or 0.0))
        loop["gauge_in"] = r3(v.gauge_in) if loop["gauge_in"] is None else loop["gauge_in"]
        loop["gauge_out"] = r3(v.gauge_out)
        loop["waited_s"] = r3(loop["waited_s"] + float(getattr(v, "waited_s", 0.0) or 0.0))
    res = {}
    for r in getattr(expl, "resources", ()) or ():
        if cid is not None and r.character_id != cid:
            continue
        res[str(r.character_id)] = {
            "energy_kind": r.energy_kind, "cost": list(r.cost) if r.cost else None, "cost_enforced": r.cost_enforced,
            "q_planned": r.q_planned, "q_cast": r.q_cast, "q_skipped": [x + 1 for x in r.q_skipped],
            "waited_s": r3(r.waited_s), "interlude_s": r3(r.interlude_s), "energy_gained": r3(r.energy_gained),
            "charge_eff": r3(r.charge_eff), "gauge_fallback": r.gauge_fallback, "fallback_reason": r.fallback_reason,
            "cd": [[k, used, best, conf] for k, used, best, _src, conf in r.cd],
            "unchecked": list(r.unchecked), "credited_gauge": r3(r.credited_gauge), "charges": r.charges,
            "meter_short": r.meter_short, "events": [list(e) for e in r.events]}
    swaps = [s.outcome for s in expl.swaps]
    return {"total": round(result.total_damage, 1), "wall_s": r3(result.wall_time_s),
            "reactions": sum(1 for o in swaps if o == tx.OUTCOME_REACTION), "swaps": len(swaps),
            "reaction_damage": round(result.reaction_damage, 1),
            "active_s": r3(result.active_time_s), "dps": round(result.dps, 1) if hasattr(result, "dps") else None,
            "waited_s": r3(getattr(expl, "waited_s", 0.0)), "waits": waits, "skips": skips, "credits": credits,
            "early_swaps": early, "all_blocked": blocked, "short_waits": short,
            "not_ready": getattr(expl, "not_ready", ""),
            "per_loop": {str(k): v for k, v in sorted(per_loop.items())}, "resources": res,
            "gauge_refills": [list(x) for x in getattr(expl, "gauge_refills", ()) or ()],
            "steps": rows}


def unclassified(cid: int) -> list[int]:
    return sorted(seq for (c, seq), row in STEP_CLASS.items() if c == cid and row[2] == "other_skill_unclassified")


def part_a(static) -> dict:
    out = {}
    for cid in TEMPLATES:
        entry = {"name": name(cid), "field_time_s": float((CHARACTERS.get(cid) or {}).get("field_time_s") or 0.0)}
        with svc.solo_session(static, cid, loops=3, resource_model="legacy") as run:
            legacy = run(svc.MemberSpec(cid)).result
        entry["legacy"] = {"total": round(legacy.total_damage, 1), "wall_s": r3(legacy.wall_time_s),
                           "active_s": r3(legacy.active_time_s)}
        for model, clock in LEVELS:
            policy = tr.policy_for(model, clock=clock)
            with svc.solo_session(static, cid, loops=3, resource_policy=policy) as run:
                got = run(svc.MemberSpec(cid)).result
            entry[f"{model}:{clock}"] = summarise(got, cid)
        default = entry["community:active"]
        flags = []
        if default["waits"]:
            flags.append("waits")
        if default["skips"]:
            flags.append("skips")
        if default["credits"]:
            flags.append("time_only_credit")
        if unclassified(cid):
            flags.append("cd_unclassified")
        if (default["resources"].get(str(cid)) or {}).get("gauge_fallback"):
            flags.append("gauge_fallback")
        entry["needs_review"] = flags
        entry["unclassified_steps"] = unclassified(cid)
        out[str(cid)] = entry
        print(f"A {cid} legacy {entry['legacy']['wall_s']}s -> community {default['wall_s']}s waits "
              f"{[w[-1] for w in default['waits']]} skips {len(default['skips'])} flags {flags}", flush=True)
    return out


def part_b(static) -> dict:
    out = {}
    for team in TEAMS:
        specs = [svc.MemberSpec(c) for c in team]
        row = {}
        for key, model, policy in (("legacy", "legacy", None), ("community:active", "community", None),
                                   ("community:wait", "community", tr.policy_for("community", not_ready="wait")),
                                   ("community:swap0", "community", tr.policy_for("community", swap_min_wait_s=0.0))):
            result = _team_run(static, specs, model, policy)
            s = summarise(result)
            s.pop("steps")
            s["order"] = list(result.explanation.order)
            if model == "legacy":
                s.pop("resources")
            row[key] = s
        out[",".join(str(c) for c in team)] = row
        d, w = row["community:active"], row["community:wait"]
        print(f"B {team} legacy {row['legacy']['total']:.0f}/{row['legacy']['wall_s']}s -> {d['total']:.0f}/"
              f"{d['wall_s']}s waits {len(d['waits'])} skips {len(d['skips'])} early swaps {len(d['early_swaps'])} "
              f"refills {d['gauge_refills']} short waits {len(d['short_waits'])} | wait rule {w['total']:.0f}/"
              f"{w['wall_s']}s | immediate swap {row['community:swap0']['total']:.0f}/"
              f"{row['community:swap0']['wall_s']}s", flush=True)
    return out


def _team_run(static, specs, model, policy=None):
    import tempfile

    from src.storage.sqlite.user_data_dao import UserDataDao

    with tempfile.TemporaryDirectory(prefix="audit_rot_", ignore_cleanup_errors=True) as tmp:
        user = pathlib.Path(tmp) / "user_data.sqlite3"
        UserDataDao(user, account_id="audit", account_name="audit").close()
        return svc.simulate_team(static, user, "audit", specs, order_mode="plan", loops=3, resource_model=model,
                                 resource_policy=policy)


def part_c(static, limit: int | None) -> dict:
    """Dry layouts (no engine) of every 4-member team, automatic order."""
    teams = list(itertools.combinations(TEMPLATES, 4))
    if limit:
        teams = teams[:limit]
    started = time.perf_counter()
    found = {"active": [], "wall": [], "active_wait": [], "active_swap0": []}
    lacrimosa_q_bind = {"active": 0, "wall": 0}
    with svc._open_session(static, None, "audit_scan", list(TEMPLATES), loops=3, gauge_rule="game",
                           opening_gauge=svc._effective_opening("full")) as make:
        full = make([svc.MemberSpec(c) for c in TEMPLATES])
        by_cid = {int(c["character_id"]): c for c in full.characters}
        for label, clock, rule, thr in (("active", "active", "auto", None), ("wall", "wall", "auto", None),
                                        ("active_wait", "active", "wait", None),     # D3: the old rule waits
                                        ("active_swap0", "active", "auto", 0.0)):    # no 0.3 s threshold (10-18)
            policy = tr.policy_for("community", clock=clock, not_ready=rule,
                                   **({} if thr is None else {"swap_min_wait_s": thr}))
            for team in teams:
                ids = list(team)
                chars = [by_cid[c] for c in ids]
                build = {"characters": [c for c in full.build["characters"] if int(c["character_id"]) in team]}
                ctx = dataclasses.replace(full, team_ids=ids, characters=chars, build=build,
                                          elements={c: full.elements[c] for c in ids},
                                          names={c: full.names[c] for c in ids}, policy=policy)
                order = svc._visit_order(ids, ctx.elements, "auto")
                layout, _sched, _to_active = svc._dry_layout(ctx, order)
                waits, early = [], []
                for v in layout.visits:
                    for s in v.steps:
                        if s.slot == "wait":
                            waits.append((v.character_id, v.loop_index + 1, s.status, s.cd_kind,
                                          r3((s.end_us - s.start_us) / 1e6), s.note))
                        elif s.status == "swap_out":
                            early.append((v.character_id, v.loop_index + 1, s.cd_kind, s.note,
                                          r3(s.remaining_us / 1e6), int(s.dropped)))
                if waits or early:
                    found[label].append({"team": ids, "order": list(order), "waits": waits, "early_swaps": early})
    seconds = time.perf_counter() - started
    out = {"teams": len(teams), "seconds_note": "runtime not stored (determinism)"}
    for clock in ("active", "wall", "active_wait", "active_swap0"):
        short = [w for t in found[clock] for w in t["waits"] if w[2] == "cd_wait" and w[5] == tx.STEP_NOTE_SHORT_WAIT]
        cases = [w for t in found[clock] for w in t["waits"] if w[2] == "cd_wait" and w[5] != tx.STEP_NOTE_SHORT_WAIT]
        by_kind = {}
        for cid, _loop, _st, kind, sec, _note in cases:
            by_kind.setdefault(f"{cid}:{kind}", []).append(sec)
        early = [e for t in found[clock] for e in t["early_swaps"]]
        early_kind = {}
        for cid, _loop, kind, reason, left, _dropped in early:
            early_kind.setdefault(f"{cid}:{kind}:{reason}", []).append(left)
        out[clock] = {
            "teams_with_wait": sum(1 for t in found[clock] if t["waits"]),
            "teams_with_cd_wait": sum(1 for t in found[clock] if any(w[2] == "cd_wait" and w[5] != tx.STEP_NOTE_SHORT_WAIT
                                                                     for w in t["waits"])),
            "teams_with_short_wait": sum(1 for t in found[clock] if any(w[5] == tx.STEP_NOTE_SHORT_WAIT
                                                                        for w in t["waits"])),
            "short_wait_cases": len(short), "short_wait_max_s": r3(max([w[4] for w in short], default=0.0)),
            "short_wait_total_s": r3(sum(w[4] for w in short)),
            "cd_wait_cases": len(cases),
            "all_blocked_cases": sum(1 for w in cases if w[5] == tx.STEP_NOTE_ALL_BLOCKED),
            "median_s": r3(statistics.median([c[4] for c in cases])) if cases else 0.0,
            "max_s": r3(max([c[4] for c in cases], default=0.0)),
            "by_member_kind": {k: {"n": len(v), "max_s": r3(max(v)), "median_s": r3(statistics.median(v))}
                               for k, v in sorted(by_kind.items())},
            "teams_with_early_swap": sum(1 for t in found[clock] if t["early_swaps"]),
            "early_swap_cases": len(early),
            "early_dropped_steps": sum(1 + e[5] for e in early),    # the swapped-out step + the rest (F2)
            "early_by_member_kind": {k: {"n": len(v), "max_left_s": r3(max(v)),
                                         "median_left_s": r3(statistics.median(v))}
                                     for k, v in sorted(early_kind.items())},
            "examples": found[clock][:12]}
    print(f"C scanned {len(teams)} teams x 3 runs in {seconds:.0f}s: active {out['active']['teams_with_cd_wait']} "
          f"wall {out['wall']['teams_with_cd_wait']} teams with a cooldown wait, active "
          f"{out['active']['teams_with_early_swap']} wall {out['wall']['teams_with_early_swap']} with an early swap; "
          f"old wait rule active {out['active_wait']['teams_with_cd_wait']}; immediate swap active "
          f"{out['active_swap0']['teams_with_early_swap']} with an early swap; default short waits "
          f"{out['active']['teams_with_short_wait']} teams", flush=True)
    return out


# ── markdown ─────────────────────────────────────────────────────────────────

def md(doc: dict) -> str:
    L = ["# Rotation audit - resource levels (energy, Esper-Cycle gauge, cooldowns)", "",
         "Generated by `teamsim_energy/tools/audit_rotations.py` (plan step 8) from the dev tree; deterministic. "
         "Solo = graduation template, 3 loops, automatic order (the efficiency-table setting). Times in seconds of "
         "the wall timeline (time stops included) unless marked active.", "",
         "Not-ready rule (user decision D3, 2026-10-14): in a team a member whose step is not ready (cooldown, Hotori's "
         "clock, a known ultimate cost) swaps out at once and the next member enters by the normal gauge rule; when "
         "every member is blocked the earliest ready one is waited for. Alone there is nobody to swap to: part A "
         "(solo) waits as before. Threshold (user decision 2026-10-18): a cooldown with less than 0.3 s of battle "
         "time left is waited for and the skill cast (\"short wait\"); 0.3 s or more swaps out. \"Immediate swap\" = "
         "the swap rule without that threshold (the implementation before 2026-10-18).", ""]
    a = doc["solo"]
    L += ["## A. Solo (3 loops) - default level `community`, active clock", "",
          "| id | member | legacy wall | default wall | waits (loop:seq kind s) | skipped / cut | Q cast | energy/loop "
          "(1,2,3) | gauge/loop (data + credit) | flags |", "|---|---|---|---|---|---|---|---|---|---|"]
    for cid, e in a.items():
        d = e["community:active"]
        res = d["resources"].get(cid) or {}
        waits = "; ".join(f"{w[0]}:{w[2]} {w[4] or w[3]} {w[5]:g}" for w in d["waits"]) or "—"
        skips = "; ".join(f"{s[0]}:{s[2]} {s[3]}" + (f"({s[4]})" if s[4] else "") for s in d["skips"]) or "—"
        el = ", ".join(f"{v['energy_gain']:g}" for _k, v in sorted(d["per_loop"].items()))
        credit = sum(x[2] for x in d["credits"]) / 3.0
        loop_gauge = float((RESOURCES[int(cid)].get("gauge") or {}).get("loop") or 0.0)
        gl = f"{loop_gauge:g}" + (f" + {credit:g}" if credit else "")
        q = f"{res.get('q_cast', 0)}/{res.get('q_planned', 0)}"
        L.append(f"| {cid} | {e['name']} | {e['legacy']['wall_s']:g} | {d['wall_s']:g} | {waits} | {skips} | {q} | "
                 f"{el} | {gl} | {', '.join(e['needs_review']) or '—'} |")
    L += ["", "### Other levels (wall time; waits total s)", "",
          "| id | member | data active | data wall | community active | community wall |", "|---|---|---|---|---|---|"]
    for cid, e in a.items():
        cells = []
        for key in ("data:active", "data:wall", "community:active", "community:wall"):
            d = e[key]
            cells.append(f"{d['wall_s']:g} (wait {d['waited_s']:g}, skip {len(d['skips'])})")
        L.append(f"| {cid} | {e['name']} | " + " | ".join(cells) + " |")
    L += ["", "### Cooldown kinds and sources (default level)", "",
          "| id | member | Q cost | E | Q | support skill | counter | unchecked kinds | events |", "|---|---|---|---|---|---|---|---|---|"]
    for cid, e in a.items():
        res = e["community:active"]["resources"].get(cid) or {}
        cd = {row[0]: row for row in res.get("cd", [])}

        def cell(kind):
            row = cd.get(kind) or (cd.get("E_alt") if kind == "E" else None)
            if not row:
                return "—"
            _k, used, best, conf = row
            if used is None:
                return f"? ({best:g}s {conf})" if best is not None else "?"
            return f"{used:g}s {conf}"
        cost = res.get("cost") or [None, "", "unknown"]
        cost_text = (f"{cost[0]:g} {cost[2]}" if cost[0] is not None else f"? {cost[2]}") + \
            (" (enforced)" if res.get("cost_enforced") else "")
        L.append(f"| {cid} | {e['name']} | {cost_text} | {cell('E')} | {cell('Q')} | {cell('QTE')} | {cell('counter')} | "
                 f"{', '.join(res.get('unchecked') or []) or '—'} | "
                 f"{', '.join(f'{c} {v:g}' for c, v in res.get('events') or []) or '—'} |")
    flagged = [(cid, e) for cid, e in a.items() if e["needs_review"]]
    L += ["", f"### Needs re-review ({len(flagged)} of {len(a)})", "",
          "A rotation is flagged when, at the default level, a step of the solo run was waited for or skipped, a "
          "time-only step was credited with gauge, a step's cooldown kind is not modelled, or the member uses the "
          "fixed gauge rule. The approved rotations are unchanged; the flag means the user should look at the "
          "result before release (user policy 2026-10-03).", ""]
    for cid, e in flagged:
        L.append(f"- {cid} {e['name']}: {', '.join(e['needs_review'])}"
                 + (f" (unclassified steps {e['unclassified_steps']})" if e["unclassified_steps"] else ""))
    b = doc["teams"]
    L += ["", "## B. Teams (order `plan`, 3 loops, default level)", "",
          "| team | legacy total / wall / reactions | default total / wall / reactions | old wait rule total / wall / "
          "reactions | default vs wait rule | immediate swap total / wall (default vs it) | order legacy → default | "
          "early swaps (member#seq loop kind left) | short waits (member#seq loop kind left) | waits | skipped | "
          "fallback refills |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, row in b.items():
        d = row["community:active"]
        w = row.get("community:wait") or d
        waits = "; ".join(f"{x[1]}#{x[2]} L{x[0]} {x[4] or x[3]} {x[5]:g}" for x in d["waits"]) or "—"
        blocked = {(x[0], x[1], x[2]) for x in d.get("all_blocked") or ()}
        if blocked:
            waits += " (all blocked)" if len(blocked) == len(d["waits"]) else f" ({len(blocked)} all blocked)"
        skips = "; ".join(f"{s[1]}#{s[2]} L{s[0]} {s[3]}" for s in d["skips"]) or "—"
        early = "; ".join(f"{x[1]}#{x[2]} L{x[0]} {x[3]} {x[5]:g}" for x in d.get("early_swaps") or ()) or "—"
        lg = row["legacy"]
        n0 = row.get("community:swap0") or d
        short = "; ".join(f"{x[1]}#{x[2]} L{x[0]} {x[3]} {x[4]:g}" for x in d.get("short_waits") or ()) or "—"
        d0 = (d["total"] / n0["total"] - 1.0) * 100.0 if n0["total"] else 0.0
        vs0 = "same" if (d["total"] == n0["total"] and d["wall_s"] == n0["wall_s"]) else (
            f"{d0:+.2f} % / {d['wall_s'] - n0['wall_s']:+.3f} s")
        delta = (d["total"] / w["total"] - 1.0) * 100.0 if w["total"] else 0.0
        diff = "same" if (d["total"] == w["total"] and d["wall_s"] == w["wall_s"]) else (
            f"{delta:+.2f} % / {d['wall_s'] - w['wall_s']:+.3f} s")
        L.append(f"| {key} | {lg['total']:,.0f} / {lg['wall_s']:g} / {lg['reactions']} of {lg['swaps']} | "
                 f"{d['total']:,.0f} / {d['wall_s']:g} / {d['reactions']} of {d['swaps']} | "
                 f"{w['total']:,.0f} / {w['wall_s']:g} / {w['reactions']} of {w['swaps']} | {diff} | "
                 f"{n0['total']:,.0f} / {n0['wall_s']:g} ({vs0}) | "
                 f"{'→'.join(str(c) for c in lg['order'])}"
                 + ("" if lg["order"] == d["order"] else f" ⇒ {'→'.join(str(c) for c in d['order'])}")
                 + f" | {early} | {short} | {waits} | {skips} | {d['gauge_refills'] or '—'} |")
    c = doc.get("scan")
    if c:
        L += ["", f"## C. All {c['teams']} four-member teams (dry layout, automatic order, community level)", ""]
        for clock in ("active", "wall", "active_wait", "active_swap0"):
            s = c.get(clock)
            if not s:
                continue
            title = {"active": "active clock (default: swap, 0.3 s threshold)", "wall": "wall clock (swap, threshold)",
                     "active_wait": "active clock, old wait rule",
                     "active_swap0": "active clock, immediate swap (no threshold)"}[clock]
            L.append(f"- {title}: {s.get('teams_with_early_swap', 0)} teams with an early swap "
                     f"({s.get('early_swap_cases', 0)} cases, {s.get('early_dropped_steps', 0)} approved steps not run); "
                     f"{s['teams_with_cd_wait']} teams with a cooldown wait ({s['cd_wait_cases']} cases, of them "
                     f"{s.get('all_blocked_cases', 0)} with every member blocked; median {s['median_s']:g} s, max "
                     f"{s['max_s']:g} s); {s['teams_with_wait'] - s['teams_with_cd_wait']} more with only Hotori's "
                     f"clock wait or only short waits; short waits (< 0.3 s left): {s.get('teams_with_short_wait', 0)} "
                     f"teams, {s.get('short_wait_cases', 0)} cases, max {s.get('short_wait_max_s', 0.0):g} s")
            for k, v in s.get("early_by_member_kind", {}).items():
                cid, kind, reason = k.split(":")
                L.append(f"  - early swap {name(int(cid))} {kind} ({reason}): {v['n']} cases, time left median "
                         f"{v['median_left_s']:g} s, max {v['max_left_s']:g} s")
            for k, v in s["by_member_kind"].items():
                cid, kind = k.split(":")
                L.append(f"  - wait {name(int(cid))} {kind}: {v['n']} cases, median {v['median_s']:g} s, "
                         f"max {v['max_s']:g} s")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=pathlib.Path)
    ap.add_argument("out_json", type=pathlib.Path)
    ap.add_argument("out_md", type=pathlib.Path)
    ap.add_argument("--skip-scan", action="store_true")
    ap.add_argument("--scan-limit", type=int)
    ap.add_argument("--only", help="comma list of parts (a,b,c)")
    args = ap.parse_args()
    static = args.root / "data" / "game_static.sqlite3"
    parts = set((args.only or "a,b,c").split(","))
    doc = {"generator": "teamsim_energy/tools/audit_rotations.py", "resource_model_default": tr.DEFAULT_RESOURCE_MODEL,
           "data_summary": __import__("src.services.team_resource_data", fromlist=["SUMMARY"]).SUMMARY}
    if args.out_json.exists():
        old = json.loads(args.out_json.read_text(encoding="utf-8"))
        for key in ("solo", "teams", "scan"):
            if key in old:
                doc[key] = old[key]
    if "a" in parts:
        doc["solo"] = part_a(static)
    if "b" in parts:
        doc["teams"] = part_b(static)
    if "c" in parts and not args.skip_scan:
        doc["scan"] = part_c(static, args.scan_limit)
    args.out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    if "solo" in doc and "teams" in doc:
        args.out_md.write_text(md(doc), encoding="utf-8")
    print(f"wrote {args.out_json} / {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
