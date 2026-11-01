"""A quotes spreadsheet names its sentiments in the report's language (N177, owner 1 Nov 2026).

The column headings were translated (the SPA sends them) but each sentiment was written as its
English key ("delight") under them. The sentiment words the report already shows live in
``locales/<lang>/enums.json``, so the export takes a ``lang`` and uses them: no new words.
English, and no ``lang`` at all, keep the key as written before. The Starred column's "Yes"
stays English until a word is approved for 21 locales.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_Q = "q-p1-46"  # the smoke fixture's delight quote


@pytest.fixture()
def client() -> TestClient:
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://"))


def _csv_sentiments(client: TestClient, **params: str) -> list[str]:
    resp = client.get("/api/projects/1/export/quotes.csv", params={"quote_ids": _Q, **params})
    assert resp.status_code == 200, resp.text
    rows = list(csv.reader(io.StringIO(resp.text.lstrip("﻿"))))
    col = rows[0].index("Sentiment")
    return [r[col] for r in rows[1:]]


def test_a_french_export_writes_the_sentiment_in_french(client: TestClient) -> None:
    assert _csv_sentiments(client, lang="fr") == ["Enchantement"]


def test_a_forgiven_spelling_of_the_language_works_too(client: TestClient) -> None:
    assert _csv_sentiments(client, lang="FR_fr.UTF-8") == ["Enchantement"]


def test_english_and_no_language_keep_the_key_as_before(client: TestClient) -> None:
    assert _csv_sentiments(client) == ["delight"]
    assert _csv_sentiments(client, lang="en") == ["delight"]


def test_an_unknown_language_is_english_not_an_error(client: TestClient) -> None:
    assert _csv_sentiments(client, lang="zz") == ["delight"]


def test_the_xlsx_writes_it_in_the_language_too(client: TestClient) -> None:
    from io import BytesIO

    from openpyxl import load_workbook

    resp = client.get(
        "/api/projects/1/export/quotes.xlsx", params={"quote_ids": _Q, "lang": "fr"},
    )
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    header = [c.value for c in ws[1]]
    assert ws.cell(row=2, column=header.index("Sentiment") + 1).value == "Enchantement"


def test_the_starred_word_is_still_english(client: TestClient) -> None:
    client.patch("/api/projects/1/starred", json={_Q: True})
    resp = client.get(
        "/api/projects/1/export/quotes.csv", params={"quote_ids": _Q, "lang": "fr"},
    )
    rows = list(csv.reader(io.StringIO(resp.text.lstrip("﻿"))))
    assert rows[1][rows[0].index("Starred")] == "Yes"


def test_a_sentiment_with_no_translation_keeps_its_key_not_a_raw_lookup_string() -> None:
    from bristlenose.server.routes.quotes_export import _sentiment_word

    assert _sentiment_word("fr", "nonsense") == "nonsense"
    assert _sentiment_word("fr", "") == ""
