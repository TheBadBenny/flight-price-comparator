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
from src.providers import KiwiTequilaProvider, PriceProvider

logger = logging.getLogger(__name__)


def _setup_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def collect_quotes(
    provider: PriceProvider,
    search: SearchConfig,
    converter: CurrencyConverter,
    app: AppConfig,
) -> list[tuple[str, str, float, float, float, str]]:
    """Iterate over search countries, query the provider and convert prices.

    Args:
        provider: Concrete price provider implementation.
        search: User search parameters.
        converter: Currency converter instance.
        app: Application runtime configuration.

    Returns:
        A list of tuples
        ``(country, currency, price_local, price_eur, price_eur_with_fee, deep_link)``
        suitable for :func:`src.output.build_rows`.
    """
    out: list[tuple[str, str, float, float, float, str]] = []
    for country in search.countries:
        try:
            quote = provider.fetch_quote(search, country)
        except Exception:
            logger.exception("Provider failed for country=%s", country)
            quote = None

        if quote is None:
            logger.warning("No quote returned for country=%s", country)
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
                country,
                quote.currency,
                quote.price_local,
                eur,
                eur_fee,
                quote.deep_link or "",
            )
        )
        logger.info(
            "%s: %.2f %s → %.2f EUR (with fee %.2f)",
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
    if not app.kiwi_api_key:
        logger.error("KIWI_TEQUILA_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 2

    search = search_from_args(args)
    logger.info(
        "Searching %s → %s on %s%s for %s pax (%s) across %s",
        search.origin,
        search.destination,
        search.depart_date,
        f" / return {search.return_date}" if search.return_date else "",
        search.passengers,
        search.cabin_class,
        ",".join(search.countries),
    )

    provider = KiwiTequilaProvider(app.kiwi_api_key)
    converter = CurrencyConverter(app.exchangerate_api_key)

    raw = collect_quotes(provider, search, converter, app)
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
