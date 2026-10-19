# 弧盘效率表（Global）：按单人已审核循环的伤害比较角色可装备的弧盘；预先计算的数据、本机缓存与后台重新计算。
"""Arc efficiency table (Global 2.3.1).

One cell = one character alone on its reviewed rotation (team simulation ``solo_session``: graduation template, only
the arc and refinement swapped, the Global arc corrections B1-B4 on), ``loops`` passes, first visit "opener".  The
characters are those with an arc flagged exclusive to them (``fork_item.exclusive_character_ids_json``, JSON string
ids), a graduation template and an approved rotation; regular characters without an exclusive arc are not listed
(user decision U1).  Their equippable arcs follow the data's only rule (rule A: ``raw_group_type == group_type``),
other characters' exclusive arcs included and flagged; hiding them is a display filter.  Refinements: 1 and the
arc's ``max_star``.  100 % = the character's exclusive arc at refinement 1 (or, as a toggle, the exclusive arc at the
same refinement).

Delivery (three layers): L1 = ``arc_efficiency_data`` (generated at build time by
``build_tools/gen_arc_efficiency_data.py``, inside the executable), L2 = ``<config>/arc_efficiency_cache.json``
(rows computed on this PC when L1 does not match), L3 = the page's memory.  A row key is (``ALGO_VERSION``, static DB
sha256, ``ENGINE_FP``, the enabled arc corrections, character, arc, refinement, loops, entry); language and account
are not part of it (the results do not depend on them - tests).  L1 is computed with every correction on (B1-B4): a
run with the dev switch ``NTE_TEAM_FORK_CORRECTIONS`` set otherwise never uses it.  L1 is used for a character when its key and the character's arc set equal
the current data; otherwise L2 when it holds every row; otherwise the character is recomputed in the background
(``Computation``: viewed character first, exclusive R1 first, cancel within one run).

Row value: ``Row(damage, flags, end_us, active_us)``; damage rounded to 0.1.  Flags: ``FLAG_UNRESOLVED`` (an arc buff
whose value the engine could not resolve), ``FLAG_DEDUP`` (B2 removed a double-counted permanent bonus),
``FLAG_SUPPLEMENT`` (a B3 / B4 Global supplement interval was applied to at least one hit), ``FLAG_NO_HIT`` (no arc
interval was applied to any hit: ``BattleHitBuffProjection.applied_interval_ids``), ``FLAG_MISSING`` (rotation actions without animation data);
``FLAG_AXIS`` (cycle length differs between arcs -> compare by DPS) is derived by ``build_table``.

Graduation template level (decision U1, 2026-10-14): one account checkbox shows the table with the template's Puka
Boot Camp (噗卡特训) at Lv 0 (default, the rows above) or at max level (``TEMPLATE_LEVELS``).  The level is part of the
identity (``Identity.template_level``): L1 keeps the level-0 rows in ``ROWS`` exactly as before and the others in
``ROWS_BY_TEMPLATE[level]``; L2 keys of a level > 0 carry a "|puka<level>" suffix.  A level > 0 run uses an empty
account whose only setting is that training level.

Dev switch: ``NTE_ARC_EFF_FORCE_STALE=1`` ignores L1 and L2 (forces the background recomputation).
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

FORMAT = 1
ALGO_VERSION = "arc-eff-1"      # raise by hand when §2 / §3 of the design (corrections, entry, target, % rule) change
ENTRY = "opener"
LOOP_CHOICES = (3, 1)           # default first (team simulation DEFAULT_LOOPS = 3)
DEFAULT_LOOPS = 3
BASES = ("exclusive_r1", "same_refine")
FORCE_STALE_ENV = "NTE_ARC_EFF_FORCE_STALE"
CACHE_FILE = "arc_efficiency_cache.json"
PREFERENCES_FILE = "arc_efficiency_preferences.json"
QUALITY_ORDER = {"ORANGE": 0, "PURPLE": 1, "BLUE": 2}
TEMPLATE_LEVELS = (0, 20)       # graduation template Puka Boot Camp level: off / max (puka_training_settings_service)

FLAG_UNRESOLVED = 0x01
FLAG_DEDUP = 0x02
FLAG_SUPPLEMENT = 0x04
FLAG_NO_HIT = 0x08
FLAG_MISSING = 0x10
FLAG_AXIS = 0x20                # derived (build_table), never stored

SEED_MODULE = "src.services.arc_efficiency_data"
FP_ROOT_MODULE = "src.services.arc_efficiency_service"
# both efficiency tables' generated seeds and hand-kept notes (display only) never enter a fingerprint
FP_EXCLUDE = frozenset((SEED_MODULE, "src.services.arc_efficiency_notes", "src.services.awakening_efficiency_data",
                        "src.services.awakening_efficiency_notes"))
FP_EXCLUDE_PREFIXES = ("src.i18n_", "src.features.", "src.ui.")

_COMPUTE_LOCK = threading.Lock()          # one efficiency computation at a time (shared static connection)


# ── catalog ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ArcEntry:
    fork_id: str
    name_zh: str
    quality: str
    fork_type_id: int
    type_name_zh: str
    max_star: int
    owner_ids: tuple[int, ...]
    owner_names_zh: tuple[str, ...]
    own_exclusive: bool
    foreign_exclusive: bool
    review: str | None                     # fork_permanent_review.status
    star_pack_id: str = ""

    @property
    def refines(self) -> tuple[int, ...]:
        top = max(1, int(self.max_star or 1))
        return (1, top) if top > 1 else (1,)


@dataclass(frozen=True)
class CharacterEntry:
    character_id: int
    name_zh: str
    element: str
    role: str
    confidence: str
    exclusive_fork_id: str                 # the 100 % basis
    exclusive_ids: tuple[str, ...]         # every arc exclusive to this character (★)
    template_fork_id: str
    arcs: tuple[ArcEntry, ...]

    @property
    def forks_key(self) -> tuple[tuple[str, int], ...]:
        """What the data says this character can equip (compared with the precomputed seed)."""
        return tuple(sorted((a.fork_id, int(a.max_star)) for a in self.arcs))

    def arc(self, fork_id: str) -> ArcEntry | None:
        return next((a for a in self.arcs if a.fork_id == fork_id), None)


def _ro(static_path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(static_path).absolute().as_uri()}?mode=ro", uri=True)


def _approved(cid: int) -> bool:
    try:
        from src.services.team_rotation_data import CHARACTERS

        steps = ((CHARACTERS.get(int(cid)) or {}).get("variants") or {}).get("approved", {}).get("steps") or ()
        return bool(steps)
    except Exception:
        return False


def _rotation_info(cid: int) -> tuple[str, str]:
    try:
        from src.services.team_rotation_data import CHARACTERS

        info = CHARACTERS.get(int(cid)) or {}
        return str(info.get("role") or ""), str(info.get("confidence") or "")
    except Exception:
        return "", ""


def eligible_characters(static_path) -> list[CharacterEntry]:
    """Characters with an exclusive arc, a graduation template and an approved rotation, in character id order;
    their arcs: exclusive basis first, then quality (orange > purple > blue), then fork id."""
    con = _ro(static_path)
    try:
        has = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        review = dict(con.execute("SELECT fork_id, status FROM fork_permanent_review")) \
            if "fork_permanent_review" in has else {}
        types = dict(con.execute("SELECT fork_type_id, name_zh FROM fork_type")) if "fork_type" in has else {}
        names = {str(c): n for c, n in con.execute("SELECT character_id, name_zh FROM character")}
        forks = []
        for fid, name, quality, type_id, group, max_star, exclusive, star_pack in con.execute(
                "SELECT fork_id, name_zh, quality, fork_type_id, raw_group_type, max_star, "
                "exclusive_character_ids_json, star_pack_id FROM fork_item"):
            try:
                owners = tuple(dict.fromkeys(str(o) for o in (json.loads(exclusive or "[]") or ())))
            except (TypeError, ValueError):
                owners = ()
            forks.append((str(fid), name, str(quality or ""), int(type_id or 0), group, int(max_star or 1), owners,
                          str(star_pack or "")))
        rows = con.execute(
            "SELECT g.character_id, c.name_zh, c.group_type, g.fork_id FROM character_graduation_template g "
            "JOIN character c USING(character_id) ORDER BY g.character_id").fetchall()
        from src.services import team_cycle_reactions as tcr

        rules = tcr.load_rules(con)
    finally:
        con.close()
    out = []
    for cid, name, group, template_fork in rows:
        cid = int(cid)
        own = sorted(f[0] for f in forks if str(cid) in f[6])     # ids are JSON strings: never compare as int
        if not own or group in (None, "") or not _approved(cid):
            continue
        basis = template_fork if template_fork in own else own[0]
        arcs = []
        for fid, fname, quality, type_id, fgroup, max_star, owners, star_pack in forks:
            if fgroup != group:
                continue
            own_ex = str(cid) in owners
            arcs.append(ArcEntry(
                fork_id=fid, name_zh=fname, quality=quality, fork_type_id=type_id,
                type_name_zh=str(types.get(type_id) or ""), max_star=max_star,
                owner_ids=tuple(int(o) for o in owners if o.isdigit()),
                owner_names_zh=tuple(dict.fromkeys(names.get(o, o) for o in owners)),
                own_exclusive=own_ex, foreign_exclusive=bool(owners) and not own_ex,
                review=review.get(fid), star_pack_id=star_pack))
        arcs.sort(key=lambda a: (a.fork_id != basis, QUALITY_ORDER.get(a.quality, 9), a.fork_id))
        role, confidence = _rotation_info(cid)
        try:
            element = str(rules.element(cid) or "")
        except Exception:
            element = ""
        out.append(CharacterEntry(cid, str(name), element, role, confidence, basis, tuple(own), str(template_fork or ""),
                                  tuple(arcs)))
    return out


def job_order(entry: CharacterEntry) -> list[tuple[str, int]]:
    """(arc, refinement) in computing order: exclusive R1 (the basis), exclusive max, the others R1 (orange ->
    purple -> blue), the others max."""
    basis = entry.arc(entry.exclusive_fork_id)
    others = [a for a in entry.arcs if a.fork_id != entry.exclusive_fork_id]
    jobs: list[tuple[str, int]] = []
    if basis is not None:
        jobs.extend((basis.fork_id, r) for r in basis.refines)
    jobs.extend((a.fork_id, 1) for a in others)
    jobs.extend((a.fork_id, a.refines[-1]) for a in others if len(a.refines) > 1)
    return jobs


# ── one cell ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Row:
    damage: float
    flags: int
    end_us: int
    active_us: int


def row_key(cid: int, fork_id: str, refine: int, loops: int, entry: str = ENTRY) -> tuple:
    return (int(cid), str(fork_id), int(refine), int(loops), str(entry))


def _is_arc_interval(interval) -> bool:
    from src.services import team_fork_corrections as tfc

    source = str(getattr(interval, "source_effect_definition_id", "") or "")
    return (source.startswith(tfc.FORK_STAR) or source.startswith("global_supplement:")
            or getattr(interval, "source_kind", "") == tfc.SOURCE_KIND)


def applied_arc_intervals(analysis, character_id: int) -> set[str]:
    """Ids of the arc intervals applied to at least one of the character's hits (per-hit buff projection)."""
    from src.services.battle_buff_interval_index import BattleBuffIntervalIndex
    from src.services.battle_hit_buff_projection_cache import BattleHitBuffProjectionCache

    ids = {i.interval_id for i in (analysis.buff_intervals or ()) if _is_arc_interval(i)}
    used: set[str] = set()
    if not ids:
        return used
    cache = BattleHitBuffProjectionCache(BattleBuffIntervalIndex(analysis.buff_intervals))
    for hit in analysis.hits:
        if getattr(hit, "direction", "outgoing") != "outgoing" or int(hit.character_id or 0) != int(character_id):
            continue
        used |= ids.intersection(cache.project(hit).applied_interval_ids)
        if used == ids:
            break
    return used


