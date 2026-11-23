"""AutoCode landing, Phase 4a: the server half of live landing (docs/design-autocode-landing-plan.md).

A first apply sends its quotes in stored order (D25), in batches of 5, then 10, then 25
(D24); a catch-up keeps 25. As each batch is saved it accepts, in the same transaction,
the run's pending proposals at or above a live line (D6): the hybrid's own line over
the proposals so far, not below 0.80 until 25 have landed, and never falling during the
run (lead's refinement, 23 Nov 2026). An accepted tag is never taken back, so the end's
cut stores a line no higher than the lowest live acceptance, and the top-up then leaves
no pending proposal above it (D46). A researcher's decision is never overwritten (D2).
Live acceptance makes no tag: the ordinary readers keep D32 until the cut; the live page
reads the proposals with ``live=true``.

The LLM is mocked; no call is paid for.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bristlenose.server import autocode
from bristlenose.server.autocode import (
    BATCH_SIZE,
    QuoteBatchItem,
    accept_live,
    cut_first_apply,
    first_apply_batches,
    hybrid_accept_line,
    live_accept_line,
    reapply_to_new_quotes,
    run_autocode_job,
)
from bristlenose.server.db import Base
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Project,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)
from tests.test_autocode_batch_save import _counts, _file_project, _n_in_prompt, _settings
from tests.test_autocode_engine import _make_batch_result, _patch_llm
from tests.test_autocode_landing_routes import (  # noqa: F401  (a fixture)
    BASE,
    _embedded,
    _live,
    _unfinish,
    seeded,
)

# ---------------------------------------------------------------------------
# A small study, in memory: one codebook tag, ``n`` quotes, a first apply running
# ---------------------------------------------------------------------------


def _study(n_quotes: int, *, upper: float | None = None) -> tuple[Any, int, int, list[int]]:
    """(session factory, job id, tag id, quote ids in stored order)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    db = session_cls()
    project = Project(name="P", slug="p", input_dir="/tmp", output_dir="/tmp")
    db.add(project)
    db.flush()
    group = CodebookGroup(name="G", subtitle="", colour_set="ux", framework_id="garrett")
    db.add(group)
    db.flush()
    tag = TagDefinition(name="t", codebook_group_id=group.id)
    db.add(tag)
    quotes = [
        Quote(project_id=project.id, session_id="s1", participant_id="p1",
              start_timecode=float(i * 10), end_timecode=float(i * 10 + 5),
              text=f"Quote {i}", quote_type="screen_specific")
        for i in range(n_quotes)
    ]
    db.add_all(quotes)
    job = AutoCodeJob(project_id=project.id, framework_id="garrett", status="running",
                      applied_upper_threshold=upper,
                      applied_lower_threshold=None if upper is None else 0.30)
    db.add(job)
    db.commit()
    out = session_cls, job.id, tag.id, [q.id for q in quotes]
    db.close()
    return out


def _land(session_cls: Any, job_id: int, tag_id: int, quote_ids: list[int],
          confidences: list[float]) -> int:
    """One batch saved: its proposals and their live acceptance, in one transaction."""
    db = session_cls()
    try:
        for quote_id, confidence in zip(quote_ids, confidences, strict=True):
            db.add(ProposedTag(job_id=job_id, quote_id=quote_id, tag_definition_id=tag_id,
                               confidence=confidence, rationale="r"))
        n = accept_live(db, job_id)
        db.commit()
        return n
    finally:
        db.close()


def _end(session_cls: Any, job_id: int, *, stopped: bool = False) -> float:
    """The run's end cut, as its outcome save runs it; answers the stored accept line."""
    db = session_cls()
    try:
        out = cut_first_apply(db, job_id, stopped=stopped)
        db.commit()
        assert out is not None
        return out.accept_at
    finally:
        db.close()


def _rows(session_cls: Any, job_id: int) -> list[tuple[float, str, str | None]]:
    db = session_cls()
    try:
        return [(p.confidence, p.status, p.decided_by)
                for p in db.query(ProposedTag).filter_by(job_id=job_id).order_by(ProposedTag.id)]
    finally:
        db.close()


