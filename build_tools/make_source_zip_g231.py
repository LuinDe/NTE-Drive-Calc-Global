"""Build the corresponding-source zip of NTE Drive Calc Global from a git tree-ish (reproducible).

usage (Python 3.11):
    make_source_zip_g231.py <repository> <tree-ish> <out zip> --exe-sha256 <sha> [--date 2026-10-08T00:00:00]
                            [--forbid <text> ...]

The zip is made from git objects only (`git -c core.autocrlf=false archive <tree-ish>`), never from a working tree,
so the same commit always gives the same files.  Every entry gets the fixed --date as its time stamp, entries are
sorted, and compression is deflate level 9: building it again from the same commit (with the same zlib, e.g. CPython
3.11.15 on Windows) gives a byte-identical zip.  The commit of a release and the tree that was staged just before
that commit give the same zip, because only the paths below are packed and the documentation that names the zip's
hash is not among them.

Layout (one top folder named after the zip):
  src/**                       the complete modified source tree of the executable
  build_tools/**               the scripts that build the executable / installer and the table generators
  config/templates/guide/*.png the Korean tutorial images the installer ships
  LICENSE.txt                  GNU AGPL-3.0, the repository's LICENSE (= the original project's LICENSE)
  NOTICE.txt                   the repository's NOTICE (original NOTICE + modification notice)
  SOURCE_OFFER.txt             the same bytes as {app}\\l10n_build\\SOURCE_OFFER.txt of the installer
  README_SOURCE.txt            what this is and how the executable / installer are built from it
Refuses to pack a file that contains a local user path or account name.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_installer_g231 as installer  # noqa: E402  (same folder; renders SOURCE_OFFER.txt)

PATHS = ("src", "build_tools", "config/templates/guide", "LICENSE", "NOTICE")
RENAME = {"LICENSE": "LICENSE.txt", "NOTICE": "NOTICE.txt"}
# generic local-path markers; the builder adds personal ones (user / account names) with --forbid at run time,
# so that they are never written into the published sources themselves
FORBIDDEN_GENERIC = ("AppData" + "\\Local\\Temp", "AppData" + "/Local/Temp", "C:" + "\\Users\\", "C:" + "/Users/")
OFFICIAL_EXE_SHA256 = "5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3"

README = """\
NTE Drive Calc {version} 다국어판 "NTE Drive Calc Global" (비공식 빌드) - 소스 코드
NTE Drive Calc {version} Multilingual Edition "NTE Drive Calc Global" (unofficial build) - source code
====================================================================================================

[한국어]
이 zip 은 NTE Drive Calc {version} 의 비공식 다국어판 NTE Drive Calc Global(한국어 / English / 日本語 / 简体中文)의
대응 소스 코드입니다. 원 프로그램은 GNU AGPL-3.0 으로 배포되며(LICENSE.txt, NOTICE.txt), 이 빌드는 그 파생물입니다.
원저작자: NTE Drive Calc contributors (hxwd94666). 원 프로젝트: {upstream_url}
기반 커밋: {upstream_commit} (공식 {version})
이 빌드의 저장소: {project_url} (이 zip 은 그 저장소의 커밋에서 git archive 로 만든 것입니다)

구성
  src/                        수정된 전체 파이썬 소스 트리. 실행 파일의 src.* 모듈은 전부 여기서 컴파일됩니다.
  build_tools/                실행 파일과 설치 프로그램을 만드는 스크립트, 자동 생성 표의 생성기 (build_tools/README.md)
  config/templates/guide/     한국어판 튜토리얼 이미지 7장 (설치 프로그램에 들어 있는 것과 같은 파일)
  LICENSE.txt                 GNU AGPL-3.0 전문 (원 프로젝트의 LICENSE 그대로)
  NOTICE.txt                  원 프로젝트의 NOTICE + 수정 고지
  SOURCE_OFFER.txt            설치 폴더의 l10n_build\\SOURCE_OFFER.txt 와 같은 파일

