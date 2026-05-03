# flight-price-comparator

Compare flight prices for the same itinerary across different **points of sale (PoS)** —
i.e. simulate being a user in different countries to spot pricing arbitrage.

> **Disclaimer.** This project is for **educational and research purposes** only. Always
> respect the Terms of Service of the APIs you use. Many fares carry restrictions tied to
> the country of purchase, the currency of the payment card, or the originating airport.
> Just because a price is cheaper from a given PoS does **not** guarantee you will be able
> to book and travel under that fare.

## Features

- **Multi-provider triangulation.** Query the same itinerary on **Kiwi Tequila**,
  **Amadeus**, **Skyscanner (via RapidAPI)** and **SerpAPI Google Flights** in a single
  run, then compare prices side-by-side per country to spot real PoS arbitrage vs.
  noise from a single source.
- Modular `PriceProvider` abstraction — adding a provider is one class.
- Per-country `market` / `partner_market` / `gl` / `currency` / `locale` overrides where
  the upstream API supports them. Providers honestly declare via
  `supports_market_switch` whether they actually vary the fare or just translate currency.
- FX conversion to EUR via [Frankfurter](https://www.frankfurter.app) (free, no key) or
  optionally [exchangerate-api.com](https://www.exchangerate-api.com).
- Configurable FX commission (default 1.5%) added on top of the converted price.
- Output: `rich` table in the terminal (one row per `provider × country`), timestamped
  CSV in `./results/`, and an optional `matplotlib` bar chart PNG.
- Logging via the standard `logging` module (no `print` calls).
- Type hints everywhere, Google-style docstrings, `ruff` linter, `pytest` tests.

## Project structure

```
flight-price-comparator/
├── .github/workflows/test.yml   # CI: ruff + pytest
├── src/
│   ├── config.py                # CLI / YAML / .env loading
│   ├── currency.py              # CurrencyConverter (Frankfurter / exchangerate-api)
│   ├── output.py                # rich table, CSV, matplotlib chart
│   ├── main.py                  # CLI entry point
│   └── providers/
│       ├── base.py              # PriceProvider / PriceQuote
│       ├── kiwi.py              # Kiwi Tequila
│       ├── amadeus.py           # Amadeus Self-Service
│       ├── skyscanner.py        # Skyscanner via RapidAPI
│       └── serpapi_flights.py   # SerpAPI Google Flights
├── tests/                       # pytest unit tests
├── results/                     # generated CSV + PNG land here (gitignored)
├── .env.example
├── requirements.txt
├── pyproject.toml               # ruff + pytest config
└── README.md
```

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/TheBadBenny/flight-price-comparator.git
cd flight-price-comparator

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your Kiwi Tequila API key
```

## Usage

CLI flags:

```bash
python -m src.main \
  --origin MAD \
  --destination JFK \
  --depart-date 2026-08-15 \
  --return-date 2026-08-29 \
  --passengers 1 \
  --cabin-class economy \
  --countries ES IN TH PL MX US TR BR
```

By default the script runs **every provider whose credentials are present in `.env`**.
Limit to a subset with `--providers`:

```bash
# Just Kiwi and Skyscanner:
python -m src.main --providers kiwi skyscanner --origin MAD --destination JFK --depart-date 2026-08-15
```

Valid provider keys: `kiwi`, `amadeus`, `skyscanner`, `serpapi`.

YAML config (see `examples/search.yml` style):

```yaml
origin: MAD
destination: JFK
depart_date: 2026-08-15
return_date: 2026-08-29
passengers: 1
cabin_class: economy
countries: [ES, IN, TH, PL, MX, US, TR, BR]
```

```bash
python -m src.main --config search.yml
```

Flags override YAML values when both are present. Add `--no-chart` to skip the PNG.

## Supported APIs

| API                                                          | Used for           | Free tier         | True PoS switching | How to get the key                                                                                              |
| ------------------------------------------------------------ | ------------------ | ----------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| [Kiwi Tequila](https://tequila.kiwi.com/portal/sign-up)      | Flight search      | Yes (limited)     | ✅ (`partner_market`) | Portal → My account → API keys → set `KIWI_TEQUILA_API_KEY`                                                    |
| [Amadeus Self-Service](https://developers.amadeus.com/register) | Flight search   | Yes (test env)    | ⚠️ currency only   | Register → "Self-Service" → create app → set `AMADEUS_API_KEY` and `AMADEUS_API_SECRET`                        |
| [Skyscanner (RapidAPI)](https://rapidapi.com/search/skyscanner) | Flight search    | Depends on host   | ✅ (`market`)      | Subscribe to a Skyscanner endpoint on RapidAPI → set `RAPIDAPI_KEY` and `SKYSCANNER_RAPIDAPI_HOST` to that host |
| [SerpAPI Google Flights](https://serpapi.com/users/sign_up)  | Flight search      | Yes (100/month)   | ✅ (`gl`+`currency`) | Sign up → dashboard → API key → set `SERPAPI_API_KEY`                                                          |
| [Frankfurter](https://www.frankfurter.app)                   | FX rates (default) | Yes, no key       | n/a                | n/a                                                                                                              |
| [exchangerate-api.com](https://www.exchangerate-api.com)     | FX rates (alt.)    | Yes (limited)     | n/a                | Sign up → free plan → set `EXCHANGERATE_API_KEY`                                                                 |

### Notes per provider

- **Kiwi Tequila** is the cleanest source for PoS arbitrage: it accepts a real
  `partner_market` plus matching `curr` and `locale`.
- **Amadeus** does **not** vary fares by PoS in the public API — it accepts a
  `currencyCode` and the underlying contract usually returns the same total in different
  currencies. We still query per country for triangulation; treat differences here as FX
  noise rather than evidence of arbitrage.
- **Skyscanner via RapidAPI**: there are several "Skyscanner" hosts on RapidAPI and they
  drift over time. The default `skyscanner80.p.rapidapi.com` works for the round-trip /
  one-way search shape implemented here; if you subscribe to a different host change
  `SKYSCANNER_RAPIDAPI_HOST` accordingly. Skyscanner natively supports `market`, `currency`
  and `locale`, so this is a strong PoS source.
- **SerpAPI Google Flights**: scrapes Google Flights and exposes `gl` (country) and
  `currency`. Reflects what a Google user in that country sees.

## Configuration reference (`.env`)

| Variable                       | Default                         | Description                                                                |
| ------------------------------ | ------------------------------- | -------------------------------------------------------------------------- |
| `KIWI_TEQUILA_API_KEY`         | _empty_                         | Enables the Kiwi Tequila provider.                                         |
| `AMADEUS_API_KEY`              | _empty_                         | Enables Amadeus (with `AMADEUS_API_SECRET`).                               |
| `AMADEUS_API_SECRET`           | _empty_                         | Amadeus client secret.                                                     |
| `AMADEUS_USE_PRODUCTION`       | `false`                         | Set to `true` to hit `api.amadeus.com` instead of the test env.            |
| `RAPIDAPI_KEY`                 | _empty_                         | Enables the Skyscanner provider via RapidAPI.                              |
| `SKYSCANNER_RAPIDAPI_HOST`     | `skyscanner80.p.rapidapi.com`   | The Skyscanner host on RapidAPI you've subscribed to.                      |
| `SERPAPI_API_KEY`              | _empty_                         | Enables the SerpAPI Google Flights provider.                               |
| `EXCHANGERATE_API_KEY`         | _empty_                         | If set, FX uses exchangerate-api.com; otherwise Frankfurter.               |
| `FX_COMMISSION`                | `0.015`                         | Multiplicative FX commission (1.5% by default).                            |
| `REQUEST_DELAY_SECONDS`        | `1.0`                           | Sleep between provider calls (rate-limit friendliness).                    |

The script auto-discovers which providers to run based on the keys above; at least one
provider must be configured.

## Development

```bash
pip install -r requirements.txt
ruff check .
pytest
```

## Known limitations

- **Bookability ≠ visibility.** Some fares are only sold to residents of the PoS country,
  to cards issued there, or to itineraries that originate there. Lower price found ≠ you
  can buy it.
- **Payment restrictions.** Many airlines block foreign cards, run 3-D Secure on the
  issuing country, or require billing addresses in the PoS country.
- **Aggregator caching.** Tequila aggregates many providers; cached results may not be
  identical to a freshly issued ticket on the airline website.
- **Rate limits.** Tequila and the FX APIs throttle aggressively; `REQUEST_DELAY_SECONDS`
  exists to be a polite citizen. Increase it if you see HTTP 429s.
- **Provider parity.** Not every PoS is implemented for every provider. Providers that
  cannot truly switch market must set `supports_market_switch = False` and should be
  treated as informational only.

## License

This project ships without a specific license file — treat it as "all rights reserved"
until you add one. Use of third-party APIs is subject to their own ToS.
