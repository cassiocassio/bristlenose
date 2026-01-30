"""Stage 7: PII detection and redaction using Presidio."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from bristlenose.config import BristlenoseSettings
from bristlenose.models import (
    FullTranscript,
    PiiCleanTranscript,
    TranscriptSegment,
    format_timecode,
)

logger = logging.getLogger(__name__)

# Mapping from Presidio entity types to our redaction labels
_ENTITY_MAP: dict[str, str] = {
    "PERSON": "[NAME]",
    "PHONE_NUMBER": "[PHONE]",
    "EMAIL_ADDRESS": "[EMAIL]",
    # NOTE: We intentionally omit LOCATION. Presidio's LOCATION fires on any
    # named place (cities, shops, landmarks) which is almost never PII in
    # user-research transcripts and destroys valuable data ("Oxford Street
    # IKEA" → "[ADDRESS] IKEA"). The ADDRESS entity below catches structured
    # postal addresses, which *are* PII.
    "ADDRESS": "[ADDRESS]",
    "CREDIT_CARD": "[CARD]",
    "US_SSN": "[SSN]",
    "UK_NHS": "[NHS]",
    "US_DRIVER_LICENSE": "[ID]",
    "US_PASSPORT": "[ID]",
    "US_BANK_NUMBER": "[ACCOUNT]",
    "IBAN_CODE": "[IBAN]",
    "IP_ADDRESS": "[IP]",
    "URL": "[URL]",
    "DATE_TIME": "[DATE]",  # Only redact if it looks like a birthdate
}

# Entity types we always want to detect.
# LOCATION is deliberately excluded — it matches public places (shop names,
# city names, landmarks) which are research data, not PII. ADDRESS catches
# actual postal addresses.
_DEFAULT_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "US_SSN",
    "IBAN_CODE",
    "IP_ADDRESS",
]


# ---------------------------------------------------------------------------
# PII redaction detail — one per redacted entity
# ---------------------------------------------------------------------------

class PiiRedaction:
    """Record of a single PII entity that was redacted."""

    def __init__(
        self,
        entity_type: str,
        original_text: str,
        replacement: str,
        score: float,
        timecode: float,
    ) -> None:
        self.entity_type = entity_type
        self.original_text = original_text
        self.replacement = replacement
        self.score = score
        self.timecode = timecode

    def __repr__(self) -> str:
        return (
            f"PiiRedaction({self.entity_type}: "
            f"{self.original_text!r} -> {self.replacement}, "
            f"score={self.score:.2f})"
        )


def remove_pii(
    transcripts: list[FullTranscript],
    settings: BristlenoseSettings,
) -> tuple[list[PiiCleanTranscript], list[PiiRedaction]]:
    """Remove PII from transcripts using Presidio.

    Args:
        transcripts: Raw transcripts with PII.
        settings: Application settings.

    Returns:
        Tuple of (cleaned transcripts, all redactions across all sessions).
    """
    logger.info("Initialising Presidio (loads spaCy NLP model on first run)...")
    analyzer, anonymizer = _init_presidio(settings)

    clean_transcripts: list[PiiCleanTranscript] = []
    all_redactions: list[PiiRedaction] = []

    for transcript in transcripts:
        total_entities = 0
        clean_segments: list[TranscriptSegment] = []

        for seg in transcript.segments:
            clean_text, redactions = _redact_text(
                seg.text, seg.start_time, analyzer, anonymizer, settings
            )
            total_entities += len(redactions)
            all_redactions.extend(redactions)

            clean_seg = seg.model_copy()
            clean_seg.text = clean_text
            clean_segments.append(clean_seg)

        clean_transcript = PiiCleanTranscript(
            participant_id=transcript.participant_id,
            source_file=transcript.source_file,
            session_date=transcript.session_date,
            duration_seconds=transcript.duration_seconds,
            segments=clean_segments,
            pii_entities_found=total_entities,
        )
        clean_transcripts.append(clean_transcript)

        logger.info(
            "%s: Removed %d PII entities",
            transcript.participant_id,
            total_entities,
        )

    return clean_transcripts, all_redactions


def write_cooked_transcripts(
    transcripts: list[PiiCleanTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write PII-cleaned ('cooked') transcript text files.

    Args:
        transcripts: Cleaned transcripts.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        filename = f"{transcript.participant_id}_cooked.txt"
        path = output_dir / filename

        lines: list[str] = []
        lines.append(f"# Transcript (cooked): {transcript.participant_id}")
        lines.append(f"# Source: {transcript.source_file}")
        lines.append(f"# Date: {transcript.session_date.date()}")
        lines.append(f"# Duration: {format_timecode(transcript.duration_seconds)}")
        lines.append(f"# PII entities redacted: {transcript.pii_entities_found}")
        lines.append("")

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            role = seg.speaker_role.value.upper()
            lines.append(f"[{tc}] [{role}] {seg.text}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote cooked transcript: %s", path)

    return paths


def write_pii_summary(
    redactions: list[PiiRedaction],
    output_dir: Path,
) -> Path | None:
    """Write a PII redaction summary report.

    Shows what was found, what it was replaced with, and where.
    This lets the user audit whether Presidio did a good job.

    Args:
        redactions: All redactions from the pipeline run.
        output_dir: Directory to write to.

    Returns:
        Path to the summary file, or None if no redactions.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "pii_summary.txt"

    lines: list[str] = []
    lines.append("# PII Redaction Summary")
    lines.append(f"# Total entities redacted: {len(redactions)}")
    lines.append("")

    if not redactions:
        lines.append("No PII entities were detected in any transcript.")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote PII summary (no redactions): %s", path)
        return path

    # Summary by type
    type_counts: Counter[str] = Counter()
    for r in redactions:
        type_counts[r.entity_type] += 1

    lines.append("## By entity type")
    lines.append("")
    for entity_type, count in type_counts.most_common():
        label = _ENTITY_MAP.get(entity_type, "[PII]")
        lines.append(f"  {entity_type:24s} {label:12s} x{count}")
    lines.append("")

    # Detailed list
    lines.append("## Detailed redactions")
    lines.append("")
    lines.append(f"  {'Timecode':<12s} {'Type':<16s} {'Original':<30s} {'Replaced with':<14s} {'Score'}")
    lines.append(f"  {'--------':<12s} {'----':<16s} {'--------':<30s} {'-------------':<14s} {'-----'}")

    for r in sorted(redactions, key=lambda x: x.timecode):
        tc = format_timecode(r.timecode)
        orig = r.original_text[:28] + ".." if len(r.original_text) > 30 else r.original_text
        lines.append(
            f"  [{tc}]    {r.entity_type:<16s} {orig:<30s} {r.replacement:<14s} {r.score:.2f}"
        )

    lines.append("")
    lines.append("# Review this file to check for false positives (over-redaction)")
    lines.append("# or false negatives (PII that was missed).")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote PII summary: %s", path)
    return path


