"""Generate docs/mockups/webview-context-menu-proposal.html.

Inlines the shipped CSS (whole files, or rules located by a line that STARTS
with the selector), each block headed with its path and line range, so the
report pixels are the design system's and can be diffed against the tree.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose/theme"
OUT = ROOT / "docs/mockups/webview-context-menu-proposal.html"

blocks = []


def whole(rel):
    p = THEME / rel
    text = p.read_text()
    n = text.count("\n") + 1
    blocks.append(f"/* ════ bristlenose/theme/{rel} — lines 1–{n} ════ */\n{text}")


def rules(rel, starts, count=1):
    """`count` consecutive top-level rules, from the first line starting with `starts`."""
    p = THEME / rel
    lines = p.read_text().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith(starts))
    j, depth, seen = i, 0, 0
    while True:
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0 and "}" in lines[j]:
            seen += 1
            if seen == count:
                break
        j += 1
    blocks.append(
        f"/* ════ bristlenose/theme/{rel} — lines {i + 1}–{j + 1} ════ */\n"
        + "\n".join(lines[i : j + 1])
    )


for f in [
    "tokens.css", "tokens-typography.css", "tokens-desktop.css",
    "colors/palette-default.css", "colors/palette-edo.css",
    "atoms/badge.css", "atoms/timecode.css", "atoms/section-heading.css",
    "atoms/thumbnail.css", "molecules/person-badge.css", "molecules/badge-row.css",
    "organisms/blockquote.css", "organisms/sessions-grid.css", "templates/transcript.css",
]:
    whole(f)
rules("organisms/signals.css", ".signal-card-location-link {", 3)
rules("organisms/signals.css", ".signals-codebook-heading {", 1)
rules("organisms/codebook-panel.css", ".preview-author {", 6)
rules("organisms/sidebar.css", ".toc-link {", 4)

SHIPPED_CSS = "\n\n".join(blocks)

# ── WebKit's own items, as measured in the probe (docs/design-webview-context-menu.md §1) ──
LINK = ["Open Link", "Open Link in New Window", "Download Linked File", "Copy Link", "-", "Share…"]
IMAGE = ["Open Image in New Window", "Download Image", "Copy Image", "Copy Subject", "Look Up", "-", "Share…"]
VIDEO = ["Open Video in New Window", "Download Video", "Copy Video Address", "-",
         "Hide Controls", "Enter Full Screen", "Enter Picture in Picture"]

# ── Context slices: real component markup, synthetic content ──
def badge(code, name, href=None, hot=False):
    inner = (f'<span class="bn-person-badge"><span class="bn-speaker-badge--split">'
             f'<span class="bn-speaker-badge-code">{code}</span>'
             f'<span class="bn-speaker-badge-name">{name}</span></span></span>')
    if href:
        return f'<a href="{href}" class="speaker-link{" hot" if hot else ""}">{inner}</a>'
    return inner


def tc(label, hot=False):
    return (f'<a class="timecode{" hot" if hot else ""}" href="#t=754">'
            f'<span class="timecode-bracket">[</span>{label}<span class="timecode-bracket">]</span></a>')


def quote_card(hot_badge=False, hot_tc=False):
    return f'''<div class="lens-pad"><h3 class="ctx-h3">Delivery costs</h3>
<blockquote class="quote-card" id="q-p3-754"><div class="quote-row">{tc("12:34", hot_tc)}
<div class="quote-body"><span class="quote-text-wrapper"><span class="smart-quote">“</span><span class="quote-text">I wanted to see the delivery cost before I typed my card number, not after.</span><span class="smart-quote">”</span></span>
<span class="speaker">{badge("p3", "Dana", "/report/sessions/s3#t-754", hot_badge)}</span>
<div class="badges"><span class="badge badge-ai" data-sentiment="frustration">frustration</span></div></div></div></blockquote>
<blockquote class="quote-card" id="q-p5-301"><div class="quote-row">{tc("05:01")}
<div class="quote-body"><span class="quote-text-wrapper"><span class="smart-quote">“</span><span class="quote-text">Free delivery over thirty pounds, fine, but tell me on the basket.</span><span class="smart-quote">”</span></span>
<span class="speaker">{badge("p5", "Sam", "/report/sessions/s5#t-301")}</span></div></div></blockquote></div>'''


THUMB_SVG = ("data:image/svg+xml;utf8," +
             "<svg xmlns='http://www.w3.org/2000/svg' width='96' height='54'>"
             "<rect width='96' height='54' fill='%23cbd5e1'/><rect x='6' y='6' width='40' height='42' rx='3' fill='%2394a3b8'/>"
             "<rect x='52' y='10' width='38' height='6' rx='2' fill='%23e2e8f0'/><rect x='52' y='22' width='30' height='6' rx='2' fill='%23e2e8f0'/></svg>")


def sessions_row(hot_id=False, hot_thumb=False):
    def row(n, sid, code, name, file_, hot_id_, hot_thumb_):
        return f'''<div class="bn-sessions-row" data-session="{sid}" role="row">
<div class="bn-sessions-cell bn-cell-id bn-session-id" role="cell"><a href="/report/sessions/{sid}" class="{"hot" if hot_id_ else ""}">#{n}</a></div>
<div class="bn-sessions-cell bn-cell-thumb" role="cell"><div class="bn-video-thumb"><img class="{"hot" if hot_thumb_ else ""}" src="{THUMB_SVG}" alt=""></div></div>
<div class="bn-sessions-cell bn-cell-speakers bn-session-speakers" role="cell">{badge(code, name)}<br>{badge("m1", "Alex")}</div>
<div class="bn-sessions-cell" role="cell"><span class="muted-s">14 Oct 10:02</span></div>
<div class="bn-sessions-cell" role="cell"><a class="timecode" href="#t=0">{file_}</a></div></div>'''
    return ('<div class="lens-pad"><!-- no .bn-session-table container: its queries would hide the thumbnail at this frame width; drawn at the widest layout of the grid --><div class="bn-sessions-grid ctx-grid" role="table">'
            + row(3, "s3", "p3", "Dana", "dana-checkout.mov", hot_id, hot_thumb)
            + row(4, "s4", "p4", "Lee", "lee-checkout.mov", False, False)
            + "</div></div>")


def transcript(hot=False):
    def seg(t, code, name, text, hot_=False, moderator=False):
        return f'''<div class="transcript-segment{" segment-moderator" if moderator else ""}" id="t-{t}">
<span class="segment-timecode-cell">{tc(f"{t // 60:02d}:{t % 60:02d}", hot_)}</span>
<span class="segment-speaker">{badge(code, name)}</span>
<div class="segment-body">{text}</div></div>'''
    return ('<div class="lens-pad"><div class="transcript-body">'
            + seg(741, "m1", "Alex", "And what were you looking for at that point?", moderator=True)
            + seg(754, "p3", "Dana", "I wanted to see the delivery cost before I typed my card number, not after. That's when I'd normally bail.", hot)
            + seg(779, "m1", "Alex", "So you'd have left there?", moderator=True)
            + "</div></div>")


def signals(hot=False):
    return f'''<div class="lens-pad"><div class="signals-codebook-heading"><a href="#section-delivery-costs" class="signal-card-location-link{" hot" if hot else ""}">Delivery costs</a></div>
<div class="ctx-card"><div class="ctx-card-h">frustration</div><div class="ctx-line"></div><div class="ctx-line s"></div></div>
<div class="signals-codebook-heading"><a href="#section-payment" class="signal-card-location-link">Payment</a></div>
<div class="ctx-card"><div class="ctx-card-h">trust</div><div class="ctx-line"></div></div></div>'''


def codebook_author(hot=False):
    return f'''<div class="lens-pad"><div class="preview-author" style="max-width:320px">
<div class="preview-author-name">Jesse James Garrett</div>
<div class="preview-author-bio">Author of <i>The Elements of User Experience</i>, which divides a product into five planes from strategy to surface.</div>
<div class="preview-author-links"><a class="{"hot" if hot else ""}" href="https://example.com/elements" target="_blank">The book &#x2197;</a><a href="https://example.com/garrett">Website &#x2197;</a></div></div></div>'''


def codebook_nav(hot=False):
    return f'''<div class="lens-pad"><div class="ctx-nav">
<a href="#" class="toc-link codebook-toc-link v2-nav-row active{" hot" if hot else ""}"><span class="codebook-toc-label">Bristlenose UXR</span></a>
<a href="#" class="toc-link codebook-toc-link v2-nav-row"><span class="codebook-toc-label">Garrett — Elements of UX</span></a>
<a href="#" class="toc-link codebook-toc-link v2-nav-row"><span class="codebook-toc-label">Norman — Design of Everyday Things</span></a>
<a href="#" class="toc-link codebook-toc-link v2-nav-row"><span class="codebook-toc-label">Nielsen — Heuristics</span></a></div></div>'''


def screengrab(hot=False):
    return f'''<div class="lens-pad"><div class="ctx-shot{" hot" if hot else ""}"><div class="bar"></div><div class="nav"><b></b><s></s><s></s><s></s></div><div class="hero"></div><div class="row"><div></div><div></div><div></div></div></div>
<div class="ctx-leadcard"><span class="timecode"><span class="timecode-bracket">[</span>12:34<span class="timecode-bracket">]</span></span> “Tell me on the basket.”</div></div>'''


def player(hot=False):
    return f'''<div class="ctx-player"><div class="ctx-video{" hot" if hot else ""}"><div class="ctx-video-pic"></div>
<div class="ctx-controls"><span>&#9654;&#xFE0E;</span><i></i><span class="t">12:34 / 41:07</span></div></div></div>'''


# ── Scenarios ──
S = [
    dict(h="Quotes — speaker badge", w="<code>&lt;a href=&quot;/report/sessions/s3#t-754&quot;&gt;</code>. A click goes to the transcript at 12:34.",
         ctx=quote_card(hot_badge=True), today=LINK, prop=["Open Link in New Window"],
         note="<b>Today</b> Open Link in New Window loads the transcript into the <i>Video Player</i> window, with no toolbar or sidebar, and closes any playing clip. <b>Proposed</b> WebKit's own item, title and position kept, retargeted to a new Bristlenose window: this project, Sessions, transcript s3 at 12:34. Open Link (a full reload), Download (does nothing), Copy Link and Share (a 127.0.0.1 address that dies on restart) are removed."),
    dict(h="Quotes — timecode", w="<code>&lt;a href=&quot;#t=754&quot;&gt;</code>. A click plays the clip; the href carries no session.",
         ctx=quote_card(hot_tc=True), today=LINK, prop=["Open Link in New Window"],
         note="<span class=flag>Decision.</span> Today the new window opens the Quotes lens at the top, since nothing reads <code>#t=</code>. Proposed: the transcript at this moment, which the card knows (session and seconds), not the href. The alternative is to offer nothing here, because a left click <i>plays</i> rather than navigates."),
    dict(h="Sessions — <code>#N</code>", w="<code>&lt;a href=&quot;/report/sessions/s3&quot;&gt;</code>", ctx=sessions_row(hot_id=True),
         today=LINK, prop=["Open Link in New Window"],
         note="Proposed: a new window on transcript s3 at the top. WindowSeed can express the lens today, not the session (doc §4.3)."),
    dict(h="Sessions — thumbnail", w="<code>&lt;img src=&quot;/report/assets/thumbnails/s3.jpg&quot;&gt;</code>; a click opens the player.",
         ctx=sessions_row(hot_thumb=True), today=IMAGE, prop=["Copy Image", "Copy Subject", "Look Up", "-", "Share…"],
         note="<b>Today</b> Open Image in New Window replaces the playing clip with the bare JPEG; Download Image does nothing. <b>Proposed</b> both removed; Copy Image and Share stay. <span class=flag>Decision.</span> Copy Subject and Look Up run Visual Look Up on a participant's recording; whether that reaches Apple's servers was not measured."),
    dict(h="Transcript — timecode", w="<code>&lt;a href=&quot;#t=754&quot;&gt;</code> on <code>/report/sessions/s3</code>.",
         ctx=transcript(hot=True), today=LINK, prop=["Open Link in New Window"],
         note="Proposed: a second window on this transcript at 12:34. Both are known on the page, so this one is exact. Words and paragraphs keep the Mac's text services; this is only the timecode."),
    dict(h="Signals — location heading", w="<code>&lt;a href=&quot;#section-delivery-costs&quot;&gt;</code>, relative to Signals. A click goes to <b>Quotes</b>.",
         ctx=signals(hot=True), today=LINK, prop=["Open Link in New Window"],
         note="<b>Today</b> the player window opens on Signals: the href names the wrong lens. <b>Proposed</b> a new window on Quotes at Delivery costs, where the left click goes. The place comes from the component, not the href (doc §4.2)."),
    dict(h="Codebooks — author link", w="External <code>https://</code> from the codebook's YAML.",
         ctx=codebook_author(hot=True), today=LINK, prop=["Open Link", "Open Link in New Window", "Copy Link", "-", "Share…"],
         note="External links behave as in Safari and open the default browser. Only Download Linked File goes, since it does nothing."),
    dict(h="Codebooks — navigator row", w="<code>&lt;a href=&quot;#&quot;&gt;</code>, a JS action, not a place.",
         ctx=codebook_nav(hot=True), today=LINK, prop=None,
         note="<b>Today</b> the player window opens on this lens. <b>Proposed</b> every link item removed; with nothing left, AppKit shows no menu. <span class=flag>Decision.</span> Offer nothing, or fall back to the page items (Back, Reload) so a right-click always answers. Same for the hidden-quotes counter and the Sessions header's Reveal link."),
    dict(h="Screens — screengrab", w="<code>&lt;img src=&quot;data:image/jpeg…&quot;&gt;</code>", ctx=screengrab(hot=True),
         today=IMAGE, prop=["Copy Image", "Copy Subject", "Look Up", "-", "Share…"],
         note="Today Open Image in New Window does nothing (the <code>data:</code> scheme is refused) and Download does nothing. On a custom board the Screens session puts <i>Tidy</i> and a separator above these items; drawn here on an automatic board."),
    dict(h="Popout player — video", w="<code>&lt;video src=&quot;/media/…&quot;&gt;</code> in <code>player.html</code>.",
         ctx=player(hot=True), today=VIDEO, prop=["Hide Controls", "Enter Full Screen", "Enter Picture in Picture"],
         note="WebKit's media items are its usual set, <b>not measured</b> in the probe. Open Video in New Window does nothing (the popout has no UI delegate), Download goes the silent way, Copy Video Address is a loopback URL: all removed. The viewing controls stay."),
]


def menu_html(items, extra=""):
    if items is None:
        return '<div class="none" data-menu>No menu</div>'
    out = []
    focus = next((it for it in items if "in New Window" in it), items[0])
    for it in items:
        if it == "-":
            out.append("<hr>")
        else:
            cls = " class=\"hl\"" if it == focus else ""
            out.append(f"<div{cls}>{it}</div>")
    return f'<div class="mac" data-menu{extra}>{"".join(out)}</div>'


def stage(ctx, items, label):
    return (f'<div><div class="frame"><div class="chrome"><i></i><i></i><i></i><span>{label}</span></div>'
            f'<div class="stage">{ctx}{menu_html(items)}</div></div></div>')


rows = []
for n, s in enumerate(S, 1):
    rows.append(f'<div class="scen"><h2><span class="num">{n}</span>{s["h"]}</h2><p>{s["w"]}</p></div>')
    rows.append(stage(s["ctx"], s["today"], "Today — WebKit's default"))
    rows.append(stage(s["ctx"], s["prop"], "Proposed"))
    rows.append(f'<div class="note" style="grid-column: 1 / -1"><span class="lbl">Commentary</span>{s["note"]}</div>')

# ── Outcome: what the window looks like ──
REPORT_PANE = f'''<div class="ctx-mini">{transcript()}</div>'''


def win(title, body, kind):
    return f'''<div class="win {kind}"><div class="win-bar"><i class="r"></i><i class="y"></i><i class="g"></i><span>{title}</span></div>{body}</div>'''


outcome_today = win("Video Player", f'<div class="win-body bare">{REPORT_PANE}</div>', "small")
outcome_prop = win("Checkout study — Sessions", f'''<div class="win-body full"><div class="win-side">
<div class="ws-proj">Checkout study</div><div class="ws-lens">Project</div><div class="ws-lens on">Sessions</div><div class="ws-lens">Quotes</div><div class="ws-lens">Codebooks</div><div class="ws-lens">Signals</div></div>
<div class="win-main"><div class="win-tool"><span>&#x25C0;&#xFE0E; &#x25B6;&#xFE0E;</span><b>Session 3 · Dana</b></div>{REPORT_PANE.replace('id="t-754"', 'id="t-754" data-anchor')}</div></div>''', "large")

PAGE_CSS = r"""
/* ── mockup page chrome (not the product) ── */
:root { --hatch: repeating-linear-gradient(135deg, light-dark(#fafafa, #151515) 0 8px, light-dark(#f2f2f3, #1b1b1d) 8px 16px);
  --pg-font: -apple-system, "SF Pro Text", system-ui, "Inter", sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: light-dark(#f4f4f5, #18181b); color: var(--bn-colour-text); font: 14px/1.5 var(--pg-font); }
main.pg { max-width: 1260px; margin: 0 auto; padding: 24px 16px 64px; }
.pg h1 { font-size: 22px; margin: 0 0 4px; }
.lede { color: var(--bn-colour-muted); margin: 0 0 14px; max-width: 78ch; }
.key { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--bn-colour-muted); margin: 0 0 18px; align-items: center; }
.key span::before { content: ""; display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 6px; vertical-align: -2px; border: 1px solid var(--bn-colour-border); }
.key .k-art::before { background: var(--bn-colour-bg); }
.key .k-com::before { background: var(--hatch); }
.key button { font: 12px var(--pg-font); padding: 3px 10px; border-radius: 6px; border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); color: var(--bn-colour-text); cursor: pointer; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; align-items: start; }
.grid > *, .outcome > * { min-width: 0; }
.colhead { font: 600 12px var(--pg-font); text-transform: uppercase; letter-spacing: .05em; color: var(--bn-colour-muted); }
.scen { grid-column: 1 / -1; display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; margin-top: 10px; }
.scen h2 { font-size: 14px; margin: 0; display: flex; gap: 8px; align-items: baseline; }
.scen .num { font: 600 11px var(--bn-font-mono); color: var(--bn-colour-muted); }
.scen p { margin: 0; font-size: 12.5px; color: var(--bn-colour-muted); }
.scen code, .note code { font: 11.5px var(--bn-font-mono); }
.frame { background: var(--bn-colour-bg); border: 1px solid var(--bn-colour-border); border-radius: 10px; overflow: hidden; }
.chrome { height: 22px; border-bottom: 1px solid var(--bn-colour-border); background: light-dark(#ececec, #2a2a2c); font: 11px var(--pg-font); color: var(--bn-colour-muted); display: flex; align-items: center; padding: 0 10px; gap: 6px; }
.chrome i { width: 8px; height: 8px; border-radius: 50%; background: #c7c9ce; display: block; }
.stage { position: relative; height: 300px; overflow: hidden; font-family: var(--bn-font-body); }
.lens-pad { padding: 14px 18px; }
.note { background: var(--hatch); border-left: 3px solid var(--bn-colour-muted); border-radius: 0 6px 6px 0; padding: 8px 12px; font-size: 12.5px; margin: 0 0 18px; }
.note .lbl { font: 600 10.5px var(--bn-font-mono); text-transform: uppercase; letter-spacing: .06em; color: var(--bn-colour-muted); display: block; margin-bottom: 2px; }
.flag { color: #b45309; font-weight: 600; }

/* ── context stand-ins for surfaces not worth extracting (approximations) ── */
.ctx-h3 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 0 0 var(--bn-space-md); }
.ctx-grid { font-size: var(--bn-text-label); }
.muted-s { color: var(--bn-colour-muted); }
.ctx-card { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); padding: 10px 12px; margin: 8px 0 16px; max-width: 360px; }
.ctx-card-h { font-size: var(--bn-text-caption); color: var(--bn-colour-muted); margin-bottom: 8px; }
.ctx-line { height: 7px; border-radius: 3px; background: var(--bn-colour-border); margin-bottom: 6px; }
.ctx-line.s { width: 60%; }
.ctx-nav { display: flex; flex-direction: column; max-width: 260px; }
.ctx-shot { width: 280px; height: 180px; border: 1px solid var(--bn-colour-border); border-radius: 4px; background: #fff; overflow: hidden; display: inline-block; vertical-align: top; }
.ctx-shot .bar { height: 14px; background: #1f2937; }
.ctx-shot .nav { height: 20px; border-bottom: 1px solid #eee; display: flex; gap: 8px; align-items: center; padding: 0 8px; }
.ctx-shot .nav b { width: 46px; height: 10px; background: #2563eb; border-radius: 2px; }
.ctx-shot .nav s { width: 26px; height: 5px; background: #d1d5db; border-radius: 2px; }
.ctx-shot .hero { margin: 8px; height: 66px; border-radius: 4px; background: linear-gradient(120deg, #d1d5db, #e5e7eb); }
.ctx-shot .row { display: flex; gap: 6px; margin: 0 8px; }
.ctx-shot .row div { flex: 1; height: 44px; border-radius: 3px; background: #eef2f7; }
.ctx-leadcard { display: inline-block; vertical-align: top; margin: 24px 0 0 10px; max-width: 150px; padding: 8px 10px; background: var(--bn-colour-quote-bg); border-radius: 0 6px 6px 0; font-size: var(--bn-text-caption); }
.ctx-player { position: absolute; inset: 0; background: #000; display: flex; align-items: center; justify-content: center; }
.ctx-video { position: relative; width: 100%; height: 100%; }
.ctx-video-pic { position: absolute; inset: 28px 60px 44px; border-radius: 3px; background: linear-gradient(140deg, #4b5563, #9ca3af 60%, #6b7280); }
.ctx-controls { position: absolute; left: 50%; bottom: 10px; transform: translateX(-50%); width: 72%; height: 26px; border-radius: 13px; background: rgba(60,60,60,.7); display: flex; align-items: center; gap: 10px; padding: 0 12px; color: #fff; font: 11px var(--pg-font); }
.ctx-controls i { flex: 1; height: 3px; border-radius: 2px; background: linear-gradient(90deg, #fff 30%, rgba(255,255,255,.35) 30%); }

.ptr { position: absolute; z-index: 6; width: 12px; height: 18px; pointer-events: none; }
.hot-ring { outline: 1.5px solid var(--bn-colour-accent); outline-offset: 2px; border-radius: 3px; }

/* ── macOS 26 context menu (approximation, as in screens-context-menu.html) ── */
.mac { position: absolute; z-index: 5; min-width: 200px; padding: 5px; border-radius: 10px; font: 13px/1 var(--pg-font);
  background: light-dark(rgba(246,246,246,.88), rgba(40,40,42,.88)); backdrop-filter: blur(24px) saturate(1.6); -webkit-backdrop-filter: blur(24px) saturate(1.6);
  box-shadow: 0 0 0 .5px light-dark(rgba(0,0,0,.18), rgba(255,255,255,.18)), 0 10px 30px rgba(0,0,0,.22); color: light-dark(#1d1d1f, #f2f2f2); }
.mac div { height: 22px; display: flex; align-items: center; padding: 0 10px; border-radius: 5px; white-space: nowrap; }
.mac div.hl { background: #007aff; color: #fff; }
.mac hr { border: 0; height: 1px; margin: 5px 10px; background: light-dark(rgba(0,0,0,.12), rgba(255,255,255,.14)); }
.none { position: absolute; z-index: 5; font: 12px var(--pg-font); color: var(--bn-colour-muted); background: var(--bn-colour-bg); border: 1px dashed var(--bn-colour-border); border-radius: 6px; padding: 6px 10px; }

/* ── outcome windows (approximations of the app's chrome) ── */
.outcome { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; align-items: start; margin-top: 8px; }
.ostage { position: relative; height: 380px; background: light-dark(#dfe3ea, #0c0c0e); border: 1px solid var(--bn-colour-border); border-radius: 10px; overflow: hidden; }
.win { position: absolute; background: var(--bn-colour-bg); border-radius: 10px; overflow: hidden; box-shadow: 0 0 0 .5px rgba(0,0,0,.25), 0 14px 40px rgba(0,0,0,.28); }
.win.small { left: 40px; top: 40px; width: 360px; height: 240px; }
.win.large { left: 16px; top: 16px; right: 16px; bottom: 16px; }
.win-bar { height: 28px; display: flex; align-items: center; gap: 7px; padding: 0 10px; background: light-dark(#f3f3f3, #2c2c2e); border-bottom: 1px solid var(--bn-colour-border); font: 600 12px var(--pg-font); }
.win-bar span { margin-left: 8px; }
.win-bar i { width: 11px; height: 11px; border-radius: 50%; display: block; }
.win-bar .r { background: #ff5f57; } .win-bar .y { background: #febc2e; } .win-bar .g { background: #28c840; }
.win-body { position: absolute; top: 28px; left: 0; right: 0; bottom: 0; overflow: hidden; }
.win-body.full { display: flex; }
.win-side { width: 118px; background: light-dark(#ebedf0, #1f1f22); border-right: 1px solid var(--bn-colour-border); padding: 10px 8px; font: 12px var(--pg-font); }
.ws-proj { font-weight: 600; margin-bottom: 8px; }
.ws-lens { padding: 4px 8px; border-radius: 6px; color: var(--bn-colour-muted); }
.ws-lens.on { background: light-dark(rgba(0,0,0,.08), rgba(255,255,255,.1)); color: var(--bn-colour-text); }
.win-main { flex: 1; min-width: 0; position: relative; }
.win-tool { height: 30px; display: flex; gap: 14px; align-items: center; padding: 0 12px; border-bottom: 1px solid var(--bn-colour-border); font: 12px var(--pg-font); color: var(--bn-colour-muted); }
.win-tool b { color: var(--bn-colour-text); font-weight: 600; }
.ctx-mini { transform: scale(.72); transform-origin: top left; width: 139%; }
.win-main [data-anchor] { background: color-mix(in srgb, var(--bn-colour-accent) 10%, transparent); border-radius: 4px; }
.mainwin-ghost { position: absolute; left: 12px; top: 12px; right: 12px; bottom: 12px; border-radius: 10px; background: var(--bn-colour-bg); opacity: .55; box-shadow: 0 0 0 .5px rgba(0,0,0,.2); }

@media (max-width: 900px) { .grid, .outcome { grid-template-columns: 1fr; } .colhead { display: none; } }
"""

SCRIPT = r"""
// Place the pointer on each stage's target and open the menu beside it,
// flipping left or up when the menu would leave the stage.
const PTR = '<svg class="ptr" viewBox="0 0 12 18"><path d="M1 1 L1 15 L4.5 11.5 L7 17 L9 16 L6.5 10.5 L11 10.5 Z" fill="#111" stroke="#fff" stroke-width="1"/></svg>';
function place() {
  document.querySelectorAll(".stage").forEach((st) => {
    st.querySelectorAll(".ptr").forEach((p) => p.remove());
    const hot = st.querySelector(".hot"); const m = st.querySelector("[data-menu]");
    if (!hot || !m) return;
    hot.classList.add("hot-ring");
    const s = st.getBoundingClientRect(), r = hot.getBoundingClientRect();
    const big = r.width > 200;
    const x = Math.min(r.left - s.left + (big ? r.width * 0.3 : Math.min(r.width * 0.6, 40)), s.width - 20);
    const y = r.top - s.top + (big ? r.height * 0.35 : Math.min(r.height * 0.6, 14));
    st.insertAdjacentHTML("beforeend", PTR);
    const p = st.lastElementChild; p.style.left = x + "px"; p.style.top = y + "px";
    let mx = x + 4, my = y + 4;
    if (mx + m.offsetWidth > s.width - 6) mx = Math.max(6, x - m.offsetWidth - 2);
    if (my + m.offsetHeight > s.height - 6) my = Math.max(6, s.height - m.offsetHeight - 6);
    m.style.left = mx + "px"; m.style.top = my + "px";
  });
}
addEventListener("load", place); addEventListener("resize", place);
document.getElementById("pal").addEventListener("click", (e) => {
  const h = document.documentElement, edo = h.dataset.colorTheme === "edo";
  h.dataset.colorTheme = edo ? "default" : "edo"; e.target.textContent = edo ? "Palette: default" : "Palette: Edo"; place();
});
document.getElementById("scheme").addEventListener("click", (e) => {
  const h = document.documentElement, cur = h.style.colorScheme;
  const next = cur === "dark" ? "light" : cur === "light" ? "light dark" : "dark";
  h.style.colorScheme = next; h.dataset.theme = next === "light dark" ? "" : next;
  e.target.textContent = "Appearance: " + (next === "light dark" ? "system" : next); place();
});
"""

HTML = f"""<!doctype html>
<html lang="en" data-color-theme="default" data-platform="desktop" style="color-scheme: light dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report right-click menus</title>
<!--
  THE REPORT'S RIGHT-CLICK MENU — TODAY vs PROPOSED  (15 Oct 2026)

  Companion to docs/design-webview-context-menu.md (the audit) and
  docs/mockups/screens-context-menu.html (Screens' Tidy, same menu drawing).

  Artefact zone: the report slices are the shipped CSS (inlined below, one block
  per file, each headed with its path and line range — regenerate with
  experiments/webview-context-menu/gen_mockup.py rather than hand-edit) and the shipped component markup, with synthetic content. The menus
  are an approximation of the macOS 26 context menu. Their items are WebKit's own
  titles, as measured by experiments/webview-context-menu/probe.swift on macOS
  27.0, except the video menu (not measured). The proposal adds NO new strings:
  every item kept is WebKit's, retargeted or left alone.

  The highlighted row is the item under discussion (the new-window item where there is one), not a recommendation.
-->
<style>
{SHIPPED_CSS}

{PAGE_CSS}
</style>
</head>
<body>
<main class="pg">
  <h1>The report's right-click menu: today and proposed</h1>
  <p class="lede">Each row is something you can right-click in the Mac app. Today every report link offers WebKit's full link menu, and its <i>Open Link in New Window</i> lands in the video player's window. The proposal keeps that item only where the page knows the place (project, lens and position), opening a real Bristlenose window there, and removes what does nothing or hands out a dead address.</p>
  <div class="key"><span class="k-art">Artefact: shipped CSS and markup, synthetic content; menus approximate macOS 26</span><span class="k-com">Commentary</span><button id="pal" type="button">Palette: default</button><button id="scheme" type="button">Appearance: system</button></div>
  <div class="grid">
    
    {"".join(rows)}
  </div>

  <h2 style="font-size:16px;margin:28px 0 4px">What <i>Open Link in New Window</i> opens</h2>
  <p class="lede">From row 1: right-click Dana's badge on a quote.</p>
  <div class="outcome">
    <div><div class="frame"><div class="chrome"><i></i><i></i><i></i><span>Today</span></div><div class="ostage"><div class="mainwin-ghost"></div>{outcome_today}</div></div></div>
    <div><div class="frame"><div class="chrome"><i></i><i></i><i></i><span>Proposed</span></div><div class="ostage">{outcome_prop}</div></div></div>
    <div class="note" style="grid-column: 1 / -1"><span class="lbl">Commentary</span><b>Today</b> the player's own 720×480 window, titled <i>Video Player</i>, holds the report with no toolbar, sidebar or lens rail; any playing clip closes; and, from reading the code, its route changes reach the main window's bridge (doc §2, a hand check owed). <b>Proposed</b> <code>WindowSeed.fresh(project:, lens: sessions, place: .session("s3", 754))</code>: a full window on the same project, the transcript scrolled to 12:34 and the paragraph highlighted as a deep link already does. The window chrome here is an approximation; the transcript inside it is the shipped CSS.</div>
  </div>
</main>
<script>
{SCRIPT}
</script>
</body>
</html>
"""

OUT.write_text(HTML)
print(OUT, len(HTML))
