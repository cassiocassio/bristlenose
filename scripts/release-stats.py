#!/usr/bin/env python3
"""release-stats.py — what the release ledgers already know, made readable.

Every run under `.release/` records each step's attempts and outcomes, and each
failed attempt leaves a log. The data to answer "how often does this class
recur?" has been there since 0.28.0 — but answering it on 23 Sep 2026 meant
hand-writing a throwaway script and re-reading 25 logs, which is how a failure
class reaches its fifth occurrence before anyone counts it.

Read-only. Classifies through `verdict_failure_class` in release.sh, so there is
ONE taxonomy: the driver stamps it into the ledger at failure time, and this
re-derives it for runs that predate the stamp. A second copy here would drift
from the one that ships, and the drift would be invisible.
"""
from __future__ import annotations

import functools
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_CLASSIFY = 'RELEASE_LIB=1 . "$0" 2>/dev/null; verdict_failure_class "$1"'


def classify(log: Path) -> str:
    """Ask release.sh, so the taxonomy has exactly one definition."""
    try:
        st = log.stat()
    except OSError:
        st = None
    return _classify_cached(str(log), st.st_mtime_ns if st else 0, st.st_size if st else -1)


@functools.lru_cache(maxsize=512)
def _classify_cached(log: str, _mtime: int, _size: int) -> str:
    # keyed on (mtime, size) so the board's live server, which rebuilds the
    # history on every change, sources release.sh once per failed log, not per tick
    out = subprocess.run(
        ["bash", "-c", _CLASSIFY, str(ROOT / "scripts" / "release.sh"), log],
        capture_output=True, text=True,
    )
    return out.stdout.strip() or "unknown"


def _attempts(events: Path) -> tuple[int, list[tuple[str, str]]]:
    """(attempts, [(step, attempt)]) for the failures in one run's ledger."""
    tries, fails, last = 0, [], {}
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue           # a torn line is not a step outcome
        step, status, detail = e.get("step"), e.get("status"), e.get("detail") or ""
        if status == "running":
            if m := re.search(r"attempt (\d+)", detail):
                last[step] = m.group(1)
                tries += 1
        elif status == "fail":
            fails.append((step, last.get(step, "?")))
    return tries, fails


# ── history: every invocation of every release, for the board's History tab ──
#
# One record per `run started` line, across every `.release/*/` dir. A release
# is grouped by the ledger's own `run` field, not the dir name, so the stopped
# 0.31.3 attempts (kept under renamed dirs) are invocations of 0.31.3.
#
# An invocation's ENTRY is the first step it executed — resume skips completed
# steps silently, so a resumed run enters mid-line, and the chart has to show
# that rather than pretend every attempt starts at preflight. Its EXIT is one of:
#   fail      a step wrote `fail` (class from the ledger stamp, else release.sh)
#   skipped   the run reached `completed` over a skipped irreversible step
#   stopped   the ledger simply ends — killed, or stopped by hand
#   completed every step it ran is ok
# None of these are inferred from anything but the ledger.

STEP_ORDER = ["preflight", "inventory", "bump", "push-main", "strict-ci", "build-all",
              "build-dmg", "ci-green", "testflight", "dmg", "tag", "snap"]
IRREVERSIBLE = {"testflight", "dmg", "tag"}
CHANNEL_ORDER = ["pypi", "github", "homebrew", "testflight", "dmg", "snap", "copr", "website"]

# The paths whose commits change how a release runs. A commit to any of these
# between two invocations is a new version of the release machine.
MACHINE_PATHS = ["scripts/release.sh", "scripts/check-release-ready.sh", "desktop/scripts/upload-dmg.sh",
                 "desktop/scripts/upload-testflight.sh", "desktop/scripts/build-dmg.sh",
                 "desktop/scripts/build-all.sh", "desktop/scripts/build-sidecar.sh", ".pre-commit-config.yaml"]

# The changes worth naming on the chart, and what each was for. Hand-kept, from
# the commit bodies and docs/release-premortem.md; every other machine commit
# still appears, unnamed, in its gap's tooltip.
MACHINE_MILESTONES = {
    "cd43af8d": "bump step can succeed, and resuming it no longer bumps twice",
    "5439d6ac": "a consumed step table must not report done (incident 22)",
    "53a3d442": "the tag lands on the exact commit strict CI names",
    "40470bf4": "one negative ASC read is not proof of absence",
    "618bce20": "every credential gathered at the confirmation",
    "bf387715": "resume re-dispatches strict CI when HEAD moved (27)",
    "fad2aa95": "push-main re-pushes an unpublished HEAD; builds rerun when HEAD moved (29, 30)",
    "eaf9fb18": "preflight resolves the sidecar deps before the bump",
    "84b8a742": "one dependency resolve per release, in preflight (23)",
    "2be60bf2": "the CI gate can say “I don't know” (33, 34)",
    "98559b24": "each failure is named and classed when it happens",
    "e53d17e7": "release.sh holds the display awake (36)",
    "62a8c7dc": "a dropped .dmg upload keeps its partial (37)",
    "8cef6d06": "CI gate fails fast and finds its run by commit; main freezes during a run (38–40)",
    "c3d6b787": "preflight reads main's own CI (42); a stale board yields its port (43)",
}