원 프로젝트와 다른 점은 저장소의 README.md 와 CHANGES.md 에 파일 단위로 정리되어 있습니다. 요약:
  - 화면 문자열의 다국어화(중국어 원문이 키, src/i18n_runtime.py; 번역 표 src/i18n_data_{{ko,en,ja}}.py, 표시 계층
    src/i18n_display.py, src/i18n_desc.py), 프로그램 안에서 언어 전환
  - 팀 시뮬레이션(Beta): src/features/team_simulation/, src/services/team_*.py
  - 아크 효율표(Beta): src/features/arc_efficiency/, src/services/arc_efficiency_*.py
  - 전투 리포트 "내 캐릭터로 비교": src/features/battle_report/my_build_comparison.py,
    src/services/battle_import_comparison_service.py
  - 게임 폴더 보호(이 프로그램 것으로 확인되지 않는 d3d12.dll 등은 덮어쓰거나 지우지 않음)
  src/ 밖의 원 프로젝트 파일(main.py, 빌드 스크립트, assets, data, 네이티브 구성 요소, third_party 등)은 바꾸지
  않았으므로 위 커밋의 원 프로젝트 저장소에 있는 것과 같습니다.

실행 파일을 만드는 방법 (Python 3.11 필요: 실행 파일이 python311.dll 을 내장)
  python build_tools/rebuild_exe_l10n.py <공식 {version} NTE_Drive_Calc.exe> src <출력 exe>
  python build_tools/verify_exe_l10n_g231.py <공식 {version} NTE_Drive_Calc.exe> <출력 exe> src
  공식 PyInstaller 실행 파일의 PYZ 아카이브에서 src.* 모듈만 이 소스를 컴파일한 것으로 바꾸고, 나머지는 바이트
  단위로 그대로 둡니다. 기준 공식 실행 파일의 SHA-256 은
      {official_sha}
  이고, CPython 3.11.15 (Windows x64) 로 빌드하면 결과물의 SHA-256 은 배포된 실행 파일과 같습니다:
      {exe_sha}
  다른 3.11.x 에서는 압축 결과가 달라 해시가 다를 수 있습니다. 그때는 verify_exe_l10n_g231.py 가 내용이 이 소스와
  일치하는지 확인해 줍니다.
  설치 프로그램: build_tools/make_stage_g231.py 로 공식 {version} 설치본의 파일(공식 설치 프로그램에서 추출)과
  튜토리얼 이미지로 스테이지를 만들고, build_tools/build_installer_g231.py 로 만듭니다(Inno Setup 6 필요).
  이 zip 은 build_tools/make_source_zip_g231.py 로 만듭니다. 자세한 사용법은 각 스크립트 첫머리에 있습니다.

자동 생성 모듈
  src/services/team_rotation_data.py, team_form_actions.py, team_custom_actions.py, arc_efficiency_data.py 는
  build_tools 의 생성기가 게임 데이터와 조사 자료에서 만든 표입니다. 생성기의 입력 자료(게임 정적 DB, 조사 노트)
  일부는 이 zip 에 들어 있지 않습니다. 표를 고쳐야 하면 생성된 파일을 직접 고쳐도 프로그램은 그대로 동작합니다
  (아크 효율표는 표가 데이터와 맞지 않으면 실행 중에 다시 계산합니다).

[English]
This zip is the corresponding source code of NTE Drive Calc Global, the unofficial multilingual edition (Korean /
English / Japanese / Simplified Chinese) of NTE Drive Calc {version}. The original program is distributed under the
GNU AGPL-3.0 (LICENSE.txt, NOTICE.txt); this build is a derivative work of it.
Original authors: NTE Drive Calc contributors (hxwd94666). Original project: {upstream_url}
Based on commit: {upstream_commit} (official {version})
Repository of this build: {project_url} (this zip is made with git archive from a commit of that repository)

