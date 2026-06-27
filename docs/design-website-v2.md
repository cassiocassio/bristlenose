# Website v2 — integration, iteration, release & infra plan

> **Status:** plan / working spec. Pairs with [`docs/design-docs-system.md`](design-docs-system.md)
> (design system + writing style) and the help-delivery thread. Local staging tree:
> `/Users/cassio/Code/bristlenose-website-v2/`. _Drafted 25 Jun 2026._

v2 = the **existing site** (index, support, privacy) **integrated into the new docs
design system**, plus the **new docs framework** (Diátaxis-lite). One look, one nav,
one footer across the whole site.

> **Build progress (staging, 25 Jun 2026).** The full docs site is drafted in
> `bristlenose-website-v2/`: a lean generator (`build.py`, the `render-docs.py`
> prototype) renders **24 Markdown pages** under `content/` into `docs/*.html` — every
> `manual.md` section redistributed per the map below, plus the net-new how-tos, all
> written **code-true** (the manual was stale in ~15 places — see
> `bristlenose-website-v2/NOTES-product-discrepancies.md`). Tone: straight software
> manual, no marketing. Nothing deployed; index/support content untouched. Remaining:
> Pagefind, the changelog page, and the production generator + sidecar packaging.

> **In-app help — decided 25 Jun.** The React SPA Help *modal* is being **removed entirely**, not slimmed. The app's Help (`?` / Help menu) opens the **browser-served docs** instead — the sidecar at `/docs/` locally (offline, version-matched) or `bn.app/docs` remotely. **All** the help-modal text moves into these docs. The **Settings** window stays in-app. The About-cluster (credits, how-it-was-made, contributing) lands on the **About page**, not the researcher docs. (Supersedes the earlier "slim the modal to a launcher" framing.)

## Scope — frozen vs new

