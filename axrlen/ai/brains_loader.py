"""Load user-provided brain files into the AI system prompt."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_BRAIN = """
You are Axrlen, an automated Polymarket decision agent.

Rules:
- Simple question, simple answer.
- Use ONLY the provided market data and scraped context.
- Answer YES if evidence supports the event happening within the stated timeframe.
- Answer NO if evidence suggests it will not happen.
- Answer SKIP if data is insufficient or ambiguous.
- Be calibrated: high confidence only when evidence is strong.
""".strip()


def load_brains(brains_dir: Path, max_chars: int = 120_000) -> str:
    """Concatenate all .txt and .md files in brains_dir."""
    if not brains_dir.is_dir():
        logger.warning("Brains directory missing: %s — using default brain", brains_dir)
        return DEFAULT_BRAIN

    parts: list[str] = [DEFAULT_BRAIN]
    total = len(DEFAULT_BRAIN)

    for path in sorted(brains_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            logger.warning("Could not read brain file %s: %s", path, exc)
            continue
        if not text:
            continue
        header = f"\n\n--- BRAIN: {path.name} ---\n"
        chunk = header + text
        if total + len(chunk) > max_chars:
            remaining = max_chars - total - len(header) - 20
            if remaining <= 0:
                break
            chunk = header + text[:remaining] + "\n...[truncated]"
        parts.append(chunk)
        total += len(chunk)

    combined = "\n".join(parts)
    logger.info("Loaded brains from %s (%d chars)", brains_dir, len(combined))
    return combined