Contents
  src/                        the complete modified Python source tree; every src.* module of the executable is
                              compiled from it
  build_tools/                the scripts that build the executable and the installer, and the generators of the
                              generated tables (build_tools/README.md)
  config/templates/guide/     the 7 Korean tutorial images (the same files the installer contains)
  LICENSE.txt                 full text of the GNU AGPL-3.0 (the original project's LICENSE, verbatim)
  NOTICE.txt                  the original project's NOTICE plus the modification notice
  SOURCE_OFFER.txt            the same file as l10n_build\\SOURCE_OFFER.txt in the installation folder

The differences from the original project are listed file by file in README.md and CHANGES.md of the repository.
In short:
  - localisation of the interface (the Chinese source text is the key, src/i18n_runtime.py; tables
    src/i18n_data_{{ko,en,ja}}.py; display layer src/i18n_display.py, src/i18n_desc.py), in-app language switching
  - Team Simulation (Beta): src/features/team_simulation/, src/services/team_*.py
  - Arc Efficiency table (Beta): src/features/arc_efficiency/, src/services/arc_efficiency_*.py
  - Battle report "Compare with My Characters": src/features/battle_report/my_build_comparison.py,
    src/services/battle_import_comparison_service.py
  - game-folder protection (a d3d12.dll or other file that cannot be identified as this program's is never
    overwritten or deleted)
  All other files of the original project outside src/ (main.py, build scripts, assets, data, native components,
  third_party ...) are unchanged and therefore identical to the original repository at the commit above.

Building the executable (Python 3.11 required: the executable embeds python311.dll)
  python build_tools/rebuild_exe_l10n.py <official {version} NTE_Drive_Calc.exe> src <output exe>
  python build_tools/verify_exe_l10n_g231.py <official {version} NTE_Drive_Calc.exe> <output exe> src
  Only the src.* modules in the PYZ archive of the official PyInstaller executable are replaced by a compile of this
  tree; everything else is kept byte for byte. The official executable used as the base has the SHA-256
      {official_sha}
  and a build with CPython 3.11.15 (Windows x64) has the SHA-256 of the distributed executable:
      {exe_sha}
  Another 3.11.x may compress differently and give another hash; verify_exe_l10n_g231.py then confirms that the
  content matches this source.
  The installer: build_tools/make_stage_g231.py stages the files of the official {version} installation (extracted from
  the official installer) and the tutorial images, then build_tools/build_installer_g231.py builds it (Inno Setup 6).
  This zip is made by build_tools/make_source_zip_g231.py. Each script starts with its usage.

Generated modules
  src/services/team_rotation_data.py, team_form_actions.py, team_custom_actions.py and arc_efficiency_data.py are
  tables generated by the generators in build_tools from game data and research notes. Some generator inputs (the
  game's static database, research notes) are not part of this zip. The generated files can be edited directly; the
  program uses them as they are (the arc efficiency table is recomputed at run time when it does not match the data).
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
            name = RENAME.get(member.name, member.name)
            entries[f"{top}/{name}"] = tar.extractfile(member).read()
    for required in ("src/i18n_runtime.py", "build_tools/build_installer_g231.py", "LICENSE.txt", "NOTICE.txt",
                     "config/templates/guide/7.png"):
        if f"{top}/{required}" not in entries:
            sys.exit(f"REFUSED: {required} is not in {args.treeish}")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in entries[f"{top}/LICENSE.txt"][:600].decode("utf-8", "replace"):
        sys.exit("REFUSED: LICENSE is not the AGPL text")

    zip_name = args.out.name
    offer = installer.render_source_offer(version=args.version, exe_sha256=args.exe_sha256, source_zip_name=zip_name)
    entries[f"{top}/SOURCE_OFFER.txt"] = offer.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
    readme = README.format(version=args.version, upstream_url=installer.UPSTREAM_URL,
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
