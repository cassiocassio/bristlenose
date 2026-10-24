"""``transcribe`` and ``analyze`` on a project ``run`` has already done (R115).

``transcribe`` had no cache: on a project a full run had transcribed, it sent
every recording through Whisper again (the researcher's time, and on a laptop
their battery). It now reuses run()'s transcription for every session whose
inputs have not changed, and transcribes only the rest. A session it serves
from run's transcription also keeps the speakers run identified.

``run`` itself, given a session its manifest records as transcribed but the
cache file does not hold, transcribes it rather than report it as silent.

``analyze`` into a run's output overwrote the intermediate files the run's
manifest vouches for, so the next ``run`` read them as corrupt and re-paid
every session's analysis. It now records what it analysed, per session, against
the transcript file it read; the next ``run`` keeps every session whose
transcript is still that file (decision #58, 22 Oct 2026).

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
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    PipelineAbandonedError,
    StageFailure,
    StageOutcome,
)
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
    write_vtt,
)


def _broken_docx_session(input_dir: Path, n: int, *, beside: str | None = None) -> InputSession:
    """A session with a .docx transcript that cannot be read: alone, or
    ``beside`` a recording ("audio") or a transcript that reads ("vtt")."""
    path = input_dir / f"notes{n}.docx"
    if not path.exists():
        path.write_bytes(b"not a docx at all")
    files = [InputFile(
        path=path, file_type=FileType.DOCX, created_at=_T0, size_bytes=path.stat().st_size,
    )]
    if beside == "audio":
        files.insert(0, audio_session(input_dir, n, f"notes{n}").files[0])
    elif beside == "vtt":
        vtt = write_vtt(input_dir, f"notes{n}", [("Ana", "Hello there."), ("Ben", "Hi, thanks.")])
        files.insert(0, InputFile(
            path=vtt, file_type=FileType.SUBTITLE_VTT, created_at=_T0,
            size_bytes=vtt.stat().st_size,
        ))
    return InputSession(
        session_id=f"s{n}", session_number=n, participant_id=f"p{n}", participant_number=n,
        files=files, audio_path=None, has_existing_transcript=True, session_date=_T0,
    )


def _drive(
    tmp_path: Path, mode: str, n_sessions: int, log: dict, *, reuse: bool = True,
    llm_researcher: str | None = None, skip: bool = False, broken_docx: bool = False,
    beside: str | None = None, topics_fail: bool = False, quotes_fail: bool = False,
    cluster_fail: str | None = None, settings_kw: dict | None = None,
) -> PipelineResult | None:
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    output_dir = tmp_path / "output"
    settings = BristlenoseSettings(
        project_name="caches", skip_transcription=skip, write_intermediate=True,
        llm_concurrency=1, no_fetch=True, pii_enabled=False, whisper_language="auto",
        **(settings_kw or {}),
    )

    def _ingest(_d, _declined=None, **_kw):
        sessions = [audio_session(input_dir, i, f"rec{i}") for i in range(1, n_sessions + 1)]
        if broken_docx:
            sessions.append(_broken_docx_session(input_dir, n_sessions + 1, beside=beside))
        return sessions

    async def _stage2(sess, _tmp, **_kw):
        log.setdefault("decoded", []).append([s.session_id for s in sess])
        for s in sess:
            # As stage 2 does: an audio file is used even beside a transcript.
            if s.audio_path is None:
                s.audio_path = next(
                    (f.path for f in s.files if f.file_type == FileType.AUDIO), None,
                )
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
        log.setdefault("roles", []).append(segments[0].text if segments else "")
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
        from bristlenose.models import TopicBoundary, TransitionType

        # analyze's topic maps differ from the run's, as a real model's do.
        boundaries = [TopicBoundary(
            timecode_seconds=0.0, topic_label="Analysed",
            transition_type=next(iter(TransitionType)),
        )] if mode == "analyze" else []
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=list(boundaries)) for t in transcripts]
        if topics_fail:
            return maps, StageOutcome(attempted=len(maps), succeeded=0, failed=[
                StageFailure(session_id=t.session_id, cause=Cause(
                    category=CauseCategoryEnum.UNKNOWN, message="stub failure"))
                for t in transcripts])
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, *_a, **_kw):
        log.setdefault("quoted", []).append(sorted(t.session_id for t in transcripts))
        # A re-extraction never returns the same wording: analyze's quotes
        # differ from the run's, as a real model's do.
        base = 10 if mode == "analyze" else 0
        quotes = [_quote(t.session_id, t.participant_id, base + n)
                  for t in transcripts for n in range(3)]
        if quotes_fail:
            return [], StageOutcome(attempted=len(transcripts), succeeded=0, failed=[
                StageFailure(session_id=t.session_id, cause=Cause(
                    category=CauseCategoryEnum.UNKNOWN, message="stub failure"))
                for t in transcripts])
        return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

    def _half(name: str):
        # ``cluster_fail`` names the half ("cluster" or "group") whose call
        # fails: it returns its fallback (here ``[]``) and says so, as s10/s11 do.
        async def _call(_quotes, *_a, **_kw):
            log.setdefault("clustered", []).append(name)
            if name == cluster_fail:
                return [], StageOutcome(attempted=1, succeeded=0, failed=[StageFailure(
                    session_id=None, cause=Cause(
                        category=CauseCategoryEnum.UNKNOWN, message="stub failure"))])
            return [], StageOutcome(attempted=1, succeeded=1)
        return _call

    async def _discuss(transcripts, *_a, **_kw):
        # Stubbed like every other LLM stage here: the pipeline's own record
        # and manifest handling still run, on a stage that succeeds.
        from bristlenose.discussion.models import DiscussionRecord

        log.setdefault("discussed", []).append(sorted(t.session_id for t in transcripts))
        return DiscussionRecord(), StageOutcome(
            attempted=len(transcripts), succeeded=len(transcripts),
        )

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
        patch("bristlenose.stages.s10_quote_clustering.cluster_by_screen", new=_half("cluster")),
        patch("bristlenose.stages.s11_thematic_grouping.group_by_theme", new=_half("group")),
        patch("bristlenose.discussion.stage.run_discussion", new=_discuss),
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
            return asyncio.run(
                pipeline.run_analysis_only(output_dir / "transcripts-raw", output_dir),
            )
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


def test_a_run_after_analyze_keeps_what_analyze_paid_for(tmp_path: Path) -> None:
    # The README's workflow: analyze the project's own transcripts. analyze
    # overwrote the files run's manifest vouched for, so the next run read them
    # as changed on disk and paid for every session's analysis again.
    _drive(tmp_path, "run", 2, {})
    _drive(tmp_path, "analyze", 2, {})

    after: dict = {}
    _drive(tmp_path, "run", 2, after)

    # At HEAD: {'quoted': [['s1', 's2']], 'topics': [['s1', 's2']]}.
    assert not {"topics", "quoted", "clustered"} & set(after), after
    # It kept analyze's analysis, not the run's older one.
    maps = json.loads(_intermediate(tmp_path, "topic_boundaries.json").read_text())
    assert {m["boundaries"][0]["topic_label"] for m in maps} == {"Analysed"}, maps
    quotes = json.loads(_intermediate(tmp_path, "extracted_quotes.json").read_text())
    assert {q["text"].split(" from")[0] for q in quotes} == {"Quote 10", "Quote 11", "Quote 12"}

    # And the run after that, on the run's own record, redoes nothing.
    again: dict = {}
    _drive(tmp_path, "run", 2, again)
    assert not {"topics", "quoted"} & set(again), again


def test_a_run_after_analyze_re_pays_only_a_hand_edited_transcript(tmp_path: Path) -> None:
    # analyze analysed the edit; run analyses the recording's transcript, which
    # is not the edit, so that one session is analysed again and no other.
    _drive(tmp_path, "run", 2, {})
    path = tmp_path / "output" / "transcripts-raw" / "s1.txt"
    path.write_text(path.read_text(encoding="utf-8").replace("Welcome", "Hello"),
                    encoding="utf-8")
    _drive(tmp_path, "analyze", 2, {})

    after: dict = {}
    _drive(tmp_path, "run", 2, after)

    assert after.get("topics") == [["s1"]], after
    assert after.get("quoted") == [["s1"]], after


@pytest.mark.parametrize("fail", ["topics_fail", "quotes_fail"])
def test_an_analyze_that_fails_leaves_the_run_s_analysis_as_it_was(
    tmp_path: Path, fail: str,
) -> None:
    # Every topic (or quote) call failed: analyze abandons, and wrote its
    # topics over the run's first, so the next run paid for every session again.
    _drive(tmp_path, "run", 2, {})
    with pytest.raises(PipelineAbandonedError):
        _drive(tmp_path, "analyze", 2, {}, **{fail: True})

    after: dict = {}
    _drive(tmp_path, "run", 2, after)
    assert not {"topics", "quoted", "clustered"} & set(after), after


def test_a_copy_beside_its_transcript_is_never_vouched_for(tmp_path: Path) -> None:
    # Copy, edit, analyze: s1-edited.txt beside s1.txt, header still s1. analyze
    # reads both as s1; vouching for s1 by either file served the pair's
    # doubled analysis as the recording's. The next run analyses s1 again.
    _drive(tmp_path, "run", 2, {})
    raw = tmp_path / "output" / "transcripts-raw"
    (raw / "s1-edited.txt").write_text(
        (raw / "s1.txt").read_text(encoding="utf-8").replace("Welcome", "Hello"),
        encoding="utf-8",
    )
    _drive(tmp_path, "analyze", 2, {})
    (raw / "s1-edited.txt").unlink()

    after: dict = {}
    _drive(tmp_path, "run", 2, after)

    assert after.get("quoted") == [["s1"]], after
    maps = json.loads(_intermediate(tmp_path, "topic_boundaries.json").read_text())
    assert sorted(m["session_id"] for m in maps) == ["s1", "s2"], maps


def test_a_stage_key_the_run_does_not_watch_is_a_change() -> None:
    # The strict arm that keeps analyze's stage off run's whole-stage cache.
    from bristlenose.pipeline import _inputs_changed

    assert _inputs_changed({"analyzed_transcripts": "x"}, {"upstream": "u", "pii_enabled": "False"})
    assert not _inputs_changed({"upstream": "u"}, {"upstream": "u", "pii_enabled": "False"})


def test_a_transcript_file_run_cannot_read_is_an_error_not_a_re_pay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A missing file is no key; any other failure to read one run has just
    # written is not quietly turned into paying for every session again.
    from bristlenose.pipeline import _transcript_file_hashes

    (tmp_path / "s1.txt").write_text("x", encoding="utf-8")
    assert set(_transcript_file_hashes(tmp_path, ["s1", "s2"])) == {"s1"}

    def _denied(self: Path) -> bytes:
        raise PermissionError(13, "denied", str(self))

    monkeypatch.setattr(Path, "read_bytes", _denied)
    with pytest.raises(PermissionError):
        _transcript_file_hashes(tmp_path, ["s1"])


def test_the_file_key_vouches_for_the_bytes_analyze_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One read per file: an editor saving between a parse and a second read
    # for the hash would key the session to bytes analyze never analysed.
    from bristlenose.pipeline import load_transcripts_from_dir

    _drive(tmp_path, "run", 1, {})
    raw = tmp_path / "output" / "transcripts-raw"
    reads: list[str] = []
    real = Path.read_bytes

    def _counted(self: Path) -> bytes:
        reads.append(self.name)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", _counted)
    monkeypatch.setattr(Path, "read_text", lambda *_a, **_k: pytest.fail("second read"))
    hashes: dict[str, str] = {}
    load_transcripts_from_dir(raw, file_hashes=hashes)

    assert reads == ["s1.txt"], reads
    from bristlenose.hashing import hash_bytes

    assert hashes == {"s1": hash_bytes(real(raw / "s1.txt"))}


def test_analyze_with_no_manifest_writes_none(tmp_path: Path) -> None:
    # A folder of transcripts run never vouched for: nothing to keep, and
    # analyze still writes no manifest of its own.
    _drive(tmp_path, "run", 2, {})
    manifest = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest.unlink()

    _drive(tmp_path, "analyze", 2, {})

    assert not manifest.exists()


def test_the_harness_runs_the_discussion_stage_without_an_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """The discussion stage is on by default, and the harness once handed it a
    MagicMock client: every ``_drive`` logged its failure path, unasserted, so a
    real failure there was invisible. Fresh, then served from its cache."""
    log: dict = {}
    with caplog.at_level("ERROR"):
        _drive(tmp_path, "run", 2, log)
        _drive(tmp_path, "run", 2, log)

    errors = [f"{r.name}: {r.getMessage()}" for r in caplog.records
              if r.levelname == "ERROR"
              and (r.name.startswith("bristlenose.discussion") or "discussion" in r.getMessage())]
    assert errors == [], errors
    assert log["discussed"] == [["s1", "s2"]], log  # ran once, then cached


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


def test_a_skip_transcription_run_does_not_call_what_it_skipped_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The researcher asked for no transcription; "No speech found — nothing was
    # said in this recording" for each recording, and a warning on the Mac, was
    # false. One line says what was not done (RE#20, decision #74).
    import io

    from rich.console import Console

    import bristlenose.pipeline as pipeline_module

    out = io.StringIO()
    monkeypatch.setattr(pipeline_module, "console", Console(file=out, width=200))

    result = _drive(tmp_path, "run", 2, {}, skip=True)

    printed = out.getvalue()
    assert "No speech found" not in printed, printed
    assert "2 recordings not transcribed (--skip-transcription)" in printed, printed
    assert result is not None
    transcripts = result.summary.transcripts
    assert transcripts.failed == [], transcripts
    assert transcripts.attempted == transcripts.succeeded + len(transcripts.failed)


def test_a_skip_run_beside_a_transcript_counts_only_what_it_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two recordings left untranscribed and one session read from its .vtt:
    # the stage counts the one it read, and the line names the two it left.
    import io

    from rich.console import Console

    import bristlenose.pipeline as pipeline_module

    out = io.StringIO()
    monkeypatch.setattr(pipeline_module, "console", Console(file=out, width=200))

    result = _drive(tmp_path, "run", 2, {}, skip=True, broken_docx=True, beside="vtt")

    printed = out.getvalue()
    assert "2 recordings not transcribed (--skip-transcription)" in printed, printed
    assert "Transcribed 1 session" in printed, printed
    assert result is not None
    transcripts = result.summary.transcripts
    assert transcripts.attempted == 1, transcripts
    assert transcripts.attempted == transcripts.succeeded + len(
        {f.session_id for f in transcripts.failed}
    ), transcripts
    assert not any(
        f.cause.reason == "no_speech" for f in transcripts.failed
    ), transcripts


def test_a_plain_run_heals_what_an_older_skip_transcription_run_left(
    tmp_path: Path,
) -> None:
    # A build before 20 Oct 2026 did not watch skip_transcription: its manifest
    # verifies the stage, the cache file holds no session, and no session is
    # recorded, so every recording read "No speech found" on every run.
    _drive(tmp_path, "run", 2, {}, skip=True)
    _forget_skip(tmp_path)

    after: dict = {}
    result = _drive(tmp_path, "run", 2, after)

    assert after.get("transcribed") == [["s1", "s2"]], after
    assert result is not None and result.summary.transcripts.failed == [], result.summary
    again: dict = {}
    _drive(tmp_path, "run", 2, again)
    assert "transcribed" not in again, again


def _forget_skip(tmp_path: Path) -> None:
    """What an older build's skip-transcription run left: no skip marker."""
    path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["stages"]["transcribe"]["input_hashes"]["skip_transcription"]
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_what_an_older_skip_run_left_beside_a_transcribed_session_is_a_retry(
    tmp_path: Path,
) -> None:
    # s1 transcribed by a plain run, s2 added under an older skip run: the
    # heal transcribes s2 alone, and counts it as a retry, not a new interview.
    _drive(tmp_path, "run", 1, {})
    _drive(tmp_path, "run", 2, {}, skip=True)
    _forget_skip(tmp_path)

    after: dict = {}
    result = _drive(tmp_path, "run", 2, after)

    assert after.get("transcribed") == [["s2"]], after
    assert result is not None and result.summary.new_sessions is None, result.summary


