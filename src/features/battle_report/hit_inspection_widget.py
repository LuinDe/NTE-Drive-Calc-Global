# 逐击概览按乘区、参与方和实际贡献打开详情，只展示采集与核心已有结果。
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

import json

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.app.window_geometry import fit_dialog_to_available_screen
from src.services.battle_hit_buff_explanation_service import battle_buff_property_label
from .hit_formula_overview import HitFormulaOverview


ATTRIBUTE_NAMES = {
    "hp": _L('当前生命'), "maxHp": _L('最大生命'), "shield": _L('护盾'), "attack": "攻击力",
    "defense": "防御力", "crit": "暴击率", "critDamage": "暴击伤害", "mag": "环合强度",
    "damageUpGeneral": _L('通用增伤'), "chargeCurrent": _L('当前充能'), "chargeMax": _L('充能上限'),
    "unbalCurrent": _L('当前倾陷'), "unbalMax": _L('倾陷上限'), "unbalIntensity": "倾陷强度",
    "unbalAccrueEfficiency": _L('倾陷积累效率'), "unbalAntiAccrueEfficiency": _L('倾陷抗积累效率'),
    "unbalSpeed": _L('倾陷速度'), "unbalBonus": _L('倾陷加成'), "unbalReduceNatur": _L('倾陷自然减少'),
    "unbalValueAdd": _L('倾陷值附加'), "isBalancedingState": _L('倾陷相关状态'),
}
for _element, _name in (
    ("Normal", _L('普通')), ("Cosmos", "光"), ("Nature", "灵"), ("Incantation", "咒"),
    ("Chaos", "暗"), ("Psyche", "魂"), ("Lakshana", "相"), ("Psychically", "心灵"),
):
    ATTRIBUTE_NAMES[f"resist{_element}"] = _LF('{0}抗性').format((_name))
    ATTRIBUTE_NAMES[f"damageUp{_element}"] = _LF('{0}增伤').format((_name))


def shown(value):
    if value is None:
        return _L('未取得')
    if isinstance(value, bool):
        return _L('是') if value else _L('否')
    return f"{value:.8g}" if isinstance(value, (int, float)) else str(value)


def native_hit(hit):
    if hit.native_evidence is None:
        return {}
    try:
        value = json.loads(hit.native_evidence.payload_json)
        raw = value.get("rawHit", {})
        return raw if isinstance(raw, dict) else {}
    except (ValueError, TypeError, AttributeError):
        return {}


def term_side(term):
    """Use source identity, not the factor containing both participants."""
    if (term.term_id.startswith("target:") or term.source_group == "target"
            or term.property_id.startswith(("Resistance:", "DamageResist"))):
        return "victim"
    return "formula"


def term_source(term, projection=None):
    if term.source_group == "buff" and projection is not None:
        decisions = [d for d in projection.decisions if d.interval_id in term.term_id]
        return contribution_source(any(d.interval_id.startswith("native-applied:") for d in decisions), decisions)
    return {
        "native_panel": _L('实测属性'), "native_contribution": _L('实测贡献'),
        "counterfactual_panel": _L('证据推导'), "panel_inclusion_inferred": _L('推断（包含关系）'),
        "character": _L('冻结角色配置'), "resolved": _L('核心解析值'),
        "target": _L('目标配置／推断'), "buff": _L('Buff 贡献（来源见本击 Buff）'),
    }.get(term.source_group, _L('冻结来源／核心结果'))


def contribution_source(direct, decisions):
    if direct:
        return _L('采用实测写入值')
    applied = [d for d in decisions if d.status == "applied"]
    observed = [d for d in applied if d.observed_stacks is not None]
    if observed:
        return _L('状态有证据／贡献模型') if len(observed) == len(applied) else _L('部分状态有证据／贡献模型')
    return _L('模型推断贡献')


