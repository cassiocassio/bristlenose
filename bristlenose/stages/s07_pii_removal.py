"""Stage 7: PII detection and redaction using Presidio."""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.status import Status

from bristlenose.config import BristlenoseSettings
from bristlenose.i18n import t
from bristlenose.models import (
    FullTranscript,
    PiiCleanTranscript,
    TranscriptSegment,
    format_timecode,
)
from bristlenose.utils.text import count_noun

logger = logging.getLogger(__name__)

# Presidio's bare ``AnalyzerEngine()`` defaults to ``en_core_web_lg``, so this
# constant was vestigial and named a model the analyzer never loaded — we
# fetched 12 MB of ``sm`` and then pulled 400 MB of ``lg`` implicitly
# (recorded in docs/design-redact-pii.md, 26 Jul 2026). It is now load-bearing:
# the engine below is bound to it explicitly, so fetched == used, always.
SPACY_MODEL = "en_core_web_lg"
SPACY_MODEL_SIZE_HUMAN = "~400 MB"

#: Points at the *loadable* model directory — the one holding ``config.cfg``.
#: Set by the macOS host once the weights are on disk, whoever fetched them:
#: Background Assets on TestFlight/App Store, a plain HTTPS download on the
#: Developer-ID ``.dmg``. Mirrors ``BRISTLENOSE_WHISPER_MODEL_DIR``; the CLI
#: leaves it unset and resolves by name.
PII_MODEL_DIR_ENV = "BRISTLENOSE_PII_MODEL_DIR"


def resolve_spacy_model() -> str:
    """The model identifier both spaCy and Presidio must load — name or path.

    **Why one function and not two literals.** Presidio's engine builder does
    ``if not (spacy.util.is_package(name) or Path(name).exists()): spacy.cli.download(name)``
    — so handing it a *name* it cannot resolve makes it shell out to
    ``pip install`` from GitHub. Inside a sandboxed App Store binary that is a
    §2.5.2 violation and an ugly failure; handing it an absolute **path** makes
    ``Path(...).exists()`` true and the download branch unreachable. Every call
    site therefore resolves through here, and there is exactly one of them.

    Raises:
        ValueError: when the override is set but does not name a loadable model
            directory. Deliberately fail-loud rather than falling back to the
            name — the fallback is the ``pip install`` above.
    """
    override = os.environ.get(PII_MODEL_DIR_ENV, "").strip()
    if not override:
        return SPACY_MODEL

    path = Path(override).expanduser()
    # Both files, in spaCy's own order: `load_model_from_path` calls
    # `get_model_meta` (meta.json) *before* reading config.cfg, so checking
    # only config.cfg lets a directory through that then dies inside spaCy
    # with an opaque `E053: Could not read meta.json` — the exact failure this
    # message exists to replace.
    if not all((path / f).is_file() for f in ("meta.json", "config.cfg")):
        raise ValueError(
            f"{PII_MODEL_DIR_ENV} is set to {path} but that is not a loadable "
            "spaCy model directory (needs meta.json and config.cfg). Point it at "
            "the directory "
            "holding config.cfg — for en_core_web_lg that is the inner "
            "en_core_web_lg-<version>/ directory, which contains no Python at "
            "all and is what makes the downloaded pack pure data."
        )
    return str(path.absolute())
# Public: doctor probes and recommends this same model. It lived in five
# doctor sites and three doctor_fixes sites as the literal "en_core_web_sm"
# while the pipeline loaded lg, so `doctor` could call the stack healthy on
# a machine that would then pull 400 MB mid-run — and, after the model was
# reconciled, could fail preflight on a machine that was actually correct.


