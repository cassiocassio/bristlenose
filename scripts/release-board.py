#!/usr/bin/env python3
"""release-board.py — draw the release board from what the train wrote down.

    .venv/bin/python scripts/release-board.py [VERSION] [--out DIR] [--with-logs] [--json]

The board is the London Underground map of a release, not the Ordnance
Survey: sequence, dependencies, pass and fail, the qualitative state — no
time axis. Design and the per-pane no-data table: docs/design-release-board.md.

READ, NEVER DERIVE. Every tile comes from a file a script wrote:
  .release/<v>/steps.tbl        the run's own step table (snapshotted by release.sh)
  .release/<v>/events.jsonl     the conductor's ledger (folded, never stored)
  .release/<v>/bn-events.log    the sink: @bn lines from every script, with ts= and run=
  .release/<v>/.lock/pid        liveness — a pid we can signal, or not
  .release/<v>/heartbeat        one overwritten line: epoch  step  elapsed  last-log-line
  .release/<v>/context.json     host facts, read through an ALLOWLIST (never env, never host)
  .release/<v>/ci-sha           the sha strict CI was dispatched on
  .release/<v>/logs/<step>.<n>.log   PATH and exit code only, unless --with-logs
  scripts/project.conf          CHANNELS / CHANNELS_UNPROBEABLE
  docs/testing/ratchet.json     ceilings (current values are not measured here)
Where nothing was written the tile says NO DATA — a third state. Where the
driver wrote a boundary and the children wrote nothing, it says so.

The CONFOUNDED-EXPECTATIONS LOG is the drift guard: everything the feed said
that this board has no rule for (unknown kinds, fields, status words), every
known thing carrying a new value, everything the run declared and never
produced, and what changed since the previous run. Its count is in the header
even when it is zero.

This script makes no network call. `release.sh status` and `release.sh verify`
are the two verbs that ask GitHub and the channels; they write the sink.

Exit codes: 0 a board was written · 1 no run dir / no ledger · 2 usage.
stdlib only, plus desktop/scripts/bn_events.py imported by path.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "scripts" / "release-board.template.html"

# The .dmg validity window. The number lives in AlphaBuild.swift (the app
# enforces it); this mirror exists so the board can draw the clock, and
# test-release-board.py asserts the two agree.
DMG_VALIDITY_DAYS = 30

VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*")

# The board's vocabulary. Anything outside it is a confounded expectation,
# rendered raw and counted — never dropped.
KNOWN_KINDS = {"meta", "step", "check", "gate", "art", "done", "bar", "run", "row", "verify", "clock", "ci"}
LEDGER_STATES = {"ok", "fail", "running", "pending", "skipped", "started", "completed"}
STEP_STATES = {"start", "ok", "skip", "fail", "end"}
ROW_RESULTS = {"ok", "warn", "bad", "skipped", "unreachable"}
CI_RESULTS = {"success", "failure", "cancelled", "skipped", "queued", "in_progress", "waiting", "unreachable", "no run for sha", "neutral", "timed_out", "action_required", "stale", "startup_failure", "completed", "-"}
CONTEXT_ALLOWLIST = ("os", "arch", "xcode", "python", "disk_free_gb", "git")
CI_VERDICT_ROW = "publish gate"   # the preflight row the CI tile keys on

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _load_bn_events():
    spec = importlib.util.spec_from_file_location("bn_events", ROOT / "desktop" / "scripts" / "bn_events.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


bn_events = _load_bn_events()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mtime_iso(p: Path) -> str | None:
    try:
        return dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return None


# ── inputs ───────────────────────────────────────────────────────────────────

def resolve_version(arg: str | None, release_dir: Path, narrate=lambda s: None) -> str | None:
    if arg:
        if not VERSION_RE.fullmatch(arg):
            sys.stderr.write(f"error: '{arg}' is not a version shape\n")
            raise SystemExit(2)  # usage, not "no run": a SystemExit(str) would exit 1
        return arg
    candidates = [d for d in release_dir.glob("*/") if (d / "events.jsonl").is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda d: (d / "events.jsonl").stat().st_mtime, reverse=True)
    if len(candidates) > 1:
        narrate(f"({len(candidates)} runs under {release_dir.name}/ — using the newest, {candidates[0].name})")
    return candidates[0].name


def read_steps(run_dir: Path) -> tuple[list[dict], str, str | None]:
    """→ (steps, source, version_line). source: 'steps.tbl' | 'ledger'."""
    p = run_dir / "steps.tbl"
    steps: list[dict] = []
    if p.is_file():
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        ver = lines[0] if lines and lines[0].startswith("#") else None
        for line in lines:
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 6)
            if len(parts) < 7:
                continue
            sid, label, kind, est, tier, cons, cmd = parts
            steps.append({"id": sid, "label": label, "kind": kind, "est": est, "tier": tier, "consequence": cons})
        return steps, "steps.tbl", ver
    return steps, "ledger", None


def read_ledger(run_dir: Path) -> dict:
    """The conductor's ledger, folded. Mirrors release.sh's fold_status: last status
    per step wins; a fragment naming a step folds it to corrupt; only newline-
    terminated lines are complete."""
    p = run_dir / "events.jsonl"
    out = {"present": p.is_file(), "events": [], "fold": {}, "corrupt": [], "unparsed": 0, "partial": False,
           "started": None, "attempts": 0, "completed": False, "as_of": mtime_iso(p)}
    if not p.is_file():
        return out
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    if text and not text.endswith("\n"):
        out["partial"] = True
        lines = lines[:-1]
    else:
        lines = [ln for ln in lines if ln != ""]
    for no, raw in enumerate(lines, 1):
        try:
            ev = json.loads(raw)
        except ValueError:
            m = re.search(r'"step":"([^"]*)"', raw)
            if m:
                out["corrupt"].append(m.group(1))
                out["fold"][m.group(1)] = {"status": "corrupt"}
            else:
                out["unparsed"] += 1
            continue
        out["events"].append({"line": no, **ev})
        step, status = ev.get("step", ""), ev.get("status", "")
        if step == "run":
            if status == "started":
                out["attempts"] += 1
                out["started"] = out["started"] or ev.get("ts")
                out["completed"] = False
            elif status == "completed":
                out["completed"] = True
            continue
        cur = out["fold"].setdefault(step, {"status": "pending", "attempt": 0, "elapsed": None, "detail": "", "ts": None})
        cur["status"] = status if status in LEDGER_STATES else "corrupt"
        cur["ts"] = ev.get("ts")
        cur["detail"] = ev.get("detail", "")
        m = re.fullmatch(r"attempt (\d+)", cur["detail"] or "")
        if m:
            cur["attempt"] = int(m.group(1))
        m = re.fullmatch(r"(\d+)s", cur["detail"] or "")
        if m and status == "ok":
            cur["elapsed"] = int(m.group(1))
    return out


def read_liveness(run_dir: Path) -> dict:
    lock = run_dir / ".lock"
    pid_file = lock / "pid"
    out = {"lock": lock.is_dir(), "pid": None, "alive": None, "heartbeat": None}
    if pid_file.is_file():
        try:
            out["pid"] = int(pid_file.read_text().strip())
        except ValueError:
            out["pid"] = None
        if out["pid"]:
            try:
                os.kill(out["pid"], 0)
                out["alive"] = True
            except ProcessLookupError:
                out["alive"] = False
            except PermissionError:
                out["alive"] = True
    hb = run_dir / "heartbeat"
    if hb.is_file():
        raw = hb.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            out["heartbeat"] = {"state": "mid-write"}
        else:
            parts = raw.split("\t")
            try:
                epoch = int(parts[0])
                age = int(dt.datetime.now(dt.timezone.utc).timestamp()) - epoch
            except ValueError:
                epoch, age = None, None
            out["heartbeat"] = {"state": "present", "epoch": epoch, "age_s": age,
                                "step": parts[1] if len(parts) > 1 else None,
                                "elapsed_s": parts[2] if len(parts) > 2 else None,
                                "last_line": _ANSI.sub("", parts[3])[:100] if len(parts) > 3 else ""}
    return out


def read_context(run_dir: Path) -> dict | None:
    p = run_dir / "context.json"
    if not p.is_file():
        return None
    try:
        ctx = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {"unparseable": True}
    # The allowlist. context.json's own env allowlist is a bug-report
    # allowlist (signing identity CN, hostname); this file may be attached to
    # things, so it carries neither env nor host.
    return {k: ctx[k] for k in CONTEXT_ALLOWLIST if k in ctx}


def read_conf(conf: Path) -> dict:
    out = {"CHANNELS": [], "CHANNELS_UNPROBEABLE": []}
    if not conf.is_file():
        return out
    for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r'^(CHANNELS|CHANNELS_UNPROBEABLE)="([^"]*)"\s*(#.*)?$', line)
        if m:
            out[m.group(1)] = m.group(2).split()
    return out


def read_ratchet(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    rows = []
    for name, spec in data.items():
        if not isinstance(spec, dict) or "ceiling" not in spec:
            continue
        rows.append({"name": name, "ceiling": spec.get("ceiling"), "authority": spec.get("authority", "local"),
                     "measured": (spec.get("measured") or {}).get("on"), "why": (spec.get("why") or "")[:120]})
    return rows


def read_sink(run_dir: Path) -> dict:
    p = run_dir / "bn-events.log"
    out = {"present": p.is_file(), "events": [], "unparsed": [], "partial": False, "as_of": mtime_iso(p)}
    if not p.is_file():
        return out
    events, unparsed, partial = bn_events.parse_stream(p.read_text(encoding="utf-8", errors="replace"))
    out["events"] = [{"line": no, "kind": kind, **fields} for no, kind, fields in events]
    out["unparsed"] = [{"line": no, "raw": raw[:200]} for no, raw in unparsed]
    out["partial"] = partial
    return out


def read_logs(run_dir: Path, steps_needed: list[str], with_logs: bool) -> dict:
    logdir = run_dir / "logs"
    out: dict = {}
    for sid in steps_needed:
        attempts = sorted(logdir.glob(f"{sid}.*.log"), key=lambda q: int(q.stem.split(".")[-1]) if q.stem.split(".")[-1].isdigit() else 0)
        if not attempts:
            continue
        newest = attempts[-1]
        entry = {"path": str(newest.relative_to(ROOT)) if str(newest).startswith(str(ROOT)) else newest.name,
                 "attempts": len(attempts), "size": newest.stat().st_size}
        if with_logs:
            text = newest.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
            lines = [_ANSI.sub("", ln) for ln in text.split("\n")]
            lines = ["".join(ch for ch in ln if ch >= " ")[:200] for ln in lines if ln.strip()]
            entry["tail"] = lines[-12:]
        out[sid] = entry
    return out


# ── the model ────────────────────────────────────────────────────────────────

def fold_stations(steps: list[dict], ledger: dict, liveness: dict, source: str) -> tuple[list[dict], list[str]]:
    """The line. One station per table step; state from the ledger; liveness decides
    running vs stranded. Returns (stations, unknown_step_ids)."""
    known = {s["id"] for s in steps}
    fold = ledger["fold"]
    stations = []
    order = steps if source == "steps.tbl" else [{"id": k, "label": k, "kind": "plain", "est": "", "tier": "", "consequence": ""} for k in fold]
    for s in order:
        f = fold.get(s["id"])
        if f is None:
            if s["tier"]:
                state = "later"
            elif ledger["completed"]:
                state = "not-in-this-run"
            else:
                state = "pending"
            stations.append({**s, "state": state, "attempt": 0, "elapsed": None, "detail": ""})
            continue
        state = f["status"]
        if state == "running":
            if liveness["lock"] and liveness["alive"]:
                state = "running"
            else:
                state = "stranded"
        stations.append({**s, "state": state, "attempt": f.get("attempt", 0), "elapsed": f.get("elapsed"),
                         "detail": f.get("detail", ""), "ts": f.get("ts")})
    unknown = [k for k in fold if k not in known and source == "steps.tbl"]
    return stations, unknown


def group_sink(sink: dict, steps: list[dict]) -> dict:
    """Split the sink's events into the panes, attributing child build events to the
    driver's step window they fell inside."""
    step_ids = {s["id"] for s in steps}
    windows: list[dict] = []      # driver windows: {id, attempt, start_line, end_line, rc, elapsed, children}
    open_by_id: dict[str, dict] = {}
    preflight_batches: list[list[dict]] = [[]]
    verify_batches: list[dict] = []
    clocks: dict[str, dict] = {}
    ci: list[dict] = []
    unknown_kinds: list[dict] = []
    new_shape: list[dict] = []
    driver_runs: list[dict] = []
    meta: dict = {}
    for ev in sink["events"]:
        kind = ev["kind"]
        if kind not in KNOWN_KINDS:
            unknown_kinds.append({"line": ev["line"], "kind": kind, "fields": {k: v for k, v in ev.items() if k not in ("line", "kind")}})
            continue
        if kind == "run":
            driver_runs.append(ev)
        elif kind == "step" and "attempt" in ev and ev.get("id") in step_ids:
            if ev.get("status") == "start":
                w = {"id": ev["id"], "attempt": ev.get("attempt"), "start_line": ev["line"], "start_ts": ev.get("ts"),
                     "end_line": None, "rc": None, "elapsed": None, "children": []}
                windows.append(w)
                open_by_id[ev["id"]] = w
            elif ev.get("status") == "end":
                w = open_by_id.pop(ev.get("id"), None)
                if w is None:
                    w = {"id": ev.get("id"), "attempt": ev.get("attempt"), "start_line": None, "start_ts": None,
                         "end_line": ev["line"], "rc": ev.get("rc"), "elapsed": ev.get("elapsed"), "children": []}
                    windows.append(w)
                else:
                    w["end_line"] = ev["line"]
                    w["rc"] = ev.get("rc")
                    w["elapsed"] = ev.get("elapsed")
            else:
                new_shape.append({"line": ev["line"], "kind": "step", "field": "status", "value": ev.get("status")})
        elif kind in ("step", "check", "gate", "art", "meta", "done", "bar"):
            if kind == "step" and ev.get("status") not in STEP_STATES:
                new_shape.append({"line": ev["line"], "kind": "step", "field": "status", "value": ev.get("status")})
            if kind == "meta":
                meta = {k: v for k, v in ev.items() if k not in ("line", "kind")}
            # attribute to the most recent open driver window, else to a standalone bucket
            target = None
            for w in reversed(windows):
                if w["start_line"] is not None and w["start_line"] < ev["line"] and (w["end_line"] is None or ev["line"] < w["end_line"]):
                    target = w
                    break
            if target is None:
                target = open_by_id.get("__standalone__")
                if target is None:
                    target = {"id": "standalone", "attempt": None, "start_line": 0, "start_ts": None, "end_line": None,
                              "rc": None, "elapsed": None, "children": []}
                    windows.append(target)
                    open_by_id["__standalone__"] = target
            target["children"].append(ev)
        elif kind == "row":
            if ev.get("result") not in ROW_RESULTS:
                new_shape.append({"line": ev["line"], "kind": "row", "field": "result", "value": ev.get("result")})
            src = ev.get("src")
            if src == "preflight":
                batch = preflight_batches[-1]
                if any(r.get("label") == ev.get("label") for r in batch):
                    preflight_batches.append([ev])
                    continue
                batch.append(ev)
            elif src == "verify":
                if not verify_batches or verify_batches[-1].get("done"):
                    verify_batches.append({"start": None, "done": None, "rows": []})
                verify_batches[-1]["rows"].append(ev)
            else:
                new_shape.append({"line": ev["line"], "kind": "row", "field": "src", "value": src})
        elif kind == "verify":
            if ev.get("status") == "start":
                verify_batches.append({"start": ev, "done": None, "rows": []})
            elif ev.get("status") == "done":
                if not verify_batches or verify_batches[-1].get("done"):
                    verify_batches.append({"start": None, "done": None, "rows": []})
                verify_batches[-1]["done"] = ev
            else:
                new_shape.append({"line": ev["line"], "kind": "verify", "field": "status", "value": ev.get("status")})
        elif kind == "clock":
            clocks[ev.get("name", "?")] = ev
        elif kind == "ci":
            if ev.get("result") not in CI_RESULTS:
                new_shape.append({"line": ev["line"], "kind": "ci", "field": "result", "value": ev.get("result")})
            ci.append(ev)
    return {"windows": windows, "driver_runs": driver_runs, "preflight_batches": preflight_batches,
            "verify_batches": verify_batches, "clocks": clocks, "ci": ci, "meta": meta,
            "unknown_kinds": unknown_kinds, "new_shape": new_shape}


