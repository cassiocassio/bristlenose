"""The Mac app tells a researcher why the Whisper download failed, in three cases.

The app only sees the last lines the download job wrote to stderr, so Swift
(`WhisperFailureCause.classify`) reads Python's own wording. These tests pin the two halves
together from the Python side: every network failure the retry loop waits on is recognised by the
Swift pattern, the real "Disk full" refusal is, and every key the Swift enum shows exists in the
English locale (the other 20 are held by check-locales).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bristlenose.preflight import PreflightAbortedError
from bristlenose.preflight import whisper as w

_ROOT = Path(__file__).resolve().parent.parent
_SWIFT = (_ROOT / "desktop/Bristlenose/Bristlenose/WhisperDownloadModel.swift").read_text(encoding="utf-8")


def _swift_pattern(name: str) -> str:
    m = re.search(rf'static let {name} =\s*#"(.*?)"#', _SWIFT, re.S)
    assert m, f"{name} moved in WhisperDownloadModel.swift; update this test"
    return m.group(1)


def test_every_marker_the_retry_loop_waits_on_is_recognised_by_the_app() -> None:
    swift_network = re.compile(_swift_pattern("networkPattern"))
    missed = [m for m in w._NETWORK_FAILURE_MARKERS if not swift_network.search(m.lower())]
    assert not missed, f"the app would show no reason for a failure the job waits out: {missed}"


def test_the_real_disk_refusal_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(w, "_cache_volume_free_bytes", lambda: (700_000_000, Path("/cache")))
    with pytest.raises(PreflightAbortedError) as err:
        w.ensure_disk_room("mlx-community/whisper-large-v3-turbo")
    assert re.search(_swift_pattern("diskPattern"), str(err.value).lower())


def test_a_certificate_failure_is_caught_by_the_certificate_pattern_not_only_the_network_one() -> None:
    text = "ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed".lower()
    assert re.search(_swift_pattern("certificatePattern"), text)


def test_what_python_never_retries_is_not_called_a_network_failure_by_the_app() -> None:
    """A refused connection is a dead proxy or a firewall; the app says nothing rather than guess."""
    swift_network = re.compile(_swift_pattern("networkPattern"))
    assert not swift_network.search("connecterror: [errno 61] connection refused")


def test_every_key_the_app_can_show_exists_in_the_english_locale() -> None:
    keys = set(re.findall(r'"(desktop\.modelDownload\.cause\w+)"', _SWIFT))
    assert len(keys) == 3, keys
    en = json.loads((_ROOT / "bristlenose/locales/en/desktop.json").read_text(encoding="utf-8"))
    for key in keys:
        assert key.split(".", 2)[2] in en["modelDownload"], key
