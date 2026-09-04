# Testing & acceptance — the one map

_Canonical index for how Bristlenose is tested. Start here. Consolidated 7 Jul 2026 from the previously-scattered acceptance/QA thinking into one set._

## The three-tier model

| Tier | Fidelity | Cost | Catches | Status |
|---|---|---|---|---|
| **CI** (`tests/` pytest · `frontend` vitest · `BristlenoseTests` Swift) | mocked, hermetic | seconds, free | logic regressions | ✅ built — Swift joined 3 Sep 2026, having run nowhere automatic until then |
| **Playwright** (`e2e/`) | real `serve`, fixture data, no LLM | ~1 min, free | SPA/DOM/render/link/network | ✅ built |
| **Acceptance matrix** ([acceptance-matrix.md](acceptance-matrix.md)) | real binaries, real providers, real reports | mins–hrs, ¢ | cross-seam, packaging, provider, GUI-integration | ⬜ Phase 1 not built |
| **Human walk** (private QA doc) | a person operating the `.app` | hours | feel, native chrome, "nothing surprised you" | ongoing |

The **defining split** (the whole reason this set exists): the top two tiers are *hermetic* — they never touch real binaries/providers, so they're fast and free but blind to a whole class of cross-seam bug (the gemma4 env-var bug that passed all three green nets — see acceptance-matrix "Why this exists"). The acceptance matrix is the mechanical tier that exercises the real seams; the human walk is the judgment tier. **Mechanical green de-risks the human walk, it does not replace it** — Playwright proves the SPA renders in a *browser*, never in the WKWebView `.app` where the blank-report-as-success class lives.

## The documents (one set)

**Here in `docs/testing/`:**
- **[gaps.md](gaps.md)** — what is *not* covered, ranked by what reaches a user, each with
  the command that measured it. The judgement layer over the generated inventory below.
- **[inventory.md](inventory.md)** — **generated**, never hand-written: every suite, every workflow and its triggers, every gate and whether a failure actually fails the job, the step lists of **both** shipping entry points (`build-all.sh` for the App Store archive, `build-dmg.sh` for the notarised download — two certificates, two channels, neither covering the other), and the local hooks. Produced by `scripts/gen-test-inventory.py`; `--check` exits 1 when the structure drifts from the tree. Read this before trusting any count or claim in the prose docs below — on 2 Sep 2026 four of them were measurably wrong, including this file's own "16 ingest formats" against coverage-inventory.md's 27.
- **[bn-release-acceptance.md](bn-release-acceptance.md)** — acceptance criteria for the `/bn-release` skill. Scores *behaviour under instruction* rather than code, so a pass is one observation and not a proof. Three tiers: dry run (free, repeatable), fault injection, live release. Written before the skill's first run, on purpose.
- **[acceptance-matrix.md](acceptance-matrix.md)** — the mechanical tier. Three-tier model, shape-not-content invariants, drive mechanisms ranked by ROI, phased plan, overnight-run gates. Plan of record.
- **[coverage-inventory.md](coverage-inventory.md)** — the single source of *what surfaces exist to cover*: ingest formats, exports, lenses and every clicking surface, providers, non-English. Both tiers consume it. Add new surfaces here first. **The counts live there and are deliberately not repeated here** — this line used to say "16 ingest formats" while the file it calls the single source said 27, which is what restating a number in two places buys you.
- **[test-data-generation.md](test-data-generation.md)** — repeatable recipe for synthetic fixtures (any topic/language/scale).
- **[real-data-testing.md](real-data-testing.md)** — using real interview data under governance.

