#!/usr/bin/env python3
"""Palette workbench: make, compare and promote iterations of a colour theme.

An ITERATION is a Python file in iterations/ that takes a frozen base palette and
changes some cells. Nothing an iteration does touches the shipped palette until you
`promote` it, so any number can be explored, diffed and shown side by side.

    workbench.py snapshot edo v1          freeze the shipped palette-edo.css as snapshots/edo-v1.css
    workbench.py list                     snapshots, iterations, and the shipped palettes
    workbench.py show edo2_a              every token, light and dark, with contrast checks
    workbench.py diff edo-v1 edo2_a       changed tokens only, with OKLab distance (perceived size)
    workbench.py lab edo-v1 edo2_a ...    one HTML page: app cell + website fragment + contrast
                                          matrix + token diff + colour-vision simulation
    workbench.py site edo2_a              the website's :root colour block, mapped from the tokens
    workbench.py serve [--project DIR]    THE LIVE LAB: real rendered pages, sliders that nudge whole families
                                          of tokens together, save an iteration as iterations/<name>.json
    workbench.py slots [N]                register experiment slots edo2..edoN once (default 4); then trying a
                                          variant is just `promote <iteration> --as edoN`, or "Send to app" in the lab
    workbench.py register edo2            make a promoted variant selectable in the app and web (10 sites)
    workbench.py unregister edo2          take it out again
    workbench.py finish edo2              the winner becomes `edo`; every variant is removed
    workbench.py check                    the shipped palette-edo.css equals what it was promoted from
    workbench.py promote edo2_a --as edo  write palette-edo.css and the native colorsets

A NAME is a snapshot (snapshots/<name>.css), an iteration (iterations/<name>.py), or a
shipped palette ("edo", "default", ...). Iteration files look like:

    BASE = "edo-v1"
    NOTE = "one line saying what this tries"
    def build(t, mix, contrast):          # t is a copy of the base: change it, return it
        t.set("--bn-colour-bg", dark="#0f1b2b")
        return t
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen  # noqa: E402  (the gallery cell CSS and the native colorset writer live there)
import table as T  # noqa: E402

HERE = Path(__file__).parent
REPO = HERE.parents[1]
COLORS = REPO / "bristlenose/theme/colors"
ASSETS = REPO / "desktop/Bristlenose/Bristlenose/Assets.xcassets"
SNAPS, ITERS = HERE / "snapshots", HERE / "iterations"
PROVENANCE = HERE / "promoted.json"   # which iteration each shipped palette was last promoted from

# Pairs the app actually puts text on; the lab and `show` flag any under the target.
PAIRS = [
    ("Body on page", "--bn-colour-text", "--bn-colour-bg", 4.5),
    ("Body on quote card", "--bn-colour-text", "--bn-colour-quote-bg", 4.5),
    ("Body on paper", "--bn-colour-text", "--bn-colour-paper", 4.5),
    ("Body on sheet", "--bn-colour-text", "--bn-colour-sheet", 4.5),
    ("Muted on page", "--bn-colour-muted", "--bn-colour-bg", 4.5),
    ("Muted on quote card", "--bn-colour-muted", "--bn-colour-quote-bg", 4.5),
    ("Muted on inspector", "--bn-colour-muted", "--bn-colour-inspector-bg", 4.5),
    ("Link on page", "--bn-colour-accent", "--bn-colour-bg", 4.5),
    ("Link on quote card", "--bn-colour-accent", "--bn-colour-quote-bg", 4.5),
    ("Accent on nav capsule", "--bn-colour-accent", "--bn-nav-selection-bg", 4.5),
    ("Badge text on badge", "--bn-colour-badge-text", "--bn-colour-badge-bg", 4.5),
    ("Negative on page", "--bn-colour-negative", "--bn-colour-bg", 4.5),
    ("Positive on active bg", "--bn-colour-positive", "--bn-colour-active-bg", 3.0),
    ("Body on highlight", "--bn-colour-text", "--bn-colour-highlight", 3.0),
    ("Page vs card (surface step)", "--bn-colour-bg", "--bn-colour-quote-bg", 1.0),
    ("Card vs border", "--bn-colour-quote-bg", "--bn-colour-border", 1.0),
]


# ── resolving names ──
def shipped() -> list[str]:
    return sorted(p.stem.removeprefix("palette-") for p in COLORS.glob("palette-*.css"))


def load(name: str) -> T.Table:
    if (SNAPS / f"{name}.css").exists():
        return T.Table.from_css(SNAPS / f"{name}.css", key=name)
    if (ITERS / f"{name}.json").exists():
        spec = json.loads((ITERS / f"{name}.json").read_text())
        t = from_knobs(load(spec["base"]), spec.get("knobs", {}), spec.get("overrides", {}))
        t.key, t.header, t.note = name, "", spec.get("note", "")  # type: ignore[attr-defined]
        return t
    if (ITERS / f"{name}.py").exists():
        spec = importlib.util.spec_from_file_location(f"iteration_{name}", ITERS / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        t = load(mod.BASE).copy()
        t = mod.build(t, T.mix, T.contrast) or t
        t.key, t.header = name, ""
        t.note = getattr(mod, "NOTE", "")  # type: ignore[attr-defined]
        return t
    if name in shipped():
        return T.Table.from_css(COLORS / f"palette-{name}.css", key=name)
    sys.exit(f"unknown palette '{name}'. Try: workbench.py list")


def note_of(t: T.Table) -> str:
    return getattr(t, "note", "")


# ── knob recipes: one implementation (knobs.mjs), run under node so the CLI and the lab agree ──
def to_json(t: T.Table) -> dict:
    return {k: {"light": c.light, "dark": c.dark} for k, c in t.cells.items()}


def from_knobs(base: T.Table, knobs: dict, overrides: dict | None = None) -> T.Table:
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "b.json").write_text(json.dumps(to_json(base)))
        (Path(d) / "k.json").write_text(json.dumps(knobs))
        (Path(d) / "o.json").write_text(json.dumps(overrides or {}))
        r = subprocess.run(["node", str(HERE / "knobs.mjs"), f"{d}/b.json", f"{d}/k.json", f"{d}/o.json"],
                           capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)
    t = base.copy()
    for k, v in out["table"].items():
        t.cells[k].light, t.cells[k].dark = v["light"], v["dark"]
    t.guard_notes = out["notes"]  # type: ignore[attr-defined]
    return t


# ── measurements ──
def oklab(h: str) -> tuple[float, float, float]:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in T.rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def delta_e(a: str, b: str) -> float | None:
    """OKLab distance x100: ~1 is a just-noticeable difference, >5 is plainly different."""
    if not (T.is_hex(a) and T.is_hex(b)):
        return None
    return 100 * sum((x - y) ** 2 for x, y in zip(oklab(a), oklab(b))) ** 0.5


def matrix(t: T.Table) -> list[dict]:
    rows = []
    for label, fg, bg, target in PAIRS:
        row = {"label": label, "target": target}
        for mode in ("light", "dark"):
            f, b = getattr(t.cells[fg], mode), getattr(t.cells[bg], mode)
            row[mode] = T.contrast(f, b) if T.is_hex(f) and T.is_hex(b) else None
        rows.append(row)
    return rows


def failures(t: T.Table) -> list[str]:
    out = []
    for r in matrix(t):
        for mode in ("light", "dark"):
            if r[mode] is not None and r[mode] < r["target"] and r["target"] > 1.0:
                out.append(f"{r['label']} ({mode}) {r[mode]:.2f}:1 < {r['target']}")
    return out


# ── commands ──
def cmd_snapshot(a) -> None:
    src = COLORS / f"palette-{a.palette}.css"
    dst = SNAPS / f"{a.palette}-{a.label}.css"
    SNAPS.mkdir(exist_ok=True)
    if dst.exists():
        sys.exit(f"{dst.name} already exists: snapshots are frozen. Pick a new label.")
    t = T.Table.from_css(src)
    dst.write_text(t.to_css(f"{a.palette}-{a.label}", header=f"/* snapshot of palette-{a.palette}.css, frozen by workbench.py. Do not edit. */"))
    print(f"froze {src.name} as snapshots/{dst.name}")


def cmd_list(_a) -> None:
    print("shipped    ", ", ".join(shipped()))
    print("snapshots  ", ", ".join(p.stem for p in sorted(SNAPS.glob("*.css"))) or "(none)")
    for p in sorted(ITERS.glob("*.py")):
        t = load(p.stem)
        print(f"iteration   {p.stem:<12} on {getattr(sys.modules.get('x'), 'BASE', '') or ''}{note_of(t)}")


def cmd_show(a) -> None:
    t = load(a.name)
    for k, c in t.cells.items():
        print(f"{k:<34}{c.light:<44}{c.dark}")
    print()
    for r in matrix(t):
        f = lambda v: "   n/a" if v is None else f"{v:6.2f}"
        print(f"{r['label']:<30}light {f(r['light'])}   dark {f(r['dark'])}   (target {r['target']})")
    bad = failures(t)
    print("\nFAILS:\n  " + "\n  ".join(bad) if bad else "\nAll text pairs meet their targets.")


def cmd_diff(a) -> None:
    x, y = load(a.a), load(a.b)
    rows = x.diff(y)
    for k, ca, cb in rows:
        for mode in ("light", "dark"):
            va, vb = getattr(ca, mode, None), getattr(cb, mode, None)
            if va != vb:
                d = delta_e(va, vb) if va and vb else None
                print(f"{k:<34}{mode:<6}{va or '-':<26}->  {vb or '-':<26}{'' if d is None else f'dE {d:4.1f}'}")
    print(f"\n{len(rows)} tokens differ out of {len(y.cells)}.")


def cmd_check(_a) -> None:
    prov = json.loads(PROVENANCE.read_text()) if PROVENANCE.exists() else {}
    bad = 0
    for key, it in prov.items():
        want = load(it)
        have = T.Table.from_css(COLORS / f"palette-{key}.css")
        d = have.diff(want)
        if d:
            bad += 1
            print(f"DRIFT palette-{key}.css differs from {it} in {len(d)} tokens (edited by hand, or {it} changed since promotion)")
            for k, ca, cb in d[:5]:
                print("   ", k, ca, cb)
        else:
            print(f"ok   palette-{key}.css == {it}")
    sys.exit(1 if bad else 0)


def cmd_promote(a) -> None:
    t = load(a.name)
    bad = failures(t)
    if bad and not a.force:
        sys.exit("refusing to promote with failing text pairs (use --force to override):\n  " + "\n  ".join(bad))
    key = a.as_
    target = COLORS / f"palette-{key}.css"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        header = existing[: existing.index("*/") + 2]
    else:  # a new palette: the header says where it came from and how to retune it
        header = (f"/* palette-{key} - generated by experiments/brand-palettes/workbench.py from iteration "
                  f"'{a.name}'.\n   {note_of(t) or 'No note.'}\n   Retune in the workbench (workbench.py serve) and promote again; "
                  f"do not hand-edit.\n   Activate: data-color-theme=\"{key}\" on <html>; BRISTLENOSE_PALETTE={key} or --palette {key}. */")
    (COLORS / f"palette-{key}.css").write_text(t.to_css(key, header=header))
    # the four native colorsets read off the same tokens, so both sides of the seam move together
    for concept, token in gen.SIDEBAR.items():
        c = t.cells[token]
        d = ASSETS / f"Palette{gen.asset_stem(key)}{concept}.colorset"
        d.mkdir(exist_ok=True)
        (d / "Contents.json").write_text(gen.colorset(c.light, c.dark))
    prov = json.loads(PROVENANCE.read_text()) if PROVENANCE.exists() else {}
    prov[key] = a.name
    PROVENANCE.write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
    print(f"wrote palette-{key}.css and the native colorsets from {a.name}.")
    import register
    register.regenerate()
    print("Mac app: with the External Server scheme the web content updates on reload; the native sidebar colours")
    print("(accent, ink, paper, selected row) are Xcode assets and need a Cmd+R rebuild.")
    print("Not recoloured: the welcome illustrations' hard-coded Edo hex (docs/private/branding-scorecard.md §3).")


# The website's colour variables, mapped from the app's tokens so the two cannot drift.
SITE_MAP = {
    "--ink": "--bn-colour-text", "--muted": "--bn-colour-muted", "--faint": "--bn-colour-icon-idle",
    "--line": "--bn-colour-border", "--bg": "--bn-colour-bg", "--bg-alt": "--bn-colour-quote-bg",
    "--accent": "--bn-colour-accent", "--badge-bg": "--bn-colour-badge-bg",
    "--badge-text": "--bn-colour-badge-text", "--code-bg": "--bn-colour-badge-bg",
    "--warn": "--bn-colour-negative", "--ok": "--bn-colour-positive", "--tip": "--bn-colour-warning",
    "--soft": "--bn-colour-paper",
}


def site_block(t: T.Table) -> str:
    out = []
    for var, tok in SITE_MAP.items():
        c = t.cells[tok]
        out.append(f"{var}:light-dark({c.light},{c.dark});")
    return ":root{\n  color-scheme:light dark;\n  " + "\n  ".join(out) + "\n}"


def cmd_site(a) -> None:
    print(site_block(load(a.name)))


# ── the lab ──
CVD = {  # Machado et al. 2009, severity 1.0, linear RGB approximated in sRGB filter space
    "none": None,
    "deuteranopia": "0.367 0.861 -0.228 0 0  0.280 0.673 0.047 0 0  -0.012 0.043 0.969 0 0  0 0 0 1 0",
    "protanopia": "0.152 1.053 -0.205 0 0  0.115 0.786 0.099 0 0  -0.004 -0.048 1.052 0 0  0 0 0 1 0",
    "tritanopia": "1.256 -0.077 -0.179 0 0  -0.078 0.931 0.148 0 0  0.005 0.691 0.304 0 0  0 0 0 1 0",
}

SITE_CSS = """
.site{background:var(--bn-colour-bg);color:var(--bn-colour-text);padding:14px 16px;border-radius:10px;border:1px solid var(--bn-colour-border);font:13px/1.5 Inter,system-ui,sans-serif}
.site .nav{display:flex;gap:14px;margin-bottom:10px;color:var(--bn-colour-muted)} .site .nav b{color:var(--bn-colour-text);margin-right:auto}
.site h4{margin:0 0 4px;font-size:18px;letter-spacing:-.01em} .site p{margin:0 0 8px;color:var(--bn-colour-muted)}
.site a{color:var(--bn-colour-accent)} .site .btn{display:inline-block;padding:4px 12px;border-radius:6px;margin-right:6px;font-weight:600;text-decoration:none}
.site .p{background:var(--bn-colour-accent);color:var(--bn-colour-bg)} .site .s{box-shadow:inset 0 0 0 1px var(--bn-colour-border);color:var(--bn-colour-text)}
.site .card{margin-top:10px;padding:8px 10px;background:var(--bn-colour-quote-bg);border-radius:6px;border:1px solid var(--bn-colour-border)}
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cell(key: str, mode: str) -> str:
    return f'''<div class="cell" data-color-theme="{key}" style="color-scheme:{mode}">
  <div class="inspector">Tags<span class="nav">Frustration</span></div>
  <div class="main"><h3>Onboarding friction</h3><p class="muted">Six quotes · three participants · 00:14:32</p>
  <blockquote>“I couldn't find where the export lived, so I just screenshotted it.”
  <div class="badges"><span class="badge">frustration</span><span class="tag">export</span></div></blockquote>
  <p>Read the <a href="#">full transcript</a>, or <mark>search for “export”</mark>.</p>
  <div class="row"><span class="sel">Selected</span><span class="pos">Accepted</span><span class="neg">Delete</span><span class="warn">Partial</span></div></div></div>
  <div class="site" data-color-theme="{key}" style="color-scheme:{mode}"><div class="nav"><b>Bristlenose</b><span>Docs</span><span>Install</span></div>
  <h4>A folder of interviews in. A report you own out.</h4><p>Quotes, themes and friction points in one file you keep.</p>
  <a class="btn p" href="#">Get Bristlenose</a><a class="btn s" href="#">Read the docs</a>
  <div class="card">Kitchen planning, round two <span style="color:var(--bn-colour-muted)">· 9 sessions</span></div></div>'''


