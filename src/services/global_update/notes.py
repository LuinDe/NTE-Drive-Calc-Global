# 릴리스 노트를 사용자 언어 구간으로 추려 Qt Markdown으로 정리 (순수 모듈)
"""Release notes in the user's language (design_final §4.3, review r5 M5 / F2 / L11).

Global release bodies carry one ``## <language>`` H2 section per language after a short preamble.  Only the
requested language's section is shown, without its own heading (fallback: the English section; the whole body only
when no language section matches).  GitHub alert markers become plain bold labels, images are reduced to their alt
text (the notes view never loads any resource: no local, network or ``data:`` image), and upstream's list / quote
normalisation (``normalize_notes_markdown``, re-homed from the deleted ``features/settings/updates.py``) is applied.
Raw HTML is not escaped here: the dialog renders with ``QTextDocument.MarkdownNoHTML`` (HTML stays literal text,
``<`` inside code stays ``<``).
"""
from __future__ import annotations

import re

from src.i18n_runtime import L as _L

from src.app.global_release import RELEASE_BODY_MAX

SECTION_NAMES = {
    "ko": ("한국어", "korean"),
    "en": ("english",),
    "ja": ("日本語", "japanese"),
    "zh": ("中文", "简体中文", "中文（简体）", "中文(简体)", "chinese"),
}
_ALERT = re.compile(r"^(\s*>\s*)\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", re.IGNORECASE)
_H2 = re.compile(r"^##\s+(.+?)\s*$")
# ![alt](target "title") and ![alt][ref] / ![alt][] -> alt text (F2: no image is ever loaded)
_IMAGE_INLINE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_IMAGE_REFERENCE = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")


def normalize_notes_markdown(message: object) -> str:
    """Normalize common release-note shorthand into Qt-compatible Markdown (upstream helper, verbatim)."""

    text = str(message or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return _L('此版本没有填写更新说明。')
    normalized_lines: list[str] = []
    lines = text.split("\n")
    for index, line in enumerate(lines):
        # GitHub users often write ``1.修复内容``.  GitHub renders it
        # leniently, while Qt requires a space after the marker to create a
        # separate list item instead of one long paragraph.
        line = re.sub(r"^(\s*\d+)\.(?=\S)", r"\1. ", line)
        line = re.sub(r"^(\s*[-*+])(?=\S)", r"\1 ", line)
        # Qt merges adjacent quote lines into one paragraph.  Keep each
        # support/download call-to-action visibly separate.
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if line.lstrip().startswith(">") and next_line.lstrip().startswith(">"):
            line += "  "
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def split_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """``(preamble, [(h2 title, section text WITHOUT its heading line)])`` split on ``## `` headings outside code
    fences."""
    lines = body.split("\n")
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _H2.match(line)
        if match is not None:
            sections.append((match.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble), [(title, "\n".join(text)) for title, text in sections]


def _section_for(sections: list[tuple[str, str]], lang: str) -> str | None:
    wanted = tuple(name.casefold() for name in SECTION_NAMES.get(lang, ()))
    for title, text in sections:
        if title.strip().casefold() in wanted:
            return text
    return None


def sanitize_markdown(text: str) -> str:
    text = _IMAGE_INLINE.sub(lambda m: m.group(1), text)
    text = _IMAGE_REFERENCE.sub(lambda m: m.group(1), text)
    return "\n".join(_ALERT.sub(lambda m: f"{m.group(1)}**{m.group(2).upper()}:**", line) for line in text.split("\n"))


def notes_for_language(body: object, lang: str) -> str:
    """Markdown for ``QTextBrowser.setMarkdown(..., MarkdownDialectGitHub | MarkdownNoHTML)`` in ``lang``; never
    empty."""
    text = str(body or "")
    if len(text.encode("utf-8")) > RELEASE_BODY_MAX:
        text = text.encode("utf-8")[:RELEASE_BODY_MAX].decode("utf-8", "ignore")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    _preamble, sections = split_sections(text)
    chosen = _section_for(sections, lang)
    if chosen is None and lang != "en":
        chosen = _section_for(sections, "en")
    result = text if chosen is None else chosen
    result = sanitize_markdown(result).strip()
    if not result:
        return _L('此版本没有填写更新说明。')
    return normalize_notes_markdown(result)


def unverified_notes_text() -> str:
    """Shown instead of a release body that the signed manifest does not cover (review r5 F1)."""
    return _L('无法验证此版本的更新说明，请在发布页查看。')
