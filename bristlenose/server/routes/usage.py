"""A study's LLM use, priced: the data under any usage surface.

``GET /api/projects/{project_id}/usage?currency=GBP`` (docs/design-llm-usage.md).
This is plumbing for a surface the owner has not chosen: it answers what was
used and what it cost, and draws nothing.

Three sources, because use is recorded in three places at three speeds:

- **rows**: the study's ledger, ``.bristlenose/usage.jsonl``, one row per
  finished job from any process (a CLI run, the Mac's run, this serve's jobs);
- **in_flight, this server**: jobs running in this process (AutoCode,
  elaboration, chat, codebook builder), read from the ledger's live tally;
- **in_flight, pipeline run**: a run in its own process, read from the newest
  ``run_progress`` line, whose ``usage_*`` fields carry its use so far summed
  over models (so it has tokens and no price).

Every figure is re-read per request, so a client polls; the ``ETag`` is a hash
of the body, and ``If-None-Match`` answers 304, so a poll every few seconds
costs a stat and a hash. Money is computed here from tokens at read time
(``money.py``): rows store no price, so a newer price table re-prices history
and a price change never rewrites old spend. Rounding is the client's.

Never in an export (``routes/export.py`` SERVER_ONLY): it is the operator's
information, not part of a deliverable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.events import RunProgressEvent, events_path
from bristlenose.llm import money, usage
from bristlenose.server.models import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

#: How much of the events log is read to find the newest progress line. A run's
#: lines are ~400 B and arrive per stage and session, so this holds hundreds.
_EVENTS_TAIL_BYTES = 256 * 1024


class PriceOut(BaseModel):
    status: money.PriceStatus
    #: USD at the price in force on the row's day; null when unpriced.
    cost_usd: float | None
    #: In ``currency``; null when unpriced or no conversion is available.
    cost: float | None
    #: Some cached tokens had no cache rate on record and were priced at the
    #: full input rate: the figure is an upper bound.
    cache_priced_at_input_rate: bool = False


class Counts(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    calls_without_usage: int


class RowOut(Counts):
    ts: str
    run_id: str
    kind: str
    provider: str
    model: str
    price: PriceOut


class TotalOut(Counts):
    provider: str
    model: str
    jobs: int
    price: PriceOut


class InFlightOut(BaseModel):
    source: Literal["this_server", "pipeline_run"]
    run_id: str
    kind: str
    #: Null for a pipeline run: its progress line sums its models.
    provider: str | None
    model: str | None
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    calls_without_usage: int | None
    price: PriceOut | None


class UsageResponse(BaseModel):
    schema_version: int = 1
    #: The currency every ``cost`` is in: the one asked for, or USD.
    currency: str
    conversion: money.Conversion | None
    #: The currency asked for when no rate is held for it; ``cost`` is then USD.
    currency_unavailable: str | None = None
    price_table_version: str
    rows: list[RowOut]
    totals: list[TotalOut]
    in_flight: list[InFlightOut]


def _project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _price(
    provider: str, model: str, on: date, counts: Counts | usage.UsageRow | usage.InFlight,
    conv: money.Conversion | None,
) -> PriceOut:
    p = money.price_tokens(
        provider, model, on,
        input_tokens=counts.input_tokens,
        output_tokens=counts.output_tokens,
        cache_read_input_tokens=counts.cache_read_input_tokens,
        cache_creation_input_tokens=counts.cache_creation_input_tokens,
    )
    rate = conv.rate if conv is not None else 1.0
    return PriceOut(
        status=p.status,
        cost_usd=p.cost_usd,
        cost=p.cost_usd * rate if p.cost_usd is not None else None,
        cache_priced_at_input_rate=p.cache_priced_at_input_rate,
    )


def _row_day(ts: str) -> date:
    try:
        return date.fromisoformat(ts[:10])
    except ValueError:
        return datetime.now(timezone.utc).date()


def _live_pipeline_usage(output_dir: Path) -> InFlightOut | None:
    """The in-flight run's use so far, from its newest progress line.

    Walks the log's tail backwards: a terminus or a ``run_started`` reached
    before any progress line means no use is on record for a live run yet.
    """
    from bristlenose.run_lifecycle import run_in_progress

    if not run_in_progress(output_dir):
        return None
    path = events_path(output_dir)
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _EVENTS_TAIL_BYTES))
            tail = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind_of_line = raw.get("event") if isinstance(raw, dict) else None
        if kind_of_line != "run_progress":
            return None  # a lifecycle line first: nothing in flight on record
        ev = RunProgressEvent.model_validate(raw)
        if not ev.usage_calls:
            return None
        return InFlightOut(
            source="pipeline_run", run_id=ev.run_id, kind=ev.kind.value,
            provider=None, model=None, calls=ev.usage_calls,
            input_tokens=ev.usage_input_tokens or 0,
            output_tokens=ev.usage_output_tokens or 0,
            cache_read_input_tokens=ev.usage_cache_read_input_tokens or 0,
            cache_creation_input_tokens=ev.usage_cache_creation_input_tokens or 0,
            calls_without_usage=None, price=None,
        )
    return None


def build_usage(output_dir: Path, currency: str | None) -> UsageResponse:
    """The response body: separate from the route so tests and other readers
    (a future CLI or MCP view) share one computation."""
    asked = (currency or "USD").upper()
    conv = money.conversion(asked)
    run_dir = output_dir / ".bristlenose"

    rows: list[RowOut] = []
    for r in usage.read_rows(run_dir):
        rows.append(RowOut(**r.model_dump(exclude={"schema_version"}),
                           price=_price(r.provider, r.model, _row_day(r.ts), r, conv)))

    totals: list[TotalOut] = []
    for t in usage.study_totals(usage.read_rows(run_dir)):
        mine = [r for r in rows if (r.provider, r.model) == (t.provider, t.model)]
        priced = [r.price for r in mine]
        status = priced[0].status if priced else "unpriced"
        usd = (sum(p.cost_usd for p in priced if p.cost_usd is not None)
               if status != "unpriced" else None)
        totals.append(TotalOut(
            **t.model_dump(),
            price=PriceOut(
                status=status, cost_usd=usd,
                cost=usd * conv.rate if (usd is not None and conv) else usd,
                cache_priced_at_input_rate=any(p.cache_priced_at_input_rate for p in priced),
            ),
        ))

    today = datetime.now(timezone.utc).date()
    in_flight: list[InFlightOut] = [
        InFlightOut(source="this_server", **f.model_dump(),
                    price=_price(f.provider, f.model, today, f, conv))
        for f in usage.peek(run_dir)
    ]
    live = _live_pipeline_usage(output_dir)
    if live is not None:
        in_flight.append(live)

    return UsageResponse(
        currency=conv.currency if conv else "USD",
        conversion=conv,
        currency_unavailable=None if conv else asked,
        price_table_version=money.price_table().price_table_version,
        rows=rows, totals=totals, in_flight=in_flight,
    )


@router.get("/projects/{project_id}/usage", response_model=UsageResponse)
def get_usage(
    project_id: int, request: Request, response: Response, currency: str | None = None,
) -> UsageResponse | Response:
    db: Session = request.app.state.db_factory()
    try:
        project = _project(db, project_id)
        output_dir = Path(project.output_dir)
    finally:
        db.close()
    body = build_usage(output_dir, currency)
    etag = '"' + hashlib.sha256(body.model_dump_json().encode("utf-8")).hexdigest()[:32] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return body
