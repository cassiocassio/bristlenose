---
status: partial
last-trued: 2026-07-16
trued-against: HEAD@main on 2026-07-16
---

# Release Process

> **Trued 2026-07-16.** Corrected "Cutting a release" to use
> `scripts/bump-version.py` (the doc described hand-editing, which drifted once
> the script landed), folded in the two mandatory gates that lived only in
> `CLAUDE.md` (evening timing, post-push PyPI verification), and added the
> **Desktop channels** pointer — the `.dmg` and App Store paths were entirely
> absent, so a reader here would ship a half-release. `status: partial` because
> this doc is accurate for the CLI channels but deliberately covers only those.

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
number); stages those; and creates the git tag.

**The footgun:** it creates the tag on the *current* HEAD — *before* your bump
commit exists — so the tag points at the wrong commit until you delete and
re-create it after committing. The standard flow:

```bash
# 1. Write the CHANGELOG.md + README.md changelog entries FIRST
#    Format: **X.Y.Z** — _D Mon YYYY_   (e.g. **0.21.0** — _16 Jul 2026_)

# 2. Bump (writes __init__.py + man page + pbxproj, stages them, tags early)
./scripts/bump-version.py minor        # or: patch / major / an explicit x.y.z

# 3. Drop the premature tag, stage CHANGELOG+README (bump staged the rest),
#    commit, then re-tag on the real commit
git tag -d vX.Y.Z
git add CHANGELOG.md README.md
git commit -m "bump to X.Y.Z"
git tag vX.Y.Z

# 4. Push branch, then tag separately (see gates below)
git push origin main
git push origin vX.Y.Z
```

GitHub Actions handles PyPI / Homebrew / Snap from there.

### Two mandatory gates — do not skip

- **Evening timing (weekdays):** push to `origin/main` only after **21:00
  London** on weekdays (avoids version churn during client hours). Weekends: any
  time. Preview remotely without triggering a release via a `wip` branch
  (`git push origin main:wip`). Override for genuine urgency.
- **Post-push PyPI verification (mandatory):** a tag reaching GitHub is **not** a
  release reaching PyPI — the pipeline has silently stalled before (v0.15.5→.9,
  ~6 days, unnoticed). After pushing the tag, poll until PyPI flips:

  ```sh
  for i in $(seq 1 20); do sleep 90
    pypi=$(curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version)
    echo "[$i] PyPI: $pypi"; [ "$pypi" = "X.Y.Z" ] && break
  done
  ```

  20×90s ≈ 30 min (recent runs take 23–25 min). If PyPI still shows the old
  version after 30 min, `gh run view --workflow=release.yml` to check the run
  fired; a debounced tag push may need redelivery
  (`git push --delete origin vX.Y.Z && git push origin vX.Y.Z`).

**Test/CI/docs-only fixes reuse the tag** — a change touching only `tests/`,
`e2e/`, `docs/`, `.claude/`, `.github/`, or fixtures ships a byte-identical
wheel, so don't bump: force-move the tag to the fix commit and re-push. (Counter:
once a version has published to PyPI, immutability forces a bump instead.)

## What happens after you push a tag

The release pipeline spans **three repos/workflows** and runs multiple jobs:

```
bristlenose repo (release.yml) — triggered by v* tag
├─ ci           → ruff, mypy, pytest (via workflow_call to ci.yml)
├─ build        → sdist + wheel (python -m build)
├─ publish      → PyPI via OIDC trusted publishing (no token needed)
├─ github-release → creates GitHub Release with auto-generated notes
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

bristlenose repo (snap.yml) — triggered by push to main AND v* tags
├─ build        → snapcore/action-build (amd64, ~10 min)
├─ publish-edge → push to main → publishes to snap edge channel
└─ publish-stable → v* tag → publishes to snap stable channel
```

Note: the snap workflow runs on **every push to main** (not just tags). This
means edge always has the latest main build. Stable only updates on tagged
releases, same as PyPI/Homebrew.

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
- **pytest**: hard gate
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

# 2. Request classic confinement approval
#    Post at https://forum.snapcraft.io with justification
#    (CLI tool needing arbitrary filesystem access, .env files, etc.)
#    Takes 3-5 business days.

# 3. Export store credentials for CI
snapcraft export-login --snaps=bristlenose \
  --channels=edge,beta,candidate,stable credentials.txt

# 4. Add to GitHub repo secrets
#    Settings → Secrets → Actions → SNAPCRAFT_STORE_CREDENTIALS
#    Paste the contents of credentials.txt
```

### How snap publishing works

The snap pipeline is independent of the PyPI/Homebrew pipeline. It runs via `.github/workflows/snap.yml`:

- **Every push to main** → builds amd64 snap → publishes to `edge` channel
- **Every v* tag** → builds amd64 snap → publishes to `stable` channel
- **Pull requests** → builds snap (no publish) → artifact available for download

The snap version is read from `bristlenose/__init__.py` at build time via `adopt-info` + `craftctl` — no manual version bumping in `snapcraft.yaml`.

### Channel strategy

```
edge      ← every push to main (CI auto-publishes)
beta      ← manual promotion: snapcraft release bristlenose <rev> beta
candidate ← manual promotion: snapcraft release bristlenose <rev> candidate
stable    ← tagged releases (CI auto-publishes)
```

Users install from stable by default:
```bash
sudo snap install bristlenose --classic
```

Testers install from edge:
```bash
sudo snap install bristlenose --edge --classic
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
sudo snap install --dangerous --classic ./bristlenose_*.snap
```

### Architecture note

CI builds amd64 only (GitHub Actions `ubuntu-latest`). arm64 snaps can be built locally on Apple Silicon via Multipass or on an arm64 Linux box, but are not published to the Store yet. See `docs/design-doctor-and-snap.md` for the full local build workflow.

## Desktop channels

The macOS app ships through **separate** channels — none of the CLI pipeline
above applies to them, and they're decoupled from the CLI version line (a CLI
release doesn't imply a desktop build, or vice versa):

- **Developer-ID `.dmg`** — direct download from bristlenose.app (an expiring
  alpha sampler). Built + notarised by `desktop/scripts/build-dmg.sh`, published
  by `scp` + the website deploy. Full mechanics:
  **[design-dmg-build.md](design-dmg-build.md)**.
- **App Store / TestFlight `.pkg`** — Apple Distribution signed, built by
  `desktop/scripts/build-all.sh`; uploaded via Transporter / `xcrun altool`. See
  **[design-desktop-build-orchestration.md](design-desktop-build-orchestration.md)**
  and `desktop/CLAUDE.md`.

A single doc mapping all five channels (PyPI · Homebrew · Snap · `.dmg` ·
TestFlight) doesn't exist yet — this doc plus the two linked above are the
current pieces.
