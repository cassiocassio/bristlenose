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
import atexit
import datetime as dt
import hmac
import http.server
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import signal
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "scripts" / "release-board.template.html"

# The .dmg validity window. The number lives in AlphaBuild.swift (the app
# enforces it); this mirror exists so the board can draw the clock, and
# test-release-board.py asserts the two agree.
DMG_VALIDITY_DAYS = 30
# release.sh writes the heartbeat every BN_HEARTBEAT_SECS (default 300) and calls
# a run stranded after three of them; the page pulses only inside that window.
# Mirror of release.sh's default — pinned by a parity test, like DMG_VALIDITY_DAYS.
HEARTBEAT_CADENCE_S = 300
LOG_TAIL_BYTES = 65536

VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*")

# The board's vocabulary. Anything outside it is a confounded expectation,
# rendered raw and counted — never dropped.
KNOWN_KINDS = {"meta", "step", "check", "gate", "art", "done", "bar", "run", "row", "verify", "clock", "ci"}
LEDGER_STATES = {"ok", "fail", "running", "pending", "skipped"}          # what fold_status accepts for a STEP
RUN_STATES = {"started", "completed"}                                    # the `run` pseudo-step only
CLOCK_NAMES = {"testflight", "dmg"}
STEPS_TBL_VERSION = "# steps.tbl v1"
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


def read_steps(run_dir: Path) -> tuple[list[dict], str, str | None, list[str]]:
    """→ (steps, source, version_line, problems). source: 'steps.tbl' | 'ledger'.
    problems: an unknown version stamp, or rows with fewer than seven fields —
    both are drift and are reported, never silently dropped."""
    p = run_dir / "steps.tbl"
    steps: list[dict] = []
    problems: list[str] = []
    if p.is_file():
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        ver = lines[0] if lines and lines[0].startswith("#") else None
        if ver != STEPS_TBL_VERSION:
            problems.append(f"steps.tbl version stamp is {ver!r}, expected {STEPS_TBL_VERSION!r}")
        for line in lines:
            if not line or line.startswith("#"):
                continue
            parts = line.split("|", 6)
            if len(parts) < 7:
                problems.append(f"steps.tbl row with {len(parts)} fields, not 7: {line[:60]!r}")
                continue
            sid, label, kind, est, tier, cons, cmd = parts
            steps.append({"id": sid, "label": label, "kind": kind, "est": est, "tier": tier, "consequence": cons, "cmd": cmd})
        return steps, "steps.tbl", ver, problems
    return steps, "ledger", None, problems


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
        # A torn last line: release.sh's awk reads it and folds the step it
        # names to `corrupt` (it refuses to advance); the board must say the
        # same, not `pending` (review, 5 Sep 2026). Only a fragment naming a
        # step is folded; an unnamed fragment is counted.
        out["partial"] = True
        frag = lines[-1]
        lines = lines[:-1]
        m = re.search(r'"step"\s*:\s*"([^"]*)"', frag)
        if m:
            out["corrupt"].append(m.group(1))
            out["_partial_step"] = m.group(1)
        else:
            out["unparsed"] += 1
    else:
        lines = [ln for ln in lines if ln != ""]
    for no, raw in enumerate(lines, 1):
        try:
            ev = json.loads(raw)
            if not isinstance(ev, dict):
                raise ValueError("ledger line is not an object")
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
        cur["status"] = status if status in LEDGER_STATES else "corrupt"   # `started`/`completed` are run-only words
        cur["ts"] = ev.get("ts")
        cur["detail"] = ev.get("detail", "")
        m = re.fullmatch(r"attempt (\d+)", cur["detail"] or "")
        if m:
            cur["attempt"] = int(m.group(1))
        m = re.fullmatch(r"(\d+)s", cur["detail"] or "")
        if m and status == "ok":
            cur["elapsed"] = int(m.group(1))
    ps = out.pop("_partial_step", None)
    if ps:
        out["fold"].setdefault(ps, {"status": "pending", "attempt": 0, "elapsed": None, "detail": "", "ts": None})["status"] = "corrupt"
    return out


_IDENTITY = re.compile(r"\b(Apple Distribution|Apple Development|Developer ID Application|Developer ID Installer|3rd Party Mac Developer (?:Application|Installer)|Mac Developer): [^()]+ \(([A-Z0-9]{10})\)")


def scrub(value: str, home: str | None = None) -> str:
    """The sink carries what the build scripts print: `bn_meta identity=`,
    `bn_art signed=`, absolute paths under the home directory, `references Team
    <id>`. context.json is allowlisted (read_context); this is the same rule for
    the other door. Identity CNs collapse to their kind, ten-character team ids
    to <team>, the home directory to ~. Scrubbing is lossy by design — the
    terminal render keeps the originals."""
    if not isinstance(value, str) or not value:
        return value
    v = _IDENTITY.sub(lambda m: f"{m.group(1)}: <identity>", value)
    if home and home.rstrip("/"):   # HOME=/ (a root container) would turn every "/" into "~/"
        v = v.replace(home.rstrip("/") + "/", "~/").replace(home.rstrip("/"), "~")
    if "Team" in v or "team" in v:
        v = re.sub(r"(?i)(team\s+)[A-Z0-9]{10}\b", r"\1<team>", v)
    return v


def scrub_fields(fields: dict, home: str | None) -> dict:
    return {k: (scrub(v, home) if isinstance(v, str) else v) for k, v in fields.items()}


