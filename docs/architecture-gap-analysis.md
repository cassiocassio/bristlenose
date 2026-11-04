# ARCHITECTURE.md — gap analysis (4 Nov 2026)

What `docs/ARCHITECTURE.md` said against what the tree holds, layer by layer and mechanism by
mechanism. "Covered" means the doc now names it and points at the owning doc. The owning docs
were not re-trued here; only the map was.

## Layers

| Layer | Before | Now | Owner of the detail |
|---|---|---|---|
| Pipeline core, 12 stages | covered | covered; cloud-LLM stated plainly | `bristlenose/stages/CLAUDE.md` |
| LLM providers | listed | six providers, no vendor default, any-llm | `bristlenose/llm/CLAUDE.md` |
| Serve mode (FastAPI, SQLite) | covered | adds assistant surfaces, export, project identity | `bristlenose/server/CLAUDE.md` |
| React SPA | covered | unchanged | `frontend/CLAUDE.md` |
| macOS app and sidecar | covered | adds the two Swift helpers | `desktop/CLAUDE.md` |
| Model delivery | "planned" | partly built (PII pack handoff only) | `design-modularity.md` |
| Release (CLI and Mac) | partly stale | current verbs, timing rule, freeze, holds, eight channels plus winget | `release.md`, `release-channels.md` |
| Tech stack | absent | addendum | `pyproject.toml`, `frontend/package.json` |

## Mechanisms

| Mechanism | Before | Now |
|---|---|---|
| State stores (files, SQLite, browser, app) | absent | §6 table |
| Run lifecycle: manifest, event log, resume | absent | §6 |
| User-facing status taxonomy | absent | §6 |
| Trust boundary, bearer and scoped MCP tokens, loopback gate | absent | §6 |
| Credentials and Keychain | one paragraph | §6 and §4 |
| Participant-data governance | absent | §6, links consent gradient |
| Assistant surfaces (chat lens, MCP, `.mcpb`) | absent | §2 |
| Codebooks, AutoCode, signals, discussion lens | absent | §6 |
| Screens and OCR, session tapestry, voice pass, Apple Speech | absent | §6 |
| Cloud import (OAuth), Miro, FigJam, exports | absent | §6 |
| Localisation | absent | §6 |
| Design system and theme | one line | §6 |
| Feature gating | absent | §6 |
| Quality gates, ratchets, soft-gate policy | absent | §6 |

## Residual gaps (not closed)

- **Not verified against code in this pass:** the Mac signing-requirements section (only the
  named files were confirmed to exist); the Snap and channel facts come from
  `release-channels.md` (trued 11 Oct 2026) and `snap.yml` triggers.
- **Whisper-model delivery** has no Background Assets code; whether that plan still stands is a
  question for `design-modularity.md` (status `mixed`), not for the map.
- **Windows** (Inno installer, winget) appears only in the tech-stack addendum and the channel
  list. It has no architecture section because no design doc here describes it as a layer.
- **Counts that drift** (locales, tables, migrations, tests) are deliberately not stated except
  the locale directory count; read the tree.
- **The tech-stack addendum duplicates dependency floors** from `pyproject.toml` and
  `package.json`; those files are authoritative.
