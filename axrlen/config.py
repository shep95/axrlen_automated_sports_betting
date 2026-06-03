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
    ai_research_simple: bool
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


def _env_str(*names: str, default: str = "") -> str:
    """Read the first set environment variable from a list of aliases."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _env_bool_aliases(*names: str, default: bool = False) -> bool:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip().lower() in ("1", "true", "yes", "on")
    return default


def _env_float_aliases(
    names: tuple[str, ...],
    default: float,
    min_val: float,
    max_val: float,
) -> float:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return _env_float(name, default, min_val, max_val)
    return default


def _env_int_aliases(
    names: tuple[str, ...],
    default: int,
    min_val: int,
    max_val: int,
) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return _env_int(name, default, min_val, max_val)
    return default


def load_settings() -> Settings:
    # --- Polymarket CLOB (order placement) ---
    live = _env_bool_aliases(
        "POLYMARKET_CLOB_LIVE_TRADING",
        "LIVE_TRADING",
        default=False,
    )
    paper = _env_bool_aliases(
        "POLYMARKET_CLOB_PAPER_TRADING",
        "PAPER_TRADING",
        default=True,
    )

    openai_key = _env_str("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY is required")

    if live:
        if not _env_bool_aliases(
            "POLYMARKET_CLOB_CONFIRM_LIVE_RISK",
            "AXRLEN_CONFIRM_LIVE_RISK",
            default=False,
        ):
            raise ValueError(
                "Live CLOB trading requires POLYMARKET_CLOB_CONFIRM_LIVE_RISK=true "
                "(you accept real-money risk)"
            )
        signer_key = _env_str("POLYMARKET_SIGNER_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY")
        if not signer_key:
            raise ValueError(
                "POLYMARKET_SIGNER_PRIVATE_KEY is required for live CLOB trading "
                "(wallet that signs orders — ClobClient `key`)"
            )

    categories_raw = _env_str(
        "POLYMARKET_GAMMA_MARKET_CATEGORIES",
        "MARKET_CATEGORIES",
        default="weather,crypto",
    )
    categories = tuple(c.strip().lower() for c in categories_raw.split(",") if c.strip())
    if not categories:
        categories = ("weather", "crypto")

    port_raw = os.getenv("PORT", "").strip()
    health_port = _env_int("PORT", 8080, 1, 65535) if port_raw else _env_int_aliases(
        ("AXRLEN_HEALTH_PORT", "HEALTH_PORT"),
        8080,
        1,
        65535,
    )

    brains_raw = _env_str("AXRLEN_BRAINS_DIR", "BRAINS_DIR")
    brains_dir = Path(brains_raw).expanduser().resolve() if brains_raw else BRAINS_DIR

    return Settings(
        openai_api_key=openai_key,
        openai_model=_env_str("OPENAI_MODEL", default="gpt-5.2-chat-latest")
        or "gpt-5.2-chat-latest",
        live_trading=live,
        paper_trading=paper if not live else False,
        polymarket_private_key=_env_str(
            "POLYMARKET_SIGNER_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY"
        ),
        polymarket_funder_address=_env_str("POLYMARKET_FUNDER_ADDRESS"),
        polymarket_signature_type=_env_int_aliases(
            ("POLYMARKET_SIGNATURE_TYPE",),
            3,
            0,
            3,
        ),
        bet_size_usd=_env_float_aliases(
            ("POLYMARKET_CLOB_ORDER_SIZE_USD", "BET_SIZE_USD"),
            5.0,
            1.0,
            1000.0,
        ),
        paper_starting_capital=_env_float_aliases(
            ("AXRLEN_PAPER_STARTING_CAPITAL_USD", "PAPER_STARTING_CAPITAL"),
            100.0,
            10.0,
            100_000.0,
        ),
        paper_min_bet_usd=_env_float_aliases(
            ("AXRLEN_PAPER_MIN_ORDER_USD", "PAPER_MIN_BET_USD"),
            5.0,
            1.0,
            1000.0,
        ),
        paper_max_bet_usd=_env_float_aliases(
            ("AXRLEN_PAPER_MAX_ORDER_USD", "PAPER_MAX_BET_USD"),
            50.0,
            1.0,
            1000.0,
        ),
        paper_compound_threshold_usd=_env_float_aliases(
            ("AXRLEN_PAPER_COMPOUND_AT_CAPITAL_USD", "PAPER_COMPOUND_THRESHOLD_USD"),
            300.0,
            50.0,
            100_000.0,
        ),
        paper_compound_pct=_env_float_aliases(
            ("AXRLEN_PAPER_COMPOUND_PERCENT", "PAPER_COMPOUND_PCT"),
            0.10,
            0.01,
            1.0,
        ),
        min_confidence=_env_float_aliases(
            ("AXRLEN_AI_MIN_CONFIDENCE", "MIN_CONFIDENCE"),
            0.65,
            0.5,
            0.99,
        ),
        max_markets_per_cycle=_env_int_aliases(
            ("POLYMARKET_GAMMA_MAX_MARKETS_PER_SCAN", "MAX_MARKETS_PER_CYCLE"),
            3,
            1,
            20,
        ),
        scan_interval_minutes=_env_int_aliases(
            ("AXRLEN_SCAN_INTERVAL_MINUTES", "SCAN_INTERVAL_MINUTES"),
            7,
            5,
            10,
        ),
        resolution_window_hours=_env_int_aliases(
            ("POLYMARKET_GAMMA_RESOLUTION_HOURS", "RESOLUTION_WINDOW_HOURS"),
            24,
            1,
            168,
        ),
        market_categories=categories,
        health_port=health_port,
        log_level=_env_str("AXRLEN_LOG_LEVEL", "LOG_LEVEL", default="INFO").upper(),
        tavily_api_key=_env_str("TAVILY_API_KEY"),
        clob_api_key=_env_str("POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY"),
        clob_api_secret=_env_str("POLYMARKET_CLOB_API_SECRET", "CLOB_API_SECRET"),
        clob_api_passphrase=_env_str(
            "POLYMARKET_CLOB_API_PASSPHRASE", "CLOB_API_PASSPHRASE"
        ),
        brains_dir=brains_dir,
        brains_max_chars=_env_int_aliases(
            ("AXRLEN_BRAINS_MAX_CHARS", "BRAINS_MAX_CHARS"),
            250_000,
            50_000,
            500_000,
        ),
        ai_research_simple=_env_bool_aliases(
            "AXRLEN_AI_RESEARCH_SIMPLE",
            "AI_RESEARCH_SIMPLE",
            default=True,
        ),
        max_ai_retries=_env_int_aliases(
            ("AXRLEN_AI_MAX_RETRIES", "MAX_AI_RETRIES"),
            3,
            1,
            5,
        ),
        ai_timeout_seconds=_env_float_aliases(
            ("AXRLEN_AI_TIMEOUT_SECONDS", "AI_TIMEOUT_SECONDS"),
            60.0,
            10.0,
            180.0,
        ),
    )


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BRAINS_DIR.mkdir(parents=True, exist_ok=True)
