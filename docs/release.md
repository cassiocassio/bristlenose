# Release Process

## Version — single source of truth

The version lives in **one place only**: `bristlenose/__init__.py`.

```python
__version__ = "0.4.0"
```

`pyproject.toml` uses `dynamic = ["version"]` with `[tool.hatch.version] path = "bristlenose/__init__.py"`, so hatchling reads it from there. Do **not** add a `version` key to `[project]`.

## Cutting a release

```bash
# 1. Bump the version
#    Edit bristlenose/__init__.py → __version__ = "X.Y.Z"

# 2. Add a changelog entry
#    Edit README.md → add a ### X.Y.Z section under ## Changelog

# 3. Commit and tag
git add bristlenose/__init__.py README.md
git commit -m "vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

That's it. GitHub Actions handles the rest automatically.

## What happens after you push a tag

The release pipeline spans **two repos** and runs five jobs:

```
bristlenose repo (release.yml)
├─ ci           → ruff, mypy, pytest (via workflow_call to ci.yml)
├─ build        → sdist + wheel (python -m build)
├─ publish      → PyPI via OIDC trusted publishing (no token needed)
├─ github-release → creates GitHub Release with auto-generated notes
└─ notify-homebrew → sends repository_dispatch to tap repo
                        │
                        ▼
homebrew-bristlenose repo (update-formula.yml)
└─ update       → fetches sdist URL + sha256 from PyPI JSON API
                  → patches Formula/bristlenose.rb (url, sha256, version)
                  → commits and pushes
```

## Cross-repo topology

| Component | Location |
|-----------|----------|
| CI workflow | `bristlenose` repo → `.github/workflows/ci.yml` |
| Release workflow (build, publish, GitHub Release, dispatch) | `bristlenose` repo → `.github/workflows/release.yml` |
| Reference copy of tap workflow | `bristlenose` repo → `.github/workflows/homebrew-tap/update-formula.yml` |
| Homebrew formula | `homebrew-bristlenose` repo → `Formula/bristlenose.rb` |
| Tap update workflow (authoritative) | `homebrew-bristlenose` repo → `.github/workflows/update-formula.yml` |
| `HOMEBREW_TAP_TOKEN` secret | `bristlenose` repo → Settings → Secrets → Actions |
| PyPI trusted publisher | pypi.org → bristlenose project → Publishing settings |
| PyPI `pypi` environment | `bristlenose` repo → Settings → Environments |

## Secrets

| Secret | Where | What it does | Rotation |
|--------|-------|-------------|----------|
| `HOMEBREW_TAP_TOKEN` | bristlenose repo → Actions secrets | Classic PAT with `repo` scope; lets `notify-homebrew` dispatch to the tap repo | No expiry set; rotate if compromised |
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
