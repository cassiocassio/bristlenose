"""Generate docs/mockups/toast-audit-v2.html.

v1 (toast-audit-v1.html, 10 Nov 2026) was the audit: today's wording and a
first proposal. v2 redraws the right-hand column with the decisions taken in
review the same day (Lucide kind glyphs, title and body, dash-free wording,
four of five kinds) and adds a decision trail: what is decided, what is still
being thought about, and what was abandoned, each with the reason.

The status vocabulary below (Decided, Leaning, Open, Parked, Abandoned) is new
with this page; no earlier mockup carried one. Run from the repo root:
    .venv/bin/python docs/mockups/toast-audit-v2.gen.py
"""

from html import escape
from pathlib import Path

OUT = Path(__file__).with_name("toast-audit-v2.html")

# Lucide paths (24 grid), the shapes that match the Mac's SF Symbols for each kind:
# circle-check / checkmark.circle, info / info.circle, triangle-alert /
# exclamationmark.triangle, circle-x / xmark.circle. Stroke follows the text stem.
LUCIDE = {
    "success": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "warning": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
        '<path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "error": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
}
TEXT_GLYPH = {"success": "✓", "info": "ℹ", "warning": "⚠", "error": "✗"}

STATUS = {
    "decided": "Decided",
    "leaning": "Leaning",
    "open": "Open",
    "parked": "Parked",
    "abandoned": "Abandoned",
}


def e(s):
    return escape(s, quote=False)


def icon(kind):
    return (
        '<svg class="ico ico-' + kind + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + LUCIDE[kind] + "</svg>"
    )


def old_toast(text, kind=None, meta=None, mac=False):
    """Today's capsule: a text glyph, one weight, one line of text."""
    cls = "toast old" + (" has-kind" if kind else "") + (" mac" if mac else "")
    inner = ""
    if kind:
        inner += '<span class="glyph glyph-' + kind + '">' + TEXT_GLYPH[kind] + "</span>"
    inner += "<span>" + e(text) + "</span>"
    out = '<div class="' + cls + '">' + inner + "</div>"
    if meta:
        out += '<div class="meta">' + e(meta) + "</div>"
    return out


def old_key(text, note):
    """A message whose locale key is missing: the page would draw the key."""
    return (
        '<div class="toast old"><code>' + e(text) + "</code></div>"
        '<div class="meta warn">' + e(note) + "</div>"
    )


def toast(body, kind=None, title=None, meta=None, action=None, held=False, code=False):
    """The proposed capsule: a Lucide icon, an optional title, a quieter body."""
    inner = ""
    if kind:
        inner += icon(kind)
    text = ""
    if title:
        text += '<div class="t-title">' + e(title) + "</div>"
    if body:
        shown = "<code>" + e(body) + "</code>" if code else e(body)
        text += '<div class="t-body' + ("" if title else " solo") + '">' + shown + "</div>"
    inner += '<div class="t-text">' + text + "</div>"
    if action:
        inner += '<span class="toast-action">' + e(action) + "</span>"
    out = '<div class="toast new">' + inner + "</div>"
    tags = []
    if meta:
        tags.append(meta)
    if held:
        tags.append("held, pauses on hover")
    if tags:
        out += '<div class="meta">' + e(" · ".join(tags)) + "</div>"
    return out


def silent(note):
    return '<div class="silent">nothing drawn</div><div class="meta">' + e(note) + "</div>"


def menu_item(label, why):
    return (
        '<div class="menu"><div class="menu-row off">' + e(label) + "</div></div>"
        '<div class="meta">' + e(why) + "</div>"
    )


def button_off(label, title):
    return (
        '<button class="btn-off" disabled>' + e(label) + "</button>"
        '<div class="meta">hover reason: “' + e(title) + "”</div>"
    )


def inline_field(value, msg):
    return (
        '<div class="field"><div class="input">' + e(value) + "</div>"
        '<div class="field-err">' + icon("error") + "<span>" + e(msg) + "</span></div></div>"
    )


def chip(title, lines):
    body = "".join('<div class="t-body">' + e(x) + "</div>" for x in lines)
    return (
        '<div class="chip"><div class="t-text">'
        '<div class="t-title chip-label bn-thinking-shimmer">' + e(title) + "</div>" + body + "</div></div>"
    )


def tag(text):
    return '<span class="tag">' + e(text) + "</span>"


def sc(trigger, left, right, ref=""):
    return {"trig": trigger, "left": left, "right": right, "ref": ref}


def dec(status, text):
    return (status, text)


# Wording notes: titles carry no full stop; a message that was one sentence stays one
# line with no title; the dash becomes a full stop (two sentences) or a split into
# title and body. All of it is English locale copy; every change is a 21-locale pass.

