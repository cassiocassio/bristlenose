"""Stage 5: Speech-to-text transcription.

Automatically selects the best backend for the current hardware:
- Apple Silicon (M1/M2/M3/M4 and all variants): mlx-whisper via Metal GPU
- NVIDIA GPU: faster-whisper via CUDA
- CPU fallback: faster-whisper with INT8 quantization

The backend can be overridden via settings.whisper_backend.
"""

from __future__ import annotations

import asyncio
import contextvars
import importlib
import logging
import re
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from bristlenose.config import BristlenoseSettings
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    StageFailure,
    StageOutcome,
)
from bristlenose.models import InputSession, TranscriptSegment, Word
from bristlenose.run_lifecycle import categorise_exception
from bristlenose.utils.hardware import AcceleratorType, HardwareInfo, detect_hardware

logger = logging.getLogger(__name__)


# English interjections / discourse markers that double naturally in real
# speech ("No. No. No." Thatcher, "yeah yeah", "very very good"). Repeats of
# these at the unigram level are protected. Phrase-level repeats (>=2 tokens)
# are never natural — those collapse regardless.
_REDUPLICABLE = frozenset([
    "yes", "yeah", "yep", "yup", "mhm",
    "no", "nope", "nah",
    "okay", "ok", "oh", "ah", "hmm", "uh", "um", "er",
    "well", "so", "right", "sure", "fine", "true",
    "wow", "hey", "now", "then",
    "very", "really", "much",
    "here", "there",
])


def _is_reduplicable(token: str) -> bool:
    """A token reduplicates naturally if its lowercased alpha core is listed."""
    core = "".join(c for c in token.lower() if c.isalpha())
    return core in _REDUPLICABLE


def collapse_adjacent_repeats(text: str) -> str:
    """Collapse adjacent identical n-gram repetitions in transcript text.

    Targets two sources: Whisper hallucination ("thanks thanks thanks",
    "Thank you. Thank you.", "facebook facebook") and content-word
    doubling that's almost always an artefact ("crockpot crockpot"). Real
    speech doubles interjections / discourse markers ("No. No. No.",
    "yeah yeah", "very very good") — those are protected by the
    ``_REDUPLICABLE`` set.

    Algorithm walks n-gram lengths 8 → 1 so longer matches win first.
    Threshold: phrase-level (n>=2) collapses at any adjacent repeat;
    single-token (n=1) collapses at 2+ for content words, 6+ for
    interjections (covers extreme Whisper loops without touching natural
    emphasis).
    """
    tokens = text.split()
    for n in range(8, 0, -1):
        i = 0
        out: list[str] = []
        while i < len(tokens):
            if i + n > len(tokens):
                out.append(tokens[i])
                i += 1
                continue
            ngram = tokens[i:i + n]
            run_end = i + n
            while run_end + n <= len(tokens) and tokens[run_end:run_end + n] == ngram:
                run_end += n
            run_count = (run_end - i) // n
            # If every token is a natural-reduplication interjection, treat
            # the run as protected speech regardless of n-gram length —
            # otherwise the n=2 pass would eat "no no no no" pairwise before
            # the n=1 protection could apply.
            if all(_is_reduplicable(t) for t in ngram):
                threshold = 6
            else:
                threshold = 2
            if run_count >= threshold:
                out.extend(ngram)
                i = run_end
            else:
                out.append(tokens[i])
                i += 1
        tokens = out
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Signal gate — Whisper invents speech over silence
# ---------------------------------------------------------------------------
#
# Given a recording with no signal in it, Whisper does not return nothing: it
# returns "Thank you." once per 30-second window. Measured 27 Sep 2026 on four
# 29-minute videos whose audio track was digital zero — 58, 66, 52 and 62
# invented lines, which the pipeline then analysed as interviews.
#
# Whisper has a guard for this and it does not work on the model we ship. The
# `no_speech_prob` behind `no_speech_threshold` is read from the `<|nospeech|>`
# logit, and large-v3-turbo (the default) reports 0.0 for it on everything:
# digital silence, and all 673 segments of two real interviews. whisper-tiny,
# on the same silent minute, reports 0.94. So the threshold below is inert on
# the default model and no amount of tuning it helps.
#
# faster-whisper is unaffected — its `vad_filter` strips silence first and
# returns 0 segments on the same file. mlx has no VAD, and the sidecar excludes
# onnxruntime (and faster_whisper), so Silero is not available on the Mac. What
# is always available is the signal itself: the gate below needs nothing but
# the samples mlx decodes anyway.
#
# A session this gate empties reaches the orchestrator with zero segments,
# which already has a stated outcome — `UnusableReason.NO_SPEECH`, "No speech
# found — nothing was said in this recording." (pipeline.py). No new message.
#
# Scope: *no signal*, not *no speech*. Room tone, music or a hum all pass, so
# Whisper can still hallucinate over them. The gate fails open by design — a
# kept hallucination is visible and deletable; a dropped word is not.

#: Whisper's sample rate, which both backends decode to.
_SAMPLE_RATE = 16000

#: 100 ms windows at Whisper's 16 kHz sample rate.
_LEVEL_WINDOW_SAMPLES = 1600
_LEVEL_WINDOWS_PER_SECOND = 10

#: The loudest 100 ms window must reach this for there to be anything to hear.
#: Measured margins over two real interviews (a Teams and a Meet recording, 669
#: segments with text), at the ±2 s pad below: the quietest peaks at -40.1 dBFS
#: (the early-stamped "drainer"), the next at -28.3. Their room tone sits at
#: -71 to -87. Digital silence is -inf. So ~20 dB of margin either side.
_SIGNAL_FLOOR_DBFS = -60.0

#: Segment timestamps drift from the audio they describe. One real word
#: ("drainer") was stamped ~1.2 s before the speech it came from, so ±0.5 s
#: would have dropped it (-73 dBFS); ±2 s keeps it at -40. Wider is the safe
#: direction — it can only keep more.
_SEGMENT_PAD_S = 2.0


def window_levels_dbfs(audio: object) -> object:
    """RMS level of each 100 ms window, in dBFS (digital silence → -inf).

    ``audio`` is mono float samples at 16 kHz, full scale ±1.0 — the shape
    both Whisper backends decode to. Returns a 1-D numpy array.
    """
    import numpy as np

    samples = np.asarray(audio, dtype=np.float32).ravel()
    n = len(samples) // _LEVEL_WINDOW_SAMPLES
    if n == 0:
        # Shorter than one window: treat the whole thing as one.
        samples = samples if len(samples) else np.zeros(1, dtype=np.float32)
        frames = samples.reshape(1, -1)
    else:
        frames = samples[: n * _LEVEL_WINDOW_SAMPLES].reshape(n, _LEVEL_WINDOW_SAMPLES)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(rms)


