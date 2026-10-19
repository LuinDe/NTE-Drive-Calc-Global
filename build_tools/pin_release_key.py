"""Release gate for the Ed25519 release-signing key of NTE Drive Calc Global (design_final §6.4, user decision U1).

The REAL key pair is created by the maintainer, interactively, never by a build step:
    ssh-keygen -t ed25519 -f %USERPROFILE%\\.ssh\\nte_global_release -C nte-global-release      (with a passphrase)
This script reads ONLY the public half (``nte_global_release.pub``) and pins it into
``<tree>/src/app/global_release.py`` (``RELEASE_SIGNING_KEYS``).  It never reads, copies or prints the private key,
and it refuses to pin anything else (so a test key can never end up in a release tree).

usage (Python 3.11):
    pin_release_key.py <tree root> [--pub <file>] [--key-id <id>] [--check] [--allow-second <pub file>]
      --pub     public key file; default %USERPROFILE%\\.ssh\\nte_global_release.pub
      --key-id  key id recorded next to the key (default: the comment of the public key line, else nte-global-release)
      --check   do not write; exit 0 only when the tree already pins exactly that key
      --allow-second  during a rotation: keep this (old) public key as the second slot
exit 0 = pinned / verified, 2 = the public key file is absent or invalid (release gate FAILS), 1 = other error
"""
from __future__ import annotations

import argparse
import base64
import os
import pathlib
import re
import sys

assert sys.version_info[:2] == (3, 11)
LINE_RE = re.compile(r"^ssh-ed25519 ([A-Za-z0-9+/=]+)(?: (\S.*))?$")
PIN_RE = re.compile(r"^RELEASE_SIGNING_KEYS(?::[^=]*)?=\s*\((?:.|\n)*?\)\s*(?:#[^\n]*)?$", re.MULTILINE)
TEST_MARKERS = ("nte-global-test", "test", "gate")


def read_public_key(path: pathlib.Path) -> tuple[str, str]:
    """``(key id, "ssh-ed25519 <base64>")`` of a one-line OpenSSH public key file; raises ValueError otherwise."""
    if path.suffix != ".pub":
        raise ValueError(f"refusing to read {path.name}: not a .pub file (the private key is never read)")
    text = path.read_text(encoding="utf-8").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{path.name}: expected exactly one public key line")
    match = LINE_RE.match(lines[0].strip())
    if not match:
        raise ValueError(f"{path.name}: not an ssh-ed25519 public key line")
    raw = base64.b64decode(match.group(1), validate=True)
    # OpenSSH wire format: string "ssh-ed25519" + string key32
    if len(raw) != 4 + 11 + 4 + 32 or raw[:4] != b"\x00\x00\x00\x0b" or raw[4:15] != b"ssh-ed25519" or raw[15:19] != b"\x00\x00\x00\x20":
        raise ValueError(f"{path.name}: malformed ssh-ed25519 key blob")
    comment = (match.group(2) or "").strip()
    key_id = comment or "nte-global-release"
    if any(marker == key_id.lower() or key_id.lower().startswith(marker + "-") for marker in TEST_MARKERS):
        raise ValueError(f"{path.name}: comment {key_id!r} looks like a test key; the release tree pins only the real key")
    return key_id, f"ssh-ed25519 {match.group(1)}"


def current_pins(source: str) -> list[tuple[str, str]]:
    match = PIN_RE.search(source)
    if not match:
        raise RuntimeError("RELEASE_SIGNING_KEYS assignment not found")
    import ast
    body = match.group(0).split("=", 1)[1]
    body = body.split("#", 1)[0] if body.rstrip().endswith(")") is False else body
    value = ast.literal_eval(body.strip())
    return [(str(a), str(b)) for a, b in value]


def render_pins(pins: list[tuple[str, str]]) -> str:
    if not pins:
        return "RELEASE_SIGNING_KEYS: tuple[tuple[str, str], ...] = ()"
    inner = ", ".join(f'("{key_id}", "{line}")' for key_id, line in pins)
    return f"RELEASE_SIGNING_KEYS: tuple[tuple[str, str], ...] = ({inner},)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tree", type=pathlib.Path)
    parser.add_argument("--pub", type=pathlib.Path, default=None)
    parser.add_argument("--key-id", default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--allow-second", type=pathlib.Path, default=None)
    args = parser.parse_args()
    source_path = args.tree.resolve() / "src" / "app" / "global_release.py"
    if not source_path.is_file():
        print(f"ERROR: {source_path} not found", file=sys.stderr)
        return 1
    pub = args.pub or (pathlib.Path(os.environ.get("USERPROFILE", "~")).expanduser() / ".ssh" / "nte_global_release.pub")
    if not pub.is_file():
        print(f"RELEASE GATE FAILED: public key file absent: {pub}\n"
              "Create the key pair interactively (never in a build step):\n"
              "  ssh-keygen -t ed25519 -f %USERPROFILE%\\.ssh\\nte_global_release -C nte-global-release", file=sys.stderr)
        return 2
    try:
        key_id, line = read_public_key(pub)
    except (ValueError, OSError) as exc:
        print(f"RELEASE GATE FAILED: {exc}", file=sys.stderr)
        return 2
    if args.key_id:
        key_id = args.key_id
    pins = [(key_id, line)]
    if args.allow_second is not None:
        try:
            pins.append(read_public_key(args.allow_second))
        except (ValueError, OSError) as exc:
            print(f"RELEASE GATE FAILED: --allow-second: {exc}", file=sys.stderr)
            return 2
    source = source_path.read_text(encoding="utf-8")
    try:
        existing = current_pins(source)
    except (RuntimeError, ValueError, SyntaxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    fingerprint = __import__("hashlib").sha256(base64.b64decode(line.split()[1])).digest()
    fp_text = "SHA256:" + base64.b64encode(fingerprint).decode().rstrip("=")
    if args.check:
        if existing == pins:
            print(f"OK: tree pins {key_id} {fp_text}")
            return 0
        print(f"RELEASE GATE FAILED: tree pins {existing!r}, expected {pins!r}", file=sys.stderr)
        return 2
    new_source = PIN_RE.sub(lambda _m: render_pins(pins), source, count=1)
    if new_source == source:
        print(f"unchanged: tree already pins {key_id} {fp_text}")
        return 0
    compile(new_source, str(source_path), "exec")
    source_path.write_text(new_source, encoding="utf-8", newline="\n")
    print(f"pinned {key_id} {fp_text} into {source_path}")
    print(f"public key line: {line} {key_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
