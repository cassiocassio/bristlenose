"""Derive Bristlenose palette CSS from each brand's official colours.

Every role the brand names is taken verbatim; the rest are mixes of those,
following the relationships palette-default.css already uses. Any colour used
as text that fails WCAG AA (4.5:1) on bg and quote-bg is nudged toward the ink
until it passes, and the report says so.
"""
from pathlib import Path

def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def hexc(c): return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)
def mix(a, b, t):  # t of a into b
    a, b = rgb(a), rgb(b); return hexc(tuple(a[i]*t + b[i]*(1-t) for i in range(3)))
def lum(h):
    def ch(v):
        v /= 255; return v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r, g, b = rgb(h); return 0.2126*ch(r) + 0.7152*ch(g) + 0.0722*ch(b)
def cr(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la+0.05)/(lb+0.05)
def rgba(h, a): r, g, b = rgb(h); return f"rgba({r}, {g}, {b}, {a})"

NOTES = []
def ensure(name, col, grounds, ink, target=4.5):
    t, out = 0.0, col
    while min(cr(out, g) for g in grounds) < target and t < 1:
        t += 0.01; out = mix("#000000" if lum(grounds[0]) > 0.5 else "#ffffff", col, t)
    if out != col:
        NOTES.append(f"{name}: {col} -> {out} ({min(cr(col,g) for g in grounds):.2f} -> {min(cr(out,g) for g in grounds):.2f})")
    return out

def derive(s, dark, tag):
    bg, text = s["bg"], s["text"]
    quote = s.get("quote_bg") or mix(text, bg, 0.04 if dark else 0.025)
    paper = bg if dark else s.get("paper") or mix(text, bg, 0.035)
    sheet = s.get("sheet") or (mix(text, bg, 0.07) if dark else s.get("sheet_light", "#ffffff" if lum(bg) > 0.97 else mix("#ffffff", bg, 0.55)))
    grounds = [bg, quote, paper]
    muted = ensure(f"{tag} muted", s["muted"], grounds, text)
    accent = ensure(f"{tag} accent", s["accent"], [bg, quote], text)
    neg = ensure(f"{tag} negative", s["negative"], [bg], text)
    pos = ensure(f"{tag} positive", s["positive"], [bg], text, 3.0)
    warn = s["warning"]
    border = s["border"]; bh = s["border_hover"]
    inspector = s.get("inspector") or mix(text, bg, 0.045 if dark else 0.025)
    badge = s.get("badge_bg") or mix(text, bg, 0.10 if dark else 0.07)
    badge_text = ensure(f"{tag} badge-text", s.get("badge_text") or mix(text, muted, 0.6), [badge], text)
    shadow_dark = "rgba(0, 0, 0, 0.4)"
    a1, a2 = (0.12, 0.2) if dark else (0.06, 0.11)
    v1, v2 = (0.2, 0.4) if dark else (0.15, 0.3)
    return {
        "--bn-colour-bg": bg,
        "--bn-colour-text": text,
        "--bn-colour-muted": muted,
        "--bn-colour-border": border,
        "--bn-colour-accent": accent,
        "--bn-colour-hover": mix(accent, bg, 0.12 if dark else 0.09),
        "--bn-colour-inspector-bg": inspector,
        "--bn-colour-quote-bg": quote,
        "--bn-colour-paper": paper,
        "--bn-colour-sheet": sheet,
        "--bn-colour-badge-bg-paper": mix(text, paper, 0.12 if dark else 0.08),
        "--bn-colour-badge-bg": badge,
        "--bn-colour-badge-text": badge_text,
        "--bn-colour-user-tag-bg": badge,
        "--bn-colour-user-tag-text": badge_text,
        "--bn-colour-crop-bg": mix(warn, bg, 0.16 if dark else 0.12),
        "--bn-crop-handle-colour": warn,
        "--bn-crop-handle-hover": mix(text, warn, 0.25),
        "--bn-colour-active-bg": mix(pos, bg, 0.14 if dark else 0.10),
        "--bn-colour-highlight": mix(warn, bg, 0.45 if dark else 0.40),
        "--bn-colour-cited-bg": mix(warn, bg, 0.22 if dark else 0.18),
        "--bn-colour-negative": neg,
        "--bn-colour-positive": pos,
        "--bn-colour-warning": warn,
        "--bn-glow-colour": rgba(accent, a1),
        "--bn-glow-colour-strong": rgba(accent, a2),
        "--bn-minimap-quote": border,
        "--bn-minimap-heading": bh,
        "--bn-minimap-viewport-bg": rgba(accent, v1),
        "--bn-minimap-viewport-border": rgba(accent, v2),
        "--bn-coverage-report": mix(accent, bg, 0.55),
        "--bn-coverage-moderator": warn,
        "--bn-coverage-omitted": bh,
        "--bn-group-none": quote,
        "--bn-bar-none": bh,
        "--bn-colour-border-hover": bh,
        "--bn-colour-icon-idle": mix(muted, bg, 0.45),
        "--bn-colour-starred": muted,
        "--bn-colour-shadow": shadow_dark if dark else rgba(s["shadow"], 0.1),
        "--bn-focus-ring": None,  # composed below
        "--bn-hover-bg": rgba(text, 0.06 if dark else 0.04),
        "--bn-hover-bg-subtle": rgba(text, 0.04 if dark else 0.03),
        "--bn-selection-bg": mix(accent, bg, 0.16 if dark else 0.10),
        "--bn-selection-border": accent,
        "--bn-selection-bg-inactive": mix(text, bg, 0.09 if dark else 0.07),
        "--bn-selection-border-inactive": mix(muted, bg, 0.6),
        "--bn-nav-selection-bg": mix(text, inspector, 0.10 if dark else 0.08),  # sits on the inspector
        "--bn-colour-suggestion": accent,
        "--bn-colour-suggestion-bg": mix(accent, bg, 0.12 if dark else 0.07),
        "_ring": rgba(accent, 0.2 if dark else 0.14),
    }

