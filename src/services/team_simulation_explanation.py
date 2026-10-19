# 队伍模拟：结果下方「使用的循环」说明面板的数据（只存代码、数值与中文名，切换语言时由页面重新渲染）。
"""Explanation data for the team simulator's "rotation used" panel.

``src.services.team_simulation_service`` fills one :class:`TeamExplanation` per run and the page
renders it with ``src.features.team_simulation.explanation_view.render_explanation``.

Everything stored here is language-neutral: logic codes (entry / outcome / status / note codes),
numbers, character ids, element codes (``"cosmos"`` ...) and Chinese game names (reaction names
such as 浊燃, ability names).  No translated text is stored, so a live language switch only has
to re-render.  Note and effect codes turn into ``_L`` / ``_LF`` source strings through
:func:`note_text` / :func:`effect_text`, which build the text when called (active language, with
provenance so the display layer can re-render it).

Times are seconds from the battle start (the simulator's ``START_US`` already subtracted) on the
wall clock (time stops included), except fields whose name says ``active``.  ``FormTrace`` durations,
``used_s`` / ``exit_s`` / ``window`` are seconds of the form clock (active time from the form start).

Loop / gauge rule: ``TeamExplanation.full_gauge_loops`` lists the 1-based loops that started with every
gauge at 100 (``team_cycle_reactions.FULL_GAUGE_LOOPS``), ``VisitTrace.refilled`` flags their visits.
Transformation damage dealers: ``VisitTrace.form`` (:class:`FormTrace`) and ``StepTrace.form_role``.
Order mode "plan": ``TeamExplanation.plan`` (:class:`PlanTrace`) holds every candidate order and the reasons.
Custom-cycle mode ("直接输入"): ``TeamExplanation.custom`` (:class:`CustomCycleTrace`) holds the typed sequence,
one :class:`CustomStepTrace` per executed step and the options used; ``order_mode`` is ``"custom"``.

Note items (``TeamExplanation.assumptions`` / ``limits``) and effect items
(``ReactionTrace.effects``) may be written as

* a bare code: ``"opening_full"``
* ``"code:arg[,arg...]"``: ``"time_stop_unknown:1036"`` (arguments stay strings)
* a tuple ``(code, (args...))``, preferably built with :func:`note` / :func:`effect`.
"""
from __future__ import annotations

from src.i18n_runtime import L as _L, LF as _LF

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

# ── elements and reactions (game data names stay Chinese; the display layer translates them) ──
ELEMENT_RING = ("cosmos", "nature", "incantation", "chaos", "psyche", "lakshana")   # adjacent = neighbours
ELEMENT_LABELS = {
    "cosmos": "光", "nature": "灵", "incantation": "咒",
    "chaos": "暗", "psyche": "魂", "lakshana": "相",
}
REACTION_NAMES = ("创生", "覆纹", "浊燃", "黯星", "浸染", "延滞", "盈蓄", "失谐")
COMBO_REACTIONS = {"盈蓄": ("创生", "延滞"), "失谐": ("浊燃", "黯星")}

# ── option codes (simulate_team keyword values) ────────────────────────────
ORDER_AUTO = "auto"
ORDER_SLOT = "slot"
ORDER_PLAN = "plan"                    # planner: max-adjacency orders compared by simulated DPS (PlanTrace)
GAUGE_GAME = "game"
GAUGE_IDEAL = "ideal"
OPENING_FULL = "full"
OPENING_ZERO = "zero"
# custom-cycle mode (team_custom_cycle_service.simulate_custom)
ORDER_CUSTOM = "custom"                # the user typed the sequence
GAUGE_AS_TYPED = "as_typed"            # a typed support entry always plays; a short gauge only warns
GAUGE_CHECK = "check"                  # a support entry needs gauge 100 and adjacent elements, else a plain swap
OPENING_CUSTOM = "custom"              # per-member starting gauge (CustomCycleTrace.start_gauge)

# ── VisitTrace.entry ───────────────────────────────────────────────────────
ENTRY_OPENER = "opener"                # first visit of the battle (no swap before it)
ENTRY_SUPPORT_SKILL = "support_skill"  # entered with the support skill (援护技), a reaction fired
ENTRY_NORMAL = "normal"                # plain swap, support-skill step dropped

# ── SwapTrace.outcome ──────────────────────────────────────────────────────
OUTCOME_REACTION = "reaction"
OUTCOME_SAME_ELEMENT = "same_element"
OUTCOME_NOT_ADJACENT = "not_adjacent"
OUTCOME_GAUGE_SHORT = "gauge_short"    # adjacent, but the outgoing gauge was below 100 (rule "game")
OUTCOME_PLAIN_SWAP = "plain_swap"      # custom cycle: the user typed a plain swap (no support skill, no reaction)

# ── StepTrace.slot (team_rotation_data step slots, plus the normal-entry substitute) ──
SLOT_QTE = "qte"
SLOT_SKILL = "skill"
SLOT_ULTIMATE = "ultimate"
SLOT_BASIC = "basic"
SLOT_OTHER = "other"
SLOT_ENTRY = "entry"                   # NORMAL_ENTRY substitute (Appear/AirAttackEnd)

# ── StepTrace.status ───────────────────────────────────────────────────────
STEP_OK = "ok"                         # simulated: hits laid out and replayed
STEP_TIME_ONLY = "time_only"           # approved step the simulator cannot run: advances est_s only
STEP_TIME_DEFAULT = "time_default"     # time-only step without est_s: 1.0 s assumed
STEP_MISSING = "missing_candidate"     # runnable step with no exact animation match (missing_actions)
STEP_SKIPPED = "skipped_entry"         # entry-only support-skill step dropped on a normal entry
STEP_FORM_CUT = "form_cut"             # form step that did not fit the form's remaining time: not run, no time
# resource levels (team_resources): StepTrace.slot "wait" rows and skipped steps
STEP_CD_WAIT = "cd_wait"               # wait inserted before a step whose cooldown was not ready (slot "wait")
STEP_RES_WAIT = "res_wait"             # wait for an own resource (Hotori's clock) (slot "wait")
STEP_CD_SKIP = "cd_skip"               # the wait would exceed the guard / the custom maximum: step skipped
STEP_ENERGY_SHORT = "energy_short"     # the ultimate's energy pool was short: skipped (no time, no hits)
# user decision D3 (2026-10-14): in a team a step that is not ready makes the member swap out at once
STEP_SWAP_OUT = "swap_out"             # not ready (cooldown / known energy cost / own clock): swapped out, no time, no hits
STEP_SWAP_DROPPED = "swap_dropped"     # custom cycle: a typed input of the member after its early swap, not run
SLOT_WAIT = "wait"
# StepTrace.note
STEP_NOTE_FORM_NOT_ENTERED = "form_not_entered"   # form_cut because the form-starting step was skipped
STEP_NOTE_EXTRA_E = "extra_e"                      # Lacrimosa: the extra E after 5 basics (no cooldown)
STEP_NOTE_CD_NOT_READY = "cd_not_ready"            # warn policy: ran although the cooldown was not ready
STEP_NOTE_ENERGY_SHORT = "energy_short"            # warn policy: ran although the energy was short
STEP_NOTE_ALL_BLOCKED = "all_blocked"              # wait row: every member was blocked, the earliest ready one waited for
STEP_NOTE_SHORT_WAIT = "short_wait"                # wait row: less than the swap threshold (0.3 s) left, no swap (10-18)
# StepTrace.note of a swap_out row (why the step was not ready)
SWAP_REASON_CD = "cd"
SWAP_REASON_ENERGY = "energy"
SWAP_REASON_CLOCK = "clock"
# TeamExplanation.not_ready
NOT_READY_SWAP = "swap"
NOT_READY_WAIT = "wait"

# ── resource levels (TeamExplanation.resource_model) ──
RESOURCE_LEGACY = "legacy"             # the old rule: gauge 100 at loops 1 and 3, nothing checked
RESOURCE_DATA = "data"                 # game data only
RESOURCE_COMMUNITY = "community"       # game data + community (prydwen) cooldowns
RESOURCE_MODELS = (RESOURCE_LEGACY, RESOURCE_DATA, RESOURCE_COMMUNITY)

# ── StepTrace.form_role (team_rotation_data step field, plus "fill" for extra rounds inside the window) ──
FORM_ROLE_BODY = "body"                # attack run inside the form window
FORM_ROLE_FILL = "fill"                # extra round added because the window still had time
FORM_ROLE_TERMINAL = "terminal"        # finisher that must start inside the window (Raven)
FORM_ROLE_TAIL = "tail"                # presses that must start inside the window (Shinku 赤红的处决)
FORM_ROLE_EXIT = "exit"                # step that ends the form inside a time window (Zankou 灭)
FORM_ROLE_WINDOW = "window"            # step allowed only inside a window after the entry (Akane second stage)
FORM_ROLE_AFTER = "after"              # form action run after the form ended
FORM_ROLE_FREE = "free"                # form action without a window rule

# ── FormTrace.status ───────────────────────────────────────────────────────
FORM_OK = "ok"
FORM_CUT = "cut"                       # some approved form steps did not fit the window
FORM_OVERRUN = "overrun"               # approved steps kept although they run past the window (warn policy)
FORM_WINDOW_MISSED = "window_missed"   # the exit / window step started outside its allowed time

# ── ReactionTrace.status / owner_basis ─────────────────────────────────────
REACTION_COMPUTED = "computed"
REACTION_EFFECT_ONLY = "effect_only"   # Remora / Charge / Discord: no damage
REACTION_PARTIAL = "partial"           # some reaction hits could not be replayed

# (values as team_cycle_reactions.CycleReactionEvent.owner_basis writes them)
OWNER_ZANKOU = "zankou_variant"        # Zankou in the team: every Scorch is the _1036 variant
OWNER_FINAL_EFFECT = "final_effect"    # argmax base x (1+Mag/600) x crit term
OWNER_TIE_INCOMING = "tie_incoming"    # tie on final effect -> incoming member
OWNER_INCOMING = "incoming"            # marker owner (延滞)
OWNER_INCOMING_PROVISIONAL = "incoming_provisional"  # first owner pass, not re-ranked
OWNER_PER_HIT = "hit_character"        # Hexed / Stain: each increment credited to the hit's own member
OWNER_COMBO = "combo"                  # 盈蓄 / 失谐: effect only, nobody credited
OWNER_NONE = "none"
OWNER_PER_HIT_CODES = frozenset((OWNER_PER_HIT, "per_hit"))
OWNER_NOBODY_CODES = frozenset((OWNER_COMBO, OWNER_NONE))

# ── MemberRotationTrace vocab (team_rotation_data values) ──────────────────
VERDICTS = ("confirmed", "corrected", "disputed")
CONFIDENCES = ("high", "medium", "low")
ROLES = ("support", "sub", "main")
VARIANT_APPROVED = "approved"
VARIANT_CUSTOM = "custom"              # custom-cycle mode: the steps come from the typed sequence