GROUPS = [
    # ── A ────────────────────────────────────────────────────────────────
    {
        "id": "A",
        "title": "Copy as CSV",
        "where": "Mac app · Edit menu ▸ Copy as CSV → bridge `copyAsCSV` → the page draws the toast · Quotes lens",
        "issue": (
            "<p><b>The three messages have no locale entry.</b> <code>toolbar.noQuotesSelected</code>, "
            "<code>toolbar.csvCopied</code> and <code>toolbar.csvFailed</code> are called in "
            "<code>AppLayout.tsx:637–644</code> with no default value, and a search of "
            "<code>bristlenose/locales/</code> and <code>frontend/src</code> finds them nowhere else. "
            "i18next returns the key when it has no string, so the toast most likely reads as the key "
            "itself. <i>Not checked live.</i> Check this first: it is reachable only from the native menu.</p>"
            "<p><b>Kinds:</b> N, C, F. In the Mac app a disabled menu item beats “nothing selected” "
            "(<code>quote-action-state</code> already mirrors it), and a copy the researcher just made "
            "needs no word. The failure keeps a toast, with the error icon.</p>"
        ),
        "dec": [
            dec("open", "Embedded confirmations: suppress the visual and keep announce()? (decision 1)"),
            dec("open", "Wording for the failure: the key has no string, so someone has to write it"),
        ],
        "rows": [
            sc("Nothing selected or focused", old_key("toolbar.noQuotesSelected", "key not found in any locale · 2000 ms · no kind"), menu_item("Copy as CSV", "dimmed by quote-action-state; the message becomes unreachable"), "#1"),
            sc("Quotes selected, clipboard write succeeds", old_key("toolbar.csvCopied", "count passed · 2000 ms · no kind"), silent("tone “confirm”: no visual under isEmbedded(); announce() still speaks"), "#2"),
            sc("Clipboard write is refused", old_key("toolbar.csvFailed", "2000 ms · no kind"), toast("toolbar.csvFailed", "error", held=True, code=True, meta="wording still to be written"), "#3"),
        ],
    },
    # ── B ────────────────────────────────────────────────────────────────
    {
        "id": "B",
        "title": "Copy Quotes",
        "where": "Quotes lens ▸ Export dropdown ▸ Copy Quotes (browser) · same code run from the Mac menu",
        "issue": (
            "<p><b>Kinds:</b> N (#9, #12), C (#10), F (#11). The origin case: the first toast ever "
            "(30 Jan 2026) confirmed a clipboard copy, and that is a legitimate use (no subject on screen).</p>"
            "<p>“Export failed” renders as the same plain capsule as “Copied”; the failure now carries "
            "the error icon and a longer hold, and a later success cannot replace it. "
            "<code>exportActions.ts:104</code> announces twice (delete one).</p>"
        ),
        "dec": [
            dec("decided", "Failures carry the error icon and a longer hold (phase 2 and 3, beta-safe)"),
            dec("open", "Keep the short success in a browser, suppress it in the app (decision 1)"),
        ],
        "rows": [
            sc("Filters leave no quotes (two sites)", old_toast("No quotes match current filters", meta="2000 ms · no kind · #9, #12"), button_off("Copy Quotes", "No quotes match current filters"), "#9, #12"),
            sc("Copy succeeds", old_toast("47 quotes copied", meta="2000 ms · no kind · also announce() again"), toast("47 quotes copied", meta="browser: kept, short") + '<div class="sp"></div>' + silent("Mac app: visual suppressed, announce() kept"), "#10"),
            sc("Clipboard write throws", old_toast("Export failed", meta="2000 ms · no kind"), toast("Export failed", "error", held=True), "#11"),
        ],
    },
    # ── C ────────────────────────────────────────────────────────────────
    {
        "id": "C",
        "title": "Extract clips: refused at the start",
        "where": "Quotes lens ▸ Export dropdown ▸ Extract clips · server answers 422 / 409 / other",
        "issue": (
            "<p><b>Kinds:</b> N (#13), F (#15, 16, 17). The server’s status is mapped to a sentence by "
            "<code>msg.includes(\"422\")</code>. The clip export first shipped with an “async progress toast” "
            "(<code>85cb1f4cf</code>) that became the chip; only these start-time refusals stayed toasts.</p>"
            "<p>“FFmpeg not found — install it to extract clips” is two sentences joined by a dash: "
            "it becomes a title (what is the case) and a body (what to do). “Extraction in progress” "
            "is the weakest failure, because the chip already shows that job.</p>"
        ),
        "dec": [
            dec("decided", "No em dash in toast copy: two sentences, or a title and a body"),
            dec("open", "Does “Extraction in progress” earn a toast at all, since the chip shows it?"),
        ],
        "rows": [
            sc("No quote is starred or featured", old_toast("No starred or featured quotes to extract", meta="2000 ms · no kind"), menu_item("Extract clips", "disabled with its reason as the title; where it stays a toast, kind “info”"), "#13"),
            sc("Server says 422: no FFmpeg", old_toast("FFmpeg not found — install it to extract clips", meta="2000 ms · no kind"), toast("Install it to extract clips.", "error", title="FFmpeg not found", held=True), "#15"),
            sc("Server says 409: already running", old_toast("Extraction in progress", meta="2000 ms · no kind"), toast("Extraction in progress", "error", held=True, meta="owner call: the chip already shows it"), "#16"),
            sc("Any other failure", old_toast("Clip extraction failed", meta="2000 ms · no kind"), toast("Clip extraction failed", "error", held=True), "#17"),
        ],
    },
    # ── D ────────────────────────────────────────────────────────────────
    {
        "id": "D",
        "title": "Extract clips: started, with notices",
        "where": "Quotes lens ▸ Export ▸ Extract clips, accepted by the server · each notice shown only when it applies",
        "issue": (
            "<p><b>Kind:</b> J, a notice about a started job. Today two warnings are joined into one toast "
            "held 6 s, because one toast replaces the last and the progress line would have replaced a second.</p>"
            "<p>It is a state of the job, not a fact, so it moves into the job’s chip: the live progress line "
            "is the title (an existing string that keeps updating), and the notices are the body in regular "
            "weight. Same anatomy as the toast, so the two read as one family. While running the title carries the shipped "
            "shimmer, not a ring (the ring is the Mac sidebar’s). No new strings beyond the dash rewrite.</p>"
        ),
        "dec": [
            dec("decided", "Title and body anatomy for toast and chip (title 490, body 420, quieter)"),
            dec("decided", "The job notice moves into the chip (phase 7)"),
            dec("open", "Does the PII notice need to show on every clip export, or once?"),
        ],
        "rows": [
            sc("PII warning and no subtitle burn-in, both present", old_toast("Clips contain original audio — PII redaction applies to transcript text only · This FFmpeg can’t burn in subtitles — extracting plain clips only", meta="6000 ms · no kind"), chip("Extracting clips… (0 of 12)", ["Clips contain original audio. PII redaction applies to transcript text only.", "This FFmpeg can’t burn in subtitles. Extracting plain clips only."]), "#14"),
        ],
    },
    # ── E ────────────────────────────────────────────────────────────────
    {
        "id": "E",
        "title": "Export screens: refused at the start",
        "where": "Screens lens ▸ Export Screens (browser and Mac)",
        "issue": (
            "<p><b>Kinds:</b> N (#18), F (#19). Copied from the clips shape on 17 Oct 2026 "
            "(<code>ab7696ceb</code>). The empty case is a state, so the control says it. "
            "Already-running is the same owner call as clips.</p>"
        ),
        "dec": [
            dec("open", "Does “already running” earn a toast, as with clips?"),
        ],
        "rows": [
            sc("Screens lens has nothing yet", old_toast("No screens to export yet", meta="2000 ms · no kind"), button_off("Export Screens", "No screens to export yet"), "#18"),
            sc("A screens export is already running", old_toast("A screens export is already running", meta="2000 ms · no kind"), toast("A screens export is already running", "error", held=True, meta="owner call: the chip already shows it"), "#19"),
            sc("Any other failure", old_toast("Screens export failed", meta="2000 ms · no kind"), toast("Screens export failed", "error", held=True), "#19"),
        ],
    },
    # ── F ────────────────────────────────────────────────────────────────
    {
        "id": "F",
        "title": "Copy Screens (a round trip)",
        "where": "Mac app only · Screens lens ▸ Copy Screens: page asks native to write the pasteboard, native answers, the page draws the word",
        "issue": (
            "<p><b>Kinds:</b> C (#4), F (#5–8). A native action’s outcome is drawn by the page "
            "(<code>screens-pasteboard-write</code> out, <code>menuAction(\"screensCopied\")</code> back, "
            "<code>BridgeHandler.swift:1621</code>). It exists because <code>0fc4193f1</code> (17 Oct) found "
            "“Copied” said before anything was on the clipboard; the only road for the shell’s verdict to "
            "the researcher ran through the page.</p>"
            "<p>One sentence at four failure sites. The success is a confirmation of something the "
            "researcher just did; if the owner keeps it, it splits into a title and a body.</p>"
        ),
        "dec": [
            dec("open", "Native success draws nothing? (decision 6; needs a yes before the page stops saying it)"),
            dec("decided", "One failure sentence, drawn once, with the error icon"),
        ],
        "rows": [
            sc("Native pasteboard write succeeds", old_toast("3 screenshots copied — paste them into Miro or FigJam", meta="6000 ms · no kind"), silent("owner call (decision 6): native success needs no word") + '<div class="sp"></div>' + toast("Paste them into Miro or FigJam.", title="3 screenshots copied", meta="only if the owner keeps it"), "#4"),
            sc("Native pasteboard write fails", old_toast("Couldn’t put the screenshots on the clipboard.", meta="6000 ms · no kind"), toast("Couldn’t put the screenshots on the clipboard.", "error", held=True), "#5"),
            sc("A newer export replaced it · no files · read failed (three branches)", old_toast("Couldn’t put the screenshots on the clipboard.", meta="6000 ms · no kind · same sentence at 3 sites"), toast("Couldn’t put the screenshots on the clipboard.", "error", held=True, meta="one site, not four"), "#6–8"),
        ],
    },
    # ── G ────────────────────────────────────────────────────────────────
    {
        "id": "G",
        "title": "Show in folder",
        "where": "Activity chip ▸ “Show in folder” after a clip or screens export",
        "issue": (
            "<p><b>Kind:</b> F. <code>f15a263d4</code> (RE#20 #44): the failure was “caught into the console "
            "only — the chip had already closed”, so it borrowed the toast. A legitimate one: no subject "
            "on screen, a failed off-screen request. It needs only the icon and a hold.</p>"
        ),
        "dec": [dec("decided", "Stays a toast, with the error icon and a hold")],
        "rows": [
            sc("The native side refuses the reveal", old_toast("Couldn’t show the folder.", meta="6000 ms · no kind"), toast("Couldn’t show the folder.", "error", held=True), "#21"),
        ],
    },
    # ── H ────────────────────────────────────────────────────────────────
    {
        "id": "H",
        "title": "Naming a speaker: the name is taken",
        "where": "Sessions grid ▸ speaker cell ▸ web picker (the Mac draws its own picker, so this is browser only; the other caller, SessionsTable.tsx:440, is unchecked)",
        "issue": (
            "<p><b>Kind:</b> N, “refused aloud” (§J8.11). The commit does not say why aloud meant a "
            "toast and not inline validation; <i>not investigated</i>.</p>"
            "<p>The subject is on screen and still open (the field being typed in), and the clash is a "
            "state of that field. Inline validation with the same sentence, no new string. New UX, so "
            "behind the R114 gate.</p>"
        ),
        "dec": [dec("open", "Inline validation instead of a toast (new UX, R114 gate)")],
        "rows": [
            sc("Typed a name another person already has", old_toast("Sam is already in the list. Pick them, or add something to tell the two apart.", meta="5000 ms · no kind"), inline_field("Sam", "Sam is already in the list. Pick them, or add something to tell the two apart."), "#20"),
        ],
    },
    # ── I ────────────────────────────────────────────────────────────────
    {
        "id": "I",
        "title": "A background save did not land",
        "where": "Anywhere the page writes: edit a quote, star, hide, tag, rename. A browser or the Mac web view, after the write returns",
        "issue": (
            "<p><b>Kind:</b> S. <code>b19c75add</code> (25 Jul): “a failed sync is otherwise invisible until "
            "reload silently reverts the user’s change.” Later commits made it say <i>why</i>.</p>"
            "<p><b>This is the toast the browser cannot do without:</b> no subject on screen, a lost "
            "edit otherwise, no native state to mirror. It fails only on hold time: 4 s is gone before a "
            "researcher who was looking at a quote sees it.</p>"
            "<p>Where the message is two sentences it splits: “Couldn’t save your change” is the title, "
            "the reason is the body. The kind for these sites is not named in phase 2; drawn as error, and "
            "the running-analysis case as warning (waiting fixes it), which is my reading.</p>"
        ),
        "dec": [
            dec("decided", "Error icon, longer hold, an error is not displaced by a success"),
            dec("open", "How long an error holds, and whether it waits to be dismissed (decision 4)"),
        ],
        "rows": [
            sc("Serve restarted under an open tab (dead token)", old_toast("Couldn’t save your change — Bristlenose has restarted. Reload the page, then make the change again.", meta="6000 ms · no kind"), toast("Bristlenose has restarted. Reload the page, then make the change again.", "error", title="Couldn’t save your change", held=True), "#22"),
            sc("Network or server error", old_toast("Couldn’t save your change — check your connection.", meta="4000 ms · no kind"), toast("Check your connection.", "error", title="Couldn’t save your change", held=True), "#23"),
            sc("Server refuses the write", old_toast("Couldn’t save your change.", meta="4000 ms · no kind"), toast("Couldn’t save your change", "error", held=True), "#23"),
            sc("An analysis is running", old_toast("An analysis is running. Try again when it finishes.", meta="4000 ms · no kind"), toast("Try again when it finishes.", "warning", title="An analysis is running", held=True), "#23"),
            sc("A re-run removed the quote", old_toast("That quote is no longer in the report, so your change wasn’t saved.", meta="4000 ms · no kind"), toast("That quote is no longer in the report, so your change wasn’t saved.", "error", held=True), "#23"),
        ],
    },
    # ── J ────────────────────────────────────────────────────────────────
    {
        "id": "J",
        "title": "AutoCode will not start",
        "where": "Codebook ▸ a framework ▸ ✦ AutoCode (Codebook lens)",
        "issue": (
            "<p><b>Kind:</b> R. The only toasts that already carry a kind (30 Aug, <code>ae050e567</code>). "
            "The code comment is the best reason in the codebase: “A refusal is transient and about the click.”</p>"
            "<p>Three of the sentences tell the researcher to go to Settings and give no way to get there. "
            "The Mac app already has the bridge message (<code>open-settings</code>, "
            "<code>BridgeHandler.swift:1899</code>). Single sentences stay one line; “No quotes yet. "
            "Analyse your sessions first.” splits at its full stop.</p>"
        ),
        "dec": [
            dec("decided", "An action button on the Settings refusals (phase 5)"),
            dec("open", "“Open Settings” is a new locale key (21 locales)"),
        ],
        "rows": [
            sc("No API key configured", old_toast("Add an API key in Settings first.", "error", meta="4000 ms · error"), toast("Add an API key in Settings first.", "error", action="Open Settings", held=True), "#24"),
            sc("Provider is a local model", old_toast("This needs a cloud AI provider, not a local model.", "error", meta="4000 ms · error"), toast("This needs a cloud AI provider, not a local model.", "error", action="Open Settings", held=True), "#24"),
            sc("Provider is ambiguous", old_toast("Choose an AI provider in Settings.", "error", meta="4000 ms · error"), toast("Choose an AI provider in Settings.", "error", action="Open Settings", held=True), "#24"),
            sc("No quotes yet", old_toast("No quotes yet — analyse your sessions first.", "warning", meta="4000 ms · warning"), toast("Analyse your sessions first.", "warning", title="No quotes yet"), "#25"),
            sc("Already tagging with this codebook", old_toast("Already tagging with this codebook.", "info", meta="4000 ms · info"), toast("Already tagging with this codebook.", "info", meta="unchanged"), "#26"),
            sc("Already applied", old_toast("Already applied.", "info", meta="4000 ms · info"), toast("Already applied.", "info", meta="unchanged"), "#26"),
            sc("Codebook template missing", old_toast("That codebook is no longer available.", "error", meta="4000 ms · error"), toast("That codebook is no longer available.", "error", meta="unchanged"), "#24"),
            sc("Rate limited (provider)", old_toast("Rate limited — tagging stopped. Try again soon.", "error", meta="autocodeFailure.rateLimited"), toast("Tagging stopped. Try again soon.", "error", title="Rate limited"), "#25"),
            sc("Any other start failure", old_toast("Tagging failed.", "error", meta="4000 ms · error"), toast("Tagging failed.", "error", meta="unchanged"), "#25"),
        ],
    },
    # ── K ────────────────────────────────────────────────────────────────
    {
        "id": "K",
        "title": "Feedback sent",
        "where": "Footer ▸ Send feedback. Browser: the web modal closes. Mac app: the footer posts open-feedback and a native sheet answers",
        "issue": (
            "<p><b>Kind:</b> C. Already forked by deployment. The history of why this one is a toast was "
            "<i>not read</i>. The modal has closed, so no subject is left on screen and the toast is the only "
            "signal the send worked: the plausible answer is keep, as a title and body.</p>"
        ),
        "dec": [dec("leaning", "Keep in the browser. In the app the native sheet closing is the confirmation")],
        "rows": [
            sc("Browser: modal closes after sending", old_toast("Feedback sent — thank you!", meta="2000 ms · no kind"), toast("Thank you!", title="Feedback sent"), "#27"),
        ],
    },
    # ── L ────────────────────────────────────────────────────────────────
    {
        "id": "L",
        "title": "The Mac’s own toast",
        "where": "Mac app · ToastView.swift (one store per window). Dropping a folder or files onto the sidebar or a project row",
        "issue": (
            "<p><b>Four call sites, no kind, no action, a fixed 3 s hold.</b> Two are drag-import copy "
            "failures (<code>ContentView.swift:2657, :2878</code>); two are the feedback “sent” message. "
            "It draws over the whole window; the web toast draws only inside the report. The duration "
            "<i>is</i> a parameter, so a longer hold on those failures is a one-line change at the call sites.</p>"
            "<p>The owner’s argument: the researcher should meet one toast, whichever side raised the event, "
            "so a native event asks the page to draw it. The price is SF Symbols and system tints, which "
            "the web view cannot draw anyway. One caveat: a window with no web view (the alpha-expiry "
            "window, possibly the welcome screen) has no page to draw into. <code>dropProjectOntoProjectToast</code> "
            "has no Swift caller: probably dead.</p>"
        ),
        "dec": [
            dec("leaning", "One look everywhere: a native look-alike toast, parked as a follow-up (doc §9); replaces routing native events through the page"),
            dec("abandoned", "Extending ToastView.swift to match the web behaviours (a Swift twin)"),
            dec("abandoned", "Moving the drag failures to dialogs: small failures, annoying dialogs"),
            dec("open", "What a window with no web view does"),
        ],
        "rows": [
            sc("Copy refused: disk full", old_toast("Not enough disk space", meta="ToastStore.show · 3 s · no kind", mac=True), toast("Not enough disk space", "error", held=True, meta="drawn by the page; hold set per failure"), ""),
            sc("Dropped items are not importable", old_toast("None of the dropped items is a file Bristlenose can import.", mac=True), toast("None of the dropped items is a file Bristlenose can import.", "error", held=True), ""),
            sc("A copy is already running", old_toast("Another copy is already in flight.", mac=True), toast("Another copy is already in flight.", "error", held=True), ""),
            sc("Part of the drop is in iCloud, not downloaded", old_toast("Nothing was copied: part of this drop isn’t downloaded to this Mac.", mac=True), toast("Nothing was copied: part of this drop isn’t downloaded to this Mac.", "error", held=True), ""),
            sc("Anything else (the system’s own error text)", old_toast("(the system’s localised error description)", mac=True), toast("(the system’s localised error description)", "error", held=True), ""),
        ],
    },
]

