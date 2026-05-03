# flight-price-comparator

Compare flight prices for the same itinerary across different **points of sale (PoS)** —
i.e. simulate being a user in different countries to spot pricing arbitrage.

> **Disclaimer.** This project is for **educational and research purposes** only. Always
> respect the Terms of Service of the APIs you use. Many fares carry restrictions tied to
> the country of purchase, the currency of the payment card, or the originating airport.
> Just because a price is cheaper from a given PoS does **not** guarantee you will be able
> to book and travel under that fare.

## Features

- Modular `PriceProvider` abstraction — Kiwi Tequila is the default; Amadeus / Skyscanner
  / others can be plugged in by implementing a single class.
- Per-country `partner_market`, `curr` and `locale` overrides on Kiwi Tequila.
- FX conversion to EUR via [Frankfurter](https://www.frankfurter.app) (free, no key) or
  optionally [exchangerate-api.com](https://www.exchangerate-api.com).
- Configurable FX commission (default 1.5%) added on top of the converted price.
- Output: `rich` table in the terminal, timestamped CSV in `./results/`, and an optional
  `matplotlib` bar chart PNG.
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
│       └── kiwi.py              # Kiwi Tequila implementation
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

| API                                                      | Used for         | Free tier           | Where to get the key                                                                    |
| -------------------------------------------------------- | ---------------- | ------------------- | --------------------------------------------------------------------------------------- |
| [Kiwi Tequila](https://tequila.kiwi.com/portal/sign-up)  | Flight search    | Yes (limited)       | Sign up at the portal → "My account" → API keys                                         |
| [Frankfurter](https://www.frankfurter.app)               | FX rates (default) | Yes, no key needed | n/a                                                                                     |
| [exchangerate-api.com](https://www.exchangerate-api.com) | FX rates (alt.)    | Yes (limited)       | Sign up → free plan → copy the key from the dashboard                                   |

The Kiwi Tequila API supports `partner_market`, `curr` and `locale`, which is what makes
PoS comparison possible. **Amadeus** and **Skyscanner RapidAPI** are good candidates to add
later: implement `src/providers/base.py:PriceProvider` and register it in `main.py`.

## Configuration reference (`.env`)

| Variable                | Default          | Description                                              |
| ----------------------- | ---------------- | -------------------------------------------------------- |
| `KIWI_TEQUILA_API_KEY`  | _required_       | Tequila Search API key.                                  |
| `EXCHANGERATE_API_KEY`  | _empty_          | If set, FX uses exchangerate-api.com; otherwise Frankfurter. |
| `FX_COMMISSION`         | `0.015`          | Multiplicative FX commission (1.5% by default).          |
| `REQUEST_DELAY_SECONDS` | `1.0`            | Sleep between provider calls (rate-limit friendliness).  |

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
