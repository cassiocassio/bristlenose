# TypeScript 7 (native compiler) — adoption assessment

**Status:** parked, gated. **Recommendation: don't adopt yet.** **Gate: revisit when `typescript-eslint` ships native-compiler support (~TS 7.1).**
**Assessed:** 2026-06-21, against TS 7.0 RC ([announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0-rc/)).

TS 7.0 is the Go rewrite of `tsc` (~10× faster type-check). Same type-checking semantics as 6.0 ("architectural parity"), but turns all of 6.0's new defaults/deprecations into hard errors.

## Why this is the cheap half of the migration

We're already on **TS `~6.0.3`** (`frontend/package.json`), the bridge release. Our `frontend/tsconfig.json` already pre-satisfies **4 of the RC's 5 breaking changes**:

| 7.0 breaking change | Us | Why non-issue |
|---|---|---|
| `strict` defaults true | already `true` | tsconfig:14 |
| `noUncheckedSideEffectImports` defaults true | already `true` | tsconfig:18 |
| `target: es5` dropped | we're `ES2020` | tsconfig:3 |
| `types: []` (no auto-discovery) | already explicit `["vitest/globals","@testing-library/jest-dom"]` | tsconfig:19; `vite/client` via `/// <reference>` in `src/vite-env.d.ts` |
| `rootDir` defaults to `./` | **live** | `include` reaches outside the dir into `../bristlenose/locales` (tsconfig:24) + `@locales/*` path map; `noEmit` likely neutralises it, but it's the one config edge to actually check |

So the residual risk is config edges, not the documented breaking-changes list.

## What interacts

**The only real blocker — `typescript-eslint` (`^8.59.x`):**
- Already needs `--legacy-peer-deps` (pins `typescript < 6.0.0` peer; works with 6). 7.0 repeats this.
- Deeper: type-aware lint calls the TS **compiler API**, which the native compiler **does not expose until ~7.1** (API work explicitly deferred in the RC). So you can't point typescript-eslint at native `tsc`.
- **Consequence:** adopting at 7.0 = run **two compilers** — native for typecheck/build, JS `typescript@6` (aliased) kept for lint. That dual-compiler carry is the *entire* non-trivial work item, and ~7.1 deletes it for free.
- Mitigating: lint is `continue-on-error: true` in CI (`ci.yml:144`, informational, 84 pre-existing). So even if tsel chokes on 7.0, **CI stays green**.

**The compiler swap — `tsc` at 5 CI sites:**
- `npm run typecheck` = `tsc --noEmit` (`ci.yml:150`, hard gate) and `npm run build` = `tsc -b && vite build` (hard gate), the build invoked in ci / release / perf / e2e jobs.
- Edges to verify: `tsc -b` project-build mode on the native compiler (landed late in the port); the cross-dir `../bristlenose/locales` include + `rootDir` default (above).

**Insulated — will NOT interact (shrinks the blast radius):**
- **Vite 8 / Rolldown + `@vitejs/plugin-react`** — transpile is Rust, never calls `tsc`. A 7.0 swap *can't* break bundling, only type-checking. Built JS is byte-identical → bundle-size gate unaffected.
- **Vitest 4** — runs via Vite's transform, doesn't type-check; test types ride the same `tsc -b`.
- **React 19 / `@types/react` / react-router / i18next** — bundled/module types, 7.0 supports.
- **Playwright e2e** — own `e2e/tsconfig.json`, own loader, no `tsc` in its path; consumes the *built* JS. Fully insulated.

## How to test what we have

CI is green on TS 6 today → clean **A/B against a known baseline**; any new error *is* the 7.0 delta. Throwaway branch, nothing shippable (wheel ships `bristlenose/`, not frontend source; Rolldown does transpile so output is identical). ~30–60 min:

```sh
cd frontend
npm i -D typescript@rc      # or @typescript/native-preview to keep 6 alongside
npm run typecheck           # tsc --noEmit on native — diff errors vs TS6 baseline   ← main signal
npm run build               # proves tsc -b project-mode + vite/Rolldown emit        ← main signal
npm test                    # vitest — expect no signal (doesn't typecheck); confirms toolchain
npm run lint                # expect typescript-eslint to refuse/degrade → confirms dual-compiler finding
npm run size                # confirms bundle unchanged
```

## Work to fully adopt (distinct from testing)

1. Dual-compiler pinning — `typescript@7` for `tsc` + `typescript@6` aliased for typescript-eslint, **until tsel native support (~7.1)**. The only non-trivial work, forced entirely by the tsel API gap.
2. Editor parity note in `frontend/CLAUDE.md` — native editor support is a separate "TypeScript Native Preview" extension; mixed-editor contributors get identical semantics, different speed.
3. Swap the compiler across the 5 CI sites + re-baseline (low risk — parity semantics).
4. Update the two stale tsel / TS6 gotchas in `frontend/CLAUDE.md` (`--legacy-peer-deps`, stricter-mock note).

## Recommendation

**Park, gated.** No present `tsc` pain (typecheck/CI not a measured bottleneck); 7.0 is parity so no correctness gain, only speed we aren't short of; the only real work is forced by a gap that self-resolves at ~7.1. Re-examining now measures a state about to change. Natural fit for a `cassandra` pre-mortem + `docs/dependency-premortem-log.md` entry when 7.1's API lands. Tracked as a gated "should" in the private launch planner (Dependency maintenance section).

If the number is wanted sooner than 7.1: run the ½-day spike above on a throwaway branch; deliverable is a go/no-go + error-diff, no merge.
