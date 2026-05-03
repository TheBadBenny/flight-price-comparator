"""Skyscanner price provider via Playwright (browser scraping).

This is a deliberately simple, polite scraper for **personal/educational use**.
It opens Skyscanner's public search page on the country-specific domain, lets
the SPA render, dismisses the cookie banner if present, and reads the cheapest
price from the visible page text. There is **no** anti-bot evasion: no UA
rotation, no proxy pool, no fingerprint spoofing. Skyscanner's Terms of Service
prohibit automated access — using this provider is at your own risk.

Because the DOM changes regularly, the price extractor uses a currency-aware
regex over the full page text rather than CSS selectors, which makes it more
resilient to selector churn at the cost of occasional false positives. The
parser is a pure function and is unit-tested independently of Playwright.
"""

from __future__ import annotations

import contextlib
import logging
import re
from dataclasses import dataclass

from src.config import SearchConfig
from src.providers.base import PriceProvider, PriceQuote

logger = logging.getLogger(__name__)

DEFAULT_NAVIGATION_TIMEOUT_MS = 30_000
DEFAULT_RENDER_WAIT_MS = 9_000


@dataclass(frozen=True)
class SkyscannerLocale:
    """Per-country mapping for the Skyscanner public website.

    Attributes:
        domain: Country-specific Skyscanner host (e.g. "www.skyscanner.es").
        currency: ISO-4217 currency code shown in search results.
        symbols: Tuple of currency symbols/strings to look for in page text.
        decimal: Decimal separator for prices on this domain.
        thousands: Thousands separator for prices on this domain.
        accept_lang: Value for the Accept-Language header.
    """

    domain: str
    currency: str
    symbols: tuple[str, ...]
    decimal: str
    thousands: str
    accept_lang: str


COUNTRY_TO_LOCALE: dict[str, SkyscannerLocale] = {
    "ES": SkyscannerLocale("www.skyscanner.es", "EUR", ("€",), ",", ".", "es-ES"),
    "DE": SkyscannerLocale("www.skyscanner.de", "EUR", ("€",), ",", ".", "de-DE"),
    "FR": SkyscannerLocale("www.skyscanner.fr", "EUR", ("€",), ",", " ", "fr-FR"),
    "IT": SkyscannerLocale("www.skyscanner.it", "EUR", ("€",), ",", ".", "it-IT"),
    "GB": SkyscannerLocale("www.skyscanner.net", "GBP", ("£",), ".", ",", "en-GB"),
    "US": SkyscannerLocale("www.skyscanner.com", "USD", ("$", "US$"), ".", ",", "en-US"),
    "CA": SkyscannerLocale("www.skyscanner.ca", "CAD", ("$", "C$", "CA$"), ".", ",", "en-CA"),
    "MX": SkyscannerLocale("www.skyscanner.com.mx", "MXN", ("$", "Mex$", "MX$"), ".", ",", "es-MX"),
    "BR": SkyscannerLocale("www.skyscanner.com.br", "BRL", ("R$",), ",", ".", "pt-BR"),
    "AR": SkyscannerLocale("www.skyscanner.com.ar", "ARS", ("$",), ",", ".", "es-AR"),
    "IN": SkyscannerLocale("www.skyscanner.co.in", "INR", ("₹", "Rs"), ".", ",", "en-IN"),
    "TH": SkyscannerLocale("www.skyscanner.co.th", "THB", ("฿", "THB"), ".", ",", "th-TH"),
    "JP": SkyscannerLocale("www.skyscanner.jp", "JPY", ("¥", "￥"), ".", ",", "ja-JP"),
    "AU": SkyscannerLocale("www.skyscanner.com.au", "AUD", ("$", "A$"), ".", ",", "en-AU"),
    "TR": SkyscannerLocale("www.skyscanner.com.tr", "TRY", ("₺", "TL"), ",", ".", "tr-TR"),
    "PL": SkyscannerLocale("www.skyscanner.pl", "PLN", ("zł", "PLN"), ",", " ", "pl-PL"),
    "ZA": SkyscannerLocale("www.skyscanner.co.za", "ZAR", ("R",), ".", ",", "en-ZA"),
}

CABIN_MAP = {"economy": "economy", "premium": "premiumeconomy", "business": "business"}


def _date_path(iso_date: str) -> str:
    """Convert YYYY-MM-DD to Skyscanner's YYMMDD URL segment."""
    y, m, d = iso_date.split("-")
    return f"{y[2:]}{m}{d}"


def build_search_url(search: SearchConfig, locale: SkyscannerLocale) -> str:
    """Build the Skyscanner public search URL for ``search`` on ``locale``.

    Args:
        search: User search parameters.
        locale: The :class:`SkyscannerLocale` for the target country.

    Returns:
        Fully-qualified search URL.
    """
    parts = [
        f"https://{locale.domain}/transport/flights",
        search.origin.lower(),
        search.destination.lower(),
        _date_path(search.depart_date),
    ]
    if search.return_date:
        parts.append(_date_path(search.return_date))
    base = "/".join(parts) + "/"
    query = (
        f"?adults={search.passengers}"
        f"&cabinclass={CABIN_MAP[search.cabin_class]}"
        f"&currency={locale.currency}"
    )
    return base + query


