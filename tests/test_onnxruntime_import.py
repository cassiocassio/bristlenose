"""onnxruntime's import-time warnings go to the log, not the terminal.

onnxruntime 1.30 probes for GPUs while its module initialises and writes each
failure to fd 2 from C++ ("GPU device discovery failed … Permission denied"
under the strict snap). ``utils/onnxruntime_import.py`` captures fd 2 for that
one import. These tests use ``capfd`` rather than ``capsys`` because the write
being caught is below Python's ``sys.stderr``, which is why the bug existed.
The fake module stands in for onnxruntime, so the mechanism is tested on every
platform; the real thing is checked by the snap workflow's strict-install step.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import pytest

from bristlenose.utils import onnxruntime_import as ort_import

_LOGGER = "bristlenose.utils.onnxruntime_import"


def _fake_module(tmp_path: Path, monkeypatch, name: str, body: str) -> str:
    (tmp_path / f"{name}.py").write_text(body, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, name, raising=False)
    return name


# Both lines are written to fd 2 directly, as onnxruntime's std::cerr does. A
# sys.stderr.write here would prove nothing: under capfd pytest points
# sys.stderr away from fd 2.
_NOISY = """
import os
os.write(2, b"\\x1b[0;93m[W:onnxruntime:Default, device_discovery.cc:1 X] GPU device discovery failed\\x1b[m\\n")
os.write(2, b"\\n[W:onnxruntime:Default, device_discovery.cc:2 Y] Skipping pci_bus_id\\n")
"""


def test_the_imports_stderr_goes_to_the_log_not_the_terminal(
        tmp_path, monkeypatch, capfd, caplog) -> None:
    name = _fake_module(tmp_path, monkeypatch, "bn_fake_ort_noisy", _NOISY)
    caplog.set_level(logging.INFO, logger=_LOGGER)

    module = ort_import._import_quietly(name)

    assert capfd.readouterr().err == ""
    assert module is sys.modules[name]
    messages = [r.getMessage() for r in caplog.records
                if r.name == _LOGGER and r.levelno == logging.INFO]
    assert len(messages) == 2
    assert messages[0].endswith("GPU device discovery failed")
    assert "\x1b" not in messages[0]
    assert messages[1].endswith("Skipping pci_bus_id")


def test_fd_2_is_restored_after_the_import(tmp_path, monkeypatch, capfd) -> None:
    name = _fake_module(tmp_path, monkeypatch, "bn_fake_ort_restore", _NOISY)

    ort_import._import_quietly(name)
    os.write(2, b"after\n")

    assert capfd.readouterr().err == "after\n"


def test_an_import_error_still_raises_with_fd_2_restored(
        tmp_path, monkeypatch, capfd, caplog) -> None:
    name = _fake_module(tmp_path, monkeypatch, "bn_fake_ort_broken",
                        _NOISY + "raise ImportError('no dylib')\n")
    caplog.set_level(logging.INFO, logger=_LOGGER)

    with pytest.raises(ImportError, match="no dylib"):
        ort_import._import_quietly(name)
    os.write(2, b"after\n")

    assert capfd.readouterr().err == "after\n"
    assert any("GPU device discovery failed" in r.getMessage()
               for r in caplog.records if r.name == _LOGGER)


def test_a_module_already_imported_touches_nothing(monkeypatch, caplog) -> None:
    held = types.ModuleType("bn_fake_ort_held")
    monkeypatch.setitem(sys.modules, "bn_fake_ort_held", held)

    def _no_dup(*_a):
        raise AssertionError("fd 2 touched for a module already imported")

    # The helper's own `os`, not the real one: pytest's capture needs dup2.
    monkeypatch.setattr(ort_import, "os", types.SimpleNamespace(dup=_no_dup, dup2=_no_dup))
    caplog.set_level(logging.INFO, logger=_LOGGER)

    assert ort_import._import_quietly("bn_fake_ort_held") is held
    assert [r for r in caplog.records if r.name == _LOGGER] == []


def test_without_a_real_fd_2_the_import_is_plain(tmp_path, monkeypatch) -> None:
    name = _fake_module(tmp_path, monkeypatch, "bn_fake_ort_nofd", "VALUE = 1\n")

    def _no_fd(_fd):
        raise OSError("bad file descriptor")

    monkeypatch.setattr(ort_import, "os", types.SimpleNamespace(dup=_no_fd))

    assert ort_import._import_quietly(name).VALUE == 1


def test_without_a_temp_dir_the_import_is_plain(tmp_path, monkeypatch) -> None:
    name = _fake_module(tmp_path, monkeypatch, "bn_fake_ort_notmp", "VALUE = 1\n")

    def _no_tmp(*_a, **_kw):
        raise OSError("no space left on device")

    monkeypatch.setattr(tempfile, "TemporaryFile", _no_tmp)

    assert ort_import._import_quietly(name).VALUE == 1


def test_importing_bristlenose_sets_ort_logging_level() -> None:
    # A subprocess, so a developer's own ORT_LOGGING_LEVEL cannot answer for it.
    env = {k: v for k, v in os.environ.items() if k != "ORT_LOGGING_LEVEL"}
    out = subprocess.run(
        [sys.executable, "-c",
         "import os, bristlenose; print(os.environ['ORT_LOGGING_LEVEL'])"],
        env=env, capture_output=True, text=True, check=True, timeout=60)

    assert out.stdout.strip() == "3"


# ── The callers go through the helper ────────────────────────────────────────


class _Spy:
    def __init__(self, returns, order: list[str] | None = None) -> None:
        self.returns = returns
        self.calls = 0
        self.order = order

    def __call__(self):
        self.calls += 1
        if self.order is not None:
            self.order.append("ort")
        return self.returns


def test_the_voice_front_end_imports_through_the_helper(monkeypatch) -> None:
    from bristlenose.stages import s05b_voice as voice
    from tests.test_speaker_voice import _TITANET_META, _FakeSession

    fake_ort = types.SimpleNamespace(
        SessionOptions=types.SimpleNamespace,
        InferenceSession=lambda *a, **kw: _FakeSession(dict(_TITANET_META)),
    )
    spy = _Spy(fake_ort)
    monkeypatch.setattr(ort_import, "import_onnxruntime", spy)

    voice._TitaNet("m.onnx", threads=1)

    assert spy.calls == 1


def test_the_self_test_imports_through_the_helper(monkeypatch) -> None:
    onnxruntime = pytest.importorskip("onnxruntime")
    pytest.importorskip("kaldi_native_fbank")
    from bristlenose.doctor import CheckStatus, check_bundle_voice
    from bristlenose.stages import s05b_voice as voice

    monkeypatch.setattr(voice, "voice_runtime_available", lambda: True)
    spy = _Spy(onnxruntime)
    monkeypatch.setattr(ort_import, "import_onnxruntime", spy)

    assert check_bundle_voice().status == CheckStatus.OK
    assert spy.calls == 1


def test_the_self_tests_session_sets_its_thread_counts(monkeypatch) -> None:
    """A default pool pins its threads; the strict snap refuses, on stderr."""
    onnxruntime = pytest.importorskip("onnxruntime")
    pytest.importorskip("kaldi_native_fbank")
    from bristlenose.doctor import CheckStatus, check_bundle_voice
    from bristlenose.stages import s05b_voice as voice

    monkeypatch.setattr(voice, "voice_runtime_available", lambda: True)
    seen = []
    real = onnxruntime.InferenceSession

    def _session(model, sess_options=None, **kw):
        seen.append(sess_options)
        return real(model, sess_options, **kw)

    monkeypatch.setattr(onnxruntime, "InferenceSession", _session)

    assert check_bundle_voice().status == CheckStatus.OK
    (opts,) = seen
    assert (opts.intra_op_num_threads, opts.inter_op_num_threads) == (1, 1)


def test_faster_whisper_is_set_up_after_the_helper_runs(monkeypatch) -> None:
    from bristlenose.stages import s05_transcribe

    order: list[str] = []

    class _Model:
        def __init__(self, *a, **kw) -> None:
            order.append("model")

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = _Model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    monkeypatch.setattr(ort_import, "import_onnxruntime", _Spy(None, order))
    monkeypatch.delenv("BRISTLENOSE_WHISPER_MODEL_DIR", raising=False)
    settings = types.SimpleNamespace(whisper_model="tiny", whisper_compute_type="int8")
    hw = types.SimpleNamespace(cuda_available=False)

    s05_transcribe._init_faster_whisper_backend(settings, hw)

    assert order == ["ort", "model"]
