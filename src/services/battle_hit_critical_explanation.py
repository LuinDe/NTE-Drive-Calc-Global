from src.i18n_runtime import L as _L, LF as _LF
# 区分公式暴击分支与原生观测标记，避免把飘字标记当作伤害倍率证据。
from src.domain.battle_report import BattleAnalysisHit, BattleHitReplayResult


def critical_explanation(hit: BattleAnalysisHit, replay: BattleHitReplayResult) -> str:
    states = {"critical": _L('是'), "non_critical": _L('否'), "not_applicable": _L('不适用'), "unknown": "未知"}
    evidence = hit.field_evidence
    if replay.critical_policy == "disabled" and replay.critical_state == "not_applicable":
        label = _L('公式暴击：不适用（当前公式不使用暴击倍率）')
        if evidence is not None and evidence.critical_source == "native_prediction":
            label += _LF('；原生预测/飘字暴击标记：{0}').format((states.get(evidence.critical_state, '未知')))
        return label
    if evidence is not None and (evidence.critical_source.startswith("native_") or evidence.critical_source == "server_settlement"):
        source = {"native_prediction": _L('原生预测/飘字'), "native_execution": _L('原生执行'), "server_settlement": _L('原生结算')}.get(evidence.critical_source, _L('原生观测'))
        return _LF('{0}暴击：{1}（字段置信度{2}）').format((source), (states.get(evidence.critical_state, '未知')), (evidence.critical_confidence))
    return _LF('推断暴击：{0}（置信度{1}）').format((states.get(replay.critical_state, replay.critical_state)), (replay.confidence))
