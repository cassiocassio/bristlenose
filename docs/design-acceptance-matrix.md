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
(`tests/fixtures/smoke-test/`) — a synthetic single-session `.vtt`, ~4 quotes,
already trusted by Playwright — plus a **local-only, gitignored** set of
representative *media* folders (audio/video) for the transcription path. Real
interview data stays out of git — fixture selection is a governance call (see
Open questions), not just a storage one.

**Transcription is provider-independent; only analysis is provider-specific.**
This single fact shapes the whole matrix. Whisper runs locally and produces the
same text regardless of which LLM later analyses it, so a cloud provider is only
ever exercised by the analysis stages (s08–s11). Two consequences:

- **The per-provider column uses text, not media.** Run
  `analyze <text-fixture> --llm <provider>` (the committed `.vtt` needs no
  Whisper — subtitle parse, not transcription) so the cell goes straight to the
  provider's wire path (auth, request/response format, model-name resolution,
  schema handling) — the only thing it uniquely tests. Feeding media to a cloud
  cell would pay Whisper time to test nothing cloud-specific. The fixture must be
  big enough to produce a *non-empty* report (≥1 boundary/quote/theme) or the
  shape invariants go vacuous — but it need not be real or large; the smoke
  fixture's ~4 quotes is the right size.
- **The media path is one cell, not a column.** A small media fixture → `run`,
  executed **once on local**, covers Whisper + the transcription→analysis
  handoff. Running it per cloud provider would re-test provider-independent
  transcription N times for no gain.

So the matrix is not "every fixture × every provider." Three groups:

- **Wire-path column** — text → `analyze` × all 5 providers. Where the motivating
  bug class lives.
- **Transcription cell** — a media fixture (video or audio) → `run` × 1, local.
  Covers extract-audio (s02) + Whisper (s05) + the handoff to analysis.
- **Input-format cells** — the non-media parsers (`.vtt` s03, `.docx` s04, `.txt`
  s01) as fast **local-only** `analyze` runs. Each format hits a different ingest
  stage, so span them — but they're all provider-independent and never multiply
  across the provider column.

The whole input funnel (video → audio → words) sits *upstream* of any provider;
the cloud columns are purely downstream of it.

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

## Desktop acceptance — the commercial surface gets an early end-to-end

The macOS app is the commercial target, so it gets a minimal end-to-end *early*,
not relegated to "GUI, later." Crucially, **the engine being green does not prove
the native surface is green** — Playwright proves the SPA renders in a *browser*,
but the WKWebView bridge, auth-token injection, and report-auto-reload are
app-only and have silently broken before (the blank-report-rendered-as-success
class). So "display the result" needs a real `.app` launch, not just a served
report.

Three sub-steps, two of them headless and key-free (all use `--llm local`, so no
API key and no spend — and they re-exercise the exact Ollama path that the
motivating bug broke):

1. **Build (headless).** `build-sidecar.sh` → `sign-sidecar.sh` (ad-hoc `-`) →
   `xcodebuild build` → assert bundled `bristlenose_version == __version__`.
   Proven to work headlessly (used for `build-for-testing` already).
2. **"Process a run" — headless engine cell (Phase 1).** A Swift integration
   test that builds the env via the *real* `BristlenoseShared.childEnvironment`
   (the seam the motivating bug lived in), spawns the *bundled* sidecar (proves
   the PyInstaller bundle executes — datas, ffmpeg, JIT entitlements), runs the
   tiny `.vtt` fixture, and asserts a `RunCompletedEvent` terminus. No window, no
   TCC, no key.
3. **"Display the result" — GUI smoke (Phase 2).** XCUITest: launch `.app` → pick
   the smoke project → Run → wait for terminus → assert the result is *shown*.
   Robust assertion = screenshot (for the dashboard) + the WebView is not on the
   empty/status page (known DOM/AX element, or shape-check the served port) —
   because the failure mode is "blank report rendered as success," which only a
   look-at-the-rendered-surface test catches. One-time TCC grant for the test
   runner (see gate 1).

## Overnight execution model — the four hard gates

"Wake up to greens" has four sharp edges. The runner must handle each explicitly.

1. **TCC / permission prompts will wedge an unattended GUI run — so front-load
   every human gate before the unattended window.** This is the operational key
   to the whole overnight ambition, and it works: the gates are one-time and
   sticky. Bedtime checklist clears them all: TCC Accessibility + Automation (for
   the test runner), the consent dialog (5.1.2(i), persisted in `@AppStorage`),
   Gatekeeper / first-launch ("app differs"), the folder-access bookmark for the
   fixture projects, the firewall "accept incoming connections" prompt, Ollama
   model pulled + daemon running, plugged in. Desktop cells use `--llm local`, so
   there are **no API keys or Keychain prompts at all**.

   **The ordering that bites: do not rebuild inside the unattended window.** A
   fresh binary re-triggers Gatekeeper / "app differs" / first-launch, which
   invalidates the grants you just cleared. So: **build as the last bedtime step
   → launch once and clear all prompts against *that exact* `.app` → the nightly
   RUNS it, it does not rebuild.** The headless cells may rebuild freely (they
   never prompt); only the GUI smoke needs the blessed build — and a fresh
   bedtime build already satisfies the stale-sidecar gate. (Keychain survives
   rebuilds via the data-protection keychain; local-provider sidesteps it
   anyway.)

   **What front-loading cannot fix — keep the session alive.** GUI automation
   needs a live WindowServer; sleep/lock stalls XCUITest. Wrap the run in
   `caffeinate -dimsu`, set auto-lock off, stay logged in (display may be dark,
   session must stay live).

   **Safety net regardless:** per the project rule that *an overnight goal whose
   gate needs a live gesture must halt loudly, not stall silently*, the runner
   still **asserts each grant exists up front and halts with a clear message** on
   a missing grant or an unexpected prompt — morning shows "needs TCC for X," not
   a silent hang. Tiers 1–2 (CLI, headless engine cell) have no TCC surface —
   another reason they're the backbone.

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

Both the CLI iceberg *and* the commercial surface's engine land in Phase 1 —
because the desktop is what people pay for and the headless engine cell is nearly
free once we're already building the sidecar.

- **Phase 1** — (a) bash CLI provider matrix: 5 providers × representative
  fixtures, JSON-invariant assertions, one summary file; (b) the **headless
  desktop engine cell** (sidecar+app build → Swift integration test:
  `childEnvironment` → bundled sidecar → run on fixture → `RunCompletedEvent`).
  Both unattended, no TCC, no keys (desktop uses `--llm local`). *Highest ROI;
  catches the motivating bug class on both surfaces.*
- **Phase 2** — the **desktop GUI smoke** ("display the result": XCUITest launch
  → pick smoke project → Run → assert rendered, via screenshot + shape) +
  real-`serve` + Playwright-on-fresh-run + export checks. Runs interactively
  first (one-time TCC grant); unattended scheduling comes in Phase 3.
- **Phase 3** — the `launchd` nightly orchestration; the HTML dashboard; the
  pre-grant / halt-on-gate discipline that lets the GUI smoke run unattended;
  broaden cells.

## Open questions (decide as we build)

- ~~**Cloud spend ceiling per night**~~ — _resolved 29 Jun 2026:_ the
  per-provider column runs the small synthetic text fixture via `analyze`
  (~a dozen small calls × 5 providers ≈ pennies/night); the media path is a
  single local `run` cell. No real cap needed at this scale; revisit only if the
  fixture set grows.
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
