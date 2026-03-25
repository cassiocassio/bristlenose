# Miro Bridge — Design Document

One-way export from Bristlenose to Miro boards. Creates spatial boards with grouped sticky notes from analysis data.

**Status:** M1 complete (token management, 47 tests). M2-M7 planned for post-beta (v1.0).

---

## Context

Bristlenose is the preprocessor. It chews through 10 hours of interview recordings and hands the researcher structured, tagged, timestamped quotes. The researcher takes those into Miro where the actual synthesis happens with the team — arranging evidence, building insights, having the conversations that turn data into decisions.

Nobody does the Miro bridge well. Researchers build their Miro boards by hand, every time, for every project. Automating this would genuinely differentiate Bristlenose.

**Product positioning:**
- **Near-term:** Bristlenose is the preprocessor. The HTML report is the researcher's private workbench. The deliverable lives in Miro. The bridge serves this story.
- **Further-out:** The Bristlenose report itself becomes rich enough to be the shareable deliverable (video clips, charts, curated quotes). The bridge remains valuable for team synthesis.

**Competitive context:** Dovetail costs ~$20,000/year for a team. Everyone can live-tag the same research session. But the output still gets arranged in Miro for stakeholder synthesis. Bristlenose can't match real-time collaboration, but it can match (or beat) the speed of going from recordings to arranged evidence in Miro — and do it for free.

**Launch story:** Tier 1 (Miro-shaped CSV) ships for free with the quotes export feature. The full API integration (M2-M7) is the "rabbit out of the hat" for v1.0 — designed, M1 shipped, impressive when it lands.

---

## Three tiers of integration

### Tier 1: Miro-shaped CSV (ships with quotes export, no API)

A CSV formatted so that when dragged onto a Miro board, the sticky notes land with useful structure. Miro imports CSV as sticky notes with configurable field mapping.

This ships for free with the quotes CSV export (see `docs/design-export-quotes.md`). Same 11 columns, same data. The researcher drags the CSV onto a Miro board and maps fields to sticky note properties.

**No separate implementation needed.** The quotes export IS Tier 1.

### Tier 2: OAuth API integration (M2-M7)

`bristlenose export --miro` or a button in the serve-mode UI that pushes curated quotes directly to a Miro board via the Miro REST API.

**What it creates:**
- Sticky notes for quotes (text, colour-coded by sentiment or theme)
- Frames for themes/sections
- Tags mapped from Bristlenose tags
- A legend frame explaining the colour scheme

### Tier 3: Intelligent layout engine (aspirational)

Not just placing stickies on a board, but laying them out with the spatial intelligence of an experienced researcher:
- Stacking similar quotes (overlapping stickies for redundant evidence)
- Variable sizing by text volume
- Colour semantics consistent across sentiment, participant, or theme
- Proximity = relatedness (co-occurring quotes sit closer)
- Evidence density visualisation (themes with more quotes take more board space)

This is essentially a data visualisation problem — mapping structured research data to 2D spatial layout. Warrants its own prototyping phase with 3-5 hand-crafted gold-standard boards.

---

## What exists today (M1 — DONE)

- `bristlenose/miro_client.py` — token validation via `GET /v2/boards?limit=1`
- `bristlenose/server/routes/miro.py` — status/connect/disconnect endpoints
- `bristlenose/credentials.py` + `credentials_macos.py` — keychain storage
- `bristlenose/config.py` — `miro_access_token` field
- `bristlenose/cli.py` — `bristlenose configure miro` with validation
- 47 tests passing
- OAuth app registered in Miro (Draft status) with `boards:read`, `boards:write`, `identity:read` scopes

---

## Design

### OAuth flow (M2)

**Use PKCE instead of client_secret.** More secure, better for local apps.

**Auth model:** OAuth 2.0. Access tokens expire in 1 hour; refresh tokens last 60 days. The serve-mode UI handles the OAuth flow; CLI `configure miro` accepts a pasted token as fallback.

**Flow:**

1. Frontend calls `GET /api/miro/auth-url` — gets the Miro authorization URL
2. Browser opens Miro OAuth page
3. User authorises
4. Miro redirects to `http://localhost:{port}/api/miro/callback`
5. Callback exchanges code for tokens (`POST https://api.miro.com/v1/oauth/token`)
6. Access + refresh token stored in keychain
7. Redirect to report with success indicator
8. Frontend polls `/api/projects/{id}/miro/status` to detect new connection

**Security:**
- State parameter: random UUID stored in-memory, validated on callback (CSRF protection)
- Token refresh: automatic before each API call (if token age > 50 min)
- Disconnect deletes both access and refresh tokens
- Client ID is build-time config (`.env`), not user-facing. **No client_secret** — PKCE replaces the shared secret at token exchange with a per-session `code_verifier`/`code_challenge`
- **Document Miro as sub-processor in `SECURITY.md`** — data leaves the user's machine when pushing to Miro

