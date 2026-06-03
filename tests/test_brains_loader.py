"""Tests for Aureon brain loading."""

from pathlib import Path

from axrlen.ai.brains_loader import load_brains

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAINS_DIR = PROJECT_ROOT / "brains"


def test_aureon_brains_loaded():
    combined = load_brains(BRAINS_DIR, max_chars=250_000)
    assert "Axrlen" in combined
    assert "AUREON BRAIN" in combined
    assert len(combined) > 10_000


def test_priority_brains_present():
    combined = load_brains(BRAINS_DIR, max_chars=250_000)
    assert "HARD CONSTRAINT" in combined or "ANTI_SPIRAL" in combined
    assert "Ava Sports" in combined or "Zophiel Trading" in combined
