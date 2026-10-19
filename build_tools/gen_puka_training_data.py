"""Generate (or check) src/services/puka_training_data.py - the Puka Boot Camp (噗卡特训) level table.

pooka/reports/design_final.md §2.  The JSON source (work_g231/tables/puka_training_levels.json, a copy of
pooka/data/pooka_training_levels.json) lists 20 levels with per-level deltas in game units (flat values and
percentage points).  The module stores INTEGERS only: flat values as they are, crit rate / crit damage as
per-mille (0.1 % -> 1), so cumulative sums are exact and ``units / 1000.0`` gives the calculator fraction in one
rounding step (25 / 1000.0 == 0.025, while a float accumulation gives 0.025000000000000005).

Validation before rendering: 20 rows with contiguous levels 1..20, required plan level 2N+5, cost sum ==
total_cost_fons == 11,000,000, the JSON's own cumulative columns equal the recomputed cumulative, the max totals
equal (28, 30, 420, 25 permille, 50 permille, 12, 12).  Two runs give the same bytes (LF line endings, sorted
provenance).

usage (py 3.11):
  gen_puka_training_data.py --json <levels.json> (--write <tree root> | --check <tree root>)
      --write   write <tree>/src/services/puka_training_data.py
      --check   render in memory and compare bytes with the tree file (differs or missing -> exit 1)
exit 0 ok | 1 check failed | 2 bad input
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

assert sys.version_info[:2] == (3, 11), "Python 3.11 only"

GENERATOR = "scratchpad/v230/work_g231/scripts/gen_puka_training_data.py"
TARGET = Path("src") / "services" / "puka_training_data.py"
COLUMNS = ("AtkAdd", "DefAdd", "HPMaxAdd", "CritBase", "CritDamageBase", "MagBase", "UnbalIntensityBase")
JSON_KEYS = ("atk", "def", "hp", "crit_rate_pct", "crit_dmg_pct", "cycle", "break")
PERMILLE = {"crit_rate_pct", "crit_dmg_pct"}
NAMES = {"zh": "噗卡特训", "ko": "푸카 특훈", "en": "Puka Boot Camp", "ja": "プカ特訓"}


def units(key: str, value) -> int:
    """Game value -> stored integer (permille for the percent columns); refuses non-integral results."""
    scaled = float(value) * (10.0 if key in PERMILLE else 1.0)
    rounded = int(round(scaled))
    if abs(scaled - rounded) > 1e-9:
        raise ValueError(f"{key}={value!r} is not a whole unit")
    return rounded


def load(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    system = data["system"]
    levels = data["levels"]
    if len(levels) != 20 or [row["level"] for row in levels] != list(range(1, 21)):
        raise ValueError("expected levels 1..20")
    max_level = int(system["max_level"])
    if max_level != 20:
        raise ValueError(f"max_level {max_level}")
    total_cost = int(system["total_cost_fons"])
    rows = []
    cumulative = [0] * len(COLUMNS)
    cumulative_cost = 0
    for row in levels:
        level = int(row["level"])
        plan = int(row["required_plan_level"])
        if plan != 2 * level + 5:
            raise ValueError(f"level {level}: required_plan_level {plan} != {2 * level + 5}")
        cost = int(row["cost_fons"])
        cumulative_cost += cost
        if int(row["cumulative_cost_fons"]) != cumulative_cost:
            raise ValueError(f"level {level}: cumulative cost mismatch")
        delta = tuple(units(key, row["delta"].get(key, 0)) for key in JSON_KEYS)
        cumulative = [a + b for a, b in zip(cumulative, delta)]
        recorded = tuple(units(key, row["cumulative"].get(key, 0)) for key in JSON_KEYS)
        if recorded != tuple(cumulative):
            raise ValueError(f"level {level}: cumulative column {recorded} != recomputed {tuple(cumulative)}")
        rows.append((level, plan, cost, delta))
    if cumulative_cost != total_cost or total_cost != 11_000_000:
        raise ValueError(f"cost sum {cumulative_cost} / total {total_cost}")
    totals = tuple(cumulative)
    recorded_totals = tuple(units(key, data["max_totals"][key]) for key in JSON_KEYS)
    if totals != recorded_totals or totals != (28, 30, 420, 25, 50, 12, 12):
        raise ValueError(f"totals {totals} / recorded {recorded_totals}")
    names = {code: system["names"][code]["system"] for code in ("zh", "ko", "en", "ja")}
    if names != NAMES:
        raise ValueError(f"system names {names}")
    sources = tuple(sorted((sid, str(info.get("id") or ""), str(info.get("url") or ""))
                           for sid, info in (data.get("sources") or {}).items()))
    return {
        "rows": rows, "totals": totals, "sources": sources,
        "data_version": str(data.get("generated") or ""),
        "game_version": str(system.get("version") or "").split(" ", 1)[0],
        "unlock_plan_level": int(levels[0]["required_plan_level"]),
        "total_cost": total_cost, "max_level": max_level,
    }


def render(table: dict) -> str:
    out = [
        "# 噗卡特训：按等级累计的账号固定属性表（由 work_g231/scripts/gen_puka_training_data.py 生成，勿手改）",
        f"# GENERATED FILE - DO NOT EDIT.  Regenerate with {GENERATOR} --write",
        f"# inputs: tables/puka_training_levels.json (generated {table['data_version']}); integers only, "
        "crit rate / crit damage in permille",
        '"""Puka Boot Camp (噗卡特训) level table (generated, do not edit).',
        "",
        "One account-wide level 0..MAX_LEVEL; every deployed character receives the cumulative flat values.",
        "LEVELS[i] = (level, required_plan_level, cost_fons, delta_units) with delta_units ordered like COLUMNS;",
        "the two PERMILLE_COLUMNS are stored x1000 (0.1 % -> 1) so that cumulative sums are exact integers and",
        "``cumulative_property_stats`` divides once (25 / 1000.0 == 0.025).  TOTALS is asserted at import.",
        '"""',
        "from __future__ import annotations",
        "",
        "FORMAT = 1",
        f"GAME_VERSION = {table['game_version']!r}",
        f"DATA_VERSION = {table['data_version']!r}",
        f"MAX_LEVEL = {table['max_level']}",
        f"UNLOCK_PLAN_LEVEL = {table['unlock_plan_level']}          # training level N needs plan level 2N+5",
        f"TOTAL_COST_FONS = {table['total_cost']:_}",
        f"COLUMNS = {COLUMNS!r}",
        'PERMILLE_COLUMNS = frozenset({"CritBase", "CritDamageBase"})',
        "LEVELS = (",
    ]
    for level, plan, cost, delta in table["rows"]:
        out.append(f"    ({level}, {plan}, {cost:_}, {delta!r}),")
    out += [
        ")",
        f"TOTALS = {table['totals']!r}",
        "NAMES = {",
    ]
    for code in ("zh", "ko", "en", "ja"):
        out.append(f"    {code!r}: {NAMES[code]!r},")
    out += ["}", "SOURCES = (   # provenance only"]
    for sid, ident, url in table["sources"]:
        out.append(f"    ({sid!r}, {ident!r}, {url!r}),")
    out += [
        ")",
        "",
        "assert len(LEVELS) == MAX_LEVEL and [row[0] for row in LEVELS] == list(range(1, MAX_LEVEL + 1))",
        "assert tuple(sum(row[3][i] for row in LEVELS) for i in range(len(COLUMNS))) == TOTALS",
        "assert sum(row[2] for row in LEVELS) == TOTAL_COST_FONS",
        "",
        "",
        "def clamp_level(level) -> int:",
        '    """Integer level inside 0..MAX_LEVEL (non-integers and out-of-range values are clamped)."""',
        "    try:",
        "        value = int(level or 0)",
        "    except (TypeError, ValueError):",
        "        value = 0",
        "    return max(0, min(MAX_LEVEL, value))",
        "",
        "",
        "def cumulative_units(level) -> tuple[int, ...]:",
        '    """Cumulative stored units (flat values, permille for CritBase / CritDamageBase) up to ``level``."""',
        "    count = clamp_level(level)",
        "    totals = [0] * len(COLUMNS)",
        "    for row in LEVELS[:count]:",
        "        for index, value in enumerate(row[3]):",
        "            totals[index] += value",
        "    return tuple(totals)",
        "",
        "",
        "def cumulative_property_stats(level) -> dict[str, float]:",
        '    """Calculator property values for ``level``: every column, zeros included (level 0 -> all 0.0)."""',
        "    values = cumulative_units(level)",
        "    return {",
        "        column: (value / 1000.0 if column in PERMILLE_COLUMNS else float(value))",
        "        for column, value in zip(COLUMNS, values)",
        "    }",
        "",
        "",
        "def cumulative_display(level) -> tuple:",
        '    """Game-unit values for tooltips: flat values as int, the percent columns as percentage points."""',
        "    values = cumulative_units(level)",
        "    return tuple(",
        "        (value / 10.0 if column in PERMILLE_COLUMNS else value)",
        "        for column, value in zip(COLUMNS, values)",
        "    )",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument("--write", metavar="TREE")
    parser.add_argument("--check", metavar="TREE")
    args = parser.parse_args()
    if bool(args.write) == bool(args.check):
        parser.error("one of --write / --check")
    try:
        table = load(Path(args.json))
    except (KeyError, ValueError, TypeError) as exc:
        print(f"bad input: {exc}")
        return 2
    text = render(table)
    compile(text, "puka_training_data.py", "exec")
    namespace: dict = {}
    exec(compile(text, "puka_training_data.py", "exec"), namespace)   # the import-time asserts
    if namespace["cumulative_property_stats"](20) != {
        "AtkAdd": 28.0, "DefAdd": 30.0, "HPMaxAdd": 420.0, "CritBase": 0.025,
        "CritDamageBase": 0.05, "MagBase": 12.0, "UnbalIntensityBase": 12.0,
    }:
        print("bad input: cumulative_property_stats(20) is not the documented contract")
        return 2
    target = Path(args.write or args.check) / TARGET
    data = text.encode("utf-8")
    if args.check:
        same = target.is_file() and target.read_bytes() == data
        print(f"puka_training_data: {'up to date' if same else 'DIFFERS'} ({target})")
        return 0 if same else 1
    if target.is_file() and target.read_bytes() == data:
        print(f"puka_training_data: unchanged ({target})")
        return 0
    target.write_bytes(data)
    print(f"puka_training_data: written ({target}, {len(table['rows'])} levels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
