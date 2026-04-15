"""Tests for Phase 2b — verify content hashes on cached stage outputs."""

from __future__ import annotations

from pathlib import Path

from bristlenose.hashing import hash_bytes, verify_file_hash
from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_QUOTE_EXTRACTION,
    PipelineManifest,
    SessionRecord,
    StageRecord,
    StageStatus,
)
from bristlenose.pipeline import _is_speaker_stage_verified, _is_stage_verified

# ── verify_file_hash ──────────────────────────────────────────────


def test_verify_file_hash_match(tmp_path: Path):
    f = tmp_path / "data.json"
    f.write_bytes(b'{"quotes": []}')
    h = hash_bytes(f.read_bytes())
    assert verify_file_hash(f, h) is True


def test_verify_file_hash_mismatch(tmp_path: Path):
    f = tmp_path / "data.json"
    f.write_bytes(b'{"quotes": []}')
    assert verify_file_hash(f, "0" * 64) is False


def test_verify_file_hash_none_expected(tmp_path: Path):
    """Old manifests with no hash → always passes (backward compat)."""
    f = tmp_path / "data.json"
    f.write_bytes(b"anything")
    assert verify_file_hash(f, None) is True


def test_verify_file_hash_missing_file(tmp_path: Path):
    assert verify_file_hash(tmp_path / "gone.json", "abc123") is False


# ── helpers ───────────────────────────────────────────────────────


def _manifest_with_stage(
    stage: str,
    content_hash: str | None = None,
    sessions: dict[str, SessionRecord] | None = None,
    input_hashes: dict[str, str] | None = None,
) -> PipelineManifest:
    return PipelineManifest(
        schema_version=1,
        project_name="test",
        pipeline_version="0.14.2",
        created_at="2026-03-24T00:00:00Z",
        updated_at="2026-03-24T00:00:00Z",
        stages={
            stage: StageRecord(
                status=StageStatus.COMPLETE,
                content_hash=content_hash,
                sessions=sessions,
                input_hashes=input_hashes,
            ),
        },
    )


# ── _is_stage_verified (single-file stages) ──────────────────────


def test_stage_verified_match(tmp_path: Path):
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    m = _manifest_with_stage(STAGE_QUOTE_EXTRACTION, content_hash=h)
    assert _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [f]) is True


def test_stage_verified_mismatch(tmp_path: Path):
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    m = _manifest_with_stage(STAGE_QUOTE_EXTRACTION, content_hash="0" * 64)
    assert _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [f]) is False


def test_stage_verified_mismatch_invalidates_manifest(tmp_path: Path):
    """Hash mismatch removes the stage from the manifest so per-session
    resume won't try to load corrupt data."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    m = _manifest_with_stage(STAGE_QUOTE_EXTRACTION, content_hash="0" * 64)
    _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [f])
    assert STAGE_QUOTE_EXTRACTION not in m.stages


def test_stage_verified_no_manifest():
    assert _is_stage_verified(None, STAGE_QUOTE_EXTRACTION, []) is False


def test_stage_verified_no_hash_backward_compat(tmp_path: Path):
    """Old manifests without content_hash → trust the cache."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    m = _manifest_with_stage(STAGE_QUOTE_EXTRACTION, content_hash=None)
    assert _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [f]) is True


def test_stage_verified_missing_file(tmp_path: Path):
    gone = tmp_path / "gone.json"
    h = "abc123"
    m = _manifest_with_stage(STAGE_QUOTE_EXTRACTION, content_hash=h)
    assert _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [gone]) is False


