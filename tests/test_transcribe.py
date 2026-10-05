"""Tests for stage 5 transcription helpers."""

from __future__ import annotations

from bristlenose.stages.s05_transcribe import collapse_adjacent_repeats


class TestCollapseAdjacentRepeats:
    """Collapse adjacent identical n-grams in transcript text.

    Asymmetric thresholds: content-word and phrase-level repeats collapse
    aggressively (almost always artefacts); interjection / discourse-marker
    doublings are protected because real speech does that (Thatcher's
    "No. No. No.", "yeah yeah", "very very good").
    """

    def test_leaves_normal_text_alone(self) -> None:
        text = "Thank you for your time. It was a great conversation."
        assert collapse_adjacent_repeats(text) == text

    def test_collapses_content_word_run(self) -> None:
        assert collapse_adjacent_repeats("thanks thanks thanks thanks") == "thanks"
        assert (
            collapse_adjacent_repeats("facebook facebook facebook") == "facebook"
        )
        assert collapse_adjacent_repeats("crockpot crockpot") == "crockpot"

    def test_collapses_bigram_repeat(self) -> None:
        # Phrase-level repeats collapse regardless of word-type.
        assert (
            collapse_adjacent_repeats("Thank you. Thank you. Thank you.")
            == "Thank you."
        )

    def test_collapses_longer_phrase(self) -> None:
        text = (
            "thanks very much for your time "
            "thanks very much for your time "
            "thanks very much for your time"
        )
        assert collapse_adjacent_repeats(text) == "thanks very much for your time"

    def test_preserves_natural_interjection_doubling(self) -> None:
        # Thatcher's iconic "No. No. No.", agreement-mirroring "yeah yeah",
        # emphatic intensifier doubling — real speech, protected.
        assert collapse_adjacent_repeats("No. No. No.") == "No. No. No."
        assert collapse_adjacent_repeats("yeah yeah") == "yeah yeah"
        assert collapse_adjacent_repeats("very very good") == "very very good"
        assert collapse_adjacent_repeats("well well well") == "well well well"
        assert collapse_adjacent_repeats("okay okay") == "okay okay"

    def test_collapses_extreme_interjection_loops(self) -> None:
        # Six or more repetitions of an interjection is Whisper looping,
        # past any plausible natural emphasis.
        assert collapse_adjacent_repeats("no no no no no no no") == "no"
        assert collapse_adjacent_repeats("yeah yeah yeah yeah yeah yeah") == "yeah"

    def test_handles_ikea_tail_pattern(self) -> None:
        # Synthesised from the actual 2026-05-09 IKEA Whisper output.
        text = (
            "thanks very much for your time stopping here "
            "thanks very much for your time "
            "thanks very much for your time "
            "thanks very much thanks thanks thanks thanks "
            "facebook facebook Thank you."
        )
        out = collapse_adjacent_repeats(text)
        assert " thanks thanks " not in out
        assert "facebook facebook" not in out

    def test_short_input(self) -> None:
        assert collapse_adjacent_repeats("") == ""
        assert collapse_adjacent_repeats("hi") == "hi"


class TestDetectedLanguageIsRecordedOnlyWhenDetected:
    """The label must never be our own input echoed back.

    Both backends report a `language`, but with the language PINNED that value
    is the decode option we handed them — so storing it would put our own guess
    in the transcript header wearing the clothes of evidence. The distinction is
    the whole point of recording it at all, and it is invisible to a test that
    only checks the auto case.
    """

    def _sessions(self, tmp_path):
        from datetime import datetime

        from bristlenose.models import FileType, InputFile, InputSession

        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"\0")
        return [InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            files=[InputFile(
                path=audio, file_type=FileType.AUDIO,
                created_at=datetime(2026, 9, 22), size_bytes=1,
            )],
            audio_path=audio,
            session_date=datetime(2026, 9, 22),
        )]

    def _settings(self, language: str):
        return type("S", (), {
            "whisper_backend": "mlx",
            "whisper_model": "tiny",
            "whisper_language": language,
        })()

    def _patched(self, monkeypatch, reported: str):
        """A backend that claims it heard `reported`, whatever it was told."""
        from bristlenose.models import TranscriptSegment
        from bristlenose.stages import s05_transcribe

        def _fake_init(_settings):
            def _t(_path, _settings, **_kw):
                seg = TranscriptSegment(
                    start_time=0.0, end_time=1.0, text="hola", speaker_label="A",
                )
                return [seg], reported
            return _t

        monkeypatch.setattr(s05_transcribe, "_init_mlx_backend", _fake_init)
        monkeypatch.setattr(
            s05_transcribe, "_resolve_backend", lambda _c, _h: "mlx",  # noqa: ARG005
        )
        return s05_transcribe

    def test_auto_records_what_the_backend_heard(self, monkeypatch, tmp_path) -> None:
        s05 = self._patched(monkeypatch, "es")
        _results, languages, outcome = s05.transcribe_sessions(
            self._sessions(tmp_path), self._settings("auto"),
        )
        assert outcome.succeeded == 1
        assert languages == {"s1": "es"}

    def test_pinned_records_nothing_even_though_the_backend_reports_it(
        self, monkeypatch, tmp_path,
    ) -> None:
        # The backend still answers "es" — pinned, that is the decode option
        # coming back, not a detection. Mutation proof: drop the `pinned is
        # None` guard in `transcribe_sessions` and this goes red.
        s05 = self._patched(monkeypatch, "es")
        _results, languages, outcome = s05.transcribe_sessions(
            self._sessions(tmp_path), self._settings("es"),
        )
        assert outcome.succeeded == 1
        assert languages == {}


