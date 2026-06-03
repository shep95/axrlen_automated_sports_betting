"""End-to-end paper trading cycle with mocked scan and AI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from axrlen.config import Settings
from axrlen.models import (
    AIVerdict,
    BetDecision,
    MarketCategory,
    PolymarketMarket,
    PolymarketOutcome,
    ScrapedContext,
    WorkflowQuestion,
)
from axrlen.workflow.pipeline import WorkflowPipeline


def _settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
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
        market_categories=("weather", "crypto"),
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


def _btc_updown_market() -> PolymarketMarket:
    return PolymarketMarket(
        market_id="test-btc-5m-001",
        question="Bitcoin Up or Down - 5 min window?",
        category=MarketCategory.CRYPTO,
        keywords=["bitcoin", "up", "down", "5min"],
        end_date=datetime.now(timezone.utc) + timedelta(minutes=8),
        outcomes=[
            PolymarketOutcome(name="Up", price=0.52, token_id="up-token"),
            PolymarketOutcome(name="Down", price=0.48, token_id="down-token"),
        ],
        liquidity=5000,
        volume=12000,
        enable_order_book=True,
    )


def test_paper_cycle_places_bet():
    settings = _settings()
    market = _btc_updown_market()
    verdict = AIVerdict(
        decision=BetDecision.YES,
        confidence=0.78,
        answer="BTC momentum favors Up.",
        reasoning="Spot ticking up this window.",
        workflow_question=WorkflowQuestion(
            subject="bitcoin / up / down",
            event="Bitcoin Up or Down - 5 min window",
            timeframe="today",
            question="Will Bitcoin Up or Down - 5 min window happen today?",
            market_id=market.market_id,
        ),
        correlation_id="test-correlation",
    )

    with TemporaryDirectory() as tmp:
        bankroll_path = Path(tmp) / "paper_bankroll.json"
        with patch("axrlen.polymarket.clob_trader.PAPER_BANKROLL_PATH", bankroll_path):
            pipeline = WorkflowPipeline(settings)
            pipeline._scanner.scan = MagicMock(return_value=[market])
            pipeline._scraper.scrape = MagicMock(
                return_value=[
                    ScrapedContext(
                        source="coingecko",
                        summary="BTC $95000, +0.2% last 5m.",
                    )
                ]
            )
            pipeline._ai.decide = MagicMock(return_value=verdict)
            pipeline._trader.get_midpoint_price = MagicMock(return_value=0.62)

            results = pipeline.run_cycle()

    assert len(results) == 1
    record = results[0]
    assert record["bet_success"] is True
    assert record["bet_paper"] is True
    assert record["bet_size_usd"] == 5.0
    assert record["ai_decision"] == "YES"

    bankroll = pipeline._trader.paper_bankroll
    assert bankroll is not None
    assert bankroll.has_open_position(market.market_id)
    snap = bankroll.snapshot()
    assert snap["capital"] == 95.0
    assert snap["bets_placed"] == 1
    assert snap["open_positions"] == 1
