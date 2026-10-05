# 汇总极速装配完成结果与提示。
"""Compact, actionable summaries for the fast-equipment completion dialog."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Mapping, Sequence
from typing import Any


def build_fast_apply_completion_summary(
    applied: Sequence[Mapping[str, Any]],
    *,
    mismatch_role_names: frozenset[str] = frozenset(),
) -> tuple[str, str]:
    """Return dispatched equipment counts without claiming fragment verification.

    Equipment residual events are not a complete inventory view.  They remain
    useful for internal retry diagnostics, but presenting their absence or a
    partial match as a player-visible loadout result would be misleading.
    """

    del mismatch_role_names
    last_attempt = max((int(row.get("attempt_count") or 1) for row in applied), default=1)

    summary = _LF('已下发 {0} 个角色的配装').format((len(applied)))
    if last_attempt > 1:
        summary += _LF('（已进行至第 {0} 轮装配）').format((last_attempt))
    lines = []
    for row in applied:
        role_name = str(row.get("role_name") or _L('未知角色'))
        module_count = row.get("module_count")
        if module_count is None:
            detail = _L('已下发')
        else:
            detail = _LF('{0} 个驱动').format((int(module_count)))
            if row.get("core_count"):
                detail += _L(' + 1 个核心')
        lines.append(f"• {role_name}：{detail}")
    return summary, "\n".join(lines)
