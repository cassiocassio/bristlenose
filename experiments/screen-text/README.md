# Screen text

What if the text on the participant's screen were searchable? Measured 13 Oct 2026 on two real
sessions and a few stress frames. The conclusion and the proposal are in
[`docs/design-screen-text-search.md`](../../docs/design-screen-text-search.md); this file is the method
and the numbers.

Every output of these scripts that holds frames or recognised text goes in the gitignored private
trial-data folder, never in the tree, because screens carry participants' and third parties' personal
data. This README holds aggregates only.

## Files

| File | What it does |
|---|---|
| `select_frames.py` | Picks the thumbnail plan's frames (one per participant turn, 25% in, plus one 2 s after each ΔE 8 scene change inside a participant turn), extracts them as full-resolution PNG and measures every storage format on a sample |
| `ocr_bench.py` | Runs candidate engines over a frame set and records lines, confidence, boxes and seconds per frame. Needs a scratch venv: `pip install rapidocr onnxruntime pillow pyobjc-framework-Vision`, and `brew install tesseract` |
| `score.py` | Scores engines against hand-written targets in a private `truth.json`: is the target found by the shipped search rule (folded phrase from a word start, `docs/design-search.md` §3)? |
| `coverage.py` | Treats Vision OCR every 2 s as the oracle and asks which frame-selection strategies capture each text "episode" (a line continuously on screen) |
| `pixel_diff.py` | A cheap text-change detector (edge maps of 480 px greyscale frames), for comparison |
| `pii_on_ocr.py` | Runs stage 7's own redactor (`_redact_text`, Presidio + `en_core_web_lg`, shipped thresholds) over the OCR text and counts personal data caught and UI text damaged |
| `pipeline_spike.py` | Second pass: the build plan's step 1 end to end. One ffmpeg pass on a pipe (1 frame per 4 s, full res, `showinfo` times) into Vision via `CGImage`, folded lines, episodes, text-diff moments; writes only the index. Reports wall, CPU, peak RSS and RSS every 100 frames |
| `sticky_eval.py` | Second pass: compares four chrome-removal rules (whole line, text anywhere, line at a place, word at a place) against the truth targets |
| `search_spike.py` | Second pass: searches an index with the shipped matching rule, groups hits into result rows, attaches the transcript paragraph at each, and times the scan |
| `rapid_levers.py` | Second pass: RapidOCR variants at 2 threads (default, detection capped at 960 px, PP-OCRv5 Latin mobile, both) for speed and accuracy |
| `sidecar-vision-spike.patch` | Third pass: the throwaway changes that put Vision in the real sidecar — pyobjc in the `apple` extra, a probe started by `sidecar_entry.py` when serving, and the `CFFIXED_USER_HOME` fix. Apply to a scratch worktree, never to `main`. Its `_variants`/`_worker` helpers are dead: the sandbox refuses the semaphores they need |
| `anchor_spike.py` | Fourth pass: how often a transcript paragraph or a quote shares a run of words (or one rare word) with a line on screen within ±4 s. The basis of the read-aloud highlight and of pinning |
| `board_spike.py` | Fourth pass: one session as a board — a still per screen, quotes pinned to lines on it. Superseded by `screens_board.py` |
| `screens_board.py` | Fourth pass: three sessions as one set of screens. Screen keys from the address bar (tab title where the bar shows only the host), screens linked across sessions, quotes placed by timecode and pinned by words or by meaning (LaBSE), pins carried across participants. Writes a private page; `--labels` scores pins against hand judgements |
| `screens_board.html`, `screens_lens.html` | The page templates: a rough one, and one drawn with the shipped theme CSS and quote card (`--style lens`, the default). Neither holds data |

## Material

- **p3**: 38-minute usability session, Teams, 1080p. 16 minutes of call (faces), then a German IKEA
  site shared from Chrome, the share drawn about 1670 px wide beside a filmstrip of video tiles.
- **Teams**: 18-minute session, 1080p. Seven minutes of call, then the UK IKEA site shared from Safari.
- **Stress frames**: one dark-mode desktop capture (1668×1080: a chat app sidebar, a call, OBS, tiny
  text) from the folder-of-horrors corpus, and a **synthetic** dark terminal (Menlo 13 pt at 2×,
  2880×1800, public repo output) at native size and shrunk into a 1080p call share. No real terminal
  recording exists in the corpus.
