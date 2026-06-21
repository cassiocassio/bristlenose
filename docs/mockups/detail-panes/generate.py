#!/usr/bin/env python3
"""Synthetic detail-pane mockups for the macOS desktop shell.

Generates one SVG per detail-pane state catalogued in
docs/design-detail-panes-catalogue.md. These are *synthetic* vector mockups
(not live screen captures) — the real SwiftUI panes need the signed sidecar +
sandbox stack, which can't run in a headless/CI context. Each frame draws the
full app window (sidebar + unified toolbar + detail pane) at macOS proportions,
because half the story is that the *sidebar* carries state the detail pane does
not.

Run:  python3 generate.py        # writes svg/*.svg
Then: rasterise with qlmanage (see render-png.sh) for png/*.png

Pure stdlib. No dependencies. Throwaway design artifact (docs/mockups is tracked
but never shipped) — bespoke styling is fine here per the repo conventions.
"""

from __future__ import annotations

import html
from pathlib import Path

# ── geometry ────────────────────────────────────────────────────────────────
M = 24                       # outer margin
W, H = 1000, 628             # window size
SB = 240                     # sidebar width
TB = 52                      # toolbar height
WX, WY = M, M                # window origin
SBX = WX                     # sidebar x
DX = WX + SB                 # detail x  (264)
DW = W - SB                  # detail width (760)
DY = WY + TB                 # detail content top (76)
DH = H - TB                  # detail content height (576)
DCX = DX + DW / 2            # detail centre x (644)
DCY = DY + DH / 2            # detail centre y (364)
SVGW = W + 2 * M             # 1048
CAP_Y = WY + H + 16          # caption strip top
CONTENT_H = CAP_Y + 48 + M   # content height (window + caption)
SVGSQ = SVGW                 # square canvas so qlmanage thumbnails don't crop
VOFF = (SVGSQ - CONTENT_H) / 2   # vertical centering offset
SVGH = SVGSQ

# ── palette (macOS light) ───────────────────────────────────────────────────
C_WIN = "#FFFFFF"
C_SIDEBAR = "#E9E9EC"
C_TOOLBAR = "#F4F4F6"
C_HAIR = "#D5D5DA"
C_TEXT = "#1D1D1F"
C_SEC = "#86868B"
C_TERT = "#AEAEB2"
C_ACCENT = "#0A84FF"
C_GREEN = "#28C840"
C_ORANGE = "#FF9F0A"
C_RED = "#FF3B30"
C_CLOUD = "#5E9CEA"
C_CARD = "#F5F5F7"
C_CHIP = "#EAEAEC"

FONT = "-apple-system, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif"
MONO = "'SF Mono', ui-monospace, Menlo, monospace"

VERDICT = {
    "designed":   ("#E7F8EC", "#1A7F37", "Designed"),
    "exists":     ("#E6F0FE", "#0050C7", "Exists (product)"),
    "thin":       ("#EFEFF1", "#5A5A5F", "Thin / under-designed"),
    "accidental": ("#FFF2E0", "#9A5B00", "Accidental / plumbing"),
    "gap":        ("#FFE9E7", "#B3261E", "GAP — no pane"),
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ── primitives ──────────────────────────────────────────────────────────────
def rrect(x, y, w, h, r, fill="none", stroke="none", sw=1, opacity=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{r:.1f}" ry="{r:.1f}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}"{d}/>')


def line(x1, y1, x2, y2, stroke, sw=1.5, cap="round", opacity=1):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}" opacity="{opacity}"/>')


def circle(cx, cy, r, fill="none", stroke="none", sw=1, opacity=1):
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>')


def text(x, y, s, size=13, fill=C_TEXT, weight=400, anchor="middle",
         family=FONT, opacity=1, ls="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" opacity="{opacity}" '
            f'letter-spacing="{ls}" style="dominant-baseline:auto">{esc(s)}</text>')


def path(d, fill="none", stroke="none", sw=1.5, cap="round", join="round", opacity=1):
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="{cap}" stroke-linejoin="{join}" opacity="{opacity}"/>')


# ── glyphs (drawn in a 72×72 box, centred at cx,cy) ──────────────────────────
def _g(cx, cy, body, s=72):
    return f'<g transform="translate({cx - s/2:.1f},{cy - s/2:.1f})">{body}</g>'


