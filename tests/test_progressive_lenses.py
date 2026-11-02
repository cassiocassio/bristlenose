"""Progressive lenses, Phase 1: sessions readable one by one.

docs/design-progressive-lenses.md §4 "Gate tests for phase 1". The phase rests
on the first one: whatever the researcher does to session 1 while the run is
still going must survive session 2 arriving.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from bristlenose.manifest import (
    STAGE_MERGE_TRANSCRIPT,
    create_manifest,
    load_manifest,
    mark_session_complete,
    write_manifest,
)
from bristlenose.server.lens_readiness import (
    PROCESSING,
    READABLE,
    WAITING,
    readable_in_manifest,
    session_states,
)
from tests.test_serve_moderator_identities import _TRANSCRIPT, _TWO, _client, _project

# ---------------------------------------------------------------------------
# The manifest overlay and the row states (pure)
# ---------------------------------------------------------------------------


def _facts(*rows: tuple[str, bool]) -> list[dict[str, object]]:
    return [{"session_id": sid, "transcribes": tx} for sid, tx in rows]


class TestOverlay:
    def test_no_manifest_none_readable(self) -> None:
        assert readable_in_manifest(None) == frozenset()

    def test_readable_is_merged(self) -> None:
        m = create_manifest("p", "0")
        assert readable_in_manifest(m) == frozenset()
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, "s1")
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, "s2")
        assert readable_in_manifest(m) == {"s1", "s2"}

    def test_none_readable_the_first_to_transcribe_is_processing(self) -> None:
        states = session_states(_facts(("s1", True), ("s2", True), ("s3", True)), frozenset())
        assert states == {"s1": PROCESSING, "s2": WAITING, "s3": WAITING}

    def test_some_readable_the_next_is_processing(self) -> None:
        states = session_states(_facts(("s1", True), ("s2", True), ("s3", True)), frozenset({"s1"}))
        assert states == {"s1": READABLE, "s2": PROCESSING, "s3": WAITING}

    def test_a_platform_transcript_never_shimmers(self) -> None:
        states = session_states(_facts(("s1", False), ("s2", True)), frozenset())
        assert states == {"s1": WAITING, "s2": PROCESSING}

    def test_a_session_that_failed_stays_waiting_and_does_not_hold_the_shimmer(self) -> None:
        # s2 produced nothing; s3 was delivered after it, so Whisper is on s4.
        states = session_states(
            _facts(("s1", True), ("s2", True), ("s3", True), ("s4", True)),
            frozenset({"s1", "s3"}),
        )
        assert states == {"s1": READABLE, "s2": WAITING, "s3": READABLE, "s4": PROCESSING}

    def test_all_readable_nothing_processing(self) -> None:
        states = session_states(_facts(("s1", True), ("s2", True)), frozenset({"s1", "s2"}))
        assert set(states.values()) == {READABLE}


# ---------------------------------------------------------------------------
# The per-session import
# ---------------------------------------------------------------------------


def _import(client, project: Path, sids: set[str]) -> set[str]:
    from bristlenose.server.importer import import_readable_sessions

    db = client.app.state.db_factory()
    try:
        _, added = import_readable_sessions(db, project, sids)
        return added
    finally:
        db.close()


def _segments(client, sid: str) -> list[tuple[str, str]]:
    body = client.get(f"/api/projects/1/transcripts/{sid}").json()
    return [(s["speaker_code"], s["text"]) for s in body["segments"]]


def _slots(client) -> dict[tuple[str, str], tuple[str, str, str]]:
    rows = client.get("/api/projects/1/sessions").json()["sessions"]
    return {
        (r["session_id"], sp["slot_code"]): (sp["speaker_code"], sp["role"], sp["name"])
        for r in rows for sp in r["speakers"]
    }


def _add_session(project: Path, sid: str, pid: str, day: str) -> None:
    raw = project / "bristlenose-output" / "transcripts-raw"
    (raw / f"{sid}.txt").write_text(_TRANSCRIPT.format(sid=sid, pid=pid, day=day), encoding="utf-8")


class TestPerSessionImport:
    def test_an_edit_made_mid_run_survives_the_next_session_arriving(self, tmp_path: Path) -> None:
        """The test Phase 1 rests on: a split, a rename and a role recode on
        session 1, made while session 2 is still with Whisper."""
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        client = _client(project)
        resp = client.post("/api/projects/1/transcripts/s1/split",
                           json={"position": 1, "token": 4, "verify": "it is good to be here."})
        assert resp.status_code == 200, resp.text
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1",
                          json={"full_name": "Martin Q. Storey", "short_name": "Marty"})
        assert resp.status_code == 200, resp.text
        martin = next(
            sp["person"]
            for r in client.get("/api/projects/1/sessions").json()["sessions"]
            for sp in r["speakers"] if sp["slot_code"] == "m1"
        )
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1",
                          json={"kind": "moderator", "person": martin})
        assert resp.status_code == 200, resp.text
        before_text, before_slots = _segments(client, "s1"), _slots(client)
        assert len(before_text) == 4, "the split is in"
        assert before_slots[("s1", "p1")][1] == "researcher", "the recode is in"

        _add_session(project, "s2", "p2", "21")
        assert _import(client, project, {"s1", "s2"}) == {"s2"}

        assert _segments(client, "s1") == before_text
        after = _slots(client)
        assert {k: v for k, v in after.items() if k[0] == "s1"} == before_slots
        assert ("s2", "p2") in after

    def test_never_deletes_a_session_it_was_not_given(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"), ("s2", "p2", "21")))
        client = _client(project)
        assert {r["session_id"] for r in client.get("/api/projects/1/sessions").json()["sessions"]} \
            == {"s1", "s2"}
        _add_session(project, "s3", "p3", "22")
        assert _import(client, project, {"s3"}) == {"s3"}
        assert {r["session_id"] for r in client.get("/api/projects/1/sessions").json()["sessions"]} \
            == {"s1", "s2", "s3"}

    def test_a_readable_session_whose_file_is_not_there_waits(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        client = _client(project)
        assert _import(client, project, {"s9"}) == set()

    def test_the_same_project_row_as_the_whole_import(self, tmp_path: Path) -> None:
        from bristlenose.server.models import Project

        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        client = _client(project)
        _add_session(project, "s2", "p2", "21")
        _import(client, project, {"s2"})
        db = client.app.state.db_factory()
        try:
            assert db.query(Project).count() == 1
        finally:
            db.close()


# ---------------------------------------------------------------------------
# The server follows a first analysis
# ---------------------------------------------------------------------------


def _start_run(output_dir: Path, run_id: str = "RUN1") -> None:
    """A first analysis in progress: run_started and a live PID file (this process)."""
    from bristlenose.events import KindEnum, Process, RunStartedEvent, append_event, events_path
    from bristlenose.run_lifecycle import _ps_start_time, _write_pid_file

    now = datetime.now(timezone.utc).isoformat()
    append_event(events_path(output_dir), RunStartedEvent(
        ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now,
        process=Process(
            pid=os.getpid(), start_time="x", hostname="h", user="u",
            bristlenose_version="0", python_version="3.12", os="darwin",
        ),
    ))
    _write_pid_file(output_dir, run_id, _ps_start_time(os.getpid()))


def _bundled_client(project: Path, tmp_path: Path):
    """A client whose serve has an SPA bundle to mount: CI's pytest job builds
    none, and without one every report route is the build-incomplete page."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text(
        '<!doctype html><html><head></head><body><div id="bn-app-root"></div></body></html>', encoding="utf-8",
    )
    with patch("bristlenose.server.app._STATIC_DIR", static):
        return _client(project)


