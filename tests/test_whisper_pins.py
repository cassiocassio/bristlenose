"""The pinned Whisper model: fetched at one revision, two files, hash-checked.

The Python pin (``bristlenose/whisper_pins.py``) and the Mac app's Swift manifest must agree;
the parity test reads the Swift source.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.utils.package_install import PackageInstallError, ensure_hf_model
from bristlenose.whisper_pins import PINNED_MODELS

REPO = "mlx-community/whisper-large-v3-turbo"
SWIFT = (
    Path(__file__).resolve().parent.parent
    / "desktop/Bristlenose/Bristlenose/WhisperPackVerifier.swift"
)


def test_swift_manifest_is_the_same_pin() -> None:
    text = SWIFT.read_text(encoding="utf-8")
    pin = PINNED_MODELS[REPO]
    assert pin.revision in text  # the doc comment names the revision it pins
    block = text[text.index("static let largeV3Turbo"):]
    found = re.findall(
        r'File\(name: "([^"]+)", bytes: ([\d_]+),\s*sha256: "([0-9a-f]{64})"\)', block
    )
    swift = [(n, int(b.replace("_", "")), h) for n, b, h in found]
    assert swift == [(f.name, f.bytes, f.sha256) for f in pin.files]


def _snapshot(tmp_path: Path, payload: dict[str, bytes]) -> Path:
    snap = tmp_path / "models--x--y" / "snapshots" / PINNED_MODELS[REPO].revision
    snap.mkdir(parents=True)
    for name, data in payload.items():
        (snap / name).write_bytes(data)
    return snap


def _fake_pin(monkeypatch, files: dict[str, bytes]):
    from bristlenose import whisper_pins as wp

    pin = wp.PinnedModel(
        repo_id=REPO,
        revision=PINNED_MODELS[REPO].revision,
        files=tuple(
            wp.PinnedFile(n, len(d), hashlib.sha256(d).hexdigest()) for n, d in files.items()
        ),
    )
    monkeypatch.setitem(wp.PINNED_MODELS, REPO, pin)
    return pin


def test_pinned_fetch_names_the_revision_and_only_the_two_files(monkeypatch) -> None:
    fake = MagicMock()
    fake.snapshot_download.return_value = "/nowhere"
    pin = PINNED_MODELS[REPO]
    with patch.dict(sys.modules, {"huggingface_hub": fake}), patch(
        "bristlenose.utils.package_install._verify_pinned_snapshot"
    ):
        ensure_hf_model(REPO)
    kwargs = fake.snapshot_download.call_args.kwargs
    assert kwargs["revision"] == pin.revision
    assert kwargs["allow_patterns"] == ["config.json", "weights.safetensors"]


def test_other_models_are_fetched_as_before() -> None:
    fake = MagicMock()
    fake.snapshot_download.return_value = "/nowhere"
    with patch.dict(sys.modules, {"huggingface_hub": fake}):
        ensure_hf_model("mobiuslabsgmbh/faster-whisper-large-v3-turbo")
    kwargs = fake.snapshot_download.call_args.kwargs
    assert "revision" not in kwargs and "allow_patterns" not in kwargs


def test_good_bytes_pass_and_main_points_at_the_pin(tmp_path, monkeypatch) -> None:
    files = {"config.json": b"{}", "weights.safetensors": b"w" * 50}
    pin = _fake_pin(monkeypatch, files)
    snap = _snapshot(tmp_path, files)
    fake = MagicMock()
    fake.snapshot_download.return_value = str(snap)
    with patch.dict(sys.modules, {"huggingface_hub": fake}):
        assert ensure_hf_model(REPO) == str(snap)
    ref = snap.parent.parent / "refs" / "main"
    assert ref.read_text(encoding="utf-8") == pin.revision


@pytest.mark.parametrize("what", ["hash", "size", "missing"])
def test_bad_bytes_are_refused_and_removed(tmp_path, monkeypatch, what) -> None:
    files = {"config.json": b"{}", "weights.safetensors": b"w" * 50}
    _fake_pin(monkeypatch, files)
    served = dict(files)
    if what == "hash":
        served["weights.safetensors"] = b"x" * 50  # same size, other bytes
    elif what == "size":
        served["weights.safetensors"] = b"w" * 49
    else:
        del served["weights.safetensors"]
    snap = _snapshot(tmp_path, served)
    fake = MagicMock()
    fake.snapshot_download.return_value = str(snap)
    with patch.dict(sys.modules, {"huggingface_hub": fake}):
        with pytest.raises(PackageInstallError, match="weights.safetensors"):
            ensure_hf_model(REPO)
    assert not (snap / "weights.safetensors").exists()
    assert not (snap.parent.parent / "refs" / "main").exists()
