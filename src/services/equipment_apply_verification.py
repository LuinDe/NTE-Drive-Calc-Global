# 将极速装配稳定快照的差异诊断集中在纯函数中，供单角色与批量流程复用。
"""Pure verification helpers for equipment-apply snapshots."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from typing import Any


def plan_mismatch(
    *,
    items: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    core_assignment: dict[str, Any] | None,
    character_id: int,
    character_uid: dict[str, int],
    ignore_module_placement: bool = False,
) -> str | None:
    """返回完整方案与稳定快照的首个具体差异。"""

    expected_uids = {
        (assignment["uid_serial"], assignment["uid_slot"])
        for assignment in modules
    }
    if core_assignment is not None:
        expected_uids.add((
            core_assignment["uid_serial"],
            core_assignment["uid_slot"],
        ))

    mismatch = module_plan_mismatch(
        items=items,
        modules=modules,
        character_id=character_id,
        character_uid=character_uid,
        ignore_placement=ignore_module_placement,
    )
    if mismatch is not None:
        return mismatch

    if core_assignment is not None:
        core_pair = (core_assignment["uid_serial"], core_assignment["uid_slot"])
        by_uid = {(item["uid_serial"], item["uid_slot"]): item for item in items}
        verified_core = by_uid.get(core_pair)
        if verified_core is None:
            return _LF('卡带 UID {0} 不在复核快照中').format((core_pair))
        if not verified_core["equipped"]:
            return _LF('卡带 UID {0} 未装备').format((core_pair))
        if verified_core["equipped_character_id"] != character_id:
            return (
                (_LF('卡带 UID {0} 装到了角色 ').format((core_pair)) + _LF('{0}，目标角色为 {1}').format((verified_core['equipped_character_id']), (character_id)))
            )
        if verified_core["equipped_character_uid"] != character_uid:
            return (
                (_LF('卡带 UID {0} 的角色实例不一致：').format((core_pair)) + _LF('实际 {0}，目标 {1}').format((verified_core['equipped_character_uid']), (character_uid)))
            )

    actual_uids = {
        (item["uid_serial"], item["uid_slot"])
        for item in items
        if item["equipped"]
        and item["equipped_character_uid"] == character_uid
        and item["equipped_character_id"] == character_id
    }
    if actual_uids != expected_uids:
        missing = sorted(expected_uids - actual_uids)
        unexpected = sorted(actual_uids - expected_uids)
        return (
            (_L('角色装备集合与方案不一致：') + _LF('缺少 {0}，额外 {1}').format((missing or '无'), (unexpected or '无')))
        )
    return None


def scoped_plan_mismatch(
    *,
    items: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    core_assignment: dict[str, Any] | None,
    character_id: int,
    character_uid: dict[str, int],
) -> str | None:
    """Check only whether planned items are equipped in a residual packet.

    Residual packets do not reliably carry target placement or owner fields.
    They are therefore suitable for detecting a missing equipment operation,
    not for asserting an exact role/grid loadout.
    """

    by_uid = {(item["uid_serial"], item["uid_slot"]): item for item in items}
    assignments = [*modules]
    if core_assignment is not None:
        assignments.append(core_assignment)
    for assignment in assignments:
        uid_pair = (assignment["uid_serial"], assignment["uid_slot"])
        item = by_uid.get(uid_pair)
        if item is None:
            continue
        if not item["equipped"]:
            return _LF('装备 UID {0} 未装备').format((uid_pair))
    return None


def module_plan_mismatch(
    *,
    items: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    character_id: int,
    character_uid: dict[str, int],
    allow_missing_placement: bool = False,
    ignore_placement: bool = False,
) -> str | None:
    """复核仅含驱动的方案，不要求更改角色当前卡带。"""

    by_uid = {(item["uid_serial"], item["uid_slot"]): item for item in items}
    for assignment in modules:
        uid_pair = (assignment["uid_serial"], assignment["uid_slot"])
        item = by_uid.get(uid_pair)
        expected_placement = {
            "row": assignment["target_row"],
            "column": assignment["target_column"],
        }
        if item is None:
            return _LF('驱动 UID {0} 不在复核快照中').format((uid_pair))
        if not item["equipped"]:
            return _LF('驱动 UID {0} 未装备').format((uid_pair))
        if item["equipped_character_id"] != character_id:
            return (
                (_LF('驱动 UID {0} 装到了角色 {1}，').format((uid_pair), (item['equipped_character_id'])) + _LF('目标角色为 {0}').format((character_id)))
            )
        if item["equipped_character_uid"] != character_uid:
            return (
                (_LF('驱动 UID {0} 的角色实例不一致：').format((uid_pair)) + _LF('实际 {0}，目标 {1}').format((item['equipped_character_uid']), (character_uid)))
            )
        if ignore_placement:
            continue
        actual_placement = item["equipped_placement"]
        if actual_placement is None and allow_missing_placement:
            # Equipment residual packets reliably identify the equipped item
            # and owner, but may omit grid placement.  Treat that as a
            # successful scoped state observation rather than a false repair.
            continue
        if actual_placement != expected_placement:
            return (
                (_LF('驱动 UID {0} 的位置不一致：').format((uid_pair)) + _LF('实际 {0}，目标 {1}').format((actual_placement), (expected_placement)))
            )
    return None
