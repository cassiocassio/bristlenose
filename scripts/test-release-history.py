#!/usr/bin/env python3
"""test-release-history.py — the History tab's model, against synthetic ledgers.

    .venv/bin/python scripts/test-release-history.py

release-stats.py's `history()` turns every `.release/*/events.jsonl` into one
record per invocation: where it ENTERED (a resume enters mid-line) and how it
EXITED (fail / stopped / skipped / completed). The board draws those records
and nothing else, so a wrong exit here is a wrong chart there, silently. Each
case below is a shape a real ledger has: 0.28.0's "completed" over an eaten
step table, 0.31.3's skipped irreversible block, 0.34.0's stopped mid-step
resume, the renamed stopped-attempt dirs, a verify pass that later reads bad
because the next release moved the channel on.

stdlib unittest; no network. git is asked for release-machine commits, and a
root that is not a repo must answer None (not computable), never [].
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


rs = _load("release_stats", ROOT / "scripts" / "release-stats.py")


def ev(ts: str, run: str, step: str, status: str, detail: str = "") -> str:
    return json.dumps({"ts": f"2026-10-01T{ts}Z", "run": run, "step": step, "status": status, "detail": detail})


def ran(ts: str, run: str, step: str, attempt: int = 1, ok: bool = True) -> list[str]:
    out = [ev(ts, run, step, "running", f"attempt {attempt}")]
    if ok:
        out.append(ev(ts, run, step, "ok", "1s"))
    return out


class History(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        rs._HISTORY_CACHE.clear()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, dirname: str, lines: list[str], sink: str | None = None) -> Path:
        d = self.root / ".release" / dirname
        (d / "logs").mkdir(parents=True, exist_ok=True)
        (d / "events.jsonl").write_text("\n".join(lines) + "\n")
        if sink is not None:
            (d / "bn-events.log").write_text(sink)
        return d

    def invs(self, version: str) -> list[dict]:
        rel = next(r for r in rs.history(self.root)["releases"] if r["version"] == version)
        return rel["invocations"]

    def test_a_clean_run_enters_at_preflight_and_completes(self):
        lines = [ev("01:00:00", "1.0.0", "run", "started")]
        for s in rs.STEP_ORDER:
            lines += ran("01:00:01", "1.0.0", s)
        lines.append(ev("01:00:02", "1.0.0", "run", "completed"))
        self.write("1.0.0", lines)
        (inv,) = self.invs("1.0.0")
        self.assertEqual(inv["entry"], "preflight")
        self.assertEqual(inv["exit"]["kind"], "completed")

    def test_a_resume_enters_where_it_picked_up_and_the_failure_carries_its_class(self):
        d = self.write("1.0.0", [
            ev("01:00:00", "1.0.0", "run", "started"),
            *ran("01:00:01", "1.0.0", "preflight"),
            *ran("01:00:02", "1.0.0", "build-all", ok=False),
            ev("01:00:03", "1.0.0", "build-all", "fail", "exit 1 class=dep-drift"),
            ev("01:10:00", "1.0.0", "run", "started"),
            *ran("01:10:01", "1.0.0", "build-all", attempt=2),
        ])
        (d / "logs" / "build-all.1.log").write_text("x\n")
        first, second = self.invs("1.0.0")
        self.assertEqual((first["entry"], first["exit"]["kind"], first["exit"]["step"], first["exit"]["class"]),
                         ("preflight", "fail", "build-all", "dep-drift"))
        self.assertEqual(second["entry"], "build-all", "a resumed run enters mid-line, not at preflight")
        self.assertEqual(second["exit"]["kind"], "stopped", "a ledger that just ends is stopped, not completed")

    def test_completed_over_an_unfinished_table_is_a_stop(self):
        # 0.28.0, incident 22: `run completed` written after dmg, tag and snap never read
        lines = [ev("01:00:00", "1.0.0", "run", "started")]
        for s in rs.STEP_ORDER[:rs.STEP_ORDER.index("dmg") + 1]:
            lines += ran("01:00:01", "1.0.0", s)
        lines.append(ev("01:00:02", "1.0.0", "run", "completed"))
        self.write("1.0.0", lines)
        (inv,) = self.invs("1.0.0")
        self.assertEqual(inv["exit"]["kind"], "stopped")
        self.assertTrue(inv["exit"]["claimed_complete"])

    def test_a_skipped_tag_is_a_stop_but_a_skipped_act_already_done_is_not(self):
        skip = [ev("01:00:00", "1.0.0", "run", "started"), *ran("01:00:01", "1.0.0", "preflight")]
        skip += [ev("01:00:02", "1.0.0", "tag", "skipped", "--skip"), ev("01:00:03", "1.0.0", "run", "completed")]
        self.write("1.0.0", skip)
        self.assertEqual(self.invs("1.0.0")[0]["exit"]["kind"], "skipped")
        done = [ev("02:00:00", "2.0.0", "run", "started"), ev("02:00:01", "2.0.0", "testflight", "skipped", "--skip")]
        done += ran("02:00:02", "2.0.0", "tag") + ran("02:00:03", "2.0.0", "snap") + [ev("02:00:04", "2.0.0", "run", "completed")]
        self.write("2.0.0", done)
        self.assertEqual(self.invs("2.0.0")[0]["exit"]["kind"], "completed")

    def test_stopped_mid_step_is_distinguished_from_stopped_between_steps(self):
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started"), *ran("01:00:01", "1.0.0", "build-dmg", ok=False)])
        self.assertTrue(self.invs("1.0.0")[0]["exit"]["mid_step"])
        self.write("2.0.0", [ev("02:00:00", "2.0.0", "run", "started"), *ran("02:00:01", "2.0.0", "build-dmg")])
        self.assertFalse(self.invs("2.0.0")[0]["exit"]["mid_step"])

    def test_renamed_dirs_group_by_the_ledgers_run_field(self):
        self.write("1.0.0-stopped-24sep", [ev("01:00:00", "1.0.0", "run", "started"), *ran("01:00:01", "1.0.0", "preflight")])
        self.write("1.0.0", [ev("03:00:00", "1.0.0", "run", "started"), *ran("03:00:01", "1.0.0", "preflight")])
        h = rs.history(self.root)
        self.assertEqual([r["version"] for r in h["releases"]], ["1.0.0"])
        self.assertEqual([i["dir"] for i in self.invs("1.0.0")], ["1.0.0-stopped-24sep", "1.0.0"])

    def test_a_channel_is_reached_if_any_verify_pass_saw_it_ok(self):
        sink = "\n".join([
            "@bn verify ts=2026-10-01T04:00:00Z run=1.0.0 status=start version=1.0.0",
            "@bn row ts=2026-10-01T04:00:00Z run=1.0.0 src=verify label=copr result=bad evidence=building",
            "@bn row ts=2026-10-01T04:00:00Z run=1.0.0 src=verify label=pypi result=ok evidence=200",
            "@bn verify ts=2026-10-01T04:00:01Z run=1.0.0 status=done version=1.0.0",
            "@bn verify ts=2026-10-01T05:00:00Z run=1.0.0 status=start version=1.0.0",
            "@bn row ts=2026-10-01T05:00:00Z run=1.0.0 src=verify label=copr result=ok evidence=1.0.0",
            # a later pass reads pypi bad only because the NEXT release moved it on
            "@bn row ts=2026-10-01T05:00:00Z run=1.0.0 src=verify label=pypi result=bad evidence=2.0.0",
            "@bn verify ts=2026-10-01T05:00:01Z run=1.0.0 status=done version=1.0.0",
            # a pass with no `done` is never rolled up
            "@bn verify ts=2026-10-01T06:00:00Z run=1.0.0 status=start version=1.0.0",
            "@bn row ts=2026-10-01T06:00:00Z run=1.0.0 src=verify label=github result=ok evidence=x",
        ]) + "\n"
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started")], sink=sink)
        v = rs.history(self.root)["releases"][0]["verify"]
        self.assertEqual(v["passes"], 2)
        self.assertEqual((v["rows"]["copr"]["result"], v["rows"]["copr"]["pass"]), ("ok", 2))
        self.assertEqual((v["rows"]["pypi"]["result"], v["rows"]["pypi"]["pass"]), ("ok", 1))
        self.assertNotIn("github", v["rows"])

    def test_no_sink_is_no_record_not_zero(self):
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started")])
        self.assertIsNone(rs.history(self.root)["releases"][0]["verify"])

    def test_torn_lines_are_counted_not_dropped_silently(self):
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started"), '{"ts":"2026-10-01T01', "not json"])
        self.assertEqual(rs.history(self.root)["unparsed_lines"], 2)

    def test_a_root_git_cannot_answer_for_is_not_computable(self):
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started")])
        self.assertIsNone(rs.history(self.root)["machine_commits"])

    def test_the_board_carries_the_history_and_survives_a_bad_read(self):
        board = _load("release_board", ROOT / "scripts" / "release-board.py")
        self.write("1.0.0", [ev("01:00:00", "1.0.0", "run", "started")])
        self.assertEqual(len(board.history_pane(self.root)["releases"]), 1)
        broken = board.release_stats.history
        try:
            board.release_stats.history = lambda root: (_ for _ in ()).throw(ValueError("boom"))
            pane = board.history_pane(self.root)
        finally:
            board.release_stats.history = broken
        self.assertIn("boom", pane["error"])
        self.assertEqual(pane["releases"], [])

    def test_every_hand_kept_cause_names_an_invocation_shape(self):
        # CAUSES keys are "version#n"; a typo would attach a cause to nothing, silently
        import re
        for k in list(rs.CAUSES) + [f"{v}#0" for v in rs.UNLEDGERED]:
            self.assertRegex(k, r"^\d+\.\d+\.\d+#\d+$", k)
        for sha in rs.MACHINE_MILESTONES:
            self.assertTrue(re.fullmatch(r"[0-9a-f]{8}", sha), sha)


if __name__ == "__main__":
    unittest.main(verbosity=1)