def build_pane(grouped: dict, ledger: dict) -> dict:
    """The build steps, from the sink's child events inside the driver's build-all
    window (or a standalone bucket). Three states: not run / ran, sink empty / data."""
    windows = [w for w in grouped["windows"] if w["id"] in ("build-all", "build-dmg")]
    fold = ledger["fold"]
    out = {"lanes": []}
    for lane_id in ("build-all", "build-dmg"):
        ws = [w for w in windows if w["id"] == lane_id]
        ledger_state = fold.get(lane_id, {}).get("status")
        if not ws:
            state = "not-run" if ledger_state in (None, "pending") else "ran-no-sink"
            out["lanes"].append({"id": lane_id, "state": state, "ledger_state": ledger_state, "steps": [], "checks": [], "gates": [], "arts": []})
            continue
        w = ws[-1]
        steps: dict[str, dict] = {}
        order: list[str] = []
        checks, gates, arts = [], [], []
        for ev in w["children"]:
            k = ev["kind"]
            if k == "step":
                sid = ev.get("id", "?")
                if sid not in steps:
                    steps[sid] = {"id": sid, "phase": ev.get("phase", ""), "name": ev.get("name", ""), "state": "running", "elapsed": None, "detail": ""}
                    order.append(sid)
                st = steps[sid]
                if ev.get("phase"):
                    st["phase"] = ev["phase"]
                if ev.get("name"):
                    st["name"] = ev["name"]
                if ev.get("status") in ("ok", "skip", "fail"):
                    st["state"] = {"ok": "ok", "skip": "skipped", "fail": "fail"}[ev["status"]]
                    try:
                        st["elapsed"] = float(ev["elapsed"]) if ev.get("elapsed") else None
                    except ValueError:
                        st["elapsed"] = None
                    st["detail"] = ev.get("detail", "")
            elif k == "check":
                checks.append({"parent": ev.get("parent"), "label": ev.get("label"), "result": ev.get("result"), "evidence": ev.get("evidence", "")})
            elif k == "gate":
                gates.append({"id": ev.get("id"), "desc": ev.get("desc"), "result": ev.get("result"), "evidence": ev.get("evidence", "")})
            elif k == "art":
                arts.append({"key": ev.get("key"), "value": ev.get("value", "")})
        state = "data" if w["children"] else "ran-no-sink"
        if not w["children"] and w["end_line"] is None:
            state = "running-no-sink"
        out["lanes"].append({"id": lane_id, "state": state, "ledger_state": ledger_state, "attempt": w["attempt"],
                             "rc": w["rc"], "elapsed": w["elapsed"], "steps": [steps[s] for s in order],
                             "checks": checks, "gates": gates, "arts": arts})
    return out


