"""Apple's speech model as Whisper's first-run stopgap (``bristlenose/apple_speech.py``).

The decisions are tested as pure functions; the helper is a fake script that
honours the JSON contract in ``tests/fixtures/apple-speech/`` (the Swift side's
gate checks the real binary against the same fixture). Plan:
``docs/design-apple-first-transcription.md``.
"""

from __future__ import annotations

import copy
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from bristlenose import apple_speech
from bristlenose.apple_speech import (
    MODE_NEVER,
    MODE_PREFER,
    MODE_UNTIL_WHISPER,
    EngineChoice,
    HelperError,
    HelperProbe,
    apple_locale_for,
    choose_engine,
    language_gate,
    segments_from_helper,
)
from bristlenose.events import CauseCategoryEnum
from bristlenose.models import InputSession

FIXTURE = Path(__file__).parent / "fixtures" / "apple-speech" / "helper-output.json"
SUPPORTED = (
    "en-US", "en-GB", "en-AU", "es-ES", "es-MX", "fr-FR", "fr-CA", "de-DE", "it-IT",
    "ko-KR", "ja-JP", "pt-BR", "pt-PT", "zh-TW", "zh-CN", "yue-CN",
)


def payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_probe_cache() -> None:
    apple_speech._probe_cache.clear()


# ---------------------------------------------------------------------------
# The language guess (§2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("ui", "region", "want"), [
    ("en", "GB", "en-GB"),
    ("en", "AU", "en-AU"),
    ("en", None, "en-US"),
    ("en", "NZ", "en-US"),       # a region the model lacks falls back, never guesses
    ("es", "MX", "es-MX"),
    ("es", "GB", "es-ES"),       # a Spanish UI in London is still Spain's Spanish
    ("fr", "CA", "fr-CA"),
    ("de", "AT", "de-DE"),
    ("it", None, "it-IT"),
    ("ko", "US", "ko-KR"),
    ("ja", None, "ja-JP"),
    ("pt-BR", "PT", "pt-BR"),    # Portuguese carries its variety in the UI code
    ("pt-PT", None, "pt-PT"),
    ("zh-Hant", "HK", "zh-TW"),
    ("zh-Hant-HK", "HK", None),  # Cantonese or Mandarin is the speaker's call
    ("pl", "PL", None),          # a UI language Apple's model does not cover
    (None, "GB", None),
])
def test_ui_language_maps_to_an_apple_locale(ui: str | None, region: str | None,
                                             want: str | None) -> None:
    assert apple_locale_for(ui, region, SUPPORTED) == want


def test_a_locale_is_only_returned_when_the_model_supports_it() -> None:
    assert apple_locale_for("it", None, ("en-US",)) is None
    assert apple_locale_for("en", "gb", ("en_GB",)) == "en_GB"  # spelling-tolerant


# ---------------------------------------------------------------------------
# The engine decision (§1)
# ---------------------------------------------------------------------------

HELPER = Path("/Applications/Bristlenose.app/Contents/Helpers/bristlenose-speech")
OK_PROBE = HelperProbe(available=True, supported=SUPPORTED)


def decide(**over: Any) -> EngineChoice:
    kw: dict[str, Any] = {
        "flag": True, "mode": MODE_UNTIL_WHISPER, "helper": HELPER, "probe": OK_PROBE,
        "whisper_on_disk": False, "whisper_language": "auto", "ui_language": "en",
        "region": "GB",
    }
    kw.update(over)
    return choose_engine(**kw)


def test_a_first_run_on_the_mac_app_goes_to_apple() -> None:
    choice = decide()
    assert choice.is_apple and choice.locale == "en-GB" and choice.helper == HELPER


@pytest.mark.parametrize(("over", "why"), [
    ({"flag": False}, "flag off"),
    ({"mode": MODE_NEVER}, "Whisper only"),
    ({"helper": None}, "not the Mac app"),
    ({"probe": None}, "did not answer"),
    ({"probe": HelperProbe(available=False, reason="needs macOS 26")}, "macOS 26"),
    ({"whisper_on_disk": True}, "on disk"),
    ({"whisper_language": "es"}, "pinned"),
    ({"ui_language": "pl"}, "no Apple locale"),
    ({"ui_language": "zh-Hant-HK"}, "no Apple locale"),
    ({"ui_language_matched": False}, "fallback"),
])
def test_any_condition_missing_gives_whisper(over: dict[str, Any], why: str) -> None:
    choice = decide(**over)
    assert not choice.is_apple
    assert why in choice.reason