def test_stage_verified_incomplete_stage(tmp_path: Path):
    """Stage not marked COMPLETE → always False."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    m = PipelineManifest(
        schema_version=1,
        project_name="test",
        pipeline_version="0.14.2",
        created_at="2026-03-24T00:00:00Z",
        updated_at="2026-03-24T00:00:00Z",
        stages={
            STAGE_QUOTE_EXTRACTION: StageRecord(
                status=StageStatus.RUNNING,
                content_hash=hash_bytes(f.read_bytes()),
            ),
        },
    )
    assert _is_stage_verified(m, STAGE_QUOTE_EXTRACTION, [f]) is False


# ── _is_stage_verified (multi-file: cluster+group) ───────────────


def test_stage_verified_multi_file_match(tmp_path: Path):
    sc = tmp_path / "screen_clusters.json"
    tg = tmp_path / "theme_groups.json"
    sc.write_bytes(b'[{"clusters": 1}]')
    tg.write_bytes(b'[{"groups": 2}]')
    combined_hash = hash_bytes(sc.read_bytes() + tg.read_bytes())
    m = _manifest_with_stage(STAGE_CLUSTER_AND_GROUP, content_hash=combined_hash)
    assert _is_stage_verified(m, STAGE_CLUSTER_AND_GROUP, [sc, tg]) is True


def test_stage_verified_multi_file_mismatch(tmp_path: Path):
    sc = tmp_path / "screen_clusters.json"
    tg = tmp_path / "theme_groups.json"
    sc.write_bytes(b'[{"clusters": 1}]')
    tg.write_bytes(b'[{"groups": 2}]')
    m = _manifest_with_stage(STAGE_CLUSTER_AND_GROUP, content_hash="0" * 64)
    assert _is_stage_verified(m, STAGE_CLUSTER_AND_GROUP, [sc, tg]) is False


# ── _is_speaker_stage_verified (per-session hashes) ──────────────


def test_speaker_verified_match(tmp_path: Path):
    si_dir = tmp_path / "speaker-info"
    si_dir.mkdir()
    f1 = si_dir / "s1.json"
    f2 = si_dir / "s2.json"
    f1.write_bytes(b'{"speaker_infos": [], "segments_with_roles": []}')
    f2.write_bytes(b'{"speaker_infos": [], "segments_with_roles": []}')
    sessions = {
        "s1": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s1",
            content_hash=hash_bytes(f1.read_bytes()),
        ),
        "s2": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s2",
            content_hash=hash_bytes(f2.read_bytes()),
        ),
    }
    m = _manifest_with_stage(STAGE_IDENTIFY_SPEAKERS, sessions=sessions)
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": f1, "s2": f2},
    ) is True


def test_speaker_verified_one_session_mismatch(tmp_path: Path):
    si_dir = tmp_path / "speaker-info"
    si_dir.mkdir()
    f1 = si_dir / "s1.json"
    f2 = si_dir / "s2.json"
    f1.write_bytes(b'{"speaker_infos": [], "segments_with_roles": []}')
    f2.write_bytes(b'{"speaker_infos": [], "segments_with_roles": []}')
    sessions = {
        "s1": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s1",
            content_hash=hash_bytes(f1.read_bytes()),
        ),
        "s2": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s2",
            content_hash="0" * 64,  # wrong hash
        ),
    }
    m = _manifest_with_stage(STAGE_IDENTIFY_SPEAKERS, sessions=sessions)
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": f1, "s2": f2},
    ) is False


def test_speaker_verified_no_session_hashes(tmp_path: Path):
    """Sessions without hashes (old manifest) → trust the cache."""
    si_dir = tmp_path / "speaker-info"
    si_dir.mkdir()
    f1 = si_dir / "s1.json"
    f1.write_bytes(b'{}')
    sessions = {
        "s1": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s1",
            content_hash=None,
        ),
    }
    m = _manifest_with_stage(STAGE_IDENTIFY_SPEAKERS, sessions=sessions)
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": f1},
    ) is True


def test_speaker_verified_missing_file(tmp_path: Path):
    gone = tmp_path / "speaker-info" / "s1.json"
    sessions = {
        "s1": SessionRecord(
            status=StageStatus.COMPLETE,
            session_id="s1",
            content_hash="abc",
        ),
    }
    m = _manifest_with_stage(STAGE_IDENTIFY_SPEAKERS, sessions=sessions)
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": gone},
    ) is False


def test_speaker_verified_no_sessions_record(tmp_path: Path):
    """Stage has no sessions dict at all (e.g. old manifest) → trust."""
    si_dir = tmp_path / "speaker-info"
    si_dir.mkdir()
    f1 = si_dir / "s1.json"
    f1.write_bytes(b'{}')
    m = _manifest_with_stage(STAGE_IDENTIFY_SPEAKERS, sessions=None)
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": f1},
    ) is True


# ── Phase 2c: input change detection ────────────────────────────


def test_stage_verified_inputs_match(tmp_path: Path):
    """When current input hashes match stored ones → cached."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    ih = {"upstream": "abc123"}
    m = _manifest_with_stage(
        STAGE_QUOTE_EXTRACTION, content_hash=h, input_hashes=ih,
    )
    assert _is_stage_verified(
        m, STAGE_QUOTE_EXTRACTION, [f], current_input_hashes=ih,
    ) is True


