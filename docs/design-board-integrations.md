# Board Integrations — Multi-Board Design

One-way export from Bristlenose to a team whiteboard, behind the **board-agnostic
layout IR** already shipped for Miro. This doc assesses three additional render
targets — **Mural**, **Lucidspark (Lucid)**, **FigJam (Figma)** — decides go/no-go
per board, and specifies the small IR changes the second board forces out.

**Status:** Research-complete (28 Jun 2026), no code; plan revised after a
correctness + parsimony + security review pass. Feeds the build behind
`docs/design-miro-bridge.md` (read that first — the IR, layout engine, SVG
renderer, anonymisation boundary, and cross-app flow are all defined there and are
**shared, not re-litigated here**).

**Goal.** Make "support another board" a *new thin renderer + auth adapter, not a
second project*. Multi-board is a real wedge: researchers and teams must often use
the whiteboard their **organisation mandates** (a fixed corporate choice), so being
board-agnostic lets a researcher push to whatever their workplace standardised on.
The value is in the agnostic middle ground, not any one board.

---

## TL;DR

| Board | Verdict | Why | First-cut auth | Renderer effort vs Miro |
|---|---|---|---|---|
| **Mural** | ✅ **GO** | Per-item REST, near-identical to Miro: create-mural → areas → bulk stickies. | OAuth (15-min tokens → OAuth needed early; paste-token demo-grade) | **Same** (ports ~1:1) |
| **Lucidspark** | ✅ **GO** | One-shot `.lucid` package POST; arbitrary hex; `editUrl` in response. | **Long-lived API key** (a true paste-token, mirrors shipped Miro model) | **Same / slightly larger** (package serializer, not item loop) |
| **FigJam** | ❌ **NO-GO** (server push) | REST is read-only for canvas; creation is plugin-in-editor or catalog-client-only MCP. No headless server path. | n/a | **Different model entirely** (publish a plugin) |

**Recommended order: Lucidspark → Mural → (FigJam only on demand).** Reasoning in
*Recommended order* below.

---

## Comparison matrix

Miro is the shipped baseline (left column); the three candidates follow. Every
fact below is from current vendor docs (28 Jun 2026); citations in *Sources*.

