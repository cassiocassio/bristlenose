"""A project's output follows the project, not the path it was analysed at.

Driven through the real ``Pipeline.run`` (the harness in
``test_pipeline_platform_transcripts``): ingest's grouping, the manifest, the
session registry, the transcript writers and the renderer are real; Whisper
and every LLM call are stubbed. Each case was measured red on 12 Oct 2026
against a scratch copy of the smoke fixture (the lifecycle handoff, §1.2
P3) before the fix it pins was written.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from bristlenose.hashing import hash_bytes, hash_file_metadata
from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline


def _one(d: Path, _i: int):
    return [audio_session(d, 1, "bare")]


# ── P3: a folder move or rename must not re-pay Whisper ─────────────────────


class TestMovedProject:
    def test_a_moved_project_is_not_re_transcribed(self, tmp_path: Path) -> None:
        """Rename the study folder between two runs: the second run finds every
        session cached. Measured 12 Oct 2026: the fingerprint carried the
        resolved absolute path, so the move re-transcribed everything."""
        first = tmp_path / "study"
        first.mkdir()
        h1 = run_pipeline(first, _one)
        assert h1.transcribed == [["s1"]]

        moved = tmp_path / "study (renamed)"
        os.rename(first, moved)
        h2 = run_pipeline(moved, _one)
        assert h2.transcribed == [], "a moved folder re-paid Whisper for its session"

    def test_a_fingerprint_written_before_the_move_fix_is_migrated(
        self, tmp_path: Path,
    ) -> None:
        """A manifest from before 12 Oct 2026 carries the absolute-path form.
        The first run after upgrading recognises it as the same files, keeps
        the cache, and rewrites the record in the new form — so a project
        pays nothing for the upgrade and is move-safe from then on."""
        h1 = run_pipeline(tmp_path, _one)
        wav = h1.input_dir / "bare.wav"
        legacy_stage = hash_file_metadata([wav])          # old stage-level value
        legacy_session = hash_bytes(legacy_stage.encode())  # old per-session form

        manifest_path = h1.output_dir / ".bristlenose" / "pipeline-manifest.json"
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = m["stages"]["transcribe"]
        assert record["sessions"]["s1"]["input_hash"] != legacy_session, (
            "the new form must differ from the old one, or this test proves nothing"
        )
        record["input_hashes"]["source_files"] = legacy_stage
        record["sessions"]["s1"]["input_hash"] = legacy_session
        manifest_path.write_text(json.dumps(m), encoding="utf-8")

        h2 = run_pipeline(tmp_path, _one)
        assert h2.transcribed == [], "a legacy fingerprint was re-paid instead of migrated"
        m2 = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert m2["stages"]["transcribe"]["sessions"]["s1"]["input_hash"] != legacy_session
