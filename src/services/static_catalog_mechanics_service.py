# 将效果、公式和反事实审计投影成玩家可读的统一战斗机制图鉴。
"""Qt-free player projections for the unified combat-mechanics catalog."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path
import re

from src.services.static_catalog_formula_presenters import (
    build_formula_detail_sections,
)
from src.services.static_catalog_formula_service import StaticCatalogFormulaService
from src.services.static_catalog_mechanics_details import (
    StaticCatalogMechanicsDetailProjector,
)
from src.services.static_catalog_mechanics_identity import (
    StaticCatalogMechanicsIdentityProvider,
)
from src.services.static_catalog_mechanics_models import (
    CatalogLink,
    FAMILY_BY_KEY,
    FAMILIES,
    FORMULA_CHAPTER_BY_KEY,
    FORMULA_CHAPTER_ORDER,
    FORMULA_FAMILY_BY_KEY,
    MechanicsCard,
    MechanicsDetail,
    MechanicsFamily,
    PLACEHOLDER_NAME,
    PlayerField,
    PlayerSection,
    decode_record,
    encode_record,
)
from src.services.static_catalog_mechanics_terminology import (
    build_mechanics_terminology_service,
)
from src.services.static_catalog_misc_models import CatalogDetail, CatalogSearchItem
from src.services.static_catalog_misc_service import StaticCatalogMiscService
from src.services.static_catalog_special_formula_service import (
    SpecialFormulaRecord,
    StaticCatalogSpecialFormulaService,
)
from src.services.static_catalog_terminology_service import (
    StaticCatalogTerminologyService,
)

_HIDDEN_FIELD_PARTS = (
    _L('路径'), "SHA", _L('来源行'), _L('来源文件'), _L('文件 ID'), _L('公式版本'), "payload",
)
_IDENTITY_LABEL_PARTS = (
    _L('正式 ID'), _L('正式索引'), "Gameplay Tag", _L('定义 key'), _L('曲线正式 ID'),
    _L('常量 ID'), _L('环合类型'), "Buff key",
)
_EFFECT_TYPE_LABELS = {
    "gameplay_effect": _L('正式 Gameplay Effect 定义'),
    "gameplay_ability": _L('正式角色技能'),
    "skill_damage": _L('正式技能伤害项'),
    "buff": _L('正式 Buff 定义'),
    "combat_effect": _L('战斗机制效果'),
    "combat_curve": _L('战斗曲线'),
    "combat_level_curve": _L('等级曲线'),
    "reaction": _L('异能环合规则'),
    "combat_constant": _L('战斗常量'),
    "gameplay_tag": _L('正式 Gameplay Tag'),
    "roguelike_modifier": _L('玩法属性包'),
}
_VALUE_LABELS = {
    "RCIM_Constant": _L('常量插值'),
    "Infinite": _L('无限持续'),
    "Instant": _L('立即结算'),
    "HasDuration": _L('有限持续'),
    "EGameplayEffectDurationType::HasDuration": _L('有限持续'),
    "EGameplayEffectDurationType::Infinite": _L('无限持续'),
    "EGameplayEffectDurationType::Instant": _L('立即结算'),
    "None": _L('未提供'),
    "—": "不可用",
    "buff": "Buff",
}
class StaticCatalogMechanicsService:
    """Compose existing read-only domains without exposing audit internals to Qt."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        terminology_service: StaticCatalogTerminologyService | None = None,
    ) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self._misc = StaticCatalogMiscService(
            self.database_path,
            manifest_path=self.database_path.with_name("manifest.json"),
        )
        self._terminology = (
            terminology_service or build_mechanics_terminology_service(self._misc)
        )
        self._details = StaticCatalogMechanicsDetailProjector(self._terminology)
        self._identity_provider = StaticCatalogMechanicsIdentityProvider(
            self.database_path,
            self._terminology,
        )
        domain = StaticCatalogFormulaService(self.database_path).load()
        self._formulas = {
            formula.key: formula
            for section in build_formula_detail_sections(domain)
            for formula in section.formulas
        }
        self._special_formulas = {
            formula.key: formula
            for formula in StaticCatalogSpecialFormulaService(
                self.database_path
            ).load()
        }
        self.projection_version = domain.projection_version
        self.dataset_id = domain.evidence_snapshot.dataset_id

    @property
    def families(self) -> tuple[MechanicsFamily, ...]:
        return FAMILIES

    def status_counts(self) -> tuple[tuple[str, int], ...]:
        """Counterfactual coverage is intentionally absent from the player catalog."""
        return ()

    def browse(
        self,
        family_key: str,
        query: str = "",
        *,
        limit: int = 30,
    ) -> tuple[MechanicsCard, ...]:
        family = FAMILY_BY_KEY.get(str(family_key))
        if family is None:
            raise ValueError(_LF('未知机制家族：{0!r}').format((family_key)))
        needle = str(query).strip().casefold()
        cards = self._formula_cards(family.key, needle)
        return tuple(sorted(cards, key=self._card_sort_key)[:limit])

    def detail(self, record_id: str) -> MechanicsDetail:
        kind, key = decode_record(record_id)
        if kind == "formula":
            special = self._special_formulas.get(key)
            if special is not None:
                return self._special_formula_detail(special)
            try:
                formula = self._formulas[key]
            except KeyError as exc:
                raise LookupError(_L('公式不存在')) from exc
            return self._details.formula_detail(formula)
        if kind == "model":
            raise LookupError(_L('反事实模型不在玩家图鉴中展示'))
        if kind == "effect":
            entity_kind, separator, entity_key = key.partition(chr(31))
            if not separator:
                raise ValueError(_L('效果记录键格式无效'))
            try:
                raw = self._misc.detail(entity_kind, entity_key)
            except (KeyError, LookupError) as exc:
                raise LookupError(_L('关联机制不存在')) from exc
            if not isinstance(raw, CatalogDetail):
                raise LookupError(_L('效果详情不可用'))
            return self._effect_detail(raw, record_id)
        raise ValueError(_LF('不支持的战斗机制记录：{0!r}').format((kind)))

    def _formula_cards(self, family_key: str, needle: str) -> list[MechanicsCard]:
        rows = []
        for formula in self._formulas.values():
            if formula.key in self._special_formulas:
                continue
            if FORMULA_FAMILY_BY_KEY.get(formula.key) != family_key:
                continue
            title, expression, variables = self._details.player_formula(formula)
            variable_text = " ".join(
                text for label, meaning in variables for text in (label, meaning)
            )
            haystack = " ".join((title, expression, variable_text)).casefold()
            if needle and needle not in haystack:
                continue
            rows.append(MechanicsCard(
                record_id=encode_record("formula", formula.key),
                family_key=family_key,
                card_kind="formula",
                eyebrow=FORMULA_CHAPTER_BY_KEY.get(formula.key, "公式"),
                title=title,
                subtitle=expression,
                badges=(),
            ))
        for formula in self._special_formulas.values():
            if formula.family_key != family_key:
                continue
            haystack = " ".join((
                formula.title,
                formula.subtitle,
                *formula.aliases,
                *(section.title for section in formula.sections),
                *(
                    text
                    for section in formula.sections
                    for field in section.fields
                    for text in (field.label, field.value)
                ),
            )).casefold()
            if needle and needle not in haystack:
                continue
            rows.append(MechanicsCard(
                record_id=encode_record("formula", formula.key),
                family_key=family_key,
                card_kind="formula",
                eyebrow=formula.chapter,
                title=formula.title,
                subtitle=formula.subtitle,
                badges=(formula.chapter,),
                status=formula.status,
            ))
        return rows

    @staticmethod
    def _special_formula_detail(
        formula: SpecialFormulaRecord,
    ) -> MechanicsDetail:
        return MechanicsDetail(
            record_id=encode_record("formula", formula.key),
            card_kind="formula",
            title=formula.title,
            subtitle=formula.subtitle,
            family_key=formula.family_key,
            badges=(formula.chapter,),
            status=formula.status,
            owner_label=_L('公共公式'),
            owner_link=None,
            redirect_only=False,
            sections=formula.sections,
            identity_fields=(),
            evidence_stages=(),
            related_links=(),
            audit_references=(),
            notice=formula.notice,
        )

    def _public_effect_cards(
        self,
        items: tuple[CatalogSearchItem, ...],
        fallback_family: str,
        *,
        include_unnamed: bool,
    ) -> list[MechanicsCard]:
        cards = []
        unnamed_kinds: set[str] = set()
        semantic_identities: set[tuple[str, str]] = set()
        for item in items:
            raw = self._misc.detail(item.entity_kind, item.entity_key)
            if not isinstance(raw, CatalogDetail):
                continue
            display_name = self._effect_display_name(raw)
            owner_label, _owner_link = self._identity_provider.owner(raw)
            identity = (item.entity_kind, display_name.casefold())
            if identity in semantic_identities:
                continue
            semantic_identities.add(identity)
            if display_name == PLACEHOLDER_NAME:
                if not include_unnamed:
                    continue
                if item.entity_kind in unnamed_kinds:
                    continue
                unnamed_kinds.add(item.entity_kind)
            cards.append(self._effect_card(
                item,
                self._effect_family(raw) or fallback_family,
                display_name,
                owner_label,
            ))
        return cards

    def _identity_cards(
        self,
        family_key: str,
        needle: str,
    ) -> list[MechanicsCard]:
        cards: list[MechanicsCard] = []
        identities: set[tuple[str, str]] = set()
        kind_counts: dict[str, int] = {}
        for candidate in self._identity_provider.candidates():
            if needle and needle not in " ".join((
                candidate.item.title,
                candidate.item.subtitle,
            )).casefold():
                continue
            try:
                raw = self._misc.detail(
                    candidate.item.entity_kind,
                    candidate.item.entity_key,
                )
            except LookupError:
                continue
            if not isinstance(raw, CatalogDetail):
                continue
            resolved_family = candidate.family_hint or self._effect_family(raw)
            if not needle and resolved_family != family_key:
                continue
            display_name = self._effect_display_name(raw)
            if display_name == PLACEHOLDER_NAME:
                continue
            identity = (raw.entity_kind, display_name.casefold())
            if identity in identities:
                continue
            if not needle and kind_counts.get(raw.entity_kind, 0) >= 4:
                continue
            identities.add(identity)
            cards.append(self._effect_card(
                candidate.item,
                resolved_family,
                display_name,
                self._identity_provider.owner(raw)[0],
            ))
            kind_counts[raw.entity_kind] = kind_counts.get(raw.entity_kind, 0) + 1
            if not needle and len(cards) >= 12:
                break
        return cards

    @staticmethod
    def _effect_card(
        item: CatalogSearchItem,
        family_key: str,
        display_name: str,
        owner_label: str,
    ) -> MechanicsCard:
        labels = {
            "gameplay_ability": _L('正式技能'),
            "skill_damage": _L('正式伤害项'),
            "gameplay_effect": "GAMEPLAY EFFECT",
            "buff": "BUFF",
            "combat_effect": _L('机制效果'),
            "combat_curve": "COMBAT CURVE",
            "combat_level_curve": _L('等级曲线'),
            "reaction": _L('异能环合'),
            "combat_constant": _L('战斗常量'),
            "gameplay_tag": "GAMEPLAY TAG",
            "roguelike_modifier": _L('玩法属性包'),
        }
        return MechanicsCard(
            record_id=encode_record(
                "effect", f"{item.entity_kind}{chr(31)}{item.entity_key}"
            ),
            family_key=family_key,
            card_kind="effect",
            eyebrow=labels.get(item.entity_kind, _L('公共效果')),
            title=display_name,
            subtitle=StaticCatalogMechanicsService._player_effect_subtitle(item),
            badges=(item.origin_label,),
            owner_label=owner_label,
        )

    @staticmethod
    def _player_effect_subtitle(item: CatalogSearchItem) -> str:
        subtitle = str(item.subtitle).strip()
        if StaticCatalogMechanicsService._hidden(_L('摘要'), subtitle):
            return _EFFECT_TYPE_LABELS.get(item.entity_kind, _L('公共战斗机制'))
        if re.search(r"[#_/]|\b(?:GA|GE|RCIM|RCCE)\b", subtitle):
            return _EFFECT_TYPE_LABELS.get(item.entity_kind, _L('公共战斗机制'))
        return subtitle or _EFFECT_TYPE_LABELS.get(item.entity_kind, _L('公共战斗机制'))

    def _effect_display_name(self, raw: CatalogDetail) -> str:
        identity = self._identity_provider.resolve(raw)
        return identity.display_name or PLACEHOLDER_NAME

    def _effect_detail(self, raw: CatalogDetail, record_id: str) -> MechanicsDetail:
        owner_label, owner_link = self._identity_provider.owner(raw)
        sections: list[PlayerSection] = []
        unstructured = False
        if owner_link is not None:
            sections.append(PlayerSection(
                _L('所属对象'),
                (PlayerField(_L('归属'), owner_label, "accent"),),
            ))
        for section in raw.sections:
            fields: list[PlayerField] = []
            for field in section.fields:
                if self._hidden(field.label, field.value):
                    if "Calculation" in field.label or "/Calculation" in field.value:
                        unstructured = True
                    continue
                if self._identity(field.label, field.value):
                    continue
                if self._unreadable_raw(field.label, field.value):
                    continue
                fields.append(PlayerField(
                    field.label,
                    self._player_value(field.value),
                    self._field_tone(field.label),
                ))
            if fields and any(
                field.label != "序号" for field in fields
            ):
                sections.append(PlayerSection(section.title, tuple(fields)))
        display_name = self._effect_display_name(raw)
        badges = (_EFFECT_TYPE_LABELS.get(raw.entity_kind, _L('战斗机制')),)
        notice = _L('数值规则暂未形成玩家可读说明。') if unstructured and not sections else ""
        return MechanicsDetail(
            record_id=record_id,
            card_kind="effect",
            title=display_name,
            subtitle=_EFFECT_TYPE_LABELS.get(raw.entity_kind, _L('公共战斗机制')),
            family_key=self._effect_family(raw),
            badges=badges,
            status=None,
            owner_label=owner_label,
            owner_link=owner_link,
            redirect_only=False,
            sections=tuple(sections),
            identity_fields=(),
            evidence_stages=(),
            related_links=(),
            audit_references=tuple(
                f"{section.title}:{field.label}" for section in raw.sections for field in section.fields
            ),
            notice=notice,
        )

    @staticmethod
    def _effect_family(raw: CatalogDetail) -> str:
        if raw.entity_kind in {"gameplay_ability", "skill_damage"}:
            return "damage"
        if raw.entity_kind == "reaction":
            return "states"
        text = " ".join(
            [raw.title, raw.subtitle]
            + [field.value for section in raw.sections for field in section.fields]
        ).casefold()
        if "state.damage.dot" in text or "持续伤害" in text:
            return "states"
        if "reaction" in text or "环合" in text or "gameplay tag" in text:
            return "states"
        if "unbal" in text or "倾陷" in text or _L('抗性') in text:
            return "states"
        if any(token in text for token in ("attachment", "召唤", "治疗", "护盾", "时停", _L('召唤'), _L('治疗'), _L('护盾'), _L('时停'))):
            return "settlement"
        return "multipliers"

    @staticmethod
    def _hidden(label: str, value: str) -> bool:
        if any(part.casefold() in str(label).casefold() for part in _HIDDEN_FIELD_PARTS):
            return True
        normalized = str(value).strip().replace("\\", "/")
        return "/Game/" in normalized or ":/" in normalized

    @staticmethod
    def _identity(label: str, value: str) -> bool:
        normalized = str(value).strip()
        if normalized in {"", "—"}:
            return False
        return str(label).strip().endswith("ID") or any(
            token.casefold() in str(label).casefold()
            for token in _IDENTITY_LABEL_PARTS
        )

    @staticmethod
    def _unreadable_raw(label: str, value: str) -> bool:
        label_text = str(label).strip()
        value_text = str(value).strip()
        if label_text.endswith("ID"):
            return True
        if label_text in {_L('反应类型'), _L('元素一'), _L('元素二')}:
            return True
        if "_" in label_text or value_text.startswith(("{", "[", "$[")):
            return True
        if "<" in value_text and ">" in value_text and not re.search(
            r"[\u3400-\u9fff]", value_text
        ):
            return True
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", value_text):
            return True
        return False

    @staticmethod
    def _clean_player_text(value: str) -> str:
        return re.sub(r"<[^>]+>", "", str(value)).strip()

    @classmethod
    def _player_value(cls, value: str) -> str:
        text = cls._clean_player_text(value)
        if text in _VALUE_LABELS:
            return _VALUE_LABELS[text]
        try:
            if abs(float(text)) >= 3.0e38:
                return "不可用"
        except ValueError:
            pass
        return text

    @staticmethod
    def _field_tone(label: str) -> str:
        if label in (_L('持续时间证据'), _L('持续策略')) or any(token in label for token in ("持续", _L('周期'), _L('叠层'), _L('目标'), _L('触发'))):
            return "accent"
        if "不可用" in label or "状态" in label:
            return "warning"
        return "neutral"

    @staticmethod
    def _technical_relation(label: str) -> bool:
        return any(token in label for token in (_L('资源'), "Calculation", "Blueprint", "Montage"))

    @staticmethod
    def _relation_link(target_kind: str, target_key: str) -> CatalogLink:
        return CatalogLink(
            "combat_mechanics",
            encode_record("effect", f"{target_kind}{chr(31)}{target_key}"),
            "related",
        )

    @staticmethod
    def _formula_links(properties: list[str]) -> list[tuple[str, CatalogLink]]:
        joined = " ".join(properties).casefold()
        mapping = (
            ("finaldamageup", "independent_final_damage", _L('查看特殊最终乘区')),
            ("defignore", "defense", _L('查看防御区')),
            ("damagepenetrate", "resistance", _L('查看抗性区')),
            ("crit", "critical", _L('查看暴击区')),
            ("damageup", "damage_increase", _L('查看增伤区')),
            ("atk", "panel_attribute", _L('查看面板公式')),
            ("hp", "panel_attribute", _L('查看面板公式')),
            ("def", "panel_attribute", _L('查看面板公式')),
        )
        rows = []
        for token, formula_key, label in mapping:
            if token in joined:
                rows.append((label, CatalogLink(
                    "combat_mechanics", encode_record("formula", formula_key), "formula"
                )))
        return list(dict.fromkeys(rows))

    @staticmethod
    def _mechanic_formula_links(
        entity_kind: str,
    ) -> list[tuple[str, CatalogLink]]:
        if entity_kind not in {
            "gameplay_ability", "skill_damage", "gameplay_effect", "buff",
        }:
            return []
        keys = (
            (_L('查看技能倍率'), "skill_multiplier"),
            (_L('查看直伤公式'), "direct_damage"),
        )
        return [
            (
                label,
                CatalogLink(
                    "combat_mechanics",
                    encode_record("formula", key),
                    "formula",
                ),
            )
            for label, key in keys
        ]

    def owner_resolution_counts(self) -> tuple[tuple[str, int], ...]:
        return self._identity_provider.owner_resolution_counts()

    def identity_provider_counts(self) -> tuple[tuple[str, int], ...]:
        return self._identity_provider.identity_provider_counts()

    def skill_relation_counts(self) -> tuple[tuple[str, int], ...]:
        return self._identity_provider.skill_relation_counts()

    @staticmethod
    def _dedupe_links(
        rows: list[tuple[str, CatalogLink]],
    ) -> list[tuple[str, CatalogLink]]:
        unique: dict[tuple[str, str, str, str], tuple[str, CatalogLink]] = {}
        for label, link in rows:
            key = (
                link.domain_key,
                link.record_id,
                link.relation_kind,
                link.anchor,
            )
            unique.setdefault(key, (label, link))
        return list(unique.values())

    @staticmethod
    def _kind_order(kind: str) -> int:
        return {"effect": 0, "formula": 1, "model": 2}.get(kind, 9)

    @classmethod
    def _card_sort_key(cls, card: MechanicsCard) -> tuple[int, int, str]:
        secondary = 0
        if card.card_kind == "formula":
            secondary = FORMULA_CHAPTER_ORDER.get(card.eyebrow, 99)
        return cls._kind_order(card.card_kind), secondary, card.title.casefold()