def test_prefer_uses_apple_even_with_whisper_on_disk() -> None:
    assert decide(mode=MODE_PREFER, whisper_on_disk=True).is_apple
    assert not decide(mode=MODE_PREFER, ui_language="pl").is_apple


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


def test_results_are_cut_at_pauses_and_sentence_ends() -> None:
    segs = segments_from_helper(payload())
    assert [s.text for s in segs] == [
        "So tell me about the last time you booked a trip.",
        "I think it was in March.",
        "And how did you pay?",
    ]
    assert all(s.source == "apple-speech" for s in segs)
    first = segs[0]
    assert (first.start_time, first.end_time) == (1.0, 3.7)
    assert first.words[1].text == "tell"  # Apple's leading space is not kept
    assert segs[2].words[-1].confidence == 1.0  # a null confidence is not a doubt


def test_a_long_pause_cuts_even_without_punctuation() -> None:
    p = {"results": [{"start": 0, "end": 5, "text": "yes no", "words": [
        {"start": 0, "end": 0.4, "text": "yes", "conf": 0.9},
        {"start": 1.5, "end": 1.9, "text": " no", "conf": 0.9},
    ]}]}
    assert [s.text for s in segments_from_helper(p)] == ["yes", "no"]


def test_a_result_without_timed_words_is_one_segment() -> None:
    p = {"results": [{"start": 2, "end": 4, "text": "Hello there.", "words": []}]}
    (seg,) = segments_from_helper(p)
    assert (seg.start_time, seg.end_time, seg.text, seg.words) == (2, 4, "Hello there.", [])


def test_japanese_words_join_without_spaces() -> None:
    p = {"results": [{"start": 0, "end": 1, "text": "", "words": [
        {"start": 0, "end": 0.3, "text": "今日", "conf": 0.9},
        {"start": 0.3, "end": 0.6, "text": "は", "conf": 0.9},
        {"start": 0.6, "end": 1.0, "text": "晴れ。", "conf": 0.9},
    ]}]}
    assert [s.text for s in segments_from_helper(p)] == ["今日は晴れ。"]


# ---------------------------------------------------------------------------
# The gate (§2)
# ---------------------------------------------------------------------------


def _with_conf(p: dict[str, Any], conf: float | None) -> dict[str, Any]:
    p = copy.deepcopy(p)
    for r in p["results"]:
        for w in r["words"]:
            w["conf"] = conf
    return p


def test_the_right_language_passes() -> None:
    p = payload()
    verdict = language_gate(p, segments_from_helper(p), signal_minutes=0.5)
    assert verdict.passed, verdict


def test_low_confidence_defers() -> None:
    p = _with_conf(payload(), 0.25)  # wrong-locale files measured 0.10-0.38
    verdict = language_gate(p, segments_from_helper(p), signal_minutes=0.5)
    assert not verdict.passed and verdict.reason == "low confidence"


def test_zero_words_over_speech_defers() -> None:
    verdict = language_gate({"results": []}, [], signal_minutes=3.0)
    assert not verdict.passed and "no words" in verdict.reason


def test_too_few_words_for_the_speech_heard_defers() -> None:
    p = payload()  # 22 words; over ten minutes of speech that is 2 a minute
    verdict = language_gate(p, segments_from_helper(p), signal_minutes=10.0)
    assert not verdict.passed and "too few words" in verdict.reason


def test_a_short_file_is_judged_on_confidence_alone() -> None:
    """Under a quarter-minute of signal is too little for a rate."""
    p = payload()
    assert language_gate(p, segments_from_helper(p), signal_minutes=0.1).passed
    # …but no words at all over sound is never "ok": it would be cached as no
    # speech and never reach Whisper.
    assert not language_gate({"results": []}, [], signal_minutes=0.1).passed


def test_a_code_switched_file_is_judged_over_the_whole_file() -> None:
    """Half the words heard well and half badly averages over the bar: kept.

    The gate reads the whole file on purpose (the first minutes can be small
    talk in another language); a mostly-right file is the model's to keep.
    """
    p = payload()
    words = [w for r in p["results"] for w in r["words"]]
    for i, w in enumerate(words):
        w["conf"] = 0.95 if i % 2 else 0.2
    assert language_gate(p, segments_from_helper(p), signal_minutes=0.5).passed


def test_signal_minutes_counts_active_windows() -> None:
    levels = np.full(1200, -80.0)  # two minutes of near silence
    levels[:600] = -20.0           # one minute of speech
    assert apple_speech.signal_minutes(levels) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# The helper, faked
