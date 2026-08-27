# Bun — adoption assessment

**Status:** parked. **Recommendation: don't adopt.** **Not gated on anything Bun-side** — the reason is the shape of this repo, not Bun's maturity.
**Assessed:** 2026-08-26, against the tree at `8e5dae98`.

Sibling to [`design-typescript-7-adoption.md`](design-typescript-7-adoption.md) (same shape, same verdict, different reason) and [`design-dev-environment.md`](design-dev-environment.md) (where the dev-tooling plan actually lives).

## It was never assessed before

Worth recording, because the obvious assumption is that it was considered and rejected. It wasn't. As of this assessment there was **zero trace** of Bun in the tree — no commit, no doc, no memory entry, no `bun` / `bunx` / `oven-sh` string anywhere.

The nearest thing to a decision is one line in the off-the-shelf inventory of `design-dev-environment.md`:

> What stays: `npm` (already off-the-shelf for Node)

That's a dismissal that follows from how the problem got framed, not a comparison. That doc exists because `/new-feature` had grown a hand-rolled env manager by accretion, and the parsimony redirect was *"don't write our own dev-environment manager."* The pains it enumerates are **tool-version pinning** and **task running** — `mise`, `uv`, `just`, `direnv`. Package-manager speed isn't on the list, so npm got waved through in four words. Bun appears exactly once in the whole repo, at `design-dev-environment.md:213`, as a *hypothetical* example of "a new tool added".

So: not rejected, never in frame.

## The measured case

Bun's pitch is install speed, a fast bundler, a fast test runner, and one binary instead of several. Measured against this repo rather than against the pitch:

| Thing | Measured | What Bun changes |
|---|---|---|
| Vite/Rolldown bundling | **308 ms + 181 ms** (two builds) | ~nothing left to win |
| Full `npm run build` | **4.46 s**, ~89% of it `tsc -b` | Bun strips types, doesn't check them → nothing to win |
| Vitest | **10.7 s / 1570 tests / 105 files** | real win available, at high migration cost |
| CI `frontend-lint-type-test` | **1 m 40 s** | the only CI job Bun touches |
| CI critical path (run `32602750413`) | **37 m 22 s**, of which `test (3.10, ubuntu)` is **32 m 11 s** | untouched — it's Python |

The last row settles it. `e2e` declares `needs: [test, frontend-lint-type-test]`. The frontend job finished at 22:34:46 and e2e started at 23:06:57 — **it sat idle for 32 minutes waiting on the Python matrix.** Taking that job to zero seconds would not move the CI wall clock.

Rolldown already collected the bundler win, which is why there are only ~489 ms of actual bundling left to compete for.

## Why the complexity argument doesn't land here

Bun replaces N tools with 1, and **the saving is proportional to N.** In 2023 a typical repo had N ≈ 5 — npm + jest + babel + ts-node + webpack, each with its own config and its own opinion about TypeScript. Collapsing that is a real, large reduction, and it is where Bun earned its reputation.

Our N is about 1. Vite 8 already does dev server, bundler, and — via Vitest — the test runner, from one config file and one Rust engine. **The consolidation is already bought, in a different colour.** Bun wouldn't collapse five tools into one; it would swap one consolidated family for another.

And it would swap it *while adding* a runtime, because:

## Node does not leave

Two independent pins, neither of which is ours to move:

- **Playwright** has no native Bun support — it needs `node` on PATH regardless, and its ESM-preflight and transpilation assumptions conflict with Bun's ([microsoft/playwright#38095](https://github.com/microsoft/playwright/issues/38095), [oven-sh/bun#28609](https://github.com/oven-sh/bun/issues/28609)).
- **The `.mcpb` agent extension** declares `"server": {"type": "node"}`, `"command": "node"`, `runtimes.node >= 18` in `desktop/mcpb/manifest.json`. That is Claude Desktop's runtime contract, not a choice. `desktop/scripts/build-mcpb.sh` also uses `node --check`.

So a migration **adds** Bun beside Node rather than replacing it. The "one fast binary, less tooling" pitch — the main reason to do this at all — does not survive contact with this repo.

## The SBOM question

Initially called a hard blocker. On research it is not; it is a tool swap within a class we already use.

