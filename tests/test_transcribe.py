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
        from bristlenose.stages.s05_transcribe import SessionTranscription

        with patch(
            "bristlenose.stages.s05_transcribe.iter_transcribe_sessions",
            return_value=iter([SessionTranscription("s1", [seg])]),
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



class TestStylePromptEcho:
    """A segment that is only the style prompt is Whisper handing the prompt
    back, not speech. Its parts are things people say, so they stay."""

    def _en(self) -> str:
        from bristlenose.stages.s05_transcribe import STYLE_PROMPTS

        return STYLE_PROMPTS["en"]

    def test_the_whole_prompt_is_an_echo(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_echo

        assert is_prompt_echo(self._en(), self._en())
        assert is_prompt_echo(" " + self._en().upper() + " ", self._en())

    def test_the_prompt_repeated_is_an_echo(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_echo

        assert is_prompt_echo(f"{self._en()} {self._en()}", self._en())

    def test_a_part_of_the_prompt_said_once_or_twice_is_speech(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_echo

        for said in ("Right.", "Right. Right.", "Hmm, okay.", "Hmm, okay. Hmm, okay."):
            assert not is_prompt_echo(said, self._en()), said

    def test_the_prompt_with_anything_else_is_speech(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_echo

        assert not is_prompt_echo(f"{self._en()} And the sofa arrived late.", self._en())

    def test_japanese_compares_without_spaces_or_punctuation(self) -> None:
        from bristlenose.stages.s05_transcribe import STYLE_PROMPTS, is_prompt_echo

        ja = STYLE_PROMPTS["ja"]
        assert is_prompt_echo(ja.replace("、", " "), ja)
        assert not is_prompt_echo("はい。", ja)

    def test_empty_text_is_not_an_echo(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_echo

        assert not is_prompt_echo("", self._en())
        assert not is_prompt_echo(" ... ", self._en())


class TestStylePromptReachesEveryWindow:
    """mlx builds a fresh DecodingOptions for every window and every fallback
    temperature. The hook must fill an empty prompt with the style prompt for
    the language mlx settled on — and do nothing outside our own call.
    Needs mlx-whisper installed (Apple Silicon); skipped elsewhere."""

    def _module(self):
        import importlib

        import pytest

        pytest.importorskip("mlx_whisper")
        from bristlenose.stages import s05_transcribe

        assert s05_transcribe._install_style_prompt_hook()
        return importlib.import_module("mlx_whisper.transcribe"), s05_transcribe

    def test_mlx_still_builds_options_where_the_hook_reaches(self) -> None:
        """Pins the mlx-whisper shape the hook relies on. If an upgrade moves
        it, this fails here rather than the prompt silently stopping."""
        import inspect

        module, _ = self._module()
        source = inspect.getsource(module.transcribe)
        assert "options = DecodingOptions(**kwargs, temperature=t)" in source
        assert 'decode_options["prompt"] = all_tokens[prompt_reset_since:]' in source

    def test_an_empty_prompt_gets_the_languages_style_prompt(self) -> None:
        module, s05 = self._module()
        token = s05._STYLE_PROMPT_ON.set(True)
        try:
            en = module.DecodingOptions(language="en", prompt=[], temperature=0.0)
            ja = module.DecodingOptions(language="ja", prompt=[], temperature=0.4)
            fr = module.DecodingOptions(language="fr", prompt=[], temperature=0.0)
        finally:
            s05._STYLE_PROMPT_ON.reset(token)
        assert en.prompt == s05.STYLE_PROMPTS["en"]
        assert ja.prompt == s05.STYLE_PROMPTS["ja"]
        assert not fr.prompt

    def test_a_prompt_already_there_is_left_alone(self) -> None:
        module, s05 = self._module()
        token = s05._STYLE_PROMPT_ON.set(True)
        try:
            opts = module.DecodingOptions(language="en", prompt=[50364, 1012])
        finally:
            s05._STYLE_PROMPT_ON.reset(token)
        assert opts.prompt == [50364, 1012]

    def test_nothing_changes_outside_our_call(self) -> None:
        module, _ = self._module()
        assert not module.DecodingOptions(language="en", prompt=[]).prompt


class TestMlxBackendPromptsAndDropsEchoes:
    """The wiring: during our transcribe call every window's options carry the
    prompt, and a segment that only repeats the prompt is dropped."""

    def test_windows_carry_the_prompt_and_echoes_are_dropped(
        self, monkeypatch, tmp_path,
    ) -> None:
        import importlib

        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        module = importlib.import_module("mlx_whisper.transcribe")
        seen: list[object] = []
        prompt = s05_transcribe.STYLE_PROMPTS["en"]

        def _fake_transcribe(audio_in, **_kw):
            # What mlx does per window, after detecting the language.
            for t in (0.0, 0.2):
                seen.append(module.DecodingOptions(language="en", prompt=[], temperature=t).prompt)
            return {"language": "en", "segments": [
                {"start": 1.0, "end": 4.0, "text": " We bought the sofa in May."},
                {"start": 5.0, "end": 8.0, "text": " " + prompt},
            ]}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(10, -30))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake_transcribe)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()

        fn = s05_transcribe._init_mlx_backend(settings)
        segments, language = fn(tmp_path / "p1.wav", settings)

        assert seen == [prompt, prompt]
        assert [s.text for s in segments] == ["We bought the sofa in May."]
        assert language == "en"
        assert not module.DecodingOptions(language="en", prompt=[]).prompt


class TestPromptGuess:
    """A partial echo Whisper barely believed is a guess; the same words
    said with confidence, or other words at low confidence, are speech."""

    PROMPT = "Ahn, então, hum, na verdade é isso, né? Eh, mais ou menos, porque, ahn, depende."

    def test_prompt_words_at_low_confidence_are_a_guess(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_guess

        assert is_prompt_guess("Ainda, hum, na verdade.", self.PROMPT, [0.02, 0.01, 0.03, 0.02])
        assert is_prompt_guess("Ahn, depende.", self.PROMPT, [0.01, 0.01])

    def test_prompt_words_said_with_confidence_are_speech(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_guess

        assert not is_prompt_guess("Ahn, depende.", self.PROMPT, [0.8, 0.9])

    def test_other_words_at_low_confidence_are_speech(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_guess

        assert not is_prompt_guess("Comprei o sofá em maio.", self.PROMPT, [0.05] * 5)

    def test_one_word_is_never_a_guess(self) -> None:
        from bristlenose.stages.s05_transcribe import is_prompt_guess

        assert not is_prompt_guess("Depende.", self.PROMPT, [0.01])


class TestMlxBackendMarksGuessesInaudible:
    """A guess becomes an inaudible gap, never text the reader could take as spoken."""

    def test_guesses_become_one_marker_and_speech_is_kept(self, monkeypatch, tmp_path) -> None:
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        def _words(text: str, start: float, p: float) -> list[dict[str, object]]:
            return [{"word": " " + w, "start": start + i * 0.4, "end": start + i * 0.4 + 0.3,
                     "probability": p} for i, w in enumerate(text.split())]

        def _seg(start: float, end: float, text: str, p: float) -> dict[str, object]:
            return {"start": start, "end": end, "text": " " + text, "words": _words(text, start, p)}

        def _fake_transcribe(_audio, **_kw):
            return {"language": "en", "segments": [
                _seg(1.0, 3.0, "Okay. Uh, right.", 0.97),
                _seg(3.0, 5.0, "Hmm, okay. Well,", 0.04),
                _seg(5.0, 7.0, "Yes, I suppose so.", 0.03),
                _seg(7.0, 9.0, "We bought the sofa in May.", 0.05),
                _seg(9.0, 9.5, "Hmm, okay.", 0.02),
                _seg(12.0, 13.0, "Hmm, okay.", 0.02),
            ]}

        monkeypatch.setattr(s05_transcribe, "SKIP_NET_ENABLED", False)
        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(14, -30))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake_transcribe)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "en"})()

        segments, _ = s05_transcribe._init_mlx_backend(settings)(tmp_path / "p1.wav", settings)

        assert [(s.text, s.inaudible) for s in segments] == [
            ("Okay. Uh, right.", False), ("", True), ("We bought the sofa in May.", False),
            ("", True), ("", True),
        ]
        # Markers merge only when they touch: a gap is time nothing came back for.
        assert [(s.start_time, s.end_time) for s in segments[3:]] == [(9.0, 9.5), (12.0, 13.0)]
        marker = segments[1]
        assert (marker.start_time, marker.end_time, marker.words) == (3.0, 7.0, [])


class TestStylePromptLanguage:
    def test_codes_and_names_reach_the_same_prompt(self) -> None:
        from bristlenose.stages.s05_transcribe import STYLE_PROMPTS, style_prompt_for

        for given in ("en", "EN", " en ", "English", "english"):
            assert style_prompt_for(given) == STYLE_PROMPTS["en"], given
        assert style_prompt_for("Japanese") == STYLE_PROMPTS["ja"]

    def test_a_language_without_a_measured_prompt_gets_none(self) -> None:
        from bristlenose.stages.s05_transcribe import style_prompt_for

        for given in ("fr", "zh", "", None):
            assert style_prompt_for(given) is None, given


class TestStylePromptFailsOpen:
    """If mlx-whisper's shape moves, transcription runs exactly as before:
    no prompt, nothing dropped, a warning in the log."""

    def test_a_changed_mlx_transcribes_without_the_prompt(
        self, monkeypatch, tmp_path, caplog,
    ) -> None:
        import importlib

        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        module = importlib.import_module("mlx_whisper.transcribe")

        class _Moved:  # no `prompt` field, as a future mlx might have it
            def __init__(self, **kw: object) -> None:
                self.kw = kw

        monkeypatch.setattr(module, "DecodingOptions", _Moved)
        monkeypatch.setattr(s05_transcribe, "_hook_state", {})
        prompt = s05_transcribe.STYLE_PROMPTS["en"]

        def _fake_transcribe(audio_in, **_kw):
            return {"language": "en", "segments": [
                {"start": 1.0, "end": 4.0, "text": " We bought the sofa in May."},
                {"start": 5.0, "end": 8.0, "text": " " + prompt},
            ]}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(10, -30))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake_transcribe)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()

        with caplog.at_level("WARNING"):
            fn = s05_transcribe._init_mlx_backend(settings)
            segments, _ = fn(tmp_path / "p1.wav", settings)

        assert module.DecodingOptions is _Moved
        # Without the prompt nothing is an echo: both segments are kept.
        assert len(segments) == 2
        assert "Style prompt not applied" in caplog.text

    def test_the_gate_closes_when_transcribe_raises(self, monkeypatch, tmp_path) -> None:
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        def _boom(audio_in, **_kw):
            raise RuntimeError("decoder fell over")

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(10, -30))
        monkeypatch.setattr(mlx_whisper, "transcribe", _boom)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()

        fn = s05_transcribe._init_mlx_backend(settings)
        with pytest.raises(RuntimeError):
            fn(tmp_path / "p1.wav", settings)
        assert s05_transcribe._STYLE_PROMPT_ON.get() is False


