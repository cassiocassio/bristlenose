# Miro Bridge — Design Document

One-way export from Bristlenose to a Miro board: a first-draft research wall of
sticky notes, grouped by section and theme, that a team rearranges to do
synthesis. Bristlenose is the preprocessor; Miro is where the conversation
happens.

**Status:** M1 shipped (token validation + connect/disconnect, paste-token only).
Layout engine + cross-app flow designed and prototyped this cycle (see
_Artefacts_). M2 onward not yet built.

---

## Context

Bristlenose chews through hours of interview recordings and hands the researcher
structured, tagged, timestamped quotes. Today the researcher rebuilds a Miro
board by hand, every project, every time. Automating that first draft is a
genuine differentiator: nobody does the Bristlenose→Miro handoff well.

**Why Miro, and why first.** The market read this cycle (market research, this
design cycle — not yet a standalone doc) is consistent: among _dedicated user
researchers_ — the people who systematically analyse
quotes — Miro is the incumbent synthesis surface (research-specific templates,
affinity/clustering features, the "research hub" positioning). FigJam leads the
_designer_ population, riding Figma's installed base, and treats research as
adjacent to design. Our market is the researcher, not the designer who wings
analysis — so Miro-first is not just preference, it's where the users are.

It's also where the API cooperates. Miro has a clean external-push REST API and
an official Python client; FigJam has no equivalent (REST is read-only for file
content; authoring needs an in-editor plugin or the beta MCP write-to-canvas
path). See _Reference: platform facts_.

**Product arc.**
- _Near-term:_ Bristlenose is the preprocessor; the HTML report is the private
  workbench; the deliverable lives in Miro. The bridge serves this story.
- _Further-out:_ the Bristlenose report itself becomes rich enough to be the
  shareable deliverable (clips, charts, curated quotes). The bridge stays
  valuable for team synthesis.

---

## Architecture: a target-agnostic layout IR

The central decision. The hard, valuable part is **layout** — turning grouped
quotes into a spatial arrangement a researcher would actually keep — not the API
plumbing. So we separate them:

```
quotes + clusters (sections, themes; scoped: all / starred / section)
        │
        ▼
   Layout engine          ← the project. pure function, no network.
        │                   decides frames, sticky positions, colour
        ▼
   Board IR               ← frames + stickies + text items, in board coords
        │
        ├──► SVG renderer  ← fast local iteration (the POC)
        └──► Miro renderer ← thin IR→REST translator (miro_api)
            (└──► FigJam renderer — only if demand; a second thin adapter)
```

Consequences:
- We iterate "is this board useful?" against the SVG in milliseconds, never
  burning Miro API calls or dev-team boards.
- The Miro renderer is a dumb translator once the IR is right.
- **"Support both" becomes a renderer swap, not a second project** — the layout
  engine and IR are shared; only the per-target adapter differs. This is the
  honest answer to the recurring FigJam question.

Three conceptual tiers still hold: **Tier 1** = Miro-shaped CSV (ships free with
quotes export — the user drags it onto a board); **Tier 2** = this API push;
**Tier 3** = intelligent spatial layout (endgame).

---

## Plan

### So far (done)

- **M1 — token plumbing.** `validate_miro_token()` (a `GET /v2/boards?limit=1`
  probe), `status`/`connect`/`disconnect` routes (paste-token model, _not_ OAuth
  yet), keychain storage, `miro_access_token` config. ~17 tests across two files.
  An app is registered in Miro (Draft) with `boards:read`/`boards:write`. **No
  board has ever been created** — everything below M1 is design, not code.
- **Research + design (this cycle).** Market read (Miro is the researcher
  surface); API feasibility (Miro REST + official `miro_api` Python client is the
  right surface; _not_ the MCP server; FigJam structurally awkward); the platform
  facts in _Reference_ below; the sticky-formatting limits.
- **Layout POC.** A target-agnostic board IR, a trivial v0 layout engine, and an
  SVG/HTML renderer (`experiments/board-layout-poc/`). Produces two named frames
  (Sections, Themes), each column led by a pale-pink header sticky over yellow
  quote stickies in session→time order, attribution italic. Phone-friendly HTML
  output. Judged "good enough as a POC — even at 500 stickies a real time-saving
  head start."
- **Flow + setup UX.** Storyboard of the cross-app journey and the first-run
  "key dance" (`docs/mockups/miro-flow.html`), and a setup help page
  (`docs/mockups/miro-setup-help.html`).

### Next (the build, in order)

The ordering is deliberate: **OAuth first**, because first-run auth friction (the
"key dance") is the biggest adoption barrier, not the layout.