GROUPS = [
    ("Colour palette", ["--bn-colour-bg", "--bn-colour-text", "--bn-colour-muted", "--bn-colour-border", "--bn-colour-accent", "--bn-colour-hover", "--bn-colour-inspector-bg"]),
    ("Semantic surfaces", ["--bn-colour-quote-bg", "--bn-colour-paper", "--bn-colour-sheet", "--bn-colour-badge-bg-paper", "--bn-colour-badge-bg", "--bn-colour-badge-text", "--bn-colour-user-tag-bg", "--bn-colour-user-tag-text", "--bn-colour-crop-bg", "--bn-crop-handle-colour", "--bn-crop-handle-hover", "--bn-colour-active-bg", "--bn-colour-highlight", "--bn-colour-cited-bg"]),
    ("Destructive, success and caution", ["--bn-colour-negative", "--bn-colour-positive", "--bn-colour-warning"]),
    ("Playback-sync glow", ["--bn-glow-colour", "--bn-glow-colour-strong"]),
    ("Minimap", ["--bn-minimap-quote", "--bn-minimap-heading", "--bn-minimap-viewport-bg", "--bn-minimap-viewport-border"]),
    ("Transcript coverage bar", ["--bn-coverage-report", "--bn-coverage-moderator", "--bn-coverage-omitted"]),
    ("Neutral group card and histogram bar", ["--bn-group-none", "--bn-bar-none"]),
    ("Interactive elements", ["--bn-colour-border-hover", "--bn-colour-icon-idle", "--bn-colour-starred", "--bn-colour-shadow"]),
    ("Focus and selection", ["--bn-focus-ring", "--bn-selection-bg", "--bn-selection-border", "--bn-selection-bg-inactive", "--bn-selection-border-inactive", "--bn-nav-selection-bg"]),
    ("Hover backgrounds", ["--bn-hover-bg", "--bn-hover-bg-subtle"]),
    ("Legacy aliases", ["--bn-colour-suggestion", "--bn-colour-suggestion-bg"]),
]

