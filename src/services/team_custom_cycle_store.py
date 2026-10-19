# 队伍模拟「直接输入」模式：按账号保存循环（accounts/<账号>/config/team_custom_cycles.json）。
"""Per-account persistence of custom cycles (standard library only).

File: ``<account config dir>/team_custom_cycles.json``::

    {"version": 1,
     "last": {"mode": "custom", "cycle": {team, steps, options}},
     "cycles": [{"name": "...", "updated": "2026-10-04T21:15:00", "team": [...], "steps": [...], "options": {...}}]}

``team`` / ``steps`` / ``options`` are stored as plain JSON (``team_custom_notation.step_to_json``,
``team_custom_cycle_service.options_to_json``); this module only keeps the list.

Team rows (``features/team_simulation/page.py`` ``team_json`` / ``apply_team``)::

    {"character_id": 1072, "awakening_level": 3, "selected_awaken_effect_ids": ["Effect1", "Effect3", "Effect5"],
     "fork_id": "...", "fork_refinement_level": 1, "suit_id": "..."}

The awakening node set (free selection, Korean UI "돌파") was added **without a version change** (an older version
would open a version 2 file read-only): ``awakening_level`` = the number of selected effects, so an older version
reads Effect1..count.  A row without ``selected_awaken_effect_ids`` (saved before) means Effect1..awakening_level -
the old result; unknown ids are dropped, a malformed value keeps the template's selection (:func:`team_row_awakening`,
``team_awakening.from_json_row``).  Ids are plain str, never translated.

* Writes go to ``<name>.tmp`` in the same folder followed by ``os.replace`` (atomic); nothing is ever deleted.
* A file that is not valid UTF-8 JSON (a UTF-8 byte order mark is accepted) is moved aside as
  ``team_custom_cycles.corrupt-<timestamp>.json`` and an empty list is used.
* A file written by a newer version (``version`` > 1) is shown read-only: nothing is written (StoreReadOnly).
* Names are stripped, 1-40 characters and unique per account (case-sensitive).
"""
from __future__ import annotations

import copy
import datetime
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

VERSION = 1
FILE_NAME = "team_custom_cycles.json"
MAX_NAME = 40


class StoreReadOnly(RuntimeError):
    """The file was saved by a newer version; it is listed but never rewritten."""


@dataclass
class CycleFile:
    version: int = VERSION
    cycles: list = field(default_factory=list)      # [{"name", "updated", "team", "steps", "options"}, ...]
    last: dict | None = None                        # {"mode": "approved" | "custom", "cycle": {...}}
    read_only: bool = False
    moved_aside: str = ""                           # path the corrupt file was moved to ("" = it was readable)

    def names(self) -> list[str]:
        return [str(c["name"]) for c in self.cycles]

    def get(self, name: str) -> dict | None:
        return next((c for c in self.cycles if c.get("name") == name), None)


def path_for(config_dir) -> Path:
    return Path(config_dir) / FILE_NAME


def team_row_awakening(row, valid_ids=None, template=None):
    """The awakening node set of a stored team row (team_awakening.AwakeningSel; see the module docstring)."""
    from src.services import team_awakening

    return team_awakening.from_json_row(row, valid_ids, template)


def clean_name(name) -> str:
    """Stripped name; ValueError when it is empty or longer than MAX_NAME characters."""
    text = " ".join(str(name or "").split())
    if not text or len(text) > MAX_NAME:
        raise ValueError(f"cycle name must have 1-{MAX_NAME} characters")
    return text


def _migrate(data: dict) -> dict:
    """Older versions -> the current shape (identity for version 1)."""
    return data


def load(path) -> CycleFile:
    """Read the file; never raises (missing file = empty list, corrupt file moved aside)."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return CycleFile()
    except OSError:
        return CycleFile()
    try:
        data = json.loads(raw.decode("utf-8-sig"))      # a BOM (Notepad) is fine; another encoding is corrupt
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (ValueError, RecursionError):                # UnicodeDecodeError is a ValueError
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        aside = path.with_name(f"{path.stem}.corrupt-{stamp}.json")
        try:
            os.replace(path, aside)
        except OSError:
            return CycleFile()
        return CycleFile(moved_aside=str(aside))
    try:
        version = int(data.get("version") or VERSION)
    except (TypeError, ValueError, OverflowError):
        version = VERSION
    read_only = version > VERSION
    if not read_only:
        data = _migrate(data)
    cycles = []
    seen = set()
    for item in data.get("cycles") if isinstance(data.get("cycles"), list) else ():
        if not isinstance(item, dict):
            continue
        try:
            name = clean_name(item.get("name"))
        except ValueError:
            continue
        if name in seen:
            continue
        seen.add(name)
        cycles.append({"name": name, "updated": str(item.get("updated") or ""),
                       "team": item.get("team") if isinstance(item.get("team"), list) else [],
                       "steps": item.get("steps") if isinstance(item.get("steps"), list) else [],
                       "options": item.get("options") if isinstance(item.get("options"), dict) else {}})
    last = data.get("last") if isinstance(data.get("last"), dict) else None
    return CycleFile(version=version, cycles=cycles, last=last, read_only=read_only)


def _write(path: Path, file: CycleFile) -> None:
    if file.read_only:
        raise StoreReadOnly(str(path))
    payload = {"version": VERSION, "last": file.last, "cycles": file.cycles}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def save_cycle(path, cycle: dict) -> CycleFile:
    """Add the cycle, or replace the one with the same name.  Raises ValueError (name), StoreReadOnly, OSError."""
    path = Path(path)
    file = load(path)
    if file.read_only:
        raise StoreReadOnly(str(path))
    entry = copy.deepcopy(dict(cycle))
    entry["name"] = clean_name(entry.get("name"))
    entry["updated"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    for key, empty in (("team", []), ("steps", []), ("options", {})):
        entry.setdefault(key, empty)
    for i, existing in enumerate(file.cycles):
        if existing["name"] == entry["name"]:
            file.cycles[i] = entry
            break
    else:
        file.cycles.append(entry)
    _write(path, file)
    return file


def delete_cycle(path, name: str) -> CycleFile:
    """Rewrite the file without the named cycle (the file itself is never deleted)."""
    path = Path(path)
    file = load(path)
    if file.read_only:
        raise StoreReadOnly(str(path))
    kept = [c for c in file.cycles if c["name"] != name]
    if len(kept) != len(file.cycles):
        file.cycles = kept
        _write(path, file)
    return file


def save_last(path, last: dict | None) -> CycleFile:
    """Store the working state (mode, steps, options) next to the named cycles."""
    path = Path(path)
    file = load(path)
    if file.read_only:
        raise StoreReadOnly(str(path))
    file.last = copy.deepcopy(last) if last is not None else None
    _write(path, file)
    return file
