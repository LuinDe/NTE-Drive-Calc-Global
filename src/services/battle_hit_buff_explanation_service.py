# 把单次逐击的 Buff 证据与属性投影整理为可审计的中文详情。
"""Qt-free explanation of the core's per-hit Buff decisions."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Sequence

from src.domain.battle_report import (
    BattleAnalysisHit,
    BattleBuffProjectionDecision,
    BattleInferredBuffInterval,
)
from src.services.battle_buff_attribute_projection_service import (
    BattleBuffAttributeProjectionService,
    normalize_battle_buff_property_id,
)
from src.services.skill_name_rendering_service import preferred_battle_damage_name


_SCOPE_LABELS = {
    "self": _L('自身'),
    "team": _L('全队'),
    "target": _L('敌方目标'),
    "unknown": _L('作用对象待确认'),
}
_STATUS_LABELS = {
    "applied": _L('已投影'),
    "not_applied": _L('未采用'),
    "unresolved": _L('待确认/结构化'),
}
_PROPERTY_LABELS = {
    "AtkUp": _L('攻击力提升'),
    "AtkAdd": _L('额外攻击力'),
    "HPMaxUp": _L('生命上限提升'),
    "HPMaxAdd": _L('额外生命上限'),
    "DefUp": _L('防御力提升'),
    "DefAdd": _L('额外防御力'),
    "CritBase": "暴击率",
    "CritDamageBase": "暴击伤害",
    "DamageUpGeneralBase": _L('通用伤害提升'),
    "DamageUpChaosBase": _L('暗属性异能伤害提升'),
    "DamageUpCosmosBase": _L('光属性异能伤害提升'),
    "DamageUpIncantationBase": _L('咒属性异能伤害提升'),
    "DamageUpLakshanaBase": _L('相属性异能伤害提升'),
    "DamageUpNatureBase": _L('灵属性异能伤害提升'),
    "DamageUpPsycheBase": _L('魂属性异能伤害提升'),
    "DamageUpPsychicallyBase": _L('心灵伤害提升'),
    "DefIgnore": _L('防御穿透'),
    "DamagePenetrateChaos": _L('暗属性穿透'),
    "DamagePenetrateCosmos": _L('光属性穿透'),
    "DamagePenetrateIncantation": _L('咒属性穿透'),
    "DamagePenetrateLakshana": _L('相属性穿透'),
    "DamagePenetrateNature": _L('灵属性穿透'),
    "DamagePenetratePsyche": _L('魂属性穿透'),
    "DamagePenetratePsychically": _L('心灵属性穿透'),
    "DamageResistChaosBase": _L('敌方暗属性抗性变化'),
    "DamageResistChaosAdd": _L('敌方额外暗属性抗性变化'),
    "DamageResistCosmosBase": _L('敌方光属性抗性变化'),
    "DamageResistCosmosAdd": _L('敌方额外光属性抗性变化'),
    "DamageResistIncantationBase": _L('敌方咒属性抗性变化'),
    "DamageResistIncantationAdd": _L('敌方额外咒属性抗性变化'),
    "DamageResistLakshanaBase": _L('敌方相属性抗性变化'),
    "DamageResistLakshanaAdd": _L('敌方额外相属性抗性变化'),
    "DamageResistNatureBase": _L('敌方灵属性抗性变化'),
    "DamageResistNatureAdd": _L('敌方额外灵属性抗性变化'),
    "DamageResistPsycheBase": _L('敌方魂属性抗性变化'),
    "DamageResistPsycheAdd": _L('敌方额外魂属性抗性变化'),
    "DamageResistPsychicallyBase": _L('敌方心灵抗性变化'),
    "DamageResistPsychicallyAdd": _L('敌方额外心灵抗性变化'),
    "MagBase": "环合强度",
    "UnbalIntensityBase": "倾陷强度",
    "UnbalIntensityUp": _L('倾陷强度提升'),
    "UnbalIntensityAdd": _L('额外倾陷强度'),
    "UnbalDamageUp": _L('倾陷伤害提升'),
    "ChargeGetEfficiencyBase": "充能效率",
    "ImmuneDeadByTeammates": _L('队友免死'),
    "ShareOutTeammatesDamageMul": _L('队友伤害分摊'),
    "MoveSpeedMaxMult": _L('移动速度上限'),
}
_PERCENT_PROPERTIES = frozenset({
    "AtkUp",
    "HPMaxUp",
    "DefUp",
    "CritBase",
    "CritDamageBase",
    "DamageUpGeneralBase",
    "DefIgnore",
    "UnbalIntensityUp",
    "UnbalDamageUp",
    "ChargeGetEfficiencyBase",
    *(
        property_id
        for property_id in _PROPERTY_LABELS
        if property_id.startswith("DamageUp")
        or property_id.startswith("DamagePenetrate")
        or property_id.startswith("DamageResist")
    ),
})


def _time(value_us: int) -> str:
    seconds = max(0, value_us) / 1_000_000.0
    minutes = int(seconds // 60)
    return f"{minutes:02d}:{seconds - minutes * 60:06.3f}"


def battle_buff_property_label(property_id: str) -> str:
    return _PROPERTY_LABELS.get(property_id, property_id)


def format_battle_buff_value(property_id: str, value: float) -> str:
    if property_id in _PERCENT_PROPERTIES:
        return f"{value * 100:+g}%"
    return f"{value:+,.3f}".rstrip("0").rstrip(".")


def _raw_modifier_lines(
    interval: BattleInferredBuffInterval,
    decision: BattleBuffProjectionDecision,
) -> tuple[str, ...]:
    lines = []
    applied_ids = set(decision.applied_property_ids)
    for modifier in interval.modifiers:
        property_id = normalize_battle_buff_property_id(modifier.property_id)
        label = battle_buff_property_label(property_id)
        if modifier.magnitude_value is not None:
            total = float(modifier.magnitude_value) * max(1, interval.stacks)
            value = format_battle_buff_value(property_id, total)
            if interval.stacks > 1:
                value += (
                    (f"（{format_battle_buff_value(property_id, float(modifier.magnitude_value))}" + _LF(' × {0} 层）').format((interval.stacks)))
                )
        elif modifier.calculation_asset_path:
            value = (
                "Calculation："
                + modifier.calculation_asset_path.rsplit("/", 1)[-1]
            )
        else:
            value = _L('数值尚未解析')
        usage = _L('已投影到属性值') if property_id in applied_ids else _L('未投影到属性值')
        lines.append(
            (_LF('  - {0} {1}（{2}，{3}，数值置信度').format((label), (value), (property_id), (usage)) + f" {modifier.value_confidence}）")
        )
    return tuple(lines) or (_L('  - 没有提取到属性修正。'),)


class BattleHitBuffExplanationService:
    """Describe active intervals and their exact per-hit projection decision."""

    @classmethod
    def build(
        cls,
        hit: BattleAnalysisHit,
        intervals: Sequence[BattleInferredBuffInterval],
        *, projection=None, allow_projection_fallback: bool = True,
    ) -> str:
        if projection is None and allow_projection_fallback:
            projection = BattleBuffAttributeProjectionService.project_hit(hit, intervals)
        if projection is None:
            return _L('本击未生成 Buff 分析详情；请先加载对应时段的逐击分析。')
        active_by_id = {row.interval_id: row for row in intervals}
        decisions = tuple(
            decision
            for decision in projection.decisions
            if decision.interval_id in active_by_id
        )
        counts = {
            status: sum(row.status == status for row in decisions)
            for status in _STATUS_LABELS
        }
        damage_name = preferred_battle_damage_name(
            hit.damage_name,
            hit.skill_name,
            hit.ability_id,
        )
        lines = [
            f"{hit.character_name} · {damage_name}",
            _LF('命中时间：{0}    目标：{1}').format((_time(hit.relative_time_us)), (hit.target_name)),
            (
                (_LF('命中时 Buff 分析：{0} 个    ').format((len(decisions))) + _LF('已投影 {0} / 未采用 {1} / ').format((counts['applied']), (counts['not_applied'])) + _LF('待确认 {0}').format((counts['unresolved'])))
            ),
            _L('口径：采用分析核心返回的逐击判定；运行时观测、静态规则与推断须按各项依据区分。'),
            _L('状态证据与数值证据分别标注；观测到效果存在，不等于已证明它对本击的数值收益。'),
            (_L('公式消费口径：已投影只表示进入逐击属性值；是否被当前伤害公式消费，') + _L('以伤害公式列出的乘区和来源项为准。')),
            "",
            _L('【投影到逐击属性值的加成汇总】'),
        ]
        if projection.modifiers:
            for modifier in projection.modifiers:
                sources = "、".join(modifier.buff_names)
                lines.append(
                    (f"- {battle_buff_property_label(modifier.property_id)} " + f"{format_battle_buff_value(modifier.property_id, modifier.additive_value)}" + f"（{modifier.property_id}，{_SCOPE_LABELS.get(modifier.target_scope, modifier.target_scope)}，" + _LF('置信度 {0}）\n').format((modifier.confidence)) + _LF('  来源：{0}').format((sources)))
                )
        else:
            lines.append(_L('- 没有 Buff 数值投影到本击属性值。'))

        decision_by_status = {
            status: tuple(row for row in decisions if row.status == status)
            for status in _STATUS_LABELS
        }
        for status, title in _STATUS_LABELS.items():
            matching = decision_by_status[status]
            if not matching:
                continue
            lines.extend(("", f"【{title} Buff】"))
            for decision in matching:
                interval = active_by_id[decision.interval_id]
                lines.append(
                    (_LF('- {0}（公式采用区间层数 ×{1}）').format((interval.buff_name), (interval.stacks)) + _LF('（来源角色：{0}；').format((interval.source_character_name)) + _LF('作用对象：{0}；').format((_SCOPE_LABELS.get(interval.target_scope, interval.target_scope))) + _LF('区间：{0}—{1}；').format((_time(interval.start_us)), (_time(interval.end_us))) + _LF('状态 {0} / 数值 {1}）').format((decision.state_confidence or interval.state_confidence), (interval.value_confidence)))
                )
                if decision.observed_stacks is not None:
                    lines.append((_LF('  回调采样层数：{0}；').format((decision.observed_stacks)) + _L('该时点不等于执行前，不据此替换公式采用层数。')))
                lines.extend(_raw_modifier_lines(interval, decision))
                if decision.reasons:
                    lines.append(_LF('  判定：{0}').format(('；'.join(decision.reasons))))
                lines.extend((
                    f"  ID：{interval.source_effect_definition_id}",
                    _LF('  资产：{0}').format((interval.buff_asset_path)),
                    _LF('  状态依据：{0}').format((interval.inference_basis)),
                ))
        if not decisions:
            lines.extend((
                "",
                _L('【证据边界】'),
                _L('- 本击没有匹配到命中时有效的推算 Buff 区间。'),
            ))
        return "\n".join(lines)
