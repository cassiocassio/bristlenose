# Static render disposition + bundle-completeness CI mechanisms

## Context

Two threads surfaced at the tail of the C3 smoke test:

1. **Static render framing.** The post-mortem called the static render a "fallback" that the serve mode "falls open" to when the React SPA is missing. User pushed back: *"it's not a fallback if we don't want any user to see it."* Is the static render a structural part of the product, or dead weight? Should serve mode **ever** serve it?

2. **BUG-6b — the CI gap.** The source→spec gate (`check-bundle-manifest.sh`) landed last night. That catches "dir in source, forgot to add to spec" — the BUG-3/4/5 class. The complement — "spec entry present, but PyInstaller silently dropped files" — is still uncovered. User asks: *"explore range of mechanisms for ensuring, during CI? part of build? when? how?"*

Neither is a coding task yet. This plan is the map of options and a recommended sequence.

---

## Part A — What role does the static render actually have?

### Evidence from the code (not CLAUDE.md assertions)

**Load-bearing callers of `bristlenose/stages/s12_render/`:**

| Caller | Entry point | Role |
|---|---|---|
| `bristlenose run` (full pipeline) | `pipeline.py:413, 1284` — Stage 12 | Writes `bristlenose-<slug>-report.html` to the output dir |
| `bristlenose run --analysis-only` | `pipeline.py:1495` | Same, minus transcription |
| `bristlenose render` (standalone CLI) | `cli.py:1115-1320` | Re-render from cached JSON after CSS/data edits |

**NOT callers:**
- Export endpoint (`routes/export.py:183-327`) — generates self-contained HTML by embedding the **React bundle** + JSON, no Jinja2 call
- Serve-mode dev CSS (`_serve_live_theme_css` in `app.py:381`) — only `_load_default_css()`, no renderer

### Reframed (correction from user, 21 Apr 2026): the static render isn't first-class — it's history

**Initial draft was wrong.** This plan first claimed the static render was a "first-class offline product for CLI users" because three CLI commands still call it. User pushed back: the static render isn't a product, it's scaffolding from the React-migration era that nobody removed yet.

**The legitimate offline-share path is via serve mode + Export HTML:**

CLI users start `bristlenose serve` → browse the React SPA in their browser → click **Export HTML** in the toolbar → get a self-contained file with all the modern features. The Export endpoint embeds the React bundle + JSON; doesn't touch `s12_render/` at all. That's the share-with-clients-without-Bristlenose path the product team intends to ship.

**What `s12_render/` is, then:**

- Stage 12 of `bristlenose run` writes a frozen-design HTML report to disk — leftover scaffolding, not pixel- or feature-identical to the React SPA, no longer the canonical artefact
- `bristlenose render` (standalone CLI) regenerates that frozen-design HTML — same status
- Both still work but neither is the product offering. Deletable once we audit whether any external workflow depends on them.

### The "fallback" in serve mode is the real bug

`bristlenose/server/app.py:420` — `_mount_prod_report()` originally fell back to serving the static-rendered HTML when the React bundle was missing. **This is wrong behaviour.** When the React SPA is missing:
- Data APIs don't work (no `/api/*` calls fire from the static render)
- Video player breaks (no React `PlayerContext`, falls into "Cannot play this format")
- Inline editing, search, sidebar, autocode UI — all absent
- User sees a frozen snapshot and doesn't know why it looks wrong

The static render isn't a real product anywhere, so letting serve mode silently serve it is straight-up incorrect — there's no legitimate "fallback" use to conflate this with.

### Recommendation for Part A

**Keep `s12_render/` for now (separate cleanup). Fix serve mode to fail loud instead of serving static HTML.**

- In `_mount_prod_report`, when `_STATIC_DIR / "index.html"` is missing:
  - In `--dev` mode: log a loud warning and let the user know to run `npm run build`
  - In production (bundled sidecar) mode: return a 500 with an error page ("Build incomplete"). Do NOT mount the output dir as static files.