# ── custom-cycle step notes (CustomStepTrace.notes), assumptions and limits ──
NOTE_CUSTOM_IMPLICIT_SWAP = "custom_implicit_swap"
NOTE_CUSTOM_OPENER = "custom_opener_no_reaction"
NOTE_CUSTOM_SUPPORT_NO_REACTION = "custom_support_no_reaction"
NOTE_CUSTOM_GAUGE_SHORT = "custom_gauge_short_warn"          # args: (gauge,)
NOTE_CUSTOM_DOWNGRADED_GAUGE = "custom_downgraded_gauge"     # args: (gauge,)
NOTE_CUSTOM_DOWNGRADED_ELEMENT = "custom_downgraded_element"
NOTE_CUSTOM_ENTRY_SKIPPED = "custom_entry_skipped"           # args: (character_id,)
NOTE_CUSTOM_CD_NOT_READY = "custom_cd_not_ready"             # args: (seconds left,)
NOTE_CUSTOM_CD_WAITED = "custom_cd_waited"                   # args: (seconds waited,)
NOTE_CUSTOM_CLOCK_WAITED = "custom_clock_waited"             # args: (seconds waited,) own clock (Hotori)
NOTE_CUSTOM_CLOCK_SHORT = "custom_clock_short"               # args: (clock, needed, seconds left)
NOTE_CUSTOM_ENERGY_SHORT = "custom_energy_short"             # args: (energy, cost)
NOTE_CUSTOM_NO_ANIMATION = "custom_no_animation"
NOTE_CUSTOM_STATE_ENTERED = "custom_state_entered"           # args: (state code, name_zh)
NOTE_CUSTOM_STATE_EXPIRED = "custom_state_expired"           # args: (state code, name_zh)
NOTE_CUSTOM_STATE_INACTIVE = "custom_state_inactive"         # args: (state code, name_zh)
NOTE_CUSTOM_STATE_OVERRUN = "custom_state_overrun"           # args: (state code, name_zh, seconds)
NOTE_CUSTOM_STATE_WINDOW = "custom_state_window"             # args: (state code, name_zh, elapsed, lo, hi)
NOTE_CUSTOM_ENERGY_SKIPPED = "custom_energy_skipped"         # args: (energy, cost) strict: ultimate skipped
NOTE_CUSTOM_CD_SKIPPED = "custom_cd_skipped"                 # args: (seconds left,) beyond the longest wait
NOTE_CUSTOM_SWAP_OUT = "custom_swap_out"                     # args: (reason, kind, seconds left, energy, cost) strict
NOTE_CUSTOM_SWAP_DROPPED = "custom_swap_dropped"             # strict: input after the member's early swap, not run
NOTE_CUSTOM_ALL_BLOCKED = "custom_all_blocked"               # args: (seconds waited, member waited for) strict, team
NOTE_CUSTOM_SHORT_WAIT = "custom_short_wait"                 # args: (seconds left, threshold) strict, team (10-18)
ASSUME_CUSTOM_STRICT_SWAP = "custom_strict_swap"             # args: (early swaps, seconds waited, cooldown skips)
ASSUME_CUSTOM_STRICT = "custom_strict"                       # args: (seconds waited, energy skips, cooldown skips)
ASSUME_CUSTOM_SEQUENCE = "custom_sequence"                   # args: (repeat,)
ASSUME_CUSTOM_AS_TYPED = "custom_as_typed"
ASSUME_CUSTOM_CHECK = "custom_check"
ASSUME_CUSTOM_START_GAUGE = "custom_start_gauge"             # args: (character_id, value, character_id, value ...)
ASSUME_CUSTOM_CD_WARN = "custom_cd_warn"
ASSUME_CUSTOM_CD_WAIT = "custom_cd_wait"                     # args: (total seconds waited,)
ASSUME_CUSTOM_CD_OFF = "custom_cd_off"
ASSUME_CUSTOM_BUFF_OFF = "custom_buff_off"                   # args: (count,)
ASSUME_CUSTOM_MANUAL_BUFF = "custom_manual_buff"             # args: (count,)
ASSUME_CUSTOM_TARGET = "custom_target"                       # args: (level, resistance, defense reduction, vulnerability)
ASSUME_CUSTOM_TARGET_KIND = "custom_target_kind"             # args: (boss 0/1, enemy count)
LIMIT_CUSTOM_CD_DATA = "custom_cd_data"
LIMIT_CUSTOM_ENERGY_MODEL = "custom_energy_model"
LIMIT_CUSTOM_CHAIN_RESET = "custom_chain_reset"
LIMIT_CUSTOM_SWAP_TIME = "custom_swap_time"
LIMIT_CUSTOM_FORM_FREE = "custom_form_free"
LIMIT_CUSTOM_SUPPORT_FREE = "custom_support_free"
LIMIT_CUSTOM_OWN_RESOURCE = "custom_own_resource"            # args: (character_id,)
LIMIT_CUSTOM_CD_BLANK = "custom_cd_blank"                    # args: (character_id, "E" | "Q" | "E/Q")
# step notes shown in amber in the step table (the others are grey information)
WARNING_NOTES = frozenset((
    NOTE_CUSTOM_GAUGE_SHORT, NOTE_CUSTOM_DOWNGRADED_GAUGE, NOTE_CUSTOM_DOWNGRADED_ELEMENT,
    NOTE_CUSTOM_SUPPORT_NO_REACTION, NOTE_CUSTOM_CD_NOT_READY, NOTE_CUSTOM_ENERGY_SHORT, NOTE_CUSTOM_NO_ANIMATION,
    NOTE_CUSTOM_CLOCK_SHORT,
    NOTE_CUSTOM_STATE_EXPIRED, NOTE_CUSTOM_STATE_INACTIVE, NOTE_CUSTOM_STATE_OVERRUN, NOTE_CUSTOM_STATE_WINDOW,
    NOTE_CUSTOM_ENERGY_SKIPPED, NOTE_CUSTOM_CD_SKIPPED, NOTE_CUSTOM_SWAP_OUT, NOTE_CUSTOM_SWAP_DROPPED,
))

# ── assumption codes ───────────────────────────────────────────────────────
ASSUME_APPROVED_ROTATIONS = "approved_rotations"
ASSUME_ORDER_AUTO = "order_auto"
ASSUME_ORDER_SLOT = "order_slot"
ASSUME_OPENING_FULL = "opening_full"
ASSUME_OPENING_ZERO = "opening_zero"
ASSUME_GAUGE_GAME = "gauge_game"
ASSUME_GAUGE_IDEAL = "gauge_ideal"
ASSUME_GAUGE_SET_SKILLS = "gauge_set_skills"
ASSUME_NORMAL_ENTRY = "normal_entry"
ASSUME_TIME_STOPS = "time_stops"
ASSUME_ENERGY_NOT_GATED = "energy_not_gated"
ASSUME_HEXED_IMMEDIATE = "hexed_immediate"
ASSUME_REACTION_OWNER = "reaction_owner"
ASSUME_SCORCH_DOT = "scorch_zankou_dot_driven"   # Zankou: DoT ticks activate / refresh Scorch (scheduler code)
ASSUME_DOT_TICKS = "dot_ticks"                   # args: (character_id,) whose damage-over-time ticks are included
ASSUME_ORDER_PLAN = "order_plan"
ASSUME_FULL_GAUGE_LOOPS = "full_gauge_loops"     # args: 1-based loop numbers starting with every gauge at 100
ASSUME_FORM_ACTIONS = "form_actions"             # args: (character_id,) whose form-state actions deal damage
ASSUME_FORM_WINDOW = "form_window"               # args: (character_id, form name_zh, duration_s)
# Global arc corrections (team_fork_corrections): args = character ids whose arcs they touched
ASSUME_FORK_SUPPLEMENT = "fork_global_supplement"   # B3 「罪与罚」 / B4 「月的对跖点」 priced by Global rules
ASSUME_FORK_DEDUP = "fork_permanent_dedup"          # B2 always-on arc bonus counted once (panel), not twice
# resources (team_resources; only at the data / community levels)
ASSUME_RESOURCE_MODEL = "resource_model"            # args: (model code,)
ASSUME_GAUGE_ACCUMULATED = "gauge_accumulated"      # gauge 100 at loop 1, then accumulated per hit
ASSUME_GAUGE_FALLBACK = "gauge_fallback"            # args: (loop, character_id, ...) fixed refill for missing data
ASSUME_ENERGY_GATED = "energy_gated"                # args: (character_id, cost)
ASSUME_START_ENERGY_FULL = "start_energy_full"
ASSUME_CHARGE_EFF = "charge_eff_rule"
ASSUME_CD_WAIT = "cd_wait_inserted"                 # args: (seconds waited in total,)
ASSUME_RESOURCE_CLOCK = "resource_clock"            # args: ("active" | "wall",)
ASSUME_OWN_RESOURCE = "own_resource"                # args: (character_id, resource name_zh)
ASSUME_HOTORI_INTERLUDE = "own_clock_interlude"     # args: (character_id, resource name_zh, seconds)
ASSUME_CUSTOM_MODEL = "custom_resource_model"       # args: (model code,)
ASSUME_ENERGY_TRACKED = "energy_tracked"            # per-hit energy gain tracked for every member (display)
ASSUME_CHARGE_ENERGY_SHOWN = "charge_energy_shown"  # args: (energy credited, grants) 盈蓄 energy in the energy shown
ASSUME_CUSTOM_CD_RULES = "custom_cd_rules"          # args: (character_id, rule code, ...) awakening / skill rules applied
ASSUME_NOT_READY_SWAP = "not_ready_swap"            # D3: a team member whose step is not ready swaps out at once
ASSUME_NOT_READY_SOLO = "not_ready_solo_wait"       # D3: alone there is nobody to swap to - the member waits
ASSUME_SHORT_WAIT = "short_cd_wait"                 # args: (character_id, waits, seconds left in total, threshold)

# ── limit codes (the reaction ones exactly as ReactionScheduler.limits() writes them) ──
LIMIT_SCORCH_ONE_LAYER = "scorch_zankou_one_layer"
LIMIT_SCORCH_IMMEDIATE = "scorch_zankou_activation_at_trigger"
LIMIT_SCORCH_CRIT_LOW = "scorch_crit_low"
LIMIT_STAIN_SCOPE = "stain_scope"                         # args (ignored): scope elements
LIMIT_HEXED_WITHOUT_LINKO = "hexed_without_linko_unconfirmed"
LIMIT_NOVA_STACKING = "nova_stacking_unconfirmed"
LIMIT_BLOSSOM_SCHEDULE = "blossom_schedule_inferred"
LIMIT_CHARGE_ENERGY = "charge_energy_not_counted"
LIMIT_DISCORD_TOPPLE = "discord_topple_not_counted"
LIMIT_ROWS_AFTER_END = "reaction_rows_after_end"         # args: (reaction hits past the end,)
LIMIT_GAUGE_FIT = "gauge_fit_one_battle"
LIMIT_LINKO_COATTACK = "linko_coattack"
LIMIT_LACRIMOSA_A6 = "lacrimosa_a6_support"          # Lacrimosa's awakening effect ⑥ selected (the node, A5)
LIMIT_ROTATION_ASSUMES_AWAKENING = "rotation_assumes_awakening"   # args: (character_id, node id) not selected
# awakening node rules (awakening_node_rules): framework codes "awakening_*", group codes "awakening_<group>_*"
ASSUME_AWAKENING_RULES = "awakening_rules"           # args: (character_id, node id, ...) rules applied
ASSUME_AWAKENING_EXPECTED = "awakening_expected"     # args: (character_id, node id, ...) priced as expected value
LIMIT_AWAKENING_UNPRICED = "awakening_unpriced"      # args: (character_id, node id, ...) selected, not priced
LIMIT_SUMMONS_DOT = "summons_dot"
LIMIT_MISSING_ACTIONS = "missing_actions"
LIMIT_DEFAULT_STEP_TIME = "default_step_time"
LIMIT_TIME_STOP_UNKNOWN = "time_stop_unknown"            # args: (character_id,)
LIMIT_UNREPLAYABLE = "unreplayable"                      # args: (hit count,)
LIMIT_FORM_CUT = "form_cut"                              # args: (character_id, groups kept, groups approved)
LIMIT_FORM_OVERRUN = "form_overrun"                      # args: (character_id, seconds past the window)
LIMIT_FORM_WINDOW_MISSED = "form_window_missed"          # args: (character_id, seconds, lo, hi)
LIMIT_FORM_TIMING_ASSUMED = "form_timing_assumed"        # args: (character_id,) spawned-actor hit timing inferred
LIMIT_RAVEN_MALICE = "raven_malice"
LIMIT_FIGHT_END = "fight_end_cutoff"
# resources (args: character id first where a member is named)
LIMIT_ENERGY_UNKNOWN = "energy_cost_unknown"        # args: (character_id, ...) ultimate cost unknown: not checked
LIMIT_COST_CONTESTED = "energy_cost_contested"      # args: (character_id, value) legacy-table cost not used
LIMIT_ENERGY_SCALE = "energy_scale_open"            # community 100 / 120 vs charge_add units unconfirmed
LIMIT_CD_UNKNOWN = "cd_unknown"                     # args: (character_id, kinds text) used, value unknown
LIMIT_CD_COMMUNITY = "cd_community"                 # args: (character_id, "E 16s · Q 20s")
LIMIT_CD_NONE_STRUCT = "cd_none_struct"             # args: (character_id, ...) support skill / counter
LIMIT_ENERGY_SHORT = "energy_short_skipped"         # args: (character_id, count)
LIMIT_CD_WAITED = "cd_waited"                       # args: (character_id, seconds)
LIMIT_CD_WAIT_TOO_LONG = "cd_wait_too_long"         # args: (character_id, kind, seconds)
LIMIT_FORM_NOT_ENTERED = "form_not_entered"         # args: (character_id, loop)
LIMIT_OWN_RESOURCE_UNIT = "own_resource_unit"       # args: (character_id, name_zh)
LIMIT_OWN_RESOURCE_DRAIN = "own_resource_drain"     # args: (character_id, name_zh)
LIMIT_MIDVISIT_SWAP = "midvisit_swap"               # args: (character_id,)
LIMIT_TIME_ONLY_CREDIT = "time_only_credit"         # args: (character_id,)
LIMIT_GAUGE_PARTIAL = "gauge_partial"               # args: (character_id, count)
LIMIT_ENERGY_EVENT_UNMODELLED = "energy_event_unmodelled"   # args: (character_id, code, ...)
LIMIT_CHARGE_ENERGY_GATED = "charge_energy_gated"
LIMIT_GAUGE_EFFICIENCY = "gauge_efficiency"
LIMIT_CD_UNCLASSIFIED = "cd_unclassified"           # args: (character_id, seq)
LIMIT_CD_CHARGES = "cd_charges"                     # args: (character_id, charges, seconds)
LIMIT_CD_CLOCK_CONFLICT = "cd_clock_conflict"       # args: (character_id, kind, seconds, recorded active s)
LIMIT_RESOURCE_DATA_MISSING = "resource_data_missing"   # args: (character_id,) no team_resource_data record
LIMIT_HIT_CREDIT = "hit_credit"                     # args: (character_id, energy, gauge, hits, confidence) per use
LIMIT_HIT_UNKNOWN = "hit_unknown"                   # args: (character_id, ability, selector) hits not laid out, count ?
LIMIT_EARLY_SWAP = "early_swap"                     # args: (character_id, early swaps, approved steps not run)
LIMIT_ALL_BLOCKED = "all_blocked_wait"              # args: (character_id, seconds waited, member waited for)
# brief §1.5 known exclusions (args: (character_id,); per-character codes name that member)
LIMIT_ADLER_SCORCH = "scorch_adler_variant"
LIMIT_CANG_SCORCH = "scorch_cang_reapply"
LIMIT_DAFFODILL_DISCORD = "discord_daffodill_topple"
LIMIT_LACRIMOSA_DISCORD = "discord_lacrimosa_hit"
LIMIT_CHARGE_PASSIVES = "charge_passive"
LIMIT_NOVA_EXTRAS = "nova_extra"
LIMIT_BLOSSOM_CURVE = "blossom_copy_curve"
LIMIT_LINKO_HEXED_BONUS = "hexed_linko_bonus"
# reaction passives the simulator does not compute (args: (character_id,))
LIMIT_CHAOS_REMORA_END = "remora_end_damage"
LIMIT_AKANE_REMORA_REAPPLY = "remora_reapply_damage"
LIMIT_HATHOR_REMORA_CRIT = "remora_crit_bonus"
LIMIT_NANALLY_VOLLEY = "blossom_volley"
LIMIT_NANALLY_FOLLOW_UP = "reaction_followup"
LIMIT_KUHARA_ROSE = "blossom_rose_settlement"
LIMIT_JIN_TIME_STOP = "blossom_time_stop"

