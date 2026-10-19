# 噗卡特训第二阶段：原生核心重算面板时，把它无法重建的五项特训加成经「边际手工调整」通道补回。
"""Puka Boot Camp (噗卡特训) Tier 2: the training stats the native core cannot rebuild by itself.

When ``nte-analysis-core.exe`` rebuilds a battle report's panel from a profile (an active modified copy, the
comparison candidate of the marginal page, "compare with my build"), it restores the account layers it knows:
the frozen ``world_bonus`` rows carry the training's ATK / CRIT DMG share, but DEF / HP / CRIT Rate / Cycle
Intensity / Break Intensity are dropped (probe W2/W1-cand: an unchanged candidate read -2.37 %).  The only channel
for them is the profile's ``battle_stat_overrides`` (absolute values of resolved properties).  This module computes
those values with the Python mirror of the reconstruction (frozen build + the profile, the frozen training level)
and passes exactly ``TRAINING_ONLY_IDS``:

* ``prepare_native_request`` - the native page loader's single entry: (1) keeps the saved modified copy of the
  record in step with the account switch (``PukaTrainingOptions.native_overrides``), (2) adds the values to the
  request's ``marginal_candidate`` (the comparison candidate) when the switch is on.
* The marginal *benefit* candidate (Console main-stat options, arc split) never receives them: the native core
  applies overrides as absolute values to every variant it derives from that candidate, so CRIT Rate / Cycle /
  Break / HP / DEF main-stat options and the arc's permanent stats would read 0 (probe T2_both: arc +46 % instead
  of +99 %).  Without them the benefit numbers are the same as the marginal page's entry view (probe T2_split ==
  T2_entry_plain).
* A record without a frozen level (Lv 0, pre-feature records) is never touched: requests stay byte-identical.

The native core shows the values as "边际手工调整" (manual marginal adjustment) source rows and may report the
candidate's quantification as "partial"; the UI says so (decision U2, 2026-10-14).
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.services.puka_training_settings_service import (
    frozen_puka_training_level,
    load_account_puka_options,
)
from src.utils.logger import logger


# AtkAdd / CritDamageBase / PanelAtk travel with the frozen world_bonus rows (W2): never here (no double count).
TRAINING_ONLY_IDS = ("DefAdd", "HPMaxAdd", "CritBase", "MagBase", "UnbalIntensityBase", "PanelHP", "PanelDef")
_ROUND = 9
_MEMO_SIZE = 64
_MEMO: "OrderedDict[str, dict[int, dict[str, float]]]" = OrderedDict()
_MEMO_LOCK = threading.Lock()


def strip_training_overrides(overrides: Mapping[str, Any] | None) -> dict[str, float]:
    """The overrides without the keys this channel owns."""

    return {
        str(key): value
        for key, value in dict(overrides or {}).items()
        if str(key) not in TRAINING_ONLY_IDS
    }


def _clean_value(value: float) -> float:
    return round(float(value), _ROUND)


def _memo_key(*parts: Any) -> str:
    text = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mirror_training_values(
    frozen_build: Mapping[str, Any],
    edit_characters: Sequence[Mapping[str, Any]],
    dependencies,
) -> dict[int, dict[str, float]]:
    """Resolved values of ``TRAINING_ONLY_IDS`` for each edited character, from the Python mirror of the native
    reconstruction (frozen build + edit, frozen training level, training-owned overrides removed first)."""

    from src.services.battle_build_edit_projection_service import apply_battle_build_edit
    from src.services.battle_build_stat_reconstruction_service import BattleBuildStatReconstructionService

    characters = []
    for row in edit_characters:
        character = deepcopy(dict(row))
        profile = dict(character.get("profile") or {})
        profile["battle_stat_overrides"] = strip_training_overrides(profile.get("battle_stat_overrides"))
        character["profile"] = profile
        characters.append(character)
    # the frozen build is immutable, but key on all of it (and on the account / static data) to stay exact
    key = _memo_key(
        "mirror", str(getattr(dependencies, "static_database_path", "")),
        str(getattr(dependencies, "user_database_path", "")), dict(frozen_build), characters,
    )
    with _MEMO_LOCK:
        cached = _MEMO.get(key)
        if cached is not None:
            _MEMO.move_to_end(key)
            return deepcopy(cached)
    shadow = deepcopy(dict(frozen_build))
    apply_battle_build_edit(shadow, {"is_active": True, "characters": characters})
    BattleBuildStatReconstructionService.enrich(shadow, dependencies, detail_cache={})
    edited_ids = {int(c["character_id"]) for c in characters}
    values: dict[int, dict[str, float]] = {}
    for character in shadow.get("characters") or ():
        character_id = int(character["character_id"])
        if character_id not in edited_ids or character.get("stat_snapshot_source") == "missing":
            continue        # not rebuilt (the reconstruction gave up): send nothing rather than a guess
        resolved = {
            str(row.get("property_id") or ""): float(row.get("value") or 0.0)
            for row in character.get("stats") or ()
            if str(row.get("source_group") or "") == "resolved"
        }
        values[character_id] = {
            property_id: _clean_value(resolved[property_id])
            for property_id in TRAINING_ONLY_IDS
            if property_id in resolved and math.isfinite(resolved[property_id])
        }
    with _MEMO_LOCK:
        _MEMO[key] = deepcopy(values)
        while len(_MEMO) > _MEMO_SIZE:
            _MEMO.popitem(last=False)
    return values


def with_training_overrides(profile: Mapping[str, Any], values: Mapping[str, float] | None) -> dict[str, Any]:
    """The profile with the channel's keys replaced by ``values`` (``None`` / empty: removed)."""

    updated = dict(profile)
    overrides = strip_training_overrides(profile.get("battle_stat_overrides"))
    overrides.update({key: _clean_value(value) for key, value in (values or {}).items()})
    updated["battle_stat_overrides"] = overrides
    return updated


