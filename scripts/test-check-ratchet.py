#!/usr/bin/env python3
"""Prove --tighten does not destroy what it rewrites.

WHY THIS EXISTS

`--tighten` is about to be run by a workflow instead of by a person, so its
write path stops being something anyone reads before it lands. It had a silent
data-loss bug at the moment that changed: the entry was rebuilt from METRICS, so
every key living only in the JSON was dropped. `note` is such a key, and `note`
is where the argument for a number lives — the mypy entry's recorded why it is
set from CI and not from the dev Mac. Tightening it deleted that, with no error
and no diff anyone was going to open.

The other half is the reporting regression that made the staleness invisible:
for an `authority: ci` metric the check path printed the measurement alone, so
148 under a ceiling of 239 read exactly like 148 at a ceiling of 148.

DEVIATION FROM THE HOUSE PATTERN, DELIBERATE

`test-dep-drift.py` and `test-doc-surfaces.sh` mutate a tracked file and restore
it in a trap, because the gates they cover read fixed paths. This one does not
need to: `CEILINGS` and `METRICS` are module attributes, so every case runs
against a temp file and stub metrics. Nothing tracked is touched and no restore
can be missed — and mypy never runs, so the suite is instant.

Usage: .venv/bin/python scripts/test-check-ratchet.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cr", HERE / "check-ratchet.py")
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

FAILURES: list[str] = []


def check(label: str, cond, detail: str = "") -> None:
    """cond is a callable, so a missing key FAILS this case instead of killing the run.

    It killed the run on the first red pass: the pre-fix code writes no
    `measured` key, and asserting it eagerly raised KeyError three cases in, so
    the ten assertions after it were never reported. A suite that dies on the
    first defect can only ever tell you about one.
    """
    try:
        ok = bool(cond())
        why = detail
    except Exception as e:  # noqa: BLE001 — a raising assertion is a failing one
        ok, why = False, f"{type(e).__name__}: {e}"
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        FAILURES.append(f"{label}{': ' + why if why else ''}")


@contextlib.contextmanager
def env(**kv):
    """Set/clear env vars, restoring exactly — this runs IN CI, where CI is set."""
    old = {k: os.environ.get(k) for k in kv}
    for k, v in kv.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run(argv, ceilings, metrics, incoming=None, **envkv):
    """Drive main() against a temp ceilings file and stub metrics.

    `incoming` is written beside it and appended to argv, for --adopt.

    CI and GITHUB_ACTIONS are CLEARED unless a case names them, so every case
    declares the environment it means. Defaulting to inherit made the suite pass
    on a laptop and fail on a runner: "a CI-authority metric is skipped outside
    CI" ran with CI=true on GitHub, where the skip correctly does not happen.
    Its first real run caught it — which is the point, but the failing test was
    the one asserting the thing this repo already knows to write down.
    """
    envkv = {"CI": None, "GITHUB_ACTIONS": None, **envkv}
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "ratchet.json"
        path.write_text(json.dumps(ceilings, indent=2, sort_keys=True) + "\n")
        if incoming is not None:
            src = pathlib.Path(d) / "incoming.json"
            src.write_text(json.dumps(incoming, indent=2, sort_keys=True) + "\n")
            argv = [*argv, str(src)]
        old_c, old_m, old_argv = cr.CEILINGS, cr.METRICS, sys.argv
        cr.CEILINGS, cr.METRICS, sys.argv = path, metrics, ["check-ratchet.py", *argv]
        buf = io.StringIO()
        try:
            with env(**envkv), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = cr.main()
        finally:
            cr.CEILINGS, cr.METRICS, sys.argv = old_c, old_m, old_argv
        return code, buf.getvalue(), json.loads(path.read_text())


# One CI-owned metric and one ordinary one, both stubbed so nothing shells out.
def metrics(ci_now: int, plain_now: int) -> dict:
    return {
        "mypy_errors": {
            "measure": lambda: ci_now,
            "basis": "basis-from-code",
            "why": "why-from-code",
            "authority": "ci",
        },
        "pytest_slow_marked": {
            "measure": lambda: plain_now,
            "basis": "plain-basis",
            "why": "plain-why",
        },
    }


NOTE = "the argument for this number, written by a person"
BASE = {
    "mypy_errors": {"ceiling": 239, "basis": "stale", "why": "stale", "note": NOTE,
                    "authority": "ci"},
    "pytest_slow_marked": {"ceiling": 7, "basis": "stale", "why": "stale"},
}

print("--tighten preserves what the code does not own")
_, out, after = run(["--tighten"], BASE, metrics(148, 5), CI="1")
check("note survives a tighten", lambda: after["mypy_errors"].get("note") == NOTE,
      f"got {after['mypy_errors'].get('note')!r}")
check("ceiling followed the measurement down", lambda: after["mypy_errors"]["ceiling"] == 148)
check("code-owned fields are refreshed from METRICS",
      lambda: after["mypy_errors"]["basis"] == "basis-from-code")
check("provenance records who measured it",
      lambda: after["mypy_errors"]["measured"]["by"] == "ci", str(after["mypy_errors"].get("measured")))
check("an untouched entry keeps its shape",
      lambda: after["pytest_slow_marked"]["ceiling"] == 5)

print("\n--tighten refuses to raise, and refuses a local number for a CI metric")
_, out, after = run(["--tighten"], BASE, metrics(300, 99))
check("a risen plain metric does not raise its ceiling",
      lambda: after["pytest_slow_marked"]["ceiling"] == 7)
check("a CI-authority metric is skipped outside CI",
      lambda: after["mypy_errors"]["ceiling"] == 239 and "skipping mypy_errors" in out, out.strip())
check("skipping leaves the entry byte-identical", lambda: after["mypy_errors"] == BASE["mypy_errors"])

print("\nthe check path names the slack instead of swallowing it")
code, out, _ = run([], BASE, metrics(148, 7), CI=None, GITHUB_ACTIONS=None)
check("slack is reported locally for a CI-authority metric",
      lambda: "91 of slack" in out, out.strip())
check("and points at the route that actually works",
      lambda: "gh workflow run ratchet-tighten.yml" in out)
check("slack alone does not fail the gate", lambda: code == 0)

code, out, _ = run([], BASE, metrics(148, 7), CI="1", GITHUB_ACTIONS="true")
check("CI emits an annotation so it is visible on the run page",
      lambda: "::notice file=docs/testing/ratchet.json::" in out, out.strip())

code, out, _ = run([], BASE, metrics(148, 8), CI="1")
check("a risen metric still fails in CI", lambda: code == 1, out.strip())

print("\n--adopt installs a CI-measured ceiling and nothing else")
CI_STAMP = {"by": "ci", "on": "2026-09-04", "run": "https://example/runs/1"}
measured = {
    "mypy_errors": {"ceiling": 148, "measured": CI_STAMP, "note": "prose from the RUN",
                    "basis": "b", "why": "w", "authority": "ci"},
    "pytest_slow_marked": {"ceiling": 5, "measured": CI_STAMP, "basis": "b", "why": "w"},
}
code, out, after = run(["--adopt"], BASE, metrics(0, 0), incoming=measured)
check("a CI-stamped ceiling is adopted", lambda: after["mypy_errors"]["ceiling"] == 148)
check("the stamp comes with it", lambda: after["mypy_errors"]["measured"] == CI_STAMP)
check("local prose is NOT overwritten by the run's copy",
      lambda: after["mypy_errors"]["note"] == NOTE, str(after["mypy_errors"].get("note")))
check("adopt succeeds", lambda: code == 0, out.strip())

print("\n--adopt applies the same two refusals as --tighten")
unstamped = {"mypy_errors": {"ceiling": 148, "measured": {"by": "local", "on": "2026-09-04"}}}
code, out, after = run(["--adopt"], BASE, metrics(0, 0), incoming=unstamped)
check("a locally-measured number is refused for a CI-authority metric",
      lambda: code == 1 and after["mypy_errors"]["ceiling"] == 239, out.strip())
check("and says why", lambda: "REFUSED" in out and "CI is the authority" in out, out.strip())

nostamp = {"pytest_slow_marked": {"ceiling": 5}}
code, _, after = run(["--adopt"], BASE, metrics(0, 0), incoming=nostamp)
check("a metric CI does not own needs no stamp",
      lambda: code == 0 and after["pytest_slow_marked"]["ceiling"] == 5)

higher = {"mypy_errors": {"ceiling": 300, "measured": CI_STAMP},
          "pytest_slow_marked": {"ceiling": 99, "measured": CI_STAMP}}
code, _, after = run(["--adopt"], BASE, metrics(0, 0), incoming=higher)
check("adopt never raises a ceiling, whoever measured it",
      lambda: after["mypy_errors"]["ceiling"] == 239 and after["pytest_slow_marked"]["ceiling"] == 7)

code, out, after = run(["--adopt"], BASE, metrics(0, 0), incoming={})
check("an empty file adopts nothing and says so",
      lambda: code == 0 and "nothing to adopt" in out and after == BASE, out.strip())

print()
sys.stdout.flush()  # else the stderr summary lands above the lines it summarises
if FAILURES:
    print("FAILED:", file=sys.stderr)
    for f in FAILURES:
        print(f"  {f}", file=sys.stderr)
    sys.exit(1)
print("all ratchet write-path assertions hold")
