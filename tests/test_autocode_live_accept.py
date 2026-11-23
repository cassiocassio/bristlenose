"""AutoCode landing, Phase 4a: the server half of live landing (docs/design-autocode-landing-plan.md).

A first apply sends its quotes in stored order (D25), in batches of 5, then 10, then 25
(D24); a catch-up keeps 25. As each batch is saved it accepts, in the same transaction,
the run's pending proposals at or above a live line (D6): the hybrid's own line over
the proposals so far, not below 0.75 until 25 have landed, and never falling during the
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
    LIVE_EARLY_FLOOR,
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


def test_the_live_line_is_the_hybrids_held_at_075_until_25_have_landed() -> None:
    assert LIVE_EARLY_FLOOR == 0.75  # owner, 23 Nov 2026 (was 0.80)
    assert live_accept_line([0.70] * 24, None) == 0.75
    assert live_accept_line([0.70] * 25, None) == 0.70
    assert live_accept_line([0.5] * 40, None) == 0.70  # never below the hybrid's floor
    assert live_accept_line([0.95] * 3, None) == 0.95
    # Never falls: the line used before stands against a lower estimate.
    assert live_accept_line([0.75] * 40, 0.85) == 0.85
    assert live_accept_line([0.95] * 40, 0.85) == 0.95


def test_the_first_proposals_are_accepted_live_only_at_075_or_above() -> None:
    session_cls, job_id, tag_id, quotes = _study(30)
    assert _land(session_cls, job_id, tag_id, quotes[:5], [0.70] * 4 + [0.76]) == 1
    assert _job(session_cls, job_id).live_accept_line == 0.75
    assert [s for _, s, _ in _rows(session_cls, job_id)] == ["pending"] * 4 + ["accepted"]


def test_twenty_five_landed_at_once_are_cut_at_their_own_line() -> None:
    session_cls, job_id, tag_id, quotes = _study(25)
    assert _land(session_cls, job_id, tag_id, quotes, [0.70] * 25) == 25
    assert _job(session_cls, job_id).live_accept_line == 0.70


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
    stored accept line, below the 0.75 floor and below a live line used earlier."""
    session_cls, job_id, tag_id, quotes = _study(10, upper=0.70)
    assert _land(session_cls, job_id, tag_id, quotes[:3], [0.71, 0.69, 0.70]) == 2
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
def test_the_stored_line_is_no_higher_than_the_lowest_live_acceptance(
    stopped: bool, caplog: pytest.LogCaptureFixture,
) -> None:
    """Accepted live at 0.85; the run's exact cut ends at 0.95. The stored line is 0.85,
    the 0.85s stay accepted, and the 0.90s the exact cut would leave pending are
    topped up: no accepted proposal below the line, no pending one above it (D46). The
    overshoot is said, with both lines and what it added (lead, 23 Nov 2026)."""
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

    import logging

    with caplog.at_level(logging.INFO, logger="bristlenose.server.autocode"):
        line = _end(session_cls, job_id, stopped=stopped)

    assert line == 0.85
    said = [r.getMessage() for r in caplog.records if "below the exact cut" in r.getMessage()]
    assert said == [
        f"AutoCode job {job_id}: stored line 0.85 is below the exact cut 0.95 (accepted live "
        "below it); the top-up accepted 10 more because of it"
    ]
    job = _job(session_cls, job_id)
    assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.85, 0.30)
    rows = _rows(session_cls, job_id)
    assert all(s == "accepted" for _, s, _ in rows)  # never taken back, and topped up
    _no_inversion(rows, line)
    assert _tags(session_cls) == 35  # the live acceptances' tags are made at the end


