# Board Integrations — Multi-Board Design

One-way export from Bristlenose to a team whiteboard, behind the **board-agnostic
layout IR** already shipped for Miro. This doc assesses three additional render
targets — **Mural**, **Lucidspark (Lucid)**, **FigJam (Figma)** — decides go/no-go
per board, and specifies the small IR changes the second board forces out.

**Status:** Research-complete (28 Jun 2026); B0 palette shipped. **Direction
(28 Jun): FigJam is the driver** — it has by far the largest user base, so the engine
is built toward a FigJam plugin, with Lucidspark picked off "for free along the way"
as the document-model dress rehearsal. Mural + OAuth are deferred (the September
Mural-friends test is the only thing that would pull them back). See *Plan — FigJam
is the driver*. Feeds the build behind
`docs/design-miro-bridge.md` (read that first — the IR, layout engine, SVG
renderer, anonymisation boundary, and cross-app flow are all defined there and are
**shared, not re-litigated here**).

**Goal.** Reach **FigJam** — the largest whiteboard user base (designers, on Figma's
installed base) — by building a board-agnostic engine whose keystone is a serialized,
versioned **Board Manifest** (the IR as a portable JSON document). FigJam has no
server write path, so it can only be reached by a **published in-editor plugin that
consumes that manifest**; building toward it reshapes the engine so the other boards
fall out cheaply. **Lucidspark** consumes a whole-board document too, so it's the
**free dress rehearsal** that proves the manifest model against a live API.
**Mural** (per-item REST, needs OAuth) advances FigJam by nothing and is deferred.
Multi-board is still a real wedge — orgs mandate a board — but FigJam is the prize
that justifies the engine; the rest are picked off along the way.

---

## TL;DR

| Board | Verdict | Why | First-cut auth | Renderer effort vs Miro |
|---|---|---|---|---|
| **Mural** | ✅ **GO** | Per-item REST, near-identical to Miro: create-mural → areas → bulk stickies. | OAuth (15-min tokens → OAuth needed early; paste-token demo-grade) | **Same** (ports ~1:1) |
| **Lucidspark** | ✅ **GO** | One-shot `.lucid` package POST; arbitrary hex; `editUrl` in response. | **Long-lived API key** (a true paste-token, mirrors shipped Miro model) | **Same / slightly larger** (package serializer, not item loop) |
| **FigJam** | ❌ **NO-GO** (server push) | REST is read-only for canvas; creation is plugin-in-editor or catalog-client-only MCP. No headless server path. | n/a | **Different model entirely** (publish a plugin) |

