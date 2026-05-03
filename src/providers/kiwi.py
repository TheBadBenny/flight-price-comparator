"""Kiwi Tequila price provider.

The Tequila Search API supports a ``partner_market`` parameter which lets us
simulate the user's point of sale, plus ``curr`` and ``locale`` for the
returned currency and language. See https://tequila.kiwi.com/portal/docs.
"""

from __future__ import annotations

import logging

import requests

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote

logger = logging.getLogger(__name__)

TEQUILA_SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"
REQUEST_TIMEOUT = 30

# Sensible defaults for the countries the user shipped with the spec.
# Currency is ISO-4217; locale is the Tequila locale code.
COUNTRY_CURRENCY_LOCALE: dict[str, tuple[str, str]] = {
    "ES": ("EUR", "es"),
    "IN": ("INR", "en"),
    "TH": ("THB", "en"),
    "PL": ("PLN", "pl"),
    "MX": ("MXN", "es"),
    "US": ("USD", "en"),
    "TR": ("TRY", "tr"),
    "BR": ("BRL", "pt"),
    "GB": ("GBP", "en"),
    "DE": ("EUR", "de"),
    "FR": ("EUR", "fr"),
    "IT": ("EUR", "it"),
    "JP": ("JPY", "en"),
    "AU": ("AUD", "en"),
    "CA": ("CAD", "en"),
    "AR": ("ARS", "es"),
    "ZA": ("ZAR", "en"),
}

CABIN_MAP = {"economy": "M", "premium": "W", "business": "C"}


def _format_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to Tequila's DD/MM/YYYY format."""
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"


def parse_search_response(payload: dict, country: str) -> PriceQuote | None:
    """Parse a Tequila ``/v2/search`` response into a :class:`PriceQuote`.

    Picks the cheapest flight from ``payload['data']``. Pure function — no I/O.

    Args:
        payload: JSON payload returned by the Tequila search endpoint.
        country: Country (PoS) the request was made for.

    Returns:
        The cheapest :class:`PriceQuote` or ``None`` if the response had no flights.
    """
    flights = payload.get("data") or []
    if not flights:
        return None
    currency = (payload.get("currency") or "EUR").upper()
    cheapest = min(flights, key=lambda f: float(f.get("price", float("inf"))))
    return PriceQuote(
        country=country,
        currency=currency,
        price_local=float(cheapest["price"]),
        provider="kiwi-tequila",
        deep_link=cheapest.get("deep_link"),
        raw=cheapest,
    )


class KiwiTequilaProvider(PriceProvider):
    """Provider backed by the Kiwi Tequila Search API."""

    name = "kiwi-tequila"
    supports_market_switch = True

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("KiwiTequilaProvider requires an API key")
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({"apikey": api_key, "accept": "application/json"})

    def _build_params(self, search: SearchConfig, country: str) -> dict:
        currency, locale = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        params = {
            "fly_from": search.origin,
            "fly_to": search.destination,
            "date_from": _format_date(search.depart_date),
            "date_to": _format_date(search.depart_date),
            "adults": search.passengers,
            "selected_cabins": CABIN_MAP[search.cabin_class],
            "curr": currency,
            "locale": locale,
            "partner_market": country.lower(),
            "limit": 5,
            "sort": "price",
        }
        if search.return_date:
            params["return_from"] = _format_date(search.return_date)
            params["return_to"] = _format_date(search.return_date)
        return params

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch the cheapest quote from Tequila for ``country`` as PoS.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code.

        Returns:
            A :class:`PriceQuote` or ``None`` if no flights were returned.
        """
        params = self._build_params(search, country)
        logger.debug("Tequila request: %s", params)
        resp = self._session.get(TEQUILA_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(
                "Tequila returned %s for country=%s: %s",
                resp.status_code,
                country,
                resp.text[:200],
            )
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("Tequila returned non-JSON for country=%s", country)
            return None
        return parse_search_response(payload, country)
