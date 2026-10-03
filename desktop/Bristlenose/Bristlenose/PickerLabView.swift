#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only Picker Lab — the moderator-identity picker (docs/design-people.md,
/// "UX iteration 3") built twice and shown side by side, so web against native
/// is judged on the real rendering rather than on a mockup of either.
///
/// - **Native half:** stock AppKit in a real `NSPopover` — a segmented control,
///   a `List` with system selection, SF Symbols, a rounded text field. Nothing
///   is approximated; the material, arrow, radius and type are the system's.
/// - **Web half:** `/report/picker-specimen` on the fronted project's sidecar —
///   the shipped classes and the real `PersonBadge`, under the real tokens and
///   `data-platform="desktop"`.
///
/// The badges are the one shared element, and the native half holds no colour
/// for them: the web half measures the real `PersonBadge` and posts the result
/// over the production `search-badge-styles` message (docs/design-search.md
/// §7a), and `BadgeStyleChip` paints exactly those values. If the two halves'
/// badges ever differ, that is a finding about the bridge, not the lab.
///
/// The scenario control drives both halves; inside each, the controls are live.
/// The web half takes its scenario from the URL (`?scenario=`), so a reload or
/// a project switch cannot leave the halves showing different things; Reset
/// starts both again from the chosen scenario.
struct PickerLabView: View {
    @EnvironmentObject private var serveFleet: ServeFleet
    @EnvironmentObject private var i18n: I18n
    @StateObject private var bridge = BridgeHandler()
    @StateObject private var model = PickerLabModel()
    @State private var scenario = "proposed"
    /// Bumped by Reset: a new URL reloads the web half from the scenario.
    @State private var resetCount = 0

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Picker("Scenario", selection: $scenario) {
                    Text("Opened on a proposed name").tag("proposed")
                    Text("Reopened after confirming").tag("confirmed")
                    Text("Opened on an unknown slot").tag("unknown")
                    Text("Participant slot").tag("participant")
                }
                .fixedSize()
                Button("Reset") {
                    resetCount += 1
                    model.apply(scenario: scenario)
                }
                Spacer()
                Text(bridge.searchBadgeStyles.people.isEmpty
                     ? "Waiting for badge styles from the web half…"
                     : "Native badges: \(bridge.searchBadgeStyles.people.count) styles measured by the web half")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(10)
            Divider()
            HStack(spacing: 0) {
                nativeHalf
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                Divider()
                webHalf
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onChange(of: scenario) { _, name in model.apply(scenario: name) }
    }

    private func specimenURL(_ base: URL) -> URL {
        var c = URLComponents(url: base.appendingPathComponent("picker-specimen"),
                              resolvingAgainstBaseURL: false)
        c?.queryItems = [URLQueryItem(name: "scenario", value: scenario),
                         URLQueryItem(name: "reset", value: String(resetCount))]
        return c?.url ?? base
    }

    // MARK: Native half

    private var nativeHalf: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("AppKit · NSPopover").font(.caption).foregroundStyle(.secondary)
                .padding(.bottom, 16)
            PopoverAnchor(model: model, bridge: bridge)
                .fixedSize()
            Spacer()
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Web half

    @ViewBuilder
    private var webHalf: some View {
        if let base = serveFleet.fronted?.serveURL,
           let project = serveFleet.frontedProject,
           let port = URLComponents(url: base, resolvingAgainstBaseURL: false)?.port {
            WebView(
                url: specimenURL(base),
                bridgeHandler: bridge,
                session: ServeSession(projectID: project, port: port),
                authToken: serveFleet.fronted?.authToken
            )
            .environmentObject(i18n)
            // A new sidecar is a new view: the auth token is injected only when
            // the view is made (desktop/CLAUDE.md, "keyed on project.id + port").
            .id(ServeSession(projectID: project, port: port).viewID)
        } else {
            ContentUnavailableView(
                "No serve running",
                systemImage: "bolt.horizontal.circle",
                description: Text("Open a project in the main window first — the web half is the real SPA on that project's sidecar, and it is also what measures the badges the native half draws.")
            )
        }
    }
}

// MARK: - Model

enum PickerRole: String, CaseIterable, Identifiable {
    case moderator, participant, observer
    var id: String { rawValue }
    var label: String { rawValue.capitalized }
    var prefix: String { String(rawValue.prefix(1)) }
    var newPrompt: String { "New \(rawValue)" }
}

