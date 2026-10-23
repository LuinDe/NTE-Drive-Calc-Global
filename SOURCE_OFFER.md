# 대응 소스 코드 안내 / Corresponding Source

NTE Drive Calc Global 2.3.2(비공식 다국어 빌드)에 대한 GNU AGPL-3.0 제5조·제6조의 고지입니다.

This is the notice under sections 5 and 6 of the GNU AGPL-3.0 for NTE Drive Calc Global 2.3.2 (unofficial multilingual build).

---

## 한국어

### 원본 저작물

- 원본 프로젝트: **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator>
- 저작권: NTE Drive Calc contributors (hxwd94666)
- 라이선스: GNU Affero General Public License v3.0 ([LICENSE](LICENSE), 원본 고지는 [NOTICE](NOTICE))
- 기준 커밋: `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` (공식 2.3.1의 소스, `src/app/version.py` = 2.3.1). 원본의 `2.3.1` 태그는 그보다 앞선 커밋(`765d78a`, 버전 2.3.0)을 가리키므로 기준이 아닙니다.

기준 커밋은 임의로 고른 것이 아닙니다. 공식 2.3.1 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.1.exe`, SHA-256 `57a6f351…8841`)이 설치하는 실행 파일(SHA-256 `5b8fa8d2…e8c3`)에 들어 있는 `src.*` 모듈 893개 전부가 이 커밋의 소스를 컴파일한 것과 일치합니다(`build_tools/rebuild_exe_l10n.py`를 원본 소스로 돌리면 893개가 모두 "변경 없음"으로 나옵니다).

### 이 빌드는 파생물입니다

이 프로그램은 위 원본을 LuinDe가 수정한 것이며(이 버전 Global 2.3.2는 2026-10-20, 잠시 공개되었던 2.3.1-global.2는 2026-10-19, 2.3.1-global.1은 2026-10-11, 첫 버전 Global 2.3.0은 2026-10-05), 원작자가 배포하거나 지원하는 공식 빌드가 아닙니다. 무엇을 바꿨는지는 [CHANGES.md](CHANGES.md)에 있습니다. Global의 버전 번호(`v<주>.<부>.<수>`)는 원본과 별개인 이 빌드의 고유 번호이고, 바탕이 된 원본 버전은 2.3.1입니다.

### 대응 소스가 있는 곳

배포되는 실행 파일(`NTE_Drive_Calc.exe`)의 `src.*` 모듈과 이 빌드에서 바꾼 파일에 대응하는 소스 코드는 다음 두 곳에 같은 내용으로 있습니다.

1. **이 저장소** — 해당 릴리스의 태그(이 버전은 `v2.3.2`)가 가리키는 커밋의 트리
   - [`src/`](src): 수정된 파이썬 소스 전체. 실행 파일에 들어 있는 `src.*` 모듈은 모두 여기서 컴파일됩니다. 프로그램 안 업데이트가 확인하는 릴리스 서명 공개키도 여기에 있습니다(`src/app/global_release.py`의 `RELEASE_SIGNING_KEYS`).
   - [`config/templates/guide/`](config/templates/guide): 한국어판 튜토리얼 이미지 7장
   - [`build_tools/`](build_tools): 실행 파일·설치 프로그램·소스 zip·릴리스 매니페스트를 만드는 스크립트, 자동 생성 모듈의 생성기
2. **같은 릴리스에 첨부된 소스 zip** — `NTE_Drive_Calc_2.3.2_Multilingual_source.zip`
   (SHA-256 `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa`)
   - 이 저장소의 커밋에서 `build_tools/make_source_zip_g231.py`로 만든 것이며(`--date 2026-10-20T00:00:00 --version 2.3.2`), 같은 커밋에서 다시 만들면 바이트 단위로 같은 파일이 나옵니다. `src/`·`build_tools/` 트리는 저장소의 것과 같습니다. 이 zip만으로 다시 빌드한 실행 파일도 배포된 실행 파일과 SHA-256이 같습니다.

`src/` 밖의 원본 파일(main.py, 빌드 스크립트, assets, data, native, third_party 등)은 바꾸지 않았으므로 원본 저장소의 위 커밋에 있는 것과 같습니다: <https://github.com/hxwd94666/NTE-Drive-Calculator/tree/0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1>

설치 폴더의 `l10n_build` 폴더에도 `LICENSE.txt`, `SOURCE_OFFER.txt`(소스 zip에 들어 있는 것과 같은 파일), `README.txt`가 설치됩니다. 이 문서들의 변경점 요약은 짧고 수정 날짜가 적혀 있지 않습니다. 변경점 전체 목록과 날짜는 이 저장소의 [CHANGES.md](CHANGES.md)와 [NOTICE](NOTICE)(소스 zip에도 `NOTICE.txt`로 들어 있음)를 기준으로 하세요.

### 배포되는 실행 파일

`NTE_Drive_Calc.exe`는 공식 2.3.1 PyInstaller 실행 파일의 PYZ 아카이브에서 **`src.*` 모듈만** 위 소스를 컴파일한 것으로 교체하고(원본의 업데이트 모듈 `src.features.settings.updates`와 `src.ui.controllers.update_controller`는 이 빌드에서 뺐습니다) PE 체크섬을 다시 계산한 것입니다. `src.*` 이외의 모든 아카이브 항목은 원본과 바이트 단위로 같습니다. 설치 프로그램에 들어 있는 그 밖의 구성 요소(`_internal`, `drivers`)는 튜토리얼 이미지 7장을 빼고 공식 2.3.1 배포본과 같습니다.

설치 프로그램에 함께 들어 있는 별도 구성 요소(nte-core, nte-analysis-core, 게임 내 컴포넌트 `d3d12.dll`·`plugins`, 로더, ViGEmBus 등)는 공식 2.3.1 배포본의 바이너리를 수정 없이 그대로 다시 배포한 것이며, 그 소스는 이 저장소에 없습니다. 각 구성 요소의 라이선스와 소스 출처 기록(`SOURCE.md`)은 설치 폴더의 `_internal\licenses`와 원본 저장소의 `third_party/`에 있습니다.

| 파일 | 크기(바이트) | SHA-256 |
|---|---:|---|
| `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` | 184,850,846 | `c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87` |
| `NTE_Drive_Calc_2.3.2_Multilingual_source.zip` | 7,478,833 | `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa` |
| 설치되는 `NTE_Drive_Calc.exe` | 25,221,222 | `3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f` |
| 바탕이 된 공식 2.3.1 `NTE_Drive_Calc.exe` | 21,320,661 | `5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3` |

이전 버전(2.3.1-global.1, 2.3.0-global.1)의 파일과 해시는 [Releases](../../releases)의 해당 릴리스와 그 태그의 이 문서에 있습니다.

### 재현 방법

Python 3.11이 필요합니다(실행 파일이 `python311.dll`을 내장).

```powershell
python build_tools/rebuild_exe_l10n.py      <공식 2.3.1 NTE_Drive_Calc.exe> src <출력 exe> --remove=src.features.settings.updates --remove=src.ui.controllers.update_controller
python build_tools/verify_exe_l10n_g231.py  <공식 2.3.1 NTE_Drive_Calc.exe> <출력 exe> src --removed=src.features.settings.updates --removed=src.ui.controllers.update_controller
```

`--remove` / `--removed`는 원본의 업데이트 모듈 두 개를 일부러 뺀다는 표시입니다(그 밖의 모듈이 빠져 있으면 빌드가 멈춥니다). CPython 3.11.15(Windows x64)로 빌드하면 결과물의 SHA-256이 배포된 실행 파일(`3a165259…384f`)과 같습니다. 다른 3.11.x에서는 압축 결과가 달라 해시가 다를 수 있으며, 그때는 `verify_exe_l10n_g231.py`가 내용이 이 소스와 일치하는지 확인합니다. 설치 프로그램, 소스 zip, 서명할 릴리스 매니페스트를 만드는 순서는 [build_tools/README.md](build_tools/README.md)에 있습니다(공식 2.3.1 설치 프로그램과 Inno Setup 6 필요). 릴리스 매니페스트의 서명은 배포자의 개인키로만 할 수 있으며, 개인키는 이 저장소에 없습니다(대응 소스에 들어가지 않는 서명 키입니다). 직접 빌드한 실행 파일에 다른 공개키를 넣으려면 `build_tools/pin_release_key.py`를 쓰세요.

다음 파일은 `build_tools`의 생성기가 만든 표입니다: `src/services/team_rotation_data.py`, `team_form_actions.py`, `team_custom_actions.py`(`gen_team_*.py`), `team_resource_data.py`(`gen_team_resource_data.py`), `puka_training_data.py`(`gen_puka_training_data.py`, 입력 `build_tools/data/puka_training_levels.json`). 생성기의 입력 자료 일부(게임 정적 데이터베이스, 조사 노트)는 이 저장소에 없습니다. 이 저장소에서는 생성된 파일 자체를 고쳐서 관리해도 됩니다. 일부 파일 머리말의 "GENERATED FILE - DO NOT EDIT" 문구는 생성기 입력 자료가 있는 작업 폴더를 기준으로 적힌 것입니다. 입력 자료를 모두 공개하지는 않으므로, 이 저장소에서는 생성된 파일이 곧 수정용 원본입니다.

`src/services/arc_efficiency_data.py`(아크 효율표)와 `awakening_efficiency_data.py`(돌파 효율표)의 미리 계산된 결과는 `build_tools/gen_arc_efficiency_data.py`와 `gen_awakening_efficiency_data.py`가 프로그램과 같은 계산 코드로 만듭니다. 프로그램은 이 표가 게임 데이터·계산 코드와 맞지 않으면 사용자 PC에서 다시 계산합니다.

---

## English

### Original work

- Original project: **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator>
- Copyright: NTE Drive Calc contributors (hxwd94666)
- License: GNU Affero General Public License v3.0 ([LICENSE](LICENSE); the original notices are in [NOTICE](NOTICE))
- Baseline: commit `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` (the source of the official 2.3.1, `src/app/version.py` = 2.3.1). The upstream tag `2.3.1` points to an older commit (`765d78a`, version 2.3.0) and is not the baseline.

The baseline was not picked by hand. All 893 `src.*` modules inside the executable (SHA-256 `5b8fa8d2…e8c3`) installed by the official 2.3.1 installer (`NTE_Drive_Calc_Setup_2.3.1.exe`, SHA-256 `57a6f351…8841`) equal a compile of the source at this commit (running `build_tools/rebuild_exe_l10n.py` on the original source reports all 893 as unchanged).

### This build is a derivative work

This program is the original as modified by LuinDe (this version, Global 2.3.2: 2026-10-20; 2.3.1-global.2, published briefly: 2026-10-19; 2.3.1-global.1: 2026-10-11; the first version, Global 2.3.0: 2026-10-05). It is not an official build published or supported by the original authors. What was changed is listed in [CHANGES.md](CHANGES.md). The Global version numbers (`v<major>.<minor>.<patch>`) are this build's own, independent of the original; the original version it is based on is 2.3.1.

### Where the corresponding source is

The source code corresponding to the `src.*` modules of the distributed executable (`NTE_Drive_Calc.exe`) and to the files changed in this build is available, with the same content, in two places:

1. **This repository**, at the tree of the commit the release's tag points to (for this version `v2.3.2`)
   - [`src/`](src): the complete modified Python source. Every `src.*` module in the executable is compiled from it. The release-signing public key that the in-app updater checks is here too (`RELEASE_SIGNING_KEYS` in `src/app/global_release.py`).
   - [`config/templates/guide/`](config/templates/guide): the seven Korean tutorial images
   - [`build_tools/`](build_tools): the scripts that produce the executable, the installer, the source zip and the release manifest, and the generators of the generated modules
2. **The source zip attached to the same release**: `NTE_Drive_Calc_2.3.2_Multilingual_source.zip`
   (SHA-256 `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa`)
   - It is made from a commit of this repository with `build_tools/make_source_zip_g231.py` (`--date 2026-10-20T00:00:00 --version 2.3.2`); making it again from the same commit gives a byte-identical file. Its `src/` and `build_tools/` trees are the repository's. An executable rebuilt from the zip alone has the SHA-256 of the distributed executable.

The original files outside `src/` (main.py, build scripts, assets, data, native, third_party and so on) are not modified and are therefore the same as in the original repository at the commit above: <https://github.com/hxwd94666/NTE-Drive-Calculator/tree/0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1>

The installer also places `LICENSE.txt`, `SOURCE_OFFER.txt` (the same file as in the source zip) and `README.txt` in the `l10n_build` folder of the installation directory. Their change summary is short and they carry no modification date. For the complete list of changes and the date, refer to [CHANGES.md](CHANGES.md) and [NOTICE](NOTICE) in this repository (the source zip contains the NOTICE as `NOTICE.txt`).

### The distributed executable

`NTE_Drive_Calc.exe` is the official 2.3.1 PyInstaller executable in which **only the `src.*` modules** of the PYZ archive are replaced by a compile of the source above (the original's update modules `src.features.settings.updates` and `src.ui.controllers.update_controller` are left out of this build), with the PE checksum recomputed. Every archive entry other than `src.*` is byte-identical to the original. The other components in the installer (`_internal`, `drivers`) are the same as in the official 2.3.1 distribution, except for the seven tutorial images.

The separately licensed components bundled in the installer (nte-core, nte-analysis-core, the in-game components `d3d12.dll` and `plugins`, the loader, ViGEmBus and so on) are the official 2.3.1 binaries, redistributed without modification; their source is not in this repository. Their licences and source records (`SOURCE.md`) are in `_internal\licenses` of the installation directory and in `third_party/` of the original repository.

| File | Size (bytes) | SHA-256 |
|---|---:|---|
| `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` | 184,850,846 | `c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87` |
| `NTE_Drive_Calc_2.3.2_Multilingual_source.zip` | 7,478,833 | `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa` |
| Installed `NTE_Drive_Calc.exe` | 25,221,222 | `3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f` |
| Official 2.3.1 `NTE_Drive_Calc.exe` used as the base | 21,320,661 | `5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3` |

The files and hashes of earlier versions (2.3.1-global.1, 2.3.0-global.1) are in their releases under [Releases](../../releases) and in this document at their tags.

### Reproducing

Python 3.11 is required (the executable embeds `python311.dll`).

```powershell
python build_tools/rebuild_exe_l10n.py      <official 2.3.1 NTE_Drive_Calc.exe> src <output exe> --remove=src.features.settings.updates --remove=src.ui.controllers.update_controller
python build_tools/verify_exe_l10n_g231.py  <official 2.3.1 NTE_Drive_Calc.exe> <output exe> src --removed=src.features.settings.updates --removed=src.ui.controllers.update_controller
```

`--remove` / `--removed` mark the two update modules of the original as left out on purpose (any other missing module stops the build). A build with CPython 3.11.15 (Windows x64) has the SHA-256 of the distributed executable (`3a165259…384f`). Another 3.11.x may compress differently and give a different hash; `verify_exe_l10n_g231.py` then confirms that the content matches this source. How the installer, the source zip and the release manifest to be signed are made is described in [build_tools/README.md](build_tools/README.md) (it needs the official 2.3.1 installer and Inno Setup 6). Only the maintainer's private key can sign a release manifest; that key is not in this repository (it is a signing key, not part of the corresponding source). To put another public key into an executable you build yourself, use `build_tools/pin_release_key.py`.

These files are tables made by generators in `build_tools`: `src/services/team_rotation_data.py`, `team_form_actions.py`, `team_custom_actions.py` (`gen_team_*.py`), `team_resource_data.py` (`gen_team_resource_data.py`) and `puka_training_data.py` (`gen_puka_training_data.py`, input `build_tools/data/puka_training_levels.json`). Some of the generators' inputs (the game's static database and research notes) are not in this repository; here the generated files themselves may be edited. The header "GENERATED FILE - DO NOT EDIT" in some of these files was written for the author's working tree, where the generator inputs exist. Not all inputs are published, so in this repository the generated files are the form to modify.

The precomputed rows of `src/services/arc_efficiency_data.py` (Arc Efficiency table) and `awakening_efficiency_data.py` (awakening efficiency table) are made by `build_tools/gen_arc_efficiency_data.py` and `gen_awakening_efficiency_data.py` with the program's own calculation code. When the rows do not match the game data or the calculation code, the program recomputes them on the user's PC.
