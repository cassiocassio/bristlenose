# Design: Acceptance Matrix — overnight "real" conformance runs

_Status: proposed (29 Jun 2026). Phase 1 not yet built. This doc pins the model, the
invariants, and the overnight-execution gates before any runner code lands._

## Why this exists

Bristlenose has two automated test layers today, and both are **hermetic by
construction** — they deliberately avoid real binaries, real providers, and real
workloads so they stay fast and free. That is correct for what they are, but it
leaves a whole class of bug invisible.

**Worked proof (the bug that motivated this doc, 29 Jun 2026):** the desktop app
injected the user's selected Ollama model into `BRISTLENOSE_LLM_MODEL` (the cloud
axis) instead of `BRISTLENOSE_LOCAL_MODEL` (the axis Ollama execution actually
reads). Every local run silently fell back to the `llama3.2:3b` default, which is
too small for structured output, so topic segmentation 100%-failed ("All topic
segmentation calls failed"). This shipped past **all three** existing green
nets:

- **CI (pytest)** — green. Mocks the environment; never injects an env var from
  Swift and runs a real model end to end.
- **Playwright** (`e2e/`) — green. Drives the SPA against a pre-baked fixture
  report; never runs the pipeline or touches a provider.
- **Swift unit tests** — green. `overlayPreferences` had coverage, but nothing
  asserted that the value reaching it was the one a *user picked*, nor that it
  produced a real report.

The bug lived in the one place none of them look: the real seam **GUI setting →
UserDefaults → env var → subprocess → real LLM → real report.** The acceptance
matrix is the tier that exercises exactly that seam.

## The three-tier model

| Tier | Fidelity | Cost | Catches |
|---|---|---|---|
| CI (`tests/`, pytest) | mocked, hermetic | seconds, free | logic regressions |
| Playwright (`e2e/`) | real `serve`, fixture data, no LLM | ~1 min, free | SPA/DOM/render/link/network regressions |
| **Acceptance matrix** (this doc) | **real binaries, real workloads, real providers, real reports** | **minutes–hours, $ + heat** | **cross-seam, packaging, provider, GUI-integration regressions** |

The new tier's defining property is **low determinism, high fidelity** — the
deliberate inverse of CI. That tension drives every choice below: we assert
*shape*, never content, and we accept that a cell can be slow and a little noisy
in exchange for catching what the hermetic tiers cannot.

## The matrix

Run representative **cells**, not the full cartesian product (which is
thousands). Axes:

- **Inputs** — one each of: audio (`.m4a`/`.mp3`), video (`.mp4`/`.mov`),
  subtitles (`.vtt`/`.srt`), `.docx`, plain transcript `.txt`. Exercises stages
  s01–s04.
- **Commands** — `run`, `analyze`, `transcribe`, `serve`, `status`, `doctor`.
  Plus `render` (a hidden deprecation stub at `cli.py:1439` — a free conformance
  cell: assert it exits 2 with the "was removed" message).
- **Providers** — `anthropic` (claude), `openai` (chatgpt/gpt), `google`
  (gemini), `azure`, `local` (ollama). Aliases in `bristlenose/providers.py`.
  **Default nightly cell set = all five** (decided 29 Jun 2026). Cloud cells
  need capped keys; Azure additionally needs endpoint + deployment configured;
  local needs Ollama running with the model pulled.
- **Surfaces** — CLI byproduct (md/html on disk), `serve` + SPA, **desktop
  app**, exports (HTML / CSV / clips / Miro).

**Fixtures.** Two sources: the committed smoke fixture
(`tests/fixtures/smoke-test/`) for hermetic shape checks, plus a **local-only,
gitignored** set of representative interview folders (one per input type) for the
real provider runs. Real interview data stays out of git — fixture selection is a
governance call (see Open questions), not just a storage one.

**Scoping insight that bounds the fragile part:** the desktop app is a thin
shell over the Python sidecar — ~80% of "out-of-box behaviour" *is* CLI/serve
behaviour. So a CLI + serve matrix already covers most of the product's real
work. The genuinely app-only seams are narrow: settings→env (the motivating
bug), consent gating (`AIConsentView`), sidebar/project management, export-menu
wiring, bridge actions. Only those need GUI automation, which shrinks the scary
tier dramatically.

## Invariants — assert shape, not output

LLM output is nondeterministic; we cannot diff report text. We assert structural
invariants that hold across providers and across re-runs:

**Pipeline**
- Process exit 0.
- Terminus event in `<output>/.bristlenose/pipeline-events.jsonl` is
  `RunCompletedEvent` (type `run_completed`), **not** `RunFailedEvent` /
  `RunCancelledEvent`.
- No stage summary with `attempted > 0 and succeeded == 0` (the
  `PipelineAbandonedError` condition — `bristlenose/events.py:202`,
  `pipeline.py`). The gemma4 bug trips this first; a one-line check catches it.

**Report content**
- `sessions == N` (known per fixture).
- themes ≥ 1; total quotes ≥ a per-fixture floor.
- Every report section non-empty (the **quote-exclusivity** invariant —
  `bristlenose/stages/CLAUDE.md`: every quote appears in exactly one section).

**Governance (privacy)**
- `pii_summary.txt` and `llm-calls.jsonl` exist in `.bristlenose/` and are
  **absent** from the shareable output root *and* from every export artifact
  (both are re-identification keys — see CLAUDE.md).

**Serve + SPA**
- `#bn-app-root` mounts; zero console errors; counts match the run.

**Exports**
- zip opens; CSV parses; exported HTML is self-contained (no `localhost`/
  `127.0.0.1` references).

**Provenance (overnight desktop only)**
- The bundled sidecar's `bristlenose_version` (from a run's `RunStartedEvent`)
  equals the tree `__version__` — proves we tested *today's* code, not a stale
  bundle (see Overnight gate 2).