# ── effect codes (ReactionTrace.effects, as ReactionScheduler.traces() writes them) ──
EFFECT_SCORCH_TICKS = "scorch_ticks"            # args: (tick count,)
EFFECT_SCORCH_REFRESH = "scorch_refresh"        # args: (first trigger index,) re-trigger extended expiry
EFFECT_SCORCH_DORMANT = "scorch_dormant"        # Zankou: no DoT tick activated this trigger's Scorch
EFFECT_SCORCH_ACTIVATED = "scorch_activated_after_s"  # args: (seconds after the trigger,) DoT tick activated it
EFFECT_ZANKOU_VARIANT = "scorch_zankou_variant"  # not shown: the owner column already says it
EFFECT_LAYERS = "layers"                        # args: (layer count,)
EFFECT_HEXED_RATIO = "hexed_ratio"              # args: (extra ratio c, e.g. 0.33,)
EFFECT_STAIN_RATIO = "stain_ratio"              # args: (damage-up s, e.g. 0.2,)
EFFECT_BOOSTED_HITS = "boosted_hits"            # args: (hits that received a Hexed / Stain increment,)
EFFECT_WINDOW = "window_s"                      # args: (seconds,)
EFFECT_REMORA_DURATION = "remora_duration_s"    # args: (seconds,)
EFFECT_EXTENDED = "extended"                    # a re-trigger extended an active window
EFFECT_SETTLE_AFTER = "settle_after_s"          # args: (seconds,)
EFFECT_NOVA_REPLACED = "nova_replaced"          # args: (later trigger index,) this pending Nova was dropped
EFFECT_NOVA_RETIMED = "nova_retimed"            # args: (later trigger index,) settles with the later Nova
EFFECT_BLOSSOM_PLANTS = "blossom_plants"        # args: (plants, flowers per plant)
EFFECT_BLOSSOM_FLOWERS = "blossom_flowers"      # args: (flower count,)
EFFECT_FLOWERS_DROPPED = "blossom_flowers_dropped"  # args: (flowers removed by the plant limit,)
EFFECT_CHARGE_ENERGY = "charge_energy"          # args: (energy, flowers that hit the 延滞 target)
EFFECT_TOPPLE_REDUCTION = "discord_topple_reduction"  # args: (ratio,)
EFFECT_LED_TO_CHARGE = "charge"                 # args: (盈蓄 reaction index,) on the parent reactions
EFFECT_LED_TO_DISCORD = "discord"               # args: (失谐 reaction index,) on the parent reactions
EFFECT_COMBO_OF = "combo_of"                    # args: (reaction_zh, reaction_zh)
EFFECT_TRUNCATED = "truncated_at_end"           # args: (count,), repeated per hit; summed by merge_effects
EFFECT_UNREPLAYABLE = "unreplayable"            # args: (hit count,)
EFFECT_EFFECT_ONLY = "effect_only"
HIDDEN_EFFECTS = frozenset((EFFECT_ZANKOU_VARIANT,))

# ── PlanTrace.reasons (note items) and carry basis ─────────────────────────
PLAN_CARRY = "plan_carry"                       # args: (character_id,)
PLAN_CARRY_MAIN = "plan_carry_main"             # args: (character_id,) no form member in the team
PLAN_BEST_DPS = "plan_best_dps"                 # args: (simulated candidate count,)
PLAN_CARRY_FIRST = "plan_carry_first"           # args: (character_id,)
PLAN_CARRY_LAST = "plan_carry_last"             # args: (character_id,)
PLAN_COVERAGE = "plan_coverage"                 # args: (covered seconds of the carry's form windows, their total)
PLAN_CARRY_FIRST_DPS = "plan_carry_first_dps"   # args: (character_id,) first without damage over time to keep
PLAN_CARRY_LAST_DPS = "plan_carry_last_dps"     # args: (character_id,) last, but not the best buff cover
PLAN_COVER_TRADE = "plan_cover_trade"           # args: (chosen cover seconds, best cover of a simulated candidate)
PLAN_Q_CASTS = "plan_q_casts"                   # args: (ultimates cast by the chosen order,)
CARRY_FORM = "form"                             # the carry is a form (transformation) damage dealer
CARRY_MAIN = "main"                             # no form member: the main damage dealer with the longest field time
CARRY_FIELD_TIME = "field_time"                 # no main role: longest approved field time
SUMMED_EFFECTS = frozenset((EFFECT_TRUNCATED,))


# ── traces ─────────────────────────────────────────────────────────────────
def _tuple(value) -> tuple:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, (str, bytes)):
        return (value,)
    return tuple(value)


@dataclass(frozen=True)
class StepTrace:
    """One approved rotation step as it ran inside a visit."""

    seq: int                        # team_rotation_data step seq (0 for an entry substitute)
    slot: str                       # SLOT_*
    ability_id: str | None
    selector: str | None
    start_s: float
    duration_s: float
    hits: int = 0
    damage: float = 0.0             # direct expected damage of this step's hits
    status: str = STEP_OK           # STEP_*
    ability_name_zh: str = ""       # gameplay_ability_catalog.name_zh when known (display only)
    form_role: str = ""             # FORM_ROLE_* for steps inside a form, "" otherwise
    # resource levels (team_resources); defaults = legacy level / older results
    energy_before: float | None = None   # pool energy (or Hotori's clock) before the step; None = not modelled
    energy_after: float | None = None
    cd_kind: str = ""               # E | E_alt | Q | QTE | counter | "" (cooldown kind checked for the step)
    remaining_s: float = 0.0        # cooldown / resource time left when reached (wait rows, skips, warn notes)
    note: str = ""                  # STEP_NOTE_*
    events: tuple = ()              # ((code, amount), ...) energy events after the step
    credit: float = 0.0             # gauge credited to a time-only step
    cost: float | None = None       # cost the step was checked against
    energy_gain: float = 0.0        # ultimate energy the step gained (hits x (1 + efficiency) + events)
    gauge_after: float | None = None    # the member's cycle gauge after the step (None = not traced)
    gauge_gain: float = 0.0         # gauge the step built
    cd_s: float | None = None       # the step's cooldown as checked (None = unknown / not enforced)
    cd_conf: str = ""               # confidence of that cooldown (team_resource_data vocabulary)
    cd_source: str = ""             # short source tag of that cooldown
    dropped: int = 0                # STEP_SWAP_OUT: approved steps of the visit not run after it
    wait_for: int | None = None     # wait row STEP_NOTE_ALL_BLOCKED: the member whose readiness was waited for

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", _tuple(self.events))


@dataclass(frozen=True)
class MemberResourceTrace:
    """Ultimate energy, cooldowns and gauge rule of one member as the run used them (resource levels)."""

    character_id: int
    energy_kind: str = "ultimate"   # ultimate | own_clock | own_meter
    cost: tuple = ()                # (value | None, source, confidence) of the ultimate cost (best known)
    cost_enforced: bool = False     # the cost gated the ultimate
    cost_display: tuple = ()        # ((value, "site date"), ...) community display values (not enforced)
    cost_bound: float | None = None  # measured upper bound (never a value)
    gauge_fallback: bool = False    # refilled by the fixed rule (missing gauge data)
    fallback_reason: str = ""       # data | missing
    cd: tuple = ()                  # ((kind, value used | None, best value | None, source, confidence), ...)
    cd_alt: tuple = ()              # ((kind, value, "site date", confidence), ...) tooltip-only alternatives
    q_planned: int = 0
    q_cast: int = 0
    q_skipped: tuple = ()           # 0-based loops whose ultimate was skipped for energy
    waited_s: float = 0.0
    cd_waits: int = 0
    res_waits: int = 0
    cd_skips: int = 0
    interlude_s: float = 0.0        # Hotori: clock deficit credited at the "swap out and wait" step
    interludes_s: tuple = ()        # the same per credited visit (seconds)
    energy_gained: float = 0.0      # ultimate energy gained over the run (display; also for unknown costs)
    charge_eff: float = 0.0
    events: tuple = ()              # ((code, amount), ...)
    unmodelled: tuple = ()          # codes of energy / cooldown effects not simulated
    unchecked: tuple = ()           # cooldown kinds used again without a value
    credited_gauge: float = 0.0     # gauge credited to time-only steps
    own_name_zh: str = ""           # own resource name (非闭合时计 / 桀骜斗志)
    charges: int = 1                # E charges (Chiichan 3)
    meter_short: int = 0            # Shinku: ultimates pressed with the meter below its cap (tracked only)
    # D3: ((1-based loop, seq, kind, reason, seconds left | None, steps not run), ...) early swaps;
    # ((1-based loop, seq, seconds waited, member waited for), ...) waits while every member was blocked
    early_swaps: tuple = ()
    all_blocked: tuple = ()
    # ((1-based loop, seq, kind, wall seconds waited, seconds left), ...) cooldowns under the swap threshold (10-18)
    short_waits: tuple = ()

    def __post_init__(self) -> None:
        for name in ("cost", "cost_display", "cd", "cd_alt", "q_skipped", "events", "unmodelled", "unchecked",
                     "interludes_s", "early_swaps", "all_blocked", "short_waits"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))