- **Ground truth**: 9 real frames and 2 synthetic, 232 target strings, written by reading each frame
  at 100% and choosing what a researcher might type: headings, body sentences, buttons, navigation,
  small print, text dimmed under a modal's scrim, dark-mode text, browser chrome, and personal data
  (names, bookmark titles, a typed postcode). Targets are legible text by construction, so the scores
  are an upper bound on what a real query finds.

## Results

### Frames and storage (`select_frames.py`)

| | p3 (38 min) | Teams (18 min) |
|---|---|---|
| participant turns | 45 | 7 |
| ΔE 8 scene changes | 34 | 19 |
| frames picked (turn + change) | 71 (112/h) | 26 (86/h) |
| seek and extract one full-res PNG | — | 0.11 s |
| decode at 1 frame per 2 s, full res, one pass | 5.8 s | 3.0 s |

Median size of one 1920×1080 frame, 40 and 26 frames sampled:

| format | p3 | Teams |
|---|---|---|
| PNG (lossless) | 475 KB | 555 KB |
| JPEG q2 | 140 KB | 205 KB |
| JPEG q5 | 87 KB | 134 KB |
| HEIC (`sips`, quality 70) | 73 KB | 94 KB |
| JPEG 1280 px q4 | 50 KB | 85 KB |
| JPEG 320 px (the thumbnail) | 5.8 KB | 8.1 KB |

### Engines (`ocr_bench.py`, `score.py`)

Seconds per 1080p frame on an M2 Max, engine warmed; CPU and memory from `/usr/bin/time -l` over 40 frames.

| engine | s / frame | CPU s / frame | peak RSS | phrase found (non-personal targets, n=206) | token recall |
|---|---|---|---|---|---|
| Apple Vision, accurate | 0.15–0.18 | ~0.13 | 180 MB | **98%** | 99% |
| Apple Vision, fast | 0.10–0.11 | | | 29% | 62% |
| RapidOCR 3.10 (PP-OCRv6 small, onnxruntime), all cores | 0.75–0.92 | ~5.3 | 1.4 GB | **96%** | 98% |
| RapidOCR, capped at 2 threads | 2.0 | ~4 | 1.3 GB | (same) | |
| Tesseract 5.5 LSTM, `--psm 3` | 0.39–0.40 | | | 59% | 76% |
| Tesseract, `--psm 11` (sparse) | 0.38–0.44 | | | 65% | 78% |
| Tesseract on frames upscaled 2× | 0.76–0.83 | | | 71–74% | 83–84% |

By kind of text (phrase found, Vision accurate / RapidOCR / Tesseract psm 11): headings 100/100/75%,
body 100/100/21%, buttons 100/100/60%, small print 93/97/53%, dimmed under a scrim 98/90/74%, dark
mode 100/100/75%, terminal 100/94/97%. Vision accurate's four misses: text under the mouse pointer, a
tooltip, a URL fragment, a small badge. Vision fast misreads characters throughout (`Get instsni
benefws`): it is not a cheaper Vision, it is a different one. German was read correctly by Vision
under its default language setting and by RapidOCR's default Chinese–English model.

Sizes if bundled: pyobjc for Vision is about 6.8 MB of wheels (`pyobjc-core`, `-Cocoa`, `-Vision`;
`objc` is 10 MB unpacked). RapidOCR is a 27 MB wheel with its models (det 9.9 MB, rec 21 MB, cls
0.6 MB), plus `opencv-python-headless` (48 MB wheel, 119 MB unpacked) and nine more dependencies;
onnxruntime is already a Bristlenose dependency. Tesseract is 25 MB plus 7 MB leptonica from Homebrew,
English data only. Licences: Apache-2.0 (RapidOCR, OpenCV, Tesseract), MIT (pyobjc).

### Is a frame at each scene change enough? (`coverage.py`)

The oracle is Vision accurate on one frame every 2 s (1,137 + 546 frames). An episode is a folded OCR
line continuously on screen; "≥ 4 s" excludes one-frame flickers, which are mostly scrolling and OCR
noise. Share of ≥ 4 s episodes captured, and frames per hour:

| strategy | p3 frames/h | p3 | Teams frames/h | Teams |
|---|---|---|---|---|
| participant turns, 25% in | 71 | 31% | 23 | 1% |
| **turn + ΔE 8 change in a participant turn (the thumbnail plan)** | 109 | **61%** | 86 | **44%** |
| every turn + every ΔE 8 change | 185 | 74% | 109 | 44% |
| every 20 s | 180 | 61% | 181 | 65% |
| every 10 s | 361 | 80% | 363 | 79% |
| **OCR every 2 s, keep a frame when the lines change (Jaccard < 0.6)** | 187 | **86%** | 237 | **85%** |
| OCR every 4 s, same rule | 152 | 87% | 158 | 84% |
| OCR every 6 s, same rule | 125 | 83% | 145 | 81% |
| edge-map diff (480 px), threshold 0.2 | 964 | 88% | 969 | 89% |
| edge-map diff, threshold 0.4 | 714 | 77% | 389 | 83% |

- **Colour is a poor proxy for text.** Of 117 and 71 text changes, 62% and 55% had no ΔE 8 colour edge
  within ±3 s: one white web page becoming another, a white popover on a white page.
- **The thumbnail plan leaves long gaps.** In the Teams session the transcript's last participant turn
  runs 14 minutes and covers the whole share, so frames appear only at colour changes; 53% of 10–30 s
  episodes are missed.
- **The edge diff is cheap (5 ms a frame) and noisy:** moving faces in call tiles change edges all the
  time, so it keeps 400–1,000 frames an hour. It would need the filmstrip masked.
- **OCR's own text diff is the detector worth having**, and on the Mac it is affordable: OCR every 4 s
  is 900 calls an hour, about 2.3 minutes per hour of video.

### Index size

Storing text rather than frames, as "episodes" (line, box, on-screen intervals) from OCR every 4 s:
1,211 and 603 distinct lines, **about 230 KB per hour as JSON, 45 KB gzipped**. The recognised
characters per hour (about 40 KB) are the same order as the transcript of the same hour.

### Personal data (`pii_on_ocr.py`)

Every real frame in the truth set carried personal data: names under the video tiles, bookmark and tab
titles, a postcode typed into a form, a delivery address. The dark-mode capture showed a chat sidebar
listing the presenter's colleagues, who are in no consent form at all.

Stage 7's redactor on the Vision OCR, per line (per frame joined, in brackets):

| | caught |
|---|---|
| person names (17) | 15 |
| bookmark and tab titles (6) | 1 |
| postcodes and addresses (3) | 0 (stage 7 deliberately omits locations) |
| **all personal targets (26)** | **16 (14)** |
| **ordinary UI targets damaged (202)** | **27 (15)**: product names read as people, buttons, headings |

**Stickiness** separates them better. Share of the session's text-dense frames (≥ 25 OCR lines) on
which a target appears:

| | targets on ≥ 50% of share frames | median share |
|---|---|---|
| personal data (19 in the two sessions) | 17 | 100% |
| browser chrome (13) | 5 | 24–59% |
| content (137) | 11, mostly site navigation | 4–13% |

Dropping lines that sit on at least half of a session's share frames removes 17 of 19 personal targets
and 11 of 137 content targets, against Presidio's 16 of 26 and 27 of 202. What it cannot remove is
personal data typed into the page itself (the postcode), which behaves like content.

## Second pass, same day: spiking the build plan

### The pipeline end to end (`pipeline_spike.py`)

| recording | video | frames | wall | per hour of video | OCR per frame | ffmpeg CPU | peak RSS | index |
|---|---|---|---|---|---|---|---|---|
| p3, 1080p call | 37.8 min | 568 | 70.6 s | **1.9 min** | 0.122 s | 43 s | 209 MB | 129 KB |
| Teams, 1080p call | 18.1 min | 273 | 35.5 s | **2.0 min** | 0.127 s | 21 s | 188 MB | 67 KB |
| macOS screen recording, 3456×2234 at 120 fps | 4.3 min | 66 | 23.9 s | 5.5 min | 0.268 s | 109 s | 288 MB | 79 KB |

- **Decode overlaps OCR** on the pipe, so it adds no wall time at 1080p; at 4K the job is decode-bound.
- **Vision keeps about one core busy**: Python's CPU time matched OCR time (69 s each on p3). The first
  pass's reading that it ran "mostly on the Neural Engine" was wrong.