def test_stage_verified_inputs_changed(tmp_path: Path):
    """When current input hashes differ → stale, re-run."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    m = _manifest_with_stage(
        STAGE_QUOTE_EXTRACTION,
        content_hash=h,
        input_hashes={"upstream": "old_hash"},
    )
    assert _is_stage_verified(
        m, STAGE_QUOTE_EXTRACTION, [f],
        current_input_hashes={"upstream": "new_hash"},
    ) is False


def test_stage_verified_inputs_changed_invalidates_manifest(tmp_path: Path):
    """Input change removes the stage from manifest (like hash mismatch)."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    m = _manifest_with_stage(
        STAGE_QUOTE_EXTRACTION,
        content_hash=h,
        input_hashes={"upstream": "old"},
    )
    _is_stage_verified(
        m, STAGE_QUOTE_EXTRACTION, [f],
        current_input_hashes={"upstream": "new"},
    )
    assert STAGE_QUOTE_EXTRACTION not in m.stages


def test_stage_verified_no_stored_input_hashes_backward_compat(tmp_path: Path):
    """Old manifests without input_hashes → trust the cache."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    m = _manifest_with_stage(
        STAGE_QUOTE_EXTRACTION, content_hash=h, input_hashes=None,
    )
    assert _is_stage_verified(
        m, STAGE_QUOTE_EXTRACTION, [f],
        current_input_hashes={"upstream": "anything"},
    ) is True


def test_stage_verified_no_current_input_hashes(tmp_path: Path):
    """When caller doesn't provide current_input_hashes → skip check."""
    f = tmp_path / "quotes.json"
    f.write_bytes(b'[]')
    h = hash_bytes(f.read_bytes())
    m = _manifest_with_stage(
        STAGE_QUOTE_EXTRACTION,
        content_hash=h,
        input_hashes={"upstream": "stored"},
    )
    assert _is_stage_verified(
        m, STAGE_QUOTE_EXTRACTION, [f],
    ) is True


def test_speaker_verified_inputs_changed(tmp_path: Path):
    """Speaker stage with changed inputs → stale."""
    si_dir = tmp_path / "speaker-info"
    si_dir.mkdir()
    f1 = si_dir / "s1.json"
    f1.write_bytes(b'{}')
    m = _manifest_with_stage(
        STAGE_IDENTIFY_SPEAKERS,
        sessions=None,
        input_hashes={"upstream": "old"},
    )
    assert _is_speaker_stage_verified(
        m, STAGE_IDENTIFY_SPEAKERS, {"s1": f1},
        current_input_hashes={"upstream": "new"},
    ) is False


def test_mark_stage_complete_stores_input_hashes():
    """Round-trip: input_hashes survive manifest serialisation."""
    from bristlenose.manifest import create_manifest, mark_stage_complete

    m = create_manifest("test", "0.14.3")
    ih = {"upstream": "abc123", "source_files": "def456"}
    mark_stage_complete(m, STAGE_QUOTE_EXTRACTION, input_hashes=ih)
    rec = m.stages[STAGE_QUOTE_EXTRACTION]
    assert rec.input_hashes == ih

    # Verify JSON round-trip
    m2 = PipelineManifest.model_validate_json(m.model_dump_json())
    assert m2.stages[STAGE_QUOTE_EXTRACTION].input_hashes == ih