def no_arc_hit(analysis, character_id: int) -> bool:
    """True when no arc interval was applied to any of the character's hits (per-hit buff projection)."""
    return not applied_arc_intervals(analysis, character_id)


def row_from_run(solo, permanent_properties: Iterable[str] = ()) -> Row:
    """Row of one ``team_simulation_service.SoloRun``."""
    from src.services import team_fork_corrections as tfc

    result = solo.result
    analysis = solo.run.analysis
    cid = int(solo.spec.character_id)
    flags = 0
    if tfc.unresolved_fork_buffs(analysis, permanent_properties):
        flags |= FLAG_UNRESOLVED
    report = solo.corrections
    if report is not None and report.of("b2"):
        flags |= FLAG_DEDUP
    used = applied_arc_intervals(analysis, cid)
    if report is not None and used & {c.interval_id for c in report.changes if c.code in ("b3", "b4")}:
        flags |= FLAG_SUPPLEMENT         # the badge only when a supplement window reached a hit
    if not used:
        flags |= FLAG_NO_HIT
    if any(m.missing_actions for m in result.members):
        flags |= FLAG_MISSING
    return Row(round(float(result.total_damage), 1), flags, int(solo.end_us),
               int(round(float(result.total_time_s) * 1_000_000)))


class Cancelled(Exception):
    pass