def _job(session_cls: Any, job_id: int) -> AutoCodeJob:
    db = session_cls()
    try:
        job = db.get(AutoCodeJob, job_id)
        assert job is not None
        db.expunge(job)
        return job
    finally:
        db.close()


def _tags(session_cls: Any) -> int:
    db = session_cls()
    try:
        return db.query(QuoteTag).filter_by(source="autocode").count()
    finally:
        db.close()


def _no_inversion(rows: list[tuple[float, str, str | None]], line: float) -> None:
    for confidence, status, decided_by in rows:
        if status == "accepted" and decided_by == "threshold":
            assert confidence >= line, (confidence, line)
        if status == "pending":
            assert confidence < line, (confidence, line)


# ---------------------------------------------------------------------------
# D24 and D25: batches of 5, then 10, then 25, in stored order
# ---------------------------------------------------------------------------


def _items(n: int) -> list[QuoteBatchItem]:
    return [QuoteBatchItem(db_id=i, text="", session_id="s1", participant_id="p1",
                           topic_label="", sentiment="") for i in range(n)]


def test_the_ramp_is_5_then_10_then_25() -> None:
    assert autocode.FIRST_APPLY_BATCH_RAMP == (5, 10) and BATCH_SIZE == 25
    sizes = [len(b) for b in first_apply_batches(_items(100))]
    assert sizes == [5, 10, 25, 25, 25, 10]
    assert [len(b) for b in first_apply_batches(_items(3))] == [3]
    assert [len(b) for b in first_apply_batches(_items(12))] == [5, 7]
    assert first_apply_batches([]) == []
    # In the order given, every item once.
    flat = [item.db_id for b in first_apply_batches(_items(60)) for item in b]
    assert flat == list(range(60))


def test_the_ramp_is_capped_at_the_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autocode, "BATCH_SIZE", 2)
    assert [len(b) for b in first_apply_batches(_items(5))] == [2, 2, 1]


def _record_calls() -> tuple[list[list[int]], AsyncMock]:
    """The quote numbers each call was sent, in the order the prompt lists them."""
    calls: list[list[int]] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        calls.append([int(n) for n in re.findall(r'"Quote (\d+)"', user_prompt)])
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.5)

    return calls, AsyncMock(side_effect=analyze)


def _reversed_reads() -> Any:
    """The counted quotes read back in reverse: the read has no ORDER BY, so only the
    pass's own sort can put them in stored order."""
    from bristlenose.server import speaker_slots

    real = speaker_slots.analysis_quotes
    return patch.object(speaker_slots, "analysis_quotes",
                        lambda db, project_id: list(reversed(real(db, project_id))))


def test_a_first_apply_sends_its_quotes_in_stored_order_ramped(tmp_path) -> None:
    session_cls, engine, project_id, _ = _file_project(tmp_path, 60)
    calls, analyze = _record_calls()
    with _reversed_reads(), _patch_llm(analyze):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert [len(c) for c in calls] == [5, 10, 25, 20]
    assert [n for c in calls for n in c] == list(range(60))
    engine.dispose()


def test_a_catch_up_keeps_batches_of_25_in_stored_order(tmp_path) -> None:
    session_cls, engine, project_id, _ = _file_project(tmp_path, 60, applied=True)
    calls, analyze = _record_calls()
    with _reversed_reads(), _patch_llm(analyze):
        asyncio.run(reapply_to_new_quotes(session_cls, project_id, "garrett", _settings()))
    assert [len(c) for c in calls] == [25, 25, 10]
    assert [n for c in calls for n in c] == list(range(60))
    engine.dispose()


# ---------------------------------------------------------------------------
# D6: the live line
# ---------------------------------------------------------------------------


def test_the_live_line_is_the_hybrids_held_at_080_until_25_have_landed() -> None:
    assert live_accept_line([0.75] * 24, None) == 0.80
    assert live_accept_line([0.75] * 25, None) == 0.75
    assert live_accept_line([0.5] * 40, None) == 0.70  # never below the hybrid's floor
    assert live_accept_line([0.95] * 3, None) == 0.95
    # Never falls: the line used before stands against a lower estimate.
    assert live_accept_line([0.75] * 40, 0.85) == 0.85
    assert live_accept_line([0.95] * 40, 0.85) == 0.95