def inject_candidate(candidate, frozen_build: Mapping[str, Any], dependencies):
    """The comparison candidate with the training values of every profile (Python mirror of that candidate:
    its equipment, cultivation and Console main-stat counterfactual included).  Profiles the mirror could not
    rebuild are left as they are."""

    from src.services.battle_marginal_candidate_service import BattleMarginalCandidateService

    plain = replace(candidate, profiles=tuple(
        {**dict(p), "battle_stat_overrides": strip_training_overrides(p.get("battle_stat_overrides"))}
        for p in candidate.profiles
    ))
    edit = BattleMarginalCandidateService.as_build_edit(plain, frozen_build=frozen_build)
    values = mirror_training_values(frozen_build, edit["characters"], dependencies)
    profiles = []
    for profile in candidate.profiles:
        character_id = int(profile.get("character_id") or 0)
        if character_id in values:
            profiles.append(with_training_overrides(profile, values[character_id]))
        else:
            profiles.append(dict(profile))
    return replace(candidate, profiles=tuple(profiles))


def _same(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    if set(a) != set(b):
        return False
    return all(abs(float(a[k]) - float(b[k])) <= 1e-9 for k in a)


def sync_saved_build_edit(
    battle_record_id: int,
    frozen_build: Mapping[str, Any],
    dependencies,
    *,
    enabled: bool,
) -> int:
    """Make the record's saved modified copy carry (``enabled``) or not carry the channel's values.  Only
    ``battle_stat_overrides`` inside the saved profiles change (the copy's other fields, active flag and timestamps
    stay).  Read-only (legacy) records are never written.  Returns the number of profiles changed."""

    from src.storage.sqlite.user_data_dao import UserDataDao

    with UserDataDao(Path(dependencies.user_database_path)) as dao:
        edit = dao.load_battle_build_edit(int(battle_record_id))
        if edit is None or not dao.battle_report_counterfactual_editable(int(battle_record_id)):
            return 0
    characters = list(edit.get("characters") or ())
    current = {
        int(c["character_id"]): dict((c.get("profile") or {}).get("battle_stat_overrides") or {})
        for c in characters
    }
    values = mirror_training_values(frozen_build, characters, dependencies) if enabled else {}
    desired: dict[int, dict[str, float]] = {}
    for character_id, overrides in current.items():
        wanted = strip_training_overrides(overrides)
        if enabled:
            if character_id not in values:
                continue          # the mirror could not rebuild this character: leave the saved copy alone
            wanted.update(values[character_id])
        if not _same(overrides, wanted):
            desired[character_id] = wanted
    if not desired:
        return 0
    with UserDataDao(Path(dependencies.user_database_path)) as dao:
        return int(dao.replace_battle_build_edit_stat_overrides(int(battle_record_id), desired))


def prepare_native_request(request, dependencies):
    """The native page loader's hook (see the module docstring).  Never raises: a failure is logged and the
    request goes out unchanged (the phase 1 behaviour: ATK / CRIT DMG share only)."""

    try:
        from src.storage.sqlite.user_data_dao import UserDataDao

        user_path = getattr(dependencies, "user_database_path", None)
        if user_path is None or getattr(dependencies, "static_database_path", None) is None:
            return request
        record_id = int(request.battle_record_id)
        with UserDataDao(Path(user_path)) as dao:
            build = dao.load_battle_build_snapshot(record_id)
        if build is None or frozen_puka_training_level(build.get("puka_training")) <= 0:
            return request
        enabled = load_account_puka_options(user_path).native_overrides
        sync_saved_build_edit(record_id, build, dependencies, enabled=enabled)
        candidate = getattr(request, "marginal_candidate", None)
        if enabled and candidate is not None and int(candidate.battle_record_id) == record_id:
            request = replace(request, marginal_candidate=inject_candidate(candidate, build, dependencies))
        return request
    except Exception as exc:  # noqa: BLE001 - Tier 2 is a correction, never a reason to fail the page
        logger.warning("puka training native overrides skipped for record {}: {}: {}",
                       getattr(request, "battle_record_id", None), type(exc).__name__, exc)
        return request


__all__ = [
    "TRAINING_ONLY_IDS",
    "inject_candidate",
    "mirror_training_values",
    "prepare_native_request",
    "strip_training_overrides",
    "sync_saved_build_edit",
    "with_training_overrides",
]
