"""Tests for market research prompts."""

from datetime import datetime, timedelta, timezone

from axrlen.ai.prompt_engine import build_market_research_prompt, build_workflow_question
from axrlen.models import MarketCategory, PolymarketMarket, PolymarketOutcome, ScrapedContext


def test_simple_workflow_uses_market_question():
    market = PolymarketMarket(
        market_id="1",
        question="Will NYC high temperature exceed 85°F on June 4?",
        category=MarketCategory.WEATHER,
        keywords=["nyc", "temperature"],
        end_date=datetime.now(timezone.utc) + timedelta(hours=18),
    )
    workflow = build_workflow_question(market, simple=True)
    assert workflow.question == market.question


def test_research_prompt_includes_market_and_research():
    market = PolymarketMarket(
        market_id="2",
        question="Will Bitcoin reach $100k by end of day?",
        category=MarketCategory.CRYPTO,
        end_date=datetime.now(timezone.utc) + timedelta(hours=6),
        outcomes=[
            PolymarketOutcome(name="Yes", price=0.4, token_id="y"),
            PolymarketOutcome(name="No", price=0.6, token_id="n"),
        ],
    )
    contexts = [ScrapedContext(source="coingecko", summary="BTC $95000, +2% 24h")]
    prompt = build_market_research_prompt(market, contexts)
    assert "MARKET" in prompt
    assert "RESEARCH" in prompt
    assert "Bitcoin" in prompt
    assert "coingecko" in prompt
    assert "Yes 40%" in prompt or "Yes 40" in prompt


def test_legacy_workflow_question_format():
    market = PolymarketMarket(
        market_id="3",
        question="Will it rain in Chicago tomorrow?",
        category=MarketCategory.WEATHER,
        keywords=["chicago", "rain"],
        end_date=datetime.now(timezone.utc) + timedelta(hours=20),
    )
    workflow = build_workflow_question(market, simple=False)
    assert workflow.question.startswith("Do you think")