| Milestone | What | Why this order |
|---|---|---|
| **M2 — OAuth Connect** | Browser-based OAuth 2.0 + PKCE, keychain refresh, state-dependent Export menu (`Connect to Miro…` → `Send to Miro board…`). Paste-token demoted to fallback. | Collapses the key dance from a 6-step developer detour to one click. Highest leverage. |
| **M3 — API client** | Via `miro_api`: `create_board`, `create_frame` (named Sections/Themes), bulk `create_stickies` (parented into frames), `create_text` (title/legend), `create_tag`/attach. Rate-limit backoff. | The thin IR→REST translator. |
| **M4 — Export service** | Port the POC IR + layout engine into `bristlenose/`. Scope = **all / starred / section** (reuses `export_core` `quote_ids` + `is_starred`). Background job (AutoCode async pattern), consent step. | The layout value, wired to real data + selection. |
| **M5 — React panel** | The flow states: not-connected → connecting → configure/consent → exporting → done (`Open in Miro`). | Surfaces M2–M4 in the report UI. |
| **M6 — Content + metadata** | Rich sticky content (participant + timecode italic), legend text item, edited-quote handling, hidden-quote exclusion. | Polish. |

### Endgame (aspirational)

- **Tier 3 — intelligent layout.** Spatial intelligence of an experienced
  researcher: evidence density → frame size, stacking redundant quotes, variable
  sticky sizing by intensity, proximity = relatedness, soft sentiment spatial
  bias. A data-viz problem; warrants its own prototyping phase against 3–5
  hand-crafted gold-standard boards.
- **FigJam as a second renderer** — only if researcher demand appears. Two
  shapes, both worse than Miro's clean push: (A) a published FigJam plugin that
  consumes a JSON manifest Bristlenose exports (stable, but a human runs it
  in-editor); (B) the remote MCP `use_figma` write-to-canvas (beta, future-paid,
  Full-seat, OAuth-only, generates Plugin-API JS). Shared layout engine; thin
  adapter either way.
- **Report-as-deliverable.** As the Bristlenose report grows richer, the bridge
  shifts from "the deliverable" to "team synthesis accelerator."

### Artefacts

| Artefact | Path | State |
|---|---|---|
| Token client | `bristlenose/miro_client.py` | M1 (validation only) |
| Server routes | `bristlenose/server/routes/miro.py` | M1 (status/connect/disconnect) |
| Config / keychain | `bristlenose/config.py`, `credentials*.py` | M1 |
| Tests | `tests/test_miro_client.py`, `tests/test_serve_miro_api.py` | ~17 |
| **Layout POC** | `experiments/board-layout-poc/` | this cycle |
| — board IR | `board_model.py` | Frame / Sticky / TextItem / Board |
| — layout engine | `layout.py` | trivial v0 |
| — SVG/HTML renderer | `render_svg.py` | + phone wrapper |
| — runner + sample | `run.py`, `sample-board.svg/.html` | smoke-fixture render |
| Flow storyboard | `docs/mockups/miro-flow.html` | mockup |
| Setup help | `docs/mockups/miro-setup-help.html` | mockup |

---

## Reference: platform facts (verified this cycle)

The hard-won constraints. Build against these.

### Auth & client
- **OAuth 2.0 + PKCE, no Marketplace publishing.** Create an app, install it to a
  Developer team directly. One-time browser consent on first run is the only
  irreducible friction; refresh tokens keep it headless after.
- **Official Python client `miro_api`** (PyPI, Python 3.9+ — fits Bristlenose).
  Stateless `MiroApi` (token in) is the right fit for a batch exporter; it
  auto-refreshes. Add as optional extra `bristlenose[miro]`.
- **Use REST, not the MCP server.** Miro's MCP server (public beta, Dec 2025) is
  a remote OAuth-2.1, AI-assistant-oriented surface exposing a REST _subset_. The
  REST API is the deterministic, scriptable batch surface we want. Revisit MCP
  only for a future "chat with your board" feature.
- Free Developer team keeps only the **3 most-recent boards editable** — use a
  paid team or don't auto-spawn many boards.

### Positioning, frames, text
- **Stickies:** absolute `position` x/y + `geometry` w/h. A sticky can be
  `parent`-ed into a frame — then its x/y are **relative to the frame's top-left
  and mark the sticky's centre**. No server-side auto-layout (we compute it).
- **Frames are named containers** (`data.title` = the label, shown as a tab),
  positionable + sizable, with a `style.fillColor`. **Frames don't nest**, and an
  item belongs to **at most one** frame — so "a Sections frame and a Themes
  frame" with columns inside is correct; per-column sub-frames are impossible.
  Frames don't auto-grow — size to the computed grid.
- **Text items are richer than stickies:** `style.fontSize`, `style.color`,
  `<span style>`. Use them for the board title / legend, where real typographic
  hierarchy is wanted.

