---
status: active
last-trued: 2026-08-31
trued-against: HEAD@main 8fee4ead on 2026-08-31
---

# Codebook defects — the running register

**What this is:** the gap between what the codebook docs specify and what the
codebook lens does, found by reading the code against the docs on 22 Aug 2026.
Each row is implementable. Nothing here is a wording question.

**What it is not:** the design record. `design-codebook-state-model.md` is
canonical on behaviour, `design-codebook-library.md` on layout (and *only*
layout — its disable-semantics half was reversed the day after it was written).
This file holds what neither of them can: where the tree disagrees with both.

**Why a file and not a test.** Every row below passed the full suite, `ruff`,
and `check-locales.py` at the moment it was found. A string that exists on both
sides is invisible to the locale gate; a control that renders but does nothing
is invisible to everything. Same reasoning as `i18n-defects.md`, one surface
along.

**How to use it.** Strike a row when it lands, with the commit. Add one the
moment you notice, even mid-unrelated-work.

## Changelog

- _2026-08-31_ — **A5 opened and struck the same day** (the framework-states
  full-replacement defect, found while the switch was being fixed). Read against
  the v1 deletion: seven rows struck across the phase-5 pass and the cutover, and
  five more dissolved rather than fixed — C1, C3, C4, C5 and E2 all described
  surfaces that `baa1aa0e` deleted. Marked in place; a dissolved row is not a
  fixed one and the distinction is the point.
- _2026-08-27_ — register opened. Rows A1–A3 and the "Your codebooks" strike
  come from the 22 Aug read; the flow decomposition below is the substrate the
  wireframe reversal is being built on.

---

## A · Correctness — these lose data

The codebook's group and tag rows are **instance-scoped by design**
(`CodebookGroup`: *"groups live in a shared library"*), but three queries that
act on them filter by tag id alone, with no project predicate. `QuoteTag` has no
`project_id` — only `Quote` does. This was harmless while an instance meant one
study. **0.26.0 ships N studies at once.**

**A5 is a different mechanism** — not a missing predicate but a client sending a
partial body to a replacement endpoint. It belongs here because section A is
about losing what the researcher decided, whichever route the loss takes; A5
also spends money doing it.

| # | Defect | Anchor | Effect |
|---|---|---|---|
| ~~**A1**~~ ✅ **fixed** — the delete is project-scoped (`QuoteTag.quote_id.in_(project_quote_ids)`) and the impact count matches. Landed in the phase-5 pass; struck 31 Aug 2026. | `remove_framework` deletes `QuoteTag` rows by `tag_definition_id` with no project filter | `server/routes/codebook.py:867` | Uninstalling a framework in one project deletes that framework's applied tags in **every** project on the instance |
| ~~**A2**~~ ✅ **fixed** — the accepted-proposal reset is gone; the code now says so in place. Struck 31 Aug 2026. | `import_template`'s restore path resets `accepted` proposals to `pending` by `tag_definition_id` alone | `server/routes/codebook.py:764` | Installing a codebook in one project un-decides another project's completed review |
| **A4** | Sentiment can be uninstalled, and nothing can restore it | `routes/codebook.py:867` + `importer.py:1397` | Uninstalling sentiment deletes every sentiment `QuoteTag`. Sentiment tags are `source="pipeline"` and **bypass `ProposedTag` entirely**, so the restore path — which relinks groups and resets *accepted proposals* to `pending` — has nothing to restore. Reinstalling returns the groups with every count at **zero**, and only a full pipeline re-run repopulates them. Reachable two ways: the Library tile's Uninstall, and the section header's **v2 status (29 Aug):** the *affordance* is gone — sentiment has no install or uninstall control on either the page or the browse card (`design-codebook-v2.md` D20). The **endpoint is unchanged**, so A4 stays open as a server-side fix at much lower priority: nothing in the UI can now reach it. |
| ~~**A3**~~ ✅ **retired** — `restorable` is gone with D20 option A. Struck 31 Aug 2026. | `restorable_ids = all_fw_ids - imported_ids` is computed across the whole database | `server/routes/codebook.py:671` | A project that never had a codebook offers *"Previously installed — reinstall instantly"* |
| ~~**A5**~~ ✅ **fixed** — the navigator computes the whole disabled set from the same array that feeds the optimistic render, so the write cannot disagree with what is on screen, and mirrors that set into `SidebarStore` so the lenses reading the switch from there agree too. Three regression tests, each watched failing on the pre-fix code. Struck 31 Aug 2026, commit *"a switch that could only turn one codebook off, and a store that never heard about it"*. | The navigator sent a single-key patch to a **full-replacement** endpoint | `frontend/src/components/CodebookV2Sidebar.tsx` `onToggle` + `server/routes/data.py` `put_framework_states` | `put_framework_states` deletes every `ProjectFrameworkState` row for the project and re-inserts only what the body carried — its own docstring says *"PUT replaces the entire stored map. Absence means enabled."* The navigator wrote `{ [id]: enabled }`, so switching a second codebook off wiped the first one's `false` row and switched it back **on**: one codebook off at a time, with nothing on screen to say so. **The money half:** absence reads as an OFF→ON transition, so each wiped row went to `_start_catch_ups`, and any with a completed job and newer sessions began a catch-up AutoCode delta — LLM spend from flipping an unrelated switch. **The second half, found by the doc audit that followed:** `onToggle` persisted without mirroring into `SidebarStore`, whose hydration is once-per-session from `TagSidebar`'s mount alone, so quote badges, the Quotes tag sidebar and autocomplete kept showing a switched-off codebook until a reload. Written in `3cdf085e`, unreachable until v1's deletion made this navigator the only door to the switch (`baa1aa0e`), shipped in **0.29.0**, fixed in **0.29.1** |