def _init_presidio(
    settings: BristlenoseSettings,
) -> tuple[object, object]:
    """Initialise Presidio analyzer and anonymizer.

    Returns:
        (AnalyzerEngine, AnonymizerEngine) tuple.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    logger.info("Presidio engines initialised.")
    return analyzer, anonymizer


def _redact_text(
    text: str,
    timecode: float,
    analyzer: object,
    anonymizer: object,
    settings: BristlenoseSettings,
) -> tuple[str, list[PiiRedaction]]:
    """Redact PII from a text string.

    Returns:
        (redacted_text, list of PiiRedaction records)
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    assert isinstance(analyzer, AnalyzerEngine)
    assert isinstance(anonymizer, AnonymizerEngine)

    # Analyse for PII entities
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=_DEFAULT_ENTITIES,
        score_threshold=0.7,
    )

    if not results:
        return text, []

    # Build operator config: replace each entity type with its label
    operators: dict[str, OperatorConfig] = {}
    for entity_type in set(r.entity_type for r in results):
        replacement = _ENTITY_MAP.get(entity_type, "[PII]")
        operators[entity_type] = OperatorConfig(
            "replace", {"new_value": replacement}
        )

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    # Build detailed redaction records
    redactions = [
        PiiRedaction(
            entity_type=r.entity_type,
            original_text=text[r.start : r.end],
            replacement=_ENTITY_MAP.get(r.entity_type, "[PII]"),
            score=r.score,
            timecode=timecode,
        )
        for r in results
    ]

    return anonymized.text, redactions
