# NTE Drive Calc Global 2.3.0

> **비공식 수정 빌드입니다. 원본 프로그램이 아닙니다.**
> 원본(공식): **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator> (hxwd94666 / NTE Drive Calc contributors, AGPL-3.0)
> 이 릴리스는 원본 공식 2.3.0을 수정해서 만든 것이며, 원작자가 배포하거나 지원하지 않습니다. 문제는 원본 저장소가 아니라 [이 저장소의 Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)에 알려 주세요.
>
> **Unofficial modified build — not the original program.** Original: <https://github.com/hxwd94666/NTE-Drive-Calculator>. Short notes in English, 日本語 and 中文 are at the bottom.

## 한국어

NTE Drive Calc 공식 2.3.0을 바탕으로 한 첫 번째 Global(다국어) 릴리스입니다.

### 받을 파일

| 파일 | 설명 |
|---|---|
| `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` | 설치 프로그램. 프로그램 전체가 들어 있습니다. |
| `NTE_Drive_Calc_2.3.0_Multilingual_source.zip` | 이 빌드의 소스 코드(AGPL-3.0). 이 저장소의 같은 태그에도 같은 내용이 있습니다. |

### 설치

1. NTE Drive Calc가 켜져 있으면 종료합니다.
2. 설치 파일을 실행하고 UAC 창에서 "예"를 누릅니다. 코드 서명이 없어서 "Windows의 PC 보호" 창이 뜨면 "추가 정보" → "실행"을 누릅니다.
3. 설치 언어를 고르고 "다음"을 눌러 마칩니다.

