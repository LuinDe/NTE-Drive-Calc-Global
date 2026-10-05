# 대응 소스 코드 안내 / Corresponding Source

NTE Drive Calc Global 2.3.0(비공식 다국어 빌드)에 대한 GNU AGPL-3.0 제5조·제6조의 고지입니다.

This is the notice under sections 5 and 6 of the GNU AGPL-3.0 for NTE Drive Calc Global 2.3.0 (unofficial multilingual build).

---

## 한국어

### 원본 저작물

- 원본 프로젝트: **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator>
- 원본 저장소의 예전 이름은 hxwd94666/NTE-Drive-Calc이며, 설치 파일과 소스 zip 안의 문서에는 그 주소가 적혀 있습니다(현재 주소로 자동 연결됩니다).
- 저작권: NTE Drive Calc contributors (hxwd94666)
- 라이선스: GNU Affero General Public License v3.0 ([LICENSE](LICENSE), 원본 고지는 [NOTICE](NOTICE))
- 기준 커밋: `d3eca803ac36a75a3fa4fbbf8adadb93dadadf65` (원본 태그 `2.3.0.1`. 공식 2.3.0 설치 프로그램 `NTE_Drive_Calc_Setup_2.3.0.exe`가 올라와 있는 릴리스입니다. 원본의 `2.3.0` 태그는 다른 커밋을 가리키므로 기준이 아닙니다.)

기준 커밋은 임의로 고른 것이 아닙니다. 공식 2.3.0 실행 파일(SHA-256 `505950ca…cbbf`)에 들어 있는 `src.*` 모듈 820개 전부가 이 커밋의 소스를 컴파일한 것과 일치합니다(`build_tools/rebuild_exe_l10n.py`를 원본 소스로 돌리면 820개가 모두 "변경 없음"으로 나옵니다).

### 이 빌드는 파생물입니다

이 프로그램은 위 원본을 LuinDe가 수정한 것이며(2026-10-05), 원작자가 배포하거나 지원하는 공식 빌드가 아닙니다. 무엇을 바꿨는지는 [CHANGES.md](CHANGES.md)에 있습니다.

### 대응 소스가 있는 곳

배포되는 실행 파일(`NTE_Drive_Calc.exe`)의 `src.*` 모듈과 이 빌드에서 바꾼 파일에 대응하는 소스 코드는 다음 두 곳에 같은 내용으로 있습니다.

1. **이 저장소** — 해당 릴리스의 태그가 가리키는 트리
   - [`src/`](src): 수정된 파이썬 소스 전체. 실행 파일에 들어 있는 `src.*` 모듈은 모두 여기서 컴파일됩니다.
   - [`config/templates/guide/`](config/templates/guide): 한국어판 튜토리얼 이미지 7장
   - [`build_tools/`](build_tools): 실행 파일과 설치 프로그램을 만드는 스크립트, 자동 생성 모듈의 생성기
2. **같은 릴리스에 첨부된 소스 zip** — `NTE_Drive_Calc_2.3.0_Multilingual_source.zip`
   (SHA-256 `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113`)

`src/` 밖의 원본 파일(main.py, 빌드 스크립트, assets, data, native, third_party 등)은 바꾸지 않았으므로 원본 저장소의 위 커밋에 있는 것과 같습니다: <https://github.com/hxwd94666/NTE-Drive-Calculator/tree/d3eca803ac36a75a3fa4fbbf8adadb93dadadf65>

설치 폴더의 `l10n_build` 폴더에도 `LICENSE.txt`, `SOURCE_OFFER.txt`, `README.txt`가 설치됩니다. 이 문서들과 소스 zip의 `README_SOURCE.txt`는 이 저장소를 만들기 전에 쓴 것이라 변경점 요약이 짧고(게임 폴더의 파일 보호, 헥스 비율 수정 등이 빠져 있습니다) 수정 날짜가 적혀 있지 않습니다. 변경점 전체 목록과 날짜(2026-10-05)는 이 저장소의 [CHANGES.md](CHANGES.md)와 [NOTICE](NOTICE)를 기준으로 하세요.

