#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only Picker Lab — the moderator-identity picker (docs/design-people.md,
/// "UX iteration 3") built twice and shown side by side, so web against native
/// is judged on the real rendering rather than on a mockup of either.
///
/// - **Native half:** a hybrid the owner set (3 Oct 2026). The popover is a Mac
///   pull-down menu in everything but its container — the system menu font in
///   label colour, a 24 pt row (measured from `NSMenu` on macOS 27), the menu's
///   own checkmark, the source-list selection capsule — while the person is
///   the house native badge, `SpeakerBadgeView`, the same entity the Sessions
///   switcher draws. Regular and Small follow the two pull-down sizes.
/// - **Web half:** `/report/picker-specimen` on the fronted project's sidecar —
///   the shipped classes and the real `PersonBadge`, under the real tokens and
///   `data-platform="desktop"`. Unchanged by the hybrid: the report's own look.
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
                Picker("Native size", selection: $model.small) {
                    Text("Regular").tag(false)
                    Text("Small").tag(true)
                }
                .pickerStyle(.segmented)
                .fixedSize()
                Spacer()
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
            PopoverAnchor(model: model)
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
                description: Text("Open a project in the main window first — the web half is the real SPA on that project's sidecar.")
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
    /// The small pull-down size: 11 pt type and a small segmented control.
    @Published var small = false
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

    var body: some View {
        Button { model.isOpen.toggle() } label: {
            if let a = model.answer {
                PersonLabel(code: a.code, name: a.name, proposed: !a.confirmed)
                    .fixedSize()
            } else {
                Text(model.role.label).italic().foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .background(PopoverHost(isOpen: model.isOpen, onClose: { model.isOpen = false }) {
            NativePersonPicker(model: model)
        })
    }
}

/// The grid's person, as the anchor: the house badge, then the name — grey
/// while proposed, as the grid draws it.
private struct PersonLabel: NSViewRepresentable {
    let code: String
    let name: String
    let proposed: Bool

    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        view.subviews.forEach { $0.removeFromSuperview() }
        let label = NSTextField(labelWithString: name)
        label.font = PickerMetrics(small: false).nameFont
        label.textColor = proposed ? .secondaryLabelColor : .labelColor
        let row = PickerRowView(tick: nil, lead: PickerBadge(code: code, proposed: proposed),
                                name: label, column: SpeakerBadgeView.width(for: code),
                                metrics: PickerMetrics(small: false))
        row.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            row.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            row.topAnchor.constraint(equalTo: view.topAnchor),
            row.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
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

// MARK: - Pull-down menu metrics

/// What a Mac pull-down menu uses at each size, measured on macOS 27 (`NSMenu`
/// with `menuFont`): rows are 24 pt at both sizes, and only the type and the
/// controls shrink — 13 → 11 pt, and the segmented control 24 → 20 pt tall.
struct PickerMetrics {
    let small: Bool
    var nameFont: NSFont {
        NSFont.menuFont(ofSize: small ? NSFont.systemFontSize(for: .small) : 0)
    }
    var rowHeight: CGFloat { 24 }
    var controlSize: ControlSize { small ? .small : .regular }
    /// The menu's check column, and the gap between the badge and the name.
    var tickColumn: CGFloat { small ? 19 : 22 }
    var gap: CGFloat { small ? 5 : 6 }
}

// MARK: - The picker

/// The list is the Sessions switcher's table (`SessionsPopoverList.swift`),
/// because that surface already settled how a list in a popover behaves on
/// this Mac (docs/design-sessions-popover-navigation.md §Interaction): single
/// click commits and dismisses, arrows move the highlight, Return or Space
/// commits, Escape dismisses, hover is the popover family's 6% wash, and the
/// selection is the grey source-list capsule.
private struct NativePersonPicker: View {
    @ObservedObject var model: PickerLabModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("Role", selection: Binding(get: { model.role }, set: { model.setRole($0) })) {
                ForEach(PickerRole.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .controlSize(PickerMetrics(small: model.small).controlSize)
            .frame(maxWidth: .infinity)

            // Someone new is the list's next row: the code they would get, and
            // the name column as the field.
            PickerPeopleList(model: model)
        }
        .padding(10)
        .frame(width: model.small ? 250 : 280)
    }
}

private struct PickerPeopleList: NSViewRepresentable {
    @ObservedObject var model: PickerLabModel

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
        context.coordinator.update()
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.update()
    }

    @MainActor
    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate, NSTextFieldDelegate {
        let model: PickerLabModel
        weak var table: NSTableView?
        private weak var newField: NSTextField?
        private var rows: [String] = []
        private var signature = ""
        private var focusListRequest = 0

        init(model: PickerLabModel) { self.model = model }

        private var metrics: PickerMetrics { PickerMetrics(small: model.small) }

        /// One badge column for the whole list, as wide as its widest code —
        /// the Sessions switcher's "pin the column, not the chip" — so names
        /// line up and the new row's code never gives way to what is typed.
        private var badgeColumn: CGFloat {
            ((model.people[model.role] ?? []).map(\.code) + [model.nextCode])
                .map(SpeakerBadgeView.width(for:)).max() ?? SpeakerBadgeView.width(for: "p1")
        }

        func update() {
            // Reload only when what the rows draw has changed — a reload on every
            // publish would drop the hover wash under the pointer, and a reload
            // while typing would throw the field away.
            let sig = "\(model.role)|\(model.rows)|\(String(describing: model.answer))|\(model.people)|\(model.small)"
            if sig != signature {
                signature = sig
                rows = model.rows
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

        func tableView(_ tableView: NSTableView, heightOfRow row: Int) -> CGFloat { metrics.rowHeight }

        func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
            let id = rows[row]
            let m = metrics
            let lead: NSView
            let name: NSTextField
            var ticked = false
            var label = ""
            switch id {
            case PickerLabModel.newRow:
                lead = PickerBadge(code: model.nextCode, proposed: false)
                let field = PickerRowView.nameField(text: model.draft, prompt: model.role.newPrompt)
                field.delegate = self
                newField = field
                name = field
                label = "\(model.nextCode), \(model.role.newPrompt)"
            case PickerLabModel.meRow:
                let icon = NSImageView(image: NSImage(systemSymbolName: "person.crop.circle.badge.checkmark",
                                                      accessibilityDescription: nil) ?? NSImage())
                icon.contentTintColor = .controlAccentColor
                icon.symbolConfiguration = .init(pointSize: m.nameFont.pointSize, weight: .regular)
                lead = icon
                name = NSTextField(labelWithString: "That’s Me (\(PickerLabModel.me))")
                ticked = model.answer?.name == PickerLabModel.me
                label = "That’s Me, \(PickerLabModel.me)"
            default:
                let person = model.people[model.role]?.first(where: { $0.code == id })
                ticked = model.answer?.code == id && model.answer?.name == person?.name
                lead = PickerBadge(code: id, proposed: ticked && !(model.answer?.confirmed ?? true))
                name = NSTextField(labelWithString: person?.name ?? "")
                label = "\(id) \(person?.name ?? "")"
            }
            name.font = m.nameFont
            name.textColor = .labelColor
            name.lineBreakMode = .byTruncatingTail
            let rowView = PickerRowView(tick: ticked, lead: lead, name: name, column: badgeColumn, metrics: m)
            rowView.translatesAutoresizingMaskIntoConstraints = false
            let cell = NSTableCellView()
            cell.addSubview(rowView)
            NSLayoutConstraint.activate([
                rowView.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 8),
                rowView.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -10),
                rowView.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ])
            if ticked { label += (model.answer?.confirmed ?? true) ? ", current answer" : ", current answer, proposed" }
            cell.setAccessibilityElement(true)
            cell.setAccessibilityLabel(label)
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
            DispatchQueue.main.async { [weak self] in
                guard let field = self?.newField else { return }
                field.window?.makeFirstResponder(field)
            }
        }

        // MARK: The new-person field

        func controlTextDidChange(_ notification: Notification) {
            if let field = notification.object as? NSTextField { model.draft = field.stringValue }
        }

        /// Return creates, Escape closes, and the arrows leave the field — the
        /// field editor's own commands, which arrive before it acts on them.
        func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
            switch selector {
            case #selector(NSResponder.insertNewline(_:)): model.create(); return true
            case #selector(NSResponder.cancelOperation(_:)): model.isOpen = false; return true
            case #selector(NSResponder.moveUp(_:)): model.leaveField(by: -1); return true
            case #selector(NSResponder.moveDown(_:)): model.leaveField(by: 1); return true
            default: return false
            }
        }

        // MARK: Type-select and commit

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

// MARK: - The row

/// One picker row in the hybrid: the menu's check column, then the person —
/// the house badge in a column pinned to the widest code — then the name in
/// the menu font, on its baseline. The new-person row puts a field in the name
/// column; That's Me puts its symbol in the badge column.
final class PickerRowView: NSView {
    let tick: NSImageView?
    let lead: NSView
    let name: NSTextField

    /// `tick: nil` leaves out the check column (the anchor in the grid).
    init(tick: Bool?, lead: NSView, name: NSTextField, column: CGFloat, metrics: PickerMetrics) {
        self.lead = lead
        self.name = name
        if let tick {
            // AppKit's own menu checkmark, in label colour, as a Mac menu draws it.
            let image = NSImageView(image: NSImage(named: NSImage.menuOnStateTemplateName) ?? NSImage())
            image.contentTintColor = .labelColor
            image.isHidden = !tick
            self.tick = image
        } else {
            self.tick = nil
        }
        super.init(frame: .zero)
        let checkWidth = tick == nil ? 0 : metrics.tickColumn
        for v in [self.tick, lead, name].compactMap({ $0 }) {
            v.translatesAutoresizingMaskIntoConstraints = false
            addSubview(v)
        }
        var c: [NSLayoutConstraint] = [
            lead.leadingAnchor.constraint(equalTo: leadingAnchor, constant: checkWidth),
            name.leadingAnchor.constraint(equalTo: leadingAnchor, constant: checkWidth + column + metrics.gap),
            name.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor),
            name.topAnchor.constraint(greaterThanOrEqualTo: topAnchor),
            name.bottomAnchor.constraint(lessThanOrEqualTo: bottomAnchor),
            lead.topAnchor.constraint(greaterThanOrEqualTo: topAnchor),
            lead.bottomAnchor.constraint(lessThanOrEqualTo: bottomAnchor),
            lead.centerYAnchor.constraint(equalTo: centerYAnchor),
            // The badge's code and the name share a baseline, as in the switcher;
            // a symbol has no text baseline, so That's Me centres instead.
            lead is PickerBadge
                ? name.firstBaselineAnchor.constraint(equalTo: lead.firstBaselineAnchor)
                : name.centerYAnchor.constraint(equalTo: lead.centerYAnchor),
        ]
        if let t = self.tick {
            c += [t.leadingAnchor.constraint(equalTo: leadingAnchor),
                  t.centerYAnchor.constraint(equalTo: name.centerYAnchor)]
        }
        // The field stretches across the name column so it is easy to click.
        if name.isEditable {
            c.append(name.trailingAnchor.constraint(equalTo: trailingAnchor))
        }
        NSLayoutConstraint.activate(c)
        name.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        lead.setContentCompressionResistancePriority(.required, for: .horizontal)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// The new-person row's field: no bezel, no fill, no focus ring — text in
    /// the name column, where a name would be.
    static func nameField(text: String, prompt: String) -> NSTextField {
        let field = NSTextField(string: text)
        field.isBordered = false
        field.isBezeled = false
        field.drawsBackground = false
        field.focusRingType = .none
        field.usesSingleLineMode = true
        field.cell?.isScrollable = true
        field.placeholderString = prompt
        field.setAccessibilityLabel(prompt)
        return field
    }
}

/// The house speaker badge, plus the one dotted ring a proposed name wears
/// (design-people.md, iteration 3). `SpeakerBadgeView` is final, so the ring is
/// a layer over it rather than a subclass.
final class PickerBadge: NSView {
    private let badge: SpeakerBadgeView
    private let ring = CAShapeLayer()

    init(code: String, proposed: Bool) {
        badge = SpeakerBadgeView(code: code)
        super.init(frame: .zero)
        wantsLayer = true
        badge.translatesAutoresizingMaskIntoConstraints = false
        addSubview(badge)
        NSLayoutConstraint.activate([
            badge.leadingAnchor.constraint(equalTo: leadingAnchor),
            badge.trailingAnchor.constraint(equalTo: trailingAnchor),
            badge.topAnchor.constraint(equalTo: topAnchor),
            badge.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])
        ring.fillColor = nil
        ring.lineWidth = 1
        ring.lineDashPattern = [3, 2]
        ring.isHidden = !proposed
        layer?.addSublayer(ring)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override var intrinsicContentSize: NSSize { badge.intrinsicContentSize }
    override var firstBaselineOffsetFromTop: CGFloat { badge.firstBaselineOffsetFromTop }

    override func layout() {
        super.layout()
        ring.frame = bounds
        ring.path = CGPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5),
                           cornerWidth: 3, cornerHeight: 3, transform: nil)
        // A CGColor is a snapshot; layout re-runs on an appearance change.
        effectiveAppearance.performAsCurrentDrawingAppearance {
            ring.strokeColor = NSColor.labelColor.cgColor
        }
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        needsLayout = true
    }
}
#endif
