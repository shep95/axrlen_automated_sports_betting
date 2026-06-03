"""Scan Polymarket for near-resolution markets."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from axrlen.config import ALLOWED_MARKET_CATEGORIES, Settings
from axrlen.models import MarketCategory, PolymarketMarket
from axrlen.polymarket.gamma_client import GammaClient

logger = logging.getLogger(__name__)


class MarketScanner:
    """Find markets resolving soon that match configured categories."""

    def __init__(self, settings: Settings, gamma: GammaClient | None = None) -> None:
        self._settings = settings
        self._gamma = gamma or GammaClient()

    def _category_allowed(self, market: PolymarketMarket) -> bool:
        cat = market.category.value
        if cat not in ALLOWED_MARKET_CATEGORIES:
            return False
        configured = {c.lower() for c in self._settings.market_categories}
        return cat in configured

    def _within_resolution_window(self, market: PolymarketMarket) -> bool:
        hours = market.hours_to_resolution
        if hours is None:
            return False
        return 0 < hours <= self._settings.resolution_window_hours

    def _passes_liquidity_price_filter(self, market: PolymarketMarket) -> bool:
        """Skip only dead markets (no real two-sided book)."""
        if not market.outcomes:
            return True
        prices = [o.price for o in market.outcomes if o.price > 0]
        if not prices:
            return True
        max_price = max(prices)
        min_price = min(prices)
        # Reject only if both sides are extreme longshots (no tradeable book)
        return max_price >= 0.08 and min_price >= 0.02

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

    def _try_add(
        self,
        market: PolymarketMarket,
        candidates: list[PolymarketMarket],
        now: datetime,
        stats: dict[str, int],
    ) -> None:
        if not market.enable_order_book:
            stats["no_order_book"] += 1
            return
        if market.category.value not in ALLOWED_MARKET_CATEGORIES:
            stats["not_weather_or_crypto"] += 1
            return
        if not self._category_allowed(market):
            stats["wrong_category"] += 1
            return
        if not self._within_resolution_window(market):
            stats["outside_window"] += 1
            return
        if market.end_date and market.end_date <= now:
            stats["already_ended"] += 1
            return
        if not self._passes_liquidity_price_filter(market):
            stats["illiquid_price"] += 1
            return
        if market.market_id in {m.market_id for m in candidates}:
            stats["duplicate"] += 1
            return
        stats["passed"] += 1
        candidates.append(market)

    def scan(self) -> list[PolymarketMarket]:
        raw_markets = self._gamma.fetch_markets(limit=150)
        logger.info("Fetched %d markets from Gamma API", len(raw_markets))

        candidates: list[PolymarketMarket] = []
        now = datetime.now(timezone.utc)
        stats = {
            "no_order_book": 0,
            "not_weather_or_crypto": 0,
            "wrong_category": 0,
            "outside_window": 0,
            "already_ended": 0,
            "illiquid_price": 0,
            "duplicate": 0,
            "passed": 0,
        }

        for market in raw_markets:
            self._try_add(market, candidates, now, stats)

        for category in self._settings.market_categories:
            query = f"{category} tomorrow"
            try:
                searched = self._gamma.search_markets(query, limit=15)
            except Exception as exc:
                logger.warning("Search failed for %s: %s", query, exc)
                continue
            for market in searched:
                self._try_add(market, candidates, now, stats)

        if not candidates:
            logger.info(
                "Scan filters: no_order_book=%d not_weather_or_crypto=%d wrong_category=%d "
                "outside_window=%d already_ended=%d illiquid_price=%d | "
                "window=%dh (max 24h) categories=%s",
                stats["no_order_book"],
                stats["not_weather_or_crypto"],
                stats["wrong_category"],
                stats["outside_window"],
                stats["already_ended"],
                stats["illiquid_price"],
                self._settings.resolution_window_hours,
                ",".join(self._settings.market_categories),
            )

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
