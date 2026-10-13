"""How well each recording transcribed: one record per session, numbers only.

Stage 5 knows things about a recording it used to log and throw away: how loud
it was, how often Whisper had to retry a window, what the nets repaired. This
module turns them into one JSON record per session, written to
``.bristlenose/intermediate/transcription-quality/<sid>.json`` and read by the
Sessions grid's diagnostics block (``docs/design-transcription-quality.md``).

The record carries **no words and no names**. Two parts carry times: the spans
where speech may be missing (``repair.found`` / ``repair.still_empty``, which
the grid turns into "listen at" timecodes) and the 10-second ``series``. Both
stay on this machine; a consented telemetry form, when one exists, sends
``summary(record)`` only, which drops both.

Measures are deliberately plain: none of them knows what was said, so none is
an accuracy score. They say where a transcript deserves a listen.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Bump when a field changes meaning. A reader shows nothing for a version it
#: does not know rather than mislabelling it.
RECORD_VERSION = 1

#: The groups a telemetry payload may carry; ``series`` is left out.
SUMMARY_GROUPS = ("audio", "recognition", "repair", "text")

#: Fields inside those groups that are a timeline of the recording, not a count.
_TIMELINE_FIELDS = ("found", "still_empty")

#: The 10-second bins of ``series``.
SERIES_BIN_S = 10

#: The signal gate's 100 ms windows (``s05_transcribe._LEVEL_WINDOWS_PER_SECOND``;
#: a test holds the two equal).
LEVEL_WINDOWS_PER_SECOND = 10

#: A word Whisper gave under this probability counts as doubtful.
LOW_CONFIDENCE = 0.5

#: Marks that end a stretch of words for the longest-unpunctuated measure.
_PUNCT_SPLIT = re.compile(r"[.,?!;:…。、，！？；：]+")

_SENTENCE_END = re.compile(r"[。？！]+|[.?!…؟]+(?=[\"'”’)\]]*(?:\s|$))")

_DIRNAME = "transcription-quality"


def record_dir(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "intermediate" / _DIRNAME


def write_record(output_dir: Path, session_id: str, record: dict[str, Any]) -> None:
    """Write one session's record. Best effort: a failure is logged, never raised."""
    try:
        d = record_dir(output_dir)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".{session_id}.json.tmp"
        tmp.write_text(json.dumps(record, ensure_ascii=True, allow_nan=False), encoding="utf-8")
        tmp.replace(d / f"{session_id}.json")
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("%s: transcription quality record not written (%s)", session_id, exc)


def remove_record(output_dir: Path, session_id: str) -> None:
    """Remove a session's record, so the grid never shows numbers about a transcript
    that no longer stands (a platform file replaced Whisper, or re-transcription
    failed). Best effort."""
    try:
        (record_dir(output_dir) / f"{session_id}.json").unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("%s: stale transcription quality record not removed (%s)", session_id, exc)


