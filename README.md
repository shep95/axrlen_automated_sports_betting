# Axrlen Automated Sports Betting (Polymarket Bot)

Automated Polymarket betting bot that scans near-resolution markets, scrapes relevant web data, asks a **simple workflow question**, gets a **simple AI answer**, and places the bet.

Hosted target: [Railway](https://railway.app)  
Repository: [shep95/axrlen_automated_sports_betting](https://github.com/shep95/axrlen_automated_sports_betting)

## Workflow Logic

```
Polymarket scan → filter (24h window) → web scrape → workflow question → AI (brains) → bet
```

Every market is evaluated with this prompt pattern:

> **Do you think `[subject]` that `[event]` will happen `[timeframe]`?**

- **subject** — keywords extracted from the bet (e.g. `nyc / temperature / 85f`)
- **event** — the market question stripped to its core claim
- **timeframe** — `today`, `tomorrow`, or `within N days` based on resolution time

The AI responds with **YES**, **NO**, or **SKIP** (simple question → simple answer), using your brain files plus scraped context.

## What it scans

Default categories: **weather** and **crypto** (configurable).

- Markets resolving within **24 hours** (configurable)
- Runs every **5–10 minutes** (default: 7 min)
- Picks the highest-scored markets per cycle (liquidity, urgency, consensus)

## Data sources

| Category | Source |
|----------|--------|
| Weather | [Open-Meteo](https://open-meteo.com/) forecast API |
| Crypto | [CoinGecko](https://www.coingecko.com/) spot + 24h change |
| General | [Tavily](https://tavily.com/) search (optional API key) |

## Brains (Aureon corpus)

The bot loads the **full Aureon agent brain corpus** you trained on. Brains live in `brains/`:

| Path | Contents |
|------|----------|
| `brains/aureon/` | All `.txt`/`.md` files copied from your Aureon Files folder |
| `brains/aureon/extracted/` | Text extracted from Aureon PDFs (sports, trading, vedic, prompt engineering) |
| `brains/BRAIN_MANIFEST.md` | Aureon manifest (load priority reference) |
| `brains/axrlen_default_brain.txt` | Axrlen betting-specific rules |

Load order follows **Aureon manifest priority**: hard constraints → betting/trading → prediction → prompt engine → rest.

Re-import after updating your local Aureon Files:

```bash
python scripts/import_aureon_brains.py
# or from a custom path:
python scripts/import_aureon_brains.py "D:/path/to/Aureon Files"
```

Tune token budget with `BRAINS_MAX_CHARS` (default `250000`).

## Quick start (local)

```bash
cd axrlen_automated_sports_betting
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # add OPENAI_API_KEY
python main.py
```

**Paper trading is on by default** — no real orders until you explicitly enable live mode.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o-mini` | AI model |
| `PAPER_TRADING` | `true` | Log bets without placing |
| `LIVE_TRADING` | `false` | Real Polymarket orders |
| `AXRLEN_CONFIRM_LIVE_RISK` | `false` | Must be `true` for live |
| `POLYMARKET_PRIVATE_KEY` | — | Wallet key (live only) |
| `POLYMARKET_FUNDER_ADDRESS` | — | Polymarket deposit address |
| `BET_SIZE_USD` | `5` | Size per bet |
| `MIN_CONFIDENCE` | `0.65` | Min AI confidence to bet |
| `SCAN_INTERVAL_MINUTES` | `7` | Cycle interval (5–10 recommended) |
| `RESOLUTION_WINDOW_HOURS` | `24` | Only markets ending within this window |
| `MARKET_CATEGORIES` | `weather,crypto` | Comma-separated categories |
| `TAVILY_API_KEY` | — | Optional web search |
| `BRAINS_DIR` | `./brains` | Brains path (includes Aureon corpus) |
| `BRAINS_MAX_CHARS` | `250000` | Max chars loaded into AI system prompt |

## Railway deploy

1. Create a new Railway project from this repo.
2. Set `OPENAI_API_KEY` (and optional keys) in Railway variables.
3. Railway uses `railway.toml` + `Dockerfile`; health check at `/health`.
4. Keep `PAPER_TRADING=true` until you have tested end-to-end.

## Live trading checklist

1. Fund your Polymarket wallet on Polygon.
2. Set `POLYMARKET_PRIVATE_KEY` and `POLYMARKET_FUNDER_ADDRESS`.
3. Set `LIVE_TRADING=true`, `PAPER_TRADING=false`, `AXRLEN_CONFIRM_LIVE_RISK=true`.
4. Install `py-clob-client-v2` (included in requirements).

See [Polymarket CLOB docs](https://docs.polymarket.com/trading/overview).

## Project structure

```
axrlen/
  polymarket/     # Gamma API + CLOB trader
  scanner/        # 24h market filter
  scraper/        # Weather, crypto, Tavily
  ai/             # Brains loader, prompt engine, decision gateway
  workflow/       # End-to-end pipeline
brains/           # Your AI brain files
main.py           # Scheduler + health server
```

## Tests

```bash
pytest tests/ -q
```

## Disclaimer

This software is for educational purposes. Prediction market trading involves financial risk. You are responsible for compliance with local laws and platform terms of service.