def glyph(name, cx, cy, color=C_TERT, sw=2.4, s=72):
    p = []
    if name == "drive_warning":
        p.append(rrect(8, 24, 44, 20, 4, stroke=color, sw=sw))
        p.append(line(15, 39, 30, 39, color, sw))
        p.append(circle(45, 39, 1.6, fill=color))
        p.append(path("M48,34 L66,34 L57,52 Z", stroke=color, sw=sw))
        p.append(line(57, 40, 57, 46, color, sw))
        p.append(circle(57, 49.5, 1.3, fill=color))
    elif name == "folder_question":
        p.append(path("M10,28 v28 a4,4 0 0 0 4,4 h44 a4,4 0 0 0 4,-4 v-22 "
                      "a4,4 0 0 0 -4,-4 h-22 l-6,-6 h-12 a4,4 0 0 0 -4,4 z",
                      stroke=color, sw=sw))
        p.append(text(36, 52, "?", size=20, fill=color, weight=600))
    elif name == "cloud":
        p.append(path("M22,50 a11,11 0 0 1 1,-22 a16,16 0 0 1 30,-3 "
                      "a10,10 0 0 1 -2,25 z", stroke=color, sw=sw))
    elif name == "tray_down":
        p.append(path("M14,42 v6 a4,4 0 0 0 4,4 h36 a4,4 0 0 0 4,-4 v-6",
                      stroke=color, sw=sw))
        p.append(line(36, 14, 36, 40, color, sw))
        p.append(path("M27,31 L36,40 L45,31", stroke=color, sw=sw))
    elif name == "doc_on_doc":
        p.append(rrect(24, 16, 28, 38, 4, fill=C_WIN, stroke=color, sw=sw))
        p.append(rrect(14, 24, 28, 38, 4, fill=C_WIN, stroke=color, sw=sw))
        for yy in (34, 41, 48):
            p.append(line(21, yy, 35, yy, color, sw * 0.8))
    elif name == "square_stack":
        p.append(rrect(26, 16, 30, 24, 4, stroke=color, sw=sw, opacity=0.55))
        p.append(rrect(20, 22, 30, 24, 4, stroke=color, sw=sw, opacity=0.78))
        p.append(rrect(14, 28, 30, 24, 4, fill=C_WIN, stroke=color, sw=sw))
    elif name == "warning_tri":
        p.append(path("M36,12 L64,56 a4,4 0 0 1 -3,6 H11 a4,4 0 0 1 -3,-6 Z",
                      stroke=color, sw=sw))
        p.append(line(36, 30, 36, 46, color, sw))
        p.append(circle(36, 53, 1.7, fill=color))
    elif name == "xmark_circle":
        p.append(circle(36, 38, 24, stroke=color, sw=sw))
        p.append(line(27, 29, 45, 47, color, sw))
        p.append(line(45, 29, 27, 47, color, sw))
    elif name == "terminal":
        p.append(rrect(8, 18, 56, 38, 6, stroke=color, sw=sw))
        p.append(line(8, 28, 64, 28, color, sw * 0.8))
        p.append(path("M18,38 L24,43 L18,48", stroke=color, sw=sw))
        p.append(line(28, 48, 40, 48, color, sw))
    elif name == "spinner":
        import math
        for i in range(12):
            a = math.radians(i * 30)
            op = 0.18 + 0.82 * (i / 11)
            x1 = 36 + 12 * math.cos(a)
            y1 = 36 + 12 * math.sin(a)
            x2 = 36 + 22 * math.cos(a)
            y2 = 36 + 22 * math.sin(a)
            p.append(line(x1, y1, x2, y2, color, 3.4, opacity=op))
    elif name == "ring":   # determinate progress ~45%
        p.append(circle(36, 36, 22, stroke="#D8D8DC", sw=4))
        p.append(path("M36,14 a22,22 0 0 1 19,33", stroke=C_ACCENT, sw=4))
    elif name == "fish":   # bristlenose app-icon motif (white on accent)
        p.append(path("M20,36 q14,-15 34,0 q-14,15 -34,0 Z", fill="#FFFFFF"))
        p.append(path("M52,36 l9,-7 v14 Z", fill="#FFFFFF"))
        p.append(circle(30, 33, 2.2, fill=C_ACCENT))
        p.append(line(20, 38, 12, 44, "#FFFFFF", 2))
        p.append(line(20, 40, 12, 48, "#FFFFFF", 2))
    return _g(cx, cy, "".join(p), s)


