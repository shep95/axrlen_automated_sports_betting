"""Scan Polymarket for BTC Up or Down 5-minute markets only."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from axrlen.config import Settings
from axrlen.models import PolymarketMarket
from axrlen.polymarket.gamma_client import GammaClient
from axrlen.scanner.btc_updown import BTC_UPDOWN_SEARCH_QUERIES, is_btc_up_or_down_5min

logger = logging.getLogger(__name__)


class MarketScanner:
    """Find BTC Up/Down ~5min markets resolving soon."""

    def __init__(self, settings: Settings, gamma: GammaClient | None = None) -> None:
        self._settings = settings
        self._gamma = gamma or GammaClient()

    def _within_resolution_window(self, market: PolymarketMarket) -> bool:
        hours = market.hours_to_resolution
        if hours is None:
            return False
        return 0 < hours <= self._settings.resolution_window_hours

    def _passes_liquidity_price_filter(self, market: PolymarketMarket) -> bool:
        if not market.outcomes:
            return True
        prices = [o.price for o in market.outcomes if o.price > 0]
        if not prices:
            return True
        max_price = max(prices)
        min_price = min(prices)
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
        if not is_btc_up_or_down_5min(market):
            stats["not_btc_updown_5min"] += 1
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
        raw_markets = self._gamma.fetch_markets(limit=200)
        logger.info("Fetched %d markets from Gamma API", len(raw_markets))

        candidates: list[PolymarketMarket] = []
        now = datetime.now(timezone.utc)
        stats = {
            "no_order_book": 0,
            "not_btc_updown_5min": 0,
            "outside_window": 0,
            "already_ended": 0,
            "illiquid_price": 0,
            "duplicate": 0,
            "passed": 0,
        }

        for market in raw_markets:
            self._try_add(market, candidates, now, stats)

        for query in BTC_UPDOWN_SEARCH_QUERIES:
            try:
                searched = self._gamma.search_markets(query, limit=25)
            except Exception as exc:
                logger.warning("Search failed for %r: %s", query, exc)
                continue
            for market in searched:
                self._try_add(market, candidates, now, stats)

        if not candidates:
            logger.info(
                "Scan filters: no_order_book=%d not_btc_updown_5min=%d outside_window=%d "
                "already_ended=%d illiquid_price=%d | window=%.2fh | target=BTC up/down 5min",
                stats["no_order_book"],
                stats["not_btc_updown_5min"],
                stats["outside_window"],
                stats["already_ended"],
                stats["illiquid_price"],
                self._settings.resolution_window_hours,
            )

        ranked = sorted(candidates, key=self.score_market, reverse=True)
        selected = ranked[: self._settings.max_markets_per_cycle]

        for market in selected:
            logger.info(
                "Selected BTC up/down 5m | resolves in %.2fh: %s",
                market.hours_to_resolution or -1,
                market.question[:100],
            )
        return selected
