# Track C C3 — Session Notes (20 Apr 2026)

**One-sentence orientation.** C3 shipped the sandbox-compatible credential path for the Mac desktop app: Swift host reads Keychain via `Security.framework` and injects `BRISTLENOSE_<PROVIDER>_API_KEY` env vars at sidecar launch. Python never calls `/usr/bin/security` in the sandboxed sidecar; its existing subprocess path remains the CLI Mac happy path. Session ran autonomously overnight; all laptop-work steps landed; smoke test (Step 6, GUI-bound) and empty-ents retest (split into own plan) pending human.

## What was accomplished

Five commits landed on `sidecar-signing` (`a8dc3cb..ab1b2a1`):

1. **`desktop/c3: inject keychain api keys as env vars`** — `ServeManager.overlayAPIKeys(into:using:)` added alongside `overlayPreferences`. Accepts an injectable `KeychainStore` (test-friendly). Iterates four LLM providers (Anthropic, OpenAI, Azure, Google — Miro descoped). Skips nil AND empty values. Emits one `Logger.info` per injection (presence only, never value). Obsolete "no env var needed" comment removed from `start(projectPath:)`. `KeychainHelper.hasAnyAPIKey()` fixed — now iterates all providers instead of hard-coding Anthropic. `PrivacyInfo.xcprivacy` (pre-staged during earlier session) rode along on this commit; expected content, harmless irregularity.
2. **`desktop/c3: runtime log redactor for api key shapes`** — `handleLine()` now masks Anthropic/OpenAI/Google key-shaped substrings with `***REDACTED***` before appending to `outputLines`. Azure deliberately skipped (32-char hex false-positives on UUIDs/SHAs; 100days.md entry tracks pre-beta re-audit). Auth-token parse moved to before redaction so base64url tokens can't possibly collide. Invariant + limitations documented next to `ansiRegex`.
3. **`bristlenose: broaden keychain subprocess except for sandbox contexts`** — `MacOSCredentialStore` exception handling broadened on `get`/`set`/`delete` to cover `FileNotFoundError`/`PermissionError`/`OSError` in addition to `CalledProcessError`. Module-level `logger` added; DEBUG log line preserves diagnostics for CLI users with `-v`. Docstring explicitly names the sandbox use case. No API change.
4. **`desktop/c3: tests for env injection, redactor, broadened except`** — 6 new Python tests (three `OSError`-family cases on `get`, plus `set`/`delete` exec-denial tests, plus DEBUG-log assertion via `caplog`) and 2 new test classes for `_populate_keys_from_keychain` (env-wins-over-keychain + keychain-fallback-when-env-empty). Two new aspirational Swift test files (`BristlenoseTests` target not wired — same treatment as existing `KeychainHelperTests.swift`): `ServeManagerEnvTests.swift` and `HandleLineRedactorTests.swift` with pattern-valid fake keys. Small internal refactor: `keyRedactionRegex` made internal + `redactKeys(in:)` helper extracted so tests can reach it.
5. **`desktop/c3: CI grep gate for Swift logging hygiene`** — new `desktop/scripts/check-logging-hygiene.sh` scans host-app Swift for logger calls that interpolate credential-shaped identifiers (`key|secret|token|credential|password`) without an explicit `privacy: .private|.sensitive` marker, and for `print()` calls that dump env dicts. Allowlist file (`logging-hygiene-allowlist.md`, `e2e/ALLOWLIST.md`-pattern markers). Wired as step 1a of `build-all.sh` pre-flight — fails fast before archive. Current codebase passes clean.

Plus **`docs/c3: credential flow, sub-processor list, review notes`** (final commit, not in the numbered series above): docs updates across nine files — `desktop/CLAUDE.md`, `SECURITY.md`, `design-desktop-python-runtime.md` (new "Credential flow" section), `design-modularity.md`, `design-decisions.md`, `design-desktop-settings.md`, `bristlenose/llm/CLAUDE.md`, `bristlenose-sidecar.entitlements` (stale comment rewritten to reflect post-C2 Apple Distribution reality), and a new `docs/private/launch-docs/app-review-notes.md` (force-added, product-intent sentence left as FIXME for Martin to hand-write).