class TestFasterWhisperGetsTheStylePrompt:
    """faster-whisper keeps conditioning on, so one unpunctuated window locks the
    style for the file; its `hotwords` carries the prompt to every window. The
    language has to be known first, so an unpinned run detects it before."""

    def _backend(self, monkeypatch, detected: str):
        import sys
        import types

        import pytest

        pytest.importorskip("faster_whisper")
        import faster_whisper.audio

        from bristlenose.stages import s05_transcribe

        calls: dict[str, object] = {}

        class _Model:
            def __init__(self, *a: object, **kw: object) -> None:
                pass

            def detect_language(self, audio, **kw):
                calls["detected_on"] = audio
                return detected, 0.93, []

            def transcribe(self, audio, **kw):
                calls["transcribe"] = kw
                info = types.SimpleNamespace(
                    language=kw["language"], language_probability=1.0, duration=10.0,
                )
                return iter([]), info

        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = _Model  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        monkeypatch.setitem(sys.modules, "faster_whisper.audio", faster_whisper.audio)
        monkeypatch.setattr(faster_whisper.audio, "decode_audio", lambda _p: "AUDIO")
        hw = type("H", (), {"cuda_available": False})()
        return s05_transcribe, hw, calls

    def _settings(self, language: str):
        return type("S", (), {
            "whisper_model": "tiny", "whisper_language": language,
            "whisper_compute_type": "int8",
        })()

    def test_an_unpinned_run_detects_then_prompts(self, monkeypatch, tmp_path) -> None:
        s05, hw, calls = self._backend(monkeypatch, detected="en")
        settings = self._settings("auto")

        fn = s05._init_faster_whisper_backend(settings, hw)
        _segments, language = fn(tmp_path / "p1.wav", settings)

        assert calls["detected_on"] == "AUDIO"
        kw = calls["transcribe"]
        assert kw["language"] == "en"
        assert kw["hotwords"] == s05.STYLE_PROMPTS["en"]
        assert language == "en"

    def test_a_language_without_a_prompt_gets_none(self, monkeypatch, tmp_path) -> None:
        s05, hw, calls = self._backend(monkeypatch, detected="fr")
        settings = self._settings("auto")

        fn = s05._init_faster_whisper_backend(settings, hw)
        fn(tmp_path / "p1.wav", settings)

        assert calls["transcribe"]["hotwords"] is None

    def test_a_pinned_language_is_not_detected_again(self, monkeypatch, tmp_path) -> None:
        s05, hw, calls = self._backend(monkeypatch, detected="fr")
        settings = self._settings("ja")

        fn = s05._init_faster_whisper_backend(settings, hw)
        fn(tmp_path / "p1.wav", settings)

        assert "detected_on" not in calls
        assert calls["transcribe"]["language"] == "ja"
        assert calls["transcribe"]["hotwords"] == s05.STYLE_PROMPTS["ja"]