# What stopped each invocation, where the release log or the premortem says so.
# Keyed "version#n", n counting invocations in ledger order. Absent → the chart
# shows the failure class alone; it never invents a cause.
CAUSES = {
    "0.28.0#1": ("the bump step could never succeed", None),
    "0.28.0#4": ("strict CI red on the tagged commit", None),
    "0.28.0#5": ("ssh ate the step table: \u201ccompleted\u201d with tag and snap never run", 22),
    "0.29.0#4": ("a re-run offered to re-upload a TestFlight build; ASC refused it as a duplicate", None),
    "0.30.0#1": ("preflight: uncommitted tree", None),
    "0.30.0#2": ("an unsigned test bundle in shared DerivedData", None),
    "0.30.0#3": ("the sidecar re-resolved 24 packages after the drift gate looked", 23),
    "0.30.0#4": ("a relative CODE_SIGN_ENTITLEMENTS broke the Settings package", 24),
    "0.30.0#5": ("a comment truncated the archive command", 25),
    "0.31.0#2": ("an Xcode signing race on the test bundle", None),
    "0.31.0#3": ("dependency drift mid-run", None),
    "0.31.0#4": ("stopped by hand: a fix committed between attempts was never pushed", 29),
    "0.31.0#5": ("stopped by hand: build-all was skipped over a .pkg from the previous commit", 30),
    "0.31.0#6": ("stopped by hand to rebuild at the moved HEAD", 30),
    "0.31.1#1": ("dependency drift mid-run", None),
    "0.31.1#2": ("a transient HTTP 503 killed the CI watch", 33),
    "0.31.2#2": ("dependency drift mid-run", None),
    "0.31.2#3": ("the CI gate failed silently: empty lookup, zero-byte log", 34),
    "0.31.2#4": ("tag refused: the tree was dirty", None),
    "0.31.3#1": ("skipped the whole irreversible block and still printed “every act is done”", 22),
    "0.31.3#2": ("stopped by hand: mypy over its ceiling", None),
    "0.32.0#1": ("PyAV 19 broke decoding; a gate never seen red", None),
    "0.32.0#2": ("helper tests pushed the skip ratchet over", None),
    "0.32.0#3": ("the .dmg gate refused the team app group the new helper needs", None),
    "0.32.0#4": ("fastapi published mid-run (dep drift)", None),
    "0.32.0#5": ("stopped by hand: two tests red on every CI cell", None),
    "0.32.0#6": ("filelock published mid-run (dep drift)", None),
    "0.33.0#1": ("the display slept; the Swift suite failed on a locked screen", 36),
    "0.34.0#1": ("strict CI: winget tests read the runner", 38),
    "0.34.0#2": ("stopped mid-step to pick up a CI fix", None),
    "0.34.0#4": ("the Swift test host exited once mid-suite", 41),
    "0.34.0#5": ("the host dropped rsync at 555 of 709 MB, and the partial was deleted", 37),
}

# Stops the release log records that no ledger can: they happened before
# `run started` was written.
UNLEDGERED = {
    "0.33.0": [("credential probes", "notary 403: Apple's licence agreement had lapsed", 35)],
}