def _normalize_number(raw: str, decimal: str, thousands: str) -> float | None:
    """Parse ``raw`` into a float honouring locale-specific separators."""
    if not raw:
        return None
    cleaned = raw.strip()
    if thousands and thousands != decimal:
        cleaned = cleaned.replace(thousands, "")
    if decimal != ".":
        cleaned = cleaned.replace(decimal, ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value


def extract_prices(text: str, locale: SkyscannerLocale) -> list[float]:
    """Extract candidate prices from raw page text for ``locale``.

    Looks for any of the locale's currency symbols followed (or preceded) by a
    number. Returns all matches as floats; callers typically take the minimum.

    Args:
        text: Full visible text of the rendered Skyscanner page.
        locale: The :class:`SkyscannerLocale` to interpret prices with.

    Returns:
        List of candidate prices in ascending order.
    """
    if not text:
        return []

    decimal = re.escape(locale.decimal)
    thousands = re.escape(locale.thousands) if locale.thousands else ""
    if thousands:
        number_pattern = rf"\d{{1,3}}(?:{thousands}\d{{3}})*(?:{decimal}\d{{1,2}})?"
    else:
        number_pattern = rf"\d+(?:{decimal}\d{{1,2}})?"

    candidates: list[float] = []
    for symbol in locale.symbols:
        sym = re.escape(symbol)
        # Symbol-before, e.g. "€ 612,40" / "$612.40"
        for match in re.finditer(rf"{sym}\s?({number_pattern})\b", text):
            value = _normalize_number(match.group(1), locale.decimal, locale.thousands)
            if value is not None and value > 0:
                candidates.append(value)
        # Symbol-after, e.g. "612,40 zł" / "1234 ฿"
        for match in re.finditer(rf"\b({number_pattern})\s?{sym}", text):
            value = _normalize_number(match.group(1), locale.decimal, locale.thousands)
            if value is not None and value > 0:
                candidates.append(value)

    # Filter implausibly tiny numbers that are almost certainly not flight prices
    # (page chrome often shows things like "€ 5" promo labels). 30 is a
    # conservative floor across all currencies for an international flight.
    candidates = [c for c in candidates if c >= 30]
    return sorted(candidates)


class SkyscannerScraperProvider(PriceProvider):
    """Browser-based Skyscanner provider using Playwright.

    Heavyweight: opens a Chromium instance on first use and reuses it across
    countries. Call :meth:`close` when done.
    """

    name = "skyscanner-scrape"
    supports_market_switch = True

    def __init__(
        self,
        headless: bool = True,
        navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
        render_wait_ms: int = DEFAULT_RENDER_WAIT_MS,
    ) -> None:
        self._headless = headless
        self._nav_timeout = navigation_timeout_ms
        self._render_wait = render_wait_ms
        self._pw = None
        self._browser = None

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - import-time error
            raise RuntimeError(
                "Playwright is required for the scraper provider. Install with "
                "`pip install playwright && playwright install chromium`."
            ) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)

    def close(self) -> None:
        """Close the underlying browser and Playwright runtime if open."""
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.exception("Error closing Playwright browser")
            self._browser = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.exception("Error stopping Playwright")
            self._pw = None

    def _dismiss_cookie_banner(self, page) -> None:
        """Best-effort cookie-banner dismissal across Skyscanner locales."""
        selectors = (
            "#acceptCookieButton",
            "button#cookie-banner-acceptbtn",
            "button[data-testid='cookie-banner-accept-cta']",
            "button:has-text('Accept all')",
            "button:has-text('Aceptar todo')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Tout accepter')",
        )
        for sel in selectors:
            try:
                page.locator(sel).first.click(timeout=1500)
                return
            except Exception:
                continue

    def fetch_quote(self, search: SearchConfig, country: str) -> PriceQuote | None:
        """Open Skyscanner's PoS-specific search page and read the cheapest price.

        Args:
            search: Search parameters.
            country: ISO-3166 alpha-2 country code; falls back to US if unknown.

        Returns:
            A :class:`PriceQuote` or ``None`` if no plausible price was found.
        """
        locale = COUNTRY_TO_LOCALE.get(country.upper())
        if locale is None:
            logger.warning("No Skyscanner locale mapping for country=%s", country)
            return None

        self._ensure_browser()
        assert self._browser is not None

        url = build_search_url(search, locale)
        logger.info("Skyscanner-scrape %s → %s", country, url)

        context = self._browser.new_context(
            locale=locale.accept_lang,
            extra_http_headers={"Accept-Language": locale.accept_lang},
        )
        try:
            page = context.new_page()
            page.set_default_navigation_timeout(self._nav_timeout)
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception:
                logger.warning("Skyscanner navigation failed for country=%s", country)
                return None

            self._dismiss_cookie_banner(page)
            page.wait_for_timeout(self._render_wait)

            try:
                text = page.evaluate("() => document.body.innerText")
            except Exception:
                logger.warning("Could not read body text for country=%s", country)
                return None

            prices = extract_prices(text, locale)
            if not prices:
                logger.warning("No plausible prices found for country=%s", country)
                return None

            cheapest = prices[0]
            return PriceQuote(
                country=country,
                currency=locale.currency,
                price_local=cheapest,
                provider="skyscanner-scrape",
                deep_link=url,
                raw={"candidates": prices[:10]},
            )
        finally:
            with contextlib.suppress(Exception):  # pragma: no cover - best-effort
                context.close()
