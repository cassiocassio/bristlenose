import SwiftUI

/// Quotes-lens native toolbar controls: an expanding search field and a starred
/// toggle. Both drive the embedded SPA via the bridge (the SPA's own SearchBox /
/// ViewSwitcher are not rendered in embedded mode). Tag filtering is the tag
/// sidebar, so there is no tag control here.
///
/// REVIEW TARGETS (gruber / swiftui-pro + GUI QA):
///  - Search uses a SwiftUI capsule + TextField rather than a true NSSearchField
///    (NSSearchToolbarItem isn't directly reachable from a SwiftUI-hosted
///    toolbar). Decide whether the native NSSearchField look is worth an
///    NSViewRepresentable.
///  - Focus-on-expand uses `.task` (not `.onAppear`, which is unreliable on
///    toolbar-hosted views per desktop/CLAUDE.md). Verify it actually focuses.
///  - Cmd+F currently still routes to the web `find` action (a no-op on the
///    embedded Quotes field) — wiring Cmd+F to expand+focus this control needs
///    shared state with the Find menu item; deferred, flagged.

/// Expanding search: a magnifier button that reveals an inline search field.
struct QuotesSearchToolbarControl: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    @State private var expanded = false
    @State private var text = ""
    @FocusState private var focused: Bool

    var body: some View {
        if expanded {
            HStack(spacing: 4) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(.secondary)
                    .font(.system(size: 12))
                TextField(i18n.t("desktop.toolbar.search"), text: $text)
                    .textFieldStyle(.plain)
                    .frame(width: 150)
                    .focused($focused)
                    .onChange(of: text) { _, newValue in
                        bridgeHandler.setQuotesSearch(newValue)
                    }
                    .onSubmit { collapseIfEmpty() }
                    .onExitCommand { clearAndCollapse() }
                if !text.isEmpty {
                    Button(action: clear) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                            .font(.system(size: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(i18n.t("desktop.toolbar.searchClear"))
                }
            }
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(.quaternary, in: Capsule())
            // `.task` (not `.onAppear`) — toolbar-hosted views fire `.onAppear`
            // unreliably on macOS 26 (desktop/CLAUDE.md).
            .task {
                text = bridgeHandler.quotesSearchQuery
                focused = true
            }
            // Mirror store-originated changes (All Quotes reset, Cmd+E selection)
            // back into the field. Echo-guarded on value to avoid clobbering the
            // user's in-flight typing.
            .onChange(of: bridgeHandler.quotesSearchQuery) { _, newValue in
                if newValue != text { text = newValue }
            }
        } else {
            Button { expanded = true } label: {
                Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
            }
            .help(i18n.t("desktop.toolbar.searchShortcut"))
        }
    }

    private func clear() {
        text = ""
        bridgeHandler.setQuotesSearch("")
    }

    private func clearAndCollapse() {
        clear()
        expanded = false
    }

    private func collapseIfEmpty() {
        if text.isEmpty { expanded = false }
    }
}

/// Disabled search button shown on lenses that don't have search yet
/// (Sessions / Codebook / Analysis). Reserves the toolbar slot and sets the
/// expectation; a self-explaining tooltip says why it's dim. Deliberate
/// exception to the "toolbars morph" rule — search is conceptually universal,
/// so a stable disabled slot reads better than a button that pops in and out.
struct QuotesSearchDisabledButton: View {
    @ObservedObject var i18n: I18n

    var body: some View {
        Button {} label: {
            Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
        }
        .disabled(true)
        .help(i18n.t("desktop.toolbar.searchComingSoon"))
    }
}

/// Starred filter: a single star toggle (active when the lens is showing
/// starred-only). Flips between the existing `allQuotes` / `starredQuotesOnly`
/// SPA actions; active state mirrors `bridgeHandler.quotesViewMode`.
struct QuotesStarredToggle: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var isStarred: Bool { bridgeHandler.quotesViewMode == "starred" }

    var body: some View {
        Button {
            bridgeHandler.menuAction(isStarred ? "allQuotes" : "starredQuotesOnly")
        } label: {
            Label(
                i18n.t("desktop.menu.view.starredQuotesOnly"),
                systemImage: isStarred ? "star.fill" : "star"
            )
        }
        .help(i18n.t(isStarred ? "desktop.menu.view.allQuotes" : "desktop.menu.view.starredQuotesOnly"))
    }
}
