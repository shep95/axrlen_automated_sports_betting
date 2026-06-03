"""Tests for market scanner scoring."""

from datetime import datetime, timedelta, timezone

from axrlen.config import Settings
from axrlen.models import MarketCategory, PolymarketMarket, PolymarketOutcome
from axrlen.scanner.market_scanner import MarketScanner


def _settings(**overrides):
    base = dict(
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
        live_trading=False,
        paper_trading=True,
        polymarket_private_key="",
        polymarket_funder_address="",
        polymarket_signature_type=3,
        bet_size_usd=5.0,
        min_confidence=0.65,
        max_markets_per_cycle=3,
        scan_interval_minutes=7,
        resolution_window_hours=24,
        market_categories=("weather", "crypto"),
        health_port=8080,
        log_level="INFO",
        tavily_api_key="",
        clob_api_key="",
        clob_api_secret="",
        clob_api_passphrase="",
        brains_dir=__import__("pathlib").Path("brains"),
        max_ai_retries=3,
        ai_timeout_seconds=60.0,
    )
    base.update(overrides)
    return Settings(**base)


def test_score_prefers_sooner_markets():
    scanner = MarketScanner(_settings())
    soon = PolymarketMarket(
        market_id="a",
        question="Rain in NYC tomorrow?",
        category=MarketCategory.WEATHER,
        end_date=datetime.now(timezone.utc) + timedelta(hours=5),
        outcomes=[PolymarketOutcome(name="Yes", price=0.6, token_id="y")],
        liquidity=2000,
        volume=10000,
    )
    later = PolymarketMarket(
        market_id="b",
        question="Rain in NYC next week?",
        category=MarketCategory.WEATHER,
        end_date=datetime.now(timezone.utc) + timedelta(hours=20),
        outcomes=[PolymarketOutcome(name="Yes", price=0.6, token_id="y")],
        liquidity=2000,
        volume=10000,
    )
    assert scanner.score_market(soon) > scanner.score_market(later)
