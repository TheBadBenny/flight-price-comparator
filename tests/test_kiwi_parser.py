"""Tests for parsing Kiwi Tequila search responses."""

from __future__ import annotations

from src.providers.kiwi import _format_date, parse_search_response


def test_parse_picks_cheapest_flight():
    payload = {
        "currency": "USD",
        "data": [
            {"price": 750.0, "deep_link": "https://kiwi/1"},
            {"price": 499.5, "deep_link": "https://kiwi/2"},
            {"price": 612.0, "deep_link": "https://kiwi/3"},
        ],
    }
    quote = parse_search_response(payload, "US")
    assert quote is not None
    assert quote.country == "US"
    assert quote.currency == "USD"
    assert quote.price_local == 499.5
    assert quote.deep_link == "https://kiwi/2"
    assert quote.provider == "kiwi-tequila"


def test_parse_returns_none_for_empty_data():
    assert parse_search_response({"currency": "EUR", "data": []}, "ES") is None
    assert parse_search_response({}, "ES") is None


def test_parse_defaults_currency_when_missing():
    payload = {"data": [{"price": 200.0}]}
    quote = parse_search_response(payload, "DE")
    assert quote is not None
    assert quote.currency == "EUR"
    assert quote.price_local == 200.0
    assert quote.deep_link is None


def test_parse_uppercases_currency():
    payload = {"currency": "thb", "data": [{"price": 12000.0}]}
    quote = parse_search_response(payload, "TH")
    assert quote is not None
    assert quote.currency == "THB"


def test_format_date():
    assert _format_date("2026-08-15") == "15/08/2026"
    assert _format_date("2026-01-01") == "01/01/2026"
