# 汇总扫描后管理动作结果。
"""Text projection for completed scan state-management results."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Mapping
from typing import Any


def append_state_mismatch_summary(summary: str, stats: Mapping[str, Any]) -> str:
    """Append the non-destructive state mismatch notice when rows were skipped."""

    mismatch_count = int(stats.get("post_action_state_mismatch_count", 0) or 0)
    if not mismatch_count:
        return summary
    indexes = tuple(stats.get("post_action_state_mismatch_indexes", ()) or ())
    index_text = "、".join(_LF('第 {0} 件').format((int(index))) for index in indexes)
    return (
        (_LF('{0}\n状态与扫描计划不一致，已跳过 {1} 件且未执行操作：').format((summary), (mismatch_count)) + f"{index_text}。")
    )
