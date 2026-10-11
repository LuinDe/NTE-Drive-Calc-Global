# Changes from the original / 원본과 다른 점

원본 NTE Drive Calc와 이 빌드의 차이를 파일 단위로 정리한 문서입니다. 사용자용 요약은 [README.md](README.md)에 있습니다.

This document lists, at file level, how **NTE Drive Calc Global 2.3.1** differs from the original program.

- Original project: <https://github.com/hxwd94666/NTE-Drive-Calculator> (NTE Drive Calc contributors, AGPL-3.0)
- Baseline: commit `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` ("feat：2.3.1版本开发完毕", `src/app/version.py` = 2.3.1). All 893 `src.*` modules inside the official 2.3.1 executable (SHA-256 `5b8fa8d2…e8c3`, installed by the official `NTE_Drive_Calc_Setup_2.3.1.exe`) equal a compile of this commit. The upstream tag `2.3.1` points to an older commit (`765d78a`, version 2.3.0) and is not the baseline.
- Modified by: LuinDe, 2026-10-11 (first Global release 2.3.0: 2026-10-05)
- Scope: only `src/` and the seven tutorial images are modified. Everything else of the original (main.py, assets, data, native components, third_party, build scripts) is unchanged and is not part of this repository.

## Overview of `src/`

| | Files |
|---|---:|
| Original `src/` at the baseline | 1,000 (915 `.py`, 85 `.sql`) |
| `src/` in this repository | 1,030 (945 `.py`, 85 `.sql`) |
| New files | 30 |
| Original files removed | 0 |
| Original `.py` files, byte-identical | 270 |
| Original `.py` files where only user-visible strings were wrapped for translation | 594 |
| Original `.py` files with code changes (listed below) | 51 |
| `.sql` files, byte-identical to the baseline | 85 |

How the split was determined: both trees were parsed and compared as syntax trees, with every `_L('…')` / `_LF('…').format(…)` wrapper resolved back to its Chinese literal or f-string and the import line of the wrappers dropped. 51 files differ after that normalisation; they are the original (not new) files in the tables of sections 1 to 7.

## 1. Four interface languages (new files and string wrapping)

New files:

| File | Purpose |
|---|---|
| `src/i18n_runtime.py` | Language runtime. The Chinese source text is the key: `L()` / `LF()` look it up in the active table, remember the key so a string can be re-rendered, and `set_language()` saves the choice (`_internal/config/i18n_language.json`) and notifies listeners. Languages: `zh` (identity), `ko`, `ja`, `en`; default `ko`. |
| `src/i18n_data_ko.py`, `src/i18n_data_en.py`, `src/i18n_data_ja.py` | Translation tables: 8,138 plain strings and 1,992 format templates per language. The English and Japanese modules also hold 3,390 game names / terms and 1,827 descriptions for the display layer. |
| `src/i18n_display.py` | Display layer. Internal identifiers (character, attribute and set names, values matched against OCR output, the static database and saved user data) stay Chinese; this module translates text only when a widget shows it, and re-translates the open window when the language changes. It also holds the Korean game-term dictionaries, the phrases returned by the bundled native analysis component, and the Korean / initial-consonant search helper `ko_contains`. |
| `src/i18n_desc.py` | Exact-match dictionary for long descriptions from the static database (Korean). |

