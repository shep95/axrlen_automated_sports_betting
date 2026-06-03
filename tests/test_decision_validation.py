"""Tests for simple-answer AI response validation."""

from axrlen.ai.decision_gateway import _validate_simple_response


def test_valid_simple_response():
    assert _validate_simple_response(
        {
            "decision": "YES",
            "confidence": 0.72,
            "answer": "Forecast supports Yes.",
            "reasoning": "High temp expected. Market underprices it.",
        }
    ) is None


def test_rejects_long_answer():
    assert _validate_simple_response(
        {
            "decision": "SKIP",
            "answer": "x" * 250,
            "reasoning": "ok",
        }
    ) == "answer too long"
