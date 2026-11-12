"""The Discussion stage's place in the pipeline: off means untouched, on writes
one record, and the cache reruns only when the quotes or the guide change."""

from __future__ import annotations

import asyncio
import json

from bristlenose.config import load_settings
from bristlenose.discussion.guide import GUIDE_FOLDER
from bristlenose.manifest import STAGE_DISCUSSION, STAGE_ORDER, StageStatus, create_manifest
from bristlenose.pipeline import Pipeline
from bristlenose.stages.s01_ingest import discover_files
from bristlenose.status import get_project_status
from tests.test_discussion_stage import FakeClient, two_sessions, write_guide


def _run(tmp_path, client, *, on=True, manifest=None, prev=None):
    pipeline = Pipeline(load_settings(discussion_lens=on))
    transcripts, quotes = two_sessions()
    out = tmp_path / "bristlenose-output"
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, out, client, manifest, prev))
    return out / ".bristlenose" / "intermediate" / "discussion.json"


def test_off_reads_writes_and_records_nothing(tmp_path):
    write_guide(tmp_path)
    client, manifest = FakeClient(), create_manifest("p", "0")
    path = _run(tmp_path, client, on=False, manifest=manifest)
    assert client.calls == []
    assert not path.exists()
    assert STAGE_DISCUSSION not in manifest.stages


def test_on_writes_the_record_and_completes_the_stage(tmp_path):
    write_guide(tmp_path)
    manifest = create_manifest("p", "0")
    path = _run(tmp_path, FakeClient(), manifest=manifest)
    assert json.loads(path.read_text(encoding="utf-8"))["guide"] is True
    record = manifest.stages[STAGE_DISCUSSION]
    assert record.status == StageStatus.COMPLETE
    assert set(record.sessions or {}) == {"s1", "s2"}


def test_unchanged_inputs_are_cached_and_a_new_guide_is_not(tmp_path):
    folder = write_guide(tmp_path)
    first = create_manifest("p", "0")
    _run(tmp_path, FakeClient(), manifest=first)

    again = FakeClient()
    _run(tmp_path, again, manifest=create_manifest("p", "0"), prev=first)
    assert again.calls == []

    (folder / "guide.md").write_text("# Guide\n## Money\n- Do you budget?\n", encoding="utf-8")
    edited = FakeClient()
    _run(tmp_path, edited, manifest=create_manifest("p", "0"), prev=first)
    assert edited.calls  # the guide is part of what the record was built from


def test_a_failed_session_leaves_the_stage_to_rerun(tmp_path):
    write_guide(tmp_path)
    manifest = create_manifest("p", "0")
    _run(tmp_path, FakeClient(fail_on="s2"), manifest=manifest)
    record = manifest.stages[STAGE_DISCUSSION]
    assert record.status == StageStatus.PARTIAL
    assert record.sessions["s2"].status == StageStatus.FAILED


def test_runs_after_themes_and_before_the_report():
    assert STAGE_ORDER.index(STAGE_DISCUSSION) == STAGE_ORDER.index("cluster_and_group") + 1
    assert STAGE_ORDER[-1] == "render"


def test_status_shows_the_stage_only_where_a_run_recorded_it(tmp_path):
    from bristlenose.manifest import write_manifest

    out = tmp_path / "bristlenose-output"
    manifest = create_manifest("p", "0")
    write_manifest(manifest, out)
    assert "discussion" not in [s.stage_key for s in get_project_status(out).stages]

    write_guide(tmp_path)
    _run(tmp_path, FakeClient(), manifest=manifest)  # writes the manifest itself
    keys = [s.stage_key for s in get_project_status(out).stages]
    assert keys[-2:] == ["discussion", "render"]


def test_ingest_never_reads_the_guide_as_a_session(tmp_path):
    folder = write_guide(tmp_path)
    (folder / "guide.docx").write_bytes(b"PK\x03\x04")
    (tmp_path / "interview.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nhi\n", encoding="utf-8")
    skipped: list = []
    found = discover_files(tmp_path, skipped)
    assert [f.path.name for f in found] == ["interview.vtt"]
    assert skipped == []


# ── timing and progress ──────────────────────────────────────────────────────


def _estimator(tmp_path):
    from bristlenose.timing import TimingEstimator, WelfordStat

    est = TimingEstimator("h", tmp_path)
    est._profile = {s: WelfordStat(mean=10.0, n=5) for s in ("cluster", "discussion", "render")}
    return est


def test_the_estimate_counts_the_stage_only_when_it_will_run(tmp_path):
    off = _estimator(tmp_path).initial_estimate(0, 3)
    on = _estimator(tmp_path).initial_estimate(0, 3, discussion_enabled=True)
    assert "discussion" not in off.breakdown
    assert on.breakdown["discussion"] == 30.0


