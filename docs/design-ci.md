# CI architecture

## Goals

CI exists to catch regressions before they reach users. It answers one question per push: "did this change break anything we already had working?"

CI is not a quality gate for perfection. Steps that enforce correctness (ruff, pytest, tsc, man page version) block the build. Steps that surface information (mypy, pip-audit, npm audit, ESLint) run but don't block — they show regressions in the log without preventing a merge. The distinction matters: blocking steps must be fixable by the author; informational steps often flag issues in third-party dependencies that can't be resolved immediately.

## Philosophy

**Fail fast.** Static checks (lint, types, man page) run in a single `lint` job before any test matrix work begins. If ruff finds an error, 8 test jobs are skipped instantly instead of each burning 3 minutes to discover the same failure.

**Canonical cell.** One combination — ubuntu-latest + Python 3.12 — is the "real" CI. It produces the coverage report, runs the dependency audit, generates the SBOM. Other matrix cells exist to catch compatibility issues, not to duplicate bookkeeping.

**macOS as signal, not gate.** macOS runners cost 10× Linux and surface platform-specific issues that rarely block a pure-Python change. All macOS jobs run with `continue-on-error: true` — a failure shows as a yellow warning, not a red block. Investigate when yellow, but don't hold a merge for it.

**`fail-fast: false` on the test matrix.** A Python 3.10 failure doesn't predict a 3.13 failure. Let all cells finish so you see the full picture in one push, not across three retry cycles.

**Tests, not tools, define correctness.** Ruff enforces style. Pytest enforces behaviour. TypeScript enforces types. Playwright enforces integration. If a check isn't in one of these categories, it's informational.

## Job structure

```
lint ──────────────┐
                   ├──► e2e
test (8 cells) ────┘
                   │
frontend ──────────┘

desktop-build ─────────  (independent, planned S2)
```

Four jobs today, one planned:

| Job | Runs on | Depends on | Blocking? |
|-----|---------|------------|-----------|
| `lint` | ubuntu, Python 3.12 | — | Yes |
| `test` | 4 Python × 2 OS (8 cells) | `lint` | Ubuntu yes, macOS informational |
| `frontend-lint-type-test` | ubuntu, Node 20 | — | Yes |
| `e2e` | ubuntu, Python 3.12 + Node 20 | `test` + `frontend` | Yes |
| `desktop-build` *(planned)* | macOS | — | Informational initially |

`lint` and `frontend` run in parallel (no dependency between them). `test` waits for `lint`. `e2e` waits for both `test` and `frontend`. `desktop-build` is independent — Swift compilation doesn't depend on Python or Node.

## What each job does

### lint

Runs once on ubuntu/3.12. Catches universal problems before the matrix runs.

| Step | Blocking? | Why |
|------|-----------|-----|
| ruff check | Yes | Style and import errors |
| mypy | No | 9 pre-existing third-party SDK errors; shows regressions |
| Man page version check | Yes | `man/bristlenose.1` must match `__version__` |
| pip-audit | No | Transitive dep CVEs often unfixable; review each run |
| SBOM generation + upload | No | Compliance artifact (US EO 14028, EU CRA) |

### test

8 matrix cells: Python 3.10, 3.11, 3.12, 3.13 × ubuntu-latest, macos-latest.

Each cell installs `.[dev,serve]` and runs `pytest --tb=short -q -m "not slow"`. Coverage is collected on all cells but only uploaded from ubuntu/3.12 (the canonical cell).

pip cache is enabled (`cache: pip` on `setup-python`) to avoid re-downloading wheels across runs.

### frontend-lint-type-test

Single ubuntu job with Node 20. Runs the full frontend quality chain:

| Step | Blocking? | Why |
|------|-----------|-----|
| ESLint | No | 84 pre-existing problems; fix incrementally |
| TypeScript typecheck | Yes | Type errors are bugs |
| npm audit | No | Production deps will become blocking; full audit stays informational |
| SBOM generation + upload | No | Compliance artifact |
| Vitest | Yes | ~1265 unit/integration tests |
| Vite build | Yes | Build errors are shipping errors |
| size-limit | Yes | Bundle size gate (305 KB gzip) |

### e2e

Playwright end-to-end tests. Starts a real FastAPI server with a built frontend, runs Chromium + WebKit against it. Currently layers 1–3 (console errors, broken links, network failures). Layers 4–5 (DB mutations, visual regression) planned for S4.

Uploads Playwright HTML report as artifact on failure (7-day retention).

## Matrix strategy

**Why 3.10–3.13?** `pyproject.toml` declares `requires-python = ">=3.10"`. Testing the floor (3.10) and ceiling (3.13) catches compatibility boundaries. The middle versions (3.11, 3.12) catch deprecation-cycle issues where a feature is warned in N and removed in N+1.

