---
status: built (88622103), awaiting QA
date: 3 Oct 2026
revision: 2 (after the 3 Oct review)
mockup: docs/mockups/desktop-sidebar-footer-version-feedback.html
---

# Sidebar footer: version and Send Feedback

Mac app only. The sidebar gets a footer:

- **Left:** the app version as small plain text, `0.32.0 alpha`. Shown to everyone during the pre-release period.
- **Right:** a small borderless `ladybug` button that opens Send Feedback **in its own window**.

The precedent for the button is Claude's desktop app. Nothing else goes in the footer. Toolbar rev 3 (`design-desktop-nav-toolbar-rearrangement.md` §3.3, 3 Oct 2026) moved New Project / New Folder to a `+⌄` in the sidebar's toolbar and rejected a labelled footer and a footer gear. This footer holds neither New nor Settings, so it doesn't reopen that decision.

## Decided (3 Oct 2026)

1. **Each control acts on its own window.** The button sets its window's `showingFeedbackSheet` directly. Help ▸ Send Feedback… acts on the **front (key) window**, not every window.
   Today the menu calls `openFeedback()`, which posts `.showFeedbackSheet` to the whole app, and each ContentView answers it (`BridgeHandler.swift:1067`, `ContentView.swift:1023`). With three windows open, three sheets appear.
   The menu fix uses the pattern View ▸ Hide/Show Projects already uses: a scene focused value published by ContentView and read by the menu command.
   The status page's `open-feedback` bridge action stays on the notification. It comes from one webview, so it should target that webview's window. Check this during the build: if the notification still fans out, scope it the same way.
2. **Plain text, not a capsule.**
   - It's `Text` with `.caption2`, `.monospacedDigit()` and `.secondary`, with no background and no monospaced design.
   - It is not selectable: selectable text in a sidebar takes keyboard focus away from the project list.
   - The tooltip is `"<version> (<build>)"`, numbers only, so it needs no new string. TestFlight ships several builds under one marketing version, and the tooltip tells them apart.
3. **The list slides under a soft edge.**
   - **macOS 26 and later:** `.safeAreaBar(edge: .bottom)` gives the system's soft scroll edge as rows pass beneath the footer.
   - **macOS 15:** there is no soft edge, so text would run behind text. There the footer stacks below the list, `VStack(spacing: 0) { sidebar; footer }`.
   - The split is one `if #available(macOS 26, *)`.
4. **The button stays small and subtle.** The glyph is unchanged. Only its invisible click area grows to 22 × 22 (`.frame(width: 22, height: 22).contentShape(Rectangle())`), which meets Apple's 20 pt minimum without adding pixels.
5. **The tooltip has no ellipsis.** Add a new key, `desktop.chrome.sendFeedbackHelp` = "Send Feedback", used for both `.help` and `.accessibilityLabel`. Each locale takes its value by stripping the ellipsis (`…` or `⋯`) from its existing `desktop.menu.help.sendFeedback`, so the menu and the button use the same words.

## Decided after review, and still open

