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
from axrlen.ai.prompt_engine import build_market_research_prompt, build_workflow_question
from axrlen.config import Settings
from axrlen.models import AIVerdict, BetDecision, PolymarketMarket, ScrapedContext, WorkflowQuestion

logger = logging.getLogger(__name__)

SYSTEM_SIMPLE = """You are a Polymarket market research analyst.

{brain}

Axrlen rule: simple question, simple answer.

Rules:
- Answer ONLY the QUESTION line in the user message.
- Use only QUESTION, MARKET, and RESEARCH — ignore outside knowledge.
- Compare research to market odds; bet YES or NO only when you see mispricing.
- Output a single JSON object with keys: decision, confidence, answer, reasoning.
- decision must be YES, NO, or SKIP (uppercase).
- answer: one short sentence, no markdown.
- reasoning: at most two short sentences.
- No extra keys, no prose before or after JSON."""

SYSTEM_FULL = """<brains>
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


def _validate_simple_response(data: dict[str, Any]) -> str | None:
    """Return error message if response breaks simple-answer rules."""
    answer = str(data.get("answer", "")).strip()
    reasoning = str(data.get("reasoning", "")).strip()
    if not answer:
        return "empty answer"
    if "```" in answer or "\n-" in answer or answer.count(".") > 2:
        return "answer must be one short sentence"
    if len(answer) > 220:
        return "answer too long"
    if len(reasoning) > 400:
        return "reasoning too long (max ~2 sentences)"
    return None


class OpenAIDecisionGateway:
    """Provider-agnostic AI gateway (OpenAI implementation)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds)
        self._simple = settings.ai_research_simple
        self._brains = load_brains(
            settings.brains_dir,
            max_chars=settings.brains_max_chars,
            simple=self._simple,
        )

    def _system_prompt(self) -> str:
        if self._simple:
            return SYSTEM_SIMPLE.format(brain=self._brains)
        return SYSTEM_FULL.format(brains=self._brains)

    def _build_user_prompt(
        self,
        market: PolymarketMarket,
        contexts: list[ScrapedContext],
        workflow: WorkflowQuestion,
    ) -> str:
        if self._simple:
            return build_market_research_prompt(
                market, contexts, workflow_question=workflow.question
            )

        from axrlen.ai.prompt_engine import format_market_context, format_scraped_context

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
        workflow = build_workflow_question(market, simple=self._simple)
        user_prompt = self._build_user_prompt(market, contexts, workflow)
        system_prompt = self._system_prompt()

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

                if self._simple:
                    validation_error = _validate_simple_response(data)
                    if validation_error:
                        last_error = validation_error
                        logger.warning(
                            "[%s] AI response format rejected attempt %d: %s",
                            correlation_id,
                            attempt,
                            validation_error,
                        )
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
