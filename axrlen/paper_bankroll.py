"""Paper trading bankroll with compounding bet sizes and settlement tracking."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from axrlen.config import Settings
from axrlen.models import BetDecision, PolymarketMarket
from axrlen.polymarket.gamma_client import GammaClient

logger = logging.getLogger(__name__)

_LOG_PREFIX = "[PAPER-BANKROLL]"


@dataclass
class OpenPaperPosition:
    position_id: str
    correlation_id: str
    market_id: str
    question: str
    side: str
    stake_usd: float
    entry_price: float
    shares: float
    placed_at: str
    end_date: str | None = None


@dataclass
class PaperBankrollState:
    starting_capital: float
    capital: float
    min_bet_usd: float
    max_bet_usd: float
    compound_threshold_usd: float
    compound_pct: float
    wins: int = 0
    losses: int = 0
    total_profit: float = 0.0
    total_wagered: float = 0.0
    bets_placed: int = 0
    open_positions: list[OpenPaperPosition] = field(default_factory=list)

    @property
    def locked_capital(self) -> float:
        return sum(p.stake_usd for p in self.open_positions)

    @property
    def equity(self) -> float:
        return self.capital + self.locked_capital

    @property
    def net_profit(self) -> float:
        return self.capital + self.locked_capital - self.starting_capital


def compute_paper_bet_size(
    capital: float,
    *,
    min_bet: float,
    max_bet: float,
    compound_threshold: float,
    compound_pct: float,
) -> float:
    """Return stake in USD, or 0 if capital cannot cover minimum bet."""
    if capital < min_bet:
        return 0.0
    if capital < compound_threshold:
        return round(min(min_bet, capital), 2)
    sized = capital * compound_pct
    return round(min(max_bet, max(min_bet, sized)), 2)


def _parse_winning_outcome(raw: dict[str, Any]) -> str | None:
    import json as json_mod

    outcomes_raw = raw.get("outcomes", "[]")
    prices_raw = raw.get("outcomePrices", "[]")
    if isinstance(outcomes_raw, str):
        try:
            outcomes_raw = json_mod.loads(outcomes_raw)
        except json_mod.JSONDecodeError:
            return None
    if isinstance(prices_raw, str):
        try:
            prices_raw = json_mod.loads(prices_raw)
        except json_mod.JSONDecodeError:
            return None
    if not isinstance(outcomes_raw, list) or not isinstance(prices_raw, list):
        return None

    for idx, name in enumerate(outcomes_raw):
        if idx >= len(prices_raw):
            break
        try:
            price = float(prices_raw[idx])
        except (TypeError, ValueError):
            continue
        if price >= 0.99:
            return str(name)
    return None


def _is_market_resolved(raw: dict[str, Any]) -> bool:
    if raw.get("closed") or raw.get("resolved"):
        return True
    return _parse_winning_outcome(raw) is not None


def _side_wins(bet_side: BetDecision, winning_name: str) -> bool:
    win_lower = winning_name.strip().lower()
    if bet_side == BetDecision.YES:
        return win_lower in ("yes", "true")
    if bet_side == BetDecision.NO:
        return win_lower in ("no", "false")
    return False


class PaperBankroll:
    """Manages paper capital, bet sizing, positions, and structured logs."""

    def __init__(self, settings: Settings, state_path: Path, gamma: GammaClient | None = None) -> None:
        self._settings = settings
        self._path = state_path
        self._gamma = gamma or GammaClient()
        self._lock = threading.Lock()
        self._state = self._load()

    def _load(self) -> PaperBankrollState:
        defaults = PaperBankrollState(
            starting_capital=self._settings.paper_starting_capital,
            capital=self._settings.paper_starting_capital,
            min_bet_usd=self._settings.paper_min_bet_usd,
            max_bet_usd=self._settings.paper_max_bet_usd,
            compound_threshold_usd=self._settings.paper_compound_threshold_usd,
            compound_pct=self._settings.paper_compound_pct,
        )
        if not self._path.exists():
            return defaults

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            positions = [
                OpenPaperPosition(**item)
                for item in raw.get("open_positions", [])
                if isinstance(item, dict)
            ]
            return PaperBankrollState(
                starting_capital=float(raw.get("starting_capital", defaults.starting_capital)),
                capital=float(raw.get("capital", defaults.capital)),
                min_bet_usd=float(raw.get("min_bet_usd", defaults.min_bet_usd)),
                max_bet_usd=float(raw.get("max_bet_usd", defaults.max_bet_usd)),
                compound_threshold_usd=float(
                    raw.get("compound_threshold_usd", defaults.compound_threshold_usd)
                ),
                compound_pct=float(raw.get("compound_pct", defaults.compound_pct)),
                wins=int(raw.get("wins", 0)),
                losses=int(raw.get("losses", 0)),
                total_profit=float(raw.get("total_profit", 0.0)),
                total_wagered=float(raw.get("total_wagered", 0.0)),
                bets_placed=int(raw.get("bets_placed", 0)),
                open_positions=positions,
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            logger.warning("%s Could not load state (%s) — resetting", _LOG_PREFIX, exc)
            return defaults

    def _save(self) -> None:
        payload = asdict(self._state)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "starting_capital": round(self._state.starting_capital, 2),
                "capital": round(self._state.capital, 2),
                "locked_capital": round(self._state.locked_capital, 2),
                "equity": round(self._state.equity, 2),
                "net_profit": round(self._state.net_profit, 2),
                "total_profit": round(self._state.total_profit, 2),
                "wins": self._state.wins,
                "losses": self._state.losses,
                "bets_placed": self._state.bets_placed,
                "open_positions": len(self._state.open_positions),
            }

    def open_market_ids(self) -> set[str]:
        with self._lock:
            return {p.market_id for p in self._state.open_positions if p.market_id}

    def has_open_position(self, market_id: str) -> bool:
        if not market_id:
            return False
        with self._lock:
            return any(p.market_id == market_id for p in self._state.open_positions)

    def log_summary(self, *, context: str = "SUMMARY") -> None:
        snap = self.snapshot()
        logger.info(
            "%s %s | capital=$%.2f | starting=$%.2f | profit=$%+.2f | "
            "wins=%d | losses=%d | bets=%d | open=%d | locked=$%.2f | equity=$%.2f",
            _LOG_PREFIX,
            context,
            snap["capital"],
            snap["starting_capital"],
            snap["net_profit"],
            snap["wins"],
            snap["losses"],
            snap["bets_placed"],
            snap["open_positions"],
            snap["locked_capital"],
            snap["equity"],
        )

    def settle_open_positions(self) -> int:
        """Resolve closed markets and return count of positions settled."""
        settled = 0
        with self._lock:
            remaining: list[OpenPaperPosition] = []
            for position in self._state.open_positions:
                raw = self._gamma.fetch_market_raw(position.market_id)
                if raw is None or not _is_market_resolved(raw):
                    remaining.append(position)
                    continue

                winner = _parse_winning_outcome(raw)
                if winner is None:
                    remaining.append(position)
                    continue

                side = BetDecision(position.side)
                won = _side_wins(side, winner)
                if won:
                    payout = position.shares * 1.0
                    pnl = payout - position.stake_usd
                    self._state.capital += payout
                    self._state.wins += 1
                    result = "WIN"
                else:
                    pnl = -position.stake_usd
                    self._state.losses += 1
                    result = "LOSS"

                self._state.total_profit += pnl
                settled += 1
                logger.info(
                    "%s SETTLED | %s | %s %s | stake=$%.2f | pnl=$%+.2f | "
                    "winner=%s | capital=$%.2f | profit=$%+.2f | wins=%d | losses=%d",
                    _LOG_PREFIX,
                    result,
                    position.side,
                    position.question[:60],
                    position.stake_usd,
                    pnl,
                    winner,
                    self._state.capital,
                    self._state.net_profit,
                    self._state.wins,
                    self._state.losses,
                )

            self._state.open_positions = remaining
            if settled:
                self._save()
        return settled

    def place_bet(
        self,
        market: PolymarketMarket,
        decision: BetDecision,
        *,
        price: float,
        correlation_id: str,
    ) -> tuple[float, dict[str, Any]]:
        """
        Lock stake and open a paper position.
        Returns (stake_usd, bankroll_snapshot_dict).
        """
        with self._lock:
            stake = compute_paper_bet_size(
                self._state.capital,
                min_bet=self._state.min_bet_usd,
                max_bet=self._state.max_bet_usd,
                compound_threshold=self._state.compound_threshold_usd,
                compound_pct=self._state.compound_pct,
            )
            snap = self.snapshot()

            if stake <= 0:
                logger.warning(
                    "%s BET REJECTED | insufficient capital=$%.2f (min bet=$%.2f) | %s",
                    _LOG_PREFIX,
                    self._state.capital,
                    self._state.min_bet_usd,
                    market.question[:80],
                )
                return 0.0, {**snap, "rejected": True, "reason": "insufficient_capital"}

            if any(p.market_id == market.market_id for p in self._state.open_positions):
                logger.info(
                    "%s BET REJECTED | already in open trade | market_id=%s | %s",
                    _LOG_PREFIX,
                    market.market_id,
                    market.question[:80],
                )
                return 0.0, {**snap, "rejected": True, "reason": "open_position_exists"}

            shares = stake / price
            position_id = f"{market.market_id}:{correlation_id}"
            end_iso = market.end_date.isoformat() if market.end_date else None

            self._state.capital -= stake
            self._state.total_wagered += stake
            self._state.bets_placed += 1
            self._state.open_positions.append(
                OpenPaperPosition(
                    position_id=position_id,
                    correlation_id=correlation_id,
                    market_id=market.market_id,
                    question=market.question,
                    side=decision.value,
                    stake_usd=stake,
                    entry_price=price,
                    shares=shares,
                    placed_at=datetime.now(timezone.utc).isoformat(),
                    end_date=end_iso,
                )
            )
            self._save()
            snap = self.snapshot()

        logger.info(
            "%s BET | %s | stake=$%.2f | price=%.3f | shares=%.4f | "
            "market=%s | capital=$%.2f | starting=$%.2f | profit=$%+.2f | "
            "wins=%d | losses=%d | bets=%d | open=%d",
            _LOG_PREFIX,
            decision.value,
            stake,
            price,
            shares,
            market.question[:80],
            snap["capital"],
            snap["starting_capital"],
            snap["net_profit"],
            snap["wins"],
            snap["losses"],
            snap["bets_placed"],
            snap["open_positions"],
        )
        self.log_summary(context="AFTER-BET")
        return stake, snap
