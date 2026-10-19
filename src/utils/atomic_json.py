# 원자적 JSON 파일 읽기/쓰기 (NTE Drive Calc Global 추가 모듈)
"""Atomic JSON file: temp file in the same folder -> fsync -> ``os.replace``.

Generalised from ``services/global_theme_settings_service.py`` (which stays untouched).  A missing, unreadable or
non-object file loads as the caller's default with a warning; it never raises on read.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.utils.logger import logger


class AtomicJsonFile:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self, default=None):
        if not self.path.is_file():
            return default
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            logger.warning(f"atomic_json: unreadable {self.path.name}: {exc!r}")
            return default
        if not isinstance(value, dict):
            logger.warning(f"atomic_json: {self.path.name} is not an object")
            return default
        return value

    def save(self, value: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
            temporary = Path(raw_path)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=1, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
