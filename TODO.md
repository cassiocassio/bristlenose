# Bristlenose — Where I Left Off

Last updated: 11 Jul 2026. _This file is a capture inbox + session context, not a changelog — `git log` + `CHANGELOG.md` are the unabridged record._

**11 Jul 2026 — v0.20.0 shipped (incremental builds).** Curation survives re-analysis (freeze marked quotes, membership-based section identity, star-anchored theme names, dismissible "New" badge); desktop loose-file intake + incremental add (drop / File→Add Files ⇧⌘A) + run recovery; native feedback sheet; sessions-journey deep-links; Shoal adaptive count. Bumped 0.19.0→0.20.0 (feature release = minor bump; convention now in CLAUDE.md). Live on PyPI + brew. **Desktop half reaches the cohort only with the next bundled-sidecar build — not yet done.**

**7 Jul 2026 — Acceptance-testing tier (Phase 1).** All test docs under `docs/testing/` (hub + `coverage-inventory.md`); built format-coverage + invariant harness + lens smoke (`bc5a036a`, folded into 0.20.0). Open: real Teams/Meet `.docx` parity fixture; firing local/cloud provider cells (`run_matrix.py --run-local` free / `--run-cloud` = keys+spend); `launchd` nightly wrapper (Phase 3).

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context — antechamber for untriaged items only; promote to the plan doc once triaged.

---

## Next session focus

Sprint schedule (S1–S6) ended 30 Jun; active focus is the **Critical Path to Internal TF** in `docs/private/100days.md` §Critical Path. Internal TF is gated on the **walks-fix-walks** quality bar — 2–3 consecutive end-to-end walks across different scenarios producing zero new snags — plus a mechanical TF-branch upload (#3 sandbox flip re-apply, #10 ASC record, #12 first upload).

Immediate ladder: (1) **build + sign the bundled sidecar** so 0.20.0's desktop features (incremental add, loose-file intake, feedback sheet) reach the cohort — nothing to walk without it; (2) **walks-fix-walks** on that build; (3) mechanical TF upload. Orthogonal small win: **Opus 4.8 P2** (price the Opus row, current-gen the picker `"Opus 4"→4.8`) — overdue since ~18 Jun, TF-non-blocking; verify the catalogue still says "Opus 4" first.

---

## Ideas (captured, not triaged)

_Inbox empty — all captures triaged into `docs/private/100days.md` (11 Jul 2026), each placed in its topic section at the right MoSCoW tier. New raw captures land here; promote to the plan doc once triaged._

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

**Launch plan:** `docs/private/100days.md` — triaged by topic and MoSCoW priority.

This file contains: session reminders, untriaged captures, dependency maintenance, and reference tables.

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` + `npm audit` on every push (informational, non-blocking). Dependabot opens weekly PRs for both ecosystems. CodeQL SAST runs on push + weekly. See `SECURITY.md` for remediation SLA.

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [x] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind _(prophecy 8 Jun 2026 via Cassandra Entries 1+2; execution 9 Jun 2026: security wave `5c96058` (presidio + cryptography 44→48, cleared 3 OSVs, floor bumped) + graduated-holds wave `e3c0a87` (starlette 1.x pair + WTForms 3.2 pair, dependabot config updated). Cassandra tally 4/4/0. Wave-3 greens deferred — see `docs/private/handoffs/dep-wave-3-greens.md`.)_
- [ ] **Aug 2026** — Same
- [ ] **Nov 2026** — Same

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Check Python EOL dates — Python 3.10 EOL is Oct 2026; if past EOL, bump `requires-python`, `target-version`, `python_version`
  - Check faster-whisper / ctranslate2 project health
  - Check spaCy major version
  - Check Pydantic major version
  - Rebuild snap; review `pip-audit` CI output

### Risk register

| Dependency | Risk | Escape hatch |
|---|---|---|
| faster-whisper / ctranslate2 | High — fragile chain, maintenance varies | `mlx-whisper` (macOS), `whisper.cpp` bindings |
| spaCy + thinc + presidio | Medium — spaCy 3.x pins thinc 8.x | Contained to PII stage; can pin 3.x indefinitely |
| anthropic / openai SDKs | Low — backward-compatible | Floor pins are fine |
| Pydantic | Low — stable at 2.x | Large migration but not urgent |
| Python itself | Low (now) — 3.10 EOL Oct 2026 | Bump floor at EOL |
| protobuf (transitive) | Low — CVE-2026-0994 (DoS); we don't parse untrusted protobuf | Resolves when patched |

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/s12_render/` | HTML report renderer package |
| `bristlenose/theme/` | Atomic CSS design system |
| `bristlenose/theme/js/` | Report JavaScript modules (frozen — static render path only) |
| `bristlenose/llm/prompts/` | LLM prompt templates |
| `bristlenose/doctor.py` | Doctor check logic |
| `frontend/` | Vite + React + TypeScript SPA |
| `.github/workflows/` | CI (ci.yml), release (release.yml), snap (snap.yml) |
| `snap/snapcraft.yaml` | Snap recipe |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **Issues:** https://github.com/cassiocassio/bristlenose/issues
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions

---

## Design docs

| Document | Covers |
|----------|--------|
| `docs/archive/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
| `docs/design-react-migration.md` | **React migration plan** (Steps 1–10, all complete) |
| `docs/design-react-component-library.md` | 16-primitive component library (complete) |
| `docs/design-llm-providers.md` | Provider roadmap |
| `docs/design-performance.md` | Performance audit |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 (**superseded** — see 4 feature docs below) |
| `docs/design-export-slides.md` | Export dropdown (scope→format), per-quote copy icon, PowerPoint quote slides |
| `docs/design-export-quotes.md` | CSV + XLS spreadsheet export (11-column table) |
| `docs/design-export-clips.md` | Video clip extraction via FFmpeg |
| `docs/design-export-html.md` | Self-contained HTML export + cross-cutting export concerns |
| `docs/design-miro-bridge.md` | Miro API integration (OAuth, board creation, layout — post-beta) |
| `docs/design-html-report.md` | HTML report, people file, transcript pages |
| `docs/design-responsive-layout.md` | Responsive layout, density setting, breakpoints |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-serve-doctor.md` | Serve-mode doctor checks, Vite auto-discovery |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-pipeline-resilience.md` | Manifest, event sourcing, resume, provenance |
| `docs/design-logging.md` | Persistent log file, two-knob system |
| `docs/design-test-strategy.md` | Gap audit, Playwright plan, `data-testid` convention |
| `docs/design-desktop-app.md` | macOS app, SwiftUI, PyInstaller sidecar |
| `docs/design-session-management.md` | Re-import, enable/disable, quarantine |
| `docs/design-codebook-island.md` | Migration audit, API design, drag-drop |
| `docs/design-signal-elaboration.md` | Interpretive names, pattern types |
| `docs/design-transcript-editing.md` | Section strike, text correction, prior art |
| `docs/design-speaker-splitting.md` | LLM splitting for single-speaker transcripts |
| `docs/design-speaker-role-detection.md` | Generalised role detection (oral history, journalism, etc.) |
| `docs/design-speaker-editing.md` | Four transcript editing operations (name, reassign, split, merge) |
| `docs/design-transcript-speaker-editing-roadmap.md` | 11-layer work breakdown for transcript + speaker editing |
| `docs/design-sidebar.md` | Dual-sidebar layout (TOC left, Tags right) |
| `docs/design-windows-ci.md` | Windows CI strategy, compatibility audit, phased plan |