**Build order (FigJam is the driver): IR→Manifest → Lucidspark (free dress
rehearsal) → FigJam plugin (the prize); Mural + OAuth deferred.** The verdicts above
still hold; the *ordering* is now pointed at FigJam — see *Plan*.

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
| **Colour** | **two fixed colours: pink headers, yellow quotes** (Miro's `light_pink` / `light_yellow`) | everyone *can* do hex, but we deliberately don't — see below |
| **Geometry** | absolute `x/y/w/h` in board px (the layout engine already emits this) | all four accept absolute coords; parenting is an optional per-renderer nicety |
| **Text** | whole-sticky text + **bold/italic** + a link; **no per-span size/colour** | Lucid alone allows per-span size — *not* worth forking the IR for |
| **Container** | a named box (`x/y/w/h` + title) drawn around its columns | Mural/Lucid can also *parent* members; the box-by-geometry form works for all |
| **Attribution hierarchy** | italic `— P1 · 0:10` inside the quote sticky (the v0 decision) | impossible to improve on Miro **and** Mural; possible on Lucid only |

**Implication:** the existing IR's sticky/frame/text shapes are already the right
common platform. Colour, which earlier drafts treated as the load-bearing IR
problem, is deliberately **not** — see the next section.

### Colour: pink headers + yellow quotes everywhere (product decision)

**The cross-board baseline is two flat colours — pink header stickies, yellow quote
stickies — exactly as Miro renders them today.** Reproduce that on every board and
stop. The other boards take arbitrary hex, but we use the **same two colours Miro's
named `light_pink` / `light_yellow` produce** (assume enterprise Miro custom
palettes aren't API-exposed, so the standard named subset is the source of truth).
A whiteboard that's the *same* on Miro, Mural and Lucidspark is the goal; cross-board
colour cleverness is anti-goal.

**Why so plain — what colour is actually *for* in research.** Colour-by-sentiment
(the current `colour_by="sentiment"` path) is a **party trick**: auto-tinting quotes
positive/negative reads well in a demo but is of little use to a working researcher.
The genuinely useful colour dimensions come from **the researcher's own context and
manual tags** — persona, free vs paid, arrived-via-email-campaign vs organic,
A/B-variant-A vs B — none of which Bristlenose can infer; they come from product
knowledge and the research brief. So:

- **Default (and the only cross-board guarantee): flat — pink headers, yellow
  quotes.** No auto-colouring.
- **Colour-by-sentiment stays in the engine but is demoted** from default to an
  optional, lower-priority path — *not* a reason to design the IR around a sentiment
  palette, and not a cross-board priority.
- **Colour-by-custom-tag is the genuinely valuable version — and it's deferred**
  (later; may relate to signal cards — a separate project). When it lands it's a
  quote→tag→colour map the researcher drives, rendered through the same two-then-N
  colour slot the baseline already uses.

**What this means for the IR.** The earlier "semantic sentiment palette" refactor is
**over-built for this baseline** and is dropped. The minimal, honest change is still
worth making because the SVG renderer already duplicates the colour vocabulary
(`TOKEN_HEX` reverse-map, `miro_render_svg.py`): extract a tiny `board_palette.py`
with just the two baseline tokens —

```
header        ───►  Miro light_pink   ───►  #FADADD
quote.default ───►  Miro light_yellow ───►  #FFF9B1
```

— delete the SVG renderer's private copy, and let each non-Miro renderer map those
two tokens to the same hex. That's the whole colour story for v1. (The existing
`SENTIMENT_TOKEN` map stays where it is for the optional sentiment path; it doesn't
need to become "semantic tokens" and the `header`/`negative` `light_pink` overlap is
a non-issue while the default is flat.) **BN is a jump-start, not a finished
analysis:** the value the researcher keeps is *headings + all the quotes about the
homepage from every user*, then the star/section/tag scope to surface the good ones
— they bring the interpretation. The board's two colours are scaffolding, not signal.

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
| **Colour** | two fixed (pink/yellow) → hex | two fixed (pink/yellow) → hex | n/a |
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
Renderer ports ~1:1; colour is trivial — just reproduce Miro's pink/yellow as hex.
Only net-extra work is auth: **15-min access tokens with rotating
refresh** force a real refresh loop sooner than Miro's longer-lived tokens, so a
paste-token cut is demo-grade and OAuth arrives early. Bulk 1000/call (vs Miro's 20)
makes large boards cheaper.

### Lucidspark — GO. Effort: **Same / slightly larger.**
Board-modelling work (coords, the two fixed colours, containers, rich text) is
identical to Miro. The difference is *architectural, not harder*: a **package serializer + ZIP
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
IR→renderer architecture** *as a server renderer*.

**But the scaffold is not wasted on FigJam — it front-loads it.** FigJam has by far
the largest user base of the four (it rides Figma's installed base), so the door
stays open deliberately. The honest path, if/when designer-demand appears, is a
**published FigJam plugin** that consumes the **same Board IR serialized as a JSON
manifest** — the layout engine, the IR, the two-colour palette, the anonymisation
boundary, and the manifest serializer are all **the same shared pieces** we build for
Mural and Lucidspark. Only the delivery runtime is new and larger (an in-editor
plugin + a human-run step + store review/distribution). So building the agnostic
scaffold now for the two GO boards is *also* the groundwork a FigJam plugin would
stand on later — FigJam is deferred, not abandoned. This sharpens
`design-miro-bridge.md`'s existing "FigJam is endgame, demand-gated" stance with a
concrete *why* and a concrete reuse path.

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
- Colour-by default — **resolved: flat (pink headers, yellow quotes) on every
  board.** Sentiment-colouring demoted to optional; custom-tag colouring (persona /
  cohort / campaign source / A/B) is the genuinely useful version, deferred. (See
  *Colour* above.)

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

1. **FigJam is the driver (largest user base); Mural/Lucidspark are picked off "for
   free along the way."** Mural and Lucidspark are GO for server push; FigJam is
   NO-GO for *server* push but reachable via an in-editor plugin — so the engine is
   built toward a **serialized Board Manifest** that the FigJam plugin (and Lucid's
   package) consume. (Research-confirmed against current vendor docs.)
2. **Colour is flat: pink headers, yellow quotes, everywhere** (Miro's `light_pink`
   / `light_yellow` reproduced on every board). Sentiment-colouring is a party trick,
   demoted to optional; custom-tag colouring is the real future win, deferred. The
   only colour work is a tiny two-token `board_palette.py` that deletes the SVG
   renderer's duplicate hex map — no semantic-sentiment-palette refactor.
3. **Defer the `BoardRenderer` Protocol, the rename, and the picker** until the
   second renderer exists — extract the Protocol from two real `push()` signatures
   (B2), do the `miro_board`→`board_layout` rename in that same commit, and build the
   picker only at 2+ connectable boards. No abstraction over a population of one.
4. **Order is IR→Manifest → Lucidspark → FigJam plugin; Mural + OAuth deferred.**
   Pointing at FigJam keeps OAuth *off* the critical path (the plugin authenticates
   in-editor; Lucid uses an API key) — only Mural needs OAuth, and only the ~Sept-2026
   Mural-friends test would pull it back. The manifest serializer is the keystone:
   FigJam's plugin and Lucid's `.lucid` package both consume a serialized whole-board
   document, so Lucid is the cheap dress rehearsal that de-risks FigJam.
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
9. **FigJam is a published plugin consuming the IR-as-manifest** — not a server
   renderer; the plugin (TS, store review, distribution, in-editor UX) is a real,
   separate project and the bulk of FigJam's cost. Only the engine spine
   (manifest serializer + Lucid dress rehearsal) is the shared/free part.

---

## Plan (build order — FigJam is the driver)

**Strategic re-point (28 Jun 2026): FigJam is the real prize; Mural/Lucidspark are
picked off "for free along the way."** FigJam has by far the largest user base, and
the road to it reshapes the engine in a way that *also* delivers the others cheaply —
and, counter-intuitively, **drops OAuth off the critical path.** The reasoning:

- FigJam has **no server write path** — the only route is a **published in-editor
  plugin that consumes a manifest** (a serialized Board IR). So the FigJam-advancing
  work is "make the IR a clean, versioned, serializable **document**," not "another
  REST renderer."
- **Lucidspark consumes a whole-board document too** (its `.lucid` package *is* a JSON
  board). Building Lucid is therefore the **dress rehearsal** that proves the
  document model end-to-end against a real API, with the cheapest auth (a paste-key),
  before any cost goes into the plugin. That is the free pickup, and it de-risks FigJam.
- **The FigJam plugin authenticates in-editor** (it runs as the user, in their Figma
  session) and Lucid uses an **API key** — so **neither needs BN-server OAuth.** OAuth
  was only ever forced by **Mural**, which is the one board that advances FigJam by
  nothing. So under this north star, **Mural and the whole OAuth build are deferred.**

Parsimony still holds: the rename / `BoardRenderer` Protocol trail the second real
consumer (the manifest), they aren't front-loaded.

| Milestone | What | Toward FigJam |
|---|---|---|
| **✅ B0 — Palette** | `board_palette.py` (done) — flat pink/yellow baseline, deletes the SVG hex duplication. | Foundation. |
| **F1 — IR → Manifest** | `board_manifest.py`: serialize the Board IR to **versioned JSON** (`ensure_ascii=True`, build-dict-once, schema `version` field). Do the `miro_board`→`board_layout` rename here — the manifest is the 2nd real consumer, so the name now describes two things. | **This *is* the FigJam plugin's input contract.** Version from day one (a published plugin lags BN releases). The SVG preview already renders the IR, so it's the creds-free way to eyeball a manifest. |
| **F2 — Lucidspark renderer (dress rehearsal)** | IR → `.lucid` package (wrap the serialized board) → `POST /documents` via API key; `routes/lucid.py`; `lucid` keychain+env; SECURITY note; serialized-payload anonymisation test. Extract the renderer seam (Miro REST + Lucid package = two real shapes → hoist `build_board`, extract `BoardRenderer`). | Proves **whole-board-as-document** against a live API, cheapest auth, before the plugin. The free product win. |
| **F3 — FigJam plugin (the prize)** | Published Figma/FigJam plugin (separate TS repo): reads a BN manifest → loops `createSticky()` + sections + text in-editor. BN side: a "Download FigJam manifest" export + the handoff UX (download → open FigJam → run plugin → pick file). **Re-verify Figma's API here** — if a server write path has shipped by then, FigJam collapses into a normal renderer (upside). | The goal. Note: the *plugin* is a real, separate project (TS, store review, distribution, in-editor UX) — only F1–F2 are shared/free. |
| **— Mural (deferred sidetrack)** | `mural_client.py` (port the Miro item-loop), `routes/mural.py`, and the **shared OAuth build** it forces (15-min rotating tokens; `ASWebAuthenticationSession`). | **Nothing.** Per-item REST, consumes no manifest, needs the OAuth the FigJam road skips. Pick off only if the ~Sept-2026 Mural-friends test specifically requires it — that test is the *only* thing that pulls Mural + OAuth back onto the path. |
| **— Picker UX (deferred)** | One "Send to a whiteboard…" entry + remembered board — only once 2+ boards are genuinely connectable. Until then ship each as a concrete row. | Orthogonal to FigJam. |

**Security disciplines for the Lucid renderer (F2):**
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
5. Colour — pink headers + yellow quotes render correctly on that board (flat
   baseline; no sentiment tinting).
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