# ---------------------------------------------------------------------------


def _fake_helper(tmp_path: Path, *, out: dict[str, Any] | None = None, exit_code: int = 0,
                 probe: dict[str, Any] | None = None) -> Path:
    """A script honouring the helper's command line and output contract."""
    if sys.platform == "win32":
        pytest.skip("the fake helper is a #! script, which Windows cannot run; the real one is a macOS binary")
    data = tmp_path / "fake-output.json"
    data.write_text(json.dumps(out if out is not None else payload()), encoding="utf-8")
    probe_line = json.dumps(probe if probe is not None else {
        "schema": 1, "available": True, "reason": None, "os_version": "Version 27.0",
        "supported": list(SUPPORTED), "installed": ["en-GB"],
    })
    script = tmp_path / "bristlenose-speech"
    script.write_text(f"""#!{sys.executable}
import shutil, sys
args = sys.argv[1:]
if args == ["probe"]:
    print({probe_line!r}); sys.exit(0)
if args and args[0] == "transcribe":
    sys.stderr.write("@progress 5.00 30.00\\n@progress 30.00 30.00\\n")
    if {exit_code}:
        sys.stderr.write("analysis failed: boom\\n"); sys.exit({exit_code})
    shutil.copy({str(data)!r}, args[3]); sys.exit(0)
sys.exit(2)
""", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_probe_reads_the_helper(tmp_path: Path) -> None:
    probe = apple_speech.probe_helper(_fake_helper(tmp_path))
    assert probe is not None and probe.available and "en-GB" in probe.supported


def test_a_probe_that_prints_nonsense_reads_as_absent(tmp_path: Path) -> None:
    script = tmp_path / "bristlenose-speech"
    script.write_text(f"#!{sys.executable}\nprint('hello')\n", encoding="utf-8")
    script.chmod(0o755)
    assert apple_speech.probe_helper(script) is None


def test_run_helper_reports_progress_and_returns_the_json(tmp_path: Path) -> None:
    seen: list[tuple[float, float]] = []
    data = apple_speech.run_helper(
        _fake_helper(tmp_path), tmp_path / "a.wav", "en-GB", tmp_path / "out.json",
        on_progress=lambda d, t: seen.append((d, t)),
    )
    assert data["locale"] == "en-GB"
    assert seen == [(5.0, 30.0), (30.0, 30.0)]


def test_a_failing_helper_raises_with_its_last_line(tmp_path: Path) -> None:
    with pytest.raises(HelperError, match="exited 2: analysis failed: boom") as err:
        apple_speech.run_helper(_fake_helper(tmp_path, exit_code=2), tmp_path / "a.wav",
                                "en-GB", tmp_path / "out.json")
    assert err.value.exit_code == 2


def test_helper_path_needs_an_executable_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(apple_speech.HELPER_ENV, raising=False)
    assert apple_speech.helper_path() is None
    monkeypatch.setenv(apple_speech.HELPER_ENV, str(tmp_path / "missing"))
    assert apple_speech.helper_path() is None
    helper = _fake_helper(tmp_path)
    monkeypatch.setenv(apple_speech.HELPER_ENV, str(helper))
    assert apple_speech.helper_path() == helper


# ---------------------------------------------------------------------------
# Stage 5 through the Apple backend
# ---------------------------------------------------------------------------


def _session(tmp_path: Path) -> InputSession:
    from datetime import datetime, timezone

    from bristlenose.models import FileType, InputFile

    audio = tmp_path / "interview.wav"
    audio.write_bytes(b"not decoded: load_audio_16k is faked")
    return InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        session_date=datetime(2026, 10, 18, tzinfo=timezone.utc),
        files=[InputFile(path=audio, file_type=FileType.AUDIO, size_bytes=1,
                         created_at=datetime(2026, 10, 18, tzinfo=timezone.utc))],
        audio_path=audio,
    )