def has_signal(levels: object) -> bool:
    """True when any window of the recording reaches the signal floor."""
    import numpy as np

    arr = np.asarray(levels)
    return bool(arr.size) and bool(np.max(arr) >= _SIGNAL_FLOOR_DBFS)


def segment_has_signal(start: float, end: float, levels: object) -> bool:
    """True when the padded span of a segment reaches the signal floor."""
    import numpy as np

    arr = np.asarray(levels)
    i0 = max(0, int((start - _SEGMENT_PAD_S) * _LEVEL_WINDOWS_PER_SECOND))
    i1 = min(len(arr), int(np.ceil((end + _SEGMENT_PAD_S) * _LEVEL_WINDOWS_PER_SECOND)) + 1)
    if i1 <= i0:
        # Timestamps past the end of the audio — nothing to judge by, so keep.
        return True
    return bool(np.max(arr[i0:i1]) >= _SIGNAL_FLOOR_DBFS)


# ---------------------------------------------------------------------------
# Style prompt — punctuation and casing on every window
# ---------------------------------------------------------------------------
#
# Whisper copies the style of the text it is prompted with. On mlx, with
# `condition_on_previous_text=False` (set in `_init_mlx_backend` to break
# repetition loops) each 30 s window is decoded with no prompt at all, so each
# window picks a style afresh — and on filler-heavy conversation it often picks lower case with no
# punctuation. Measured on an 18-minute interview (docs/design-transcript-
# readability.md §2.3): 72 sentences, a 681-word unpunctuated run, 96 of 172
# "I"s lower-case; and no full stop at all in a Japanese file. mlx's
# `initial_prompt` reaches only the first window on these settings.
#
# So the decode step gets the prompt for the language mlx has decided on, on
# every window and every fallback temperature (`_install_style_prompt_hook`). Measured with three seeds each:
# 267–286 sentences, longest unpunctuated run 24–31 words, no lower-case "I",
# and fewer windows falling back to sampling (5–21 against 92–123); Japanese
# 20–25 full stops against 0. The prompt holds fillers on purpose: a prompt
# without them makes Whisper drop "um" and "uh", and quotes need the verbatim.
#
# faster-whisper keeps `condition_on_previous_text` on, so one unpunctuated
# window locks the style for the rest of the file: a 5-minute English excerpt
# came back with no sentence end at all and every "I" lower-case. Its
# `hotwords` reaches every window by design, so the same prompt goes there:
# 49 sentences, no lower-case "I", longest unpunctuated run 31 words.
#
# Rules for adding a language: fillers in; nothing a moderator would say (an
# interview phrase in the prompt was the one leak seen, "Tell me about it." x4);
# the language's own punctuation; measured on a real recording first. A
# language not listed gets no prompt, which is how every language ran before.
# Chinese is deliberately absent: the prompt's script would decide whether the
# transcript comes out Simplified or Traditional, and that is a product call.
#
# Spanish, French, Italian and German (13 Oct 2026) were measured on mlx over
# sixteen public recordings, interviews and covert conversations
# (docs/design-whisper-style-prompts.md). The first prompts for Spanish and
# Portuguese ended on lone assent words ("Vale.", "Certo.") and Whisper handed
# them back over speech it skipped; these keep the fillers, carry no standalone
# assent word, and end on a hedging clause. On the two Spanish conversations
# with reference transcripts, word error rate fell 42.7% -> 35.7% and 58.4% ->
# 42.9% with the prompt (42.0% once the skipped-window net was added). Portuguese followed once the inaudible
# marker and loop removal were in: on three interviews (Brazil, Portugal,
# Angola) it loses no more speech than Spanish, and the recording that had held
# it back was a street recording Whisper hears 73 words of in 17 minutes. Its
# fillers sound Brazilian ("né", "ahn"), and Whisper has one code for both
# varieties; European Portuguese gains least. faster-whisper sends none of these
# (`FASTER_WHISPER_PROMPT_LANGUAGES` below).
STYLE_PROMPTS: dict[str, str] = {
    "en": "Hmm, okay. Well, yes, I suppose so, um, and then? Right.",
    "ja": "えーと、はい。そうですね、なるほど。",
    "es": "Eeh, pues, mm, la verdad es que sí, ¿no? Eh, más o menos, porque, mm, depende.",
    "fr": "Euh, bon, je pense que oui. Mais ça dépend, hein. Et alors ? Je ne sais pas trop.",
    "it": "Ehm, allora, mh, in realtà sì, no? Eh, più o meno, perché, ehm, dipende.",
    "de": "Ähm, ja. Also, ich denke schon, äh, und dann? Genau.",
    "pt": "Ahn, então, hum, na verdade é isso, né? Eh, mais ou menos, porque, ahn, depende.",
    # Waves 1 and 2 (13 Oct 2026), fifteen recordings: in Catalan, Danish,
    # Norwegian and Swedish the longest unpunctuated run fell on every
    # recording that had one to fix (sv-1 133 -> 25, da-3 200 -> 14).
    # Catalan takes v2: v1 swallowed a 15 s passage and handed back its
    # own "No ho sé, depèn." Dutch gets none on purpose: it came back punctuated
    # without a prompt, and both prompts made some recordings worse.
    # Norwegian is Whisper's "no" (Bokmål); Nynorsk ("nn") is left out.
    "ca": "Eh, doncs, mm, la veritat és que sí, no? Eh, més o menys, perquè, em, depèn.",
    "sv": "Ehm, alltså, jag tänker väl så, eh, och sen då? Det beror lite på, liksom.",
    "da": "Øh, altså, jeg tror nok det, øh, og hvad så? Det kommer lidt an på.",
    "no": "Ehm, altså, jeg tror vel det, eh, og hva da? Det kommer litt an på, liksom.",
    # Waves 3 and 4 (13 Oct 2026), 21 recordings. Turkish (v2) and Korean (v1)
    # gain: longest unpunctuated run 63 -> 21 and 74 -> 14, at two seeds. Korean
    # drops one quiet off-mic question in a press Q&A, unmarked: it sits below
    # the skipped-window net's level gate. Polish, Czech, Russian, Ukrainian and
    # Finnish get none ON PURPOSE: Whisper already punctuates them (longest runs
    # 17-53 words with no prompt); Polish, Czech and Finnish gained nothing, and
    # Russian and Ukrainian lost real speech (Ukrainian v1 5 blocks of uk-3).
    # In these trials the languages that gained were the ones whose unprompted
    # output ran on for long stretches; that is a description of three
    # recordings a language, not a rule (Dutch and Russian each had one
    # recording past 50 words and still got nothing reliable from a prompt).
    "tr": "Eee, yani, ııı, aslında öyle, değil mi? Şey, bilmiyorum, ııı, biraz duruma bağlı.",
    "ko": "음, 그러니까, 저는 그렇게 생각해요. 근데 어, 잘 모르겠어요, 좀 상황에 따라 다른 것 같아요.",
}


