"""Tests for the Skyscanner scraper's pure parsing helpers."""

from __future__ import annotations

from src.config import SearchConfig
from src.providers.skyscanner_scraper import (
    COUNTRY_TO_LOCALE,
    build_search_url,
    extract_prices,
)


def test_build_search_url_oneway_es():
    s = SearchConfig(
        origin="MAD",
        destination="JFK",
        depart_date="2026-08-15",
        passengers=1,
        cabin_class="economy",
    )
    url = build_search_url(s, COUNTRY_TO_LOCALE["ES"])
    assert url == (
        "https://www.skyscanner.es/transport/flights/mad/jfk/260815/"
        "?adults=1&cabinclass=economy&currency=EUR"
    )


def test_build_search_url_roundtrip_in_business():
    s = SearchConfig(
        origin="DEL",
        destination="LHR",
        depart_date="2026-09-01",
        return_date="2026-09-20",
        passengers=2,
        cabin_class="business",
    )
    url = build_search_url(s, COUNTRY_TO_LOCALE["IN"])
    assert url == (
        "https://www.skyscanner.co.in/transport/flights/del/lhr/260901/260920/"
        "?adults=2&cabinclass=business&currency=INR"
    )


def test_extract_prices_eur_es_format():
    text = "Vuelos desde € 612,40 hasta €1.234,00 — promo €5,00"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["ES"])
    # 5,00 is filtered (below 30 floor); 612,40 and 1234,00 remain
    assert prices == [612.40, 1234.00]


def test_extract_prices_usd_us_format():
    text = "From $499.50 to $1,234.50 today only"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["US"])
    assert prices == [499.50, 1234.50]


def test_extract_prices_inr_symbol_before():
    text = "Cheapest ₹ 32,500 round trip; ₹45,000 for direct"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["IN"])
    assert prices == [32500.0, 45000.0]


def test_extract_prices_pln_symbol_after():
    text = "Najtaniej 2 450,99 zł a najdrożej 3 800,00 zł"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["PL"])
    assert prices == [2450.99, 3800.00]


def test_extract_prices_brl_symbol_before():
    text = "A partir de R$ 1.999,90 ou R$ 2.450,00"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["BR"])
    assert prices == [1999.90, 2450.00]


def test_extract_prices_filters_low_noise():
    text = "Promo €5 €10 €25 — desde €450,00"
    prices = extract_prices(text, COUNTRY_TO_LOCALE["ES"])
    assert prices == [450.00]


def test_extract_prices_empty_text():
    assert extract_prices("", COUNTRY_TO_LOCALE["ES"]) == []
    assert extract_prices("no prices here", COUNTRY_TO_LOCALE["ES"]) == []
