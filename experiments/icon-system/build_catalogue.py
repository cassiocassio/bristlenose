"""Build docs/mockups/icon-catalogue/index.html from capture_icons.mjs output.

Local only: the screenshots carry a real project's text, so the folder is gitignored.
    python3 experiments/icon-system/build_catalogue.py docs/mockups/icon-catalogue
"""

from __future__ import annotations

import html
import json
import struct
import sys
from pathlib import Path


def size(p: Path) -> tuple[int, int]:
    with p.open("rb") as f:
        h = f.read(24)
    return struct.unpack(">II", h[16:24])


def img(out: Path, name: str | None, scale: float, cls: str = "") -> str:
    if not name or not (out / "shots" / name).exists():
        return '<div class="none">—</div>'
    w, h = size(out / "shots" / name)
    # shots are 2x pixels: /2 is real size, *2 is a 4x pixel zoom
    return (f'<img class="{cls}" src="shots/{name}" width="{w * scale:g}" height="{h * scale:g}" '
            f'alt="">')


def main(out: Path) -> None:
    data = json.loads((out / "catalogue.json").read_text())
    groups: dict[str, list] = {}
    for it in data["items"]:
        groups.setdefault(it["step"], []).append(it)
    rows = []
    for step, items in groups.items():
        rows.append(f'<tr class="grp"><th colspan="6">{html.escape(step)} '
                    f'<span>{html.escape(items[0]["url"])}</span></th></tr>')
        for it in items:
            what = it.get("glyph") or it.get("row") or "unmapped svg"
            kind = {"svg": "SVG", "glyph": "character", "pseudo": f"CSS {it.get('pseudo', '')}"}[it["kind"]]
            prop = it["lucide"] or "— keep (by decision)" if it.get("glyph") == "★" else (it["lucide"] or "— no mapping")
            link = (f' · <a href="../icon-system-side-by-side.html#icon-{it["row"]}">sheet row</a>'
                    if it.get("row") else "")
            rows.append(
                f'<tr id="cat-{it["base"]}"><td class="meta"><a class="id" href="#cat-{it["base"]}">{it["base"]}</a>'
                f'<div><b>{html.escape(what)}</b> · {kind}</div>'
                f'<div class="ctx">{html.escape(it["ctx"])}</div>'
                f'<div class="ctx">{html.escape(it["aria"] or it["text"])}</div>'
                f'<div class="to">→ <code>{html.escape(prop)}</code>{link}</div>'
                + (f'<div class="ctx">text {it["stemInfo"]["size"]} / {it["stemInfo"]["weight"]} → stem {it["stemInfo"]["stem"]:.3f} em'
                   f' = {max(1.0, it["stemInfo"]["stem"] * float(it["stemInfo"]["size"].rstrip("px"))):.2f} px</div>' if it.get("stemInfo") else "")
                + '</td>'
                f'<td>{img(out, it["base"] + "-before.png", 0.5)}</td>'
                f'<td>{img(out, it.get("after"), 0.5) if not it.get("afterFailed") else "<div class=none>capture failed — see the side-by-side sheet</div>"}</td>'
                f'<td class="zoom">{img(out, it["base"] + "-zoom.png", 2, "px")}</td>'
                f'<td class="zoom">{img(out, it.get("afterZoom"), 2, "px")}</td>'
                f'<td><textarea data-note="{it["base"]}" placeholder="note"></textarea></td></tr>')
    page = TEMPLATE.replace("{{ROWS}}", "\n".join(rows)).replace("{{N}}", str(len(data["items"]))) \
        .replace("{{WHEN}}", data["when"][:16].replace("T", " ")).replace("{{BASE}}", data["base"])
    (out / "index.html").write_text(page)
    print(f"wrote {out / 'index.html'}")


