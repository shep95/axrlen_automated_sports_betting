"""Tests for duplicate-bet prevention on open markets."""

from pathlib import Path
from tempfile import TemporaryDirectory

from axrlen.config import Settings
from axrlen.models import BetDecision, MarketCategory, PolymarketMarket
from axrlen.paper_bankroll import PaperBankroll


def _settings() -> Settings:
    return Settings(
        openai_api_key="test",
        openai_model="gpt-5.2-chat-latest",
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
        market_categories=("weather",),
        health_port=8080,
        log_level="INFO",
        tavily_api_key="",
        clob_api_key="",
        clob_api_secret="",
        clob_api_passphrase="",
        brains_dir=Path("brains"),
        brains_max_chars=250_000,
        ai_research_simple=True,
        max_ai_retries=3,
        ai_timeout_seconds=60.0,
    )


def test_rejects_second_bet_on_same_market():
    market = PolymarketMarket(
        market_id="market-abc",
        question="Will it rain in NYC tomorrow?",
        category=MarketCategory.WEATHER,
    )
    with TemporaryDirectory() as tmp:
        bankroll = PaperBankroll(_settings(), Path(tmp) / "paper.json")
        stake1, result1 = bankroll.place_bet(
            market, BetDecision.YES, price=0.5, correlation_id="c1"
        )
        stake2, result2 = bankroll.place_bet(
            market, BetDecision.YES, price=0.5, correlation_id="c2"
        )

    assert stake1 == 5.0
    assert result1.get("rejected") is not True
    assert stake2 == 0.0
    assert result2.get("rejected") is True
    assert result2.get("reason") == "open_position_exists"
    assert bankroll.has_open_position("market-abc")
