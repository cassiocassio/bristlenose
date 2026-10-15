---
status: partial
last-trued: 2026-10-15
trued-against: HEAD@main on 2026-10-15 (64a2b36a)
date: 15 Oct 2026
specimen: docs/mockups/monospace-roles-specimen.html
probes: experiments/monospace-audit/
---

# Monospace roles: audit, proposal, and what shipped

> **Truing status (15 Oct 2026).** Audited and proposed earlier the same day, then **shipped in 64a2b36a** ("monospace: one stack on both scales, tags 460 in light, the screen's path at 560"): the one stack, the three mono weight tokens and their dark scope, one weight for every tag, the Screens path at 560, footer keycaps, the player page and the Welcome copies. **Durations decided** the same evening: they are timecodes, 400, which is what the sessions list already draws. **Figures left mono** later still: values, counts and scores are in the body face with tabular numerals. The codebook add-tag chip and drag ghost moved to badge size too. **Still open, owner undecided:** the Welcome HTML keycaps at 500 and badges without a weight (§3), the native Welcome chip, the dev surfaces, and Linux. §1 and §2 describe the tree **before** the change and are kept as the baseline it was measured against; §3 and §4 are current; §6 is the ground truth.

An audit of every monospace face in Bristlenose (web report, desktop webview, native Swift), the measured rendering of each one on both type scales, and the four roles they were corralled into.

What prompted it: the Screens info-line path was set to `--bn-weight-emphasis` (490) in mono, on a measurement that WebKit steps 420→490 (+11% ink) while Chromium renders them alike. That measurement is right about researchers' Macs and wrong about the developer's, and the reason is the subject of §1.

## 1. Which face actually draws the mono (before 64a2b36a)

_Baseline, kept as measured. Since 64a2b36a there is one stack, the proposed one, and no Mac reaches Courier; §6 has what it draws._

**"SF Mono" by name exists only on a Mac with Apple's developer font package installed** (`com.apple.pkg.SFMonoFonts`, in `/Library/Fonts`). This machine has it. The system's own monospace is the hidden `.SF NS Mono` (`/System/Library/Fonts/SFNSMono.ttf`), and CSS can reach it only as `ui-monospace`, and only in WebKit. Chromium has no `ui-monospace`.

The two stacks as they shipped until 64a2b36a:

- web (`tokens-typography.css:21`): `"SF Mono", "Fira Code", "Consolas", monospace`
- desktop (`tokens-desktop.css:41`): `"SF Mono", ui-monospace, monospace`

Generic `monospace` in a `lang="en"` page, which the report is (`server/app.py:746`): **Menlo in WebKit, Courier in Chromium.** Chromium's answer comes from its own font API (`CSS.getPlatformFontsForNode`). Without a `lang` attribute, WebKit's generic is Courier as well.

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
- **Menlo and Courier on a Mac** (Regular and Bold only): up to 500 is Regular; 520 and up is Bold. The CSS matching rule puts everything above 500 on the next heavier face. **Windows matches differently**: Chromium there takes the nearest weight through DirectWrite, so Consolas stays Regular to 540 and is Bold from 550 (§6).

At the named instances (400, 500, 600, 700), the download and the system font agree within 2–5%, with identical advances. **All the divergence between the developer's Mac and a researcher's Mac sits at the off-instance weights: 370, 420, 490 and 520.** Native Swift (`NSFont.monospacedSystemFont`, `.monospaced()`) always draws the system font at named weights, so it matches a researcher's webview and differs slightly from the developer's.

**600 is the only emphasis weight that reads about the same on every path:** Semibold at +30% (download) or +35% (system), Bold at +33–39% (Menlo, Courier). 500 is Medium in WebKit and Regular wherever the face has only Regular and Bold.

### What the product set (before 64a2b36a)

_Since 64a2b36a: every tag is `--bn-weight-mono-tag` (460 light, 400 dark), the Screens path 560, footer keycaps micro at 400; the rest unchanged. §3 is current._

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
| `bristlenose/theme/tokens-typography.css:27` | `ui-monospace, Menlo, "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace` | both scales, since 64a2b36a (was `"SF Mono", "Fira Code", "Consolas", monospace`) |
| `bristlenose/theme/tokens-typography.css:42`–`44`, `:68`–`77` | `--bn-weight-mono` 400 · `-mono-tag` 460 (400 in dark) · `-mono-emphasis` 560 | since 64a2b36a |
| `bristlenose/theme/tokens-desktop.css:41` | no mono override (a comment) | the desktop override `"SF Mono", ui-monospace, monospace` was removed in 64a2b36a |
| `bristlenose/theme/tokens.css:286` | `--font-mono: var(--bn-font-mono)` | alias |
| `tokens-typography-v1.css:16`, `-v2.css:22`, `tokens-desktop-v1.css:12`, `-v2.css:22` | the same stacks | archives; not in `index.css` |
| `desktop/…/WelcomeTimelineCSS.swift` | the theme's stack and weights | **generated** from the theme (`scripts/gen-welcome-timeline.py`); regenerated in 64a2b36a |

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