def _ensure_spacy_model(
    *, allow_fetch: bool = True, status: Status | None = None
) -> None:
    """Probe spaCy for :data:`SPACY_MODEL`; lazily download it on first run.

    The model is ~400 MB. This docstring used to reason about 12 MB and pick the
    one-line inline treatment on that basis — the wrong model and so the wrong
    UX tier, since the design doc's "fetch UX should scale with fetch size" rule
    puts anything over 50 MB behind the framed banner used for Whisper. The
    string now states the real size; the framed-banner treatment is still owed.

    On success the function returns, and :func:`_build_engines` binds the
    analyzer to this same model — so what is fetched is what is used.

    Args:
        allow_fetch: ``False`` under ``--no-fetch``. The flag means "do not
            reach the network", and a silent 425 MB download is the largest
            possible way to disobey it. Refuse instead.
        status: the run's Rich spinner, stopped for the duration of the
            download so the downloader's own output is not fought over. See
            the comment at the call site.

    Raises:
        PackageInstallError: when the model is absent and ``allow_fetch`` is
            ``False``. Deliberately this type rather than a bespoke one: it is
            literally a refused install, ``categorise_exception`` already maps
            it to ``MISSING_DEP``, and stage 7's handler in ``pipeline.py``
            turns that into a clean abandon with a privacy-safe Cause.
        Whatever :func:`ensure_spacy_model` raises (network failure, frozen
            sidecar). Caller surfaces the error.
    """
    import spacy

    from bristlenose.utils.package_install import ensure_spacy_model

    model = resolve_spacy_model()

    # A path means the host already placed the weights (BA, or the .dmg's own
    # download). There is nothing to fetch and nothing to ask the network for —
    # and on the frozen sidecar `ensure_spacy_model` would raise anyway.
    if model != SPACY_MODEL:
        spacy.load(model)
        return

    try:
        spacy.load(model)
        return
    except OSError:
        pass

    if not allow_fetch:
        from bristlenose.utils.package_install import PackageInstallError

        raise PackageInstallError(t("preflight.pii.aborted_no_fetch", model=model))

    from bristlenose.ui_kinds import MessageKind, cli_prefix

    # Per-call Console: terminal width is detected at call time so the desktop
    # sidecar's stdout piping isn't frozen at module-import time (avoiding the
    # gotcha where a sandboxed run inherits an 80-wide assumption made before
    # the host wired up its pipes).
    console = Console(width=min(80, Console().width))

    # Framed and stepped-aside rather than inline. Two reasons, and only the
    # first is the house ">50 MB gets the framed banner" rule.
    #
    # The second is a real output defect. `ensure_spacy_model` runs
    # `subprocess.run([... spacy download ...], check=True)` with **no
    # capture**, so pip writes its 425 MB of progress straight to this stdout —
    # while `Pipeline.run` holds a `console.status` spinner open across the
    # whole run, repainting the same lines. With `end=""` our own line was the
    # first casualty ("…one-off)...Collecting en-core-web-lg") and the ✓ was
    # orphaned after pip's last line. Whisper hit this first and answered it the
    # same way — `preflight/whisper.py`, "step aside, let HF Hub print
    # natively".
    console.print()
    console.print("  " + t("preflight.pii.downloading"))
    console.print()

    if status is not None:
        status.stop()
    t0 = time.perf_counter()
    try:
        ensure_spacy_model(model)
    except Exception:
        console.print(f"  {cli_prefix(MessageKind.ERROR)} {model}")
        raise
    finally:
        if status is not None:
            status.start()
    elapsed = time.perf_counter() - t0
    console.print(f"  {cli_prefix(MessageKind.SUCCESS)} {model} [{elapsed:.0f}s]")
    console.print()

    # Re-load to confirm Presidio's later spacy.load() will succeed (finding 23).
    spacy.load(model)

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
    "UK_NHS",
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
        # Do not include original_text — it contains PII that would leak into
        # logs and tracebacks.  Show length instead.
        return (
            f"PiiRedaction({self.entity_type}: "
            f"<{len(self.original_text)} chars> -> {self.replacement}, "
            f"score={self.score:.2f})"
        )


def remove_pii(
    transcripts: list[FullTranscript],
    settings: BristlenoseSettings,
    *,
    status: Status | None = None,
) -> tuple[list[PiiCleanTranscript], list[PiiRedaction]]:
    """Remove PII from transcripts using Presidio.

    Args:
        transcripts: Raw transcripts with PII.
        settings: Application settings.

    Returns:
        Tuple of (cleaned transcripts, all redactions across all sessions).
    """
    # Refuse configured-but-unimplemented fields rather than warning past them.
    #
    # Both stay deliberately unimplemented (D7, docs/design-redact-pii.md —
    # `pii_llm_pass` is the reserved stub for the planned regex + LLM-NER
    # approach, so it graduates rather than gets built against Presidio). The
    # defect was never that they do nothing; it was that they did nothing
    # *quietly*. A `warnings.warn` is shown once per location and is trivially
    # lost in a long run, so a researcher who listed the names they most wanted
    # gone got a run that reported redaction succeeded while those exact names
    # sat in `transcripts-cooked/` — fake success in a privacy guarantee, which
    # is the one place it cannot be tolerated. Fail closed: for a redaction
    # control, refusing to run is the only safe direction.
    unimplemented: list[str] = []
    if settings.pii_llm_pass:
        unimplemented.append(
            "pii_llm_pass — there is no LLM second pass; detection is Presidio-only"
        )
    if settings.pii_custom_names:
        unimplemented.append(
            f"pii_custom_names — the {count_noun(len(settings.pii_custom_names), 'name')} "
            "listed here would NOT be redacted"
        )
    if unimplemented:
        raise ValueError(
            "PII redaction was asked for settings it cannot honour:\n  - "
            + "\n  - ".join(unimplemented)
            + "\n\nUnset them to run with Presidio-only redaction, which is what "
            "the CLI ships today. They are reserved for the planned regex + LLM "
            "approach — see docs/design-redact-pii.md."
        )

    logger.info("Initialising Presidio (loads spaCy NLP model on first run)...")
    analyzer, anonymizer = _init_presidio(settings, status=status)

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
            # Clear word-level data — it contains the original unredacted text
            clean_seg.words = []
            clean_segments.append(clean_seg)

        clean_transcript = PiiCleanTranscript(
            session_id=transcript.session_id,
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
            transcript.session_id,
            total_entities,
        )

    return clean_transcripts, all_redactions


