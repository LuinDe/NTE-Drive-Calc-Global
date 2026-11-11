# 소스 제공 범위 / 源码范围 / Source coverage / ソースの範囲

NTE Drive Calc Global **2.3.7** · 소스 범위는 2026-11-07 보완 이후 같음 / source coverage unchanged since the 2026-11-07 supplement

- Original author: **[hxwd94666](https://github.com/hxwd94666) and NTE Drive Calc contributors**
- Original project: https://github.com/hxwd94666/NTE-Drive-Calculator
- Original releases: https://github.com/hxwd94666/NTE-Drive-Calc
- Global maintainer / repository: LuinDe — https://github.com/LuinDe/NTE-Drive-Calc-Global
- Public upstream baseline: `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` (Calc 2.3.1)
- Retained v2.3.6 application commit: [`5d3522a37bd35ef094721cf17b91f36ed9c6cb94`](https://github.com/LuinDe/NTE-Drive-Calc-Global/tree/5d3522a37bd35ef094721cf17b91f36ed9c6cb94)
- Current source package: [v2.3.7 release](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.7) (Korean-server Elyms texts; same native components and source coverage as 2.3.6)
- Installer notice correction: [v2.3.6 release](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.6)

## 한국어

이 문서는 현재 공개된 소스의 범위를 설명합니다. 설치 파일의 모든 구성 요소에 대한 전체 대응 소스를 제공한다는 선언이나 향후 제공을 보증하는 서면 제안이 아닙니다.

애플리케이션은 원본의 GNU AGPL-3.0을 따릅니다. `src/`의 Global 수정, 엘림 도감·Core 리소스 수정 스크립트, 빌드 도구를 공개했습니다. 빠져 있던 원본의 `main.py`, `pyproject.toml`, `uv.lock`, `build_exe.py`, `build_installer.py`, `tools/`, `native/` 공개 파일 121개를 기준 커밋에서 복원했습니다. 파일별 해시는 [UPSTREAM_SOURCE_FILES.json](UPSTREAM_SOURCE_FILES.json)에 있습니다. `native/counterfactual-core`는 공개 C++ 프로토타입이며 배포된 비공개 Rust analysis Core의 소스가 아닙니다.

**남은 누락:** 배포된 `nte-core.exe`, `nte-analysis-core.exe`, `nte-mod-loader.exe`(AGPL), `d3d12.dll` 및 User·Combat·HUD·Performance DLL(GPL)의 정확한 전체 대응 소스를 확보하지 못했습니다. 기존 SOURCE 기록에는 수정된 작업 트리나 비공개 소스가 명시되어 있어, 기준 커밋·파일 해시·바이너리 수정 스크립트만으로는 그 전체 소스를 대신할 수 없습니다. 실행 파일 재현 성공도 네이티브 구성 요소의 소스 누락을 해결하지 않습니다.

원본 및 제3자 라이선스·출처 고지는 [license_records/v2.3.6](license_records/v2.3.6)에 설치본 그대로 보존했습니다. 이러한 기록은 소스 코드 자체가 아닙니다. 전체 게임 DB·이미지·일부 생성기 조사 입력도 별도이며, 게임 자료를 일괄 AGPL로 허가하지 않습니다. 제공한 파일만으로 전체 배포본을 소스부터 독립적으로 빌드할 수 있다고 보증하지 않습니다. 완전한 대응 소스 또는 유효한 별도 허락의 확인이 남아 있습니다.

## 中文

本文说明当前公开源码的范围，不是已提供安装包全部组件的完整对应源码的声明，也不是保证日后提供的书面要约。

应用程序沿用原项目 GNU AGPL-3.0。已公开 Global 的 `src/` 修改、曳尔沐图鉴与 Core 资源修改脚本及构建工具。本次从基准提交恢复了入口、依赖与构建元数据、`tools/` 和 `native/` 共 121 个遗漏的公开文件，哈希见 [UPSTREAM_SOURCE_FILES.json](UPSTREAM_SOURCE_FILES.json)。`native/counterfactual-core` 是公开 C++ 原型，不是所分发私有 Rust analysis Core 的源码。

**仍有缺口：** 未取得所分发 `nte-core.exe`、`nte-analysis-core.exe`、`nte-mod-loader.exe`（AGPL），以及 `d3d12.dll`、User、Combat、HUD、Performance DLL（GPL）的精确完整对应源码。现有 SOURCE 记录提及修改后的工作树或私有源码；基准提交、哈希和二进制修改脚本不能替代完整源码。可复现某个可执行文件不代表解决了原生组件的源码缺失。

[license_records/v2.3.6](license_records/v2.3.6) 原样保留安装包中的许可与来源记录，这些记录并非源码。完整游戏数据库、图片及部分生成器研究输入也未全部提供，游戏材料不因此统一转为 AGPL 授权。不保证仅凭此包即可从源码独立构建整个发行版。仍需确认完整对应源码或有效的另行许可。

## English

This document describes the available source. It is neither a statement that complete Corresponding Source for every installer component has been supplied nor a written offer guaranteeing future delivery.

The application follows upstream GNU AGPL-3.0. Published materials include the Global `src/` changes, Elyms catalog/Core resource adaptation scripts and build tools. This supplement restores 121 omitted public upstream files: bootstrap, dependency/build metadata, `tools/` and `native/`. [UPSTREAM_SOURCE_FILES.json](UPSTREAM_SOURCE_FILES.json) records their hashes. `native/counterfactual-core` is a public C++ prototype, not the source of the distributed private Rust analysis Core.

**Remaining gaps:** the exact complete Corresponding Source of the distributed `nte-core.exe`, `nte-analysis-core.exe`, `nte-mod-loader.exe` (AGPL), and `d3d12.dll` plus the User, Combat, HUD and Performance DLLs (GPL) has not been obtained. Their SOURCE records refer to modified working trees or private sources. Base commits, hashes and binary adaptation scripts are not substitutes for complete source. Reproducing an executable does not resolve missing native component source.

[license_records/v2.3.6](license_records/v2.3.6) preserves the installed license and provenance records unchanged; these records are not source code. The full game databases/artwork and some generator research inputs are also not all provided. Game materials are not collectively relicensed under AGPL. A standalone build of the whole distribution from this archive alone is not promised. Complete Corresponding Source or applicable separate permission still needs to be established.

## 日本語

本書は現在公開しているソースの範囲を説明します。インストーラーの全コンポーネントについて完全な対応ソースを提供したという声明でも、将来の提供を保証する書面による申し出でもありません。

アプリケーションは原本の GNU AGPL-3.0 に従います。Global の `src/` 変更、イェルムの図鑑・Core リソース変更スクリプト、ビルドツールを公開しています。今回、入口ファイル、依存・ビルド情報、`tools/`、`native/` の欠落していた公開原本ファイル計 121 個を基準コミットから復元しました。ハッシュは [UPSTREAM_SOURCE_FILES.json](UPSTREAM_SOURCE_FILES.json) に記載しています。`native/counterfactual-core` は公開 C++ 試作コードであり、配布された非公開 Rust analysis Core のソースではありません。

**未解決の欠落：** 配布された `nte-core.exe`、`nte-analysis-core.exe`、`nte-mod-loader.exe`（AGPL）、および `d3d12.dll` と User・Combat・HUD・Performance DLL（GPL）の正確で完全な対応ソースを確保できていません。SOURCE 記録には変更済み作業ツリーや非公開ソースへの言及があり、基準コミット、ハッシュ、バイナリ変更スクリプトでは完全なソースを代替できません。実行ファイルの再現だけではこの欠落は解消しません。

[license_records/v2.3.6](license_records/v2.3.6) にはインストール先のライセンスと出典記録をそのまま保存していますが、記録自体はソースコードではありません。ゲーム DB・画像の全体、一部生成器の調査入力もすべては含まれていません。ゲーム資料を一括して AGPL で再許諾するものではありません。この ZIP だけで配布版全体をソースから独立してビルドできるとは保証していません。完全な対応ソースまたは有効な別途許諾の確認が残っています。

## Build and provenance

[Build instructions](build_tools/README.md) · [Elyms adaptation](build_tools/ELYMS.md) · [Installer notice correction](docs/SOURCE_OFFER_CORRECTION_2.3.6.md) · [Historical source commits](docs/source-history.md)

| Retained 2.3.6 artifact | SHA-256 |
|---|---|
| `NTE_Drive_Calc_2.3.6_Multilingual_Setup.exe` | `8f797c7657f425423347253b09c6dc8e5bccffd6ef15f7d03fd7edaf48eecabb` |
| Installed `NTE_Drive_Calc.exe` | `3743845cb74a5ed7e175464386d4411fd32bda611cec5fd9a8570ea31a623115` |

The source/documentation supplement does not change `src/`, the v2.3.6 Git tag, or installer bytes. The release notes identify the supplement commit and new source ZIP hash. Previously distributed documents remain in Git history as historical records; their source-completeness claims are corrected here.