def emit(key, header, light, dark):
    L, D = derive(light, False, f"{key} light"), derive(dark, True, f"{key} dark")
    sel = f'[data-color-theme="{key}"]'
    out = [header.rstrip() + "\n", f"{sel} {{"]
    for title, toks in GROUPS:
        out.append(f"    /* {title} */")
        for t in toks:
            if t == "--bn-colour-cited-bg":
                continue  # dark-block only, as in the other palettes
            v = f"0 0 0 2px {L['_ring']}" if t == "--bn-focus-ring" else L[t]
            out.append(f"    {t}: {v};")
        out.append("")
    sh = rgb(light["shadow"])
    out += ["    /* Shadows: the same in both appearances */",
            f"    --bn-focus-shadow: 0 3px 12px rgba({sh[0]}, {sh[1]}, {sh[2]}, 0.12), 0 0 0 1px rgba({sh[0]}, {sh[1]}, {sh[2]}, 0.05);",
            f"    --bn-overlay-shadow: 4px 0 16px rgba({sh[0]}, {sh[1]}, {sh[2]}, 0.08);", "}", "",
            "@supports (color: light-dark(#000, #fff)) {", f"    {sel} {{"]
    for title, toks in GROUPS:
        out.append(f"        /* {title} */")
        for t in toks:
            if t == "--bn-focus-ring":
                v = f"0 0 0 2px light-dark({L['_ring']}, {D['_ring']})"
            else:
                v = f"light-dark({L[t]}, {D[t]})"
            out.append(f"        {(t + ':').ljust(32)}{v};")
        out.append("")
    out[-1:] = ["    }", "}", ""]
    return "\n".join(out)

GALLERY_CSS = """
body { margin: 0; padding: 24px 16px; font: 13px/1.45 Inter, -apple-system, system-ui, sans-serif; background: #e9e9ec; color: #1a1a1a; }
@media (prefers-color-scheme: dark) { body { background: #0b0b0c; color: #ddd; } }
h1 { font-size: 20px; margin: 0 0 4px; } section { margin: 20px 0; } h2 { font-size: 15px; margin: 0 0 8px; }
.pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.cell { display: grid; grid-template-columns: 96px 1fr; border-radius: 10px; overflow: hidden; background: var(--bn-colour-bg); color: var(--bn-colour-text); border: 1px solid var(--bn-colour-border); }
.inspector { background: var(--bn-colour-inspector-bg); border-right: 1px solid var(--bn-colour-border); padding: 12px 8px; font-weight: 600; color: var(--bn-colour-muted); }
.nav { display: block; margin-top: 8px; padding: 3px 6px; border-radius: 5px; background: var(--bn-nav-selection-bg); color: var(--bn-colour-accent); font-weight: 500; }
.main { padding: 12px 14px; } h3 { margin: 0; font-size: 15px; } .muted { color: var(--bn-colour-muted); margin: 2px 0 10px; }
blockquote { margin: 0 0 10px; padding: 10px 12px; background: var(--bn-colour-quote-bg); border-left: 3px solid var(--bn-colour-border-hover); border-radius: 6px; font-size: 15px; }
.badges { margin-top: 8px; display: flex; gap: 6px; }
.badge, .tag { font: 11.5px ui-monospace, Menlo, monospace; padding: 1px 6px; border-radius: 4px; }
.badge { background: var(--bn-colour-badge-bg); color: var(--bn-colour-badge-text); } .tag { background: var(--bn-colour-user-tag-bg); color: var(--bn-colour-user-tag-text); }
a { color: var(--bn-colour-accent); } mark { background: var(--bn-colour-highlight); color: inherit; }
.row { display: flex; flex-wrap: wrap; gap: 6px; } .row span { padding: 2px 8px; border-radius: 5px; }
.sel { background: var(--bn-selection-bg); box-shadow: inset 0 0 0 1px var(--bn-selection-border); }
.pos { background: var(--bn-colour-active-bg); color: var(--bn-colour-positive); }
.neg { color: var(--bn-colour-negative); box-shadow: inset 0 0 0 1px var(--bn-colour-negative); }
.warn { background: var(--bn-colour-crop-bg); color: var(--bn-colour-text); box-shadow: inset 0 0 0 1px var(--bn-colour-warning); }
"""

GALLERY = [("default", "Default"), ("edo", "Edo"), ("catppuccin", "Catppuccin"), ("gruvbox", "Gruvbox"),
           ("rose-pine", "Rosé Pine"), ("solarized", "Solarized")]