### Board creation and stickies (M3)

**Miro API v2 endpoints used:**

| Endpoint | Purpose |
|----------|---------|
| `POST /boards` | Create a board |
| `POST /boards/{id}/sticky_notes` | Create sticky notes (bulk: 20 per call) |
| `POST /boards/{id}/frames` | Create frames (containers) |
| `POST /boards/{id}/tags` | Create tags |
| `POST /boards/{id}/connectors` | Create connectors (future) |

**Sticky note properties:**
- `data.content` — text (supports `<b>`, `<i>`, `<a>`)
- `style.fillColor` — background colour
- `position.x`, `position.y` — board coordinates
- `geometry.width`, `geometry.height` — sticky size

**Rate limits:** 1,000 creates/minute. Bulk create: 20 items per call. Exponential backoff on 429 responses.

### Colour mapping

Miro's 16 fixed colours mapped to Bristlenose sentiments:

| Sentiment | Miro colour |
|-----------|-------------|
| positive | light_green |
| negative | light_pink |
| neutral | light_gray |
| mixed | light_yellow |
| frustrated | red |
| delighted | green |
| confused | light_blue |

For codebook groups (tag colouring), cycle through remaining colours.

### Sticky content format

```html
<b>P1</b> 01:23<br>"Quote text here"
```

- Participant code (bold) + timecode + quote text
- Tags shown via Miro tags feature (not in sticky text)
- Edited quotes: export the edited version
- Hidden quotes: excluded (respect `.bn-hidden` flag)
- Long quotes: truncated at 300 chars with "..."

### Layout algorithm (M4 grid-by-group, M7 refinements)

**M4 — basic grid:**

```
Board
├── Legend frame (top-left) — colour key, project name, export date
├── Section/Theme 1 frame
│   ├── Sticky (row 0, col 0) — highest intensity
│   ├── Sticky (row 0, col 1)
│   └── ...
├── Section/Theme 2 frame
│   └── ...
└── ...
```

- Frames: 2-column layout, N/2 rows
- Frame width: 1200px, height auto (based on sticky count)
- Stickies: 4-column grid inside each frame, 20px gap
- Sticky size: 199x228 (Miro default)
- Sort within frame: by intensity (highest first) then participant

**M7 — spatial refinements:**
- Variable frame sizing based on quote count
- Within-frame sub-clusters by tag group
- Sentiment spatial hints (positive top-left, negative bottom-right — soft bias)
- Intensity sizing (high-intensity quotes get 228x228 vs 199x199)
- Cross-participant alignment across frames

**Will NOT do:** auto-rearranging existing board content, AI-driven clustering (pipeline clusters already exist), automatic connections/arrows.

### Export config

```python
class MiroExportConfig(BaseModel):
    board_name: str | None = None          # Default: project name + timestamp
    scope: Literal["all", "section", "theme"] = "all"
    section_filter: str | None = None
    theme_filter: str | None = None
    colour_by: Literal["sentiment", "participant"] = "sentiment"
    include_tags: bool = True
    include_legend: bool = True
```

### Consent UI

Before pushing to Miro, show a consent step with:
- Quote count being exported
- Destination (new board name)
- Reminder that data will leave the user's machine
- "Export to Miro" confirmation button

### React export panel (M5)

Modal triggered from the export dropdown. States:

1. **Not connected:** "Connect to Miro" button (opens OAuth)
2. **Connected:** Config form (board name, scope, colour by, tags, legend)
3. **Exporting:** Progress bar + cancel button
4. **Done:** Board link + "Open in Miro" button
5. **Error:** Error message + retry button

### Background job

Uses `asyncio.create_task` pattern (same as AutoCode):
- Progress: `(items_created, total_items)`
- Job state: in-memory (not DB — ephemeral)
- Cancel support via `asyncio.Event`

---

## Implementation milestones

### M1: Token management — DONE

Already shipped. 47 tests passing.

### M2: OAuth 2.0 flow

| File | Change |
|------|--------|
| `bristlenose/server/routes/miro.py` | Add `auth-url`, `callback`, `refresh` endpoints |
| `bristlenose/miro_client.py` | Add `exchange_code_for_tokens()`, `refresh_access_token()`, `get_user_info()` |
| `bristlenose/credentials.py` | Add `"miro_refresh"` key |
| `bristlenose/config.py` | Add `miro_client_id` (from `.env`). No `client_secret` — PKCE eliminates it |
| `tests/test_miro_client.py` | Token exchange, refresh, user info tests |
| `tests/test_serve_miro_api.py` | Auth-url, callback, CSRF state validation tests |

### M3: API client — boards, frames, stickies

