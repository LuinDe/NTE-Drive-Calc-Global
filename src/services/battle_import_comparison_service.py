# 将导入战报中与当前账号相同的角色替换为本账号的养成与当前空幕/驱动，在同一固定轴上只读对比。
"""Compare an imported battle report with the current account's own characters.

For every character that appears in BOTH the imported report and the current account (same
character id only), the character's whole build - level, awakening, skills, fork + refinement and
the currently equipped cores/drives - is replaced with the account's own, and the report's recorded
fixed axis is re-evaluated once by the native core.  Characters the account does not own keep the
original player's build (including the locked imported equipment).

Nothing is written: the candidate lives in memory only, it is never saved as a build edit and never
handed to the marginal session.  The upstream import lock stays intact - the original side is the
native baseline (which applies the lock), and only this in-memory candidate carries
equipment_editable=True.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.services.advancement_stage_service import select_fork_breakthrough
from src.services.battle_build_equipment_service import freeze_equipment_context
from src.services.battle_marginal_candidate_service import (
    BattleMarginalCandidate,
    BattleMarginalCandidateService,
)
from src.services.battle_report_analysis_load_service import (
    BattleReportAnalysisLoadRequest,
    BattleReportAnalysisLoadService,
)
from src.services.official_role_page_service import load_official_role_detail

_ROLE_PAGE_ONLY = ("persisted", "field_sources", "is_active", "created_at_utc", "updated_at_utc", "profile_source")
_CULTIVATION = ("character_level", "breakthrough_stage", "awakening_level", "selected_awaken_effect_ids",
                "likeability_level_10_enabled", "fork_id", "fork_level", "fork_breakthrough_stage",
                "fork_refinement_level", "selected_skill_id", "skill_levels")
_SHAPE = ("extra_shape_label", "extra_shape_buffs", "extra_shape_source")


@dataclass(frozen=True)
class ImportComparisonMatch:
    character_id: int
    character_name: str
    replaced: bool
    reason: str                    # replaced | not_owned | no_current_equipment
    cultivation_source: str        # account | native_observed | template
    changed_fields: tuple[str, ...]
    equipment_changed: bool


@dataclass(frozen=True)
class ImportComparisonPlan:
    battle_record_id: int
    source_account_nickname: str
    matches: tuple[ImportComparisonMatch, ...]
    candidate: BattleMarginalCandidate
    scopes: tuple[str | None, ...]


@dataclass(frozen=True)
class ImportComparisonRow:
    character_id: int
    character_name: str
    replaced: bool
    original_damage: float
    mine_damage: float
    mine_basis: str                # exact | known | axis
    original_dps: float
    mine_dps: float

    @property
    def delta_percent(self) -> float | None:
        return (self.mine_damage / self.original_damage - 1.0) * 100.0 if self.original_damage > 0 else None


@dataclass(frozen=True)
class ImportComparisonScopeResult:
    detail_scope: str | None
    duration_seconds: float
    original_damage: float
    original_dps: float
    mine_damage: float | None
    mine_dps: float | None
    known_gain_percent: float | None
    status: str
    rows: tuple[ImportComparisonRow, ...]

    @property
    def delta_percent(self) -> float | None:
        if self.mine_damage is None or self.original_damage <= 0:
            return None
        return (self.mine_damage / self.original_damage - 1.0) * 100.0


def _first(*values):
    return next((v for v in values if v is not None), None)


def _equipment_key(items) -> list:
    rows = []
    for item in items or ():
        stats = sorted((str(s.get("stat_group")), str(s.get("property_id")), round(float(s.get("value") or 0), 4))
                       for s in item.get("stats") or ())
        rows.append((str(item.get("item_id")), item.get("level"), stats))
    return sorted(rows, key=repr)


class BattleImportComparisonService:
    """Qt-free service; the controller runs prepare()+compare() on a worker thread."""

    @staticmethod
    def state(history, battle_record_id: int) -> dict[str, Any]:
        with history._open_current_dao() as dao:
            origin = dao.load_battle_report_import_origin(int(battle_record_id))
            editable = bool(dao.battle_report_counterfactual_editable(int(battle_record_id))) if origin else False
        return {
            "imported": origin is not None,
            "available": origin is not None and editable,
            "source_account_nickname": str((origin or {}).get("source_account_nickname") or ""),
        }

    @staticmethod
    def prepare(history, battle_record_id: int, *, user_database_path: Path, static_database_path: Path) -> ImportComparisonPlan:
        record_id = int(battle_record_id)
        with history._open_current_dao() as dao:
            origin = dao.load_battle_report_import_origin(record_id)
            locks = dao.load_battle_import_equipment_locks(record_id) if origin else {}
        if origin is None:
            raise ValueError(_L('只有导入的战报可以与我的角色对比。'))
        editor = history.load_build_editor_data(record_id)
        prepared = BattleMarginalCandidateService.prepare_editor_data(editor, equipment_editable=False)

        cache: dict = {}
        profiles, matches, replaced_ids, scopes = [], [], set(), set()
        for detail in prepared.get("details") or ():
            original = dict(detail["profile"])
            cid = int(original["character_id"])
            name = str((detail.get("character") or {}).get("name_zh") or original.get("observed_name") or cid)
            scopes.add(detail.get("analysis_detail_scope"))
            role = load_official_role_detail(user_database_path, cid, include_inventory_contexts=True,
                                             static_database_path=static_database_path, request_cache=cache)
            prof = dict(role.get("profile") or {})
            ctx = dict((role.get("equipment_contexts") or {}).get("current") or {})
            sources = set((prof.get("field_sources") or {}).values())
            owned = bool(prof.get("persisted")) or "native_observed" in sources or bool(ctx.get("available"))
            source = ("account" if prof.get("persisted") else
                      "native_observed" if "native_observed" in sources else "template")
            if not owned or not ctx.get("available"):
                profiles.append(original)
                matches.append(ImportComparisonMatch(cid, name, False,
                                                     "not_owned" if not owned else "no_current_equipment",
                                                     source, (), False))
                continue

            mine = {k: deepcopy(v) for k, v in prof.items() if k not in _ROLE_PAGE_ONLY}
            mine.update(character_id=cid, observed_name=original.get("observed_name"),
                        ordinal=int(original.get("ordinal") or 0))
            for key in _SHAPE:
                if key in original:
                    mine[key] = deepcopy(original[key])
            if mine.get("fork_id") and mine.get("fork_breakthrough_stage") is None:
                fork_template = next((row for row in role.get("forks") or ()
                                      if str(row.get("fork_id") or "") == str(mine["fork_id"])), None)
                resolved = select_fork_breakthrough((fork_template or {}).get("breakthroughs") or (),
                                                    int(mine.get("fork_level") or 1))
                if resolved is not None:
                    mine["fork_breakthrough_stage"] = int(resolved["stage"])
            gear = freeze_equipment_context(ctx)
            mine.update(equipment_context_key="current",
                        equipment_context_title=str(ctx.get("title") or "current"),
                        equipment_source_kind="role_page_current",
                        equipment_override=gear)
            changed = tuple(k for k in _CULTIVATION if original.get(k) != mine.get(k))
            lock_gear = (locks.get(cid) or {}).get("equipment") or ()
            profiles.append(mine)
            replaced_ids.add(cid)
            matches.append(ImportComparisonMatch(cid, name, True, "replaced", source, changed,
                                                 _equipment_key(gear) != _equipment_key(lock_gear)))

        if not replaced_ids:
            raise ValueError(_L('当前账号没有与该战报相同且已装备空幕/驱动的角色。'))
        disabled = [f.fact_id for f in editor.get("inferred_character_facts") or ()
                    if getattr(f, "fact_kind", None) == "awaken_effect_active"
                    and int(getattr(f, "character_id", 0) or 0) in replaced_ids]
        candidate = BattleMarginalCandidateService.freeze(record_id, profiles, equipment_editable=True,
                                                          disabled_inferred_fact_ids=disabled)
        ordered_scopes = tuple(sorted((s for s in scopes if s is not None), key=str)) or (None,)
        return ImportComparisonPlan(record_id, str(origin.get("source_account_nickname") or ""),
                                    tuple(matches), candidate, ordered_scopes)

    @staticmethod
    def compare(history, plan: ImportComparisonPlan, *, static_database_path: Path,
                progress_callback: Callable[[Any], None] | None = None) -> tuple[ImportComparisonScopeResult, ...]:
        replaced = {m.character_id for m in plan.matches if m.replaced}
        names = {m.character_id: m.character_name for m in plan.matches}
        results = []
        for scope in plan.scopes:
            loaded = BattleReportAnalysisLoadService.load(history, BattleReportAnalysisLoadRequest(
                battle_record_id=plan.battle_record_id, detail_scope=scope, detail_level="marginal",
                marginal_candidate=plan.candidate, static_database_path=static_database_path,
            ), progress_callback=progress_callback)
            cf = loaded.analysis.build_counterfactual
            if cf is None:
                raise ValueError(_L('原生分析没有返回对比结果。'))
            duration = max(0.001, float(loaded.analysis.duration_seconds or 0.0))
            rows = []
            for role in cf.roles:
                mine = _first(role.candidate_damage, role.known_projection_damage, role.baseline_damage)
                basis = ("exact" if role.candidate_damage is not None else
                         "known" if role.known_projection_damage is not None else "axis")
                rows.append(ImportComparisonRow(
                    character_id=int(role.character_id),
                    character_name=names.get(int(role.character_id), str(role.character_name)),
                    replaced=int(role.character_id) in replaced,
                    original_damage=float(role.baseline_damage), mine_damage=float(mine), mine_basis=basis,
                    original_dps=float(role.baseline_damage) / duration, mine_dps=float(mine) / duration,
                ))
            # prefer the quantified projection over the heuristic one: for partially quantified axes the
            # heuristic keeps unquantified damage at its recorded value and can read as "no change"
            mine_damage = _first(cf.candidate_damage, cf.known_projection_damage, cf.heuristic_projection_damage)
            mine_dps = _first(cf.candidate_dps, cf.known_projection_dps, cf.heuristic_projection_dps)
            results.append(ImportComparisonScopeResult(
                detail_scope=scope, duration_seconds=duration,
                original_damage=float(cf.baseline_damage), original_dps=float(cf.baseline_dps),
                mine_damage=None if mine_damage is None else float(mine_damage),
                mine_dps=None if mine_dps is None else float(mine_dps),
                known_gain_percent=cf.known_gain_percent,
                status=str(getattr(cf.quantification.status, "value", cf.quantification.status)),
                rows=tuple(rows),
            ))
        return tuple(results)
