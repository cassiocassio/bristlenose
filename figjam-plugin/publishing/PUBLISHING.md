# Publishing the Bristlenose board plugin

Everything for the Figma Community submission, drafted 19 Oct 2026. The
listing facts come from Figma's help centre as of that date (the "Publish
plugins" and "Plugin review guidelines" articles); re-check the dialog itself,
because Figma does not publish its field limits.

## What's here

| File | What it is |
|---|---|
| `icon-128.png` | The listing icon, 128×128: the app icon, resized |
| `cover-1920x1080.png` | The thumbnail. The board is a real screenshot of the plugin drawing `sample-board.json` in FigJam |
| `cover-src/` | The cover's HTML and its inputs, to adjust it (render notes inside) |
| `sample-board.json` | An invented study for reviewers and first-time users. Written by `board_manifest`; `tests/test_figjam_sample_board.py` and the plugin's own tests keep it valid |

## Before you submit

1. **Two-factor sign-in** on the Figma account that will publish (Settings ›
   Security). Figma won't let you publish without it.
2. **Build and try it once more** in the Figma desktop app:
   ```bash
   cd figjam-plugin && npm ci && npm run build
   ```
   Plugins › Development › Import plugin from manifest…, choose
   `figjam-plugin/manifest.json`, then run it on `publishing/sample-board.json`.
   Do the checks in "By hand" below at the same time.
3. **Record the demo video** (script below). Figma's reviewers have asked
   other developers for one, and there's no field for reviewer notes, so have
   it ready and link it if asked.
4. **Push `main`** so the sample-board link in the description resolves.

## Submitting

1. Figma desktop app › Plugins › Manage plugins, then **Publish** on Bristlenose board.
2. The dialog will say the manifest id is invalid (`bristlenose-board-dev` is a
   placeholder). Click **Generate ID**, put the new id in
   `figjam-plugin/manifest.json`, rebuild, and commit that one-line change to
   `main`. Every later update must keep the same id, or it becomes a second
   listing.
3. Fill in the pages as below. **Skip "Data security"** on the first
   submission: it's optional, and its own review can add two weeks. The answers
   are drafted below for later.
4. Publish, then watch the account's email, including spam, for the decision.
   Reports from 2026 put review at two to eight weeks.

### Describe

**Name:** Bristlenose board

**Tagline:** Build a research board of sticky notes from a Bristlenose board file.

**Description:**

> Bristlenose board builds a research board in FigJam from the board file that
> Bristlenose exports.
>
> Bristlenose is open-source software for user researchers. It turns interview
> recordings into quotes, sections and themes, and its **Send to FigJam** export
> saves a board file. This plugin reads that file and draws the board. You need
> a board file from Bristlenose (bristlenose.app), or the sample below.
>
> **What you get**
> - A section for the study's sections and one for its themes, with a column
>   for each, headed by a pink label with its quote count
> - Each quote on its own sticky note, attributed to a participant code and
>   timecode (— P2 · 14:05), never a participant's name
> - Long quotes broken into two or three sticky notes, grouped, so you can
>   delete the weaker parts and keep the rest
> - Square or wide sticky notes, as chosen in Bristlenose
> - Links to video clips, where the researcher added them
>
> **How to use it**
> 1. In Bristlenose, choose Export › Send to FigJam… and save the board file.
> 2. Open a FigJam board and run Bristlenose board.
> 3. Choose the file, or drop it on the plugin's window.
>
> One undo removes everything the plugin drew.
>
> **Privacy.** The plugin has no network access. It draws only what the board
> file holds, into the board you have open, and sends nothing anywhere.
>
> **Try it without Bristlenose:** download the sample board file from
> https://raw.githubusercontent.com/cassiocassio/bristlenose/main/figjam-plugin/publishing/sample-board.json

The description avoids any AI wording on purpose: Figma has rejected plugins
that overlap its own AI and MCP features.

**Tags** (Figma's current article says up to 5): user research, interviews,
sticky notes, affinity mapping, research synthesis

**Category:** the closest research or productivity category the dialog offers.

### Images

Icon: `icon-128.png`. Thumbnail: `cover-1920x1080.png`. The carousel (up to
nine images or videos) is optional; the demo video can go there too.

### Final details

- **Support contact:** `https://bristlenose.app/docs/send-to-figjam.html` once
  the website's `figjam-launch` branch is deployed, or an email address until
  then. Figma accepts an email, a website or a help-centre link.
- **Comments:** your call.
- **Playground file** (optional): a FigJam file people can try the plugin in.
  The scratch file "Bristlenose FigJam spike (scratch)" already holds the
  sample board, drawn by the plugin, beside the earlier test boards. To use it,
  delete everything but the sample board and rename it, or start a fresh file.
- **Network access** is read from the manifest (`"none"`), and should show as
  **No access**.

## Data security answers, for later

Optional at first submission. If you fill it in later, these are the facts:

| Question | Answer |
|---|---|
| Do you host a backend that receives Figma data? | No. |
| Does the plugin make network requests to services you don't host? | No. It declares no network access (`networkAccess: none`). Clip links are written into sticky text; the plugin never fetches them. |
| Does it require user authentication? | No. |
| Does it store data read from the Figma API? | No. It reads the size and position of what is already on the page, only to place the new board beside it, and keeps nothing. |
| How do you manage updates? | Published from the public repository (`figjam-plugin/` in github.com/cassiocassio/bristlenose). The board file format is versioned, and the plugin refuses a file it would draw wrong. |

## Demo video (about 45 seconds)

1. Bristlenose with a project open: Export › Send to FigJam…, the dialog with
   the board name filled in, **Download board file** (8 s).
2. FigJam, an empty board: run Bristlenose board, choose the file (8 s).
3. The board drawing, with the progress bar (10 s).
4. Zoom in on a column, ⌘-click one part of a long quote's set and delete it
   (10 s).
5. Press ⌘Z once and the whole board goes (5 s).

Use the sample project, or a study whose participants agreed to it. The board
shows quote text, and the video will be public if it goes in the carousel.

## By hand, before submitting

Things no test can see:

- [ ] ⌘-click selects one part of a set; Delete removes just that part.
- [ ] One ⌘Z removes the whole board, after a full build and after **Stop**.
- [ ] A long label wraps inside its pink header and nothing is cut off.
- [ ] The plugin panel in FigJam's light and dark themes.
- [ ] Bristlenose's Send to FigJam dialog in light and dark, web and Mac.
      To switch the Mac menu item on before launch:
      ```bash
      defaults write app.bristlenose BristlenoseFigJamExport -bool YES
      ```
      For the web panel, set `figjamExport: true` in
      `frontend/src/utils/featureFlags.ts` locally and don't commit it.
- [ ] A refusal: drop a file that isn't a board file (any other `.json`) and
      read the sentence.

## After approval

1. Put the Community URL in place of `PLUGIN-ID` in `docs-src/send-to-figjam.md`
   on the website's `figjam-launch` branch, and set the "Last updated" dates on
   `privacy.html` and `terms.html` to the deploy day.
2. Merge `figjam-launch` in this repo. It turns both flags on, updates
   `SECURITY.md`, and changes the next-steps line to "Then, in FigJam:" in all
   21 languages.
3. Merge the website's `figjam-launch` and deploy from a clean checkout (see
   `CLAUDE.md` on `deploy.sh`).
4. Release as usual: a changelog entry under **New**, which means a minor bump.
