"""The per-session transcription-quality record (bristlenose/transcription_quality.py)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bristlenose import transcription_quality as tq
from bristlenose.models import TranscriptSegment, Word

_SR = 16000


def _seg(a: float, b: float, text: str, confs: list[float] | None = None, **kw) -> TranscriptSegment:
    words = []
    if confs is not None:
        toks = text.split()
        step = (b - a) / max(1, len(toks))
        words = [
            Word(text=t, start_time=a + i * step, end_time=a + (i + 1) * step, confidence=c)
            for i, (t, c) in enumerate(zip(toks, confs, strict=True))
        ]
    return TranscriptSegment(start_time=a, end_time=b, text=text, words=words, **kw)


class TestTextMeasures:
    def test_counts_words_sentence_ends_and_the_longest_run(self) -> None:
        segs = [
            _seg(0, 10, "Well, I suppose so. And then we went home."),
            _seg(10, 20, "it was 3.5 hours long and nobody stopped us at all"),
        ]
        m = tq.text_measures(segs, duration_s=60)
        assert m["words"] == 20
        assert m["wpm"] == 20
        # "so." and "home." end sentences; "3.5" does not.
        assert m["sentence_ends_per_100"] == 10.0
        # "3" is split from "5 hours…" by the full stop, so the run is the 9
        # words from "5" to the end.
        assert m["longest_unpunctuated"] == 9
        assert m["segments"] == 2

    def test_japanese_is_counted_in_reading_length(self) -> None:
        segs = [_seg(0, 10, "はい。そうですね、なるほど。")]
        m = tq.text_measures(segs, duration_s=10)
        # 11 kana at 0.4 a word, and two full stops with no space after them.
        assert m["words"] == 4
        assert m["sentence_ends_per_100"] == pytest.approx(100 * 2 / 4.4, abs=0.1)

    def test_inaudible_gaps_carry_no_words(self) -> None:
        segs = [_seg(0, 5, "Hello there."), _seg(5, 9, "", inaudible=True)]
        assert tq.text_measures(segs, 10)["words"] == 2
        assert tq.gap_measures(segs) == {"inaudible_gaps": 1, "inaudible_seconds": 4.0}


class TestConfidenceAndSeries:
    def test_histogram_and_low_share(self) -> None:
        segs = [_seg(0, 4, "a b c d", [0.1, 0.45, 0.9, 1.0])]
        c = tq.confidence_measures(segs)
        assert c["mean_confidence"] == pytest.approx(0.6125, abs=0.001)
        assert c["low_confidence_share"] == 0.5
        assert c["confidence_hist"] == [0, 1, 0, 0, 1, 0, 0, 0, 0, 2]

    def test_no_word_timings_reads_as_unknown_not_zero(self) -> None:
        c = tq.confidence_measures([_seg(0, 4, "no timings here")])
        assert c["mean_confidence"] is None and c["low_confidence_share"] is None

    def test_a_long_segment_spreads_its_words_over_the_bins_it_covers(self) -> None:
        # 30 words over 0–30 s: 10 words in each 10 s bin, 60 a minute each.
        s = tq.series([_seg(0, 30, " ".join(["w"] * 30))], None, duration_s=30)
        assert s["wpm"] == [60, 60, 60]
        assert s["level_p90"] == []
        assert s["low_conf"] == [None, None, None]

    def test_levels_are_summarised_per_bin(self) -> None:
        levels = np.concatenate([np.full(100, -20.0), np.full(100, -60.0)])
        s = tq.series([], levels, duration_s=20)
        assert s["level_p90"] == [-20.0, -60.0]


class TestRecordFile:
    def test_round_trip_and_unknown_versions_are_ignored(self, tmp_path: Path) -> None:
        rec = tq.build_record(
            session_id="s1", duration_s=20.0,
            segments=[_seg(0, 10, "Some words here.", [0.9, 0.9, 0.9])],
            recognition={"backend": "mlx"},
        )
        tq.write_record(tmp_path, "s1", rec)
        tq.write_record(tmp_path, "s2", {**rec, "version": 999})
        got = tq.read_records(tmp_path)
        assert set(got) == {"s1"}
        assert got["s1"]["text"]["words"] == 3

    def test_the_record_carries_no_transcript_text(self, tmp_path: Path) -> None:
        words = ["Rosalind", "Pemberton", "Albemarle", "Ashbourne", "Kettering"]
        rec = tq.build_record(
            session_id="s1", duration_s=30.0,
            segments=[_seg(0, 10, " ".join(words), [0.9] * 5)],
            recognition={"backend": "mlx"},
        )
        dumped = json.dumps(rec)
        for w in words:
            assert w not in dumped

    def test_the_summary_places_nothing_in_time(self) -> None:
        rec = tq.build_record(
            session_id="s1", duration_s=60.0,
            segments=[_seg(0, 10, "Some words here.", [0.9, 0.9, 0.9])],
            recognition={"backend": "mlx"},
            repair={"skipped_found": 1, "found": [[10.0, 30.0]], "still_empty": [[10.0, 30.0]]},
        )
        out = tq.summary(rec)
        assert "series" not in out and "session_id" not in out
        assert out["repair"]["skipped_found"] == 1

        def no_spans(v: object) -> None:
            if isinstance(v, dict):
                for x in v.values():
                    no_spans(x)
            elif isinstance(v, list):
                assert not any(isinstance(x, list) for x in v), v

        no_spans(out)

    def test_an_unwritable_folder_is_logged_not_raised(self, tmp_path: Path) -> None:
        blocker = tmp_path / "out"
        blocker.write_text("a file where the folder should be", encoding="utf-8")
        tq.write_record(blocker, "s1", {"version": 1})  # must not raise


class TestStage5Fills:
    def test_the_mlx_backend_reports_what_it_did(self, monkeypatch, tmp_path) -> None:
        """Fallback windows, the skipped stretch and audio levels reach the record."""
        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        def tone(seconds: float, dbfs: float) -> np.ndarray:
            t = np.arange(int(seconds * _SR)) / _SR
            return (10 ** (dbfs / 20) * np.sqrt(2) * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

        calls: list[int] = []

        def fake(audio_in, **_kw):
            calls.append(len(audio_in))
            if len(calls) == 1:
                return {"language": "en", "segments": [
                    {"seek": 0, "start": 0.0, "end": 10.0, "temperature": 0.0,
                     "text": " " + " ".join(f"a{i}" for i in range(25))},
                    {"seek": 3000, "start": 30.0, "end": 40.0, "temperature": 0.4,
                     "text": " " + " ".join(f"b{i}" for i in range(25))},
                ]}
            return {"language": "en", "segments": []}  # the net hears nothing

        monkeypatch.setattr(s05_transcribe, "STYLE_PROMPTS", {})
        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: tone(40, -20))
        monkeypatch.setattr(mlx_whisper, "transcribe", fake)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()

        sink: dict = {}
        token = s05_transcribe._QUALITY_SINK.set(sink)
        try:
            segments, _ = s05_transcribe._init_mlx_backend(settings)(tmp_path / "x.wav", settings)
        finally:
            s05_transcribe._QUALITY_SINK.reset(token)

        rec = s05_transcribe._quality_record("s1", segments, sink)
        assert rec is not None
        assert rec["recognition"]["decode_windows"] == 2
        assert rec["recognition"]["fallback_windows"] == 1
        assert rec["recognition"]["prompt"] is False
        assert rec["repair"]["skipped_found"] == 1
        assert rec["repair"]["skipped_recovered"] == 0
        assert rec["repair"]["still_empty"] == [[10.0, 30.0]]
        assert rec["audio"]["peak_dbfs"] == pytest.approx(-20.0, abs=0.5)
        assert rec["audio"]["active_share"] == 1.0
        assert rec["duration_s"] == 40.0

    def test_a_backend_that_measures_nothing_gives_no_record(self, monkeypatch, tmp_path) -> None:
        """A stub backend (as every older test uses) leaves no record and no error."""
        from bristlenose.stages import s05_transcribe

        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"x")
        session = type("Sess", (), {
            "session_id": "s1", "audio_path": audio, "has_existing_transcript": False,
        })()

        def init(_settings):
            return lambda _p, _s: ([_seg(0, 1, "Hi.")], "en")

        monkeypatch.setattr(s05_transcribe, "_init_mlx_backend", init)
        monkeypatch.setattr(s05_transcribe, "_resolve_backend", lambda _c, _h: "mlx")
        settings = type("S", (), {
            "whisper_backend": "mlx", "whisper_model": "tiny", "whisper_language": "auto",
        })()
        [done] = list(s05_transcribe.iter_transcribe_sessions([session], settings))
        assert done.quality is None and done.segments

    def test_the_iterator_hands_the_record_on(self, monkeypatch, tmp_path) -> None:
        from bristlenose.stages import s05_transcribe

        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"x")
        session = type("Sess", (), {
            "session_id": "s1", "audio_path": audio, "has_existing_transcript": False,
        })()

        def init(_settings):
            def run(_p, _s):
                s05_transcribe._report_quality(
                    np.zeros(_SR * 2, dtype=np.float32), None,
                    recognition={"backend": "mlx"}, measure_audio=False,
                )
                return [_seg(0, 1, "Hi there.")], "en"
            return run

        monkeypatch.setattr(s05_transcribe, "_init_mlx_backend", init)
        monkeypatch.setattr(s05_transcribe, "_resolve_backend", lambda _c, _h: "mlx")
        settings = type("S", (), {
            "whisper_backend": "mlx", "whisper_model": "tiny", "whisper_language": "auto",
        })()
        [done] = list(s05_transcribe.iter_transcribe_sessions([session], settings))
        assert done.quality is not None
        assert done.quality["session_id"] == "s1"
        assert done.quality["text"]["words"] == 2
        assert done.quality["duration_s"] == 2.0


class TestPipelineWritesAndClears:
    """`Pipeline._gather_all_segments` keeps one honest record per session."""

    @staticmethod
    def _session(tmp_path: Path, *, srt: bool = False):
        from datetime import datetime

        from bristlenose.models import FileType, InputFile, InputSession

        files = []
        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"")
        if srt:
            sub = tmp_path / "s1.srt"
            sub.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello there.\n\n", encoding="utf-8")
            files.append(InputFile(path=sub, file_type=FileType.SUBTITLE_SRT,
                                   created_at=datetime(2026, 10, 1), size_bytes=sub.stat().st_size))
        return InputSession(
            session_id="s1", session_number=1, participant_id="p1", participant_number=1,
            files=files, audio_path=audio, has_existing_transcript=srt,
            session_date=datetime(2026, 10, 1),
        )

    @staticmethod
    def _gather(tmp_path: Path, session, done) -> Path:
        import asyncio
        from unittest.mock import patch

        from bristlenose.config import BristlenoseSettings
        from bristlenose.pipeline import Pipeline

        out = tmp_path / "out"
        pipeline = Pipeline(BristlenoseSettings())
        with patch(
            "bristlenose.stages.s05_transcribe.iter_transcribe_sessions",
            return_value=iter(done),
        ):
            asyncio.run(pipeline._gather_all_segments([session], quality_output_dir=out))
        return out

    def test_a_transcribed_session_leaves_its_record(self, tmp_path: Path) -> None:
        from bristlenose.stages.s05_transcribe import SessionTranscription

        rec = {"version": tq.RECORD_VERSION, "session_id": "s1"}
        out = self._gather(tmp_path, self._session(tmp_path),
                           [SessionTranscription("s1", [_seg(0, 1, "Hi.")], quality=rec)])
        assert set(tq.read_records(out)) == {"s1"}

    def test_a_session_that_measured_nothing_loses_its_old_record(self, tmp_path: Path) -> None:
        from bristlenose.stages.s05_transcribe import SessionTranscription

        out = tmp_path / "out"
        tq.write_record(out, "s1", {"version": tq.RECORD_VERSION, "session_id": "s1"})
        self._gather(tmp_path, self._session(tmp_path),
                     [SessionTranscription("s1", [_seg(0, 1, "Hi.")])])
        assert tq.read_records(out) == {}

    def test_a_platform_transcript_clears_the_whisper_record(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        tq.write_record(out, "s1", {"version": tq.RECORD_VERSION, "session_id": "s1"})
        self._gather(tmp_path, self._session(tmp_path, srt=True), [])
        assert tq.read_records(out) == {}


def test_the_series_bins_use_the_signal_gates_windows() -> None:
    from bristlenose.stages import s05_transcribe

    assert tq.LEVEL_WINDOWS_PER_SECOND == s05_transcribe._LEVEL_WINDOWS_PER_SECOND


def test_a_record_that_cannot_be_serialised_is_logged_not_raised(tmp_path: Path) -> None:
    tq.write_record(tmp_path, "s1", {"version": 1, "x": float("nan")})
    tq.write_record(tmp_path, "s2", {"version": 1, "x": object()})
    assert tq.read_records(tmp_path) == {}
