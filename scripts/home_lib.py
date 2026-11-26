"""Readers and the page builder for scripts/home.py. Standard library only.

A reader turns one source into a panel dict (the contract in docs/private/design-home-dashboard.md,
section 2). It never raises: a failure becomes `status: "unknown"` with one of the fixed ERR strings
and the last good data keeps its own `as_of`. No raw stderr, path or exception text is ever shown.

Times are UTC epoch seconds. `as_of` is when the DATA last changed or was last fetched, never the
time we read it. The page formats display times in Europe/London.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent

# The only strings a panel may show as an error. Raw exceptions and stderr can carry host names,
# paths and stranger-typed text; they are mapped to one of these and dropped.
ERR = {
    "unreadable": "the source could not be read",
    "missing_tool": "a needed tool was not found",
    "unexpected": "the source had an unexpected shape",
    "unreachable": "host unreachable",
    "timeout": "timed out",
    "failed": "the refresh job failed",
}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_RB = None


def release_board():
    """scripts/release-board.py by path: its `inline_json` (the one safe way to put data in a page)
    and `board_tokens` (the shared palette). Loaded once."""
    global _RB
    if _RB is None:
        _RB = _load_module(HERE / "release-board.py", "release_board_for_home")
    return _RB


# ---- links -----------------------------------------------------------------

def safe_link(url: str | None) -> str | None:
    """A `file:` URL, or `http://localhost|127.0.0.1[:port]/...`. Anything else is not a link.
    The page applies the same rule again; this is the first of two checks."""
    if not url:
        return None
    try:
        u = urlsplit(url)
    except ValueError:
        return None
    if u.scheme == "file" and not u.netloc:
        return url
    if u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1") and not u.username:
        return url
    return None


def file_link(path: Path | str) -> str | None:
    p = Path(path)
    return p.as_uri() if p.exists() else None


# ---- the panel skeleton -----------------------------------------------------

def panel(pid: str, title: str, **kw) -> dict:
    p = {"id": pid, "title": title, "link": None, "link_note": None, "span": 1, "status": "ok",
         "as_of": None, "as_of_label": "as of", "max_age": None, "refreshable": True, "stateless": False,
         "body": [], "facts": [], "error": None, "src": ""}
    p.update(kw)
    p["link"] = safe_link(p["link"])
    return p


def unknown(pid: str, title: str, err: str, **kw) -> dict:
    return panel(pid, title, status="unknown", error=ERR[err], **kw)


def nodata(pid: str, title: str, **kw) -> dict:
    return panel(pid, title, status="nodata", **kw)


# ---- the page ---------------------------------------------------------------

def _hash(text: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def build_page(panels: list[dict], built_at: float) -> str:
    """The finished page. Data goes in through the board's own inline_json (escapes < > & and the
    JS line separators); both inline scripts are named in a CSP that also forbids every network
    connection, so a rule broken in a future edit still cannot send data anywhere."""
    rb = release_board()
    tpl = (HERE / "home-page.template.html").read_text(encoding="utf-8")
    fresh_js = (HERE / "home-freshness.js").read_text(encoding="utf-8")
    page_js = (HERE / "home-page.js").read_text(encoding="utf-8")
    for name, js in (("home-freshness.js", fresh_js), ("home-page.js", page_js)):
        if "</script" in js.lower() or "<!--" in js:
            raise RuntimeError(f"{name} would end its own script block")
    csp = (f"default-src 'none'; script-src '{_hash(fresh_js)}' '{_hash(page_js)}'; style-src 'unsafe-inline'; "
           "img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'")
    model = {"built_at": built_at, "panels": panels}
    slots = ("__CSP__", "__BOARD_TOKENS__", "__HOME_DATA__", "__HOME_FRESHNESS_JS__", "__HOME_PAGE_JS__")
    for slot in slots:
        if tpl.count(slot) != 1:
            raise RuntimeError(f"the template must carry {slot} exactly once")
    # The data goes in LAST: whatever a stranger typed into it is never searched for a slot name.
    out = tpl.replace("__CSP__", csp, 1)
    out = out.replace("__BOARD_TOKENS__", rb.board_tokens(), 1)
    out = out.replace("__HOME_FRESHNESS_JS__", fresh_js, 1)
    out = out.replace("__HOME_PAGE_JS__", page_js, 1)
    return out.replace("__HOME_DATA__", rb.inline_json(model), 1)


# ---- panel 1: installs calling home ------------------------------------------

_BEAT_OK = 36 * 3600
_SKIP_LIMIT = 0.10


def _dashboard_module(website_repo: Path):
    return _load_module(website_repo / "scripts" / "counts-dashboard.py", "counts_dashboard_for_home")


def read_installs(website_repo: Path, counts_dir: Path) -> dict:
    """Panel 1, from the CSVs `counts-refresh.sh` pulled, through the website repo's own loader (one
    copy of the parsing and of its hostile-value rules). The loader can raise SystemExit on a wrong
    header: that is caught here as `unknown`, not allowed to end the whole run."""
    pid, title = "installs", "Installs calling home"
    common = {"span": 2, "as_of_label": "counted", "max_age": _BEAT_OK, "refreshable": True,
              "src": "Totals the host counted, pulled by counts-refresh.sh. Only opted-in installs are described; "
                     "the rest are a count."}
    try:
        mod = _dashboard_module(website_repo)
    except (ImportError, OSError, SyntaxError):
        return nodata(pid, title, error=ERR["missing_tool"], **common)
    try:
        d = mod.load(counts_dir)
    except (SystemExit, Exception):  # noqa: BLE001 - a borrowed script's SystemExit must not end the run
        return unknown(pid, title, "unexpected", **common)
    link = file_link(counts_dir / "dashboard.html")
    if "counts.csv" in d.missing or "heartbeat" in d.missing:
        return nodata(pid, title, link=link, **common)
    if d.heartbeat is None:
        return unknown(pid, title, "unexpected", link=link, **common)
    as_of = d.heartbeat.timestamp()
    rows = len(d.daily) + len(d.monthly)
    if not d.daily:
        return nodata(pid, title, link=link, as_of=as_of, **common)
    if d.skipped and d.skipped > _SKIP_LIMIT * max(1, rows + d.skipped):
        return unknown(pid, title, "unexpected", link=link, as_of=as_of, **common)
    days = sorted({r["date"] for r in d.daily})
    last = days[-1]
    window = [x for x in days if x > last - timedelta(days=90)]

    def day_all(x):
        return sum(r["checks"] for r in d.daily if r["date"] == x)

    def day_opt(x):
        return sum(r["checks"] for r in d.daily if r["date"] == x and r["ch"])

    month_key = last.strftime("%Y-%m")
    active = sum(r["month"] for r in d.daily if r["date"].strftime("%Y-%m") == month_key)
    kpis = [{"n": day_all(last), "l": f"checks on {last.day} {last.strftime('%b')}", "link": link},
            {"n": day_opt(last), "l": "of them opted in"},
            {"n": active, "l": f"active installs, {last.strftime('%b')}"}]
    body = [{"kind": "kpis", "items": kpis}]
    points = [{"all": day_all(x), "opt": day_opt(x)} for x in window]
    body.append({"kind": "area", "points": points,
                 "first_label": f"{window[0].day} {window[0].strftime('%b')}",
                 "last_label": f"{window[-1].day} {window[-1].strftime('%b')}",
                 "aria": (f"Daily news checks, {window[0].isoformat()} to {window[-1].isoformat()}: "
                          f"the last day had {points[-1]['all']} checks, {points[-1]['opt']} of them opted in")})
    facts = []
    gaps = (window[-1] - window[0]).days + 1 - len(window)
    if gaps:
        facts.append(f"{gaps} day{'s' if gaps != 1 else ''} not counted in this window")
    if d.skipped:
        facts.append(f"{d.skipped} unreadable row{'s' if d.skipped != 1 else ''} skipped")
    months = sorted({r["month"] for r in d.monthly})
    if months:
        m = months[-1]
        grp = {"1": 0, "t": 0, "": 0}
        for r in d.monthly:
            if r["month"] == m:
                grp[r["sub"] if r["sub"] in grp else ""] += r["installs"]
        n = sum(grp.values())
        body.append({"kind": "split", "title": f"Opted in, by subscription ({m})",
                     "parts": [{"l": "paying", "n": grp["1"], "color": "--s-a"}, {"l": "trial", "n": grp["t"], "color": "--ok"},
                               {"l": "other", "n": grp[""], "color": "--skip"}],
                     "note": f"(n = {n})", "aria": f"Paying {grp['1']}, trial {grp['t']}, other {grp['']}"})
    return panel(pid, title, link=link, as_of=as_of, body=body, facts=facts, **common)


def atomic_write(path: Path, text: str) -> None:
    """0600, atomic (temp file in the same directory, then os.replace), never through a symlink."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(str(tmp), 0o600)
    os.replace(str(tmp), str(path))


