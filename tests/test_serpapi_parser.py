"""Tests for SerpAPI Google Flights response parsing."""

from __future__ import annotations

from src.providers.serpapi_flights import parse_search_response


def test_parse_picks_cheapest_across_best_and_other():
    payload = {
        "best_flights": [{"price": 720}, {"price": 640}],
        "other_flights": [{"price": 510}, {"price": 800}],
    }
    q = parse_search_response(payload, "US", "USD")
    assert q is not None
    assert q.price_local == 510
    assert q.provider == "serpapi-google-flights"
    assert q.currency == "USD"


def test_parse_only_best_flights():
    payload = {"best_flights": [{"price": 1000}]}
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.price_local == 1000


def test_parse_returns_none_when_no_flights():
    assert parse_search_response({}, "ES", "EUR") is None
    assert parse_search_response({"best_flights": [], "other_flights": []}, "ES", "EUR") is None


def test_parse_extracts_booking_token():
    payload = {"best_flights": [{"price": 200, "booking_token": "abc123"}]}
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.deep_link == "abc123"


def test_parse_skips_non_numeric_prices():
    payload = {"best_flights": [{"price": "n/a"}, {"price": 300}]}
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.price_local == 300
