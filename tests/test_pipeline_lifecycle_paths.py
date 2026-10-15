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

import pytest

from bristlenose.hashing import hash_bytes, hash_file_metadata
from bristlenose.logging import release_log_file
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
        # The run's log handler holds bristlenose.log open inside the folder,
        # and Windows will not rename it while it does (WinError 5).
        release_log_file()
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

    def test_a_relative_path_fingerprint_is_migrated_to_content(self, tmp_path: Path) -> None:
        """A manifest from 12–15 Oct 2026 carries the relative-path form; since
        then transcription is keyed by content. The first run after upgrading
        keeps the cache and rewrites the record, so a project pays nothing."""
        h1 = run_pipeline(tmp_path, _one)
        wav = h1.input_dir / "bare.wav"
        relative = hash_bytes(hash_file_metadata([wav], relative_to=h1.input_dir).encode())

        manifest_path = h1.output_dir / ".bristlenose" / "pipeline-manifest.json"
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = m["stages"]["transcribe"]
        assert record["sessions"]["s1"]["input_hash"] != relative, (
            "the content form must differ from the relative one, or this test proves nothing"
        )
        record["input_hashes"]["source_files"] = "stale"
        record["sessions"]["s1"]["input_hash"] = relative
        manifest_path.write_text(json.dumps(m), encoding="utf-8")

        h2 = run_pipeline(tmp_path, _one)
        assert h2.transcribed == [], "a 12-Oct fingerprint was re-paid instead of migrated"
        m2 = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert m2["stages"]["transcribe"]["sessions"]["s1"]["input_hash"] != relative


class TestEvictedRecording:
    def test_an_evicted_recording_is_not_transcribed_again(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """iCloud evicts an analysed recording, then the researcher adds one.
        The evicted file has no bytes to fingerprint; the fingerprint last seen
        at its place stands in (design-project-identity.md §5), so it is not
        downloaded and transcribed again. Found by review, 15 Oct 2026."""
        from tests.test_pipeline_platform_transcripts import audio_session

        def one(d: Path, _i: int):
            return [audio_session(d, 1, "kept")]

        def two(d: Path, _i: int):
            return [audio_session(d, 1, "kept"), audio_session(d, 2, "added")]

        run_pipeline(tmp_path, one)
        import bristlenose.utils.fingerprint as fpmod

        real = fpmod.is_dataless
        monkeypatch.setattr(fpmod, "is_dataless", lambda p: p.name == "kept.wav" or real(p))
        h2 = run_pipeline(tmp_path, two)
        assert h2.transcribed == [["s2"]], f"the evicted recording was transcribed again: {h2.transcribed}"


class _StopAtRegistry(BaseException):
    """Ends a run at the registry: the test only needs the call's arguments."""


@pytest.mark.parametrize(("skip", "expected"), [(True, False), (False, True)])
def test_the_early_cloud_fetch_follows_whether_the_run_transcribes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, skip: bool, expected: bool,
) -> None:
    """The registry may download an unseen placeholder only because the run
    will download it to transcribe anyway; with transcription skipped it must
    not (Fable review, 15 Oct 2026)."""
    import asyncio

    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline
    from bristlenose.session_registry import SessionRegistry

    seen: list[bool] = []

    def spy(self, sessions, input_dir=None, *, fetch=False):
        seen.append(fetch)
        raise _StopAtRegistry

    monkeypatch.setattr(SessionRegistry, "apply", spy)
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "interview.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Ana>Hello\n", encoding="utf-8")
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=skip))
    with pytest.raises(_StopAtRegistry):
        asyncio.run(pipeline.run(tmp_path / "in", tmp_path / "in" / "bristlenose-output"))
    assert seen == [expected]