def _record_readable(output_dir: Path, *sids: str) -> None:
    m = load_manifest(output_dir) or create_manifest("p", "0")
    for sid in sids:
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, sid)
    write_manifest(m, output_dir)


@pytest.fixture()
def first_analysis(tmp_path: Path):
    """A project mid-way through its first analysis: session 1 written, no report."""
    project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
    out = project / "bristlenose-output"
    for name in ("screen_clusters.json", "theme_groups.json"):
        (out / ".bristlenose" / "intermediate" / name).unlink()
    # The client's startup import must not be what puts s1 in the database.
    s1 = out / "transcripts-raw" / "s1.txt"
    held = s1.read_text(encoding="utf-8")
    s1.unlink()
    client = _bundled_client(project, tmp_path)
    s1.write_text(held, encoding="utf-8")
    _start_run(out)
    return project, out, client


def _follow(client, project: Path) -> None:
    from bristlenose.output_paths import project_output_dir
    from bristlenose.run_condition import read_condition
    from bristlenose.server.progressive import ProgressiveImport

    # What the watcher's ``_on_change`` does on every change to the events log.
    state = client.app.state
    state.condition = read_condition(project_output_dir(project))
    follower = state.__dict__.setdefault(
        "_test_follower", ProgressiveImport(client.app, state.db_factory, project),
    )
    asyncio.run(follower.follow(state.condition))


class TestServerFollowsTheRun:
    def test_a_readable_session_is_imported_and_the_version_moves(self, first_analysis) -> None:
        project, out, client = first_analysis
        assert client.get("/api/projects/1/condition").json()["data_version"] == 0
        _record_readable(out, "s1")
        _follow(client, project)
        body = client.get("/api/projects/1/condition").json()
        assert body["data_version"] == 1
        assert body["lenses"]["sessions"] is True
        assert body["lenses"]["quotes"] is False
        assert client.app.state.sessions_imported is True

        _follow(client, project)  # nothing new: the version stays
        assert client.get("/api/projects/1/condition").json()["data_version"] == 1

    def test_the_grid_lists_every_ingested_session_with_its_state(self, first_analysis) -> None:
        from bristlenose.models import FileType, InputFile, InputSession
        from bristlenose.readable_chain import write_ingest_facts

        project, out, client = first_analysis

        def _session(sid: str, n: int) -> InputSession:
            f = InputFile(path=project / f"{sid}.mov", file_type=FileType.VIDEO,
                          created_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
                          size_bytes=1, duration_seconds=600.0)
            return InputSession(
                session_id=sid, session_number=n, participant_id=f"p{n}", participant_number=n,
                files=[f], session_date=datetime(2026, 9, 20, tzinfo=timezone.utc),
            )

        write_ingest_facts(out, [_session("s1", 1), _session("s2", 2), _session("s3", 3)])
        _record_readable(out, "s1")
        _follow(client, project)
        rows = client.get("/api/projects/1/sessions").json()["sessions"]
        assert [(r["session_id"], r["state"]) for r in rows] == [
            ("s1", "readable"), ("s2", "processing"), ("s3", "waiting"),
        ]
        waiting = rows[2]
        assert waiting["speakers"] == [] and waiting["thumbnail_url"] is None
        assert waiting["duration_seconds"] == 600.0
        assert waiting["source_files"][0]["filename"] == "s3.mov"

    def test_the_status_page_gives_way_once_a_session_is_in(self, first_analysis) -> None:
        project, out, client = first_analysis
        _follow(client, project)
        page = client.get("/report/")
        assert 'data-condition="RUN1:in_progress' in page.text, "no session yet: the in-progress page"
        _record_readable(out, "s1")
        _follow(client, project)
        # The SPA's own route, not the status page. (Whether the bundle is built
        # is the test environment's business: CI's pytest job does not build it.)
        assert 'id="bn-app-root"' in client.get("/report/").text

    def test_a_report_on_record_is_not_progressive(self, tmp_path: Path) -> None:
        """A re-run under an existing report shows that report; every lens stays."""
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        out = project / "bristlenose-output"
        client = _client(project)
        from bristlenose.events import (
            KindEnum,
            OutcomeEnum,
            RunCompletedEvent,
            append_event,
            events_path,
        )

        now = datetime.now(timezone.utc).isoformat()
        _start_run(out, "OLD")
        append_event(events_path(out), RunCompletedEvent(
            ts=now, run_id="OLD", kind=KindEnum.RUN, started_at=now, ended_at=now,
            outcome=OutcomeEnum.COMPLETED,
        ))
        _start_run(out, "NEW")
        _record_readable(out, "s1")
        _follow(client, project)
        assert client.app.state.progress is None
        assert all(client.get("/api/projects/1/condition").json()["lenses"].values())


