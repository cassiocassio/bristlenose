# Motion tokens — one set of numbers, web and Swift

_Drafted 9 Nov 2026, revised the same day after three independent reviews (facts, parsimony, native fit). Status: PLAN, nothing built. Counts are from grep at that date; re-run them at HEAD before ratcheting anything._

**The aim is the same as the rest of the app: the seam between the macOS shell and the webview is zero.** A transition that has a native counterpart matches it, measured. Hand-typed numbers in two languages are what to remove, and there are more moving elements every month.

Companions: `docs/design-motion.md` (the why, the taxonomy, the prose reference in §6), `docs/design-notification-surfaces.md` (toasts, pills, rings, notifications — out of scope here).

## 1. What exists today

### CSS (`bristlenose/theme/`)
- 154 `transition:` declarations; 34 carry a literal duration, of which 33 are true literals (`atoms/modal.css:25` counts only for `visibility 0s`). Two are `transition: all`: `molecules/hidden-quotes.css:25` (`300ms ease`, a literal) and `organisms/inspector.css:361` (already token-based).
- `--bn-transition-fast/normal/slow` = `0.15s/0.2s/0.3s`, all plain `ease` (`tokens.css:286-288`).
- Measured, named tokens already exist: the sheet (`--bn-modal-enter 230ms`, `-fade 100ms`, `-ease`, `--bn-modal-exit 240ms`), focus mode, arrival, shimmer (locked 18 Jul 2026).
- Not tokens, just literals: sidebar grid `75ms ease` (`organisms/sidebar.css:157`), inspector `75ms cubic-bezier(0, 0, 0.2, 1)` (`inspector.css:108`), and the TOC panel's own 75ms decelerate/accelerate keyframes (`sidebar.css:358/387`). One role, three curves, all web-side.
- Reduced motion is handled in 14 CSS files; `design-motion.md` §5.3 records the gaps.

### Swift (`desktop/Bristlenose/Bristlenose/`)
- **In scope: 8 hand-typed durations in 5 files as drafted 9 Nov; two sites were missed and are unclassified: `ProjectSidebarOutline.swift:708` (a 0.2 s height slide, added 9 Nov) and `WelcomeHomeView.swift:597,779,1011` (0.8 / 0.22 / 0.2). `ProviderProblemPill.swift:101` is a spring (`.smooth`), so it belongs to the springs rule below, not here. Re-run the grep before Phase 1.**, four values (0.12, 0.15, 0.2, 0.25): `ContentView.swift:4183,4691`, `LLMSettingsView.swift:255,282`, `ProviderProblemPill.swift:100,101`, `ProjectRowActivityIndicator.swift:122`. (Parsimony review count, once the out-of-scope sites below are excluded. Fix one regex for the count before anything is ratcheted.)
- **Out of scope on purpose:** `WelcomeIllustrations.swift` (art-directed `Self.tempo`), the system-default `withAnimation {}` that moves the sidebar (`ContentView.swift:751,753`, `MenuCommands.swift:1036,1100`), `ToastView.swift` (notification plan), `ShoalDebugView` and the SpriteKit fades, and `ProjectSidebarOutline.swift:747` (which sets duration 0, a suppressor, not a motion site).
- Springs (`ProviderProblemPill` `.smooth`, `TumblingProjectIcon` `.spring`) are not Béziers and sit outside a four-number token.
- Reduce Motion: honoured in effect, usually by a gate further up the call chain; `SettingsView.swift:353` centralised its check in the helper after both call sites forgot. Under Reduce Motion Swift **snaps** (`reduceMotion ? nil : …`) where the web sheet **fades**: a seam of its own.
- Shimmer: `SidebarShimmerText.swift` re-types the locked CSS numbers, with a second private twin in `ShimmerTunerView.swift`. Nothing pins either to `tokens.css`.
- A hand-rolled disclosure in native code: `ContentView.swift:4691` (Export popover, `expanded`). Check whether it should be a `DisclosureGroup`.

