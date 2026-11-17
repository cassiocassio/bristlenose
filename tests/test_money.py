"""Tokens to money (layer 2, docs/design-llm-usage.md).

The contract's ``pricing_case`` is the shared expectation for any reader; the
rest pins the rules that make a figure honest: the price of the row's day,
exact-id lookup only, no wall clock, and the REAL bundled tables (a data file
stubbed in every test is how ``cohort-baselines.json`` shipped empty for five
months, ``bristlenose/llm/gotchas.md``).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from bristlenose.llm import money, pricing

_CASE = json.loads(
    (Path(__file__).parent / "fixtures" / "usage-ledger-contract.json").read_text(
        encoding="utf-8"
    )
)["pricing_case"]


class TestTheContractCase:
    def test_each_row_prices_to_the_expected_figure(self) -> None:
        table = money.PriceTable.model_validate(_CASE["price_table"])
        fx = money.FxTable.model_validate(_CASE["fx"])
        conv = money.conversion(_CASE["currency"], fx)
        assert conv is not None
        for row, want in zip(_CASE["rows"], _CASE["expected"], strict=True):
            got = money.price_tokens(
                row["provider"], row["model"], date.fromisoformat(row["day"]),
                input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
                cache_read_input_tokens=row["cache_read_input_tokens"],
                cache_creation_input_tokens=row["cache_creation_input_tokens"],
                table=table,
            )
            assert got.status == want["status"], row
            assert got.cache_priced_at_input_rate == want["cache_priced_at_input_rate"], row
            if want["cost_usd"] is None:
                assert got.cost_usd is None
            else:
                assert got.cost_usd == pytest.approx(want["cost_usd"])
                assert got.cost_usd * conv.rate == pytest.approx(want["cost"])


class TestLookup:
    def _table(self) -> money.PriceTable:
        return money.PriceTable.model_validate(_CASE["price_table"])

    def test_no_family_fallback(self) -> None:
        """Gemini 3.5 Flash, 3.8 Flash and 3.5 Flash Lite share a cohort family
        and not a price; matching on the family would price the wrong model."""
        assert money.price_on("google", "m-g-lite", date(2026, 6, 1), self._table()) == "unpriced"

    def test_a_deployment_named_like_a_model_is_not_that_model(self) -> None:
        assert money.price_on("azure", "m-o", date(2026, 6, 1), self._table()) == "unpriced"

    def test_a_price_change_applies_from_its_day_not_before(self) -> None:
        t = self._table()
        before = money.price_on("anthropic", "m-a", date(2026, 6, 30), t)
        after = money.price_on("anthropic", "m-a", date(2026, 7, 1), t)
        assert isinstance(before, money.PriceEntry) and before.input == 3.0
        assert isinstance(after, money.PriceEntry) and after.input == 1.5

    def test_prices_must_be_in_date_order(self) -> None:
        bad = json.loads(json.dumps(_CASE["price_table"]))
        bad["models"]["m-a"]["prices"].reverse()
        with pytest.raises(ValueError):
            money.PriceTable.model_validate(bad)


class TestConversion:
    def test_unknown_and_malformed_currencies_convert_to_nothing(self) -> None:
        fx = money.FxTable.model_validate(_CASE["fx"])
        assert money.conversion("XYZ", fx) is None
        assert money.conversion("gb", fx) is None
        assert money.conversion("../etc", fx) is None

    def test_lower_case_is_accepted(self) -> None:
        fx = money.FxTable.model_validate(_CASE["fx"])
        conv = money.conversion("gbp", fx)
        assert conv is not None and conv.currency == "GBP"


class TestTheBundledTables:
    """The real files, as they ship."""

    def test_the_price_table_loads_and_feeds_pricing(self) -> None:
        table = money.price_table()
        assert table.models, "pricing.json is empty or unreadable — nothing can be priced"
        assert pricing.PRICE_TABLE_VERSION == table.price_table_version
        assert set(pricing.PRICING) == set(table.models)

    def test_every_provider_named_is_one_bristlenose_calls(self) -> None:
        from bristlenose.providers import PROVIDERS

        for model, entry in money.price_table().models.items():
            assert entry.provider in PROVIDERS, (model, entry.provider)

    def test_pricing_does_not_read_the_wall_clock(self) -> None:
        """PRICING is the price in force on the table's own version day, so a
        serve running across a price change and a test agree until a release
        changes the file."""
        day = money.table_day()
        for model, (rate_in, rate_out) in pricing.PRICING.items():
            entry = money.price_on(money.price_table().models[model].provider, model, day)
            assert isinstance(entry, money.PriceEntry)
            assert (entry.input, entry.output) == (rate_in, rate_out)

    def test_the_exchange_rates_load(self) -> None:
        fx = money.fx_table()
        assert fx is not None, "fx-rates.json is missing or unreadable"
        date.fromisoformat(fx.as_of)
        assert fx.rates["USD"] == 1.0
        assert {"EUR", "GBP", "JPY"} <= set(fx.rates)

    def test_local_is_free(self) -> None:
        assert money.price_on("local", "llama3.2:3b", money.table_day()) == "free"


class TestAPriceWithAnEnd:
    def test_a_promotion_is_not_carried_past_its_end(self) -> None:
        """The Gemini 3.x rows are promotional through 31 Dec 2026. Carried on,
        a January row would read as priced at about half its cost (review,
        17 Nov 2026)."""
        for model, entry in money.price_table().models.items():
            if model.startswith("gemini-3"):
                assert entry.prices[-1].until is not None, model
        assert money.price_on("google", "gemini-3.8-flash", date(2027, 1, 1)) == "unpriced"
        last = money.price_on("google", "gemini-3.8-flash", date(2026, 12, 31))
        assert isinstance(last, money.PriceEntry)
