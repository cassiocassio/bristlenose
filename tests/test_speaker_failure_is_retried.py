"""A failed speaker-identification call is retried on the next run (R97).

When the role call (or the split call) for one session failed, the heuristic's
roles stood, and the session was recorded complete anyway, so every later run
served those roles from the cache and never asked again. It is now recorded
failed: the stage reads partial, and the next run asks for that session only.

Real ``Pipeline.run`` and real manifest; everything else is the stub harness of
``test_pipeline_interrupted_rerun``. Both places that identify speakers are
driven: the readable chain (a first analysis) and stage 5b's own loop.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import StageOutcome
from bristlenose.manifest import STAGE_IDENTIFY_SPEAKERS, StageStatus, load_manifest
from bristlenose.models import FileType, SessionTopicMap
from bristlenose.pipeline import Pipeline
from tests.conftest import iter_transcribe_from
from tests.test_pipeline_platform_transcripts import _quote, _whisper_segments, audio_session


def _sid(segments) -> str:
    m = re.search(r"the (s\d+) session", " ".join(s.text for s in segments))
    assert m, "the stub transcript names its session"
    return m.group(1)


def _drive(tmp_path: Path, asked: list[str], *, fail: set[str], chain: bool) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    settings = BristlenoseSettings(
        project_name="speakers", skip_transcription=False, write_intermediate=True,
        llm_concurrency=1, no_fetch=True, pii_enabled=False, whisper_language="auto",
    )

    def _ingest(_d, _declined=None, **_kw):
        return [audio_session(input_dir, i, f"rec{i}") for i in (1, 2)]

    async def _stage2(sess, _tmp, **_kw):
        for s in sess:
            if s.audio_path is None:
                s.audio_path = next(f.path for f in s.files if f.file_type == FileType.AUDIO)
        return sess

    def _transcribe(sessions, _settings, **_kw):
        sids = [s.session_id for s in sessions]
        return ({sid: _whisper_segments(sid) for sid in sids}, {},
                StageOutcome(attempted=len(sids), succeeded=len(sids)))

    async def _split(segments, _c, errors=None):
        for i, seg in enumerate(segments):
            seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
        return segments

    async def _roles(segments, _c, errors=None):
        sid = _sid(segments)
        asked.append(sid)
        if sid in fail and errors is not None:
            errors.append("role call failed")  # what the real pass does on an exception
        return []

    async def _topics(transcripts, *_a, **_kw):
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[]) for t in transcripts]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, *_a, **_kw):
        quotes = [_quote(t.session_id, t.participant_id, n) for t in transcripts for n in range(3)]
        return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

    async def _one(_quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    patches = [
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
    ]
    if not chain:
        # A re-analysis's shape: stage 5b's own loop identifies the speakers.
        patches.append(patch.object(Pipeline, "_readable_chain", return_value=None))
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        asyncio.run(Pipeline(settings).run(input_dir, tmp_path / "output"))


@pytest.mark.parametrize("chain", [True, False], ids=["readable-chain", "stage-5b-loop"])
def test_the_failed_session_alone_is_asked_again(
    tmp_path: Path, chain: bool, capsys: pytest.CaptureFixture[str],
) -> None:
    first: list[str] = []
    _drive(tmp_path, first, fail={"s2"}, chain=chain)
    assert sorted(first) == ["s1", "s2"]
    # The stage's one warning still says why.
    assert "role call failed" in capsys.readouterr().out

    record = load_manifest(tmp_path / "output", strict=True).stages[STAGE_IDENTIFY_SPEAKERS]
    assert record.sessions["s2"].status == StageStatus.FAILED
    assert record.sessions["s1"].status == StageStatus.COMPLETE

    again: list[str] = []
    _drive(tmp_path, again, fail=set(), chain=chain)
    assert again == ["s2"], again

    record = load_manifest(tmp_path / "output", strict=True).stages[STAGE_IDENTIFY_SPEAKERS]
    assert record.status == StageStatus.COMPLETE


def test_a_clean_rerun_asks_nothing(tmp_path: Path) -> None:
    _drive(tmp_path, [], fail=set(), chain=True)
    again: list[str] = []
    _drive(tmp_path, again, fail=set(), chain=True)
    assert again == []
