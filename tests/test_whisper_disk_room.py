"""A fetch the cache's volume cannot hold is refused before a byte is written.

A Mac with little free space used to find out mid-download, as hf_xet's own error, after
the time was spent; below the app's auto-start floor it found out never (30 Oct 2026). The
download peaks at its final size, 1,539 MB for the default model, so the ask is the model
plus 1 GB of headroom, measured on the volume the cache lives on.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest
from rich.console import Console

from bristlenose.config import BristlenoseSettings
from bristlenose.preflight import PreflightAbortedError, whisper
from bristlenose.utils.package_install import PackageInstallError

REPO = "mlx-community/whisper-large-v3-turbo"  # 1614 MB in _DOWNLOAD_MB
NEED = 1614 * 1_000_000 + 1_000_000_000


def _free(monkeypatch: pytest.MonkeyPatch, free: int | None, where: str = "/cache") -> None:
    monkeypatch.setattr(
        whisper, "_cache_volume_free_bytes",
        lambda: None if free is None else (free, Path(where)),
    )


def test_a_volume_too_small_for_the_model_refuses(monkeypatch) -> None:
    _free(monkeypatch, 700_000_000)
    with pytest.raises(PreflightAbortedError) as err:
        whisper.ensure_disk_room(REPO)
    msg = str(err.value)
    assert "~2.6 GB" in msg and "~700 MB" in msg and "Disk full" in msg
    # It names where the model will be written, not the nearest folder that exists.
    assert "huggingface/hub" in msg


def test_exactly_enough_goes_ahead(monkeypatch) -> None:
    _free(monkeypatch, NEED)
    whisper.ensure_disk_room(REPO)


def test_a_repo_we_never_measured_is_not_refused_on_a_guess(monkeypatch) -> None:
    _free(monkeypatch, 0)
    whisper.ensure_disk_room("someone/unmeasured-model")


def test_a_volume_that_will_not_say_is_not_an_obstacle(monkeypatch) -> None:
    _free(monkeypatch, None)
    whisper.ensure_disk_room(REPO)


def test_the_message_is_one_the_mac_app_classifies_as_a_disk_failure(monkeypatch) -> None:
    """Read the pattern from PipelineRunner.swift (which lowercases the tail), not a copy."""
    swift = (
        Path(__file__).resolve().parent.parent
        / "desktop" / "Bristlenose" / "Bristlenose" / "PipelineRunner.swift"
    ).read_text(encoding="utf-8")
    m = re.search(r'matches\(tail, #"([^"]*)"#\) \{ return \.disk \}', swift)
    assert m, "the .disk classifier in PipelineRunner.swift moved; update this test"
    _free(monkeypatch, 500_000_000)
    with pytest.raises(PreflightAbortedError) as err:
        whisper.ensure_disk_room(REPO)
    assert re.search(m.group(1), str(err.value).lower())


def test_the_volume_asked_is_the_one_the_cache_lives_on(monkeypatch, tmp_path: Path) -> None:
    """A cache directory that does not exist yet is measured at its nearest parent."""
    monkeypatch.setattr(whisper, "_hf_cache_root", lambda: tmp_path / "not" / "yet" / "hub")
    free, where = whisper._cache_volume_free_bytes()  # type: ignore[misc]
    assert where == tmp_path
    assert free > 0


def _missing(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
    # A shell the Mac app spawned (or a developer) may export this; the run would then wait
    # on a real pid instead of reaching the check.
    monkeypatch.delenv("_BRISTLENOSE_WHISPER_FETCH_PID", raising=False)
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "missing")
    monkeypatch.setattr(whisper, "_print_banner", lambda *_a: None)
    monkeypatch.setattr(whisper, "_stderr_is_tty", lambda: True)
    fetched: list[str] = []
    monkeypatch.setattr(
        "bristlenose.utils.package_install.ensure_hf_model",
        lambda *_a, **_kw: fetched.append("fetched"),
    )
    return fetched


def _run_preflight() -> None:
    whisper.preflight_whisper(
        settings=BristlenoseSettings(), console=Console(quiet=True), status=None, allow_fetch=True,
    )


def test_a_run_that_needs_whisper_stops_before_fetching(monkeypatch) -> None:
    fetched = _missing(monkeypatch)
    _free(monkeypatch, 1_000_000_000)
    with pytest.raises(PreflightAbortedError, match="Disk full"):
        _run_preflight()
    assert fetched == []


def test_a_run_with_room_fetches(monkeypatch) -> None:
    fetched = _missing(monkeypatch)
    _free(monkeypatch, 50_000_000_000)
    _run_preflight()
    assert fetched == ["fetched"]


def test_while_the_app_is_downloading_its_partial_file_is_not_held_against_the_run(
    monkeypatch,
) -> None:
    """Free space is already net of the app's partial file; waiting needs no room of its own."""
    fetched = _missing(monkeypatch)
    _free(monkeypatch, 100_000_000)  # would refuse a fresh fetch
    monkeypatch.setattr(whisper, "_host_fetch_pid", lambda: 4242)
    monkeypatch.setattr(whisper, "_wait_for_host_fetch", lambda *_a, **_kw: True)
    _run_preflight()
    assert fetched == []  # the app's download landed it; this run fetched nothing


