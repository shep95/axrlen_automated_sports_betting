"""Runtime configuration for Axrlen Polymarket bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAINS_DIR = PROJECT_ROOT / "brains"
DATA_DIR = PROJECT_ROOT / "data"
JOURNAL_PATH = DATA_DIR / "bet_journal.jsonl"
PAPER_BANKROLL_PATH = DATA_DIR / "paper_bankroll.json"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    live_trading: bool
    paper_trading: bool
    polymarket_private_key: str
    polymarket_funder_address: str
    polymarket_signature_type: int
    bet_size_usd: float
    paper_starting_capital: float
    paper_min_bet_usd: float
    paper_max_bet_usd: float
    paper_compound_threshold_usd: float
    paper_compound_pct: float
    min_confidence: float
    max_markets_per_cycle: int
    scan_interval_minutes: int
    resolution_window_hours: int
    market_categories: tuple[str, ...]
    health_port: int
    log_level: str
    tavily_api_key: str
    clob_api_key: str
    clob_api_secret: str
    clob_api_passphrase: str
    brains_dir: Path
    brains_max_chars: int
    max_ai_retries: int
    ai_timeout_seconds: float

    @property
    def is_live(self) -> bool:
        return self.live_trading and not self.paper_trading


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float, min_val: float, max_val: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not min_val <= value <= max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}")
    return value


def _env_int(name: str, default: int, min_val: int, max_val: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not min_val <= value <= max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}")
    return value


def load_settings() -> Settings:
    live = _env_bool("LIVE_TRADING", default=False)
    paper = _env_bool("PAPER_TRADING", default=True)

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise ValueError("OPENAI_API_KEY is required")

    if live:
        if not _env_bool("AXRLEN_CONFIRM_LIVE_RISK", default=False):
            raise ValueError(
                "LIVE_TRADING=true requires AXRLEN_CONFIRM_LIVE_RISK=true"
            )
        if not os.getenv("POLYMARKET_PRIVATE_KEY", "").strip():
            raise ValueError("POLYMARKET_PRIVATE_KEY is required for live trading")

    categories_raw = os.getenv("MARKET_CATEGORIES", "weather,crypto").strip()
    categories = tuple(c.strip().lower() for c in categories_raw.split(",") if c.strip())
    if not categories:
        categories = ("weather", "crypto")

    port_raw = os.getenv("PORT", "").strip()
    health_port = _env_int("PORT", 8080, 1, 65535) if port_raw else _env_int(
        "HEALTH_PORT", 8080, 1, 65535
    )

    brains_raw = os.getenv("BRAINS_DIR", "").strip()
    brains_dir = Path(brains_raw).expanduser().resolve() if brains_raw else BRAINS_DIR

    return Settings(
        openai_api_key=openai_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.2").strip() or "gpt-5.2",
        live_trading=live,
        paper_trading=paper if not live else False,
        polymarket_private_key=os.getenv("POLYMARKET_PRIVATE_KEY", "").strip(),
        polymarket_funder_address=os.getenv("POLYMARKET_FUNDER_ADDRESS", "").strip(),
        polymarket_signature_type=_env_int("POLYMARKET_SIGNATURE_TYPE", 3, 0, 3),
        bet_size_usd=_env_float("BET_SIZE_USD", 5.0, 1.0, 1000.0),
        paper_starting_capital=_env_float("PAPER_STARTING_CAPITAL", 100.0, 10.0, 100_000.0),
        paper_min_bet_usd=_env_float("PAPER_MIN_BET_USD", 5.0, 1.0, 1000.0),
        paper_max_bet_usd=_env_float("PAPER_MAX_BET_USD", 50.0, 1.0, 1000.0),
        paper_compound_threshold_usd=_env_float(
            "PAPER_COMPOUND_THRESHOLD_USD", 300.0, 50.0, 100_000.0
        ),
        paper_compound_pct=_env_float("PAPER_COMPOUND_PCT", 0.10, 0.01, 1.0),
        min_confidence=_env_float("MIN_CONFIDENCE", 0.65, 0.5, 0.99),
        max_markets_per_cycle=_env_int("MAX_MARKETS_PER_CYCLE", 3, 1, 20),
        scan_interval_minutes=_env_int("SCAN_INTERVAL_MINUTES", 7, 5, 10),
        resolution_window_hours=_env_int("RESOLUTION_WINDOW_HOURS", 24, 1, 168),
        market_categories=categories,
        health_port=health_port,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        clob_api_key=os.getenv("CLOB_API_KEY", "").strip(),
        clob_api_secret=os.getenv("CLOB_API_SECRET", "").strip(),
        clob_api_passphrase=os.getenv("CLOB_API_PASSPHRASE", "").strip(),
        brains_dir=brains_dir,
        brains_max_chars=_env_int("BRAINS_MAX_CHARS", 250_000, 50_000, 500_000),
        max_ai_retries=_env_int("MAX_AI_RETRIES", 3, 1, 5),
        ai_timeout_seconds=_env_float("AI_TIMEOUT_SECONDS", 60.0, 10.0, 180.0),
    )


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BRAINS_DIR.mkdir(parents=True, exist_ok=True)