def test_the_first_proposals_are_accepted_live_only_at_080_or_above() -> None:
    session_cls, job_id, tag_id, quotes = _study(30)
    assert _land(session_cls, job_id, tag_id, quotes[:5], [0.75] * 4 + [0.82]) == 1
    assert _job(session_cls, job_id).live_accept_line == 0.80
    assert [s for _, s, _ in _rows(session_cls, job_id)] == ["pending"] * 4 + ["accepted"]


def test_twenty_five_landed_at_once_are_cut_at_their_own_line() -> None:
    session_cls, job_id, tag_id, quotes = _study(25)
    assert _land(session_cls, job_id, tag_id, quotes, [0.75] * 25) == 25
    assert _job(session_cls, job_id).live_accept_line == 0.75


def test_live_acceptance_never_excludes() -> None:
    session_cls, job_id, tag_id, quotes = _study(30)
    _land(session_cls, job_id, tag_id, quotes, [0.1] * 30)
    assert {s for _, s, _ in _rows(session_cls, job_id)} == {"pending"}


def test_the_line_never_falls_and_a_resumed_run_continues_from_it() -> None:
    session_cls, job_id, tag_id, quotes = _study(60)
    _land(session_cls, job_id, tag_id, quotes[:5], [0.90] * 5)
    assert _job(session_cls, job_id).live_accept_line == 0.90
    # 30 landed, the estimate falls to 0.70: the line stays where it was.
    assert _land(session_cls, job_id, tag_id, quotes[5:30], [0.70] * 25) == 0
    assert _job(session_cls, job_id).live_accept_line == 0.90
    # A resumed run (another pass of the same job) reads the line from the job.
    assert _land(session_cls, job_id, tag_id, quotes[30:35], [0.72] * 5) == 0


def test_a_run_with_stored_lines_accepts_at_its_stored_line() -> None:
    """A stop's settle (D27) or a review stored the lines: a resumed run accepts at the
    stored accept line, below the 0.80 floor and below a live line used earlier."""
    session_cls, job_id, tag_id, quotes = _study(10, upper=0.75)
    assert _land(session_cls, job_id, tag_id, quotes[:3], [0.76, 0.74, 0.75]) == 2
    assert _job(session_cls, job_id).live_accept_line is None


def test_a_hidden_quotes_proposal_is_not_accepted_live() -> None:
    from bristlenose.server.models import QuoteState

    session_cls, job_id, tag_id, quotes = _study(5)
    db = session_cls()
    db.add(QuoteState(quote_id=quotes[0], is_hidden=True))
    db.commit()
    db.close()
    assert _land(session_cls, job_id, tag_id, quotes, [0.95] * 5) == 4
    assert _rows(session_cls, job_id)[0][1] == "pending"


# ---------------------------------------------------------------------------
# D2: a researcher's decision is never overwritten
# ---------------------------------------------------------------------------


def test_a_researchers_decision_mid_run_is_never_overwritten() -> None:
    session_cls, job_id, tag_id, quotes = _study(10)
    _land(session_cls, job_id, tag_id, quotes[:5], [0.85] * 5)  # live line 0.85: accepted
    _land(session_cls, job_id, tag_id, quotes[5:7], [0.82, 0.83])  # below it: pending
    db = session_cls()
    try:
        first, second = (db.query(ProposedTag).filter_by(job_id=job_id)
                         .order_by(ProposedTag.id).all()[5:7])
        first.status, first.decided_by = "denied", "researcher"
        second.status, second.decided_by = "accepted", "researcher"
        # A review stores a line that would reach both.
        job = db.get(AutoCodeJob, job_id)
        assert job is not None
        job.applied_upper_threshold, job.applied_lower_threshold = 0.80, 0.30
        db.commit()
    finally:
        db.close()
    _land(session_cls, job_id, tag_id, quotes[7:8], [0.81])
    _end(session_cls, job_id)
    rows = _rows(session_cls, job_id)
    assert rows[5][1:] == ("denied", "researcher")
    assert rows[6][1:] == ("accepted", "researcher")
    assert rows[7][1:] == ("accepted", "threshold")


