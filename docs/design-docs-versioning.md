# Docs versioning — channels over time

> **Status:** working spec. Owns the *versioning* axis of the docs surface; pairs
> with [`design-docs-system.md`](design-docs-system.md) (design system + writing
> style + surface map) and [`design-website-v2.md`](design-website-v2.md) (build +
> integration). Those two describe *what a page is*; this one describes *which
> version of it a reader sees, and when*.
> _Drafted 28 Jun 2026._

The trigger was a small question — "we built a DEBUG-only Debug menu; did we write
user docs, and where would they live?" The answer (no, and correctly so — it's
`#if DEBUG`, users can't see it) opened a bigger one: features routinely land in
code **behind a gate** before they're released, but docs have no equivalent gate,
so a doc can only ever **lead** a release (publish for a feature users can't reach)
or **lag** it (drift in afterward). This doc settles how docs ride the version
train, now and later.

## Decision summary

1. **Adopt the pre-release channel now; defer web archives.** Build only the
   "docs for the unreleased version" capability today. Per-version web archives
   wait until there's an audience that actually reads them.
2. **Path, not a pulldown.** When versions do appear in URLs, they live in the
   path (`/docs/`, `/docs/v0.20/`), surfaced by a quiet link — never a version
   dropdown. The dropdown is enterprise furniture we don't need.
3. **Per-minor, never per-patch.** If/when web archives exist, they snapshot at
   minor releases (`0.20`, `0.21`), not patches (`0.20.3 → 0.20.4` — docs rarely
   differ).
4. **The in-package channel already is a per-version archive — for free.** See
   below; this is the Bristlenose-specific reason the web archive can wait.

## The canonical model (what the docs world does)

The standard pattern is three channels — **current / pre-release / archived-by-
version** — as in Docusaurus (`docs/` = "next", the live site = current,
`versioned_docs/version-X/` = archives), Read the Docs (`latest` / `stable` /
per-version), MkDocs + `mike`, Sphinx. The version selector is the usual furniture.

The thing the survey reveals: that model **bundles two independent capabilities**
that solve different problems, and they should be reasoned about separately.

| Capability | Problem it solves | Cost |
|---|---|---|
| **pre-release ("next")** | docs for the unreleased version, built but not the public default | tiny — one excluded directory |
| **archived by version** | a reader *on an old version* needs *version-matched* docs | real — maintenance fan-out + stale-landing (not disk) |

## The Bristlenose twist: in-package docs are a free archive

Bristlenose ships docs **two ways** (per `design-docs-system.md`):

- **In-package `/docs/`** — served by the sidecar, **version-matched to the
  installed app** (the topbar version chip shows the *installed* version).
- **Web** (`bristlenose.app/docs`) — shows **latest**.

The consequence is large: **every app bundle carries its own matched docs
snapshot.** A user pinned on 0.18 reading `/docs/` in their app gets 0.18 docs —
automatically, with zero back-porting, because that bundle is an immutable artifact
already shipped. The "user on an old version reads mismatched docs" failure — the
entire reason web archives exist — is *already handled for app users.*

So the only readers a **web archive** would serve are people reading old-version
docs *without the matching app*: someone who landed via search/bookmark, or an
enterprise version-manager browsing the web. That audience is ~empty today (pre-1.0,
auto-updating), which is why the web archive is **deferred, not rejected.**

## Why web archives aren't worth it yet (the cost is not disk)

"Disk is cheap" is true and irrelevant — the expensive resource is correctness, not
bytes:

- **Maintenance fan-out.** Every future doc fix (a clarified step, a corrected
  screenshot) forks: back-port it into each frozen snapshot, or it rots there. In
  practice it rots — so each archived web version becomes a place corrections don't
  reach. Weeks of patch releases → dozens of near-identical snapshots, each subtly
  wrong.
- **Stale-landing.** A version dropdown (or an indexed `/docs/v0.18/`) is an
  *invitation* to read the wrong one. Search and bookmarks send readers to docs for
  a version they auto-updated past — manufacturing the exact mismatch versioning was
  meant to prevent.

In-package archives have neither cost: the bundle is immutable (nothing to
back-port) and the reader can only ever be on the version that bundle matches
(nothing to mis-land on).

## The earn-it ladder

| Phase | Web `bristlenose.app/docs` | In-package `/docs/` | Trigger to advance |
|---|---|---|---|
| **Now** | **current** (latest) + **pre-release** (local-only) | version-matched (already designed) | — |
| **Later** | + **archived by minor** (path-based) | unchanged | a real audience reading **old-version docs on the web** without the app: 1.0 with version-pinning, an enterprise install that can't auto-update, or a stable file-format/API promise |

The principle that sets the cadence: **doc-version archiving should match how long
readers actually sit on an old version *on the web*.** For an auto-updating alpha
whose app already carries matched docs, that's ≈ zero — so the right number of web
archives right now is zero, and the trigger to start is the day it stops being zero.

## The tiny bit of complexity we *will* carry

We explicitly do **not** build the enterprise version-management surface — per-
version sites, a version dropdown, breaking-change matrices, "what broke / will
break between X and Y" upgrade guides, pinning guides. That is a substantial,
permanent cost that serves a tiny audience (people whose job is managing pinned
version numbers on locked-down systems). It's a nightmare and it's not ours.

But we carry a *seed* of it, because version-reality can't be fully wished away:

- **A version chip** (installed vs latest) — already in the topbar design.
- **`CHANGELOG.md`** — already the one place behavioural changes are called out.
  That is the lightweight stand-in for a breaking-change matrix; one changelog, not
  a per-version cross-product.
- **The pre-release channel** itself — a one-bit notion of "next vs current."

That's the whole seed. It grows into the full archive only at the trigger above.

> **Footnote — users do funny things about not updating.** Auto-update reduces but
> does not eliminate version lag: people defer updates, disable auto-update, or run
> pinned installs. This is why the cadence is "low," not "zero," and why the archive
> capability is *deferred, not rejected*. For app users, the in-package channel
> already covers it. The deferred web archive is for the residual: non-app readers
> on old versions. We'll know that audience exists when we see it; we don't pre-build
> for it.

## Path scheme (designed now so we don't repaint later)

URLs carry the version in the **path**; no dropdown. Designed now even though only
the first row ships today, so adding archives later is additive, not a migration:

| URL | Channel | Ships |
|---|---|---|
| `bristlenose.app/docs/…` | **current** (latest release) | now |
| `bristlenose.app/docs/next/…` | **pre-release** preview (noindex) | *optional, future* — only if a beta audience wants to read ahead; today the pre-release channel is **local-only** (see implementation) |
| `bristlenose.app/docs/v0.20/…` | **archived** minor | future (at the trigger) |

Surfaced by a quiet footer line ("viewing latest · other versions") when more than
one exists — not a topbar selector. The default and canonical URL is always
`/docs/…` = current; archives are the exception, reached deliberately.

## Migration, when the trigger fires

When web archives are earned, **move to a standard SSG** (Docusaurus, or MkDocs +
`mike`) rather than growing the custom `build.py` into a versioning engine. Those
tools do path-based versioning, the channels, and the snapshot-cutting natively —
all three channels come for free, and the custom build carries only the pre-release
exclusion until then. Nothing built now is throwaway: the `unreleased/` directory is
exactly the SSG's "next" channel, and the path scheme above is what `mike` produces.

---

## Implementation: the pre-release channel (build now)

The only thing built today. It closes the lead-or-lag gap with one excluded
directory and no new infrastructure.

### Mechanism

A feature's user-facing pages live in an **`unreleased/`** directory in the doc
source while the feature is gated; the build **excludes** it from the published
output. At release, the pages move out in a single `git mv`, and they go live with
the feature in the same deploy. (See the dialog + state-machine diagrams in the
design thread; the whole control surface is *where the file lives*.)

The same build signal that gates the **feature** gates its **docs**: a release/prod
build (web *and* the in-package `/docs/` of a release app) excludes `unreleased/`; a
preview/beta build (the one that enables the gated feature) includes it. So docs and
feature ride together in **every** build configuration — that's the coupling we want.

### Where the directory lives

- **Multi-page Diátaxis pages** (the website's `docs-src/`): `docs-src/unreleased/<feature>/`.
  The directory boundary is the feature boundary — a feature's how-to + reference +
  cross-linked pages move out together in one `git mv`, so you can't half-leak a
  multi-page feature (the granularity worry that killed per-page front-matter).
- **`docs/manual.md`** (single file, this repo): a feature's manual prose stays in
  its feature branch/commit and merges into `manual.md` at release. One small file
  doesn't need directory gating.

### Steps

1. **Author** the feature's user docs in `unreleased/<feature>/`, in the same
   commit series as the feature.
2. **Preview** locally: build with the unreleased docs **included** and the feature
   flag **on** — exercise the how-to against live behaviour. (No noindex site, no
   staging box; the preview is your machine.)
3. **Hold:** any number of unrelated releases can ship meanwhile; their prod builds
   skip `unreleased/`, so the public site and release-app `/docs/` never show the
   gated docs.
4. **Release flip (one gesture):** `git mv docs-src/unreleased/<feature>/* docs-src/<section>/`,
   update the NAV, bump the version, deploy. Feature flag flips default-on in the
   same release.

### `build.py` change (website repo — spec)

The render lives in the private `bristlenose-website` repo (`build.py`), edited on
the maintainer machine. Two small changes:

- **Prod build:** skip any path under `unreleased/` (out of output, NAV, sitemap,
  search index).
- **Preview:** an `--include-unreleased` flag (or `STAGE=preview` env) that renders
  them, for local testing alongside the flag-on app.

Per the existing `build.py` convention, page metadata lives in NAV, **not
front-matter** — so this is a directory exclusion, not a per-page schema. That's
deliberate: a directory has one place to get right (the `git mv`); front-matter has
one-per-page, and forgetting one silently leaks.

### Drift guard — a checklist line, not CI

The residual risk after this is **drift**: a feature ships but its docs were never
moved out (or never written). The proportionate guard for a solo, manually-deployed
project is a **release-checklist line**, not a CI job:

> _Docs for this version's features moved out of `unreleased/` + NAV updated?_

A CI parity check (grep for features whose flag is now default-on while their docs
still sit in `unreleased/`) is **write-it-down territory** until we've actually been
bitten — four environments earn their keep through observed incidents; this hasn't
had one yet.

### What this is not

No front-matter schema, no preview environment, no version numbers in paths, no
dropdown, no CI check. Those are the deferred structures above — the `unreleased/`
directory is the one bit that pays for itself today, and it's shaped so the rest
slots in later without rework.
