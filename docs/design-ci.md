# CI architecture

## Goals

CI exists to catch regressions before they reach users. It answers one question per push: "did this change break anything we already had working?"

CI is not a quality gate for perfection. Steps that enforce correctness (ruff, pytest, tsc, man page version) block the build. Steps that surface information (mypy, pip-audit, npm audit, ESLint) run but don't block — they show regressions in the log without preventing a merge. The distinction matters: blocking steps must be fixable by the author; informational steps often flag issues in third-party dependencies that can't be resolved immediately.

## Philosophy

**Fail fast.** Static checks (lint, types, man page) run in a single `lint` job before any test matrix work begins. If ruff finds an error, 8 test jobs are skipped instantly instead of each burning 3 minutes to discover the same failure.

**Bound every job; a hang must fail, not wait.** A job with no `timeout-minutes` inherits GitHub's 6-hour default ceiling. A single stalled network call can therefore burn six hours and — because a cancelled job cancels its workflow — silently take sibling workflows down with it. Every job sets an explicit `timeout-minutes`, and any step that talks to an external CDN/registry is additionally bounded per-attempt and retried (see [Timeouts and external-download resilience](#timeouts-and-external-download-resilience)). Fast failure with a clear error beats slow death with none.

**Least privilege by default.** CI runs other people's code (every `uses:` line) with access to our secrets and an automatic repo token. Two defaults shrink the blast radius if any of that code is compromised: the token is read-only unless a job explicitly needs more, and third-party actions are pinned to immutable commit SHAs rather than moving tags. See [Least privilege and supply-chain pinning](#least-privilege-and-supply-chain-pinning).

**Canonical cell.** One combination — ubuntu-latest + Python 3.12 — is the "real" CI. It produces the coverage report, runs the dependency audit, generates the SBOM. Other matrix cells exist to catch compatibility issues, not to duplicate bookkeeping.

**macOS as signal, not gate.** macOS runners cost 10× Linux and surface platform-specific issues that rarely block a pure-Python change. All macOS jobs run with `continue-on-error: true` — a failure shows as a yellow warning, not a red block. Investigate when yellow, but don't hold a merge for it.

**`fail-fast: false` on the test matrix.** A Python 3.10 failure doesn't predict a 3.13 failure. Let all cells finish so you see the full picture in one push, not across three retry cycles.

**Tests, not tools, define correctness.** Ruff enforces style. Pytest enforces behaviour. TypeScript enforces types. Playwright enforces integration. If a check isn't in one of these categories, it's informational.

## Fragility classes

Every CI incident in the project's history fits one of six classes. Naming them is the point: each has a distinct *signature*, a distinct *catch*, and a distinct *fix horizon*. A single "CI monitor" that treated them as one thing would mishandle most of them — which is exactly why the defensive measures in this document are several small mechanisms, not one big one.

