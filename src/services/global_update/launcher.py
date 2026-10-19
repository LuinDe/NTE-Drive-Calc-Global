# Global 업데이트 설치 프로그램 실행: 사전 게이트(재해시·서명 재검증·폴더 허용 목록) → 고정 argv로 무인 실행
"""Installer hand-off of the Global updater (design_final §6.5, §7.2, §7.4, §7.5, §8.4; review r5 H1 / F4 / F5).

``preflight`` runs the whole gate while the window is still open (so a refusal is shown in place instead of closing
the program for nothing); ``launch`` runs the same gate again right before ``CreateProcess`` and keeps the
deny-write handle open across it.  The gate: the tag must be newer than the running build and named by the staged
record; ``updates`` and the tag folder must be real folders (no junction / symlink); the tag folder holds only
allow-listed entries (DLL preloading); the installer is re-hashed through a handle that denies writes and renames to
everyone else; manifest + signature are re-verified from disk.  Setup then runs with a fixed argument list in which
only the tag, the wizard language and our log path vary.  Inno's ``{tmp}`` is moved into the tag folder through
``TMP``/``TEMP`` of the child (the relaunched app heals that environment, ``env.py``).

Concurrency: an exclusive lock FILE inside ``updates`` (share mode 0, delete-on-close) instead of a session-wide
named mutex, so a process that cannot write the folder cannot block updates either (review r5 F5).
"""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from src.app import global_release as gr
from src.i18n_runtime import LANGUAGES
from src.services.global_update.models import UpdateError
from src.services.global_update.state import NOTES_NAME, SETUP_LOG_NAME, TMP_DIR_NAME
from src.services.global_update.verify import sha256_stream, verify_manifest

LOCK_NAME = "update.lock"
DISK_SPACE_MARGIN = gr.DISK_SPACE_MARGIN
LISTING_RETRIES = 3
LISTING_RETRY_SECONDS = 0.5
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_DELETE = 0x00010000
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_OPEN_ALWAYS = 4
_FILE_ATTRIBUTE_NORMAL = 0x80
_FILE_ATTRIBUTE_HIDDEN = 0x2
_FILE_FLAG_DELETE_ON_CLOSE = 0x04000000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_INVALID_HANDLE = ctypes.c_void_p(-1).value

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None


# ───────────────────────────── lock ─────────────────────────────
class UpdateLock:
    """Exclusive handle on ``updates\\update.lock`` held from the first download click until the launcher returns;
    the file disappears when the handle closes (also when the process dies)."""

    def __init__(self, handle: int) -> None:
        self.handle = handle

    def release(self) -> None:
        if self.handle and _kernel32 is not None:
            _kernel32.CloseHandle(wintypes.HANDLE(self.handle))
        self.handle = 0


