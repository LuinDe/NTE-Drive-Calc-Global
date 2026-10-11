# NTE Drive Calc Global 2.3.1

> **비공식 수정 빌드입니다. 원본 프로그램이 아닙니다.**
> 원본(공식): **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator> (hxwd94666 / NTE Drive Calc contributors, AGPL-3.0)
> 이 릴리스는 원본 공식 2.3.1을 수정해서 만든 것이며, 원작자가 배포하거나 지원하지 않습니다. 문제는 원본 저장소가 아니라 [이 저장소의 Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)에 알려 주세요.
>
> **Unofficial modified build — not the original program.** Original: <https://github.com/hxwd94666/NTE-Drive-Calculator>. Short notes in English, 日本語 and 中文 are at the bottom.

## 한국어

NTE Drive Calc 공식 2.3.1을 바탕으로 한 Global(다국어) 릴리스입니다. 새 기능 **아크 효율표(Beta)** 가 들어 있습니다.

### 받을 파일

| 파일 | 설명 |
|---|---|
| `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` | 설치 프로그램. 프로그램 전체가 들어 있습니다. |
| `NTE_Drive_Calc_2.3.1_Multilingual_source.zip` | 이 빌드의 소스 코드(AGPL-3.0). 이 저장소의 같은 커밋에도 같은 내용이 있습니다. |

### 설치

1. NTE Drive Calc가 켜져 있으면 종료합니다.
2. 설치 파일을 실행하고 UAC 창에서 "예"를 누릅니다. 코드 서명이 없어서 "Windows의 PC 보호" 창이 뜨면 "추가 정보" → "실행"을 누릅니다.
3. 설치 언어를 고르고 "다음"을 눌러 마칩니다.

