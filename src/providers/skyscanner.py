"""Skyscanner price provider via RapidAPI.

The official Skyscanner partner programme requires approval and is not used
here. Instead this provider talks to a RapidAPI Skyscanner host, which
forwards your query to Skyscanner's Browse/Search endpoints. The host name
and path are configurable because RapidAPI vendors come and go: set
``SKYSCANNER_RAPIDAPI_HOST`` and (optionally) ``SKYSCANNER_RAPIDAPI_PATH``
in your ``.env`` to match the host you've subscribed to.

Skyscanner natively supports ``market``, ``currency`` and ``locale``, which
makes it one of the cleanest sources for true PoS arbitrage comparison.
"""

from __future__ import annotations

import logging

import requests

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote
from src.providers.kiwi import COUNTRY_CURRENCY_LOCALE

logger = logging.getLogger(__name__)

DEFAULT_HOST = "skyscanner80.p.rapidapi.com"
DEFAULT_PATH = "/api/v1/flights/search-roundtrip"
DEFAULT_PATH_ONEWAY = "/api/v1/flights/search-one-way"
REQUEST_TIMEOUT = 30

CABIN_MAP = {"economy": "economy", "premium": "premiumeconomy", "business": "business"}

COUNTRY_LOCALE_FALLBACK = "en-US"


def _price_from_itinerary(it: dict) -> float:
    """Extract a numeric price from a Skyscanner itinerary record."""
    price_block = it.get("price") or {}
    raw_price = price_block.get("raw")
    if raw_price is not None:
        try:
            return float(raw_price)
        except (TypeError, ValueError):
            pass
    formatted = price_block.get("formatted") or ""
    digits = "".join(ch for ch in formatted if ch.isdigit() or ch == ".")
    return float(digits) if digits else float("inf")


def parse_search_response(payload: dict, country: str, currency: str) -> PriceQuote | None:
    """Parse a Skyscanner RapidAPI response into a :class:`PriceQuote`.

    Tries multiple shapes seen across RapidAPI Skyscanner hosts:
    ``data.itineraries`` (list or {results: [...]}) and ``itineraries``.
    Pure function — no I/O.

    Args:
        payload: JSON payload from the RapidAPI host.
        country: PoS country.
        currency: Currency the request was made in.

    Returns:
        Cheapest :class:`PriceQuote` or ``None``.
    """
    data = payload.get("data") or {}
    itineraries = (
        (data.get("itineraries") if isinstance(data, dict) else None)
        or payload.get("itineraries")
        or []
    )
    if isinstance(itineraries, dict):
        itineraries = itineraries.get("results") or []
    if not itineraries:
        return None

    cheapest = min(itineraries, key=_price_from_itinerary)
    price = _price_from_itinerary(cheapest)
    if price == float("inf"):
        return None

    deep_link = None
    pricing_options = cheapest.get("pricingOptions") or cheapest.get("pricing_options") or []
    if pricing_options:
        first = pricing_options[0]
        url = first.get("url") or (first.get("items") or [{}])[0].get("url")
        if url:
            deep_link = url

    return PriceQuote(
        country=country,
        currency=currency.upper(),
        price_local=price,
        provider="skyscanner",
        deep_link=deep_link,
        raw=cheapest,
    )


class SkyscannerProvider(PriceProvider):
    """Provider backed by a Skyscanner host on RapidAPI."""

    name = "skyscanner"
    supports_market_switch = True

    def __init__(
        self,
        rapidapi_key: str,
        host: str = DEFAULT_HOST,
        path: str = DEFAULT_PATH,
        path_oneway: str = DEFAULT_PATH_ONEWAY,
    ) -> None:
        if not rapidapi_key:
            raise ValueError("SkyscannerProvider requires a RapidAPI key")
        self._key = rapidapi_key
        self._host = host
        self._path = path
        self._path_oneway = path_oneway
        self._session = requests.Session()
        self._session.headers.update(
            {"x-rapidapi-key": rapidapi_key, "x-rapidapi-host": host, "accept": "application/json"}
        )

    def _build_params(self, search: SearchConfig, country: str) -> dict:
        currency, locale = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        params: dict = {
            "fromId": search.origin,
            "toId": search.destination,
            "departDate": search.depart_date,
            "adults": search.passengers,
            "cabinClass": CABIN_MAP[search.cabin_class],
            "currency": currency,
            "market": country.upper(),
            "locale": f"{locale}-{country.upper()}" if len(locale) == 2 else COUNTRY_LOCALE_FALLBACK,
        }
        if search.return_date:
            params["returnDate"] = search.return_date
        return params

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch the cheapest Skyscanner itinerary for ``country`` as PoS.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code.

        Returns:
            A :class:`PriceQuote` or ``None`` on missing/failed responses.
        """
        params = self._build_params(search, country)
        path = self._path if search.return_date else self._path_oneway
        url = f"https://{self._host}{path}"
        logger.debug("Skyscanner request: %s %s", url, params)
        resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(
                "Skyscanner returned %s for country=%s: %s",
                resp.status_code,
                country,
                resp.text[:200],
            )
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("Skyscanner returned non-JSON for country=%s", country)
            return None
        currency, _ = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        return parse_search_response(payload, country, currency)