def test_a_progress_line_is_never_the_terminus(tmp_path: Path) -> None:
    """``run_progress`` per session does not change the condition's latest run."""
    from bristlenose.events import KindEnum, RunProgressEvent, append_event, events_path
    from bristlenose.run_condition import RunStateEnum, read_condition

    out = tmp_path / "bristlenose-output"
    out.mkdir()
    _start_run(out)
    before = read_condition(out).latest
    now = datetime.now(timezone.utc).isoformat()
    for n in (1, 2, 3):
        append_event(events_path(out), RunProgressEvent(
            ts=now, run_id="RUN1", kind=KindEnum.RUN, started_at=now, sessions_readable=n,
        ))
    after = read_condition(out).latest
    assert after == before
    assert after is not None and after.state == RunStateEnum.IN_PROGRESS


# ---------------------------------------------------------------------------
# The pipeline's readable chain
# ---------------------------------------------------------------------------


def _audio_sessions(input_dir: Path, n: int) -> list:
    from bristlenose.models import FileType, InputFile, InputSession

    sessions = []
    for i in range(1, n + 1):
        audio = input_dir / f"s{i}.wav"
        audio.write_bytes(audio.name.encode())  # its own bytes: identical files fold (R49)
        sessions.append(InputSession(
            session_id=f"s{i}", session_number=i, participant_id=f"p{i}", participant_number=i,
            files=[InputFile(path=audio, file_type=FileType.AUDIO,
                             created_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
                             size_bytes=1, duration_seconds=60.0)],
            audio_path=audio, session_date=datetime(2026, 9, 20, tzinfo=timezone.utc),
        ))
    return sessions


def _two_speakers() -> list:
    from bristlenose.models import TranscriptSegment

    return [
        TranscriptSegment(start_time=0, end_time=4, text="So how did you find it?",
                          speaker_label="A"),
        TranscriptSegment(start_time=5, end_time=9, text="It was fine, honestly.",
                          speaker_label="B"),
    ]


async def _passthrough(first, *_a, **_kw):
    return first


def _run(
    tmp_path: Path, *, iter_fn, roles, pii: bool = False, extra=(), match="stop",
    raises: type[BaseException] = RuntimeError, **settings_kw,
) -> tuple:
    """Drive ``Pipeline.run`` on two recordings until the stub stops it."""
    from contextlib import ExitStack

    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    out = input_dir / "bristlenose-output"
    sessions = _audio_sessions(input_dir, 2)

    async def _stop(*_a, **_kw):
        raise RuntimeError("stop after the speakers")

    progress: list[dict[str, object]] = []
    pipeline = Pipeline(BristlenoseSettings(
        output_dir=out, pii_enabled=pii, anthropic_api_key="sk-test", voice_pass=False,
        **settings_kw,
    ))
    pipeline.set_progress_sink(lambda **f: progress.append(f))
    with ExitStack() as stack:
        for target, kw in (
            ("bristlenose.stages.s01_ingest.ingest", {"return_value": sessions}),
            ("bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
             {"new": _passthrough}),
            ("bristlenose.preflight.whisper.preflight_whisper", {"new": lambda **_kw: None}),
            ("bristlenose.stages.s05_transcribe.iter_transcribe_sessions", {"new": iter_fn}),
            ("bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm",
             {"new": roles}),
            ("bristlenose.stages.s05b_identify_speakers.split_single_speaker_llm",
             {"new": _passthrough}),
            ("bristlenose.stages.s08_topic_segmentation.segment_topics", {"new": _stop}),
            *extra,
        ):
            stack.enter_context(patch(target, **kw))
        with pytest.raises(raises, match=match):
            asyncio.run(pipeline.run(input_dir, out))
    return out, progress


def test_session_one_is_readable_before_session_two_is_transcribed(tmp_path: Path) -> None:
    """The outcome in §1, end to end through ``Pipeline.run``: while Whisper is
    still on session 2, session 1's transcript file is written and the manifest
    calls it merged — and stage 5b does not pay for its speakers a second time.

    Whisper runs on its own thread (Phase 3), so "still on session 2" is the stub
    holding session 2 back until session 1 is readable. Run serially, on the event
    loop, nothing could deliver session 1 while the stub waits, and it times out.
    """
    import threading
    import time

    from bristlenose.stages.s05_transcribe import SessionTranscription

    seen_at_s2: dict[str, object] = {}
    out_box: list[Path] = []

    def _iter(needs, _settings, **_kw):
        out = needs[0].audio_path.parent / "bristlenose-output"
        out_box.append(out)
        seen_at_s2["thread"] = threading.current_thread() is not threading.main_thread()
        yield SessionTranscription("s1", _two_speakers())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                if readable_in_manifest(load_manifest(out)):
                    break
            except Exception:  # noqa: BLE001 — a manifest mid-write; look again
                pass
            time.sleep(0.01)
        seen_at_s2["file"] = (out / "transcripts-raw" / "s1.txt").exists()
        seen_at_s2["readable"] = readable_in_manifest(load_manifest(out))
        yield SessionTranscription("s2", _two_speakers())

    role_calls: list[int] = []

    async def _roles(segments, _client, **_kw):
        role_calls.append(len(segments))
        return []

    out, progress = _run(tmp_path, iter_fn=_iter, roles=_roles, match="stop after the speakers")

    assert seen_at_s2 == {"thread": True, "file": True, "readable": frozenset({"s1"})}
    assert role_calls == [2, 2], "each session's speakers are paid for once"
    readable = [f["sessions_readable"] for f in progress if "sessions_readable" in f]
    assert readable[:1] == [1] and max(readable) == 2
    assert readable_in_manifest(load_manifest(out)) == {"s1", "s2"}
    assert sorted(p.name for p in (out / "transcripts-raw").glob("*.txt")) == ["s1.txt", "s2.txt"]


