# Global 2.3.6 소스와 빌드 / Source and build guide

[한국어](../README.md) · [中文](../README.zh.md) · [English](../README.en.md) · [日本語](../README.ja.md)

한국어: 공개 원본 진입점·의존성·빌드 도구를 복원했지만, 배포된 모든 Core·DLL의 전체 대응 소스가 확보된 것은 아닙니다. 아래 절차는 원본 바이너리와 게임 자료를 입력으로 사용하는 Global 재조립 절차입니다. [소스 제공 범위](../SOURCE_OFFER.md)를 먼저 확인하세요.

中文：已恢复公开入口、依赖和构建工具，但尚未取得全部 Core/DLL 的完整对应源码。下列流程仍依赖原版二进制及游戏资料，详见[源码范围](../SOURCE_OFFER.md)。

English: restored public bootstrap, dependency and build files do not resolve all native Corresponding Source gaps. The procedure below adapts an existing upstream binary distribution and requires external game materials. See [source coverage](../SOURCE_OFFER.md).

日本語：公開の入口・依存・ビルド情報を復元しましたが、全 Core/DLL の完全な対応ソースは未確保です。以下は原版バイナリとゲーム資料を入力にする手順です。[公開範囲](../SOURCE_OFFER.md)を確認してください。

## Provenance and prerequisites

