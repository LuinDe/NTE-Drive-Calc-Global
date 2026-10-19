# Global 인앱 업데이트 컨트롤러: 시작 시 조용한 확인 → 배너/대화상자 → 백그라운드 다운로드 → 명시적 설치 → 재시작 조정
"""State machine of the Global in-app update (design_final §8, §10.2, §12; review r5).

Composed into ``MainWindow`` like the other controllers.  The blocking network work runs in DAEMON Python threads
(``_Job``): a stalled GitHub connection can never keep the process alive or abort it at exit (review r5 M4).  Results
come back through queued Qt signals; widgets are touched only in slots.  The views (settings card, home banner,
dialog) render the frozen ``UpdateState`` projection emitted by ``state_changed``; the persisted truth lives in
``updates\\state.json`` (``GlobalUpdateState``).
"""
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import functools
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from src import i18n_runtime
from src.app import global_release as gr
from src.observability import OperationContext, log_event
from src.services.global_update import launcher as L
from src.services.global_update.client import GlobalUpdateClient
from src.services.global_update.models import CheckOutcome, ReleaseCandidate, UpdateError, UpdateState
from src.services.global_update.notes import notes_for_language, unverified_notes_text
from src.services.global_update.state import (
    GlobalUpdateState, LAST_LOG_NAME, LAST_NOTES_NAME, NOTES_NAME, OUTCOME_IN_PROGRESS, OUTCOME_LAUNCH_FAILED,
    OUTCOME_NONE, OUTCOME_NOT_COMPLETED, OUTCOME_UPDATED, SETUP_LOG_NAME, decode_setup_log, now_utc,
)
from src.services.global_update.verify import verify_manifest
from src.utils.logger import logger

JANITOR_DELAY_MS = 90_000
PROMPT_RETRY_MS = 1500
PROMPT_WINDOW_SECONDS = 60
SPEED_WINDOW_SECONDS = 3.0
INSTALL_LOG_MAX = 256 * 1024
_RESULT_BY_CODE = {
    "check.network": "offline", "check.timeout": "timeout", "check.tls": "tls", "check.ratelimit": "rate_limited",
    "check.invalid_response": "invalid", "check.no_release": "no_release", "check.untrusted_release": "untrusted",
}
_CODE_BY_RESULT = {
    "offline": "check.network", "timeout": "check.timeout", "tls": "check.tls", "rate_limited": "check.ratelimit",
    "server": "check.http_500", "invalid": "check.invalid_response", "no_release": "check.no_release",
    "untrusted": "check.untrusted_release",
}
def _remove_tree(path: Path, attempts: int = 6, pause: float = 0.1) -> bool:
    """``rmtree`` that waits out Windows' delete-pending state: a scanner that still holds a file we just deleted
    keeps its folder "not empty" for a moment.  True when the folder is gone."""
    for _attempt in range(attempts):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.lexists(path):
            return True
        time.sleep(pause)
    return not os.path.lexists(path)


def _blocker_sentence(key: str) -> str:
    """What stops the app update right now (the work-mode composition reports the key; review r5 M2: the app update
    has its own sentences, not the native plugin update's)."""
    return {
        "work_mode": _L('工作模式正在切换，请完成后更新。'),
        "battle_report": _L('战报正在录制或收尾，请在战报页停止录制并等待保存完成后再更新程序。'),
        "automatic_equipment_apply": _L('自动装配正在操作游戏界面，请等待装配结束或停止装配后再更新程序。'),
        "rewind_execution": _L('倒带正在执行游戏操作，请等待本次执行结束或停止倒带后再更新程序。'),
        "scanning": _L('背包扫描正在进行，请等待扫描结束或停止扫描后再更新程序。'),
        "character_profile_sync": _L('角色养成同步正在进行，请等待同步结束后再更新程序。'),
    }.get(str(key), _L('有尚未结束的游戏操作，请等待其结束后再更新程序。'))


class _Job(QObject):
    """One blocking job in a DAEMON thread; the result is emitted through a queued signal.  ``isRunning`` / ``wait``
    mirror the QThread names the controller used before."""

    result_ready = Signal(object)
    download_progress = Signal(int, int)

    def __init__(self, target, parent=None) -> None:
        super().__init__(parent)
        self._target = target
        self._thread: threading.Thread | None = None
        self.cancel_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=f"global-update-{type(self).__name__}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            result = self._target()
        except BaseException as exc:  # noqa: BLE001 - fail closed, class name only
            result = UpdateError("check.network" if isinstance(self, _CheckJob) else "download.io", type(exc).__name__)
        try:
            self.result_ready.emit(result)
        except RuntimeError:
            pass   # the controller is gone (the program is exiting)

    def emit_progress(self, done: int, total: int) -> None:
        try:
            self.download_progress.emit(int(done), int(total))
        except RuntimeError:
            pass

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait(self, ms: int) -> bool:
        if self._thread is not None:
            self._thread.join(max(0, ms) / 1000)
        return not self.isRunning()

    def cancel(self) -> None:
        self.cancel_event.set()


class _CheckJob(_Job):
    def __init__(self, client: GlobalUpdateClient, parent=None) -> None:
        super().__init__(target=self._job, parent=parent)
        self._client = client

    def _job(self):
        try:
            # the signed manifest is verified during the check (review r5 F1): nothing unverified is ever announced
            return self._client.verify_candidate(self._client.fetch_candidate())
        except UpdateError as exc:
            return exc
        except Exception as exc:  # fail closed, class name only
            return UpdateError("check.network", type(exc).__name__)