def test_a_transcript_that_cannot_be_read_says_so_on_every_run(tmp_path: Path) -> None:
    first = _drive(tmp_path, "run", 1, {}, broken_docx=True)
    assert first is not None
    first_causes = [
        (f.session_id, f.cause.category, f.cause.stage)
        for f in first.summary.transcripts.failed
    ]
    assert first_causes == [("s2", CauseCategoryEnum.MISSING_INPUT, "s04_parse_docx")]

    log: dict = {}
    second = _drive(tmp_path, "run", 1, log, broken_docx=True)

    assert second is not None
    # Re-read, and nothing else redone or re-paid.
    assert not {"transcribed", "topics", "quoted"} & set(log), log
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

    messages = [r.getMessage() for r in caplog.records]
    assert any("s1: speaker cache missing" in m for m in messages), messages
    assert any("s1.json unusable: ValidationError" in m for m in messages), messages
    raw = tmp_path / "output" / "transcripts-raw"
    assert "Welcome" in (raw / "s1.txt").read_text(encoding="utf-8")
    assert "[m1] (Speaker B)" in (raw / "s2.txt").read_text(encoding="utf-8")


def test_plain_then_skip_then_plain_redoes_nothing(tmp_path: Path) -> None:
    # Watching skip_transcription costs a project that was transcribed nothing:
    # a skip run serves the cache, and the plain run after it does too.
    _drive(tmp_path, "run", 2, {})

    for skip in (True, False):
        log: dict = {}
        _drive(tmp_path, "run", 2, log, skip=skip)
        assert not {"transcribed", "roles", "topics", "quoted"} & set(log), (skip, log)


