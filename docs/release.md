---
status: partial
last-trued: 2026-08-14
trued-against: the publish-hold release rebuild (pypi environment hold live, strict-macos wired, bump-version no longer tags)
---

# Release Process

> **Superseded 23 Aug 2026 — the `pypi` required-reviewer hold was REMOVED.**
> A tag push now publishes. Everything below that describes the publish job
> waiting for an approval is history, kept because the reasoning for the
> ordering still holds; only the act that lands the release moved from the
> approval to the tag. The replacement gate is the job graph:
> `publish → build → ci(strict-macos: true)`, asserted by
> `check-release-ready.sh`'s `publish gate` row. See `CLAUDE.md` § Release
> timing and `scripts/release.sh`.


> **Truing status:** Partial — CLI channels only, deliberately (see Desktop
> channels pointer at the end). Head and tail trued 2026-08-14 against the
> publish-hold rebuild; the 2026-07-16 pass folded in bump-version.py and the
> two mandatory gates.

## Changelog

- _2026-08-14_ — trued up: rewrote §Post-push verification (the poll now starts
  at the **approval**, not the tag push — the old timeout remedy was tag surgery
  on a merely-unapproved release); redrew the §What-happens-after diagram (hold
  on `publish`, `verify-pypi` job, `strict-macos: true`); corrected every Snap
  claim (strict confinement not classic, edge publishes on dispatch only since
  8 Aug, publish jobs fail loudly on missing credentials); §CI gates gains the
  release-run macOS blocking; §Desktop channels upload path is
  `upload-testflight.sh`, Transporter is the fallback. Anchors:
  `.github/workflows/release.yml:111-122`, `.github/workflows/snap.yml:29-35,62-68`,
  `snap/snapcraft.yaml:3`, commits "hold publish for approval, and make the
  release gate certify macOS", "stop bump-version.py tagging a commit that
  doesn't exist yet".
- _2026-07-16_ — trued up: bump-version.py flow, two mandatory gates, Desktop
  channels pointer.

