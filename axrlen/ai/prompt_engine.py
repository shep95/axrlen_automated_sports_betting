"""Workflow prompt engineering — simple question, simple answer."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from axrlen.models import PolymarketMarket, WorkflowQuestion


def _strip_question_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^(will|does|is|are|can|could|should)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.rstrip("?").strip()
    return cleaned


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


def build_workflow_question(market: PolymarketMarket) -> WorkflowQuestion:
    """
    Build the Axrlen workflow question:

    "Do you think [subject] that [event] will happen [timeframe]?"
    """
    event = _strip_question_prefix(market.question)
    subject = _extract_subject(market.keywords, market.question)
    timeframe = _timeframe_label(market)

    question = f"Do you think {subject} that {event} will happen {timeframe}?"

    return WorkflowQuestion(
        subject=subject,
        event=event,
        timeframe=timeframe,
        question=question,
        market_id=market.market_id,
        keywords=market.keywords,
    )


def format_market_context(market: PolymarketMarket) -> str:
    lines = [
        f"Market question: {market.question}",
        f"Category: {market.category.value}",
        f"Resolution window: {market.hours_to_resolution:.1f} hours"
        if market.hours_to_resolution is not None
        else "Resolution window: unknown",
    ]
    for outcome in market.outcomes:
        lines.append(f"  - {outcome.name}: {outcome.price:.2%} implied")
    if market.description:
        lines.append(f"Description: {market.description[:500]}")
    return "\n".join(lines)


def format_scraped_context(contexts: list) -> str:
    blocks = []
    for ctx in contexts:
        blocks.append(f"[{ctx.source}] {ctx.summary}")
    return "\n".join(blocks) if blocks else "No external data available."
