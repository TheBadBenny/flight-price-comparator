"""Travelpayouts (Aviasales) Data API provider.

Travelpayouts is the affiliate program behind Aviasales / JetRadar. The Data
API has a generous free tier and is stable. It supports a ``currency`` switch
but does **not** truly vary fares by point of sale, so we mark
``supports_market_switch = False`` — treat differences here as currency / FX
artefacts rather than evidence of arbitrage.

Docs: https://support.travelpayouts.com/hc/en-us/articles/203956163
"""

from __future__ import annotations

import logging

import requests

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote
from src.providers.kiwi import COUNTRY_CURRENCY_LOCALE

logger = logging.getLogger(__name__)

TRAVELPAYOUTS_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
REQUEST_TIMEOUT = 30


def parse_search_response(payload: dict, country: str, currency: str) -> PriceQuote | None:
    """Parse a Travelpayouts ``prices_for_dates`` response.

    Pure function — no I/O.

    Args:
        payload: JSON payload from the Travelpayouts endpoint.
        country: PoS country.
        currency: Currency the request was made in.

    Returns:
        Cheapest :class:`PriceQuote` or ``None``.
    """
    if not payload.get("success", True):
        return None
    items = payload.get("data") or []
    if not items:
        return None

    def _price(item: dict) -> float:
        try:
            return float(item.get("price", float("inf")))
        except (TypeError, ValueError):
            return float("inf")

    cheapest = min(items, key=_price)
    price = _price(cheapest)
    if price == float("inf"):
        return None

    deep_link = cheapest.get("link")
    if deep_link and deep_link.startswith("/"):
        deep_link = f"https://www.aviasales.com{deep_link}"

    return PriceQuote(
        country=country,
        currency=currency.upper(),
        price_local=price,
        provider="travelpayouts",
        deep_link=deep_link,
        raw=cheapest,
    )


class TravelpayoutsProvider(PriceProvider):
    """Provider backed by the Travelpayouts (Aviasales) Data API."""

    name = "travelpayouts"
    supports_market_switch = False  # currency only

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("TravelpayoutsProvider requires an API token")
        self._token = token
        self._session = requests.Session()
        self._session.headers.update({"X-Access-Token": token, "accept": "application/json"})

    def _build_params(self, search: SearchConfig, country: str) -> dict:
        currency, _ = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        params: dict = {
            "origin": search.origin,
            "destination": search.destination,
            "departure_at": search.depart_date,
            "currency": currency.lower(),
            "sorting": "price",
            "limit": 5,
            "one_way": "false" if search.return_date else "true",
            "token": self._token,
        }
        if search.return_date:
            params["return_at"] = search.return_date
        return params

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch the cheapest Travelpayouts offer for ``country``.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code (used to pick currency).

        Returns:
            A :class:`PriceQuote` or ``None`` on missing/failed responses.
        """
        params = self._build_params(search, country)
        logger.debug("Travelpayouts request: %s", {k: v for k, v in params.items() if k != "token"})
        resp = self._session.get(TRAVELPAYOUTS_URL, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(
                "Travelpayouts returned %s for country=%s: %s",
                resp.status_code,
                country,
                resp.text[:200],
            )
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("Travelpayouts returned non-JSON for country=%s", country)
            return None
        currency, _ = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        return parse_search_response(payload, country, currency)
