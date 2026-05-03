"""Currency conversion to EUR via exchangerate-api.com or Frankfurter (fallback)."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest"
EXCHANGERATE_URL = "https://v6.exchangerate-api.com/v6/{key}/latest/{base}"

REQUEST_TIMEOUT = 15


class CurrencyConverter:
    """Convert arbitrary amounts to EUR using a public FX rates API.

    Rates are fetched lazily on the first conversion away from EUR and cached
    for the lifetime of the instance. Pass ``api_key`` to use exchangerate-api.com,
    otherwise the free Frankfurter API is used.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._rates_to_eur: dict[str, float] = {"EUR": 1.0}
        self._loaded = False

    def _load_rates(self) -> None:
        """Fetch rates and populate the EUR-denominated cache."""
        if self._api_key:
            url = EXCHANGERATE_URL.format(key=self._api_key, base="EUR")
            logger.info("Fetching FX rates from exchangerate-api.com (base=EUR)")
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("conversion_rates") or {}
        else:
            logger.info("Fetching FX rates from Frankfurter (base=EUR)")
            resp = requests.get(f"{FRANKFURTER_URL}?from=EUR", timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates") or {}

        if not rates:
            raise RuntimeError("FX provider returned no rates")

        self._rates_to_eur = {"EUR": 1.0}
        for code, rate_from_eur in rates.items():
            if rate_from_eur and float(rate_from_eur) > 0:
                # rate_from_eur = how many CODE per 1 EUR.
                self._rates_to_eur[code.upper()] = 1.0 / float(rate_from_eur)
        self._loaded = True

    def to_eur(self, amount: float, currency: str) -> float:
        """Convert ``amount`` in ``currency`` to EUR.

        Args:
            amount: Amount in the source currency.
            currency: ISO-4217 code (e.g. "USD"). Case-insensitive.

        Returns:
            Amount in EUR.

        Raises:
            ValueError: If the currency is unknown to the FX provider.
        """
        code = (currency or "").upper().strip()
        if not code:
            raise ValueError("currency code is empty")
        if code == "EUR":
            return float(amount)
        if not self._loaded:
            self._load_rates()
        if code not in self._rates_to_eur:
            raise ValueError(f"Unknown currency code: {code}")
        return float(amount) * self._rates_to_eur[code]

    def apply_commission(self, amount_eur: float, commission: float) -> float:
        """Apply a multiplicative FX commission on top of an EUR amount.

        Args:
            amount_eur: Amount already converted to EUR.
            commission: Commission as decimal (e.g. 0.015 for 1.5%).

        Returns:
            Amount in EUR including the commission.
        """
        if commission < 0:
            raise ValueError("commission must be non-negative")
        return amount_eur * (1.0 + commission)