- Original author: **[WuDu / hxwd94666](https://github.com/hxwd94666) and NTE Drive Calc contributors**.
- Original source: https://github.com/hxwd94666/NTE-Drive-Calculator
- Upstream baseline: `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` (Calc 2.3.1).
- [UPSTREAM_SOURCE_FILES.json](../UPSTREAM_SOURCE_FILES.json) lists 121 restored public files and hashes. Original `pyproject.toml` metadata (including upstream maintainer and URLs) is preserved as provenance; **Global is maintained by LuinDe**, not WuDu. `uv.lock` is the original dependency lock.
- `main.py` is the public upstream entry point. Root `build_exe.py` and `build_installer.py` are upstream build tools and expect assets/data/third_party payloads that are not fully in this source package. Use the Global tools below for the retained build workflow.
- `native/counterfactual-core` is the public C++ prototype, not the shipped private Rust analysis Core.
- Windows x64, CPython 3.11 (historical builds used 3.11.15), the appropriate Python dependencies and Inno Setup 6 are required. Do not infer a standalone full build from the restored metadata alone.

## Retained artifacts and external inputs

The 2026-11-07 supplement does not rebuild the installer or modify application `src/`. The original v2.3.6 tag remains at `5d3522a37bd35ef094721cf17b91f36ed9c6cb94`. Its executable SHA-256 is `3743845cb74a5ed7e175464386d4411fd32bda611cec5fd9a8570ea31a623115`.

The adaptation workflow requires the lawful original 2.3.1 installer/payload:

- Installer SHA-256: `57a6f351d53a32c6f989335e1ea812cd55057e331902b5921343ad2d73428841`.
- Original application EXE SHA-256: `5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3`.
- An extraction directory containing `manifest.json` and `app/`, as required by `make_stage_g231.py`. The script's header documents its extraction contract. The original EXE passed to release checks needs its original `_internal` folder beside it.

Native component binaries, complete game databases and some generator inputs are external inputs, not fully supplied source. Original and third-party notices are preserved in [license_records/](../license_records). [ELYMS.md](ELYMS.md) records the catalog, artwork and native resource adaptation.

## Global build procedure

Commands are examples with local placeholders. Use a separate work directory. The verifier/installer gates execute source checks; native fixture tools execute the supplied Core and belong in an isolated test environment.

```powershell
python build_tools/make_stage_g231.py <extracted-original-2.3.1> config/templates/guide <new-stage>
python build_tools/rebuild_exe_l10n.py <original-NTE_Drive_Calc.exe> src <output-NTE_Drive_Calc.exe> --remove=src.features.settings.updates --remove=src.ui.controllers.update_controller
python build_tools/verify_exe_l10n_g231.py <original-NTE_Drive_Calc.exe> <output-NTE_Drive_Calc.exe> src <new-stage/_internal/data> --removed=src.features.settings.updates --removed=src.ui.controllers.update_controller
python build_tools/verify_elyms.py <new-stage/_internal>
python build_tools/build_installer_g231.py --exe <output-NTE_Drive_Calc.exe> --stage <new-stage> --out <out> --variant release --version 2.3.6 --tree . --official-exe <original-NTE_Drive_Calc.exe> --notes <release-body.md> --emit-manifest --aux-dir <build-work>
```

`rebuild_exe_l10n.py` recompiles the application's `src.*` modules inside the upstream PyInstaller archive and keeps other archive members. This is not compilation of the native binaries from complete source. `make_stage_g231.py` applies the Elyms catalog/artwork and Core resource adaptations. Release gates validate the catalog with the actual application loader and verify staged mappings/provenance. Inno Setup version and build time affect installer bytes; this supplement's corrected notice templates also differ from the retained installer.

## Rebuild the public source archive

Use the tools from the same source supplement commit identified by the release notes. The packer reads tracked Git objects, excludes executable/DLL payloads and validates every restored upstream file against its manifest. It retains `LICENSE`/`NOTICE` at their original paths and supplies `.txt` aliases. `SOURCE_OFFER.txt` is the corrected generated notice; it is **not byte-identical** to the old retained installer's embedded notice.

```powershell
python build_tools/make_source_zip_g231.py . <supplement-commit> NTE_Drive_Calc_2.3.6_Multilingual_source.zip --version 2.3.6 --exe-sha256 3743845cb74a5ed7e175464386d4411fd32bda611cec5fd9a8570ea31a623115 --date 2026-11-07T00:00:00
```

Identical inputs, timestamp and compression runtime produce identical ZIP bytes. The root README, four language guides, source coverage/correction, exact upstream manifest and component license records are included. Personal paths, credentials, signing keys and build output directories must not be published.

## Signed release metadata

Global updates verify the installer size/hash and Ed25519 signature using the public key pinned in `src/app/global_release.py`. The release body is bound by `notes_sha256`; changing its text requires a newly signed manifest. Source ZIPs are separate assets with GitHub SHA-256 digests; they are not covered by the installer's signed hash.

For this documentation supplement the existing installer hash, version and tag stay fixed. Only the source/correction assets, release body and its signed manifest are revised. This exception does not authorize silently replacing application binaries under an existing version. New binary builds should receive a new version.

After preparing the final manifest/body, the maintainer signs and validates locally:

```powershell
ssh-keygen -Y sign -f <private-key-path> -n nte-drive-calc-global-release <NTE_Drive_Calc_version_release.json>
python build_tools/verify_release_manifest.py --local <release-folder> --tree . --notes <release-body.md>
```

The private key is never included in source or published assets. Verification uses OpenSSH and the application's independent pure-Python verifier. See `verify_release_manifest.py --help` for its read-only checks. Retain the four release-note H2 headings `한국어`, `中文`, `English`, `日本語` for in-app language selection. Verify the exact published body against the signed digest after uploading.

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

The team generators read the game's static database and research notes, which are not part of this repository or the source zip, and their default paths assume the author's working folder layout. They are included to show how the tables were made. To change one of the team tables, edit the generated file in `src/services/` directly; the program uses it as it is. The header "GENERATED FILE - DO NOT EDIT" in these files was written for the author's working tree, where the generator inputs exist. Those inputs are not all published. The checked-in tables can be edited, but this does not establish that all preferred source forms and regeneration inputs have been provided; that review remains open.

The Arc Efficiency and awakening (돌파) efficiency rows are different: the program checks them against its game data and the calculation code, and recomputes on your PC when they do not match. Edit the calculation (`arc_efficiency_service.py`, `awakening_efficiency_service.py`, `team_fork_corrections.py`, `awakening_node_rules/`) rather than the rows, and regenerate them with `gen_arc_efficiency_data.py --write` and then `gen_awakening_efficiency_data.py --write`.
