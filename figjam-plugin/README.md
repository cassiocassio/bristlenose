# Bristlenose board — FigJam plugin

Builds a research board in FigJam from the board file Bristlenose downloads:
one section per frame, a pink header sticky per column, the quotes beneath in
yellow with their attribution in italics and a clip link where there is one.
FigJam has no way for an outside app to write to a board, so the plugin draws
it inside the editor. Design and decisions: `docs/design-board-integrations.md`.

It declares no network access. Everything it draws comes from the file.

## Files

- `src/board.ts` — reads and checks a board file; refuses one it would draw wrong
- `src/plan.ts` — the stickies to draw, with every text range worked out (pure)
- `src/draw.ts` — draws a plan with the Figma API (the only part that needs Figma)
- `src/code.ts` — the plugin's entry: panel, canvas drop, progress, summary
- `src/ui.html`, `src/ui.ts` — the panel

The file format is pinned by `tests/fixtures/figjam-board-v1.json`, which
Bristlenose's tests generate and `src/plan.test.ts` reads, so neither side can
change it alone.

## Build and test

```bash
npm install
npm test
npm run typecheck
npm run build
```

`npm test` runs in Node, which has browser features Figma's plugin sandbox
lacks (`URL`, `structuredClone`). One test plans the fixture with them removed,
but the drawing itself is only proven in a real FigJam file.

## Try it in FigJam

Needs the Figma desktop app. Build first, then in any FigJam board:
Plugins › Development › Import plugin from manifest… and choose
`figjam-plugin/manifest.json`. Run **Bristlenose board** and choose a file from
Bristlenose's FigJam download, or `tests/fixtures/figjam-board-v1.json`.

## Before publishing to Figma Community

See "Plugin build notes" in the design doc: two-factor auth on the publishing
account, a 128×128 icon and a 1920×1080 thumbnail, a support contact, and a
check that the panel's inline script runs with network access set to none. The
`id` in `manifest.json` is a placeholder until Figma assigns one.
