# Platform and dependency policy

*Single source of truth for how Bristlenose handles platform-major versions (Node, Python, macOS, Xcode), dependency updates, and the rituals that keep us off the "Adobe surprise" treadmill.*

Last reviewed: 4 May 2026.

## Why this doc exists

Bristlenose runs on a stack of platforms that move on independent annual cycles. Left to default, every WWDC keynote, every Node major, every Python release candidate is a paper cut; aggregated, they're the difference between a tool that ships reliably and one that's perpetually catching up. This doc names the trade-offs explicitly so the same reasoning isn't re-derived every quarter.

It is also the policy layer that makes Dependabot useful instead of noisy. Dependabot is great at telling us *what* changed; this doc decides *whether and when* to take it.

## Principle

**Stay on stable.** Never run on an odd-numbered Node, a Python release candidate, or a macOS developer beta as a primary environment. New platform majors are tested deliberately on side machines or branches; they never become the "main" target until they're shipped GA *and* the ecosystem has caught up.

**Move as a wave, not a phone call.** Major version bumps tend to ripple — a Node major drags jsdom, vitest, eslint, vite. Take majors in coordinated batches (a "tooling sprint"), not as four uncoordinated dependabot PRs over a fortnight.

**Calendar the platforms, automate the rest.** Platform majors are calendar events (WWDC, Node Oct LTS cut, Python Oct release). Dep minor/patch is automation. Manually deciding individual minor patch bumps is the worst of both worlds.

## The four pillars

| Pillar | Annual cadence | What we pin to | Where the detail lives |
|---|---|---|---|
| **Node** | LTS cut (April + October) | Active LTS; skip 21/23/25 | This doc + `frontend/CLAUDE.md` "Node 24 LTS required" |
| **Python** | Release (October) | `requires-python = ">=3.10"`; floor + ceiling tested | [`docs/design-ci.md`](design-ci.md) §"Why 3.10–3.13?" + §"Python EOL dates" |
| **macOS** | WWDC (June) → GA (Sept) | Deployment target = current LTS-1 | [`docs/design-decisions.md`](design-decisions.md) (Sequoia rationale); current `pbxproj` |
| **Xcode/Swift** | September (WWDC year + 3mo) | Latest stable; bump within 30 days of GA | This doc + [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md) (sidecar Python.framework constraint) |

### Pillar 1 — Node

Current state: CI on Node 20 (4× `node-version: "20"` in `.github/workflows/{ci,release}.yml`); local-dev target Node 24 LTS per `frontend/CLAUDE.md`. The mismatch is flagged as known in [`docs/design-ci.md`](design-ci.md) §"Risks accepted".

**Policy:**

- Match CI to local-dev: both on the current active Node LTS.
- Skip odd-numbered majors — they're "Current" only, never LTS, used for previewing features that will land in the next even major.
- Bump CI's `node-version` immediately after a new LTS lands (April or October), not on the day a Dependabot PR demands it.
- Document the bump in CHANGELOG.md.

**Known hazard:** Node 25 + jsdom 29 broke `localStorage.X is not a function` for ~140 tests in April 2026 (CHANGELOG v0.14.5). The interaction is jsdom's missing Web Storage polyfill expecting Node's native API, which Node 25 gates behind a flag. Today's evidence (#99 vitest run) suggests jsdom 29 + Node 24 is fine; Node 25 is still hot.

### Pillar 2 — Python

Most of the thinking is already in [`docs/design-ci.md`](design-ci.md):

- **Why 3.10–3.13** — `pyproject.toml` declares `requires-python = ">=3.10"`. Testing the floor (3.10) and ceiling (3.13) catches compatibility boundaries; middle versions catch deprecation-cycle issues.
- **Why macOS Python is `continue-on-error`** — pure-Python ships via Linux-built PyPI/Homebrew/Snap; macOS failures are informational. Revisit when desktop integration tests exist.
- **3.10 EOL October 2026** — decision before then: drop from matrix and bump `requires-python`, or keep 3.10 as the floor. Both are defensible.

