# 队伍模拟「直接输入」模式：步骤提示、假设与限制的文本（代码 -> _L/_LF 文本）。
"""Note texts of the team simulator's custom-cycle mode.

``team_simulation_explanation.note_text`` falls back to ``NOTES`` for codes starting with ``custom_`` (the step
notes of ``CustomStepTrace.notes`` and the custom assumptions / limits).  Texts are built when called, so they
follow the active language and carry provenance for a live language switch.  Character ids become Chinese names
and state names stay Chinese; the display layer translates them.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from typing import Mapping

from src.services import team_simulation_explanation as tx


def _name(args: tuple, names: Mapping | None, i: int = 0) -> str:
    return tx._name(args[i] if len(args) > i else "?", names)


def _state_name(args: tuple, i: int = 0) -> str:
    """Display name of a transformation state from (code, name_zh) note arguments."""
    return tx.form_name_text(str(args[i]) if len(args) > i else "", str(args[i + 1]) if len(args) > i + 1 else "")


def _start_gauge_text(args: tuple, names: Mapping | None) -> str:
    """"A 100 · B 40" from (character_id, value, character_id, value ...)."""
    out = None
    for i in range(0, len(args) - 1, 2):
        piece = tx._name(args[i], names) + f" {tx._num(args, i + 1):.0f}"
        out = piece if out is None else out + " · " + piece
    return out or ""


NOTES = {
    # step notes
    tx.NOTE_CUSTOM_IMPLICIT_SWAP: lambda a, n: _L('未写登场方式，按普通切换处理'),
    tx.NOTE_CUSTOM_OPENER: lambda a, n: _L('开场第一步：没有切出队员，不触发环合反应'),
    tx.NOTE_CUSTOM_SUPPORT_NO_REACTION: lambda a, n: _L('属性相同或不相邻：援护技照常释放，但不触发环合反应（实战中不会出援护技）'),
    tx.NOTE_CUSTOM_GAUGE_SHORT: lambda a, n: _LF('环合值不足（{0:.0f}/100），仍按输入触发').format(tx._num(a, 0)),
    tx.NOTE_CUSTOM_DOWNGRADED_GAUGE: lambda a, n: _LF('环合值不足（{0:.0f}/100），改为普通切换').format(tx._num(a, 0)),
    tx.NOTE_CUSTOM_DOWNGRADED_ELEMENT: lambda a, n: _L('属性相同或不相邻，改为普通切换'),
    tx.NOTE_CUSTOM_ENTRY_SKIPPED: lambda a, n: _LF('{0} 已在场上，跳过登场步骤').format(_name(a, n)),
    tx.NOTE_CUSTOM_CD_NOT_READY: lambda a, n: _LF('冷却未结束（还差 {0:.1f} 秒）').format(tx._num(a, 0)),
    tx.NOTE_CUSTOM_CD_WAITED: lambda a, n: _LF('等待冷却 {0:.1f} 秒后使用').format(tx._num(a, 0)),
    tx.NOTE_CUSTOM_CLOCK_WAITED: lambda a, n: _LF('等待时计 {0:.1f} 秒后使用').format(tx._num(a, 0)),
    tx.NOTE_CUSTOM_CLOCK_SHORT: lambda a, n: _LF('时计不足（{0:.0f}/{1:.0f}，还差 {2:.1f} 秒）').format(
        tx._num(a, 0), tx._num(a, 1), tx._num(a, 2)),
    tx.NOTE_CUSTOM_ENERGY_SHORT: lambda a, n: _LF('终结能量不足（{0:.0f}/{1:.0f}）').format(tx._num(a, 0), tx._num(a, 1)),
    tx.NOTE_CUSTOM_NO_ANIMATION: lambda a, n: _L('缺少动画数据，未计伤害'),
    tx.NOTE_CUSTOM_STATE_ENTERED: lambda a, n: _LF('进入「{0}」').format(_state_name(a)),
    tx.NOTE_CUSTOM_STATE_EXPIRED: lambda a, n: _LF('「{0}」已结束，按普通状态的动作计算').format(_state_name(a)),
    tx.NOTE_CUSTOM_STATE_INACTIVE: lambda a, n: _LF('不在「{0}」中却使用了该形态的动作').format(_state_name(a)),
    tx.NOTE_CUSTOM_STATE_OVERRUN: lambda a, n: _LF('动作结束时已超出「{0}」{1:.1f} 秒').format(
        _state_name(a), tx._num(a, 2)),
    tx.NOTE_CUSTOM_STATE_WINDOW: lambda a, n: _LF('「{0}」开始后 {1:.1f} 秒使用，不在可用时间 {2}–{3} 秒内').format(
        _state_name(a), tx._num(a, 2), f"{tx._num(a, 3):g}", f"{tx._num(a, 4):g}"),
    tx.NOTE_CUSTOM_ENERGY_SKIPPED: lambda a, n: _LF('终结能量不足（{0:.0f}/{1:.0f}），跳过').format(
        tx._num(a, 0), tx._num(a, 1)),
    tx.NOTE_CUSTOM_CD_SKIPPED: lambda a, n: _LF('冷却还差 {0:.1f} 秒，超过最长等待，跳过').format(tx._num(a, 0)),
    # D3 (strict, team): not ready -> swap out at once
    tx.NOTE_CUSTOM_SWAP_OUT: lambda a, n: tx.swap_out_text(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                                                           tx._num(a, 2), tx._num(a, 3), tx._num(a, 4)),
    tx.NOTE_CUSTOM_SWAP_DROPPED: lambda a, n: _L('已提前切换，未执行'),
    tx.NOTE_CUSTOM_ALL_BLOCKED: lambda a, n: _LF('所有队员都未就绪：等待 {0:.1f} 秒（{1} 最早就绪）').format(
        tx._num(a, 0), _name(a, n, 1)),
    tx.NOTE_CUSTOM_SHORT_WAIT: lambda a, n: _LF('等待冷却 {0:.2f} 秒后使用（< {1:.1f} 秒，不切换）').format(
        tx._num(a, 0), tx._num(a, 1, tx._swap_min_wait_s())),
    tx.ASSUME_CUSTOM_STRICT_SWAP: lambda a, n: _LF('严格检查：技能未就绪或终结能量不足时立即切换到后面输入的下一名队员（{0} 次），该队员这一段其余输入不执行；冷却还差不到 {4:.1f} 秒、后面没有其他队员或所有队员都未就绪时等待冷却（共 {1:.1f} 秒），终结能量不足时跳过（{2} 次），超过最长等待时跳过（{3} 次）').format(
        int(tx._num(a, 0)), tx._num(a, 1), int(tx._num(a, 2)), int(tx._num(a, 3)), tx._num(a, 4, tx._swap_min_wait_s())),
    tx.ASSUME_CUSTOM_STRICT: lambda a, n: _LF('严格检查：冷却未结束时等待（共 {0:.1f} 秒），终结能量不足时跳过极轨终结（{1} 次），超过最长等待时跳过（{2} 次）').format(
        tx._num(a, 0), int(tx._num(a, 1)), int(tx._num(a, 2))),
    # assumptions
    tx.ASSUME_CUSTOM_SEQUENCE: lambda a, n: _LF('按用户直接输入的循环行动（重复 {0} 次）').format(int(tx._num(a, 0, 1))),
    tx.ASSUME_CUSTOM_AS_TYPED: lambda a, n: _L('援护技按输入登场，不受环合值限制（不足时仅警告）'),
    tx.ASSUME_CUSTOM_CHECK: lambda a, n: _L('环合值满 100 且属性相邻时才以援护技登场，否则改为普通切换'),
    tx.ASSUME_CUSTOM_START_GAUGE: lambda a, n: _LF('开始时环合值：{0}').format(_start_gauge_text(a, n)),
    tx.ASSUME_CUSTOM_CD_WARN: lambda a, n: _L('冷却与能量只检查填写了数值的项目，未就绪时仅警告'),
    tx.ASSUME_CUSTOM_CD_WAIT: lambda a, n: _LF('冷却未结束时自动插入等待（共 {0:.1f} 秒）').format(tx._num(a, 0)),
    tx.ASSUME_CUSTOM_CD_OFF: lambda a, n: _L('不检查冷却与能量'),
    tx.ASSUME_CUSTOM_BUFF_OFF: lambda a, n: _LF('已关闭 {0} 个队伍 Buff').format(int(tx._num(a, 0))),
    tx.ASSUME_CUSTOM_MANUAL_BUFF: lambda a, n: _LF('已加入 {0} 个手动 Buff').format(int(tx._num(a, 0))),
    tx.ASSUME_CUSTOM_TARGET: lambda a, n: _LF('敌人 {0} 级、抗性 {1:.0%}、防御降低 {2:.0%}、易伤 {3:.0%}').format(
        int(tx._num(a, 0, 80)), tx._num(a, 1), tx._num(a, 2), tx._num(a, 3)),
    tx.ASSUME_CUSTOM_TARGET_KIND: lambda a, n: _LF('敌人：{0}，{1} 名（觉醒效果的首领 / 单体条件按此判断）').format(
        _L('首领') if int(tx._num(a, 0)) else _L('普通敌人'), int(tx._num(a, 1, 1))),
    # limits
    tx.LIMIT_CUSTOM_CD_DATA: lambda a, n: _L('大多数角色的冷却与能量消耗不在游戏数据中，需手动填写；未填写的不检查'),
    tx.LIMIT_CUSTOM_ENERGY_MODEL: lambda a, n: _L('终结能量只按命中的充能量累计，极限闪避、弹反、盈蓄等来源未计入'),
    tx.LIMIT_CUSTOM_CHAIN_RESET: lambda a, n: _L('普通攻击连段在使用其他动作或切换后从第 1 段重新开始（推断）'),
    tx.LIMIT_CUSTOM_SWAP_TIME: lambda a, n: _L('普通切换不占用时间'),
    tx.LIMIT_CUSTOM_FORM_FREE: lambda a, n: _L('形态内的动作不按形态时间裁剪，超时只提示'),
    tx.LIMIT_CUSTOM_SUPPORT_FREE: lambda a, n: _L('「按输入执行」下，环合值不足或属性不相邻时也会释放援护技，结果可能高于实战'),
    tx.LIMIT_CUSTOM_OWN_RESOURCE: lambda a, n: _LF('{0} 使用自身资源，不检查终结能量').format(_name(a, n)),
    tx.LIMIT_CUSTOM_CD_BLANK: lambda a, n: _LF('{0} 多次使用了 {1}，但未填写冷却时间，未检查是否就绪（结果可能偏高）').format(
        _name(a, n), str(a[1]) if len(a) > 1 else ""),
}

NOTE_CODES = tuple(NOTES)
