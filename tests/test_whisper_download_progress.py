"""A first run's speech-model download reaches the progress record (R32).

The Mac app draws its ring from ``run_progress``. The ~1.6 GB Whisper download
emitted none, so a first analysis spent minutes under a ring timed for the
analysis alone: it climbed to near full and sat there, and read as hung. The
download is now its own ``download`` stage with the fraction of bytes received.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from bristlenose.config import BristlenoseSettings
from bristlenose.events import StageOutcome
from bristlenose.models import FileType, SessionTopicMap
from bristlenose.pipeline import Pipeline
from bristlenose.preflight import whisper
from tests.conftest import iter_transcribe_from
from tests.test_pipeline_platform_transcripts import _quote, _whisper_segments, audio_session

# ── the preflight hands the bytes to its caller ─────────────────────────────


def _missing_model(monkeypatch: pytest.MonkeyPatch, tty: bool) -> list[str]:
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: "mlx-community/whisper-test")
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "missing")
    monkeypatch.setattr(whisper, "_print_banner", lambda *_a: None)
    monkeypatch.setattr(whisper, "_stderr_is_tty", lambda: tty)
    used: list[str] = []

    def fake_lines(_settings, write=None, **_kw):
        used.append("lines")
        for line in ("@download-start mlx-community/whisper-test 1000",
                     "@download 400 1000", "@download 1000 1000", "@download-done 3.1"):
            write(line)

    monkeypatch.setattr(whisper, "fetch_with_progress_lines", fake_lines)
    monkeypatch.setattr(
        "bristlenose.utils.package_install.ensure_hf_model",
        lambda *_a, **_kw: used.append("native"),
    )
    return used


def _preflight(on_progress) -> None:
    whisper.preflight_whisper(
        settings=BristlenoseSettings(), console=Console(file=None, quiet=True),
        status=None, allow_fetch=True, on_download_progress=on_progress,
    )


def test_off_a_terminal_the_download_reports_its_bytes(monkeypatch) -> None:
    used = _missing_model(monkeypatch, tty=False)
    seen: list[tuple[int, int]] = []
    _preflight(lambda done, total: seen.append((done, total)))
    assert used == ["lines"]
    assert seen == [(0, 1000), (400, 1000), (1000, 1000)]


def test_on_a_terminal_hugging_face_still_draws_its_own_bars(monkeypatch) -> None:
    used = _missing_model(monkeypatch, tty=True)
    seen: list[tuple[int, int]] = []
    _preflight(lambda done, total: seen.append((done, total)))
    assert used == ["native"]
    assert seen == []


# ── the run writes it as a progress stage ───────────────────────────────────


def _run_with_download(tmp_path: Path) -> list[dict]:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    settings = BristlenoseSettings(
        project_name="dl", skip_transcription=False, llm_concurrency=1,
        pii_enabled=False, whisper_language="auto",
    )
    emitted: list[dict] = []

    def _preflight_stub(**kw):
        for done in (0, 600, 1000):
            kw["on_download_progress"](done, 1000)

    async def _stage2(sess, _tmp, **_kw):
        for s in sess:
            s.audio_path = next(f.path for f in s.files if f.file_type == FileType.AUDIO)
        return sess

    def _transcribe(sessions, _settings, **_kw):
        sids = [s.session_id for s in sessions]
        return ({sid: _whisper_segments(sid) for sid in sids}, {},
                StageOutcome(attempted=len(sids), succeeded=len(sids)))

    async def _split(segments, _c, errors=None):
        return segments

    async def _roles(segments, _c, errors=None):
        return []

    async def _topics(transcripts, *_a, **_kw):
        maps = [SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[]) for t in transcripts]
        return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

    async def _quotes(transcripts, *_a, **_kw):
        quotes = [_quote(t.session_id, t.participant_id, 0) for t in transcripts]
        return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

    async def _one(_quotes, *_a, **_kw):
        return [], StageOutcome(attempted=1, succeeded=1)

    pipeline = Pipeline(settings)
    pipeline.set_progress_sink(lambda **fields: emitted.append(fields))
    with (
        patch("bristlenose.stages.s01_ingest.ingest",
              new=lambda *_a, **_kw: [audio_session(input_dir, 1, "rec1")]),
        patch("bristlenose.stages.s02_extract_audio.extract_audio_for_sessions", new=_stage2),
        patch("bristlenose.preflight.whisper.preflight_whisper", new=_preflight_stub),
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
        asyncio.run(pipeline.run(input_dir, tmp_path / "output"))
    return emitted


def test_the_run_reports_the_download_before_transcription(tmp_path: Path) -> None:
    emitted = _run_with_download(tmp_path)
    stages = [e.get("stage") for e in emitted if e.get("stage")]
    downloads = [e["stage_fraction"] for e in emitted if e.get("stage") == "download"]

    assert downloads == [0.0, 0.6, 1.0]
    # The download comes first, and the very next stage named is transcription,
    # before audio extraction runs: otherwise the row goes on saying it is
    # downloading until the first recording is transcribed.
    assert stages[: len(downloads) + 1] == ["download"] * len(downloads) + ["transcribe"]
    assert "download" not in stages[len(downloads):]


# ── review fixes (20 Oct 2026) ──────────────────────────────────────────────


def test_a_partial_cache_counts_what_is_already_on_disk() -> None:
    seen: list[tuple[int, int]] = []
    read = whisper._progress_line_reader(lambda d, t: seen.append((d, t)), already=600)
    read("@download-start repo 1000")
    read("@download 200 1000")
    read("@download 900 1000")  # never past the whole
    assert seen == [(600, 1000), (800, 1000), (1000, 1000)]


def test_a_progress_fault_never_fails_the_download(caplog) -> None:
    calls = []

    def sink(done: int, total: int) -> None:
        calls.append(done)
        raise ValueError("sink broke")

    read = whisper._progress_line_reader(sink)
    read("@download-start repo 1000")      # raises inside, swallowed and logged
    read("@download 500 1000")             # forwarding has stopped
    assert calls == [0]
    assert "stopped reporting" in caplog.text


def test_the_real_line_writer_and_reader_agree(monkeypatch) -> None:
    """Not hand-written lines: the format fetch_with_progress_lines prints."""
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: "repo")
    states = iter(["missing", "cached"])
    monkeypatch.setattr(whisper, "cache_state", lambda _r: next(states))
    monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r: 1000)

    def fake_hf(_repo, tqdm_class=None):
        bar = tqdm_class(total=1000, unit="B", desc="Downloading bytes")
        bar.update(400)
        bar.update(600)

    monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model", fake_hf)
    seen: list[tuple[int, int]] = []
    whisper.fetch_with_progress_lines(
        BristlenoseSettings(), write=whisper._progress_line_reader(lambda d, t: seen.append((d, t)))
    )
    assert seen[0] == (0, 1000)
    assert seen[-1] == (1000, 1000)


def test_a_predicted_total_leaves_out_the_download() -> None:
    """The ring measures from the download's end, so every predicted total must too."""
    import time
    from types import SimpleNamespace

    from bristlenose.timing import Estimate

    pipeline = Pipeline(BristlenoseSettings(project_name="frame"))
    emitted: list[dict] = []
    pipeline.set_progress_sink(lambda **f: emitted.append(f))
    pipeline._run_start_perf = time.perf_counter() - 1_000   # run started 1000 s ago
    pipeline._download_started = time.perf_counter() - 900   # download took 900 s
    pipeline._model_download_seen = True
    pipeline._end_model_download()
    assert 899 < pipeline._download_seconds < 901

    remaining = Estimate.__new__(Estimate)
    object.__setattr__(remaining, "total_seconds", 300.0)
    pipeline._estimator = SimpleNamespace(
        stage_completed=lambda *_a: remaining,
        stage_budget=lambda *_a, **_k: None,  # cold: no ring slice
    )
    pipeline._emit = lambda _e: None
    pipeline._emit_remaining("transcribe", 50)
    # 100 s of analysis + 300 s left, not 1000 + 300.
    assert 399 < emitted[-1]["predicted_total_seconds"] < 402

    pipeline._carry_eta(remaining)
    assert 399 < pipeline._last_predicted_total < 402