def read_liveness(run_dir: Path) -> dict:
    lock = run_dir / ".lock"
    pid_file = lock / "pid"
    out = {"lock": lock.is_dir(), "pid": None, "alive": None, "heartbeat": None}
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8", errors="replace").strip())
            out["pid"] = pid if 0 < pid < 2**31 else None   # -1 would signal every process; 30 digits overflow os.kill
        except (ValueError, OSError, OverflowError):
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
                if not (946684800 <= epoch <= 4102444800):   # 2000..2100: anything else is not a clock
                    raise ValueError(parts[0])
                age = int(dt.datetime.now(dt.timezone.utc).timestamp()) - epoch
            except ValueError:
                epoch, age = None, None
            out["heartbeat"] = {"state": "present" if epoch else "unparseable", "epoch": epoch, "age_s": age,
                                "cadence_s": HEARTBEAT_CADENCE_S,
                                "step": parts[1] if len(parts) > 1 else None,
                                "elapsed_s": parts[2] if len(parts) > 2 else None,
                                "last_line": scrub(_ANSI.sub("", parts[3])[:100], str(Path.home())) if len(parts) > 3 else ""}
    return out


def read_context(run_dir: Path) -> dict | None:
    p = run_dir / "context.json"
    if not p.is_file():
        return None
    try:
        ctx = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(ctx, dict):
            return None
    except ValueError:
        return {"unparseable": True}
    # The allowlist. context.json's own env allowlist is a bug-report
    # allowlist (signing identity CN, hostname); this file may be attached to
    # things, so it carries neither env nor host.
    return {k: ctx[k] for k in CONTEXT_ALLOWLIST if k in ctx}


_CONF_SCALARS = ("PROJECT_NAME", "PROJECT_DISPLAY", "GH_REPO", "TAP_REPO", "COPR_OWNER", "COPR_PROJECT", "SITE", "DMG_PERMALINK", "CHANGELOG_URL")


def read_conf(conf: Path) -> dict:
    """The channel lists plus the scalars the links are built from, with the
    file's own `${VAR}` references expanded (COPR_PROJECT="${PROJECT_NAME}")."""
    out: dict = {"CHANNELS": [], "CHANNELS_UNPROBEABLE": []}
    if not conf.is_file():
        return out
    raw: dict[str, str] = {}
    for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r'^([A-Z_]+)=(?:"([^"]*)"|\'([^\']*)\'|(\S*))\s*(#.*)?$', line)
        if m:
            raw[m.group(1)] = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4) or "")
    for _ in range(4):
        raw = {k: re.sub(r"\$\{([A-Z_]+)\}", lambda mm: raw.get(mm.group(1), ""), v) for k, v in raw.items()}
    for k in ("CHANNELS", "CHANNELS_UNPROBEABLE"):
        out[k] = raw.get(k, "").split()
    for k in _CONF_SCALARS:
        if raw.get(k):
            out[k] = raw[k]
    return out


_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_RUN_ID = re.compile(r"^\d{1,20}$")


def https(url: str | None) -> str | None:
    """Every href on the board passes through here: https only, and never a
    string that came out of the sink or the ledger unvalidated."""
    return url if url and url.startswith("https://") and not any(c in url for c in ' <>"\'') else None


def build_links(conf: dict, version: str, ci_sha: str | None) -> dict:
    """Pointers, not claims: where each channel's public page is, the commit,
    the release tag. Built from project.conf constants and validated ids only."""
    name, site = conf.get("PROJECT_NAME"), conf.get("SITE")
    repo, tap = conf.get("GH_REPO"), conf.get("TAP_REPO")
    out: dict = {"channels": {}}
    if name:
        out["channels"]["pypi"] = f"https://pypi.org/project/{name}/{version}/"
        out["channels"]["snap"] = f"https://snapcraft.io/{name}"
    if repo:
        out["repo"] = f"https://github.com/{repo}"
        out["channels"]["github"] = f"https://github.com/{repo}/releases/tag/v{version}"
        out["tag"] = out["channels"]["github"]
        out["actions"] = f"https://github.com/{repo}/actions"
        if ci_sha and _SHA.match(ci_sha):
            out["ci_sha"] = f"https://github.com/{repo}/commit/{ci_sha}"
            out["ratchets"] = f"https://github.com/{repo}/blob/{ci_sha}/docs/testing/ratchet.json"
    if tap and name:
        out["channels"]["homebrew"] = f"https://github.com/{tap}/blob/main/Formula/{name}.rb"
    if conf.get("COPR_OWNER") and conf.get("COPR_PROJECT"):
        out["channels"]["copr"] = f"https://copr.fedorainfracloud.org/coprs/{conf['COPR_OWNER']}/{conf['COPR_PROJECT']}/"
    if conf.get("DMG_PERMALINK"):
        out["channels"]["dmg"] = conf["DMG_PERMALINK"]
    if conf.get("CHANGELOG_URL"):
        out["channels"]["website"] = conf["CHANGELOG_URL"]
    elif site:
        out["channels"]["website"] = f"https://{site}/"
    out["channels"]["testflight"] = "https://appstoreconnect.apple.com/apps"
    withheld = [f"project.conf {k} is not an https url — link withheld" for k in ("DMG_PERMALINK", "CHANGELOG_URL") if conf.get(k) and not https(conf[k])]
    out["channels"] = {k: v for k, v in ((k, https(v)) for k, v in out["channels"].items()) if v}
    out = {k: (https(v) if isinstance(v, str) else v) for k, v in out.items()}
    out["withheld"] = withheld
    return out


def sha_url(conf: dict, sha: str | None) -> str | None:
    repo = conf.get("GH_REPO")
    return https(f"https://github.com/{repo}/commit/{sha}") if repo and sha and _SHA.match(sha) else None


def run_url(conf: dict, run_id: str | None) -> str | None:
    repo = conf.get("GH_REPO")
    return https(f"https://github.com/{repo}/actions/runs/{run_id}") if repo and run_id and _RUN_ID.match(str(run_id)) else None


