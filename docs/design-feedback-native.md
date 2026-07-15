# Feedback — native, rich, ethical (long-term design)

**Status:** Aspirational / roadmap. What ships today is the *simplest possible*
example: a rating + free-text form (native `FeedbackSheet` in the Mac app; React
`FeedbackModal` in the browser; a status-page web form for the SPA-down case).
This doc is the target the native feedback experience grows toward. It is
Swift-first: the rich version lives in the Mac app, where we have native capture
and on-device processing; the web keeps the simple form.

Related: `docs/design-footer-feedback-react.md` (the web form as shipped),
`docs/methodology/consent-gradient.md` (the Level 0–3 data-governance gradient
this feature must exemplify), `docs/methodology/tag-rejections-are-great.md`
(the rejection/telemetry corpus a couple of attachments draw from).

---

## Why this feature matters more than most

Bristlenose is a user-research tool. Our feedback channel is not plumbing — it
is a **reference implementation of listening well and ethically**. Every choice
here should be one we'd be proud to show a researcher as best practice:
data-minimal by default, additive-opt-in, on-device processing, nothing leaves
without a preview, and a receipt afterward. "We practice what we preach" is the
whole point.

Corollary: the *simplest* form (rating + text) is the floor, not the ceiling. In
the Mac app we can do much better than a web modal, so we should.

---

## Two settled principles (near-term, act on these first)

1. **Native app → native UI, in every state.** The web modal was the best we
   could do *in a browser*. In the Mac app the native sheet is better and does
   not depend on the SPA (it reads config from `/api/health`), so the app should
   use it **everywhere — normal and degraded** — never fall back to the web
   modal. (Drop the probe-then-route; Help → Send Feedback always opens native.
   The web modal becomes browser-only.)
2. **Not a modal.** Same reason the docs aren't a modal: **you have to look at
   the thing you're giving feedback on.** A blocking sheet hides the analysis
   you're commenting on. Target form factor is a **non-modal companion surface**
   — a right-side inspector panel or a detachable, non-activating palette that
   sits *beside* the content and stays open while you point at things. (The
   shipped v1 sheet is an interim compromise; the target is non-modal.)

---

## The capture menu — optional context, each with its consent treatment

Everything below the rating is **additive and opt-in**, never pre-checked, and
always shown in a review-before-send manifest (below). Ordered roughly by value.

| Attachment | What it is | On-device treatment before it can be sent | Consent-gradient level |
|---|---|---|---|
| **Rating** | 5-point affect | none needed | L0 (anonymous, non-identifying) |
| **Free text** | what's useful / what's broken | **Anonymise ("fuzzy-greek")** — entity scrub (Presidio) + optional lorem/greek fill that keeps length + shape but drops the words; live preview of the redacted version | L1 raw / L2 if it may carry participant content |
| **Voice note** | dictate feedback aloud | transcribe **on-device via the bundled Whisper** (dogfood our own transcription); user edits the transcript; audio attaches only if they opt in | L2 (voice is identifying) |
| **Dictation** | speak straight into the box | on-device speech→text; same scrub as free text | L1/L2 |
| **Screenshot of your analysis** | "this feature isn't working" with the thing in frame | **auto-redact quote/transcript text regions** (detected via the DOM / accessibility tree) to fuzzy-greek; annotate (draw/highlight the broken bit); preview the redacted image | L2 |
| **Screen recording / think-aloud** | record yourself using the system and thinking aloud | region-redaction pass; user scrubs/trims; opt-in | L2/L3 |
| **Contextual artifact** | "feedback about *this* quote / tag / theme / session" | attaches the element's id + minimal context, redacted; deep-linked | L1 |
| **Anonymised analysis analytics** | e.g. how often an autotag fires across your corpus; tag **rejection** rates; signal distributions | aggregate rates only, computed on-device — never the underlying quotes; ties into the rejection-telemetry corpus | L1 (aggregate) |
| **Usage metrics** | which features used, session shape | aggregate, opt-in, no content | L1 |
| **Diagnostics** | version, provider/model, sandbox state, `doctor` snapshot, redacted error tail | auto-offered on a *bug* report; secrets/keys redacted (reuse `redactKeys`) | L0/L1 |
| **Reproduction state** | the minimal state to reproduce a bug | heavy scrub + explicit preview; opt-in of last resort | L2/L3 |

**Fuzzy-greek, precisely:** replace real words (and quote text inside
screenshots) with greek/lorem filler that preserves length, line-count, and
layout, so the team sees the *shape* of the feedback — where, how much, which UI
— without the actual content. Combined with Presidio entity-redaction for names.
The researcher sees exactly the fuzzed artifact before it can leave. This is the
single most on-brand feature in the doc: a UR tool that lets you redact your own
data before you share it, and *see* the redaction.

---

## The transparency gate — "nothing leaves without you seeing it"

