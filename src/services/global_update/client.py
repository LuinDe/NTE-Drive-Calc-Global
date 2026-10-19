# Global 업데이트 클라이언트: GitHub Releases 조회·후보 선택·설치 파일 다운로드 (표준 라이브러리만)
"""Release discovery and installer download of the Global updater (design_final §4, §6.1).

Only ``GET {api_base}/repos/LuinDe/NTE-Drive-Calc-Global/releases?per_page=30`` is ever queried.  Owner, repo, tag
grammar and asset names are compile-time constants; the installer URL is constructed from the validated tag and must
equal the asset's ``browser_download_url`` byte for byte.  Redirects are limited to three hops onto allow-listed
hosts.  Every network byte is untrusted: bodies are capped, JSON shapes validated, and the download gate (exact
size, streaming SHA-256 against the API digest, PE sanity) decides whether a file is kept.  Nothing here touches Qt.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import http.client
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from src.app import global_release as gr
from src.services.global_update.models import AssetInfo, CheckOutcome, ReleaseCandidate, UpdateError
from src.services.global_update.verify import CHUNK, hexdigest_from_api_digest, notes_digest, pe_sanity, verify_manifest
from src.utils.logger import logger

MAX_REDIRECTS = 3
# fetching the signed manifest during a check: these failures are transient (the check failed, retry later); every
# other failure means the release itself is unusable
_TRANSIENT_TAILS = ("network", "timeout", "tls", "ratelimit", "io")
PROGRESS_INTERVAL_SECONDS = 0.25
_PE_PROBE = 4096
_RELEASE_BODY_KEEP = 4 * gr.RELEASE_BODY_MAX


class RedirectRefused(UpdateError):
    """Raised inside the redirect handler; mapped to the pipeline step by the caller."""


def utc_text(moment: _dt.datetime) -> str:
    return moment.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ───────────────────────────── URL rules ─────────────────────────────
def url_refusal(url: object, settings: gr.GlobalUpdateSettings) -> str:
    """"" when ``url`` may be requested, else the reason (scheme / userinfo / host / port)."""
    if not isinstance(url, str) or not url:
        return "empty"
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "malformed"
    scheme = parts.scheme.lower()
    if scheme == "http" and not settings.allow_http:
        return "scheme"
    if scheme not in ("https", "http"):
        return "scheme"
    if parts.username is not None or parts.password is not None:
        return "userinfo"
    host = (parts.hostname or "").lower()
    if not host:
        return "host"
    try:
        port = parts.port
    except ValueError:
        return "port"
    if port is not None and not settings.allow_http:
        return "port"
    if host in tuple(h.lower() for h in settings.allowed_hosts):
        return ""
    if any(host.endswith(suffix.lower()) for suffix in settings.allowed_host_suffixes):
        return ""
    return "host"


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """At most MAX_REDIRECTS hops, each onto an allow-listed https host (http only when the settings allow it)."""

    def __init__(self, settings: gr.GlobalUpdateSettings) -> None:
        super().__init__()
        self._settings = settings
        self.max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        hops = len(getattr(req, "redirect_dict", None) or {})
        if hops >= MAX_REDIRECTS:
            raise RedirectRefused("download.redirect_refused", f"more than {MAX_REDIRECTS} redirects")
        reason = url_refusal(newurl, self._settings)
        if reason:
            raise RedirectRefused("download.redirect_refused", f"redirect target refused ({reason})")
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            raise RedirectRefused("download.redirect_refused", f"HTTP {code} not followed")
        return new


def _map_transport_error(exc: BaseException, step: str) -> UpdateError:
    """URLError / socket / ssl / http.client failures -> ``<step>.network|timeout|tls`` (class name only)."""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLError):
        return UpdateError(f"{step}.tls", type(reason).__name__)
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return UpdateError(f"{step}.timeout", type(reason).__name__)
    detail = f"{type(reason).__name__}: {str(reason)[:160]}"
    return UpdateError(f"{step}.network", detail)


def _retry_after_utc(headers) -> str | None:
    reset = headers.get("X-RateLimit-Reset")
    if reset:
        try:
            return utc_text(_dt.datetime.fromtimestamp(int(reset), _dt.timezone.utc))
        except (ValueError, OverflowError, OSError):
            pass
    retry = headers.get("Retry-After")
    if retry:
        try:
            seconds = max(0, int(retry))
        except ValueError:
            return None
        return utc_text(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=seconds))
    return None


def _map_http_error(exc: urllib.error.HTTPError, step: str) -> UpdateError:
    status = int(exc.code)
    headers = exc.headers
    try:
        exc.read(16)
    except Exception:
        pass
    if status in (403, 429):
        remaining = str(headers.get("X-RateLimit-Remaining") or "").strip()
        if status == 429 or remaining == "0" or headers.get("Retry-After"):
            return UpdateError(f"{step}.ratelimit", f"HTTP {status}", retry_after_utc=_retry_after_utc(headers))
    return UpdateError(f"{step}.http_{status}", f"HTTP {status}")


# ───────────────────────────── selection (pure) ─────────────────────────────
def _release_rejection(release: object, settings: gr.GlobalUpdateSettings) -> str:
    if not isinstance(release, dict):
        return "not_object"
    if release.get("draft") is not False:
        return "draft"
    if release.get("prerelease") is not False and not settings.accept_prerelease:
        return "prerelease"
    tag = release.get("tag_name")
    if gr.parse_global_tag(tag) is None:
        return "tag_grammar"
    author = release.get("author")
    login = author.get("login") if isinstance(author, dict) else None
    if login not in gr.GLOBAL_RELEASE_AUTHORS:
        return "author"
    if release.get("html_url") != gr.release_html_url(tag):
        return "html_url"
    if not isinstance(release.get("assets"), list):
        return "assets"
    return ""


def _asset_info(asset: dict, expected_url: str) -> tuple[AssetInfo | None, str]:
    name = asset.get("name")
    size = asset.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return None, "size"
    if asset.get("state") != "uploaded":
        return None, "state"
    digest = asset.get("digest")
    if digest is None:
        return None, "digest"
    try:
        sha256 = hexdigest_from_api_digest(digest)
    except UpdateError:
        return None, "digest"
    url = asset.get("browser_download_url")
    if url != expected_url:
        return None, "untrusted_url"
    return AssetInfo(name=str(name), size=size, sha256=sha256, url=str(url),
                     content_type=str(asset.get("content_type") or ""), state="uploaded"), ""


def _select_assets(release: dict, tag: str, settings: gr.GlobalUpdateSettings):
    """``(installer, manifest, signature, rejection reason)`` for the newest candidate."""
    assets = [asset for asset in release["assets"] if isinstance(asset, dict)]
    wanted = gr.installer_name(tag)
    installers = [asset for asset in assets if asset.get("name") == wanted]
    if len(installers) != 1:
        return None, None, None, ("installer_missing" if not installers else "installer_duplicate")
    installer, reason = _asset_info(installers[0], gr.asset_download_url(settings.download_base, tag, wanted))
    if installer is None:
        return None, None, None, reason if reason == "untrusted_url" else f"installer_{reason}"
    if not (settings.installer_size_min <= installer.size <= settings.installer_size_max):
        return None, None, None, "installer_size"
    if installer.content_type not in gr.INSTALLER_CONTENT_TYPES:
        return None, None, None, "installer_content_type"
    manifest = signature = None
    if settings.require_signed_manifest:
        found = []
        for label, name in (("manifest", gr.manifest_name(tag)), ("signature", gr.signature_name(tag))):
            matches = [asset for asset in assets if asset.get("name") == name]
            if len(matches) != 1:
                return None, None, None, f"{label}_missing"
            info, reason = _asset_info(matches[0], gr.asset_download_url(settings.download_base, tag, name))
            if info is None:
                return None, None, None, reason if reason == "untrusted_url" else f"{label}_{reason}"
            if not (0 < info.size <= gr.MANIFEST_SIZE_MAX):
                return None, None, None, f"{label}_size"
            found.append(info)
        manifest, signature = found
    return installer, manifest, signature, ""


def select_candidate(releases: object, *, current: gr.GlobalVersion, settings: gr.GlobalUpdateSettings) -> CheckOutcome:
    """design_final §4.2: the newest valid release, offered only when newer than ``current``; a newest candidate
    whose assets fail validation means "no update" (never an older one); an asset at an unexpected URL is a
    tripwire (``check.untrusted_release``)."""
    if not isinstance(releases, list):
        raise UpdateError("check.invalid_response", "releases is not a list")
    rejected: list[tuple[str, str]] = []
    valid: list[tuple[gr.GlobalVersion, str, dict]] = []
    for release in releases:
        tag = release.get("tag_name") if isinstance(release, dict) else None
        label = tag if isinstance(tag, str) else "?"
        reason = _release_rejection(release, settings)
        if reason:
            rejected.append((label, reason))
            continue
        valid.append((gr.parse_global_tag(tag), tag, release))
    seen = len(releases)
    if not valid:
        raise UpdateError("check.no_release", f"{seen} releases, none usable")
    version, tag, release = max(valid, key=lambda item: item[0])
    if version <= current:
        return CheckOutcome(None, seen, tuple(rejected), tag)
    installer, manifest, signature, reason = _select_assets(release, tag, settings)
    if reason == "untrusted_url":
        raise UpdateError("check.untrusted_release", f"{tag}: an asset is not at its expected location")
    if reason:
        rejected.append((tag, reason))
        return CheckOutcome(None, seen, tuple(rejected), tag)
    body = release.get("body")
    candidate = ReleaseCandidate(
        tag=tag, version=version, name=str(release.get("name") or tag), html_url=str(release["html_url"]),
        published_at=str(release.get("published_at") or ""),
        body=(body if isinstance(body, str) else "")[:_RELEASE_BODY_KEEP],
        installer=installer, manifest=manifest, signature=signature,
    )
    return CheckOutcome(candidate, seen, tuple(rejected), tag)


# ───────────────────────────── client ─────────────────────────────
class GlobalUpdateClient:
    """One opener per client; ``request_log`` records the request URLs (tests assert localhost only; the app never
    logs URLs that may carry signed CDN tokens)."""

    def __init__(self, settings: gr.GlobalUpdateSettings, *, current_version: gr.GlobalVersion | None = None) -> None:
        self.settings = settings
        self.current_version = current_version or gr.current_global_version()
        self.request_log: list[str] = []
        handlers: list = [_AllowlistRedirectHandler(settings)]
        if not settings.allow_http:
            handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self._opener = urllib.request.build_opener(*handlers)

    # ── requests ──
    def _request(self, url: str, accept: str) -> urllib.request.Request:
        reason = url_refusal(url, self.settings)
        if reason:
            raise UpdateError("check.invalid_response", f"request url refused ({reason})")
        self.request_log.append(url)
        return urllib.request.Request(url, headers={
            "Accept": accept,
            "User-Agent": gr.user_agent(),
            "X-GitHub-Api-Version": "2022-11-28",
        })

    @staticmethod
    def _read_capped(response, cap: int, step: str) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            total += len(block)
            if total > cap:
                raise UpdateError(f"{step}.invalid_response" if step == "check" else "verify.size",
                                  f"body larger than {cap} bytes")
            chunks.append(block)
        return b"".join(chunks)

    def fetch_releases(self) -> list:
        url = gr.api_releases_url(self.settings.api_base)
        request = self._request(url, "application/vnd.github+json")
        try:
            with self._opener.open(request, timeout=self.settings.api_timeout) as response:
                body = self._read_capped(response, gr.API_BODY_MAX, "check")
        except UpdateError as exc:
            if isinstance(exc, RedirectRefused):
                raise UpdateError("check.invalid_response", exc.detail) from None
            raise
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc, "check") from None
        except (urllib.error.URLError, ssl.SSLError, socket.timeout, TimeoutError, http.client.HTTPException,
                OSError) as exc:
            raise _map_transport_error(exc, "check") from None
        except Exception as exc:  # fail closed on anything unexpected (class name only)
            raise UpdateError("check.network", type(exc).__name__) from None
        try:
            releases = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise UpdateError("check.invalid_response", f"not JSON ({type(exc).__name__})") from None
        if not isinstance(releases, list):
            raise UpdateError("check.invalid_response", "releases is not a list")
        return releases

    def fetch_candidate(self) -> CheckOutcome:
        outcome = select_candidate(self.fetch_releases(), current=self.current_version, settings=self.settings)
        for tag, reason in outcome.rejected:
            logger.info(f"global_update.release_rejected | tag={tag} reason={reason}")
        return outcome

    def verify_candidate(self, outcome: CheckOutcome) -> CheckOutcome:
        """Review r5 F1: the signed manifest of the release about to be offered is fetched and verified DURING the
        check, so an unsigned or tampered release is never announced (no notification, no notes).  A transport
        failure while fetching it fails the check (retried later); a verification failure makes the release
        unusable (``unusable_tag``: "no update", the newest-only rule of ``select_candidate``).  A correctly signed
        release whose ``min_global_version`` is newer than this build stays a candidate with
        ``manual_install_min`` (the notification says "install it by hand").  The verified bytes travel with the
        candidate; the download step re-verifies exactly those bytes."""
        candidate = outcome.candidate
        if candidate is None:
            return outcome
        if not self.settings.require_signed_manifest:
            # test settings only (the release build always requires the signed manifest): nothing binds the notes
            return dataclasses.replace(outcome, candidate=dataclasses.replace(candidate, notes_verified=True))
        try:
            if candidate.manifest is None or candidate.signature is None:
                raise UpdateError("verify.manifest_missing", "release has no signed manifest")
            manifest_bytes = self.fetch_small(candidate.manifest)
            signature_bytes = self.fetch_small(candidate.signature)
            manifest = verify_manifest(
                manifest_bytes, signature_bytes, self.settings.signing_keys, gr.RELEASE_SIG_NAMESPACE,
                expected_tag=candidate.tag, expected_size=candidate.installer.size,
                expected_sha256=candidate.installer.sha256, current_version=self.current_version,
                size_min=self.settings.installer_size_min, size_max=self.settings.installer_size_max,
                allow_manual=True,
            )
        except UpdateError as exc:
            tail = exc.code.split(".", 1)[1] if "." in exc.code else exc.code
            if exc.kind == "download" and (tail in _TRANSIENT_TAILS or tail.startswith("http_5")):
                raise UpdateError(f"check.{tail}", exc.detail, retry_after_utc=exc.retry_after_utc) from None
            logger.info(f"global_update.release_rejected | tag={candidate.tag} reason={exc.code}")
            return dataclasses.replace(outcome, candidate=None, rejected=outcome.rejected + ((candidate.tag, exc.code),),
                                       unusable_tag=candidate.tag, unusable_code=exc.code)
        notes_ok = bool(manifest.notes_sha256) and notes_digest(candidate.body) == manifest.notes_sha256
        if not notes_ok:
            logger.info(f"global_update.notes_unverified | tag={candidate.tag} bound={bool(manifest.notes_sha256)}")
        verified = dataclasses.replace(candidate, manifest_bytes=manifest_bytes, signature_bytes=signature_bytes,
                                       notes_verified=notes_ok, manual_install_min=manifest.manual_install_min)
        return dataclasses.replace(outcome, candidate=verified)

    def fetch_small(self, asset: AssetInfo, max_bytes: int = gr.MANIFEST_SIZE_MAX) -> bytes:
        """A manifest or signature asset: size and SHA-256 must equal the API record."""
        request = self._request(asset.url, "application/octet-stream")
        try:
            with self._opener.open(request, timeout=self.settings.api_timeout) as response:
                body = self._read_capped(response, max_bytes, "download")
        except UpdateError:
            raise
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc, "download") from None
        except (urllib.error.URLError, ssl.SSLError, socket.timeout, TimeoutError, http.client.HTTPException,
                OSError) as exc:
            raise _map_transport_error(exc, "download") from None
        except Exception as exc:
            raise UpdateError("download.io", type(exc).__name__) from None
        if len(body) < asset.size:
            # the connection ended early: a transport failure, not a different file
            raise UpdateError("download.network", f"truncated: {len(body)} bytes, expected {asset.size}")
        if len(body) != asset.size:
            raise UpdateError("verify.size", f"{len(body)} bytes, expected {asset.size}")
        if hashlib.sha256(body).hexdigest() != asset.sha256:
            raise UpdateError("verify.sha256", "small asset digest mismatch")
        return body

    def download(self, asset: AssetInfo, destination: str | os.PathLike, *,
                 progress: Callable[[int, int], None] | None = None, cancel=None) -> str:
        """Streams ``asset`` to ``<destination>.part`` through the §6.1 gate and renames it into place; returns the
        hex digest.  Any failure or cancel removes the partial file and raises ``UpdateError``."""
        final = Path(destination)
        part = final.with_name(final.name + ".part")
        expected = int(asset.size)
        if len(asset.sha256) != 64:
            raise UpdateError("verify.digest_missing", "asset has no digest")
        request = self._request(asset.url, "application/octet-stream")
        digest = hashlib.sha256()
        total = 0
        head = b""
        last_report = 0.0
        try:
            try:
                with self._opener.open(request, timeout=self.settings.download_timeout) as response:
                    length = response.headers.get("Content-Length")
                    if length is not None:
                        try:
                            if int(length) != expected:
                                raise UpdateError("verify.size", f"Content-Length {length}, expected {expected}")
                        except ValueError:
                            raise UpdateError("verify.size", "Content-Length malformed") from None
                    if progress is not None:
                        progress(0, expected)
                        last_report = time.monotonic()
                    with open(part, "wb") as out:
                        while True:
                            if cancel is not None and cancel.is_set():
                                raise UpdateError("download.cancelled")
                            block = response.read(CHUNK)
                            if not block:
                                break
                            total += len(block)
                            if total > expected:
                                raise UpdateError("verify.size", f"more than {expected} bytes")
                            if len(head) < _PE_PROBE:
                                head += block[:_PE_PROBE - len(head)]
                                reason = pe_sanity(head)
                                if reason is not None:
                                    raise UpdateError("verify.not_pe", reason)
                            digest.update(block)
                            out.write(block)
                            now = time.monotonic()
                            if progress is not None and now - last_report >= PROGRESS_INTERVAL_SECONDS:
                                progress(total, expected)
                                last_report = now
                        out.flush()
                        os.fsync(out.fileno())
            except UpdateError:
                raise
            except urllib.error.HTTPError as exc:
                raise _map_http_error(exc, "download") from None
            except (urllib.error.URLError, ssl.SSLError, socket.timeout, TimeoutError,
                    http.client.HTTPException) as exc:
                raise _map_transport_error(exc, "download") from None
            except OSError as exc:
                if getattr(exc, "errno", None) == 28:
                    # the detail is the free space needed in MB (the sentence shows it; never an exception name)
                    raise UpdateError("download.disk_space", str((expected + gr.DISK_SPACE_MARGIN) // 2**20)) from None
                raise UpdateError("download.io", type(exc).__name__) from None
            except Exception as exc:
                raise UpdateError("download.io", type(exc).__name__) from None
            if total != expected:
                raise UpdateError("verify.size", f"{total} bytes, expected {expected}")
            hexdigest = digest.hexdigest()
            if hexdigest != asset.sha256:
                raise UpdateError("verify.sha256", "download digest differs from the release record")
            os.replace(part, final)
            if progress is not None:
                progress(total, expected)
            return hexdigest
        except BaseException:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            raise
