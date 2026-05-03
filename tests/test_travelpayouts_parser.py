"""Tests for Travelpayouts response parsing."""

from __future__ import annotations

from src.providers.travelpayouts import parse_search_response


def test_parse_picks_cheapest_offer():
    payload = {
        "success": True,
        "data": [
            {"price": 720, "airline": "IB"},
            {"price": 510, "airline": "AY"},
            {"price": 880, "airline": "BA"},
        ],
        "currency": "eur",
    }
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.price_local == 510
    assert q.currency == "EUR"
    assert q.provider == "travelpayouts"


def test_parse_returns_none_when_unsuccessful():
    payload = {"success": False, "data": []}
    assert parse_search_response(payload, "ES", "EUR") is None


def test_parse_returns_none_when_empty():
    assert parse_search_response({"success": True, "data": []}, "ES", "EUR") is None
    assert parse_search_response({}, "ES", "EUR") is None


def test_parse_builds_absolute_link():
    payload = {
        "success": True,
        "data": [{"price": 200, "link": "/flights/MADJFK"}],
    }
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.deep_link == "https://www.aviasales.com/flights/MADJFK"


def test_parse_keeps_absolute_link():
    payload = {
        "success": True,
        "data": [{"price": 200, "link": "https://example.com/x"}],
    }
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.deep_link == "https://example.com/x"


def test_parse_skips_non_numeric_prices():
    payload = {
        "success": True,
        "data": [{"price": "n/a"}, {"price": 333}],
    }
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.price_local == 333