def test_a_decision_committed_while_the_acceptance_writes_wins() -> None:
    """The write is conditional on pending at write time: a decision committed after the
    rows were read and before the UPDATE runs is not overwritten."""
    session_cls, job_id, tag_id, quotes = _study(3)
    db = session_cls()
    for quote_id in quotes:
        db.add(ProposedTag(job_id=job_id, quote_id=quote_id, tag_definition_id=tag_id,
                           confidence=0.95, rationale="r"))
    db.commit()
    db.close()

    db = session_cls()
    real_query = db.query
    landed: list[bool] = []

    def query_then_decide(*entities: Any, **kw: Any) -> Any:
        if len(entities) == 1 and entities[0] is ProposedTag and not landed:  # the UPDATE
            landed.append(True)
            other = session_cls()
            try:
                p = other.query(ProposedTag).filter_by(quote_id=quotes[0]).one()
                p.status, p.decided_by = "denied", "researcher"
                other.commit()
            finally:
                other.close()
        return real_query(*entities, **kw)

    try:
        with patch.object(db, "query", query_then_decide):
            assert accept_live(db, job_id) == 2
        db.commit()
    finally:
        db.close()
    assert landed
    assert _rows(session_cls, job_id)[0][1:] == ("denied", "researcher")


# ---------------------------------------------------------------------------
# An accepted tag is never taken back: the end's reconcile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stopped", [False, True])
def test_the_stored_line_is_no_higher_than_the_lowest_live_acceptance(stopped: bool) -> None:
    """Accepted live at 0.85; the run's exact cut ends at 0.95. The stored line is 0.85,
    the 0.85s stay accepted, and the 0.90s the exact cut would leave pending are
    topped up: no accepted proposal below the line, no pending one above it (D46)."""
    session_cls, job_id, tag_id, quotes = _study(35)
    _land(session_cls, job_id, tag_id, quotes[:5], [0.85] * 5)
    _land(session_cls, job_id, tag_id, quotes[5:25], [0.95] * 20)
    _land(session_cls, job_id, tag_id, quotes[25:35], [0.90] * 10)
    assert hybrid_accept_line(c for c, _, _ in _rows(session_cls, job_id)) == 0.95
    db = session_cls()
    job = db.get(AutoCodeJob, job_id)
    assert job is not None
    job.status = "cancelled" if stopped else "completed"
    db.commit()
    db.close()

    line = _end(session_cls, job_id, stopped=stopped)

    assert line == 0.85
    job = _job(session_cls, job_id)
    assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.85, 0.30)
    rows = _rows(session_cls, job_id)
    assert all(s == "accepted" for _, s, _ in rows)  # never taken back, and topped up
    _no_inversion(rows, line)
    assert _tags(session_cls) == 35  # the live acceptances' tags are made at the end


def test_a_live_acceptance_has_no_tag_until_the_end() -> None:
    session_cls, job_id, tag_id, quotes = _study(10)
    _land(session_cls, job_id, tag_id, quotes[:5], [0.95] * 5)
    assert _tags(session_cls) == 0
    _end(session_cls, job_id)
    assert _tags(session_cls) == 5


def test_a_tag_the_researcher_already_had_is_not_doubled() -> None:
    session_cls, job_id, tag_id, quotes = _study(5)
    db = session_cls()
    db.add(QuoteTag(quote_id=quotes[0], tag_definition_id=tag_id, source="human"))
    db.commit()
    db.close()
    _land(session_cls, job_id, tag_id, quotes, [0.95] * 5)
    _end(session_cls, job_id)
    db = session_cls()
    try:
        assert db.query(QuoteTag).filter_by(quote_id=quotes[0]).count() == 1
        assert db.query(QuoteTag).filter_by(source="autocode").count() == 4
    finally:
        db.close()


_GRID = [i / 100 for i in range(101)]


