# 队伍模拟：觉醒（돌파）效果规则登记处。各角色组只修改自己的模块（g0.py…g3.py），不修改共享文件。
"""Global awakening-node rules (Korean UI "돌파"): one registry, one module per character group.

Group modules (each owns six characters; it edits only its own file):

======  ==========================================
``g0``  1003 1004 1008 1010 1019 1020
``g1``  1021 1023 1025 1033 1036 1039
``g2``  1042 1051 1052 1054 1055 1057
``g3``  1070 1071 1072 1073 1075 1076
======  ==========================================

Recipe (inside ``gN.py``)::

    from src.services.awakening_node_rules.core import RuleSet, PostIncrement, SOURCE_KIND

    RULES = RuleSet("g1", (1021, 1023, 1025, 1033, 1036, 1039))      # already in the stub

    RULES.node(1021, "Effect4", category="damage", bucket="now", confidence="high",
               assumption={"ko": "…", "en": "…"})

    @RULES.hook("prepare", 1021, nodes=("Effect4",))
    def _edgar_prepare(ctx):
        return {"bonus": ...}                     # DB curves via ctx.con / ctx.static (read only)

    @RULES.hook("evidence", 1021, nodes=("Effect4",))
    def _edgar_e4(ctx, run, evidence):
        ...                                       # return the patched evidence

The framework (``core``) decides when a hook runs (the member is in the team and one of ``nodes`` is selected /
reached; ``nodes=()`` = always for that character) and wires every hook kind into the team simulator, the custom
cycle and the efficiency-table path (``solo_session``).  With no registration the simulator is byte-identical to the
selection model alone.  ``NTE_TEAM_AWAKENING_RULES=off`` switches every group off (regression baseline).

This package is inside the efficiency seeds' engine fingerprint (it is imported from team_simulation_service): any
change here makes the arc / awakening seeds stale (regenerate them with their generators).
"""
from __future__ import annotations

from src.services.awakening_node_rules.core import (  # noqa: F401  (re-exported API)
    BUCKETS,
    CATEGORIES,
    HOOK_KINDS,
    MODES,
    NAME_PREFIX,
    REGISTRY,
    SOURCE_KIND,
    SUPPLEMENT_CONFIDENCE,
    GateEvent,
    HookCtx,
    LayoutHooks,
    Member,
    NodeInfo,
    PlacedAction,
    PostIncrement,
    Prepared,
    Registration,
    ResourceEvent,
    ResourceHooks,
    RuleSet,
    RunHooks,
    RunInfo,
    SwapEvent,
    all_node_info,
    for_selections,
    group_enabled,
    node_info,
    nodes_of,
    note_text,
    owner_of,
    prepare,
    registrations,
    rulesets,
)
from src.services.awakening_node_rules import g0, g1, g2, g3  # noqa: F401,E402  (group modules register on import)

GROUPS = {"g0": g0, "g1": g1, "g2": g2, "g3": g3}
