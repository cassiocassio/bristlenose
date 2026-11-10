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
    "desktop/scripts/test-check-release-binary.sh",
    "desktop/scripts/test-check-deployment-floors.sh",
    "desktop/scripts/test-check-sidecar-appstore-strings.sh",
    "desktop/scripts/test-check-dmg-shippable.sh",
    "desktop/scripts/test-check-pkg-shippable.sh",
    "desktop/scripts/test-report-exit-status.sh",
]

# The gates are bash scripts, so there is nothing to run on Windows: the list is empty there rather
# than carrying a skip marker (the skip-site ratchet counts markers, and an empty parameter set reads
# as one skipped case in the summary without being a site).
_RUNNABLE = [] if sys.platform == "win32" else _SELFTESTS


@pytest.mark.parametrize("script", _RUNNABLE)
def test_the_gate_selftest_passes(script: str) -> None:
    path = _ROOT / script
    assert path.is_file(), f"{script} is listed here but does not exist"
    runner = [sys.executable, str(path)] if script.endswith(".py") else ["bash", str(path)]
    result = subprocess.run(
        runner, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"
    if script.endswith(".sh"):  # the shell harnesses end with "N passed, 0 failed", or say they skipped
        assert "0 failed" in result.stdout or "skipped" in result.stdout, result.stdout


def test_every_paired_selftest_on_disk_is_run_here() -> None:
    """A new ``test-check-*.sh`` that nobody lists would be exactly the uncalled gate this prevents."""
    on_disk = {
        str(p.relative_to(_ROOT))
        for d in ("scripts", "desktop/scripts")
        for p in [*(_ROOT / d).glob("test-check-*.sh"), *(_ROOT / d).glob("test-check-*.py")]
    }
    # Selftests run by a workflow instead, because they need what this suite does not have.
    # Outside this glob, and run by nothing automatically: desktop/scripts/test-ensure-sidecar.sh
    # and scripts/test-pre-push.sh (by hand, per their READMEs).
    elsewhere = {
        "scripts/test-check-doctor-install.sh",  # install-test.yml (needs a real pip install)
        # ratchet-tighten.yml, which runs only on manual dispatch: nothing runs this automatically.
        "scripts/test-check-ratchet.py",
    }
    unlisted = on_disk - elsewhere - set(_SELFTESTS)
    assert not unlisted, sorted(unlisted)
    assert all((_ROOT / s).is_file() for s in _SELFTESTS)