def read_records(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Every readable record of the current version, keyed by session id."""
    d = record_dir(output_dir)
    out: dict[str, dict[str, Any]] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("transcription quality record unreadable: %s", p.name)
            continue
        if isinstance(rec, dict) and rec.get("version") == RECORD_VERSION:
            out[p.stem] = rec
        else:
            logger.info("transcription quality record %s skipped: version %r, want %d",
                        p.name, rec.get("version") if isinstance(rec, dict) else None,
                        RECORD_VERSION)
    return out


def summary(record: dict[str, Any]) -> dict[str, Any]:
    """The record without anything that places events in time.

    What a consented telemetry payload may carry: counts and levels only. The
    gap spans and the 10-second series are a timeline of one participant's
    recording and stay on this machine.
    """
    out: dict[str, Any] = {"version": record.get("version")}
    for group in SUMMARY_GROUPS:
        value = record.get(group)
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in _TIMELINE_FIELDS}
        out[group] = value
    return out


def _round(x: float, n: int = 1) -> float:
    return round(float(x), n)


def noise_floor_dbfs(levels: Any) -> float | None:
    """The quietest tenth of the recording's 100 ms windows, in dBFS."""
    import numpy as np

    arr = np.asarray(levels, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if not finite.size:
        return None
    return float(np.percentile(finite, 10))


def audio_measures(audio: Any, levels: Any, *, active_over_dbfs: float) -> dict[str, Any]:
    """Noise floor, peak, share of windows with sound, share of clipped samples.

    ``active_over_dbfs`` is the level a window must exceed to count as sound —
    the skipped-window net's own threshold, so "sound" means here what it
    means there.
    """
    import numpy as np

    arr = np.asarray(levels, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    samples = np.asarray(audio, dtype=np.float32).ravel()
    floor = noise_floor_dbfs(arr)
    return {
        "floor_dbfs": None if floor is None else _round(floor),
        "peak_dbfs": _round(float(np.max(finite))) if finite.size else None,
        "active_share": _round(float(np.mean(arr > active_over_dbfs)), 3) if arr.size else 0.0,
        "clipped_share": (
            round(float(np.mean(np.abs(samples) >= 0.999)), 5) if samples.size else 0.0
        ),
    }


def _reading_length(text: str) -> float:
    from bristlenose.stages.s06_merge_transcript import reading_length

    return float(reading_length(text))


def text_measures(segments: Sequence[Any], duration_s: float) -> dict[str, Any]:
    """Words, pace, sentence ends and the longest unpunctuated run.

    Lengths are counted as the paragraph rule counts them (a no-space character
    is 0.4 of a word), so Japanese reads in the same units as English.
    ``segments`` are ``TranscriptSegment``s; inaudible gaps are skipped.
    """
    texts = [s.text for s in segments if not getattr(s, "inaudible", False) and s.text]
    joined = " ".join(texts)
    words = sum(_reading_length(t) for t in texts)
    # Counted inside segments, which often hold several sentences. A Latin
    # mark counts only before a space or the end ("3.5" is not an end); a CJK
    # one always does, since those scripts put no space after it.
    sentence_ends = len(_SENTENCE_END.findall(joined))
    runs = [_reading_length(p) for p in _PUNCT_SPLIT.split(joined)] if joined else [0.0]
    minutes = duration_s / 60 if duration_s > 0 else 0
    return {
        "words": round(words),
        "wpm": round(words / minutes) if minutes else 0,
        "sentence_ends_per_100": _round(100 * sentence_ends / words) if words else 0.0,
        "longest_unpunctuated": round(max(runs)),
        "segments": len(texts),
    }


def confidence_measures(segments: Sequence[Any]) -> dict[str, Any]:
    """Mean word confidence, the share under `LOW_CONFIDENCE`, and a 10-bin histogram."""
    import math

    confs = [
        c for s in segments for w in (getattr(s, "words", None) or [])
        if math.isfinite(c := float(w.confidence))
    ]
    hist = [0] * 10
    for c in confs:
        hist[min(9, max(0, int(c * 10)))] += 1
    return {
        "mean_confidence": _round(sum(confs) / len(confs), 3) if confs else None,
        "low_confidence_share": (
            _round(sum(c < LOW_CONFIDENCE for c in confs) / len(confs), 3) if confs else None
        ),
        "confidence_hist": hist,
    }


def series(
    segments: Sequence[Any], levels: Any | None, duration_s: float,
) -> dict[str, Any]:
    """Per 10 s: the loudest tenth's level, words a minute, share of doubtful words.

    A segment's words are spread over the bins it covers, as the trials'
    lost-speech count does, so a long segment does not credit one bin with
    everything. ``low_conf`` is null for a bin with no timed words.
    """
    import numpy as np

    n = max(1, int(np.ceil(duration_s / SERIES_BIN_S))) if duration_s > 0 else 0
    words = [0.0] * n
    low = [0] * n
    timed = [0] * n
    for s in segments:
        if getattr(s, "inaudible", False) or not s.text:
            continue
        a, b = float(s.start_time), max(float(s.end_time), float(s.start_time) + 0.01)
        count = _reading_length(s.text)
        k = int(a // SERIES_BIN_S)
        while k < n and k * SERIES_BIN_S < b:
            share = (min(b, (k + 1) * SERIES_BIN_S) - max(a, k * SERIES_BIN_S)) / (b - a)
            words[k] += count * share
            k += 1
        for w in getattr(s, "words", None) or []:
            k = min(n - 1, int(float(w.start_time) // SERIES_BIN_S))
            if k >= 0:
                timed[k] += 1
                low[k] += float(w.confidence) < LOW_CONFIDENCE
    level_p90: list[float | None] = []
    if levels is not None:
        arr = np.asarray(levels, dtype=np.float64)
        per = SERIES_BIN_S * LEVEL_WINDOWS_PER_SECOND
        for k in range(n):
            chunk = arr[k * per:(k + 1) * per]
            chunk = chunk[np.isfinite(chunk)]
            level_p90.append(_round(float(np.percentile(chunk, 90))) if chunk.size else None)
    return {
        "bin_s": SERIES_BIN_S,
        "level_p90": level_p90,
        "wpm": [round(w * 60 / SERIES_BIN_S) for w in words],
        "low_conf": [_round(lo / t, 2) if t else None for lo, t in zip(low, timed, strict=True)],
    }


def gap_measures(segments: Sequence[Any]) -> dict[str, Any]:
    gaps = [s for s in segments if getattr(s, "inaudible", False)]
    return {
        "inaudible_gaps": len(gaps),
        "inaudible_seconds": _round(sum(s.end_time - s.start_time for s in gaps)),
    }


def spans(pairs: Iterable[tuple[float, float]]) -> list[list[float]]:
    return [[_round(a), _round(b)] for a, b in pairs]


def build_record(
    *,
    session_id: str,
    duration_s: float,
    segments: Sequence[Any],
    recognition: dict[str, Any],
    repair: dict[str, Any] | None = None,
    audio: dict[str, Any] | None = None,
    levels: Any | None = None,
) -> dict[str, Any]:
    """Assemble one session's record.

    ``recognition`` and ``repair`` come from the backend (what it did);
    everything else is measured here from the finished segments, so both
    backends describe their output the same way. A backend that measures no
    audio levels (faster-whisper) leaves ``audio`` null.
    """
    rec_recognition = {**recognition, **confidence_measures(segments)}
    rec_repair = {**(repair or {}), **gap_measures(segments)}
    return {
        "version": RECORD_VERSION,
        "session_id": session_id,
        "duration_s": _round(duration_s),
        "audio": audio,
        "recognition": rec_recognition,
        "repair": rec_repair,
        "text": text_measures(segments, duration_s),
        "series": series(segments, levels, duration_s),
    }
