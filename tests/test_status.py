"""Tests for bristlenose.status — project status report."""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_INGEST,
    STAGE_QUOTE_EXTRACTION,
    STAGE_RENDER,
    STAGE_TOPIC_SEGMENTATION,
    STAGE_TRANSCRIBE,
    StageStatus,
    create_manifest,
    mark_session_complete,
    mark_stage_complete,
    mark_stage_running,
    write_manifest,
)
from bristlenose.status import (
    format_resume_summary,
    get_project_status,
)


def _write_manifest(tmp_path: Path, manifest):
    """Write a manifest to a tmp_path output directory."""
    write_manifest(manifest, tmp_path)


def _make_intermediate(tmp_path: Path, filename: str, data: list):
    """Write an intermediate JSON file."""
    idir = tmp_path / ".bristlenose" / "intermediate"
    idir.mkdir(parents=True, exist_ok=True)
    (idir / filename).write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# get_project_status
# ---------------------------------------------------------------------------


def test_no_manifest_returns_none(tmp_path):
    assert get_project_status(tmp_path) is None


def test_empty_manifest_all_pending(tmp_path):
    m = create_manifest("my-project", "0.10.2")
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None
    assert status.project_name == "my-project"
    assert status.pipeline_version == "0.10.2"

    # All displayed stages should be PENDING
    for stage in status.stages:
        assert stage.status == StageStatus.PENDING


def test_completed_stages_shown(tmp_path):
    m = create_manifest("ikea-study", "0.10.2")
    mark_stage_running(m, STAGE_INGEST)
    mark_stage_complete(m, STAGE_INGEST)
    mark_stage_running(m, STAGE_TRANSCRIBE)
    mark_session_complete(m, STAGE_TRANSCRIBE, "s1")
    mark_session_complete(m, STAGE_TRANSCRIBE, "s2")
    mark_stage_complete(m, STAGE_TRANSCRIBE)
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None

    ingest = next(s for s in status.stages if s.stage_key == "ingest")
    assert ingest.status == StageStatus.COMPLETE

    transcribe = next(s for s in status.stages if s.stage_key == "transcribe")
    assert transcribe.status == StageStatus.COMPLETE
    assert transcribe.session_total == 2
    assert transcribe.session_complete == 2
    assert "2 sessions" in transcribe.detail


def test_partial_stage_shows_incomplete(tmp_path):
    m = create_manifest("partial-study", "0.10.2")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s1")
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s2")
    # s3 not completed — stage stays RUNNING
    # Add s3 as a pending session record manually
    from bristlenose.manifest import SessionRecord

    record = m.stages[STAGE_QUOTE_EXTRACTION]
    assert record.sessions is not None
    record.sessions["s3"] = SessionRecord(
        status=StageStatus.PENDING,
        session_id="s3",
    )
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None

    quotes = next(s for s in status.stages if s.stage_key == "quote_extraction")
    assert quotes.status == StageStatus.PARTIAL
    assert quotes.session_total == 3
    assert quotes.session_complete == 2
    assert "1 incomplete" in quotes.detail


def test_quote_count_from_intermediate_json(tmp_path):
    m = create_manifest("counted-study", "0.10.2")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s1")
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s2")
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    _write_manifest(tmp_path, m)

    # Write intermediate JSON with 5 quotes
    _make_intermediate(tmp_path, "extracted_quotes.json", [1, 2, 3, 4, 5])

    status = get_project_status(tmp_path)
    quotes = next(s for s in status.stages if s.stage_key == "quote_extraction")
    assert "5 quotes" in quotes.detail


def test_topic_count_from_intermediate_json(tmp_path):
    m = create_manifest("topics-study", "0.10.2")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    mark_stage_complete(m, STAGE_TOPIC_SEGMENTATION)
    _write_manifest(tmp_path, m)

    _make_intermediate(tmp_path, "topic_boundaries.json", list(range(87)))

    status = get_project_status(tmp_path)
    topics = next(s for s in status.stages if s.stage_key == "topic_segmentation")
    assert "87 boundaries" in topics.detail


def test_cluster_and_theme_counts(tmp_path):
    m = create_manifest("clustered-study", "0.10.2")
    mark_stage_running(m, STAGE_CLUSTER_AND_GROUP)
    mark_stage_complete(m, STAGE_CLUSTER_AND_GROUP)
    _write_manifest(tmp_path, m)

    _make_intermediate(tmp_path, "screen_clusters.json", list(range(12)))
    _make_intermediate(tmp_path, "theme_groups.json", list(range(8)))

    status = get_project_status(tmp_path)
    clusters = next(s for s in status.stages if s.stage_key == "cluster_and_group")
    assert "12 screens" in clusters.detail
    assert "8 themes" in clusters.detail


