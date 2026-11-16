"""Progressive lenses: Stop, then Analyse again, keeps what was already delivered.

docs/design-progressive-lenses.md §3 principle 4 and §5.2. A resumed run starts a
fresh manifest, so the overlay must not be rebuilt from it alone: until stages 6
and 9 record the sessions again, Quotes went dark over rows the database held.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.manifest import (
    STAGE_MERGE_TRANSCRIPT,
    create_manifest,
    hold_for_resume,
    load_manifest,
    mark_session_complete,
    write_manifest,
)
from bristlenose.server.grounding import delivery_coverage
from tests.test_progressive_lenses import (  # noqa: F401
    _follow,
    _record_readable,
    _segments,
    _start_run,
    first_analysis,
)
from tests.test_progressive_quotes import QUOTE, _record_quoted, _write_quotes


def _stop(out: Path, run_id: str = "RUN1") -> None:
    from bristlenose.events import (
        Cause,
        CauseCategoryEnum,
        KindEnum,
        RunCancelledEvent,
        append_event,
        events_path,
    )

    now = datetime.now(timezone.utc).isoformat()
    append_event(events_path(out), RunCancelledEvent(
        ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now, ended_at=now,
        cause=Cause(category=CauseCategoryEnum.USER_SIGNAL),
    ))


def _restart(out: Path, *, held: bool, own_manifest: bool) -> None:
    """Analyse again, as far as the pipeline has got: ``held`` once it has kept the
    previous manifest aside (pipeline.py, right after the run starts), ``own_manifest``
    once ingest has written the new run's empty one."""
    previous = load_manifest(out)
    time.sleep(0.02)  # the new run starts after the old manifest was created
    _start_run(out, "RUN2")
    if held:
        hold_for_resume(previous, out)
    if own_manifest:
        time.sleep(0.02)
        write_manifest(create_manifest("p", "0"), out)


def _delivered(client, project: Path, out: Path) -> None:
    """The first attempt delivered session 1 and its quote, then was stopped."""
    _record_readable(out, "s1")
    _write_quotes(out, [QUOTE])
    _record_quoted(out, "s1")
    _follow(client, project)
    assert client.get("/api/projects/1/condition").json()["lenses"]["quotes"] is True
    _stop(out)
    _follow(client, project)


def _lit(client) -> dict:
    return client.get("/api/projects/1/condition").json()["lenses"]


