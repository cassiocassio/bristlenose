import SwiftUI

/// Quotes-lens native toolbar controls: an expanding search field and a starred
/// toggle. Both drive the embedded SPA via the bridge (the SPA's own SearchBox /
/// ViewSwitcher are not rendered in embedded mode). Tag filtering is the tag
/// sidebar, so there is no tag control here.
///
/// Search is a SwiftUI capsule + TextField rather than a true NSSearchField
/// (NSSearchToolbarItem isn't directly reachable from a SwiftUI-hosted toolbar).
/// Three reviewers converged on keeping the capsule — see
/// docs/private/reviews/native-quotes-toolbar.md (consensus note).

/// Expanding search: a magnifier button that reveals an inline search field.
/// The field auto-expands when the store pushes a non-empty query (Cmd+E "Use
/// Selection for Find", findNext) so the user always sees what the report is
/// filtered by. Input is debounced 150ms before crossing the bridge, matching
/// the SPA SearchBox the native field replaced.
struct QuotesSearchToolbarControl: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    @State private var expanded = false
    @State private var text = ""
    @State private var debounce: Task<Void, Never>?
    @FocusState private var focused: Bool

    var body: some View {
        Group {
            if expanded {
                HStack(spacing: 4) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(.secondary)
                        .font(.system(size: 12))
                    TextField(i18n.t("desktop.toolbar.search"), text: $text)
                        .textFieldStyle(.plain)
                        .frame(width: 150)
                        .focused($focused)
                        .onChange(of: text) { _, newValue in scheduleSearch(newValue) }
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
                // unreliably on macOS 26 (desktop/CLAUDE.md). Seed only when empty
                // so a re-expand mid-typing can't clobber an in-flight keystroke.
                .task {
                    if text.isEmpty { text = bridgeHandler.quotesSearchQuery }
                    focused = true
                }
            } else {
                Button { expanded = true } label: {
                    Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
                }
                // Tooltip says "Search", not "Search (⌘F)" — Cmd+F isn't wired to
                // expand the native field yet, so don't advertise a dead shortcut.
                .help(i18n.t("desktop.toolbar.search"))
            }
        }
        // Surface store-originated query changes (Cmd+E, findNext, All Quotes
        // reset): expand the field and mirror the text so the user sees the term.
        // Guarded so the SPA echo of the user's own typing never clobbers it.
        .onChange(of: bridgeHandler.quotesSearchQuery) { _, newValue in
            if !newValue.isEmpty { expanded = true }
            if newValue != text { text = newValue }
        }
    }

    /// Debounce 150ms before crossing the bridge (the SPA SearchBox did the same).
    private func scheduleSearch(_ value: String) {
        debounce?.cancel()
        debounce = Task {
            try? await Task.sleep(for: .milliseconds(150))
            if Task.isCancelled { return }
            bridgeHandler.setQuotesSearch(value)
        }
    }

    private func clear() {
        text = ""
        debounce?.cancel()
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
struct SearchComingSoonButton: View {
    @ObservedObject var i18n: I18n

    var body: some View {
        Button {} label: {
            Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
        }
        .disabled(true)
        .help(i18n.t("desktop.toolbar.searchComingSoon"))
    }
}

/// Starred filter: a button-style toggle whose active state is a quiet
/// monochrome recessed background (`.tint(.secondary)`), not the accent-blue
/// default — chrome stays neutral; the star glyph carries the meaning (per the
/// colour-discipline rule). Flips between `starredQuotesOnly` and the
/// view-mode-only `showAllQuotes` action — turning the filter off preserves a
/// typed search query (star and search are orthogonal filters that compose).
/// Active state mirrors `bridgeHandler.quotesViewMode` (SPA owns the truth).
struct QuotesStarredToggle: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Toggle(isOn: Binding(
            get: { bridgeHandler.quotesViewMode == "starred" },
            set: { on in bridgeHandler.menuAction(on ? "starredQuotesOnly" : "showAllQuotes") }
        )) {
            Label(i18n.t("desktop.menu.view.starredQuotesOnly"), systemImage: "star")
        }
        .toggleStyle(.button)
        .tint(.secondary)
        .help(i18n.t(
            bridgeHandler.quotesViewMode == "starred"
                ? "desktop.menu.view.allQuotes"
                : "desktop.menu.view.starredQuotesOnly"
        ))
    }
}
