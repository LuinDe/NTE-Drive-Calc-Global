# 定义战斗机制图鉴的 Qt-free 公开投影契约与稳定分类。
"""Immutable contracts and taxonomy for the combat-mechanics catalog."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from dataclasses import dataclass
from urllib.parse import quote, unquote

from src.domain.static_catalog import CatalogLink


@dataclass(frozen=True, slots=True)
class MechanicsFamily:
    key: str
    title: str
    subtitle: str
    glyph: str
    accent: str


@dataclass(frozen=True, slots=True)
class MechanicsCard:
    record_id: str
    family_key: str
    card_kind: str
    eyebrow: str
    title: str
    subtitle: str
    badges: tuple[str, ...]
    status: str | None = None
    owner_label: str = _L('公共机制')


@dataclass(frozen=True, slots=True)
class PlayerField:
    label: str
    value: str
    tone: str = "neutral"


@dataclass(frozen=True, slots=True)
class PlayerSection:
    title: str
    fields: tuple[PlayerField, ...]


@dataclass(frozen=True, slots=True)
class EvidenceStage:
    key: str
    label: str
    status: str
    summary: str


@dataclass(frozen=True, slots=True)
class MechanicsDetail:
    record_id: str
    card_kind: str
    title: str
    subtitle: str
    family_key: str
    badges: tuple[str, ...]
    status: str | None
    owner_label: str
    owner_link: CatalogLink | None
    redirect_only: bool
    sections: tuple[PlayerSection, ...]
    identity_fields: tuple[PlayerField, ...]
    evidence_stages: tuple[EvidenceStage, ...]
    related_links: tuple[tuple[str, CatalogLink], ...]
    audit_references: tuple[str, ...]
    notice: str = ""


FAMILIES = (
    MechanicsFamily("damage", _L('直伤链'), _L('面板、技能倍率与直伤总公式'), "✦", "#58a6ff"),
    MechanicsFamily("multipliers", _L('通用乘区'), _L('增伤、易伤、暴击、防御与抗性'), "◈", "#bc8cff"),
    MechanicsFamily("states", _L('DOT 与环合'), _L('噩梦、蚀心、鸩火与全部环合'), "◌", "#ff7b72"),
    MechanicsFamily("settlement", _L('倾陷与结算'), _L('团队倾陷、特殊结算与生命变化'), "◇", "#39d0d8"),
)
FAMILY_BY_KEY = {family.key: family for family in FAMILIES}

FORMULA_FAMILY_BY_KEY = {
    "panel_attribute": "damage",
    "skill_multiplier": "damage",
    "direct_damage": "damage",
    "damage_increase": "multipliers",
    "vulnerability": "multipliers",
    "critical": "multipliers",
    "defense": "multipliers",
    "resistance": "multipliers",
    "dot_damage": "states",
    "topple_damage": "states",
    "weave_followup": "states",
    "independent_final_damage": "settlement",
    "settlement_rounding": "settlement",
    "max_hp_settlement": "settlement",
}

FORMULA_CHAPTER_BY_KEY = {
    "panel_attribute": _L('面板'),
    "skill_multiplier": "技能倍率",
    "direct_damage": "直伤",
    "damage_increase": _L('增伤'),
    "vulnerability": _L('易伤'),
    "critical": "暴击",
    "defense": "防御",
    "resistance": _L('抗性'),
    "independent_final_damage": _L('独立增伤'),
    "dot_damage": "持续伤害",
    "topple_damage": "倾陷",
    "weave_followup": "覆纹",
    "settlement_rounding": _L('最终取整'),
    "max_hp_settlement": _L('生命结算'),
}
FORMULA_CHAPTER_ORDER = {
    chapter: index
    for index, chapter in enumerate((
        _L('面板'), "技能倍率", "直伤", _L('增伤'), _L('易伤'), "防御", _L('抗性'),
        "暴击", "持续伤害", "倾陷", "覆纹", _L('独立增伤'), _L('最终取整'),
        _L('生命结算'),
    ))
}
FORMULA_CHAPTER_ORDER.update({
    _L('持续直伤'): 8,
    _L('环合基础'): 9,
    "环合": 10,
    "倾陷": 11,
    "共享伤害": 12,
    _L('生命结算'): 13,
})
# 反事实模型仍供仓库审计使用，但不属于玩家图鉴的分类或卡墙。
STATUS_ORDER = {"complete": 0, "partial": 1, "unavailable": 2, "not_applicable": 3}
MODEL_FAMILY_BY_KEY = {
    "buff_ge_attributes": "attributes",
    "formal_dot_classification": "dot",
    "dot_state_replay": "dot",
    "topple_base_formula": "topple",
    "topple_special_states": "topple",
    "max_hp_settlement": "topple",
    "attachments": "events",
    "summon_lifecycle": "events",
    "healing_damage_coupling": "events",
    "healing_without_damage_consumer": "events",
    "shield_state": "events",
    "fixed_axis_replay": "formula",
    "native_counterfactual_core": "formula",
    "unknown_preservation": "formula",
}
PLACEHOLDER_NAME = "名称暂未提供"


def encode_record(kind: str, key: str) -> str:
    return f"{kind}|{quote(str(key), safe='')}"


def decode_record(record_id: str) -> tuple[str, str]:
    kind, separator, encoded = str(record_id).partition("|")
    if not separator or not kind or not encoded:
        raise ValueError(_L('战斗机制记录键格式无效'))
    return kind, unquote(encoded)