## What works (proven by tests + build)

- `xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"` → `** BUILD SUCCEEDED **`. Verified after each Swift-touching commit plus a final end-of-session pass.
- `.venv/bin/python -m pytest tests/` (full suite) → 2239 passed, 101 skipped, 22 xfailed, 3 errors. Runtime 2m32s.
  - The 3 errors are in `tests/test_autocode_discrimination.py::TestLiveLLMDiscrimination` — pre-existing, environment-dependent. Test class is `@pytest.mark.slow` but its class-level fixture instantiates an `LLMClient` at setup, which raises `ValueError: Claude API key not set` when `BRISTLENOSE_ANTHROPIC_API_KEY` isn't exported. Not caused by C3. Worth a follow-up (skip at fixture layer, not class-marker layer) but scope creep for this session.
- `.venv/bin/ruff check .` → clean (whole repo, matches CI).
- `desktop/scripts/check-logging-hygiene.sh` → clean against the real codebase; confirmed catches deliberate violations (temp `/tmp/hygiene-test/` scaffolding with `Logger.info("\(secret)")` + `print(env)`); confirmed silences when `privacy: .private` marker present.
- Redactor regex sanity-checked against `trial-runs/fossda-opensource/perf-baselines/pipeline-run.log` — zero false-positive hits.

## What's parked, and why

- **Step 6 — manual Debug smoke test.** Requires Xcode Cmd+R, Settings.app GUI, throwaway Anthropic key paste, `ps ewww` against running sidecar. Not automatable; left for Martin. Procedure is spelled out in `~/.claude/plans/c3-closeout.md` Step 6 — two passes (Pass A: pattern-valid fake key forces an auth-failure traceback, verify redactor masks it; Pass B: real throwaway key, verify happy path + length check + zero substring hits in `log stream`).
- **Empty-entitlements retest.** Split into its own plan (`~/.claude/plans/c3-empty-ents-retest.md`) before execution started. Prerequisite: SECURITY #5+#8 unblocker so Release archive builds. 8-point procedure with notarised archive + second local user account + iCloud Keychain off + throwaway key + 2nd-screen `log stream` + full diagnostic toolkit for the red-case branch.
- **Host app `Bristlenose.entitlements` file.** Track A territory (sandbox flip). C3 is correct-by-construction; end-to-end proof under sandbox pends Track A.
- **`BristlenoseTests` target wiring.** Two new aspirational Swift test files added alongside the existing five orphan tests. Parked qa-backlog item — 20–60 min of pbxproj work.

## Gotchas burned in

1. **Swift `log.info(...)` doesn't match a naive `Logger\s*\(` regex.** `log` is an instance-var, not the type name. First pass of `check-logging-hygiene.sh` missed `Logger.info("... \(secret)")` because it required `Logger(`. Fixed by also matching `\.(info|debug|error|warning|fault|notice|trace|log|critical)\(` — covers the instance-method dispatch pattern too.
2. **`@testable import` reaches `internal` symbols but not `private`.** Had `keyRedactionRegex` as `private static let`; tests couldn't touch it. Made internal + added an internal `redactKeys(in:)` helper that `handleLine` delegates to — tests call the helper directly.
3. **`docs/private/` is gitignored.** `app-review-notes.md` needs `git add -f`. CLAUDE.md covers this but easy to forget.
4. **Ruff's `I001 [*]` import-sort rule fires on in-function imports.** The `_populate_keys_from_keychain` test imports both symbols at the top of each test method; had to `ruff check --fix` to merge them. Tests green either way.
5. **`git add <two-files>` then `git commit`** includes any other pre-staged files. `PrivacyInfo.xcprivacy` (staged during an earlier user turn) landed in the Step 2a commit. Harmless but worth naming in commit messages going forward.
6. **Build-all.sh already uses `$ROOT` for repo-root**, not `$REPO_ROOT`. Called `check-logging-hygiene.sh "$ROOT"` to match.

