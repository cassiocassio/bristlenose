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
from datetime import timedelta
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
