#!/usr/bin/env python3
"""Render docs/mockups/project-condition-poc.html from the POC's real output.

Every scenario's events log is pushed through the real reducer
(``bristlenose.run_condition``) and the real status page
(``bristlenose.server.status_page.detect_status``), so the "POC" column shows
what the code produced — the copy, the outcome, the condition JSON. The
"today" column is the verified behaviour from the register in
docs/design-project-condition.md. The Mac rows in the POC column are the
phase-C design (§5), marked as designed, not built.

    .venv/bin/python experiments/run-condition/make_mockup.py \
        --diff /path/to/diff-anon.json
"""

from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    Process,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunProgressEvent,
    RunStartedEvent,
    append_event,
    events_path,
)
from bristlenose.manifest import PipelineManifest, StageRecord, StageStatus, write_manifest
from bristlenose.run_condition import read_condition
from bristlenose.server.status_page import ReportPolicy, detect_status, page_for

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/project-condition-poc.html"
_PROC = Process(pid=1, start_time="1.0", hostname="h", user="u",
                bristlenose_version="0.31.4", python_version="3.12", os="darwin-arm64")


def _ev(out: Path, kind: str, rid: str, day: int, run_kind=KindEnum.RUN, cat=None, msg=None,
        failed_sessions: int = 0) -> None:
    ts = f"2026-09-{day:02d}T14:00:00Z"
    f = events_path(out)
    if kind == "start":
        append_event(f, RunStartedEvent(ts=ts, run_id=rid, kind=run_kind, started_at=ts,
                                        process=_PROC))
    elif kind == "progress":
        append_event(f, RunProgressEvent(ts=ts, run_id=rid, kind=run_kind, started_at=ts,
                                         stage="transcribe"))
    elif kind == "done":
        append_event(f, RunCompletedEvent(ts=ts, run_id=rid, kind=run_kind, started_at=ts,
                                          ended_at=ts))
    elif kind == "fail":
        append_event(f, RunFailedEvent(ts=ts, run_id=rid, kind=run_kind, started_at=ts,
                                       ended_at=ts, cause=Cause(category=cat, message=msg,
                                                                stage="topic_segmentation",
                                                                provider="anthropic")))
    elif kind == "cancel":
        append_event(f, RunCancelledEvent(ts=ts, run_id=rid, kind=run_kind, started_at=ts,
                                          ended_at=ts, cause=Cause(
                                              category=CauseCategoryEnum.USER_SIGNAL)))


OOC = CauseCategoryEnum.OUT_OF_CREDIT

