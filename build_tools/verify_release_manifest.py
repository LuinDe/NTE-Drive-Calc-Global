r"""Release verifier of NTE Drive Calc Global: checks a signed release manifest with TWO independent verifiers
(OpenSSH ``ssh-keygen -Y verify`` and the program's own pure-Python sshsig/Ed25519 verifier, imported from the
source tree the release was built from) and, with ``--github``, runs the program's exact release-selection code
against the real GitHub API JSON.

Signing (maintainer, interactive; the private key never leaves %USERPROFILE%\.ssh and its passphrase is typed by you):

    ssh-keygen -Y sign -f %USERPROFILE%\.ssh\nte_global_release -n nte-drive-calc-global-release NTE_Drive_Calc_<version>_release.json

    -> writes NTE_Drive_Calc_<version>_release.json.sig next to the manifest (the asset name the program expects).

Usage (Python 3.11; read-only, nothing is uploaded):

    verify_release_manifest.py --local <dir> --tree <root> [--notes <body.md>] [--pub <file.pub>] [--no-ssh-keygen]
        <dir> holds NTE_Drive_Calc_<v>_Multilingual_Setup.exe, NTE_Drive_Calc_<v>_release.json and its .sig.
        Checks: the manifest names that installer with its real size and SHA-256; the signature verifies with the
        key(s) pinned in <root>/src/app/global_release.py (or --pub) under both verifiers; manifest rules of the app;
        with --notes, the signed notes digest equals that release body (the app shows the notes only then).

    verify_release_manifest.py --github <tag> --tree <root> [--draft] [--pub <file.pub>] [--download-dir <dir>]
        Fetches the releases JSON of LuinDe/NTE-Drive-Calc-Global (``gh api``; authenticated, so a draft is visible to
        its owner), runs the app's select_candidate() as a build one step older than <tag> would, downloads the
        manifest, signature and installer (published: through the app's own client; draft: ``gh release download``)
        and verifies everything as --local does, plus the API digest of each asset, the four H2 sections of the
        release body, the signed notes digest against the body GitHub serves and (published) the app's own
        check-time verification (the release is announced with verified notes).  With --draft the URL-equality rules are reported, not enforced (a draft's asset URLs carry an
        ``untagged-...`` path until it is published) - run it again without --draft after publishing.

    verify_release_manifest.py --sign-command <manifest>      print the exact signing command for that manifest

Exit 0 = "OK" printed; 1 = verification failed; 2 = usage / environment error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types

NAMESPACE = "nte-drive-calc-global-release"
REPO = "LuinDe/NTE-Drive-Calc-Global"
BODY_SECTIONS = ("한국어", "English", "日本語", "中文")
DEFAULT_PUB = pathlib.Path(os.environ.get("USERPROFILE") or str(pathlib.Path.home())) / ".ssh" / "nte_global_release.pub"


def fail(message: str, code: int = 1) -> int:
    print(f"FAILED: {message}")
    return code


def import_tree(root: pathlib.Path):
    """Imports the release modules of the given tree (no Qt; loguru is stubbed with logging when absent)."""
    src = root / "src"
    if not (src / "app" / "global_release.py").is_file():
        raise SystemExit(f"not a tree root: {root}")
    sys.path.insert(0, str(root))
    try:
        import loguru  # noqa: F401
    except ImportError:
        stub = types.ModuleType("src.utils.logger")
        stub.logger = logging.getLogger("nte-release-check")
        sys.modules["src.utils.logger"] = stub
    from src.app import global_release as gr
    from src.services.global_update import client as client_mod
    from src.services.global_update import verify as verify_mod
    from src.services.global_update.models import UpdateError
    return gr, client_mod, verify_mod, UpdateError


def read_pub(path: pathlib.Path) -> tuple[str, str]:
    if path.suffix != ".pub":
        raise SystemExit(f"refusing to read {path.name}: only .pub files are read")
    parts = path.read_text(encoding="utf-8").strip().split()
    if len(parts) < 2 or parts[0] != "ssh-ed25519":
        raise SystemExit(f"{path}: not an ssh-ed25519 public key line")
    return (parts[2] if len(parts) > 2 else "nte-global-release"), f"ssh-ed25519 {parts[1]}"


def pinned_keys(gr, pub: pathlib.Path | None) -> list[tuple[str, str]]:
    if pub is not None:
        return [read_pub(pub)]
    return [(str(k), str(v)) for k, v in gr.RELEASE_SIGNING_KEYS]


def ssh_keygen_verify(manifest: pathlib.Path, signature: pathlib.Path, keys: list[tuple[str, str]]) -> tuple[bool, str]:
    exe = shutil.which("ssh-keygen")
    if exe is None:
        return False, "ssh-keygen not found on PATH"
    with tempfile.TemporaryDirectory(prefix="nte_rel_") as tmp:
        allowed = pathlib.Path(tmp) / "allowed_signers"
        allowed.write_text("".join(f'{key_id} namespaces="{NAMESPACE}" {line}\n' for key_id, line in keys),
                           encoding="utf-8", newline="\n")
        last = ""
        for key_id, _line in keys:
            with manifest.open("rb") as stdin:
                done = subprocess.run([exe, "-Y", "verify", "-f", str(allowed), "-I", key_id, "-n", NAMESPACE,
                                       "-s", str(signature)], stdin=stdin, capture_output=True, text=True)
            last = (done.stdout + done.stderr).strip()
            if done.returncode == 0:
                return True, last
        return False, last


def verify_files(gr, verify_mod, UpdateError, installer: pathlib.Path, manifest: pathlib.Path,
                 signature: pathlib.Path, keys, use_ssh_keygen: bool, api_sha256: str | None = None,
                 body: str | None = None) -> list[str]:
    problems: list[str] = []
    if not keys:
        return ["no release signing key: the tree pins none and --pub was not given"]
    data = installer.read_bytes() if installer.is_file() else b""
    size, sha = len(data), hashlib.sha256(data).hexdigest()
    manifest_bytes, signature_bytes = manifest.read_bytes(), signature.read_bytes()
    try:
        parsed = verify_mod.parse_manifest(manifest_bytes)
    except UpdateError as exc:
        return [f"manifest: {exc.code} {exc.detail}"]
    tag = parsed.tag
    for label, expected, actual in (("installer file name", gr.installer_name(tag), installer.name),
                                    ("manifest file name", gr.manifest_name(tag), manifest.name),
                                    ("signature file name", gr.signature_name(tag), signature.name)):
        if expected != actual:
            problems.append(f"{label}: expected {expected}, found {actual}")
    if api_sha256 is not None and api_sha256 != sha:
        problems.append(f"installer SHA-256 {sha} != GitHub API digest {api_sha256}")
    if not getattr(parsed, "notes_sha256", ""):
        problems.append("the manifest does not bind the release notes (no notes_sha256: rebuild with --notes)")
    elif body is not None:
        actual = verify_mod.notes_digest(body)
        if actual != parsed.notes_sha256:
            problems.append(f"release body digest {actual} != signed notes_sha256 {parsed.notes_sha256} "
                            "(the app would show 'notes could not be verified')")
        else:
            print(f"  release notes   : OK (normalised body sha256 {actual})")
    else:
        print(f"  release notes   : bound ({parsed.notes_sha256}); pass --notes <body.md> to compare")
    current = gr.parse_global_tag(tag)
    try:
        result = verify_mod.verify_manifest(manifest_bytes, signature_bytes, keys, gr.RELEASE_SIG_NAMESPACE,
                                            expected_tag=tag, expected_size=size, expected_sha256=sha,
                                            current_version=current, size_min=gr.INSTALLER_SIZE_MIN,
                                            size_max=gr.INSTALLER_SIZE_MAX)
        print(f"  python verifier : OK (key {result.key_id}; {tag}; installer {size} bytes sha256 {sha})")
        print(f"  in-app updates allowed from running version >= {result.min_global_version or '(any)'}")
    except UpdateError as exc:
        problems.append(f"python verifier: {exc.code} {exc.detail}")
    if gr.RELEASE_SIG_NAMESPACE != NAMESPACE:
        problems.append(f"namespace of the tree {gr.RELEASE_SIG_NAMESPACE!r} != {NAMESPACE!r}")
    if use_ssh_keygen:
        ok, text = ssh_keygen_verify(manifest, signature, keys)
        if ok:
            print(f"  ssh-keygen      : OK ({text.splitlines()[0] if text else ''})")
        else:
            problems.append(f"ssh-keygen -Y verify: {text}")
    return problems


def local_mode(args, gr, client_mod, verify_mod, UpdateError) -> int:
    folder = args.local.resolve()
    manifests = sorted(folder.glob("NTE_Drive_Calc_*_release.json"))
    if len(manifests) != 1:
        return fail(f"expected exactly one NTE_Drive_Calc_*_release.json in {folder}, found {len(manifests)}")
    manifest = manifests[0]
    try:
        tag = verify_mod.parse_manifest(manifest.read_bytes()).tag
    except UpdateError as exc:
        return fail(f"manifest: {exc.code} {exc.detail}")
    installer = folder / gr.installer_name(tag)
    signature = folder / gr.signature_name(tag)
    for path in (installer, signature):
        if not path.is_file():
            return fail(f"missing {path.name}" + ("  (sign the manifest first: --sign-command)" if path == signature else ""))
    print(f"{tag}: {folder}")
    body = args.notes.read_bytes().decode("utf-8") if args.notes is not None else None
    problems = verify_files(gr, verify_mod, UpdateError, installer, manifest, signature,
                            pinned_keys(gr, args.pub), not args.no_ssh_keygen, body=body)
    for problem in problems:
        print(f"  - {problem}")
    if problems:
        return fail(f"{len(problems)} problem(s)")
    print("OK")
    return 0


def gh_json(*argv: str):
    exe = shutil.which("gh")
    if exe is None:
        raise SystemExit("gh (GitHub CLI) not found")
    done = subprocess.run([exe, *argv], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit(f"gh {' '.join(argv)} failed: {done.stderr.strip()}")
    return json.loads(done.stdout)


def github_mode(args, gr, client_mod, verify_mod, UpdateError) -> int:
    tag = args.github
    version = gr.parse_global_tag(tag)
    if version is None:
        return fail(f"{tag!r} is not a Global tag (v<major>.<minor>.<patch>[-global.<n>])", 2)
    releases = gh_json("api", f"repos/{REPO}/releases?per_page={gr.API_PER_PAGE}")
    matching = [r for r in releases if isinstance(r, dict) and r.get("tag_name") == tag]
    if len(matching) != 1:
        return fail(f"{len(matching)} releases with tag {tag}")
    release = matching[0]
    problems: list[str] = []
    is_draft = release.get("draft") is True
    if is_draft and not args.draft:
        return fail(f"{tag} is still a draft: pass --draft (and run again after publishing)")
    if not is_draft and args.draft:
        print("  note: the release is already published; checking it as published")
    body = release.get("body") or ""
    heads = {line[3:].strip() for line in body.replace("\r\n", "\n").split("\n") if line.startswith("## ")}
    missing_sections = [s for s in BODY_SECTIONS if s not in heads]
    if missing_sections:
        problems.append(f"release body lacks the H2 sections {missing_sections}")
    if release.get("immutable") is False and not is_draft:
        print("  warning: the release is not immutable (enable Settings -> Releases -> Immutable releases)")
    # the app's own selection, as the build one step older would run it (a plain tag such as v2.3.2: the previous
    # patch; otherwise 0.0.0-global.1 - any running version older than the tag is enough for the selection rules)
    if version.n > 1:
        previous = gr.GlobalVersion(version.major, version.minor, version.patch, version.n - 1)
    elif version.n == 0 and version.patch > 0:
        previous = gr.GlobalVersion(version.major, version.minor, version.patch - 1, 0)
    else:
        previous = gr.GlobalVersion(0, 0, 0, 1)
    settings = gr.default_update_settings()
    view = dict(release)
    if is_draft:
        # a draft's URLs carry an untagged-... path; evaluate the rest of the rules as if it were published
        view.update(draft=False, html_url=gr.release_html_url(tag))
        view["assets"] = [dict(a, browser_download_url=gr.asset_download_url(settings.download_base, tag, a.get("name", "")))
                          for a in release.get("assets") or [] if isinstance(a, dict)]
        print("  draft: URL-equality rules skipped (re-run without --draft after publishing)")
    others = [r for r in releases if isinstance(r, dict) and r is not release and r.get("draft") is False]
    try:
        outcome = client_mod.select_candidate([view, *others], current=previous, settings=settings)
    except UpdateError as exc:
        return fail(f"app selection: {exc.code} {exc.detail}")
    candidate = outcome.candidate
    if candidate is None or candidate.tag != tag:
        reasons = [f"{t}: {r}" for t, r in outcome.rejected]
        return fail(f"the app would not offer {tag} to {previous.text}: {reasons or 'a newer release wins'}")
    print(f"  app selection   : OK ({tag} offered to {previous.text}; installer {candidate.installer.size} bytes, "
          f"API sha256 {candidate.installer.sha256})")
    if not is_draft:
        # the app verifies the signed manifest during the check (review r5 F1): it must announce this release
        checked = client_mod.GlobalUpdateClient(settings, current_version=previous)
        if args.pub is not None:
            import dataclasses
            checked.settings = dataclasses.replace(settings, signing_keys=tuple(pinned_keys(gr, args.pub)))
        try:
            verified = checked.verify_candidate(outcome)
        except UpdateError as exc:
            return fail(f"app check-time verification: {exc.code} {exc.detail}")
        if verified.candidate is None:
            problems.append(f"the app's check-time verification rejects {tag}: {verified.unusable_code}")
        elif not verified.candidate.notes_verified:
            problems.append("the app would announce the release WITHOUT its notes (body digest != notes_sha256)")
        else:
            print("  app check       : OK (announced with verified notes)")
    keep = args.download_dir is not None
    folder = (args.download_dir.resolve() if keep else pathlib.Path(tempfile.mkdtemp(prefix="nte_rel_dl_")))
    folder.mkdir(parents=True, exist_ok=True)
    try:
        names = [gr.installer_name(tag), gr.manifest_name(tag), gr.signature_name(tag)]
        if is_draft:
            exe = shutil.which("gh")
            for name in names:
                done = subprocess.run([exe, "release", "download", tag, "-R", REPO, "-p", name, "-D", str(folder),
                                       "--clobber"], capture_output=True, text=True)
                if done.returncode != 0:
                    return fail(f"gh release download {name}: {done.stderr.strip()}")
        else:
            client = client_mod.GlobalUpdateClient(settings, current_version=previous)
            (folder / names[1]).write_bytes(client.fetch_small(candidate.manifest))
            (folder / names[2]).write_bytes(client.fetch_small(candidate.signature))
            client.download(candidate.installer, folder / names[0])     # streaming size + SHA-256 gate
        for asset, name in ((candidate.manifest, names[1]), (candidate.signature, names[2])):
            actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            if asset is not None and actual != asset.sha256:
                problems.append(f"{name}: SHA-256 {actual} != API digest {asset.sha256}")
        problems += verify_files(gr, verify_mod, UpdateError, folder / names[0], folder / names[1], folder / names[2],
                                 pinned_keys(gr, args.pub), not args.no_ssh_keygen, api_sha256=candidate.installer.sha256,
                                 body=release.get("body") or "")
    finally:
        if not keep:
            shutil.rmtree(folder, ignore_errors=True)
    for problem in problems:
        print(f"  - {problem}")
    if problems:
        return fail(f"{len(problems)} problem(s)")
    print("OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a signed NTE Drive Calc Global release manifest.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", type=pathlib.Path)
    mode.add_argument("--github", metavar="TAG")
    mode.add_argument("--sign-command", type=pathlib.Path, metavar="MANIFEST")
    parser.add_argument("--tree", type=pathlib.Path, help="source tree root the release was built from")
    parser.add_argument("--pub", type=pathlib.Path, default=None,
                        help="public key to verify with instead of the tree's pinned keys (e.g. a sandbox test key)")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--notes", type=pathlib.Path, default=None,
                        help="--local: the release body (.md) the GitHub release will show; compared with notes_sha256")
    parser.add_argument("--download-dir", type=pathlib.Path, default=None)
    parser.add_argument("--no-ssh-keygen", action="store_true", help="skip the OpenSSH verifier (not for releases)")
    args = parser.parse_args()
    if args.sign_command is not None:
        print(f'ssh-keygen -Y sign -f "%USERPROFILE%\\.ssh\\nte_global_release" -n {NAMESPACE} "{args.sign_command}"')
        print(f"(writes {args.sign_command.name}.sig; then: verify_release_manifest.py --local "
              f'"{args.sign_command.resolve().parent}" --tree <root>)')
        return 0
    if args.tree is None:
        parser.error("--tree is required")
    gr, client_mod, verify_mod, UpdateError = import_tree(args.tree.resolve())
    if args.local is not None:
        return local_mode(args, gr, client_mod, verify_mod, UpdateError)
    return github_mode(args, gr, client_mod, verify_mod, UpdateError)


if __name__ == "__main__":
    sys.exit(main())
