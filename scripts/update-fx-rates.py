#!/usr/bin/env python3
"""Refresh ``bristlenose/llm/fx-rates.json`` from the ECB's reference rates.

The usage API converts USD prices into the researcher's currency with this
table (docs/design-llm-usage.md, layer 2). It is bundled, not fetched by the
app: the network call happens here, on the maintainer's machine, so no
installed copy of Bristlenose makes a request for it. A stale table is shown
as stale, because every converted figure carries the table's ``as_of`` date.

Run by hand before a release (``docs/release.md``)::

    .venv/bin/python scripts/update-fx-rates.py
    .venv/bin/python scripts/update-fx-rates.py --from-file eurofxref-daily.xml

The ECB publishes euro-based rates for about 30 currencies each working day
(https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/).
Every provider bills API use in US dollars, so the table is rebased to USD.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
OUT = Path(__file__).resolve().parent.parent / "bristlenose" / "llm" / "fx-rates.json"


def parse(xml_bytes: bytes) -> tuple[str, dict[str, float]]:
    """The ECB file's date and its euro-based rates, EUR itself included."""
    root = ET.fromstring(xml_bytes)
    dated = [c for c in root.iter(f"{_NS}Cube") if c.get("time")]
    if len(dated) != 1:
        raise ValueError(f"expected one dated Cube, found {len(dated)}")
    day = dated[0]
    per_eur = {"EUR": 1.0}
    for cube in day:
        code, rate = cube.get("currency"), cube.get("rate")
        if code and rate:
            per_eur[code] = float(rate)
    return str(day.get("time")), per_eur


def rebase_to_usd(per_eur: dict[str, float]) -> dict[str, float]:
    """Units of each currency per US dollar."""
    usd = per_eur.get("USD")
    if not usd or usd <= 0:
        raise ValueError("the ECB file has no positive USD rate")
    return {code: round(rate / usd, 6) for code, rate in sorted(per_eur.items())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from-file", type=Path, help="parse a saved ECB daily XML instead of fetching")
    args = ap.parse_args()
    if args.from_file:
        raw = args.from_file.read_bytes()
    else:
        with urllib.request.urlopen(ECB_DAILY, timeout=20) as resp:  # noqa: S310 (fixed https URL)
            raw = resp.read(1_000_000)
    as_of, per_eur = parse(raw)
    rates = rebase_to_usd(per_eur)
    rates["USD"] = 1.0
    payload = {
        "_doc": (
            "Units of each currency per US dollar, rebased from the European Central Bank's "
            "euro reference rates by scripts/update-fx-rates.py. Read by bristlenose/llm/money.py. "
            "Bundled, never fetched by the app; every converted figure carries as_of."
        ),
        "schema_version": 1,
        "base": "USD",
        "as_of": as_of,
        "source": "European Central Bank euro reference rates, rebased to USD",
        "rates": dict(sorted(rates.items())),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(OUT.parent.parent.parent)}: {len(rates)} currencies as of {as_of}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
