"""Build the installer stage of NTE Drive Calc Global 2.3.1 from the extracted official 2.3.1 payload (plan 8.2).

usage (Python 3.11):
    make_stage_g231.py <official231 dir> <guide dir> <stage dir> [--report <json>]

  <official231 dir>  scratchpad/v230/official231: manifest.json (written and self-verified by inno_extract.py) + app/
  <guide dir>        the seven Korean tutorial images 1.png .. 7.png (repository config/templates/guide; the same
                     files Global 2.3.0 and KO 2.3.1 ship)
  <stage dir>        must not exist yet

The stage holds exactly the files of the official manifest, copied by name from the manifest (the extraction folder
also contains runtime files written later by test runs - NTE.log, logs/, plugins/.loaded/ - which are never copied):
  - without NTE_Drive_Calc.exe (the installer gets our executable with --exe) and without the top-level
    config/stats.json (the installer sources it from _internal/config/stats.json, as upstream does);
  - _internal/config/templates/guide/1..7.png replaced by the Korean tutorial images (as in Global 2.3.0);
  - plus the one empty directory the official installer creates (_internal/PySide6/plugins/platforminputcontexts,
    an empty source folder of upstream's createallsubdirs line; the extractor does not create empty folders).
Every copied file is hashed again and compared with the manifest.  Nothing outside <stage dir> (and --report) is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SKIP = {"NTE_Drive_Calc.exe", "config/stats.json"}
GUIDE_REL = "_internal/config/templates/guide"
EMPTY_DIRS = ("_internal/PySide6/plugins/platforminputcontexts",)
EXPECTED_VERSION = "2.3.1"
EXPECTED_INSTALLER_SHA = "57a6f351d53a32c6f989335e1ea812cd55057e331902b5921343ad2d73428841"
EXPECTED_EXE_SHA = "5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("official", type=Path)
    parser.add_argument("guide", type=Path)
    parser.add_argument("stage", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    manifest = json.loads((args.official / "manifest.json").read_text(encoding="utf-8"))
    app = args.official / "app"
    stage = args.stage
    if manifest.get("app_version") != EXPECTED_VERSION or manifest.get("installer_sha256") != EXPECTED_INSTALLER_SHA:
        sys.exit(f"REFUSED: manifest is not the official {EXPECTED_VERSION} installer ({manifest.get('installer_sha256')})")
    files = {row["path"]: row for row in manifest["files"]}
    if files["NTE_Drive_Calc.exe"]["sha256"] != EXPECTED_EXE_SHA:
        sys.exit("REFUSED: manifest exe is not the official 2.3.1 executable")
    if stage.exists():
        sys.exit(f"REFUSED: {stage} exists - use a new folder")
    if "program files" in str(stage).lower():
        sys.exit("REFUSED: stage under Program Files")

    guide_files = sorted(p.name for p in args.guide.glob("*.png"))
    if guide_files != [f"{i}.png" for i in range(1, 8)]:
        sys.exit(f"REFUSED: expected 1.png .. 7.png in {args.guide}, found {guide_files}")
    guide_rows = {f"{GUIDE_REL}/{i}.png" for i in range(1, 8)}
    if not guide_rows <= set(files):
        sys.exit("REFUSED: the official manifest has no 7 tutorial images at " + GUIDE_REL)

    stage.mkdir(parents=True)
    copied = 0
    replaced = []
    for rel, row in sorted(files.items(), key=lambda item: item[0].lower()):
        if rel in SKIP:
            continue
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel in guide_rows:
            source = args.guide / Path(rel).name
            shutil.copyfile(source, target)
            replaced.append({"path": rel, "official_sha256": row["sha256"], "staged_sha256": sha256_of(target),
                             "size": target.stat().st_size})
            if replaced[-1]["staged_sha256"] == row["sha256"]:
                sys.exit(f"REFUSED: {source} is the official (Chinese) image, not the Korean one")
            continue
        source = app / rel
        shutil.copyfile(source, target)
        got = sha256_of(target)
        if got != row["sha256"] or target.stat().st_size != row["size"]:
            sys.exit(f"REFUSED: {rel} differs from the official manifest after copying ({got})")
        copied += 1
    for rel in EMPTY_DIRS:
        (stage / rel).mkdir(parents=True, exist_ok=True)

    extra_on_disk = []
    for path in app.rglob("*"):
        if path.is_file():
            rel = path.relative_to(app).as_posix()
            if rel not in files:
                extra_on_disk.append(rel)
    report = {
        "official_installer_sha256": manifest["installer_sha256"],
        "official_manifest_files": len(files),
        "staged_files": copied + len(replaced),
        "copied_identical": copied,
        "not_staged": sorted(SKIP),
        "replaced_tutorial_images": replaced,
        "empty_dirs": list(EMPTY_DIRS),
        "ignored_runtime_files_in_extraction_folder": sorted(extra_on_disk),
    }
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8", newline="\n")
    print(f"staged {report['staged_files']} files ({copied} identical to the official manifest, "
          f"{len(replaced)} tutorial images replaced); not staged: {sorted(SKIP)}; "
          f"ignored runtime files in the extraction folder: {len(extra_on_disk)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