## File map — where C3 work landed

### Swift (host)
| File | Change |
|---|---|
| `ServeManager.swift` | New `overlayAPIKeys(into:using:)`; call site in `start`; redactor regex + `redactKeys(in:)` helper; `handleLine` reordered (auth parse before redact, append redacted); obsolete comment replaced |
| `KeychainHelper.swift` | `hasAnyAPIKey()` iterates all providers |

### Python (sidecar)
| File | Change |
|---|---|
| `bristlenose/credentials_macos.py` | Module docstring + logger; `get`/`set`/`delete` except broadened with DEBUG log |

### Tests
| File | Change |
|---|---|
| `tests/test_credentials.py` | 6 new MacOS exception cases + `TestPopulateKeysFromKeychain` (2 tests) |
| `desktop/Bristlenose/BristlenoseTests/ServeManagerEnvTests.swift` | NEW — aspirational |
| `desktop/Bristlenose/BristlenoseTests/HandleLineRedactorTests.swift` | NEW — aspirational |

### Scripts
| File | Change |
|---|---|
| `desktop/scripts/check-logging-hygiene.sh` | NEW |
| `desktop/scripts/logging-hygiene-allowlist.md` | NEW |
| `desktop/scripts/build-all.sh` | Wired check-logging-hygiene as pre-flight step 1a |

### Docs
| File | Change |
|---|---|
| `desktop/CLAUDE.md` | Current/Target Keychain row updated |
| `desktop/bristlenose-sidecar.entitlements` | Comment rewritten (post-C2 + C3 credential path) |
| `SECURITY.md` | Keychain entry reflects Swift-fetches; "Data leaves your machine only when" two-item list; no Miro |
| `bristlenose/llm/CLAUDE.md` | Priority order clarified |
| `docs/design-desktop-python-runtime.md` | New "Credential flow" section |
| `docs/design-modularity.md` | Env var name corrected (`_API_KEY` suffix); table row updated |
| `docs/design-decisions.md` | Credential-storage paragraph rewritten |
| `docs/design-desktop-settings.md` | "Python reads Keychain directly" phrasing removed |
| `docs/private/launch-docs/app-review-notes.md` | NEW (force-added) |
| `docs/private/sprint2-tracks.md` | C3 marked ✅; C4 budget revised up; duplicate C4 line removed |
| `docs/private/100days.md` | Pre-beta LLM-provider key-format re-audit entry added |

## Smoke test findings (post-hand-off, 21 Apr 2026)

After the autonomous session closed out, Martin ran the Step 6 manual smoke test (Xcode Cmd+R, Debug build, throwaway Anthropic key) and three data-bundling bugs surfaced that the autonomous session couldn't have caught — unit tests run against an editable install where every source dir is present. All were fixed on `sidecar-signing` before the doc-truing pass:

| Bug | Symptom | Commit | Root cause |
|---|---|---|---|
| **BUG-3** | Sidecar served the deprecated Jinja2 static-render HTML instead of the React SPA. Masked by serve mode's silent fallback — the UI looked plausibly like Bristlenose | `5aae47c` | `bristlenose/server/static/` (React SPA build output) not in PyInstaller `datas`. Fix includes a **fail-loud contract**: `_mount_prod_report` now returns HTTP 500 + error page (`3a9bc6a`) rather than falling back. Static render formally reframed as vestigial scaffolding (`66f4050`) |
| **BUG-4** | Browse Codebooks modal empty; CODEBOOK FRAMEWORKS list returned zero entries | `08a0664` | `bristlenose/server/codebook/*.yaml` not in `datas` — loaded as filesystem resource by `routes/codebook.py`, not via Python import |
| **BUG-5** | Every LLM call raised `FileNotFoundError` before reaching the provider | `08a0664` (same commit) | `bristlenose/llm/prompts/*.md` not in `datas` — loaded by `prompts/__init__.py::_load_prompt` as a filesystem resource |
| **BUG-6** | *(meta)* No gate existed to prevent a future fourth data dir from shipping missing | `673ddee` | Added `desktop/scripts/check-bundle-manifest.sh`: AST-parses the spec, walks `bristlenose/` for dirs containing runtime-data file extensions, asserts every uncovered dir appears in `datas` or in the allowlist. Wired as `build-all.sh` pre-flight step 2a |

