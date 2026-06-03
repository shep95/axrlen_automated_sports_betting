"""AI decision gateway with retry and schema validation."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Protocol

from openai import OpenAI
from pydantic import ValidationError

from axrlen.ai.brains_loader import load_brains
from axrlen.ai.prompt_engine import build_workflow_question, format_market_context, format_scraped_context
from axrlen.config import Settings
from axrlen.models import AIVerdict, BetDecision, PolymarketMarket, ScrapedContext, WorkflowQuestion

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """<brains>
{brains}
</brains>

You evaluate Polymarket bets using the Axrlen workflow.

WORKFLOW LOGIC:
1. Read the market and scraped data inside XML tags only.
2. Answer the workflow question with a simple YES, NO, or SKIP.
3. Return ONLY valid JSON matching this schema:
{{"decision": "YES"|"NO"|"SKIP", "confidence": 0.0-1.0, "answer": "one short sentence", "reasoning": "2-3 sentences max"}}

Simple question, simple answer. No markdown. No extra keys."""


class ModelGateway(Protocol):
    def decide(
        self,
        market: PolymarketMarket,
        contexts: list[ScrapedContext],
        *,
        correlation_id: str,
    ) -> AIVerdict: ...


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            obj, _ = json.JSONDecoder().raw_decode(fenced.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    return None


def _normalize_decision(raw: str) -> BetDecision:
    value = raw.strip().upper()
    if value in ("YES", "Y", "TRUE"):
        return BetDecision.YES
    if value in ("NO", "N", "FALSE"):
        return BetDecision.NO
    return BetDecision.SKIP


class OpenAIDecisionGateway:
    """Provider-agnostic AI gateway (OpenAI implementation)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
        self._brains = load_brains(settings.brains_dir)

    def _build_user_prompt(
        self,
        market: PolymarketMarket,
        contexts: list[ScrapedContext],
        workflow: WorkflowQuestion,
    ) -> str:
        return f"""<market>
{format_market_context(market)}
</market>

<scraped_data>
{format_scraped_context(contexts)}
</scraped_data>

<workflow_question>
{workflow.question}
</workflow_question>

Answer the workflow question. JSON only."""

    def decide(
        self,
        market: PolymarketMarket,
        contexts: list[ScrapedContext],
        *,
        correlation_id: str | None = None,
    ) -> AIVerdict:
        correlation_id = correlation_id or str(uuid.uuid4())
        workflow = build_workflow_question(market)
        user_prompt = self._build_user_prompt(market, contexts, workflow)
        system_prompt = SYSTEM_TEMPLATE.format(brains=self._brains)

        last_error = "unknown"
        for attempt in range(1, self._settings.max_ai_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=300,
                )
                raw = (response.choices[0].message.content or "").strip()
                data = _extract_json(raw)
                if data is None:
                    last_error = f"invalid JSON: {raw[:200]}"
                    logger.warning("[%s] AI JSON parse failed attempt %d", correlation_id, attempt)
                    time.sleep(min(2 ** attempt, 8))
                    continue

                decision = _normalize_decision(str(data.get("decision", "SKIP")))
                try:
                    confidence = float(data.get("confidence", 0.5))
                except (TypeError, ValueError):
                    confidence = 0.5

                verdict = AIVerdict(
                    decision=decision,
                    confidence=confidence,
                    answer=str(data.get("answer", decision.value)).strip()[:500],
                    reasoning=str(data.get("reasoning", "")).strip()[:2000],
                    workflow_question=workflow,
                    correlation_id=correlation_id,
                )
                logger.info(
                    "[%s] AI verdict: %s (%.0f%%) — %s",
                    correlation_id,
                    verdict.decision.value,
                    verdict.confidence * 100,
                    verdict.answer,
                )
                return verdict
            except ValidationError as exc:
                last_error = str(exc)
                logger.warning("[%s] Validation failed attempt %d: %s", correlation_id, attempt, exc)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("[%s] AI call failed attempt %d: %s", correlation_id, attempt, exc)
            time.sleep(min(2 ** attempt, 8))

        return AIVerdict(
            decision=BetDecision.SKIP,
            confidence=0.0,
            answer="AI unavailable",
            reasoning=f"Failed after retries: {last_error}",
            workflow_question=workflow,
            correlation_id=correlation_id,
        )
