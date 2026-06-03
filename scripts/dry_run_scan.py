"""Scan Gamma and print filter diagnostics (no OpenAI key required)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from axrlen.config import load_settings
from axrlen.models import MarketCategory
from axrlen.polymarket.gamma_client import GammaClient, classify_market

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("dry_run")


def main() -> None:
    settings = load_settings()
    gamma = GammaClient()
    raw = gamma.fetch_markets(limit=150)
    now = datetime.now(timezone.utc)
    allowed = {c.lower() for c in settings.market_categories}

    stats = {
        "fetched": len(raw),
        "no_order_book": 0,
        "wrong_category": 0,
        "no_end_date": 0,
        "outside_window": 0,
        "already_ended": 0,
        "price_filter": 0,
        "passed": 0,
    }
    passed_samples: list[str] = []

    for market in raw:
        if not market.enable_order_book:
            stats["no_order_book"] += 1
            continue
        if market.category.value not in allowed and "all" not in allowed:
            stats["wrong_category"] += 1
            continue
        hours = market.hours_to_resolution
        if hours is None:
            stats["no_end_date"] += 1
            continue
        if not (0 < hours <= settings.resolution_window_hours):
            stats["outside_window"] += 1
            continue
        if market.end_date and market.end_date <= now:
            stats["already_ended"] += 1
            continue
        prices = [o.price for o in market.outcomes if o.price > 0]
        if prices:
            max_p, min_p = max(prices), min(prices)
            if max_p < 0.52 and (max_p - min_p) < 0.08:
                stats["price_filter"] += 1
                continue
        stats["passed"] += 1
        if len(passed_samples) < 5:
            passed_samples.append(
                f"  [{market.category.value}] {hours:.0f}h | {market.question[:90]}"
            )

    print("\n=== Gamma scan diagnostics ===")
    print(f"Categories: {settings.market_categories}")
    print(f"Resolution window: {settings.resolution_window_hours}h")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    if passed_samples:
        print("\nSample qualifying markets:")
        print("\n".join(passed_samples))
    else:
        print("\nNo markets passed filters — consider widening POLYMARKET_GAMMA_RESOLUTION_HOURS")


if __name__ == "__main__":
    main()
