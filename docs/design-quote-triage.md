# Quote-card triage — design doc

_Captured 15 May 2026 from a session with Simon plus a follow-up reality-check against the codebase. Single doc, several chapters; meant to be read whole because the chapters only make sense together._

_Supersedes `docs/design-close-quote-affordance.md`. The associated (gitignored) review log stays valid — its findings carry forward to this doc._

---

## 0. What this doc is, and isn't

This is **alpha-iteration material**, not a bugfix backlog. The mechanics of quote management get a design pass *as a coherent whole* in Figma after the TestFlight cohort have used the PoC and given real feedback. This doc captures the thinking that goes *into* that iteration — first principles, the dominant gesture, the verbs, where things live, what the keyboard and selection model want to feel like.

Anchoring points for the iteration:

- **The product is moving from PoC → Alpha.** That justifies revisiting the basic mechanics as a coherent piece, not picking at them one button at a time. Quote management is one of the surfaces that earns a unified pass.
- **The cohort hasn't spoken yet.** Most decisions in this doc are inputs to a Figma iteration that *responds to* real-use feedback. Don't pre-empt them by shipping surgical bits and bobs. **Quote-handling ergonomics is one of the focus areas for the TestFlight cohort calls** — the design iteration follows from what testers reach for, where they get stuck, which verbs read right to them, and what they expect the closed/archived/trashed states to mean in practice.
- **The work is one design iteration, not N tweaks.** When the time comes, the close affordance, the Counter position, the verbs, the keyboard rhythm, the selection/focus polish, and the "where do closed quotes go" mental model all move together because they constitute *one* researcher gesture-loop. Splitting them ships incoherence.
- **Figma is where the iteration lives.** This doc is the brief; Figma is the design surface. Code follows Figma.

The reality-check sections below (§11 starting-point pieces, §12 already shipped) describe **what's already on the floor of the workshop** — current code state, places the iteration can take as given or as material to rework. They're not a checklist to execute against now.

---

## 1. What this affordance actually serves

The first ~2 hours of a project is **rapid triage**. The researcher has just ingested a folder; the pipeline has surfaced everything plausibly quote-worthy; they're skimming, sorting, and starting to form hypotheses.

**Both gestures are at play — additive (star the leads) and subtractive (close the clutter).** The two workflows aren't cleanly inverted; they have different cost structures:

- **Paper-and-pen.** Skim-reading transcripts is cheap. Highlighting with a pen is cheap. **Copying onto sticky notes with a Sharpie is expensive.** The sticky-writing cost is what forces brutal selection — you highlight 10–20%, then maybe rewrite half of those onto stickies, ending up with the best 3–4 candidates per theme. The artifact is small because the artifact is expensive to make.
- **Digital.** The pipeline already removes most obvious dross before the researcher sees anything — you start with maybe 70–80% non-junk. Starring marks the 5–20% that could lead a section. Closing clears another ~20% of working clutter (duplicates, near-irrelevant, off-topic) so the active set shrinks to something the researcher can hold in their head. **What's *not* starred or closed isn't waste — it's the body of evidence.** The 23 quotes about checkout friction stay accessible, clusterable, weighable. Paper would have forced them down to 3.

So the digital superpower isn't "easier subtraction." It's that **the researcher doesn't have to cull down to the final publishable set.** The insight doc may lead with 1–2 headline quotes, but the long tail of 23 sits behind the finding and gives it weight. The sum of that text shaped the summary; the report keeps it.

Mental neighbours for the *gesture* of triage:

- **Gmail keyboard triage** — single-keystroke rhythm on a focused-item queue. Two hours of working through quotes needs no chord-stretches.
- **Highlighter on paper** — the natural research gesture for *starring* (additive, marking leads).
- **Photo editing — ergonomics yes, goal no.** Lightroom's P/X/U rhythm and the muscle memory of star-and-reject under multi-select map directly onto the gesture we want. What doesn't carry over is the destination: photo culling drives toward a small final publishable set; quote triage doesn't. The long tail of "okay evidence" is part of the deliverable, not waste to discard.

