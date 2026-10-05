# 生成加权配装结果中未分配角色和缺失卡带的说明文本。
"""Human-readable result explanations independent from Qt layout code."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from src.services.allocation_context import AllocationContext


def unassigned_reason(
    owner,
    context: AllocationContext | None,
    character_ids: tuple[int, ...],
) -> str:
    if context is None:
        return _L('部分角色没有可用的完整方案。')
    names = getattr(owner, "_weighted_role_names", {})
    suits = getattr(owner, "_weighted_suit_names", {})
    attributes = getattr(owner, "_weighted_property_names", {})
    reasons = []
    for role in context.roles:
        if role.character_id not in character_ids:
            continue
        cores = [item for item in context.candidates if item.kind == "core"]
        if role.target_suit_id:
            cores = [
                item for item in cores if item.suit_id == role.target_suit_id
            ]
        if role.core_main_property_id:
            cores = [
                item
                for item in cores
                if any(
                    stat.property_id == role.core_main_property_id
                    for stat in item.main_stats
                )
            ]
        if not cores:
            suit = suits.get(
                role.target_suit_id, role.target_suit_id or _L('任意套装')
            )
            attribute = attributes.get(
                role.core_main_property_id,
                role.core_main_property_id or _L('任意主词条'),
            )
            reasons.append(
                (f"{names.get(role.character_id, role.character_id)}：" + _LF('缺少 {0}＋{1} 主词条卡带').format((suit), (attribute)))
            )
        else:
            reasons.append(
                (f"{names.get(role.character_id, role.character_id)}：" + _L('缺少可组成完整图纸的驱动'))
            )
    return "；".join(reasons)


def missing_core_text(owner, role, reason: str | None = None) -> str:
    if reason:
        return _LF('卡带缺失：{0}（驱动图纸已匹配，方案将按不完整状态保存）').format((reason))
    if role is None:
        return _L('卡带未分配')
    suits = getattr(owner, "_weighted_suit_names", {})
    attributes = getattr(owner, "_weighted_property_names", {})
    suit = suits.get(role.target_suit_id, role.target_suit_id or _L('任意套装'))
    attribute = attributes.get(
        role.core_main_property_id,
        role.core_main_property_id or _L('任意主词条'),
    )
    return (
        (_LF('卡带缺失：缺少 {0}＋{1} 主词条卡带').format((suit), (attribute)) + _L('（驱动图纸已匹配）'))
    )
