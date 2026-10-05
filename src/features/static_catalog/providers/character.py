# 将角色资料域映射到公共只读提供器契约。
"""Adapt the character catalog domain to the common read-only provider contract."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from src.features.static_catalog.contracts import (
    CatalogDetail,
    CatalogDomain,
    CatalogItem,
    CatalogPage,
    CatalogReference,
    CatalogSection,
    StaticCatalogRelease,
)
from src.features.static_catalog.providers._shared import (
    annotation,
    derived,
    ensure_release_metadata,
    ensure_release_path,
    lines,
    official,
)
from src.services.static_catalog_character_models import CharacterDetail, CharacterSummary
from src.services.static_catalog_character_service import StaticCatalogCharacterService
from src.storage.sqlite.static_catalog_character_queries import (
    StaticCatalogCharacterQueries,
)


CHARACTER_DOMAIN = CatalogDomain(
    key="character",
    label=_L('角色数据'),
    description=_L('等级面板、突破状态、技能消耗、觉醒、好感度、培养与毕业模板'),
    order=10,
)


class CharacterCatalogProvider:
    """Own one read-only character DAO and expose only common catalog DTOs."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path).resolve()
        self._queries = StaticCatalogCharacterQueries(self._database_path)
        self._service = StaticCatalogCharacterService(self._queries)
        self._closed = False

    @property
    def domain(self) -> CatalogDomain:
        return CHARACTER_DOMAIN

    def close(self) -> None:
        if not self._closed:
            self._queries.close()
            self._closed = True

    def search(
        self,
        release: StaticCatalogRelease,
        *,
        query: str,
        offset: int,
        limit: int,
    ) -> CatalogPage:
        ensure_release_path(release, self._database_path)
        page = self._service.list_characters(query=query, offset=offset, limit=limit)
        self._ensure_dataset(release, page.dataset)
        return CatalogPage(
            items=tuple(self._item(item) for item in page.items),
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )

    def detail(
        self, release: StaticCatalogRelease, record_id: str,
    ) -> CatalogDetail | None:
        ensure_release_path(release, self._database_path)
        try:
            character_id = int(record_id)
        except (TypeError, ValueError):
            return None
        detail = self._service.get_character_detail(character_id)
        if detail is None:
            return None
        self._ensure_dataset(release, detail.dataset)
        growth = self._service.list_growth(character_id, limit=200)
        combat = self._service.list_combat_links(character_id, limit=500)
        sections = [
            self._identity(detail),
            self._availability(detail),
            CatalogSection(
                title=_L('1–80 级面板（含临界等级突破前后）'),
                fields=tuple(
                    official(
                        _LF('Lv.{0} · 阶段 {1} · {2}').format((point.level), (point.breakthrough_stage), (point.state)),
                        _LF('生命 {0:g} / 攻击 {1:g} / 防御 {2:g}').format((point.hp_base), (point.atk_base), (point.def_base)),
                    )
                    for point in growth.items
                ) or (derived(_L('面板状态'), _L('unavailable：该角色没有成长行')),),
            ),
        ]
        sections.extend(self._detail_sections(detail))
        if combat.items:
            sections.append(CatalogSection(
                title=_L('GA、GE 与 Buff 正式关系'),
                fields=tuple(
                    official(
                        f"{link.relationship_kind} · {link.binding_kind}",
                        " / ".join(filter(None, (
                            link.ability_id,
                            link.event_tag,
                            link.gameplay_effect_id,
                            link.buff_definition_id,
                            link.effect_asset_path,
                        ))),
                        copyable=True,
                    )
                    for link in combat.items
                ),
            ))
        return CatalogDetail(
            item=self._item(detail.character),
            sections=tuple(sections),
            notes=(
                _L('人物升级和突破需求关系缺失时保持 unavailable，不从文本、同名角色或账号数据猜测。'),
                _L('技能升级材料名称由公共术语服务解析；本提供器中的 raw ID 只作内部审计，不进入玩家主界面。'),
            ),
        )

    @staticmethod
    def _item(summary: CharacterSummary) -> CatalogItem:
        subtitle = (
            (_LF('{0} · 技能 {1} · ').format((summary.element_label), (summary.skill_count)) + _LF('觉醒 {0} · 成长状态 {1}').format((summary.awakening_count), (summary.growth_count)))
        )
        return CatalogItem(
            domain_key=CHARACTER_DOMAIN.key,
            record_id=str(summary.character_id),
            title=summary.name_zh,
            subtitle=subtitle,
        )

    @staticmethod
    def _ensure_dataset(release: StaticCatalogRelease, dataset: object) -> None:
        ensure_release_metadata(
            release,
            dataset_id=str(getattr(dataset, "dataset_id")),
            schema_version=int(getattr(dataset, "schema_version")),
            importer_version=int(getattr(dataset, "importer_version")),
            built_at_utc=str(getattr(dataset, "built_at_utc")),
        )

    @staticmethod
    def _identity(detail: CharacterDetail) -> CatalogSection:
        item = detail.character
        return CatalogSection(
            title=_L('角色身份与目录'),
            fields=(
                official("character_id", item.character_id, copyable=True),
                official(_L('中文名'), item.name_zh),
                official("属性", f"{item.element_label} · {item.element_type or '未保留'}"),
                official(_L('组别'), item.group_type),
                official(_L('Actor 路径'), item.actor_path, copyable=True),
                official(_L('大陆服展示时间'), item.mainland_show_time),
                annotation(_L('逻辑角色键'), item.logical_character_key, copyable=True),
                annotation(_L('规范角色 ID'), item.canonical_character_id, copyable=True),
                annotation(_L('分类'), item.classification),
                annotation(_L('注解来源'), detail.annotation_source),
            ),
        )

    @staticmethod
    def _availability(detail: CharacterDetail) -> CatalogSection:
        return CatalogSection(
            title=_L('数据可用性'),
            fields=(
                derived(_L('成长状态数'), detail.growth_count),
                derived(_L('战斗关系数'), detail.combat_link_count),
                *(derived(gap.label, f"{gap.status}：{gap.reason}") for gap in detail.gaps),
            ),
        )

    def _detail_sections(self, detail: CharacterDetail) -> list[CatalogSection]:
        sections: list[CatalogSection] = []
        if detail.likeability is not None:
            likeability = detail.likeability
            sections.append(CatalogSection(
                title=_LF('好感度 {0} 级加成').format((likeability.required_level)),
                fields=(
                    official("modify_data_id", likeability.modify_data_id, copyable=True),
                    *(official(
                        prop.display_name,
                        f"{prop.value:g} · {prop.modifier_operation}",
                    ) for prop in likeability.properties),
                ),
            ))
        for awakening in detail.awakenings:
            sections.append(CatalogSection(
                title=_LF('觉醒 {0} · {1}').format((awakening.ordinal), (awakening.title_zh or awakening.effect_id)),
                fields=(
                    official("effect_id", awakening.effect_id, copyable=True),
                    official(_L('类型'), awakening.awaken_type),
                    official(_L('说明'), awakening.description_zh),
                    official("Gameplay Effects", lines(list(awakening.gameplay_effect_ids)), copyable=True),
                    official(
                        _L('技能等级修改'),
                        lines([f"{row.skill_id} {row.level_delta:+d}" for row in awakening.skill_level_bonuses]),
                    ),
                    official(
                        _L('结构化效果'),
                        lines([f"{row.path} = {row.value_json}" for row in awakening.structured_effects]),
                    ),
                ),
            ))
        for skill in detail.skills:
            sections.append(CatalogSection(
                title=_LF('技能 · {0}').format((skill.name_zh or skill.skill_id)),
                fields=(
                    official("skill_id", skill.skill_id, copyable=True),
                    official(_L('类型 / 序号'), f"{skill.ability_type} / {skill.ability_index}"),
                    official("Gameplay Tag", skill.gameplay_tag, copyable=True),
                    official(_L('GA 路径'), skill.gameplay_ability_path, copyable=True),
                    official(_L('GE 路径'), skill.gameplay_effect_path, copyable=True),
                    official(
                        _L('等级、解锁与消耗'),
                        lines([
                            (_LF('Lv.{0} · 突破 {1} · ').format((level.level), (level.required_breakthrough_stage)) + _LF('觉醒 {0} · ').format((level.required_awaken_level)))
                            + (", ".join(
                                f"{cost.item_id} × {cost.quantity:g}" for cost in level.costs
                            ) or _L('无材料'))
                            for level in skill.levels
                        ]),
                    ),
                    official(
                        _L('正式说明'),
                        lines([
                            " · ".join(filter(None, (row.title_zh, row.description_zh, row.unlock_description_zh)))
                            for row in skill.descriptions
                        ]),
                    ),
                    official(
                        _L('等级提示与伤害索引'),
                        lines([
                            f"{row.name_id or row.ordinal} · {row.value_description_zh or row.description_zh or '未保留'}"
                            f" · damage={','.join(row.damage_effect_ids) or '无'}"
                            for row in skill.level_hints
                        ]),
                    ),
                ),
            ))
        if detail.cultivation is not None:
            guide = detail.cultivation
            references = tuple(
                CatalogReference(_L('查看推荐弧盘'), "fork", fork_id)
                for fork_id, _name, _description in guide.fork_recommendations
            )
            sections.append(CatalogSection(
                title=_L('养成指南'),
                fields=(
                    official(_L('评分阈值'), f"S {guide.s_score:g} / A {guide.a_score:g}"),
                    official(_L('推荐属性'), lines([f"{name} ({property_id})" for property_id, name in guide.attribute_recommendations])),
                    official(_L('推荐弧盘'), lines([f"{name} ({fork_id})" for fork_id, name, _description in guide.fork_recommendations])),
                    official(
                        _L('阶段路线'),
                        lines([
                            (_LF('阶段 {0}：角色 {1} / 弧盘 {2} / ').format((row.ordinal), (row.character_level), (row.fork_level)) + _LF('空幕 {0} Lv.{1} / 驱动 Lv.{2} / ').format((row.core_item_id), (row.core_level), (row.equipment_level)))
                            + _L('技能：')
                            + (
                                ", ".join(
                                    f"{sex_kind}:{ability_id} Lv.{recommended_level}"
                                    for sex_kind, ability_id, recommended_level
                                    in row.recommended_skills
                                )
                                or _L('无正式阶段技能')
                            )
                            for row in guide.stages
                        ]),
                    ),
                ),
                references=references,
            ))
        if detail.graduation is not None:
            graduation = detail.graduation
            references = (
                (CatalogReference(_L('查看毕业弧盘'), "fork", graduation.fork_id),)
                if graduation.fork_id else ()
            )
            sections.append(CatalogSection(
                title=_L('毕业模板（项目派生）'),
                fields=(
                    annotation(_L('来源类型'), graduation.source_kind),
                    annotation(_L('弧盘'), f"{graduation.fork_name_zh or '未保留'} ({graduation.fork_id or '无'})"),
                    annotation(_L('弧盘等级 / 混频'), f"{graduation.fork_level} / {graduation.fork_refinement_level}"),
                    annotation(_L('空幕套装'), f"{graduation.core_suit_name_zh or '未保留'} ({graduation.core_suit_id or '无'})"),
                    annotation(_L('卡带主属性'), graduation.core_main_property_name_zh or graduation.core_main_property_id),
                    annotation(_L('基准伤害'), graduation.benchmark_damage),
                ),
                references=references,
            ))
        return sections