struct PickerPerson: Hashable { let code: String; let name: String }

/// The slot's answer: who it is, and whether a person has said yes.
struct PickerAnswer: Equatable { let code: String; let name: String; let confirmed: Bool }

@MainActor
final class PickerLabModel: ObservableObject {
    static let me = "Martin Storey"
    static let meRow = "me"
    /// The row for someone new, after the people it would join.
    static let newRow = "new"

    @Published var role: PickerRole = .moderator
    @Published var people: [PickerRole: [PickerPerson]] = [
        .moderator: [.init(code: "m1", name: "Martin B Storey"), .init(code: "m2", name: "Kerri Ng")],
        .participant: [.init(code: "p1", name: "Sarah Chen"), .init(code: "p2", name: "Dr Amara Nwosu"),
                       .init(code: "p3", name: "Mary Adeyemi"), .init(code: "p4", name: "Marrian Boateng"),
                       .init(code: "p5", name: "Mary Okafor"), .init(code: "p6", name: "Mickael Hurley")],
        .observer: [.init(code: "o1", name: "Jane Smith")],
    ]
    @Published var answer: PickerAnswer? = .init(code: "m1", name: "Martin B Storey", confirmed: false)
    @Published var selection: String? = "m1"
    @Published var draft = ""
    @Published var isOpen = true
    /// Bumped when an arrow key leaves the new-person field, so the list takes
    /// the keyboard back.
    @Published var focusListRequest = 0

    var rows: [String] {
        (people[role] ?? []).map(\.code) + [Self.newRow] + (role == .participant ? [] : [Self.meRow])
    }

    /// The code someone new would get: the next number in this role.
    var nextCode: String { "\(role.prefix)\((people[role]?.count ?? 0) + 1)" }

    /// An arrow key in the new-person field moves to the row above or below.
    func leaveField(by delta: Int) {
        guard let i = rows.firstIndex(of: Self.newRow), rows.indices.contains(i + delta) else { return }
        selection = rows[i + delta]
        focusListRequest += 1
    }

    func apply(scenario: String) {
        switch scenario {
        case "confirmed":
            role = .moderator; answer = .init(code: "m1", name: "Martin B Storey", confirmed: true)
        case "unknown":
            role = .moderator; answer = nil
        case "participant":
            role = .participant; answer = .init(code: "p3", name: "Mary Adeyemi", confirmed: false)
        default:
            role = .moderator; answer = .init(code: "m1", name: "Martin B Storey", confirmed: false)
        }
        selection = answer?.code ?? people[role]?.first?.code
        draft = ""
        isOpen = true
    }

    func setRole(_ r: PickerRole) {
        role = r
        selection = rows.first
    }

    func choose(_ id: String) {
        guard id != Self.newRow else { return }   // the new row is typed into, not chosen
        if id == Self.meRow {
            // That's Me answers this slot, so it keeps the slot's role prefix.
            let code = (answer?.code.hasPrefix(role.prefix) ?? false) ? answer!.code : nextCode
            answer = .init(code: code, name: Self.me, confirmed: true)
        } else if let p = people[role]?.first(where: { $0.code == id }) {
            answer = .init(code: p.code, name: p.name, confirmed: true)
        }
        isOpen = false
    }

    func create() {
        let name = draft.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        let code = nextCode
        people[role, default: []].append(.init(code: code, name: name))
        answer = .init(code: code, name: name, confirmed: true)
        draft = ""
        isOpen = false
    }
}

// MARK: - The anchor and its real NSPopover

/// The badge in the grid that opens the picker. The popover is AppKit's own,
/// `.applicationDefined` so it stays up while you look at the web half.
private struct PopoverAnchor: View {
    @ObservedObject var model: PickerLabModel
    @ObservedObject var bridge: BridgeHandler