@dataclass(frozen=True)
class FormTrace:
    """One form window inside a visit (transformation damage dealers): game-data duration and its use."""

    code: str                       # team_form_actions.FORMS code, e.g. "zankou_fantasy"
    name_zh: str                    # game name, e.g. 幻境形态 (form_name_text() gives the display name)
    duration_s: float               # form duration from game data
    start_s: float | None = None    # wall seconds of the form start (None: the entry step did not run)
    used_s: float = 0.0             # active seconds of the window that the visit used (capped at duration_s)
    groups: int = 0                 # body groups run, extra rounds included
    groups_approved: int = 0        # body groups of the approved rotation
    fills: int = 0                  # extra rounds added because the window still had time
    cut_steps: int = 0              # approved form steps that did not fit (STEP_FORM_CUT)
    overrun_s: float = 0.0          # active seconds kept past the window (warn policy)
    status: str = FORM_OK           # FORM_*
    pauses_off_field: bool = False  # the form clock stops while the member is off the field (game text)
    ends_on_swap: bool = True       # swapping out ends the form (game data)
    exit_s: float | None = None     # active seconds from the form start to the exit / window step
    window: tuple = ()              # allowed (lo, hi) seconds for that step

    def __post_init__(self) -> None:
        object.__setattr__(self, "window", _tuple(self.window))


@dataclass(frozen=True)
class VisitTrace:
    """One stay on the field: entry type, time span, gauge and the steps run."""

    index: int                      # 0-based over the whole battle
    loop_index: int                 # 0-based loop number
    character_id: int
    element: str                    # element code
    entry: str                      # ENTRY_*
    start_s: float
    end_s: float
    active_s: float                 # visit length without time stops
    gauge_in: float                 # own cycle gauge when entering
    gauge_out: float                # own cycle gauge when leaving
    steps: tuple = ()               # tuple[StepTrace, ...]
    damage: float = 0.0             # direct damage of the visit's steps
    # the member's own damage-over-time ticks (Zankou erosion / venom, Lacrimosa nightmare) from this visit
    # until the member's next visit; they keep ticking after the swap and are not part of any step
    dot_damage: float = 0.0
    dot_hits: int = 0
    refilled: bool = False          # the member's gauge was set to 100 at the start of this visit's loop (legacy:
    #                                 every gauge at FULL_GAUGE_LOOPS; resource levels: loop 1, or the fallback)
    form: Any = None                # FormTrace when the member entered its form in this visit
    energy_in: float | None = None  # pool energy / own clock when entering (None = not modelled)
    energy_out: float | None = None
    waited_s: float = 0.0           # cooldown / resource waits inserted in this visit
    energy_gain: float = 0.0        # ultimate energy gained in this visit (display; also for unknown costs)
    early_swap: tuple = ()          # D3: (seq, kind, seconds left | None, reason, steps not run) when it ended early

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", _tuple(self.steps))
        object.__setattr__(self, "early_swap", _tuple(self.early_swap))

    @property
    def total_damage(self) -> float:
        """Step damage plus damage-over-time ticks (sums to the member's direct damage over its visits)."""
        return float(self.damage or 0.0) + float(self.dot_damage or 0.0)


@dataclass(frozen=True)
class SwapTrace:
    """One swap (every swap, also the ones that did not react)."""

    index: int
    time_s: float
    out_character_id: int
    in_character_id: int
    out_element: str
    in_element: str
    gauge: float | None             # outgoing member's gauge at the swap
    outcome: str                    # OUTCOME_*
    reaction_index: int | None = None   # ReactionTrace.index when outcome == reaction


@dataclass(frozen=True)
class ReactionTrace:
    """One reaction event (swap-triggered, or a 盈蓄 / 失谐 combination with no swap of its own)."""

    index: int
    time_s: float
    reaction_zh: str                # 创生 / 覆纹 / 浊燃 / 黯星 / 浸染 / 延滞 / 盈蓄 / 失谐
    out_character_id: int | None
    in_character_id: int | None
    owner_character_id: int | None
    owner_basis: str                # OWNER_*
    hits: int = 0                   # reaction hits (ticks, flowers, settlements) or boosted hits
    damage: float = 0.0
    status: str = REACTION_COMPUTED  # REACTION_*
    effects: tuple = ()             # effect items, see module docstring

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", _tuple(self.effects))


@dataclass(frozen=True)
class MemberRotationTrace:
    """Which approved rotation a member used and how much of it could be simulated."""

    character_id: int
    variant_id: str                 # "approved"
    verdict: str                    # VERDICTS
    confidence: str                 # CONFIDENCES
    role: str                       # ROLES
    steps_total: int
    steps_simulated: int
    steps_time_only: int
    missing: tuple = ()             # ability ids / "ability:selector" without an animation match
    name_zh: str = ""
    element: str = ""
    dot_damage: float = 0.0         # the member's damage-over-time ticks over the battle (VisitTrace.dot_damage sum)
    dot_hits: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing", _tuple(self.missing))


@dataclass(frozen=True)
class TimeStopTrace:
    """One ultimate time stop added to the axis (measured duration)."""

    start_s: float
    duration_s: float
    character_id: int | None = None
    ability_id: str | None = None


@dataclass(frozen=True)
class PlanCandidate:
    """One visit order the planner considered (order mode "plan")."""

    order: tuple
    adjacency: int                  # adjacent-element pairs around the loop (closing swap included)
    reactions: int                  # reactions fired over all loops (layout pass, gauge rule applied)
    coverage_s: float               # seconds of the carry's form windows under team buffs / 覆纹 / 浸染
    loop2_support_entry: bool       # the carry enters loop 2 with the support skill
    carry_first: bool
    dps: float | None = None        # simulated team DPS (None: not simulated)
    chosen: bool = False
    rank: int = 0                   # stage-1 rank (0 = best)
    form_s: float = 0.0             # total seconds of the carry's form windows (coverage_s is part of it)
    q_casts: int | None = None      # ultimates cast (resource levels; None = legacy level)
    waited_s: float = 0.0           # cooldown / resource waits inserted

    def __post_init__(self) -> None:
        object.__setattr__(self, "order", _tuple(self.order))


@dataclass(frozen=True)
class PlanTrace:
    """How the planner chose the visit order: the carry, every candidate and the reasons (note items)."""

    carry_character_id: int | None
    carry_basis: str                # CARRY_*
    candidates: tuple = ()          # tuple[PlanCandidate, ...] in stage-1 rank order
    reasons: tuple = ()             # note items (PLAN_*)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", _tuple(self.candidates))
        object.__setattr__(self, "reasons", _tuple(self.reasons))

    @property
    def chosen(self) -> PlanCandidate | None:
        return next((c for c in self.candidates if c.chosen), None)


@dataclass(frozen=True)
class CustomStepTrace:
    """One executed step of a custom cycle (repeat counts and repeats of the whole list expanded)."""

    index: int                      # 0-based in the executed timeline
    source_index: int               # index of the CustomStep in the typed sequence (chip number - 1); -1 = inserted wait
    repeat_index: int               # 0-based repeat of the whole sequence
    character_id: int
    action: str                     # team_custom_notation action code
    pos: int | None = None          # resolved 1-based chain / variant position
    state: str = ""                 # state code the action was resolved in, "" = base
    slot: str = SLOT_OTHER          # StepTrace slot
    keys: tuple = ()                # ((ability_id, selector), ...) placed
    name_zh: str = ""               # ability / form action name (the display layer translates it)
    start_s: float = 0.0
    duration_s: float = 0.0
    wait_before_s: float = 0.0      # cooldown wait inserted before the step
    hits: int = 0
    damage: float = 0.0
    status: str = STEP_OK           # STEP_OK | STEP_TIME_ONLY | STEP_MISSING | STEP_SKIPPED
    entry: str = ""                 # "" | ENTRY_OPENER | ENTRY_SUPPORT_SKILL | ENTRY_NORMAL
    swap_index: int | None = None   # SwapTrace.index of the swap this step made
    reaction_index: int | None = None   # ReactionTrace.index when the entry fired a reaction
    gauge_before: float = 0.0       # the acting member's cycle gauge
    gauge_after: float = 0.0
    out_gauge: float | None = None  # outgoing member's gauge at the swap
    energy_after: float | None = None   # None when the member's ultimate cost is unknown
    notes: tuple = ()               # note items (code, args)
    visit_index: int = 0
    step_index: int | None = None   # index in VisitTrace.steps; None for a plain swap
    reaction_zh: str = ""           # reaction the entry fired ("" = none); set by the preview too
    out_character_id: int | None = None
    energy_gained: float | None = None  # cost unknown: ultimate energy since the member's last ultimate (display)
    clock_after: float | None = None    # own clock (Hotori) after the step (resource levels)

    def __post_init__(self) -> None:
        object.__setattr__(self, "keys", _tuple(self.keys))
        object.__setattr__(self, "notes", _tuple(self.notes))

    @property
    def warned(self) -> bool:
        return any(split_note(item)[0] in WARNING_NOTES for item in self.notes)


@dataclass(frozen=True)
class CustomCycleTrace:
    """The custom cycle as simulated: the typed sequence, every executed step and the options used."""

    steps: tuple = ()               # tuple[CustomStepTrace, ...]
    sequence: tuple = ()            # the CustomStep list as simulated (codes)
    repeat: int = 1
    gauge_mode: str = GAUGE_AS_TYPED
    start_gauge: tuple = ()         # ((character_id, value), ...)
    resource_check: str = "warn"
    resources: tuple = ()           # ((character_id, e_cd_s, q_cd_s, q_cost), ...) as used
    waited_s: float = 0.0           # total cooldown wait inserted
    warnings: int = 0               # steps with at least one warning note
    target: tuple = ()              # (enemy_level, resistance, defense_reduction, vulnerability)
    buffs_disabled: tuple = ()      # buff keys
    buffs_manual: int = 0

    def __post_init__(self) -> None:
        for name in ("steps", "sequence", "start_gauge", "resources", "target", "buffs_disabled"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))


@dataclass(frozen=True)
class TeamExplanation:
    order_mode: str                 # ORDER_*
    gauge_rule: str                 # GAUGE_*
    opening_gauge: str              # OPENING_*
    loops: int
    order: tuple                    # character ids in visit order of one loop
    wall_time_s: float
    active_time_s: float
    time_stops: tuple = ()          # tuple[TimeStopTrace, ...] (plain (start_s, duration_s, ...) tuples accepted)
    visits: tuple = ()              # tuple[VisitTrace, ...]
    swaps: tuple = ()               # tuple[SwapTrace, ...]
    reactions: tuple = ()           # tuple[ReactionTrace, ...]
    members: tuple = ()             # tuple[MemberRotationTrace, ...] in slot order
    assumptions: tuple = ()         # note items
    limits: tuple = ()              # note items
    full_gauge_loops: tuple = ()    # 1-based loops that started with every gauge at 100 (FULL_GAUGE_LOOPS)
    plan: Any = None                # PlanTrace when order_mode == "plan"
    custom: Any = None              # CustomCycleTrace when order_mode == "custom"
    # resource levels (team_resources); defaults = legacy level / results from before the resource model
    resource_model: str = RESOURCE_LEGACY
    gauge_refills: tuple = ()       # ((1-based loop, character_id), ...) fixed refills of fallback members
    resources: tuple = ()           # tuple[MemberResourceTrace, ...] in slot order
    waited_s: float = 0.0           # cooldown / resource waits inserted in total
    resource_clock: str = ""        # active | wall ("" = legacy)
    not_ready: str = ""             # NOT_READY_SWAP (team, D3) | NOT_READY_WAIT (solo / wait policy) | "" legacy

    def __post_init__(self) -> None:
        for name in ("order", "time_stops", "visits", "swaps", "reactions", "members", "assumptions", "limits",
                     "full_gauge_loops", "gauge_refills", "resources"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))

    def resource(self, character_id) -> MemberResourceTrace | None:
        for r in self.resources or ():
            if r.character_id == character_id:
                return r
        return None

    # ── convenience for the view / tests ──
    @property
    def reaction_damage(self) -> float:
        return float(sum(r.damage or 0.0 for r in self.reactions))

    @property
    def time_stop_s(self) -> float:
        return max(0.0, float(self.wall_time_s) - float(self.active_time_s))

    def member(self, character_id) -> MemberRotationTrace | None:
        for m in self.members:
            if m.character_id == character_id:
                return m
        return None

    def name_of(self, character_id) -> str:
        """Chinese name (the display layer translates it); falls back to the rotation data, then the id."""
        if character_id is None:
            return ""
        m = self.member(character_id)
        if m is not None and m.name_zh:
            return m.name_zh
        return rotation_character(character_id).get("name_zh") or str(character_id)

    def element_of(self, character_id) -> str:
        m = self.member(character_id)
        if m is not None and m.element:
            return element_code(m.element)
        for v in self.visits:
            if v.character_id == character_id and v.element:
                return element_code(v.element)
        return element_code(rotation_character(character_id).get("element") or "")

    def team_elements(self) -> tuple[str, ...]:
        ids = [m.character_id for m in self.members] or list(self.order)
        return tuple(self.element_of(cid) for cid in ids)

    def has_adjacent_pair(self) -> bool:
        return team_has_adjacent_pair(self.team_elements())

    def reaction_by_index(self) -> dict:
        return {r.index: r for r in self.reactions}


