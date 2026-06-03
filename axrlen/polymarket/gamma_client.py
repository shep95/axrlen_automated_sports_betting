"""Polymarket Gamma API client for market discovery."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from axrlen.models import MarketCategory, PolymarketMarket, PolymarketOutcome

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

CATEGORY_KEYWORDS: dict[MarketCategory, tuple[str, ...]] = {
    MarketCategory.WEATHER: (
        "weather",
        "temperature",
        "rain",
        "snow",
        "hurricane",
        "celsius",
        "fahrenheit",
        "heat",
        "cold",
        "storm",
        "forecast",
    ),
    MarketCategory.CRYPTO: (
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "crypto",
        "solana",
        "sol",
        "token",
        "blockchain",
        "defi",
    ),
    MarketCategory.SPORTS: (
        "nba",
        "nfl",
        "mlb",
        "soccer",
        "football",
        "basketball",
        "tennis",
        "ufc",
        "game",
        "match",
        "championship",
    ),
    MarketCategory.POLITICS: (
        "election",
        "president",
        "congress",
        "senate",
        "vote",
        "trump",
        "biden",
    ),
}


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _parse_end_date(raw: dict[str, Any]) -> datetime | None:
    for key in ("endDate", "end_date_iso", "umaEndDate", "closedTime"):
        value = raw.get(key)
        if not value:
            continue
        try:
            text = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError):
            continue
    return None


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9$%]+", text.lower())
    stop = {"will", "the", "be", "a", "an", "on", "in", "at", "to", "of", "by", "for", "and", "or"}
    return [t for t in tokens if len(t) > 2 and t not in stop][:12]


def classify_market(question: str, description: str = "") -> MarketCategory:
    blob = f"{question} {description}".lower()
    scores: dict[MarketCategory, int] = {cat: 0 for cat in MarketCategory}
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in blob:
                scores[category] += 1
    best = max(scores.items(), key=lambda item: item[1])
    if best[1] == 0:
        return MarketCategory.OTHER
    return best[0]


def _market_from_gamma(raw: dict[str, Any]) -> PolymarketMarket | None:
    question = str(raw.get("question") or raw.get("title") or "").strip()
    if not question:
        return None

    outcomes_raw = _parse_json_field(raw.get("outcomes", "[]"))
    prices_raw = _parse_json_field(raw.get("outcomePrices", "[]"))
    token_ids_raw = _parse_json_field(raw.get("clobTokenIds", "[]"))

    outcomes: list[PolymarketOutcome] = []
    if isinstance(outcomes_raw, list):
        for idx, name in enumerate(outcomes_raw):
            price = 0.0
            if isinstance(prices_raw, list) and idx < len(prices_raw):
                try:
                    price = float(prices_raw[idx])
                except (TypeError, ValueError):
                    price = 0.0
            token_id = ""
            if isinstance(token_ids_raw, list) and idx < len(token_ids_raw):
                token_id = str(token_ids_raw[idx])
            outcomes.append(PolymarketOutcome(name=str(name), price=price, token_id=token_id))

    description = str(raw.get("description") or "")
    category = classify_market(question, description)

    try:
        volume = float(raw.get("volumeNum") or raw.get("volume") or 0)
    except (TypeError, ValueError):
        volume = 0.0
    try:
        liquidity = float(raw.get("liquidityNum") or raw.get("liquidity") or 0)
    except (TypeError, ValueError):
        liquidity = 0.0

    return PolymarketMarket(
        market_id=str(raw.get("id") or raw.get("conditionId") or ""),
        event_id=str(raw.get("eventId") or raw.get("event_id") or ""),
        question=question,
        description=description,
        slug=str(raw.get("slug") or ""),
        end_date=_parse_end_date(raw),
        category=category,
        keywords=_extract_keywords(question),
        outcomes=outcomes,
        volume=volume,
        liquidity=liquidity,
        enable_order_book=bool(raw.get("enableOrderBook", True)),
        raw=raw,
    )


class GammaClient:
    """Fetch and filter Polymarket markets via the public Gamma API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def fetch_markets(
        self,
        *,
        limit: int = 100,
        active: bool = True,
        closed: bool = False,
        tag_slug: str | None = None,
    ) -> list[PolymarketMarket]:
        params: dict[str, Any] = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": "endDate",
            "ascending": "true",
        }
        if tag_slug:
            params["tag_slug"] = tag_slug

        url = f"{GAMMA_BASE}/markets"
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            logger.warning("Unexpected Gamma response shape: %s", type(payload))
            return []

        markets: list[PolymarketMarket] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            market = _market_from_gamma(item)
            if market and market.market_id:
                markets.append(market)
        return markets

    def search_markets(self, query: str, limit: int = 20) -> list[PolymarketMarket]:
        url = f"{GAMMA_BASE}/public-search"
        params = {"q": query, "limit": limit}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        markets: list[PolymarketMarket] = []
        events = payload.get("events", []) if isinstance(payload, dict) else []
        for event in events:
            if not isinstance(event, dict):
                continue
            for raw in event.get("markets", []) or []:
                if isinstance(raw, dict):
                    market = _market_from_gamma(raw)
                    if market and market.market_id:
                        markets.append(market)
        return markets