- Export endpoint stays as-is (already correct — uses React bundle, not static renderer).
- `bristlenose render` CLI stays as-is **for now**, but file as a deletion candidate. Same for stage 12's static HTML output.
- Update CLAUDE.md's framing: not "first-class CLI product"; instead, **"vestigial scaffolding from the React-migration era; the React SPA + Export HTML is the actual share-with-clients product; `s12_render/` and `bristlenose render` are on the eventual-deletion path."**

This is small — ~20 lines in `app.py`, plus the CLAUDE.md wording pass.

---

## Part B — CI mechanisms for ensuring bundle completeness

### What exists today

| Layer | Where | What it covers |
|---|---|---|
| `.pre-commit-config.yaml` | client-side via `pre-commit install` | Only gitleaks (secret scanning) |
| `desktop/scripts/check-logging-hygiene.sh` | `build-all.sh` step 1a | Swift logger calls leaking credentials |
| `desktop/scripts/check-bundle-manifest.sh` | `build-all.sh` step 1b (just landed) | **source→spec** datas coverage |
| `desktop/scripts/check-release-binary.sh` | `build-all.sh` post-export | Dev env-var literals + `get-task-allow` in Mach-Os |
| `.github/workflows/ci.yml` | GitHub Actions | pytest + ruff, on ubuntu + macos-latest (macOS is `continue-on-error: true`) |
| `.github/workflows/install-test.yml` | GitHub Actions | Post-install smoke (pip install + import) |
| `pytest` | unit tests | Source-level; doesn't see the bundle |

### Range of mechanisms on offer

Options ordered by **how early they catch** and **who pays the cost**:

#### 1. IDE / editor-time
**Mechanism:** VS Code / Xcode linters that flag something as you type.
**Catches:** typos, obvious syntax, lint issues.
**Cannot catch:** bundle-completeness (needs either spec parsing or a build).
**Cost:** contributor-installs, easy to bypass.
**Verdict:** not useful for BUG-6b.

#### 2. Pre-commit hook (client-side)
**Mechanism:** extend `.pre-commit-config.yaml` to run `check-bundle-manifest.sh` before commits that touch `bristlenose/` or the spec.
**Catches:** source→spec gap at commit time.
**Cannot catch:** spec→bundle drops (requires a build).
**Cost:** 60ms per commit for contributors who have `pre-commit install`'d. Silently skipped by contributors who haven't.
**Verdict:** nice-to-have for defence-in-depth; not load-bearing because it's skippable.

#### 3. Pre-push hook (client-side)
**Mechanism:** same script, fires on `git push`.
**Catches:** same as pre-commit.
**Verdict:** duplicates pre-commit without adding value.

