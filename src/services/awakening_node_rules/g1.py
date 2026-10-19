# 队伍模拟：觉醒（돌파）效果规则——角色组 g1（埃德嘉 白藏 哈索尔 阿德勒 残虹 法帝娅）。只在本文件登记本组角色的规则。
"""Awakening-node rules of group g1: 1021 Edgar, 1023 Cang (白藏), 1025 Hathor, 1033 Adler, 1036 Zankou, 1039 Fadia.

Source: ``awaken/specs/group_1.json`` after the 10-18 adversarial review (``group_1_review.md``); the hooks follow the
measured prototype ``_g1review/proto_rv.py`` with the reviewed switches (Cang ② stacking, Hathor gains from the
approved steps and blocked inside 紧急派送, Adler resonance 6 from the shield notify).  Numbers come from the static
DB in the ``prepare`` hooks (``combat_curve_point``, ``buff_definition``, ``buff_trigger_effect``,
``combat_montage_notify``) or from the simulator's own form rule (``team_form_actions.FORMS``); values that exist only
in a skill description are the ``TEXT_*`` constants below.  A value the DB lacks switches its rule off (no guess).

Hooks (``core`` explains the kinds):

=========  ===============  ==================================================================================
Edgar      intervals        ④ E hits DamageUpGeneralBase; ⑥ team DefUp over the Q field (10 s + 1 s per key)
Cang       dot_rows (base)  「判予秋」 field ticks every 2 s while the field lives (12 s, ⑤ 16 s)  [D-2]
           intervals        ② word AtkUp stacks (AggregateBySource, limit 4); ⑥ CritBase / 共鸣6 team AtkUp
Hathor     intervals        紧急派送 windows: ⑥ CritDamageBase, 共鸣6 DefIgnore; ④ Cyclone casts CritBase;
                            ③ non-boss DamageUpGeneralBase; ⑤ DamageUpGeneralBase per 闪送之力 gained (①② gains)
Adler      intervals        共鸣6 team DamageUpIncantationBase from the shield (8 s, ⑥ 12 s); (base) analysis stash
           evidence (base)  「业」: basics +1 / aim +2 / ① Q +20, the next E consumes them (2 %, ② 3 % per stack)
Zankou     intervals        ⑥ the 「灭」 final hit +12 % per DoT layer (max 240 %)
           evidence         ② (+④) 蓄焰 from the simulator's 浊燃 / 覆纹 reactions: next Q x2.5 final
Fadia      intervals        ⑤ CritBase over the 敌神者 chase hits (replaces the engine's Q-begin window)
=========  ===============  ==================================================================================

Base-kit rules (``nodes=()``) also run at awakening 0: Cang's field ticks (A0 rises, user decision D-2 recommended
default) and Adler's 「业」 from basics / aim (no basic attack in the approved rotation: A0 unchanged there).
"""
from __future__ import annotations

import dataclasses
import json

from src.services.awakening_node_rules.core import NAME_PREFIX, SOURCE_KIND, SUPPLEMENT_CONFIDENCE, RuleSet

RULES = RuleSet("g1", (1021, 1023, 1025, 1033, 1036, 1039))

EDGAR, CANG, HATHOR, ADLER, ZANKOU, FADIA = 1021, 1023, 1025, 1033, 1036, 1039
GROUP = "g1"

# values that exist only in the skill descriptions (no curve in the DB)
TEXT_EDGAR_MAX_KEYS = 3          # GA_Edgar_Passive_2: at most three 真理之匙 (upstream _edgar_q_field uses the same cap)

# switches of the reviewed defaults (group_1.md §5); the alternatives are listed in the group report
CANG_FIELD_TICKS = True          # D-2: lay the missing field ticks (base kit); False = stage 1 (windows only)
HATHOR_PLUS2_AFTER_HOLD = True   # D-8: the E's +2 闪送之力 also after the hold E
HATHOR_BLOCK_IN_DISPATCH = True  # review E2/E3: no 闪送之力 gained inside 紧急派送
HATHOR_E4_PER_SEGMENT = True     # D-10: each approved Cyclone segment is one cast
ZANKOU_E2_SKIP_ENGINE = True     # a Q hit the engine already gave the 蓄焰 multiplier is not multiplied again

_AGGREGATE_BY_SOURCE = "EGameplayEffectStackingType::AggregateBySource"


# ── static data ──────────────────────────────────────────────────────────────

class _Db:
    """Read-only lookups in the static DB (``ctx.con``); a missing value is None and recorded in ``missing``."""

    def __init__(self, con) -> None:
        self.con = con
        self.missing: list[str] = []

    def _one(self, sql: str, args: tuple):
        try:
            return self.con.execute(sql, args).fetchone()
        except Exception:
            return None

    def curve(self, table: str, row: str) -> float | None:
        got = self._one("SELECT value FROM combat_curve_point WHERE curve_id = ? AND curve_table_asset_path LIKE ? "
                        "ORDER BY curve_table_asset_path, ordinal LIMIT 1", (row, "%/" + table))
        if got is None or got[0] is None:
            self.missing.append(f"{table}:{row}")
            return None
        return float(got[0])

    def buff(self, name: str) -> tuple | None:
        """(stacking type, stack limit, duration magnitude json) of a buff / gameplay effect."""
        got = self._one("SELECT stacking_type, stack_limit_count, duration_magnitude_json FROM buff_definition "
                        "WHERE asset_path LIKE ? ORDER BY asset_path LIMIT 1", ("%/" + name,))
        if got is None:
            self.missing.append(f"buff_definition:{name}")
        return got

    def stack_limit(self, name: str) -> int | None:
        got = self.buff(name)
        return int(got[1]) if got is not None and got[1] is not None else None

    def trigger_stacks(self, name: str, target: str) -> int | None:
        """StackCount a buff's trigger effect adds to ``target``."""
        got = self._one("SELECT stack_count FROM buff_trigger_effect WHERE asset_path LIKE ? AND "
                        "target_effect_asset_path LIKE ? AND stack_count > 0 ORDER BY asset_path, ordinal LIMIT 1",
                        ("%/" + name, "%/" + target))
        if got is None or got[0] is None:
            self.missing.append(f"buff_trigger_effect:{name}->{target}")
            return None
        return int(got[0])

    def duration_s(self, name: str, table: str) -> float | None:
        """A HasDuration buff's duration: ScalableFloat Value x its curve row (Value alone without a curve)."""
        got = self.buff(name)
        try:
            magnitude = json.loads(got[2])["ScalableFloatMagnitude"]
            value = float(magnitude.get("Value", 1.0))
            row = ((magnitude.get("Curve") or {}).get("RowName") or "None")
        except Exception:
            self.missing.append(f"duration:{name}")
            return None
        if row in ("", "None"):
            return value
        curve = self.curve(table, row)
        return None if curve is None else value * curve

    def notify_s(self, ability: str, selector: str, event_tag: str) -> float | None:
        """Start (montage seconds) of the first notify with ``event_tag`` in the ability's bound montage."""
        got = self._one("SELECT n.start_seconds FROM combat_ability_montage_binding b JOIN combat_montage_notify n "
                        "ON n.asset_path = b.montage_asset_path WHERE b.ability_asset_path LIKE ? AND "
                        "b.selector_key = ? AND n.event_tag = ? ORDER BY n.start_seconds LIMIT 1",
                        ("%/" + ability, selector, event_tag))
        if got is None or got[0] is None:
            self.missing.append(f"notify:{ability}:{selector}:{event_tag}")
            return None
        return float(got[0])


def _us(seconds) -> int:
    return int(round(float(seconds) * 1_000_000))


def _form_start_s(character_id: int) -> float | None:
    """Offset of a form window from its ability start (team_form_actions.FORMS[cid]['start'] = (ability, sel, s))."""
    try:
        from src.services.team_form_actions import FORMS

        return float(FORMS[int(character_id)]["start"][2])
    except Exception:
        return None


# ── analysis helpers (lazy engine imports: the registry import stays engine-free) ──

def _clock():
    from src.services.team_fork_corrections import active_us, active_window_end

    return active_us, active_window_end


def _interval(cid: int, key: str, index: int, start: int, end: int, prop: str, value: float, *, scope: str = "self",
              tags: tuple = (), requirement: str = "", stacking: str = "", limit: int = 1):
    """One supplement buff interval (team_fork_corrections._interval shape).  Identity per (character, key): the
    projection keeps the newest overlapping interval of one asset unless it stacks (``stacking`` / ``limit``)."""
    from src.domain.battle_report import BattleBuffModifierEvidence, BattleInferredBuffInterval

    return BattleInferredBuffInterval(
        interval_id=f"global:awaken:{cid}:{key}:{index}", buff_asset_path=f"global-awakening:{cid}:{key}",
        buff_name=f"{NAME_PREFIX}{cid} {key}", source_effect_definition_id=f"global_awakening:{cid}:{key}",
        source_kind=SOURCE_KIND, source_character_id=cid, source_character_name="", target_scope=scope,
        start_us=int(start), end_us=int(end), stacks=1, duration_policy="HasDuration",
        state_confidence=SUPPLEMENT_CONFIDENCE, value_confidence=SUPPLEMENT_CONFIDENCE,
        inference_basis="Global awakening rule g1 (description + DB values, built from the simulated hits)",
        trigger_event_type="GLOBAL_SUPPLEMENT", stacking_type=stacking, stack_limit_count=int(limit),
        evidence_action_ids=(), evidence_event_ids=(),
        modifiers=(BattleBuffModifierEvidence(
            property_id=prop, modifier_operation="EGameplayModOp::Additive", magnitude_kind=SOURCE_KIND,
            magnitude_value=float(value), calculation_asset_path="", value_confidence=SUPPLEMENT_CONFIDENCE,
            application_requirement_asset_path=requirement, source_require_tags=tuple(tags)),))


def _apply(analysis, add: list, drop: set = frozenset()):
    """New analysis: engine intervals of the ``drop`` sources removed, ``add`` appended (both interval lists)."""
    if not add and not drop:
        return analysis

    def keep(seq):
        return tuple(x for x in (seq or ()) if str(getattr(x, "source_effect_definition_id", "") or "") not in drop)

    return dataclasses.replace(analysis, buff_intervals=keep(analysis.buff_intervals) + tuple(add),
                               timeline_buff_intervals=keep(analysis.timeline_buff_intervals) + tuple(add))


def _hits(analysis) -> list:
    return sorted(analysis.hits, key=lambda h: (h.relative_time_us, h.event_id))


def _actions(analysis) -> list:
    return sorted(analysis.inferred_actions, key=lambda a: a.start_us)


def _stash(run, analysis) -> None:
    """The analysis of the engine call in progress, for this group's evidence hooks (same _run_engine call)."""
    run.scratch[(GROUP, "analysis")] = analysis


def _stashed(run):
    return run.scratch.get((GROUP, "analysis"))


def _steps(run, ability: str):
    """(visit, step) of the layout whose step runs ``ability`` (approved or custom layout, time order)."""
    for visit in getattr(run.layout, "visits", ()) or ():
        for step in getattr(visit, "steps", ()) or ():
            if getattr(step, "ability_id", None) == ability:
                yield visit, step


def _swap_out_after(run, character_id: int, t_us: int) -> int | None:
    """Wall time of the member's first swap-out after ``t_us`` (None in a solo run / without one)."""
    times = [int(s.time_us) for s in getattr(run.layout, "swaps", ()) or ()
             if int(getattr(s, "out_character_id", 0) or 0) == int(character_id) and int(s.time_us) > int(t_us)]
    return min(times) if times else None


# ── 1021 Edgar ───────────────────────────────────────────────────────────────

