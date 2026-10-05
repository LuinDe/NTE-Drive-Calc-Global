# Changes from the original / 원본과 다른 점

원본 NTE Drive Calc와 이 빌드의 차이를 파일 단위로 정리한 문서입니다. 사용자용 요약은 [README.md](README.md)에 있습니다.

This document lists, at file level, how **NTE Drive Calc Global 2.3.0** differs from the original program.

- Original project: <https://github.com/hxwd94666/NTE-Drive-Calculator> (NTE Drive Calc contributors, AGPL-3.0)
- Baseline: commit `d3eca803ac36a75a3fa4fbbf8adadb93dadadf65` (upstream tag `2.3.0.1`, the release that carries the official 2.3.0 installer `NTE_Drive_Calc_Setup_2.3.0.exe`; the upstream tag `2.3.0` points to a different commit and is not the baseline)
- Modified by: LuinDe, 2026-10-05
- Scope: only `src/` and the seven tutorial images are modified. Everything else of the original (main.py, assets, data, native components, third_party, build scripts) is unchanged and is not part of this repository.

## Overview of `src/`

| | Files |
|---|---:|
| Original `src/` at the baseline | 924 (842 `.py`, 82 `.sql`) |
| `src/` in this repository | 947 (865 `.py`, 82 `.sql`) |
| New files | 23 |
| Original `.py` files, byte-identical | 263 |
| Original `.py` files where only user-visible strings were wrapped for translation | 549 |
| Original `.py` files with code changes (listed below) | 30 |
| `.sql` files, byte-identical to the baseline | 82 |

How the split was determined: both trees were parsed and compared as syntax trees, with every `_L('…')` / `_LF('…').format(…)` wrapper resolved back to its Chinese literal or f-string. 30 files (211 changed lines) differ after that normalisation; they are the original (not new) files in the "Hooks in original files" tables of sections 1 and 2 and in the tables of sections 3 to 6.

## 1. Four interface languages (new files and string wrapping)

New files:

| File | Purpose |
|---|---|
| `src/i18n_runtime.py` | Language runtime. The Chinese source text is the key: `L()` / `LF()` look it up in the active table, remember the key so a string can be re-rendered, and `set_language()` saves the choice (`_internal/config/i18n_language.json`) and notifies listeners. Languages: `zh` (identity), `ko`, `ja`, `en`; default `ko`. |
| `src/i18n_data_ko.py`, `src/i18n_data_en.py`, `src/i18n_data_ja.py` | Translation tables: 7,468 plain strings and 1,881 format templates per language. The English and Japanese modules also hold 2,938 game names / terms and 1,527 descriptions for the display layer. |
| `src/i18n_display.py` | Display layer. Internal identifiers (character, attribute and set names, values matched against OCR output, the static database and saved user data) stay Chinese; this module translates text only when a widget shows it, and re-translates the open window when the language changes. It also holds the Korean game-term dictionaries, the phrases returned by the bundled native analysis component, and the Korean / initial-consonant search helper `ko_contains`. |
| `src/i18n_desc.py` | Exact-match dictionary for long descriptions from the static database (Korean). |

String wrapping: in 576 original files the user-visible Chinese literals are written as `_L('原文')` and f-strings as `_LF('模板{0}').format(…)`, plus one import line. In 549 of them this is the only change; with the language set to Chinese they behave as the original.

Hooks in original files:

| File | Change |
|---|---|
| `src/ui/app.py` | Installs the display layer at start-up. |
| `src/ui/main_window_navigation_mixin.py` | Language switcher at the bottom of the sidebar: four buttons (中文 / 한국어 / 日本語 / English) that switch the running interface. |
| `src/app/theme.py` | `Malgun Gothic` and `Yu Gothic UI` are placed in front of the font stack. |

## 2. Team Simulation (Beta) — new feature

A new page in the sidebar. It is marked as unfinished in the interface; see the limits in [RELEASE_NOTES.md](RELEASE_NOTES.md).

New files:

| File | Purpose |
|---|---|
| `src/features/team_simulation/__init__.py`, `page.py` | The page: four member cards (Awakening, Arc, Refinement, Cartridge Set), mode switch, swap-order choice, result cards, notice. |
| `src/features/team_simulation/explanation_view.py` | Explanation panel below the result: rotation used, visit order and why it was chosen, reaction table, steps per member, assumptions and limits. |
| `src/features/team_simulation/custom_panel.py`, `custom_view.py` | Custom Input mode: step builder, notation text box, options, save / load, step table of the result. |
| `src/services/team_simulation_service.py` | The simulator: builds the team from the graduation templates, lays out the rotations on the animation time axis, runs the existing battle-replay engine, 3 loops, visit-order planner (`plan` / `auto` / `slot`). |
| `src/services/team_cycle_reactions.py` | Esper Cycle model: element ring, Cycle Value rule, scheduling of Blossom / Hex / Scorch / Nova / Stain / Remora and of Charge / Discord. Reactions are always computed. |
| `src/services/team_rotation_data.py` | Generated table: the reviewed rotation of each of the 24 characters. |
| `src/services/team_form_actions.py` | Generated table: attacks available in transformation / form states. |
| `src/services/team_simulation_explanation.py` | Data model and texts of the explanation panel. |
| `src/services/team_custom_actions.py` | Generated table: per-character action palette of the Custom Input mode (names in four languages, hit timing, cooldown data where the game data has it). |
| `src/services/team_custom_notation.py` | Parser and formatter of the notation (`Zero support > Zero E > Zero basicx3 > …`) with aliases in four languages. |
| `src/services/team_custom_cycle_service.py` | Simulation of a typed sequence: support / swap entries, Cycle Value modes, cooldown and energy checks, inferred and manual buffs, numeric options. |
| `src/services/team_custom_cycle_store.py` | Save / load of named rotations (`accounts/<id>/config/team_custom_cycles.json`). |
| `src/services/team_custom_cycle_texts.py` | Texts of the Custom Input mode. |

Hooks in original files:

| File | Change |
|---|---|
| `src/ui/navigation.py` | New navigation item `team_sim`. |
| `src/ui/main_window_mixins.py` | `TeamSimulationMixin` adds the page builder to the main window. |