#### 4. Local build-all.sh pre-flight
**Mechanism:** `check-bundle-manifest.sh` as step 1b (**LANDED**). Fast-fail before the 3-min PyInstaller build.
**Catches:** source→spec gap, always (can't skip).
**Verdict:** ✅ solved for BUG-6a. Keeps delivering value on every local build.

#### 5. Local build-all.sh post-bundle (the BUG-6b slot)
**Mechanism:** after `build-sidecar.sh`, before `archive`, run a **spec→bundle** verification.
**Two sub-options:**
- **5a — HTTP endpoint probe** (what the plan originally called D3): spawn bundled sidecar, hit endpoints, assert no 5xx. Needs: 127.0.0.1 pinning, `trap` cleanup, random token, hard timeout, TCP-poll readiness. ~30s cost.
- **5b — `bristlenose doctor --self-test` mode** (new idea): extend the existing `bristlenose doctor` command so that when invoked with `--self-test` (or `--bundle-integrity`) it does an in-process check: imports every expected module, stat()s every expected runtime data file (codebook YAMLs, prompt MDs, theme CSS, React SPA index.html), reads them to verify they're non-empty, exits 0 if all good, non-zero with a diagnostic list. No HTTP, no subprocesses, no port handling. ~2s cost.
**Preferred sub-option:** **5b**. Simpler, faster, fewer moving parts, no network, and `doctor` already exists as a CLI command with an established place in the codebase (`bristlenose/doctor.py`). We'd extend an existing feature rather than invent a new test harness.
**Verdict:** this is the right gate for BUG-6b. Lands in `build-all.sh` as step 7a (after `build-sidecar.sh`, before `archive`).

#### 6. CI on every PR (GitHub Actions)
**Mechanism:** a GitHub Actions job that runs on `pull_request` affecting `bristlenose/`, `desktop/`, or `frontend/`. Could include `check-bundle-manifest.sh` and/or a full `build-sidecar.sh` + doctor self-test.
**Catches:** regressions landed via PRs.
**Cost:**
- Just the manifest check: free (<1s on any runner)
- Full sidecar build: requires macOS runner (Ubuntu PyInstaller produces a Linux binary, useless for us); GitHub macOS runners are **6× cost multiplier**, ~5 min per run. At ~20 PRs/week with desktop changes, that's ~10 CI-hours/week of macOS time, ~$50-80/month on GitHub's paid tier.
**Verdict:** **manifest check on every PR is a no-brainer** (free, fast, catches source→spec class). Full sidecar build per PR is expensive; see 7.

#### 7. CI on push to main (or release-candidate branches)
**Mechanism:** macOS runner builds the sidecar bundle, runs self-test. Fires less often than per-PR, catches pre-release regressions.
**Catches:** spec→bundle drops before a tag is cut.
**Cost:** one macOS build per push to main. Bristlenose's cadence is low (~5 commits to main/week), so ~5 macOS-CI-minutes/week. Cheap.
**Verdict:** **right spot for the full sidecar-build gate**. Doesn't slow PRs; does catch "main is shippable" regressions.

#### 8. CI as pre-release gate (on tag push)
**Mechanism:** existing `.github/workflows/release.yml` extended to run `build-all.sh` end-to-end (including signing + notarisation against the Apple Distribution cert).
**Catches:** anything the local build-all.sh would catch, but reproducibly from a clean checkout.
**Cost:** full notarisation queue (~5-15 min Apple-side) per release.
**Verdict:** **the load-bearing gate for actual shipping**. Non-negotiable for alpha onwards. Already exists for the pip/Homebrew/Snap releases; needs extending to cover the Mac sidecar.

#### 9. Canary / scheduled builds
**Mechanism:** weekly or nightly GitHub Actions that spin up a fresh macOS runner, clone main, do a full build-all.sh, report.
**Catches:** environmental drift — things that were fine on Martin's Mac but broke on a vanilla environment (wrong brew versions, missing env vars, etc.).
**Cost:** ~5 macOS-CI-minutes/week.
**Verdict:** low-effort insurance. Worth having once alpha ships. Skip until then.

#### 10. Release-gate only (no CI, just humans)
**Mechanism:** "Martin runs `build-all.sh` locally before every release, trusts the outcome."
**Cost:** zero CI.
**Risk:** single point of failure (Martin's machine), brittle to env drift, no audit trail.
**Verdict:** **this is the current state.** The three bugs we just hit came from exactly this mode. Worth improving.

### The question the user actually asked — "during CI? part of build? when? how?"

**During CI (GitHub Actions):**
- **Per-PR:** `check-bundle-manifest.sh` + pytest + ruff (free, fast)
- **On push to main:** `build-sidecar.sh` + `doctor --self-test` (~5 min macOS runner)
- **On tag push:** full `build-all.sh` including sign+notarise (~15-20 min)
- **Weekly canary:** full build-all.sh from clean checkout (~15 min, catches env drift)

**Part of build (local `build-all.sh`):**
- Pre-flight: `check-logging-hygiene.sh`, `check-bundle-manifest.sh` (**done**)
- Post-build, pre-archive: new `doctor --self-test` step against the bundle (**the BUG-6b slot**)
- Post-archive: `check-release-binary.sh` (done)

**When:**
- Cheap/fast checks → everywhere (pre-commit, pre-flight, PR)
- Expensive/slow checks → at the right gate (push to main, tag push)
- Don't duplicate: if the pre-flight catches it, the PR CI catches it, and the push-to-main CI catches it, that's three runs for the same class — ok as long as they're cheap

**How:**
- `doctor --self-test` (the runtime checker) lives inside `bristlenose/doctor.py` as a new subcommand, reused by both local `build-all.sh` and by GitHub Actions. **One implementation, three invocation sites.**
- GitHub Actions jobs read the exit code; non-zero fails the run; output is attached as a job artefact for triage.

---

## Recommended sequence

### Track P1 — Fix Part A first (~30 min)

1. Patch `bristlenose/server/app.py:_mount_prod_report` — in production mode, return a 500 with a clear error page instead of mounting the static output dir as a fallback.
2. Update `bristlenose/server/CLAUDE.md` and `CLAUDE.md` root: static render is vestigial scaffolding (not first-class), absent from serve mode, on the eventual-deletion path. Real share-with-clients product is the Export HTML feature in serve mode (which doesn't touch `s12_render/`).
3. Verify `bristlenose render` CLI still works (it's the only consumer of `s12_render/` that matters on the CLI path).

### Track P2 — Add `doctor --self-test` (~2 hr)

1. Extend `bristlenose/doctor.py` (or add a sibling module) with a `self_test()` function that:
   - stat()s every expected runtime data file with a size floor (e.g. every codebook YAML is ≥100 bytes, every prompt MD is ≥500 bytes, React `index.html` exists and is ≥1KB)
   - imports every stage module to surface module-resolution errors
   - reads `theme/` CSS files to verify they're parseable
   - returns a structured result (list of checks, each pass/fail with diagnostic)
2. Add a CLI flag: `bristlenose doctor --self-test` (or `--bundle-integrity` — name TBD).
3. Wire into `desktop/scripts/build-all.sh` as step 7a (between `build-sidecar.sh` and `archive`).

### Track P3 — Extend GitHub Actions (~1 hr)

1. `ci.yml` — add `check-bundle-manifest.sh` to the PR pre-flight (no build cost, matrix-skip not needed).
2. New workflow `desktop-build.yml` — triggered on push to main, runs `build-sidecar.sh` + `bristlenose doctor --self-test` on macos-latest. No signing, no notarising.
3. `release.yml` — extend to run full `build-all.sh` on tag push once the Mac alpha is a shippable artefact (post-SECURITY #5/#8).

### Track P4 — Canary (post-alpha, ~30 min)

Weekly scheduled workflow, full build-all.sh on macos-latest from a clean checkout.

---

## Decision points for the user

Three things to decide before any code change:

1. **Part A fix shape:** 500 error page vs. no-route-mounted (404 from FastAPI) vs. something else?
2. **Part B mechanism:** `doctor --self-test` (5b, preferred) vs. HTTP endpoint probe (5a) vs. both?
3. **CI ambition:** conservative (just extend pre-flight + push-to-main) vs. aggressive (all four tracks)?

## Critical files to read before implementing

- `bristlenose/server/app.py:420-437` — the `_mount_prod_report` fallback that needs fixing
- `bristlenose/doctor.py` — existing doctor command shape (reuse this)
- `bristlenose/cli.py:1115-1320` — `bristlenose render` entry, to verify Part A doesn't break it
- `bristlenose/stages/s12_render/__init__.py` — the warning at line 108, stays
- `.github/workflows/ci.yml` — existing matrix, to understand where the manifest check slots in
- `desktop/scripts/build-all.sh` — where `doctor --self-test` wires in post-build
- `desktop/scripts/check-bundle-manifest.sh` — the precedent for the new gate

## Part D — Thought experiment: deleting the static renderer wholesale

User asked: "during the React migration when we had the islands strategy it was essential, right? but now?"

**Then (islands era):** essential. Jinja2 rendered the data; React islands progressively enhanced on top. Without the Jinja base, React had nothing to mount into.

**Now (SPA era):** not essential for serve mode. Per `bristlenose/server/CLAUDE.md`, serve mode reads the Vite-built `bristlenose/server/static/index.html` (React bundle's own HTML shell), not the static-rendered HTML. The islands→SPA migration concluded; the Jinja base became scaffolding that's no longer load-bearing for serve mode.

### What actually breaks if we delete `s12_render/` wholesale

Auditing imports + invocation sites (21 Apr 2026):

**Direct invocation sites — would lose functionality:**
- `bristlenose run` stage 12 — no more on-disk HTML report
- `bristlenose render` CLI command (`cli.py:1115-1320`)
- `bristlenose run --analysis-only` — same as `run`

**Hidden coupling — serve mode imports utilities from `s12_render`:**
- `bristlenose/server/app.py:381` imports `_load_default_css` from `s12_render.theme_assets` for live-CSS dev mode
- `bristlenose/server/routes/sessions.py`, `routes/dashboard.py`, `routes/dev.py` — all import from `s12_render`. Likely sentiment-colour helpers, quote formatters, dashboard data-shapers
- `bristlenose/status.py` also imports from `s12_render`

So serve mode depends on **data-extraction utilities** that live in `s12_render`. They're not render code; they're data-shape helpers that ended up in the wrong namespace because `s12_render` was where data prep happened during the islands era.

**Per-session transcript HTML pages** (`render_transcript_pages` in `s12_render/transcript_pages.py`):
- Produced by stage 12 to disk
- Possibly served by serve mode at `/report/sessions/<id>/...html` deep-link URLs
- The React `TranscriptTab` exists per memory notes — but does it fully replace the file-on-disk pages including deep links? Needs verification.

**Tests** — 7 files reference `s12_render` directly: `test_dark_mode`, `test_navigation`, `test_analysis_integration`, `test_search_filter`, `test_doctor`, `test_hidden_quotes`, `test_status`. They'd need porting.

### Phased deletion sequence

| Phase | Cost | Action |
|---|---|---|
| 1 | ~30 min | Stop `bristlenose run` calling `render_html()`. No more on-disk HTML. Audit CI/Snap/Homebrew for dependence on the file existing. |
| 2 | ~30 min | Remove `bristlenose render` CLI command. |
| 3 | ~1-2 hr | Audit React `TranscriptTab` parity with `render_transcript_pages`. If React covers it (incl. deep links), drop transcript-page generation. If not, add to React first. |
| 4 | ~2-3 hr | Move `theme_assets._load_default_css`, `sentiment.*`, `quote_format.*`, `dashboard.*` (data-shape parts) out of `s12_render/` into serve-owned location (e.g. `bristlenose/server/utilities/`). Update import sites. |
| 5 | ~30 min | Delete `s12_render/__init__.py`'s `render_html` + `render_transcript_pages` exports. |
| 6 | ~30 min | Delete `bristlenose/theme/templates/`. |
| 7 | ~30 min | Delete `bristlenose/theme/js/`. |
| 8 | ~3-4 hr | Port the 7 affected test files. |

**Total: ~10-13 hours focused work.** Worth doing before alpha (smaller bundle + surface area), but not a one-line cleanup. Filed as a structured cleanup in qa-backlog.

### Smaller pre-alpha cleanups that are quick wins

- Delete `bristlenose/theme/js/` once the deprecated render is gone (frees ~100KB + removes the entire vanilla-JS test surface; CLAUDE.md already marks it frozen)
- The `_strip_vanilla_js()` function in serve `app.py` becomes dead code
- The `_ensure_index_symlink` helper becomes dead code
- The `<!-- bn-app -->` marker substitution may become dead code (verify React-only path doesn't use it)

These all collapse alongside Phase 5-7 above.

## Out of scope

- Deleting `bristlenose/stages/s12_render/` (it's load-bearing for CLI)
- Adding automated post-notarisation smoke (that's Track B's TestFlight concern)
- Rewriting the export endpoint (already correct — uses React bundle)
- Branch-protection rules on GitHub (separate admin task)

## Appendix — Why does this class of bug exist at all?

Extended explainer for the "this failure mode is generic to every PyInstaller-bundled Python app" claim, assuming less Python-packaging knowledge.

### The two ways your app exists at different moments

Bristlenose is a Python program. But "a Python program" has at least two very different shapes depending on where it's running:

**Shape 1 — a bag of files on disk (development / CLI install)**

When you're developing, or when a user runs `pip install bristlenose`, the program is a directory tree. `bristlenose/server/codebook/garrett.yaml` is just a file sitting on disk at a path you can `ls`. When the Python code says "open the YAML next to me," Python uses `__file__` (a magic variable meaning "where this .py file lives on disk") + relative paths to find it. Works because the file really does exist on disk at a predictable place.

The `pip install -e .` (the `-e` is "editable") is the developer variant: instead of copying Bristlenose files into Python's libraries, it just points Python at the working tree. Edits to `bristlenose/llm/prompts/autocode.md` are live the next time Python reads them — no reinstall. Every data file is on disk, reachable by path, exactly as it appears in the source tree.

**Shape 2 — a single executable (PyInstaller bundle / desktop app)**

When you build the Mac app, PyInstaller takes the whole Python program — the interpreter, the standard library, every dependency (numpy, torch, FastAPI, etc.), plus Bristlenose's own code — and packages it into a self-contained binary. The end user double-clicks a `.app`, Python code runs, but now "running" means something very different:

- The `.py` source files have been compiled to bytecode (`.pyc`).
- Those bytecode files are packed into archives (`base_library.zip`, per-package collections).
- At runtime, Python fishes each module out of the archive, decompresses it, executes it. The files aren't on disk at predictable paths — they're *inside* another file.

So far so good — Python handles this transparently for code. `import numpy` works the same way whether numpy lives as disk files or inside a PyInstaller archive. You don't notice.

### The gap: non-code files

Here's where it breaks. Python handles *code* (`.py` → `.pyc` → archive → runtime import) automatically. But `.yaml`, `.md`, `.json`, `.css`, `.html`, `.png` — **PyInstaller has no idea those files are part of your program unless you tell it.**

The bytecode-compilation step only looks at `.py` files. If your code says `Path(__file__).parent / "autocode.md"` — "look for autocode.md next to me" — that works on disk. In the bundle, there's nothing next to `prompts/__init__.py` because:

- `__init__.py` got compiled to bytecode and packed into an archive
- `autocode.md` is just sitting there, ignored, because PyInstaller didn't know it was yours
- At runtime `Path(__file__).parent / "autocode.md"` points to somewhere inside the archive — no file there
- `Path(...).read_text()` raises `FileNotFoundError`
- Your program crashes

The mechanism you're supposed to use is the `datas` list in the PyInstaller spec file. Each entry says: "also copy this source directory into this location inside the bundle." PyInstaller then includes the YAMLs/MDs/etc. alongside the bundled bytecode so that `Path(__file__).parent / "autocode.md"` resolves correctly at runtime.

**If you forget a `datas` entry:**
- Your source tree still has the file. Dev works.
- Unit tests still have the file (they run against source). Tests pass.
- `pip install bristlenose` still has the file (copied into Python's libraries directory). CLI users are fine.
- The PyInstaller bundle **silently** doesn't have the file. Your desktop app users crash on first use.

### Why unit tests never catch it

Unit tests run against **Shape 1** (the bag of files on disk). They exercise the Python code by importing it from the source tree. `Path(__file__).parent / "autocode.md"` works in tests because the file is at the expected path.

To catch the bug, a test would have to run against **Shape 2** (the bundle). That means:
- Build the bundle (3-5 minutes on macOS)
- Spawn the built binary
- Exercise the same codepaths the test covers
- Check for `FileNotFoundError` at runtime

This is a different kind of test — an integration/smoke test, not a unit test. It's slower, needs a build step, and has a bigger dependency surface. Most Python projects don't have one because:

- PyInstaller apps are a minority of Python projects (most Python ships as pip packages or Docker images, not frozen binaries)
- Integration-testing a frozen binary requires CI runners of the same OS as the target (macOS bundle → needs a macOS runner → expensive on GitHub Actions at 6× cost multiplier)
- The failure mode is invisible until someone actually *runs* the binary, which in development happens rarely because `pip install -e .` is faster for iteration

So the gap opens: your source-level tests all pass, your CLI distribution works, your dev loop is fine, and the bundle quietly ships missing files.

### Why it's generic, not just us

Every PyInstaller-bundled Python app with runtime data files hits this sooner or later. The pattern shows up in:

- **ML apps** that need model weights, tokenizer configs, prompt templates
- **CLI/desktop apps** with i18n strings, themed assets, CSS, bundled fonts
- **Scientific apps** with default parameters, reference datasets, SQL schema files
- **Anything with plugins** (plugin discovery by `__file__`-relative globbing)

The Python packaging ecosystem has **three** different, non-overlapping ways to declare non-code files:

1. **`pyproject.toml` / `setup.py` `package_data`** — for pip-installable packages
2. **PyInstaller `datas`** — for frozen bundles
3. **`MANIFEST.in`** — for source distributions (sdist)

A correctly-shipped Python app with runtime data files has to maintain all three in lockstep. They don't cross-check each other. Adding a new YAML means adding a new line to three separate files. If you forget PyInstaller's `datas`, your bundle breaks and no other layer tells you.

**PEP 503 / PEP 621 / PEP 639** have steadily improved the pip side (modern `pyproject.toml` can do most of what `setup.py` + `MANIFEST.in` used to). PyInstaller is a separate tool with its own manifest. There is **no** standardised "Python runtime data manifest" that both pip and PyInstaller consume — that's the documented gap.

### The fix pattern (what we did)

Rather than maintaining three manifests by hand:

1. **Source→spec gate** (`check-bundle-manifest.sh`, just landed): walks the source tree, reads the PyInstaller spec, fails if any runtime-data dir isn't in `datas`. Catches forgotten additions at build time.

2. **Spec→bundle gate** (`doctor --self-test`, Track P2 above): runs against the built bundle, verifies every expected file is reachable at runtime. Catches PyInstaller's silent drops (the other direction).

Together they close the loop. Other PyInstaller-app maintainers solve the same problem with variations on the same theme — some use a handwritten integration script, some use pytest fixtures that spawn the bundled binary, some use Docker/VM-based test harnesses. The specific mechanism varies; the need is universal.

### The broader lesson

*"Dev works, tests pass, bundle is broken"* is the canonical signature. Any time a Python program has files that aren't `.py` and are loaded at runtime by path, there's a packaging risk surface. The more loudly the app fails-closed when a file is missing (the CLAUDE.md way — visible `FileNotFoundError`, not silent fallback), the easier this class of bug is to diagnose when it does slip through.

Bristlenose's fail-closed architecture (caught in the post-mortem) is what let us surface BUG-3/4/5 during a smoke test rather than weeks later in the field. The architecture choice bought time; the CI gates make the time-bought sustainable.

## Verification

- **Part A:** after the serve-mode fix, remove `bristlenose/server/static/index.html` and confirm `bristlenose serve` returns a clear 500 with an error page (not the static-render HTML). Restore; confirm normal operation. Run `bristlenose render` against a cached project to confirm the CLI path still works.
- **Part B (doctor):** run `bristlenose doctor --self-test` on a working bundle — all pass. Delete one bundled prompt file, run again — fail with a clear diagnostic naming the missing file.
- **Part C (CI):** open a PR that adds a stray YAML to an uncovered source dir — PR CI fails on the manifest check. Open a PR that removes a datas entry — push-to-main CI would fail (simulate with a local run).
