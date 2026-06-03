"""Tests for paper bankroll bet sizing and PnL."""

from axrlen.paper_bankroll import compute_paper_bet_size


def test_bet_size_below_compound_threshold_is_min():
    assert compute_paper_bet_size(
        250.0,
        min_bet=5.0,
        max_bet=50.0,
        compound_threshold=300.0,
        compound_pct=0.10,
    ) == 5.0


def test_bet_size_at_threshold_compounds():
    assert compute_paper_bet_size(
        400.0,
        min_bet=5.0,
        max_bet=50.0,
        compound_threshold=300.0,
        compound_pct=0.10,
    ) == 40.0


def test_bet_size_capped_at_max():
    assert compute_paper_bet_size(
        1000.0,
        min_bet=5.0,
        max_bet=50.0,
        compound_threshold=300.0,
        compound_pct=0.10,
    ) == 50.0


def test_bet_size_zero_when_insufficient_capital():
    assert compute_paper_bet_size(
        4.0,
        min_bet=5.0,
        max_bet=50.0,
        compound_threshold=300.0,
        compound_pct=0.10,
    ) == 0.0


def test_bet_size_uses_min_when_capital_between_min_and_threshold():
    assert compute_paper_bet_size(
        299.0,
        min_bet=5.0,
        max_bet=50.0,
        compound_threshold=300.0,
        compound_pct=0.10,
    ) == 5.0
