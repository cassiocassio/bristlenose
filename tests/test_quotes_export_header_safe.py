"""A quotes export's caller-supplied header row is formula-safe like the data rows (T25).

The headings arrive in the query string (``col_headers``, the SPA's translated words). The
data rows went through ``csv_safe``; the header row did not, so a heading that starts with
``=``, ``+``, ``-`` or ``@`` was written as a formula to a spreadsheet that evaluates it.
"""

from __future__ import annotations

import csv
import io
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.routes.quotes_export import _DEFAULT_HEADERS
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_Q = "q-p1-46"
_EVIL = ['=HYPERLINK("http://example.invalid","x")', "+1", "-2", "@SUM(1)"]


@pytest.fixture()
def client() -> TestClient:
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://"))


def _headers(first: str) -> str:
    return ",".join([first, *_DEFAULT_HEADERS[1:]])


@pytest.mark.parametrize("evil", [e.replace(",", ";") for e in _EVIL])
def test_the_csv_header_row_is_formula_safe(client: TestClient, evil: str) -> None:
    resp = client.get("/api/projects/1/export/quotes.csv",
                      params={"quote_ids": _Q, "col_headers": _headers(evil)})
    assert resp.status_code == 200, resp.text
    first = next(csv.reader(io.StringIO(resp.text.lstrip("﻿"))))[0]
    assert first[0] not in "=+-@", first
    assert first.lstrip("\t") == evil


@pytest.mark.parametrize("evil", [e.replace(",", ";") for e in _EVIL])
def test_the_xlsx_header_row_is_formula_safe(client: TestClient, evil: str) -> None:
    from openpyxl import load_workbook

    resp = client.get("/api/projects/1/export/quotes.xlsx",
                      params={"quote_ids": _Q, "col_headers": _headers(evil)})
    assert resp.status_code == 200, resp.text
    cell = load_workbook(BytesIO(resp.content)).active["A1"].value
    assert cell[0] not in "=+-@", cell
    assert cell.lstrip("\t") == evil


def test_an_ordinary_translated_heading_is_unchanged(client: TestClient) -> None:
    resp = client.get("/api/projects/1/export/quotes.csv",
                      params={"quote_ids": _Q, "col_headers": ",".join(_DEFAULT_HEADERS)})
    assert next(csv.reader(io.StringIO(resp.text.lstrip("﻿")))) == list(_DEFAULT_HEADERS)


def test_a_control_character_in_a_heading_does_not_break_the_xlsx(client: TestClient) -> None:
    resp = client.get("/api/projects/1/export/quotes.xlsx",
                      params={"quote_ids": _Q, "col_headers": _headers("Quote\x01")})
    assert resp.status_code == 200, resp.text
