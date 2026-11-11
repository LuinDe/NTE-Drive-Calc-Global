# NTE Drive Calc Global

[한국어](README.md) · [简体中文](README.zh.md) · [English](README.en.md) · [日本語](README.ja.md)

**An unofficial multilingual derivative of NTE Drive Calc, independently maintained by LuinDe.** It began as a Korean patch and expanded with translations and calculation tools. This is not an official Global edition published or supported by the original author.

## Original author and project

- Original author: **[hxwd94666](https://github.com/hxwd94666) and NTE Drive Calc contributors**
- Original source: **[NTE-Drive-Calculator](https://github.com/hxwd94666/NTE-Drive-Calculator)**
- Original releases: **[NTE-Drive-Calc](https://github.com/hxwd94666/NTE-Drive-Calc)**
- Global maintainer: [LuinDe](https://github.com/LuinDe). Report Global issues in [this repository](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues).

Original links are retained for attribution. The original repositories were inaccessible when checked on 2026-11-07; the reason has not been established. This project does not claim official endorsement, support or joint authorship by the original author.

## Current release: 2.3.7

**[Download v2.3.7 and read the release notes](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.7)**

For Windows 10/11 x64. The installer is `NTE_Drive_Calc_2.3.7_Multilingual_Setup.exe`; the public source archive is `NTE_Drive_Calc_2.3.7_Multilingual_source.zip`.

- Elyms (1090) launched on the Korean server on 2026-11-11, so her data now follows the **Korean server**. In the Korean UI her skill, Awakening, Resonance, passive and Arc names and descriptions use the Korean server's game text (live 1.5.4 Korean data of [nte.nanoka.cc](https://nte.nanoka.cc/)), and Korean cultivation material names follow the same data.
- The Korean UI's Elyms catalog profile shows the teams and rotations community players actually use, for reference only (not used in calculations).
- Stats, skill multipliers, Arc values and the equipment layout match the values confirmed on the Korean server and are unchanged.
- The home page (Workbench) avatar now shows Elyms (PNG).
- Fixes the 2.3.3–2.3.5 startup error ("Standalone character catalog unavailable"). A catalog that fails validation (such as an image format error or a damaged image list file) no longer stops the program; it starts with the complete game database and shows a warning.
- Measured Elyms DPS rotations are not ready, so Elyms is excluded from team simulation and rotation-based efficiency tables. Inventory synchronization with a live game session has not yet been verified.

The existing 2.3.6 installer's statement that the ZIP contains all Corresponding Source is inaccurate; read the [correction](docs/SOURCE_OFFER_CORRECTION_2.3.6.md).

## Features

- Korean, Simplified Chinese, English and Japanese UI, switchable in the application.
- Upstream inventory synchronization, equipment appraisal/allocation, character management and battle reports.
- Team Simulation (Beta), custom rotations, and arc/awakening efficiency tables.
- Puka Boot Camp adjustments, personal-character comparisons in battle reports, and Global updates with signature verification.

Calculations are estimates within the implemented model and available data. They do not reproduce every character effect or combat situation. See the [Elyms notes](build_tools/ELYMS.md) for scope and data provenance.

## Install and use

1. Close the calculator and back up existing account and settings data.
2. Download and run the [v2.3.7 installer](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.7). It uses the existing installation location and is designed to preserve user data.
3. Select a language using the buttons at the bottom left. See the [usage guide](docs/USAGE.en.md) for simulation and efficiency-table controls.

Versions 2.3.3–2.3.5 (startup error) and 2.3.3 and earlier (no Global updater or the old signing key) require a one-time manual installation of 2.3.7; 2.3.6 can update in-app. Subsequent update checks use this Global repository. Game-connection compatibility depends on the game build and native components.

## Source and licensing status

The application follows the upstream [GNU AGPL-3.0](LICENSE). Original copyright and Global modification notices are retained in [NOTICE](NOTICE). Bundled components have their own licenses.

- Published: modified `src/`, bootstrap, dependency lockfile, upstream and Global build tools, public native prototype, adaptation materials and license records.
- **Unresolved:** this repository and ZIP do not provide the exact complete Corresponding Source for the distributed Core, analysis Core and Loader (AGPL), or the five capture DLLs (GPL). The `native/` prototype and Elyms resource adaptation scripts are not substitutes for that source.
- Game artwork and data remain the property of their respective rights holders. This supplement does not establish that all redistribution conditions are satisfied.

[Source coverage and remaining gaps](SOURCE_OFFER.md) · [Build guide](build_tools/README.md) · [Restored files and hashes](UPSTREAM_SOURCE_FILES.json) · [Historical source](docs/source-history.md)