# Each scenario: name, story, events, liveness, Mac overlay, and the verified
# "today" behaviour per surface (from the register; F/N ids cite it).
SCENARIOS = [
    dict(
        id="queued-over-failure", title="Re-analysis queued behind another study",
        study="Homepage engagement",
        story="The last analysis ran out of credit. The researcher tops up and clicks "
              "Re-analyse while another study is still transcribing.",
        events=[("start", "r1", 30), ("fail", "r1", 31, OOC,
                                      "All topic segmentation calls failed.")],
        alive=[], overlay="queued · position 1",
        today=dict(row="Queued · position 1",
                   pane="“Last run failed.” — All topic segmentation calls failed.",
                   web="Last run failed. (a failure from 31 Aug, shown as current)",
                   refs="the bug that started this"),
    ),
    dict(
        id="dequeued", title="Removed from the queue",
        study="Checkout flow",
        story="A finished study is queued for a re-run, then the researcher changes their "
              "mind and chooses Stop Analysis.",
        events=[("start", "r1", 20), ("done", "r1", 20)],
        alive=[], overlay=None,
        today=dict(row="(silent — reads as never analysed)",
                   pane="“Drag Interviews Here” over a finished report; lens rows dim",
                   web="report (unchanged)", refs="F1"),
    ),
    dict(
        id="rerun-fails", title="Re-run fails over a good report",
        study="Beds & duvets",
        story="Analysed last week. Today's re-analysis fails: the Claude account is out "
              "of credit.",
        events=[("start", "r1", 21), ("done", "r1", 21), ("start", "r2", 28),
                ("fail", "r2", 28, OOC, "All quote extraction calls failed.")],
        alive=[], overlay=None,
        today=dict(row="Run failed",
                   pane="the old report (the server never heard of the failure)",
                   web="the old report, silently — until the server restarts, then "
                       "“Last run failed.”",
                   refs="F4"),
    ),
    dict(
        id="clean-rerun", title="Re-analyse completes",
        study="Talismanic",
        story="Re-analyse (which starts from scratch) finishes successfully with new "
              "sessions.",
        events=[("start", "r1", 10), ("done", "r1", 10), ("start", "r2", 28),
                ("done", "r2", 28)],
        alive=[], overlay=None, replaced_log=True,
        today=dict(row="Analysed just now",
                   pane="the PREVIOUS analysis — the watcher missed the new run",
                   web="the previous analysis until the server restarts",
                   refs="N19 (reproduced)"),
    ),
    dict(
        id="first-run", title="First analysis of a new folder",
        study="Rockclimbing",
        story="A folder of recordings is dropped on the sidebar and analysed for the "
              "first time.",
        events=[("start", "r1", 28), ("progress", "r1", 28)],
        alive=["r1"], overlay=None,
        today=dict(row="Transcribing · 1 of 8",
                   pane="“No interviews to analyse yet.” — and when it finishes, still "
                        "that, until relaunch (server watching the wrong folder)",
                   web="Nothing to see here, yet.", refs="N46 (reproduced)"),
    ),
    dict(
        id="stranded", title="The app crashed mid-run",
        study="Folder of horrors",
        story="The Mac restarted during transcription. No terminus was ever written.",
        events=[("start", "r1", 27), ("progress", "r1", 27)],
        alive=[], overlay=None,
        today=dict(row="Analysis stopped unexpectedly.",
                   pane="“No interviews to analyse yet.”",
                   web="Nothing to see here, yet. (false — found on real data)",
                   refs="F5; differential"),
    ),
    dict(
        id="import-in-flight", title="First analysis finishing — database still importing",
        study="Kitchen planner",
        story="The run has written its completion; the server is still loading the "
              "results into the report database.",
        events=[("start", "r1", 28), ("done", "r1", 28)],
        alive=[], overlay=None, importing=True,
        today=dict(row="Analysed just now",
                   pane="the report app over an empty database, or the stale "
                        "“Nothing to see here” page",
                   web="depends on which poll lands first", refs="review finding 3"),
    ),
    dict(
        id="transcribe-only", title="Transcribed, not analysed",
        study="Field notes",
        story="Only `bristlenose transcribe` has been run on this folder.",
        events=[("start", "r1", 26, KindEnum.TRANSCRIBE_ONLY),
                ("done", "r1", 26, KindEnum.TRANSCRIBE_ONLY)],
        alive=[], overlay=None,
        today=dict(row="Transcribed", pane="the report app, analysis lenses empty",
                   web="the report app, analysis lenses empty",
                   refs="N20 — kept deliberately: a status page hid the transcripts"),
    ),
    dict(
        id="legacy", title="Analysed before the events log existed",
        study="Fishkeeping",
        story="A project from March 2026, before runs were logged. The report is on disk.",
        events=[], alive=[], overlay=None, legacy=True,
        today=dict(row="Analysed", pane="“No interviews to analyse yet.” over the report",
                   web="Nothing to see here, yet.", refs="differential — 2 real projects"),
    ),
]


