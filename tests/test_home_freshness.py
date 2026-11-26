"""The home page's freshness rules (scripts/home-freshness.js), run by node against one case table.

One copy of the rule lives in JS because the page must re-evaluate it from the clock; this test is
the only place Python meets it. Cases: tests/fixtures/home-freshness-cases.json. See
docs/private/design-home-dashboard.md section 2.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "home_freshness_runner.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@needs_node
def test_every_case_in_the_table_passes():
    r = subprocess.run(["node", str(RUNNER)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 failed" in r.stdout, r.stdout
