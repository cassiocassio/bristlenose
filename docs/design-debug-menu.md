# Debug menu & instrumentation — candidate additions

Status: **largely shipped** (28 Jun 2026, branch `claude/debug-menu-instrumentation-4r9npy`).
Began as a survey of the existing debug surface + a ranked candidate list; the
recommended first cut (#1–#4 + #9) plus the native Run Inspector window, the live
diagnostic-fixtures submenu (#6), and a build-time sidecar-staleness gate are now
built. The survey and ranked list below are preserved for context (they record
the reasoning and the not-yet-built remainder); **see "Implementation" at the
foot for exactly what shipped.**

The guiding principle is **reveal, don't reinvent**: most of the high-value
items below expose data that the pipeline/serve layers *already capture* — they
turn a Finder dig or a three-command `grep` into one click. New logging paths
are explicitly out of scope.

## What exists today

### Desktop `Debug` menu (`MenuCommands.swift`, `#if DEBUG`)
Two items only:
- **Type Parity Inspector** (⌘⌃T) — dedicated window for the TypeParity ladder.
- **Ollama setup-pill state harness** — cycle (⌘⌃O) or force every
  `OllamaDownloadModel.DebugScene`; "Hide pill (idle)". Drives the pill through
  all states with no daemon/network. This is the *pattern* to copy: force a
  surface through its states from a reliable menu-bar menu (a toolbar
  `.contextMenu` is swallowed by "Customize Toolbar" — see `desktop/CLAUDE.md`).

### Env-var harnesses (no menu surface)
- `BRISTLENOSE_DEBUG_500=1` — raw exception on 500s.
- `BRISTLENOSE_DEBUG_OLLAMA_PHASE=<scene>` — force pill state at launch.
- `BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE=<scenario>` — inject a synthetic
  pipeline-failure state into the sidebar for popover QA (13 scenarios + gallery).
- `BRISTLENOSE_DEV_SIDECAR_PATH` / `BRISTLENOSE_DEV_EXTERNAL_PORT` — sidecar mode.

### `serve --dev` endpoints (`bristlenose/server/routes/dev.py`)
- `GET /api/dev/info` — system info, DB path, endpoint list (About tab).
- `GET /api/dev/sessions-table-html` — Jinja2 sessions table (visual React diff).
- `POST/GET/DELETE /api/dev/telemetry` — alpha tag-rejection telemetry stub.
- `GET/POST /api/dev/codebook-lab/*` — dynamic-codebook-builder experiment UI.
- `/admin/` — SQLAdmin DB browser (dev-only). `/api/docs` — Swagger.

## Instrumentation that exists but isn't reachable from a menu

| Artifact | Location | Captures |
|---|---|---|
| Run log | `<output>/.bristlenose/bristlenose.log` | per-stage lines, `sidecar_exit`, `llm_request`, `llm_resolve` |
| LLM call log | `<output>/.bristlenose/llm-calls.jsonl` | model, tokens (in/out/cache), cost, latency, retries, finish reason (OTel GenAI schema) |
| Pipeline events | `<output>/.bristlenose/pipeline-events.jsonl` | run_started/progress/completed/failed; `bristlenose_version` |
| Last failure | `<output>/.bristlenose/last-run-failure.log` | redacted stderr tail |
| Timing | `bristlenose/timing.py` (Welford) | per-stage estimate vs actual |
| Diagnostic popover | `ui_kinds.py` / `events.py` / `ProjectDiagnosticPopover.swift` | per-stage failure cause + glyph |
| SQLite | `<output>/.bristlenose/bristlenose.db` | all researcher state |
| Doctor | `bristlenose/doctor.py` | 7 runtime + 6 bundle checks |
| Build provenance | `_build.py` (SHA/`@time`/`-dirty`), `GeneratedBuildInfo.swift` | did my rebuild land? |
| Web Inspector | `webView.isInspectable` (DEBUG) | full WKWebView devtools |

## Prior art

- **In-repo:** the Ollama pill harness and the `…DIAGNOSTIC_FIXTURE` scenario
  injector — force-a-state + reveal-an-artifact. Follow it.
- **Mac apps** (Things, NetNewsWire, Ivory): DEBUG menus with "Reveal
  Application Support in Finder", "Copy Diagnostics", "Reset Onboarding",
  state-forcing toggles.
- **Web/server** (Django Debug Toolbar, Chrome `about:` pages, Rails
  `/rails/info`): one "everything about this run" page — versions, DB path,
  recent SQL, timings. `/api/dev/info` is the seed.

## Ranked additions

★ = high value, cheap (reveals data that already exists).

### Desktop `Debug` menu (`#if DEBUG`)
1. **✅ ★ Open Log** — open the served project's `bristlenose.log` in Console.app. *(shipped)*
2. **✅ ★ Reveal `.bristlenose/` in Finder** — one click to logs/events/llm-calls/db/last-failure. *(shipped)*
3. **✅ ★ Copy Build Provenance** — `GeneratedBuildInfo` SHA/`@time`/`-dirty`
   + active `SidecarMode` + live sidecar version + events-file `bristlenose_version`.
   Automates the recurring "is the bundled sidecar stale?" check. *(shipped)*
4. **✅ ★ Web Inspector** — `webView.isInspectable = true` (DEBUG) on the report
   WebView + the Run Inspector window → right-click → Inspect Element in-app. *(shipped)*
5. **Run Doctor…** — invoke `doctor` against the active sidecar, results in a sheet. *(not built)*
6. **✅ Diagnostic-fixtures submenu** — the `…DIAGNOSTIC_FIXTURE` scenarios as live
   menu buttons that inject into the selected project (no relaunch). *(shipped)*
7. **Sidecar controls** — Restart sidecar / Copy serve URL+port / show `SidecarMode`. *(not built)*
8. **Reset onboarding / consent** — re-show `AIConsentView` + first-run states
   (without touching the keychain). *(not built)*

### `serve --dev` (browser-side)
9. **★ `/api/dev/run` inspector page** — extend `/api/dev/info`: versions, DB
   path, last N pipeline-events, last N llm-calls (model/tokens/cost/latency),
   and the `llm_resolve` ledger. Turns three greps into one URL.
10. **LLM call-log viewer** — table over `llm-calls.jsonl`: cost/latency/retries,
    p50/p95, forecast-vs-actual. Data is captured; nothing reads it back.
11. **Timing breakdown** — per-stage Welford estimate vs actual.

### Out of scope
- "Performance breakpoints" (JS profiler) — Safari Web Inspector (#4) covers it.
- A second SQL inspector — `/admin/` SQLAdmin already exists; just link to it.

## Recommended first cut

**#1–#4 + #9.** All "reveal existing data," each small. #3/#9 directly attack the
stale-sidecar and provider-resolution debugging that the gotchas show eating
whole sessions.

**Env note:** the desktop (Swift) items can't be compiled or verified in the
Linux cloud env — they need a Mac. The `serve --dev` items (#9–#11) are
Python/HTML and testable here with pytest.

## Implementation (shipped — items #9–#11)

Built as a standalone, dev-only, server-rendered page. No React, no npm dep, no
CDN — buildable and testable without the frontend toolchain.

- **`bristlenose/server/run_inspector.py`** (NEW, stdlib-only) — pure readers +
  shapers + `build_run_inspector_html()`. Imports nothing from FastAPI /
  SQLAlchemy / the heavy pipeline, so it unit-tests in isolation. This is the
  testable seam; the endpoint is a thin wrapper.
- **`bristlenose/server/routes/dev.py`** (EDIT) — `GET /api/dev/run` (HTML) and
  `GET /api/dev/run.json` (raw payload), plus a "Run Inspector" link in
  `dev_info`. Dev-router only → 404 without `--dev`.
- **Tests:** `tests/test_run_inspector.py` (18 pure-function tests, run anywhere)
  + `tests/test_serve_dev_run.py` (endpoint tests, run in CI/Mac — need fastapi).

### Three tabs, all real-data-backed
- **Run overview** — gantt reconstructed from the `run_progress` `elapsed_seconds`
  stream; cost-by-stage donut + token bar + event stream from `llm-calls.jsonl`.
- **LLM calls** — latency×tokens scatter (retry rings), cache-hit donut, stacked
  per-stage cost bars, full calls table. All from `llm-calls.jsonl`.
- **Timing & forecast** — Welford μ±σ-vs-actual dumbbell (from `timing.json`) and
  a **forecast-calibration scatter** (predicted vs actual cost per call).

### Honesty decisions (from the review)
- **Dropped the mockup's "convergence over runs" curve** — `timing.json` stores
  only aggregate Welford `{mean,m2,n}`, not a per-run series, so it had no
  backing data. Replaced with the predicted-vs-actual cost calibration, which is
  genuinely recorded (`cost_usd_predicted` / `cost_usd_actual_estimate`).
- **XSS:** JSON injected into the `<script>` block is escaped `<`/`>`/`&` →
  `\uXXXX` (ensure_ascii handles non-ASCII + the U+2028/9 separators). NB —
  `ensure_ascii=True` alone does **not** escape `<`; **`routes/export.py:222`
  relies on exactly that and is a latent `</script>`-breakout vector** if any
  embedded project string contains `</script>`. Flagged, not fixed here.
- **Gantt is reconstructed, not stored** — `PipelineSummary` only carries 4
  coarse rollups; the per-stage timeline comes from the progress stream. Stages
  with no progress events degrade to an empty-state rather than faking bars.

## Implementation (shipped — desktop, 28 Jun 2026)

Brought up on a Mac after the cloud authored #9–#11. Corrections + the desktop
surfaces:

- **Event-schema fix** (`run_inspector.py`) — the lifecycle readers keyed off a
  non-existent `event_type` field and matched `kind` against event names; the
  canonical schema (`events.py`) is the `event` field (`run_started`/`…`) with
  `kind` = the level (`"run"`). On real data `run_id`/`status`/`duration` were all
  `—`. Now read via one `_event_type()` helper; fixtures rebuilt to the real
  schema + regression-pinned. (The XSS-escaping test was also brittle — rewritten
  to assert against a hostile `</script>` payload.)
- **Cost unavailable vs free** — `summarise_calls` returns `cost = None` when *no*
  call recorded a cost (renders "—" / "not recorded"), distinct from `0.0` (a
  genuinely free run, e.g. local Ollama → "$0.00"). Prevents the donut/stat
  reading "free" when cost simply wasn't captured.
- **Native Debug ▸ Run Inspector** (⌃⌘R) — `RunInspectorView.swift`, a DEBUG-only
  window hosting `/api/dev/run`. Auth: the page is bearer-protected and WKWebView
  drops a top-level `Authorization` header (and a cookie raced), so it fetches via
  `URLSession` (Bearer) and renders the self-contained HTML with `loadHTMLString`.
- **Dev API in the bundled sidecar** — `/api/dev/*` is `--dev`-gated, but the
  desktop runs a production serve. The DEBUG build sets `_BRISTLENOSE_DEV_ENDPOINTS=1`
  (`BristlenoseShared.childEnvironment`) to mount just the dev router (not SQLAdmin
  / Vite). Release never sets it.
- **#1/#2/#3/#4/#6** — reveal `.bristlenose/`, open log, copy provenance, web
  inspector, live diagnostic-fixtures submenu. Ollama pill scenes moved to a
  flyout submenu to declutter the top level.
- **Build-time sidecar-staleness gate** — the desktop runs the *bundled* sidecar,
  not live Python, so a Python change without a `build-sidecar.sh` rerun silently
  ships old code (this cost a multi-hour debugging session — the very symptom this
  whole branch exists to surface). `build-sidecar.sh` now stamps the bundle with a
  fingerprint of `bristlenose/**/*.py`; the Xcode "Copy Sidecar Resources" phase
  recomputes it (`check-sidecar-freshness.sh`) and **fails the build** on drift.
  Shared recipe in `sidecar-source-hash.sh` (writer + checker can't diverge);
  bypass with `BRISTLENOSE_ALLOW_STALE_SIDECAR=1`.

### Follow-ups
- #5 **Run Doctor…**, #7 **Sidecar controls**, #8 **Reset onboarding/consent** — not built.
- A timing-history store would re-enable the convergence curve honestly.
- The native window needs a `build-sidecar.sh` rerun to reflect Python changes
  (the staleness gate now enforces this rather than letting it pass silently).