### Existing mechanisms
`scripts/gen-welcome-timeline.py` generates `WelcomeTimelineCSS.swift` from `tokens.css` and others, and `tests/test_welcome_timeline.py` fails on drift. Parity tests that read the other language's source are the house pattern for a few numbers (`CLAUDE.md` §Seams).

## 2. Curves: a real gap, no visible pair yet

CSS `ease` is `cubic-bezier(0.25, 0.1, 0.25, 1)`; the CSS `ease-in-out` keyword and (reportedly, Apple does not publish it) SwiftUI's `.easeInOut` are `(0.42, 0, 0.58, 1)`. So the generic web tokens and Swift's `.easeInOut` are two different curves. The sheet's `(0, 0, 0.58, 1)` is exactly CSS `ease-out` and Core Animation's `easeOut`, so it ports. `Animation.timingCurve(c0x, c0y, c1x, c1y, duration:)` takes the same four numbers as `cubic-bezier()`.

**Do not build a test around this.** Today no element animates on both sides next to each other with the two curves, and for 0.12–0.25 s fades the difference is noise. Correct the curve when a role migrates and only for roles that move.

## 3. Source of truth and the Swift file

CSS tokens in `tokens.css` are the source. **A short hand-written `Motion.swift`** (about four constants built with `.timingCurve`) takes the values, and **one parity test** reads `tokens.css`, `Motion.swift` and `SidebarShimmerText.swift` and fails when a paired value disagrees. That fits the existing parity-test seam and every assertion can fail. A generator (the welcome-timeline pattern) earns its keep for whole CSS documents, not four numbers: revisit it if the roles grow past about ten or the springs/reduced variants make hand copying error-prone. Owner decision 1, decided: hand-written (§8).

**Guard:** no motion constant is applied to anything the system owns — `columnVisibility`, `.sheet`, popovers, `DisclosureGroup`, `NSOutlineView` expansion. A header comment in `Motion.swift` says so, because the first person to see a bare `withAnimation {}` will want to "fix" it with a 75ms web number.

## 4. Roles, not numbers

Only measured values become tokens. The rest stay rows in this table until a measurement turns them into tokens.

| Role | Today | Native counterpart | Status |
|---|---|---|---|
| `sheet-enter` / `sheet-exit` | 230ms `ease-out` (100ms solid) / 240ms linear | window sheet (`beginSheet` / `.sheet`), measured on a stock Save sheet, light mode, commit `0d482d246` | **measured** — record the OS version; dark mode still owed |
| `sidebar-reveal` (web TOC) | 75ms, three curves | none: the window's sidebar is system-owned and slower, NavigationSplitView | **tuned by eye (web)**, not native; settle the three curves inside the web layer |
| `help-tag` | tooltip: 300ms delay, 8px float, 0.2s ease-out | help tags fade after a delay and warm up (the next shows at once) | owed: split from popover; measure delay and warm-up |
| `popover` | none distinct | NSPopover `animates` | owed |
| `disclosure` | `max-height` 0.2–0.35s, chevron 0.15s | `ProjectSidebarOutline` expand, in the same window | owed: record side by side |
| `progress-fill` | width 0.2–0.4s | `NSProgressIndicator`: tweens or steps? | owed |
| `indeterminate-spinner` | web spinners `0.8s linear infinite` | native `ProgressView().controlSize(.small)` | owed: a native and a web spinner in one window is a visible seam |
| `menu` | web dropdown budget 75–200ms (`design-motion.md` §6) | NSMenu opens instantly, blinks, fades out | owed: the native answer may be "open: 0" |
| `scroll-jump` | `behavior: "smooth"` | respects Reduce Motion | see §7 |
| `hover-fade` / button states | 0.1–0.15s | classic push buttons: no hover, instant press; Liquid Glass on macOS 26 reacts to press | owed: measure on 26; rule now: no `transition` on `:active` |
| `focus-mode`, `arrival`, `shimmer` | existing tokens | — | keep as they are |

## 5. Phases (revised)

Three commits, all beta-safe. Every check fails when CSS and Swift drift.

