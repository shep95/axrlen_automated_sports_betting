"""Pydantic models for the Axrlen Polymarket workflow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MarketCategory(str, Enum):
    WEATHER = "weather"
    CRYPTO = "crypto"
    SPORTS = "sports"
    POLITICS = "politics"
    OTHER = "other"


class PolymarketOutcome(BaseModel):
    name: str
    price: float
    token_id: str = ""


class PolymarketMarket(BaseModel):
    market_id: str
    event_id: str = ""
    question: str
    description: str = ""
    slug: str = ""
    end_date: datetime | None = None
    category: MarketCategory = MarketCategory.OTHER
    keywords: list[str] = Field(default_factory=list)
    outcomes: list[PolymarketOutcome] = Field(default_factory=list)
    volume: float = 0.0
    liquidity: float = 0.0
    enable_order_book: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def hours_to_resolution(self) -> float | None:
        if self.end_date is None:
            return None
        delta = self.end_date - datetime.now(tz=self.end_date.tzinfo)
        return max(delta.total_seconds() / 3600.0, 0.0)

    @property
    def yes_outcome(self) -> PolymarketOutcome | None:
        for outcome in self.outcomes:
            if outcome.name.lower() in ("yes", "true"):
                return outcome
        return self.outcomes[0] if self.outcomes else None

    @property
    def no_outcome(self) -> PolymarketOutcome | None:
        for outcome in self.outcomes:
            if outcome.name.lower() in ("no", "false"):
                return outcome
        return self.outcomes[1] if len(self.outcomes) > 1 else None


class ScrapedContext(BaseModel):
    source: str
    summary: str
    url: str = ""
    fetched_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class WorkflowQuestion(BaseModel):
    subject: str
    event: str
    timeframe: str
    question: str
    market_id: str
    keywords: list[str] = Field(default_factory=list)


class BetDecision(str, Enum):
    YES = "YES"
    NO = "NO"
    SKIP = "SKIP"


class AIVerdict(BaseModel):
    decision: BetDecision
    confidence: float = Field(ge=0.0, le=1.0)
    answer: str
    reasoning: str = ""
    workflow_question: WorkflowQuestion
    correlation_id: str

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class BetExecutionResult(BaseModel):
    market_id: str
    side: BetDecision
    size_usd: float
    price: float
    success: bool
    order_id: str = ""
    paper: bool = True
    message: str = ""
    correlation_id: str = ""
    bankroll: dict[str, float | int | bool | str] | None = None
