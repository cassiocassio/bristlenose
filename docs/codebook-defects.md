---
status: active
last-trued: 2026-08-27
trued-against: HEAD@main 0b1f1857 on 2026-08-22
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

| # | Defect | Anchor | Effect |
|---|---|---|---|
| **A1** | `remove_framework` deletes `QuoteTag` rows by `tag_definition_id` with no project filter | `server/routes/codebook.py:867` | Uninstalling a framework in one project deletes that framework's applied tags in **every** project on the instance |
| **A2** | `import_template`'s restore path resets `accepted` proposals to `pending` by `tag_definition_id` alone | `server/routes/codebook.py:764` | Installing a codebook in one project un-decides another project's completed review |
| **A3** | `restorable_ids = all_fw_ids - imported_ids` is computed across the whole database | `server/routes/codebook.py:671` | A project that never had a codebook offers *"Previously installed — reinstall instantly"* |

**Not reproduced.** All three are read from source. The first move is a
two-project repro, not a patch — if the scoping turns out to be intentional
somewhere upstream, the fix changes shape.

---

## B · The copy says something untrue

| # | Defect | Anchor | Note |
|---|---|---|---|
| **B1** | `codebook.autoCodeQuotes` is `"Apply"` — the spec is `"Apply to {{count}} quotes"` | `locales/en/common.json` | The count carried the whole cost-honesty argument: it sizes the spend before you commit. One string plus one interpolation |
| **B2** | `codebook.restoreHelp` promises *"Restores previous tags and AutoCode results"* | `locales/en/common.json` | Tags are **not** restored — A1 deleted them. Proposals come back as `pending`. The copy describes a restore that does not happen |
| **B3** | `.picker-card.imported::after { content: "Installed" }` — hardcoded in CSS | `theme/organisms/codebook-panel.css:762` | Unlocalised in all 21 locales. This is the *exact* defect the Library doc named as its reason for replacing the badge with a button; the button was added and the badge kept |
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

---

## E · The doc is the thing that is wrong

| # | Stale claim | Reality |
|---|---|---|
| **E1** | Library doc, Outstanding call 1: *"the exported HTML embeds neither `framework-states` nor `hidden-tag-groups`"* | Both are embedded — `server/routes/export.py`, the `"/framework-states"` and
`"/hidden-tag-groups"` entries in the embed map (no line number: that file is
under concurrent edit, so grep it). The *design* question (should a view toggle sanitise a deliverable?) is still real; the mechanism it rested on has changed |
| **E2** | `CodebookSidebar.tsx` header comment: *'Three sections: "Your tags", "Built-in", "Frameworks"'* | Renders "Manual tags", "Default", "Library". The comment is the only place the old names survive |
| **E3** | `remove_framework` docstring: *"Hide a framework from the project"* | It uninstalls, and it deletes. "Hide" was the retired third metaphor the 26 Jul rename existed to kill — it survives in the docstring of the function doing the deleting |

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