@pytest.mark.parametrize("beside", ["audio", "vtt"])
def test_an_unreadable_transcript_beside_one_that_worked_is_not_a_failed_session(
    tmp_path: Path, beside: str,
) -> None:
    # The session ended with segments (Whisper on the recording, or the .vtt),
    # so it is complete. Recorded failed, it was transcribed again every run.
    _drive(tmp_path, "run", 1, {}, broken_docx=True, beside=beside)
    manifest = json.loads(
        (tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json").read_text()
    )
    assert manifest["stages"]["transcribe"]["sessions"]["s2"]["status"] == "complete"

    again: dict = {}
    _drive(tmp_path, "run", 1, again, broken_docx=True, beside=beside)
    assert not {"transcribed", "roles", "topics", "quoted"} & set(again), again


def _break_s1_speaker_cache(tmp_path: Path, *, restamp: bool) -> None:
    from bristlenose.hashing import hash_bytes

    path = _intermediate(tmp_path, "speaker-info/s1.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segments_with_roles"] = [{"start_time": "not a time"}]
    path.write_text(json.dumps(data), encoding="utf-8")
    if restamp:
        manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["stages"]["identify_speakers"]["sessions"]["s1"]["content_hash"] = (
            hash_bytes(path.read_bytes())
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize(("restamp", "n_after"), [(True, 2), (False, 3)])
def test_run_identifies_again_over_a_malformed_speaker_cache(
    tmp_path: Path, restamp: bool, n_after: int,
) -> None:
    # restamp: the file passes the stage's hash check (the verified path).
    # Otherwise a new recording sends the stage down the per-session path.
    _drive(tmp_path, "run", 2, {})
    _break_s1_speaker_cache(tmp_path, restamp=restamp)

    log: dict = {}
    _drive(tmp_path, "run", n_after, log)

    # Before the fix: a ValidationError out of run(). Now s1 is asked again.
    assert any("s1 session" in text for text in log.get("roles", [])), log
    assert "Welcome" in (tmp_path / "output" / "transcripts-raw" / "s1.txt").read_text()


# ── transcribe: the line says what it did ────────────────────────────────────


def test_transcribe_counts_new_sessions_as_run_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # s2 failed last run and s3 is a session the cache file lost: both are
    # retries, as run() counts them. Only s4 is a new recording.
    _drive(tmp_path, "run", 3, {})
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["transcribe"]["sessions"]["s2"]["status"] = "failed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    del cached["s3"]
    path.write_text(json.dumps(cached), encoding="utf-8")
    capsys.readouterr()

    after: dict = {}
    _drive(tmp_path, "transcribe", 4, after)

    assert after["transcribed"] == [["s2", "s3", "s4"]], after
    out = " ".join(capsys.readouterr().out.split())
    # Before the fix: "3 new sessions".
    assert "1 new session)" in out, out

    # Retries alone are no new session at all.
    capsys.readouterr()
    _drive(tmp_path, "transcribe", 3, {})
    out = " ".join(capsys.readouterr().out.split())
    assert "Transcribed 3 sessions" in out, out
    assert "new session" not in out, out


def test_transcribe_over_a_corrupt_speaker_cache_does_not_say_recomputing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture,
) -> None:
    # transcribe has no model to identify speakers again: it falls back to the
    # heuristic, and the log says so. The terminal must not say "recomputing".
    _drive(tmp_path, "run", 2, {}, llm_researcher="Speaker B")
    _intermediate(tmp_path, "speaker-info/s1.json").write_text('{"speaker_inf', encoding="utf-8")
    capsys.readouterr()
    # The terminal warning is deduplicated per process; transcribe never clears it.
    from bristlenose import pipeline

    pipeline._printed_warnings.clear()

    with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
        _drive(tmp_path, "transcribe", 2, {})

    out = capsys.readouterr().out
    assert "recomputing" not in out, out
    messages = [r.getMessage() for r in caplog.records]
    assert any("s1: speaker cache missing" in m for m in messages), messages
    raw = tmp_path / "output" / "transcripts-raw"
    assert "[m1] (Speaker B)" not in (raw / "s1.txt").read_text(encoding="utf-8")
    assert "[m1] (Speaker B)" in (raw / "s2.txt").read_text(encoding="utf-8")


def test_run_over_a_corrupt_speaker_cache_still_says_recomputing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    # run() does ask the model again, so its warning stays true and stays.
    _drive(tmp_path, "run", 2, {})
    _intermediate(tmp_path, "speaker-info/s1.json").write_text('{"speaker_inf', encoding="utf-8")
    capsys.readouterr()

    log: dict = {}
    _drive(tmp_path, "run", 3, log)

    out = " ".join(capsys.readouterr().out.split())
    assert "s1.json: cache unreadable (JSONDecodeError) — recomputing" in out, out
    assert any("s1 session" in text for text in log.get("roles", [])), log


# ── a session_segments.json that parses but is not an object ─────────────────


def _segments_file_not_an_object(tmp_path: Path, *, path_taken: str | None) -> None:
    """Valid JSON, not an object. ``path_taken``: "verified" restamps the
    stage hash so the file passes it; "per-session" leaves the stage RUNNING,
    as an interrupted run does, where the hash is never checked."""
    from bristlenose.hashing import hash_bytes

    path = _intermediate(tmp_path, "session_segments.json")
    path.write_text(json.dumps([{"s1": []}]), encoding="utf-8")
    if path_taken is None:
        return
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if path_taken == "verified":
        manifest["stages"]["transcribe"]["content_hash"] = hash_bytes(path.read_bytes())
    else:
        manifest["stages"]["transcribe"]["status"] = "running"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize("path_taken", ["verified", "per-session"])
def test_run_recomputes_over_a_segments_file_that_is_not_an_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], path_taken: str,
) -> None:
    # Read on either path, it is a corrupt cache file: discarded, recomputed.
    _drive(tmp_path, "run", 2, {})
    _segments_file_not_an_object(tmp_path, path_taken=path_taken)
    capsys.readouterr()

    log: dict = {}
    result = _drive(tmp_path, "run", 2, log)

    # Before the fix: a TypeError or AttributeError out of run().
    assert log.get("transcribed") == [["s1", "s2"]], log
    assert result is not None and result.summary.transcripts.failed == [], result
    out = " ".join(capsys.readouterr().out.split())
    assert "session_segments.json: cache unreadable (ValueError) — recomputing" in out, out