@settings(max_examples=80, deadline=None)
@given(
    batches=st.lists(st.lists(st.sampled_from(_GRID), min_size=1, max_size=25),
                     min_size=1, max_size=6),
    order=st.randoms(use_true_random=False),
    stopped=st.booleans(),
)
def test_any_run_in_any_arrival_order_keeps_every_rule(
    batches: list[list[float]], order: Any, stopped: bool,
) -> None:
    """Whatever the confidences and whatever order the batches answer in: the live line
    never falls, never sits below 0.70, and not below 0.80 until 25 have landed; nothing
    accepted is taken back; the end stores a line on the grid, no higher than the exact
    cut; no accepted proposal sits below it and no pending one above it; the run takes at
    least what the exact cut takes; every acceptance has its tag."""
    arrival = list(range(len(batches)))
    order.shuffle(arrival)
    session_cls, job_id, tag_id, quotes = _study(sum(len(b) for b in batches))
    starts = [sum(len(b) for b in batches[:i]) for i in range(len(batches))]
    lines: list[float] = []
    accepted_so_far: set[int] = set()
    landed = 0
    for index in arrival:
        batch = batches[index]
        _land(session_cls, job_id, tag_id, quotes[starts[index]:starts[index] + len(batch)],
              batch)
        landed += len(batch)
        line = _job(session_cls, job_id).live_accept_line
        assert line is not None and line >= 0.70
        if landed < 25:
            assert line >= 0.80
        assert not lines or line >= lines[-1]
        lines.append(line)
        rows = _rows(session_cls, job_id)
        now = {i for i, (_, s, _) in enumerate(rows) if s == "accepted"}
        assert accepted_so_far <= now  # never taken back
        assert all(rows[i][0] >= line for i in now - accepted_so_far)
        accepted_so_far = now

    exact = hybrid_accept_line(c for b in batches for c in b)
    stored = _end(session_cls, job_id, stopped=stopped)
    rows = _rows(session_cls, job_id)
    assert stored <= exact
    assert round(stored * 20, 9) == round(stored * 20)
    _no_inversion(rows, stored)
    assert accepted_so_far <= {i for i, (_, s, _) in enumerate(rows) if s == "accepted"}
    assert all(s == "accepted" for c, s, _ in rows if c >= exact)  # only ever overshoot
    assert all(s == "denied" for c, s, _ in rows if c < 0.30)
    assert _tags(session_cls) == sum(1 for _, s, _ in rows if s == "accepted")


# ---------------------------------------------------------------------------
# A whole run, batches answering out of order (the lead's simulation, 23 Nov 2026)
# ---------------------------------------------------------------------------


def test_an_early_low_batch_does_not_drag_the_run_into_overshoot(tmp_path) -> None:
    """65 quotes go as 5, 10, 25, 25, all four at once. The first batch (0.90) answers,
    then the third (25 at 0.70), then the second and fourth (0.90). The plain estimate
    fell to 0.70 when the third landed, accepted it live, and the end's reconcile then
    accepted the whole run (100%). Never falling, the line stays at 0.90 and the run
    takes exactly what the end-only cut takes: the 40 at 0.90."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 65)
    starts, sizes = [0, 5, 15, 40], [5, 10, 25, 25]
    confidence = {0: 0.90, 5: 0.90, 15: 0.70, 40: 0.90}
    arrival = [0, 2, 1, 3]  # by batch
    live_during: list[tuple[int, int]] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        first = int(re.search(r'"Quote (\d+)"', user_prompt).group(1))  # type: ignore[union-attr]
        batch = starts.index(first)
        before = sum(sizes[b] for b in arrival[:arrival.index(batch)])
        deadline = time.monotonic() + 10
        while _counts(session_cls)[0] < before:
            assert time.monotonic() < deadline, "the batches before this one never landed"
            await asyncio.sleep(0.01)
        live_during.append((_counts(session_cls)[0], _tags(session_cls)))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", confidence[first])

    run_settings = _settings()
    run_settings.llm_concurrency = 4
    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", run_settings))

    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        assert job.status == "completed"
        assert job.applied_upper_threshold == 0.90
        statuses = [(p.confidence, p.status) for p in db.query(ProposedTag)]
        assert sum(1 for _, s in statuses if s == "accepted") == 40
        assert all(s == "pending" for c, s in statuses if c == 0.70)
    finally:
        db.close()
    # No tag reached the ordinary readers while the run coded (D32).
    assert all(tags == 0 for _, tags in live_during)
    assert _tags(session_cls) == 40
    engine.dispose()


def test_a_run_accepts_live_as_its_batches_land(tmp_path) -> None:
    """Mid-run, another session sees the earlier batches' proposals already accepted, in
    their own save's transaction, with no tags yet."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 40)
    seen: list[tuple[int, int]] = []

    def accepted() -> int:
        db = session_cls()
        try:
            return db.query(ProposedTag).filter_by(status="accepted").count()
        finally:
            db.close()

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        seen.append((accepted(), _tags(session_cls)))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.9)

    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert seen == [(0, 0), (5, 0), (15, 0)]
    assert _tags(session_cls) == 40
    engine.dispose()


