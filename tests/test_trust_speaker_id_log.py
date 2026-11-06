"""Stage 5b must not write a participant's real name to the log (finding F6-1, audit n6a1, 6 Nov 2026).

A platform transcript labels speakers with real names. identify_speaker_roles_llm logs its role map at INFO,
keyed by those labels, ahead of PII redaction. The policy (bristlenose/logging.py) says logs carry no names.
This is a KNOWN DEFECT held as a strict xfail: the day the line stops logging the label, the xfail turns into
a failure and the marker must come off. Positive control: the same call must log through this stage's logger
at all, or the assertion proves nothing. Proven with docs/private/trust-map/audit_tools.py mutate (replace the
logged role_map with its roles only: the strict xfail must then fail).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import bristlenose
from bristlenose.llm.structured import SpeakerRoleAssignment, SpeakerRoleItem
from bristlenose.models import TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import identify_speaker_roles_llm

NAME = "Zephyrine Quillfeather"


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def _run(caplog: pytest.LogCaptureFixture) -> list[str]:
    segments = [
        TranscriptSegment(start_time=1.0, end_time=4.0, text="Hello, thanks for joining.",
                          speaker_label="Interviewer"),
        TranscriptSegment(start_time=5.0, end_time=9.0, text="Happy to be here.", speaker_label=NAME),
    ]
    result = SpeakerRoleAssignment(assignments=[
        SpeakerRoleItem(speaker_label="Interviewer", role="researcher", reasoning="asks questions"),
        SpeakerRoleItem(speaker_label=NAME, role="participant", reasoning="answers"),
    ])
    client = MagicMock()
    client.analyze = AsyncMock(return_value=result)
    caplog.set_level(logging.INFO, logger="bristlenose.stages.s05b_identify_speakers")
    caplog.clear()
    asyncio.run(identify_speaker_roles_llm(segments, client))
    return [r.getMessage() for r in caplog.records
            if r.name == "bristlenose.stages.s05b_identify_speakers"]


def test_the_stage_logs_through_its_own_logger(caplog: pytest.LogCaptureFixture) -> None:
    """Positive control: without a record from this logger the name assertion below is vacuous."""
    assert _run(caplog), "no INFO record from the speaker-identification stage"


@pytest.mark.xfail(strict=True, reason="F6-1: the INFO role map is keyed by the speaker label, which on "
                   "platform transcripts is the participant's real name")
def test_the_stage_does_not_log_a_speaker_label_that_is_a_name(caplog: pytest.LogCaptureFixture) -> None:
    messages = _run(caplog)
    assert messages, "positive control: nothing logged"
    assert not any(NAME in m or "Quillfeather" in m for m in messages)