def acquire_update_lock(updates_dir: str | os.PathLike) -> UpdateLock | None:
    """``UpdateLock`` when this process now holds the lock, ``None`` when another process holds it (or the folder
    cannot be written, in which case nothing could be installed from it either)."""
    folder = Path(updates_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    if _kernel32 is None:
        return UpdateLock(0)
    _kernel32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = _kernel32.CreateFileW(os.fspath(folder / LOCK_NAME), _GENERIC_READ | _GENERIC_WRITE | _DELETE, 0, None,
                                   _OPEN_ALWAYS, _FILE_ATTRIBUTE_HIDDEN | _FILE_FLAG_DELETE_ON_CLOSE, None)
    if not handle or handle == _INVALID_HANDLE:
        return None
    return UpdateLock(int(handle))


# ───────────────────────────── pure helpers ─────────────────────────────
def build_installer_argv(installer: str | os.PathLike, lang: str, relaunch: bool, log: str | os.PathLike) -> list[str]:
    """The fixed Setup command line; only the installer path, the language and the log path vary."""
    if lang not in LANGUAGES:
        raise ValueError(f"not a wizard language: {lang!r}")
    return [
        str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCANCEL", "/CLOSEAPPLICATIONS",
        "/NORESTARTAPPLICATIONS", "/MERGETASKS=!installvigem", f"/LANG={lang}", "/AUTOUPDATE=1",
        f"/RELAUNCH={1 if relaunch else 0}", f"/LOG={os.fspath(log)}",
    ]


def allowed_entries(tag: str) -> frozenset[str]:
    return frozenset({gr.installer_name(tag), gr.manifest_name(tag), gr.signature_name(tag), NOTES_NAME,
                      SETUP_LOG_NAME, TMP_DIR_NAME})


def _ignorable(entry: str, tag: str) -> bool:
    """Names a scanner may leave next to the download for a moment (``<installer>.part.tmp`` seen on this PC); no
    loader ever loads a file by such a name, so they never refuse a launch (review r5 regression 8)."""
    base = re.escape(gr.installer_name(tag))
    return re.fullmatch(base + r"\.part(?:\.tmp)?", entry, re.IGNORECASE) is not None


def _listing_problems(tag_dir: Path, tag: str) -> list[str]:
    allowed = allowed_entries(tag)
    bad = []
    for entry in sorted(os.listdir(tag_dir)):
        path = tag_dir / entry
        if entry == TMP_DIR_NAME:
            if not path.is_dir() or is_reparse_point(path):
                bad.append(entry)
        elif entry not in allowed:
            if not (_ignorable(entry, tag) and path.is_file()):
                bad.append(entry)
        elif path.is_dir() or is_reparse_point(path):
            bad.append(entry)
    return bad


def unexpected_entries(tag_dir: str | os.PathLike, tag: str, *, retries: int = 1,
                       pause: float = LISTING_RETRY_SECONDS) -> list[str]:
    """Entries of the tag folder that the launcher refuses (anything outside the allow-list; ``tmp`` only as a real
    directory; no reparse points).  With ``retries`` > 1 the listing is repeated after ``pause`` seconds while it
    is not clean (files a virus scanner creates for a moment)."""
    folder = Path(tag_dir)
    bad = _listing_problems(folder, tag)
    for _ in range(max(0, int(retries) - 1)):
        if not bad:
            break
        time.sleep(pause)
        bad = _listing_problems(folder, tag)
    return bad


def is_reparse_point(path: str | os.PathLike) -> bool:
    """Junction, symbolic link or any other reparse point (never followed by the launcher)."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT) or stat.S_ISLNK(info.st_mode)


def open_deny_write(path: str | os.PathLike):
    """Read-only handle that denies write / delete / rename to every other opener (NT share mode READ only); the
    returned file object owns the handle.  Off Windows a plain file object is returned."""
    if _kernel32 is None:
        return open(path, "rb")
    import msvcrt

    _kernel32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = _kernel32.CreateFileW(os.fspath(path), _GENERIC_READ, _FILE_SHARE_READ, None, _OPEN_EXISTING,
                                   _FILE_ATTRIBUTE_NORMAL, None)
    if not handle or handle == _INVALID_HANDLE:
        raise OSError(ctypes.get_last_error(), f"CreateFileW failed for {Path(path).name}")
    descriptor = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
    return os.fdopen(descriptor, "rb", buffering=0)


def check_disk_space(updates_dir: str | os.PathLike, size: int) -> None:
    needed = int(size) + DISK_SPACE_MARGIN
    try:
        free = shutil.disk_usage(updates_dir).free
    except OSError as exc:
        raise UpdateError("download.io", type(exc).__name__) from None
    if free < needed:
        raise UpdateError("download.disk_space", str(needed // 2**20))


def check_folder(updates_dir: str | os.PathLike, tag: str | None = None) -> None:
    """``updates`` (and the tag folder) must be real folders, never a junction / symlink that redirects the
    download, the clean-up or Setup elsewhere (review r5 F4)."""
    folders = [Path(updates_dir)] + ([Path(updates_dir) / tag] if tag else [])
    for folder in folders:
        if is_reparse_point(folder):
            raise UpdateError("install.unsafe_folder", f"{folder.name} is a reparse point")


def child_environment(tmp_dir: str | os.PathLike) -> dict[str, str]:
    env = dict(os.environ)
    env["TMP"] = env["TEMP"] = os.fspath(tmp_dir)
    return env


def prepare_tmp_dir(tag_dir: Path) -> Path:
    """``<tag dir>\\tmp`` exists and is empty (leftovers of an earlier Setup run are ours to drop)."""
    tmp_dir = tag_dir / TMP_DIR_NAME
    if tmp_dir.is_dir():
        for entry in tmp_dir.iterdir():
            if entry.is_dir() and not is_reparse_point(entry):
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
    else:
        tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


# ───────────────────────────── the gate + launch ─────────────────────────────
def _gate(*, updates_dir, tag: str, staged: dict, settings: gr.GlobalUpdateSettings,
          current_version: gr.GlobalVersion | None, listing_retries: int):
    """Every check of design_final §6.5; returns ``(tag_dir, installer, open deny-write handle, size, sha)``.  The
    caller closes the handle.  Raises ``UpdateError`` (nothing started)."""
    current = current_version or gr.current_global_version()
    version = gr.parse_global_tag(tag)
    if version is None or not version > current:
        raise UpdateError("verify.version", f"{tag} is not newer than {current.text}")
    if not isinstance(staged, dict) or staged.get("tag") != tag:
        raise UpdateError("verify.version", "staged record does not name this tag")
    expected_size = int(staged.get("size") or 0)
    expected_sha = str(staged.get("sha256") or "")
    if expected_size <= 0 or len(expected_sha) != 64:
        raise UpdateError("verify.manifest_invalid", "staged record incomplete")
    tag_dir = Path(updates_dir) / tag
    check_folder(updates_dir, tag)
    if not tag_dir.is_dir():
        raise UpdateError("install.download_missing", "tag folder missing")
    bad = unexpected_entries(tag_dir, tag, retries=listing_retries)
    if bad:
        raise UpdateError("install.unexpected_files", ", ".join(bad)[:200])
    installer = tag_dir / gr.installer_name(tag)
    if not installer.is_file():
        raise UpdateError("install.download_missing", "installer missing")
    try:
        handle = open_deny_write(installer)
    except OSError as exc:
        raise UpdateError("install.launch_failed", f"open: {type(exc).__name__}") from None
    try:
        digest = sha256_stream(handle, expected_size)
        if digest != expected_sha:
            raise UpdateError("verify.sha256", "staged installer changed since verification")
        if settings.require_signed_manifest:
            manifest_path = tag_dir / gr.manifest_name(tag)
            signature_path = tag_dir / gr.signature_name(tag)
            if not manifest_path.is_file() or not signature_path.is_file():
                raise UpdateError("verify.manifest_missing", "manifest or signature missing")
            if manifest_path.stat().st_size > gr.MANIFEST_SIZE_MAX or signature_path.stat().st_size > gr.MANIFEST_SIZE_MAX:
                raise UpdateError("verify.manifest_invalid", "manifest or signature too large")
            verify_manifest(
                manifest_path.read_bytes(), signature_path.read_bytes(), settings.signing_keys,
                gr.RELEASE_SIG_NAMESPACE, expected_tag=tag, expected_size=expected_size,
                expected_sha256=expected_sha, current_version=current,
                size_min=settings.installer_size_min, size_max=settings.installer_size_max,
            )
    except BaseException:
        handle.close()
        raise
    return tag_dir, installer, handle, expected_size, expected_sha


def preflight(*, updates_dir: str | os.PathLike, tag: str, staged: dict, settings: gr.GlobalUpdateSettings,
              current_version: gr.GlobalVersion | None = None) -> None:
    """The whole launch gate WITHOUT starting anything (review r5 H1): called while the window is still open, so a
    refusal is shown in place and the program is never closed for nothing.  ``launch`` repeats every check."""
    _tag_dir, _installer, handle, _size, _sha = _gate(updates_dir=updates_dir, tag=tag, staged=staged,
                                                      settings=settings, current_version=current_version,
                                                      listing_retries=LISTING_RETRIES)
    handle.close()


def launch(
    *,
    updates_dir: str | os.PathLike,
    tag: str,
    staged: dict,
    settings: gr.GlobalUpdateSettings,
    lang: str,
    relaunch: bool,
    current_version: gr.GlobalVersion | None = None,
    popen: Callable = subprocess.Popen,
) -> int:
    """design_final §6.5: the gate of ``preflight`` again, then Setup starts with the fixed argv while the deny-write
    handle is still open.  Returns the child pid; raises ``UpdateError`` (nothing started) otherwise."""
    tag_dir, installer, handle, expected_size, expected_sha = _gate(
        updates_dir=updates_dir, tag=tag, staged=staged, settings=settings, current_version=current_version,
        listing_retries=LISTING_RETRIES)
    try:
        tmp_dir = prepare_tmp_dir(tag_dir)
        argv = build_installer_argv(installer, lang, relaunch, tag_dir / SETUP_LOG_NAME)
        env = child_environment(tmp_dir)
        try:
            process = popen(argv, cwd=str(tag_dir), close_fds=True, env=env)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 32 and handle is not None:
                # documented fallback: the share mode blocked CreateProcess on this system -> re-hash, then start
                handle.close()
                handle = None
                with open(installer, "rb") as plain:
                    if sha256_stream(plain, expected_size) != expected_sha:
                        raise UpdateError("verify.sha256", "staged installer changed since verification") from None
                try:
                    process = popen(argv, cwd=str(tag_dir), close_fds=True, env=env)
                except OSError as again:
                    raise UpdateError("install.launch_failed", type(again).__name__) from None
            else:
                raise UpdateError("install.launch_failed", type(exc).__name__) from None
        return int(getattr(process, "pid", 0) or 0)
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
