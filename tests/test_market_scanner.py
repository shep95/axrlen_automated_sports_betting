"""Tests for market scanner scoring."""

from datetime import datetime, timedelta, timezone

from axrlen.config import Settings
from axrlen.models import MarketCategory, PolymarketMarket, PolymarketOutcome
from axrlen.scanner.btc_updown import is_btc_up_or_down_5min
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
        paper_starting_capital=100.0,
        paper_min_bet_usd=5.0,
        paper_max_bet_usd=50.0,
        paper_compound_threshold_usd=300.0,
        paper_compound_pct=0.10,
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
        brains_max_chars=250_000,
        ai_research_simple=True,
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


def test_btc_updown_passes_scanner_filters():
    scanner = MarketScanner(_settings())
    market = PolymarketMarket(
        market_id="btc-5m",
        question="Bitcoin Up or Down - 5 min?",
        category=MarketCategory.CRYPTO,
        end_date=datetime.now(timezone.utc) + timedelta(minutes=8),
        outcomes=[PolymarketOutcome(name="Up", price=0.52, token_id="u")],
        enable_order_book=True,
    )
    assert is_btc_up_or_down_5min(market)
    assert scanner._within_resolution_window(market)