The three generated tables are produced by `build_tools/gen_team_form_actions.py`, `gen_team_rotation_data.py` and `gen_team_custom_actions.py`. Their inputs (the game's static database and research notes) are not in this repository; the generated files are the form in which the tables are maintained here and can be edited directly. The header "GENERATED FILE - DO NOT EDIT" in these three files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.

## 3. Battle Report: Compare with My Characters — new feature

| File | Change |
|---|---|
| `src/services/battle_import_comparison_service.py` (new) | For an imported report, replaces the builds of characters the current account also owns with the account's own build and equipment, re-evaluates the recorded battle once, and returns both results. In memory only; nothing is saved. |
| `src/features/battle_report/my_build_comparison.py` (new) | Button state, background worker and result window. |
| `src/features/battle_report/analysis_view.py`, `page.py` | New button `compare_mine` (hidden unless the record is an imported report) and its signal. |
| `src/features/battle_report/controller.py`, `analysis_controller_mixin.py` | Create the controller and refresh it when a record is opened. |

## 4. Protection of foreign files in the game folder — behaviour change

| File | Change |
|---|---|
| `src/services/native_plugin_deployment.py` | Deploying the in-game components stops with a message when `d3d12.dll` / `NTE_Capture.dll` in the game folder exists and its SHA-256 is neither the bundled file nor a declared predecessor (`protect_foreign`). Automatic and manual clean-up delete a file only when its SHA-256 is the recorded one, the bundled one or a declared predecessor; any other file (for example ReShade installed as `d3d12.dll`) is kept and reported, and the clean-up of the program's own files still completes. |
| `src/services/work_mode_runtime.py` | Passes the application root to the clean-up so it can read the bundled component hashes. |

## 5. Battle-report replay — Python reference arithmetic

| File | Change |
|---|---|
| `src/services/battle_special_replay_numeric.py` | Hex (覆纹) follow-up copy ratio with Linko's passive in `python_special_numeric`: `0.30` → `0.33` (20% + 13%, as documented upstream for the analysis component). This path runs when no native compute backend takes the job; results computed by the bundled analysis component are unchanged. Team Simulation does not go through this path for Hex: it applies its own post-replay formula (`apply_hexed` in `src/services/team_cycle_reactions.py`), which uses the same 0.33. |

## 6. Adjustments needed by the localisation

Search, layout and input:

| File | Change |
|---|---|
| `src/features/static_catalog/domain_pages/character_page.py`, `equipment_page.py`, `fork_page.py`, `monster_page.py` | Search boxes also match Korean text and Korean initial consonants (`ko_contains`). |
| `src/features/allocation/execute_page.py` | Two result-header buttons use a minimum width instead of a fixed size, so longer translations fit. |
| `src/features/battle_report/timeline_view.py` | The fallback avatar letter is taken from the displayed (translated) name. |
| `src/features/identification/controller.py` | Manual input on the Appraisal page: stat names shown in the current language are mapped back to the internal names before parsing. |
| `src/ui/plain_text_edit.py` | Paste inserts through the text cursor so the display layer does not translate the text the parser reads. |

Text matching that no longer depends on the language (code that compared a message with a Chinese literal or cut a label out of it):

| File | Change |
|---|---|
| `src/features/home/page.py`, `src/features/home/sync_retry_dialog.py`, `src/ui/controllers/inventory_sync_controller.py` | `relabel_next_step()` replaces a text replacement that only worked on the Chinese label. |
| `src/features/battle_report/hit_formula_overview.py` | Factor labels are looked up with the same template that produces them. |
| `src/features/inventory/equipment_assembly_controller.py` | Recognises the "missing character instance" reason in any language. |
| `src/features/plugins/page.py`, `src/features/settings/page.py`, `src/ui/controllers/update_controller.py` | Compare against the translated message as well as the Chinese fragment. |
| `src/features/static_catalog/domain_pages/monster_page.py`, `src/services/static_catalog_monster_feast.py`, `src/services/static_catalog_mechanics_service.py` | Section titles, category suffixes and field tones are matched in any language. |

Fixes relative to the earlier Korean patch (<https://github.com/LuinDe/NTE-Drive-Calc-KO>), not relative to the original: in that patch some dictionary keys were translated on one side only. For example, the save / manage confirmation of the inventory page failed because `counts['弃置']` no longer matched. In this tree both sides use the same wrapped key (`src/features/inventory/warehouse_controller.py`, `src/features/static_catalog/domain_pages/monster_detail_view.py`).

## 7. Outside `src/`

| Item | Change |
|---|---|
| `config/templates/guide/1.png` – `7.png` | The seven "how to use" tutorial images are replaced by Korean versions. The program has one image set, so they are Korean in every language. |
| Executable `NTE_Drive_Calc.exe` | The official 2.3.0 PyInstaller executable (SHA-256 `505950ca…cbbf`) with only the `src.*` records of its PYZ archive replaced: 253 records kept as they are, 567 recompiled from this tree, 45 added (the 23 new files, and 22 modules that exist in the original source but that the official build did not bundle because nothing imports them). The 2,008 other PYZ entries and every other archive entry are byte-identical; the PE checksum is recomputed. Script: `build_tools/rebuild_exe_l10n.py`; proof: `build_tools/verify_exe_l10n.py`. |
| Installer | `build_tools/build_installer_l10n.py`, a port of the original `build_installer.py`. Same application ID, default folder and privileges as the official installer, so it upgrades an official install in place and a later official installer installs over it. Differences: a setup wizard in four languages, the product is named "NTE Drive Calc 2.3.0 Multilingual Edition" (localised) with a publisher string that says unofficial, a notice page, the folder `l10n_build` with `LICENSE.txt`, `README.txt` and `SOURCE_OFFER.txt`, and the program's start language is written from the setup language when no language was set before. |
| `_internal/`, `drivers/` in the installer | Copied from the official 2.3.0 installation without change, except the seven tutorial images. |
