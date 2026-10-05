# 将原生逐击效果快照渲染为来源明确的只读详情，不计算 Buff 收益。
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import json
import math

from src.domain.battle_native_evidence import BattleHitFieldEvidence, BattleNativeHitEvidence


def field_critical_label(evidence: BattleHitFieldEvidence) -> str:
    """Render the core's decision without interpreting the captured payload."""
    state = {"critical": "暴击", "non_critical": _L('未暴击'),
             "not_applicable": _L('不适用'), "unknown": "未知"}[evidence.critical_state]
    source = evidence.critical_source
    kind = {"unknown": "未知", "static_rule": _L('静态规则'), "static_ge": _L('静态规则'),
            "native_prediction": _L('客户端预测观测'), "native_execution": _L('执行观测'),
            "server_settlement": _L('服务器结算观测'),
            "native_metadata": _L('原生观测')}.get(source, _L('来源未识别'))
    return f"{state}（{kind}，{evidence.critical_confidence}）"


def render_field_evidence(evidence: BattleHitFieldEvidence | None) -> str:
    if evidence is None:
        return _L('字段判定：尚无独立证据结果；公式判定须按推断理解。')
    return "\n".join((
        _L('字段判定（分析核心）'),
        _LF('暴击：{0}；来源：{1}').format((field_critical_label(evidence)), (evidence.critical_source)),
        (_LF('属性来源：{0}；').format((evidence.damage_attribute_source)) + _LF('置信度：{0}').format((evidence.damage_attribute_confidence))),
        *evidence.notes,
    ))


def _value(value: object) -> str:
    if value is None or value == "":
        return "未知"
    if isinstance(value, bool):
        return _L('是') if value else _L('否')
    if isinstance(value, (str, int)):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(value)
    return "未知"


def _execution(value: object) -> list[str]:
    lines = [_L('【执行输入与输出（原始观测）】')]
    if value is None:
        return lines + [_L('本击没有已关联的执行输入记录；已有暴击或元素字段不代表完整输入已采集。')]
    if not isinstance(value, dict):
        return lines + [_L('执行证据格式无效，不能解释为没有修正项。')]
    if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1:
        return lines + [_L('执行证据版本尚不支持解释，原文仍随逐击保留。')]
    lines.extend([
        _LF('执行 ID：{0}；采集代次：{1}').format((_value(value.get('executionId'))), (_value(value.get('generation')))),
        _LF('求值覆盖：{0}（未观测不等于没有参与项）').format((_value(value.get('evaluationCoverage')))),
        _LF('名称解析：{0}；FName 索引只作本次运行身份，不能直接还原标签名称。').format((_value(value.get('nameResolution')))),
        _L('以下是执行阶段冻结的 Spec 输入与输出；捕获定义、标签或 Spec 修正项存在，不等于该项实际被公式采用。'),
        _L('DLL 不复算伤害；尚未观测的属性求值、条件过滤及来源链不作为已知事实。'),
    ])
    for key, label in (("before", _L('执行前')), ("after", _L('执行后'))):
        phase = value.get(key)
        lines.append(f"{label}：")
        if not isinstance(phase, dict):
            lines.append(_L('未取得该阶段记录，不能与另一时点拼成完整输入。'))
        else:
            lines.append((_LF('时间（Unix 微秒）：{0}；').format((_value(phase.get('observedUnixUs')))) + _LF('状态：{0}').format((_value(phase.get('status'))))))
            for name, item in phase.items():
                if name in ("observedUnixUs", "status"):
                    continue
                # Display captured values only, without resolving definitions into applied bonuses.
                try:
                    raw = json.dumps(item, ensure_ascii=False, allow_nan=False,
                                     separators=(",", ":"))
                except (ValueError, TypeError):
                    raw = _L('格式无效；原始记录保留，不能按零或空列表解释')
                lines.append(f"{name}：{raw}")
    return lines


def _snapshot(title: str, value: object, names: dict[str, str]) -> list[str]:
    lines = [f"【{title}】"]
    if value is None:
        return lines + [_L('未取得快照；不能判断该侧是否存在 Buff。')]
    if not isinstance(value, dict) or not isinstance(value.get("effects"), list):
        return lines + [_L('快照格式无效；不能解释为空 Buff 列表。')]
    effects = value["effects"]
    complete = value.get("complete") is True
    live = value.get("ended") is False
    lines.extend([
        _LF('对象：{0} / {1}').format((_value(value.get('actorName'))), (_value(value.get('actor')))),
        (_LF('快照 ID：{0}；对象索引/代次：').format((_value(value.get('id')))) + f"{_value(value.get('actorIndex'))}/{_value(value.get('actorSerial'))}"),
        (_LF('快照内容版本时间（Unix 微秒）：{0}；').format((_value(value.get('observedUs')))) + _LF('世界时间（秒）：{0}').format((_value(value.get('worldSeconds'))))),
        (_LF('快照列表完整：{0}；').format(('是' if complete else '未确认')) + _LF('状态：{0}；对象已结束：{1}').format((_value(value.get('status'))), (_value(value.get('ended'))))),
    ])
    if not effects:
        return lines + ([_L('已采集有效空列表：该对象本次快照中没有效果条目。')]
                        if complete and live else
                        [_L('本次返回 0 条；快照不完整或对象已结束，不能认定没有 Buff。')])
    lines.append(_LF('观察到 {0} 条效果（存在记录不等于对本击生效）：').format((len(effects))))
    for index, effect in enumerate(effects, 1):
        if not isinstance(effect, dict):
            lines.append(_LF('{0}. 条目格式无效').format((index)))
            continue
        name = names.get(str(effect.get('key', '')))
        lines.extend([
            f"{index}. {name + '（静态目录名称）' if name else _value(effect.get('name') or effect.get('key'))}",
            _LF('   定义：{0}；实例：{1}').format((_value(effect.get('key'))), (_value(effect.get('instanceKey')))),
            _LF('   来源：{0}；种类：{1}').format((_value(effect.get('source'))), (_value(effect.get('kind')))),
            (_LF('   层数：{0}；等级：{1}；').format((_value(effect.get('stacks'))), (_value(effect.get('level')))) + _LF('已抑制：{0}').format((_value(effect.get('inhibited'))))),
            (_LF('   持续时间（秒）：{0}；').format((_value(effect.get('duration')))) + _LF('开始世界时间：{0}').format((_value(effect.get('startWorldTime'))))),
        ])
        if effect.get("description"):
            lines.append(_LF('   描述：{0}').format((_value(effect.get('description')))))
    return lines


