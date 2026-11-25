"""The shape of ci.yml that the test-speed work depends on.

`scripts/check-gate-policy.py` reads `continue-on-error` only, so it cannot
see a job's `needs:` or an `if:` that skips it. These assertions pin the
parts of the workflow whose change would silently cost coverage or time.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


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
