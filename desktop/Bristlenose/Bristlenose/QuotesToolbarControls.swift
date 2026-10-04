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
    /// The suggestions row ↩ would choose, by id (a row's position moves as
    /// new rows arrive; its id names its subject). Nil means the first row.
    @State private var highlightID: String?
    /// The list is closed until the researcher edits the text, and closes
    /// again on Esc, a choice, or a click away. Text put back by the store or
    /// a lens switch never opens it (`seed`).
    @State private var menuDismissed = true
    /// A value the code just wrote into `text`, so its `onChange` is not taken
    /// for typing.
    @State private var seeded: String?
    /// The token a first ⌫ in the empty field selected (§6).
    @State private var selectedToken: SearchSubject?
    /// Where the pointer was when the list opened: a list that opens under a
    /// resting pointer must not let it take the highlight from the free text.
    @State private var openMouse: NSPoint?
    @State private var fieldWidth: CGFloat = 0
    @State private var chipsWidth: CGFloat = 0

    private var onQuotes: Bool { bridgeHandler.activeTab == .quotes }
    private var tokens: [SearchTokenChip] { onQuotes ? bridgeHandler.quotesSearchTokens : [] }
    private var rows: [SearchSuggestionRow] { onQuotes ? bridgeHandler.searchSuggestions.rows : [] }
    private var rowIDs: [String] { rows.map(\.id) }
    private var highlighted: String? { SearchFieldKeys.highlighted(highlightID, rows: rowIDs) }
    private var menuOpen: Bool {
        SearchFieldKeys.isOpen(focused: focused, text: text, rows: rows.count, dismissed: menuDismissed)
    }

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
            seed(newValue)
        }
        // A typed code becomes a token ("p3 " → said by p3) and leaves the
        // text. When the store's query was already empty it does not change, so
        // the observer above never fires and "p3 " would stay in the field.
        .onChange(of: bridgeHandler.quotesSearchTokens) { _, tokens in
            seed(bridgeHandler.quotesSearchQuery)
            if !tokens.isEmpty { expanded = true }
            if let s = selectedToken, !tokens.contains(where: { $0.subject == s }) { selectedToken = nil }
        }
        // New rows keep the highlighted row while it is still offered; a re-post
        // that only moves counts (AutoCode, a hide) must not snap it back.
        .onChange(of: bridgeHandler.searchSuggestions) { _, _ in
            if let h = highlightID, !rowIDs.contains(h) { highlightID = nil }
        }
        .onChange(of: menuOpen) { _, open in openMouse = open ? NSEvent.mouseLocation : nil }
        .onChange(of: focused) { _, isFocused in if !isFocused { selectedToken = nil } }
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
                seed(bridgeHandler.quotesSearchQuery)
                expanded = !text.isEmpty || !bridgeHandler.quotesSearchTokens.isEmpty
            } else {
                seed("")
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
                    // Tokens sit before the text, as in Mail (§5), in a strip that
                    // scrolls past a cap so three people do not push the rest of
                    // the toolbar into `»`.
                    if !tokens.isEmpty { tokenStrip }
                    TextField(i18n.t("desktop.toolbar.search"), text: $text)
                        .textFieldStyle(.plain)
                        .frame(width: 150)
                        .focused($focused)
                        .onChange(of: text) { _, newValue in
                            if newValue == seeded { seeded = nil; return }  // the code wrote it
                            seeded = nil
                            menuDismissed = false
                            selectedToken = nil
                            highlightID = nil
                            scheduleSearch(newValue)
                        }
                        // ↩ on a closed list commits now, without the debounce wait.
                        .onSubmit {
                            commitNow()
                            collapseIfEmpty()
                        }
                        .onExitCommand {
                            // Esc closes the list first, then empties the field.
                            if menuOpen { menuDismissed = true } else { clearAndCollapse() }
                        }
                        // While an input method composes (Japanese, Chinese,
                        // Korean), its candidates own these keys.
                        .onKeyPress(.downArrow) { SearchFieldKeys.isComposing ? .ignored : moveHighlight(1) }
                        .onKeyPress(.upArrow) { SearchFieldKeys.isComposing ? .ignored : moveHighlight(-1) }
                        .onKeyPress(.return) {
                            guard menuOpen, !SearchFieldKeys.isComposing, let id = highlighted else { return .ignored }
                            choose(id)
                            return .handled
                        }
                        // Key-down only: a held ⌫ that empties the text must not
                        // go on to select and remove the tokens.
                        .onKeyPress(SearchFieldKeys.deleteKey, phases: .down) { _ in
                            SearchFieldKeys.isComposing ? .ignored : backspace()
                        }
                    // Always laid out, shown only with text: adding it on the
                    // first character widened the whole item by its width.
                    Button(action: clear) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.secondary)
                            .font(.system(size: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(i18n.t("desktop.toolbar.searchClear"))
                    .opacity(isEmpty ? 0 : 1)
                    .disabled(isEmpty)
                    .accessibilityHidden(isEmpty)
                }
                .padding(.horizontal, 4)
                .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { fieldWidth = $0 }
                .background(SuggestionsAnchor(
                    isOpen: menuOpen,
                    content: AnyView(SearchSuggestionsList(
                        rows: rows, styles: bridgeHandler.searchBadgeStyles, highlightID: highlighted,
                        width: max(320, fieldWidth),
                        onChoose: { choose($0) }, onHover: { hover($0) }
                    )),
                    onDismiss: { menuDismissed = true }
                ))
                // `.task` (not `.onAppear`) — toolbar-hosted views fire `.onAppear`
                // unreliably on macOS 26 (desktop/CLAUDE.md). Seed only when empty
                // so a re-expand mid-typing can't clobber an in-flight keystroke.
                .task {
                    if text.isEmpty { seed(bridgeHandler.quotesSearchQuery) }
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

    /// The chips, in a strip that grows to a cap and then scrolls, keeping the
    /// newest token in view.
    private var tokenStrip: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 4) {
                    ForEach(tokens) { chip in
                        SearchTokenChipView(
                            chip: chip, styles: bridgeHandler.searchBadgeStyles,
                            selected: chip.subject == selectedToken,
                            onOpen: { menuDismissed = true },
                            onMode: { bridgeHandler.setSearchTokenMode(chip.subject, mode: $0) },
                            onRemove: { removeToken(chip.subject) }
                        )
                        .id(chip.subject)
                    }
                }
                .fixedSize()
                .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { chipsWidth = $0 }
            }
            .frame(width: min(chipsWidth, 280))
            .onChange(of: tokens.map(\.subject)) { _, subjects in
                if let last = subjects.last { proxy.scrollTo(last, anchor: .trailing) }
            }
        }
    }

    /// Nothing typed and no tokens: the clear button has nothing to clear.
    private var isEmpty: Bool { text.isEmpty && tokens.isEmpty }

    /// Write `text` from the code (the store's echo, a lens switch, a clear):
    /// not typing, so it neither re-sends the text nor opens the list.
    private func seed(_ value: String) {
        if value != text {
            seeded = value
            text = value
        }
        menuDismissed = true
    }

    private func moveHighlight(_ step: Int) -> KeyPress.Result {
        guard onQuotes, !rows.isEmpty else { return .ignored }
        if menuOpen {
            highlightID = SearchFieldKeys.move(highlighted, by: step, rows: rowIDs)
            announceHighlight()
        } else if !text.isEmpty {
            menuDismissed = false  // ↓ on a closed list opens it
        }
        return .handled
    }

    /// The list is a window that never becomes key, so VoiceOver's focus stays
    /// on the field and would hear nothing as ↓ moves through it. Say the row.
    private func announceHighlight() {
        guard let id = highlighted, let row = rows.first(where: { $0.id == id }) else { return }
        announce(SuggestionLabel.spoken(row))
    }

    private func announce(_ text: String) {
        NSAccessibility.post(
            element: NSApp as Any, notification: .announcementRequested,
            userInfo: [.announcement: text,
                       .priority: NSAccessibilityPriorityLevel.high.rawValue]
        )
    }

    /// A token's name, as its chip shows it.
    private func tokenName(_ subject: SearchSubject) -> String {
        tokens.first(where: { $0.subject == subject })?.label ?? ""
    }

    /// Remove a token and say so: a chip that vanishes is otherwise silent.
    private func removeToken(_ subject: SearchSubject) {
        let name = tokenName(subject)
        bridgeHandler.removeSearchToken(subject)
        announce(i18n.t("common.search.announce.removed", ["label": name]))
    }

    /// A hover takes the highlight only once the pointer has moved since the
    /// list opened, so a list that opens under a resting pointer keeps the
    /// free text as ↩'s default.
    private func hover(_ id: String) {
        if let start = openMouse {
            if NSEvent.mouseLocation == start { return }
            openMouse = nil
        }
        highlightID = id
    }

    /// Send what was typed now, without the debounce wait.
    private func commitNow() {
        debounce?.cancel()
        if onQuotes, text != bridgeHandler.quotesSearchQuery { bridgeHandler.setQuotesSearch(text) }
    }

    /// Choose a row by id. The free text commits what was typed now and closes
    /// the list (the SPA leaves the query as it is, so no new rows would arrive
    /// to close it). A person or tag becomes a token, and the SPA clears what
    /// was typed to find it; the pending push of that text is cancelled, or it
    /// could land after the token and put the text back.
    private func choose(_ id: String) {
        guard let row = rows.first(where: { $0.id == id }) else { return }
        if row.kind == .text {
            commitNow()
            menuDismissed = true
        } else {
            debounce?.cancel()
            bridgeHandler.applySearchSuggestion(id: row.id)
            highlightID = nil
            menuDismissed = true
        }
    }

    private func backspace() -> KeyPress.Result {
        switch SearchFieldKeys.backspace(text: text, tokens: tokens, selected: selectedToken) {
        case .passThrough:
            return .ignored
        case .select(let subject):
            selectedToken = subject
            // Selected is the warning: the next press removes it.
            announce(i18n.t("common.search.announce.selected", ["label": tokenName(subject)]))
            return .handled
        case .remove(let subject):
            selectedToken = nil
            removeToken(subject)
            return .handled
        }
    }

    private func clear() {
        // Said only when there was something to empty: an empty search has no
        // match count to announce, so otherwise nothing is heard at all.
        if !text.isEmpty || !tokens.isEmpty {
            announce(i18n.t("common.search.announce.cleared"))
        }
        seed("")
        selectedToken = nil
        debounce?.cancel()
        // The text and every token, as the SPA's clear and Esc do.
        if bridgeHandler.activeTab == .quotes { bridgeHandler.clearQuotesSearch() }
    }

    private func clearAndCollapse() {
        clear()
        expanded = false
    }

    private func collapseIfEmpty() {
        if isEmpty { expanded = false }
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
