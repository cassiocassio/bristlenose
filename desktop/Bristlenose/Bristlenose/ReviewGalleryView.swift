#if DEBUG
import AppKit
import SwiftUI

/// DEBUG-only Review Gallery — every changed surface in the state that shows
/// the change, without making test data. Diagnostics ▸ Review Gallery.
/// Design: `docs/mockups/review-gallery.html` §1–§2 (Phase 1, the Mac window).
///
/// Shaped like Sidebar Lab: a source list of `ReviewGalleryRegistry.entries`
/// on the left, the selected entry on the right — its commits and files, a
/// Mark Reviewed button, a state picker, and a canvas holding the real view.
///
/// **What the toolbar changes, and what it doesn't.** Appearance applies to
/// this window only, through `.preferredColorScheme` — the Keycap Gallery
/// exception in `desktop/CLAUDE.md` §Appearance; the app's own appearance seam
/// is untouched. Language drives a gallery-owned `I18n`, never the app's, so
/// switching it here re-renders the specimens and leaves the app's language
/// alone. Chrome strings are English literals (the Diagnostics exception);
/// only the specimens render through locale keys.
///
/// **Which doors are real.** The boot pane's Retry and Send Feedback… and the
/// re-analyse sheet's buttons write to the footer readout instead, so
/// reviewing them never starts a sidecar, opens a form or runs anything. Two
/// doors are real on purpose: the diagnostic popover's Set Up Provider… and
/// the "In the app" entries' Open It both open the app's own Settings window,
/// which is harmless and is the point of those doors. In the sidebar rows the
/// glyph popovers open (the real ones), and the two running rows offer no Stop
/// — the fixture's runner does not own them (`ReviewGallerySidebarFixture`).
struct ReviewGalleryView: View {

    @EnvironmentObject private var appI18n: I18n
    @StateObject private var galleryI18n = ReviewGalleryView.makeI18n()
    @StateObject private var reviewed = ReviewGalleryReviewed()

    @State private var selection: String? = ReviewGalleryRegistry.entries.first?.id
    @State private var filter = ""
    @State private var stateIndex = 0
    @State private var appearance: GalleryAppearance = .auto
    @State private var language = "en"
    @State private var changedSince = ""          // "" = everything
    @State private var readout = "Specimen buttons write here."
    @State private var built: (key: String, specimen: ReviewGallerySpecimen)?

    enum GalleryAppearance: String, CaseIterable, Identifiable {
        case auto = "Auto", light = "Light", dark = "Dark"
        var id: String { rawValue }
        var scheme: ColorScheme? {
            switch self {
            case .auto: nil
            case .light: .light
            case .dark: .dark
            }
        }
    }

    static func makeI18n() -> I18n {
        let i18n = I18n()
        if let dir = I18n.findLocalesDirectory() {
            i18n.configure(localesDirectory: dir)
        }
        i18n.setLocale("en")
        return i18n
    }

    // MARK: - Derived

    private var visibleEntries: [ReviewGalleryEntry] {
        ReviewGalleryRegistry.entries.filter { entry in
            (changedSince.isEmpty || entry.landed >= changedSince)
                && (filter.isEmpty
                    || entry.title.localizedCaseInsensitiveContains(filter)
                    || entry.id.localizedCaseInsensitiveContains(filter)
                    || entry.commits.contains { $0.hasPrefix(filter.lowercased()) })
        }
    }

    private var selectedEntry: ReviewGalleryEntry? {
        ReviewGalleryRegistry.entries.first { $0.id == selection }
    }

    private var landedDates: [String] {
        Array(Set(ReviewGalleryRegistry.entries.map(\.landed))).sorted(by: >)
    }

    /// Everything a specimen is built from. A change rebuilds it, so a state's
    /// fixtures (a fleet, a temp project list) are made once per showing, not
    /// on every redraw.
    private var buildKey: String {
        "\(selection ?? "")#\(stateIndex)#\(language)#\(appearance.rawValue)"
    }

