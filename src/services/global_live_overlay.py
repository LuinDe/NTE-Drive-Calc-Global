# Global 实时数据覆盖层：数据集与数据库 sha 一致时，按国服正式上线数据修正明音凛（文字、上线状态、规则开关）；不一致时自动关闭。
"""Global live overlay: release data the calculator's static DB does not have yet (``global_live_overlay_data``).

Active only while the running static DB is exactly the one the data was written for: the manifest's ``dataset_id``
AND the DB file's sha256 (the manifest value when it names this file with this size, else the file hash - the same
identity as the efficiency tables, ``arc_efficiency_service.db_sha256``).  An upstream DB update switches it off by
itself.  Dev / test switch: ``NTE_GLOBAL_OVERLAY`` = ``off`` (everything off) | ``on`` (the default groups) | a comma
list of groups (``text,awakening``); ``ENABLED_GROUPS`` (None = the defaults) can be set in memory.

What it changes (Akane Rin 1057, CN release 2026-10-15; work_g231/awaken/akane_cn/akane_overlay_spec.json):
- ``release_status``: classification available, release annotation row (CN date; the profile adds the Global date),
  the team simulator's explanation code akane_release_pending -> akane_values_unverified.
- ``text``: description texts read through the static DAO (``dao_patcher``) and the arc efficiency service
  (``patch_star_text``): awakening effects, passives 1 / 2, ultimate, 「月的对跖点」.  Translations: the language
  tables' DESC rows of the same zh text.
- ``awakening`` / ``passive2``: Akane's node rules and 烁星激昂 (awakening_node_rules/g2.py reads ``active_for_con``).
- ``ult_window``: 音障爆鸣 stage 2 from 4 s into 华彩连段 (``form_window``: approved and custom layouts).
- ``arc_release``: 「月的对跖点」 B4 release mode (team_fork_corrections reads ``active_for_con``).
The battle report's numbers are never changed (its native core keeps the 9-24 catalogue): ``battle_report_notice``
gives the one-line notice the page shows.  Qt-free.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from src.services import global_live_overlay_data as D

ENV = "NTE_GLOBAL_OVERLAY"


def parse_switch(value) -> set | None:
    """``NTE_GLOBAL_OVERLAY`` -> enabled groups (None = the default groups, empty = none)."""
    text = str(value or "").strip().casefold()
    if text in ("", "on", "default", "1", "true", "yes"):
        return None
    if text in ("off", "none", "0", "false", "no"):
        return set()
    if text == "all":
        return set(D.GROUPS)
    return {t.strip() for t in text.replace(";", ",").split(",") if t.strip() in D.GROUPS}


ENABLED_GROUPS: set | None = parse_switch(os.environ.get(ENV))


def group_on(group: str) -> bool:
    if group not in D.GROUPS:
        return False
    if ENABLED_GROUPS is None:
        return bool(D.GROUPS[group]["default"])
    return group in ENABLED_GROUPS


def groups_on() -> tuple:
    return tuple(g for g in D.GROUPS if group_on(g))


# ── identity ──────────────────────────────────────────────────────────────────
_KEY_MEMO: dict = {}


def _default_path() -> Path | None:
    try:
        from src.storage.sqlite.static_game_data_dao import resolve_static_database

        return resolve_static_database()
    except Exception:
        return None


def key_matches(static_path=None) -> bool:
    """The static DB is the one the overlay was written for (dataset id AND sha256; memo per path, size, mtime)."""
    path = Path(static_path) if static_path is not None else _default_path()
    if path is None:
        return False
    try:
        st = path.stat()
    except OSError:
        return False
    memo = (os.path.normcase(str(path.resolve())), int(st.st_size), int(st.st_mtime_ns))
    if memo not in _KEY_MEMO:
        # review L-F2: a manifest that cannot be read (or names no dataset) answers False without a memo, so a one-off
        # read failure does not keep the overlay off for the whole session; only a completed comparison is memoised
        try:
            from src.services.arc_efficiency_service import db_sha256, manifest_dataset

            block = manifest_dataset(path)
        except Exception:
            return False
        if not block.get("dataset_id"):
            return False
        try:
            ok = (str(block.get("dataset_id") or "") == D.OVERLAY_KEY["dataset_id"]
                  and str(db_sha256(path) or "").upper() == D.OVERLAY_KEY["static_sha256"].upper())
        except Exception:
            return False
        _KEY_MEMO[memo] = ok
    return _KEY_MEMO[memo]


def active(static_path=None, group: str | None = None) -> bool:
    """Overlay on for this DB (``static_path`` None = the application's static DB) and, with ``group``, that group."""
    if group is not None and not group_on(group):
        return False
    if group is None and not groups_on():
        return False
    return key_matches(static_path)


def path_of(con) -> Path | None:
    """The file of a sqlite3 connection's main database (None when unknown / in memory)."""
    try:
        rows = con.execute("PRAGMA database_list").fetchall()
    except Exception:
        return None
    name = next((str(r[2]) for r in rows if str(r[1]) == "main"), "")
    return Path(name) if name else None


def active_for_con(con, group: str | None = None) -> bool:
    path = path_of(con)
    return path is not None and active(path, group)


# ── release status ─────────────────────────────────────────────────────────────

def release_info(character_id: int, static_path=None) -> Mapping | None:
    """The overlay's release facts of a character (None when the overlay is off or has none)."""
    info = D.CHARACTER_RELEASE.get(int(character_id))
    if info is None or not active(static_path, "release_status"):
        return None
    return info


def global_release_date(character_id: int, static_path=None) -> str | None:
    info = release_info(character_id, static_path)
    return str(info.get("global_release_date") or "") or None if info else None


def release_annotation_rows(rows: list, static_path=None) -> list:
    """``list_catalog_character_release_annotations`` rows plus a synthesised row for an overlay character the DB has
    none for (shape of the DB rows; source kind official, one evidence key: the official notice)."""
    if not active(static_path, "release_status"):
        return rows
    have = {int(r.get("character_id") or 0) for r in rows}
    out = list(rows)
    for cid, info in sorted(D.CHARACTER_RELEASE.items()):
        if cid in have:
            continue
        out.append({"character_id": cid, "quality": info["quality"], "quality_source_kind": info["quality_source_kind"],
                    "acquisition_type": info["acquisition_type"],
                    "acquisition_source_kind": info["acquisition_source_kind"],
                    "mainland_release_date": info["mainland_release_date"],
                    "release_source_kind": info["release_source_kind"], "evidence_keys": (info["evidence_key"],)})
    return sorted(out, key=lambda r: int(r.get("character_id") or 0))


def unmodelled_codes(character_id: int, codes: Iterable[str], static_path=None) -> tuple:
    """Team simulator explanation codes with the overlay's replacements (akane_release_pending -> unverified)."""
    codes = tuple(codes or ())
    if int(character_id) not in D.CHARACTER_RELEASE or not active(static_path, "release_status"):
        return codes
    return tuple(D.UNMODELLED_CODE_MAP.get(str(c), c) for c in codes)


def code_map(static_path=None) -> dict:
    """{generated explanation code: shown code} while the overlay's release status is on (else {})."""
    return dict(D.UNMODELLED_CODE_MAP) if active(static_path, "release_status") else {}


# ── texts ──────────────────────────────────────────────────────────────────────

def _edit(text: str, edits) -> str:
    for kind, old, new in edits:
        if kind == "regex":
            text = re.sub(old, new, text, count=1)
        elif old in text:
            text = text.replace(old, new, 1)
    return text


def percent_text(value: float) -> str:
    """A fraction as the arc renderer writes it (0.28 -> "28%")."""
    return f"{float(value) * 100.0:.6f}".rstrip("0").rstrip(".") + "%"


def prism_text(damage_up1: float | None) -> str | None:
    """「月的对跖点」 release text of one refinement (the static Skill bonus = DamageUp1 x 4 written out)."""
    if damage_up1 is None:
        return None
    return D.PRISM_TEXT.replace("{S}", percent_text(float(damage_up1) * D.PRISM_STATIC_FACTOR))


_TEXT_MEMO: dict = {}


def text_tables(con) -> dict:
    """{"exact": {DB zh text: release zh text}, "prism": {refinement: release text}, "prism_old": DB template} built
    from the DB of ``con`` (cached per file)."""
    path = path_of(con)
    try:
        st = path.stat() if path is not None else None
        memo = (os.path.normcase(str(path)), st.st_size, st.st_mtime_ns) if st is not None else None
    except OSError:
        memo = None
    if memo is not None and memo in _TEXT_MEMO:
        return _TEXT_MEMO[memo]
    exact: dict = {}
    for effect_id, text in con.execute("SELECT effect_id, description_zh FROM character_awaken_effect "
                                       "WHERE character_id=?", (D.AKANE,)):
        new = D.AWAKEN_TEXT.get(str(effect_id))
        if new and text and new != text:
            exact[str(text)] = new
    for (ability, field), edits in D.ABILITY_EDITS.items():
        if field not in ("description_zh", "short_description_zh"):
            continue
        for (text,) in con.execute(f"SELECT {field} FROM gameplay_ability_description WHERE ability_id=?", (ability,)):
            if text:
                new = _edit(str(text), edits)
                if new != text:
                    exact[str(text)] = new
    prism: dict = {}
    prism_old = None
    row = con.execute("SELECT description_zh FROM fork_star_level WHERE star_pack_id=? ORDER BY star_level LIMIT 1",
                      (D.PRISM_PACK,)).fetchone()
    if row is not None:
        prism_old = str(row[0] or "")
        for level, value in con.execute(
                "SELECT p.star_level, v.value FROM fork_star_parameter p JOIN fork_refinement_parameter_value v "
                "ON v.name_id = p.name_id AND v.refinement_level = p.star_level "
                "WHERE p.star_pack_id=? AND p.name_id='buff_Prism_DamageUp1'", (D.PRISM_PACK,)):
            text = prism_text(value)
            if text:
                prism[int(level)] = text
    out = {"exact": exact, "prism": prism, "prism_old": prism_old}
    if memo is not None:
        _TEXT_MEMO[memo] = out
    return out


class RowPatcher:
    """Post-processing of the static DAO's rows (``StaticGameDataDao._rows``) while the overlay is on: release texts
    by exact match of the DB zh text (any ``*description_zh`` column; the arc text per ``star_level``) and the
    classification of overlay characters.  Rows are changed in place and returned."""

    def __init__(self, tables: Mapping, texts: bool, release: bool) -> None:
        self.exact = dict(tables.get("exact") or {}) if texts else {}
        self.prism = dict(tables.get("prism") or {}) if texts else {}
        self.prism_old = tables.get("prism_old") if texts else None
        self.release = {cid: info["classification"] for cid, info in D.CHARACTER_RELEASE.items()} if release else {}

    def __call__(self, rows: list) -> list:
        if not rows:
            return rows
        keys = rows[0].keys()
        text_keys = [k for k in keys if k.endswith("description_zh")] if (self.exact or self.prism) else []
        classify = bool(self.release) and "classification" in keys and "character_id" in keys
        if not text_keys and not classify:
            return rows
        for row in rows:
            for key in text_keys:
                value = row.get(key)
                # isinstance, not type() is str (logic check K4: never reject a str subclass such as LStr / FVal;
                # the rows arrive here as plain sqlite str, before the display layer's description pass)
                if not isinstance(value, str) or not value:
                    continue
                new = self.exact.get(value)
                if new is None and value == self.prism_old:
                    new = self.prism.get(int(row.get("star_level") or 1) if "star_level" in row else 1)
                if new is not None:
                    row[key] = new
            if classify:
                try:
                    cid = int(row.get("character_id") or 0)
                except (TypeError, ValueError):
                    continue
                if cid in self.release:
                    row["classification"] = self.release[cid]
        return rows


def dao_patcher(database_path, connection) -> Callable | None:
    """The DAO's row patcher for its DB (None while the overlay is off for it)."""
    texts = active(database_path, "text")
    release = active(database_path, "release_status")
    if not texts and not release:
        return None
    try:
        tables = text_tables(connection) if texts else {}
    except Exception:
        tables = {}
    return RowPatcher(tables, texts, release)


def patch_star_text(fork_id: str, level: int, description: str, static_path=None, con=None) -> str:
    """The arc efficiency page's star text (read with its own connection): the release text of 「月的对跖点」."""
    if str(fork_id) != D.PRISM_FORK or not active(static_path, "text"):
        return description
    try:
        if con is None:
            import sqlite3

            own = sqlite3.connect(f"{Path(static_path).absolute().as_uri()}?mode=ro", uri=True)
            try:
                tables = text_tables(own)
            finally:
                own.close()
        else:
            tables = text_tables(con)
    except Exception:
        return description
    if description != tables.get("prism_old"):
        return description
    return tables["prism"].get(int(level)) or description


# ── rules the layouts read ─────────────────────────────────────────────────────

def form_window(character_id: int, form_code: str, window, static_path=None):
    """The window of a form's exit / window step (``team_form_actions.FORMS`` / the custom palette's state):
    音障爆鸣 stage 2 from 4 s while ``ult_window`` is on."""
    if (int(character_id) == D.AKANE and str(form_code or "") == D.FORM_CODE and window is not None
            and active(static_path, "ult_window")):
        return tuple(D.ULT_STAGE2_WINDOW_S)
    return window


def label_ko(character_id: int, seq: int, text: str, static_path=None) -> str:
    """The reviewed rotation's Korean step tooltip with the overlay's term map (烁星激昂: ATK +20 % for 20 s)."""
    pairs = D.LABEL_KO.get((int(character_id), int(seq or 0)))
    if not pairs or not text or not active(static_path, "passive2"):
        return text
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def battle_report_notice(character_ids: Iterable[int], static_path=None) -> str | None:
    """One line for the battle report page when a record holds an overlay character: the native analysis core keeps
    the 9-24 catalogue (pre-release awakening crit / resonance ATK, arc conditions not computed)."""
    ids = {int(c) for c in character_ids or () if c is not None}
    if D.AKANE not in ids or not active(static_path):
        return None
    from src.i18n_runtime import L as _L

    return _L('明音凛：实战记录分析仍按上线前数据（9-24）计算（觉醒暴击率、共鸣攻击力为旧值，弧盘条件效果未计算）；队伍模拟与效率表已按国服上线数据。')


def unverified_note(static_path=None) -> str | None:
    """Short badge text of the overlay character rows (efficiency tables, tooltips)."""
    if not active(static_path):
        return None
    from src.i18n_runtime import L as _L

    return _L('国服上线数据（10-15）· 部分未确认')


def status(static_path=None) -> dict:
    """What the overlay does for this DB (tests, diagnostics)."""
    return {"key": key_matches(static_path), "groups": groups_on(),
            "active": {g: active(static_path, g) for g in D.GROUPS}}