The triage gesture should be light at scale (single keystrokes, multi-select) *because* the researcher is moving through volume, but the goal of the gesture isn't reduction-to-publishable-set — it's **separating leads from working body from clutter**, while keeping the body accessible.

### Fluid ergonomics is a first-class quality requirement

Star and hide are a *paired* gesture, not two independent buttons. A researcher in flow toggles back and forth — star a few, hide a few, change their mind, multi-select and bulk-act, undo, keep moving. The interaction has to feel **fast and fluid both ways** at single-quote and at multi-select scope:

- The keyboard rhythm has to be near-instantaneous (no animation lock-in, no modal confirmations, no focus-lost surprises).
- Star and hide must be equally cheap from the same focused state — you shouldn't have to navigate or context-switch to flip between them.
- Multi-select bulk-star and bulk-hide must compose as easily as their single-quote forms.
- "Made the wrong call" is the dominant correction — un-star, re-open, swap a star for a hide — and has to be one keystroke away, not a menu-walk.

This is a quality the Figma iteration has to feel; it's not a feature you bolt on. The bug-shaped framing ("verify focus-after-close handoff") in §11 understates this — if the gesture isn't fluid both ways, the rest of the design doesn't matter.

## 2. What the AI does and doesn't do

**AI extracts. Researcher curates.** This is durable, not a slogan:

- The triage decisions — what's signal, what's noise — are the researcher's. They aren't suggestions to accept, they're judgement to apply.
- The AI surfaces themes and sections, which helps. It doesn't pre-cull, doesn't auto-hide low-confidence quotes, doesn't weight its own confidence into the triage queue.
- AutoCode-style proposals exist as a separate, opt-in surface. Triage is not that surface.

## 3. The unmarked middle — evidence body, not "maybe"

The natural triage reactions are **yes** (star — lead candidate), **no** (close — working clutter), and a wide middle that's neither. We don't render the middle as a separate affordance — and crucially, the middle isn't "undecided maybe" parking lot. It's the **body of evidence**: okay quotes about checkout friction, contextual material, quotes that contribute weight to a finding without leading it.

A third UI state would mis-frame this material as a decision-pending pile rather than what it is — the substantial set of quotes that shape the summary without earning the headline. The unmarked default already carries it correctly, costs nothing, and keeps the researcher moving.

(There's also a temporary "I'll come back to this" mental maybe — but that lives in the researcher's head, not the data model. Same affordance, different reading.)

## 4. Volume is the asset, not the problem

It's tempting to read "too much" as a problem the UX should solve by pre-sorting, signal-concentrating, or hiding-the-long-tail-behind-show-more. **That reads the situation backwards.** The volume *is* the digital advantage over paper — the reason a finding about checkout friction can be backed by 23 quotes instead of 3.

What that means for the design:

- **Don't pre-sort by signal-concentration during the first pass.** The act of reading-and-deciding is the researcher's work; pre-sorting short-circuits the hypothesis-forming that happens as they go. They're hunting for stars, not having them handed over.
- **Don't hide the long tail.** It carries evidence weight. Find-by-attribute (tags, search, topic clustering) is what makes the long tail valuable — the researcher can later assemble "all 23 quotes about checkout" on demand. That's the digital superpower over Sharpie-and-stickies.
- **Do make topic clustering fast and visible.** Tags, search, the Analysis page's signal-concentration metrics — these reveal evidence weight *after* the reading, not before, and they're what give the long tail its return-on-keeping.

The Analysis page (`bristlenose/analysis/`) and tag-based filtering aren't anti-volume tools — they're the affordances that make volume into evidence.

## 5. Close, not hide — and where closed things go

The current verb is *hide*; the current glyph is an eye-with-slash (`QuoteCard.tsx:37`). Simon's diagnosis:

- **Eye-icon vocabulary belongs to design tools** (Figma layer panels, Photoshop visibility). It's not a research-tool gesture.
- **The eye appears on tags too**, where it does something different — toggling visibility of every quote under a tag. One glyph, two scopes.

The fix:

**Verb: close.** Mental neighbour is a **browser tab** — closeable, reopenable, you can have lots, the content isn't lost. Specifically *not* a Mac window (no traffic-light apparatus); *not* a cancellation (the quote isn't being retracted from a flow); *not* a deletion.

