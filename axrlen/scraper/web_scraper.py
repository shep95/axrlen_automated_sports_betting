"""Web and API data gathering for market context."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from axrlen.config import Settings
from axrlen.models import MarketCategory, PolymarketMarket, ScrapedContext
from axrlen.scanner.btc_updown import is_btc_up_or_down_5min

logger = logging.getLogger(__name__)

CITY_COORDS: dict[str, tuple[float, float]] = {
    "nyc": (40.7128, -74.0060),
    "new york": (40.7128, -74.0060),
    "london": (51.5074, -0.1278),
    "chicago": (41.8781, -87.6298),
    "miami": (25.7617, -80.1918),
    "los angeles": (34.0522, -118.2437),
    "la": (34.0522, -118.2437),
    "dallas": (32.7767, -96.7970),
    "houston": (29.7604, -95.3698),
    "denver": (39.7392, -104.9903),
    "seattle": (47.6062, -122.3321),
    "boston": (42.3601, -71.0589),
    "atlanta": (33.7490, -84.3880),
}

CRYPTO_IDS: dict[str, str] = {
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "solana": "solana",
    "sol": "solana",
}


def _detect_city(text: str) -> tuple[float, float] | None:
    lower = text.lower()
    for name, coords in CITY_COORDS.items():
        if name in lower:
            return coords
    return None


def _detect_crypto(text: str) -> str | None:
    lower = text.lower()
    for token, coin_id in CRYPTO_IDS.items():
        if re.search(rf"\b{re.escape(token)}\b", lower):
            return coin_id
    return None


class ContextScraper:
    """Gather niche external data related to a Polymarket bet."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _fetch_weather(self, market: PolymarketMarket) -> ScrapedContext | None:
        coords = _detect_city(market.question + " " + market.description)
        if coords is None:
            coords = (40.7128, -74.0060)

        lat, lon = coords
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "hourly": "temperature_2m,precipitation",
            "timezone": "auto",
            "forecast_days": 2,
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Weather fetch failed: %s", exc)
            return None

        daily = data.get("daily", {})
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        dates = daily.get("time", [])

        summary_parts = []
        for idx, date in enumerate(dates[:2]):
            tmax = temps_max[idx] if idx < len(temps_max) else "?"
            tmin = temps_min[idx] if idx < len(temps_min) else "?"
            rain = precip[idx] if idx < len(precip) else "?"
            summary_parts.append(f"{date}: high {tmax}C, low {tmin}C, precip {rain}mm")

        return ScrapedContext(
            source="open-meteo",
            summary="Weather forecast — " + "; ".join(summary_parts),
            url=url,
        )

    def _fetch_crypto(self, market: PolymarketMarket) -> ScrapedContext | None:
        coin_id = _detect_crypto(market.question + " " + market.description)
        if coin_id is None:
            coin_id = "bitcoin"

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Crypto fetch failed: %s", exc)
            return None

        coin = data.get(coin_id, {})
        price = coin.get("usd", "?")
        change = coin.get("usd_24h_change", "?")
        updated = coin.get("last_updated_at", "")

        return ScrapedContext(
            source="coingecko",
            summary=f"{coin_id.upper()} price ${price}, 24h change {change}%, updated {updated}",
            url="https://www.coingecko.com",
        )

    def _fetch_tavily(self, market: PolymarketMarket) -> ScrapedContext | None:
        if not self._settings.tavily_api_key:
            return None

        query = f"{market.question} latest news data"
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self._settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
        }
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Tavily search failed: %s", exc)
            return None

        snippets = []
        for result in data.get("results", [])[:5]:
            content = str(result.get("content", "")).strip()
            if content:
                snippets.append(content[:300])

        if not snippets:
            return None

        return ScrapedContext(
            source="tavily",
            summary=" | ".join(snippets),
            url=str(data.get("results", [{}])[0].get("url", "")),
        )

    def scrape(self, market: PolymarketMarket) -> list[ScrapedContext]:
        contexts: list[ScrapedContext] = []

        if is_btc_up_or_down_5min(market) or market.category == MarketCategory.CRYPTO:
            crypto = self._fetch_crypto(market)
            if crypto:
                contexts.append(crypto)
        elif market.category == MarketCategory.WEATHER:
            weather = self._fetch_weather(market)
            if weather:
                contexts.append(weather)

        tavily = self._fetch_tavily(market)
        if tavily:
            contexts.append(tavily)

        if not contexts:
            contexts.append(
                ScrapedContext(
                    source="market-only",
                    summary=f"No external data fetched. Market: {market.question}",
                    fetched_at=datetime.now(timezone.utc),
                )
            )

        logger.info("Scraped %d context sources for market %s", len(contexts), market.market_id)
        return contexts
