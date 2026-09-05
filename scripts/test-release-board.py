#!/usr/bin/env python3
"""test-release-board.py — prove the board reads, never derives.

    .venv/bin/python scripts/test-release-board.py

Every case builds a run dir under a temp .release/ and asks the generator what
it would draw. The assertions are the plan's no-data table
(docs/design-release-board.md §2) turned into code: no data is a third state,
a stranded run is not a running one, an unreachable channel is never green,
a partial verify is never rolled up, and the two escaping rules from CLAUDE.md
hold on the inlined block. The confounded-expectations log gets a fixture with
one of each section, because a drift guard that reports zero on a drifted run
is the false green it replaces.

stdlib unittest. Imports the generator by path; drives the CLI by subprocess
for the exit codes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "release-board.py"
TEMPLATE = ROOT / "scripts" / "release-board.template.html"
FIXTURE = ROOT / "tests" / "fixtures" / "release-board" / "0.28.0"
PY = sys.executable

spec = importlib.util.spec_from_file_location("release_board", GEN)
rb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rb)

STEPS = """# steps.tbl v1
preflight|preflight|gate|1m|||./scripts/check-release-ready.sh __V__
bump|bump + commit|plain|1m|||__BUMP__
build-all|build the app|plain|11m|||desktop/scripts/build-all.sh
tag|tag + push|hard|2m||HARD: this PUBLISHES|__TAG__
snap-stable|snap stable|plain|10m|2||gh workflow run snap.yml
"""
CONF = 'PROJECT_NAME="bristlenose"\nCHANNELS="pypi github testflight"\nCHANNELS_UNPROBEABLE="testflight"\n'


def ev(ts, step, status, detail=""):
    return json.dumps({"ts": ts, "run": "1.0.0", "step": step, "status": status, "detail": detail})


class Tree:
    """A throwaway repo root with .release/<v>/, scripts/project.conf and docs/testing/ratchet.json."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="rb-"))
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "project.conf").write_text(CONF)
        (self.root / "docs" / "testing").mkdir(parents=True)
        (self.root / "docs" / "testing" / "ratchet.json").write_text(json.dumps({"mypy_errors": {"ceiling": 149, "authority": "ci", "why": "x"}}))

    def run(self, version="1.0.0", steps=STEPS, events="", sink=None, extra=None):
        d = self.root / ".release" / version
        d.mkdir(parents=True, exist_ok=True)
        if steps is not None:
            (d / "steps.tbl").write_text(steps)
        (d / "events.jsonl").write_text(events)
        if sink is not None:
            (d / "bn-events.log").write_text(sink)
        for name, body in (extra or {}).items():
            p = d / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        return d

    def model(self, version="1.0.0", with_logs=False):
        return rb.build_model(self.root, version, with_logs)

    def cli(self, *args):
        return subprocess.run([PY, str(GEN), "--root", str(self.root), *args], capture_output=True, text=True)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def stations(m):
    return {s["id"]: s["state"] for s in m["line"]["stations"]}