# The decision trail: everything decided or ruled out across the review, in the order it
# was reached. Status words are this page's own vocabulary (see the module docstring).
TRAIL = [
    ("decided", "Where the SPA is the product, the toast system is worth doing well", "Owner, 10 Nov. It owns concurrency, timing, pause and dismissal so no call site does."),
    ("decided", "Kind glyphs in the web view are Lucide shapes in the palette colours", "SF Symbols are for native chrome only: Apple’s terms scope them to apps drawing their own UI, and the project’s own rule (`design-icon-system.md`) says the same. Owner: “can live with that.” The shapes match the Mac’s symbols (circle-check, info, triangle-alert, circle-x)."),
    ("decided", "A toast takes four of the five kinds; `skipped` folds into info", "Owner, 10 Nov. The taxonomy keeps all five for the CLI and the Mac popover."),
    ("decided", "Title and body anatomy, for toast and chip", "Title in the emphasis weight, body regular and quieter; a one-sentence message has no title; titles carry no full stop. The cut is at an existing full stop, so it costs two locale keys, not new copy."),
    ("decided", "No em dash in toast copy", "Two short sentences, or a title and a body. Eleven values in the toast and chip set, one 21-locale pass."),
    ("decided", "The wording, type and glyph slice goes into the existing toast first", "Independent of the engine choice. Order: this mockup and the doc, owner approval, locale and wording pass, title/body and Lucide, then phases 2 and 3."),
    ("leaning", "One toast look the researcher ever sees, whichever side raised it", "Owner’s argument against leaving the Mac toast (UX mixture) and against dialogs (annoying for small failures). Revised the same day: a native look-alike, not a bridge route, because some native events have no web view."),
    ("parked", "A native look-alike of the web toast for the four Mac sites (follow-up, after phases 2 and 3)", "Owner idea, 10 Nov. Same look, minimal behaviour, SF Symbols for the icon, a shared JSON contract to stop the two drifting. Wins over the bridge route because some native events have no web view to draw into. Full account in `design-notification-surfaces.md` §9."),
    ("open", "Engine: adopt Sonner, or harden our own and borrow its tricks", "Decided by a test-first spike: write the behaviour spec as tests, run it against both. Deciding facts: one speech path, size in the single-file export, works from outside React."),
    ("open", "How the toast and the activity chip share the bottom-right corner", "Both are fixed there (toast 90 px up, chips 48 px up). A stack that grows upward would collide with the chips. Touches the chip-docking decision in the routing doc."),
    ("open", "How long an error holds, and whether it waits to be dismissed", "“Not needy UX” and “failed things must be visible” pull in opposite directions (decision 4)."),
    ("open", "Mac app: suppress confirmations; Copy Screens success", "Decisions 1 and 6. Both need an owner yes before the page stops saying anything."),
    ("open", "Inline validation for a taken name; “Open Settings” as a new string", "New UX and a new locale key, both behind the R114 gate."),
    ("parked", "A browser or Linux “while away” notification", "Default no before launch; revisit if browser and Linux researchers report missing a finished run (decision 9)."),
    ("abandoned", "SF Symbols inside the web view", "Apple’s terms and our own rule. A private-use code point might render on a Mac, but the same bundle runs in browsers and the export, where it would show empty boxes. Not tested, and not wanted."),
    ("abandoned", "Extending `ToastView.swift` to match the web behaviours", "A second implementation of stacking, priority, pause and title/body kept in step by hand, for four call sites."),
    ("abandoned", "Moving the drag-import failures to dialogs", "Owner: small failures, annoying dialogs."),
    ("abandoned", "Promise toasts, swipe to dismiss, the expanding stack animation", "The chip is the progress surface; a desktop tool needs no swipe; the motion brief wants causal, proportional, interruptible."),
    ("decided", "The chip shows work as a shimmering label, not a ring or spinner", "That is the shipped chip (`atoms/activity-chip.css`: “replaces the old spinner”). The ring is native: `SidebarActivityRing` on a sidebar row. The first draft of this page drew an invented spinner; v2 now uses the real shimmer atom."),
    ("open", "Tokenise the toast and chip", "Today only font size, colour, radius, the right margin and the toast’s z-index come from tokens. Padding, offsets, gaps, shadow, durations and the chip’s inverted colours are literals; the toast and chip disagree on z-index (1100 token against a literal 200)."),
    ("abandoned", "The em dash as a separator", "Replaced by a full stop or a title and body."),
    ("abandoned", "A spinner ring on the chip (my first draft of v2)", "Invented; the shipped chip has none."),
    ("abandoned", "v1’s placeholder “(same sentence, once it exists)” in the Copy as CSV failure", "Not product copy. v2 draws the key and says the wording still has to be written."),
]