### Sticky text formatting (all-or-nothing)
- `data.content` supports only: `<p> <a> <strong>/<b> <em>/<i> <u> <s> <br>`.
- **`<span>` is NOT supported** — silently escaped and rendered as literal
  `<span…>` text on the board. Silent-failure trap; stay in the allowlist.
- **No per-span font size or colour.** No `style.fontSize`; font is **auto-fit**
  (Miro scales the whole note to its box). Only colour control is
  `style.fillColor` (background, 16 named colours) — there is no text-colour field.
- `style` has exactly three fields: `fillColor`, `textAlign`, `textAlignVertical`.
- Content cap **< 6000 chars** (failure mode at the boundary undocumented).
- **Implication:** a prominent quote + a smaller/greyer attribution _inside one
  sticky_ is impossible. The only de-emphasis a sticky affords is `<i>`. For true
  hierarchy you'd need a separate text item (costs a second item per quote). v0
  uses italic attribution — pragmatic, keeps one item per quote.

### Rate limits
- Credit-based, 100k credits/min account ceiling; mutations are heavy-weight
  calls. **Bulk create: 20 items/call, mixed types, but no connectors** (and tag
  attach is a separate call). 429 → exponential backoff via `X-RateLimit-*`
  headers. A few-hundred-sticky board is trivially within limits.
- Recommended soft cap ≤ 10,000 items/board.

---

## Layout mapping (IR → Miro)