def _transcribe(tmp_path: Path, monkeypatch, out: dict[str, Any], *,
                whisper_on_disk: bool = False, exit_code: int = 0) -> Any:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.models import TranscriptSegment
    from bristlenose.stages import s05_transcribe as s05

    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(16000 * 30) * 0.1).astype(np.float32)  # -20 dBFS throughout
    monkeypatch.setattr("bristlenose.stages.s05b_voice.load_audio_16k", lambda _p: audio)
    monkeypatch.setattr(s05, "whisper_is_on_disk", lambda _s: whisper_on_disk)

    def fake_whisper(_settings: Any, *_a: Any) -> Any:
        def fn(path: Path, settings: Any, on_segment: Any = None) -> Any:
            return [TranscriptSegment(start_time=0, end_time=2, text="Hola.", source="mlx-whisper")], "es"
        return fn

    monkeypatch.setattr(s05, "_init_mlx_backend", fake_whisper)
    monkeypatch.setattr(s05, "_init_faster_whisper_backend", fake_whisper)
    helper = _fake_helper(tmp_path, out=out, exit_code=exit_code)
    token = s05.RUN_ENGINE.set(EngineChoice("apple", "test", locale="en-GB", helper=helper))
    try:
        settings = BristlenoseSettings(output_dir=tmp_path / "out")
        (done,) = list(s05.iter_transcribe_sessions([_session(tmp_path)], settings))
    finally:
        s05.RUN_ENGINE.reset(token)
    return done


def test_stage_5_transcribes_with_apple(tmp_path: Path, monkeypatch) -> None:
    done = _transcribe(tmp_path, monkeypatch, payload())
    assert done.failure is None
    assert [s.source for s in done.segments] == ["apple-speech"] * 3
    # A guess is never recorded as a detection (§2).
    assert done.detected_language is None
    rec = done.quality["recognition"]
    assert rec["backend"] == "apple-speech"
    assert (rec["locale"], rec["locale_source"]) == ("en-GB", "assumed")
    assert rec["gate"]["passed"] is True


def test_stage_5_defers_a_session_in_the_wrong_language(tmp_path: Path, monkeypatch) -> None:
    done = _transcribe(tmp_path, monkeypatch, _with_conf(payload(), 0.2))
    assert done.segments == []
    assert done.failure is not None
    assert done.failure.cause.category == CauseCategoryEnum.DEFERRED
    assert done.failure.cause.code == "language_unsure"
    # The record says why, for the Diagnostics row; it carries no words.
    assert done.quality["recognition"]["gate"]["reason"] == "low confidence"


def test_with_whisper_on_disk_a_deferred_session_goes_to_whisper_now(tmp_path: Path,
                                                                      monkeypatch) -> None:
    """Whisper landed mid-run, or the mode is "prefer": no need to wait."""
    done = _transcribe(tmp_path, monkeypatch, _with_conf(payload(), 0.2), whisper_on_disk=True)
    assert done.failure is None
    assert [s.source for s in done.segments] == ["mlx-whisper"]
    assert done.detected_language == "es"  # Whisper detects; nothing was assumed


@pytest.mark.parametrize(("exit_code", "code"), [
    (5, "helper_exit_5"),   # the locale model could not be fetched (offline)
    (2, "helper_exit_2"),   # analysis failed on this file
])
def test_a_helper_failure_defers_rather_than_failing(tmp_path: Path, monkeypatch,
                                                     exit_code: int, code: str) -> None:
    """Not a Whisper failure: Whisper never ran. Deferred, so it reaches Whisper."""
    done = _transcribe(tmp_path, monkeypatch, payload(), exit_code=exit_code)
    assert done.failure is not None
    assert done.failure.cause.category == CauseCategoryEnum.DEFERRED
    assert done.failure.cause.code == code


def test_after_an_engine_level_exit_later_sessions_skip_the_helper(tmp_path: Path,
                                                                   monkeypatch) -> None:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.stages import s05_transcribe as s05

    calls: list[str] = []
    real = apple_speech.run_helper

    def counting(*a: Any, **k: Any) -> Any:
        calls.append("helper")
        return real(*a, **k)

    monkeypatch.setattr(apple_speech, "run_helper", counting)
    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(16000 * 30) * 0.1).astype(np.float32)
    monkeypatch.setattr("bristlenose.stages.s05b_voice.load_audio_16k", lambda _p: audio)
    monkeypatch.setattr(s05, "whisper_is_on_disk", lambda _s: False)
    helper = _fake_helper(tmp_path, exit_code=3)
    a, b = _session(tmp_path), _session(tmp_path)
    b = b.model_copy(update={"session_id": "s2"})
    token = s05.RUN_ENGINE.set(EngineChoice("apple", "t", locale="en-GB", helper=helper))
    try:
        done = list(s05.iter_transcribe_sessions([a, b], BristlenoseSettings()))
    finally:
        s05.RUN_ENGINE.reset(token)
    assert calls == ["helper"], "the second session asked a helper that had said it cannot"
    assert [d.failure.cause.code for d in done] == ["helper_exit_3", "helper_unavailable"]


