#!/usr/bin/env python3
"""Generate docs/mockups/whisper-delivery-states.html.

Every moment of the Whisper model delivery (toolbar pill, Settings row, size
alert, run-deferral message), drawn today beside proposed. The stylesheet is
lifted from whisper-first-wait-options.html (same native-macOS drawing style),
so it cannot drift from the sibling mockups; this file adds only what the page
needs. Run: .venv/bin/python docs/mockups/whisper-delivery-states.gen.py
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = (HERE / "whisper-first-wait-options.html").read_text(encoding="utf-8")
BASE_CSS = re.search(r"<style>(.*?)</style>", SRC, re.S).group(1)

EXTRA_CSS = """
  .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 0 0 6px; align-items: start; }
  @media (max-width: 980px) { .pair { grid-template-columns: 1fr; } }
  .moment { background: var(--card); border: 0.5px solid var(--sep); border-radius: 12px; padding: 14px 16px 16px; margin: 0 0 22px; }
  .moment h3 { display: flex; gap: 8px; align-items: baseline; }
  .moment h3 .n { font-family: var(--mono); font-size: 11px; color: var(--tertiary); }
  .tag.inv { color: var(--new); border-color: var(--new); }
  .tag.ship { color: var(--shipped); border-color: var(--shipped); }
  .strip { display: flex; align-items: center; justify-content: flex-end; min-height: 38px; padding: 0 12px;
           background: var(--tbar); border-bottom: 0.5px solid var(--sep); gap: 8px; color: var(--label); }
  .strip .ttl { margin-right: auto; font-size: 12.5px; font-weight: 600; }
  .stage { position: relative; min-height: 190px; background: var(--pane); color: var(--label); }
  .stage .pop { right: 12px; top: 8px; }
  .stage .pop.left { left: 12px; right: auto; }
  .stage .pop.left::before { left: 30px; right: auto; }
  .alertbox { width: 300px; margin: 16px auto; background: var(--pop-bg); border: 0.5px solid var(--pop-stroke); border-radius: 12px;
              box-shadow: 0 14px 40px rgba(0,0,0,0.22); padding: 16px 18px; text-align: left; color: var(--label); }
  .alertbox .icon { width: 36px; height: 36px; border-radius: 9px; background: light-dark(#fff, #3a3a3d);
              border: 0.5px solid var(--sep); display: grid; place-items: center; font-weight: 700; color: var(--accent); margin-bottom: 8px; }
  .alertbox .at { font-size: 13px; font-weight: 600; margin: 0 0 4px; }
  .alertbox .ab { font-size: 11.5px; color: var(--secondary); margin: 0 0 12px; line-height: 1.4; }
  .alertbox .bt { display: flex; flex-direction: column; gap: 6px; }
  .alertbox .bt .btn { text-align: center; }
  .inv-mark { outline: 1.5px dashed var(--new); outline-offset: 2px; border-radius: 6px; }
  .sbrow { padding: 10px 14px; display: grid; grid-template-columns: 1fr; gap: 3px; }
  .sbrow .nm { font-size: 12.5px; font-weight: 500; }
  .sbrow .sub { font-size: 11px; color: var(--secondary); }
  .tbl { width: 100%; border-collapse: collapse; font-size: 12px; background: var(--card); border-radius: 8px; overflow: hidden; }
  .tbl th, .tbl td { text-align: left; padding: 6px 9px; border-bottom: 0.5px solid var(--sep); vertical-align: top; }
  .tbl th { font-weight: 600; color: var(--page-muted); background: var(--pane); }
  .ctl { position: sticky; top: 0; z-index: 9; background: var(--page); padding: 8px 0; display: flex; gap: 8px; font-size: 12px; border-bottom: 0.5px solid var(--sep); }
  .ctl button { font: inherit; padding: 2px 10px; border-radius: 6px; border: 0.5px solid var(--btn-stroke); background: var(--btn-bg); color: var(--label); cursor: pointer; }
  :root[data-force="light"] { color-scheme: light; }
  :root[data-force="dark"] { color-scheme: dark; }
  .btn { white-space: nowrap; }
  .bar.ind > i { width: 35%; animation: slide 1.4s ease-in-out infinite alternate; }
  @keyframes slide { from { margin-left: 0; } to { margin-left: 65%; } }
  @media (prefers-reduced-motion: reduce) { .bar.ind > i { animation: none; margin-left: 32%; } }
  .alertbox .bt.row { flex-direction: row-reverse; justify-content: flex-start; }
  .alertbox .bt.row .btn { flex: 0 0 auto; }
  .gap-note { color: var(--red); font-weight: 600; }
"""

BAR = '<div class="bar"><i style="width:{w}%"></i></div>'
ARROW = ('<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">'
         '<circle cx="8" cy="8" r="6.2"/><path d="M8 4.8v5.6M5.6 8.4 8 10.8l2.4-2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
XCIRC = ('<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="var(--red)" stroke-width="1.6">'
         '<circle cx="8" cy="8" r="6.2"/><path d="M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8" stroke-linecap="round"/></svg>')


def pill(label, w=None, pct=None, failed=False, extra=""):
    if failed:
        return '<span class="pill">' + XCIRC + "<span>" + label + "</span></span>"
    bar = BAR.format(w=w) if w is not None else '<div class="bar ind"><i></i></div>'
    pc = '<span class="pct">' + str(pct) + "%</span>" if pct is not None else ""
    return '<span class="pill">' + ARROW + "<span>" + label + "</span>" + bar + pc + extra + "</span>"


def pop(title, body, foot="", cls="", bar_w=None, buttons="", ind=False):
    b = BAR.format(w=bar_w) if bar_w is not None else ""
    if ind:
        b = '<div class="bar ind"><i></i></div>'
    f = '<div class="foot">' + foot + "</div>" if foot else ""
    return ('<div class="pop ' + cls + '"><div class="ptitle">' + title + "</div>" + b
            + '<div class="pbody">' + body + "</div>" + buttons + f + "</div>")


def frame(chrome, inner):
    return '<div class="shot"><div class="chrome">' + chrome + "</div>" + inner + "</div>"


def toolbar(pill_html, popover=""):
    return ('<div class="strip"><span class="ttl">Ikea interviews</span>' + pill_html + "</div>"
            '<div class="stage">' + popover + "</div>")


def settings(rows, chrome_hint=""):
    return '<div class="settings">' + rows + "</div>"


def engine_rows(status):
    return ('<div class="form-sec"><div class="frow"><div><div class="flabel">Transcription engine</div>'
            '<div class="fhint">Apple’s speech model is built into macOS and is faster. Whisper copes better with '
            'poor audio, people talking over each other, larger groups, and languages Apple’s model lacks.</div></div>'
            '<span class="popup">Whisper ⌃</span></div>'
            '<div class="frow" style="align-items:center">' + status + "</div></div>")


def status_row(left, right=""):
    return ('<div style="display:flex;gap:12px;align-items:center;width:100%;justify-content:space-between">'
            '<div style="min-width:0">' + left + "</div>" + right + "</div>")


def comment(text):
    return '<div class="comment"><span class="lab">Commentary</span>' + text + "</div>"


def moment(num, title, tags, today_chrome, today, prop_chrome, prop, note):
    t = "".join('<span class="tag ' + c + '">' + lab + "</span>" for c, lab in tags)
    return ('<section class="moment" id="m' + str(num) + '"><h3><span class="n">' + str(num) + "</span>" + title + t + "</h3>"
            '<div class="pair">' + frame(today_chrome, today) + frame(prop_chrome, prop) + "</div>" + comment(note) + "</section>")


BTN = lambda t, p=False: '<span class="btn' + (" primary" if p else "") + '">' + t + "</span>"  # noqa: E731
TODAY = "<b>today</b> · main + ba-whisper-build"
PROP = "<b>proposed</b>"
SHIP = '<span class="sys">shipped key</span>'
NEW = '<span class="new">NEW string</span>'
MOMENTS = []

# 1 ---------------------------------------------------------------------------
MOMENTS.append(moment(
    1, "First run on macOS 26 or later, Apple’s engine transcribes", [("ship", "settled: Apple first")],
    TODAY + " · sidebar row + toolbar",
    '<div class="strip"><span class="ttl">Ikea interviews</span></div><div class="stage"><div class="sbrow"><div class="nm">Ikea interviews</div>'
    '<div class="sub">Transcribing · 3 of 8 · ~12 min left</div></div></div>',
    PROP + " · same surfaces; the engine is named once, in the transcript, not in the run",
    '<div class="strip"><span class="ttl">Ikea interviews</span></div><div class="stage"><div class="sbrow"><div class="nm">Ikea interviews</div>'
    '<div class="sub">Transcribing · 3 of 8 · ~12 min left</div></div>'
    '<div class="sbrow inv-mark" style="margin:8px 14px;background:var(--card);border:0.5px solid var(--sep)"><div class="nm">p1.mp4</div>'
    '<div class="sub">Transcribed with Apple’s speech model</div></div></div>',
    "<b>Today:</b> nothing says which engine ran. Settings says Whisper, the run uses Apple’s until the model is on disk. "
    "<b>Proposed (INVENTED, option for the owner):</b> a per-session line, “Transcribed with Apple’s speech model” / "
    "“…with Whisper”, in the session’s detail only, so a reader can tell which engine produced which transcript. "
    "Not on the Sessions grid, not in the pill: one place, shown after the fact. Needs the engine recorded per session; check "
    "whether the manifest already carries it before costing it. New strings: 2 (one per engine) × 21 locales."))

# 2 ---------------------------------------------------------------------------
ALERT_BODY = "About 1.5 GB. It helps with poor audio and people talking over each other. You can download it later in Settings."
MOMENTS.append(moment(
    2, "Offering Whisper: the size alert", [("ship", "4.2.3(ii) disclosure"), ("inv", "proposed text = option")],
    TODAY + " · NSAlert sheet, asked once per Mac",
    '<div class="stage" style="min-height:230px"><div class="alertbox"><div class="icon">B</div>'
    '<div class="at">Download the Whisper speech model?</div>'
    '<div class="ab">' + ALERT_BODY + '</div>'
    '<div class="bt row">' + BTN("Download", True) + BTN("Not Now") + "</div></div></div>",
    PROP + " · macOS 26 and later only; one sentence swapped in",
    '<div class="stage" style="min-height:230px"><div class="alertbox"><div class="icon">B</div>'
    '<div class="at">Download the Whisper speech model?</div>'
    '<div class="ab">About 1.5 GB. <span class="inv-mark">Apple’s speech model transcribes until Whisper is on this Mac.</span> You can download it later in Settings.</div>'
    '<div class="bt row">' + BTN("Download", True) + BTN("Not Now") + "</div></div></div>",
    "<b>What the guideline needs:</b> 4.2.3(ii) asks that the app disclose the size and prompt before downloading; today’s alert does (size, two buttons, Escape answers Not Now). "
    "<b>Gap this closes:</b> a researcher who says Not Now, or ignores the pill, still has Whisper selected in Settings and a run silently on Apple’s engine. "
    "The dashed sentence (INVENTED, 1 string × 21 locales) replaces the benefit clause, so the alert stays at three sentences. It is true only where Apple’s engine exists: on macOS 15 the alert keeps today’s text. "
    "Buttons are drawn as a row with the default trailing, as an NSAlert lays them out (the first mock stacked them). "
    "<b>Why no alert at a relaunch (read from code, not reproduced):</b> <code>autoStart</code> returns <code>.ask</code> only while <code>hasAnswered</code> is false; the answer is stored in UserDefaults, so after one Download or Not Now it never asks again (by design), and after Download the next launch starts silently. "
    "A first run with no alert has another cause (no AI consent yet, under 10 GB free, a remembered Stop): unknown on build 6532. "
    "<b>Review risk, from the App Store review:</b> after Not Now, with under 10 GB free, on macOS 15 or with a pinned language, a run that needs Whisper still fetches from Hugging Face with no alert (design doc §7 exception). A reviewer who says Not Now and then watches a download start is a 4.2.3(ii) rejection. Not drawn here because it is a behaviour, not a pixel."))

# 3 ---------------------------------------------------------------------------
today3 = toolbar(pill("Downloading Whisper", w=0),
                 pop("Downloading Whisper", "Zero KB of 1.61 GB", cls="", bar_w=0,
                     foot='<span>For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.</span>'))
prop3 = toolbar(pill("Downloading Whisper"),
                pop("Downloading Whisper", "Starting", ind=True,
                    foot="<span>For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.</span>"))
MOMENTS.append(moment(
    3, "In progress, first seconds: “Zero KB”", [("ship", "bug fix, no new UX")],
    TODAY + " · before the first byte", today3,
    PROP + " · a moving indeterminate bar until a byte arrives", prop3,
    "<b>Measured today (Foundation on macOS 27):</b> <code>ByteCountFormatter.string(fromByteCount: 0, countStyle: .file)</code> returns “Zero KB”, and a <code>Progress</code> with 0 completed units and 1.6 GB total prints “Zero KB of 1.61 GB”. "
    "That is the line shown while the bar is at 0, which is the wait before Background Assets reports its first byte. "
    "<b>Fix, no new string:</b> treat 0 bytes as not started, show a moving indeterminate bar (HIG: “Keep progress indicators moving”; the bar stops under Reduce Motion) and the shipped <code>desktop.cloudImport.downloadStarting</code> (“Starting”, shipped for the importer). "
    "Setting <code>allowsNonnumericFormatting = false</code> would give “0 KB”: honest, still ugly."))

# 4 ---------------------------------------------------------------------------
today4 = toolbar(pill("Downloading Whisper", w=49, pct=49),
                 pop("Downloading Whisper", "789.0 MB of 1.61 GB", bar_w=49,
                     foot='<span></span>' + BTN("Stop Download")))
prop4 = toolbar(pill("Downloading Whisper", w=49, pct=49),
                pop("Downloading Whisper", "789 MB of 1.6 GB", bar_w=49,
                    foot='<span></span>' + BTN("Stop Download")))
MOMENTS.append(moment(
    4, "In progress: pill and popover", [("ship", "pill is shipped; no change proposed")],
    TODAY + " · Background Assets path (no throughput from Apple)", today4,
    PROP + " · same pill; only the byte line’s number format", prop4,
    "<b>What the API gives:</b> a <code>Progress</code> (completed and total units, cancellable) and nothing else; throughput and time remaining are not set by Apple (observed 17 Nov). "
    "<b>Deliberately not proposed: an ETA.</b> The BA download took about 2.5 minutes on 17 Nov, an estimate would be short-lived and would invent a new string (Foundation’s localised line needs a rate Apple does not supply); the HIG warns that progress which jumps “can even feel deceptive”. "
    "<b>Only change:</b> one rule for sizes (“1.5 GB” in the alert, 1.61 GB in the line, 1.6 GB on disk are three spellings of one model); fix the formatter, do not merge the true numbers (about 1.5 GB download, 1.6 GB on disk). "
    "The percent beside the bar duplicates the popover; left as shipped. "
    "<b>Stop note:</b> the branch already hides “Starts again from the beginning next time.” on the Background Assets path, so both frames omit it. Cancel restarting from byte 0 is observed, not documented, so copy says neither. No confirmation: a restart costs about 2.5 minutes, not a real loss."))

# 5 ---------------------------------------------------------------------------
frame5 = ('<div class="strip"><span class="ttl">Ikea interviews</span>' + pill("Downloading Whisper", w=62, pct=62) + "</div>"
          '<div class="stage"><div class="sbrow"><div class="nm">p4.mp4</div>'
          '<div class="sub">Waiting for Whisper</div></div>'
          '<div class="sbrow"><div class="nm" style="color:var(--secondary);font-weight:400">Apple’s speech model wasn’t sure of what it heard, so Whisper will transcribe it once it’s on this Mac.</div></div></div>')
MOMENTS.append(moment(
    5, "Run waits for the model", [("ship", "copy shipped; no change proposed")],
    TODAY + " · run-deferral message", frame5,
    PROP + " · unchanged", frame5,
    "Drawn identically on purpose. An earlier draft repeated the pill’s percentage inside the deferral line; the Mac review called that a fourth progress readout in one window (the pill, the popover and the Settings row already show it) and the HIG asks for progress in one consistent place. Dropped. "
    "<b>The gap here is not the wait, it is the end of the wait:</b> the design doc (open item 4) says that with Whisper absent and Background Assets failing, a deferred session waits indefinitely, and the App Store review rates that as the most likely thing a reviewer meets, because reviewer fetches of Apple-hosted packs have failed in several forum reports. The wait needs an end state (the failed pill and Retry, or letting Apple’s transcript stand). That is a behaviour decision for the owner, not a pixel."))

# 6 ---------------------------------------------------------------------------
sett6a = settings(engine_rows(status_row('<span style="color:var(--secondary)">Not on this Mac</span>', BTN("Download Now"))))
sett6b = settings(engine_rows(status_row('<span style="color:var(--secondary)">Not on this Mac</span>', BTN("Download Now"))
                              + ''))
MOMENTS.append(moment(
    6, "Settings, Transcription: Whisper not on this Mac", [("ship", "row shipped"), ("inv", "wording = option")],
    TODAY + " · Settings › Transcription", sett6a,
    PROP + " · the row says what runs meanwhile",
    settings(engine_rows(status_row('<span style="color:var(--secondary)">Not on this Mac</span><div class="fhint inv-mark">Apple’s speech model transcribes until Whisper is on this Mac.</div>', BTN("Download Now")))),
    "<b>Gap:</b> the picker says Whisper, the row says Not on this Mac, and a run uses Apple’s engine with no sentence connecting the two. "
    "<b>Proposed (INVENTED, 1 string × 21 locales):</b> one hint line under the status, only in this state, only when Apple’s engine is available. "
    "On macOS 15 (no Apple engine) the line does not appear and the run waits instead; that case needs its own words, not this one."))

# 7 ---------------------------------------------------------------------------
dl_row = status_row('<div style="width:200px">' + BAR.format(w=49) + '</div><div class="fhint">789.0 MB of 1.61 GB</div>', BTN("Stop Download"))
dl_row_p = status_row('<div style="width:200px">' + BAR.format(w=49) + '</div><div class="fhint">789 MB of 1.6 GB</div>', BTN("Stop Download"))
MOMENTS.append(moment(
    7, "Settings: downloading, ready, failed", [("ship", "all three shipped")],
    TODAY + " · downloading", settings(engine_rows(dl_row)),
    PROP + " · same row; only the number format changes", settings(engine_rows(dl_row_p)),
    "The row and the pill already read one <code>WhisperDownloadModel</code> so they cannot disagree; the proposal only changes the byte line to the pill’s. "
    "Ready: “On this Mac · 1.6 GB” (shipped) and the status row hides under the Apple choice. Failed: the shipped cause lines "
    "(disk, network, certificate) plus Retry. The size reads 1.6 GB on disk and “about 1.5 GB” in the alert and 1.61 GB in the progress line: "
    "<span class=\"gap-note\">three spellings of one number</span> (1,613,977,612 B plus config, pack download size 1,501,833,765 B); pick one unit rule."))

# 8 ---------------------------------------------------------------------------
fail_pop = pop("Whisper didn’t download",
               "The connection dropped and didn’t come back.<br><br>For your next recordings. Whisper copes better with poor audio, people talking over each other and larger groups.",
               buttons='<div style="text-align:right">' + BTN("Retry", True) + "</div>")
fail_prop = pop("Whisper didn’t download",
                "The connection dropped and didn’t come back.",
                buttons='<div style="text-align:right">' + BTN("Retry", True) + "</div>")
MOMENTS.append(moment(
    8, "Failed, offline, low disk", [("ship", "causes shipped"), ("inv", "dropping the pitch = option")],
    TODAY + " · network cause", toolbar(pill("Whisper didn’t download", failed=True), fail_pop),
    PROP + " · the failure says only what failed", toolbar(pill("Whisper didn’t download", failed=True), fail_prop),
    "<b>Offline:</b> macOS owns a Background Assets download; the observed failure on a dropped server was NSURLErrorDomain -1005 and the OS did not retry by itself, so Retry is right. "
    "<b>Proposed (small):</b> drop the “Whisper copes better…” pitch from inside an error; the Mac review: a sales sentence does not belong in a failure. The cause line stays. "
    "<b>Low disk:</b> the shipped cause line is “This Mac doesn’t have enough free space for it.” An earlier draft added “about 1.6 GB free”; dropped, because nobody has measured that 1.6 GB is enough for download plus staging, and a wrong number is worse than none. "
    "A lone Retry on a full disk is a dead end: the better fix is to name the fact to act on once it is measured (house rule). The app also does not auto-start below 10 GB free (owner, 30 Oct) and says nothing about that: gap G8. "
    "<b>Raw detail:</b> the house rule is interpretation first, raw behind a disclosure; the shipped popover has none (gap G10, not an invention)."))

# 9 ---------------------------------------------------------------------------
MOMENTS.append(moment(
    9, "macOS 15, kill switch off: the Hugging Face path", [("ship", "shipped")],
    TODAY + " · Hugging Face download (macOS 15, .dmg, fallback)", toolbar(pill("Downloading Whisper", w=49, pct=49),
        pop("Downloading Whisper", "789.0 MB of 1.61 GB (10.0 MB/s) — About 1 minute, 23 seconds remaining", bar_w=49,
            foot="<span>Starts again from the beginning next time.</span>" + BTN("Stop Download"))),
    PROP + " · unchanged", toolbar(pill("Downloading Whisper", w=49, pct=49),
        pop("Downloading Whisper", "789.0 MB of 1.61 GB (10.0 MB/s) — About 1 minute, 23 seconds remaining", bar_w=49,
            foot="<span>Starts again from the beginning next time.</span>" + BTN("Stop Download"))),
    "Same pill, same row. Here the app owns the download, so rate, time left and the “starts again” note are true and shown. "
    "The line “(10.0 MB/s) — About 1 minute, 23 seconds remaining” is Foundation’s own text, em dash included; the no-em-dash rule is about our copy, so the owner decides whether to accept a system string or compose the line. "
    "On macOS 15 there is no Apple engine, so a first run waits for Whisper; a different state that this page does not redraw. "
    "Locale cost of everything marked INVENTED: 1 string × 21 locales (the “meanwhile” sentence); the per-session engine line is not drawn."))

STRINGS = [
    ("Apple’s speech model transcribes until Whisper is on this Mac.", "size alert (macOS 26+) and Settings status row: one string, two uses", "NEW"),
    ("Starting", "pill popover before the first byte", "reuse desktop.cloudImport.downloadStarting"),
    ("789 MB of 1.6 GB", "popover line", "Foundation, localised by the OS; only the number format changes"),
    ("Transcribed with Apple’s speech model / with Whisper", "session detail, not drawn here (2 strings, post-submission option)", "NEW, not drawn"),
]

html = ["<!DOCTYPE html><html lang=\"en-GB\" data-color-theme=\"default\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Whisper delivery: every state, today and proposed</title>",
        "<!-- Generated by whisper-delivery-states.gen.py from whisper-first-wait-options.html (stylesheet). Drawn 17 Nov 2026 "
        "against main 3e9894709 and branch ba-whisper-build (read only). Medium-fidelity native macOS chrome. Every string inside an "
        "artefact frame is a shipped locale key (checked against bristlenose/locales/en/desktop.json) unless dashed in orange = INVENTED. -->",
        "<style>" + BASE_CSS + EXTRA_CSS + "</style></head><body><div class=\"wrap\">",
        '<div class="ctl"><span>Scheme</span><button onclick="document.documentElement.removeAttribute(\'data-force\')">Auto</button>'
        '<button onclick="document.documentElement.dataset.force=\'light\'">Light</button>'
        '<button onclick="document.documentElement.dataset.force=\'dark\'">Dark</button></div>',
        "<h1>Whisper delivery: every state, today and proposed</h1>",
        '<p class="lede">Nine moments from first run to failure, each drawn as today (left) and proposed (right) for the toolbar pill, '
        'the Settings row, the size alert and the run-deferral message. Evidence and sources: '
        '<code>docs/private/app-store-launch/ba-ux-research.md</code>.</p>',
        '<div class="key"><span><i class="swatch art"></i>Artefact: real pixels, shipped strings</span>'
        '<span><i class="swatch com"></i>Commentary: not the product</span>'
        '<span><span class="inv-mark" style="padding:0 6px">dashed orange</span>INVENTED element or string, owner decision</span></div>']
html += MOMENTS
html.append("<h2>String plan</h2><table class=\"tbl\"><tr><th>Text</th><th>Where</th><th>Status</th></tr>"
            + "".join("<tr><td>" + a + "</td><td>" + b + "</td><td>" + c + "</td></tr>" for a, b, c in STRINGS)
            + "</table><p class=\"lede\" style=\"margin-top:8px\">Each NEW string needs all 21 full locales; none is added by this mockup.</p>")
html.append("</div></body></html>")
(HERE / "whisper-delivery-states.html").write_text("\n".join(html), encoding="utf-8")
print("wrote whisper-delivery-states.html")