    // MARK: - Body

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(min: 240, ideal: 300, max: 420)
        } detail: {
            detail
                .navigationTitle("Review Gallery")
                .navigationSubtitle(subtitle)
        }
        .toolbar { galleryToolbar }
        .preferredColorScheme(appearance.scheme)
        .onAppear {
            language = I18n.supportedLocales.contains(appI18n.locale) ? appI18n.locale : "en"
        }
        .onChange(of: buildKey, initial: true) { _, _ in rebuild() }
    }

    private var subtitle: String {
        let all = ReviewGalleryRegistry.entries
        let done = all.filter { reviewed.isReviewed($0) }.count
        return "\(done) of \(all.count) reviewed"
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        List(selection: Binding(get: { selection }, set: { select($0) })) {
            ForEach(ReviewGalleryEntry.Section.allCases) { section in
                let rows = visibleEntries.filter { $0.section == section }
                if !rows.isEmpty {
                    Section(section.title) {
                        ForEach(rows) { entry in
                            row(entry).tag(entry.id as String?)
                        }
                    }
                }
            }
        }
        .safeAreaInset(edge: .top) {
            TextField("Filter", text: $filter)
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
        }
    }

    private func row(_ entry: ReviewGalleryEntry) -> some View {
        HStack(spacing: 6) {
            Image(systemName: reviewed.isReviewed(entry) ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(reviewed.isReviewed(entry) ? Color.green : Color.secondary)
                .help(reviewed.isReviewed(entry) ? "Reviewed at these commits" : "Not reviewed")
            Text(entry.title)
                .lineLimit(1)
                .truncationMode(.tail)
            Spacer(minLength: 4)
            if entry.section == .inTheApp {
                Image(systemName: "arrow.up.forward")
                    .foregroundStyle(.secondary)
                    .font(.caption)
            } else {
                Text("\(entry.states.count)")
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
        }
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if let entry = selectedEntry {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        header(entry)
                        if entry.states.count > 1 {
                            Picker("State", selection: $stateIndex) {
                                ForEach(Array(entry.states.enumerated()), id: \.offset) { i, state in
                                    Text(state.name).tag(i)
                                }
                            }
                            .pickerStyle(.segmented)
                            .labelsHidden()
                        }
                        if let built, built.key == buildKey {
                            ReviewGalleryCanvas(specimen: built.specimen, log: log)
                                .environmentObject(galleryI18n)
                                .id(built.key)
                        }
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                Divider()
                footer
            }
        } else {
            ContentUnavailableView("No entry selected", systemImage: "square.grid.2x2")
        }
    }

    private func header(_ entry: ReviewGalleryEntry) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(entry.title).font(.title2.weight(.semibold))
                Spacer()
                let isReviewed = reviewed.isReviewed(entry)
                Button(isReviewed ? "Mark Unreviewed" : "Mark Reviewed") {
                    reviewed.setReviewed(!isReviewed, id: entry.id, commits: entry.commits)
                }
                .keyboardShortcut(.return, modifiers: .command)
            }
            Text(entry.what)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
            HStack(spacing: 6) {
                ForEach(entry.commits, id: \.self) { chip($0, symbol: "number") }
                ForEach(entry.files, id: \.self) { chip($0, symbol: "doc") }
                Text("landed \(entry.landed)")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
    }

    private func chip(_ text: String, symbol: String) -> some View {
        Label(text, systemImage: symbol)
            .font(.system(.caption, design: .monospaced))
            .textSelection(.enabled)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Capsule().fill(Color.secondary.opacity(0.12)))
    }

    private var footer: some View {
        HStack {
            Text(readout)
                .font(.system(.caption, design: .monospaced))
                .lineLimit(1)
                .truncationMode(.tail)
                .textSelection(.enabled)
            Spacer()
            Text("⌥⌘↓ next · ⌥⌘↑ previous · ⌘↩ mark reviewed")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var galleryToolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .navigation) {
            Button { step(-1) } label: { Label("Previous Entry", systemImage: "chevron.up") }
                .keyboardShortcut(.upArrow, modifiers: [.command, .option])
                .help("Previous entry (⌥⌘↑)")
            Button { step(1) } label: { Label("Next Entry", systemImage: "chevron.down") }
                .keyboardShortcut(.downArrow, modifiers: [.command, .option])
                .help("Next entry (⌥⌘↓)")
        }
        ToolbarItemGroup(placement: .primaryAction) {
            Picker("Appearance", selection: $appearance) {
                ForEach(GalleryAppearance.allCases) { Text($0.rawValue).tag($0) }
            }
            .help("Appearance of this window only")
            Picker("Language", selection: $language) {
                ForEach(I18n.supportedLocales.sorted(), id: \.self) { Text($0).tag($0) }
            }
            .help("Language of the specimens (a gallery-owned I18n; the app's language is untouched)")
            Picker("Changed since", selection: $changedSince) {
                Text("Everything").tag("")
                ForEach(landedDates, id: \.self) { Text("Since \($0)").tag($0) }
            }
            .help("Entries whose latest commit landed on or after this day")
        }
    }

    // MARK: - Actions

    private func step(_ delta: Int) {
        let order = ReviewGalleryEntry.Section.allCases.flatMap { section in
            visibleEntries.filter { $0.section == section }
        }
        guard !order.isEmpty else { return }
        let current = order.firstIndex { $0.id == selection } ?? (delta > 0 ? -1 : order.count)
        let next = min(max(current + delta, 0), order.count - 1)
        select(order[next].id)
    }

    /// A new entry starts at its first state, in the same write: resetting
    /// `stateIndex` afterwards (an `onChange` of `selection`) built the new
    /// entry's specimen twice, once at the old index.
    private func select(_ id: String?) {
        guard id != selection else { return }
        selection = id
        stateIndex = 0
    }

    private func log(_ message: String) {
        let time = Date().formatted(date: .omitted, time: .standard)
        readout = "\(time)  \(message)"
    }

    private func rebuild() {
        guard let entry = selectedEntry, !entry.states.isEmpty else {
            built = nil
            return
        }
        let state = entry.states[min(stateIndex, entry.states.count - 1)]
        galleryI18n.setLocale(state.locale ?? language)
        let context = ReviewGalleryContext(i18n: galleryI18n, appearance: appearance.scheme,
                                           log: { log($0) })
        built = (key: buildKey, specimen: state.make(context))
    }
}

// MARK: - Canvas

/// Draws one specimen: a card per view, each under its monospaced label, side
/// by side for `.views`; the recipe and door for `.navigation`. Separate from
/// the window so `ReviewGalleryRegistryTests` hosts exactly what the window
/// shows.
struct ReviewGalleryCanvas: View {
    let specimen: ReviewGallerySpecimen
    let log: (String) -> Void

    var body: some View {
        switch specimen {
        case .view(let view, let label):
            card(label: label, view)
        case .views(let views):
            ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: 16) {
                    ForEach(Array(views.enumerated()), id: \.offset) { _, item in
                        card(label: item.label, item.1)
                    }
                }
                .padding(.bottom, 8)
            }
        case .navigation(let recipe, let open):
            GroupBox {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Seen in the real app, not faked here.")
                        .font(.headline)
                    Text(recipe)
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                    if let open {
                        Button("Open It") {
                            open()
                            log("Opened in the app")
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(6)
            }
        }
    }

    private func card(label: String, _ view: AnyView) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
            view
                .background(Color(nsColor: .windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(Color.secondary.opacity(0.3)))
                .fixedSize()
        }
    }
}
#endif
