"""Stage the Elyms Core resource change and bind it to the native bundle's checked metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from elyms_core import patch_core


CORE = "nte-core.exe"
SOURCE = "licenses/native-capture/core/SOURCE.md"
COMPATIBILITY = "licenses/native-capture/compatibility.json"
BUNDLE = "component-bundle.json"
OFFICIAL_BUNDLE_SHA256 = "bfb932b6a87bf7b494d586dd582f2d37c9bf62c48dabadbf8884bef2ec7f25d0"


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _mapped_files(original: Path, catalog: Path) -> dict[str, bytes]:
    bundle_bytes = (original / BUNDLE).read_bytes()
    if hashlib.sha256(bundle_bytes).hexdigest() != OFFICIAL_BUNDLE_SHA256:
        raise ValueError("the Elyms native stage requires the original 2.3.1 component-bundle.json")
    bundle = json.loads(bundle_bytes)
    inputs = {}
    for relative in (CORE, SOURCE, COMPATIBILITY):
        data = (original / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != bundle["files"][relative]:
            raise ValueError(f"official native input differs from the 2.3.1 manifest: {relative}")
        inputs[relative] = data

    core = patch_core(inputs[CORE], catalog)
    core_sha = hashlib.sha256(core).hexdigest()
    original_sha = bundle["files"][CORE]
    provenance = {
        "character_id": 1090,
        "source": "build_tools/elyms_core.py",
        "upstream_core_sha256": original_sha,
        "global_core_sha256": core_sha,
    }
    compatibility = json.loads(inputs[COMPATIBILITY])
    compatibility["core_sha256"] = core_sha
    compatibility["core_reused"] = False
    # core_rebuilt describes a Rust compilation; Global edits packaged resource data.
    compatibility["global_catalog_patch"] = provenance
    validation = compatibility["validation"]
    validation["upstream_build"] = validation["build"]
    validation["build"] = "Global native Core with CN 1.5.4 Elyms catalog data; see the Core SOURCE.md."
    source = inputs[SOURCE].rstrip() + (
        "\n\n## NTE Drive Calc Global resource modification\n\n"
        "Global 2.3.5 includes CN 1.5.4 character 1090 (Elyms) in the embedded character and "
        "equipment mapping resources used by native inventory sync. The Rust source identity and "
        "upstream test results above describe the base Core. The Global source package includes "
        "build_tools/elyms_core.py and the catalog inputs to reproduce this change.\n\n"
        f"Upstream Core SHA-256: {original_sha}\n\nGlobal Core SHA-256: {core_sha}\n"
    ).encode("utf-8")
    result = {CORE: core, SOURCE: source, COMPATIBILITY: _json_bytes(compatibility)}
    bundle["global_catalog_patch"] = provenance
    for relative, payload in result.items():
        bundle["files"][relative] = hashlib.sha256(payload).hexdigest()
        bundle["file_sizes"][relative] = len(payload)
    result[BUNDLE] = _json_bytes(bundle)
    return result


def stage_core_bundle(internal: Path) -> int:
    """Apply only in a fresh installer stage; the integrity manifest is written last."""
    files = _mapped_files(internal, internal / "data/game_static.sqlite3")
    for relative, payload in files.items():
        (internal / relative).write_bytes(payload)
    return len(files)


def verify_core_bundle(internal: Path, official_internal: Path) -> str:
    """Prevent packaging a self-consistent old native bundle with a new Global executable."""
    expected = _mapped_files(official_internal, internal / "data/game_static.sqlite3")
    for relative, payload in expected.items():
        if (internal / relative).read_bytes() != payload:
            raise ValueError(f"staged file differs from the Elyms native build: {relative}")
    return hashlib.sha256(expected[CORE]).hexdigest()
