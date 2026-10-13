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

## Caveats

Two sessions, both IKEA shopping flows on Teams, both 1080p. One dark-mode frame, a synthetic terminal,
no CJK, no Windows desktop, no 4K share. One reader wrote the targets. The coverage oracle is itself
OCR, so text Vision misses is missing from both sides. Tesseract was installed with Homebrew on the
measuring Mac for this comparison.
