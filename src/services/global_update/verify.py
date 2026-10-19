# Global 업데이트 무결성 검증 (SHA-256 · PE 검사 · Ed25519 서명 매니페스트; 순수 모듈)
"""Integrity gates of the Global updater (design_final §6).  Standard library only.

* ``sha256_stream`` / ``pe_sanity`` / ``hexdigest_from_api_digest``: the download gate (API ``size`` + ``digest``).
* ``ed25519_verify``: RFC 8032 §5.1.7 verification in pure Python (public inputs only, so no constant-time
  requirement); ``parse_sshsig`` / ``sshsig_verify``: the OpenSSH ``ssh-keygen -Y sign`` signature format
  (PROTOCOL.sshsig); ``verify_manifest``: the signed release manifest that binds tag, asset name, size and SHA-256.

Every check fails closed: any malformed input raises ``UpdateError`` with a ``verify.*`` code.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import struct
from typing import BinaryIO, Iterable

from src.app.global_release import GlobalVersion, installer_name, parse_global_tag, parse_global_version
from src.services.global_update.models import Manifest, UpdateError

_HEX64 = re.compile(r"[0-9a-f]{64}", re.ASCII)
_API_DIGEST = re.compile(r"sha256:([0-9a-f]{64})", re.ASCII)
CHUNK = 256 * 1024
MANIFEST_FORMAT = 1
MANIFEST_PRODUCT = "NTE-Drive-Calc-Global"
SSHSIG_VERSION = 1
SSHSIG_KEY_TYPE = b"ssh-ed25519"
_SSHSIG_MAGIC = b"SSHSIG"
_ARMOR_BEGIN = "-----BEGIN SSH SIGNATURE-----"
_ARMOR_END = "-----END SSH SIGNATURE-----"
_HASHES = {b"sha256": hashlib.sha256, b"sha512": hashlib.sha512}


# ───────────────────────────── release notes binding ─────────────────────────────
def normalize_notes(text: object) -> str:
    """The release body as the signed ``notes_sha256`` covers it: line endings -> LF, trailing white space of every
    line removed, leading / trailing blank lines removed.  (GitHub keeps the body as uploaded, but its web editor
    may turn LF into CRLF or drop a final newline; none of that changes what the user reads.)
    build_tools/build_installer_g231.py ``normalize_notes`` must stay identical (unit-tested)."""
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def notes_digest(text: object) -> str:
    return hashlib.sha256(normalize_notes(text).encode("utf-8")).hexdigest()


# ───────────────────────────── download gate ─────────────────────────────
def hexdigest_from_api_digest(value: object) -> str:
    """``sha256:<64 hex>`` (GitHub asset ``digest``) -> the 64 hex digits; anything else -> verify.digest_missing."""
    if not isinstance(value, str):
        raise UpdateError("verify.digest_missing", "asset has no digest")
    match = _API_DIGEST.fullmatch(value)
    if match is None:
        raise UpdateError("verify.digest_missing", "asset digest is not sha256:<hex>")
    return match.group(1)


def pe_sanity(head: bytes) -> str | None:
    """None when ``head`` looks like the start of a PE image, else the reason (sanity, not security)."""
    if len(head) < 2 or head[:2] != b"MZ":
        return "no MZ header"
    if len(head) < 0x40:
        return None
    e_lfanew = int.from_bytes(head[0x3C:0x40], "little")
    if e_lfanew + 4 <= len(head):
        if head[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            return "no PE signature at e_lfanew"
    elif len(head) >= 4096:
        return "e_lfanew beyond the first 4 KiB"
    return None


def sha256_stream(stream: BinaryIO, expected_size: int, chunk: int = CHUNK) -> str:
    """Hash ``stream`` to its end; the byte count must equal ``expected_size`` (else verify.size)."""
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(chunk)
        if not block:
            break
        digest.update(block)
        total += len(block)
        if total > expected_size:
            raise UpdateError("verify.size", f"more than {expected_size} bytes")
    if total != expected_size:
        raise UpdateError("verify.size", f"{total} bytes, expected {expected_size}")
    return digest.hexdigest()


def sha256_file(path, expected_size: int | None = None) -> str:
    with open(path, "rb") as stream:
        if expected_size is None:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
            return digest.hexdigest()
        return sha256_stream(stream, expected_size)


# ───────────────────────────── Ed25519 (RFC 8032) ─────────────────────────────
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = (-121665 * _inv(121666)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _I % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _point_add(p1, p2):
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _point_mul(scalar: int, point):
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _point_add(result, point)
        point = _point_add(point, point)
        scalar >>= 1
    return result


def _point_equal(p1, p2) -> bool:
    x1, y1, z1, _ = p1
    x2, y2, z2, _ = p2
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _point_decompress(raw: bytes):
    if len(raw) != 32:
        return None
    y = int.from_bytes(raw, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _point_compress(point) -> bytes:
    x, y, z, _ = point
    zinv = _inv(z)
    x, y = x * zinv % _P, y * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


_BY = 4 * _inv(5) % _P
_BX = _recover_x(_BY, 0)
_B = (_BX, _BY, 1, _BX * _BY % _P)


def ed25519_public_key(secret: bytes) -> bytes:
    """Public key of a 32-byte seed (used by the tests to cross-check the RFC vectors; not needed by the app)."""
    if len(secret) != 32:
        raise ValueError("secret must be 32 bytes")
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return _point_compress(_point_mul(a, _B))


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """RFC 8032 §5.1.7 (cofactorless check as in the reference implementation of the RFC appendix)."""
    try:
        if len(public_key) != 32 or len(signature) != 64:
            return False
        a_point = _point_decompress(public_key)
        if a_point is None:
            return False
        r_raw, s_raw = signature[:32], signature[32:]
        r_point = _point_decompress(r_raw)
        if r_point is None:
            return False
        s = int.from_bytes(s_raw, "little")
        if s >= _L:
            return False
        k = int.from_bytes(hashlib.sha512(r_raw + public_key + message).digest(), "little") % _L
        left = _point_mul(s, _B)
        right = _point_add(r_point, _point_mul(k, a_point))
        return _point_equal(left, right)
    except Exception:
        return False


# ───────────────────────────── OpenSSH sshsig ─────────────────────────────
class SshSig:
    __slots__ = ("version", "key_type", "public_key", "namespace", "reserved", "hash_algorithm", "sig_type", "signature")

    def __init__(self, version, key_type, public_key, namespace, reserved, hash_algorithm, sig_type, signature):
        self.version = version
        self.key_type = key_type
        self.public_key = public_key
        self.namespace = namespace
        self.reserved = reserved
        self.hash_algorithm = hash_algorithm
        self.sig_type = sig_type
        self.signature = signature


def _ssh_string(buf: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(buf):
        raise UpdateError("verify.signature", "truncated ssh string length")
    (length,) = struct.unpack(">I", buf[offset:offset + 4])
    offset += 4
    if offset + length > len(buf):
        raise UpdateError("verify.signature", "truncated ssh string")
    return buf[offset:offset + length], offset + length


def _ssh_encode_string(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def dearmor_sshsig(armored: bytes) -> bytes:
    try:
        text = armored.decode("ascii")
    except UnicodeDecodeError as exc:
        raise UpdateError("verify.signature", "signature is not ASCII") from exc
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if line]
    if len(lines) < 3 or lines[0] != _ARMOR_BEGIN or lines[-1] != _ARMOR_END:
        raise UpdateError("verify.signature", "signature armor malformed")
    body = "".join(lines[1:-1])
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", body):
        raise UpdateError("verify.signature", "signature armor malformed")
    try:
        return base64.b64decode(body, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise UpdateError("verify.signature", "signature base64 malformed") from exc


def parse_sshsig(armored: bytes) -> SshSig:
    blob = dearmor_sshsig(armored)
    if blob[:6] != _SSHSIG_MAGIC:
        raise UpdateError("verify.signature", "not an SSHSIG blob")
    if len(blob) < 10:
        raise UpdateError("verify.signature", "truncated SSHSIG blob")
    (version,) = struct.unpack(">I", blob[6:10])
    if version != SSHSIG_VERSION:
        raise UpdateError("verify.signature", f"unsupported SSHSIG version {version}")
    offset = 10
    public_blob, offset = _ssh_string(blob, offset)
    namespace, offset = _ssh_string(blob, offset)
    reserved, offset = _ssh_string(blob, offset)
    hash_algorithm, offset = _ssh_string(blob, offset)
    signature_blob, offset = _ssh_string(blob, offset)
    if offset != len(blob):
        raise UpdateError("verify.signature", "trailing bytes after the signature")
    key_type, key_offset = _ssh_string(public_blob, 0)
    public_key, key_offset = _ssh_string(public_blob, key_offset)
    if key_offset != len(public_blob):
        raise UpdateError("verify.signature", "trailing bytes in the public key")
    sig_type, sig_offset = _ssh_string(signature_blob, 0)
    signature, sig_offset = _ssh_string(signature_blob, sig_offset)
    if sig_offset != len(signature_blob):
        raise UpdateError("verify.signature", "trailing bytes in the signature")
    return SshSig(version, key_type, public_key, namespace, reserved, hash_algorithm, sig_type, signature)


def pinned_key_bytes(text: str) -> bytes:
    """Accepts the raw 32-byte key as base64, the OpenSSH wire blob (``AAAAC3NzaC1lZDI1NTE5...``) or a whole
    ``ssh-ed25519 <blob> comment`` line; anything else raises ValueError."""
    parts = str(text).strip().split()
    if len(parts) >= 2 and parts[0] == "ssh-ed25519":
        candidate = parts[1]
    elif len(parts) == 1:
        candidate = parts[0]
    else:
        raise ValueError("unrecognised public key text")
    raw = base64.b64decode(candidate, validate=True)
    if len(raw) == 32:
        return raw
    key_type, offset = _ssh_string(raw, 0)
    key, offset = _ssh_string(raw, offset)
    if key_type != SSHSIG_KEY_TYPE or offset != len(raw) or len(key) != 32:
        raise ValueError("not an ssh-ed25519 public key")
    return key


def sshsig_verify(sig: SshSig, message: bytes, pinned_keys: Iterable[tuple[str, str]], namespace: str) -> str:
    """Checks, in order: key type, pinned key, namespace, hash algorithm, Ed25519 signature.  Returns the key id."""
    if sig.key_type != SSHSIG_KEY_TYPE or sig.sig_type != SSHSIG_KEY_TYPE:
        raise UpdateError("verify.signature", "signature key type is not ssh-ed25519")
    key_id = ""
    for pinned_id, pinned_text in pinned_keys:
        try:
            if pinned_key_bytes(pinned_text) == sig.public_key:
                key_id = str(pinned_id)
                break
        except (ValueError, UpdateError, base64.binascii.Error):
            continue
    if not key_id:
        raise UpdateError("verify.signature", "signing key is not pinned")
    if sig.namespace != namespace.encode("utf-8"):
        raise UpdateError("verify.signature", "namespace mismatch")
    hasher = _HASHES.get(sig.hash_algorithm)
    if hasher is None:
        raise UpdateError("verify.signature", "unknown hash algorithm")
    signed = (_SSHSIG_MAGIC + _ssh_encode_string(sig.namespace) + _ssh_encode_string(sig.reserved)
              + _ssh_encode_string(sig.hash_algorithm) + _ssh_encode_string(hasher(message).digest()))
    if not ed25519_verify(sig.public_key, signed, sig.signature):
        raise UpdateError("verify.signature", "Ed25519 verification failed")
    return key_id


# ───────────────────────────── release manifest ─────────────────────────────
def _require_str(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise UpdateError("verify.manifest_invalid", f"missing or non-string {key}")
    return value


def _require_int(data: dict, key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise UpdateError("verify.manifest_invalid", f"missing or non-integer {key}")
    return value


def parse_manifest(manifest_bytes: bytes) -> Manifest:
    """Structure and grammar only (no comparison with the release); see ``verify_manifest`` for the rules."""
    try:
        data = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateError("verify.manifest_invalid", "manifest is not UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise UpdateError("verify.manifest_invalid", "manifest is not an object")
    if _require_int(data, "format") != MANIFEST_FORMAT:
        raise UpdateError("verify.manifest_invalid", "unknown manifest format")
    if _require_str(data, "product") != MANIFEST_PRODUCT:
        raise UpdateError("verify.manifest_invalid", "product mismatch")
    tag = _require_str(data, "tag")
    if parse_global_tag(tag) is None:
        raise UpdateError("verify.manifest_invalid", "tag outside the Global grammar")
    global_version = _require_str(data, "global_version")
    if global_version != tag[1:]:
        raise UpdateError("verify.manifest_invalid", "global_version does not match the tag")
    installer = data.get("installer")
    if not isinstance(installer, dict):
        raise UpdateError("verify.manifest_invalid", "missing installer object")
    name = _require_str(installer, "name")
    if name != installer_name(tag):
        raise UpdateError("verify.manifest_invalid", "installer name does not match the tag")
    size = _require_int(installer, "size")
    sha256 = _require_str(installer, "sha256")
    if _HEX64.fullmatch(sha256) is None:
        raise UpdateError("verify.manifest_invalid", "installer sha256 is not 64 lower-case hex digits")
    exe_sha256 = data.get("exe_sha256", "")
    if not isinstance(exe_sha256, str) or (exe_sha256 and _HEX64.fullmatch(exe_sha256) is None):
        raise UpdateError("verify.manifest_invalid", "exe_sha256 malformed")
    min_version = data.get("min_global_version", "")
    if not isinstance(min_version, str) or (min_version and parse_global_version(min_version) is None):
        raise UpdateError("verify.manifest_invalid", "min_global_version malformed")
    notes_sha256 = data.get("notes_sha256", "")
    if not isinstance(notes_sha256, str) or (notes_sha256 and _HEX64.fullmatch(notes_sha256) is None):
        raise UpdateError("verify.manifest_invalid", "notes_sha256 malformed")
    upstream_base = data.get("upstream_base", "")
    published = data.get("published_utc", "")
    return Manifest(
        format=MANIFEST_FORMAT, product=MANIFEST_PRODUCT, tag=tag, global_version=global_version,
        upstream_base=upstream_base if isinstance(upstream_base, str) else "",
        installer_name=name, installer_size=size, installer_sha256=sha256, exe_sha256=exe_sha256,
        min_global_version=min_version, published_utc=published if isinstance(published, str) else "",
        notes_sha256=notes_sha256,
    )


def verify_manifest(
    manifest_bytes: bytes,
    signature_bytes: bytes,
    pinned_keys: Iterable[tuple[str, str]],
    namespace: str,
    *,
    expected_tag: str,
    expected_size: int,
    expected_sha256: str,
    current_version: GlobalVersion,
    size_min: int = 1,
    size_max: int = 1 << 40,
    allow_manual: bool = False,
) -> Manifest:
    """The second integrity gate (design_final §6.2): signature first, then every rule, all fail closed.
    ``allow_manual`` (the release check only): a release whose ``min_global_version`` is newer than the running
    build is returned with ``manual_install_min`` set instead of raising ``verify.manual_install_required``, so the
    notification can say "install it by hand"; the download and the launcher keep the default and refuse it."""
    pinned = tuple(pinned_keys)
    if not pinned:
        raise UpdateError("verify.signature", "no release signing key is pinned")
    sig = parse_sshsig(signature_bytes)
    key_id = sshsig_verify(sig, manifest_bytes, pinned, namespace)
    manifest = parse_manifest(manifest_bytes)
    if manifest.tag != expected_tag:
        raise UpdateError("verify.manifest_invalid", "manifest tag does not match the release")
    if not (size_min <= manifest.installer_size <= size_max) or manifest.installer_size != expected_size:
        raise UpdateError("verify.manifest_invalid", "installer size does not match the release")
    if manifest.installer_sha256 != expected_sha256:
        raise UpdateError("verify.manifest_invalid", "installer sha256 does not match the release")
    manual = ""
    if manifest.min_global_version:
        minimum = parse_global_version(manifest.min_global_version)
        if minimum is not None and minimum > current_version:
            if not allow_manual:
                raise UpdateError("verify.manual_install_required", manifest.min_global_version)
            manual = manifest.min_global_version
    return Manifest(**{**manifest.__dict__, "key_id": key_id, "manual_install_min": manual})
