"""Run the paired self-tests of the shell gates, so a gate that cannot fail is noticed.

Each ``test-check-<gate>.sh`` / ``.py`` drives its gate red on a violating fixture and shows an intact
fixture passes (``docs/testing/gaps.md`` G8: "is it passing" and "can it fail" are different
questions). They exist as scripts, but a script nothing calls proves nothing, so this runs them
with the rest of the suite. Adding a gate with a paired self-test means adding its name here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

_SELFTESTS = [
    "scripts/test-check-tracked-vs-gitignore.sh",
    "scripts/test-check-locales.py",
    "desktop/scripts/test-check-logging-hygiene.sh",
    "desktop/scripts/test-check-menu-routing.sh",
    "desktop/scripts/test-check-appearance-seam.sh",
    "desktop/scripts/test-check-window-surfaces.sh",
    "desktop/scripts/test-check-mcpb.sh",
]

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="bash gates; Windows CI has no bash fixtures")


@pytest.mark.parametrize("script", _SELFTESTS)
def test_the_gate_selftest_passes(script: str) -> None:
    path = _ROOT / script
    assert path.is_file(), f"{script} is listed here but does not exist"
    runner = [sys.executable, str(path)] if script.endswith(".py") else ["bash", str(path)]
    result = subprocess.run(
        runner, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"
    if script.endswith(".sh"):  # the shell harnesses end with "N passed, 0 failed"
        assert "0 failed" in result.stdout, result.stdout


def test_every_paired_selftest_on_disk_is_run_here() -> None:
    """A new ``test-check-*.sh`` that nobody lists would be exactly the uncalled gate this prevents."""
    on_disk = {
        str(p.relative_to(_ROOT))
        for d in ("scripts", "desktop/scripts")
        for p in [*(_ROOT / d).glob("test-check-*.sh"), *(_ROOT / d).glob("test-check-*.py")]
    }
    # Selftests that need a Mac, a signing identity or a built artefact are run by their own caller.
    elsewhere = {
        "desktop/scripts/test-check-pkg-shippable.sh",  # build-all.sh
        "scripts/test-check-doctor-install.sh",  # install-test.yml
        "scripts/test-check-ratchet.py",  # ratchet-tighten.yml, before it measures anything
    }
    assert on_disk - elsewhere == set(_SELFTESTS), sorted(on_disk - elsewhere ^ set(_SELFTESTS))
