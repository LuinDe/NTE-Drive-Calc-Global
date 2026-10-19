# Global 업데이트의 자료형과 오류 코드 (순수 모듈)
"""Types shared by the Global update modules.  No I/O, no Qt.

Error codes are stable ASCII constants (``UpdateError.code``); the user-visible sentence is chosen by the UI from
the code, so a code is never wrapped by the localisation layer and never compared with a translated text.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.app.global_release import GlobalVersion


class UpdateError(Exception):
    """One failure of the update pipeline, identified by a dotted code (design_final §12)."""

    def __init__(self, code: str, detail: str = "", retry_after_utc: str | None = None) -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = str(code)
        self.detail = str(detail or "")
        self.retry_after_utc = retry_after_utc

    @property
    def kind(self) -> str:
        """``check`` / ``verify`` / ``download`` / ``install`` / ``postupdate``."""
        return self.code.split(".", 1)[0]


@dataclass(frozen=True)
class AssetInfo:
    name: str
    size: int
    sha256: str              # 64 lower-case hex digits from the API ``digest``; "" when the API gave none
    url: str                 # equals the URL constructed from the tag (checked at selection time)
    content_type: str = ""
    state: str = ""


@dataclass(frozen=True)
class ReleaseCandidate:
    tag: str
    version: GlobalVersion
    name: str
    html_url: str
    published_at: str
    body: str
    installer: AssetInfo
    manifest: AssetInfo | None = None
    signature: AssetInfo | None = None
    # filled by the check after the signed manifest verified (design_final §6.2, review r5 F1): the exact bytes the
    # download step re-verifies and stores, whether the release body matches the signed notes digest, and the oldest
    # running version allowed to install in-app when this build is older ("" = installable here)
    manifest_bytes: bytes = b""
    signature_bytes: bytes = b""
    notes_verified: bool = False
    manual_install_min: str = ""


@dataclass(frozen=True)
class Manifest:
    format: int
    product: str
    tag: str
    global_version: str
    upstream_base: str
    installer_name: str
    installer_size: int
    installer_sha256: str
    exe_sha256: str
    min_global_version: str
    published_utc: str
    key_id: str = ""
    notes_sha256: str = ""          # sha256 of the normalised release body (verify.notes_digest); "" = not bound
    manual_install_min: str = ""    # set by verify_manifest(allow_manual=True) instead of raising


@dataclass(frozen=True)
class CheckOutcome:
    """Result of one release check: the candidate (newer than the running build) or ``None``."""

    candidate: ReleaseCandidate | None
    seen: int = 0
    rejected: tuple[tuple[str, str], ...] = ()   # (tag or "?", reason) for the log
    latest_seen_tag: str = ""                     # newest tag that parsed, even when not offered
    unusable_tag: str = ""                        # newest tag is newer than this build but failed validation
    unusable_code: str = ""                       # why (verify.* / check.* code or a selection reason)


# UI projection (rendered by the dialog, the settings card and the home banner)
PHASES = (
    "idle", "checking", "up_to_date", "available", "skipped", "downloading", "verifying", "ready", "installing",
    "check_failed", "download_failed", "updated", "launch_failed", "not_completed", "manual_required",
)


@dataclass(frozen=True)
class UpdateState:
    phase: str = "idle"
    tag: str = ""                       # candidate / staged / pending tag of the phase
    version_text: str = ""              # tag without "v"
    size: int = 0
    published_at: str = ""
    progress: int = 0                   # percent 0..100 while downloading
    downloaded: int = 0
    speed_bps: float = 0.0
    eta_seconds: int = -1
    error_code: str = ""
    error_detail: str = ""
    blocker_text: str = ""
    last_check_utc: str = ""
    auto_check: bool = True
    skipped_tag: str = ""
    staged_tag: str = ""
    retry_after_utc: str = ""
    updated_from: str = ""
    manual_min: str = ""                # manual_required: oldest Global version that can install it in-app
    unusable_tag: str = ""              # up_to_date: a newer release exists but failed the in-app checks
    extra: dict = field(default_factory=dict)

    def replace(self, **changes) -> "UpdateState":
        from dataclasses import replace as _replace
        return _replace(self, **changes)
