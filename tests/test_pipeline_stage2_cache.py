"""Stage 2 does not decode a video whose transcription is cached.

Through the real ``Pipeline.run`` (harness: ``test_pipeline_platform_transcripts``).
Measured red 12 Oct 2026 (lifecycle handoff §1.2 P10).
"""

from __future__ import annotations

from pathlib import Path

from tests.test_pipeline_platform_transcripts import audio_session, run_pipeline


def _one(d: Path, _i: int):
    return [audio_session(d, 1, "bare")]


class TestStageTwo:
    def test_a_cached_session_is_not_decoded_again(self, tmp_path: Path) -> None:
        """On iCloud a decode is a download; a cached session needs neither."""
        h = run_pipeline(tmp_path, _one, runs=2)
        assert h.extracted == [["s1"], []]


def _undecoded(d: Path, _i: int):
    """A bare video as ingest hands it over: no audio path until stage 2."""
    session = audio_session(d, 1, "bare")
    session.audio_path = None
    return [session]


class TestOnDemandDecode:
    def test_a_cache_that_fails_to_serve_still_gets_its_audio(self, tmp_path: Path) -> None:
        """Stage 2 trusts the fingerprint; the cache file itself can still be
        unreadable. The session is then decoded on demand and transcribed,
        never dropped for want of audio."""
        h1 = run_pipeline(tmp_path, _undecoded)
        assert h1.extracted == [["s1"]] and h1.transcribed == [["s1"]]
        (h1.output_dir / ".bristlenose" / "intermediate" / "session_segments.json").write_text(
            "{ not json", encoding="utf-8",
        )
        h2 = run_pipeline(tmp_path, _undecoded)
        assert h2.extracted == [[], ["s1"]], "stage 2 skipped it; decoded on demand after the miss"
        assert h2.transcribed == [["s1"]], "the session reached Whisper"
