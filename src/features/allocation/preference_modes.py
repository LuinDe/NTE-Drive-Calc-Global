# 判断角色自选配置适用的分配模式。
"""Mode guards for per-role equipment preference options."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF


def role_preference_mode_error(strategy: str, tape_main_filters=None, crit_priority_modes=None, crit_rate_caps=None) -> str | None:
    if strategy in ("role_priority", "update_mode"):
        return None
    return _L('未知分配策略。')
