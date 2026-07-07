# Testing & acceptance — the one map

_Canonical index for how Bristlenose is tested. Start here. Consolidated 7 Jul 2026 from the previously-scattered acceptance/QA thinking into one set._

## The three-tier model

| Tier | Fidelity | Cost | Catches | Status |
|---|---|---|---|---|
| **CI** (`tests/`, pytest) | mocked, hermetic | seconds, free | logic regressions | ✅ built |
| **Playwright** (`e2e/`) | real `serve`, fixture data, no LLM | ~1 min, free | SPA/DOM/render/link/network | ✅ built |
| **Acceptance matrix** ([acceptance-matrix.md](acceptance-matrix.md)) | real binaries, real providers, real reports | mins–hrs, ¢ | cross-seam, packaging, provider, GUI-integration | ⬜ Phase 1 not built |
| **Human walk** (private QA doc) | a person operating the `.app` | hours | feel, native chrome, "nothing surprised you" | ongoing |

The **defining split** (the whole reason this set exists): the top two tiers are *hermetic* — they never touch real binaries/providers, so they're fast and free but blind to a whole class of cross-seam bug (the gemma4 env-var bug that passed all three green nets — see acceptance-matrix "Why this exists"). The acceptance matrix is the mechanical tier that exercises the real seams; the human walk is the judgment tier. **Mechanical green de-risks the human walk, it does not replace it** — Playwright proves the SPA renders in a *browser*, never in the WKWebView `.app` where the blank-report-as-success class lives.

## The documents (one set)

**Here in `docs/testing/`:**
- **[acceptance-matrix.md](acceptance-matrix.md)** — the mechanical tier. Three-tier model, shape-not-content invariants, drive mechanisms ranked by ROI, phased plan, overnight-run gates. Plan of record.
- **[coverage-inventory.md](coverage-inventory.md)** — the single source of *what surfaces exist to cover* (16 ingest formats · 5 exports · 5 lenses + every clicking surface · 5 providers · non-English). Both tiers consume it. Add new surfaces here first.
- **[test-data-generation.md](test-data-generation.md)** — repeatable recipe for synthetic fixtures (any topic/language/scale).
- **[real-data-testing.md](real-data-testing.md)** — using real interview data under governance.

**Elsewhere (indexed here, left in place — widely referenced):**
- [`docs/design-test-philosophy.md`](../design-test-philosophy.md) — the testing pyramid + house position (James Bach / context-driven).
- [`docs/design-test-strategy.md`](../design-test-strategy.md) — per-layer audit, tool choices.
- [`docs/design-playwright-testing.md`](../design-playwright-testing.md) — tier-2 Playwright specifics.
- [`docs/design-perf-stress-test.md`](../design-perf-stress-test.md) + [`docs/design-perf-regression-gate.md`](../design-perf-regression-gate.md) — performance/stress + CI gate.
- [`desktop/CLAUDE.md`](../../desktop/CLAUDE.md) §testing — Swift Testing conventions + the testable-helper rule that bounds GUI automation.
- **Private human tier** — the walks-fix-walks QA doc (cohort/TF-gated, under the gitignored private docs tree): the by-hand end-to-end walk, upload-day steps, and the concrete fixture-folder mapping. Kept private because it carries TF timing + cohort detail.

**Code artifacts:**
- `tests/test_no_fake_success_acceptance.py` — ✅ built. Executable fake-success audit: full pipeline on real data × providers × formats, asserts every success signal has a real artifact. `@pytest.mark.slow`, each leg **skips if its input is absent** — currently waiting on the format-parity fixtures.
- `e2e/` — Playwright tier 2 (Chromium + WebKit; layers 1–3: console, links, network). `e2e/ALLOWLIST.md` governs suppressions.
- `tests/fixtures/smoke-test/` — the committed synthetic single-session fixture both CI and Playwright trust.

## What's next (iterated plan, 7 Jul 2026)

The mechanical/human split is settled; the build order is Phase 1 of the acceptance matrix, highest-ROI first (all free or ¢, none needs the `.app`):

1. **Close the fixture gap** — produce the format-parity `.docx` (Teams + Meet) + the 10 missing media/subtitle containers, so the *already-written* `test_no_fake_success_acceptance.py` stops skipping. Recipe in test-data-generation.md; gap tracked in coverage-inventory.md §1.
2. **Phase-1 CLI provider matrix** — `scripts/acceptance/` : text-fixture `analyze × 5 providers` + one media `run` cell, shape-invariant assertions, one summary file. Local cell is free; provider column ≈ pennies. This is the backbone that catches the motivating bug class.
3. **Extend the Playwright pass** — "every lens loads clean" (visit all 5 lenses, assert mount + zero console errors) + export structural checks (HTML self-contained, XLS valid, clips ffprobe-valid, anonymised = zero PII).
4. **Wire the human doc to this set** — tag each atom in the private walk `[matrix]` / `[e2e]` / `[human]` so the by-hand load visibly shrinks to judgment-only.

Phases 2–3 (desktop GUI smoke via XCUITest, `launchd` nightly, one HTML dashboard) are specified in acceptance-matrix.md and stay post-Phase-1.
