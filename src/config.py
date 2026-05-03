"""Configuration loading from CLI args, YAML files and environment variables."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEFAULT_COUNTRIES = ["ES", "IN", "TH", "PL", "MX", "US", "TR", "BR"]
VALID_CABIN_CLASSES = ("economy", "premium", "business")
SUPPORTED_PROVIDERS = ("kiwi", "amadeus", "skyscanner", "serpapi")


@dataclass
class SearchConfig:
    """User-facing search parameters for a flight comparison run.

    Attributes:
        origin: IATA code of the origin airport (e.g. "MAD").
        destination: IATA code of the destination airport (e.g. "JFK").
        depart_date: Outbound date as YYYY-MM-DD.
        return_date: Optional return date as YYYY-MM-DD.
        passengers: Number of adult passengers (>= 1).
        cabin_class: One of "economy", "premium", "business".
        countries: ISO-3166 alpha-2 country codes to compare.
    """

    origin: str
    destination: str
    depart_date: str
    return_date: str | None = None
    passengers: int = 1
    cabin_class: str = "economy"
    countries: list[str] = field(default_factory=lambda: list(DEFAULT_COUNTRIES))

    def __post_init__(self) -> None:
        self.origin = self.origin.upper().strip()
        self.destination = self.destination.upper().strip()
        self.cabin_class = self.cabin_class.lower().strip()
        self.countries = [c.upper().strip() for c in self.countries]
        if len(self.origin) != 3 or len(self.destination) != 3:
            raise ValueError("origin/destination must be 3-letter IATA codes")
        if self.cabin_class not in VALID_CABIN_CLASSES:
            raise ValueError(f"cabin_class must be one of {VALID_CABIN_CLASSES}")
        if self.passengers < 1:
            raise ValueError("passengers must be >= 1")


@dataclass
class AppConfig:
    """Runtime configuration sourced from environment variables.

    Attributes:
        kiwi_api_key: Tequila API key.
        exchangerate_api_key: Optional key for exchangerate-api.com.
        fx_commission: FX commission as decimal (e.g. 0.015 = 1.5%).
        request_delay_seconds: Sleep between provider calls.
    """

    kiwi_api_key: str | None
    amadeus_api_key: str | None
    amadeus_api_secret: str | None
    amadeus_use_production: bool
    rapidapi_key: str | None
    skyscanner_host: str
    serpapi_api_key: str | None
    exchangerate_api_key: str | None
    fx_commission: float
    request_delay_seconds: float

    def available_providers(self) -> list[str]:
        """Return provider names whose required credentials are present."""
        out: list[str] = []
        if self.kiwi_api_key:
            out.append("kiwi")
        if self.amadeus_api_key and self.amadeus_api_secret:
            out.append("amadeus")
        if self.rapidapi_key:
            out.append("skyscanner")
        if self.serpapi_api_key:
            out.append("serpapi")
        return out


def load_app_config(env_path: Path | None = None) -> AppConfig:
    """Load runtime config from a .env file (if present) and env vars.

    Args:
        env_path: Optional explicit path to a .env file.

    Returns:
        Populated :class:`AppConfig`.
    """
    if env_path is not None:
        load_dotenv(env_path)
    else:
        load_dotenv()

    return AppConfig(
        kiwi_api_key=os.getenv("KIWI_TEQUILA_API_KEY") or None,
        amadeus_api_key=os.getenv("AMADEUS_API_KEY") or None,
        amadeus_api_secret=os.getenv("AMADEUS_API_SECRET") or None,
        amadeus_use_production=os.getenv("AMADEUS_USE_PRODUCTION", "").lower()
        in ("1", "true", "yes"),
        rapidapi_key=os.getenv("RAPIDAPI_KEY") or None,
        skyscanner_host=os.getenv("SKYSCANNER_RAPIDAPI_HOST", "skyscanner80.p.rapidapi.com"),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY") or None,
        exchangerate_api_key=os.getenv("EXCHANGERATE_API_KEY") or None,
        fx_commission=float(os.getenv("FX_COMMISSION", "0.015")),
        request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "1.0")),
    )


def load_search_from_yaml(path: Path) -> SearchConfig:
    """Load a :class:`SearchConfig` from a YAML file.

    Args:
        path: Filesystem path to the YAML config.

    Returns:
        A :class:`SearchConfig` built from the YAML contents.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return SearchConfig(
        origin=data["origin"],
        destination=data["destination"],
        depart_date=data["depart_date"],
        return_date=data.get("return_date"),
        passengers=int(data.get("passengers", 1)),
        cabin_class=data.get("cabin_class", "economy"),
        countries=list(data.get("countries", DEFAULT_COUNTRIES)),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="flight-price-comparator",
        description="Compare flight prices across point-of-sale countries.",
    )
    parser.add_argument("--config", type=Path, help="Path to a YAML config file.")
    parser.add_argument("--origin", type=str, help="Origin IATA code (e.g. MAD).")
    parser.add_argument("--destination", type=str, help="Destination IATA code (e.g. JFK).")
    parser.add_argument("--depart-date", type=str, help="Outbound date YYYY-MM-DD.")
    parser.add_argument("--return-date", type=str, default=None, help="Return date YYYY-MM-DD.")
    parser.add_argument("--passengers", type=int, default=1, help="Number of passengers.")
    parser.add_argument(
        "--cabin-class",
        type=str,
        default="economy",
        choices=list(VALID_CABIN_CLASSES),
        help="Cabin class.",
    )
    parser.add_argument(
        "--countries",
        type=str,
        nargs="+",
        default=None,
        help="ISO country codes to compare (e.g. ES IN TH).",
    )
    parser.add_argument(
        "--providers",
        type=str,
        nargs="+",
        default=None,
        choices=list(SUPPORTED_PROVIDERS),
        help="Providers to query. Defaults to every provider whose credentials are present.",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip rendering the matplotlib bar chart.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def search_from_args(args: argparse.Namespace) -> SearchConfig:
    """Build a :class:`SearchConfig` from parsed CLI args, optionally merging YAML.

    CLI flags take precedence over YAML values when both are provided.

    Args:
        args: Parsed argparse namespace.

    Returns:
        A populated :class:`SearchConfig`.
    """
    base: SearchConfig | None = None
    if args.config is not None:
        base = load_search_from_yaml(args.config)

    if base is None and not (args.origin and args.destination and args.depart_date):
        raise SystemExit(
            "Either --config or all of --origin, --destination, --depart-date are required."
        )

    return SearchConfig(
        origin=args.origin or (base.origin if base else ""),
        destination=args.destination or (base.destination if base else ""),
        depart_date=args.depart_date or (base.depart_date if base else ""),
        return_date=args.return_date if args.return_date else (base.return_date if base else None),
        passengers=args.passengers if args.passengers != 1 else (base.passengers if base else 1),
        cabin_class=args.cabin_class
        if args.cabin_class != "economy"
        else (base.cabin_class if base else "economy"),
        countries=args.countries or (base.countries if base else list(DEFAULT_COUNTRIES)),
    )
