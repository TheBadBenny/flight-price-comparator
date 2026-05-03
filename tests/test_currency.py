"""Tests for the CurrencyConverter."""

from __future__ import annotations

import pytest

from src.currency import CurrencyConverter


def _converter_with_fake_rates(rates_to_eur: dict) -> CurrencyConverter:
    c = CurrencyConverter()
    c._rates_to_eur = rates_to_eur
    c._loaded = True
    return c


def test_eur_to_eur_is_identity():
    c = CurrencyConverter()
    assert c.to_eur(100.0, "EUR") == 100.0


def test_to_eur_applies_rate():
    c = _converter_with_fake_rates({"EUR": 1.0, "USD": 0.9, "INR": 0.011})
    assert c.to_eur(100.0, "USD") == pytest.approx(90.0)
    assert c.to_eur(8000.0, "INR") == pytest.approx(88.0)


def test_to_eur_is_case_insensitive():
    c = _converter_with_fake_rates({"EUR": 1.0, "usd": 0.9, "USD": 0.9})
    assert c.to_eur(50.0, "usd") == pytest.approx(45.0)


def test_to_eur_unknown_currency_raises():
    c = _converter_with_fake_rates({"EUR": 1.0})
    with pytest.raises(ValueError):
        c.to_eur(10.0, "XYZ")


def test_to_eur_empty_currency_raises():
    c = CurrencyConverter()
    with pytest.raises(ValueError):
        c.to_eur(10.0, "")


def test_apply_commission():
    c = CurrencyConverter()
    assert c.apply_commission(100.0, 0.015) == pytest.approx(101.5)
    assert c.apply_commission(0.0, 0.05) == 0.0


def test_apply_commission_negative_raises():
    c = CurrencyConverter()
    with pytest.raises(ValueError):
        c.apply_commission(100.0, -0.01)