**Why macOS is `continue-on-error`?** The desktop app builds separately (Xcode). The Python package ships via PyPI/Homebrew/Snap, all Linux-built. macOS CI catches platform-specific test failures (path handling, FFmpeg behaviour, signal handling) but these rarely block a pure-Python change.

**Why `fail-fast: false`?** Version compatibility failures are independent — a 3.10 issue (removed API) and a 3.13 issue (new deprecation) are unrelated. Running all cells to completion gives the full picture.

## Artifacts

| Artifact | Produced by | Retention | Purpose |
|----------|-------------|-----------|---------|
| `coverage-report` | test (ubuntu/3.12) | 90 days | Line coverage XML |
| `sbom-python` | lint | 90 days | CycloneDX dependency inventory |
| `sbom-frontend` | frontend | 90 days | CycloneDX dependency inventory |
| `playwright-report` | e2e (on failure) | 7 days | HTML test report for debugging |

## Informational steps

These run with `continue-on-error: true`. They appear as yellow warnings, not red failures.

| Step | Job | Why informational |
|------|-----|-------------------|
| mypy | lint | 9 pre-existing third-party SDK type errors (anthropic, presidio, faster-whisper) that can't be fixed upstream |
| pip-audit | lint | Transitive deps (torch, protobuf) frequently have unfixed advisories |
| npm audit | frontend | Dev dep CVEs (Vite ecosystem) rarely actionable |
| ESLint | frontend | 84 pre-existing problems from missing jsx-a11y plugin and strict react-hooks rules |
| SBOM generation | lint, frontend | Compliance artifact; generation tool failures shouldn't block |
| macOS test cells | test | Platform signal, not a gate (see Philosophy) |

**Promotion path:** when pre-existing errors are resolved, promote to blocking by removing `continue-on-error: true`. Target: mypy and ESLint first, pip-audit and npm audit when transitive dep noise is manageable.

## Release workflow

`release.yml` triggers on version tags (`v*`). It:

1. Calls `ci.yml` via `workflow_call` — the full lint → test → frontend → e2e pipeline must pass
2. Builds the React frontend (`npm run build`)
3. Builds Python sdist + wheel
4. Publishes to PyPI via OIDC (trusted publisher, no stored token)
5. Creates a GitHub Release with auto-generated notes
6. Dispatches a `repository_dispatch` to the Homebrew tap repo to update the formula

The release workflow never runs independently — it always gates on the full CI suite first.

## Other workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `codeql.yml` | Push/PR to main + weekly Monday | CodeQL security scanning (Python + JavaScript). Security-extended queries. LLM prompt injection detection requires manual review |
| `i18n-check.yml` | Locale file changes | Validates locale JSON files via `scripts/check-locales.py` (key parity, syntax) |
| `snap.yml` | Push to main + version tags | Builds Snap package. Edge channel on main pushes, stable channel on tags. Skips gracefully if credentials unavailable |
| `install-test.yml` | Weekly + on-demand + install doc changes | Tests documented install paths (pip, pipx, Homebrew) across platforms. Optional full pipeline run with real API key on weekly schedule |

## Coverage gaps

Audit of what the project uses vs what CI actually tests (Apr 2026).

### What's covered well

| Area | CI coverage |
|------|------------|
| Python (Linux) | 4 versions (3.10–3.13), blocking, coverage, SBOM |
| React/TypeScript frontend | ESLint, tsc, Vitest, build, bundle size gate |
| E2E integration | Playwright layers 1–3, Chromium + WebKit |
| Dependency security | pip-audit, npm audit, CodeQL (informational) |
| Locale parity | `i18n-check.yml` validates key coverage across 6 locales |
| Install methods (Linux) | pip, pipx smoke tests on push |

### Known gaps

| Gap | Severity | Decision |
|-----|----------|----------|
| **Swift desktop app — no CI at all** | High | Fix: add `desktop-build` job (see plan below). The product going to the App Store has zero build verification |
| **Windows — 3 code paths, never tested** | Low | Accept. Windows is Won't for 100-day scope. Code paths are defensive (`platform.system()` checks in ingest, Ollama, clips). No Windows runner until there's a Windows release plan |
| **macOS Python tests — informational** | Medium | Accept. macOS failures show as yellow warnings. Promoting to blocking would gate every push on the 10× cost runners for a pure-Python package that ships via Linux-built PyPI/Homebrew/Snap. Revisit when desktop app integration tests exist |
| **Node version mismatch (CI: 20, docs: 24)** | Medium | Fix when Node 24 LTS lands in GitHub Actions runner images. Current code works on both; the constraint is ESLint 10 which was added after the CI was set up |
| **Snap arm64 — declared, never built** | Low | Accept. No arm64 Snap users. `snapcraft.yaml` declares it for future use |
| **Homebrew install — weekly only** | Low | Accept. Formula changes are rare and triggered by releases. Weekly cadence is sufficient |
| **Firefox — not in Playwright browsers** | Low | Accept. WebKit (Safari engine) + Chromium covers the two browser engines users actually encounter. Firefox shares no engine with either |

