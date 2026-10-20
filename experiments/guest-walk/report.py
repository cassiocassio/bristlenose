#!/usr/bin/env python3
"""report.py <baseline-dir> <tonight-dir> <out-dir> — the morning page for two walks.

Compares every screen and every menu-state of tonight's walk with the baseline
walk, and writes <out-dir>/index.html: a verdict line, a contact sheet grouped
by walk phase where only changed screens are pink, a detail panel per changed
screen (baseline | tonight | diff), and the menu-tree diff. Standard library
only; the pixel work is `walker diff` (CoreGraphics, no dependencies).

Design follows docs/mockups/guest-walk-diff.html. Proof of concept, 20 Oct 2026.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

WALKER = Path(__file__).with_name("walker-host")

# Regions where a difference is noise by construction, in capture pixels.
# Every mask carries its reason, which the page prints: masking is a decision,
# so it has to be visible.
MASKS: dict[str, list[tuple[tuple[int, int, int, int], str]]] = {
    "new-project-rename": [((80, 465, 360, 50), "text cursor blink in the rename field")],
    # The Welcome cards animate (AutoCode types its quote out), and the checkbox's
    # focus ring follows key-window timing. Better fixed by a walk-mode freeze or
    # Reduce Motion in the guest than masked; masked here so the PoC can proceed.
    "first-launch-1": [((40, 100, 930, 940), "Welcome card animation"), ((28, 1036, 64, 64), "focus ring timing")],
    "consent-accepted-1": [((40, 100, 930, 940), "Welcome card animation"), ((28, 1036, 64, 64), "focus ring timing")],
}

# Menu items whose state is not the app's: the tart guest agent shares the host's
# clipboard, so Edit ▸ Paste follows whatever was last copied on the host.
MENU_MASKS: dict[str, str] = {
    "Edit ▸ Paste": "follows the host clipboard (tart shares it)",
}

PHASES = [
    ("First launch", ("first-launch", "consent")),
    ("Sidebar & projects", ("empty-main", "new-project", "open-panel", "create-project")),
    ("Settings", ("settings-",)),
    ("Dialogs & sheets", ("about",)),
    ("Run lifecycle", ("run-",)),
    ("Lenses", ("lens-",)),
]

# Below this fraction a difference is reported but not painted as a change:
# a handful of antialiased pixels is not new work landing.
CHANGED_AT = 0.0005


def stem(name: str) -> str:
    """'06-settings-llm-provider-2.png' -> 'settings-llm-provider-2'."""
    return name.split("-", 1)[1].rsplit(".", 1)[0]


def phase_of(screen: str) -> str:
    for title, prefixes in PHASES:
        if screen.startswith(prefixes):
            return title
    return "Other"


def mask_arg(screen: str) -> tuple[str, list[str]]:
    key = next((k for k in MASKS if screen.startswith(k)), None)
    if not key:
        return "", []
    regions = MASKS[key]
    return ";".join(",".join(map(str, r)) for r, _ in regions), [why for _, why in regions]


def menus(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        d = json.loads(line)
        out[d["path"]] = d
    return out


def menu_diff(a: dict[str, dict], b: dict[str, dict]) -> list[str]:
    rows = []
    for p in sorted(set(a) | set(b)):
        if p in MENU_MASKS:
            continue
        if p not in a:
            rows.append(f"{p} — new item ({'enabled' if b[p]['enabled'] else 'disabled'})")
        elif p not in b:
            rows.append(f"{p} — gone")
        else:
            for k, label in (("enabled", "enabled"), ("shortcut", "shortcut"), ("checked", "checked")):
                if a[p][k] != b[p][k]:
                    rows.append(f"{p} — {label} {a[p][k]!r} → {b[p][k]!r}")
    return rows


def verdict_of(d: Path) -> str:
    v = d / "verdict.txt"
    return v.read_text().strip() if v.exists() else "NO VERDICT (the walk left no verdict file)"


def main() -> int:
    base, tonight, out = (Path(a) for a in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=True)
    img = out / "img"
    img.mkdir(exist_ok=True)

    b_shots = {stem(p.name): p for p in base.glob("[0-9][0-9]-*.png")}
    t_shots = {stem(p.name): p for p in tonight.glob("[0-9][0-9]-*.png")}
    screens = []
    for s in sorted(set(b_shots) | set(t_shots), key=lambda s: (t_shots.get(s) or b_shots[s]).name):
        entry = {"screen": s, "phase": phase_of(s), "masks": []}
        if s not in t_shots:
            entry["state"] = "missing"
            shutil.copy(b_shots[s], img / f"base-{s}.png")
        elif s not in b_shots:
            entry["state"] = "new"
            shutil.copy(t_shots[s], img / f"tonight-{s}.png")
        else:
            m, why = mask_arg(s)
            res = subprocess.run(
                [str(WALKER), "diff", str(b_shots[s]), str(t_shots[s]), str(img / f"diff-{s}.png"), m],
                capture_output=True, text=True, check=True,
            ).stdout.strip().split("\t")
            frac, bbox = float(res[0]), res[1]
            entry.update(frac=frac, bbox=bbox, masks=why, size=res[2] if len(res) > 2 else "")
            entry["state"] = "changed" if frac >= CHANGED_AT or entry["size"] else "same"
            shutil.copy(t_shots[s], img / f"tonight-{s}.png")
            shutil.copy(b_shots[s], img / f"base-{s}.png")
            hdr = t_shots[s].read_bytes()[16:24]
            entry["dims"] = (int.from_bytes(hdr[:4], "big"), int.from_bytes(hdr[4:], "big"))
        screens.append(entry)

    # Menu state per step: compared by step name (one menus file per step, not per window).
    b_menus = {p.name.split("-", 1)[1]: p for p in base.glob("*.menus.jsonl")}
    t_menus = {p.name.split("-", 1)[1]: p for p in tonight.glob("*.menus.jsonl")}
    menu_rows = []
    for k in sorted(set(b_menus) | set(t_menus)):
        for r in menu_diff(menus(b_menus.get(k, Path("-"))), menus(t_menus.get(k, Path("-")))):
            menu_rows.append((k.removesuffix(".menus.jsonl"), r))

    n_changed = sum(e["state"] == "changed" for e in screens)
    n_new = sum(e["state"] == "new" for e in screens)
    n_missing = sum(e["state"] == "missing" for e in screens)
    t_verdict, b_verdict = verdict_of(tonight), verdict_of(base)
    halted = t_verdict.startswith("HALTED")

    def tile(e: dict) -> str:
        s, st = e["screen"], e["state"]
        src = f"img/tonight-{s}.png" if st != "missing" else f"img/base-{s}.png"
        # A changed tile shows tonight's screen centred on the change, with the region
        # outlined in pink. The diff image itself is dimmed to near-white by design,
        # so as a thumbnail it reads as blank (20 Oct 2026 review).
        style = ""
        if st == "changed" and e["bbox"] != "-":
            x, y, w, h = map(int, e["bbox"].split(","))
            iw, ih = e["dims"]
            style = f' style="object-position:{(x + w / 2) / iw * 100:.0f}% {(y + h / 2) / ih * 100:.0f}%"'
        tag = {"changed": f"{e['frac'] * 100:.2f}% changed", "new": "NEW", "missing": "missing tonight",
               "same": "same" + (" · masked" if e["masks"] else "")}[st]
        return (f'<a class="tile {st}" href="#d-{html.escape(s)}" title="{html.escape(s)}">'
                f'<span class="frame"><img loading="lazy" src="{src}" alt=""{style}></span>'
                f'<span class="cap">{html.escape(s)}'
                f'<em>{tag}</em></span></a>')

    groups = []
    for title, _ in PHASES + [("Other", ())]:
        items = [e for e in screens if e["phase"] == title]
        if items:
            quiet = " all-same" if all(e["state"] == "same" for e in items) else ""
            groups.append(f'<div class="phase{quiet}"><h3>{html.escape(title)}</h3>'
                          f'<div class="grid">{"".join(map(tile, items))}</div></div>')

    details = []
    for e in screens:
        if e["state"] not in ("changed", "new", "missing"):
            continue
        s = e["screen"]
        panes = []
        if e["state"] != "new":
            panes.append(f'<figure><figcaption>baseline</figcaption><img src="img/base-{s}.png" alt=""></figure>')
        if e["state"] != "missing":
            panes.append(f'<figure><figcaption>tonight</figcaption><img src="img/tonight-{s}.png" alt=""></figure>')
        if e["state"] == "changed":
            panes.append(f'<figure><figcaption>diff</figcaption><img src="img/diff-{s}.png" alt=""></figure>')
        meta = (f"{e['frac'] * 100:.3f}% of pixels · changed region {e['bbox']} px"
                if e["state"] == "changed" else e["state"])
        if e.get("masks"):
            meta += " · masked: " + "; ".join(e["masks"])
        details.append(f'<section class="detail" id="d-{html.escape(s)}"><h3>{html.escape(s)}</h3>'
                       f'<p class="meta">{html.escape(meta)}</p><div class="panes">{"".join(panes)}</div></section>')

    menu_html = ("".join(f'<li><code>{html.escape(k)}</code> {html.escape(r)}</li>' for k, r in menu_rows)
                 or "<li class='quiet'>No menu item changed title, enabled state, shortcut or check mark.</li>")
    masked = [e for e in screens if e["masks"]]

    head = (f"{n_changed} of {len(screens)} screens changed"
            + (f" · {n_new} new" if n_new else "") + (f" · {n_missing} missing" if n_missing else "")
            + f" · {len(menu_rows)} menu {'change' if len(menu_rows) == 1 else 'changes'}")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Guest walk diff</title>
<style>
:root{{--bg:#f5f5f7;--panel:#fff;--ink:#1d1d1f;--muted:#6b6b72;--line:#dcdce1;--pink:#ff2d95;--pink-ink:#c4006a;
--pink-wash:rgba(255,45,149,.10);--sans:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#121214;--panel:#1b1b1e;--ink:#ececf0;--muted:#9b9ba4;--line:#323238;--pink-ink:#ff6fb5;--pink-wash:rgba(255,45,149,.13)}}}}
:root[data-theme=dark]{{--bg:#121214;--panel:#1b1b1e;--ink:#ececf0;--muted:#9b9ba4;--line:#323238;--pink-ink:#ff6fb5;--pink-wash:rgba(255,45,149,.13)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 var(--sans)}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:20px;margin:0 0 4px}}h2{{font-size:15px;margin:32px 0 8px}}h3{{font-size:13px;margin:20px 0 8px;color:var(--muted);font-weight:600}}
.verdict{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.verdict .big{{font-size:17px;font-weight:600}}.verdict .big b{{color:var(--pink-ink)}}
.meta,.quiet{{color:var(--muted);font-size:12.5px}}.halt{{color:#b00020;font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}}
.tile{{display:block;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden;color:inherit;text-decoration:none}}
.tile img{{display:block;width:100%;aspect-ratio:10/7;object-fit:cover;object-position:top left}}
.tile.same img{{filter:grayscale(1);opacity:.48}}
.frame{{position:relative;display:block}}
.tile.changed .frame{{outline:3px solid var(--pink-wash);outline-offset:-3px}}
.tile.changed{{border:3px solid var(--pink)}}.tile.new{{border:2px solid var(--muted)}}.tile.missing{{border:2px dashed var(--muted)}}
.tile.missing img{{opacity:.15}}
.cap{{display:block;padding:6px 8px;font:11.5px/1.3 var(--mono);word-break:break-word}}.cap em{{display:block;font-style:normal;color:var(--muted)}}
.tile.changed .cap em{{color:var(--pink-ink);font-weight:600}}
.detail{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--pink);border-radius:10px;padding:12px 16px;margin:14px 0}}
.detail h3{{margin:0;color:var(--ink);font-family:var(--mono)}}
.panes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:10px}}
figure{{margin:0}}figcaption{{font-size:11.5px;color:var(--muted);margin-bottom:4px}}figure img{{width:100%;border:1px solid var(--line);border-radius:6px}}
ul.menus{{list-style:none;padding:0;margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px}}
ul.menus li{{padding:8px 12px;border-top:1px solid var(--line);font-size:13px}}ul.menus li:first-child{{border-top:0}}
ul.menus li:not(.quiet){{background:var(--pink-wash);border-left:3px solid var(--pink);color:var(--pink-ink)}}
code{{font-family:var(--mono);font-size:12px}}
.filter{{margin:10px 0}}.filter button{{font:inherit;border:1px solid var(--line);background:var(--panel);color:inherit;border-radius:6px;padding:3px 10px;cursor:pointer}}
.filter button[aria-pressed=true]{{border-color:var(--ink)}}
body.only-changed .tile.same,body.only-changed .phase.all-same{{display:none}}
</style></head><body><main>
<h1>Guest walk</h1>
<div class="verdict"><div class="big">{'<span class="halt">' + html.escape(t_verdict) + '</span>' if halted else '<b>' + html.escape(head.split(' of ')[0]) + '</b> of ' + html.escape(head.split(' of ', 1)[1])}</div>
<div class="meta">tonight: {html.escape(t_verdict)} · baseline: {html.escape(b_verdict)} · {html.escape(tonight.name)} vs {html.escape(base.name)}</div>
<div class="meta">{len(masked)} {'screen has' if len(masked) == 1 else 'screens have'} masked regions: {html.escape('; '.join(f"{e['screen']} ({', '.join(e['masks'])})" for e in masked)) or 'none'}</div></div>
<div class="filter"><button aria-pressed="true" id="all">All</button> <button aria-pressed="false" id="chg">Changed &amp; new only</button></div>
<h2>Screens</h2>{''.join(groups)}
<h2>Changed screens</h2>{''.join(details) or "<p class='quiet'>None.</p>"}
<h2>Menus</h2><ul class="menus">{menu_html}</ul>
</main><script>
const a=document.getElementById('all'),c=document.getElementById('chg');
a.onclick=()=>{{document.body.classList.remove('only-changed');a.setAttribute('aria-pressed','true');c.setAttribute('aria-pressed','false')}};
c.onclick=()=>{{document.body.classList.add('only-changed');c.setAttribute('aria-pressed','true');a.setAttribute('aria-pressed','false')}};
</script></body></html>"""
    (out / "index.html").write_text(page)
    print(f"{head}  ->  {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