@RULES.hook("prepare", EDGAR, nodes=("Effect4", "Effect6"))
def _edgar_prepare(ctx):
    db = _Db(ctx.con)
    table = "DT_EdgarEffectFigure"
    return {"e4": db.curve(table, "Buff_Edgar_Star4_SkillDamUP"), "e6": db.curve(table, "Buff_Edgar_Star6_DefUP"),
            "field_s": db.curve(table, "GA_UltraSkill_Duration"),
            "per_key_s": db.curve(table, "GA_UltraSkill_PerKeyAddDuration"), "missing": tuple(db.missing)}


@RULES.hook("intervals", EDGAR, nodes=("Effect4", "Effect6"))
def _edgar_intervals(ctx, run, analysis):
    """④ 狂流 (E) hits +50 % in the damage-bonus zone; ⑥ DEF +15 % to the team over the Q field: from the Q damage
    hit for 10 s + 1 s per 真理之匙 (own E / QTE, with ① teammates' support skills; at most 3) of active time; the
    field stays after Edgar swaps out (D-4, the field actor applies the buff to every equipped character)."""
    data = ctx.data or {}
    _active_us, window_end = _clock()
    end = int(analysis.battle_end_us)
    add = []
    if ctx.member.has("Effect4") and data.get("e4") is not None:
        add.append(_interval(EDGAR, "E4", 0, 0, end, "DamageUpGeneralBase", data["e4"],
                             tags=("State.Damage.Skill", "Ability.GE_Player_Edgar_Skill_Damage")))
    if ctx.member.has("Effect6") and None not in (data.get("e6"), data.get("field_s"), data.get("per_key_s")):
        hits = _hits(analysis)
        keys, index = 0, 0
        teammate_keys = ctx.member.has("Effect1")
        for a in _actions(analysis):
            if a.character_id == EDGAR and a.input_kind in ("E", "QTE"):
                keys = min(TEXT_EDGAR_MAX_KEYS, keys + 1)
            elif a.character_id != EDGAR and a.input_kind == "QTE" and teammate_keys:
                keys = min(TEXT_EDGAR_MAX_KEYS, keys + 1)
            elif a.character_id == EDGAR and a.input_kind == "Q":
                q_hits = [h.relative_time_us for h in hits if h.character_id == EDGAR
                          and h.gameplay_effect_id == "GE_Player_Edgar_UltraSkill_Damage"
                          and h.relative_time_us >= a.start_us]
                start = min(q_hits) if q_hits else a.start_us
                stop = window_end(analysis, start, data["field_s"] + data["per_key_s"] * keys)
                add.append(_interval(EDGAR, "E6", index, start, min(stop, end), "DefUp", data["e6"], scope="team"))
                keys, index = 0, index + 1
    return _apply(analysis, add)


# ── 1023 Cang (白藏) ──────────────────────────────────────────────────────────

CANG_FIELD_HIT = "GE_Player_Cang_UltraSkill2_Damage"     # the Q 展开 hit: the field starts right after it
CANG_TICK_GE = "GE_Player_Cang_UltraSkill_Damage"        # 「判予秋」 field DoT (period 2 s, fixed crit 0.5)
CANG_TICK_LABEL = "判予秋"


@RULES.hook("prepare", CANG)
def _cang_prepare(ctx):
    db = _Db(ctx.con)
    table = "DT_CangEffectFigure"
    word = db.buff("Buff_Cang023_Level2_AtkUP")
    return {"field_s": db.curve(table, "Cang_FieldDuaration"), "field_e5_s": db.curve(table, "Cang_FieldDuaration_Lv5"),
            "period_s": db.curve(table, "GE_Player_Cang_UltraSkill_Damage_period"),
            "e2": db.curve(table, "Buff_Cang023_Level2_AtkUP"), "e2_s": db.curve(table, "Buff_Cang023_Level2_Time"),
            "e2_stacking": str(word[0] or "") if word else "", "e2_limit": int(word[1] or 0) if word else 0,
            "e6": db.curve(table, "Buff_Cang023_Level6_CritAdd"),
            "r6": db.curve(table, "Buff_Cang023_Level6_Extra_TeamAtkUP"), "missing": tuple(db.missing)}


def _cang_field_s(ctx) -> float | None:
    data = ctx.data or {}
    return data.get("field_e5_s") if ctx.member.has("Effect5") else data.get("field_s")


@RULES.hook("dot_rows", CANG)
def _cang_field_ticks(ctx, run, dot_rows):
    """Base kit (D-2): the 「判予秋」 field ticks the simulator never laid out - one tick every 2 s of active time from
    the 展开 hit while the field lives (12 s = 6 ticks, ⑤ 16 s = 8 ticks), cut by the next field and the axis end."""
    data = ctx.data or {}
    field_s, period_s = _cang_field_s(ctx), data.get("period_s")
    if not CANG_FIELD_TICKS or not field_s or not period_s or CANG not in run.names:
        return dot_rows
    dmg = run.static.get_skill_damage(CANG_TICK_GE)
    if not dmg:
        return dot_rows
    starts = [run.to_active(r["relative_time_us"])
              for r in sorted(run.layout.rows, key=lambda r: r["relative_time_us"])
              if r["character_id"] == CANG and r["gameplay_effect_name"] == CANG_FIELD_HIT]
    if not starts:
        return dot_rows
    period = _us(period_s)
    count = int(float(field_s) / float(period_s) + 1e-9)
    end_active = run.to_active(run.layout.end_us)
    attribute = str(dmg.get("damage_type") or "").lower()
    out = list(dot_rows)
    for i, a0 in enumerate(starts):
        stop = starts[i + 1] if i + 1 < len(starts) else end_active
        for k in range(1, count + 1):
            t_active = a0 + k * period
            if t_active > stop or t_active > end_active:
                break
            out.append(run.row(CANG, run.to_wall(t_active), dmg.get("ability_id"), CANG_TICK_GE, attribute,
                               component=CANG_TICK_LABEL))
    ctx.note("awakening_g1_cang_field_ticks", CANG)
    return out


@RULES.hook("intervals", CANG, nodes=("Effect2", "Effect5", "Effect6", "resonance_6"))
def _cang_intervals(ctx, run, analysis):
    """⑥ CritBase +30 % (self) and 共鸣6 AtkUp +20 % (team) from right after each 展开 hit for the field's 12 s (⑤ 16 s)
    of active time or until the next field (D-3: the 展开 hit itself is outside); ② every generated word (噤念 /
    如此罪状 hit, support skill hit, counter hit, every 3rd 言行合一 hit) AtkUp +6 % for 10 s, each stack its own
    timer (D-11), at most 4 at once (DB AggregateBySource / StackLimitCount 4)."""
    data = ctx.data or {}
    _active_us, window_end = _clock()
    end = int(analysis.battle_end_us)
    hits = _hits(analysis)
    add = []
    field_s = _cang_field_s(ctx)
    want_e6 = ctx.member.has("Effect6") and data.get("e6") is not None
    want_r6 = ctx.member.has("resonance_6") and data.get("r6") is not None
    if field_s and (want_e6 or want_r6):
        unfolds = [h.relative_time_us for h in hits if h.character_id == CANG and h.gameplay_effect_id == CANG_FIELD_HIT]
        for i, t in enumerate(unfolds):
            stop = min(end, window_end(analysis, t, field_s))
            if i + 1 < len(unfolds):
                stop = min(stop, unfolds[i + 1])
            if want_e6:
                add.append(_interval(CANG, "E6", i, t + 1, stop, "CritBase", data["e6"]))
            if want_r6:
                add.append(_interval(CANG, "R6", i, t + 1, stop, "AtkUp", data["r6"], scope="team"))
    if ctx.member.has("Effect2") and None not in (data.get("e2"), data.get("e2_s")) and data.get("e2_limit"):
        words, melee = [], 0
        for h in hits:
            if h.character_id != CANG:
                continue
            ge = h.gameplay_effect_id
            if ge in ("GE_Player_Cang_SkillA_Damage", "GE_Player_Cang_QTE_Damage",
                      "GE_Player_Cang_PerfectEvadeAttack_Damage"):
                words.append(h.relative_time_us)        # 噤念 / 如此罪状 -> 噤, support skill -> 噤, counter -> 祝
            elif ge.startswith("GE_Player_Cang_Melee"):
                melee += 1
                if melee % 3 == 0:
                    words.append(h.relative_time_us)    # every 3rd 言行合一 hit -> 祝
        stacking = data.get("e2_stacking") or _AGGREGATE_BY_SOURCE
        for i, t in enumerate(words):
            add.append(_interval(CANG, "E2", i, t + 1, min(end, window_end(analysis, t, data["e2_s"])), "AtkUp",
                                 data["e2"], stacking=stacking, limit=data["e2_limit"]))
    return _apply(analysis, add)


# ── 1025 Hathor ──────────────────────────────────────────────────────────────

HATHOR_CYCLONE = "GA_Hathor_Skill2"      # 轮转打击 (the three approved Cyclone segments)
HATHOR_E = "GA_Hathor_Skill"             # 空中指令 (Power / PowerEnd = hold, Short* = tap)


@RULES.hook("prepare", HATHOR, nodes=("Effect3", "Effect4", "Effect5", "Effect6", "resonance_6"))
def _hathor_prepare(ctx):
    db = _Db(ctx.con)
    table = "DT_HathorEffectFigure"
    stack = "Buff_HathorAngerStack"
    start_s = _form_start_s(HATHOR)
    if start_s is None:
        db.missing.append("team_form_actions.FORMS[1025].start")
    return {"dispatch_start_s": start_s, "dispatch_s": db.curve(table, "Buff_HathorAngerActive_Duration"),
            "e3": db.curve(table, "Buff_Hathor025_Level3_DmgUp"), "e4": db.curve(table, "Buff_Hathor_Skill2CritUp"),
            "e4_limit": db.stack_limit("Buff_Hathor_Skill2CritUp"),
            "e5": db.curve(table, "Buff_Hathor_DmgUpLevel5"), "e5_cap": db.stack_limit("Buff_Hathor_DmgUpLevel5_CheckStack"),
            "gain_e": db.trigger_stacks("Buff_HathorAngerStack_Skill1ShortAdd", stack),
            "gain_e1": db.trigger_stacks("Buff_HathorAngerStack_SkillAddOnce", stack),
            "gain_e2": db.curve(table, "Hathor_GazeExAddAnger"), "gaze_s": db.curve(table, "Buff_HathorAnger_GazeEx_Duration"),
            "e6": db.curve(table, "Buff_HathorAngerActive_CritDmgUp"),
            "r6": db.curve(table, "Buff_HathorAngerActive_DefIgnore"), "missing": tuple(db.missing)}


def _hathor_windows(run, analysis, data, hits, acts, window_end) -> list:
    """紧急派送 windows: Q start + 1.5 s (form rule) for 5 s of active time, extended to the last 轮转打击 hit before
    the next Q (the approved Cyclone steps overrun the 5 s), ended by Hathor's swap-out (team runs)."""
    end = int(analysis.battle_end_us)
    # one window per Q cast: the engine infers one Q action per damage GE of the cast (same start), so dedupe starts
    q_starts = sorted({a.start_us for a in acts if a.character_id == HATHOR and a.input_kind == "Q"})
    out = []
    for q_start in q_starts:
        start = q_start + _us(data["dispatch_start_s"])
        stop = window_end(analysis, start, data["dispatch_s"])
        later = [t for t in q_starts if t > q_start]
        cap = min(later) if later else end
        cyclone = [h.relative_time_us for h in hits if h.character_id == HATHOR and h.ability_id == HATHOR_CYCLONE
                   and start <= h.relative_time_us < cap]
        if cyclone:
            stop = max(stop, max(cyclone) + 1)
        swap = _swap_out_after(run, HATHOR, start)
        if swap is not None:
            stop = min(stop, swap)
        out.append((start, min(stop, end)))
    return out