def test_each_sessions_quotes_are_extracted_while_the_next_is_transcribed(
    tmp_path: Path,
) -> None:
    """Phase 3: once session 1 is readable, its topics and quotes run alongside
    Whisper on session 2, and its quotes are recorded for the server while session 2
    is still decoding. Stages 8 and 9 then take the chain's work and pay for nothing
    a second time."""
    import time

    from bristlenose.events import StageOutcome
    from bristlenose.manifest import load_manifest as _load
    from bristlenose.models import (
        ExtractedQuote,
        QuoteType,
        SessionTopicMap,
        TopicBoundary,
        TransitionType,
    )
    from bristlenose.server.lens_readiness import quoted_in_manifest
    from bristlenose.stages.s05_transcribe import SessionTranscription

    seen: dict[str, object] = {}

    def _iter(needs, _settings, **_kw):
        out = needs[0].audio_path.parent / "bristlenose-output"
        yield SessionTranscription("s1", _two_speakers())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                if quoted_in_manifest(_load(out)):
                    break
            except Exception:  # noqa: BLE001 — a manifest mid-write; look again
                pass
            time.sleep(0.01)
        seen["quoted_while_s2_decodes"] = quoted_in_manifest(_load(out))
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(_segments, _client, **_kw):
        return []

    topic_calls: list[list[str]] = []
    quote_calls: list[list[str]] = []

    async def _topics(transcripts, _client, **_kw):
        topic_calls.append([t.session_id for t in transcripts])
        maps = [
            SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                            boundaries=[TopicBoundary(timecode_seconds=0.0, topic_label="Welcome",
                                                      transition_type=TransitionType.TOPIC_SHIFT)])
            for t in transcripts
        ]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, _maps, _client, **kw):
        quote_calls.append([t.session_id for t in transcripts])
        got = [
            ExtractedQuote(session_id=t.session_id, participant_id=t.participant_id,
                           start_timecode=1.0, end_timecode=2.0, text="a quote of some length",
                           topic_label="Welcome", quote_type=QuoteType.GENERAL_CONTEXT)
            for t in transcripts
        ]
        done = kw.get("on_session_done")
        for q in got:
            if done is not None:
                done(q.session_id, [q])
        return got, StageOutcome(attempted=len(got), succeeded=len(got))

    async def _stop(*_a, **_kw):
        raise RuntimeError("stop at clustering")

    _out, progress = _run(
        tmp_path, iter_fn=_iter, roles=_roles, match="stop at clustering",
        extra=(
            ("bristlenose.stages.s08_topic_segmentation.segment_topics", {"new": _topics}),
            ("bristlenose.stages.s09_quote_extraction.extract_quotes", {"new": _quotes}),
            ("bristlenose.stages.s10_quote_clustering.cluster_by_screen", {"new": _stop}),
            ("bristlenose.stages.s11_thematic_grouping.group_by_theme", {"new": _stop}),
        ),
    )
    assert seen == {"quoted_while_s2_decodes": frozenset({"s1"})}
    assert sorted(topic_calls) == [["s1"], ["s2"]], "one call per session, by the chain"
    assert sorted(quote_calls) == [["s1"], ["s2"]], "stage 9 took the chain's quotes"
    # …and kept them: stage 9's file, which clustering reads, holds every session's.
    written = json.loads(
        (_out / ".bristlenose" / "intermediate" / "extracted_quotes.json").read_text(encoding="utf-8"),
    )
    assert sorted(q["session_id"] for q in written) == ["s1", "s2"]
    # The stages say what the chain finished, or the Mac's row keeps the previous
    # stage's count: this run's work, so new, not cached.
    for stage in ("topics", "quotes"):
        pairs = [f for f in progress if f.get("stage") == stage and f.get("sessions_total")]
        assert pairs, f"{stage} reported nothing"
        assert (pairs[-1]["sessions_complete"], pairs[-1]["sessions_total"],
                pairs[-1]["sessions_new"], pairs[-1]["sessions_cached"]) == (2, 2, 2, 0)


