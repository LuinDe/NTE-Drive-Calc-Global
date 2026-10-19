"""Generate (or check) src/services/arc_efficiency_data.py - the arc efficiency table's precomputed rows (L1).

global231_plan 3.4, efficiency_design §4.  The rows come from ``arc_efficiency_service.compute_character`` - the
same code the application runs when the seed does not match its data - so the seed and an in-app recomputation
cannot differ.  Every eligible character (exclusive arc + graduation template + approved rotation; regular
characters are not in the table, user decision U1) x every equippable arc (rule A) x refinement {1, max_star} x
loops {1, 3} x entry "opener" x graduation template Puka Boot Camp level (aes.TEMPLATE_LEVELS, decision U1: level 0 in
ROWS exactly as before, the others in ROWS_BY_TEMPLATE).  Language zh, empty account in a temp folder (a level > 0
account holds only that training level), no byte-code written, keys sorted, damage rounded to 0.1: two runs give
the same bytes.

usage (py 3.11):
  gen_arc_efficiency_data.py --root <tree root> --internal <runtime _internal> (--write | --check) [--src <dir>]
      --root      the tree (src/ and data/; e.g. work_g231/g231_root)
      --src       folder that holds the src/ to import and to write (default: --root)
      --internal  PySide6 / runtime modules for a source run (e.g. work_g231/app_test231/_internal)
      --write     write <src>/src/services/arc_efficiency_data.py
      --check     rebuild in memory and compare: file bytes, DATASET.sha256 == data/manifest.json == the file's
                  real hash, ENGINE_FP == the current source closure; any difference -> exit 1 (stops the build)
exit 0 ok | 1 check failed | 2 bad environment (corrections switched off, manifest does not match the DB)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

assert sys.version_info[:2] == (3, 11), "Python 3.11 only"

GENERATOR = "scratchpad/v230/work_g231/scripts/gen_arc_efficiency_data.py"
TARGET = Path("src") / "services" / "arc_efficiency_data.py"


def setup(src: Path, internal: Path) -> None:
    os.environ["NTE_KO_PATCH_LANG"] = "zh"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(src))
    sys.path.append(str(internal))
    for folder in (internal, internal / "PySide6", internal / "shiboken6"):
        if folder.is_dir():
            os.add_dll_directory(str(folder))


def _row_lines(rows: dict, indent: str) -> list:
    out = []
    for key in sorted(rows):
        row = rows[key]
        cid, fork_id, refine, loops, entry = key
        out.append(f"{indent}({cid}, {fork_id!r}, {refine}, {loops}, {entry!r}): "
                   f"({row.damage:.1f}, 0x{row.flags:02x}, {row.end_us}, {row.active_us}),")
    return out


def render(identity, dataset: dict, characters: list, rows_by_level: dict, closure_size: int) -> str:
    from src.services import arc_efficiency_service as aes

    rows = rows_by_level[0]

    out = [
        "# 弧盘效率表：预先计算的单人循环伤害（由 work_g231/scripts/gen_arc_efficiency_data.py 生成，勿手改）",
        f"# GENERATED FILE - DO NOT EDIT.  Regenerate with {GENERATOR} --write",
        f"# inputs: static DB sha256 {identity.db_sha256}; engine fingerprint {identity.engine_fp} "
        f"(source closure of {aes.FP_ROOT_MODULE}, {closure_size} modules)",
        '"""Precomputed rows of the arc efficiency table (generated, do not edit): L1 of arc_efficiency_service.',
        "",
        "ROWS[(character_id, fork_id, refinement, loops, entry)] = (damage, flags, end_us, active_us): the character",
        "alone on its approved rotation, graduation template with only the arc and refinement swapped, Global arc",
        "corrections B1-B4 on, empty account, language zh (flags: arc_efficiency_service.FLAG_*).",
        "CHARACTERS[cid] = {name_zh, exclusive, forks: ((fork_id, max_star), ...)}: the arc set the rows were computed",
        "for; the service uses a character's rows only while ALGO_VERSION, DATASET.sha256, ENGINE_FP and that set",
        "equal the running application's.",
        "ROWS_BY_TEMPLATE[level] = the same rows with the graduation template's Puka Boot Camp at that level (decision",
        "U1: the account checkbox 'view at max level'); ROWS is level 0.",
        '"""',
        "",
        f"FORMAT = {aes.FORMAT}",
        f"ALGO_VERSION = {aes.ALGO_VERSION!r}",
        "DATASET = {" + ", ".join(f"{k!r}: {dataset[k]!r}" for k in ("dataset_id", "schema", "sha256")) + "}",
        f"ENGINE_FP = {identity.engine_fp!r}",
        f"RESOURCE_MODEL = {aes.resource_model_state()!r}",
        f"ENTRY = {aes.ENTRY!r}",
        f"LOOPS = {tuple(sorted(aes.LOOP_CHOICES))!r}",
        "",
        "CHARACTERS = {",
    ]
    for entry in sorted(characters, key=lambda e: e.character_id):
        forks = ", ".join(f"({f!r}, {m})" for f, m in entry.forks_key)
        out.append(f"    {entry.character_id}: {{'name_zh': {entry.name_zh!r}, 'exclusive': {entry.exclusive_fork_id!r}, "
                   f"'forks': ({forks},)}},")
    out.append("}")
    out.append("")
    out.append("ROWS = {")
    out.extend(_row_lines(rows, "    "))
    out.append("}")
    out.append("")
    levels = tuple(sorted(rows_by_level))
    out.append(f"TEMPLATE_LEVELS = {levels!r}")
    out.append("")
    out.append("ROWS_BY_TEMPLATE = {")
    for level in levels:
        if level == 0:
            continue
        out.append(f"    {level}: {{")
        out.extend(_row_lines(rows_by_level[level], "        "))
        out.append("    },")
    out.append("}")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--src", default="")
    ap.add_argument("--internal", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    src = Path(args.src).resolve() if args.src else root
    setup(src, Path(args.internal).resolve())
    switch = os.environ.get("NTE_TEAM_FORK_CORRECTIONS", "")
    if switch.strip().casefold() not in ("", "on", "all", "1", "true", "yes"):
        print(f"refusing: NTE_TEAM_FORK_CORRECTIONS={switch!r} (the seed is computed with every correction on)")
        return 2

    from src.services import arc_efficiency_service as aes
    from src.services import team_fork_corrections as tfc
    from src.services import team_resources

    if team_resources.DEFAULT_RESOURCE_MODEL != team_resources.SHIPPED_RESOURCE_MODEL:     # review F8
        print(f"refusing: NTE_TEAM_RESOURCE_MODEL={team_resources.DEFAULT_RESOURCE_MODEL!r} (the seed is computed at "
              f"the shipped level {team_resources.SHIPPED_RESOURCE_MODEL!r})")
        return 2

    tfc.ENABLED.update(tfc.ALL)
    static = root / "data" / "game_static.sqlite3"
    block = aes.manifest_dataset(static)
    real = aes.file_sha256(static)
    if str(block.get("sha256", "")).upper() != real or int(block.get("size_bytes") or -1) != static.stat().st_size:
        print(f"refusing: data/manifest.json does not describe {static.name} (manifest {block.get('sha256')}, "
              f"file {real})")
        return 2
    dataset = {"dataset_id": str(block.get("dataset_id") or ""), "schema": int(block.get("schema_version") or 0),
               "sha256": real}
    closure = aes.source_closure(src)
    identity = aes.Identity(aes.ALGO_VERSION, real, aes.engine_fingerprint(src), dataset["dataset_id"])
    started = time.perf_counter()
    characters = aes.eligible_characters(static)
    rows_by_level: dict = {}
    for level in aes.TEMPLATE_LEVELS:
        rows: dict = {}
        for loops in sorted(aes.LOOP_CHOICES):
            for entry in characters:
                t0 = time.perf_counter()
                got = aes.compute_character(static, entry, loops, template_level=level)
                basis = got.get(aes.row_key(entry.character_id, entry.exclusive_fork_id, 1, loops))
                if basis is None or basis.damage <= 0:
                    print(f"FAIL {entry.character_id} loops {loops} template Lv {level}: exclusive refinement-1 "
                          f"damage is 0")
                    return 1
                rows.update(got)
                print(f"  {entry.character_id} L{loops} T{level}: {len(got)} rows {time.perf_counter() - t0:.1f}s "
                      f"basis {basis.damage:,.1f}", flush=True)
        rows_by_level[level] = rows
    text = render(identity, dataset, characters, rows_by_level, len(closure))
    print(f"{len(characters)} characters, {sum(len(r) for r in rows_by_level.values())} rows "
          f"(template levels {tuple(rows_by_level)}), {time.perf_counter() - started:.1f}s; "
          f"engine fingerprint {identity.engine_fp} ({len(closure)} modules); DB {real[:16]}...")
    target = src / TARGET
    data = text.encode("utf-8")
    if args.write:
        target.write_bytes(data)
        print(f"written {target} sha256 {hashlib.sha256(data).hexdigest()}")
        return 0
    problems = []
    current = target.read_bytes() if target.is_file() else b""
    if current != data:
        problems.append(f"{TARGET.as_posix()} differs from a fresh generation (sha256 file "
                        f"{hashlib.sha256(current).hexdigest()[:16]} vs fresh {hashlib.sha256(data).hexdigest()[:16]})")
    namespace: dict = {}
    try:
        exec(compile(current.decode("utf-8"), str(target), "exec"), namespace)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"{TARGET.as_posix()} does not load: {type(exc).__name__}: {exc}")
    seed_dataset = namespace.get("DATASET") or {}
    if str(seed_dataset.get("sha256", "")).upper() != str(block.get("sha256", "")).upper():
        problems.append(f"DATASET.sha256 {seed_dataset.get('sha256')} != data/manifest.json {block.get('sha256')}")
    if namespace.get("ENGINE_FP") != identity.engine_fp:
        problems.append(f"ENGINE_FP {namespace.get('ENGINE_FP')} != current source closure {identity.engine_fp}")
    for p in problems:
        print("CHECK FAILED: " + p)
    print("check " + ("FAILED" if problems else "ok") + f" ({target})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
