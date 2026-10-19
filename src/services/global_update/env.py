# 자동 업데이트 재실행 후 환경 자가 치유: Setup이 물려준 TMP/TEMP가 updates\ 안을 가리키면 되돌림
"""Environment self-heal after a relaunch through Setup (design_final §7.5, D10).

The launcher runs Setup with ``TMP``/``TEMP`` = ``{app}\\updates\\<tag>\\tmp`` so that Inno's ``{tmp}`` lives in the
admin-only folder.  Setup's gated ``[Run]`` entry restarts the application with Setup's environment, so the new
instance would inherit a temp directory that the janitor deletes.  ``restore_temp_environment`` runs before anything
else (``gui_startup.run_gui``) and points the two variables back at ``%LOCALAPPDATA%\\Temp``; child processes then
inherit the healed values.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def restore_temp_environment(app_dir: str | os.PathLike) -> list[str]:
    """Names of the variables that were healed (``[]`` when nothing pointed into ``<app_dir>\\updates``)."""
    try:
        updates = Path(app_dir).resolve() / "updates"
    except (OSError, ValueError):
        return []
    local = os.environ.get("LOCALAPPDATA") or ""
    replacement = str(Path(local) / "Temp") if local else ""
    healed: list[str] = []
    for name in ("TMP", "TEMP"):
        value = os.environ.get(name)
        if not value:
            continue
        try:
            resolved = Path(value).resolve()
        except (OSError, ValueError):
            continue
        if not _under(resolved, updates):
            continue
        if replacement:
            os.environ[name] = replacement
        else:
            os.environ.pop(name, None)
        healed.append(name)
    if healed:
        tempfile.tempdir = None
    return healed