class Fold(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_running_with_dead_pid_is_stranded_not_running(self):
        d = self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started", "bump=minor"),
                                         ev("2026-09-05T10:00:01Z", "preflight", "running", "attempt 1")]) + "\n")
        (d / ".lock").mkdir()
        (d / ".lock" / "pid").write_text("999999")
        m = self.t.model()
        self.assertEqual(stations(m)["preflight"], "stranded")
        self.assertEqual(m["phase"], "stranded")
        self.assertFalse(m["liveness"]["alive"])

    def test_running_with_live_pid_is_running(self):
        d = self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started", "bump=minor"),
                                         ev("2026-09-05T10:00:01Z", "preflight", "running", "attempt 1")]) + "\n")
        (d / ".lock").mkdir()
        (d / ".lock" / "pid").write_text(str(os.getpid()))
        m = self.t.model()
        self.assertEqual(stations(m)["preflight"], "running")
        self.assertEqual(m["phase"], "running")

    def test_running_without_lock_is_stranded(self):
        self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"),
                                     ev("2026-09-05T10:00:01Z", "bump", "running", "attempt 1")]) + "\n")
        self.assertEqual(stations(self.t.model())["bump"], "stranded")

    def test_fragment_naming_a_step_folds_it_to_corrupt_like_release_sh(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:01Z", "bump", "ok", "3s") + "\n"
                   + '{"ts":"2026-09-05T10:00:02Z","run":"1.0.0","step":"build-all","status":"o\n')
        m = self.t.model()
        self.assertEqual(stations(m)["build-all"], "corrupt")
        self.assertTrue(any("corrupt" in n["what"] for n in m["confounded"]["new_shape"]))

    def test_partial_last_line_naming_a_step_folds_to_corrupt(self):
        # A write in progress is not read as an event — but release.sh's own fold
        # treats a fragment naming a step as corrupt, and the board matches it
        # rather than drawing the step as untouched (review, 5 Sep 2026).
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:01Z", "bump", "running", "attempt 1"))  # no trailing newline
        m = self.t.model()
        self.assertTrue(m["line"]["ledger_partial"])
        self.assertEqual(stations(m)["bump"], "corrupt")

    def test_partial_last_line_naming_no_step_is_just_partial(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + '{"ts":"2026-09-05T10:00:01Z","ru')
        m = self.t.model()
        self.assertTrue(m["line"]["ledger_partial"])
        self.assertTrue(all(s in ("pending", "later") for s in stations(m).values()), stations(m))

    def test_steps_tbl_problems_reach_the_confounded_log(self):
        self.t.run(steps="# steps.tbl v9\nbump|bump|plain|1m|||x\nshort|only|three\n", events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
        c = self.t.model()["confounded"]
        self.assertTrue(any("version stamp" in u["what"] for u in c["unknown"]), c["unknown"])
        self.assertTrue(any("not 7" in u["what"] for u in c["unknown"]), c["unknown"])

    def test_skipped_later_unknown_and_not_in_this_run(self):
        self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"),
                                     ev("2026-09-05T10:00:01Z", "preflight", "skipped", "--skip"),
                                     ev("2026-09-05T10:00:02Z", "bump", "ok", "1s"),
                                     ev("2026-09-05T10:00:03Z", "ci-green", "ok", "2s"),
                                     ev("2026-09-05T10:00:04Z", "run", "completed")]) + "\n")
        m = self.t.model()
        st = stations(m)
        self.assertEqual(st["preflight"], "skipped")
        self.assertEqual(st["snap-stable"], "later")
        self.assertEqual(st["build-all"], "not-in-this-run")
        self.assertEqual(m["line"]["unknown_steps"], ["ci-green"])
        self.assertTrue(any("ci-green" in u["what"] for u in m["confounded"]["unknown"]))
        self.assertTrue(any("build-all" in x["what"] for x in m["confounded"]["missing"]))
        self.assertEqual(m["phase"], "completed")

    def test_tier_two_step_reads_later_even_while_the_run_is_in_progress(self):
        # snap-stable is a tier-2 step: it runs after publish, on its own. On a
        # run still in progress it is "later", not "pending" — pending would
        # promise the driver is about to reach it.
        self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"),
                                     ev("2026-09-05T10:00:01Z", "bump", "ok", "1s")]) + "\n")
        self.assertEqual(stations(self.t.model())["snap-stable"], "later")

    def test_no_steps_tbl_falls_back_to_ledger_order_and_says_so(self):
        self.t.run(steps=None, events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"),
                                                 ev("2026-09-05T10:00:01Z", "zeta", "ok", "1s"),
                                                 ev("2026-09-05T10:00:02Z", "alpha", "ok", "1s")]) + "\n")
        m = self.t.model()
        self.assertEqual([s["id"] for s in m["line"]["stations"]], ["zeta", "alpha"])
        self.assertEqual(m["line"]["source"], "ledger")
        self.assertFalse(m["confounded"]["computable"])