def lab_html(names: list[str]) -> str:
    tables = [load(n) for n in names]
    css = "\n".join(T.Table.to_css(t, key=f"lab-{i}", header="") for i, t in enumerate(tables))
    base = tables[0]
    sections = []
    for i, (n, t) in enumerate(zip(names, tables)):
        rows = "".join(
            "<tr><td>{}</td>{}</tr>".format(r["label"], "".join(
                f'<td class="{"bad" if r[m] is not None and r[m] < r["target"] and r["target"] > 1 else ""}">{"-" if r[m] is None else f"{r[m]:.2f}"}</td>'
                for m in ("light", "dark"))) for r in matrix(t))
        diff = ""
        if i:
            drows = []
            for k, ca, cb in base.diff(t):
                for mode in ("light", "dark"):
                    va, vb = getattr(ca, mode, None), getattr(cb, mode, None)
                    if va != vb:
                        d = delta_e(va, vb) if va and vb else None
                        sw = lambda v: f'<i style="background:{v}"></i>' if v and T.is_hex(v) else ""
                        drows.append(f"<tr><td>{k.removeprefix('--bn-')}</td><td>{mode}</td><td>{sw(va)}{esc(va or '-')}</td><td>{sw(vb)}{esc(vb or '-')}</td><td>{'' if d is None else f'{d:.1f}'}</td></tr>")
            diff = f"<details open><summary>{len(drows)} cells differ from {esc(names[0])} (dE = OKLab distance x100: 1 is barely visible, 5+ is plain)</summary><table class='d'>{''.join(drows)}</table></details>"
        sections.append(f'''<section><h2>{esc(n)}</h2><p class="note">{esc(note_of(t))}</p>
<div class="pair">{cell(f"lab-{i}", "light")}{cell(f"lab-{i}", "dark")}</div>
<table class="m"><tr><th>Text pair</th><th>light</th><th>dark</th></tr>{rows}</table>{diff}</section>''')
    filters = "".join(f'<filter id="cvd-{k}"><feColorMatrix type="matrix" values="{v}"/></filter>' for k, v in CVD.items() if v)
    opts = "".join(f'<option value="{k}">{k}</option>' for k in CVD)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Palette lab</title><style>