- 공식 버전과 같은 위치(기본 `C:\Program Files\NTE Drive Calc`)에 설치됩니다. 공식 2.3.1, 한국어 패치를 적용한 2.3.1, 이전 다국어판(Global 2.3.0) 위에 그대로 설치하면 되고, 처음 설치하는 경우에도 이 파일 하나면 됩니다.
- 계정·설정·드라이브·창고·전투 리포트·육성 기록·로그·저장한 사이클 등 사용자 데이터는 그대로 유지됩니다. 한국어 패치가 만든 백업 파일도 지우지 않습니다.
- 되돌리려면 공식 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.1.exe`)을 같은 위치에 다시 설치합니다. 공식 설치 프로그램은 [원본 프로젝트의 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)에서 받으세요.

자세한 안내는 [README](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.md)에 있습니다.

### 2.3.0에서 달라진 점

- **공식 2.3.1 기반**: 원본이 2.3.1에서 추가한 기능(육성 기록, 플러그인 방식의 게임 내 컴포넌트 등)이 모두 들어 있습니다.
- **새 기능: 아크 효율표(Beta)** — 전용 아크가 있는 캐릭터 11명에 대해, 낄 수 있는 아크를 1인 딜 사이클 피해로 비교합니다. 전용 아크 1재련 = 100%, 1재련과 최대 재련 두 열, 3바퀴(기본)/1바퀴, 다른 캐릭터의 전용 아크는 †로 표시(숨김 가능), "팀 시뮬레이션에서 열기". 결과는 미리 계산되어 있어 바로 열리고, 게임 데이터가 바뀌면 그 PC에서 다시 계산합니다.
- **팀 시뮬레이션 아크 보정**(효율표와 같은 계산):
  - 팀원의 아크·재련을 바꾸면 그 아크의 스탯이 반영됩니다(2.3.0에서는 템플릿 아크의 스탯이 남아 있었습니다).
  - 아크의 상시 효과를 두 번 계산하던 것을 한 번만 계산합니다.
  - 전투 엔진이 수치를 구하지 못하는 「죄와 벌」·「달의 대척점」의 조건부 효과를 설명문과 게임 데이터 수치로 계산합니다(Global 보충 규칙).
  - **그래서 같은 팀이라도 결과가 2.3.0과 다릅니다.** 상시 효과가 있는 아크를 낀 팀은 대체로 1~11% 낮아지고, 위 두 아크를 낀 팀은 높아집니다. 레이븐·아카네 린은 2.3.1 게임 데이터 변경으로도 숫자가 바뀌었습니다.
- **게임 폴더 보호**를 2.3.1 구조에 맞게 다시 만들었습니다. 게임 폴더의 `d3d12.dll`, `plugins\NTE_Plugin*.dll`, `NTE_Capture.dll`, `dwmapi.dll`이 이 프로그램의 파일로 확인되지 않으면(예: ReShade, UE4SS) 덮어쓰거나 지우지 않습니다.
- **번역**: 2.3.1의 새 문장 약 700개를 한국어·영어·일본어로 번역했습니다. 한국어는 2.3.1 한국어 패치의 표현(공식 스킬명, 倾陷 = 붕괴, 援护技 = 서포트 스킬)을 따릅니다. 영어·일본어는 예전 게임 설명문 288개도 새로 번역했습니다.
- **수정**:
  - 2.3.1의 육성 기록이 번역된 화면에서 저장되고, 저장한 기록이 어느 언어에서나 열립니다(공식 2.3.1이 저장한 기록도 열립니다).
  - 번역문 9곳에서 두 값이 서로 자리를 바꿔 나올 수 있던 문제를 고쳤습니다.
  - 영어 버튼·탭의 `&`가 단축키 표시로 먹히던 문제를 고쳤습니다(이제 "and").
  - 문구 비교가 번역문에서도 맞게 동작하도록 했습니다(전투 리포트의 일반 공격 판정, 플러그인 상태 배지 등).
  - 기본 창 크기에서 육성 화면이 잘리지 않습니다. 작업 모드 화면의 라벨·버튼이 잘리지 않습니다.

원본과의 차이 전체는 [CHANGES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/CHANGES.md)에 있습니다.

### 알려진 한계

**팀 시뮬레이션과 아크 효율표는 Beta(미완성)입니다.** 딜 사이클 검수가 완벽하지 않아 결과가 실전과 다를 수 있습니다. 대략적인 비교 용도로만 쓰세요.

팀 시뮬레이션:

- 적 80레벨·저항 20%의 움직이지 않는 허수아비가 기준이고, 드라이브와 메인/서브 스탯은 공식 졸업 템플릿을 씁니다(내 창고의 장비가 아닙니다).
- 검수된 딜 사이클 모드는 쿨타임과 에너지를 확인하지 않습니다.
- 직접 입력 모드에서 쿨타임·에너지 값이 게임 데이터에 있는 캐릭터는 **2명뿐**입니다: 라크리모사(E 15초, Q 30초, Q 에너지 45)와 카오스(Q 20초). 나머지 캐릭터는 값을 직접 입력해야 검사합니다.
- 직접 입력의 "입력대로" 모드는 사이클 수치가 부족하거나 인접 속성이 아니어도 서포트 스킬을 내보내므로 실전보다 결과가 높게 나올 수 있습니다(해당 단계에 경고 표시).
- 반응 규칙 일부는 추정이거나 실전에서 확인되지 않았습니다. 소환물과 잔홍·라크리모사 외의 지속 피해, 전투 엔진이 해석하지 못하는 버프, 일부 캐릭터 고유의 반응 추가 효과는 계산에 들어가지 않습니다.
- 「죄와 벌」·「달의 대척점」의 보충 규칙은 설명문과 게임 데이터 수치로 만든 모델이며 실전 기록으로 확인하지 않았습니다.

아크 효율표:

- **전용 아크가 있는 캐릭터만**(현재 11명) 나옵니다. 전용 아크가 없는 상시 캐릭터는 넣지 않았습니다.
- 캐릭터 **혼자** 검수된 딜 사이클대로 행동하는 계산입니다. 팀원·교대·사이클 반응이 없으므로 서포트 스킬·팀원·팀 구성·사이클 강도·붕괴 강도에 달린 아크 효과는 0으로 계산됩니다. 팀을 돕는 아크는 실제보다 낮게 나옵니다.
- 공식 졸업 템플릿에서 아크와 재련만 바꿉니다(내 장비가 아닙니다).
- 대상은 Lv80 허수아비(보스 아님·붕괴 없음·피격 없음)이고, 에너지와 쿨타임은 사이클에 영향을 주지 않습니다. 피격·붕괴·보스 조건의 효과는 발동하지 않습니다.
- 중첩 효과는 매번 0층에서 시작합니다(3바퀴로 보면 이어지는 중첩이 반영됩니다).
- 일부 재련 효과는 1인 계산에 반영되지 않습니다(`=R` 표시). 예: 치명타 확률이 이미 상한이면 치명타 확률 재련 효과가 늘지 않아 레이븐 + †심장을 좀먹는 칼은 최대 재련 = 1재련으로 나옵니다.
- † 아크(다른 캐릭터 전용)는 계산기의 같은 유형 규칙으로 나열한 것이며, 게임에서 실제로 낄 수 있는지 확인하지 않았습니다.
- 서포트·서브 캐릭터는 1인 사이클이 짧아 팀 기여를 반영하지 못합니다(표에 표시). 사이클 신뢰도가 낮은 캐릭터도 표시됩니다.

번역·화면:

- "사용 방법" 튜토리얼 이미지는 어느 언어를 골라도 한국어입니다.
- 실행 중에 언어를 바꾸면 일부 글자(예: 육성 기록 목록의 열 제목과 검색 칸)가 페이지를 다시 열거나 다시 시작하기 전까지 이전 언어로 남습니다.
- 육성 기록에 저장된 계산 이름, 계정 이름("기본 계정" 등)은 만든 때의 언어로 남습니다.
- 전투 리포트에서 분석 컴포넌트가 돌려주는 예전 문장 약 310개는 한국어·영어 화면에서도 중국어로 나올 수 있습니다(2.3.1에서 새로 생긴 83개는 번역했습니다).
- 한국어 화면의 일부 페이지에서 "지식(蜘识)"이 "지식(지식(蜘识))"으로 겹쳐 보입니다. 일본어 화면에서는 일부 이름(예: 小吱)이 원문 그대로이고, 영어·일본어의 일부 용어는 화면마다 표기가 다를 수 있습니다.
- 검색창의 번역 이름 검색은 한글(초성 포함)만 지원합니다. 영어·일본어 화면에서는 중국어 원문(또는 병음)으로 검색해야 합니다.
- 게임 언어는 원본과 마찬가지로 简体中文이어야 스캔·감정(문자 인식)이 동작합니다.
- 프로그램 안의 GitHub·채팅 그룹(QQ/Discord)·후원·다운로드·업데이트 링크는 원본 그대로여서 원작자의 페이지로 연결됩니다. 이 빌드에서 생긴 문제를 그쪽에 올리지 말아 주세요.

**확인 범위**

- 실행 파일은 이 저장소의 `src/`로 다시 빌드해 SHA-256이 같은 것을 확인했고(두 번 빌드해 바이트 동일), 공식 실행 파일과의 차이가 `src.*` 모듈과 PE 체크섬뿐임을 `verify_exe_l10n_g231.py`로 확인했습니다.
- 배포용 실행 파일로 네 가지 언어 각각 오프라인 모드·빈 계정에서 자동 점검(페이지 순회, 팀 시뮬레이션, 아크 효율표, 육성 기록 저장과 언어별 열기, 실행 중 언어 전환 등 177항목)을 했고 실패 0건입니다.
- 설치·업그레이드·제거는 테스트용 설치 프로그램(권한 없이 설치되는 변형)으로 자동 확인했습니다: 새 설치, 공식 2.3.1 위 업그레이드, Global 2.3.0 위 업그레이드, 한국어 패치 2.3.1 위 업그레이드(백업 파일 유지), 같은 버전 재설치, 제거(사용자 데이터 유지). 배포용 설치 프로그램은 파일 목록·삭제 목록·프로그램 ID·폴더를 공식 2.3.1 설치 프로그램과 대조했으며, **관리자 권한으로 실제 설치해 보지는 않았습니다.** 공식 설치 프로그램으로 되돌리는 것은 같은 프로그램 ID와 같은 폴더를 쓰는 구조에 따른 것이며, 실제로 실행해 확인하지는 않았습니다.
- **게임과 연동되는 기능(동기화, 전투 기록, 자동 장착, 컴포넌트 로드 등)은 게임 폴더 보호와 번역용 문자열 처리를 빼고 원본의 로직 그대로이며, 이 빌드를 게임에 연결해 다시 검증하지는 않았습니다.** 게임 폴더 보호는 자동 테스트(33항목 + 시나리오 16개)로 확인했습니다.
- "내 캐릭터로 비교"는 이번 버전의 자동 점검에 들어 있지 않습니다. 결과는 추정치입니다.
- 설치 파일과 실행 파일에는 코드 서명이 없습니다.

### SHA-256

```
7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812  NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe  (184,093,883 bytes)
1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff  NTE_Drive_Calc_2.3.1_Multilingual_source.zip  (6,975,679 bytes)
76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0  설치되는 NTE_Drive_Calc.exe  (24,458,550 bytes)
5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3  (참고) 바탕이 된 공식 2.3.1 NTE_Drive_Calc.exe  (21,320,661 bytes)
57a6f351d53a32c6f989335e1ea812cd55057e331902b5921343ad2d73428841  (참고) 공식 NTE_Drive_Calc_Setup_2.3.1.exe  (180,707,151 bytes)
```

```powershell
Get-FileHash .\NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe -Algorithm SHA256
```

### 라이선스

NTE Drive Calc는 GNU AGPL-3.0으로 배포되는 프로그램이고 이 빌드는 그 파생물입니다. 원저작권: NTE Drive Calc contributors ([hxwd94666](https://github.com/hxwd94666)). 수정: [LuinDe](https://github.com/LuinDe), 2026-10-11, 원본 커밋 `0e7a6b4`(공식 2.3.1의 소스. 원본의 `2.3.1` 태그는 그보다 앞선 커밋을 가리킵니다) 기준. 대응 소스는 이 릴리스의 소스 zip과 같은 커밋의 저장소에 있습니다([SOURCE_OFFER.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/SOURCE_OFFER.md)).

이 프로그램은 팬이 만든 비공식 도구이며 게임의 개발사·배급사와 관계가 없습니다.

---

## English

**Unofficial modified build of [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1** (original by hxwd94666 / NTE Drive Calc contributors, AGPL-3.0). Modified by LuinDe on 2026-10-11, based on original commit `0e7a6b4` (the source of the official 2.3.1). It is not published or supported by the original author; report problems in this repository's Issues, not upstream.

- **Install**: download `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` and run it (UAC "Yes"; the file is unsigned, so on the SmartScreen window click "More info" → "Run anyway"). It contains the whole program, installs to the same location as the official version, can be installed over the official 2.3.1, a Korean-patched 2.3.1 or Global 2.3.0, and keeps your user data. To go back, run the official installer again (from the [original project's Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)).
- **New in this release**: based on the official 2.3.1 (cultivation history and the other 2.3.1 features included); a new **Arc Efficiency Table (Beta)** that compares the arcs each of the 11 characters with an exclusive arc can equip, by solo-rotation damage (exclusive arc R1 = 100 %, R1 and max-refinement columns, 3 loops by default or 1, other characters' exclusive arcs marked † and hideable, "Open in Team Simulation"); **Team Simulation arc corrections** shared with that table (the chosen arc now reaches the stats, always-on arc bonuses counted once, the conditional effects of "Crime and Punishment" and "Antipode of the Moon" modelled from their description and game data as a "Global supplement rule"), **so the same team gives different numbers than in 2.3.0**; game-folder protection rebuilt for the 2.3.1 layout (`d3d12.dll`, `plugins\NTE_Plugin*.dll`, `NTE_Capture.dll`, `dwmapi.dll` that are not this program's files, for example ReShade or UE4SS, are never overwritten or deleted); about 700 new strings translated, plus 288 older game descriptions in English and Japanese; the 2.3.1 cultivation history saves and opens in every language; `&` in English buttons fixed.
- **Known limits**: Team Simulation and the Arc Efficiency table are unfinished Betas; results may differ from real battles. Both assume a stationary Lv80 dummy and the official graduation templates. The Arc Efficiency table lists **only characters with an exclusive arc** and is a **solo** calculation: arc effects that depend on support skills, teammates, team makeup, cycle or break intensity count as 0, effects that need hits taken, a break or a boss never trigger, some refinement effects do not show (`=R`, for example at the crit-rate cap), and † arcs follow the calculator's same-type rule and were not verified in game. The tutorial images are Korean in every language; after a live language switch a few texts stay in the previous language until the page is reopened; about 310 older sentences of the battle-report analysis component may stay Chinese; search accepts Chinese, pinyin and Korean only; the game language must be Simplified Chinese for scanning and appraisal. In-app GitHub, chat, support, download and update links lead to the original author's pages; do not report problems of this build there.
- **What was checked**: the executable was rebuilt from `src/` with an identical SHA-256 and differs from the official one only in the `src.*` modules and the PE checksum; an automated check of the release executable in all four languages (Offline mode, empty account, 177 checks) passed; install, upgrade (over official 2.3.1, Global 2.3.0 and Korean-patched 2.3.1), reinstall and uninstall were tested with a test build of the installer that needs no administrator rights. The release installer was compared with the official one but **not run with administrator rights**. Features that interact with the game keep the original's logic (apart from the game-folder protection and string handling) and were not re-verified against the game.

SHA-256: installer `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`, source zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`, installed `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`. Full guide: [README.en.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.en.md).