CSS = """
:root{color-scheme:light dark;
--bn-font-body:"Inter","Segoe UI Variable",system-ui,-apple-system,sans-serif;
--bn-font-mono:ui-monospace,Menlo,"Cascadia Mono",Consolas,"DejaVu Sans Mono",monospace;
--bn-text-badge:.72rem;--bn-text-caption:.75rem;--bn-text-label:.8125rem;--bn-text-body:.9375rem;
--bn-text-heading:1.125rem;--bn-text-title:1.375rem;
--bn-weight-normal:420;--bn-weight-emphasis:490;--bn-weight-strong:700;--bn-weight-mono:400;
--bn-space-xs:.15rem;--bn-space-sm:.35rem;--bn-space-md:.75rem;--bn-space-lg:1.5rem;--bn-space-xl:2rem;
--bn-radius-sm:3px;--bn-radius-md:6px;--bn-radius-lg:8px;--bn-radius-pill:999px;--bn-toast-z:1100;
--bn-shimmer-contrast:5%;--bn-shimmer-band:34%;--bn-shimmer-angle:100deg;--bn-shimmer-period:2700ms;--bn-shimmer-easing:ease-in-out}
:root,[data-color-theme="default"]{
--bn-colour-bg:light-dark(#ffffff,#111111);--bn-colour-text:light-dark(#1a1a1a,#e5e7eb);
--bn-colour-muted:light-dark(#6b7280,#9ca3af);--bn-colour-border:light-dark(#e5e7eb,#2d2d2d);
--bn-colour-accent:light-dark(#007aff,#0a84ff);--bn-colour-hover:light-dark(#e8f0fe,#1e293b);
--bn-colour-quote-bg:light-dark(#f9fafb,#1a1a1a);--bn-colour-badge-bg:light-dark(#f3f4f6,#252525);
--bn-colour-badge-text:light-dark(#374151,#d1d5db);--bn-off-track:light-dark(#c7ccd1,#3a3f45);
--bn-colour-negative:light-dark(#dc2626,#ef4444);--bn-colour-positive:light-dark(#16a34a,#22c55e);
--bn-colour-warning:light-dark(#f59e0b,#fbbf24)}
[data-color-theme="edo"]{
--bn-colour-bg:light-dark(#fdfbf7,#1a1816);--bn-colour-text:light-dark(#1b2230,#e8e3d6);
--bn-colour-muted:light-dark(#4a698a,#7ba8a0);--bn-colour-border:light-dark(#d4c9a8,#2d2820);
--bn-colour-accent:light-dark(#0f5c9e,#4d9fe0);--bn-colour-hover:light-dark(#ede5d1,#252118);
--bn-colour-quote-bg:light-dark(#f0e9d8,#211e18);--bn-colour-badge-bg:light-dark(#e8dfc9,#2d2820);
--bn-colour-badge-text:light-dark(#2d3654,#c4b898);--bn-off-track:light-dark(#c9bd9c,#4a4030);
--bn-colour-negative:light-dark(#b5432a,#e06a4a);--bn-colour-positive:light-dark(#4a6b4a,#7fa87f);
--bn-colour-warning:light-dark(#a8842c,#c4a96a)}
*{box-sizing:border-box}
body{margin:0;background:var(--bn-colour-bg);color:var(--bn-colour-text);font-family:var(--bn-font-body);
font-size:var(--bn-text-body);font-weight:var(--bn-weight-normal);line-height:1.45}
code{font-family:var(--bn-font-mono);font-size:.85em;font-weight:var(--bn-weight-mono)}
.bar{position:sticky;top:0;z-index:20;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;
padding:.5rem 1.25rem;background:var(--bn-colour-bg);border-bottom:1px solid var(--bn-colour-border);
font-size:var(--bn-text-caption);color:var(--bn-colour-muted)}
.bar button{font:inherit;color:var(--bn-colour-text);background:var(--bn-colour-badge-bg);border:1px solid var(--bn-colour-border);
border-radius:var(--bn-radius-md);padding:.2rem .6rem;cursor:pointer}
.bar button[aria-pressed="true"]{background:var(--bn-colour-accent);color:#fff;border-color:transparent}
main{padding:1.25rem;min-width:1180px;max-width:1700px;margin:0 auto}
h1{font-size:var(--bn-text-title);margin:.2rem 0 .3rem;font-weight:var(--bn-weight-strong)}
h2{font-size:var(--bn-text-heading);margin:2rem 0 .5rem;font-weight:var(--bn-weight-strong)}
.lede{color:var(--bn-colour-muted);max-width:75ch;margin:0 0 .8rem}
.key{display:flex;gap:1.2rem;flex-wrap:wrap;font-size:var(--bn-text-caption);color:var(--bn-colour-muted);margin-bottom:1rem}
.key i{display:inline-block;width:1.2rem;height:.8rem;vertical-align:middle;margin-right:.35rem;border-radius:2px}
.k-art{border:1px solid var(--bn-colour-border);background:var(--bn-colour-quote-bg)}
.k-com{background:repeating-linear-gradient(135deg,var(--bn-colour-border) 0 3px,transparent 3px 6px)}
table.main{width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed}
col.c1{width:29%}col.c2{width:38%}col.c3{width:33%}
table.main thead th{position:sticky;top:2.35rem;z-index:10;background:var(--bn-colour-bg);text-align:left;
padding:.5rem .7rem;font-size:var(--bn-text-caption);text-transform:uppercase;letter-spacing:.04em;
color:var(--bn-colour-muted);border-bottom:2px solid var(--bn-colour-border)}
tr.gh th{padding:1.5rem .7rem .4rem;text-align:left;font-size:var(--bn-text-heading);
font-weight:var(--bn-weight-strong);border-bottom:1px solid var(--bn-colour-border);background:transparent}
tr.gh th small{display:block;margin-top:.15rem;font-size:var(--bn-text-caption);font-weight:var(--bn-weight-normal);
color:var(--bn-colour-muted);font-family:var(--bn-font-mono)}
td{vertical-align:top;padding:.55rem .7rem;border-bottom:1px solid var(--bn-colour-border)}
td.art{background:var(--bn-colour-quote-bg)}
td.com{padding:.5rem}
.commentary{border:7px solid transparent;border-left:3px solid var(--bn-colour-muted);
background:linear-gradient(var(--bn-colour-bg),var(--bn-colour-bg)) padding-box,
repeating-linear-gradient(135deg,var(--bn-colour-border) 0 5px,transparent 5px 10px) border-box;
padding:.5rem .7rem;font-size:var(--bn-text-label)}
.commentary p{margin:.1rem 0 .6rem}
.lab{font-family:var(--bn-font-mono);font-size:var(--bn-text-badge);color:var(--bn-colour-muted);text-transform:uppercase;margin-bottom:.3rem}
.decs{list-style:none;margin:.5rem 0 .1rem;padding:.4rem 0 0;border-top:1px solid var(--bn-colour-border)}
.decs li{display:flex;gap:.5rem;align-items:baseline;margin:.25rem 0;font-size:var(--bn-text-caption)}
.st{flex:none;font-family:var(--bn-font-mono);font-size:.62rem;text-transform:uppercase;letter-spacing:.03em;
padding:.05rem .4rem;border-radius:var(--bn-radius-pill);border:1px solid currentColor}
.st-decided{color:var(--bn-colour-positive)}.st-leaning{color:var(--bn-colour-accent)}
.st-open{color:var(--bn-colour-warning)}.st-parked{color:var(--bn-colour-muted)}
.st-abandoned{color:var(--bn-colour-negative);text-decoration:none}
.trig{font-family:var(--bn-font-mono);font-size:var(--bn-text-badge);color:var(--bn-colour-muted);margin:0 0 .3rem}
.trig b{color:var(--bn-colour-text);font-weight:var(--bn-weight-emphasis)}
.meta{font-family:var(--bn-font-mono);font-size:.66rem;color:var(--bn-colour-muted);margin:.25rem 0 0}
.meta.warn{color:var(--bn-colour-warning)}
.sp{height:.55rem}
.toast{display:flex;gap:.55rem;align-items:flex-start;width:fit-content;max-width:100%;background:var(--bn-colour-text);
color:var(--bn-colour-bg);padding:.6rem 1.2rem;border-radius:var(--bn-radius-lg);font-size:var(--bn-text-label);
box-shadow:0 2px 10px var(--bn-colour-border)}
.toast.old{display:inline-block}
.toast.old.has-kind{display:flex;gap:.45rem;align-items:baseline}
.toast.mac{border-radius:var(--bn-radius-pill);padding:.5rem 1.1rem}
.toast code{font-size:.8rem}
.glyph{font-weight:var(--bn-weight-strong);flex-shrink:0}
.glyph-success{color:var(--bn-colour-positive)}.glyph-error{color:var(--bn-colour-negative)}
.glyph-warning{color:var(--bn-colour-warning)}.glyph-info{color:var(--bn-colour-accent)}
.ico{flex:none;width:1.1em;height:1.1em;margin-top:.12em;stroke-width:1.5px;vector-effect:non-scaling-stroke}
.ico *{vector-effect:non-scaling-stroke}
.ico-success{color:var(--bn-colour-positive)}.ico-error{color:var(--bn-colour-negative)}
.ico-warning{color:var(--bn-colour-warning)}.ico-info{color:var(--bn-colour-accent)}
.t-title{font-weight:var(--bn-weight-emphasis)}
.t-body{opacity:.78}
.t-body.solo{opacity:1}
.t-title+.t-body{margin-top:.1rem}
.toast-action{margin-left:.7rem;font-weight:var(--bn-weight-emphasis);color:var(--bn-colour-accent);white-space:nowrap;align-self:center}
.silent{display:inline-block;padding:.5rem 1rem;border:1px dashed var(--bn-colour-muted);border-radius:var(--bn-radius-lg);
color:var(--bn-colour-muted);font-size:var(--bn-text-label)}
.menu{display:inline-block;min-width:11rem;padding:.25rem;border:1px solid var(--bn-colour-border);border-radius:var(--bn-radius-lg);
background:var(--bn-colour-bg);box-shadow:0 4px 14px var(--bn-colour-border)}
.menu-row{padding:.25rem .7rem;border-radius:var(--bn-radius-sm);font-size:var(--bn-text-label)}
.menu-row.off{color:var(--bn-colour-muted);opacity:.65}
.btn-off{font:inherit;font-size:var(--bn-text-label);padding:.3rem .8rem;border-radius:var(--bn-radius-md);
border:1px solid var(--bn-colour-border);background:var(--bn-colour-badge-bg);color:var(--bn-colour-muted);opacity:.7}
.field{max-width:30rem}
.field .input{border:1px solid var(--bn-colour-negative);border-radius:var(--bn-radius-md);background:var(--bn-colour-bg);
padding:.3rem .6rem;font-size:var(--bn-text-label)}
.field-err{display:flex;gap:.35rem;align-items:flex-start;margin-top:.3rem;font-size:var(--bn-text-caption);color:var(--bn-colour-negative)}
.chip{display:flex;gap:.6rem;align-items:flex-start;width:fit-content;max-width:100%;background:var(--bn-colour-text);
color:var(--bn-colour-bg);padding:.6rem 1rem;border-radius:var(--bn-radius-lg);font-size:var(--bn-text-label);
box-shadow:0 4px 20px rgba(0,0,0,.25)}
.chip .t-body+.t-body{margin-top:.2rem}
/* ════ bristlenose/theme/atoms/shimmer.css (text shimmer) and atoms/activity-chip.css .chip-label ════ */
.bn-thinking-shimmer{--_shimmer-base:var(--bn-shimmer-base,currentColor);
--_shimmer-peak:color-mix(in srgb,var(--_shimmer-base),var(--bn-shimmer-peak,#fff) var(--bn-shimmer-contrast))}
@media (prefers-reduced-motion:no-preference){:root:not([data-analysis-animation="off"]) .bn-thinking-shimmer{
background-image:linear-gradient(var(--bn-shimmer-angle),var(--_shimmer-base) 0%,var(--_shimmer-base) calc(50% - var(--bn-shimmer-band) / 6),var(--_shimmer-peak) 50%,var(--_shimmer-base) calc(50% + var(--bn-shimmer-band) / 6),var(--_shimmer-base) 100%);
background-size:300% 100%;background-repeat:no-repeat;-webkit-background-clip:text;background-clip:text;
-webkit-text-fill-color:transparent;color:transparent;animation:bn-thinking-shimmer var(--bn-shimmer-period) var(--bn-shimmer-easing) infinite}}
@keyframes bn-thinking-shimmer{0%{background-position:100% 50%}66.67%{background-position:0% 50%}100%{background-position:0% 50%}}
.chip-label{--bn-shimmer-base:var(--bn-colour-bg);--bn-shimmer-peak:var(--bn-colour-text);--bn-shimmer-contrast:20%}
.tag{font-family:var(--bn-font-mono);font-size:var(--bn-text-badge);background:var(--bn-colour-badge-bg);
color:var(--bn-colour-badge-text);padding:0 .35rem;border-radius:var(--bn-radius-sm)}
.spec{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;padding:1rem;background:var(--bn-colour-quote-bg);
border:1px solid var(--bn-colour-border)}
.spec .cell{display:flex;flex-direction:column;gap:.35rem;align-items:flex-start}
.dock{position:relative;height:15rem;border:1px solid var(--bn-colour-border);border-radius:var(--bn-radius-lg);
background:var(--bn-colour-bg);overflow:hidden}
.dock .win-bar{height:1.6rem;border-bottom:1px solid var(--bn-colour-border);background:var(--bn-colour-badge-bg)}
.dock .corner{position:absolute;right:1rem;bottom:1rem;display:flex;flex-direction:column;gap:.4rem;align-items:flex-end}
table.trail{width:100%;border-collapse:collapse;font-size:var(--bn-text-label)}
table.trail th{text-align:left;font-size:var(--bn-text-caption);text-transform:uppercase;letter-spacing:.04em;
color:var(--bn-colour-muted);padding:.4rem .6rem;border-bottom:2px solid var(--bn-colour-border)}
table.trail td{padding:.5rem .6rem;border-bottom:1px solid var(--bn-colour-border);vertical-align:top}
table.trail td:first-child{width:7rem;white-space:nowrap}
table.trail td:nth-child(2){width:30%;font-weight:var(--bn-weight-emphasis)}
footer{margin:2rem 0 3rem;color:var(--bn-colour-muted);font-size:var(--bn-text-caption);max-width:80ch}
"""

