# Session tapestry

An expandable timeline slice under each row of the Sessions grid, showing:
- section flags
- speaker clips on moderator and participant tracks
- sentiment bars (positive above the line, negative below)
- theme spans

The design mockups are `docs/mockups/session-tapestry.html` (first sketch) and `docs/mockups/session-tapestry-scale.html` (the scale rule, from measured transcript rates).

## Files

| File | What it is |
|---|---|
| `build.py` + `template.html` | Builds the tapestry from a real output folder, drawn in the real Sessions-grid markup with the shipped theme inlined |
| `colour_lab.py` + `colour-lab.html` | Samples frames from every distinct recording under a folder, so the clip-colour algorithm can be tuned live |

Both pages carry participant content, so write them to a gitignored, private folder:

```bash
.venv/bin/python experiments/session-tapestry/build.py <project>/bristlenose-output -o <private>/tapestry.html
.venv/bin/python experiments/session-tapestry/colour_lab.py <folder-of-projects> -o <private>/colour-lab.html --per-role 4
```

The app's preview pane will not open a local page much over 500 KB. That is why `--per-role 4` is used and the thumbnails are downscaled. A normal browser opens the larger pages fine.

## Settled (6 Oct 2026)

- **Scale:** one shared scale per project, fitted to the longest session and held between 1 and 4 s/px. The speaker lane switches from clips to slivers above 2.5 s/px. Zoom runs from that fit down to 0.25 s/px.
- **Top lane:** sections, not s08 topics. "Topics" is not a product noun. Each section is flagged at its first quote in the session, which is the anchor the row's User journey chain links to.
- **Clip colour:** the per-turn scene colour, in seven steps. These are the colour lab's defaults:
  1. Crop black bars: drop an edge row or column when 85% of its pixels have luma below 30.
  2. Ignore pixels with luma below 18. Keep whites.
  3. Cluster the remaining pixels in OKLab, k = 4.
  4. A cluster is eligible only if it holds at least 15% of the pixels.
  5. Pick the most colourful eligible cluster.
  6. Tone it: map OKLab L into 0.42–0.88 and multiply chroma by 1.4.
  7. If the cluster sets of two speakers are within a scene distance of 6, treat them as one scene and do not assign per-speaker colours.

## In the pipeline (6 Oct 2026)

The clip colour is computed by `bristlenose/utils/scene_colour.py`, which `Pipeline.run()` calls just before render. It writes `.bristlenose/intermediate/scene-colours/<session>.json`: one `{t0, t1, speaker, colour, share}` per turn. The file is cached by the video's identity and the turn boundaries, so a re-run costs nothing until the recording or the speaker turns change. A failure logs a warning and leaves the session without colours, the same as thumbnails.

**The module's constants are the colour lab's defaults.** To retune, regenerate the lab, move the handles, then copy the new values into the module and into the `P` table at the top of `colour-lab.html` in the same commit. The lab still carries the per-speaker distinctness and same-scene handles. The pipeline doesn't use them, because the lab showed the picture never changes with who is speaking.

**In the app (6 Oct 2026):** `GET /api/projects/{id}/tapestry` (`bristlenose/server/routes/tapestry.py`) serves every session's turns, section flags and quotes from the database, so hidden quotes, quote edits and heading renames apply. It matches each turn to a scene colour by time, so a speaker edit made in serve doesn't orphan the colours. The route is embedded in the HTML export. `frontend/src/components/SessionTapestry.tsx` draws it as a disclosure under each Sessions-grid row. The chevron sits in the ID cell, so the grid gains no column. The component is lazy-loaded; only `utils/tapestryScale.ts` is on first paint. The CSS is `bristlenose/theme/organisms/session-tapestry.css`.

Not wired yet:
- `analyze` (no video) and render-only runs don't compute colours.
- Projects analysed before this change show neutral clips until their next `run`.


**Decided (6 Oct 2026): the zoom has no keyboard shortcut.** ⌘+ and ⌘− stay the browser's text zoom, because readers rely on text size more than they would on a timeline zoom. Don't add a shortcut.

## Measured

- **The video never flips with the speaker.** Across 25 distinct recordings in the maintainer's test corpus, all 12 with two speakers showed the same picture whoever spoke (scene distance 0.3–4.6). The speaker is shown by the track; the colour shows what was on screen.
- **Keyframe colour sampling is cheap.** It takes about 1.5 s per hour of video (15 s for the 9 hours of the FOSSDA oral histories), cheap enough to run in the pipeline beside thumbnail extraction.
- **Some transcripts have coarse or mislabelled turns** (FOSSDA s5 has the narrator on `m1` from about 10 minutes in). The slice makes this visible at a glance.
- **Quote extraction does not record which words carried a quote's sentiment.** `verbatim_excerpt` is only the first 200 characters of the quote.
