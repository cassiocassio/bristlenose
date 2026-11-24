# Lens-wide design-system audit — diagnose and fix

**Status:** Plan, awaiting review + triage (6 Aug 2026). Phase 3 (icons) done 16 Oct 2026.
Phase 0 partly built 4 Nov 2026: `scripts/audit-css.py` scores the CSS source and
`experiments/token-xray/live-scan.mjs` scans the rendered page; neither runs in CI. On 24 Nov
2026 the tooling question was reopened and researched; the planned spike is §8. Planning
only, nothing on the App Store path depends on it.

**Scope (owner, 24 Nov 2026):** the React SPA and the CSS it draws with. The deprecated
static report is out of scope entirely: its CSS-only files stay out of every score, and a
shared-CSS change that shifts its output is accepted unchecked. The Mac app's native UI is
the Mac's own business.

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

We are a one-person system. When this was written (6 Aug) that meant two render paths and
three consumers (web SPA, static render, native shell); since 24 Nov the static render is
out of scope, so it is one render path in two hosts (browser and the Mac's WKWebView). The
prior art that fits that shape:

| Source | What we take | Where it lands |
|---|---|---|
| [stylelint-value-no-unknown-custom-properties](https://stylelint.io/awesome-stylelint/) | Fails on a `var(--x)` that no token defines. Would have caught `--bn-colour-danger` the day it was written. **Highest leverage single tool for this codebase.** | Phase 0 (report), Phase 1 (error) |
| [stylelint-declaration-strict-value](https://github.com/AndyOGo/stylelint-declaration-strict-value) | Requires a token (not a literal) for named properties — colour, spacing, radius. | Phase 0 (report), Phase 6 (error) |
| [Omlet CLI](https://www.npmjs.com/package/@omlet/cli) (`@omlet/cli`, [Zeplin](https://github.com/zeplin/omlet)) | Static React component analytics — "see what new custom components are being created and review whether they should be added to your design system". Automates the page-local-component finding permanently. *24 Nov 2026: its makers blogged on 28 Apr 2026 that it is going open source under MIT; whether the hosted service continues is unconfirmed. §8 prefers a small script (react-scanner raw report or the TypeScript compiler) that classifies each component by where it is defined and how many files import it.* | Phase 0 |
| [DTCG format + Style Dictionary 4](https://styledictionary.com/info/dtcg/) — spec [stable since Oct 2025](https://www.w3.org/community/design-tokens/) | One token source → CSS custom properties + Swift constants + Figma variables. The only real fix for the web/native/Figma three-way drift. | Phase 1 decision point |
| [Brad Frost, *Maintaining Design Systems*](https://atomicdesign.bradfrost.com/chapter-5/) | The **interface inventory** as a recurring ritual, not a launch task. | Phase 6 cadence |
| [Nathan Curtis, *Naming Tokens in Design Systems*](https://medium.com/eightshapes-llc/naming-tokens-in-design-systems-9e86c7444676) and [*On Classification*](https://medium.com/eightshapes-llc/on-classification-in-design-systems-6b33b97f4a8f) | Taxonomy discipline — the vocabulary for settling our three-way naming split. | Phase 2 |
| [Design-system maintenance practice](https://www.magicpatterns.com/blog/design-system-maintenance) | Quarterly audit cadence as the sweet spot; a component **lifecycle with an owner** prevents more drift than any review checklist; watch for components that technically use the library but override so many props they've gone custom. | Phase 6 |

Deliberately **not** adopting: any hosted design-system SaaS (Supernova/Knapsack/Backlight —
priced and shaped for teams).

*Storybook was on that list on 6 Aug, as "a third render path for a system that already
struggles with two". The second path was the static render, now out of scope, so that
reason no longer holds. Reopened 24 Nov 2026: Storybook, hosted visual diffs and plain
Playwright screenshots go through the spike in §8 rather than being decided here.*

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
pattern the linter in Phase 0 exists to make impossible. *24 Nov 2026: `warning` is now
defined in the palettes; `danger` still has no definition and 2 use sites; `success` has
none of either.*

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
  the ~25 page-local components counted by hand. *(24 Nov: or the inventory script in §8,
  given Omlet's uncertain status.)*
- *Added 24 Nov 2026:* a **declared-exception marker** for the odd legitimate literal, e.g.
  `/* ds-deviation: optical nudge for the timecode glyph */` on the declaration (the CSS twin
  of `live-scan.mjs`'s `data-ds-deviation`). `audit-css.py` counts it as *declared*, not
  *outside*, and lists every one with its reason. The target becomes "no undeclared
  exceptions" rather than a coverage percentage. Today `audit-css.py` strips comments first,
  so it cannot see one.
- *Added 24 Nov 2026:* hold the number with the CI ratchet (`docs/testing/ratchet.json`,
  `scripts/check-ratchet.py`) so it cannot fall while the burndown runs. Baseline 24 Nov:
  81% coverage, 91 health; 2,534 declarations through tokens, 63 literals that equal a
  token (one-line swaps), 554 outside.
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

*Done 16 Oct 2026 — executed as `docs/design-icon-system.md`, which supersedes the plan
below; three CSS-drawn glyphs are deferred there (§ What's left). Kept as written.*

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
  SessionsTable, QuoteSections, QuoteThemes and SignalsPage, *and* the styleless
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
   *24 Nov 2026: confirmed — "the mac stuff is the mac stuff".*

## 8. Tooling spike: Playwright screenshots, Storybook, hosted diffs (planned 24 Nov 2026)

*Planning only; nothing built. Source: the research report
[`Storybook and visual regression spike`](../experiments/storybook-research/reports/Storybook%20and%20visual%20regression%20spike.md)
and its four note files beside it, researched 24 Nov 2026. Prices and versions are as of
that date. Every threshold below is a proposal: the research found no published framework
for scoping this kind of spike.*

### The question is which layer is missing

| Layer | Tool | Good for | Status |
|---|---|---|---|
| Logic | Vitest (jsdom), ~1,700 tests | Behaviour; renders nothing | Live |
| Component | Storybook | Every state of one component, in every theme and locale, per push | Candidate |
| Page | Playwright E2E in CI, Chromium + WebKit on Linux | Mounts, links, requests, clipped labels, overflow | Live; no pixels |
| Whole app | Guest walk, nightly (`docs/design-guest-walk.md`) | The real signed app, real macOS, real WKWebView, real journeys | Live: 22 steps, 26 captures, ~4 min (20 Oct) |

- **Real WKWebView fidelity already belongs to the guest walk**, and no candidate can take
  it over. Playwright's WebKit is a patched WebKit trunk build, not Safari; Chromatic's and
  Percy's Safari are approximations too. Linux WebKit screenshots are a tripwire for layout
  and token regressions, not a check of how the Mac app looks.
- **What is missing is a deterministic pixel check on every push, and reach into odd
  states** (empty, error, long German labels, every colour theme) that the walk can't get
  to cheaply.
- **Determinism is the same work whichever tool captures**: frozen clock (`page.clock`),
  stubbed polling, `document.fonts.ready`, transitions off via `stylePath`, mouse moved
  away, baselines made in the pinned Playwright Docker image. Playwright is the cheapest
  place to do it.

### What the research found

- **Playwright `toHaveScreenshot()` is the floor** (the owner's "just extend Playwright"):
  no new tool, tests the app as assembled, both browsers. Baselines are per OS (the
  platform is in the filename), so they are made in Docker; the image has a remote-server
  mode so the Mac can render in Linux without running the tests in Docker.
- **Storybook 10.6.8 fits the stack** (React 19, Vite 8 since 10.3, Node 24, TS 6), with
  open Vite 8 bugs but none fatal. **Storybook 11 is in beta** (11.0.0-beta.5, 23 Nov) with
  a migration roughly 15× the size of 9→10; adopt on 11 stable, not 10.6.
- **Mocking is where Storybook gets expensive here.** ~40 files import `utils/api.ts`
  directly and ~30 use `useSyncExternalStore`. Cheapest route: `sb.mock` on `api.ts` in
  `preview.ts` plus a reset hook per store (stores can't be automocked). Open bugs: #37040
  (spy mode differs between Storybook and CI) and #32336 (files exporting a TS `enum`).
- **Storybook's Vitest addon documents Chromium only** and has no native screenshot
  assertion; every workaround needs the same Docker discipline as plain Playwright.
- **Goals (a) and (b) need none of these tools.** Token coverage is a stylelint ratchet
  (`declaration-strict-value` + `value-no-unknown-custom-properties`) beside
  `audit-css.py`; "shared vs one-off" is an inventory script; accessibility is
  `@axe-core/playwright` in the existing suite rather than Storybook's a11y addon.
- **Hosted services sell review, not capture.**
  - *Chromatic:* free is 5,000 snapshots/month, Chrome only, and pauses at the cap. At
    ~600 snapshots a build (150 stories × light/dark × 2 locales) that is ~8 builds.
    Safari needs Starter at $179/month. It needs Storybook, and it re-renders in its own
    browsers.
  - *Argos:* compares screenshots your own CI takes, so it can sit on top of the
    Playwright shots with no Storybook, and the browser is whatever Playwright ran. Hobby is
    free for 5,000/month (one person, 30-day retention); Pro is $100/month. Only PNGs are
    uploaded. Platform MIT-licensed; self-hosting unsupported. That it accepts WebKit
    screenshots is inferred, not documented.
  - *Percy:* lists macOS Safari, but extras cost $0.036 each.
  - *Happo:* $4 per 1,000, all browsers on every plan.
  - *Lost Pixel:* shut down; its team joined Figma and the repo was archived on 22 Apr 2026.
  - Nearly every 2026 comparison found was written by Argos; treat them as vendor-authored.

### The spike (about 6 working days)

| Order | Step | Smallest version worth comparing | Time |
|---|---|---|---|
| 0 | Shared harness | The determinism kit above, and a branch with six deliberate regressions | 0.5 day |
| 1 | Playwright screenshots | ~10 page and ~10 component (locator) shots on the committed fixture; light and dark; one non-default colour theme; German on 5 key components; Chromium and WebKit; WebP baselines; a `workflow_dispatch` job to regenerate them | 2 days |
| 2 | Goals (a) and (b) | stylelint rules above with violations baselined; inventory script over `frontend/src` | 0.5 day |
| 3 | Storybook | Hand-rolled scheme, theme and locale decorators; `sb.mock` on `api.ts`; store resets. Stories for 3 primitives, 2 connected components (one API-driven, one store-driven) and 1 page-local one-off, each with Empty, Error, Long German and Dark. Addon-vitest on Chromium and WebKit. One timed upgrade to the 11 beta | 2 days |
| 4 | Hosted review | Upload step 1's screenshots to Argos Hobby; optionally Chromatic free to judge its review screen | 0.5 day |
| 5 | Decision | Score against the table below; write the outcome here | 0.5 day |

The six seeded regressions: a 1px padding token change; a colour token changed in dark mode
only inside a non-default colour theme (a state the guest walk never visits); a font-weight
change; a hidden icon; a German label overflowing its button; and a native-control or
scrollbar change only WKWebView renders faithfully (records whether Linux WebKit sees it, or
whether it stays the walk's job).

| Criterion | How measured | Success | Kill |
|---|---|---|---|
| Flake rate | `--repeat-each=20` in Docker, then 5 consecutive CI runs | 0 screenshot failures | More than 1 flaky shot in 100 runs after the kit |
| Cross-OS baselines | Mac-made baselines (arm64 Docker) compared on GitHub's x86_64 runner | Pass unchanged | Never match, and the CI-only update loop takes over 10 min |
| Seeded regressions | The six breaks, against step 1 and step 3 separately | Playwright catches ≥5 of 6; Storybook catches the token and overflow breaks | Playwright catches fewer than 4 |
| Time to add a screenshot | Idea to committed baseline | ≤10 min | >30 min |
| Time to add a story | Median, primitive vs connected | Primitive ≤15 min; connected ≤45 min | Connected median >90 min |
| Mocking cost | Fixture and decorator lines, plus any app-code change, per connected story | Typed fixtures and one store-reset hook per store only | Needs app restructuring or `api.ts` changes, or hits #37040/#32336 with no workaround |
| Review time after a token change | Change one shared colour token, review every diff | ≤15 min in the Playwright HTML report | >30 min — the trigger to try Argos Pro, not a kill of Playwright |
| CI minutes | Added wall-clock per push, both browsers | ≤3 min | >8 min |
| Bytes added to git | One full regeneration, WebP vs PNG, projected at 4 refreshes a month | <10 MB/month | >50 MB/month, or LFS needed |
| WebKit under addon-vitest | Step 3's stories on WebKit, Mac and Linux | Green with no WebKit-only workaround | WebKit-only failures taking over an hour to diagnose |
| Storybook 11 exposure | Migration items touching spike files; timed beta upgrade | <2 hours and <10 items | >half a day, or a decorator broken with no migration path |
| Hosted value | Argos review of the token-change diff vs the HTML report | Measurably faster, WebKit screenshots accepted | WebKit rejected, or no time saved |

**Decision rule (proposal).** If Playwright passes flake, cross-OS and seeded-regression, it
becomes the visual-regression layer, with its soft-gate disposition recorded in
`docs/testing/soft-gates.json` before it ships. The stylelint ratchet and the inventory
script go ahead whatever happens to the visual tooling. Storybook is adopted only if
connected-component cost lands under the kill line, it reaches states that Playwright could
reach only through costlier stubs, and the catalogue is wanted as documentation; then it is
scoped to the primitives plus a few named connected states, on 11 stable. A hosted service
is tried only if review time, not capture, breaks its line. The guest walk stays the arbiter
of what the Mac app actually looks like.

**Design reading.** The components that are costly to give stories (they fetch and
subscribe for themselves) are the same page-local one-offs Phase 5 wants surfaced. Record
mocking cost per component as a measure of that coupling, not only as a verdict on
Storybook: pulling them into presentational primitives would raise token consistency,
shrink the inventory and make stories cheap at once.

**Open research gaps:** no independent hands-on 2024–26 reports for either route; no
measured hours per connected story; whether arm64 Docker on the Mac matches GitHub's x86_64
runner pixel for pixel; whether standard macOS runners are free for public repos; where
Chromatic and Happo run Safari; Omlet's hosted status.