def test_the_chains_analysis_runs_on_a_true_first_analysis_alone(tmp_path: Path) -> None:
    """A previous run's topic or quote records may still be fresh, and stage 9 reads
    extracted_quotes.json as that cache; the chain would rewrite it with its own
    quotes. And with a local model, Whisper and the model would compete for the GPU."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.manifest import STAGE_QUOTE_EXTRACTION
    from bristlenose.pipeline import Pipeline
    from bristlenose.session_registry import SessionRegistry

    sessions = _audio_sessions(tmp_path, 2)
    out = tmp_path / "out"
    out.mkdir()

    def _chain(prev, **settings_kw):
        settings = BristlenoseSettings(
            output_dir=out, anthropic_api_key="sk-test", voice_pass=False, **settings_kw,
        )
        status = type("S", (), {"update": lambda *_a, **_k: None})()
        return Pipeline(settings)._readable_chain(
            sessions, prev_manifest=prev, manifest=create_manifest("p", "0"),
            output_dir=out, input_dir=tmp_path, registry=SessionRegistry(out),
            tx_fingerprints={}, segments_path=out / "ss.json", status=status,
        )

    assert _chain(None).analysis is not None
    analysed = create_manifest("p", "0")
    mark_session_complete(analysed, STAGE_QUOTE_EXTRACTION, "s1")
    assert _chain(analysed).analysis is None, "an earlier run's quotes are a cache"
    assert _chain(None, llm_provider="local").analysis is None


def test_with_a_local_model_whisper_stays_on_the_loop(tmp_path: Path) -> None:
    """Phase 1's shape: a local model and MLX Whisper share the GPU."""
    import threading

    from bristlenose.stages.s05_transcribe import SessionTranscription

    on_thread: list[bool] = []

    def _iter(_needs, _settings, **_kw):
        on_thread.append(threading.current_thread() is not threading.main_thread())
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(_segments, _client, **_kw):
        return []

    _run(tmp_path, iter_fn=_iter, roles=_roles, match="stop after the speakers",
         llm_provider="local")
    assert on_thread == [False]


def test_a_failed_delivery_stops_the_chain_and_codes_stay_in_session_order(
    tmp_path: Path,
) -> None:
    """Session 1's early delivery fails: session 2 must not be numbered first."""
    from bristlenose.stages.s05_transcribe import SessionTranscription

    def _iter(_needs, _settings, **_kw):
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    from bristlenose.models import SpeakerRole

    calls: list[int] = []

    async def _roles(segments, _client, **_kw):
        calls.append(len(segments))
        if len(calls) == 1:
            raise ValueError("a programming error in the chain's first delivery")
        for seg in segments:  # what the real pass decides: A asks, B answers
            seg.speaker_role = (
                SpeakerRole.RESEARCHER if seg.speaker_label == "A" else SpeakerRole.PARTICIPANT
            )
        return []

    out, progress = _run(tmp_path, iter_fn=_iter, roles=_roles, match="stop after the speakers")

    assert not [f for f in progress if f.get("sessions_readable")], "nothing was delivered early"
    raw = out / "transcripts-raw"
    assert "[p1]" in (raw / "s1.txt").read_text(encoding="utf-8")
    assert "[p2]" in (raw / "s2.txt").read_text(encoding="utf-8")
    assert len(calls) == 3, "s1 tried once by the chain, then both by stage 5b"


def test_a_redacted_run_records_nothing_readable_before_redaction(tmp_path: Path) -> None:
    """The unredacted transcripts must never be offered to the server."""
    from bristlenose.stages.s05_transcribe import SessionTranscription

    def _iter(_needs, _settings, **_kw):
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(_segments, _client, **_kw):
        return []

    seen: dict[str, object] = {}

    def _remove_pii(transcripts, settings, **_kw):
        out = settings.output_dir
        seen["readable"] = readable_in_manifest(load_manifest(out))
        raise RuntimeError("stop at redaction")

    from bristlenose.events import PipelineAbandonedError

    out, progress = _run(
        tmp_path, iter_fn=_iter, roles=_roles, pii=True, match="pii_removal",
        raises=PipelineAbandonedError,
        extra=(("bristlenose.stages.s07_pii_removal.remove_pii", {"new": _remove_pii}),),
    )
    assert seen == {"readable": frozenset()}
    assert not [f for f in progress if f.get("sessions_readable")]


def test_a_redacted_first_analysis_says_its_sessions_are_readable_once_redacted(
    tmp_path: Path,
) -> None:
    """The chain is off under redaction; redaction is where the sessions become
    readable, and the Mac's shoal hands over on this count."""
    from bristlenose.models import PiiCleanTranscript
    from bristlenose.stages.s05_transcribe import SessionTranscription

    def _iter(_needs, _settings, **_kw):
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(_segments, _client, **_kw):
        return []

    def _remove_pii(transcripts, settings, **_kw):
        return [PiiCleanTranscript(**t.model_dump()) for t in transcripts], []

    _out, progress = _run(
        tmp_path, iter_fn=_iter, roles=_roles, pii=True,
        extra=(("bristlenose.stages.s07_pii_removal.remove_pii", {"new": _remove_pii}),),
    )
    # Nothing before redaction is pinned by the test above; this one, the count after.
    assert [f["sessions_readable"] for f in progress if f.get("sessions_readable")][-1:] == [2]