6. **The stage word is beta** (decided 3 Oct 2026). Researchers read "beta" as "usable, a bit rough"; "alpha" is engineering jargon. TestFlight already calls every build a beta. The word goes before a paid App Store launch either way. The key is stage-neutral (`desktop.chrome.prereleaseVersion` = `"{{version}} beta"`), so a later change is a value change. Swept the same day: the `.dmg` expiry pill and alert, README, SECURITY.md, and on the website the terms page, the welcome page and the homepage.
7. **How the word is kept off the App Store.** It can't be gated at runtime: App Review uses the same StoreKit sandbox receipt as TestFlight (`DistributionChannel.swift`), and §2.2 rejects apps presented as betas.
   - **Current plan:** a compile-time `ReleaseStage.showsPrereleaseVersion`, plus a line on the App Store submission checklist (in the maintainer's private notes, kept outside the public tree).
   - **Review is not a backstop:** a reviewer can miss a 10 pt label.
   - **The alternative:** make the stage an Info.plist key that `check-pkg-shippable.sh` refuses on a submission marked for review.
   - This may simply dissolve: if the word goes before paid launch anyway, the App Store build never has it.

## What exists (reuse)

| Need | Shipped thing |
|---|---|
| Version and build | `BuildInfo.current.appVersion` and `.buildNumber` (`BuildInfo.swift:24,40–41`). Don't read `infoDictionary` a third time |
| The sheet | `FeedbackSheet`, presented by ContentView with the live-serve or `.serverless` config (`ContentView.swift:1026`) |
| Scene-scoped menu command | The focused-value pattern View ▸ Hide/Show Projects already uses (`ContentView.swift`, after `.sheet`) |
| Placeholder idiom | `i18n.t(key, ["version": v])` with `{{version}}` (`I18n.swift:270`). This is the form `check-locales.py --strict` checks; `%@` is unchecked |
| Width floor | `columnMin` 200 (`DetailFloor.swift:105`) |

## Implementation

**`SidebarFooter.swift` (new):**

```swift
struct SidebarFooter: View {
    @ObservedObject var i18n: I18n
    let onSendFeedback: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            if ReleaseStage.showsPrereleaseVersion {
                Text(i18n.t("desktop.chrome.prereleaseVersion",
                            ["version": BuildInfo.current.appVersion]))
                    .font(.caption2).monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .help("\(BuildInfo.current.appVersion) (\(BuildInfo.current.buildNumber))")
            }
            Spacer(minLength: 0)
            Button(action: onSendFeedback) {
                Image(systemName: "ladybug")
                    .frame(width: 22, height: 22)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
            .help(i18n.t("desktop.chrome.sendFeedbackHelp"))
            .accessibilityLabel(i18n.t("desktop.chrome.sendFeedbackHelp"))
        }
        .padding(.leading, 16).padding(.trailing, 10)
        .padding(.vertical, 6)
    }
}

/// Compile-time on purpose: see docs/design-desktop-sidebar-footer.md item 7.
enum ReleaseStage { static let showsPrereleaseVersion = true }
```

**In `ContentView.swift`, at the `sidebar` call site,** before `.navigationSplitViewColumnWidth`. That covers both the shipping SwiftUI `List` and the flag-gated AppKit outline:

```swift
let footer = SidebarFooter(i18n: i18n) { showingFeedbackSheet = true }
if #available(macOS 26, *) {
    sidebar.safeAreaBar(edge: .bottom, spacing: 0) { footer }
} else {
    VStack(spacing: 0) { sidebar; footer }
}
```

Factor this into a small `@ViewBuilder`, so the `.navigationSplitViewColumnWidth` chain stays readable.

**Help menu:** replace `bridgeHandler.openFeedback()` with the focused-value action. Keep `openFeedback()` for the bridge path only (decision 1).

**`SidebarDeselectMonitor` (`ContentView.swift:19–62`):** on macOS 26 the list's table now extends under the footer, so a click on the ladybug lands inside the table's bounds below its last row, and the monitor clears the selection. Guard it: act only if the window's hit-test at the click lands on the table (or a view inside it), not on a control drawn over it. That's one `guard`, and it can't misfire on a real empty-space click.

**Locales:** add `desktop.chrome.prereleaseVersion` and `desktop.chrome.sendFeedbackHelp` to the 21 full locales (`zh-Hant-HK` inherits).
- Use a targeted insert, never a `json.load`/`dump` round-trip.
- Seeds for "alpha": de `Alpha`; fr `alpha`; es/it/pt/nl/ca/tr/pl/cs/nordics `alfa`; ja `アルファ版`; ko `알파`; ru `альфа-версия`; uk `альфа-версія`; zh-Hant `Alpha版`. For beta: Apple's own `BETA` forms (ja `ベータ版`, ko `베타`, ru `бета-версия`, etc.).
- Add a `glossary.csv` row for the stage word.
- Run `check-locales.py --strict`.

**Why localise it:** this is release-stage status every tester reads, not diagnostic chrome, and Apple localises its own BETA badge (`docs/design-i18n.md` §"Which surfaces are targets").

## Risks and build checks

1. **AppKit sidebar: built as a split view item accessory (3 Oct 2026).** The prediction held: under `.safeAreaBar` the outline stopped dead at the footer, while the toolbar above it got the soft edge. On macOS 26 the AppKit path now hosts `SidebarFooter` in a bottom-aligned `NSSplitViewItemAccessoryViewController` with `preferredScrollEdgeEffectStyle = .soft` (26.1+; "automatic" on 26.0), installed by a probe view that finds the sidebar's `NSSplitViewItem` (`SidebarFooterAccessory.swift`); the outline ignores the bottom safe area so it runs under it, as it already does under the toolbar. The SwiftUI list keeps `.safeAreaBar`; macOS 15 keeps the stacked footer.
   - **Measure, not given by the API:** the accessory's `automaticallyAppliesContentInsets` pads the accessory's own view, not the list. Whether the last row scrolls clear of the footer, and whether the scroller stops at it, has to be checked in the app.
   - **Also check:** the soft edge actually appears (AppKit draws it where the scroll view underlaps the accessory); hiding and showing the column keeps exactly one footer; full screen; the empty-space deselect guard still holds with the table under the footer; window drag from the footer's empty middle.
2. **Window drag:** the footer's empty middle must not start a window drag.
3. **Debug builds show the version twice:** the footer and the bottom-right build-info capsule. Accepted: they answer different questions.

## Tests

- **A test that the button opens one sheet, not one per window.** This is the one behaviour that was actually wrong, so it's the one worth pinning. Build two `ContentView`-shaped hosts, trigger one host's footer action, and assert that only that host's flag flips. If that can't be done without standing up the whole scene, test the menu's focused-value action instead, which carries the same bug.
- **No format test for the tooltip:** it's string interpolation.
- **The gates cover the two keys:** `check-locales.py --strict`.

## Human QA

In the built `.app`, on macOS 26+ and on 15 if available, light and dark:

1. **The footer:** reads `<MARKETING_VERSION> alpha` bottom-left and doesn't truncate at the narrowest sidebar. Hovering it shows version and build.
2. **The soft edge (26+):** scroll a long project list; the rows soften under the footer. On 15 the list ends above it.
3. **One window, one sheet:** open two windows (⌥⌘N). The ladybug opens Send Feedback in its own window only, and so does Help ▸ Send Feedback in the front window. The project selection survives the click.
4. **No project selected:** the ladybug still opens the sheet.
5. **Accessibility:**
   - Reduce Transparency and Increase Contrast on: the version stays readable.
   - With Full Keyboard Access on, Tab from the project list reaches the ladybug, and Space opens the sheet.
   - VoiceOver says "Send Feedback".
6. **Language:** switch to Japanese; both strings follow.

## Separate item, found during review

**The legal privacy page still says "We don't have a server".**
- The docs privacy page was corrected in the website repo on 31 Aug (`ad98272`) to describe the feedback form.
- The legal permalink, `content/privacy.html`, still says "We don't have a server … We don't collect any of your data" in both its body and its meta description. Live on 3 Oct 2026.
- The two pages now disagree. Reconciling them is website work, tracked outside this plan.
