"""Generate (or check) src/services/awakening_efficiency_data.py - the character awakening (돌파) efficiency table's
precomputed rows (L1).

design_final §3.4 (work_g231/awaken/reports).  The rows come from ``awakening_efficiency_service.compute_character``
- the code the application runs when the seed does not match its data - so the seed and an in-app recomputation
cannot differ.  Every eligible character (graduation template + approved rotation: 24) x every variant
(``jobs_of``: A0, A6, +EffectN, R3, R6, -EffectN) x loops {1, 3} x entry "opener" x graduation template Puka Boot
Camp level (TEMPLATE_LEVELS: level 0 in ROWS, the others in ROWS_BY_TEMPLATE).  Arc corrections B1-B4, the awakening
node rules and the Global live overlay at the shipped state, language zh, empty account in a temp folder, no
byte-code written, keys sorted, damage rounded to 0.1: two runs give the same bytes.

usage (py 3.11):
  gen_awakening_efficiency_data.py --root <tree root> --internal <runtime _internal> (--write | --check) [--src <dir>]
      --root      the tree (src/ and data/; e.g. work_g231/updater/root)
      --src       folder that holds the src/ to import and to write (default: --root)
      --internal  PySide6 / runtime modules for a source run (e.g. work_g231/app_test231/_internal)
      --write     write <src>/src/services/awakening_efficiency_data.py
      --check     rebuild in memory and compare: file bytes, DATASET.sha256 == data/manifest.json == the file's
                  real hash, ENGINE_FP == the current source closure; any difference -> exit 1 (stops the build)
exit 0 ok | 1 check failed | 2 bad environment (corrections / node rules / overlay switched, manifest mismatch)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

assert sys.version_info[:2] == (3, 11), "Python 3.11 only"

GENERATOR = "scratchpad/v230/work_g231/scripts/gen_awakening_efficiency_data.py"
TARGET = Path("src") / "services" / "awakening_efficiency_data.py"


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
    for key in sorted(rows, key=lambda k: (k[0], VARIANT_ORDER[k[1]], k[2], k[3])):
        row = rows[key]
        cid, variant, loops, entry = key
        out.append(f"{indent}({cid}, {variant!r}, {loops}, {entry!r}): "
                   f"({row.damage:.1f}, 0x{row.flags:02x}, {row.end_us}, {row.active_us}),")
    return out


VARIANT_ORDER: dict = {}


def render(identity, dataset: dict, characters: list, rows_by_level: dict, closure_size: int) -> str:
    from src.services import arc_efficiency_service as aes
    from src.services import awakening_efficiency_service as awk

    rows = rows_by_level[0]
    out = [
        "# 角色觉醒（돌파）效率表：预先计算的单人循环伤害（由 work_g231/scripts/gen_awakening_efficiency_data.py 生成，勿手改）",
        f"# GENERATED FILE - DO NOT EDIT.  Regenerate with {GENERATOR} --write",
        f"# inputs: static DB sha256 {identity.db_sha256}; engine fingerprint {identity.engine_fp} "
        f"(source closure of {awk.FP_ROOT_MODULE}, {closure_size} modules)",
        '"""Precomputed rows of the character awakening efficiency table (generated, do not edit): L1 of',
        "awakening_efficiency_service.",
        "",
        "ROWS[(character_id, variant, loops, entry)] = (damage, flags, end_us, active_us): the character alone on its",
        "approved rotation, graduation template, basis arc at refinement 1, awakening = the variant (VARIANTS: A0 none,",
        "+EffectN level 1 with that effect, R3 / R6 level 3 / 6 with no effect, A6 the template's selection, -EffectN",
        "the template's selection without that effect), Global arc corrections B1-B4, awakening node rules and the",
        "Global live overlay at the shipped state, empty account, language zh (flags: arc_efficiency_service.FLAG_*).",
        "CHARACTERS[cid] = {name_zh, fork, nodes, template, template_level, exclusive}: what the rows were computed",
        "for; the service uses a character's rows only while ALGO_VERSION, DATASET.sha256, ENGINE_FP and that entry",
        "equal the running application's.",
        "ROWS_BY_TEMPLATE[level] = the same rows with the graduation template's Puka Boot Camp at that level (decision",
        "U1); ROWS is level 0.",
        '"""',
        "",
        f"FORMAT = {awk.FORMAT}",
        f"ALGO_VERSION = {awk.ALGO_VERSION!r}",
        "DATASET = {" + ", ".join(f"{k!r}: {dataset[k]!r}" for k in ("dataset_id", "schema", "sha256")) + "}",
        f"ENGINE_FP = {identity.engine_fp!r}",
        f"RESOURCE_MODEL = {aes.resource_model_state()!r}",
        f"ENTRY = {awk.ENTRY!r}",
        f"LOOPS = {tuple(sorted(awk.LOOP_CHOICES))!r}",
        f"VARIANTS = {tuple(awk.VARIANTS)!r}",
        "",
        "CHARACTERS = {",
    ]
    for entry in sorted(characters, key=lambda e: e.character_id):
        out.append(f"    {entry.character_id}: {{'name_zh': {entry.name_zh!r}, 'fork': {entry.fork_id!r}, "
                   f"'exclusive': {entry.exclusive!r}, 'nodes': {tuple(entry.nodes)!r}, "
                   f"'template': {tuple(entry.template)!r}, 'template_level': {int(entry.template_level)}}},")
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
    ap.add_argument("--only", default="", help="debug: comma list of character ids (never with --write)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.only and args.write:
        print("refusing: --only never writes the seed")
        return 2
    root = Path(args.root).resolve()
    src = Path(args.src).resolve() if args.src else root
    setup(src, Path(args.internal).resolve())
    switch = os.environ.get("NTE_TEAM_FORK_CORRECTIONS", "")
    if switch.strip().casefold() not in ("", "on", "all", "1", "true", "yes"):
        print(f"refusing: NTE_TEAM_FORK_CORRECTIONS={switch!r} (the seed is computed with every correction on)")
        return 2

    from src.services import arc_efficiency_service as aes
    from src.services import awakening_efficiency_service as awk
    from src.services import team_fork_corrections as tfc
    from src.services import team_resources

    if team_resources.DEFAULT_RESOURCE_MODEL != team_resources.SHIPPED_RESOURCE_MODEL:
        print(f"refusing: NTE_TEAM_RESOURCE_MODEL={team_resources.DEFAULT_RESOURCE_MODEL!r} (the seed is computed at "
              f"the shipped level {team_resources.SHIPPED_RESOURCE_MODEL!r})")
        return 2
    if aes.state_suffix():
        print(f"refusing: node rules / live overlay switched ({aes.state_suffix()}); the seed is computed at the "
              f"shipped state")
        return 2

    VARIANT_ORDER.update({v: i for i, v in enumerate(awk.VARIANTS)})
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
    closure = awk.source_closure(src)
    identity = aes.Identity(awk.ALGO_VERSION, real, awk.engine_fingerprint(src), dataset["dataset_id"])
    started = time.perf_counter()
    characters = awk.eligible_characters(static)
    if args.only:
        wanted = {int(c) for c in args.only.split(",") if c.strip()}
        characters = [e for e in characters if e.character_id in wanted]
    rows_by_level: dict = {}
    for level in awk.TEMPLATE_LEVELS:
        rows: dict = {}
        for loops in sorted(awk.LOOP_CHOICES):
            for entry in characters:
                t0 = time.perf_counter()
                got = awk.compute_character(static, entry, loops, template_level=level)
                a0 = got.get(awk.row_key(entry.character_id, "A0", loops))
                a6 = got.get(awk.row_key(entry.character_id, "A6", loops))
                if a0 is None or a6 is None or a0.damage <= 0 or a6.damage <= 0:
                    print(f"FAIL {entry.character_id} loops {loops} template Lv {level}: A0 / A6 damage is 0")
                    return 1
                rows.update(got)
                print(f"  {entry.character_id} L{loops} T{level}: {len(got)} rows {time.perf_counter() - t0:.1f}s "
                      f"A0 {a0.damage:,.1f} A6 {a6.damage:,.1f}", flush=True)
        rows_by_level[level] = rows
    text = render(identity, dataset, characters, rows_by_level, len(closure))
    print(f"{len(characters)} characters, {sum(len(r) for r in rows_by_level.values())} rows "
          f"(template levels {tuple(rows_by_level)}), {time.perf_counter() - started:.1f}s; "
          f"engine fingerprint {identity.engine_fp} ({len(closure)} modules); DB {real[:16]}...")
    target = src / TARGET
    data = text.encode("utf-8")
    if args.only:
        print("debug run (--only): nothing written or compared")
        return 0
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