| Class | Failure signature | What bit us | What catches it now | Status |
|-------|-------------------|-------------|---------------------|--------|
| **A — Hang** | job runs to the 6h ceiling, ends `cancelled`, cascades to sibling workflows | 2026-06-03 e2e (WebKit CDN stall) | per-job `timeout-minutes` + bounded-retry on external downloads | fixed → [Timeouts](#timeouts-and-external-download-resilience) |
| **B — Silent release stall** | tag is green on GitHub, PyPI never updates, *no failure event fires* | v0.15.5–v0.15.9 (~8 days, tags pushed, never published) | `verify-pypi` job (in-pipeline) + post-push poll (human backstop, CLAUDE.md) | guarded → [Release workflow](#release-workflow) |
| **C — Local-vs-CI parity** | passes locally, fails in CI (no API keys; `ruff check .` vs `ruff check bristlenose/`) | v0.6.7–v0.6.13 (7 versions) | parity discipline: lint the whole repo, mock all env-dependent calls | discipline (CLAUDE.md "Before committing") |
| **D — False green** | a check passes when it shouldn't | swallowed errors; non-`success` counted green; E2E 401s read as "fast latency"; perf-gate false-greens | assert `res.ok` + size floors in E2E; treat non-`success` as non-green; audit `continue-on-error` | partial — standing audit target |
| **E — Supply-chain / least-privilege** | a compromised action or over-broad token turns one bad step into repo-write or secret theft | latent (not yet bitten; tj-actions class) | third-party actions SHA-pinned + read-only default token | fixed → [Least privilege](#least-privilege-and-supply-chain-pinning) |
| **F — Methodology drift** | the *reason* a check exists lives in someone's head; nobody can audit the deck | the meta-cause that lets A–E recur | this document + the standing audit below | ongoing |

These classes resist a clean "transient vs structural" label, and trying to sort incidents that way is a trap: the 2026-06-03 hang *looked* transient (a CDN stall) but was structural (a missing timeout), and the v0.15.x stall produced no failure event at all. So the posture is to **verify invariants, not classify symptoms** — see [Standing audit targets](#maintenance).

### Further reading

The patterns here are standard CI practice, not local invention:

- **Martin Fowler, "Eradicating Non-Determinism in Tests"** (martinfowler.com, 2011) — why flaky tests destroy a suite's signal value, and the discipline of quarantine.
- **Google Testing Blog, "Flaky Tests at Google and How We Mitigate Them"** (2016) — empirical flaky-test rates at scale and the case for treating flakiness as a first-class defect.
- **Arkency, "How to deal with flaky tests"** — the quarantine-with-a-time-limit pattern: a quarantined test must be fixed or deleted by a deadline, never parked indefinitely.
- **DHH / 37signals, "System tests have failed"** (world.hey.com, 2023) — the cost-benefit argument against over-investing in brittle end-to-end tests.
- **PyPA, "Trusted Publishers" and the GitHub Actions publishing guide** (docs.pypi.org) — the OIDC release-pipeline pattern behind the PyPI publish step and `verify-pypi`.
- **NetNewsWire** (github.com/Ranchero-Software/NetNewsWire) — reference for the CI shape of an indie open-source Mac app, informing the planned `mac-build` / `desktop-build` direction.

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

## Timeouts and external-download resilience

**Standing rule.** Every job declares an explicit `timeout-minutes`. Any step that downloads from an external CDN/registry (Playwright browsers, apt, large model fetches) is *additionally* bounded with a per-attempt `timeout` and retried. A workflow must never be able to hang for hours on a half-open socket.

### Why (postmortem — 2026-06-03)

The `e2e` job had no `timeout-minutes` and ran `npx playwright install chromium webkit --with-deps` bare. Chromium downloaded fine; the WebKit download from the Playwright CDN then stalled on a half-open socket (TCP connection alive, zero bytes flowing). `playwright install` has **no internal download deadline**, so the step sat silent for ~6 hours until GitHub's default 6-hour job ceiling auto-cancelled it. Because a cancelled job cancels its workflow, this also took down the parent CI run *and* the Perf workflow. None of the actual e2e tests ever ran — the job died during browser provisioning. Every gate that mattered (Mac Build, the full Python test matrix) was green; the only casualty was six hours of runner time and two falsely-red workflows.

The tell that this is an infra stall, not a real failure: a genuine test or compile failure exits in seconds-to-minutes, never hours. A multi-hour "failure" is almost always a missing timeout around a network call.

**Root-cause update (5 Jun 2026).** The "half-open socket" reading above was the best guess at the time; the v0.15.13 release surfaced the real mechanism. It was a **yauzl extraction hang** in Playwright `<1.60.0` on **Node 24.16+**: the browser zip downloads to 100%, then *extraction* silently stalls (microsoft/playwright#40998, fixed in 1.60.0). It presents like a CDN stall but isn't — the bytes arrive, the unzip wedges. Bumping `@playwright/test` to 1.60.0 (`14af414`) was the durable fix. The timeout+retry below is still the correct *structural* defence regardless of mechanism — and it proved itself here, converting the original 6-hour silent cascade into a 15-minute fast-fail — but the root fix was the version bump. Generalised lesson: a `playwright install` that reaches 100% then hangs is an *extraction* problem (check Node × Playwright compatibility), not a network one.

### The pattern

Job-level backstop:

```yaml
e2e:
  runs-on: ubuntu-latest
  timeout-minutes: 30   # fail fast instead of the 6h default ceiling
```

Per-step bounded retry for any external download (`timeout` is GNU coreutils, present on `ubuntu-latest`):

```yaml
- name: Install Playwright browsers
  working-directory: e2e
  timeout-minutes: 18              # backstop bounding the whole retry sequence
  run: |
    n=0
    until [ "$n" -ge 3 ]; do
      timeout 5m npx playwright install chromium webkit --with-deps && exit 0
      n=$((n + 1))
      echo "::warning::playwright browser install attempt $n stalled or failed; retrying in 15s"
      sleep 15
    done
    echo "::error::playwright browser install failed after 3 attempts"
    exit 1
```

Why these numbers: a healthy browser download finishes in seconds, so `timeout 5m` per attempt catches a stall fast without false-positiving on a slow-but-working network. Three attempts with a 15s backoff ride out a transient CDN blip. The loop `exit 0`s on first success and `exit 1`s only after all attempts fail — a genuinely broken install still reddens the build (no silent swallow). The same pattern guards the chromium-only install in `perf.yml`.

### What this deliberately is *not*

Browser-binary caching (`actions/cache` on `~/.cache/ms-playwright`) is the canonical *speed* optimisation and would skip the download on most runs, but it does **not** fix the hang — the `timeout` does. Caching only reduces how often you touch the network; an uncached run (cache miss, new Playwright version) still needs the bound. Add caching for speed if desired, but never as the hang fix.

## Least privilege and supply-chain pinning

**Standing rules.**

1. Every third-party action (one not published by `actions/*`, `github/*`, or another platform-vendor org we already trust to run code) is pinned to a full 40-character commit SHA, never a moving tag.
2. Every workflow sets a top-level `permissions:` block defaulting to `contents: read`. A job that needs to write opts in explicitly, scoped to exactly what it needs.

### Why third-party actions are pinned to a commit SHA

A `uses: owner/action@v3` line downloads code from someone else's repository and runs it on our runner with access to that job's secrets and `GITHUB_TOKEN`. A tag like `v3` is *mutable* — the action's author, or anyone who compromises their account, can re-point it at new code, and the next run executes that code with no change on our side. This is a live attack class: in March 2025 the widely-used `tj-actions/changed-files` action was compromised by exactly this tag-repointing, leaking thousands of repositories' secrets into build logs.

A commit SHA is a content hash and therefore immutable — `@ff45666…` always resolves to byte-identical code. The trailing `# v3.0.0` comment keeps the line human-readable and lets Dependabot propose SHA bumps as reviewable PRs (you approve the new code, rather than receiving it silently).

The three pinned actions were prioritised because each touches a credential:

| Action | Workflow | Credential in reach |
|--------|----------|---------------------|
| `peter-evans/repository-dispatch` | `release.yml` | `HOMEBREW_TAP_TOKEN` (can push to the tap repo) |
| `snapcore/action-build` | `snap.yml` | — (build only; pinned for consistency) |
| `snapcore/action-publish` | `snap.yml` | `SNAPCRAFT_STORE_CREDENTIALS` (can publish as us) |

### Why the token is read-only by default

Each run gets an automatic `GITHUB_TOKEN`. Left at the repository default it is often *read **and write***, meaning any step in any job could push commits, cut releases, or edit issues. Most jobs only read the repo (checkout, test, build). A read-only default is the blast-radius limiter: if a step is ever compromised, a read-only token cannot turn "ran malicious code" into "pushed malicious code to main."

Mechanics worth knowing: a job-level `permissions:` block *fully replaces* the top-level default for that job (it does not merge), and any scope not listed is set to `none`. In `release.yml` two jobs opt in — `publish` declares `id-token: write` (the OIDC handshake that authenticates to PyPI) and `github-release` declares `contents: write` (to create the release). Every other job runs read-only. The change is behaviour-preserving: artifact upload/download between jobs uses a separate runtime token, not `GITHUB_TOKEN`, so read-only is sufficient everywhere else.

### What is deliberately *not* pinned

- **`actions/*` and `github/codeql-action`** — GitHub's own verified org. Different threat model (compromising them compromises the platform itself), and pinning forgoes their automatic security patches.
- **`pypa/gh-action-pypi-publish@release/v1`** — PyPA's official publisher, referenced by a *branch* (more mutable than a tag). PyPA explicitly recommends tracking that branch so the action — which holds the PyPI publishing identity via OIDC — always carries their latest security fixes. A conscious trade-off; revisit if PyPA's guidance changes.
- **`homebrew-tap/update-formula.yml`** — not a live workflow here (GitHub ignores nested subdirectories); it is a template copied into the tap repo, and its hardening belongs to that repo. It is already permission-scoped (`contents: write`, which it needs to push the formula).

### Follow-ups (not done in this pass)

- **OIDC everywhere.** PyPI already uses trusted publishing (no stored token). The Homebrew dispatch still relies on a stored PAT (`HOMEBREW_TAP_TOKEN`); migrating it to a short-lived credential is a separate, larger task.
- **`peter-evans/repository-dispatch` is a major version behind** (pinned at v3.0.0; v4 is available). Pinning locks *what we already run*; a major-version upgrade is a separate decision because it may carry breaking changes.

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
7. **`verify-pypi`** — polls PyPI's JSON endpoint (20× over ~10 min, riding out Fastly cache staleness) until the just-published version appears. Runs *parallel* to `github-release`; does **not** gate it.

The release workflow never runs independently — it always gates on the full CI suite first.

**`verify-pypi` is a load-bearing fence, not decoration.** Releases v0.15.5–v0.15.9 silently stalled for ~8 days because tags reached GitHub but the upload never reached PyPI and nothing checked (fragility class B). Do not remove `verify-pypi` to "speed up" releases — it is the only in-pipeline proof that the publish actually happened. On failure it deliberately does **not** delete the tag: twine has already consumed the version immutably on PyPI by the time it runs, so deletion would mask that and tempt a re-bump of an already-published version.

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
| Locale parity | `i18n-check.yml` validates key coverage across 20 full locales |
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
6. **Does it download from an external CDN/registry?** If so, bound it: per-attempt `timeout` + retry on the step, and confirm the job has a `timeout-minutes`. See [Timeouts and external-download resilience](#timeouts-and-external-download-resilience). Any *new* job must set `timeout-minutes` regardless.
7. **Does it add a third-party action?** Pin it to a full commit SHA (with a `# vX.Y.Z` comment), not a moving tag, and give the job the minimum token permissions it needs — read-only unless it must write. See [Least privilege and supply-chain pinning](#least-privilege-and-supply-chain-pinning).

## Maintenance

**Standing audit targets.** These are the invariants that keep the [fragility classes](#fragility-classes) from recurring. Re-check them on the cadence below, and whenever a workflow file changes. The discipline is to verify the invariant, not to classify a symptom:

- **Every `continue-on-error: true` is a deliberately-swallowed signal.** Confirm each is still justified — third-party noise the author genuinely cannot fix — and not a real failure someone muted to land a merge. The inventory lives in [Informational steps](#informational-steps).
- **A conclusion other than `success` is not green.** `cancelled`, `timed_out`, and a `skipped` job that *should* have run are all amber-or-worse. The 2026-06-03 hang ended as `cancelled` and looked benign — any monitoring must treat non-`success` as non-green.
- **`verify-pypi` stays in the release pipeline** ([Release workflow](#release-workflow)) — the only automated proof a publish reached PyPI.
- **Every third-party action stays SHA-pinned and every workflow keeps a `permissions:` block** ([Least privilege and supply-chain pinning](#least-privilege-and-supply-chain-pinning)). A new `uses:` on a moving tag, or a new workflow with no permissions block, is a regression.
- **Every job declares `timeout-minutes`** ([Timeouts and external-download resilience](#timeouts-and-external-download-resilience)).

**Quarterly dependency review (next: May 2026).** `pip list --outdated`, bump for security and features. Check pip-audit and npm audit output for newly actionable advisories.

**Python EOL dates.** 3.10 reaches EOL October 2026. Decision: drop from matrix before launch or keep as floor? If dropping, update `requires-python` in `pyproject.toml` and remove from matrix simultaneously.

**Runner image updates.** GitHub periodically updates `ubuntu-latest` and `macos-latest` base images. These can break FFmpeg availability, system Python, or native lib paths. If a previously-green macOS cell goes red after a runner update, check the [GitHub Actions runner images changelog](https://github.com/actions/runner-images/releases).

**Promoting informational → blocking.** Review quarterly. When a step's pre-existing error count reaches zero, promote it. Current candidates and their error counts:
- mypy: 9 errors (third-party SDK types)
- ESLint: 84 problems (jsx-a11y, react-hooks)

**CI minutes budget.** Public repo — Linux minutes are free. macOS minutes consume from the 2,000 free minutes/month at 10× rate. At current push volume (1–3/day) this is well within budget. Monitor if push frequency increases significantly.
