# 队伍模拟「直接输入」模式：循环文本的解析与生成（角色 + 动作，用 > 连接）。
"""Notation of the team simulator's custom-cycle mode.

One flat team-wide sequence of ``<character> <action...>`` segments separated by ``>``::

    제로 서포트 > 제로 E > 제로 평타 평타 평타 > 일로이 교체 > 일로이 Q > 일로이 E > 일로이 평타

``parse(text, team_ids)`` turns the text into :class:`CustomStep` codes (character id + action code) and reports
every problem with its text span; ``format_steps(steps, lang)`` writes the canonical text back.  The model stores
codes only, so a language switch re-renders the text from the same steps.  The names and aliases of all four
languages are accepted at all times.

Grammar (spec §1.2)::

    sequence := segment ( SEP segment )*         SEP: > ＞ → -> => ⇒ » ; newline
    segment  := [ character ] item+              a segment without a name continues with the previous member
    item     := entry | action [ #N ] [ repeat ] | wait | raw [ repeat ]
    entry    := support | swap                   first item of its segment / name group
    repeat   := (x|X|×|*) N | N                  "평타x3" = "평타3" = "평타 평타 평타"; a number is always a repeat;
                                                 a counter word may follow it ("3번", "3회", "3回", "3次", "3 times")
    #N       := position in the chain / variants ("E#2", "평타#4"; Korean "4타" = 평타#4, but right after a plain
                평타 it counts the hits: "평타 3타" = 평타x3)
    wait     := WAIT seconds [초|s|sec|秒]
    raw      := [ability_id/selector]
    ( ... )  remarks are ignored

Standard library only, apart from the generated palette (``team_custom_actions``), which is imported lazily.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Sequence

ENTRY_ACTIONS = ("support", "swap")
SLOT_ACTIONS = ("basic", "heavy", "skill", "skill_hold", "ult", "counter", "plunge", "entry_attack", "special")
TIME_ACTIONS = ("wait", "dodge")
RAW_ACTION = "raw"
ALL_ACTIONS = ENTRY_ACTIONS + SLOT_ACTIONS + TIME_ACTIONS + (RAW_ACTION,)
LANGS = ("ko", "en", "ja", "zh")
MAX_STEP_REPEAT = 20
MAX_WAIT_S = 60.0
MAX_STEPS = 200
MAX_ACTIONS = 600

# Hand-written.  The first alias of a language is the canonical token the formatter writes; every alias of every
# language is accepted whatever the UI language is.  Must stay a pure literal (the palette generator reads it
# with ast.literal_eval).
TOKEN_ALIASES = {
    "support": {"ko": ("서포트", "서폿", "지원", "서포트스킬", "서포트 스킬", "QTE"),
                "en": ("support", "sup", "qte", "assist"),
                "ja": ("サポート", "支援", "支援スキル"),
                "zh": ("援护", "援护技")},
    "swap": {"ko": ("교체", "교대", "스왑"),
             "en": ("swap", "switch", "tag"),
             "ja": ("交代", "スワップ"),
             "zh": ("切换", "切人", "换人")},
    "basic": {"ko": ("평타", "일반공격", "일반 공격", "기본공격", "평"),
              "en": ("basic", "a", "na", "attack"),
              "ja": ("通常", "通常攻撃"),
              "zh": ("普攻", "普通攻击", "平a")},
    "heavy": {"ko": ("강공격", "강공", "평타홀드", "평꾹", "차지공격", "Z"),
              "en": ("heavy", "z", "charged", "ca"),
              "ja": ("強攻撃", "重撃", "長押し攻撃"),
              "zh": ("重击", "蓄力攻击", "长按普攻")},
    "skill": {"ko": ("E", "스킬", "바이레일", "바이레일스킬"),
              "en": ("E", "skill"),
              "ja": ("E", "スキル"),
              "zh": ("E", "技能", "变轨", "变轨技能")},
    "skill_hold": {"ko": ("E홀드", "홀드E", "E길게", "E꾹", "스킬홀드"),
                   "en": ("E-hold", "ehold", "holde", "hold-e"),
                   "ja": ("E長押し", "長押しE"),
                   "zh": ("E长按", "长按E", "蓄力E")},
    "ult": {"ko": ("Q", "궁", "궁극기", "울티", "울티메이트"),
            "en": ("Q", "ult", "ultimate", "burst"),
            "ja": ("Q", "アルティメット"),
            "zh": ("Q", "终结", "极轨终结", "大招")},
    "counter": {"ko": ("반격", "극한반격", "극한 반격", "회피반격"),
                "en": ("counter", "extreme counter"),
                "ja": ("カウンター", "極限カウンター", "反撃"),
                "zh": ("反击", "极限反击")},
    "dodge": {"ko": ("회피", "대시", "닷지"),
              "en": ("dodge", "dash", "evade"),
              "ja": ("回避",),
              "zh": ("闪避",)},
    "plunge": {"ko": ("낙하", "낙하공격", "공중공격"),
               "en": ("plunge", "air"),
               "ja": ("落下", "落下攻撃"),
               "zh": ("下落", "下落攻击", "空中攻击")},
    "entry_attack": {"ko": ("등장공격", "등장"),
                     "en": ("appear", "entry"),
                     "ja": ("登場攻撃",),
                     "zh": ("登场攻击",)},
    "special": {"ko": ("특수", "특수동작"),
                "en": ("special", "sp"),
                "ja": ("特殊",),
                "zh": ("特殊",)},
    "wait": {"ko": ("대기", "딜레이"),
             "en": ("wait", "delay"),
             "ja": ("待機",),
             "zh": ("等待",)},
}
WAIT_UNITS = {"ko": "", "en": "", "ja": "", "zh": ""}        # the formatter writes bare seconds ("대기 2")

_QUOTES = "「」『』“”\"'"
_SEP = re.compile(r"->|=>|[>→⇒»;\n\r]")
_COMMENT = re.compile(r"\([^()]*\)")
_HANGUL = re.compile("[가-힣]")


# ── model ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class CustomStep:
    character_id: int
    action: str                         # one of ALL_ACTIONS
    pos: int | None = None              # 1-based chain / variant position (SLOT_ACTIONS only); None = automatic
    repeat: int = 1                     # 1..MAX_STEP_REPEAT; always 1 for ENTRY_ACTIONS and "wait"
    seconds: float | None = None        # "wait" only
    raw: tuple | None = None            # "raw" only: (ability_id, selector)
    span: tuple | None = field(default=None, compare=False, hash=False)   # parser output: offsets in the typed text


@dataclass(frozen=True)
class ParseIssue:
    code: str
    args: tuple = ()
    start: int = 0
    end: int = 0
    segment: int = 0                    # 1-based number of the segment in the typed text (0 = whole text)


@dataclass(frozen=True)
class ParseResult:
    steps: tuple = ()
    errors: tuple = ()
    warnings: tuple = ()

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.steps)


# ── palette access (generated module, imported lazily) ─────────────────────
def _data():
    from src.services import team_custom_actions

    return team_custom_actions


def _key(text: str) -> str:
    """Lookup key of a name / alias: NFKC, casefold, quotes and all whitespace removed."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(ch for ch in text.casefold() if ch not in _QUOTES and not ch.isspace())


