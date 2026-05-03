"""Rendering of comparison results: rich table, CSV export, optional bar chart."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)


@dataclass
class ComparisonRow:
    """A single row in the comparison table.

    Attributes:
        provider: Source provider name (e.g. "kiwi-tequila").
        country: ISO-3166 alpha-2 country code (PoS).
        currency: ISO-4217 currency code.
        price_local: Price in local currency.
        price_eur: Price converted to EUR (no commission).
        price_eur_with_fee: ``price_eur`` plus FX commission.
        diff_pct_vs_cheapest: Percentage difference vs the cheapest row.
        deep_link: Booking deep link (or empty string).
    """

    provider: str
    country: str
    currency: str
    price_local: float
    price_eur: float
    price_eur_with_fee: float
    diff_pct_vs_cheapest: float
    deep_link: str = ""


def render_table(rows: list[ComparisonRow], console: Console | None = None) -> None:
    """Render the comparison rows as a Rich table on ``console``.

    Args:
        rows: Already sorted ascending by ``price_eur_with_fee``.
        console: Optional Rich console (a fresh one is created if omitted).
    """
    console = console or Console()
    table = Table(title="Flight price comparison by point-of-sale country")
    table.add_column("Provider", style="green", no_wrap=True)
    table.add_column("Country", style="cyan", no_wrap=True)
    table.add_column("Currency", style="magenta")
    table.add_column("Price (local)", justify="right")
    table.add_column("Price (EUR)", justify="right")
    table.add_column("Price + FX fee (EUR)", justify="right", style="bold")
    table.add_column("Δ vs cheapest", justify="right")

    for i, row in enumerate(rows):
        diff = "—" if i == 0 else f"+{row.diff_pct_vs_cheapest:.2f}%"
        table.add_row(
            row.provider,
            row.country,
            row.currency,
            f"{row.price_local:,.2f}",
            f"{row.price_eur:,.2f}",
            f"{row.price_eur_with_fee:,.2f}",
            diff,
        )
    console.print(table)


def export_csv(rows: list[ComparisonRow], results_dir: Path) -> Path:
    """Persist ``rows`` to a timestamped CSV file inside ``results_dir``.

    Args:
        rows: Comparison rows.
        results_dir: Directory to write into (created if missing).

    Returns:
        Path of the written CSV file.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = results_dir / f"comparison_{ts}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "provider",
                "country",
                "currency",
                "price_local",
                "price_eur",
                "price_eur_with_fee",
                "diff_pct_vs_cheapest",
                "deep_link",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.provider,
                    row.country,
                    row.currency,
                    f"{row.price_local:.2f}",
                    f"{row.price_eur:.2f}",
                    f"{row.price_eur_with_fee:.2f}",
                    f"{row.diff_pct_vs_cheapest:.4f}",
                    row.deep_link or "",
                ]
            )
    logger.info("Wrote CSV to %s", out)
    return out


def export_chart(rows: list[ComparisonRow], results_dir: Path) -> Path | None:
    """Render a horizontal bar chart of ``price_eur_with_fee`` per country.

    Args:
        rows: Comparison rows (sorted ascending recommended).
        results_dir: Directory to write the PNG into.

    Returns:
        Path of the saved PNG, or ``None`` if matplotlib is unavailable.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping chart")
        return None

    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = results_dir / f"comparison_{ts}.png"

    labels = [f"{r.provider}/{r.country}" for r in rows]
    prices = [r.price_eur_with_fee for r in rows]

    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(rows) + 1)))
    ax.barh(labels, prices)
    ax.invert_yaxis()
    ax.set_xlabel("Price (EUR, FX fee included)")
    ax.set_title("Flight price by provider × point-of-sale country")
    for i, p in enumerate(prices):
        ax.text(p, i, f" {p:,.0f}", va="center")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    logger.info("Wrote chart to %s", out)
    return out


def build_rows(
    quotes_eur: list[tuple[str, str, str, float, float, float, str]],
) -> list[ComparisonRow]:
    """Build sorted :class:`ComparisonRow` instances from raw tuples.

    Args:
        quotes_eur: Tuples of
            ``(provider, country, currency, price_local, price_eur, price_eur_with_fee, deep_link)``.

    Returns:
        Rows sorted ascending by EUR-with-fee, with ``diff_pct_vs_cheapest`` filled in.
    """
    if not quotes_eur:
        return []
    sorted_q = sorted(quotes_eur, key=lambda x: x[5])
    cheapest = sorted_q[0][5]
    rows: list[ComparisonRow] = []
    for (
        provider,
        country,
        currency,
        price_local,
        price_eur,
        price_eur_with_fee,
        deep_link,
    ) in sorted_q:
        diff = 0.0 if cheapest == 0 else (price_eur_with_fee - cheapest) / cheapest * 100.0
        rows.append(
            ComparisonRow(
                provider=provider,
                country=country,
                currency=currency,
                price_local=price_local,
                price_eur=price_eur,
                price_eur_with_fee=price_eur_with_fee,
                diff_pct_vs_cheapest=diff,
                deep_link=deep_link,
            )
        )
    return rows