### 배포되는 실행 파일

`NTE_Drive_Calc.exe`는 공식 2.3.0 PyInstaller 실행 파일의 PYZ 아카이브에서 **`src.*` 모듈만** 위 소스를 컴파일한 것으로 교체하고 PE 체크섬을 다시 계산한 것입니다. `src.*` 이외의 모든 아카이브 항목은 원본과 바이트 단위로 같습니다. 설치 프로그램에 들어 있는 그 밖의 구성 요소(`_internal`, `drivers`)는 튜토리얼 이미지 7장을 빼고 공식 2.3.0 배포본과 같습니다.

설치 프로그램에 함께 들어 있는 별도 구성 요소(nte-core, nte-analysis-core, 캡처/로더 컴포넌트, ViGEmBus 등)는 공식 2.3.0 배포본의 바이너리를 수정 없이 그대로 다시 배포한 것이며, 그 소스는 이 저장소에 없습니다. 각 구성 요소의 라이선스와 소스 출처 기록(`SOURCE.md`)은 설치 폴더의 `_internal\licenses`와 원본 저장소의 `third_party/`에 있습니다.

| 파일 | SHA-256 |
|---|---|
| `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` | `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177` |
| `NTE_Drive_Calc_2.3.0_Multilingual_source.zip` | `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113` |
| 설치되는 `NTE_Drive_Calc.exe` | `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30` |
| 바탕이 된 공식 2.3.0 `NTE_Drive_Calc.exe` | `505950ca2261902df6c78a61c3f17c6e756b82bb9309689ac08114c4f3a1cbbf` |

### 재현 방법

Python 3.11이 필요합니다(실행 파일이 `python311.dll`을 내장).

```powershell
python build_tools/rebuild_exe_l10n.py <공식 2.3.0 NTE_Drive_Calc.exe> src <출력 exe>
python build_tools/verify_exe_l10n.py  <공식 2.3.0 NTE_Drive_Calc.exe> <출력 exe> src
```

CPython 3.11.15(Windows x64)로 빌드하면 결과물의 SHA-256이 배포된 실행 파일과 같습니다. 다른 3.11.x에서는 압축 결과가 달라 해시가 다를 수 있으며, 그때는 `verify_exe_l10n.py`가 내용이 이 소스와 일치하는지 확인합니다. 설치 프로그램은 `build_tools/build_installer_l10n.py`로 만듭니다(공식 설치본의 `_internal` / `drivers` 사본과 Inno Setup 6 필요).

`src/services/team_rotation_data.py`, `team_form_actions.py`, `team_custom_actions.py`는 `build_tools/gen_team_*.py`가 만든 표입니다. 생성기의 입력 자료(게임 정적 데이터베이스, 조사 노트)는 이 저장소에 없습니다. 이 저장소에서는 생성된 파일 자체를 고쳐서 관리합니다. 이 세 파일 머리말의 "GENERATED FILE - DO NOT EDIT" 문구는 생성기 입력 자료가 있는 작업 폴더를 기준으로 적힌 것입니다. 입력 자료는 공개하지 않으므로, 이 저장소에서는 생성된 파일이 곧 수정용 원본입니다.

---

## English

### Original work

- Original project: **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator>
- The original repository was formerly named hxwd94666/NTE-Drive-Calc; the documents inside the installer and the source zip still show that address (it redirects to the current one).
- Copyright: NTE Drive Calc contributors (hxwd94666)
- License: GNU Affero General Public License v3.0 ([LICENSE](LICENSE); the original notices are in [NOTICE](NOTICE))
- Baseline: commit `d3eca803ac36a75a3fa4fbbf8adadb93dadadf65` (upstream tag `2.3.0.1`, the release that carries the official 2.3.0 installer `NTE_Drive_Calc_Setup_2.3.0.exe`; the upstream tag `2.3.0` points to a different commit and is not the baseline)

The baseline was not picked by hand. All 820 `src.*` modules inside the official 2.3.0 executable (SHA-256 `505950ca…cbbf`) equal a compile of the source at this commit (running `build_tools/rebuild_exe_l10n.py` on the original source reports all 820 as unchanged).