def test_transcribe_says_it_recomputes_over_a_segments_file_that_is_not_an_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture,
) -> None:
    _drive(tmp_path, "run", 2, {})
    _segments_file_not_an_object(tmp_path, path_taken=None)
    capsys.readouterr()
    from bristlenose import pipeline

    pipeline._printed_warnings.clear()

    after: dict = {}
    with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
        _drive(tmp_path, "transcribe", 2, after)

    assert after["transcribed"] == [["s1", "s2"]], after
    # Before the fix: every recording transcribed again, and nothing said why.
    out = " ".join(capsys.readouterr().out.split())
    assert "session_segments.json: cache unreadable (ValueError) — recomputing" in out, out
    assert any(
        "Discarding corrupt intermediate cache" in r.getMessage() for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


# ── a session_segments.json whose object holds a malformed session ───────────


def _segments_file_with_a_bad_session(
    tmp_path: Path, *, path_taken: str | None, bad: object = "x",
) -> None:
    """An object, s2 intact, s1 ``bad``: not a list of segments. ``path_taken``
    as in ``_segments_file_not_an_object``."""
    from bristlenose.hashing import hash_bytes

    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["s1"] = bad
    path.write_text(json.dumps(cached), encoding="utf-8")
    if path_taken is None:
        return
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if path_taken == "verified":
        manifest["stages"]["transcribe"]["content_hash"] = hash_bytes(path.read_bytes())
    else:
        manifest["stages"]["transcribe"]["status"] = "running"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize("path_taken", ["verified", "per-session"])
def test_run_recomputes_over_a_segments_file_with_a_malformed_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], path_taken: str,
) -> None:
    _drive(tmp_path, "run", 2, {})
    _segments_file_with_a_bad_session(tmp_path, path_taken=path_taken)
    capsys.readouterr()

    log: dict = {}
    result = _drive(tmp_path, "run", 2, log)

    # Before the fix: a ValidationError out of run(). Now a corrupt file:
    # discarded whole, and every session transcribed again.
    assert log.get("transcribed") == [["s1", "s2"]], log
    assert result is not None and result.summary.transcripts.failed == [], result
    out = " ".join(capsys.readouterr().out.split())
    assert "session_segments.json: cache unreadable (ValidationError) — recomputing" in out, out


