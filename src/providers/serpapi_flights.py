"""SerpAPI Google Flights provider.

SerpAPI scrapes Google Flights and exposes the result via a stable JSON API.
It supports ``gl`` (country) and ``currency`` parameters, which together
provide a reasonably faithful PoS simulation against Google's index.

Docs: https://serpapi.com/google-flights-api
"""

from __future__ import annotations

import logging

import requests

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote
from src.providers.kiwi import COUNTRY_CURRENCY_LOCALE

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"
REQUEST_TIMEOUT = 30

CABIN_MAP = {"economy": 1, "premium": 2, "business": 3}


def parse_search_response(payload: dict, country: str, currency: str) -> PriceQuote | None:
    """Parse a SerpAPI Google Flights payload into a :class:`PriceQuote`.

    Pure function — no I/O.

    Args:
        payload: JSON payload from SerpAPI.
        country: PoS country.
        currency: Currency the request was made in.

    Returns:
        Cheapest :class:`PriceQuote` or ``None``.
    """
    candidates: list[dict] = []
    for key in ("best_flights", "other_flights"):
        items = payload.get(key) or []
        candidates.extend(items)
    if not candidates:
        return None

    def _price(item: dict) -> float:
        p = item.get("price")
        try:
            return float(p)
        except (TypeError, ValueError):
            return float("inf")

    cheapest = min(candidates, key=_price)
    price = _price(cheapest)
    if price == float("inf"):
        return None

    return PriceQuote(
        country=country,
        currency=currency.upper(),
        price_local=price,
        provider="serpapi-google-flights",
        deep_link=cheapest.get("booking_token") or None,
        raw=cheapest,
    )


class SerpApiGoogleFlightsProvider(PriceProvider):
    """Provider backed by SerpAPI's Google Flights endpoint."""

    name = "serpapi-google-flights"
    supports_market_switch = True

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("SerpApiGoogleFlightsProvider requires an API key")
        self._key = api_key
        self._session = requests.Session()

    def _build_params(self, search: SearchConfig, country: str) -> dict:
        currency, locale = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        params: dict = {
            "engine": "google_flights",
            "departure_id": search.origin,
            "arrival_id": search.destination,
            "outbound_date": search.depart_date,
            "adults": search.passengers,
            "travel_class": CABIN_MAP[search.cabin_class],
            "currency": currency,
            "gl": country.lower(),
            "hl": locale,
            "api_key": self._key,
        }
        if search.return_date:
            params["return_date"] = search.return_date
            params["type"] = 1  # round trip
        else:
            params["type"] = 2  # one way
        return params

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch the cheapest Google Flights itinerary for ``country`` via SerpAPI.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code.

        Returns:
            A :class:`PriceQuote` or ``None`` on missing/failed responses.
        """
        params = self._build_params(search, country)
        logger.debug("SerpAPI request: %s", {k: v for k, v in params.items() if k != "api_key"})
        resp = self._session.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(
                "SerpAPI returned %s for country=%s: %s",
                resp.status_code,
                country,
                resp.text[:200],
            )
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("SerpAPI returned non-JSON for country=%s", country)
            return None
        if payload.get("error"):
            logger.warning("SerpAPI error for country=%s: %s", country, payload["error"])
            return None
        currency, _ = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        return parse_search_response(payload, country, currency)