A **review-before-send manifest** is mandatory: a plain-language list of exactly
what will be transmitted, each line human-readable ("your rating", "your message
— redacted", "1 screenshot — quote text blurred", "autotag rates — aggregate,
no quotes"). The payload is assembled **on-device**; the user reviews the literal
thing; only then does Send fire. No attachment is ever implicit.

Afterward: a **local receipt / feedback history** — the user keeps a record of
what they sent and when. Reversibility and recall are part of ethical listening.

---

## Ideation — ways this could go mega (beyond the starting list)

- **Contextual entry points.** Right-click a quote / tag / theme / failed
  session → "Send feedback about this." The panel opens anchored to it with that
  context pre-attached and pre-redacted. Feedback where the friction is.
- **Experience-sampling "friction marker".** A global shortcut / toolbar tap:
  "this frustrated me *right now*" — timestamped, one gesture, elaborate later.
  Critical-incident / diary-study technique built into the product. The richest
  UR signal is captured at the moment of friction, not reconstructed afterward.
- **Dogfood the whole pipeline.** Think-aloud feedback recordings are just
  interviews about Bristlenose — run them through Bristlenose (transcribe →
  quotes → themes about our own UX). Our roadmap becomes a Bristlenose report.
- **Severity/category quick-tags** (bug · idea · confusion · praise) to route and
  triage feedback without a form.
- **Side-by-side redact preview** — raw vs fuzzed, so the user trusts the scrub.
- **Optional contact-back** — leave an email for follow-up; opt-in, explicitly
  breaks anonymity by the user's choice (and says so).
- **Offline drafts** — compose over time, review, send when ready (the web form
  already persists a draft; extend to attachments).
- **Two-way (far future)** — a lightweight reply thread so feedback feels heard,
  not shouted into a void. Scope carefully; may be out of band.

---

## Architecture (Swift-first)

The Mac app is where the rich version lives, because the good primitives are
native:

- **Capture:** ScreenCaptureKit (screenshot / screen recording), AVFoundation
  (audio), the bundled **Whisper** (voice→text on-device), the DOM/AX tree from
  the WKWebView (to locate quote-text regions for screenshot redaction).
- **Redaction on-device:** Presidio (already a dep) for entities; a "fuzzy-greek"
  transform for shape-preserving text/image blur; `redactKeys` for secrets.
- **Assembly + consent:** payload built locally; the review manifest is a native
  view; Send is the only egress.
- **Form factor:** a non-modal inspector/palette (Bristlenose already has
  inspector infrastructure — `InspectorPanel`, the Tag inspector over
  BroadcastChannel — reuse the pattern rather than a fresh window).
- **Web stays simple:** the browser keeps the rating + text form (redaction and
  capture there are limited; don't try to port the native rig).

**Transport:** extend the `feedback.php` contract to a structured, versioned
payload; attachments upload separately and only when opted in. Keep the
re-identification-key discipline absolute — nothing that assembles the payload
may read `pii_summary.txt` / `llm-calls.jsonl` / `pipeline-events.jsonl`, and no
project/session identifiers ride along unless the user explicitly attaches a
contextual artifact.

---

## Consent-gradient alignment (the ethical spine)

Map every attachment to the gradient in `docs/methodology/consent-gradient.md`
and honour its gates — this feature must not become the hole in our own fence:

- **L0** (anonymous rating, diagnostics-without-content) — the default, no gate.
- **L1** (aggregate rates, usage shape, redacted text) — opt-in, preview.
- **L2** (free text that may carry participant content, screenshots, voice) —
  on-device scrub + preview + per-item opt-in; this is exactly the Level-2
  free-text scrub the gradient requires, applied *here first* as the showcase.
- **L3** (recordings, reproduction state) — heaviest scrub, most explicit
  consent, last resort.

No dark patterns: nothing pre-checked, plain-language labels, data-minimal by
default, reversible, receipted.

---

## Phasing (Swift-first)

- **v1 (shipped):** rating + text. Native sheet (app) / React modal (browser) /
  status-page form (browser degraded).
- **Phase 0 (shipped, 15 Jul 2026):** the Mac app is now **always native** —
  `BridgeHandler.openFeedback()` unconditionally posts `.showFeedbackSheet` (the
  probe-then-route that handed off to the web modal when the SPA was up is gone).
  The web `FeedbackModal` is browser-only; the report lens no longer shows it.
- **Phase 1:** move the native surface from sheet → **non-modal companion panel**
  (see the thing you're commenting on). Add anonymise / fuzzy-greek + preview to
  the text field. Ship the review-before-send manifest.
- **Phase 2:** voice note (on-device Whisper) + dictation.
- **Phase 3:** annotated screenshot with auto-redaction; contextual entry points.
- **Phase 4:** anonymised analytics (autotag / rejection rates), usage metrics,
  diagnostics auto-attach.
- **Phase 5:** screen recording / think-aloud; experience-sampling friction
  marker; dogfood-the-pipeline.

Each phase is independently shippable and independently valuable. Every phase
adds *only* opt-in surface — the floor stays "rating + text, anonymous."

---

## Open questions

- Endpoint: extend `feedback.php` vs a new richer ingest for attachments? (SBOM /
  storage / retention implications — battle-tested-human territory.)
- Retention + deletion story for anything received (we should be able to say how
  long we keep feedback and how a user revokes it — consistent with the ethics).
- How much of the redaction is trustworthy enough to *promise*? (Presidio recall
  isn't 100%; the preview is the honest backstop — the user is the final gate.)
- Non-modal panel vs detachable window on macOS — which reads most native for a
  "companion to the content" surface (this is the *inspector/palette* case,
  where a non-activating panel is legitimate — unlike the committed-data-entry
  sheet, where it wasn't).