def test_a_cut_that_lands_at_the_exact_line_says_nothing(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    session_cls, job_id, tag_id, quotes = _study(10)
    _land(session_cls, job_id, tag_id, quotes, [0.95] * 3 + [0.5] * 7)
    with caplog.at_level(logging.INFO, logger="bristlenose.server.autocode"):
        assert _end(session_cls, job_id) == 0.95
    assert not [r for r in caplog.records if "below the exact cut" in r.getMessage()]


def test_a_live_acceptance_has_no_tag_until_the_end() -> None:
    session_cls, job_id, tag_id, quotes = _study(10)
    _land(session_cls, job_id, tag_id, quotes[:5], [0.95] * 5)
    assert _tags(session_cls) == 0
    _end(session_cls, job_id)
    assert _tags(session_cls) == 5


def test_a_tag_the_researcher_already_had_is_not_doubled_or_counted() -> None:
    """The settle's count of tags it made (what decides a Signals rebuild after a stop or
    a failure, D31) leaves out a tag the quote already had, the researcher's own."""
    session_cls, job_id, tag_id, quotes = _study(5)
    db = session_cls()
    db.add(QuoteTag(quote_id=quotes[0], tag_definition_id=tag_id, source="human"))
    db.commit()
    db.close()
    _land(session_cls, job_id, tag_id, quotes, [0.95] * 5)
    db = session_cls()
    try:
        out = cut_first_apply(db, job_id, stopped=True)
        db.commit()
    finally:
        db.close()
    assert out is not None and out.tagged == 4
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
    never falls, never sits below 0.70, and not below 0.75 until 25 have landed; nothing
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
            assert line >= LIVE_EARLY_FLOOR
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
    _accept_live_now(client)  # the live line is 0.75: the 0.8 one is accepted

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


# ---------------------------------------------------------------------------
# Every end of a first apply settles (D27, extended by the lead on 23 Nov 2026)
# ---------------------------------------------------------------------------


def _ended_job_holds_no_unsettled_acceptance(session_cls: Any) -> AutoCodeJob:
    """The invariant over every terminal path: an ended job with a threshold acceptance
    has stored lines, every such acceptance has its tag, and none sits below the stored
    line nor any pending proposal on or above it."""
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        assert job.status in ("completed", "failed", "cancelled")
        accepted = db.query(ProposedTag).filter_by(
            job_id=job.id, status="accepted", decided_by="threshold",
        ).all()
        if accepted:
            assert job.applied_upper_threshold is not None
            tagged = {(t.quote_id, t.tag_definition_id) for t in db.query(QuoteTag)}
            assert all((p.quote_id, p.tag_definition_id) in tagged for p in accepted)
        if job.applied_upper_threshold is not None:
            _no_inversion(
                [(p.confidence, p.status, p.decided_by)
                 for p in db.query(ProposedTag).filter_by(job_id=job.id)],
                job.applied_upper_threshold,
            )
        db.expunge(job)
        return job
    finally:
        db.close()


def _set_job_status(session_cls: Any, status: str) -> None:
    db = session_cls()
    try:
        db.query(AutoCodeJob).update({"status": status})
        db.commit()
    finally:
        db.close()


def _first_batch_lands_then(session_cls: Any, then: Any) -> AsyncMock:
    """The first batch (5 at 0.95) answers and is accepted live; ``then`` runs as the
    second batch is sent, which answers at 0.5."""
    calls = {"n": 0}

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 2:
            await then()
        confidence = 0.95 if calls["n"] == 1 else 0.5
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", confidence)

    return AsyncMock(side_effect=analyze)


def test_a_stopped_run_settles(tmp_path) -> None:
    session_cls, engine, project_id, _ = _file_project(tmp_path, 40)

    async def stop() -> None:
        _set_job_status(session_cls, "cancelled")

    with _patch_llm(_first_batch_lands_then(session_cls, stop)):
        tags = asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.completed_at) == ("cancelled", None)
    assert tags == _tags(session_cls) == 5
    engine.dispose()


@pytest.mark.parametrize("stopped", [False, True])
def test_a_run_whose_outcome_never_saved_settles_with_its_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch, stopped: bool,
) -> None:
    """The outcome's save runs out of tries: the job is marked failed (a Stop's stays
    cancelled) and settled in the same transaction."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 40)
    real_save = autocode._save_batch

    async def save(db_factory, write, what):  # type: ignore[no-untyped-def]
        if what.endswith("its outcome"):
            return False, None
        return await real_save(db_factory, write, what)

    async def maybe_stop() -> None:
        if stopped:
            _set_job_status(session_cls, "cancelled")

    monkeypatch.setattr(autocode, "_save_batch", save)
    with _patch_llm(_first_batch_lands_then(session_cls, maybe_stop)):
        tags = asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.completed_at) == ("cancelled" if stopped else "failed", None)
    assert job.applied_upper_threshold is not None
    assert tags == _tags(session_cls) == 5
    engine.dispose()


def test_a_run_that_fails_settles_what_earlier_passes_accepted(tmp_path) -> None:
    """A pass whose every batch fails ends failed; what an earlier pass accepted live and
    left without lines (a job from before every end settled) is settled with it."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 10)
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        tag = db.query(TagDefinition).filter_by(name="User need").first() or \
            db.query(TagDefinition).first()
        assert tag is not None
        for quote in db.query(Quote).order_by(Quote.id).limit(5):
            db.add(ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=tag.id,
                               confidence=0.9, rationale="r", status="accepted",
                               decided_by="threshold"))
            autocode.record_sent(db, job.id, [quote.id])
        job.status, job.live_accept_line = "failed", 0.90
        db.commit()
    finally:
        db.close()

    with _patch_llm(AsyncMock(side_effect=RuntimeError("credit balance is too low"))):
        tags = asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.completed_at, job.applied_upper_threshold) == ("failed", None, 0.9)
    assert tags == 5
    engine.dispose()