### This build is a derivative work

This program is the original as modified by LuinDe (2026-10-05). It is not an official build published or supported by the original authors. What was changed is listed in [CHANGES.md](CHANGES.md).

### Where the corresponding source is

The source code corresponding to the `src.*` modules of the distributed executable (`NTE_Drive_Calc.exe`) and to the files changed in this build is available, with the same content, in two places:

1. **This repository**, at the tree the release's tag points to
   - [`src/`](src): the complete modified Python source. Every `src.*` module in the executable is compiled from it.
   - [`config/templates/guide/`](config/templates/guide): the seven Korean tutorial images
   - [`build_tools/`](build_tools): the scripts that produce the executable and the installer, and the generators of the generated modules
2. **The source zip attached to the same release**: `NTE_Drive_Calc_2.3.0_Multilingual_source.zip`
   (SHA-256 `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113`)

The original files outside `src/` (main.py, build scripts, assets, data, native, third_party and so on) are not modified and are therefore the same as in the original repository at the commit above: <https://github.com/hxwd94666/NTE-Drive-Calculator/tree/d3eca803ac36a75a3fa4fbbf8adadb93dadadf65>

The installer also places `LICENSE.txt`, `SOURCE_OFFER.txt` and `README.txt` in the `l10n_build` folder of the installation directory. These notes and `README_SOURCE.txt` in the source zip were written before this repository existed: their change summary is shorter (it leaves out, for example, the game-folder file protection and the Hex ratio change) and they carry no modification date. For the complete list of changes and the date (2026-10-05), refer to [CHANGES.md](CHANGES.md) and [NOTICE](NOTICE) in this repository.

### The distributed executable

`NTE_Drive_Calc.exe` is the official 2.3.0 PyInstaller executable in which **only the `src.*` modules** of the PYZ archive are replaced by a compile of the source above, with the PE checksum recomputed. Every archive entry other than `src.*` is byte-identical to the original. The other components in the installer (`_internal`, `drivers`) are the same as in the official 2.3.0 distribution, except for the seven tutorial images.

The separately licensed components bundled in the installer (nte-core, nte-analysis-core, the capture / loader components, ViGEmBus and so on) are the official 2.3.0 binaries, redistributed without modification; their source is not in this repository. Their licences and source records (`SOURCE.md`) are in `_internal\licenses` of the installation directory and in `third_party/` of the original repository.

| File | SHA-256 |
|---|---|
| `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` | `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177` |
| `NTE_Drive_Calc_2.3.0_Multilingual_source.zip` | `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113` |
| Installed `NTE_Drive_Calc.exe` | `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30` |
| Official 2.3.0 `NTE_Drive_Calc.exe` used as the base | `505950ca2261902df6c78a61c3f17c6e756b82bb9309689ac08114c4f3a1cbbf` |

### Reproducing

Python 3.11 is required (the executable embeds `python311.dll`).

```powershell
python build_tools/rebuild_exe_l10n.py <official 2.3.0 NTE_Drive_Calc.exe> src <output exe>
python build_tools/verify_exe_l10n.py  <official 2.3.0 NTE_Drive_Calc.exe> <output exe> src
```

A build with CPython 3.11.15 (Windows x64) has the same SHA-256 as the distributed executable. Another 3.11.x may compress differently and give a different hash; `verify_exe_l10n.py` then confirms that the content matches this source. The installer is built with `build_tools/build_installer_l10n.py` (it needs a copy of the official installation's `_internal` / `drivers` folders and Inno Setup 6).

`src/services/team_rotation_data.py`, `team_form_actions.py` and `team_custom_actions.py` are tables generated by `build_tools/gen_team_*.py`. The generators' inputs (the game's static database and research notes) are not in this repository; here the generated files themselves are what gets edited. The header "GENERATED FILE - DO NOT EDIT" in these three files was written for the author's working tree, where the generator inputs exist. Those inputs are not published, so in this repository the generated files are the form to modify.
