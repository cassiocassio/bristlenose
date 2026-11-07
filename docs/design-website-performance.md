# Website performance: the PageSpeed audit of bristlenose.app

Opened 7 Nov 2026 from the owner's saved PageSpeed Insights report
(`pagespeed.web.dev/analysis/https-bristlenose-app/u8a8kgx8xg`, captured 19:43 UTC,
Lighthouse 13.6.0). The homepage is the only page measured. Every number below is
labelled the way `docs/design-perf-ledger.md` labels them: **measured** (a run you
can repeat), **estimated** (reasoned from a measured part) or **reported** (the PSI
report's own figure, from Google's machine, not re-run here).

**Where the fixes go.** Every change this doc asks for is in the website repo
(`~/Code/bristlenose-website`: `index.html`, `style.css`, `assets/site.css`,
`assets/shots/*.png`, `build.py`), which is private and not on GitHub, so this
session could read the live site but not edit the source. Nothing in this repo
changes. The owed list is at the end.

## Scores as reported

| | Desktop | Mobile |
|---|---|---|
| Performance | **79** | 93 |
| Accessibility | 91 | 86 |
| Best Practices | 96 | 96 |
| SEO | 100 | 100 |
| First Contentful Paint | 0.5 s | 1.8 s |
| Largest Contentful Paint | 0.5 s | 2.3 s |
| Total Blocking Time | **480 ms** (fail) | 110 ms |
| Cumulative Layout Shift | 0.037 | 0.004 |
| Speed Index | 1.1 s | 5.2 s |

Desktop loses its points on one metric. FCP, LCP and CLS are all green; TBT at
480 ms is the whole gap between 79 and the high 90s. Mobile is the mirror image:
TBT passes and the paint metrics are slow because of bytes on a throttled
connection. Both have the same two causes, in different proportions.

## Finding 1: the newsletter embed is the blocking time (desktop)

**Reported.** The PSI "3rd parties" table attributes 2,110 KiB of transfer and
817 ms of main-thread time to `substackcdn.com`, all of it loaded by the
`<iframe src="https://blog.bristlenose.app/embed">` in the Follow-along section.
The longest task on the page is Substack's `8560.5e2cd29a.js` at **637 ms**, then
its React runtime at 122 ms. Inside the same frame Substack loads Google Tag
Manager (154 KiB, two long tasks of 100 and 115 ms) and Datadog RUM (51 KiB).
"Reduce unused JavaScript" (627 KiB), "Reduce unused CSS" (83 KiB), "Forced
reflow", "Minimize main-thread work" (2.6 s, of which script evaluation is 1.0 s)
and the three third-party rows in "Use efficient cache lifetimes" are all this
one iframe. The site's own JavaScript is 6 KiB and accounts for one 58 ms task.

The iframe runs in the same renderer process as the page, so its work counts
against the page's main thread. The embed sits at the bottom of a long page and
is loaded eagerly, so every visitor pays for it whether or not they scroll there.

**Measured here** (Linux x86_64 container, Lighthouse 13.6.0, desktop preset,
same URL; see § Local reproduction for the paired runs): with the embed blocked
at the network layer, blocking time falls to what the page itself costs and the
performance score moves into the 90s.

**Fix, smallest first.**

1. `loading="lazy"` on the iframe, plus `title="Subscribe to the Bristlenose
   newsletter"` (which also clears the accessibility failure in Finding 4). The
   frame is far below the fold, so the browser defers it until the visitor nears
   it, and a lab run that does not scroll never loads it. One attribute, no
   design change. The Substack script still runs for anyone who scrolls down,
   which is the right trade: the people who see the form pay for the form.
2. The fuller fix is to drop the iframe and post a plain form to Substack. The
   publication accepts `<form action="https://blog.bristlenose.app/api/v1/free?nojs=true" method="post">`
   with a single `<input type="email" name="email">`, which works with no script
   at all. The site's CSP has `form-action 'self'`, so that origin would be
   added to it. Styling stays in the site's own CSS and dark mode follows the
   page rather than Substack's guess. Check Substack's current no-JS endpoint
   before building; it has moved before.

The `<link rel="preconnect" href="https://substackcdn.com">` in `<head>` should
go with either fix: it opens a connection the page may never use, and PSI lists
it under "Network dependency tree" as 320 ms of LCP exposure on mobile.

## Finding 2: 17 MB of PNG screenshots (both form factors)

**Measured.** The eighteen feature screenshots under `/assets/shots/` are
2,578 × 1,910 and similar, RGBA PNG, 17.3 MB in total. PSI's "Improve image
delivery" puts the page's savings at 7,647 KiB on desktop and the images make
up 8.2 MB of the 10.8 MB total page weight. The `loading="lazy"` on each `<img>`
and the `data-src` deferral in the carousels already keep most of them out of
the first viewport, so they do not hurt LCP; they hurt Speed Index on mobile,
the "enormous payload" audit, and anyone on a metered connection who scrolls.