**Bun has no SBOM command today** (confirmed against Bun's own `bun audit` docs, which cover advisories but nothing CycloneDX/SPDX). `bun audit` itself is at parity with `npm audit` — it reads `bun.lock`, queries the npm advisory endpoint, and supports `--prod` / `--audit-level`.

Three things soften the gap:

1. **`bun pm sbom` is an open PR** — [oven-sh/bun#29512](https://github.com/oven-sh/bun/issues/29512), opened 20 Apr 2026, last updated 18 Aug 2026, CI green, marked ready for maintainer review, tagged to close [#8483](https://github.com/oven-sh/bun/issues/8483). Emits CycloneDX 1.7 (default) and SPDX 2.3 with purls, SHA-512 integrity hashes, dependency edges, and dev/optional scoping. **Caveats:** unmerged, from an automated contributor, no maintainer commitment; and CycloneDX **1.7** needs checking against what `actions/attest-sbom` accepts.
2. **Both mainstream generators already parse `bun.lock`** — cdxgen (the OWASP CycloneDX generator) supports it, and Syft ships `bun-lock-cataloger` + `bun-binary-cataloger` ([anchore/syft#2820](https://github.com/anchore/syft/issues/2820), [#4617](https://github.com/anchore/syft/issues/4617)).
3. **We already do exactly this on the bigger half.** `release.yml:80` generates the Python SBOM with `cyclonedx-py environment` pointed at a real installed venv. Third-party SBOM generation is the *existing* pattern; the frontend is the odd one out for using a bundled subcommand.

Residual real difference: `npm sbom` reads npm's own resolved tree, while cdxgen/syft parse a lockfile — one inference step further from the installer. That matters less than it might, because `release.yml`'s own comment notes the frontend SBOM "isn't separately attested — it's already inside the attested wheel." It is a release asset, not an attestation subject.

## If it is ever picked up

The only variant that survives this assessment is **package manager only** — `bun install` with Node kept as the runtime, which is also the most-adopted slice of Bun in the wild. Switch to `bun.lock` wholesale (never carry both lockfiles — divergent resolution between a worktree and CI is the silent-drift class `design-dev-environment.md` was written in response to, and `frontend/CLAUDE.md:17` has the specific scar: a full re-resolve moved vite 8.0.10 → 8.1.3 and blew the size gate 213 → 233 kB).

Migration sites, for whoever costs it:

- `npm ci` → `bun install --frozen-lockfile` in `ci.yml`, `release.yml`, `perf.yml`, and `desktop/scripts/build-sidecar.sh`
- `npm sbom` → cdxgen / syft / `bun pm sbom` (`ci.yml:198` is `continue-on-error`; **`release.yml:82` is deliberately not** — "a release with no bill of materials should fail loud")
- `npm audit --omit=dev` → `bun audit --prod`
- `npx` → `bunx` at `bristlenose/cli.py:1848` (the `serve --dev` Vite spawn) and the `size-limit` gate
- `.tool-versions` needs its own Bun pin — `setup-bun` does not read it; `setup-node` stays anyway for Playwright
- `desktop/scripts/build-sidecar.sh:83-104`'s Homebrew-keg PATH fallback needs a Bun equivalent, and still needs `node` for `build-mcpb.sh`
- Docs: `DEVELOPMENT.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `frontend/CLAUDE.md`, `.claude/skills/new-branch/SKILL.md`

**Held-register predicate**, if it is ever worth watching: *#29512 merges, **or** cdxgen output validated against the current `npm sbom` baseline.* Neither is urgent — see below.

## Recommendation

**Park, not gated.** Every bottleneck Bun addresses has already been collected by something else here: Rolldown took the bundler, `tsc` owns the remaining build time and Bun doesn't type-check, and CI's critical path is a Python matrix Bun cannot touch. It would add a runtime rather than remove one, because Playwright and the `.mcpb` contract both pin Node.

The frontend-loop speed target is `tsc`, which is [`design-typescript-7-adoption.md`](design-typescript-7-adoption.md) — already assessed, already gated. **The CI target is the Python matrix, which is [`design-test-performance.md`](design-test-performance.md)** — measured, actionable, and worth an order of magnitude more than anything on this page.

The friction actually encountered while measuring this is the one worth fixing, and Bun does nothing for it: local shell Node was **v26.0.0** against `.tool-versions`' pinned **24**, so the vitest run needed `PATH="/opt/homebrew/opt/node@24/bin:$PATH"` — exactly the incantation `frontend/CLAUDE.md:15` documents. That is `mise`, Phase 1 of `design-dev-environment.md`.

## Rule of thumb this leaves behind

For the next consolidation tool that looks like this: **ask what N is before asking how fast it is.** A tool that collapses N things into one pays out in proportion to how fragmented you already are. This repo's frontend is the least fragmented part of it.
