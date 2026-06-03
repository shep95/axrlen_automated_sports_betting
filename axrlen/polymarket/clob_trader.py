"""Polymarket CLOB order placement (live + paper)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from axrlen.config import Settings
from axrlen.models import BetDecision, BetExecutionResult, PolymarketMarket

logger = logging.getLogger(__name__)

CLOB_BASE = "https://clob.polymarket.com"


class ClobTrader:
    """Place YES/NO bets on Polymarket."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_sdk_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from py_clob_client_v2 import ApiCreds, ClobClient
        except ImportError as exc:
            raise RuntimeError(
                "py-clob-client-v2 is required for live trading. "
                "Install with: pip install py-clob-client-v2"
            ) from exc

        creds = None
        if self._settings.clob_api_key:
            creds = ApiCreds(
                api_key=self._settings.clob_api_key,
                api_secret=self._settings.clob_api_secret,
                api_passphrase=self._settings.clob_api_passphrase,
            )

        client = ClobClient(
            host=CLOB_BASE,
            chain_id=137,
            key=self._settings.polymarket_private_key,
            creds=creds,
            signature_type=self._settings.polymarket_signature_type,
            funder=self._settings.polymarket_funder_address or None,
        )

        if creds is None:
            derived = client.create_or_derive_api_key()
            client = ClobClient(
                host=CLOB_BASE,
                chain_id=137,
                key=self._settings.polymarket_private_key,
                creds=derived,
                signature_type=self._settings.polymarket_signature_type,
                funder=self._settings.polymarket_funder_address or None,
            )

        self._client = client
        return client

    def get_midpoint_price(self, token_id: str) -> float | None:
        if not token_id:
            return None
        url = f"{CLOB_BASE}/midpoint"
        try:
            with httpx.Client(timeout=15.0) as http:
                response = http.get(url, params={"token_id": token_id})
                response.raise_for_status()
                data = response.json()
                return float(data.get("mid", 0))
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning("Midpoint fetch failed for %s: %s", token_id, exc)
            return None

    def execute_bet(
        self,
        market: PolymarketMarket,
        decision: BetDecision,
        *,
        correlation_id: str,
    ) -> BetExecutionResult:
        if decision == BetDecision.SKIP:
            return BetExecutionResult(
                market_id=market.market_id,
                side=decision,
                size_usd=0.0,
                price=0.0,
                success=False,
                paper=self._settings.paper_trading,
                message="Skipped by AI",
                correlation_id=correlation_id,
            )

        outcome = market.yes_outcome if decision == BetDecision.YES else market.no_outcome
        if outcome is None or not outcome.token_id:
            return BetExecutionResult(
                market_id=market.market_id,
                side=decision,
                size_usd=0.0,
                price=0.0,
                success=False,
                paper=self._settings.paper_trading,
                message="Missing outcome token",
                correlation_id=correlation_id,
            )

        price = self.get_midpoint_price(outcome.token_id) or outcome.price or 0.5
        price = max(0.01, min(0.99, price))
        size_usd = self._settings.bet_size_usd

        if self._settings.paper_trading or not self._settings.is_live:
            logger.info(
                "[PAPER] %s %s @ %.3f for $%.2f on %s",
                decision.value,
                outcome.name,
                price,
                size_usd,
                market.question[:80],
            )
            return BetExecutionResult(
                market_id=market.market_id,
                side=decision,
                size_usd=size_usd,
                price=price,
                success=True,
                paper=True,
                message="Paper trade logged",
                correlation_id=correlation_id,
            )

        try:
            from py_clob_client_v2 import OrderArgs, OrderType, PartialCreateOrderOptions, Side

            client = self._get_sdk_client()
            shares = size_usd / price
            order = client.create_and_post_order(
                order_args=OrderArgs(
                    token_id=outcome.token_id,
                    price=round(price, 2),
                    side=Side.BUY,
                    size=round(shares, 2),
                ),
                options=PartialCreateOrderOptions(tick_size="0.01"),
                order_type=OrderType.GTC,
            )
            order_id = str(order.get("orderID") or order.get("id") or "")
            return BetExecutionResult(
                market_id=market.market_id,
                side=decision,
                size_usd=size_usd,
                price=price,
                success=True,
                order_id=order_id,
                paper=False,
                message="Live order placed",
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.exception("Live order failed: %s", exc)
            return BetExecutionResult(
                market_id=market.market_id,
                side=decision,
                size_usd=size_usd,
                price=price,
                success=False,
                paper=False,
                message=str(exc),
                correlation_id=correlation_id,
            )
