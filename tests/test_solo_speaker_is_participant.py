"""A session with one speaker is a solo think-aloud: its speaker is p1, never m1.

Found in own use, 8 Nov 2026, recording the Google Meet verification demo: two
recordings of one person speaking, each with a Meet transcript naming one
account. The heuristic pass already called the lone speaker a participant, but
the LLM role pass overruled it with "researcher", so both sessions were coded
m1, quote extraction (participants only) found nothing, and the run ended
"No usable content found".

Owner rule (8 Nov 2026): one speaker is one research subject doing a solo
think-aloud. Coded p1, no m1, whatever the model says. The person's name the
model read from the transcript is still kept.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import bristlenose
from bristlenose.llm.structured import SpeakerRoleAssignment, SpeakerRoleItem
from bristlenose.models import SpeakerRole, TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import (
    assign_speaker_codes,
    identify_speaker_roles_heuristic,
    identify_speaker_roles_llm,
)

SOLO = "Ada Lovelace-Byron"


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def _client(*items: SpeakerRoleItem) -> MagicMock:
    client = MagicMock()
    client.analyze = AsyncMock(return_value=SpeakerRoleAssignment(assignments=list(items)))
    return client


def _identify(segments: list[TranscriptSegment], client: MagicMock):
    """Stage 5b as `SpeakerPass._run` runs it: heuristic, then the model."""
    identify_speaker_roles_heuristic(segments)
    return asyncio.run(identify_speaker_roles_llm(segments, client))


def _solo_session() -> list[TranscriptSegment]:
    return [
        TranscriptSegment(start_time=0.0, end_time=4.0, speaker_label=SOLO,
                          text="I'm the user researcher on this account, testing the import."),
        TranscriptSegment(start_time=5.0, end_time=12.0, speaker_label=SOLO,
                          text="Okay, so I'd expect the checkout button to be here, but it isn't."),
    ]


def test_a_lone_speaker_the_model_calls_a_researcher_is_coded_p1() -> None:
    segments = _solo_session()
    client = _client(SpeakerRoleItem(speaker_label=SOLO, role="researcher",
                                     reasoning="introduces themself as the researcher",
                                     person_name="Ada"))

    infos = _identify(segments, client)
    codes, next_number = assign_speaker_codes(1, segments)

    assert client.analyze.await_count == 1, "positive control: the model was asked"
    assert codes == {SOLO: "p1"}
    assert {seg.speaker_code for seg in segments} == {"p1"}
    assert next_number == 2
    assert [(i.speaker_label, i.role) for i in infos] == [(SOLO, SpeakerRole.PARTICIPANT)]
    assert infos[0].person_name == "Ada", "the name the model read is still kept"


def test_two_speakers_keep_the_models_roles() -> None:
    """Control: the rule is about one speaker, not about overruling the model."""
    segments = [
        TranscriptSegment(start_time=0.0, end_time=3.0, speaker_label="Interviewer",
                          text="What did you expect to happen there?"),
        TranscriptSegment(start_time=4.0, end_time=9.0, speaker_label=SOLO,
                          text="I thought it would save my basket."),
    ]
    client = _client(
        SpeakerRoleItem(speaker_label="Interviewer", role="researcher", reasoning="asks"),
        SpeakerRoleItem(speaker_label=SOLO, role="participant", reasoning="answers"),
    )

    _identify(segments, client)
    codes, _ = assign_speaker_codes(1, segments)

    assert codes == {"Interviewer": "m1", SOLO: "p1"}
