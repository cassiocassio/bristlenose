"""The home page's freshness rules (scripts/home-freshness.js), run by node against one case table.

One copy of the rule lives in JS because the page must re-evaluate it from the clock; this test is
the only place Python meets it. Cases: tests/fixtures/home-freshness-cases.json. See
docs/private/design-home-dashboard.md section 2.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "home_freshness_runner.js"
CASES = ROOT / "tests" / "fixtures" / "home-freshness-cases.json"
JS = ROOT / "scripts" / "home-freshness.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@needs_node
def test_every_case_in_the_table_passes():
    r = subprocess.run(["node", str(RUNNER)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 failed" in r.stdout, r.stdout


def test_the_table_covers_every_failure_that_must_not_read_as_fresh():
    """A table that quietly loses a row stops guarding it, and the failures that matter are the
    quiet ones: each of these would be `fresh` in a careless implementation."""
    names = {c["name"] for c in json.loads(CASES.read_text(encoding="utf-8"))["freshness"]}
    for must in ("missing as_of is unknown, not fresh", "non-numeric as_of is unknown", "NaN as_of is unknown",
                 "ten minutes in the future is unknown", "missing age limit is unknown",
                 "zero age limit is unknown", "no data beats a fresh timestamp",
                 "source-old, not refreshable", "exactly at the limit is fresh"):
        assert must in names, must


def test_the_engine_has_no_dom_and_no_clock_of_its_own():
    src = JS.read_text(encoding="utf-8")
    for banned in ("document.", "innerHTML", "insertAdjacentHTML", "outerHTML", "Date.now", "new Date("):
        assert banned not in src, banned
