"""Stage 5: Speech-to-text transcription.

Automatically selects the best backend for the current hardware:
- Apple Silicon (M1/M2/M3/M4 and all variants): mlx-whisper via Metal GPU
- NVIDIA GPU: faster-whisper via CUDA
- CPU fallback: faster-whisper with INT8 quantization

The backend can be overridden via settings.whisper_backend.
"""

from __future__ import annotations

import logging
from pathlib import Path

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


ProgressCallback = type(lambda current, total: None)


def transcribe_sessions(
    sessions: list[InputSession],
    settings: BristlenoseSettings,
    *,
    on_progress: ProgressCallback | None = None,
) -> tuple[dict[str, list[TranscriptSegment]], StageOutcome]:
    """Transcribe audio for sessions that need it.

    Detects hardware and selects the optimal backend automatically.

    Only processes sessions that:
    - Have an audio_path set
    - Do not already have an existing transcript (subtitle/docx)

    Args:
        sessions: Sessions to transcribe.
        settings: Application settings.
        on_progress: Optional callback(current, total) called after each file completes.

    Returns:
        Tuple of (results, outcome). ``results`` maps session_id to
        TranscriptSegments (empty list when that session failed). ``outcome``
        records per-session attempts/successes/failures so the orchestrator
        can decide whether to abandon the run.
    """
    needs_transcription = [
        s for s in sessions
        if s.audio_path is not None and not s.has_existing_transcript
    ]

    if not needs_transcription:
        logger.info("No sessions need transcription.")
        return {}, StageOutcome()

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

    results: dict[str, list[TranscriptSegment]] = {}
    outcome = StageOutcome(attempted=len(needs_transcription))
    total = len(needs_transcription)

    for i, session in enumerate(needs_transcription, start=1):
        assert session.audio_path is not None
        logger.info(
            "%s: Transcribing %s",
            session.session_id,
            session.audio_path.name,
        )

        try:
            segments = transcribe_fn(session.audio_path, settings)
            results[session.session_id] = segments
            outcome.succeeded += 1
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
            results[session.session_id] = []
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
            outcome.failed.append(StageFailure(
                session_id=session.session_id, cause=cause,
            ))

        if on_progress:
            on_progress(i, total)

    return results, outcome


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------

def _resolve_backend(configured: str, hw: HardwareInfo) -> str:
    """Resolve which backend to use.

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

TranscribeFn = type(lambda path, settings: [])  # callable type hint placeholder


def _init_mlx_backend(
    settings: BristlenoseSettings,
) -> callable:  # type: ignore[valid-type]
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
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()
    except ImportError:
        pass

    logger.info(
        "MLX backend initialised (model will be loaded on first use): %s",
        settings.whisper_model,
    )

    def transcribe_mlx(
        audio_path: Path,
        settings: BristlenoseSettings,
    ) -> list[TranscriptSegment]:
        # mlx-whisper uses HuggingFace model names
        model_name = _mlx_model_name(settings.whisper_model)

        # Hallucination mitigations for mlx-whisper (faster-whisper has
        # vad_filter); revisit after cohort feedback (see 100days.md).
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=model_name,
            language=settings.whisper_language if settings.whisper_language != "auto" else None,
            word_timestamps=True,
            verbose=None,
            condition_on_previous_text=False,
            no_speech_threshold=0.85,
            compression_ratio_threshold=1.8,
        )

        segments: list[TranscriptSegment] = []
        for seg in result.get("segments", []):
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
            if text:
                segments.append(TranscriptSegment(
                    start_time=seg.get("start", 0.0),
                    end_time=seg.get("end", 0.0),
                    text=text,
                    words=words,
                    source="mlx-whisper",
                ))

        return segments

    return transcribe_mlx


def _mlx_model_name(whisper_model: str) -> str:
    """Map short model names to HuggingFace repo paths for mlx-whisper.

    mlx-whisper accepts HuggingFace model paths. The mlx-community has
    pre-converted quantised models that are optimal.
    """
    # Map common short names to mlx-community models
    mapping = {
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
    return mapping.get(whisper_model, whisper_model)


# ---------------------------------------------------------------------------
# faster-whisper backend (CUDA / CPU)
# ---------------------------------------------------------------------------

def _init_faster_whisper_backend(
    settings: BristlenoseSettings,
    hw: HardwareInfo,
) -> callable:  # type: ignore[valid-type]
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
    ) -> list[TranscriptSegment]:
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=settings.whisper_language if settings.whisper_language != "auto" else None,
            word_timestamps=True,
            vad_filter=True,
        )

        logger.info(
            "Audio: language=%s (prob=%.2f), duration=%.0fs",
            info.language,
            info.language_probability,
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

        return transcript_segments

    return transcribe_faster_whisper