    var body: some View {
        Button { model.isOpen.toggle() } label: {
            if let a = model.answer {
                BadgeStyleChip(code: a.code, name: a.name, proposed: !a.confirmed,
                               styles: bridge.searchBadgeStyles)
            } else {
                Text(model.role.label).italic().foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .background(PopoverHost(isOpen: model.isOpen, onClose: { model.isOpen = false }) {
            NativePersonPicker(model: model, bridge: bridge)
        })
    }
}

private struct PopoverHost<Content: View>: NSViewRepresentable {
    let isOpen: Bool
    let onClose: () -> Void
    @ViewBuilder let content: () -> Content

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        let popover = context.coordinator.popover
        if popover.contentViewController == nil {
            let host = NSHostingController(rootView: content())
            host.sizingOptions = .preferredContentSize
            popover.contentViewController = host
            popover.behavior = .applicationDefined
            popover.delegate = context.coordinator
        }
        context.coordinator.onClose = onClose
        DispatchQueue.main.async {
            if isOpen, !popover.isShown, view.window != nil {
                // Below the badge, as menus and pop-ups open. The host view is
                // unflipped, so its bottom edge is minY.
                popover.show(relativeTo: view.bounds, of: view, preferredEdge: .minY)
            } else if !isOpen, popover.isShown {
                popover.close()
            }
        }
    }

    static func dismantleNSView(_ view: NSView, coordinator: Coordinator) {
        coordinator.popover.close()
    }

    /// `.applicationDefined` so the popover stays up while you look at the web
    /// half; Escape closes it through the list, and every close reaches the
    /// model here, so the next click on the badge opens it again.
    final class Coordinator: NSObject, NSPopoverDelegate {
        let popover = NSPopover()
        var onClose: (() -> Void)?
        func popoverDidClose(_ notification: Notification) { onClose?() }
    }
}

// MARK: - The picker, in stock controls

/// The list is the Sessions switcher's table (`SessionsPopoverList.swift`),
/// because that surface already settled how a list in a popover behaves on
/// this Mac (docs/design-sessions-popover-navigation.md §Interaction): single
/// click commits and dismisses, arrows move the highlight, Return or Space
/// commits, Escape dismisses, hover is the popover family's 6% wash, and the
/// selection is the grey source-list capsule. A SwiftUI `List` gives none of
/// that — click only selects, and a tap gesture on its rows breaks selection.
private struct NativePersonPicker: View {
    @ObservedObject var model: PickerLabModel
    @ObservedObject var bridge: BridgeHandler

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("Role", selection: Binding(get: { model.role }, set: { model.setRole($0) })) {
                ForEach(PickerRole.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(maxWidth: .infinity)

            // Someone new is the list's next row: the code they would get, and a
            // name half to type into — so it reads as making another badge.
            PickerPeopleList(model: model, styles: bridge.searchBadgeStyles)
        }
        .padding(10)
        .frame(width: 280)
    }
}

private struct PickerPeopleList: NSViewRepresentable {
    @ObservedObject var model: PickerLabModel
    let styles: SearchBadgeStyles

    /// Every row is one badge high. Measured from the badge style the web half
    /// sent, so a taller chip makes a taller row instead of being clipped.
    static func rowHeight(_ styles: SearchBadgeStyles) -> CGFloat {
        guard let s = styles.people.values.first else { return 24 }
        let face = s.name ?? s.code
        let font = NSFont.systemFont(ofSize: CGFloat(face.size))
        let line = face.lineHeight.map { CGFloat($0) } ?? ceil(font.ascender - font.descender + font.leading)
        let chip = line + CGFloat(face.padY + face.padBottom) + CGFloat(2 * (s.code.border?.width ?? 0))
        return max(24, ceil(chip) + 6)
    }

    /// The list is exactly as tall as its rows, read from the table itself,
    /// so a source-list inset can never clip the last one.
    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSScrollView, context: Context) -> CGSize? {
        guard let table = context.coordinator.table, table.numberOfRows > 0 else { return nil }
        let height = table.rect(ofRow: table.numberOfRows - 1).maxY + 2
        return CGSize(width: proposal.width ?? 260, height: height)
    }

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeNSView(context: Context) -> NSScrollView {
        let table = SessionsPopoverTableView()
        configureSourceListTable(table)
        table.dataSource = context.coordinator
        table.delegate = context.coordinator
        table.target = context.coordinator
        table.action = #selector(Coordinator.rowClicked(_:))
        table.commitHandler = { [weak coordinator = context.coordinator] in coordinator?.commitSelected() }
        table.cancelHandler = { [weak model] in model?.isOpen = false }

        let scroll = NSScrollView()
        scroll.documentView = table
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = false
        scroll.automaticallyAdjustsContentInsets = false
        scroll.contentInsets = NSEdgeInsetsZero
        context.coordinator.table = table
        context.coordinator.update(model: model, styles: styles)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.update(model: model, styles: styles)
    }

