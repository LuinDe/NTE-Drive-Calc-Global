# build_tools

NTE Drive Calc Global의 실행 파일과 설치 프로그램을 만드는 스크립트입니다. 릴리스의 소스 zip에 들어 있는 `build_tools/`와 같은 파일입니다.

Scripts that produce the executable and the installer of NTE Drive Calc Global. They are the same files as `build_tools/` in the release's source zip.

All scripts need **Python 3.11** (the executable embeds `python311.dll`). Each script starts with a description of its arguments.

## Executable

The executable is not repackaged from scratch. `rebuild_exe_l10n.py` takes the official 2.3.0 `NTE_Drive_Calc.exe` (SHA-256 `505950ca2261902df6c78a61c3f17c6e756b82bb9309689ac08114c4f3a1cbbf`), replaces only the `src.*` modules in its PYZ archive with a compile of [`../src`](../src), and recomputes the PE checksum. Everything else stays byte for byte.

```powershell
python build_tools/rebuild_exe_l10n.py <official 2.3.0 NTE_Drive_Calc.exe> src <output exe>
python build_tools/verify_exe_l10n.py  <official 2.3.0 NTE_Drive_Calc.exe> <output exe> src
```

With CPython 3.11.15 (Windows x64) the output has the SHA-256 of the released executable, `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30`. Another 3.11.x may compress differently; `verify_exe_l10n.py` then shows that the content still matches the source.

| Script | What it does |
|---|---|
| `rebuild_exe_l10n.py` | Builds the executable from the official executable and the `src` tree. |
| `verify_exe_l10n.py` | Proves that a built executable differs from the official one only in the `src.*` PYZ records and the PE checksum, and that every `src.*` record equals a compile of the tree. |
| `audit_frozen_imports.py` | Static check that every import in the `src` tree can be resolved inside the packaged program (needs a copy of the official installation's `_internal` folder). |

## Installer

`build_installer_l10n.py` is a port of the original project's `build_installer.py`. It needs the rebuilt executable, a staged copy of the official 2.3.0 installation's `_internal` and `drivers` folders in which the seven tutorial images are replaced by the ones in [`../config/templates/guide`](../config/templates/guide) (`_internal/config/templates/guide`), and Inno Setup 6. The `release` variant uses the same application ID and default folder as the official installer; the `sandbox` variant installs without administrator rights under a separate identity for testing. Pass `--license LICENSE` (the licence file at the repository root); the script's default path points to the author's working folder and does not exist in this repository.

## Generators and helpers

| Script | What it does |
|---|---|
| `gen_team_form_actions.py` | Generates `src/services/team_form_actions.py` (transformation-state actions). |
| `gen_team_rotation_data.py` | Generates `src/services/team_rotation_data.py` (reviewed rotations). |
| `gen_team_custom_actions.py` | Generates `src/services/team_custom_actions.py` (action palette of the Custom Input mode). |
| `l10n_add_keys.py` | Lists `_L()` / `_LF()` keys that a language table lacks and merges translations into it. |

The three generators read the game's static database and research notes, which are not part of this repository or the source zip, and their default paths assume the author's working folder layout. They are included to show how the tables were made. To change a table, edit the generated file in `src/services/` directly; the program uses it as it is. The header "GENERATED FILE - DO NOT EDIT" in these three files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.