**Glyph: bare ×** at the card's edge. Avoids the `xmark.circle.fill` chip-clear reading; sits in the content-region register; quiet at rest, lifts on hover/focus (the existing `.hide-btn` opacity transition still applies).

**Where they go matters.** Closed quotes need a visible destination so the researcher's mental model includes "I closed those — they're in the count badge at the section's bottom." Three properties together carry this:

1. **A visible counter** — the existing `Counter` component, repositioned (§7).
2. **A close animation** that travels — already in place (`hideQuote()` snapshot-and-animate sequence in `bristlenose/theme/js/hidden.js`). Don't remove or weaken; the journey is the mental model.
3. **A verb pair that promises reversibility** — close / open / open all. Not trash, not delete, not archive. Researchers' work feels precious; a trashcan glyph would imply destruction, even with a recycle bin behind it.

### What "destruction" means here — the source can't be destroyed, but the quote-as-extracted can be relocated

The transcript is the source of truth. The quote is a *window* onto a passage in the transcript, not a free-standing object — the underlying text can never be deleted by user action on the quote view. Whatever the verb is, the source stays.

But the quote-as-extracted *is* a real object with a home: the data-model invariant is **every quote lives in exactly one section or theme** (see `bristlenose/stages/CLAUDE.md`). That gives us a meaningful sense of "move" — a quote can be relocated *out of* its section/theme into a different category, without touching the transcript.

This is what makes a real Trash/Wastebasket category coherent: it's not "destroy data" (impossible — the source is intact), it's **a third category alongside sections and themes**. A trashed quote leaves its section/theme home and lives in Trash. An archived/closed quote stays in its section/theme but is hidden from view. Different operations, different data shapes.

### Three semantic levels (Visible / Archive / Trash) — post-TF

The session converged on a clean three-tier model. The alpha ships only the first two; Trash is a post-TF capability with a planned shape.

