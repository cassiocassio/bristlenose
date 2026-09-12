"""Drive the real matrix runner against a FAKE `bristlenose`, and prove it goes RED.

`test_acceptance_invariants.py` tests the predicates. A cloud run tests the
providers. Neither tests the thing in between — the runner — and that is where
both 12 Sep 2026 defects lived: a cell reusing its output directory, and a
configured provider failing while the verdict said green.

Proving that needed keys and spend, so it was never done, so the matrix went
**two months** reporting PASS on runs that never happened. This file removes the
excuse: a fake executable reproduces every shape — healthy, resumed, hard-failed,
late-failed — for nothing, offline, in milliseconds, and can run in CI where the
cloud cells never can.

**The control matters as much as the failures.** A harness that only asserts red
passes by being permanently red, which is the same class of defect as one that
only asserts green. `test_healthy_provider_is_green` is the other half, and every
scenario asserts the fake was actually invoked — a runner that silently skipped
the subprocess would otherwise satisfy most of the assertions below.
"""

from __future__ import annotations

import json
import shutil
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "acceptance"))

import run_matrix  # noqa: E402
from invariants import CellOutcome  # noqa: E402
from run_matrix import (  # noqa: E402
    Cell,
    Matrix,
    _run_provider_cell,
    validate_output_dir,
)

_SMOKE_OUTPUT = (
    Path(__file__).resolve().parent
    / "fixtures" / "smoke-test" / "input" / "bristlenose-output"
)

# What a cell that produced a real, complete report looks like. Copying the
# committed smoke fixture rather than hand-rolling one keeps the "healthy" arm
# honest: it is the same artefact `validate:smoke` already vouches for, so a
# change to the invariants moves this file's control with it.
_MODES = {
    # (writes a valid output dir?, exit code)
    "healthy": (True, 0),
    "late_failure": (True, 2),   # produced a report, then exited non-zero
    "hard_failure": (False, 2),  # died before writing anything — the 4 Sep shape
    "silent_resume": (False, 0),  # wrote nothing and claimed success — the 7 Jul shape
}


def _fake_bristlenose(tmp_path: Path, mode: str) -> str:
    """A stand-in executable that reproduces one real failure shape.

    Records its argv to `invoked.json` so every test can assert the runner
    actually shelled out. Without that, a runner that quietly stopped invoking
    the subprocess would still satisfy most assertions here.
    """
    writes_output, exit_code = _MODES[mode]
    script = tmp_path / "fake-bristlenose"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, shutil, sys\n"
        "from pathlib import Path\n"
        f"Path({str(tmp_path / 'invoked.json')!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "argv = sys.argv[1:]\n"
        "out = Path(argv[argv.index('--output') + 1]) if '--output' in argv else None\n"
        f"if {writes_output!r} and out is not None:\n"
        f"    shutil.copytree({str(_SMOKE_OUTPUT)!r}, out, dirs_exist_ok=True)\n"
        f"sys.exit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


@pytest.fixture
def cell() -> Cell:
    return Cell("run:openai", "openai", "BRISTLENOSE_OPENAI_API_KEY", "run")


def _run(monkeypatch, tmp_path: Path, mode: str, cell: Cell):
    monkeypatch.setattr(run_matrix, "bristlenose_exe", lambda: _fake_bristlenose(tmp_path, mode))
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    result = _run_provider_cell(cell, tmp_path / "input", artifacts)
    return result, artifacts


def _argv(tmp_path: Path) -> list[str]:
    marker = tmp_path / "invoked.json"
    assert marker.exists(), "the runner never shelled out — every assertion below is vacuous"
    return json.loads(marker.read_text())


# ---------------------------------------------------------------------------
# The control: the matrix must still be able to say yes.
# ---------------------------------------------------------------------------


def test_healthy_provider_is_green(monkeypatch, tmp_path: Path, cell: Cell) -> None:
    result, _ = _run(monkeypatch, tmp_path, "healthy", cell)
    assert result.outcome is CellOutcome.PASS
    assert result.is_green
    argv = _argv(tmp_path)
    # The invocation contract, pinned cheaply while we are here: the provider is
    # forced rather than inherited from the user's current one, and --no-serve
    # keeps the cell from blocking on a dev server it will never visit.
    assert argv[0] == "run"
    assert "--llm" in argv and argv[argv.index("--llm") + 1] == "openai"
    assert "--no-serve" in argv


