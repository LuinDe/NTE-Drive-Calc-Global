# 分开展示逐击原生 Buff 采样与规则推断的结构化加成详情。
"""Reusable modeless dialog for observed effects and inferred Buff projection."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Sequence

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from src.services.battle_native_evidence_rendering import render_field_evidence, render_native_evidence
from src.domain.battle_report import (
    BattleAnalysisHit,
    BattleHitReplayResult,
    BattleInferredBuffInterval,
)
from src.services.battle_hit_buff_explanation_service import (
    BattleHitBuffExplanationService,
)
from .hit_inspection_dialog import HitInspectionDialog


class BattleHitBuffDialog(HitInspectionDialog):
    """Keep one modeless dialog while the user inspects adjacent hit rows."""

    def __init__(self, parent: QWidget | None = None, *, game_ui_asset_root=None) -> None:
        super().__init__(parent, game_ui_asset_root=game_ui_asset_root)
        self.setWindowTitle(_L('逐击详情'))
        self.detail.setObjectName("battleHitBuffDetail")

    def show_for_hit(
        self,
        hit: BattleAnalysisHit,
        intervals: Sequence[BattleInferredBuffInterval],
        *,
        replay: BattleHitReplayResult | None = None,
        projection=None, participant_names=None, target_resolutions=(),
    ) -> None:
        self.setWindowTitle(_LF('逐击详情 · Hit #{0} · {1}').format((hit.sequence), (hit.character_name)))
        self.inspection.set_hit(hit, replay, projection, participant_names=participant_names, target_resolutions=target_resolutions)
        hp_before = "—" if hit.target_hp_before is None else f"{hit.target_hp_before:,.0f}"
        hp_after = "—" if hit.target_hp_after is None else f"{hit.target_hp_after:,.0f}"
        raw_lines = (
            (_LF('事件 ID：{0}\n序号：{1}\n').format((hit.event_id), (hit.sequence)) + f"Ability：{hit.ability_id or '—'}\nGE：{hit.gameplay_effect_id or '—'}\n" + _LF('组件：{0}\n攻击类型：{1}\n').format((hit.damage_component or '—'), (hit.attack_type or '—')) + _LF('伤害属性：{0}\n目标 ID：{1}\n').format((hit.damage_attribute or '—'), (hit.target_id or '—')) + f"HP：{hp_before} → {hp_after}\n" + _L('Buff口径：原始逐击归属；公式另按正式来源角色消费属性。\n'))
        )
        replay_lines = _L('公式重放：尚未生成')
        if replay is not None:
            factors = "\n".join(
                f"- {row.label}: {row.value:g}（{row.evidence_basis}）"
                for row in replay.factors
            ) or _L('- 无结构化因子')
            gaps = "\n".join(f"- {row}" for row in replay.missing_evidence)
            replay_lines = (
                (_LF('公式重放：{0}\n').format((replay.selected_damage if replay.selected_damage is not None else '—')) + _LF('暴击判定：{0}\n置信度：{1}\n').format((replay.critical_state), (replay.confidence)) + _LF('暴击策略：{0}\n公式类型：{1}\n').format((replay.critical_policy), (replay.formula_type)) + _LF('因子：\n{0}').format((factors)))
                + (_LF('\n缺失证据：\n{0}').format((gaps)) if gaps else "")
            )
        self.detail.setPlainText(
            raw_lines + "\n" + render_field_evidence(hit.field_evidence)
            + "\n" + render_native_evidence(hit.native_evidence)
            + _L('\n\n规则推断与公式重放（与原生采样分开）\n') + replay_lines + "\n\n"
            + BattleHitBuffExplanationService.build(hit, intervals, projection=projection,
                                                   allow_projection_fallback=False)
        )
        self.detail.moveCursor(QTextCursor.MoveOperation.Start)
        self.fit_overview()
        self.show()
        self.raise_()
        self.activateWindow()
