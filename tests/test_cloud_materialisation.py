"""Cloud-placeholder handling — `bristlenose/utils/fs.py`.

Dataless files can't be created in CI (no File Provider), so `st_flags` is
faked. What's worth pinning is the *decision* logic, not the kernel's.

Motivating incident: a Dropbox project whose media were online-only failed a
run with "ffprobe timed out after 30s", which reads as "your video is broken"
when it meant "your file was still downloading". Reproduced 29 Jul 2026 —
`docs/design-project-storage.md` §3.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bristlenose.utils.fs import (
    SF_DATALESS,
    CloudFetchTimeoutError,
    cloud_provider_for,
    ensure_materialised,
    is_dataless,
)


def _fake_stat(monkeypatch, flags: int, size: int = 1024) -> None:
    """Fake `st_flags` on the stat result, on every platform.

    NOT via ``os.stat_result(tuple(st), {...})``: that second dict only
    carries fields the *platform* declares, so Linux — which has no
    ``st_flags`` at all — silently drops it and the fake becomes a no-op.
    Three tests then assert real macOS behaviour and fail on ubuntu while
    passing locally, which is exactly the CI-parity trap CLAUDE.md warns
    about; it held up the 0.23.0 release.

    A proxy object carries the attribute everywhere (the same shape
    `test_linux_without_st_flags_is_false` already uses to prove the
    opposite case), and the code under test only ever reads it by name.
    """
    real = os.stat

    class _Stat:
        def __init__(self, st) -> None:  # type: ignore[no-untyped-def]
            self._st = st
            self.st_flags = flags
            self.st_size = size

        def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
            return getattr(self._st, name)

    monkeypatch.setattr(os, "stat", lambda p, *a, **k: _Stat(real(p, *a, **k)))


class TestIsDataless:
    def test_resident_file_is_not_dataless(self, tmp_path: Path) -> None:
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        assert is_dataless(f) is False

    def test_missing_file_is_not_dataless(self, tmp_path: Path) -> None:
        # An absent file is "gone", not "in the cloud" — a different state with
        # a different remedy. Must not be conflated.
        assert is_dataless(tmp_path / "nope.mp4") is False

    def test_dataless_flag_is_detected(self, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        _fake_stat(monkeypatch, SF_DATALESS)
        assert is_dataless(f) is True

    def test_other_flags_do_not_false_positive(self, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        _fake_stat(monkeypatch, 0x00000002)  # UF_IMMUTABLE, not dataless
        assert is_dataless(f) is False

    def test_linux_without_st_flags_is_false(self, tmp_path: Path, monkeypatch) -> None:
        """The CLI is first-class on Linux, where `st_flags` doesn't exist.

        A bare `st.st_flags` would be an AttributeError on every Linux run.
        """
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        real = os.stat

        class NoFlags:
            def __init__(self, st):
                self._st = st

            def __getattr__(self, name):
                if name == "st_flags":
                    raise AttributeError(name)
                return getattr(self._st, name)

        monkeypatch.setattr(os, "stat", lambda p, *a, **k: NoFlags(real(p, *a, **k)))
        assert is_dataless(f) is False


class TestCloudProviderFor:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/Users/x/Library/CloudStorage/Dropbox/study/a.mp4", "Dropbox"),
            ("/Users/x/Library/CloudStorage/GoogleDrive-a@b.com/s/a.mp4", "Google Drive"),
            ("/Users/x/Library/CloudStorage/OneDrive-Acme Corp/s/a.mp4", "OneDrive"),
            ("/Users/x/Library/CloudStorage/Box-Box/s/a.mp4", "Box"),
            ("/Users/x/Library/Mobile Documents/com~apple~CloudDocs/a.mp4", "iCloud Drive"),
            ("/Users/x/Documents/study/a.mp4", None),
            ("/Volumes/T7/study/a.mp4", None),
        ],
    )
    def test_provider_names(self, path: str, expected: str | None) -> None:
        assert cloud_provider_for(Path(path)) == expected

    def test_unknown_provider_still_gets_a_name(self) -> None:
        """Structural, not an allowlist — a provider we've never heard of still
        resolves, so the researcher is told *something* rather than nothing."""
        p = Path("/Users/x/Library/CloudStorage/Fastmail-a@b.com/s/a.mp4")
        assert cloud_provider_for(p) == "Fastmail"


class TestEnsureMaterialised:
    def test_resident_file_is_a_no_op(self, tmp_path: Path) -> None:
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        assert ensure_materialised(f) is False

    def test_dataless_file_is_read_and_reported(self, tmp_path: Path, monkeypatch) -> None:
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        _fake_stat(monkeypatch, SF_DATALESS)
        seen: list[tuple[str, str | None]] = []
        # The file is really readable here, so the "fetch" returns at once —
        # what's pinned is that the wait is announced before it starts.
        assert ensure_materialised(f, on_wait=lambda p, prov: seen.append((p.name, prov))) is True
        assert seen == [("interview.mp4", None)]

    def test_never_arriving_file_raises_a_distinct_error(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A dead provider must NOT surface as a probe failure.

        "Still downloading" and "corrupt file" want opposite remedies from the
        researcher, so they must never share an exception type or a message.
        """
        f = tmp_path / "interview.mp4"
        f.write_bytes(b"x" * 64)
        _fake_stat(monkeypatch, SF_DATALESS)

        import bristlenose.utils.fs as fs_mod

        class NeverReturns:
            def __init__(self, *a, **kw):
                import time

                time.sleep(30)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(fs_mod, "open", NeverReturns, raising=False)
        with pytest.raises(CloudFetchTimeoutError) as exc:
            ensure_materialised(f, timeout=0.2)
        assert "fetched" in str(exc.value)
        assert "ffprobe" not in str(exc.value)


