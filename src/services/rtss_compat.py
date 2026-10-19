# RTSS(RivaTuner Statistics Server) 호환성 읽기 전용 검사 (NTE Drive Calc Global 추가 모듈)
"""Read-only RivaTuner Statistics Server (RTSS) compatibility check.

Verified on a user PC (2026-10-13/14): HTGame.exe (UE 5.6) crashed at start with ``D3D12Viewport.cpp:554 error
80004004`` (E_ABORT while creating the swap chain) whenever the calculator's Loader injected its native host
(``config/native-loader/d3d12.dll``, a d3d12 proxy) while RTSS was running with its default hook-chaining engine.
The D3D method puts the same kind of d3d12 host into the game folder, so it is treated alike (not separately verified).
Fix confirmed by the user: an RTSS application profile for HTGame.exe with Setup -> General -> "Use Microsoft
Detours API hooking" (``[Hooking] UseDetours=1`` in ``<RTSS>/Profiles/HTGame.exe.cfg``).  "Application detection
level: None" (``EnableHooking=0``) also avoids the conflict, at the cost of the RTSS overlay for the game.

This module only READS: the process list, the RTSS install location (running ``RTSS.exe`` image, the registry key
written by the RTSS installer, the default folder) and the two profile files.  It never writes RTSS settings, never
elevates, and never raises: every IO problem becomes status ``unknown`` with a short reason code.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from src.utils.atomic_json import AtomicJsonFile
from src.utils.logger import logger


GAME_PROFILE_NAME = "HTGame.exe.cfg"
GLOBAL_PROFILE_NAME = "Global"
PROFILES_DIR_NAME = "Profiles"
DEFAULT_INSTALL_DIR = r"C:\Program Files (x86)\RivaTuner Statistics Server"
# RTSS.exe is the server that keeps the hooks injected; the hook loaders only live while it runs.
RTSS_PROCESS_NAMES = frozenset({"rtss.exe", "rtsshooksloader64.exe", "rtsshooksloader.exe"})
# (hive name, subkey, use the 32-bit registry view) - the RTSS installer is 32-bit (WOW6432Node on 64-bit Windows).
REGISTRY_LOCATIONS = (
    ("HKLM", r"SOFTWARE\Unwinder\RTSS", True),
    ("HKLM", r"SOFTWARE\WOW6432Node\Unwinder\RTSS", False),
    ("HKCU", r"Software\Unwinder\RTSS", False),
)
# RTSS defaults when neither profile carries the key: hooking enabled, own (non-Detours) hook engine.
DEFAULT_ENABLE_HOOKING = 1
DEFAULT_USE_DETOURS = 0
MAX_PROFILE_BYTES = 1 << 20

STATUS_OK = "ok"
STATUS_RISK = "risk"
STATUS_UNKNOWN = "unknown"

REASON_NOT_INSTALLED = "not_installed"
REASON_NOT_RUNNING = "not_running"
REASON_HOOKING_DISABLED = "hooking_disabled"
REASON_DETOURS_ENABLED = "detours_enabled"
REASON_DEFAULT_HOOKING = "default_hooking"
REASON_PROCESS_QUERY_FAILED = "process_query_failed"
REASON_INSTALL_DIR_UNKNOWN = "install_dir_unknown"
REASON_PROFILE_UNREADABLE = "profile_unreadable"
REASON_CHECK_FAILED = "check_failed"

SOURCE_APP = GAME_PROFILE_NAME
SOURCE_GLOBAL = GLOBAL_PROFILE_NAME
SOURCE_DEFAULT = "default"


@dataclass(frozen=True)
class ProcessInfo:
    name: str
    path: str = ""          # full image path when it could be queried, else ""


@dataclass(frozen=True)
class RtssCompatResult:
    status: str             # ok | risk | unknown
    reason: str             # REASON_* code
    running: bool | None = None
    installed: bool | None = None
    install_dir: str = ""
    app_profile_present: bool | None = None
    global_profile_present: bool | None = None
    enable_hooking: int | None = None
    enable_hooking_source: str = ""
    use_detours: int | None = None
    use_detours_source: str = ""
    detail: str = ""        # short technical reason for 'unknown' (exception type, file name)

    @property
    def is_risk(self) -> bool:
        return self.status == STATUS_RISK

    def facts(self) -> tuple[tuple[str, bool | str | None], ...]:
        """Language-neutral evidence for diagnostics (the copyable report, logs)."""
        values: list[tuple[str, bool | str | None]] = [
            ("rtss_status", self.status), ("rtss_reason", self.reason), ("rtss_running", self.running),
        ]
        if self.install_dir:
            values.append(("rtss_install_dir", self.install_dir))
        if self.app_profile_present is not None:
            values.append(("rtss_app_profile", self.app_profile_present))
        if self.use_detours is not None:
            values.append(("rtss_use_detours", f"{self.use_detours} ({self.use_detours_source})"))
        if self.enable_hooking is not None:
            values.append(("rtss_enable_hooking", f"{self.enable_hooking} ({self.enable_hooking_source})"))
        if self.detail:
            values.append(("rtss_detail", self.detail))
        return tuple(values)


# --------------------------------------------------------------------------------------------- pure functions

def decode_profile_bytes(data: bytes) -> str:
    """Profile bytes -> text: UTF-8 / UTF-16 BOMs, BOM-less UTF-16LE, UTF-8, else Latin-1 (never fails)."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le", errors="replace")
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", errors="replace")
    if len(data) >= 4 and data[1] == 0 and data[3] == 0 and data[0] != 0:
        return data.decode("utf-16-le", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def parse_profile(text: str) -> dict[str, dict[str, str]]:
    """Tolerant INI parse; section and key names are case-insensitive (casefolded).

    Like the Windows profile API, the FIRST occurrence of a section and of a key wins; comment lines (``;``/``#``),
    blank lines, lines without ``=`` and keys before the first section are ignored.
    """
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.replace("\x00", "").splitlines():
        line = raw.strip().lstrip("\ufeff").strip()
        if not line or line[0] in ";#":
            continue
        if line.startswith("["):
            end = line.find("]")
            if end < 0:
                current = None
                continue
            name = line[1:end].strip().casefold()
            current = sections.setdefault(name, {}) if name not in sections else None
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().casefold()
        if key and key not in current:
            current[key] = value.strip()
    return sections


def profile_int(value: str | None) -> int | None:
    """Integer value of a profile entry (decimal or 0x hex, optional sign); None when absent or not a number."""
    if value is None:
        return None
    text = value.strip().split(";", 1)[0].strip()
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-").strip()
    try:
        if text[:2].casefold() == "0x":
            return sign * int(text[2:], 16)
        digits = ""
        for character in text:
            if not character.isdigit():
                break
            digits += character
        return sign * int(digits) if digits else None
    except ValueError:
        return None


def effective_hooking_value(
    key: str, app_profile: Mapping[str, Mapping[str, str]] | None,
    global_profile: Mapping[str, Mapping[str, str]] | None, default: int,
) -> tuple[int, str]:
    """(value, source) of ``[Hooking] key``: the HTGame profile, else the Global profile, else the RTSS default."""
    key = key.casefold()
    for profile, source in ((app_profile, SOURCE_APP), (global_profile, SOURCE_GLOBAL)):
        if profile is None:
            continue
        value = profile_int((profile.get("hooking") or {}).get(key))
        if value is not None:
            return value, source
    return default, SOURCE_DEFAULT


def evaluate_profiles(
    app_text: str | None, global_text: str | None, *, install_dir: str = "",
    installed: bool | None = True,
) -> RtssCompatResult:
    """Decision for a RUNNING RTSS from the two profile texts (None = file absent)."""
    app_profile = parse_profile(app_text) if app_text is not None else None
    global_profile = parse_profile(global_text) if global_text is not None else None
    enable, enable_source = effective_hooking_value(
        "EnableHooking", app_profile, global_profile, DEFAULT_ENABLE_HOOKING)
    detours, detours_source = effective_hooking_value(
        "UseDetours", app_profile, global_profile, DEFAULT_USE_DETOURS)
    if enable == 0:
        status, reason = STATUS_OK, REASON_HOOKING_DISABLED
    elif detours != 0:
        status, reason = STATUS_OK, REASON_DETOURS_ENABLED
    else:
        status, reason = STATUS_RISK, REASON_DEFAULT_HOOKING
    return RtssCompatResult(
        status, reason, running=True, installed=installed, install_dir=install_dir,
        app_profile_present=app_text is not None, global_profile_present=global_text is not None,
        enable_hooking=enable, enable_hooking_source=enable_source,
        use_detours=detours, use_detours_source=detours_source,
    )


def rtss_processes(processes: Iterable[ProcessInfo]) -> tuple[ProcessInfo, ...]:
    return tuple(item for item in processes if str(item.name).casefold() in RTSS_PROCESS_NAMES)


def _install_dir_candidates(
    running: Iterable[ProcessInfo], registry_dirs: Iterable[str], default_dir: str,
) -> list[str]:
    candidates: list[str] = []
    # The running server's own folder first (portable installs, a second copy), then the installer's records.
    for item in running:
        if item.path and Path(item.path).name.casefold() == "rtss.exe":
            candidates.append(str(Path(item.path).parent))
    candidates.extend(str(path) for path in registry_dirs if str(path).strip())
    if default_dir:
        candidates.append(default_dir)
    seen: set[str] = set()
    unique = []
    for candidate in candidates:
        key = os.path.normcase(os.path.normpath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _find_profile(names: Iterable[str], wanted: str) -> str | None:
    wanted = wanted.casefold()
    return next((name for name in sorted(names) if name.casefold() == wanted), None)


# ------------------------------------------------------------------------------------------------- system IO

def list_processes() -> list[ProcessInfo]:
    """Processes named like RTSS (Toolhelp32 snapshot); raises OSError when the snapshot cannot be taken."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes, snapshot.restype = [wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE
    first, following = kernel.Process32FirstW, kernel.Process32NextW
    for function in (first, following):
        function.argtypes, function.restype = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
    open_process = kernel.OpenProcess
    open_process.argtypes, open_process.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    handle = snapshot(2, 0)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    result: list[ProcessInfo] = []
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        found = first(handle, ctypes.byref(entry))
        if not found:
            raise OSError(ctypes.get_last_error(), "Process32FirstW failed")
        while found:
            name = entry.name
            if name.casefold() in RTSS_PROCESS_NAMES:
                path = ""
                process = open_process(0x1000, False, entry.pid)    # PROCESS_QUERY_LIMITED_INFORMATION
                if process:
                    try:
                        buffer = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(len(buffer))
                        if query(process, 0, buffer, ctypes.byref(size)):
                            path = buffer.value
                    finally:
                        close(process)
                result.append(ProcessInfo(name, path))
            found = following(handle, ctypes.byref(entry))
    finally:
        close(handle)
    return result


def registry_install_dirs() -> list[str]:
    """RTSS folders recorded by its installer (InstallDir, else the parent of InstallPath); [] when absent."""
    if os.name != "nt":
        return []
    import winreg

    hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    found: list[str] = []
    for hive, subkey, view32 in REGISTRY_LOCATIONS:
        access = winreg.KEY_READ | (winreg.KEY_WOW64_32KEY if view32 else 0)
        try:
            with winreg.OpenKey(hives[hive], subkey, 0, access) as key:
                for name in ("InstallDir", "InstallPath"):
                    try:
                        value, _kind = winreg.QueryValueEx(key, name)
                    except OSError:
                        continue
                    if isinstance(value, str) and value.strip():
                        value = value.strip().strip('"')
                        found.append(value if name == "InstallDir" else str(Path(value).parent))
                        break
        except OSError:
            continue
    return found


def _read_profile_bytes(path: Path) -> bytes:
    with open(path, "rb") as stream:
        return stream.read(MAX_PROFILE_BYTES)


# ----------------------------------------------------------------------------------------------- orchestration

def check_rtss_compat(
    *,
    processes: Callable[[], Iterable[ProcessInfo]] = list_processes,
    registry_dirs: Callable[[], Iterable[str]] = registry_install_dirs,
    default_dir: str = DEFAULT_INSTALL_DIR,
    list_dir: Callable[[str], Iterable[str]] = os.listdir,
    is_dir: Callable[[str], bool] = os.path.isdir,
    read_bytes: Callable[[Path], bytes] = _read_profile_bytes,
) -> RtssCompatResult:
    """One read-only evaluation.  Never raises; dependencies are injectable for tests."""
    try:
        return _check(processes, registry_dirs, default_dir, list_dir, is_dir, read_bytes)
    except Exception as error:      # pragma: no cover - last-resort guard, the check must never break a caller
        return RtssCompatResult(STATUS_UNKNOWN, REASON_CHECK_FAILED, detail=type(error).__name__)


def _check(processes, registry_dirs, default_dir, list_dir, is_dir, read_bytes) -> RtssCompatResult:
    process_error = ""
    try:
        running_items = rtss_processes(processes())
        running: bool | None = bool(running_items)
    except Exception as error:
        running_items, running, process_error = (), None, type(error).__name__
    try:
        recorded = [str(path) for path in registry_dirs()]
    except Exception:
        recorded = []
    candidates = _install_dir_candidates(running_items, recorded, default_dir)
    existing = []
    for candidate in candidates:
        try:
            if is_dir(candidate):
                existing.append(candidate)
        except Exception:
            continue
    installed = bool(running_items) or bool(existing)
    if running is False:
        return RtssCompatResult(STATUS_OK, REASON_NOT_RUNNING if installed else REASON_NOT_INSTALLED,
                                running=False, installed=installed, install_dir=existing[0] if existing else "")
    if running is None:
        if not installed:
            return RtssCompatResult(STATUS_OK, REASON_NOT_INSTALLED, running=None, installed=False)
        return RtssCompatResult(STATUS_UNKNOWN, REASON_PROCESS_QUERY_FAILED, running=None, installed=True,
                                install_dir=existing[0], detail=process_error)
    profiles_dir = ""
    for candidate in existing:
        path = os.path.join(candidate, PROFILES_DIR_NAME)
        try:
            if is_dir(path):
                profiles_dir = path
                break
        except Exception:
            continue
    if not profiles_dir:
        return RtssCompatResult(STATUS_UNKNOWN, REASON_INSTALL_DIR_UNKNOWN, running=True, installed=True,
                                install_dir=existing[0] if existing else "", detail=PROFILES_DIR_NAME)
    install_dir = str(Path(profiles_dir).parent)
    try:
        names = list(list_dir(profiles_dir))
    except Exception as error:
        return RtssCompatResult(STATUS_UNKNOWN, REASON_PROFILE_UNREADABLE, running=True, installed=True,
                                install_dir=install_dir, detail=f"{PROFILES_DIR_NAME}: {type(error).__name__}")
    texts: list[str | None] = []
    for wanted in (GAME_PROFILE_NAME, GLOBAL_PROFILE_NAME):
        name = _find_profile(names, wanted)
        if name is None:
            texts.append(None)
            continue
        try:
            texts.append(decode_profile_bytes(read_bytes(Path(profiles_dir) / name)))
        except FileNotFoundError:
            texts.append(None)      # removed between the listing and the read
        except Exception as error:
            return RtssCompatResult(STATUS_UNKNOWN, REASON_PROFILE_UNREADABLE, running=True, installed=True,
                                    install_dir=install_dir, detail=f"{wanted}: {type(error).__name__}")
    return evaluate_profiles(texts[0], texts[1], install_dir=install_dir, installed=True)


class RtssCompatMonitor:
    """Thread-safe cache around :func:`check_rtss_compat` for the periodic environment observation."""

    def __init__(self, check: Callable[[], RtssCompatResult] = check_rtss_compat, *, ttl: float = 10.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._check = check
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._cached: RtssCompatResult | None = None
        self._stamp = 0.0
        self._logged: tuple[str, str] | None = None

    def current(self, *, force: bool = False) -> RtssCompatResult:
        with self._lock:
            now = self._clock()
            if not force and self._cached is not None and now - self._stamp < self._ttl:
                return self._cached
        try:
            result = self._check()
        except Exception as error:      # an injected check may raise; keep the never-raise contract
            result = RtssCompatResult(STATUS_UNKNOWN, REASON_CHECK_FAILED, detail=type(error).__name__)
        with self._lock:
            self._cached, self._stamp = result, self._clock()
            key = (result.status, result.reason)
            changed = key != self._logged
            self._logged = key
        if changed and result.status != STATUS_OK:
            try:
                logger.info("rtss_compat | {}", " ".join(f"{k}={v}" for k, v in result.facts()))
            except Exception:
                pass
        return result


# Short TTL: an explicit "Re-detect" while sync is paused is not forced (allow_connect=False) and must still see a
# setting the user just changed in RTSS.  One read = a process snapshot + two small file reads.
_MONITOR = RtssCompatMonitor(ttl=2.0)


def current_rtss_compat(*, force: bool = False) -> RtssCompatResult:
    """Shared, cached RTSS evaluation (``force`` re-reads now: explicit checks and the pre-start reminder)."""
    return _MONITOR.current(force=force)


def rtss_probe_for(policy, *, force: bool = False) -> RtssCompatResult | None:
    """The environment probe's RTSS field: evaluated only where the calculator injects (native_load allowed =
    medium / developer); None in offline / low-risk mode or when the policy cannot answer."""
    try:
        if not policy.allowed("native_load"):
            return None
    except Exception:
        return None
    return current_rtss_compat(force=force)


# --------------------------------------------------------------------------------------- per-account preference

NOTICE_FILE_NAME = "rtss_compat_notice.json"


class RtssNoticePreference:
    """Per-account "don't show the pre-start RTSS reminder again" flag (``<account>/config/rtss_compat_notice.json``).

    Reading never raises (a missing or broken file means "show"); saving reports failure with ``False``.
    """

    def __init__(self, account_config_dir: str | Path | None) -> None:
        self._file = AtomicJsonFile(Path(account_config_dir) / NOTICE_FILE_NAME) if account_config_dir else None

    def suppressed(self) -> bool:
        if self._file is None:
            return False
        try:
            value = self._file.load({}) or {}
        except Exception:
            return False
        return value.get("suppress_injection_reminder") is True

    def set_suppressed(self, suppressed: bool = True) -> bool:
        if self._file is None:
            return False
        try:
            self._file.save({"suppress_injection_reminder": bool(suppressed), "version": 1})
            return True
        except Exception as error:
            try:
                logger.warning("rtss_compat | saving the reminder preference failed: {}", type(error).__name__)
            except Exception:
                pass
            return False