# ── window chrome ───────────────────────────────────────────────────────────
def chrome(tabs_dim=False, active_tab=0):
    o = []
    # window shadow + body
    o.append(f'<rect x="{WX}" y="{WY}" width="{W}" height="{H}" rx="12" '
             f'fill="{C_WIN}" filter="url(#winshadow)"/>')
    # sidebar (full height)
    o.append(f'<clipPath id="winclip"><rect x="{WX}" y="{WY}" width="{W}" height="{H}" rx="12"/></clipPath>')
    o.append('<g clip-path="url(#winclip)">')
    o.append(rrect(SBX, WY, SB, H, 0, fill=C_SIDEBAR))
    o.append(rrect(DX, WY, DW, TB, 0, fill=C_TOOLBAR))
    o.append(line(DX, WY + TB, WX + W, WY + TB, C_HAIR, 1))     # toolbar hairline (detail only)
    o.append(line(DX, WY, DX, WY + H, C_HAIR, 1))               # sidebar divider
    o.append('</g>')
    # traffic lights
    for i, col in enumerate((C_RED, C_ORANGE, C_GREEN)):
        o.append(circle(WX + 22 + i * 20, WY + 22, 6, fill=col))
    # back / forward
    bx = DX + 22
    o.append(path(f"M{bx+4},{WY+20} L{bx-2},{WY+26} L{bx+4},{WY+32}", stroke=C_SEC, sw=2))
    o.append(path(f"M{bx+20},{WY+20} L{bx+26},{WY+26} L{bx+20},{WY+32}", stroke=C_TERT, sw=2))
    # segmented tab control (centred over detail)
    tabs = ["Project", "Sessions", "Quotes", "Codebook", "Analysis"]
    seg_w, seg_h = 360, 26
    seg_x = DX + (DW - seg_w) / 2
    seg_y = WY + 13
    tdim = 0.4 if tabs_dim else 1
    o.append(rrect(seg_x, seg_y, seg_w, seg_h, 7, fill="#E4E4E8", opacity=tdim))
    tw = seg_w / len(tabs)
    for i, t in enumerate(tabs):
        if not tabs_dim and i == active_tab:
            o.append(rrect(seg_x + i * tw + 2, seg_y + 2, tw - 4, seg_h - 4, 6,
                           fill=C_WIN, stroke="#00000010", sw=1))
        col = C_TEXT if (not tabs_dim and i == active_tab) else C_SEC
        o.append(text(seg_x + i * tw + tw / 2, seg_y + 17, t, size=12,
                      fill=col, weight=600 if i == active_tab else 500, opacity=tdim))
    # trailing: search + share
    sx = WX + W - 70
    o.append(circle(sx, WY + 24, 7, stroke=C_SEC, sw=2))
    o.append(line(sx + 5, WY + 29, sx + 9, WY + 33, C_SEC, 2))
    o.append(path(f"M{sx+26},{WY+18} v14 M{sx+20},{WY+24} L{sx+26},{WY+18} L{sx+32},{WY+24}",
                  stroke=C_SEC, sw=2))
    return "".join(o)


def sidebar(rows):
    """rows: list of dicts {name, sub, sel, trail, dim, tint, sub_glyph}."""
    o = [text(SBX + 18, WY + 86, "Projects", size=11, fill=C_SEC, weight=600,
              anchor="start", ls="0.4")]
    y = WY + 100
    rh = 50
    for r in rows:
        sel = r.get("sel")
        dim = 0.45 if r.get("dim") else 1
        cy = y + rh / 2
        if sel:
            o.append(rrect(SBX + 8, y + 4, SB - 16, rh - 8, 7, fill=C_ACCENT))
        nm_col = "#FFFFFF" if sel else C_TEXT
        sub_col = "#FFFFFFCC" if sel else C_SEC
        # project icon chip
        tint = r.get("tint", "#C7C7CC")
        ic_fill = "#FFFFFF33" if sel else tint
        o.append(f'<g opacity="{dim}">')
        o.append(rrect(SBX + 18, cy - 11, 22, 22, 6, fill=ic_fill))
        o.append(glyph("doc_on_doc", SBX + 29, cy, color=("#FFFFFF" if sel else "#FFFFFF"),
                       sw=1.6, s=22) if False else "")
        # tiny doc line motif inside chip
        o.append(line(SBX + 23, cy - 3, SBX + 35, cy - 3, "#FFFFFF" if sel else "#8A8A8E", 1.4))
        o.append(line(SBX + 23, cy + 1, SBX + 35, cy + 1, "#FFFFFF" if sel else "#A8A8AC", 1.4))
        o.append(line(SBX + 23, cy + 5, SBX + 31, cy + 5, "#FFFFFFAA" if sel else "#C2C2C6", 1.4))
        o.append('</g>')
        # name
        o.append(text(SBX + 50, cy - 2, r["name"], size=13, fill=nm_col,
                      weight=600, anchor="start", opacity=dim))
        # subtitle (optional leading glyph char)
        sg = r.get("sub_glyph", "")
        sub = (sg + " " if sg else "") + r.get("sub", "")
        if sub.strip():
            o.append(text(SBX + 50, cy + 13, sub, size=11, fill=sub_col,
                          weight=400, anchor="start", opacity=dim))
        # trailing slot
        tr = r.get("trail")
        tx = SBX + SB - 26
        if tr == "spinner":
            o.append(glyph("spinner", tx, cy, color=(C_WIN if sel else C_SEC), s=20))
        elif tr == "ring":
            o.append(circle(tx, cy, 9, stroke=("#FFFFFF55" if sel else "#D8D8DC"), sw=2.6))
            o.append(path(f"M{tx},{cy-9} a9,9 0 0 1 8,13",
                          stroke=(C_WIN if sel else C_ACCENT), sw=2.6))
        elif tr == "cloud":
            o.append(glyph("cloud", tx, cy, color=(C_WIN if sel else C_CLOUD), sw=2, s=22))
        elif tr == "fail":
            o.append(circle(tx, cy, 8, fill=(C_WIN if sel else C_RED)))
            o.append(line(tx - 3, cy - 3, tx + 3, cy + 3, (C_RED if sel else C_WIN), 2))
            o.append(line(tx + 3, cy - 3, tx - 3, cy + 3, (C_RED if sel else C_WIN), 2))
        elif tr == "warn":
            o.append(glyph("warning_tri", tx, cy, color=(C_WIN if sel else C_ORANGE), sw=2, s=20))
        elif tr == "drive":
            o.append(glyph("drive_warning", tx, cy, color=(C_WIN if sel else C_SEC), sw=1.8, s=22))
        y += rh
    return "".join(o)