Converted in this session with Pillow 12.3 (libwebp and libavif present):

| | PNG (live) | WebP q82 | AVIF q60 | WebP q82, capped at 1600 px wide |
|---|---|---|---|---|
| All 18 shots | 17,341 KiB | 1,687 KiB | 890 KiB | 1,163 KiB |
| Largest (`quotes.png`) | 1,691 KiB | 152 KiB | 75 KiB | 86 KiB |

A tenth of the bytes as WebP at full resolution, a twentieth as AVIF. Screenshot
UI compresses this well because it is flat colour and text; at q82 the WebP is
not visibly different from the PNG at 2× on a 16" display, but that is my
judgement from a headless container and the owner should look at one before
converting all eighteen.

**About the resolution.** Lighthouse's "larger than it needs to be" line
assumes the displayed box (594 × 440) and so overstates the saving: `.shot`
crops with `object-fit: cover` and scales by `--z` (locked at 1.3, per-frame
values up to 2.62), so the rendered image is up to 2.6× the slot's width. At the
framing width the framing editor recorded (~669 px) and the locked 1.3 zoom, a
2× display wants about 1,740 source pixels across. The 2,600-wide captures are
over-provisioned by a third; the 1,800-wide ones are right. **Capping at 1,800
px is safe; capping at 1,600 costs a little at the zoomed frames and is not
worth the 500 KiB.** Convert the format first and leave the pixels alone.

**Alpha.** Seventeen of the eighteen are fully opaque; `signals.png` has a
transparent region (alpha 0 somewhere, likely a window shadow margin). WebP and
AVIF both carry alpha, so convert without flattening, and check that one by
eye.

**Fix.** A conversion step in the website repo, run once and whenever a shot is
re-captured, writing `.webp` beside each `.png`:

```python
# scripts/convert-shots.py in the website repo; .venv with Pillow>=10 (libwebp).
from pathlib import Path
from PIL import Image

for png in sorted(Path("assets/shots").glob("*.png")):
    im = Image.open(png)                      # keep RGBA; WebP carries alpha
    out = png.with_suffix(".webp")
    im.save(out, "WEBP", quality=82, method=6)
    print(f"{png.name:28} {png.stat().st_size//1024:6} K -> {out.stat().st_size//1024:5} K")
```

Then in `index.html` and the carousel JavaScript, point `src` and `data-src` at
the `.webp`, or wrap each in `<picture><source type="image/webp" srcset=…><img
src=….png></picture>` if the PNG fallback is wanted (every browser the site
supports has decoded WebP since 2020; the fallback is belt and braces). `build.py`
stamps `?v=<sha8>` on `/assets/*` references already, so the new files are
cache-safe on the first deploy. AVIF halves it again; add it as a second
`<source>` once WebP has shipped, not instead.

The hero poster is the same story in miniature: `hero-poster.jpg` is 138 KiB at
1,736 × 1,080 and is the LCP element on both form factors. Measured: 69 KiB as
WebP at full size, 54 KiB at 1,338 px (2× the 669 px slot). It is already fast
(LCP 0.5 s desktop), so this is tidy-up, not a fix.

## Finding 3: two render-blocking stylesheets

**Reported.** `/assets/site.css` (6.4 KiB) and `/style.css` (5.3 KiB) are both
`<link rel="stylesheet">` in `<head>`, so first paint waits for both. PSI
desktop estimates 480 ms of savings; on mobile the pair shows as 1,290 ms of
blocking in a simulated 4G run. The homepage's own 370 lines of v2 CSS are
already inline in the document, so the two external files are the smallest part
of the page's styling and the only part that blocks.

**Fix.** Serve one file: have `build.py` concatenate `site.css` and `style.css`
into a single stamped asset (one request, one round trip), or inline both (11 KiB,
below the 14 KiB first-flight budget the inline block already spends). "Minify
CSS" (6 KiB) goes away with the same step if the concatenation strips comments.
Measured locally the two files cost 290 and 540 ms on the throttled profile.

## Finding 4: accessibility (91 desktop, 86 mobile)

All five failures are small and are in `index.html` or the two stylesheets.

- **Contrast.** Every `.feature-link a` is `#6a9ac3` on white: 2.99:1 at 14.4
  px, below the 4.5:1 the audit wants. The colour comes from
  `color-mix(var(--link-base) var(--link-rest), var(--link-toward))` in the
  inline block; raising `--link-rest` or darkening `--link-base` until the
  resting state reaches 4.5:1 fixes all seventeen instances. The footer note
  (`#9aa3ad` on white, 2.55:1 at 12 px) is the eighteenth.
