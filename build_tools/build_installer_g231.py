# NTE Drive Calc Global 2.3.1 (zh/ko/ja/en) 공식 방식 전체 설치 프로그램(Inno Setup) 생성기
r"""Build the official-style FULL installer of NTE Drive Calc Global (the unofficial multilingual build).

This is a port of upstream ``build_installer.py`` at commit 0e7a6b4 (official 2.3.1).  The upstream script packages
``dist/NTE_Drive_Calc`` straight out of PyInstaller; we cannot rebuild that bundle (private native components), so
the payload is a *stage* directory holding exactly what the official installer lays down, and the executable is our
rebuilt one:

    <stage>/_internal/**            official PyInstaller runtime directory (verbatim, except the seven tutorial
                                    images _internal/config/templates/guide/1..7.png, which are the Korean ones)
    <stage>/drivers/ViGEmBus_Setup.exe
    <stage>/config/stats.json       optional; must equal _internal/config/stats.json (the upstream source of
                                    {app}\config\stats.json)
    <stage>/stage_manifest.json     optional but recommended: path/size/sha256 of every staged file; when present
                                    the stage is verified against it before building

What follows upstream 0e7a6b4 (the [Files] / [InstallDelete] / [Dirs] structure is the same):
  - VersionInfoVersion / VersionInfoProductVersion = windows_numeric_version(version), plus the two text versions;
  - stale files deleted on install: _internal\assets\game_ui (folder), the ambient ICU DLLs, and dwmapi.dll ONLY when
    the bundled component layout is "native-capture-v1" (2.3.0 and older).  2.3.1 ships "native-plugins-v3"
    (d3d12.dll host + plugins\NTE_Plugin*.dll), so dwmapi.dll is not touched;
  - byte-identical role-catalog images (_internal\data\role_catalog\game_ui) are stored once and installed at both
    paths (upstream tools/release/installer_asset_dedup.py: the copies are excluded from the recursive line and
    re-added as DestName lines with the donor as source).
What differs: our executable, the wizard in four languages (en / ko / ja / zh; the first run of the program uses
the wizard language unless a language file already exists), the notice page, three documents in {app}\l10n_build,
the uninstall entry name, and [UninstallDelete] of the language file the installer may have written.

Usage (Python 3.11):
    build_installer_g231.py --exe <NTE_Drive_Calc.exe> --stage <dir> --out <dir> --variant release
    build_installer_g231.py --exe <NTE_Drive_Calc.exe> --stage <dir> --out <dir> --variant sandbox
    build_installer_g231.py --stage <dir> --write-stage-manifest          (re)write stage_manifest.json

Variants
    release  same AppId / default directory / privileges as the official installer, so it upgrades an official,
             KO-patched or earlier Global installation in place and a later official installer upgrades over it.
    sandbox  PrivilegesRequired=lowest, a test-only AppId (the same one the Global 2.3.0 sandbox build used), no
             ViGEmBus task / run step / shortcut, default directory under C:\Temp - for testing without
             administrator rights and without touching the real installation or its uninstall registry entry.

Versions: ``--version`` is the GLOBAL version of ``src/app/global_release.py`` (``--tree <root>`` refuses a
mismatch), in the grammar ``<major>.<minor>.<patch>`` with an optional ``-global.<n>`` suffix (n >= 1; the releases
before 2.3.2 carry it, from 2.3.2 the Global version is plain).  It must be newer than the last published release
``PREVIOUS_RELEASE_VERSION`` (2.3.1-global.2); versions are ordered as (major, minor, patch, n) with n = 0 without
the suffix.  AppVersion / DisplayVersion carry the full Global version, VERSIONINFO is ``major.minor.patch.n``, the
program entry name carries ``major.minor.patch`` of the Global version, the asset names carry the full version (the
in-app updater derives them from the release tag).  The documents and the manifest's ``upstream_base`` name the
official version the build is based on (``UPSTREAM_BASE``, = src/app/version.py of the tree).  The installer also carries the
gated ``[Run]`` entry that restarts the program after an in-app update (``/AUTOUPDATE=1 /RELAUNCH=1``, silent only)
and removes ``{app}\\updates`` on uninstall.  ``--emit-manifest`` writes the unsigned release manifest the updater
verifies (sign it with ``ssh-keygen -Y sign`` afterwards; see build_tools/README.md).

Outputs in --out:
    <output base>.exe   (default NTE_Drive_Calc_<version>_Multilingual_Setup[_sandbox])
    NTE_Drive_Calc_<version>_release.json   (with --emit-manifest; unsigned)
Outputs in --aux-dir (default: --out):
    payload_manifest_<variant>.json   every file the installer lays down under {app} (size, sha256)
    build_report_<variant>.json       installer size/sha256, compile time, inputs
    build_<variant>/                  generated setup.iss, Chinese message overrides, notices, docs, ISCC log
    (these contain local paths: never publish them)

Nothing is uploaded, nothing outside --out / --aux-dir (and stage_manifest.json with --write-stage-manifest) is written.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_LICENSE = TOOLS_DIR.parent / "LICENSE"                  # repository root: the upstream LICENSE, verbatim

APP_NAME = "NTE Drive Calc"
APP_EXE_NAME = "NTE_Drive_Calc.exe"
OFFICIAL_APP_ID = "D7DA28BE-8A19-4E05-9216-3F16C4C2C820"      # upstream build_installer.py APP_ID
SANDBOX_APP_ID = "5B0C6E1A-7F2D-4C39-8E54-1D9A3F6B2C70"       # test-only identity, never the official one
SANDBOX_DEFAULT_DIR = r"C:\Temp\nte_g231_setup_sandbox"
DEFAULT_VERSION = "2.3.7"                                      # Global grammar: <major>.<minor>.<patch>[-global.<n>]
# the grammar of src/app/global_release.py (_PLAIN / _VERSION_CORE): fullmatch only, ASCII digits, no leading zeros
_PLAIN = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
_VERSION_CORE = _PLAIN + r"(?:-global\.([1-9][0-9]*))?"
GLOBAL_VERSION_RE = re.compile(_VERSION_CORE, re.ASCII)
GLOBAL_TAG_RE = re.compile(r"v" + _VERSION_CORE, re.ASCII)
PREVIOUS_RELEASE_VERSION = "2.3.6"                    # last published release: --version must be newer
UPSTREAM_BASE = "2.3.1"                                        # official version this build is based on (src/app/version.py)
MANIFEST_FORMAT = 1                                            # src/services/global_update/verify.py parse_manifest
MANIFEST_PRODUCT = "NTE-Drive-Calc-Global"
FIRST_AUTO_UPDATE_VERSION = "2.3.4"                            # first build that trusts the current release key
RELEASE_KEY_ID_DEFAULT = "nte-global-release"
RELEASE_SIG_NAMESPACE = "nte-drive-calc-global-release"       # src/app/global_release.py RELEASE_SIG_NAMESPACE
RELEASE_PUBKEY_DEFAULT = Path(os.environ.get("USERPROFILE") or str(Path.home())) / ".ssh" / "nte_global_release_20261107.pub"
# throwaway TEST keys used by the sandbox end-to-end tests (public halves only): never pinned by a release
KNOWN_TEST_KEY_FINGERPRINTS = ("SHA256:rtNBWF/OjSt0BLrQqMA6az9qA/OAMaZdf7heZnAQw2M",)
TEST_HOOK_MARKERS = ("NTE_GUP_", "NTE_SMOKE_")
REMOVABLE_UPSTREAM_MODULES = ("features/settings/updates", "ui/controllers/update_controller")
UPSTREAM_COMMIT = "0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1"
UPSTREAM_URL = "https://github.com/hxwd94666/NTE-Drive-Calculator"
PROJECT_URL = "https://github.com/LuinDe/NTE-Drive-Calc-Global"
PUBLISHER = "NTE Drive Calc Global (unofficial multilingual build)"
DOCS_DIR_NAME = "l10n_build"                                   # {app}\l10n_build\LICENSE.txt ...
STAGE_MANIFEST_NAME = "stage_manifest.json"
LANGUAGE_FILE_REL = "_internal/config/i18n_language.json"      # written by [Code], never packaged

CLOSE_APPLICATIONS_FILTER = "NTE_Drive_Calc.exe,nte-mod-loader.exe,nte-core.exe,nte-analysis-core.exe"
CORE_CONFIG_FILES = ("stats.json",)                            # upstream CORE_CONFIG_FILES
STALE_AMBIENT_ICU_DLLS = ("icuuc.dll", "icudt78.dll")          # upstream STALE_AMBIENT_ICU_DLLS
LEGACY_CAPTURE_LAYOUT = "native-capture-v1"                    # upstream GameComponentBundleInspection default
KNOWN_LAYOUTS = (LEGACY_CAPTURE_LAYOUT, "native-plugins-v3")
VIGEM_DEST_NAME = "ViGEmBus_Setup.exe"
VIGEM_PARAMS = "/qn /norestart"
CATALOG_IMAGE_ROOT = "data/role_catalog/game_ui"               # upstream installer_asset_dedup catalog_root
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")             # upstream installer_asset_dedup IMAGE_SUFFIXES

# Upstream _validate_app_bundle(): files that must exist in the PyInstaller runtime directory.
REQUIRED_INTERNAL = (
    "nte-core.exe",
    "nte-analysis-core.exe",
    "analysis-core-meta/component.json",
    "component-bundle.json",
    "src/storage/sqlite/schema/001_user_data.sql",
    "data/game_static.sqlite3",
    "data/manifest.json",
    "data/app_shared.sqlite3",
    "data/migrations/shape_bonus_defaults_2.0.2.json",
    "config/stats.json",
)
# Never part of a clean payload: user/runtime data, files a test run writes next to the runtime, and leftovers of
# the exe-only patch kits.
FORBIDDEN_INTERNAL = (
    "config/i18n_language.json",
    "config/templates/guide_zh",
    "NTE.log",
    "logs",
    "plugins/.loaded",
)

# Wizard languages.  Names double as the app's language codes (src/i18n_runtime.LANGUAGES) and are
# deliberately different from the official installer's single language name "chinesesimp": with
# UsePreviousLanguage=yes an upgrade of an official install then falls back to OS language detection
# instead of preselecting Chinese, while our own earlier choice is still remembered.
# First entry = fallback when the OS UI language matches none of them.
LANGS = ("en", "ko", "ja", "zh")
MESSAGES_FILES = {
    "en": "compiler:Default.isl",
    "ko": r"compiler:Languages\Korean.isl",
    "ja": r"compiler:Languages\Japanese.isl",
    "zh": "compiler:Default.isl,{zh_isl}",      # no Chinese .isl ships with Inno Setup 6
}

CUSTOM_MESSAGES = {
    "L10nAppVerName": {
        "en": "NTE Drive Calc {version} Multilingual Edition (Global)",
        "ko": "NTE Drive Calc {version} 다국어판 (Global)",
        "ja": "NTE Drive Calc {version} 多言語版 (Global)",
        "zh": "NTE Drive Calc {version} 多语言版 (Global)",
    },
    "RuntimeDepsGroup": {
        "en": "Runtime dependencies:",
        "ko": "실행에 필요한 구성 요소:",
        "ja": "実行に必要なコンポーネント:",
        "zh": "运行依赖：",
    },
    "ViGEmTask": {
        "en": "Install the ViGEmBus virtual gamepad driver",
        "ko": "ViGEmBus 가상 게임패드 드라이버 설치",
        "ja": "ViGEmBus 仮想ゲームパッドドライバーをインストールする",
        "zh": "安装 ViGEmBus 虚拟手柄驱动",
    },
    "ViGEmIconName": {
        "en": "Install ViGEmBus driver",
        "ko": "ViGEmBus 드라이버 설치",
        "ja": "ViGEmBus ドライバーのインストール",
        "zh": "安装 ViGEmBus 驱动",
    },
    "UninstallIconName": {
        "en": "Uninstall NTE Drive Calc",
        "ko": "NTE Drive Calc 제거",
        "ja": "NTE Drive Calc のアンインストール",
        "zh": "卸载 NTE Drive Calc",
    },
    "StatusInstallViGEm": {
        "en": "Installing or repairing the ViGEmBus virtual gamepad driver...",
        "ko": "ViGEmBus 가상 게임패드 드라이버를 설치(복구)하는 중...",
        "ja": "ViGEmBus 仮想ゲームパッドドライバーをインストール／修復しています...",
        "zh": "正在安装或修复 ViGEmBus 虚拟手柄驱动...",
    },
    "StatusStartViGEm": {
        "en": "Starting the ViGEmBus driver service...",
        "ko": "ViGEmBus 드라이버 서비스를 시작하는 중...",
        "ja": "ViGEmBus ドライバーサービスを開始しています...",
        "zh": "正在启动 ViGEmBus 驱动服务...",
    },
    "MigrationBackupFailed": {
        "en": "Could not back up the previous static database. Installation was stopped.",
        "ko": "이전 버전의 정적 데이터베이스를 백업하지 못해 설치를 중단했습니다.",
        "ja": "旧バージョンの静的データベースをバックアップできなかったため、インストールを中止しました。",
        "zh": "无法备份旧版静态数据库，安装已停止。",
    },
}
# Shortcut names are file names: they must stay free of \ / : * ? " < > |
ICON_MESSAGE_KEYS = ("ViGEmIconName", "UninstallIconName")

# Upstream build_installer.py `chinese_messages` (verbatim, unchanged between 2.3.0 and 2.3.1) ...
ZH_MESSAGES_UPSTREAM = """\
SetupAppTitle=安装程序
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载
UninstallAppFullTitle=%1 卸载
InformationTitle=提示
ConfirmTitle=确认
ErrorTitle=错误
SetupLdrStartupMessage=即将安装 %1。是否继续？
AdminPrivilegesRequired=安装本程序需要管理员权限。
SetupAppRunningError=安装程序检测到 %1 正在运行。%n%n请先关闭程序后点击“确定”继续，或点击“取消”退出安装。
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成。如果现在退出，程序将不会被完整安装。%n%n是否退出安装？
ButtonBack=< 上一步
ButtonNext=下一步 >
ButtonInstall=安装
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是
ButtonNo=否
ButtonFinish=完成
ButtonBrowse=浏览...
ClickNext=点击“下一步”继续，或点击“取消”退出安装。
BrowseDialogTitle=选择文件夹
BrowseDialogLabel=请选择一个文件夹，然后点击“确定”。
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=本向导将在你的电脑上安装 [name/ver]。%n%n建议在继续之前关闭其他正在运行的应用程序。
WizardSelectDir=选择安装位置
SelectDirDesc=请选择 [name] 的安装目录
SelectDirLabel3=安装程序会将 [name] 安装到以下文件夹。
SelectDirBrowseLabel=点击“下一步”继续。如需选择其他文件夹，请点击“浏览”。
DiskSpaceGBLabel=至少需要 [gb] GB 可用磁盘空间。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁盘空间。
DirExistsTitle=文件夹已存在
DirExists=文件夹：%n%n%1%n%n已经存在。是否仍然安装到该文件夹？
DirDoesntExistTitle=文件夹不存在
DirDoesntExist=文件夹：%n%n%1%n%n不存在。是否创建该文件夹？
WizardSelectTasks=选择附加任务
SelectTasksDesc=请选择安装时需要执行的附加任务
SelectTasksLabel2=请选择安装 [name] 时要执行的附加任务，然后点击“下一步”。
WizardReady=准备安装
ReadyLabel1=安装程序已准备好开始安装 [name]。
ReadyLabel2a=点击“安装”开始安装；如需检查或修改设置，请点击“上一步”。
ReadyLabel2b=点击“安装”开始安装。
ReadyMemoDir=安装位置：
ReadyMemoGroup=开始菜单文件夹：
ReadyMemoTasks=附加任务：
WizardPreparing=准备安装
PreparingDesc=安装程序正在准备安装 [name]。
ApplicationsFound=以下程序正在使用需要更新的文件。建议允许安装程序自动关闭这些程序。
ApplicationsFound2=以下程序正在使用需要更新的文件。建议允许安装程序自动关闭这些程序。安装完成后，安装程序会尝试重新启动它们。
CloseApplications=自动关闭这些程序
DontCloseApplications=不要关闭这些程序
WizardInstalling=正在安装
InstallingLabel=请稍候，安装程序正在将 [name] 安装到你的电脑。
FinishedHeadingLabel=[name] 安装向导完成
FinishedLabelNoIcons=[name] 已成功安装到你的电脑。
FinishedLabel=[name] 已成功安装到你的电脑。你可以通过已创建的快捷方式启动程序。
ClickFinish=点击“完成”退出安装程序。
RunEntryExec=运行 %1
SetupAborted=安装未完成。%n%n请修正问题后重新运行安装程序。
StatusClosingApplications=正在关闭应用程序...
StatusCreateDirs=正在创建文件夹...
StatusExtractFiles=正在释放文件...
StatusCreateIcons=正在创建快捷方式...
StatusSavingUninstall=正在保存卸载信息...
StatusRunProgram=正在完成安装...
StatusRollback=正在回滚更改...
ErrorExecutingProgram=无法执行文件：%n%1
FileExists2=文件已存在。
FileExistsOverwriteExisting=覆盖现有文件
FileExistsKeepExisting=保留现有文件
ExistingFileNewer2=现有文件比安装程序要安装的文件更新。
ExistingFileNewerOverwriteExisting=覆盖现有文件
ExistingFileNewerKeepExisting=保留现有文件（推荐）
ConfirmUninstall=确定要完全移除 %1 及其所有组件吗？
UninstallStatusLabel=请稍候，正在从你的电脑中移除 %1。
UninstalledAll=%1 已成功从你的电脑中移除。
UninstalledMost=%1 卸载完成。%n%n部分内容无法移除，可以手动删除。
WizardUninstalling=卸载状态
StatusUninstalling=正在卸载 %1...
"""
# ... plus the pages the official single-language wizard never shows (language dialog, notice page).
ZH_MESSAGES_EXTRA = """\
SelectLanguageTitle=选择安装语言
SelectLanguageLabel=请选择安装过程中使用的语言。
WizardInfoBefore=信息
InfoBeforeLabel=继续安装前请阅读以下重要信息。
InfoBeforeClickLabel=准备好继续安装后，请点击“下一步”。
"""
# Upstream `chinese_custom_messages` (verbatim).
ZH_CUSTOM_MESSAGES_UPSTREAM = """\
NameAndVersion=%1 版本 %2
AdditionalIcons=附加快捷方式：
CreateDesktopIcon=创建桌面快捷方式
ProgramOnTheWeb=%1 官方页面
UninstallProgram=卸载 %1
LaunchProgram=启动 %1
"""

NOTICE = {
    "ko": """\