def test_a_stage_that_is_off_is_never_remaining(tmp_path):
    est = _estimator(tmp_path)
    est.initial_estimate(0, 3)
    remaining = est.stage_completed("cluster", 30.0)
    assert "discussion" not in remaining.breakdown


def test_the_stage_announces_itself_fresh_and_cached(tmp_path):
    write_guide(tmp_path)
    out = tmp_path / "bristlenose-output"
    first = create_manifest("p", "0")
    transcripts, quotes = two_sessions()

    def run(prev):
        pipeline = Pipeline(load_settings(discussion_lens=True))
        seen: list = []
        pipeline.set_progress_sink(lambda **f: seen.append(f.get("stage")))
        elapsed = asyncio.run(pipeline._run_discussion(
            transcripts, quotes, tmp_path, out, FakeClient(), first if prev is None else
            create_manifest("p", "0"), prev))
        return seen, elapsed

    seen, elapsed = run(None)
    assert "discussion" in seen and elapsed is not None  # a fresh run is timed
    seen, elapsed = run(first)
    assert "discussion" in seen and elapsed is None  # cached: announced, not timed


# ── caching, after the silent-failure review of 3 Oct 2026 ───────────────────


def _runs(tmp_path, clients, transcripts=None):
    """Consecutive runs, each handed the previous run's manifest as `prev`."""
    calls, prev = [], None
    for client in clients:
        manifest = create_manifest("p", "0")
        pipeline = Pipeline(load_settings(discussion_lens=True))
        ts, quotes = two_sessions()
        asyncio.run(pipeline._run_discussion(
            transcripts or ts, quotes, tmp_path, tmp_path / "bristlenose-output",
            client, manifest, prev))
        calls.append(len(client.calls))
        prev = manifest
    return calls, prev


def test_a_cached_run_carries_its_record_so_the_next_is_cached_too(tmp_path):
    write_guide(tmp_path)
    calls, last = _runs(tmp_path, [FakeClient(), FakeClient(), FakeClient()])
    assert calls[0] > 0 and calls[1:] == [0, 0]
    assert STAGE_DISCUSSION in last.stages


def test_a_failed_run_level_call_is_retried_not_cached(tmp_path):
    from tests.test_discussion_stage import ConsolidateOut, SpineOut

    write_guide(tmp_path)
    for kind in (SpineOut, ConsolidateOut):
        calls, last = _runs(tmp_path, [FakeClient(fail_kinds=(kind,)), FakeClient()])
        assert calls[1] > 0, kind  # the second run pays again rather than serving the gap
        assert last.stages[STAGE_DISCUSSION].status == StageStatus.COMPLETE


def test_a_changed_transcript_reruns_the_stage(tmp_path):
    write_guide(tmp_path)
    _, first = _runs(tmp_path, [FakeClient()])
    ts, quotes = two_sessions()
    ts[0].segments[2].text = "Tell me who shares your home with you"  # a redaction would do this
    client = FakeClient()
    asyncio.run(Pipeline(load_settings(discussion_lens=True))._run_discussion(
        ts, quotes, tmp_path, tmp_path / "bristlenose-output", client,
        create_manifest("p", "0"), first))
    assert client.calls


def test_a_corrupt_guide_never_ends_the_run(tmp_path):
    folder = tmp_path / GUIDE_FOLDER
    folder.mkdir()
    (folder / "guide.docx").write_bytes(b"\xd0\xcf\x11\xe0 an encrypted Word file")
    path = _run(tmp_path, FakeClient(), manifest=create_manifest("p", "0"))
    assert json.loads(path.read_text(encoding="utf-8"))["guide_problem"] == "unreadable"


def test_an_unmoderated_study_is_skipped_not_warned():
    from bristlenose.discussion.models import DiscussionRecord, RecordSession
    from bristlenose.pipeline import _discussion_line
    from bristlenose.ui_kinds import MessageKind

    solo = DiscussionRecord(status="failed", sessions=[
        RecordSession(id=f"s{i}", number=i, state="no_moderator") for i in (1, 2)])
    line, kind = _discussion_line(solo, retry=False)
    assert kind == MessageKind.SKIPPED and "no session has a moderator" in line

    unclear = DiscussionRecord(status="failed", sessions=[
        RecordSession(id="s1", number=1, state="moderator_unreliable")])
    assert _discussion_line(unclear, retry=False)[1] == MessageKind.WARNING


