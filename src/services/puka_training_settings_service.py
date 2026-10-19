# 管理当前账号的噗卡特训等级，并与家具加成合并为账号级固定属性层。
"""Account-owned Puka Boot Camp (噗卡特训) level shared by every official-role calculation.

The level is one account-wide integer (0..``MAX_LEVEL``) persisted in the account's setting-copy table under
``PUKA_TRAINING_SETTING_KEY``; the furniture bonus (``world_bonus_settings_service``) stays byte-for-byte the
same.  ``account_bonus_property_stats`` is the single choke point that merges both account layers for the
attribute service; at level 0 it returns exactly the furniture values, so an account that never entered a
level computes exactly as before this feature.
"""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import math

from src.services.puka_training_data import (
    COLUMNS,
    DATA_VERSION,
    MAX_LEVEL,
    cumulative_display,
    cumulative_property_stats,
)
from src.services.world_bonus_settings_service import world_bonus_property_stats
from src.storage.sqlite.user_data_dao import UserDataDao
from src.utils.logger import logger


PUKA_TRAINING_SETTING_KEY = "puka_training"
PUKA_TRAINING_OPTIONS_SETTING_KEY = "puka_training_options"
DEFAULT_LEVEL = 0        # account default: the user enters the level (max level needs 11,000,000 Fons)
TEMPLATE_LEVEL = 0       # graduation benchmark / empty-account (efficiency table) template level by default
# decision U1 (2026-10-14): the graduation template is shown either without the training (Lv 0, default) or at
# max level (Lv 20) - one checkbox per account, nothing in between.
TEMPLATE_LEVELS = (TEMPLATE_LEVEL, MAX_LEVEL)


def _coerce_level(raw: Any) -> int:
    """Stored level -> int; ``None``, bool, text, negative or fractional values are corrupt."""
    if isinstance(raw, bool) or raw is None:
        raise ValueError(_LF('噗卡特训等级必须是 0 到 {0} 之间的整数。').format(MAX_LEVEL))
    if isinstance(raw, float):
        if not raw.is_integer():
            raise ValueError(_LF('噗卡特训等级必须是 0 到 {0} 之间的整数。').format(MAX_LEVEL))
        raw = int(raw)
    if not isinstance(raw, int) or raw < 0:
        raise ValueError(_LF('噗卡特训等级必须是 0 到 {0} 之间的整数。').format(MAX_LEVEL))
    return int(raw)


