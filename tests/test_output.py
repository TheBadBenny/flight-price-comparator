"""Tests for the output row builder."""

from __future__ import annotations

import pytest

from src.output import build_rows


def test_build_rows_sorts_and_computes_diff():
    raw = [
        ("kiwi-tequila", "US", "USD", 600.0, 540.0, 548.1, ""),
        ("kiwi-tequila", "ES", "EUR", 480.0, 480.0, 487.2, ""),
        ("amadeus", "IN", "INR", 50000.0, 550.0, 558.25, ""),
    ]
    rows = build_rows(raw)
    assert [r.country for r in rows] == ["ES", "US", "IN"]
    assert rows[0].provider == "kiwi-tequila"
    assert rows[0].diff_pct_vs_cheapest == 0.0
    assert rows[1].diff_pct_vs_cheapest == pytest.approx(
        (548.1 - 487.2) / 487.2 * 100, rel=1e-6
    )
    assert rows[2].diff_pct_vs_cheapest > rows[1].diff_pct_vs_cheapest


def test_build_rows_empty():
    assert build_rows([]) == []