def _hathor_e_casts(run) -> list:
    """(hold / tap start, release, end, gesture) of the E casts of the layout (approved / custom steps)."""
    out = []
    for visit in getattr(run.layout, "visits", ()) or ():
        power = None
        for step in getattr(visit, "steps", ()) or ():
            if getattr(step, "ability_id", None) != HATHOR_E or getattr(step, "status", "ok") == "skipped_entry":
                continue
            selector = str(getattr(step, "selector", "") or "")
            if selector == "PowerEnd" and power is not None:
                out.append((power, step.start_us, step.end_us, "hold"))
                power = None
            elif selector == "Power":
                power = step.start_us
            elif selector.startswith("Short"):
                out.append((step.start_us, step.start_us, step.end_us, "tap"))
    return out


def _hathor_gains(ctx, run, analysis, data, acts, windows, window_end) -> list:
    """(wall µs, stacks) of 闪送之力 gained: +2 at the end of every E cast, ① +6 at the first hold, ② +3 when
    满星追踪 ends 5 s after the release; none inside 紧急派送 (description '不再获得「闪送之力」')."""
    gains, first_hold = [], True
    has1, has2 = ctx.member.has("Effect1"), ctx.member.has("Effect2")
    casts = _hathor_e_casts(run)
    if casts:
        for press, release, finish, gesture in casts:
            if (gesture != "hold" or HATHOR_PLUS2_AFTER_HOLD) and data.get("gain_e"):
                gains.append((finish, data["gain_e"]))
            if gesture == "hold":
                if has1 and first_hold and data.get("gain_e1"):
                    gains.append((press + 1, data["gain_e1"]))
                    first_hold = False
                if has2 and data.get("gain_e2") and data.get("gaze_s"):
                    gains.append((window_end(analysis, release, data["gaze_s"]), int(data["gain_e2"])))
    else:       # no step trace: the analysis' inferred E actions
        for a in acts:
            if a.character_id != HATHOR or a.input_kind != "E":
                continue
            if any(ws <= a.start_us < we for ws, we in windows):
                continue
            hold = a.input_gesture == "hold"
            if (not hold or HATHOR_PLUS2_AFTER_HOLD) and data.get("gain_e"):
                gains.append((a.end_us, data["gain_e"]))
            if hold:
                if has1 and first_hold and data.get("gain_e1"):
                    gains.append((a.start_us + 1, data["gain_e1"]))
                    first_hold = False
                if has2 and data.get("gain_e2") and data.get("gaze_s"):
                    gains.append((window_end(analysis, a.end_us, data["gaze_s"]), int(data["gain_e2"])))
    gains.sort()
    if HATHOR_BLOCK_IN_DISPATCH:
        gains = [(t, n) for (t, n) in gains if not any(ws <= t < we for ws, we in windows)]
    return gains


@RULES.hook("intervals", HATHOR, nodes=("Effect3", "Effect4", "Effect5", "Effect6", "resonance_6"))
def _hathor_intervals(ctx, run, analysis):
    """⑥ CritDamageBase +30 % / 共鸣6 DefIgnore 10 % over 紧急派送; ④ Cyclone cast k (k >= 2, one approved segment =
    one cast, D-10) CritBase +25 % x (k-1); ③ +15 % damage on a non-boss target (D-1: the dummy is not a boss);
    ⑤ +1 % damage per 闪送之力 gained so far (cap 15), replacing the engine's valueless interval."""
    data = ctx.data or {}
    _active_us, window_end = _clock()
    end = int(analysis.battle_end_us)
    hits, acts = _hits(analysis), _actions(analysis)
    add, drop = [], set()
    windows = []
    if data.get("dispatch_start_s") is not None and data.get("dispatch_s"):
        windows = _hathor_windows(run, analysis, data, hits, acts, window_end)
    for i, (start, stop) in enumerate(windows):
        if ctx.member.has("Effect6") and data.get("e6") is not None:
            add.append(_interval(HATHOR, "E6", i, start, stop, "CritDamageBase", data["e6"]))
        if ctx.member.has("resonance_6") and data.get("r6") is not None:
            add.append(_interval(HATHOR, "R6", i, start, stop, "DefIgnore", data["r6"]))
    if ctx.member.has("Effect4") and data.get("e4") is not None and windows:
        limit = int(data.get("e4_limit") or 1)
        steps = [(s.start_us, s.end_us) for _v, s in _steps(run, HATHOR_CYCLONE)]
        index = 0
        for start, stop in windows:
            if steps and HATHOR_E4_PER_SEGMENT:
                casts = [[h.relative_time_us for h in hits if h.character_id == HATHOR
                          and h.ability_id == HATHOR_CYCLONE and s0 <= h.relative_time_us < s1]
                         for s0, s1 in steps if start <= s0 < stop]
            else:   # no step trace: casts = Cyclone hit groups (gap > 0.4 s)
                casts = []
                for h in hits:
                    if h.character_id == HATHOR and h.ability_id == HATHOR_CYCLONE and start <= h.relative_time_us <= stop:
                        if casts and h.relative_time_us - casts[-1][-1] <= 400_000:
                            casts[-1].append(h.relative_time_us)
                        else:
                            casts.append([h.relative_time_us])
            casts = [c for c in casts if c]
            for k, cast in enumerate(casts):
                if k == 0:
                    continue
                add.append(_interval(HATHOR, "E4", index, min(cast) - 1, max(cast) + 1, "CritBase",
                                     data["e4"] * min(k, limit), tags=("Ability.GA_Hathor_Skill2",)))
                index += 1
    if ctx.member.has("Effect3") and data.get("e3") is not None and not _boss_target(run):
        drop.add(f"character_awaken:{HATHOR}:Effect3")
        add.append(_interval(HATHOR, "E3", 0, 0, end, "DamageUpGeneralBase", data["e3"]))
    if ctx.member.has("Effect5") and data.get("e5") is not None and data.get("e5_cap"):
        drop.add(f"character_awaken:{HATHOR}:Effect5")
        gains = _hathor_gains(ctx, run, analysis, data, acts, windows, window_end)
        total = 0
        for i, (t, n) in enumerate(gains):
            total = min(int(data["e5_cap"]), total + int(n))
            nxt = gains[i + 1][0] if i + 1 < len(gains) else end
            if nxt > t:
                add.append(_interval(HATHOR, "E5", i, t, nxt, "DamageUpGeneralBase", data["e5"] * total))
    return _apply(analysis, add, drop)


def _boss_target(run) -> bool:
    """True only when the run's enemy options name a boss (DEFAULT_TARGET: a non-boss Lv80 dummy)."""
    target = getattr(run.ctx, "target_condition", None) or {}
    try:
        kind = str(target.get("enemy_type") or "").casefold()
        return bool(target.get("boss")) or kind in ("boss", "weeklyboss")
    except Exception:
        return False


# ── 1033 Adler ───────────────────────────────────────────────────────────────

@RULES.hook("prepare", ADLER)
def _adler_prepare(ctx):
    db = _Db(ctx.con)
    table = "DT_AdlerEffectFigure"
    karma = "Buff_AdlerUltraSkill_QiHai"
    shield_at = db.notify_s("GA_Adler_Skill", "Default", "Event.Montage.Player.Skill.1")
    return {"per_stack": db.curve(table, "Adler_SkillDamUp"), "e2": db.curve(table, "Adler_lv2"),
            "consume_s": db.duration_s("Buff_AdlerQiHai_SkillDamUP", table), "cap": db.stack_limit(karma),
            "gain_melee": db.trigger_stacks("Buff_AdlerMelee_QiHaiAdd", karma),
            "gain_aim": db.trigger_stacks("Buff_AdlerAim_QiHaiAdd", karma),
            "gain_e1": db.trigger_stacks("Buff_AdlerUltraSkill_QiHaiAdd", karma),
            "shield_s": db.curve(table, "Adler_SkillShield_time"), "shield_e6_s": db.curve(table, "Adler_SkillShield_lv6_time"),
            "shield_at_us": None if shield_at is None else _us(shield_at),
            "r6": db.curve(table, "Adler_lv6_extra"), "missing": tuple(db.missing)}


@RULES.hook("intervals", ADLER, name="adler_stash", order=-1)
def _adler_stash(ctx, run, analysis):
    """Base kit: keep the analysis for the 「业」 evidence hook of the same engine call (no interval change)."""
    _stash(run, analysis)
    return analysis


@RULES.hook("intervals", ADLER, nodes=("Effect1", "Effect2", "Effect6", "resonance_6"))
def _adler_intervals(ctx, run, analysis):
    """共鸣6: incantation damage +10 % (team) while the E shield lives - from the shield notify after the E's two
    hits (D-9) for 8 s (⑥ 12 s) of active time; the shield never breaks (no incoming damage).  ①② are priced by
    the 「业」 evidence hook (base kit); their nodes are listed here so the explanation names them when selected."""
    data = ctx.data or {}
    if not ctx.member.has("resonance_6") or None in (data.get("r6"), data.get("shield_at_us"), data.get("shield_s")):
        return analysis
    _active_us, window_end = _clock()
    end = int(analysis.battle_end_us)
    seconds = data.get("shield_e6_s") if ctx.member.has("Effect6") else data.get("shield_s")
    if not seconds:
        return analysis
    add = []
    for i, a in enumerate(x for x in _actions(analysis) if x.character_id == ADLER and x.input_kind == "E"):
        start = a.start_us + int(data["shield_at_us"])
        add.append(_interval(ADLER, "R6", i, start, min(end, window_end(analysis, start, seconds)),
                             "DamageUpIncantationBase", data["r6"], scope="team"))
    return _apply(analysis, add)


@RULES.hook("evidence", ADLER)
def _adler_karma(ctx, run, evidence):
    """「业」 (base kit): each basic hit +1, each aim hit +2, ① each Q +20 (at the Q end), at most 20; every E
    consumes all of them at its start: the E's damage hits within 12 s of active time get an independent final
    multiplier 1 + 2 % (② 3 %) x stacks (FinalDamageUp is not a safe additive buff property, hence evidence)."""
    analysis = _stashed(run)
    data = ctx.data or {}
    if analysis is None or None in (data.get("per_stack"), data.get("consume_s"), data.get("cap")):
        return evidence
    per = data["per_stack"] + (data.get("e2") or 0.0 if ctx.member.has("Effect2") else 0.0)
    _active_us, window_end = _clock()
    hits = {h.event_id: h for h in analysis.hits}
    events = []
    for h in hits.values():
        if h.character_id != ADLER:
            continue
        ge = h.gameplay_effect_id
        if (ge.startswith("GE_Player_Adler_Melee") or ge == "GE_Player_Adler_AirAttack_Damage") and data.get("gain_melee"):
            events.append((h.relative_time_us, "gain", int(data["gain_melee"])))
        elif ge == "GE_Player_Adler_Aim_Damage" and data.get("gain_aim"):
            events.append((h.relative_time_us, "gain", int(data["gain_aim"])))
    for a in _actions(analysis):
        if a.character_id != ADLER:
            continue
        if a.input_kind == "Q" and ctx.member.has("Effect1") and data.get("gain_e1"):
            events.append((a.end_us, "gain", int(data["gain_e1"])))
        if a.input_kind == "E":
            events.append((a.start_us, "consume", 0))
    events.sort()
    stacks, windows, from_basics = 0, [], False
    for t, kind, n in events:
        if kind == "gain":
            stacks = min(int(data["cap"]), stacks + n)
            from_basics = from_basics or n != data.get("gain_e1")
        else:
            if stacks:
                windows.append((t, window_end(analysis, t, data["consume_s"]), stacks))
                if from_basics:         # base-kit stacks (basics / aim) consumed: say so in the explanation
                    ctx.note("awakening_g1_adler_karma", ADLER)
            stacks, from_basics = 0, False
    if not windows:
        return evidence
    out = list(evidence)
    for i, e in enumerate(out):
        h = hits.get(e.event_id)
        if h is None or h.character_id != ADLER or not str(e.damage_id).startswith("GE_Player_Adler_Skill"):
            continue
        for start, stop, n in windows:
            if start <= h.relative_time_us <= stop:
                out[i] = dataclasses.replace(e, skill_final_multiplier=max(1.0, e.skill_final_multiplier) * (1 + per * n),
                                             skill_final_multiplier_basis=f"Global awakening g1: 业 x{n}")
    return tuple(out)