class TestAResumedRunKeepsWhatWasDelivered:
    def test_quotes_coverage_and_the_report_stay_through_every_moment_of_the_restart(
        self, first_analysis,  # noqa: F811
    ) -> None:
        project, out, client = first_analysis
        _delivered(client, project, out)

        # The run has started; the pipeline has kept nothing aside and written nothing.
        # The live manifest is still the stopped attempt's, which `_predates` refuses.
        _restart(out, held=False, own_manifest=False)
        _follow(client, project)
        assert _lit(client)["quotes"] is True
        assert client.app.state.sessions_imported is True

        # Held aside, and the new run's own manifest is empty.
        hold_for_resume(load_manifest(out), out)
        write_manifest(create_manifest("p", "0"), out)
        _follow(client, project)
        assert _lit(client)["quotes"] is True
        assert delivery_coverage(client.app.state) == {
            "analysis": "running", "sessions_readable": 1,
            "sessions_total": 1, "sessions_with_quotes": 1,
        }
        assert client.app.state.sessions_imported is True

        # A second Stop before any record is written keeps what the first delivered.
        _stop(out, "RUN2")
        _follow(client, project)
        assert _lit(client)["quotes"] is True
        assert client.app.state.progress.ended is True

    def test_a_serve_restarted_mid_resume_finds_the_same(self, first_analysis) -> None:  # noqa: F811
        project, out, client = first_analysis
        _delivered(client, project, out)
        _restart(out, held=True, own_manifest=True)
        client.app.state.__dict__.pop("_test_follower")  # a new serve: a new follower
        _follow(client, project)
        assert _lit(client)["quotes"] is True

    def test_after_a_second_restart_the_newer_attempts_delivery_counts(
        self, first_analysis,  # noqa: F811
    ) -> None:
        """Before the pipeline holds the live manifest aside, the held copy is the
        OLDER record: attempt 2's delivery lives in the live manifest."""
        project, out, client = first_analysis
        stale = create_manifest("p", "0")  # attempt 1: nothing delivered
        hold_for_resume(stale, out)
        _delivered(client, project, out)  # attempt 2 delivered s1 and its quote
        _restart(out, held=False, own_manifest=False)
        hold_for_resume(stale, out)  # the held file is still attempt 1's
        _follow(client, project)
        assert _lit(client)["quotes"] is True

    def test_a_session_without_quotes_leaves_quotes_dark(self, first_analysis) -> None:  # noqa: F811
        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        _stop(out)
        _restart(out, held=True, own_manifest=True)
        _follow(client, project)
        assert _lit(client)["quotes"] is False
        assert client.app.state.progress.readable == {"s1"}

    def test_a_clean_reanalyse_starts_from_nothing(self, first_analysis) -> None:  # noqa: F811
        """`run --clean` moves the output folder's records aside: no manifest, no seed,
        and Re-analyse stays the one way back to zero."""
        project, out, client = first_analysis
        _delivered(client, project, out)
        hold_for_resume(load_manifest(out), out)  # an earlier restart left a held copy too
        _start_run(out, "RUN2")
        for name in ("pipeline-manifest.json", "pipeline-manifest.resume.json"):
            (out / ".bristlenose" / name).unlink()
        _follow(client, project)
        assert _lit(client)["quotes"] is False
        assert client.app.state.progress.readable == frozenset()

    def test_a_seeded_session_still_reaches_the_redacted_re_read(
        self, first_analysis,  # noqa: F811
    ) -> None:
        """The seed is published, not worked: when this run records s1 redacted, the
        importer still re-reads it from the redacted copy."""
        from bristlenose.manifest import STAGE_PII_REMOVAL, mark_stage_running

        project, out, client = first_analysis
        _delivered(client, project, out)
        _restart(out, held=True, own_manifest=True)
        cooked = out / "transcripts-cooked"
        cooked.mkdir()
        raw = (out / "transcripts-raw" / "s1.txt").read_text(encoding="utf-8")
        (cooked / "s1.txt").write_text(
            raw.replace("it is good to be here", "I am [NAME]"), encoding="utf-8")
        m = load_manifest(out)
        mark_stage_running(m, STAGE_PII_REMOVAL)
        mark_session_complete(m, STAGE_PII_REMOVAL, "s1")
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, "s1")
        write_manifest(m, out)
        _follow(client, project)
        assert "Thanks for having me, I am [NAME]." in [t for _, t in _segments(client, "s1")]

    def test_the_seed_claims_only_what_the_database_holds(self, first_analysis) -> None:  # noqa: F811
        """The record vouches for s2, which nobody imported (the serve was not up, or
        the rows were cleared): it is not claimed."""
        project, out, client = first_analysis
        _delivered(client, project, out)
        m = load_manifest(out)
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, "s2")
        _record = m  # s2 vouched readable and quoted, absent from the database
        from bristlenose.manifest import STAGE_QUOTE_EXTRACTION

        mark_session_complete(_record, STAGE_QUOTE_EXTRACTION, "s2")
        write_manifest(_record, out)
        _restart(out, held=True, own_manifest=True)
        _follow(client, project)
        assert client.app.state.progress.readable == {"s1"}
        assert client.app.state.progress.quoted == {"s1"}

    def test_the_seed_never_shrinks_when_the_held_copy_replaces_the_live_manifest(
        self, first_analysis,  # noqa: F811
    ) -> None:
        project, out, client = first_analysis
        _delivered(client, project, out)
        _restart(out, held=False, own_manifest=False)
        _follow(client, project)  # seeded from the live manifest: s1 and its quote
        hold_for_resume(create_manifest("p", "0"), out)  # a held copy that vouches for nothing
        write_manifest(create_manifest("p", "0"), out)
        _follow(client, project)
        assert client.app.state.progress.quoted == {"s1"}
        assert _lit(client)["quotes"] is True

    def test_a_database_that_will_not_answer_seeds_nothing_and_says_so_once(
        self, first_analysis, monkeypatch, caplog,  # noqa: F811
    ) -> None:
        from bristlenose.server.progressive import ProgressiveImport

        def _no_such_table(self, readable, quoted):
            raise RuntimeError("no such table: sessions")

        project, out, client = first_analysis
        _delivered(client, project, out)
        monkeypatch.setattr(ProgressiveImport, "_held_by_database", _no_such_table)
        # Before the run's own manifest is written the seed is not final: every tick
        # tries again, and a failure that persists is said once.
        _restart(out, held=True, own_manifest=False)
        client.app.state.__dict__.pop("_test_follower")
        for _ in range(3):
            _follow(client, project)
        said = [r for r in caplog.records if "cannot read the database" in r.getMessage()]
        assert len(said) == 1
        assert client.app.state.progress.readable == frozenset()