class HitInspectionWidget(QWidget):
    """One display component for the analysis and counterfactual detail dialogs."""

    technical_requested = Signal()

    def __init__(self, parent=None, *, game_ui_asset_root=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)
        self.overview = HitFormulaOverview(self, game_ui_asset_root=game_ui_asset_root)
        self.overview.participant_requested.connect(self.participant)
        self.overview.factor_requested.connect(self.factor)
        self.layout.addWidget(self.overview)
        footer = QHBoxLayout()
        self.buff_button = QPushButton(_L('本击 Buff 贡献'))
        self.buff_button.clicked.connect(self.contributions)
        self.evidence_button = QPushButton(_L('公式取值证据'))
        self.evidence_button.clicked.connect(self.formula_observations)
        self.technical_button = QPushButton(_L('完整公式与原始字段'))
        self.technical_button.clicked.connect(self.technical_requested)
        for button in (self.buff_button, self.evidence_button):
            footer.addWidget(button)
        footer.addStretch(1)
        footer.addWidget(self.technical_button)
        self.layout.addLayout(footer)
        self._popup = None

    def set_hit(self, hit, replay=None, projection=None, *, participant_names=None, target_resolutions=()):
        self.hit, self.replay, self.projection = hit, replay, projection
        self.raw = native_hit(hit)
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None
        self.overview.set_hit(hit, replay, self.raw, participant_names=participant_names, target_resolutions=target_resolutions)
        self.evidence_button.setVisible(bool((self.raw.get("executionEvidence") or {}).get("applicationEvidence")))

    def table(self, title, headers, rows, note=""):
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
        dialog = QDialog(self.window())
        dialog.setWindowTitle(title)
        root = QVBoxLayout(dialog)
        if note:
            label = QLabel(note)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            root.addWidget(label)
        table = QTableWidget(len(rows), len(headers), dialog)
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(shown(value))
                item.setToolTip(shown(value))
                table.setItem(r, c, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.resizeColumnsToContents()
        limits = (200, 85, 140, 70, 110, 190) if len(headers) == 7 else (300, 130, 170)
        for column, limit in enumerate(limits[:len(headers) - 1]):
            table.setColumnWidth(column, min(table.columnWidth(column), limit))
        table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        table.resizeRowsToContents()
        root.addWidget(table)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.hide)
        root.addWidget(close)
        fit_dialog_to_available_screen(dialog, QSize(1050, 580))
        self._popup = dialog
        dialog.show()

    def factor(self, factor):
        rows = [(t.label or t.property_id, t.value, t.source_name or t.source_group,
                 t.evidence_basis) for t in factor.terms]
        note = _LF('{0}\n本乘区结果：{1}\n{2}').format((factor.formula), (shown(factor.value)), (factor.evidence_basis))
        if factor.factor_id == "critical" and self.replay.critical_state in {"non_critical", "not_applicable"}:
            note = _LF('本击未采用暴击候选，乘区采用 1。以下保留暴击候选的倍率与来源。\n{0}').format((note))
        self.table(factor.label, [_L('输入项'), _L('结果值'), _L('来源'), _L('依据')], rows, note)

    def participant(self, side):
        raw = self.raw
        snapshot = raw.get(f"{side}Attributes") or {}
        title = {"attacker": _L('攻击方属性'), "victim": _L('受击方属性'), "formula": _L('公式属性方')}[side]
        rows = []
        # Identity, status and original getter source are carried with each sample.
        matched = (side != "formula" and snapshot.get("actorIndex") == raw.get(f"{side}ObjectIndex")
                   and snapshot.get("actorSerial", 0) > 0)
        for key, field in snapshot.get("values", {}).items():
            known = matched and field.get("status") == "ok" and field.get("value") is not None
            rows.append((ATTRIBUTE_NAMES.get(key, key), field.get("value") if known else None,
                         _L('实测') if known else _L('未取得'), field.get("source", "")))
        if side == "victim":
            rows.extend((label, value, _L('记录值'), basis) for label, value, basis in (
                (_L('结算前生命'), self.hit.target_hp_before, _L('战报原始生命证据')),
                (_L('结算后生命'), self.hit.target_hp_after, _L('战报原始生命证据')),
                (_L('生命上限'), self.hit.target_max_hp, _L('战报原始生命证据')),
            ) if value is not None)
        if self.replay is not None:
            for factor in self.replay.factors:
                if side == "attacker" and self.replay.formula_panel_character_id not in (0, None, self.hit.character_id):
                    continue
                rows.extend((_LF('公式输入 · {0}').format((t.label or t.property_id)), t.value,
                             term_source(t, self.projection), t.evidence_basis or t.source_name)
                            for t in factor.terms if (side == "victim") == (term_side(t) == "victim"))
        self.table(title, ["属性", _L('原始数值'), _L('来源类型'), _L('依据')], rows,
                   (_LF('观测阶段：{0}；观测编号：{1}。\n').format((snapshot.get('stage', '未取得')), (snapshot.get('id', '未取得'))) + _L('动态观测按游戏原始单位展示；公式输入来自计算核心。未取得第三方属性时不借用攻击方属性。')))

    def contributions(self):
        execution = self.raw.get("executionEvidence") or {}
        applications = execution.get("applicationEvidence") or {}
        rows = []
        identity = execution.get("identity") or {}
        for item in applications.get("items", []):
            if item.get("source") != "native_application":
                continue
            asc = item.get("recipientAsc") or {}
            weak = [asc.get("objectIndex"), asc.get("objectSerial")]
            side = _L('攻击方') if weak == identity.get("sourceAsc") else _L('受击方') if weak == identity.get("targetAsc") else _L('其他对象')
            relation = {"included": _L('已包含'), "excluded": _L('未包含')}.get(item.get("inclusion"), _L('包含关系待定'))
            usage = _L('公式读取已观测') if item.get("formulaUse") == "observed" else _L('公式读取尚未观测')
            buff = item.get("buff") or {}
            property_name = battle_buff_property_label(str(item.get("property") or ""))
            rows.append((_LF('原生属性写入 · {0}').format((property_name)), side, item.get("property"),
                         item.get("value"), _L('实测写入'), _L('原始应用证据（与下方采用值不重复相加）'),
                         (_LF('{0}；{1}；层数 {2}；{3}；').format((relation), (usage), (shown(item.get('stacks'))), (item.get('operation', ''))) + _LF('原始效果标识：{0}').format((buff.get('className') or buff.get('name') or '未取得')))))
        if self.projection is not None:
            terms = [t for f in (() if self.replay is None else self.replay.factors) for t in f.terms]
            for modifier in self.projection.modifiers:
                decisions = [d for d in self.projection.decisions if d.interval_id in modifier.interval_ids]
                direct = any(i.startswith("native-applied:") for i in modifier.interval_ids)
                measured = any(t.source_group == "native_panel" and
                               (t.property_id == modifier.property_id or
                                t.term_id == "native:attack" and modifier.property_id in {"AtkBase", "AtkUp", "AtkAdd"} or
                                t.term_id == "native:maxHp" and modifier.property_id in {"HPMaxBase", "HPMaxUp", "HPMaxAdd"})
                               and (term_side(t) == "victim") == (modifier.target_scope == "target") for t in terms)
                referenced = any(any(i in t.term_id for i in modifier.interval_ids) for t in terms)
                has_extra = any(t.term_id.startswith("native-extra:") and t.value != 0 for t in terms)
                usage = (_L('该属性按实测基准与本击贡献解析；包含关系见乘区') if measured and has_extra else
                         _L('实测面板已覆盖该属性；来源拆分用于解释／反事实') if measured else
                         _L('作为公式输入') if referenced else _L('当前公式未单独使用；仅保留模型关联'))
                rows.append(("、".join(modifier.buff_names),
                             {"self": _L('攻击／公式属性方'), "target": _L('受击方'), "team": _L('队伍')}.get(modifier.target_scope, modifier.target_scope),
                             modifier.property_id, modifier.additive_value, contribution_source(direct, decisions), usage,
                             "；".join(reason for d in decisions for reason in d.reasons)
                             or _LF('核心投影；置信度 {0}').format((modifier.confidence))))
        self.table(_L('本击 Buff 贡献'), ["Buff", _L('作用对象'), "属性", _L('贡献值'), _L('来源'), _L('计算用途'), _L('采用依据')], rows,
                   (_L('上方实测写入与核心采用值是两个视角，不能把两者再次相加。\n') + _LF('当前直接证据范围：{0}；').format((applications.get('coverage', '未取得'))) + _LF('状态：{0}。\n').format((applications.get('status', '未取得'))) + _L('应用列表并不覆盖所有 Buff。实测面板与各 Buff 的来源拆分是不同证据；') + _L('模型关联不代表本击已实测应用，详见计算用途。')))

    def formula_observations(self):
        execution = self.raw.get("executionEvidence") or {}
        evidence = execution.get("applicationEvidence") or {}
        bound = (self.raw.get("executionId") is not None
                 and str(self.raw["executionId"]) == str(execution.get("executionId")))
        rows = []
        for term in evidence.get("baseTerms", []):
            component = term.get("component") or {}
            identity = _LF('组件 {0}:{1}').format((component.get('objectIndex')), (component.get('objectSerial')))
            witness = (bound and term.get("returned") is True and term.get("identityStable") is True
                       and term.get("attackReadPathObserved") is True)
            for key, label in (("usedAttack", _L('实际读取攻击力')), ("result", _L('基础项返回值'))):
                field = term.get(key) or {}
                known = field.get("status") == "ok" and (witness if key == "usedAttack" else bound and term.get("returned"))
                rows.append((identity, label, field.get("value") if known else None,
                             _L('客户端实测') if known else _L('缺少读取证据'), _L('计算实例与读取路径关联')))
            for phase, title in (("before", _L('进入基础项函数')), ("after", _L('基础项函数返回'))):
                inputs = term.get(phase) or {}
                attack = inputs.get("attack") or {}
                rows.append((title, _L('聚合攻击力'), attack.get("value"), _L('本地属性观测'), identity))
                for name in ("AtkBase", "AtkUp", "AtkAdd", "OnlineAtkRatio"):
                    values = inputs.get(name) or {}
                    for part, caption in (("base", _L('基础值')), ("current", _L('当前值'))):
                        field = values.get(part) or {}
                        rows.append((title, f"{name} · {caption}", field.get("value"),
                                     _L('本地属性观测'), _L('服务器同期值未确认') if name == "OnlineAtkRatio" else identity))
        self.table(_L('客户端公式取值证据'), [_L('阶段／对象'), _L('字段'), _L('值'), _L('来源'), _L('依据')], rows,
                   _L('这里展示客户端实际函数调用。基础项返回值不是服务器最终伤害；属性写入与面板包含关系仍分别判断。'))