def _pattern(text: str) -> str:
    """Regex of a name / alias: its words with optional whitespace between them."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = "".join(" " if ch in _QUOTES else ch for ch in text)
    body = r"\s*".join(re.escape(part) for part in text.split())
    return body


def _latin(ch: str) -> bool:
    return "a" <= ch.lower() <= "z"


def _alternation(texts: Iterable[str], *, repeat_ok: bool) -> re.Pattern | None:
    """Longest-first alternation.  A match ending in a Latin letter must not be followed by a Latin letter,
    except (aliases only) a repeat marker such as ``x3``."""
    parts = []
    for text in sorted({t for t in texts if t and _key(t)}, key=lambda t: (-len(_key(t)), t)):
        body = _pattern(text)
        if not body:
            continue
        if _latin(_key(text)[-1]):
            body += r"(?=[xX]\s*\d|[^A-Za-z]|$)" if repeat_ok else r"(?![A-Za-z])"
        parts.append(body)
    return re.compile("(?:" + "|".join(parts) + ")", re.IGNORECASE) if parts else None


@lru_cache(maxsize=1)
def _generic() -> dict:
    """alias key -> action code."""
    out: dict = {}
    for code, per_lang in TOKEN_ALIASES.items():
        for aliases in per_lang.values():
            for alias in aliases:
                out.setdefault(_key(alias), code)
    return out


@lru_cache(maxsize=1)
def _all_names() -> tuple[dict, re.Pattern | None]:
    """(name key -> character id, name regex) over every template character and language."""
    names: dict = {}
    for cid, per_lang in _data().NAMES.items():
        for shown in per_lang.values():
            for name in shown:
                names.setdefault(_key(name), int(cid))
    return names, _alternation((n for per in _data().NAMES.values() for shown in per.values() for n in shown),
                               repeat_ok=False)


@lru_cache(maxsize=64)
def _aliases_for(character_id: int | None) -> tuple[dict, re.Pattern | None]:
    """(alias key -> (action, pos), alias regex): the generic aliases plus the member's named actions."""
    table = {k: (code, None) for k, code in _generic().items()}
    texts = [a for per in TOKEN_ALIASES.values() for aliases in per.values() for a in aliases]
    named = _data().NAMED.get(int(character_id), {}) if character_id is not None else {}
    for alias, (slot, pos, _state) in named.items():
        key = _key(alias)
        if key in table:
            continue
        table[key] = (slot, None if int(pos) == 1 else int(pos))
        texts.append(alias)
    return table, _alternation(texts, repeat_ok=True)


