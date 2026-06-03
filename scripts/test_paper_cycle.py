#!/usr/bin/env python3
"""Run one paper-trading cycle. Use --fixture for offline test without API keys."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from axrlen.config import load_settings
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_paper")


def _fixture_market() -> PolymarketMarket:
    return PolymarketMarket(
        market_id="fixture-weather-nyc",
        question="Will NYC high temperature exceed 85°F tomorrow?",
        category=MarketCategory.WEATHER,
        keywords=["nyc", "temperature"],
        end_date=datetime.now(timezone.utc) + timedelta(hours=12),
        outcomes=[
            PolymarketOutcome(name="Yes", price=0.58, token_id="yes-fixture"),
            PolymarketOutcome(name="No", price=0.42, token_id="no-fixture"),
        ],
        liquidity=3000,
        volume=8000,
        enable_order_book=True,
    )


def _fixture_verdict(market: PolymarketMarket) -> AIVerdict:
    return AIVerdict(
        decision=BetDecision.YES,
        confidence=0.72,
        answer="Fixture test: forecast favors Yes.",
        reasoning="Simulated research supports YES for paper test.",
        workflow_question=WorkflowQuestion(
            subject="nyc / temperature",
            event="NYC high temperature exceed 85°F tomorrow",
            timeframe="today",
            question="Will NYC high temperature exceed 85°F tomorrow happen today?",
            market_id=market.market_id,
        ),
        correlation_id="fixture-run",
    )


def run_fixture_cycle() -> bool:
    """Offline paper bet — no OpenAI or Polymarket network required."""
    from unittest.mock import MagicMock, patch

    from axrlen.scanner.market_scanner import MarketScanner

    os.environ.setdefault("OPENAI_API_KEY", "fixture-test-key")

    market = _fixture_market()
    verdict = _fixture_verdict(market)

    settings = load_settings()
    with patch.object(MarketScanner, "scan", return_value=[market]):
        pipeline = WorkflowPipeline(settings)
        pipeline._scraper.scrape = MagicMock(
            return_value=[ScrapedContext(source="fixture", summary="High 31C expected.")]
        )
        pipeline._ai.decide = MagicMock(return_value=verdict)
        pipeline._trader.get_midpoint_price = MagicMock(return_value=0.58)

        results = pipeline.run_cycle()

    if not results or not results[0].get("bet_success"):
        logger.error("Fixture cycle did not place a paper bet: %s", results)
        return False

    snap = pipeline._trader.paper_bankroll.snapshot() if pipeline._trader.paper_bankroll else {}
    logger.info("SUCCESS — paper bet placed | stake=$%.2f | capital=$%.2f", results[0]["bet_size_usd"], snap.get("capital", 0))
    logger.info("Bankroll: %s", snap)
    return True


def run_live_cycle() -> bool:
    """Real scan + OpenAI + paper bet (needs OPENAI_API_KEY and network)."""
    settings = load_settings()
    pipeline = WorkflowPipeline(settings)
    results = pipeline.run_cycle()
    if not results:
        logger.warning("No markets processed — try POLYMARKET_GAMMA_RESOLUTION_HOURS or check Polymarket listings")
        return False
    for record in results:
        logger.info(
            "Market %s | AI=%s | bet_success=%s | size=$%.2f | %s",
            record.get("market_id"),
            record.get("ai_decision"),
            record.get("bet_success"),
            record.get("bet_size_usd", 0),
            record.get("bet_message"),
        )
    placed = any(r.get("bet_success") and r.get("bet_size_usd", 0) > 0 for r in results)
    if pipeline._trader.paper_bankroll:
        pipeline._trader.paper_bankroll.log_summary(context="TEST-RUN")
    return placed


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Axrlen paper trading cycle")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Offline test with a fake weather market (no API keys)",
    )
    args = parser.parse_args()

    try:
        ok = run_fixture_cycle() if args.fixture else run_live_cycle()
    except ValueError as exc:
        logger.error("Config error: %s", exc)
        logger.info("For offline test run: python scripts/test_paper_cycle.py --fixture")
        return 1
    except Exception as exc:
        logger.exception("Test failed: %s", exc)
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
