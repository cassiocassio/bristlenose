"""The Discussion stage's place in the pipeline: off means untouched, on writes
one record, and the cache reruns only when the quotes or the guide change."""

from __future__ import annotations

import asyncio
import json

from bristlenose.config import load_settings
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
    assert json.loads(path.read_text())["guide"] is True
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

    (folder / "guide.md").write_text("# Guide\n## Money\n- Do you budget?\n")
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
    (tmp_path / "interview.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nhi\n")
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
