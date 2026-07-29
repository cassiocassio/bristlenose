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
    real = os.stat

    def fake(path, *a, **kw):  # type: ignore[no-untyped-def]
        st = real(path, *a, **kw)
        return os.stat_result(
            tuple(st), {**getattr(st, "__dict__", {}), "st_flags": flags, "st_size": size}
        )

    monkeypatch.setattr(os, "stat", fake)


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
