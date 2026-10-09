"""Every GitHub Actions job declares a ``timeout-minutes``.

GitHub's default is 360 minutes, so a hung job without one holds a runner —
or a release — for six hours. Jobs that are ``uses:`` calls to a reusable
workflow are exempt: they cannot carry ``timeout-minutes``, and the jobs
inside the called workflow are checked in their own file.
"""

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _jobs_without_timeout() -> list[str]:
    missing = []
    files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    for path in files:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, job in (doc.get("jobs") or {}).items():
            if "uses" in job:
                continue
            if "timeout-minutes" not in job:
                missing.append(f"{path.name}: {name}")
    return missing


def test_workflows_found():
    assert list(WORKFLOWS.glob("*.yml")), f"no workflows under {WORKFLOWS}"


def test_every_job_declares_timeout_minutes():
    missing = _jobs_without_timeout()
    assert not missing, (
        f"{len(missing)} job(s) without timeout-minutes (GitHub's default is 360):\n  "
        + "\n  ".join(missing)
    )
