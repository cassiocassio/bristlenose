"""``transcribe`` and ``analyze`` on a project ``run`` has already done (R115).

``transcribe`` had no cache: on a project a full run had transcribed, it sent
every recording through Whisper again (the researcher's time, and on a laptop
their battery). It now reuses run()'s transcription for every session whose
inputs have not changed, and transcribes only the rest. A session it serves
from run's transcription also keeps the speakers run identified.

``run`` itself, given a session its manifest records as transcribed but the
cache file does not hold, transcribes it rather than report it as silent.

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
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.config import BristlenoseSettings
from bristlenose.events import Cause, CauseCategoryEnum, PipelineAbandonedError, StageOutcome
from bristlenose.models import (
    FileType,
    InputFile,
    InputSession,
    PipelineResult,
    SessionTopicMap,
)
from bristlenose.pipeline import Pipeline
from tests.conftest import iter_transcribe_from
from tests.test_pipeline_platform_transcripts import (
    _T0,
    _quote,
    _whisper_segments,
    audio_session,
)


def _broken_docx_session(input_dir: Path, n: int) -> InputSession:
    """A session whose only transcript is a .docx that cannot be read."""
    path = input_dir / f"notes{n}.docx"
    if not path.exists():
        path.write_bytes(b"not a docx at all")
    docx = InputFile(
        path=path, file_type=FileType.DOCX, created_at=_T0, size_bytes=path.stat().st_size,
    )
    return InputSession(
        session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
        files=[docx], audio_path=None, has_existing_transcript=True, session_date=_T0,
    )


def _drive(
    tmp_path: Path, mode: str, n_sessions: int, log: dict, *, reuse: bool = True,
    llm_researcher: str | None = None, skip: bool = False, broken_docx: bool = False,
) -> PipelineResult | None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    output_dir = tmp_path / "output"
    settings = BristlenoseSettings(
        project_name="caches", skip_transcription=skip, write_intermediate=True,
        llm_concurrency=1, no_fetch=True, pii_enabled=False, whisper_language="auto",
    )

    def _ingest(_d, _declined=None, **_kw):
        sessions = [audio_session(input_dir, i, f"rec{i}") for i in range(1, n_sessions + 1)]
        if broken_docx:
            sessions.append(_broken_docx_session(input_dir, n_sessions + 1))
        return sessions

    async def _stage2(sess, _tmp, **_kw):
        log.setdefault("decoded", []).append([s.session_id for s in sess])
        for s in sess:
            if s.audio_path is None and not s.has_existing_transcript:
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
        # A model that disagrees with the heuristic, as a real one can.
        if llm_researcher is not None:
            from bristlenose.models import SpeakerRole

            for seg in segments:
                seg.speaker_role = (
                    SpeakerRole.RESEARCHER if seg.speaker_label == llm_researcher
                    else SpeakerRole.PARTICIPANT
                )
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
            return asyncio.run(pipeline.run(input_dir, output_dir))
        if mode == "transcribe":
            asyncio.run(pipeline.run_transcription_only(
                input_dir, output_dir, reuse_transcription=reuse,
            ))
        elif mode == "analyze":
            asyncio.run(pipeline.run_analysis_only(output_dir / "transcripts-raw", output_dir))
        else:
            raise AssertionError(mode)
    return None


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


def _intermediate(tmp_path: Path, name: str) -> Path:
    return tmp_path / "output" / ".bristlenose" / "intermediate" / name


def test_transcribe_redoes_a_session_the_cache_file_does_not_hold(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    del cached["s2"]
    path.write_text(json.dumps(cached), encoding="utf-8")

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after)

    # Recorded complete in the manifest but not in the file: transcribed, not
    # lost (and not reported as a silent recording).
    assert after["transcribed"] == [["s2"]], after
    assert "Welcome" in (tmp_path / "output" / "transcripts-raw" / "s2.txt").read_text()


def test_transcribe_redoes_everything_over_a_corrupt_cache_file(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    _intermediate(tmp_path, "session_segments.json").write_text('{"s1": [', encoding="utf-8")

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after)

    assert after["transcribed"] == [["s1", "s2"]], after


def test_transcribe_redoes_a_session_the_run_recorded_as_failed(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["transcribe"]["sessions"]["s2"]["status"] = "failed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after)

    assert after["transcribed"] == [["s2"]], after


def test_transcribe_says_what_it_did_not_transcribe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _drive(tmp_path, "run", 2, {})
    capsys.readouterr()

    _drive(tmp_path, "transcribe", 2, {})
    out = capsys.readouterr().out
    assert "Transcribed 2 sessions (12 segments) (cached)" in " ".join(out.split()), out

    # transcribe writes no cache of its own, so the third is new each time.
    _drive(tmp_path, "transcribe", 3, {})
    out = capsys.readouterr().out
    assert "1 new session" in out, out


def test_transcribe_asked_not_to_reuse_transcribes_everything(tmp_path: Path) -> None:
    _drive(tmp_path, "run", 2, {})

    after: dict = {}
    _drive(tmp_path, "transcribe", 2, after, reuse=False)

    assert after["transcribed"] == [["s1", "s2"]], after


@pytest.mark.parametrize(
    ("options", "reuse"),
    [([], True), (["-w", "tiny"], False), (["--whisper-language", "de"], False)],
)
def test_the_cli_reuses_a_transcription_unless_a_model_or_language_is_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: list[str], reuse: bool,
) -> None:
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    seen: dict = {}

    async def _capture(self, input_dir, output_dir, **kw):
        seen.update(kw)
        raise PipelineAbandonedError(
            cause=Cause(category=CauseCategoryEnum.UNKNOWN, message="stop here"),
        )

    monkeypatch.setattr("bristlenose.pipeline.Pipeline.run_transcription_only", _capture)
    interviews = tmp_path / "interviews"
    interviews.mkdir()
    CliRunner().invoke(app, ["transcribe", str(interviews), *options])

    assert seen == {"reuse_transcription": reuse}


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


# ── transcribe keeps the speakers run identified ─────────────────────────────


def test_transcribe_on_a_run_project_keeps_the_speakers_run_identified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # run() split each recording into two speakers and gave them codes; the
    # heuristic transcribe uses without a model sees one speaker. Served from
    # run's transcription, a session keeps run's speakers: transcribe must not
    # rewrite them into the heuristic's, nor number new participants. The
    # model here calls Speaker B the researcher, where the heuristic says A.
    _drive(tmp_path, "run", 2, {}, llm_researcher="Speaker B")
    raw = tmp_path / "output" / "transcripts-raw"
    before = {p.name: p.read_text(encoding="utf-8") for p in raw.iterdir()}
    registry = tmp_path / "output" / ".bristlenose" / "sessions.json"
    registry_before = registry.read_text(encoding="utf-8")
    assert "[m1] (Speaker B)" in before["s1.txt"], before["s1.txt"]

    capsys.readouterr()
    _drive(tmp_path, "transcribe", 2, {})

    after = {p.name: p.read_text(encoding="utf-8") for p in raw.iterdir()}
    # Before the fix: every turn `[p3]`, the split and the m1 code gone.
    assert after == before
    assert registry.read_text(encoding="utf-8") == registry_before
    # Nothing was identified by the heuristic, and the line does not say it was.
    out = " ".join(capsys.readouterr().out.split())
    assert "Identified speakers (cached)" in out, out

    # A new recording beside them: it alone is identified by the heuristic.
    _drive(tmp_path, "transcribe", 3, {})
    assert (raw / "s1.txt").read_text(encoding="utf-8") == before["s1.txt"]
    assert "(Speaker A)" not in (raw / "s3.txt").read_text(encoding="utf-8")
    assert "Identified speakers (heuristic)" in capsys.readouterr().out


def test_transcribe_identifies_a_changed_session_by_heuristic(tmp_path: Path) -> None:
    # A session transcribed again has segments run never identified: its
    # speakers come from the heuristic, never from run's stale record.
    _drive(tmp_path, "run", 2, {})

    _drive(tmp_path, "transcribe", 2, {}, reuse=False)

    text = (tmp_path / "output" / "transcripts-raw" / "s1.txt").read_text(encoding="utf-8")
    assert "(Speaker A)" not in text, text


# ── run(): recorded complete, missing from the cache file ────────────────────


def _drop_s2_from_the_cache_and_restamp(tmp_path: Path) -> None:
    """s2 recorded COMPLETE, absent from a session_segments.json the manifest
    vouches for: what a run before this fix left behind once it had lost one."""
    from bristlenose.hashing import hash_bytes

    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    del cached["s2"]
    path.write_text(json.dumps(cached), encoding="utf-8")
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stages"]["transcribe"]["sessions"]["s2"]["status"] == "complete"
    manifest["stages"]["transcribe"]["content_hash"] = hash_bytes(path.read_bytes())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_run_transcribes_a_session_the_cache_file_does_not_hold(tmp_path: Path) -> None:
    # A new recording sends run() down the per-session path, which trusted the
    # manifest's record for s2 and found nothing in the file to serve.
    _drive(tmp_path, "run", 2, {})
    _drop_s2_from_the_cache_and_restamp(tmp_path)

    after: dict = {}
    result = _drive(tmp_path, "run", 3, after)

    # Before the fix: [["s3"]], and s2 reported as a recording with no speech.
    assert after["transcribed"] == [["s2", "s3"]], after
    assert result is not None
    assert result.summary.transcripts.failed == [], result.summary.transcripts
    # s3 is the one new interview; s2 is one the project already had.
    assert result.summary.new_sessions == 1, result.summary
    assert "Welcome" in (tmp_path / "output" / "transcripts-raw" / "s2.txt").read_text()


def test_run_transcribes_a_session_a_verified_cache_file_does_not_hold(
    tmp_path: Path,
) -> None:
    # Nothing changed, so the stage verifies whole; s2 is still not in it.
    _drive(tmp_path, "run", 2, {})
    _drop_s2_from_the_cache_and_restamp(tmp_path)

    after: dict = {}
    result = _drive(tmp_path, "run", 2, after)

    assert after["transcribed"] == [["s2"]], after
    assert result is not None and result.summary.new_sessions is None, result
    assert "Welcome" in (tmp_path / "output" / "transcripts-raw" / "s2.txt").read_text()
    # And the run heals the file, so the next one serves s2 from it.
    assert "s2" in json.loads(_intermediate(tmp_path, "session_segments.json").read_text())
    again: dict = {}
    _drive(tmp_path, "run", 2, again)
    assert "transcribed" not in again, again


def test_transcribe_does_not_give_run_s_speakers_to_changed_segments(
    tmp_path: Path,
) -> None:
    # run's speakers belong to the segments run identified. s1's cached
    # transcription differs from those now, so its record is not fresh and
    # the heuristic decides, whatever run's speaker cache holds.
    from bristlenose.hashing import hash_bytes

    _drive(tmp_path, "run", 2, {}, llm_researcher="Speaker B")
    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["s1"][0]["text"] += " Edited."
    path.write_text(json.dumps(cached), encoding="utf-8")
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["transcribe"]["content_hash"] = hash_bytes(path.read_bytes())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _drive(tmp_path, "transcribe", 2, {})

    raw = tmp_path / "output" / "transcripts-raw"
    assert "[m1] (Speaker B)" not in (raw / "s1.txt").read_text(encoding="utf-8")
    assert "[m1] (Speaker B)" in (raw / "s2.txt").read_text(encoding="utf-8")


def test_transcribe_logs_a_speaker_cache_it_cannot_use(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    # A fresh record whose file is gone: the heuristic stands in, and the log
    # says so rather than pass it off as a new recording's identification.
    _drive(tmp_path, "run", 2, {}, llm_researcher="Speaker B")
    _intermediate(tmp_path, "speaker-info/s1.json").unlink()

    with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
        _drive(tmp_path, "transcribe", 2, {})

    assert any("s1: speaker cache missing" in r.getMessage() for r in caplog.records), (
        [r.getMessage() for r in caplog.records]
    )


# ── run(): what one run did not transcribe, the next one is told ─────────────


def test_a_plain_run_transcribes_what_a_skip_transcription_run_left(tmp_path: Path) -> None:
    # --skip-transcription transcribes nothing and records no session as
    # failed; the stage still verified on the next plain run, which then said
    # "No speech found" for every recording, on every run.
    _drive(tmp_path, "run", 2, {}, skip=True)

    after: dict = {}
    result = _drive(tmp_path, "run", 2, after)

    assert after.get("transcribed") == [["s1", "s2"]], after
    assert result is not None and result.summary.transcripts.failed == [], result.summary
    again: dict = {}
    _drive(tmp_path, "run", 2, again)
    assert "transcribed" not in again, again


def test_a_transcript_that_cannot_be_read_says_so_on_every_run(tmp_path: Path) -> None:
    first = _drive(tmp_path, "run", 1, {}, broken_docx=True)
    assert first is not None
    first_causes = [
        (f.session_id, f.cause.category, f.cause.stage)
        for f in first.summary.transcripts.failed
    ]
    assert first_causes == [("s2", CauseCategoryEnum.MISSING_INPUT, "s04_parse_docx")]

    second = _drive(tmp_path, "run", 1, {}, broken_docx=True)

    assert second is not None
    # Before the fix: the stage verified whole, and s2 was "no speech".
    assert [
        (f.session_id, f.cause.category, f.cause.stage)
        for f in second.summary.transcripts.failed
    ] == first_causes
    # A file that fails again is a retry, not a new interview, every time.
    assert second.summary.new_sessions is None, second.summary


def test_the_transcribed_line_counts_new_sessions_as_the_summary_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # A session the cache file lost, and a transcript that fails again, are
    # retries: the summary never called them new, and neither does the line.
    _drive(tmp_path, "run", 2, {}, broken_docx=True)
    _drop_s2_from_the_cache_and_restamp(tmp_path)
    capsys.readouterr()

    result = _drive(tmp_path, "run", 2, {}, broken_docx=True)

    out = " ".join(capsys.readouterr().out.split())
    assert result is not None and result.summary.new_sessions is None, result.summary
    assert "Transcribed 3 sessions" in out, out
    assert "new session" not in out, out

    # A recording that really is new is still counted, and only it.
    result = _drive(tmp_path, "run", 3, {}, broken_docx=True)
    out = " ".join(capsys.readouterr().out.split())
    assert result is not None and result.summary.new_sessions == 1, result.summary
    assert "1 new session)" in out, out


@pytest.mark.parametrize("bad", [[{"start_time": "not a time"}], "not a list"])
def test_transcribe_falls_back_over_a_malformed_speaker_cache(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, bad: object,
) -> None:
    # As a missing file does: the heuristic and one log line, not a traceback.
    _drive(tmp_path, "run", 2, {}, llm_researcher="Speaker B")
    path = _intermediate(tmp_path, "speaker-info/s1.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segments_with_roles"] = bad
    path.write_text(json.dumps(data), encoding="utf-8")

    with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
        _drive(tmp_path, "transcribe", 2, {})

    assert any("s1: speaker cache missing" in r.getMessage() for r in caplog.records)
    raw = tmp_path / "output" / "transcripts-raw"
    assert "Welcome" in (raw / "s1.txt").read_text(encoding="utf-8")
    assert "[m1] (Speaker B)" in (raw / "s2.txt").read_text(encoding="utf-8")