# ── a run while the Mac app's own download runs waits on it ─────────────────
# The app starts the Whisper download in the background from launch (owner,
# 18 and 22 Oct 2026); a run started meanwhile must not fetch a second copy.


def _host_downloading(monkeypatch, *, states, alive=True, bytes_seq=(0,)):
    used = _missing_model(monkeypatch, tty=False)
    monkeypatch.setenv("_BRISTLENOSE_WHISPER_FETCH_PID", "4321")
    states_it = iter(states)
    last = [states[-1]]

    def state(_r):
        last[0] = next(states_it, last[0])
        return last[0]

    monkeypatch.setattr(whisper, "cache_state", state)
    monkeypatch.setattr(whisper, "_host_fetch_alive", lambda _pid: alive)
    bytes_it = iter(bytes_seq)
    held = [bytes_seq[-1]]

    def in_flight(_r):
        held[0] = next(bytes_it, held[0])
        return held[0]

    monkeypatch.setattr(whisper, "_bytes_in_flight", in_flight)
    monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r: 1000)
    naps = [0]

    def sleep(_s):
        # A wait that never ends fails here, fast, rather than hanging the suite.
        naps[0] += 1
        assert naps[0] < 200, "the run waited on the app's download for ever"

    monkeypatch.setattr(whisper.time, "sleep", sleep)
    return used


