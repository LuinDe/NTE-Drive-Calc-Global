# 汇总扫描后管理动作结果。
"""Text projection for completed scan state-management results."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.app.window_geometry import fit_dialog_to_available_screen


def append_scan_post_action_summary(summary: str, stats: Mapping[str, Any]) -> str:
    """Render the existing management summary and append any skipped-row notice."""

    if not stats.get("post_actions_enabled"):
        return summary
    planned = _L('计划') if stats.get("post_action_issue_count") else ""
    summary += (
        (_L('\n扫描后管理：') + _LF('参与计算 {0} 件，').format((int(stats.get('post_action_candidate_count', 0) or 0))) + _LF('目标变更 {0} 个，').format((int(stats.get('post_action_target_count', 0) or 0))) + _LF('已处理 {0} 个。').format((int(stats.get('post_action_applied_count', 0) or 0))) + _LF('\n{0}弃置 {1} 个，').format((planned), (int(stats.get('discard_set_count', 0) or 0))) + _LF('取消弃置 {0} 个；').format((int(stats.get('discard_clear_count', 0) or 0))) + _LF('锁定 {0} 个，').format((int(stats.get('lock_set_count', 0) or 0))) + _LF('取消锁定 {0} 个。').format((int(stats.get('lock_clear_count', 0) or 0))))
    )
    filtered_parts = []
    for key, label in (
        ("post_action_quality_filtered_count", _L('品质范围过滤')),
        ("post_action_type_filtered_count", _L('处理类别过滤')),
        ("post_action_type_range_filtered_count", _L('类型范围过滤')),
    ):
        count = int(stats.get(key, 0) or 0)
        if count:
            filtered_parts.append(_LF('{0} {1} 件').format((label), (count)))
    if filtered_parts:
        summary += "\n" + "，".join(filtered_parts) + "。"
    return append_post_action_issue_summary(summary, stats)


def append_post_action_issue_summary(summary: str, stats: Mapping[str, Any]) -> str:
    """Keep the notice compact; individual scan indexes belong in details."""

    issue_count = int(stats.get("post_action_issue_count", 0) or 0)
    if not issue_count:
        return summary
    applied = int(stats.get("post_action_applied_count", 0) or 0)
    return (
        (_LF('{0}\n状态管理已结束：成功 {1} 件，跳过 {2} 件。').format((summary), (applied), (issue_count)) + _L('跳过的装备未执行状态修改，请查看详情。'))
    )


def post_action_issue_details(stats: Mapping[str, Any]) -> str:
    """Describe only the frozen plan and the pre-action failure."""

    actions = {"locked": _L('锁定'), "discarded": _L('弃置'), "normal": _L('恢复普通状态')}
    reasons = {
        "identity_mismatch": _L('详情与扫描截图不一致'),
        "state_mismatch": _L('当前状态与计划不一致'),
    }
    return "\n".join(
        (_LF('第 {0} 件：{1}，').format((int(issue['index'])), (reasons.get(issue['reason'], '操作前校验未通过'))) + _LF('已跳过原计划的{0}操作。').format((actions.get(issue['target_state'], '状态修改'))))
        for issue in stats.get("post_action_issues", ()) or ()
    )


def show_scan_completion(
    parent: QWidget | None, title: str, summary: str, stats: Mapping[str, Any],
) -> None:
    """Use the existing completion notice, with one warning when rows were skipped."""

    if not int(stats.get("post_action_issue_count", 0) or 0):
        QMessageBox.information(parent, title, summary)
        return
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(summary)
    box.setDetailedText(post_action_issue_details(stats))
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    box.adjustSize()
    fit_dialog_to_available_screen(box)
    QApplication.beep()
    box.exec()