- `atoms/badge.css:9`: `.badge` at badge, `--bn-weight-mono-tag` (460 light, 400 dark); `.badge-user` inherits it. Until 64a2b36a: 370, and `.badge-user` 420, 490 in dark
- `organisms/sidebar-tags.css:250`: `.tag-sidebar .badge`
- `molecules/person-badge.css:32`: speaker code; `screens.css:94` (speaker code at micro); `signals.css:257` (participant boxes); `signals.css:598` (tooltip speaker)
- `atoms/bar.css:17`: sentiment bar label
- `atoms/input.css:6` and `:64`, and `molecules/tag-input.css:69`: tag input, sizer and suggestions at badge
- `organisms/codebook-panel.css:380`, `:474`, `:491`, `:541` and `:554`: inline edit (inherit); add-tag field, input and drag ghost **at label**; preview at badge, `--bn-weight-mono-tag` (was 420). The add-tag chip and drag ghost were the same chips at a second size; both at badge size since 15 Oct 2026.
- `organisms/codebook-v2.css:415`: `.picker-card-version` at badge, `--bn-weight-mono` (was 420)
- `organisms/signals.css:727`: `.pattern-label` at badge, 520, uppercase
- `atoms/moderator-question.css:23` and `:128`: moderator pill (parked feature) and "more"

**Path** (filename, path, URL, raw text):

- `screens.css:86`: `.screens-nav-path` at micro
- `screens.css:137`: `.screens-sub code` at caption, `--bn-weight-mono-emphasis` 560 (was 490)
- `templates/status-page.css:56` and `:81`: status page long text at label, details at caption

**Keycap:**

- `atoms/footer.css:54`: `.footer-keyboard-hint kbd` at `--bn-text-micro`, `--bn-weight-mono` (was 0.85em, inherited 400)

**Figures** (numbers set in mono for alignment until 15 Oct 2026; now the body face with `font-variant-numeric: tabular-nums`, weights unchanged):

- `signals.css:161`, `:373`, `:531` and `:607`: metric value at label, heatmap cell at label 490, tooltip metrics and footer at micro
- `codebook-v2.css:98`: `.v2-nav-pending` at micro
- `molecules/threshold-review.css:50`, `:115`, `:164` and `:222`: axis, slider label, zone counter (490) and confidence

Fifteen other rules already align numbers in the body face with `font-variant-numeric: tabular-nums`: `transcription-diagnostics.css`, `sidebar.css:930`, `codebook-panel.css`, `codebook-v2.css`, `sidebar-tags.css`, `search.css`, `tag-filter.css`, `autocode-toast.css` and `screens.css`.

### Inline styles and literal stacks outside the tokens (the rogue uses)

| where | stack and type | ships? | fold into |
|---|---|---|---|
| `bristlenose/theme/templates/player.html:11` | the shipped stack written out, 0.8rem | yes (popout player status line) | path; carries its own copy because the page has no tokens (updated in 64a2b36a) |
| `frontend/src/utils/transcriptCopy.ts:66` | `Menlo,Consolas,monospace`, 85%, normal | yes (rich-text clipboard) | timecode. Keep a literal on purpose: the paste target has no theme and no `ui-monospace` |
| `desktop/…/WelcomeIllustrations.swift:1514` (`--mono`), `:1820`, `:1986`, `:2121`, `:2290`, `:2488` | `ui-monospace,Menlo,monospace` (was `"SF Mono",…` until 64a2b36a) | yes (Welcome illustrations, Mac webview only) | code; hand copies, unlike `WelcomeTimelineCSS.swift`, which is generated |
| `desktop/…/WelcomeIllustrations.swift:1537`, `:1858`, `:2006`, `:2165`, `:2336` | `.badge` copies with no `font-weight` | yes | code; they draw 400 where the report draws 460 in light. **Open** |
| `desktop/…/WelcomeIllustrations.swift:2179`, `:2352` | `.cap` keycaps, mono, `font-weight:500` | yes | keycap; Mac-only, so 500 is SF Mono Medium and matches `Keycap.swift`'s `.medium`; it diverges from the footer keycap's 400 (`docs/design-keycaps.md` §1). **Open** |
| `frontend/src/islands/GridSpecimen.tsx:77`, `:182`, `:213`, `:219`, `:276` | `ui-monospace, monospace` at 500 and 600, 10–11 px | dev (specimen route) | when touched |
| `frontend/src/components/playground.css` (12 rules, including `:591` `font: 500 9px/1`) | token family, rem and px literals | dev | when touched |
| `bristlenose/server/run_inspector.py:589` | `"SF Mono",ui-monospace,Menlo,Consolas,monospace` | dev | when touched |
| `bristlenose/server/routes/dev.py:720` and `routes/chat_lens.py:186`, `:191` | `ui-monospace, monospace`, 12 px | dev / experimental flag | when touched |

