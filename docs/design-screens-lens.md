---
status: proposal
updated: 13 Oct 2026
---

# Screens lens

> **Part of one project, 13 Oct 2026.** The Screens lens and screen text are planned together in
> [`design-screens.md`](design-screens.md), which owns the UX (this lens is its surface S5),
> architecture, privacy model and phases (Mac first, engine pluggable). This doc is the **evidence
> record** for deriving screens; where its §9 or §10 disagree with the plan, the plan wins.

**Status: exploratory proposal, 13 Oct 2026. Nothing here is built and nothing is decided; the owner
decides whether it is.** It builds on the screen-text proposal
([`design-screen-text-search.md`](design-screen-text-search.md)), which is also unbuilt: this lens
needs that index and adds almost no cost on top of it. Method and every number:
[`experiments/screens-lens/README.md`](../experiments/screens-lens/README.md). Prior-art survey with
citations: [`experiments/screens-lens/prior-art.md`](../experiments/screens-lens/prior-art.md).
Mockup: [`docs/mockups/screens-lens.html`](mockups/screens-lens.html).
Speculative series, eleven further ideas each marked grounded, plausible or speculative:
[`docs/mockups/screens-lens-speculative.html`](mockups/screens-lens-speculative.html).

## 1. The idea

The owner's words, 13 Oct 2026: *a new lens called "Screens" — a grid or maybe a tree — based on link
clicks implied by sequence — of all the screens in order typically visited; click on a screen and see
all the quotes from all the users, sidebar of the tags.*

The job it does for a researcher: **"what happened on the delivery page?"** answered across every
participant at once, with the evidence (what they said there, what they tagged, how it felt), and the
route people took to get there. Today that question is answered by the report's sections, which are
inferred from what people *said*. This lens answers it from what was *on screen*.

## 2. What already exists, and the overlap that matters

**The pipeline already infers screens, from speech.** Topic segmentation marks `screen_change`
boundaries in the transcript (`llm/prompts/topic-segmentation.md`), and quote clustering groups
screen-specific quotes into **screen clusters** ordered "in the logical flow of the product"
(`llm/prompts/quote-clustering.md`, `screen_clusters.json`). Those clusters are the report's
**sections**: the Quotes lens's "Sections" grouping and the Signals heatmap's rows. So Bristlenose has
had a screens model all along; it is a guess from the transcript.

What is new here is an **observed** screens model, read off the shared screen. The two can be
compared, and on the two real sessions they mostly agree and sometimes do not (§4.5). That is the most
useful thing this lens can do that nothing else can: show where the transcript's story of the session
and the screen's story diverge.

## 3. Prior art, in brief

Full survey, 4 research strands and ~60 sources:
[`prior-art.md`](../experiments/screens-lens/prior-art.md). The findings that shape this design:

- **Nobody does this.** No shipped product or published paper was found that infers screens from a
  third-party screen-share recording and files participants' quotes under them. Every tool that shows
  findings per screen owns the stimulus: Maze imports a Figma prototype; UserTesting's Interactive
  Path Flows (2020, the closest analogue: screens as nodes with thumbnails, each step linked to its
  video) need Chrome and record navigation; Contentsquare, FullStory and Hotjar inject a tag. Tools
  that take any recording (Dovetail, Condens, dscout) read only the transcript. Zoom ships "Use screen
  share content with OCR", for meeting summaries, not a screen index.
- **"Same screen" is a granularity decision, not a threshold.** Of 275 near-duplicate web states, 219
  were "same template, different data"; the best of ten detectors scored F1 0.60, and thresholds lost
  ~15% on apps they were not tuned on (Yandrapally, Stocco & Mesbah, ICSE 2020). One app went from 5
  to 55 screens by changing the definition (Baek & Bae, ASE 2016). Rico calls it a product decision.
- **The closest recipe is task mining.** UiPath's patent US11507772B2 clusters OCR'd screenshots by
  words that recur at the same place (box IoU > 0.9, present in > 70% of a cluster), turns varying
  values into placeholders, and links screens by rare words carried across. It was built for Citrix
  screenshots, the same pixels-only position as a call recording. UiPath's product lets users rename
  and discard the steps it finds.
- **Image hashes are weak screen keys.** On mobile UI, whole-frame aHash/pHash/dHash found the right
  screen 39–51% of the time; SSIM + ORB 85% (GIFdroid, ICSE 2022). OCR text alone: F1 0.65 for
  same-state pairs (one 2026 measurement).