# ── helpers ────────────────────────────────────────────────────────────────
def element_code(value: Any) -> str:
    """"cosmos" / "COSMOS" / "ECharacterElementType::CHARACTER_ELEMENT_TYPE_COSMOS" / "光" -> "cosmos"."""
    if not value:
        return ""
    text = str(value)
    for code, label in ELEMENT_LABELS.items():
        if text == label:
            return code
    text = text.rsplit("::", 1)[-1].rsplit("CHARACTER_ELEMENT_TYPE_", 1)[-1]
    return text.strip().lower()


def element_label(value: Any) -> str:
    """Single Chinese character for an element code (光/灵/咒/暗/魂/相); "" when unknown."""
    return ELEMENT_LABELS.get(element_code(value), "")


def is_adjacent(a: Any, b: Any) -> bool:
    a, b = element_code(a), element_code(b)
    if a not in ELEMENT_RING or b not in ELEMENT_RING or a == b:
        return False
    d = abs(ELEMENT_RING.index(a) - ELEMENT_RING.index(b))
    return d in (1, len(ELEMENT_RING) - 1)


def team_has_adjacent_pair(elements: Iterable) -> bool:
    codes = [element_code(e) for e in elements]
    return any(is_adjacent(a, b) for i, a in enumerate(codes) for b in codes[i + 1:])


def rotation_character(character_id) -> dict:
    """team_rotation_data.CHARACTERS[cid] when the generated module is present, else {}."""
    try:
        from src.services import team_rotation_data
    except Exception:
        return {}
    try:
        return dict(team_rotation_data.CHARACTERS.get(int(character_id), {}))
    except Exception:
        return {}


def note(code: str, *args) -> tuple:
    """Canonical note item: (code, args)."""
    return (str(code), tuple(args))


effect = note


def split_note(item) -> tuple[str, tuple]:
    """Any note / effect item form -> (code, args)."""
    if isinstance(item, (tuple, list)):
        if not item:
            return "", ()
        code = str(item[0])
        rest = tuple(item[1:])
        if len(rest) == 1 and isinstance(rest[0], (tuple, list)):
            rest = tuple(rest[0])
        return code, rest
    text = str(item)
    if ":" in text:
        code, raw = text.split(":", 1)
        return code, tuple(a for a in raw.split(",") if a != "")
    return text, ()


def _name(value, names: Mapping | None) -> str:
    """Character id (int or digit string) -> Chinese name; other values pass through."""
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return str(value)
    if names and cid in names:
        return names[cid]
    return rotation_character(cid).get("name_zh") or str(cid)


def _num(args: tuple, i: int, default: float = 0.0) -> float:
    try:
        return float(args[i])
    except (IndexError, TypeError, ValueError):
        return default


def _secs(value: float) -> str:
    return f"{value:g}s"


def _who(args: tuple, names: Mapping | None, fallback: str) -> str:
    """Name of the character in args[0], or the fallback list of names when no id was given."""
    return _name(args[0], names) if args else fallback


def _members_text(args: tuple, names: Mapping | None) -> str:
    """Chinese names of the character ids in args as one "、"-separated data string (the display layer translates
    the names and the separator together, like the fixed name lists below)."""
    return "、".join(dict.fromkeys(str(_name(value, names)) for value in (args or ("?",))))


def loops_text(loops) -> str:
    """1-based loop numbers as "1 · 3" (language-neutral separator)."""
    return " · ".join(str(int(float(n))) for n in _tuple(loops) if str(n).strip() != "")


_FORM_CODES_BY_ZH = {"幻境形态": "zankou_fantasy", "救世的魔女": "raven_witch", "升腾之赤": "shinku_rage",
                     "紧急派送": "hathor_dispatch", "华彩连段": "akane_cadenza", "啮逐潜影": "skia_shadow"}


def form_name_text(code: str, name_zh: str = "") -> str:
    """Form code (or its Chinese game name) -> display name.  Built with _L: several of these game names have
    no display-layer entry."""
    code = _FORM_CODES_BY_ZH.get(str(code), str(code))
    return {
        "zankou_fantasy": _L('幻境形态'),
        "raven_witch": _L('救世的魔女'),
        "shinku_rage": _L('升腾之赤'),
        "hathor_dispatch": _L('紧急派送'),
        "akane_cadenza": _L('华彩连段'),
        "skia_shadow": _L('啮逐潜影'),
    }.get(code, name_zh or code)