| Page | Treatment |
|---|---|
| **index** | **Content FROZEN.** Keeps its bespoke marketing layout + copy verbatim. Integration = inherit the shared topbar/footer only (palette already matches, so the seam is near-zero). |
| **support** | **Content FROZEN, verbatim.** Integration = new design-system chrome + `.plain` layout. The one walkthrough link → `/docs/` so it doesn't 404 post-rename. |
| **privacy** | Same as support — frozen content, integrated chrome. |
| **docs/** | **New.** The Diátaxis-lite tree, design system, and generator. This is where iteration and copy work happen. |

**We do not rewrite index/support/privacy copy.** A "manual"→"docs" terminology pass
inside their prose is a *separate, deferred* decision for the maintainer — flagged, not done.

## Iteration (now → pre-release)

- **Staging:** `/Users/cassio/Code/bristlenose-website-v2/`, off the live deploy. Run `python3 -m http.server 8000`.
- **Iterate on:** docs IA, the design system, and the **new docs copy** — not the frozen pages.
- **Two gating decisions** size everything downstream:
  1. **Sidebar IA** — by *kind* (Get started / How-to / Reference / Understand) vs by *topic* (Providers / Export / Privacy…).
  2. **`manual.html`** — does the docs front page *retire* it, or does it survive as the Reference section behind a redirect?

## Build-out (before release)

1. **Generator** — extend `render-manual.py` (single-file) into a tree-aware `render-docs.py`: one chrome template + N markdown → N pages + sidebar. **Emits both the website tree and the sidecar `/docs/` tree from one markdown source** (see help-delivery thread) so in-app and web docs can't drift.
2. **Migrate `manual.md`** — decompose the single everything-page into the Diátaxis-lite markdown tree (install → Get started, CLI table → Reference, concepts → Understand, setup → How-to).
3. **Truth the Reference values** — hard gate for the Reference section only; the mock's env-var defaults are placeholders.
4. **Integrate the frozen pages** — index/support/privacy into the unified chrome, content verbatim.
5. **URLs & redirects — low-stakes, no users yet** — nothing's hardened, so just go **clean URLs** (`/docs/set-up-claude`) because they read better, and wire the `.htaccess` rewrite whenever it's convenient. A `/manual.html → /docs/` redirect is a courtesy for the handful of existing links, not a gate. Change the structure as freely as you like until there's traffic worth protecting.
6. **Search** — omit at launch (a non-working "Search" chip is worse than none) or add a client-side index (Pagefind) later.

## Release / cutover (safe swap)

1. **Archive** — `git tag v1-final` on the live `bristlenose-website` repo (the archive is git, not a copied `old/` dir).
2. Assemble v2 into the live repo's structure.
3. Run the **existing** `deploy.sh` — same rsync, same keys, **untouched**.
4. **Verify** — extend the deploy's curl checks to cover `/docs/`, the `/manual.html` redirect, and `/support.html`.
5. **Rollback** — redeploy the `v1-final` tag.

## Infra — reuse / new / don't-disturb

- **Reuse:** DreamHost host, `deploy.sh` rsync + `--delete` discipline, SSH keys, the render-from-public-repo pattern, `feedback.php` / `telemetry.php` (untouched), the `data/` protection filter.
- **New:** `render-docs.py`; `.htaccess` redirects (+ maybe clean-URL rewrites); the sidecar `/docs/` route (offline + version-matched in-app delivery — opens in the system browser, auth-exempt).
- **Don't disturb until cutover:** the live tree, `deploy.sh`, and `data/`. v2 stays in its out-of-tree staging dir so a stray `./deploy.sh` can neither push it nor be affected by it.

## Sequence

1. Settle the two gating decisions (IA, `manual.html` fate).
2. Build the generator.
3. Migrate `manual.md` → tree; truth the Reference.
4. Integrate index/support/privacy chrome (verbatim).
5. Redirects + extend verify checks.
6. Archive tag → cutover deploy → post-deploy verify.

## Cutover runbook (refined 26 Jun 2026)

Supersedes the high-level "Sequence" above with the gaps found during the 26 Jun review.
Quality bar: **ship as-is, iterate after** — the review's non-keyboard findings (dead search
control, `--faint` AA contrast, tone softenings, a11y polish) are deferred to the launch-planning
Icebox, not launch gates.

**Phase A — close the deploy-breakage gaps (in staging first).** A naive `rsync --delete`
deploy would wipe live files v2 doesn't yet carry.

> **Hard URL contract — the shipped SPA links into the docs.** Every `bristlenose.app/…` URL
> hardcoded in the shipped frontend MUST keep resolving post-cutover. Audit:
> `grep -rn "bristlenose\.app" frontend/src`. The one this cycle adds is
> **`…/docs/how-to/miro-setup.html`** — the Miro panel's "How do I get a token?" link
> (`MiroExportPanel.tsx:207`, ships with PR #120). Handled per the 27 Jun
> decision below: **no redirect — update the panel's href to the new `/docs/send-to-miro` URL** rather
> than pin the legacy path. (`feedback.php`/`telemetry.php` are covered by step 2; `blog.bristlenose.app`
> is a separate subdomain, outside `--delete` scope.)

1. **Port the frozen `privacy.html`** into the new chrome (`.plain` layout + shared topbar/footer),
   content verbatim — as index/support already were. Missing today; `--delete` would remove the
   live privacy page without it.
2. **Carry the ops endpoints** — `feedback.php` + `telemetry.php` must be in the cutover tree
   (they back the report's feedback footer + health API), or `--delete` removes them.
3. **Reconcile the build** — the live repo renders docs via `render-manual.py` + `render-howtos.py`
   + templates; v2 uses `build.py`. Pick one: (a) adopt `build.py` as the live docs generator, or
   (b) commit v2's rendered `docs/*.html` static and retire the old templates. Either way the live
   `deploy.sh` must emit the full tree: index/support/privacy + `/docs/` + assets + PHP.
   **⚠️ Uncommitted wiring lives here:** the live `bristlenose-website` repo's how-to render
   (`render-howtos.py`, `howto-template.html`, the `deploy.sh` step) has **uncommitted changes**
   pending review (the miro-setup how-to render). Review/absorb them before reconciling — `build.py`
   may supersede the mechanism, but don't clobber it blind, and the rendered URL must survive.
4. **Settle `manual.html`** — retire with a `/manual.html → /docs/` redirect, or keep as a
   Reference section.

**Phase B — assemble into the live repo (`bristlenose-website`).**
5. Land the reconciled tree: new chrome, `/docs/`, integrated index/support/privacy, PHP,
   `.htaccess` redirects.
6. **Archive the current live site** — `git tag v1-final` on `bristlenose-website` (rollback point).
7. **Extend the deploy verify** — add curl 200-checks for `/docs/`, `/docs/how-to/miro-setup.html`
   (the shipped-panel contract), the `/manual.html` redirect, `/support.html`, `/privacy.html` to
   `deploy.sh`.

**Phase C — deploy (maintainer-run; needs SSH-agent access to `dreamhost`).**
8. `./deploy.sh` dry-run first — eyeball the rsync delta, confirm nothing live is deleted unexpectedly.
9. Confirm + deploy.
10. Post-deploy curl checks pass.
11. Rollback = redeploy `v1-final`.

Steps 1–7 are prep-able locally (no SSH); 8–11 are the maintainer's. Deferred polish: launch-planning Icebox.

## Open decisions (carried)

- ~~Sidebar IA~~ — **settled: by-kind** (Get started / How-to / Reference / Understand). Already what's built.
- `manual.html`: retire vs keep-as-section + redirect.
- ~~Clean URLs / redirects~~ — **non-issue pre-users**: go clean, change freely, add rewrites/redirects when convenient.
- Search: omit vs Pagefind-later.
- "manual"→"docs" terminology pass inside the frozen pages' prose — maintainer's call.

## Cutover — refreshed plan (27 Jun 2026)

Supersedes the sketch above where they conflict. Tonight's `bristlenose-website` restructure and the
Miro-how-to merge changed the starting line and surfaced the serving architecture the original only
gestured at.

### Starting point (changed 26–27 Jun)

- **The live repo is already on the assemble-then-ship model** v2 wants: `content/` ships,
  `templates/`/`scripts/`/`notes/` don't, `deploy.sh` assembles `build/site/` and ships only that —
  no exclude list. So the cutover's old "reconcile two rival build systems" step collapses to
  "swap `render-*.py` for `build.py`."
- **The Miro how-to is consolidated.** `bristlenose-website-v2/content/send-to-miro.md` is the
  code-true source of truth (paste-token reality, Preview + link-clips options, two named frames
  Sections/Themes, real error strings, the honest "spoken names travel" privacy note). The
  public-repo `docs/how-to/miro-setup.md` is **superseded — retire at cutover** (no back-port; no
  live users to justify maintaining a throwaway interim copy).

### Architecture — one source → one renderer → two outputs

The no-drift design the original only sketched ("one markdown source → website + sidecar"):

- **Source of truth:** the Diátaxis markdown lives in the **public bristlenose repo** (e.g.
  `docs/site/`) with `build.py` + the chrome assets. One home; researchers PR it like `manual.md`.
  Chosen because the **app builds from this repo** — the only place it can bundle docs from — and the
  marketing deploy already renders from it (`render-manual.py` reads `$BRISTLENOSE_PUBLIC_REPO`).
- **One renderer:** `build.py` (→ `render-docs.py`), used by both outputs.
- **Output 1 — public:** the marketing `deploy.sh` calls the renderer, assembles `build/site/docs/`,
  ships → `bristlenose.app/docs/`.
- **Output 2 — bundled/offline:** rendered docs shipped as **`bristlenose` package data** → `bristlenose
  serve` serves `/docs/` for *every* install (pip · Homebrew · Snap · Mac app), version-matched, offline;
  PyInstaller `datas` carries it into the `.app`; Help (`?`) opens local `/docs/`, else `bn.app/docs`.

### Gating decisions (settled 27 Jun)

1. **Generator = `build.py`**, retiring `render-manual.py`/`render-howtos.py`. ✓
2. **Source of truth in the public repo** (`docs/site/`). ✓ — required for the app bundle.
3. **`manual.html` retires — no redirect.** Its content is already migrated: the manual was passed over
   in full and incorporated / rewritten / confirmed-superseded across the 29 pages, so there's nothing to
   carry and nothing bookmarked worth a redirect (no users). _Coverage is closed; the page-truthing pass
   below is about code-accuracy, not whether manual content survived._
4. **Miro URL — no redirect.** No users to have bookmarked the legacy path. The one real dependency is
   the *shipped* panel's hardcoded link (`MiroExportPanel.tsx:207` → `/docs/how-to/miro-setup.html`) —
   handled at the source, not with a server redirect: **update that href to `/docs/send-to-miro` in the
   product, shipped around the cutover.** Cleaner than a redirect, and with no users the interim gap is
   irrelevant. (Redirects are the right tool once there's traffic worth protecting — not yet.)

### Steps once decisions are settled

Assemble v2 into the live repo (content + `build.py` + assets; frozen index/support/privacy take the
shared chrome, content verbatim) → re-wire `deploy.sh` to `build.py` → preserve URL contracts (Miro
redirect, PHP, `/manual.html`) → **truth the remaining 28 pages against the code** (the Reference hard
gate; `bristlenose-website-v2/NOTES-product-discrepancies.md` is the lead) → `git tag v1-final` → deploy
(maintainer). The Miro page is the worked example of that page-truthing step — done; the other 28 are the
bulk of the remaining content work.
