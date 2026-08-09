# Lens-wide design-system audit — diagnose and fix

**Status:** Plan, awaiting review + triage (6 Aug 2026). Nothing implemented.

Extends the **design police** method from `docs/design-dashboard-widgets/design-police.md`
from one parked widget effort to **all six lenses**. That doc is the method and stays the
method; this doc is the campaign that applies it, in sequence, with the tooling that makes
it repeatable instead of a one-off read-through.

The first-pass findings are in §3. They came from a manual sweep — which is exactly the
problem: **the audit is not reproducible.** Phase 0 fixes that before anything is fixed at
all.

---

## 1. What we already have (reuse, don't rebuild)

| Asset | State | What it's used for here |
|---|---|---|
| `docs/design-dashboard-widgets/design-police.md` | Live, scoped to widgets | **The method.** Two-outcome rule (refactor to an atom / flex-and-log), the mirror rule, the Lucide icon policy, the delta-ledger format. Generalise scope; change nothing else. |
| `docs/design-system/INVENTORY.md` | Live, drifted (3 files missing) | The CSS surface catalogue. Becomes **generated**, not hand-maintained (Phase 2). |
| `docs/design-react-component-library.md` | Marked *Complete (Feb 2026)* | The 16-primitive dictionary + coverage matrix. **Not complete** — ~25 page-local components never entered it. Reopen and extend (Phase 5). |
| `docs/design-system/style-guide.html` | Live, 78KB | The visual catalogue. Has a fatal flaw — it **re-declares tokens as a hardcoded subset** in its own `<style>` block, so it drifts from `theme/` silently. Fix by importing the real CSS (Phase 2). |
| `docs/design-system/icon-catalog.html` | Feb 2026, stale | Already structured as exactly the three drifting layers (*Inline SVG / Unicode / CSS pseudo-element*). It diagnosed the icon problem five months before design-police named it. **Revive as the icon migration tracker** (Phase 3). |
| `typography.html`, `typography-stress-bench.html`, `buttons.html` | Live | Per-domain specimens. Fold into the catalogue's tier pages. |
| `_discover_design_files()` — `bristlenose/server/routes/dev.py:274` | Live | Auto-lists `docs/design-system/*.html` in About→Design. **Free distribution** — any new catalogue page appears in-app with zero wiring. Note the non-recursive glob (subfolders vanish). |
| `SpecimenTab` / `GridSpecimen` / `TypeScalePreview` / `PlaygroundStore` | Live, lazy-loaded, dev-gated | A live in-app specimen lens that already code-splits and is excluded from the bundle gate. **Host for the live catalogue** (Phase 2) — no new surface needed. |
| `docs/design-figma-setup.md` | Live | The Figma token pages. Claims to be "mirrors of the CSS tokens, not a parallel system" — **it is not a mirror** (see §3, finding D). Reconcile in Phase 1. |
| `.claude/skills/usual-suspects/` | Live | The review process for each phase gate. |
| Figma MCP + `figma-code-connect` skill | Available, no `.figma.ts` files exist | The design↔code naming bridge. Optional, Phase 2 decision point. |

## 2. What we borrow from outside (prior art)

We are a one-person system with two render paths and three consumers (web SPA, static
render, native shell). The prior art that fits that shape:

| Source | What we take | Where it lands |
|---|---|---|
| [stylelint-value-no-unknown-custom-properties](https://stylelint.io/awesome-stylelint/) | Fails on a `var(--x)` that no token defines. Would have caught `--bn-colour-danger` the day it was written. **Highest leverage single tool for this codebase.** | Phase 0 (report), Phase 1 (error) |
| [stylelint-declaration-strict-value](https://github.com/AndyOGo/stylelint-declaration-strict-value) | Requires a token (not a literal) for named properties — colour, spacing, radius. | Phase 0 (report), Phase 6 (error) |
| [Omlet CLI](https://www.npmjs.com/package/@omlet/cli) (`@omlet/cli`, [Zeplin](https://github.com/zeplin/omlet)) | Static React component analytics — "see what new custom components are being created and review whether they should be added to your design system". Automates the page-local-component finding permanently. | Phase 0 |
| [DTCG format + Style Dictionary 4](https://styledictionary.com/info/dtcg/) — spec [stable since Oct 2025](https://www.w3.org/community/design-tokens/) | One token source → CSS custom properties + Swift constants + Figma variables. The only real fix for the web/native/Figma three-way drift. | Phase 1 decision point |
| [Brad Frost, *Maintaining Design Systems*](https://atomicdesign.bradfrost.com/chapter-5/) | The **interface inventory** as a recurring ritual, not a launch task. | Phase 6 cadence |
| [Nathan Curtis, *Naming Tokens in Design Systems*](https://medium.com/eightshapes-llc/naming-tokens-in-design-systems-9e86c7444676) and [*On Classification*](https://medium.com/eightshapes-llc/on-classification-in-design-systems-6b33b97f4a8f) | Taxonomy discipline — the vocabulary for settling our three-way naming split. | Phase 2 |
| [Design-system maintenance practice](https://www.magicpatterns.com/blog/design-system-maintenance) | Quarterly audit cadence as the sweet spot; a component **lifecycle with an owner** prevents more drift than any review checklist; watch for components that technically use the library but override so many props they've gone custom. | Phase 6 |

Deliberately **not** adopting: Storybook (a third render path for a system that already
struggles with two), and any hosted design-system SaaS (Supernova/Knapsack/Backlight —
priced and shaped for teams).

## 3. Diagnosis so far

The full first-pass findings are in the audit conversation and get transcribed into the
ledger in §6. Two are worth stating up front because **they change the sequence**:

**A. The spacing bypass is the scale's fault, not the authors'.**
236 raw px/rem declarations vs 567 tokenised (~29% bypass). But the raw values cluster
precisely in the token gaps:

| Raw value | Uses | Sits between |
|---|---:|---|
| `0.2` / `0.25` / `0.3rem` | 68 | `xs` 0.15 → `sm` 0.35 |
| `0.4` / `0.45` / `0.5` / `0.6rem` | 50 | `sm` 0.35 → `md` 0.75 |
| `0.15` / `0.35rem` written literally | 21 | *is* a token, written as a number |

The scale is 2.4 / 5.6 / 12 / 24 / 32px. It has one usable stop (5.6px) across the entire
2.4–12px band where all chrome density actually lives. **Linting the bypass away first
would force 118 sites onto values that don't exist.** Fix the scale, then lint.

**B. Three colour tokens are used but never defined.** `--bn-colour-danger`,
`--bn-colour-success`, `--bn-colour-warning`: zero definitions, ~20 use sites, every one
silently rendering its hex fallback and therefore blind to `data-color-theme`. This is the
pattern the linter in Phase 0 exists to make impossible.

**C. The catalogue drifts because it re-declares the system.** `style-guide.html` opens
with `/* Bristlenose design tokens (subset for this guide) */` and hardcodes them. A
catalogue that copies the system cannot audit the system.

**D. The Figma "mirror" is not a mirror.** `design-figma-setup.md` states its tokens
mirror the CSS. They don't:

| | Figma | CSS |
|---|---|---|
| space xs / sm / md | 4 / 8 / 16 | 2.4 / 5.6 / 12 |
| radius sm / lg | 4 / 10 | 3 / 8 |

Three of five spacing stops and two of three radii disagree. Any pixel-alignment work done
against that file has been measuring against the wrong ruler.

---

## 4. The phases

Each phase ends at a gate: `/usual-suspects` review, then Martin triages before the next
starts. Phases are sequenced by **dependency**, not by size.

### Phase 0 — Make the audit reproducible

*Nothing is fixed in this phase. This is diagnosis only.*

Why first: a manual sweep found these problems once. It will not find them again in three
months, and it cannot measure whether any fix worked. Every later phase needs a baseline
number to move.

- Add `stylelint` to `frontend/` with `value-no-unknown-custom-properties` and
  `declaration-strict-value`, both **report-only** (`--quiet` in CI, no gate).
- Promote the two throwaway sweeps to committed scripts under `scripts/design-audit/`:
  orphan-class detection (TSX `className` with no CSS home), and the raw-value/breakpoint
  histogram from §3A.
- Run `@omlet/cli` over `frontend/src` for the component-usage graph — confirm or correct
  the ~25 page-local components counted by hand.
- Output: `docs/design-system/AUDIT.md`, regenerated by one command, with the baseline
  counts as of today.

**Exit:** `just design-audit` (or equivalent) prints the numbers. They match §3.

### Phase 1 — Fix the source of truth

Why here: the catalogue renders tokens and the components consume them. Fixing either
before the tokens are right means doing it twice.

- **Re-cut the spacing scale.** §3A is the evidence; the 118 gap-uses are the requirements
  doc. Likely a 7-stop scale with real stops at ~4px and ~8px. This is a design decision,
  not a mechanical one — it changes rendered density everywhere and needs eyes on the
  before/after.
- **Define `danger` / `success` / `warning`** in every palette (`palette-default`,
  `palette-edo`, `_contract.css`). Flip `value-no-unknown-custom-properties` to **error**.
  That gate is cheap and permanent.
- **Consolidate breakpoints.** 4 tokens declared, 12 values in use, including 799 *and*
  800. Decide the real set; `@media` can't read `var()`, so the enforcement is the linter
  plus a comment convention.
- **Reconcile Figma** (§3D) — or explicitly demote that file from "mirror" to "sketchpad,
  do not measure against".
- **Decision point:** adopt DTCG + Style Dictionary now, or defer? Adopting means one JSON
  source emitting CSS + Swift + Figma variables and permanently closing the three-way
  drift. Deferring means the Figma reconciliation is manual and will drift again. Cost is
  a build step and a migration of `tokens.css`. *Recommend deferring to post-TestFlight
  but recording the decision, since Phase 1 is the only cheap moment to adopt it.*

**Exit:** no undefined tokens; one scale; one breakpoint set; Figma either reconciled or
demoted in writing.

### Phase 2 — The visual catalogue

Why here: this is the instrument you read the rest of the campaign through. It must render
real tokens (Phase 1) to be trustworthy, and it must exist before component decisions
(Phases 3–5) so the deltas are visible while being decided.

Spec — **one page per tier**, hierarchy explicit, at `docs/design-system/catalogue.html`
(flat, so `_discover_design_files()` picks it up):

- **Imports the real theme CSS.** No local token block, ever. This is the whole point.
- **Every entry is a card** carrying: rendered live specimen · canonical name · tier
  (token/atom/molecule/organism/template) · CSS file:line · React primitive (or *none*) ·
  consuming lenses · **status chip**.
- **Status chips** are the delta view you asked for:
  - `✅ in system` — exists as an atom/molecule/organism, used as such
  - `⚠️ flexed` — deliberate extension, links to its ledger row
  - `❌ off-system` — invented locally, no ledger entry
  - `🔁 duplicated` — two implementations of one idea (e.g. the two `TagRow`s)
  - `👻 retained` — feature-flagged off but deliberately kept (`moderator-question`,
    `context-expansion`) so nobody sweeps it as dead
- **A hierarchy pane** — the tree, showing which molecules compose which atoms and which
  lenses consume which organisms. This is where "naming and hierarchy" becomes legible:
  the three-way naming split (flat kebab / BEM element / BEM modifier) is *visible* as
  soon as the names sit in one column.
- **Naming convention decided and written down** — using Curtis's taxonomy vocabulary.
  Then the catalogue marks every non-conforming name.

Also in this phase: regenerate `INVENTORY.md` from disk by script (it has already drifted
by three files); revive `icon-catalog.html` as the Phase-3 tracker; fold `typography.html`
and `buttons.html` into their tier pages.

**Optional:** mirror the catalogue into the live `SpecimenTab` so it can be read against
real data in the real app. Cheap — the lens already exists and code-splits.

**Exit:** every element in `theme/` and every component in `frontend/src` appears exactly
once, with a status chip. The count of `❌` is the campaign's burndown number.

### Phase 3 — Icons

Why here: ~10 of the page-local components in Phase 5 contain inline SVGs. Promoting them
first would promote the icon debt *into* the system. Icons must be an atom before
components become atoms.

- Install `lucide-react` — the July 2026 decision, never executed (`lucide` is absent from
  `package.json`).
- Build the missing **`Icon` atom**. There isn't one; that's the root cause of 20 inline
  SVGs across 7 viewBox grids and 5 stroke weights.
- Migrate the 20 inline SVGs; migrate the 4 unicode `▶`/`▼` in `coverage.css` and the `▲`
  in `user_journeys.html` (logged as debt in July, still shipping).
- **Keep** the typographic glyphs — `★`, `→`, `↔`, and the Settings `✓✗⚠●○` matrix. The
  existing glyph-vs-icon rule is correct and these are in running text. Record this in the
  catalogue as `✅ in system` so nobody "fixes" them later.
- Track in the revived `icon-catalog.html`, whose three-layer structure is already the
  right shape for a burndown.

**Exit:** one icon idiom. `icon-catalog.html` shows an empty unicode-chrome column.

### Phase 4 — State atoms

Why here: same reason as Phase 3 — six lenses hand-roll loading/error, and Phase 5 would
otherwise promote six hand-rolls into the library.

- One `EmptyState` / `LoadingState` / `ErrorState` atom family (or one atom with a variant
  — decide during the work; Rule of Three is already satisfied at six).
- Retires the `<p style={{opacity: 0.5, padding: "1rem"}}>` pattern in Dashboard,
  SessionsTable, QuoteSections, QuoteThemes and AnalysisPage, *and* the styleless
  `.bn-loading`/`.bn-error` in TranscriptPage.
- Depends on Phase 1's `danger` token — the error variant currently renders a hex fallback.

**Exit:** zero inline-styled state blocks; `.bn-loading`/`.bn-error` deleted or given CSS.

### Phase 5 — Promote the page-local components

Why last of the fix phases: it is the largest, and every earlier phase reduces its size.
Work lens by lens, worst first, applying design-police's **mirror rule** (read the real CSS
*and* JSX, copy verbatim, confirm it actually renders).

| Order | Lens | Headline work |
|---|---|---|
| 1 | **Analysis** | 8 page-local components in a 1,259-line file. `SignalCard` → `components/`. Delete `IntensityDotsSvg` (a degraded copy of `Metric`, missing the half-dot case). Delete `SparkBars` (use `Sparkline`). Use `TimecodeLink` in `QuoteBlock` — it hand-builds identical markup. Resolve the third tooltip implementation. |
| 2 | **Project** | 10 page-local components. Decide whether `CompactSessionsTable` is a second sessions table or a variant of the first. Adopt `SectionHeading` (only lens not using it). Feeds the parked dashboard-widgets effort — **check that effort's state before starting** so the two don't diverge. |
| 3 | **Codebook** | The two diverged `TagRow`s — one composes `MicroBar`, one doesn't. Rename or merge. Four styleless classes. |
| 4 | **Sessions** | `sessions-grid.css` into the inventory; 7 bespoke container breakpoints onto the Phase-1 set. |
| 5 | **Quotes** | `HideIcon` → the Phase-3 `Icon` atom. Re-file the `.crop-*` rules — they live under transcript annotations but render on quote cards. |
| 6 | **Transcript** | The `.bn-selector__*` BEM island → the Phase-2 naming convention. |

Each lens is its own slice with its own `/usual-suspects` pass, logged to the same review
log. Do not batch them.

### Phase 6 — Governance

Why last: gates on green. Turning linters to error before the code is clean just produces
a permanently red build that everyone learns to ignore.

- Flip `declaration-strict-value` to **error** in CI.
- Keep `value-no-unknown-custom-properties` at error (set in Phase 1).
- **Quarterly interface inventory** — re-run `just design-audit`, walk the catalogue, count
  the `❌` chips. Quarterly is the researched sweet spot; monthly during active migration.
- **The delta ledger becomes the standing contribution path.** New element → check the
  catalogue first → if it doesn't exist, either build it as an atom or log a delta. Never
  a third option.
- Record the *review-step-before-new-component* rule where it will actually be read
  (`frontend/CLAUDE.md`), not only here.

---

## 5. Sequencing at a glance

```
Phase 0  diagnose ─────────────────────────────────────────► baseline numbers
Phase 1     └─ tokens (scale, danger/success/warning, breakpoints, Figma)
Phase 2         └─ catalogue (renders Phase 1; makes deltas visible)
Phase 3             ├─ icons ──────────┐
Phase 4             └─ state atoms ────┤  (both must precede promotion,
Phase 5                 └─ promote ◄───┘   or their debt is promoted too)
Phase 6                     └─ gates flip to error once green
```

## 6. Delta ledger

Same format and same rules as `design-police.md` §Ledger — every deliberate extension gets
a row, and an empty ledger is the goal. Rows are added as phases run; the first-pass
findings are transcribed here at the start of Phase 0 so the ledger is the single list.

| Delta | Forced by | Justification | Decision |
|---|---|---|---|
| *(carried from `design-police.md`)* dashboard card side padding `space-lg` → `space-md` | Dashboard widgets | See that doc | PENDING — **re-decide under Phase 1's new scale**, which may make this moot |
| *(carried)* `--ramp-1/2/3` heat weights | Co-occurrence widget | See that doc | PENDING — leaning promote |
| | | | |

## 7. Open questions for Martin

1. **Scale re-cut (Phase 1) changes rendered density across the whole app.** Do it now, or
   ship TestFlight on the current scale and re-cut after? Everything downstream is cheaper
   after the re-cut, and more expensive if it happens later.
2. **DTCG/Style Dictionary** — adopt in Phase 1 or record-and-defer? (Recommendation:
   defer, record.)
3. **The parked dashboard-widgets effort** is due to resume ~Sept 2026 and overlaps Phase 5
   order 2. Merge the two, or keep this campaign clear of the Project lens until it lands?
4. **Figma** — reconcile the token pages, or demote the file to "sketchpad, don't measure"?
5. **Native parity** is deliberately out of scope here (design-police scoped itself to
   HTML/CSS; SF Symbols are "a separate world"). Confirm that still holds — Phase 1's token
   work is the one place where a shared source would change the answer.