## 日本語

**[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 を改変した非公式ビルドです**（オリジナル：hxwd94666 / NTE Drive Calc contributors、AGPL-3.0）。LuinDe が 2026-10-11 に改変（ベースはオリジナルのコミット `0e7a6b4`＝公式 2.3.1 のソース）。原作者が配布・サポートしているものではありません。問題はオリジナルではなく、このリポジトリの Issues に報告してください。

- **インストール**：`NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` をダウンロードして実行します（UAC は「はい」。署名がないため SmartScreen が出たら「詳細情報」→「実行」）。プログラム全体が入っており、公式版と同じ場所にインストールされ、公式 2.3.1・韓国語パッチを適用した 2.3.1・Global 2.3.0 の上にそのままインストールでき、ユーザーデータは残ります。戻すときは公式インストーラー（[オリジナルのプロジェクトの Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) から入手）をもう一度実行します。
- **このリリースの変更点**：公式 2.3.1 ベース（育成記録など 2.3.1 の機能を含む）。新機能 **アーク効率表 (Beta)**：専用アークを持つ 11 キャラクターについて、装備できるアークを単独ローテーションのダメージで比較（専用アーク精錬1 = 100%、精錬1 と最大精錬の 2 列、既定 3 周／1 周、他キャラの専用アークは † 付きで非表示にも可能、「チームシミュレーションで開く」）。同じ計算を使う**チームシミュレーションのアーク補正**（選んだアークがステータスに反映、常時効果の二重計算を補正、「罪と罰」「月の対蹠点」の条件効果を説明文とゲームデータから「Global補完ルール」として計算）により、**同じチームでも数値が 2.3.0 と異なります**。2.3.1 の構成に合わせたゲームフォルダー保護（このプログラムのファイルでない `d3d12.dll`・`plugins\NTE_Plugin*.dll`・`NTE_Capture.dll`・`dwmapi.dll`、例えば ReShade や UE4SS は上書きも削除もしない）。2.3.1 の新しい文字列 約 700 件と古いゲーム説明文 288 件を翻訳。2.3.1 の育成記録がどの言語でも保存・表示できるように修正。英語ボタンの `&` を修正。
- **既知の制限**：チームシミュレーションとアーク効率表は未完成の Beta で、結果が実戦と異なる場合があります。どちらも動かない Lv80 のカカシと公式卒業テンプレートが前提です。アーク効率表は**専用アークを持つキャラクターだけ**を扱う**単独**計算で、支援スキル・仲間・編成・サイクル強度・ブレイク強度に依存するアーク効果は 0、被弾・ブレイク・ボスが条件の効果は発動せず、一部の精錬効果は反映されません（`=R`。例：会心率が上限のとき）。† のアークは計算機の同タイプ規則によるもので、ゲーム内では未検証です。チュートリアル画像はどの言語でも韓国語です。実行中に言語を切り替えると、一部の文字がページを開き直すまで前の言語のまま残ります。戦闘レポートの分析コンポーネントが返す古い文章 約 310 件は中国語のまま表示されることがあります。検索は中国語・ピンイン・ハングルのみ対応です。スキャン・鑑定にはゲームの言語が簡体字中国語である必要があります。プログラム内の GitHub・チャット・支援・ダウンロード・アップデートのリンクはオリジナルのままで、原作者のページにつながります。このビルドで起きた問題はそちらに書き込まないでください。
- **確認した範囲**：実行ファイルは `src/` から再ビルドして SHA-256 が一致し、公式との違いが `src.*` モジュールと PE チェックサムだけであることを確認しました。配布用の実行ファイルで 4 言語それぞれ自動チェック（オフラインモード、空のアカウント、177 項目）を行い、すべて通過しました。インストール・アップグレード（公式 2.3.1、Global 2.3.0、韓国語パッチ適用 2.3.1 の上）・再インストール・アンインストールは、管理者権限なしで動くテスト用インストーラーで確認しました。配布用インストーラーは公式のものと構成を照合しましたが、**管理者権限で実際にインストールしてはいません**。ゲームと連携する機能はオリジナルのロジックのままで（ゲームフォルダー保護と文字列処理を除く）、ゲームに接続して再検証してはいません。

SHA-256：インストーラー `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`、ソース zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`、インストールされる `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`。詳しい案内：[README.ja.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.ja.md)

## 中文

**这是在 [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 基础上修改的非官方构建**（原版：hxwd94666 / NTE Drive Calc contributors，AGPL-3.0）。由 LuinDe 于 2026-10-11 修改（基于原版提交 `0e7a6b4`，即官方 2.3.1 的源代码）。它不是原作者发布或支持的版本；问题请反馈到本仓库的 Issues，不要反馈到原版仓库。

- **安装**：下载并运行 `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe`（UAC 选“是”；文件没有签名，出现 SmartScreen 时点击“更多信息”→“仍要运行”）。安装包包含整个程序，安装位置与官方版本相同，可以直接装在官方 2.3.1、打过韩语补丁的 2.3.1 或 Global 2.3.0 之上，用户数据会保留。要恢复官方版本，重新运行官方安装程序即可（从[原版项目的 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) 获取）。
- **本版本的变化**：基于官方 2.3.1（包含养成记录等 2.3.1 功能）；新功能 **弧盘效率表 (Beta)**：对拥有专属弧盘的 11 名角色，用单人循环伤害比较其可装备的弧盘（专属弧盘精炼 1 = 100%，精炼 1 与满精炼两列，默认 3 轮、可切换 1 轮，其他角色的专属弧盘标 † 并可隐藏，“在队伍模拟中打开”）；与之共用计算的**队伍模拟弧盘修正**（所选弧盘反映到面板、常驻效果只计算一次、「罪与罚」「月的对跖点」的条件效果按说明文和游戏数据以“Global 补充规则”计算），因此**同一支队伍的数值会与 2.3.0 不同**；按 2.3.1 结构重新实现游戏目录保护（不是本程序文件的 `d3d12.dll`、`plugins\NTE_Plugin*.dll`、`NTE_Capture.dll`、`dwmapi.dll`，例如 ReShade、UE4SS，不会被覆盖或删除）；翻译了 2.3.1 新增的约 700 条文本，并为英语和日语补译了 288 条较早的游戏说明文；修复 2.3.1 养成记录在各语言下的保存与打开；修复英语按钮中的 `&`。
- **已知限制**：队伍模拟和弧盘效率表都是尚未完成的 Beta，结果可能与实战不同。两者都以原地不动的 80 级木桩和官方毕业模板为前提。弧盘效率表**只包含拥有专属弧盘的角色**，并且是**单人**计算：依赖援护技、队友、队伍构成、环合强度或倾陷强度的弧盘效果按 0 计算，以受击、倾陷或首领为条件的效果不会触发，部分精炼效果无法体现（`=R`，例如暴击率已达上限时），标 † 的弧盘按计算器的同类型规则列出，未在游戏内实测。教程图片在任何语言下都是韩语；运行中切换语言后，少数文字在重新打开页面前仍显示为之前的语言；战报分析组件返回的约 310 条较早的句子可能仍显示为中文；搜索只支持中文、拼音和韩文；与原版一样，扫描和鉴定需要游戏语言为简体中文。程序内的 GitHub、交流群、赞助、下载和更新链接与原版相同，会打开原作者的页面；本构建出现的问题请不要反馈到那里。
- **验证范围**：可执行文件已用 `src/` 重新构建，SHA-256 完全一致，并确认与官方可执行文件的差异仅限于 `src.*` 模块和 PE 校验和；用发布的可执行文件在四种语言下分别进行了自动检查（离线模式、空账号、177 项），全部通过；安装、升级（官方 2.3.1、Global 2.3.0、打过韩语补丁的 2.3.1 之上）、重新安装和卸载已用无需管理员权限的测试版安装程序验证。发布用安装程序已与官方安装程序对照结构，但**没有以管理员权限实际安装**。与游戏交互的功能除游戏目录保护和文本处理外沿用原版逻辑，没有连接游戏重新验证。

SHA-256：安装程序 `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`，源代码 zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`，安装后的 `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`。完整说明：[README.zh.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.zh.md)
