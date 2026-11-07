# 2026-11-07 · Global 2.3.6 source/documentation supplement

- Restored 121 public upstream files (with a documented Global maintainer metadata adjustment); see UPSTREAM_SOURCE_FILES.json.
- Preserved 120 installed license/provenance records under license_records/.
- Expanded the public source archive and corrected source-completeness claims.
- Rewrote the Korean, Chinese, English and Japanese descriptions with original author credits.
- Retained installer, application src/ and v2.3.6 tag unchanged. Exact native Corresponding Source gaps remain; see SOURCE_OFFER.md.
- Earlier release assets and version tags were removed; historical Git commits remain discoverable in docs/source-history.md.

The text below records historical changes. Current source coverage is described in SOURCE_OFFER.md.

---

# Changes from the original / 원본과 다른 점

Global 2.3.6 converts Elyms' full-body artwork to PNG so the runtime character catalog can load during startup. The installer release gate now runs the application's catalog validator. The Elyms regression check also decodes all three character and Arc images with Qt. [Release notes](RELEASE_NOTES_2.3.6.md).

Global 2.3.5 adds Elyms (1090) to the native Core’s embedded character and equipment mappings so inventory sync can save her equipped items. [Release notes](RELEASE_NOTES_2.3.5.md).

Global 2.3.4 distributes the Elyms update with a new Ed25519 release key. Existing installations require one manual upgrade. [Release notes](RELEASE_NOTES_2.3.4.md).

Global 2.3.3 adds CN 1.5.4 Elyms (1090) to both catalogs, the equipment solver and the four-language UI. See [Elyms build data and validation](build_tools/ELYMS.md).

원본 NTE Drive Calc와 이 빌드의 차이를 파일 단위로 정리한 문서입니다. 사용자용 요약은 [README.md](README.md)에 있습니다.

This document lists, at file level, how **NTE Drive Calc Global 2.3.2** differs from the original program.

- Original project: <https://github.com/hxwd94666/NTE-Drive-Calculator> (NTE Drive Calc contributors, AGPL-3.0)
- Baseline: commit `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` ("feat：2.3.1版本开发完毕", `src/app/version.py` = 2.3.1). All 893 `src.*` modules inside the official 2.3.1 executable (SHA-256 `5b8fa8d2…e8c3`, installed by the official `NTE_Drive_Calc_Setup_2.3.1.exe`) equal a compile of this commit. The upstream tag `2.3.1` points to an older commit (`765d78a`, version 2.3.0) and is not the baseline.
- Modified by: LuinDe, 2026-10-20 (Global 2.3.2; everything except section 16 was first published briefly on 2026-10-19 as 2.3.1-global.2; 2.3.1-global.1: 2026-10-11; first Global release 2.3.0: 2026-10-05)
- A 2.3.1-global.2 install does not recognise the new version format, so install 2.3.2 once by hand (as from 2.3.1-global.1).
- Version numbers: Global's version number is now independent of the original's: `v<major>.<minor>.<patch>` (`GLOBAL_VERSION` in `src/app/global_release.py`; Global 2.3.2 is based on the official 2.3.1). Releases up to 2.3.1-global.2 used `<major>.<minor>.<patch>-global.<n>`; that form is still read and sorts before the plain version with the same numbers (2.3.1-global.1 < 2.3.1-global.2 < 2.3.2 < 2.3.2-global.1 < 2.3.3; grammar in section 8). `src/app/version.py` keeps the upstream `2.3.1`, because the bundled native components read it.
- Scope: only `src/` and the seven tutorial images are modified. Everything else of the original (main.py, assets, data, native components, third_party, build scripts) is unchanged and is not part of this repository.

## Overview of `src/`

