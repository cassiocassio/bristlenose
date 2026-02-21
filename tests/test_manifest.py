"""Tests for bristlenose.manifest — manifest model and read/write helpers."""

from __future__ import annotations

from pathlib import Path

from bristlenose.manifest import (
    STAGE_INGEST,
    STAGE_ORDER,
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
    STAGE_TRANSCRIBE,
    StageStatus,
    _derive_stage_status,
    create_manifest,
    get_completed_session_ids,
    load_manifest,
    mark_session_complete,
    mark_stage_complete,
    mark_stage_running,
    write_manifest,
)


def test_create_manifest_fields():
    m = create_manifest("test-project", "0.10.1")
    assert m.schema_version == 1
    assert m.project_name == "test-project"
    assert m.pipeline_version == "0.10.1"
    assert m.stages == {}
    assert m.total_cost_usd == 0.0
    assert m.created_at == m.updated_at


def test_mark_stage_running():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_INGEST)
    rec = m.stages[STAGE_INGEST]
    assert rec.status == StageStatus.RUNNING
    assert rec.started_at is not None
    assert rec.completed_at is None


def test_mark_stage_complete():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_INGEST)
    mark_stage_complete(m, STAGE_INGEST)
    rec = m.stages[STAGE_INGEST]
    assert rec.status == StageStatus.COMPLETE
    assert rec.completed_at is not None
    # started_at should be preserved
    assert rec.started_at is not None


def test_write_and_load_manifest(tmp_path: Path):
    m = create_manifest("roundtrip", "0.10.1")
    mark_stage_running(m, STAGE_INGEST)
    mark_stage_complete(m, STAGE_INGEST)
    mark_stage_running(m, STAGE_TRANSCRIBE)

    write_manifest(m, tmp_path)
    loaded = load_manifest(tmp_path)

    assert loaded is not None
    assert loaded.project_name == "roundtrip"
    assert loaded.stages[STAGE_INGEST].status == StageStatus.COMPLETE
    assert loaded.stages[STAGE_TRANSCRIBE].status == StageStatus.RUNNING


def test_load_manifest_missing(tmp_path: Path):
    assert load_manifest(tmp_path) is None


def test_stage_order_has_all_stages():
    assert len(STAGE_ORDER) == 10
    assert STAGE_INGEST == STAGE_ORDER[0]


def test_atomic_write_creates_no_tmp_file(tmp_path: Path):
    """After write_manifest, only the final file should exist (no .tmp)."""
    m = create_manifest("atomic", "1.0")
    write_manifest(m, tmp_path)
    manifest_dir = tmp_path / ".bristlenose"
    files = list(manifest_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "pipeline-manifest.json"


# ---------------------------------------------------------------------------
# Per-session tracking (Phase 1d)
# ---------------------------------------------------------------------------


def test_mark_session_complete_creates_session_record():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    mark_session_complete(
        m, STAGE_TOPIC_SEGMENTATION, "s1", provider="anthropic", model="sonnet",
    )
    rec = m.stages[STAGE_TOPIC_SEGMENTATION]
    assert rec.sessions is not None
    assert "s1" in rec.sessions
    sr = rec.sessions["s1"]
    assert sr.status == StageStatus.COMPLETE
    assert sr.session_id == "s1"
    assert sr.provider == "anthropic"
    assert sr.model == "sonnet"
    assert sr.completed_at is not None


def test_mark_session_complete_leaves_stage_running():
    """Stage stays RUNNING after per-session marks — needs explicit complete."""
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s1")
    # Stage should still be RUNNING until mark_stage_complete is called
    assert m.stages[STAGE_QUOTE_EXTRACTION].status == StageStatus.RUNNING


def test_mark_stage_complete_after_sessions():
    """mark_stage_complete sets COMPLETE after all sessions are marked."""
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s1")
    mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s2")
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    assert m.stages[STAGE_QUOTE_EXTRACTION].status == StageStatus.COMPLETE


def test_derive_stage_status_no_sessions():
    from bristlenose.manifest import StageRecord

    rec = StageRecord(status=StageStatus.RUNNING)
    assert _derive_stage_status(rec) == StageStatus.RUNNING


def test_derive_stage_status_all_complete():
    from bristlenose.manifest import SessionRecord, StageRecord

    rec = StageRecord(
        status=StageStatus.RUNNING,
        sessions={
            "s1": SessionRecord(status=StageStatus.COMPLETE, session_id="s1"),
            "s2": SessionRecord(status=StageStatus.COMPLETE, session_id="s2"),
        },
    )
    assert _derive_stage_status(rec) == StageStatus.COMPLETE


def test_derive_stage_status_mixed():
    from bristlenose.manifest import SessionRecord, StageRecord

    rec = StageRecord(
        status=StageStatus.RUNNING,
        sessions={
            "s1": SessionRecord(status=StageStatus.COMPLETE, session_id="s1"),
            "s2": SessionRecord(status=StageStatus.PENDING, session_id="s2"),
        },
    )
    assert _derive_stage_status(rec) == StageStatus.PARTIAL


def test_derive_stage_status_all_pending():
    from bristlenose.manifest import SessionRecord, StageRecord

    rec = StageRecord(
        status=StageStatus.RUNNING,
        sessions={
            "s1": SessionRecord(status=StageStatus.PENDING, session_id="s1"),
            "s2": SessionRecord(status=StageStatus.PENDING, session_id="s2"),
        },
    )
    assert _derive_stage_status(rec) == StageStatus.PENDING


def test_get_completed_session_ids_none_manifest():
    assert get_completed_session_ids(None, STAGE_TOPIC_SEGMENTATION) == set()


def test_get_completed_session_ids_no_sessions():
    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    assert get_completed_session_ids(m, STAGE_TOPIC_SEGMENTATION) == set()


def test_get_completed_session_ids_mixed():
    from bristlenose.manifest import SessionRecord

    m = create_manifest("p", "1.0")
    mark_stage_running(m, STAGE_TOPIC_SEGMENTATION)
    rec = m.stages[STAGE_TOPIC_SEGMENTATION]
    rec.sessions = {
        "s1": SessionRecord(status=StageStatus.COMPLETE, session_id="s1"),
        "s2": SessionRecord(status=StageStatus.PENDING, session_id="s2"),
        "s3": SessionRecord(status=StageStatus.COMPLETE, session_id="s3"),
    }
    result = get_completed_session_ids(m, STAGE_TOPIC_SEGMENTATION)
    assert result == {"s1", "s3"}


def test_session_records_roundtrip(tmp_path: Path):
    """Session records survive write → load round-trip."""
    m = create_manifest("roundtrip", "1.0")
    mark_stage_running(m, STAGE_QUOTE_EXTRACTION)
    mark_session_complete(
        m, STAGE_QUOTE_EXTRACTION, "s1", provider="google", model="gemini",
    )
    mark_session_complete(
        m, STAGE_QUOTE_EXTRACTION, "s2", provider="anthropic", model="sonnet",
    )
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION)
    write_manifest(m, tmp_path)

    loaded = load_manifest(tmp_path)
    assert loaded is not None
    rec = loaded.stages[STAGE_QUOTE_EXTRACTION]
    assert rec.sessions is not None
    assert len(rec.sessions) == 2
    assert rec.sessions["s1"].provider == "google"
    assert rec.sessions["s2"].model == "sonnet"
    assert rec.status == StageStatus.COMPLETE
