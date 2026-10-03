import SwiftUI

/// Native toolbar search and the Quotes starred toggle. Both drive the embedded
/// SPA via the bridge (the SPA's own SearchBox / ViewSwitcher are not rendered
/// in embedded mode). Tag filtering is the tag sidebar, so there is no tag
/// control here.
///
/// Search is a SwiftUI TextField in its own toolbar item rather than a native
/// `.searchable` field. That was tried on 3 Oct 2026 and rejected by
/// measurement: attached to the detail column it gave that column a hard
/// minimum width and the split view overflowed, pushing the projects column off
/// the window's left edge (desktop/CLAUDE.md, the `.searchable` gotcha;
/// design-desktop-nav-toolbar-rearrangement.md §4.4). This control changes no
/// column geometry. It draws no fill of its own either — the system glass
/// around the toolbar item is the only chrome (the earlier `.quaternary`
/// capsule read as a grey pill inside macOS 26's glass pill).
///
/// Shown on every lens that will have search (Quotes, Sessions, Codebook,
/// Signals); it only *filters* on Quotes. Elsewhere it is present and inert,
/// placeholder unchanged — accepted 3 Oct 2026 while multi-lens search is
/// built, instead of a disabled button that was the one grey thing in the
/// toolbar.

/// Raises the `visibilityPriority` of the `NSToolbarItem` this view is hosted
/// in. Apple: "When a toolbar doesn't have enough space to fit all of its
/// items, it pushes lower-priority items to the overflow menu first. When two
/// or more items have the same priority, the toolbar removes them one at a
/// time starting from the trailing edge." SwiftUI gives every `ToolbarItem`
/// the same priority and no way to change it, so the trailing item — search —
/// always folded first. With this, the actions capsule folds and the open
/// field stays, as Photos does. Targeted AppKit surgery where SwiftUI cannot
/// deliver (nav/toolbar spec §0); it reads the window's toolbar and writes one
/// property. If the item is not found (a hosting change upstream), nothing
/// happens and the toolbar behaves as before — never worse than today.
struct ToolbarItemPriority: NSViewRepresentable {
    let priority: NSToolbarItem.VisibilityPriority
    init(_ priority: NSToolbarItem.VisibilityPriority) { self.priority = priority }

    func makeNSView(context: Context) -> ProbeView { ProbeView(priority: priority) }
    func updateNSView(_ nsView: ProbeView, context: Context) { nsView.apply() }

    final class ProbeView: NSView {
        let priority: NSToolbarItem.VisibilityPriority
        private var observers: [NSObjectProtocol] = []

        init(priority: NSToolbarItem.VisibilityPriority) {
            self.priority = priority
            super.init(frame: .zero)
        }
        required init?(coder: NSCoder) { nil }
        deinit { observers.forEach(NotificationCenter.default.removeObserver) }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            observers.forEach(NotificationCenter.default.removeObserver)
            observers = []
            guard let window else { return }
            // The item list is populated after the view lands in the window;
            // one hop later is enough on 15 and 27 (measured 3 Oct 2026). A
            // toolbar rebuilt on a lens switch, and every resize, re-apply:
            // the priority was measured lost after a rebuild without this.
            DispatchQueue.main.async { [weak self] in self?.apply() }
            let center = NotificationCenter.default
            observers.append(center.addObserver(forName: NSWindow.didResizeNotification, object: window,
                                                queue: .main) { [weak self] _ in self?.apply() })
            observers.append(center.addObserver(forName: NSWindow.didEndLiveResizeNotification, object: window,
                                                queue: .main) { [weak self] _ in self?.apply() })
        }

        func apply() {
            guard let toolbar = window?.toolbar else { return }
            for item in toolbar.items {
                guard let host = item.view, isDescendant(of: host) else { continue }
                if item.visibilityPriority != priority { item.visibilityPriority = priority }
                break
            }
            if SidebarFitTrace.isEnabled { SidebarFitTrace.noteToolbar(toolbar) }
        }
    }
}

