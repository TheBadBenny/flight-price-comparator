"""Tests for Skyscanner (RapidAPI) response parsing."""

from __future__ import annotations

from src.providers.skyscanner import parse_search_response


def test_parse_picks_cheapest_with_data_itineraries_list():
    payload = {
        "data": {
            "itineraries": [
                {"price": {"raw": 850.0, "formatted": "$850"}},
                {"price": {"raw": 612.5, "formatted": "$612"}},
            ]
        }
    }
    q = parse_search_response(payload, "US", "USD")
    assert q is not None
    assert q.price_local == 612.5
    assert q.currency == "USD"
    assert q.provider == "skyscanner"


def test_parse_picks_cheapest_with_results_wrapper():
    payload = {
        "data": {
            "itineraries": {
                "results": [
                    {"price": {"raw": 700.0}},
                    {"price": {"raw": 480.0}},
                ]
            }
        }
    }
    q = parse_search_response(payload, "ES", "EUR")
    assert q is not None
    assert q.price_local == 480.0


def test_parse_falls_back_to_top_level_itineraries():
    payload = {"itineraries": [{"price": {"raw": 333.3}}]}
    q = parse_search_response(payload, "TH", "THB")
    assert q is not None
    assert q.price_local == 333.3
    assert q.currency == "THB"


def test_parse_handles_formatted_only_price():
    payload = {"itineraries": [{"price": {"formatted": "$1,234.50"}}]}
    q = parse_search_response(payload, "US", "USD")
    assert q is not None
    assert q.price_local == 1234.50


def test_parse_extracts_pricing_options_url():
    payload = {
        "itineraries": [
            {
                "price": {"raw": 100},
                "pricingOptions": [{"url": "https://book.example/1"}],
            }
        ]
    }
    q = parse_search_response(payload, "US", "USD")
    assert q is not None
    assert q.deep_link == "https://book.example/1"


def test_parse_empty_returns_none():
    assert parse_search_response({}, "ES", "EUR") is None
    assert parse_search_response({"data": {"itineraries": []}}, "ES", "EUR") is None
