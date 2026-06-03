"""Load Aureon + Axrlen brain files into the AI system prompt."""

from __future__ import annotations

import logging
from pathlib import Path

from axrlen.ai.aureon_manifest import AUREON_PRIORITY

logger = logging.getLogger(__name__)

DEFAULT_BRAIN = """
Axrlen rules:
- Simple question, simple answer.
- Use ONLY the QUESTION, MARKET, and RESEARCH in the user message.
- YES = event likely vs market odds; NO = unlikely; SKIP = no edge or weak data.
- One-sentence answer; at most two sentences of reasoning.
""".strip()

SUPPORTED_SUFFIXES = {".txt", ".md"}


def _priority_for(path: Path) -> tuple[int, str]:
    name = path.name
    tier = AUREON_PRIORITY.get(name, 100)
    return (tier, name.lower())


def _read_brain_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _collect_brain_files(brains_dir: Path) -> list[Path]:
    if not brains_dir.is_dir():
        return []
    files = [
        path
        for path in brains_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files, key=_priority_for)


def load_simple_research_brain(brains_dir: Path) -> str:
    """Lightweight brain for market research (no full Aureon corpus)."""
    axrlen_brain = brains_dir / "axrlen_default_brain.txt"
    if axrlen_brain.is_file():
        try:
            extra = _read_brain_file(axrlen_brain)
            return f"{DEFAULT_BRAIN}\n\n{extra}"
        except OSError as exc:
            logger.warning("Could not read %s: %s", axrlen_brain, exc)
    return DEFAULT_BRAIN


def load_brains(brains_dir: Path, max_chars: int = 250_000, *, simple: bool = False) -> str:
    """
    Load brain text for the AI system prompt.

    simple=True: only Axrlen default rules (~fast, focused market research).
    simple=False: full Aureon corpus up to max_chars.
    """
    if simple:
        text = load_simple_research_brain(brains_dir)
        logger.info("Loaded simple research brain (%d chars)", len(text))
        return text

    if not brains_dir.is_dir():
        logger.warning("Brains directory missing: %s — using default brain", brains_dir)
        return DEFAULT_BRAIN

    files = _collect_brain_files(brains_dir)
    if not files:
        logger.warning("No brain files found in %s — using default brain", brains_dir)
        return DEFAULT_BRAIN

    parts: list[str] = [DEFAULT_BRAIN]
    total = len(DEFAULT_BRAIN)
    loaded_names: list[str] = []
    skipped_names: list[str] = []

    for path in files:
        try:
            text = _read_brain_file(path)
        except OSError as exc:
            logger.warning("Could not read brain file %s: %s", path, exc)
            continue
        if not text:
            continue

        rel = path.relative_to(brains_dir).as_posix()
        header = f"\n\n--- AUREON BRAIN: {rel} ---\n"
        chunk = header + text

        if total + len(chunk) > max_chars:
            remaining = max_chars - total - len(header) - 20
            if remaining <= 500:
                skipped_names.append(rel)
                continue
            chunk = header + text[:remaining] + "\n...[truncated for token budget]"
            parts.append(chunk)
            total += len(chunk)
            loaded_names.append(f"{rel} (truncated)")
            break

        parts.append(chunk)
        total += len(chunk)
        loaded_names.append(rel)

    combined = "\n".join(parts)
    logger.info(
        "Loaded %d Aureon brain files (%d chars). Skipped %d over budget.",
        len(loaded_names),
        len(combined),
        len(skipped_names),
    )
    if loaded_names:
        logger.debug("Brains loaded: %s", ", ".join(loaded_names[:15]))
    return combined
