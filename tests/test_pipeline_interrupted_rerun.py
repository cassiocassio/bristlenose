"""A re-run that is stopped must not make the next run pay for every session.

Each run writes a fresh manifest, and each stage writes its record only when it
ends, so a stop left only the stages before it on disk; the next run found no
record of the rest and redid them for every session, unchanged ones included
(Whisper and LLM spend the researcher never asked for). The previous run's
manifest is now held beside it for resume until a run completes.

Real ``Pipeline.run`` and real manifest; ingest, stage 2, Whisper and every LLM
stage are stubbed (the harness of ``test_pipeline_platform_transcripts``).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import StageOutcome
from bristlenose.manifest import RESUME_FILENAME
from bristlenose.models import FileType, SessionTopicMap
from bristlenose.pipeline import Pipeline
from tests.conftest import iter_transcribe_from
from tests.test_pipeline_platform_transcripts import _quote, _whisper_segments, audio_session

# These drive the whole pipeline to test other stages; the discussion stage,
# on by default, would run on the mocked client and log its failure every
# drive, unasserted (conftest.no_discussion_stage; #109, decision #97 follow-up).
pytestmark = pytest.mark.usefixtures("no_discussion_stage")


def _drive(tmp_path: Path, n_sessions: int, log: dict, stop_in: str | None = None) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    settings = BristlenoseSettings(
        project_name="rerun", skip_transcription=False, write_intermediate=True,
        llm_concurrency=1, no_fetch=True, pii_enabled=False, whisper_language="auto",
    )

    def _ingest(_d, _declined=None, **_kw):
        return [audio_session(input_dir, i, f"rec{i}") for i in range(1, n_sessions + 1)]

    async def _stage2(sess, _tmp, **_kw):
        if stop_in == "stage2":
            raise KeyboardInterrupt
        for s in sess:
            if s.audio_path is None:
                s.audio_path = next(f.path for f in s.files if f.file_type == FileType.AUDIO)
        return sess

    def _transcribe(sessions, _settings, **_kw):
        sids = [s.session_id for s in sessions]
        log.setdefault("transcribed", []).append(sids)
        if stop_in == "transcribe":
            raise KeyboardInterrupt
        return ({sid: _whisper_segments(sid) for sid in sids}, {},
                StageOutcome(attempted=len(sids), succeeded=len(sids)))

    async def _split(segments, _c, errors=None):
        for i, seg in enumerate(segments):
            seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
        return segments

    async def _roles(segments, _c, errors=None):
        return []

    async def _topics(transcripts, *_a, **_kw):
        log.setdefault("topics", []).append(sorted(t.session_id for t in transcripts))
        if stop_in == "topics":
            raise KeyboardInterrupt
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[]) for t in transcripts]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, *_a, **_kw):
        log.setdefault("quoted", []).append(sorted(t.session_id for t in transcripts))
        quotes = [_quote(t.session_id, t.participant_id, n) for t in transcripts for n in range(3)]
        return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

    async def _one(_quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    with (
        patch("bristlenose.stages.s01_ingest.ingest", new=_ingest),
        patch("bristlenose.stages.s02_extract_audio.extract_audio_for_sessions", new=_stage2),
        patch("bristlenose.preflight.whisper.preflight_whisper", new=lambda **_kw: None),
        patch("bristlenose.stages.s05_transcribe.iter_transcribe_sessions",
              new=iter_transcribe_from(_transcribe)),
        patch("bristlenose.stages.s05b_identify_speakers.split_single_speaker_llm", new=_split),
        patch("bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm", new=_roles),
        patch("bristlenose.stages.s08_topic_segmentation.segment_topics", new=_topics),
        patch("bristlenose.stages.s09_quote_extraction.extract_quotes", new=_quotes),
        patch("bristlenose.stages.s10_quote_clustering.cluster_by_screen", new=_one),
        patch("bristlenose.stages.s11_thematic_grouping.group_by_theme", new=_one),
        patch("bristlenose.llm.client.LLMClient", MagicMock()),
    ):
        asyncio.run(Pipeline(settings).run(input_dir, tmp_path / "output"))


def _resume_file(tmp_path: Path) -> Path:
    return tmp_path / "output" / ".bristlenose" / RESUME_FILENAME


@pytest.mark.parametrize("stop_in", ["stage2", "transcribe", "topics"])
def test_a_stopped_rerun_costs_only_the_new_session(tmp_path: Path, stop_in: str) -> None:
    _drive(tmp_path, 2, {})

    # The researcher adds a third recording, re-runs, and the run is stopped.
    with pytest.raises(KeyboardInterrupt):
        _drive(tmp_path, 3, {}, stop_in=stop_in)

    after: dict = {}
    _drive(tmp_path, 3, after)

    # Only the new recording is transcribed, segmented and quoted. Before the
    # fix the stop erased the earlier records and every session was redone.
    if stop_in != "topics":  # a stop in topics comes after transcription finished
        assert after["transcribed"] == [["s3"]], after
    assert after["topics"] == [["s3"]], after
    assert after["quoted"] == [["s3"]], after


def test_a_completed_run_releases_the_held_manifest(tmp_path: Path) -> None:
    _drive(tmp_path, 2, {})
    assert not _resume_file(tmp_path).exists()

    with pytest.raises(KeyboardInterrupt):
        _drive(tmp_path, 3, {}, stop_in="transcribe")
    assert _resume_file(tmp_path).exists()

    _drive(tmp_path, 3, {})
    assert not _resume_file(tmp_path).exists()


def test_two_stops_in_a_row_keep_the_first_runs_work(tmp_path: Path) -> None:
    _drive(tmp_path, 2, {})
    with pytest.raises(KeyboardInterrupt):
        _drive(tmp_path, 3, {}, stop_in="stage2")
    with pytest.raises(KeyboardInterrupt):
        _drive(tmp_path, 3, {}, stop_in="stage2")

    after: dict = {}
    _drive(tmp_path, 3, after)
    assert after["topics"] == [["s3"]], after
    assert after["quoted"] == [["s3"]], after


def test_an_unreadable_held_manifest_is_ignored(tmp_path: Path) -> None:
    _drive(tmp_path, 2, {})
    with pytest.raises(KeyboardInterrupt):
        _drive(tmp_path, 3, {}, stop_in="stage2")
    _resume_file(tmp_path).write_text("{ truncated", encoding="utf-8")

    after: dict = {}
    _drive(tmp_path, 3, after)  # must not crash; it just has less to reuse
    assert after["transcribed"] == [["s1", "s2", "s3"]], after