def _load_bn_events(root: Path):
    p = root / "desktop" / "scripts" / "bn_events.py"
    if not p.is_file():
        p = ROOT / "desktop" / "scripts" / "bn_events.py"
    spec = importlib.util.spec_from_file_location("bn_events", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _final_verify(run_dirs: list[Path], root: Path) -> dict | None:
    """The last complete `release.sh verify` pass across a release's dirs, or None."""
    bn = _load_bn_events(root)
    passes: list[tuple[str, dict, int]] = []
    for d in run_dirs:
        p = d / "bn-events.log"
        if not p.is_file():
            continue
        events, _unparsed, _partial = bn.parse_stream(bn.read_sink_text(p))
        cur: dict | None = None
        count = 0
        for _no, kind, f in events:
            if kind == "verify" and f.get("status") == "start":
                cur = {"ts": f.get("ts", ""), "rows": {}}
            elif kind == "row" and f.get("src") == "verify" and cur is not None:
                cur["rows"][f.get("label", "")] = {"result": f.get("result", ""), "evidence": (f.get("evidence") or "")[:120]}
            elif kind == "verify" and f.get("status") == "done" and cur is not None:
                count += 1
                passes.append((cur["ts"], cur, count))
                cur = None
    if not passes:
        return None
    passes.sort(key=lambda t: t[0])
    # A channel is REACHED if any pass saw it ok: a later pass can read "bad" only
    # because the next release has since moved the channel on. `pass` is which
    # pass first saw it, so "needed three verifies" stays visible.
    rows: dict[str, dict] = {}
    for n, (_ts, p, _c) in enumerate(passes, 1):
        for c in CHANNEL_ORDER:
            r = p["rows"].get(c)
            if r is None:
                continue
            if c not in rows or (rows[c]["result"] != "ok" and r["result"] == "ok"):
                rows[c] = {**r, "pass": n}
    return {"ts": passes[-1][0], "passes": len(passes), "rows": {c: rows[c] for c in CHANNEL_ORDER if c in rows}}


def _machine_commits(root: Path, since: str) -> list[dict] | None:
    """Commits to the release machine since `since`, oldest first; None if git cannot answer."""
    try:
        out = subprocess.run(["git", "-C", str(root), "log", f"--since={since}", "--format=%h%x09%cI%x09%s",
                              "--", *MACHINE_PATHS], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        sha, ts, subject = parts
        named = next((v for k, v in MACHINE_MILESTONES.items() if sha.startswith(k) or k.startswith(sha)), None)
        rows.append({"sha": sha, "ts": ts, "subject": subject[:140], "milestone": named})
    rows.sort(key=lambda r: r["ts"])
    return rows


def _iso_utc(ts: str) -> str:
    """Normalise an ISO stamp with an offset to ...Z, so it sorts against ledger stamps."""
    from datetime import datetime, timezone
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ts


def _invocations(lines: list[dict], run_dirs: dict[str, Path]) -> list[dict]:
    invs: list[dict] = []
    cur: dict | None = None
    attempt: dict[str, str] = {}
    for e in lines:
        step, status, detail = e.get("step"), e.get("status"), e.get("detail") or ""
        if step == "run":
            if status == "started":
                cur = {"start": e.get("ts"), "end": e.get("ts"), "dir": e["_dir"], "steps": [], "exit": None}
                invs.append(cur)
            elif status == "completed" and cur is not None:
                cur["completed"] = True
                cur["end"] = e.get("ts")
            continue
        if cur is None:
            continue
        cur["end"] = e.get("ts") or cur["end"]
        if status == "running":
            if m := re.search(r"attempt (\d+)", detail):
                attempt[step] = m.group(1)
            if not cur["steps"] or cur["steps"][-1]["step"] != step:
                cur["steps"].append({"step": step, "status": "running", "start": e.get("ts")})
        elif status in ("ok", "fail", "skipped"):
            rec = cur["steps"][-1] if cur["steps"] and cur["steps"][-1]["step"] == step else None
            if rec is None:
                rec = {"step": step, "start": e.get("ts")}
                cur["steps"].append(rec)
            rec["status"] = status
            rec["end"] = e.get("ts")
            if status == "fail":
                m = re.search(r"class=([\w-]+)", detail)
                cls = m.group(1) if m else None
                if not cls or cls == "unknown":
                    log = run_dirs[e["_dir"]] / "logs" / f"{step}.{attempt.get(step, '?')}.log"
                    cls = classify(log) if log.is_file() else (cls or "no-log")
                rec["class"] = cls
                rec["attempt"] = attempt.get(step)
    return invs


def _exit(inv: dict) -> dict:
    ran = [s for s in inv["steps"] if s["status"] != "skipped"]
    fails = [s for s in inv["steps"] if s["status"] == "fail"]
    skipped_irrev = [s["step"] for s in inv["steps"] if s["status"] == "skipped" and s["step"] in IRREVERSIBLE]
    if fails:
        f = fails[-1]
        return {"kind": "fail", "step": f["step"], "class": f.get("class"), "attempt": f.get("attempt")}
    tagged = any(s["step"] == "tag" and s["status"] == "ok" for s in inv["steps"])
    # a skip of an act an earlier invocation already did is fine; a skip that leaves the tag unpushed is a stop
    if skipped_irrev and not tagged:
        return {"kind": "skipped", "step": skipped_irrev[0], "skipped": skipped_irrev}
    if inv.get("completed") and ran and all(s["status"] == "ok" for s in ran):
        if ran[-1]["step"] == STEP_ORDER[-1]:
            return {"kind": "completed", "step": ran[-1]["step"]}
        # `run completed` over a table that never reached the end (incident 22's first form)
        return {"kind": "stopped", "step": ran[-1]["step"], "claimed_complete": True}
    last = ran[-1]["step"] if ran else None
    # stopped: the last step either finished ok (stopped before the next) or never wrote a terminal line
    return {"kind": "stopped", "step": last, "mid_step": bool(ran and ran[-1]["status"] == "running")}


_HISTORY_CACHE: dict = {}


def history(root: Path = ROOT) -> dict:
    """Every invocation of every release under root/.release, for the History tab."""
    release_dir = root / ".release"
    ledgers = sorted(release_dir.glob("*/events.jsonl"))
    key = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in ledgers)
    sinks = tuple((str(p), p.stat().st_mtime_ns) for p in release_dir.glob("*/bn-events.log"))
    if _HISTORY_CACHE.get("key") == (key, sinks, str(root)):
        return _HISTORY_CACHE["value"]

    by_release: dict[str, list[dict]] = {}
    dirs_of: dict[str, list[Path]] = {}
    run_dirs: dict[str, Path] = {}
    unparsed = 0
    for p in ledgers:
        run_dirs[p.parent.name] = p.parent
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
            try:
                e = json.loads(line)
            except ValueError:
                unparsed += 1     # counted and shown, never silently dropped
                continue
            if not isinstance(e, dict) or not e.get("step"):
                unparsed += 1
                continue
            e["_dir"], e["_n"] = p.parent.name, n
            v = str(e.get("run") or p.parent.name)
            by_release.setdefault(v, []).append(e)
            if p.parent not in dirs_of.setdefault(v, []):
                dirs_of[v].append(p.parent)

    def vkey(v: str):
        return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.-]", v))

    releases = []
    for v in sorted(by_release, key=lambda v: min(e.get("ts", "") for e in by_release[v])):
        lines = sorted(by_release[v], key=lambda e: (e.get("ts", ""), e["_dir"], e["_n"]))
        invs = _invocations(lines, run_dirs)
        for i, inv in enumerate(invs, 1):
            inv["id"] = f"{v}#{i}"
            inv["entry"] = next((s["step"] for s in inv["steps"] if s["status"] != "skipped"), None)
            inv["exit"] = _exit(inv)
            cause = CAUSES.get(inv["id"])
            if cause:
                inv["exit"]["cause"], inv["exit"]["incident"] = cause
        shipped = any(s["step"] == "tag" and s["status"] == "ok" for inv in invs for s in inv["steps"])
        releases.append({"version": v, "dirs": [d.name for d in dirs_of[v]], "invocations": invs,
                         "shipped": shipped, "verify": _final_verify(dirs_of[v], root),
                         "unledgered": [{"where": w, "cause": c, "incident": n} for w, c, n in UNLEDGERED.get(v, [])]})
    releases.sort(key=lambda r: vkey(r["version"]))

    first = min((inv["start"] for r in releases for inv in r["invocations"] if inv.get("start")), default=None)
    commits = _machine_commits(root, first) if first else []
    if commits is not None:
        for c in commits:
            c["ts"] = _iso_utc(c["ts"])

    value = {"schema": 1, "steps": STEP_ORDER, "irreversible": sorted(IRREVERSIBLE), "channels": CHANNEL_ORDER,
             "releases": releases, "machine_commits": commits, "unparsed_lines": unparsed,
             "ledgers": len(ledgers)}
    _HISTORY_CACHE["key"], _HISTORY_CACHE["value"] = (key, sinks, str(root)), value
    return value