class TestTheDetectedLanguageReachesTheTranscriptHeader:
    """The researcher-facing end of the chain — the only surface that shows it."""

    def _transcript_inputs(self, tmp_path):
        from datetime import datetime

        from bristlenose.models import (
            FileType,
            InputFile,
            InputSession,
            TranscriptSegment,
        )

        src = tmp_path / "s1.wav"
        src.write_bytes(b"\0")
        session = InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            files=[InputFile(
                path=src, file_type=FileType.AUDIO,
                created_at=datetime(2026, 9, 22), size_bytes=1,
            )],
            session_date=datetime(2026, 9, 22),
        )
        segments = {"s1": [TranscriptSegment(
            start_time=0.0, end_time=1.0, text="hola", speaker_label="A",
        )]}
        return [session], segments

    def test_header_names_the_language_when_one_was_detected(self, tmp_path) -> None:
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )

        sessions, segments = self._transcript_inputs(tmp_path)
        transcripts = merge_transcripts(
            sessions, segments, session_languages={"s1": "es"},
        )
        assert transcripts[0].detected_language == "es"

        write_raw_transcripts(transcripts, tmp_path)
        assert "Language: es (detected)" in (tmp_path / "s1.txt").read_text(encoding="utf-8")

    def test_header_records_a_pinned_language_as_set_not_detected(self, tmp_path) -> None:
        # A pinned run: not evidence of anything, but it IS the language, and
        # an exported clip's subtitle track needs one to be found by players.
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )

        sessions, segments = self._transcript_inputs(tmp_path)
        transcripts = merge_transcripts(sessions, segments, pinned_languages={"s1": "es"})
        assert transcripts[0].detected_language is None

        write_raw_transcripts(transcripts, tmp_path)
        text = (tmp_path / "s1.txt").read_text(encoding="utf-8")
        assert "Language: es (set)" in text
        assert "detected" not in text

    def test_importer_reads_a_set_language(self, tmp_path) -> None:
        from bristlenose.server.importer import _parse_transcript_headers

        (tmp_path / "s1.txt").write_text("# Transcript: s1\n# Language: es (set)\n", encoding="utf-8")
        assert _parse_transcript_headers(tmp_path)["s1"]["language"] == "es"

    def test_header_stays_silent_when_nothing_was_detected(self, tmp_path) -> None:
        # A transcript that came from a subtitle/docx file: nothing knew the
        # language. (A pinned run writes "(set)" — see the test above.)
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )

        sessions, segments = self._transcript_inputs(tmp_path)
        transcripts = merge_transcripts(sessions, segments)
        assert transcripts[0].detected_language is None

        write_raw_transcripts(transcripts, tmp_path)
        assert "Language:" not in (tmp_path / "s1.txt").read_text(encoding="utf-8")