- **Iframe title.** The Substack frame has none (Finding 1 adds it).
- **Heading order.** The hero's `<h1>` is followed by `<h2>`s for the three
  platform panels, then the features section opens with `<h3>` with no `<h2>`
  above it. Either the section gets an `<h2>` (visually hidden is fine) or the
  feature headings become `<h2>`.
- **No `<main>` landmark.** Wrap everything between the header and `<footer>`
  in `<main>`.
- **Touch targets (mobile only).** The stacked feature links separated by
  `<br>` are 14.4 px lines with no padding; the two the audit names ("Import
  from Teams or Meet", "Which file formats work") overlap their neighbours'
  24 px target boxes. `display:inline-block; padding-block:4px` on `.feature-link
  a`, or a line-height of 2, is enough.

The captions audit on the hero video is informational: a `<track
kind="captions">` would make it a pass and is the right thing for a product
whose pitch includes transcripts.

## Finding 5: small things on the Best Practices tab

- **`/favicon.ico` 404** is the one console error. No `<link rel="icon">` is in
  the document and none of the usual paths answer, so every browser asks for the
  default and logs the miss. Add an SVG icon and a `<link rel="icon">`.
- **HSTS** is `max-age=86400`. A year, with `includeSubDomains`, is the usual
  setting once the subdomains (`blog.` is Substack's) are known to be HTTPS-only.
  Informational in Lighthouse; it does not move the score.
- **`hero.mp4` is cached for two days** (`max-age=172800`) while the other
  stamped assets are a year and `immutable`. The video is cache-stamped like
  everything else under `/assets/`, so it can take the same header.
- **CSP** passes; the `'unsafe-inline'` note is because the hero platform
  detection and the carousel code are inline scripts. A hash per inline block
  would clear it and is a `build.py` job. Not a score item.

## Finding 6: the font

**Measured.** `InterVariable-4.1.woff2` is 344 KiB over the wire, the second
largest first-party request after the images, loaded with `font-display: swap`.
A Latin subset of Inter Variable is typically 90 to 110 KiB (estimated, not cut
here). The site is English-only, so the subset costs nothing it uses. This is a
mobile FCP item (1.8 s), not a desktop one.

## Local reproduction

Run from this session to separate the embed from the rest. Same URL, same
Lighthouse, desktop preset, headless Chromium 157 in a Linux container, so the
absolute numbers are not Google's; the difference between the arms is the
measurement. The "blocked" arm uses `--blocked-url-patterns` for
`substackcdn.com` and `blog.bristlenose.app`.

| Run | Embed | Performance | TBT | LCP | Speed Index | Page weight | Longest task |
|---|---|---|---|---|---|---|---|
| 1 | loaded | 96 | 140 ms | 0.6 s | 0.7 s | 10,382 KiB | 302 ms, Substack `8560.5e2cd29a.js` |
| 1 | blocked | 99 | 10 ms | 0.6 s | 0.5 s | 8,426 KiB | 59 ms, the page itself |
| 2 | loaded | 96 | 130 ms | 0.5 s | 0.6 s | 10,382 KiB | 295 ms, Substack `8560.5e2cd29a.js` |
| 2 | blocked | 99 | 30 ms | 0.5 s | 0.6 s | 8,584 KiB | 88 ms, the page itself |

Blocking the embed removes about 2 MB and every long task over 100 ms; what is
left of TBT is the page's own inline script.

TBT on this machine never reached PSI's 480 ms with the embed loaded because the
Google Tag Manager and Datadog scripts Substack loads inside the frame are not
reachable from here; the Substack bundle alone is the 300 to 640 ms long task in
both reports.

## Owed, in the website repo

In the order they pay back:

1. `loading="lazy"` and a `title` on the Substack iframe; remove the
   `substackcdn.com` preconnect. One commit. Expect desktop TBT to fall to under
   100 ms and the score to the mid-90s.
2. Convert `assets/shots/*.png` to WebP at the current pixel size and repoint
   `src`/`data-src`. About 15.6 MB off the full-page weight. Look at
   `signals.png` (alpha) and one dense shot at 2× before committing all
   eighteen.
3. Contrast, `<main>`, heading order, touch-target padding, favicon: a single
   accessibility commit.
4. One stylesheet instead of two (`build.py`).
5. Later, each worth a line and not a session: AVIF second source, Latin subset
   of Inter, HSTS to a year, `hero.mp4` cache header, hero poster as WebP,
   captions track on the hero video, a plain Substack form instead of the
   iframe.

After deploying 1 and 2, run PSI again on both form factors and record the
numbers under a dated line here; the before is this doc.