String wrapping: in the original files the user-visible Chinese literals are written as `_L('原文')` and f-strings as `_LF('模板{0}').format(…)`, plus one import line. In 594 files this is the only change; with the language set to Chinese they behave as the original. The slot numbers `{0}`, `{1}` … follow the order of the expressions in the Chinese original (Global 2.3.0 numbered 9 templates in the Korean order, so some values could appear in each other's place).

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
| `src/features/team_simulation/__init__.py`, `page.py` | The page: four member cards (Awakening, Arc, Refinement, Cartridge Set), mode switch, swap-order choice, result cards, notice. The arc list of a member card shows the arcs the character can equip; another character's exclusive arc carries its owner's name. |
| `src/features/team_simulation/explanation_view.py` | Explanation panel below the result: rotation used, visit order and why it was chosen, reaction table, steps per member, assumptions and limits (including which arcs the Global supplement rule modelled). |
| `src/features/team_simulation/custom_panel.py`, `custom_view.py` | Custom Input mode: step builder, notation text box, options, save / load, step table of the result. |
| `src/services/team_simulation_service.py` | The simulator: builds the team from the graduation templates, lays out the rotations on the animation time axis, runs the existing battle-replay engine, 3 loops, visit-order planner (`plan` / `auto` / `slot`). |
| `src/services/team_fork_corrections.py` | New in 2.3.1. Arc corrections shared with the Arc Efficiency table (section 3), applied before the engine runs; the upstream engine files are not changed. **B1** the chosen arc and refinement reach the character panel (in Global 2.3.0 an arc swap did not change the panel stats). **B2** an always-on arc bonus that the panel already holds is not counted a second time by the engine. **B3** 「罪与罚」 (Crime and Punishment) and **B4** 「月的对跖点」 (Antipode of the Moon): the engine opens these arcs' buffs but cannot price them, so their windows and values are built from the description text and the database parameters; durations run on the engine's active clock (time stops excluded). B3 / B4 are labelled "Global supplement rule" in the interface. |
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
| `src/ui/navigation.py` | New navigation items `team_sim` (below Calculate) and `arc_eff` (section 3). |
| `src/ui/main_window_mixins.py` | `TeamSimulationMixin` and `ArcEfficiencyMixin` add the page builders to the main window. |

The three generated team tables are produced by `build_tools/gen_team_form_actions.py`, `gen_team_rotation_data.py` and `gen_team_custom_actions.py` (run through `build_tools/g231_shims/` for this tree). Their inputs (the game's static database and research notes) are not in this repository; the generated files are the form in which the tables are maintained here and can be edited directly. The header "GENERATED FILE - DO NOT EDIT" in these three files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.

Team Simulation numbers differ from Global 2.3.0. Two causes: the 2.3.1 game data (graduation templates and arc rows of 黑羽 Raven and 明音凛 Akane Rin changed upstream), and B1–B4 above. Typical effects: teams with a character whose arc has an always-on bonus are about 1–11 % lower (B2), teams with Crime and Punishment or Antipode of the Moon are higher (B3 / B4), and a member whose arc was changed from the template now gets that arc's stats (B1). Every changed number was traced to one of these causes (89 test scenarios, 52 changed by the corrections, none without the corrected arc in the team). The development switch `NTE_TEAM_FORK_CORRECTIONS=off` turns the corrections off; the Arc Efficiency table then does not use its precomputed rows.

## 3. Arc Efficiency Table (Beta) — new feature

A new page in the sidebar, below Team Simulation. For every character with an exclusive arc it compares the arcs the character can equip by the damage of the character's reviewed solo rotation.

| File | Purpose |
|---|---|
| `src/features/arc_efficiency/__init__.py`, `page.py`, `table_view.py` | The page: character list (best alternative and where the row came from), the arc table (rank, R1 %, max-refinement %, refinement gain, notes, optional damage columns), legend, notice, options (3 loops / 1 loop, basis "exclusive R1 = 100 %" / "same refinement", show or hide other characters' exclusive arcs †, damage columns), "Open in Team Simulation". Options are saved in `config/arc_efficiency_preferences.json` (not per account). |
| `src/services/arc_efficiency_service.py` | The calculation: the character alone, official graduation template, only the arc and its refinement swapped, reviewed rotation, Lv80 dummy, the Team Simulation engine with the corrections of section 2. It decides per character whether the precomputed rows can be used (same game data and the same calculation code), otherwise it recomputes in the background, the viewed character first, and caches the result on this PC (`config/arc_efficiency_cache.json`). |
| `src/services/arc_efficiency_notes.py` | Per-arc notes: which effects the solo calculation cannot reflect (support skill, teammates, team makeup, Cycle / Break intensity, hits taken …). |
| `src/services/arc_efficiency_data.py` | Generated: the precomputed rows (11 characters × the arcs each can equip × refinement 1 and max × 1 and 3 loops; 448 rows) with the hash of the game database and a fingerprint of the calculation code. Generator: `build_tools/gen_arc_efficiency_data.py`. |

Which arcs are listed: the character's exclusive arc (★), the generic arcs of the same type, and other characters' exclusive arcs that the calculator's same-type rule lets the character equip (†; not verified in game, hidden with one switch). Characters without an exclusive arc are not in the table; a future character with an exclusive arc in the game data appears automatically. The limits of the model are shown on the page ("Notice") and in [RELEASE_NOTES.md](RELEASE_NOTES.md).

## 4. Battle Report: Compare with My Characters — new feature

| File | Change |
|---|---|
| `src/services/battle_import_comparison_service.py` (new) | For an imported report, replaces the builds of characters the current account also owns with the account's own build and equipment, re-evaluates the recorded battle once, and returns both results. In memory only; nothing is saved. |
| `src/features/battle_report/my_build_comparison.py` (new) | Button state, background worker and result window. |
| `src/features/battle_report/analysis_view.py`, `page.py` | New button `compare_mine` (hidden unless the record is an imported report) and its signal. |
| `src/features/battle_report/controller.py`, `analysis_controller_mixin.py` | Create the controller and refresh it when a record is opened. |

## 5. Protection of other programs' files in the game folder — behaviour change

Official 2.3.1 deploys `d3d12.dll` (host) and `plugins/NTE_Plugin{User,Combat,HUD,Performance}.dll` into the game folder and still cleans up the older `NTE_Capture.dll` and the legacy `dwmapi.dll` loader. In this build a file with one of these names is replaced or deleted only when its SHA-256 is a file of this program: the bundled component, a declared predecessor (`upgrade_from`), any official build of that component, or the file this program recorded when it deployed it.

| File | Change |
|---|---|
| `src/services/native_plugin_deployment.py` | Deploying to the game folder stops with a message (`ForeignGameFileError`) when a target file exists and is not known; the Loader's private folder keeps the original behaviour. Automatic and manual clean-up delete only known files; any other file (for example ReShade installed as `d3d12.dll`) is kept and reported, and the clean-up of the program's own files still completes. |
| `src/integrations/legacy_game_proxy.py`, `src/services/managed_plugin_cleanup.py` | Only this program's own old `dwmapi.dll` loaders count as a leftover; another `dwmapi.dll` (for example UE4SS) is kept and reported. |
| `src/services/component_upgrade_guide.py` | The component-upgrade check names an unknown file as foreign instead of offering to replace it. |
| `src/services/work_mode_runtime.py` | Passes the application root and the deployment record to the clean-up so it can read the known hashes. |
| `src/ui/controllers/native_plugin_deployment_ui.py` | Shows the foreign-file message, and notes a kept file in the success dialogs. |

The hot plugin update of 2.3.1 (`src/services/native_plugin_update.py`) is unchanged: it only replaces plugin files the running host reports as loaded with the same SHA-256.

## 6. Battle-report replay — Python reference arithmetic

| File | Change |
|---|---|
| `src/services/battle_special_replay_numeric.py` | Hex (覆纹) follow-up copy ratio with Linko's passive in `python_special_numeric`: `0.30` → `0.33` (20% + 13%, as documented upstream for the analysis component). This path runs when no native compute backend takes the job; results computed by the bundled analysis component are unchanged. Team Simulation does not go through this path for Hex: it applies its own post-replay formula (`apply_hexed` in `src/services/team_cycle_reactions.py`), which uses the same 0.33. |

## 7. Adjustments needed by the localisation

Search, layout and input:

| File | Change |
|---|---|
| `src/features/static_catalog/domain_pages/character_page.py`, `equipment_page.py`, `fork_page.py`, `monster_page.py` | Search boxes also match Korean text and Korean initial consonants (`ko_contains`). |
| `src/features/allocation/execute_page.py` | Two result-header buttons use a minimum width instead of a fixed size, so longer translations fit. |
| `src/features/settings/work_mode_card.py` | The work-mode labels and the "检测并处理" (Check and Fix) button use a minimum width instead of a fixed width (the official 96 px button is 3 px too narrow even for the Chinese text). |
| `src/features/toolbox/cultivation_stamina_ui.py` | The stamina hint wraps, so the cultivation page has no horizontal overflow at the default window size in any language. |
| `src/features/static_catalog/domain_pages/character_profile.py` | The quality badge uses the quality keys (`S 级` / `A 级`) instead of the level template, so it is not translated as a level. |
| `src/features/battle_report/timeline_view.py` | The fallback avatar letter is taken from the displayed (translated) name. |
| `src/features/identification/controller.py` | Manual input on the Appraisal page: stat names shown in the current language are mapped back to the internal names before parsing. |
| `src/ui/plain_text_edit.py` | Paste inserts through the text cursor so the display layer does not translate the text the parser reads. |
| `src/ui/operation_guidance.py` | The "current mode does not allow this feature" message is one template, so the mode name can be placed by the translation. |
| `src/features/settings/component_upgrade_dialog.py` | The upgrade step text is rendered in the active language before the method name is filled in (after a live language switch it stayed Chinese). |

Text matching that no longer depends on the language (code that compared a message with a Chinese literal, cut a label out of it, or checked the type of a value):

| File | Change |
|---|---|
| `src/domain/cultivation_history.py` | The value check of a saved cultivation-history record accepts translated text objects (subclasses of `str`); without it every save failed in every language. The record's target label is kept in the original Chinese, so a record opens in every language and records written by the official 2.3.1 open too. |
| `src/services/battle_buff_interval_support.py`, `battle_buff_projection_rules.py`, `battle_damage_composition_service.py`, `battle_fork_damage_state_service.py`, `battle_trigger_requirement_service.py` | Attack-type tests accept the original `普通攻击` as well as the translated label. |
| `src/services/battle_action_inference_service.py`, `battle_timeline_projection_service.py`, `skill_name_rendering_service.py`, `src/features/battle_report/timeline_tooltip.py`, `src/services/battle_damage_composition_service.py` | "Unrecognised / unknown skill" markers are recognised in the original and the translated form. |
| `src/services/battle_hit_replay_explanation_service.py`, `src/features/battle_report/hit_formula_overview.py` | Factor labels and missing-evidence markers are looked up in both forms. |
| `src/features/plugins/page.py` | Plugin status badges ("not supported", "needs update" …) are chosen from the Chinese source of the status text, so a translated status gets the same badge as in Chinese. |
| `src/features/home/page.py`, `src/features/home/sync_retry_dialog.py`, `src/ui/controllers/inventory_sync_controller.py` | `relabel_next_step()` replaces a text replacement that only worked on the Chinese label. |
| `src/features/inventory/equipment_assembly_controller.py` | Recognises the "missing character instance" reason in any language. |
| `src/features/settings/page.py`, `src/ui/controllers/update_controller.py` | Compare against the translated message as well as the Chinese fragment. |
| `src/features/static_catalog/domain_pages/monster_page.py`, `monster_detail_view.py`, `src/services/static_catalog_monster_feast.py`, `src/services/static_catalog_mechanics_service.py` | Section titles, level labels, category suffixes and field tones are matched in any language. |

Fixes relative to the earlier Korean patch (<https://github.com/LuinDe/NTE-Drive-Calc-KO>), not relative to the original: in that patch some dictionary keys were translated on one side only. For example, the save / manage confirmation of the inventory page failed because `counts['弃置']` no longer matched. In this tree both sides use the same wrapped key (`src/features/inventory/warehouse_controller.py`, `src/features/static_catalog/domain_pages/monster_detail_view.py`).

## 8. Outside `src/`

| Item | Change |
|---|---|
| `config/templates/guide/1.png` – `7.png` | The seven "how to use" tutorial images are replaced by Korean versions. The program has one image set, so they are Korean in every language. |
| Executable `NTE_Drive_Calc.exe` | The official 2.3.1 PyInstaller executable (SHA-256 `5b8fa8d2…e8c3`) with only the `src.*` records of its PYZ archive replaced: 260 records kept as they are, 633 recompiled from this tree, 52 added (the 30 new files, and 22 modules that exist in the original source but that the official build did not bundle because nothing imports them). The 2,008 other PYZ entries and every other archive entry are byte-identical; the PE checksum is recomputed. Script: `build_tools/rebuild_exe_l10n.py`; proof: `build_tools/verify_exe_l10n_g231.py`. |
| Installer | `build_tools/build_installer_g231.py`, a port of the original `build_installer.py` at the baseline commit. Same application ID, default folder, privileges, `[Files]` / `[InstallDelete]` / `[Dirs]` structure as the official 2.3.1 installer, so it upgrades an official install in place and a later official installer installs over it. Differences: a setup wizard in four languages, the product is named "NTE Drive Calc 2.3.1 Multilingual Edition (Global)" (localised) with a publisher string that says unofficial, a notice page, the folder `l10n_build` with `LICENSE.txt`, `README.txt` and `SOURCE_OFFER.txt`, the program's start language is written from the setup language only when no language was set before, and the language file is removed on uninstall. |
| `_internal/`, `drivers/` in the installer | Copied from the official 2.3.1 installation without change, except the seven tutorial images. |

## 9. Changes since Global 2.3.0

For users of the previous release, in short:

- Based on the official 2.3.1 (everything the original added in 2.3.1, including the cultivation history and the plugin-based in-game components).
- New Arc Efficiency Table (Beta) (section 3).
- Team Simulation: arc corrections B1–B4 (section 2), so its numbers change.
- Game-folder protection rewritten for the 2.3.1 component layout (section 5).
- Translations: about 700 new 2.3.1 strings in three languages; the Korean texts take the wording of the Korean patch for 2.3.1 (official Korean skill names, 倾陷 = 붕괴, 援护技 = 서포트 스킬); 288 older game descriptions are now translated into English and Japanese as well.
- Fixed: value slots of 9 translated templates (section 1), `&` in English buttons and tabs being read as a keyboard shortcut (now "and"), and a few English and Japanese terms.
