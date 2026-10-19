# Global 업데이트 화면 문구: 오류 코드 → 사용자 문장, 시간/용량/기간 표기 (순수 렌더링 도우미)
"""User-facing sentences of the Global updater (design_final §11, §12; review r5 L5 / M3 / M6 / M10 / L4).

Error **codes** are plain ASCII constants that are never wrapped and never shown as the sentence: every code has a
sentence of its own (the code itself only appears in a tooltip).  Every function is pure so the dialog, the settings
card and the home banner render the same words.
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import datetime as _dt
import html

from PySide6.QtCore import QDateTime, Qt, QTimeZone

from src.app.global_release import GLOBAL_VERSION, parse_global_version, repo_url_allowed
from src.services.global_update.state import parse_utc


def local_time_text(utc_text: object) -> str:
    """``2026-10-12T01:02:03Z`` -> ``2026-10-12 10:02`` in the local time zone; one language-neutral format for every
    UI language (review r5 M10: never the Windows locale's words); "" for anything else."""
    moment = parse_utc(utc_text)
    if moment is None:
        return ""
    qt_moment = QDateTime.fromSecsSinceEpoch(int(moment.timestamp()), QTimeZone.utc()).toLocalTime()
    return qt_moment.toString("yyyy-MM-dd HH:mm")


def mb_text(size: object) -> str:
    try:
        return f"{int(size) / (1024 * 1024):.1f}"
    except (TypeError, ValueError):
        return "0.0"


def duration_text(seconds: object) -> str:
    try:
        total = max(0, int(seconds))
    except (TypeError, ValueError):
        total = 0
    if total < 90:
        return _LF('{0} 秒').format((total))
    return _LF('{0} 分钟').format((max(1, round(total / 60))))


def clock_text(utc_text: object) -> str:
    moment = parse_utc(utc_text)
    if moment is None:
        return "--:--"
    return moment.astimezone().strftime("%H:%M")


def _tail(code: str) -> str:
    return code.split(".", 1)[1] if "." in code else code


def kind_sentence(code: str, detail: str = "", retry_after_utc: str = "") -> str:
    """The short reason shown inside ``检查更新失败（…）`` and ``下载失败：…`` (never the raw code)."""
    code = str(code or "")
    tail = _tail(code)
    if tail == "network":
        return _L('无法连接到 GitHub')
    if tail == "timeout":
        return _L('连接超时')
    if tail == "tls":
        return _L('安全连接失败，请检查系统时间与证书')
    if tail == "ratelimit":
        if parse_utc(retry_after_utc) is None:
            return _L('GitHub 请求次数已达上限，请稍后重试')
        return _LF('GitHub 请求次数已达上限，{0} 后可重试').format((clock_text(retry_after_utc)))
    if tail.startswith("http_"):
        status = tail[5:]
        return _L('GitHub 服务暂时不可用') if status.startswith("5") else _L('服务器响应无效')
    if tail == "invalid_response":
        return _L('服务器响应无效')
    if tail == "no_release":
        return _L('没有可用的 Global 发布')
    if tail in ("untrusted_release", "redirect_refused") or code.startswith("verify."):
        return _L('发布未通过安全校验')
    if tail == "busy":
        return _L('另一个窗口正在更新。')
    if tail == "io":
        return _L('保存文件时出错')
    return _L('发生未知错误')


def manual_install_sentence(minimum: str) -> str:
    version = minimum if parse_global_version(minimum) is not None else "?"
    return _LF('此更新无法在程序内安装（需要 Global {0} 或更高版本）。请从发布页下载安装程序手动安装。').format((version))


def error_sentence(code: str, detail: str = "", retry_after_utc: str = "") -> str:
    """One full sentence for a failed download / check step (the technical detail belongs in a tooltip)."""
    code = str(code or "")
    detail = str(detail or "")
    if code == "download.cancelled":
        return _L('下载已取消。')
    if code == "download.disk_space":
        if detail.isdigit():
            return _LF('磁盘空间不足：需要约 {0} MB 可用空间。').format((detail))
        return _L('磁盘空间不足。')
    if code in ("verify.sha256", "verify.size", "verify.not_pe"):
        return _L('下载的文件与发布记录不一致，已删除。请重试或到发布页手动下载。')
    if code == "verify.manual_install_required":
        return manual_install_sentence(detail)
    if code == "verify.version":
        return _L('这个下载不比当前版本新，已停止安装。')
    if code.startswith("verify."):
        return _L('此发布未通过安全校验，已停止更新。请到发布页查看。')
    if code == "install.blocked":
        return _LF('当前无法更新：{0}').format((detail))
    if code == "install.busy":
        return _L('另一个窗口正在更新。')
    if code.startswith("install.") or code.startswith("postupdate."):
        return launch_sentence(code)
    if code.startswith("check."):
        return kind_sentence(code, detail, retry_after_utc)
    if code.startswith("download."):
        return _LF('下载失败：{0}').format((kind_sentence(code, detail, retry_after_utc)))
    return _L('更新失败。')


def launch_sentence(code: str) -> str:
    """Why the installer did not start (the gate runs while the window is open, and again before CreateProcess)."""
    code = str(code or "")
    if code == "install.unexpected_files":
        return _L('更新文件夹中有不应存在的文件，已停止安装。请重新下载。')
    if code == "install.download_missing":
        return _L('下载的安装程序已不存在，请重新下载。')
    if code == "install.unsafe_folder":
        return _L('更新文件夹是链接或重定向，已停止安装。')
    if code == "install.busy":
        return _L('另一个窗口正在更新。')
    if code in ("verify.sha256", "verify.size"):
        return _L('下载的安装程序在校验后被改动，已停止安装。请重新下载。')
    if code == "verify.version":
        return _L('这个下载不比当前版本新，已停止安装。')
    if code == "verify.manual_install_required":
        return _L('此更新无法在程序内安装，请从发布页下载安装程序手动安装。')
    if code.startswith("verify."):
        return _L('下载的文件未通过安装前校验，已停止安装。请重新下载。')
    return _L('无法启动更新安装程序。')


# a refused launch whose cause lives in the downloaded files: the primary action is "download again" (review r5 H1)
REDOWNLOAD_CODES = ("install.unexpected_files", "install.download_missing", "install.unsafe_folder")


def needs_redownload(code: str) -> bool:
    return str(code or "") in REDOWNLOAD_CODES or str(code or "").startswith("verify.")


def ratelimit_active(retry_after_utc: object) -> bool:
    moment = parse_utc(retry_after_utc)
    return moment is not None and moment > _dt.datetime.now(_dt.timezone.utc)


def github_anchor_allowed(url: str) -> bool:
    """Links in release notes open only pages of the Global repository (review r5 F3)."""
    return repo_url_allowed(str(url))


def tooltip_text(text: object) -> str:
    """A tooltip that is always shown as plain text (review r5 F6: values from files or exceptions are never
    interpreted as rich text)."""
    text = str(text or "").strip()
    return f"<p>{html.escape(text)}</p>" if text else ""


def current_version_text() -> str:
    return GLOBAL_VERSION


__all__ = [
    "Qt", "local_time_text", "mb_text", "duration_text", "clock_text", "kind_sentence", "error_sentence",
    "launch_sentence", "manual_install_sentence", "ratelimit_active", "github_anchor_allowed", "tooltip_text",
    "needs_redownload", "REDOWNLOAD_CODES",
]