_NOTES = {
    # assumptions
    ASSUME_APPROVED_ROTATIONS: lambda a, n: _L('各队员按已审核的循环行动，缺少动画的步骤不替换为其他动作'),
    ASSUME_ORDER_AUTO: lambda a, n: _L('出场顺序自动选择：相邻属性组合最多，场上时间最长的队员最后登场'),
    ASSUME_ORDER_SLOT: lambda a, n: _L('出场顺序按编队 1→2→3→4'),
    ASSUME_OPENING_FULL: lambda a, n: _L('开场时所有队员环合值已满'),
    ASSUME_OPENING_ZERO: lambda a, n: _L('开场时环合值为 0，残虹为 100（被动）'),
    ASSUME_GAUGE_GAME: lambda a, n: _L('切出队员环合值满 100 且属性相邻时，切入队员以援护技登场并触发环合反应'),
    ASSUME_GAUGE_IDEAL: lambda a, n: _L('理想：每次相邻切换都触发'),
    ASSUME_GAUGE_SET_SKILLS: lambda a, n: _L('「零」与黑羽的变轨技能直接把环合值补满（推断）'),
    ASSUME_NORMAL_ENTRY: lambda a, n: _L('普通切换时不放援护技；薄荷、哈尼娅、埃德嘉改用登场动作'),
    ASSUME_TIME_STOPS: lambda a, n: _L('极轨终结演出按实测时停扣除，DPS 按扣除时停后的战斗时间计算'),
    ASSUME_ENERGY_NOT_GATED: lambda a, n: _L('极轨终结能量与冷却未检查'),
    ASSUME_HEXED_IMMEDIATE: lambda a, n: _L('覆纹：每次灵/咒伤害后立即追加'),
    ASSUME_REACTION_OWNER: lambda a, n: _L('浊燃、黯星、创生归最终效果更高的队员（残虹在队时浊燃归残虹）'),
    ASSUME_SCORCH_DOT: lambda a, n: _L('残虹在队时，浊燃在下一次持续伤害跳时才激活，之后每次持续伤害跳都把持续时间刷新为 15 秒（残虹被动）'),
    ASSUME_DOT_TICKS: lambda a, n: _LF('{0} 的持续伤害跳已计入（每 1 秒一跳，切出后继续）').format(
        _name(a[0] if a else "?", n)),
    # limits
    LIMIT_SCORCH_ONE_LAYER: lambda a, n: _L('残虹浊燃按 1 层计算（未模拟持续伤害跳，实战多为 3 层）'),
    LIMIT_ROWS_AFTER_END: lambda a, n: _LF('{0} 个反应命中在战斗结束后，未计入').format(int(_num(a, 0))),
    LIMIT_SCORCH_IMMEDIATE: lambda a, n: _L('残虹浊燃在触发时立即生效（实战要等到持续伤害跳出现）'),
    LIMIT_SCORCH_CRIT_LOW: lambda a, n: _L('浊燃暴击伤害可能偏低约 12%'),
    LIMIT_STAIN_SCOPE: lambda a, n: _L('浸染只提升魂/相属性伤害（待实战确认）'),
    LIMIT_HEXED_WITHOUT_LINKO: lambda a, n: _L('没有灵可时覆纹追加比例按 20% 计算（未经实战验证）'),
    LIMIT_NOVA_STACKING: lambda a, n: _L('不同队员的黯星叠加方式未经实战验证'),
    LIMIT_BLOSSOM_SCHEDULE: lambda a, n: _L('创生花的开花时间为推断（每 2 秒一朵，共 5 朵）'),
    LIMIT_GAUGE_FIT: lambda a, n: _L('环合值规则只用一场实战拟合（26 次切换中 24 次一致）'),
    LIMIT_LINKO_COATTACK: lambda a, n: _L('灵可协同攻击触发的援护技未模拟'),
    LIMIT_LACRIMOSA_A6: lambda a, n: _L('安魂曲觉醒效果 ⑥ 的自动援护技未模拟'),
    LIMIT_ROTATION_ASSUMES_AWAKENING: lambda a, n: _LF('{0} 的已审核循环以 {1} 为前提；未选择该效果时实际循环不同，结果可能偏高').format(
        _name(a[0] if a else "?", n), node_labels(a[1:2])),
    ASSUME_AWAKENING_RULES: lambda a, n: _LF('{0} 的 {1} 按 Global 补充规则计算（说明文与游戏数据数值）').format(
        _name(a[0] if a else "?", n), node_labels(a[1:])),
    ASSUME_AWAKENING_EXPECTED: lambda a, n: _LF('{0} 的 {1} 的条件无法在模拟中再现，按期望值计算').format(
        _name(a[0] if a else "?", n), node_labels(a[1:])),
    LIMIT_AWAKENING_UNPRICED: lambda a, n: _LF('{0} 已选择的 {1} 未计入伤害（需要实测，或木桩上无法计算）').format(
        _name(a[0] if a else "?", n), node_labels(a[1:])),
    LIMIT_CHARGE_ENERGY: lambda a, n: _L('盈蓄的终结能量未计入'),
    LIMIT_DISCORD_TOPPLE: lambda a, n: _L('失谐的倾陷削减不计伤害（木桩不倾陷）'),
    LIMIT_SUMMONS_DOT: lambda a, n: _L('召唤物与残虹、安魂曲以外的持续伤害未计入'),
    LIMIT_MISSING_ACTIONS: lambda a, n: _L('部分动作缺少动画数据，未计入伤害（结果偏低）'),
    LIMIT_DEFAULT_STEP_TIME: lambda a, n: _L('部分仅计时的步骤没有时长数据，按 1 秒计算'),
    LIMIT_TIME_STOP_UNKNOWN: lambda a, n: _LF('{0} 未测得时停时长').format(_name(a[0] if a else "?", n)),
    LIMIT_UNREPLAYABLE: lambda a, n: _LF('{0} 个命中无法计算').format(int(_num(a, 0))),
    LIMIT_ADLER_SCORCH: lambda a, n: _L('阿德勒浊燃的额外暴击与加快跳伤未模拟'),
    LIMIT_CANG_SCORCH: lambda a, n: _L('白藏重新施加浊燃未模拟'),
    LIMIT_DAFFODILL_DISCORD: lambda a, n: _L('达芙蒂尔失谐的倾陷效果未模拟'),
    LIMIT_CHARGE_PASSIVES: lambda a, n: _LF('{0} 与盈蓄相关的被动未模拟').format(_who(a, n, "埃德嘉、小吱、真红")),
    LIMIT_NOVA_EXTRAS: lambda a, n: _LF('{0} 的黯星额外效果未模拟').format(_who(a, n, "哈尼娅、法帝娅、黑羽")),
    LIMIT_BLOSSOM_CURVE: lambda a, n: _LF('{0} 的创生 37.5% 曲线未模拟').format(_who(a, n, "伊洛伊、薄荷")),
    LIMIT_LACRIMOSA_DISCORD: lambda a, n: _L('安魂曲对失谐目标的额外伤害未模拟'),
    LIMIT_LINKO_HEXED_BONUS: lambda a, n: _L('灵可对覆纹目标的额外伤害未模拟'),
    LIMIT_CHAOS_REMORA_END: lambda a, n: _LF('{0} 在延滞结束时造成的相属性伤害未模拟').format(_who(a, n, "卡厄斯")),
    LIMIT_AKANE_REMORA_REAPPLY: lambda a, n: _LF('{0} 对延滞中的目标重新施加延滞时造成的伤害未模拟').format(
        _who(a, n, "明音凛")),
    LIMIT_HATHOR_REMORA_CRIT: lambda a, n: _LF('{0} 对延滞目标的全队暴击率提升未模拟（只计入延长的持续时间）').format(
        _who(a, n, "哈索尔")),
    LIMIT_NANALLY_VOLLEY: lambda a, n: _LF('{0} 的创生花增至 10 朵、每 1 秒一朵未模拟（按 5 朵、每 2 秒计算）').format(
        _who(a, n, "娜娜莉")),
    LIMIT_NANALLY_FOLLOW_UP: lambda a, n: _LF('{0} 由环合伤害触发的追加攻击未模拟').format(_who(a, n, "娜娜莉")),
    LIMIT_KUHARA_ROSE: lambda a, n: _LF('{0} 的创生花命中玫约目标时的追加清算未模拟').format(_who(a, n, "九原")),
    LIMIT_JIN_TIME_STOP: lambda a, n: _LF('{0} 的创生株在时停期间继续攻击未模拟').format(_who(a, n, "浔")),
    # 3 loops, gauge refill, form windows (2026-10-04)
    ASSUME_ORDER_PLAN: lambda a, n: _L('出场顺序：在相邻属性组合最多的顺序中比较模拟 DPS 后选出'),
    ASSUME_FULL_GAUGE_LOOPS: lambda a, n: _LF('第 {0} 轮开始时所有队员环合值补满 100；其他轮沿用累积的环合值').format(
        loops_text(a) or "1"),
    ASSUME_FORM_ACTIONS: lambda a, n: _LF('{0} 的形态动作按动画数据计算伤害').format(_name(a[0] if a else "?", n)),
    ASSUME_FORM_WINDOW: lambda a, n: _LF('{0} 的「{1}」持续 {2} 秒，形态内动作按剩余时间安排').format(
        _name(a[0] if a else "?", n), form_name_text(a[1] if len(a) > 1 else ""), f"{_num(a, 2):g}"),
    LIMIT_FORM_CUT: lambda a, n: _LF('{0} 的形态时间只够 {1} 组（已审核循环为 {2} 组）').format(
        _name(a[0] if a else "?", n), int(_num(a, 1)), int(_num(a, 2))),
    LIMIT_FORM_OVERRUN: lambda a, n: _LF('{0} 的形态内动作超出形态时间 {1} 秒（按已审核循环保留）').format(
        _name(a[0] if a else "?", n), f"{_num(a, 1):.1f}"),
    LIMIT_FORM_WINDOW_MISSED: lambda a, n: _LF('{0} 的形态收尾动作在形态开始后 {1} 秒，不在可用时间 {2}–{3} 秒内').format(
        _name(a[0] if a else "?", n), f"{_num(a, 1):.1f}", f"{_num(a, 2):g}", f"{_num(a, 3):g}"),
    LIMIT_FORM_TIMING_ASSUMED: lambda a, n: _LF('{0} 的部分形态动作由召唤的伤害体造成，命中间隔为推断').format(
        _name(a[0] if a else "?", n)),
    ASSUME_FORK_SUPPLEMENT: lambda a, n: _LF('Global 补充规则（依据说明文与数据库数值）：{0}').format(
        _members_text(a, n)),
    ASSUME_FORK_DEDUP: lambda a, n: _LF('已修正常驻效果的重复计算：{0}').format(_members_text(a, n)),
    LIMIT_RAVEN_MALICE: lambda a, n: _L('黑羽「恶意」追加伤害（按消耗量计算）未计入'),
    LIMIT_FIGHT_END: lambda a, n: _L('战斗在最后一次出场结束时截止，之后的持续伤害不计入'),
    PLAN_CARRY: lambda a, n: _LF('变身输出：{0}').format(_name(a[0] if a else "?", n)),
    PLAN_CARRY_MAIN: lambda a, n: _LF('主输出：{0}').format(_name(a[0] if a else '?', n)),
    PLAN_BEST_DPS: lambda a, n: _LF('在 {0} 个候选顺序中模拟 DPS 最高').format(int(_num(a, 0))),
    PLAN_CARRY_FIRST: lambda a, n: _LF('{0} 先手：最后一轮的持续伤害与增益不会被战斗结束截断').format(
        _name(a[0] if a else "?", n)),
    PLAN_CARRY_LAST: lambda a, n: _LF('{0} 最后登场：所有增益都在其登场前生效').format(_name(a[0] if a else "?", n)),
    PLAN_COVERAGE: lambda a, n: (
        _LF('形态时间 {1} 秒中有 {0} 秒处于排序计入的队伍增益或覆纹/浸染内').format(f"{_num(a, 0):.1f}", f"{_num(a, 1):.1f}")
        if len(a) > 1 else _LF('形态时间中 {0} 秒有队伍增益或覆纹/浸染').format(f"{_num(a, 0):.1f}")),
    PLAN_CARRY_FIRST_DPS: lambda a, n: _LF('{0} 先手：模拟 DPS 最高').format(_name(a[0] if a else "?", n)),
    PLAN_CARRY_LAST_DPS: lambda a, n: _LF('{0} 最后登场：模拟 DPS 最高').format(_name(a[0] if a else "?", n)),
    PLAN_COVER_TRADE: lambda a, n: _LF('所选顺序的形态增益覆盖 {0} 秒，少于其他候选的 {1} 秒；按模拟 DPS 选择').format(
        f"{_num(a, 0):.1f}", f"{_num(a, 1):.1f}"),
    PLAN_Q_CASTS: lambda a, n: _LF('该顺序可释放更多极轨终结（{0} 次）').format(int(_num(a, 0))),
    # resources (team_resources, 2026-10-14)
    ASSUME_RESOURCE_MODEL: lambda a, n: _LF('资源模型：{0}').format(resource_model_text(a[0] if a else "")),
    ASSUME_GAUGE_ACCUMULATED: lambda a, n: _L('环合值按每次命中累积，第 1 轮开始时为 100，之后不再自动补满'),
    ASSUME_GAUGE_FALLBACK: lambda a, n: _LF('第 {0} 轮开始时 {1} 的环合值补满 100（缺少数据时的固定规则）').format(
        int(_num(a, 0)), _members_text(a[1:], n)),
    ASSUME_ENERGY_GATED: lambda a, n: _LF('{0} 的极轨终结按终结能量检查（消耗 {1}）；能量不足时跳过').format(
        _name(a[0] if a else "?", n), f"{_num(a, 1):g}"),
    ASSUME_START_ENERGY_FULL: lambda a, n: _L('开场时极轨终结能量已满（实测：首次释放均在战斗初期）'),
    ASSUME_CHARGE_EFF: lambda a, n: _L('终结能量获取 = 每次命中的充能量 ×（1 + 充能效率）'),
    ASSUME_CD_WAIT: lambda a, n: _LF('冷却未结束时插入等待后再使用（共 {0:.1f} 秒）').format(_num(a, 0)),
    ASSUME_RESOURCE_CLOCK: lambda a, n: (_L('冷却与时计按包含时停的实际时间计算') if (a and a[0] == "wall")
                                         else _L('冷却与时计按扣除时停后的战斗时间计算')),
    ASSUME_OWN_RESOURCE: lambda a, n: _LF('{0} 使用自身资源「{1}」，按游戏数据计算').format(
        _name(a[0] if a else "?", n), own_resource_text(a[1] if len(a) > 1 else "")),
    ASSUME_HOTORI_INTERLUDE: lambda a, n: (
        _LF('{0} 等待「{1}」蓄满共约 {2:.1f} 秒（每次出场 {3} 秒；视为队友行动的时间，未计入时间轴）').format(
            _name(a[0] if a else "?", n), own_resource_text(a[1] if len(a) > 1 else ""), _num(a, 2), str(a[3]))
        if len(a) > 3 and a[3] else
        _LF('{0} 等待「{1}」蓄满约 {2:.1f} 秒（视为队友行动的时间，未计入时间轴）').format(
            _name(a[0] if a else "?", n), own_resource_text(a[1] if len(a) > 1 else ""), _num(a, 2))),
    ASSUME_CUSTOM_MODEL: lambda a, n: _LF('冷却与能量的默认数值来自：{0}').format(custom_model_text(a[0] if a else "")),
    ASSUME_CHARGE_ENERGY_SHOWN: lambda a, n: _LF('盈蓄给场上队员的终结能量已计入显示的能量（共 +{0}，{1} 次；不参与能量检查）').format(
        f"{_num(a, 0):g}", int(_num(a, 1))),
    ASSUME_CUSTOM_CD_RULES: lambda a, n: _LF('{0} 的冷却规则按觉醒与技能数据计算：{1}').format(
        _name(a[0] if a else "?", n), _join_texts(cd_rule_text(code) for code in a[1:])),
    ASSUME_ENERGY_TRACKED: lambda a, n: _L('每次命中的终结能量都会累计并显示；消耗量未知的队员不检查能量'),
    LIMIT_ENERGY_UNKNOWN: lambda a, n: _LF('{0} 的终结能量消耗未知，不检查能量（照常释放）').format(_members_text(a, n)),
    LIMIT_COST_CONTESTED: lambda a, n: _LF('{0} 的终结能量消耗 {1} 来自游戏已不引用的旧数据表，未用于检查').format(
        _name(a[0] if a else "?", n), f"{_num(a, 1):g}"),
    LIMIT_ENERGY_SCALE: lambda a, n: _L('社区资料的终结能量消耗（100/120）与每次命中的充能量是否同一单位尚未确认，只作显示'),
    LIMIT_CD_UNKNOWN: lambda a, n: _LF('{0} 的 {1} 冷却时间未知，不检查').format(
        _name(a[0] if a else "?", n), _join_texts(cd_kind_text(k) for k in str(a[1] if len(a) > 1 else "").split("/"))),
    LIMIT_CD_COMMUNITY: lambda a, n: _LF('{0} 的冷却时间：{1}（社区资料，可信度低）').format(
        _name(a[0] if a else "?", n), str(a[1]) if len(a) > 1 else ""),
    LIMIT_CD_NONE_STRUCT: lambda a, n: _LF('{0} 的援护技与极限反击在游戏数据中没有冷却设定，仅受环合值与闪避冷却限制').format(
        _members_text(a, n)),
    LIMIT_ENERGY_SHORT: lambda a, n: _LF('{0} 因终结能量不足跳过了 {1} 次极轨终结').format(
        _name(a[0] if a else "?", n), int(_num(a, 1))),
    LIMIT_CD_WAITED: lambda a, n: _LF('{0} 等待冷却共 {1:.1f} 秒').format(_name(a[0] if a else "?", n), _num(a, 1)),
    LIMIT_CD_WAIT_TOO_LONG: lambda a, n: _LF('{0} 的 {1} 冷却超过 {2} 秒，已跳过（请检查数据）').format(
        _name(a[0] if a else "?", n), cd_kind_text(a[1]) if len(a) > 1 else "", f"{_num(a, 2):g}"),
    LIMIT_FORM_NOT_ENTERED: lambda a, n: _LF('{0} 第 {1} 轮未进入形态（极轨终结被跳过），形态内动作未执行').format(
        _name(a[0] if a else "?", n), int(_num(a, 1))),
    LIMIT_OWN_RESOURCE_UNIT: lambda a, n: _LF('{0} 的自身资源「{1}」每次获得量的单位未确认，只显示不检查').format(
        _name(a[0] if a else "?", n), own_resource_text(a[1] if len(a) > 1 else "")),
    LIMIT_OWN_RESOURCE_DRAIN: lambda a, n: _LF('{0} 的「{1}」在时停中的消耗起点与终结后的剩余量未确认，按较严格的读法计算').format(
        _name(a[0] if a else "?", n), own_resource_text(a[1] if len(a) > 1 else "")),
    LIMIT_MIDVISIT_SWAP: lambda a, n: _LF('{0} 的“离场再入场”步骤无法在一次出场中模拟，按原地等待计算').format(
        _name(a[0] if a else "?", n)),
    LIMIT_TIME_ONLY_CREDIT: lambda a, n: _LF('{0} 的仅计时步骤按技能数据计入环合值（近似）').format(
        _name(a[0] if a else "?", n)),
    LIMIT_GAUGE_PARTIAL: lambda a, n: _LF('{0} 有 {1} 个仅计时的步骤在游戏中会累积环合值（结果偏低）').format(
        _name(a[0] if a else "?", n), int(_num(a, 1))),
    LIMIT_ENERGY_EVENT_UNMODELLED: lambda a, n: _LF('{0} 的能量与冷却相关效果未模拟：{1}').format(
        _name(a[0] if a else "?", n), _join_texts(unmodelled_text(code) for code in a[1:])),
    LIMIT_CHARGE_ENERGY_GATED: lambda a, n: _L('盈蓄的终结能量未计入能量检查（偏保守）'),
    LIMIT_GAUGE_EFFICIENCY: lambda a, n: _L('环合效率修正（覆纹 −50% 等）未计入'),
    LIMIT_CD_UNCLASSIFIED: lambda a, n: _LF('{0} 的第 {1} 步冷却类型未建模，未检查冷却').format(
        _name(a[0] if a else "?", n), int(_num(a, 1))),
    LIMIT_CD_CLOCK_CONFLICT: lambda a, n: _LF('{0} 的 {1} 冷却 {2} 秒长于录像中两次使用之间扣除时停后的 {3} 秒（冷却是否在时停中计时、或被效果重置，尚未确认）').format(
        _name(a[0] if a else "?", n), cd_kind_text(a[1]) if len(a) > 1 else "", f"{_num(a, 2):g}", f"{_num(a, 3):g}"),
    LIMIT_CD_CHARGES: lambda a, n: _LF('{0} 的变轨技能可储存 {1} 次，每次 {2} 秒恢复（按依次恢复计算，含义未确认）').format(
        _name(a[0] if a else "?", n), int(_num(a, 1)), f"{_num(a, 2):g}"),
    LIMIT_RESOURCE_DATA_MISSING: lambda a, n: _LF('{0} 没有终结能量与冷却数据：不检查冷却与能量，环合值按固定规则补满').format(
        _name(a[0] if a else "?", n)),
    LIMIT_HIT_CREDIT: lambda a, n: _LF('{0} 的变轨技能有 {3} 次命中（召唤物等）未排入时间轴：每次使用补计终结能量 {1} 与环合值 {2}（{4}；伤害未计入）').format(
        _name(a[0] if a else "?", n), f"{_num(a, 1):g}", f"{_num(a, 2):g}", int(_num(a, 3)),
        confidence_label(a[4] if len(a) > 4 else "")),
    LIMIT_HIT_UNKNOWN: lambda a, n: _LF('{0} 的变轨技能有一段命中未排入时间轴且次数未知：其终结能量与环合值未计入（结果偏低）').format(
        _name(a[0] if a else "?", n)),
    # D3 (2026-10-14): not ready -> swap out at once (team) / wait (alone)
    ASSUME_NOT_READY_SWAP: lambda a, n: _LF('技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员：本次出场剩余步骤不执行，援护技登场按通常规则判定；冷却还差不到 {0:.1f} 秒（战斗时间）时原地等待后使用；所有队员都未就绪时等待最早就绪的队员').format(
        _num(a, 0, _swap_min_wait_s())),
    ASSUME_SHORT_WAIT: lambda a, n: _LF('{0} 冷却还差不到 {3:.1f} 秒时原地等待后使用：{1} 次，共 {2:.2f} 秒').format(
        _name(a[0] if a else "?", n), int(_num(a, 1)), _num(a, 2), _num(a, 3, _swap_min_wait_s())),
    ASSUME_NOT_READY_SOLO: lambda a, n: _L('单人没有可切换的队员：技能未就绪时原地等待（等待期间不攻击）'),
    LIMIT_EARLY_SWAP: lambda a, n: (
        _LF('{0} 因技能未就绪提前切换 {1} 次（共 {2} 个步骤未执行）').format(
            _name(a[0] if a else "?", n), int(_num(a, 1)), int(_num(a, 2))) if int(_num(a, 2)) else
        _LF('{0} 因技能未就绪提前切换 {1} 次').format(_name(a[0] if a else "?", n), int(_num(a, 1)))),
    LIMIT_ALL_BLOCKED: lambda a, n: _LF('所有队员的技能都未就绪：{0} 原地等待 {1:.1f} 秒（{2} 最早就绪）').format(
        _name(a[0] if a else "?", n), _num(a, 1), _name(a[2] if len(a) > 2 else "?", n)),
}