| # | Phase | Result |
|---|---|---|
| 1 | **CSS lint.** A theme test (model: `tests/test_theme_token_resolution.py`) fails on `transition: all` and on a literal duration outside `tokens.css` unless it is on an allowlist with a reason per entry (matched-to-native, web-only, awaiting measurement). Fix the two `transition: all`. Swap **only exact matches** (`0.15s/0.2s/0.3s ease`, about 17 of the 34) for the existing tokens: that is the only swap with no visual change. Any other swap (`0.35s`, `ease-out`, `linear`) is a visible change and goes through the mockup-then-approve gate. No ratchet on the allowlist: the test already is the gate. | The 34 are classified by the allowlist itself. |
| 2 | **`Motion.swift` + parity test.** Constants from the measured roles (sheet, plus any value the 8 sites genuinely share), migrate the 8 sites in one commit, make the shimmer defaults a parity row, and assert zero hand-typed `duration:` outside system-owned and out-of-scope files. List every bare `withAnimation {}` and `.animation(.default)` and allow only the system-owned ones. | Hand-typed Swift numbers gone, and a test that notices their return. |
| 3 | **Reduce Motion pair (small).** Give each role a reduced variant (a fade, not a snap) so the Swift accessor takes `reduceMotion` and returns the right fallback, matching the web sheet. | The Reduce Motion seam closes. |

Measurement is **not a phase** here. It is a backlog list (§6) that turns table rows into tokens as it lands.

## 6. Measurements owed (a real Mac, macOS 26, both appearances; screen-record at 60/120 fps and count frames)

1. NavigationSplitView collapse: duration, curve; does `withAnimation(.linear(duration: 2))` change it; does Reduce Motion stop the slide? (If the bare call is system-owned, the four sidebar sites are right as they are; if Reduce Motion does not stop it, wrap them in `reduceMotion ? nil : …`.)
2. Help-tag delay, warm-up and movement. 3. NSPopover appear/disappear. 4. `ProjectSidebarOutline` expand: row slide and chevron. 5. Small spinner: period, stepped or continuous. 6. Determinate `NSProgressIndicator`: tween or step. 7. macOS 26 push-button press, Liquid Glass press, toolbar-item hover. 8. NSMenu open and dismiss. 9. Focus ring appearance. 10. The Save sheet in dark mode.

## 7. A separate accessibility hole, independent of the tokens

Smooth scrolling ignores Reduce Motion at six call sites: `frontend/src/utils/scrollToLand.ts:89,95,108`, `contexts/PlayerContext.tsx:323`, `islands/TranscriptPage.tsx:266,652`. Only `TranscriptPage.tsx:765` checks `prefers-reduced-motion`. An explicit JS `behavior: "smooth"` overrides a CSS `scroll-behavior` media query. The HIG asks to reduce "peripheral motion". Fix: route the callers through `scrollToLand` and pass `"auto"` under reduce. Small, real, beta-safe — worth doing even if the rest of this plan waits.

## 8. Owner decisions

1. ~~Hand-written `Motion.swift` + parity test, or the generated file?~~ **Decided 9 Nov 2026: hand-written, with the parity test.** Revisit a generator only if the roles pass about ten or springs and reduced variants make hand copying error-prone.
2. Under Reduce Motion, should Swift fade like the web sheet (phase 3) or keep snapping?
3. Does the 75ms TOC matching "native sidebar" claim stay? Measure first (§6.1); if the native slide is three times slower, drop the claim and keep the 75ms as a web tuning.
4. Button hover/press: settled by §6.7, not here.

## 9. Deliberately left alone

System-default `withAnimation {}` the OS owns; welcome-illustration tempo; the toast and activity surfaces; springs; any animation library (the work is naming and sharing numbers); the frozen vanilla `theme/js/` (static render).

## 10. Verification each phase needs

Phase 1: the lint fails on a seeded `transition: all` and a seeded literal; before/after screenshots of the exact-match swaps show no change (visual-diff page). Phase 2: the parity test goes red after editing a token or a Swift constant, green after restoring; the literal-duration assertion goes red on a seeded `.easeInOut(duration: 0.3)`. Phase 3: human check with Reduce Motion on, in the app and in the browser. Motion feel is not testable by pytest; human QA stays.