NTE Drive Calc Global {global_version} - NTE Drive Calc {version} 다국어판 (비공식 빌드)

이 설치 프로그램은 NTE Drive Calc {version} 의 비공식 다국어(한국어 / English / 日本語 / 简体中文) 빌드를 설치합니다.
원 프로그램 제작자(hxwd94666 및 NTE Drive Calc contributors)가 배포하는 공식 빌드가 아니며, 공식 지원 대상이 아닙니다.
원 프로젝트: {upstream_url}
이 빌드: {project_url}

- 공식 버전과 같은 위치·같은 프로그램 항목으로 설치됩니다. 공식 {version}, 이전 다국어판(Global 2.3.0), 한글 패치를 적용한 {version} 이 설치되어 있으면 그 자리에서 업그레이드합니다.
- 계정, 설정, 로그, 저장한 사이클, 효율표 캐시 등 사용자 데이터는 그대로 유지됩니다. 한글 패치가 만든 백업 파일(NTE_Drive_Calc.original.exe 등)도 지우지 않습니다.
- 나중에 공식 설치 프로그램을 실행하면 공식 버전으로 되돌릴 수 있습니다.
- 이 빌드는 시작할 때(하루 한 번) {releases_url} 에서 새 Global 버전을 확인하고, 사용자가 승인하면 같은 폴더에 설치합니다. 원 프로젝트의 업데이트 채널은 사용하지 않습니다.
- 프로그램은 지금 고른 설치 언어로 시작하며(이미 언어를 설정해 둔 경우 그 설정을 유지), 프로그램 안에서 언제든 바꿀 수 있습니다.
- 팀 시뮬레이션(Beta)과 아크 효율표는 이 빌드에서 추가한 기능이며, 계산 모델에 한계가 있습니다(자세한 내용은 저장소의 README).