### Swift

Native code always draws the system SF Mono. Most sites use AppKit's named weights; the search tokens interpolate between them.

- **Code:** `SessionsPopoverList.swift:485` (speaker badge, 11 regular); `WelcomeIllustrations.swift:136` (sentiment chip, 11 regular); `SearchFieldViews.swift:24` (search tokens). The last maps CSS weight to AppKit by interpolation (`appKitWeight`, `:31`), so 490 lands "just under medium" and 370 between light and regular.
- **Path and command:** `LLMSettingsView.swift:253` (shell commands, caption) and `:457` (`localhost:11434`); `ProjectDiagnosticPopover.swift:270` and `:428` (source file, footnote), `:370` (glyph) and `:373` (symbol name, caption2); `MCPAgentsSettingsView.swift:1258` (dialect box, subheadline).
- **Build provenance:** `ContentView.swift:826` (status strip, 10 pt); `MenuCommands.swift:433` (About credits, 10 pt); `BootView.swift:166` (server log, caption).
- **Keycap:** `Keycap.swift:40` and `:50`, **medium**.
- **Figures** (system font, monospaced digits, not the mono face): `LLMSettingsView.swift:563`, `SidebarFooter.swift:29`, `CloudImportOutlineView.swift:1170`, `:1552` and `:1555`, `MCPAgentsSettingsView.swift:489`, `:725` and `:729`, `OllamaDownloadPill.swift:98`, `:203`, `:272` and `:450`, `SearchFieldViews.swift:399`.
- **Debug and lab views:** `SidebarLabView:276`, `SeamLabView:284`, `ShimmerTunerView:77` and `:94`, `ShoalDebugView:122` and `:286`, `KeycapGalleryView` (three sites), `WelcomeDegradationLab` (eight sites).

**Swift already follows the proposal:** mono for codes, paths and keycaps, and monospaced digits rather than a mono face for numbers. The search tokens (`SearchFieldViews.swift:31`–`43`) take the CSS weight measured off the web badge and interpolate between AppKit's named weights, so a light-mode tag at 460 draws between regular and medium there too.

## 4. Proposal, and what shipped

Decisions taken 15 Oct 2026 are marked **Decided**. The emphasis weight was revised the same evening, after the Windows measurement in §6. **Everything decided here shipped in 64a2b36a**; what did not is marked **open** in the table below.

### One stack, both scales

**Decided:** drop "SF Mono" by name, and never let a supported platform reach Courier.

```css
--bn-font-mono: ui-monospace, Menlo, "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
```

Delete the desktop override. What each platform then draws, all measured except Linux:

- **WebKit** (the Mac app, Safari): the system SF Mono, on every Mac, download or not. This is also the face native Swift uses.
- **Chromium on a Mac** (Chrome, Edge, Arc): Menlo instead of today's Courier.
- **Windows 11**: Cascadia Mono, which ships with Windows Terminal.
- **Windows 10**: Consolas.
- **Linux**: DejaVu Sans Mono (expected, not measured).

"SF Mono" by name goes because it is the one entry that makes the developer's view differ from everyone else's. "Fira Code" goes because nobody has it who isn't a developer. The generic is still last but is no longer reached on any measured platform. That matters: it is Courier in Chromium on a Mac and Courier New in Windows 10's Edge, and it varies with the page's `lang`.

Open after shipping: Liberation Mono and Noto Sans Mono after DejaVu, once Linux is measured.

### Weights

