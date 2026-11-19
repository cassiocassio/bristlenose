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

pytest.importorskip("onnxruntime")

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


def _run(tmp_path: Path, first_import: str) -> list[Path]:
    home = tmp_path / first_import
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in ("ORT_DISABLE_TELEMETRY", "XDG_CACHE_HOME", *_ORT_CI_MARKERS)}
    env["HOME"] = str(home)
    # The probe imports bristlenose.doctor either way, so the control has to
    # get there without the package's opt-out: run it with the var forced off.
    if first_import == "control":
        env["ORT_DISABLE_TELEMETRY"] = "0"
    subprocess.run([sys.executable, "-c", _PROBE, first_import],
                   env=env, check=True, timeout=120)
    return list(home.rglob(".onnxruntime"))


def test_importing_bristlenose_sets_the_opt_out() -> None:
    import bristlenose  # noqa: F401

    assert os.environ.get("ORT_DISABLE_TELEMETRY") == "1"


def test_a_session_writes_no_telemetry_queue(tmp_path: Path) -> None:
    assert _run(tmp_path, "bristlenose") == []


def test_control_without_the_opt_out_does_write_one(tmp_path: Path) -> None:
    """Proves the test above can fail: with the opt-out off, the queue appears."""
    if not _run(tmp_path, "control"):
        pytest.skip("this onnxruntime build carries no telemetry")
