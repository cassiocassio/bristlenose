"""The home page's readers (scripts/home_lib.py): each source in its ok and no-data states, and the
specific ways a number could be wrong while looking right. No network, no private data: every
source is a fixture written here. Design: docs/private/design-home-dashboard.md section 3."""
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import home_lib as hl  # noqa: E402

NOW = 1795737600
FINISHED = "finished 11,222/11,222  passed 11,205  failed 5  error 0  skipped 5  xfailed 7  · 210 s"


def write(p: Path, text: str, mtime_s: float | None = None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mtime_s is not None:
        os.utime(p, (mtime_s, mtime_s))
    return p


# ---- release ------------------------------------------------------------------------------------

def board(batches=0, states=None, newest="2026-11-25T11:17:14Z", generated="2026-11-26T23:00:00Z", version="0.48.0"):
    names = ["pypi", "github", "homebrew", "testflight", "dmg", "snap", "copr", "website"]
    states = states or dict.fromkeys(names, "no-data")
    return {"version": version, "phase": "completed", "generated": generated,
            "header": {"newest_source": newest},
            "channels": {"batches": batches, "cards": [{"name": n, "state": states.get(n, "no-data")} for n in names]}}


def test_release_no_board_file_is_no_data(tmp_path):
    assert hl.read_release(tmp_path)["status"] == "nodata"


def test_release_as_of_is_the_newest_source_never_the_time_the_model_was_made(tmp_path):
    write(tmp_path / "release" / "board.json", json.dumps(board(generated="2099-01-01T00:00:00Z")))
    p = hl.read_release(tmp_path)
    assert p["status"] == "ok"
    assert p["as_of"] == hl.iso_z_to_epoch("2026-11-25T11:17:14Z")       # not the (far later) `generated`
    assert p["refreshable"] is False and p["max_age"] == 30 * 86400


def test_release_with_no_verify_batch_says_not_verified_and_counts_nothing_as_fine(tmp_path):
    write(tmp_path / "release" / "board.json", json.dumps(board(batches=0)))
    p = hl.read_release(tmp_path)
    assert any("not verified" in f for f in p["facts"]) and not any("of 8 channels verified" in f for f in p["facts"])
    assert all(s["state"] != "ok" for s in p["body"][1]["items"])


def test_release_counts_only_what_the_board_marked_ok(tmp_path):
    write(tmp_path / "release" / "board.json", json.dumps(board(batches=1, states={"pypi": "ok", "snap": "unreachable", "copr": "absent"})))
    p = hl.read_release(tmp_path)
    assert any("1 of 8 channels verified" in f for f in p["facts"])
    st = {s["name"]: s for s in p["body"][1]["items"]}
    assert st["pypi"]["state"] == "ok" and st["copr"]["state"] == "bad" and st["snap"]["note"] == "could not look"


@pytest.mark.parametrize("model", [{}, {"version": "0.48.0"}, board(newest="2026-11-25 11:17:14"), board(newest="2026-11-25T11:17:14+01:00"),
                                   board(newest=None), board(version="not a version")])
def test_release_a_model_we_cannot_read_is_unknown_not_fresh(tmp_path, model):
    write(tmp_path / "release" / "board.json", json.dumps(model))
    p = hl.read_release(tmp_path)
    assert p["status"] == "unknown" and p["error"] == hl.ERR["unexpected"] and p["as_of"] is None


def test_release_link_exists_only_when_the_board_page_does(tmp_path):
    write(tmp_path / "release" / "board.json", json.dumps(board()))
    assert hl.read_release(tmp_path)["link"] is None
    write(tmp_path / "release" / "board.html", "<html>")
    assert hl.read_release(tmp_path)["link"].startswith("file://")


# ---- tests and CI ----------------------------------------------------------------------------------

def test_parse_finished_reads_the_real_line_and_nothing_else():
    d = hl.parse_finished("started 19:34:40\n  11,177/11,222  passed 11,160\n" + FINISHED + "\n")
    assert d == {"ran": 11222, "total": 11222, "passed": 11205, "failed": 5, "error": 0, "skipped": 5, "xfailed": 7, "seconds": 210}
    assert hl.parse_finished("started 19:34:40\n  11,177/11,222  passed 11,160") is None
    assert hl.parse_finished("finished 11,222/11,222 passed lots") is None


def test_tests_five_failures_are_in_the_words_and_never_green(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW - 600)
    p = hl.read_tests(live, tmp_path / "out")
    pill = p["body"][0]["items"][0]
    assert "5 failed" in pill["text"] and pill["tone"] == "bad"
    assert p["as_of"] == NOW - 600 and p["refreshable"] is False


def test_tests_the_last_finished_result_survives_pytest_wiping_the_file(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW - 600)
    hl.read_tests(live, tmp_path / "out")
    write(live, "started 20:01:00\n  10/11,222  passed 10\n", NOW - 5)             # a new run began and wiped it
    p = hl.read_tests(live, tmp_path / "out")
    assert p["status"] == "ok" and p["as_of"] == NOW - 600                         # the old result with its OWN time
    assert any("in progress" in f for f in p["facts"])


def test_tests_nothing_finished_and_nothing_cached_is_no_data(tmp_path):
    live = write(tmp_path / "live.txt", "started 20:01:00\n", NOW)
    assert hl.read_tests(live, tmp_path / "out")["status"] == "nodata"
    assert hl.read_tests(tmp_path / "absent.txt", tmp_path / "out")["status"] == "nodata"


def test_tests_says_when_commits_are_newer_than_the_run(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW - 3600)
    assert any("newer than this test run" in f for f in hl.read_tests(live, tmp_path / "o1", head_commit_epoch=NOW)["facts"])
    assert not any("newer" in f for f in hl.read_tests(live, tmp_path / "o2", head_commit_epoch=NOW - 7200)["facts"])


def ci_runs(*runs):
    return json.dumps({"runs": list(runs)})


def run(conclusion, status="completed", created="2026-11-26T20:00:00Z", sha="7c7c79efbfd2b3cca5bfa30c5f5dffe621abf8f8", event="push"):
    return {"conclusion": conclusion, "status": status, "createdAt": created, "headSha": sha, "event": event}


def test_ci_uses_the_newest_completed_run_and_skips_one_in_progress(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW)
    write(tmp_path / "out" / "ci.json", ci_runs(run("success", created="2026-11-26T18:00:00Z"), run("", status="in_progress", created="2026-11-26T20:30:00Z")))
    pills = hl.read_tests(live, tmp_path / "out")["body"][0]["items"]
    assert "CI on main: success (7c7c79e" in pills[1]["text"] and pills[1]["tone"] == "ok"


def test_ci_cancelled_is_neither_green_nor_red_and_a_failure_is_red(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW)
    write(tmp_path / "o" / "ci.json", ci_runs(run("cancelled")))
    assert hl.read_tests(live, tmp_path / "o")["body"][0]["items"][1]["tone"] == ""
    write(tmp_path / "o" / "ci.json", ci_runs(run("failure")))
    assert hl.read_tests(live, tmp_path / "o")["body"][0]["items"][1]["tone"] == "bad"


def test_ci_not_read_is_said_not_assumed_green(tmp_path):
    live = write(tmp_path / "live.txt", FINISHED + "\n", NOW)
    p = hl.read_tests(live, tmp_path / "o")
    assert len(p["body"][0]["items"]) == 1 and any("CI status has not been read" in f for f in p["facts"])


# ---- bug campaign ---------------------------------------------------------------------------------

def state(statuses, history=None, updated="2026-11-16T15:00:00"):
    return json.dumps({"updated": updated, "bugs": {f"BR-{i:02d}": {"status": s} for i, s in enumerate(statuses)},
                       "history": history or [{"t": "2026-11-16T07:00", "open": len(statuses)}]})


def test_bugs_no_state_file_is_no_data(tmp_path):
    assert hl.read_bugs(tmp_path)["status"] == "nodata"


def test_bugs_as_of_is_the_files_time_and_it_cannot_be_refreshed(tmp_path):
    write(tmp_path / "state.json", state(["fixed"] * 16 + ["decision"] * 15 + ["owner"] * 2 + ["already-fixed"]), NOW - 864000)
    p = hl.read_bugs(tmp_path)
    assert p["status"] == "ok" and p["as_of"] == NOW - 864000 and p["refreshable"] is False
    k = p["body"][1]["items"]
    assert (k[0]["n"], k[0]["of"], k[1]["n"], k[2]["n"]) == (17, 34, 15, 2)


@pytest.mark.parametrize("bad", ["{}", '{"bugs": {}}', '{"bugs": [1]}', '{"bugs": {"a": {}}}', "not json"])
def test_bugs_an_unreadable_shape_is_unknown_or_no_data_never_a_number(tmp_path, bad):
    write(tmp_path / "state.json", bad)
    assert hl.read_bugs(tmp_path)["status"] in ("unknown", "nodata")


def test_bugs_done_set_matches_the_campaigns_own_rule_when_that_file_is_present():
    render = ROOT / "docs" / "private" / "bug-campaign" / "render.py"
    if not render.exists():
        pytest.skip("the private bug campaign is not on this machine")
    m = re.search(r"DONE\s*=\s*\{([^}]*)\}", render.read_text(encoding="utf-8"))
    assert m and {s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()} == hl.BUG_DONE


# ---- launch ---------------------------------------------------------------------------------------

def test_launch_ok_and_no_data_and_unexpected(tmp_path):
    assert hl.read_launch(tmp_path)["status"] == "nodata"
    items = [{"status": "done", "title": "a", "who": "me"}, {"status": "doing", "title": "Paywall", "who": "owner"},
             {"status": "todo", "title": "c", "who": "owner"}]
    write(tmp_path / "launch-tracker.data.json", json.dumps({"items": items}), NOW - 3600)
    p = hl.read_launch(tmp_path)
    assert p["status"] == "ok" and p["as_of"] == NOW - 3600 and p["body"][0]["done"] == 1 and p["body"][0]["items"] == ["Paywall"]
    write(tmp_path / "launch-tracker.data.json", json.dumps({"items": [{"nope": 1}]}))
    assert hl.read_launch(tmp_path)["status"] == "unknown"


# ---- the host read ---------------------------------------------------------------------------------

GOOD = {"heartbeat_epoch": NOW - 79200, "news_status": 200, "news_expires_epoch": NOW + 43 * 86400, "hate": 2, "dislike": 6,
        "neutral": 21, "like": 5, "love": 2, "other": 0, "total": 36, "problems": 5, "newest_epoch": NOW - 21 * 86400}


def host_text(**over):
    d = dict(GOOD, **over)
    return "\n".join(f"{k}={d[k]}" for k in hl.HOST_KEYS) + "\n"


def test_host_output_parsed_strictly():
    assert hl.parse_host_output(host_text()) == GOOD
    assert hl.parse_host_output(host_text() + "evil=1\n") is None                 # unknown key
    assert hl.parse_host_output(host_text() + "hate=3\n") is None                  # duplicate
    assert hl.parse_host_output(host_text().replace("hate=2", "hate=two")) is None   # not digits
    assert hl.parse_host_output(host_text().replace("hate=2\n", "")) is None       # a key missing
    assert hl.parse_host_output("Welcome to the host\n" + host_text()) is None     # a banner is not output
    assert hl.parse_host_output(host_text() + "x" * 5000) is None                  # oversize
    assert hl.parse_host_output("") is None and hl.parse_host_output(None) is None


def put_host(out, data=GOOD, fetched=NOW - 1800, error=None, last_good=True):
    state = {"last_good": {"fetched_at": fetched, "data": data} if last_good else None, "last_attempt": {"at": NOW, "error": error}}
    write(Path(out) / "host.json", json.dumps(state))


def test_host_and_feedback_with_no_file_are_no_data(tmp_path):
    assert hl.read_host(tmp_path)["status"] == "nodata" and hl.read_feedback(tmp_path)["status"] == "nodata"


def test_host_ok_uses_the_heartbeat_as_its_time(tmp_path):
    put_host(tmp_path)
    p = hl.read_host(tmp_path)
    assert p["status"] == "ok" and p["as_of"] == NOW - 79200 and p["max_age"] == 36 * 3600


def test_host_failed_attempt_is_unknown_with_a_fixed_string_and_keeps_the_last_good_time(tmp_path):
    put_host(tmp_path, error="unreachable")
    p = hl.read_host(tmp_path)
    assert p["status"] == "unknown" and p["error"] == "host unreachable" and p["as_of"] == NOW - 79200


def test_host_state_with_an_error_we_do_not_know_is_refused(tmp_path):
    put_host(tmp_path, error="ssh: connect to host stranger@evil.example port 22")
    assert hl.read_host(tmp_path)["status"] == "nodata"


def test_feedback_counts_the_five_ratings_and_carries_no_message_text(tmp_path):
    put_host(tmp_path)
    p = hl.read_feedback(tmp_path)
    bars = p["body"][1]
    assert [(i["l"], i["n"]) for i in bars["items"]] == [("hate", 2), ("dislike", 6), ("neutral", 21), ("like", 5), ("love", 2)]
    assert "hate 2" in bars["aria"] and p["as_of"] == NOW - 1800
    assert '"message"' not in json.dumps(p)           # no field for message text exists, by construction


def test_feedback_other_bucket_appears_only_when_it_has_something_and_never_echoes_a_value(tmp_path):
    put_host(tmp_path, data=dict(GOOD, other=3))
    labels = [i["l"] for i in hl.read_feedback(tmp_path)["body"][1]["items"]]
    assert labels[-1] == "other"


def test_feedback_zero_ratings_is_no_data_not_five_zeros(tmp_path):
    put_host(tmp_path, data=dict(GOOD, total=0, hate=0, dislike=0, neutral=0, like=0, love=0, problems=0))
    assert hl.read_feedback(tmp_path)["status"] == "nodata"


def test_feedback_after_a_failed_attempt_still_shows_the_last_counts_marked_unknown(tmp_path):
    put_host(tmp_path, error="timeout")
    p = hl.read_feedback(tmp_path)
    assert p["status"] == "unknown" and p["error"] == "timed out" and p["body"]


# ---- expiries and visitors ----------------------------------------------------------------------------

def test_expiries_rows_sorted_news_row_from_the_host_and_a_bad_date_stays_listed(tmp_path):
    put_host(tmp_path)
    p = hl.read_expiries([{"what": "Copr token", "date": "2027-02-23"}, {"what": "Broken", "date": "soon"}], tmp_path)
    rows = p["body"][0]["rows"]
    assert p["stateless"] is True
    assert [r["what"] for r in rows] == ["News file (re-sign and redeploy)", "Copr token", "Broken"]
    assert rows[0]["epoch"] == GOOD["news_expires_epoch"] and rows[-1]["epoch"] is None


def test_expiries_without_a_host_read_keeps_the_news_row_as_unknown(tmp_path):
    rows = hl.read_expiries([], tmp_path)["body"][0]["rows"]
    assert rows == [{"what": "News file (re-sign and redeploy)", "epoch": None}]


def test_visitors_is_a_link_with_no_state_and_no_data():
    p = hl.read_visitors()
    assert p["stateless"] is True and p["link"] == "http://localhost:8210/_local/visitors.html"


def test_every_reader_that_can_fail_uses_a_fixed_error_string():
    for key, text in hl.ERR.items():
        assert re.fullmatch(r"[a-z ,]+", text), key


def test_time_is_always_epoch_seconds_and_a_naive_string_is_refused():
    assert hl.iso_z_to_epoch("2026-11-25T11:17:14Z") == 1795605434.0
    for naive in ("2026-11-25 11:17:14", "2026-11-25T11:17:14", "2026-11-25T11:17:14+01:00", "yesterday", None, 5):
        assert hl.iso_z_to_epoch(naive) is None


# ---- the Installs reader ---------------------------------------------------

WEBSITE = Path.home() / "Code" / "bristlenose-website"
needs_website = pytest.mark.skipif(not (WEBSITE / "scripts" / "counts-dashboard.py").exists(),
                                   reason="the website repo is not on this machine")


def write_counts(d: Path, heartbeat=True, header=True, daily=None):
    d.mkdir(parents=True, exist_ok=True)
    rows = ["date,ch,v,checks,first,month,welcome,other"] if header else ["wrong,header"]
    last = time.gmtime()
    today = f"{last.tm_year}-{last.tm_mon:02d}-{last.tm_mday:02d}"
    rows += daily or [f"{today},,,50,0,0,0,0", f"{today},store,0.48,6,1,1,2,0"]
    (d / "counts.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (d / "monthly.csv").write_text("month,ch,sub,days,installs\n", encoding="utf-8")
    if heartbeat:
        (d / "heartbeat").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " ok files=1 lines=1 news=1 rewrote=x\n")


def test_installs_without_the_website_repo_is_no_data_with_a_fixed_reason(tmp_path):
    p = hl.read_installs(tmp_path / "nowhere", tmp_path / "counts")
    assert p["status"] == "nodata" and p["error"] == hl.ERR["missing_tool"] and p["body"] == []


@needs_website
def test_installs_ok_reads_the_heartbeat_as_its_time_and_never_the_clock(tmp_path):
    write_counts(tmp_path / "c")
    p = hl.read_installs(WEBSITE, tmp_path / "c")
    assert p["status"] == "ok" and p["as_of_label"] == "counted" and p["max_age"] == 36 * 3600
    assert abs(p["as_of"] - time.time()) < 5          # the heartbeat we just wrote
    k = p["body"][0]["items"]
    assert (k[0]["n"], k[1]["n"]) == (56, 6)


@needs_website
def test_installs_no_files_is_no_data_not_zero(tmp_path):
    p = hl.read_installs(WEBSITE, tmp_path / "empty")
    assert p["status"] == "nodata" and not p["body"]


@needs_website
def test_installs_wrong_header_is_unknown_and_does_not_end_the_run(tmp_path):
    write_counts(tmp_path / "c", header=False)
    p = hl.read_installs(WEBSITE, tmp_path / "c")        # the loader raises SystemExit here
    assert p["status"] == "unknown" and p["error"] == hl.ERR["unexpected"]


@needs_website
def test_installs_missing_heartbeat_is_no_data(tmp_path):
    write_counts(tmp_path / "c", heartbeat=False)
    assert hl.read_installs(WEBSITE, tmp_path / "c")["status"] == "nodata"


@needs_website
def test_installs_many_unreadable_rows_is_unknown_not_a_smaller_number(tmp_path):
    bad = [f"2026-11-0{i},,,x,0,0,0,0" for i in range(1, 8)]
    write_counts(tmp_path / "c", daily=bad + ["2026-11-09,,,50,0,0,0,0"])
    p = hl.read_installs(WEBSITE, tmp_path / "c")
    assert p["status"] == "unknown"