```css
--bn-weight-mono: 400;            /* every role at rest */
--bn-weight-mono-tag: 460;        /* tags, light appearance only; 400 in dark */
--bn-weight-mono-emphasis: 560;   /* Bold on every face that has only Regular and Bold */
```

- **Rest, 400. Decided.** Every monospace role, and every tag in dark mode.
- **Tags in the light appearance, 460. Decided.** Light tags read a little weak against their pale tints: light sentiment chips measure 3.1–5.2:1 WCAG, against 6.2–9.3:1 in dark. 460 is +9% ink in SF Mono, a touch under 490's +13–14%, and **Regular in Menlo, Consolas and Cascadia Mono**, so it is a fine adjustment where SF Mono can show one and invisible elsewhere. CSS cannot vary `font-weight` with `light-dark()`, so the token is set to 400 in the dark scopes, in `tokens-typography.css:68`–`77`, using the same `[data-theme="dark"]` and `prefers-color-scheme` pair `atoms/badge.css` uses for the dark user-tag colour.
- **Emphasis, 560. Revised from 520.** The aim, decided earlier, is a step that survives in a browser. 520 reaches Bold in Menlo on a Mac but stays Regular in Consolas, where Windows's nearest-weight matching needs 550; 560 adds margin. In SF Mono 560 is +24% (520 was +18%), in Cascadia Mono SemiBold (+16%), in Menlo and Consolas Bold (+33–36%). Today it applies only to the Screens path that names the screen.
- **No 500.** Fewer weights, decided. Also, 500 is exactly where Cascadia Mono jumps to SemiBold, so it is a poor value for anything meant to be subtle.

**The safe band is 400–490:** every weight in it is Regular in Menlo, Courier, Consolas and Cascadia Mono and varies only in SF Mono. Anything meant as an SF Mono-only nuance belongs there.

Who sees which: the Mac app and Safari get SF Mono. Chrome, Edge, Arc and probably Firefox on a Mac get Menlo, and the CLI-on-Mac audience likely leans that way. So emphasis is tuned to read in Menlo and Consolas, not only in SF Mono.

### Four roles

| role | size | weight | why |
|---|---|---|---|
| **timecode** | `--bn-text-label` inline beside a quote; `--bn-text-caption` in a metadata row, durations included; `--bn-text-micro` on an axis | 400 | A pointer into the recording. Fixed advances keep a column of times aligned. The accent colour, not weight, says it is a link. |
| **code** | `--bn-text-badge`; `--bn-text-micro` in a dense list | 400; tags 460 in light | A vocabulary marker beside the finding, never the finding. Size and the chip carry its subordinate rank. |
| **path** | `--bn-text-caption`; `--bn-text-micro` in a nav list | 400; 560 when the path names the subject | Literal text the researcher may need to type or find on disk. |
| **keycap** | `--bn-text-micro` | 400 | Regular, so the browser never shows Bold keycaps. The native `Keycap.swift` is `.medium`, a small departure kept for fewer weights. |

**Figures fold out of monospace:** body font with `font-variant-numeric: tabular-nums`, which is what SwiftUI's `.monospacedDigit()` already does natively. Numbers align without a change of voice, and the body ladder's 490 works there, since Inter and SF Pro are both variable. Numbers that are identifiers (participant codes in the grid) stay in **code**.

**Light chips: decided against.** `atoms/badge.css` set `.badge` to 370 for subordinate chips. That drew Light only on a Mac with the SF Mono download.

### What folds where

