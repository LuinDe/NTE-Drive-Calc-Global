# 富文本提示：按原样显示（显示层的提示钩子不再二次翻译），并让 Qt 自动换行。
"""Rich-text tooltips shown exactly as given (Global).

``shown_as_is(text)``: the display layer's tooltip hook translates any tooltip text with Chinese characters again,
which would double a Korean text's kept term ("지식(蜘识)" -> "지식(지식(蜘识))"), and Qt never wraps a plain-text
tooltip (one line as wide as the text).  The text is HTML-escaped, line breaks become <br>, Han characters become
character references and the whole is wrapped in <qt>: Qt renders it as word-wrapped rich text with the original
characters.  ``translated_as_is(text)`` first applies the display layer's ``tr()`` once (what the hook would have
done to the plain text), for texts that still carry game names as Chinese pieces.
"""
from __future__ import annotations

import html
import re

_HAN = re.compile("[\u4e00-\u9fff]")          # what the display layer's term pass looks for


def shown_as_is(text) -> str:
    out = html.escape(str(text), quote=False).replace("\n", "<br>")
    return "<qt>" + _HAN.sub(lambda m: f"&#{ord(m.group(0))};", out) + "</qt>"


def translated_as_is(text) -> str:
    """``tr()`` of the display layer once, then ``shown_as_is`` ("" stays "")."""
    if not text:
        return ""
    try:
        from src.i18n_display import tr

        text = tr(text)
    except Exception:  # noqa: BLE001 - no display layer (tests, zh): the text as it is
        pass
    return shown_as_is(text)