라이선스: GNU AGPL-3.0
라이선스 전문과 소스 코드 안내는 설치 폴더의 {docs} 폴더(LICENSE.txt, SOURCE_OFFER.txt, README.txt)에 들어 있습니다.
공개 Calc/Global 소스와 수정 자료: {source_zip}. 배포된 Core·analysis Core·Loader·캡처 DLL의 정확한 전체 대응 소스는 아직 확보되지 않았습니다. 소스 제공 범위와 남은 항목은 SOURCE_OFFER.txt 및 저장소의 SOURCE_OFFER.md를 확인하세요.
""",
    "en": """\
NTE Drive Calc Global {global_version} - Multilingual Edition of NTE Drive Calc {version} (unofficial build)

This installer sets up an unofficial multilingual (Korean / English / Japanese / Simplified Chinese) build of NTE Drive Calc {version}.
It is NOT an official build published by the original authors (hxwd94666 and NTE Drive Calc contributors) and is not supported by them.
Original project: {upstream_url}
This build: {project_url}

- It installs to the same location and under the same program entry as the official version. An existing official {version}, an earlier multilingual build (Global 2.3.0) or a Korean-patched {version} is upgraded in place.
- User data such as accounts, settings, logs, saved cycles and the efficiency-table cache is kept. Backup files made by the Korean patch (NTE_Drive_Calc.original.exe and others) are not removed.
- Running the official installer later restores the official version.
- At startup (at most once a day) this build checks {releases_url} for a newer Global version and, after your confirmation, installs it into the same folder. The original project's update channel is not used.
- The program starts in the language chosen for this setup (an existing language setting is kept); it can be changed inside the program at any time.
- Team Simulation (Beta) and the Arc Efficiency table are features added by this build; their calculation model has limits (see the README of the repository).

License: GNU AGPL-3.0
The full license text and the source code notice are installed into the {docs} folder of the installation directory (LICENSE.txt, SOURCE_OFFER.txt, README.txt).
Public Calc/Global source and adaptations: {source_zip}. Exact complete Corresponding Source for the distributed Core, analysis Core, Loader and capture DLLs has not been obtained. See SOURCE_OFFER.txt and the repository SOURCE_OFFER.md for coverage and remaining gaps.
""",
    "ja": """\
NTE Drive Calc Global {global_version} - NTE Drive Calc {version} 多言語版（非公式ビルド）

このインストーラーは NTE Drive Calc {version} の非公式多言語（韓国語 / English / 日本語 / 簡体字中国語）ビルドをインストールします。
原作者（hxwd94666 および NTE Drive Calc contributors）が配布する公式ビルドではなく、公式サポートの対象外です。
元のプロジェクト: {upstream_url}
このビルド: {project_url}

- 公式版と同じ場所・同じプログラム項目にインストールされます。公式 {version}、以前の多言語版（Global 2.3.0）、韓国語パッチを適用した {version} がインストール済みの場合は、そのまま上書きアップグレードします。
- アカウント、設定、ログ、保存したサイクル、効率表のキャッシュなどのユーザーデータは保持されます。韓国語パッチが作成したバックアップファイル（NTE_Drive_Calc.original.exe など）も削除しません。
- 後で公式インストーラーを実行すれば公式版に戻せます。
- このビルドは起動時（1日1回まで）に {releases_url} で新しい Global バージョンを確認し、承認すると同じフォルダーにインストールします。元プロジェクトの更新チャンネルは使用しません。
- プログラムはここで選んだ言語で起動します（すでに言語を設定済みの場合はその設定を維持）。言語はプログラム内でいつでも変更できます。
- チームシミュレーション（Beta）とアーク効率表はこのビルドで追加した機能で、計算モデルには限界があります（詳しくはリポジトリの README）。

ライセンス: GNU AGPL-3.0
ライセンス全文とソースコードの案内は、インストール先の {docs} フォルダー（LICENSE.txt、SOURCE_OFFER.txt、README.txt）に入っています。
公開 Calc/Global ソースと変更資料: {source_zip}。配布された Core・analysis Core・Loader・キャプチャ DLL の正確で完全な対応ソースは未確保です。範囲と未解決事項は SOURCE_OFFER.txt およびリポジトリの SOURCE_OFFER.md を確認してください。
""",
    "zh": """\
NTE Drive Calc Global {global_version} - NTE Drive Calc {version} 多语言版（非官方构建）

本安装程序将安装 NTE Drive Calc {version} 的非官方多语言（韩语 / English / 日语 / 简体中文）构建。
它不是原作者（hxwd94666 及 NTE Drive Calc contributors）发布的官方构建，也不在官方支持范围内。
原项目：{upstream_url}
本构建：{project_url}

- 安装位置和程序条目与官方版本相同。如果已安装官方 {version}、更早的多语言版（Global 2.3.0）或打过韩语补丁的 {version}，将直接原地升级。
- 账号、设置、日志、保存的循环、效率表缓存等用户数据会被保留。韩语补丁创建的备份文件（NTE_Drive_Calc.original.exe 等）也不会被删除。
- 之后运行官方安装程序即可恢复为官方版本。
- 本构建会在启动时（每天至多一次）检查 {releases_url} 是否有新的 Global 版本，经你确认后安装到同一文件夹。不使用原项目的更新渠道。
- 程序将以此处选择的安装语言启动（如已设置过语言则保留原设置），之后可随时在程序内切换。
- 队伍模拟（Beta）和弧盘效率表是本构建新增的功能，其计算模型有局限（详见仓库的 README）。

许可证：GNU AGPL-3.0
许可证全文与源代码说明位于安装目录的 {docs} 文件夹（LICENSE.txt、SOURCE_OFFER.txt、README.txt）。
公开 Calc/Global 源码及修改材料：{source_zip}。所分发 Core、analysis Core、Loader 与捕获 DLL 的精确完整对应源码尚未取得。范围及缺口请参阅 SOURCE_OFFER.txt 和仓库的 SOURCE_OFFER.md。
""",
}

SOURCE_OFFER = """\
NTE Drive Calc Global {global_version} — public source coverage / 소스 제공 범위 / 源码范围 / ソースの範囲

Original author: hxwd94666 and NTE Drive Calc contributors
Author profile: https://github.com/hxwd94666
Original project: {upstream_url}
Global maintainer: LuinDe — {project_url}
Upstream baseline: {upstream_commit} (Calc {version})
Public source archive: {source_zip}
Application executable: {exe_name}
Application executable SHA-256: {exe_sha256}

[한국어]
비공식 다국어 파생 프로젝트입니다. 애플리케이션은 GNU AGPL-3.0을 따르며, 함께 배포되는 구성 요소에는 각 라이선스가 적용됩니다.
ZIP에는 Global src/, 공개 원본 진입점·의존성·빌드 도구, 공개 native/ 프로토타입, 엘림 자료와 Core 리소스 수정 스크립트가 들어 있습니다.
배포된 Core·analysis Core·Loader(AGPL)와 캡처 DLL 5개(GPL)의 정확한 전체 대응 소스는 아직 확보되지 않았습니다. 공개 프로토타입·해시·수정 스크립트는 그 대체물이 아닙니다.
일부 생성기 입력과 전체 게임 자료도 제공되지 않습니다. 게임 자료는 각 권리자의 권리를 따릅니다. ZIP만으로 전체 배포본을 소스부터 독립 빌드할 수 있다고 보증하지 않습니다.
이 문서는 모든 재배포 조건을 충족했다는 선언이나 향후 소스 제공을 보증하는 서면 제안이 아닙니다.

[中文]
本项目是非官方多语言衍生版本。应用程序遵循 GNU AGPL-3.0，捆绑组件遵循各自许可。
ZIP 包含 Global src/、公开原本入口与依赖及构建工具、公开 native/ 原型、曳尔沐资料及 Core 资源修改脚本。
所分发 Core、analysis Core、Loader（AGPL）和 5 个捕获 DLL（GPL）的精确完整对应源码尚未取得。原型、哈希和修改脚本不能替代这些源码。
部分生成器输入和完整游戏资料也未提供。游戏资料属于各权利人。不保证仅凭此 ZIP 即可从源码独立构建整个发行版。
本文不声明已满足全部再分发条件，也不是保证日后提供源码的书面要约。

[English]
This is an unofficial multilingual derivative. The application follows GNU AGPL-3.0; bundled components retain their own licenses.
The ZIP includes Global src/, public upstream bootstrap/dependency/build files, the public native/ prototype, Elyms materials and Core resource adaptation scripts.
Exact complete Corresponding Source for the distributed Core, analysis Core and Loader (AGPL) and five capture DLLs (GPL) has not been obtained. Prototypes, hashes and adaptation scripts are not substitutes.
Some generator inputs and the full game materials are also not supplied. Game materials belong to their respective rights holders. A standalone build of the entire distribution from this ZIP alone is not promised.
This notice does not establish compliance with all redistribution conditions and is not a written offer guaranteeing future source delivery.

