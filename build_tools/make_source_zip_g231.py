"""Build the public source supplement ZIP from a Git tree (not complete native Corresponding Source).

Usage (Python 3.11): make_source_zip_g231.py <repo> <tree-ish> <out.zip>
    --version 2.3.6 --exe-sha256 <sha256> --date 2026-11-07T00:00:00

Files come from Git objects, sorted with fixed timestamps and deflate level 9.
Use the script/templates from the same tree. Source coverage and known missing
native source are documented in SOURCE_OFFER.md. No executable/DLL is packed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_installer_g231 as installer  # noqa: E402  (same folder; renders SOURCE_OFFER.txt)

PATHS = (
    "src", "build_tools", "config/templates/guide", "LICENSE", "NOTICE",
    "main.py", "pyproject.toml", "uv.lock", "build_exe.py", "build_installer.py",
    "tools", "native", "UPSTREAM_SOURCE_FILES.json", "license_records",
    "README.md", "README.zh.md", "README.en.md", "README.ja.md", "SOURCE_OFFER.md",
    "CHANGES.md", "docs",
)
# generic local-path markers; the builder adds personal ones (user / account names) with --forbid at run time,
# so that they are never written into the published sources themselves
FORBIDDEN_GENERIC = ("AppData" + "\\Local\\Temp", "AppData" + "/Local/Temp", "C:" + "\\Users\\", "C:" + "/Users/")
OFFICIAL_EXE_SHA256 = "5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3"

README = """\
NTE Drive Calc Global {global_version} — public source supplement
Original author: hxwd94666 and NTE Drive Calc contributors
Original project: {upstream_url}
Upstream baseline: {upstream_commit} (Calc {version})
Global maintainer/repository: LuinDe — {project_url}
Application EXE SHA-256: {exe_sha}

한국어: README.md, SOURCE_OFFER.md와 build_tools/README.md를 확인하세요.
中文：请参阅 README.zh.md、SOURCE_OFFER.md 和 build_tools/README.md。
English: see README.en.md, SOURCE_OFFER.md and build_tools/README.md.
日本語：README.ja.md、SOURCE_OFFER.md、build_tools/README.md を確認してください。

The archive includes modified application src/, restored public upstream
bootstrap/dependency/build/tools/prototype files, Global build/adaptation tools,
four-language documentation and preserved license records.
LICENSE/NOTICE retain their source paths; LICENSE.txt/NOTICE.txt are aliases.
SOURCE_OFFER.txt contains the corrected notice, not the old retained installer's
bytes. See docs/SOURCE_OFFER_CORRECTION_2.3.6.md.

Exact complete Corresponding Source for the distributed Core, analysis Core,
Loader and five capture DLLs is still missing. The native/ public C++ prototype
and resource patch scripts do not substitute for that source. Full game data and
some generator inputs are external requirements. This archive does not promise
a standalone source build of all installer components or complete compliance.
"""


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false", *args],
                          capture_output=True, check=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("treeish")
    parser.add_argument("out", type=Path)
    parser.add_argument("--exe-sha256", required=True)
    parser.add_argument("--date", default="2026-10-08T00:00:00", help="time stamp of every entry (local, no zone)")
    parser.add_argument("--version", default=installer.DEFAULT_VERSION)
    parser.add_argument("--forbid", action="append", default=[],
                        help="extra text that must not occur in any packed file (e.g. your user name); repeatable")
    args = parser.parse_args()
    forbidden = [s.encode("utf-8") for s in (*FORBIDDEN_GENERIC, *args.forbid)]

    stamp = dt.datetime.fromisoformat(args.date).timetuple()[:6]
    top = args.out.stem
    tar_bytes = git(args.repo, "archive", "--format=tar", args.treeish, "--", *PATHS)
    entries: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if Path(name).suffix.lower() in {".exe", ".dll", ".pyd", ".pyc", ".key"}:
                sys.exit(f"REFUSED: binary/private-key payload {name}")
            entries[f"{top}/{name}"] = tar.extractfile(member).read()
    for original in ("LICENSE", "NOTICE"):
        entries[f"{top}/{original}.txt"] = entries[f"{top}/{original}"]
    required_files = (
        "src/i18n_runtime.py", "build_tools/build_installer_g231.py", "LICENSE", "NOTICE",
        "config/templates/guide/7.png", "main.py", "pyproject.toml", "uv.lock",
        "build_exe.py", "build_installer.py", "UPSTREAM_SOURCE_FILES.json",
        "SOURCE_OFFER.md", "docs/SOURCE_OFFER_CORRECTION_2.3.6.md", "license_records/manifest.json",
        "README.md", "README.zh.md", "README.en.md", "README.ja.md",
    )
    for required in required_files:
        if f"{top}/{required}" not in entries:
            sys.exit(f"REFUSED: {required} is not in {args.treeish}")
    provenance = json.loads(entries[f"{top}/UPSTREAM_SOURCE_FILES.json"])
    for record in provenance["files"]:
        data = entries.get(f"{top}/{record['path']}")
        if data is None or hashlib.sha256(data).hexdigest() != record.get("published_sha256", record["sha256"]):
            sys.exit(f"REFUSED: restored source missing or changed: {record['path']}")

    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in entries[f"{top}/LICENSE.txt"][:600].decode("utf-8", "replace"):
        sys.exit("REFUSED: LICENSE is not the AGPL text")

    zip_name = args.out.name
    offer = installer.render_source_offer(version=args.version, exe_sha256=args.exe_sha256, source_zip_name=zip_name)
    entries[f"{top}/SOURCE_OFFER.txt"] = offer.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
    installer.parse_global_version(args.version)            # BuildError for a non-Global version
    readme = README.format(global_version=args.version, version=installer.UPSTREAM_BASE, upstream_url=installer.UPSTREAM_URL,
                           upstream_commit=installer.UPSTREAM_COMMIT, project_url=installer.PROJECT_URL,
                           official_sha=OFFICIAL_EXE_SHA256, exe_sha=args.exe_sha256)
    entries[f"{top}/README_SOURCE.txt"] = readme.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")

    bad = [(name, needle.decode("utf-8")) for name, data in entries.items() for needle in forbidden if needle in data]
    if bad:
        sys.exit(f"REFUSED: local user path / account name found in {bad[:10]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            archive.writestr(info, entries[name], compresslevel=9)
    with zipfile.ZipFile(args.out) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    src_count = sum(1 for n in names if n.startswith(f"{top}/src/"))
    print(f"wrote {args.out}")
    print(f"tree-ish {args.treeish}; entries {len(names)} (src {src_count}, "
          f"build_tools {sum(1 for n in names if n.startswith(f'{top}/build_tools/'))})")
    print(f"uncompressed {sum(len(d) for d in entries.values()):,} bytes, zip {args.out.stat().st_size:,} bytes")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