class _DownloadJob(_Job):
    def __init__(self, client: GlobalUpdateClient, candidate: ReleaseCandidate, tag_dir: Path,
                 settings: gr.GlobalUpdateSettings, current: gr.GlobalVersion, parent=None) -> None:
        super().__init__(target=self._job, parent=parent)
        self._client = client
        self._candidate = candidate
        self._tag_dir = tag_dir
        self._settings = settings
        self._current = current
        self.tag = candidate.tag

    def _job(self):
        candidate = self._candidate
        try:
            key_id = ""
            if self._settings.require_signed_manifest:
                manifest_bytes, signature_bytes = candidate.manifest_bytes, candidate.signature_bytes
                if not manifest_bytes or not signature_bytes:
                    if candidate.manifest is None or candidate.signature is None:
                        raise UpdateError("verify.manifest_missing", "release has no signed manifest")
                    manifest_bytes = self._client.fetch_small(candidate.manifest)
                    signature_bytes = self._client.fetch_small(candidate.signature)
                # exactly the bytes the check verified (or fetched now) are verified again and stored
                manifest = verify_manifest(
                    manifest_bytes, signature_bytes, self._settings.signing_keys, gr.RELEASE_SIG_NAMESPACE,
                    expected_tag=candidate.tag, expected_size=candidate.installer.size,
                    expected_sha256=candidate.installer.sha256, current_version=self._current,
                    size_min=self._settings.installer_size_min, size_max=self._settings.installer_size_max,
                )
                key_id = manifest.key_id
                (self._tag_dir / gr.manifest_name(candidate.tag)).write_bytes(manifest_bytes)
                (self._tag_dir / gr.signature_name(candidate.tag)).write_bytes(signature_bytes)
            if self.cancel_event.is_set():
                raise UpdateError("download.cancelled")
            digest = self._client.download(
                candidate.installer, self._tag_dir / gr.installer_name(candidate.tag),
                progress=self.emit_progress, cancel=self.cancel_event,
            )
            notes = {"tag": candidate.tag, "name": candidate.name, "html_url": candidate.html_url,
                     "published_at": candidate.published_at, "body": candidate.body,
                     "notes_verified": bool(candidate.notes_verified)}
            (self._tag_dir / NOTES_NAME).write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
            return {"tag": candidate.tag, "size": candidate.installer.size, "sha256": digest, "key_id": key_id,
                    "published_at": candidate.published_at}
        except UpdateError as exc:
            return exc
        except OSError as exc:
            if getattr(exc, "errno", None) == 28:
                return UpdateError("download.disk_space",
                                   str((candidate.installer.size + gr.DISK_SPACE_MARGIN) // 2**20))
            return UpdateError("download.io", type(exc).__name__)
        except Exception as exc:
            return UpdateError("download.io", type(exc).__name__)


class GlobalUpdateController(QObject):
    state_changed = Signal(object)

    _PHASE_DEFAULTS = dict(error_code="", error_detail="", blocker_text="", manual_min="", unusable_tag="")

    def __init__(self, *, window, settings: gr.GlobalUpdateSettings, parent: QObject | None = None) -> None:
        super().__init__(parent or window)
        self.window = window
        self.settings = settings
        self.current = gr.current_global_version()
        self.updates_dir = Path(window.app_context.paths.data_root) / "updates"
        self.state = GlobalUpdateState(self.updates_dir)
        self.client = GlobalUpdateClient(settings, current_version=self.current)
        self.view = UpdateState(auto_check=self.state.auto_check)
        self.candidate: ReleaseCandidate | None = None
        self.last_error: UpdateError | None = None
        self._check_job: _CheckJob | None = None
        self._download_job: _DownloadJob | None = None
        self._lock: L.UpdateLock | None = None
        self._dialog = None
        self._banner_hidden_tag = ""
        self._prompt_deadline = 0.0
        self._manual = False
        self._resume_tag = ""
        self._download_after_check = False
        self._warning: tuple[str, str, str, str] | None = None     # (phase, tag, error code, detail)
        self._started = False
        self._closed = False
        self._closing_prompted = False
        self._close_confirmed = False
        self._speed_samples: list[tuple[float, int]] = []
        self._pending_outcome = OUTCOME_NONE
        self._log = OperationContext.create("global_update")
        i18n_runtime.add_listener(self._on_language_changed)

    # ───────────────────────────── projection ─────────────────────────────
    def _emit(self, **changes) -> None:
        base = dict(
            last_check_utc=self.state.last_check_utc, auto_check=self.state.auto_check,
            skipped_tag=self.state.skipped_tag, staged_tag=(self.state.staged or {}).get("tag", ""),
            retry_after_utc=self.state.rate_limit_reset_utc,
        )
        base.update(changes)
        extra = dict(self.view.extra)
        extra.update(changes.pop("extra", {}) if "extra" in changes else {})
        extra["banner_hidden"] = bool(self.view.tag and self.view.tag == self._banner_hidden_tag) if "tag" not in changes else bool(changes.get("tag") == self._banner_hidden_tag and changes.get("tag"))
        base["extra"] = extra
        self.view = self.view.replace(**base)
        self.state_changed.emit(self.view)

    def _set_phase(self, phase: str, **changes) -> None:
        """A phase change resets the phase-specific fields (error, blocker, manual minimum, unusable tag) unless
        they are given."""
        merged = dict(self._PHASE_DEFAULTS)
        extra = {"quiet_error": False}
        extra.update(changes.pop("extra", {}))
        merged.update(changes)
        self._emit(phase=phase, extra=extra, **merged)

    def _on_language_changed(self, _code: str) -> None:
        if not self._closed:
            try:
                self.state_changed.emit(self.view)
            except RuntimeError:
                pass

    def _log_event(self, level: str, event: str, message: str, **fields) -> None:
        try:
            log_event(level, f"global_update.{event}", message, self._log, **fields)
        except Exception as exc:  # logging must never break the update flow
            logger.debug(f"global_update log failed: {exc!r}")

    # ───────────────────────────── startup ─────────────────────────────
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._reconcile_on_start()
        self._drop_staged_not_newer()
        self._janitor()
        QTimer.singleShot(JANITOR_DELAY_MS, self._janitor)
        if self.view.phase == "updated":
            return
        if self._pending_outcome == OUTCOME_IN_PROGRESS:
            # a second instance while Setup may still be running: show nothing and offer nothing (no second Setup)
            self._set_phase("idle")
            self._log_event("INFO", "check_skipped", _L('已跳过启动时的更新检查'), reason="install_in_progress")
            return
        if self._warning is None:
            staged = self.state.staged
            if staged is not None and not self.state.staged_is_stale(now_utc(), self.settings.staged_max_age_days):
                self._show_ready(staged)
            else:
                self._show_known_latest()
        # review r5 M8: the startup check also runs after a failed / unfinished install (a newer release
        # supersedes it; otherwise the warning stays)
        reason = self.state.check_skip_reason(now_utc(), self.settings.check_interval_hours,
                                              self.settings.check_retry_minutes)
        if reason:
            self._log_event("INFO", "check_skipped", _L('已跳过启动时的更新检查'), reason=reason)
            return
        QTimer.singleShot(max(0, int(self.settings.startup_delay_ms)), lambda: self.check(manual=False))

    def _drop_staged_not_newer(self) -> None:
        """A staged download that is not newer than the running build (this version or a newer one was installed in
        another way, e.g. by hand) is never offered: forget it here, the janitor that runs next removes its folder."""
        staged = self.state.staged
        if staged is None:
            return
        version = gr.parse_global_tag(str(staged.get("tag", "")))
        if version is not None and version > self.current:
            return
        logger.debug(f"global_update: staged {staged.get('tag')!r} is not newer than {gr.GLOBAL_VERSION}; dropped")
        self.state.clear_staged()

    def _show_ready(self, staged: dict, **changes) -> None:
        self._set_phase("ready", tag=staged["tag"], version_text=staged["tag"][1:], size=staged["size"],
                        published_at=staged.get("published_at", ""), **changes)

    def _known_latest(self) -> dict | None:
        latest = self.state.latest
        if latest is None:
            return None
        version = gr.parse_global_tag(latest["tag"])
        return latest if version is not None and version > self.current else None

    def _show_known_latest(self, **changes) -> None:
        latest = self._known_latest()
        if latest is None:
            if self.state.last_result and self.state.last_result != "ok":
                self._set_phase("check_failed", tag="", version_text="",
                                error_code=_CODE_BY_RESULT.get(self.state.last_result, "check.invalid_response"),
                                error_detail=self.state.last_error)
            else:
                self._set_phase("up_to_date" if self.state.last_check_utc else "idle", tag="", version_text="")
            return
        if self.state.skipped_tag == latest["tag"]:
            self._set_phase("skipped", tag=latest["tag"], version_text=latest["tag"][1:], size=latest["size"])
        else:
            self._set_phase("available", tag=latest["tag"], version_text=latest["tag"][1:], size=latest["size"],
                            published_at=latest.get("published_at", ""), **changes)

    def _reconcile_on_start(self) -> None:
        pending = self.state.pending
        if pending is None:
            self._pending_outcome = OUTCOME_NONE
            last = self.state.last_update
            if last is not None and not last.get("shown"):
                # shown on ONE start only (it stays for this session until dismissed)
                self.state.mark_last_update_shown()
                self._set_phase("updated", tag=last["to"], version_text=last["to"][1:], updated_from=last.get("from", ""))
            return
        log_text = None
        try:
            log_path = self.updates_dir / pending["tag"] / SETUP_LOG_NAME
            if log_path.is_file():
                log_text = decode_setup_log(log_path.read_bytes()[-65536:])
        except OSError:
            log_text = None
        outcome = self.state.reconcile(self.current, now_utc(), log_text)
        self._pending_outcome = outcome
        if outcome == OUTCOME_UPDATED:
            last = self.state.last_update or {}
            self.state.mark_last_update_shown()      # the "updated" banner belongs to this first start only
            self._log_event("INFO", "post_update_succeeded", _L('已更新到新版本'), to=last.get("to"), from_version=last.get("from"))
            self._set_phase("updated", tag=last.get("to", ""), version_text=last.get("to", "")[1:], updated_from=last.get("from", ""))
        elif outcome == OUTCOME_LAUNCH_FAILED:
            code = pending.get("error") or "install.launch_failed"
            self._log_event("ERROR", "post_update_failed", _L('上次更新未能启动安装程序'), code=code)
            self._enter_warning("launch_failed", pending["tag"], code, "")
        elif outcome == OUTCOME_NOT_COMPLETED:
            self._log_event("ERROR", "post_update_failed", _L('上次更新未完成'), code="postupdate.version_mismatch")
            self._enter_warning("not_completed", pending["tag"], "postupdate.version_mismatch", "")
        elif outcome == OUTCOME_IN_PROGRESS:
            self._log_event("INFO", "post_update_pending", _L('安装程序可能仍在运行'))

    def _warning_extra(self, phase: str, tag: str) -> dict:
        # Setup's log exists only when Setup ran (not_completed); a refused launch has none (review r5 L8)
        has_log = phase == "not_completed" and gr.parse_global_tag(tag) is not None and (
            (self.updates_dir / tag / SETUP_LOG_NAME).is_file())
        return {"install_log": bool(has_log)}

    def _enter_warning(self, phase: str, tag: str, code: str, detail: str) -> None:
        self._warning = (phase, tag, code, detail)
        self._set_phase(phase, tag=tag, version_text=tag[1:], error_code=code, error_detail=detail,
                        extra=self._warning_extra(phase, tag))

    def _restore_warning(self) -> bool:
        """The failed / unfinished install warning stays until the user acts or a newer release supersedes it."""
        warning = self._warning
        if warning is None:
            return False
        phase, tag, code, detail = warning
        names = {(self.state.staged or {}).get("tag"), (self.state.pending or {}).get("tag")}
        if tag not in names:
            self._warning = None
            return False
        self._set_phase(phase, tag=tag, version_text=tag[1:], error_code=code, error_detail=detail,
                        extra=self._warning_extra(phase, tag))
        return True

    def _clear_warning(self) -> None:
        self._warning = None
        self._pending_outcome = OUTCOME_NONE

    def _janitor(self) -> None:
        if self._closed:
            return
        try:
            if not self.updates_dir.is_dir() or L.is_reparse_point(self.updates_dir):
                return
            now = now_utc()
            if self.state.staged is not None and self.state.staged_is_stale(now, self.settings.staged_max_age_days):
                self.state.clear_staged()
            if self._pending_outcome == OUTCOME_IN_PROGRESS:
                return
            finished = (self.state.last_update or {}).get("to", "")
            busy = self._download_job.tag if self.is_downloading else ""
            names = [entry.name for entry in self.updates_dir.iterdir() if entry.is_dir() and entry.name != busy]
            for name in self.state.janitor_targets(names):
                folder = self.updates_dir / name
                if name == finished:
                    for source, target in ((SETUP_LOG_NAME, LAST_LOG_NAME), (NOTES_NAME, LAST_NOTES_NAME)):
                        try:
                            if (folder / source).is_file():
                                shutil.copyfile(folder / source, self.updates_dir / target)
                        except OSError:
                            pass
                _remove_tree(folder)
        except Exception as exc:
            logger.debug(f"global_update janitor: {exc!r}")

    # ───────────────────────────── check ─────────────────────────────
    @property
    def is_checking(self) -> bool:
        return self._check_job is not None and self._check_job.isRunning()

    def check(self, manual: bool = True, resume_tag: str = "") -> None:
        if self._closed or self.is_checking:
            return
        if self.view.phase in ("downloading", "verifying", "installing"):
            return
        self._manual = bool(manual)
        self._resume_tag = resume_tag
        self._log_event("INFO", "check_started", _L('开始检查更新'), trigger="manual" if manual else "startup",
                        current_version=gr.GLOBAL_VERSION)
        keep = resume_tag or (self.view.tag if self.view.phase in ("available", "manual_required") else "")
        self._set_phase("checking", tag=keep, version_text=keep[1:])
        job = _CheckJob(self.client, parent=self)
        job.result_ready.connect(self._on_checked)
        self._check_job = job
        job.start()

    def _on_checked(self, result) -> None:
        job = self._check_job
        self._check_job = None
        if job is not None:
            job.deleteLater()
        if self._closed:
            return
        download_after_check = self._download_after_check
        self._download_after_check = False
        resume_tag = self._resume_tag
        self._resume_tag = ""
        now = now_utc()
        if isinstance(result, UpdateError):
            self._on_check_failed(result, now, resume_tag)
            return
        outcome: CheckOutcome = result
        self.state.mark_checked(now, "ok")
        candidate = outcome.candidate
        self._log_event("INFO", "check_succeeded", _L('更新检查完成'), candidate=candidate.tag if candidate else "none",
                        seen=outcome.seen, rejected=len(outcome.rejected), unusable=outcome.unusable_tag or "none")
        if candidate is None:
            self.candidate = None
            self.state.clear_latest()
            if self._restore_warning():
                return
            staged = self.state.staged
            if staged is not None:
                self._show_ready(staged)
                return
            unusable = outcome.unusable_tag
            version = gr.parse_global_tag(unusable) if unusable else None
            self._set_phase("up_to_date", tag="", version_text="",
                            unusable_tag=unusable if version is not None and version > self.current else "",
                            error_code=outcome.unusable_code if unusable else "")
            return
        self.candidate = candidate
        discarded = self.state.set_latest(candidate.tag, candidate.installer.size, candidate.published_at)
        if discarded:
            _remove_tree(self.updates_dir / discarded)
        if self._restore_warning():
            return
        self._clear_warning()
        if candidate.manual_install_min:
            self._set_phase("manual_required", tag=candidate.tag, version_text=candidate.version.text,
                            size=candidate.installer.size, published_at=candidate.published_at,
                            manual_min=candidate.manual_install_min)
            if self._manual or self.state.notified_tag != candidate.tag:
                self._prompt_deadline = time.monotonic() + PROMPT_WINDOW_SECONDS
                self._maybe_prompt()
            return
        staged = self.state.staged
        if staged is not None and staged["tag"] == candidate.tag:
            self._show_ready(staged, published_at=candidate.published_at)
            return
        if self.state.skipped_tag == candidate.tag and not self._manual:
            self._set_phase("skipped", tag=candidate.tag, version_text=candidate.version.text, size=candidate.installer.size)
            return
        self._set_phase("available", tag=candidate.tag, version_text=candidate.version.text, size=candidate.installer.size,
                        published_at=candidate.published_at)
        if download_after_check:
            # [업데이트] was pressed on a tag remembered from an earlier session (or "download again"): the release
            # had to be validated first; the download starts now without another prompt
            self.state.set_notified(candidate.tag)
            self.start_download()
            return
        if self._manual or self.state.notified_tag != candidate.tag:
            self._prompt_deadline = time.monotonic() + PROMPT_WINDOW_SECONDS
            self._maybe_prompt()

    def _on_check_failed(self, result: UpdateError, now, resume_tag: str) -> None:
        self.last_error = result
        self.state.mark_checked(now, _RESULT_BY_CODE.get(result.code, "server" if result.code.startswith("check.http") else "invalid"),
                                error=f"{result.code} {result.detail}".strip(), retry_after_utc=result.retry_after_utc)
        self._log_event("WARNING" if not self._manual else "ERROR", "check_failed", _L('更新检查失败'), code=result.code)
        if self._restore_warning():
            return
        error = dict(error_code=result.code, error_detail=result.detail, retry_after_utc=self.state.rate_limit_reset_utc)
        staged = self.state.staged
        if staged is not None:
            self._show_ready(staged, **error)
            return
        latest = self._known_latest()
        if latest is not None and self.state.skipped_tag != latest["tag"]:
            # review r5 M1: a release known from an earlier check stays offered; the failure is reported with it
            # (in the banner only when the user asked: manual check or [업데이트] / [자세히 보기] on that release)
            self._show_known_latest(extra={"quiet_error": not (self._manual or resume_tag)}, **error)
            return
        self._set_phase("check_failed", tag="", version_text="", **error)

    def _maybe_prompt(self) -> None:
        if self._closed or self.view.phase not in ("available", "manual_required") or self.candidate is None:
            return
        if self._dialog is not None:
            return
        try:
            visible = self.window.isVisible()
        except RuntimeError:
            return
        # no automatic dialog in the middle of a game operation (the download itself is never blocked)
        if not visible or QApplication.activeModalWidget() is not None or self.blocker_text():
            if time.monotonic() < self._prompt_deadline:
                QTimer.singleShot(PROMPT_RETRY_MS, self._maybe_prompt)
            return
        self.state.set_notified(self.candidate.tag)
        self.show_dialog()

    # ───────────────────────────── dialog ─────────────────────────────
    def show_dialog(self, read_only: bool = False) -> None:
        if self._closed:
            return
        if (not read_only and self.view.phase in ("available", "manual_required")
                and (self.candidate is None or self.candidate.tag != self.view.tag)):
            # a tag remembered from an earlier session: fetch (and verify) its notes and assets first; the manual
            # check opens the dialog when it finds the candidate
            self.check(manual=True, resume_tag=self.view.tag)
            return
        from src.features.settings.global_update_dialog import GlobalUpdateDialog
        if self._dialog is not None:
            try:
                self._dialog.set_read_only(read_only)
                self._dialog.show()
                self._dialog.raise_()
                self._dialog.activateWindow()
                return
            except RuntimeError:
                self._dialog = None
        dialog = GlobalUpdateDialog(self.window, self, read_only=read_only)
        dialog.finished.connect(self._on_dialog_finished)
        self._dialog = dialog
        dialog.show()

    def _on_dialog_finished(self, _result: int) -> None:
        dialog = self._dialog
        self._dialog = None
        if dialog is not None:
            dialog.deleteLater()

    def dialog_closed_by_user(self) -> None:
        """Title-bar close / Esc of the dialog = 나중에 for the candidate phases."""
        if self.view.phase in ("available", "manual_required"):
            self.later()

    # ───────────────────────────── user decisions ─────────────────────────────
    def later(self) -> None:
        tag = self.view.tag
        if tag:
            if self.view.phase in ("available", "manual_required"):
                self.state.set_notified(tag)
            self._banner_hidden_tag = tag
            self._log_event("INFO", "later", _L('用户选择稍后更新'), tag=tag)
        self._emit()

    def skip(self) -> None:
        tag = self.view.tag
        if not tag or self.view.phase not in ("available", "ready", "manual_required"):
            return
        self.state.skip(tag)
        self.state.set_notified(tag)
        self._log_event("INFO", "skipped", _L('用户跳过此版本'), tag=tag)
        self._set_phase("skipped", tag=tag)

    def unskip(self) -> None:
        self.state.unskip()
        latest = self._known_latest()
        if latest is not None:
            self._banner_hidden_tag = ""
            self._set_phase("available", tag=latest["tag"], version_text=latest["tag"][1:], size=latest["size"],
                            published_at=latest.get("published_at", ""))
        else:
            self._set_phase("idle", tag="", version_text="")
            self.check(manual=True)

    def set_auto_check(self, enabled: bool) -> None:
        self.state.set_auto_check(bool(enabled))
        self._emit()

    # ───────────────────────────── blockers ─────────────────────────────
    def blocker_text(self) -> str:
        """Why the update cannot be INSTALLED right now ("" = nothing blocks it).  The download is never blocked."""
        window = self.window
        probe = getattr(window, "app_update_blocker", None)
        if callable(probe):
            try:
                key = probe()
            except Exception:
                key = None
            if key:
                return _blocker_sentence(key)
        loader = getattr(window, "_mod_plugin_loading_service", None)
        snapshot = None
        if loader is not None and callable(getattr(loader, "snapshot", None)):
            try:
                snapshot = loader.snapshot()
            except Exception:
                snapshot = None
        if snapshot is not None and (getattr(snapshot, "process_id", None) is not None
                                     or str(getattr(snapshot, "phase", "")) == "running"):
            return _L('Mod Loader 正在运行，请先停止。')
        for name in ("scanning_controller", "identification_controller"):
            owner = getattr(window, name, None)
            probe = getattr(owner, "is_running", None)
            try:
                if callable(probe) and probe():
                    return _L('扫描正在进行，请先完成。')
            except Exception:
                pass
        return ""

    def sync_running_text(self) -> str:
        service = getattr(self.window, "_inventory_sync_service", None)
        try:
            if service is not None and service.is_running:
                return _L('背包同步正在运行，更新时会停止。')
        except Exception:
            pass
        return ""

    # ───────────────────────────── download ─────────────────────────────
    @property
    def is_downloading(self) -> bool:
        return self._download_job is not None and self._download_job.isRunning()

    def has_running_job(self) -> bool:
        return self.is_checking or self.is_downloading

    def _acquire_lock(self) -> bool:
        if self._lock is None:
            self._lock = L.acquire_update_lock(self.updates_dir)
        return self._lock is not None

    def start_download(self) -> None:
        candidate = self.candidate
        if self._closed or self.view.phase not in ("available", "download_failed", "skipped"):
            return
        if self.is_downloading:
            return
        if candidate is None or (self.view.tag and candidate.tag != self.view.tag):
            # the phase was restored from state.json (no check in this session): validate the release again, then
            # download (``_on_checked`` continues here)
            self._download_after_check = True
            self.check(manual=True, resume_tag=self.view.tag)
            return
        if candidate.manual_install_min:
            return
        tag = candidate.tag
        tag_dir = self.updates_dir / tag
        try:
            self.updates_dir.mkdir(parents=True, exist_ok=True)
            L.check_folder(self.updates_dir)
            L.check_disk_space(self.updates_dir, candidate.installer.size)
            if not self._acquire_lock():
                raise UpdateError("install.busy")
            if tag_dir.exists() or L.is_reparse_point(tag_dir):
                if L.is_reparse_point(tag_dir):
                    tag_dir.unlink() if tag_dir.is_symlink() else tag_dir.rmdir()
                else:
                    _remove_tree(tag_dir)
            if tag_dir.exists():
                raise UpdateError("download.io", "cannot reset the update folder")
            tag_dir.mkdir(parents=True)
            L.check_folder(self.updates_dir, tag)
        except UpdateError as exc:
            self._on_download_done(exc)
            return
        except OSError as exc:
            self._on_download_done(UpdateError("download.io", type(exc).__name__))
            return
        if self.state.skipped_tag == tag:
            self.state.unskip()
        self._log_event("INFO", "download_started", _L('开始下载更新'), tag=tag, size=candidate.installer.size)
        self._speed_samples = [(time.monotonic(), 0)]
        self._set_phase("downloading", tag=tag, version_text=candidate.version.text, size=candidate.installer.size,
                        published_at=candidate.published_at, progress=0, downloaded=0, speed_bps=0.0, eta_seconds=-1)
        job = _DownloadJob(self.client, candidate, tag_dir, self.settings, self.current, parent=self)
        job.download_progress.connect(self._on_progress)
        job.result_ready.connect(self._on_download_done)
        self._download_job = job
        job.start()

    def cancel_download(self, wait_ms: int = 2000) -> None:
        job = self._download_job
        if job is None:
            return
        job.cancel()
        if job.isRunning():
            job.wait(wait_ms)

    def _on_progress(self, downloaded: int, total: int) -> None:
        if self._closed or self.view.phase != "downloading":
            return
        now = time.monotonic()
        self._speed_samples.append((now, downloaded))
        self._speed_samples = [(t, b) for t, b in self._speed_samples if now - t <= SPEED_WINDOW_SECONDS] or [(now, downloaded)]
        t0, b0 = self._speed_samples[0]
        speed = (downloaded - b0) / (now - t0) if now - t0 > 0.2 else 0.0
        eta = int((total - downloaded) / speed) if speed > 0 else -1
        percent = int(downloaded * 100 / total) if total > 0 else 0
        if downloaded >= total and total > 0:
            self._set_phase("verifying", progress=100, downloaded=downloaded, speed_bps=speed, eta_seconds=0)
        else:
            self._emit(progress=percent, downloaded=downloaded, speed_bps=speed, eta_seconds=eta)

    def _on_download_done(self, result) -> None:
        job = self._download_job
        self._download_job = None
        if job is not None:
            job.deleteLater()
        if self._closed:
            return
        if isinstance(result, UpdateError):
            self.last_error = result
            tag = self.view.tag
            tag_dir = self.updates_dir / tag if tag else None
            if (tag_dir is not None and gr.parse_global_tag(tag) is not None and tag_dir.is_dir()
                    and not L.is_reparse_point(tag_dir) and (self.state.staged or {}).get("tag") != tag):
                _remove_tree(tag_dir)
            self._release_lock()
            if result.code == "download.cancelled":
                # review r5 L6: a cancel is the user's choice, not an error -> back to "available"
                self._log_event("INFO", "download_cancelled", _L('用户取消了更新下载'), tag=tag)
                if self.candidate is not None and self.candidate.tag == tag:
                    self._set_phase("available", tag=tag, version_text=tag[1:], size=self.candidate.installer.size,
                                    published_at=self.candidate.published_at, progress=0, downloaded=0,
                                    speed_bps=0.0, eta_seconds=-1)
                    return
            elif result.kind == "verify":
                self._log_event("ERROR", "verify_failed", _L('更新文件校验失败'), code=result.code)
            else:
                self._log_event("ERROR", "download_failed", _L('更新下载失败'), code=result.code)
            if result.code == "verify.manual_install_required" and self.candidate is not None:
                self._set_phase("manual_required", tag=self.candidate.tag, version_text=self.candidate.version.text,
                                size=self.candidate.installer.size, published_at=self.candidate.published_at,
                                manual_min=result.detail)
                return
            self._set_phase("download_failed", error_code=result.code, error_detail=result.detail, progress=0,
                            downloaded=0, speed_bps=0.0, eta_seconds=-1)
            return
        self.state.set_staged(result["tag"], result["size"], result["sha256"], now_utc(), result.get("published_at", ""))
        self._log_event("INFO", "verify_succeeded", _L('更新文件已校验'), tag=result["tag"], sha256=result["sha256"],
                        key_id=result.get("key_id", ""))
        self._show_ready(self.state.staged, progress=100)

    def _release_lock(self) -> None:
        if self._lock is not None:
            self._lock.release()
            self._lock = None

    # backwards-compatible name (tests and the E2E harness call it on tear-down)
    _release_mutex = _release_lock

    # ───────────────────────────── install ─────────────────────────────
    def _refuse_install(self, tag: str, exc: UpdateError) -> None:
        """The launch gate refused while the window is open (review r5 H1): show it in place, close nothing."""
        self._log_event("ERROR", "install_launch_failed", _L('无法启动更新安装程序'), code=exc.code)
        self._release_lock()
        self._enter_warning("launch_failed", tag, exc.code, exc.detail)

    def _show_blocker(self, text: str) -> None:
        self._emit(blocker_text=text)
        if self._dialog is None and self.view.phase in ("ready", "launch_failed", "not_completed"):
            self.show_dialog()       # review r5 M2: the reason is always visible, wherever the click came from

    def request_install(self, relaunch: bool = True) -> bool:
        """[지금 설치하고 다시 시작] / [다시 시도]: blockers -> lock -> the whole launch gate (window still open) ->
        pending -> close the window (the launcher runs inside ``closeEvent`` after every service stopped).  Returns
        False when nothing was started."""
        if self._closed or self.view.phase not in ("ready", "launch_failed", "not_completed"):
            return False
        staged = self.state.staged
        if staged is None:
            # review r5 M8: nothing left to install (the download expired or was replaced): offer the download again
            tag = self.view.tag
            self.state.clear_pending()
            self._clear_warning()
            if tag and gr.parse_global_tag(tag) is not None:
                _remove_tree(self.updates_dir / tag)
            self._show_known_latest(error_code="install.download_missing", error_detail="")
            if self.view.phase != "available":
                self._set_phase("download_failed", tag=tag, version_text=tag[1:] if tag else "",
                                error_code="install.download_missing")
            return False
        blocker = self.blocker_text()
        if blocker:
            self._log_event("WARNING", "install_blocked", _L('当前无法更新'), reason=blocker)
            self._show_blocker(blocker)
            return False
        if not self._acquire_lock():
            self._show_blocker(_L('另一个窗口正在更新。'))
            return False
        tag = staged["tag"]
        try:
            L.preflight(updates_dir=self.updates_dir, tag=tag, staged=staged, settings=self.settings,
                        current_version=self.current)
        except UpdateError as exc:
            self._refuse_install(tag, exc)
            return False
        except Exception as exc:
            self._refuse_install(tag, UpdateError("install.launch_failed", type(exc).__name__))
            return False
        self.state.set_pending(tag, gr.GLOBAL_VERSION, staged["sha256"], now_utc(), relaunch)
        self._log_event("INFO", "install_confirmed", _L('用户确认安装更新'), tag=tag, relaunch=relaunch)
        self.window._global_update_launch = functools.partial(self.launch_staged_installer, relaunch)
        self._set_phase("installing", tag=tag, version_text=tag[1:])
        if self._dialog is not None:
            try:
                self._dialog.close()
            except RuntimeError:
                pass
        QTimer.singleShot(0, self.window.close)
        return True

    def launch_staged_installer(self, relaunch: bool) -> bool:
        """Runs inside ``MainWindow.closeEvent`` after the services stopped (design_final §8.4).  When the gate
        refuses at this last moment and the user asked for a restart, the program is started again so the failure
        is shown (review r5 H1)."""
        staged = self.state.staged
        pending = self.state.pending
        if staged is None or pending is None:
            return False
        tag = pending["tag"]
        lang = i18n_runtime.get_language()
        try:
            if not self._acquire_lock():
                raise UpdateError("install.busy")
            pid = L.launch(updates_dir=self.updates_dir, tag=tag, staged=staged, settings=self.settings, lang=lang,
                           relaunch=relaunch, current_version=self.current)
        except Exception as exc:
            code = exc.code if isinstance(exc, UpdateError) else "install.launch_failed"
            self.state.mark_launch_failed(code)
            self._log_event("ERROR", "install_launch_failed", _L('无法启动更新安装程序'),
                            code=code if isinstance(exc, UpdateError) else type(exc).__name__)
            self._release_lock()
            if relaunch:
                self._relaunch_self()
            return False
        self.state.mark_launched()
        self._log_event("INFO", "install_launched", _L('更新安装程序已启动'), tag=tag, lang=lang, pid=pid)
        self._release_lock()
        application = QApplication.instance()
        if application is not None:
            QTimer.singleShot(0, application.quit)
        return True

    def _relaunch_self(self) -> None:
        if not getattr(sys, "frozen", False):
            return       # only the frozen program restarts itself (never a test interpreter)
        try:
            ok = QProcess.startDetached(sys.executable, list(sys.argv[1:]), str(Path(sys.executable).parent))
            self._log_event("INFO", "relaunch_after_launch_failure", _L('安装程序未能启动，已重新打开程序'),
                            started=bool(ok[0] if isinstance(ok, tuple) else ok))
        except Exception as exc:
            logger.warning(f"global_update relaunch failed: {exc!r}")

    def delete_download(self) -> None:
        tag = self.view.tag or (self.state.staged or {}).get("tag") or (self.state.pending or {}).get("tag")
        if tag and gr.parse_global_tag(tag) is not None:
            _remove_tree(self.updates_dir / tag)
        self.state.clear_pending()
        self.state.clear_staged()
        self._clear_warning()
        self._release_lock()
        self._set_phase("idle", tag="", version_text="", size=0)
        self.check(manual=True)

    def redownload(self) -> None:
        """[다시 내려받기]: the downloaded files are unusable (review r5 H1) -> delete them, validate the release
        again and download it again without another prompt."""
        if self.is_downloading:
            return
        tag = self.view.tag or (self.state.staged or {}).get("tag") or (self.state.pending or {}).get("tag")
        if tag and gr.parse_global_tag(tag) is not None:
            _remove_tree(self.updates_dir / tag)
        self.state.clear_pending()
        self.state.clear_staged()
        self._clear_warning()
        self._release_lock()
        self._download_after_check = True
        self._set_phase("idle", tag="", version_text="", size=0)
        self.check(manual=True)

    def acknowledge_updated(self) -> None:
        self.state.mark_last_update_shown()
        self._set_phase("idle", tag="", version_text="", updated_from="")

    # ───────────────────────────── close handling ─────────────────────────────
    def close_decision(self, offer_install: bool = True) -> str:
        """Called by ``MainWindow.closeEvent`` after the page-transition defer and BEFORE anything irreversible is
        shut down (and by the theme restart with ``offer_install=False`` before it starts the new instance):
        ``"cancel"`` keeps the window open and fully working.  Once the user let the close proceed, later
        re-entries of ``closeEvent`` (the page-task defer re-calls ``close`` after 25 ms) proceed without asking."""
        if self._closed or self._close_confirmed:
            return "proceed"
        if self.view.phase == "installing":
            self._close_confirmed = True
            return "proceed"
        if self.is_downloading:
            box = QMessageBox(self.window)
            box.setWindowTitle(_L('软件更新'))
            box.setText(_L('正在下载更新，要取消下载并退出吗？'))
            quit_button = box.addButton(_L('取消下载并退出'), QMessageBox.AcceptRole)
            keep_button = box.addButton(_L('继续下载'), QMessageBox.RejectRole)
            box.setDefaultButton(keep_button)
            box.setEscapeButton(keep_button)
            box.exec()
            if box.clickedButton() is not quit_button:
                return "cancel"
            self.cancel_download()
        if offer_install and self.view.phase == "ready" and self.state.staged is not None and not self._closing_prompted:
            self._closing_prompted = True
            box = QMessageBox(self.window)
            box.setWindowTitle(_L('软件更新'))
            box.setText(_L('更新已准备好，要在退出时安装吗？'))
            install_button = box.addButton(_L('安装后退出'), QMessageBox.AcceptRole)
            quit_button = box.addButton(_L('直接退出'), QMessageBox.DestructiveRole)
            cancel_button = box.addButton(_L('取消'), QMessageBox.RejectRole)
            box.setDefaultButton(install_button)
            box.setEscapeButton(cancel_button)
            box.exec()
            clicked = box.clickedButton()
            self._closing_prompted = False
            if clicked is cancel_button or clicked is None:
                return "cancel"
            if clicked is install_button:
                blocker = self.blocker_text()
                if blocker:
                    QMessageBox.information(self.window, _L('软件更新'), _LF('当前无法更新：{0}').format((blocker)))
                    return "cancel"
                if not self._acquire_lock():
                    QMessageBox.information(self.window, _L('软件更新'), _L('另一个窗口正在更新。'))
                    return "cancel"
                staged = self.state.staged
                try:
                    L.preflight(updates_dir=self.updates_dir, tag=staged["tag"], staged=staged, settings=self.settings,
                                current_version=self.current)
                except Exception as exc:
                    error = exc if isinstance(exc, UpdateError) else UpdateError("install.launch_failed", type(exc).__name__)
                    self._refuse_install(staged["tag"], error)
                    from src.features.settings.global_update_texts import error_sentence
                    QMessageBox.information(self.window, _L('软件更新'), error_sentence(error.code, error.detail))
                    return "cancel"
                self.state.set_pending(staged["tag"], gr.GLOBAL_VERSION, staged["sha256"], now_utc(), False)
                self._log_event("INFO", "install_confirmed", _L('用户确认安装更新'), tag=staged["tag"], relaunch=False)
                self.window._global_update_launch = functools.partial(self.launch_staged_installer, False)
        self._close_confirmed = True
        return "proceed"

    def reset_close_decision(self) -> None:
        """The close that ``close_decision`` allowed did not happen (e.g. the theme restart failed)."""
        if not self._closed:
            self._close_confirmed = False

    def close(self) -> None:
        self._closed = True
        unfinished = self._download_job.tag if self._download_job is not None else ""
        self.cancel_download()
        if (unfinished and gr.parse_global_tag(unfinished) is not None
                and (self.state.staged or {}).get("tag") != unfinished
                and not L.is_reparse_point(self.updates_dir / unfinished)):
            # quitting during a download: the result slot no longer runs once the controller is closed, so the
            # partial download is removed here (a file a stalled job still holds is left to the next start's janitor)
            _remove_tree(self.updates_dir / unfinished)
        if self._dialog is not None:
            try:
                self._dialog.close()
            except RuntimeError:
                pass
            self._dialog = None

    # ───────────────────────────── links / notes / log ─────────────────────────────
    def open_releases_page(self) -> None:
        opener = getattr(self.window, "_open_global_releases", None)
        if callable(opener):
            opener()

    def open_release_html(self) -> None:
        url = self.candidate.html_url if self.candidate is not None else gr.GLOBAL_RELEASES_URL
        if not gr.repo_url_allowed(url):
            url = gr.GLOBAL_RELEASES_URL
        opener = getattr(self.window, "_open_url", None)
        if callable(opener):
            opener(url)

    def install_log_path(self) -> Path | None:
        """Setup's log of the attempt the current warning is about; ``None`` when Setup never ran (a refused or
        failed launch) or the log is gone (review r5 L8)."""
        if self.view.phase == "launch_failed":
            return None
        tag = self.view.tag or (self.state.pending or {}).get("tag", "")
        if not tag or gr.parse_global_tag(tag) is None:
            return None
        path = self.updates_dir / tag / SETUP_LOG_NAME
        if path.is_file():
            return path
        last = self.updates_dir / LAST_LOG_NAME
        if last.is_file() and (self.state.last_update or {}).get("to") == tag:
            return last
        return None

    def install_log_text(self) -> str:
        path = self.install_log_path()
        if path is None:
            return ""
        try:
            with path.open("rb") as handle:
                size = path.stat().st_size
                handle.seek(max(0, size - INSTALL_LOG_MAX))
                raw = handle.read()
        except OSError:
            return ""
        text = decode_setup_log(raw)
        return text if size <= INSTALL_LOG_MAX else "…\n" + text

    def open_install_log(self) -> None:
        """Shown inside the program (review r5 I1: the elevated process hands no file to the Windows shell)."""
        text = self.install_log_text()
        if not text:
            return
        from src.features.settings.global_update_dialog import show_install_log
        show_install_log(self.window, text)

    def notes_markdown(self) -> str:
        """Release notes of the current candidate / staged / last update in the user's language; a release body the
        signed manifest does not cover is replaced by a fixed sentence (review r5 F1)."""
        lang = i18n_runtime.get_language()
        if self.candidate is not None and self.candidate.tag == self.view.tag:
            if not self.candidate.notes_verified:
                return unverified_notes_text()
            return notes_for_language(self.candidate.body, lang)
        tag = self.view.tag or (self.state.last_update or {}).get("to", "")
        for path in ((self.updates_dir / tag / NOTES_NAME) if tag else None, self.updates_dir / LAST_NOTES_NAME):
            if path is None or not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and (not tag or data.get("tag") == tag):
                    if data.get("notes_verified") is not True:
                        return unverified_notes_text()
                    return notes_for_language(data.get("body", ""), lang)
            except (OSError, ValueError):
                continue
        return notes_for_language("", lang)

    def candidate_meta(self) -> tuple[str, int]:
        if self.candidate is not None and self.candidate.tag == self.view.tag:
            return self.candidate.published_at, self.candidate.installer.size
        return self.view.published_at, self.view.size