    @MainActor
    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate {
        let model: PickerLabModel
        weak var table: NSTableView?
        private var rows: [String] = []
        private var styles = SearchBadgeStyles.empty
        private var signature = ""
        private var focusListRequest = 0

        init(model: PickerLabModel) { self.model = model }

        func update(model: PickerLabModel, styles: SearchBadgeStyles) {
            // Reload only when what the rows draw has changed — a reload on every
            // publish would drop the hover wash under the pointer.
            let sig = "\(model.role)|\(model.rows)|\(String(describing: model.answer))|\(model.people)|\(styles.people.count)"
            if sig != signature {
                signature = sig
                rows = model.rows
                self.styles = styles
                table?.reloadData()
            }
            if model.focusListRequest != focusListRequest {
                focusListRequest = model.focusListRequest
                table?.window?.makeFirstResponder(table)
            }
            if let table, let id = model.selection, let i = rows.firstIndex(of: id), table.selectedRow != i {
                table.selectRowIndexes(IndexSet(integer: i), byExtendingSelection: false)
                table.scrollRowToVisible(i)
            }
        }

        func numberOfRows(in tableView: NSTableView) -> Int { rows.count }

        func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? {
            SessionsPopoverHoverRowView()
        }

        func tableView(_ tableView: NSTableView, heightOfRow row: Int) -> CGFloat {
            PickerPeopleList.rowHeight(styles)
        }

        func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
            let id = rows[row]
            let content = PickerRowContent(id: id, model: model, styles: styles)
            let cell = NSTableCellView()
            let host = NSHostingView(rootView: content)
            host.translatesAutoresizingMaskIntoConstraints = false
            cell.addSubview(host)
            NSLayoutConstraint.activate([
                host.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 12),
                host.trailingAnchor.constraint(lessThanOrEqualTo: cell.trailingAnchor, constant: -12),
                host.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ])
            cell.setAccessibilityElement(true)
            cell.setAccessibilityLabel(content.accessibilityText)
            return cell
        }

        func tableViewSelectionDidChange(_ notification: Notification) {
            // Highlight only — choosing happens on click, Return or Space.
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count else { return }
            let id = rows[table.selectedRow]
            if model.selection != id { model.selection = id }
            // Arriving on the new row puts the cursor in its name.
            if id == PickerLabModel.newRow { focusNewField() }
        }

        func focusNewField() {
            guard let table, let i = rows.firstIndex(of: PickerLabModel.newRow) else { return }
            DispatchQueue.main.async {
                guard let cell = table.view(atColumn: 0, row: i, makeIfNecessary: true),
                      let field = Self.editableField(in: cell) else { return }
                table.window?.makeFirstResponder(field)
            }
        }

        private static func editableField(in view: NSView) -> NSTextField? {
            if let field = view as? NSTextField, field.isEditable { return field }
            for sub in view.subviews { if let f = editableField(in: sub) { return f } }
            return nil
        }

        func tableView(_ tableView: NSTableView, typeSelectStringFor tableColumn: NSTableColumn?, row: Int) -> String? {
            typeSelectString(rows[row])
        }

        /// Matches the start of any word, so "m2", "kerri" and "ng" all land —
        /// AppKit's default only matches the start of the whole string.
        func tableView(_ tableView: NSTableView, nextTypeSelectMatchFromRow startRow: Int,
                       toRow endRow: Int, for searchString: String) -> Int {
            guard !rows.isEmpty, (0..<rows.count).contains(startRow),
                  (0..<rows.count).contains(endRow) else { return -1 }
            let search = searchString.lowercased()
            var row = startRow
            repeat {   // [startRow, endRow) with wrap; equal bounds = one full sweep
                let words = typeSelectString(rows[row]).lowercased().split(separator: " ")
                if words.contains(where: { $0.hasPrefix(search) }) { return row }
                row = (row + 1) % rows.count
            } while row != endRow
            return -1
        }

        private func typeSelectString(_ id: String) -> String {
            if id == PickerLabModel.meRow { return "That’s Me \(PickerLabModel.me)" }
            if id == PickerLabModel.newRow { return "" }
            let name = model.people[model.role]?.first(where: { $0.code == id })?.name ?? ""
            return "\(id) \(name)"
        }

        @objc func rowClicked(_ sender: Any?) {
            guard let table, table.clickedRow >= 0, table.clickedRow < rows.count else { return }
            let id = rows[table.clickedRow]
            if id == PickerLabModel.newRow { focusNewField() } else { model.choose(id) }
        }

        func commitSelected() {
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count else { return }
            let id = rows[table.selectedRow]
            if id == PickerLabModel.newRow { focusNewField() } else { model.choose(id) }
        }
    }
}