| File | Change |
|------|--------|
| `bristlenose/miro_client.py` | `create_board()`, `create_frame()`, `create_stickies()` (bulk), `create_tag()`, `attach_tags()` |
| `tests/test_miro_client.py` | Board/frame/sticky creation, bulk batching, rate limit retry, colour mapping (~15 tests) |

### M4: Export service — quote selection, layout, background job

| File | Change |
|------|--------|
| `bristlenose/server/miro_export.py` | **New.** `export_to_miro()` orchestration + layout computation |
| `bristlenose/server/routes/miro.py` | `POST/GET /export`, `POST /export/cancel` endpoints |
| `tests/test_miro_export.py` | **New.** Layout, sticky content, batch sizing, progress (~25 tests) |

### M5: React export panel

| File | Change |
|------|--------|
| `frontend/src/islands/MiroExportPanel.tsx` | **New.** Modal with 5 states |
| `frontend/src/islands/MiroExportPanel.test.tsx` | **New.** Render states, API mock (~12 tests) |
| `frontend/src/utils/api.ts` | Miro API functions |
| `frontend/src/utils/types.ts` | Miro types |

### M6: Content formatting and metadata

- Rich sticky content (participant code bold, timecode, topic label)
- Legend frame (colour key, project name, date, version, total quotes)
- Edited quote handling, hidden quote exclusion
- ~10 tests

### M7: Layout refinement

- Variable frame sizing, within-frame sub-clusters, sentiment spatial hints
- Intensity sizing, cross-participant alignment
- ~8 tests

**Estimated total: ~70 new tests across M2-M7.**

---

## Decisions

1. **OAuth 2.0 with PKCE, not personal access tokens only.** Smoother UX, token refresh, future distribution.
2. **One-way push only.** Miro killed webhooks Dec 2025. Sync back is neither possible nor desirable. The spatial arrangement IS the analysis — the researcher controls it.
3. **New board per export.** Never modify existing boards. Learned from "magic organize" horror stories.
4. **No auto-rearranging.** The spatial arrangement is the analysis; researcher controls it.
5. **Sentiment colouring default.** 7 sentiments map cleanly to Miro's 16 colours.
6. **Grid-by-theme layout.** One frame per section/theme, stickies in grid inside. Simple and useful.
7. **Client ID in `.env`.** Build-time config, not user-facing. No client_secret needed (PKCE).
8. **Refresh token in keychain.** Separate from access token for independent lifecycle.
9. **HTML in stickies.** Miro supports `<b>`, `<i>`, `<a>` — enough for participant + timecode formatting.
10. **Background job, not synchronous.** Export takes 10-30s; follows AutoCode async pattern.
11. **Document as sub-processor.** Data leaves the user's machine — this must be clear in `SECURITY.md` and the consent UI.

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| Miro API rate limiting | Bulk create (20/call), exponential backoff |
| Token expiry mid-export | Refresh before starting, check during long exports |
| Board sluggish with >5K items | Warn user, suggest section-scoped export |
| OAuth redirect URI mismatch | Exact match required — use consistent port |
| Miro kills more APIs | One-way push is minimal surface area |
| Sticky content too long | Truncate at 300 chars |

---

## Open questions

1. **Colour by: sentiment vs participant vs theme?** Sentiment is the default. Researchers have strong preferences. The config exposes the choice. May need user research.
2. **FigJam support?** Miro is dominant in UX research. FigJam is growing. Layout logic would be similar but APIs differ. Start with Miro, add FigJam if there's demand.
3. **Video links on stickies?** Miro supports `<a>` tags. Could link to timecoded video — but `file://` only works on the researcher's machine, and `localhost:PORT` dies when the server stops. For now: timecodes as text, not links.
4. **Board layout strategy refinements?** Grid-by-theme is the M4 default. Radial, force-directed, and other layouts are Tier 3 territory.

---

## Verification

1. Connect to Miro via OAuth — verify token stored, status shows connected
2. Disconnect — verify both tokens removed
3. Export to Miro with default settings — verify board created with frames and stickies
4. Verify sticky content: participant code bold, timecode, quote text
5. Verify colour mapping: sentiments get correct Miro colours
6. Verify frame layout: one frame per section/theme, stickies in grid
7. Verify legend frame: colour key, project name, date
8. Test with >200 quotes — verify rate limiting handled (no 429 errors)
9. Test cancel during export — verify job stops, partial board left in Miro
10. Test token refresh — verify automatic refresh before API calls
11. Test consent UI — verify quote count and destination shown before export
12. `pytest tests/` + `ruff check .`

---

## Related docs

- `docs/design-export-quotes.md` — CSV/XLS export (Tier 1 = Miro-shaped CSV)
- `docs/design-export-html.md` — HTML report export
- `docs/design-export-clips.md` — video clip extraction
- `docs/design-export-sharing.md` — original monolith (superseded, kept for git history)
- `SECURITY.md` — document Miro as sub-processor
