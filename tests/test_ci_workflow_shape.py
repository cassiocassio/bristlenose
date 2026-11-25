"""The shape of ci.yml that the test-speed work depends on.

`scripts/check-gate-policy.py` reads `continue-on-error` only, so it cannot
see a job's `needs:` or an `if:` that skips it. These assertions pin the
parts of the workflow whose change would silently cost coverage or time.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
PROJECT_CONF = ROOT / "scripts" / "project.conf"


def _ci() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def test_e2e_does_not_wait_for_the_test_matrix() -> None:
    """Waiting on `test` queued e2e behind a macOS cell's ~40 min runner wait.

    A subset check, not `"test" not in needs`, so a renamed or split matrix job
    (`test-linux`) can't slip back in unnoticed.
    """
    needs = _ci()["jobs"]["e2e"].get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    assert set(needs) <= {"frontend-lint-type-test"}, f"e2e waits for {needs}"


def test_the_push_gates_run_on_every_push() -> None:
    """e2e, the frontend gate (Vitest) and the package build: never conditional.

    Job level only: a step-level `if:` inside one of them is not checked here.
    """
    doc = _ci()
    triggers = doc.get("on", doc.get(True))  # PyYAML reads a bare `on:` key as True
    assert set(triggers["push"]) <= {"branches"}, "a push filter could skip whole pushes"
    for name in ("e2e", "frontend-lint-type-test", "package"):
        job = doc["jobs"][name]
        assert "if" not in job, f"{name} has an `if:` and could be skipped: {job['if']}"
        assert not job.get("continue-on-error"), f"{name} is soft"


def _triggers(doc: dict) -> dict:
    return doc.get("on", doc.get(True))  # PyYAML reads a bare `on:` key as True


def test_macos_cells_run_nightly_and_under_strict_only() -> None:
    """Off pushes since 25 Nov 2026; nightly and the release paths still run them.

    The strict half (macOS in the matrix behind the input, no continue-on-error)
    is the release preflight's to check: check-release-ready.sh's publish gate.
    This pins the schedule half, which nothing else reads.
    """
    doc = _ci()
    assert _triggers(doc).get("schedule"), "no nightly: macOS would run only on release night"
    oses = str(doc["jobs"]["test"]["strategy"]["matrix"]["os"])
    assert "github.event_name == 'schedule'" in oses and "macos-latest" in oses, oses


def test_the_test_matrix_is_never_soft() -> None:
    """Wherever a macOS cell runs now, it blocks; a soft matrix would hide it."""
    assert "continue-on-error" not in _ci()["jobs"]["test"]


def test_no_concurrency_group_can_cancel_a_run() -> None:
    """The release gate is a workflow_dispatch of this file; a shared group with
    cancel-in-progress could drop it (stress test of the plan, 25 Nov 2026)."""
    doc = _ci()
    groups = [doc.get("concurrency")] + [j.get("concurrency") for j in doc["jobs"].values()]
    for group in filter(None, groups):
        cancel = group.get("cancel-in-progress", False) if isinstance(group, dict) else False
        assert cancel is False, f"a concurrency group cancels in progress: {group}"


def test_the_strict_input_release_sh_sends_exists() -> None:
    """project.conf's WF_STRICT_INPUT must name a real workflow_dispatch input."""
    conf = PROJECT_CONF.read_text(encoding="utf-8")
    name = next(
        line.split("=", 1)[1].strip().strip('"')
        for line in conf.splitlines()
        if line.startswith("WF_STRICT_INPUT=")
    )
    inputs = _triggers(_ci())["workflow_dispatch"]["inputs"]
    assert name in inputs, f"release.sh dispatches {name}=true, but ci.yml has {list(inputs)}"