@dataclass(frozen=True)
class PukaTrainingSettings:
    """Current account's Puka Boot Camp level."""

    level: int = DEFAULT_LEVEL

    def validate(self) -> None:
        if type(self.level) is not int or not 0 <= self.level <= MAX_LEVEL:
            raise ValueError(_LF('噗卡特训等级必须是 0 到 {0} 之间的整数。').format(MAX_LEVEL))

    def to_payload(self) -> dict[str, Any]:
        self.validate()
        return {"level": int(self.level), "data_version": DATA_VERSION}

    @classmethod
    def from_payload(cls, value: Mapping[str, Any] | None) -> "PukaTrainingSettings":
        """Missing payload or missing ``level`` key -> default; a level above the table is clamped with a
        warning (a value saved by a newer table); anything else malformed raises ``ValueError``."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValueError(_LF('噗卡特训等级必须是 0 到 {0} 之间的整数。').format(MAX_LEVEL))
        if "level" not in value:
            return cls()
        level = _coerce_level(value.get("level"))
        if level > MAX_LEVEL:
            logger.warning(
                "puka_training level {} above the table maximum {}; clamped", level, MAX_LEVEL,   # loguru {} style
            )
            level = MAX_LEVEL
        settings = cls(level=level)
        settings.validate()
        return settings

    def display_values(self) -> tuple:
        return cumulative_display(self.level)


def account_puka_training(payload: Any) -> PukaTrainingSettings:
    """The account's stored setting, tolerant: a corrupt row (hand-edited database, unexpected type) is reported
    and read as level 0 so that the character page, battle capture and team simulation keep working; saving the
    level on the character page overwrites the bad row.  ``from_payload`` itself stays strict."""

    try:
        return PukaTrainingSettings.from_payload(payload)
    except ValueError:
        logger.warning("account puka_training payload {!r} is invalid; treated as level 0", payload)
        return PukaTrainingSettings()


def puka_training_level(value: Mapping[str, Any] | PukaTrainingSettings | int | None) -> int:
    if isinstance(value, PukaTrainingSettings):
        return int(value.level)
    if value is None:
        return DEFAULT_LEVEL
    if isinstance(value, Mapping):
        return int(PukaTrainingSettings.from_payload(value).level)
    settings = PukaTrainingSettings(level=_coerce_level(value))
    settings.validate()
    return int(settings.level)


def frozen_puka_training_level(payload: Any) -> int:
    """Level recorded in a frozen battle build (``build["puka_training"]``).

    A missing or non-mapping payload is level 0 (team-simulation builds, pre-feature records); a corrupt
    value is reported and treated as level 0 instead of blocking the whole record.
    """

    if not isinstance(payload, Mapping):
        return 0
    try:
        return int(PukaTrainingSettings.from_payload(payload).level)
    except ValueError:
        logger.warning("frozen puka_training payload {!r} is invalid; treated as level 0", dict(payload))
        return 0


def _frozen_values(value: Any) -> dict[str, float] | None:
    """Validated ``values`` of a frozen payload (the cumulative stats recorded when a battle was captured), or
    ``None`` when the payload carries none (account setting, pre-feature record) or they are malformed (logged;
    the level table is used instead).  Keys must be training property ids, amounts finite non-negative numbers."""

    if not isinstance(value, Mapping) or "values" not in value:
        return None
    raw = value.get("values")
    if isinstance(raw, Mapping) and all(
        str(key) in COLUMNS and not isinstance(amount, bool) and isinstance(amount, (int, float))
        and math.isfinite(float(amount)) and float(amount) >= 0.0
        for key, amount in raw.items()
    ):
        return {str(key): float(amount) for key, amount in raw.items() if float(amount) != 0.0}
    logger.warning("frozen puka_training values {!r} are invalid; the level table is used", raw)
    return None


def puka_training_property_stats(
    value: Mapping[str, Any] | PukaTrainingSettings | int | None,
) -> dict[str, float]:
    """Formal property values of the training level: ``{}`` at level 0, otherwise only the non-zero keys.

    The empty dict at level 0 is what keeps every frozen row and every panel byte-identical to the
    pre-feature calculator for accounts without a level.  A frozen payload that recorded its cumulative
    ``values`` (battle capture) is restored from them, so a later correction of the level table never changes
    what an old battle record froze.
    """

    level = puka_training_level(value)
    if level <= 0:
        return {}
    frozen = _frozen_values(value)
    if frozen is not None:
        return frozen
    return {
        property_id: float(amount)
        for property_id, amount in cumulative_property_stats(level).items()
        if amount != 0.0
    }


def frozen_capture_payload(settings: PukaTrainingSettings, source: str) -> dict[str, Any]:
    """What a battle capture freezes (``calc_capture_context["puka_training"]``): the level, the table version,
    the cumulative values of that level (``{}`` at level 0) and where the level came from."""

    payload = settings.to_payload()
    payload["values"] = puka_training_property_stats(settings)
    payload["source"] = str(source)
    return payload


def frozen_puka_training_detail(payload: Any) -> dict[str, Any]:
    """Detail payload (``detail["puka_training"]``) for a frozen battle build: the recorded level (corrupt or
    missing -> 0, see ``frozen_puka_training_level``) plus the recorded values when they are valid."""

    level = frozen_puka_training_level(payload)
    detail: dict[str, Any] = {"level": level}
    if level > 0:
        values = _frozen_values(payload)
        if values is not None:
            detail["values"] = values
    return detail


@dataclass(frozen=True)
class PukaTrainingOptions:
    """The account's two Puka Boot Camp switches (setting copy ``PUKA_TRAINING_OPTIONS_SETTING_KEY``).

    ``native_overrides`` (decision U2, default on): when the native core rebuilds a battle report's panel (an
    active modified copy, the comparison candidate of the marginal page, "compare with my build"), the training
    stats it cannot rebuild itself (DEF/HP/CRIT Rate/Cycle/Break) are passed through the manual-adjustment channel.
    ``template_max`` (decision U1, default off): the graduation template (efficiency table, graduation rate) counts
    the training at max level (Lv 20) instead of Lv 0.
    """

    native_overrides: bool = True
    template_max: bool = False

    def template_level(self) -> int:
        return MAX_LEVEL if self.template_max else TEMPLATE_LEVEL

    def to_payload(self) -> dict[str, Any]:
        return {"native_overrides": bool(self.native_overrides), "template_max": bool(self.template_max)}

    @classmethod
    def from_payload(cls, value: Any) -> "PukaTrainingOptions":
        """Tolerant: a missing row is the default; a malformed row or key is reported and read as the default."""
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            logger.warning("puka_training_options payload {!r} is invalid; defaults used", value)
            return cls()
        defaults = cls()
        fields: dict[str, bool] = {}
        for key in ("native_overrides", "template_max"):
            raw = value.get(key, getattr(defaults, key))
            if not isinstance(raw, bool):
                logger.warning("puka_training_options {} = {!r} is invalid; default used", key, raw)
                raw = getattr(defaults, key)
            fields[key] = raw
        return cls(**fields)


def account_puka_options(payload: Any) -> PukaTrainingOptions:
    return PukaTrainingOptions.from_payload(payload)


def graduation_template_level(detail: Mapping[str, Any]) -> int:
    """Training level of the graduation template for this role detail (``detail["puka_template_level"]``, set by
    the role-page loader from the account's U1 checkbox): only 0 or ``MAX_LEVEL``; anything else is 0."""

    raw = detail.get("puka_template_level", TEMPLATE_LEVEL) if isinstance(detail, Mapping) else TEMPLATE_LEVEL
    return int(raw) if (type(raw) is int and raw in TEMPLATE_LEVELS) else TEMPLATE_LEVEL


def load_account_puka_options(user_database_path: str | Path | None) -> PukaTrainingOptions:
    """The options of an account database, read through a read-only connection (pages and background loaders call
    this often; it never migrates or writes).  A missing / unreadable database or table gives the defaults."""

    import json
    import sqlite3

    try:
        if user_database_path is None or not Path(user_database_path).is_file():
            return PukaTrainingOptions()
        uri = f"{Path(user_database_path).resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            row = connection.execute(
                "SELECT value_json FROM application_setting_copy WHERE setting_key = ?",
                (PUKA_TRAINING_OPTIONS_SETTING_KEY,),
            ).fetchone()
        finally:
            connection.close()
        return account_puka_options(None if row is None else json.loads(row[0]))
    except Exception as exc:  # noqa: BLE001 - an option never blocks a page
        logger.warning("puka_training_options not readable ({}); defaults used", exc)
        return PukaTrainingOptions()


