# 展示战报原始角色配置与单一修改副本的切换状态。
"""Battle build edit control card."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from src.app.theme import themed_style

class BattleBuildSnapshotControl(QWidget):
    edit_requested = Signal()
    activation_requested = Signal(bool)
    role_page_import_requested = Signal()
    environment_requested = Signal()
    puka_overrides_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel(_L('等待战报角色配置'))
        self.status.hide()
        self.edit_button = QPushButton(_L('编辑角色'))
        self.edit_button.clicked.connect(self.edit_requested)
        self.edit_button.setEnabled(False)
        layout.addWidget(self.edit_button)
        # 本场冻结的噗卡特训等级：常显短标签，完整说明在其提示与按钮提示中。
        self.puka_label = QLabel("")
        self.puka_label.setObjectName("battleBuildPukaLevel")
        self.puka_label.setStyleSheet(themed_style("color:#8b949e;font-size:12px"))
        self.puka_label.hide()
        layout.addWidget(self.puka_label)
        # 账号开关（决定 U2）：冻结 Lv>0 的战报才显示；与边际页的勾选框是同一设置。
        self.puka_check = QCheckBox(_L('全部计入特训'))
        self.puka_check.setObjectName("battleBuildPukaOverrides")
        self.puka_check.setToolTip(_L('账号设置，适用于所有冻结了噗卡特训等级的战报：原生核心重算修改副本、边际对比候选与「与我的角色对比」时，把防御力、生命值、暴击率、环合强度与倾陷强度的特训份额经「边际手工调整」补回。关闭后只保留攻击力与暴击伤害份额（未改动的候选约 −2.4%）。'))
        self.puka_check.setChecked(True)
        self.puka_check.hide()
        self.puka_check.toggled.connect(self.puka_overrides_toggled)
        layout.addWidget(self.puka_check)
        self.import_button = QPushButton(_L('从角色页同步'))
        self.import_button.setToolTip(
            _L('用当前角色页养成覆盖本场修改副本；保留副本已选边际空幕/驱动。')
        )
        self.import_button.clicked.connect(self.role_page_import_requested)
        self.import_button.setEnabled(False)
        self.import_button.hide()
        self.environment_button = QPushButton(_L('环境配置 · 未配置'))
        self.environment_button.setToolTip(
            _L('确认战斗模式、对象、难度、争锋加成与魔女赐福。')
        )
        self.environment_button.clicked.connect(self.environment_requested)
        self.environment_button.setEnabled(False)
        self.environment_button.hide()
        self.activation_button = QPushButton(_L('恢复原始快照'))
        self.activation_button.clicked.connect(self._request_activation)
        self.activation_button.setEnabled(False)
        self.activation_button.hide()

    def set_state(
        self,
        *,
        has_edit: bool,
        active: bool,
        available: bool = True,
        puka_training_level: int = 0,
        puka_training_source: str = "",
        puka_native_overrides: bool = True,
    ) -> None:
        self.edit_button.setEnabled(available)
        self.import_button.setEnabled(available)
        self.activation_button.setEnabled(available and has_edit)
        if not available:
            text = _L('当前记录没有可编辑的角色配置快照。')
        elif not has_edit:
            text = _L('当前使用原始快照；首次编辑会复制本场原始冻结配置。')
        elif active:
            text = _L('当前使用修改副本；它只用于逐击重放和边际计算，主页面实测数据不变。')
        else:
            text = _L('当前已恢复原始快照；修改副本仍保留，可继续编辑或重新启用。')
        level = max(0, int(puka_training_level or 0))
        partial = False
        if available:
            # 本场冻结的噗卡特训等级；功能上线前的战报没有记录（按 Lv 0，不追加当前账号等级）。
            if puka_training_source == "pre_feature":
                short = _L('噗卡特训：未记录（Lv.0）')
                text = text + "\n" + _L('本战报未记录噗卡特训（按 Lv.0 计算，不追加当前账号等级）。')
            else:
                short = _LF('噗卡特训 Lv.{0}').format(level)
                text = text + "\n" + _LF('本战报冻结的噗卡特训等级：Lv.{0}').format(level)
            if level <= 0:
                # 1.4 之后录制、但当时未录入等级的战报：游戏实测已含特训，重构面板会偏低。
                text = text + "\n" + _L('若录制时游戏内已有特训等级，重构面板会低于实测。')
            edit_active = bool(has_edit and active and level > 0)
            partial = edit_active and not puka_native_overrides
            if partial:
                text = text + "\n" + _L('修改副本启用时由原生核心重算面板，噗卡特训只计攻击力与暴击伤害部分，逐击与边际结果可能偏低。')
                short = "⚠ " + short
            elif edit_active:
                text = text + "\n" + _L('修改副本启用时由原生核心重算面板：噗卡特训的防御力、生命值、暴击率、环合强度与倾陷强度经「边际手工调整」补回，来源明细会出现该行，量化状态可能为「部分」。')
            self.puka_label.setText(short)
            self.puka_label.setToolTip(text)
            self.puka_label.setStyleSheet(themed_style("color:#d29922;font-size:12px" if partial
                                                       else "color:#8b949e;font-size:12px"))
        self.puka_label.setVisible(bool(available))
        self.puka_check.blockSignals(True)
        self.puka_check.setChecked(bool(puka_native_overrides))
        self.puka_check.blockSignals(False)
        self.puka_check.setVisible(bool(available and level > 0))
        self.status.setText(text)
        self.edit_button.setToolTip(text)
        self.activation_button.setText(
            _L('恢复原始快照') if active else _L('使用修改副本')
        )

    def set_environment_state(self, *, status: str, summary: str = "") -> None:
        labels = {
            "configured": _L('已配置'),
            "inferred": _L('已推理'),
            "unconfigured": _L('未配置'),
        }
        label = labels.get(status, _L('未配置'))
        self.environment_button.setText(_LF('环境配置 · {0}').format((label)))
        self.environment_button.setToolTip(
            summary or _L('确认战斗模式、对象、难度、争锋加成与魔女赐福。')
        )

    def _request_activation(self) -> None:
        self.activation_requested.emit(
            self.activation_button.text() == _L('使用修改副本')
        )
