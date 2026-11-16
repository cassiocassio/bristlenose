"""The CLI stats line counts participants of analysed sessions, not failed ones."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from bristlenose import cli
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    PipelineSummary,
    StageFailure,
    StageOutcome,
)
from bristlenose.models import PeopleFile, PersonComputed, PersonEditable, PersonEntry

_T = datetime(2026, 9, 22)


def _entry(pid: str, sid: str, name: str = "") -> PersonEntry:
    return PersonEntry(
        computed=PersonComputed(
            participant_id=pid, session_id=sid, session_date=_T, duration_seconds=0.0,
            words_spoken=0, pct_words=0.0, pct_time_speaking=0.0, source_file="x",
        ),
        editable=PersonEditable(short_name=name),
    )


def _result(failed_sids: list[str], transcribed: tuple[str, ...] = ()) -> SimpleNamespace:
    sessions = [SimpleNamespace(session_id=f"s{i}", participant_id=f"p{i}") for i in range(1, 6)]
    people = PeopleFile(participants={
        f"p{i}": _entry(f"p{i}", f"s{i}", "Ann" if i <= 3 else "") for i in range(1, 6)
    })
    failed = [
        StageFailure(session_id=s, cause=Cause(
            category=CauseCategoryEnum.UNUSABLE_INPUT, message="x", stage="s03", session_id=s))
        for s in failed_sids
    ]
    summary = PipelineSummary(transcripts=StageOutcome(attempted=5, succeeded=5 - len(failed), failed=failed))
    raw = [SimpleNamespace(session_id=s) for s in transcribed]
    return SimpleNamespace(
        participants=sessions, people=people, summary=summary, raw_transcripts=raw
    )


def _stats_line(result, capsys) -> str:
    cli._print_pipeline_summary(result)
    return capsys.readouterr().out


def test_failed_sessions_are_not_counted(capsys: pytest.CaptureFixture[str]) -> None:
    out = _stats_line(_result(["s4", "s5"]), capsys)
    assert "3 participants" in out and "5 participants" not in out
    assert "of 5 named" not in out


def test_control_nothing_failed_counts_all(capsys: pytest.CaptureFixture[str]) -> None:
    out = _stats_line(_result([]), capsys)
    assert "5 participants (3 of 5 named)" in out


def test_a_failed_file_beside_a_read_transcript_still_counts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # s4 had a bad .vtt but its recording was transcribed: it is analysed.
    out = _stats_line(_result(["s4", "s5"], transcribed=("s4",)), capsys)
    assert "4 participants" in out