def compute_character(static_path, entry: CharacterEntry, loops: int, jobs: Iterable[tuple[str, int]] | None = None, *,
                      cancel: threading.Event | None = None, on_row: Callable[[tuple, Row], None] | None = None,
                      user_db_path=None, template_level: int = 0) -> dict[tuple, Row]:
    """Run the character alone for every (arc, refinement) of ``jobs`` (default: ``job_order``) on one shared
    session; ``on_row(key, row)`` after each run.  ``cancel`` is checked before every run (raises ``Cancelled``
    after keeping what is done in the returned mapping's ``on_row`` calls).  Uses an empty account; with
    ``template_level`` > 0 an empty account whose Puka Boot Camp level is that level (decision U1)."""
    from src.services import team_fork_corrections as tfc
    from src.services import team_simulation_service as svc

    jobs = list(job_order(entry) if jobs is None else jobs)
    out: dict[tuple, Row] = {}
    if not jobs:
        return out
    con = _ro(static_path)
    try:
        permanent = {(f, r): tuple(p for p, _v in tfc.load_permanent(con, f, r)) for f, r in jobs}
    finally:
        con.close()
    with _COMPUTE_LOCK:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        with contextlib.ExitStack() as stack:
            if int(template_level or 0) > 0 and user_db_path is None:
                from src.services.puka_training_settings_service import template_account_database

                folder = stack.enter_context(tempfile.TemporaryDirectory(prefix="nte_arc_eff_tpl_",
                                                                         ignore_cleanup_errors=True))
                user_db_path = template_account_database(folder, int(template_level))
            run = stack.enter_context(svc.solo_session(static_path, entry.character_id, loops=loops,
                                                       user_db_path=user_db_path, account_id="arc_efficiency"))
            for fork_id, refine in jobs:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                solo = run(svc.MemberSpec(entry.character_id, fork_id=fork_id, fork_refinement_level=int(refine)))
                key = row_key(entry.character_id, fork_id, refine, loops)
                row = row_from_run(solo, permanent.get((fork_id, refine), ()))
                out[key] = row
                if on_row is not None:
                    on_row(key, row)
    return out


# ── identity: data, engine, algorithm ─────────────────────────────────────────

_SHA_MEMO: dict[tuple, str] = {}


def manifest_dataset(static_path) -> dict:
    """``data/manifest.json`` ``database`` block (empty dict when missing or broken)."""
    try:
        data = json.loads((Path(static_path).parent / "manifest.json").read_text(encoding="utf-8"))
        block = data.get("database") or {}
        return block if isinstance(block, dict) else {}
    except Exception:
        return {}


def file_sha256(path) -> str:
    path = Path(path)
    st = path.stat()
    memo = (str(path.resolve()), st.st_size, st.st_mtime_ns)
    if memo not in _SHA_MEMO:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                h.update(chunk)
        _SHA_MEMO[memo] = h.hexdigest().upper()
    return _SHA_MEMO[memo]


def db_sha256(static_path) -> str:
    """The static DB's sha256: the manifest value when it names this file with this size, else the file hash."""
    path = Path(static_path)
    block = manifest_dataset(path)
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    sha = str(block.get("sha256") or "")
    if sha and block.get("filename") == path.name and int(block.get("size_bytes") or -1) == size:
        return sha.upper()
    return file_sha256(path)