def test_the_run_waits_for_the_apps_download_and_reports_its_bytes(monkeypatch) -> None:
    used = _host_downloading(
        monkeypatch, states=["missing", "missing", "missing", "cached"], bytes_seq=(0, 700),
    )
    seen: list[tuple[int, int]] = []
    _preflight(lambda done, total: seen.append((done, total)))
    assert used == []
    assert seen == [(0, 1000), (700, 1000)]


def test_when_the_apps_download_has_gone_the_run_fetches_itself(monkeypatch) -> None:
    used = _host_downloading(monkeypatch, states=["missing"], alive=False)
    _preflight(lambda *_a: None)
    assert used == ["lines"]


def test_a_stalled_download_the_run_cannot_see_is_not_waited_on_for_ever(monkeypatch) -> None:
    # The process cannot be asked (None), and no bytes move: give up and fetch.
    used = _host_downloading(monkeypatch, states=["missing"], alive=None, bytes_seq=(300,))
    ticks = iter(range(0, 10_000, 100))
    monkeypatch.setattr(whisper.time, "monotonic", lambda: float(next(ticks)))
    _preflight(lambda *_a: None)
    assert used == ["lines"]


def test_a_download_known_to_be_alive_is_waited_on_though_its_file_sits_still(monkeypatch) -> None:
    # hf_xet's partial file can sit still while bytes land: a live job is waited on.
    used = _host_downloading(
        monkeypatch, states=["missing"] * 50 + ["cached"], bytes_seq=(300,),
    )
    ticks = iter(range(0, 100_000, 100))
    monkeypatch.setattr(whisper.time, "monotonic", lambda: float(next(ticks)))
    _preflight(lambda *_a: None)
    assert used == []


def test_without_the_apps_download_nothing_changes(monkeypatch) -> None:
    used = _missing_model(monkeypatch, tty=False)
    monkeypatch.delenv("_BRISTLENOSE_WHISPER_FETCH_PID", raising=False)
    _preflight(lambda *_a: None)
    assert used == ["lines"]