def swap_out_text(reason: str, kind: str = "", remaining_s=None, energy=None, cost=None) -> str:
    """Step text of an early swap (D3): why the step was not ready, then "swap out at once"."""
    if reason == SWAP_REASON_ENERGY:
        return _LF('终结能量不足（{0:.0f}/{1:.0f}）→ 立即切换').format(float(energy or 0.0), float(cost or 0.0))
    left = max(0.1, float(remaining_s or 0.0))     # a few ms left reads "0.1 s", never "0.0 s" (review F4)
    if reason == SWAP_REASON_CLOCK:
        return _LF('时计不足（还差 {0:.1f} 秒）→ 立即切换').format(left)
    return _LF('冷却未就绪（{0}，还差 {1:.1f} 秒）→ 立即切换').format(cd_kind_text(kind), left)


def _swap_min_wait_s() -> float:
    from src.services.team_resources import SWAP_MIN_WAIT_S

    return float(SWAP_MIN_WAIT_S)


def short_wait_text(remaining_s, kind: str = "", threshold_s=None) -> str:
    """Step text of a cooldown wait under the swap threshold (user decision 2026-10-18): waited, no swap."""
    return _LF('等待冷却 {0:.2f} 秒（< {1:.1f} 秒，不切换；{2}）').format(
        float(remaining_s or 0.0), float(_swap_min_wait_s() if threshold_s is None else threshold_s), cd_kind_text(kind))


def swap_dropped_text(count) -> str:
    """Approved steps of the visit that were not run after the early swap."""
    return _LF('本次出场其余 {0} 个步骤未执行').format(int(count or 0))


def _join_texts(items) -> str:
    """A list in running text: the separator is a template, so ko / en read ", " and zh / ja "、" (review F-UX2)."""
    out = None
    for item in items:
        if not item:
            continue
        out = item if out is None else _LF('{0}、{1}').format(out, item)
    return out or ""


def join_list(items) -> str:
    """Public form of the list join (the view lists member names with it)."""
    return _join_texts(items)


def custom_model_text(code: str) -> str:
    """Where a custom cycle's default cooldown / energy numbers come from (the resource level; review F9)."""
    return {RESOURCE_LEGACY: _L('旧版直接输入数值表'), RESOURCE_DATA: _L('游戏数据'),
            RESOURCE_COMMUNITY: _L('游戏数据 + 社区冷却')}.get(str(code), str(code))


def step_event_text(code, amount) -> str:
    """Tooltip line of one step event (ResourceState.after / layout credits): energy gains read "+n"; the reset rules
    name what they did; a node-rule group code (``awakening_<group>_...``) uses its group's text."""
    code = str(code or "")
    if code in ("q_resets_e", "counter_resets_e", "e_resets_q"):
        return cd_rule_text(code)
    if code.startswith("awakening_"):
        rules = _node_rules()
        try:
            text = rules.note_text(code, (amount,), None) if rules is not None else None
        except Exception:
            text = None
        if text:
            return text
    return _LF('额外获得 +{0:g}').format(float(amount or 0.0))


def cd_rule_text(code: str) -> str:
    """Cooldown rules of team_resource_data (awakening / skill effects) applied in both modes."""
    return {"q_resets_e": _L('极轨终结刷新变轨技能冷却'), "counter_resets_e": _L('极限反击刷新变轨技能冷却'),
            "e_resets_q": _L('变轨技能刷新极轨终结冷却'),
            "extra_e_after_basics": _L('5 次普通攻击后可额外使用一次变轨技能'),
            "e_cd_add": _L('觉醒缩短变轨技能冷却'), "cd_offset": _L('冷却从技能生效时开始计算')}.get(str(code), str(code))


def resource_model_text(code: str) -> str:
    return {RESOURCE_LEGACY: _L('旧规则（第 1、3 轮补满，不检查能量与冷却）'), RESOURCE_DATA: _L('游戏数据'),
            RESOURCE_COMMUNITY: _L('游戏数据 + 社区冷却')}.get(str(code), str(code))


def own_resource_text(name_zh: str) -> str:
    """Own resource names (game terms, built with _L: no display-layer entry)."""
    return {"非闭合时计": _L('非闭合时计'), "桀骜斗志": _L('桀骜斗志')}.get(str(name_zh), str(name_zh))


def cd_kind_text(kind: str) -> str:
    return {"E": _L('变轨技能'), "E_alt": _L('变轨技能（噤念/如此罪状）'), "E_short": _L('变轨技能（短按）'),
            "Q": _L('极轨终结'), "QTE": _L('援护技'), "counter": _L('极限反击'), "evade": _L('闪避')}.get(
        str(kind), str(kind))


def confidence_label(conf: str) -> str:
    """Short pill text of a data confidence."""
    return {"db_value": _L('游戏数据'), "db_struct_none": _L('游戏数据'), "db_text": _L('说明文'),
            "measured_value": _L('实测'), "db_legacy": _L('旧数据表'), "inference": _L('推断'),
            "community_low": _L('社区·低'), "community_very_low": _L('社区·极低'), "user": _L('用户填写'),
            "measured_bound": _L('未知'), "unknown": _L('未知')}.get(str(conf), str(conf))


_UNMODELLED = {
    "lacrimosa_a6_support": lambda: _L('觉醒效果 ⑥ 自动援护技'),
    "lacrimosa_e_steal_variant": lambda: _L('「恶魔的礼物」的能量'),
    "linko_a6_coattack_charge": lambda: _L('觉醒效果 ⑥ 协同攻击充能'),
    "linko_a5_coattack_reaction": lambda: _L('觉醒效果 ⑤ 协同攻击触发的环合反应'),
    "hotori_a3_refund": lambda: _L('觉醒效果 ③ 返还时计'),
    "hotori_a4_per_kill": lambda: _L('觉醒效果 ④ 击败目标恢复时计'),
    "hotori_e_extra_drain": lambda: _L('变轨技能记录期间额外消耗的时计'),
    "edgar_e_channel_extension": lambda: _L('持续施放延长冷却'),
    "edgar_passive_charge_120": lambda: _L('盈蓄时获得 120 点终结能量'),
    "cang_a1_cd_cut": lambda: _L('觉醒效果 ① 缩短冷却'),
    "nanally_a1_follow_up_energy": lambda: _L('觉醒效果 ① 追加攻击 +2.5'),
    "hathor_speed_stack_energy": lambda: _L('每层闪送之力 +5'),
    "kuhara_bud_boom_energy": lambda: _L('致约清算 +40'),
    "iloi_a6_energy": lambda: _L('觉醒效果 ⑥ +50'),
    "sagiri_a5_float_refill": lambda: _L('觉醒效果 ⑤ 浮空时回满能量'),
    "daffodill_a2_refill": lambda: _L('觉醒效果 ② 反击失败时回满能量'),
    "fadia_threshold_refill": lambda: _L('达到破灭阈值时回满能量'),
    "chiichan_charge_passive": lambda: _L('盈蓄强化 +4'),
    "akane_release_pending": lambda: _L('角色未上线，数据待确认'),
    "akane_values_unverified": lambda: _L('国服 10-15 已上线；冷却与终结能量未确认'),
    "skia_shadow_exit_variant": lambda: _L('潜影结束动作的两种版本'),
    "chaos_e_short_binding": lambda: _L('短按变轨技能的 2 秒冷却'),
    "raven_witch_q_row": lambda: _L('魔女形态极轨终结的冷却'),
    "zankou_a4_magic_q": lambda: _L('觉醒效果 ④「梦魇生花」'),
}


