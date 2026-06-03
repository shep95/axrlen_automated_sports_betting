"""Tests for BTC Up/Down 5-minute market matching."""

from datetime import datetime, timedelta, timezone

from axrlen.models import PolymarketMarket
from axrlen.scanner.btc_updown import is_btc_up_or_down_5min


def test_matches_bitcoin_up_or_down_5_min():
    market = PolymarketMarket(
        market_id="1",
        question="Bitcoin Up or Down - 5 min window ending 12:10 PM ET?",
        description="5 minute candle",
    )
    assert is_btc_up_or_down_5min(market) is True


def test_matches_btc_time_range():
    market = PolymarketMarket(
        market_id="2",
        question="BTC Up or Down",
        description="12:05PM-12:10PM ET",
        slug="btc-up-or-down-march",
    )
    assert is_btc_up_or_down_5min(market) is True


def test_rejects_weather():
    market = PolymarketMarket(
        market_id="3",
        question="Will it rain in NYC tomorrow?",
    )
    assert is_btc_up_or_down_5min(market) is False


def test_rejects_btc_without_5min():
    market = PolymarketMarket(
        market_id="4",
        question="Will Bitcoin reach $100k by end of month?",
    )
    assert is_btc_up_or_down_5min(market) is False
