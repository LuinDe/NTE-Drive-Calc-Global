# build_tools

For Global 2.3.3, make the stage before verifying the executable. Pass the staged `_internal/data` as the fourth positional argument to verify_exe_l10n_g231.py. The release installer gate checks that staged database. [CN 1.5.4 Elyms data, sources and tests](ELYMS.md).

NTE Drive Calc Global의 실행 파일과 설치 프로그램을 만드는 스크립트입니다. 릴리스의 소스 zip에 들어 있는 `build_tools/`와 같은 파일입니다.

Scripts that produce the executable, the installer and the source zip of NTE Drive Calc Global 2.3.1. They are the same files as `build_tools/` in the release's source zip.

All scripts need **Python 3.11** (the executable embeds `python311.dll`). Each script starts with a description of its arguments.

## Executable

The executable is not repackaged from scratch. `rebuild_exe_l10n.py` takes the official 2.3.1 `NTE_Drive_Calc.exe` (SHA-256 `5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3`, installed by the original project's `NTE_Drive_Calc_Setup_2.3.1.exe`), replaces only the `src.*` modules in its PYZ archive with a compile of [`../src`](../src), and recomputes the PE checksum. Everything else stays byte for byte.

```powershell
python build_tools/rebuild_exe_l10n.py      <official 2.3.1 NTE_Drive_Calc.exe> src <output exe>
python build_tools/verify_exe_l10n_g231.py  <official 2.3.1 NTE_Drive_Calc.exe> <output exe> src [<official _internal\data>]
```

With CPython 3.11.15 (Windows x64) a build of the `v2.3.1-global.1` tree (tag `v2.3.1-global.1`, with the tools of that tag) has the SHA-256 of that release's executable, `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`. Later trees give their own hash (listed in each release). Another 3.11.x may compress differently; `verify_exe_l10n_g231.py` then shows that the content still matches the source.

From `2.3.2` the tree no longer contains the original project's two update modules; both commands then name them (any other missing module still stops the build):

```powershell
python build_tools/rebuild_exe_l10n.py      <official exe> src <output exe> --remove=src.features.settings.updates --remove=src.ui.controllers.update_controller
python build_tools/verify_exe_l10n_g231.py  <official exe> <output exe> src --removed=src.features.settings.updates --removed=src.ui.controllers.update_controller
```

| Script | What it does |
|---|---|
| `rebuild_exe_l10n.py` | Builds the executable from the official executable and the `src` tree. A rebuild from the unmodified upstream `src` (commit `0e7a6b4`) keeps all 893 original `src.*` records. |
| `verify_exe_l10n_g231.py` | Proves that a built executable differs from the official one only in the `src.*` PYZ records and the PE checksum, that every `src.*` record equals a compile of the tree, and (check 8) that the precomputed rows of the arc and awakening efficiency tables were made from the game database the official 2.3.1 ships. |
| `audit_frozen_imports.py` | Static check that every import in the `src` tree can be resolved inside the packaged program (needs a copy of the official installation's `_internal` folder; pass `--baseline-src` = the upstream `src` of commit `0e7a6b4`). |

## Installer

| Script | What it does |
|---|---|
| `inno_extract.py` | Read-only extractor for Inno Setup 6.7 installers. It unpacks the official `NTE_Drive_Calc_Setup_2.3.1.exe` without running it and checks the SHA-256 of every file against the installer's own records (`--manifest` writes the file list). |
| `make_stage_g231.py` | Builds the installer stage from that extraction: exactly the files of the official 2.3.1 installation, without the main executable, with the seven tutorial images replaced by the ones in [`../config/templates/guide`](../config/templates/guide). |
| `build_installer_g231.py` | A port of the original project's `build_installer.py` (commit `0e7a6b4`). Same `[Files]` / `[InstallDelete]` / `[Dirs]` structure as the official 2.3.1 installer; with the 2.3.1 component layout (`native-plugins-v3`) the old `dwmapi.dll` is not deleted, as upstream. The `release` variant uses the official application ID, default folder and privileges; the `sandbox` variant installs without administrator rights under a separate test identity. Needs Inno Setup 6 (the release was built with 6.7.3). |
| `make_source_zip_g231.py` | Makes the source zip from a git commit (`git archive`, fixed time stamps, sorted entries), so the same commit always gives the same zip. It refuses to pack a file that contains a local user path. |

Reproducing **v2.3.1-global.1** (check out the tag `v2.3.1-global.1` first: these are the tools and file names of that release; the tools on `main` have since changed):

```powershell
python build_tools/inno_extract.py NTE_Drive_Calc_Setup_2.3.1.exe official231 --json official231/inno_entries.json --manifest official231/manifest.json
python build_tools/make_stage_g231.py official231 config/templates/guide stage
python build_tools/build_installer_g231.py --stage stage --write-stage-manifest
python build_tools/build_installer_g231.py --exe <built exe> --stage stage --out out --variant release --output-base NTE_Drive_Calc_2.3.1_Multilingual_Setup --source-zip-name NTE_Drive_Calc_2.3.1_Multilingual_source.zip --aux-dir build
python build_tools/make_source_zip_g231.py . <commit> NTE_Drive_Calc_2.3.1_Multilingual_source.zip --exe-sha256 76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0 --date 2026-10-11T00:00:00
```

From **v2.3.2** (the tools on `main`; `<version>` = e.g. `2.3.2`; the asset names carry the full version; v2.3.1-global.2 is reproduced with the tools of its own tag):

```powershell
python build_tools/build_installer_g231.py --exe <built exe> --stage stage --out out --variant release --version <version> --tree . --official-exe <official 2.3.1 NTE_Drive_Calc.exe> --notes RELEASE_NOTES_<version>.md --emit-manifest --aux-dir build
python build_tools/make_source_zip_g231.py . <commit> NTE_Drive_Calc_<version>_Multilingual_source.zip --version <version> --exe-sha256 <exe sha256> --date <date>
```

The installer's compiled bytes depend on the Inno Setup version and on the build time, so a rebuilt installer has another SHA-256 even from identical inputs; the files it installs are the same. The `--aux-dir` folder contains local paths (the generated `setup.iss`, logs): do not publish it.

## In-app update releases (from 2.3.2)

From `2.3.2` the program updates itself from the GitHub Releases of **this repository only**
(`LuinDe/NTE-Drive-Calc-Global`); the original project's update channel is not used. Version numbers are Global's own:
tags `v<major>.<minor>.<patch>` (`src/app/global_release.py` `GLOBAL_VERSION`; the releases before 2.3.2 carry a
`-global.<n>` suffix, which is still read: versions are compared as (major, minor, patch, n) with n = 0 for a
plain version, so 2.3.1-global.2 < 2.3.2 < 2.3.3), compared by that grammar only; drafts and prereleases are ignored. The program offers a release only when all of these hold: the tag is newer
than the running build, the release is by `LuinDe`, it has exactly these assets at their `github.com/LuinDe/NTE-Drive-Calc-Global/releases/download/<tag>/` URLs,
GitHub reports a SHA-256 `digest` for each, and the manifest is signed by a pinned Ed25519 key. The signature is
checked **before** the program announces anything (an unsigned or tampered release is never shown), and the release
notes are shown only when their SHA-256 is the one signed in the manifest (otherwise the program shows "see the
releases page" instead of the body). Setup then runs silently **with administrator rights**: whoever holds the
signing key can run code on every PC that updates, so keep the key offline and protected by its passphrase.

| Asset (example for `v2.3.2`) | Made by |
|---|---|
| `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` | `build_installer_g231.py --variant release --version 2.3.2 --tree . --official-exe <official exe> --notes <body .md> --emit-manifest` |
| `NTE_Drive_Calc_2.3.2_Multilingual_source.zip` | `make_source_zip_g231.py` |
| `NTE_Drive_Calc_2.3.2_release.json` | `--emit-manifest` (binds tag, installer name, size, SHA-256, executable SHA-256 and the SHA-256 of the release notes) |
| `NTE_Drive_Calc_2.3.2_release.json.sig` | `ssh-keygen -Y sign` (below) |

### Release-signing key (once, by the maintainer, interactively)

```powershell
ssh-keygen -t ed25519 -f %USERPROFILE%\.ssh\nte_global_release -C nte-global-release
```

Type a passphrase. The private key never goes into a repository, a build folder or a chat; keep an offline backup.
Then pin the **public** key into the tree (the script reads only `nte_global_release.pub` and refuses test keys):

```powershell
python build_tools/pin_release_key.py .            # writes RELEASE_SIGNING_KEYS in src/app/global_release.py
python build_tools/pin_release_key.py . --check    # exit 0 = the tree pins exactly that key
```

### Every release

1. Bump `GLOBAL_VERSION` in `src/app/global_release.py`; `pin_release_key.py . --check` must pass. Write the release
   body first (`RELEASE_NOTES_<version>.md`, with the four sections of step 6): it is signed with the manifest, so
   publish exactly this text (a later edit of the body on GitHub makes the program hide the notes until a new
   manifest is signed).
2. Build and verify the executable. The tree no longer has upstream's update modules, so they are dropped on purpose:
   `rebuild_exe_l10n.py <official exe> src <out exe> --remove=src.features.settings.updates --remove=src.ui.controllers.update_controller`
   then `verify_exe_l10n_g231.py <official exe> <out exe> src --removed=src.features.settings.updates --removed=src.ui.controllers.update_controller`
3. Build the installer with `--variant release --version <version> --tree . --official-exe <official exe> --notes RELEASE_NOTES_<version>.md --emit-manifest`.
   **Release gate:** the build stops before Inno Setup runs when `%USERPROFILE%\.ssh\nte_global_release.pub` is
   absent, names a test key, or is not the key the tree pins; when any pinned slot is a known test key
   (`--reject-key <test .pub>` adds more); when the tree contains a test hook (`NTE_GUP_` / `NTE_SMOKE_`); or when
   `--exe` was not built from `--tree` (it runs `verify_exe_l10n_g231.py` against `--official-exe`).
4. Sign the manifest (you type the passphrase):

   ```powershell
   ssh-keygen -Y sign -f %USERPROFILE%\.ssh\nte_global_release -n nte-drive-calc-global-release NTE_Drive_Calc_<version>_release.json
   ```

   (`verify_release_manifest.py --sign-command <manifest>` prints this line for a given file.)
5. Verify with two independent verifiers - OpenSSH and the program's own pure-Python Ed25519/sshsig code:

   ```powershell
   python build_tools/verify_release_manifest.py --local <folder with the installer, manifest and .sig> --tree . --notes RELEASE_NOTES_<version>.md
   ```

   OpenSSH alone (`allowed_signers` holds one line:
   `nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAA...`):

   ```powershell
   ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_<version>_release.json.sig < NTE_Drive_Calc_<version>_release.json
   ```
6. `gh release create v<version> --draft ...` and upload the four assets (never `--clobber`, never move a tag; a mistake
   becomes a new, higher version, for example `2.3.3`). The body needs the four sections `## 한국어`, `## English`, `## 日本語`, `## 中文` (the
   program shows the one of the user's language).
7. When GitHub shows a `digest` for every asset: `verify_release_manifest.py --github v<version> --tree . --draft` → `OK`
   (runs the program's own release selection on the real API answer, verifies the downloaded files and compares the
   body GitHub serves with the signed notes digest).
8. Publish, enable **Settings → Releases → Immutable releases**, and run `verify_release_manifest.py --github v<version> --tree .` once more
   (published: also the program's own check-time verification, which must announce the release with verified notes).

| Script | What it does |
|---|---|
| `pin_release_key.py` | Pins the release public key into `src/app/global_release.py`; `--check` is the release gate for the tree. |
| `verify_release_manifest.py` | Verifies a signed release with `ssh-keygen -Y verify` and the program's verifier (`--local`), or a draft / published GitHub release end to end (`--github`). |

## Generators

| Script | What it does |
|---|---|
| `gen_arc_efficiency_data.py` | Generates `src/services/arc_efficiency_data.py`, the precomputed rows of the Arc Efficiency table. The rows are computed by `src/services/arc_efficiency_service.py`, the same code the program runs when the rows do not match its data, so a precomputed row and a row computed on your PC cannot differ. `--check` rebuilds in memory and compares. Needs a source-run environment (the official `_internal` runtime, the game database). |
| `gen_awakening_efficiency_data.py` | Generates `src/services/awakening_efficiency_data.py`, the precomputed rows of the character awakening (돌파) efficiency table, with `src/services/awakening_efficiency_service.py` (the code the program runs when the rows do not match its data); same environment and `--write` / `--check` as the arc generator; run it after the arc generator. |
| `gen_team_form_actions.py` | Generates `src/services/team_form_actions.py` (transformation-state actions). |
| `gen_team_rotation_data.py` | Generates `src/services/team_rotation_data.py` (reviewed rotations). |
| `gen_team_custom_actions.py` | Generates `src/services/team_custom_actions.py` (action palette of the Custom Input mode). |
| `gen_team_resource_data.py` | Generates `src/services/team_resource_data.py` (ultimate energy per hit, Esper-Cycle gauge, cooldowns with source and confidence per value) from four reviewed research data chunks that are not in this repository; `--check` compares. `g231_shims/gen_team_resource_data.py` runs it against the 2.3.1 tree. |
| `gen_puka_training_data.py` | Generates `src/services/puka_training_data.py` (Puka Boot Camp level table) from [`data/puka_training_levels.json`](data/puka_training_levels.json) (values per level with their public sources); `--check` compares. |
| `audit_rotations.py`, `make_collect_plan.py`, `i18n_resource_keys.py` | Research helpers of the team-simulation resource model (rotation audit, the plan for collecting missing values from recordings, the translation keys of its texts). Like the team generators they read inputs that are not in this repository. |
| `g231_shims/` | Wrappers that run the three team generators against the 2.3.1 tree. `g231_shims/gen_team_rotation_data.py` also applies the Korean term 援护技 = 서포트 스킬 to the step tooltips. |
| `l10n_add_keys.py` | Lists `_L()` / `_LF()` keys that a language table lacks and merges translations into it. |

The team generators read the game's static database and research notes, which are not part of this repository or the source zip, and their default paths assume the author's working folder layout. They are included to show how the tables were made. To change one of the team tables, edit the generated file in `src/services/` directly; the program uses it as it is. The header "GENERATED FILE - DO NOT EDIT" in these files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.

The Arc Efficiency and awakening (돌파) efficiency rows are different: the program checks them against its game data and the calculation code, and recomputes on your PC when they do not match. Edit the calculation (`arc_efficiency_service.py`, `awakening_efficiency_service.py`, `team_fork_corrections.py`, `awakening_node_rules/`) rather than the rows, and regenerate them with `gen_arc_efficiency_data.py --write` and then `gen_awakening_efficiency_data.py --write`.