| | **Miro** (shipped) | **Mural** | **Lucidspark** | **FigJam** |
|---|---|---|---|---|
| **OAuth 2.0** | Yes, +PKCE | Yes (Auth-Code); PKCE optional | Yes (Auth-Code, confidential client) | Yes — but the write scope `mcp:connect` is **not granted to 3rd-party apps** |
| **PKCE** | Yes | Optional | Undocumented (assume no) | Moot |
| **Paste-token first cut** | ✅ personal token (non-expiring) | ⚠️ OAuth-issued **15-min** token (demo only) | ✅ **long-lived API key** (best of all four) | ❌ PAT is read-only for content |
| **Create board server-side?** | ✅ `POST /v2/boards` | ✅ `POST /murals` (`murals:write`) | ✅ `.lucid` ZIP → `POST /documents` (`product=lucidspark`) | ❌ no REST file-create; MCP only (catalog clients) |
| **Container model** | Frames (named, **no nest**, 1 item↦1 frame) | **Areas** (named, **nest** via `parentId`, `layout: column/row`) | Containers (membership by **bounding-box overlap**, nest) | Sections (plugin/MCP only) |
| **Sticky colour** | **16 named palette** | **arbitrary hex RGBA** | **arbitrary hex** | hex/RGB `fills` |
| **Sticky geometry** | x/y + w/h px; absolute or frame-relative (centre) | x/y + w/h px; absolute or `parentId`-relative | `boundingBox` x/y/w/h; units configurable; absolute | 240×240 default, auto-grow |
| **Sticky text markup** | `<p><a><strong><em><u><s><br>`; **no `<span>`**; no per-span size/colour | `htmlText`: `<b><i><u><s><ul><ol><li>`; no per-span size/colour | rich: span + `font` (bold/italic/**size**) | `characters` string |
| **Per-sticky de-emphasis** | italic only | italic only | **per-span size possible** | n/a |
| **Bulk create** | 20 items/call | **1000/call** | whole doc, **one POST** | loop in-editor |
| **Rate limits** | credit-based, backoff on `X-RateLimit-*` | 25/user/s, 10k/app/min, `X-RateLimit*` | 750/min, 429 (no Retry-After) | n/a for write |
| **Shareable board URL** | ✅ | ✅ (visitor link; exact field unverified) | ✅ `editUrl`/`viewUrl` in create response | only after in-editor/MCP create |
| **Official Python SDK** | `miro_api` (we hand-roll httpx anyway) | ❌ httpx | ❌ httpx + ZIP builder | ❌ |
| **Char cap / sticky** | <6000 | UNKNOWN | UNKNOWN (bounded by 1.5 MB doc) | UNKNOWN (auto-grow) |

**UNKNOWNs to resolve with a ~30-min live spike before committing each board:**
- *Mural:* free-account can register a dev app + create a mural? exact shareable-URL field? sticky char cap?
- *Lucid:* free/individual plan can mint a Dev-Portal API key? PKCE support? sticky char cap?
- (Neither set is a plausible blocker — both are GO; these are de-risking confirmations.)

---

## Sticky-spec comparison → the common platform

The question "do they share a sticky vocabulary?" decides how much abstracts. They
do — with **Miro as the most-constrained** target, so designing to Miro's ceiling
is automatically safe everywhere else.

| Spec axis | Common platform (lowest safe denominator) | Who exceeds it |
|---|---|---|
| **Colour** | one background colour per sticky, from a **semantic** palette | Miro is the constraint (16 named); Mural/Lucid/FigJam take arbitrary hex |
| **Geometry** | absolute `x/y/w/h` in board px (the layout engine already emits this) | all four accept absolute coords; parenting is an optional per-renderer nicety |
| **Text** | whole-sticky text + **bold/italic** + a link; **no per-span size/colour** | Lucid alone allows per-span size — *not* worth forking the IR for |
| **Container** | a named box (`x/y/w/h` + title) drawn around its columns | Mural/Lucid can also *parent* members; the box-by-geometry form works for all |
| **Attribution hierarchy** | italic `— P1 · 0:10` inside the quote sticky (the v0 decision) | impossible to improve on Miro **and** Mural; possible on Lucid only |

**Implication:** the existing IR's sticky/frame/text shapes are already the right
common platform. The only genuine Miro-ism that leaked into the IR is **colour**.

### The one IR change the second board forces: semantic colour tokens

Today the IR's colour tokens *are* Miro's named-palette strings
(`bristlenose/miro_board.py`: `HEADER_TOKEN = "light_pink"`,
`SENTIMENT_TOKEN = {"positive": "light_green", …}`). That makes the Miro renderer
an identity map but every other renderer a translation *away from a Miro
vocabulary* — backwards. The SVG renderer already pays this tax with a
`TOKEN_HEX = {"light_pink": "#FADADD", …}` reverse-map (`miro_render_svg.py`).

**Fix:** make tokens semantic, define one canonical hex per token in a shared
palette, and let each renderer own the *outbound* mapping. The mapping below is
the **actual** `SENTIMENT_TOKEN` from `miro_board.py` (all 7 sentiments), not an
illustrative sketch — implement against these exact values:

```
Semantic token (IR)        Miro named (today)   Canonical hex   Miro (quantise→named)
sentiment.positive   ───►  light_green     ───► #CDEBC5   ───►  light_green
sentiment.delight    ───►  green           ───► #9BD7A0   ───►  green
sentiment.negative   ───►  light_pink      ───► #FADADD   ───►  light_pink
sentiment.frustration ──►  red             ───► #F4A6A6   ───►  red
sentiment.confusion  ───►  light_blue      ───► #BEE0F2   ───►  light_blue
sentiment.neutral    ───►  gray            ───► #E2E2E2   ───►  gray
sentiment.mixed      ───►  light_yellow    ───► #FFF9B1   ───►  light_yellow
quote.default        ───►  light_yellow    ───► #FFF9B1   ───►  light_yellow
header               ───►  light_pink      ───► #FADADD   ───►  light_pink
```

**Watch the `header` / `sentiment.negative` collision.** Both are `light_pink`
(`#FADADD`) today — a header sticky and a negative-sentiment quote are the *same*
colour by accident of the named palette. The palette extraction must **decide**:
keep them identical (pure no-op refactor — B0 stays "no behaviour change"), or give
`header` its own hex (arguably better — a header shouldn't read as negative — but a
*visible behaviour change* on the Miro board, so it is **not** a no-op). **Recommend:
keep identical in the extraction commit; raise the header-colour fix as a separate,
visible change** so the refactor stays reviewable. (Mural/Lucid colour by sentiment,
so the collision only bites if a future board tints headers distinctly.)

- **IR**: `SENTIMENT_TOKEN` keys become semantic (`sentiment.positive`), not Miro
  colours. A new `board_palette.py` holds `TOKEN_HEX` (the canonical hex, lifted
  from the SVG renderer) as the single source of truth.
- **SVG renderer**: drop its private `TOKEN_HEX`; import the shared one. Net simpler.
  Preserve its unknown-token fallback (`#FFF9B1`) verbatim.
- **Miro renderer**: gains a small `TOKEN_TO_MIRO_NAMED` quantiser — the *only*
  Miro-specific colour code. ~16 lines.
- **Mural / Lucid renderers**: consume the canonical hex directly. Zero colour code.

This is the test of the abstraction: it pushes the Miro vocabulary *out* of the IR
and into the Miro renderer where it belongs. **Not purely mechanical:**
`tests/test_miro_board.py:59-60` asserts on *literal Miro strings* (`"green"`,
`"red"`), so the token rename **requires test edits** — B0 stays green only after
those assertions move to the semantic tokens. Grep `SENTIMENT_TOKEN`,
`HEADER_TOKEN`, `DEFAULT_QUOTE_TOKEN`, `TOKEN_HEX` first
(`miro_board.py`, `miro_render_svg.py`, `tests/test_miro_board.py`).

---

## Common vs custom — what each board adds

The reuse point is large; the per-board delta is small and shaped like Miro's.

### Shared (build once, never fork)
- **Layout engine + Board IR** (`miro_board.py`, to be renamed `board_layout.py`).
- **Semantic palette** (`board_palette.py`, new — see above).
- **Creds-free SVG renderer** (`miro_render_svg.py`, to be renamed
  `board_render_svg.py`) — dev/iteration, board-independent.
- **Export orchestration** — quotes → columns → IR. Scope = `all / starred /
  section / tag` reusing `export_core` `quote_ids` + `is_starred`. Currently
  `server/miro_export.py`; generalise to `server/board_export.py` with the
  per-board push pluggable.
- **Anonymisation boundary** — enforced *structurally* at IR construction:
  `QuoteCard` has **no name field**, so `build_columns()` drops the display name
  before any renderer sees the data. That guarantee is genuinely shared and is
  already pinned at `build_columns` (`tests/test_miro_export.py`). **The per-board
  test pins something different** — that the renderer's *serializer* touches no
  name-bearing field. It must inspect the **final serialized egress payload**
  (Mural `htmlText` string / Lucid `document.json` bytes), not just re-run the
  `build_columns` assertion (which passes for free and proves nothing about the new
  renderer). Plant **both** a `participant_name` *and* a name-bearing `source_file`
  stem (e.g. `jane-doe.mov`) in the fixture and assert both absent —
  `export_core` carries `source_file` through (`anonymise=False`), so a renderer
  that serializes more of the quote graph than Miro does could leak the filename-name.
- **Cross-app flow + consent UX** — the parallel-surfaces native entry, the
  state-encoding Export menu, the consent step. Same pattern, new label.
- **Clip-link enhancement** — `<a href>` to exported clips; identical contract
  (see `design-miro-bridge.md` *Enhancement: clip links*).

### Custom per board (the thin renderer + auth adapter)

| Concern | Mural | Lucidspark | (FigJam) |
|---|---|---|---|
| **Renderer shape** | **per-item REST** (port `miro_client.py`: create-mural → areas → bulk stickies, 1000/call) | **one-shot package**: serialize IR → `document.json` → ZIP → `POST /documents` | publish a plugin (not a renderer) |
| **New file** | `mural_client.py` | `lucid_client.py` + `lucid_package.py` (JSON+ZIP builder) | a Figma plugin repo |
| **Colour** | semantic hex → identity | semantic hex → identity | n/a |
| **Container** | areas + `parentId` (or absolute box) | container box, membership by bbox overlap | n/a |
| **Auth** | OAuth (15-min access + rotating refresh) — paste-token only demo-grade | **API key** paste-token first; OAuth later | n/a |
| **Routes** | `routes/mural.py` | `routes/lucid.py` | n/a |
| **Keychain + env** | `mural` service name + `BRISTLENOSE_MURAL_ACCESS_TOKEN` | `lucid` + `BRISTLENOSE_LUCID_API_KEY` | n/a |
| **Sub-processor note** | `SECURITY.md` | `SECURITY.md` | n/a |

### The renderer abstraction (accommodating both delivery shapes)

The current Miro path is an item-loop with bulk batching; Lucid is a single
package POST. Both consume the same IR. The eventual shape is one protocol:

```python
class BoardRenderer(Protocol):
    name: str  # "miro" | "mural" | "lucid"
    def push(self, board: Board, creds: BoardCreds, *,
             clips_base: str | None = None) -> ExportResult: ...
```

**Do NOT declare this Protocol up front — extract it when the second `push()`
exists** (see *Plan*, B2). Today there is one renderer; a Protocol over a
population of one is abstraction-for-its-own-sake. Write `lucid_client.push()`
against the existing seam first, then extract the Protocol from two real
signatures that demonstrably rhyme.

Two seam realities the eventual extraction must handle (the "just swap the last
call" framing is too glib):

1. **`push_to_miro` does not take a `Board`.** Its signature is
   `push_to_miro(token, db, project_id, project_name, quote_ids, *, colour_by,
   clips_base)` (`miro_export.py:141`) — it builds the board *internally* and holds
   the "no quotes selected" guard (`n_quotes == 0`). The `push(board, creds)` shape
   requires first **hoisting `build_board()` out of `push_to_miro` into the
   orchestrator** and moving the empty-guard up. That's a real (small) refactor of
   the route too (`routes/miro.py`), not a rename.
2. **Partial-failure semantics differ by delivery shape.** A per-item renderer
   (Miro/Mural) can leave a board *created but half-filled*; today that recovery URL
   travels inside a raised `MiroError` (`miro_export.py:174-178`), not a return
   value. Lucid's one-shot POST is atomic — `editUrl` or nothing. So `ExportResult`
   needs an explicit partial path: **let each renderer raise a typed error carrying
   the recovery URL**, and have the orchestrator normalise — don't pretend a single
   happy-path tuple covers a created-but-failed board.

- **Miro / Mural** implement `push` as a create-board → frames/areas → bulk-stickies
  loop with rate-limit backoff.
- **Lucid** implements `push` as serialize-IR → zip → one POST, reading `editUrl`
  from the response.
- The **SVG preview** stays a separate creds-free function (`render_html(board)`),
  not a `BoardRenderer` — it never pushes.

**`_sticky_content` is NOT shared.** It currently emits **Miro-dialect HTML**
(`<strong>`, `<i>`, `<br>`, `<a>`) in the orchestrator (`miro_export.py:117-128`).
Mural wants `<b>` not `<strong>` (and may not support `<a>` at all — verify in the
spike); Lucid wants spans / a JSON link object. So sticky-text serialisation moves
**down into each renderer**. The IR carries the *structured* content (quote, the
italic attribution, the optional link); each renderer dialects it. (Carrying
fully-typed text segments in the IR is the richer alternative that would unlock
Lucid's per-span sizing later — deferred; not worth it for v1.)

---

## Per-board go/no-go + effort

### Mural — GO. Effort: **Same as Miro.**
Widget model is near-identical (create-mural → areas → stickies with x/y/size/parent).
Renderer ports ~1:1; **arbitrary hex is *easier* than Miro's named palette** (no
quantisation). Only net-extra work is auth: **15-min access tokens with rotating
refresh** force a real refresh loop sooner than Miro's longer-lived tokens, so a
paste-token cut is demo-grade and OAuth arrives early. Bulk 1000/call (vs Miro's 20)
makes large boards cheaper.

### Lucidspark — GO. Effort: **Same / slightly larger.**
Board-modelling work (coords, sentiment→hex, containers, rich text) is identical to
Miro. The difference is *architectural, not harder*: a **package serializer + ZIP
builder** replaces the item loop. That actually *simplifies* rate-limit/retry (one
call) but adds the package step and a coordinate-driven container model (membership
by bounding-box overlap — free, since the layout engine already emits absolute
coords). **Simplest auth story of the four — but the highest revocation cost if
leaked.** A long-lived API key is a true paste-token, matching the shipped Miro
keychain model with the least new machinery (`editUrl`/`viewUrl` come back in the
create response, no extra sharing call). The flip side: Miro's and Mural's tokens
are short-lived/auto-rotating, but a leaked Lucid key works **until a human revokes
it in the Lucid Dev Portal** and may grant broad document access to the org tenant.
So the key gets explicit handling, not just "best story" framing:
- **Never logged** — log `get_credential_source("lucid")` (a `"keychain"`/`"env"`
  label), never the value, mirroring `miro_token_trace`. `credentials.py` logs no
  values today; keep it that way.
- **Never in any export / support bundle** — it's a live credential (same "never
  bundle" rule as the re-identification keys, for a different reason).
- **Keychain path strongly preferred over the env-var fallback** — the env var is
  process-inheritable and the key is long-lived, so the fallback is *more* dangerous
  for Lucid than for a short-lived token.
- **Revocation path documented** in the connect/disconnect copy (Lucid Dev Portal),
  so a researcher can kill a leaked key.

### FigJam — NO-GO for the server-push model. Effort: **different model entirely.**
Figma's REST API is **read-only for canvas content** — no file-create, no
node/sticky write, no `file_content:write` scope. Creation exists only via:
- the **Plugin API** (`figma.createSticky()`) which runs *inside the editor* — needs
  a human to open the file and run a published plugin; **not server-side**; or
- the **MCP write-to-canvas** path, which *can* create a FigJam file + stickies but
  whose `mcp:connect` scope is **locked to catalog clients** (VS Code / Cursor /
  Claude Code) — **not available to a general third-party OAuth backend**, beta,
  paid-seat-gated, and agent-mediated (non-deterministic).

There is **no authenticated, deterministic, server-side way** for Bristlenose's
backend to end up with a FigJam board of stickies. FigJam does **not slot into the
IR→renderer architecture.** If designer-demand appears, the only honest path is a
**published FigJam plugin** that consumes the **same IR serialized as a JSON
manifest** (the IR→manifest serializer is reusable; the plugin runtime + in-editor
human step + store review/distribution is the new, larger surface). This confirms
`design-miro-bridge.md`'s existing "FigJam is endgame, demand-gated" stance —
research now makes the *why* concrete rather than a hunch.

### Recommended order: **Lucidspark → Mural**

Two reasonable orderings; the deciding axis is **auth friction**, which the Miro
doc names as "the make-or-break adoption surface," not layout.

- **Lucidspark first** — its **long-lived API key** is a true paste-token that
  mirrors the *already-shipped* Miro keychain+env model **exactly**, so v1 ships with
  the least new auth machinery (no refresh loop, no early OAuth). It also exercises
  the *harder* renderer shape (package vs item-loop), proving the IR is genuinely
  delivery-agnostic — the strongest test of the abstraction. Cost: confirm free-tier
  Dev-Portal key access in the live spike first (the one UNKNOWN that could reorder).
- **Mural second** — renderer ports ~1:1 from Miro (cheapest *code*), and by then
  the **OAuth work** it needs (15-min tokens) is the same OAuth that benefits every
  board, so it lands on built foundations rather than pulling auth forward into v1.

*Alternative if the live spike shows Lucid free-tier can't mint API keys:* flip to
**Mural first**, accept early OAuth, and treat Lucid as the package-shape follow-up.
Surface this as a decision point, not a silent default.

---

## Proposed UX flow changes

The Miro flow (`design-miro-bridge.md` *Cross-app flow*, `docs/mockups/miro-flow.html`)
is the template. Multi-board needs **one** structural change and several label
changes; the make-or-break (cross the app boundary as few times as possible; never
set up twice) is unchanged.

1. **Export menu: one "Send to a board…" entry, then a board picker** — *not* N
   sibling rows (`Send to Miro…`, `Send to Mural…`, `Send to Lucidspark…`), which
   bloats the popover and implies you'd pick a different board each time. A
   researcher's org has *one* mandated board. So:
   - First use: **Send to a whiteboard…** → a small picker (Miro / Mural /
     Lucidspark, each with connect-state). Pick once.
   - The chosen board is **remembered** (per project, or per install — open
     question below). Subsequent exports show **Send to {board}…** directly, with a
     quiet "change board" affordance. This keeps the common path one click and
     honours "never make someone set up twice."
2. **The menu still encodes connect-state per board** — `Connect to {board}…`
   (routes to consent + token) vs `Send to {board} board…` (jumps to configure),
   exactly as Miro does today.
3. **Consent copy is board-named, and the per-export consent step is
   non-skippable** — "data leaves your machine and goes to **{board}**; {board} is a
   sub-processor; hidden quotes excluded; N quotes." One shared consent component,
   board name interpolated. **The remembered board (below) skips *connect*, never
   *consent*:** the count + named destination shown at every export is the control
   that makes "remembered" safe (it stops a researcher one-clicking a *high*-
   sensitivity project to a board they set up for a low-sensitivity one — a
   purpose-limitation nudge; the anonymisation boundary still holds either way).
4. **Configure/Preview is board-independent** — the creds-free SVG preview already
   renders the IR, so "Preview" shows the would-be board identically regardless of
   target. (Per the brief, the Preview *button* is being removed from the shipped
   UX; the `/preview` route stays for dev.)
5. **Done state: `Open in {board}`** — one obvious button, board-named, from the
   `board_url` the renderer returns.
6. **Native macOS entry** reuses the parallel-surfaces pattern
   (`docs/mockups/miro-native-flow.html`): a native "Send to a whiteboard…" row in
   the Quotes menu + export popover that opens the existing React panel via the
   bridge. The board picker lives in the web panel; native just triggers it.

**Open UX questions (for the user / a tester pass, not to pre-decide):**
- Is the remembered board **per-project** (a project pushed to Mural keeps pushing
  to Mural) or **per-install** (one org, one board, set once)? Per-install matches
  the "org mandates one board" reality and is simpler; per-project is more flexible
  for consultants juggling clients. *Lean: per-install default, overridable.*
- Does the picker show **all three always**, or only **connected** boards once one is
  set up? *Lean: show the connected one prominently, others under "change board".*
- Colour-by default (sentiment / participant / theme) — inherited from Miro's open
  question, unchanged.

---

## Map to our code (the seams, generalised)

| Seam | Today (Miro) | After generalisation |
|---|---|---|
| Layout + IR | `bristlenose/miro_board.py` | `bristlenose/board_layout.py` (rename; grep `miro_board` import sites first) |
| Palette | inline in `miro_board.py` + `miro_render_svg.py` | `bristlenose/board_palette.py` (new, single source) |
| SVG renderer | `bristlenose/miro_render_svg.py` | `bristlenose/board_render_svg.py` (rename) |
| Per-target renderer | `bristlenose/miro_client.py` | `+ mural_client.py`, `+ lucid_client.py` (+ `lucid_package.py`) behind a `BoardRenderer` protocol |
| Export orchestration | `bristlenose/server/miro_export.py` | `bristlenose/server/board_export.py` (build_board agnostic; `push` pluggable) |
| Routes | `bristlenose/server/routes/miro.py` | `+ routes/mural.py`, `+ routes/lucid.py` (same shape) |
| Token storage | `credentials*.py` + Swift `KeychainHelper.serviceNames` + `overlayMiroToken` + `EnvCredentialStore.ENV_VAR_MAP` | one keychain entry + env var **per board**, same pattern (no Python-writes-Keychain path; Swift host stores, injects via env under App Sandbox) |
| Egress governance | `SECURITY.md` Miro sub-processor note (singular, Miro-named); anonymisation tests | **Generalise the headline** — `SECURITY.md:43` currently says "…makes Miro Inc. a sub-processor" (singular); rewrite to name whichever board the researcher connects (Miro Inc. / Mural Inc. / Lucid Software Inc.). Per board: a note with vendor + egress shape (quote text, speaker codes, sentiment, opt-in clip links; never names; hidden excluded) **+ a DPA/residency pointer URL** (procurement asks). One serialized-payload anonymisation test per board. |
| Native entry | `ContentView.swift` / `MenuCommands.swift` → bridge `sendToMiro` | a generalised `sendToBoard` (or keep per-board dispatch); web panel owns the picker |

**Naming discipline (per the no-legacy-naming rule):** name the generalised pieces
by what they *are* (`board_layout`, `board_palette`, `board_render_svg`,
`board_export`, `BoardRenderer`), not after Miro. Do the rename **when the second
board lands**, not speculatively — and in one mechanical commit with the
import-site grep done first.

---

## Decisions

1. **Mural and Lucidspark are GO; FigJam is NO-GO for server push** — research-confirmed
   against current vendor docs.
2. **Semantic colour tokens** — the IR stops speaking Miro's named palette; a shared
   `board_palette.py` holds canonical hex; each renderer maps outbound (Miro
   quantises to named; others use hex directly). The single real IR change, and the
   **only** generalisation worth doing *before* a second board (B0) — the SVG
   renderer is already a second consumer paying the tax.
3. **Defer the `BoardRenderer` Protocol, the rename, and the picker** until the
   second renderer exists — extract the Protocol from two real `push()` signatures
   (B2), do the `miro_board`→`board_layout` rename in that same commit, and build the
   picker only at 2+ connectable boards. No abstraction over a population of one.
4. **Lucidspark first, Mural second** — auth friction decides; Lucid's long-lived API
   key matches the shipped paste-token model with the least new machinery and tests
   the harder package renderer. Reorder only if the live spike kills Lucid free-tier
   key access.
5. **One "Send to a whiteboard…" entry + remembered board**, not N sibling menu rows
   — a researcher's org mandates one board.
6. **Generalise names when the 2nd board lands** (`miro_board.py` → `board_layout.py`,
   etc.), name by data/shape not by Miro, after grepping import sites.
7. **Reuse everything shared** — layout, IR, SVG preview, export orchestration,
   anonymisation boundary, consent UX, clip links, the keychain+env auth layer. The
   per-board delta is `<board>_client.py` + `routes/<board>.py` + keychain/env entry +
   sub-processor note + one anonymisation test.
8. **One-way push, new board per export, no sync-back** — inherited from Miro,
   applies to every board.
9. **FigJam, if ever, is a published plugin consuming the IR-as-manifest** — not a
   renderer; demand-gated; a separate, larger surface.

---

## Plan (build order, behind the shipped Miro work)

Revised after a parsimony pass (Occam): **do not front-load a "generalisation
pass."** Most of the abstraction (rename, `BoardRenderer` Protocol, picker UX) should
*trail* the second renderer, not precede it — extracted from two real
implementations, not guessed over a population of one. Only one piece earns its keep
*today*: the palette, because the SVG renderer is already a second consumer paying
the Miro-vocabulary tax.

| Milestone | What | Notes |
|---|---|---|
| **B0 — Palette only** | Extract `board_palette.py` (semantic tokens + canonical hex); repoint the Miro renderer's `TOKEN_TO_MIRO_NAMED` quantiser; **delete** the SVG renderer's private `TOKEN_HEX` duplication. Fix the `test_miro_board.py` literal-string assertions. **Keep `miro_board.py` named `miro_board.py`.** | The one change that pays for itself now — two real consumers, deletes a live duplication. No rename, no Protocol. |
| **B1 — Lucidspark spike** | 30-min live spike: free-tier Dev-Portal API key? create a `lucidspark` document via `.lucid` package? `editUrl` back? does a sticky support a clickable link (and in what escaping context)? Confirm/kill the GO. | **Gate.** If key access is paid-only → reorder to Mural-first (which pulls B4/B5 OAuth forward). This fork inverts the whole sequence; decide here, surface it. |
| **B2 — Lucidspark renderer (+ rename + Protocol, same commit)** | `lucid_client.py` + `lucid_package.py` (IR → `document.json` → ZIP → `POST /documents`); `routes/lucid.py`; `lucid` keychain+env; API-key connect; SECURITY note; serialized-payload anonymisation test. **Now that a 2nd `push()` exists:** hoist `build_board` out of `push_to_miro`, extract the `BoardRenderer` Protocol from the two real signatures, and do the `miro_board`→`board_layout` etc. rename — all in this commit (the names finally describe two things). | The rename/Protocol ride here, not in B0. See *security disciplines* below. |
| **B3 — Mural spike** | 30-min live spike: free-account dev app + create-mural? shareable-URL field? sticky char cap? `<a>` link support in `htmlText`? | Gate before B4. |
| **B4 — Mural renderer** | `mural_client.py` (port the Miro item-loop: create-mural → areas → bulk-1000 stickies + backoff); `routes/mural.py`; `mural` keychain+env; SECURITY note; serialized-payload anonymisation test. | Needs OAuth (15-min tokens) — B5. |
| **B5 — Shared OAuth (Mural prerequisite + Miro-OAuth catch-up)** | Browser OAuth 2.0 + PKCE + keychain-refresh, `ASWebAuthenticationSession` native path. Persists Mural's **rotating** refresh token atomically (write-back-on-refresh, or a crash mid-refresh dead-ends the user). | **Not** "generalisation overhead" and **not** on the second-board critical path — Lucid (B2) needs no OAuth. This is pulled in by Mural specifically, and it also lands Miro's own deferred M2 OAuth. Label it honestly. |
| **B6 — Board picker UX** | *Only once 2+ boards are genuinely connectable.* Until then, ship board #2 as a concrete `Send to Lucidspark…` row exactly as Miro ships today. The "never set up twice" goal is satisfied by remembered tokens, not by a picker. | Deferred. Build the picker when a real user hits the 2-connected-boards ambiguity, not before. |

**Security disciplines for the Lucid renderer (B2):**
- **`lucid_package.py` builds `document.json` as a Python dict and serialises via
  `json.dumps(..., ensure_ascii=True)` exactly once — never string-templates JSON.**
  (The CLAUDE.md `ensure_ascii` XSS lesson applies to this new JSON sink: a quote
  with `"`, `\`, `</script>`, ` `, or a control char must stay confined to a
  string value, not break the package structure.) Test: plant those chars, assert
  the ZIP's `document.json` round-trips through `json.loads` structurally intact.
- **ZIP entry names are fixed** (`document.json`, `data/…`) — never interpolated
  from project / section / participant text (Zip-Slip-class; lands on Lucid's
  importer, but we don't ship a malformed package).
- **Clip-link escaping is JSON-context for Lucid** (`ensure_ascii` JSON string), not
  `html.escape`. The shared `_clip_url` http(s)-only scheme-allowlist still applies
  (re-run its adversarial cases through the Lucid link path).

**Endgame (unchanged from Miro doc):** Tier-3 intelligent layout; FigJam-as-plugin
on demand; report-as-deliverable.

---

## Verification (per new board, mirroring the Miro list)

1. Connect (API key / OAuth) — token stored, status Connected, menu flips.
2. Disconnect — token removed.
3. Export (default) — new board: two containers (Sections / Themes), header
   stickies, quote stickies.
4. Sticky content — quote leads, italic `— P1 · 0:10` trails.
5. Colour mapping — sentiments → correct hex/named on that board.
6. Scope — `starred only` exports just starred; `all` excludes hidden.
7. Container layout — Sections left, Themes right; columns session→time.
8. > 200 quotes — bulk + backoff (or package size), no error surfaced.
9. **Anonymisation** — speaker codes egress, never display names (pinned test).
10. Consent UI — board name + quote count + destination shown before upload.
11. `pytest tests/` + `ruff check .`.

---

## Sources (verified 28 Jun 2026)

**Mural:** [OAuth](https://developers.mural.co/public/docs/oauth) ·
[Scopes](https://developers.mural.co/public/docs/scopes) ·
[Create mural](https://developers.mural.co/public/reference/createmural) ·
[Create area](https://developers.mural.co/public/reference/createarea) ·
[Create sticky](https://developers.mural.co/public/reference/createstickynote) ·
[Update sticky (htmlText)](https://developers.mural.co/public/reference/updatestickynote) ·
[Rate limiting](https://developers.mural.co/public/docs/rate-limiting) ·
[Official samples](https://github.com/spackows/MURAL-API-Samples)

**Lucid:** [Using OAuth 2.0](https://developer.lucid.co/reference/using-oauth-20) ·
[Access scopes](https://developer.lucid.co/reference/access-scopes) ·
[API keys](https://developer.lucid.co/reference/authentication-methods) ·
[Create/import document](https://developer.lucid.co/reference/createorcopyorimportdocument) ·
[Standard Import overview](https://developer.lucid.co/docs/overview-si) ·
[Rate limits](https://developer.lucid.co/reference/rate-limits) ·
[Sample REST apps](https://github.com/lucidsoftware/sample-lucid-rest-applications)

**Figma/FigJam:** [REST API intro (read-only)](https://developers.figma.com/docs/rest-api/) ·
[Scopes](https://developers.figma.com/docs/rest-api/scopes/) ·
[createSticky (in-editor)](https://www.figma.com/plugin-docs/api/properties/figma-createsticky/) ·
[StickyNode](https://developers.figma.com/docs/plugins/api/StickyNode/) ·
[MCP server guide](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server) ·
[Remote MCP install (catalog-only)](https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/)

---

## Related docs

- `docs/design-miro-bridge.md` — the shipped baseline (IR, layout, flow, clip links,
  anonymisation). **Read first.**
- `docs/design-export-quotes.md` — Tier-1 board-shaped CSV.
- `docs/design-export-clips.md` — clip extraction (clip-link enhancement).
- `SECURITY.md` — sub-processor notes (one per board).
- `experiments/board-layout-poc/` — the original layout prototype.