def read_ratchet(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    rows = []
    if not isinstance(data, dict):
        return []
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
    events, unparsed, partial = bn_events.parse_stream(bn_events.read_sink_text(p))
    home = str(Path.home())
    out["events"] = [{"line": no, "kind": kind, **scrub_fields(fields, home)} for no, kind, fields in events]
    out["unparsed"] = [{"line": no, "raw": raw[:200]} for no, raw in unparsed]
    out["partial"] = partial
    return out


def tail_lines(path: Path, n: int = 12, span: int = LOG_TAIL_BYTES) -> list[str]:
    """The last n lines by seeking, never by reading the file: a `gh run watch`
    transcript grows to megabytes over a 38-minute gate and the live server
    re-reads a running step's log on every write (perf review, 5 Sep 2026)."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - span))
        chunk = fh.read()
    text = chunk.decode("utf-8", errors="replace").replace("\r", "\n")
    lines = [_ANSI.sub("", ln) for ln in text.split("\n")]
    if size > span and lines:
        lines = lines[1:]  # the first line of a mid-file chunk is a fragment
    lines = ["".join(ch for ch in ln if ch >= " " and ch != "\x7f" and not ("\x80" <= ch <= "\x9f"))[:200] for ln in lines if ln.strip()]
    return lines[-n:]


def read_logs(run_dir: Path, steps_needed: list[str], with_logs: bool, root: Path = ROOT) -> dict:
    """→ {step_id: entry}, plus "_problems": [str] when logs/ could not be listed —
    "no log" and "could not read logs/" are different states (silent-failure
    review, 5 Sep 2026)."""
    logdir = run_dir / "logs"
    out: dict = {}
    problems: list[str] = []
    names: list[str] = []
    if logdir.exists():
        try:
            names = sorted(os.listdir(logdir))
        except OSError as e:
            problems.append(f"logs/ could not be listed ({type(e).__name__}) — every lane's output line is unknown, not absent")
    for sid in steps_needed:
        attempts = sorted((logdir / nm for nm in names if nm.startswith(f"{sid}.") and nm.endswith(".log")),
                          key=lambda q: int(q.stem.split(".")[-1]) if q.stem.split(".")[-1].isdigit() else 0)
        if not attempts:
            continue
        newest = attempts[-1]
        try:
            entry = {"path": str(newest.relative_to(root)) if str(newest).startswith(str(root)) else f"{run_dir.name}/logs/{newest.name}",
                     "attempts": len(attempts), "size": newest.stat().st_size}
            if with_logs:
                entry["tail"] = [scrub(ln, str(Path.home())) for ln in tail_lines(newest)]
        except OSError as e:
            problems.append(f"{newest.name} could not be read ({type(e).__name__})")
            continue
        out[sid] = entry
    if problems:
        out["_problems"] = problems
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
                # A batch is the driver's `preflight` window when one brackets this
                # row (exact — the driver wrote it); only a standalone preflight, run
                # by hand under a sink, falls back to "a repeated label starts a new
                # batch". The old rule alone split a real preflight in two on a
                # label the preflight emits twice (review, 5 Sep 2026).
                win = None
                for w in reversed(windows):
                    if w["id"] == "preflight" and w["start_line"] is not None and w["start_line"] < ev["line"] and (w["end_line"] is None or ev["line"] < w["end_line"]):
                        win = w
                        break
                batch = preflight_batches[-1]
                if win is not None:
                    if batch and batch[0].get("_window") != id(win):
                        preflight_batches.append([])
                        batch = preflight_batches[-1]
                    ev["_window"] = id(win)
                elif any(r.get("label") == ev.get("label") for r in batch):
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
            if ev.get("name") not in CLOCK_NAMES:
                new_shape.append({"line": ev["line"], "kind": "clock", "field": "name", "value": ev.get("name")})
            clocks[ev.get("name", "?")] = ev
        elif kind == "ci":
            if ev.get("result") not in CI_RESULTS:
                new_shape.append({"line": ev["line"], "kind": "ci", "field": "result", "value": ev.get("result")})
            ci.append(ev)
    return {"windows": windows, "driver_runs": driver_runs, "preflight_batches": preflight_batches,
            "verify_batches": verify_batches, "clocks": clocks, "ci": ci, "meta": meta,
            "unknown_kinds": unknown_kinds, "new_shape": new_shape}


def lane_ids(steps: list[dict]) -> list[str]:
    """The build lanes are the steps whose command is a desktop build script —
    read from steps.tbl, not hardcoded (principle 4). The fallback names the
    two the table has carried since 27 Aug 2026, for runs that predate it."""
    ids = [s["id"] for s in steps if re.search(r"desktop/scripts/build-[a-z-]+\.sh", s.get("cmd", ""))]
    return ids or ["build-all", "build-dmg"]


def source_emits(root: Path, cmd: str) -> bool | str:
    """Does the lane's script, as it stands in the tree TODAY, report steps
    through report.sh? Read, not inferred: the file is grepped for bn_autowrap.
    None when the command names no readable file. The tree now is not the tree
    at the time of the run, which the wording says."""
    m = re.search(r"(desktop/scripts/[a-z-]+\.sh)", cmd or "")
    if not m:
        return "no-script"
    p = root / m.group(1)
    if not p.is_file():
        return "absent"
    try:
        return "bn_autowrap" in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unreadable"


def build_pane(grouped: dict, ledger: dict, steps: list[dict], previous: dict | None, root: Path = ROOT, logs: dict | None = None) -> dict:
    """The build steps, from the sink's child events inside the driver's window for
    each lane. States: not-run · skipped · failed-no-window · ran-no-sink (the
    ledger says it ran; the sink has no @bn lines from it) · running-no-sink · data."""
    lanes = lane_ids(steps)
    windows = [w for w in grouped["windows"] if w["id"] in lanes]
    fold = ledger["fold"]
    prev_children = (previous or {}).get("lanes_with_children", set())
    cmds = {s["id"]: s.get("cmd", "") for s in steps}
    out = {"lanes": [], "lane_ids": lanes}
    for lane_id in lanes:
        ws = [w for w in windows if w["id"] == lane_id]
        ledger_state = fold.get(lane_id, {}).get("status")
        # a run without steps.tbl names no command; the lane is named after its script
        common = {"source_emits": source_emits(root, cmds.get(lane_id) or f"desktop/scripts/{lane_id}.sh"), "log": (logs or {}).get(lane_id)}
        if not ws:
            if ledger_state in (None, "pending"):
                state = "not-run"
            elif ledger_state == "skipped":
                state = "skipped"
            elif ledger_state == "fail":
                state = "failed-no-window"
            else:
                state = "ran-no-sink"
            out["lanes"].append({"id": lane_id, "state": state, "ledger_state": ledger_state, "steps": [], "checks": [], "gates": [], "arts": [],
                                 "emits_known": lane_id in prev_children, **common})
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
                        _el = float(ev["elapsed"]) if ev.get("elapsed") else None
                    except ValueError:
                        _el = None
                    # a non-finite value would reach the page as bare NaN and break JSON.parse for the whole board
                    st["elapsed"] = _el if _el is not None and math.isfinite(_el) else None
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
                             "checks": checks, "gates": gates, "arts": arts, "emits_known": lane_id in prev_children or bool(w["children"]), **common})
    return out


def channels_pane(conf: dict, grouped: dict, sink_as_of: str | None, version: str | None = None) -> dict:
    batches = grouped["verify_batches"]
    latest = batches[-1] if batches else None
    # A verify records the version it probed. `release.sh verify` with no
    # argument probes the TREE's version and writes into the newest run dir, so
    # the two can differ; a batch for another version is not this run's truth.
    mismatch = None
    if latest:
        probed = (latest.get("start") or latest.get("done") or {}).get("version")
        if version and probed and probed != version:
            mismatch = probed
    rows = {} if mismatch else {r.get("label"): r for r in (latest["rows"] if latest else [])}
    complete = bool(latest and latest.get("done")) and not mismatch
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
    batch_as_of = None
    if latest:
        stamps = [r.get("ts") for r in latest["rows"] if r.get("ts")] + [(latest.get("done") or {}).get("ts")]
        batch_as_of = max((s for s in stamps if s), default=None)
    return {"cards": cards, "extras": extras, "complete": complete, "batches": len(batches),
            "partial_rows": len(rows) if latest and not complete else 0, "rollup": rollup,
            "as_of": batch_as_of, "version_mismatch": mismatch}


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


def ci_pane(grouped: dict, ci_sha: str | None, conf: dict | None = None) -> dict:
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
    job_rows = []
    for j in jobs:
        m = re.fullmatch(r"(\w[\w-]*) \((\d+\.\d+), ([a-z]+)-[a-z0-9.]+\)", j.get("job", ""))
        if m:
            matrix.append({"job": m.group(1), "python": m.group(2), "os": m.group(3), "result": j.get("result")})
        job_rows.append({"job": j.get("job"), "result": j.get("result"), "workflow": j.get("workflow"), "matrix": bool(m)})
    # No "sha matches" claim: `status` writes sha= from the same ci-sha file the
    # board reads, so a comparison would be a file against a copy of itself.
    conf = conf or {}
    return {"state": "data", "runs": [{"workflow": r.get("workflow"), "run_id": r.get("run_id"), "sha": r.get("sha"), "branch": r.get("branch"), "result": r.get("result"), "as_of": r.get("ts"),
                                       "url": run_url(conf, r.get("run_id")), "sha_url": sha_url(conf, r.get("sha"))} for r in runs],
            "jobs": job_rows, "matrix": matrix, "ci_sha": ci_sha}


def preflight_pane(grouped: dict) -> dict:
    batches = [b for b in grouped["preflight_batches"] if b]
    if not batches:
        wins = [w for w in grouped["windows"] if w["id"] == "preflight"]
        if wins:
            return {"state": "ran-no-sink", "rows": [], "counts": {}, "attempt": wins[-1]["attempt"], "rc": wins[-1]["rc"]}
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


def events_total(ledger: dict, sink: dict) -> int:
    return len(ledger["events"]) + len(sink["events"])


def activity(ledger: dict, sink: dict) -> dict:
    stamps = [ev.get("ts") for ev in ledger["events"]] + [ev.get("ts") for ev in sink["events"]]
    stamps = [s for s in stamps if s]
    if not stamps:
        return {"minutes": [], "start": None}
    parsed = []
    bad = 0
    for s in stamps:
        try:
            parsed.append(dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            bad += 1
    if not parsed:
        return {"minutes": [], "start": None, "unparseable": bad, "span_minutes": 0, "bin_minutes": 1}
    t0 = min(parsed).replace(second=0)
    full = int((max(parsed) - t0).total_seconds() // 60) + 1
    # Bin adaptively: at most 600 bins across the whole span, so a five-day run
    # is 600 bins of 12 minutes rather than its first 600 minutes (which the
    # strip then reported as truncated, 5 Sep 2026). Nothing is dropped.
    bin_minutes = max(1, -(-full // 600))
    counts = [0] * (-(-full // bin_minutes))
    for t in parsed:
        counts[int((t - t0).total_seconds() // 60) // bin_minutes] += 1
    return {"minutes": counts, "start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "unparseable": bad,
            "span_minutes": full, "bin_minutes": bin_minutes}


def confounded(steps: list[dict], steps_source: str, stations: list[dict], unknown_steps: list[str], grouped: dict,
               channels: dict, preflight: dict, ledger: dict, sink: dict, previous: dict | None,
               steps_problems: list[str] | None = None, build: dict | None = None, act: dict | None = None) -> dict:
    log = {"unknown": [], "new_shape": [], "missing": [], "changed": [], "computable": True, "notes": []}
    if steps_source != "steps.tbl":
        log["computable"] = False
        log["notes"].append("no steps.tbl — the run predates the snapshot (5 Sep 2026); stations are the ledger's own step ids in first-seen order")
    for pr in (steps_problems or []):
        log["unknown"].append({"what": pr, "line": None, "raw": ""})
    standalone = [w for w in grouped["windows"] if w["id"] == "standalone"]
    if standalone and standalone[0]["children"]:
        log["notes"].append(f"{len(standalone[0]['children'])} child @bn line(s) fell outside every rendered lane (a gate run standalone, or lines inside the preflight window) — counted, not drawn")
    if channels.get("version_mismatch"):
        log["new_shape"].append({"what": f"latest verify probed {channels['version_mismatch']}, not this run — its rows are not shown", "line": None})
    if act and act.get("unparseable"):
        log["unknown"].append({"what": f"{act['unparseable']} timestamp(s) not in the sink's own format, excluded from the activity strip", "line": None, "raw": ""})
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
    for lane in (build or {}).get("lanes", []):
        # A closed window with no child lines is "missing" only when the lane's
        # script is KNOWN to emit @bn lines (it did on this or a previous run).
        # build-dmg.sh does not report steps, and a permanent entry for that is
        # the gate that cries wolf (review, 5 Sep 2026).
        if lane["state"] == "ran-no-sink" and lane.get("attempt") is not None and lane.get("emits_known"):
            log["missing"].append({"what": f"driver window for '{lane['id']}' (attempt {lane['attempt']}) closed with zero child lines, and this script has emitted before — BN_REPORT=0, an unwritable sink, or a lost export"})
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
    """The newest run dir OLDER than this one that carries a steps.tbl — the diff
    base. Drawing an old run must not diff it against a newer one and call the
    difference "since" (review, 5 Sep 2026)."""
    this = release_dir / version / "events.jsonl"
    this_m = this.stat().st_mtime if this.is_file() else float("inf")
    cands = [d for d in release_dir.glob("*/") if d.is_dir() and d.name != version and (d / "steps.tbl").is_file() and (d / "events.jsonl").is_file()
             and (d / "events.jsonl").stat().st_mtime < this_m]
    if not cands:
        return None
    cands.sort(key=lambda d: (d / "events.jsonl").stat().st_mtime, reverse=True)
    d = cands[0]
    steps, _, _, _ = read_steps(d)
    sink = read_sink(d)
    chans = sorted({ev.get("label") for ev in sink["events"] if ev["kind"] == "row" and ev.get("src") == "verify" and ev.get("label") in conf["CHANNELS"]})
    grouped = group_sink(sink, steps)
    with_children = {w["id"] for w in grouped["windows"] if w["children"] and w["id"] != "standalone"}
    return {"version": d.name, "steps": steps, "channels": chans or conf["CHANNELS"], "lanes_with_children": with_children}


_UNSET: dict = {"_unset": True}


def build_model(root: Path, version: str, with_logs: bool, narrate=lambda s: None, liveness_override: dict | None = None,
                previous: dict | None = _UNSET) -> dict:
    release_dir = root / ".release"
    run_dir = release_dir / version
    steps, steps_source, steps_ver, steps_problems = read_steps(run_dir)
    ledger = read_ledger(run_dir)
    liveness = liveness_override or read_liveness(run_dir)
    sink = read_sink(run_dir)
    conf = read_conf(root / "scripts" / "project.conf")
    stations, unknown_steps = fold_stations(steps, ledger, liveness, steps_source)
    grouped = group_sink(sink, steps if steps_source == "steps.tbl" else [{"id": s["id"]} for s in stations])
    ci_sha = (run_dir / "ci-sha").read_text(encoding="utf-8", errors="replace").strip() if (run_dir / "ci-sha").is_file() else None
    if ci_sha and not re.fullmatch(r"[0-9a-f]{40}", ci_sha):
        ci_sha = None
    prev = previous if previous is not _UNSET else previous_run(release_dir, version, conf)
    channels = channels_pane(conf, grouped, sink["as_of"], version)
    preflight = preflight_pane(grouped)
    ci = ci_pane(grouped, ci_sha, conf)
    links = build_links(conf, version, ci_sha)
    for c in channels["cards"]:
        c["url"] = links["channels"].get(c["name"])
    clocks = clocks_pane(grouped)
    needing_logs = [s["id"] for s in stations if s["state"] in ("fail", "running", "stranded", "corrupt")]
    lane_logs = read_logs(run_dir, [ln for ln in lane_ids(steps) if ln not in needing_logs], False, root)
    logs = read_logs(run_dir, needing_logs, with_logs, root)
    steps_problems = list(steps_problems) + lane_logs.pop("_problems", []) + logs.pop("_problems", []) + links.get("withheld", [])
    build = build_pane(grouped, ledger, steps, prev, root, {**lane_logs, **logs})
    act = activity(ledger, sink)
    conf_log = confounded(steps, steps_source, stations, unknown_steps, grouped, channels, preflight, ledger, sink, prev,
                          steps_problems, build, act)
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
        "run_dir": str(run_dir.relative_to(root)) if str(run_dir).startswith(str(root)) else run_dir.name,
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
        "links": links,
        "channels": channels,
        "clocks": clocks,
        "events": merged_events(ledger, sink),
        "events_total": events_total(ledger, sink),
        "activity": act,
        "logs": logs,
        "sink": {"present": sink["present"], "events": len(sink["events"]), "unparsed": len(sink["unparsed"]),
                 "partial": sink["partial"], "as_of": sink["as_of"], "driver_runs": len(grouped["driver_runs"]),
                 "meta": {k: v for k, v in grouped["meta"].items() if k in ("title", "done_title", "bundle")}},
        "confounded": conf_log,
        "previous": prev["version"] if prev else None,
    }
    return model


# ── output ───────────────────────────────────────────────────────────────────

def inline_json(model: dict) -> str:
    """ensure_ascii is NOT enough — `<`, `>` and `&` are ASCII and pass through, so a
    literal </script> in evidence text would break out of the data block
    (CLAUDE.md, the export-JSON gotcha)."""
    s = json.dumps(model, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


_SINK_TS = re.compile(r"\bts=(\S+)")


def replay_frames(root: Path, version: str) -> list[dict]:
    """The board at every moment of a finished run: frame i is the real generator
    run on the first i ledger lines (and the sink lines stamped no later than
    the i-th), in a throwaway copy of the run dir. Liveness is the one thing a
    replay cannot read — a step left running by a prefix is shown as running,
    and the frame says so. There is no previous run in the copy, so the
    confounded log's "changed" section is empty in every frame."""
    run_dir = root / ".release" / version
    ledger = [ln for ln in (run_dir / "events.jsonl").read_text(encoding="utf-8", errors="replace").split("\n") if ln.strip()]
    sink_path = run_dir / "bn-events.log"
    sink = bn_events.read_sink_text(sink_path).split("\n") if sink_path.is_file() else []
    sink = [ln for ln in sink if ln.strip()]
    frames = []
    with tempfile.TemporaryDirectory(prefix=".rb-replay-", dir=run_dir.parent) as tmp:   # a leftover from a crash lands inside .release/, not /tmp
        troot = Path(tmp)
        (troot / "scripts").mkdir()
        (troot / "docs" / "testing").mkdir(parents=True)
        for rel in ("scripts/project.conf", "docs/testing/ratchet.json"):
            if (root / rel).is_file():
                shutil.copy(root / rel, troot / rel)
        trun = troot / ".release" / version
        shutil.copytree(run_dir, trun, ignore=shutil.ignore_patterns("board*.html", "board*.json", ".lock"))
        upto = None
        for i in range(len(ledger) + 1):
            prefix = ledger[:i]
            (trun / "events.jsonl").write_text("".join(ln + "\n" for ln in prefix), encoding="utf-8")
            if prefix:
                try:
                    upto = json.loads(prefix[-1]).get("ts") or upto   # an unparseable line keeps the last horizon
                except ValueError:
                    pass
            excluded = 0
            if sink:
                if i == len(ledger):
                    keep = sink  # the last frame IS the board: the whole sink, late verifies included
                else:
                    keep = [ln for ln in sink if (m := _SINK_TS.search(ln)) and upto and m.group(1) <= upto]
                excluded = len(sink) - len(keep)
                (trun / "bn-events.log").write_text("".join(ln + "\n" for ln in keep), encoding="utf-8")
            fold = read_ledger(trun)["fold"]
            running = any(f.get("status") == "running" for f in fold.values())
            live = {"lock": running and i < len(ledger), "pid": None, "alive": running and i < len(ledger), "heartbeat": None, "replay": True}
            model = build_model(troot, version, False, liveness_override=live)
            model["now"] = upto   # the frame's clock: a running station's elapsed counts from here, not from today
            caption = "before the first event"
            if prefix:
                try:
                    e = json.loads(prefix[-1])
                    caption = f"{e.get('ts', '')}  {e.get('step', '?')} {e.get('status', '?')}  {e.get('detail', '')}".strip()
                except ValueError:
                    caption = "(unparseable ledger line)"
            if excluded:
                caption += f"  · {excluded} sink line(s) beyond this frame"
            frames.append({"i": i, "of": len(ledger), "caption": caption, "model": model})
    return frames


def render_html(model: dict, template: Path) -> str:
    tpl = template.read_text(encoding="utf-8")
    if "__BOARD_JSON__" not in tpl:
        raise RuntimeError(f"template {template} carries no __BOARD_JSON__ marker")
    return tpl.replace("__BOARD_JSON__", inline_json(model), 1)


def write_private(path: Path, text: str) -> None:
    """0600, atomic, and never through a symlink: written to a sibling temp file
    (O_EXCL|O_NOFOLLOW, fchmod on the fd) and renamed into place, so a reader —
    a browser reloading, a poller — never sees a half file, and a symlink at the
    destination is replaced rather than followed. The house standard for
    credential-class files (telemetry.py, MCPHandshake)."""
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── the live server ──────────────────────────────────────────────────────────
#
# Transport only. It watches the run dir, rebuilds the model when a file the
# train writes changes, and serves the page, board.json and an SSE tick on
# loopback. It knows the generator and the run dir; the writers know nothing of
# it (docs/design-release-board.md §1 — the scripts must never need the board).
#
# Loopback is not a boundary between users or processes on one Mac, so every
# request carries a per-run token minted at start and written only into the
# 0600 handshake (security review, 5 Sep 2026) — the house pattern of serve
# mode's auth token and the scoped /mcp bearer.

BOARD_SERVER_FILE = "board-server.json"
DEFAULT_PORT = 8151          # deterministic so the browser's saved layout (keyed by origin) survives a restart
DEFAULT_IDLE_S = 4 * 3600    # the server owns its own life: no request for this long → exit
RUN_DIR_GONE_S = 60          # …and the run dir's ledger missing for this long → exit
_HOSTS = ("127.0.0.1", "localhost", "[::1]")


class BoardState:
    """The current model, rebuilt when the run dir's watched files move."""

    def __init__(self, root: Path, version: str, poll_s: float = 1.0, with_logs: bool = False, token: str | None = None) -> None:
        self.root, self.version, self.poll_s, self.with_logs = root, version, max(0.05, poll_s), with_logs
        self.token = token or secrets.token_urlsafe(32)
        self.run_dir = root / ".release" / version
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.generation = 0
        self.model: dict | None = None
        self.error: str | None = None
        self.stamp: tuple | None = None
        self.changed_at: str | None = None
        self.last_request = time.monotonic()
        self.gone_since: float | None = None
        self.exit_reason: str | None = None
        self.request_exit = lambda reason: None   # serve_board wires this to httpd.shutdown
        self._stop = threading.Event()
        # the previous run cannot change while this one is live: read it once
        try:
            conf = read_conf(root / "scripts" / "project.conf")
            self.previous = previous_run(root / ".release", version, conf)
        except Exception:
            self.previous = None

    def newest(self) -> tuple:
        """(name, mtime_ns, size) of every watched file — size too, since two writes
        inside one mtime tick are common on a fast step."""
        out = []
        for p in (self.run_dir / "events.jsonl", self.run_dir / "bn-events.log", self.run_dir / "heartbeat",
                  self.run_dir / "steps.tbl", self.run_dir / "ci-sha", self.run_dir / "context.json", self.run_dir / ".lock" / "pid"):
            try:
                st = p.stat()
                out.append((p.name, st.st_mtime_ns, st.st_size))
            except OSError:
                out.append((p.name, None, None))
        logs = self.run_dir / "logs"
        try:
            with os.scandir(logs) as it:
                for e in sorted(it, key=lambda e: e.name):
                    if e.name.endswith(".log"):
                        try:
                            st = e.stat()
                            out.append((e.name, st.st_mtime_ns, st.st_size))
                        except OSError:
                            pass
        except OSError:
            pass
        return tuple(out)

    def _ledger_torn(self) -> bool:
        """A read that lands mid-append would fold the step to corrupt and flash
        the run stranded for one poll. If the ledger does not end in a newline,
        wait for the next tick instead of publishing (fresh-eyes review)."""
        try:
            with open(self.run_dir / "events.jsonl", "rb") as fh:
                fh.seek(0, os.SEEK_END)
                if fh.tell() == 0:
                    return False
                fh.seek(-1, os.SEEK_END)
                return fh.read(1) != b"\n"
        except OSError:
            return False

    def _publish(self, model: dict | None, err: str | None, st: tuple | None) -> None:
        with self.cond:
            if st is not None:
                self.stamp = st
            self.generation += 1
            if model is not None:
                self.model = model
            self.error = err
            self.changed_at = utc_now()
            if self.model is not None:
                self.model["live"] = {"generation": self.generation, "poll_ms": int(self.poll_s * 1000), "changed_at": self.changed_at,
                                      "served_at": self.changed_at, "error": self.error, "token": self.token, "with_logs": self.with_logs}
            self.cond.notify_all()

    def refresh(self, force: bool = False) -> bool:
        st = self.newest()
        if not force and st == self.stamp and self.model is not None:
            return False
        if not force and self.model is not None and self._ledger_torn():
            return False   # a write in progress: next tick
        try:
            if not (self.run_dir / "events.jsonl").is_file():
                raise FileNotFoundError(f"{self.run_dir.name}/events.jsonl is gone — the run dir lost its ledger")
            model = build_model(self.root, self.version, self.with_logs, previous=self.previous)
            err = None
        except Exception as e:  # the last good model stays; the page says why
            model, err = None, scrub(f"{type(e).__name__}: {e}", str(Path.home()))
        self._publish(model, err, st)
        return True

    def watch(self, idle_s: float | None = None) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception as e:  # a dead watcher must be a visible state, not a stale 200
                self._publish(None, scrub(f"watcher: {type(e).__name__}: {e}", str(Path.home())), None)
            now = time.monotonic()
            if (self.run_dir / "events.jsonl").is_file():
                self.gone_since = None
            else:
                self.gone_since = self.gone_since or now
                if now - self.gone_since > RUN_DIR_GONE_S:
                    self.exit_reason = "run dir gone"
                    self.request_exit(self.exit_reason)
                    break
            if idle_s and now - self.last_request > idle_s:
                self.exit_reason = "idle"
                self.request_exit(self.exit_reason)
                break
            self._stop.wait(self.poll_s)

    def stop(self) -> None:
        self._stop.set()
        with self.cond:
            self.cond.notify_all()

    def wait_change(self, seen: int, timeout: float) -> int:
        with self.cond:
            self.cond.wait_for(lambda: self.generation != seen or self._stop.is_set(), timeout)
            return self.generation

    def snapshot(self) -> tuple[dict | None, str | None]:
        """The model with served_at stamped NOW: the page reads staleness as
        "no successful pull", not "nothing changed" (silent-failure review)."""
        with self.lock:
            if self.model is None:
                return None, self.error
            m = dict(self.model)
            m["live"] = {**m["live"], "served_at": utc_now()}
            return m, self.error


class BoardHandler(http.server.BaseHTTPRequestHandler):
    state: BoardState  # set on the server class
    server_version = "release-board/1"
    sys_version = ""
    timeout = 30                      # a connection that sends nothing does not hold a thread
    sse_slots = threading.BoundedSemaphore(16)

    def log_message(self, fmt, *args):  # request lines are noise on a loopback tool
        return

    def log_error(self, fmt, *args):    # errors still reach stderr (log_error delegates to log_message by default)
        sys.stderr.write("  board: " + (fmt % args) + "\n")

    def _headers(self, code: int, ctype: str, length: int | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip()
        bare = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        return bare in _HOSTS

    def _token_ok(self, query: str) -> bool:
        given = ""
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            given = auth[7:].strip()
        else:
            given = (urllib.parse.parse_qs(query).get("k") or [""])[0]
        return bool(given) and hmac.compare_digest(given, self.state.token)

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self._headers(code, ctype, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._host_ok():  # DNS rebinding: a page on another origin naming this port by a hostname
            self._send(400, "text/plain; charset=utf-8", b"")
            return
        path, _, query = self.path.partition("?")
        if not self._token_ok(query):   # no token, wrong token: as if nothing were here
            self._send(404, "text/plain; charset=utf-8", b"")
            return
        st = self.state
        st.last_request = time.monotonic()
        if path in ("/", "/board.html"):
            model, err = st.snapshot()
            if model is None:
                self._send(503, "text/plain; charset=utf-8", f"no model yet — {err or 'first build pending'}".encode())
                return
            try:
                body = render_html(model, TEMPLATE).encode("utf-8")
            except Exception as e:
                self._send(500, "text/plain; charset=utf-8", f"render failed — {type(e).__name__}: {e}".encode())
                return
            self._send(200, "text/html; charset=utf-8", body)
        elif path == "/board.json":
            model, err = st.snapshot()
            body = json.dumps(model if model is not None else {"error": err}, ensure_ascii=True, allow_nan=False).encode("utf-8")
            self._send(200 if model is not None else 503, "application/json; charset=utf-8", body)
        elif path == "/health":
            with st.lock:
                body = json.dumps({"generation": st.generation, "version": st.version, "error": st.error, "changed_at": st.changed_at}).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
        elif path == "/events":
            if not self.sse_slots.acquire(blocking=False):
                self._send(503, "text/plain; charset=utf-8", b"too many event streams")
                return
            try:
                self._headers(200, "text/event-stream; charset=utf-8")
                seen = -1
                while True:
                    gen = st.wait_change(seen, 15.0)
                    if st._stop.is_set():
                        break
                    if gen != seen:
                        seen = gen
                        self.wfile.write(f"data: {gen}\n\n".encode("ascii"))
                    else:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    st.last_request = time.monotonic()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
            finally:
                self.sse_slots.release()
        else:
            self._send(404, "text/plain; charset=utf-8", b"")


class BoardServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(root: Path, version: str, port: int = 0, poll_s: float = 1.0, with_logs: bool = False,
                token: str | None = None, idle_s: float | None = None) -> tuple[BoardServer, BoardState, threading.Thread]:
    """Bind loopback, build the first model, start the watcher. The caller
    serves (serve_forever) and stops (shutdown + state.stop)."""
    state = BoardState(root, version, poll_s, with_logs, token)
    state.refresh(force=True)
    handler = type("Handler", (BoardHandler,), {"state": state, "sse_slots": threading.BoundedSemaphore(16)})
    httpd = BoardServer(("127.0.0.1", port), handler)
    watcher = threading.Thread(target=state.watch, kwargs={"idle_s": idle_s}, name="board-watch", daemon=True)
    watcher.start()
    return httpd, state, watcher


def write_handshake(run_dir: Path, port: int, version: str, token: str) -> Path:
    """The one file the driver may read: where the board is, whose it is, and
    the token that opens it. 0600, so only this user's processes can read it.
    release.sh prints the url when this exists and the pid is alive; it never
    starts, waits on, or fails because of the server."""
    p = run_dir / BOARD_SERVER_FILE
    write_private(p, json.dumps({"schema": 2, "url": f"http://127.0.0.1:{port}/?k={token}", "port": port, "pid": os.getpid(),
                                 "token": token, "version": version, "started": utc_now()}, indent=1))
    return p


def remove_handshake(p: Path) -> None:
    try:
        if json.loads(p.read_text(encoding="utf-8", errors="replace")).get("pid") == os.getpid():
            p.unlink()
    except (OSError, ValueError):
        pass


def serve_board(root: Path, version: str, port: int, poll_s: float, with_logs: bool, idle_s: float) -> int:
    run_dir = root / ".release" / version
    try:
        httpd, state, _ = make_server(root, version, port, poll_s, with_logs, idle_s=idle_s)
    except OSError as e:
        sys.stderr.write(f"error: cannot bind 127.0.0.1:{port} ({e.strerror or e}) — another board, or pass --port\n")
        return 1
    actual = httpd.server_address[1]
    hs = write_handshake(run_dir, actual, version, state.token)
    atexit.register(remove_handshake, hs)

    def _stop(*_):
        state.stop()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    state.request_exit = lambda reason: _stop()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    sys.stderr.write(f"  board: http://127.0.0.1:{actual}/?k={state.token}  ·  {version}  ·  loopback + per-run token"
                     f"{'  ·  carries log tails' if with_logs else ''}  ·  exits after {int(idle_s // 3600)}h idle  ·  ^C stops\n")
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        state.stop()
        remove_handshake(hs)
        httpd.server_close()
        if state.exit_reason:
            sys.stderr.write(f"  board: stopped — {state.exit_reason}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="draw the release board for a run under .release/")
    ap.add_argument("version", nargs="?", help="X.Y.Z; default: the newest run under .release/")
    ap.add_argument("--out", type=Path, help="directory for board.json + board.html (default: the run dir)")
    ap.add_argument("--with-logs", action="store_true", help="also write board-with-logs.html carrying raw log tails — do not attach it to anything")
    ap.add_argument("--json", action="store_true", help="print board.json to stdout instead of writing files")
    ap.add_argument("--replay", action="store_true", help="write board-replay.html: the board at every ledger line, with back/forward controls (design tool — not a live view)")
    ap.add_argument("--serve", action="store_true", help="serve the board live on loopback with a per-run token: the page patches itself as the run dir changes; add --with-logs for tails")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"with --serve: port (default {DEFAULT_PORT}; 0 = a free one, but the browser's saved layout is keyed by origin)")
    ap.add_argument("--poll", type=float, default=1.0, help="with --serve: seconds between run-dir checks")
    ap.add_argument("--idle", type=float, default=DEFAULT_IDLE_S, help="with --serve: exit after this many seconds without a request")
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
    if args.serve:
        if args.poll <= 0:
            ap.error("--poll must be > 0")
        return serve_board(root, version, args.port, args.poll, args.with_logs, args.idle)
    if args.replay:
        if (run_dir / ".lock" / "pid").is_file():
            sys.stderr.write("  note: this run has a lock — a replay of a live run copies files mid-write; frames may be torn\n")
        out = (args.out or run_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        frames = replay_frames(root, version)
        write_private(out / "board-replay.html", render_html({"replay": frames, "version": version}, TEMPLATE))
        sys.stderr.write(f"  wrote {out / 'board-replay.html'}  ·  {version}  ·  {len(frames)} frames\n")
        return 0
    model = build_model(root, version, args.with_logs, narrate)
    if args.json:
        print(json.dumps(model, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
    out = (args.out or run_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # --with-logs changes the classification of BOTH outputs, so both carry the
    # stamp in their name; the safe board.json is never overwritten with tails.
    stem = "board-with-logs" if args.with_logs else "board"
    write_private(out / f"{stem}.json", json.dumps(model, indent=1, ensure_ascii=True, allow_nan=False))
    write_private(out / f"{stem}.html", render_html(model, TEMPLATE))
    target = out / f"{stem}.html"
    c = model["confounded"]
    sys.stderr.write(f"  wrote {target}  ·  {version} {model['phase']}  ·  confounded: {c['count'] if c['computable'] else 'not computable'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
