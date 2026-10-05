# 怪物与玩法页面的不可变浏览状态和正式记录键解析。
"""Qt-free browse models and typed-key helpers for the monster page."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote

from src.services.static_catalog_monster_service import CatalogEntry


PLAY_LABELS = {
    "official_illustrated": _L('大世界图鉴'),
    "feast": "争锋赏宴",
    "outer_realm": "轨外之境",
    "clone": _L('材料与养成副本'),
    "world_boss": "异象追猎",
    "high_risk": _L('具有正式怪物池的高危委托'),
}
PLAY_COPY = {
    "official_illustrated": _L('按地区浏览大世界敌人，查看弱点与战斗属性。'),
    "feast": _L('先选择当前或往期活动，再浏览当期挑战、难度与敌方画像。'),
    "outer_realm": _L('浏览全部正式配置；无排期配置仍按层与半场展示敌人。'),
    "clone": _L('材料、养成与活动副本，可按难度查看出场敌人。'),
    "world_boss": _L('浏览异象追猎目标和不同等级下的战斗属性。'),
    "high_risk": _L('仅收录各难度已有明确出场敌人的高危委托。'),
}


@dataclass(frozen=True, slots=True)
class BrowseCard:
    title: str
    subtitle: str
    badge: str
    icon: Path | None
    action: Callable[[], None] | None
    formal_id: str = ""
    unavailable: bool = False
    category: str = ""
    difficulty: str = ""
    region: str = ""
    period: str = ""


@dataclass(frozen=True, slots=True)
class BrowseSection:
    title: str
    note: str
    cards: tuple[BrowseCard, ...]
    initial_limit: int = 0


@dataclass(frozen=True, slots=True)
class BrowseState:
    title: str
    subtitle: str
    sections: tuple[BrowseSection, ...]


def group_entries(
    entries: Iterable[CatalogEntry], key: Callable[[CatalogEntry], object],
) -> dict[str, tuple[CatalogEntry, ...]]:
    rows: dict[str, list[CatalogEntry]] = defaultdict(list)
    for entry in entries:
        rows[str(key(entry))].append(entry)
    return {name: tuple(values) for name, values in rows.items()}


def key_parts(key: str) -> tuple[str, ...]:
    return tuple(unquote(part) for part in key.split("|"))


def profile_parts(key: str) -> tuple[str, str] | None:
    parts = key_parts(key)
    return (
        (parts[1], parts[2])
        if len(parts) == 3 and parts[0] == "profile_monster"
        else None
    )


def object_name(path: str) -> str:
    name = str(path).rsplit(".", 1)[-1]
    return name[:-2] if name.endswith("_C") else name


def period_label(config_id: str) -> str:
    ordinal = str(config_id).rsplit("_", 1)[-1]
    return _LF('第 {0} 期').format((ordinal)) if ordinal.isdigit() else _L('正式期数')


def home_badge(mode: str, entries: Iterable[CatalogEntry]) -> str:
    """Summarize one home category without duplicating records in the view."""

    if mode == "outer_realm":
        count = len({entry.primary_id for entry in entries})
        return _LF('{0} 期正式配置').format((count))
    labels = {
        "official_illustrated": _L('名大世界敌人'),
        "feast": _L('名挑战对象'),
        "clone": _L('个副本'),
        "world_boss": _L('名追猎目标'),
        "high_risk": _L('项高危委托'),
    }
    return f"{len({entry.primary_id for entry in entries})} {labels[mode]}"
