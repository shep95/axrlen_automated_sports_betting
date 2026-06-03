"""Market research prompts — clear brief for the AI."""

from __future__ import annotations

import re

from axrlen.models import PolymarketMarket, ScrapedContext, WorkflowQuestion


def _strip_question_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^(will|does|is|are|can|could|should)\s+", "", cleaned, flags=re.IGNORECASE)
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
        return "soon"
    if hours <= 24:
        return "tomorrow" if hours > 12 else "today"
    days = int(hours // 24)
    return f"within {days} day{'s' if days != 1 else ''}"


def build_workflow_question(market: PolymarketMarket, *, simple: bool = True) -> WorkflowQuestion:
    """Research question stored for logs and journal."""
    event = _strip_question_prefix(market.question)
    subject = _extract_subject(market.keywords, market.question)
    timeframe = _timeframe_label(market)

    if simple:
        question = market.question.strip()
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


def build_market_research_prompt(market: PolymarketMarket, contexts: list[ScrapedContext]) -> str:
    """Single user message: market + research + decision task."""
    return f"""MARKET
{format_market_snapshot(market)}

RESEARCH
{format_research_notes(contexts)}

TASK
Compare the research to the market odds. Is the market mispriced?
- YES = event is more likely than the price suggests
- NO = event is less likely than the price suggests
- SKIP = not enough data or no clear edge

Return only JSON:
{{"decision":"YES"|"NO"|"SKIP","confidence":0.0-1.0,"answer":"one sentence","reasoning":"max 2 sentences"}}"""


# Backward-compatible aliases
def format_market_context(market: PolymarketMarket) -> str:
    return format_market_snapshot(market)


def format_scraped_context(contexts: list[ScrapedContext]) -> str:
    return format_research_notes(contexts)