def channels_pane(conf: dict, grouped: dict, sink_as_of: str | None) -> dict:
    batches = grouped["verify_batches"]
    latest = batches[-1] if batches else None
    rows = {r.get("label"): r for r in (latest["rows"] if latest else [])}
    complete = bool(latest and latest.get("done"))
    cards = []
    for ch in conf["CHANNELS"]:
        r = rows.get(ch)
        if r is None:
            state = "skipped" if ch in conf["CHANNELS_UNPROBEABLE"] and latest is None else "no-data"
            cards.append({"name": ch, "state": state, "evidence": "no probe from this machine" if state == "skipped" else "", "as_of": None})
        else:
            cards.append({"name": ch, "state": r.get("result"), "evidence": r.get("evidence", ""), "as_of": r.get("ts")})
    extras = [{"label": ln, "state": r.get("result"), "evidence": r.get("evidence", "")} for ln, r in rows.items() if ln not in conf["CHANNELS"]]
    rollup = None
    if latest and latest.get("done"):
        d = latest["done"]
        rollup = {"rc": d.get("rollup"), "channels": d.get("channels"), "ok": d.get("ok"), "as_of": d.get("ts")}
    return {"cards": cards, "extras": extras, "complete": complete, "batches": len(batches),
            "partial_rows": len(rows) if latest and not complete else 0, "rollup": rollup, "as_of": sink_as_of}