# ── detail renderers ────────────────────────────────────────────────────────
def state_pane(g_name, headline, body, button=None, tone=C_TERT, sub2=None):
    o = []
    o.append(glyph(g_name, DCX, DCY - 56, color=tone, s=80))
    o.append(text(DCX, DCY + 8, headline, size=19, fill=C_TEXT, weight=600))
    if body:
        o.append(text(DCX, DCY + 34, body, size=14, fill=C_SEC))
    if sub2:
        o.append(text(DCX, DCY + 54, sub2, size=13, fill=C_TERT))
    if button:
        bw = 12 + len(button) * 8.2
        bx = DCX - bw / 2
        by = DCY + 70
        o.append(rrect(bx, by, bw, 30, 7, fill=C_ACCENT))
        o.append(text(DCX, by + 20, button, size=13, fill="#FFFFFF", weight=600))
    return "".join(o)


def boot_pane(mode, headline, body, button=None):
    o = []
    if mode == "spinner":
        o.append(glyph("spinner", DCX, DCY - 50, color=C_SEC, s=64))
        o.append(text(DCX, DCY + 16, headline, size=18, fill=C_TEXT, weight=600))
        o.append(text(DCX, DCY + 40, body, size=13, fill=C_SEC))
    else:  # failed
        o.append(glyph("warning_tri", DCX, DCY - 56, color=C_ORANGE, s=72))
        o.append(text(DCX, DCY + 8, headline, size=18, fill=C_TEXT, weight=600))
        o.append(text(DCX, DCY + 32, body, size=13, fill=C_SEC))
        if button:
            o.append(rrect(DCX - 92, DCY + 56, 84, 30, 7, fill=C_ACCENT))
            o.append(text(DCX - 50, DCY + 76, button, size=13, fill="#FFFFFF", weight=600))
            o.append(rrect(DCX + 8, DCY + 56, 110, 30, 7, fill="#EAEAEC"))
            o.append(text(DCX + 63, DCY + 76, "Show details", size=13, fill=C_TEXT, weight=500))
    return "".join(o)


def status_pane(tone, kind_label, headline, body, mono=False, details=False):
    col = {"info": C_SEC, "warning": C_ORANGE, "error": C_RED}[tone]
    g = {"info": "terminal", "warning": "warning_tri", "error": "xmark_circle"}[tone]
    o = []
    o.append(glyph(g, DCX, DCY - 58, color=col, s=74))
    o.append(text(DCX, DCY + 6, headline, size=19, fill=C_TEXT, weight=600))
    if body:
        fam = MONO if mono else FONT
        o.append(f'<text x="{DCX}" y="{DCY+32}" font-family="{fam}" font-size="13" '
                 f'fill="{C_SEC}" text-anchor="middle">{esc(body)}</text>')
    if details:
        dyy = DCY + 52
        o.append(rrect(DCX - 200, dyy, 400, 56, 8, fill=C_CARD, stroke=C_HAIR, sw=1))
        o.append(text(DCX - 186, dyy + 20, "▸ Cause & recent log", size=12, fill=C_SEC,
                      weight=600, anchor="start"))
        o.append(text(DCX - 186, dyy + 40, "category · stage · provider · log tail",
                      size=11, fill=C_TERT, anchor="start", family=MONO))
    return "".join(o)