def test_missing_intermediate_file_warning(tmp_path):
    m = create_manifest("missing-file-study", "0.10.2")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    _write_manifest(tmp_path, m)

    # Don't write extracted_quotes.json — file missing
    status = get_project_status(tmp_path)
    quotes = next(s for s in status.stages if s.stage_key == "quote_extraction")
    assert quotes.status == StageStatus.COMPLETE
    assert quotes.file_exists is False
    assert "missing" in quotes.file_missing_warning


def test_file_exists_when_present(tmp_path):
    m = create_manifest("present-file-study", "0.10.2")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    _write_manifest(tmp_path, m)

    _make_intermediate(tmp_path, "extracted_quotes.json", [1, 2, 3])

    status = get_project_status(tmp_path)
    quotes = next(s for s in status.stages if s.stage_key == "quote_extraction")
    assert quotes.file_exists is True
    assert quotes.file_missing_warning == ""


# ---------------------------------------------------------------------------
# format_resume_summary
# ---------------------------------------------------------------------------


def test_resume_summary_partial_stage(tmp_path):
    m = create_manifest("partial-resume", "0.10.2")
    mark_stage_running(m, STAGE_INGEST)
    mark_stage_complete(m, STAGE_INGEST)
    mark_stage_running(m, STAGE_TRANSCRIBE)
    mark_session_complete(m, STAGE_TRANSCRIBE, "s1")
    mark_session_complete(m, STAGE_TRANSCRIBE, "s2")
    # s3 pending
    from bristlenose.manifest import SessionRecord

    record = m.stages[STAGE_TRANSCRIBE]
    assert record.sessions is not None
    record.sessions["s3"] = SessionRecord(
        status=StageStatus.PENDING,
        session_id="s3",
    )
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None
    summary = format_resume_summary(status)
    assert "2/3" in summary
    assert "1 remaining" in summary


def test_resume_summary_pending_stage(tmp_path):
    m = create_manifest("pending-resume", "0.10.2")
    mark_stage_running(m, STAGE_INGEST)
    mark_stage_complete(m, STAGE_INGEST)
    mark_stage_running(m, STAGE_TRANSCRIBE)
    mark_stage_complete(m, STAGE_TRANSCRIBE)
    mark_stage_running(m, STAGE_IDENTIFY_SPEAKERS)
    mark_stage_complete(m, STAGE_IDENTIFY_SPEAKERS)
    # topic_segmentation not started
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None
    summary = format_resume_summary(status)
    assert "topics" in summary.lower()


def test_resume_summary_all_complete(tmp_path):
    m = create_manifest("all-done", "0.10.2")
    for stage_key in ["ingest", "transcribe", "identify_speakers",
                      "topic_segmentation", "quote_extraction",
                      "cluster_and_group", "render"]:
        mark_stage_running(m, stage_key)
        mark_stage_complete(m, stage_key)
    _write_manifest(tmp_path, m)

    status = get_project_status(tmp_path)
    assert status is not None
    summary = format_resume_summary(status)
    assert "re-render" in summary.lower()


def test_displayed_stages_are_subset():
    """Status should show a curated list, not every internal stage."""
    m = create_manifest("display-test", "0.10.2")
    # Just create empty — check that we get the right number of display stages
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _write_manifest(Path(td), m)
        status = get_project_status(Path(td))
        assert status is not None
        # We display 7 stages (not all 10 internal stages)
        assert len(status.stages) == 7
        stage_keys = [s.stage_key for s in status.stages]
        # extract_audio, merge_transcript, pii_removal are hidden
        assert "extract_audio" not in stage_keys
        assert "merge_transcript" not in stage_keys
        assert "pii_removal" not in stage_keys


def test_render_stage_shows_report_filename(tmp_path):
    m = create_manifest("report-check", "0.10.2")
    mark_stage_running(m, STAGE_RENDER)
    mark_stage_complete(m, STAGE_RENDER)
    _write_manifest(tmp_path, m)

    # Create a report file
    (tmp_path / "bristlenose-report-check-report.html").write_text("<html>", encoding="utf-8")

    status = get_project_status(tmp_path)
    render = next(s for s in status.stages if s.stage_key == "render")
    assert "bristlenose-report-check-report.html" in render.detail
