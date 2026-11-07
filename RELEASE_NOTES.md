# Global 2.3.5

[엘림 가방 동기화 수정 · 한국어 / English / 日本語 / 中文](RELEASE_NOTES_2.3.5.md)

# Global 2.3.4

[엘림 업데이트 및 새 서명 키로 전환하는 방법 · 한국어 / English / 日本語 / 中文](RELEASE_NOTES_2.3.4.md)

# NTE Drive Calc Global — 릴리스 노트 / Release notes

> **비공식 수정 빌드입니다. 원본 프로그램이 아닙니다.**
> 원본(공식): **NTE Drive Calc** — <https://github.com/hxwd94666/NTE-Drive-Calculator> (hxwd94666 / NTE Drive Calc contributors, AGPL-3.0)
> 이 저장소의 릴리스는 원본 공식 버전을 수정해서 만든 것이며, 원작자가 배포하거나 지원하지 않습니다. 문제는 원본 저장소가 아니라 [이 저장소의 Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)에 알려 주세요.
>
> **Unofficial modified build — not the original program.** Original: <https://github.com/hxwd94666/NTE-Drive-Calculator>. Each entry has a Korean part followed by short notes in English, 日本語 and 中文.

최신 버전이 위에 있습니다. / Newest first: **2.3.2** (2026-10-23) · **2.3.1-global.2** (2026-10-19, 잠시 공개 / published briefly) · **2.3.1-global.1** (2026-10-11). Global의 버전 번호는 2.3.2부터 원본과 따로 매깁니다 / From 2.3.2 on, Global numbers its versions independently of the original. Global 2.3.0의 노트는 [그 릴리스](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.0-global.1)에 있습니다.

> [!TIP]
> **ReShade·DLSS5와 함께 쓰기 (Loader 방식)** — [한국어](docs/COEXIST_RESHADE_DLSS.ko.md) · [English](docs/COEXIST_RESHADE_DLSS.en.md) · [日本語](docs/COEXIST_RESHADE_DLSS.ja.md) · [中文](docs/COEXIST_RESHADE_DLSS.zh.md)

## 2.3.2 (2026-10-23)

### 한국어

NTE Drive Calc 공식 2.3.1을 바탕으로 한 Global(다국어) 릴리스 **2.3.2**입니다. **Global의 버전 번호는 이제 원본과 따로 매깁니다.** 번호는 2.3.2이지만 바탕은 공식 2.3.1입니다. 업데이트는 프로그램 안에서 받을 수 있습니다.

2.3.1-global.1이나 2.3.1-global.2를 쓰고 있다면 **이 버전은 한 번 직접 설치해야 합니다.** 2.3.1-global.1에는 업데이트 기능이 없고, 2.3.1-global.2는 새 버전 번호 형식을 알아보지 못해 이 버전을 알려 주지 않기 때문입니다. 이 버전을 설치한 뒤에는 새 Global 버전이 나오면 프로그램이 알려 주고 설치합니다.

#### 받을 파일

| 파일 | 설명 |
|---|---|
| `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` | 설치 프로그램. 프로그램 전체가 들어 있습니다. |
| `NTE_Drive_Calc_2.3.2_Multilingual_source.zip` | 이 빌드의 소스 코드(AGPL-3.0). 태그 `v2.3.2`의 커밋에도 같은 내용이 있습니다. |
| `NTE_Drive_Calc_2.3.2_release.json`, `NTE_Drive_Calc_2.3.2_release.json.sig` | 프로그램 안 업데이트가 확인하는 매니페스트와 그 서명입니다. 직접 받을 필요는 없습니다. |

파일 이름에는 Global 버전(`2.3.2`)이 들어갑니다.

#### 설치

1. NTE Drive Calc가 켜져 있으면 종료합니다.
2. 설치 파일을 실행하고 UAC 창에서 "예"를 누릅니다. 코드 서명이 없어서 "Windows의 PC 보호" 창이 뜨면 "추가 정보" → "실행"을 누릅니다.
3. 설치 언어를 고르고 "다음"을 눌러 마칩니다.

- 공식 버전과 같은 위치(기본 `C:\Program Files\NTE Drive Calc`)에 설치됩니다. Global 2.3.1-global.2, Global 2.3.1(2.3.1-global.1), 공식 2.3.1, 한국어 패치를 적용한 2.3.1, Global 2.3.0 위에 그대로 설치하면 되고, 처음 설치하는 경우에도 이 파일 하나면 됩니다.
- 계정·설정·드라이브·창고·전투 리포트·육성 기록·로그·저장한 사이클 등 사용자 데이터는 그대로 유지됩니다. 한국어 패치가 만든 백업 파일도 지우지 않습니다.
- 되돌리려면 공식 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.1.exe`)을 같은 위치에 다시 설치합니다. 공식 설치 프로그램은 [원본 프로젝트의 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)에서 받으세요.

자세한 안내는 [README](README.md)에 있습니다.

#### 2.3.1-global.2에서 달라진 점

- 홈 화면 "작업 공간" 머리글의 캐릭터 그림이 레이븐(黑羽)에서 아카네 린(明音凛)으로 바뀌었습니다.
- 버전 번호 형식이 바뀌었습니다. Global 버전은 이제 `2.3.2`처럼 원본과 따로 매기는 번호이고, 태그는 `v2.3.2`입니다. `v2.3.1-global.2` 같은 이전 형식의 릴리스도 그대로 읽으며, 순서는 2.3.1-global.1 < 2.3.1-global.2 < 2.3.2입니다.
- 2.3.1-global.2는 2026-10-19에 잠시 공개했던 버전이고, 그 내용(아래)은 이 버전에 모두 들어 있습니다. 2.3.1-global.2는 새 번호 형식을 알아보지 못하므로 이 버전을 한 번 직접 설치해 주세요(2.3.1-global.1에서 올 때와 같습니다).

#### 2.3.1-global.1에서 달라진 점 (2.3.1-global.2에서 처음 공개)

##### 프로그램 안 업데이트 (Global 전용)

- 새 Global 버전이 나오면 프로그램이 버전과 업데이트 내용을 보여 주고 [지금 업데이트] [나중에] [이 버전 건너뛰기] 중에서 고르게 합니다.
- [지금 업데이트]를 누르면 설치 프로그램을 내려받아 확인합니다. 준비되면 [지금 설치하고 다시 시작]을 누르거나, 프로그램을 끌 때 설치를 고를 수 있습니다. 설치는 프로그램을 닫은 뒤 같은 폴더에 설치 마법사 없이(진행 창만 표시) 진행되고, [지금 설치하고 다시 시작]을 눌렀다면 끝난 뒤 프로그램이 다시 시작됩니다. 사용자 데이터는 그대로 남습니다.
- 확인 시점: 프로그램을 시작할 때 하루에 한 번까지, 그리고 설정 → "소프트웨어 업데이트" 카드의 [업데이트 확인]을 누를 때. 자동 확인은 같은 카드의 "시작할 때 자동으로 업데이트 확인 (하루 한 번)"을 끄면 멈춥니다.
- **업데이트는 이 저장소(LuinDe/NTE-Drive-Calc-Global)의 릴리스에서만 옵니다.** Global은 이제 원본과 별개로 개발·업데이트됩니다. 원본의 업데이트 기능(원본 릴리스·Mirror酱 확인, 공식 설치 파일 내려받기·열기, 업데이트 확인 창)은 이 빌드에서 뺐고, 원본 서버에 버전을 묻지 않으며, 프로그램 안 업데이트로 공식 빌드가 설치되는 일은 없습니다.
- 확인하는 것: 이 저장소의 정식 릴리스만(초안·사전 릴리스 제외), Global 버전 규칙(`v<주>.<부>.<수>`, 2.3.2 이전 릴리스는 `v<주>.<부>.<수>-global.<n>`)으로 지금보다 새 버전, 정해진 파일 이름과 이 저장소의 다운로드 주소, GitHub가 알려 주는 SHA-256, 배포자의 릴리스 서명 키(Ed25519)로 서명된 매니페스트. 서명이 없거나 맞지 않는 릴리스는 알리지 않고, 내려받은 설치 프로그램은 크기와 SHA-256이 모두 맞을 때만 실행합니다.
- 릴리스 서명 키(공개키) 지문: `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`. 설정의 "소프트웨어 업데이트" 카드에도 같은 지문이 나옵니다.
- 설치 프로그램은 관리자 권한으로 조용히 실행됩니다(공식과 같은 Program Files 폴더에 설치하기 때문입니다).
- 버전 번호는 Global 고유의 번호입니다. "소프트웨어 업데이트" 카드에 Global 버전과, 참고용으로 바탕이 된 원본 버전(2.3.1)을 따로 보여 줍니다.
- 프로그램 안의 업데이트·다운로드·릴리스 링크는 이 저장소로 연결됩니다. 원본 GitHub·채팅 그룹(QQ/Discord)·후원 링크는 원작자 표기로 그대로 두었습니다.

##### 팀 시뮬레이션: 울티메이트 에너지·사이클 수치·쿨타임

- 24명 모두 타격마다 울티메이트 에너지와 에스퍼 사이클 수치를 게임 데이터대로 쌓고, 스킬 쿨타임을 적용합니다. 쿨타임은 게임 데이터와 커뮤니티 자료(prydwen.gg, GameWith)로 채웠고, 시계는 시간 정지를 뺀 전투 시간입니다. 값마다 출처와 신뢰도가 설명란에 나옵니다.
- 자료가 없는 캐릭터와 값은 예전 규칙(1·3바퀴 시작 때 사이클 수치 100)을 대신 쓰고, 설명란에 그렇게 표시합니다.
- **교체 규칙**: 팀에서 다음 스킬의 쿨타임이 **0.3초 이상** 남았거나 울티메이트 에너지가 모자라면 기다리지 않고 다음 캐릭터로 교체합니다. **0.3초 미만**이면 기다렸다가 사용합니다. 모든 팀원이 준비되지 않았으면 가장 빨리 준비되는 팀원을 기다립니다. 설명란에 교체·대기 내역이 나옵니다.
- 혼자 돌리는 아크 효율표·돌파 효율표는 교체할 팀원이 없으므로 쿨타임을 기다립니다.
- 직접 입력은 기본이 "입력대로"(경고만)이고, "엄격"을 고르면 같은 교체 규칙을 적용합니다.
- 결과: 검수된 팀 대부분은 결과가 같습니다. 쿨타임이 빠듯한 빠른 팀(예: 일로이가 들어간 팀)은 교체가 늘어 총피해가 줄 수 있습니다.

##### 돌파 자유 선택과 돌파 효율표

- 이환의 돌파는 순서와 관계없이 고를 수 있습니다(예: ③·⑤·①). 팀 시뮬레이션의 캐릭터 카드에서 돌파 효과 6개를 하나씩 켜고 끌 수 있고("돌파 n/6"), 공명은 고른 효과와 관계없이 돌파 3개·6개에서 켜집니다. 예전처럼 "돌파 N = 1~N번 효과"로 가정하지 않습니다. 예전에 저장한 팀과 사이클은 그대로 열립니다(돌파 수만 있으면 1~N번으로 읽습니다).
- 돌파 효과 192개 중 129개를 계산에 넣었습니다. 나머지는 "측정 필요"(34개, 0%로 보지 않음)와 "계산 불가"(29개: 회복·보호막·피격·다수 대상처럼 목각인형 피해와 관계없는 효과)로 따로 표시합니다. 시뮬레이션에서 조건을 재현할 수 없는 효과는 기대값으로 넣고 "기대값"으로 표시합니다.
- 아크 효율표 아래에 **"캐릭터 돌파 효율(Beta)"** 표를 추가했습니다(처음에는 접혀 있음). 돌파 효과를 하나만 더했을 때와 돌파 6개에서 하나만 뺐을 때의 DPS 변화(%), 공명3·공명6, 돌파 전체를 1바퀴·3바퀴로 보여 줍니다. 값은 미리 계산해 두었고, 데이터가 맞지 않으면 PC에서 다시 계산합니다.
- 라크리모사 ③은 남은 지속 피해를 한 번에 정산하고 그 층을 지우는 방식으로 계산합니다.

##### 아카네 린: 중국 정식 출시 데이터

- 계산기에 들어 있는 게임 데이터의 아카네 린 값은 출시 전 값입니다. 중국 서버 정식 출시(10-15) 뒤 서로 독립된 중국 자료 두 곳 이상에서 일치하는 값만 실행 중에 바꿔서 계산합니다(돌파 효과·공명·「반짝이는 별의 격정」·전용 아크 「달의 대척점」 등). 게임 데이터 파일 자체는 바꾸지 않습니다.
- 쿨타임과 울티메이트 에너지는 아직 확인되지 않았습니다. 팀 시뮬레이션 설명, 아크 효율표, 돌파 효율표에 이 사실을 표시합니다.
- 전투 리포트의 분석 컴포넌트(원본에 포함된 프로그램)는 출시 전 데이터로 계산합니다. 아카네 린이 있는 기록에는 안내가 한 줄 나옵니다.

##### 푸카 특훈

- 게임 1.4에서 생긴 계정 성장 "푸카 특훈"(Lv 0~20)을 계산에 넣습니다. 캐릭터 페이지의 가구 보너스 카드에 레벨을 입력하면(기본 0) 캐릭터 패널, 한계 이득, 팀 시뮬레이션, 새로 녹화하는 전투 리포트에 공격력·방어력·HP·치명 확률·치명 피해·사이클 강도·붕괴 강도가 더해집니다(Lv 20 합계 +28 / +30 / +420 / +2.5%p / +5%p / +12 / +12).
- 전투 리포트는 녹화를 시작할 때의 레벨을 기록에 고정합니다. 이 기능 전에 녹화한 기록은 Lv 0으로 계산하며 소급하지 않습니다(카드에 안내가 나옵니다).
- "특훈 전체 반영"(기본 켜짐): 수정 사본과 한계 이득 비교를 다시 계산할 때 특훈 전체를 넣습니다. 이때 "한계 이득 수동 조정" 줄이 보이고 정량화 상태가 "부분"으로 나올 수 있습니다. 끄면 공격력·치명 피해 몫만 반영됩니다.
- "푸카 특훈 만렙(20) 기준으로 보기": 아크 효율표와 졸업률의 졸업 템플릿을 Lv 0 / Lv 20 중에서 고릅니다(계정별로 기억, 기본은 Lv 0 = 이전과 같은 결과).

##### RTSS(RivaTuner) 호환성 안내

- 작성자 환경에서는 RTSS(RivaTuner Statistics Server, MSI Afterburner와 함께 설치됨)가 기본 후킹 방식으로 켜져 있으면 2.3.1의 게임 내 컴포넌트와 함께 게임이 시작하자마자 꺼졌습니다(D3D12 오류 `80004004 (E_ABORT)`).
- 이 빌드는 RTSS 설정을 읽기만 해서, 그럴 위험이 있으면 [네이티브 Loader 시작]을 누를 때 해결 방법(HTGame.exe 프로필에서 "Use Microsoft Detours API hooking" 켜기)을 안내하고, 환경 검사의 "검사 상세"에도 표시합니다. RTSS 설정은 바꾸지 않습니다.

##### 그 밖의 수정

- 일본어: 직접 입력 팔레트 툴팁의 스킬 이름(아카네 린 E 홀드 등 9줄)이 중국어로 나오던 것을 고쳤습니다. 치즈(小吱)의 일본어 이름을 「ちぃちゃん」으로 통일했습니다(영어 설명문은 "Chiz").
- 팀 시뮬레이션 카드의 캐릭터 선택칸에서 긴 이름(라크리모사 등)이 잘리던 것을 고쳤습니다. 그래도 안 들어가면 "…"로 줄이고 툴팁에 전체 이름을 보여 줍니다.

#### 알려진 한계

이번 버전에서 새로 생긴 것과 꼭 알아야 할 것을 적었습니다. 2.3.1-global.1부터 이어지는 한계(튜토리얼 이미지, 번역, 검색 등)는 아래 2.3.1-global.1 항목에 있습니다.

- **팀 시뮬레이션, 아크 효율표, 돌파 효율표는 Beta(미완성)입니다.** 딜 사이클 검수가 완벽하지 않아 결과가 실전과 다를 수 있습니다. 대략적인 비교 용도로만 쓰세요. 대상은 움직이지 않는 Lv80 허수아비(저항 20%)이고, 드라이브와 메인/서브 스탯은 공식 졸업 템플릿을 씁니다(내 창고의 장비가 아닙니다). 효율표는 캐릭터 혼자 계산하므로 팀원·서포트 스킬에 기대는 효과는 0으로 계산됩니다.
- 팀 시뮬레이션의 자원과 교체 규칙:
  - 쿨타임 일부는 커뮤니티 자료(prydwen.gg, 신뢰도 낮음 표시)입니다. 확인하지 못한 쿨타임(E: 하토르·잔홍·아카네 린·카오스·일로이·신쿠, Q: 잔홍·아카네 린·신쿠)은 검사하지 않습니다.
  - 울티메이트 에너지 비용은 호토리(전용 게이지)만 게임 데이터에 있어서, 다른 캐릭터는 에너지가 모자라도 울티메이트를 미루지 않습니다(설명란에 "미확인"으로 표시).
  - 혼자 돌리는 딜사이클 일부는 쿨타임 대기가 생겨 이전 버전과 결과가 다를 수 있습니다. 직접 입력은 기본값이 "경고만"이라 쿨타임이 남아 있어도 입력대로 계산합니다("엄격"을 고르면 교체 규칙을 적용합니다).
- 돌파:
  - 192개 효과 중 63개는 아직 계산하지 않습니다. 둘 다 0%로 보지 않고 표와 툴팁에 따로 표시합니다.
    - **측정 필요**(34개): 효과가 붙는 타격이나 자원(소환수의 공격, 캐릭터 고유 자원 등)이 아직 계산기의 타임라인에 없거나, 필요한 수치·발동 시점이 게임 데이터에도 설명문에도 없어서 게임에서 재 봐야 하는 효과입니다.
    - **계산 불가**(29개): 회복·보호막·이동처럼 피해와 관계없거나, 붕괴·처치·피격·여러 대상·적의 스킬이 있어야 발동해서, 움직이지 않는 허수아비 1명에게 주는 피해로는 나타나지 않는 효과입니다.
  - 시뮬레이션에서 조건을 재현할 수 없는 효과는 기대값으로 계산하고 "기대값"으로 표시합니다. 라크리모사 ③은 남은 지속 피해를 한 번에 정산하는 해석으로 계산합니다.
- 아카네 린(중국 출시 데이터):
  - 출시 뒤 서로 독립된 자료 두 곳 이상이 일치한 값만 바꿨습니다. 자료: 중국 공식 공지(yh.wanmei.com, 10-14·10-15·10-16), 중국 출시 클라이언트 화면(바하무트 forum.gamer.com.tw), TapTap 공략, 중국판 정보임을 밝힌 일본 공략(kamigame·AppMedia·GameWith), 아크 문구만 LDShop.
  - 확인되지 않아 게임 데이터(출시 전 값)를 그대로 쓰는 것: Lv80 기본 능력치, 스킬 배율, 평타 전달 기본값, 카덴차 연격 지속 시간, 자료가 한 곳뿐인 메커니즘 5개, 전용 아크 「달의 대척점」의 1재련 치명타 확률과 상(相) 속성 피해(자료끼리 16%와 15%·20%로 엇갈려 게임 데이터의 16% 유지), 2~5재련의 치명타 확률·평타·상 속성 값. 2~5재련의 스킬 피해 증가(+35~56%)는 1재련 값(+28%)에서 계산한 값입니다.
  - E·Q 쿨타임과 울티메이트 에너지는 자료가 없어 비워 두고 검사하지 않습니다. 졸업 템플릿, 추천 가중치, 한국어·영어·일본어 이름은 이 보정에 들어 있지 않습니다.
- **전투 리포트의 분석 컴포넌트는 바꾸지 않았습니다.** 녹화한 전투는 원본에 들어 있는 분석 컴포넌트(`nte-analysis-core`, 수정하지 않음)가 계산하므로, 팀 시뮬레이션의 자원·돌파 규칙과 아카네 린 보정은 전투 리포트에 적용되지 않습니다. 아카네 린이 있는 기록은 출시 전 데이터(9-24)로 계산되고 화면에 안내가 한 줄 나옵니다.

#### 확인 범위

- 실행 파일은 이 저장소의 `src/`로 다시 빌드해 SHA-256이 같은 것을 확인했고(두 번 빌드해 바이트 동일, 소스 zip만으로 다시 빌드해도 동일), 공식 실행 파일과의 차이가 `src.*` 모듈(원본 업데이트 모듈 2개 제거 포함)과 PE 체크섬뿐임을 `verify_exe_l10n_g231.py`로 확인했습니다.
- Global 전체 테스트 84개가 통과했고, 실행 파일을 네 언어로 띄워 화면과 계산 결과를 점검했습니다(ko 140/140 · en 120/120 · ja 120/120 · zh 120/120; 팀 시뮬레이션·효율표 수치는 소스 실행 결과와 같음).
- 프로그램 안 업데이트는 테스트용 빌드(이 버전에 테스트 훅만 더한 것)와 로컬 테스트 서버(GitHub 대역), 테스트 서명 키로 끝까지 확인했습니다: 알림·내려받기·검증·조용한 설치·재시작, 나중에/건너뛰기, 수동 확인, 오프라인·요청 제한, 해시·크기 불일치, 잘못된 파일 이름, 초안·사전 릴리스, 낮은 버전, 다운로드 취소, 설치 실패, 서명 없는/잘못된 릴리스, 수정된 릴리스 본문 등 13개 시나리오 384개 항목(네 언어). 원본 프로젝트로 가는 요청이 없는 것도 확인했습니다. 실제 GitHub 릴리스로 업데이트해 보는 것은 다음 버전부터 가능합니다(새 버전 번호 형식을 읽는 첫 버전이 이 버전입니다).
- 설치·업그레이드·제거는 테스트용 설치 프로그램(권한 없이 설치되는 변형)으로 자동 확인했습니다(배포용 실행 파일 10/10, 테스트용 실행 파일 12/12): 새 설치, 2.3.1-global.1 위 업그레이드(조용한 설치와 설치 마법사 모두), 2.3.1-global.2 위 업그레이드, 공식 2.3.1·Global 2.3.0·한국어 패치 2.3.1 위 업그레이드, 같은 버전 재설치, 제거(사용자 데이터 유지). 배포용 설치 프로그램은 **관리자 권한으로 실제 설치해 보지 않았습니다.**
- 게임과 연동되는 기능은 이번에도 게임에 연결해 다시 검증하지 않았습니다. RTSS 안내는 작성자 PC의 실제 RTSS 설정을 읽어서만 확인했습니다.
- 설치 파일과 실행 파일에는 코드 서명이 없습니다(프로그램 안 업데이트는 별도의 릴리스 서명 키로 확인합니다).

#### SHA-256

```
c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87  NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe  (184,850,846 bytes)
29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa  NTE_Drive_Calc_2.3.2_Multilingual_source.zip  (7,478,833 bytes)
3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f  설치되는 NTE_Drive_Calc.exe  (25,221,222 bytes)
5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3  (참고) 바탕이 된 공식 2.3.1 NTE_Drive_Calc.exe  (21,320,661 bytes)
```

설치 프로그램의 SHA-256은 릴리스 페이지의 파일 목록(GitHub가 보여 주는 sha256)과 서명된 매니페스트 `NTE_Drive_Calc_2.3.2_release.json`에도 있습니다.

```powershell
Get-FileHash .\NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe -Algorithm SHA256
```

#### 서명 확인하기 (선택)

프로그램 안 업데이트는 이 확인을 스스로 합니다. 설치 파일을 직접 받았을 때 손으로 확인하려면 Windows 10/11에 들어 있는 OpenSSH의 `ssh-keygen`을 씁니다.

1. 설치 파일, `NTE_Drive_Calc_2.3.2_release.json`, `NTE_Drive_Calc_2.3.2_release.json.sig`를 한 폴더에 받습니다.
2. 그 폴더에서 **명령 프롬프트**(cmd)를 열고 아래 두 줄을 실행합니다(PowerShell에서는 `<`를 쓸 수 없습니다). 첫 줄은 배포자의 공개키로 `allowed_signers` 파일을 만듭니다.

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.2_release.json.sig < NTE_Drive_Calc_2.3.2_release.json
```