def main(argv: list[str]) -> int:
    if "--history" in argv:
        print(json.dumps(history(), indent=1))
        return 0
    runs = sorted(p for p in (ROOT / ".release").glob("*/events.jsonl"))
    if not runs:
        print("no runs under .release/ yet")
        return 0

    classes: Counter[str] = Counter()
    per_class_runs: dict[str, set[str]] = {}
    total_tries = total_fails = clean = 0

    print(f"  {'release':<9} {'tries':>5} {'failures':>9}  classes")
    for events in runs:
        version = events.parent.name
        tries, fails = _attempts(events)
        total_tries += tries
        total_fails += len(fails)
        if not fails:
            clean += 1
        here: Counter[str] = Counter()
        for step, attempt in fails:
            cls = classify(events.parent / "logs" / f"{step}.{attempt}.log")
            classes[cls] += 1
            here[cls] += 1
            per_class_runs.setdefault(cls, set()).add(version)
        shown = " ".join(f"{c}×{n}" if n > 1 else c for c, n in here.most_common())
        print(f"  {version:<9} {tries:>5} {len(fails):>9}  {shown or '—'}")

    print(f"\n  {len(runs)} runs · {total_tries} attempts · {total_fails} failures"
          f" · {clean} clean ({100 * clean // max(len(runs), 1)}%)")

    print("\n  failure class          count   releases   recurring?")
    for cls, n in classes.most_common():
        seen = len(per_class_runs[cls])
        # Recurrence across RELEASES is the signal, not raw count: three
        # failures in one run is one bad night, three across three runs is a
        # class that will happen again.
        flag = "← recurring" if seen > 1 else ""
        print(f"  {cls:<22} {n:>5}   {seen:>8}   {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