| IR element | Miro primitive | Notes |
|---|---|---|
| Sections / Themes group | **Frame**, `title` = "Sections" / "Themes" | two big named containers, sections left, themes right |
| Column (one section or theme) | column of stickies inside the frame | led by a header sticky (no sub-frame — frames don't nest) |
| Column title | **pale-pink header sticky** | the natural Miro affordance; label + count |
| Quote | **yellow sticky**, parented into the frame | body leads; `— P1 · 0:10` trails in italic |
| Board title / colour legend | **text item** | real fontSize/colour |

- **Order:** sections (by `display_order`) then themes — same as the Quotes page.
- **Within a column:** session→time (`session_id` natural sort, then
  `start_timecode`).
- **Scope:** `all` (non-hidden) / `starred only` / `this section` — reuses the
  existing `export_core` `quote_ids` selection and `QuoteState.is_starred`.
- **Colour:** sentiment by default (Bristlenose's 7 sentiments → Miro's 16 named
  colours); participant/theme optional.

### Sentiment → Miro colour

| Sentiment | Miro colour |
|-----------|-------------|
| positive / delight | light_green / green |
| negative / frustration | light_pink / red |
| neutral | light_gray |
| mixed | light_yellow |
| confusion | light_blue |

(Quote stickies default to yellow when not colouring by sentiment; header
stickies are pale pink.)

---

## Cross-app flow & setup (the adoption surface)

The make-or-break is the journey across two apps and getting past first-run
setup, not sticky detail. Design goals: **cross the app boundary as few times as
possible; never make someone do setup twice.**

- **The menu encodes state.** Export popover shows `Connect to Miro…` when
  disconnected (routes to consent) and `Send to Miro board…` once connected
  (jumps to configure).
- **First run** crosses the boundary twice (consent out + auto-return). **Every
  run after** crosses once (the final `Open in Miro`). Consent never reappears —
  token + refresh live in the keychain.
- **No dead-ends:** the browser handoff sets the expectation ("come back here"),
  the return is automatic via localhost callback, the finish gives one obvious
  `Open in Miro` button.
- **Consent + privacy** stated at the moment of action: quote count shown, data
  leaves the machine, hidden quotes excluded. Miro is a sub-processor — document
  in `SECURITY.md`.

See `docs/mockups/miro-flow.html` and `miro-setup-help.html`.

---

## OAuth flow (M2 detail)

1. Frontend gets the authorize URL (`GET /api/miro/auth-url`).
2. System browser opens Miro's consent page.
3. User clicks **Allow**.
4. Miro redirects to `http://localhost:{port}/api/miro/callback`.
5. Callback exchanges the code for tokens (PKCE — no client secret).
6. Access + refresh tokens stored in keychain.
7. Report shows Connected; menu flips to `Send to Miro board…`.

Security: random-UUID `state` validated on callback (CSRF); auto-refresh before
calls when token age > 50 min; disconnect deletes both tokens; client ID is
build-time `.env`, not user-facing. Paste-token remains a fallback for orgs that
block third-party app authorisation.

---

## Decisions

1. **Layout IR decoupled from target.** The engine produces a renderer-agnostic
   board model; Miro/FigJam/SVG are thin renderers. Makes "support both" cheap.
2. **Miro first, structurally** — it's where researchers synthesise _and_ the
   only target with a clean external-push API. FigJam is endgame, demand-gated.
3. **REST, not MCP**, for the deterministic batch export.
4. **OAuth before layout polish** — first-run friction is the real barrier.
5. **One-way push only.** Miro retired webhooks (Dec 2025); the spatial
   arrangement _is_ the researcher's analysis. Never sync back.
6. **New board per export.** Never modify existing boards.
7. **Two named frames** (Sections, Themes); columns inside; **pink header
   stickies** for column titles (frames can't nest).
8. **Italic attribution** inside the quote sticky — the only de-emphasis a sticky
   affords (no per-span size/colour).
9. **Scope reuses starred/filter** — `quote_ids` + `is_starred`, no new machinery.
10. **Background job**, not synchronous (10–30s export).
11. **Document Miro as sub-processor** — data leaves the machine.

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| First-run auth friction (the key dance) | OAuth one-click (M2); paste-token fallback |
| Rate limiting | bulk 20/call, exponential backoff |
| Token expiry mid-export | refresh before start + during long exports |
| Board sluggish > 5k items | warn; suggest scoped (starred/section) export |
| OAuth redirect URI mismatch | exact-match localhost port |
| Sticky content > 6000 chars | truncate (~300 chars for readability anyway) |
| `<span>`/style silently escaped | stay in the tag allowlist; never inject CSS |
| Miro deprecates more APIs | one-way push = minimal surface |

---

## Enhancement: clip links in stickies

The obvious win — each quote sticky links straight to its video clip. Stickies
support `<a href>`, so the link itself is trivial. The only real question is
_where the clip already lives_ — and the answer is **wherever the researcher put
it. Bristlenose references; it never hosts, uploads, or moves participant
video.**

**The real workflow.** A researcher makes meaning out of _dozens_ of clips and
_shares_ maybe five; the handful that matter usually end up embedded in a deck
later, not in Miro. Where the source videos sit is the researcher's / client's
call, driven by access control — Teams/Zoom recordings land in Google Drive,
OneDrive, a corporate network drive, local disk, or iCloud, "depends." Modern
WiFi makes network-drive playback natural.

Two intents follow:
- **Private analysis** (local / iCloud / personal Drive): the videos are for the
  researcher's own sense-making. They don't care about shareable links in Miro —
  the key clips go to the deck later. Clip-links are optional / for their own use.
- **Collaboration** (team shared space with access control): the team has already
  put the videos in a permissioned shared drive. _Those_ are the URLs that belong
  in the board. Bristlenose embeds links pointing into that location; access
  control stays the client's, enforced by their drive — which is more
  privacy-respecting than Bristlenose hosting anything.

**Sequencing discipline (the v1 rule):** put the videos in the right place
_first_, then generate the board. Bristlenose constructs per-clip links at
board-creation time from the location you give it (a base folder link / path) +
the clip filename convention. **v1 does not update links in an already-made
board** — consistent with "new board per export, never modify existing boards."
If the videos move, you make a new board.

**Bristlenose doesn't gatekeep this.** The researcher already knows — from the
client contract, the team's culture, and the infosec rules they work under — what
may and may not be done with these recordings, which came off Zoom in the first
place. Our job isn't to second-guess a professional's governance; it's to link to
the location they point us at. We never host or move the video — placement and
permissions are theirs, and Bristlenose never becomes a hosting sub-processor.
Default stays timecode-as-text — no links, zero config — for when clip links
aren't wanted.

## Open questions

1. **Colour-by default:** sentiment (current default) vs participant vs theme.
   Config exposes the choice; may need user research.
2. **Attribution hierarchy:** accept italic-only (v0), or spend a second text
   item per quote for true smaller/greyer attribution? Decide from tester feel.
3. **Tier 3 layout strategy:** grid-by-column (v0) vs density/force-directed.

---

## Verification

1. Connect via OAuth — token stored, status Connected, menu flips.
2. Disconnect — both tokens removed.
3. Export (default) — new board: two frames, pink headers, yellow quotes.
4. Sticky content — quote leads, italic `— P1 · 0:10` trails.
5. Colour mapping — sentiments → correct Miro colours.
6. Scope — `starred only` exports just starred quotes; `all` excludes hidden.
7. Frame layout — Sections left, Themes right; columns session→time.
8. > 200 quotes — rate-limit backoff, no 429 surfaced.
9. Cancel mid-export — job stops, partial board left.
10. Consent UI — quote count + destination shown before upload.
11. `pytest tests/` + `ruff check .`.

---

## Related docs

- `docs/design-export-quotes.md` — CSV/XLS export (Tier 1 = Miro-shaped CSV)
- `docs/design-export-html.md` — HTML report export (anonymisation)
- `docs/design-export-clips.md` — video clip extraction
- `SECURITY.md` — Miro as sub-processor
- `experiments/board-layout-poc/` — the layout prototype
- `docs/mockups/miro-flow.html`, `miro-setup-help.html` — flow + setup UX
