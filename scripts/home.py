#!/usr/bin/env python3
"""home: refresh what is old, read every panel, write one page, open it.

    scripts/home.py [--offline] [--no-open]

Writes ~/bristlenose-home/home.html (dirs 0700, files 0600, written atomically). The page knows from
the clock how old each panel is; this command only makes the data under it fresher. Design:
docs/private/design-home-dashboard.md. Standard library only.

Every job is a fixed argv list built in this file: never a shell, never built from the page or from
data. A job that fails never touches a panel's time: the last good file keeps its own age and the
panel says it could not ask.

  --offline   skip every job that touches the network (scp, ssh, gh); read what is already on disk
  --no-open   write the page, do not open it

Machine-local settings (never committed): ~/.config/bristlenose-home/config.json
  { "website_repo": "~/Code/bristlenose-website", "counts_dir": "~/bristlenose-counts",
    "host_alias": "dreamhost", "expiries": [ {"what": "Copr token", "date": "2027-02-23"} ] }
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import home_lib as hl  # noqa: E402

OUT_DIR = Path.home() / "bristlenose-home"
CONFIG = Path.home() / ".config" / "bristlenose-home" / "config.json"
PYTEST_LIVE = Path.home() / ".cache" / "bristlenose" / "pytest-live.txt"
_SAFE = re.compile(r"^[A-Za-z0-9._/-]+$")

# The one remote command: a literal, with nothing interpolated into it. It runs python3 on the host and
# prints key=value lines (digits only): the counts heartbeat, what the live /app/news answers and its
# expiry, and the feedback RATING COUNTS. The messages are never printed, so they never leave the host.
# No single quote may appear inside it (it is wrapped in single quotes for the remote shell).
REMOTE_PY = (
    "import calendar,csv,json,os,time,base64,urllib.error,urllib.request\n"
    "h=os.path.expanduser(\"~\")\n"
    "def z(s):\n"
    " return calendar.timegm(time.strptime(s,\"%Y-%m-%dT%H:%M:%SZ\"))\n"
    "def hb():\n"
    " try:\n"
    "  return z(open(h+\"/bn-counts/heartbeat\").read().split()[0])\n"
    " except Exception:\n"
    "  return 0\n"
    "st=0;ex=0\n"
    "try:\n"
    " r=urllib.request.urlopen(\"https://bristlenose.app/app/news\",timeout=10)\n"
    " st=r.status\n"
    " ex=z(json.loads(base64.b64decode(json.loads(r.read(20000))[\"payload\"]))[\"expires\"])\n"
    "except urllib.error.HTTPError as e:\n"
    " st=e.code\n"
    "except Exception:\n"
    " pass\n"
    "c={k:0 for k in (\"hate\",\"dislike\",\"neutral\",\"like\",\"love\",\"other\",\"total\",\"problems\",\"newest_epoch\")}\n"
    "try:\n"
    " f=open(h+\"/bristlenose.app/data/feedback.csv\",encoding=\"utf-8\",errors=\"replace\")\n"
    "except FileNotFoundError:\n"
    " f=None\n"
    "for row in (csv.DictReader(f) if f else []):\n"
    " v=(row.get(\"rating\") or \"\")\n"
    " c[v if v in (\"hate\",\"dislike\",\"neutral\",\"like\",\"love\") else \"other\"]+=1\n"
    " c[\"total\"]+=1\n"
    " c[\"problems\"]+=1 if row.get(\"kind\")==\"problem\" else 0\n"
    " try:\n"
    "  c[\"newest_epoch\"]=max(c[\"newest_epoch\"],calendar.timegm(time.strptime((row.get(\"time\") or \"\")[:19],\"%Y-%m-%d %H:%M:%S\")))\n"
    " except ValueError:\n"
    "  pass\n"
    "print(\"heartbeat_epoch=%d\"%hb());print(\"news_status=%d\"%st);print(\"news_expires_epoch=%d\"%ex)\n"
    "for k in (\"hate\",\"dislike\",\"neutral\",\"like\",\"love\",\"other\",\"total\",\"problems\",\"newest_epoch\"):\n"
    " print(\"%s=%d\"%(k,c[k]))\n"
)
REMOTE_CMD = "python3 -I -c '" + REMOTE_PY + "'"       # -I: no user site-packages or PYTHON* variables on a shared account
assert "'" not in REMOTE_PY

SSH_OPTIONS = ["-a", "-x", "-T", "-o", "BatchMode=yes", "-o", "ClearAllForwardings=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10", "-o", "ControlPath=none"]


GH_REPO = "cassiocassio/bristlenose"      # pinned: gh otherwise reads the repository from the directory home was run in

# ---- configuration -----------------------------------------------------------------------------

def load_config(path: Path | None = None, home: Path | None = None) -> dict:
    """The machine-local settings with safe defaults. A value that is not a plain path or alias is
    dropped (the setting then reads as absent), so a hand-edited config cannot inject an ssh or scp option."""
    home = home or Path.home()
    raw = hl.read_json(path or CONFIG)
    raw = raw if isinstance(raw, dict) else {}

    def pathval(key, default):
        v = raw.get(key)
        if isinstance(v, str) and _SAFE.match(v.replace("~", "", 1)) and ".." not in v:
            return Path(v.replace("~", str(home), 1))
        return default

    alias = raw.get("host_alias")
    alias = alias if isinstance(alias, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", alias) else None
    expiries = raw.get("expiries") if isinstance(raw.get("expiries"), list) else []
    return {"website_repo": pathval("website_repo", home / "Code" / "bristlenose-website"),
            "counts_dir": pathval("counts_dir", home / "bristlenose-counts"),
            "host_alias": alias, "expiries": expiries,
            "private": ROOT / "docs" / "private", "out": OUT_DIR}


# ---- jobs ----------------------------------------------------------------------------------------

def run(argv: list[str], timeout: float) -> tuple[str, bytes]:
    """('ok', stdout) | ('failed', b'') | ('timeout', b''). shell=False, no stdin, its own process
    group (killed whole on timeout: a deadline that kills only the child can leave scp hanging), a
    minimal environment."""
    assert isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(Path.home()), "LC_ALL": "C"}
    try:
        p = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env=env, start_new_session=True)
    except OSError:
        return "failed", b""
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass                                       # something still holds the pipe: abandon it
        return "timeout", b""
    return ("ok" if p.returncode == 0 else "failed"), out


def job_argv(cfg: dict) -> dict:
    """Every job, by name. The allowlist test reads this."""
    web = cfg["website_repo"]
    jobs = {
        "release": {"argv": [sys.executable, str(HERE / "release-board.py"), "--out", str(cfg["out"] / "release")],
                    "net": False, "timeout": 120, "fresh_for": 0},
        "counts": {"argv": [str(web / "scripts" / "counts-refresh.sh"), "--no-open"],
                   "net": True, "timeout": 120, "fresh_for": 6 * 3600},
        "ci": {"argv": ["gh", "run", "list", "-R", GH_REPO, "--workflow", "ci.yml", "--branch", "main", "--limit", "5",
                        "--json", "conclusion,status,createdAt,headSha,event"],
               "net": True, "timeout": 20, "fresh_for": 900},
    }
    if cfg.get("host_alias"):
        jobs["host"] = {"argv": ["ssh", *SSH_OPTIONS, cfg["host_alias"], REMOTE_CMD],
                        "net": True, "timeout": 40, "fresh_for": 3600}
    return jobs


def should_run(job: dict, output_mtime: float | None, now: float, offline: bool) -> bool:
    if offline and job["net"]:
        return False
    return output_mtime is None or now - output_mtime >= job["fresh_for"]


def record_host(out: Path, status: str, stdout: bytes, now: float) -> None:
    """Update host.json. A success replaces last_good; a failure only changes last_attempt, so three
    failures in a row leave the last good time exactly where it was."""
    prev = hl.read_host_state(out) or {"last_good": None, "last_attempt": {"at": now, "error": None}}
    last_good, error = prev["last_good"], None
    if status == "ok":
        data = hl.parse_host_output(stdout.decode("utf-8", "replace"))
        if data is None:
            error = "unexpected"
        else:
            last_good = {"fetched_at": now, "data": data}
    else:
        error = "timeout" if status == "timeout" else "unreachable"
    hl.atomic_write(out / "host.json", json.dumps({"last_good": last_good, "last_attempt": {"at": now, "error": error}}))


def record_ci(out: Path, status: str, stdout: bytes) -> None:
    """ci.json keeps only the five fields the panel reads (no titles, no branch names: strangers type those),
    and only runs that are not pull requests. Output that is not a non-empty list of runs leaves the
    old file alone: a bad read must not turn 'CI success' into 'not read'."""
    if status != "ok":
        return
    try:
        rows = json.loads(stdout.decode("utf-8", "replace"))
    except ValueError:
        return
    if not isinstance(rows, list):
        return
    keep = [{k: r.get(k) for k in ("conclusion", "status", "createdAt", "headSha", "event")}
            for r in rows if isinstance(r, dict) and r.get("event") != "pull_request"]
    if keep:
        hl.atomic_write(out / "ci.json", json.dumps({"runs": keep}))


def run_jobs(cfg: dict, offline: bool, now: float, say=print) -> None:
    out = cfg["out"]
    marks = {"release": out / "release" / "board.json", "counts": cfg["counts_dir"] / "heartbeat",
             "ci": out / "ci.json", "host": out / "host.json"}
    hs = hl.read_host_state(out)
    host_mark = hs["last_good"]["fetched_at"] if hs and hs["last_good"] else None   # a failed read must not stop the next retry
    for name, job in job_argv(cfg).items():
        mark = host_mark if name == "host" else hl.mtime(marks[name])
        if not should_run(job, mark, now, offline):
            say(f"  {name}: {'skipped (offline)' if offline and job['net'] else 'fresh enough'}")
            continue
        status, stdout = run(job["argv"], job["timeout"])
        if name == "host":
            record_host(out, status, stdout, now)
        elif name == "ci":
            record_ci(out, status, stdout)
        if name == "release" and (out / "release").is_dir():
            os.chmod(str(out / "release"), 0o700)
        say(f"  {name}: {status}")


# ---- reading and writing the page ------------------------------------------------------------------

def guarded(pid: str, title: str, fn) -> dict:
    """One reader, whatever it does. An exception, or a SystemExit from a script we borrowed, becomes
    an unknown panel with a fixed error: never a silent blank, never the end of the whole run."""
    try:
        return fn()
    except (SystemExit, Exception):  # noqa: BLE001
        return hl.unknown(pid, title, "reader")


def head_commit_epoch() -> float | None:
    status, out = run(["git", "-C", str(ROOT), "log", "-1", "--format=%ct", "main", "--"], 10)
    try:
        return float(out.decode().strip()) if status == "ok" else None
    except ValueError:
        return None


def current_version() -> str | None:
    m = re.search(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', (ROOT / "bristlenose" / "__init__.py").read_text(encoding="utf-8")) \
        if (ROOT / "bristlenose" / "__init__.py").exists() else None
    return m.group(1) if m else None


def read_panels(cfg: dict) -> list[dict]:
    out = cfg["out"]
    host_on = cfg.get("host_alias") is not None
    return [
        guarded("installs", "Installs calling home", lambda: hl.read_installs(cfg["website_repo"], cfg["counts_dir"])),
        guarded("visitors", "Website visitors", hl.read_visitors),
        guarded("release", "Release", lambda: hl.read_release(out, current_version())),
        guarded("tests", "Tests and CI", lambda: hl.read_tests(PYTEST_LIVE, out, head_commit_epoch())),
        guarded("bugs", "Bug campaign", lambda: hl.read_bugs(cfg["private"] / "bug-campaign")),
        guarded("feedback", "User feedback", lambda: hl.read_feedback(out, host_on)),
        guarded("launch", "App Store launch", lambda: hl.read_launch(cfg["private"] / "app-store-launch")),
        guarded("expiries", "Things that expire", lambda: hl.read_expiries(cfg["expiries"], out)),
        guarded("host", "Host health", lambda: hl.read_host(out, host_on)),
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return 0
    unknown_args = [a for a in args if a not in ("--offline", "--no-open")]
    if unknown_args:
        print(f"home: unknown argument: {unknown_args[0]}", file=sys.stderr)
        return 2
    offline, no_open = "--offline" in args, "--no-open" in args
    cfg = load_config()
    cfg["out"].mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(str(cfg["out"]), 0o700)
    now = time.time()
    print("home: refreshing" + (" (offline)" if offline else ""))
    run_jobs(cfg, offline, now)
    page = hl.build_page(read_panels(cfg), time.time())
    target = cfg["out"] / "home.html"
    hl.atomic_write(target, page)
    print(f"home: wrote {target}")
    if not no_open and sys.platform == "darwin":
        run(["open", str(target)], 10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
