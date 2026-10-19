# Global 업데이트의 앱 전역 상태 파일 (updates\state.json; 경로를 담지 않음)
"""App-wide update state in ``<updates dir>\\state.json`` (design_final §7.3, §8.6).

The file never contains a path: every file name is derived from the tag at use time, so a rewritten state can only
change *when* the app asks and *which tag* it looks at; the launcher re-verifies the staged file from scratch and
refuses anything that is not newer than the running build.  Reads validate every field; a corrupt file loads as
defaults with a warning and is never a crash.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Iterable

from src.app.global_release import GlobalVersion, parse_global_tag
from src.utils.atomic_json import AtomicJsonFile
from src.utils.logger import logger

STATE_FORMAT = 1
STATE_FILE_NAME = "state.json"
LAST_LOG_NAME = "last_update.log"
LAST_NOTES_NAME = "last_update_notes.json"
SETUP_LOG_NAME = "setup.log"
NOTES_NAME = "notes.json"
TMP_DIR_NAME = "tmp"
PENDING_TIMEOUT = _dt.timedelta(minutes=15)
INNO_TERMINAL_MARKERS = ("Installation process succeeded", "Setup failed", "Fatal exception", "Rolling back", "Log closed.")
CHECK_RESULTS = ("ok", "offline", "rate_limited", "server", "timeout", "invalid", "tls", "no_release", "untrusted")

OUTCOME_UPDATED = "updated"
OUTCOME_LAUNCH_FAILED = "launch_failed"
OUTCOME_NOT_COMPLETED = "not_completed"
OUTCOME_IN_PROGRESS = "in_progress"
OUTCOME_NONE = "none"
# an error code as the pipeline writes it (models.UpdateError.code); anything else read from the file is dropped
# (review r5 F6: state.json values never reach a label unvalidated)
ERROR_CODE_RE = re.compile(r"[a-z]+\.[a-z0-9_]+", re.ASCII)

_UTC = _dt.timezone.utc


def utc_text(moment: _dt.datetime) -> str:
    return moment.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: object) -> _dt.datetime | None:
    if not isinstance(text, str) or not text:
        return None
    try:
        return _dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC)
    except ValueError:
        return None


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_UTC)


def decode_setup_log(raw: bytes) -> str:
    """Inno writes /LOG files as UTF-16 with a BOM on this platform; tolerate UTF-8 as well."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8", "replace")


def setup_log_is_terminal(text: str | None) -> bool:
    return bool(text) and any(marker in text for marker in INNO_TERMINAL_MARKERS)


def _tag_or_empty(value: object) -> str:
    return value if isinstance(value, str) and parse_global_tag(value) is not None else ""


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _latest(value: object) -> dict | None:
    if not isinstance(value, dict) or not _tag_or_empty(value.get("tag")):
        return None
    return {"tag": value["tag"], "size": _int(value.get("size")), "published_at": _str(value.get("published_at"))}


def _code(value: object) -> str:
    return value if isinstance(value, str) and ERROR_CODE_RE.fullmatch(value) else ""


def _utc(value: object) -> str:
    return value if isinstance(value, str) and parse_utc(value) is not None else ""


def _staged(value: object) -> dict | None:
    if not isinstance(value, dict) or not _tag_or_empty(value.get("tag")):
        return None
    sha = _str(value.get("sha256"))
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        return None
    return {"tag": value["tag"], "size": _int(value.get("size")), "sha256": sha,
            "verified_utc": _str(value.get("verified_utc")), "published_at": _utc(value.get("published_at"))}


def _pending(value: object) -> dict | None:
    if not isinstance(value, dict) or not _tag_or_empty(value.get("tag")):
        return None
    return {"tag": value["tag"], "from": _str(value.get("from")), "sha256": _str(value.get("sha256")),
            "started_utc": _str(value.get("started_utc")), "launched": _bool(value.get("launched"), False),
            "relaunch": _bool(value.get("relaunch"), True), "error": _code(value.get("error"))}


def _last_update(value: object) -> dict | None:
    if not isinstance(value, dict) or not _tag_or_empty(value.get("to")):
        return None
    return {"to": value["to"], "from": _str(value.get("from")), "finished_utc": _str(value.get("finished_utc")),
            "shown": _bool(value.get("shown"), False)}


def _defaults() -> dict:
    return {
        "format": STATE_FORMAT, "auto_check": True, "last_check_utc": "", "last_attempt_utc": "", "last_result": "",
        "last_error": "",
        "rate_limit_reset_utc": "", "latest": None, "notified_tag": "", "skipped_tag": "", "staged": None,
        "pending": None, "last_update": None,
    }