- **Flow charts mislead at n = 5–12.** Analytics Sankeys show the top 3–5 nodes per step plus
  "Other", which at this size hides whole people. Directly-follows graphs invent loops whenever
  ordering is flexible and stop adding up once edges are pruned (van der Aalst 2019). What transfers:
  collapse consecutive repeats but keep revisits (every vendor's default), count *participants* not
  events, pair any diagram with each person's whole path, and compare against an expected path
  (Maze's direct/indirect, Treejack's pietree and directness, Smith's lostness).
- **Quotes are the missing half of path analysis.** A revisit or a high lostness score cannot tell
  "lost" from "exploring" (Smith's own follow-up). What the participant said on the screen can. That
  is the part instrumented tools cannot supply.

The survey's one recommendation this design **rejects**: using a vision-language model to name screen
clusters or judge merges. That would send participants' screens to a cloud model, which the
screen-text proposal rules out (§7).

## 4. What the measurements say

Two real sessions (38 min German, 18 min UK; both IKEA shopping tasks shared over Teams at 1080p,
browser shares), the screen-text spike's dense OCR (Apple Vision every 2 s), hand labels written by
looking at contact sheets of every visit. Directionally firm, not a benchmark: one labeller, two
sessions, one site, one call app, browser shares only.

### 4.1 The address bar is readable, and it is the best screen key

| | German session | UK session |
|---|---|---|
| share frames with an address-bar URL read | 638 of 649 (98%) | 326 of 330 (99%) |
| visits (runs of frames whose text stays within Jaccard 0.6) | 91, median 6 s | 73, median 2 s |
| pages by hand label | 9 | 11 |
| states by hand label (page + dialog, panel or drop-down) | 21 | 17 |

**Is this visit the same page as that one?** Every pair of visits in a session, against the hand
labels. Clustering is average-linkage at the best threshold; ARI is the adjusted Rand index (1 = the
labels exactly).

| signal | AUC (DE / UK) | best F1 | clusters (9 / 11 true) | ARI |
|---|---|---|---|---|
| **address-bar URL, else text** | **0.98 / 0.97** | **0.98 / 0.95** | **11 / 12** | **0.98 / 0.96** |
| address-bar URL (path + #route) | 0.98 / 0.97 | 0.98 / 0.91 | 14 / 14 | 0.97 / 0.90 |
| TF-IDF over the visit's words | 0.90 / 0.89 | 0.72 / 0.73 | 11 / 18 | 0.86 / 0.76 |
| token-set Jaccard | 0.91 / 0.90 | 0.78 / 0.76 | 13 / 19 | 0.77 / 0.77 |
| line-set Jaccard | 0.88 / 0.89 | 0.77 / 0.75 | 15 / 19 | 0.81 / 0.72 |
| dHash of the share area | 0.83 / 0.89 | 0.66 / 0.71 | 29 / 23 | 0.62 / 0.71 |
| tallest line ("heading") equal | 0.61 / 0.63 | 0.37 / 0.40 | 45 / 39 | 0.33 / 0.35 |

- **URL first, text second.** When the address bar is visible the URL is close to exact; its misses
  were visits where no URL was read, a page whose URL changed before its content did, and a
  half-typed URL. Text
  fallback is usable (ARI 0.76–0.86) and is all there is for a window share, an app, or a prototype
  presented full screen. dHash and headings are weak, matching the literature.
- **The URL needs three rules.** Read only a line that is wholly a URL (Safari's bookmark bar has a
  "Bookfeed.io – …" title that otherwise reads as an address); drop the query string (personal data
  and noise); keep the `#route` fragment, because a single-page app's screens live there (the German
  session's planner was one path for 13 minutes; `#/planner` and `#/summary` split it correctly).
- **The screen-text chrome filter removes the URL.** Word-at-position stickiness treats the address
  bar as chrome. The URL must be read before that filter runs, and kept apart from searchable text.

### 4.2 States within a page did not separate

Dialogs, panels and drop-downs (the cookie banner, a store picker, "Choose how you'd like to check
out", a date picker) are what a researcher most wants to see as their own screens. **No visit-level
signal separated them** (AUC 0.45–0.69 on same-page pairs). Two targeted attempts:

- TF-IDF computed within each page, so the page's own text weighs nothing: ARI 0.69 / 0.72 against
  0.68 / 0.72 for page labels alone. No gain.
- An overlay rule (the page underneath stays put; new lines appear in a compact box): it found 9 of 21
  and 4 of 14 overlay visits, and flagged 14 and 15 that were not. The dimmed page under a scrim
  loses OCR lines unevenly, and a scrolled dialog list looks like a new page.

So **v1 is page-level**. States are either marked by the researcher, or wait for a detector that
uses the change *between* frames (TalkMiner's region rules, UiPath's templates) with its own labelled
test set. Recurrence may be the lever: the same dialog came back 5 times in one session.

### 4.3 Sequences

| | German | UK |
|---|---|---|
| steps, repeats merged | 9 | 18 |
| revisits / immediate back-steps (A→B→A) | 0 / 0 | 7 / 5 |
| distinct URL templates | 9 | 8 |

One participant went straight through; the other went back and forth between home and search, and
twice between bag and checkout. A flow diagram flattens that difference; per-participant paths keep
it, which is why the lens shows both (§5).

**Across the two sessions, the URL aligns where text cannot.** One is in German, one in English, on
different country sites. With the locale prefix dropped (`/de/de`, `/gb/en`) and ids and product
slugs masked, they share 6 templates (`/`, `/cat/*`, `/p/*`, `/shoppingcart`, `/order/continue`,
`/order/delivery`) and 4 transitions. Text similarity between the two languages is near zero. Most
studies are one language and one site, where text would align too; this is the hard case, and two
sessions cannot show whether a "typical order" is meaningful. That needs a real 6–10 session study.

### 4.4 Quotes on screens are sparse

| | German | UK |
|---|---|---|
| quotes extracted / said during the share | 25 / 18 | 28 / 16 |
| pages with at least one quote | 6 of 9 | 8 of 11 |
| quotes per page | 4, 4, 3, 3, 3, 1 | 4, 4, 2, 2, 1, 1, 1, 1 |

A screen card will often hold one or two quotes. So the detail view also offers **everything said
while the screen was up** (the transcript paragraphs), which is where the bulk of the evidence is.

### 4.5 The transcript's screens against the screen's screens

- **Report sections mostly sit on one page.** Of the quotes in sections (the speech-derived screen
  clusters), 14 of 17 and 12 of 15 were said while that section's most common page was on screen. The
  rest were said elsewhere, typically a comment about the previous page made on the next one.
- **Speech misses screen changes.** Topic segmentation's `screen_change` boundaries were within ±30 s
  of 2 of 8 observed page transitions in the German session (4 boundaries, 2 of them near a
  transition). The UK session's 8 boundaries covered 16 of 17 transitions, but 8 of those 17 came in
  44 seconds of searching, where two boundaries ±30 s cover them all, so that recall is generous;
  precision was 6 of 8.

Both numbers say the same thing: the transcript knows roughly which screens were discussed and is
loose about when the screen changed. The screen knows exactly when, and nothing about why.

### 4.6 Smaller findings

- **Link clicks cannot be seen at 4 s.** Clicks are inferred as page transitions. The browser's
  link-hover preview (a URL at the bottom of the window just before a click) appeared in 12 visits in
  Chrome and never in Safari: not a usable signal.
- **Loading frames become visits.** A blank page with the new URL and no content (4 in each session)
  should fold into the visit it leads to.
- **Other tabs and bookmarks become screens.** In the UK session the participant's own bookmarks
  briefly read as addresses. A participant who switches to their inbox will produce an inbox
  "screen". See §7.
- **Cost on top of screen text: none that matters.** Identity, clustering and the quote join are
  seconds per study over the screen-text index; no extra decode or OCR. dHash would need frames and
  adds little, so it is left out.

## 5. The lens

### 5.1 Layout: step columns, paths, grid (recommended); tree (rejected)

| layout | answers | at n = 5–12 | verdict |
|---|---|---|---|
| **Flow: step columns** | where people typically went next, where they turned back | columns are the typical first-arrival step (median, dense-ranked); edges carry *k of n* participants, never pruned; back-steps drawn distinctly | **recommended default** |
| **Paths** | what each person actually did | one row per session, screens in order, repeats merged, revisits outlined | **recommended**, one click away |
| **Grid** | what screens exist | cards in typical order, no edges | fallback: fixed-order walkthroughs, narrow windows |
| Tree (sitemap by URL) | how the site is filed | every product page under a different parent | rejected: describes the site, not the session |
| Sankey / directly-follows graph | volume flows | invents loops, hides people in "Other" | rejected (§3) |

### 5.2 A screen card

Thumbnail (a still extracted on demand, 320 px, the hover-thumbnail size), name, URL template,
*k of n* participants (one dot each), median time on screen, visits, quote count. Names come from, in
order: the researcher; the report section the screen's quotes fall into (§6.3); the page heading;
the URL path. The name's source is stated where it was guessed.

### 5.3 Selecting a screen

- **Header**: larger still, name, URL template, *k of n*, visits, median time, typical step.
- **States** as pills ("The page", "Enter postcode 5 of 6"), once states exist (§4.2).
- **When it was on screen**: one lane per participant, each visit a bar, dialogs in a second colour.
  Clicking a bar opens the transcript at that second with the video cued.
- **Quotes**: every quote said while the screen was up, from every participant, as quote cards
  (timecode, participant code, sentiment, tags), with the state it was said over. A second tab,
  **Everything said here**, lists the transcript paragraphs.
- **Tag sidebar**: the Quotes lens's sidebar, scoped to this screen's quotes, with counts; clicking a
  tag filters. Sentiment counts beneath it.

**Friction is shown as evidence, not a score.** Negative-sentiment quotes, revisits and back-steps
into the screen, and time on screen are counts on the card. A combined "friction score" would claim
more than five sessions can support.

### 5.4 Corrections are part of the design

The literature is unanimous that any automatic "same screen" will mis-merge or over-split somewhere.
The researcher can **rename**, **merge**, **split**, **hide**, and toggle **separate product pages**
(URL template ↔ instance). Overrides live in SQLite like other researcher edits, keyed by the derived
screen's URL template or text signature, so a re-run of the derivation keeps them.

### 5.5 Sessions without a screen

A session with no share (an interview, a call-only session) is counted out loud ("6 of 8 sessions
shared a screen"), never silently dropped. Its quotes stay in Quotes and Sessions.

## 6. Data model and pipeline

### 6.1 Derivation

Runs after the screen-text index, in the same serve background job, per study:

1. **Visits**: the screen-text index's text-diff moments, as intervals per session; loading visits
   folded into their successor.
2. **Address-bar URL per visit**, read before the chrome filter: whole-line URL only, scheme and
   query dropped, `#route` kept, long digit runs masked. **Template**: locale prefix dropped, product
   slugs and ids masked.
3. **Page key**: the URL template when present; otherwise TF-IDF over the visit's words with IDF over
   the study, average-linkage within the study, threshold ~0.25 (measured best 0.21–0.30).
4. **Screens**: visits grouped by page key across sessions. Text-keyed screens join across sessions
   only within one language.
5. **Quote join**: a quote belongs to the screen it overlaps most; a quote spanning a transition is
   listed under both, primary on the larger. The researcher sees the rule.
6. **Section link**: for each screen, the report section(s) its quotes fall into.

### 6.2 Storage

`<output>/.bristlenose/intermediate/screens/screens.json`: screens (id, key, URL template, derived
name and its source), visits (session, start, end, screen id), version in the cache key. Kilobytes.
No frames: thumbnails are extracted on demand, as the screen-text proposal decides for its results.

### 6.3 Names without sending screens anywhere

Screen text never reaches the LLM (§7). But the report already has LLM-made names for screens: the
section names, made from the transcript. A screen whose quotes mostly fall in one section borrows its
name ("Checkout & Delivery Options"). Measured purity (§4.5) says this will be right most of the time
and wrong in an identifiable way: when a screen's quotes split across sections, the card says so and
falls back to the heading or URL.

### 6.4 Routes

`GET /api/projects/{id}/screens` (screens, visits, stats, quote ids per screen) and the on-demand still
`GET …/screens/{screen_id}/still`. Both **server-only** (`SERVER_ONLY_PATH_TEMPLATES` in
`server/routes/export.py`; `tests/test_serve_export_coverage.py` forces the classification).

## 7. Privacy

The screen-text proposal's model applies whole: the index stays in the project; never in the HTML
export, the anonymised outputs, clip or quote exports, MCP, the chat lens or support bundles; **never
sent to the LLM.** What this lens adds:

- **Stills on cards are participants' screens.** Same treatment as the hover thumbnails: served behind
  the bearer token, never stored as files, never exported.
- **Screen names and URLs are screen text.** A URL can carry an order number or an email address; a
  heading can carry a name. Queries are dropped and digit runs masked, but the lens as a whole is
  **absent from the HTML export in v1.** Exporting a screen map (names, counts, flow, no stills) is a
  later, explicit choice.
- **Off-task screens.** A participant's inbox, bank or chat can appear as a screen visited by one
  person. Default: a screen on a different host from the study's main one, seen by one participant,
  is **hidden but counted** ("1 screen hidden"), and the researcher can reveal it.
- **No cloud vision.** The prior-art recommendation to have a vision-language model name or merge
  screens is rejected for the same reason screen text is not sent to the LLM. If it comes back, it is
  a local model or a new consent decision.
- **Copy where the feature is switched on** extends the screen-text sentence: Bristlenose also builds
  a map of the screens participants visited, from the same reading, kept in this project.

## 8. Failure modes

| case | what happens | mitigation |
|---|---|---|
| single-page app, one URL | one screen for many | keep the `#route`; text split within a URL as a researcher action |
| modal, panel, drop-down | folded into the page | v1: researcher-marked states; later a change-based detector (§4.2) |
| loading frames | spurious visits | fold empty visits with a new URL into the next |
| window or app share, prototype full screen | no URL | text identity (ARI 0.76–0.86 measured); Figma prototypes in a browser show `node-id=` in the URL, an exact key when visible, and the one query parameter the URL rule should keep |
| product pages | one template, many instances | default template; "separate product pages" toggle |
| participant typing in the address bar | half-URLs | require a URL to persist two samples |
| other tabs, personal sites | off-task screens | hidden-but-counted default (§7) |
| two languages or two sites | text cannot align | URL templates align (§4.3); otherwise per-session screens |
| call-only sessions | no screens | counted out loud (§5.5) |
| screens up < 4 s | never sampled | accepted; the scene strips (4 fps) could locate boundaries densely later |
| Zoom, Meet, mobile shares, CJK | unmeasured | the screen-text proposal's open list (§5 there) |

## 9. What it would take

Given the screen-text index (its §4 steps 1–2):

1. **`bristlenose/utils/screens.py`**: URL extraction before the chrome filter, visit folding, page
   keys, cross-session grouping, quote join, section link. Pure functions over the index and the
   quotes; tests on synthetic indexes (a site with known pages, a two-language pair, an SPA with
   routes, a loading frame, a bookmark that looks like a URL).
2. **Serve job**: one more step after screen text, same deferral rules, seconds.
3. **Routes and overrides**: §6.4; an overrides table for rename/merge/split/hide.
4. **SPA**: the lens (`/report/screens/`, a `TAB_ROUTES` key and its Swift `Tab` twin, pinned by
   `tests/test_tab_route_parity.py`), the card, the flow layer, paths, the detail with the existing
   quote card and tag sidebar; i18n in 21 locales; hidden in export mode.
5. **A labelled test set before any state detector**: a few hundred hand-labelled visit pairs from 6–10
   real sessions, the step the prior-art survey and these measurements both name as missing.

## 10. Open questions for the owner

1. **A lens, or grounding the sections?** The lens is the bold version. A smaller first step puts the
   observed screen on what already exists: a still and "said on: Delivery" beside each section in
   Quotes, and a flag on quotes said on a different page from their section. Both need the same data.
2. **Does it replace the transcript-derived sections when screens exist?** They answer the same
   question from two sources. Keeping both is honest; it is also two "screen" concepts in one report.
3. **Page-level only for v1?** States (dialogs, panels) did not separate automatically. Ship pages
   with researcher-marked states, or wait for a detector and a labelled set?
4. **Off-task screens hidden by default?** The proposed rule hides a one-participant, off-host screen
   but counts it. Too aggressive, or not enough?
5. **In the export, ever?** v1 keeps the whole lens out. A screen map without stills is plausible
   later; screen names are still screen text.
6. **Expected paths?** The discussion guide's tasks could supply an expected order per task, which
   unlocks direct/indirect success and lostness. Worth a design of its own once the map exists.