JS = """
(function(){
var root=document.documentElement;
function set(attr,val,group){root.setAttribute(attr,val);
 document.querySelectorAll('[data-g="'+group+'"]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.v===val))})}
document.querySelectorAll('[data-g="pal"]').forEach(function(b){b.onclick=function(){set('data-color-theme',b.dataset.v,'pal')}});
document.querySelectorAll('[data-g="sch"]').forEach(function(b){b.onclick=function(){
 root.style.colorScheme=b.dataset.v==='auto'?'light dark':b.dataset.v;
 document.querySelectorAll('[data-g="sch"]').forEach(function(x){x.setAttribute('aria-pressed',String(x===b))})}});
})();
"""


def status_chip(status):
    return '<span class="st st-' + status + '">' + STATUS[status] + "</span>"


def specimen():
    kinds = [
        ("success", "Feedback sent", "Thank you!"),
        ("info", "Already applied.", None),
        ("warning", "No quotes yet", "Analyse your sessions first."),
        ("error", "Couldn’t save your change", "Check your connection."),
    ]
    cells = ""
    for kind, a, b in kinds:
        if b:
            t = toast(b, kind, title=a)
        else:
            t = toast(a, kind)
        cells += '<div class="cell"><div class="trig"><b>' + kind + "</b></div>" + t + "</div>"
    return '<div class="spec">' + cells + "</div>"