def gallery(colors: Path) -> str:
    css = "\n".join((colors / f"palette-{k}.css").read_text() for k, _ in GALLERY)
    def cell(k, scheme):
        return f'''<div class="cell" data-color-theme="{k}" style="color-scheme:{scheme}">
  <div class="inspector">Tags<span class="nav">Frustration</span></div>
  <div class="main">
    <h3>Onboarding friction</h3>
    <p class="muted">Six quotes · three participants · 00:14:32</p>
    <blockquote>“I couldn't find where the export lived, so I just screenshotted it.”
      <div class="badges"><span class="badge">frustration</span><span class="tag">export</span></div></blockquote>
    <p>Read the <a href="#">full transcript</a>, or <mark>search for “export”</mark>.</p>
    <div class="row"><span class="sel">Selected</span><span class="pos">Accepted</span><span class="neg">Delete</span><span class="warn">Partial</span></div>
  </div>
</div>'''
    rows = "\n".join(f'<section><h2>{n}</h2><div class="pair">{cell(k, "light")}{cell(k, "dark")}</div></section>'
                     for k, n in GALLERY)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Palette gallery</title>
<style>
/* Generated by experiments/brand-palettes/gen.py from the shipped palette files. Rerun it; don't hand-edit. */
{css}
{GALLERY_CSS}</style></head><body>
<h1>Palette gallery</h1>
<p>Every palette in light and dark, from the shipped palette files. A rough sample of the main surfaces, not a page of the app.</p>
{rows}
</body></html>
'''


def colorset(light: str, dark: str) -> str:
    """An Xcode colorset (Any + Dark), in the shape of the hand-made Edo ones."""
    import json
    def comp(h):
        r, g, b = rgb(h)
        return {"alpha": "1.000", "blue": f"0x{b:02X}", "green": f"0x{g:02X}", "red": f"0x{r:02X}"}
    return json.dumps({"colors": [
        {"color": {"color-space": "srgb", "components": comp(light)}, "idiom": "universal"},
        {"appearances": [{"appearance": "luminosity", "value": "dark"}],
         "color": {"color-space": "srgb", "components": comp(dark)}, "idiom": "universal"},
    ], "info": {"author": "xcode", "version": 1}}, indent=2) + "\n"


# The native sidebar's four concepts (SidebarPalette.Concept), read off the CSS tokens
# the web report uses, so both sides of the seam share one value.
SIDEBAR = {"Paper": "--bn-colour-bg", "Ink": "--bn-colour-text",
           "Accent": "--bn-colour-accent", "Lozenge": "--bn-nav-selection-bg"}


def asset_stem(key: str) -> str:
    """Mirror of SidebarPalette.assetStem: "rose-pine" -> "RosePine"."""
    return "".join(part.capitalize() for part in key.split("-"))


def write_colorsets(assets: Path, key: str, light: dict, dark: dict) -> None:
    L, D = derive(light, False, key), derive(dark, True, key)
    for concept, token in SIDEBAR.items():
        d = assets / f"Palette{asset_stem(key)}{concept}.colorset"
        d.mkdir(exist_ok=True)
        (d / "Contents.json").write_text(colorset(L[token], D[token]))


if __name__ == "__main__":
    import palettes
    repo = Path(__file__).resolve().parents[2]
    colors = repo / "bristlenose/theme/colors"
    for key, (header, light, dark) in palettes.PALETTES.items():
        NOTES.clear()
        css = emit(key, header, light, dark)
        adj = "\n".join("   AA nudge: " + n for n in NOTES) or "   No colour needed nudging for WCAG AA."
        (colors / f"palette-{key}.css").write_text(css.replace("{adjust}", adj))
        print(key); print(adj)
    assets = repo / "desktop/Bristlenose/Bristlenose/Assets.xcassets"
    for key, (_, light, dark) in palettes.PALETTES.items():
        write_colorsets(assets, key, light, dark)
    print("wrote the sidebar colorsets")
    (repo / "docs/mockups/palette-gallery.html").write_text(gallery(colors))
    print("wrote docs/mockups/palette-gallery.html")
