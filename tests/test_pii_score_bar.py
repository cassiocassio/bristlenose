"""The two-bar score policy — PERSON strict, pattern-matched entities relaxed.

Measured 12 Sep 2026 on the planted-PII corpus, end to end through
`remove_pii`: at a flat 0.7, **2 of 8 planted phone numbers were redacted**.
Presidio's `PhoneRecognizer` scores a bare match 0.4 and only reaches ~0.75
when a context word ("call", "mobile") happens to sit nearby, so a participant
who simply reads their number out was not redacted. That is a false negative in
a privacy control — the failure direction that matters — and it is invisible to
any test that feeds the detector a sentence containing the word "phone".

Splitting the bar took it to 7 of 8 **with the false-positive count unchanged**
(9 of 32 planted near-miss probes, all product-names-that-are-also-people, both
before and after), because PERSON's bar never moves.

These tests are fast: they exercise the policy, not the model. One slow test
below asserts the behaviour end to end for anyone who has the 425 MB model.
"""

from __future__ import annotations

import pytest

from bristlenose.stages.s07_pii_removal import (
    _ENTITY_MAP,
    _STRUCTURED_ENTITIES,
    analysis_floor,
    score_bar,
)

_DEFAULT = 0.7


class TestTheTwoBars:
    def test_a_bare_phone_match_clears_its_bar(self) -> None:
        """0.4 is exactly what Presidio scores an uncontextualised phone."""
        assert score_bar("PHONE_NUMBER", _DEFAULT) <= 0.4

    def test_person_keeps_the_configured_bar(self) -> None:
        """The whole point of targeting: PERSON over-firing destroys research data.

        `_ENTITY_MAP`'s LOCATION comment is the precedent — "Oxford Street IKEA"
        becoming "[ADDRESS] IKEA". A blanket threshold drop would reintroduce
        that class for PERSON.
        """
        assert score_bar("PERSON", _DEFAULT) == _DEFAULT

    def test_date_time_is_deliberately_not_relaxed(self) -> None:
        """Context-sensitive, not pattern-matched — "last Tuesday" is not PII."""
        assert "DATE_TIME" not in _STRUCTURED_ENTITIES
        assert score_bar("DATE_TIME", _DEFAULT) == _DEFAULT

    @pytest.mark.parametrize("entity", sorted(_STRUCTURED_ENTITIES))
    def test_every_structured_entity_is_a_real_mapped_entity(self, entity: str) -> None:
        """A typo here silently does nothing — the name would just never match."""
        assert entity in _ENTITY_MAP, (
            f"{entity} is in _STRUCTURED_ENTITIES but not _ENTITY_MAP, so it is "
            f"either never detected or never labelled — the relaxed bar is dead"
        )


class TestTheKnobStillWorksDownwards:
    """A floor that could *raise* a bar would invert the setting below 0.4."""

    def test_a_lower_configured_threshold_lowers_structured_too(self) -> None:
        assert score_bar("PHONE_NUMBER", 0.2) == 0.2
        assert score_bar("PERSON", 0.2) == 0.2

    def test_the_floor_never_raises_a_bar(self) -> None:
        for configured in (0.0, 0.1, 0.35, 0.4, 0.5, 0.7, 0.9, 1.0):
            for entity in ("PHONE_NUMBER", "PERSON", "DATE_TIME"):
                assert score_bar(entity, configured) <= configured, (
                    f"{entity} at configured={configured} was RAISED to "
                    f"{score_bar(entity, configured)}"
                )

    def test_analysis_floor_is_never_above_any_entity_bar(self) -> None:
        """Anything analysed above an entity's own bar can never be seen."""
        for configured in (0.2, 0.5, 0.7, 0.95):
            floor = analysis_floor(configured)
            for entity in list(_ENTITY_MAP) + ["PERSON"]:
                assert floor <= score_bar(entity, configured), (
                    f"{entity} would be filtered on a score analyze() never returned"
                )


@pytest.mark.slow
def test_a_phone_with_no_context_word_is_redacted_end_to_end() -> None:
    """The measured defect, pinned against the real detector.

    Needs `en_core_web_lg`. Deselected by default (`addopts`), like every other
    presidio test — see CLAUDE.md. The sentence deliberately carries **no**
    context word, which is the case a flat 0.7 missed.
    """
    from datetime import datetime, timezone

    from bristlenose.config import BristlenoseSettings
    from bristlenose.models import FullTranscript, TranscriptSegment
    from bristlenose.stages.s07_pii_removal import remove_pii

    # Ofcom reserved drama range — never allocated to a real subscriber.
    number = "07700 900412"
    transcript = FullTranscript(
        session_id="s1",
        participant_id="p1",
        source_file="x.txt",
        session_date=datetime.now(timezone.utc),
        duration_seconds=30.0,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=5.0,
                text=f"Yeah it's {number} and I check it most evenings.",
                source="whisper",
                segment_index=0,
            )
        ],
    )
    settings = BristlenoseSettings(project_name="t", pii_enabled=True)
    clean, _ = remove_pii([transcript], settings)
    assert number not in clean[0].segments[0].text
