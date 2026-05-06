---
status: pending
last-trued: 2026-05-06
trued-against: HEAD@main on 2026-05-06
---

# Dev environment — adopt off-the-shelf tooling, stop hand-rolling

> Architecture decision (proposed). **Status: pending — Phase 0 only ships before TestFlight; Phases 1–4 are post-alpha.** Sibling to `desktop/CLAUDE.md` (build-script idioms), `docs/design-ci.md` (CI parity).

## Rule

**Phase 0 is the only phase that may land before TestFlight.** Phases 1–4 don't compete for attention during the alpha sprint, full stop. Re-open this section after the first internal-TestFlight cohort feedback lands.

## Why this exists

`/new-feature` and the surrounding shell scripts have grown a per-worktree dev-environment story by accretion. Today it pins Python via `release.yml` grep, `pip install -e '.[dev,serve]'` via hardcoded literal, builds the frontend, optionally fetches static FFmpeg, and runs a four-probe smoke test. Each new dep added elsewhere in the repo silently drifts the skill — surfaced 6 May 2026 when worktree-built desktop .apps shipped without `ffprobe` because no probe checked.

The proposed fix from the same session was a `scripts/dev-setup.sh` extraction with fingerprint-based drift detection. That plan was reviewed and the parsimony agent flagged it as **reinventing existing tooling.** This doc records the redirect.

## Principle

**Don't write our own dev-environment manager.** Tool versions, dependency installs, and task running are solved problems with mature off-the-shelf tooling that has more eyes on it than we ever will.

## Off-the-shelf inventory (what we'd actually adopt)