def test_parsed_transcripts_are_identified_together_and_delivered_in_order(
    tmp_path: Path,
) -> None:
    """A project of platform transcripts must not be slower than the batch: the
    speaker passes run at once, and only the deliveries take turns."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.manifest import create_manifest
    from bristlenose.pipeline import _assign_session_codes, _segments_fingerprint
    from bristlenose.readable_chain import ReadableChain
    from bristlenose.session_registry import SessionRegistry

    out = tmp_path / "bristlenose-output"
    sessions = _audio_sessions(tmp_path, 2)
    in_flight = {"now": 0, "most": 0}
    both = asyncio.Event()

    class _Pass:
        split_records: dict[str, dict[str, object]] = {}
        failed: set[str] = set()

        async def run(self, _sid, _segments):
            in_flight["now"] += 1
            in_flight["most"] = max(in_flight["most"], in_flight["now"])
            if in_flight["now"] == 2:
                both.set()
            await asyncio.wait_for(both.wait(), timeout=5)
            in_flight["now"] -= 1
            return []

    delivered: list[int] = []

    async def _go() -> None:
        chain = ReadableChain(
            order=sessions, settings=BristlenoseSettings(output_dir=out),
            speaker_pass=_Pass(),  # type: ignore[arg-type]
            manifest=create_manifest("p", "0"), output_dir=out, input_dir=tmp_path,
            registry=SessionRegistry.load(out), sentence_paragraphs=set(),
            languages=lambda: ({}, {}), fingerprint=_segments_fingerprint,
            assign_codes=_assign_session_codes, tx_fingerprints={},
            segments_path=out / ".bristlenose" / "intermediate" / "session_segments.json",
            emit=delivered.append,
        )
        await asyncio.gather(
            chain.offer("s1", _two_speakers()), chain.offer("s2", _two_speakers()),
        )
        assert chain.readable == ["s1", "s2"]

    asyncio.run(_go())
    assert in_flight["most"] == 2
    assert delivered == [1, 2]


# ---------------------------------------------------------------------------
# Review fixes: restart, isolation, the end of the run, export
# ---------------------------------------------------------------------------


class TestFollowerEdges:
    def test_a_serve_restarted_mid_run_shows_what_it_already_imported(
        self, tmp_path: Path,
    ) -> None:
        """Startup import pulled session 1 in; nothing new is added, and the
        report must still be the surface, not the in-progress page."""
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        out = project / "bristlenose-output"
        for name in ("screen_clusters.json", "theme_groups.json"):
            (out / ".bristlenose" / "intermediate" / name).unlink()
        client = _bundled_client(project, tmp_path)  # imports s1 at startup
        _start_run(out)
        _record_readable(out, "s1")
        _follow(client, project)
        assert client.app.state.data_version == 0, "nothing was added"
        assert client.app.state.sessions_imported is True
        # The SPA's own route, not the status page. (Whether the bundle is built
        # is the test environment's business: CI's pytest job does not build it.)
        assert 'id="bn-app-root"' in client.get("/report/").text

    def test_one_session_that_will_not_import_does_not_hold_back_the_rest(
        self, first_analysis, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import bristlenose.server.importer as importer

        project, out, client = first_analysis
        _add_session(project, "s2", "p2", "21")
        _add_session(project, "s3", "p3", "22")
        real = importer.import_readable_sessions
        asked: list[str] = []

        def _flaky(db, project_dir, sids, **kw):
            asked.extend(sorted(sids))
            if "s2" in sids:
                raise ValueError("a header the importer chokes on")
            return real(db, project_dir, sids, **kw)

        monkeypatch.setattr(importer, "import_readable_sessions", _flaky)
        _record_readable(out, "s1", "s2", "s3")
        _follow(client, project)
        rows = {r["session_id"] for r in client.get("/api/projects/1/sessions").json()["sessions"]}
        assert {"s1", "s3"} <= rows and "s2" not in rows
        for _ in range(4):
            _follow(client, project)
        assert asked.count("s2") == 3, "tried three times, not on every heartbeat for good"

    def test_an_import_that_fails_once_is_tried_again(
        self, first_analysis, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """One "database is locked" while the researcher edits must not hide a
        session for the rest of the run."""
        import bristlenose.server.importer as importer

        project, out, client = first_analysis
        real = importer.import_readable_sessions
        calls = {"n": 0}

        def _locked_once(db, project_dir, sids, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("database is locked")
            return real(db, project_dir, sids, **kw)

        monkeypatch.setattr(importer, "import_readable_sessions", _locked_once)
        _record_readable(out, "s1")
        _follow(client, project)
        _follow(client, project)
        assert _segments(client, "s1"), "imported on the second try"

    def test_the_overlay_lasts_until_the_whole_report_is_imported(self, first_analysis) -> None:
        from bristlenose.events import (
            KindEnum,
            OutcomeEnum,
            RunCompletedEvent,
            append_event,
            events_path,
        )
        from bristlenose.server.app import _make_run_completed_handler

        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        now = datetime.now(timezone.utc).isoformat()
        done = RunCompletedEvent(ts=now, run_id="RUN1", kind=KindEnum.RUN, started_at=now,
                                 ended_at=now, outcome=OutcomeEnum.COMPLETED)
        append_event(events_path(out), done)
        _follow(client, project)
        assert client.app.state.progress is not None, "terminus seen, report not yet imported"
        handler = _make_run_completed_handler(client.app, client.app.state.db_factory, project)
        asyncio.run(handler(done))
        assert client.app.state.progress is None

    def test_export_waits_for_the_whole_report(self, first_analysis) -> None:
        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        assert client.get("/api/projects/1/export").status_code == 409

    def test_a_row_the_database_holds_stays_readable_whatever_the_manifest_says(
        self, first_analysis,
    ) -> None:
        """A resumed run's fresh manifest records nothing yet: session 1 is
        still the researcher's to read."""
        from bristlenose.readable_chain import write_ingest_facts
        from bristlenose.server.lens_readiness import Progress

        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        write_ingest_facts(out, _audio_sessions(project, 2))
        client.app.state.progress = Progress(readable=frozenset())
        rows = client.get("/api/projects/1/sessions").json()["sessions"]
        assert [(r["session_id"], r["state"]) for r in rows] == [
            ("s1", "readable"), ("s2", "processing"),
        ]
        assert rows[0]["speakers"], "the full row, not a stub"