class TestEveryReturnPathCarriesThreeValues:
    """`transcribe_sessions` returns (results, languages, outcome) — always.

    The early return for "nothing to transcribe" returned two values while the
    signature, the docstring's caller contract and `pipeline.py`'s unpack all
    said three, so reaching it raised ValueError and killed the run. Found by
    mypy during the 0.31.0 release, after a green suite: no test had ever
    called this function with sessions it would filter out entirely.

    Reachable because the two filters differ. `pipeline.py` calls when a
    session is "not already in session_segments and has audio"; this function
    then keeps only those with "audio and NO existing transcript". A session
    whose sidecar subtitle was found but failed to parse satisfies the first
    and fails the second — audio present, transcript flagged, no segments.
    """

    def _session_with_audio_and_a_failed_subtitle(self, tmp_path):
        from datetime import datetime

        from bristlenose.models import FileType, InputFile, InputSession

        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"\0")
        return InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            files=[InputFile(
                path=audio, file_type=FileType.AUDIO,
                created_at=datetime(2026, 9, 22), size_bytes=1,
            )],
            audio_path=audio,
            # The subtitle was found — so this is True — but produced no
            # segments, so the orchestrator still has nothing for the session.
            has_existing_transcript=True,
            session_date=datetime(2026, 9, 22),
        )

    def test_nothing_to_transcribe_still_returns_three_values(self, tmp_path) -> None:
        # Mutation proof: make the early return `{}, StageOutcome()` again and
        # this fails on the unpack, exactly as the pipeline did.
        from bristlenose.stages import s05_transcribe

        settings = type("S", (), {
            "whisper_backend": "mlx", "whisper_model": "tiny",
            "whisper_language": "auto",
        })()

        results, languages, outcome = s05_transcribe.transcribe_sessions(
            [self._session_with_audio_and_a_failed_subtitle(tmp_path)], settings,
        )

        assert results == {}
        assert languages == {}
        assert outcome.attempted == 0


# ---------------------------------------------------------------------------
# Signal gate — Whisper invents "Thank you." over silence
# ---------------------------------------------------------------------------

_SR = 16_000


def _tone(seconds: float, dbfs: float):
    """A 220 Hz sine at the given RMS level (a sine's RMS is peak / √2)."""
    import numpy as np

    t = np.arange(int(seconds * _SR)) / _SR
    peak = 10 ** (dbfs / 20) * np.sqrt(2)
    return (peak * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def _silence(seconds: float):
    import numpy as np

    return np.zeros(int(seconds * _SR), dtype=np.float32)


class TestSignalGate:
    """The shape measured on 27 Sep 2026: four videos whose audio track was
    digital zero came back as 52–66 lines of "Thank you.", one per 30-second
    window, and were analysed as interviews. large-v3-turbo reports
    ``no_speech_prob == 0.0`` even there, so Whisper's own guard cannot help.
    """

    def test_digital_silence_has_no_signal(self) -> None:
        from bristlenose.stages.s05_transcribe import has_signal, window_levels_dbfs

        assert not has_signal(window_levels_dbfs(_silence(60)))

    def test_room_tone_alone_is_not_signal(self) -> None:
        # The two real interviews measured had room tone at -71 to -87 dBFS.
        from bristlenose.stages.s05_transcribe import has_signal, window_levels_dbfs

        assert not has_signal(window_levels_dbfs(_tone(60, -80)))

    def test_quiet_speech_level_is_signal(self) -> None:
        # The quietest real segment measured peaked at -46.8 dBFS.
        import numpy as np

        from bristlenose.stages.s05_transcribe import has_signal, window_levels_dbfs

        audio = np.concatenate([_silence(30), _tone(0.5, -47), _silence(30)])
        assert has_signal(window_levels_dbfs(audio))

    def test_empty_audio_has_no_signal(self) -> None:
        import numpy as np

        from bristlenose.stages.s05_transcribe import has_signal, window_levels_dbfs

        assert not has_signal(window_levels_dbfs(np.zeros(0, dtype=np.float32)))

    def test_a_segment_deep_in_silence_is_dropped(self) -> None:
        import numpy as np

        from bristlenose.stages.s05_transcribe import segment_has_signal, window_levels_dbfs

        # Speech in the first ten seconds, then silence; Whisper's invented
        # line sits at the start of the next 30 s window, as measured.
        levels = window_levels_dbfs(np.concatenate([_tone(10, -30), _silence(50)]))
        assert not segment_has_signal(30.0, 30.12, levels)

    def test_a_word_stamped_early_is_kept(self) -> None:
        # Measured: "drainer" was stamped at 1750.08–1750.50 while its speech
        # began at 1751.3 — the stamp sits entirely in room tone. A gate that
        # read only the stamped span would have dropped a real word.
        import numpy as np

        from bristlenose.stages.s05_transcribe import segment_has_signal, window_levels_dbfs

        levels = window_levels_dbfs(np.concatenate([_tone(11.3, -82), _tone(3, -45)]))
        assert segment_has_signal(10.08, 10.50, levels)

    def test_a_segment_past_the_end_of_the_audio_is_kept(self) -> None:
        # Nothing to judge by — fail open.
        from bristlenose.stages.s05_transcribe import segment_has_signal, window_levels_dbfs

        levels = window_levels_dbfs(_tone(5, -30))
        assert segment_has_signal(100.0, 101.0, levels)


class TestMlxBackendAppliesTheSignalGate:
    """The wiring, not the arithmetic: a silent file must never reach Whisper,
    and a line Whisper puts in a silent stretch must not reach the transcript.
    Needs mlx-whisper installed (Apple Silicon); skipped elsewhere."""

    def _backend(self, monkeypatch, audio, whisper_segments):
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        calls: list[object] = []

        def _fake_transcribe(audio_in, **_kw):
            calls.append(audio_in)
            return {"language": "en", "segments": whisper_segments}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: audio)
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake_transcribe)

        from bristlenose.stages import s05_transcribe

        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()
        return s05_transcribe._init_mlx_backend(settings), settings, calls

    def test_a_silent_file_is_not_sent_to_whisper(self, monkeypatch, tmp_path) -> None:
        thank_you = [{"start": 30.0 * i, "end": 30.0 * i + 0.12, "text": " Thank you."}
                     for i in range(4)]
        fn, settings, calls = self._backend(monkeypatch, _silence(120), thank_you)

        segments, language = fn(tmp_path / "p3.wav", settings)

        assert segments == []
        assert language is None
        assert calls == []

    def test_lines_in_a_silent_stretch_are_dropped_and_speech_is_kept(
        self, monkeypatch, tmp_path,
    ) -> None:
        import numpy as np

        audio = np.concatenate([_tone(10, -30), _silence(50)])
        fn, settings, calls = self._backend(monkeypatch, audio, [
            {"start": 1.0, "end": 4.0, "text": " We bought the sofa in May."},
            {"start": 30.0, "end": 30.12, "text": " Thank you."},
        ])

        segments, _language = fn(tmp_path / "p1.wav", settings)

        assert [s.text for s in segments] == ["We bought the sofa in May."]
        assert len(calls) == 1


