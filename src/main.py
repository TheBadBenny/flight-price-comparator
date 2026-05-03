"""CLI entry point for the flight price comparator."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from src.config import (
    AppConfig,
    SearchConfig,
    build_arg_parser,
    load_app_config,
    search_from_args,
)
from src.currency import CurrencyConverter
from src.output import build_rows, export_chart, export_csv, render_table
from src.providers import (
    AmadeusProvider,
    KiwiTequilaProvider,
    PriceProvider,
    SerpApiGoogleFlightsProvider,
    SkyscannerProvider,
)

logger = logging.getLogger(__name__)


def _setup_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def build_providers(app: AppConfig, selected: list[str] | None) -> list[PriceProvider]:
    """Instantiate providers chosen by the user (or all available by default).

    Args:
        app: Application configuration with API keys.
        selected: User-supplied list of provider keys
            (``"kiwi"`` / ``"amadeus"`` / ``"skyscanner"`` / ``"serpapi"``)
            or ``None`` to use every provider whose credentials are present.

    Returns:
        Concrete :class:`PriceProvider` instances ready to be queried.
    """
    available = app.available_providers()
    if selected is None:
        chosen = available
    else:
        chosen = [s for s in selected if s in available]
        missing = [s for s in selected if s not in available]
        for m in missing:
            logger.warning("Skipping provider %s: required credentials missing.", m)

    providers: list[PriceProvider] = []
    for name in chosen:
        if name == "kiwi":
            providers.append(KiwiTequilaProvider(app.kiwi_api_key))  # type: ignore[arg-type]
        elif name == "amadeus":
            providers.append(
                AmadeusProvider(
                    app.amadeus_api_key,  # type: ignore[arg-type]
                    app.amadeus_api_secret,  # type: ignore[arg-type]
                    use_production=app.amadeus_use_production,
                )
            )
        elif name == "skyscanner":
            providers.append(
                SkyscannerProvider(app.rapidapi_key, host=app.skyscanner_host)  # type: ignore[arg-type]
            )
        elif name == "serpapi":
            providers.append(SerpApiGoogleFlightsProvider(app.serpapi_api_key))  # type: ignore[arg-type]
    return providers


def collect_quotes(
    providers: list[PriceProvider],
    search: SearchConfig,
    converter: CurrencyConverter,
    app: AppConfig,
) -> list[tuple[str, str, str, float, float, float, str]]:
    """Iterate provider × country and convert prices to EUR.

    Args:
        providers: Concrete provider instances.
        search: User search parameters.
        converter: Currency converter instance.
        app: Application runtime configuration.

    Returns:
        List of tuples
        ``(provider, country, currency, price_local, price_eur, price_eur_with_fee, deep_link)``.
    """
    out: list[tuple[str, str, str, float, float, float, str]] = []
    for provider in providers:
        logger.info("Querying provider: %s", provider.name)
        for country in search.countries:
            try:
                quote = provider.fetch_quote(search, country)
            except Exception:
                logger.exception("%s failed for country=%s", provider.name, country)
                quote = None

            if quote is None:
                logger.warning("No quote from %s for country=%s", provider.name, country)
                time.sleep(app.request_delay_seconds)
                continue

            try:
                eur = converter.to_eur(quote.price_local, quote.currency)
            except Exception:
                logger.exception(
                    "Currency conversion failed for %s %s", quote.price_local, quote.currency
                )
                time.sleep(app.request_delay_seconds)
                continue

            eur_fee = converter.apply_commission(eur, app.fx_commission)
            out.append(
                (
                    provider.name,
                    country,
                    quote.currency,
                    quote.price_local,
                    eur,
                    eur_fee,
                    quote.deep_link or "",
                )
            )
            logger.info(
                "%s | %s: %.2f %s → %.2f EUR (with fee %.2f)",
                provider.name,
                country,
                quote.price_local,
                quote.currency,
                eur,
                eur_fee,
            )
            time.sleep(app.request_delay_seconds)
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument vector (mainly for tests).

    Returns:
        Process exit code.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.log_level)

    app = load_app_config()
    available = app.available_providers()
    if not available:
        logger.error(
            "No provider credentials found. Set at least one of "
            "KIWI_TEQUILA_API_KEY, AMADEUS_API_KEY+AMADEUS_API_SECRET, "
            "RAPIDAPI_KEY, or SERPAPI_API_KEY in your .env."
        )
        return 2

    search = search_from_args(args)
    providers = build_providers(app, args.providers)
    if not providers:
        logger.error("No usable providers selected (have keys for: %s).", ", ".join(available))
        return 2

    logger.info(
        "Searching %s → %s on %s%s for %s pax (%s) across %s — providers: %s",
        search.origin,
        search.destination,
        search.depart_date,
        f" / return {search.return_date}" if search.return_date else "",
        search.passengers,
        search.cabin_class,
        ",".join(search.countries),
        ",".join(p.name for p in providers),
    )

    converter = CurrencyConverter(app.exchangerate_api_key)
    raw = collect_quotes(providers, search, converter, app)
    if not raw:
        logger.error("No quotes were collected — nothing to render.")
        return 1

    rows = build_rows(raw)
    render_table(rows)

    results_dir = Path("results")
    export_csv(rows, results_dir)
    if not args.no_chart:
        export_chart(rows, results_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