**Scope: PyPI · Homebrew · Snap (the CLI channels).** The desktop app ships
through separate channels — Developer-ID `.dmg` and App Store / TestFlight —
each with its own signing and build script. See **[Desktop channels](#desktop-channels)**
at the end.

## Version — single source of truth

The version lives in **one place only**: `bristlenose/__init__.py`.

```python
__version__ = "0.4.0"
```

`pyproject.toml` uses `dynamic = ["version"]` with `[tool.hatch.version] path = "bristlenose/__init__.py"`, so hatchling reads it from there. Do **not** add a `version` key to `[project]`.

## Cutting a release

**Bump semantics:** minor = feature (`0.20.0 → 0.21.0`), patch = fix
(`0.20.0 → 0.20.1`). Ask "does this add a capability?" — yes → minor.

**Use `scripts/bump-version.py` — don't hand-edit versions.** It updates
`bristlenose/__init__.py` (the single source), the man page `.TH` line + ISO
date, **and** the desktop Xcode `project.pbxproj` (marketing version + build
number); stages those. It does **not** commit or tag — the commit the tag
belongs on doesn't exist until you've added the changelog prose, so the tag is
yours to create afterwards (the script prints the exact sequence). The
standard flow:

```bash
# 1. Write the CHANGELOG.md + README.md changelog entries FIRST
#    Format: **X.Y.Z** — _D Mon YYYY_   (e.g. **0.21.0** — _16 Jul 2026_)

# 2. Bump (writes __init__.py + man page + pbxproj, stages them; no commit, no tag)
./scripts/bump-version.py minor        # or: patch / major / an explicit x.y.z

# 3. Stage CHANGELOG+README (bump staged the rest), commit, THEN tag —
#    the tag must point at the bump commit, so it cannot come first
git add CHANGELOG.md README.md
git commit -m "bump to X.Y.Z"
git tag vX.Y.Z
git rev-parse HEAD; git rev-parse vX.Y.Z^{}   # same SHA — confirm

# 4. Push branch and tag — two commands, back to back (never one `--tags`)
git push origin main
git push origin vX.Y.Z
```

**Pushing the tag IS publishing.** The `pypi` environment's required-reviewer
hold was **removed on 23 Aug 2026**. Nothing waits for a human: the tag push
starts `release.yml`, and PyPI receives the version on its own. PyPI is
immutable, so that version number is spent the moment it lands.

Until 23 Aug this section said the opposite, and said it for a good reason — the
hold was what let the tag go out *early*, alongside `main`, because a human
still stood between the run and PyPI. **That is no longer true, and the ordering
inverted with it: the tag now goes LAST.**

**What replaced the hold is mechanical, and stronger.** `publish` needs `build`
needs `ci`, and `release.yml` invokes `ci.yml` with `strict-macos: true`. PyPI
cannot receive a version whose full matrix, e2e and strict macOS suite did not
pass on the tagged commit. `check-release-ready.sh` asserts that chain in its
**`publish gate`** row and *fails* if it is ever broken — where the old hold was
a click that re-verified nothing.

**The `publish hold` row still exists, with its polarity inverted.** It reports
`ok` on **zero** reviewers, and **warns when one exists** — because a restored
hold would break the tag-last ordering `scripts/release.sh run` encodes. If you
ever see that warning, someone re-armed the environment; either remove it again
or stop using `release.sh run` until you have.

```sh
gh api repos/cassiocassio/bristlenose/environments/pypi \
  --jq '[.protection_rules[]? | select(.type=="required_reviewers")] | length'
# 0 = expected. A non-zero means a hold came BACK — do NOT restore one.
```

To abandon: **don't push the tag.** Everything before it — bump, commit, `main`,
both builds, even the TestFlight and `.dmg` uploads — is reversible or merely
audience-reaching, and none of it is on PyPI. If the tag is already pushed and
its CI is still running, deleting it (`git push --delete origin vX.Y.Z && git tag
-d vX.Y.Z`) cancels the publish only if you win the race; assume you will not.
`./scripts/release.sh abandon <X.Y.Z>` prints this plus the website consequence.

### Two mandatory gates — do not skip

- **Evening timing (working days):** the act that *lands* the release is the
  **tag push** — that is what waits for **21:00 London** on working days (avoids
  version churn during client hours). Weekends and **UK bank holidays: any
  time**; check the official feed rather than deriving the date. Pushing `main` publishes nothing and can
  happen any time; it buys CI signal, which is the point of doing it early.
  Weekends: any time. This used to say "publish approval"; the approval is gone
  and the wait moved to the tag.
- **Post-APPROVAL PyPI verification (mandatory):** an approved publish job is
  **not** a release reaching PyPI — the pipeline has silently stalled before
  (v0.15.5→.9, ~6 days, unnoticed). The clock starts at the **approval**, not
  the tag push: until you approve, the run is *parked at the hold by design*,
  and a poll started at tag-push time will "time out" on a release that is
  merely unapproved. **Do not reach for tag surgery on an unapproved run** —
  check the run page first; if `publish` shows "waiting for review", the fix
  is the Approve button, not the tag. After approving, verify:

  ```sh
  curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/bristlenose/X.Y.Z/json
  # 200 = published; the version-specific endpoint is authoritative
  # (the /json index is CDN-cached and can read stale — don't trust a single
  # negative from it)
  ```

  `release.yml`'s own `verify-pypi` job also polls server-side and turns a
  stalled publish into a red run. The tag-redelivery workaround
  (`git push --delete origin vX.Y.Z && git push origin vX.Y.Z`) remains valid
  for exactly one case: `gh run view --workflow=release.yml` shows the workflow
  **never fired at all** (the debounced-tag-push class).

**Test/CI/docs-only fixes reuse the tag** — a change touching only `tests/`,
`e2e/`, `docs/`, `.claude/`, `.github/`, or fixtures ships a byte-identical
wheel, so don't bump: force-move the tag to the fix commit and re-push. (Counter:
once a version has published to PyPI, immutability forces a bump instead.)

## What happens after you push a tag

The release pipeline spans **three repos/workflows** and runs multiple jobs:

```
bristlenose repo (release.yml) — triggered by v* tag
├─ ci           → full suite via workflow_call to ci.yml, WITH strict-macos: true
│                 (macOS test cells BLOCK here; informational on daily pushes)
├─ build        → sdist + wheel (python -m build), SBOMs, attestation
├─ publish      → PUBLISHES to PyPI. No hold, no approval, nothing waits
│                 for a human (the required-reviewer hold went 23 Aug 2026).
│                 OIDC trusted publishing, no token. Immutable once it lands.
│
│   the three below are PARALLEL siblings, all `needs: publish` —
│   none of them gates another:
├─ github-release → creates GitHub Release with auto-generated notes
├─ verify-pypi  → server-side poll; a stalled publish goes RED, not silent
└─ notify-homebrew → sends repository_dispatch to tap repo
                        │
                        ▼
homebrew-bristlenose repo (update-formula.yml)
└─ update       → fetches sdist URL + sha256 from PyPI JSON API
                  → patches Formula/bristlenose.rb (url, sha256)
                  → commits and pushes
                  (formula structure is stable — only URL/SHA change.
                   See docs/design-homebrew-packaging.md for why the
                   formula uses post_install pip instead of resource blocks)

bristlenose repo (snap.yml) — BUILDS on every push/PR; publishes only on demand
├─ build          → canonical/action-build (amd64, ~10 min) — publishes nothing
├─ publish-edge   → workflow_dispatch ONLY (gh workflow run snap.yml --ref main)
└─ publish-stable → dispatch against a v* tag ref (--ref vX.Y.Z)
                    NB a tag-ref dispatch fires BOTH publish jobs — the ref
                    adds stable, it does not switch channels
```