# ── 1036 Zankou ──────────────────────────────────────────────────────────────

ZANKOU_FINAL_HIT = "GE_Player_Zankou_Skill3_2_Damage"    # the last hit of 「灭」 (enhanced 离魂错)
ZANKOU_CHARGE_REACTIONS = ("浊燃", "覆纹")                 # ReactionScheduler reaction names (data, not display)


@RULES.hook("prepare", ZANKOU, nodes=("Effect2", "Effect6"))
def _zankou_prepare(ctx):
    db = _Db(ctx.con)
    table = "DT_ZankouEffectFigure"
    e2 = db.curve(table, "ZankouFinalUltraDamUpLv2")
    return {"e2_mult": None if e2 is None else 1.0 + e2, "e6": db.curve(table, "ZankouPerStackDamUpLv6"),
            "e6_cap": db.curve(table, "ZankouDamUpMaxLv6"), "missing": tuple(db.missing)}


def _zankou_layers(analysis):
    """t -> DoT layers (erosion + venom, the simulator's own _DotState rules) on the target just before t."""
    from src.services import team_simulation_service as svc

    active_us, _window_end = _clock()
    rows = [{"relative_time_us": h.relative_time_us, "character_id": h.character_id,
             "gameplay_effect_name": h.gameplay_effect_id, "ability_name": h.ability_id}
            for h in analysis.hits if h.direction == "outgoing"]
    apps = svc._dot_applications(rows, {"characters": []})

    def count(t_us: int) -> int:
        total = 0
        t_active = active_us(analysis, t_us)
        for kind in ("erosion", "venom"):
            state = svc._DotState(int(svc.ZANKOU_DOT_DURATION_S * 1e6), False)
            for (w, op, n) in apps.get(kind, ()):
                if w >= t_us:
                    break
                a = active_us(analysis, w)
                if op == "add":
                    state.add(n, a)
                else:
                    state.refresh(a)
            if state.alive(t_active):
                total += state.count
        return total

    return count


@RULES.hook("intervals", ZANKOU, nodes=("Effect2", "Effect6"))
def _zankou_intervals(ctx, run, analysis):
    """⑥ the 「灭」 final hit: damage bonus +12 % per DoT layer on the target (erosion / venom), at most +240 %."""
    _stash(run, analysis)
    data = ctx.data or {}
    if not ctx.member.has("Effect6") or None in (data.get("e6"), data.get("e6_cap")):
        return analysis
    layers = _zankou_layers(analysis)
    add = []
    finals = [h for h in _hits(analysis) if h.character_id == ZANKOU and h.gameplay_effect_id == ZANKOU_FINAL_HIT]
    for i, h in enumerate(finals):
        n = layers(h.relative_time_us)
        if n > 0:
            add.append(_interval(ZANKOU, "E6", i, h.relative_time_us - 1, h.relative_time_us + 1, "DamageUpGeneralBase",
                                 min(data["e6_cap"], data["e6"] * n), tags=(f"Ability.{ZANKOU_FINAL_HIT}",)))
    return _apply(analysis, add)


@RULES.hook("evidence", ZANKOU, nodes=("Effect2",))
def _zankou_charge(ctx, run, evidence):
    """② 「渊底之吻」: a 浊燃 / 覆纹 reaction with Zankou on either side of the swap stores 蓄焰 (max 1); the next
    焚天烬灭舞 (force Q) hits x2.5 final and consume it; with ④ the next 血宴入梦时 (magic Q) has its own charge.  The
    simulator's reaction rows do not reach the engine's own trigger test, so the readiness walk of
    reconstruct_zankou_q_final_damage runs here on the scheduler's triggers."""
    analysis = _stashed(run)
    data = ctx.data or {}
    sched = run.sched
    if analysis is None or sched is None or not data.get("e2_mult"):
        return evidence
    triggers = sorted(t for (_i, t, name, out_id, in_id) in getattr(sched, "triggers", ())
                      if name in ZANKOU_CHARGE_REACTIONS and ZANKOU in (int(out_id or 0), int(in_id or 0)))
    if not triggers:
        return evidence
    hits = {h.event_id: h for h in analysis.hits}
    magic_too = ctx.member.has("Effect4")
    q_actions = sorted((a for a in analysis.inferred_actions if a.character_id == ZANKOU and a.input_kind == "Q"),
                       key=lambda a: a.start_us)
    ti, force_ready, magic_ready, chosen = 0, False, False, set()
    for a in q_actions:
        while ti < len(triggers) and triggers[ti] < a.start_us:
            force_ready = True
            magic_ready = magic_ready or magic_too
            ti += 1
        branches = {"magic": [], "force": []}
        for eid in a.evidence_event_ids:
            h = hits.get(eid)
            if h is None or h.character_id != ZANKOU:
                continue
            ident = (str(h.ability_id) + "|" + str(h.gameplay_effect_id)).casefold()
            if "ultraskill" in ident:
                branches["magic" if "magicultraskill" in ident else "force"].append(eid)
        for branch, ids in branches.items():
            ready = magic_ready if branch == "magic" else force_ready
            if ready and ids:
                chosen.update(ids)
                if branch == "magic":
                    magic_ready = False
                else:
                    force_ready = False
    if not chosen:
        return evidence
    mult = float(data["e2_mult"])
    out = list(evidence)
    for i, e in enumerate(out):
        if e.event_id not in chosen:
            continue
        if ZANKOU_E2_SKIP_ENGINE and e.skill_final_multiplier >= mult - 1e-9 and e.skill_final_multiplier_basis:
            continue        # the engine's own 蓄焰 evidence already priced this hit
        out[i] = dataclasses.replace(e, skill_final_multiplier=max(1.0, e.skill_final_multiplier) * mult,
                                     skill_final_multiplier_basis=f"Global awakening g1: 蓄焰 x{mult:g}")
    return tuple(out)


# ── 1039 Fadia ───────────────────────────────────────────────────────────────

@RULES.hook("prepare", FADIA, nodes=("Effect5",))
def _fadia_prepare(ctx):
    db = _Db(ctx.con)
    return {"e5": db.curve("DT_FadiaEffectFigure", "FadiaCritUpLv5"), "missing": tuple(db.missing)}


@RULES.hook("intervals", FADIA, nodes=("Effect5",))
def _fadia_intervals(ctx, run, analysis):
    """⑤ crit +50 % on the 敌神者 chase hits (the chase only exists in the state, so the window is the chase itself;
    the Q's own six hits stay out, as the upstream requirement says, D-12); replaces the engine's Q-begin 5 s window
    that ends before the chase starts."""
    data = ctx.data or {}
    if data.get("e5") is None:
        return analysis
    from src.services.battle_character_awakening_hit_service import FADIA_GODSLAYER_REQUIREMENT

    chase = [h.relative_time_us for h in _hits(analysis) if h.character_id == FADIA
             and "fadia_ultraskillmelee" in str(h.gameplay_effect_id).casefold()]
    groups: list[list[int]] = []
    for t in chase:
        if groups and t - groups[-1][-1] < 3_000_000:
            groups[-1].append(t)
        else:
            groups.append([t])
    add = [_interval(FADIA, "E5", i, g[0] - 1, g[-1] + 1, "CritBase", data["e5"], requirement=FADIA_GODSLAYER_REQUIREMENT)
           for i, g in enumerate(groups)]
    return _apply(analysis, add, {f"character_awaken:{FADIA}:Effect5"})


# ── explanation notes of this group (ctx.note codes; plain sentences per language, ko uses 돌파) ─────────────

_NOTE_TEXTS = {
    "awakening_g1_cang_field_ticks": {
        "zh": "白藏「判予秋」领域的持续伤害按每 2 秒 1 跳、在领域持续期间（12 秒，觉醒效果 ⑤ 为 16 秒）计算"
              "（补充基础技能；跳数为实测前的假设）",
        "ko": "백장 「판결의 가을」 영역의 지속 피해를 영역이 유지되는 동안(12초, 돌파 효과 ⑤ 16초) 2초마다 1회로 계산"
              " (기본 키트 보충, 횟수는 측정 전 가정)",
        "en": "Baicang's Autumn's Verdict field damage over time is counted as one tick every 2 s while the field "
              "lasts (12 s, 16 s with Awakening Effect ⑤) (base-kit supplement; the tick count is an assumption until "
              "measured)",
        "ja": "白蔵「判予秋」の領域継続ダメージを領域の持続中（12秒、覚醒効果⑤で16秒）2秒ごとに1回として計算"
              "（基本キットの補足。回数は実測前の仮定）",
    },
    "awakening_g1_adler_karma": {
        "zh": "阿德勒的「业」：普通攻击每段 +1 层、瞄准射击 +2 层，下一次变轨技能（E）消耗全部层数（每层独立最终伤害 +2%）"
              "（补充基础技能）",
        "ko": "아들러의 「업」: 일반 공격 1타당 +1중첩, 조준 사격 +2중첩, 다음 E가 모두 소비 (중첩당 독립 최종 피해 +2%)"
              " (기본 키트 보충)",
        "en": "Adler's 'Karma': +1 stack per basic attack hit, +2 per aimed shot; the next skill (E) consumes them all "
              "(+2% independent final damage per stack) (base-kit supplement)",
        "ja": "アドラーの「業」：通常攻撃1ヒットごとに+1層、照準射撃で+2層、次のスキル（E）が全層を消費"
              "（1層ごとに独立最終ダメージ+2%）（基本キットの補足）",
    },
}


def _language() -> str:
    try:
        from src import i18n_runtime

        return str(i18n_runtime.get_language() or "zh")
    except Exception:
        return "zh"


def _note_builder(code: str):
    def build(args, names):
        table = _NOTE_TEXTS[code]
        return table.get(_language()) or table["zh"]
    return build


for _code in _NOTE_TEXTS:
    RULES.text(_code, _note_builder(_code))


# ── node metadata (all 48 nodes: efficiency cell class, bucket, confidence, scope, the user-facing assumption) ──
# Source: awakening_node_specs.json (efficiency_category / bucket / confidence / scope / assumption_ko); the Korean
# sentences say 돌파 (user decision 10-18) and describe the implemented state.  No group-1 node is an expected value.