def template_account_database(folder: str | Path, level: int) -> Path:
    """An empty account database in ``folder`` whose Puka Boot Camp level is ``level`` (graduation template runs
    of the efficiency table at ``MAX_LEVEL``).  The caller owns and removes the folder."""

    path = Path(folder) / "user_data.sqlite3"
    with UserDataDao(path, account_id="arc_efficiency", account_name="arc_efficiency") as dao:
        settings = PukaTrainingSettings(level=int(level))
        if settings != PukaTrainingSettings():
            dao.replace_application_setting_copy(PUKA_TRAINING_SETTING_KEY, settings.to_payload())
    return path


def account_bonus_property_stats(detail: Mapping[str, Any]) -> dict[str, float]:
    """THE choke point: furniture bonus + Puka Boot Camp, summed per property id."""

    merged = dict(world_bonus_property_stats(detail.get("world_bonus")))
    for property_id, amount in puka_training_property_stats(detail.get("puka_training")).items():
        merged[property_id] = merged.get(property_id, 0.0) + float(amount)
    return merged


class PukaTrainingSettingsService:
    """Persist the training level in the active account's setting-copy table."""

    def __init__(self, user_database_path: str | Path) -> None:
        self.user_database_path = Path(user_database_path).expanduser().resolve()

    def load(self) -> PukaTrainingSettings:
        with UserDataDao(self.user_database_path) as dao:
            payload = dao.list_application_setting_copies().get(PUKA_TRAINING_SETTING_KEY)
        return account_puka_training(payload)

    def save(self, settings: PukaTrainingSettings) -> PukaTrainingSettings:
        payload = settings.to_payload()
        with UserDataDao(self.user_database_path) as dao:
            if settings == PukaTrainingSettings():
                dao.delete_application_setting_copy(PUKA_TRAINING_SETTING_KEY)
            else:
                dao.replace_application_setting_copy(PUKA_TRAINING_SETTING_KEY, payload)
        return settings

    def load_options(self) -> PukaTrainingOptions:
        with UserDataDao(self.user_database_path) as dao:
            payload = dao.list_application_setting_copies().get(PUKA_TRAINING_OPTIONS_SETTING_KEY)
        return account_puka_options(payload)

    def save_options(self, options: PukaTrainingOptions) -> PukaTrainingOptions:
        """The default options delete the row (an account that never touched a switch keeps no row)."""
        with UserDataDao(self.user_database_path) as dao:
            if options == PukaTrainingOptions():
                dao.delete_application_setting_copy(PUKA_TRAINING_OPTIONS_SETTING_KEY)
            else:
                dao.replace_application_setting_copy(PUKA_TRAINING_OPTIONS_SETTING_KEY, options.to_payload())
        return options


__all__ = [
    "DEFAULT_LEVEL",
    "PUKA_TRAINING_OPTIONS_SETTING_KEY",
    "PUKA_TRAINING_SETTING_KEY",
    "TEMPLATE_LEVEL",
    "TEMPLATE_LEVELS",
    "PukaTrainingOptions",
    "PukaTrainingSettings",
    "PukaTrainingSettingsService",
    "account_bonus_property_stats",
    "account_puka_options",
    "account_puka_training",
    "graduation_template_level",
    "load_account_puka_options",
    "template_account_database",
    "frozen_capture_payload",
    "frozen_puka_training_detail",
    "frozen_puka_training_level",
    "puka_training_level",
    "puka_training_property_stats",
]