3. `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`가 나오면 매니페스트가 배포자의 릴리스 키로 서명된 것입니다. `Could not verify signature`가 나오면 그 파일을 쓰지 말고 [Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)에 알려 주세요.
4. 매니페스트를 메모장으로 열어 `installer`의 `sha256`과 `size`가 받은 설치 파일과 같은지 확인합니다(`certutil -hashfile NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe SHA256`).

#### 라이선스

NTE Drive Calc는 GNU AGPL-3.0으로 배포되는 프로그램이고 이 빌드는 그 파생물입니다. 원저작권: NTE Drive Calc contributors ([hxwd94666](https://github.com/hxwd94666)). 수정: [LuinDe](https://github.com/LuinDe), 2026-10-20(2.3.2), 원본 커밋 `0e7a6b4`(공식 2.3.1의 소스) 기준. 대응 소스는 이 릴리스의 소스 zip과 태그 `v2.3.2`의 커밋에 있습니다([SOURCE_OFFER.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/SOURCE_OFFER.md)).

이 프로그램은 팬이 만든 비공식 도구이며 게임의 개발사·배급사와 관계가 없습니다.

### English

This is an **unofficial modified build of [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1** (original by hxwd94666 / NTE Drive Calc contributors, AGPL-3.0). Global release **2.3.2**, modified by LuinDe on 2026-10-20, based on original commit `0e7a6b4` (the source of the official 2.3.1). It is not published or supported by the original author; report problems in this repository's Issues, not upstream.

- **Users of 2.3.1-global.1 or 2.3.1-global.2 install this version once by hand** (.1 has no updater; .2 does not recognise the new version format and will not offer this release). From this version on, new Global versions arrive inside the program.
- **Global now numbers its versions independently of the original.** Global 2.3.2 is based on the official 2.3.1.
- **Changes since 2.3.1-global.2** (published briefly on 2026-10-19): everything of 2.3.1-global.2 is included (the items marked "New" below are new since 2.3.1-global.1); the header of the home page ("Workbench") now shows Akane Rin instead of Raven; the version format is now plain `2.3.2` (tag `v2.3.2`). Older tags such as `v2.3.1-global.2` are still read, in the order 2.3.1-global.1 < 2.3.1-global.2 < 2.3.2.
- **Install**: download `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` and run it (UAC "Yes"; the file is not code-signed, so on the SmartScreen window click "More info" → "Run anyway"). It contains the whole program, installs to the same location as the official version, can be installed over Global 2.3.1-global.2, Global 2.3.1 (2.3.1-global.1), the official 2.3.1, a Korean-patched 2.3.1 or Global 2.3.0, and keeps your user data. To go back, run the official installer again (from the [original project's Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)). The asset names carry the Global version (`2.3.2`).
- **New: in-app updates (Global only).** The program checks **only the Releases of this repository** (LuinDe/NTE-Drive-Calc-Global) at most once a day at startup and with [Check for Updates] on the "Software Update" card in Settings (untick "Check for updates at startup (at most once a day)" there to turn the automatic check off). A new version is shown with its notes and [Update Now] / [Later] / [Skip This Version]; [Update Now] downloads the installer and verifies its size and SHA-256 against GitHub's digest and a manifest signed with the maintainer's Ed25519 release key (fingerprint `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`, also shown on the card); then [Install and Restart Now] (or installing when you quit) closes the program, runs the installer silently with administrator rights in the same folder (user data kept) and, with [Install and Restart Now], starts the program again. Drafts, prereleases, unsigned or tampered releases are never offered; versions are compared by Global's own grammar `v<major>.<minor>.<patch>` (releases before 2.3.2: `v<major>.<minor>.<patch>-global.<n>`). Global is now developed independently of the original: the original's update check (its releases, Mirror酱), the official-installer download and the update dialog are removed, no version request goes to the original's servers, and no in-app path installs the official build. In-app update / download / release links lead to this repository; the original's GitHub, chat and support links stay as credit. The "Software Update" card shows the Global version and, for information, the original version it is based on (2.3.1).
- **New: Team Simulation resources.** For all 24 characters, ultimate energy and the Esper-Cycle gauge build up per hit from the game data, and skill cooldowns apply (game data plus community sources prydwen.gg / GameWith; the clock is combat time without time stops). Every value shows its source and confidence in the explanation panel; characters or values without data fall back to the old rule (gauge 100 at the start of loops 1 and 3) and say so. **Swap rule**: in a team, a skill whose cooldown still has **0.3 s or more** left, or an ultimate without enough energy, hands over to the next character; with less than 0.3 s left the character waits and uses it. Solo tables (Arc / Awakening Efficiency) wait, since there is nobody to swap to; Custom Input stays "as entered" (warnings only) unless you choose "Strict". Most reviewed teams give the same result; fast teams with tight cooldowns (e.g. with Oneiroi) may swap more and deal less total damage.
- **New: free awakening choice and the awakening efficiency table.** Awakening effects can be taken in any order (e.g. ③ ⑤ ①): the member cards of Team Simulation toggle each of the six effects ("Awakening n/6"), and the resonances turn on at 3 and 6 awakenings whatever the chosen effects. Saved teams and cycles open as before (a plain count means effects 1..N). 129 of the 192 effects are computed; the others are marked "Unmeasured" (34, never shown as 0 %) or "Not computable" (29: healing, shields, being hit, several targets …); effects whose condition the simulator cannot reproduce use an expected value and are marked "expected". A new **"Character Awakening Efficiency (Beta)"** table under the Arc Efficiency table (collapsed at first) shows the DPS change of adding one effect, removing one from all six, Resonance 3 / 6 and all six, for 1 and 3 loops (precomputed; recomputed on your PC when the data do not match). Lacrimosa ③ settles the remaining damage over time at once and removes that stack.
- **New: Akane Rin on CN release data.** The bundled game data holds pre-release values for Akane Rin. Values of the CN release (10-15) on which at least two independent Chinese sources agree replace them at run time (awakening effects, resonances, "Sparkling Star Fervor", her exclusive arc …); the data file itself is not changed. Cooldowns and ultimate energy are still unverified, and the pages say so. The battle report's analysis component (part of the original program) still uses the pre-release data; records with Akane Rin show a note.
- **New: Puka Boot Camp.** The account-wide progression of game version 1.4 (Lv 0–20, entered on the Furniture Bonus card of the character page) adds ATK, DEF, HP, CRIT Rate, CRIT DMG, cycle and break intensity to panels, marginal gains, Team Simulation and newly recorded battle reports (+28 / +30 / +420 / +2.5 pp / +5 pp / +12 / +12 at Lv 20). Reports freeze the level when recording starts; older reports count as Lv 0. "All Boot Camp stats" (on by default) includes the whole bonus in recomputed modified copies and marginal comparisons ("Manual Marginal Adjustment" rows, status may read "Partial"); "View at Puka Boot Camp max (Lv.20)" switches the graduation template of the Arc Efficiency table and the graduation rate.
- **New: RTSS (RivaTuner) compatibility notice.** On the author's PC, RTSS with its default hooking made the game crash at start together with the 2.3.1 in-game component (D3D12 `80004004 (E_ABORT)`). When the program sees that risk (it only reads the RTSS settings), [Start native Loader] explains the fix (turn on "Use Microsoft Detours API hooking" in an HTGame.exe profile), and "Detection Details" lists it.
- **Fixes**: Japanese skill names in the Custom Input palette tooltips (nine lines were Chinese), one Japanese name for Chiz (ちぃちゃん), and long names (e.g. Lacrimosa) no longer cut off in the team cards' character selector.
- **Known limits (new in this version)**: whoever holds the release-signing key could run a program with administrator rights on every PC that updates (the key is kept offline with a passphrase); if this repository's account were taken over, a fake release would not install but could stop the normal update notification; new official versions of the original are not announced. Team Simulation: some cooldowns come from community sources (marked low confidence); unconfirmed cooldowns (E: Hathor, Zankou, Akane Rin, Chaos, Oneiroi, Shinku; Q: Zankou, Akane Rin, Shinku) are not checked, and the ultimate energy cost is known only for Xun (her own gauge), so the other characters are never held back for energy; some solo rotations now wait for cooldowns and give other results than before. Awakening: 63 effects are not computed yet; Akane Rin's cooldowns and ultimate energy are unverified. Puka Boot Camp: the level table comes from public sources and two points are not verified in game (break-intensity total 12; whether ATK / DEF / HP are flat bonuses); marginal-gain breakdowns of reports with the training keep an offset of a few pp; older program versions show the new rows with a Chinese prefix. RTSS: no notice while RTSS is installed but not running; the fix was confirmed on one PC only. The known limits of 2.3.1-global.1 are listed under that release in [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md).
- **Also note**: Team Simulation, the Arc Efficiency table and the awakening efficiency table are unfinished Betas (a stationary Lv80 dummy, the official graduation templates; results may differ from real battles). Of the 192 awakening effects, 34 need in-game measurement (the hits or resources they act on are not on the calculator's time axis yet, or their values or timing are in neither the game data nor the descriptions) and 29 cannot be computed against one stationary dummy (no damage effect, or they need a break, a kill, being hit, several targets or an enemy skill); both are marked and never shown as 0 %. Akane Rin: values that only one source gives or on which the sources disagree keep the game data (Lv80 base stats, skill multipliers, basic-attack conduction base values, the Cadenza Combo duration, five single-source mechanics, the exclusive arc's R1 crit rate and Lakshana bonus and its R2–R5 values); her E / Q cooldowns and ultimate energy are unknown. Sources: the official CN notices, CN release-client screenshots (forum.gamer.com.tw), TapTap guides, Japanese guides of the Chinese version (kamigame, AppMedia, GameWith), LDShop for the arc text only. **The battle report's analysis component (`nte-analysis-core`, unchanged from the original) is not modified**: recorded battles are computed without the Team Simulation rules, and with Akane Rin's pre-release data.
- **What was checked**: the executable was rebuilt from `src/` with an identical SHA-256 (also from the source zip alone) and differs from the official one only in the `src.*` modules (including the removal of the original's two update modules) and the PE checksum. All 84 Global tests pass, and the executable was run in all four languages (ko 140/140 · en 120/120 · ja 120/120 · zh 120/120; Team Simulation and efficiency numbers equal a source run). The in-app updater was tested end to end with a test build (this version plus test hooks), a local GitHub stand-in and a test signing key (13 scenarios, 384 checks, four languages; no request to the original project); an update through the real GitHub becomes possible from the next version. Install, upgrade (over 2.3.1-global.1 silently and through the wizard, over 2.3.1-global.2, the official 2.3.1, Global 2.3.0 and a Korean-patched 2.3.1), reinstall and uninstall were tested with a test build of the installer that needs no administrator rights (release executable 10/10, test executable 12/12); the release installer was **not run with administrator rights**. Features that interact with the game were not re-verified against the game.

SHA-256: installer `c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87` (184,850,846 bytes; also next to the file on the release page and in the signed manifest `NTE_Drive_Calc_2.3.2_release.json`); source zip `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa`, installed `NTE_Drive_Calc.exe` `3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f`. Full guide: [README.en.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.en.md). Source: tag `v2.3.2`.

**Verify the signature (optional).** The in-app updater does this itself. To check a downloaded installer by hand with the OpenSSH `ssh-keygen` built into Windows 10/11, put the installer, `NTE_Drive_Calc_2.3.2_release.json` and `NTE_Drive_Calc_2.3.2_release.json.sig` in one folder, open **Command Prompt** (cmd) there (PowerShell has no `<` redirection) and run the two lines below; the first writes an `allowed_signers` file with the maintainer's public key. It must print `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`. If it prints `Could not verify signature`, do not use the files and report it in Issues. Then check that `installer.sha256` and `installer.size` in the manifest match the installer (`certutil -hashfile NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe SHA256`).

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.2_release.json.sig < NTE_Drive_Calc_2.3.2_release.json
```

### 日本語

このリリースは **[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 を改変した非公式ビルドです**（オリジナル：hxwd94666 / NTE Drive Calc contributors、AGPL-3.0）。Global リリース **2.3.2**、LuinDe が 2026-10-20 に改変（ベースはオリジナルのコミット `0e7a6b4`＝公式 2.3.1 のソース）。原作者が配布・サポートしているものではありません。問題はオリジナルではなく、このリポジトリの Issues に報告してください。

- **2.3.1-global.1 または 2.3.1-global.2 をお使いの場合、このバージョンは一度だけ手動でインストールしてください**（.1 には更新機能がなく、.2 は新しいバージョン番号の形式を認識できないため、このリリースを通知しません）。このバージョンからは、新しい Global バージョンをプログラム内で受け取れます。
- **Global のバージョン番号は、今後オリジナルとは別に付けます。** Global 2.3.2 は公式 2.3.1 をベースにしています。
- **2.3.1-global.2（2026-10-19 に短期間公開）からの変更**：2.3.1-global.2 の内容はすべて含まれます（下の「新機能」は 2.3.1-global.1 からの変更です）。ホーム画面のヘッダー（「ワークベンチ」）のキャラクター画像を黒羽から明音凛に変えました。バージョン番号の形式は `2.3.2`（タグ `v2.3.2`）になりました。`v2.3.1-global.2` などの以前の形式も引き続き読み取り、順序は 2.3.1-global.1 < 2.3.1-global.2 < 2.3.2 です。
- **インストール**：`NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe` をダウンロードして実行します（UAC は「はい」。コード署名がないため SmartScreen が出たら「詳細情報」→「実行」）。プログラム全体が入っており、公式版と同じ場所にインストールされ、Global 2.3.1-global.2・Global 2.3.1（2.3.1-global.1）・公式 2.3.1・韓国語パッチを適用した 2.3.1・Global 2.3.0 の上にそのままインストールでき、ユーザーデータは残ります。戻すときは公式インストーラー（[オリジナルのプロジェクトの Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) から入手）をもう一度実行します。ファイル名には Global のバージョン（`2.3.2`）が入ります。
- **新機能：プログラム内アップデート（Global 専用）**。確認先は **このリポジトリ（LuinDe/NTE-Drive-Calc-Global）の Releases だけ** で、起動時に 1 日 1 回まで、または「設定」→「ソフトウェア更新」カードの［更新確認］で確認します（自動確認は同じカードの「起動時に更新を自動確認する（1日1回まで）」で止められます）。新しいバージョンがあると、バージョンと更新内容に［今すぐ更新］［後で］［このバージョンをスキップ］が表示されます。［今すぐ更新］はインストーラーをダウンロードし、サイズと SHA-256 を GitHub のダイジェストとメンテナーの Ed25519 リリース鍵（フィンガープリント `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`、カードにも表示）で署名されたマニフェストで確認します。その後［今すぐインストールして再起動］（または終了時にインストール）を選ぶと、プログラムを閉じて同じフォルダーに管理者権限でサイレントインストールし（ユーザーデータは保持）、［今すぐインストールして再起動］の場合はプログラムを再起動します。下書き・プレリリース・署名のない／改ざんされたリリースは通知しません。バージョンは Global 独自の規則 `v<major>.<minor>.<patch>`（2.3.2 より前のリリースは `v<major>.<minor>.<patch>-global.<n>`）で比較します。Global は今後オリジナルとは独立して開発・更新します。オリジナルの更新確認（オリジナルのリリース、Mirror酱）、公式インストーラーのダウンロード、更新ダイアログは削除し、オリジナルのサーバーにバージョンを問い合わせることも、プログラム内の更新で公式ビルドがインストールされることもありません。プログラム内の更新・ダウンロード・リリースのリンクはこのリポジトリにつながり、オリジナルの GitHub・チャット・支援のリンクはクレジットとしてそのまま残しています。「ソフトウェア更新」カードには Global のバージョンと、参考としてベースになったオリジナルのバージョン（2.3.1）を別々に表示します。
- **新機能：チームシミュレーションのリソース**。24 人全員について、ヒットごとのアルティメットエネルギーとエスパーサイクル値をゲームデータどおりに蓄積し、スキルのクールタイムを適用します（ゲームデータとコミュニティ資料 prydwen.gg・GameWith。時計は時間停止を除いた戦闘時間）。値ごとの出典と信頼度は説明欄に表示し、資料のないキャラ・値は従来の規則（1・3 周目の開始時にサイクル値 100）で代用してその旨を表示します。**交代規則**：チームでは、次のスキルのクールタイムが **0.3 秒以上** 残っているか、アルティメットのエネルギーが足りないときは待たずに次のキャラへ交代し、**0.3 秒未満** なら待ってから使います。単独の表（アーク効率・覚醒効率）は交代相手がいないので待ちます。直接入力は既定で「入力どおり」（警告のみ）で、「厳格」を選ぶと同じ規則になります。審査済みのチームの多くは結果が変わりませんが、クールタイムに余裕のない速いチーム（例：イロヒ入り）は交代が増えて総ダメージが下がることがあります。
- **新機能：覚醒の自由選択と覚醒効率表**。覚醒効果は順番に関係なく選べます（例：③⑤①）。チームシミュレーションのキャラカードで 6 つの効果をそれぞれオン／オフでき（「覚醒 n/6」）、共鳴は選んだ効果に関係なく覚醒 3・6 で有効になります。以前に保存したチームとサイクルはそのまま開けます（数だけの場合は効果 1〜N）。192 個の効果のうち 129 個を計算に入れ、残りは「要実測」（34 個、0% 扱いにはしない）と「計算不可」（29 個：回復・シールド・被弾・複数対象など）として表示します。シミュレーターで条件を再現できない効果は期待値で計算し「期待値」と表示します。アーク効率表の下に **「キャラクター覚醒効率 (Beta)」** 表を追加しました（最初は折りたたみ）。効果を 1 つだけ足したとき・6 つから 1 つだけ外したときの DPS 変化、共鳴 3・6、覚醒すべてを 1 周・3 周で表示します（事前計算済み、データが合わないときは PC で再計算）。ラクリモサ③は残りの継続ダメージを一度に精算してその層を消す形で計算します。
- **新機能：明音凛（アカネ・リン）の中国版リリースデータ**。同梱のゲームデータの明音凛はリリース前の値です。中国版リリース（10-15）後、互いに独立した中国の資料 2 つ以上で一致する値だけを実行時に置き換えて計算します（覚醒効果・共鳴・「煌星激昂」・専用アークなど）。データファイル自体は変更しません。クールタイムとアルティメットエネルギーは未確認で、各ページにそう表示します。戦闘レポートの解析コンポーネント（オリジナルに含まれるプログラム）はリリース前のデータのままで、明音凛を含む記録には注記が出ます。
- **新機能：プカ特訓**。ゲーム 1.4 のアカウント共通の育成（Lv 0〜20、キャラページの家具ボーナスカードで入力）を、パネル・限界値・チームシミュレーション・新しく記録する戦闘レポートの攻撃力・防御力・HP・会心率・会心ダメージ・サイクル強度・ブレイク強度に反映します（Lv 20 で +28 / +30 / +420 / +2.5pt / +5pt / +12 / +12）。戦闘レポートは記録開始時のレベルを固定し、以前のレポートは Lv 0 として扱います。「特訓をすべて反映」（既定オン）で変更コピーと限界値比較の再計算に特訓をすべて含めます（「限界値の手動調整」行が表示され、数値化状態が「一部」になることがあります）。「プカ特訓最大（Lv.20）基準で表示」でアーク効率表と完成度の卒業テンプレートを切り替えます。
- **新機能：RTSS（RivaTuner）互換性のお知らせ**。作者の環境では、既定のフック方式の RTSS と 2.3.1 のゲーム内コンポーネントの組み合わせで、ゲームが起動直後に落ちました（D3D12 `80004004 (E_ABORT)`）。そのおそれがあるとき（RTSS の設定は読み取るだけです）、［ネイティブ Loader を起動］で対処方法（HTGame.exe のプロファイルで「Use Microsoft Detours API hooking」をオン）を案内し、「検出詳細」にも表示します。
- **修正**：直接入力パレットのツールチップで中国語のままだったスキル名（9 行）を日本語にし、小吱の日本語名を「ちぃちゃん」に統一しました。チームカードのキャラ選択欄で長い名前（ラクリモサなど）が切れなくなりました。
- **既知の制限（このバージョンで新しいもの）**：リリース署名鍵を持つ人は、更新するすべての PC で管理者権限のプログラムを実行できることになります（鍵はオフラインでパスフレーズ付きで保管）。このリポジトリのアカウントが乗っ取られた場合、偽リリースはインストールされませんが、通常の更新通知が止まることがあります。オリジナルの新しい公式版は通知しません。チームシミュレーション：クールタイムの一部はコミュニティ資料（低信頼度と表示）で、確認できなかったクールタイム（E は 6 人、Q は 3 人）はチェックしません。アルティメットのエネルギーコストは潯（専用ゲージ）しか分からないため、ほかのキャラはエネルギー不足でアルティメットを遅らせません。単独のサイクルの一部はクールタイム待ちが生じ、以前と結果が変わります。覚醒：63 個の効果はまだ計算しません。明音凛のクールタイムとアルティメットエネルギーは未確認です。プカ特訓のレベル表は公開資料によるもので、2 点（ブレイク強度合計 12、攻撃力・防御力・HP が固定値か）はゲーム内で未確認です。特訓のあるレポートの限界値の内訳には数 pt のずれが残り、以前のバージョンのプログラムでは新しい行が中国語の接頭辞で表示されます。RTSS：インストールされていても実行中でなければ表示されず、対処方法は 1 台の PC でのみ確認しました。2.3.1-global.1 の既知の制限は [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md) のそのリリースの項目にあります。
- **その他の注意**：チームシミュレーション・アーク効率表・覚醒効率表は未完成の Beta です（動かない Lv80 のカカシ、公式卒業テンプレート前提。実戦と結果が異なる場合があります）。覚醒効果 192 個のうち 34 個は要実測（効果の対象となるヒットやリソースがまだ計算機のタイムラインにない、または必要な数値・タイミングがゲームデータにも説明文にもない）、29 個は計算不可（ダメージと無関係、またはブレイク・撃破・被弾・複数の対象・敵のスキルが必要で、動かないカカシ 1 体へのダメージには表れない）で、どちらも 0% 扱いにせず表示で区別します。明音凛：出典が 1 つだけの値や出典どうしが食い違う値はゲームデータのまま（Lv80 の基礎ステータス、スキル倍率、通常攻撃の伝導の基本値、華彩連撃の持続時間、出典が 1 つだけの仕様 5 つ、専用アークの精錬1の会心率と相属性ダメージ、精錬2〜5 の値）で、E・Q のクールタイムとアルティメットエネルギーは不明です。出典：中国の公式告知、中国版リリースクライアントの画面（forum.gamer.com.tw）、TapTap の攻略、中国版の情報と明記した日本の攻略（kamigame・AppMedia・GameWith）、アークの文面のみ LDShop。**戦闘レポートの解析コンポーネント（`nte-analysis-core`、オリジナルのまま）は変更していません**。記録した戦闘はチームシミュレーションの規則なしで、明音凛はリリース前のデータで計算されます。
- **確認した範囲**：実行ファイルは `src/` から再ビルドして SHA-256 が一致し（ソース zip だけからの再ビルドでも一致）、公式との違いが `src.*` モジュール（オリジナルの更新モジュール 2 つの削除を含む）と PE チェックサムだけであることを確認しました。Global の全テスト 84 件が通過し、実行ファイルを 4 言語で起動して画面と計算結果を点検しました（ko 140/140 · en 120/120 · ja 120/120 · zh 120/120。チームシミュレーションと効率表の数値はソース実行の結果と一致）。プログラム内アップデートはテスト用ビルド（このバージョンにテスト用フックだけを加えたもの）・ローカルの GitHub 代替サーバー・テスト用署名鍵で端から端まで確認しました（13 シナリオ、384 項目、4 言語。オリジナルへのリクエストなし）。実際の GitHub のリリースでの更新は次のバージョンから可能になります。インストール・アップグレード（2.3.1-global.1 の上にサイレントとウィザードの両方、2.3.1-global.2 の上、公式 2.3.1、Global 2.3.0、韓国語パッチ適用 2.3.1 の上）・再インストール・アンインストールは、管理者権限なしで動くテスト用インストーラーで確認しました（配布用実行ファイル 10/10、テスト用実行ファイル 12/12）。配布用インストーラーは**管理者権限で実際にインストールしてはいません**。ゲームと連携する機能はゲームに接続して再検証していません。

SHA-256：インストーラー `c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87`（184,850,846 バイト。リリースページのファイル横の sha256 と署名付きマニフェスト `NTE_Drive_Calc_2.3.2_release.json` にも記載）、ソース zip `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa`、インストールされる `NTE_Drive_Calc.exe` `3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f`。詳しい案内：[README.ja.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.ja.md)。ソース：タグ `v2.3.2`。

**署名の確認（任意）**：プログラム内アップデートはこの確認を自動で行います。ダウンロードしたインストーラーを手動で確認するには、Windows 10/11 に入っている OpenSSH の `ssh-keygen` を使います。インストーラー・`NTE_Drive_Calc_2.3.2_release.json`・`NTE_Drive_Calc_2.3.2_release.json.sig` を同じフォルダーに置き、そこで **コマンドプロンプト**（cmd）を開いて（PowerShell では `<` が使えません）次の 2 行を実行します。1 行目はメンテナーの公開鍵で `allowed_signers` ファイルを作ります。`Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY` と表示されれば正しい署名です。`Could not verify signature` と表示されたらファイルを使わず、Issues に報告してください。続けて、マニフェストの `installer.sha256` と `installer.size` がインストーラーと一致することを確認します（`certutil -hashfile NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe SHA256`）。

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.2_release.json.sig < NTE_Drive_Calc_2.3.2_release.json
```

### 中文

这是**在 [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 基础上修改的非官方构建**（原版：hxwd94666 / NTE Drive Calc contributors，AGPL-3.0）。Global 发布 **2.3.2**，由 LuinDe 于 2026-10-20 修改（基于原版提交 `0e7a6b4`，即官方 2.3.1 的源代码）。它不是原作者发布或支持的版本；问题请反馈到本仓库的 Issues，不要反馈到原版仓库。

- **正在使用 2.3.1-global.1 或 2.3.1-global.2 的用户需要手动安装一次本版本**（.1 没有更新功能；.2 无法识别新的版本号格式，不会提示本版本）。从本版本起，新的 Global 版本可以在程序内获取。
- **Global 的版本号今后与原版分开编号。** Global 2.3.2 基于官方 2.3.1。
- **相对 2.3.1-global.2（2026-10-19 短暂发布）的变化**：包含 2.3.1-global.2 的全部内容（下面标为“新功能”的是相对 2.3.1-global.1 的变化）；首页标题栏（“工作台”）的角色头像由黑羽改为明音凛；版本号格式改为 `2.3.2`（标签 `v2.3.2`），仍可读取 `v2.3.1-global.2` 等旧格式，顺序为 2.3.1-global.1 < 2.3.1-global.2 < 2.3.2。
- **安装**：下载并运行 `NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe`（UAC 选“是”；文件没有代码签名，出现 SmartScreen 时点击“更多信息”→“仍要运行”）。安装包包含整个程序，安装位置与官方版本相同，可以直接装在 Global 2.3.1-global.2、Global 2.3.1（2.3.1-global.1）、官方 2.3.1、打过韩语补丁的 2.3.1 或 Global 2.3.0 之上，用户数据会保留。要恢复官方版本，重新运行官方安装程序即可（从[原版项目的 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) 获取）。文件名包含 Global 版本号（`2.3.2`）。
- **新功能：程序内更新（仅 Global）**。只检查**本仓库（LuinDe/NTE-Drive-Calc-Global）的 Releases**：启动时每天至多一次，或在“设置”→“软件更新”卡片中点击［检查更新］（取消同一卡片上的“启动时自动检查更新（每天至多一次）”即可关闭自动检查）。发现新版本时显示版本号与更新说明，以及［立即更新］［稍后］［跳过此版本］。［立即更新］会下载安装程序，并用 GitHub 提供的摘要和由维护者 Ed25519 发布密钥（指纹 `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`，卡片上也会显示）签名的清单核对大小与 SHA-256；之后选择［立即安装并重启］（或在退出时安装），程序会关闭并以管理员权限在同一目录静默安装（保留用户数据），选择［立即安装并重启］时安装完成后重新启动程序。草稿、预发布、未签名或被篡改的发布不会提示；版本按 Global 自己的规则 `v<major>.<minor>.<patch>`（2.3.2 之前的发布为 `v<major>.<minor>.<patch>-global.<n>`）比较。Global 今后独立于原版开发和更新：原版的更新检查（原版发布、Mirror酱）、官方安装程序下载和更新对话框已删除，不会向原版服务器查询版本，程序内更新也不会安装官方构建。程序内的更新、下载和发布链接指向本仓库；原版的 GitHub、交流群和赞助链接作为对原作者的署名保留。“软件更新”卡片分别显示 Global 版本和作为参考的原版基础版本（2.3.1）。
- **新功能：队伍模拟的资源**。全部 24 名角色按游戏数据逐击累积终结能量和环合值，并应用技能冷却（游戏数据加社区资料 prydwen.gg、GameWith；计时为扣除时停的战斗时间）。每个数值的来源和可信度显示在说明栏；没有资料的角色或数值沿用旧规则（第 1、3 轮开始时环合值 100），并注明。**切换规则**：在队伍中，下一个技能的冷却还剩 **0.3 秒及以上**，或终结技能量不足时，不等待而直接切换到下一名角色；剩余 **不足 0.3 秒** 时等待后使用。单人表格（弧盘效率、觉醒效率）没有可切换的队友，因此等待。直接输入默认“按输入”（只提示），选择“严格”时使用同样的规则。多数已审核队伍结果不变；冷却紧张的快节奏队伍（例如带伊洛伊的队伍）切换会增加，总伤害可能下降。
- **新功能：自由选择觉醒与觉醒效率表**。觉醒效果可以不按顺序选择（例如 ③⑤①）：在队伍模拟的角色卡片上可以分别开关 6 个效果（“觉醒 n/6”），共鸣与所选效果无关，在觉醒 3 次、6 次时生效。以前保存的队伍和循环照常打开（只有次数时按效果 1–N 读取）。192 个效果中 129 个已计入计算；其余标为“需要实测”（34 个，不按 0% 处理）和“无法计算”（29 个：治疗、护盾、受击、多目标等）。模拟器无法再现条件的效果按期望值计算并标注“期望值”。在弧盘效率表下方新增 **“角色觉醒效率 (Beta)”** 表（初始为折叠）：显示只加一个效果、从全部 6 个中去掉一个时的 DPS 变化，以及共鸣 3、共鸣 6、全部觉醒，分 1 轮和 3 轮（预先计算，数据不符时在本机重新计算）。安魂曲③按一次性结算剩余持续伤害并移除该层计算。
- **新功能：明音凛按国服上线数据计算**。程序自带的游戏数据中，明音凛是上线前的数值。国服正式上线（10-15）后，只有至少两个相互独立的中文资料一致的数值才会在运行时替换计算（觉醒效果、共鸣、「烁星激昂」、专属弧盘等）；游戏数据文件本身不修改。冷却和终结能量尚未确认，相关页面会注明。战报的分析组件（原版自带的程序）仍使用上线前的数据，含明音凛的记录会显示一行提示。
- **新功能：噗卡特训**。游戏 1.4 的账号通用养成（Lv 0–20，在角色页的家具加成卡片中输入）会计入面板、边际收益、队伍模拟和新录制的战报中的攻击力、防御力、生命值、暴击率、暴击伤害、环合强度和倾陷强度（Lv 20 时 +28 / +30 / +420 / +2.5% / +5% / +12 / +12）。战报在开始录制时固定等级，之前的战报按 Lv 0 计算。「全部计入特训」（默认开启）使修改副本与边际对比的重算计入全部加成（会出现「边际手工调整」行，量化状态可能为「部分」）；「按噗卡特训满级（Lv.20）查看」切换弧盘效率表与毕业率所用的毕业模板。
- **新功能：RTSS（RivaTuner）兼容性提醒**。在作者的环境中，默认挂钩方式的 RTSS 与 2.3.1 的游戏内组件同时使用时，游戏一启动就会崩溃（D3D12 `80004004 (E_ABORT)`）。程序检测到这种风险时（只读取 RTSS 设置），点击［启动原生 Loader］会提示解决方法（在 HTGame.exe 的配置中开启“Use Microsoft Detours API hooking”），“检测详情”中也会列出。
- **修复**：日语版直接输入面板提示中仍为中文的技能名（9 行）已翻译，小吱的日语名统一为「ちぃちゃん」；队伍卡片的角色选择框中较长的名字（如安魂曲）不再被截断。
- **已知限制（本版本新增）**：持有发布签名密钥的人可以在所有执行更新的电脑上以管理员权限运行程序（密钥离线保存并有密码保护）；如果本仓库的账号被盗，伪造的发布不会被安装，但可能使正常的更新提示停止；不提示原版的新官方版本。队伍模拟：部分冷却来自社区资料（标为低可信度），未能确认的冷却（变轨技能：哈索尔、残虹、明音凛、卡厄斯、伊洛伊、真红；终结技：残虹、明音凛、真红）不做检查；终结技能量消耗只有浔（专属计量）有数据，其他角色不会因能量不足而推迟终结技；部分单人循环会因等待冷却而与以前结果不同。觉醒：63 个效果尚未计算；明音凛的冷却和终结能量未确认。噗卡特训的等级表来自公开资料，有两点未在游戏内确认（倾陷强度合计 12；攻击力、防御力、生命值是否为固定值）；带特训的战报在边际收益分解中仍有几个百分点的偏差；旧版本程序打开新战报时，新增的行以中文前缀显示。RTSS：已安装但未运行时不会提示，解决方法只在一台电脑上确认过。2.3.1-global.1 的已知限制见 [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md) 中该版本的条目。
- **其他注意事项**：队伍模拟、弧盘效率表和觉醒效率表是尚未完成的 Beta（以原地不动的 80 级木桩和官方毕业模板为前提，结果可能与实战不同）。192 个觉醒效果中，34 个需要实测（效果作用的命中或资源尚未出现在计算器的时间轴上，或所需数值、时机在游戏数据和说明文中都没有），29 个无法计算（与伤害无关，或需要倾陷、击杀、受击、多个目标或敌方技能，对单个不动木桩的伤害体现不出来）；两者都单独标注，不按 0% 处理。明音凛：只有一个来源或来源之间不一致的数值保持游戏数据（80 级基础属性、技能倍率、普攻传导基础值、华彩连段持续时间、只有一个来源的 5 项机制、专属弧盘精炼 1 的暴击率与相属性伤害、精炼 2–5 的数值），E、Q 冷却和终结能量未知。来源：国服官方公告、国服上线客户端截图（forum.gamer.com.tw）、TapTap 攻略、注明为国服信息的日本攻略（kamigame、AppMedia、GameWith），弧盘文本另参考 LDShop。**战报的分析组件（`nte-analysis-core`，与原版相同）没有修改**：录制的战斗不应用队伍模拟的规则，明音凛按上线前的数据计算。
- **验证范围**：可执行文件已用 `src/` 重新构建，SHA-256 完全一致（只用源代码 zip 重新构建也一致），并确认与官方可执行文件的差异仅限于 `src.*` 模块（包括删除原版的 2 个更新模块）和 PE 校验和。Global 全部 84 项测试通过，并以四种语言启动可执行文件检查了界面和计算结果（ko 140/140 · en 120/120 · ja 120/120 · zh 120/120；队伍模拟与效率表的数值与源代码运行结果一致）。程序内更新已用测试构建（本版本仅加入测试挂钩）、本地 GitHub 替身服务器和测试签名密钥做了端到端验证（13 个场景、384 项检查、四种语言；没有向原版项目发出请求）；通过真实 GitHub 发布进行更新要从下一个版本开始才能实现。安装、升级（在 2.3.1-global.1 之上的静默安装和安装向导、在 2.3.1-global.2 之上、官方 2.3.1、Global 2.3.0、打过韩语补丁的 2.3.1 之上）、重新安装和卸载已用无需管理员权限的测试版安装程序验证（发布用可执行文件 10/10，测试用可执行文件 12/12）；发布用安装程序**没有以管理员权限实际安装**。与游戏交互的功能没有连接游戏重新验证。

SHA-256：安装程序 `c9faeb139a4dbad0c2d978b847c86b97dd9c3ee984bc1efba1d8db4f25623f87`（184,850,846 字节；也可见发布页文件旁的 sha256 和签名清单 `NTE_Drive_Calc_2.3.2_release.json`），源代码 zip `29ef19f2566f63745177c4da05c311cb73dee3f7cffa342f4001d86b0ce601aa`，安装后的 `NTE_Drive_Calc.exe` `3a165259d6395050311d30816f34ac547b2b7646e8991e7acb68f36ff4ef384f`。完整说明：[README.zh.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.zh.md)。源代码：标签 `v2.3.2`。

**验证签名（可选）**：程序内更新会自动完成这项检查。要手动检查下载的安装程序，可以使用 Windows 10/11 自带的 OpenSSH `ssh-keygen`：把安装程序、`NTE_Drive_Calc_2.3.2_release.json` 和 `NTE_Drive_Calc_2.3.2_release.json.sig` 放在同一文件夹，在该文件夹打开**命令提示符**（cmd；PowerShell 不支持 `<` 重定向），运行下面两行；第一行用维护者的公钥生成 `allowed_signers` 文件。显示 `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY` 即签名正确；如果显示 `Could not verify signature`，请不要使用这些文件，并在 Issues 中反馈。然后核对清单中的 `installer.sha256` 和 `installer.size` 是否与安装程序一致（`certutil -hashfile NTE_Drive_Calc_2.3.2_Multilingual_Setup.exe SHA256`）。

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.2_release.json.sig < NTE_Drive_Calc_2.3.2_release.json
```

---

## 2.3.1-global.2 (2026-10-19, 잠시 공개 — 내용은 모두 2.3.2에 들어 있음 / published briefly — everything is included in 2.3.2)

### 한국어

NTE Drive Calc 공식 2.3.1을 바탕으로 한 Global(다국어) 릴리스 **2.3.1-global.2**입니다. **이 버전부터 업데이트를 프로그램 안에서 받을 수 있습니다.**

2.3.1-global.1을 쓰고 있다면 **이 버전은 한 번 직접 설치해야 합니다.** 2.3.1-global.1에는 업데이트 기능이 없기 때문입니다. 이 버전을 설치한 뒤에는 새 Global 버전이 나오면 프로그램이 알려 주고 설치합니다.

#### 받을 파일

| 파일 | 설명 |
|---|---|
| `NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe` | 설치 프로그램. 프로그램 전체가 들어 있습니다. |
| `NTE_Drive_Calc_2.3.1-global.2_Multilingual_source.zip` | 이 빌드의 소스 코드(AGPL-3.0). 태그 `v2.3.1-global.2`의 커밋에도 같은 내용이 있습니다. |
| `NTE_Drive_Calc_2.3.1-global.2_release.json`, `NTE_Drive_Calc_2.3.1-global.2_release.json.sig` | 프로그램 안 업데이트가 확인하는 매니페스트와 그 서명입니다. 직접 받을 필요는 없습니다. |

이 버전부터 파일 이름에 Global 버전 전체(`2.3.1-global.2`)가 들어갑니다.

#### 설치

1. NTE Drive Calc가 켜져 있으면 종료합니다.
2. 설치 파일을 실행하고 UAC 창에서 "예"를 누릅니다. 코드 서명이 없어서 "Windows의 PC 보호" 창이 뜨면 "추가 정보" → "실행"을 누릅니다.
3. 설치 언어를 고르고 "다음"을 눌러 마칩니다.

- 공식 버전과 같은 위치(기본 `C:\Program Files\NTE Drive Calc`)에 설치됩니다. Global 2.3.1(2.3.1-global.1), 공식 2.3.1, 한국어 패치를 적용한 2.3.1, Global 2.3.0 위에 그대로 설치하면 되고, 처음 설치하는 경우에도 이 파일 하나면 됩니다.
- 계정·설정·드라이브·창고·전투 리포트·육성 기록·로그·저장한 사이클 등 사용자 데이터는 그대로 유지됩니다. 한국어 패치가 만든 백업 파일도 지우지 않습니다.
- 되돌리려면 공식 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.1.exe`)을 같은 위치에 다시 설치합니다. 공식 설치 프로그램은 [원본 프로젝트의 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)에서 받으세요.

자세한 안내는 [README](README.md)에 있습니다.

#### 2.3.1-global.1에서 달라진 점

##### 프로그램 안 업데이트 (Global 전용)

- 새 Global 버전이 나오면 프로그램이 버전과 업데이트 내용을 보여 주고 [지금 업데이트] [나중에] [이 버전 건너뛰기] 중에서 고르게 합니다.
- [지금 업데이트]를 누르면 설치 프로그램을 내려받아 확인합니다. 준비되면 [지금 설치하고 다시 시작]을 누르거나, 프로그램을 끌 때 설치를 고를 수 있습니다. 설치는 프로그램을 닫은 뒤 같은 폴더에 설치 마법사 없이(진행 창만 표시) 진행되고, [지금 설치하고 다시 시작]을 눌렀다면 끝난 뒤 프로그램이 다시 시작됩니다. 사용자 데이터는 그대로 남습니다.
- 확인 시점: 프로그램을 시작할 때 하루에 한 번까지, 그리고 설정 → "소프트웨어 업데이트" 카드의 [업데이트 확인]을 누를 때. 자동 확인은 같은 카드의 "시작할 때 자동으로 업데이트 확인 (하루 한 번)"을 끄면 멈춥니다.
- **업데이트는 이 저장소(LuinDe/NTE-Drive-Calc-Global)의 릴리스에서만 옵니다.** Global은 이제 원본과 별개로 개발·업데이트됩니다. 원본의 업데이트 기능(원본 릴리스·Mirror酱 확인, 공식 설치 파일 내려받기·열기, 업데이트 확인 창)은 이 빌드에서 뺐고, 원본 서버에 버전을 묻지 않으며, 프로그램 안 업데이트로 공식 빌드가 설치되는 일은 없습니다.
- 확인하는 것: 이 저장소의 정식 릴리스만(초안·사전 릴리스 제외), Global 버전 규칙(`v<주>.<부>.<수>-global.<n>`)으로 지금보다 새 버전, 정해진 파일 이름과 이 저장소의 다운로드 주소, GitHub가 알려 주는 SHA-256, 배포자의 릴리스 서명 키(Ed25519)로 서명된 매니페스트. 서명이 없거나 맞지 않는 릴리스는 알리지 않고, 내려받은 설치 프로그램은 크기와 SHA-256이 모두 맞을 때만 실행합니다.
- 릴리스 서명 키(공개키) 지문: `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`. 설정의 "소프트웨어 업데이트" 카드에도 같은 지문이 나옵니다.
- 설치 프로그램은 관리자 권한으로 조용히 실행됩니다(공식과 같은 Program Files 폴더에 설치하기 때문입니다).
- 버전 번호는 Global 고유의 번호입니다. "소프트웨어 업데이트" 카드에 Global 버전과, 참고용으로 바탕이 된 원본 버전(2.3.1)을 따로 보여 줍니다.
- 프로그램 안의 업데이트·다운로드·릴리스 링크는 이 저장소로 연결됩니다. 원본 GitHub·채팅 그룹(QQ/Discord)·후원 링크는 원작자 표기로 그대로 두었습니다.

##### 팀 시뮬레이션: 울티메이트 에너지·사이클 수치·쿨타임

- 24명 모두 타격마다 울티메이트 에너지와 에스퍼 사이클 수치를 게임 데이터대로 쌓고, 스킬 쿨타임을 적용합니다. 쿨타임은 게임 데이터와 커뮤니티 자료(prydwen.gg, GameWith)로 채웠고, 시계는 시간 정지를 뺀 전투 시간입니다. 값마다 출처와 신뢰도가 설명란에 나옵니다.
- 자료가 없는 캐릭터와 값은 예전 규칙(1·3바퀴 시작 때 사이클 수치 100)을 대신 쓰고, 설명란에 그렇게 표시합니다.
- **교체 규칙**: 팀에서 다음 스킬의 쿨타임이 **0.3초 이상** 남았거나 울티메이트 에너지가 모자라면 기다리지 않고 다음 캐릭터로 교체합니다. **0.3초 미만**이면 기다렸다가 사용합니다. 모든 팀원이 준비되지 않았으면 가장 빨리 준비되는 팀원을 기다립니다. 설명란에 교체·대기 내역이 나옵니다.
- 혼자 돌리는 아크 효율표·돌파 효율표는 교체할 팀원이 없으므로 쿨타임을 기다립니다.
- 직접 입력은 기본이 "입력대로"(경고만)이고, "엄격"을 고르면 같은 교체 규칙을 적용합니다.
- 결과: 검수된 팀 대부분은 결과가 같습니다. 쿨타임이 빠듯한 빠른 팀(예: 일로이가 들어간 팀)은 교체가 늘어 총피해가 줄 수 있습니다.

##### 돌파 자유 선택과 돌파 효율표

- 이환의 돌파는 순서와 관계없이 고를 수 있습니다(예: ③·⑤·①). 팀 시뮬레이션의 캐릭터 카드에서 돌파 효과 6개를 하나씩 켜고 끌 수 있고("돌파 n/6"), 공명은 고른 효과와 관계없이 돌파 3개·6개에서 켜집니다. 예전처럼 "돌파 N = 1~N번 효과"로 가정하지 않습니다. 예전에 저장한 팀과 사이클은 그대로 열립니다(돌파 수만 있으면 1~N번으로 읽습니다).
- 돌파 효과 192개 중 129개를 계산에 넣었습니다. 나머지는 "측정 필요"(34개, 0%로 보지 않음)와 "계산 불가"(29개: 회복·보호막·피격·다수 대상처럼 목각인형 피해와 관계없는 효과)로 따로 표시합니다. 시뮬레이션에서 조건을 재현할 수 없는 효과는 기대값으로 넣고 "기대값"으로 표시합니다.
- 아크 효율표 아래에 **"캐릭터 돌파 효율(Beta)"** 표를 추가했습니다(처음에는 접혀 있음). 돌파 효과를 하나만 더했을 때와 돌파 6개에서 하나만 뺐을 때의 DPS 변화(%), 공명3·공명6, 돌파 전체를 1바퀴·3바퀴로 보여 줍니다. 값은 미리 계산해 두었고, 데이터가 맞지 않으면 PC에서 다시 계산합니다.
- 라크리모사 ③은 남은 지속 피해를 한 번에 정산하고 그 층을 지우는 방식으로 계산합니다.

##### 아카네 린: 중국 정식 출시 데이터

- 계산기에 들어 있는 게임 데이터의 아카네 린 값은 출시 전 값입니다. 중국 서버 정식 출시(10-15) 뒤 서로 독립된 중국 자료 두 곳 이상에서 일치하는 값만 실행 중에 바꿔서 계산합니다(돌파 효과·공명·「반짝이는 별의 격정」·전용 아크 「달의 대척점」 등). 게임 데이터 파일 자체는 바꾸지 않습니다.
- 쿨타임과 울티메이트 에너지는 아직 확인되지 않았습니다. 팀 시뮬레이션 설명, 아크 효율표, 돌파 효율표에 이 사실을 표시합니다.
- 전투 리포트의 분석 컴포넌트(원본에 포함된 프로그램)는 출시 전 데이터로 계산합니다. 아카네 린이 있는 기록에는 안내가 한 줄 나옵니다.

##### 푸카 특훈

- 게임 1.4에서 생긴 계정 성장 "푸카 특훈"(Lv 0~20)을 계산에 넣습니다. 캐릭터 페이지의 가구 보너스 카드에 레벨을 입력하면(기본 0) 캐릭터 패널, 한계 이득, 팀 시뮬레이션, 새로 녹화하는 전투 리포트에 공격력·방어력·HP·치명 확률·치명 피해·사이클 강도·붕괴 강도가 더해집니다(Lv 20 합계 +28 / +30 / +420 / +2.5%p / +5%p / +12 / +12).
- 전투 리포트는 녹화를 시작할 때의 레벨을 기록에 고정합니다. 이 기능 전에 녹화한 기록은 Lv 0으로 계산하며 소급하지 않습니다(카드에 안내가 나옵니다).
- "특훈 전체 반영"(기본 켜짐): 수정 사본과 한계 이득 비교를 다시 계산할 때 특훈 전체를 넣습니다. 이때 "한계 이득 수동 조정" 줄이 보이고 정량화 상태가 "부분"으로 나올 수 있습니다. 끄면 공격력·치명 피해 몫만 반영됩니다.
- "푸카 특훈 만렙(20) 기준으로 보기": 아크 효율표와 졸업률의 졸업 템플릿을 Lv 0 / Lv 20 중에서 고릅니다(계정별로 기억, 기본은 Lv 0 = 이전과 같은 결과).

##### RTSS(RivaTuner) 호환성 안내

- 작성자 환경에서는 RTSS(RivaTuner Statistics Server, MSI Afterburner와 함께 설치됨)가 기본 후킹 방식으로 켜져 있으면 2.3.1의 게임 내 컴포넌트와 함께 게임이 시작하자마자 꺼졌습니다(D3D12 오류 `80004004 (E_ABORT)`).
- 이 빌드는 RTSS 설정을 읽기만 해서, 그럴 위험이 있으면 [네이티브 Loader 시작]을 누를 때 해결 방법(HTGame.exe 프로필에서 "Use Microsoft Detours API hooking" 켜기)을 안내하고, 환경 검사의 "검사 상세"에도 표시합니다. RTSS 설정은 바꾸지 않습니다.

##### 그 밖의 수정

- 일본어: 직접 입력 팔레트 툴팁의 스킬 이름(아카네 린 E 홀드 등 9줄)이 중국어로 나오던 것을 고쳤습니다. 치즈(小吱)의 일본어 이름을 「ちぃちゃん」으로 통일했습니다(영어 설명문은 "Chiz").
- 팀 시뮬레이션 카드의 캐릭터 선택칸에서 긴 이름(라크리모사 등)이 잘리던 것을 고쳤습니다. 그래도 안 들어가면 "…"로 줄이고 툴팁에 전체 이름을 보여 줍니다.

#### 알려진 한계

이번 버전에서 새로 생긴 것과 꼭 알아야 할 것을 적었습니다. 2.3.1-global.1부터 이어지는 한계(튜토리얼 이미지, 번역, 검색 등)는 아래 2.3.1-global.1 항목에 있습니다.

- **팀 시뮬레이션, 아크 효율표, 돌파 효율표는 Beta(미완성)입니다.** 딜 사이클 검수가 완벽하지 않아 결과가 실전과 다를 수 있습니다. 대략적인 비교 용도로만 쓰세요. 대상은 움직이지 않는 Lv80 허수아비(저항 20%)이고, 드라이브와 메인/서브 스탯은 공식 졸업 템플릿을 씁니다(내 창고의 장비가 아닙니다). 효율표는 캐릭터 혼자 계산하므로 팀원·서포트 스킬에 기대는 효과는 0으로 계산됩니다.
- 팀 시뮬레이션의 자원과 교체 규칙:
  - 쿨타임 일부는 커뮤니티 자료(prydwen.gg, 신뢰도 낮음 표시)입니다. 확인하지 못한 쿨타임(E: 하토르·잔홍·아카네 린·카오스·일로이·신쿠, Q: 잔홍·아카네 린·신쿠)은 검사하지 않습니다.
  - 울티메이트 에너지 비용은 호토리(전용 게이지)만 게임 데이터에 있어서, 다른 캐릭터는 에너지가 모자라도 울티메이트를 미루지 않습니다(설명란에 "미확인"으로 표시).
  - 혼자 돌리는 딜사이클 일부는 쿨타임 대기가 생겨 이전 버전과 결과가 다를 수 있습니다. 직접 입력은 기본값이 "경고만"이라 쿨타임이 남아 있어도 입력대로 계산합니다("엄격"을 고르면 교체 규칙을 적용합니다).
- 돌파:
  - 192개 효과 중 63개는 아직 계산하지 않습니다. 둘 다 0%로 보지 않고 표와 툴팁에 따로 표시합니다.
    - **측정 필요**(34개): 효과가 붙는 타격이나 자원(소환수의 공격, 캐릭터 고유 자원 등)이 아직 계산기의 타임라인에 없거나, 필요한 수치·발동 시점이 게임 데이터에도 설명문에도 없어서 게임에서 재 봐야 하는 효과입니다.
    - **계산 불가**(29개): 회복·보호막·이동처럼 피해와 관계없거나, 붕괴·처치·피격·여러 대상·적의 스킬이 있어야 발동해서, 움직이지 않는 허수아비 1명에게 주는 피해로는 나타나지 않는 효과입니다.
  - 시뮬레이션에서 조건을 재현할 수 없는 효과는 기대값으로 계산하고 "기대값"으로 표시합니다. 라크리모사 ③은 남은 지속 피해를 한 번에 정산하는 해석으로 계산합니다.
- 아카네 린(중국 출시 데이터):
  - 출시 뒤 서로 독립된 자료 두 곳 이상이 일치한 값만 바꿨습니다. 자료: 중국 공식 공지(yh.wanmei.com, 10-14·10-15·10-16), 중국 출시 클라이언트 화면(바하무트 forum.gamer.com.tw), TapTap 공략, 중국판 정보임을 밝힌 일본 공략(kamigame·AppMedia·GameWith), 아크 문구만 LDShop.
  - 확인되지 않아 게임 데이터(출시 전 값)를 그대로 쓰는 것: Lv80 기본 능력치, 스킬 배율, 평타 전달 기본값, 카덴차 연격 지속 시간, 자료가 한 곳뿐인 메커니즘 5개, 전용 아크 「달의 대척점」의 1재련 치명타 확률과 상(相) 속성 피해(자료끼리 16%와 15%·20%로 엇갈려 게임 데이터의 16% 유지), 2~5재련의 치명타 확률·평타·상 속성 값. 2~5재련의 스킬 피해 증가(+35~56%)는 1재련 값(+28%)에서 계산한 값입니다.
  - E·Q 쿨타임과 울티메이트 에너지는 자료가 없어 비워 두고 검사하지 않습니다. 졸업 템플릿, 추천 가중치, 한국어·영어·일본어 이름은 이 보정에 들어 있지 않습니다.
- **전투 리포트의 분석 컴포넌트는 바꾸지 않았습니다.** 녹화한 전투는 원본에 들어 있는 분석 컴포넌트(`nte-analysis-core`, 수정하지 않음)가 계산하므로, 팀 시뮬레이션의 자원·돌파 규칙과 아카네 린 보정은 전투 리포트에 적용되지 않습니다. 아카네 린이 있는 기록은 출시 전 데이터(9-24)로 계산되고 화면에 안내가 한 줄 나옵니다.

#### 확인 범위

- 실행 파일은 이 저장소의 `src/`로 다시 빌드해 SHA-256이 같은 것을 확인했고(두 번 빌드해 바이트 동일, 소스 zip만으로 다시 빌드해도 동일), 공식 실행 파일과의 차이가 `src.*` 모듈(원본 업데이트 모듈 2개 제거 포함)과 PE 체크섬뿐임을 `verify_exe_l10n_g231.py`로 확인했습니다.
- Global 전체 테스트 83개가 통과했고, 실행 파일을 네 언어로 띄워 화면과 계산 결과를 점검했습니다(ko 136/136 · en 116/116 · ja 116/116 · zh 116/116; 팀 시뮬레이션·효율표 수치는 소스 실행 결과와 같음).
- 프로그램 안 업데이트는 테스트용 빌드(이 버전에 테스트 훅만 더한 것)와 로컬 테스트 서버(GitHub 대역), 테스트 서명 키로 끝까지 확인했습니다: 알림·내려받기·검증·조용한 설치·재시작, 나중에/건너뛰기, 수동 확인, 오프라인·요청 제한, 해시·크기 불일치, 잘못된 파일 이름, 초안·사전 릴리스, 낮은 버전, 다운로드 취소, 설치 실패, 서명 없는/잘못된 릴리스, 수정된 릴리스 본문 등 13개 시나리오 384개 항목(네 언어). 원본 프로젝트로 가는 요청이 없는 것도 확인했습니다. 실제 GitHub 릴리스로 업데이트해 보는 것은 다음 버전부터 가능합니다(이 버전이 업데이트 기능이 있는 첫 버전입니다).
- 설치·업그레이드·제거는 테스트용 설치 프로그램(권한 없이 설치되는 변형)으로 자동 확인했습니다(배포용 실행 파일 9/9, 테스트용 실행 파일 11/11): 새 설치, 2.3.1-global.1 위 업그레이드(조용한 설치와 설치 마법사 모두), 공식 2.3.1·Global 2.3.0·한국어 패치 2.3.1 위 업그레이드, 같은 버전 재설치, 제거(사용자 데이터 유지). 배포용 설치 프로그램은 **관리자 권한으로 실제 설치해 보지 않았습니다.**
- 게임과 연동되는 기능은 이번에도 게임에 연결해 다시 검증하지 않았습니다. RTSS 안내는 작성자 PC의 실제 RTSS 설정을 읽어서만 확인했습니다.
- 설치 파일과 실행 파일에는 코드 서명이 없습니다(프로그램 안 업데이트는 별도의 릴리스 서명 키로 확인합니다).

#### SHA-256

```
8d6ea7de21b76e6a44eadb7f372f4551ce0c010a1a4df32eccfec0a2b99a209a  NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe  (184,851,232 bytes)
75cdf8f2d8c32cafc240c1abf9d0da1934fc7409f929d47055a61a46b6479ce1  NTE_Drive_Calc_2.3.1-global.2_Multilingual_source.zip  (7,497,484 bytes)
9355c146beb984e864de739998d85da6a24772838d6007ed866de534517509f3  설치되는 NTE_Drive_Calc.exe  (25,220,941 bytes)
5b8fa8d2b7580bacd494c0f71e76d7b05cf1bee4f9b94bb945993a2e1c69e8c3  (참고) 바탕이 된 공식 2.3.1 NTE_Drive_Calc.exe  (21,320,661 bytes)
```

설치 프로그램의 SHA-256은 릴리스 페이지의 파일 목록(GitHub가 보여 주는 sha256)과 서명된 매니페스트 `NTE_Drive_Calc_2.3.1-global.2_release.json`에도 있습니다.

```powershell
Get-FileHash .\NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe -Algorithm SHA256
```

#### 서명 확인하기 (선택)

프로그램 안 업데이트는 이 확인을 스스로 합니다. 설치 파일을 직접 받았을 때 손으로 확인하려면 Windows 10/11에 들어 있는 OpenSSH의 `ssh-keygen`을 씁니다.

1. 설치 파일, `NTE_Drive_Calc_2.3.1-global.2_release.json`, `NTE_Drive_Calc_2.3.1-global.2_release.json.sig`를 한 폴더에 받습니다.
2. 그 폴더에서 **명령 프롬프트**(cmd)를 열고 아래 두 줄을 실행합니다(PowerShell에서는 `<`를 쓸 수 없습니다). 첫 줄은 배포자의 공개키로 `allowed_signers` 파일을 만듭니다.

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.1-global.2_release.json.sig < NTE_Drive_Calc_2.3.1-global.2_release.json
```

3. `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`가 나오면 매니페스트가 배포자의 릴리스 키로 서명된 것입니다. `Could not verify signature`가 나오면 그 파일을 쓰지 말고 [Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)에 알려 주세요.
4. 매니페스트를 메모장으로 열어 `installer`의 `sha256`과 `size`가 받은 설치 파일과 같은지 확인합니다(`certutil -hashfile NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe SHA256`).

#### 라이선스

NTE Drive Calc는 GNU AGPL-3.0으로 배포되는 프로그램이고 이 빌드는 그 파생물입니다. 원저작권: NTE Drive Calc contributors ([hxwd94666](https://github.com/hxwd94666)). 수정: [LuinDe](https://github.com/LuinDe), 2026-10-19(2.3.1-global.2), 원본 커밋 `0e7a6b4`(공식 2.3.1의 소스) 기준. 대응 소스는 이 릴리스의 소스 zip과 태그 `v2.3.1-global.2`의 커밋에 있습니다([SOURCE_OFFER.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/SOURCE_OFFER.md)).

이 프로그램은 팬이 만든 비공식 도구이며 게임의 개발사·배급사와 관계가 없습니다.

### English

This is an **unofficial modified build of [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1** (original by hxwd94666 / NTE Drive Calc contributors, AGPL-3.0). Global release **2.3.1-global.2**, modified by LuinDe on 2026-10-19, based on original commit `0e7a6b4` (the source of the official 2.3.1). It is not published or supported by the original author; report problems in this repository's Issues, not upstream.

- **Users of 2.3.1-global.1 install this version once by hand** (.1 has no updater). From this version on, new Global versions arrive inside the program.
- **Install**: download `NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe` and run it (UAC "Yes"; the file is not code-signed, so on the SmartScreen window click "More info" → "Run anyway"). It contains the whole program, installs to the same location as the official version, can be installed over Global 2.3.1 (2.3.1-global.1), the official 2.3.1, a Korean-patched 2.3.1 or Global 2.3.0, and keeps your user data. To go back, run the official installer again (from the [original project's Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)). From this version the asset names carry the full Global version.
- **New: in-app updates (Global only).** The program checks **only the Releases of this repository** (LuinDe/NTE-Drive-Calc-Global) at most once a day at startup and with [Check for Updates] on the "Software Update" card in Settings (untick "Check for updates at startup (at most once a day)" there to turn the automatic check off). A new version is shown with its notes and [Update Now] / [Later] / [Skip This Version]; [Update Now] downloads the installer and verifies its size and SHA-256 against GitHub's digest and a manifest signed with the maintainer's Ed25519 release key (fingerprint `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`, also shown on the card); then [Install and Restart Now] (or installing when you quit) closes the program, runs the installer silently with administrator rights in the same folder (user data kept) and, with [Install and Restart Now], starts the program again. Drafts, prereleases, unsigned or tampered releases are never offered; versions are compared by Global's own grammar `v<major>.<minor>.<patch>-global.<n>`. Global is now developed independently of the original: the original's update check (its releases, Mirror酱), the official-installer download and the update dialog are removed, no version request goes to the original's servers, and no in-app path installs the official build. In-app update / download / release links lead to this repository; the original's GitHub, chat and support links stay as credit. The "Software Update" card shows the Global version and, for information, the original version it is based on (2.3.1).
- **New: Team Simulation resources.** For all 24 characters, ultimate energy and the Esper-Cycle gauge build up per hit from the game data, and skill cooldowns apply (game data plus community sources prydwen.gg / GameWith; the clock is combat time without time stops). Every value shows its source and confidence in the explanation panel; characters or values without data fall back to the old rule (gauge 100 at the start of loops 1 and 3) and say so. **Swap rule**: in a team, a skill whose cooldown still has **0.3 s or more** left, or an ultimate without enough energy, hands over to the next character; with less than 0.3 s left the character waits and uses it. Solo tables (Arc / Awakening Efficiency) wait, since there is nobody to swap to; Custom Input stays "as entered" (warnings only) unless you choose "Strict". Most reviewed teams give the same result; fast teams with tight cooldowns (e.g. with Oneiroi) may swap more and deal less total damage.
- **New: free awakening choice and the awakening efficiency table.** Awakening effects can be taken in any order (e.g. ③ ⑤ ①): the member cards of Team Simulation toggle each of the six effects ("Awakening n/6"), and the resonances turn on at 3 and 6 awakenings whatever the chosen effects. Saved teams and cycles open as before (a plain count means effects 1..N). 129 of the 192 effects are computed; the others are marked "Unmeasured" (34, never shown as 0 %) or "Not computable" (29: healing, shields, being hit, several targets …); effects whose condition the simulator cannot reproduce use an expected value and are marked "expected". A new **"Character Awakening Efficiency (Beta)"** table under the Arc Efficiency table (collapsed at first) shows the DPS change of adding one effect, removing one from all six, Resonance 3 / 6 and all six, for 1 and 3 loops (precomputed; recomputed on your PC when the data do not match). Lacrimosa ③ settles the remaining damage over time at once and removes that stack.
- **New: Akane Rin on CN release data.** The bundled game data holds pre-release values for Akane Rin. Values of the CN release (10-15) on which at least two independent Chinese sources agree replace them at run time (awakening effects, resonances, "Sparkling Star Fervor", her exclusive arc …); the data file itself is not changed. Cooldowns and ultimate energy are still unverified, and the pages say so. The battle report's analysis component (part of the original program) still uses the pre-release data; records with Akane Rin show a note.
- **New: Puka Boot Camp.** The account-wide progression of game version 1.4 (Lv 0–20, entered on the Furniture Bonus card of the character page) adds ATK, DEF, HP, CRIT Rate, CRIT DMG, cycle and break intensity to panels, marginal gains, Team Simulation and newly recorded battle reports (+28 / +30 / +420 / +2.5 pp / +5 pp / +12 / +12 at Lv 20). Reports freeze the level when recording starts; older reports count as Lv 0. "All Boot Camp stats" (on by default) includes the whole bonus in recomputed modified copies and marginal comparisons ("Manual Marginal Adjustment" rows, status may read "Partial"); "View at Puka Boot Camp max (Lv.20)" switches the graduation template of the Arc Efficiency table and the graduation rate.
- **New: RTSS (RivaTuner) compatibility notice.** On the author's PC, RTSS with its default hooking made the game crash at start together with the 2.3.1 in-game component (D3D12 `80004004 (E_ABORT)`). When the program sees that risk (it only reads the RTSS settings), [Start native Loader] explains the fix (turn on "Use Microsoft Detours API hooking" in an HTGame.exe profile), and "Detection Details" lists it.
- **Fixes**: Japanese skill names in the Custom Input palette tooltips (nine lines were Chinese), one Japanese name for Chiz (ちぃちゃん), and long names (e.g. Lacrimosa) no longer cut off in the team cards' character selector.
- **Known limits (new in this version)**: whoever holds the release-signing key could run a program with administrator rights on every PC that updates (the key is kept offline with a passphrase); if this repository's account were taken over, a fake release would not install but could stop the normal update notification; new official versions of the original are not announced. Team Simulation: some cooldowns come from community sources (marked low confidence); unconfirmed cooldowns (E: Hathor, Zankou, Akane Rin, Chaos, Oneiroi, Shinku; Q: Zankou, Akane Rin, Shinku) are not checked, and the ultimate energy cost is known only for Xun (her own gauge), so the other characters are never held back for energy; some solo rotations now wait for cooldowns and give other results than before. Awakening: 63 effects are not computed yet; Akane Rin's cooldowns and ultimate energy are unverified. Puka Boot Camp: the level table comes from public sources and two points are not verified in game (break-intensity total 12; whether ATK / DEF / HP are flat bonuses); marginal-gain breakdowns of reports with the training keep an offset of a few pp; older program versions show the new rows with a Chinese prefix. RTSS: no notice while RTSS is installed but not running; the fix was confirmed on one PC only. The known limits of 2.3.1-global.1 are listed under that release in [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md).
- **Also note**: Team Simulation, the Arc Efficiency table and the awakening efficiency table are unfinished Betas (a stationary Lv80 dummy, the official graduation templates; results may differ from real battles). Of the 192 awakening effects, 34 need in-game measurement (the hits or resources they act on are not on the calculator's time axis yet, or their values or timing are in neither the game data nor the descriptions) and 29 cannot be computed against one stationary dummy (no damage effect, or they need a break, a kill, being hit, several targets or an enemy skill); both are marked and never shown as 0 %. Akane Rin: values that only one source gives or on which the sources disagree keep the game data (Lv80 base stats, skill multipliers, basic-attack conduction base values, the Cadenza Combo duration, five single-source mechanics, the exclusive arc's R1 crit rate and Lakshana bonus and its R2–R5 values); her E / Q cooldowns and ultimate energy are unknown. Sources: the official CN notices, CN release-client screenshots (forum.gamer.com.tw), TapTap guides, Japanese guides of the Chinese version (kamigame, AppMedia, GameWith), LDShop for the arc text only. **The battle report's analysis component (`nte-analysis-core`, unchanged from the original) is not modified**: recorded battles are computed without the Team Simulation rules, and with Akane Rin's pre-release data.
- **What was checked**: the executable was rebuilt from `src/` with an identical SHA-256 (also from the source zip alone) and differs from the official one only in the `src.*` modules (including the removal of the original's two update modules) and the PE checksum. All 83 Global tests pass, and the executable was run in all four languages (ko 136/136 · en 116/116 · ja 116/116 · zh 116/116; Team Simulation and efficiency numbers equal a source run). The in-app updater was tested end to end with a test build (this version plus test hooks), a local GitHub stand-in and a test signing key (13 scenarios, 384 checks, four languages; no request to the original project); an update through the real GitHub becomes possible from the next version. Install, upgrade (over 2.3.1-global.1 silently and through the wizard, the official 2.3.1, Global 2.3.0 and a Korean-patched 2.3.1), reinstall and uninstall were tested with a test build of the installer that needs no administrator rights (release executable 9/9, test executable 11/11); the release installer was **not run with administrator rights**. Features that interact with the game were not re-verified against the game.

SHA-256: installer `8d6ea7de21b76e6a44eadb7f372f4551ce0c010a1a4df32eccfec0a2b99a209a` (184,851,232 bytes; also next to the file on the release page and in the signed manifest `NTE_Drive_Calc_2.3.1-global.2_release.json`); source zip `75cdf8f2d8c32cafc240c1abf9d0da1934fc7409f929d47055a61a46b6479ce1`, installed `NTE_Drive_Calc.exe` `9355c146beb984e864de739998d85da6a24772838d6007ed866de534517509f3`. Full guide: [README.en.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.en.md). Source: tag `v2.3.1-global.2`.

**Verify the signature (optional).** The in-app updater does this itself. To check a downloaded installer by hand with the OpenSSH `ssh-keygen` built into Windows 10/11, put the installer, `NTE_Drive_Calc_2.3.1-global.2_release.json` and `NTE_Drive_Calc_2.3.1-global.2_release.json.sig` in one folder, open **Command Prompt** (cmd) there (PowerShell has no `<` redirection) and run the two lines below; the first writes an `allowed_signers` file with the maintainer's public key. It must print `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`. If it prints `Could not verify signature`, do not use the files and report it in Issues. Then check that `installer.sha256` and `installer.size` in the manifest match the installer (`certutil -hashfile NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe SHA256`).

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.1-global.2_release.json.sig < NTE_Drive_Calc_2.3.1-global.2_release.json
```

### 日本語

このリリースは **[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 を改変した非公式ビルドです**（オリジナル：hxwd94666 / NTE Drive Calc contributors、AGPL-3.0）。Global リリース **2.3.1-global.2**、LuinDe が 2026-10-19 に改変（ベースはオリジナルのコミット `0e7a6b4`＝公式 2.3.1 のソース）。原作者が配布・サポートしているものではありません。問題はオリジナルではなく、このリポジトリの Issues に報告してください。

- **2.3.1-global.1 をお使いの場合、このバージョンは一度だけ手動でインストールしてください**（.1 には更新機能がありません）。このバージョンからは、新しい Global バージョンをプログラム内で受け取れます。
- **インストール**：`NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe` をダウンロードして実行します（UAC は「はい」。コード署名がないため SmartScreen が出たら「詳細情報」→「実行」）。プログラム全体が入っており、公式版と同じ場所にインストールされ、Global 2.3.1（2.3.1-global.1）・公式 2.3.1・韓国語パッチを適用した 2.3.1・Global 2.3.0 の上にそのままインストールでき、ユーザーデータは残ります。戻すときは公式インストーラー（[オリジナルのプロジェクトの Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) から入手）をもう一度実行します。このバージョンからファイル名に Global のバージョン全体が入ります。
- **新機能：プログラム内アップデート（Global 専用）**。確認先は **このリポジトリ（LuinDe/NTE-Drive-Calc-Global）の Releases だけ** で、起動時に 1 日 1 回まで、または「設定」→「ソフトウェア更新」カードの［更新確認］で確認します（自動確認は同じカードの「起動時に更新を自動確認する（1日1回まで）」で止められます）。新しいバージョンがあると、バージョンと更新内容に［今すぐ更新］［後で］［このバージョンをスキップ］が表示されます。［今すぐ更新］はインストーラーをダウンロードし、サイズと SHA-256 を GitHub のダイジェストとメンテナーの Ed25519 リリース鍵（フィンガープリント `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`、カードにも表示）で署名されたマニフェストで確認します。その後［今すぐインストールして再起動］（または終了時にインストール）を選ぶと、プログラムを閉じて同じフォルダーに管理者権限でサイレントインストールし（ユーザーデータは保持）、［今すぐインストールして再起動］の場合はプログラムを再起動します。下書き・プレリリース・署名のない／改ざんされたリリースは通知しません。バージョンは Global 独自の規則 `v<major>.<minor>.<patch>-global.<n>` で比較します。Global は今後オリジナルとは独立して開発・更新します。オリジナルの更新確認（オリジナルのリリース、Mirror酱）、公式インストーラーのダウンロード、更新ダイアログは削除し、オリジナルのサーバーにバージョンを問い合わせることも、プログラム内の更新で公式ビルドがインストールされることもありません。プログラム内の更新・ダウンロード・リリースのリンクはこのリポジトリにつながり、オリジナルの GitHub・チャット・支援のリンクはクレジットとしてそのまま残しています。「ソフトウェア更新」カードには Global のバージョンと、参考としてベースになったオリジナルのバージョン（2.3.1）を別々に表示します。
- **新機能：チームシミュレーションのリソース**。24 人全員について、ヒットごとのアルティメットエネルギーとエスパーサイクル値をゲームデータどおりに蓄積し、スキルのクールタイムを適用します（ゲームデータとコミュニティ資料 prydwen.gg・GameWith。時計は時間停止を除いた戦闘時間）。値ごとの出典と信頼度は説明欄に表示し、資料のないキャラ・値は従来の規則（1・3 周目の開始時にサイクル値 100）で代用してその旨を表示します。**交代規則**：チームでは、次のスキルのクールタイムが **0.3 秒以上** 残っているか、アルティメットのエネルギーが足りないときは待たずに次のキャラへ交代し、**0.3 秒未満** なら待ってから使います。単独の表（アーク効率・覚醒効率）は交代相手がいないので待ちます。直接入力は既定で「入力どおり」（警告のみ）で、「厳格」を選ぶと同じ規則になります。審査済みのチームの多くは結果が変わりませんが、クールタイムに余裕のない速いチーム（例：イロヒ入り）は交代が増えて総ダメージが下がることがあります。
- **新機能：覚醒の自由選択と覚醒効率表**。覚醒効果は順番に関係なく選べます（例：③⑤①）。チームシミュレーションのキャラカードで 6 つの効果をそれぞれオン／オフでき（「覚醒 n/6」）、共鳴は選んだ効果に関係なく覚醒 3・6 で有効になります。以前に保存したチームとサイクルはそのまま開けます（数だけの場合は効果 1〜N）。192 個の効果のうち 129 個を計算に入れ、残りは「要実測」（34 個、0% 扱いにはしない）と「計算不可」（29 個：回復・シールド・被弾・複数対象など）として表示します。シミュレーターで条件を再現できない効果は期待値で計算し「期待値」と表示します。アーク効率表の下に **「キャラクター覚醒効率 (Beta)」** 表を追加しました（最初は折りたたみ）。効果を 1 つだけ足したとき・6 つから 1 つだけ外したときの DPS 変化、共鳴 3・6、覚醒すべてを 1 周・3 周で表示します（事前計算済み、データが合わないときは PC で再計算）。ラクリモサ③は残りの継続ダメージを一度に精算してその層を消す形で計算します。
- **新機能：明音凛（アカネ・リン）の中国版リリースデータ**。同梱のゲームデータの明音凛はリリース前の値です。中国版リリース（10-15）後、互いに独立した中国の資料 2 つ以上で一致する値だけを実行時に置き換えて計算します（覚醒効果・共鳴・「煌星激昂」・専用アークなど）。データファイル自体は変更しません。クールタイムとアルティメットエネルギーは未確認で、各ページにそう表示します。戦闘レポートの解析コンポーネント（オリジナルに含まれるプログラム）はリリース前のデータのままで、明音凛を含む記録には注記が出ます。
- **新機能：プカ特訓**。ゲーム 1.4 のアカウント共通の育成（Lv 0〜20、キャラページの家具ボーナスカードで入力）を、パネル・限界値・チームシミュレーション・新しく記録する戦闘レポートの攻撃力・防御力・HP・会心率・会心ダメージ・サイクル強度・ブレイク強度に反映します（Lv 20 で +28 / +30 / +420 / +2.5pt / +5pt / +12 / +12）。戦闘レポートは記録開始時のレベルを固定し、以前のレポートは Lv 0 として扱います。「特訓をすべて反映」（既定オン）で変更コピーと限界値比較の再計算に特訓をすべて含めます（「限界値の手動調整」行が表示され、数値化状態が「一部」になることがあります）。「プカ特訓最大（Lv.20）基準で表示」でアーク効率表と完成度の卒業テンプレートを切り替えます。
- **新機能：RTSS（RivaTuner）互換性のお知らせ**。作者の環境では、既定のフック方式の RTSS と 2.3.1 のゲーム内コンポーネントの組み合わせで、ゲームが起動直後に落ちました（D3D12 `80004004 (E_ABORT)`）。そのおそれがあるとき（RTSS の設定は読み取るだけです）、［ネイティブ Loader を起動］で対処方法（HTGame.exe のプロファイルで「Use Microsoft Detours API hooking」をオン）を案内し、「検出詳細」にも表示します。
- **修正**：直接入力パレットのツールチップで中国語のままだったスキル名（9 行）を日本語にし、小吱の日本語名を「ちぃちゃん」に統一しました。チームカードのキャラ選択欄で長い名前（ラクリモサなど）が切れなくなりました。
- **既知の制限（このバージョンで新しいもの）**：リリース署名鍵を持つ人は、更新するすべての PC で管理者権限のプログラムを実行できることになります（鍵はオフラインでパスフレーズ付きで保管）。このリポジトリのアカウントが乗っ取られた場合、偽リリースはインストールされませんが、通常の更新通知が止まることがあります。オリジナルの新しい公式版は通知しません。チームシミュレーション：クールタイムの一部はコミュニティ資料（低信頼度と表示）で、確認できなかったクールタイム（E は 6 人、Q は 3 人）はチェックしません。アルティメットのエネルギーコストは潯（専用ゲージ）しか分からないため、ほかのキャラはエネルギー不足でアルティメットを遅らせません。単独のサイクルの一部はクールタイム待ちが生じ、以前と結果が変わります。覚醒：63 個の効果はまだ計算しません。明音凛のクールタイムとアルティメットエネルギーは未確認です。プカ特訓のレベル表は公開資料によるもので、2 点（ブレイク強度合計 12、攻撃力・防御力・HP が固定値か）はゲーム内で未確認です。特訓のあるレポートの限界値の内訳には数 pt のずれが残り、以前のバージョンのプログラムでは新しい行が中国語の接頭辞で表示されます。RTSS：インストールされていても実行中でなければ表示されず、対処方法は 1 台の PC でのみ確認しました。2.3.1-global.1 の既知の制限は [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md) のそのリリースの項目にあります。
- **その他の注意**：チームシミュレーション・アーク効率表・覚醒効率表は未完成の Beta です（動かない Lv80 のカカシ、公式卒業テンプレート前提。実戦と結果が異なる場合があります）。覚醒効果 192 個のうち 34 個は要実測（効果の対象となるヒットやリソースがまだ計算機のタイムラインにない、または必要な数値・タイミングがゲームデータにも説明文にもない）、29 個は計算不可（ダメージと無関係、またはブレイク・撃破・被弾・複数の対象・敵のスキルが必要で、動かないカカシ 1 体へのダメージには表れない）で、どちらも 0% 扱いにせず表示で区別します。明音凛：出典が 1 つだけの値や出典どうしが食い違う値はゲームデータのまま（Lv80 の基礎ステータス、スキル倍率、通常攻撃の伝導の基本値、華彩連撃の持続時間、出典が 1 つだけの仕様 5 つ、専用アークの精錬1の会心率と相属性ダメージ、精錬2〜5 の値）で、E・Q のクールタイムとアルティメットエネルギーは不明です。出典：中国の公式告知、中国版リリースクライアントの画面（forum.gamer.com.tw）、TapTap の攻略、中国版の情報と明記した日本の攻略（kamigame・AppMedia・GameWith）、アークの文面のみ LDShop。**戦闘レポートの解析コンポーネント（`nte-analysis-core`、オリジナルのまま）は変更していません**。記録した戦闘はチームシミュレーションの規則なしで、明音凛はリリース前のデータで計算されます。
- **確認した範囲**：実行ファイルは `src/` から再ビルドして SHA-256 が一致し（ソース zip だけからの再ビルドでも一致）、公式との違いが `src.*` モジュール（オリジナルの更新モジュール 2 つの削除を含む）と PE チェックサムだけであることを確認しました。Global の全テスト 83 件が通過し、実行ファイルを 4 言語で起動して画面と計算結果を点検しました（ko 136/136 · en 116/116 · ja 116/116 · zh 116/116。チームシミュレーションと効率表の数値はソース実行の結果と一致）。プログラム内アップデートはテスト用ビルド（このバージョンにテスト用フックだけを加えたもの）・ローカルの GitHub 代替サーバー・テスト用署名鍵で端から端まで確認しました（13 シナリオ、384 項目、4 言語。オリジナルへのリクエストなし）。実際の GitHub のリリースでの更新は次のバージョンから可能になります。インストール・アップグレード（2.3.1-global.1 の上にサイレントとウィザードの両方、公式 2.3.1、Global 2.3.0、韓国語パッチ適用 2.3.1 の上）・再インストール・アンインストールは、管理者権限なしで動くテスト用インストーラーで確認しました（配布用実行ファイル 9/9、テスト用実行ファイル 11/11）。配布用インストーラーは**管理者権限で実際にインストールしてはいません**。ゲームと連携する機能はゲームに接続して再検証していません。

SHA-256：インストーラー `8d6ea7de21b76e6a44eadb7f372f4551ce0c010a1a4df32eccfec0a2b99a209a`（184,851,232 バイト。リリースページのファイル横の sha256 と署名付きマニフェスト `NTE_Drive_Calc_2.3.1-global.2_release.json` にも記載）、ソース zip `75cdf8f2d8c32cafc240c1abf9d0da1934fc7409f929d47055a61a46b6479ce1`、インストールされる `NTE_Drive_Calc.exe` `9355c146beb984e864de739998d85da6a24772838d6007ed866de534517509f3`。詳しい案内：[README.ja.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.ja.md)。ソース：タグ `v2.3.1-global.2`。

**署名の確認（任意）**：プログラム内アップデートはこの確認を自動で行います。ダウンロードしたインストーラーを手動で確認するには、Windows 10/11 に入っている OpenSSH の `ssh-keygen` を使います。インストーラー・`NTE_Drive_Calc_2.3.1-global.2_release.json`・`NTE_Drive_Calc_2.3.1-global.2_release.json.sig` を同じフォルダーに置き、そこで **コマンドプロンプト**（cmd）を開いて（PowerShell では `<` が使えません）次の 2 行を実行します。1 行目はメンテナーの公開鍵で `allowed_signers` ファイルを作ります。`Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY` と表示されれば正しい署名です。`Could not verify signature` と表示されたらファイルを使わず、Issues に報告してください。続けて、マニフェストの `installer.sha256` と `installer.size` がインストーラーと一致することを確認します（`certutil -hashfile NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe SHA256`）。

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.1-global.2_release.json.sig < NTE_Drive_Calc_2.3.1-global.2_release.json
```

### 中文

这是**在 [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 基础上修改的非官方构建**（原版：hxwd94666 / NTE Drive Calc contributors，AGPL-3.0）。Global 发布 **2.3.1-global.2**，由 LuinDe 于 2026-10-19 修改（基于原版提交 `0e7a6b4`，即官方 2.3.1 的源代码）。它不是原作者发布或支持的版本；问题请反馈到本仓库的 Issues，不要反馈到原版仓库。

- **正在使用 2.3.1-global.1 的用户需要手动安装一次本版本**（.1 没有更新功能）。从本版本起，新的 Global 版本可以在程序内获取。
- **安装**：下载并运行 `NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe`（UAC 选“是”；文件没有代码签名，出现 SmartScreen 时点击“更多信息”→“仍要运行”）。安装包包含整个程序，安装位置与官方版本相同，可以直接装在 Global 2.3.1（2.3.1-global.1）、官方 2.3.1、打过韩语补丁的 2.3.1 或 Global 2.3.0 之上，用户数据会保留。要恢复官方版本，重新运行官方安装程序即可（从[原版项目的 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) 获取）。从本版本起，文件名包含完整的 Global 版本号。
- **新功能：程序内更新（仅 Global）**。只检查**本仓库（LuinDe/NTE-Drive-Calc-Global）的 Releases**：启动时每天至多一次，或在“设置”→“软件更新”卡片中点击［检查更新］（取消同一卡片上的“启动时自动检查更新（每天至多一次）”即可关闭自动检查）。发现新版本时显示版本号与更新说明，以及［立即更新］［稍后］［跳过此版本］。［立即更新］会下载安装程序，并用 GitHub 提供的摘要和由维护者 Ed25519 发布密钥（指纹 `SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY`，卡片上也会显示）签名的清单核对大小与 SHA-256；之后选择［立即安装并重启］（或在退出时安装），程序会关闭并以管理员权限在同一目录静默安装（保留用户数据），选择［立即安装并重启］时安装完成后重新启动程序。草稿、预发布、未签名或被篡改的发布不会提示；版本按 Global 自己的规则 `v<major>.<minor>.<patch>-global.<n>` 比较。Global 今后独立于原版开发和更新：原版的更新检查（原版发布、Mirror酱）、官方安装程序下载和更新对话框已删除，不会向原版服务器查询版本，程序内更新也不会安装官方构建。程序内的更新、下载和发布链接指向本仓库；原版的 GitHub、交流群和赞助链接作为对原作者的署名保留。“软件更新”卡片分别显示 Global 版本和作为参考的原版基础版本（2.3.1）。
- **新功能：队伍模拟的资源**。全部 24 名角色按游戏数据逐击累积终结能量和环合值，并应用技能冷却（游戏数据加社区资料 prydwen.gg、GameWith；计时为扣除时停的战斗时间）。每个数值的来源和可信度显示在说明栏；没有资料的角色或数值沿用旧规则（第 1、3 轮开始时环合值 100），并注明。**切换规则**：在队伍中，下一个技能的冷却还剩 **0.3 秒及以上**，或终结技能量不足时，不等待而直接切换到下一名角色；剩余 **不足 0.3 秒** 时等待后使用。单人表格（弧盘效率、觉醒效率）没有可切换的队友，因此等待。直接输入默认“按输入”（只提示），选择“严格”时使用同样的规则。多数已审核队伍结果不变；冷却紧张的快节奏队伍（例如带伊洛伊的队伍）切换会增加，总伤害可能下降。
- **新功能：自由选择觉醒与觉醒效率表**。觉醒效果可以不按顺序选择（例如 ③⑤①）：在队伍模拟的角色卡片上可以分别开关 6 个效果（“觉醒 n/6”），共鸣与所选效果无关，在觉醒 3 次、6 次时生效。以前保存的队伍和循环照常打开（只有次数时按效果 1–N 读取）。192 个效果中 129 个已计入计算；其余标为“需要实测”（34 个，不按 0% 处理）和“无法计算”（29 个：治疗、护盾、受击、多目标等）。模拟器无法再现条件的效果按期望值计算并标注“期望值”。在弧盘效率表下方新增 **“角色觉醒效率 (Beta)”** 表（初始为折叠）：显示只加一个效果、从全部 6 个中去掉一个时的 DPS 变化，以及共鸣 3、共鸣 6、全部觉醒，分 1 轮和 3 轮（预先计算，数据不符时在本机重新计算）。安魂曲③按一次性结算剩余持续伤害并移除该层计算。
- **新功能：明音凛按国服上线数据计算**。程序自带的游戏数据中，明音凛是上线前的数值。国服正式上线（10-15）后，只有至少两个相互独立的中文资料一致的数值才会在运行时替换计算（觉醒效果、共鸣、「烁星激昂」、专属弧盘等）；游戏数据文件本身不修改。冷却和终结能量尚未确认，相关页面会注明。战报的分析组件（原版自带的程序）仍使用上线前的数据，含明音凛的记录会显示一行提示。
- **新功能：噗卡特训**。游戏 1.4 的账号通用养成（Lv 0–20，在角色页的家具加成卡片中输入）会计入面板、边际收益、队伍模拟和新录制的战报中的攻击力、防御力、生命值、暴击率、暴击伤害、环合强度和倾陷强度（Lv 20 时 +28 / +30 / +420 / +2.5% / +5% / +12 / +12）。战报在开始录制时固定等级，之前的战报按 Lv 0 计算。「全部计入特训」（默认开启）使修改副本与边际对比的重算计入全部加成（会出现「边际手工调整」行，量化状态可能为「部分」）；「按噗卡特训满级（Lv.20）查看」切换弧盘效率表与毕业率所用的毕业模板。
- **新功能：RTSS（RivaTuner）兼容性提醒**。在作者的环境中，默认挂钩方式的 RTSS 与 2.3.1 的游戏内组件同时使用时，游戏一启动就会崩溃（D3D12 `80004004 (E_ABORT)`）。程序检测到这种风险时（只读取 RTSS 设置），点击［启动原生 Loader］会提示解决方法（在 HTGame.exe 的配置中开启“Use Microsoft Detours API hooking”），“检测详情”中也会列出。
- **修复**：日语版直接输入面板提示中仍为中文的技能名（9 行）已翻译，小吱的日语名统一为「ちぃちゃん」；队伍卡片的角色选择框中较长的名字（如安魂曲）不再被截断。
- **已知限制（本版本新增）**：持有发布签名密钥的人可以在所有执行更新的电脑上以管理员权限运行程序（密钥离线保存并有密码保护）；如果本仓库的账号被盗，伪造的发布不会被安装，但可能使正常的更新提示停止；不提示原版的新官方版本。队伍模拟：部分冷却来自社区资料（标为低可信度），未能确认的冷却（变轨技能：哈索尔、残虹、明音凛、卡厄斯、伊洛伊、真红；终结技：残虹、明音凛、真红）不做检查；终结技能量消耗只有浔（专属计量）有数据，其他角色不会因能量不足而推迟终结技；部分单人循环会因等待冷却而与以前结果不同。觉醒：63 个效果尚未计算；明音凛的冷却和终结能量未确认。噗卡特训的等级表来自公开资料，有两点未在游戏内确认（倾陷强度合计 12；攻击力、防御力、生命值是否为固定值）；带特训的战报在边际收益分解中仍有几个百分点的偏差；旧版本程序打开新战报时，新增的行以中文前缀显示。RTSS：已安装但未运行时不会提示，解决方法只在一台电脑上确认过。2.3.1-global.1 的已知限制见 [RELEASE_NOTES.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/RELEASE_NOTES.md) 中该版本的条目。
- **其他注意事项**：队伍模拟、弧盘效率表和觉醒效率表是尚未完成的 Beta（以原地不动的 80 级木桩和官方毕业模板为前提，结果可能与实战不同）。192 个觉醒效果中，34 个需要实测（效果作用的命中或资源尚未出现在计算器的时间轴上，或所需数值、时机在游戏数据和说明文中都没有），29 个无法计算（与伤害无关，或需要倾陷、击杀、受击、多个目标或敌方技能，对单个不动木桩的伤害体现不出来）；两者都单独标注，不按 0% 处理。明音凛：只有一个来源或来源之间不一致的数值保持游戏数据（80 级基础属性、技能倍率、普攻传导基础值、华彩连段持续时间、只有一个来源的 5 项机制、专属弧盘精炼 1 的暴击率与相属性伤害、精炼 2–5 的数值），E、Q 冷却和终结能量未知。来源：国服官方公告、国服上线客户端截图（forum.gamer.com.tw）、TapTap 攻略、注明为国服信息的日本攻略（kamigame、AppMedia、GameWith），弧盘文本另参考 LDShop。**战报的分析组件（`nte-analysis-core`，与原版相同）没有修改**：录制的战斗不应用队伍模拟的规则，明音凛按上线前的数据计算。
- **验证范围**：可执行文件已用 `src/` 重新构建，SHA-256 完全一致（只用源代码 zip 重新构建也一致），并确认与官方可执行文件的差异仅限于 `src.*` 模块（包括删除原版的 2 个更新模块）和 PE 校验和。Global 全部 83 项测试通过，并以四种语言启动可执行文件检查了界面和计算结果（ko 136/136 · en 116/116 · ja 116/116 · zh 116/116；队伍模拟与效率表的数值与源代码运行结果一致）。程序内更新已用测试构建（本版本仅加入测试挂钩）、本地 GitHub 替身服务器和测试签名密钥做了端到端验证（13 个场景、384 项检查、四种语言；没有向原版项目发出请求）；通过真实 GitHub 发布进行更新要从下一个版本开始才能实现。安装、升级（在 2.3.1-global.1 之上的静默安装和安装向导、官方 2.3.1、Global 2.3.0、打过韩语补丁的 2.3.1 之上）、重新安装和卸载已用无需管理员权限的测试版安装程序验证（发布用可执行文件 9/9，测试用可执行文件 11/11）；发布用安装程序**没有以管理员权限实际安装**。与游戏交互的功能没有连接游戏重新验证。

SHA-256：安装程序 `8d6ea7de21b76e6a44eadb7f372f4551ce0c010a1a4df32eccfec0a2b99a209a`（184,851,232 字节；也可见发布页文件旁的 sha256 和签名清单 `NTE_Drive_Calc_2.3.1-global.2_release.json`），源代码 zip `75cdf8f2d8c32cafc240c1abf9d0da1934fc7409f929d47055a61a46b6479ce1`，安装后的 `NTE_Drive_Calc.exe` `9355c146beb984e864de739998d85da6a24772838d6007ed866de534517509f3`。完整说明：[README.zh.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.zh.md)。源代码：标签 `v2.3.1-global.2`。

**验证签名（可选）**：程序内更新会自动完成这项检查。要手动检查下载的安装程序，可以使用 Windows 10/11 自带的 OpenSSH `ssh-keygen`：把安装程序、`NTE_Drive_Calc_2.3.1-global.2_release.json` 和 `NTE_Drive_Calc_2.3.1-global.2_release.json.sig` 放在同一文件夹，在该文件夹打开**命令提示符**（cmd；PowerShell 不支持 `<` 重定向），运行下面两行；第一行用维护者的公钥生成 `allowed_signers` 文件。显示 `Good "nte-drive-calc-global-release" signature for nte-global-release with ED25519 key SHA256:/fAeeg67muvrTrfFKosRIJGZd58nxmO9hX/q82d05XY` 即签名正确；如果显示 `Could not verify signature`，请不要使用这些文件，并在 Issues 中反馈。然后核对清单中的 `installer.sha256` 和 `installer.size` 是否与安装程序一致（`certutil -hashfile NTE_Drive_Calc_2.3.1-global.2_Multilingual_Setup.exe SHA256`）。

```bat
echo nte-global-release namespaces="nte-drive-calc-global-release" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN> allowed_signers
ssh-keygen -Y verify -f allowed_signers -I nte-global-release -n nte-drive-calc-global-release -s NTE_Drive_Calc_2.3.1-global.2_release.json.sig < NTE_Drive_Calc_2.3.1-global.2_release.json
```

---

## 2.3.1-global.1 (2026-10-11)

### 한국어

NTE Drive Calc 공식 2.3.1을 바탕으로 한 Global(다국어) 릴리스입니다. 새 기능 **아크 효율표(Beta)** 가 들어 있습니다.

#### 받을 파일

| 파일 | 설명 |
|---|---|
| `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` | 설치 프로그램. 프로그램 전체가 들어 있습니다. |
| `NTE_Drive_Calc_2.3.1_Multilingual_source.zip` | 이 빌드의 소스 코드(AGPL-3.0). 이 저장소의 같은 커밋에도 같은 내용이 있습니다. |

#### 설치

1. NTE Drive Calc가 켜져 있으면 종료합니다.
2. 설치 파일을 실행하고 UAC 창에서 "예"를 누릅니다. 코드 서명이 없어서 "Windows의 PC 보호" 창이 뜨면 "추가 정보" → "실행"을 누릅니다.
3. 설치 언어를 고르고 "다음"을 눌러 마칩니다.

- 공식 버전과 같은 위치(기본 `C:\Program Files\NTE Drive Calc`)에 설치됩니다. 공식 2.3.1, 한국어 패치를 적용한 2.3.1, 이전 다국어판(Global 2.3.0) 위에 그대로 설치하면 되고, 처음 설치하는 경우에도 이 파일 하나면 됩니다.
- 계정·설정·드라이브·창고·전투 리포트·육성 기록·로그·저장한 사이클 등 사용자 데이터는 그대로 유지됩니다. 한국어 패치가 만든 백업 파일도 지우지 않습니다.
- 되돌리려면 공식 설치 프로그램(`NTE_Drive_Calc_Setup_2.3.1.exe`)을 같은 위치에 다시 설치합니다. 공식 설치 프로그램은 [원본 프로젝트의 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)에서 받으세요.

자세한 안내는 [README](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.md)에 있습니다.

#### 2.3.0에서 달라진 점

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

#### 알려진 한계

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

#### SHA-256

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

#### 라이선스

NTE Drive Calc는 GNU AGPL-3.0으로 배포되는 프로그램이고 이 빌드는 그 파생물입니다. 원저작권: NTE Drive Calc contributors ([hxwd94666](https://github.com/hxwd94666)). 수정: [LuinDe](https://github.com/LuinDe), 2026-10-11, 원본 커밋 `0e7a6b4`(공식 2.3.1의 소스. 원본의 `2.3.1` 태그는 그보다 앞선 커밋을 가리킵니다) 기준. 대응 소스는 이 릴리스의 소스 zip과 같은 커밋의 저장소에 있습니다([SOURCE_OFFER.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/SOURCE_OFFER.md)).

이 프로그램은 팬이 만든 비공식 도구이며 게임의 개발사·배급사와 관계가 없습니다.


### English

**Unofficial modified build of [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1** (original by hxwd94666 / NTE Drive Calc contributors, AGPL-3.0). Modified by LuinDe on 2026-10-11, based on original commit `0e7a6b4` (the source of the official 2.3.1). It is not published or supported by the original author; report problems in this repository's Issues, not upstream.

- **Install**: download `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` and run it (UAC "Yes"; the file is unsigned, so on the SmartScreen window click "More info" → "Run anyway"). It contains the whole program, installs to the same location as the official version, can be installed over the official 2.3.1, a Korean-patched 2.3.1 or Global 2.3.0, and keeps your user data. To go back, run the official installer again (from the [original project's Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases)).
- **New in this release**: based on the official 2.3.1 (cultivation history and the other 2.3.1 features included); a new **Arc Efficiency Table (Beta)** that compares the arcs each of the 11 characters with an exclusive arc can equip, by solo-rotation damage (exclusive arc R1 = 100 %, R1 and max-refinement columns, 3 loops by default or 1, other characters' exclusive arcs marked † and hideable, "Open in Team Simulation"); **Team Simulation arc corrections** shared with that table (the chosen arc now reaches the stats, always-on arc bonuses counted once, the conditional effects of "Crime and Punishment" and "Antipode of the Moon" modelled from their description and game data as a "Global supplement rule"), **so the same team gives different numbers than in 2.3.0**; game-folder protection rebuilt for the 2.3.1 layout (`d3d12.dll`, `plugins\NTE_Plugin*.dll`, `NTE_Capture.dll`, `dwmapi.dll` that are not this program's files, for example ReShade or UE4SS, are never overwritten or deleted); about 700 new strings translated, plus 288 older game descriptions in English and Japanese; the 2.3.1 cultivation history saves and opens in every language; `&` in English buttons fixed.
- **Known limits**: Team Simulation and the Arc Efficiency table are unfinished Betas; results may differ from real battles. Both assume a stationary Lv80 dummy and the official graduation templates. The Arc Efficiency table lists **only characters with an exclusive arc** and is a **solo** calculation: arc effects that depend on support skills, teammates, team makeup, cycle or break intensity count as 0, effects that need hits taken, a break or a boss never trigger, some refinement effects do not show (`=R`, for example at the crit-rate cap), and † arcs follow the calculator's same-type rule and were not verified in game. The tutorial images are Korean in every language; after a live language switch a few texts stay in the previous language until the page is reopened; about 310 older sentences of the battle-report analysis component may stay Chinese; search accepts Chinese, pinyin and Korean only; the game language must be Simplified Chinese for scanning and appraisal. In-app GitHub, chat, support, download and update links lead to the original author's pages; do not report problems of this build there.
- **What was checked**: the executable was rebuilt from `src/` with an identical SHA-256 and differs from the official one only in the `src.*` modules and the PE checksum; an automated check of the release executable in all four languages (Offline mode, empty account, 177 checks) passed; install, upgrade (over official 2.3.1, Global 2.3.0 and Korean-patched 2.3.1), reinstall and uninstall were tested with a test build of the installer that needs no administrator rights. The release installer was compared with the official one but **not run with administrator rights**. Features that interact with the game keep the original's logic (apart from the game-folder protection and string handling) and were not re-verified against the game.

SHA-256: installer `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`, source zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`, installed `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`. Full guide: [README.en.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.en.md).

### 日本語

**[NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 を改変した非公式ビルドです**（オリジナル：hxwd94666 / NTE Drive Calc contributors、AGPL-3.0）。LuinDe が 2026-10-11 に改変（ベースはオリジナルのコミット `0e7a6b4`＝公式 2.3.1 のソース）。原作者が配布・サポートしているものではありません。問題はオリジナルではなく、このリポジトリの Issues に報告してください。

- **インストール**：`NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe` をダウンロードして実行します（UAC は「はい」。署名がないため SmartScreen が出たら「詳細情報」→「実行」）。プログラム全体が入っており、公式版と同じ場所にインストールされ、公式 2.3.1・韓国語パッチを適用した 2.3.1・Global 2.3.0 の上にそのままインストールでき、ユーザーデータは残ります。戻すときは公式インストーラー（[オリジナルのプロジェクトの Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) から入手）をもう一度実行します。
- **このリリースの変更点**：公式 2.3.1 ベース（育成記録など 2.3.1 の機能を含む）。新機能 **アーク効率表 (Beta)**：専用アークを持つ 11 キャラクターについて、装備できるアークを単独ローテーションのダメージで比較（専用アーク精錬1 = 100%、精錬1 と最大精錬の 2 列、既定 3 周／1 周、他キャラの専用アークは † 付きで非表示にも可能、「チームシミュレーションで開く」）。同じ計算を使う**チームシミュレーションのアーク補正**（選んだアークがステータスに反映、常時効果の二重計算を補正、「罪と罰」「月の対蹠点」の条件効果を説明文とゲームデータから「Global補完ルール」として計算）により、**同じチームでも数値が 2.3.0 と異なります**。2.3.1 の構成に合わせたゲームフォルダー保護（このプログラムのファイルでない `d3d12.dll`・`plugins\NTE_Plugin*.dll`・`NTE_Capture.dll`・`dwmapi.dll`、例えば ReShade や UE4SS は上書きも削除もしない）。2.3.1 の新しい文字列 約 700 件と古いゲーム説明文 288 件を翻訳。2.3.1 の育成記録がどの言語でも保存・表示できるように修正。英語ボタンの `&` を修正。
- **既知の制限**：チームシミュレーションとアーク効率表は未完成の Beta で、結果が実戦と異なる場合があります。どちらも動かない Lv80 のカカシと公式卒業テンプレートが前提です。アーク効率表は**専用アークを持つキャラクターだけ**を扱う**単独**計算で、支援スキル・仲間・編成・サイクル強度・ブレイク強度に依存するアーク効果は 0、被弾・ブレイク・ボスが条件の効果は発動せず、一部の精錬効果は反映されません（`=R`。例：会心率が上限のとき）。† のアークは計算機の同タイプ規則によるもので、ゲーム内では未検証です。チュートリアル画像はどの言語でも韓国語です。実行中に言語を切り替えると、一部の文字がページを開き直すまで前の言語のまま残ります。戦闘レポートの分析コンポーネントが返す古い文章 約 310 件は中国語のまま表示されることがあります。検索は中国語・ピンイン・ハングルのみ対応です。スキャン・鑑定にはゲームの言語が簡体字中国語である必要があります。プログラム内の GitHub・チャット・支援・ダウンロード・アップデートのリンクはオリジナルのままで、原作者のページにつながります。このビルドで起きた問題はそちらに書き込まないでください。
- **確認した範囲**：実行ファイルは `src/` から再ビルドして SHA-256 が一致し、公式との違いが `src.*` モジュールと PE チェックサムだけであることを確認しました。配布用の実行ファイルで 4 言語それぞれ自動チェック（オフラインモード、空のアカウント、177 項目）を行い、すべて通過しました。インストール・アップグレード（公式 2.3.1、Global 2.3.0、韓国語パッチ適用 2.3.1 の上）・再インストール・アンインストールは、管理者権限なしで動くテスト用インストーラーで確認しました。配布用インストーラーは公式のものと構成を照合しましたが、**管理者権限で実際にインストールしてはいません**。ゲームと連携する機能はオリジナルのロジックのままで（ゲームフォルダー保護と文字列処理を除く）、ゲームに接続して再検証してはいません。

SHA-256：インストーラー `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`、ソース zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`、インストールされる `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`。詳しい案内：[README.ja.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.ja.md)

### 中文

**这是在 [NTE Drive Calc](https://github.com/hxwd94666/NTE-Drive-Calculator) 2.3.1 基础上修改的非官方构建**（原版：hxwd94666 / NTE Drive Calc contributors，AGPL-3.0）。由 LuinDe 于 2026-10-11 修改（基于原版提交 `0e7a6b4`，即官方 2.3.1 的源代码）。它不是原作者发布或支持的版本；问题请反馈到本仓库的 Issues，不要反馈到原版仓库。

- **安装**：下载并运行 `NTE_Drive_Calc_2.3.1_Multilingual_Setup.exe`（UAC 选“是”；文件没有签名，出现 SmartScreen 时点击“更多信息”→“仍要运行”）。安装包包含整个程序，安装位置与官方版本相同，可以直接装在官方 2.3.1、打过韩语补丁的 2.3.1 或 Global 2.3.0 之上，用户数据会保留。要恢复官方版本，重新运行官方安装程序即可（从[原版项目的 Releases](https://github.com/hxwd94666/NTE-Drive-Calculator/releases) 获取）。
- **本版本的变化**：基于官方 2.3.1（包含养成记录等 2.3.1 功能）；新功能 **弧盘效率表 (Beta)**：对拥有专属弧盘的 11 名角色，用单人循环伤害比较其可装备的弧盘（专属弧盘精炼 1 = 100%，精炼 1 与满精炼两列，默认 3 轮、可切换 1 轮，其他角色的专属弧盘标 † 并可隐藏，“在队伍模拟中打开”）；与之共用计算的**队伍模拟弧盘修正**（所选弧盘反映到面板、常驻效果只计算一次、「罪与罚」「月的对跖点」的条件效果按说明文和游戏数据以“Global 补充规则”计算），因此**同一支队伍的数值会与 2.3.0 不同**；按 2.3.1 结构重新实现游戏目录保护（不是本程序文件的 `d3d12.dll`、`plugins\NTE_Plugin*.dll`、`NTE_Capture.dll`、`dwmapi.dll`，例如 ReShade、UE4SS，不会被覆盖或删除）；翻译了 2.3.1 新增的约 700 条文本，并为英语和日语补译了 288 条较早的游戏说明文；修复 2.3.1 养成记录在各语言下的保存与打开；修复英语按钮中的 `&`。
- **已知限制**：队伍模拟和弧盘效率表都是尚未完成的 Beta，结果可能与实战不同。两者都以原地不动的 80 级木桩和官方毕业模板为前提。弧盘效率表**只包含拥有专属弧盘的角色**，并且是**单人**计算：依赖援护技、队友、队伍构成、环合强度或倾陷强度的弧盘效果按 0 计算，以受击、倾陷或首领为条件的效果不会触发，部分精炼效果无法体现（`=R`，例如暴击率已达上限时），标 † 的弧盘按计算器的同类型规则列出，未在游戏内实测。教程图片在任何语言下都是韩语；运行中切换语言后，少数文字在重新打开页面前仍显示为之前的语言；战报分析组件返回的约 310 条较早的句子可能仍显示为中文；搜索只支持中文、拼音和韩文；与原版一样，扫描和鉴定需要游戏语言为简体中文。程序内的 GitHub、交流群、赞助、下载和更新链接与原版相同，会打开原作者的页面；本构建出现的问题请不要反馈到那里。
- **验证范围**：可执行文件已用 `src/` 重新构建，SHA-256 完全一致，并确认与官方可执行文件的差异仅限于 `src.*` 模块和 PE 校验和；用发布的可执行文件在四种语言下分别进行了自动检查（离线模式、空账号、177 项），全部通过；安装、升级（官方 2.3.1、Global 2.3.0、打过韩语补丁的 2.3.1 之上）、重新安装和卸载已用无需管理员权限的测试版安装程序验证。发布用安装程序已与官方安装程序对照结构，但**没有以管理员权限实际安装**。与游戏交互的功能除游戏目录保护和文本处理外沿用原版逻辑，没有连接游戏重新验证。

SHA-256：安装程序 `7f9289f220b30c9646366d1d7d5d94766649d941f5d0e608e4a879f1fd557812`，源代码 zip `1f2938331a2c1a6386ca017d60324191ff60dbd8d93bd695266e41ec52641dff`，安装后的 `NTE_Drive_Calc.exe` `76b7d0112d548517a39b05239970086f45408662e675afbc6c0283d2616dd8d0`。完整说明：[README.zh.md](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/main/README.zh.md)
