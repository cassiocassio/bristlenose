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
from bristlenose.models import InputSession, TranscriptSegment, Word
from bristlenose.utils.hardware import AcceleratorType, HardwareInfo, detect_hardware

logger = logging.getLogger(__name__)


def transcribe_sessions(
    sessions: list[InputSession],
    settings: BristlenoseSettings,
) -> dict[str, list[TranscriptSegment]]:
    """Transcribe audio for sessions that need it.

    Detects hardware and selects the optimal backend automatically.

    Only processes sessions that:
    - Have an audio_path set
    - Do not already have an existing transcript (subtitle/docx)

    Args:
        sessions: Sessions to transcribe.
        settings: Application settings.

    Returns:
        Dict mapping participant_id to list of TranscriptSegments.
    """
    needs_transcription = [
        s for s in sessions
        if s.audio_path is not None and not s.has_existing_transcript
    ]

    if not needs_transcription:
        logger.info("No sessions need transcription.")
        return {}

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

    for session in needs_transcription:
        assert session.audio_path is not None
        logger.info(
            "%s: Transcribing %s",
            session.participant_id,
            session.audio_path.name,
        )

        try:
            segments = transcribe_fn(session.audio_path, settings)
            results[session.participant_id] = segments
            logger.info(
                "%s: Transcribed %d segments",
                session.participant_id,
                len(segments),
            )
        except Exception as exc:
            logger.error(
                "%s: Transcription failed: %s",
                session.participant_id,
                exc,
            )
            results[session.participant_id] = []

    return results


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

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=model_name,
            language=settings.whisper_language if settings.whisper_language != "auto" else None,
            word_timestamps=True,
            verbose=False,
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

            text = seg.get("text", "").strip()
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

    model = WhisperModel(
        settings.whisper_model,
        device=device,
        compute_type=compute_type,
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
                    text=segment.text.strip(),
                    words=words,
                    source="faster-whisper",
                )
            )

        return transcript_segments

    return transcribe_faster_whisper