class TestReadSitesAreGuarded:
    """Every ffmpeg/ffprobe site that reads a user file must fetch it FIRST.

    The bug this whole feature exists to kill: the download happens *inside* a
    subprocess timeout, so a slow fetch is reported as a broken file. Two sites
    were already guarded (`probe_duration`, `has_audio_stream`); these are the
    other four. What's pinned per site is the **degradation contract** — fatal,
    cosmetic, or skippable — plus, crucially, that the subprocess is never
    reached, since reaching it is the defect.
    """

    @staticmethod
    def _explode(monkeypatch, module, subprocess_guard: bool = True) -> list[str]:
        """Make the fetch time out in *module*, and trip a flag if ffmpeg runs."""
        ran: list[str] = []

        def boom(path, *a, **kw):  # type: ignore[no-untyped-def]
            raise CloudFetchTimeoutError(
                f"{Path(path).name} was still being fetched from Dropbox after 30 minutes"
            )

        monkeypatch.setattr(module, "ensure_materialised", boom)
        if subprocess_guard:
            def never(*a, **kw):  # type: ignore[no-untyped-def]
                ran.append("subprocess")
                raise AssertionError("ffmpeg ran despite an unmaterialised source")

            monkeypatch.setattr(module.subprocess, "run", never)
        return ran

    @pytest.mark.parametrize("site", ["extract_audio_from_video", "has_audio_stream"])
    def test_stage_2_reads_raise_the_fetch_timeout_unwrapped(
        self, tmp_path: Path, monkeypatch, site: str,
    ) -> None:
        """Stage 2's two reads let ``CloudFetchTimeoutError`` through as itself,
        never as ``AudioToolError``: wrapped, it aborted the whole run as a
        broken toolchain (category unknown), when one recording was merely not
        downloaded in time (docs/design-cloud-files.md, pattern B). And the
        subprocess is never reached — reaching it is the original defect.

        The provider rides in the exception for the log line only: what a
        researcher reads is the categorised cause, and that names neither the
        provider nor the file."""
        import bristlenose.utils.audio as audio_mod
        from bristlenose.refusals import CLOUD_FETCH_MESSAGE
        from bristlenose.run_lifecycle import categorise_exception
        from bristlenose.utils.audio import AudioToolError

        ran = self._explode(monkeypatch, audio_mod)
        src = tmp_path / "interview.mov"
        src.write_bytes(b"x")
        call = getattr(audio_mod, site)
        args = (src, tmp_path / "out.wav") if site == "extract_audio_from_video" else (src,)
        with pytest.raises(CloudFetchTimeoutError) as exc:
            call(*args)
        assert not isinstance(exc.value, AudioToolError)
        assert ran == [], "ffmpeg/ffprobe ran despite an unmaterialised source"
        cause = categorise_exception(exc.value)
        assert cause.message == CLOUD_FETCH_MESSAGE
        assert "Dropbox" not in (cause.message or "")
        assert "interview.mov" not in (cause.message or "")

    def test_media_probe_degrades_to_none_pair(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """The scan-time probe (duration + container meta, one ffprobe). A
        nicety — it must never download, never fail a run, and must say why.
        `ran == []` is asserted because after the probe widened its except, a
        bare AssertionError from the guard would be swallowed into "Could not
        probe" and a None pair — the flag is the only signal that survives."""
        import bristlenose.utils.audio as audio_mod
        from bristlenose.utils.audio import probe_media

        ran = self._explode(monkeypatch, audio_mod)
        src = tmp_path / "interview.mov"
        src.write_bytes(b"x")
        with caplog.at_level("WARNING"):
            assert probe_media(src) == (None, None)
        assert "fetched" in caplog.text
        assert ran == [], "ffprobe ran despite an unmaterialised source"

    def test_thumbnail_degrades_to_none(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """A thumbnail is cosmetic — losing it must not fail a run. But it has to
        say WHY: this site historically swallowed the reason and thumbnails just
        silently vanished."""
        import bristlenose.utils.video as video_mod
        from bristlenose.utils.video import extract_thumbnail

        self._explode(monkeypatch, video_mod)
        src = tmp_path / "interview.mov"
        src.write_bytes(b"x")
        with caplog.at_level("WARNING"):
            assert extract_thumbnail(src, tmp_path / "thumb.jpg", timestamp=1.0) is None
        assert "fetched" in caplog.text

    def test_clip_export_degrades_to_none(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """The likeliest site to hit this in real use — cutting clips is the
        "go back to an old study" operation, which is exactly when sources have
        been evicted."""
        import bristlenose.server.clip_backend as clip_mod
        from bristlenose.server.clip_backend import FFmpegBackend

        self._explode(monkeypatch, clip_mod)
        src = tmp_path / "interview.mov"
        src.write_bytes(b"x")
        with caplog.at_level("WARNING"):
            assert FFmpegBackend().extract_clip(
                src, tmp_path / "clip.mp4", start=1.0, end=2.0
            ) is None
        assert "fetched" in caplog.text


class TestRunBudget:
    """One stalled provider must not cost a run 30 minutes per file.

    The bound is per file, and a run reads many: stage 2 four at a time, stage
    5 one at a time. With a provider stalled on 20 recordings, sessions failed
    only after 2.5 h (videos) or 10 h (audio). Inside a run, after the first
    timeout for a provider, its later placeholders get the short bound; other
    providers keep the full one, and serve, which sets no budget, is unchanged
    (docs/design-cloud-files.md, pattern A).
    """

    LONG = 1.0
    SHORT = 0.1

    @pytest.fixture
    def stalled(self, tmp_path: Path, monkeypatch):
        """Every placeholder's read blocks until the test ends; returns a
        factory for placeholder paths under a provider's folder, and the list of
        paths whose read was started."""
        import threading

        import bristlenose.utils.fs as fs_mod

        release = threading.Event()
        started: list[str] = []

        class Blocks:
            def __init__(self, path, *a, **kw) -> None:
                started.append(Path(path).name)
                release.wait()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n):
                return b""

        _fake_stat(monkeypatch, SF_DATALESS)
        monkeypatch.setattr(fs_mod, "open", Blocks, raising=False)
        monkeypatch.setattr(fs_mod, "MATERIALISE_TIMEOUT_SECONDS", self.LONG)
        monkeypatch.setattr(fs_mod, "MATERIALISE_TRIPPED_TIMEOUT_SECONDS", self.SHORT)

        def placeholder(folder: str, name: str) -> Path:
            f = tmp_path / "Library" / folder / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"x")
            return f

        yield placeholder, started
        release.set()

    @staticmethod
    def _timed_out_after(path: Path) -> float:
        import time

        t0 = time.monotonic()
        with pytest.raises(CloudFetchTimeoutError):
            ensure_materialised(path)
        return time.monotonic() - t0

    def test_a_tripped_provider_gets_the_short_bound(self, stalled) -> None:
        from bristlenose.utils.fs import cloud_fetch_budget

        placeholder, started = stalled
        a = placeholder("CloudStorage/Dropbox", "a.mp4")
        b = placeholder("CloudStorage/Dropbox", "b.mp4")
        with cloud_fetch_budget():
            assert self._timed_out_after(a) >= self.LONG * 0.9
            assert self._timed_out_after(b) < self.LONG * 0.5
        # The short wait still starts the read, so the provider keeps fetching.
        # Polled: the reader thread may not have run its first line by the time
        # the short join returns on a loaded machine.
        import time

        deadline = time.monotonic() + 2.0
        while len(started) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert started == ["a.mp4", "b.mp4"]

    def test_another_provider_keeps_the_long_bound(self, stalled) -> None:
        from bristlenose.utils.fs import cloud_fetch_budget

        placeholder, _started = stalled
        a = placeholder("CloudStorage/Dropbox", "a.mp4")
        c = placeholder("Mobile Documents/com~apple~CloudDocs", "c.mp4")
        with cloud_fetch_budget():
            self._timed_out_after(a)
            assert self._timed_out_after(c) >= self.LONG * 0.9

    def test_without_a_run_budget_every_file_gets_the_long_bound(self, stalled) -> None:
        # Serve's reads (clips, stills, screens) set no budget.
        placeholder, _started = stalled
        a = placeholder("CloudStorage/Dropbox", "a.mp4")
        b = placeholder("CloudStorage/Dropbox", "b.mp4")
        assert self._timed_out_after(a) >= self.LONG * 0.9
        assert self._timed_out_after(b) >= self.LONG * 0.9

    def test_the_budget_does_not_outlive_its_run(self, stalled) -> None:
        from bristlenose.utils.fs import RUN_CLOUD_BUDGET, cloud_fetch_budget

        placeholder, _started = stalled
        a = placeholder("CloudStorage/Dropbox", "a.mp4")
        b = placeholder("CloudStorage/Dropbox", "b.mp4")
        with cloud_fetch_budget():
            self._timed_out_after(a)
        assert RUN_CLOUD_BUDGET.get() is None
        with cloud_fetch_budget():
            assert self._timed_out_after(b) >= self.LONG * 0.9

    def test_the_trip_is_logged_once_per_provider(self, stalled, caplog) -> None:
        import logging

        from bristlenose.utils.fs import cloud_fetch_budget

        placeholder, _started = stalled
        a = placeholder("CloudStorage/Dropbox", "a.mp4")
        b = placeholder("CloudStorage/Dropbox", "b.mp4")
        with caplog.at_level(logging.WARNING, logger="bristlenose.utils.fs"):
            with cloud_fetch_budget():
                self._timed_out_after(a)
                self._timed_out_after(b)
        trips = [r for r in caplog.records if "cloud_fetch_budget_tripped" in r.getMessage()]
        assert len(trips) == 1
        assert "Dropbox" in trips[0].getMessage()


class TestRunEntryPointsSetTheBudget:
    """`run` and `transcribe` each read the study's recordings under one budget."""

    @pytest.mark.parametrize("method", ["run", "run_transcription_only"])
    def test_ingest_runs_inside_a_budget(self, method: str, tmp_path: Path) -> None:
        import asyncio
        from unittest.mock import MagicMock, patch

        from bristlenose.pipeline import Pipeline
        from bristlenose.utils.fs import RUN_CLOUD_BUDGET, CloudFetchBudget

        seen: list[object] = []

        class StopRunError(Exception):
            pass

        def _ingest(*_a, **_kw):
            seen.append(RUN_CLOUD_BUDGET.get())
            raise StopRunError

        settings = MagicMock()
        settings.project_name = "budget"
        settings.write_intermediate = False
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        pipeline = Pipeline(settings)
        with patch("bristlenose.stages.s01_ingest.ingest", _ingest):
            with pytest.raises(StopRunError):
                asyncio.run(getattr(pipeline, method)(input_dir, tmp_path / "out"))
        assert len(seen) == 1 and isinstance(seen[0], CloudFetchBudget)
        assert RUN_CLOUD_BUDGET.get() is None
