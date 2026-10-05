# 提供游戏资料库 125 张发行静态表的固定只读登记。
"""Fixed-table coverage queries for the release static catalog overview."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.storage.sqlite.static_game_data_dao import StaticGameDataError, resolve_static_database
from src.storage.sqlite.static_game_data_metadata import (
    MINIMUM_SUPPORTED_SCHEMA_VERSION,
    SCHEMA_VERSION,
)


# 表名只来自本固定登记，绝不接受 UI 输入。状态是独立覆盖审计结论：
# A=完整正式目录，B=已公开但仍有高级字段，C=可展示且存在结构化缺口，
# D=只有 ID/有限证据，E=正式发行中为空或 payload 明确省略。
STATIC_TABLE_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("dataset", _L('元数据与来源'), "B"),
    ("schema_migration", _L('元数据与来源'), "B"),
    ("source_file", _L('元数据与来源'), "C"),
    ("source_row", _L('元数据与来源'), "E"),
    ("application_setting_default", _L('元数据与来源'), "B"),
    ("localized_term", _L('元数据与来源'), "B"),
    ("localized_term_name", _L('元数据与来源'), "A"),
    ("character", _L('角色与养成'), "A"),
    ("character_release_evidence", _L('角色与养成'), "B"),
    ("character_release_annotation", _L('角色与养成'), "B"),
    ("character_release_evidence_link", _L('角色与养成'), "B"),
    ("character_acquisition_membership", _L('角色与养成'), "A"),
    ("character_annotation", _L('角色与养成'), "B"),
    ("character_awaken_effect", _L('角色与养成'), "A"),
    ("character_awaken_skill_level_bonus", _L('角色与养成'), "A"),
    ("character_likeability_bonus", _L('角色与养成'), "B"),
    ("character_likeability_bonus_property", _L('角色与养成'), "B"),
    ("character_panel_growth", _L('角色与养成'), "A"),
    ("character_skill", _L('角色与养成'), "A"),
    ("character_skill_level", _L('角色与养成'), "B"),
    ("character_cultivation_guide", _L('角色与养成'), "C"),
    ("character_cultivation_fork_recommendation", _L('角色与养成'), "B"),
    ("character_cultivation_attribute_recommendation", _L('角色与养成'), "C"),
    ("character_cultivation_stage", _L('角色与养成'), "C"),
    ("character_cultivation_stage_skill", _L('角色与养成'), "B"),
    ("character_weight_recommendation", _L('角色与养成'), "B"),
    ("character_weight_recommendation_property", _L('角色与养成'), "B"),
    ("character_graduation_template", _L('角色与养成'), "B"),
    ("character_shape_bonus", _L('角色与养成'), "E"),
    ("character_shape_bonus_property", _L('角色与养成'), "E"),
    ("logical_character_shape_bonus", _L('角色与养成'), "A"),
    ("logical_character_shape_bonus_property", _L('角色与养成'), "B"),
    ("fork_type", _L('弧盘'), "B"),
    ("fork_item", _L('弧盘'), "A"),
    ("fork_modify_pack", _L('弧盘'), "B"),
    ("fork_modify_value", _L('弧盘'), "A"),
    ("fork_upgrade_level", _L('弧盘'), "B"),
    ("fork_breakthrough", _L('弧盘'), "A"),
    ("fork_refinement_parameter_value", _L('弧盘'), "A"),
    ("fork_permanent_property", _L('弧盘'), "A"),
    ("fork_star_level", _L('弧盘'), "A"),
    ("fork_star_parameter", _L('弧盘'), "A"),
    ("fork_lottery_campaign", _L('弧盘'), "A"),
    ("progression_item", _L('角色与养成'), "A"),
    ("progression_item_alias", _L('角色与养成'), "B"),
    ("item_quality_term", _L('角色与养成'), "A"),
    ("equipment_attribute", _L('装备与套装'), "A"),
    ("equipment_base_attribute_curve", _L('装备与套装'), "B"),
    ("equipment_base_attribute_point", _L('装备与套装'), "B"),
    ("equipment_buff_curve", _L('装备与套装'), "B"),
    ("equipment_buff_curve_point", _L('装备与套装'), "B"),
    ("equipment_core_random_attribute", _L('装备与套装'), "D"),
    ("equipment_item", _L('装备与套装'), "A"),
    ("equipment_strength_level", _L('装备与套装'), "D"),
    ("equipment_modify_pack", _L('装备与套装'), "B"),
    ("equipment_modify_value", _L('装备与套装'), "B"),
    ("equipment_plan", _L('装备与套装'), "A"),
    ("equipment_plan_cell", _L('装备与套装'), "A"),
    ("equipment_plan_core_attribute", _L('装备与套装'), "B"),
    ("equipment_plan_module", _L('装备与套装'), "A"),
    ("equipment_plan_recommended_attribute", _L('装备与套装'), "B"),
    ("equipment_shape", _L('装备与套装'), "A"),
    ("equipment_shape_cell", _L('装备与套装'), "A"),
    ("equipment_suit", _L('装备与套装'), "A"),
    ("equipment_suit_effect", _L('装备与套装'), "A"),
    ("equipment_suit_required_shape", _L('装备与套装'), "B"),
    ("gameplay_ability_catalog", _L('技能与正式标识'), "B"),
    ("gameplay_ability_description", _L('技能与正式标识'), "C"),
    ("gameplay_ability_level_hint", _L('技能与正式标识'), "B"),
    ("gameplay_effect_catalog", _L('技能与正式标识'), "B"),
    ("skill_damage", _L('技能与正式标识'), "A"),
    ("skill_damage_modifier", _L('技能与正式标识'), "B"),
    ("character_combat_ability_binding", _L('技能与正式标识'), "B"),
    ("combat_ability_effect_binding", _L('技能与正式标识'), "B"),
    ("combat_ability_montage_binding", _L('技能与正式标识'), "B"),
    ("combat_level_curve", _L('公式与效果证据'), "B"),
    ("combat_level_curve_point", _L('公式与效果证据'), "B"),
    ("reaction_definition", _L('公式与效果证据'), "C"),
    ("combat_effect_constant", _L('公式与效果证据'), "C"),
    ("damage_resistance_term", _L('公式与效果证据'), "A"),
    ("combat_effect_definition", _L('公式与效果证据'), "B"),
    ("combat_effect_buff_link", _L('公式与效果证据'), "B"),
    ("combat_curve", _L('公式与效果证据'), "B"),
    ("combat_curve_point", _L('公式与效果证据'), "B"),
    ("buff_definition", _L('公式与效果证据'), "B"),
    ("buff_modifier", _L('公式与效果证据'), "B"),
    ("buff_trigger_effect", _L('公式与效果证据'), "B"),
    ("roguelike_modifier_profile", _L('公式与效果证据'), "C"),
    ("roguelike_modifier_property", _L('公式与效果证据'), "C"),
    ("combat_blueprint_asset", _L('蓝图与动画证据'), "B"),
    ("combat_blueprint_reference", _L('蓝图与动画证据'), "B"),
    ("combat_blueprint_semantic_property", _L('蓝图与动画证据'), "B"),
    ("combat_blueprint_tag", _L('蓝图与动画证据'), "B"),
    ("combat_montage", _L('蓝图与动画证据'), "B"),
    ("combat_montage_section", _L('蓝图与动画证据'), "B"),
    ("combat_montage_notify", _L('蓝图与动画证据'), "B"),
    ("monster_catalog", _L('怪物与画像'), "A"),
    ("monster_identifier_alias", _L('怪物与画像'), "B"),
    ("monster_template_binding", _L('怪物与画像'), "B"),
    ("monster_boss_support", _L('怪物与画像'), "B"),
    ("monster_instance_profile", _L('怪物与画像'), "B"),
    ("monster_instance_profile_variant", _L('怪物与画像'), "B"),
    ("enemy_combat_profile", _L('怪物与画像'), "B"),
    ("enemy_element_resistance", _L('怪物与画像'), "B"),
    ("abyss_level", _L('玩法与遭遇'), "A"),
    ("abyss_level_monster_spawn", _L('玩法与遭遇'), "B"),
    ("abyss_monster_pool_entry", _L('玩法与遭遇'), "B"),
    ("clone_activity_category", _L('玩法与遭遇'), "A"),
    ("clone_activity", _L('玩法与遭遇'), "B"),
    ("clone_activity_difficulty", _L('玩法与遭遇'), "B"),
    ("clone_drop_projection", _L('玩法与遭遇'), "B"),
    ("clone_drop_projection_item", _L('玩法与遭遇'), "A"),
    ("clone_drop_projection_gap", _L('玩法与遭遇'), "C"),
    ("clone_spawn_member", _L('玩法与遭遇'), "B"),
    ("feast_stage", _L('玩法与遭遇'), "A"),
    ("feast_stage_difficulty", _L('玩法与遭遇'), "B"),
    ("feast_option", _L('玩法与遭遇'), "A"),
    ("feast_stage_option", _L('玩法与遭遇'), "A"),
    ("divination_buff", _L('玩法与遭遇'), "A"),
    ("outer_realm_rotation", _L('玩法与遭遇'), "A"),
    ("outer_realm_season_buff", _L('玩法与遭遇'), "A"),
    ("catalog_outer_realm_season", _L('玩法与遭遇'), "A"),
    ("outer_realm_season_buff_component", _L('玩法与遭遇'), "B"),
    ("high_risk_commission", _L('玩法与遭遇'), "B"),
    ("high_risk_commission_difficulty", _L('玩法与遭遇'), "B"),
    ("high_risk_monster_pool_member", _L('玩法与遭遇'), "B"),
)


@dataclass(frozen=True, slots=True)
class StaticTableOverview:
    name: str
    domain: str
    coverage_state: str
    rows: int


class StaticCatalogOverviewQueries:
    """Count every registered static table through a schema-checked RO handle."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = resolve_static_database(database_path)
        try:
            self._connection = sqlite3.connect(
                f"{self.database_path.as_uri()}?mode=ro", uri=True
            )
        except sqlite3.Error as exc:
            raise StaticGameDataError(_L('无法只读打开资料库覆盖总览')) from exc
        version = self._connection.execute(
            "SELECT MAX(version) FROM schema_migration"
        ).fetchone()[0]
        self._schema_version = int(version or 0)
        if not MINIMUM_SUPPORTED_SCHEMA_VERSION <= self._schema_version <= SCHEMA_VERSION:
            self.close()
            raise StaticGameDataError(
                (_LF('不支持的静态数据库结构版本：{0!r}；支持 ').format((version)) + _LF('{0} 至 {1}').format((MINIMUM_SUPPORTED_SCHEMA_VERSION), (SCHEMA_VERSION)))
            )

    def close(self) -> None:
        connection = getattr(self, "_connection", None)
        if connection is not None:
            connection.close()
            self._connection = None

    def list_tables(self) -> tuple[StaticTableOverview, ...]:
        if self._connection is None:
            raise StaticGameDataError(_L('资料库覆盖总览连接已关闭'))
        available_tables = {
            str(row[0])
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        rows: list[StaticTableOverview] = []
        for name, domain, state in STATIC_TABLE_CATALOG:
            if name not in available_tables:
                continue
            count = self._connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            rows.append(StaticTableOverview(name, domain, state, int(count)))
        return tuple(rows)