def dock():
    stack = (
        toast("Check your connection.", "error", title="Couldn’t save your change", held=True)
        + toast("Clip extraction failed", "error")
        + chip("Extracting clips… (3 of 12)", ["This FFmpeg can’t burn in subtitles. Extracting plain clips only."])
    )
    return (
        '<div class="dock"><div class="win-bar"></div><div class="corner">'
        + stack.replace('<div class="meta">', '<div class="meta" hidden>')
        + "</div></div>"
    )


def build():
    rows = []
    for g in GROUPS:
        rows.append(
            '<tr class="gh"><th colspan="3">' + e(g["id"]) + ". " + e(g["title"])
            + "<small>" + e(g["where"]) + "</small></th></tr>"
        )
        for i, s in enumerate(g["rows"]):
            cells = (
                '<td class="art"><p class="trig"><b>' + e(s["trig"]) + "</b>"
                + ((" " + tag(s["ref"])) if s["ref"] else "") + "</p>" + s["left"] + "</td>"
            )
            if i == 0:
                decs = "".join(
                    "<li>" + status_chip(st) + "<span>" + e(tx) + "</span></li>" for st, tx in g["dec"]
                )
                cells += (
                    '<td class="com" rowspan="' + str(len(g["rows"])) + '"><div class="commentary">'
                    '<div class="lab">Commentary</div>' + g["issue"]
                    + '<ul class="decs">' + decs + "</ul></div></td>"
                )
            cells += '<td class="art">' + s["right"] + "</td>"
            rows.append("<tr>" + cells + "</tr>")
    trail = "".join(
        "<tr><td>" + status_chip(st) + "</td><td>" + e(what) + "</td><td>" + e(why) + "</td></tr>"
        for st, what, why in TRAIL
    )
    page = (
        '<!DOCTYPE html>\n<html lang="en" data-color-theme="default">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>Toast audit v2: decisions · Bristlenose mockups</title>\n<style>" + CSS + "</style>\n</head>\n<body>\n"
        '<div class="bar"><span>Palette</span>'
        '<button data-g="pal" data-v="default" aria-pressed="true">Default</button>'
        '<button data-g="pal" data-v="edo" aria-pressed="false">Edo</button>'
        "<span>Scheme</span>"
        '<button data-g="sch" data-v="auto" aria-pressed="true">Auto</button>'
        '<button data-g="sch" data-v="light" aria-pressed="false">Light</button>'
        '<button data-g="sch" data-v="dark" aria-pressed="false">Dark</button></div>\n'
        "<main>\n<h1>Every toast, and what it becomes: v2</h1>\n"
        '<p class="lede">v2 of the audit (10 Nov 2026; <a href="toast-audit-v1.html">v1</a> kept as the trail). '
        "Left: today, exact wording. Centre: the issue, and the status of each decision. Right: the outcome "
        "with the review’s decisions drawn in. Source: <code>docs/design-notification-surfaces.md</code>. "
        "Nothing is built; anything that suppresses a message or adds a control still needs the R114 gate.</p>\n"
        '<div class="key"><span><i class="k-art"></i>Artefact: what is drawn (the small mono lines are mockup chrome)</span>'
        '<span><i class="k-com"></i>Commentary: reasons, not pixels</span>'
        "<span>“held” = longer hold for errors, pauses on hover</span>"
        "<span>Dashed box = message deleted, VoiceOver still hears it</span></div>\n"
        '<div class="key"><span>Status:</span>'
        "<span>" + status_chip("decided") + " owner has ruled</span>"
        "<span>" + status_chip("leaning") + " argued for, not confirmed</span>"
        "<span>" + status_chip("open") + " still thinking</span>"
        "<span>" + status_chip("parked") + " not before launch</span>"
        "<span>" + status_chip("abandoned") + " ruled out, with the reason</span></div>\n"
        "<h2>The anatomy, by kind</h2>\n"
        '<p class="lede">Lucide shapes in the palette colours (the Mac’s SF Symbols have the same shapes). '
        "Title in the emphasis weight, body regular and quieter. A one-sentence message has no title.</p>\n"
        + specimen() +
        "\n<h2>Toasts and the activity chip share the corner</h2>\n"
        '<p class="lede">The open question: both are fixed bottom-right today (toast 90 px up, chips 48 px up). '
        "This is how a stack of two toasts above a chip would read as one family. The collision is still unsolved.</p>\n"
        + dock() +
        '\n<table class="main"><colgroup><col class="c1"><col class="c2"><col class="c3"></colgroup>\n'
        "<thead><tr><th>Today: scenario and exact wording</th><th>Issue, thinking, decisions</th>"
        "<th>New outcome</th></tr></thead>\n<tbody>\n" + "\n".join(rows) + "\n</tbody></table>\n"
        "<h2>Decision trail</h2>\n"
        '<p class="lede">Everything decided, still open, parked or ruled out in this review, with the reason. '
        "The status words are new with this page: no earlier mockup had a trail format.</p>\n"
        '<table class="trail"><thead><tr><th>Status</th><th>Decision</th><th>Why</th></tr></thead><tbody>'
        + trail + "</tbody></table>\n"
        "<footer>Wording is the English locale value or the literal in the source, copied not retyped; the "
        "right column is the proposed copy. Counts like “47” and the name “Sam” are example values. Glyph "
        "colours are the shipped semantic tokens. Icons are Lucide paths drawn inline.</footer>\n"
        "</main>\n<script>" + JS + "</script>\n</body>\n</html>\n"
    )
    OUT.write_text(page, encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    print("rows:", build())
