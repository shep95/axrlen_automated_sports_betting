"""End-to-end Axrlen workflow pipeline."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from axrlen.ai.decision_gateway import OpenAIDecisionGateway
from axrlen.config import JOURNAL_PATH, Settings
from axrlen.models import AIVerdict, BetDecision, BetExecutionResult, PolymarketMarket
from axrlen.polymarket.clob_trader import ClobTrader
from axrlen.scanner.market_scanner import MarketScanner
from axrlen.scraper.web_scraper import ContextScraper

logger = logging.getLogger(__name__)


class WorkflowPipeline:
    """
    Axrlen workflow:
    Polymarket scan → scrape web → workflow question → AI verdict → place bet
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._scanner = MarketScanner(settings)
        self._scraper = ContextScraper(settings)
        self._ai = OpenAIDecisionGateway(settings)
        self._trader = ClobTrader(settings)

    def _journal(self, record: dict) -> None:
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            with JOURNAL_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            logger.error("Journal write failed: %s", exc)

    def process_market(self, market: PolymarketMarket) -> dict:
        correlation_id = str(uuid.uuid4())
        logger.info("[%s] Processing: %s", correlation_id, market.question[:100])

        contexts = self._scraper.scrape(market)
        verdict = self._ai.decide(market, contexts, correlation_id=correlation_id)

        execution: BetExecutionResult | None = None
        if verdict.decision == BetDecision.SKIP:
            execution = self._trader.execute_bet(market, BetDecision.SKIP, correlation_id=correlation_id)
        elif verdict.confidence >= self._settings.min_confidence:
            execution = self._trader.execute_bet(market, verdict.decision, correlation_id=correlation_id)
        else:
            logger.info(
                "[%s] Confidence %.0f%% below threshold %.0f%% — skipping bet",
                correlation_id,
                verdict.confidence * 100,
                self._settings.min_confidence * 100,
            )
            execution = self._trader.execute_bet(market, BetDecision.SKIP, correlation_id=correlation_id)

        record = {
            "correlation_id": correlation_id,
            "market_id": market.market_id,
            "question": market.question,
            "category": market.category.value,
            "workflow_question": verdict.workflow_question.question,
            "ai_decision": verdict.decision.value,
            "confidence": verdict.confidence,
            "answer": verdict.answer,
            "reasoning": verdict.reasoning,
            "bet_success": execution.success if execution else False,
            "bet_paper": execution.paper if execution else True,
            "bet_size_usd": execution.size_usd if execution else 0.0,
            "bet_price": execution.price if execution else 0.0,
            "bet_message": execution.message if execution else "",
            "bankroll": execution.bankroll if execution else None,
        }
        self._journal(record)
        return record

    def run_cycle(self) -> list[dict]:
        if self._settings.paper_trading or not self._settings.is_live:
            settled = self._trader.settle_paper_positions()
            if settled:
                logger.info("Settled %d paper position(s) this cycle", settled)

        markets = self._scanner.scan()
        if not markets:
            logger.info("No qualifying markets this cycle")
            return []

        results = []
        for market in markets:
            try:
                results.append(self.process_market(market))
            except Exception as exc:
                logger.exception("Market processing failed: %s", exc)

        if (self._settings.paper_trading or not self._settings.is_live) and self._trader.paper_bankroll:
            self._trader.paper_bankroll.log_summary(context="CYCLE-END")

        return results
