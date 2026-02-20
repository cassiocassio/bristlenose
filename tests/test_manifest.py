"""Tests for bristlenose.manifest — manifest model and read/write helpers."""

from __future__ import annotations

from pathlib import Path

from bristlenose.manifest import (
    STAGE_INGEST,
    STAGE_ORDER,
    STAGE_TRANSCRIBE,
    StageStatus,
    create_manifest,
    load_manifest,
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