def test_a_crash_mid_run_is_settled_by_the_boot_sweep(tmp_path) -> None:
    from bristlenose.server.autocode import reconcile_orphaned_jobs

    session_cls, engine, project_id, _ = _file_project(tmp_path, 40)

    async def main() -> None:
        second = asyncio.Event()

        async def never_answers() -> None:
            second.set()
            await asyncio.Event().wait()

        with _patch_llm(_first_batch_lands_then(session_cls, never_answers)):
            task = asyncio.ensure_future(
                run_autocode_job(session_cls, project_id, "garrett", _settings()))
            await second.wait()
            task.cancel()  # the process goes; no handler of the job's runs
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(main())
    assert _tags(session_cls) == 0  # accepted live, untagged, as the crash left it
    db = session_cls()
    try:
        assert reconcile_orphaned_jobs(db) == 1
    finally:
        db.close()
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.completed_at, job.applied_upper_threshold) == ("failed", None, 0.95)
    assert _tags(session_cls) == 5
    engine.dispose()


def test_a_failed_runs_retry_resumes_at_the_lines_it_settled(tmp_path) -> None:
    """15 quotes go as 5 and 10: the first lands (0.95, accepted live), the second fails,
    and the outcome cannot be saved, so the run ends failed and settles at 0.95. Its retry
    sends the 10 owed, which answer 0.9: below the settled line, they stay pending."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 15)

    async def fail() -> None:
        raise RuntimeError("credit balance is too low")

    real_save = autocode._save_batch

    async def save(db_factory, write, what):  # type: ignore[no-untyped-def]
        if what.endswith("its outcome"):
            return False, None
        return await real_save(db_factory, write, what)

    with patch.object(autocode, "_save_batch", save), \
            _patch_llm(_first_batch_lands_then(session_cls, fail)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert _job(session_cls, 1).applied_upper_threshold == 0.95
    _set_job_status(session_cls, "pending")  # Apply's start on a never-applied job
    with _patch_llm(AsyncMock(side_effect=lambda system_prompt, user_prompt, response_model,
                              **kw: _make_batch_result(_n_in_prompt(user_prompt),
                                                       "user need", 0.9))):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.applied_upper_threshold) == ("completed", 0.95)
    assert _tags(session_cls) == 5  # the 0.9s of the retry sit below the settled line
    engine.dispose()


# ---------------------------------------------------------------------------
# Review is inactive while a first apply codes (D17)
# ---------------------------------------------------------------------------


_REVIEW_ACTIONS = [
    ("recut", {"lower": 0.3, "upper": 0.8}),
    ("accept-all", {"min_confidence": 0.8}),
    ("deny-all", {"min_confidence": 0.0, "max_confidence": 0.3}),
]


@pytest.mark.parametrize(("action", "body"), _REVIEW_ACTIONS)
@pytest.mark.parametrize("status", ["pending", "running"])
def test_the_reviews_lines_are_refused_while_a_first_apply_codes(
    seeded, action: str, body: dict, status: str,  # noqa: F811
) -> None:
    client, ids, _ = seeded
    _unfinish(client, status)
    resp = client.post(f"{BASE}/autocode/garrett/{action}", json=body)
    assert resp.status_code == 409
    assert resp.json()["reason"] == "already_running"
    # A researcher's own decision on one row stays allowed (D2).
    assert client.post(f"{BASE}/autocode/proposals/{ids[0]}/deny").status_code == 200


@pytest.mark.parametrize(("action", "body"), _REVIEW_ACTIONS)
def test_the_reviews_lines_are_refused_while_a_stopped_run_settles(
    seeded, action: str, body: dict,  # noqa: F811
) -> None:
    client, _, _ = seeded
    _unfinish(client, "cancelled")
    url = f"{BASE}/autocode/garrett/{action}"
    with patch.object(autocode, "_FIRST_APPLY_CODING", {(1, "garrett"): 1}):
        assert client.post(url, json=body).status_code == 409
    assert client.post(url, json=body).status_code == 200


def test_the_review_stays_live_while_a_catch_up_codes(seeded) -> None:  # noqa: F811
    """A catch-up on an applied job leaves it "running" with ``completed_at``: Review
    stays live (D20)."""
    client, _, _ = seeded
    db = client.app.state.db_factory()
    try:
        db.query(AutoCodeJob).update({"status": "running"})
        db.commit()
    finally:
        db.close()
    resp = client.post(f"{BASE}/autocode/garrett/recut", json={"lower": 0.3, "upper": 0.8})
    assert resp.status_code == 200


def test_a_recut_with_no_stored_lines_reads_the_live_line(seeded) -> None:  # noqa: F811
    """The belt: a job that accepted live and stored no lines (no known path reaches it)
    is re-cut against its live line, so a live acceptance below the new line moves."""
    client, ids, _ = seeded
    db = client.app.state.db_factory()
    try:
        job = db.query(AutoCodeJob).one()
        job.applied_upper_threshold = job.applied_lower_threshold = None
        job.live_accept_line = 0.80
        p = db.get(ProposedTag, ids[3])  # 0.8
        assert p is not None
        p.status, p.decided_by = "accepted", "threshold"
        db.commit()
    finally:
        db.close()
    resp = client.post(f"{BASE}/autocode/garrett/recut", json={"lower": 0.3, "upper": 0.85})
    assert resp.status_code == 200
    db = client.app.state.db_factory()
    try:
        p = db.get(ProposedTag, ids[3])
        assert p is not None and (p.status, p.decided_by) == ("pending", None)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The live read: settled, and its cursor
# ---------------------------------------------------------------------------


def test_the_live_read_is_not_settled_while_a_catch_up_codes(seeded) -> None:  # noqa: F811
    from unittest.mock import MagicMock

    client, _, _ = seeded
    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0&live=true"
    coding = MagicMock()
    coding.done.return_value = False
    with patch.dict(autocode._REAPPLY_IN_FLIGHT, {(1, "garrett"): coding}):
        assert client.get(url).json()["run"]["settled"] is False
    assert client.get(url).json()["run"]["settled"] is True


def test_a_silent_catch_up_after_a_run_is_registered_while_it_codes(tmp_path) -> None:
    """Every catch-up path registers its task, the run's silent one included, so the live
    read can tell a codebook is still coding."""
    from bristlenose.server.autocode import live_reapply, reapply_active_frameworks

    session_cls, engine, project_id, _ = _file_project(tmp_path, 3, applied=True)
    seen: list[bool] = []

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        seen.append(live_reapply(project_id, "garrett") is not None)
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.5)

    with _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(reapply_active_frameworks(session_cls, project_id, _settings()))
    assert seen == [True]
    engine.dispose()


def test_the_cursor_is_what_this_answers_proposals_reached(seeded) -> None:  # noqa: F811
    client, ids, _ = seeded
    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0&live=true"
    assert client.get(f"{url}&since_id={ids[1]}").json()["run"]["cursor"] == ids[3]
    assert client.get(f"{url}&since_id={ids[3]}").json()["run"]["cursor"] == ids[3]
    assert client.get(f"{url}&min_confidence=0.99").json()["run"]["cursor"] is None


def test_a_row_committed_between_the_two_reads_comes_in_full_next_time(seeded) -> None:  # noqa: F811
    """The states read runs after the proposals read: a batch committed between them is in
    ``states`` and not in ``proposals``, and the cursor stays below it."""
    client, ids, tag_ids = seeded
    db = client.app.state.db_factory()
    try:
        gone = db.get(ProposedTag, ids[3])
        assert gone is not None
        free_quote = gone.quote_id
        db.delete(gone)
        db.commit()
    finally:
        db.close()

    real_factory = client.app.state.db_factory
    landed: list[int] = []

    def factory() -> Any:
        session = real_factory()
        real_query = session.query

        def query(*entities: Any, **kw: Any) -> Any:
            if len(entities) == 5 and entities[0] is ProposedTag.id and not landed:
                other = real_factory()
                try:
                    job = other.query(AutoCodeJob).one()
                    p = ProposedTag(job_id=job.id, quote_id=free_quote,
                                    tag_definition_id=tag_ids[3], confidence=0.9,
                                    rationale="r")
                    other.add(p)
                    other.commit()
                    landed.append(p.id)
                finally:
                    other.close()
            return real_query(*entities, **kw)

        session.query = query  # type: ignore[method-assign]
        return session

    url = f"{BASE}/autocode/garrett/proposals?min_confidence=0&live=true"
    with patch.object(client.app.state, "db_factory", factory):
        body = client.get(f"{url}&since_id={ids[1]}").json()
    assert landed
    assert [p["id"] for p in body["proposals"]] == [ids[2]]
    assert landed[0] in {s["id"] for s in body["states"]}
    assert body["run"]["cursor"] == ids[2]
    after = client.get(f"{url}&since_id={body['run']['cursor']}").json()
    assert [p["id"] for p in after["proposals"]] == [landed[0]]


# ---------------------------------------------------------------------------
# Live acceptance can never cost a batch its save
# ---------------------------------------------------------------------------


def test_a_live_acceptance_that_fails_rolls_back_alone(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """It accepts, then fails: its savepoint takes back its own writes, the batch's
    proposals are saved, and the end cut accepts what it missed."""
    import logging

    session_cls, engine, project_id, _ = _file_project(tmp_path, 15)
    real = autocode.accept_live

    def accept_then_fail(session, job_id):  # type: ignore[no-untyped-def]
        real(session, job_id)
        session.flush()
        raise RuntimeError("live acceptance broke")

    monkeypatch.setattr(autocode, "accept_live", accept_then_fail)
    seen: list[tuple[int, int]] = []

    def accepted() -> int:
        db = session_cls()
        try:
            return db.query(ProposedTag).filter_by(status="accepted").count()
        finally:
            db.close()

    async def analyze(system_prompt, user_prompt, response_model, **kw):  # type: ignore[no-untyped-def]
        seen.append((_counts(session_cls)[0], accepted()))
        return _make_batch_result(_n_in_prompt(user_prompt), "user need", 0.95)

    with caplog.at_level(logging.WARNING, logger="bristlenose.server.autocode"), \
            _patch_llm(AsyncMock(side_effect=analyze)):
        asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    assert seen == [(0, 0), (5, 0)]  # saved, and nothing accepted live survived
    assert sum("live acceptance skipped" in r.getMessage() for r in caplog.records) == 2
    assert accepted() == 15 and _tags(session_cls) == 15
    assert _job(session_cls, 1).status == "completed"
    engine.dispose()


def test_a_run_whose_codebook_is_gone_settles_what_it_had(tmp_path) -> None:
    """The codebook's template missing fails the run at once; what an earlier pass accepted
    live is settled with it."""
    session_cls, engine, project_id, _ = _file_project(tmp_path, 5)
    db = session_cls()
    try:
        job = db.query(AutoCodeJob).one()
        tag = db.query(TagDefinition).first()
        assert tag is not None
        for quote in db.query(Quote).order_by(Quote.id):
            db.add(ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=tag.id,
                               confidence=0.9, rationale="r", status="accepted",
                               decided_by="threshold"))
        job.status, job.live_accept_line = "failed", 0.90
        db.commit()
    finally:
        db.close()
    with patch("bristlenose.server.codebook.get_template", return_value=None):
        tags = asyncio.run(run_autocode_job(session_cls, project_id, "garrett", _settings()))
    job = _ended_job_holds_no_unsettled_acceptance(session_cls)
    assert (job.status, job.applied_upper_threshold) == ("failed", 0.9)
    assert tags == 5
    engine.dispose()


def test_a_settle_whose_acceptances_are_all_on_hidden_quotes_still_stores_lines() -> None:
    from bristlenose.server.models import QuoteState

    session_cls, job_id, tag_id, quotes = _study(5)
    _land(session_cls, job_id, tag_id, quotes, [0.95] * 5)
    db = session_cls()
    db.add_all([QuoteState(quote_id=q, is_hidden=True) for q in quotes])
    db.commit()
    db.close()
    _end(session_cls, job_id, stopped=True)
    job = _job(session_cls, job_id)
    assert (job.applied_upper_threshold, job.applied_lower_threshold) == (0.70, 0.30)
    assert _tags(session_cls) == 5  # kept: accepted before they were hidden (lead's call)
