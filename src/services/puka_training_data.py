# 噗卡特训：按等级累计的账号固定属性表（由 work_g231/scripts/gen_puka_training_data.py 生成，勿手改）
# GENERATED FILE - DO NOT EDIT.  Regenerate with scratchpad/v230/work_g231/scripts/gen_puka_training_data.py --write
# inputs: tables/puka_training_levels.json (generated 2026-10-11); integers only, crit rate / crit damage in permille
"""Puka Boot Camp (噗卡特训) level table (generated, do not edit).

One account-wide level 0..MAX_LEVEL; every deployed character receives the cumulative flat values.
LEVELS[i] = (level, required_plan_level, cost_fons, delta_units) with delta_units ordered like COLUMNS;
the two PERMILLE_COLUMNS are stored x1000 (0.1 % -> 1) so that cumulative sums are exact integers and
``cumulative_property_stats`` divides once (25 / 1000.0 == 0.025).  TOTALS is asserted at import.
"""
from __future__ import annotations

FORMAT = 1
GAME_VERSION = '1.4'
DATA_VERSION = '2026-10-11'
MAX_LEVEL = 20
UNLOCK_PLAN_LEVEL = 7          # training level N needs plan level 2N+5
TOTAL_COST_FONS = 11_000_000
COLUMNS = ('AtkAdd', 'DefAdd', 'HPMaxAdd', 'CritBase', 'CritDamageBase', 'MagBase', 'UnbalIntensityBase')
PERMILLE_COLUMNS = frozenset({"CritBase", "CritDamageBase"})
LEVELS = (
    (1, 7, 100_000, (2, 0, 0, 1, 0, 0, 0)),
    (2, 9, 100_000, (0, 2, 0, 0, 2, 0, 0)),
    (3, 11, 100_000, (0, 0, 20, 0, 0, 1, 0)),
    (4, 13, 100_000, (0, 0, 0, 1, 0, 0, 1)),
    (5, 15, 600_000, (5, 5, 80, 5, 10, 2, 2)),
    (6, 17, 200_000, (0, 2, 0, 0, 0, 1, 0)),
    (7, 19, 200_000, (0, 0, 20, 0, 0, 0, 1)),
    (8, 21, 200_000, (0, 2, 0, 1, 0, 0, 0)),
    (9, 23, 200_000, (2, 0, 0, 0, 2, 0, 0)),
    (10, 25, 1_200_000, (5, 5, 80, 5, 10, 2, 2)),
    (11, 27, 300_000, (0, 0, 20, 0, 0, 0, 1)),
    (12, 29, 300_000, (0, 0, 20, 1, 0, 0, 0)),
    (13, 31, 300_000, (2, 0, 0, 0, 2, 0, 0)),
    (14, 33, 300_000, (0, 2, 0, 0, 0, 1, 0)),
    (15, 35, 1_800_000, (5, 5, 80, 5, 10, 2, 2)),
    (16, 37, 500_000, (2, 0, 0, 0, 2, 0, 0)),
    (17, 39, 500_000, (0, 2, 0, 0, 2, 0, 0)),
    (18, 41, 500_000, (0, 0, 20, 0, 0, 1, 0)),
    (19, 43, 500_000, (0, 0, 0, 1, 0, 0, 1)),
    (20, 45, 3_000_000, (5, 5, 80, 5, 10, 2, 2)),
)
TOTALS = (28, 30, 420, 25, 50, 12, 12)
NAMES = {
    'zh': '噗卡特训',
    'ko': '푸카 특훈',
    'en': 'Puka Boot Camp',
    'ja': 'プカ特訓',
}
SOURCES = (   # provenance only
    ('S1', 'kamigame', 'https://kamigame.jp/nte/page/420112618024357379.html'),
    ('S10', 'official_en', 'https://nte.perfectworld.com/en/article/news/gamenews/20260929/264409.html'),
    ('S11', 'official_jp', 'https://nte.perfectworld.com/jp/article/news/gamenews/20260929/264412.html'),
    ('S12', 'official_cn_via_taptap', 'https://www.taptap.cn/app/714119/all-info'),
    ('S13', 'x_froggy', 'https://x.com/FroGGyNTE/status/2106929291342602360'),
    ('S2', 'gamefaqs_image', 'https://gamefaqs.gamespot.com/boards/475499-nte-neverness-to-everness/81198285'),
    ('S3', 'game8', 'https://game8.co/games/Neverness-to-Everness/archives/630789'),
    ('S4', 'namu', 'https://namu.wiki/w/%EC%9D%B4%ED%99%98/%EB%8F%84%EC%8B%9C%20%ED%83%80%EC%9D%B4%EC%BF%A4'),
    ('S5', 'reddit_via_gamewiki', 'https://game-wiki.online/nte/%E3%80%90nte-%E3%81%BE%E3%81%A8%E3%82%81%E3%80%91%E3%83%97%E3%82%AB%E8%A8%93%E7%B7%B4lv20%E3%81%AE%E3%82%B9%E3%83%86%E3%83%BC%E3%82%BF%E3%82%B9%E3%81%A8%E8%8E%AB%E5%A4%A7%E3%81%AA%E3%83%95%E3%82%A1/'),
    ('S6', 'ptt_disp', 'https://disp.cc/ptt/C_Chat/1gm9d4YT'),
    ('S7', 'arca_leak', 'https://arca.live/b/nevernesstoeverness/183555556'),
    ('S8', 'arca_plan_table', 'https://arca.live/b/nevernesstoeverness/184148155'),
    ('S9', 'official_kr', 'https://nte.perfectworld.com/kr/article/news/gamenews/20260929/264413.html'),
)

assert len(LEVELS) == MAX_LEVEL and [row[0] for row in LEVELS] == list(range(1, MAX_LEVEL + 1))
assert tuple(sum(row[3][i] for row in LEVELS) for i in range(len(COLUMNS))) == TOTALS
assert sum(row[2] for row in LEVELS) == TOTAL_COST_FONS


def clamp_level(level) -> int:
    """Integer level inside 0..MAX_LEVEL (non-integers and out-of-range values are clamped)."""
    try:
        value = int(level or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(MAX_LEVEL, value))


def cumulative_units(level) -> tuple[int, ...]:
    """Cumulative stored units (flat values, permille for CritBase / CritDamageBase) up to ``level``."""
    count = clamp_level(level)
    totals = [0] * len(COLUMNS)
    for row in LEVELS[:count]:
        for index, value in enumerate(row[3]):
            totals[index] += value
    return tuple(totals)


def cumulative_property_stats(level) -> dict[str, float]:
    """Calculator property values for ``level``: every column, zeros included (level 0 -> all 0.0)."""
    values = cumulative_units(level)
    return {
        column: (value / 1000.0 if column in PERMILLE_COLUMNS else float(value))
        for column, value in zip(COLUMNS, values)
    }


def cumulative_display(level) -> tuple:
    """Game-unit values for tooltips: flat values as int, the percent columns as percentage points."""
    values = cumulative_units(level)
    return tuple(
        (value / 10.0 if column in PERMILLE_COLUMNS else value)
        for column, value in zip(COLUMNS, values)
    )
