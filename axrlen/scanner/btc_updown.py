"""Filter for Polymarket BTC Up or Down short-window markets."""

from __future__ import annotations

import re

from axrlen.models import PolymarketMarket

# Polymarket titles vary; match all three signals in question/description/slug.
_BTC_TERMS = ("bitcoin", "btc")
_UPDOWN_TERMS = ("up or down", "up/down", "up-down")
_FIVE_MIN_TERMS = (
    "5 min",
    "5-min",
    "5min",
    "5 minutes",
    "five minute",
    "5m ",
    " 5m",
)


def market_text_blob(market: PolymarketMarket) -> str:
    return f"{market.question} {market.description} {market.slug}".lower()


def is_btc_up_or_down_5min(market: PolymarketMarket) -> bool:
    """True only for BTC (or Bitcoin) Up/Down markets with a ~5-minute window."""
    blob = market_text_blob(market)

    has_btc = any(term in blob for term in _BTC_TERMS)
    has_up_down = any(term in blob for term in _UPDOWN_TERMS)
    has_five_min = any(term in blob for term in _FIVE_MIN_TERMS)

    # e.g. "12:05PM-12:10PM" (5-minute slot)
    if not has_five_min:
        has_five_min = bool(
            re.search(
                r"\d{1,2}:\d{2}\s*(?:am|pm)?\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm)?",
                blob,
                re.IGNORECASE,
            )
        )

    return has_btc and has_up_down and has_five_min


BTC_UPDOWN_SEARCH_QUERIES = (
    "bitcoin up or down 5 min",
    "btc up or down 5 minutes",
    "bitcoin up or down",
)