def test_the_download_job_stops_before_announcing_a_download(monkeypatch) -> None:
    """`doctor --fetch --progress-lines` must not print @download-start for a fetch it will refuse."""
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "missing")
    _free(monkeypatch, 1_000_000_000)
    lines: list[str] = []
    with pytest.raises(PreflightAbortedError, match="Disk full"):
        whisper.fetch_with_progress_lines(BristlenoseSettings(), write=lines.append)
    assert lines == []


def test_an_already_cached_model_needs_no_room(monkeypatch) -> None:
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "cached")
    _free(monkeypatch, 0)
    lines: list[str] = []
    whisper.fetch_with_progress_lines(BristlenoseSettings(), write=lines.append)
    assert lines[-1].startswith("@download-done")


# ── a dead download's partial file is not a tenant ──────────────────────────


def _cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    monkeypatch.setattr(whisper, "_repo_cache_dir", lambda _r: tmp_path)
    return blobs


def _file(path: Path, size: int, age_s: float) -> None:
    path.write_bytes(b"x" * size)
    t = time.time() - age_s
    os.utime(path, (t, t))


def test_a_stale_partial_is_removed_and_counted(monkeypatch, tmp_path: Path) -> None:
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "abc.937ec48d.incomplete", 5000, age_s=3600)
    assert whisper.discard_stale_partials(REPO) == 5000
    assert not (blobs / "abc.937ec48d.incomplete").exists()


def test_a_partial_being_written_is_left_alone(monkeypatch, tmp_path: Path) -> None:
    """Another process may be fetching: its file was touched seconds ago."""
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "live.incomplete", 5000, age_s=3)
    assert whisper.discard_stale_partials(REPO) == 0
    assert (blobs / "live.incomplete").exists()


def test_a_finished_blob_is_never_touched(monkeypatch, tmp_path: Path) -> None:
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "951ed3fc1203e6a6", 5000, age_s=99999)
    assert whisper.discard_stale_partials(REPO) == 0
    assert (blobs / "951ed3fc1203e6a6").exists()


def test_no_cache_yet_is_not_an_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(whisper, "_repo_cache_dir", lambda _r: tmp_path / "nowhere")
    assert whisper.discard_stale_partials(REPO) == 0


def test_a_run_clears_the_orphan_before_it_asks_for_room(monkeypatch, tmp_path: Path) -> None:
    """The orphan is the disk the check would otherwise count against the fetch."""
    fetched = _missing(monkeypatch)
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "dead.incomplete", 5000, age_s=3600)
    seen: list[bool] = []
    monkeypatch.setattr(
        whisper, "ensure_disk_room", lambda _r: seen.append((blobs / "dead.incomplete").exists())
    )
    _run_preflight()
    assert seen == [False] and fetched == ["fetched"]


def test_the_download_job_clears_the_orphan_too(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "missing")
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "dead.incomplete", 5000, age_s=3600)
    seen: list[bool] = []
    monkeypatch.setattr(
        whisper, "ensure_disk_room", lambda _r: seen.append((blobs / "dead.incomplete").exists())
    )
    monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r: 1000)
    monkeypatch.setattr(
        "bristlenose.utils.package_install.ensure_hf_model", lambda *_a, **_k: None
    )
    with pytest.raises(PackageInstallError, match="not complete"):  # the stub leaves it uncached
        whisper.fetch_with_progress_lines(BristlenoseSettings(), write=lambda _l: None)
    assert seen == [False]


# ── an orphan too young to sweep at the start is swept once the fetch has succeeded ─────────


def test_a_young_partial_is_kept_by_the_start_sweep_and_taken_by_the_settled_one(
    monkeypatch, tmp_path: Path
) -> None:
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "young.incomplete", 5000, age_s=45)  # killed 45 s ago
    assert whisper.discard_stale_partials(REPO) == 0                       # start: left alone
    assert whisper.discard_stale_partials(REPO, min_age_s=whisper._SETTLED_PARTIAL_S) == 5000


def test_a_writer_touched_seconds_ago_survives_even_the_settled_sweep(
    monkeypatch, tmp_path: Path
) -> None:
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "live.incomplete", 5000, age_s=3)
    assert whisper.discard_stale_partials(REPO, min_age_s=whisper._SETTLED_PARTIAL_S) == 0


def test_a_successful_download_job_sweeps_the_orphans_it_left_behind(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    states = iter(["missing", "cached"])
    monkeypatch.setattr(whisper, "cache_state", lambda _r: next(states))
    monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r: 1000)
    _free(monkeypatch, 50_000_000_000)
    blobs = _cache(monkeypatch, tmp_path)
    _file(blobs / "orphan.incomplete", 5000, age_s=45)
    monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model", lambda *_a, **_k: None)
    lines: list[str] = []
    whisper.fetch_with_progress_lines(BristlenoseSettings(), write=lines.append)
    assert lines[-1].startswith("@download-done")
    assert not (blobs / "orphan.incomplete").exists()


def test_a_message_that_would_round_both_figures_alike_shows_the_difference(monkeypatch) -> None:
    """'needs ~2.6 GB and only ~2.6 GB is free' (seen on a macOS 27 guest) tells nobody anything."""
    _free(monkeypatch, NEED - 40_000_000)
    with pytest.raises(PreflightAbortedError) as err:
        whisper.ensure_disk_room(REPO)
    msg = str(err.value)
    assert "2.61 GB" in msg and "2.57 GB" in msg
