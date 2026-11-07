# NTE Drive Calc Global

[한국어](README.md) · [简体中文](README.zh.md) · [English](README.en.md) · [日本語](README.ja.md)

**NTE Drive Calc를 바탕으로 LuinDe가 유지보수하는 비공식 다국어 파생 프로젝트입니다.** 한국어 패치에서 출발해 번역과 계산 보조 기능을 확장했습니다. 원작자가 배포하거나 지원하는 공식 Global 버전이 아닙니다.

## 원작자와 원본 프로젝트

- 원작자: **[WuDu / hxwd94666](https://github.com/hxwd94666) 및 NTE Drive Calc contributors**
- 원본 소스: **[NTE-Drive-Calculator](https://github.com/hxwd94666/NTE-Drive-Calculator)**
- 원본 배포 페이지: **[NTE-Drive-Calc](https://github.com/hxwd94666/NTE-Drive-Calc)**
- Global 유지보수: [LuinDe](https://github.com/LuinDe) · Global 관련 문의: [이 저장소의 Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)

원본 주소는 출처를 밝히기 위해 유지합니다. 2026-11-07 확인 당시 원본 저장소에 접근할 수 없었으며, 그 사유는 확인하지 못했습니다. Global은 원작자의 공식 승인·지원·공동 제작을 표방하지 않습니다.

## 현재 배포: 2.3.6

**[v2.3.6 다운로드와 릴리스 안내](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.6)**

Windows 10/11 x64용입니다. 설치 파일은 `NTE_Drive_Calc_2.3.6_Multilingual_Setup.exe`, 공개 소스 묶음은 `NTE_Drive_Calc_2.3.6_Multilingual_source.zip`입니다. 현재 릴리스는 2.3.6만 제공합니다. 이전 릴리스와 버전 태그는 정리했으며, 소스 변경 이력은 보존합니다.

- 엘림(1090)의 중국 본서버 1.5.4 데이터·도감·장비 배치와 Core 가방 매핑을 반영했습니다.
- 2.3.6은 엘림 전신 이미지 형식으로 인한 시작 오류를 수정한 버전입니다.
- 엘림의 실측 DPS 사이클은 아직 준비되지 않아 팀 시뮬레이션과 사이클 기반 효율표에서 제외됩니다. 실제 글로벌 게임 접속 중 가방 동기화 검증은 완료되지 않았습니다.

2026-11-07 소스·문서 보완에서는 **기존 2.3.6 설치 파일을 변경하지 않았습니다.** 누락된 공개 원본 파일 121개를 복원하고 소스 ZIP, 라이선스 안내 및 릴리스 설명을 정정했습니다. 기존 설치 파일 안의 “전체 대응 소스가 ZIP에 포함된다”는 문구는 정확하지 않으므로 [정정 안내](docs/SOURCE_OFFER_CORRECTION_2.3.6.md)를 함께 확인하세요.

## 주요 기능

- 한국어·简体中文·English·日本語 UI 및 프로그램 안 언어 전환
- 원본의 인벤토리 동기화, 장비 감정·배분, 캐릭터 관리와 전투 리포트
- 팀 시뮬레이션(Beta), 직접 입력하는 딜 사이클, 아크·돌파 효율표
- 푸카 특훈 반영, 전투 리포트의 내 캐릭터 비교, Global 전용 서명 검증 업데이트

계산 결과는 구현된 모델과 데이터 범위에 따른 참고값입니다. 모든 캐릭터의 모든 효과와 실전 상황을 재현하지는 않습니다. 자세한 엘림 적용 범위와 자료 출처는 [엘림 안내](build_tools/ELYMS.md)를 보세요.

## 설치와 사용

1. 계산기를 종료하고 기존 계정·설정 데이터를 백업합니다.
2. [v2.3.6](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.6)의 설치 파일을 내려받아 실행합니다. 기존 설치 위치를 쓰며 사용자 데이터를 유지하도록 구성되어 있습니다.
3. 왼쪽 아래 언어 버튼으로 표시 언어를 선택합니다. [상세 사용법](docs/USAGE.ko.md)에서 팀 시뮬레이션과 효율표 사용 방법을 확인할 수 있습니다.

이전 서명 키를 사용하는 2.3.2 이하 설치본은 2.3.6을 한 번 수동 설치해야 합니다. 이후 업데이트는 이 Global 저장소에서만 확인합니다. 게임 연결 기능의 호환성은 게임 빌드와 네이티브 구성 요소에 따라 달라집니다.

## 소스와 라이선스 상태

애플리케이션은 원본의 [GNU AGPL-3.0](LICENSE)을 따릅니다. [NOTICE](NOTICE)에 원본 저작권과 Global 변경 고지를 보존했습니다. 함께 배포되는 구성 요소에는 별도 라이선스가 적용됩니다.

- 공개 범위: 수정한 `src/`, 진입점·의존성 잠금 파일·원본 빌드 도구, Global 빌드 도구, 공개 네이티브 프로토타입, 변경 자료 및 라이선스 기록.
- **미해결:** 배포된 Core·analysis Core·Loader(AGPL)와 캡처 DLL 5개(GPL)의 정확한 전체 대응 소스는 이 저장소와 ZIP에 확보되어 있지 않습니다. 공개 `native/` 프로토타입과 엘림 리소스 수정 스크립트는 그 대체물이 아닙니다.
- 게임 이미지·데이터의 권리는 각 권리자에게 있습니다. 이번 보완으로 모든 재배포 조건이 충족되었다고 주장하지 않습니다.

[소스 제공 범위와 남은 항목](SOURCE_OFFER.md) · [빌드 안내](build_tools/README.md) · [복원 파일·해시](UPSTREAM_SOURCE_FILES.json) · [과거 소스 이력](docs/source-history.md)