### Desktop build job — implementation plan

**Goal:** catch Swift compilation errors, missing imports, and deployment target issues on every push. Does not run the app or test it — just verifies it builds.

**Job definition** (add to `ci.yml`):

```yaml
desktop-build:
  runs-on: macos-latest
  # Informational initially — promote to blocking once stable
  continue-on-error: true

  steps:
    - uses: actions/checkout@v4

    - name: Select Xcode
      run: sudo xcode-select -s /Applications/Xcode.app

    - name: Build desktop app
      run: |
        xcodebuild build \
          -project desktop/Bristlenose/Bristlenose.xcodeproj \
          -scheme Bristlenose \
          -configuration Debug \
          -destination "platform=macOS" \
          CODE_SIGNING_ALLOWED=NO \
          | xcpretty || true

    - name: Run Swift tests
      run: |
        xcodebuild test \
          -project desktop/Bristlenose/Bristlenose.xcodeproj \
          -scheme Bristlenose \
          -destination "platform=macOS" \
          CODE_SIGNING_ALLOWED=NO \
          | xcpretty || true
```

**Key decisions:**

- **`CODE_SIGNING_ALLOWED=NO`** — CI has no Apple Developer certificate. Build verification doesn't need signing. Archive/notarisation is a separate S2 task (`desktop app build pipeline` in 100days.md)
- **`continue-on-error: true` initially** — start informational, promote to blocking once we confirm the macOS runner has a compatible Xcode/SDK version (needs macOS 15 SDK for deployment target)
- **`xcpretty`** — formats xcodebuild output into readable lines. The `|| true` prevents xcpretty exit code from masking xcodebuild failures (xcpretty returns 0 even on build failure; the step fails on xcodebuild's exit code before the pipe)
- **No dependency on `lint` or `test`** — runs in parallel. Swift builds are independent of Python/Node
- **Debug configuration** — faster than Release (no optimisation), sufficient for compilation verification
- **Includes Swift tests** — the BristlenoseTests target already has 5 test files (Tab, I18n, LLMProvider, KeychainHelper, ProjectIndex). Running them in CI catches regressions immediately. Tests use `InMemoryKeychain` and temp file URLs, so no real credentials or filesystem side effects
- **Single macOS job** — no matrix needed. One Xcode version, one deployment target, one architecture (arm64 on GitHub's M1 runners)

**Cost:** ~2-3 min on a macOS runner = ~$0.20/push at 10× rate. Acceptable.

**Sprint:** not in S1. Add to S2 alongside "Desktop app build pipeline" and "Code signing" items, which share the same macOS runner infrastructure.

**Verification:** after adding the job, push to `wip` and confirm the build step passes. Check that `xcodebuild` finds the scheme (it's a shared scheme at `xcshareddata/xcschemes/Bristlenose.xcscheme`).

## Adding a new CI step

Decision tree:

1. **Does it need to run?** If it duplicates an existing check or tests something that can't fail, skip it.
2. **Which job?** Static analysis → `lint`. Python runtime behaviour → `test`. Frontend → `frontend`. Full-stack integration → `e2e`.
3. **Blocking or informational?** Can the author always fix the failure before merging? If yes, blocking. If it depends on third parties, informational (`continue-on-error: true`).
4. **Does it need the matrix?** Only if behaviour varies across Python versions or OS. Most checks don't — put them in `lint` (runs once).
5. **Does it produce an artifact?** If so, name it descriptively and set appropriate retention (90 days for compliance, 7 days for debug).

## Maintenance

**Quarterly dependency review (next: May 2026).** `pip list --outdated`, bump for security and features. Check pip-audit and npm audit output for newly actionable advisories.

**Python EOL dates.** 3.10 reaches EOL October 2026. Decision: drop from matrix before launch or keep as floor? If dropping, update `requires-python` in `pyproject.toml` and remove from matrix simultaneously.

**Runner image updates.** GitHub periodically updates `ubuntu-latest` and `macos-latest` base images. These can break FFmpeg availability, system Python, or native lib paths. If a previously-green macOS cell goes red after a runner update, check the [GitHub Actions runner images changelog](https://github.com/actions/runner-images/releases).

**Promoting informational → blocking.** Review quarterly. When a step's pre-existing error count reaches zero, promote it. Current candidates and their error counts:
- mypy: 9 errors (third-party SDK types)
- ESLint: 84 problems (jsx-a11y, react-hooks)

**CI minutes budget.** Public repo — Linux minutes are free. macOS minutes consume from the 2,000 free minutes/month at 10× rate. At current push volume (1–3/day) this is well within budget. Monitor if push frequency increases significantly.
