"""Aureon brain corpus manifest — load order for Axrlen betting AI."""

from __future__ import annotations

from pathlib import Path

# Priority tiers: lower number loads first (within token budget).
AUREON_PRIORITY: dict[str, int] = {
    # Must-read (hard constraints + truth engine)
    "HARD CONSTRAINT (Priority 1 - NON-N.txt": 1,
    "ANTI_SPIRAL_PROTOCOL.md": 1,
    "Coding Rules For Aureon.txt": 2,
    "Code Scanning and Debugging Checkli.txt": 2,
    "How To Stop Hackers Files.txt": 3,
    # Betting / trading / sports
    "Ava Sports Algo.txt": 10,
    "Ava Sports Betting v.2.txt": 10,
    "Zophiel Trading.txt": 10,
    "Nestal Fractal Strategy.txt": 11,
    "Nestal Fractor Algorithm.txt": 11,
    "Twitter Audit For Asher (@shep_newton).txt": 12,
    # Prediction / analytics
    "Data Anaylitic Agent.txt": 20,
    "Vadic Global prediction.txt": 20,
    "Vadic Brain #1.txt": 20,
    "Vadic Brain #2.txt": 20,
    "vedic_planet_combos_3_and_4.txt": 21,
    "COMPLETE VEDIC PLANET SIGNIFICATION.txt": 21,
    "PLANETARY COMBINATION KNOWLEDGE MAP.txt": 21,
    "Occultism Prediction Algorithm.txt": 21,
    "VIMSHOTTARI_EXACT_TIMING_ADVANCED.txt": 22,
    "VIMSHOTTARI_ACCURACY_SUPPLEMENT.txt": 22,
    "AI_TRANSFORMATION_ANALYSIS.txt": 23,
    "Project Rome.txt": 23,
    # Prompt / agent architecture
    "ZOPHIEL_ELITE_PROMPT_ENGINE.txt": 30,
    "ZOPHIEL SUPREME ARCHITECTURE BRIEFI.txt": 30,
    "ZOPHIEL_ELITE_v4_TOTAL_ARCHITECTURE.txt": 31,
    "ZERLAL — Full Expansion Blueprint.txt": 31,
    "Prompt Egneeering.txt": 32,
    "Zophiel Brain LLM.txt": 33,
    "Zophiel Brain LLM (1).txt": 33,
    # Philosophy / consciousness
    "Aureon Philosppjy.txt": 40,
    "PHILOSOPHICAL_CONSCIOUSNESS_TRAINING_DATASET.txt": 40,
    "Aureon Brain.txt": 41,
    "You need this form of logic in your.txt": 41,
    "Actionable tactics “how to take a c.txt": 42,
    # LLM coding training (lower priority for betting)
    "LLM TRAINING FOR CODING.txt": 50,
    "LLM Debugging.txt": 50,
    "Improve LLM For Coding.txt": 51,
    "Coding LLM Improvement v.2.txt": 51,
    "Aureon LLM Coding v.3.txt": 51,
    "Aureon Zaiel Coding.txt": 51,
    "Claude Coding LLMs.txt": 52,
    "Imagine LLM .txt": 52,
    "Consious Files For Aureon.txt": 52,
    # Human patterns
    "Text Human Patterns.txt": 60,
    "HUMAN PATTERN RECOGNITION & BIO-LINGUISTICS.txt": 60,
    "Human psychology Brain.txt": 61,
    "Human Emotions.txt": 61,
    # Misc intelligence / vedic supplements
    "consciousness-ontology-brain.txt": 70,
    "Chinese Zodiac.txt": 71,
    "BIBLE_OCCULT_SYMBOLISM_ZOPHIEL_v2.txt": 72,
    "ZOPHIEL_HACKER_EXPLOITATION_ATLAS.txt": 80,
}

# PDFs to extract into .txt on import (basename without extension).
AUREON_PDF_SOURCES: tuple[str, ...] = (
    "Ava Sports Algo.pdf",
    "Ava Sports Betting v.2.pdf",
    "Zophiel Trading.pdf",
    "Nestal Fractal Strategy.pdf",
    "Nestal Fractor Algorithm.pdf",
    "Zophiel Brain LLM.pdf",
    "Zophiel Brain LLM (1).pdf",
    "Data Anaylitic Agent.pdf",
    "Prompt Egneeering.pdf",
    "Vadic Global prediction.pdf",
    "Vadic Brain #2.pdf",
    "LLM TRAINING FOR CODING.pdf",
    "LLM Debugging.pdf",
    "Improve LLM For Coding.pdf",
    "Coding LLM Improvement v.2.pdf",
    "Aureon LLM Coding v.3.pdf",
    "Aureon Zaiel Coding.pdf",
    "Claude Coding LLMs.pdf",
    "Imagine LLM .pdf",
    "Consious Files For Aureon.pdf",
    "Text Human Patterns.pdf",
    "HUMAN PATTERN RECOGNITION & BIO-LINGUISTICS.pdf",
    "Human psychology Brain.pdf",
    "Human Emotions.pdf",
    "Aureon Brain.pdf",
    "consciousness-ontology-brain.pdf",
    "Twitter Audit For Asher (@shep_newton).pdf",
    "Vadic Global prediction.pdf",
    "Mahadashas Speed of Light.pdf",
    "Aspects Speed of Light (1).pdf",
    "Astrology Speed of Light.pdf",
    "Conjugation Speed of Light.pdf",
)

DEFAULT_AUREON_SOURCE = Path(r"C:\Users\kille\Downloads\Aureon Files")
