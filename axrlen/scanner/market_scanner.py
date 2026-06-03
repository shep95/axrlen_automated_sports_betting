"""Scan Polymarket for near-resolution markets."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from axrlen.config import Settings
from axrlen.models import MarketCategory, PolymarketMarket
from axrlen.polymarket.gamma_client import GammaClient

logger = logging.getLogger(__name__)


class MarketScanner:
    """Find markets resolving soon that match configured categories."""

    def __init__(self, settings: Settings, gamma: GammaClient | None = None) -> None:
        self._settings = settings
        self._gamma = gamma or GammaClient()

    def _category_allowed(self, market: PolymarketMarket) -> bool:
        allowed = {c.lower() for c in self._settings.market_categories}
        return market.category.value in allowed or "all" in allowed

    def _within_resolution_window(self, market: PolymarketMarket) -> bool:
        hours = market.hours_to_resolution
        if hours is None:
            return False
        return 0 < hours <= self._settings.resolution_window_hours

    def _is_almost_completed(self, market: PolymarketMarket) -> bool:
        """Prefer markets where one side is heavily priced but still tradable."""
        if not market.outcomes:
            return True
        prices = [o.price for o in market.outcomes if o.price > 0]
        if not prices:
            return True
        max_price = max(prices)
        min_price = min(prices)
        # Near resolution: strong consensus OR tight window
        return max_price >= 0.55 or (max_price - min_price) >= 0.10

    def score_market(self, market: PolymarketMarket) -> float:
        hours = market.hours_to_resolution or 999.0
        urgency = max(0.0, self._settings.resolution_window_hours - hours)
        liquidity_score = min(market.liquidity / 1000.0, 5.0)
        volume_score = min(market.volume / 5000.0, 5.0)
        consensus = 0.0
        if market.outcomes:
            prices = [o.price for o in market.outcomes]
            if prices:
                consensus = max(prices) - min(prices)
        return urgency * 2.0 + liquidity_score + volume_score + consensus

    def scan(self) -> list[PolymarketMarket]:
        raw_markets = self._gamma.fetch_markets(limit=150)
        logger.info("Fetched %d markets from Gamma API", len(raw_markets))

        candidates: list[PolymarketMarket] = []
        now = datetime.now(timezone.utc)

        for market in raw_markets:
            if not market.enable_order_book:
                continue
            if not self._category_allowed(market):
                continue
            if not self._within_resolution_window(market):
                continue
            if market.end_date and market.end_date <= now:
                continue
            if not self._is_almost_completed(market):
                continue
            candidates.append(market)

        # Category-specific search boost (weather, crypto short-term)
        for category in self._settings.market_categories:
            query = f"{category} tomorrow"
            try:
                searched = self._gamma.search_markets(query, limit=15)
            except Exception as exc:
                logger.warning("Search failed for %s: %s", query, exc)
                continue
            for market in searched:
                if market.market_id in {m.market_id for m in candidates}:
                    continue
                if not self._category_allowed(market):
                    continue
                if not self._within_resolution_window(market):
                    continue
                candidates.append(market)

        ranked = sorted(candidates, key=self.score_market, reverse=True)
        selected = ranked[: self._settings.max_markets_per_cycle]

        for market in selected:
            logger.info(
                "Selected market [%s] resolves in %.1fh: %s",
                market.category.value,
                market.hours_to_resolution or -1,
                market.question[:100],
            )
        return selected
