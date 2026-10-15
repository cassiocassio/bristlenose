"""The quarterly Whisper size check can fail.

``scripts/check-whisper-sizes.py`` needs the network, so it never runs in CI;
this pins the part that decides, so a green run at review time means "the table
is current" and not "the comparison cannot say otherwise".
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-whisper-sizes.py"
_spec = importlib.util.spec_from_file_location("check_whisper_sizes", _SCRIPT)
assert _spec is not None and _spec.loader is not None
check = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check  # @dataclass looks its module up there
_spec.loader.exec_module(check)


def test_rounding_is_not_drift():
    assert check.compare({"a/b": 1614}, {"a/b": 1615}) == []


def test_a_resized_repo_is_named_with_its_new_size():
    drifts = check.compare({"a/b": 1614}, {"a/b": 3091})
    assert [d.describe() for d in drifts] == ["a/b: table 1614 MB, Hub 3091 MB — set it to 3091"]


def test_a_repo_gone_from_the_hub_is_drift():
    drifts = check.compare({"a/b": 1614}, {"a/b": None})
    assert drifts and "not on the Hub" in drifts[0].describe()


def test_every_table_repo_is_asked():
    from bristlenose.preflight.whisper import _DOWNLOAD_MB

    # A repo the fetch skipped reads as gone, so a short Hub answer cannot pass.
    assert len(check.compare(_DOWNLOAD_MB, {})) == len(_DOWNLOAD_MB)
