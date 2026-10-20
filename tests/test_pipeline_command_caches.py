"""``transcribe`` and ``analyze`` on a project ``run`` has already done (R115).

``transcribe`` had no cache: on a project a full run had transcribed, it sent
every recording through Whisper again (the researcher's time, and on a laptop
their battery). It now reuses run()'s transcription for every session whose
inputs have not changed, and transcribes only the rest.

``analyze`` into a run's output overwrites the intermediate files the run's
manifest vouches for, so the next ``run`` reads them as corrupt and re-pays
every session's analysis. That half waits on a product decision (see the
strict xfail below).

Real ``Pipeline`` methods and real manifest; ingest, stage 2, Whisper and every
LLM stage are stubbed (the harness of ``test_pipeline_interrupted_rerun``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.events import StageOutcome
from bristlenose.models import FileType, SessionTopicMap
from bristlenose.pipeline import Pipeline
from tests.conftest import iter_transcribe_from
from tests.test_pipeline_platform_transcripts import _quote, _whisper_segments, audio_session


def _drive(tmp_path: Path, mode: str, n_sessions: int, log: dict) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    output_dir = tmp_path / "output"
    settings = BristlenoseSettings(
        project_name="caches", skip_transcription=False, write_intermediate=True,
        llm_concurrency=1, no_fetch=True, pii_enabled=False, whisper_language="auto",
    )

    def _ingest(_d, _declined=None, **_kw):
        return [audio_session(input_dir, i, f"rec{i}") for i in range(1, n_sessions + 1)]

    async def _stage2(sess, _tmp, **_kw):
        log.setdefault("decoded", []).append([s.session_id for s in sess])
        for s in sess:
            if s.audio_path is None:
                s.audio_path = next(f.path for f in s.files if f.file_type == FileType.AUDIO)
        return sess

    def _transcribe(sessions, _settings, **_kw):
        sids = [s.session_id for s in sessions]
        log.setdefault("transcribed", []).append(sids)
        return ({sid: _whisper_segments(sid) for sid in sids}, dict.fromkeys(sids, "fr"),
                StageOutcome(attempted=len(sids), succeeded=len(sids)))

    async def _split(segments, _c, errors=None):
        for i, seg in enumerate(segments):
            seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
        return segments

    async def _roles(segments, _c, errors=None):
        return []

    async def _topics(transcripts, *_a, **_kw):
        log.setdefault("topics", []).append(sorted(t.session_id for t in transcripts))
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[]) for t in transcripts]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, *_a, **_kw):
        log.setdefault("quoted", []).append(sorted(t.session_id for t in transcripts))
        # A re-extraction never returns the same wording: analyze's quotes
        # differ from the run's, as a real model's do.
        base = 10 if mode == "analyze" else 0
        quotes = [_quote(t.session_id, t.participant_id, base + n)
                  for t in transcripts for n in range(3)]
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
        pipeline = Pipeline(settings)
        if mode == "run":
            asyncio.run(pipeline.run(input_dir, output_dir))
        elif mode == "transcribe":
            asyncio.run(pipeline.run_transcription_only(input_dir, output_dir))
        elif mode == "analyze":
            asyncio.run(pipeline.run_analysis_only(output_dir / "transcripts-raw", output_dir))
        else:
            raise AssertionError(mode)


def test_transcribe_on_a_run_project_transcribes_nothing_again(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after)

    # Before the fix: [["s1", "s2"]] — every recording through Whisper again.
    assert "transcribed" not in after, after
    # Nor decoded: on iCloud a decode is a download.
    assert after.get("decoded", [[]]) == [[]], after
    raw = tmp_path / "output" / "transcripts-raw"
    for sid in ("s1", "s2"):
        text = (raw / f"{sid}.txt").read_text(encoding="utf-8")
        assert "Welcome, thanks for joining" in text
        # A cached session keeps the language its transcription detected.
        assert "Language: fr (detected)" in text, text[:400]


def test_transcribe_on_a_run_project_transcribes_only_a_new_recording(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})

    after: dict = {}
    _drive(tmp_path, "transcribe", 3, after)

    assert after["transcribed"] == [["s3"]], after
    assert after["decoded"] == [["s3"]], after
    raw = tmp_path / "output" / "transcripts-raw"
    assert {p.stem for p in raw.glob("*.txt")} == {"s1", "s2", "s3"}


def test_transcribe_on_a_run_project_redoes_a_session_whose_inputs_changed(
    tmp_path: Path,
) -> None:
    _drive(tmp_path, "run", 2, {})
    # s2's transcription no longer matches what it would be computed from now
    # (as after a parser bump on a transcript file): only a fresh record is
    # reused. A re-exported recording is a new session to the registry, so
    # this is the way to reach the check under the same session id.
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["transcribe"]["sessions"]["s2"]["input_hash"] = "stale"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after)

    assert after["transcribed"] == [["s2"]], after


def test_transcribe_with_no_earlier_run_transcribes_everything(tmp_path: Path) -> None:
    log: dict = {}
    _drive(tmp_path, "transcribe", 2, log)
    assert log["transcribed"] == [["s1", "s2"]], log


@pytest.mark.xfail(
    strict=True,
    reason=(
        "R115 analyze half: analyze overwrites the intermediates run()'s manifest "
        "vouches for, and the next run reads them as corrupt and re-pays. Which "
        "fix (analyze records its outputs, refuses a run project, or a demote on "
        "mismatch) is a product decision."
    ),
)
def test_a_run_after_analyze_does_not_re_pay_the_analysis(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    _drive(tmp_path, "analyze", 2, {})

    after: dict = {}
    _drive(tmp_path, "run", 2, after)

    # At HEAD: {'quoted': [['s1', 's2']]} — every session's quotes re-paid.
    assert "quoted" not in after, after
    assert "topics" not in after, after
