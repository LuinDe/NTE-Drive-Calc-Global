# 游戏资料库争锋赏宴按活动期浏览的页面行为。
"""Feast period and challenge browsing mixed into the monster archive page."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from src.features.static_catalog.domain_pages.monster_browse_models import (
    PLAY_LABELS,
    BrowseCard,
    BrowseSection,
    BrowseState,
)
from src.services.static_catalog_monster_models import FeastPeriod, FeastSetup


class FeastCatalogBrowserMixin:
    """Render period cards first, then the period's ordered challenges."""

    def _feast_state(self) -> BrowseState:
        periods = self._controller.feast_periods()
        active = tuple(
            self._feast_period_card(period) for period in periods
            if period.release_state in {"current", "next", "scheduled"}
        )
        history = tuple(
            self._feast_period_card(period) for period in periods
            if period.release_state == "historical"
        )
        sections = []
        if active:
            sections.append(BrowseSection(
                _L('当前与预计'),
                _L('按大陆服公开排期判定；进入活动期后再选择挑战对象。'),
                active,
            ))
        if history:
            sections.append(BrowseSection(
                _L('往期'),
                _L('保留同期正式挑战成员；数值读取发行资源中仍可验证的配置。'),
                history,
            ))
        return BrowseState(
            PLAY_LABELS["feast"],
            _L('先选择活动期，再按当期正式顺序查看挑战、难度和敌方画像。'),
            tuple(sections),
        )

    def _feast_period_card(self, period: FeastPeriod) -> BrowseCard:
        setup = self._controller.feast_setup(
            period.period_id, period.challenge_ids[0]
        )
        state_label = {
            "current": _L('当期'), "next": _L('预计'), "scheduled": _L('预计'),
            "historical": _L('往期'),
        }
        return BrowseCard(
            period.display_label,
            _LF('{0} 个挑战 · {1}').format((len(period.challenge_ids)), (period.schedule_label)),
            state_label.get(period.release_state, period.release_state),
            self._feast_setup_icon(setup),
            lambda checked=False, value=period: self._open_feast_period(value),
            formal_id=period.period_id,
            category=state_label.get(period.release_state, ""),
            period=period.display_label,
        )

    def _open_feast_period(self, period: FeastPeriod) -> None:
        cards = []
        for stage_id in period.challenge_ids:
            setup = self._controller.feast_setup(period.period_id, stage_id)
            if setup is None:
                continue
            cards.append(BrowseCard(
                _LF('挑战 {0} · {1}').format((setup.challenge_ordinal), (setup.title)),
                _LF('{0} · {1} 个难度').format((setup.boss_name), (len(setup.difficulties))),
                _L('挑战对象'),
                self._feast_setup_icon(setup),
                lambda checked=False, value=setup: self._open_feast_stage(value),
                formal_id=stage_id,
                period=period.display_label,
            ))
        self._show_state(BrowseState(
            _LF('争锋赏宴 · {0}').format((period.display_label)),
            _LF('{0} · 选择挑战后查看难度、条件与敌方画像。').format((period.schedule_label)),
            (BrowseSection(
                _L('挑战对象'), _LF('共 {0} 个，按当期正式顺序展示。').format((len(cards))),
                tuple(cards),
            ),),
        ), push=True)

    def _feast_setup_icon(self, setup: FeastSetup | None) -> Path | None:
        if setup is None:
            return None
        detail = self._controller.feast_detail(
            setup.period_id, setup.stage_id, setup.default_difficulty_id, ()
        )
        return self._formal_icon(detail)

    def _open_feast_stage(self, setup: FeastSetup) -> None:
        self.feast_view.set_stage(
            setup,
            icon=self._feast_setup_icon(setup),
            loader=self._controller.feast_detail,
            blessings=self._controller.witch_blessings(),
            blessing_loader=self._controller.detail,
        )
        self.stack.setCurrentWidget(self.feast_view)
        self._catalog_navigation_listener()
