---
status: proposal
date: 15 Oct 2026
specimen: docs/mockups/monospace-roles-specimen.html
probes: experiments/monospace-audit/
---

# Monospace roles: audit and proposal

An audit of every monospace face in Bristlenose (web report, desktop webview, native Swift), the measured rendering of each one on both type scales, and a proposal to corral them into four roles. **Audit only: no product CSS was changed.** The owner decides the tokens.

What prompted it: the Screens info-line path was set to `--bn-weight-emphasis` (490) in mono, on a measurement that WebKit steps 420→490 (+11% ink) while Chromium renders them alike. That measurement is right about researchers' Macs and wrong about the developer's, and the reason is the subject of §1.

## 1. Which face actually draws the mono

**"SF Mono" by name exists only on a Mac with Apple's developer font package installed** (`com.apple.pkg.SFMonoFonts`, in `/Library/Fonts`). This machine has it. The system's own monospace is the hidden `.SF NS Mono` (`/System/Library/Fonts/SFNSMono.ttf`), and CSS can reach it only as `ui-monospace`, and only in WebKit. Chromium has no `ui-monospace`.

The two shipped stacks:

- web (`tokens-typography.css:21`): `"SF Mono", "Fira Code", "Consolas", monospace`
- desktop (`tokens-desktop.css:41`): `"SF Mono", ui-monospace, monospace`

Generic `monospace` in a `lang="en"` page, which the report is (`server/app.py:726`): **Menlo in WebKit, Courier in Chromium.** Chromium's answer comes from its own font API (`CSS.getPlatformFontsForNode`). Without a `lang` attribute, WebKit's generic is Courier as well.

| Surface | Stack | Developer's Mac (download) | A researcher's Mac (stock) |
|---|---|---|---|
| Mac app, Typography ▸ SF Pro (default) | desktop | SF Mono, static download | system SF Mono, variable (via `ui-monospace`) |
| Mac app, Typography ▸ Inter | web | SF Mono, static download | **Menlo** |
| Safari (serve, HTML export) | web | not measured¹ | **Menlo** |
| Chrome (serve, HTML export) | web | SF Mono, static download | **Courier** |
| Windows | web | — | Consolas (by name) |
| Linux | web | — | the distro's generic (often DejaVu Sans Mono) |

¹ Safari's policy limits web content to system-installed fonts, so the download is probably invisible there too. Not measured: driving Safari needs a settings change. WebKit's `<canvas>` already ignores the download in this harness, which fits the same policy.

So **the developer's eye is calibrated on a face no researcher has.** Every timecode, tag and speaker code a researcher sees in Chrome is Courier.

### The premise of the Screens change, corrected

