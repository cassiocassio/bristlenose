"""Tokens to money: the price in force on a day, in the researcher's currency.

Layer 2 of three (``docs/design-llm-usage.md``). Layer 1 (``usage.py``)
counts tokens and knows no price; layer 3, where any of it is shown, is the
owner's. This module turns counts into an estimate and says what the estimate
rests on: which price table, which day's price, which exchange rate and its
date, and anything it had to assume.

**Prices change, so a count is priced at the price of its day.** The bundled
``pricing.json`` keeps dated prices per model; :func:`price_on` picks the one
in force on a date. The ledger stores tokens, never money, so a release with a
newer table re-prices every study, and a price change never rewrites what was
already spent at the old price. Nothing here reads the wall clock:
"today's price" is the price in force on the table's own version date.

**Lookup is exact.** A model is priced only by its exact id under its own
provider. No family or alias matching: Gemini 3.5 Flash and 3.8 Flash share a
family and not a price. An Azure deployment name and an any-llm route are
never priced (``unpriced``); a local model is ``free``.

**Currency.** Every provider bills API use in US dollars, so prices are USD
and conversion is a display convenience, with ECB reference rates bundled by
``scripts/update-fx-rates.py``. The caller names the currency; nothing here
guesses one from a locale.

Both files are bundled and never fetched: whether to fetch fresher prices is
``docs/design-llm-pricing-fetch.md``, an egress decision for the owner.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

_PRICES_PATH = Path(__file__).parent / "pricing.json"
_FX_PATH = Path(__file__).parent / "fx-rates.json"

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")

PriceStatus = Literal["priced", "free", "unpriced"]


class PriceEntry(BaseModel):
    """One model's price from a date on, USD per million tokens."""

    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(alias="from")
    input: float = Field(ge=0, le=10_000)
    output: float = Field(ge=0, le=10_000)
    cache_read: float | None = Field(default=None, ge=0, le=10_000)
    cache_write: float | None = Field(default=None, ge=0, le=10_000)
    #: The last day this price is known to hold, for a price published with an
    #: end (a promotion). After it, with no later entry, the model is
    #: ``unpriced``: a promotional rate is not carried past its end as if it
    #: were the price.
    until: date | None = None


class ModelPrices(BaseModel):
    provider: str
    prices: list[PriceEntry] = Field(min_length=1)

    @field_validator("prices")
    @classmethod
    def _dated_in_order(cls, v: list[PriceEntry]) -> list[PriceEntry]:
        days = [e.from_ for e in v]
        if days != sorted(set(days)):
            raise ValueError("prices must be in date order, one per date")
        return v


class PriceTable(BaseModel):
    schema_version: Literal[1]
    price_table_version: str
    currency: Literal["USD"]
    unit: Literal["usd_per_million_tokens"]
    free_providers: list[str]
    models: dict[str, ModelPrices]

    @field_validator("price_table_version")
    @classmethod
    def _iso_day(cls, v: str) -> str:
        if not _ISO_DAY.match(v):
            raise ValueError("price_table_version must be an ISO date")
        return v


class FxTable(BaseModel):
    schema_version: Literal[1]
    base: Literal["USD"]
    as_of: str
    source: str
    rates: dict[str, float]

    @field_validator("rates")
    @classmethod
    def _sane(cls, v: dict[str, float]) -> dict[str, float]:
        for code, rate in v.items():
            if not _CURRENCY.match(code) or not (0 < rate < 1_000_000):
                raise ValueError(f"bad rate {code}={rate}")
        if v.get("USD") != 1.0:
            raise ValueError("a USD-based table has USD = 1")
        return v


_EMPTY_PRICES = PriceTable(
    schema_version=1, price_table_version="1970-01-01", currency="USD",
    unit="usd_per_million_tokens", free_providers=[], models={},
)


@lru_cache(maxsize=1)
def price_table() -> PriceTable:
    """The bundled price table. A missing or broken file is a packaging fault:
    logged at ERROR, and every model then reads as unpriced rather than at a
    made-up price."""
    try:
        return PriceTable.model_validate(json.loads(_PRICES_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError):
        logger.error("price table unreadable at %s — every model unpriced", _PRICES_PATH,
                     exc_info=True)
        return _EMPTY_PRICES


@lru_cache(maxsize=1)
def fx_table() -> FxTable | None:
    """The bundled exchange rates, or None (logged) if they cannot be read."""
    try:
        return FxTable.model_validate(json.loads(_FX_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError):
        logger.error("exchange rates unreadable at %s — USD only", _FX_PATH, exc_info=True)
        return None


def price_on(
    provider: str, model: str, on: date, table: PriceTable | None = None,
) -> PriceEntry | PriceStatus:
    """The price in force for *model* on *on*, or ``"free"`` / ``"unpriced"``."""
    t = table if table is not None else price_table()
    if provider in t.free_providers:
        return "free"
    entry = t.models.get(model)
    if entry is None or entry.provider != provider:
        return "unpriced"
    in_force = entry.prices[0]  # the earliest also covers every earlier day
    for e in entry.prices:
        if e.from_ <= on:
            in_force = e
    if in_force.until is not None and on > in_force.until:
        return "unpriced"
    return in_force


def table_day(table: PriceTable | None = None) -> date:
    """The table's own "today": its version date."""
    t = table if table is not None else price_table()
    return date.fromisoformat(t.price_table_version)


class Price(BaseModel):
    """What some token counts cost, and what the figure rests on."""

    status: PriceStatus
    cost_usd: float | None
    #: Cached tokens with no cache rate on record were priced at the full
    #: input rate: the figure is then an upper bound.
    cache_priced_at_input_rate: bool = False


def price_tokens(
    provider: str,
    model: str,
    on: date,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    table: PriceTable | None = None,
) -> Price:
    """Price token counts (the ledger's normalised meanings) as of *on*."""
    p = price_on(provider, model, on, table)
    if p == "free":
        return Price(status="free", cost_usd=0.0)
    if p == "unpriced" or isinstance(p, str):
        return Price(status="unpriced", cost_usd=None)
    assumed = (cache_read_input_tokens > 0 and p.cache_read is None) or (
        cache_creation_input_tokens > 0 and p.cache_write is None
    )
    cr = p.cache_read if p.cache_read is not None else p.input
    cw = p.cache_write if p.cache_write is not None else p.input
    usd = (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_read_input_tokens * cr
        + cache_creation_input_tokens * cw
    ) / 1_000_000
    return Price(status="priced", cost_usd=usd, cache_priced_at_input_rate=assumed)


class Conversion(BaseModel):
    currency: str
    rate: float
    as_of: str
    source: str


def conversion(currency: str, fx: FxTable | None = None) -> Conversion | None:
    """How to turn USD into *currency* (an ISO 4217 code), or None if unknown."""
    code = currency.upper()
    if not _CURRENCY.match(code):
        return None
    table = fx if fx is not None else fx_table()
    if table is None or code not in table.rates:
        return None
    return Conversion(currency=code, rate=table.rates[code], as_of=table.as_of,
                      source=table.source)