class TestPipelineRecordsAPinnedLanguage:
    """A pinned ``--whisper-language`` reaches the transcript header as ``(set)``."""

    def _gather(self, tmp_path, whisper_language: str):
        import asyncio
        from datetime import datetime
        from unittest.mock import patch

        from bristlenose.config import BristlenoseSettings
        from bristlenose.events import StageOutcome
        from bristlenose.models import InputSession, TranscriptSegment
        from bristlenose.pipeline import Pipeline

        audio = tmp_path / "s1.wav"
        audio.write_bytes(b"")
        session = InputSession(
            session_id="s1", session_number=1, participant_id="p1",
            participant_number=1, files=[], audio_path=audio,
            session_date=datetime(2026, 9, 29),
        )
        seg = TranscriptSegment(start_time=0.0, end_time=1.0, text="hola", speaker_label="A")
        pipeline = Pipeline(BristlenoseSettings(whisper_language=whisper_language))
        with patch(
            "bristlenose.stages.s05_transcribe.transcribe_sessions",
            return_value=({"s1": [seg]}, {}, StageOutcome(attempted=1, succeeded=1)),
        ):
            asyncio.run(pipeline._gather_all_segments([session]))
        return pipeline

    def test_pinned_language_is_recorded_per_transcribed_session(self, tmp_path) -> None:
        assert self._gather(tmp_path, "ES")._pinned_languages == {"s1": "es"}

    def test_auto_records_nothing_pinned(self, tmp_path) -> None:
        assert self._gather(tmp_path, "auto")._pinned_languages == {}

    def test_a_cached_session_keeps_the_language_its_last_run_wrote(self, tmp_path) -> None:
        """Stage 6 rewrites every header; a session served from the
        transcription cache was not detected this run, so its language is read
        back from the header the last run wrote."""
        from bristlenose.config import BristlenoseSettings
        from bristlenose.pipeline import Pipeline

        raw = tmp_path / "transcripts-raw"
        raw.mkdir()
        (raw / "s1.txt").write_text("# Transcript: s1\n# Language: ja (detected)\n\n", encoding="utf-8")
        (raw / "s2.txt").write_text("# Transcript: s2\n# Language: es (set)\n\n", encoding="utf-8")
        (raw / "s3.txt").write_text("# Transcript: s3\n\n", encoding="utf-8")
        pipeline = Pipeline(BristlenoseSettings())
        pipeline._detected_languages["s4"] = "fr"  # detected this run: kept
        pipeline._recover_languages(raw, ["s1", "s2", "s3", "s4", "s5"])
        assert pipeline._detected_languages == {"s1": "ja", "s4": "fr"}
        assert pipeline._pinned_languages == {"s2": "es"}

