"""onnxruntime must not start its Microsoft telemetry uploader.

From 1.29 onnxruntime ships 1DS telemetry on macOS and Linux: a persistent
device id and an event queue under the user's home, uploaded to Microsoft, and
an uploader thread that aborts the process at exit. ``bristlenose/__init__.py``
sets ``ORT_DISABLE_TELEMETRY`` before anything imports onnxruntime. These tests
run a real session in a subprocess with a throwaway ``$HOME`` and look for the
queue on disk, so they fail if the opt-out stops working, not only if the line
is deleted.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

onnxruntime_version: str = pytest.importorskip("onnxruntime").__version__

_PROBE = """
import base64, sys
if sys.argv[1] == "bristlenose":
    import bristlenose  # noqa: F401
from bristlenose.doctor import _ORT_IDENTITY_MODEL
import onnxruntime
onnxruntime.InferenceSession(
    base64.b64decode(_ORT_IDENTITY_MODEL), providers=["CPUExecutionProvider"])
"""

# onnxruntime turns its own telemetry off when any of these is set, so on a CI
# runner the probe proved nothing either way: the session test passed with the
# opt-out deleted, and the control had to be skipped. Read from the strings in
# libonnxruntime 1.32.0 and checked one by one on 19 Nov 2026 (`CI` is too
# short for `strings` to show; setting it alone suppresses the queue). The
# probe runs without them, so both tests mean the same thing on CI as on a Mac.
_ORT_CI_MARKERS = (
    "CI", "TF_BUILD", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS",
    "JENKINS_URL", "CODEBUILD_BUILD_ID", "BUILDKITE", "TEAMCITY_VERSION",
    "APPVEYOR", "BITBUCKET_BUILD_NUMBER", "ORT_RUNNING_UNIT_TESTS",
)


def _run(tmp_path: Path, first_import: str) -> tuple[int, list[Path]]:
    home = tmp_path / first_import
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in ("ORT_DISABLE_TELEMETRY", "XDG_CACHE_HOME", *_ORT_CI_MARKERS)}
    env["HOME"] = str(home)
    # The probe imports bristlenose.doctor either way, so the control has to
    # get there without the package's opt-out: run it with the var forced off.
    if first_import == "control":
        env["ORT_DISABLE_TELEMETRY"] = "0"
    proc = subprocess.run([sys.executable, "-c", _PROBE, first_import],
                          env=env, check=False, timeout=120)
    return proc.returncode, list(home.rglob(".onnxruntime"))


def test_importing_bristlenose_sets_the_opt_out() -> None:
    import bristlenose  # noqa: F401

    assert os.environ.get("ORT_DISABLE_TELEMETRY") == "1"


def test_a_session_writes_no_telemetry_queue(tmp_path: Path) -> None:
    returncode, queue = _run(tmp_path, "bristlenose")
    assert returncode == 0
    assert queue == []


# The 1DS uploader exists only on macOS and Linux builds from 1.29.
_ORT_HAS_1DS = sys.platform != "win32" and tuple(
    int(part) for part in onnxruntime_version.split(".")[:2]) >= (1, 29)


def test_control_without_the_opt_out_does_write_one(tmp_path: Path) -> None:
    """Proves the test above can fail: with the opt-out off, the queue appears.

    The control runs the live uploader, which can abort Python at exit
    (std::system_error from recursive_mutex::lock, seen on macOS; see
    ``bristlenose/__init__.py``). A death by signal is therefore not a failure
    here: the queue on disk is the evidence. A Python error (positive exit
    code) still fails. On a CI runner this arm makes a real upload attempt to
    Microsoft, because the probe strips the CI variables that would suppress
    it; that is the price of the control meaning the same thing on CI.
    """
    if not _ORT_HAS_1DS:
        pytest.skip("this onnxruntime build carries no 1DS telemetry (Windows, or before 1.29)")
    returncode, queue = _run(tmp_path, "control")
    assert returncode <= 0, f"the control probe failed with exit code {returncode}"
    # Empty here with a telemetry build means onnxruntime suppressed itself,
    # most likely under a CI variable missing from _ORT_CI_MARKERS.
    assert queue, (
        f"onnxruntime {onnxruntime_version} wrote no telemetry queue with the opt-out off "
        f"(exit code {returncode}); is a suppressing variable missing from _ORT_CI_MARKERS?"
    )
