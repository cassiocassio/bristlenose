"""BR-07 (owner ruling B, 16 Nov 2026): a model that returns no researcher in a
2+ speaker session cannot remove the researcher the heuristic found.

An unmoderated study (heuristic found no researcher) is unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from bristlenose.llm.structured import SpeakerRoleAssignment, SpeakerRoleItem
from bristlenose.models import SpeakerRole, TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import (
    identify_speaker_roles_heuristic,
    identify_speaker_roles_llm,
)


def _client(*roles: tuple[str, str]) -> MagicMock:
    client = MagicMock()
    client.analyze = AsyncMock(return_value=SpeakerRoleAssignment(assignments=[
        SpeakerRoleItem(speaker_label=lbl, role=role, reasoning="x") for lbl, role in roles
    ]))
    return client


def _seg(t: float, who: str, text: str) -> TranscriptSegment:
    return TranscriptSegment(start_time=t, end_time=t + 4, speaker_label=who, text=text)


def _moderated() -> list[TranscriptSegment]:
    return [
        _seg(0, "Sarah", "Thanks for joining today, there are no right or wrong answers."),
        _seg(5, "Tom", "Thanks for having me."),
        _seg(10, "Sarah", "Can you walk me through how you usually search? What do you do first?"),
        _seg(20, "Tom", "I usually just type into the box and scroll for a while."),
        _seg(30, "Sarah", "And what happens next? How did that feel?"),
        _seg(40, "Tom", "Honestly a bit slow, I gave up the first time."),
    ]


def _unmoderated() -> list[TranscriptSegment]:
    return [
        _seg(0, "Ann", "I think I would click the big blue button here to continue."),
        _seg(10, "Bob", "I agree, that looks like what I would do on my own phone."),
        _seg(20, "Ann", "Hm, it is a bit slow though and I am not sure about the colours."),
        _seg(30, "Bob", "Yes I did not expect the page to reload like that at all."),
    ]


def _run(segs: list[TranscriptSegment], client: MagicMock):
    identify_speaker_roles_heuristic(segs)
    before = {s.speaker_label: s.speaker_role for s in segs}
    infos = asyncio.run(identify_speaker_roles_llm(segs, client))
    return before, infos


def test_model_without_researcher_keeps_the_heuristic_researcher(caplog) -> None:
    segs = _moderated()
    client = _client(("Sarah", "participant"), ("Tom", "participant"))
    with caplog.at_level(logging.INFO):
        before, infos = _run(segs, client)
    assert client.analyze.await_count == 1, "control: the model was asked"
    assert before["Sarah"] == SpeakerRole.RESEARCHER, "precondition: heuristic found the researcher"
    roles = {s.speaker_label: s.speaker_role for s in segs}
    assert roles == {"Sarah": SpeakerRole.RESEARCHER, "Tom": SpeakerRole.PARTICIPANT}
    assert {i.speaker_label: i.role for i in infos}["Sarah"] == SpeakerRole.RESEARCHER
    log = " ".join(r.getMessage() for r in caplog.records)
    assert "heuristic_researchers=1" in log and "speakers=2" in log
    ours = " ".join(m for m in (r.getMessage() for r in caplog.records) if "keeping" in m)
    assert ours and "Sarah" not in ours and "Tom" not in ours, "counts only, no names"


def test_unmoderated_study_stays_as_the_model_says() -> None:
    segs = _unmoderated()
    client = _client(("Ann", "participant"), ("Bob", "participant"))
    before, _ = _run(segs, client)
    assert before["Bob"] == SpeakerRole.RESEARCHER, "precondition: the heuristic ranks someone"
    # The heuristic ranks someone first even here (Bob); it has no evidence, so the
    # model's "no researcher" stands and the study stays unmoderated.
    assert {s.speaker_role for s in segs} == {SpeakerRole.PARTICIPANT}


def test_model_that_names_a_researcher_still_wins() -> None:
    segs = _moderated()
    client = _client(("Sarah", "participant"), ("Tom", "researcher"))
    _run(segs, client)
    roles = {s.speaker_label: s.speaker_role for s in segs}
    assert roles == {"Sarah": SpeakerRole.PARTICIPANT, "Tom": SpeakerRole.RESEARCHER}


def _question_asker() -> list[TranscriptSegment]:
    return [
        _seg(0, "Sarah", "Where do you start? What do you see first?"),
        _seg(5, "Tom", "I start at the top."),
        _seg(10, "Sarah", "And then? Does that feel right?"),
        _seg(15, "Tom", "Mostly."),
        _seg(20, "Sarah", "Why is that? What would you change?"),
        _seg(25, "Tom", "The colours."),
    ]


def test_three_questions_over_half_their_turns_is_evidence() -> None:
    segs = _question_asker()
    _run(segs, _client(("Sarah", "participant"), ("Tom", "participant")))
    assert {s.speaker_label: s.speaker_role for s in segs}["Sarah"] == SpeakerRole.RESEARCHER


def test_a_guest_phrase_blocks_the_override() -> None:
    segs = _moderated()
    segs.append(_seg(50, "Sarah", "Thanks for having me, do you want me to share my screen?"))
    _run(segs, _client(("Sarah", "participant"), ("Tom", "participant")))
    assert {s.speaker_label: s.speaker_role for s in segs}["Sarah"] == SpeakerRole.PARTICIPANT


def test_a_model_observer_is_not_turned_into_a_researcher() -> None:
    segs = _moderated()
    _run(segs, _client(("Sarah", "observer"), ("Tom", "participant")))
    assert {s.speaker_label: s.speaker_role for s in segs}["Sarah"] == SpeakerRole.OBSERVER


def test_a_model_researcher_with_an_unknown_label_does_not_hide_the_gap() -> None:
    segs = _moderated()
    _run(segs, _client(("Speaker Z", "researcher"), ("Sarah", "participant"),
                       ("Tom", "participant")))
    assert {s.speaker_label: s.speaker_role for s in segs}["Sarah"] == SpeakerRole.RESEARCHER