| Tool | Solves | Status |
|---|---|---|
| **`mise`** ([mise.jdx.dev](https://mise.jdx.dev)) | Per-project tool versions (Python, Node, etc.) via `mise.toml`; tasks; hooks. Successor to `asdf`. | Mature 2024+, native Mac, fast |
| **`uv`** ([astral.sh/uv](https://docs.astral.sh/uv)) | Python venv + deps + lockfile, ~10–100× faster than pip. | Mature 2024+, already on roadmap (wheel hash pinning is gated on this migration) |
| **`just`** ([just.systems](https://just.systems)) | Task runner. `justfile` declares tasks. Modern `make` without the tabs. | Mature, used widely (Cloudflare, Astral) |
| **`direnv`** | Auto-activate per-directory env on `cd`. | Mature 10+ years |

What stays: `npm` (already off-the-shelf for Node), `pyproject.toml`, `package.json`, `desktop/scripts/*` (project-specific build/sign chain).

## Mapping: pain points → tooling

| Pain | Today | Off-the-shelf |
|---|---|---|
| Pin Python version | grep `release.yml` | `mise.toml`: `python = "3.12"` |
| Pin Node version | implicit | `mise.toml`: `node = "22"` |
| Install Python deps | `pip install -e '.[dev,serve]'` literal in skill | `uv sync --extra dev --extra serve` |
| Install Node deps | `npm install` | `npm ci` (still npm) |
| Auto-activate venv on `cd` | not done | `.envrc`: `layout python` (1 line) |
| Run common tasks | shell scripts in two locations | `justfile` — declared once, discoverable via `just --list` |
| Detect tool-version drift | not done | `mise install` re-reads `mise.toml`; reports missing |
| Detect Python dep drift | not done | `uv sync --check` exits non-zero if `uv.lock` differs from venv |
| Smoke probes | hardcoded bash in skill | `just verify` task — bash inside, but in *one* declared place |

## What stays project-specific (the genuine 5%)

These are bristlenose-shaped and don't belong in any off-the-shelf tool. They stay in `/new-feature` and `desktop/scripts/`:

- Worktree creation + Xcode project hand-off
- `BRANCHES.md` updates
- Finder label tagging (purple = active, orange = stale)
- Symlink-from-main for gitignored binaries (becomes a `just symlink-binaries` task)
- Setup-incomplete sentinel
- Handoff plan seeding from the gitignored handoffs area
- The full `desktop/scripts/{fetch-ffmpeg,build-sidecar,sign-sidecar,build-all,reset-sandbox-state}.sh` chain — these stay; `just` can wrap them as discoverable tasks but doesn't replace them

## Target shape

### Repo root files (new)

```
mise.toml               # tool versions
justfile                # task declarations
.envrc                  # direnv auto-activation (optional)
uv.lock                 # uv lockfile (when uv migration lands)
```

### Example `mise.toml`

```toml
[tools]
python = "3.12"
node = "22"
# Future: claude, just, uv themselves can be mise-managed too
```

### Example `justfile` skeleton

```just
default:
    @just --list

setup:
    mise install
    uv sync --extra dev --extra serve
    cd frontend && npm ci && npm run build
    just symlink-binaries

verify:
    @python -c "import sqlalchemy, fastapi, pytest" && echo "✓ extras"
    @bristlenose --version > /dev/null && echo "✓ CLI"
    @bristlenose doctor 2>&1 | tail -5
    @test -f bristlenose/server/static/index.html && echo "✓ frontend bundle"
    @test -d desktop/Bristlenose/Resources && python -c "from bristlenose.utils.bundled_binary import resolve_bundled_binary; assert resolve_bundled_binary('ffmpeg') and resolve_bundled_binary('ffprobe')" && echo "✓ desktop binaries"

symlink-binaries:
    @MAIN="$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')"; \
    for path in ffmpeg ffprobe models; do \
        src="$MAIN/desktop/Bristlenose/Resources/$path"; \
        dst="desktop/Bristlenose/Resources/$path"; \
        [ -e "$src" ] && [ ! -e "$dst" ] && ln -s "$src" "$dst" && echo "✓ $path" || true; \
    done

fetch-ffmpeg:
    desktop/scripts/fetch-ffmpeg.sh

build-sidecar:
    desktop/scripts/build-sidecar.sh

build-desktop:
    desktop/scripts/build-all.sh

test:
    .venv/bin/python -m pytest tests/

lint:
    .venv/bin/ruff check .
```

### What `/new-feature` becomes

Steps 1–4: unchanged (validate name, location, kind; create branch + worktree; seed handoff).

Steps 5–8 collapse to:
```bash
mise install      # ensures correct Python/Node
uv sync --extra dev --extra serve
cd frontend && npm ci && npm run build
just symlink-binaries
just verify
```

Step 9 (`BRANCHES.md` update), step 10 (commit) unchanged.

The skill *shrinks* by maybe a third. Drift detection is automatic — `mise install` and `uv sync` both tell you when their inputs (`mise.toml`, `pyproject.toml`, `uv.lock`) have changed.

## Adoption sequence

Each phase is independently shippable. Don't land all at once.

### Phase 0 — narrow patch (in-flight)

Land the `new-feature-binary-symlinks` branch: extend skill Step 9 to symlink ffmpeg/ffprobe/models from main, add Step 8 probe via `bundled_binary.resolve_bundled_binary`. ~25 lines. Patches today's hole. Doesn't depend on any off-the-shelf tool.

### Bootstrap (per-developer, one-time)

Before any of the post-Phase-0 phases helps a contributor, they need the tools installed. One line in `INSTALL.md` (or this doc's prerequisites section, when Phase 1 lands):

```bash
brew install mise just uv
```

`direnv` (Phase 4) is `brew install direnv` if/when adopted.

### Phase 1 — `mise` adoption

Add `mise.toml` at repo root:
```toml
[tools]
python = "3.12"
node = "22"
```

Document in root `CLAUDE.md` that `mise install` is the canonical way to get the right tool versions. `/new-feature` Step 6 grows a `mise install` line before the venv create.

Cost: minutes. Value: one fewer place to update Python version.

### Phase 2 — `just` adoption

Add `justfile` at repo root with the tasks shown above. Existing `desktop/scripts/*` stay where they are; just provides a discoverable index. CI (`release.yml` etc.) can call `just verify` instead of bespoke probe sequences.

**Probe taxonomy for `just verify` (rescued from the prior over-scoped plan).** When a `verify` probe gets added in Phase 2 or later, place it under one of these categories so the task stays organised. Don't ship them all at once — add each only when its absence has caused a real incident:

- *Python deps* — extras importable
- *CLI* — `bristlenose --version` exits clean
- *Doctor* — `bristlenose doctor` passes
- *Frontend bundle* — `bristlenose/server/static/index.html` + `assets/` present
- *Desktop binaries* — `bundled_binary.resolve_bundled_binary("ffmpeg"/"ffprobe")` returns a path (Phase 0 ships this one)
- *Bundle manifest parity* — codebook YAML + LLM prompt MDs present (mirrors `desktop/scripts/check-bundle-manifest.sh`)
- *Port uniqueness* — `.claude/launch.json` port doesn't collide with another worktree (existing E2E gotcha)
- *Migrations* — `alembic check` if Bristlenose adopts Alembic; today migrations are hand-rolled in `db.py` so this probe is dormant
- *Locales* — `bristlenose/locales/*.json` count matches the canonical 6

Each gets its own `@echo "✓ <category>"` line. The list isn't a manifest to ship; it's a parking lot.

`/new-feature` Steps 6–8 become `mise install && just setup && just verify`.

Cost: hour or two to extract + verify task parity. Value: one place to add new probes/setup steps; `just --list` is the contract.

### Phase 3 — `uv` migration

Replace `pip install -e '.[dev,serve]'` with `uv sync --extra dev --extra serve` (or `uv sync --all-extras` once we model the extras). Add `uv.lock` to repo. Faster CI. Wheel hash pinning falls out (already on the roadmap).

Cost: half-day; needs CI parity check. Value: 10–100× faster venv creation across worktrees.

### Phase 4 (optional) — `direnv`

Auto-activate venv on `cd` into worktree. Removes one source of "I forgot to source the venv" bugs. Pure ergonomics.

Cost: minutes per developer. Optional; not required for any other phase.

## Drift detection — falls out, doesn't need invention

Once Phase 1+2+3 land, the original "how does `/new-feature` know it's behind?" question dissolves:

- New tool added (e.g. Bun)? `mise.toml` updates → `mise install` in worktree complains → developer runs `mise install` → done.
- New Python dep added? `pyproject.toml` updates → `uv.lock` updates → `uv sync --check` in CI fails → PR blocked until lockfile rebuilt → worktree's `uv sync` updates venv.
- New task needed? `justfile` updates → it's just there.
- New gitignored binary class? `just symlink-binaries` (or whatever task) updates in one place.

No fingerprint file. No drift detector. The toolchain *is* the drift detector.

## What this doc isn't

- A timeline. Phases land when they land.
- A mandate. If `mise` falls out of fashion in 2027, swap it. The principle (don't hand-roll) survives the choice.
- A blocker for the Phase 0 narrow branch. Phase 0 ships independently.

## Risks / open questions

- **`mise` learning curve.** Low — single-file declaration, brew-installable. But every new tool is friction during the alpha sprint. Defer Phase 1+ until post-TestFlight if it competes for attention.
- **`uv` ecosystem maturity.** It's stable; FastAPI itself uses it. Lockfile format isn't yet standardised across tools (PEP 751 in flight). Migration is reversible.
- **`just` requires another tool.** Adopters need `brew install just`. `mise` can install it (`mise.toml`: `just = "1.x"`), so once Phase 1 lands this is one line.
- **Codesigning vs symlinks.** Resolved at Phase 0 verification — Xcode's Copy Resources phase resolves symlinks before signing, so the signed .app contains real bytes. If verification fails, Phase 0 falls back to copy and downstream phases inherit that choice.
- **Cloud Code VMs (Ubuntu, ephemeral).** `mise` and `uv` work on Linux. `just` works on Linux. No regressions.

## Cross-references

- `.claude/skills/new-feature/SKILL.md` — current skill that this doc proposes to slim down
- `desktop/scripts/build-all.sh` — the project-specific 5% that stays
- `bristlenose/utils/bundled_binary.py` — the resolver Phase 0's smoke probe calls

Established 6 May 2026 after the `sandbox-mimetypes-init` walk surfaced ffmpeg/ffprobe as gitignored-binary drift, and a usual-suspects pass on the immediate fix told us to stop reinventing dev tooling.