@pytest.mark.parametrize(("bad", "error"), [("x", "ValidationError"), (5, "TypeError")])
def test_transcribe_recomputes_over_a_segments_file_with_a_malformed_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture,
    bad: object, error: str,
) -> None:
    _drive(tmp_path, "run", 2, {})
    _segments_file_with_a_bad_session(tmp_path, path_taken=None, bad=bad)
    capsys.readouterr()
    from bristlenose import pipeline

    pipeline._printed_warnings.clear()

    after: dict = {}
    with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
        _drive(tmp_path, "transcribe", 2, after)

    assert after["transcribed"] == [["s1", "s2"]], after
    out = " ".join(capsys.readouterr().out.split())
    assert f"session_segments.json: cache unreadable ({error}) — recomputing" in out, out
    assert any(
        "Discarding corrupt intermediate cache" in r.getMessage() for r in caplog.records
    ), [r.getMessage() for r in caplog.records]


@pytest.mark.parametrize("mode", ["run", "transcribe"])
def test_a_malformed_session_the_cache_would_not_serve_still_discards_the_file(
    tmp_path: Path, mode: str,
) -> None:
    # s3's inputs changed, so it is not served from the cache either way; its
    # entry is malformed all the same. The file is corrupt, and is discarded
    # whole: s1 and s2 are transcribed again too, not served from it.
    _drive(tmp_path, "run", 3, {})
    path = _intermediate(tmp_path, "session_segments.json")
    cached = json.loads(path.read_text(encoding="utf-8"))
    cached["s3"] = "x"
    path.write_text(json.dumps(cached), encoding="utf-8")
    manifest_path = tmp_path / "output" / ".bristlenose" / "pipeline-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["transcribe"]["sessions"]["s3"]["input_hash"] = "stale"
    # run: left RUNNING, as an interrupted run does, so the per-session path reads it.
    manifest["stages"]["transcribe"]["status"] = "running"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    log: dict = {}
    _drive(tmp_path, mode, 3, log)

    assert log.get("transcribed") == [["s1", "s2", "s3"]], log


