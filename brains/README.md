# Aureon Brains (imported corpus)

This folder contains the **full Aureon agent brain corpus** used by the betting AI.

## Structure

- `aureon/` — `.txt` / `.md` files copied from `Downloads/Aureon Files`
- `aureon/extracted/` — text extracted from Aureon PDFs (trading, sports, vedic, prompts)
- `BRAIN_MANIFEST.md` — Aureon manifest (priority reference)
- `axrlen_default_brain.txt` — Axrlen-specific betting rules

## Load priority

1. Hard constraints + anti-spiral protocol
2. Betting / trading (Ava Sports, Zophiel Trading, Nestal)
3. Prediction / vedic / analytics
4. Prompt engine + architecture
5. Philosophy, psychology, coding training

## Re-import

When you update brains locally:

```bash
python scripts/import_aureon_brains.py
```

Set `BRAINS_MAX_CHARS` in `.env` if you need more context in the AI prompt (default 250000).
