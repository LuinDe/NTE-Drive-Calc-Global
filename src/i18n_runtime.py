# 언어 전환 런타임 (한글패치 추가 모듈)
"""Language runtime for the localisation patch.

Source literals are wrapped as ``_L('原文')`` / ``_LF('模板{0}').format(...)`` at build time;
this module resolves them against the active language table.  Chinese is the identity
language (no table), Korean ships in ``src.i18n_data_ko``, and further languages are plain
data modules (``src.i18n_data_en`` / ``src.i18n_data_ja``) with the same S/T shape.

Initialisation is lazy: the first ``L()`` call (which happens during module imports) loads
the persisted choice, so import order never matters.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_LANGUAGE = "ko"
LANGUAGES = ("zh", "ko", "ja", "en")
_DATA_MODULES = {"ko": "src.i18n_data_ko", "en": "src.i18n_data_en", "ja": "src.i18n_data_ja"}

_lang: str | None = None
_S: dict = {}
_T: dict = {}
_listeners: list = []


def _config_path() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "_internal" / "config")
    here = Path(__file__).resolve()
    candidates.append(here.parent.parent / "config")          # source runs: <root>/config
    candidates.append(here.parent.parent / "_internal" / "config")
    for c in candidates:
        if c.is_dir():
            return c / "i18n_language.json"
    return None


def _load_tables(code: str) -> tuple[dict, dict]:
    mod_name = _DATA_MODULES.get(code)
    if not mod_name:
        return {}, {}
    try:
        __import__(mod_name)
        mod = sys.modules[mod_name]
        return getattr(mod, "S", {}), getattr(mod, "T", {})
    except Exception:
        return {}, {}


def _ensure() -> None:
    global _lang, _S, _T
    if _lang is not None:
        return
    code = os.environ.get("NTE_KO_PATCH_LANG", "")   # smoke-test override
    if code not in LANGUAGES:
        code = ""
    if not code:
        p = _config_path()
        try:
            if p is not None and p.is_file():
                code = json.loads(p.read_text(encoding="utf-8")).get("language", "")
        except Exception:
            code = ""
    if code not in LANGUAGES:
        code = DEFAULT_LANGUAGE
    _lang = code
    _S, _T = _load_tables(code)


class _Concat:
    """`+` between provenance strings keeps the pieces, so the result can be re-rendered.

    Python calls a str subclass's __radd__ before str.__add__, so both "prefix" + L(...) and
    L(...) + "suffix" land here.

    The provenance strings are immutable, so copy/deepcopy return the object itself (the default
    deepcopy would call __new__ without the provenance arguments and crash - that broke every
    deepcopy of editor data holding _L titles).  __reduce__ keeps them picklable."""

    __slots__ = ()

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        return (_rebuild, (type(self).__name__, str(self), _state(self)))

    def __add__(self, other):
        if isinstance(other, str):
            return CStr(str.__add__(str(self), str(other)), (self, other))
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return CStr(str.__add__(str(other), str(self)), (other, self))
        return NotImplemented


class LStr(_Concat, str):
    """A translated string that remembers its Chinese source key (live language switching)."""

    __slots__ = ("_zh",)

    def __new__(cls, value: str, zh: str):
        s = super().__new__(cls, value)
        s._zh = zh
        return s


class CStr(_Concat, str):
    """Concatenation of pieces, some of which carry provenance."""

    __slots__ = ("_parts",)

    def __new__(cls, value: str, parts: tuple):
        s = super().__new__(cls, value)
        s._parts = parts
        return s


class FVal(_Concat, str):
    """A formatted template result; keeps template key and arguments for re-rendering."""

    __slots__ = ("_zh", "_args", "_kwargs")

    def __new__(cls, value: str, zh: str, args: tuple, kwargs: dict):
        s = super().__new__(cls, value)
        s._zh = zh
        s._args = args
        s._kwargs = kwargs
        return s


class TStr(str):
    """A translated template; .format() yields an FVal carrying provenance."""

    __slots__ = ("_zh",)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __reduce__(self):
        return (_rebuild, ("TStr", str(self), (self._zh,)))

    def __new__(cls, value: str, zh: str):
        s = super().__new__(cls, value)
        s._zh = zh
        return s

    def format(self, *args, **kwargs):  # noqa: A003 - mirrors str.format
        return FVal(str.format(self, *args, **kwargs), self._zh, args, kwargs)


def _state(obj) -> tuple:
    if isinstance(obj, LStr):
        return (obj._zh,)
    if isinstance(obj, CStr):
        return (obj._parts,)
    if isinstance(obj, FVal):
        return (obj._zh, obj._args, obj._kwargs)
    return ()


def _rebuild(kind: str, value: str, state: tuple):
    cls = {"LStr": LStr, "CStr": CStr, "FVal": FVal, "TStr": TStr}[kind]
    return cls(value, *state)


def L(key: str) -> str:
    """Translate one plain source string (identity when no table entry exists)."""
    _ensure()
    return LStr(_S.get(key, key), key)


def LF(key: str) -> str:
    """Translate one f-string template ({n}-slot form); caller formats the result."""
    _ensure()
    return TStr(_T.get(key, key), key)


def has_provenance(text) -> bool:
    return isinstance(text, (LStr, FVal, CStr))


def is_translated(text) -> bool:
    """True when a provenance string (or any provenance piece of it) has an active-language entry."""
    if isinstance(text, CStr):
        return any(is_translated(p) for p in text._parts)
    zh = getattr(text, "_zh", None)
    if zh is None:
        return False
    _ensure()
    return zh in (_T if getattr(text, "_args", None) is not None else _S)


def resolve(text, value_map=None):
    """Re-render a provenance-carrying string in the CURRENT language (else return as-is).

    Recursive: format arguments and concatenation pieces that carry provenance re-render too.
    ``value_map`` (the display layer's tr) is applied to plain data pieces - format arguments and
    concatenated plain strings such as a character name - so they follow the language as well."""
    def piece(p):
        if has_provenance(p):
            return resolve(p, value_map)
        if value_map is not None and isinstance(p, str):
            return value_map(p)
        return p

    if isinstance(text, CStr):
        parts = tuple(piece(p) for p in text._parts)
        return CStr("".join(str(p) for p in parts), parts)
    zh = getattr(text, "_zh", None)
    if zh is None:
        return text
    args = getattr(text, "_args", None)
    if args is None:
        _ensure()
        return LStr(_S.get(zh, zh), zh)
    kwargs = getattr(text, "_kwargs", {}) or {}
    try:
        return LF(zh).format(*(piece(a) for a in args), **{k: piece(v) for k, v in kwargs.items()})
    except Exception:
        return text


def get_language() -> str:
    _ensure()
    return _lang or DEFAULT_LANGUAGE


def available_languages() -> tuple[str, ...]:
    """zh is always available; others need their data module."""
    import importlib.util

    out = ["zh"]
    for code in ("ko", "ja", "en"):
        try:
            if importlib.util.find_spec(_DATA_MODULES[code]) is not None:
                out.append(code)
        except Exception:
            pass
    return tuple(out)


def set_language(code: str) -> bool:
    """Persist and activate ``code``; newly created strings use it immediately."""
    global _lang, _S, _T
    if code not in LANGUAGES:
        return False
    _ensure()
    _lang = code
    _S, _T = _load_tables(code)
    p = _config_path()
    try:
        if p is not None:
            p.write_text(json.dumps({"language": code}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    for cb in list(_listeners):
        try:
            cb(code)
        except Exception:
            pass
    return True


def add_listener(cb) -> None:
    """cb(code) runs after every language change (display layer refresh hooks in here)."""
    if cb not in _listeners:
        _listeners.append(cb)


def restart_app() -> None:
    """Relaunch the application so build-time wrapped strings re-evaluate."""
    try:
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QApplication

        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, [])
        else:
            QProcess.startDetached(sys.executable, list(sys.argv))
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            raise SystemExit(0)
    except Exception:
        os._exit(0)