def mac_designed(cond, overlay: str | None, platform_page) -> tuple[str, str]:
    """The phase-C design (§5): row subtitle and pane, from condition + overlay."""
    latest, report = cond.latest, cond.report
    if overlay:
        pane = "native cover: " + overlay.capitalize()
        if report:
            pane = "the report, with a native “Queued” note in the toolbar"
        return overlay.capitalize(), pane
    if latest is None:
        return ("Analysed" if report else "—"), ("the report" if report else
                                                   "“Drag Interviews Here”")
    state = latest.state.value
    if state == "in_progress":
        return "Analysing…", ("the report" if report else "native cover: Analysing…")
    if state == "completed":
        if latest.kind == KindEnum.TRANSCRIBE_ONLY and not report:
            return "Transcribed", "the report app — sessions and transcripts, not analysed yet"
        return "Analysed", "the report"
    label = {"failed": "Run failed", "cancelled": "Stopped",
             "stranded": "Analysis stopped unexpectedly."}[state]
    return label, ("status page: " + platform_page if platform_page else "the report")


def build(diff: dict | None) -> str:
    cards = []
    for sc in SCENARIOS:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bristlenose-output"
            out.mkdir()
            for e in sc["events"]:
                kind, rid, day, *rest = e
                run_kind = rest[0] if rest and isinstance(rest[0], KindEnum) else KindEnum.RUN
                cat = rest[0] if rest and isinstance(rest[0], CauseCategoryEnum) else None
                msg = rest[1] if len(rest) > 1 else None
                _ev(out, kind, rid, day, run_kind, cat, msg)
            if sc.get("legacy"):
                write_manifest(PipelineManifest(
                    project_name="p", pipeline_version="0.14.0",
                    created_at="2026-03-14T15:00:00Z", updated_at="2026-03-14T15:16:10Z",
                    stages={"render": StageRecord(status=StageStatus.COMPLETE,
                                                  completed_at="2026-03-14T15:16:10Z")}),
                    out)
            alive = set(sc["alive"])
            cond = read_condition(out, liveness=lambda r, a=alive: r in a)
            imp = dict(importing=True, has_data=False) if sc.get("importing") else {}
            info_web = detect_status(out, cond, platform="", **imp)
            info_mac = detect_status(out, cond, platform="desktop", **imp)
            info_good = detect_status(out, cond, policy=ReportPolicy.LAST_GOOD_REPORT, **imp)
            events_text = [ln for ln in events_path(out).read_text().splitlines()] \
                if events_path(out).exists() else []
        web = (f"{info_web.short}" + (f" — {info_web.long}" if info_web.long else "")) \
            if info_web else "the report"
        mac_page = (f"{info_mac.short}" + (f" {info_mac.long}" if info_mac.long else "")) \
            if info_mac else ""
        row, pane = mac_designed(cond, sc["overlay"], mac_page)
        if sc.get("importing"):
            row, pane = "Analysed just now", "status page: " + mac_page
        cards.append(dict(
            id=sc["id"], title=sc["title"], study=sc["study"], story=sc["story"],
            refs=sc["today"]["refs"], today=sc["today"],
            poc=dict(row=row, pane=pane, web=web,
                     outcome=page_for(cond, **imp) or "SPA",
                     outcome_last_good=page_for(cond, ReportPolicy.LAST_GOOD_REPORT,
                                                **imp) or "SPA",
                     web_last_good=(info_good.short if info_good else "the report")),
            condition=cond.to_wire(),
            timeline=[_timeline(json.loads(ln)) for ln in events_text],
            overlay=sc["overlay"], replaced=sc.get("replaced_log", False),
        ))
    data = dict(cards=cards, diff=diff)
    return TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=True)
                            .replace("<", "\\u003c").replace(">", "\\u003e")
                            .replace("&", "\\u0026"))


def _timeline(ev: dict) -> dict:
    return {"event": ev["event"].replace("run_", ""), "run": ev["run_id"],
            "kind": ev["kind"], "day": ev["ts"][8:10],
            "category": (ev.get("cause") or {}).get("category")}


TEMPLATE = (Path(__file__).parent / "mockup_template.html").read_text()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", type=Path)
    args = ap.parse_args()
    diff = json.loads(args.diff.read_text()) if args.diff else None
    OUT.write_text(build(diff))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
