"""PII redaction audit — adversarial test transcript.

Two test layers:

1. **Config tests** (CI-safe): Verify score threshold, default entities, and
   runtime warnings for unimplemented config fields.

2. **Detection tests** (``@pytest.mark.slow``, skipped in CI): Run the horror-
   show transcript through Presidio and check what gets caught vs missed.
   Requires ``presidio-analyzer``, ``presidio-anonymizer``, and the spaCy
   ``en_core_web_lg`` model.  Run manually with ``pytest -m slow``.

The horror transcript (``tests/fixtures/pii_horror_transcript.txt``) contains
PII planted across 8 adversarial categories.  Expected results are in
``tests/fixtures/pii_horror_expected.yaml``.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from bristlenose.config import BristlenoseSettings

FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPT_PATH = FIXTURES / "pii_horror_transcript.txt"
EXPECTED_PATH = FIXTURES / "pii_horror_expected.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_expected() -> list[dict]:
    """Load the expected PII items from the YAML fixture."""
    raw = yaml.safe_load(EXPECTED_PATH.read_text(encoding="utf-8"))
    return raw["items"]


def _parse_transcript_segments() -> list[tuple[str, str]]:
    """Parse the horror transcript into (timecode, text) pairs.

    Returns a list of (timecode_str, segment_text) tuples, ignoring
    header lines (starting with #) and blank lines.
    """
    import re

    segments: list[tuple[str, str]] = []
    for line in TRANSCRIPT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"\[(\d+:\d+)\]\s+\[\w+\]\s+(.*)", line)
        if m:
            segments.append((m.group(1), m.group(2)))
    return segments


def _timecode_to_seconds(tc: str) -> float:
    """Convert MM:SS to seconds."""
    parts = tc.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ---------------------------------------------------------------------------
# Layer 1: Config tests (CI-safe)
# ---------------------------------------------------------------------------


class TestPiiConfig:
    """Tests for PII configuration fields."""

    def test_default_score_threshold(self) -> None:
        settings = BristlenoseSettings()
        assert settings.pii_score_threshold == 0.7

    def test_custom_score_threshold(self) -> None:
        settings = BristlenoseSettings(pii_score_threshold=0.5)
        assert settings.pii_score_threshold == 0.5

    def test_score_threshold_bounds_low(self) -> None:
        with pytest.raises(Exception):
            BristlenoseSettings(pii_score_threshold=-0.1)

    def test_score_threshold_bounds_high(self) -> None:
        with pytest.raises(Exception):
            BristlenoseSettings(pii_score_threshold=1.1)

    def test_uk_nhs_in_default_entities(self) -> None:
        """UK_NHS must be in the default entity list (regression guard)."""
        from bristlenose.stages.s07_pii_removal import _DEFAULT_ENTITIES

        assert "UK_NHS" in _DEFAULT_ENTITIES

    def test_repr_no_original_text(self) -> None:
        """PiiRedaction.__repr__ must not contain the original PII text."""
        from bristlenose.stages.s07_pii_removal import PiiRedaction

        r = PiiRedaction(
            entity_type="PERSON",
            original_text="Sarah Thompson",
            replacement="[NAME]",
            score=0.95,
            timecode=12.0,
        )
        repr_str = repr(r)
        assert "Sarah Thompson" not in repr_str
        assert "<14 chars>" in repr_str

    def test_warning_pii_llm_pass(self) -> None:
        """Setting pii_llm_pass=True should emit a warning."""
        settings = BristlenoseSettings(pii_enabled=True, pii_llm_pass=True)
        # We need to call remove_pii to trigger the warning, but we can't
        # without Presidio.  Instead, test the warning logic directly.
        from bristlenose.stages.s07_pii_removal import remove_pii

        with warnings.catch_warnings(record=True) as w, \
                patch("bristlenose.stages.s07_pii_removal._init_presidio") as mock_init:
            mock_init.return_value = (MagicMock(), MagicMock())
            warnings.simplefilter("always")
            remove_pii([], settings)
            warning_messages = [str(x.message) for x in w]
            assert any("pii_llm_pass" in msg for msg in warning_messages)

    def test_warning_pii_custom_names(self) -> None:
        """Setting pii_custom_names should emit a warning."""
        settings = BristlenoseSettings(
            pii_enabled=True,
            pii_custom_names=["Sarah Thompson"],
        )
        from bristlenose.stages.s07_pii_removal import remove_pii

        with warnings.catch_warnings(record=True) as w, \
                patch("bristlenose.stages.s07_pii_removal._init_presidio") as mock_init:
            mock_init.return_value = (MagicMock(), MagicMock())
            warnings.simplefilter("always")
            remove_pii([], settings)
            warning_messages = [str(x.message) for x in w]
            assert any("pii_custom_names" in msg for msg in warning_messages)

    def test_no_warning_default_config(self) -> None:
        """Default config should not emit warnings."""
        settings = BristlenoseSettings(pii_enabled=True)
        from bristlenose.stages.s07_pii_removal import remove_pii

        with warnings.catch_warnings(record=True) as w, \
                patch("bristlenose.stages.s07_pii_removal._init_presidio") as mock_init:
            mock_init.return_value = (MagicMock(), MagicMock())
            warnings.simplefilter("always")
            remove_pii([], settings)
            warning_messages = [str(x.message) for x in w]
            assert not any("pii_llm_pass" in msg for msg in warning_messages)
            assert not any("pii_custom_names" in msg for msg in warning_messages)


class TestPiiSummaryLocation:
    """Tests for pii_summary.txt placement in .bristlenose/ directory."""

    def test_summary_written_to_hidden_dir(self, tmp_path: Path) -> None:
        """pii_summary.txt must be in .bristlenose/, not the output root."""
        from bristlenose.stages.s07_pii_removal import PiiRedaction, write_pii_summary

        redactions = [
            PiiRedaction(
                entity_type="PERSON",
                original_text="Test Name",
                replacement="[NAME]",
                score=0.9,
                timecode=0.0,
            )
        ]
        result = write_pii_summary(redactions, tmp_path)
        assert result is not None
        assert result.parent.name == ".bristlenose"
        assert not (tmp_path / "pii_summary.txt").exists()
        assert (tmp_path / ".bristlenose" / "pii_summary.txt").exists()

    def test_summary_has_confidentiality_header(self, tmp_path: Path) -> None:
        from bristlenose.stages.s07_pii_removal import PiiRedaction, write_pii_summary

        redactions = [
            PiiRedaction(
                entity_type="PERSON",
                original_text="Test Name",
                replacement="[NAME]",
                score=0.9,
                timecode=0.0,
            )
        ]
        write_pii_summary(redactions, tmp_path)
        content = (tmp_path / ".bristlenose" / "pii_summary.txt").read_text()
        assert "CONFIDENTIAL" in content


class TestWordLeakPrevention:
    """Tests that Word objects are cleared during PII redaction."""

    def test_words_cleared_after_redaction(self) -> None:
        """Redacted segments must have empty words list."""
        from datetime import datetime

        from bristlenose.models import FullTranscript, TranscriptSegment, Word
        from bristlenose.stages.s07_pii_removal import remove_pii

        seg = TranscriptSegment(
            start_time=0.0,
            end_time=5.0,
            text="My name is Test Person",
            words=[
                Word(text="My", start_time=0.0, end_time=0.5),
                Word(text="name", start_time=0.5, end_time=1.0),
                Word(text="is", start_time=1.0, end_time=1.3),
                Word(text="Test", start_time=1.3, end_time=1.8),
                Word(text="Person", start_time=1.8, end_time=2.3),
            ],
        )
        transcript = FullTranscript(
            session_id="s1",
            participant_id="p1",
            source_file="test.mp4",
            session_date=datetime(2025, 1, 1),
            duration_seconds=300.0,
            segments=[seg],
        )
        settings = BristlenoseSettings(pii_enabled=True)

        with patch("bristlenose.stages.s07_pii_removal._init_presidio") as mock_init, \
                patch("bristlenose.stages.s07_pii_removal._redact_text") as mock_redact:
            mock_init.return_value = (MagicMock(), MagicMock())
            mock_redact.return_value = ("[NAME] said hello", [])

            clean_transcripts, _ = remove_pii([transcript], settings)
            # Words must be cleared even if no PII was found in this segment
            assert clean_transcripts[0].segments[0].words == []


# ---------------------------------------------------------------------------
# Layer 2: Presidio detection tests (slow — requires spaCy model)
# ---------------------------------------------------------------------------

# Check if Presidio + spaCy are available
try:
    import spacy  # noqa: F401
    from presidio_analyzer import AnalyzerEngine  # noqa: F401

    _nlp = spacy.load("en_core_web_lg")
    _HAS_PRESIDIO = True
    del _nlp
except (ImportError, OSError):
    _HAS_PRESIDIO = False

_skip_no_presidio = pytest.mark.skipif(
    not _HAS_PRESIDIO,
    reason="Requires presidio-analyzer + spacy en_core_web_lg model",
)


@_skip_no_presidio
@pytest.mark.slow
class TestPresidioDetection:
    """Run Presidio against the horror transcript and check each planted item.

    Tests marked should_catch=true in the YAML are expected to pass.
    Tests marked should_catch=false are expected to fail (xfail).
    """

    @pytest.fixture(autouse=True)
    def _setup_presidio(self) -> None:
        from presidio_analyzer import AnalyzerEngine

        from bristlenose.stages.s07_pii_removal import _DEFAULT_ENTITIES

        self.analyzer = AnalyzerEngine()
        self.entities = _DEFAULT_ENTITIES
        self.segments = _parse_transcript_segments()

    def _find_segment_text(self, timecode: str | None) -> str | None:
        """Find the segment text for a given timecode."""
        if timecode is None:
            return None
        for tc, text in self.segments:
            if tc == timecode:
                return text
        return None

    def _presidio_finds(self, text: str, target: str) -> bool:
        """Check if Presidio detects the target text within the segment."""
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.entities,
            score_threshold=0.7,
        )
        for r in results:
            detected = text[r.start:r.end]
            # Check if the target is within or overlaps the detected span
            if target in detected or detected in target:
                return True
        return False

    @pytest.fixture(params=_load_expected() if EXPECTED_PATH.exists() else [])
    def pii_item(self, request: pytest.FixtureRequest) -> dict:
        return request.param

    def test_pii_detection(self, pii_item: dict) -> None:
        """Parametrised test: one per PII item in the YAML."""
        text = pii_item["text"]
        timecode = pii_item.get("segment_time")
        should_catch = pii_item["should_catch"]
        category = pii_item["category"]
        notes = pii_item.get("notes", "")

        segment_text = self._find_segment_text(timecode)

        if segment_text is None:
            if not should_catch:
                pytest.skip(f"No segment for {text!r} (category {category})")
            pytest.fail(f"Could not find segment at {timecode} for {text!r}")

        found = self._presidio_finds(segment_text, text)

        if should_catch:
            assert found, (
                f"Presidio MISSED (should catch): {text!r} "
                f"in segment [{timecode}]. {notes}"
            )
        else:
            # We expect Presidio to miss these — if it catches them, great!
            if found:
                pytest.xfail(
                    f"Presidio CAUGHT (expected miss): {text!r} "
                    f"in segment [{timecode}]. {notes}"
                )
            # Confirm the expected gap
            assert not found, (
                f"Expected Presidio to miss {text!r} but it caught it. "
                f"Update YAML should_catch to true. {notes}"
            )