| | Files |
|---|---:|
| Original `src/` at the baseline | 1,000 (915 `.py`, 85 `.sql`) |
| `src/` in this repository | 1,067 (982 `.py`, 85 `.sql`) |
| New files | 69 |
| Original files removed | 2 (the original's update function, section 8) |
| Original `.py` files, byte-identical | 267 |
| Original `.py` files where only user-visible strings were wrapped for translation | 557 |
| Original `.py` files with code changes (listed below) | 89 |
| `.sql` files, byte-identical to the baseline | 85 |

How the split was determined: both trees were parsed and compared as syntax trees, with every `_L('…')` / `_LF('…').format(…)` wrapper resolved back to its Chinese literal or f-string and the import line of the wrappers dropped. 89 files differ after that normalisation; they are the original (not new) files in the tables of sections 1 to 14.

## 1. Four interface languages (new files and string wrapping)

New files:

| File | Purpose |
|---|---|
| `src/i18n_runtime.py` | Language runtime. The Chinese source text is the key: `L()` / `LF()` look it up in the active table, remember the key so a string can be re-rendered, and `set_language()` saves the choice (`_internal/config/i18n_language.json`) and notifies listeners. Languages: `zh` (identity), `ko`, `ja`, `en`; default `ko`. |
| `src/i18n_data_ko.py`, `src/i18n_data_en.py`, `src/i18n_data_ja.py` | Translation tables (plain strings and format templates per language). The English and Japanese modules also hold game names / terms and descriptions for the display layer. |
| `src/i18n_display.py` | Display layer. Internal identifiers (character, attribute and set names, values matched against OCR output, the static database and saved user data) stay Chinese; this module translates text only when a widget shows it, and re-translates the open window when the language changes. It also holds the Korean game-term dictionaries, the phrases returned by the bundled native analysis component, and the Korean / initial-consonant search helper `ko_contains`. |
| `src/i18n_desc.py` | Exact-match dictionary for long descriptions from the static database (Korean). |

String wrapping: in the original files the user-visible Chinese literals are written as `_L('原文')` and f-strings as `_LF('模板{0}').format(…)`, plus one import line. In 557 files this is the only change; with the language set to Chinese they behave as the original. The slot numbers `{0}`, `{1}` … follow the order of the expressions in the Chinese original (Global 2.3.0 numbered 9 templates in the Korean order, so some values could appear in each other's place).

Korean terms: since 2.3.2 the Korean interface calls awakening (觉醒) **돌파**; the level breakthrough (突破) is **레벨 돌파**. English and Japanese keep "Awakening" / 「覚醒」.

Hooks in original files:

| File | Change |
|---|---|
| `src/ui/app.py` | Installs the display layer at start-up (and, since 2.3.2, the Global update controller, section 8). |
| `src/ui/main_window_navigation_mixin.py` | Language switcher at the bottom of the sidebar: four buttons (中文 / 한국어 / 日本語 / English) that switch the running interface. Since 2.3.2 the sidebar title reads "NTE Drive Calc Global". |
| `src/app/theme.py` | `Malgun Gothic` and `Yu Gothic UI` are placed in front of the font stack. |

## 2. Team Simulation (Beta) — new feature

A new page in the sidebar. It is marked as unfinished in the interface; see the limits in [RELEASE_NOTES.md](RELEASE_NOTES.md). Since 2.3.2 it also models ultimate energy, the Esper-Cycle gauge and cooldowns (section 9) and free awakening choice (section 10).

New files:

| File | Purpose |
|---|---|
| `src/features/team_simulation/__init__.py`, `page.py` | The page: four member cards (Awakening, Arc, Refinement, Cartridge Set), mode switch, swap-order choice, resource-model choice (section 9), result cards, notice. The arc list of a member card shows the arcs the character can equip; another character's exclusive arc carries its owner's name. |
| `src/features/team_simulation/explanation_view.py` | Explanation panel below the result: rotation used, visit order and why it was chosen, reaction table, steps per member, resource events (energy, gauge, cooldown waits and swaps), assumptions and limits (including which arcs the Global supplement rule modelled). |
| `src/features/team_simulation/custom_panel.py`, `custom_view.py` | Custom Input mode: step builder, notation text box, options, save / load, step table of the result. |
| `src/services/team_simulation_service.py` | The simulator: builds the team from the graduation templates, lays out the rotations on the animation time axis, runs the existing battle-replay engine, 3 loops, visit-order planner (`plan` / `auto` / `slot`). |
| `src/services/team_fork_corrections.py` | New in 2.3.1. Arc corrections shared with the Arc Efficiency table (section 3), applied before the engine runs; the upstream engine files are not changed. **B1** the chosen arc and refinement reach the character panel (in Global 2.3.0 an arc swap did not change the panel stats). **B2** an always-on arc bonus that the panel already holds is not counted a second time by the engine. **B3** 「罪与罚」 (Crime and Punishment) and **B4** 「月的对跖点」 (Antipode of the Moon): the engine opens these arcs' buffs but cannot price them, so their windows and values are built from the description text and the database parameters; durations run on the engine's active clock (time stops excluded). B3 / B4 are labelled "Global supplement rule" in the interface. Since 2.3.2 B4 follows Akane Rin's CN-release arc text while the overlay of section 11 is on. |
| `src/services/team_cycle_reactions.py` | Esper Cycle model: element ring, Cycle Value rule, scheduling of Blossom / Hex / Scorch / Nova / Stain / Remora and of Charge / Discord. Reactions are always computed. |
| `src/services/team_rotation_data.py` | Generated table: the reviewed rotation of each of the 24 characters. |
| `src/services/team_form_actions.py` | Generated table: attacks available in transformation / form states. |
| `src/services/team_simulation_explanation.py` | Data model and texts of the explanation panel. |
| `src/services/team_custom_actions.py` | Generated table: per-character action palette of the Custom Input mode (names in four languages, hit timing). |
| `src/services/team_custom_notation.py` | Parser and formatter of the notation (`Zero support > Zero E > Zero basicx3 > …`) with aliases in four languages. |
| `src/services/team_custom_cycle_service.py` | Simulation of a typed sequence: support / swap entries, Cycle Value modes, cooldown and energy checks, inferred and manual buffs, numeric options. |
| `src/services/team_custom_cycle_store.py` | Save / load of named rotations (`accounts/<id>/config/team_custom_cycles.json`). |
| `src/services/team_custom_cycle_texts.py` | Texts of the Custom Input mode. |

Hooks in original files:

| File | Change |
|---|---|
| `src/ui/navigation.py` | New navigation items `team_sim` (below Calculate) and `arc_eff` (section 3). |
| `src/ui/main_window_mixins.py` | `TeamSimulationMixin` and `ArcEfficiencyMixin` add the page builders to the main window (and, since 2.3.2, the update and about-link controllers of section 8). |

The generated team tables are produced by `build_tools/gen_team_form_actions.py`, `gen_team_rotation_data.py`, `gen_team_custom_actions.py` and `gen_team_resource_data.py` (run through `build_tools/g231_shims/` for this tree). Some of their inputs (the game's static database and research notes) are not in this repository; the generated files are the form in which the tables are maintained here and can be edited directly. The header "GENERATED FILE - DO NOT EDIT" in these files was written for the author's working tree, where the generator inputs exist.

Team Simulation numbers differ from Global 2.3.0. Two causes: the 2.3.1 game data (graduation templates and arc rows of 黑羽 Raven and 明音凛 Akane Rin changed upstream), and B1–B4 above. Typical effects: teams with a character whose arc has an always-on bonus are about 1–11 % lower (B2), teams with Crime and Punishment or Antipode of the Moon are higher (B3 / B4), and a member whose arc was changed from the template now gets that arc's stats (B1). Every changed number was traced to one of these causes (89 test scenarios, 52 changed by the corrections, none without the corrected arc in the team). The development switch `NTE_TEAM_FORK_CORRECTIONS=off` turns the corrections off; the Arc Efficiency table then does not use its precomputed rows. The numbers change again in 2.3.2 (sections 9 to 12).

## 3. Arc Efficiency Table (Beta) — new feature

A new page in the sidebar, below Team Simulation. For every character with an exclusive arc it compares the arcs the character can equip by the damage of the character's reviewed solo rotation. Since 2.3.2 the page also holds the awakening efficiency table (section 10) and the Puka Boot Camp template switch (section 12).

| File | Purpose |
|---|---|
| `src/features/arc_efficiency/__init__.py`, `page.py`, `table_view.py` | The page: character list (best alternative and where the row came from), the arc table (rank, R1 %, max-refinement %, refinement gain, notes, optional damage columns), legend, notice, options (3 loops / 1 loop, basis "exclusive R1 = 100 %" / "same refinement", show or hide other characters' exclusive arcs †, damage columns), "Open in Team Simulation". Options are saved in `config/arc_efficiency_preferences.json` (not per account). |
| `src/services/arc_efficiency_service.py` | The calculation: the character alone, official graduation template, only the arc and its refinement swapped, reviewed rotation, Lv80 dummy, the Team Simulation engine with the corrections of section 2. It decides per character whether the precomputed rows can be used (same game data and the same calculation code), otherwise it recomputes in the background, the viewed character first, and caches the result on this PC (`config/arc_efficiency_cache.json`). |
| `src/services/arc_efficiency_notes.py` | Per-arc notes: which effects the solo calculation cannot reflect (support skill, teammates, team makeup, Cycle / Break intensity, hits taken …). |
| `src/services/arc_efficiency_data.py` | Generated: the precomputed rows (11 characters × the arcs each can equip × refinement 1 and max × 1 and 3 loops; since 2.3.2 for Puka Boot Camp level 0 and level 20) with the hash of the game database and a fingerprint of the calculation code. Generator: `build_tools/gen_arc_efficiency_data.py`. |

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
| `src/services/work_mode_runtime.py` | Passes the application root and the deployment record to the clean-up so it can read the known hashes (and, since 2.3.2, the RTSS check of section 13). |
| `src/ui/controllers/native_plugin_deployment_ui.py` | Shows the foreign-file message, and notes a kept file in the success dialogs. |

The hot plugin update of 2.3.1 (`src/services/native_plugin_update.py`) is unchanged: it only replaces plugin files the running host reports as loaded with the same SHA-256.

## 6. Battle-report replay — Python reference arithmetic

| File | Change |
|---|---|
| `src/services/battle_special_replay_numeric.py` | Hex (覆纹) follow-up copy ratio with Linko's passive in `python_special_numeric`: `0.30` → `0.33` (20% + 13%, as documented upstream for the analysis component). This path runs when no native compute backend takes the job; results computed by the bundled analysis component are unchanged. Team Simulation does not go through this path for Hex: it applies its own post-replay formula (`apply_hexed` in `src/services/team_cycle_reactions.py`), which uses the same 0.33. |

The bundled native analysis component (`nte-analysis-core.exe`) is not modified in any version of this build. It still computes battle reports from the game data it was built with (for Akane Rin: the pre-release data, section 11).

## 7. Adjustments needed by the localisation

Search, layout and input:

| File | Change |
|---|---|
| `src/features/static_catalog/domain_pages/character_page.py`, `equipment_page.py`, `fork_page.py`, `monster_page.py` | Search boxes also match Korean text and Korean initial consonants (`ko_contains`). |
| `src/features/allocation/execute_page.py` | Two result-header buttons use a minimum width instead of a fixed size, so longer translations fit. |
| `src/features/settings/work_mode_card.py` | The work-mode labels and the "检测并处理" (Check and Fix) button use a minimum width instead of a fixed width (the official 96 px button is 3 px too narrow even for the Chinese text). |
| `src/features/toolbox/cultivation_stamina_ui.py` | The stamina hint wraps, so the cultivation page has no horizontal overflow at the default window size in any language. |
| `src/features/static_catalog/domain_pages/character_profile.py` | The quality badge uses the quality keys (`S 级` / `A 级`) instead of the level template, so it is not translated as a level. Since 2.3.2 the profile also shows Akane Rin's CN release (section 11). |
| `src/features/battle_report/timeline_view.py` | The fallback avatar letter is taken from the displayed (translated) name. |
| `src/features/identification/controller.py` | Manual input on the Appraisal page: stat names shown in the current language are mapped back to the internal names before parsing. |
| `src/ui/plain_text_edit.py` | Paste inserts through the text cursor so the display layer does not translate the text the parser reads. |
| `src/ui/operation_guidance.py` | The "current mode does not allow this feature" message is one template, so the mode name can be placed by the translation. |
| `src/features/settings/component_upgrade_dialog.py` | The upgrade step text is rendered in the active language before the method name is filled in (after a live language switch it stayed Chinese). |
| `src/ui/rich_tooltip.py` (new in 2.3.2) | Rich-text tooltips shown as given: the display layer does not translate them a second time (which doubled kept terms such as "지식(蜘识)"), and long tooltips wrap. Used by the awakening and efficiency tables. |

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
| `src/features/settings/page.py` | Compares against the translated message as well as the Chinese fragment. (The original's `src/ui/controllers/update_controller.py`, which had the same fix in 2.3.1-global.1, is removed in 2.3.2, section 8.) |
| `src/features/static_catalog/domain_pages/monster_page.py`, `monster_detail_view.py`, `src/services/static_catalog_monster_feast.py`, `src/services/static_catalog_mechanics_service.py` | Section titles, level labels, category suffixes and field tones are matched in any language. |

Fixes relative to the earlier Korean patch (<https://github.com/LuinDe/NTE-Drive-Calc-KO>), not relative to the original: in that patch some dictionary keys were translated on one side only. For example, the save / manage confirmation of the inventory page failed because `counts['弃置']` no longer matched. In this tree both sides use the same wrapped key (`src/features/inventory/warehouse_controller.py`, `src/features/static_catalog/domain_pages/monster_detail_view.py`).

## 8. In-app updates (Global only) — new in 2.3.2

The original's update function is removed and replaced by an updater that only knows this repository. Global is developed and updated independently of the original from this version on.

Removed original files:

| File | What it did |
|---|---|
| `src/features/settings/updates.py` | The update section of the settings page: version check against the original project's releases and Mirror酱, links to the official installer and the netdisks. |
| `src/ui/controllers/update_controller.py` | Start-up update check (1.2 s after start, every start), download and opening of the official installer, the update dialogs. |

New files:

| File | Purpose |
|---|---|
| `src/app/global_release.py` | Version identity and channel constants: `GLOBAL_VERSION` (`2.3.2`), the upstream base (`2.3.1`, information only), the only repository asked (`LuinDe/NTE-Drive-Calc-Global`), asset names derived from the tag, size limits, the check interval (start-up check at most once per 20 hours), and `RELEASE_SIGNING_KEYS`, the pinned Ed25519 public key of the maintainer (fingerprint `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`; written by `build_tools/pin_release_key.py`). |
| `src/services/global_update/client.py` | Release discovery (`GET /repos/LuinDe/NTE-Drive-Calc-Global/releases`, never another host or repository) and installer download. Drafts and prereleases are ignored; tags must follow the Global grammar; a release is offered only when it is newer than the running version, carries the expected assets and a manifest with a valid signature. |
| `src/services/global_update/verify.py` | Integrity gates, standard library only: Ed25519 (RFC 8032) and OpenSSH `sshsig` verification in pure Python (namespace `nte-drive-calc-global-release`), manifest parsing and comparison with the release (tag, version, installer name / size / SHA-256, exe SHA-256, minimum running version, notes digest), SHA-256 and PE checks of the download. |
| `src/services/global_update/state.py` | Update state in `updates\state.json` under the program folder (last check, skipped version, staged download; never a path). |
| `src/services/global_update/launcher.py` | Pre-flight and hand-off to the installer: re-verifies the staged file, takes `updates\update.lock`, runs Setup with `/SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /MERGETASKS=!installvigem /LANG=<ui language> /AUTOUPDATE=1 /RELAUNCH=0|1` and its own temp folder. |
| `src/services/global_update/models.py`, `notes.py`, `env.py` | Shared types and error codes; the release notes in the user's language (one `## <language>` section of the release body, shown only when the body matches the signed `notes_sha256`); restoring `TMP` / `TEMP` after a relaunch through Setup. |
| `src/features/settings/global_update_card.py`, `global_update_dialog.py`, `global_update_texts.py` | The "Software Update" card in Settings (Global version, upstream base, release-key fingerprint, [Check for Updates], [Open release page], "Check for updates at startup (at most once a day)"), the update dialog ([Update Now] / [Later] / [Skip This Version], download progress, [Install and Restart Now] / install on exit, errors) and their texts. |
| `src/features/home/global_update_banner.py` | The banner on the home page (update available, download ready, updated). |
| `src/ui/controllers/global_update_controller.py` | The state machine: start-up check, manual check, download in daemon threads (a stalled connection never keeps the program alive), install on request or on exit, relaunch. |
| `src/ui/controllers/about_links_controller.py` | About / credit links: update, download, release and issue links lead to this repository; the original project's GitHub home page, Bilibili, support and QQ / Discord links stay as attribution. |
| `src/utils/atomic_json.py` | Atomic JSON writes (temp file, fsync, replace). |

Changed original files:

| File | Change |
|---|---|
| `src/app/constants.py` | The original's release, Mirror酱 and netdisk URLs are removed; `GITHUB_HOME_URL` (the original project) stays for attribution. |
| `src/features/settings/page.py` | Shows the "Software Update" card instead of the removed update section. |
| `src/features/home/page.py` | Hosts the update banner. |
| `src/ui/app.py`, `src/ui/main_window_mixins.py` | Create the update and about-link controllers. |
| `src/ui/main_window_theme_mixin.py`, `src/ui/controllers/hotkey_controller.py`, `src/ui/main_window_data_mixin.py` | The original's account-scoped update preferences and netdisk links are removed; closing the window asks about a running download or a ready update. |
| `src/ui/work_mode_composition.py` | `app_update_blocker()`: no installation while the work mode is switching, a battle is being recorded or a hotkey owner is active. |
| `src/ui/gui_startup.py` | Restores `TMP` / `TEMP` after a relaunch through Setup. |

The installer (`build_tools/build_installer_g231.py`) has a relaunch entry that runs only for a silent install with `/AUTOUPDATE=1 /RELAUNCH=1`, and removes `{app}\updates` on uninstall. The release manifest (`NTE_Drive_Calc_<version>_release.json`) is written by the same tool and signed by the maintainer with `ssh-keygen -Y sign` (namespace `nte-drive-calc-global-release`); `build_tools/verify_release_manifest.py` checks a signed release locally or on GitHub. 2.3.1-global.1 has no updater, so the first update to 2.3.2 is a manual install.

Version grammar (extended in 2.3.2): a Global version is `<major>.<minor>.<patch>` or, as written by the releases up to 2.3.1-global.2, `<major>.<minor>.<patch>-global.<n>` with n ≥ 1; a tag is `v` followed by the version. Only ASCII digits, no leading zeros, every part at most 65535, no spaces or line breaks; the whole string must match. Versions are ordered by (major, minor, patch, n), with n = 0 for the plain form, and the Windows file version is major.minor.patch.n (2.3.2 → 2.3.2.0). The build tools refuse a `--version` that is not newer than 2.3.1-global.2. Everything else of the updater is unchanged (only this repository, signature, notes digest, download hosts, size limits), and the minimum running version (`FIRST_AUTO_UPDATE_VERSION`, the manifest's `min_global_version`) stays 2.3.1-global.2. 2.3.1-global.2 itself reads only the `-global.<n>` form, so it is not offered 2.3.2 in the program.

## 9. Team Simulation: ultimate energy, Esper-Cycle gauge, cooldowns and the swap rule — new in 2.3.2

| File | Purpose |
|---|---|
| `src/services/team_resources.py` (new) | `ResourceState` per layout: ultimate energy and the Esper-Cycle gauge gained per hit (`charge_add`, `heterochrome_add` of the game data), energy costs, cooldowns on combat time without time stops, awakening-dependent cooldown rules, Hotori's clock. `ResourcePolicy`: in a team, a skill still on cooldown for `SWAP_MIN_WAIT_S` = **0.3 s** or more, or an ultimate without enough energy, hands over to the next member; below 0.3 s the member waits; when nobody is ready, the earliest member waits. Solo layouts (efficiency tables) always wait. Resource models: `community` (default: game data plus community cooldowns), `data` (game data only), `legacy` (the old rule: no energy / cooldown check, gauge refilled to 100 at the start of loops 1 and 3). |
| `src/services/team_resource_data.py` (new, generated by `build_tools/gen_team_resource_data.py`) | Per character and value: number or unknown, source (game data, description text, the user's recordings, prydwen.gg, GameWith) and confidence. Unknown values are never guessed; the explanation panel lists them. |
| `src/services/team_simulation_service.py`, `team_custom_cycle_service.py`, `team_cycle_reactions.py`, `team_simulation_explanation.py` | Drive the resource state, apply the swap rule, record waits / swaps / energy / gauge events, and explain them. Custom Input: check modes off / warn (default) / wait / strict; "strict" uses the same rules as the reviewed rotations. |
| `src/features/team_simulation/page.py`, `explanation_view.py`, `custom_panel.py`, `custom_view.py` | Resource-model choice (remembered per account), resource rows in the explanation, custom-cycle options. |
| `src/services/arc_efficiency_notes.py`, `arc_efficiency_data.py` | Notes and precomputed rows follow the resource model (some solo rotations now wait for cooldowns). |

## 10. Awakening (觉醒, Korean UI 돌파): free choice, node rules and the awakening efficiency table — new in 2.3.2

In the game an awakening level gives one slot, and the six effects can be chosen in any order; the resonances turn on at levels 3 and 6 whatever is chosen. Global 2.3.1-global.1 assumed "level N = effects 1..N".

| File | Purpose |
|---|---|
| `src/services/team_awakening.py` (new) | A member's awakening = level plus a free set of effects. Old saved teams and cycles (a level only) are read as effects 1..N; the saved key is `selected_awaken_effect_ids`. |
| `src/services/awakening_node_rules/` (new: `__init__.py`, `core.py`, `g0.py` – `g3.py`) | Rules for 192 awakening nodes of the 24 template characters, one module per group of six characters: 129 are computed (one as an expected value), 34 are marked "needs measurement" and 29 "not computable" (healing, shields, being hit, several targets …); unmodelled nodes are never shown as 0 %. Lacrimosa ③ settles the remaining damage over time at once and removes that stack. |
| `src/services/awakening_efficiency_service.py`, `awakening_efficiency_notes.py`, `awakening_efficiency_data.py` (new; rows generated by `build_tools/gen_awakening_efficiency_data.py`) | The awakening efficiency table: per character and node, the DPS change of adding one effect to A0 and of removing one from A6, resonance 3 / 6 and all six, for 1 and 3 loops. Recomputed on the PC when the rows do not match the data or the code. |
| `src/features/arc_efficiency/awakening_section.py` (new), `page.py`, `table_view.py` | The "Character Awakening Efficiency (Beta)" section under the arc table (collapsed at first, scrollable). |
| `src/features/team_simulation/awakening_text.py` (new), `page.py` | The member cards: six effect toggles, "Awakening n/6" (Korean "돌파 n/6"), node tooltips with the rule marks. |
| `src/services/team_simulation_service.py`, `team_custom_cycle_service.py`, `team_custom_cycle_store.py`, `team_custom_cycle_texts.py`, `team_simulation_explanation.py` | 17 places that assumed "level N = 1..N" (including Mint ①, Haniel ⑥, Adler ⑤, Zero ②, Linko ③ resource rules) now read the selected set. |
| `src/i18n_data_*.py`, `src/i18n_display.py`, `src/i18n_desc.py` | Korean term change (觉醒 = 돌파, 突破 = 레벨 돌파) and the new texts. |

## 11. Akane Rin (明音凛): CN-release data overlay — new in 2.3.2

The bundled game database (dataset `cn_retail_20260924`) holds Akane Rin's pre-release values. Values of the CN release (2026-10-15) on which at least two independent sources agree replace them at run time; the database file is not changed.

| File | Purpose |
|---|---|
| `src/services/global_live_overlay_data.py` (new) | 77 fields: 46 replaced, 13 already equal, 15 kept from the database and marked unverified (sources disagree or only one source), 3 unknown (E and Q cooldown, ultimate energy). Release status, awakening effects ①–⑥, resonances, 「烁星激昂」 (ATK +20 % for 20 s after each stage-1 ultimate), the ultimate's stage-2 window, the exclusive arc 「月的对跖点」 (Skill damage +28 % … +56 %, no stacks). |
| `src/services/global_live_overlay.py` (new) | On only when the running database is exactly the 9-24 one (dataset id and SHA-256); otherwise it switches itself off. Development switch `NTE_GLOBAL_OVERLAY=off`. |
| `src/storage/sqlite/static_game_data_dao.py`, `static_catalog_character_queries.py` | Apply the overlay's text and release rows when reading. |
| `src/features/static_catalog/domain_pages/character_profile.py`, `src/features/battle_report/analysis_view.py`, `src/services/team_fork_corrections.py` | Release line in the profile; a one-line notice on battle reports that contain Akane Rin (the native analysis component still uses the pre-release data); B4 follows the release arc text. |

Sources: the official CN notices (yh.wanmei.com, 10-14 / 10-15 / 10-16), in-game screenshots of the CN release client (forum.gamer.com.tw), TapTap guides, Japanese guides that state they describe the Chinese version (kamigame, AppMedia, GameWith) and, for the arc only, LDShop. Unverified fields: Lv80 base stats, skill multipliers, the basic-attack conduction base values, the 华彩连段 duration and five mechanics that only one source describes, the arc's R1 crit rate and Lakshana bonus (sources disagree: 16 % vs 15 / 20 %; the database's 16 % is kept) and R2–R5 values. Graduation template, recommendation weights and Korean / English / Japanese names are not part of the overlay.

## 12. Puka Boot Camp (噗卡特训) — new in 2.3.2

The account-wide progression of game version 1.4 (levels 0–20; at Lv 20: ATK +28, DEF +30, HP +420, CRIT Rate +2.5 pp, CRIT DMG +5 pp, cycle intensity +12, break intensity +12) applies to deployed characters.

| File | Purpose |
|---|---|
| `src/services/puka_training_data.py` (new, generated by `build_tools/gen_puka_training_data.py` from `build_tools/data/puka_training_levels.json`) | The level table (required plan level, cost, cumulative stats). |
| `src/services/puka_training_settings_service.py` (new) | The account's level (default 0) and options (`native_overrides` on by default, `template_max` off by default); `account_bonus_property_stats` = furniture bonus + training. |
| `src/services/puka_training_override_service.py` (new) | "All Boot Camp stats": the training stats that the native analysis component cannot rebuild by itself are injected into recomputed modified copies and marginal comparisons. |
| `src/services/official_role_attribute_service.py`, `official_role_graduation_service.py`, `official_role_page_service.py`, `official_role_scoring_service.py`, `src/features/official_role/controller.py`, `role_calculation.py`, `role_growth.py`, `role_shell.py` | Character panels and marginal gains include the training; the level is entered on the Furniture Bonus card of the character page; a crit rate already at 100 % gains nothing more. |
| `src/services/battle_*` (8 files), `src/storage/sqlite/battle_analysis_dao.py`, `battle_build_edit_dao.py`, `src/features/battle_report/build_snapshot_control.py`, `build_snapshot_controller.py`, `marginal_page.py`, `my_build_comparison.py`, `page.py` | Battle reports freeze the level when recording starts (older reports count as Lv 0); the frozen rows carry the prefix `噗卡特训·`; the "All Boot Camp stats" switch. |
| `src/features/allocation/role_selector.py`, `role_selector_help.py`, `role_selector_preferences.py`, `src/features/inventory/equipment_graduation_controller.py`, `src/services/allocation_catalog_service.py`, `legacy_allocation_static_catalog.py` | Graduation rate and allocation use the account's level; the crit-rate cap counts the training. |
| `src/services/arc_efficiency_service.py`, `src/features/arc_efficiency/page.py`, `src/features/team_simulation/page.py` | "View at Puka Boot Camp max (Lv.20)": the graduation template of the efficiency tables at level 0 or 20 (both precomputed); Team Simulation uses the account's level. |

## 13. RTSS (RivaTuner Statistics Server) compatibility notice — new in 2.3.2

On the author's PC the game crashed at start (`D3D12Viewport.cpp:554`, `80004004 E_ABORT`) when RTSS with its default hooking ran together with the 2.3.1 in-game component. The check is read-only; RTSS settings are never changed.

| File | Purpose |
|---|---|
| `src/services/rtss_compat.py` (new) | Reads whether RTSS is running and how the `HTGame.exe` profile hooks (`UseDetours`); result ok / risk / unknown. |
| `src/services/rtss_compat_guidance.py` (new), `src/ui/controllers/rtss_compat_notice.py` (new) | Texts and the reminder before the calculator injects into the game ([Start native Loader] / D3D deploy): fix steps (add `HTGame.exe`, Setup → General → "Use Microsoft Detours API hooking"), check again, continue, cancel, or turn the reminder off for the account. The reminder opens as tall as its text needs at its width (on a screen too small for that the text scrolls and the buttons stay visible). |
| `src/domain/work_mode.py`, `src/services/work_mode_checks.py`, `work_mode_runtime.py`, `src/ui/controllers/environment_controller.py`, `mod_loader_controller.py` | The risk appears as an advisory item in "Detection Details" (it never blocks readiness); the reminder hook before injection. |

## 14. Other changes in 2.3.2

- Japanese: skill names in the Custom Input palette tooltips (nine lines were Chinese); 小吱 is 「ちぃちゃん」 everywhere (`src/services/team_custom_actions.py`, `src/i18n_data_ja.py`); the English description name is "Chiz".
- Team Simulation member cards: long character names (for example Lacrimosa) no longer cut off in the character selector (shortened with "…" and a tooltip when they still do not fit).
- The sidebar title reads "NTE Drive Calc Global" (`src/ui/main_window_navigation_mixin.py`).
- New in 2.3.2: the avatar in the home page's work-space header (工作台) shows Akane Rin (明音凛, character 1057) instead of Raven (黑羽, 1042), from the same verified character image catalogue (`src/features/home/page.py`; `data/role_catalog/game_ui` is unchanged).

## 15. Outside `src/`

| Item | Change |
|---|---|
| `config/templates/guide/1.png` – `7.png` | The seven "how to use" tutorial images are replaced by Korean versions. The program has one image set, so they are Korean in every language. |
| Executable `NTE_Drive_Calc.exe` | The official 2.3.1 PyInstaller executable (SHA-256 `5b8fa8d2…e8c3`) with only the `src.*` records of its PYZ archive replaced: 257 records kept as they are, 634 recompiled from this tree, 91 added (the 69 new files, and 22 modules that exist in the original source but that the official build did not bundle because nothing imports them), 2 removed on purpose (`src.features.settings.updates`, `src.ui.controllers.update_controller`). The 2,008 other PYZ entries and every other archive entry are byte-identical; the PE checksum is recomputed. Script: `build_tools/rebuild_exe_l10n.py` (with `--remove=` for the two modules); proof: `build_tools/verify_exe_l10n_g231.py`. |
| Installer | `build_tools/build_installer_g231.py`, a port of the original `build_installer.py` at the baseline commit. Same application ID, default folder, privileges, `[Files]` / `[InstallDelete]` / `[Dirs]` structure as the official 2.3.1 installer, so it upgrades an official install in place and a later official installer installs over it. Differences: a setup wizard in four languages, the product is named "NTE Drive Calc 2.3.2 Multilingual Edition (Global)" (localised; the number is the Global version) with a publisher string that says unofficial, a notice page, the folder `l10n_build` with `LICENSE.txt`, `README.txt` and `SOURCE_OFFER.txt`, the program's start language is written from the setup language only when no language was set before, and the language file is removed on uninstall. Since 2.3.2: `AppVersion` is the Global version, file version major.minor.patch.n (2.3.2.0), asset names carry the Global version, the in-app update relaunch entry and `{app}\updates` removal of section 8. |
| Release manifest | Since 2.3.2 every release carries `NTE_Drive_Calc_<version>_release.json` and its signature `.sig` (section 8). |
| `_internal/`, `drivers/` in the installer | Copied from the official 2.3.1 installation without change, except the seven tutorial images. |

## 16. Changes from 2.3.1-global.2 to 2.3.2

Global 2.3.2 contains everything of 2.3.1-global.2, which was published briefly on 2026-10-19, plus:

- Version numbers: Global's version number is now independent of the original's, and this release is plain **2.3.2** everywhere (program, installer, file names, tag `v2.3.2`). Global 2.3.2 is based on the official 2.3.1; `src/app/version.py` stays `2.3.1`. The version grammar is extended to the plain form (section 8).
- The home page's work-space header shows Akane Rin instead of Raven (section 14).
- A 2.3.1-global.2 install does not recognise the new version format, so it is not offered 2.3.2 in the program: install 2.3.2 once by hand, as from 2.3.1-global.1.

## 17. Changes since 2.3.1-global.1

For users of the previous release, in short:

- In-app updates from this repository only, with a signed release manifest; the original's update function is removed (section 8). The first update from 2.3.1-global.1 is a manual install.
- Team Simulation: ultimate energy, Esper-Cycle gauge and cooldowns for all 24 characters, and the 0.3 s swap rule (section 9).
- Awakening (돌파) chosen freely, node rules, and the awakening efficiency table (section 10).
- Akane Rin on CN-release data (section 11).
- Puka Boot Camp (section 12).
- RTSS compatibility notice (section 13).
- Version numbers independent of the original, and the home avatar (section 16).
- Fixes listed in section 14.

## 18. Changes from Global 2.3.0 to 2.3.1-global.1

- Based on the official 2.3.1 (everything the original added in 2.3.1, including the cultivation history and the plugin-based in-game components).
- New Arc Efficiency Table (Beta) (section 3).
- Team Simulation: arc corrections B1–B4 (section 2), so its numbers change.
- Game-folder protection rewritten for the 2.3.1 component layout (section 5).
- Translations: about 700 new 2.3.1 strings in three languages; the Korean texts take the wording of the Korean patch for 2.3.1 (official Korean skill names, 倾陷 = 붕괴, 援护技 = 서포트 스킬); 288 older game descriptions are now translated into English and Japanese as well.
- Fixed: value slots of 9 translated templates (section 1), `&` in English buttons and tabs being read as a keyboard shortcut (now "and"), and a few English and Japanese terms.