[日本語]
非公式の多言語派生プロジェクトです。アプリケーションは GNU AGPL-3.0 に従い、同梱コンポーネントには各ライセンスが適用されます。
ZIP には Global src/、公開原本の入口・依存・ビルド情報、公開 native/ 試作コード、イェルム資料と Core リソース変更スクリプトを含みます。
配布された Core・analysis Core・Loader（AGPL）とキャプチャ DLL 5 個（GPL）の正確で完全な対応ソースは未確保です。試作コード・ハッシュ・変更スクリプトは代替になりません。
一部生成器の入力と全ゲーム資料も未提供です。ゲーム資料の権利は各権利者に帰属します。この ZIP だけで配布版全体をソースから独立ビルドできるとは保証していません。
本書は全再配布条件の充足を宣言するものでも、将来のソース提供を保証する書面による申し出でもありません。

Detailed scope and remaining gaps: {project_url}/blob/main/SOURCE_OFFER.md
Build instructions: build_tools/README.md in the source archive.
Application license: LICENSE / LICENSE.txt. Installed component notices: _internal/licenses.
Preserved component notice records: license_records/v2.3.6 in the source archive (records are not source code).
"""

README = """\
NTE Drive Calc Global {global_version} - NTE Drive Calc {version} 다국어판 (비공식 빌드) / Multilingual Edition (unofficial build)
================================================================================================================

[한국어]
이 폴더는 NTE Drive Calc {version} 비공식 다국어판(NTE Drive Calc Global) 설치 프로그램이 만든 것입니다.
원 프로그램 제작자(hxwd94666 및 NTE Drive Calc contributors)가 배포하는 공식 빌드가 아니며, 공식 지원 대상이 아닙니다.
원 프로젝트: {upstream_url}
이 빌드: {project_url}

- 지원 언어: 한국어, English, 日本語, 简体中文. 프로그램 안에서 언제든 바꿀 수 있습니다.
- 처음 설치할 때는 설치 마법사에서 고른 언어로 시작합니다(_internal\\config\\i18n_language.json).
  이미 언어 설정이 있으면 설치 프로그램은 그 설정을 바꾸지 않습니다.
- 공식 버전과 같은 위치·같은 프로그램 항목으로 설치됩니다. 업그레이드해도 계정, 설정, 로그 등 사용자
  데이터는 그대로 유지됩니다.
- 공식 버전으로 되돌리려면 공식 설치 프로그램을 다시 실행하면 됩니다.
- 제거는 Windows 의 "앱 및 기능" 또는 시작 메뉴의 제거 바로 가기를 사용합니다. 공식 버전과 마찬가지로
  사용자 데이터(accounts, config, logs, migration 등)는 지우지 않습니다.
- 라이선스: GNU AGPL-3.0 (LICENSE.txt). 소스 코드 안내: SOURCE_OFFER.txt.

[English]
This folder was created by the installer of the unofficial multilingual edition of NTE Drive Calc {version}
(NTE Drive Calc Global). It is NOT an official build published by the original authors (NTE Drive Calc
contributors) and is not supported by them.
Original project: {upstream_url}
This build: {project_url}

- Languages: Korean, English, Japanese, Simplified Chinese. The language can be changed inside the program.
- On first installation the program starts in the language chosen in the setup wizard
  (_internal\\config\\i18n_language.json). An existing language setting is never changed by the installer.
- It installs to the same location and under the same program entry as the official version. Upgrading keeps
  user data such as accounts, settings and logs.
- To go back to the official version, run the official installer again.
- To uninstall, use Windows "Apps & features" or the uninstall shortcut in the Start menu. Like the official
  version, uninstalling does not delete user data (accounts, config, logs, migration, ...).