def test_each_session_s_quotes_are_on_disk_before_the_manifest_says_so(tmp_path: Path) -> None:
    """Phase 2, through ``Pipeline.run``: stage 9 writes a session's quotes to
    ``extracted_quotes.json`` and only then records the session done, while
    the other sessions are still being extracted."""
    from bristlenose.events import StageOutcome
    from bristlenose.models import ExtractedQuote, QuoteType, SessionTopicMap
    from bristlenose.server.lens_readiness import quoted_in_manifest
    from bristlenose.stages.s05_transcribe import SessionTranscription

    def _iter(_needs, _settings, **_kw):
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(_segments, _client, **_kw):
        return []

    async def _topics(ts, _client, **_kw):
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[]) for t in ts]
        return maps, StageOutcome(attempted=len(ts), succeeded=len(ts))

    seen: dict[str, object] = {}

    async def _quotes(ts, _maps, _client, **kw):
        done = kw["on_session_done"]
        q = ExtractedQuote(session_id="s1", participant_id="p1", start_timecode=5.0,
                           end_timecode=9.0, text="It was fine, honestly.",
                           topic_label="", quote_type=QuoteType.GENERAL_CONTEXT)
        done("s1", [q])
        seen["quoted"] = quoted_in_manifest(load_manifest(out_dir))
        seen["file"] = json.loads((out_dir / ".bristlenose" / "intermediate"
                                   / "extracted_quotes.json").read_text(encoding="utf-8"))
        raise RuntimeError("stop after the first session's quotes")

    out_dir = tmp_path / "in" / "bristlenose-output"
    _run(
        tmp_path, iter_fn=_iter, roles=_roles, match="stop after the first session",
        extra=(
            ("bristlenose.stages.s08_topic_segmentation.segment_topics", {"new": _topics}),
            ("bristlenose.stages.s09_quote_extraction.extract_quotes", {"new": _quotes}),
        ),
    )
    assert seen["quoted"] == frozenset({"s1"})
    assert [q["session_id"] for q in seen["file"]] == ["s1"]  # type: ignore[union-attr]


def test_each_sessions_scene_colours_are_written_before_it_is_readable(tmp_path: Path) -> None:
    """Phase 4 item 5: the colour layer arrives with the row, not at the barrier,
    and a colour failure does not stop the session being delivered."""
    from bristlenose.stages.s05_transcribe import SessionTranscription

    calls: list[tuple[str, frozenset[str]]] = []

    def _colours(sessions, transcripts, out_dir):
        out = out_dir.parents[2]
        sid = sessions[0].session_id
        calls.append((sid, readable_in_manifest(load_manifest(out))))
        if sid == "s1":
            raise OSError("ffmpeg could not read the video")
        return {}

    def _iter(needs, _settings, **_kw):
        yield SessionTranscription("s1", _two_speakers())
        yield SessionTranscription("s2", _two_speakers())

    async def _roles(*_a, **_kw):
        return []

    out, _ = _run(
        tmp_path, iter_fn=_iter, roles=_roles, match="stop after the speakers",
        extra=(("bristlenose.utils.scene_colour.extract_scene_colours", {"new": _colours}),),
    )
    assert calls[:2] == [("s1", frozenset()), ("s2", frozenset({"s1"}))]
    assert readable_in_manifest(load_manifest(out)) == {"s1", "s2"}


def test_a_platform_transcripts_duration_is_known_at_ingest(tmp_path: Path) -> None:
    """§4.6 / §7 item 11: the last cue's end, so the timeline scale does not move
    when a platform transcript is imported."""
    from bristlenose.models import FileType, InputFile, InputSession
    from bristlenose.readable_chain import ingest_facts

    vtt = tmp_path / "s1.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Ann>Hello there.\n\n"
        "00:04:58.000 --> 00:05:02.500\n<v Ben>Thanks, bye.\n",
        encoding="utf-8",
    )
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[InputFile(path=vtt, file_type=FileType.SUBTITLE_VTT,
                         created_at=datetime(2026, 9, 20, tzinfo=timezone.utc), size_bytes=1)],
        session_date=datetime(2026, 9, 20, tzinfo=timezone.utc),
        has_existing_transcript=True,
    )
    (fact,) = ingest_facts([session])
    assert fact["duration_seconds"] == pytest.approx(302.5)
    assert fact["transcribes"] is False


# ---------------------------------------------------------------------------
# Redaction: nothing unredacted is readable during the run
# ---------------------------------------------------------------------------


def _record_redacted(output_dir: Path, *sids: str) -> None:
    from bristlenose.manifest import STAGE_PII_REMOVAL

    m = load_manifest(output_dir) or create_manifest("p", "0")
    for sid in sids:
        mark_session_complete(m, STAGE_PII_REMOVAL, sid)
    write_manifest(m, output_dir)


class TestRedactionDuringTheRun:
    def test_a_session_imported_unredacted_is_reread_from_the_redacted_copy(
        self, tmp_path: Path,
    ) -> None:
        """A first analysis with redaction off failed; the serve imported its raw
        transcript. The re-run redacts, and calls s1 readable once stage 7 has it:
        the rows the lens shows must be the redacted ones, not the raw ones."""
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        out = project / "bristlenose-output"
        for name in ("screen_clusters.json", "theme_groups.json"):
            (out / ".bristlenose" / "intermediate" / name).unlink()
        client = _bundled_client(project, tmp_path)  # no run yet: startup imports raw s1
        assert ("p1", "Thanks for having me, it is good to be here.") in _segments(client, "s1")

        _start_run(out)
        cooked = out / "transcripts-cooked"
        cooked.mkdir()
        raw = (out / "transcripts-raw" / "s1.txt").read_text(encoding="utf-8")
        (cooked / "s1.txt").write_text(raw.replace("it is good to be here", "I am [NAME]"), encoding="utf-8")
        _record_redacted(out, "s1")
        _follow(client, project)

        texts = [t for _, t in _segments(client, "s1")]
        assert "Thanks for having me, I am [NAME]." in texts
        assert not any("good to be here" in t for t in texts), "raw text still served"
        assert client.get("/api/projects/1/condition").json()["data_version"] == 1

    def test_a_serve_started_during_a_first_analysis_imports_nothing_at_startup(
        self, tmp_path: Path,
    ) -> None:
        """Stage 6 has written s1's unredacted transcript and stage 7 has not run:
        a serve starting now must not read it in."""
        project = _project(tmp_path, _TWO, sessions=(("s1", "p1", "20"),))
        out = project / "bristlenose-output"
        for name in ("screen_clusters.json", "theme_groups.json"):
            (out / ".bristlenose" / "intermediate" / name).unlink()
        _start_run(out)
        client = _bundled_client(project, tmp_path)
        from bristlenose.server.models import TranscriptSegment

        db = client.app.state.db_factory()
        try:
            assert db.query(TranscriptSegment).count() == 0
        finally:
            db.close()
        # …but the project row is there: every route reads it, the condition first.
        assert client.get("/api/projects/1/condition").status_code == 200


    def test_a_redacted_copy_left_by_an_earlier_run_is_not_this_runs(
        self, first_analysis,
    ) -> None:
        """A redacted first analysis failed; the re-run has redaction off. Its
        sessions are its raw transcripts, not the old redacted copies — and a
        session the old copies do not hold is not refused as missing."""
        project, out, client = first_analysis
        cooked = out / "transcripts-cooked"
        cooked.mkdir()
        raw = (out / "transcripts-raw" / "s1.txt").read_text(encoding="utf-8")
        (cooked / "s1.txt").write_text(raw.replace("it is good to be here", "I am [NAME]"), encoding="utf-8")
        _add_session(project, "s2", "p2", "21")
        _record_readable(out, "s1", "s2")
        _follow(client, project)
        assert ("p1", "Thanks for having me, it is good to be here.") in _segments(client, "s1")
        assert _segments(client, "s2"), "s2 imported from this run's folder"