#: Whisper also accepts a language by name; a pinned ``--whisper-language
#: English`` must reach the same prompt as ``en``.
_LANGUAGE_NAMES: dict[str, str] = {
    "english": "en", "japanese": "ja", "spanish": "es", "castilian": "es",
    "french": "fr", "italian": "it", "german": "de", "portuguese": "pt",
    "catalan": "ca", "valencian": "ca", "swedish": "sv", "danish": "da",
    "norwegian": "no", "turkish": "tr", "korean": "ko",
}


def _language_code(language: str | None) -> str:
    code = (language or "").strip().lower()
    return _LANGUAGE_NAMES.get(code, code)


def style_prompt_for(language: str | None) -> str | None:
    """The style prompt for a Whisper language code or name, or None."""
    return STYLE_PROMPTS.get(_language_code(language))


#: faster-whisper (Linux, Windows) gets a prompt only where one was measured ON
#: faster-whisper. Every other prompt was measured on mlx, with nets around it
#: that faster-whisper does not have (echo filter, inaudible marker, loop
#: removal, skipped-window net), and it keeps `condition_on_previous_text` on,
#: so a leaked fragment would become context for the windows after it.
FASTER_WHISPER_PROMPT_LANGUAGES = frozenset({"en", "ja"})


def _prompt_core(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def is_prompt_echo(text: str, prompt: str) -> bool:
    """True when ``text`` is nothing but the whole prompt, once or repeated.

    Whisper can hand a prompt back as speech. Only the whole prompt counts:
    its parts ("Right.", "Hmm, okay.") are things people say, so a segment
    holding one of them, or the prompt plus anything else, is kept — a kept
    echo is visible and deletable, a dropped word is not.
    """
    core, unit = _prompt_core(text), _prompt_core(prompt)
    if not core or not unit or len(core) % len(unit):
        return False
    return core == unit * (len(core) // len(unit))


#: Measured 12 Oct 2026 on seven recordings in six languages
#: (docs/design-whisper-style-prompts.md): every line made mostly of prompt
#: words with a mean word confidence under 0.15 was a partial echo ("Ainda,
#: hum, na verdade." at 0.02); real speech made of the same words ("Ähm,
#: genau." 0.75, "Okay. Uh, right." 0.97) sat far above it.
_GUESS_PROMPT_SHARE = 0.6
_GUESS_MAX_CONFIDENCE = 0.15


def _word_keys(text: str) -> list[str]:
    return [k for k in (re.sub(r"[\W_]+", "", w.casefold()) for w in text.split()) if k]


def is_prompt_guess(text: str, prompt: str, confidences: list[float]) -> bool:
    # Words are split on spaces, so in Japanese (a whole line is one "word")
    # this never fires: inert there, by measurement rather than design, until
    # a character-level version is calibrated on real Japanese echoes.
    """True when ``text`` is a partial echo of the prompt Whisper barely believed.

    `is_prompt_echo` catches the whole prompt handed back. This catches the
    pieces: a line of at least two words, most of them the prompt's own,
    decoded with a mean word confidence under `_GUESS_MAX_CONFIDENCE`. Either
    condition alone is ordinary speech — people say "um, right", and noisy
    recordings are full of low-confidence lines — so both must hold.
    """
    words = _word_keys(text)
    if len(words) < 2 or not confidences:
        return False
    vocab = set(_word_keys(prompt))
    share = sum(w in vocab for w in words) / len(words)
    mean = sum(confidences) / len(confidences)
    return share >= _GUESS_PROMPT_SHARE and mean < _GUESS_MAX_CONFIDENCE


#: A run of consecutive segments with the same text is a Whisper loop, never
#: speech, when it is this long, or this many spread over this many seconds.
#: Measured 12 Oct 2026 on the twenty trial recordings (docs/design-whisper-
#: style-prompts.md): loops ran 3-39 lines ("Gracias." three times over 60 s,
#: "nada" 39 times in 29 s), while real repeated backchannel stayed tight
#: ("Sim." four times in 2.4 s, "¡No!" six times in 6 s). Pairs are left
#: alone: 202 of them, many real ("no", "¿Ya ves?").
_LOOP_MIN_LINES = 3
_LOOP_MIN_SPAN_S = 15.0
_LOOP_ALWAYS_LINES = 8


def find_segment_loops(segs: list[tuple[float, float, str]]) -> list[tuple[int, int]]:
    """Runs ``[i, j)`` of consecutive segments that are one Whisper loop.

    ``collapse_adjacent_repeats`` catches a loop inside one segment; this one
    catches it spread across many, which that never sees ("nada" as 39
    separate one-word lines). Text is compared as the reader gets it, repeats
    collapsed, on its letters and digits, so "Gracias.", "gracias" and "nada
    nada" against "nada" are each one line.
    """
    keys = [_prompt_core(collapse_adjacent_repeats(text.strip())) for _, _, text in segs]
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(segs):
        key = keys[i]
        j = i + 1
        while key and j < len(segs) and keys[j] == key:
            j += 1
        n, span = j - i, segs[j - 1][1] - segs[i][0]
        if key and n >= _LOOP_MIN_LINES and (n >= _LOOP_ALWAYS_LINES or span >= _LOOP_MIN_SPAN_S):
            runs.append((i, j))
        i = j
    return runs


def _is_guess_segment(seg: dict[str, Any], prompt: str) -> bool:
    text = collapse_adjacent_repeats(str(seg.get("text", "")).strip())
    probs = [float(w.get("probability", 1.0)) for w in seg.get("words", [])]
    return is_prompt_guess(text, prompt, probs)


def drop_segment_loops(
    segs: list[dict[str, Any]], prompt: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Whisper segments without the loops `find_segment_loops` finds, and how
    many segments went.

    With ``prompt``, a loop made entirely of prompt guesses ("Ainda, hum, na
    verdade." three times at 0.02) is left in place: the inaudible marker turns
    it into a gap, where dropping it would leave the stretch silently empty when
    the skipped-window net cannot recover it.
    """
    loops = [
        (i, j) for i, j in find_segment_loops([
            (float(x.get("start", 0.0)), float(x.get("end", 0.0)), str(x.get("text", "")))
            for x in segs
        ])
        if not (prompt and all(_is_guess_segment(segs[k], prompt) for k in range(i, j)))
    ]
    looped = {k for i, j in loops for k in range(i, j)}
    return [x for k, x in enumerate(segs) if k not in looped], len(looped)


#: True only inside our own `mlx_whisper.transcribe` call, so the hook below
#: changes nothing for any other caller, in this thread or another.
_STYLE_PROMPT_ON: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "bristlenose_style_prompt_on", default=False,
)
_hook_state: dict[str, bool] = {}
#: Decode steps built and filled inside our calls, for the per-file log line
#: that shows the prompt really reached the decoder.
_hook_counts: dict[str, int] = {"built": 0, "filled": 0}


def _install_style_prompt_hook() -> bool:
    """Make mlx's decode step carry the style prompt. True when installed.

    `mlx_whisper.transcribe.transcribe` builds a fresh ``DecodingOptions`` for
    every window and every fallback temperature, looking the name up in its
    own module, after it has settled the language. Rebinding that name to a
    factory that fills an EMPTY ``prompt`` reaches every window without
    patching source — which matters because the Mac sidecar ships no ``.py``
    source to patch. A non-empty prompt (conditioning on previous text, or a
    caller's own ``initial_prompt``) is left alone.

    Fails open: if mlx-whisper's shape has moved, log once and transcribe as
    before. ``tests/test_transcribe.py`` pins the shape so an upgrade that
    moves it fails there first.
    """
    if "ok" in _hook_state:
        return _hook_state["ok"]
    try:
        module = importlib.import_module("mlx_whisper.transcribe")
        original = module.DecodingOptions
        if getattr(original, "_bristlenose_style_prompt", False):
            _hook_state["ok"] = True
            return True
        if "prompt" not in getattr(original, "__dataclass_fields__", {}):
            raise AttributeError("DecodingOptions has no prompt field")
    except (ImportError, AttributeError) as exc:
        logger.warning("Style prompt not applied: mlx-whisper not as expected (%s)", exc)
        _hook_state["ok"] = False
        return False

    def decoding_options(*args: object, **kwargs: object) -> object:
        if _STYLE_PROMPT_ON.get():
            _hook_counts["built"] += 1
            if not kwargs.get("prompt"):
                language = kwargs.get("language")
                prompt = style_prompt_for(language if isinstance(language, str) else None)
                if prompt:
                    kwargs["prompt"] = prompt
                    _hook_counts["filled"] += 1
        return original(*args, **kwargs)

    setattr(decoding_options, "_bristlenose_style_prompt", True)  # noqa: B010 (mypy: a function has no such attribute)
    setattr(module, "DecodingOptions", decoding_options)  # noqa: B010 (mypy: mlx is untyped)
    _hook_state["ok"] = True
    return True


# ---------------------------------------------------------------------------
# Skipped-window net — speech Whisper jumped over
# ---------------------------------------------------------------------------
#
# Whisper sometimes skips a stretch of real speech: it returns nothing for it,
# or one long segment holding a word or two ("Tr", "Certo." over half a minute),
# and carries on after it. Measured 12 Oct 2026 on twelve public interviews in
# five languages (docs/design-whisper-style-prompts.md): it happens with no
# prompt at all (a Portugal meeting, an Italian and a German interview, a
# Mexican podcast each lost a stretch that another run heard at 2-5 words a
# second), and more often under a style prompt in Spanish and Portuguese.
#
# The audio levels we already compute say where there is sound. A stretch of
# at least `_SKIP_MIN_S` with fewer than `_SKIP_SLOW_WPS` words a second, where
# at least `_SKIP_ACTIVE_FRACTION` of the 100 ms windows sit `_SKIP_OVER_FLOOR_DB`
# above the recording's own noise floor, is re-decoded on its own, without the
# style prompt. The new text replaces the old only if it reaches
# `_RECOVER_MIN_WPS` words a second — real speech, not one invented "Thank
# you." over music — so the net can only add speech, never lose any.
SKIP_NET_ENABLED = True
_SKIP_MIN_S = 8.0
_SKIP_SLOW_WPS = 0.3
_SKIP_OVER_FLOOR_DB = 15.0
_SKIP_ACTIVE_FRACTION = 0.4
_RECOVER_MIN_WPS = 1.0
#: The noise floor is the quietest tenth of the recording, but never above this:
#: a file that is loud throughout (wall-to-wall talk, a café) has no quiet tenth,
#: and a floor at speech level would make the net blind exactly where skips are
#: likeliest. Most measured floors sat at -45 to -49 dBFS.
_SKIP_FLOOR_CAP_DBFS = -45.0


def find_skipped_stretches(
    spans: list[tuple[float, float, float]],
    levels: object,
    total_s: float,
) -> list[tuple[float, float]]:
    """Stretches with sound and almost no words: ``(start, end)`` in seconds.

    ``spans`` are a transcript's segments as ``(start, end, word_count)``.
    A segment slower than `_SKIP_SLOW_WPS` words a second counts as uncovered,
    so one long near-empty segment is caught as well as a gap between two.
    """
    import numpy as np

    arr = np.asarray(levels, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if not finite.size:
        return []
    floor = min(float(np.percentile(finite, 10)), _SKIP_FLOOR_CAP_DBFS)
    active = arr > floor + _SKIP_OVER_FLOOR_DB
    covered = sorted(
        (a, b) for a, b, n in spans if n / max(b - a, 0.01) >= _SKIP_SLOW_WPS
    )
    found: list[tuple[float, float]] = []
    t = 0.0
    for a, b in [*covered, (total_s, total_s)]:
        if a - t >= _SKIP_MIN_S:
            window = active[int(t * _LEVEL_WINDOWS_PER_SECOND):int(a * _LEVEL_WINDOWS_PER_SECOND)]
            if window.size and float(np.mean(window)) >= _SKIP_ACTIVE_FRACTION:
                found.append((t, a))
        t = max(t, b)
    return found


#: ``(files_done, files_total)``, called after each file.
ProgressCallback = Callable[[int, int], None]
#: ``(file_index, file_total, seconds_done, file_seconds)``, called within a file.
SegmentCallback = Callable[[int, int, float, float], None]
#: ``(seconds_done, file_seconds)``: the per-file heartbeat a backend calls.
FileSegmentCallback = Callable[[float, float], None]


class TranscribeFn(Protocol):
    """A transcription backend, as returned by the ``_init_*_backend`` functions."""

    def __call__(
        self,
        audio_path: Path,
        settings: BristlenoseSettings,
        on_segment: FileSegmentCallback | None = None,
    ) -> tuple[list[TranscriptSegment], str | None]: ...


def _needs_transcription(sessions: list[InputSession]) -> list[InputSession]:
    return [
        s for s in sessions
        if s.audio_path is not None and not s.has_existing_transcript
    ]


@dataclass(frozen=True)
class SessionTranscription:
    """One session's transcription, as soon as it is done."""

    session_id: str
    #: Empty when the session failed (``failure`` says why) or was silent.
    segments: list[TranscriptSegment]
    #: The language the backend DETECTED; None when the language was pinned.
    detected_language: str | None = None
    failure: StageFailure | None = None


def iter_transcribe_sessions(
    sessions: list[InputSession],
    settings: BristlenoseSettings,
    *,
    on_progress: ProgressCallback | None = None,
    on_segment: SegmentCallback | None = None,
) -> Iterator[SessionTranscription]:
    """Transcribe the sessions that need it, yielding each one as it finishes.

    The backend is initialised once. A caller that wants to act on session 1
    while session 2 is still to come (progressive lenses: a transcript a
    researcher can read before the run ends) consumes this; everyone else
    calls :func:`transcribe_sessions`, which collects it.
    """
    needs_transcription = _needs_transcription(sessions)
    if not needs_transcription:
        logger.info("No sessions need transcription.")
        return

    # Detect hardware and choose backend
    hw = detect_hardware()
    backend = _resolve_backend(settings.whisper_backend, hw)

    logger.info(
        "Transcribing %d sessions | backend=%s | model=%s | %s",
        len(needs_transcription),
        backend,
        settings.whisper_model,
        hw.summary(),
    )

    # Initialise the chosen backend
    if backend == "mlx":
        transcribe_fn = _init_mlx_backend(settings)
    else:
        transcribe_fn = _init_faster_whisper_backend(settings, hw)

    pinned = settings.whisper_language if settings.whisper_language != "auto" else None
    total = len(needs_transcription)

    for i, session in enumerate(needs_transcription, start=1):
        assert session.audio_path is not None
        logger.info(
            "%s: Transcribing %s",
            session.session_id,
            session.audio_path.name,
        )

        seg_cb = None
        if on_segment is not None:
            def seg_cb(seconds_done: float, file_seconds: float, _i: int = i) -> None:
                on_segment(_i, total, seconds_done, file_seconds)

        try:
            # Only pass on_segment when a caller actually wants the within-file
            # heartbeat — keeps backward-compat with transcribe_fn callables
            # (and test stubs) that take only (audio_path, settings).
            if seg_cb is not None:
                out = transcribe_fn(
                    session.audio_path, settings, on_segment=seg_cb,
                )
            else:
                out = transcribe_fn(session.audio_path, settings)
            # Backends return (segments, label); a stub may still return a bare
            # list — the same backward-compat the on_segment arity dance above
            # exists for.
            segments, detected = out if isinstance(out, tuple) else (out, None)
            # Only record a label we did NOT supply. With the language pinned,
            # every backend echoes the decode option straight back, so storing
            # it would be our own input wearing the clothes of evidence.
            done = SessionTranscription(
                session.session_id, segments, detected if pinned is None and detected else None,
            )
            logger.info(
                "%s: Transcribed %d segments",
                session.session_id,
                len(segments),
            )
        except Exception as exc:
            logger.error(
                "%s: Transcription failed: %s",
                session.session_id,
                exc,
            )
            # Categorise the exception. Default-category fallback is WHISPER
            # (more useful than UNKNOWN for transcription-stage failures).
            cause = categorise_exception(exc)
            if cause.category == CauseCategoryEnum.UNKNOWN:
                cause = Cause(
                    category=CauseCategoryEnum.WHISPER,
                    message=cause.message,
                    stage="s05_transcribe",
                    session_id=session.session_id,
                )
            else:
                cause = cause.model_copy(update={
                    "stage": "s05_transcribe",
                    "session_id": session.session_id,
                })
            done = SessionTranscription(
                session.session_id, [], None,
                StageFailure(session_id=session.session_id, cause=cause),
            )

        if on_progress:
            on_progress(i, total)
        # After the progress callback, so the stage's own count has moved
        # before the caller does anything with this session.
        yield done


async def aiter_transcribe_sessions(
    sessions: list[InputSession],
    settings: BristlenoseSettings,
    *,
    on_progress: ProgressCallback | None = None,
    on_segment: SegmentCallback | None = None,
    on_finished: Callable[[float], None] | None = None,
) -> AsyncIterator[SessionTranscription]:
    """:func:`iter_transcribe_sessions` on its own thread, as an async iterator.

    Progressive lenses, Phase 3 (decided 12 Oct 2026). The backend is a blocking
    call; run on the event loop, a coroutine started between files (the readable
    chain's speaker pass, topics and quotes for the session just finished) made no
    progress until the next file was decoded. Here Whisper decodes session N+1
    while the loop works on N.

    - **One thread for the whole run**, so the backend is initialised and used on
      the same thread (MLX keeps per-thread streams).
    - **Daemon**, so Ctrl-C ends the run without waiting for the file in hand; the
      thread stops at the next file boundary when the consumer goes away.
    - **The callbacks run on the loop**, in the order the backend made them
      (``call_soon_threadsafe`` is first in, first out), so a progress line never
      comes from two threads at once.
    - ``on_finished`` is told the ``perf_counter`` time the backend finished, so
      the caller can say how long the work after it held transcription up.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
    stop = threading.Event()

    def _post(kind: str, value: object) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, (kind, value))
        except RuntimeError:  # the loop has closed: the run is over
            stop.set()

    def _on_loop(fn: Callable[..., None] | None) -> Callable[..., None] | None:
        if fn is None:
            return None

        def hop(*args: object) -> None:
            try:
                loop.call_soon_threadsafe(lambda: fn(*args))
            except RuntimeError:
                stop.set()
        return hop

    def _work() -> None:
        try:
            for done in iter_transcribe_sessions(
                sessions, settings,
                on_progress=_on_loop(on_progress), on_segment=_on_loop(on_segment),
            ):
                _post("item", done)
                if stop.is_set():
                    return
            if on_finished is not None:
                on_finished(time.perf_counter())
            _post("done", None)
        except BaseException as exc:  # noqa: BLE001 — re-raised on the loop
            _post("error", exc)

    ctx = contextvars.copy_context()
    threading.Thread(
        target=ctx.run, args=(_work,), name="bristlenose-transcribe", daemon=True,
    ).start()
    try:
        while True:
            kind, value = await queue.get()
            if kind == "item":
                yield value  # type: ignore[misc]
            elif kind == "error":
                raise value  # type: ignore[misc]
            else:
                return
    finally:
        stop.set()


def transcribe_sessions(
    sessions: list[InputSession],
    settings: BristlenoseSettings,
    *,
    on_progress: ProgressCallback | None = None,
    on_segment: SegmentCallback | None = None,
) -> tuple[dict[str, list[TranscriptSegment]], dict[str, str], StageOutcome]:
    """Transcribe audio for sessions that need it.

    Detects hardware and selects the optimal backend automatically.

    Only processes sessions that:
    - Have an audio_path set
    - Do not already have an existing transcript (subtitle/docx)

    Args:
        sessions: Sessions to transcribe.
        settings: Application settings.
        on_progress: Optional callback(current, total) called after each file completes.
        on_segment: Optional callback(file_index, file_total, seconds_done,
            file_seconds) called repeatedly *within* a file as audio is
            transcribed — faster-whisper only (mlx is one blocking call).

    Returns:
        Tuple of (results, languages, outcome). ``results`` maps session_id to
        TranscriptSegments (empty list when that session failed).
        ``languages`` maps session_id to the language the backend DETECTED,
        and is empty for a pinned run (that is the decode option coming back,
        not a detection). ``outcome`` records per-session
        attempts/successes/failures so the orchestrator can decide whether to
        abandon the run.

        Returns all three when nothing needs transcribing too. Until
        ``iter_transcribe_sessions`` took the work, that path was an early
        return that gave two values to a caller unpacking three, so it raised
        ValueError rather than returning nothing.
    """

    results: dict[str, list[TranscriptSegment]] = {}
    #: session_id -> the language the backend DETECTED. Populated only when the
    #: language was left to the backend; see SessionTranscription.
    languages: dict[str, str] = {}
    outcome = StageOutcome(attempted=len(_needs_transcription(sessions)))
    for done in iter_transcribe_sessions(
        sessions, settings, on_progress=on_progress, on_segment=on_segment,
    ):
        results[done.session_id] = done.segments
        if done.detected_language:
            languages[done.session_id] = done.detected_language
        if done.failure is None:
            outcome.succeeded += 1
        else:
            outcome.failed.append(done.failure)
    return results, languages, outcome


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------

def _resolve_backend(configured: str, hw: HardwareInfo) -> str:
    """Resolve which backend to use.

    An interim model picker: fix, don't grow (docs/design-pluggable-llm-routing.md §Interim model pickers).

    Args:
        configured: The user's setting — "auto", "mlx", or "faster-whisper".
        hw: Detected hardware info.

    Returns:
        "mlx" or "faster-whisper"
    """
    if configured == "mlx":
        if not hw.mlx_available:
            logger.warning(
                "MLX backend requested but mlx-whisper not installed. "
                "Install with: pip install bristlenose[apple]  "
                "Falling back to faster-whisper."
            )
            return "faster-whisper"
        return "mlx"

    if configured == "faster-whisper":
        return "faster-whisper"

    # Auto mode: prefer MLX on Apple Silicon, otherwise faster-whisper
    if (
        hw.accelerator == AcceleratorType.APPLE_SILICON
        and hw.mlx_available
    ):
        logger.info("Auto-selected MLX backend (Apple Silicon detected)")
        return "mlx"

    if hw.accelerator == AcceleratorType.APPLE_SILICON and not hw.mlx_available:
        logger.info(
            "Apple Silicon detected but mlx-whisper not installed. "
            "Using faster-whisper on CPU. For GPU acceleration: "
            "pip install bristlenose[apple]"
        )

    return "faster-whisper"


# ---------------------------------------------------------------------------
# MLX backend (Apple Silicon GPU)
# ---------------------------------------------------------------------------

def _init_mlx_backend(
    settings: BristlenoseSettings,
) -> TranscribeFn:
    """Initialise the MLX-whisper backend.

    MLX runs on Apple's Metal GPU. It uses unified memory, so the model
    and audio data share the same memory pool — no copying between CPU and
    GPU. This is efficient on all M-series chips (M1 through M4 Ultra and
    future chips) because they all expose the same Metal compute API.

    Returns:
        A function(audio_path, settings) -> list[TranscriptSegment]
    """
    import mlx_whisper

    # huggingface_hub is now imported (transitive dep of mlx_whisper).
    # Programmatically disable its download progress bars — the env var
    # may have been too late if huggingface_hub was imported earlier.
    try:
        # The defining module: ``huggingface_hub.utils`` re-exports it implicitly,
        # which strict mypy does not count as an export.
        from huggingface_hub.utils.tqdm import disable_progress_bars
        disable_progress_bars()
    except ImportError:
        pass

    logger.info(
        "MLX backend initialised (model will be loaded on first use): %s",
        settings.whisper_model,
    )

    def _recover_skipped(
        segs: list[dict[str, Any]],
        audio: Any,
        levels: object,
        decode_kwargs: dict[str, object],
        language: str | None,
        name: str,
    ) -> list[dict[str, Any]]:
        """Re-decode stretches Whisper skipped; see the note above `find_skipped_stretches`.

        Runs outside the style-prompt block, so the re-decode has no prompt.
        """
        # Lengths as the paragraph rule counts them: a Japanese line is one
        # "word" to str.split(), which made every Japanese stretch look skipped
        # and re-decoded about 40% of a file to no effect.
        from bristlenose.stages.s06_merge_transcript import reading_length

        total_s = len(audio) / _SAMPLE_RATE
        # Words as the transcript will show them: after the repeat filter, a
        # "nada nada nada..." loop is one word, so the stretch it covers reads
        # as what it is (speech lost to a loop) and is re-decoded.
        spans = [
            (float(x.get("start", 0.0)), float(x.get("end", 0.0)),
             reading_length(collapse_adjacent_repeats(str(x.get("text", "")).strip())))
            for x in segs
        ]
        stretches = find_skipped_stretches(spans, levels, total_s)
        kept = list(segs)
        recovered = 0
        words = 0.0
        for a, b in stretches:
            chunk = audio[int(a * _SAMPLE_RATE):int(b * _SAMPLE_RATE)]
            r = mlx_whisper.transcribe(chunk, language=language, **decode_kwargs)
            new: list[dict[str, Any]] = []
            for seg in r.get("segments", []):
                seg = dict(seg)
                seg["start"] = float(seg.get("start", 0.0)) + a
                seg["end"] = float(seg.get("end", 0.0)) + a
                seg["words"] = [
                    {**w, "start": float(w.get("start", 0.0)) + a,
                     "end": float(w.get("end", 0.0)) + a}
                    for w in seg.get("words", [])
                ]
                if a <= (seg["start"] + seg["end"]) / 2 < b:
                    new.append(seg)
            # The re-decode loops too (12 Oct 2026: "nada" 39 times over 28 s,
            # which read as 1.4 words a second and was accepted). Judged as the
            # reader would get it: loops out, repeats collapsed.
            new, _ = drop_segment_loops(new)
            n = sum(
                reading_length(collapse_adjacent_repeats(str(x.get("text", "")).strip()))
                for x in new
            )
            if n / max(b - a, 0.01) >= _RECOVER_MIN_WPS:
                kept = [
                    x for x in kept
                    if not a <= (float(x.get("start", 0.0)) + float(x.get("end", 0.0))) / 2 < b
                ] + new
                recovered += 1
                words += n
        kept.sort(key=lambda x: float(x.get("start", 0.0)))
        if stretches:
            logger.info(
                "%s: %d skipped stretch(es) found, %d recovered (%d words, %.0f s)",
                name, len(stretches), recovered, words,
                sum(b - a for a, b in stretches),
            )
        return kept

    def transcribe_mlx(
        audio_path: Path,
        settings: BristlenoseSettings,
        on_segment: FileSegmentCallback | None = None,
    ) -> tuple[list[TranscriptSegment], str | None]:
        # on_segment is ignored: mlx_whisper.transcribe() is one blocking call
        # that returns every segment at once, so there's no within-file
        # heartbeat to surface (per-file progress still ticks in the caller).
        # mlx-whisper uses HuggingFace model names
        model_name = _mlx_model_name(settings.whisper_model)

        # Decode once, here, so the signal gate and Whisper read the same
        # samples. `transcribe` would otherwise run this same ffmpeg call on
        # the path itself.
        audio = mlx_whisper.audio.load_audio(str(audio_path))
        levels = window_levels_dbfs(audio)
        if not has_signal(levels):
            # Nothing to hear — and Whisper would not return nothing, it would
            # return "Thank you." every 30 s. See the signal-gate note above.
            # Zero segments is stated downstream as NO_SPEECH.
            logger.info(
                "%s: no signal above %.0f dBFS — not transcribed",
                audio_path.name, _SIGNAL_FLOOR_DBFS,
            )
            return [], None

        # Loop-breaking kwargs for mlx-whisper. `no_speech_threshold` is inert
        # on large-v3-turbo (its no_speech_prob is always 0.0 — see the gate
        # note above); it is kept for the smaller models, where it still works.
        # The style prompt (see the note above `STYLE_PROMPTS`) rides on every
        # window inside this block, and the seed makes the windows that fall
        # back to sampling come out the same on every run of the same file.
        hook_ready = _install_style_prompt_hook()
        import mlx.core as mx

        mx.random.seed(0)
        _hook_counts.update(built=0, filled=0)
        token = _STYLE_PROMPT_ON.set(hook_ready)
        decode_kwargs: dict[str, object] = {
            "path_or_hf_repo": model_name,
            "word_timestamps": True,
            "verbose": None,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.85,
            "compression_ratio_threshold": 1.8,
        }
        try:
            result = mlx_whisper.transcribe(
                audio,
                language=(
                    settings.whisper_language
                    if settings.whisper_language != "auto" else None
                ),
                **decode_kwargs,
            )
        finally:
            _STYLE_PROMPT_ON.reset(token)
        prompt = style_prompt_for(result.get("language")) if hook_ready else None
        if hook_ready:
            built, filled = _hook_counts["built"], _hook_counts["filled"]
            if built == 0 or (prompt and filled == 0):
                # The hook is installed but mlx no longer goes through it.
                logger.warning(
                    "%s: style prompt did not reach the decoder (%d of %d decode steps)",
                    audio_path.name, filled, built,
                )
            else:
                logger.info(
                    "%s: style prompt %s, %d of %d decode steps (language=%s)",
                    audio_path.name, "on" if prompt else "none for this language",
                    filled, built, result.get("language"),
                )

        # What the model decided the audio was. mlx computes the full
        # probability distribution internally (`model.detect_language` →
        # `probs`) and keeps only the argmax, so unlike faster-whisper there is
        # no confidence to report — the label is the whole signal we get.
        #
        # And mlx detects on `pad_or_trim(mel, N_FRAMES)`, the RAW first window:
        # no VAD. faster-whisper strips silence first (`get_speech_timestamps`
        # → `collect_chunks` → features → `detect_language`), so its 30s is 30s
        # of speech while this one is 30s of file — mic checks, "can you hear
        # me", dead air. Since mlx is the Apple Silicon default, the desktop is
        # the weaker of the two paths here. Don't assume the backends agree.
        logger.info(
            "Audio: language=%s (mlx: no confidence reported)",
            result.get("language"),
        )

        # The two filters first, so the net looks at the transcript the reader
        # will get: a dropped prompt echo leaves a gap over real speech, and the
        # net re-decodes it; and "found", "recovered" and "still empty" all
        # describe one transcript.
        kept: list[dict[str, Any]] = []
        in_silence = 0
        echoes = 0
        for seg in result.get("segments", []):
            if not segment_has_signal(seg.get("start", 0.0), seg.get("end", 0.0), levels):
                # A recording with speech in it can still carry long silent
                # stretches, and Whisper fills those the same way.
                if seg.get("text", "").strip():
                    in_silence += 1
                continue
            if prompt and is_prompt_echo(seg.get("text", ""), prompt):
                echoes += 1
                continue
            kept.append(seg)

        # A loop is never what was said, so it goes before the net: the stretch
        # it covered then reads as the gap it is, and is re-decoded.
        kept, looped = drop_segment_loops(kept, prompt)

        if SKIP_NET_ENABLED:
            kept = _recover_skipped(
                kept, audio, levels, decode_kwargs, result.get("language"), audio_path.name,
            )

        segments: list[TranscriptSegment] = []
        guesses = 0
        for seg in kept:
            if not segment_has_signal(seg.get("start", 0.0), seg.get("end", 0.0), levels):
                in_silence += 1  # a re-decoded line over a silent part of its stretch
                continue
            words: list[Word] = []
            for w in seg.get("words", []):
                word_text = w.get("word", "").strip()
                if word_text:
                    words.append(Word(
                        text=word_text,
                        start_time=w.get("start", 0.0),
                        end_time=w.get("end", 0.0),
                        confidence=w.get("probability", 1.0),
                    ))

            text = collapse_adjacent_repeats(seg.get("text", "").strip())
            if prompt and is_prompt_guess(text, prompt, [w.confidence for w in words]):
                # Kept as a gap rather than dropped, so the reader sees that
                # someone spoke here and nothing was heard; Whisper's guess
                # goes, so it can never be quoted.
                guesses += 1
                last = segments[-1] if segments else None
                if last and last.inaudible and seg.get("start", 0.0) - last.end_time < 1.0:
                    last.end_time = seg.get("end", 0.0)
                    continue
                segments.append(TranscriptSegment(
                    start_time=seg.get("start", 0.0),
                    end_time=seg.get("end", 0.0),
                    text="",
                    inaudible=True,
                    source="mlx-whisper",
                ))
                continue
            if text:
                segments.append(TranscriptSegment(
                    start_time=seg.get("start", 0.0),
                    end_time=seg.get("end", 0.0),
                    text=text,
                    words=words,
                    source="mlx-whisper",
                ))

        # And once more on the finished transcript: a re-decode beside a
        # first-pass line of the same text can make a loop neither held, and a
        # line the gates above dropped can have hidden one (es-1, 12 Oct 2026:
        # 18 "nada" lines survived a check made before the gates).
        final = find_segment_loops([(s.start_time, s.end_time, s.text) for s in segments])
        gone = {k for i, j in final for k in range(i, j)}
        segments = [s for k, s in enumerate(segments) if k not in gone]
        looped += len(gone)

        if in_silence:
            logger.info(
                "%s: dropped %d segment(s) with no signal above %.0f dBFS",
                audio_path.name, in_silence, _SIGNAL_FLOOR_DBFS,
            )
        if echoes:
            logger.info(
                "%s: dropped %d segment(s) that repeat the style prompt",
                audio_path.name, echoes,
            )
        if looped:
            logger.info(
                "%s: removed %d segment(s) of repetition loops",
                audio_path.name, looped,
            )
        if guesses:
            logger.info(
                "%s: marked %d segment(s) inaudible (prompt words at low confidence)",
                audio_path.name, guesses,
            )

        return segments, result.get("language")

    return transcribe_mlx


# Interim model picker: fix, don't grow. Model choice belongs to the
# per-stage resolver that is not built yet (docs/design-pluggable-llm-routing.md §Interim model pickers) —
# fix a wrong ID or tag here, but add no tiers, ladders or new picking.
#
# Short model names to the mlx-community conversions mlx-whisper loads. The
# Whisper preflight (``bristlenose/preflight/whisper.py``) and ``doctor`` read
# this same table, so the repo the preflight fetches is the repo stage 5 opens.
MLX_REPO_FOR_MODEL: dict[str, str] = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "tiny.en": "mlx-community/whisper-tiny.en-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "base.en": "mlx-community/whisper-base.en-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "small.en": "mlx-community/whisper-small.en-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "medium.en": "mlx-community/whisper-medium.en-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


def _mlx_model_name(whisper_model: str) -> str:
    """Map short model names to HuggingFace repo paths for mlx-whisper.

    mlx-whisper accepts HuggingFace model paths. The mlx-community has
    pre-converted quantised models that are optimal. Anything not in
    :data:`MLX_REPO_FOR_MODEL` passes through as a repo id.
    """
    return MLX_REPO_FOR_MODEL.get(whisper_model, whisper_model)


# ---------------------------------------------------------------------------
# faster-whisper backend (CUDA / CPU)
# ---------------------------------------------------------------------------

def _init_faster_whisper_backend(
    settings: BristlenoseSettings,
    hw: HardwareInfo,
) -> TranscribeFn:
    """Initialise the faster-whisper backend.

    Uses CUDA on NVIDIA GPUs, CPU with INT8 quantization otherwise.

    Returns:
        A function(audio_path, settings) -> list[TranscriptSegment]
    """
    import os

    from faster_whisper import WhisperModel

    # Choose device and compute type based on hardware
    if hw.cuda_available:
        device = "cuda"
        compute_type = "float16"
        logger.info("faster-whisper: using CUDA (GPU)")
    else:
        device = "cpu"
        compute_type = settings.whisper_compute_type  # default: int8
        logger.info("faster-whisper: using CPU (%s)", compute_type)

    # Support bundled model directory (desktop app sets BRISTLENOSE_WHISPER_MODEL_DIR)
    model_dir = os.environ.get("BRISTLENOSE_WHISPER_MODEL_DIR")
    model_id: str = settings.whisper_model
    local_only = False
    if model_dir:
        candidate = os.path.join(model_dir, settings.whisper_model)
        if os.path.isdir(candidate):
            model_id = candidate
            local_only = True
            logger.info("Using bundled Whisper model: %s", candidate)
        else:
            logger.warning(
                "BRISTLENOSE_WHISPER_MODEL_DIR set but model not found at %s, "
                "falling back to download",
                candidate,
            )

    model = WhisperModel(
        model_id,
        device=device,
        compute_type=compute_type,
        local_files_only=local_only,
    )

    def transcribe_faster_whisper(
        audio_path: Path,
        settings: BristlenoseSettings,
        on_segment: FileSegmentCallback | None = None,
    ) -> tuple[list[TranscriptSegment], str | None]:
        from faster_whisper.audio import decode_audio

        # Decode once: the language has to be known before the style prompt
        # can be chosen, and transcribe would otherwise decode the file again.
        audio = decode_audio(str(audio_path))
        language = settings.whisper_language if settings.whisper_language != "auto" else None
        detected_prob: float | None = None
        if language is None:
            # The same detection transcribe runs (speech only, via VAD).
            language, detected_prob, _all = model.detect_language(audio, vad_filter=True)
        prompt = (
            style_prompt_for(language)
            if _language_code(language) in FASTER_WHISPER_PROMPT_LANGUAGES else None
        )
        segments_iter, info = model.transcribe(
            audio,
            language=language,
            word_timestamps=True,
            vad_filter=True,
            hotwords=prompt,
        )
        logger.info(
            "%s: style prompt %s (language=%s)",
            audio_path.name, "on" if prompt else "none for this language", language,
        )

        logger.info(
            "Audio: language=%s (prob=%.2f), duration=%.0fs",
            info.language,
            # transcribe reports 1.0 for a language it was given; the
            # detection's own confidence is the one worth logging.
            detected_prob if detected_prob is not None else info.language_probability,
            info.duration,
        )

        transcript_segments: list[TranscriptSegment] = []

        for segment in segments_iter:
            words: list[Word] = []
            if segment.words:
                words = [
                    Word(
                        text=w.word.strip(),
                        start_time=w.start,
                        end_time=w.end,
                        confidence=w.probability,
                    )
                    for w in segment.words
                    if w.word.strip()
                ]

            transcript_segments.append(
                TranscriptSegment(
                    start_time=segment.start,
                    end_time=segment.end,
                    text=collapse_adjacent_repeats(segment.text.strip()),
                    words=words,
                    source="faster-whisper",
                )
            )

            # Within-file heartbeat: how far through this file's audio we are.
            # info.duration is the total audio length; segment.end is the
            # timestamp of the segment just decoded.
            if on_segment is not None and info.duration:
                on_segment(segment.end, info.duration)

        return transcript_segments, info.language

    return transcribe_faster_whisper