| before 64a2b36a | becomes | status |
|---|---|---|
| `.badge` 370, `.badge-user` 420, dark 490, `.tag-preview` 420 | code: **one weight for every tag**, `--bn-weight-mono-tag` (460 light, 400 dark); colour separates sentiment chips from codebook tags | shipped |
| `.picker-card-version` 420 | code at `--bn-weight-mono` | shipped |
| `.screens-sub code` 490 | path at `--bn-weight-mono-emphasis` (560) | shipped |
| footer `kbd` 0.85em | keycap at micro, 400 | shipped |
| `player.html` status line, a copy of the old stack | path; the shipped stack written out | shipped |
| `WelcomeIllustrations.swift` stacks | `ui-monospace,Menlo,monospace` in all six (Mac-only webviews); not generated | shipped |
| `WelcomeTimelineCSS.swift` | regenerated from the theme | shipped |
| heatmap cells, metric values, hero score (490), threshold axis, slider values, counters and confidence, pending count, tooltip metrics and footer | figures: body face with tabular figures, weights unchanged | shipped (participant codes and tooltip speaker codes stay mono, as codes) |
| session durations ("42 min", `.session-entry-duration`) | timecode role, 400: a duration is a time | decided 15 Oct 2026; already drawn so, no change |
| codebook "+ add tag" chip and drag ghost at label (Codebooks lens, editable groups) | the chip at badge size and padding, 400, matching the `TagInput` that replaces it; the ghost keeps the cloned `.badge`'s size, padding and weight (its height follows `body` line-height, 2.5px shorter than in a quote card). `.tag-add-input` is emitted only by the sealed static renderer | shipped |
| Welcome HTML `.badge` copies with no weight; `.cap` at 500 | 460 in light to match the report; keycaps 400 or kept at 500 (Mac-only) | **open** |
| native Welcome chip (`WelcomeIllustrations.swift:136`, 11 regular) | match the report's light 460 | **open** |
| `.pattern-label` 520 | rendered only by the dev `GridSpecimen` route; code at 400 when next touched | **open**, dev-only |
| coverage timecode 0.85em | timecode at caption; `.coverage-segment` is emitted only by the sealed static renderer | **open**, sealed surface |
| clipboard `MONO` in `transcriptCopy.ts` | stays a literal; it already matches the stack minus `ui-monospace` and Cascadia | by design |
| dev surfaces (`GridSpecimen`, playground, run inspector, dev and chat-lens pages) | when next touched | **open**, dev-only |

## 5. Not measured (open after shipping)

- **Safari's DOM on a Mac with the download.** Driving Safari needs a settings change. Safari limits web content to system fonts, and WebKit's canvas already ignores the download, so it is expected to match the stock-Mac WebKit row. A ten-second human check: open the specimen in Safari and read the "drawn in" line.
- **Firefox.** Version 157 is installed here, but headless Firefox refused a throwaway profile, and its real profile was not touched. Firefox has no `ui-monospace`, so the proposed stack should reach Menlo on a Mac and Cascadia Mono or Consolas on Windows.
- **Linux.** The aella boxes or CI could answer it. Expected DejaVu Sans Mono by name.
- **Windows 10 with a current Edge.** The VM's Edge is 92, from the clean image; its Courier New generic may differ in Edge 14x. Neither stack reaches the generic there.
- **x-height.** Whether mono at the same pixel size reads larger than the body face. The sizes are carried over, not re-tuned.

## 6. Ground truth, 15 Oct 2026

**Read this before touching monospace again.** Machine-readable copy: `experiments/monospace-audit/ground-truth.json`.

### Environments

| name | what |
|---|---|
| Mac, developer | macOS 27.0 (26A428), arm64, with Apple's SF Mono download (`com.apple.pkg.SFMonoFonts`) |
| Mac, stock | the same Mac with "SF Mono" removed from each stack, which is what a Mac without the download resolves |
| Mac app WebKit | sandboxed WKWebView, default configuration, system WebKit 22625.1.29.11.27; agrees with Playwright WebKit 26.4 to the pixel |
| Chromium on a Mac | Playwright 1.60.0, Chromium 148.0.7778.96 |
| Windows 11 | Enterprise evaluation 26H2, build 26300, Edge 152.0.4191.66, Windows Terminal 1.18 inbox (VirtualBox 7.0.26 on benbecula) |
| Windows 10 | 22H2 clean image, Edge 92.0.902.67 (same host) |

### Which face each stack reaches

| environment · browser | web token before 64a2b36a | desktop token before 64a2b36a | shipped stack | generic `monospace` | `ui-monospace` |
|---|---|---|---|---|---|
| Mac, developer · WebKit | SF Mono download | SF Mono download | system SF Mono | Menlo (Courier without `lang`) | system SF Mono |
| Mac, developer · Chromium | SF Mono download | SF Mono download | Menlo | Courier | unsupported |
| Mac, stock · WebKit | Menlo | system SF Mono | system SF Mono | Menlo | system SF Mono |
| Mac, stock · Chromium | **Courier** | **Courier** | Menlo | Courier | unsupported |
| Windows 11 · Edge 152 | Consolas | — | Cascadia Mono | Consolas | unsupported |
| Windows 10 · Edge 92 | Consolas | — | Consolas | **Courier New** | unsupported |

Cascadia Mono on Windows 11 is not a system font file. It is not in `C:\Windows\Fonts` or the HKLM/HKCU font registry; it comes from the Windows Terminal package, as a shared font. Edge resolves it by name all the same, and GDI+ lists ExtraLight, Light, SemiLight, Regular and SemiBold. Windows 10 has none. Registry `ProductName` reads "Windows 10" on Windows 11; trust the build number.