class TestFindSkippedStretches:
    """A stretch with sound and almost no words is speech Whisper jumped over."""

    def _levels(self, seconds: float, loud: list[tuple[float, float]]):
        import numpy as np

        lv = np.full(int(seconds * 10), -70.0)  # room tone
        for a, b in loud:
            lv[int(a * 10):int(b * 10)] = -25.0  # speech
        return lv

    def test_a_gap_over_speech_is_found(self) -> None:
        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        spans = [(0.0, 10.0, 25), (30.0, 40.0, 25)]
        assert find_skipped_stretches(spans, self._levels(40, [(0, 40)]), 40) == [(10.0, 30.0)]

    def test_a_gap_over_room_tone_is_a_pause(self) -> None:
        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        spans = [(0.0, 10.0, 25), (30.0, 40.0, 25)]
        loud = [(0, 10), (30, 40)]
        assert find_skipped_stretches(spans, self._levels(40, loud), 40) == []

    def test_one_long_near_empty_segment_is_found(self) -> None:
        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        spans = [(0.0, 10.0, 25), (10.0, 36.0, 1), (36.0, 46.0, 25)]
        assert find_skipped_stretches(spans, self._levels(46, [(0, 46)]), 46) == [(10.0, 36.0)]

    def test_a_short_gap_is_not_a_skip(self) -> None:
        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        spans = [(0.0, 10.0, 25), (15.0, 25.0, 25)]
        assert find_skipped_stretches(spans, self._levels(25, [(0, 25)]), 25) == []

    def test_speech_with_no_pauses_still_counts_as_sound(self) -> None:
        """No quiet tenth to take a floor from: the cap keeps the net working."""
        import numpy as np

        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        spans = [(0.0, 10.0, 25), (30.0, 40.0, 25)]
        assert find_skipped_stretches(spans, np.full(400, -25.0), 40) == [(10.0, 30.0)]

    def test_a_silent_file_has_nothing_to_find(self) -> None:
        import numpy as np

        from bristlenose.stages.s05_transcribe import find_skipped_stretches

        assert find_skipped_stretches([], np.full(300, -np.inf), 30) == []