def clocks_pane(grouped: dict) -> list[dict]:
    out = []
    tf = grouped["clocks"].get("testflight")
    if tf:
        exp = (tf.get("expires") or "").strip()
        out.append({"name": "testflight", "build": tf.get("build"), "expires": exp or None, "state": "no-data" if not exp else "known",
                    "confirmed": tf.get("confirmed"), "as_of": tf.get("ts")})
    dmg = grouped["clocks"].get("dmg")
    if dmg:
        built = (dmg.get("built") or "").strip()
        expires = None
        try:
            b = dt.datetime.strptime(built, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            expires = (b + dt.timedelta(days=DMG_VALIDITY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
        out.append({"name": "dmg", "built": built or None, "expires": expires, "state": "no-data" if not expires else "known",
                    "version": dmg.get("version"), "as_of": dmg.get("ts"), "rule": f"{DMG_VALIDITY_DAYS} days from the build (AlphaBuild.swift)"})
    return out


def ci_pane(grouped: dict, ci_sha: str | None) -> dict:
    lines = grouped["ci"]
    if not lines:
        return {"state": "not-queried", "hint": "run `release.sh status`", "runs": [], "jobs": []}
    latest_by_key: dict[tuple, dict] = {}
    for ev in lines:
        key = (ev.get("workflow"), ev.get("job"))
        latest_by_key[key] = ev
    runs = [v for (wf, job), v in latest_by_key.items() if not job]
    jobs = [v for (wf, job), v in latest_by_key.items() if job]
    matrix = []
    for j in jobs:
        m = re.fullmatch(r"(\w[\w-]*) \((\d+\.\d+), ([a-z]+)-latest\)", j.get("job", ""))
        if m:
            matrix.append({"job": m.group(1), "python": m.group(2), "os": m.group(3), "result": j.get("result")})
    return {"state": "data", "runs": [{"workflow": r.get("workflow"), "run_id": r.get("run_id"), "sha": r.get("sha"), "result": r.get("result"), "as_of": r.get("ts")} for r in runs],
            "jobs": [{"job": j.get("job"), "result": j.get("result"), "workflow": j.get("workflow")} for j in jobs],
            "matrix": matrix, "sha_matches": (ci_sha is not None and any(r.get("sha") == ci_sha for r in runs))}


def preflight_pane(grouped: dict) -> dict:
    batches = [b for b in grouped["preflight_batches"] if b]
    if not batches:
        return {"state": "no-data", "rows": [], "counts": {}}
    latest = batches[-1]
    counts: dict[str, int] = {}
    for r in latest:
        counts[r.get("result", "?")] = counts.get(r.get("result", "?"), 0) + 1
    ci_row = next((r for r in latest if r.get("label") == CI_VERDICT_ROW), None)
    return {"state": "data", "rows": [{"label": r.get("label"), "result": r.get("result"), "evidence": r.get("evidence", "")} for r in latest],
            "counts": counts, "batches": len(batches), "as_of": latest[-1].get("ts"),
            "ci_verdict": {"result": ci_row.get("result"), "evidence": ci_row.get("evidence", "")} if ci_row else None}


def merged_events(ledger: dict, sink: dict, limit: int = 60) -> list[dict]:
    rows = []
    for ev in ledger["events"]:
        rows.append({"ts": ev.get("ts", ""), "rank": 0, "line": ev["line"], "src": "ledger",
                     "text": f"{ev.get('step','')} {ev.get('status','')} {ev.get('detail','')}".strip()})
    for ev in sink["events"]:
        summary = " ".join(f"{k}={v}" for k, v in ev.items() if k not in ("line", "kind", "ts", "run"))
        rows.append({"ts": ev.get("ts", ""), "rank": 1, "line": ev["line"], "src": ev["kind"], "text": summary[:160]})
    rows.sort(key=lambda r: (r["ts"], r["rank"], r["line"]))
    return rows[-limit:]


def activity(ledger: dict, sink: dict) -> dict:
    stamps = [ev.get("ts") for ev in ledger["events"]] + [ev.get("ts") for ev in sink["events"]]
    stamps = [s for s in stamps if s]
    if not stamps:
        return {"minutes": [], "start": None}
    parsed = []
    for s in stamps:
        try:
            parsed.append(dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            pass
    if not parsed:
        return {"minutes": [], "start": None}
    t0 = min(parsed).replace(second=0)
    span = int((max(parsed) - t0).total_seconds() // 60) + 1
    span = min(span, 600)
    counts = [0] * span
    for t in parsed:
        i = int((t - t0).total_seconds() // 60)
        if 0 <= i < span:
            counts[i] += 1
    return {"minutes": counts, "start": t0.strftime("%Y-%m-%dT%H:%M:%SZ")}


def confounded(steps: list[dict], steps_source: str, stations: list[dict], unknown_steps: list[str], grouped: dict,
               channels: dict, preflight: dict, ledger: dict, sink: dict, previous: dict | None) -> dict:
    log = {"unknown": [], "new_shape": [], "missing": [], "changed": [], "computable": True, "notes": []}
    if steps_source != "steps.tbl":
        log["computable"] = False
        log["notes"].append("no steps.tbl — the run predates the snapshot (5 Sep 2026); stations are the ledger's own step ids in first-seen order")
    for u in grouped["unknown_kinds"]:
        log["unknown"].append({"what": f"@bn kind '{u['kind']}'", "line": u["line"], "raw": u["fields"]})
    for u in sink["unparsed"]:
        log["unknown"].append({"what": "unparseable sink line", "line": u["line"], "raw": u["raw"]})
    if ledger["unparsed"]:
        log["unknown"].append({"what": f"{ledger['unparsed']} unparseable ledger line(s) naming no step", "line": None, "raw": ""})
    for s in unknown_steps:
        log["unknown"].append({"what": f"ledger step '{s}' is not in steps.tbl", "line": None, "raw": ""})
    for n in grouped["new_shape"]:
        log["new_shape"].append({"what": f"{n['kind']}.{n['field']} = '{n['value']}'", "line": n["line"]})
    for st in stations:
        if st["state"] == "corrupt":
            log["new_shape"].append({"what": f"ledger status for '{st['id']}' outside the fold vocabulary (corrupt)", "line": None})
    # missing
    if channels["complete"]:
        for c in channels["cards"]:
            if c["state"] == "no-data":
                log["missing"].append({"what": f"channel '{c['name']}' has no row in a verify that reported done"})
    if ledger["completed"]:
        for st in stations:
            if st["state"] == "not-in-this-run":
                log["missing"].append({"what": f"step '{st['id']}' declared in steps.tbl, no event in a completed run"})
    for w in grouped["windows"]:
        if w["id"] in ("build-all", "build-dmg") and w["end_line"] is not None and not w["children"]:
            log["missing"].append({"what": f"driver window for '{w['id']}' (attempt {w['attempt']}) closed with zero child lines — BN_REPORT=0, unwritable sink, or a script that never sourced sink.sh"})
    if preflight["state"] == "data" and preflight.get("ci_verdict") is None:
        log["missing"].append({"what": f"preflight row '{CI_VERDICT_ROW}' absent from the latest preflight — the CI tile keys on it"})
    # changed since previous run
    if previous is None:
        log["notes"].append("no previous run with steps.tbl to diff against")
    else:
        prev_ids = [s["id"] for s in previous["steps"]]
        cur_ids = [s["id"] for s in steps]
        for sid in cur_ids:
            if sid not in prev_ids:
                log["changed"].append({"what": f"step '{sid}' added since {previous['version']}"})
        for sid in prev_ids:
            if sid not in cur_ids:
                log["changed"].append({"what": f"step '{sid}' removed since {previous['version']}"})
        if prev_ids and cur_ids and [s for s in cur_ids if s in prev_ids] != [s for s in prev_ids if s in cur_ids]:
            log["changed"].append({"what": f"step order changed since {previous['version']}"})
        prev_ch, cur_ch = set(previous.get("channels", [])), set(c["name"] for c in channels["cards"])
        for ch in sorted(cur_ch - prev_ch):
            log["changed"].append({"what": f"channel '{ch}' added since {previous['version']}"})
        for ch in sorted(prev_ch - cur_ch):
            log["changed"].append({"what": f"channel '{ch}' removed since {previous['version']}"})
    log["count"] = sum(len(log[k]) for k in ("unknown", "new_shape", "missing", "changed"))
    return log


def previous_run(release_dir: Path, version: str, conf: dict) -> dict | None:
    """The next-newest run dir that carries a steps.tbl — the diff base."""
    cands = [d for d in release_dir.glob("*/") if d.name != version and (d / "steps.tbl").is_file() and (d / "events.jsonl").is_file()]
    if not cands:
        return None
    cands.sort(key=lambda d: (d / "events.jsonl").stat().st_mtime, reverse=True)
    d = cands[0]
    steps, _, _ = read_steps(d)
    sink = read_sink(d)
    chans = sorted({ev.get("label") for ev in sink["events"] if ev["kind"] == "row" and ev.get("src") == "verify" and ev.get("label") in conf["CHANNELS"]})
    return {"version": d.name, "steps": steps, "channels": chans or conf["CHANNELS"]}


def build_model(root: Path, version: str, with_logs: bool, narrate=lambda s: None) -> dict:
    release_dir = root / ".release"
    run_dir = release_dir / version
    steps, steps_source, steps_ver = read_steps(run_dir)
    ledger = read_ledger(run_dir)
    liveness = read_liveness(run_dir)
    sink = read_sink(run_dir)
    conf = read_conf(root / "scripts" / "project.conf")
    stations, unknown_steps = fold_stations(steps, ledger, liveness, steps_source)
    grouped = group_sink(sink, steps if steps_source == "steps.tbl" else [{"id": s["id"]} for s in stations])
    ci_sha = (run_dir / "ci-sha").read_text().strip() if (run_dir / "ci-sha").is_file() else None
    if ci_sha and not re.fullmatch(r"[0-9a-f]{40}", ci_sha):
        ci_sha = None
    channels = channels_pane(conf, grouped, sink["as_of"])
    preflight = preflight_pane(grouped)
    build = build_pane(grouped, ledger)
    ci = ci_pane(grouped, ci_sha)
    clocks = clocks_pane(grouped)
    needing_logs = [s["id"] for s in stations if s["state"] in ("fail", "running", "stranded", "corrupt")]
    logs = read_logs(run_dir, needing_logs, with_logs)
    prev = previous_run(release_dir, version, conf)
    conf_log = confounded(steps, steps_source, stations, unknown_steps, grouped, channels, preflight, ledger, sink, prev)
    running = [s for s in stations if s["state"] == "running"]
    stranded = [s for s in stations if s["state"] in ("stranded", "corrupt")]
    if ledger["completed"] and not running and not stranded:
        phase = "completed"
    elif stranded:
        phase = "stranded"
    elif running:
        phase = "running"
    elif not ledger["present"]:
        phase = "no-ledger"
    else:
        phase = "stopped"
    sources = [p for p in (run_dir / "events.jsonl", run_dir / "bn-events.log", run_dir / "steps.tbl", run_dir / "heartbeat") if p.exists()]
    newest_source = max((mtime_iso(p) or "" for p in sources), default=None) or None
    model = {
        "schema": 1,
        "generated": utc_now(),
        "version": version,
        "run_dir": str(run_dir),
        "phase": phase,
        "header": {"started": ledger["started"], "attempts": ledger["attempts"], "completed": ledger["completed"],
                   "context": read_context(run_dir), "ci_sha": ci_sha, "newest_source": newest_source,
                   "with_logs": with_logs, "sink_present": sink["present"], "steps_source": steps_source,
                   "steps_version": steps_ver},
        "liveness": liveness,
        "line": {"stations": stations, "source": steps_source, "unknown_steps": unknown_steps, "as_of": ledger["as_of"],
                 "ledger_partial": ledger["partial"], "ledger_unparsed": ledger["unparsed"]},
        "preflight": preflight,
        "build": build,
        "ci": ci,
        "ratchets": read_ratchet(root / "docs" / "testing" / "ratchet.json"),
        "tag": {"ci_sha": ci_sha, "station": next((s for s in stations if s["id"] == "tag"), None)},
        "channels": channels,
        "clocks": clocks,
        "events": merged_events(ledger, sink),
        "activity": activity(ledger, sink),
        "logs": logs,
        "sink": {"present": sink["present"], "events": len(sink["events"]), "unparsed": len(sink["unparsed"]),
                 "partial": sink["partial"], "as_of": sink["as_of"], "driver_runs": len(grouped["driver_runs"]),
                 "meta": grouped["meta"]},
        "confounded": conf_log,
        "previous": prev["version"] if prev else None,
    }
    return model


# ── output ───────────────────────────────────────────────────────────────────

def inline_json(model: dict) -> str:
    """ensure_ascii is NOT enough — `<`, `>` and `&` are ASCII and pass through, so a
    literal </script> in evidence text would break out of the data block
    (CLAUDE.md, the export-JSON gotcha)."""
    s = json.dumps(model, ensure_ascii=True, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_html(model: dict, template: Path) -> str:
    tpl = template.read_text(encoding="utf-8")
    if "__BOARD_JSON__" not in tpl:
        raise SystemExit(f"error: template {template} carries no __BOARD_JSON__ marker")
    return tpl.replace("__BOARD_JSON__", inline_json(model), 1)


def write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="draw the release board for a run under .release/")
    ap.add_argument("version", nargs="?", help="X.Y.Z; default: the newest run under .release/")
    ap.add_argument("--out", type=Path, help="directory for board.json + board.html (default: the run dir)")
    ap.add_argument("--with-logs", action="store_true", help="also write board-with-logs.html carrying raw log tails — do not attach it to anything")
    ap.add_argument("--json", action="store_true", help="print board.json to stdout instead of writing files")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    root = args.root.resolve()
    release_dir = root / ".release"
    def narrate(s: str) -> None:
        sys.stderr.write(f"  {s}\n")
    version = resolve_version(args.version, release_dir, narrate)
    if version is None:
        sys.stderr.write(f"error: no run under {release_dir} carries an events.jsonl — nothing to draw\n")
        return 1
    run_dir = (release_dir / version).resolve()
    if not str(run_dir).startswith(str(release_dir.resolve()) + os.sep) or not run_dir.is_dir():
        sys.stderr.write(f"error: no run dir at {release_dir / version}\n")
        return 1
    if not (run_dir / "events.jsonl").is_file():
        sys.stderr.write(f"error: {run_dir} has no events.jsonl — not a run\n")
        return 1
    model = build_model(root, version, args.with_logs, narrate)
    if args.json:
        print(json.dumps(model, indent=2, ensure_ascii=True))
        return 0
    out = (args.out or run_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    write_private(out / "board.json", json.dumps(model, indent=1, ensure_ascii=True))
    if args.with_logs:
        html = render_html(model, TEMPLATE)
        write_private(out / "board-with-logs.html", html)
        target = out / "board-with-logs.html"
    else:
        write_private(out / "board.html", render_html(model, TEMPLATE))
        target = out / "board.html"
    c = model["confounded"]
    sys.stderr.write(f"  wrote {target}  ·  {version} {model['phase']}  ·  confounded: {c['count'] if c['computable'] else 'not computable'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
