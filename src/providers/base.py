"""Abstract price-provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import SearchConfig


@dataclass
class PriceQuote:
    """A single flight quote returned by a provider for a given country.

    Attributes:
        country: ISO-3166 alpha-2 country code that was simulated as PoS.
        currency: ISO-4217 currency code in which the price was quoted.
        price_local: Total price in the local currency.
        provider: Human-readable provider name (e.g. "kiwi-tequila").
        deep_link: Optional booking URL.
        raw: Optional raw provider payload for debugging.
    """

    country: str
    currency: str
    price_local: float
    provider: str
    deep_link: str | None = None
    raw: dict | None = None


class PriceProvider(ABC):
    """Abstract flight-price provider.

    Implementations must be able to query the same itinerary while simulating
    different points of sale (countries) and return a :class:`PriceQuote`.
    """

    name: str = "abstract"
    supports_market_switch: bool = False

    @abstractmethod
    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Fetch a single price quote for ``search`` simulating ``country`` as PoS.

        Args:
            search: User search parameters.
            country: ISO-3166 alpha-2 country code to simulate as point of sale.

        Returns:
            A :class:`PriceQuote` or ``None`` if no flights were found.
        """
        raise NotImplementedError
