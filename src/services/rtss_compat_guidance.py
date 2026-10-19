# RTSS 호환성 안내 문구와 환경 검사 항목 (NTE Drive Calc Global 추가 모듈)
"""User-facing texts of the read-only RTSS compatibility check and its environment-check item.

Every text is built at call time (``_L`` / ``_LF`` inside functions, never module constants) so a live language
switch re-renders it.  RTSS has no ko/ja/zh UI (its translations cover other languages only), so its labels are
quoted in English, with a translation in parentheses.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from src.domain.work_mode import CheckState, FeatureCheck
from src.services.rtss_compat import (
    REASON_NOT_INSTALLED, REASON_NOT_RUNNING, SOURCE_APP, SOURCE_DEFAULT, SOURCE_GLOBAL, STATUS_OK, STATUS_RISK,
    RtssCompatResult,
)

RTSS_FEATURE = "rtss_compat"
GAME_BINARIES_SUFFIX = r"\Client\WindowsNoEditor\HT\Binaries\Win64"


def game_binaries_folder(game_executable: str | None) -> str:
    """Folder that holds HTGame.exe: the configured one, else the generic layout under the game folder."""
    raw = str(game_executable or "").strip().strip('"')
    if raw and Path(raw).name.casefold() == "htgame.exe":
        return str(Path(raw).parent)
    return _L('<游戏安装目录>') + GAME_BINARIES_SUFFIX


def rtss_feature_label() -> str:
    return _L('RTSS（RivaTuner）兼容性')


def rtss_risk_summary() -> str:
    return _L('RivaTuner Statistics Server（RTSS）正在运行，且 HTGame.exe 未启用 Microsoft Detours 挂钩。RTSS 默认的挂钩方式会与 Calc 注入游戏的组件冲突：游戏可能在启动时崩溃，并显示 D3D12 错误 80004004（E_ABORT）。')


def rtss_fix_steps(game_executable: str | None) -> list[str]:
    return [
        _L('1. 从通知区域（任务栏右端，可能收在 ^ 里）的 RivaTuner Statistics Server 图标打开 RTSS 窗口。'),
        _LF('2. 点击“Add”（添加），选择以下文件夹中的 HTGame.exe（列表中已有 HTGame.exe 时跳过此步）：\n{0}').format(game_binaries_folder(game_executable)),
        _L('3. 确认应用程序列表中选中的是“HTGame.exe”，而不是“Global”。'),
        _L('4. 点击“Setup”（设置），在“General”（常规）选项卡中勾选“Use Microsoft Detours API hooking”（使用 Microsoft Detours API 挂钩），然后点击“OK”保存。'),
        _L('5. 启动游戏（如果游戏已在运行，请先完全退出再重新启动）。'),
    ]


def rtss_alternative_text() -> str:
    return _L('另一种做法：选中“HTGame.exe”（不要选“Global”）后，把“Application detection level”（应用程序检测级别）设为“None”；但这样游戏中不会显示 RTSS 叠加层。')


def rtss_fix_text(game_executable: str | None) -> str:
    """Header + numbered steps + scope note + alternative, as plain text."""
    return "\n".join([
        _L('解决方法（只需设置一次）：'),
        *rtss_fix_steps(game_executable),
        _L('此设置只作用于 HTGame.exe，其他游戏的 RTSS 设置不变。Calc 只读取 RTSS 设置，不会修改。'),
        rtss_alternative_text(),
    ])


def _source_label(source: str) -> str:
    if source == SOURCE_APP:
        return SOURCE_APP
    if source == SOURCE_GLOBAL:
        return SOURCE_GLOBAL
    if source == SOURCE_DEFAULT:
        return _L('RTSS 默认值')
    return source or "?"


def rtss_evidence(result: RtssCompatResult) -> str:
    """One line of language-light evidence (file names and raw values stay as RTSS writes them)."""
    profile = _L('有（HTGame.exe.cfg）') if result.app_profile_present else _L('无（使用 Global 配置）')
    return _LF('RTSS 文件夹：{0}；HTGame.exe 专用配置：{1}；UseDetours={2}（{3}）；EnableHooking={4}（{5}）').format(
        result.install_dir or "?", profile,
        "?" if result.use_detours is None else result.use_detours, _source_label(result.use_detours_source),
        "?" if result.enable_hooking is None else result.enable_hooking, _source_label(result.enable_hooking_source),
    )


def rtss_recheck_message(result: RtssCompatResult) -> tuple[str, str]:
    """(tone, text) after "check again": tone is ok | risk | unknown."""
    if result.status == STATUS_OK:
        if result.reason in {REASON_NOT_RUNNING, REASON_NOT_INSTALLED}:
            return "ok", _L('已确认：RTSS 当前未运行，现在不会冲突。若之后启动 RTSS，请先完成上述设置。')
        return "ok", _L('已确认：RTSS 当前设置不会与 Calc 组件冲突，可以继续。')
    if result.status == STATUS_RISK:
        return "risk", _L('仍检测到冲突设置：HTGame.exe 尚未启用 “Use Microsoft Detours API hooking”。请在 RTSS 中点击 “OK” 保存后再检查。')
    return "unknown", _LF('无法读取 RTSS 设置（{0}），本次不能确认。').format(result.detail or result.reason)


def rtss_feature_check(result: RtssCompatResult | None, *, game_executable: str | None) -> FeatureCheck | None:
    """Environment-check item for a 'risk' result only; advisory, so it never blocks readiness or sync enabling."""
    if result is None or result.status != STATUS_RISK:
        return None
    detail = (
        rtss_risk_summary() + "\n" + rtss_fix_text(game_executable) + "\n"
        + _LF('设置完成后点击“{0}”确认。').format(_L('重新检测'))
        + _L('\n诊断：') + rtss_evidence(result)
    )
    return FeatureCheck(
        RTSS_FEATURE, rtss_feature_label(), CheckState.WARNING, detail, ("recheck",),
        (("advisory", True),) + result.facts(),
    )
