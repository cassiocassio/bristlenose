# Miro Bridge — Design Document

One-way export from Bristlenose to a Miro board: a first-draft research wall of
sticky notes, grouped by section and theme, that a team rearranges to do
synthesis. Bristlenose is the preprocessor; Miro is where the conversation
happens.

**Status:** Phase 1 in progress. **End-to-end vertical slice built (23 Jun 2026)
and validated live against a real Miro account (24 Jun)** — board, frames, bulk
stickies, and text all confirmed against Miro's REST API. Now offered as **Send
to Miro** in the SPA export menu, connecting via **paste-token**; **one-click
OAuth is phase 2** (see _Implementation status_ at the foot of this doc).

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
- **Not enterprise-gated.** OAuth + PKCE + expiring/refresh tokens are the
  standard auth for _all_ Miro apps on _every_ plan (incl. free). Only specific
  scopes need Enterprise (`auditlogs:read`, `organizations:*`). Bristlenose uses
  only `boards:read` + `boards:write` — both **standard scopes**, available on
  free accounts; you can even build/test on a free Developer team.
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
- Content cap **< 6000 chars _per sticky_** (not cumulative across the board) —
  a single quote would need ~1,000 words to hit it; never a real constraint (we
  truncate long quotes ~300 chars anyway). The board-level limit that matters at
  scale is **item count** (~10k soft cap), not characters.
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
- **Scope:** whatever the current view resolves to — `all` (non-hidden),
  `starred`, a tag slice, or `this section`. Reuses the existing `export_core`
  `quote_ids` selection (starred / tag filter / hidden-exclusion all collapse to
  a quote-id set).
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
12. **Clip links (opt-in):** linked stickies point to _exported, snipped-out
    clips_ of the quotes on the board — never to the original recording at a
    timecode (which would expose the whole tape). **The board's contents are the
    disclosure boundary**, curated by whatever mechanism (star / hide / tag slice
    / section / all) — Miro consumers reach only those clips, not the video
    between them or what didn't make the cut. The clip is the researcher's
    disclosure boundary: raw video stays proprietary, the interpretation is the
    value, "no you can't have the whole video." Export clips → place them → make
    the board; v1 never updates an existing board's links.

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

The obvious win — each _shared_ sticky links to a short exported **clip**: the
curated, snipped-out moment, never the whole recording. Stickies support
`<a href>`, so the link is trivial. The whole design is about _what_ we link to.

**Why clips, not the raw recording — the researcher's value and control.** The
raw session is proprietary to the researcher. It holds chitchat, unguarded
humanity, off-the-record asides — things you'd never put in front of the boss or
the wider team. The clip is the unit of _curated disclosure_: the researcher
snips exactly the moment worth sharing, nothing before or after, no scrubbing
into the rest. And the researcher's value _is_ the interpretation, not the tape:
"I ran 600 minutes of interviews; these ten clips are emblematic of the challenge
you face; here's my board with the analysis and links to the starred quotes that
define the issue. No, you can't have the whole video — trust me." Handing over
raw footage both leaks the honest bits _and_ invites the boss/team to
re-interpret around the researcher. **The board + the clips + the framing is the
deliverable.** The raw videos stay in the researcher's archive; the research repo
holds the _meaning the team chooses to carry forward_, not the unedited source.

**So: link to exported clips, never to the original at a timecode.** A timecode
deep-link into the full recording exposes the whole tape (scrub anywhere) — the
exact opposite of what's wanted. (This reverses an earlier draft of this doc.)
Bonus: a clip is just a file URL — no `#t=` media-fragment / host start-time
fragility to chase.

**The board's contents are the disclosure boundary — by whatever mechanism.**
Which quotes land on the board is the researcher's curation, and it's
mechanism-agnostic: starring, hiding, a tag slice ("pain from onboarding"), a
section, or all of them. Whatever the board ends up showing, the clips linked
from Miro are _exactly those quotes — and nothing between them_. The researcher
might have exported 1 or 1,000 clips into their own archive; what's reachable
from Miro is only the set they chose to put on the board. That's the whole point:
Miro consumers get the chosen moments, not the connective tissue, not the quotes
that didn't make the cut, not the raw tape. The clip count stays small because
you only link what's on the board, not because "starred" is special.

**Flow.** Curate the board's quote set (any mechanism) → export clips for those
quotes (Bristlenose does this locally — see `docs/design-export-clips.md`) →
place the clips folder wherever the team's access rules say it belongs → make the
board. Bristlenose knows quote→clip-filename (it generated them); the user
supplies the **clips-folder base location** at board time, and each linked sticky
points to `{clips_base}/{clip}`. Bristlenose never uploads or hosts — it exports
clips locally and references the location the user places them in.

**Links are only _live_ with team-accessible, stable URLs.** A clip link works
for the team only if the clips sit at permanent, permissioned URLs — a shared
Drive / OneDrive / SharePoint folder where access is controlled by team
membership and the file IDs don't expire. That's a common corporate setup, so
it's a fair expectation, not a blocker. If the clips stay local/private, the
links resolve only for the author — which is fine, because that mode isn't about
sharing (the key clips go to the deck instead). Bristlenose builds the link from
the base the user gives it; whether that base is genuinely team-reachable is the
researcher's setup to get right.

**In the common case the precondition is already met.** Research wraps up as a
_delivery bundle_ — the board, the deck, the Copilot/playback meeting summary,
and the video-clips folder — dropped into the team Google Drive that every member
(and every day-1 joiner, alongside Slack and Miro) already has. The clips folder
living there _is_ the team-accessible permissioned store; the Miro board simply
links into it. So the perm-URL requirement is usually satisfied by default, not
extra work — the board takes its place in a bundle the team already knows how to
consume.