@pytest.mark.skipif(sys.platform == "win32", reason="the slow helper is a #! script, which Windows cannot run")
def test_a_helper_that_runs_too_long_is_killed_and_named(tmp_path: Path) -> None:
    script = tmp_path / "slow-helper"
    script.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n", encoding="utf-8")
    script.chmod(0o755)
    with pytest.raises(HelperError, match="timed out") as err:
        apple_speech.run_helper(script, tmp_path / "a.wav", "en-GB", tmp_path / "o.json",
                                timeout=0.5)
    assert err.value.timed_out


def test_a_progress_callback_that_raises_does_not_orphan_the_helper(tmp_path: Path) -> None:
    def boom(_d: float, _t: float) -> None:
        raise RuntimeError("callback")

    with pytest.raises(RuntimeError, match="callback"):
        apple_speech.run_helper(_fake_helper(tmp_path), tmp_path / "a.wav", "en-GB",
                                tmp_path / "out.json", on_progress=boom)
    # The fake helper exits by itself; the point is no zombie and no hang here.


def test_decide_engine_reads_settings_env_and_helper(tmp_path: Path, monkeypatch) -> None:
    from bristlenose import i18n
    from bristlenose.config import BristlenoseSettings
    from bristlenose.stages import s05_transcribe as s05

    monkeypatch.setenv(apple_speech.HELPER_ENV, str(_fake_helper(tmp_path)))
    monkeypatch.setenv(apple_speech.REGION_ENV, "GB")
    monkeypatch.setenv(apple_speech.UI_LANGUAGE_MATCHED_ENV, "1")
    monkeypatch.setattr(s05, "whisper_is_on_disk", lambda _s: False)
    old = i18n.get_locale()
    i18n.set_locale("en")
    try:
        on = BristlenoseSettings(experimental_apple_speech=True)
        choice = s05.decide_engine(on)
        assert choice.is_apple and choice.locale == "en-GB"
        # The kill switch turns it off.
        assert not s05.decide_engine(BristlenoseSettings(experimental_apple_speech=False)).is_apple
        never = BristlenoseSettings(experimental_apple_speech=True, apple_speech=MODE_NEVER)
        assert not s05.decide_engine(never).is_apple
        # A UI language the app fell back to is not the researcher's.
        monkeypatch.delenv(apple_speech.UI_LANGUAGE_MATCHED_ENV)
        assert not s05.decide_engine(on).is_apple
    finally:
        i18n.set_locale(old)


