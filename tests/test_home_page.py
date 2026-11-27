"""The home page: what a hostile string can do, what the CSP names, and what the page shows when run.

Design: docs/private/design-home-dashboard.md section 5. The page opens from file:// and its data is
third-party-influenced (a release verdict, CI output, a rating a stranger typed).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import home_lib as hl  # noqa: E402

NOW = 1795737600
HOSTILE = "</script><script>alert(2)</script><!--     & < >"


def hostile_panels():
    p = []
    p.append(hl.panel("fresh", "Fresh one", link=Path("/tmp/x.html").as_uri(), as_of=NOW - 240, as_of_label="pulled",
                      max_age=3600, body=[{"kind": "kpis", "items": [{"n": 1, "l": HOSTILE}]}]))
    p.append(hl.panel("old", "Old one", as_of=NOW - 7200, as_of_label="pulled", max_age=3600))
    p.append(hl.panel("srcold", "Source old", as_of=NOW - 864000, as_of_label="changed", max_age=259200, refreshable=False))
    p.append(hl.unknown("unk", "Unknown one", "unreachable", as_of=NOW - 5))
    p.append(hl.nodata("nod", "Nothing"))
    p.append(hl.panel("lnk", "Link only", stateless=True))
    bad = hl.panel("evil", "<img src=x onerror=alert(1)> javascript", as_of=NOW - 10, as_of_label="pulled", max_age=3600,
                   facts=[HOSTILE])
    bad["link"] = "javascript:alert(1)"       # bypass panel(): the page must refuse it by itself
    p.append(bad)
    p.append(hl.panel("exp", "Things that expire", stateless=True, body=[{"kind": "expiries", "rows": [
        {"what": "soon", "epoch": NOW + 30 * 86400 + 3600}, {"what": "later", "epoch": NOW + 100 * 86400 + 3600},
        {"what": "past", "epoch": NOW - 86400}, {"what": "unknown", "epoch": None},
        {"what": "summer", "epoch": 1776643199}]}]))      # 2026-04-19 23:59:59 UTC: must read 19 Apr, not 20 Apr (London is UTC+1 then)
    return p


def page(built_at=NOW - 60):
    return hl.build_page(hostile_panels(), built_at)


def data_block(html):
    m = re.search(r'<script type="application/json" id="home-data">(.*?)</script\s*>', html, re.S | re.I)
    assert m, "no data block"
    return m.group(1)


def test_hostile_strings_round_trip_and_cannot_close_the_data_block():
    html = page()
    data = json.loads(data_block(html))
    assert data["panels"][0]["body"][0]["items"][0]["l"] == HOSTILE
    assert data["panels"][6]["facts"] == [HOSTILE]
    assert html.count("</script>") == 3, "data block + freshness + page: nothing typed may add one"
    assert "<!--" not in data_block(html) and " " not in data_block(html)


def test_the_csp_names_exactly_the_two_scripts_and_blocks_the_network():
    html = page()
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', html).group(1)
    assert "connect-src 'none'" in csp and "default-src 'none'" in csp and "'unsafe-inline'" in csp.split("style-src")[1].split(";")[0]
    assert "script-src 'sha256-" in csp and "unsafe-eval" not in csp and csp.count("sha256-") == 2
    scripts = re.findall(r"<script>(.*?)</script\s*>", html, re.S | re.I)
    assert len(scripts) == 2
    for s in scripts:
        assert hl._hash(s) in csp, "a script the CSP does not name would not run"


def test_the_csp_is_the_first_thing_in_the_head():
    html = page()
    head = html.split("<head>", 1)[1]
    assert head.lstrip().startswith('<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy"'), head[:120]


def test_no_dom_sinks_in_the_template_the_scripts_or_the_built_page():
    pats = (r"\.innerHTML\s*=", r"\.outerHTML\s*=", r"\.insertAdjacentHTML\s*\(", r"\bdocument\.write\s*\(", r"\beval\s*\(", r"new Function\s*\(")
    for name in ("home-page.template.html", "home-page.js", "home-freshness.js"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        for pat in pats:
            assert not re.search(pat, src), f"{name}: {pat}"
    for pat in pats:
        assert not re.search(pat, page()), pat


@pytest.mark.parametrize("url,ok", [
    ("file:///Users/x/dashboard.html", True), ("http://localhost:8210/_local/visitors.html", True),
    ("http://127.0.0.1:8210/", True), ("https://bristlenose.app/", False), ("javascript:alert(1)", False),
    ("http://localhost.evil.com/", False), ("http://user@localhost/", False), ("file://host/etc/passwd", False),
    ("data:text/html,<script>", False), ("", False), (None, False)])
def test_only_file_and_localhost_urls_become_links(url, ok):
    assert (hl.safe_link(url) is not None) == ok


def test_panel_itself_drops_an_unsafe_link_before_the_page_ever_sees_it():
    assert hl.panel("x", "X", link="https://evil.example/")["link"] is None
    assert hl.panel("x", "X", link="javascript:alert(1)")["link"] is None
    assert hl.panel("x", "X", link="file:///Users/x/a.html")["link"] == "file:///Users/x/a.html"


def test_every_slot_is_filled_once_and_a_slot_name_typed_into_data_is_left_alone():
    p = hl.panel("a", "A", as_of=NOW, as_of_label="x", max_age=9, facts=["__HOME_PAGE_JS__ __CSP__"])
    html = hl.build_page([p], NOW)
    assert json.loads(data_block(html))["panels"][0]["facts"] == ["__HOME_PAGE_JS__ __CSP__"]


def test_an_error_is_only_ever_one_of_the_fixed_strings():
    for key in hl.ERR:
        assert hl.unknown("x", "X", key)["error"] == hl.ERR[key]
    with pytest.raises(KeyError):
        hl.unknown("x", "X", "ssh: connect to host stranger@evil.example port 22: Connection refused")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_page_run_in_jsdom_shows_what_a_person_would_see(tmp_path):
    f = tmp_path / "home.html"
    f.write_text(page(), encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "tests" / "home_page_dom.js"), str(f)], capture_output=True, text=True,
                       timeout=120, env=dict(os.environ, HOME_NOW_S=str(NOW)))
    if r.returncode == 3:
        pytest.skip("jsdom is absent: " + r.stderr.strip())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 failed" in r.stdout, r.stdout