_NODES = (
    # 1021 Edgar
    (EDGAR, "Effect1", "team", "now", "high", "team_only", {
        "ko": "돌파 효과 ①은 팀원 서포트 스킬마다 열쇠를 얻어 울티메이트 치유 영역을 1초씩(최대 3초) 늘릴 뿐이라, 피해에는 "
              "돌파 효과 ⑥(영역 방어력)과 방어력 계수 팀원(아들러)이 함께 있을 때만 영향을 준다고 봅니다.",
        "zh": "觉醒效果①只是在每次队友释放援护技时获得一把钥匙，使终结技的治疗领域每把延长 1 秒（至多 3 秒）；只有同时选择"
              "觉醒效果⑥（领域防御力）且队中有以防御力计算伤害的队友（阿德勒）时才影响伤害。",
        "en": "Awakening Effect ① only gives a key per teammate Support Skill, extending the ultimate's healing field by "
              "1 s each (up to 3 s); it affects damage only together with Awakening Effect ⑥ (field DEF) and a "
              "DEF-scaling teammate (Adler).",
        "ja": "覚醒効果①は味方の支援スキルごとに鍵を得てアルティメットの回復領域を1秒ずつ（最大3秒）延ばすだけなので"
              "、ダメージに影響するのは覚醒効果⑥（領域の防御力）と防御力依存の味方（アドラー）が揃うときだけと見なし"
              "ます。"}),
    (EDGAR, "Effect2", "none", "measure", "medium", "", {
        "ko": "광류 쿨타임 연장 단위는 게임 데이터 행 이름(채널 시간 × 1.0)과 스킬 설명(1단당 X초, 값 없음)이 달라 "
              "아직 모르지만, 검수 사이클의 광류는 1타짜리 짧은 누르기(1.25초)라 1단당 연장이 3초 이하인 한 3초 "
              "상한에 닿지 않으므로 돌파 효과 ②는 0으로 둡니다.",
        "zh": "狂流冷却延长的单位尚不明确（数据行名为“持续施放时间 ×1.0”，技能说明为“每段 X 秒”且无数值）；已审核循环中的"
              "狂流是只有 1 段的短按（1.25 秒），只要每段延长不超过 3 秒就碰不到 3 秒上限，因此觉醒效果②按 0 计。",
        "en": "The unit of Torrent's cooldown extension is unknown (the game data row reads 'channel time × 1.0', "
              "the skill text 'X s per segment' without a value); the reviewed rotation's Torrent is a one-hit tap "
              "(1.25 s), so as long as the extension per segment is at most 3 s it never reaches the 3 s cap, and "
              "Awakening Effect ② is priced at 0.",
        "ja": "狂流のクールタイム延長の単位は、ゲームデータの行名（持続時間×1.0）とスキル説明（1段ごとにX秒、数値なし"
              "）が食い違って未確定ですが、審査済みサイクルの狂流は1ヒットの短押し（1.25秒）なので、1段あたりの延長が"
              "3秒以下である限り3秒の上限に届かず、覚醒効果②は0とします。"}),
    (EDGAR, "Effect3", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ③은 치유량만 바꾸므로 피해 계산에서는 0입니다.",
        "zh": "觉醒效果③只改变治疗量，伤害计算中为 0。",
        "en": "Awakening Effect ③ only changes healing, so it is 0 in the damage calculation.",
        "ja": "覚醒効果③は回復量だけを変えるため、ダメージ計算では0です。"}),
    (EDGAR, "Effect4", "damage", "now", "high", "solo_team", {
        "ko": "돌파 효과 ④는 게임 데이터 값 +50%를 다른 피해 증가와 같은 합연산 구간에 더하고 광류(E) 타격에만 "
              "적용합니다.",
        "zh": "觉醒效果④把数据值 +50% 加进与其他增伤相同的加算区，只作用于狂流（E）的命中。",
        "en": "Awakening Effect ④ adds the game data value +50% to the same additive zone as the other damage "
              "bonuses, on Torrent (E) hits only.",
        "ja": "覚醒効果④はゲームデータの値+50%を他のダメージアップと同じ加算枠に加え、狂流（E）のヒットにだけ適用しま"
              "す。"}),
    (EDGAR, "Effect5", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ⑤는 HP만 올리고 에드가의 피해는 모두 공격력 계수라서 0입니다.",
        "zh": "觉醒效果⑤只提高生命值，埃德嘉的伤害全部按攻击力计算，因此为 0。",
        "en": "Awakening Effect ⑤ only raises HP and all of Edgar's damage scales with ATK, so it is 0.",
        "ja": "覚醒効果⑤はHPを上げるだけで、エドガーのダメージはすべて攻撃力依存のため0です。"}),
    (EDGAR, "Effect6", "team", "now", "medium", "team_only", {
        "ko": "돌파 효과 ⑥의 방어력 +15%는 울티메이트 영역이 10초(+열쇠당 1초) 동안 에드가가 교대한 뒤에도 남아 필드 위 "
              "팀원에게 걸린다고 보며, 방어력 계수 공격(아들러)만 이득을 봅니다.",
        "zh": "觉醒效果⑥的防御力 +15% 视为在终结技领域存在的 10 秒（每把钥匙 +1 秒）内、埃德嘉切走后依然保留并作用于场上"
              "队员；只有以防御力计算的伤害（阿德勒）受益。",
        "en": "Awakening Effect ⑥'s DEF +15% is taken to stay on the on-field teammate for the ultimate field's 10 s "
              "(+1 s per key) even after Edgar swaps out; only DEF-scaling damage (Adler) gains from it.",
        "ja": "覚醒効果⑥の防御力+15%は、アルティメットの領域がある10秒（鍵1本ごとに+1秒）の間、エドガーが交代した後も"
              "残ってフィールド上の味方にかかると見なし、防御力依存の攻撃（アドラー）だけが恩恵を受けます。"}),
    (EDGAR, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3(스킬 레벨 +1)은 지금 엔진이 그대로 계산하며 고칠 것이 없습니다.",
        "zh": "共鸣3（技能等级 +1）由现有引擎直接计算，无需修改。",
        "en": "Resonance 3 (skill level +1) is priced by the engine as is; nothing to fix.",
        "ja": "共鳴3（スキルレベル+1）は現在のエンジンがそのまま計算しており、修正は不要です。"}),
    (EDGAR, "resonance_6", "none", "not_computable", "high", "", {
        "ko": "시뮬레이터에는 아군 피격이 없어 공명6의 충전량은 항상 0이고, 에드가 울티메이트 비용도 아직 검사하지 않습니다.",
        "zh": "模拟中我方不会受击，共鸣6 的充能始终为 0；埃德嘉终结技的消耗也尚未检查。",
        "en": "The simulation has no hits taken by the team, so Resonance 6's charge is always 0; Edgar's ultimate cost "
              "is not checked yet either.",
        "ja": "シミュレーションには味方の被弾がないため共鳴6のチャージは常に0で、エドガーのアルティメットコストもまだ"
              "検査していません。"}),
    # 1023 Cang (白藏)
    (CANG, "Effect1", "unmodelled", "measure", "low", "", {
        "ko": "언령 글자가 영역 안에서 언제 발동하는지 데이터가 없어 돌파 효과 ①은 계산하지 않으며(미반영), 검수 사이클에서는 "
              "영역 뒤 첫 E가 시간만 쓰는 단계라 넣어도 1바퀴 값은 0입니다.",
        "zh": "数据中没有言灵字在领域内何时触发的信息，因此觉醒效果①不计算（未反映）；已审核循环中领域之后的第一个 E 是只占"
              "时间的步骤，即使计入，1 轮的值也为 0。",
        "en": "The data does not say when a spirit word triggers inside the field, so Awakening Effect ① is not priced "
              "(not reflected); in the reviewed rotation the first E after the field is a time-only step, so the 1-loop "
              "value would be 0 anyway.",
        "ja": "言霊の文字が領域内でいつ発動するかのデータがないため覚醒効果①は計算せず（未反映）、審査済みサイクルでは"
              "領域後の最初のEが時間だけのステップなので、入れても1周の値は0です。"}),
    (CANG, "Effect2", "damage", "now", "low", "solo_team", {
        "ko": "언령 글자는 억눌린 생각(SkillA) 1타, 서포트 스킬, 극한 반격, 일반 공격(언행일치) 3타마다 1개씩 "
              "생긴다고 보고, 글자마다 공격력 +6%를 각자 10초씩(설명문 '중첩마다 10초 지속', 최대 4중첩) 줍니다. "
              "게임 데이터에는 중첩 시간 규칙이 없어 게임 기본값(새 글자마다 전체 10초 갱신)이라면 3바퀴 값이 "
              "+3.1%에서 +4.5%로 커집니다.",
        "zh": "言灵字视为在噤念（SkillA）第 1 段、援护技、极限反击、普通攻击（言行合一）每 3 段时各生成 1 个，每个字给予攻击力 "
              "+6%、各自持续 10 秒（说明文“每层持续时间10秒”，至多 4 层）。数据中没有叠层时间规则，若按游戏默认（每个新字刷新"
              "全部 10 秒），3 轮的值会从 +3.1% 增至 +4.5%。",
        "en": "A spirit word is taken to appear on the first hit of Silenced Thought (SkillA), each Support Skill, "
              "each Extreme Counter and every 3rd basic-attack (Words and Deeds as One) hit; each word gives ATK +6% "
              "for its own 10 s (description: each stack lasts 10 s, at most 4 stacks). The game data has no "
              "stack-timer rule; under the game default (each new word refreshes all stacks to 10 s) the 3-loop "
              "value grows from +3.1% to +4.5%.",
        "ja": "言霊の文字は噤念（SkillA）の1ヒット目、支援スキル、極限カウンター、通常攻撃（言行一致）3ヒットごとに1"
              "つずつ生まれると見なし、文字ごとに攻撃力+6%をそれぞれ10秒（説明文「各層10秒持続」、最大4層）与えます。"
              "ゲームデータに重ね時間のルールがなく、ゲーム既定（新しい文字ごとに全体を10秒更新）なら3周の値は+3.1%か"
              "ら+4.5%に増えます。"}),
    (CANG, "Effect3", "unmodelled", "measure", "medium", "", {
        "ko": "글자 상한은 글자 발동 피해(아직 미모델)와 글자가 3개 동시에 쌓일 때만 의미가 있어, 검수 사이클에서는 0이고 "
              "계산하지 않습니다.",
        "zh": "字数上限只在字触发伤害（尚未建模）且同时积累 3 个字时才有意义，已审核循环中为 0，不计算。",
        "en": "The word cap matters only for word-trigger damage (not modelled yet) and when three words are held at "
              "once; it is 0 in the reviewed rotation and not priced.",
        "ja": "文字の上限は文字発動ダメージ（未モデル化）と文字が同時に3つ溜まるときにだけ意味があり、審査済みサイクル"
              "では0なので計算しません。"}),
    (CANG, "Effect4", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ④는 회복만 하므로 피해 계산에서는 0입니다.",
        "zh": "觉醒效果④只有回复，伤害计算中为 0。",
        "en": "Awakening Effect ④ only heals, so it is 0 in the damage calculation.",
        "ja": "覚醒効果④は回復のみなので、ダメージ計算では0です。"}),
    (CANG, "Effect5", "damage", "now", "low", "solo_team", {
        "ko": "판결의 가을 영역은 전개 타격 직후 시작해 2초마다 1틱(12초 6틱, 돌파 효과 ⑤면 16초 8틱)이라고 보며, "
              "계산에서 빠져 있던 이 틱을 기본 키트 보충으로 넣었습니다(돌파 0 기준치도 같이 오릅니다). 단, 게임 "
              "데이터의 영역 지속 피해 효과 자체 지속은 20초라, 틱이 영역(12/16초)이 아니라 이 20초를 따른다면 돌파 "
              "효과 ⑤의 틱 몫은 0이 되고 돌파 0 기준치 상승은 3바퀴 +28.0%가 됩니다.",
        "zh": "判予秋领域视为在展开命中之后开始、每 2 秒 1 跳（12 秒 6 跳，觉醒效果⑤时 16 秒 8 "
              "跳）；原本计算中缺少的这些跳已作为基础技能补充计入（觉醒 0 "
              "的基准值也随之上升）。但数据中领域持续伤害效果本身的持续时间为 20 秒，若跳数跟随这 20 "
              "秒而非领域（12/16 秒），觉醒效果⑤的跳伤份额为 0，觉醒 0 基准值在 3 轮中上升 +28.0%。",
        "en": "The Autumn's Verdict field is taken to start right after the unfold hit and tick every 2 s (12 s = 6 "
              "ticks, 16 s = 8 ticks with Awakening Effect ⑤); these ticks, missing before, are now added as a "
              "base-kit supplement (the awakening-0 baseline rises too). The game data's field DoT effect itself "
              "lasts 20 s, though: if the ticks follow those 20 s instead of the field (12/16 s), Awakening Effect "
              "⑤'s tick share is 0 and the awakening-0 baseline rises +28.0% over 3 loops.",
        "ja": "判予秋の領域は展開ヒットの直後に始まり2秒ごとに1回（12秒で6回、覚醒効果⑤なら16秒で8回）と見なし、計算"
              "から抜けていたこの継続ダメージを基本キットの補足として入れました（覚醒0の基準値も上がります）。ただし"
              "ゲームデータの領域継続ダメージ効果自体の持続は20秒なので、領域（12/16秒）ではなくこの20秒に従うなら、"
              "覚醒効果⑤の継続ダメージ分は0になり、覚醒0の基準値は3周で+28.0%上がります。"}),
    (CANG, "Effect6", "damage", "now", "medium", "solo_team", {
        "ko": "돌파 효과 ⑥의 치명 확률 +30%는 영역이 생긴 직후(전개 타격 다음)부터 12초(돌파 효과 ⑤면 16초) 동안 백장의 "
              "타격에 붙고, 고정 치명률인 영역 틱에는 붙지 않는다고 봅니다.",
        "zh": "觉醒效果⑥的暴击率 +30% 视为从领域生成之后（展开命中之后）起 12 秒（觉醒效果⑤时 16 秒）作用于白藏的命中，"
              "不作用于固定暴击率的领域跳伤。",
        "en": "Awakening Effect ⑥'s CRIT Rate +30% is taken to apply to Baicang's hits for 12 s (16 s with Awakening "
              "Effect ⑤) from right after the field appears (after the unfold hit), not to the field ticks, whose crit "
              "rate is fixed.",
        "ja": "覚醒効果⑥の会心率+30%は、領域が生まれた直後（展開ヒットの後）から12秒（覚醒効果⑤なら16秒）白蔵のヒット"
              "にかかり、会心率固定の領域継続ダメージにはかからないと見なします。"}),
    (CANG, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3은 지금 엔진이 계산하지만, SkillA 폭발 2타가 1레벨로 계산되는 기존 문제 때문에 실제보다 약 0.7%p 작게 "
              "나옵니다.",
        "zh": "共鸣3 由现有引擎计算，但由于 SkillA 爆发第 2 段按 1 级计算的既有问题，结果比实际约小 0.7 个百分点。",
        "en": "Resonance 3 is priced by the engine, but an existing issue (the second SkillA burst hit is priced at skill "
              "level 1) makes it about 0.7 pp lower than it should be.",
        "ja": "共鳴3は現在のエンジンが計算しますが、SkillA爆発の2ヒット目がレベル1で計算される既存の問題のため、実際より"
              "約0.7ポイント小さく出ます。"}),
    (CANG, "resonance_6", "damage", "now", "medium", "solo_team", {
        "ko": "공명6의 공격력 +20%는 영역 지속 동안 필드에 있는 팀원 전원(백장 포함)에게 걸린다고 보며, 즉결처형은 피해 "
              "계산과 무관해 넣지 않습니다.",
        "zh": "共鸣6 的攻击力 +20% 视为在领域持续期间作用于场上的全部队员（含白藏）；即刻斩杀与伤害计算无关，不计入。",
        "en": "Resonance 6's ATK +20% is taken to apply to every team member on the field (Baicang included) while the "
              "field lasts; the instant execution has nothing to do with the damage calculation and is left out.",
        "ja": "共鳴6の攻撃力+20%は領域の持続中、フィールドにいる味方全員（白蔵を含む）にかかると見なし、即時処刑は"
              "ダメージ計算と無関係なので入れません。"}),
    # 1025 Hathor
    (HATHOR, "Effect1", "review", "measure", "low", "", {
        "ko": "돌파 효과 ①의 스피드퀵 6중첩(게임 데이터 값)은 지금은 돌파 효과 ⑤(획득 중첩당 피해 +1%)에만 반영하고, "
              "긴급 배송 중 중첩당 공격력 증가는 값이 확인되지 않아 넣지 않습니다. 보유 상한 6을 넘는 획득도 돌파 "
              "효과 ⑤에 센다고 보며, 상한을 적용하면 6돌파에서 뺀 값이 +3.4%에서 +2.4%로 줄어듭니다.",
        "zh": "觉醒效果①的闪送之力 6 层（数据值）目前只体现在觉醒效果⑤（每获得 1 层伤害 +1%）中；紧急派送期间每层的攻击力"
              "提升因数值未确认而不计入。超过持有上限 6 的获得也计入觉醒效果⑤；若套用上限，从 6 次觉醒中去掉此效果的差值会"
              "从 +3.4% 降到 +2.4%。",
        "en": "Awakening Effect ①'s 6 stacks of Power of Flash Delivery (game data value) are reflected only through "
              "Awakening Effect ⑤ (+1% damage per stack gained); the ATK per stack during Emergency Delivery is left "
              "out because its value is unconfirmed. Gains above the holding cap of 6 still count for Awakening "
              "Effect ⑤; with the cap, the value of removing it from a full 6 drops from +3.4% to +2.4%.",
        "ja": "覚醒効果①の速達の力6層（ゲームデータの値）は今のところ覚醒効果⑤（獲得1層ごとにダメージ+1%）にだけ反映"
              "し、緊急配送中の1層ごとの攻撃力アップは数値が未確認のため入れません。保有上限6を超える獲得も覚醒効果⑤"
              "に数えると見なし、上限を適用すると覚醒6から外したときの差は+3.4%から+2.4%に減ります。"}),
    (HATHOR, "Effect2", "review", "measure", "low", "", {
        "ko": "돌파 효과 ②는 '만점 추적'이 손을 뗀 뒤 5초에 자연 종료될 때 공격 반응과 같은 3중첩(게임 데이터에 수치 "
              "없음)을 준다고 보지만, 검수 사이클에서는 그 시점이 늘 긴급 배송(중첩 획득 불가) 안이라 1인 값은 "
              "0이고, 팀에서 교대로 긴급 배송이 먼저 끝날 때만 값이 생깁니다.",
        "zh": "觉醒效果②视为在“满星追踪”松手后 5 秒自然结束时给予与受到攻击时相同的 3 层（数据中无数值）；但已审核循环中"
              "该时刻总在紧急派送内（无法获得层数），单人值为 0，只有在队伍中因切人使紧急派送先结束时才有值。",
        "en": "Awakening Effect ② is taken to give the same 3 stacks as an attack reaction (no value in the game "
              "data) when Full-Star Tracking ends naturally 5 s after the release; in the reviewed rotation that "
              "moment always falls inside Emergency Delivery (no stacks gained), so the solo value is 0 and it only "
              "counts in a team when a swap ends Emergency Delivery first.",
        "ja": "覚醒効果②は「満星追跡」が手を離してから5秒で自然終了したときに攻撃反応と同じ3層（ゲームデータに数値な"
              "し）を与えると見なしますが、審査済みサイクルではその時点が常に緊急配送中（層を獲得できない）なので単独"
              "値は0で、チームで交代により緊急配送が先に終わる場合にだけ値が出ます。"}),
    (HATHOR, "Effect3", "damage", "now", "high", "solo_team", {
        "ko": "효율표 대상은 '보스가 아닌 Lv80 목각인형'이므로 돌파 효과 ③의 비보스 피해 +15%를 항상 적용합니다(보스 기준으로 "
              "보면 0%입니다).",
        "zh": "效率表的目标是“非首领的 80 级木桩”，因此觉醒效果③的非首领增伤 +15% 始终生效（若按首领计算则为 0%）。",
        "en": "The efficiency table's target is a non-boss Lv80 training dummy, so Awakening Effect ③'s +15% damage "
              "against non-bosses always applies (0% against a boss).",
        "ja": "効率表の対象は「ボスではないLv80の木人」なので、覚醒効果③の非ボスへのダメージ+15%を常に適用します（ボス"
              "相手なら0%です）。"}),
    (HATHOR, "Effect4", "damage", "now", "low", "solo_team", {
        "ko": "돌파 효과 ④는 싸이클론 스트라이크 1·2·3단을 각각 한 번의 '시전'으로 보고 2·3단의 치명 확률을 "
              "+25%·+50% 올립니다(졸업 템플릿 치명 83%라 둘 다 100% 상한). 게임 데이터에서 1·2·3단은 한 스킬의 "
              "몽타주 구간이라, 세 단 전체가 한 번의 시전이면 돌파 효과 ④ 값은 0입니다.",
        "zh": "觉醒效果④把轮转打击的一、二、三段各视为一次“释放”，使第二、三段的暴击率 +25%、+50%（毕业模板暴击率 83%，"
              "两段都到 100% 上限）。数据中一、二、三段是同一技能的蒙太奇片段，若三段合起来才算一次释放，觉醒效果④的值为 0。",
        "en": "Awakening Effect ④ counts Rotating Strike segments 1, 2 and 3 as one 'cast' each and raises the CRIT "
              "Rate of segments 2 and 3 by +25% and +50% (the graduation template's 83% crit reaches the 100% cap "
              "either way). In the game data the three segments are montage sections of one skill; if all three "
              "together are one cast, Awakening Effect ④ is worth 0.",
        "ja": "覚醒効果④は輪転打撃の1・2・3段をそれぞれ1回の「発動」と見なし、2・3段の会心率を+25%・+50%上げます（卒"
              "業テンプレートの会心率83%なので、どちらも100%の上限）。ゲームデータでは1・2・3段は1つのスキルのモンタ"
              "ージュ区間なので、3段全体で1回の発動なら覚醒効果④の値は0です。"}),
    (HATHOR, "Effect5", "damage", "now", "low", "solo_team", {
        "ko": "돌파 효과 ⑤는 긴급 배송 밖에서 실제로 얻은 스피드퀵 수(공중 지령 시전 +2, 돌파 효과 ① +6, 돌파 효과 ② "
              "+3)를 누적해 1중첩당 피해 +1%(최대 15%)로 계산합니다. +2는 게임 데이터 이름상 짧게 누르기 전용일 수 "
              "있어(검수 사이클은 길게 누르기) 그러면 돌파 효과 ⑤ 단독 값은 0이고, 보유 상한 6을 넘는 획득을 세지 "
              "않으면 6돌파에서 뺀 값이 줄어듭니다.",
        "zh": "觉醒效果⑤累计在紧急派送之外实际获得的闪送之力层数（空中指令释放 +2、觉醒效果① +6、觉醒效果② +3），每层伤害 "
              "+1%（至多 15%）。按数据命名，+2 可能只适用于短按（已审核循环为长按），那样觉醒效果⑤单独的值为 0；若不计超过"
              "持有上限 6 的获得，从 6 次觉醒中去掉此效果的差值会变小。",
        "en": "Awakening Effect ⑤ adds up the Power of Flash Delivery stacks actually gained outside Emergency "
              "Delivery (+2 per Aerial Command cast, +6 from Awakening Effect ①, +3 from Awakening Effect ②) at +1% "
              "damage per stack (max 15%). By its game data name the +2 may be for taps only (the reviewed rotation "
              "holds); then Awakening Effect ⑤ alone is worth 0, and not counting gains above the holding cap of 6 "
              "lowers the value of removing it from a full 6.",
        "ja": "覚醒効果⑤は緊急配送の外で実際に獲得した速達の力の層数（空中指令の発動+2、覚醒効果①+6、覚醒効果②+3）を"
              "累積し、1層ごとにダメージ+1%（最大15%）として計算します。+2はゲームデータ上の名前から短押し専用の可能"
              "性があり（審査済みサイクルは長押し）、その場合は覚醒効果⑤単独の値は0で、保有上限6を超える獲得を数えな"
              "ければ覚醒6から外したときの差は小さくなります。"}),
    (HATHOR, "Effect6", "damage", "now", "medium", "solo_team", {
        "ko": "긴급 배송은 울티메이트 시작 1.5초 뒤부터 싸이클론 스트라이크 마지막 타격까지로 보고(검수 사이클이 게임 데이터 "
              "5초보다 4.2초 길게 이어짐), 그 사이 하토르의 모든 타격(울티메이트 마지막 일격 포함)에 치명 피해 +30%를 줍니다.",
        "zh": "紧急派送视为从终结技开始 1.5 秒后持续到轮转打击的最后一击（已审核循环比游戏数据的 5 秒长 4.2 秒），其间哈索尔"
              "的所有命中（含终结技最后一击）暴击伤害 +30%。",
        "en": "Emergency Delivery is taken to run from 1.5 s after the ultimate starts until the last Rotating Strike "
              "hit (the reviewed rotation runs 4.2 s past the game data's 5 s); all of Hathor's hits in between (the "
              "ultimate's final slam included) get Crit DMG +30%.",
        "ja": "緊急配送はアルティメット開始の1.5秒後から輪転打撃の最後のヒットまでと見なし（審査済みサイクルはゲーム"
              "データの5秒より4.2秒長く続く）、その間のハトホルの全ヒット（アルティメットの最後の一撃を含む）に会心ダ"
              "メージ+30%を与えます。"}),
    (HATHOR, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3은 지금 엔진이 그대로 계산합니다.",
        "zh": "共鸣3 由现有引擎直接计算。",
        "en": "Resonance 3 is priced by the engine as is.",
        "ja": "共鳴3は現在のエンジンがそのまま計算します。"}),
    (HATHOR, "resonance_6", "damage", "now", "medium", "solo_team", {
        "ko": "공명6의 방어 10% 무시는 돌파 효과 ⑥과 같은 긴급 배송 구간에 적용합니다.",
        "zh": "共鸣6 的无视防御 10% 作用于与觉醒效果⑥相同的紧急派送区间。",
        "en": "Resonance 6's 10% DEF ignore applies over the same Emergency Delivery window as Awakening Effect ⑥.",
        "ja": "共鳴6の防御無視10%は覚醒効果⑥と同じ緊急配送の区間に適用します。"}),
    # 1033 Adler
    (ADLER, "Effect1", "damage", "now", "medium", "solo_team", {
        "ko": "업 중첩은 시간이 지나도 사라지지 않고(게임 데이터 지속 정책 '무한'), 돌파 효과 ①의 20중첩은 다음 "
              "E에서 모두 소비되어 그 E의 피해를 최종 피해 구간에서 중첩당 2%(돌파 효과 ②면 3%) 올린다고 봅니다(15초 "
              "만료가 있더라도 검수 사이클에서는 다음 E가 Q가 끝나고 12.4초 안에 와서 값이 같습니다).",
        "zh": "「业」层数不会随时间消失（数据持续策略为“无限”）；觉醒效果①的 20 层在下一次 E 时全部消耗，使该 E 的伤害在最终"
              "伤害区每层提高 2%（觉醒效果②时为 3%）（即使有 15 秒过期，已审核循环中下一次 E 在 Q 结束后 12.4 秒内到来，值"
              "不变）。",
        "en": "'Karma' stacks are taken not to expire (game data duration policy 'infinite'); Awakening Effect ①'s "
              "20 stacks are all consumed by the next E, raising that E's damage in the final-damage zone by 2% per "
              "stack (3% with Awakening Effect ②) (even with a 15 s expiry the value is the same in the reviewed "
              "rotation, where the next E comes within 12.4 s after the Q ends).",
        "ja": "「業」の層は時間で消えず（ゲームデータの持続ポリシー「無限」）、覚醒効果①の20層は次のEで全て消費され、"
              "そのEのダメージを最終ダメージ枠で1層ごとに2%（覚醒効果②なら3%）上げると見なします（15秒の期限があって"
              "も、審査済みサイクルでは次のEがQ終了後12.4秒以内に来るので値は同じです）。"}),
    (ADLER, "Effect2", "damage", "now", "medium", "solo_team", {
        "ko": "돌파 효과 ②는 업 1중첩당 피해를 3%로 올릴 뿐이라, 일반 공격이 없는 검수 사이클에서는 돌파 효과 ①이 있을 때만 "
              "값이 생깁니다.",
        "zh": "觉醒效果②只是把每层「业」的增伤提高到 3%，在没有普通攻击的已审核循环中，只有同时选择觉醒效果①时才有值。",
        "en": "Awakening Effect ② only raises the damage per 'Karma' stack to 3%, so in the reviewed rotation, which has "
              "no basic attacks, it is worth something only together with Awakening Effect ①.",
        "ja": "覚醒効果②は「業」1層あたりのダメージを3%に上げるだけなので、通常攻撃のない審査済みサイクルでは覚醒効果①が"
              "あるときだけ値が出ます。"}),
    (ADLER, "Effect3", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ③은 보호막 흡수량만 올리므로 0입니다.",
        "zh": "觉醒效果③只提高护盾吸收量，因此为 0。",
        "en": "Awakening Effect ③ only raises shield absorption, so it is 0.",
        "ja": "覚醒効果③はシールド吸収量を上げるだけなので0です。"}),
    (ADLER, "Effect4", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ④는 보호막이 깨질 때만 작동하고 피격이 없어 0입니다.",
        "zh": "觉醒效果④只在护盾破碎时生效，模拟中没有受击，因此为 0。",
        "en": "Awakening Effect ④ only works when the shield breaks, and nothing hits the team, so it is 0.",
        "ja": "覚醒効果④はシールドが割れたときだけ働き、被弾がないので0です。"}),
    (ADLER, "Effect5", "resource", "now", "high", "resource_only", {
        "ko": "궁극기 비용을 아직 검사하지 않으므로 돌파 효과 ⑤의 에너지 +20은 팀 시뮬 자원 표에만 보이고 피해·시간은 "
              "바뀌지 않습니다.",
        "zh": "终结技消耗尚未检查，因此觉醒效果⑤的能量 +20 只显示在队伍模拟的资源表中，伤害与时间不变。",
        "en": "The ultimate's cost is not checked yet, so Awakening Effect ⑤'s +20 energy only shows in the team "
              "simulation's resource table; damage and time do not change.",
        "ja": "アルティメットのコストはまだ検査していないため、覚醒効果⑤のエネルギー+20はチームシミュレーションの資源"
              "表にだけ表示され、ダメージと時間は変わりません。"}),
    (ADLER, "Effect6", "damage", "now", "medium", "solo_team", {
        "ko": "돌파 효과 ⑥은 보호막을 12초로 늘려 공명6(주속성 피해 +10%) 시간을 4초 늘리는 만큼만 피해에 반영합니다.",
        "zh": "觉醒效果⑥把护盾延长到 12 秒，只按共鸣6（咒属性伤害 +10%）延长 4 秒的部分计入伤害。",
        "en": "Awakening Effect ⑥ lengthens the shield to 12 s and is priced only through the 4 s it adds to Resonance 6 "
              "(Incantation damage +10%).",
        "ja": "覚醒効果⑥はシールドを12秒に延ばし、共鳴6（呪属性ダメージ+10%）の時間が4秒延びる分だけダメージに反映します。"}),
    (ADLER, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3은 지금 엔진이 그대로 계산합니다.",
        "zh": "共鸣3 由现有引擎直接计算。",
        "en": "Resonance 3 is priced by the engine as is.",
        "ja": "共鳴3は現在のエンジンがそのまま計算します。"}),
    (ADLER, "resonance_6", "damage", "now", "low", "solo_team", {
        "ko": "공명6은 E 보호막이 걸린 뒤(설명문상 E 타격 다음, E 시작 0.57초) 8초(돌파 효과 ⑥이면 12초) 동안 팀 전체 주속성 "
              "피해 +10%로 보며, E 자신의 직접 타격에는 붙지 않습니다(E 시작부터로 보면 1바퀴 +7.7%, 버프 자체 지속 60초로 보면 "
              "3바퀴 +6.2%).",
        "zh": "共鸣6 视为在 E 的护盾生成之后（说明文中为 E 命中之后，E 开始后 0.57 秒）8 秒（觉醒效果⑥时 12 秒）内全队咒属性"
              "伤害 +10%，不作用于 E 自身的直接命中（若从 E 开始算，1 轮为 +7.7%；若按增益本身 60 秒的持续时间，3 轮为 "
              "+6.2%）。",
        "en": "Resonance 6 is taken as team Incantation damage +10% for 8 s (12 s with Awakening Effect ⑥) after the E's "
              "shield lands (after the E's hits by the description, 0.57 s after the E starts), not on the E's own "
              "direct hits (counting from the E's start gives +7.7% over 1 loop; the buff's own 60 s duration gives "
              "+6.2% over 3 loops).",
        "ja": "共鳴6はEのシールドがかかった後（説明文ではEのヒットの後、E開始から0.57秒）8秒（覚醒効果⑥なら12秒）、チーム"
              "全体の呪属性ダメージ+10%と見なし、E自身の直接ヒットにはかかりません（E開始からなら1周+7.7%、バフ自体の持続"
              "60秒なら3周+6.2%）。"}),
    # 1036 Zankou
    (ZANKOU, "Effect1", "damage", "now", "high", "solo_team", {
        "ko": "돌파 효과 ①(사냥·현혹 상시)은 지금 엔진이 그대로 계산합니다(단일 대상이라 지속 피해 확산은 의미 없음).",
        "zh": "觉醒效果①（狩、惑常驻）由现有引擎直接计算（单一目标，持续伤害扩散没有意义）。",
        "en": "Awakening Effect ① (Hunt and Allure always on) is priced by the engine as is (single target, so the DoT "
              "spread does not matter).",
        "ja": "覚醒効果①（狩・惑の常時化）は現在のエンジンがそのまま計算します（単一対象なので継続ダメージの拡散は無意味）。"}),
    (ZANKOU, "Effect2", "team", "now", "medium", "team_only", {
        "ko": "돌파 효과 ②는 잔홍이 교대 양쪽 중 하나인 스코치·헥스 반응이 나면 다음 '타버린 종말의 춤'(돌파 효과 ④가 있으면 "
              "'핏기 어린 꿈'도) 피해를 최종 2.5배로 한다고 보며, 팀 시뮬의 반응 기록으로 직접 계산합니다(엔진의 판정은 "
              "시뮬레이터의 반응 행을 인식하지 못해 0이었습니다).",
        "zh": "觉醒效果②视为：残虹作为切人双方之一触发浊燃或覆纹反应后，下一次「焚天烬灭舞」（有觉醒效果④时「血宴入梦时」也"
              "同样）伤害最终 ×2.5；按队伍模拟的反应记录直接计算（引擎的判定无法识别模拟器的反应行，原本为 0）。",
        "en": "Awakening Effect ② is taken as: after a Scorch or Hex reaction with Zankou on either side of the swap, the "
              "next Skyburning Ashfall Dance (with Awakening Effect ④ also When the Blood Feast Enters Dreams) deals "
              "×2.5 final damage; it is priced directly from the team simulation's reactions (the engine's own check "
              "did not recognise the simulator's reaction rows and gave 0).",
        "ja": "覚醒効果②は、残虹が交代の片側となる濁燃・覆紋反応が起きると、次の「焚天燼滅の舞」（覚醒効果④があれば「血の"
              "宴、夢に入る時」も）のダメージを最終2.5倍にすると見なし、チームシミュレーションの反応記録から直接計算します"
              "（エンジン側の判定はシミュレーターの反応行を認識できず0でした）。"}),
    (ZANKOU, "Effect3", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ③은 경직 저항과 회복이라 피해 계산에서는 0입니다.",
        "zh": "觉醒效果③是抗打断与回复，伤害计算中为 0。",
        "en": "Awakening Effect ③ is interrupt resistance and healing, so it is 0 in the damage calculation.",
        "ja": "覚醒効果③は怯み耐性と回復なので、ダメージ計算では0です。"}),
    (ZANKOU, "Effect4", "team", "now", "medium", "team_only", {
        "ko": "검수 사이클은 강화 갈라진 영혼('멸')으로 핏기 어린 꿈을 여는 정식 경로를 쓰므로 돌파 효과 ④ 없이도 그대로 "
              "성립하고, 돌파 효과 ④는 돌파 효과 ②의 축염을 핏기 어린 꿈에도 주는 팀 효과로만 계산합니다.",
        "zh": "已审核循环通过强化离魂错（「灭」）开启血宴入梦时的正式路径，没有觉醒效果④也成立；觉醒效果④只按把觉醒效果②的"
              "蓄焰也给予血宴入梦时的队伍效果计算。",
        "en": "The reviewed rotation opens When the Blood Feast Enters Dreams through the regular path (enhanced Soulstray "
              "Error, 'Ruin'), so it holds without Awakening Effect ④; Awakening Effect ④ is priced only as the team "
              "effect that also gives Awakening Effect ②'s Stored Flame to When the Blood Feast Enters Dreams.",
        "ja": "審査済みサイクルは強化離魂錯（「滅」）で「血の宴、夢に入る時」を開く正規ルートを使うため覚醒効果④なしでも成立"
              "し、覚醒効果④は覚醒効果②の蓄炎を「血の宴、夢に入る時」にも与えるチーム効果としてだけ計算します。"}),
    (ZANKOU, "Effect5", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ⑤는 붕괴 피해를 올리는데, 효율표 대상은 붕괴가 없어 0입니다.",
        "zh": "觉醒效果⑤提高倾陷伤害，效率表的目标没有倾陷，因此为 0。",
        "en": "Awakening Effect ⑤ raises Break damage, and the efficiency table's target is never broken, so it is 0.",
        "ja": "覚醒効果⑤はブレイクダメージを上げますが、効率表の対象はブレイクしないので0です。"}),
    (ZANKOU, "Effect6", "damage", "now", "medium", "solo_team", {
        "ko": "돌파 효과 ⑥은 '멸'의 마지막 타격(강화 갈라진 영혼 7타)이 맞는 순간 대상에게 있는 지속 피해 중첩 수(침식·독화) "
              "× 12%(최대 240%)를 다른 피해 증가와 합연산한다고 봅니다(팀원의 지속 피해 중첩은 아직 세지 않습니다).",
        "zh": "觉醒效果⑥视为在「灭」最后一击（强化离魂错第 7 段）命中时，按目标身上的持续伤害层数（蚀心、鸩火）× 12%（至多 "
              "240%）与其他增伤加算（队友的持续伤害层数暂不计入）。",
        "en": "Awakening Effect ⑥ is taken to add 12% per DoT stack on the target (Heart Erosion, Venomfire) at the "
              "moment Ruin's last hit (enhanced Soulstray Error hit 7) lands, up to 240%, additively with the other "
              "damage bonuses (teammates' DoT stacks are not counted yet).",
        "ja": "覚醒効果⑥は「滅」の最後のヒット（強化離魂錯7ヒット目）が当たった瞬間に対象にある継続ダメージの層数（蝕心・"
              "鴆火）×12%（最大240%）を他のダメージアップと加算すると見なします（味方の継続ダメージの層はまだ数えません）。"}),
    (ZANKOU, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3(스킬 레벨 +1과 울티메이트 배율 1.2배)은 지금 엔진이 그대로 계산합니다.",
        "zh": "共鸣3（技能等级 +1 与终结技倍率 ×1.2）由现有引擎直接计算。",
        "en": "Resonance 3 (skill level +1 and the ultimate's multiplier ×1.2) is priced by the engine as is.",
        "ja": "共鳴3（スキルレベル+1とアルティメット倍率1.2倍）は現在のエンジンがそのまま計算します。"}),
    (ZANKOU, "resonance_6", "damage", "now", "high", "solo_team", {
        "ko": "공명6의 공격력 +40%는 지금 엔진이 계산하며, 처치 후 강화 부분은 처치가 없어 넣지 않습니다.",
        "zh": "共鸣6 的攻击力 +40% 由现有引擎计算；击败后的强化部分因没有击败而不计入。",
        "en": "Resonance 6's ATK +40% is priced by the engine; the part that strengthens after a kill is left out "
              "because nothing is killed.",
        "ja": "共鳴6の攻撃力+40%は現在のエンジンが計算し、撃破後の強化部分は撃破がないので入れません。"}),
    # 1039 Fadia
    (FADIA, "Effect1", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ①은 피해 분담 비율만 바꾸고 피격이 없어 0입니다.",
        "zh": "觉醒效果①只改变伤害分担比例，模拟中没有受击，因此为 0。",
        "en": "Awakening Effect ① only changes the damage-sharing ratio, and nothing hits the team, so it is 0.",
        "ja": "覚醒効果①はダメージ分担の比率を変えるだけで、被弾がないので0です。"}),
    (FADIA, "Effect2", "review", "measure", "low", "", {
        "ko": "돌파 효과 ②는 아군 피격이 없으므로 '파멸 체험'이 15초 뒤 끝날 때 상한 전부(파디아 최대 HP의 25%)를 피해로 "
              "준다고 보지만, 이 피해가 방어·저항·치명을 거치는지 확인되지 않아 계산에 넣지 않았습니다(측정 필요, 3바퀴 약 "
              "+10.0~10.7% 추정).",
        "zh": "觉醒效果②视为：因我方不受击，「破灭体验」在 15 秒后结束时以上限全额（法帝娅最大生命值的 25%）造成伤害；但该伤害"
              "是否经过防御、抗性与暴击尚未确认，因此未计入（需要实测；3 轮估计约 +10.0~10.7%）。",
        "en": "With no hits taken by the team, Awakening Effect ② is taken to deal its full cap (25% of Fadia's max HP) "
              "as damage when Ruin Experience ends after 15 s; whether that damage goes through DEF, resistance and "
              "crit is unconfirmed, so it is not priced (needs measurement; about +10.0 to +10.7% over 3 loops by "
              "estimate).",
        "ja": "味方の被弾がないため、覚醒効果②は「破滅体験」が15秒後に終わるとき上限全額（ファディアの最大HPの25%）を"
              "ダメージとして与えると見なしますが、このダメージが防御・耐性・会心を経るかが未確認なので計算には入れていません"
              "（実測が必要。3周で約+10.0〜10.7%の推定）。"}),
    (FADIA, "Effect3", "damage", "now", "high", "solo_team", {
        "ko": "돌파 효과 ③(전투 중 HP +30%)은 지금 엔진이 그대로 계산합니다.",
        "zh": "觉醒效果③（战斗中生命值 +30%）由现有引擎直接计算。",
        "en": "Awakening Effect ③ (HP +30% in battle) is priced by the engine as is.",
        "ja": "覚醒効果③（戦闘中HP+30%）は現在のエンジンがそのまま計算します。"}),
    (FADIA, "Effect4", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ④는 회복량만 바꾸므로 0입니다.",
        "zh": "觉醒效果④只改变回复量，因此为 0。",
        "en": "Awakening Effect ④ only changes healing, so it is 0.",
        "ja": "覚醒効果④は回復量だけを変えるので0です。"}),
    (FADIA, "Effect5", "damage", "now", "low", "solo_team", {
        "ko": "돌파 효과 ⑤의 치명 확률 +50%는 원본 계산기의 규칙처럼 '적신자' 추격 타격에만 붙이고, 추격은 그 "
              "상태에서만 쓸 수 있으므로 시간 창 대신 추격 단계 전체에 적용합니다. 게임 데이터의 치명 버프 자체에는 "
              "타격 제한이 없어, Q의 6타도 '적신자' 상태 안이라면 값이 약 +8%p 더 커집니다.",
        "zh": "觉醒效果⑤的暴击率 +50% 按原版计算器的规则只作用于「敌神者」追击命中；追击只能在该状态下使用，因此不用"
              "时间窗而作用于整个追击步骤。数据中的暴击增益本身没有命中限制，若 Q 的 6 "
              "段也在「敌神者」状态内，值会再大约 8 个百分点。",
        "en": "Awakening Effect ⑤'s CRIT Rate +50% is applied, as in the original calculator's rule, only to the "
              "Godfoe chase hits; the chase can only be used in that state, so it covers the whole chase step "
              "instead of a time window. The game data's crit buff itself has no hit restriction: if the Q's 6 hits "
              "are also inside the Godfoe state, the value grows by about 8 pp.",
        "ja": "覚醒効果⑤の会心率+50%は元の計算機のルールどおり「敵神者」の追撃ヒットにだけ付け、追撃はその状態でしか"
              "使えないため、時間枠ではなく追撃ステップ全体に適用します。ゲームデータの会心バフ自体にはヒットの制限が"
              "ないので、Qの6ヒットも「敵神者」状態内なら値は約8ポイント大きくなります。"}),
    (FADIA, "Effect6", "none", "not_computable", "high", "", {
        "ko": "돌파 효과 ⑥은 대상 수만 늘려 단일 대상 기준에서는 0입니다.",
        "zh": "觉醒效果⑥只增加目标数量，单一目标下为 0。",
        "en": "Awakening Effect ⑥ only adds targets, so it is 0 against a single target.",
        "ja": "覚醒効果⑥は対象数を増やすだけなので、単一対象では0です。"}),
    (FADIA, "resonance_3", "damage", "now", "high", "solo_team", {
        "ko": "공명3은 지금 엔진이 그대로 계산합니다.",
        "zh": "共鸣3 由现有引擎直接计算。",
        "en": "Resonance 3 is priced by the engine as is.",
        "ja": "共鳴3は現在のエンジンがそのまま計算します。"}),
    (FADIA, "resonance_6", "damage", "now", "high", "solo_team", {
        "ko": "공명6(팀 HP +10%)은 지금 엔진이 계산하며 HP 계수 캐릭터에만 피해 차이가 납니다.",
        "zh": "共鸣6（队伍生命值 +10%）由现有引擎计算，只有以生命值计算伤害的角色才有伤害差异。",
        "en": "Resonance 6 (team HP +10%) is priced by the engine; only HP-scaling characters see a damage difference.",
        "ja": "共鳴6（チームHP+10%）は現在のエンジンが計算し、HP依存のキャラクターにだけダメージ差が出ます。"}),
)

for _cid, _node, _category, _bucket, _confidence, _scope, _text in _NODES:
    RULES.node(_cid, _node, category=_category, bucket=_bucket, confidence=_confidence, assumption=_text,
               scope=_scope if _bucket == "now" else "")