/// Whether a typed value should cross the bridge. A view's decision in a
/// helper, as `LensItem.tab` and `ProjectSubtitle.resolve` are: the echo guard
/// (the SPA echoes the query back, and re-sending it would loop) and the lens
/// gate (only Quotes filters) are the two silent failures this exists to pin.
enum QuotesSearchPush {
    static func shouldPush(typed: String, lastKnown: String, activeTab: Tab?) -> Bool {
        activeTab == .quotes && typed != lastKnown
    }
}

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
                field
            } else {
                Button { expanded = true } label: {
                    Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
                }
                // ⌘F is wired now (12 Sep 2026), so the tooltip advertises it.
                // Interpolated rather than given its own key — the symbol needs no
                // translation, and the label already has one in all 21 locales.
                .help("\(i18n.t("desktop.toolbar.search")) (⌘F)")
            }
        }
        // Surface store-originated query changes (Cmd+E, findNext, All Quotes
        // reset): expand the field and mirror the text so the user sees the term.
        // Guarded so the SPA echo of the user's own typing never clobbers it.
        .onChange(of: bridgeHandler.quotesSearchQuery) { _, newValue in
            if !newValue.isEmpty { expanded = true }
            if newValue != text { text = newValue }
        }
        // A typed code becomes a token ("p3 " → said by p3) and leaves the
        // text. When the store's query was already empty it does not change, so
        // the observer above never fires and "p3 " would stay in the field.
        .onChange(of: bridgeHandler.quotesSearchTokens) { _, _ in
            if bridgeHandler.quotesSearchQuery != text { text = bridgeHandler.quotesSearchQuery }
        }
        // Edit ▸ Find (⌘F). Both assignments are load-bearing: when collapsed,
        // `expanded` renders the field and its `.task` takes focus; when already
        // expanded, `.task` does not re-fire, so `focused` is the only thing that
        // returns the caret to a field the user has clicked away from. Setting
        // `focused` while collapsed is a harmless no-op — the field isn't there.
        .onChange(of: bridgeHandler.focusSearchRequests) { _, _ in
            expanded = true
            focused = true
        }
        // Photos' behaviour when the toolbar is tight: the open field wins and
        // the tools fold into `»`. NSToolbar decides that by
        // `visibilityPriority`, which SwiftUI does not expose, so a probe
        // raises this item's priority at runtime (`ToolbarItemPriority`).
        .background(ToolbarItemPriority(.user))
        // The field shows the Quotes query on Quotes and nothing elsewhere.
        // Leaving Quotes drops the text without sending it (the store keeps the
        // query; coming back reseeds from it), so a late echo or a store reset
        // can never write the Quotes query into the Sessions field.
        .onChange(of: bridgeHandler.activeTab) { _, tab in
            debounce?.cancel()
            if tab == .quotes {
                text = bridgeHandler.quotesSearchQuery
                expanded = !text.isEmpty
            } else {
                text = ""
                expanded = false
            }
        }
    }

    /// The input itself, in the toolbar item.
    private var field: some View {
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
                    // Always laid out, shown only with text: adding it on the
                    // first character widened the whole item by its width.
                    Button(action: clear) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                            .font(.system(size: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(i18n.t("desktop.toolbar.searchClear"))
                    .opacity(text.isEmpty ? 0 : 1)
                    .disabled(text.isEmpty)
                    .accessibilityHidden(text.isEmpty)
                }
                .padding(.horizontal, 4)
                // `.task` (not `.onAppear`) — toolbar-hosted views fire `.onAppear`
                // unreliably on macOS 26 (desktop/CLAUDE.md). Seed only when empty
                // so a re-expand mid-typing can't clobber an in-flight keystroke.
                .task {
                    if text.isEmpty { text = bridgeHandler.quotesSearchQuery }
                    focused = true
                }
    }

    /// Debounce 150ms before crossing the bridge (the SPA SearchBox did the same).
    private func scheduleSearch(_ value: String) {
        debounce?.cancel()
        debounce = Task {
            try? await Task.sleep(for: .milliseconds(150))
            if Task.isCancelled { return }
            // Decided when the debounce fires, not when it was scheduled: a
            // lens switch inside the 150 ms must not send to the wrong lens.
            guard QuotesSearchPush.shouldPush(
                typed: value, lastKnown: bridgeHandler.quotesSearchQuery,
                activeTab: bridgeHandler.activeTab
            ) else { return }
            bridgeHandler.setQuotesSearch(value)
        }
    }

    private func clear() {
        text = ""
        debounce?.cancel()
        if bridgeHandler.activeTab == .quotes { bridgeHandler.setQuotesSearch("") }
    }

    private func clearAndCollapse() {
        clear()
        expanded = false
    }

    private func collapseIfEmpty() {
        if text.isEmpty { expanded = false }
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