/// One row: the check gutter, then the person's badge (or That's Me).
private struct PickerRowContent: View {
    let id: String
    @ObservedObject var model: PickerLabModel
    let styles: SearchBadgeStyles

    private var person: PickerPerson? { model.people[model.role]?.first(where: { $0.code == id }) }
    private var isMe: Bool { id == PickerLabModel.meRow }
    private var isAnswer: Bool {
        guard let a = model.answer else { return false }
        return isMe ? a.name == PickerLabModel.me : (a.code == id && a.name == person?.name)
    }
    private var isProposed: Bool { isAnswer && !(model.answer?.confirmed ?? true) }

    var accessibilityText: String {
        if id == PickerLabModel.newRow { return "\(model.nextCode), \(model.role.newPrompt)" }
        let what = isMe ? "That’s Me, \(PickerLabModel.me)" : "\(id) \(person?.name ?? "")"
        return what + (isAnswer ? (isProposed ? ", current answer, proposed" : ", current answer") : "")
    }

    var body: some View {
        HStack(spacing: 4) {
            // AppKit's own menu checkmark, in label colour, as a Mac menu draws it.
            Image(nsImage: NSImage(named: NSImage.menuOnStateTemplateName) ?? NSImage())
                .renderingMode(.template)
                .foregroundStyle(.primary)
                .opacity(isAnswer ? 1 : 0)
                .frame(width: 16)
            if id == PickerLabModel.newRow {
                BadgeStyleChip(code: model.nextCode, name: "", proposed: false, styles: styles,
                               field: .init(text: $model.draft, prompt: model.role.newPrompt,
                                            onSubmit: { model.create() },
                                            onExit: { model.isOpen = false },
                                            onUp: { model.leaveField(by: -1) },
                                            onDown: { model.leaveField(by: 1) }))
            } else if isMe {
                Label("That’s Me (\(PickerLabModel.me))", systemImage: "person.crop.circle.badge.checkmark")
            } else if let person {
                BadgeStyleChip(code: person.code, name: person.name, proposed: isProposed, styles: styles)
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: - A badge painted from measured styles

/// Paints a person badge from the values the SPA measured off the real
/// `PersonBadge` (SearchPersonBadgeStyle). No colour, size or radius here is
/// ours. Before the first measurement arrives it says so rather than guess.
struct BadgeStyleChip: View {
    let code: String
    let name: String
    let proposed: Bool
    let styles: SearchBadgeStyles
    /// When set, the name half is a field: someone new, as the badge they will be.
    var field: Field? = nil

    struct Field {
        let text: Binding<String>
        let prompt: String
        let onSubmit: () -> Void
        let onExit: () -> Void
        let onUp: () -> Void
        let onDown: () -> Void
    }

    var body: some View {
        if let style = styles.people[code] ?? sameRoleStyle {
            chip(style)
        } else if let field {
            HStack(spacing: 6) {
                Text(code).foregroundStyle(.tertiary)
                TextField(field.prompt, text: field.text, prompt: Text(field.prompt))
                    .textFieldStyle(.plain)
                    .onSubmit(field.onSubmit)
            }
        } else {
            Text("\(code) \(name)").foregroundStyle(.tertiary)
        }
    }

    /// A person created in the native half was never measured by the web
    /// half; any badge of the same role has the same style.
    private var sameRoleStyle: SearchPersonBadgeStyle? {
        styles.people.first(where: { $0.key.first == code.first })?.value
    }

    private func chip(_ s: SearchPersonBadgeStyle) -> some View {
        let radius = s.code.radius
        let outline = s.code.border.map { colour($0.colour) } ?? .clear
        let ring = colour((s.name ?? s.code).text)
        let bw = s.code.border?.width ?? 0
        return HStack(spacing: 0) {
            // The outline is drawn inside the shape, so the outer edges carry the
            // border width on top of their padding, as CSS's border box does.
            half(code, s.code, leading: bw, trailing: s.name == nil && field == nil ? bw : 0)
            if let field { editableHalf(field, s.name ?? s.code, trailing: bw) }
            else if let n = s.name { half(name, n, leading: 0, trailing: bw) }
        }
        .clipShape(RoundedRectangle(cornerRadius: radius))
        .overlay {
            if proposed {
                // One dotted ring while proposed (design-people.md, iteration 3).
                RoundedRectangle(cornerRadius: radius)
                    .strokeBorder(ring, style: StrokeStyle(lineWidth: 1, dash: [3, 2]))
            } else {
                RoundedRectangle(cornerRadius: radius)
                    .strokeBorder(outline, lineWidth: s.code.border?.width ?? 0)
            }
        }
    }

    private func half(_ text: String, _ s: SearchBadgeStyle, leading: Double, trailing: Double) -> some View {
        let bw = s.border?.width ?? 0
        return Text(text)
            .font(Font(font(s)))
            .foregroundStyle(colour(s.text))
            // CSS centres the glyphs in the line box; a fixed frame does the same.
            .frame(height: s.lineHeight.map { CGFloat($0) })
            .padding(.leading, s.padX + leading)
            .padding(.trailing, s.padRight + trailing)
            .padding(.top, s.padY + bw)
            .padding(.bottom, s.padBottom + bw)
            .background(s.fill.map { colour($0) } ?? .clear)
    }

    /// The name half as a field. A hidden copy of the text sets the width, so
    /// the badge grows as you type, the way the web half's does.
    private func editableHalf(_ f: Field, _ s: SearchBadgeStyle, trailing: Double) -> some View {
        let bw = s.border?.width ?? 0
        let face = Font(font(s))
        let shown = f.text.wrappedValue.isEmpty ? f.prompt : f.text.wrappedValue
        return Text(shown + " ")
            .font(face)
            .hidden()
            .overlay(alignment: .leading) {
                TextField(f.prompt, text: f.text, prompt: Text(f.prompt))
                    .textFieldStyle(.plain)
                    .font(face)
                    .foregroundStyle(colour(s.text))
                    .onSubmit(f.onSubmit)
                    .onExitCommand(perform: f.onExit)
                    .onKeyPress(.upArrow) { f.onUp(); return .handled }
                    .onKeyPress(.downArrow) { f.onDown(); return .handled }
            }
            .frame(height: s.lineHeight.map { CGFloat($0) })
            .padding(.leading, s.padX)
            .padding(.trailing, s.padRight + trailing)
            .padding(.top, s.padY + bw)
            .padding(.bottom, s.padBottom + bw)
            .background(s.fill.map { colour($0) } ?? .clear)
    }

    private func font(_ s: SearchBadgeStyle) -> NSFont {
        let w = NSFont.Weight(rawValue: CGFloat(Self.appKitWeight(css: s.weight)))
        return s.family == .mono
            ? NSFont.monospacedSystemFont(ofSize: CGFloat(s.size), weight: w)
            : NSFont.systemFont(ofSize: CGFloat(s.size), weight: w)
    }

    /// CSS weight (100…900) to AppKit's scale, interpolated over Apple's own
    /// named weights rather than a straight line: 490 lands just under medium.
    static func appKitWeight(css: Double) -> Double {
        let table: [(Double, Double)] = [
            (100, NSFont.Weight.ultraLight.rawValue), (200, NSFont.Weight.thin.rawValue),
            (300, NSFont.Weight.light.rawValue), (400, NSFont.Weight.regular.rawValue),
            (500, NSFont.Weight.medium.rawValue), (600, NSFont.Weight.semibold.rawValue),
            (700, NSFont.Weight.bold.rawValue), (800, NSFont.Weight.heavy.rawValue),
            (900, NSFont.Weight.black.rawValue),
        ].map { ($0.0, Double($0.1)) }
        let w = min(max(css, 100), 900)
        guard let hi = table.firstIndex(where: { $0.0 >= w }), hi > 0 else { return table[0].1 }
        let (x0, y0) = table[hi - 1], (x1, y1) = table[hi]
        return y0 + (y1 - y0) * (w - x0) / (x1 - x0)
    }

    private func colour(_ c: BadgeColour) -> Color {
        Color(.displayP3, red: c.red, green: c.green, blue: c.blue, opacity: c.opacity)
    }
}
#endif
