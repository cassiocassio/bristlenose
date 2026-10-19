"""A session whose transcription failed or was deferred is tried again next run.

Apple's first-run model can send a session on to Whisper when the recording
does not sound like the language it assumed
(``docs/design-apple-first-transcription.md`` §2). That only works if the next
run transcribes it, and until 18 Oct 2026 it would not have: every freshly
transcribed session was marked complete in the manifest, failed ones included,
so a failed session's empty result was served from the cache for good. Driven
through the real ``bristlenose run`` (``tests/lifecycle_rig.py``).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from bristlenose.events import CauseCategoryEnum
from tests.lifecycle_rig import new_study


def test_a_deferred_only_recording_is_not_an_abandoned_run(tmp_path: Path) -> None:
    """One recording, deferred: the run completes and says so; nothing is lost."""
    study = new_study(tmp_path, "Entrevista.wav")
    study.run(fail={"Entrevista.wav": CauseCategoryEnum.DEFERRED})  # asserts exit 0
    assert study.transcribed[0] == ["Entrevista.wav"]
    assert "Waiting for Whisper" in study.last_output
    assert "No usable content" not in study.last_output
    # What the Mac reads to say "Waiting for Whisper" and to re-run later.
    failed = study.last_summary()["transcripts"]["failed"]
    assert [f["cause"]["category"] for f in failed] == ["deferred"]


def test_a_deferred_session_is_transcribed_on_the_next_run(tmp_path: Path) -> None:
    study = new_study(tmp_path, "Interview 1.wav", "Entrevista.wav")
    study.run(fail={"Entrevista.wav": CauseCategoryEnum.DEFERRED})
    study.run()
    assert study.transcribed[1] == ["Entrevista.wav"], (
        "the deferred session was served from the cache instead of transcribed again"
    )
    study.run()
    assert study.transcribed[2] == [], "a transcribed session was transcribed again"


def test_a_failed_whisper_session_is_tried_again(tmp_path: Path) -> None:
    """The same rule for an ordinary failure, which it fixed as well."""
    study = new_study(tmp_path, "Interview 1.wav", "Interview 2.wav")
    study.run(fail={"Interview 2.wav": CauseCategoryEnum.WHISPER})
    study.run(fail={"Interview 2.wav": CauseCategoryEnum.WHISPER})
    assert study.transcribed[1] == ["Interview 2.wav"]
    # A retry is not a new interview: the Mac's "+N new sessions" stays quiet.
    assert not study.last_summary().get("new_sessions")
    study.run()
    assert study.transcribed[2] == ["Interview 2.wav"]


def test_one_deferral_does_not_hide_a_run_where_everything_else_failed(tmp_path: Path) -> None:
    study = new_study(tmp_path, "Interview 1.wav", "Entrevista.wav")
    import pytest

    with pytest.raises(AssertionError, match="run exited"):
        study.run(fail={"Interview 1.wav": CauseCategoryEnum.WHISPER,
                        "Entrevista.wav": CauseCategoryEnum.DEFERRED})


def test_changing_the_engine_setting_does_not_re_transcribe(tmp_path: Path) -> None:
    """The engine never joins a session's fingerprint: a session Apple's model
    transcribed stays Apple's, or a re-run would silently re-transcribe it and
    orphan the stars, tags and edits hung off its words (README § 7)."""
    from bristlenose.apple_speech import EngineChoice

    apple = EngineChoice("apple", "first run", locale="en-GB", helper=Path("/x/helper"))
    study = new_study(tmp_path, "Interview 1.wav")
    with patch.dict(os.environ, {"BRISTLENOSE_EXPERIMENTAL_APPLE_SPEECH": "1",
                                 "BRISTLENOSE_APPLE_SPEECH": "prefer"}), \
            patch("bristlenose.stages.s05_transcribe.decide_engine", return_value=apple):
        study.run()
    assert study.whisper_preflights == [0], "run 1 was not on Apple's model"
    with patch.dict(os.environ, {"BRISTLENOSE_EXPERIMENTAL_APPLE_SPEECH": "0",
                                 "BRISTLENOSE_APPLE_SPEECH": "never"}):
        study.run()
    assert study.whisper_preflights[1] == 1, "run 2 was not on Whisper"
    assert study.transcribed[1] == []


def test_python_never_fetches_whisper_on_the_apple_path(tmp_path: Path) -> None:
    """On the Apple path the run does not start the 1.6 GB download: the Mac
    app owns the one download, and two fetchers of one repo each write their
    own partial (docs/design-apple-first-transcription.md §3 C)."""
    from bristlenose.apple_speech import EngineChoice

    apple = EngineChoice("apple", "first run", locale="en-GB", helper=Path("/x/helper"))
    study = new_study(tmp_path, "Interview 1.wav")
    with patch("bristlenose.stages.s05_transcribe.decide_engine", return_value=apple):
        study.run()
    assert study.whisper_preflights == [0]
    study.add_recording("Interview 2.wav")
    study.run()  # Whisper's turn: the preflight runs as it always has
    assert study.whisper_preflights[1] == 1