class TestMlxBackendRecoversSkippedSpeech:
    """The wiring: a skipped stretch is re-decoded on its own and the new text
    replaces the old only when it is real speech."""

    def _run(self, monkeypatch, tmp_path, redecode_text: str):
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        calls: list[int] = []
        first = [
            {"start": 0.0, "end": 10.0, "text": " " + " ".join(f"a{i}" for i in range(25))},
            {"start": 10.0, "end": 30.0, "text": " Certo."},
            {"start": 30.0, "end": 40.0, "text": " " + " ".join(f"b{i}" for i in range(25))},
        ]

        def _fake(audio_in, **_kw):
            calls.append(len(audio_in))
            if len(calls) == 1:
                return {"language": "pt", "segments": first}
            return {"language": "pt", "segments": [
                {"start": 0.5, "end": 19.5, "text": redecode_text,
                 "words": [{"word": " x", "start": 1.0, "end": 1.2, "probability": 0.9}]},
            ]}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(40, -20))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()
        fn = s05_transcribe._init_mlx_backend(settings)
        segments, _ = fn(tmp_path / "p1.wav", settings)
        return segments, calls

    def test_skipped_speech_is_recovered_in_place(self, monkeypatch, tmp_path) -> None:
        recovered = " ".join(f"palavra{i}" for i in range(40))
        segments, calls = self._run(monkeypatch, tmp_path, " " + recovered)

        assert calls == [40 * 16000, 20 * 16000]  # the file, then just the stretch
        assert [round(s.start_time) for s in segments] == [0, 10, 30]
        assert segments[1].text == recovered
        assert segments[1].words[0].start_time == 11.0  # word times moved too
        assert "Certo." not in " ".join(s.text for s in segments)

    def test_a_redecode_without_real_speech_changes_nothing(self, monkeypatch, tmp_path) -> None:
        segments, calls = self._run(monkeypatch, tmp_path, " Obrigado.")

        assert len(calls) == 2
        assert [s.text for s in segments][1] == "Certo."

    def test_a_dropped_prompt_echo_is_re_decoded(self, monkeypatch, tmp_path) -> None:
        """The net runs after the echo filter, so the gap an echo leaves over
        real speech is re-transcribed, without the prompt."""
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        prompt = s05_transcribe.STYLE_PROMPTS["en"]
        calls: list[int] = []

        def _fake(audio_in, **_kw):
            calls.append(len(audio_in))
            if len(calls) == 1:
                return {"language": "en", "segments": [
                    {"start": 0.0, "end": 10.0, "text": " " + " ".join(f"a{i}" for i in range(25))},
                    {"start": 10.0, "end": 30.0, "text": " " + prompt},
                    {"start": 30.0, "end": 40.0, "text": " " + " ".join(f"b{i}" for i in range(25))},
                ]}
            return {"language": "en", "segments": [
                {"start": 0.5, "end": 19.5, "text": " " + " ".join(f"c{i}" for i in range(40))},
            ]}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(40, -20))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()
        segments, _ = s05_transcribe._init_mlx_backend(settings)(tmp_path / "p1.wav", settings)

        assert calls == [40 * 16000, 20 * 16000]
        assert [s.text.split()[0] for s in segments] == ["a0", "c0", "b0"]


    def test_a_repetition_loop_is_treated_as_lost_speech(self, monkeypatch, tmp_path) -> None:
        """Forty "nada"s are one word once the repeat filter has run, so the
        stretch is a gap and is re-decoded."""
        import pytest

        pytest.importorskip("mlx_whisper")
        import mlx_whisper
        import mlx_whisper.audio

        from bristlenose.stages import s05_transcribe

        calls: list[int] = []

        def _fake(audio_in, **_kw):
            calls.append(len(audio_in))
            if len(calls) == 1:
                return {"language": "es", "segments": [
                    {"start": 0.0, "end": 10.0, "text": " " + " ".join(f"a{i}" for i in range(25))},
                    {"start": 10.0, "end": 30.0, "text": " " + " ".join(["nada"] * 40)},
                    {"start": 30.0, "end": 40.0, "text": " " + " ".join(f"b{i}" for i in range(25))},
                ]}
            return {"language": "es", "segments": [
                {"start": 0.5, "end": 19.5, "text": " " + " ".join(f"c{i}" for i in range(40))},
            ]}

        monkeypatch.setattr(mlx_whisper.audio, "load_audio", lambda _p: _tone(40, -20))
        monkeypatch.setattr(mlx_whisper, "transcribe", _fake)
        settings = type("S", (), {"whisper_model": "tiny", "whisper_language": "auto"})()
        segments, _ = s05_transcribe._init_mlx_backend(settings)(tmp_path / "p1.wav", settings)

        assert calls == [40 * 16000, 20 * 16000]
        assert [s.text.split()[0] for s in segments] == ["a0", "c0", "b0"]
