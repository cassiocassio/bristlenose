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

    @staticmethod
    def _not_downloaded_on_first_run(monkeypatch, stem: str) -> None:
        """On the first run only, leave *stem*'s session as stage 2 leaves a
        recording whose cloud fetch outlasted the read bound: the real
        ``_record_not_downloaded`` writes the token, and the session has no
        audio. The harness stubs stage 2 itself, so this is applied as stage 2
        ends — just before the pipeline records the ingest outcome."""
        from bristlenose.pipeline import Pipeline
        from bristlenose.stages import s02_extract_audio
        from bristlenose.utils.fs import CloudFetchTimeoutError

        real = Pipeline._record_ingest_outcome
        calls = {"n": 0}

        def after_stage_2(self, sessions, *a, **kw):  # type: ignore[no-untyped-def]
            if calls["n"] == 0:
                for s in sessions:
                    for f in s.files:
                        if f.path.stem == stem:
                            s02_extract_audio._record_not_downloaded(
                                s, f.path, CloudFetchTimeoutError(
                                    f"{f.path.name} was still being fetched from "
                                    "iCloud Drive after 30 minutes"
                                ),
                            )
                            s.audio_path = None
            calls["n"] += 1
            return real(self, sessions, *a, **kw)

        monkeypatch.setattr(Pipeline, "_record_ingest_outcome", after_stage_2)

    def test_a_recording_not_downloaded_in_time_is_a_retryable_failure(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """One recording's cloud fetch outlasts the bound. Until 22 Oct 2026
        stage 2 wrapped that as ``AudioToolError`` and aborted the whole run,
        categorised ``unknown``. Now the run goes on with the other session;
        the evicted one is a ``cloud_fetch`` failure on the transcripts bucket
        (not NO_SPEECH, not a refused file), recorded FAILED in the manifest,
        and transcribed by the next run (docs/design-cloud-files.md, B)."""
        from bristlenose.events import CauseCategoryEnum
        from bristlenose.refusals import CLOUD_FETCH_MESSAGE

        def two(d: Path, _i: int):
            return [audio_session(d, 1, "kept"), audio_session(d, 2, "evicted")]

        self._not_downloaded_on_first_run(monkeypatch, "evicted")
        h = run_pipeline(tmp_path, two, runs=2)

        assert h.transcribed[0] == ["s1"], h.transcribed
        summary = h.results[0].summary
        assert summary is not None
        tx = summary.transcripts
        assert tx.succeeded == 1
        assert [(f.session_id, f.cause.category) for f in tx.failed] == [
            ("s2", CauseCategoryEnum.CLOUD_FETCH),
        ], "the evicted recording was not stated as cloud_fetch (or was also called silent)"
        assert tx.failed[0].source_file == "evicted.wav"
        assert tx.failed[0].cause.message == CLOUD_FETCH_MESSAGE
        assert summary.ingest.failed == [], "a slow download was stated as a refused file"

        # The second run, with the file now here, transcribes it and only it.
        assert h.transcribed[1] == ["s2"], (
            f"the recording not downloaded in time was not retried: {h.transcribed}"
        )

    def test_the_failed_session_is_recorded_failed_in_the_manifest(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """FAILED, not absent: absence derives COMPLETE and caches the stage."""
        def two(d: Path, _i: int):
            return [audio_session(d, 1, "kept"), audio_session(d, 2, "evicted")]

        self._not_downloaded_on_first_run(monkeypatch, "evicted")
        h = run_pipeline(tmp_path, two)
        m = json.loads(
            (h.output_dir / ".bristlenose" / "pipeline-manifest.json").read_text(encoding="utf-8")
        )
        sessions = m["stages"]["transcribe"]["sessions"]
        assert sessions["s2"]["status"] == "failed", sessions
        assert sessions["s1"]["status"] == "complete", sessions

    def test_a_lone_recording_not_downloaded_abandons_as_cloud_fetch(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Nothing came back at all: the run is abandoned, as for any other
        all-sessions failure — but as ``cloud_fetch`` (retryable), not as
        ``whisper`` or ``unknown``."""
        from bristlenose.events import CauseCategoryEnum, PipelineAbandonedError

        self._not_downloaded_on_first_run(monkeypatch, "evicted")
        with pytest.raises(PipelineAbandonedError) as exc:
            run_pipeline(tmp_path, lambda d, _i: [audio_session(d, 1, "evicted")])
        assert exc.value.cause.category == CauseCategoryEnum.CLOUD_FETCH


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


def test_transcribe_states_a_recording_not_downloaded_as_cloud_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``bristlenose transcribe`` has its own rollup, and the same fold: a
    video whose cloud fetch outlasted the bound in stage 2 (the real stage,
    with ffprobe/ffmpeg stubbed) is a ``cloud_fetch`` failure, not a silent
    recording, and not a refused file. The other session is transcribed."""
    import asyncio
    from datetime import datetime, timezone
    from unittest.mock import MagicMock, patch

    from bristlenose.events import CauseCategoryEnum, StageOutcome
    from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
    from bristlenose.pipeline import Pipeline
    from bristlenose.refusals import CLOUD_FETCH_MESSAGE
    from bristlenose.stages import s02_extract_audio
    from bristlenose.utils.fs import CloudFetchTimeoutError

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    now = datetime.now(timezone.utc)
    sessions = []
    for i, stem in enumerate(("kept", "evicted"), start=1):
        media = input_dir / f"{stem}.mp4"
        media.write_bytes(b"fake " + stem.encode())
        sessions.append(InputSession(
            session_id=f"s{i}", session_number=i, participant_id=f"p{i}", participant_number=i,
            session_date=now,
            files=[InputFile(path=media, file_type=FileType.VIDEO, created_at=now,
                             size_bytes=media.stat().st_size)],
        ))

    def probe(path: Path) -> bool:
        if path.name == "evicted.mp4":
            raise CloudFetchTimeoutError(f"{path.name} was still being fetched after 30 minutes")
        return True

    monkeypatch.setattr(s02_extract_audio, "has_audio_stream", probe)
    monkeypatch.setattr(s02_extract_audio, "extract_audio_from_video", lambda _src, out: out)

    async def _fake_gather(_self, sess, **_kw):
        # As the real one: only a session with audio reaches Whisper.
        heard = [s.session_id for s in sess if s.audio_path is not None]
        segs = {sid: [TranscriptSegment(start_time=0.0, end_time=5.0, text="Hello there.")]
                for sid in heard}
        return segs, StageOutcome(attempted=len(heard), succeeded=len(heard))

    settings = MagicMock()
    settings.project_name = "evicted"
    settings.write_intermediate = False
    settings.color_scheme = "default"
    pipeline = Pipeline(settings)
    with (
        patch("bristlenose.stages.s01_ingest.ingest", return_value=sessions),
        patch.object(Pipeline, "_gather_all_segments", new=_fake_gather),
    ):
        asyncio.run(pipeline.run_transcription_only(input_dir, tmp_path / "out"))

    tx = pipeline._summary.transcripts
    assert tx is not None
    assert tx.succeeded == 1
    assert [(f.session_id, f.cause.category) for f in tx.failed] == [
        ("s2", CauseCategoryEnum.CLOUD_FETCH),
    ], f"not stated as cloud_fetch (or also called silent): {tx.failed!r}"
    assert tx.failed[0].cause.message == CLOUD_FETCH_MESSAGE
    assert tx.failed[0].source_file == "evicted.mp4"
    assert pipeline._summary.ingest.failed == []
