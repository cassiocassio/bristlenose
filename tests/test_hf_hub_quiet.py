"""huggingface_hub must not print its first-download chatter to a researcher.

On a fresh Windows install (9 Oct 2026) the first transcription printed, twice
each: a symlink warning advising Developer Mode or running as administrator,
"hf_xet is not installed ... pip install", and a server-sent X-HF-Warning asking
for an HF_TOKEN. ``bristlenose/__init__.py`` sets HF_HUB_VERBOSITY and
HF_HUB_DISABLE_SYMLINKS_WARNING before anything imports huggingface_hub. These
run in a subprocess, because huggingface_hub reads both once, at first import.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("huggingface_hub")

_PROBE = """
import sys
if sys.argv[1] == "bristlenose":
    import bristlenose  # noqa: F401
from huggingface_hub import constants
from huggingface_hub.utils import logging as hf_logging
# The logger the server-sent X-HF-Warning (and the hf_xet notice) goes through.
hf_logging.get_logger("huggingface_hub.utils._http").warning("PROBE-WARNING")
print("symlinks-quiet" if constants.HF_HUB_DISABLE_SYMLINKS_WARNING else "symlinks-loud")
"""


def _run(first_import: str, **extra: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items()
           if k not in ("HF_HUB_VERBOSITY", "HF_HUB_DISABLE_SYMLINKS_WARNING")}
    env.update(extra)
    return subprocess.run([sys.executable, "-c", _PROBE, first_import],
                          capture_output=True, text=True, env=env, timeout=120)


def test_importing_bristlenose_silences_huggingface_hub_warnings() -> None:
    r = _run("bristlenose")
    assert r.returncode == 0, r.stderr
    assert "PROBE-WARNING" not in r.stdout + r.stderr
    assert "symlinks-quiet" in r.stdout


def test_without_bristlenose_the_warning_prints() -> None:
    """The control: the probe can see the warning, so the test above can fail."""
    r = _run("plain")
    assert r.returncode == 0, r.stderr
    assert "PROBE-WARNING" in r.stdout + r.stderr
    assert "symlinks-loud" in r.stdout


def test_a_user_setting_still_wins() -> None:
    r = _run("bristlenose", HF_HUB_VERBOSITY="warning")
    assert "PROBE-WARNING" in r.stdout + r.stderr