The +11% was measured on `<canvas>`. In WebKit, canvas text skips the user-installed "SF Mono" and falls through to `ui-monospace`, the variable system font, where 420 is +4% and 490 is +16% (1.16/1.04 = +11.5%). DOM text in the same browser, in Playwright WebKit and in a **sandboxed WKWebView** (the app's own configuration), draws the static download, where 420, 490 and 500 are all Medium (+15%). On this Mac, then, the app renders the Screens path at 420 and 490 identically. On a researcher's Mac (desktop scale) it steps by the +11% that was measured. Chromium "rendering them alike" is the static download snapping both to Medium.

**Given the same face, WebKit and Chromium draw identical ink at every weight measured.** Neither engine snaps differently. They find different faces.

## 2. Measurements

Ink is summed from DOM screenshots at 2× (black on white, 0.299/0.587/0.114 luminance), relative to 400 in the same face, size and engine. Engines: Playwright WebKit (2287), Playwright Chromium (1223), and a sandboxed WKWebView in a minimal `.app` with `app-sandbox` and `network.client`. **The two WebKits agree to the pixel.** Each percentage holds within ±0.5 points from 9.6 px to 15 px, so the table is per weight rather than per size.

| face (how it is reached) | 300 | 370 | 400 | 420 | 490 | 500 | 520 | 600 | 700 |
|---|---|---|---|---|---|---|---|---|---|
| SF Mono download, static (both engines, by name) | −21% | −21% | 0 | +15% | +15% | +15% | +30% | +30% | +50% |
| system SF Mono, variable (WebKit, `ui-monospace`) | −20% | −5% | 0 | +4% | +16% | +18% | +21% | +35% | +53% |
| Menlo (WebKit generic; Chromium by name) | 0 | 0 | 0 | 0 | 0 | 0 | Bold | Bold | Bold |
| Courier (Chromium generic) | 0 | 0 | 0 | 0 | 0 | 0 | Bold | Bold | Bold |

Bold is +33 to +39% for Menlo and +37 to +38% for Courier, varying with the string. Snapping, by face:

- **Static download** (Light, Regular, Medium, Semibold, Bold, Heavy): 300 and 370 draw Light; 420–500 draw Medium; 520–600 draw Semibold.
- **System variable:** continuous, no snapping.
- **Menlo, Courier, Consolas** (Regular and Bold only): up to 500 is Regular; 520 and up is Bold. The CSS matching rule puts everything above 500 on the next heavier face.

At the named instances (400, 500, 600, 700), the download and the system font agree within 2–5%, with identical advances. **All the divergence between the developer's Mac and a researcher's Mac sits at the off-instance weights: 370, 420, 490 and 520.** Native Swift (`NSFont.monospacedSystemFont`, `.monospaced()`) always draws the system font at named weights, so it matches a researcher's webview and differs slightly from the developer's.

**600 is the only emphasis weight that reads about the same on every path:** Semibold at +30% (download) or +35% (system), Bold at +33–39% (Menlo, Courier). 500 is Medium in WebKit and Regular wherever the face has only Regular and Bold.

### What the product actually sets

Computed from the live SPA (smoke fixture, both scales, WebKit and Chromium). `body` declares no `font-weight`, so **every mono element without its own weight renders at 400**, not at `--bn-weight-normal` (420).

| size (web / desktop) | weight | elements |
|---|---|---|
| micro (9.6 / 10) | 400 | Screens nav path and codes, moderator pill, threshold axis and labels, codebook pending count, heatmap tooltip lines, tapestry ticks and thumbnail times |
| micro | 370 | `.badge` at micro (Signals quote tags), signal hero caret |
| micro | 700 | badge delete ×, accept ✓ and deny ✗ glyphs |
| badge (11.5 / 11) | 370 | `.badge`: every tag and sentiment chip |
| badge | 400 | speaker codes, participant grid boxes, sentiment bar labels, tag input and suggestions |
| badge | 420 | user tags (`.badge-user`), codebook tag preview, picker card version |
| badge | 490 | user tags in dark mode |
| badge | 520 | Signals pattern label (uppercase, +0.06em) |
| caption (12) | 400 | session durations, Screens version times, AutoCode report times, threshold confidence, moderator "more", status-page details |
| caption | 490 | Screens info-line path |
| label (13) | 400 | timecodes (quotes, transcript, Signals, hidden list), metric values, codebook add-tag field and drag ghost, status-page long text |
| label | 370 | signal hero chip label (it is a `.badge` at label size) |
| label | 490 | heatmap cells, signal hero score |
| 0.85em literal | 400 | footer keycaps (9.79 / 9.35 px live), coverage timecodes |

What each pair renders comes straight from the table above. For example, `.badge` at 370 is −21% (Light) on the developer's Mac, −5% in the app on a researcher's Mac, and Regular in Chrome. And `.badge-user`'s dark-mode compensation (420→490) does nothing on the developer's Mac (both Medium) or in Chrome (both Regular); it works only in the app on a stock Mac.

## 3. Catalogue

### Tokens

| where | value | note |
|---|---|---|
| `bristlenose/theme/tokens-typography.css:21` | `"SF Mono", "Fira Code", "Consolas", monospace` | web; also the Mac app in Inter mode |
| `bristlenose/theme/tokens-desktop.css:41` | `"SF Mono", ui-monospace, monospace` | desktop override |
| `bristlenose/theme/tokens.css:286` | `--font-mono: var(--bn-font-mono)` | alias |
| `tokens-typography-v1.css:16`, `-v2.css:22`, `tokens-desktop-v1.css:12`, `-v2.css:22` | the same stacks | archives; not in `index.css` |
| `desktop/…/WelcomeTimelineCSS.swift:428`, `:501` | both stacks | **generated** from the theme (`scripts/gen-welcome-timeline.py`); follows any change |

### CSS rules setting a mono family, by role

**Timecode** (a pointer into the recording):

- `atoms/timecode.css:6` and `:14`: `a.timecode`, `span.timecode` at label
- `organisms/blockquote.css:44` and `:103`: quote and rewatch timecodes at label
- `molecules/hidden-quotes.css:116`: hidden-list timecode at label
- `organisms/coverage.css:56`: coverage timecode at 0.85em (literal)
- `molecules/autocode-report.css:34`: `.report-timecode` at caption
- `frontend/src/islands/screens/screens.css:106`: `.screens-versions .timecode` at caption
- `organisms/session-tapestry.css:78`, `:196` and `:354`: tick, timecode and thumbnail time at micro
- `organisms/sidebar.css:926`: `.session-entry-duration` at caption (a duration)

**Code** (an identifier or vocabulary word):

- `atoms/badge.css:9`: `.badge` at badge, 370; `.badge-user` at 420, 490 in dark mode
- `organisms/sidebar-tags.css:250`: `.tag-sidebar .badge`
- `molecules/person-badge.css:32`: speaker code; `screens.css:94` (speaker code at micro); `signals.css:257` (participant boxes); `signals.css:598` (tooltip speaker)
- `atoms/bar.css:17`: sentiment bar label
- `atoms/input.css:6` and `:64`, and `molecules/tag-input.css:69`: tag input, sizer and suggestions at badge
- `organisms/codebook-panel.css:380`, `:474`, `:491`, `:541` and `:554`: inline edit (inherit); add-tag field, input and drag ghost **at label**; preview at badge, 420. These are the same chips at two sizes.
- `organisms/codebook-v2.css:415`: `.picker-card-version` at badge, 420
- `organisms/signals.css:727`: `.pattern-label` at badge, 520, uppercase
- `atoms/moderator-question.css:23` and `:128`: moderator pill (parked feature) and "more"

**Path** (filename, path, URL, raw text):

- `screens.css:86`: `.screens-nav-path` at micro
- `screens.css:136`: `.screens-sub code` at caption, 490
- `templates/status-page.css:56` and `:81`: status page long text at label, details at caption

**Keycap:**

- `atoms/footer.css:54`: `.footer-keyboard-hint kbd` at 0.85em (literal)

**Figures** (numbers set in mono for alignment):

- `signals.css:161`, `:373`, `:531` and `:607`: metric value at label, heatmap cell at label 490, tooltip metrics and footer at micro
- `codebook-v2.css:98`: `.v2-nav-pending` at micro
- `molecules/threshold-review.css:50`, `:115`, `:164` and `:222`: axis, slider label, zone counter (490) and confidence

Fifteen other rules already align numbers in the body face with `font-variant-numeric: tabular-nums`: `transcription-diagnostics.css`, `sidebar.css:930`, `codebook-panel.css`, `codebook-v2.css`, `sidebar-tags.css`, `search.css`, `tag-filter.css`, `autocode-toast.css` and `screens.css`.

### Inline styles and literal stacks outside the tokens (the rogue uses)

| where | stack and type | ships? | fold into |
|---|---|---|---|
| `bristlenose/theme/templates/player.html:11` | a copy of the web stack, 0.8rem | yes (popout player status line) | path; carries its own copy because the page has no tokens |
| `frontend/src/utils/transcriptCopy.ts:66` | `Menlo,Consolas,monospace`, 85%, normal | yes (rich-text clipboard) | timecode. Keep a literal on purpose: the paste target has no theme and no `ui-monospace` |
| `desktop/…/WelcomeIllustrations.swift:1514` (`--mono`), `:1820`, `:1986`, `:2121`, `:2290`, `:2488` | `"SF Mono",ui-monospace,Menlo,monospace` | yes (Welcome illustrations) | code; hand copies, unlike `WelcomeTimelineCSS.swift`, which is generated |
| `frontend/src/islands/GridSpecimen.tsx:77`, `:182`, `:213`, `:219`, `:276` | `ui-monospace, monospace` at 500 and 600, 10–11 px | dev (specimen route) | when touched |
| `frontend/src/components/playground.css` (12 rules, including `:591` `font: 500 9px/1`) | token family, rem and px literals | dev | when touched |
| `bristlenose/server/run_inspector.py:589` | `"SF Mono",ui-monospace,Menlo,Consolas,monospace` | dev | when touched |
| `bristlenose/server/routes/dev.py:720` and `routes/chat_lens.py:186`, `:191` | `ui-monospace, monospace`, 12 px | dev / experimental flag | when touched |

### Swift

Native code always draws the system SF Mono, at AppKit's named weights.

- **Code:** `SessionsPopoverList.swift:485` (speaker badge, 11 regular); `WelcomeIllustrations.swift:136` (sentiment chip, 11 regular); `SearchFieldViews.swift:24` (search tokens). The last maps CSS weight to AppKit by interpolation (`appKitWeight`, `:31`), so 490 lands "just under medium" and 370 between light and regular.
- **Path and command:** `LLMSettingsView.swift:253` (shell commands, caption) and `:457` (`localhost:11434`); `ProjectDiagnosticPopover.swift:270` and `:428` (source file, footnote), `:370` (glyph) and `:373` (symbol name, caption2); `MCPAgentsSettingsView.swift:1258` (dialect box, subheadline).
- **Build provenance:** `ContentView.swift:817` (status strip, 10 pt); `MenuCommands.swift:433` (About credits, 10 pt); `BootView.swift:166` (server log, caption).
- **Keycap:** `Keycap.swift:40` and `:50`, **medium**.
- **Figures** (system font, monospaced digits, not the mono face): `LLMSettingsView.swift:563`, `SidebarFooter.swift:29`, `CloudImportOutlineView.swift:1170`, `:1552` and `:1555`, `MCPAgentsSettingsView.swift:489`, `:725` and `:729`, `OllamaDownloadPill.swift:98`, `:203`, `:272` and `:450`, `SearchFieldViews.swift:399`.
- **Debug and lab views:** `SidebarLabView:276`, `SeamLabView:284`, `ShimmerTunerView:77` and `:94`, `ShoalDebugView:122` and `:286`, `KeycapGalleryView` (three sites), `WelcomeDegradationLab` (eight sites).

**Swift already follows the proposal:** named weights only, mono for codes, paths and keycaps, and monospaced digits rather than a mono face for numbers.

## 4. Proposal

### One stack, both scales

**Decided 15 Oct 2026:** drop "SF Mono" by name, and never let a supported platform reach Courier. To check before shipping: Cascadia Mono ahead of Consolas (Windows 11, if it ships system-wide), and Liberation Mono and Noto Sans Mono after DejaVu (Linux).

```css
--bn-font-mono: ui-monospace, Menlo, Consolas, "DejaVu Sans Mono", monospace;
```

Delete the desktop override. WebKit then draws the system SF Mono on every Mac, download or not, which is also the face native Swift uses. Chromium on a Mac draws Menlo instead of Courier, Windows Consolas, and Linux DejaVu Sans Mono. "SF Mono" by name goes because it is the one entry that makes the developer's view differ from everyone else's. "Fira Code" goes because nobody has it who isn't a developer. The generic is still last but is no longer reached on a Mac, which also removes the `lang` dependence: in a Japanese report Chromium's generic is a Japanese face, not a monospace one.

### Weights: Regular at rest, two emphasis values by job

Every monospace role rests at **Regular (400)**. No mono role is Semibold or Bold.

```css
--bn-weight-mono: 400;            /* every role at rest */
--bn-weight-mono-emphasis: 520;   /* first weight above 500: Bold where the face has only Regular and Bold */
--bn-weight-mono-refine: 500;     /* Medium on SF Mono, Regular in Menlo and Consolas: app-only */
```

Menlo, Consolas, DejaVu and Liberation have only Regular and Bold, and CSS matching gives Regular up to 500 and Bold above it. So browser emphasis is either absent or Bold; nothing in between exists. **520** is the cheapest value across the line: SF Mono +21% (about Medium, near the +16% of today's 490), and Bold on the two-instance faces. Use it where emphasis must survive in a browser; today that is only the Screens path naming the screen. **500** is Medium on SF Mono and plain Regular elsewhere; use it for refinements that can be app-only, such as keycaps, which would be too heavy in Chrome Bold. 600 (`--bn-weight-semibold`) is the alternative if the browser step should look the same as the app's, at about twice the step in the app.

Who sees which: the Mac app and Safari get SF Mono; Chrome, Edge, Arc and probably Firefox on a Mac get Menlo, and the CLI-on-Mac audience likely leans that way. So tune emphasis for Menlo too, not only for SF Mono.

### Four roles

| role | size | weight | why |
|---|---|---|---|
| **timecode** | `--bn-text-label` inline beside a quote; `--bn-text-caption` in a metadata row; `--bn-text-micro` on an axis | mono | A pointer into the recording. Fixed advances keep a column of times aligned. The accent colour, not weight, says it is a link. |
| **code** | `--bn-text-badge`; `--bn-text-micro` in a dense list | mono (or 300, below) | A vocabulary marker beside the finding, never the finding. Size and the chip carry its subordinate rank. |
| **path** | `--bn-text-caption`; `--bn-text-micro` in a nav list | mono; mono-emphasis (520) when the path names the subject | Literal text the researcher may need to type or find on disk. |
| **keycap** | `--bn-text-micro` | mono-refine (500) | Matches `Keycap.swift` (`.medium`, monospaced); Regular in browsers. |

**Figures fold out of monospace:** body font with `font-variant-numeric: tabular-nums`, which is what SwiftUI's `.monospacedDigit()` already does natively. Numbers align without a change of voice, and the body ladder's 490 works there, since Inter and SF Pro are both variable. Numbers that are identifiers (participant codes in the grid) stay in **code**.

**Light chips.** `atoms/badge.css` sets `.badge` to 370 deliberately ("the rung the system reserves for subordinate text"). The developer has seen Light (−21%) since that change. A researcher sees −5% in the app and Regular in Chrome. If the light chip is the intent, **300** gives Light on every Mac path (−20% system, −21% download); otherwise use 400. This is a decision about the look, so it is the owner's. The specimen draws 400.

### What folds where

| today | becomes |
|---|---|
| `.badge` 370, `.badge-user` 420, dark 490, `.tag-preview` 420, `.picker-card-version` 420 | code at mono (or 300): **one weight for every tag**, colour separates sentiment chips from codebook tags; dark-mode user tags at mono-refine if the compensation is kept |
| codebook add-tag field, input and drag ghost at label | code at badge: the same chips at one size |
| `.pattern-label` 520 | rendered only by the dev `GridSpecimen` route, not a shipped surface; code at mono when next touched |
| `.screens-sub code` 490 | path at mono-emphasis (520) |
| `.screens-nav-path`, status page, `player.html` status line | path; the player page gets the token stack written out |
| heatmap cells, metric values, hero score (490), threshold counters and confidence, pending count, tooltip metrics | figures |
| footer `kbd` 0.85em | keycap at micro |
| coverage timecode 0.85em | timecode at caption |
| `WelcomeIllustrations.swift` hand copies | generate them as `WelcomeTimelineCSS.swift` is generated, or update all six to the new stack |
| clipboard `MONO` in `transcriptCopy.ts` | stays a literal; it already matches the proposal minus `ui-monospace` |
| dev surfaces (`GridSpecimen`, playground, run inspector, dev and chat-lens pages) | when next touched |

### Not covered

- Safari DOM on the developer's Mac (¹ above).
- Windows and Linux rendering. Consolas and DejaVu Sans Mono are two-instance families, so the Menlo row should hold, but that is inference.
- Whether mono at the same pixel size reads larger than the body face (x-height). The sizes are carried over, not re-tuned.

## 5. Reproduce

`experiments/monospace-audit/` (run from the repo root; Playwright is resolved from `e2e/`):

```bash
node experiments/monospace-audit/gen-pages.mjs /tmp/mono && node experiments/monospace-audit/probe-playwright.mjs /tmp/mono
```

- `face-check.mjs`: which face each stack reaches (large-glyph ink, both engines, with and without `lang`)
- `probe-wkwebview.swift` + `.entitlements`: the sandboxed-WKWebView probe, built as a minimal `.app` with pages in `Contents/Resources` (README in the file header)
- `analyse.py`: the ink table; `results-2026-10-15.json` is this run
- `build-specimen.py`: regenerates the specimen from the shipped theme files

Two measurement traps found on the way, and worth knowing before re-running:

1. **WebKit `<canvas>` ignores user-installed fonts** where its DOM does not. Measure DOM pixels.
2. **Chromium's `fullPage` screenshot resizes the viewport, and while it does, its generic `monospace` draws Menlo instead of Courier.** Identify faces without that capture: `face-check.mjs` uses a tall viewport, or ask CDP.