- License: GNU AGPL-3.0 (LICENSE.txt). Source code notice: SOURCE_OFFER.txt.
"""


class BuildError(RuntimeError):
    pass


def info(message: str) -> None:
    print(f"[installer-g231] {message}", flush=True)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_global_version(value: str) -> tuple[int, int, int, int]:
    """``2.3.2`` -> (2, 3, 2, 0), ``2.3.1-global.2`` -> (2, 3, 1, 2): the grammar of src/app/global_release.py (no
    leading zeros, ASCII digits, ``-global.<n>`` optional with n from 1, every part <= 65535).  A tag
    (``v2.3.2``) or anything else is refused.  The tuple is the release order."""
    match = GLOBAL_VERSION_RE.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise BuildError(f"not a Global version (expected <major>.<minor>.<patch>[-global.<n>]): {value!r}")
    parts = tuple(0 if part is None else int(part) for part in match.groups())
    if any(part > 65535 for part in parts):
        raise BuildError(f"not a Global version (every part must be <= 65535): {value!r}")
    major, minor, patch, n = parts
    return major, minor, patch, n


def global_version_text(parts: tuple[int, int, int, int]) -> str:
    """(2, 3, 2, 0) -> ``2.3.2``; (2, 3, 1, 2) -> ``2.3.1-global.2`` (src.app.global_release.GlobalVersion.text)."""
    major, minor, patch, n = parts
    core = f"{major}.{minor}.{patch}"
    return core if n == 0 else f"{core}-global.{n}"


def require_newer_than_previous(value: str) -> None:
    """A build must be strictly newer than the last published release (2.3.1-global.2)."""
    if parse_global_version(value) <= parse_global_version(PREVIOUS_RELEASE_VERSION):
        raise BuildError(f"--version {value} is not newer than the published release {PREVIOUS_RELEASE_VERSION}")


def windows_numeric_version(value: str) -> str:
    """VERSIONINFO of the Global build: ``2.3.2`` -> ``2.3.2.0``, ``2.3.1-global.2`` -> ``2.3.1.2``
    (src.app.global_release.global_numeric_version)."""
    return ".".join(str(part) for part in parse_global_version(value))


def base_version(value: str) -> str:
    """``major.minor.patch`` of a Global version (``2.3.2`` -> ``2.3.2``, ``2.3.1-global.2`` -> ``2.3.1``): the program
    entry name.  The official version a build is based on is ``UPSTREAM_BASE`` (documents, manifest)."""
    major, minor, patch, _n = parse_global_version(value)
    return f"{major}.{minor}.{patch}"


def installer_asset_name(value: str) -> str:
    """The asset name the in-app updater derives from the release tag (src.app.global_release.installer_name)."""
    return f"NTE_Drive_Calc_{value}_Multilingual_Setup.exe"


def tree_global_version(root: Path) -> str:
    """GLOBAL_VERSION of ``<root>/src/app/global_release.py``: what an executable built from that tree reports."""
    source = root / "src" / "app" / "global_release.py"
    if not source.is_file():
        raise BuildError(f"not a tree root (src/app/global_release.py missing): {root}")
    match = re.search(r'^GLOBAL_VERSION\s*=\s*"([^"]+)"', source.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise BuildError(f"GLOBAL_VERSION not found in {source}")
    return match.group(1)


def tree_upstream_base(root: Path) -> str:
    """``__version__`` of ``<root>/src/app/version.py``: the official version the tree is based on."""
    source = root / "src" / "app" / "version.py"
    if not source.is_file():
        raise BuildError(f"not a tree root (src/app/version.py missing): {root}")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', source.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise BuildError(f"__version__ not found in {source}")
    return match.group(1)


def normalize_notes(text) -> str:
    """The release body as the signed ``notes_sha256`` covers it (identical to src/services/global_update/verify.py
    ``normalize_notes``; unit-tested): line endings -> LF, trailing white space of every line removed, leading /
    trailing blank lines removed."""
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def notes_digest(text) -> str:
    return hashlib.sha256(normalize_notes(text).encode("utf-8")).hexdigest()


def release_manifest(*, version: str, installer_size: int, installer_sha256: str, exe_sha256: str,
                     published_utc: str, min_global_version: str = FIRST_AUTO_UPDATE_VERSION,
                     notes_sha256: str = "") -> dict:
    """The unsigned release manifest (design_final §6.2) the updater verifies after the sshsig signature: it binds
    the tag, the canonical asset name, the installer size and SHA-256 and the executable's SHA-256.
    ``min_global_version`` = the oldest RUNNING Global version that may install this release in-app (older
    builds are told to install it manually); it must not exceed ``version``."""
    minimum = parse_global_version(min_global_version)
    if minimum > parse_global_version(version):
        raise BuildError(f"min_global_version {min_global_version} is newer than the release {version}")
    return {
        "format": MANIFEST_FORMAT, "product": MANIFEST_PRODUCT, "tag": "v" + version, "global_version": version,
        "upstream_base": UPSTREAM_BASE,
        "installer": {"name": installer_asset_name(version), "size": int(installer_size), "sha256": installer_sha256},
        "exe_sha256": exe_sha256, "min_global_version": min_global_version, "published_utc": published_utc,
        "notes_sha256": notes_sha256,
    }


def read_release_public_key(path: Path) -> tuple[str, str]:
    """(key id, "ssh-ed25519 <base64>") of a one-line OpenSSH ed25519 PUBLIC key file.  Only *.pub files are read:
    the private key is never opened by any build step."""
    import base64
    if path.suffix != ".pub":
        raise BuildError(f"refusing to read {path.name}: not a .pub file")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    match = re.fullmatch(r"ssh-ed25519 ([A-Za-z0-9+/=]+)(?: (\S.*))?", lines[0]) if len(lines) == 1 else None
    if match is None:
        raise BuildError(f"{path}: not a one-line ssh-ed25519 public key")
    blob = base64.b64decode(match.group(1), validate=True)
    if len(blob) != 51 or blob[:15] != b"\x00\x00\x00\x0bssh-ed25519" or blob[15:19] != b"\x00\x00\x00\x20":
        raise BuildError(f"{path}: malformed ssh-ed25519 key blob")
    key_id = (match.group(2) or "").strip() or RELEASE_KEY_ID_DEFAULT
    if "test" in key_id.lower():
        raise BuildError(f"{path}: comment {key_id!r} names a test key; a release pins only the real key")
    return key_id, f"ssh-ed25519 {match.group(1)}"


def key_fingerprint(line: str) -> str:
    import base64
    digest = hashlib.sha256(base64.b64decode(line.split()[1])).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def tree_signing_keys(root: Path) -> list[tuple[str, str]]:
    """RELEASE_SIGNING_KEYS of <root>/src/app/global_release.py (literal evaluation, nothing is executed)."""
    import ast
    source = root / "src" / "app" / "global_release.py"
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "RELEASE_SIGNING_KEYS" and node.value is not None:
            return [(str(a), str(b)) for a, b in ast.literal_eval(node.value)]
    raise BuildError(f"RELEASE_SIGNING_KEYS not found in {source}")


def _key_fingerprints_of(paths) -> set[str]:
    result = set()
    for path in paths or ():
        line = Path(path).read_text(encoding="utf-8").split()
        if len(line) >= 2 and line[0] == "ssh-ed25519":
            result.add(key_fingerprint(" ".join(line[:2])))
    return result


def release_exe_gate(*, tree: Path, exe: Path, official_exe: Path | None, payload_data: Path) -> dict:
    """Review r5 F7: the executable that gets packaged must be the one built from ``tree`` (verify_exe_l10n_g231.py
    against the official 2.3.1 exe: every src.* module equals the tree, nothing else changed), and the tree must not
    carry a test hook."""
    hooks = []
    for path in sorted((tree / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        hooks += [f"{path.relative_to(tree).as_posix()}: {marker}" for marker in TEST_HOOK_MARKERS if marker in text]
    if hooks:
        raise BuildError(f"RELEASE GATE: the tree carries test hooks: {hooks[:5]}")
    if official_exe is None or not official_exe.is_file():
        raise BuildError("RELEASE GATE: a release build needs --official-exe <official 2.3.1 NTE_Drive_Calc.exe> "
                         "to verify that --exe was built from --tree")
    catalog_check = subprocess.run(
        [sys.executable, "-c",
         "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
         "from src.integrations.role_catalog_release import read_role_catalog; "
         "read_role_catalog(Path(sys.argv[2]))",
         str(tree), str(payload_data / "role_catalog")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if catalog_check.returncode != 0:
        raise BuildError("RELEASE GATE: the application cannot load the staged character catalog\n"
                         + (catalog_check.stdout + catalog_check.stderr)[-2000:])
    removed = [f"--removed=src.{m.replace('/', '.')}" for m in REMOVABLE_UPSTREAM_MODULES
               if not (tree / "src" / f"{m}.py").is_file()]
    verifier = TOOLS_DIR / "verify_exe_l10n_g231.py"
    completed = subprocess.run([sys.executable, str(verifier), str(official_exe), str(exe), str(tree / "src"), str(payload_data), *removed],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0 or "VERIFY_OK" not in completed.stdout:
        tail = (completed.stdout + completed.stderr)[-2000:]
        raise BuildError(f"RELEASE GATE: --exe was not built from --tree (verify_exe_l10n_g231.py rc="
                         f"{completed.returncode})\n{tail}")
    from elyms_core_bundle import verify_core_bundle

    try:
        core_sha256 = verify_core_bundle(payload_data.parent, official_exe.parent / "_internal")
    except (OSError, ValueError) as exc:
        raise BuildError(f"RELEASE GATE: native Core bundle verification failed: {exc}") from exc
    return {"exe_verified": completed.stdout.strip().splitlines()[-1], "test_hooks": 0,
            "native_core_sha256": core_sha256, "role_catalog_verified": True}


def release_key_gate(tree: Path | None, pubkey: Path, reject_keys=()) -> dict:
    """Release gate (user decision U1, 2026-10-13): the tree the release exe was built from pins EXACTLY the real
    public key of ``pubkey`` (default %USERPROFILE%\\.ssh\\nte_global_release_20261107.pub) in its first slot.  An absent key
    file fails the gate; a test key is never substituted."""
    if tree is None:
        raise BuildError("RELEASE GATE: a release build needs --tree <root> (the tree the exe was built from)")
    if not pubkey.is_file():
        raise BuildError(f"RELEASE GATE: release public key file absent: {pubkey}\n"
                         "  create the key pair yourself (interactive, with a passphrase):\n"
                         "  ssh-keygen -t ed25519 -f %USERPROFILE%\\.ssh\\nte_global_release_20261107 -C nte-global-release-20261107\n"
                         "  then: build_tools/pin_release_key.py <tree root>, rebuild the exe, rebuild the installer")
    key_id, line = read_release_public_key(pubkey)
    pins = tree_signing_keys(tree)
    if not pins:
        raise BuildError(f"RELEASE GATE: {tree} pins no release key (run build_tools/pin_release_key.py {tree})")
    if pins[0][1].split()[:2] != line.split()[:2]:
        raise BuildError(f"RELEASE GATE: the first key pinned by {tree} is not {pubkey.name} "
                         f"({key_fingerprint(pins[0][1])} != {key_fingerprint(line)})")
    if any("test" in key.lower() for key, _ in pins):
        raise BuildError(f"RELEASE GATE: {tree} pins a key whose id names a test key: {[k for k, _ in pins]}")
    rejected = set(KNOWN_TEST_KEY_FINGERPRINTS) | _key_fingerprints_of(reject_keys)
    test_slots = [key_fingerprint(value) for _key, value in pins if key_fingerprint(value) in rejected]
    if test_slots:
        raise BuildError(f"RELEASE GATE: {tree} pins a known TEST key in a slot: {test_slots}")
    return {"key_id": pins[0][0], "fingerprint": key_fingerprint(line), "slots": len(pins)}


def scan_tree(root: Path) -> list[dict]:
    """Every file below root as {path (posix, relative), size, sha256}, sorted case-insensitively."""
    rows = []
    for current, _dirs, files in os.walk(root):
        for name in files:
            full = Path(current) / name
            rows.append({
                "path": full.relative_to(root).as_posix(),
                "size": full.stat().st_size,
                "sha256": sha256_of(full),
            })
    rows.sort(key=lambda row: row["path"].lower())
    return rows


def scan_stage(stage: Path) -> list[dict]:
    rows = [row for row in scan_tree(stage) if row["path"] != STAGE_MANIFEST_NAME]
    lowered = [row["path"].lower() for row in rows]
    if len(set(lowered)) != len(lowered):
        raise BuildError("stage contains paths that differ only by case")
    return rows


def write_stage_manifest(stage: Path) -> Path:
    rows = scan_stage(stage)
    check_stage_layout(stage, rows)
    manifest = {
        "format": 1,
        "description": "Clean payload of the NTE Drive Calc Global installer: what the official installer lays "
                       "down, without the main executable (passed with --exe).",
        "created_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_files": len(rows),
        "total_bytes": sum(row["size"] for row in rows),
        "files": rows,
    }
    target = stage / STAGE_MANIFEST_NAME
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return target


def bundle_layout(internal: Path) -> str:
    """The layout the bundled component manifest declares (upstream's inspection default: native-capture-v1)."""
    data = json.loads((internal / "component-bundle.json").read_text(encoding="utf-8"))
    layout = str(data.get("layout") or LEGACY_CAPTURE_LAYOUT)
    if layout not in KNOWN_LAYOUTS:
        raise BuildError(f"unknown component bundle layout {layout!r}: review upstream's stale-file list first")
    return layout


def stale_install_delete_targets(internal: Path) -> list[str]:
    """Upstream 0e7a6b4 [InstallDelete]: assets/game_ui, the ambient ICU DLLs, and dwmapi.dll only for the
    native-capture-v1 layout (an old installer could leave that game proxy in the application folder)."""
    targets = ["assets/game_ui", *STALE_AMBIENT_ICU_DLLS]
    if bundle_layout(internal) == LEGACY_CAPTURE_LAYOUT:
        targets.append("dwmapi.dll")
    return targets


def catalog_duplicates(internal: Path) -> list[tuple[str, str]]:
    """Upstream prepare_installer_asset_stage(): byte-identical role-catalog images, (donor, omitted) relative to
    _internal, in the same order (sorted paths; the first image of each digest is the donor)."""
    root = internal / CATALOG_IMAGE_ROOT
    if not root.is_dir():
        return []
    first: dict[str, Path] = {}
    copies = []
    for image in sorted(root.rglob("*")):
        if not image.is_file() or image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        digest = sha256_of(image)
        donor = first.get(digest)
        if donor is None:
            first[digest] = image
            continue
        copies.append((donor.relative_to(internal).as_posix(), image.relative_to(internal).as_posix()))
    return copies


def check_stage_layout(stage: Path, rows: list[dict]) -> None:
    """Refuse a polluted stage: only the three official subtrees, no user/runtime data."""
    internal = stage / "_internal"
    problems: list[str] = []
    for row in rows:
        path = row["path"]
        low = path.lower()
        top = low.split("/", 1)[0]
        if top == "_internal":
            continue
        if low == "drivers/" + VIGEM_DEST_NAME.lower():
            continue
        if low in {"config/" + name for name in CORE_CONFIG_FILES}:
            continue
        problems.append(f"unexpected file outside the official payload: {path}")
    for relative in FORBIDDEN_INTERNAL:
        if (internal / relative).exists():
            problems.append(f"user/runtime data in stage: _internal/{relative}")
    for relative in REQUIRED_INTERNAL:
        if not (internal / relative).is_file():
            problems.append(f"missing required runtime file: _internal/{relative}")
    if not (stage / "drivers" / VIGEM_DEST_NAME).is_file():
        problems.append(f"missing drivers/{VIGEM_DEST_NAME}")
    for name in CORE_CONFIG_FILES:
        seed = stage / "config" / name
        source = internal / "config" / name
        if seed.is_file() and source.is_file() and seed.read_bytes() != source.read_bytes():
            problems.append(f"config/{name} differs from _internal/config/{name} (the upstream seed source)")
    if (internal / "component-bundle.json").is_file():
        for target in stale_install_delete_targets(internal):
            if (internal / target).exists():
                problems.append(f"payload contains a path the installer deletes as stale: _internal/{target}")
    if problems:
        raise BuildError("stage is not a clean payload:\n  " + "\n  ".join(problems))


def verify_stage(stage: Path, rows: list[dict]) -> dict:
    """Stage vs stage_manifest.json, bundled component manifest and static database manifests."""
    result = {"stage_manifest": "absent", "component_bundle_files": 0, "static_databases": 0}
    by_path = {row["path"]: row for row in rows}
    manifest_path = stage / STAGE_MANIFEST_NAME
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {row["path"]: row for row in manifest["files"]}
        missing = sorted(set(expected) - set(by_path))
        extra = sorted(set(by_path) - set(expected))
        changed = sorted(
            path for path in set(expected) & set(by_path)
            if expected[path]["size"] != by_path[path]["size"] or expected[path]["sha256"] != by_path[path]["sha256"]
        )
        if missing or extra or changed:
            raise BuildError(
                "stage does not match stage_manifest.json: "
                f"missing={missing[:5]} extra={extra[:5]} changed={changed[:5]} "
                f"(counts {len(missing)}/{len(extra)}/{len(changed)})"
            )
        result["stage_manifest"] = f"verified ({len(expected)} files)"
    else:
        info(f"WARNING: {manifest_path} not found - stage contents are not verified against a manifest")

    internal = stage / "_internal"
    bundle = json.loads((internal / "component-bundle.json").read_text(encoding="utf-8"))
    for relative, digest in bundle.get("files", {}).items():
        row = by_path.get("_internal/" + relative)
        if row is None or row["sha256"].lower() != str(digest).lower():
            raise BuildError(f"component-bundle.json hash mismatch: {relative}")
    result["component_bundle_files"] = len(bundle.get("files", {}))
    result["component_bundle_layout"] = bundle_layout(internal)

    analysis = json.loads((internal / "analysis-core-meta" / "component.json").read_text(encoding="utf-8"))
    if by_path["_internal/nte-analysis-core.exe"]["sha256"].lower() != str(analysis.get("sha256", "")).lower():
        raise BuildError("analysis-core-meta/component.json hash mismatch: nte-analysis-core.exe")

    for manifest_rel in ("data/manifest.json", "data/role_catalog/manifest.json"):
        path = internal / manifest_rel
        if not path.is_file():
            continue
        database = json.loads(path.read_text(encoding="utf-8")).get("database", {})
        db_rel = "_internal/" + str(Path(manifest_rel).parent.as_posix()) + "/" + str(database.get("filename"))
        row = by_path.get(db_rel)
        if row is None or row["size"] != database.get("size_bytes") or row["sha256"].lower() != str(database.get("sha256", "")).lower():
            raise BuildError(f"static database does not match {manifest_rel}: {db_rel}")
        result["static_databases"] += 1
    return result


def find_iscc(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise BuildError(f"Inno Setup compiler not found: {explicit}")
        return explicit
    candidates = [
        os.environ.get("INNO_SETUP_ISCC"),
        shutil.which("ISCC.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise BuildError("Inno Setup 6 compiler (ISCC.exe) not found; pass --iscc or set INNO_SETUP_ISCC")


def _write_text(path: Path, text: str, *, bom: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n").replace("\n", "\r\n")
    path.write_text(data, encoding="utf-8-sig" if bom else "utf-8", newline="")


def _check_inno_value(value: str) -> str:
    if '"' in value or "\n" in value:
        raise BuildError(f"value cannot be used in the Inno script: {value!r}")
    return value


def custom_message_lines(version: str, sandbox: bool) -> str:
    lines = []
    for key, table in CUSTOM_MESSAGES.items():
        for lang in LANGS:
            # the program entry name carries major.minor.patch (no churn per -global.<n>); DisplayVersion the full one
            text = table[lang].format(version=base_version(version) if key == "L10nAppVerName" else version)
            if key == "L10nAppVerName" and sandbox:
                text += " [sandbox]"
            if key in ICON_MESSAGE_KEYS and any(ch in text for ch in '\\/:*?"<>|'):
                raise BuildError(f"shortcut name contains a character not allowed in file names: {text!r}")
            lines.append(f"{lang}.{key}={text}")
    return "\n".join(lines)


def stale_shortcut_delete_lines(sandbox: bool) -> str:
    """Remove this product's shortcuts created under another wizard language (incl. the official
    Chinese names), so an upgrade never leaves two differently named copies in the Start menu."""
    keys = ("UninstallIconName",) if sandbox else ICON_MESSAGE_KEYS
    lines = []
    for key in keys:
        for lang in LANGS:
            others = " ".join(other for other in LANGS if CUSTOM_MESSAGES[key][other] != CUSTOM_MESSAGES[key][lang])
            if others:
                lines.append(
                    f'Type: files; Name: "{{group}}\\{CUSTOM_MESSAGES[key][lang]}.lnk"; Languages: {others}'
                )
    return "\n".join(lines)


def asset_copy_lines(internal: Path, copies: list[tuple[str, str]]) -> str:
    """Upstream inno_asset_copy_lines(): one stored image, a second Inno-managed installed path."""
    lines = []
    for donor, omitted in copies:
        source = internal / donor
        dest = Path(omitted)
        for value in (str(source), omitted):
            if '"' in value or ";" in value or "," in value:
                raise BuildError(f"asset path contains an Inno script separator: {value!r}")
        parent = str(dest.parent).replace("/", "\\")
        lines.append(
            f'Source: "{source}"; DestDir: "{{app}}\\_internal\\{parent}"; DestName: "{dest.name}"; Flags: ignoreversion'
        )
    return "\n".join(lines)


def build_iss(*, variant: str, version: str, exe: Path, stage: Path, out_dir: Path, build_dir: Path,
              compression: str, icon: Path | None, sandbox_dir: str, output_base: str,
              copies: list[tuple[str, str]]) -> str:
    sandbox = variant == "sandbox"
    app_name = APP_NAME + (" (sandbox)" if sandbox else "")
    app_id = SANDBOX_APP_ID if sandbox else OFFICIAL_APP_ID
    default_dir = sandbox_dir if sandbox else "{autopf}\\NTE Drive Calc"
    privileges = "lowest" if sandbox else "admin"
    internal = stage / "_internal"
    vigem_file = f"{{app}}\\drivers\\{VIGEM_DEST_NAME}"
    numeric_version = windows_numeric_version(version)
    setup_icon_line = f"SetupIconFile={icon}\n" if icon else ""

    languages = "\n".join(
        'Name: "{lang}"; MessagesFile: "{messages}"; InfoBeforeFile: "{notice}"'.format(
            lang=lang,
            messages=MESSAGES_FILES[lang].format(zh_isl=build_dir / "ChineseSimplified.overrides.isl"),
            notice=build_dir / f"notice_{lang}.txt",
        )
        for lang in LANGS
    )
    tasks = ['Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"']
    if not sandbox:
        tasks.append(
            'Name: "installvigem"; Description: "{cm:ViGEmTask}"; GroupDescription: "{cm:RuntimeDepsGroup}"; '
            "Flags: checkedonce"
        )
    excludes = ",".join("\\" + omitted.replace("/", "\\") for _donor, omitted in copies)
    if '"' in excludes:
        raise BuildError("Excludes list contains a quote")
    excludes_part = f'; Excludes: "{excludes}"' if excludes else ""
    config_lines = "\n".join(
        f'Source: "{internal / "config" / name}"; DestDir: "{{app}}\\config"; Flags: ignoreversion'
        for name in CORE_CONFIG_FILES
    )
    docs_lines = "\n".join(
        f'Source: "{build_dir / "docs" / name}"; DestDir: "{{app}}\\{DOCS_DIR_NAME}"; Flags: ignoreversion'
        for name in ("LICENSE.txt", "README.txt", "SOURCE_OFFER.txt")
    )
    stale_runtime_delete_lines = "\n".join(
        (f'Type: filesandordirs; Name: "{{app}}\\_internal\\{target}"' if "/" in target
         else f'Type: files; Name: "{{app}}\\_internal\\{target}"').replace("/", "\\")
        for target in stale_install_delete_targets(internal)
    )
    icons = [f'Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; WorkingDir: "{{app}}"']
    if not sandbox:
        icons.append(
            f'Name: "{{group}}\\{{cm:ViGEmIconName}}"; Filename: "{vigem_file}"; Parameters: "{VIGEM_PARAMS}"; '
            'WorkingDir: "{app}"; Check: IsWin64'
        )
    icons.append('Name: "{group}\\{cm:UninstallIconName}"; Filename: "{uninstallexe}"')
    icons.append(
        'Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; WorkingDir: "{app}"; '
        "Tasks: desktopicon"
    )
    run = []
    if not sandbox:
        run.append(
            f'Filename: "{vigem_file}"; Parameters: "{VIGEM_PARAMS}"; StatusMsg: "{{cm:StatusInstallViGEm}}"; '
            "Flags: waituntilterminated; Tasks: installvigem; Check: ShouldInstallViGEmBus"
        )
        run.append(
            'Filename: "{cmd}"; Parameters: "/C sc start ViGEmBus >NUL 2>NUL & exit /B 0"; '
            'StatusMsg: "{cm:StatusStartViGEm}"; Flags: runhidden waituntilterminated; Tasks: installvigem; '
            "Check: IsWin64"
        )
    # In-app update (design_final §9): the program's own updater runs Setup silently with /AUTOUPDATE=1 /RELAUNCH=1
    # and this entry restarts it; a wizard install (not silent) or /RELAUNCH=0 (install on exit) never triggers it.
    run.append(
        'Filename: "{app}\\{#MyAppExeName}"; WorkingDir: "{app}"; Flags: nowait runascurrentuser; '
        "Check: ShouldRelaunchAfterAutoUpdate"
    )
    run.append(
        'Filename: "{app}\\{#MyAppExeName}"; '
        "Description: \"{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}\"; "
        "Flags: nowait postinstall skipifsilent runascurrentuser"
    )
    relaunch_code = """\
function ShouldRelaunchAfterAutoUpdate: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:AUTOUPDATE|0}') = '1') and
    (ExpandConstant('{param:RELAUNCH|1}') = '1');
end;

"""
    vigem_code = "" if sandbox else """\
function ShouldInstallViGEmBus: Boolean;
begin
  Result := IsWin64 and WizardIsTaskSelected('installvigem');
end;

"""
    for value in (str(exe), str(stage), str(out_dir), str(build_dir), default_dir, output_base, compression):
        _check_inno_value(value)

    return f"""; Generated by build_installer_g231.py ({variant}). Do not edit by hand.
; Port of the official build_installer.py script (upstream commit {UPSTREAM_COMMIT[:7]}).
#define MyAppName "{app_name}"
#define MyAppVersion "{version}"
#define MyAppPublisher "{PUBLISHER}"
#define MyAppExeName "{APP_EXE_NAME}"

[Setup]
AppId={{{{{app_id}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{cm:L10nAppVerName}}
VersionInfoVersion={numeric_version}
VersionInfoProductVersion={numeric_version}
VersionInfoTextVersion={{#MyAppVersion}}
VersionInfoProductTextVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppCopyright=GNU AGPL-3.0. Original work: NTE Drive Calc contributors
VersionInfoDescription={app_name} {version} multilingual edition (NTE Drive Calc Global, unofficial) setup
VersionInfoProductName={app_name} Global (unofficial multilingual edition)
VersionInfoCopyright=GNU AGPL-3.0. Original work: NTE Drive Calc contributors
DefaultDirName={default_dir}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={out_dir}
OutputBaseFilename={output_base}
Compression={compression}
SolidCompression=yes
WizardStyle=modern
{setup_icon_line}PrivilegesRequired={privileges}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}
CloseApplications=yes
CloseApplicationsFilter={CLOSE_APPLICATIONS_FILTER}
ShowLanguageDialog=yes
UsePreviousLanguage=yes

[Languages]
{languages}

[CustomMessages]
{custom_message_lines(version, sandbox)}

[Tasks]
{chr(10).join(tasks)}

[Files]
Source: "{exe}"; DestDir: "{{app}}"; DestName: "{APP_EXE_NAME}"; Flags: ignoreversion
Source: "{internal}\\*"; DestDir: "{{app}}\\_internal"{excludes_part}; Flags: ignoreversion recursesubdirs createallsubdirs
{asset_copy_lines(internal, copies)}
{config_lines}
Source: "{stage / "drivers" / VIGEM_DEST_NAME}"; DestDir: "{{app}}\\drivers"; DestName: "{VIGEM_DEST_NAME}"; Flags: ignoreversion
{docs_lines}

[InstallDelete]
Type: files; Name: "{{app}}\\_internal\\data\\role_catalog\\game_ui\\character_arts\\1090.webp"
{stale_runtime_delete_lines}
{stale_shortcut_delete_lines(sandbox)}

[UninstallDelete]
Type: files; Name: "{{app}}\\_internal\\config\\i18n_language.json"
Type: filesandordirs; Name: "{{app}}\\updates"

[Dirs]
Name: "{{app}}\\config"; Permissions: users-modify
Name: "{{app}}\\_internal\\data"; Permissions: users-modify
Name: "{{app}}\\migration"; Permissions: users-modify
Name: "{{app}}\\logs"; Permissions: users-modify
Name: "{{app}}\\scanned_images"; Permissions: users-modify

[Icons]
{chr(10).join(icons)}

[Run]
{chr(10).join(run)}

[Code]
{relaunch_code}{vigem_code}procedure WriteInitialLanguage;
var
  ConfigDir: String;
  LanguageFile: String;
begin
  // The wizard language names are the application's language codes (en / ko / ja / zh).
  // An existing language file (an earlier choice in the program or in an earlier installer) is never changed.
  ConfigDir := ExpandConstant('{{app}}\\_internal\\config');
  LanguageFile := ConfigDir + '\\i18n_language.json';
  if FileExists(LanguageFile) or not DirExists(ConfigDir) then
    Exit;
  SaveStringToFile(LanguageFile, #123 + '"language": "' + ActiveLanguage + '"' + #125, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OldStaticDatabase: String;
  MigrationBackup: String;
begin
  if CurStep = ssPostInstall then
  begin
    WriteInitialLanguage;
    Exit;
  end;
  if CurStep <> ssInstall then
    Exit;
  OldStaticDatabase :=
    ExpandConstant('{{app}}\\_internal\\data\\game_static.sqlite3');
  MigrationBackup :=
    ExpandConstant('{{app}}\\migration\\game_static.previous.sqlite3');
  if FileExists(OldStaticDatabase) then
  begin
    ForceDirectories(ExtractFileDir(MigrationBackup));
    if not CopyFile(OldStaticDatabase, MigrationBackup, False) then
      RaiseException(CustomMessage('MigrationBackupFailed'));
  end;
end;
"""


def doc_fields(*, version: str, exe_sha256: str, source_zip_name: str) -> dict:
    """``version`` in the documents is the upstream base (what the program is a build *of*: UPSTREAM_BASE);
    ``global_version`` is this build's own version."""
    return dict(version=UPSTREAM_BASE, global_version=version, docs=DOCS_DIR_NAME, source_zip=source_zip_name,
                exe_name=APP_EXE_NAME, exe_sha256=exe_sha256, upstream_url=UPSTREAM_URL, upstream_commit=UPSTREAM_COMMIT,
                project_url=PROJECT_URL, releases_url=PROJECT_URL + "/releases")


def render_source_offer(*, version: str, exe_sha256: str, source_zip_name: str) -> str:
    """The text installed as {app}\\l10n_build\\SOURCE_OFFER.txt (LF line ends; written with CRLF + BOM)."""
    return SOURCE_OFFER.format(**doc_fields(version=version, exe_sha256=exe_sha256, source_zip_name=source_zip_name))


def write_support_files(*, build_dir: Path, version: str, license_path: Path, exe_sha256: str,
                        source_zip_name: str) -> list[Path]:
    zh_isl = (
        "; Generated by build_installer_g231.py - Simplified Chinese overrides on top of Default.isl.\n"
        "; [Messages] / [CustomMessages] are ported from the official build_installer.py.\n"
        "[LangOptions]\nLanguageName=简体中文\nLanguageID=$0804\nLanguageCodePage=936\n\n"
        "[Messages]\n" + ZH_MESSAGES_UPSTREAM + ZH_MESSAGES_EXTRA + "\n"
        "[CustomMessages]\n" + ZH_CUSTOM_MESSAGES_UPSTREAM
    )
    _write_text(build_dir / "ChineseSimplified.overrides.isl", zh_isl)
    fields = doc_fields(version=version, exe_sha256=exe_sha256, source_zip_name=source_zip_name)
    for lang in LANGS:
        _write_text(build_dir / f"notice_{lang}.txt", NOTICE[lang].format(**fields))
    docs = build_dir / "docs"
    license_text = license_path.read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text[:400]:
        raise BuildError(f"{license_path} does not look like the AGPL license text")
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(license_path, docs / "LICENSE.txt")          # verbatim copy of the upstream LICENSE
    _write_text(docs / "README.txt", README.format(**fields))
    _write_text(docs / "SOURCE_OFFER.txt", SOURCE_OFFER.format(**fields))
    return [docs / "LICENSE.txt", docs / "README.txt", docs / "SOURCE_OFFER.txt"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the NTE Drive Calc Global installer.")
    parser.add_argument("--exe", type=Path, help="our rebuilt NTE_Drive_Calc.exe (any file name)")
    parser.add_argument("--stage", type=Path, required=True, help="clean payload directory")
    parser.add_argument("--out", type=Path, help="output directory")
    parser.add_argument("--variant", choices=("release", "sandbox"))
    parser.add_argument("--version", default=DEFAULT_VERSION,
                        help="Global version <major>.<minor>.<patch>[-global.<n>], newer than "
                             f"{PREVIOUS_RELEASE_VERSION} (default %(default)s)")
    parser.add_argument("--tree", type=Path, default=None,
                        help="source tree root; its src/app/global_release.py GLOBAL_VERSION must equal --version")
    parser.add_argument("--emit-manifest", action="store_true",
                        help="also write the unsigned release manifest NTE_Drive_Calc_<version>_release.json into --out")
    parser.add_argument("--notes", type=Path, default=None,
                        help="manifest: the release body (Markdown, exactly what the GitHub release will show); its "
                             "normalised SHA-256 is signed with the manifest (required for a release manifest)")
    parser.add_argument("--official-exe", type=Path, default=None,
                        help="release gate: the official 2.3.1 NTE_Drive_Calc.exe (verifies that --exe was built from --tree)")
    parser.add_argument("--reject-key", type=Path, action="append", default=[],
                        help="release gate: a test PUBLIC key that no release may pin (repeatable)")
    parser.add_argument("--min-global-version", default=FIRST_AUTO_UPDATE_VERSION,
                        help="manifest: oldest running Global version allowed to install this release in-app "
                             "(default %(default)s)")
    parser.add_argument("--release-pubkey", type=Path, default=RELEASE_PUBKEY_DEFAULT,
                        help="release gate: the real release-signing PUBLIC key the --tree must pin "
                             "(default %%USERPROFILE%%\\.ssh\\nte_global_release_20261107.pub)")
    parser.add_argument("--iscc", type=Path, default=None, help="path to ISCC.exe (else INNO_SETUP_ISCC / default install)")
    parser.add_argument("--compression", default="lzma2/ultra64",
                        help="Inno Compression value (official: lzma2/ultra64; lzma2/fast for quick dry runs)")
    parser.add_argument("--license", type=Path, default=DEFAULT_LICENSE, help="AGPL LICENSE file to ship")
    parser.add_argument("--source-zip-name", default=None,
                        help="file name of the source zip shipped next to the installer (named in the notices)")
    parser.add_argument("--sandbox-dir", default=SANDBOX_DEFAULT_DIR, help="default directory of the sandbox variant")
    parser.add_argument("--output-base", default=None,
                        help="installer file name without .exe (default NTE_Drive_Calc_<version>_Multilingual_Setup[_sandbox])")
    parser.add_argument("--aux-dir", type=Path, default=None,
                        help="directory for build_<variant>/, the payload manifest and the build report (default: --out)")
    parser.add_argument("--generate-only", action="store_true", help="write the .iss and support files, skip ISCC")
    parser.add_argument("--write-stage-manifest", action="store_true",
                        help=f"write <stage>/{STAGE_MANIFEST_NAME} from the current stage contents and exit")
    args = parser.parse_args()

    try:
        stage = args.stage.resolve()
        if not stage.is_dir():
            raise BuildError(f"stage directory not found: {stage}")
        if "program files" in str(stage).lower():
            raise BuildError("the stage must be a copy, not the installed program folder")
        if args.write_stage_manifest:
            target = write_stage_manifest(stage)
            manifest = json.loads(target.read_text(encoding="utf-8"))
            info(f"wrote {target}: {manifest['total_files']} files, {manifest['total_bytes']} bytes")
            return 0
        if not (args.exe and args.out and args.variant):
            parser.error("--exe, --out and --variant are required unless --write-stage-manifest is used")

        exe = args.exe.resolve()
        out_dir = args.out.resolve()
        if not exe.is_file() or exe.read_bytes()[:2] != b"MZ":
            raise BuildError(f"not a Windows executable: {exe}")
        if "program files" in str(out_dir).lower():
            raise BuildError("refusing to write under Program Files")
        license_path = args.license.resolve()
        if not license_path.is_file():
            raise BuildError(f"LICENSE file not found: {license_path} (pass --license)")
        version = args.version
        parse_global_version(version)
        require_newer_than_previous(version)
        if args.tree is not None:
            tree_version = tree_global_version(args.tree.resolve())
            if tree_version != version:
                raise BuildError(f"--version {version} does not match GLOBAL_VERSION {tree_version!r} of {args.tree}")
            tree_base = tree_upstream_base(args.tree.resolve())
            if tree_base != UPSTREAM_BASE:
                raise BuildError(f"src/app/version.py of {args.tree} is {tree_base!r}, not the upstream base {UPSTREAM_BASE}")
        source_zip_name = args.source_zip_name or f"NTE_Drive_Calc_{version}_Multilingual_source.zip"
        aux_dir = (args.aux_dir or out_dir).resolve()
        if "program files" in str(aux_dir).lower():
            raise BuildError("refusing to write under Program Files")
        build_dir = aux_dir / f"build_{args.variant}"
        output_base = args.output_base or (
            installer_asset_name(version)[:-4] + ("_sandbox" if args.variant == "sandbox" else ""))
        if not output_base.strip() or any(ch in output_base for ch in '\\/:*?"<>|') or output_base.lower().endswith(".exe"):
            raise BuildError(f"--output-base must be a plain file name without extension: {output_base!r}")
        if args.variant == "release" and output_base.lower().endswith("_sandbox"):
            raise BuildError("a release build must not carry the sandbox file name")
        if args.variant == "sandbox" and not output_base.lower().endswith("_sandbox"):
            raise BuildError("a sandbox build's file name must end with _sandbox")
        setup_path = out_dir / f"{output_base}.exe"

        info(f"variant={args.variant} version={version}")
        info("hashing stage ...")
        rows = scan_stage(stage)
        check_stage_layout(stage, rows)
        verification = verify_stage(stage, rows)
        copies = catalog_duplicates(stage / "_internal")
        verification["catalog_image_copies"] = [list(pair) for pair in copies]
        exe_sha256 = sha256_of(exe)
        info(f"stage ok: {len(rows)} files, {sum(r['size'] for r in rows)} bytes; layout "
             f"{verification['component_bundle_layout']}; {len(copies)} catalog image copies")
        info(f"exe: {exe} sha256={exe_sha256}")

        out_dir.mkdir(parents=True, exist_ok=True)
        aux_dir.mkdir(parents=True, exist_ok=True)
        docs = write_support_files(build_dir=build_dir, version=version, license_path=license_path,
                                   exe_sha256=exe_sha256, source_zip_name=source_zip_name)
        icon = stage / "_internal" / "assets" / "app_icon.ico"
        iss_text = build_iss(variant=args.variant, version=version, exe=exe, stage=stage, out_dir=out_dir,
                             build_dir=build_dir, compression=args.compression,
                             icon=icon if icon.is_file() else None, sandbox_dir=args.sandbox_dir,
                             output_base=output_base, copies=copies)
        iss_path = build_dir / "setup.iss"
        _write_text(iss_path, iss_text)
        info(f"wrote {iss_path}")

        # Everything the installer lays down under {app} (the uninstaller and the language file
        # written by [Code] are created at install time and therefore not listed).
        installed = [{"path": APP_EXE_NAME, "size": exe.stat().st_size, "sha256": exe_sha256}]
        installed += [row for row in rows if row["path"].startswith("_internal/")]
        installed += [row for row in rows if row["path"].lower() == "drivers/" + VIGEM_DEST_NAME.lower()]
        by_path = {row["path"]: row for row in rows}
        for name in CORE_CONFIG_FILES:
            source = by_path[f"_internal/config/{name}"]
            installed.append({"path": f"config/{name}", "size": source["size"], "sha256": source["sha256"]})
        for doc in docs:
            installed.append({"path": f"{DOCS_DIR_NAME}/{doc.name}", "size": doc.stat().st_size, "sha256": sha256_of(doc)})
        installed.sort(key=lambda row: row["path"].lower())
        payload_manifest = {
            "format": 1,
            "variant": args.variant,
            "version": version,
            "app_id": SANDBOX_APP_ID if args.variant == "sandbox" else OFFICIAL_APP_ID,
            "generated_at_install": [LANGUAGE_FILE_REL, "unins000.exe", "unins000.dat"],
            "stale_deletes": stale_install_delete_targets(stage / "_internal"),
            "total_files": len(installed),
            "total_bytes": sum(row["size"] for row in installed),
            "files": installed,
        }
        payload_manifest_path = aux_dir / f"payload_manifest_{args.variant}.json"
        payload_manifest_path.write_text(json.dumps(payload_manifest, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
        info(f"wrote {payload_manifest_path} ({len(installed)} files)")

        key_gate = None
        if args.variant == "release":
            if args.generate_only:
                info("generate-only: release key gate not evaluated (it runs before every ISCC release build)")
            else:
                key_gate = release_key_gate(args.tree.resolve() if args.tree is not None else None,
                                            args.release_pubkey.expanduser().resolve(), args.reject_key)
                info(f"release key gate: tree pins {key_gate['key_id']} {key_gate['fingerprint']}")
                key_gate.update(release_exe_gate(tree=args.tree.resolve(), exe=exe,
                                                 official_exe=args.official_exe.resolve() if args.official_exe else None,
                                                 payload_data=stage / "_internal" / "data"))
                info(f"release exe gate: {key_gate['exe_verified']}")
            if args.emit_manifest and args.notes is None:
                raise BuildError("a release manifest needs --notes <release body .md> (the signed notes digest)")
        parse_global_version(args.min_global_version)
        notes_sha256 = ""
        if args.notes is not None:
            if not args.notes.is_file():
                raise BuildError(f"--notes file not found: {args.notes}")
            notes_sha256 = notes_digest(args.notes.read_bytes().decode("utf-8"))
            info(f"release notes {args.notes.name}: notes_sha256={notes_sha256}")
        if args.generate_only:
            info("generate-only: skipped ISCC")
            return 0

        iscc = find_iscc(args.iscc)
        log_path = build_dir / "iscc.log"
        info(f"running {iscc} (compression {args.compression}) ...")
        started = time.monotonic()
        with log_path.open("wb") as log:
            completed = subprocess.run([str(iscc), "/Q", str(iss_path)], stdout=log, stderr=subprocess.STDOUT, check=False)
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            tail = log_path.read_bytes()[-3000:].decode("mbcs", "replace")
            raise BuildError(f"ISCC failed with exit code {completed.returncode}; see {log_path}\n{tail}")
        if not setup_path.is_file():
            raise BuildError(f"ISCC finished but the installer was not found: {setup_path}")
        report = {
            "variant": args.variant,
            "version": version,
            "global_version": version,
            "tag": "v" + version,
            "upstream_base": UPSTREAM_BASE,
            "asset_name": installer_asset_name(version),
            "installer": str(setup_path),
            "installer_size": setup_path.stat().st_size,
            "installer_sha256": sha256_of(setup_path),
            "compile_seconds": round(elapsed, 1),
            "compression": args.compression,
            "iscc": str(iscc),
            "exe": str(exe),
            "exe_sha256": exe_sha256,
            "stage": str(stage),
            "stage_verification": verification,
            "payload_files": len(installed),
            "payload_bytes": payload_manifest["total_bytes"],
            "source_zip_name": source_zip_name,
            "built_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "release_key": key_gate,
        }
        if args.emit_manifest:
            # The manifest names the canonical asset (what the app derives from the tag).  A sandbox build is
            # published under that name only on a test server; the release build's file name already equals it.
            manifest = release_manifest(version=version, installer_size=report["installer_size"],
                                        installer_sha256=report["installer_sha256"], exe_sha256=exe_sha256,
                                        published_utc=report["built_utc"],
                                        min_global_version=args.min_global_version, notes_sha256=notes_sha256)
            manifest_path = out_dir / f"NTE_Drive_Calc_{version}_release.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                     encoding="utf-8", newline="\n")
            report["manifest"] = str(manifest_path)
            info(f"wrote {manifest_path} (unsigned)")
            info("sign it (maintainer, interactive; the passphrase is typed by you):")
            info(f"  ssh-keygen -Y sign -f %USERPROFILE%\\.ssh\\nte_global_release_20261107 -n {RELEASE_SIG_NAMESPACE} {manifest_path.name}")
        report_path = aux_dir / f"build_report_{args.variant}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        info(f"installer: {setup_path}")
        info(f"size={report['installer_size']} sha256={report['installer_sha256']} compile={report['compile_seconds']}s")
        return 0
    except BuildError as exc:
        print(f"[installer-g231] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
