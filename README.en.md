# NTE Drive Calc Global

[한국어](README.md) | **English** | [日本語](README.ja.md) | [中文](README.zh.md)

> [!IMPORTANT]
> **This is not the original program. It is an unofficial build made by modifying the original.**
>
> **Original (official) project: [NTE Drive Calc — hxwd94666/NTE-Drive-Calculator](https://github.com/hxwd94666/NTE-Drive-Calculator)**
> <https://github.com/hxwd94666/NTE-Drive-Calculator>
>
> - NTE Drive Calc Global is a **derivative build: [LuinDe](https://github.com/LuinDe) modified the source code of the official NTE Drive Calc 2.3.0**, which was created by [hxwd94666](https://github.com/hxwd94666) and the NTE Drive Calc contributors.
> - **It is not an official release.** The original author did not make, review or support this build.
> - Please report problems with this build in **[this repository's Issues](../../issues)**, not in the original repository. Do not contact the original author about it.
> - If you want the official version, get it from the original link above.
> - Thank you to the original author and contributors for creating the program and publishing its source under AGPL-3.0. The core features of this build (Drive calculation, scanning, sync, battle report and the rest) are theirs. The parts listed under "What was changed from the original" below, such as Team Simulation, were added or changed in this build; errors in them are not the original author's.

## What this repository is

[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) (异环驱动计算器) is a Windows calculator for Drive and Cartridge progression in the game Neverness to Everness (NTE / 异环). It reads your inventory, appraises items, calculates loadouts for your characters and equips them in the game automatically. For the full feature description, see the [original README](https://github.com/hxwd94666/NTE-Drive-Calculator#readme).

**NTE Drive Calc Global** is an unofficial modified build based on the official 2.3.0 that

- lets you use the interface in **Korean / English / Japanese / Chinese**, and
- adds a few features such as **Team Simulation (Beta)**.

This repository holds the modified source code (`src/`) and the build tools. The installer is available from [Releases](../../releases).

![Team Simulation (Beta) — English](docs/images/team_sim_en.png)

## What was changed from the original

A detailed, file-level list is in [CHANGES.md](CHANGES.md).

### 1. Four languages

- The interface language can be **中文 (the original text) / 한국어 / 日本語 / English**. Click the **language buttons at the bottom left** of the program: the language changes immediately while the program is running (no restart), and your choice is saved.
- About 9,300 interface strings are translated per language. Names of characters, sets, Arcs, skills and monsters, effect descriptions and battle report texts are shown translated as well.
- Korean uses the official names of the Korean game client. English and Japanese follow each language's client where the terms could be confirmed; names that could not be confirmed (for example content not yet released in that language) may be provisional translations or left in the original text.
- The search boxes of the game database (characters, equipment, Arcs, monsters) accept Korean text and Korean initial consonants (Chinese search works as before).
- The installer is in four languages too.

![The four languages and the language buttons at the bottom left](docs/images/languages.png)

### 2. Team Simulation (Beta) — new feature

> [!WARNING]
> **This feature is unfinished.** The program shows the same warning: *"This feature is unfinished. The rotation review is not complete yet, so results may differ from real battles."*
> It is meant for a rough comparison of team strength and does not guarantee real combat results.

- Pick four members and it calculates the team's total damage, DPS and each member's contribution. You can choose Awakening, Arc, Refinement and Cartridge Set per member; Drives and main/sub stats follow the official graduation template (it does not use the equipment in your own inventory).
- **Reviewed Rotation**: rotations for 24 characters are built in, and the team runs 3 loops.
- **Esper Cycle reactions are always computed.** When swapping to an adjacent-element member, Blossom, Hex, Scorch, Nova, Stain and Remora, plus Charge and Discord, are handled (Remora, Charge and Discord are shown as effects without damage).
- **Attacks in transformation / form states** are included (Zankou, Raven, Shinku, Hathor, Akane Rin, Yi and others).
- You can choose the **Swap Order**: Auto (transformation DPS first) / Auto (most reactions) / Team slot order.
- **Explanation panel**: below the result it shows the rotation used, the swap order and why it was chosen, a table of Cycle reactions, the rotation per member, and the assumptions and limits.
- **Custom Input mode**: write a rotation as text and calculate it. It has options for the Cycle Value, cooldowns, buffs and numbers, and rotations can be saved under a name and loaded again. For the notation, see [Usage](#usage) below.

### 3. Battle Report: Compare with My Characters — new feature

In an imported battle report, the characters you also own are replaced with your own build and current equipment, the same battle is recalculated, and the result is compared with the original. It is read-only: no saved data is changed.

### 4. Protection for other programs' files in the game folder

When deploying or cleaning up the "in-game components", `d3d12.dll` / `NTE_Capture.dll` in the game folder are replaced or deleted **only when they are confirmed (by SHA-256) to be this program's own files**. A file that cannot be confirmed (for example ReShade installed as `d3d12.dll`) is neither overwritten nor deleted. In that case deployment stops and a message is shown. Only these two file names are covered; the original's removal of its old-style `dwmapi.dll` from the game folder is unchanged.

### 5. Calculation fix

The Python reference formula of the battle report replay still used a copy ratio of 0.30 for the Hex (覆纹) follow-up when Linko's passive is active; it is now 0.33 (20% + 13%), the value the original's documentation gives for its analysis component. This Python formula runs when a replay is calculated without the analysis component. Battle report figures calculated by the bundled analysis component (not modified) are not affected. Team Simulation does not use this formula for Hex: it has its own, newly written formula, which uses the same ratio (0.33).

### 6. Other changes

- Fixes for problems of the earlier Korean patch, such as an error at the save / manage confirmation step of the Inventory (仓库) page (a mismatch caused by translation).
- Korean and Japanese fonts take priority, button widths follow the translated text, and translated stat names are recognised in the manual input of the Appraisal page.
- The seven "Tutorial" images are replaced by Korean versions (these images are Korean whichever language you choose).
- An installer that installs the whole program.

### What was not changed

- The executable is the official 2.3.0 executable with only the `src.*` Python modules replaced. All other components (nte-core, the capture / loader components, the OCR model, the game's static database, the ViGEmBus driver and so on) are the same as in the official 2.3.0 distribution.
- The logic of everything that interacts with the game, such as scanning (OCR), sync and automatic equipping, is unchanged except for item 4 above and the text-matching adjustments that translation made necessary (section 6 of [CHANGES.md](CHANGES.md)). Those files did receive the string wrapping (`_L()`) needed for translation, and this build was not fully re-verified against the live game (see "What was checked" in [RELEASE_NOTES.md](RELEASE_NOTES.md)).

## Download and install

1. Download `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` from [Releases](../../releases). It contains the whole program, so you do not need to install the official version first.
2. Close NTE Drive Calc if it is running.
3. Run the installer and click "Yes" in the User Account Control (UAC) prompt.
   - The file is not code-signed, so the **"Windows protected your PC" (SmartScreen)** window may appear. Click "More info" → "Run anyway". Before running it you can check the file with the [SHA-256](#verifying-the-files-sha-256) values below.
4. Choose the setup language (the language of your Windows is preselected if it is one of the four; otherwise English).
5. Read the notice and click "Next" to finish. The additional tasks (desktop shortcut, ViGEmBus virtual gamepad driver) are the same options as in the official installer.

After a first installation the program starts in the language you chose for setup. If you had already set a language, that setting is kept.

### If NTE Drive Calc is already installed

- It installs to the **same location** as the official version (default: `C:\Program Files\NTE Drive Calc`) and under the **same program entry**. Just install it over the official 2.3.0, over an install with the [earlier Korean patch](https://github.com/LuinDe/NTE-Drive-Calc-KO), or over an earlier multilingual build. You do not need to uninstall first.
- **User data is kept.** Accounts, settings, Drive and inventory data, battle report records, logs and saved rotations stay. User files in the `accounts`, `config`, `data`, `logs`, `migration` and `scanned_images` folders are neither deleted nor changed (like the official installer, it only rewrites the default file `config\stats.json` and the static-database backup `migration\game_static.previous.sqlite3`).
- After installation the name in the Windows "Installed apps" list becomes "NTE Drive Calc 2.3.0 Multilingual Edition" (when installed in English).

## Going back to the official build

- Run the **official installer** (`NTE_Drive_Calc_Setup_2.3.0.exe`) again and install to the same location. The executable and the tutorial images become the official ones; user data stays. Get the official installer from the original project: <https://github.com/hxwd94666/NTE-Drive-Calculator>
- Running the installer of a later official version also installs the official build in the same place. The multilingual interface and Team Simulation are gone in that case.
- To remove the program completely, use Windows "Installed apps" (Apps & features) or the uninstall shortcut in the Start menu. As with the official version, uninstalling does not delete the user data folders.
- The installer of the earlier Korean patch was not made for this build. Do not use its "restore the original" option on top of this build; use the method above.

## Usage

### Changing the language

The buttons `中文` `한국어` `日本語` `English` are at the bottom left of the program. Click one and the language changes at once.

### Team Simulation

Open **Team Sim (Beta)** in the left menu, ① pick four members, ② set Awakening, Arc, Refinement and Cartridge Set for each member, then ③ click **Calculate Team**. The default mode is "Reviewed Rotation".

### Writing your own rotation

Click **Custom Input** and write `character action` steps in the **Notation** box, joined with `>`.

```text
Zero support > Zero E > Zero basic basic basic > Oneiroi swap > Oneiroi Q > Oneiroi E > Oneiroi basic
```

- **support** enters with the Support Skill. If the outgoing member's element is adjacent, an Esper Cycle reaction triggers. A support on the very first step only plays the skill, because there is no outgoing member.
- **swap** is a normal swap: no Support Skill and no reaction.
- Available actions: `support` `swap` `basic` `heavy` `E` `E-hold` `Q` `counter` `dodge` `plunge` `appear` `special` `wait` (which actions exist depends on the character)
- `basic basic basic` = `basicx3` = `basic 3 times`. Pick a specific hit of a chain with `#N` (for example `basic#4`). `wait 2` waits 2 seconds.
- Remarks in parentheses are ignored. Besides `>`, `→` and line breaks also work as separators.
- You can also build the steps by clicking the member and action buttons. Korean, Japanese and Chinese notation is accepted at any time.
- **▶ Options**: Cycle Value mode (As entered / Check Cycle Value) and Starting Cycle Value; E and Q cooldowns, Q energy cost and the check mode (No check / Warn only / Insert wait); turning the team buffs inferred by the engine on or off; manual buffs; repeat count; enemy level, RES, DEF reduction and vulnerability; swap time.
- Rotations can be **saved** under a name and **loaded** again. **Load Reviewed Rotation** imports a built-in rotation (1 loop or 3 loops) so you can edit it.
- The limits are 200 steps and 600 executed actions including repeats.

<details>
<summary>Show the result screen of Custom Input mode (the example above, Korean interface)</summary>

<img src="docs/images/custom_cycle_result_ko.png" alt="Result of Custom Input mode" width="520">

</details>

## Notes and risks

- **The requirements are the same as for the original.** Windows 10/11 x64; game language **简体中文 (Simplified Chinese)** (text recognition for scanning and appraisal is based on the Chinese game screen); recommended resolution 1080p, 2K, 4K or 2560x1600; the scan feature needs the ViGEmBus virtual gamepad driver. Follow the [original README](https://github.com/hxwd94666/NTE-Drive-Calculator#readme) for details.
- **Features that interact with the game carry risk.** The original program has work modes (Offline / Low Risk / Medium Risk / Development) and warns by itself that the Low Risk mode (packet capture, simulated input) and the Medium Risk mode (loading components into the game and operating inside it) *may trigger the game's protection or cause compatibility problems*. Apart from item 4 under "What was changed from the original" (protection of files in the game folder), this build does not change how those modes work, so the risk is at least the same as with the original. Before using them, read the notices inside the program and the [original documentation](https://github.com/hxwd94666/NTE-Drive-Calculator), and check the game's rules, the terms of service and your local law yourself.
- Language switching and Team Simulation also work in Offline mode and do not connect to the game.
- **Team Simulation is a Beta.** It assumes a stationary Lv80 training dummy with 20% resistance, and the Reviewed Rotation mode does not check cooldowns or energy. In Custom Input mode only two characters (Lacrimosa, Chaos) come with default cooldown / energy values; for the others you have to enter them yourself. Further limits are listed under "Assumptions and Limits" below each result and in [RELEASE_NOTES.md](RELEASE_NOTES.md).
- The installer and the executable are **not code-signed**.
- If you install a newer official version through the program's own update function or the official installer, the official build replaces this one.
- The original author does not support this build. **The GitHub, group chat (QQ / Discord), support, download and update links inside the program are unchanged from the original and lead to the original author's pages.** Do not report problems of this build there; use [this repository's Issues](../../issues).

## Verifying the files (SHA-256)

| File | Size (bytes) | SHA-256 |
|---|---:|---|
| `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` (installer) | 177,299,000 | `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177` |
| `NTE_Drive_Calc_2.3.0_Multilingual_source.zip` (source code) | 6,565,584 | `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113` |
| Installed `NTE_Drive_Calc.exe` | 23,750,579 | `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30` |
| (reference) Official 2.3.0 `NTE_Drive_Calc.exe` this build is based on | 20,920,550 | `505950ca2261902df6c78a61c3f17c6e756b82bb9309689ac08114c4f3a1cbbf` |

To check in PowerShell:

```powershell
Get-FileHash .\NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe -Algorithm SHA256
Get-FileHash "C:\Program Files\NTE Drive Calc\NTE_Drive_Calc.exe" -Algorithm SHA256
```

## Building from source

[`src/`](src) in this repository is the source of all `src.*` modules inside the distributed executable. The build tools are in [`build_tools/`](build_tools) (see [build_tools/README.md](build_tools/README.md)).

The executable is not repackaged from scratch. It is made by **replacing only the `src.*` modules in the PYZ archive of the official 2.3.0 executable with a compile of this source**; everything else is kept byte for byte. The executable embeds `python311.dll`, so **Python 3.11** is required.

```powershell
python build_tools/rebuild_exe_l10n.py <official 2.3.0 NTE_Drive_Calc.exe> src <output exe>
python build_tools/verify_exe_l10n.py  <official 2.3.0 NTE_Drive_Calc.exe> <output exe> src
```

The official executable used as the base has the SHA-256 `505950ca…cbbf` (the file installed by the installer of the original's release `2.3.0.1`). A build with CPython 3.11.15 (Windows x64) has the same SHA-256 as the distributed executable (`4d403af1…cb30`). Another 3.11.x may compress differently and give a different hash; in that case `verify_exe_l10n.py` confirms that the content matches this source.

The notice about the corresponding source is in [SOURCE_OFFER.md](SOURCE_OFFER.md).

## License

- NTE Drive Calc is distributed under the **GNU AGPL-3.0**. This build is a derivative work of it and is under the same license. Full text: [LICENSE](LICENSE); notices: [NOTICE](NOTICE)
- Original copyright: **NTE Drive Calc contributors** ([hxwd94666](https://github.com/hxwd94666)) — <https://github.com/hxwd94666/NTE-Drive-Calculator>
- Modifications: [LuinDe](https://github.com/LuinDe), 2026-10-05 (based on original commit `d3eca80`, the original's release tag `2.3.0.1`, which carries official 2.3.0)
- nte-core, the capture / loader components, ViGEmBus and the other components bundled in the installer are separate components under their own licenses and were not modified. For their origin and terms, see [NOTICE](NOTICE) and `third_party/` in the original repository.

## Disclaimer

This is an unofficial, fan-made tool. It is not affiliated with, endorsed by or supported by the developer or publisher of the game. Neverness to Everness / 异环 names, characters, artwork and other game materials belong to their respective rights holders. The program is provided as is, and you use it at your own risk.
