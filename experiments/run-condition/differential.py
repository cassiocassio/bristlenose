#!/usr/bin/env python3
"""Differential: every real events log through three readers.

For each ``pipeline-events.jsonl`` found under the given roots, compute:

* **server today** — the startup seed (last terminus outcome) → status page;
* **Mac today** — a Python port of ``EventLogReader.deriveState``: last
  lifecycle event within a 64 KB tail → PipelineState;
* **condition** — ``bristlenose.run_condition`` → ``page_for`` under both
  report policies.

Prints a table and writes JSON (``--out``). Project names are private —
the JSON keeps them; ``--anon`` replaces them with ``project N`` for anything
that will be committed or shown. Liveness is taken from each project's own
``run.pid`` (matched to run_id).

    .venv/bin/python experiments/run-condition/differential.py trial-runs \
        --out /tmp/diff.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bristlenose.run_condition import read_condition
from bristlenose.server.status_page import ReportPolicy, page_for

TAIL_BYTES = 64 * 1024
LIFECYCLE = {"run_started", "run_completed", "run_failed", "run_cancelled"}


def server_today(lines: list[dict]) -> str:
    for ev in reversed(lines):
        if ev.get("event") in ("run_completed", "run_failed", "run_cancelled"):
            return {"completed": "SPA", "failed": "failed",
                    "cancelled": "cancelled"}[ev["outcome"]]
    return "no-run"


def mac_today(raw: bytes, alive: bool) -> str:
    tail = raw[-TAIL_BYTES:]
    text = tail.decode("utf-8", errors="replace").split("\n")
    if len(raw) > TAIL_BYTES:
        text = text[1:]  # first line of a tail window is partial
    for line in reversed([ln for ln in text if ln.strip()]):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        kind = ev.get("event")
        if kind == "run_progress" or kind not in LIFECYCLE:
            continue
        failures = _failures(ev.get("summary"))
        if kind == "run_started":
            return "running" if alive else "failed(stranded)"
        if kind == "run_completed":
            if ev.get("kind") == "transcribe-only":
                return "partial"
            return "completedPartial" if failures else "ready"
        if kind == "run_cancelled":
            return "stopped"
        return "failedWithDiagnostic" if failures else "failed"
    return "(no tail event → manifest)"


def _failures(summary: dict | None) -> int:
    if not summary:
        return 0
    return sum(len((summary.get(k) or {}).get("failed") or [])
               for k in ("ingest", "transcripts", "topics", "quotes", "themes"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--anon", action="store_true")
    args = ap.parse_args()

    rows = []
    logs = sorted({p for r in args.roots for p in r.rglob("pipeline-events.jsonl")})
    outputs = sorted({p for r in args.roots for p in r.rglob("bristlenose-output")
                      if p.is_dir()})
    for i, log in enumerate(logs, 1):
        out = log.parent.parent
        raw = log.read_bytes()
        parsed = []
        for ln in raw.decode("utf-8", errors="replace").splitlines():
            try:
                parsed.append(json.loads(ln))
            except ValueError:
                pass
        cond = read_condition(out)
        alive = cond.latest is not None and cond.latest.state.value == "in_progress"
        latest = cond.latest
        rows.append({
            "project": f"project {i}" if args.anon else str(out.parent),
            "bytes": len(raw),
            "events": len(parsed),
            "runs": cond.history.runs,
            "kinds": sorted({e.get("kind") for e in parsed if e.get("kind")}),
            "versions": sorted({(e.get("process") or {}).get("bristlenose_version")
                                for e in parsed if e.get("event") == "run_started"} - {None}),
            "server_today": server_today(parsed),
            "mac_today": mac_today(raw, alive),
            "latest": None if latest is None else {
                "state": latest.state.value, "kind": latest.kind.value,
                "degraded": latest.degraded,
                "category": latest.cause.category if latest.cause else None},
            "report": None if cond.report is None else {
                "kind": cond.report.kind.value, "degraded": cond.report.degraded},
            "stranded": cond.history.stranded,
            "decodable": cond.decodable,
            "page_latest_attempt": page_for(cond, ReportPolicy.LATEST_ATTEMPT) or "SPA",
            "page_last_good": page_for(cond, ReportPolicy.LAST_GOOD_REPORT) or "SPA",
        })
    legacy = [str(o.parent) if not args.anon else "…" for o in outputs
              if not (o / ".bristlenose" / "pipeline-events.jsonl").exists()]
    summary = {"logs": len(logs), "output_dirs": len(outputs),
               "outputs_without_log": len(legacy), "rows": rows}
    for r in rows:
        agree = r["server_today"] == r["page_latest_attempt"]
        print(f'{r["project"][-38:]:<38} {r["runs"]:>3} runs  server={r["server_today"]:<10}'
              f' new={r["page_latest_attempt"]:<11} mac={r["mac_today"]:<22}'
              f' {"" if agree else "≠"}')
    print(f"\n{len(logs)} logs, {len(outputs)} output dirs, "
          f"{len(legacy)} without an events log")
    if args.out:
        args.out.write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