- **Memory needs two things.** A `CGImage` built with `CGDataProviderCreateWithData` over the Python
  buffer leaked one frame per call (~8 MB at 1080p), pool or no pool: RSS 927 → 4,154 MB over 500
  frames. Copying into `NSData` fixed the provider; without a per-frame `objc.autorelease_pool()` it
  still leaked at the same rate (941 → 2,586 MB over 300 frames). With both, RSS stayed at 163–197 MB.

### Vision under the App Sandbox

The spike froze a 40-line Vision probe with PyInstaller into a `.app`, signed it ad hoc with
`com.apple.security.app-sandbox`, and ran it. It ran in its container (`NSHomeDirectory()` resolved to
`~/Library/Containers/<bundle id>/Data`), checked its own bundle id before reporting, and read a
synthetic frame with Vision accurate: 27 lines, no error, no extra entitlement. Vision listed 33
recognition languages, covering every Bristlenose locale but Catalan (Portugal's Portuguese is under
`pt-BR`). pyobjc's frozen footprint: `objc` 0.9 MB, `Quartz` 0.7 MB, `Foundation` and `CoreFoundation`
0.15 MB each, `Vision` 56 KB; the whole probe app, Python included, 23 MB. **Not tested:** the shipped
sidecar's shape, an inherited-sandbox child of the Swift host.

### Chrome removal, four rules (`sticky_eval.py`)

| rule | personal targets removed (19) | content targets removed (146) |
|---|---|---|
| whole line on ≥ 50% of dense frames | 12 | 5 |
| text anywhere on ≥ 50% | 13 | 13 |
| whole line at the same place | 12 | 4 |
| **word at the same place (2% buckets, ±1)** | **16** | **5, all browser chrome** |

Whole-line rules fail on the bookmark bar because Vision reads bookmark icons as stray letters and
regroups the bar into different lines from frame to frame. The word rule's five "content" removals are
the browser's restore banner, the URL, an assistant button and two Safari bookmarks: no page content.
What it leaves is one bookmark title and the two values the participant typed (a postcode and a
delivery address).

### Search rows (`search_spike.py`)

A folded scan of 495–930 episodes takes 0.0–0.3 ms per query. Rows per query on the two sessions
(13 queries, IKEA UI text):

| grouping | specific phrases (dialog titles, buttons) | common words |
|---|---|---|
| one row per episode run | 1–2 | 6–28 |
| overlapping intervals merged | 1–2 | 1–3, but one row spanned eight minutes of different screens |
| **by the screen a match appeared on, same text within 60 s rejoining, leading 1–2-character token ignored** | **1, at the right moment** | **1–7** |

### RapidOCR at 2 threads (`rapid_levers.py`)

| variant | found (206) | s / frame | CPU s / frame |
|---|---|---|---|
| default, PP-OCRv6 small | 96% | 2.16 | 4.64 |
| detection capped at 960 px | 95% | 1.55 | 3.28 |
| PP-OCRv5 mobile, Latin recogniser | 96% | 1.71 | 3.88 |
| both | 86% | 1.40 | 2.77 |

An unchanged-frame gate (edge-map diff against the previous 4 s sample, OCR only above the threshold)
at 0.1: OCR on 63% (p3) and 69% (Teams) of samples, keeping 95–96% of distinct lines. Non-default
models download at first use from modelscope.cn.

## Third pass: Vision in the real sidecar

The second pass ran Vision in a sandboxed `.app` of its own. The shipped shape is different: the
sidecar is a child of the sandboxed host that **inherits** its sandbox. The third pass built that
shape in a throwaway worktree. pyobjc went into the `apple` extra, and a probe in the sidecar read
8 frames (one every 4 s, from 60% in) of the served project's first recording through the bundled
ffmpeg. `ensure-sidecar.sh` built and signed the sidecar with its shipped entitlements, and the
sandboxed Debug app launched it as its child. Results:

| | without the fix | with `CFFIXED_USER_HOME` = container |
|---|---|---|
| sandbox on (a read of a plain file outside the grant) | refused, `EPERM` | refused, `EPERM` |
| `NSHomeDirectory()` in the sidecar | the real home (the host's `HOME` env is the container) | the container |
| Vision | fails on the first frame: `e5rt_e5_compiler_create … (Code: 11)`, detector load error, no `NSError` | 8 of 8 frames, 74–97 lines each (3456×2234 screen recording) |
| first frame, cold | — | 41 s (the one-time model compile) |
| first frame, after relaunch | — | 0.63 s |
| later frames | — | 0.15–0.22 s |
| peak RSS, whole serve | — | ~400 MB |
| bundle size | 561 MB against main's 559 MB | |

**The cause:** Vision caches its compiled model under
`<NSHomeDirectory()>/Library/Caches/<id>/com.apple.e5rt.e5bundlecache`. The standalone sandboxed
probe's cache was in its container, and unsandboxed processes keep theirs under the real
`~/Library/Caches/`. The inherited child computed the real-home path, and the sandbox refused the
write. The sandbox also refused POSIX semaphores (`multiprocessing.Queue` raised `EPERM`).

**Wired and re-measured.** `childEnvironment` now sets the variable on the host side (`32e9d2b3`). A
second rebuild applied the patch *without* its `sidecar_entry.py` lines, so only the Swift wiring
supplied it. The sidecar's environment carried `CFFIXED_USER_HOME`, `NSHomeDirectory()` in the sidecar
was the container, the outside read was still refused, and Vision read 8 of 8 frames (same line
counts). Its first frame took 41.5 s again: the cache from the earlier build in the same container
was not reused, so the compile appears to be once per build.

Not tested: a TestFlight-signed build (Apple Distribution, Hardened Runtime on the host). The probe
wrote its result file into the served project's hidden `.bristlenose/` folder; both result files were
deleted afterwards, and the worktree and its DerivedData were removed.

## Fourth pass: one set of screens, three participants

The owner's test of `docs/design-screens.md` §S5: three IKEA sessions (UK site on a Mac in a Teams
call, German site in Chrome, UK site on an iPad in Safari), cut into screens, every quote placed on
its screen by timecode and pinned to the element it is about.

- **Read-aloud is common.** In the UK session, 57% of participant paragraphs during the share contain
  a run of 2+ words that is on screen at that moment. Participants read out what they are looking at.
- **Screens: 21 across the three sessions, 5 visited by two of them, none by all three.** The address
  bar is the key where it shows a path. Safari's default shows only the host, so the iPad session is
  keyed by tab title, and nothing in the other sessions shares a title with it unambiguously. A title
  seen with two or more URLs in one session is a bookmark, not a title: one bookmark otherwise
  chained every page of a session into one screen.
- **Across languages the same screen aligns by URL template** (locale prefix dropped, product and
  category slugs masked): the UK and German carts, delivery pages and category pages line up.
- **Positions are per moment.** A line's box moves as the page scrolls, so a pin is matched on the
  still it is drawn on (re-read by Vision), not on the episode index.
- **Pinning: 47 quotes placed on a screen; 15 pinned by shared words, 8 by meaning, 24 left unpinned.**
  Against 27 hand-labelled pins, precision went from 18 of 27 to 17 of 23 when lines were limited to
  the web page (no call tiles, no browser bars) and page furniture was dropped (a line flagged sticky,
  or seen on 5+ screens of a session). Dropping lines seen on 3+ screens instead lost four right
  pins, among them "Continue to checkout", which sits on every cart page.
- **What is still wrong:** a cookie banner, a one-word button whose word the participant happened to
  say, a site welcome line matched by meaning, a heading chosen over the line actually discussed.
- **Carrying a pin to another participant's still works across languages:** a UK quote about the
  shopping bag lands on the German *Warenkorb* heading; a German quote about delivery costs lands on
  the UK "Shipping costs are calculated at checkout". 3 carried pins on the shared screens.
- **The still chosen per screen moves pins.** It is the moment that pins the most quotes; a filter
  change can pick another moment, on which a pin finds a different line.

## Caveats

Two sessions, both IKEA shopping flows on Teams, both 1080p. One dark-mode frame, a synthetic terminal,
no CJK, no Windows desktop, no 4K share inside a call. One reader wrote the targets. The coverage oracle is itself
OCR, so text Vision misses is missing from both sides. Tesseract was installed with Homebrew on the
measuring Mac for this comparison.
