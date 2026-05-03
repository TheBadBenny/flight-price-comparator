"""Tests for Amadeus response parsing."""

from __future__ import annotations

from src.providers.amadeus import parse_search_response


def test_parse_picks_cheapest_amadeus_offer():
    payload = {
        "data": [
            {"price": {"total": "812.45", "currency": "EUR"}},
            {"price": {"total": "640.10", "currency": "EUR"}},
            {"price": {"total": "999.00", "currency": "EUR"}},
        ]
    }
    quote = parse_search_response(payload, "ES")
    assert quote is not None
    assert quote.country == "ES"
    assert quote.currency == "EUR"
    assert quote.price_local == 640.10
    assert quote.provider == "amadeus"


def test_parse_amadeus_uppercases_currency():
    payload = {"data": [{"price": {"total": "100", "currency": "usd"}}]}
    quote = parse_search_response(payload, "US")
    assert quote is not None
    assert quote.currency == "USD"


def test_parse_amadeus_empty_returns_none():
    assert parse_search_response({}, "ES") is None
    assert parse_search_response({"data": []}, "ES") is None


def test_parse_amadeus_missing_total_returns_none():
    payload = {"data": [{"price": {"currency": "EUR"}}]}
    assert parse_search_response(payload, "ES") is None