def character_name(character_id: int, lang: str = "ko") -> str:
    """Display name the formatter writes (falls back to the Chinese name, then the id)."""
    per_lang = _data().NAMES.get(int(character_id)) or {}
    shown = per_lang.get(lang) or per_lang.get("zh") or ()
    return shown[0] if shown else str(character_id)


def canonical_token(action: str, lang: str = "ko") -> str:
    per_lang = TOKEN_ALIASES.get(action) or {}
    aliases = per_lang.get(lang) or per_lang.get("en") or ()
    return aliases[0] if aliases else str(action)


def slot_tables(character_id: int, slot: str) -> list[tuple[str, dict]]:
    """[(state code or "", table)] of a slot: the base table first, then the states."""
    p = _data().PALETTE.get(int(character_id)) or {}
    out = []
    if slot in (p.get("base") or {}):
        out.append(("", p["base"][slot]))
    for code, st in (p.get("states") or {}).items():
        if slot in st["slots"]:
            out.append((code, st["slots"][slot]))
    return out


def slot_max(character_id: int, slot: str) -> int:
    """Largest position any table of the slot has (0 = the member has no such slot)."""
    return max((len(table["entries"]) for _code, table in slot_tables(character_id, slot)), default=0)


def available_actions(character_id: int) -> tuple[str, ...]:
    """Action codes the member can be given, in palette order (entry and time actions included)."""
    ordered = ("support", "swap", "basic", "heavy", "skill", "skill_hold", "ult", "counter", "dodge", "plunge",
               "entry_attack", "special", "wait")
    return tuple(a for a in ordered if a in ("swap", "dodge", "wait") or slot_max(character_id, a) > 0)


# ── step <-> text ──────────────────────────────────────────────────────────
def step_label(step: CustomStep, lang: str = "ko") -> str:
    """Canonical token text of one step without the character name ("평타#4x2", "대기 1.5", "[GA/sel]")."""
    if step.action == RAW_ACTION and step.raw:
        text = f"[{step.raw[0]}/{step.raw[1]}]"
    elif step.action == "wait":
        return f"{canonical_token('wait', lang)} {float(step.seconds or 0.0):g}"
    else:
        text = canonical_token(step.action, lang)
        if step.pos is not None:
            text += f"#{int(step.pos)}"
    if int(step.repeat or 1) > 1:
        text += f"x{int(step.repeat)}"
    return text


def step_text(step: CustomStep, lang: str = "ko") -> str:
    return f"{character_name(step.character_id, lang)} {step_label(step, lang)}"


def format_steps(steps: Sequence[CustomStep], lang: str = "ko") -> str:
    """Canonical text: one segment per step, the name on every segment, a line break when the member changes."""
    lines: list[list[str]] = []
    previous = None
    for step in steps:
        if previous is None or step.character_id != previous:
            lines.append([])
        lines[-1].append(step_text(step, lang))
        previous = step.character_id
    return "\n".join(" > ".join(line) for line in lines)


def step_to_json(step: CustomStep) -> dict:
    out: dict = {"c": int(step.character_id), "a": step.action}
    if step.pos is not None:
        out["p"] = int(step.pos)
    if int(step.repeat or 1) != 1:
        out["n"] = int(step.repeat)
    if step.seconds is not None:
        out["s"] = float(step.seconds)
    if step.raw is not None:
        out["k"] = [str(step.raw[0]), str(step.raw[1])]
    return out


