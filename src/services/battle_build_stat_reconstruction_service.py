# 使用冻结配装、修改养成和手工边际属性重建战报角色面板。
"""Battle-build stat reconstruction kept outside the history orchestrator."""

from __future__ import annotations

from typing import Any
from copy import deepcopy

from src.services.battle_build_equipment_service import battle_equipment_items
from src.services.character_shape_bonus_service import (
    character_shape_profile_fields,
)
from src.services.battle_report_persistence_service import (
    BattleReportPersistenceDependencies,
)
from src.services.official_role_attribute_service import (
    calculate_official_role_combat_stat_components,
    calculate_official_role_combat_stat_sources,
)
from src.services.official_role_page_service import load_official_role_detail
from src.services.puka_training_settings_service import (
    frozen_puka_training_detail,
    puka_training_property_stats,
)


class BattleBuildStatReconstructionService:
    """Rebuild missing or edited role stats without mutating saved battle facts."""

    @staticmethod
    def enrich(
        build: dict[str, Any],
        dependencies: BattleReportPersistenceDependencies,
        *,
        detail_cache: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        if dependencies.static_database_path is None:
            return
        detail_request_cache: dict[object, Any] = {}
        for character in build.get("characters") or ():
            existing_stats = list(character.get("stats") or ())
            existing_sources = {
                str(row.get("source_group") or "") for row in existing_stats
            }
            world_bonus_repair_required = "world_bonus" not in existing_sources
            # 显式家具副本（battle_world_bonus）只含家具值：恢复时不再扣除噗卡特训份额。
            explicit_world_bonus = bool(character.pop("_explicit_world_bonus", False))
            character_id = int(character["character_id"])
            items = battle_equipment_items(character)
            try:
                if detail_cache is not None and character_id in detail_cache:
                    detail = deepcopy(detail_cache[character_id])
                else:
                    detail = load_official_role_detail(
                        dependencies.user_database_path,
                        character_id,
                        include_inventory_contexts=False,
                        static_database_path=dependencies.static_database_path,
                        request_cache=detail_request_cache,
                    )
                    if detail_cache is not None:
                        detail_cache[character_id] = deepcopy(detail)
                frozen_world_bonus = {
                    str(row.get("property_id") or ""): float(
                        row.get("value") or 0.0
                    )
                    for row in existing_stats
                    if str(row.get("source_group") or "") == "world_bonus"
                }
                training_payload = build.get("puka_training")
                if training_payload is not None:
                    # 战报：加载器总会填入冻结等级（功能上线前的记录为 0）；队伍模拟的 build 没有该键，
                    # 保留 detail 中的账号等级。冻结时记录的累计数值（values）优先于当前等级表。
                    detail["puka_training"] = frozen_puka_training_detail(training_payload)
                training = puka_training_property_stats(detail.get("puka_training"))
                if frozen_world_bonus:
                    # 冻结的 world_bonus 行 = 家具 + 噗卡特训份额；扣回份额得到家具值。round(…, 6) 必需：
                    # (0.04 + t) - t 在 Lv 5–8/13–14 为 0.04000000000000001（超出 0.04 上限会放弃重建）。
                    # 份额为 0（Lv 0、显式家具副本）时原值不动，保证与功能上线前逐字节一致。
                    def furniture_value(property_id: str) -> float:
                        value = frozen_world_bonus.get(property_id, 0.0)
                        share = 0.0 if explicit_world_bonus else training.get(property_id, 0.0)
                        return round(value - share, 6) if share else value

                    detail["world_bonus"] = {
                        "yaodao_attack_add": furniture_value("AtkAdd"),
                        "quantao_crit_damage": furniture_value("CritDamageBase"),
                    }
                profile = dict(character.get("profile") or {})
                static_shape_fields = character_shape_profile_fields(
                    detail.get("shape_bonus")
                )
                shape_repair_required = any(
                    profile.get(key) != value
                    for key, value in static_shape_fields.items()
                )
                if (
                    {"character", "fork", "equipment"}.issubset(existing_sources)
                    and not shape_repair_required
                    and not world_bonus_repair_required
                ):
                    continue
                profile.update(static_shape_fields)
                character["profile"] = profile
                detail["profile"] = profile
                sources = calculate_official_role_combat_stat_sources(detail, items)
                resolved = calculate_official_role_combat_stat_components(detail, items)
            except (OSError, RuntimeError, ValueError):
                continue
            overrides = {
                str(key): float(value)
                for key, value in (
                    (character.get("profile") or {}).get("battle_stat_overrides")
                    or {}
                ).items()
            }
            resolved_values = {row.key: float(row.value) for row in resolved}
            source_rows = [
                {
                    "source_group": source_group,
                    "property_id": row.key,
                    "display_name": row.label,
                    "value": row.value,
                    "is_percent": row.percent,
                    "ordinal": ordinal,
                }
                for source_group, rows in sources.items()
                for ordinal, row in enumerate(rows)
            ]
            source_rows.extend(
                {
                    "source_group": "battle_override",
                    "property_id": property_id,
                    "display_name": next(
                        (row.label for row in resolved if row.key == property_id),
                        property_id,
                    ),
                    "value": value - resolved_values.get(property_id, 0.0),
                    "is_percent": next(
                        (row.percent for row in resolved if row.key == property_id),
                        False,
                    ),
                    "ordinal": ordinal,
                }
                for ordinal, (property_id, value) in enumerate(overrides.items())
                if property_id in resolved_values
                and value != resolved_values[property_id]
            )
            rebuild_resolved = (
                shape_repair_required
                or world_bonus_repair_required
                or "resolved" not in existing_sources
            )
            if rebuild_resolved:
                source_rows.extend(
                    {
                        "source_group": "resolved",
                        "property_id": row.key,
                        "display_name": row.label,
                        "value": overrides.get(row.key, row.value),
                        "is_percent": row.percent,
                        "ordinal": ordinal,
                    }
                    for ordinal, row in enumerate(resolved)
                )
            character["stats"] = [
                row
                for row in existing_stats
                if (
                    str(row.get("source_group") or "") == "resolved"
                    and not rebuild_resolved
                )
            ] + source_rows
            edited_equipment = bool(
                character.pop("_edited_equipment_active", False)
            )
            edited_snapshot = bool(character.pop("_edited_snapshot_active", False))
            character["stat_snapshot_source"] = (
                "user_edited_equipment_reconstructed"
                if edited_equipment
                else "user_edited_reconstructed"
                if edited_snapshot
                else "reconstructed_current_static_shape"
                if shape_repair_required
                else "reconstructed_current_world_bonus"
                if world_bonus_repair_required
                else "reconstructed_current_static"
            )