Note: since 8 Aug 2026 the snap workflow **builds** on every push (build-health
coverage, zero publish risk) but **publishes only when dispatched** — edge does
NOT track main automatically, and goes stale unless someone dispatches it.
Both publish jobs fail loudly if `SNAPCRAFT_STORE_CREDENTIALS` is missing
(they were green no-ops before 14 Aug 2026).

## Cross-repo topology

| Component | Location |
|-----------|----------|
| CI workflow | `bristlenose` repo → `.github/workflows/ci.yml` |
| Release workflow (build, publish, GitHub Release, dispatch) | `bristlenose` repo → `.github/workflows/release.yml` |
| Snap build & publish workflow | `bristlenose` repo → `.github/workflows/snap.yml` |
| Snap recipe | `bristlenose` repo → `snap/snapcraft.yaml` |
| Reference copy of tap workflow | `bristlenose` repo → `.github/workflows/homebrew-tap/update-formula.yml` |
| Homebrew formula | `homebrew-bristlenose` repo → `Formula/bristlenose.rb` |
| Tap update workflow (authoritative) | `homebrew-bristlenose` repo → `.github/workflows/update-formula.yml` |
| `HOMEBREW_TAP_TOKEN` secret | `bristlenose` repo → Settings → Secrets → Actions |
| `SNAPCRAFT_STORE_CREDENTIALS` secret | `bristlenose` repo → Settings → Secrets → Actions |
| PyPI trusted publisher | pypi.org → bristlenose project → Publishing settings |
| PyPI `pypi` environment | `bristlenose` repo → Settings → Environments |

## Secrets

| Secret | Where | What it does | Rotation |
|--------|-------|-------------|----------|
| `HOMEBREW_TAP_TOKEN` | bristlenose repo → Actions secrets | Classic PAT with `repo` scope; lets `notify-homebrew` dispatch to the tap repo | No expiry set; rotate if compromised |
| `SNAPCRAFT_STORE_CREDENTIALS` | bristlenose repo → Actions secrets | Snap Store login credentials for publishing to edge/stable channels. Generated with `snapcraft export-login --snaps=bristlenose --channels=edge,beta,candidate,stable` | Rotate periodically; expires based on Ubuntu One session |
| PyPI OIDC | pypi.org trusted publisher | `release.yml` `publish` job uses `id-token: write` — no token stored anywhere | N/A (keyless) |
| `GITHUB_TOKEN` | automatic per workflow run | `github-release` job uses it to create GitHub Releases | Automatic |

## CI gates

- **Ruff**: hard gate
- **pytest**: hard gate — and on **release runs** the macOS matrix cells are
  **blocking** too (`ci.yml`'s `strict-macos` input, passed `true` by
  `release.yml`; informational on daily pushes). A release green certifies both
  platforms; a push green certifies Linux.
- **mypy**: informational (continue-on-error due to third-party SDK type issues)

## Homebrew tap automation