class NoData(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_empty_run_dir_renders_every_tile_no_data_and_exits_0(self):
        self.t.run(events="")
        m = self.t.model()
        self.assertEqual(m["preflight"]["state"], "no-data")
        self.assertEqual([ln["state"] for ln in m["build"]["lanes"]], ["not-run"])  # one build-*.sh in STEPS
        self.assertEqual(m["ci"]["state"], "not-queried")
        self.assertTrue(all(c["state"] in ("no-data", "skipped") for c in m["channels"]["cards"]))
        self.assertEqual(m["clocks"], [])
        self.assertFalse(m["sink"]["present"])
        r = self.t.cli("1.0.0", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_run_dir_exits_1(self):
        r = self.t.cli("9.9.9", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no run dir", r.stderr)

    def test_no_runs_at_all_exits_1(self):
        r = self.t.cli("--json")
        self.assertEqual(r.returncode, 1)

    def test_malformed_version_exits_2(self):
        r = self.t.cli("../etc", "--json")
        self.assertEqual(r.returncode, 2)

    def test_newest_run_is_chosen_and_narrated(self):
        import time
        self.t.run("1.0.0", events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
        time.sleep(0.05)
        self.t.run("1.1.0", events=ev("2026-09-05T11:00:00Z", "run", "started") + "\n")
        os.utime(self.t.root / ".release" / "1.1.0" / "events.jsonl", None)
        r = self.t.cli("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["version"], "1.1.0")
        self.assertIn("using the newest", r.stderr)

    def test_build_ran_but_sink_received_nothing_is_named(self):
        sink = "@bn run ts=2026-09-05T10:00:00Z run=1.0.0 status=start attempt=1 proto=1\n" \
               "@bn step ts=2026-09-05T10:00:01Z run=1.0.0 id=build-all attempt=1 status=start\n" \
               "@bn step ts=2026-09-05T10:05:00Z run=1.0.0 id=build-all attempt=1 status=end rc=0 elapsed=299\n"
        self.t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"), ev("2026-09-05T10:00:01Z", "build-all", "running", "attempt 1"),
                                     ev("2026-09-05T10:05:00Z", "build-all", "ok", "299s")]) + "\n", sink=sink)
        m = self.t.model()
        lane = [ln for ln in m["build"]["lanes"] if ln["id"] == "build-all"][0]
        self.assertEqual(lane["state"], "ran-no-sink")
        # no previous run, no children ever: the lane is named, not counted as
        # missing — LaneEmission covers the case where the script is known to emit
        self.assertFalse(lane["emits_known"])
        self.assertFalse(any("zero child lines" in x["what"] for x in m["confounded"]["missing"]))

    def test_build_with_child_lines_has_data(self):
        sink = "@bn step ts=2026-09-05T10:00:01Z run=1.0.0 id=build-all attempt=1 status=start\n" \
               "@bn step ts=2026-09-05T10:00:02Z run=1.0.0 id=1 phase=Pre-flight name=Pre-flight status=start\n" \
               "@bn check ts=2026-09-05T10:00:03Z run=1.0.0 parent=1 result=ok label=logging\\ hygiene evidence=clean\n" \
               "@bn step ts=2026-09-05T10:00:04Z run=1.0.0 id=1 status=ok elapsed=2 detail=fine\n" \
               "@bn gate ts=2026-09-05T10:00:05Z run=1.0.0 id=a result=ok desc=staple evidence=stapled\n" \
               "@bn step ts=2026-09-05T10:05:00Z run=1.0.0 id=build-all attempt=1 status=end rc=0 elapsed=299\n"
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:05:00Z", "build-all", "ok", "299s") + "\n", sink=sink)
        lane = [ln for ln in self.t.model()["build"]["lanes"] if ln["id"] == "build-all"][0]
        self.assertEqual(lane["state"], "data")
        self.assertEqual(lane["steps"][0]["state"], "ok")
        self.assertEqual(lane["steps"][0]["elapsed"], 2.0)
        self.assertEqual(lane["checks"][0]["label"], "logging hygiene")
        self.assertEqual(lane["gates"][0]["id"], "a")


class Preflight(unittest.TestCase):
    def test_repeated_label_inside_one_driver_window_is_one_batch(self):
        t = Tree()
        try:
            sink = ("@bn step ts=2026-09-05T10:00:00Z run=1.0.0 id=preflight attempt=1 status=start\n"
                    "@bn row ts=2026-09-05T10:00:01Z run=1.0.0 src=preflight label=dependency\\ drift result=ok evidence=a\n"
                    "@bn row ts=2026-09-05T10:00:02Z run=1.0.0 src=preflight label=dependency\\ drift result=warn evidence=b\n"
                    "@bn step ts=2026-09-05T10:00:03Z run=1.0.0 id=preflight attempt=1 status=end rc=0 elapsed=3\n")
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:03Z", "preflight", "ok", "3s") + "\n", sink=sink)
            pf = t.model()["preflight"]
            self.assertEqual(pf["state"], "data")
            self.assertEqual(len(pf["rows"]), 2, pf)
        finally:
            t.close()

    def test_window_with_no_rows_is_ran_no_sink(self):
        t = Tree()
        try:
            sink = ("@bn step ts=2026-09-05T10:00:00Z run=1.0.0 id=preflight attempt=1 status=start\n"
                    "@bn step ts=2026-09-05T10:00:03Z run=1.0.0 id=preflight attempt=1 status=end rc=0 elapsed=3\n")
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
            self.assertEqual(t.model()["preflight"]["state"], "ran-no-sink")
        finally:
            t.close()


class Channels(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def verify(self, rows, done=True):
        s = "@bn verify ts=2026-09-05T12:00:00Z run=1.0.0 status=start version=1.0.0\n"
        for i, (label, res) in enumerate(rows):
            s += f"@bn row ts=2026-09-05T12:00:0{i+1}Z run=1.0.0 src=verify label={label} result={res} evidence=probe\n"
        if done:
            s += f"@bn verify ts=2026-09-05T12:00:09Z run=1.0.0 status=done version=1.0.0 rollup=0 channels={len(rows)} ok={sum(1 for _, r in rows if r == 'ok')}\n"
        return s

    def test_every_channel_in_conf_has_a_card_and_unreachable_is_not_ok(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=self.verify([("pypi", "ok"), ("github", "unreachable"), ("testflight", "skipped")]))
        m = self.t.model()
        cards = {c["name"]: c["state"] for c in m["channels"]["cards"]}
        self.assertEqual(cards, {"pypi": "ok", "github": "unreachable", "testflight": "skipped"})
        self.assertTrue(m["channels"]["complete"])
        self.assertEqual(m["channels"]["rollup"]["rc"], "0")

    def test_partial_verify_is_never_rolled_up(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=self.verify([("pypi", "ok")], done=False))
        m = self.t.model()
        self.assertFalse(m["channels"]["complete"])
        self.assertIsNone(m["channels"]["rollup"])
        self.assertEqual(m["channels"]["partial_rows"], 1)
        self.assertFalse(any("channel" in x["what"] for x in m["confounded"]["missing"]))  # incomplete → no "missing" claim

    def test_channel_absent_from_complete_verify_is_missing(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=self.verify([("pypi", "ok")]))
        m = self.t.model()
        self.assertTrue(any("github" in x["what"] for x in m["confounded"]["missing"]))

    def test_verify_of_another_version_is_not_this_runs_truth(self):
        s = self.verify([("pypi", "ok"), ("github", "ok"), ("testflight", "ok")]).replace("version=1.0.0", "version=2.0.0")
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=s)
        m = self.t.model()
        self.assertEqual(m["channels"]["version_mismatch"], "2.0.0")
        self.assertFalse(m["channels"]["complete"])
        self.assertTrue(all(c["state"] in ("no-data", "skipped") for c in m["channels"]["cards"]))
        self.assertTrue(any("2.0.0" in n["what"] for n in m["confounded"]["new_shape"]))

    def test_channels_as_of_is_the_batch_not_the_sink(self):
        s = self.verify([("pypi", "ok")]) + "@bn meta ts=2026-09-06T00:00:00Z run=1.0.0 title=later\n"
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=s)
        self.assertEqual(self.t.model()["channels"]["as_of"], "2026-09-05T12:00:09Z")

    def test_unprobeable_channel_with_no_verify_reads_skipped_with_reason(self):
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
        c = {c["name"]: c for c in self.t.model()["channels"]["cards"]}
        self.assertEqual(c["testflight"]["state"], "skipped")
        self.assertEqual(c["pypi"]["state"], "no-data")


class Clocks(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_empty_testflight_expiry_is_no_data_never_computed(self):
        sink = "@bn clock ts=2026-09-05T12:00:00Z run=1.0.0 name=testflight build=3070 expires= confirmed=0\n"
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
        k = self.t.model()["clocks"][0]
        self.assertEqual(k["state"], "no-data")
        self.assertIsNone(k["expires"])

    def test_unknown_clock_name_is_a_new_shape(self):
        sink = "@bn clock ts=2026-09-05T12:00:00Z run=1.0.0 name=frob expires=2026-10-01T00:00:00Z\n"
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
        c = self.t.model()["confounded"]
        self.assertTrue(any("clock.name = 'frob'" in n["what"] for n in c["new_shape"]), c["new_shape"])

    def test_dmg_expiry_is_built_plus_rule_and_rule_matches_swift(self):
        sink = "@bn clock ts=2026-09-05T12:00:00Z run=1.0.0 name=dmg version=1.0.0 built=2026-09-05T11:00:00Z commit=abc\n"
        self.t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
        k = self.t.model()["clocks"][0]
        self.assertEqual(k["expires"], "2026-10-05T11:00:00Z")
        swift = (ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "AlphaBuild.swift").read_text()
        m = re.search(r"static let validityDays = (\d+)", swift)
        self.assertIsNotNone(m, "AlphaBuild.swift no longer declares validityDays — the board's mirror has lost its source")
        self.assertEqual(int(m.group(1)), rb.DMG_VALIDITY_DAYS)


class Merge(unittest.TestCase):
    def test_same_second_ties_order_ledger_before_sink_then_by_line(self):
        t = Tree()
        try:
            sink = "@bn step ts=2026-09-05T10:00:01Z run=1.0.0 id=bump attempt=1 status=start\n@bn meta ts=2026-09-05T10:00:01Z run=1.0.0 title=x\n"
            t.run(events=ev("2026-09-05T10:00:01Z", "bump", "running", "attempt 1") + "\n" + ev("2026-09-05T10:00:01Z", "run", "started") + "\n", sink=sink)
            rows = t.model()["events"]
            self.assertEqual([r["src"] for r in rows], ["ledger", "ledger", "step", "meta"])
            self.assertEqual(rows[0]["text"].split()[0], "bump")  # ledger line 1 before ledger line 2
        finally:
            t.close()


class Activity(unittest.TestCase):
    def test_long_span_bins_adaptively_and_drops_nothing(self):
        t = Tree()
        try:
            evs = [ev("2026-09-01T00:00:00Z", "run", "started")] + [ev(f"2026-09-0{d}T12:00:00Z", "bump", "ok", "1s") for d in range(1, 6)]
            t.run(events="\n".join(evs) + "\n")
            a = t.model()["activity"]
            self.assertLessEqual(len(a["minutes"]), 600)
            self.assertEqual(sum(a["minutes"]), 6)
            self.assertEqual(a["bin_minutes"], -(-a["span_minutes"] // 600))
            self.assertGreater(a["bin_minutes"], 1)
        finally:
            t.close()


class Ci(unittest.TestCase):
    def test_ci_lines_place_matrix_cells_and_flag_sha_mismatch(self):
        t = Tree()
        try:
            sha = "a" * 40
            sink = (f"@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha={sha} run_id=1 result=failure\n"
                    f"@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha={sha} run_id=1 job=test\\ \\(3.12\\,\\ macos-latest\\) result=failure\n"
                    f"@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha={sha} run_id=1 job=ruff result=success\n")
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink, extra={"ci-sha": "b" * 40})
            ci = t.model()["ci"]
            self.assertEqual(ci["state"], "data")
            self.assertEqual(ci["matrix"], [{"job": "test", "python": "3.12", "os": "macos", "result": "failure"}])
            self.assertEqual([j["matrix"] for j in ci["jobs"]], [True, False])
        finally:
            t.close()

    def test_ci_pane_makes_no_sha_claim(self):
        # `status` writes sha= from the same ci-sha file the board reads, so a
        # "matches" tick would compare a file with a copy of itself.
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n",
                  sink="@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha=abc run_id=1 result=success\n"
                       "@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha=abc run_id=1 job=ruff result=success\n", extra={"ci-sha": "a" * 40})
            ci = t.model()["ci"]
            self.assertNotIn("sha_matches", ci)
            self.assertEqual(ci["ci_sha"], "a" * 40)
            self.assertEqual([j["matrix"] for j in ci["jobs"]], [False])
        finally:
            t.close()

    def test_no_ci_lines_is_not_queried(self):
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
            self.assertEqual(t.model()["ci"]["state"], "not-queried")
        finally:
            t.close()


class Confounded(unittest.TestCase):
    def test_one_of_each_section_and_zero_on_a_clean_run(self):
        t = Tree()
        try:
            # previous run: one more step, one more channel
            prev_steps = STEPS + "old-step|old|plain|1m|||true\n"
            t.run("0.9.0", steps=prev_steps, events=ev("2026-09-01T10:00:00Z", "run", "started") + "\n",
                  sink="@bn row ts=2026-09-01T12:00:00Z run=0.9.0 src=verify label=pypi result=ok evidence=x\n"
                       "@bn row ts=2026-09-01T12:00:01Z run=0.9.0 src=verify label=github result=ok evidence=x\n")
            time.sleep(0.05)
            sink = ("@bn frobnicate ts=2026-09-05T10:00:00Z run=1.0.0 foo=bar\n"                       # unknown kind
                    "@bn row ts=2026-09-05T10:00:01Z run=1.0.0 src=preflight label=branch result=meh evidence=x\n"  # new shape
                    "@bn verify ts=2026-09-05T12:00:00Z run=1.0.0 status=start version=1.0.0\n"
                    "@bn row ts=2026-09-05T12:00:01Z run=1.0.0 src=verify label=pypi result=ok evidence=x\n"
                    "@bn verify ts=2026-09-05T12:00:09Z run=1.0.0 status=done version=1.0.0 rollup=0 channels=1 ok=1\n"   # github missing
                    "@bn check ts=t run=1.0.0 evidence=$'a\\nb it\\'s'\n")                                  # decodes, not unparsed
            t.run("1.0.0", events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
            os.utime(t.root / ".release" / "1.0.0" / "events.jsonl", None)
            c = t.model("1.0.0")["confounded"]
            self.assertTrue(c["computable"])
            self.assertTrue(any("frobnicate" in u["what"] for u in c["unknown"]), c["unknown"])
            self.assertTrue(any("row.result = 'meh'" in n["what"] for n in c["new_shape"]), c["new_shape"])
            self.assertTrue(any("github" in x["what"] for x in c["missing"]), c["missing"])
            self.assertTrue(any("old-step" in x["what"] and "removed" in x["what"] for x in c["changed"]), c["changed"])
            self.assertTrue(any("preflight row 'publish gate' absent" in x["what"] for x in c["missing"]))
            self.assertGreaterEqual(c["count"], 5)
            self.assertEqual(c["count"], sum(len(c[k]) for k in ("unknown", "new_shape", "missing", "changed")))
            # and a clean run reports zero
            t2 = Tree()
            try:
                t2.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
                c2 = t2.model()["confounded"]
                self.assertTrue(c2["computable"])
                self.assertEqual(c2["count"], 0)
            finally:
                t2.close()
        finally:
            t.close()


class LaneEmission(unittest.TestCase):
    def test_zero_child_lines_is_missing_only_for_a_script_known_to_emit(self):
        t = Tree()
        try:
            # previous run: build-all emitted children
            prev = ("@bn step ts=2026-09-01T10:00:01Z run=0.9.0 id=build-all attempt=1 status=start\n"
                    "@bn step ts=2026-09-01T10:00:02Z run=0.9.0 id=1 name=x status=start\n"
                    "@bn step ts=2026-09-01T10:00:03Z run=0.9.0 id=1 status=ok elapsed=1\n"
                    "@bn step ts=2026-09-01T10:00:04Z run=0.9.0 id=build-all attempt=1 status=end rc=0 elapsed=3\n")
            t.run("0.9.0", events=ev("2026-09-01T10:00:00Z", "run", "started") + "\n", sink=prev)
            time.sleep(0.05)
            steps = STEPS + "build-dmg|build the dmg|plain|5m|||desktop/scripts/build-dmg.sh\n"
            now = ("@bn step ts=2026-09-05T10:00:01Z run=1.0.0 id=build-all attempt=1 status=start\n"
                   "@bn step ts=2026-09-05T10:00:04Z run=1.0.0 id=build-all attempt=1 status=end rc=0 elapsed=3\n"
                   "@bn step ts=2026-09-05T10:00:05Z run=1.0.0 id=build-dmg attempt=1 status=start\n"
                   "@bn step ts=2026-09-05T10:00:09Z run=1.0.0 id=build-dmg attempt=1 status=end rc=0 elapsed=4\n")
            t.run("1.0.0", steps=steps, events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:04Z", "build-all", "ok", "3s") + "\n"
                  + ev("2026-09-05T10:00:09Z", "build-dmg", "ok", "4s") + "\n", sink=now)
            os.utime(t.root / ".release" / "1.0.0" / "events.jsonl", None)
            m = t.model("1.0.0")
            self.assertEqual(m["build"]["lane_ids"], ["build-all", "build-dmg"])
            lanes = {ln["id"]: ln for ln in m["build"]["lanes"]}
            self.assertEqual(lanes["build-all"]["state"], "ran-no-sink")
            self.assertTrue(lanes["build-all"]["emits_known"])
            self.assertFalse(lanes["build-dmg"]["emits_known"])
            missing = [x["what"] for x in m["confounded"]["missing"] if "zero child lines" in x["what"]]
            self.assertEqual(len(missing), 1, missing)
            self.assertIn("build-all", missing[0])
        finally:
            t.close()

    def test_lane_says_whether_its_source_reports_steps_and_where_its_output_went(self):
        t = Tree()
        try:
            (t.root / "desktop" / "scripts").mkdir(parents=True)
            (t.root / "desktop" / "scripts" / "build-all.sh").write_text("#!/bin/bash\nsource report.sh\nbn_autowrap \"$0\"\n")
            (t.root / "desktop" / "scripts" / "build-dmg.sh").write_text("#!/bin/bash\necho plain\n")
            steps = STEPS + "build-dmg|build the dmg|plain|5m|||desktop/scripts/build-dmg.sh\n"
            t.run(steps=steps, events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:04Z", "build-all", "ok", "3s") + "\n"
                  + ev("2026-09-05T10:00:09Z", "build-dmg", "ok", "4s") + "\n",
                  extra={"logs/build-all.1.log": "x" * 300, "logs/build-all.2.log": "y" * 500, "logs/build-dmg.1.log": "z" * 10})
            lanes = {ln["id"]: ln for ln in t.model()["build"]["lanes"]}
            self.assertTrue(lanes["build-all"]["source_emits"])
            self.assertFalse(lanes["build-dmg"]["source_emits"])
            self.assertEqual(lanes["build-all"]["log"]["attempts"], 2)
            self.assertEqual(lanes["build-all"]["log"]["size"], 500)
            self.assertTrue(lanes["build-all"]["log"]["path"].endswith("logs/build-all.2.log"))
            self.assertNotIn("tail", lanes["build-all"]["log"])
        finally:
            t.close()

    def test_skipped_and_failed_lanes_have_their_own_states(self):
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:01Z", "build-all", "skipped", "--skip") + "\n")
            self.assertEqual([ln["state"] for ln in t.model()["build"]["lanes"] if ln["id"] == "build-all"], ["skipped"])
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:01Z", "build-all", "fail", "exit 1") + "\n")
            self.assertEqual([ln["state"] for ln in t.model()["build"]["lanes"] if ln["id"] == "build-all"], ["failed-no-window"])
        finally:
            t.close()


class Links(unittest.TestCase):
    def test_links_are_https_from_conf_and_validated_ids_only(self):
        t = Tree()
        try:
            (t.root / "scripts" / "project.conf").write_text(CONF + 'GH_REPO="o/r"\nTAP_REPO="o/homebrew-r"\nSITE="x.app"\nCOPR_OWNER="o"\nCOPR_PROJECT="${PROJECT_NAME}"\nCHANGELOG_URL="https://${SITE}/docs/changelog.html"\n')
            sink = ("@bn ci ts=2026-09-05T12:00:00Z run=1.0.0 workflow=ci.yml sha=javascript:alert(1) run_id=12 result=success\n"
                    "@bn ci ts=2026-09-05T12:00:01Z run=1.0.0 workflow=release.yml sha=abcdef0123456789abcdef0123456789abcdef01 run_id=../x result=success\n")
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink, extra={"ci-sha": "a" * 40})
            m = t.model()
            links = m["links"]
            self.assertEqual(links["channels"]["pypi"], "https://pypi.org/project/bristlenose/1.0.0/")
            self.assertEqual(links["channels"]["copr"], "https://copr.fedorainfracloud.org/coprs/o/bristlenose/")
            self.assertEqual(links["channels"]["website"], "https://x.app/docs/changelog.html")
            self.assertEqual(links["ci_sha"], "https://github.com/o/r/commit/" + "a" * 40)
            self.assertEqual(links["tag"], "https://github.com/o/r/releases/tag/v1.0.0")
            self.assertTrue(all(v.startswith("https://") for v in links["channels"].values()))
            runs = {r["workflow"]: r for r in m["ci"]["runs"]}
            self.assertIsNone(runs["ci.yml"]["sha_url"])      # not a sha
            self.assertEqual(runs["ci.yml"]["url"], "https://github.com/o/r/actions/runs/12")
            self.assertIsNone(runs["release.yml"]["url"])     # not a run id
            self.assertTrue(runs["release.yml"]["sha_url"].endswith("/commit/abcdef0123456789abcdef0123456789abcdef01"))
            self.assertEqual({c["name"]: bool(c["url"]) for c in m["channels"]["cards"]}, {"pypi": True, "github": True, "testflight": True})
        finally:
            t.close()

    def test_template_sets_href_in_exactly_one_place(self):
        code = TEMPLATE.read_text().split("<script>", 1)[1]
        self.assertEqual(len(re.findall(r"\.href\s*=", code)), 1)


class _ScriptGrabber(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_data = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script" and ("id", "board-data") in attrs:
            self.in_data = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, d):
        if self.in_data:
            self.data += d


class Html(unittest.TestCase):
    def test_inlined_block_round_trips_and_escapes_script_breakout(self):
        t = Tree()
        try:
            sink = "@bn row ts=2026-09-05T10:00:01Z run=1.0.0 src=preflight label=branch result=ok evidence='</script><script>alert(1)</script>'\n"
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
            model = t.model()
            html = rb.render_html(model, TEMPLATE)
            self.assertIn("\\u003c/script\\u003e", html)
            self.assertEqual(html.count("</script>"), 2, "only the template's own two script tags may close")  # data block + renderer
            g = _ScriptGrabber()
            g.feed(html)
            self.assertEqual(json.loads(g.data), model)
        finally:
            t.close()

    def test_template_has_no_dom_sinks(self):
        tpl = TEMPLATE.read_text()
        code = tpl.split("<script>", 1)[1]  # the renderer, not the comment block above it
        for name in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write"):
            self.assertIsNone(re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", code), f"{name} in the renderer")

    def test_canary_context_never_reaches_the_board(self):
        t = Tree()
        try:
            ctx = {"os": "macOS", "host": "CANARY-HOST", "env": {"SIGN_IDENTITY_APPSTORE": "CANARY-IDENTITY"}, "git": {"sha": "abc", "branch": "main"}}
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", extra={"context.json": json.dumps(ctx)})
            html = rb.render_html(t.model(), TEMPLATE)
            self.assertNotIn("CANARY-HOST", html)
            self.assertNotIn("CANARY-IDENTITY", html)
            self.assertIn("macOS", html)
        finally:
            t.close()

    def test_canary_sink_identity_and_home_never_reach_the_board(self):
        t = Tree()
        try:
            home = str(Path.home())
            sink = ("@bn meta ts=2026-09-05T10:00:00Z run=1.0.0 title=x identity=Developer\\ ID\\ Application:\\ CANARY-NAME\\ \\(ABCDE12345\\)\n"
                    f"@bn art ts=2026-09-05T10:00:01Z run=1.0.0 key=dmg value={home}/CANARY-DIR/x.dmg\n"
                    "@bn gate ts=2026-09-05T10:00:02Z run=1.0.0 id=g result=ok desc=sign evidence=references\\ Team\\ ABCDE12345\n")
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n", sink=sink)
            html = rb.render_html(t.model(), TEMPLATE)
            self.assertNotIn("CANARY-NAME", html)
            self.assertNotIn("ABCDE12345", html)
            self.assertNotIn(home, html)
            self.assertIn("CANARY-DIR", html)  # the path survives, rooted at ~
        finally:
            t.close()

    def test_click_map_names_real_stations_and_real_panes(self):
        tpl = TEMPLATE.read_text()
        m = re.search(r"var CLICK_MAP = (\{[^\n]*\});", tpl)
        self.assertIsNotNone(m)
        click = json.loads(m.group(1))
        station_ids = {ln.split("|")[0] for ln in (FIXTURE / "steps.tbl").read_text().splitlines() if ln and not ln.startswith("#")}
        self.assertTrue(set(click) <= station_ids, set(click) - station_ids)
        panes = set(re.findall(r'panel\("([a-z-]+)"', tpl))
        self.assertTrue(set(click.values()) <= panes, set(click.values()) - panes)

    def test_template_lays_out_three_columns_with_two_gutters_and_the_band(self):
        tpl = TEMPLATE.read_text()
        code = tpl.split("<script>", 1)[1]
        for token in ('"gutter-"+(a === 0 ? "tag" : "stream")', 'panel("log"', 'panel("events"', 'band.id = "pane-activity"', "--c3"):
            self.assertIn(token, code, token)
        self.assertNotIn('panel("activity"', code, "activity is the band under the line, not a pane")
        # dim = inputs not written yet; anything that happened stays full contrast
        self.assertIn(".panel.idle", tpl)
        self.assertIn('idle(pfP, pf.state === "no-data")', code)
        self.assertNotIn('idle(bp, lane.state !== "data")', code, "ran-no-sink and failed lanes must not be dimmed")
        self.assertIn("minmax(0,var(--c1,1fr)) 14px minmax(0,var(--c2,1fr)) 14px minmax(0,var(--c3,1.25fr))", tpl)
        self.assertNotIn('+"px")', code, "column widths persist as fractions, never pixels — a saved layout must fit any window")

    def test_replay_is_the_real_generator_on_ledger_prefixes(self):
        t = Tree()
        try:
            t.run(events="\n".join([ev("2026-09-05T10:00:00Z", "run", "started"),
                                     ev("2026-09-05T10:00:01Z", "bump", "running", "attempt 1"),
                                     ev("2026-09-05T10:00:05Z", "bump", "ok", "4s")]) + "\n",
                  sink="@bn meta ts=2026-09-05T10:00:02Z run=1.0.0 title=x\n@bn meta ts=2026-09-05T11:00:00Z run=1.0.0 title=late\n")
            out = t.root / "replay"
            r = t.cli("1.0.0", "--replay", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((out / "board.html").exists())
            g = _ScriptGrabber()
            g.feed((out / "board-replay.html").read_text())
            frames = json.loads(g.data)["replay"]
            self.assertEqual([f["i"] for f in frames], [0, 1, 2, 3])
            st = [stations(f["model"]) for f in frames]
            self.assertEqual(st[0]["bump"], "pending")
            self.assertEqual(st[2]["bump"], "running")   # liveness assumed while a prefix leaves it running
            self.assertTrue(frames[2]["model"]["liveness"]["replay"])
            self.assertEqual(st[3]["bump"], "ok")
            self.assertEqual(frames[2]["model"]["sink"]["events"], 0)  # the 10:00:02 line is after frame 2's 10:00:01
            self.assertEqual(frames[3]["model"]["sink"]["events"], 1)  # …and within frame 3; the 11:00 line never lands
            self.assertIn("bump ok", frames[3]["caption"])
        finally:
            t.close()

    def test_json_flag_prints_what_the_file_would_hold_and_out_dir_is_honoured(self):
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
            out = t.root / "elsewhere"
            r = t.cli("1.0.0", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((out / "board.html").is_file() and (out / "board.json").is_file())
            self.assertFalse((t.root / ".release" / "1.0.0" / "board.html").exists())
            j = t.cli("1.0.0", "--json")
            a = json.loads(j.stdout)
            b = json.loads((out / "board.json").read_text())
            a.pop("generated")
            b.pop("generated")
            self.assertEqual(a, b)
            w = t.cli("1.0.0", "--out", str(out), "--with-logs")
            self.assertEqual(w.returncode, 0, w.stderr)
            self.assertTrue((out / "board-with-logs.json").is_file())
            self.assertFalse(json.loads((out / "board.json").read_text())["header"]["with_logs"])
        finally:
            t.close()

    def test_logs_are_paths_only_unless_with_logs(self):
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n" + ev("2026-09-05T10:00:01Z", "bump", "fail", "exit 1") + "\n",
                  extra={"logs/bump.1.log": "\x1b[31mCANARY-LOG-LINE\x1b[0m --apiKey SECRET\n"})
            plain = rb.render_html(t.model(with_logs=False), TEMPLATE)
            self.assertNotIn("CANARY-LOG-LINE", plain)
            self.assertIn("bump.1.log", plain)
            with_logs = rb.render_html(t.model(with_logs=True), TEMPLATE)
            self.assertIn("CANARY-LOG-LINE", with_logs)
            self.assertNotIn("\\u001b", with_logs)  # ANSI stripped
        finally:
            t.close()

    def test_output_files_are_private(self):
        t = Tree()
        try:
            t.run(events=ev("2026-09-05T10:00:00Z", "run", "started") + "\n")
            r = t.cli("1.0.0")
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ("board.html", "board.json"):
                self.assertEqual(oct((t.root / ".release" / "1.0.0" / name).stat().st_mode & 0o777), "0o600")
            # and never through a symlink
            os.remove(t.root / ".release" / "1.0.0" / "board.html")
            victim = t.root / "victim"
            victim.write_text("keep")
            os.symlink(victim, t.root / ".release" / "1.0.0" / "board.html")
            r = t.cli("1.0.0")
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(victim.read_text(), "keep")
        finally:
            t.close()


class RealRun(unittest.TestCase):
    """The committed copy of the real 0.28.0 ledger: fail, retry, skip, resume, no context.json.
    steps.tbl in the fixture is RECONSTRUCTED (the driver did not write one in
    0.28.0) — see the fixture's README."""

    def test_the_0_28_0_fixture_by_name(self):
        t = Tree()
        try:
            d = t.root / ".release" / "0.28.0"
            shutil.copytree(FIXTURE, d)
            m = t.model("0.28.0")
            st = stations(m)
            self.assertEqual(m["phase"], "completed")
            self.assertEqual(m["header"]["attempts"], 7)
            self.assertEqual(m["header"]["context"], None)
            self.assertEqual(st["testflight"], "skipped")
            self.assertEqual(st["build-dmg"], "ok")
            self.assertEqual([s for s in m["line"]["stations"] if s["id"] == "build-dmg"][0]["attempt"], 2)
            self.assertEqual(st["dmg"], "ok")
            self.assertEqual(st["snap-stable"], "later")
            self.assertEqual(m["header"]["ci_sha"], "df8a068ae5f61b99a68c844705cbe073a7864ce1")
            self.assertEqual([ln["state"] for ln in m["build"]["lanes"]], ["ran-no-sink", "ran-no-sink"])
            self.assertEqual(m["preflight"]["state"], "no-data")
            self.assertTrue(m["confounded"]["computable"])
            self.assertEqual(m["confounded"]["count"], 0)
        finally:
            t.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)
