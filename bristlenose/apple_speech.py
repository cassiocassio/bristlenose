"""Apple's on-device speech model as a first-run stopgap for Whisper.

When the Mac app runs on macOS 26 or later and Whisper is not on disk yet, a
run can transcribe with Apple's ``SpeechTranscriber`` instead of waiting for a
1.6 GB download, in the nine languages it covers. Plan:
``docs/design-apple-first-transcription.md``; evidence:
``experiments/apple-speech/README.md`` (18 Oct 2026).

This module holds the decisions, which are pure and testable without a Mac:

- :func:`apple_locale_for` — the UI language as the interview's language (§2's
  table). A guess, and recorded as one (``locale_source: "assumed"``).
- :func:`choose_engine` — whether this run goes to Apple or Whisper (§1). The
  engine is chosen once per run, never per session.
- :func:`segments_from_helper` — Apple's long results cut into Whisper-sized
  segments, which stage 5b labels one by one.
- :func:`language_gate` — whether the guess held (§2). A session that fails it
  is deferred to Whisper, never kept.

…and the one impure part, :func:`run_helper`, which launches the Swift helper
(``desktop/speech-helper/``) that the app bundles. Its JSON contract is
``tests/fixtures/apple-speech/``.

The CLI never takes this path: only the Mac app sets ``BRISTLENOSE_SPEECH_HELPER``.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Set by the Mac app to the bundled helper's path. Its absence is the CLI.
HELPER_ENV = "BRISTLENOSE_SPEECH_HELPER"
#: The Mac's region (``Locale.current.region``), so English is en-GB in London.
REGION_ENV = "BRISTLENOSE_SPEECH_REGION"
#: "1" when the app's UI language is one the researcher chose or speaks: their
#: own pick in Settings, or the Mac's first preferred language. Absent when the
#: app fell back to English because it does not render the Mac's language — the
#: Greek or Hindi researcher `cca68462` protected — so Apple is never told to
#: hear English on a guess built on a fallback.
UI_LANGUAGE_MATCHED_ENV = "BRISTLENOSE_SPEECH_UI_MATCHED"

#: ``TranscriptSegment.source`` for a segment Apple's model wrote.
SOURCE = "apple-speech"

#: The helper's JSON schema this side reads.
SCHEMA = 1

#: ``apple_speech`` setting values.
MODE_UNTIL_WHISPER = "until-whisper"  # Apple until Whisper is on disk (default)
MODE_PREFER = "prefer"                # Apple in its languages, Whisper for the rest
MODE_NEVER = "never"                  # Whisper only
MODES = (MODE_UNTIL_WHISPER, MODE_PREFER, MODE_NEVER)

# ---------------------------------------------------------------------------
# The language guess (§2)
# ---------------------------------------------------------------------------

#: UI language → Apple locale when the Mac's region does not pick one. ``None``
#: refuses: Hong Kong Chinese may be spoken as Cantonese or Mandarin, which is
#: the speaker's call, not the reader's.
_DEFAULT_REGION: dict[str, str | None] = {
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "ko": "ko-KR",
    "ja": "ja-JP",
    "pt-BR": "pt-BR",
    "pt-PT": "pt-PT",
    "zh-Hant": "zh-TW",
    "zh-Hant-HK": None,
}

#: UI languages whose region the Mac's own region may refine (en-GB, es-MX,
#: fr-CA, de-AT…). Portuguese and Chinese carry their variety in the UI code.
_REGION_REFINES = frozenset({"en", "es", "fr", "de", "it"})


def _norm(tag: str) -> str:
    return tag.replace("_", "-").lower()


def apple_locale_for(
    ui_language: str | None,
    region: str | None,
    supported: Sequence[str],
) -> str | None:
    """The Apple locale to assume for a recording, or ``None`` to use Whisper.

    ``supported`` is the helper's list of locales the model covers. A locale
    is returned only when it is in that list, compared case-insensitively and
    with ``_`` and ``-`` equal.
    """
    if not ui_language or ui_language not in _DEFAULT_REGION:
        return None
    available = {_norm(s): s for s in supported}
    if ui_language in _REGION_REFINES and region:
        candidate = f"{ui_language}-{region.upper()}"
        if _norm(candidate) in available:
            return available[_norm(candidate)]
    default = _DEFAULT_REGION[ui_language]
    if default is None:
        return None
    return available.get(_norm(default))


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HelperProbe:
    """What ``bristlenose-speech probe`` reported."""

    available: bool
    reason: str | None = None
    os_version: str = ""
    supported: tuple[str, ...] = ()
    installed: tuple[str, ...] = ()


_probe_cache: dict[str, HelperProbe | None] = {}
_probe_lock = threading.Lock()


def helper_path() -> Path | None:
    """The bundled helper, when the Mac app named one that exists."""
    raw = os.environ.get(HELPER_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() and os.access(path, os.X_OK) else None


def probe_helper(path: Path, *, timeout: float = 20.0) -> HelperProbe | None:
    """Ask the helper what it can do. Cached per path for the process.

    ``None`` when the helper could not be asked at all (it crashed, timed out,
    or printed something we cannot read), which the caller treats as absent.
    """
    key = str(path)
    with _probe_lock:
        if key in _probe_cache:
            return _probe_cache[key]
    result: HelperProbe | None = None
    try:
        proc = subprocess.run(
            [str(path), "probe"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        line = next((ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")), "")
        data = json.loads(line) if line else None
        if isinstance(data, dict) and data.get("schema") == SCHEMA:
            result = HelperProbe(
                available=bool(data.get("available")),
                reason=data.get("reason"),
                os_version=str(data.get("os_version") or ""),
                supported=tuple(str(s) for s in data.get("supported") or ()),
                installed=tuple(str(s) for s in data.get("installed") or ()),
            )
        else:
            logger.warning("speech helper probe: unreadable output (exit %s)", proc.returncode)
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        logger.warning("speech helper probe failed: %s", type(exc).__name__)
    with _probe_lock:
        _probe_cache[key] = result
    return result


class HelperError(RuntimeError):
    """The helper ran and failed. ``exit_code`` follows the contract."""

    #: Exits about the engine, not the file: unavailable (3), locale not
    #: supported (4), model fetch failed (5). The next file would fail the same.
    ENGINE_EXITS = frozenset({3, 4, 5})

    def __init__(self, message: str, exit_code: int, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.timed_out = timed_out

    @property
    def engine_level(self) -> bool:
        return self.exit_code in self.ENGINE_EXITS


_PROGRESS_RE = re.compile(r"^@progress\s+([0-9.]+)\s+([0-9.]+)\s*$")


def run_helper(
    path: Path,
    wav: Path,
    locale: str,
    out_json: Path,
    *,
    on_progress: Callable[[float, float], None] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Transcribe ``wav`` under ``locale`` with the helper; return its JSON.

    ``on_progress(seconds_done, audio_s)`` is called for each ``@progress``
    line the helper writes to stderr. Raises :class:`HelperError` on a non-zero
    exit, with the helper's last stderr line (never transcript text: the
    helper writes none there).
    """
    proc = subprocess.Popen(
        [str(path), "transcribe", str(wav), locale, str(out_json)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    tail = ""
    timed_out = threading.Event()
    timer: threading.Timer | None = None

    def _expire() -> None:
        timed_out.set()
        proc.kill()

    if timeout is not None:
        timer = threading.Timer(timeout, _expire)
        timer.start()
    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.rstrip("\n")
            match = _PROGRESS_RE.match(line)
            if match:
                if on_progress is not None:
                    on_progress(float(match.group(1)), float(match.group(2)))
            elif line.strip():
                tail = line.strip()[:300]
        code = proc.wait()
    finally:
        if timer is not None:
            timer.cancel()
        # Any abnormal exit from the loop (a callback that raised, Ctrl-C)
        # must not leave the helper running and holding a locale reservation.
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if timed_out.is_set():
        raise HelperError(f"speech helper timed out after {timeout:.0f} s", code, timed_out=True)
    if code != 0:
        raise HelperError(f"speech helper exited {code}: {tail or 'no message'}", code)
    data = json.loads(out_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise HelperError("speech helper wrote an unexpected schema", 2)
    return data


# ---------------------------------------------------------------------------
# The engine decision (§1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineChoice:
    """Which engine a run uses, and why. ``locale`` is set only for Apple."""

    engine: str  # "apple" or "whisper"
    reason: str
    locale: str | None = None
    helper: Path | None = None

    @property
    def is_apple(self) -> bool:
        return self.engine == "apple"


def choose_engine(
    *,
    flag: bool,
    mode: str,
    helper: Path | None,
    probe: HelperProbe | None,
    whisper_on_disk: bool,
    whisper_language: str,
    ui_language: str | None,
    region: str | None,
    ui_language_matched: bool = True,
) -> EngineChoice:
    """Decide the engine for a run. Pure: every input is passed in.

    Apple only when all of §1's conditions hold; any one missing gives Whisper,
    with the reason (logged, never shown).
    """
    def whisper(reason: str) -> EngineChoice:
        return EngineChoice("whisper", reason)

    if not flag:
        return whisper("flag off")
    if mode == MODE_NEVER:
        return whisper("set to Whisper only")
    if helper is None:
        return whisper("no speech helper (not the Mac app)")
    if probe is None:
        return whisper("speech helper did not answer")
    if not probe.available:
        return whisper(f"speech helper unavailable: {probe.reason or 'no reason given'}")
    if mode != MODE_PREFER and whisper_on_disk:
        return whisper("Whisper is on disk")
    if (whisper_language or "auto").strip().lower() != "auto":
        return whisper("transcription language pinned")
    if not ui_language_matched:
        return whisper("UI language is a fallback, not the researcher's")
    locale = apple_locale_for(ui_language, region, probe.supported)
    if locale is None:
        return whisper(f"no Apple locale for UI language {ui_language!r}")
    return EngineChoice("apple", "first run", locale=locale, helper=helper)


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

#: A gap between words longer than this starts a new segment. Apple returns
#: whole utterances of a minute or more; stage 5b labels speakers per segment,
#: so a segment must not straddle a turn.
SEGMENT_GAP_S = 0.7

_SENTENCE_END_RE = re.compile(r"[.?!…。？！]['\"”’)\]]*\s*$")


@dataclass
class _Run:
    words: list[dict[str, Any]] = field(default_factory=list)


def _word_time(w: dict[str, Any], key: str) -> float | None:
    value = w.get(key)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def segments_from_helper(payload: dict[str, Any]) -> list[Any]:
    """Apple's results as ``TranscriptSegment``s, cut at pauses and sentence ends.

    Each segment carries its words (``source = "apple-speech"``). A result
    with no timed words becomes one segment of its text.
    """
    from bristlenose.models import TranscriptSegment, Word

    out: list[TranscriptSegment] = []

    def emit(words: list[dict[str, Any]]) -> None:
        text = "".join(str(w.get("text", "")) for w in words).strip()
        if not text:
            return
        word_models = []
        for w in words:
            t = str(w.get("text", "")).strip()
            if not t:
                continue
            conf = w.get("conf")
            word_models.append(Word(
                text=t,
                start_time=_word_time(w, "start") or 0.0,
                end_time=_word_time(w, "end") or 0.0,
                confidence=float(conf) if isinstance(conf, (int, float)) else 1.0,
            ))
        out.append(TranscriptSegment(
            start_time=_word_time(words[0], "start") or 0.0,
            end_time=_word_time(words[-1], "end") or 0.0,
            text=text,
            words=word_models,
            source=SOURCE,
        ))

    for result in payload.get("results") or []:
        words = [
            w for w in result.get("words") or []
            if _word_time(w, "start") is not None and _word_time(w, "end") is not None
        ]
        timed = "".join(str(w.get("text", "")) for w in words)
        whole = str(result.get("text", ""))
        if words and len("".join(timed.split())) < len("".join(whole.split())):
            # Counts only: the words are participant speech.
            logger.warning(
                "apple-speech result at %.1fs: %d of %d characters carry timings",
                _word_time(result, "start") or 0.0,
                len("".join(timed.split())), len("".join(whole.split())),
            )
        if not words:
            text = str(result.get("text", "")).strip()
            start, end = _word_time(result, "start"), _word_time(result, "end")
            if text and start is not None and end is not None:
                out.append(TranscriptSegment(
                    start_time=start, end_time=end, text=text, source=SOURCE,
                ))
            continue
        current: list[dict[str, Any]] = []
        for w in words:
            if current:
                gap = (_word_time(w, "start") or 0.0) - (_word_time(current[-1], "end") or 0.0)
                ends_sentence = bool(_SENTENCE_END_RE.search(str(current[-1].get("text", ""))))
                if gap > SEGMENT_GAP_S or ends_sentence:
                    emit(current)
                    current = []
            current.append(w)
        if current:
            emit(current)
    return out


# ---------------------------------------------------------------------------
# The gate (§2)
# ---------------------------------------------------------------------------

#: Mean word confidence under this means the model was not hearing its own
#: language (0.10–0.38 measured on a wrong locale, 0.92–0.93 on the right one;
#: ``transcription_quality.LOW_CONFIDENCE``). Five files: measure on more
#: before the flag comes off.
GATE_MIN_CONFIDENCE = 0.5
#: Words per minute of signal under this means it heard sound and wrote almost
#: nothing. Conversation runs 100–200; the wrong-locale files gave a few words.
GATE_MIN_WPM = 20.0
#: Too little signal to judge a words-per-minute rate.
_GATE_MIN_SIGNAL_MIN = 0.25


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    reason: str
    mean_confidence: float | None
    words: float
    signal_minutes: float

    def as_record(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "mean_confidence": (
                round(self.mean_confidence, 3) if self.mean_confidence is not None else None
            ),
            "words_per_signal_minute": (
                round(self.words / self.signal_minutes, 1) if self.signal_minutes > 0 else None
            ),
            "signal_minutes": round(self.signal_minutes, 2),
        }


def language_gate(
    payload: dict[str, Any],
    segments: Sequence[Any],
    signal_minutes: float,
) -> GateVerdict:
    """Did the assumed language hold for this whole file?

    ``payload`` is the helper's JSON (raw confidences, so a word Apple gave no
    confidence is left out rather than counted as sure); ``segments`` is what
    will be kept; ``signal_minutes`` is how much of the file had signal.
    """
    from bristlenose.stages.s06_merge_transcript import reading_length

    confs = [
        float(w["conf"])
        for r in payload.get("results") or [] for w in r.get("words") or []
        if isinstance(w.get("conf"), (int, float)) and math.isfinite(float(w["conf"]))
    ]
    mean = sum(confs) / len(confs) if confs else None
    words = float(sum(reading_length(s.text) for s in segments))

    def verdict(passed: bool, reason: str) -> GateVerdict:
        return GateVerdict(passed, reason, mean, words, signal_minutes)

    # Zero words over sound is "can't tell", however short the file: kept, it
    # would be cached as no speech and never reach Whisper. (`has_signal` has
    # already said there is sound, or the backend would not be asking.)
    if words == 0 and signal_minutes > 0:
        return verdict(False, "no words over speech")
    if mean is not None and mean < GATE_MIN_CONFIDENCE:
        return verdict(False, "low confidence")
    if signal_minutes >= _GATE_MIN_SIGNAL_MIN and words / signal_minutes < GATE_MIN_WPM:
        return verdict(False, "too few words for the speech heard")
    return verdict(True, "ok")


def signal_minutes(levels: Any) -> float:
    """Minutes of the file whose 100 ms windows clear the active-speech gate.

    The same gate the skipped-window net uses: 15 dB over the quietest tenth,
    with that floor capped at -45 dBFS so a file loud throughout is not blind.
    """
    import numpy as np

    from bristlenose.transcription_quality import LEVEL_WINDOWS_PER_SECOND, noise_floor_dbfs

    arr = np.asarray(levels, dtype=np.float64)
    if not arr.size:
        return 0.0
    floor = noise_floor_dbfs(levels)
    gate = (min(floor, -45.0) + 15.0) if floor is not None else -60.0
    active = int(np.sum(np.isfinite(arr) & (arr >= gate)))
    return active / LEVEL_WINDOWS_PER_SECOND / 60.0
