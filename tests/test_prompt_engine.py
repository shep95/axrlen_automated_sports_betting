"""Tests for workflow prompt engineering."""

from datetime import datetime, timedelta, timezone

from axrlen.ai.prompt_engine import build_workflow_question
from axrlen.models import MarketCategory, PolymarketMarket, PolymarketOutcome


def test_build_workflow_question_weather():
    market = PolymarketMarket(
        market_id="1",
        question="Will NYC high temperature exceed 85°F on June 4?",
        category=MarketCategory.WEATHER,
        keywords=["nyc", "high", "temperature", "exceed", "85f"],
        end_date=datetime.now(timezone.utc) + timedelta(hours=18),
        outcomes=[
            PolymarketOutcome(name="Yes", price=0.72, token_id="yes"),
            PolymarketOutcome(name="No", price=0.28, token_id="no"),
        ],
    )
    workflow = build_workflow_question(market)
    assert workflow.subject
    assert "tomorrow" in workflow.timeframe or "today" in workflow.timeframe
    assert workflow.question.startswith("Do you think")
    assert "happen" in workflow.question


def test_build_workflow_question_crypto():
    market = PolymarketMarket(
        market_id="2",
        question="Will Bitcoin reach $100k by end of day?",
        category=MarketCategory.CRYPTO,
        keywords=["bitcoin", "100k"],
        end_date=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    workflow = build_workflow_question(market)
    assert "bitcoin" in workflow.subject.lower() or "100k" in workflow.subject.lower()
    assert workflow.market_id == "2"