| Level | User's read of the data | Where the quote lives | Visible in section/theme views? | Counted in signals / aggregates / AI analysis? | Safe to send in an export to a PM? |
|---|---|---|---|---|---|
| **Visible** | Valid, on-topic, fine to show | Its section or theme | Yes | Yes | Yes |
| **Archive** (today's `.bn-hidden` semantic) | Valid, worth keeping, sensitive or off-deliverable | Its section or theme — just hidden from view | No | **Yes** | No (unless un-archived for the export) |
| **Trash** (post-TF) | Misleading, garbled, mis-extracted, hallucinated, "shouldn't have been pulled" | **Trash category** (third home, outside sections and themes) | No | **No** — requires the exclusion to flow through to aggregates | N/A — shouldn't influence findings |

**What ships in the alpha iteration:** one per-card affordance, mapping to Archive semantics (whichever verb wins from §5 — Close / Archive / Hide). Today's hidden-quote machinery already does this implicitly: `.bn-hidden` removes the quote from the view but signals were computed pipeline-time, with the quote included, before any user state existed. Pragmatically: today's "Hide" is structurally Archive.

**What's planned post-TF:** a Trash category. Captured shape:

- **Quotes page has three areas** (post-TF): citable sections, citable themes, **and a Trash area** at/near the bottom. Trash isn't banished to a sidebar destination — it's part of the Quotes page's own structure, just visually and semantically separate from the citable cards above it. Likely collapsed by default; clearly labelled; not competing for the eye with the sections/themes the researcher is curating.
- **Sessions / transcript view** keeps everything (source is sacred — §5 invariant) but renders trashed quotes inline with a **strikethrough** treatment, so the researcher's curation is legible at the source. Two coherent views: the Quotes page hides Trash from the citable foreground, the transcript marks it visually but doesn't omit it. (See §14 for the full transcript-layer treatment alongside Archive and Star.)
- **Per-quote affordance to move to Trash** lives in a secondary surface (right-click menu, `…` overflow, or a power-user keyboard binding). Not competing for the per-card primary slot with Close/Archive.
- **The invariant holds.** Every quote still lives in exactly one home — citable sections, citable themes, or Trash. The three areas on the Quotes page mirror the three possible homes.
- **Aggregate / signal recompute is the real engineering cost.** Today's signal-concentration, theme weights, sentiment bars all compute pipeline-time, before user state exists. Trash needs either re-aggregation passes or a pipeline-time flag that drives selective inclusion. This is the work that gates Trash; the UX is the easy part.

This three-tier model is also why Bin/Wastebasket/Trash is the right metaphor *only* at this level: it names a place quotes go to be excluded from the analysis story, not a place where source data dies. Mail's Trash analogy holds (the source server has a copy, the local trash is a folder, restoring is one click).

### Note: Archive is the live alternative — don't decide yet

Gmail's verb for the same "remove from view but keep accessible" operation is **Archive** (keystroke `e`, glyph `archivebox`). Functionally and emotionally close to our Close: both promise reversibility, both move the item to a findable destination, both refuse the trash framing. Researchers who use Gmail keyboard shortcuts — and many will — already have the muscle memory: `e` = "deal with this, move on."

Three verb options on the table going into the Figma iteration:

1. **Archive / Restore** (Gmail precedent, archivebox glyph). Strongest single-product analogue for keyboard triage of a high-volume queue. Researchers who know Gmail will read it instantly. Apple Mail also calls it Archive on iCloud/Gmail accounts. *Those who know will know.* Archive carries a useful additional meaning over Close: **"I'm probably never going to look at this individually again — but it should still be in the dataset."** Searches hit it. Tags persist. AI signal-concentration counts it. The 23-checkout-friction cluster still includes archived quotes — they contribute evidence weight to the finding even if the researcher never reopens them one by one. Archive ≠ "out of the corpus"; it's "out of the foreground." This framing fits the §4 stance (volume is the asset, long tail has weight) more cleanly than Close/Open does, because Close hints at a still-active-but-shut state where Archive hints at a settled-but-counted state. Worth weighing in Figma.
2. **Close / Open** (browser-tab precedent, bare ×). The current doc's lead; carries reversibility cleanly; safe in the research register.
3. **Hide / Show** (status quo). The verb the code uses today; what Simon's session pushed back against.

Keystroke options, **independent** of the verb choice, in rough order of precedent strength:

- **Delete (the key)** — Apple Mail's archive binding on iCloud/Gmail accounts (configurable, default). Mac users do this every day without complaint *because the underlying action is non-destructive and reversible*. Reuses convention rather than teaching new muscle memory. **Carries the strongest "I don't want to see this again" semantic** of all the options — feels like a clean settle-it gesture. Maps best to verb-as-Archive; also defensible for verb-as-Close. Safe here precisely because §5 above establishes the data isn't destroyed.
- **`e`** — Gmail's archive key. Strongest cross-product muscle memory for high-volume keyboard triage. Maps cleanly to verb-as-Archive (and acceptably to verb-as-Close).
- **`h`** — status quo binding. Survives a verb change without breaking existing muscle memory.
- **`c`** — "close" mnemonic. Free in Gmail and in Bristlenose; light cognitive load if verb-as-Close wins. No deep precedent.
- **`w`** — the "⌘W is window-close, lowercase `w` is content-close" mnemonic. Free in Gmail and Bristlenose; geographically adjacent to `e` on the home row (useful if a two-level "light/heavy" pair is wanted later). Thin precedent — works only as a derivation from ⌘W.

### Keystroke-weight vs click-weight asymmetry

Worth noting a real subtlety here: **the keystroke can carry more semantic weight than the click affordance, even though both trigger the same underlying action.** Pressing Delete *feels* like a heavier, settle-it-and-move-on gesture; clicking the same card's bare × *feels* like a casual "close this for now." Same action, same data outcome — different felt commitment.

That asymmetry is OK, even desirable: keyboard triage is the deeper-attention mode (the researcher's deliberately driving), where finality reads as confidence; mouse-tap is the lighter ambient mode (caught a quote off the corner of the eye), where reversibility reads as kindness. Letting the keystroke skew heavier than the click is actually a feature.

Worth checking in cohort: does the Delete keystroke feel *too* heavy on a quote you might want to reopen? If yes, fall back to `e` or `h` for the primary, with Delete possibly available as a power-user binding only.

Verb + glyph + key are three independent dials. The Figma iteration picks each from real cohort use:

- Do testers reach for `e` instinctively (Gmail users)?
- Do they reach for Delete (Apple Mail users)?
- Does "Close" or "Archive" read as the right register for a research surface?
- Does the archivebox glyph beat bare × at carrying "filed away"?

Don't decide here. Locale-key renames (§6) and any aria-label changes follow whichever verb wins; the Counter-to-bottom move (§7) and the open/restore mirror are independent of all three dials and can go ahead regardless.

### The glyph–verb pairing constraint

The verbs don't all pair equally with the available glyphs in the per-card affordance slot. The slot is small and dense — there's room for one quiet glyph at the card's edge, alongside the star at the opposite edge. That constrains what reads naturally:

- **× (bare close mark)** — pairs with **Close** instantly. Doesn't naturally say "Hide" or "Archive" — those verbs want different glyphs.
- **`archivebox`** — pairs with **Archive** instantly. Crowds the card at small sizes; reads as heavy on a per-quote slot; not a per-card affordance.
- **Eye-slash** — pairs with **Hide**. The status quo. Simon's session pushed back on the Figma/Photoshop reading.

So the realistic per-card pairings are: **× + Close** (easiest), eye-slash + Hide (status quo, register-mismatched), or a one-off custom glyph that sells a chosen verb harder than the SF Symbol library offers.

There's a separate question: **the two concepts — light "close for now" and heavier "archive out of eyeline unless hunting" — may not both belong in the same per-card slot.** Possible Figma reads:

- One verb, one slot. Close + × wins on glyph-fit grounds. The "out of dataset hunting only" semantic Archive offers is genuinely useful, but might not earn the per-card real-estate.
- Two levels. Per-card × + Close as the light gesture (the dominant triage move); a heavier Archive action lives elsewhere (right-click, bulk action menu, or a state transition for "really put this away for the rest of the project"). Two strengths of "remove from view," chosen by the depth of the gesture.
- One state, two readings. Treat Close and Archive as the *same* underlying state and let the verb in the UI follow whichever framing tested best with the cohort — the data model doesn't have to be split.

This is exactly the kind of constraint the Figma iteration is for: real glyph sketches at the actual per-card density, real cohort observation of how researchers reach for the gesture, real test of whether a two-level affordance carries its weight.

## 6. Open, not unhide

In the closed-quotes section:

- single-quote restore → **Open**
- bulk restore → **Open all**

Tighter verb pair than hide/show, matches the tab-close mental model in both directions, drops the awkward "unhide" / "restore" / "un-dismiss" cluster.

Locale-key renames (verified at line numbers in `bristlenose/locales/en/common.json`):

| Today | Tomorrow | Line |
|---|---|---|
| `announce.hidden` ("Quote hidden") | `announce.closed` | 136 |
| `announce.restored` ("Quote restored") | `announce.opened` | 137 |
| `keyboard.shortcuts.hideQuotes` ("Hide quote(s)") | `keyboard.shortcuts.closeQuotes` | 239 |

Six locales × three keys. **Internal data-model identifiers stay `hidden`**: `.bn-hidden` CSS class (defence-in-depth), `bristlenose-hidden` localStorage key, `hideQuote()` / `isHidden()` / `bulkHideSelected()` functions. The split is deliberate — user-facing vocab vs internal-code vocab — and gets a one-line note in `docs/design-html-report.md` near the `.bn-hidden` section so a future contributor doesn't "tidy" it.

## 7. Counter position — bottom, not header

The hidden-quotes Counter sits inside the section's `<h3>` block today (`QuoteGroup.tsx:815-823`), competing with the title. It's housekeeping; the title is the anchor. Move it to the **bottom of the section block** as a footer-line, where Mail's labels and Finder's status bar live.

Implementation note: move in JSX, not via CSS `order:` / `grid-row:` (WCAG 1.3.2). Don't render it at all when zero — keeps screen-reader skim clean.

## 8. Keyboard rhythm — what exists, what stays, what shifts

The Gmail-style rhythm is already wired in `useKeyboardShortcuts.ts:267-465`. Most of what the session was designing already exists:

| Key | Today | Tomorrow |
|---|---|---|
| `j` / `k` (or ↓/↑) | Move focus | Same |
| `Shift+j` / `Shift+k` | Extend selection | Same |
| `x` | **Toggle selection on focused quote** | Same — *don't* repurpose for close |
| `h` | Hide (focused or selected) | Same keystroke, verb-renamed in labels to "close" |
| `s` | Star | Same |
| `t` | Add tag | Same |
| `r` | Repeat last tag | Same |
| `Enter` | Play | Same |
| `/` | Focus search | Same |
| `Escape` | Cascade: modal → overlay → search → selection → focus | Same |

**Critical avoided collision:** `x` is already selection-toggle (correctly — Gmail's `x` does the same). Don't reassign to close. Keep `h` for the close action; rename only the *user-facing labels and announcements*, not the keystroke. Minimum churn, maximum signal in the changelog because the *vocabulary* changes everywhere visible while the muscle memory stays put.

**Not adopting ⌘W.** Tempting under the tab-framing, but it collides with the host window's own close on macOS and adds a special case. Cost > benefit. Park.

## 9. Selection and focus — already there, polish where it falls short

Selection state, focus state, multi-select (Shift-click range, anchor, Cmd-click toggle), bulk handlers (star, hide, tag) all exist:

- Focus and selection live in `FocusContext.tsx` (selected IDs + anchor + focused ID)
- Bulk action on click acts on the selection if the clicked quote is in it (`frontend/CLAUDE.md` — Bulk actions on multi-selection)
- Visual states: `.bn-focused` (focus ring), `.bn-selected` (selected wash) — both render simultaneously, distinct
- Focus outline: keyboard-only (`:focus-visible`), mouse focus suppressed globally (`atoms/interactive.css`)

**Land-now polish (real gaps, not new design):**

1. **Confirm focus-after-close handoff.** Today `handleToggleHide` in `QuoteGroup.tsx:316` runs the bulk-hide flow, but no explicit next-sibling-focus handoff is visible. Either it's there and I missed it, or it's a latent gap. When you close the focused card with `h`, focus should move to the next quote (or previous if last) — otherwise the keyboard burst stalls every closure. Verify, then implement if missing.

2. **Selection persistence through filter / search.** Less clear-cut — needs a manual check. If a researcher selects 30 quotes and types a filter, do the selected IDs survive? They should.

3. **`AnnounceRegion` polite vs assertive.** Today `aria-live="assertive"` (per `frontend/CLAUDE.md`). For close/open in a triage burst, **polite is right** — assertive interrupts; close confirmation isn't an interrupt-class event. Either change the region or add a separate polite one for triage announcements.

## 10. Tag-side eye — out of scope here, but flagged

The eye glyph also appears on tags, where it toggles visibility of every quote carrying that tag. Two views remain on whether that's:

- A genuine visibility toggle (eye is right; the only reason it felt mixed was that quotes used the same icon for an unrelated job)
- A *filter* operation (additive, composable) — in which case the right glyph is a funnel (`line.3.horizontal.decrease.circle`)

Defer the call. Quote-side close lands now; tag-side glyph stays on the eye until cohort observation tells us researchers expect filter semantics. Document the deferral in this doc rather than the table pretending the answer is settled.

## 11. Starting-point pieces for the Figma iteration

These are the structural pieces the iteration will work with. Not a to-do list to execute against — material for Figma to absorb, rework, or extend as a coherent whole. File:line references are anchors so the design pass knows what's where in the current build.

All in serve-mode React; static render path stays as-is (sealed byproduct).

| # | Change | File | Notes |
|---|---|---|---|
| 1 | Replace `HideIcon` SVG with bare × | `frontend/src/islands/QuoteCard.tsx:37-51` | Smaller SVG or text `×` character |
| 2 | `aria-label="Hide this quote"` → `aria-label="Close quote"` | `frontend/src/islands/QuoteCard.tsx:779` | Object-scoped per a11y guidance |
| 3 | CSS class semantics (keep `.hide-btn` name or rename to `.close-btn`) | `bristlenose/theme/atoms/toggle.css:23-49` | Lean toward keeping `.hide-btn` to minimise blast radius — class name is internal |
| 4 | Counter UI strings: "Unhide all" / "Unhide:" / `title="Unhide"` → "Open all" / "Open:" / "Open" | `frontend/src/components/Counter.tsx:69, 80, 109` | Three strings |
| 5 | Locale-key renames × 6 locales | `bristlenose/locales/*/common.json:136, 137, 239` | Mechanical; preserve internal `hidden` data-model identifiers |
| 6 | Move `<Counter>` from `<h3>` block to bottom of section | `frontend/src/islands/QuoteGroup.tsx:815-823` (move out of `.bn-group-header`) | JSX move, not CSS; don't render when count is zero |
| 7 | Document the user-facing-`close` vs internal-`hidden` split | `docs/design-html-report.md` (near `.bn-hidden` section) | One paragraph |
| 8 | Verify focus-after-close handoff; implement next-sibling fallback if missing | `frontend/src/islands/QuoteGroup.tsx:316` (`handleToggleHide`) | Code change if absent |
| 9 | Consider polite live region for close/open announcements | `frontend/src/utils/announce.ts` + `AnnounceRegion` | Or split assertive/polite by event type |

Estimate at *implementation* time (after the Figma pass, after cohort feedback): roughly a careful sprint-day for the items above, possibly more once the design iteration adds visual / interaction polish on top — particularly the locale-key sweep across six locales (see `docs/design-i18n.md` for the round-trip-encoding trap with `\u` escapes).

## 12. What's already shipped, don't redo

Confirmed against current code:

- Single-keystroke triage rhythm (Gmail-style) — `useKeyboardShortcuts.ts`
- Multi-select with anchor, Shift-extend, Cmd-toggle, Escape-clear — `FocusContext.tsx` + `useKeyboardShortcuts.ts`
- Bulk star / hide / tag on selection — `QuoteGroup.tsx` handlers + `frontend/CLAUDE.md`
- Close/reveal animations with snapshot-and-travel — `bristlenose/theme/js/hidden.js` (vanilla path) + React equivalent
- Live region for SR announcements — `announce.ts` + `AnnounceRegion`
- Star button + hide button + their ordering (top-right) — `toggle.css`
- Closed-quotes counter UI with expandable preview + per-quote-open + open-all — `Counter.tsx`
- Hidden-group tag UX (closed-eye icon in autocomplete + auto-unhide on accept) — `frontend/CLAUDE.md`
- `content-visibility: auto` perf for hundreds of cards — `theme/CLAUDE.md`
- Focus ring via `:focus-visible` keyboard-only convention — `atoms/interactive.css`

## 13. Out of scope for this iteration

Decisions deliberately not pre-empted here. Some are for the Figma iteration to take a view on; others are out of scope for the alpha pass entirely.

- **Tri-state "maybe" affordance** — see §3; maybe is mental, not UI. Don't add a third pile.
- **Signal-concentration sort within sections** — see §4; researcher hunts. Pre-sorting short-circuits the work.
- **Show-more / long-tail UI** — see §4; same reason.
- **Trash/Wastebasket as a third category** — see §5 three-tier table; planned **post-TF** as a real data-model addition (third home alongside sections and themes), not a verb in the per-card slot. The alpha ships Archive-semantics under whichever verb wins (Close / Archive / Hide); Trash arrives after, gated on aggregate-recompute work.
- **⌘W binding** — see §8; cost > benefit on Mac. Don't add.
- **Tag-side glyph decision (eye vs filter funnel)** — see §10; pending cohort. Figma iteration may revisit.
- **Animation fast-mode during keyboard burst** — premature optimisation; measure before adding.
- **Bulk-close undo threshold + toast** — Figma iteration may want this; depends on what cohort says about accidental-close rates at speed.
- **× placement reshuffle (top-left bicameral pairing)** — see §9; today's top-right stack is already working. Figma iteration revisits as part of the card-as-a-whole, not as a standalone move.

## Future: transcript-layer reflection of triage state

Sketched for capture, not for soon. Once the three-tier model (Visible / Archive / Trash) is real and starring is on the existing data, the **transcript view** could reflect that triage state visually — making the researcher's curation legible at the source, not only at the report.

**Sessions / transcript view** — sketch:

- **Trashed quote** → shown in the transcript but with **strikethrough** (visible-but-discarded; the source isn't lost, but the reader sees this was set aside)
- **Archived quote** → shown at **50% grey** (de-emphasised but readable — present in the corpus, not in the citable foreground)
- **Citable / unmarked quote** → normal full-contrast text
- **Starred quote** → a star glyph in the transcript margin, or inline marker, on the extracted span

**Quotes page** — the parallel structure:

- **Trashed quotes** → live in the page's third area (Trash), separate from citable sections and themes
- **Archived quotes** → hidden from view in their citable section/theme, surfaced via the Counter at the bottom of each section
- **Citable** → the foreground cards in sections and themes, the dominant view
- **Starred** → marked inline on the card (existing star)

The two views aren't redundant; they're complementary. The Quotes page is the **curated foreground** where Trash is structurally removed from citable space. The transcript is the **source view** where everything stays visible but the curation state is rendered as visual emphasis.

Implication: the percentage of text left in full-contrast black is the citable proportion. The starred subset is the lead candidates. The grey is the body of evidence (still counted in signals — §5 three-tier table). The struck-through is what the researcher judged wrong-data.

This builds on the existing `<mark class="bn-cited">` mechanism (`bristlenose/theme/CLAUDE.md` — quote extents are already marked in transcript segments; the inline highlight CSS is currently `background: transparent` but the spans are emitted). The mechanism is in place; the visual treatment is the missing layer.

A reader of the project — the researcher's future self, a colleague, a PM scrolling through evidence — gets a coherent view: the report's tiers and the transcript's tiers tell the same story.

Not for the alpha iteration. Gated on Trash existing (post-TF, §5) and on the visual treatment surviving a Figma sketch at the transcript's typographic density. Worth keeping on the horizon because it's the affordance that ties report-curation back to source-evidence with no friction.

## 14. Open questions the Figma iteration will work through

These are the questions the cohort's first-real-use feedback should inform. Don't pre-empt them; collect signal, then iterate in Figma:

1. Does "Close" survive translation in fr (`Fermer` already overloaded) and ja (particle question on "Open all")? Default to Fermer/Ouvrir; flag for native reviewer.
2. Does the bottom-of-section Counter position feel right, or does it orphan the housekeeping? An indicator near the title ("3 closed ↓") might help; see if researchers ask for it.
3. Is the eye on tags read as visibility-toggle or as filter? Drives §10.
4. Does the close animation read as travel-to-a-place, or does it feel like the quote vanished? If the latter, the destination needs to be more visible (e.g. a momentary highlight on the Counter on close).
5. Does bulk-close above some threshold (10? 30?) need an undo affordance? The single-keystroke rhythm makes accidental closes more likely at speed.

---

## Document history

- 15 May 2026 — created from session with Simon. Absorbs `docs/design-close-quote-affordance.md`. Reality-checked against `QuoteCard.tsx`, `QuoteGroup.tsx`, `useKeyboardShortcuts.ts`, `Counter.tsx`, `toggle.css`, `en/common.json`, plus `frontend/CLAUDE.md` and `bristlenose/theme/CLAUDE.md`.
