# Cover image source

`cover.html` is a 1920×1080 page; `sections.png` and `themes.png` are
screenshots of the plugin drawing `../sample-board.json` in a real FigJam file
(Figma MCP `get_screenshot`, 19 Oct 2026). `fish.png` is the app icon.

Render it with the Playwright the e2e suite already installs:

```bash
cd e2e && node -e 'const {chromium}=require("playwright");(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080}});await p.goto("file://"+require("path").resolve("../figjam-plugin/publishing/cover-src/cover.html"));await p.screenshot({path:"../figjam-plugin/publishing/cover-1920x1080.png"});await b.close();})()'
```

If the board's look changes, redraw the sample in FigJam and replace the two
screenshots, so the listing shows what the plugin really draws.