/* Generated by experiments/brand-palettes/workbench.py lab {" ".join(names)}. Rerun it; do not hand-edit. */
{css}
{gen.GALLERY_CSS}{SITE_CSS}
body{{background:#e9e9ec;color:#1a1a1a}} .bar{{position:sticky;top:0;background:#e9e9ec;padding:6px 0;z-index:2}}
.pair{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}
.pair>*{{margin:0}} .note{{color:#555;max-width:70em}}
table{{border-collapse:collapse;font:12px ui-monospace,Menlo,monospace;margin:8px 0}} td,th{{padding:2px 10px;text-align:left}}
td.bad{{background:#f4d9d1;color:#a33217;font-weight:700}} table.d i{{display:inline-block;width:11px;height:11px;border:1px solid #0003;margin-right:5px;vertical-align:-1px}}
</style></head><body><svg width="0" height="0" style="position:absolute">{filters}</svg>
<div class="bar"><b>Palette lab</b> &nbsp; Colour vision: <select id="cvd">{opts}</select>
&nbsp; Constant neutral surround, on purpose: judge every specimen against the same ground.</div>
<div id="g">{"".join(sections)}</div>
<script>document.getElementById("cvd").onchange=e=>{{document.getElementById("g").style.filter=e.target.value==="none"?"":"url(#cvd-"+e.target.value+")"}}</script>
</body></html>'''


def cmd_lab(a) -> None:
    out = Path(a.output) if a.output else REPO / "docs/mockups/palette-lab.html"
    out.write_text(lab_html(a.names))
    print("wrote", out)


def find_project(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    for p in sorted((REPO / "trial-runs").glob("*/bristlenose-output")):
        if list(p.glob("*-report.html")):
            return p
    sys.exit("no rendered project found: pass --project <a bristlenose-output folder>")


def cmd_serve(a) -> None:
    """The live lab: real rendered pages, recoloured as you move the sliders. Local only."""
    import http.server
    import mimetypes
    import urllib.parse
    proj = find_project(a.project)
    import everything
    pages = [{"label": "Everything (all components + states)", "url": "/everything"},
             {"label": "Report", "url": "/pages/" + next(proj.glob("*-report.html")).name}]
    for extra in ("analysis.html", "codebook.html"):
        if (proj / extra).exists():
            pages.append({"label": extra.removesuffix(".html").capitalize(), "url": "/pages/" + extra})
    for sess in sorted((proj / "sessions").glob("*.html"))[:3]:
        pages.append({"label": "Transcript " + sess.stem.split("_")[-1], "url": "/pages/sessions/" + sess.name})
    ITERS.mkdir(exist_ok=True)

    class H(http.server.BaseHTTPRequestHandler):
        def send(self, body: bytes, ctype: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def file(self, path: Path) -> None:
            if path.is_file():
                self.send(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            else:
                self.send(b"not found", "text/plain", 404)

        def do_GET(self) -> None:  # noqa: N802
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            if u.path == "/":
                return self.file(HERE / "lab/index.html")
            if u.path == "/knobs.mjs":
                return self.send((HERE / "knobs.mjs").read_bytes(), "text/javascript")
            if u.path == "/api/base":
                return self.send(json.dumps(to_json(load(q["name"][0]))).encode(), "application/json")
            if u.path == "/api/slots":
                import register
                return self.send(json.dumps(register.variants()).encode(), "application/json")
            if u.path == "/api/pages":
                return self.send(json.dumps(pages).encode(), "application/json")
            if u.path == "/api/iterations":
                rows = [{"name": p.stem, "note": json.loads(p.read_text()).get("note", "")} for p in sorted(ITERS.glob("*.json"))]
                return self.send(json.dumps(rows).encode(), "application/json")
            if u.path == "/api/iteration":
                return self.file(ITERS / (Path(q["name"][0]).name + ".json"))
            if u.path == "/everything":
                return self.send(everything.build().encode(), "text/html; charset=utf-8")
            if u.path.startswith("/theme/"):
                theme = (REPO / "bristlenose/theme").resolve()
                target = (theme / urllib.parse.unquote(u.path[len("/theme/"):])).resolve()
                if theme in target.parents:
                    return self.file(target)
            if u.path.startswith("/pages/"):
                target = (proj / urllib.parse.unquote(u.path[len("/pages/"):])).resolve()
                if proj in target.parents or target == proj:
                    return self.file(target)
            self.send(b"not found", "text/plain", 404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/api/promote":
                import io
                from contextlib import redirect_stdout
                d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                name, slot = Path(d["name"]).name, d["slot"]
                if not name.replace("-", "").replace("_", "").isalnum() or slot not in {f"edo{i}" for i in range(2, 10)}:
                    return self.send(b"bad name or slot", "text/plain", 400)
                (ITERS / f"{name}.json").write_text(json.dumps(
                    {"base": d["base"], "note": d.get("note", ""), "knobs": d["knobs"], "overrides": d.get("overrides", {})}, indent=2) + "\n")
                if not (COLORS / f"palette-{slot}.css").exists():
                    return self.send(f"{slot} is not registered: run `workbench.py slots`".encode(), "text/plain", 409)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    cmd_promote(argparse.Namespace(name=name, as_=slot, force=True))
                bad = failures(load(name))
                return self.send(json.dumps({"slot": slot, "text": buf.getvalue(), "failing": bad}).encode(), "application/json")
            if self.path != "/api/save":
                return self.send(b"not found", "text/plain", 404)
            d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name = Path(d["name"]).name
            if not name.replace("-", "").replace("_", "").isalnum():
                return self.send(b"bad name", "text/plain", 400)
            (ITERS / f"{name}.json").write_text(json.dumps(
                {"base": d["base"], "note": d.get("note", ""), "knobs": d["knobs"], "overrides": d.get("overrides", {})}, indent=2) + "\n")
            self.send(b"ok", "text/plain")

        def log_message(self, *_a) -> None:
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"palette lab on http://127.0.0.1:{a.port}/   (pages from {proj})\nCtrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def cmd_slots(a) -> None:
    """Register edo2..edoN once. Each is a placeholder copy of edo-v1 until an iteration is promoted into it."""
    import register
    for n in range(2, a.n + 1):
        key = f"edo{n}"
        if not (COLORS / f"palette-{key}.css").exists():
            base = load("edo-v1")
            (COLORS / f"palette-{key}.css").write_text(base.to_css(key, header=(
                f"/* palette-{key} - an experiment slot, a copy of edo-v1 until an iteration is promoted into it\n"
                f"   (workbench.py promote <iteration> --as {key}). Removed by `workbench.py finish`. */")))
            for concept, token in gen.SIDEBAR.items():
                c = base.cells[token]
                d = ASSETS / f"Palette{gen.asset_stem(key)}{concept}.colorset"
                d.mkdir(exist_ok=True)
                (d / "Contents.json").write_text(gen.colorset(c.light, c.dark))
        for f in register.register(key):
            print("  edited", f)
    register.regenerate()
    print(f"slots edo2..edo{a.n} are registered; promote into them with `promote <iteration> --as edoN`.")


def cmd_register(a) -> None:
    import register
    for f in register.register(a.key):
        print("  edited", f)
    register.regenerate()
    print(f"{a.key} is now selectable in the app and the web report (rebuild the Mac app to see it there).")


def cmd_unregister(a) -> None:
    import register
    for f in register.unregister(a.key):
        print("  ", f)
    register.regenerate()


def cmd_finish(a) -> None:
    """End the experiment: the winner becomes `edo`; every variant is unregistered and deleted."""
    import register
    winner = a.key
    ns = argparse.Namespace(name=winner, as_="edo", force=a.force)
    cmd_promote(ns)
    for v in register.variants():
        for f in register.unregister(v):
            print("  ", f)
    register.regenerate()
    print(f"edo is now {winner}; all variants removed. Re-run the tests, then commit.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot"); p.add_argument("palette"); p.add_argument("label"); p.set_defaults(f=cmd_snapshot)
    p = sub.add_parser("list"); p.set_defaults(f=cmd_list)
    p = sub.add_parser("show"); p.add_argument("name"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("diff"); p.add_argument("a"); p.add_argument("b"); p.set_defaults(f=cmd_diff)
    p = sub.add_parser("lab"); p.add_argument("names", nargs="+"); p.add_argument("-o", "--output"); p.set_defaults(f=cmd_lab)
    p = sub.add_parser("site"); p.add_argument("name"); p.set_defaults(f=cmd_site)
    p = sub.add_parser("serve"); p.add_argument("--project"); p.add_argument("--port", type=int, default=8530); p.set_defaults(f=cmd_serve)
    p = sub.add_parser("slots"); p.add_argument("n", type=int, nargs="?", default=4); p.set_defaults(f=cmd_slots)
    p = sub.add_parser("register"); p.add_argument("key"); p.set_defaults(f=cmd_register)
    p = sub.add_parser("unregister"); p.add_argument("key"); p.set_defaults(f=cmd_unregister)
    p = sub.add_parser("finish"); p.add_argument("key"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_finish)
    p = sub.add_parser("check"); p.set_defaults(f=cmd_check)
    p = sub.add_parser("promote"); p.add_argument("name"); p.add_argument("--as", dest="as_", required=True)
    p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_promote)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
