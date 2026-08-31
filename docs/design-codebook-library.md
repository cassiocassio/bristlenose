---
status: partial
last-trued: 2026-07-26
trued-against: HEAD@main on 2026-07-26
superseded-by: [design-codebook-state-model.md]
---

# Codebook Library — design & build plan

> **Truing status (2026-07-26): the enable/disable SEMANTICS in this doc are
> SUPERSEDED by [design-codebook-state-model.md](design-codebook-state-model.md)** —
> the canonical spec for how disable behaves. This doc was written around a
> **view-only** disable ("off is just a fold; results always retained; re-enabling is
> free and instant; the switch does NOT gate re-apply"). The code **reversed** all of
> that: disable is now **functional — "off means off"**. It drops the codebook from
> the tags sidebar + autocomplete, hides its badges report-wide, folds the section,
> AND stops coding new sessions; **re-enabling fires a catch-up delta that DOES spend**
> on the sessions added while it was off. So treat every _"view-only / never re-spend /
> free-and-retained / does not gate re-apply / disable = Hide"_ statement below as
> **historical** (commits: "flip re-apply gate to enabled + catch-up delta on
> re-enable", "split hide (decorate, still suggests) from disable (exclude)", "true the 'disable is
> view-only' framing out of code + docs"). The **UI-redesign layout** — Library tiles,
> Add↔Remove, fold, sidebar dots, Forget — remains the live plan; only the
> disable-semantics thread rotted. **Decision B** and the **Q6 delta-only** shape below
> are still correct under the new model.

## Changelog

- _2026-07-26_ — **decided: the install-axis label is Install / Uninstall**, replacing
  Add / Remove. Rationale: it's the more precise word and locks the whole codebook
  surface onto the browser-extension model the doc already leans on (Install button ·
  Enable toggle · optional purge-on-uninstall). One toggling button per Library tile
  (Install when out / Uninstall when in), wired to the existing import/remove endpoints.
  20-locale re-translation is a follow-up (English settles first). The "Added" badge
  becomes "Installed"; "Remove from Codebook" becomes "Uninstall".
- _2026-07-26_ — trued against the "off means off" work. The view-only disable thread
  is reversed and now points to the state-model doc as canonical; the Status header,
  Principles 1–2, the three-surfaces table, the Phase 1 "Decision A" items, and the
  parallelizability buckets are corrected/annotated inline. Decision B and Q6's
  delta-only shape preserved (still valid). The UI-redesign body stays as the live
  plan. Anchors: state-model doc §7/§8; commit subjects above.

**Status:** design settled; partially built. **Shipped**: vertical full-width Library
tiles + de-greened "Added" badge; the Library/Add/Apply string renames (de-sparkled);
the **framework enable/disable switch** (trailing macOS-matched switch); and — landed
*since this doc's first draft* — the **functional disable + persistence** behind that
switch (`ProjectFrameworkState`, migration 007): off now folds the section, hides
badges report-wide, drops the codebook from the tags sidebar + autocomplete, and gates
re-apply on `enabled` (see the state-model doc). **Not yet built:** fold *animation*,
collapsed summary meta, Add↔Remove install toggle, sidebar dots, **Forget**. Mock:
[`docs/mockups/codebook-library-states.html`](mockups/codebook-library-states.html).

Supersedes the "Import / Remove from Codebook" framing. Related:
[design-autocode.md](design-autocode.md), [design-codebook-island.md](design-codebook-island.md),
[design-dynamic-codebook-builder.md](design-dynamic-codebook-builder.md).

## The shift, in one line

From **Import a codebook** (a file-I/O verb) and **Remove from Codebook** (a red,
destructive-sounding button) to a **Library → Add → Apply → enable/disable**
lifecycle that is non-destructive, cost-honest, and lets researchers *play*.

Why it matters: the old copy fought itself — you **Import**, but you **Remove**
(not a pair); the remove confirm said **Hide "{x}"?** while the reassurance said
**restore instantly** (three metaphors for one behaviour). Underneath, the
behaviour was *already* a reversible, retained toggle. Only the words lied.

## Principles

1. **Cost-safe play.** ~~Getting a codebook onto your workbench is free.~~
   **Reversed in codebook v2, 31 Aug 2026 — installing IS the spend.**
   `importCodebookTemplate(id).then(() => startAutoCode(id))`
   (`frontend/src/islands/CodebookV2.tsx`): Install fires AutoCode immediately,
   with no separate confirmation, deliberately — *"it spends, but the researcher
   asked by clicking, and a dialog on an additive act teaches them to dismiss
   dialogs, which is what makes the destructive one stop working."* The
   reversal was recorded as owed in `design-codebook-v2.md` (D4) and never
   discharged here until now; a contributor reading this principle would have
   built a free-install path the shipped lens does not have. The original text
   is kept below so the change is legible. **Apply**
   (AutoCode) is the *one* deliberate spend. Disabling never re-spends and always
   keeps its results. _(Trued 2026-07-26: re-enabling is **no longer** free-if-
   unchanged in all cases — if sessions were imported while the codebook was off,
   re-enable fires a **catch-up delta** that codes just those new sessions. The
   existing results are still never re-billed; the spend is only on the genuinely-new
   quotes. See state-model doc §6.)_ (No `✦` marker: the sparkle is **dropped from
   the Apply button** — decided. The wider system-wide `✦` retirement leans yes;
   deferred to its own pass — Q5.)
2. **Retention is visible.** Disabling keeps every result — nothing is deleted.
   _(Trued: disable is more than a fold — it also drops the codebook from the tags
   sidebar + autocomplete and hides its badges report-wide, "off means off". The
   section-fold is one of several consequences, not the whole of it. State-model §5.)_
3. **No control does two jobs; no surface does two jobs.** The Library is a
   catalogue (browse + Add). Your codebook is the workbench (Apply, toggle, fold).
   The sidebar is status only. A control that looks operable *is* operable.
4. **Colour maps to cost.** No red on anything reversible. Red is reserved for the
   one genuinely destructive action — **Forget** (purge retained results, so
   re-adding would re-spend) — which is *deferred*, not built now.

## The three surfaces

| Surface | Job | Verbs |
|---|---|---|
| **Codebook Library** (modal) | catalogue — the *install axis* | **Install ↔ Uninstall** (one toggling button) |
| **Your project codebook** (page) | workbench — the *enable axis* + run | **Apply**, enable/disable (slider), fold |
| **Sidebar** (contents) | status — what's on | none (blue dot = on) |

**Two axes, like a browser extension.** *Install* (Add/Remove — is it in my
project?) is separate from *enable* (slider on/off — is it running?). An added-but-
disabled codebook still sits on the codebook page (folded, slider off); a *removed*
one is gone from there, back in the Library showing **Add**. Both are reversible and
retained — Remove uninstalls but re-adding is free. This anticipates user-published
codebooks: you'll want to uninstall ones you're not using, not just disable them.

The Library and the codebook are honestly different: a *catalogue* you take from,
and a *workbench* you work at. Neither borrows the other's controls.

## State machines

### Library tile
```
Not installed ──[Install]──▶ Installed ──[Uninstall]──▶ Not installed   (one toggling button, both states)
Coming soon (greyed, non-interactive)
Create new (dashed + tile)
```
The Library never spends money and never runs anything. `Add` is free (drops the
codebook's tag groups into your codebook, then the modal closes — see Landing).
`Remove` uninstalls it from your project (back to `Add` here); re-adding later is
**free, retained**. Both are **the same button sharing one fixed footprint**
(`min-width` + centred text), top-right in the tile corner, so the control column
never shifts between states. **Remove is neutral, not red** — it's reversible. It
reuses the existing impact dialog (see below), softened (re-add is free). *Decide
later:* dim an added tile to ~80% since it's no longer "addable".

### Codebook-page framework section — the trailing control morphs
```
Added, not applied ──▶  [ Apply to N quotes ]       (big accent button, right edge)
        │ click
        ▼
Applying ──────────▶   (progress = EXISTING floating indicator — see below, out of scope)
        │ done
        ▼
Applied, ENABLED ──▶   [ ●▶ switch ON ]  groups expanded, counts shown
        │ switch off ⇅ switch on   (free, retained)
        ▼
Applied, DISABLED ─▶   [ ▶● switch OFF ] groups folded to one line: "N tag groups · off · kept"
```
`Apply → switch` is a one-way handoff: once applied, the button is spent and the
switch takes over as the free on/off forever after.

**Apply progress is NOT part of this redesign.** "Auto-coding N quotes…" is the
*existing, already-engineered floating* activity indicator — deliberately built to
stay visible across every lens, so it is **not** an inline spinner in the codebook
section. Where it ultimately belongs (project-status line / a titlebar pill) is a
**separate session** — do not touch it here.

### Landing after Add
Clicking **Add** in the Library **closes the modal immediately** and drops the user
back on the codebook page, **anchor-scrolled to the just-added framework section**,
with its **Apply to N quotes** button at the top of the eyeline. (Reuse the existing
`#codebook-fw-{id}` anchor scroll.)

### Sidebar row
```
Active     → blue dot + full contrast   (echoes the switch: accent on)
Disabled   → grey dot, muted text       (echoes the switch: off-track)
Available  → muted (.not-imported)      → opens the Library
```
**Dot echoes the switch — blue on / grey off.** We looked at macOS System Settings
(Settings › Network, 17 Jul): its status dots are green/amber/red, but that colour
*range* is for **multi-state connection status**. Our codebook is **binary on/off**,
and the control beside the dot is the standard macOS **switch (blue on / grey off)**.
So the dot speaks the switch's language, not the network traffic-light's — importing
green would (a) imply a state range we don't have and (b) break colour-agreement with
the adjacent switch. Flat solid ~7–8px, `--bn-colour-accent` on / `--bn-off-track`
off. Mock shows two rows: **A** compact lone dot; **B** dot + status word + count
(`On · 142 tags` / `Off · kept`) for a richer row if wanted.

## Controls & affordances

- **Add / Remove — one footprint.** The Library control is a single toggling button
  (`Add` ↔ `Remove`) with a fixed `min-width` and centred text, so switching state
  never shifts the right-edge alignment. Both neutral (Remove is reversible).
- **Apply button weight.** Concern noted: `Apply to N quotes` risks feeling
  *heavy-handed* yet is *easily missed*. Resolution: the **landing anchor-scroll puts
  it in the eyeline**, so it doesn't need to shout — a calm, moderate accent button
  is enough. Let the scroll do the "don't miss it" work, not size. (Tune weight in
  build; don't over-inflate it.)
- **Sidebar dot — lone, first-line aligned.** A single blue/grey dot (variant A;
  B dropped as too heavy). Aligned to the **first line** like a list bullet
  (`align-items: flex-start` + optical `margin-top`), so it stays put when a long
  codebook name wraps rather than drifting to the vertical centre of the block.
- **Trailing switch, not a leading tick.** A checkbox is anchored to the *leading*
  edge (it precedes its label), so it fights the title or forces an indent. A
  switch lives on the *trailing* edge — the macOS settings-row idiom: title flush
  left, control + state + message all on the right. The switch here is a *genuinely
  operable* control (it folds the section), so it is not a "tick you can't tick."
- **macOS-matched switch.** Match metrics (~38×22 track, ~18 white knob + soft drop
  shadow), on-fill bound to the system accent, grey off-track. The exact `NSSwitch`
  spring curve and focus ring are not reproducible in CSS/WKWebView — that ~5% is
  the accepted gap, judged in-app against a real switch (not in a mock).
- **Fold animation** (reuse hidden-quotes physics — *timing*, not the ghost-fly).
  Disable: groups fold up into the header line (height→0 + slight lift & fade so
  they read as tucking *in*), content below slides up, summary meta crossfades to
  `· off · kept`. Re-enable reverses. Wire to the shared `--bn-transition-*`
  tokens; `prefers-reduced-motion` → instant.

## UX text (current → new)

| Key | Current | New |
|---|---|---|
| `browseCodebooks` (button) | "Browse codebooks" | **"Codebook Library"** |
| `browseTitle` (modal) | "Browse codebooks" | **"Codebook Library"** |
| `browseSubtitle` | "Import a framework codebook or create your own" | **"Add codebooks to your project, or create your own"** |
| `frameworksHeader` | "Codebook frameworks" | unchanged |
| `yourCodebooksHeader` | "Your codebooks" | unchanged |
| `createNew` | "Create new codebook" | unchanged |
| `comingSoon` | "Coming soon" | unchanged |
| `importCodebook` | "Import codebook" | **"Add"** |
| `autoCodeQuotes` | "✦ AutoCode quotes" | **"Apply to {{count}} quotes"** (sparkle dropped — decided) |
| — (new) | | **"Added"** (tile status) |
| — (new) | | **"Auto-coding quotes…"** (apply progress) |
| — (new) | | **"{{groups}} tag groups · {{tags}} tags"** (enabled summary) |
| — (new) | | **"{{groups}} tag groups · off · kept"** (disabled summary) |

**Removed strings:** `removeFromCodebook`, `hideTitle`, `tagsRemovedFromQuotes_*`,
`restoreAnytime`, `autoCodePreserved`, `restoreCodebook`, `restoringCodebook`,
`restoreHelp`, `previouslyImported`, `loadingImpact`, `noQuotesTagged`.

> **i18n:** settle the English copy here first; the other 19 locales are a later
> propagation pass (per the hand-tune-copy-before-i18n rule). Don't seed 20 files
> until these strings are signed off.

## What's removed / relocated

- The **"Remove from Codebook" button on the codebook page** (desktop: "Remove
  Framework") — gone. The codebook page's on/off is the **slider (fold)**, which is
  *disable* (Hide), not removal.
- The **impact dialog** (`getRemoveFrameworkImpact` / the "Hide {x}?" modal) is **not
  deleted — it's relocated** to the Library's **Remove** button (true uninstall),
  softened since re-adding is free. So Remove keeps a confirm; disable (fold) does not.
- The green **`imported` badge** (`.picker-card.imported::after`) — replaced by the
  **Remove** button in the added state; also fixes that it was a hardcoded CSS
  `content:` string, not localised.

## This session's scope (deliberately narrow)

**Only:** layout changes (Library modal + tiles + Add top-right, codebook section
control morph, fold) · button/label text (Library rename, `Add`, `Apply` sans
sparkle) · the **blue dot** status · the **blue/grey switch** language. Nothing else.

## Deferred (explicitly not building now)

- **Apply-progress relocation** — the "Auto-coding N quotes…" **floating indicator
  already exists and is good enough**; where it ultimately lives (project-status
  line / titlebar pill) is its **own session**. Do not re-engineer it here.
- **Retire `✦` system-wide** (Q5 — *decided*) — remove from the proposed-badge
  action pill + the AutoCode toast (the Apply button is already done). One
  coordinated pass so nothing's left half-sparkled.
- **Personal / cross-project codebook library** (Q2) — reuse your own *created*
  codebooks across projects. Created codebooks are **per-project** for now; a shared
  personal shelf is a separate future feature.
- **Purge retained results ("Forget")** — the lone destructive action (drop a
  codebook's stored proposals/tags → re-adding would re-spend). _(Decided 26 Jul
  2026: this is **not** a fourth standalone red button. It folds into **Uninstall**
  as an optional "**also purge results?**" — the app-store idiom, uninstall → "remove
  data too?".)_ Rationale: hide · disable · uninstall already form a reversible,
  nothing-lost gradient; purge is the one irreversible act, and it only makes sense
  *at uninstall time*, so it belongs in that flow, not as always-visible chrome.
  Bonus: it resolves the current "Remove — no promise on accept/deny work" hedge into
  a clean contract — **uninstall keeps results by default; opt-in to purge**. Build
  later — not needed until retained-but-uninstalled data starts leaking somewhere it
  shouldn't (exports at scale). Until then, uninstall is retained + reversible.
- **19-locale propagation** of the new/changed strings.
- **"Add & Apply" fast path** — ship the safe default (separate Apply); add the
  shortcut only if the cohort asks (a mis-click on a combined button is the exact
  surprise-spend we're avoiding).
- **Incremental sessions × active codebooks** — ~~the cross-feature re-apply question
  (see Open Q6). Parked; needs the incremental path to be additive first.~~ **Built** —
  see §"Session update — Q6 (incremental re-apply) is BUILT". Cost-consent and
  interim-state remain open.

## Open questions for review

1. **macOS switch fidelity** — *resolved: yes, the metric/colour match is enough.*
   Accept the custom CSS switch (`.framework-toggle` — ~38×22 track, accent-on /
   grey-off, white knob + soft shadow) already shipped in `c62e611f`; **no** native
   `NSSwitch` overlay. The spring curve is the accepted ~5% gap.
2. **"Your codebooks" placement** — *resolved:* a created codebook is **per-project**
   (lands in *this* project, not a shared shelf), shown as its own "Your codebooks"
   section below the frameworks shelf in the Library modal. **Deferred:** a personal
   / cross-project shared codebook library — reusing your own codebooks across
   projects — is a separate future feature (see Deferred).
3. **Sidebar dot** — *resolved & confirmed:* **blue on / grey off** (echoing the
   switch, not green), **variant A** — the compact lone dot, first-line/bullet
   aligned. Variant B (dot + word + count) set aside. Not yet built.
4. **Apply progress verb** — *resolved:* **"Auto-coding quotes…"** (describes the
   work), not "Applying…".
5. **The `✦` AI-sparkle** — *resolved: retire it everywhere.* Apply button already
   dropped (shipped). The remaining pass removes `✦` from the **proposed-badge action
   pill** and the **AutoCode toast** too — words/context carry "this is AutoCode".
   One coordinated pass across every AutoCode surface (so nothing's left half-
   sparkled); tracked in Deferred, not this feature.
6. **Incremental sessions × active codebooks — does adding sessions re-apply?**
   (~~Parked — needs the incremental path to be additive first.~~ **Unparked: built** —
   see §Q6-BUILT below; the additive path shipped v0.20.0, 11 Jul 2026.) **Intuition: yes** — an *enabled + applied* codebook should
   cover *all* project quotes, or "active" is a silent lie (new quotes uncoded). But
   re-applying spends, so it must respect cost-safe-play. Shape:
   - **Scope:** only *enabled + applied* codebooks re-apply; disabled (off·kept) and
     never-applied ones don't (consistent with the enable axis).
   - **Delta only:** code just the NEW quotes — never re-code existing ones, never
     clobber human-provenance tags (`QuoteTag.source == "human"`). ~~Prerequisite:
     incremental re-analyse must become *additive*, not destructive (it currently
     isn't).~~ **Both clauses stale (28 Jul 2026):** the additive path shipped
     v0.20.0 (11 Jul) — `--clean` is the only destructive route and has zero Swift
     callers — and *Delta only* is no longer a proposal but what shipped
     (`autocode.py:831` `reapply_active_frameworks`, wired at `app.py:865`).
   - **Cost consent:** lean toward **bundling into the incremental-add consent point**
     ("adding 3 sessions will also apply your 2 active codebooks to the new quotes")
     — the user is already committing to an expensive run — rather than a silent
     auto-spend *or* a manual per-codebook re-apply chore.
   - **Honest interim state:** between add and re-apply, show *partially applied*
     ("142 tags · 38 new quotes pending"), not a fake fully-applied count.

## Build scope (files)

| Area | Files |
|---|---|
| Strings (en only) | `bristlenose/locales/en/common.json`, `.../desktop.json` |
| Library modal + codebook section | `frontend/src/islands/CodebookPanel.tsx` |
| Sidebar dots | `frontend/src/components/CodebookSidebar.tsx` |
| Tile/section/fold CSS | `bristlenose/theme/organisms/codebook-panel.css` |
| Sidebar dot CSS | `bristlenose/theme/organisms/sidebar.css` |

---

## Session update — Q6 (incremental re-apply) is BUILT

Q6 shipped as a backend feature (3 commits: `0605ad7f` persist apply params +
migration 006; `20284c4f` the re-apply engine + auto-trigger; `d88fffd6` the
review fix). Behaviour: add sessions → re-run → on `run_completed`, every
previously-applied framework auto-tags **only the new sessions' quotes**, at the
job's stored cutoff, non-clobbering, no modal; safe no-op otherwise.

Key functions: `reapply_to_new_quotes` / `reapply_active_frameworks`
(`bristlenose/server/autocode.py`), wired into `_make_run_completed_handler`
(`app.py`). **Delta is session-recency based** — quotes from sessions whose
`Session.first_imported_at` postdates the apply (a code review caught that
"quotes with no proposal" wrongly re-coded untagged existing quotes + treated a
clean re-run's re-extracted quotes as all-new; the session-recency delta fixes
both — regression-tested). Unit-tested; true end-to-end (apply → add → re-run)
needs a two-wave fixture + serve QA.

**Judgment calls / follow-ups from the review (not yet done):**
- Re-apply uses the *current* provider, not the job's stored `llm_provider`/
  `llm_model` — reuse the stored one (silent-fail if the default changed).
- The re-apply is `await`-ed in the watcher (blocks back-to-back runs) — make it a
  tracked background task (ties to the progress-surfacing follow-up).
- Threshold fallback is `0.70` when no explicit cutoff was recorded (stricter than
  accept-all's 0.5 default) — decide: mirror 0.5 or stay conservative.
- Mid-confidence review band is silently denied for new quotes (no modal) — maybe
  surface a count later.
- Re-apply covers **all previously-applied** frameworks. _(Trued 2026-07-26 — the
  earlier "Superseded by Decision A: do NOT gate on enabled" note here is itself now
  reversed. The shipped gate is **ever-applied ∩ currently linked ∩ enabled**: Remove
  stops maintenance (the linked check) AND disable stops it (the enabled check). See
  the state-model doc §7/§8 and `reapply_active_frameworks`.)_
- No dedicated progress toast for the re-apply's tagging phase (watcher-initiated,
  so the existing autocode-status poll doesn't cover it) — outcome shows on refresh.
- LLM emitting two tags for one quote → `(job_id, quote_id)` violation rolls the
  whole re-apply back to a silent no-op (edge case, logged).

## Session update — two re-apply decisions settled (25 Jul 2026)

Two questions that the Q6 build left open — *does disable gate re-apply?* and *do
we ever revisit old sessions?* — are now decided. Both reduce to one primitive and
make Phase 1 (persistence) simpler than the "gate on enabled" framing above.

### Decision A — the enable/disable toggle is **view-only**; it never gates re-apply

> **⚠️ SUPERSEDED (26 Jul 2026).** Decision A was **reversed**. Disable is now
> **functional — "off means off"**: it gates re-apply on `enabled` (a disabled
> codebook stops maintaining new sessions), drops the codebook from the tags sidebar
> + autocomplete, and re-enabling fires a one-shot **catch-up delta** over the
> sessions added while off. The "keep coding while off" model below is no longer the
> design. Canonical spec: **[design-codebook-state-model.md](design-codebook-state-model.md)**
> (§7 the delta, §8 settled). Reversed in commit `9744b4e9`; the reasoning that
> replaced this section is §2 (hand-made vs machine-made) and §4a (the watermark).
> The section is kept below for provenance — read it as history, not current design.

"Functional off" was conflating two axes:
- **View off** — fold the panel section + hide the framework's badges *report-wide*.
  This is what "off · kept" means, and it's all the toggle does.
- **Maintenance off** — stop coding new sessions. **The toggle does NOT own this.**

Tying re-apply to *enabled* creates a coverage gap: disable X → add sessions 5–8 →
re-run skips X → re-enable → X covers 1–4 but not 5–8, so "active" silently lies.
The fix is to **not gate on enabled at all.** A disabled-but-installed codebook keeps
quietly coding new sessions in the background (delta-cheap, results retained but
hidden), so re-enable is *always* an instant, free reveal — "re-enabling never
re-spends" (Principle 1) holds literally. The only cost is a few cents coding new
quotes for a hidden codebook, which is just the appliance keeping evidence current.

The intent "stop spending on this" belongs to **Remove** (Library uninstall — drops
the `ProjectCodebookGroup` link, stops maintenance), not the view toggle. This keeps
the three verbs clean:

| Verb | Maintains new sessions? | Reactivation cost |
|---|---|---|
| **Disable** (toggle) | **Yes** — codes, hidden | Re-enable is **free** (already current) |
| **Remove** (Library uninstall) | **No** — link dropped | **Re-add fires the delta** — deliberate spend |
| **Forget** (red, deferred) | No — purges results | Re-add = full re-spend |

The spend-bearing reactivation is tied to the *deliberate* act (Add in the Library),
never the *casual* one (flip a view toggle). Remove's gap self-heals the same way —
while unlinked the watermark doesn't move, so re-add's delta catches every session
that arrived in the meantime. Same mechanism, no new code.

**Consequence for the re-apply gate** (`reapply_active_frameworks`): gate on
**"ever-applied AND currently linked"** (add the `ProjectCodebookGroup` check).
Do **not** add an `enabled` check — the docstring note "once persisted this should
also skip disabled" is now **wrong** and must be deleted. So `ProjectFrameworkState.
enabled` drives **view state only**; no re-apply gate to wire, no backfill-on-enable
machinery.

### Decision B — delta-only on every path; **"already-seen"** is the do-not-touch line

We never "reapply completely" to a session-set that has had new imports — we code
**only the new sessions' quotes**. The earlier sessions already record the user's
opinion: explicitly (accept/reject curation) *or* weakly (the tags they've already
seen in the report). So "don't touch earlier sessions" holds **even if they curated
nothing** — which means this path needs **no "did they curate?" test**.

Verified correctness reason it must stay delta-only: the accept guard is
non-clobbering on *additions* only (it skips an existing `QuoteTag`) but is **blind
to the denied ledger**. A pass that revisited an old session would re-propose a
human-*rejected* tag at high confidence, find no `QuoteTag`, and **resurrect it**.
Delta safety comes entirely from never going back. Plus LLM nondeterminism means
re-coding a seen session could silently move tags the user already looked at.

The whole shipping path collapses to one rule:

> **On any reactivation or re-run: code only quotes from sessions imported after the
> last apply (`first_imported_at > completed_at`). Never revisit an earlier session.**

Covers re-run, re-enable, and Remove→re-add alike. No complete-reapply, no curation
test, no denial-ledger wiring needed to ship.

**Deferred prerequisite (future only):** a **codebook-edit re-apply** — the *one*
case that legitimately revisits old sessions, because editing the framework's tags
or retuning the threshold makes the old coding stale by design. *There*, the "did the
human touch anything?" test gates destructive-vs-preserve (uncurated → safe to blow
away + re-code; curated → refuse or preserving-merge), and *that* is the point at
which the guard must finally learn to respect denials/removals, not just existing
tags. Not on the critical path.

## Persist the enable/disable toggle — Phase 1 (persistence + fold BUILT)

**Built (25 Jul 2026):** the switch is no longer UI-local. `ProjectFrameworkState
(project_id, framework_id, enabled)` (migration 007) + `GET/PUT /framework-states`
(dict map, **absence = enabled**) + `getFrameworkStates`/`putFrameworkStates` in
`api.ts`; `CodebookPanel` hydrates the folded set on mount and PUTs on toggle.
_(Trued 2026-07-26: the "Per Decision A it does not gate re-apply" claim here is
**reversed** — the 26 Jul "off means off" work made the switch **functional**. It now
gates re-apply on `enabled`, drops the codebook from the tags sidebar + autocomplete,
and re-enabling fires a catch-up delta. Read item 1 below as historical.)_ Decisions
settled during the build:
1. ~~**What "disabled" turns off** — view only (fold now; report-wide badge hide is
   the remaining sub-step below). Not a re-apply gate.~~ **(Reversed 26 Jul — disable
   is now functional: fold + report-wide badge hide + sidebar/autocomplete drop + the
   re-apply gate. State-model §5/§8.)**
2. **Reconcile with the group eye-toggle** — a **distinct** per-framework flag
   (chosen), not "framework off ⇔ all its groups hidden". Render will treat a group
   hidden if eye-toggled **or** its framework disabled.
3. **Data model** — `ProjectFrameworkState` (project-scoped, per-framework; not on
   the instance-scoped `CodebookGroup`). Shipped as above.

**Report-wide badge hide — BUILT (25 Jul 2026, option (a)).** The disabled-framework
set now lives in **`SidebarStore.disabledFrameworks`** (module-level, beside
`hiddenTagGroups`), so the codebook fold and the quote-card badge hide read one source
of truth. Shipped:
- `SidebarStore`: `disabledFrameworks` state + `setFrameworkDisabled(fid, disabled)`
  (updates the set + PUTs `{fid: false}`) + `hydrateFrameworkStates()` (fetch-once,
  **guarded** so a Codebook↔Quotes remount can't refetch stale state and clobber an
  in-flight local toggle).
- `CodebookPanel`: local `useState` replaced by the store — the fold reads
  `disabledFrameworks`, the toggle calls `setFrameworkDisabled`, mount calls
  `hydrateFrameworkStates`.
- `TagSidebar`: also calls `hydrateFrameworkStates` on mount, so badges hydrate on the
  Quotes tab even if the Codebook tab was never opened this session (guard makes the
  second call a no-op).
- `QuoteGroup`: `effectiveHiddenGroups = hiddenTagGroups ∪ {groups whose framework is
  disabled}` — `TagGroupInfo` gained `frameworkId` (populated in `QuoteSections` /
  `QuoteThemes` from `g.framework_id`); the badge filter + autocomplete closed-eye
  hint both read the union. The manual-add auto-unhide (`handleTagAdd`) still keys off
  `hiddenTagGroups` only — disabling a framework is a view state, not something a
  single tag-add should silently re-enable.

So a disabled framework now folds its codebook section **and** suppresses its badges
across the report, surviving reload. Tests: `SidebarStore.test` (framework API +
guard), `CodebookPanel.test` (persist + hydrate via the store). One edge left as-is:
adding a tag from a *disabled* framework's group leaves that badge hidden (rare;
noted, not fixed).

## Remaining "Not built" — and parallelizability

The constraint is **file contention on `CodebookPanel.tsx`**, not logic. Buckets:

- **Parallel-safe now (separate files, no deps):** `✦` sparkle retirement
  (`badge.css`/toast — pure mechanical cleanup) · Red ⊖ "Forget" (new backend
  purge, if wanted) · a *presence-based* sidebar dot.
- **Shipped 26 Jul:** the re-apply gate — now **enabled-gated** (`reapply_active_
  frameworks` gates on ever-applied ∩ linked ∩ enabled) · functional **off means off**
  (fold + report-wide badge hide + sidebar/autocomplete drop) · on-enable catch-up
  delta + chip. _(Trued: the earlier "No longer includes enabled-gated re-apply —
  Decision A removed that" note is reversed; enabled-gated re-apply is exactly what
  shipped. State-model §7/§8.)_
- **Shipped 26 Jul (0.22.0):** the sidebar **status dot** (blue on / grey off /
  none for the floor) · the **collapsed summary meta** ("N tags · M coded" when a
  codebook is switched off) · the per-tile **Install / Uninstall** toggle + the
  Add→Install / Remove→Uninstall rename (the "Added" badge → "Installed").
  Uninstall now also drops the `ProjectFrameworkState` row, so reinstalling a
  previously-disabled codebook returns it **enabled**, not folded/greyed (server
  `remove_framework` + client `dropFrameworkDisabled`, both regression-tested).
- **Deferred — the fold animation.** The group columns are `auto-fill` grid items
  with auto height, and `.codebook-group` is shared with researcher groups + the
  preview modal, so a clean both-directions height-fold needs a delayed-unmount
  state machine or wrapping the shared component; a blanket mount-fade would add
  page-load motion (against the motion-restraint bar). Not worth the polish it
  buys — the summary-meta crossfade already covers the fold boundary. Revisit only
  if a proper accordion primitive lands.
- **Deferred — Uninstall-from-Library in place.** A tile's Uninstall closes the
  Library then opens the remove-with-impact confirm, rather than confirming over the
  still-open Library (the "one footprint" ideal). Cause: the confirm overlay is
  z-index 150, the picker 200, so in-place stacking needs a z-index change to the
  shared merge-confirm — a taste refinement, not a bug.
- **i18n follow-up — DONE, 21 Aug 2026, and it was bigger than this line said.**
  `codebook.foldedSummary` is seeded in all 19 locales with the plural shapes
  described (ko + zh-Hant `_other`-only; cs/pl/ru/uk four forms; the rest
  `_one`/`_other`; zh-Hant-HK inherits). The rename drift was **13** keys, not 10 —
  `browseCodebooks`, `browseTitle`, `browseSubtitle`, `previouslyImported`,
  `importCodebook`, `importingCodebook`, `importHelp`, `autoCodeQuotes`,
  `removeFromCodebook`, `hideTitle`, `autoCodePreserved`, `restoreAnytime`, `hide` —
  and it had been live since `7530106e`/`e8745070` in July without anyone noticing,
  because a key that is present on both sides is invisible to `check-locales.py`.
  The worst of them labelled one button **"Apply"** in English and **"✦ AutoCode
  citas"** in Spanish. Install / Uninstall / Apply are Apple's own imperatives,
  measured from the shipping macOS loctables and recorded in
  `bristlenose/locales/glossary.csv`; all 13 × 19 are machine-seeded and owe a
  native pass. Full account: `docs/i18n-defects.md` item 10.

Highest-leverage next: the persistence flag (now view-only, so smaller). Best
parallel win meanwhile: the `✦` sweep (isolated, mechanical) or the re-apply gate
fix (backend-only, isolated).

## Outstanding calls (post-review, 25 Jul 2026)

The enable/disable feature was reviewed (code-review + silent-failure-hunter). The
clearly-correct fixes shipped (`d94d8f44`, `cd70dd36`): re-apply per-quote dedup
(stops a duplicate-tag IntegrityError rolling back the watermark → perpetual silent
re-fail); `firePut` now checks `resp.ok` (a failed PUT was fully silent — the
dropped-auth masquerade); hydrate-race generation guard; dead `[projectId]` dep
dropped. What's left are **product/design decisions**, not bugs:

1. **Export HTML doesn't sanitise hidden badges.** Disabling a framework (or
   eye-toggling a group) hides badges in-app, but the exported HTML deliverable
   embeds neither `framework-states` nor `hidden-tag-groups`, so **the badges
   reappear in the file you share.** Consistent between the two toggles, but
   "disable = report-wide hide" reads like deliverable sanitation in a way the eye
   toggle never claimed. *Call: should either toggle sanitise the export?* If yes,
   embed both in the export payload + `resolveFromExport`. **Detailed capture for a
   future export session: [design-export-hidden-badges.md](design-export-hidden-badges.md)**
   (root cause, the is_hidden precedent, parity-vs-sanitation fork, touchpoints).
2. **Manual-add to a disabled framework's group is an invisible success.** You add a
   tag, it persists, but the badge stays hidden (filtered by `effectiveHiddenGroups`)
   with no feedback. *Call: auto-enable the framework on add (mirroring the eye-
   toggle auto-unhide), leave it hidden (disable is absolute), or toast "framework
   is off"?*
3. **Fire-and-forget PUT lost-update ordering.** Two rapid toggles fire two full-
   replacement PUTs; out-of-order landing keeps the stale one until reload. Identical
   for `hiddenTagGroups` (house style) — but the framework switch is lower-frequency
   and spend-adjacent. *Call: accept eventual-consistency-on-reload for all view-
   toggles, or add a sequence token / awaited write to this one?*
4. **Toast on a failed background sync.** `firePut` now *logs* a failed PUT; the
   vanilla `apiPut` path *toasts*. *Call: do view-toggle sync failures warrant a
   user-visible toast, or is a console line enough for a best-effort sync?*

Remaining unbuilt **Library polish** (unchanged from the parallelizability buckets
above): the serialized `CodebookPanel.tsx` pass (fold animation · collapsed summary
meta · header reconciliation · Add↔Remove + dialog relocation · "Your codebooks" ·
80%-dim tiles); sidebar dots (`CodebookSidebar.tsx`, wireable to the now-persisted
enabled state); Red ⊖ "Forget"; and the `✦` retirement — which lives in **20 locale
`common.json` files** (AutoCode toast + `autoCodeQuotes`), so it belongs to the
deferred i18n-propagation pass, not the "isolated CSS cleanup" the bucket above
assumed (correction: the `✦` is data, not code).