- 공식 버전과 같은 위치(기본 `C:\Program Files\NTE Drive Calc`)에 설치됩니다. 공식 2.3.0, 이전 한국어 패치 적용본, 이전 다국어판 위에 그대로 설치하면 되고, 처음 설치하는 경우에도 이 파일 하나면 됩니다.
- 계정·설정·드라이브·창고·전투 리포트·로그 등 사용자 데이터는 그대로 유지됩니다.
- 되돌리려면 공식 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.0.exe`)을 같은 위치에 다시 설치합니다. 공식 설치 프로그램은 [원본 프로젝트의 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)에서 받으세요.

자세한 안내는 [README](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.md)에 있습니다.

### 들어 있는 것

- **네 가지 화면 언어**: 中文 / 한국어 / 日本語 / English. 왼쪽 아래 버튼으로 실행 중에 바로 전환합니다.
- **팀 시뮬레이션(Beta)**: 캐릭터 24명의 검수된 딜 사이클, 3바퀴, 에스퍼 사이클 반응 항상 계산, 변신·형태 상태 공격, 교체 순서 선택, 결과 설명 패널.
- **딜 사이클 직접 입력**: `제로 서포트 > 제로 E > 제로 평타 평타 평타 > 일로이 교체 > 일로이 Q > 일로이 E > 일로이 평타`처럼 적어서 계산합니다. 사이클 수치·쿨타임·버프·수치 옵션, 저장과 불러오기.
- **전투 리포트 "내 캐릭터로 비교"**: 가져온 전투 리포트를 내 캐릭터의 육성·장비로 다시 계산해 비교합니다.
- **게임 폴더 보호**: 게임 폴더의 `d3d12.dll` / `NTE_Capture.dll`이 이 프로그램의 파일로 확인되지 않으면(예: ReShade) 덮어쓰거나 지우지 않습니다.
- 헥스(覆纹) 비율 수정: 전투 리포트 재현 계산의 파이썬 쪽 참조 계산식에서 링코 패시브 적용 시 0.30 → 0.33(원본 문서에 적힌 분석 컴포넌트의 값). 분석 컴포넌트가 계산하는 전투 리포트 수치는 그대로이며, 팀 시뮬레이션은 별도 계산식에서 같은 0.33을 씁니다.
- 이전 한국어 패치의 문제 수정(창고의 저장/관리 확인 단계 오류 등).
- 공식 설치 프로그램과 같은 방식의 전체 설치 프로그램(설치 화면 4개 언어).

원본과의 차이 전체는 [CHANGES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/CHANGES.md)에 있습니다.

### 알려진 한계

**팀 시뮬레이션은 Beta(미완성)입니다.** 딜 사이클 검수가 완벽하지 않아 결과가 실전과 다를 수 있습니다. 팀 체급을 대략 비교하는 용도로만 쓰세요.

- 적 80레벨·저항 20%의 움직이지 않는 허수아비가 기준이고, 드라이브와 메인/서브 스탯은 공식 졸업 템플릿을 씁니다(내 창고의 장비가 아닙니다).
- 검수된 딜 사이클 모드는 쿨타임과 에너지를 확인하지 않습니다.
- 직접 입력 모드에서 쿨타임·에너지 값이 게임 데이터에 있는 캐릭터는 **2명뿐**입니다: 라크리모사(E 15초, Q 30초, Q 에너지 45)와 카오스(Q 20초). 나머지 캐릭터는 값을 직접 입력해야 검사하고, 비워 두면 검사하지 않습니다.
- 직접 입력의 "입력대로" 모드는 사이클 수치가 부족하거나 인접 속성이 아니어도 서포트 스킬을 내보내므로 실전보다 결과가 높게 나올 수 있습니다(해당 단계에 경고 표시).
- 사이클 수치 규칙(100이 찬 뒤 교체해야 반응 발동)은 실전 기록 한 건에 맞춘 것이라 추가 확인이 필요합니다.
- 반응 규칙 일부는 추정이거나 실전에서 확인되지 않았습니다(스테인의 적용 범위, 링코가 없을 때의 헥스 비율, 서로 다른 팀원의 노바 중첩, 블라썸 꽃의 개화 간격 등).
- 소환물과 잔홍·라크리모사 외의 지속 피해, 전투 엔진이 해석하지 못하는 버프, 일부 캐릭터 고유의 반응 추가 효과는 계산에 들어가지 않습니다. 애니메이션 데이터가 없는 동작은 피해에서 빠집니다(결과가 낮게 나옴).
- 해당 팀에 적용되는 한계는 계산 결과 아래 "가정과 한계"에 표시됩니다.

**번역·화면**

- "사용 방법" 튜토리얼 이미지는 어느 언어를 골라도 한국어입니다.
- 실행 중에 언어를 바꾸면 일부 글자가 다시 시작하기 전까지 이전 언어로 남을 수 있습니다.
- 영어·일본어의 일부 이름(그 언어로 아직 출시되지 않은 캐릭터 등)은 임시 번역이거나 원문 그대로입니다.
- 검색창의 번역 이름 검색은 한글(초성 포함)만 지원합니다. 영어·일본어 화면에서는 중국어 원문으로 검색해야 합니다.
- 게임 언어는 원본과 마찬가지로 简体中文이어야 스캔·감정(문자 인식)이 동작합니다.
- 프로그램 안의 GitHub·채팅 그룹(QQ/Discord)·후원·다운로드·업데이트 링크는 원본 그대로여서 원작자의 페이지로 연결됩니다. 이 빌드에서 생긴 문제를 그쪽에 올리지 말아 주세요.

**확인 범위**

- 실행 파일은 이 저장소의 `src/`로 다시 빌드해 SHA-256이 같은 것을 확인했고, 공식 실행 파일과의 차이가 `src.*` 모듈과 PE 체크섬뿐임을 `verify_exe_l10n.py`로 확인했습니다.
- 설치·업그레이드·제거는 테스트용 설치 프로그램으로 자동 확인했고, 배포용 설치 프로그램은 PC 한 대에 설치해 프로그램이 오류 없이 시작되는 것을 확인했습니다. 공식 설치 프로그램으로 되돌리는 것은 같은 프로그램 ID와 같은 폴더를 쓰는 구조에 따른 것이며, 실제로 실행해 확인하지는 않았습니다.
- 자동 테스트는 오프라인 모드에서 진행했습니다. **게임과 연동되는 기능(동기화, 전투 기록, 자동 장착, 컴포넌트 로드 등)은 게임 폴더 보호와 번역용 문자열 처리를 빼고 원본의 로직 그대로이며, 이 빌드를 게임에 연결해 전부 다시 검증하지는 않았습니다.**
- 게임 폴더 보호는 자동 테스트로 확인했습니다.
- "내 캐릭터로 비교"의 결과는 추정치입니다. 설치본에서는 결과 창이 열리는 것까지만 자동 확인했고, 실제로 가져온 리포트를 넣어 비교를 실행하는 것은 설치본에서 확인하지 못했습니다.
- 설치 파일과 실행 파일에는 코드 서명이 없습니다.

### SHA-256

```
fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177  NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe  (177,299,000 bytes)
30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113  NTE_Drive_Calc_2.3.0_Multilingual_source.zip  (6,565,584 bytes)
4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30  설치되는 NTE_Drive_Calc.exe  (23,750,579 bytes)
505950ca2261902df6c78a61c3f17c6e756b82bb9309689ac08114c4f3a1cbbf  (참고) 바탕이 된 공식 2.3.0 NTE_Drive_Calc.exe  (20,920,550 bytes)
```

```powershell
Get-FileHash .\NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe -Algorithm SHA256
```

### 라이선스

NTE Drive Calc는 GNU AGPL-3.0으로 배포되는 프로그램이고 이 빌드는 그 파생물입니다. 원저작권: NTE Drive Calc contributors ([hxwd94666](https://github.com/hxwd94666)). 수정: [LuinDe](https://github.com/LuinDe), 2026-10-05, 원본 커밋 `d3eca80`(원본 릴리스 태그 `2.3.0.1`, 공식 2.3.0) 기준. 대응 소스는 이 릴리스의 소스 zip과 같은 태그의 저장소에 있습니다([SOURCE_OFFER.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/SOURCE_OFFER.md)).

이 프로그램은 팬이 만든 비공식 도구이며 게임의 개발사·배급사와 관계가 없습니다.

---

## English

**Unofficial modified build of [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.0** (original by hxwd94666 / NTE Drive Calc contributors, AGPL-3.0). Modified by LuinDe on 2026-10-05, based on original commit `d3eca80`. It is not published or supported by the original author; report problems in this repository's Issues, not upstream.

- **Install**: download `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` and run it (UAC "Yes"; the file is unsigned, so on the SmartScreen window click "More info" → "Run anyway"). It contains the whole program, installs to the same location as the official version, can be installed over the official 2.3.0, and keeps your user data. To go back, run the official installer again (from the [original project's Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)).
- **What is in it**: interface in 中文 / 한국어 / 日本語 / English with live switching (buttons at the bottom left); Team Simulation (Beta) with reviewed rotations for 24 characters, 3 loops, Esper Cycle reactions always computed, transformation-state attacks, a swap-order choice and an explanation panel; a Custom Input mode (`Zero support > Zero E > Zero basic basic basic > Oneiroi swap > Oneiroi Q > Oneiroi E > Oneiroi basic`) with options and save / load; "Compare with My Characters" for imported battle reports; protection so that a `d3d12.dll` / `NTE_Capture.dll` in the game folder that is not this program's file (for example ReShade) is never overwritten or deleted; the Hex ratio in the Python reference formula of the battle report replay corrected from 0.30 to 0.33 with Linko's passive (the value the original's documentation gives for its analysis component; battle report figures calculated by that component do not change, and Team Simulation uses the same 0.33 in its own formula).
- **Known limits**: Team Simulation is an unfinished Beta. The rotation review is not complete, so results may differ from real battles. It assumes a stationary Lv80 dummy with 20% resistance and the official graduation templates, the Reviewed Rotation mode does not check cooldowns or energy, and in Custom Input mode only two characters (Lacrimosa, Chaos) have cooldown / energy data; the rest must be entered by hand. Some reaction rules are inferred or not confirmed in game. The tutorial images are Korean in every language. After switching the language while the program runs, a few texts may stay in the previous language until restart. Some English names are provisional or left in the original text. The game language must be Simplified Chinese for scanning and appraisal, as with the original. The GitHub, group chat (QQ / Discord), support, download and update links inside the program are unchanged from the original and lead to the original author's pages; do not report problems of this build there.
- **What was checked**: the executable was rebuilt from `src/` in this repository with an identical SHA-256, and it differs from the official executable only in the `src.*` modules and the PE checksum. Automated tests ran in Offline mode; the features that interact with the game keep the original's logic (apart from the game-folder protection and the string handling for translation) and were not all re-verified against the game in this build. Going back with the official installer follows from the shared application ID and folder and was not exercised.

SHA-256: installer `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177`, source zip `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113`, installed `NTE_Drive_Calc.exe` `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30`. Full guide: [README.en.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.en.md).

## 日本語

**[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.0 を改変した非公式ビルドです**（オリジナル：hxwd94666 / NTE Drive Calc contributors、AGPL-3.0）。LuinDe が 2026-10-05 に改変（ベースはオリジナルのコミット `d3eca80`）。原作者が配布・サポートしているものではありません。問題はオリジナルではなく、このリポジトリの Issues に報告してください。

- **インストール**：`NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe` をダウンロードして実行します（UAC は「はい」。署名がないため SmartScreen が出たら「詳細情報」→「実行」）。プログラム全体が入っており、公式版と同じ場所にインストールされ、公式 2.3.0 の上にそのままインストールでき、ユーザーデータは残ります。戻すときは公式インストーラー（[オリジナルのプロジェクトの Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) から入手）をもう一度実行します。
- **内容**：中文 / 한국어 / 日本語 / English の画面と実行中の切り替え（左下のボタン）。チームシミュレーション (Beta)：24 キャラクターの検証済みローテーション、3 周、エスパーサイクルの反応を常に計算、変身中の攻撃、交代順の選択、説明パネル。直接入力モード（`零 サポート > 零 E > 零 通常 通常 通常 > 伊洛伊 交代 > 伊洛伊 Q > 伊洛伊 E > 伊洛伊 通常`）とオプション、保存/読み込み。取り込んだ戦闘レポートの「自分のキャラで比較」。ゲームフォルダーの `d3d12.dll` / `NTE_Capture.dll` がこのプログラムのファイルでない場合（ReShade など）は上書きも削除もしない保護。戦闘レポート再現計算の Python 側の参照計算式の覆紋比率の修正（リンコのパッシブ有効時 0.30 → 0.33。オリジナルのドキュメントが分析コンポーネントの値として示している数値です。分析コンポーネントが計算する戦闘レポートの数値は変わらず、チームシミュレーションは別の計算式で同じ 0.33 を使います）。
- **既知の制限**：チームシミュレーションは未完成の Beta です。ローテーションの検証が完全ではないため、結果が実戦と異なる場合があります。Lv80・耐性 20% の動かないカカシと公式卒業テンプレートが前提で、検証済みローテーションのモードはクールタイムとエネルギーを考慮しません。直接入力モードでクールタイム・エネルギーのデータがあるのは 2 人（ラクリモサ、カオス）だけで、ほかは手入力が必要です。反応のルールの一部は推定、または実戦で未確認です。チュートリアル画像はどの言語でも韓国語です。実行中に言語を切り替えると、一部の文字が再起動まで前の言語のまま残ることがあります。日本語の一部の名前は仮訳または原文のままです。スキャン・鑑定にはオリジナルと同じくゲームの言語が簡体字中国語である必要があります。プログラム内の GitHub・チャットグループ（QQ / Discord）・支援・ダウンロード・アップデートのリンクはオリジナルのままで、原作者のページにつながります。このビルドで起きた問題はそちらに書き込まないでください。
- **確認した範囲**：実行ファイルはこのリポジトリの `src/` から再ビルドして SHA-256 が一致することを確認し、公式の実行ファイルとの違いが `src.*` モジュールと PE チェックサムだけであることを確認しました。自動テストはオフラインモードで行いました。ゲームと連携する機能は、ゲームフォルダーの保護と翻訳用の文字列処理を除いてオリジナルのロジックのままで、このビルドをゲームに接続してすべてを再検証したわけではありません。公式インストーラーで戻す手順は、同じアプリ ID・同じフォルダーを使う構造に基づくもので、実際に実行して確認してはいません。

SHA-256：インストーラー `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177`、ソース zip `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113`、インストールされる `NTE_Drive_Calc.exe` `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30`。詳しい案内：[README.ja.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.ja.md)

## 中文

**这是在 [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.0 基础上修改的非官方构建**（原版：hxwd94666 / NTE Drive Calc contributors，AGPL-3.0）。由 LuinDe 于 2026-10-05 修改（基于原版提交 `d3eca80`）。它不是原作者发布或支持的版本；问题请反馈到本仓库的 Issues，不要反馈到原版仓库。

- **安装**：下载并运行 `NTE_Drive_Calc_2.3.0_Multilingual_Setup.exe`（UAC 选“是”；文件没有签名，出现 SmartScreen 时点击“更多信息”→“仍要运行”）。安装包包含整个程序，安装位置与官方版本相同，可以直接装在官方 2.3.0 之上，用户数据会保留。要恢复官方版本，重新运行官方安装程序即可（从[原版项目的 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) 获取）。
- **内容**：中文 / 한국어 / 日本語 / English 界面，运行中可切换（左下角按钮）；队伍模拟 (Beta)：24 名角色的已审核循环、3 轮、始终计算环合反应、变身形态中的攻击、出场顺序选择、说明面板；直接输入模式（`零 援护 > 零 E > 零 普攻 普攻 普攻 > 伊洛伊 切换 > 伊洛伊 Q > 伊洛伊 E > 伊洛伊 普攻`）及其选项与保存/读取；导入战报的“与我的角色对比”；游戏目录中的 `d3d12.dll` / `NTE_Capture.dll` 如果不是本程序的文件（例如 ReShade），不会被覆盖或删除；战报重放计算的 Python 侧参考算式中覆纹比例的修正（灵可被动生效时 0.30 → 0.33，即原版文档为其分析组件给出的数值；由分析组件计算的战报数值不变，队伍模拟在独立算式中使用相同的 0.33）。
- **已知限制**：队伍模拟是尚未完成的 Beta，角色循环的审核还不完善，结果可能与实战不同。它以 80 级、抗性 20%、原地不动的木桩和官方毕业模板为前提；已审核循环模式不检查冷却与能量；直接输入模式中只有 2 名角色（安魂曲、卡厄斯）有冷却/能量数据，其余需要手动填写。部分反应规则为推断或未经实战确认。教程图片在任何语言下都是韩语。运行中切换语言后，少数文字可能在重启前仍显示为之前的语言。与原版一样，扫描和鉴定需要游戏语言为简体中文。程序内的 GitHub、交流群（QQ / Discord）、赞助、下载和更新链接与原版相同，会打开原作者的页面；本构建出现的问题请不要反馈到那里。
- **验证范围**：可执行文件已用本仓库的 `src/` 重新构建，SHA-256 完全一致，并确认它与官方可执行文件的差异仅限于 `src.*` 模块和 PE 校验和。自动测试在离线模式下进行；与游戏交互的功能除游戏目录保护和翻译所需的文本处理外沿用原版逻辑，本构建没有连接游戏全部重新验证。用官方安装程序恢复官方版本依据的是相同的应用 ID 和安装目录，并未实际执行验证。

SHA-256：安装程序 `fbdd2979e974517374cb1f7ddda67efffb4da5301802eb1bb8b44dbc2de9a177`，源代码 zip `30f5313862cb868d15ead2c63ec0ae435c147af760781e496b571bac415bd113`，安装后的 `NTE_Drive_Calc.exe` `4d403af14c8e04728ebc26eaa6b2f981dbd245c73ce9920d6bcdabbf123fcb30`。完整说明：[README.zh.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.zh.md)