**Bristlenose doesn't gatekeep placement.** Where the clips folder goes and who
may see it is the researcher's call — governed by their client contract, team
culture, and infosec rules (the footage came off Zoom in the first place; they
already know what's allowed). We don't second-guess a professional's governance;
we link to the location they point us at.

**Opt-in + sequencing (the v1 rule).** Default is timecode-as-text — no links,
zero config. A **"Link quotes to clips"** toggle reveals the clips-folder base
field (which implies you've already exported and placed the clips). Links are
built at board-creation time; **v1 never updates an
already-made board** — new board per export. If the clips move, make a new board.
Nothing to "remember" beyond, optionally, the last-used base as a convenience.

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

---

## Implementation status (experimental, 23 Jun 2026)

An end-to-end slice was built in one session to be playable on a Mac. **Built in
the cloud without a venv / Miro creds**, so: pure layout + preview verified;
server + real Miro push are syntax-checked + typechecked but unrun. Treat as a
first draft for review, not shippable.

### What's built
| Piece | File | Verified |
|---|---|---|
| Layout engine (IR + trivial layout) | `bristlenose/miro_board.py` | ✅ 7 unit tests pass (`tests/test_miro_board.py`) |
| Creds-free SVG/HTML preview | `bristlenose/miro_render_svg.py` | ✅ rendered vs smoke fixture |
| REST client (OAuth/PKCE + board/frame/sticky/text) | `bristlenose/miro_client.py` | ⚠️ syntax only (no httpx in cloud) |
| Export orchestration (quotes→columns→push/preview) | `bristlenose/server/miro_export.py` | ⚠️ syntax only |
| Routes (preview, export, oauth auth-url+callback) | `bristlenose/server/routes/miro.py` | ⚠️ syntax only |
| React panel + state-dependent menu | `frontend/src/components/MiroExportPanel.tsx`, `ExportDropdown.tsx` | ✅ `tsc -b` + `vite build` clean |
| config `miro_client_id`, api.ts, types.ts | — | ✅ typecheck |

### Assumptions (review later)
- **A2** — hand-rolled httpx instead of the `miro_api` SDK (dependency-light;
  swap later).
- **A7** — **synchronous** export, no `MiroExportJob` table/migration (seconds
  for hundreds of stickies). Revisit for very large boards.
- **A9** — stickies placed at **absolute board coords, not parented into
  frames** (frame-relative coord math is the untestable footgun). Frames are
  visual containers; proper parenting once testable.
- **A4** — panel strings hardcoded English; i18n (7 locales) deferred — must do
  before merge (size gate).
- **A11** — scope UI is **all visible quotes** only in v0; the backend already
  takes `quote_ids`, so wiring the current star/tag/section filter → ids is a
  small frontend follow-up.
- **A5** — clip-link filename convention is a guess
  (`{session}-{participant}-{secs}.mp4`); verify against `design-export-clips`.
- **A10** — no token auto-refresh in the export path; if an OAuth token expired,
  reconnect. Paste-token (non-expiring) sidesteps this.
- Miro request shapes (frame `type:freeform`/`format:custom`, sticky
  `shape:square` + named `fillColor`, text `style.fontSize` string, bulk array
  body) are from the verified REST facts but **unrun** — first real push may
  need a tweak.

### Review findings — deferred (flagged, not fixed tonight)
A usual-suspects pass (correctness/security/silent-failure/parsimony) ran against
the slice. Non-contentious fixes applied (see commit "apply non-contentious
review fixes"). Deferred, needing your call:
- **OAuth callback auth wiring.** The callback is under `/api` (bearer-gated) and
  the auth cookie is `SameSite=Strict`, which a browser withholds on the
  cross-site redirect back from `miro.com` — so OAuth likely 401s today. Fix is a
  decision: exempt `/api/miro/callback` from bearer auth (rely on `state`) or move
  the cookie to `SameSite=Lax`. **Not a tonight blocker — paste-token is the
  path.** Don't change auth posture without review.
- **OAuth `state` hardening.** In-memory map has no TTL/size cap; `project_id` is
  captured then discarded (token stored globally). Fine for single-project; revisit
  with multi-project + the callback decision above.
- **Egress governance (pre-ship, not pre-play).** Miro export has no anonymise
  toggle (the HTML export does) and only a one-line consent. Boundary still holds
  (stickies carry speaker codes, not names). Before leaving experimental: add a
  redaction option, an explicit consent checkbox, and a `SECURITY.md` Miro
  sub-processor note.
- **First-push reshaping.** Miro request bodies (bulk array response, frame/sticky
  field names, text position centring) are unrun; expect to tweak on first real
  push. Frontend export error currently shows a generic message and drops the
  server detail (incl. the partial-board URL) — surfacing it needs `apiPost` to
  expose the response body.

### Mac QA (play tonight)
```sh
.venv/bin/python -m pytest tests/test_miro_board.py   # layout engine
cd frontend && npm run build                           # SPA (rebuilds static)
.venv/bin/bristlenose serve --dev trial-runs/<project> # open http://localhost:8150/report/
```
Then: Quotes tab → Export ▾ → **Connect to Miro…**. Fastest path = paste a token
(Miro dev dashboard → app → install → copy token); OAuth needs `MIRO_CLIENT_ID`
set + redirect `http://localhost:8150/api/miro/callback` registered. **Preview
needs no token** — Configure → Preview opens the would-be board in a new tab.
Then **Create board** → **Open in Miro**. Expect first-push rough edges per the
unrun shapes above.