_IMPORT_RE = re.compile(r"^[ \t]*(?:from[ \t]+(\.*[\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n#]+)|import[ \t]+([^\n#]+))",
                        re.MULTILINE)


def _module_index(src_root: Path) -> dict[str, Path]:
    """Every module file under ``<src_root>/src`` by dotted name (one directory walk)."""
    index: dict[str, Path] = {}
    base = Path(src_root)
    for folder, dirs, files in os.walk(base / "src"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = Path(folder).relative_to(base).parts
        for name in files:
            if not name.endswith(".py"):
                continue
            if name == "__init__.py":
                index[".".join(rel)] = Path(folder) / name
            else:
                index[".".join(rel + (name[:-3],))] = Path(folder) / name
    return index


def _excluded(name: str) -> bool:
    return name in FP_EXCLUDE or any(name.startswith(p) for p in FP_EXCLUDE_PREFIXES)


def source_closure(src_root: Path, root_module: str = FP_ROOT_MODULE) -> dict[str, Path]:
    """Static import closure of ``root_module`` inside ``src`` (imports inside functions included), without the
    seed, the notes, the language tables and the Qt layers.  ``src_root`` = the folder that contains ``src``."""
    index = _module_index(Path(src_root))
    found: dict[str, Path] = {}
    todo = [root_module]
    while todo:
        name = todo.pop()
        if name in found or _excluded(name):
            continue
        path = index.get(name)
        if path is None:
            continue
        found[name] = path
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        parent = package
        while "." in parent:                      # importing a.b.c runs a/__init__ and a/b/__init__
            parent = parent.rpartition(".")[0]
            todo.append(parent)
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _IMPORT_RE.finditer(text):
            source, names, plain = match.group(1), match.group(2), match.group(3)
            if plain is not None:
                for part in plain.split(","):
                    target = part.strip().split(" as ")[0].strip()
                    if target.startswith("src"):
                        todo.append(target)
                continue
            if source.startswith("."):
                level = len(source) - len(source.lstrip("."))
                base = package
                for _ in range(level - 1):
                    base = base.rpartition(".")[0]
                source = base + ("." + source.lstrip(".") if source.lstrip(".") else "")
            if not source.startswith("src"):
                continue
            todo.append(source)
            for item in names.strip("()").replace("\n", " ").split(","):
                item = item.strip().split(" as ")[0].strip()
                if item and item != "*" and f"{source}.{item}" in index:
                    todo.append(f"{source}.{item}")
    return found


def engine_fingerprint(src_root: Path | None = None, root_module: str = FP_ROOT_MODULE) -> str:
    """16 hex characters over the sources of the computation path (``source_closure`` of ``root_module``; the
    awakening efficiency table passes its own service module)."""
    if src_root is None:
        src_root = Path(__file__).resolve().parents[2]
    h = hashlib.sha256()
    for name, path in sorted(source_closure(Path(src_root), root_module).items()):
        h.update(name.encode("utf-8") + b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return h.hexdigest()[:16]


_FP_MEMO: list = []


def seed():
    """The generated L1 module, or None (not generated yet / broken)."""
    try:
        import importlib

        module = importlib.import_module(SEED_MODULE)
        if int(getattr(module, "FORMAT", 0)) != FORMAT:
            return None
        return module
    except Exception:
        return None


def current_engine_fp() -> str:
    """Source runs: the closure hash (once per process).  A frozen executable cannot hash its sources: it trusts
    the fingerprint of the seed it was built with (the build's ``gen --check`` guarantees it)."""
    if _FP_MEMO:
        return _FP_MEMO[0]
    value = ""
    here = Path(__file__)
    if not getattr(sys, "frozen", False) and here.suffix == ".py" and here.is_file():
        try:
            value = engine_fingerprint()
        except Exception:
            value = ""
    if not value:
        module = seed()
        value = str(getattr(module, "ENGINE_FP", "") or "") if module is not None else ""
    _FP_MEMO.append(value)
    return value


def corrections_state() -> str:
    """The enabled arc corrections (``team_fork_corrections.ENABLED``, dev switch ``NTE_TEAM_FORK_CORRECTIONS``)."""
    from src.services import team_fork_corrections as tfc

    return ",".join(sorted(tfc.ENABLED))


def full_corrections() -> str:
    from src.services import team_fork_corrections as tfc

    return ",".join(sorted(tfc.ALL))


@dataclass(frozen=True)
class Identity:
    algo: str
    db_sha256: str
    engine_fp: str
    dataset_id: str = ""
    corrections: str = field(default_factory=corrections_state)
    template_level: int = 0                 # decision U1: graduation template Puka Boot Camp level (0 / max)

    def family_prefix(self) -> str:
        """Algorithm, data, engine and corrections: every template level of one build."""
        return f"{self.algo}|{self.db_sha256}|{self.engine_fp}|{self.corrections}"

    def prefix(self) -> str:
        base = self.family_prefix()
        return f"{base}|puka{int(self.template_level)}" if int(self.template_level or 0) > 0 else base


def current_identity(static_path, template_level: int = 0) -> Identity:
    return Identity(ALGO_VERSION, db_sha256(static_path), current_engine_fp(),
                    str(manifest_dataset(static_path).get("dataset_id") or ""),
                    template_level=int(template_level or 0))


def seed_rows(module, template_level: int = 0) -> dict:
    """The seed's rows of one template level (``ROWS`` at level 0, ``ROWS_BY_TEMPLATE[level]`` above)."""
    if module is None:
        return {}
    if not int(template_level or 0):
        return getattr(module, "ROWS", {}) or {}
    return (getattr(module, "ROWS_BY_TEMPLATE", {}) or {}).get(int(template_level), {}) or {}


def _force_stale() -> bool:
    return str(os.environ.get(FORCE_STALE_ENV, "")).strip() not in ("", "0", "false", "no", "off")


# ── L2 cache ──────────────────────────────────────────────────────────────────

def resource_model_state() -> str:
    """The team simulator's resource level the rows are computed at (``team_resources.DEFAULT_RESOURCE_MODEL``; the
    dev switch ``NTE_TEAM_RESOURCE_MODEL``).  Review F8: rows of another level never meet the shipped level's L1 / L2."""
    from src.services import team_resources

    return str(team_resources.DEFAULT_RESOURCE_MODEL)


def resource_suffix() -> str:
    """"" at the shipped level (its keys are unchanged), "|res-<level>" for a regression run at another level."""
    from src.services import team_resources

    model = resource_model_state()
    return "" if model == team_resources.SHIPPED_RESOURCE_MODEL else f"|res-{model}"


def state_suffix() -> str:
    """"" at the shipped switch state (every awakening node-rule group on, the Global live overlay at its default
    groups: the seeds' state, keys unchanged); "|rules-<groups>|overlay-<groups>" otherwise (dev / test switches
    ``NTE_TEAM_AWAKENING_RULES`` / ``NTE_GLOBAL_OVERLAY``): rows of another state never meet the seed or its keys."""
    parts = []
    try:
        from src.services.awakening_node_rules import core

        if core.ENABLED_GROUPS is not None:
            parts.append("|rules-" + (",".join(sorted(core.ENABLED_GROUPS)) or "off"))
    except Exception:
        pass
    try:
        from src.services import global_live_overlay as glo

        if glo.ENABLED_GROUPS is not None:
            defaults = {g for g, spec in glo.D.GROUPS.items() if spec.get("default")}
            on = set(glo.groups_on())
            if on != defaults:
                parts.append("|overlay-" + (",".join(sorted(on)) or "off"))
    except Exception:
        pass
    return "".join(parts)


def dataset_suffix(identity) -> str:
    """"|ds-<manifest dataset id>" of an identity ("" without one).  Review L-F1: the Global live overlay switches on the
    dataset id AND the DB sha256, so the same DB bytes under another dataset id give other rows (L2 keys differ)."""
    dataset = str(getattr(identity, "dataset_id", "") or "")
    return f"|ds-{dataset}" if dataset else ""


def cache_key_text(identity: Identity, key: tuple) -> str:
    cid, fork_id, refine, loops, entry = key
    return (f"{identity.prefix()}{dataset_suffix(identity)}{resource_suffix()}{state_suffix()}"
            f"|{cid}|{fork_id}|{refine}|{loops}|{entry}")


class Cache:
    """``<config>/arc_efficiency_cache.json``: {"format": 1, "entries": {key: [damage, flags, end_us, active_us,
    computed_at]}}.  Thread-safe.  A broken / unreadable file is ignored (memory only, one log line); saving replaces
    the file atomically and drops entries of other identities."""

    def __init__(self, path: Path | None) -> None:
        self.path = Path(path) if path is not None else None
        self._lock = threading.RLock()
        self._entries: dict[str, list] = {}
        self._loaded = False
        self.error: str = ""

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self.path is None or not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = data.get("entries") if isinstance(data, dict) and data.get("format") == FORMAT else None
            if isinstance(entries, dict):
                self._entries = {str(k): list(v) for k, v in entries.items()
                                 if isinstance(v, list) and len(v) >= 4}
        except Exception as exc:  # noqa: BLE001 - a damaged cache is never fatal
            self.error = f"{type(exc).__name__}: {exc}"
            _log(f"arc efficiency cache ignored: {self.error}")

    def key_text(self, identity: Identity, key: tuple) -> str:
        """The entry key of a row key (the awakening efficiency cache overrides it for its own key shape)."""
        return cache_key_text(identity, key)

    def get(self, identity: Identity, key: tuple) -> Row | None:
        with self._lock:
            self._load()
            value = self._entries.get(self.key_text(identity, key))
            if value is None:
                return None
            try:
                return Row(float(value[0]), int(value[1]), int(value[2]), int(value[3]))
            except (TypeError, ValueError, IndexError):
                return None

    def put(self, identity: Identity, key: tuple, row: Row) -> None:
        with self._lock:
            self._load()
            self._entries[self.key_text(identity, key)] = [row.damage, row.flags, row.end_us, row.active_us,
                                                           time.strftime("%Y-%m-%d %H:%M")]

    def computed_at(self, identity: Identity, key: tuple) -> str:
        with self._lock:
            self._load()
            value = self._entries.get(self.key_text(identity, key))
            return str(value[4]) if value is not None and len(value) > 4 else ""

    def save(self, identity: Identity) -> bool:
        if self.path is None:
            return False
        with self._lock:
            self._load()
            # every template level of the same build stays (U1: switching the checkbox must not drop the other)
            prefix = identity.family_prefix() + "|"
            self._entries = {k: v for k, v in self._entries.items() if k.startswith(prefix)}
            payload = json.dumps({"format": FORMAT, "entries": dict(sorted(self._entries.items()))},
                                 ensure_ascii=False, separators=(",", ":"))
            tmp = self.path.with_name(self.path.name + ".tmp")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, self.path)
                return True
            except Exception as exc:  # noqa: BLE001
                self.error = f"{type(exc).__name__}: {exc}"
                _log(f"arc efficiency cache not saved: {self.error}")
                return False


def _log(message: str) -> None:
    try:
        from src.utils.logger import logger

        logger.warning(message)
    except Exception:
        pass


# ── which layer serves a character ────────────────────────────────────────────

SOURCE_SEED = "seed"
SOURCE_CACHE = "cache"
SOURCE_STALE = "stale"


@dataclass
class Resolution:
    identity: Identity
    sources: dict[int, str]                     # cid -> seed | cache | stale
    rows: dict[tuple, Row]                      # every row known now (seed / cache)
    computed_at: dict[int, str] = field(default_factory=dict)


def seed_matches(module, identity: Identity) -> bool:
    if module is None:
        return False
    from src.services import team_resources

    dataset = getattr(module, "DATASET", {}) or {}
    # the seed's resource level (a seed without the line predates review F8: the shipped level) - review F8
    if str(getattr(module, "RESOURCE_MODEL", team_resources.SHIPPED_RESOURCE_MODEL)) != resource_model_state():
        return False
    if state_suffix():              # node rules / live overlay switched away from the shipped state
        return False
    return (str(getattr(module, "ALGO_VERSION", "")) == identity.algo
            and str(dataset.get("sha256", "")).upper() == identity.db_sha256.upper()
            and str(dataset.get("dataset_id", "")) == str(identity.dataset_id)    # review L-F1 (overlay key)
            and str(getattr(module, "ENGINE_FP", "")) == identity.engine_fp and bool(identity.engine_fp)
            and identity.corrections == full_corrections())       # L1 is computed with B1-B4 on


def resolve(static_path, entries: Iterable[CharacterEntry], loops: int, cache: Cache | None,
            identity: Identity | None = None, module=...) -> Resolution:
    """For every character: L1 when the seed's key and arc set match, else L2 when it holds every row, else stale."""
    identity = identity or current_identity(static_path)
    module = seed() if module is ... else module
    force = _force_stale()
    ok_seed = (not force) and seed_matches(module, identity)
    seed_chars = getattr(module, "CHARACTERS", {}) if ok_seed else {}
    table = seed_rows(module, identity.template_level) if ok_seed else {}
    sources: dict[int, str] = {}
    rows: dict[tuple, Row] = {}
    stamps: dict[int, str] = {}
    for entry in entries:
        cid = entry.character_id
        keys = [row_key(cid, f, r, loops) for f, r in job_order(entry)]
        info = seed_chars.get(cid) or {}
        if ok_seed and tuple(sorted(tuple(x) for x in info.get("forks", ()))) == entry.forks_key \
                and all(k in table for k in keys):
            for k in keys:
                rows[k] = Row(*table[k])
            sources[cid] = SOURCE_SEED
            continue
        got = {k: cache.get(identity, k) for k in keys} if (cache is not None and not force) else {}
        if got and all(v is not None for v in got.values()):
            rows.update(got)
            sources[cid] = SOURCE_CACHE
            stamps[cid] = max((cache.computed_at(identity, k) for k in keys), default="")
        else:
            sources[cid] = SOURCE_STALE
            if not force:
                rows.update({k: v for k, v in got.items() if v is not None})    # finished rows show at once
    return Resolution(identity, sources, rows, stamps)


# ── background recomputation ──────────────────────────────────────────────────

class _Gate:
    """Cancel token for ``compute_character``: the user's cancel, or a switch to another character."""

    def __init__(self, *events: threading.Event) -> None:
        self._events = events

    def is_set(self) -> bool:
        return any(e.is_set() for e in self._events)


class Computation:
    """Recompute stale characters in a worker thread (``run``), the viewed one first.

    ``pending`` = {cid: [(arc, refinement), ...]} in job order.  ``prioritize(cid)`` moves a character to the front
    after the current run; ``cancel()`` stops before the next run (the delay is one run).  Every finished row goes to
    the cache (memory) and to ``on_row``; the cache file is saved when a character finishes and when the computation
    stops.  A character whose exclusive refinement-1 damage is 0 (or which fails) is not cached: ``on_character``
    reports it as failed."""

    def __init__(self, static_path, entries: Mapping[int, CharacterEntry], loops: int,
                 pending: Mapping[int, list], cache: Cache | None, identity: Identity, *,
                 on_row: Callable[[tuple, Row], None] | None = None,
                 on_character: Callable[[int, bool, str], None] | None = None,
                 order: Iterable[int] | None = None, generation: int = 0, user_db_path=None) -> None:
        self.static_path = static_path
        self.entries = dict(entries)
        self.loops = int(loops)
        self.pending = {int(c): list(j) for c, j in pending.items() if j}
        self.cache = cache
        self.identity = identity
        self.on_row = on_row
        self.on_character = on_character
        self.order = [int(c) for c in (order if order is not None else self.pending)]
        self.generation = generation
        self.user_db_path = user_db_path
        self._cancel = threading.Event()
        self._priority: int | None = None
        self.done_rows: dict[tuple, Row] = {}
        self.runs = 0

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def prioritize(self, cid: int | None) -> None:
        self._priority = None if cid is None else int(cid)

    def _next(self) -> int | None:
        if self._priority is not None and self.pending.get(self._priority):
            return self._priority
        for cid in self.order:
            if self.pending.get(cid):
                return cid
        return next((c for c, j in self.pending.items() if j), None)

    def _finish(self, cid: int) -> None:
        entry = self.entries[cid]
        basis = row_key(cid, entry.exclusive_fork_id, 1, self.loops)
        rows = {k: v for k, v in self.done_rows.items() if k[0] == cid and k[3] == self.loops}
        ok = basis in rows and rows[basis].damage > 0
        if ok and self.cache is not None:
            for key, row in rows.items():
                self.cache.put(self.identity, key, row)
            self.cache.save(self.identity)
        if self.on_character is not None:
            self.on_character(cid, ok, "" if ok else "basis")

    def run(self) -> dict[tuple, Row]:
        """Process until nothing is pending or cancelled; returns every finished row."""
        while not self._cancel.is_set():
            cid = self._next()
            if cid is None:
                break
            switch = threading.Event()
            gate = _Gate(self._cancel, switch)

            def watch(key, row, session_cid=cid):
                self.done_rows[key] = row
                self.runs += 1
                job = (key[1], key[2])
                if job in self.pending.get(session_cid, []):
                    self.pending[session_cid].remove(job)
                if self.on_row is not None:
                    self.on_row(key, row)
                wanted = self._priority
                if wanted is not None and wanted != session_cid and self.pending.get(wanted):
                    switch.set()          # the viewed character goes first: stop this session after this run

            try:
                compute_character(self.static_path, self.entries[cid], self.loops, list(self.pending[cid]),
                                  cancel=gate, on_row=watch, user_db_path=self.user_db_path,
                                  template_level=self.identity.template_level)
            except Cancelled:
                pass
            except Exception as exc:  # noqa: BLE001 - one character failing never stops the others
                self.pending[cid] = []
                _log(f"arc efficiency: {cid} failed: {type(exc).__name__}: {exc}")
                if self.on_character is not None:
                    self.on_character(cid, False, f"{type(exc).__name__}: {exc}")
                continue
            if not self.pending.get(cid):
                self._finish(cid)
        if self.cache is not None and self.done_rows:
            # finished rows of an interrupted character stay available (cached once its basis row is in)
            for cid in {k[0] for k in self.done_rows}:
                entry = self.entries[cid]
                basis = row_key(cid, entry.exclusive_fork_id, 1, self.loops)
                if self.done_rows.get(basis) is not None and self.done_rows[basis].damage > 0:
                    for key, row in self.done_rows.items():
                        if key[0] == cid:
                            self.cache.put(self.identity, key, row)
            self.cache.save(self.identity)
        return self.done_rows


# ── the table ─────────────────────────────────────────────────────────────────

@dataclass
class TableRow:
    arc: ArcEntry
    marker: str                       # "★" own exclusive, "†" other character's exclusive, ""
    damage_r1: float | None
    damage_max: float | None
    max_star: int
    pct_r1: float | None
    pct_max: float | None
    pct_max_same: float | None        # max refinement vs the exclusive arc at its max refinement
    gain: float | None                # D(max) / D(1)
    flags: int                        # both refinements' flags OR-ed, ○ only when both have it (+ FLAG_AXIS)
    flat: bool                        # =R: refinement does not change the solo number
    above: bool                       # ▲: refinement 1 above the exclusive arc
    rank: int = 0
    tied: bool = False
    pending: bool = False


@dataclass
class Table:
    entry: CharacterEntry
    loops: int
    basis: str
    rows: list[TableRow]
    basis_damage: float | None
    basis_damage_max: float | None
    end_us: int | None
    active_s: float | None
    dps_mode: bool                    # cycle lengths differ: % from DPS
    failed: bool                      # the basis is 0: "cannot calculate"
    complete: bool

    def best_alternative(self) -> TableRow | None:
        rows = [r for r in self.rows if r.marker != "★" and r.pct_r1 is not None]
        return max(rows, key=lambda r: (r.pct_r1, r.pct_max or 0.0), default=None)


def build_table(entry: CharacterEntry, rows: Mapping[tuple, Row], loops: int, basis: str = "exclusive_r1",
                include_foreign: bool = True) -> Table:
    """Percentages, rank, marks.  ``basis`` = "exclusive_r1" (E: every cell against the exclusive arc at R1) or
    "same_refine" (E': the max-refinement column against the exclusive arc at its max refinement)."""
    cid = entry.character_id
    ex = entry.arc(entry.exclusive_fork_id)
    ex_max = ex.refines[-1] if ex is not None else 1
    b1 = rows.get(row_key(cid, entry.exclusive_fork_id, 1, loops))
    bm = rows.get(row_key(cid, entry.exclusive_fork_id, ex_max, loops))
    known = [rows[k] for k in (row_key(cid, f, r, loops) for f, r in job_order(entry)) if k in rows]
    ends = {r.end_us for r in known}
    dps_mode = len(ends) > 1
    failed = b1 is not None and b1.damage <= 0

    def value(row: Row | None) -> float | None:
        if row is None:
            return None
        if dps_mode:
            return row.damage / (row.active_us / 1e6) if row.active_us > 0 else None
        return row.damage

    v1 = value(b1) if not failed else None
    vm = value(bm) if not failed else None
    out: list[TableRow] = []
    for arc in entry.arcs:
        if arc.foreign_exclusive and not include_foreign:
            continue
        top = arc.refines[-1]
        r1 = rows.get(row_key(cid, arc.fork_id, 1, loops))
        rm = rows.get(row_key(cid, arc.fork_id, top, loops))
        a1, am = value(r1), value(rm)
        pct1 = 100.0 * a1 / v1 if (a1 is not None and v1) else None
        pctm = 100.0 * am / v1 if (am is not None and v1) else None
        pcts = 100.0 * am / vm if (am is not None and vm) else None
        f1, fm = (r1.flags if r1 else 0), (rm.flags if rm else 0)
        # ○ only when neither refinement applied an arc buff; the other flags when either row has them
        flags = ((f1 | fm) & ~FLAG_NO_HIT) | (f1 & fm & FLAG_NO_HIT) | (FLAG_AXIS if dps_mode else 0)
        marker = "★" if arc.fork_id in entry.exclusive_ids else ("†" if arc.foreign_exclusive else "")
        out.append(TableRow(
            arc=arc, marker=marker, damage_r1=r1.damage if r1 else None, damage_max=rm.damage if rm else None,
            max_star=top, pct_r1=pct1, pct_max=pctm, pct_max_same=pcts,
            gain=(rm.damage / r1.damage) if (r1 and rm and r1.damage > 0) else None, flags=flags,
            flat=bool(r1 and rm and top > 1 and abs(rm.damage - r1.damage) < 1e-6),
            above=bool(marker != "★" and pct1 is not None and pct1 > 100.0 + 1e-9),
            pending=(r1 is None or rm is None)))

    def sort_value(r: TableRow):
        second = r.pct_max_same if basis == "same_refine" else r.pct_max
        return (-(r.pct_r1 if r.pct_r1 is not None else -1.0), -(second if second is not None else -1.0),
                QUALITY_ORDER.get(r.arc.quality, 9), r.arc.name_zh, r.arc.fork_id)

    out.sort(key=sort_value)
    rank, previous = 0, None
    for r in out:
        current = (r.damage_r1, r.damage_max)
        if r.pct_r1 is None:
            r.rank = 0
            continue
        if current != previous:
            rank += 1
        else:
            r.tied = True
            for other in out:
                if other is not r and (other.damage_r1, other.damage_max) == current:
                    other.tied = True
        r.rank = rank
        previous = current
    end = b1.end_us if b1 is not None else None
    active = (b1.active_us / 1e6) if b1 is not None else None
    return Table(entry, loops, basis, out, b1.damage if b1 else None, bm.damage if bm else None, end, active,
                 dps_mode, failed, all(not r.pending for r in out))


# ── preferences (account independent) ────────────────────────────────────────

DEFAULT_PREFERENCES = {"loops": DEFAULT_LOOPS, "basis": "exclusive_r1", "show_foreign": True, "show_damage": False,
                       "character": None}


def load_preferences(path: Path | None) -> dict:
    prefs = dict(DEFAULT_PREFERENCES)
    if path is None:
        return prefs
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if data.get("loops") in LOOP_CHOICES:
                prefs["loops"] = int(data["loops"])
            if data.get("basis") in BASES:
                prefs["basis"] = data["basis"]
            for key in ("show_foreign", "show_damage"):
                if isinstance(data.get(key), bool):
                    prefs[key] = data[key]
            if isinstance(data.get("character"), int):
                prefs["character"] = data["character"]
    except Exception:
        pass
    return prefs


def save_preferences(path: Path | None, prefs: Mapping[str, Any]) -> None:
    if path is None:
        return
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({k: prefs.get(k) for k in DEFAULT_PREFERENCES}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001
        _log(f"arc efficiency preferences not saved: {type(exc).__name__}: {exc}")


# ── text helpers shared by the page and the tests ─────────────────────────────

def load_star_texts(static_path, fork_ids: Iterable[str]) -> dict[tuple[str, int], tuple[str, tuple]]:
    """(fork_id, refinement) -> (Chinese description template, ((ordinal, is_percent, value), ...)) for every
    refinement of the given arcs (one read-only connection)."""
    wanted = sorted(set(fork_ids))
    out: dict[tuple[str, int], tuple[str, tuple]] = {}
    if not wanted:
        return out
    con = _ro(static_path)
    try:
        marks = ",".join("?" * len(wanted))
        packs = {}
        for fork_id, star_pack in con.execute(
                f"SELECT fork_id, star_pack_id FROM fork_item WHERE fork_id IN ({marks})", wanted):
            packs[str(star_pack)] = str(fork_id)
        params: dict[tuple[str, int], list] = {}
        for pack, level, ordinal, percent, value in con.execute(
                "SELECT p.star_pack_id, p.star_level, p.ordinal, p.is_percent, v.value FROM fork_star_parameter p "
                "LEFT JOIN fork_refinement_parameter_value v ON v.name_id = p.name_id "
                "AND v.refinement_level = p.star_level"):
            if pack in packs:
                params.setdefault((packs[pack], int(level)), []).append((int(ordinal), bool(percent), value))
        from src.services import global_live_overlay       # release texts on the overlay's DB (「月的对跖点」)

        for pack, level, description in con.execute("SELECT star_pack_id, star_level, description_zh FROM fork_star_level"):
            if pack in packs:
                key = (packs[pack], int(level))
                text = global_live_overlay.patch_star_text(packs[pack], int(level), str(description or ""),
                                                           static_path, con)
                out[key] = (text, tuple(sorted(params.get(key, ()))))
    finally:
        con.close()
    return out


def render_star_text(template_zh: str, params: Iterable[tuple]) -> str:
    """The effect text in the ACTIVE language: the template goes through the display layer (descriptions are keyed
    by their template), then the placeholders are filled and the markup removed."""
    source = str(template_zh or "")
    tr = None
    try:
        from src.i18n_display import tr
    except Exception:
        pass
    template = str(tr(source)) if tr is not None else source
    for ordinal, percent, value in params:
        if value is None:
            continue
        number = float(value) * (100.0 if percent else 1.0)
        shown = f"{number:.6f}".rstrip("0").rstrip(".") + ("%" if percent else "")
        template = template.replace("{" + str(int(ordinal)) + "}", shown)
    text = template.replace("<lv>", "").replace("</>", "").replace("\r\n", "\n").strip()
    if tr is not None and template == source:
        text = str(tr(text))        # no description entry for this language: the term table, once
    return text