INTRO_FIRST = """<b>Before</b> is the app as it is. <b>After</b> is the same
place with the proposed Lucide icon swapped in live, stroke by the stem rule: the stem of the icon's own text, at its weight and size (shown per row), never under 1 px."""
INTRO_COMPARE = """<b>Before</b> is the first capture, before the migration; <b>now</b> is the
same control captured again from the migrated app. Matched by page and control name."""

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Icon catalogue — in place, before and after</title>
<style>
:root { color-scheme: light dark; --bg: light-dark(#fff,#111); --fg: light-dark(#1a1a1a,#e5e7eb);
  --muted: light-dark(#6b7280,#9ca3af); --line: light-dark(#e5e7eb,#2d2d2d); --tint: light-dark(#f9fafb,#1a1a1a);
  --accent: light-dark(#007aff,#0a84ff); }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.45 Inter, -apple-system, system-ui, sans-serif; }
main { max-width: 1500px; margin: 0 auto; padding: 20px 16px 80px; }
h1 { font-size: 22px; font-weight: 490; margin: 0 0 4px; }
.sub { color: var(--muted); font-size: 13px; margin: 0 0 12px; }
.bar { position: sticky; top: 0; background: var(--bg); padding: 8px 0; border-bottom: 1px solid var(--line);
  display: flex; gap: 12px; align-items: center; font: 12px ui-monospace, monospace; z-index: 2; }
.bar button { font: inherit; padding: 3px 8px; border: 1px solid var(--line); border-radius: 4px; background: var(--tint); color: var(--fg); }
table { border-collapse: collapse; width: 100%; }
thead th { position: sticky; top: 41px; background: var(--bg); z-index: 1; text-align: left;
  font: 10px ui-monospace, monospace; text-transform: uppercase; letter-spacing: .05em; color: var(--muted);
  padding: 6px 8px; border-bottom: 1px solid var(--line); }
tr.grp th { text-align: left; padding: 22px 8px 6px; font-size: 16px; font-weight: 490; border-bottom: 1px solid var(--line); }
tr.grp th span { font: 11px ui-monospace, monospace; color: var(--muted); margin-left: 8px; }
td { padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
tr:target { background: light-dark(#e8f0fe,#1e293b); }
td.meta { width: 260px; font-size: 12px; }
.id { font: 11px ui-monospace, monospace; color: var(--accent); text-decoration: none; }
.ctx { font: 11px ui-monospace, monospace; color: var(--muted); word-break: break-all; }
.to { margin-top: 4px; } .to a { color: var(--accent); }
td img { display: block; border: 1px solid var(--line); border-radius: 4px; background: #fff; }
img.px { image-rendering: pixelated; }
td img { max-width: 520px; height: auto; }
td.zoom img { max-width: 280px; }
table { table-layout: auto; }
.none { color: var(--muted); }
textarea { width: 170px; min-height: 60px; font: 12px Inter, system-ui; border: 1px solid var(--line);
  border-radius: 4px; background: var(--bg); color: var(--fg); padding: 4px; }
dialog textarea { width: 100%; height: 50vh; font: 12px ui-monospace, monospace; }
</style></head><body><main>
<h1>Icon catalogue — every icon in place, before and after</h1>
<p class="sub">{{N}} icons captured from the running app ({{BASE}}) on {{WHEN}} by
experiments/icon-system/capture_icons.mjs. <b>Before</b> is the app as it is. <b>After</b> is the same
place with the proposed Lucide icon swapped in live, stroke by the stem rule: the stem of the icon's own text, at its weight and size (shown per row), never under 1 px.
Before/after are real size; the zooms are the same 2× pixels at 4×, unsmoothed. Local only: these
screenshots carry the project's text. Not captured: icons that need a state the walk doesn't reach
(tapestry quote popover, AutoCode and threshold dialogs, activity chips, toasts, search token menu) —
see the side-by-side sheet for those.</p>
<div class="bar"><button type="button" id="copy">Copy my notes</button><span id="count"></span></div>
<table><thead><tr><th>icon</th><th>before · in place</th><th>after · Lucide</th><th>before · zoom</th>
<th>after · zoom</th><th>note</th></tr></thead><tbody>
{{ROWS}}
</tbody></table></main>
<dialog id="out"><p>Paste this back into the conversation.</p><textarea readonly></textarea>
<form method="dialog"><button>Close</button></form></dialog>
<script>
(() => { const KEY = "bn-icon-catalogue-v1"; let st = {};
  try { st = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
  document.querySelectorAll("textarea[data-note]").forEach(t => { if (st[t.dataset.note]) t.value = st[t.dataset.note];
    t.addEventListener("input", () => { st[t.dataset.note] = t.value; save(); }); });
  document.getElementById("copy").addEventListener("click", () => {
    const lines = ["## Icon catalogue — notes", ""];
    for (const [k, v] of Object.entries(st)) if (v.trim()) lines.push(`- cat-${k}: ${v.trim()}`);
    const d = document.getElementById("out"); d.querySelector("textarea").value = lines.join("\\n"); d.showModal();
    try { navigator.clipboard.writeText(lines.join("\\n")); } catch (e) {} });
})();
</script></body></html>
"""

def compare(out: Path, final: Path) -> None:
    """compare.html: each icon as first captured (before any migration) beside the
    same control captured again from the running app, matched by page and name."""
    first = json.loads((out / "catalogue.json").read_text())["items"]
    now = json.loads((final / "catalogue.json").read_text())["items"]

    def key(i: dict) -> tuple[str, str]:
        # a label that held the glyph ("▶ Config") is the same control once it is gone
        label = "".join(c for c in (i["aria"] or i["text"]) if c not in "×✕✗✓▶▸▾▼▴▲⌃↩✎✦⊘⚠↗+")
        return i["step"], " ".join(label.split())[:40]

    by_key = {key(i): i for i in now}
    rows = []
    for it in first:
        n = by_key.get(key(it))
        rel = final.name
        cells = (f'<td>{img(out, it["base"] + "-before.png", 0.5)}</td>'
                 f'<td class="zoom">{img(out, it["base"] + "-zoom.png", 2, "px")}</td>')
        if n:
            cells += (f'<td>{img(final, n["base"] + "-before.png", 0.5).replace("shots/", rel + "/shots/")}</td>'
                      f'<td class="zoom">{img(final, n["base"] + "-zoom.png", 2, "px").replace("shots/", rel + "/shots/")}</td>')
        else:
            cells += '<td colspan="2" class="none">not matched in the final capture (label changed, or not reached)</td>'
        what = it.get("glyph") or it.get("row") or "svg"
        rows.append(f'<tr id="cmp-{it["base"]}"><td class="meta"><a class="id" href="#cmp-{it["base"]}">{it["base"]}</a>'
                    f'<div><b>{html.escape(what)}</b></div><div class="ctx">{html.escape(it["aria"] or it["text"])}</div></td>'
                    f'{cells}<td><textarea data-note="{it["base"]}" placeholder="note"></textarea></td></tr>')
    page = TEMPLATE.replace("{{ROWS}}", "\n".join(rows)).replace("{{N}}", str(len(first))) \
        .replace("{{WHEN}}", json.loads((final / "catalogue.json").read_text())["when"][:16].replace("T", " ")) \
        .replace("{{BASE}}", "the running app") \
        .replace("<th>after · Lucide</th><th>before · zoom</th>\n<th>after · zoom</th>",
                 "<th>before · zoom</th><th>now · in place</th>\n<th>now · zoom</th>") \
        .replace("Icon catalogue — every icon in place, before and after", "Icon catalogue — before tonight, and now") \
        .replace("<title>Icon catalogue — in place, before and after</title>", "<title>Icon catalogue — before and now</title>") \
        .replace(INTRO_FIRST, INTRO_COMPARE) \
        .replace("bn-icon-catalogue-v1", "bn-icon-compare-v1")
    (out / "compare.html").write_text(page)
    print(f"wrote {out / 'compare.html'}")


def inline(page: Path) -> None:
    """A copy with every image embedded: the app's preview pane opens a local file as a
    data: URL, from which relative image paths cannot load."""
    import base64
    import re

    h = page.read_text()
    h = re.sub(r'src="([^"]+\.png)"', lambda m: 'src="data:image/png;base64,'
               + base64.b64encode((page.parent / m.group(1)).read_bytes()).decode() + '"', h)
    out = page.with_name(page.stem + "-inlined.html")
    out.write_text(h)
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        compare(Path(sys.argv[1]), Path(sys.argv[2]))
        inline(Path(sys.argv[1]) / "compare.html")
    else:
        main(Path(sys.argv[1]))
        inline(Path(sys.argv[1]) / "index.html")