**Sidecar Python is separate.** The desktop bundle ships its own CPython 3.12 inside `Python.framework`; user system Python doesn't enter that path. See [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md). Bumping the sidecar Python is a coordinated event with macOS bumps (App Store SDK requirements, code signing, framework reseal) — not a Dependabot trigger.

**Policy additions on top of design-ci.md:**

- Don't run CI or local dev on a Python "release candidate" — only on stable releases.
- Treat Python 3.14 as "watch but defer" until the macOS `ensurepip` issue (CLAUDE.md gotcha) clears upstream. Re-check date: October 2026 (post 3.14.1).
- The TODO to extract `scripts/primary-python-version.sh` (referenced in `release.yml:28` but missing; see `docs/private/100days.md`) is the right time to centralise the pin — bundle with the next CI Python bump.

### Pillar 3 — macOS

Current deployment target: dual — **macOS 15.0 (Sequoia)** for the production scheme, **macOS 26.1 (Tahoe)** for some debug/feature schemes (`desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj`). Rationale for the Sequoia floor: [`docs/design-decisions.md`](design-decisions.md) — Sequoia is n-1 by launch, avoids SwiftUI contortion for older APIs.

The Tahoe-specific issues already encountered:

- **Custom URL schemes + `.nonPersistent()` crash on macOS 26** — see [`docs/design-wkwebview-messaging.md`](design-wkwebview-messaging.md) §143. Workaround: HTTP loopback.
- **Sandbox-on Debug locale loading + resizable window** — fixed in v0.15.3 (today's CHANGELOG).
- **Apple Foundation Models / Apple Intelligence** — gated to macOS 26+ + compatible Mac, see [`docs/design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md) §"Apple FM provider".

**Policy:**

- Deployment target stays at LTS-1 (currently Sequoia/15.0). Bump when the current LTS becomes n-2.
- The dual-target setup (15.0 for prod, 26.1 for Apple-Intelligence-only schemes) is intentional. **Add a comment block in `pbxproj`** explaining which scheme uses which target. Currently easy to bump one without the other; that's a bug waiting to happen.
- WWDC week (June): install macOS developer beta on a non-primary machine. Build the desktop app. File any breakage as a tracked issue.
- Public beta (July): ship a TestFlight build on the new SDK to at least one beta tester running the public beta.
- GA (September): bump Xcode + deployment target if needed, sign, push within 30 days.
- App Store usually requires building with the latest *major* Xcode within ~6 months of GA. The September bump satisfies this with margin.

### Pillar 4 — Xcode / Swift

Coupled with macOS — bump alongside. The sidecar's Python.framework + Hardened Runtime + entitlements story (in [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md)) is sensitive to Xcode toolchain shifts; verify the C0–C5 signing chain after every Xcode major bump.

**Policy:** match Xcode to macOS GA (September). Don't run on Xcode betas in CI; use a maintainer's machine for beta testing.

## Pinning register

Things we know we're pinned at, with re-check dates. When a re-check date comes due in a quarterly review, the pin gets re-validated or removed.

| Pin | Reason | Re-check |
|---|---|---|
| **CI Node 20** | Inertia from initial CI setup; Node 24 lands in runner images. Bumping is selective-major decision. | June 2026 (post-WWDC, alongside any Node news) |
| **jsdom 27.x → 29.x batched with `claude/review-dependabot-updates-CF7in`** | jsdom 29 dropped Web Storage polyfill; was unsafe with Node 25 (see CHANGELOG v0.14.5). #89 + test fix lands the bump. | Resolved — once #89 merges |
| **lighthouse 12.x** | Lighthouse 13 requires Node ≥22.19; CI is on 20. Bump alongside Node. | Same as Node bump |
| **Python 3.14** | macOS `ensurepip` broken for `python -m venv` (CLAUDE.md gotcha). Watch upstream. | October 2026 (post 3.14.1) |
| **Python 3.10 floor** | EOL October 2026. Decision point. | Quarterly review preceding the EOL |
| **macOS deployment target 15.0** | Sequoia is n-1; avoids SwiftUI back-compat work. | When Sequoia becomes n-2 (autumn 2026 if macOS 27 ships on time) |
| **macOS deployment target 26.1 (Apple Intelligence schemes)** | Foundation Models requires macOS 26+. | When/if the gate moves |
| **Sidecar CPython 3.12** | Bundled in `Python.framework`; bumping is a signing/entitlement event. | Coordinated with macOS major bump |

## Auto-merge boundary

**Minor and patch bumps auto-merge** when:

1. They land in a `minor-and-patch` Dependabot group (the `groups` block in `.github/dependabot.yml` is the gate);
2. Full CI is green (lint + frontend-lint-type-test + 8-cell Python matrix + e2e + perf-gate);
3. The PR has no manual `do-not-merge` label.

The risk of auto-merge is "a flaky test once a year that lets a regression through." The CI surface is broad enough (~2328 Python tests + ~1265 Vitest + e2e on Chromium and WebKit + perf gate) that the credible regression vector is narrow. The mitigation is the existing release window: pushes to `main` after 9pm London → if a regression slips through, it's caught before the next morning's release.

**Major bumps are hand-reviewed**, with a selective ignore list for deps that empirically cause rework. See `.github/dependabot.yml` for the maintained list. Selective rather than blanket ignore — react-i18next 17, for example, was painless and worth taking quickly.

**Security advisories** bypass everything. A security PR opens regardless of `ignore` rules; review and merge within 7 days, regardless of release-window timing. Quarterly is too slow for security.

## Tooling-sprint cadence

Once per quarter, batch the deferred majors into a coordinated release. This is the natural fixture for:

- Node LTS bump (when due).
- Major bumps from the `ignore` list that have been gathering.
- Re-check of pins from the register.
- macOS deployment-target review.

A tooling sprint is roughly 1–2 days for a maintainer with a tidy testing surface. Skip it if there's nothing to do; don't ritualise for its own sake.

## WWDC ritual (annual)

Calendar events, not vibes. Quarterly review absorbs the post-mortem.

| Date | Event | Action |
|---|---|---|
| WWDC week (early June) | Keynote + developer beta | Install developer beta on a non-primary machine. Build the desktop app. File breakage. |
| Mid-July | Public beta | Ship TestFlight build on the new SDK to ≥1 beta tester running public beta. |
| Late September / early October | macOS GA | Bump Xcode + `MACOSX_DEPLOYMENT_TARGET` if needed. Sign, notarise, push within 30 days. |

WWDC 2026: ~5 weeks out at time of writing. Action item: check before WWDC week whether we have a non-primary machine available for the developer beta install.

## Cross-references to existing thinking

This doc is the index. The detail lives elsewhere — don't duplicate.

- **Python policy:** [`docs/design-ci.md`](design-ci.md) §"Test" + §"Risks accepted" + §"Future work".
- **Sidecar Python:** [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md).
- **macOS deployment-target rationale:** [`docs/design-decisions.md`](design-decisions.md) §"Apple Silicon + macOS Sequoia" (or wherever — search for the relevant block).
- **Tahoe-specific gotchas:** [`docs/design-wkwebview-messaging.md`](design-wkwebview-messaging.md) §143; [`docs/design-native-inspector.md`](design-native-inspector.md) §"Spike run".
- **Apple Intelligence / Foundation Models gate:** [`docs/design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md) §"Apple FM provider".
- **Node 24 LTS local-dev requirement:** [`frontend/CLAUDE.md`](../frontend/CLAUDE.md) "Node 24 LTS required".
- **Quarterly review template:** [`docs/methodology/framework-arc-quarterly-review.md`](methodology/framework-arc-quarterly-review.md) — Section 6 added to track platform/tooling state.

## Open questions / known gaps

- `scripts/primary-python-version.sh` is referenced in `release.yml:28` but doesn't exist. The first CI Python bump should ship the helper alongside (per `docs/private/100days.md`).
- macOS Python `continue-on-error: true` may need promoting to blocking once desktop integration tests land.
- Auto-merge workflow (proposed in `.github/workflows/dependabot-automerge.yml`) is the operational implementation of this doc's auto-merge boundary; review it as you would any new CI workflow before enabling.
- "How quickly do we react to a Tier 1 CVE?" (npm advisory rated critical) is not in this doc. Defaulting to "same-day acknowledge, 7-day patch ship". Worth a separate hardening pass before alpha.