@pytest.mark.parametrize("mode", ["run", "analyze"])
def test_the_summary_names_the_local_model_that_ran(tmp_path: Path, mode: str) -> None:
    # The summary line ("LLM: … (model)") read llm_model, which a local run
    # snaps to the provider default; Ollama is sent local_model. Every gemma run
    # in the RE#R105 measurement was reported as llama3.2:3b.
    local = {"llm_provider": "local", "llm_model": "llama3.2:3b", "local_model": "gemma4:e4b"}
    _drive(tmp_path, "run", 1, {}, settings_kw=local)
    result = _drive(tmp_path, mode, 1, {}, settings_kw=local)
    assert result is not None and result.llm_model == "gemma4:e4b", result


def test_the_summary_names_a_cloud_model_as_before(tmp_path: Path) -> None:
    cloud = {"llm_provider": "anthropic", "llm_model": "claude-sonnet-4-6",
             "local_model": "gemma4:e4b"}
    result = _drive(tmp_path, "run", 1, {}, settings_kw=cloud)
    assert result is not None and result.llm_model == "claude-sonnet-4-6", result


@pytest.mark.parametrize("mode", ["run", "analyze"])
def test_the_manifest_records_the_local_model_that_ran(tmp_path: Path, mode: str) -> None:
    # Each session's record named llm_model, so `bristlenose status -v` showed
    # every gemma session as llama3.2:3b. Nothing decides reuse from it
    # (fresh_session_ids keys on input fingerprints): this is the record only.
    from bristlenose.manifest import load_manifest

    local = {"llm_provider": "local", "llm_model": "llama3.2:3b", "local_model": "gemma4:e4b"}
    _drive(tmp_path, "run", 1, {}, settings_kw=local)
    if mode == "analyze":
        _drive(tmp_path, mode, 1, {}, settings_kw=local)
    manifest = load_manifest(tmp_path / "output")
    assert manifest is not None
    models = {
        (stage, sid): rec.model
        for stage, record in manifest.stages.items()
        for sid, rec in (record.sessions or {}).items()
        if rec.provider == "local"
    }
    assert models, manifest.stages.keys()
    assert set(models.values()) == {"gemma4:e4b"}, models


def test_every_manifest_write_records_the_reported_model() -> None:
    # The run above reaches some of the fourteen mark_session_* sites, not all
    # (the readable chain, a failed session). Read the rest off the source, as
    # tests/test_prompt_boundary.py does for its call sites.
    # Every `model=` keyword in these two modules is a manifest write or the
    # helper passing its own parameter on; a new site written any other way
    # (llm_model, local_model, wire_model) fails here.
    import inspect
    import re

    import bristlenose.pipeline
    import bristlenose.readable_chain

    for module in (bristlenose.pipeline, bristlenose.readable_chain):
        source = inspect.getsource(module)
        values = re.findall(r"(?<![\w.])model=\s*([^,\n]+)", source)
        assert values, module.__name__
        wrong = [v for v in values if v.strip() not in ("reported_model(self.settings)", "model")]
        assert wrong == [], (module.__name__, wrong)