## Drive mechanisms, ranked by ROI

1. **Bash → CLI** (Phase 1). `bristlenose run <fixture> --llm X`, parse report
   JSON, assert invariants. No TCC, no GUI, fully unattended. Would have caught
   the motivating bug at ~zero cost. **~70% of the value for ~10% of the
   effort.**
2. **Bash → `serve` + Playwright** (Phase 2). Boot a real `serve` against a
   freshly-*run* project (not the baked fixture), assert SPA + exports. Medium
   cost, no TCC.
3. **GUI automation** (Phase 3, scope tiny). XCUITest preferred over AppleScript
   (in-process, less fragile). *Only* for the irreducible app-only seam: launch
   → pick project → pick Ollama model → Run → wait → report shows expected
   counts. **Not** "press every button" — most button *logic* belongs in
   testable Swift helpers per the house rule in `desktop/CLAUDE.md`
   (`DropDecision`, `RevealAvailability`, `ProjectSubtitle`, …), leaving GUI
   drive for the few true integration paths.

## Overnight execution model — the four hard gates

"Wake up to greens" has four sharp edges. The runner must handle each explicitly.

1. **TCC / permission prompts will wedge an unattended GUI run.** AppleScript UI
   scripting needs Accessibility + Automation grants; XCUITest, Keychain reads,
   and the consent dialog (Apple 5.1.2(i)) can all prompt. Per the project rule
   that *an overnight goal whose gate needs a physical gesture or live TCC grant
   must halt loudly, not stall silently*: pre-grant everything once,
   interactively; the nightly run **asserts the grants exist and halts with a
   clear message if not.** Tiers 1–2 have no TCC surface — another reason
   they're the backbone.

2. **The stale-sidecar trap is lethal here.** A desktop cell that doesn't
   rebuild + sign the sidecar first tests *yesterday's* Python (documented
   repeatedly in `desktop/CLAUDE.md`; the version in `pipeline-events.jsonl` is
   the tell). The runner's **step 1** is
   `desktop/scripts/build-sidecar.sh && SIGN_IDENTITY=- desktop/scripts/sign-sidecar.sh`
   + clean build, then assert bundled `bristlenose_version == __version__`
   before any desktop cell runs.

3. **Cost, heat, battery, determinism.** Cloud cells cost money + need keys
   (capped, non-renewing keys are proportionate per the threat model). Local
   cells are free but slow + GPU-pinned + hot — **must be plugged in** (a 24 GB
   model on battery gives <1 h runtime). Determinism is handled by the
   shape-only invariants above.

4. **Known flakes to design around** — all documented:
   - Playwright `reuseExistingServer` + a stale `serve` on port 8150 →
     wrong measurements. Use fresh ports / check `lsof -i :8150`.
   - The smoke fixture's `RunCompletedEvent` terminus contract (a fixture
     without it never mounts the SPA).
   - Concurrent `xcodebuild test` teardown hangs across worktrees — run Xcode
     cells serially.

## "Green in the morning" mechanism

A single `scripts/acceptance/nightly.sh` that: rebuilds → runs each matrix cell
→ captures per-cell pass/fail + logs + the actual produced reports as artifacts
→ emits **one** `acceptance-report.html` built from `bristlenose/theme/` tokens
(never bespoke inline CSS — house rule). Schedule via `launchd` (plugged in,
screen may sleep). Morning = open one page, read the grid, click any red cell
through to its log + the report it produced.

## Phased plan

- **Phase 1** — bash CLI provider matrix: 5 providers × representative fixtures,
  JSON-invariant assertions, one summary file. Unattended, no TCC. *Highest ROI;
  catches the motivating bug class.*
- **Phase 2** — real-`serve` + Playwright-on-fresh-run + export checks.
- **Phase 3** — one thin XCUITest GUI smoke for the app-only seam; the `launchd`
  nightly; the HTML dashboard; the pre-grant / halt-on-gate discipline.

## Open questions (decide as we build)

- **Cloud spend ceiling per night** — cap which fixtures run against paid
  providers (e.g. smallest fixture for cloud, full for local).
- **Where artifacts live** — a gitignored `acceptance-runs/` dir vs. a temp dir
  wiped each run. Reports may carry real interview content, so this is a
  governance call, not just storage.
- **Failure routing** — morning summary only, or a push/notification on red.
- **Fixture provenance** — which inputs are safe to commit vs. local-only (real
  interview data must stay out of git).

## See also

- `e2e/` + `docs/design-playwright-testing.md` — tier 2 as it exists today.
- `docs/design-test-strategy.md`, `docs/design-test-philosophy.md` — the testing
  pyramid this extends.
- `desktop/CLAUDE.md` — sidecar-rebuild trap, TCC/sandbox notes, the
  view-logic-into-helpers rule that bounds Phase 3.
- `bristlenose/events.py` — terminus event taxonomy the invariants read.