class GlobalUpdateState:
    """Loads at construction; every mutator saves immediately (one small atomic write)."""

    def __init__(self, updates_dir: str | Path) -> None:
        self.updates_dir = Path(updates_dir)
        self._file = AtomicJsonFile(self.updates_dir / STATE_FILE_NAME)
        self.data: dict = _defaults()
        self.load()

    # ── persistence ──
    def load(self) -> None:
        raw = self._file.load(default=None)
        data = _defaults()
        if raw is None:
            self.data = data
            return
        for key, value in raw.items():
            if key not in data:
                data[key] = value                      # unknown keys are kept verbatim
        data["auto_check"] = _bool(raw.get("auto_check"), True)
        data["last_check_utc"] = _utc(raw.get("last_check_utc"))
        result = _str(raw.get("last_result"))
        data["last_result"] = result if result in CHECK_RESULTS else ""
        if "last_attempt_utc" in raw:
            data["last_attempt_utc"] = _utc(raw.get("last_attempt_utc"))
        else:
            # files written before review r5: last_check_utc was the last ATTEMPT, successful or not
            data["last_attempt_utc"] = data["last_check_utc"]
            if data["last_result"] not in ("ok", ""):
                data["last_check_utc"] = ""
        data["last_error"] = _str(raw.get("last_error"))[:500]
        data["rate_limit_reset_utc"] = _str(raw.get("rate_limit_reset_utc")) if parse_utc(raw.get("rate_limit_reset_utc")) else ""
        data["latest"] = _latest(raw.get("latest"))
        data["notified_tag"] = _tag_or_empty(raw.get("notified_tag"))
        data["skipped_tag"] = _tag_or_empty(raw.get("skipped_tag"))
        data["staged"] = _staged(raw.get("staged"))
        data["pending"] = _pending(raw.get("pending"))
        data["last_update"] = _last_update(raw.get("last_update"))
        if raw.get("format") != STATE_FORMAT:
            logger.warning(f"global_update: state format {raw.get('format')!r} read as format {STATE_FORMAT}")
        self.data = data

    def save(self) -> None:
        self.data["format"] = STATE_FORMAT
        self._file.save(self.data)

    # ── read ──
    @property
    def auto_check(self) -> bool:
        return bool(self.data["auto_check"])

    @property
    def last_check_utc(self) -> str:
        return self.data["last_check_utc"]

    @property
    def last_attempt_utc(self) -> str:
        return self.data["last_attempt_utc"]

    @property
    def last_result(self) -> str:
        return self.data["last_result"]

    @property
    def last_error(self) -> str:
        return self.data["last_error"]

    @property
    def rate_limit_reset_utc(self) -> str:
        return self.data["rate_limit_reset_utc"]

    @property
    def latest(self) -> dict | None:
        return self.data["latest"]

    @property
    def notified_tag(self) -> str:
        return self.data["notified_tag"]

    @property
    def skipped_tag(self) -> str:
        return self.data["skipped_tag"]

    @property
    def staged(self) -> dict | None:
        return self.data["staged"]

    @property
    def pending(self) -> dict | None:
        return self.data["pending"]

    @property
    def last_update(self) -> dict | None:
        return self.data["last_update"]

    def check_skip_reason(self, now: _dt.datetime, interval_hours: float, retry_minutes: float = 60) -> str:
        """"" when the startup check is due (review r5 M7: only a SUCCESSFUL check uses up the day):
        ``auto_check_off``; ``rate_limited`` until GitHub's reset time; ``throttled`` within ``interval_hours`` of
        the last successful check (a clock moved back by more than an interval resets it); ``retry_later`` within
        ``retry_minutes`` of a failed attempt."""
        if not self.auto_check:
            return "auto_check_off"
        interval = _dt.timedelta(hours=interval_hours)
        reset = parse_utc(self.rate_limit_reset_utc)
        if reset is not None and now < reset <= now + interval:
            return "rate_limited"
        last = parse_utc(self.last_check_utc)
        if last is not None and -interval < now - last < interval:
            return "throttled"
        attempt = parse_utc(self.last_attempt_utc)
        retry = _dt.timedelta(minutes=retry_minutes)
        if self.last_result not in ("ok", "") and attempt is not None and -retry < now - attempt < retry:
            return "retry_later"
        return ""

    def is_check_due(self, now: _dt.datetime, interval_hours: float, retry_minutes: float = 60) -> bool:
        return self.check_skip_reason(now, interval_hours, retry_minutes) == ""

    def staged_is_stale(self, now: _dt.datetime, max_age_days: int) -> bool:
        staged = self.staged
        if staged is None:
            return False
        verified = parse_utc(staged.get("verified_utc"))
        return verified is None or now - verified > _dt.timedelta(days=max_age_days)

    def tag_dir(self, tag: str) -> Path:
        if parse_global_tag(tag) is None:
            raise ValueError(f"not a Global tag: {tag!r}")
        return self.updates_dir / tag

    def janitor_targets(self, entries: Iterable[str]) -> list[str]:
        """Tag folders that are neither staged nor pending (never the state file or the kept logs)."""
        keep = {(self.staged or {}).get("tag"), (self.pending or {}).get("tag")}
        return sorted(name for name in entries if parse_global_tag(name) is not None and name not in keep)

    # ── write ──
    def set_auto_check(self, enabled: bool) -> None:
        self.data["auto_check"] = bool(enabled)
        self.save()

    def mark_checked(self, now: _dt.datetime, result: str, error: str = "", retry_after_utc: str | None = None) -> None:
        """``last_attempt_utc`` = every check; ``last_check_utc`` = the last SUCCESSFUL one (shown as "last checked"
        and used by the daily throttle)."""
        self.data["last_attempt_utc"] = utc_text(now)
        if result == "ok":
            self.data["last_check_utc"] = utc_text(now)
        self.data["last_result"] = result if result in CHECK_RESULTS else "invalid"
        self.data["last_error"] = str(error or "")[:500]
        self.data["rate_limit_reset_utc"] = retry_after_utc if parse_utc(retry_after_utc) else ""
        self.save()

    def set_latest(self, tag: str, size: int, published_at: str) -> str:
        """Records the newest candidate.  A newer tag resets ``skipped_tag`` and discards an older ``staged``;
        returns the discarded staged tag ("" if none) so the caller can delete its folder."""
        version = parse_global_tag(tag)
        if version is None:
            raise ValueError(f"not a Global tag: {tag!r}")
        discarded = ""
        skipped = parse_global_tag(self.skipped_tag)
        if skipped is not None and version > skipped:
            self.data["skipped_tag"] = ""
        staged = self.staged
        if staged is not None:
            staged_version = parse_global_tag(staged["tag"])
            if staged_version is not None and version > staged_version:
                discarded = staged["tag"]
                self.data["staged"] = None
        pending = self.pending
        if pending is not None:
            pending_version = parse_global_tag(pending["tag"])
            if pending_version is not None and version > pending_version:
                # review r5 M8: a failed / unfinished install of an older tag is superseded by the newer release
                discarded = discarded or pending["tag"]
                self.data["pending"] = None
        self.data["latest"] = {"tag": tag, "size": _int(size), "published_at": _str(published_at)}
        self.save()
        return discarded

    def clear_latest(self) -> None:
        self.data["latest"] = None
        self.save()

    def set_notified(self, tag: str) -> None:
        self.data["notified_tag"] = _tag_or_empty(tag)
        self.save()

    def skip(self, tag: str) -> None:
        self.data["skipped_tag"] = _tag_or_empty(tag)
        self.save()

    def unskip(self) -> None:
        self.data["skipped_tag"] = ""
        self.save()

    def set_staged(self, tag: str, size: int, sha256: str, now: _dt.datetime, published_at: str = "") -> None:
        staged = _staged({"tag": tag, "size": size, "sha256": sha256, "verified_utc": utc_text(now),
                          "published_at": published_at})
        if staged is None:
            raise ValueError("invalid staged record")
        self.data["staged"] = staged
        self.save()

    def clear_staged(self) -> None:
        self.data["staged"] = None
        self.save()

    def set_pending(self, tag: str, from_version: str, sha256: str, now: _dt.datetime, relaunch: bool) -> None:
        pending = _pending({"tag": tag, "from": from_version, "sha256": sha256, "started_utc": utc_text(now),
                            "launched": False, "relaunch": bool(relaunch), "error": ""})
        if pending is None:
            raise ValueError("invalid pending record")
        self.data["pending"] = pending
        self.save()

    def mark_launched(self) -> None:
        if self.pending is not None:
            self.data["pending"]["launched"] = True
            self.data["pending"]["error"] = ""
            self.save()

    def mark_launch_failed(self, error_code: str) -> None:
        if self.pending is not None:
            self.data["pending"]["launched"] = False
            self.data["pending"]["error"] = _code(error_code) or "install.launch_failed"
            self.save()

    def clear_pending(self) -> None:
        self.data["pending"] = None
        self.save()

    def mark_last_update_shown(self) -> None:
        if self.last_update is not None:
            self.data["last_update"]["shown"] = True
            self.save()

    def reconcile(self, current: GlobalVersion, now: _dt.datetime, setup_log_text: str | None) -> str:
        """Outcome of a previous install attempt (design_final §8.6).  ``pending`` stays for the user to retry or
        delete unless the update succeeded."""
        pending = self.pending
        if pending is None:
            return OUTCOME_NONE
        target = parse_global_tag(pending["tag"])
        if target is not None and target == current:
            self.data["last_update"] = {"to": pending["tag"], "from": pending["from"], "finished_utc": utc_text(now),
                                        "shown": False}
            self.data["staged"] = None
            self.data["pending"] = None
            self.data["latest"] = None
            self.data["notified_tag"] = ""
            self.save()
            return OUTCOME_UPDATED
        if target is not None and target < current:
            # superseded: a newer build was installed by other means since; nothing to retry or report
            self.data["staged"] = None
            self.data["pending"] = None
            self.save()
            return OUTCOME_NONE
        if not pending["launched"]:
            return OUTCOME_LAUNCH_FAILED
        started = parse_utc(pending["started_utc"])
        if started is None or setup_log_is_terminal(setup_log_text) or now - started > PENDING_TIMEOUT:
            return OUTCOME_NOT_COMPLETED
        return OUTCOME_IN_PROGRESS
