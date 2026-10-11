# 统一计算失败结果和日志的一行说明，不参与配装判断。
from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Mapping
from typing import Any


def allocation_failure_text(plan: Mapping[str, Any] | None) -> str:
    """Render existing solver evidence without recomputing any constraint."""
    plan = plan or {}
    reason = " ".join(str(
        plan.get("reason") or _L('本次未生成可保存方案，原因待诊断')
    ).split())
    progress = plan.get("group_search") or {}
    if plan.get("search_status") in {
        "bounded_unproven", "budget_exhausted", "candidate_truncated",
    } and progress.get("members", 0) > 1 and progress.get("completed", 0) > 0:
        reason += _LF('（同级组已完成 {0}/{1} 人）').format((progress['completed']), (progress['members']))
    return reason