def launcher_pane():
    o = []
    # app icon
    o.append(rrect(DCX - 34, DY + 56, 68, 68, 16, fill="url(#appgrad)"))
    o.append(glyph("fish", DCX, DY + 90, s=68))
    o.append(text(DCX, DY + 156, "Welcome to Bristlenose", size=22, fill=C_TEXT, weight=700))
    o.append(text(DCX, DY + 182, "Turn a folder of interviews into a report you can share — on your laptop, nothing uploaded.",
                  size=13, fill=C_SEC))
    # two cards
    cw, ch = 188, 96
    gap = 20
    cx0 = DCX - cw - gap / 2
    cx1 = DCX + gap / 2
    cy0 = DY + 210
    o.append(rrect(cx0, cy0, cw, ch, 12, fill=C_CARD, stroke=C_ACCENT, sw=1.5))
    o.append(circle(cx0 + cw / 2, cy0 + 36, 16, stroke=C_ACCENT, sw=2))
    o.append(line(cx0 + cw / 2 - 7, cy0 + 36, cx0 + cw / 2 + 7, cy0 + 36, C_ACCENT, 2))
    o.append(line(cx0 + cw / 2, cy0 + 29, cx0 + cw / 2, cy0 + 43, C_ACCENT, 2))
    o.append(text(cx0 + cw / 2, cy0 + 76, "New Project", size=14, fill=C_TEXT, weight=600))
    o.append(rrect(cx1, cy0, cw, ch, 12, fill=C_CARD, stroke=C_TERT, sw=1.5, dash="5 4"))
    o.append(glyph("tray_down", cx1 + cw / 2, cy0 + 34, color=C_SEC, s=44))
    o.append(text(cx1 + cw / 2, cy0 + 76, "Drop a folder", size=14, fill=C_TEXT, weight=600))
    # AI & privacy link
    o.append(text(DCX, cy0 + ch + 34, "Review AI & privacy settings…", size=13, fill=C_ACCENT, weight=500))
    return "".join(o)


def report_pane(tab="dashboard"):
    o = []
    pad = 28
    x0 = DX + pad
    y0 = DY + 24
    if tab == "dashboard":
        # stat cards row
        labels = [("142", "quotes"), ("8", "sessions"), ("11", "themes"), ("63%", "coverage")]
        cw = (DW - 2 * pad - 3 * 14) / 4
        for i, (n, lab) in enumerate(labels):
            cx = x0 + i * (cw + 14)
            o.append(rrect(cx, y0, cw, 78, 10, fill=C_CARD, stroke=C_HAIR, sw=1))
            o.append(text(cx + cw / 2, y0 + 38, n, size=26, fill=C_TEXT, weight=700))
            o.append(text(cx + cw / 2, y0 + 60, lab, size=12, fill=C_SEC))
        # featured + lists
        y1 = y0 + 100
        o.append(text(x0, y1, "Featured quotes", size=14, fill=C_TEXT, weight=700, anchor="start"))
        for i in range(3):
            qy = y1 + 16 + i * 64
            o.append(rrect(x0, qy, DW - 2 * pad, 54, 9, fill=C_WIN, stroke=C_HAIR, sw=1))
            o.append(circle(x0 + 18, qy + 27, 5, fill=[C_RED, C_GREEN, C_ORANGE][i]))
            for k, ww in enumerate((0.82, 0.56)):
                o.append(rrect(x0 + 34, qy + 14 + k * 16, (DW - 2 * pad - 80) * ww, 8, 4,
                               fill="#E9E9ED"))
            o.append(rrect(x0 + DW - 2 * pad - 70, qy + 19, 52, 16, 8, fill=C_CHIP))
    else:  # quotes
        # left section nav
        o.append(rrect(x0, y0, 150, DH - 60, 10, fill=C_CARD, stroke=C_HAIR, sw=1))
        for i in range(5):
            o.append(rrect(x0 + 14, y0 + 16 + i * 30, 120, 12, 4,
                           fill=C_ACCENT if i == 0 else "#E2E2E6"))
        # quote cards grid
        gx = x0 + 168
        gw = DW - pad - 168 - pad
        col_w = (gw - 14) / 2
        for i in range(6):
            r, c = divmod(i, 2)
            qx = gx + c * (col_w + 14)
            qy = y0 + r * 120
            o.append(rrect(qx, qy, col_w, 106, 10, fill=C_WIN, stroke=C_HAIR, sw=1))
            o.append(circle(qx + 16, qy + 18, 5, fill=[C_RED, C_GREEN, C_ORANGE, C_ACCENT, C_RED, C_GREEN][i]))
            o.append(rrect(qx + 28, qy + 13, 70, 9, 4, fill="#ECECEF"))
            for k, ww in enumerate((0.9, 0.78, 0.5)):
                o.append(rrect(qx + 14, qy + 36 + k * 15, (col_w - 28) * ww, 8, 4, fill="#EAEAEE"))
            o.append(rrect(qx + 14, qy + 84, 48, 14, 7, fill=C_CHIP))
            o.append(rrect(qx + 68, qy + 84, 40, 14, 7, fill=C_CHIP))
    return "".join(o)