def step_from_json(obj) -> CustomStep:
    """Raises ValueError for anything that is not a step (unknown code, bad number)."""
    if not isinstance(obj, dict):
        raise ValueError("step is not an object")
    action = obj.get("a")
    if action not in ALL_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    try:
        cid = int(obj["c"])
        pos = None if obj.get("p") is None else int(obj["p"])
        repeat = int(obj.get("n") or 1)
        seconds = None if obj.get("s") is None else float(obj["s"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:      # OverflowError: int(inf)
        raise ValueError(f"bad step {obj!r}") from exc
    raw = obj.get("k")
    if raw is not None:
        if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
            raise ValueError(f"bad raw key {raw!r}")
        raw = (str(raw[0]), str(raw[1]))
    if action == RAW_ACTION and raw is None:
        raise ValueError("raw step without a key")
    if action == "wait" and (seconds is None or not (0 < seconds <= MAX_WAIT_S)):
        raise ValueError(f"bad wait {seconds!r}")
    if not (1 <= repeat <= MAX_STEP_REPEAT) or (pos is not None and pos < 1):
        raise ValueError(f"bad repeat / position in {obj!r}")
    if action in ENTRY_ACTIONS or action == "wait":
        repeat = 1
    return CustomStep(cid, action, pos if action in SLOT_ACTIONS else None, repeat,
                      seconds if action == "wait" else None, raw if action == RAW_ACTION else None)


def steps_to_json(steps: Sequence[CustomStep]) -> list:
    return [step_to_json(s) for s in steps]


def steps_from_json(items) -> tuple[tuple, list]:
    """(steps, bad items): loading never raises; unknown entries are returned apart."""
    steps, bad = [], []
    for item in items if isinstance(items, (list, tuple)) else ():
        try:
            steps.append(step_from_json(item))
        except ValueError:
            bad.append(item)
    return tuple(steps), bad


# ── static checks shared by the parser and the builder ─────────────────────
def check_steps(steps: Sequence[CustomStep], team_ids: Sequence[int]) -> tuple[list, list]:
    """(errors, warnings) of a step list against a team: members, slots, positions, entries, length.
    ``ParseIssue.segment`` is the 1-based number of the step (0 for the whole list)."""
    data = _data()
    team = [int(c) for c in team_ids]
    errors: list[ParseIssue] = []
    warnings: list[ParseIssue] = []

    index = 0

    def issue(code, step, *args):
        start, end = step.span or (0, 0)
        return ParseIssue(code, tuple(args), start, end, index + 1)     # segment = the step's number here

    on_field = None
    total = 0
    for i, step in enumerate(steps):
        index = i
        cid = int(step.character_id)
        total += max(1, int(step.repeat or 1))
        if cid not in team:
            name = (data.PALETTE.get(cid) or {}).get("name_zh") or str(cid)
            errors.append(issue("not_in_team", step, name))
            on_field = cid
            continue
        if step.action in ENTRY_ACTIONS:
            if i > 0 and on_field == cid:
                errors.append(issue("entry_on_field", step, cid))
        else:
            if on_field is not None and on_field != cid:
                warnings.append(issue("implicit_swap", step, cid))
            if step.action in SLOT_ACTIONS:
                most = slot_max(cid, step.action)
                if most <= 0:
                    errors.append(issue("action_unavailable", step, cid, step.action))
                elif step.pos is not None and not (1 <= int(step.pos) <= most):
                    errors.append(issue("bad_position", step, cid, step.action, int(step.pos), most))
            elif step.action == RAW_ACTION:
                action = data.ACTIONS.get(tuple(step.raw or ()))
                if action is None or int(action["character_id"]) != cid:
                    errors.append(issue("bad_raw", step, "/".join(step.raw or ("", ""))))
            elif step.action == "wait":
                if step.seconds is None or not (0 < float(step.seconds) <= MAX_WAIT_S):
                    errors.append(issue("bad_wait", step, f"{step.seconds}"))
        if not (1 <= int(step.repeat or 1) <= MAX_STEP_REPEAT):
            errors.append(issue("bad_repeat", step, int(step.repeat or 0)))
        on_field = cid
    if len(steps) > MAX_STEPS:
        errors.append(ParseIssue("too_long", (MAX_STEPS,), 0, 0, 0))
    elif total > MAX_ACTIONS:
        errors.append(ParseIssue("too_long", (MAX_ACTIONS,), 0, 0, 0))
    return errors, warnings


def merge_steps(steps: Sequence[CustomStep]) -> tuple:
    """Consecutive steps of the same member and action (automatic position, no entry between) become one repeat."""
    out: list[CustomStep] = []
    for step in steps:
        prev = out[-1] if out else None
        if (prev is not None and prev.character_id == step.character_id and prev.action == step.action
                and step.action not in ENTRY_ACTIONS and step.action != "wait"
                and prev.pos is None and step.pos is None and prev.raw == step.raw
                and int(prev.repeat) + int(step.repeat) <= MAX_STEP_REPEAT):
            span = None
            if prev.span and step.span:
                span = (min(prev.span[0], step.span[0]), max(prev.span[1], step.span[1]))
            out[-1] = CustomStep(prev.character_id, prev.action, None, int(prev.repeat) + int(step.repeat),
                                 prev.seconds, prev.raw, span or prev.span or step.span)
        else:
            out.append(step)
    return tuple(out)


# ── parser ─────────────────────────────────────────────────────────────────
def _normalise(text: str) -> tuple[str, list[int], bool]:
    """NFKC text with quotes and (remarks) blanked, the offset of every character in the typed text, and whether
    those offsets are exact."""
    whole = unicodedata.normalize("NFKC", text)
    pieces = [unicodedata.normalize("NFKC", ch) for ch in text]
    exact = "".join(pieces) == whole
    if exact:
        chars, offsets = [], []
        for i, piece in enumerate(pieces):
            for ch in piece:
                chars.append(ch)
                offsets.append(i)
        norm = "".join(chars)
    else:                       # composing sequences (decomposed Hangul ...): spans become approximate
        norm = whole
        scale = len(text) / max(1, len(whole))
        offsets = [min(len(text) - 1, int(i * scale)) for i in range(len(whole))] if text else []
    norm = "".join(" " if ch in _QUOTES or ch == "\t" else ch for ch in norm)
    while True:
        blanked = _COMMENT.sub(lambda m: " " * len(m.group(0)), norm)
        if blanked == norm:
            break
        norm = blanked
    offsets.append(len(text))
    return norm, offsets, exact


def _close(word: str, candidates: Iterable[str], n: int = 3) -> tuple:
    """Close matches of a word (Hangul compared by jamo, so one wrong vowel still matches)."""
    def decomposed(s: str) -> str:
        return unicodedata.normalize("NFD", s.casefold())

    table: dict = {}
    for cand in candidates:
        table.setdefault(decomposed(cand), cand)
    hits = difflib.get_close_matches(decomposed(word), list(table), n=n, cutoff=0.5)
    return tuple(table[h] for h in hits)


_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WAIT_VALUE = re.compile(r"\s*(\d+(?:\.\d+)?|\.\d+)\s*(?:초|秒|sec(?![A-Za-z])|s(?![A-Za-z]))?", re.IGNORECASE)
_POSITION = re.compile(r"#\s*(\d+)")
_HIT = re.compile(r"(\d+)\s*타")
_REPEAT = re.compile(r"[xX×*]\s*(\d+)|(\d+)")
_COUNTER = re.compile(r"\s*(번|회|回|次|times(?![A-Za-z]))", re.IGNORECASE)
_RAW = re.compile(r"\[\s*([^\]/\s]+)\s*/\s*([^\]\s]+)\s*\]")
_WORD = re.compile(r"\S+")


def parse(text: str, team_ids: Sequence[int], lang: str = "ko") -> ParseResult:
    """Parse a typed sequence for a team.  Every error found is reported; offsets refer to the typed text."""
    data = _data()
    team = [int(c) for c in team_ids]
    norm, offsets, exact = _normalise(text or "")
    name_keys, name_re = _all_names()
    errors: list[ParseIssue] = []
    steps: list[CustomStep] = []

    def span(a: int, b: int) -> tuple[int, int]:
        a = max(0, min(a, len(norm)))
        b = max(a, min(b, len(norm)))
        start = offsets[a]                       # offsets has len(norm) + 1 entries
        return start, (offsets[b - 1] + 1 if b > a else start)

    def err(code: str, a: int, b: int, seg: int, *args) -> None:
        start, end = span(a, b)
        errors.append(ParseIssue(code, tuple(args), start, end, seg))

    def typed(a: int, b: int) -> str:
        """What the user wrote in a normalised range: messages echo it as typed ("ㅍ", not its NFKC form)."""
        if not exact:
            return norm[a:b]
        start, end = span(a, b)
        return (text or "")[start:end] or norm[a:b]

    def team_names() -> list[str]:
        """Member names for suggestions: the active language first, one spelling per name."""
        out: dict = {}
        for code in (lang,) + tuple(c for c in LANGS if c != lang):
            for cid in team:
                for name in (data.NAMES.get(cid) or {}).get(code) or ():
                    out.setdefault(_key(name), name)
        return list(out.values())

    # segments
    bounds, last = [], 0
    for m in _SEP.finditer(norm):
        bounds.append((last, m.start()))
        last = m.end()
    bounds.append((last, len(norm)))
    current: int | None = None          # member the next action belongs to
    current_ok = True                   # False: the named member is not in the team (its items are skipped)
    seg_no = 0
    for seg_start, seg_end in bounds:
        segment = norm[seg_start:seg_end]
        if not segment.strip():
            continue
        seg_no += 1
        i = seg_start
        seg_first = seg_start + len(segment) - len(segment.lstrip())    # offset of the segment's first item
        group_items = 0                 # items since the last character name (entries must come first)
        last_step: int | None = None    # index in steps of the item a position / repeat applies to
        named_here = False
        named_at = (seg_start, seg_start)
        while i < seg_end:
            if norm[i].isspace():
                i += 1
                continue
            at_start = i == seg_first
            after_space = at_start or norm[i - 1].isspace()
            rest_end = seg_end
            # a named action that starts with a digit ("38억 년의 신기루") is an action, not a hit / repeat number
            named_digit = False
            if norm[i].isdigit():
                digit_re = _aliases_for(current if current_ok else None)[1]
                named_digit = digit_re is not None and digit_re.match(norm, i, rest_end) is not None
            # 1. position / Korean hit form / repeat
            m = _POSITION.match(norm, i, rest_end)
            if m:
                n = int(m.group(1))
                target = steps[last_step] if last_step is not None else None
                if target is None or target.action not in SLOT_ACTIONS or target.pos is not None \
                        or int(target.repeat) != 1 or n < 1:
                    if current_ok:
                        cid_arg = target.character_id if target is not None else (current or 0)
                        act = target.action if target is not None else ""
                        err("bad_position", m.start(), m.end(), seg_no, cid_arg, act, n,
                            slot_max(cid_arg, act) if act in SLOT_ACTIONS else 0)
                else:
                    steps[last_step] = CustomStep(target.character_id, target.action, n, 1, None, None,
                                                  (target.span[0], span(m.start(), m.end())[1]))
                i = m.end()
                continue
            m = None if named_digit else _HIT.match(norm, i, rest_end)
            if m:
                target = steps[last_step] if last_step is not None else None
                if current is None:
                    err("no_character", m.start(), m.end(), seg_no)
                elif current_ok and target is not None and target.action == "basic" and target.pos is None \
                        and int(target.repeat) == 1:
                    count = int(m.group(1))     # "평타 3타": the chain up to hit 3, not hit 1 followed by hit 3
                    if 1 <= count <= MAX_STEP_REPEAT:
                        steps[last_step] = CustomStep(target.character_id, "basic", None, count, None, None,
                                                      (target.span[0], span(m.start(), m.end())[1]))
                        last_step = None
                    else:
                        err("bad_repeat", m.start(), m.end(), seg_no, count)
                elif current_ok:
                    steps.append(CustomStep(current, "basic", int(m.group(1)), 1, None, None, span(m.start(), m.end())))
                    last_step = len(steps) - 1
                    group_items += 1
                i = m.end()
                continue
            m = None if named_digit else _REPEAT.match(norm, i, rest_end)
            if m:
                n = int(m.group(1) or m.group(2))
                end = _counter_end(norm, m.end(), rest_end, _aliases_for(current if current_ok else None)[1])
                target = steps[last_step] if last_step is not None else None
                if target is None:
                    if current_ok:
                        if current is None:
                            err("no_character", m.start(), end, seg_no)
                        else:
                            err("unknown_action", m.start(), end, seg_no, current, typed(m.start(), end), (),
                                _available_tokens(current, lang))
                elif target.action in ENTRY_ACTIONS or target.action == "wait" or not (1 <= n <= MAX_STEP_REPEAT) \
                        or int(target.repeat) != 1:
                    if current_ok:
                        err("bad_repeat", m.start(), end, seg_no, n)
                else:
                    steps[last_step] = CustomStep(target.character_id, target.action, target.pos, n, target.seconds,
                                                  target.raw, (target.span[0], span(m.start(), end)[1]))
                    last_step = None            # one count per item
                i = end
                continue
            # 2. raw key
            if norm[i] == "[":
                m = _RAW.match(norm, i, rest_end)
                if m is None:
                    close = norm.find("]", i, rest_end)
                    end = close + 1 if close >= 0 else rest_end
                    if current_ok:
                        err("bad_raw", i, end, seg_no, norm[i:end].strip("[] "))
                    i = end
                    continue
                key = _raw_key(m.group(1), m.group(2))
                if current is None:
                    err("no_character", m.start(), m.end(), seg_no)
                elif current_ok:
                    steps.append(CustomStep(current, RAW_ACTION, None, 1, None, key, span(m.start(), m.end())))
                    last_step = len(steps) - 1
                    group_items += 1
                i = m.end()
                continue
            # 3. character name (segment start or after whitespace)
            if after_space and name_re is not None:
                m = name_re.match(norm, i, rest_end)
                if m:
                    cid = name_keys.get(_key(m.group(0)))
                    if cid is not None:
                        if named_here and group_items == 0 and current_ok and current is not None \
                                and current != cid:
                            _name_only(steps, current, span(*named_at))
                        current, current_ok = cid, cid in team
                        if not current_ok:
                            err("not_in_team", m.start(), m.end(), seg_no,
                                (data.PALETTE.get(cid) or {}).get("name_zh") or str(cid))
                        named_here, named_at = True, (m.start(), m.end())
                        group_items, last_step = 0, None
                        i = m.end()
                        continue
            alias_table, alias_re = _aliases_for(current if current_ok else None)
            word = _WORD.match(norm, i, rest_end)
            word_text = word.group(0) if word else norm[i:rest_end]
            # 4. abbreviated name (segment start only; an action alias always wins)
            if at_start:
                am = alias_re.match(norm, i, rest_end) if alias_re is not None else None
                if am is None and len(_key(word_text)) >= 2:
                    wanted = _key(word_text)
                    hits = sorted({cid for cid in team
                                   for shown in (data.NAMES.get(cid) or {}).values()
                                   for name in shown if _key(name).startswith(wanted)})
                    if len(hits) == 1:
                        current, current_ok = hits[0], True
                        named_here, named_at = True, (i, i + len(word_text))
                        group_items, last_step = 0, None
                        i += len(word_text)
                        continue
                    if len(hits) > 1:
                        err("ambiguous_character", i, i + len(word_text), seg_no, typed(i, i + len(word_text)),
                            tuple((data.PALETTE.get(c) or {}).get("name_zh") or str(c) for c in hits))
                        current, current_ok = hits[0], False
                        named_here, named_at = True, (i, i + len(word_text))
                        group_items, last_step = 0, None
                        i += len(word_text)
                        continue
            # 5. action alias (the rest of a glued word must scan too: "평티" is not 평 + 티)
            m = alias_re.match(norm, i, rest_end) if alias_re is not None else None
            if m and not _glued_ok(norm, m.end(), rest_end, alias_re, alias_table, _key(m.group(0))):
                glued = _WORD.match(norm, m.end(), rest_end)
                word_text = norm[i:glued.end()] if glued and glued.start() == m.end() else word_text
                m = None
            if m:
                action, pos = alias_table[_key(m.group(0))]
                end = m.end()
                if current is None:
                    err("no_character", m.start(), end, seg_no)
                    if action == "wait":
                        w = _WAIT_VALUE.match(norm, end, rest_end)
                        end = w.end() if w else end
                    i = end
                    continue
                if action in ENTRY_ACTIONS:
                    if group_items > 0:
                        if current_ok:
                            err("entry_not_first", m.start(), end, seg_no)
                    elif current_ok:
                        steps.append(CustomStep(current, action, None, 1, None, None, span(m.start(), end)))
                        last_step = len(steps) - 1
                    group_items += 1
                    i = end
                    continue
                if action == "wait":
                    w = _WAIT_VALUE.match(norm, end, rest_end)
                    seconds = float(w.group(1)) if w else None
                    stop = w.end() if w else end
                    if seconds is None or not (0 < seconds <= MAX_WAIT_S):
                        if current_ok:
                            err("bad_wait", m.start(), stop, seg_no, norm[m.start():stop].strip())
                    elif current_ok:
                        steps.append(CustomStep(current, "wait", None, 1, seconds, None, span(m.start(), stop)))
                    last_step = None
                    group_items += 1
                    i = stop
                    continue
                if current_ok:
                    steps.append(CustomStep(current, action, pos if action in SLOT_ACTIONS else None, 1, None, None,
                                            span(m.start(), end)))
                    last_step = len(steps) - 1
                group_items += 1
                i = end
                continue
            # 6. nothing matched: an unknown word
            stop = i + max(1, len(word_text))
            if at_start and not named_here and (current is None or _looks_like_name(word_text, team_names())):
                # neither a member name nor an action: the rest of the segment has no usable member
                err("unknown_character", i, stop, seg_no, typed(i, stop), _close(word_text, team_names()))
                current, current_ok, named_here = 0, False, True
                named_at = (i, stop)
            elif current is None:
                err("no_character", i, stop, seg_no)
            elif current_ok:
                # suggestions: the canonical tokens first, then every alias of the language and the named actions
                close = _close(word_text, [per[lang][0] for per in TOKEN_ALIASES.values() if per.get(lang)], n=2)
                if not close:
                    candidates = [a for per in TOKEN_ALIASES.values() for a in per.get(lang, ())]
                    candidates += list(data.NAMED.get(current, {}))
                    close = _close(word_text, candidates, n=2)
                err("unknown_action", i, stop, seg_no, current, typed(i, stop), close,
                    _available_tokens(current, lang))
            group_items += 1
            last_step = None
            i = stop
        if named_here and group_items == 0 and current_ok and current is not None:
            _name_only(steps, current, span(*named_at))

    merged = merge_steps(steps)
    if not errors:
        if not merged:
            errors.append(ParseIssue("empty", (), 0, len(text or ""), 0))
    static_errors, warnings = check_steps(merged, team)
    seen = {(e.code, e.start, e.end) for e in errors}
    for e in static_errors:
        if e.code == "not_in_team":
            continue                        # reported at the name already
        if (e.code, e.start, e.end) not in seen:
            errors.append(ParseIssue(e.code, e.args, e.start, e.end, _segment_of(e.start, bounds, norm, offsets)))
    errors.sort(key=lambda e: (e.start, e.end))
    return ParseResult(tuple(merged), tuple(errors), tuple(warnings))


def _glued_ok(norm: str, i: int, end: int, alias_re, alias_table: dict, first_key: str) -> bool:
    """True when the characters glued to an alias (up to the next whitespace) are items themselves."""
    wait = alias_table.get(first_key, ("", None))[0] == "wait"
    while i < end and not norm[i].isspace():
        if wait:
            m = _WAIT_VALUE.match(norm, i, end)
            wait = False
            if m and m.end() > i:
                i = m.end()
                continue
        m = _POSITION.match(norm, i, end) or _HIT.match(norm, i, end)
        if m is None:
            m = _REPEAT.match(norm, i, end)
            if m is not None:
                i = _counter_end(norm, m.end(), end, alias_re)
                continue
        if m is None and norm[i] == "[":
            m = _RAW.match(norm, i, end)
        if m is None and alias_re is not None:
            m = alias_re.match(norm, i, end)
            if m:
                wait = alias_table.get(_key(m.group(0)), ("", None))[0] == "wait"
        if m is None or m.end() <= i:
            return False
        i = m.end()
    return True


def _counter_end(norm: str, i: int, end: int, alias_re) -> int:
    """End of a counter word after a repeat number ("3번", "3회", "3 times"); ``i`` when there is none or when the
    word starts an action alias ("평타 3 회피" is a repeat followed by 회피)."""
    m = _COUNTER.match(norm, i, end)
    if m is None or (alias_re is not None and alias_re.match(norm, m.start(1), end) is not None):
        return i
    return m.end()


def _name_only(steps: list, character_id: int, where: tuple) -> None:
    """A segment that only names a member: a plain swap to it (nothing when it is already on the field)."""
    if steps and steps[-1].character_id != character_id:
        steps.append(CustomStep(character_id, "swap", None, 1, None, None, where))


def _looks_like_name(word: str, names: Iterable[str]) -> bool:
    """A word at a segment start that is close to a member name (and to no action alias) is a mistyped name."""
    if not _close(word, names, n=1):
        return False
    aliases = [a for per in TOKEN_ALIASES.values() for group in per.values() for a in group]
    return not _close(word, aliases, n=1)


def _raw_key(ability: str, selector: str) -> tuple:
    """The catalog spelling of a typed raw key (matching is case-insensitive)."""
    wanted = (ability.casefold(), selector.casefold())
    for key in _data().ACTIONS:
        if (key[0].casefold(), key[1].casefold()) == wanted:
            return tuple(key)
    return (ability, selector)


def _available_tokens(character_id: int | None, lang: str) -> tuple:
    if character_id is None:
        return ()
    return tuple(canonical_token(a, lang) for a in available_actions(character_id))


def _segment_of(start: int, bounds, norm: str, offsets) -> int:
    n = 0
    for a, b in bounds:
        if not norm[a:b].strip():
            continue
        n += 1
        lo = offsets[a] if a < len(offsets) else 0
        hi = offsets[b] if b < len(offsets) else offsets[-1]
        if lo <= start <= hi:
            return n
    return 0
