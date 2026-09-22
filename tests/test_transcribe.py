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
        assert "Language: es (detected)" in (tmp_path / "s1.txt").read_text()

    def test_header_stays_silent_when_nothing_was_detected(self, tmp_path) -> None:
        # A pinned run, or a transcript that came from a subtitle/docx file.
        # A header line claiming a detection here would be worse than no line.
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )

        sessions, segments = self._transcript_inputs(tmp_path)
        transcripts = merge_transcripts(sessions, segments)
        assert transcripts[0].detected_language is None

        write_raw_transcripts(transcripts, tmp_path)
        assert "Language:" not in (tmp_path / "s1.txt").read_text()
