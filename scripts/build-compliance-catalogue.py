#!/usr/bin/env python3
"""Rebuild docs/design-system/compliance-catalogue.html from the current app.

Three inputs, all re-readable, so the page can be regenerated at any time:

  1. bristlenose/theme/   — the shipped CSS (same file order as the report), embedded
     verbatim as the specimens' stylesheet, and classified declaration by
     declaration with the same classifier as scripts/audit-css.py.
  2. docs/design-system/compliance-specimens.json — the hand-built specimen markup
     (and any hand-written defect/fix prose) per CSS file. Bootstrapped once from the
     previous catalogue; edit it to add or fix a specimen.
  3. a live-scan file from experiments/token-xray/live-scan.mjs --all, summarised
     into docs/design-system/compliance-live.json (committed, so a rebuild needs no
     running server).

    .venv/bin/python scripts/build-compliance-catalogue.py                 # rebuild
    .venv/bin/python scripts/build-compliance-catalogue.py --live scan.json # refresh the on-screen summary too
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "bristlenose" / "theme"
CATALOGUE = ROOT / "docs" / "design-system" / "compliance-catalogue.html"
SPECIMENS = ROOT / "docs" / "design-system" / "compliance-specimens.json"
LIVE_SUMMARY = ROOT / "docs" / "design-system" / "compliance-live.json"

_spec = importlib.util.spec_from_file_location("audit_css", ROOT / "scripts" / "audit-css.py")
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_css"] = audit  # a path-loaded module goes into sys.modules first
_spec.loader.exec_module(audit)

MAX_FINDINGS = 40
LENS_ORDER = ["quotes", "sessions", "themes", "analysis", "codebook", "shell"]
LENS_TEXT = {
    "quotes": ("Quotes", "The Quotes lens, x-rayed.",
               "Every component that builds a quote card, in all four theme combinations."),
    "sessions": ("Sessions", "The Sessions lens, x-rayed.",
                 "Session table, thumbnails, sparklines, journey labels and transcript coverage."),
    "themes": ("Themes", "The Themes lens, x-rayed.",
               "Section grouping, table of contents, the responsive grid and the uncategorised floor."),
    "analysis": ("Analysis", "The Analysis lens, x-rayed.",
                 "Signal-concentration heatmap, sentiment bar charts and metric chrome."),
    "codebook": ("Codebook", "The Codebook lens, x-rayed.",
                 "Codebook panel, tag filter, autocode surfaces and the threshold reviewer."),
    "shell": ("Shell", "The app shell, x-rayed.",
              "Toolbar, sidebar, dialogs, settings, the Sessions grid and every other file the five content lenses do not cover."),
}
TIER_OF = {"atoms": "atom", "molecules": "molecule", "organisms": "organism", "templates": "template"}


# ── 1. specimens: bootstrap once from the previous catalogue ─────────────────
def bootstrap_specimens() -> None:
    html = CATALOGUE.read_text(encoding="utf-8")
    m = re.search(r"const T=\(s\)=>s;.*?\nconst _CODEBOOK = .*?;\n", html, re.S)
    if not m:
        sys.exit("cannot bootstrap: old data block not found and compliance-specimens.json is missing")
    js = m.group(0) + "\nconsole.log(JSON.stringify([COMPONENTS,_SESSIONS,_THEMES,_ANALYSIS,_CODEBOOK]));"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    entries: dict[str, dict] = {}
    for group in json.loads(out):
        for c in group:
            e = entries.setdefault(c["file"], {"names": [], "specimens": [], "xr": [], "prose": []})
            e["names"].append(c["name"])
            e["specimens"].append(c["specimen"])
            e["xr"].extend(c.get("xr", []))
            for f in c.get("findings", []):
                bad = "".join(p[1] if isinstance(p, list) and len(p) > 1 and p[0] == "bad" else ""
                              for p in f["code"])
                e["prose"].append({"value": bad, "defect": f["defect"], "fix": f["fix"]})
    SPECIMENS.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"bootstrapped {SPECIMENS.name}: {len(entries)} files with specimens")


# ── 2. token vocabulary, for fix suggestions ─────────────────────────────────
def parse_tokens() -> dict[str, list[tuple[str, str]]]:
    text = ""
    for f in ("tokens.css", "tokens-typography.css", "tokens-desktop.css"):
        p = THEME / f
        if p.exists():
            text += audit.strip_comments(p.read_text(encoding="utf-8"))
    fam: dict[str, list[tuple[str, str]]] = {k: [] for k in ("space", "radius", "text", "weight", "dur")}
    for name, value in re.findall(r"(--bn-[\w-]+)\s*:\s*([^;{}]+);", text):
        v = value.strip().lower()
        if name.startswith("--bn-space-"):
            fam["space"].append((name, v))
        elif name.startswith("--bn-radius-"):
            fam["radius"].append((name, v))
        elif name.startswith("--bn-transition-") or name == "--bn-overlay-duration":
            fam["dur"].append((name, v))
        elif re.match(r"--bn-text-[a-z]+$", name):
            fam["text"].append((name, v))
        elif name.startswith("--bn-weight-"):
            fam["weight"].append((name, v))
    return fam


def to_px(v: str) -> float | None:
    m = re.fullmatch(r"(-?\d*\.?\d+)(rem|em|px)", v.strip())
    if not m:
        return None
    return float(m.group(1)) * (16 if m.group(2) != "px" else 1)


def family_of(prop: str) -> str | None:
    if prop in audit.SPACING_PROPS:
        return "space"
    if prop in audit.RADIUS_PROPS:
        return "radius"
    if prop == "font-size":
        return "text"
    if prop == "font-weight":
        return "weight"
    if prop in audit.TRANSITION_PROPS:
        return "dur"
    return None


def suggest(prop: str, value: str, fam: dict, state: str) -> str:
    f = family_of(prop)
    if f is None:
        return ""
    parts = [p for p in value.split() if p != "0"]
    out = []
    for part in parts:
        exact = [n for n, v in fam[f] if v == part]
        if exact:
            out.append(f"<code>{part}</code> → <code>var({exact[0]})</code>")
            continue
        px = to_px(part)
        cands = [(abs((to_px(v) or 1e9) - px), n, v) for n, v in fam[f]] if px is not None else []
        if cands:
            _, n, v = min(cands)
            out.append(f"<code>{part}</code> ≈ <code>var({n})</code> ({v})")
    return "; ".join(out)


# ── 3. per-declaration scan with line + selector ─────────────────────────────
TOKEN_RE = re.compile(r"(?P<open>[^{};]*\{)|(?P<close>\})|(?P<decl>[\w-]+\s*:\s*[^;{}]+;)")


def scan_file(path: Path, tv: dict) -> tuple[dict, list[dict]]:
    raw = path.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw, flags=re.S)
    stack: list[str] = []
    counts = {"good": 0, "warn": 0, "bad": 0, "high": 0, "low": 0}
    found: list[dict] = []
    for m in TOKEN_RE.finditer(css):
        if m.group("open"):
            stack.append(" ".join(m.group("open")[:-1].split()))
        elif m.group("close"):
            if stack:
                stack.pop()
        else:
            prop, _, value = m.group("decl")[:-1].partition(":")
            value = " ".join(value.split())
            res = audit.classify(prop, value, tv)
            if res is None:
                continue
            state, sev, cat = res
            if state == "good":
                counts["good"] += 1
                continue
            counts["warn" if state == "fixable" else "bad"] += 1
            if state == "bad":
                counts["high" if sev == "high" else "low"] += 1
            sel = next((s for s in reversed(stack) if not s.startswith("@")), "")
            found.append({"state": state, "cat": cat, "prop": prop.strip(), "value": value,
                          "sel": sel, "line": css.count("\n", 0, m.start()) + 1})
    return counts, found


def build_findings(found: list[dict], prose: list[dict], fam: dict) -> tuple[list[dict], int]:
    groups: dict[tuple, list[dict]] = {}
    for f in found:
        groups.setdefault((f["state"], f["cat"], f["prop"], f["value"]), []).append(f)
    ordered = sorted(groups.items(),
                     key=lambda kv: (kv[0][0] != "bad", kv[0][1] != "hardcoded-colour", -len(kv[1])))
    by_value = {p["value"].strip().lower(): p for p in prose}
    out = []
    for (state, cat, prop, value), items in ordered[:MAX_FINDINGS]:
        first = items[0]
        lines = [str(i["line"]) for i in items]
        loc = ":" + ", :".join(lines[:4]) + (f" (+{len(lines) - 4} more)" if len(lines) > 4 else "")
        hand = by_value.get(value.strip().lower())
        sug = suggest(prop, value, fam, state)
        if hand:
            defect, fix = hand["defect"], hand["fix"]
        elif cat == "hardcoded-colour":
            defect = "A literal colour: it cannot follow dark mode or the Edo palette."
            fix = "Use an existing <code>--bn-colour-*</code> token; if none fits, that is a missing token."
        elif cat == "shadow":
            defect = "Shadow geometry (or colour) is a literal repeated across the theme."
            fix = "Introduce a shadow-geometry token and reference it."
        elif cat == "z-index":
            defect = "A magic z-index with no scale behind it, so values collide across files."
            fix = "Add a z-index scale to tokens.css and use its stops."
        elif state == "warn":
            defect = "A literal that already equals an existing token."
            fix = f"Swap for the token: {sug}." if sug else "Swap for the matching token."
        else:
            defect = "Off the scale: no token equals this value."
            fix = (f"Snap to the nearest stop, or add one if the value is deliberate: {sug}."
                   if sug else "Snap to the nearest stop, or add one if the value is deliberate.")
        out.append({
            "sev": "bad" if state == "bad" else "warn", "cat": cat, "loc": loc,
            "code": [["sel", first["sel"]], [" { "], ["prop", prop], [": "], ["bad", value], [" }"]],
            "defect": defect, "fix": fix,
        })
    return out, max(0, len(ordered) - MAX_FINDINGS)


# ── 4. assemble the component list ───────────────────────────────────────────
def build_components(theme_css: str) -> tuple[dict[str, list[dict]], dict]:
    tv = audit.parse_token_values()
    fam = parse_tokens()
    spec = json.loads(SPECIMENS.read_text(encoding="utf-8"))
    css_classes = set(re.findall(r"\.([\w-]+)", theme_css))
    lenses: dict[str, list[dict]] = {k: [] for k in LENS_ORDER}
    stale_report, stats = [], {"files": 0, "specimens": 0, "mismatch": []}
    for p in sorted(p for d in audit.SCAN_DIRS for p in (THEME / d).glob("*.css")):
        rel = f"{p.parent.name}/{p.name}"
        counts, found = scan_file(p, tv)
        n = counts["good"] + counts["warn"] + counts["bad"]
        if n == 0:
            continue
        ref = audit.audit_file(p, tv)  # the audit script is the arbiter: any disagreement is a bug here
        if (ref["good"], ref["warn"], ref["bad"]) != (counts["good"], counts["warn"], counts["bad"]):
            stats["mismatch"].append(rel)
        s = spec.get(rel)
        findings, extra = build_findings(found, s["prose"] if s else [], fam)
        stem = p.stem
        comp = {
            "id": f"{p.parent.name[:-1]}-{stem}", "name": (s["names"][0] if s and len(s["names"]) == 1 else stem),
            "tier": TIER_OF[p.parent.name], "file": rel, "counts": {k: counts[k] for k in ("good", "warn", "bad")},
            "sev": {"high": counts["high"], "low": counts["low"]}, "findings": findings,
        }
        cov, health, _ = audit.metric(counts["good"], counts["warn"], counts["bad"], counts["high"], counts["low"])
        bits = [f"<b>{n}</b> themeable declarations — {counts['good']} inside, {counts['warn']} fixable, "
                f"{counts['bad']} outside ({counts['high']} colour, {counts['low']} scale/shadow/z-index)."]
        if extra:
            bits.append(f"{extra} further distinct values are not listed here; run "
                        f"<code>scripts/audit-css.py</code> for the full count.")
        if s:
            comp["specimen"] = "".join(s["specimens"])
            comp["xr"] = s["xr"]
            classes = {c for m in re.findall(r'class="([^"]+)"', comp["specimen"]) for c in m.split()}
            stale = sorted(c for c in classes - css_classes if not c.startswith("cx-"))
            if stale:
                bits.append("<b>Specimen may be stale:</b> markup uses classes no longer in the theme CSS — "
                            + ", ".join(f"<code>{c}</code>" for c in stale[:6]) + ".")
                stale_report.append((rel, stale))
            stats["specimens"] += 1
        else:
            comp["specimen"] = None
            comp["xr"] = []
        comp["does"] = " ".join(bits)
        lenses[audit.LENS_OF.get(rel, "shell")].append(comp)
        stats["files"] += 1
    stats["stale"] = stale_report
    return lenses, stats


# ── 5. live-scan summary ─────────────────────────────────────────────────────
def load_live(path: Path | None) -> dict | None:
    if path:
        raw = json.loads(path.read_text(encoding="utf-8"))
        pages = [{"tab": pg["tab"], "scheme": pg["scheme"], "total": pg["total"],
                  "top": pg["topValues"][:6]} for pg in raw["pages"]]
        summary = {"scannedAt": raw["scannedAt"][:10], "pages": pages}
        LIVE_SUMMARY.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
        return summary
    if LIVE_SUMMARY.exists():
        return json.loads(LIVE_SUMMARY.read_text(encoding="utf-8"))
    return None


# ── 6. systemic note ─────────────────────────────────────────────────────────
def systemic_note(lenses: dict, theme_files: list[Path], tv: dict) -> str:
    tally: dict[tuple, set] = {}
    occ: dict[tuple, int] = {}
    for p in theme_files:
        _, found = scan_file(p, tv)
        for f in found:
            if f["state"] != "bad":
                continue
            k = (f["prop"], f["value"])
            tally.setdefault(k, set()).add(p.name)
            occ[k] = occ.get(k, 0) + 1
    top = sorted(occ, key=lambda k: -occ[k])[:5]
    rows = "; ".join(f"<code>{k[0]}: {k[1]}</code> ×{occ[k]} in {len(tally[k])} files" for k in top)
    worst = sorted((c for comps in lenses.values() for c in comps),
                   key=lambda c: audit.metric(c["counts"]["good"], c["counts"]["warn"], c["counts"]["bad"],
                                              c["sev"]["high"], c["sev"]["low"])[0])[:3]
    names = ", ".join(f"<code>{c['file']}</code>" for c in worst)
    return (f"<b>A few repeated values drive most of the magenta</b>, not per-component sloppiness. "
            f"The most repeated outside-system values are {rows}. Where the same literal recurs, "
            f"the fix is one token, not many edits. Weakest files by coverage: {names}.")


# ── 7. write the page ────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=Path, help="full live-scan.mjs --all output to summarise")
    args = ap.parse_args()

    if not SPECIMENS.exists():
        bootstrap_specimens()

    sys.path.insert(0, str(ROOT))
    from bristlenose.stages.s12_render.theme_assets import (
        _THEME_FILES,  # same order the report ships
    )

    snap = "".join(f"/* --- {f} --- */\n{(THEME / f).read_text(encoding='utf-8')}\n" for f in _THEME_FILES)
    lenses, stats = build_components(snap)
    live = load_live(args.live)

    today = datetime.date.today()
    stamp = f"{today.day} {today.strftime('%b %Y')}"
    all_comps = [c for k in LENS_ORDER for c in lenses[k]]
    tot = {k: sum(c["counts"][k] for c in all_comps) for k in ("good", "warn", "bad")}
    hi = sum(c["sev"]["high"] for c in all_comps)
    lo = sum(c["sev"]["low"] for c in all_comps)
    cov, health, _ = audit.metric(tot["good"], tot["warn"], tot["bad"], hi, lo)

    html = CATALOGUE.read_text(encoding="utf-8")

    # theme snapshot
    block = (f'<style id="bn-theme">\n/* ===== EMBEDDED SNAPSHOT of bristlenose/theme/ — generated {stamp} by '
             f'scripts/build-compliance-catalogue.py, in the order the report ships it. ===== */\n{snap}</style>')
    html = re.sub(r'^<style id="bn-theme">.*?^</style>', lambda _: block, html, count=1, flags=re.S | re.M)

    # data block (markers inserted on first run)
    lens_js = ",\n  ".join(
        f'{k}: {{name:{json.dumps(LENS_TEXT[k][0])}, title:{json.dumps(LENS_TEXT[k][1])}, '
        f'lede:{json.dumps(LENS_TEXT[k][2])}, components: DATA.{k}}}' for k in LENS_ORDER)
    data = json.dumps({k: lenses[k] for k in LENS_ORDER}, ensure_ascii=False).replace("</", "<\\/")
    live_js = json.dumps(live, ensure_ascii=False) if live else "null"
    new_data = (f"/*@@DATA-BEGIN@@*/\n/* generated {stamp} — do not hand-edit; see scripts/build-compliance-catalogue.py */\n"
                f"const DATA = {data};\nconst LIVE = {live_js};\nconst LENSES = {{\n  {lens_js}\n}};\n"
                f"const LENS_ORDER = {json.dumps(LENS_ORDER)};\n/*@@DATA-END@@*/")
    if "/*@@DATA-BEGIN@@*/" in html:
        html = re.sub(r"/\*@@DATA-BEGIN@@\*/.*?/\*@@DATA-END@@\*/", lambda _: new_data, html, count=1, flags=re.S)
    else:
        html, n = re.subn(r"/\* =+ compliance dataset.*?const LENS_ORDER = \[[^\]]*\];", lambda _: new_data,
                          html, count=1, flags=re.S)
        if not n:
            sys.exit("data block not found")

    # one-time template patches (idempotent)
    def patch(old: str, new: str) -> None:
        nonlocal html
        if new in html:
            return
        if old not in html:
            sys.exit(f"template anchor missing: {old[:60]!r}")
        html = html.replace(old, new, 1)

    patch('const TIER_ORDER=["atom","molecule","organism"];', 'const TIER_ORDER=["atom","molecule","organism","template"];')
    patch('  organism:{name:"Organisms",sub:"Self-contained sections — panels, tables, charts, the quote card."}\n};',
          '  organism:{name:"Organisms",sub:"Self-contained sections — panels, tables, charts, the quote card."},\n'
          '  template:{name:"Templates",sub:"Page-level layout and print overrides."}\n};')
    patch('<small>/8</small>', '<small id="stOf">/8</small>')
    patch('setTxt("stComp",String(comps.length));',
          'setTxt("stComp",String(comps.length)); setTxt("stOf","/"+comps.length);')
    patch('<div class="cx-specimens">${quads}</div>',
          '${c.specimen?`<div class="cx-specimens">${quads}</div>`:`<div class="cx-nospec">no specimen — scored from source</div>`}')
    patch('<b>What it gets right — </b>', '<b>Reading — </b>')
    patch('renderLens("quotes");\n', 'renderLens("quotes");\nrenderLive();\n')
    patch('</style>\n', '/* live panel */\n.cx-nospec{padding:10px 18px;font-family:var(--cx-mono);font-size:11.5px;color:var(--cx-faint);'
          'border-top:1px solid var(--cx-hair);}\n.cx-live table{border-collapse:collapse;font-size:12.5px;width:100%;}\n'
          '.cx-live th,.cx-live td{text-align:left;padding:4px 10px 4px 0;border-bottom:1px solid var(--cx-hair);'
          'font-variant-numeric:tabular-nums;}\n.cx-live th{font-family:var(--cx-mono);font-size:10.5px;color:var(--cx-faint);'
          'text-transform:uppercase;letter-spacing:.05em;}\n.cx-live code{font-family:var(--cx-mono);font-size:11.5px;}\n</style>\n')
    if "function renderLive()" not in html:
        html = html.replace("</script>\n", LIVE_JS + "</script>\n", 1) if False else html.replace(
            "/* ---- X-ray toggle ---- */", LIVE_JS + "\n/* ---- X-ray toggle ---- */", 1)

    # lens buttons
    btns = "\n".join(
        f'      <button class="cx-lensbtn" data-lens="{k}" aria-pressed="{"true" if k == "quotes" else "false"}">{LENS_TEXT[k][0]}</button>'
        for k in LENS_ORDER)
    html = re.sub(r'(<div class="cx-lenses"[^>]*>\n).*?(\n    </div>)', lambda m: m.group(1) + btns + m.group(2),
                  html, count=1, flags=re.S)

    # prose that carries numbers or dates
    note = systemic_note(lenses, sorted(p for d in audit.SCAN_DIRS for p in (THEME / d).glob("*.css")),
                         audit.parse_token_values())
    note_html = f"<!--@@NOTE-BEGIN@@-->\n    <div class=\"cx-note\">\n      {note}\n    </div>\n    <!--@@NOTE-END@@-->"
    if "<!--@@NOTE-BEGIN@@-->" in html:
        html = re.sub(r"<!--@@NOTE-BEGIN@@-->.*?<!--@@NOTE-END@@-->", lambda _: note_html, html, count=1, flags=re.S)
    else:
        html, n = re.subn(r'<div class="cx-note">.*?</div>(?=\n\n    <details)', lambda _: note_html, html, count=1, flags=re.S)
        if not n:
            sys.exit("note block not found")
    if 'id="livePanel"' not in html:
        html = html.replace("<!--@@NOTE-END@@-->", '<!--@@NOTE-END@@-->\n\n    <div class="cx-card cx-live" id="livePanel" style="margin-bottom:18px;padding:18px 20px"></div>', 1)
    with_spec = stats["specimens"]
    roll = (f"<h4>Roll-up &amp; honest limits</h4>\n        <p>Per-declaration → per-component → per-lens, weighted equally. "
            f"Since {stamp} the tallies are <b>generated</b>: <code>scripts/build-compliance-catalogue.py</code> runs the same "
            f"classifier as <code>scripts/audit-css.py</code> over every component file ({stats['files']} files, "
            f"<b>{cov:.0f}% coverage / {health:.0f}% health</b>), attaches each finding’s file:line and selector, and keeps the "
            f"hand-written defect and fix wording wherever the same value is still there. Specimens are hand-built markup "
            f"({with_spec} of {stats['files']} files have one; the rest are scored from source). "
            f"The <b>on screen</b> panel comes from <code>experiments/token-xray/live-scan.mjs</code> on the running app. "
            f"The browser resolves <code>var()</code> away, so that scan compares each computed value with the token values: "
            f"a literal that happens to equal a token passes it, and the source scan is the arbiter. "
            f"Components are still weighted equally, whereas the adoption literature weights by <b>render frequency</b>.</p>")
    html = re.sub(r"<h4>Roll-up &amp; honest limits</h4>\s*<p>.*?</p>", lambda _: roll, html, count=1, flags=re.S)
    footer = (f'<span>Generated from <code>bristlenose/theme/</code> — {stamp} · {len(LENS_ORDER)} lenses, '
              f'{stats["files"]} component files. Switch lenses in the top bar.</span>\n'
              f'    <span>Re-run <code>scripts/build-compliance-catalogue.py</code> after CSS edits.</span>')
    html = re.sub(r'<span>Snapshot of <code>bristlenose/theme/</code>.*?</span>\s*<span>Specimens are live.*?</span>',
                  lambda _: footer, html, count=1, flags=re.S)
    header = (
        "<!-- ==========================================================================\n"
        "     Bristlenose CSS Design-System Compliance X-ray\n"
        f"     GENERATED {stamp} by scripts/build-compliance-catalogue.py — do not hand-edit the data.\n"
        f"     {len(LENS_ORDER)} lenses, {stats['files']} component files.\n\n"
        "     HOW IT WORKS\n"
        "     - Specimens are REAL components: the <style id=bn-theme> block is the shipped\n"
        "       bristlenose/theme/ CSS, in the order the report concatenates it. Each 2x2\n"
        "       quadrant is a container with data-color-theme + color-scheme, so one component\n"
        "       renders in all four theme combinations at once.\n"
        "     - Findings are generated from source (the browser resolves var() away, so a\n"
        "       token cannot be told from a literal at runtime): every declaration is\n"
        "       classified, with file:line and selector. Hand-written defect/fix wording and\n"
        "       specimen markup live in docs/design-system/compliance-specimens.json.\n"
        "     - The on-screen panel is docs/design-system/compliance-live.json, from\n"
        "       experiments/token-xray/live-scan.mjs --all against a running serve.\n"
        "     To refresh: .venv/bin/python scripts/build-compliance-catalogue.py [--live scan.json]\n"
        "     ========================================================================== -->"
    )
    html = re.sub(r"<!-- =+\n\s+Bristlenose CSS Design-System Compliance X-ray\n.*?=+ -->", lambda _: header, html,
                  count=1, flags=re.S)

    CATALOGUE.write_text(html, encoding="utf-8")
    print(f"wrote {CATALOGUE.relative_to(ROOT)}: {stats['files']} files, {with_spec} with specimens, "
          f"coverage {cov:.1f}% health {health:.1f}%, live={'yes' if live else 'no'}")
    for rel, cls in stats["stale"]:
        print(f"  stale specimen? {rel}: {', '.join(cls)}")
    if stats["mismatch"]:
        print(f"  MISMATCH vs audit-css.py: {stats['mismatch']}", file=sys.stderr)
        return 1
    return 0


LIVE_JS = r"""
/* ---- on-screen panel (from live-scan.mjs --all) ---- */
function renderLive(){
  const el=document.getElementById("livePanel"); if(!el) return;
  if(!LIVE){ el.innerHTML='<span class="cx-eyebrow">On screen</span><p style="margin:6px 0 0;color:var(--cx-muted)">No live scan recorded yet.</p>'; return; }
  const tabs=[...new Set(LIVE.pages.map(p=>p.tab))];
  const get=(t,s)=>LIVE.pages.find(p=>p.tab===t&&p.scheme===s);
  const vals={}; LIVE.pages.filter(p=>p.scheme==="light").forEach(p=>p.top.forEach(([k,n])=>{vals[k]=(vals[k]||0)+n;}));
  const top=Object.entries(vals).sort((a,b)=>b[1]-a[1]).slice(0,8);
  el.innerHTML=`<span class="cx-eyebrow">On screen — the running app, ${esc(LIVE.scannedAt)}</span>
    <p style="margin:6px 0 10px;color:var(--cx-muted);font-size:13px">Elements whose computed colour, size, radius or spacing matches no <code>--bn-*</code> token, per tab.</p>
    <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:28px">
      <table><tr><th>tab</th><th>light</th><th>dark</th></tr>${tabs.map(t=>`<tr><td>${esc(t)}</td><td>${get(t,"light")?get(t,"light").total:"—"}</td><td>${get(t,"dark")?get(t,"dark").total:"—"}</td></tr>`).join("")}</table>
      <table><tr><th>most common off-token value (light)</th><th>elements</th></tr>${top.map(([k,n])=>`<tr><td><code>${esc(k)}</code></td><td>${n}</td></tr>`).join("")}</table>
    </div>`;
}
"""

if __name__ == "__main__":
    sys.exit(main())