def test_a_crashed_stage_leaves_a_failed_record_not_none(tmp_path, monkeypatch):
    """No record reads as "never run"; a crash must say it failed."""
    import bristlenose.discussion.stage as stage_mod

    async def boom(*a, **k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(stage_mod, "run_discussion", boom)
    manifest = create_manifest("p", "0")
    path = _run(tmp_path, FakeClient(), manifest=manifest)
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "failed"
    assert manifest.stages[STAGE_DISCUSSION].status != StageStatus.COMPLETE  # retried next run


# ── N128: a lens that failed is not a plain "Done" ───────────────────────────


def test_a_stage_that_raises_is_remembered_for_the_end_line(tmp_path, monkeypatch):
    write_guide(tmp_path)
    pipeline = Pipeline(load_settings(discussion_lens=True))
    assert pipeline._discussion_failed is False

    async def boom(*_a, **_k):
        raise RuntimeError("model fell over")

    monkeypatch.setattr("bristlenose.discussion.stage.run_discussion", boom)
    transcripts, quotes = two_sessions()
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output", FakeClient(),
        create_manifest("p", "0"), None))
    assert pipeline._discussion_failed is True

    # A later stage that works clears it: the flag is about this attempt only.
    monkeypatch.undo()
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output2", FakeClient(),
        create_manifest("p", "0"), None))
    assert pipeline._discussion_failed is False


def test_the_end_line_names_a_missing_lens():
    from bristlenose.pipeline import _with_lens_warning

    assert _with_lens_warning("", False) == ""
    assert _with_lens_warning("no quotes from s2", False) == "no quotes from s2"
    assert _with_lens_warning("", True) == "the discussion lens wasn't built"
    assert _with_lens_warning("no quotes from s2", True) == (
        "no quotes from s2 · the discussion lens wasn't built"
    )


def test_the_run_end_line_asks_the_pipeline_not_the_helper():
    """The two entry points close their warning through `_end_warning`; a run that
    ended in error leaves it alone."""
    pipeline = Pipeline(load_settings(discussion_lens=True))
    pipeline._discussion_failed = True
    assert pipeline._end_warning("", "") == "the discussion lens wasn't built"
    assert pipeline._end_warning("", "no quotes from s2") == (
        "no quotes from s2 · the discussion lens wasn't built"
    )
    assert pipeline._end_warning("credits low", "") == ""
    pipeline._discussion_failed = False
    assert pipeline._end_warning("", "") == ""


def test_an_unreadable_people_file_is_on_the_end_line_too():
    """N82: the run carries on without the names in a people.yaml it could not
    read, so it must not end as a plain Done."""
    pipeline = Pipeline(load_settings(discussion_lens=False))
    assert pipeline._end_warning("", "") == ""
    pipeline._people_unreadable = True
    assert pipeline._end_warning("", "") == "people.yaml couldn't be read"
    pipeline._discussion_failed = True
    assert pipeline._end_warning("", "no quotes from s2") == (
        "no quotes from s2 · people.yaml couldn't be read · the discussion lens wasn't built"
    )
    assert pipeline._end_warning("credits low", "") == ""


def test_a_lens_the_model_could_not_read_any_session_for_is_a_failure_too(tmp_path):
    """N128: every session's classify call failed, so the lens was not built. The
    stage did not raise, but the lens is missing for a reason that broke, so the
    run must not end as a plain Done."""
    from bristlenose.discussion.models import SessionLabelsOut

    write_guide(tmp_path)
    pipeline = Pipeline(load_settings(discussion_lens=True))
    transcripts, quotes = two_sessions()
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output",
        FakeClient(fail_kinds=(SessionLabelsOut,)), create_manifest("p", "0"), None))
    assert pipeline._discussion_failed is True


def test_an_unmoderated_study_is_not_a_failure(tmp_path):
    """A solo think-aloud has no moderator in any session: skipped, nothing wrong."""
    pipeline = Pipeline(load_settings(discussion_lens=True))
    transcripts, quotes = two_sessions()
    for t in transcripts:  # no moderator turns anywhere
        t.segments = [seg for seg in t.segments if seg.speaker_code.startswith("p")]
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output", FakeClient(),
        create_manifest("p", "0"), None))
    assert pipeline._discussion_failed is False


# ── what the Mac is told (N128): the run summary's warnings ──────────────────


def _record(status, *states):
    from bristlenose.discussion.models import DiscussionRecord, RecordSession

    return DiscussionRecord(
        status=status,
        sessions=[RecordSession(id=f"s{i}", number=i, state=st) for i, st in enumerate(states, 1)],
    )