**On reproduction.** A1–A4 were read from source and the note here used to say
the first move was a two-project repro, not a patch. A1 and A2 were then patched
without one. That was the right call for those two — the scoping was
unambiguous — but the note is left standing for A4, which is still unreproduced
and where an upstream intention would change the shape of the fix.

**A5 is the exception that earned its place:** it was reproduced before it was
fixed, in the app and then in a test that was watched failing on the pre-fix
code. Section A is otherwise a source-read register, and the difference in
confidence between the two kinds of row is worth keeping visible.

---

## B · The copy says something untrue

| # | Defect | Anchor | Note |
|---|---|---|---|
| **B1** | `codebook.autoCodeQuotes` is `"Apply"` — the spec is `"Apply to {{count}} quotes"` | `locales/en/common.json` | The count carried the whole cost-honesty argument: it sizes the spend before you commit. One string plus one interpolation |
| **B2** | ~~`codebook.restoreHelp`~~ → **repointed 31 Aug 2026.** `restoreHelp` is now an orphan with no call site. The live falsehood was `codebook.autoCodePreserved` on the v1 uninstall confirm — *"AutoCode results are preserved — reinstall any time"* — while `remove_framework`'s own docstring says **"Nothing is preserved."** ✅ **fixed**: both arms of that dialog now take `restoreAnytime`, which is true of both. | `CodebookPanel.tsx:688` | Was a false reassurance on a **destructive confirmation**, in 21 locales, on the one screen a researcher reads before losing reviewed proposals. **A test pinned it** (*"hide dialog mentions preserved AutoCode results"*) — the suite was defending the lie, which is why no gate could ever have caught it. Test flipped to assert the truth |
| **B3** | `.picker-card.imported::after { content: "Installed" }` — hardcoded in CSS | `theme/organisms/codebook-panel.css:762` | Unlocalised in all 21 locales. This is the *exact* defect the Library doc named as its reason for replacing the badge with a button; the button was added and the badge kept |
| ~~**B6**~~ ✅ **fixed** — `framework_quote_totals` is computed server-side as distinct quotes per framework and consumed by `summariseFramework`. Struck 31 Aug 2026. | Framework-level quote counts **overstate** | `frontend/src/utils/codebookSummary.ts` | `total_quotes` is `len(seen_quotes)` — distinct *within a group* (`routes/codebook.py:248`). `summariseFramework` then **sums** across groups, so a quote carrying tags from two groups of the same framework counts twice. The shipped `codebook.foldedSummary` ("N tags · M coded") therefore overstates whenever a framework's groups overlap on a quote. No distinct framework-level count is exposed by the API |
| **B7** | The codebook author renders in **four** places, one of which is easy to miss | `TagSidebar.tsx:619` | `.codebook-author` renders the author in the **Tag sidebar on the Quotes lens** — a surface outside the codebook lens entirely, and the one any change to the author treatment will forget. The four sites: `.codebook-author` (Quotes tag sidebar, badge/muted), `.picker-card-author` (Library tile, label/muted), `.framework-section-author` (codebook section header, label/muted), `.preview-author-name` (preview author card, label/**emphasis**). Not a defect on its own — see the correction in `design-codebook-v2.md` D19 — but any v2 author treatment must cover all four |
| **B5** | `.proposed-count` hardcodes `rgba(37, 99, 235, 0.08)` | `theme/organisms/codebook-panel.css:621` | That is the **light-mode** accent. Dark mode resolves `--bn-colour-accent` to `#0a84ff` and `palette-edo` to `#0f5c9e`, so the count pill's tint is wrong on **two of the four theme combinations** — the same hardcoded-blue class the island doc's decision 6 fixed for `.merge-target` with `color-mix()`, missed here |
| **B4** | The `✦` sparkle is half-retired | `locales/*/common.json` | `autocode.toast.{progress,done,failed,failedWithError}` and `autocode.chip.{coding,coded}` still carry it; the Apply button is clean. Exactly the half-sparkled outcome Q5's "one coordinated pass" clause existed to prevent. It is locale **data** in 21 files, not a CSS sweep |

---

## C · Specced, never executed

| # | Defect | Note |
|---|---|---|
| **C1** | Apply never morphs into the switch | Spec: *"once applied, the button is spent and the switch takes over."* Shipped: Apply, Uninstall and the switch are all permanently present in the section header. Apply only ever becomes "View Report" |
| **C2** | No install landing | Spec: Install closes the modal and anchor-scrolls to the new section, Apply in the eyeline. Shipped: tile install keeps the Library open; preview install closes it but does not scroll. Two paths, neither of them the specced one — and C1's calm button weight was predicated on this scroll doing the work |
| **C3** | The lens still carries a "Remove from Codebook" button | Spec: gone, the impact dialog relocates to the Library tile. Shipped: both exist. The dialog was relocated by *addition* |
| **C4** | Library modal has no focus trap, no `useInert`, no Escape handler | `ThresholdReviewModal` has all three. The Library overlay closes on scrim click or the ✕ only |
| **C5** | Adding a tag to a *disabled* framework's group is an invisible success | Persists, badge stays hidden, no feedback. Logged as an open product call in the Library doc since 25 Jul; still open |

---

## D · Dead or unreachable

| # | Defect | Note |
|---|---|---|
| **D1** | `AutoCodeReportModal.tsx` has no production consumer | Only its own test file imports it; `ThresholdReviewModal` replaced it. Its 7 `autocode.report.*` strings are orphans in 21 locales, and it holds the last `&#x2726;` in the component tree |
| **D2** | All nine templates ship `enabled: true` | So `codebook.comingSoon`, `.picker-card.disabled` and the `isClickable` guard have never rendered for a user, and have never been visually checked |
| **D3** | Denied proposals are terminal in the UI | The review modal filters to `status === "pending"`, so a denied proposal never appears in any surface again — though it is deliberately retained as telemetry. No route back. This is the state model's open **Q-C** |
| ~~D4~~ | ~~"Your codebooks" section header + "+ Create new codebook" tile whose only handler closed the modal~~ | **Landed `0b1f1857`, 22 Aug 2026.** Header, tile, `.picker-card-create` CSS and two dead strings across 21 locales removed. The feature stays specced (Library doc Q2) and a comment at the site says to restore header and tile together |
| **D5** | ~~Five~~ **30** orphaned locale strings with no call site | `bristlenose/locales/en/common.json:527, 538–542, 545–547, 551`, ×21 locales. **Anchor corrected 31 Aug 2026** — this row previously cited `:532,535-537,549`, which are `availableByDefault`, `tagCount_*` and `appliedToQuotes_*`: all **live** keys the navigator renders. Verified by grepping each key against `frontend/src` minus tests. Also renumbered from D4, which collided with the struck D4 above, and moved out of section E, where it had been sitting as a four-cell row in a three-column table. `codebook.restoreCodebook`, `restoringCodebook`, `restoreHelp`, `previouslyImported` died with D20 option A; `autoCodePreserved` died 31 Aug 2026 when the false promise was removed. Left in place rather than swept — a file-wide regex over 21 locale files is the documented way to delete a same-named key in another namespace by accident. Remove deliberately, per-namespace. **Updated 31 Aug 2026:** v1 has now gone, and the orphan count went 5 → 30 with it — the whole `browseTitle` / `foldedSummary` / `errorLoading` family belonged to `CodebookPanel`. Still not swept, for the same reason: a file-wide regex over 21 locale files is how a same-named key in another namespace gets deleted by accident (it took `menu.edit.undo` out of all 21 on 19 Aug 2026, and `check-locales.py` stayed green because English lost it too). Enumerate the keys, delete by fully-qualified path, and diff one locale before repeating |

---

## E · The doc is the thing that is wrong

| # | Stale claim | Reality |
|---|---|---|
| **E1** | Library doc, Outstanding call 1: *"the exported HTML embeds neither `framework-states` nor `hidden-tag-groups`"* | Both are embedded — declared in `EMBED_PATH_TEMPLATES` at `server/routes/export.py:59-60` and written at `:480-481`. **Anchors added 31 Aug 2026:** this row previously refused a line number because the file was under concurrent edit, and the row was also broken across three physical lines, so it rendered as a two-cell row in a three-column table and no reader ever saw the Reality column. The *design* question (should a view toggle sanitise a deliverable?) is still real; the mechanism it rested on has changed |
| **E2** | `CodebookSidebar.tsx` header comment: *'Three sections: "Your tags", "Built-in", "Frameworks"'* | Renders "Manual tags", "Default", "Library". The comment is the only place the old names survive |
| ~~**E3**~~ ✅ **fixed** — the docstring now reads *"Uninstall a framework from this project. Nothing is kept for a restore."* Struck 31 Aug 2026. | `remove_framework` docstring: *"Hide a framework from the project"* | It uninstalls, and it deletes. "Hide" was the retired third metaphor the 26 Jul rename existed to kill — it survives in the docstring of the function doing the deleting |

---

## The flow

Reversing wireframes out of the implementation, flow first. Five FigJam
diagrams, one board — 35+ elements in a single chart is unreadable, and these
are five coherent loops:
[figma.com/board/2H7rrbqAP5J1ic5Zmkyo32](https://www.figma.com/board/2H7rrbqAP5J1ic5Zmkyo32)
(access-controlled).

1. **Ways in and the lens** — four entry points, the route, every element, and what export mode strips
2. **Install and uninstall** — tile states, the two install paths, the impact confirm
3. **Apply and review** — the only path that spends
4. **Authoring your own codes** — group and tag CRUD, the three drag gestures, which Codes-menu items land somewhere
5. **Enable, disable and reach** — the switch, and where hide and disable diverge

Three things only became visible once it was drawn as a flow, and all three are
rows above: the install axis is a **lossy cycle** (A1 + B2), **denied is a dead
end** (D3), and the **thresholds are a default rather than a gate** — you can
accept from the Exclude zone and deny from the Accept zone, so the slider
proposes and the rows dispose.

## What to build next

The wireframe inventory falls out of the flow instead of being guessed at.
Every box that is a *surface* needs a frame; every box that is a *state* becomes
a variant. That is ~12 frames — the lens in five states (floor only, installed
not applied, applied enabled, disabled/folded, export), the picker, preview ×2,
review ×3, the impact confirm, and three inline confirms.

Method is already settled and should be honoured rather than re-litigated:
`design-figma-setup.md` says **bootstrap by import, not by redraw**, the Figma
copy is a **stamp, not a live component**, and if Figma and CSS disagree, **CSS
wins**. Two constraints that doc predates and that bite this lens specifically:
the codebook's ~99 colour tokens are authored in **OKLCH**, which Figma
variables cannot hold; and there are **two palettes** (`palette-default` web,
`palette-edo` desktop) × light/dark, against the doc's assumption that two
variable modes is enough.