class TestPredates:
    def test_an_event_timestamp_in_z_form_compares(self) -> None:
        from bristlenose.server.progressive import _predates

        assert _predates("2020-01-01T00:00:00+00:00", "2026-10-12T21:00:00Z") is True
        assert _predates("2026-10-12T21:00:05+00:00", "2026-10-12T21:00:00Z") is False

    def test_a_timestamp_that_will_not_parse_reads_as_the_previous_runs(self) -> None:
        from bristlenose.server.progressive import _predates

        assert _predates("not a time", "2026-10-12T21:00:00Z") is True


class TestARunThatEndsWithoutAReport:
    def _cancel(self, out: Path) -> None:
        from bristlenose.events import (
            Cause,
            CauseCategoryEnum,
            KindEnum,
            RunCancelledEvent,
            append_event,
            events_path,
        )

        now = datetime.now(timezone.utc).isoformat()
        append_event(events_path(out), RunCancelledEvent(
            ts=now, run_id="RUN1", kind=KindEnum.RUN, started_at=now, ended_at=now,
            cause=Cause(category=CauseCategoryEnum.USER_SIGNAL),
        ))

    def test_a_stopped_first_analysis_keeps_what_it_delivered_as_it_was(
        self, first_analysis,
    ) -> None:
        """Every lens lighting over a partial database would show empty sections and
        let a partial report be exported; the overlay stays, with nothing processing."""
        from bristlenose.readable_chain import write_ingest_facts

        project, out, client = first_analysis
        write_ingest_facts(out, _audio_sessions(project, 2))
        _record_readable(out, "s1")
        _follow(client, project)
        before = client.get("/api/projects/1/condition").json()["data_version"]
        self._cancel(out)
        _follow(client, project)

        body = client.get("/api/projects/1/condition").json()
        assert body["lenses"]["signals"] is False and body["lenses"]["sessions"] is True
        assert body["data_version"] == before + 1, "the grid refetches"
        rows = client.get("/api/projects/1/sessions").json()["sessions"]
        assert [(r["session_id"], r["state"]) for r in rows] == [
            ("s1", "readable"), ("s2", "waiting"),
        ], "nothing is processing once the run has stopped"
        refused = client.get("/api/projects/1/export")
        assert refused.status_code == 409
        assert "did not finish" in refused.json()["detail"]

        _follow(client, project)  # a later change to the log moves nothing
        assert client.get("/api/projects/1/condition").json()["data_version"] == before + 1

    def test_a_whole_import_that_fails_ends_the_overlay_without_lifting_it(
        self, first_analysis,
    ) -> None:
        from bristlenose.events import (
            KindEnum,
            OutcomeEnum,
            RunCompletedEvent,
            append_event,
            events_path,
        )
        from bristlenose.server import importer
        from bristlenose.server.app import _make_run_completed_handler

        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        now = datetime.now(timezone.utc).isoformat()
        done = RunCompletedEvent(ts=now, run_id="RUN1", kind=KindEnum.RUN, started_at=now,
                                 ended_at=now, outcome=OutcomeEnum.COMPLETED)
        append_event(events_path(out), done)
        _follow(client, project)

        def _boom(*_a, **_kw):
            raise RuntimeError("import failed")

        with patch.object(importer, "import_project", _boom):  # bound when the handler is made
            handler = _make_run_completed_handler(
                client.app, client.app.state.db_factory, project,
            )
            asyncio.run(handler(done))
        progress = client.app.state.progress
        assert progress is not None and progress.ended
        assert "did not finish" in client.get("/api/projects/1/export").json()["detail"]

    def test_a_report_put_back_under_the_partial_delivery_is_refetched(
        self, first_analysis,
    ) -> None:
        """A failed ``--clean`` run restores the stash: the previous report is the
        project's again, and the SPA, still holding the partial delivery, refetches."""
        from bristlenose.events import (
            KindEnum,
            OutcomeEnum,
            RunCompletedEvent,
            append_event,
            events_path,
        )

        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        before = client.app.state.data_version
        now = datetime.now(timezone.utc).isoformat()
        append_event(events_path(out), RunCompletedEvent(
            ts=now, run_id="OLD", kind=KindEnum.RUN, started_at=now, ended_at=now,
            outcome=OutcomeEnum.COMPLETED,
        ))
        _follow(client, project)
        assert client.app.state.progress is None
        assert client.app.state.data_version == before + 1
