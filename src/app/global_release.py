# Global 빌드의 버전 정체성과 업데이트 채널 상수 (NTE Drive Calc Global 추가 모듈; 순수 함수, I/O 없음)
"""Version identity and update-channel constants of NTE Drive Calc Global.

The Global build has its own version grammar ``<major>.<minor>.<patch>[-global.<n>]`` (tag ``v`` + version):
plain ``x.y.z`` since Global 2.3.2, the ``-global.<n>`` form for the earlier releases (2.3.0-global.1,
2.3.1-global.1, 2.3.1-global.2).  The Global version number is independent of the original project's.
``src.app.version.__version__`` stays the upstream base the build is derived from: it feeds the native
client version, battle bundles and the workshop User-Agent and is shown only as information.

Ordering is the tuple ``(major, minor, patch, n)`` with ``n = 0`` for a plain version, so
2.3.1-global.1 < 2.3.1-global.2 < 2.3.2 < 2.3.2-global.1 < 2.3.3.

Everything here is a compile-time constant or a pure function: no file, network or Qt access, so the module can
be imported by the release tooling and by tests alike.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from src.app.version import __version__

# ── identity (bumped every release; the tag is "v" + GLOBAL_VERSION) ─────────────────────────────────────────
GLOBAL_VERSION = "2.3.3"
UPSTREAM_BASE = __version__                      # "2.3.1": information only, never compared with GLOBAL_VERSION

# ── update channel: ONLY the GitHub Releases of this repository ──────────────────────────────────────────────
GLOBAL_REPO_OWNER = "LuinDe"
GLOBAL_REPO_NAME = "NTE-Drive-Calc-Global"
GLOBAL_REPO_SLUG = f"{GLOBAL_REPO_OWNER}/{GLOBAL_REPO_NAME}"
GLOBAL_RELEASE_AUTHORS = ("LuinDe",)             # tripwire: releases by any other login are ignored
GLOBAL_PROJECT_URL = f"https://github.com/{GLOBAL_REPO_SLUG}"
GLOBAL_RELEASES_URL = GLOBAL_PROJECT_URL + "/releases"
GLOBAL_ISSUES_URL = GLOBAL_PROJECT_URL + "/issues"
GLOBAL_API_BASE = "https://api.github.com"
GLOBAL_DOWNLOAD_BASE = "https://github.com"
ALLOWED_DOWNLOAD_HOSTS = ("github.com", "api.github.com")
ALLOWED_DOWNLOAD_HOST_SUFFIXES = (".githubusercontent.com",)

# ── release signing (Ed25519 public keys, OpenSSH "sshsig" format; at most two slots during a rotation) ──────
# The maintainer pins the public key line here (key id, base64 of the 32 raw key bytes as printed by
# ``ssh-keygen`` after ``ssh-ed25519``).  With no key pinned every signed-manifest check fails closed, so the
# release build cannot offer an update until the key ceremony of the release checklist has been done.
RELEASE_SIGNING_KEYS: tuple[tuple[str, str], ...] = (("nte-global-release", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDrNqNVxLCFuc+fq7jN0vTL2Aphh+VzGkOmQZf74TscN"),)
RELEASE_SIG_NAMESPACE = "nte-drive-calc-global-release"

INSTALLER_SIZE_MIN = 50 * 2**20
INSTALLER_SIZE_MAX = 1024 * 2**20
MANIFEST_SIZE_MAX = 64 * 1024
RELEASE_BODY_MAX = 64 * 1024
API_BODY_MAX = 8 * 2**20
API_PER_PAGE = 30
CHECK_INTERVAL_HOURS = 20                        # "once a day" for a daily user (24 h exactly skips every other day)
CHECK_RETRY_MINUTES = 60                         # a failed startup check is retried at the next start after 1 h
STAGED_MAX_AGE_DAYS = 14
STARTUP_DELAY_MS = 4000
DISK_SPACE_MARGIN = 1536 * 2**20                 # free space required beyond the installer (Setup unpacks the payload)
INSTALLER_CONTENT_TYPES = (
    "application/x-msdownload",
    "application/octet-stream",
    "application/vnd.microsoft.portable-executable",
)

_PLAIN = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
_VERSION_CORE = _PLAIN + r"(?:-global\.([1-9][0-9]*))?"     # suffix absent -> n = 0; present -> n >= 1
# fullmatch only (not "$": "$" also matches before a trailing newline); re.ASCII: no full-width/other digits
_TAG_RE = re.compile(r"v" + _VERSION_CORE, re.ASCII)
_VERSION_RE = re.compile(_VERSION_CORE, re.ASCII)
_NUMERIC_MAX = 65535


class GlobalVersion(NamedTuple):
    """``n == 0``: plain ``x.y.z``; ``n >= 1``: ``x.y.z-global.n``.  Compared as the tuple."""

    major: int
    minor: int
    patch: int
    n: int

    @property
    def text(self) -> str:
        return self.base if self.n == 0 else f"{self.base}-global.{self.n}"

    @property
    def tag(self) -> str:
        return "v" + self.text

    @property
    def base(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def _from_match(match: re.Match | None) -> GlobalVersion | None:
    if match is None:
        return None
    try:
        parts = tuple(0 if group is None else int(group) for group in match.groups())
    except ValueError:
        return None
    if any(part > _NUMERIC_MAX for part in parts):
        return None
    return GlobalVersion(*parts)


def parse_global_tag(tag: object) -> GlobalVersion | None:
    """``v2.3.2`` / ``v2.3.1-global.2`` -> GlobalVersion; anything else (no ``v``, other grammar, whitespace,
    leading zeros, ``-global.0``, non-ASCII digits, a part above 65535) -> None."""
    if not isinstance(tag, str):
        return None
    return _from_match(_TAG_RE.fullmatch(tag))


def parse_global_version(text: object) -> GlobalVersion | None:
    """Same grammar without the leading ``v``."""
    if not isinstance(text, str):
        return None
    return _from_match(_VERSION_RE.fullmatch(text))


def current_global_version() -> GlobalVersion:
    version = parse_global_version(GLOBAL_VERSION)
    if version is None:
        raise ValueError(f"GLOBAL_VERSION does not follow the Global grammar: {GLOBAL_VERSION!r}")
    return version


def global_tag(version: GlobalVersion) -> str:
    return version.tag


def installer_name(tag: str) -> str:
    """``NTE_Drive_Calc_<version>_Multilingual_Setup.exe``; raises for a tag outside the grammar."""
    return f"NTE_Drive_Calc_{_require_tag(tag).text}_Multilingual_Setup.exe"


def manifest_name(tag: str) -> str:
    return f"NTE_Drive_Calc_{_require_tag(tag).text}_release.json"


def signature_name(tag: str) -> str:
    return manifest_name(tag) + ".sig"


def source_zip_name(tag: str) -> str:
    return f"NTE_Drive_Calc_{_require_tag(tag).text}_Multilingual_source.zip"


def _require_tag(tag: str) -> GlobalVersion:
    version = parse_global_tag(tag)
    if version is None:
        raise ValueError(f"not a Global release tag: {tag!r}")
    return version


def global_numeric_version(text: str) -> str:
    """``2.3.2`` -> ``2.3.2.0``, ``2.3.1-global.2`` -> ``2.3.1.2`` (Windows VERSIONINFO; every part fits 16 bits)."""
    version = parse_global_version(text)
    if version is None:
        raise ValueError(f"not a Global version: {text!r}")
    return f"{version.major}.{version.minor}.{version.patch}.{version.n}"


def release_html_url(tag: str) -> str:
    return f"{GLOBAL_RELEASES_URL}/tag/{_require_tag(tag).tag}"


_REPO_PATH_PREFIX = f"/{GLOBAL_REPO_SLUG}/"


def repo_url_allowed(url: object) -> bool:
    """True only for ``https://github.com/LuinDe/NTE-Drive-Calc-Global/...`` (no user info, no port, no encoded or
    dotted path segments, no backslash): the only pages the elevated app opens from release notes or release data."""
    if not isinstance(url, str) or not url or any(ch.isspace() for ch in url) or "\\" in url:
        return False
    import urllib.parse
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.netloc != "github.com" or port is not None:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    path = parts.path
    if path != _REPO_PATH_PREFIX.rstrip("/") and not path.startswith(_REPO_PATH_PREFIX):
        return False
    lowered = url.lower()
    if "%2e" in lowered or "%2f" in lowered or "%5c" in lowered:
        return False
    return not any(segment in (".", "..") for segment in path.split("/"))


def signing_key_fingerprint(key_line: str) -> str:
    """``ssh-ed25519 <base64>`` -> ``SHA256:<base64 without padding>`` (what ``ssh-keygen -l`` prints); "" when the
    line is malformed."""
    import base64
    import hashlib
    try:
        blob = base64.b64decode(str(key_line).split()[1], validate=True)
    except (IndexError, ValueError):
        return ""
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def asset_download_url(download_base: str, tag: str, asset: str) -> str:
    return f"{download_base.rstrip('/')}/{GLOBAL_REPO_SLUG}/releases/download/{_require_tag(tag).tag}/{asset}"


def api_releases_url(api_base: str) -> str:
    return f"{api_base.rstrip('/')}/repos/{GLOBAL_REPO_SLUG}/releases?per_page={API_PER_PAGE}"


def user_agent() -> str:
    return f"NTE-Drive-Calc-Global/{GLOBAL_VERSION}"


@dataclass(frozen=True)
class GlobalUpdateSettings:
    """Everything the update client may vary.  The release build uses ``default_update_settings()``; the
    sandbox test variant constructs one from its test environment (the only place test hooks exist)."""

    api_base: str = GLOBAL_API_BASE
    download_base: str = GLOBAL_DOWNLOAD_BASE
    allowed_hosts: tuple[str, ...] = ALLOWED_DOWNLOAD_HOSTS
    allowed_host_suffixes: tuple[str, ...] = ALLOWED_DOWNLOAD_HOST_SUFFIXES
    allow_http: bool = False
    signing_keys: tuple[tuple[str, str], ...] = RELEASE_SIGNING_KEYS
    require_signed_manifest: bool = True
    accept_prerelease: bool = False
    startup_delay_ms: int = STARTUP_DELAY_MS
    check_interval_hours: int = CHECK_INTERVAL_HOURS
    check_retry_minutes: int = CHECK_RETRY_MINUTES
    staged_max_age_days: int = STAGED_MAX_AGE_DAYS
    installer_size_min: int = INSTALLER_SIZE_MIN
    installer_size_max: int = INSTALLER_SIZE_MAX
    api_timeout: float = 10.0
    download_timeout: float = 30.0


def default_update_settings() -> GlobalUpdateSettings:
    return GlobalUpdateSettings()