# ---------------------------------------------------------------------------
# D32: the live page's read; every other reader unchanged
# ---------------------------------------------------------------------------


def _accept_live_now(client: Any) -> None:
    db = client.app.state.db_factory()
    try:
        job = db.query(AutoCodeJob).one()
        accept_live(db, job.id)
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("status", ["running", "cancelled", "failed"])
def test_a_running_runs_live_acceptances_show_only_on_the_live_read(seeded, status) -> None:  # noqa: F811
    client, ids, _ = seeded  # four pending proposals at 0.5, 0.6, 0.7, 0.8
    _unfinish(client, status)
    _accept_live_now(client)  # the live line is 0.80: the 0.8 one is accepted

    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0"
    live = client.get(f"{url}&live=true").json()
    assert {s["id"]: (s["status"], s["decided_by"]) for s in live["states"]} == {
        ids[0]: ("pending", None), ids[1]: ("pending", None), ids[2]: ("pending", None),
        ids[3]: ("accepted", "threshold"),
    }
    assert live["run"]["status"] == status
    assert live["run"]["settled"] is (status != "running")
    assert live["run"]["cursor"] == max(ids)

    # The ordinary readers, the export among them, show nothing of it (D32).
    db = client.app.state.db_factory()
    try:
        assert db.query(QuoteTag).filter_by(source="autocode").count() == 0
    finally:
        db.close()
    assert _live(client) == (0, 0, 0)
    assert _embedded(client) == (0, 0, 0)


def test_the_live_read_reports_a_decision_on_a_row_already_read(seeded) -> None:  # noqa: F811
    """A cursor of ids alone misses a decision made on a row it has already listed; the
    states carry it, whatever the cursor."""
    client, ids, _ = seeded
    _unfinish(client, "running")
    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0&live=true"
    first = client.get(url).json()
    assert first["run"]["cursor"] == max(ids)
    _accept_live_now(client)
    after = client.get(f"{url}&since_id={first['run']['cursor']}").json()
    assert after["proposals"] == []  # nothing new in full
    assert {s["id"]: s["status"] for s in after["states"]}[ids[3]] == "accepted"
    assert {s["id"]: s["quote_id"] for s in after["states"]} == {
        p["id"]: p["quote_id"] for p in first["proposals"]
    }


def test_the_review_dialogs_read_is_unchanged_without_live(seeded) -> None:  # noqa: F811
    client, _, _ = seeded
    body = client.get(f"{BASE}/autocode/garrett/proposals?min_confidence=0").json()
    assert set(body) == {"proposals", "total"}


def test_the_live_read_is_settled_only_once_the_runner_has_ended(seeded) -> None:  # noqa: F811
    """A Stop marks the job cancelled at once; until its runner's last batches and its
    settle have landed (``ending``), the read is not the run's last."""
    client, _, _ = seeded
    _unfinish(client, "cancelled")
    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0&live=true"
    with patch.object(autocode, "_FIRST_APPLY_CODING", {(1, "garrett"): 1}):
        run = client.get(url).json()["run"]
    assert (run["ending"], run["settled"]) == (True, False)
    run = client.get(url).json()["run"]
    assert (run["ending"], run["settled"]) == (False, True)