def unmodelled_text(code: str) -> str:
    build = _UNMODELLED.get(str(code))
    return build() if build else str(code)


# ── awakening nodes (free selection, team_awakening; Korean UI "돌파") ─────────
# A6: team_resource_data ``unmodelled`` codes bound to an awakening node -> (character_id, node): shown only when the
# member selected the node (codes not listed here, e.g. akane_release_pending / *_variant, are always shown).  Groups
# add more through awakening_node_rules NodeInfo.unmodelled_codes.
UNMODELLED_NODE = {
    "sagiri_a5_float_refill": (1003, "Effect5"),
    "lacrimosa_a6_support": (1004, "Effect6"),
    "nanally_a1_follow_up_energy": (1010, "Effect1"),
    "cang_a1_cd_cut": (1023, "Effect1"),
    "zankou_a4_magic_q": (1036, "Effect4"),
    "hotori_a3_refund": (1052, "Effect3"),
    "hotori_a4_per_kill": (1052, "Effect4"),
    "daffodill_a2_refill": (1054, "Effect2"),
    "linko_a6_coattack_charge": (1072, "Effect6"),
    "linko_a5_coattack_reaction": (1072, "Effect5"),
    "iloi_a6_energy": (1075, "Effect6"),
}
# The approved rotation assumes these nodes (design §2.2; a limit is shown when the member did not select one).  Empty
# since the 10-18 integration (group_1.md §7.1): Zankou's reviewed rotation reaches 血宴入梦时 through 灭 without
# 「梦魇生花」 (Effect4), and {④}@1 equals A0; nodes may still declare it (NodeInfo.rotation_assumed).
ROTATION_ASSUMES = frozenset()


def _node_rules():
    """The awakening_node_rules package (None when it cannot be imported)."""
    try:
        from src.services import awakening_node_rules
    except Exception:
        return None
    return awakening_node_rules


def node_label(node) -> str:
    """①..⑥ for an ordinary effect (language-neutral), 共鸣3 / 共鸣6 (translated) for a resonance."""
    from src.services import team_awakening

    text = str(node)
    canonical = team_awakening.node_id(text)
    if canonical in team_awakening.NODE_IDS:
        return team_awakening.circled(canonical)
    if canonical in team_awakening.RESONANCE_LEVEL:
        return _LF('共鸣{0}').format(team_awakening.RESONANCE_LEVEL[canonical])
    return text


def node_labels(nodes) -> str:
    """Circles run together under one 觉醒效果 caption ("돌파 효과 ①③⑤"); resonances ("공명3") joined with the list
    separator (review UX F9: the templates no longer put the caption in front of a resonance)."""
    from src.services import team_awakening

    circles = "".join(node_label(n) for n in nodes if team_awakening.node_id(n) in team_awakening.NODE_IDS)
    if circles:
        circles = _LF('觉醒效果 {0}').format(circles)     # keeps its provenance (re-rendered on a language switch)
    others = [node_label(n) for n in nodes if team_awakening.node_id(n) not in team_awakening.NODE_IDS]
    items = ([circles] if circles else []) + others
    return join_list(items) if len(items) > 1 else (items[0] if items else "")


def unmodelled_for(character_id, codes, selection=None) -> tuple:
    """A6: the member's unmodelled codes to show - a node-bound code only when the node is selected, a code a
    selected node's rules make obsolete (NodeInfo.resolves_codes) never.  ``selection`` None keeps every code."""
    codes = tuple(codes or ())
    if selection is None:
        return codes
    from src.services import team_awakening

    cid = int(character_id)
    bound = dict(UNMODELLED_NODE)
    resolved: set = set()
    rules = _node_rules()
    if rules is not None:
        for (owner, node), info in rules.all_node_info().items():
            for code in info.unmodelled_codes:
                bound[str(code)] = (owner, node)
            if owner == cid and rules.group_enabled(info.group) and team_awakening.unlocked(selection, node):
                resolved.update(info.resolves_codes)
    out = []
    for code in codes:
        owner = bound.get(str(code))
        if owner is not None and int(owner[0]) == cid and not team_awakening.unlocked(selection, owner[1]):
            continue
        if code in resolved:
            continue
        out.append(code)
    return tuple(out)


def rotation_assumed_nodes(character_id) -> tuple:
    """Nodes the member's approved rotation assumes (ROTATION_ASSUMES + NodeInfo.rotation_assumed)."""
    cid = int(character_id)
    nodes = [node for owner, node in sorted(ROTATION_ASSUMES) if owner == cid]
    rules = _node_rules()
    if rules is not None:
        for node, info in sorted(rules.nodes_of(cid).items()):
            if info.rotation_assumed and node not in nodes:
                nodes.append(node)
    return tuple(nodes)


def node_rule_notes(prepared, run=None) -> tuple[list, list, set]:
    """(assumptions, limits, limit codes to drop) of the awakening node rules of a run (team_simulation_service
    ._with_node_notes): rules applied, expected-value nodes, selected nodes not priced, hook notes, obsolete codes."""
    assume: list = []
    limits: list = []
    drop: set = set()
    if prepared is None:
        return assume, limits, drop
    rules = _node_rules()
    order = {n: i for i, n in enumerate(("Effect1", "Effect2", "Effect3", "Effect4", "Effect5", "Effect6",
                                         "resonance_3", "resonance_6"))}
    for cid, nodes in sorted(prepared.applied().items()):
        assume.append(note(ASSUME_AWAKENING_RULES, cid, *nodes))
    if rules is not None:
        for cid, member in sorted(prepared.members.items()):
            expected, unpriced = [], []
            for node, info in sorted(rules.nodes_of(cid).items(), key=lambda kv: order.get(kv[0], 99)):
                if not rules.group_enabled(info.group) or not member.has(node):
                    continue
                if info.expected_value:
                    expected.append(node)
                if info.bucket != "now" and info.category != "none":
                    unpriced.append(node)
                drop.update(info.resolves_codes)
            if expected:
                assume.append(note(ASSUME_AWAKENING_EXPECTED, cid, *expected))
            if unpriced:
                limits.append(note(LIMIT_AWAKENING_UNPRICED, cid, *unpriced))
    sinks = [getattr(prepared, "notes", None)]
    if run is not None:
        sinks.append(getattr(getattr(run, "node_hooks", None), "notes", None))
        layout = getattr(run, "layout", None)
        sinks.append(getattr(getattr(layout, "node_hooks", None), "notes", None))
        sinks.append(getattr(getattr(getattr(layout, "resources", None), "hooks", None), "notes", None))
    for sink in sinks:
        for kind, code, args in sink or ():
            item = note(code, *args)
            target = assume if kind == "assume" else limits
            if item not in target:
                target.append(item)
    return assume, limits, drop

_EFFECTS = {
    EFFECT_SCORCH_TICKS: lambda a: _LF('浊燃 {0} 跳').format(int(_num(a, 0))),
    EFFECT_SCORCH_REFRESH: lambda a: _L('刷新了生效中的持续时间'),
    EFFECT_SCORCH_DORMANT: lambda a: _L('没有持续伤害跳将其激活，未造成跳伤'),
    EFFECT_SCORCH_ACTIVATED: lambda a: _LF('{0} 后由持续伤害跳激活').format(_secs(_num(a, 0))),
    EFFECT_ZANKOU_VARIANT: lambda a: "",
    EFFECT_LAYERS: lambda a: _LF('{0} 层').format(int(_num(a, 0, 1))),
    EFFECT_HEXED_RATIO: lambda a: _LF('覆纹追加比例 {0:.1%}').format(_num(a, 0)),
    EFFECT_STAIN_RATIO: lambda a: _LF('浸染增伤 {0:.0%}').format(_num(a, 0)),
    EFFECT_BOOSTED_HITS: lambda a: _LF('{0} 个命中获得加成').format(int(_num(a, 0))),
    EFFECT_WINDOW: lambda a: _LF('持续 {0} 秒').format(f"{_num(a, 0):g}"),
    EFFECT_REMORA_DURATION: lambda a: _LF('持续 {0} 秒').format(f"{_num(a, 0):g}"),
    EFFECT_EXTENDED: lambda a: _L('刷新了生效中的持续时间'),
    EFFECT_SETTLE_AFTER: lambda a: _LF('{0} 后结算').format(_secs(_num(a, 0))),
    EFFECT_NOVA_REPLACED: lambda a: _L('被同一队员之后的黯星替换，不结算'),
    EFFECT_NOVA_RETIMED: lambda a: _L('与之后的黯星一起结算'),
    EFFECT_BLOSSOM_PLANTS: lambda a: _LF('创生花 {0} 朵').format(int(_num(a, 0, 1) * _num(a, 1, 5))),
    EFFECT_BLOSSOM_FLOWERS: lambda a: _LF('创生花 {0} 朵').format(int(_num(a, 0))),
    EFFECT_FLOWERS_DROPPED: lambda a: _LF('超过数量上限，移除 {0} 朵创生花').format(int(_num(a, 0))),
    EFFECT_CHARGE_ENERGY: lambda a: _LF('场上队员能量 +{0}（{1} 朵创生花命中）').format(
        f"{_num(a, 0):g}", int(_num(a, 1))),
    EFFECT_TOPPLE_REDUCTION: lambda a: _LF('倾陷上限降低 {0:.0%}').format(_num(a, 0)),
    EFFECT_LED_TO_CHARGE: lambda a: _LF('引发 {0}').format("盈蓄"),
    EFFECT_LED_TO_DISCORD: lambda a: _LF('引发 {0}').format("失谐"),
    EFFECT_COMBO_OF: lambda a: _LF('{0} 与 {1} 同时生效').format(
        str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
    EFFECT_TRUNCATED: lambda a: _LF('{0} 个反应命中在战斗结束后，未计入').format(int(_num(a, 0, 1))),
    EFFECT_UNREPLAYABLE: lambda a: _LF('{0} 个命中无法计算').format(int(_num(a, 0))),
    EFFECT_EFFECT_ONLY: lambda a: _L('仅效果，无伤害'),
}

NOTE_CODES = tuple(_NOTES)
EFFECT_CODES = tuple(_EFFECTS)


def note_text(item, names: Mapping | None = None) -> str:
    """Assumption / limit item -> display text (provenance string); unknown codes come back raw.

    ``names`` maps character ids to Chinese names for codes that carry a character id."""
    code, args = split_note(item)
    build = _NOTES.get(code)
    if build is None and code.startswith("custom_"):       # custom-cycle notes live in their own module
        try:
            from src.services.team_custom_cycle_texts import NOTES as custom_notes

            build = custom_notes.get(code)
        except Exception:
            build = None
    if build is None and code.startswith("awakening_"):    # awakening node-rule group codes: their group module
        rules = _node_rules()
        try:
            text = rules.note_text(code, args, names) if rules is not None else None
        except Exception:
            text = None
        if text is not None:
            return text
    if build is None:
        return ":".join((code, *map(str, args))) if args else code
    try:
        return build(args, names)
    except Exception:
        return code


def merge_effects(items) -> list:
    """Effect items in first-seen order: exact duplicates dropped, SUMMED_EFFECTS counts added up."""
    out: list = []
    seen: dict = {}
    for item in items:
        code, args = split_note(item)
        if code in SUMMED_EFFECTS:
            if code in seen:
                total = _num(out[seen[code]][1], 0, 1) + _num(args, 0, 1)
                out[seen[code]] = (code, (int(total),))
            else:
                seen[code] = len(out)
                out.append((code, (int(_num(args, 0, 1)),)))
            continue
        key = (code, tuple(map(str, args)))
        if key not in seen:
            seen[key] = len(out)
            out.append((code, args))
    return out


def effect_text(item) -> str:
    """ReactionTrace effect item -> display text (provenance string); unknown codes come back raw,
    HIDDEN_EFFECTS as ""."""
    code, args = split_note(item)
    build = _EFFECTS.get(code)
    if build is None:
        return ":".join((code, *map(str, args))) if args else code
    try:
        return build(args)
    except Exception:
        return code