**Elsewhere (indexed here, left in place — widely referenced):**
- [`docs/design-release-system-audit.md`](../design-release-system-audit.md) — eight-lens adversarial audit of the release system (scripts, both skills, the three workflows), run the morning after the 0.25.2 incident. Pairs with `bn-release-acceptance.md` above: that doc asks whether the skill behaves, this one asks whether the machinery underneath it can be trusted. Findings carry their verification status inline — nine confirmed by skeptics who re-derived them, six high-severity still unverified. Untriaged; §5 proposes rescoping the acceptance doc's own protocol and its `S9` criterion.
- [`docs/design-test-philosophy.md`](../design-test-philosophy.md) — the testing pyramid + house position (James Bach / context-driven).
- [`docs/design-test-environments.md`](../design-test-environments.md) — the **instruments**: which machines and OS versions can run these tiers, and what each one is blind to. Orthogonal to the tier model above — that doc asks "what kind of test?", this one asks "what can actually prove it?". Written 2 Sep 2026 when three macOS sidebar geometries went live at once (Sequoia flat / Tahoe inset plateau / Golden Gate edge-anchored again) and the visual question turned out to be the one a VM is worst at. Carries the EULA two-VM grant, the Apple-ID-in-VM limits, and an explicitly-unverified caveat about Liquid Glass fidelity under Virtualization.framework.
- [`docs/archive/design-test-strategy.md`](../design-test-strategy.md) — per-layer audit, tool choices.
- [`docs/design-playwright-testing.md`](../design-playwright-testing.md) — tier-2 Playwright specifics.
- [`docs/design-perf-stress-test.md`](../design-perf-stress-test.md) + [`docs/design-perf-regression-gate.md`](../design-perf-regression-gate.md) — performance/stress + CI gate.
- [`desktop/CLAUDE.md`](../../desktop/CLAUDE.md) §testing — Swift Testing conventions + the testable-helper rule that bounds GUI automation.
- **Private human tier** — the walks-fix-walks QA doc (cohort/TF-gated, under the gitignored private docs tree): the by-hand end-to-end walk, upload-day steps, and the concrete fixture-folder mapping. Kept private because it carries TF timing + cohort detail.

**Code artifacts:**
- `tests/test_no_fake_success_acceptance.py` — ⚠️ **written, never run.** Measured 4 Sep 2026: 6 tests, **6 skipped**, exit 0 (needs `-m slow`; the bare command now deselects them) — and a skip is indistinguishable from a pass in a summary line, a badge, or a close-out report, so the fake-success auditor currently produces a fake success ([gaps.md](gaps.md) G2). Executable fake-success audit: full pipeline on real data × providers × formats, asserts every success signal has a real artifact. `@pytest.mark.slow`, each leg **skips if its input is absent** — currently waiting on the format-parity fixtures.
- `e2e/` — Playwright tier 2 (Chromium + WebKit; layers 1–3: console, links, network). `e2e/ALLOWLIST.md` governs suppressions.
- `tests/fixtures/smoke-test/` — the committed synthetic single-session fixture both CI and Playwright trust.

## What's next (iterated plan, 7 Jul 2026 — **audited 3 Sep 2026**)

> Two of the four items below had already shipped when this was audited, one of
> them in the very commit that wrote the list. A plan nobody is obliged to
> reconcile reads as a backlog when it is partly a changelog. Items 1 and 4
> remain genuinely open.

The mechanical/human split is settled; the build order is Phase 1 of the acceptance matrix, highest-ROI first (all free or ¢, none needs the `.app`):

1. **Close the fixture gap** — produce the format-parity `.docx` (Teams + Meet) + the 10 missing media/subtitle containers, so the *already-written* `test_no_fake_success_acceptance.py` stops skipping. Recipe in test-data-generation.md; gap tracked in coverage-inventory.md §1.
2. ~~**Phase-1 CLI provider matrix** — `scripts/acceptance/`~~ ✅ **shipped 22 Aug 2026** (`scripts/acceptance/run_matrix.py` + `invariants.py`; two free cells and five gated ones). [acceptance-matrix.md](acceptance-matrix.md) tracked this correctly and this list did not — the second of two items here that stayed "next" after landing. Text-fixture `analyze × 5 providers` + one media `run` cell, shape-invariant assertions, one summary file.
3. ~~**Extend the Playwright pass** — "every lens loads clean"~~ ✅ the lens half shipped **7 Jul 2026**, in the very commit that wrote this list (`e2e/tests/lenses-load-clean.spec.ts`, "add acceptance-testing tier: format coverage, invariant harness, lens smoke"). It sat here as future work for two months. Still open: the export structural checks — + export structural checks (HTML self-contained, XLS valid, clips ffprobe-valid, anonymised = zero PII).
4. **Wire the human doc to this set** — tag each atom in the private walk `[matrix]` / `[e2e]` / `[human]` so the by-hand load visibly shrinks to judgment-only.

Phases 2–3 (desktop GUI smoke via XCUITest, `launchd` nightly, one HTML dashboard) are specified in acceptance-matrix.md and stay post-Phase-1.
