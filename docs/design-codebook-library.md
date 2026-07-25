# Codebook Library — design & build plan

**Status:** design settled; partially built. **Shipped** (commits `7530106e`,
`c62e611f`): vertical full-width Library tiles + de-greened "Added" badge; the
Library/Add/Apply string renames (de-sparkled); and the **framework enable/disable
switch** (trailing macOS-matched switch, off collapses the framework's tag-group
columns — UI-local fold, tags kept). **Not yet built:** fold *animation*, collapsed
summary meta, Add↔Remove install toggle, sidebar dots, and the functional
"hide-from-analysis" + persistence behind the switch (currently visual-only). Mock:
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

1. **Cost-safe play.** Getting a codebook onto your workbench is free. **Apply**
   (AutoCode) is the *one* deliberate spend. Disabling and re-enabling never
   re-spend — results are retained. (No `✦` marker: the sparkle is **dropped from
   the Apply button** — decided. The wider system-wide `✦` retirement leans yes;
   deferred to its own pass — Q5.)
2. **Retention is visible.** Disabling **folds** the tag groups to a single line;
   it never deletes them. A folded disclosure self-evidently still contains its
   contents — no reassurance copy required.
3. **No control does two jobs; no surface does two jobs.** The Library is a
   catalogue (browse + Add). Your codebook is the workbench (Apply, toggle, fold).
   The sidebar is status only. A control that looks operable *is* operable.
4. **Colour maps to cost.** No red on anything reversible. Red is reserved for the
   one genuinely destructive action — **Forget** (purge retained results, so
   re-adding would re-spend) — which is *deferred*, not built now.

## The three surfaces

| Surface | Job | Verbs |
|---|---|---|
| **Codebook Library** (modal) | catalogue — the *install axis* | **Add ↔ Remove** (one toggling button) |
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
Not added ──[Add]──▶ Added ──[Remove]──▶ Not added   (one toggling button, both states)
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
- **Red ⊖ "Forget"** — the lone destructive action (purge retained results → would
  re-spend). Only place red belongs.
- **19-locale propagation** of the new/changed strings.
- **"Add & Apply" fast path** — ship the safe default (separate Apply); add the
  shortcut only if the cohort asks (a mis-click on a combined button is the exact
  surprise-spend we're avoiding).
- **Incremental sessions × active codebooks** — the cross-feature re-apply question
  (see Open Q6). Parked; needs the incremental path to be additive first.

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
   (Parked — cross-feature with incremental analysis; needs the incremental path to
   be additive first.) **Intuition: yes** — an *enabled + applied* codebook should
   cover *all* project quotes, or "active" is a silent lie (new quotes uncoded). But
   re-applying spends, so it must respect cost-safe-play. Shape:
   - **Scope:** only *enabled + applied* codebooks re-apply; disabled (off·kept) and
     never-applied ones don't (consistent with the enable axis).
   - **Delta only:** code just the NEW quotes — never re-code existing ones, never
     clobber human-provenance tags (`QuoteTag.source == "human"`). Prerequisite:
     incremental re-analyse must become *additive*, not destructive (it currently
     isn't — see `project_incremental_analysis`).
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
- Re-apply covers **all previously-applied** frameworks. *Superseded by Decision A
  (below): keep it that way — do NOT gate on enabled; add a "currently linked"
  check instead so Remove stops maintenance.*
- No dedicated progress toast for the re-apply's tagging phase (watcher-initiated,
  so the existing autocode-status poll doesn't cover it) — outcome shows on refresh.
- LLM emitting two tags for one quote → `(job_id, quote_id)` violation rolls the
  whole re-apply back to a silent no-op (edge case, logged).

## Session update — two re-apply decisions settled (25 Jul 2026)

Two questions that the Q6 build left open — *does disable gate re-apply?* and *do
we ever revisit old sessions?* — are now decided. Both reduce to one primitive and
make Phase 1 (persistence) simpler than the "gate on enabled" framing above.

### Decision A — the enable/disable toggle is **view-only**; it never gates re-apply

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
`api.ts`; `CodebookPanel` hydrates the folded set on mount and PUTs on toggle. Per
Decision A it does **not** gate re-apply. Decisions settled during the build:
1. **What "disabled" turns off** — view only (fold now; report-wide badge hide is
   the remaining sub-step below). Not a re-apply gate.
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
  purge, if wanted) · a *presence-based* sidebar dot · the re-apply gate fix
  (add the `ProjectCodebookGroup`-linked check + delete the stale "skip disabled"
  docstring note in `reapply_active_frameworks` — backend-only, per Decision A).
- **Blocked on the persistence flag above:** functional **view** off (fold +
  report-wide badge hide) · blue-dot-means-enabled. *(No longer includes
  "enabled-gated re-apply" — Decision A removed that.)*
- **Must serialize (all touch `CodebookPanel.tsx` — one frontend session):** fold
  animation · collapsed summary meta · header reconciliation (drop Remove, morph
  AutoCode→switch) · Add↔Remove + dialog relocation · "Your codebooks" section ·
  80%-dim tiles.
- **i18n-careful (touch all 20 locale files — collide with concurrent i18n):**
  19-locale propagation · the summary-meta's new keys.

Highest-leverage next: the persistence flag (now view-only, so smaller). Best
parallel win meanwhile: the `✦` sweep (isolated, mechanical) or the re-apply gate
fix (backend-only, isolated).