def gap_overlay(note, lines=None):
    """Dashed red frame + banner across the detail pane, marking an absent design."""
    o = [rrect(DX + 8, DY + 8, DW - 16, DH - 16, 10, stroke=C_RED, sw=2, dash="8 6", opacity=0.9)]
    bh = 26 + (len(lines) * 16 if lines else 0)
    o.append(rrect(DX + 8, DY + 8, DW - 16, bh, 0, fill="#FFFFFFEE"))
    o.append(rrect(DX + 8, DY + 8, 5, bh, 0, fill=C_RED))
    o.append(text(DX + 22, DY + 27, note, size=13, fill="#B3261E", weight=700, anchor="start"))
    if lines:
        for i, ln in enumerate(lines):
            o.append(text(DX + 22, DY + 44 + i * 16, ln, size=11.5, fill="#7A1B16",
                          anchor="start"))
    return "".join(o)


def popover(rows_y_index, header, items):
    """Diagnostic popover anchored to a sidebar row (the native failure surface)."""
    py = WY + 100 + rows_y_index * 50 + 6
    px = SBX + SB - 6
    pw, ph = 232, 40 + len(items) * 22
    o = ['<g filter="url(#popshadow)">']
    o.append(path(f"M{px-6},{py+24} l-8,6 l8,6 Z", fill=C_WIN))
    o.append(rrect(px, py, pw, ph, 10, fill=C_WIN, stroke=C_HAIR, sw=1))
    o.append('</g>')
    o.append(text(px + 14, py + 24, header, size=13, fill=C_TEXT, weight=700, anchor="start"))
    for i, (g, t) in enumerate(items):
        iy = py + 44 + i * 22
        col = {"fail": C_RED, "skip": C_CLOUD}[g]
        o.append(circle(px + 18, iy - 4, 5, fill=col))
        o.append(text(px + 32, iy, t, size=11.5, fill=C_SEC, anchor="start", family=MONO))
    return "".join(o)


# ── frame assembly ──────────────────────────────────────────────────────────
def caption(fid, title, verdict):
    bg, fg, label = VERDICT[verdict]
    o = [text(WX, CAP_Y + 18, fid, size=15, fill=C_TEXT, weight=700, anchor="start"),
         text(WX + 14 + len(fid) * 10, CAP_Y + 18, "· " + title, size=14, fill=C_SEC,
              anchor="start", weight=500)]
    # verdict chip on the right
    cw = 24 + len(label) * 7.2
    o.append(rrect(WX + W - cw, CAP_Y + 2, cw, 24, 12, fill=bg))
    o.append(text(WX + W - cw / 2, CAP_Y + 18, label, size=12, fill=fg, weight=700))
    return "".join(o)


DEFS = '''<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0" stop-color="#F2F3F5"/><stop offset="1" stop-color="#E8EAEE"/>
 </linearGradient>
 <linearGradient id="appgrad" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0" stop-color="#3DA0FF"/><stop offset="1" stop-color="#0A6CF0"/>
 </linearGradient>
 <filter id="winshadow" x="-20%" y="-20%" width="140%" height="140%">
   <feDropShadow dx="0" dy="8" stdDeviation="16" flood-color="#000000" flood-opacity="0.16"/>
 </filter>
 <filter id="popshadow" x="-40%" y="-40%" width="180%" height="180%">
   <feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#000000" flood-opacity="0.22"/>
 </filter>
</defs>'''