def test_a_pinned_engine_wins_over_a_fresh_decision(monkeypatch) -> None:
    """The preflight's choice holds for stage 5, even if Whisper lands between."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.stages import s05_transcribe as s05

    pinned = EngineChoice("apple", "pinned", locale="en-GB", helper=HELPER)
    token = s05.RUN_ENGINE.set(pinned)
    try:
        assert s05.decide_engine(BristlenoseSettings()) is pinned
    finally:
        s05.RUN_ENGINE.reset(token)


def test_the_timing_profile_is_keyed_by_engine(monkeypatch) -> None:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.stages import s05_transcribe as s05
    from bristlenose.timing import build_hardware_key

    settings = BristlenoseSettings()
    whisper_key = build_hardware_key(settings)
    monkeypatch.setattr(s05, "decide_engine",
                        lambda _s: EngineChoice("apple", "t", locale="en-GB", helper=HELPER))
    apple_key = build_hardware_key(settings)
    assert "apple-speech" in apple_key and apple_key != whisper_key


# ---------------------------------------------------------------------------
# The download job's progress lines (§3 D)
# ---------------------------------------------------------------------------


def test_doctor_fetch_progress_lines(monkeypatch) -> None:
    from bristlenose.preflight import whisper as preflight

    monkeypatch.setattr(preflight, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(preflight, "_resolve_repo_id", lambda _s: "org/model")
    states = iter(["missing", "cached"])  # before the fetch, and after it
    monkeypatch.setattr(preflight, "cache_state", lambda _r: next(states))
    monkeypatch.setattr(preflight, "_server_total_bytes", lambda _r: 1000)
    ticks = iter(float(i) for i in range(1000))

    def fake_fetch(repo_id: str, *, tqdm_class: Any) -> str:
        wire = tqdm_class(desc="Downloading bytes", unit="B", total=0)
        recon = tqdm_class(desc="Reconstructing (incomplete total...)", unit="B", total=0)
        files = tqdm_class(desc="Fetching 2 files", unit="it", total=2)
        for _ in range(10):
            wire.update(90)    # wire bytes finish below the file sizes (dedup)
            recon.update(100)
        files.update(2)
        return "/cache"

    monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model", fake_fetch)
    lines: list[str] = []
    preflight.fetch_with_progress_lines(object(), lines.append, clock=lambda: next(ticks))  # type: ignore[arg-type]
    assert lines[0] == "@download-start org/model 1000"
    assert lines[-1].startswith("@download-done ")
    progress = [tuple(map(int, ln.split()[1:])) for ln in lines if ln.startswith("@download ")]
    assert progress[-1] == (1000, 1000)
    assert all(total == 1000 for _, total in progress)
    assert [d for d, _ in progress] == sorted(d for d, _ in progress)  # never goes back


def test_doctor_fetch_says_done_only_when_the_run_will_find_it(monkeypatch) -> None:
    from bristlenose.preflight import whisper as preflight
    from bristlenose.utils.package_install import PackageInstallError

    monkeypatch.setattr(preflight, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(preflight, "_resolve_repo_id", lambda _s: "org/model")
    monkeypatch.setattr(preflight, "cache_state", lambda _r: "missing")  # before and after
    monkeypatch.setattr(preflight, "_server_total_bytes", lambda _r: 10)
    monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model",
                        lambda repo_id, *, tqdm_class: "/cache")
    lines: list[str] = []
    with pytest.raises(PackageInstallError, match="not complete"):
        preflight.fetch_with_progress_lines(object(), lines.append)  # type: ignore[arg-type]
    assert not any(ln.startswith("@download-done") for ln in lines)


def test_doctor_fetch_already_on_disk(monkeypatch) -> None:
    from bristlenose.preflight import whisper as preflight

    monkeypatch.setattr(preflight, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(preflight, "_resolve_repo_id", lambda _s: "org/model")
    monkeypatch.setattr(preflight, "cache_state", lambda _r: "cached")
    lines: list[str] = []
    preflight.fetch_with_progress_lines(object(), lines.append)  # type: ignore[arg-type]
    assert lines == ["@download-start org/model 0", "@download-done 0"]


def test_settings_default_has_apple_speech_on_with_a_kill_switch() -> None:
    from bristlenose.config import BristlenoseSettings

    s = BristlenoseSettings()
    assert s.experimental_apple_speech is True  # unparked 22 Oct 2026
    assert BristlenoseSettings(experimental_apple_speech=False).experimental_apple_speech is False
    assert s.apple_speech == MODE_UNTIL_WHISPER
    assert os.environ.get("BRISTLENOSE_EXPERIMENTAL_APPLE_SPEECH") in (None, "", "0")


def test_doctor_and_the_run_agree_on_a_partial_download(monkeypatch) -> None:
    """``doctor`` asked ``scan_cache_dir``, which lists a repo once config.json
    has landed, so a stopped download read as cached while the run fetched it
    again. Both now ask the preflight's probe."""
    from unittest.mock import MagicMock, patch

    from bristlenose.config import BristlenoseSettings
    from bristlenose.doctor import CheckStatus, check_whisper_model
    from bristlenose.preflight import whisper as preflight

    repo = MagicMock(repo_id="org/model", size_on_disk=1_000)
    monkeypatch.setattr(preflight, "_resolve_repo_id", lambda _s: "org/model")
    monkeypatch.setattr(preflight, "unknown_model_message", lambda _s: None)
    monkeypatch.delenv("BRISTLENOSE_WHISPER_MODEL_DIR", raising=False)
    with patch("huggingface_hub.scan_cache_dir", return_value=MagicMock(repos=[repo])):
        monkeypatch.setattr(preflight, "cache_state", lambda _r: "partial")
        partial = check_whisper_model(BristlenoseSettings())
        monkeypatch.setattr(preflight, "cache_state", lambda _r: "cached")
        cached = check_whisper_model(BristlenoseSettings())
    assert partial.status == CheckStatus.SKIP and "partly" in partial.detail
    assert cached.status == CheckStatus.OK


def test_whisper_status_line(monkeypatch) -> None:
    from bristlenose.preflight import whisper as preflight

    monkeypatch.setattr(preflight, "_resolve_repo_id", lambda _s: "org/model")
    monkeypatch.setattr(preflight, "cache_state", lambda _r: "partial")
    assert preflight.whisper_status_line(object()) == "@whisper-status partial org/model 0"  # type: ignore[arg-type]
