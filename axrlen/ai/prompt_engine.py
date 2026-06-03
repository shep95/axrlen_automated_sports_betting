"""Market research prompts — simple question, simple answer."""

from __future__ import annotations

import re

from axrlen.models import PolymarketMarket, ScrapedContext, WorkflowQuestion


def _strip_question_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^(will|does|is|are|can|could|should)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.rstrip("?").strip()


def _extract_subject(keywords: list[str], question: str) -> str:
    if keywords:
        return " / ".join(keywords[:4])
    words = re.findall(r"[A-Za-z0-9$]+", question)
    if len(words) >= 2:
        return " ".join(words[:3])
    return "this market"


def _timeframe_label(market: PolymarketMarket) -> str:
    hours = market.hours_to_resolution
    if hours is None:
        return "before resolution"
    if hours <= 12:
        return "today"
    if hours <= 24:
        return "tomorrow"
    days = int(hours // 24)
    return f"within {days} day{'s' if days != 1 else ''}"


def build_simple_question(market: PolymarketMarket) -> str:
    """One-line yes/no question for the AI (Axrlen workflow)."""
    event = _strip_question_prefix(market.question)
    timeframe = _timeframe_label(market)
    return f"Will {event} happen {timeframe}?"


def build_workflow_question(market: PolymarketMarket, *, simple: bool = True) -> WorkflowQuestion:
    """Workflow question stored in logs and journal."""
    event = _strip_question_prefix(market.question)
    subject = _extract_subject(market.keywords, market.question)
    timeframe = _timeframe_label(market)

    if simple:
        question = build_simple_question(market)
    else:
        question = f"Do you think {subject} that {event} will happen {timeframe}?"

    return WorkflowQuestion(
        subject=subject,
        event=event,
        timeframe=timeframe,
        question=question,
        market_id=market.market_id,
        keywords=market.keywords,
    )


def format_market_snapshot(market: PolymarketMarket) -> str:
    hours = (
        f"{market.hours_to_resolution:.1f} hours"
        if market.hours_to_resolution is not None
        else "unknown"
    )
    lines = [
        f"Question: {market.question}",
        f"Category: {market.category.value}",
        f"Resolves in: {hours}",
    ]
    if market.outcomes:
        odds = ", ".join(f"{o.name} {o.price:.0%}" for o in market.outcomes)
        lines.append(f"Market odds: {odds}")
    if market.description:
        lines.append(f"Details: {market.description[:400]}")
    return "\n".join(lines)


def format_research_notes(contexts: list[ScrapedContext]) -> str:
    if not contexts:
        return "No external data — use market odds and question only."
    return "\n".join(f"- {ctx.source}: {ctx.summary}" for ctx in contexts)


def build_market_research_prompt(
    market: PolymarketMarket,
    contexts: list[ScrapedContext],
    *,
    workflow_question: str | None = None,
) -> str:
    """Single user message: one question, market facts, research, strict JSON answer."""
    question = workflow_question or build_simple_question(market)
    return f"""QUESTION (answer this only):
{question}

MARKET
{format_market_snapshot(market)}

RESEARCH
{format_research_notes(contexts)}

RULES
- Simple question, simple answer.
- decision must be exactly YES, NO, or SKIP (bet the market Yes/No side accordingly).
- answer = one short plain sentence (no markdown, no lists).
- reasoning = maximum two short sentences.
- SKIP if research is missing, conflicting, or no edge vs market odds.

Return only this JSON object, nothing else:
{{"decision":"YES"|"NO"|"SKIP","confidence":0.0-1.0,"answer":"one sentence","reasoning":"max two sentences"}}"""


def format_market_context(market: PolymarketMarket) -> str:
    return format_market_snapshot(market)


def format_scraped_context(contexts: list[ScrapedContext]) -> str:
    return format_research_notes(contexts)
