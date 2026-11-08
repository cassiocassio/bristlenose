# The in-Miro app: Bristlenose boards drawn inside Miro, no sign-in

Status: built, deployed to bristlenose.app/miro and run on a real Miro board, 8 Nov 2026 ("Board built: 10 quotes" from the published sample). Owner decision the same day, recorded in the
maintainer's board-platforms register.

## Why

Send to Miro today pushes a board through Miro's REST API with the researcher's
token. Getting that token is the problem:

- Miro's one-click sign-in needs the app's client secret at the token swap.
  PKCE without it was refused twice on 8 Nov 2026 (`401 tokenNotProvided`, query
  string and form body; `experiments/miro-pkce-probe/`).
- Holding the secret means a relay server. The owner rules out servers, and a
  company Miro admin is very likely to veto "a third party holds a long-lived
  token to our boards".
- The interim route, a developer token, makes a researcher create a developer
  team and app, and boards made there carry Miro's developer marking, so they
  cannot go to a stakeholder. It stays for keen beta testers, labelled interim.

Miro's own answer for an app with no server is a **Web SDK app**: a web page
Miro loads in a panel inside the user's open board. It acts as that user,
through Miro's SDK, only while the board is open. No token leaves Miro and
there is no secret anywhere.

## Shape

Static files at `https://bristlenose.app/miro/` (the hosting choice is being
revisited in its own session):

- `index.html`: the app URL. Miro runs it headless when a board opens; it only
  listens for the toolbar icon and opens the panel.
- `app.html` + `app.js`: the panel. Choose, drop or paste a Bristlenose board
  file; it draws the board into the open Miro board, with progress and Stop.

The researcher's steps: in Bristlenose, download or copy the board file (the
same file the FigJam plugin reads); in Miro, open the Bristlenose panel and
choose, drop or paste it.

## What is reused from the FigJam plugin

- **The board file and its contract**: `bristlenose-board` v1, written by
  `bristlenose/board_manifest.py`, pinned by `tests/fixtures/figjam-board-v1.json`.
  No new format, no Bristlenose change needed to start.
- **`figjam-plugin/src/board.ts`** (read and refuse) and
  **`figjam-plugin/src/clipboard.ts`** (paste flavours), imported as they are.
  Both are pure and already tested.
- **The panel's behaviour**: choose / drop / ⌘V, a progress bar, Stop, one-line
  refusals, status set with `textContent` only.

## What is new

1. **`miro-app/src/layout.ts`: the Send to Miro layout, ported.** The in-Miro
   board must look like the REST one, so testers' feedback on sticky layout
   carries over. Ported from `bristlenose/board_layout.py`: sticky width from
   the square root of the text width (`SIZE_K` 17, East Asian wide characters
   count two), the shape's aspect, split parts stacked with `set_overlap`
   (past Miro's shadow, `MIRO_PAPER` 0.825, then one x-height, 5) and stepped
   right by 5, column width from the widest set, gaps 36 / 24, frame padding
   28, frames 72 apart, a 300-wide header sticky per column. Positions are
   relative to the board's top-left; the app adds an origin.
   **Parity is mechanical**: a Python test computes the expected geometry for
   the fixture with `board_layout`'s own functions and checks it against
   `tests/fixtures/miro-inboard-layout-v1.json`; the TypeScript test plans the
   same fixture and compares with that JSON. Change either side and a test fails.
2. **Sticky content, as Send to Miro writes it.** Header `<strong>label</strong><br>count`;
   earlier parts the words alone; the last part the words, then
   `<br><i>attribution · <a href="…">▶ clip</a></i>`. HTML-escaped, cut only if
   past Miro's 6,000-character limit. Colour tokens are Miro's own named
   colours, passed straight through; an unknown token falls back to
   `light_yellow`.
3. **`miro-app/src/draw.ts`: the only part that needs Miro.** Finds empty
   space near the viewport (`miro.board.findEmptySpace`), creates the frames,
   the title text and the stickies (centre coordinates, width only), groups each
   split quote's parts, then zooms to the result. Stop is read between quotes.
   A refusal that looks like a rate limit or timeout is retried twice with a
   pause (about 2,000 items a minute per user); anything else is said at once,
   in Miro's own words, with how far it got. Stop is honoured before a wait.
   A file with no quotes is refused before anything is drawn, as Send to Miro
   refuses an empty selection.
   As in Send to Miro, stickies are not made children of their frame (one fewer
   call each, and the REST board does not either).
4. **Hosting**: `content/miro/` in the website repo, with its own `.htaccess`
   lifting the site-wide no-framing headers for that folder only: framing by
   `miro.com` alone. Scripts may come from any HTTPS source for now, because
   `miro.js` is a loader that asks the Miro page for the real SDK's address and
   injects it, and Miro does not document that host; tighten once a real board's
   console shows it. Long-term host: see the maintainer's register (GitHub Pages
   at `miro.bristlenose.app` recommended, owner to rule).
5. **Miro app settings** (owner, once): App URL
   `https://bristlenose.app/miro/index.html`, scopes `boards:read`,
   `boards:write` (already set), an icon.

## Company Miro accounts (research, 8 Nov 2026)

- Members can add any app by default. Business and Enterprise team admins can
  stop non-admins installing apps; Enterprise company admins can restrict to an
  approved list.
- **Approval is by client ID**, so an unlisted app shared by install link can be
  approved like a Marketplace one. On Enterprise a blocked member gets "Send
  request" with a reason, which emails every company admin.
- A Marketplace listing is not a near-term route (since 2026: partnership
  approval, more than 50 monthly active users in two consecutive months,
  installs in more than 10 organisations, then 8–12 weeks of review).
- So the help text for researchers names the client ID their admin will ask for.

## Out of scope tonight

- Renaming Bristlenose's "Send to FigJam" download to a board-file export for
  both whiteboards (the file already works for both). The FigJam export is
  still behind `featureFlags.figjamExport`, so until it is unparked testers
  use the flag or a sample file.
- Marketplace listing, the app icon artwork, localising the panel (FigJam's
  panel is English too; the board's own words come localised in the file).
- Making stickies children of frames.

## Tests

- TypeScript (vitest): plan parity against the Python-generated layout JSON;
  sticky content composition and escaping; colour fallback; clip links only
  when `safeClipUrl` accepts them; draw.ts against a fake `miro.board` (order of
  calls, grouping of sets, Stop between quotes, a retried failure, the summary).
- Python: the layout JSON is regenerated from `board_layout` and must match the
  checked-in file.
- By hand, once deployed: a real board, a file with split quotes and a clip
  link, a paste, Stop part-way.

## Related

- `docs/research/miro-integration-2026-11.md`: everything learned on 8 Nov 2026,
  measured and researched, with sources. Read it before re-opening any Miro
  sign-in question.
- `docs/design-miro-bridge.md`: the REST Send to Miro (developer token), kept for
  keen beta testers.
- `docs/archive/design-miro-oauth-one-click.md`: the archived one-click sign-in
  plan and its mockups.
- `miro-app/README.md`: build, test, the layout contract, deploy.