The Homebrew tap updates automatically after every PyPI publish. The `notify-homebrew` job in `release.yml` sends a `repository_dispatch` event to the [`homebrew-bristlenose`](https://github.com/cassiocassio/homebrew-bristlenose) repo. The tap's `update-formula.yml` workflow:

1. Receives the version from the dispatch payload
2. Fetches the sdist URL + sha256 from `https://pypi.org/pypi/bristlenose/{version}/json` (with a retry loop for CDN propagation)
3. Uses `sed` to patch the `url`, `sha256`, and `version` lines in `Formula/bristlenose.rb`
4. Commits as `github-actions[bot]` and pushes

**Manual fallback** — if the automation fails (e.g. expired token, PyPI API issue), update the tap manually:

```bash
# Get the new sdist URL and sha256
curl -s https://pypi.org/pypi/bristlenose/X.Y.Z/json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for f in data['urls']:
    if f['packagetype'] == 'sdist':
        print(f'url: {f[\"url\"]}')
        print(f'sha256: {f[\"digests\"][\"sha256\"]}')
"
```

Clone `cassiocassio/homebrew-bristlenose`, edit `Formula/bristlenose.rb` — update the `url`, `sha256`, and `version` lines. Commit and push.

## Homebrew architecture note

The formula at `Formula/bristlenose.rb` creates a Python 3.12 virtualenv and runs `pip install bristlenose==<version>` from PyPI. This uses pre-built wheels rather than individual Homebrew resource stanzas. A traditional resource-stanza formula would require maintaining 100+ pinned dependencies (including PyTorch, onnxruntime, spacy) — impractical for an ML-heavy tool. The pip-in-venv approach is standard for custom taps with complex dependency trees.

## Snap Store

### First-time setup (one-off, before first publish)

```bash
# 1. Register the snap name
snapcraft register bristlenose

# 2. (historical) Classic confinement approval was planned but never needed —
#    the shipped snap is STRICT confinement (snap/snapcraft.yaml:3), so there
#    is no forum request step.

# 3. Export store credentials for CI
snapcraft export-login --snaps=bristlenose \
  --channels=edge,beta,candidate,stable credentials.txt

# 4. Add to GitHub repo secrets
#    Settings → Secrets → Actions → SNAPCRAFT_STORE_CREDENTIALS
#    Paste the contents of credentials.txt
```

### How snap publishing works

The snap pipeline is independent of the PyPI/Homebrew pipeline. It runs via `.github/workflows/snap.yml`:

- **Every push / pull request** → builds the amd64 snap — **publishes nothing**
  (build-health coverage restored 8 Aug 2026; publishing is a decision, not a
  side effect of committing)
- **`gh workflow run snap.yml --ref main`** → publishes the build to `edge`
- **`gh workflow run snap.yml --ref vX.Y.Z`** → publishes to `stable` — and NB
  a tag-ref dispatch fires the edge job too (the ref adds stable, it does not
  switch)
- Both publish jobs **fail loudly** if `SNAPCRAFT_STORE_CREDENTIALS` is absent
  (silent green skips retired 14 Aug 2026)

The snap version is read from `bristlenose/__init__.py` at build time via `adopt-info` + `craftctl` — no manual version bumping in `snapcraft.yaml`.

### Channel strategy

```
edge      ← manual dispatch against main (does NOT auto-track main)
beta      ← manual promotion: snapcraft release bristlenose <rev> beta
candidate ← manual promotion: snapcraft release bristlenose <rev> candidate
stable    ← manual dispatch against a v* tag ref
```

Users install from stable by default:
```bash
sudo snap install bristlenose
```

Testers install from edge:
```bash
sudo snap install bristlenose --edge
```

### Manual snap operations

```bash
# Check published revisions
snapcraft status bristlenose

# Promote a specific revision to a channel
snapcraft release bristlenose <revision> beta

# Build locally (Linux only, or in a Multipass VM)
snapcraft --destructive-mode

# Install a locally-built snap (bypasses Store entirely)
sudo snap install --dangerous ./bristlenose_*.snap
```

### Architecture note

CI builds amd64 only (GitHub Actions `ubuntu-latest`). arm64 snaps can be built locally on Apple Silicon via Multipass or on an arm64 Linux box, but are not published to the Store yet. See `docs/design-doctor-and-snap.md` for the full local build workflow.

## Desktop channels

The macOS app ships through **separate** channels — none of the CLI pipeline
above applies to them, and they're decoupled from the CLI version line (a CLI
release doesn't imply a desktop build, or vice versa):

- **Developer-ID `.dmg`** — direct download from bristlenose.app (an expiring
  alpha sampler). Built + notarised by `desktop/scripts/build-dmg.sh` (one
  notary round trip, on the image — app-level notarisation retired 14 Aug
  2026), published atomically by `desktop/scripts/upload-dmg.sh`. Full
  mechanics: **[design-dmg-build.md](design-dmg-build.md)**.
- **App Store / TestFlight `.pkg`** — Apple Distribution signed, built by
  `desktop/scripts/build-all.sh`; uploaded by
  `desktop/scripts/upload-testflight.sh` (gate as precondition, independent
  ASC confirmation; Transporter is the documented *fallback* on its failure
  path). See
  **[design-desktop-build-orchestration.md](design-desktop-build-orchestration.md)**
  and `desktop/CLAUDE.md`.

**All five channels on one page: [release-channels.md](release-channels.md)** —
which script or trigger reaches which destination, what a tag push actually
fires, and the expiry clocks. Written 8 Aug 2026; this doc remains the detailed
CLI process.
