# Bristlenose — the in-Miro app

Draws a Bristlenose research board inside Miro from the board file Bristlenose
downloads (the same file the FigJam plugin reads): a frame per kind, a pink
header sticky per column, the quotes beneath, split quotes grouped, clip links
where there are any. It lays the board out exactly as Send to Miro does.

It has no server and no sign-in. Miro loads these static pages in a panel inside
the user's open board, and the panel draws through Miro's Web SDK, acting as that
user only while the board is open. Design and decisions:
`docs/design-miro-in-board-app.md`.

## Files

- `src/layout.ts` — Send to Miro's layout and sticky content, ported from
  `bristlenose/board_layout.py` and `server/miro_export.py` (pure)
- `src/eastAsianWide.ts` — Python's East Asian Width table, generated (do not edit)
- `src/draw.ts` — draws a plan with Miro's SDK (the only part that needs Miro)
- `src/app.ts`, `src/app.html`, `src/app.css` — the panel
- `src/index.ts`, `src/index.html` — the app URL Miro loads unseen; opens the panel
- `hosting/.htaccess` — lifts the website's no-framing headers for this folder only
- `icons/outline.svg`, `icons/colored.svg` — the toolbar (one colour) and app-panel icons Miro's app settings take: square SVG under 5,000 bytes. The fish is traced from the Mac app icon's colour layer (`desktop/.../AppIcon.appiconset/layers/foreground-default.png`) into one path
- The board file is read by `figjam-plugin/src/board.ts` and `clipboard.ts`, imported as they are

## The layout contract

`tests/test_miro_inboard_layout_contract.py` lays out the board-file fixture's own
columns with `bristlenose.board_layout` and writes
`tests/fixtures/miro-inboard-layout-v1.json`: every sticky's box, colour and
content, the frames and the title. `src/layout.test.ts` plans
`tests/fixtures/figjam-board-v1.json` and must arrive at the same numbers. After a
deliberate change on the Python side:

```bash
BRISTLENOSE_REGENERATE_BOARD_FIXTURE=1 .venv/bin/python -m pytest tests/test_miro_inboard_layout_contract.py
```

## Build and test

```bash
npm install
npm test
npm run typecheck
npm run build      # dist/ is the whole site folder, .htaccess included
```

## Deploy

`dist/` is copied to the website repo's `content/miro/` and published with its
`deploy.sh`. In the Miro app's settings, the App URL is
`https://bristlenose.app/miro/index.html`, with scopes `boards:read` and
`boards:write`. Researchers add the app to their team once from its install link;
a company admin who restricts apps approves it by its client ID.