### What each weight draws

Ink relative to 400 in the same face. "B" is the face's Bold.

| face | 370 | 420 | 440 | 460 | 480 | 490 | 500 | 520 | 550 | 560 | 600 | 700 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| system SF Mono (WebKit) | −5% | +3% | +6% | **+9%** | +12% | +14% | +15% | +18% | +23% | **+24%** | +30% | +46% |
| SF Mono download (both engines) | −21% (Light) | +15% (Medium) | | | | +15% | +15% | +29% (Semibold) | +27% | +27% | +30% | +49% |
| Menlo (Mac, both engines) | 0 | 0 | 0 | **0** | 0 | 0 | 0 | B | B | **B** | B | B |
| Courier (Mac) | 0 | 0 | | 0 | | 0 | 0 | B | B | B | B | B |
| Consolas (Windows Edge) | | | 0 | **0** | 0 | 0 | 0 | 0 | B | **B** | B | B |
| Cascadia Mono (Windows 11 Edge) | | | 0 | **0** | 0 | 0 | +16% | +16% | +16% | **+16%** | +16% | +27% |

The system SF Mono figures are at 11–13 px; other strings and sizes move them by 2–5 points, not their order. Menlo's Bold is +33–39%, Courier's +37–45%, Consolas's +33–36%. Blank cells were not measured. The bold columns are the shipped values (460 for light tags, 560 for emphasis).

### How each platform picks a weight

- **Mac, both engines:** the CSS rule. Above 500, the next heavier face that exists, so a Regular-and-Bold family flips to Bold at 501.
- **Windows Chromium (DirectWrite):** the nearest named weight, ties going heavier. Consolas is Regular to 540 and Bold from 550; Cascadia Mono is Regular to 490 and SemiBold from 500.
- **The static SF Mono download:** 300 and 370 draw Light; 420–500 Medium; 520–600 Semibold; 700 Bold.

### Face metrics (em)

| face | advance | x-height | cap height | descender |
|---|---|---|---|---|
| SF Mono | 0.618 | 0.530 | 0.705 | 0.179 |
| Menlo | 0.602 | 0.547 | 0.729 | 0.208 |
| Cascadia Mono | 0.586 | | | |
| Consolas | 0.550 | | | |
| Courier New | 0.600 | | | |

### Measurement traps

All five produced a confident wrong answer during this audit.

1. **WebKit `<canvas>` ignores user-installed fonts; its DOM does not.** Canvas text on the developer's Mac drew the system SF Mono while the page drew the download. Measure DOM pixels.
2. **Chromium's `fullPage` screenshot resizes the viewport, and while it does, its generic `monospace` draws Menlo instead of Courier.** Use a viewport tall enough for every row, or ask CDP (`CSS.getPlatformFontsForNode`).
3. **The generic depends on the page's `lang`.** WebKit's generic is Courier without `lang` and Menlo with `lang="en"`.
4. **Pixel hashes of rows misidentify faces.** Compare large-glyph ink (100 px) against reference rows on the same page, or use CDP.
5. **A stack with double quotes inside an inline `style="…"` attribute breaks the attribute,** and the row silently falls back to 16px serif. Single-quote family names in generated markup.

### Reproduce

From the repo root; Playwright is resolved from `e2e/`:

```bash
node experiments/monospace-audit/gen-pages.mjs /tmp/mono && node experiments/monospace-audit/probe-playwright.mjs /tmp/mono
```

- `face-check.mjs`: which face each stack reaches, by large-glyph ink, both engines, with and without `lang`.
- `probe-wkwebview.swift` and its `.entitlements`: the sandboxed-WKWebView probe, built as a minimal `.app` (steps in the file header).
- `analyse.py`: the ink table; `results-2026-10-15.json` is this run.
- `windows/edge-check.sh [vm]` and `windows/font-list.sh [vm]`: run on the Mac that hosts the VirtualBox VMs (`docs/release-winget.md`). They boot the VM headless, render `windows/fontcheck.html` in headless Edge, or list the installed mono fonts, then power off and restore the `clean` snapshot. `windows/ink.mjs` reads the screenshot.
- `build-specimen.py`: regenerates the specimen. It reads the theme as it stood before 64a2b36a, so its "Today" columns stay the baseline and its "Proposed" columns show what shipped.