# ---------------------------------------------------------------------------
# The two defects, reproduced.
# ---------------------------------------------------------------------------


def test_hard_failure_is_not_green(monkeypatch, tmp_path: Path, cell: Cell) -> None:
    """The 4 Sep shape: ChatGPT exited 2 on every invocation, having written
    nothing, and the matrix printed `GREEN: all 4 cells green`."""
    result, _ = _run(monkeypatch, tmp_path, "hard_failure", cell)
    _argv(tmp_path)
    assert not result.is_green, "a provider that could not start a run reported green"
    assert result.outcome is CellOutcome.FAIL_BLOCKING


def test_late_failure_is_reported_expected_but_still_not_green(
    monkeypatch, tmp_path: Path, cell: Cell
) -> None:
    """A report was produced and the process still exited non-zero.

    This is the cell that F7 calls `FAIL_EXPECTED` — the rate-limited-key class.
    Both halves matter: the outcome keeps its own name, so a throttle does not
    read as a breach, and it no longer counts toward a green run.
    """
    result, _ = _run(monkeypatch, tmp_path, "late_failure", cell)
    _argv(tmp_path)
    assert result.outcome is CellOutcome.FAIL_EXPECTED
    assert not result.is_green


def test_a_stale_directory_cannot_carry_a_cell(
    monkeypatch, tmp_path: Path, cell: Cell
) -> None:
    """The 7 Jul shape, and the reason it survived two months.

    A previous run's complete output is sitting in the cell's directory. The
    subprocess runs, writes nothing and exits 0 — which is exactly what
    `bristlenose run` does when it resumes a finished manifest. Before the wipe,
    the invariants were then applied to *last time's* report and passed.
    """
    artifacts = tmp_path / "artifacts"
    stale = artifacts / "run_openai"
    shutil.copytree(_SMOKE_OUTPUT, stale)

    # The counterfactual, asserted rather than described: that stale content is
    # a valid report and DOES satisfy every invariant. This is what the matrix
    # was reporting PASS on.
    assert validate_output_dir("stale", stale, quote_floor=1).outcome is CellOutcome.PASS

    monkeypatch.setattr(
        run_matrix, "bristlenose_exe", lambda: _fake_bristlenose(tmp_path, "silent_resume")
    )
    result = _run_provider_cell(cell, tmp_path / "input", artifacts)

    _argv(tmp_path)
    assert not result.is_green, (
        "the cell passed off a previous run's report — prepare_cell_dir did not wipe"
    )


# ---------------------------------------------------------------------------
# Composition: one failing cell must redden the whole run.
# ---------------------------------------------------------------------------


def test_one_failing_cell_reddens_the_verdict(monkeypatch, tmp_path: Path, cell: Cell) -> None:
    """Cell-level red is necessary but not sufficient — the exit code is what a
    scheduled run is judged by, and a runner could still sum four cells into a
    cheerful total."""
    m = Matrix()
    for cid, mode in (("run:anthropic", "healthy"), ("run:openai", "late_failure")):
        m.expected.append(cid)
        sub = tmp_path / cid.replace(":", "_")
        sub.mkdir()
        result, _ = _run(monkeypatch, sub, mode, Cell(cid, cid.split(":")[1], None, "run"))
        m.record(result)

    ok, message = m.verdict()
    assert not ok
    assert "run:openai" in message
    assert "run:anthropic" not in message, "a passing cell was named as a failure"


def test_all_green_still_says_so(monkeypatch, tmp_path: Path, cell: Cell) -> None:
    """The other half of the control, at the verdict level."""
    m = Matrix()
    m.expected.append("run:anthropic")
    result, _ = _run(monkeypatch, tmp_path, "healthy", Cell("run:anthropic", "anthropic", None, "run"))
    m.record(result)

    ok, message = m.verdict()
    assert ok, message
    assert "green" in message.lower()


def test_an_undeclared_skip_is_still_the_loudest_state(tmp_path: Path) -> None:
    """Pre-existing guard, re-pinned here because the synthetic path is now the
    cheapest place to break it: a cell promised in the manifest that produced no
    result at all outranks every other failure."""
    m = Matrix()
    m.expected.extend(["run:anthropic", "run:openai"])
    m.record(
        validate_output_dir("run:anthropic", _SMOKE_OUTPUT, quote_floor=1)
    )
    ok, message = m.verdict()
    assert not ok
    assert "UNDECLARED SKIP" in message
    assert "run:openai" in message