# ---- shared helpers for the other readers -------------------------------------

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def iso_z_to_epoch(s) -> float | None:
    """Strict: only `YYYY-MM-DDTHH:MM:SSZ`. A naive or offset string is refused rather than guessed
    (it would be read as London or Pacific time and be hours out)."""
    if not isinstance(s, str) or not ISO_Z.match(s):
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def read_json(path: Path):
    """The parsed file, or None when it is absent, unreadable or not JSON. Never raises."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def mtime(path: Path) -> float | None:
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


# ---- panel 3: release -------------------------------------------------------------

_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def read_release(out_dir: Path) -> dict:
    """From the release board's own model, written by `release-board.py --out <out_dir>/release`.
    `as_of` is the board's `header.newest_source`, never its `generated` (which is the moment the
    model was built, so it would make every release look fresh forever). With no verify batch the
    channels are NOT VERIFIED, said in words, never a count of fine ones."""
    pid, title = "release", "Release"
    common = {"span": 2, "as_of_label": "run", "max_age": 30 * 86400, "refreshable": False,
              "src": "The release board's own model (no network). Open the board for the run picker and replay."}
    model = read_json(Path(out_dir) / "release" / "board.json")
    link = file_link(Path(out_dir) / "release" / "board.html")
    if model is None:
        return nodata(pid, title, link=link, **common)
    try:
        version = model["version"]
        header = model["header"]
        channels = model["channels"]
        cards = channels["cards"]
        as_of = iso_z_to_epoch(header.get("newest_source"))
        if not isinstance(version, str) or not _VERSION.match(version) or as_of is None or not isinstance(cards, list):
            raise ValueError("shape")
        stations = []
        verified = 0
        for c in cards:
            name, state = str(c["name"]), c.get("state")
            if state == "ok":
                verified += 1
                stations.append({"name": name, "state": "ok"})
            elif state in ("no-data", "skipped", None):
                stations.append({"name": name, "state": "", "note": "skipped" if state == "skipped" else ""})
            elif state == "unreachable":
                stations.append({"name": name, "state": "", "note": "could not look"})
            else:
                stations.append({"name": name, "state": "bad", "note": "not ok"})
        batches = channels.get("batches") or 0
        phase = str(model.get("phase") or "")
    except (KeyError, TypeError, ValueError, AttributeError):
        return unknown(pid, title, "unexpected", link=link, **common)
    facts = []
    if not batches:
        facts.append(f"Channels not verified for {version}: no verify batch is recorded for this run.")
    else:
        facts.append(f"{verified} of {len(cards)} channels verified (the rest are not ok, skipped or could not be looked at).")
    body = [{"kind": "text", "text": f"{version} · {phase}"},
            {"kind": "stations", "items": stations,
             "aria": "Release channels: " + ", ".join(f"{s['name']} {s['state'] or 'not verified'}" for s in stations)}]
    return panel(pid, title, link=link, as_of=as_of, body=body, facts=facts, **common)


# ---- panel 4: tests and CI ---------------------------------------------------------

_FINISHED = re.compile(r"^finished\s+([\d,]+)/([\d,]+)\s+passed\s+([\d,]+)\s+failed\s+([\d,]+)\s+error\s+([\d,]+)"
                       r"\s+skipped\s+([\d,]+)\s+xfailed\s+([\d,]+)\s+\W+\s*(\d+)\s*s\s*$")


def _n(s: str) -> int:
    return int(s.replace(",", ""))


def parse_finished(text: str) -> dict | None:
    """The last `finished` line of pytest-live.txt, as numbers. Anything that does not match
    exactly is None: a line we cannot read is not a result."""
    last = None
    for line in text.splitlines():
        if line.startswith("finished"):
            last = line.strip()
    if last is None:
        return None
    m = _FINISHED.match(last)
    if not m:
        return None
    t = [_n(g) for g in m.groups()]
    return {"ran": t[0], "total": t[1], "passed": t[2], "failed": t[3], "error": t[4], "skipped": t[5],
            "xfailed": t[6], "seconds": t[7]}


def newest_completed_ci(ci: dict | None) -> dict | None:
    """The newest COMPLETED run of the CI workflow with a known conclusion; in-progress runs are
    skipped over, not counted as green and not as red."""
    if not isinstance(ci, dict):
        return None
    runs = [r for r in ci.get("runs", []) if isinstance(r, dict) and r.get("status") == "completed"
            and isinstance(r.get("conclusion"), str) and iso_z_to_epoch(r.get("createdAt")) is not None
            and isinstance(r.get("headSha"), str) and re.fullmatch(r"[0-9a-f]{7,40}", r["headSha"])]
    return max(runs, key=lambda r: iso_z_to_epoch(r["createdAt"])) if runs else None


def read_tests(live_file: Path, out_dir: Path, head_commit_epoch: float | None = None) -> dict:
    """The last FULL pytest run (pytest wipes the live file when a run starts, so the last finished
    line is kept in tests.json) and the newest completed CI run (`ci.json`, written by the gh job).
    The verdict is in words, never a bare green: five failures read '5 failed'."""
    pid, title = "tests", "Tests and CI"
    common = {"as_of_label": "run", "max_age": 24 * 3600, "refreshable": False,
              "src": "The last full pytest run (the live results file) and the newest completed CI run on main."}
    cache = Path(out_dir) / "tests.json"
    live_m = mtime(live_file)
    finished = None
    try:
        finished = parse_finished(Path(live_file).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        pass
    facts = []
    if finished is not None and live_m is not None:
        saved = {"finished": finished, "as_of": live_m}
        try:
            atomic_write(cache, json.dumps(saved))
        except OSError:
            pass
        as_of = live_m
    else:
        saved = read_json(cache)
        if not isinstance(saved, dict) or not isinstance(saved.get("finished"), dict) or not isinstance(saved.get("as_of"), (int, float)):
            return nodata(pid, title, **common)
        finished, as_of = saved["finished"], float(saved["as_of"])
        facts.append("A test run is in progress or ended early: this is the last run that finished.")
    bad = finished["failed"] + finished["error"]
    pills = [{"text": f"pytest: {finished['passed']:,} passed, {finished['failed']} failed"
                      f"{', ' + str(finished['error']) + ' errors' if finished['error'] else ''}, "
                      f"{finished['skipped']} skipped ({finished['seconds']} s)",
              "tone": "bad" if bad else "ok"}]
    ci = newest_completed_ci(read_json(Path(out_dir) / "ci.json"))
    if ci is None:
        facts.append("CI status has not been read.")
    else:
        c = ci["conclusion"]
        tone = "ok" if c == "success" else "bad" if c == "failure" else ""
        pills.append({"text": f"CI on main: {c} ({ci['headSha'][:7]}, {ci.get('event', 'run')})", "tone": tone})
    if head_commit_epoch is not None and head_commit_epoch > as_of + 60:
        facts.append("There are commits newer than this test run.")
    return panel(pid, title, as_of=as_of, body=[{"kind": "pills", "items": pills}], facts=facts, **common)


# ---- panel 5: bug campaign ----------------------------------------------------------

# Copied from docs/private/bug-campaign/render.py (a script, not importable). tests/test_home_readers.py
# compares this set with that file's line whenever the file is present, so the two cannot drift quietly.
BUG_DONE = {"fixed", "already-fixed", "dropped", "filed"}


def read_bugs(campaign_dir: Path) -> dict:
    pid, title = "bugs", "Bug campaign"
    common = {"span": 2, "as_of_label": "changed", "max_age": 3 * 86400, "refreshable": False,
              "src": "Reads bug-campaign/state.json. Dashed grey: the straight-line plan."}
    f = Path(campaign_dir) / "state.json"
    link = file_link(Path(campaign_dir) / "campaign.html")
    state = read_json(f)
    if state is None:
        return nodata(pid, title, link=link, **common)
    try:
        bugs = state["bugs"]
        if not isinstance(bugs, dict) or not bugs:
            raise ValueError("shape")
        statuses = [str(b["status"]) for b in bugs.values()]
        history = [h for h in state.get("history", []) if isinstance(h, dict) and isinstance(h.get("open"), int)]
        total = len(statuses)
        done = sum(1 for s in statuses if s in BUG_DONE)
        series = [h["open"] for h in history] + [total - done]
        labels = [str(h.get("t", ""))[:10] for h in history] + [str(state.get("updated", ""))[:10]]
    except (KeyError, TypeError, ValueError, AttributeError):
        return unknown(pid, title, "unexpected", link=link, **common)
    as_of = mtime(f)
    waiting = statuses.count("decision")
    owner = statuses.count("owner")
    kpis = [{"n": done, "of": total, "l": f"done ({statuses.count('fixed')} fixed, {statuses.count('already-fixed')} already fixed)", "link": link},
            {"n": waiting, "l": "waiting on a design decision"}, {"n": owner, "l": "owner-only"}]
    body = [{"kind": "line", "points": series, "top": total, "plan": True, "first_label": labels[0], "last_label": labels[-1],
             "aria": f"Open bugs fell from {series[0]} to {series[-1]} between {labels[0]} and {labels[-1]}"},
            {"kind": "kpis", "items": kpis}]
    return panel(pid, title, link=link, as_of=as_of, body=body, **common)


# ---- panel 7: app store launch ---------------------------------------------------------

def read_launch(launch_dir: Path) -> dict:
    pid, title = "launch", "App Store launch"
    common = {"as_of_label": "changed", "max_age": 7 * 86400, "refreshable": False,
              "src": "launch-tracker.data.json. The rejection-checklist items are on the tracker page, not counted here."}
    f = Path(launch_dir) / "launch-tracker.data.json"
    link = file_link(Path(launch_dir) / "launch-tracker.html")
    data = read_json(f)
    if data is None:
        return nodata(pid, title, link=link, **common)
    try:
        items = data["items"]
        if not isinstance(items, list) or not items:
            raise ValueError("shape")
        status = [str(i["status"]) for i in items]
        doing = [str(i["title"]) for i in items if i["status"] == "doing"][:3]
        owner_todo = sum(1 for i in items if i["status"] == "todo" and i.get("who") == "owner")
    except (KeyError, TypeError, ValueError, AttributeError):
        return unknown(pid, title, "unexpected", link=link, **common)
    done, total = status.count("done"), len(status)
    body = [{"kind": "progress", "done": done, "total": total, "items": doing,
             "aria": f"{done} of {total} tracker items done"}]
    facts = [f"{done} of {total} tracker items done · {owner_todo} owner-only still to do"]
    return panel(pid, title, link=link, as_of=mtime(f), body=body, facts=facts, **common)


# ---- the single host read: panels 6, 8 (the news row) and 9 --------------------------------

HOST_KEYS = ("heartbeat_epoch", "news_status", "news_expires_epoch", "hate", "dislike", "neutral", "like", "love",
             "other", "total", "problems", "newest_epoch")
_INT = re.compile(r"^\d{1,12}$")


def parse_host_output(text: str) -> dict | None:
    """The host's `key=value` lines, strictly: at most 4 KB, known keys only, values are plain
    digits. Anything else is None, and the caller records 'unexpected' - the text itself, which
    a compromised host could shape, is never kept or shown."""
    if not isinstance(text, str) or len(text.encode("utf-8", "replace")) > 4096:
        return None
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        k, sep, v = line.partition("=")
        if not sep or k not in HOST_KEYS or k in out or not _INT.match(v):
            return None
        out[k] = int(v)
    return out if all(k in out for k in HOST_KEYS) else None


def read_host_state(out_dir: Path) -> dict | None:
    """host.json: {"last_good": {"fetched_at": s, "data": {...}} | null, "last_attempt": {"at": s, "error": key|null}}."""
    s = read_json(Path(out_dir) / "host.json")
    if not isinstance(s, dict):
        return None
    lg, la = s.get("last_good"), s.get("last_attempt")
    if lg is not None and not (isinstance(lg, dict) and isinstance(lg.get("fetched_at"), (int, float)) and isinstance(lg.get("data"), dict)):
        return None
    if not isinstance(la, dict) or (la.get("error") is not None and la["error"] not in ERR):
        return None
    return {"last_good": lg, "last_attempt": la}


def read_host(out_dir: Path) -> dict:
    pid, title = "host", "Host health"
    common = {"as_of_label": "counted", "max_age": 36 * 3600, "refreshable": True,
              "src": "One SSH read: the counts job's heartbeat and what the live /app/news answers."}
    st = read_host_state(out_dir)
    if st is None:
        return nodata(pid, title, **common)
    lg, err = st["last_good"], st["last_attempt"]["error"]
    data = lg["data"] if lg else None
    as_of = float(data["heartbeat_epoch"]) if data else None
    body, facts = [], []
    if data:
        facts.append(f"/app/news answers {data['news_status']}." if data["news_status"] else "/app/news could not be read from the host.")
        body.append({"kind": "expiries", "rows": [{"what": "News file expires", "epoch": data["news_expires_epoch"] or None}]})
    if err:
        return unknown(pid, title, err, as_of=as_of, body=body, facts=facts, **common)
    if not data:
        return nodata(pid, title, **common)
    return panel(pid, title, as_of=as_of, body=body, facts=facts, **common)


RATINGS = ("hate", "dislike", "neutral", "like", "love")


def read_feedback(out_dir: Path) -> dict:
    """Counts computed on the host: messages never reach this Mac. Zero ratings is NO DATA."""
    pid, title = "feedback", "User feedback"
    common = {"as_of_label": "pulled", "max_age": 36 * 3600, "refreshable": True,
              "src": "Rating counts from the host's feedback file. The messages stay on the host."}
    st = read_host_state(out_dir)
    if st is None or st["last_good"] is None:
        err = st["last_attempt"]["error"] if st else None
        return unknown(pid, title, err, **common) if err else nodata(pid, title, **common)
    lg, err = st["last_good"], st["last_attempt"]["error"]
    d = lg["data"]
    if not d["total"]:
        return nodata(pid, title, **common)
    items = [{"l": r, "n": d[r]} for r in RATINGS]
    if d["other"]:
        items.append({"l": "other", "n": d["other"]})
    neg, pos = d["hate"] + d["dislike"], d["like"] + d["love"]
    body = [{"kind": "kpis", "items": [{"n": d["total"], "l": "ratings"}, {"n": d["problems"], "l": "problem reports"}]},
            {"kind": "bars", "items": items,
             "aria": "Ratings: " + ", ".join(f"{i['l']} {i['n']}" for i in items)},
            {"kind": "age", "label": "Latest rating", "epoch": d["newest_epoch"] or None}]
    facts = [f"{neg} negative, {pos} positive, all versions together"]
    p = panel(pid, title, as_of=float(lg["fetched_at"]), body=body, facts=facts, **common)
    if err:
        p["status"], p["error"] = "unknown", ERR[err]
    return p


# ---- panel 8: things that expire ---------------------------------------------------------

def read_expiries(config_list: list, out_dir: Path) -> dict:
    """Dated items from the machine-local config, plus the news file's expiry as the HOST last read it
    (one source: the repo's copy can differ until a deploy). Days left are worked out in the page,
    from the clock. A row with no date says unknown; it never drops out of the list."""
    pid, title = "expiries", "Things that expire"
    rows = []
    for item in config_list if isinstance(config_list, list) else []:
        try:
            d = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            rows.append({"what": str(item["what"]), "epoch": d.timestamp()})
        except (KeyError, TypeError, ValueError):
            rows.append({"what": str(item.get("what", "?")) if isinstance(item, dict) else "?", "epoch": None})
    st = read_host_state(out_dir)
    news = None
    if st and st["last_good"]:
        news = st["last_good"]["data"].get("news_expires_epoch") or None
    rows.append({"what": "News file (re-sign and redeploy)", "epoch": news})
    rows.sort(key=lambda r: (r["epoch"] is None, r["epoch"] or 0))
    return panel(pid, title, stateless=True, body=[{"kind": "expiries", "rows": rows}],
                 facts=["After the news file expires every installed app ignores it."],
                 src="Dates from the private config; the news file's expiry from the last host read.")


# ---- panel 2: website visitors (a link only) ------------------------------------------------

def read_visitors(port: int = 8210) -> dict:
    return panel("visitors", "Website visitors", stateless=True, link=f"http://localhost:{port}/_local/visitors.html",
                 link_note="Opens the GoAccess report; logs in to the host each time",
                 body=[{"kind": "text", "text": "Opens the visitors report (needs the website's docs-site server running)."}],
                 facts=["Every look logs in to the host, so this page never opens it by itself."])