def test_the_reason_a_lens_is_missing_is_a_closed_vocabulary():
    from bristlenose.events import StageOutcome
    from bristlenose.pipeline import _discussion_warning

    empty = StageOutcome(attempted=0, succeeded=0, failed=[])
    # An unmoderated study, a built lens and a partial one say nothing.
    assert _discussion_warning(_record("failed", "no_moderator", "no_moderator"), empty) is None
    assert _discussion_warning(_record("complete", "ok", "ok"), empty) is None
    assert _discussion_warning(_record("partial", "ok", "failed"), empty) is None
    # Moderators exist but none could be told from the rest.
    w = _discussion_warning(_record("failed", "moderator_unreliable", "no_moderator"), empty)
    assert (w.kind, w.reason, w.line) == ("discussion_lens", "no_clear_moderator", None)


def test_a_lens_the_model_could_not_read_reaches_the_summary_with_its_cause(tmp_path):
    from bristlenose.discussion.models import SessionLabelsOut

    write_guide(tmp_path)
    pipeline = Pipeline(load_settings(discussion_lens=True))
    pipeline._summary.warnings = None
    transcripts, quotes = two_sessions()
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output",
        FakeClient(fail_kinds=(SessionLabelsOut,)), create_manifest("p", "0"), None))
    warnings = pipeline._summary.warnings
    assert warnings is not None and len(warnings) == 1
    assert warnings[0].kind == "discussion_lens"
    from bristlenose.events import CauseCategoryEnum

    # a CauseCategoryEnum value, never free text: the Mac maps it to a short label
    assert warnings[0].reason in {c.value for c in CauseCategoryEnum}


def test_a_stage_that_raised_reaches_the_summary_as_unknown(tmp_path, monkeypatch):
    write_guide(tmp_path)
    pipeline = Pipeline(load_settings(discussion_lens=True))

    async def boom(*_a, **_k):
        raise RuntimeError("model fell over")

    monkeypatch.setattr("bristlenose.discussion.stage.run_discussion", boom)
    transcripts, quotes = two_sessions()
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output", FakeClient(),
        create_manifest("p", "0"), None))
    assert [(w.kind, w.reason) for w in pipeline._summary.warnings] == [("discussion_lens", "unknown")]


def test_an_unmoderated_study_puts_nothing_in_the_summary(tmp_path):
    pipeline = Pipeline(load_settings(discussion_lens=True))
    transcripts, quotes = two_sessions()
    for t in transcripts:
        t.segments = [seg for seg in t.segments if seg.speaker_code.startswith("p")]
    asyncio.run(pipeline._run_discussion(
        transcripts, quotes, tmp_path, tmp_path / "bristlenose-output", FakeClient(),
        create_manifest("p", "0"), None))
    assert not pipeline._summary.warnings


def test_a_cached_lens_with_no_clear_moderator_still_warns(tmp_path, monkeypatch):
    """The record of a lens with no clear moderator is cached (nothing to retry), and it
    is as missing on the next run as on the first: the end line and the Mac row must not
    go back to a plain Done because the answer was read from disk."""
    from bristlenose.events import StageOutcome

    async def unclear(*_a, **_k):
        return _record("failed", "moderator_unreliable", "moderator_unreliable"), StageOutcome(
            attempted=2, succeeded=0, failed=[])

    monkeypatch.setattr("bristlenose.discussion.stage.run_discussion", unclear)
    transcripts, quotes = two_sessions()
    out = tmp_path / "bristlenose-output"
    first = create_manifest("p", "0")
    fresh = Pipeline(load_settings(discussion_lens=True))
    asyncio.run(fresh._run_discussion(transcripts, quotes, tmp_path, out, FakeClient(), first, None))
    assert [w.reason for w in fresh._summary.warnings] == ["no_clear_moderator"]

    again, client = Pipeline(load_settings(discussion_lens=True)), FakeClient()
    asyncio.run(again._run_discussion(
        transcripts, quotes, tmp_path, out, client, create_manifest("p", "0"), first))
    assert client.calls == []  # served from the cache
    assert [(w.kind, w.reason) for w in again._summary.warnings or []] == [
        ("discussion_lens", "no_clear_moderator")]
    assert again._end_warning("", "") == "the discussion lens wasn't built"


def test_a_cached_unmoderated_study_stays_silent(tmp_path):
    transcripts, quotes = two_sessions()
    for t in transcripts:
        t.segments = [seg for seg in t.segments if seg.speaker_code.startswith("p")]
    out = tmp_path / "bristlenose-output"
    first = create_manifest("p", "0")
    asyncio.run(Pipeline(load_settings(discussion_lens=True))._run_discussion(
        transcripts, quotes, tmp_path, out, FakeClient(), first, None))
    again, client = Pipeline(load_settings(discussion_lens=True)), FakeClient()
    asyncio.run(again._run_discussion(
        transcripts, quotes, tmp_path, out, client, create_manifest("p", "0"), first))
    assert client.calls == []
    assert not again._summary.warnings and again._end_warning("", "") == ""
