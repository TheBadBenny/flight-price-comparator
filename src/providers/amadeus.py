"""Amadeus Self-Service flight-offers provider.

Uses the official Amadeus API (test environment by default). Authentication is
OAuth2 client_credentials. The API does not expose a true point-of-sale
parameter — it accepts ``currencyCode`` but the underlying fare contract is
mostly invariant across markets. We still iterate the user-supplied countries
and request the matching local currency, so the output is comparable to the
other providers and exposes any currency-driven differences.
"""

from __future__ import annotations

import logging

import requests

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote
from src.providers.kiwi import COUNTRY_CURRENCY_LOCALE

logger = logging.getLogger(__name__)

AMADEUS_BASE_TEST = "https://test.api.amadeus.com"
AMADEUS_BASE_PROD = "https://api.amadeus.com"
TOKEN_PATH = "/v1/security/oauth2/token"
SEARCH_PATH = "/v2/shopping/flight-offers"
REQUEST_TIMEOUT = 30

CABIN_MAP = {"economy": "ECONOMY", "premium": "PREMIUM_ECONOMY", "business": "BUSINESS"}


def parse_search_response(payload: dict, country: str) -> PriceQuote | None:
    """Parse an Amadeus ``/v2/shopping/flight-offers`` payload.

    Picks the cheapest offer from ``payload['data']``. Pure function — no I/O.

    Args:
        payload: JSON payload returned by the Amadeus search endpoint.
        country: Country (PoS) the request was made for.

    Returns:
        Cheapest :class:`PriceQuote` or ``None``.
    """
    offers = payload.get("data") or []
    if not offers:
        return None

    def _price(offer: dict) -> float:
        return float((offer.get("price") or {}).get("total", float("inf")))

    cheapest = min(offers, key=_price)
    price_block = cheapest.get("price") or {}
    total = price_block.get("total")
    if total is None:
        return None
    currency = (price_block.get("currency") or "EUR").upper()
    return PriceQuote(
        country=country,
        currency=currency,
        price_local=float(total),
        provider="amadeus",
        deep_link=None,
        raw=cheapest,
    )


class AmadeusProvider(PriceProvider):
    """Provider backed by the Amadeus Self-Service flight-offers API."""

    name = "amadeus"
    supports_market_switch = False  # currency only, no real PoS variation

    def __init__(self, api_key: str, api_secret: str, use_production: bool = False) -> None:
        if not api_key or not api_secret:
            raise ValueError("AmadeusProvider requires api_key and api_secret")
        self._api_key = api_key
        self._api_secret = api_secret
        self._base = AMADEUS_BASE_PROD if use_production else AMADEUS_BASE_TEST
        self._session = requests.Session()
        self._token: str | None = None

    def _ensure_token(self) -> str:
        if self._token:
            return self._token
        logger.info("Authenticating with Amadeus (%s)", self._base)
        resp = self._session.post(
            f"{self._base}{TOKEN_PATH}",
            data={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._api_secret,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _build_params(self, search: SearchConfig, country: str) -> dict:
        currency, _ = COUNTRY_CURRENCY_LOCALE.get(country, ("EUR", "en"))
        params: dict = {
            "originLocationCode": search.origin,
            "destinationLocationCode": search.destination,
            "departureDate": search.depart_date,
            "adults": search.passengers,
            "currencyCode": currency,
            "travelClass": CABIN_MAP[search.cabin_class],
            "max": 5,
        }
        if search.return_date:
            params["returnDate"] = search.return_date
        return params

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch the cheapest Amadeus offer for ``country``.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code (used to pick currency).

        Returns:
            A :class:`PriceQuote` or ``None`` on missing/failed responses.
        """
        token = self._ensure_token()
        params = self._build_params(search, country)
        logger.debug("Amadeus request: %s", params)
        resp = self._session.get(
            f"{self._base}{SEARCH_PATH}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 401:
            self._token = None  # token may have expired; retry once
            token = self._ensure_token()
            resp = self._session.get(
                f"{self._base}{SEARCH_PATH}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT,
            )
        if resp.status_code != 200:
            logger.warning(
                "Amadeus returned %s for country=%s: %s",
                resp.status_code,
                country,
                resp.text[:200],
            )
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("Amadeus returned non-JSON for country=%s", country)
            return None
        return parse_search_response(payload, country)