def render_native_evidence(evidence: BattleNativeHitEvidence | None) -> str:
    """Display immutable observations without joining inferred identity or modifier state."""
    heading = _L('原生 DLL 逐击证据')
    if evidence is None:
        return heading + _L('\n未采集原生逐击证据（旧战报或该击没有原生证据）。')
    try:
        payload = json.loads(evidence.payload_json)
    except (ValueError, TypeError):
        return heading + _L('\n原生证据格式无效，不能解释为空列表。')
    if not isinstance(payload, dict) or not isinstance(payload.get("rawHit"), dict):
        return heading + _L('\n原生证据格式无效，不能解释为空列表。')
    hit = payload["rawHit"]
    critical_known = hit.get("criticalKnown") is True or hit.get("metadataKnown") is True
    element_known = hit.get("damageTypeKnown") is True or hit.get("metadataKnown") is True
    critical = _value(hit.get("critical")) if critical_known else "未知"
    lines = [heading,
             (_LF('提供方：{0}；采集场次：{1}；').format((_value(payload.get('providerId'))), (_value(payload.get('captureId')))) + _LF('原生逐击 ID：{0}').format((_value(payload.get('hitId'))))),
             _LF('伤害来源：{0}；关联依据：{1}').format((_value(hit.get('source'))), (_value(hit.get('association')))),
             (_LF('伤害采样阶段：{0}；').format((_value(hit.get('captureStage')))) + _LF('效果采样阶段：{0}').format((_value(hit.get('effectsStage'))))),
             (_L('本击来源侧 / 目标侧效果读取时间（Unix 微秒）：') + f"{_value(hit.get('attackerEffectsObservedUnixUs'))} / " + f"{_value(hit.get('victimEffectsObservedUnixUs'))}"),
             _LF('正式结算伤害：{0}；GE：{1}').format((_value(hit.get('damage'))), (_value(hit.get('gameplayEffectName')))),
             _LF('原生暴击：{0}；证据来源：{1}').format((critical), (_value(hit.get('criticalSource')))),
             (_LF('原生字段标志：metadataKnown={0}；').format((_value(hit.get('metadataKnown')))) + f"criticalKnown={_value(hit.get('criticalKnown'))}；" + f"damageTypeKnown={_value(hit.get('damageTypeKnown'))}；" + _LF('正式显示类型：{0}').format((_value(hit.get('displayType'))))),
             (_LF('伤害类型原始枚举：{0}；').format((_value(hit.get('damageType')) if element_known else '未知')) + _LF('证据来源：{0}').format((_value(hit.get('damageTypeSource'))))),
             (_LF('结算标识：{0}；分量：{1}；').format((_value(hit.get('settlementKey'))), (_value(hit.get('componentOrdinal')))) + _LF('末分量：{0}').format((_value(hit.get('lastTargetComponent'))))),
             _LF('服务器结算生命：{0}；采样阶段：{1}').format((_value(hit.get('victimHp'))), (_value(hit.get('victimHpStage')))),
             _LF('观测最大生命：{0}；采样阶段：{1}').format((_value(hit.get('victimMaxHp'))), (_value(hit.get('victimMaxHpStage')))),
             (_LF('生命 / 上限采样时间（Unix 微秒）：{0} / ').format((_value(hit.get('victimHpObservedUnixUs')))) + f"{_value(hit.get('victimMaxHpObservedUnixUs'))}"),
             _L('生命与上限按各自采样阶段展示，不拼成同一时点的前后血量。'),
             _L('完整性：仅描述当时读到的对象效果；全场来源覆盖未知，时停完整性由本场时钟证据单独说明。'),
             _L('效果存在、层数和采样时刻是观察值；不据此认定增伤比例、对本击生效或完整队伍 Buff。')]
    # Keep source and target identities as sampled, even if a replay uses another panel owner.
    names = dict(evidence.static_names)
    lines.extend(_execution(hit.get("executionEvidence")))
    lines.extend(_snapshot(_L('辅助：伤害来源侧效果'), hit.get("attackerEffects"), names))
    lines.extend(_snapshot(_L('辅助：受击目标侧效果'), hit.get("victimEffects"), names))
    return "\n".join(lines)