Plus `bristlenose doctor --self-test` (`52024f8`) — runtime bundle-integrity check the sidecar can run against itself, giving the `doctor` command a sidecar-aware code path.

**Lesson burned in.** PyInstaller's `Analysis` only traces `.py` imports; non-`.py` runtime data must be listed explicitly in `datas`. Unit tests can't catch this because they run against the editable install where every source dir is on disk. The only audit that surfaces this class of issue is a manual end-to-end smoke test — and serve-mode's old silent fallback to static render masked even that. The fix is structural (bundle-manifest gate + fail-loud contract), not procedural — the gate now runs on every build, not "remember to check."

These findings were promoted into `docs/design-desktop-python-runtime.md` §"Bundle data requirements" and §"Fail-loud contracts" as the canonical reference.

## Open questions / follow-ups for future sessions

- **Empty-ents retest outcome.** If green, significant procurement win ("sidecar runs with empty entitlements"). If red, investigate which Mach-O actually needs DLV post-C2 single-identity signing. Diagnostic toolkit spelled out in the retest plan.
- **SECURITY #5 + #8 unblocker.** Plan at `~/.claude/plans/next-track-security-5-and-8-unblocker.md`. Prerequisite for the retest; not a prerequisite for C3 code (which landed without it).
- **C4 Privacy Manifest triage** — 222 `.so` files. Plan at `~/.claude/plans/c4-privacy-manifests.md`. Revised budget 1–2 days (was ½). Host manifest already drafted; sidecar + FFmpeg + Python.framework need the triage pass.
- **`BristlenoseTests` target wiring.** Stack of 7 aspirational Swift test files now. Each new Track C track adds more. Worth a dedicated micro-track between desktop tracks.
- **LLMSettingsView polish** — 7 Gruber-flagged items including save-on-blur key clobber (alpha-blocker-class per reviewer). Parked in qa-backlog per user decision; do not delay C3 on it.
- **Product-intent sentence** in `app-review-notes.md` — FIXME. User hand-writes before submission. Memory record exists (`project_app_review_notes_product_intent.md`).

## How to verify this session's output

Human steps (run any order, all independent):

```bash
# 1. All commits land cleanly and tests pass
cd "/Users/cassio/Code/bristlenose_branch sidecar-signing"
git log --oneline a8dc3cb^..HEAD
.venv/bin/python -m pytest tests/test_credentials.py

# 2. Swift still builds
cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS" 2>&1 | grep "BUILD SUCCEEDED"

# 3. Logging-hygiene gate runs clean
cd ../.. && desktop/scripts/check-logging-hygiene.sh

# 4. Manual smoke test (Step 6 of closeout plan — see plan for full procedure)
# Requires Xcode + throwaway Anthropic key (revoke after)

# 5. Push when ready (not pushed by autonomous session)
git push origin sidecar-signing
```

## References

- `~/.claude/plans/c3-closeout.md` — the execution plan this session followed
- `~/.claude/plans/c3-keychain-in-sandbox.md` — the design plan
- `~/.claude/plans/c3-empty-ents-retest.md` — the follow-up retest
- `~/.claude/plans/c4-privacy-manifests.md` — next track
- `~/.claude/plans/next-track-security-5-and-8-unblocker.md` — empty-ents prerequisite
- `docs/private/c2-session-notes.md` — prior context
- `docs/private/sprint2-tracks.md` — overall track status