def write_cooked_transcripts(
    transcripts: list[PiiCleanTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write PII-cleaned ('cooked') transcript text files.

    Format uses the markdown style template from
    :mod:`bristlenose.utils.markdown`.

    Args:
        transcripts: Cleaned transcripts.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    from bristlenose.utils.markdown import (
        format_cooked_segment_txt,
        format_transcript_header_txt,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.txt (was s1_cooked.txt — directory name now indicates raw/cooked)
        filename = f"{transcript.session_id}.txt"
        path = output_dir / filename

        header = format_transcript_header_txt(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=transcript.session_date.isoformat(),
            duration=format_timecode(transcript.duration_seconds),
            label="Transcript (cooked)",
            extra_headers={
                "PII entities redacted": str(transcript.pii_entities_found),
            },
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(format_cooked_segment_txt(tc, code, seg.text))
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote cooked transcript: %s", path)

    return paths


def write_cooked_transcripts_md(
    transcripts: list[PiiCleanTranscript],
    output_dir: Path,
) -> list[Path]:
    """Write PII-cleaned transcript Markdown files alongside the .txt files.

    The ``.md`` version provides a more readable format with bold
    participant code labels and structured metadata.  Files are named
    ``{session_id}.md`` and placed in ``transcripts-cooked/``.

    Args:
        transcripts: Cleaned transcripts.
        output_dir: Directory to write to.

    Returns:
        List of written file paths.
    """
    from bristlenose.utils.markdown import (
        format_cooked_segment_md,
        format_transcript_header_md,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for transcript in transcripts:
        # New naming: s1.md (was s1_cooked.md)
        filename = f"{transcript.session_id}.md"
        path = output_dir / filename

        header = format_transcript_header_md(
            participant_id=transcript.session_id,
            source_file=transcript.source_file,
            session_date=transcript.session_date.isoformat(),
            duration=format_timecode(transcript.duration_seconds),
            label="Transcript (cooked)",
            extra_headers={
                "PII entities redacted": str(transcript.pii_entities_found),
            },
        )

        lines: list[str] = [header, ""]

        for seg in transcript.segments:
            tc = format_timecode(seg.start_time)
            code = seg.speaker_code or transcript.participant_id
            lines.append(format_cooked_segment_md(tc, code, seg.text))
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        paths.append(path)
        logger.info("Wrote cooked transcript (md): %s", path)

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
    # Write to .bristlenose/ hidden directory — the summary contains original
    # PII values for audit purposes and must not be shared with the output.
    internal_dir = output_dir / ".bristlenose"
    internal_dir.mkdir(parents=True, exist_ok=True)
    path = internal_dir / "pii_summary.txt"

    lines: list[str] = []
    lines.append("# CONFIDENTIAL — this file contains original personal data.")
    lines.append("# Do not share this file outside your research team.")
    lines.append("#")
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
    *,
    status: Status | None = None,
) -> tuple[object, object]:
    """Initialise Presidio analyzer and anonymizer.

    Returns:
        (AnalyzerEngine, AnonymizerEngine) tuple.
    """
    _ensure_spacy_model(allow_fetch=not settings.no_fetch, status=status)

    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine

    # Bind the analyzer to SPACY_MODEL explicitly. A bare AnalyzerEngine()
    # silently takes Presidio's own default, which is what let the fetched and
    # the used model diverge in the first place.
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": resolve_spacy_model()}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
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
        score_threshold=settings.pii_score_threshold,
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
