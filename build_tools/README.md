# build_tools

NTE Drive Calc Global의 실행 파일과 설치 프로그램을 만드는 스크립트입니다. 릴리스의 소스 zip에 들어 있는 `build_tools/`와 같은 파일입니다.

Scripts that produce the executable, the installer and the source zip of NTE Drive Calc Global 2.3.1. They are the same files as `build_tools/` in the release's source zip.

All scripts need **Python 3.11** (the executable embeds `python311.dll`). Each script starts with a description of its arguments.

## Executable

The executable is not repackaged from scratch. `rebuild_exe_l10n.py` takes the official 2.3.1 `NTE_Drive_Calc.exe` (SHA-256 `5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3`, installed by the original project's `NTE_Drive_Calc_Setup_2.3.1.exe`), replaces only the `src.*` modules in its PYZ archive with a compile of [`../src`](../src), and recomputes the PE checksum. Everything else stays byte for byte.

```powershell
python build_tools/rebuild_exe_l10n.py      <official 2.3.1 NTE_Drive_Calc.exe> src <output exe>
python build_tools/verify_exe_l10n_g231.py  <official 2.3.1 NTE_Drive_Calc.exe> <output exe> src [<official _internal\data>]
```

With CPython 3.11.15 (Windows x64) the output has the SHA-256 of the released executable, `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`. Another 3.11.x may compress differently; `verify_exe_l10n_g231.py` then shows that the content still matches the source.

| Script | What it does |
|---|---|
| `rebuild_exe_l10n.py` | Builds the executable from the official executable and the `src` tree. A rebuild from the unmodified upstream `src` (commit `0e7a6b4`) keeps all 893 original `src.*` records. |
| `verify_exe_l10n_g231.py` | Proves that a built executable differs from the official one only in the `src.*` PYZ records and the PE checksum, that every `src.*` record equals a compile of the tree, and (check 8) that the efficiency table's precomputed rows were made from the game database the official 2.3.1 ships. |
| `audit_frozen_imports.py` | Static check that every import in the `src` tree can be resolved inside the packaged program (needs a copy of the official installation's `_internal` folder; pass `--baseline-src` = the upstream `src` of commit `0e7a6b4`). |

## Installer

| Script | What it does |
|---|---|
| `inno_extract.py` | Read-only extractor for Inno Setup 6.7 installers. It unpacks the official `NTE_Drive_Calc_Setup_2.3.1.exe` without running it and checks the SHA-256 of every file against the installer's own records (`--manifest` writes the file list). |
| `make_stage_g231.py` | Builds the installer stage from that extraction: exactly the files of the official 2.3.1 installation, without the main executable, with the seven tutorial images replaced by the ones in [`../config/templates/guide`](../config/templates/guide). |
| `build_installer_g231.py` | A port of the original project's `build_installer.py` (commit `0e7a6b4`). Same `[Files]` / `[InstallDelete]` / `[Dirs]` structure as the official 2.3.1 installer; with the 2.3.1 component layout (`native-plugins-v3`) the old `dwmapi.dll` is not deleted, as upstream. The `release` variant uses the official application ID, default folder and privileges; the `sandbox` variant installs without administrator rights under a separate test identity. Needs Inno Setup 6 (the release was built with 6.7.3). |
| `make_source_zip_g231.py` | Makes the source zip from a git commit (`git archive`, fixed time stamps, sorted entries), so the same commit always gives the same zip. It refuses to pack a file that contains a local user path. |

```powershell
python build_tools/inno_extract.py NTE_Drive_Calc_Setup_2.3.1.exe official231 --json official231/inno_entries.json --manifest official231/manifest.json
python build_tools/make_stage_g231.py official231 config/templates/guide stage
python build_tools/build_installer_g231.py --stage stage --write-stage-manifest
python build_tools/build_installer_g231.py --exe <built exe> --stage stage --out out --variant release --output-base NTE_Drive_Calc_2.3.1_Multilingual_Setup --source-zip-name NTE_Drive_Calc_2.3.1_Multilingual_source.zip --aux-dir build
python build_tools/make_source_zip_g231.py . <commit> NTE_Drive_Calc_2.3.1_Multilingual_source.zip --exe-sha256 76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0 --date 2026-10-11T00:00:00
```

The installer's compiled bytes depend on the Inno Setup version and on the build time, so a rebuilt installer has another SHA-256 even from identical inputs; the files it installs are the same. The `--aux-dir` folder contains local paths (the generated `setup.iss`, logs): do not publish it.

## Generators

| Script | What it does |
|---|---|
| `gen_arc_efficiency_data.py` | Generates `src/services/arc_efficiency_data.py`, the precomputed rows of the Arc Efficiency table. The rows are computed by `src/services/arc_efficiency_service.py`, the same code the program runs when the rows do not match its data, so a precomputed row and a row computed on your PC cannot differ. `--check` rebuilds in memory and compares. Needs a source-run environment (the official `_internal` runtime, the game database). |
| `gen_team_form_actions.py` | Generates `src/services/team_form_actions.py` (transformation-state actions). |
| `gen_team_rotation_data.py` | Generates `src/services/team_rotation_data.py` (reviewed rotations). |
| `gen_team_custom_actions.py` | Generates `src/services/team_custom_actions.py` (action palette of the Custom Input mode). |
| `g231_shims/` | Wrappers that run the three team generators against the 2.3.1 tree. `g231_shims/gen_team_rotation_data.py` also applies the Korean term 援护技 = 서포트 스킬 to the step tooltips. |
| `l10n_add_keys.py` | Lists `_L()` / `_LF()` keys that a language table lacks and merges translations into it. |

The team generators read the game's static database and research notes, which are not part of this repository or the source zip, and their default paths assume the author's working folder layout. They are included to show how the tables were made. To change one of the three team tables, edit the generated file in `src/services/` directly; the program uses it as it is. The header "GENERATED FILE - DO NOT EDIT" in these files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.

The Arc Efficiency rows are different: the program checks them against its game data and the calculation code, and recomputes on your PC when they do not match. Edit the calculation (`arc_efficiency_service.py`, `team_fork_corrections.py`) rather than the rows, and regenerate them with `gen_arc_efficiency_data.py --write`.
