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
| **Python** | Release (October) | `requires-python = ">=3.10"`; floor + ceiling tested | [`docs/design-ci.md`](design-ci.md) (matrix rationale at line 89; EOL note at line 236) |
| **macOS** | WWDC (June) → GA (Sept) | Deployment target = current LTS-1 | [`docs/design-decisions.md`](design-decisions.md) §"Desktop app: SwiftUI + sidecar" (Sequoia/n-1 rationale at line 65); current `pbxproj` |
| **Xcode/Swift** | September (WWDC year + 3mo) | Latest stable; bump within 30 days of GA | This doc + [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md) (sidecar Python.framework constraint) |

### Pillar 1 — Node

Current state: CI and local-dev are aligned on **Node 24 LTS**. All three workflows resolve Node from `.tool-versions` (`node 24`) via `node-version-file: '.tool-versions'` (`.github/workflows/ci.yml:133,217`, `release.yml:38`) — there are no hardcoded `node-version: "20"` pins. (Historical note: an earlier Node-20 / Node-24 mismatch was the original motivation here; it's since been closed by the `.tool-versions` single-source.)

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

- **Custom URL schemes + `.nonPersistent()` crash on macOS 26** — see [`docs/design-wkwebview-messaging.md:143`](design-wkwebview-messaging.md). Workaround: HTTP loopback.
- **Sandbox-on Debug locale loading + resizable window** — fixed in v0.15.3 (today's CHANGELOG).
- **Apple Foundation Models / Apple Intelligence** — gated to macOS 26+ + compatible Mac, see [`docs/design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md) §"2. Apple Foundation Models — Swift-side, not Python" (line 43) and §"Sequencing" item 3 (line 88).

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
| **jsdom pinned to 27.x in `frontend/package.json`** | jsdom 29 dropped Web Storage polyfill; was unsafe with Node 25 (see CHANGELOG v0.14.5). Test fix landed in v0.15.3 (#99) clears the assertion blocker; `#89` (jsdom → 29) is open and will land next. | Re-check once `#89` merges |
| **lighthouse 12.x** | Lighthouse 13 requires Node ≥22.19; CI is on 20. Bump alongside Node. | Same as Node bump |
| **Python 3.14** | macOS `ensurepip` broken for `python -m venv` (CLAUDE.md gotcha). Watch upstream. | October 2026 (post 3.14.1) |
| **Python 3.10 floor** | EOL October 2026. Decision point. | Quarterly review preceding the EOL |
| **macOS deployment target 15.0** | Sequoia is n-1; avoids SwiftUI back-compat work. | When Sequoia becomes n-2 (autumn 2026 if macOS 27 ships on time) |
| **macOS deployment target 26.1 (Apple Intelligence schemes)** | Foundation Models requires macOS 26+. | When/if the gate moves |
| **Sidecar CPython 3.12** | Bundled in `Python.framework`; bumping is a signing/entitlement event. | Coordinated with macOS major bump |

## Triage boundary

**Manual review for everything, with a selective major-ignore.** Auto-merge is deferred — see "Open questions" below. In the meantime:

- **Minor and patch bumps**: arrive grouped (`minor-and-patch` block in `.github/dependabot.yml`). One PR per ecosystem per Monday. Glance at the diff, confirm CI is green (lint + frontend-lint-type-test + 8-cell Python matrix + e2e + perf-gate), squash-merge.
- **Major bumps**: hand-reviewed. The `ignore` block in `.github/dependabot.yml` suppresses majors for the deps that empirically cause rework (jsdom, vite, vitest, eslint family, lighthouse, etc.); the rest still flow as PRs. Selective rather than blanket — react-i18next 17, for example, was painless (#90) and worth taking quickly.
- **Security advisories**: Dependabot's `security-update` PRs bypass `ignore` rules entirely (per Dependabot's documented behaviour — `ignore` filters apply only to `version-update` PRs). Review and merge within 7 days, regardless of release-window timing. *Caveat*: the bypass works only for advisories already in GitHub's Advisory Database (GHSA). For deeper coverage, defence-in-depth via `pip-audit` and `npm audit` running in CI is the right next step (currently neither runs as a gate — see Open questions).

**Why pip's ignore list is shorter than npm's.** The Python wheel ecosystem has fewer "Node major drags everything with it" cascades. The pip ignores are just the deps where a major bump genuinely rewrites Bristlenose (pydantic 1→2 was the canonical event; fastapi major would be similar). The npm side carries the scar tissue of CHANGELOG v0.14.5 and today's session — more pillars coupled to Node majors, more deps that move with them.

## Tooling-sprint cadence

Once per quarter, batch the deferred majors into a coordinated release. This is the natural fixture for:

- Node LTS bump (when due).
- Major bumps from the `ignore` list that have been gathering.
- Re-check of pins from the register.
- macOS deployment-target review.

**Before applying the batch, run `/cassandra`.** It pre-mortems the blast radius of the whole wave — resolver conflicts, ABI couplings, silent runtime breaks — grounded against installed metadata (not the `outdated` headline) and the gossip on each bump, and records the prophecy to `docs/dependency-premortem-log.md` so the next sprint can see how well the last call held. After the batch lands, `/cassandra --score` closes the loop. See [`docs/design-dependency-premortem.md`](design-dependency-premortem.md).

A tooling sprint is roughly 1–2 days for a maintainer with a tidy testing surface. Skip it if there's nothing to do; don't ritualise for its own sake.

## Quarterly tooling review

Run alongside [`docs/methodology/framework-arc-quarterly-review.md`](methodology/framework-arc-quarterly-review.md) — same cadence, separate ~15-minute checklist. The methodology review is for the ten-year arc; this is for the platform underneath. They share a slot in the calendar, not a document.

The review answers, in order:

1. **Are we on the current Node LTS?** If not — what's the date by which we will be?
2. **Are we on a Python version not yet at "release candidate"?** Are any supported Python versions reaching EOL within two quarters? (3.10 EOL Oct 2026 is the live one.)
3. **macOS deployment target review.** Should the floor move? Is the dual-target setup (prod 15.0 + AI-features-only 26.1) still right?
4. **Beta-window check** — was the most recent beta window honoured? (Q3 has WWDC + developer beta install; Q4 has GA + Xcode bump.)
5. **Pinning register sweep** — any pin past its re-check date? Re-validate or remove.
6. **Tooling-sprint trigger** — have enough deferred majors piled up to justify a 1–2 day batch release? (Three is usually the trigger; one or two is below the per-PR cost.) If triggered, **run `/cassandra` on the batch before applying it** — pre-mortem first, apply second.
7. **Security advisories** — any open more than 2 weeks? Note exceptions and reasons.

Output is a single bullet list in the quarterly review note ("Tooling: …") — not a separate document. The discipline is honesty: "nothing changed" is a valid answer if it's true.

## WWDC ritual (annual)

Calendar events, not vibes. Quarterly review absorbs the post-mortem.

| Date | Event | Action |
|---|---|---|
| WWDC week (early June) | Keynote + developer beta | Install developer beta to the **external Samsung T7**. Boot from it via Startup Disk when needed. Build the desktop app. File breakage. Internal SSD remains the trusted dev environment. |
| Mid-July | Public beta | Ship TestFlight build on the new SDK to ≥1 beta tester running public beta. |
| Late September / early October | macOS GA | Bump Xcode + `MACOSX_DEPLOYMENT_TARGET` if needed. Sign, notarise, push within 30 days. |

**Why external SSD over VirtualBuddy.** External-boot gives real hardware: Apple Intelligence / Foundation Models, Neural Engine perf, camera/sensor APIs all work — important for the Apple FM provider work in `design-pluggable-llm-routing.md`. Risk of a beta bricking the machine is low; if it crashes hard, restart on internal. (VirtualBuddy is a viable fallback for anyone without spare external storage — same compatibility table for sandbox / signing / WKWebView / AVFoundation, minus the Apple-Intelligence-specific gates.)

WWDC 2026: ~5 weeks out at time of writing. Action item: install macOS 27 developer beta to the T7 within a week of the keynote; build the desktop app on it before public beta.

## Cross-references to existing thinking

This doc is the index. The detail lives elsewhere — don't duplicate.

- **Python policy:** [`docs/design-ci.md`](design-ci.md) — `### test` (line 59); `## Matrix strategy` floor/ceiling rationale (line 89); `### Known gaps` (line 156); `## Maintenance` Python EOL note (line 236).
- **Sidecar Python:** [`docs/design-desktop-python-runtime.md`](design-desktop-python-runtime.md).
- **macOS deployment-target rationale:** [`docs/design-decisions.md`](design-decisions.md) §"Desktop app: SwiftUI + sidecar" (lines 61–65; the n-1 / Sequoia logic is line 65).
- **Tahoe-specific gotchas:** [`docs/design-wkwebview-messaging.md:143`](design-wkwebview-messaging.md) (custom-scheme `.nonPersistent()` crash); [`docs/design-native-inspector.md:85,99`](design-native-inspector.md) (spike notes on the same crash, scheme-specific not general).
- **Apple Intelligence / Foundation Models gate:** [`docs/design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md) §"2. Apple Foundation Models — Swift-side, not Python" (line 43) and §"Sequencing" item 3 (line 88).
- **Node 24 LTS local-dev requirement:** [`frontend/CLAUDE.md`](../frontend/CLAUDE.md) "Node 24 LTS required".
- **Quarterly review template:** [`docs/methodology/framework-arc-quarterly-review.md`](methodology/framework-arc-quarterly-review.md) — companion pointer added at end of Section 7.

## Open questions / known gaps

- **Auto-merge for minor/patch.** Deferred. The current model is manual squash-merge after a CI-green check. Promoting to true auto-merge needs (a) a `.github/workflows/dependabot-automerge.yml` workflow, (b) `pip-audit` and `npm audit --audit-level=high` running as required gates, and (c) `npm config set ignore-scripts true` in the verification step to close the install-script attack surface. Worth landing as a discrete hardening PR; not bundled into this policy.
- **Tiered security SLA matrix** — current "7 days" line is defensible for High/Medium severity but weak for npm `severity: critical` (RCE in a runtime dep, prototype pollution in a parser). Industry norm is 72-hour patch for criticals. Worth a Tier 1 (72h) / Tier 2 (7d) / Tier 3 (next quarterly) matrix before alpha.
- **`scripts/primary-python-version.sh`** is referenced in `release.yml:28` but doesn't exist. The first CI Python bump should ship the helper alongside (per `docs/private/100days.md`).
- **macOS Python `continue-on-error: true`** may need promoting to blocking once desktop integration tests land.
- **ESLint stack — `groups` vs `ignore`?** Currently four separate ignores (eslint, eslint-plugin-react-hooks, typescript-eslint, typescript). Bumping them as a wave argues for a single `groups: lint-stack` block instead — one PR, dropped from the ignore list. Defer until the next coordinated bump exposes the friction in practice.
- **WWDC ritual durability.** Currently a prose commitment with no calendar hook. Cost of "I forgot" is a year of accumulated breakage; a recurring auto-filed GitHub issue (June 1 each year) is the obvious mitigation. Add when the rest of the desktop machinery has settled.
- **`pbxproj` dual-target comment.** The doc identifies the risk (line 72); the comment in the project file itself is a follow-up.