def frame(fid, title, verdict, detail_svg, rows, tabs_dim=True, active_tab=0, extra=""):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVGSQ} {SVGSQ}" '
        f'width="{SVGSQ}" height="{SVGSQ}" font-family="{FONT}">',
        DEFS,
        f'<rect x="0" y="0" width="{SVGSQ}" height="{SVGSQ}" fill="url(#bg)"/>',
        f'<g transform="translate(0,{VOFF:.0f})">',
        chrome(tabs_dim=tabs_dim, active_tab=active_tab),
        f'<g clip-path="url(#winclip)">{sidebar(rows)}{detail_svg}</g>',
        extra,
        caption(fid, title, verdict),
        '</g>',
        '</svg>',
    ]
    return "".join(parts)


# common sidebar fillers
def rows_with(active, extra_rows=None):
    base = [
        {"name": "Ikea Kitchen Study", "sub": "8 sessions", "tint": "#FF9F5A"},
        {"name": "Onboarding v3", "sub": "5 sessions", "tint": "#5AC8FA"},
        {"name": "Pricing Interviews", "sub": "12 sessions", "tint": "#AF8CFF"},
    ]
    if extra_rows:
        base = extra_rows
    for i, r in enumerate(base):
        r["sel"] = (i == active)
    return base


# ── the catalogue ───────────────────────────────────────────────────────────
def build():
    frames = []

    # —— StatePane family (native) ——
    r = rows_with(0)
    r[0].update(sub="Samsung T7 · missing", trail="drive", dim=True)
    frames.append(("N01-unavailable-volume", "Unavailable — unmounted volume", "designed",
                   state_pane("drive_warning", "Project Unavailable",
                              "Samsung T7", tone=C_SEC,
                              sub2="Connect the drive to access this project."), r))

    r = rows_with(0)

    r[0].update(sub="Missing", trail="warn", dim=True)
    frames.append(("N02-unavailable-moved", "Unavailable — moved / missing", "designed",
                   state_pane("folder_question", "Project Moved or Deleted",
                              "The project folder couldn’t be found. It may have been moved or deleted.",
                              button="Locate…", tone=C_SEC), r))

    r = rows_with(0)

    r[0].update(sub="In iCloud", trail="cloud")
    frames.append(("N03-unavailable-cloud", "Unavailable — in iCloud", "designed",
                   state_pane("cloud", "In iCloud",
                              "Connect the drive to access this project.",
                              tone=C_CLOUD), r))

    r = rows_with(0)

    r[0].update(name="Untitled Project", sub="")
    frames.append(("N04-empty-path", "Empty project — drag interviews", "designed",
                   state_pane("tray_down", "Drag Interviews Here",
                              "Add interview recordings or transcripts to get started.", tone=C_TERT), r))

    r = rows_with(0)

    r[0].update(name="3 clips", sub="")
    frames.append(("N05-subset-files", "File-subset project (can’t analyse)", "thin",
                   state_pane("doc_on_doc", "Bristlenose analyses folders",
                              "This project was created from individual files, so it can’t be analysed.",
                              tone=C_SEC, sub2="interview-01.mov · interview-02.mov · notes.txt"), r))

    r = rows_with(-1)
    for rr in r:
        rr["sel"] = False
    # multi-select: highlight two rows
    r[0]["sel"] = True
    r[1]["sel"] = True
    frames.append(("N10-multi-select", "Multiple projects selected", "thin",
                   state_pane("square_stack", "2 items selected",
                              "Select a single project to view its report.", tone=C_TERT), r))

    r = rows_with(-1)
    frames.append(("N12-no-selection", "No selection (projects exist)", "thin",
                   state_pane("square_stack", "No Project Selected",
                              "Select a project from the sidebar.", button="New Project", tone=C_TERT), r))

    # —— launcher ——
    frames.append(("N11-welcome-firstrun", "Welcome / first run (zero projects)", "designed",
                   launcher_pane(), []))

    # —— boot family ——
    r = rows_with(0)
    frames.append(("N06-boot-starting", "Boot — starting sidecar", "designed",
                   boot_pane("spinner", "Starting Bristlenose…", "Sensemaking for User Research"), r))

    r = rows_with(0)
    frames.append(("N07-boot-loading-report", "Boot — loading report (2s-timeout handoff)", "thin",
                   boot_pane("spinner", "Loading report…", "Sensemaking for User Research"), r))

    r = rows_with(0)
    frames.append(("N08-serve-failed", "Boot — server failed to start", "designed",
                   boot_pane("failed", "Couldn’t start Bristlenose",
                             "The server exited before it was ready.", button="Retry"), r))

    # —— report (web, exists) ——
    r = rows_with(0)
    r[0].update(sub="Analysed 2 days ago")
    frames.append(("N09-report-dashboard", "Report — Project / Dashboard tab", "exists",
                   report_pane("dashboard"), r, False, 0))
    r = rows_with(0)
    r[0].update(sub="Analysed 2 days ago")
    frames.append(("W10-report-quotes", "Report — Quotes tab", "exists",
                   report_pane("quotes"), r, False, 2))

    # —— web status pages ——
    r = rows_with(0)
    r[0].update(name="Untitled Project", sub="Ready to analyse")
    frames.append(("W01-status-no-run-desktop", "Status — no run yet (desktop)", "designed",
                   status_pane("info", "INFO", "No interviews to analyse yet.",
                               "Drop a folder of interviews here to start."), r, False, 0))

    r = rows_with(0)
    frames.append(("W02-status-no-run-cli", "Status — no run yet (CLI build)", "designed",
                   status_pane("info", "INFO", "Nothing to see here, yet.",
                               "$ bristlenose run interviews/", mono=True), r, False, 0))

    r = rows_with(0)

    r[0].update(sub="Run cancelled", trail="warn")
    frames.append(("W03-status-cancelled", "Status — last run cancelled", "designed",
                   status_pane("warning", "WARNING", "Last run was cancelled.",
                               "Re-run when ready.", details=True), r, False, 0))

    r = rows_with(0)

    r[0].update(sub="Run failed", trail="fail")
    frames.append(("W04-status-failed", "Status — last run failed", "designed",
                   status_pane("error", "ERROR", "Last run failed.",
                               "The AI provider rejected the request (model not found).",
                               details=True), r, False, 0))

    r = rows_with(0)
    frames.append(("W05-build-incomplete", "Status — build incomplete (fail-loud 500)", "designed",
                   status_pane("error", "ERROR", "Build incomplete",
                               "The Bristlenose React bundle is missing from this build.",
                               details=False), r, False, 0))

    r = rows_with(0)
    frames.append(("W06-server-500", "Status — unhandled 500", "thin",
                   status_pane("error", "ERROR", "Internal Server Error", "", ), r, False, 0))

    # —— GAPS ——
    r = rows_with(0)
    r[0].update(sub="Transcribing · 2 of 3 · <1 min left", trail="ring")
    det = status_pane("info", "INFO", "No interviews to analyse yet.",
                      "Drop a folder of interviews here to start.")
    det += gap_overlay("GAP · No “analysing” detail pane",
                       ["Sidebar says “Transcribing · 2 of 3”, but the pane shows the no-run status page.",
                        "All run progress lives in the sidebar row; the main area contradicts it."])
    frames.append(("GAP-analysing", "Run in progress — the missing pane", "gap",
                   det, r, False, 0))

    r = rows_with(0)

    r[0].update(sub="Run failed", trail="fail")
    det = status_pane("error", "ERROR", "Last run failed.",
                      "The AI provider rejected the request (model not found).", details=True)
    det += popover(0, "Run failed", [("fail", "s10 · quote extraction"),
                                     ("fail", "provider says: not_found"),
                                     ("skip", "s11 · clustering — skipped")])
    det += gap_overlay("GAP · Failure rendered twice, two vocabularies",
                       ["Native diagnostic popover (sidebar) AND web status page (pane) — different copy.",
                        "Pick one owner per post-terminal state for a coherent set."])
    frames.append(("GAP-failed-duplication", "Failure shown in two surfaces", "gap",
                   det, r, False, 0))

    r = rows_with(0)

    r[0].update(sub="Transcribed", trail="warn")
    det = report_pane("dashboard")
    det += gap_overlay("GAP · queued / stopped / partial have no pane",
                       ["queued → stale report · stopped → stale report · partial → half report + popover.",
                        "No “resume”, “continue to analysis”, or “partial — N sessions failed” surface here."])
    frames.append(("GAP-queued-stopped-partial", "Queued / stopped / partial states", "gap",
                   det, r, False, 0))

    return frames


def main():
    out = Path(__file__).parent / "svg"
    out.mkdir(exist_ok=True)
    frames = build()
    for fid, title, verdict, detail, rows, *rest in frames:
        tabs_dim = rest[0] if len(rest) > 0 else True
        active = rest[1] if len(rest) > 1 else 0
        svg = frame(fid, title, verdict, detail, rows, tabs_dim=tabs_dim, active_tab=active)
        (out / f"{fid}.svg").write_text(svg, encoding="utf-8")
    print(f"wrote {len(frames)} SVGs to {out}")
    for fid, *_ in frames:
        print(" ", fid)


if __name__ == "__main__":
    main()
