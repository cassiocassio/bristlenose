import AppKit
import SwiftUI
import WebKit

// The person picker, native (docs/design-people.md § UX iteration 3, v1.1).
//
// In the Mac app a click on a speaker in the Sessions grid does not open the
// web picker: the SPA sends `person-picker` with everything this popover draws
// — the slot, the rows, where the badge is, every string already localised —
// and this side answers with the name that was picked (`personPickerChoose`).
// What a pick *means* (a yes to a proposed name, a rename, nothing) is decided
// on the web side, so the two pickers cannot disagree. The shapes are pinned on
// both sides by tests/fixtures/person-picker-bridge-contract.json.
//
// The owner's hybrid (4 Oct 2026): inside the popover it is a Mac pull-down
// menu at the small size — 11 pt menu type, the small segmented control, 24 pt
// rows measured from NSMenu, the menu's own checkmark, the source-list
// capsule — while the person is the house native badge, `SpeakerBadgeView`.

// MARK: - The request

/// What the SPA asks for: one speaker slot and its rows.
struct PersonPickerRequest: Equatable {
    enum Role: String, CaseIterable { case moderator, participant, observer }

    struct Slot: Equatable {
        let code: String
        let role: Role
        let name: String
        let confirmed: Bool
    }

    struct Labels: Equatable {
        let roles: [Role: String]
        let roleGroup: String
        let newPrompt: String
        /// "That’s Me ({{name}})", or nil where the role has none (a participant).
        let thatsMe: String?
        let menu: String
    }

    let sessionId: String
    let slot: Slot
    let names: [String]
    /// The badge, in CSS pixels from the web view's top-left.
    let anchor: CGRect
    let labels: Labels

    init(sessionId: String, slot: Slot, names: [String], anchor: CGRect, labels: Labels) {
        self.sessionId = sessionId
        self.slot = slot
        self.names = names
        self.anchor = anchor
        self.labels = labels
    }

    /// The `person-picker` message body; nil when anything it needs is missing.
    init?(message body: [String: Any]) {
        guard let sessionId = body["sessionId"] as? String,
              let s = body["slot"] as? [String: Any],
              let code = s["code"] as? String, !code.isEmpty,
              let role = (s["role"] as? String).flatMap(Role.init(rawValue:)),
              let names = body["names"] as? [String],
              let a = body["anchor"] as? [String: Any],
              let l = body["labels"] as? [String: Any],
              let roleWords = l["roles"] as? [String: String],
              let newPrompt = l["newPrompt"] as? String,
              let menu = l["menu"] as? String
        else { return nil }
        func num(_ v: Any?) -> CGFloat? { (v as? NSNumber).map { CGFloat($0.doubleValue) } }
        guard let x = num(a["x"]), let y = num(a["y"]), let w = num(a["width"]), let h = num(a["height"])
        else { return nil }
        self.sessionId = sessionId
        self.slot = Slot(code: code, role: role, name: s["name"] as? String ?? "",
                         confirmed: s["confirmed"] as? Bool ?? true)
        self.names = names
        self.anchor = CGRect(x: x, y: y, width: w, height: h)
        var words: [Role: String] = [:]
        for (k, v) in roleWords { if let r = Role(rawValue: k) { words[r] = v } }
        self.labels = Labels(roles: words, roleGroup: l["roleGroup"] as? String ?? "",
                             newPrompt: newPrompt, thatsMe: l["thatsMe"] as? String, menu: menu)
    }
}

/// What this side sends back: the name that was picked, as
/// `(action, payload)` for `BridgeHandler.menuAction`. Pure, so the contract
/// test can compare it with the fixture without a web view.
enum PersonPickerAction {
    static func choose(sessionId: String, code: String, name: String) -> (String, [String: Any]) {
        ("personPickerChoose", ["sessionId": sessionId, "code": code,
                                "choice": ["kind": "name", "name": name]])
    }
}

// MARK: - Pull-down menu metrics

/// What a Mac pull-down menu uses at each size, measured on macOS 27 (`NSMenu`
/// with `menuFont`): rows are 24 pt at both sizes, and only the type and the
/// controls shrink — 13 → 11 pt, and the segmented control 24 → 20 pt tall.
/// The picker ships at the small size (owner, 4 Oct 2026).
struct PickerMetrics {
    let small: Bool
    var nameFont: NSFont {
        NSFont.menuFont(ofSize: small ? NSFont.systemFontSize(for: .small) : 0)
    }
    var rowHeight: CGFloat { 24 }
    var controlSize: NSControl.ControlSize { small ? .small : .regular }
    /// The menu's check column, and the gap between the badge and the name.
    var tickColumn: CGFloat { small ? 19 : 22 }
    var gap: CGFloat { small ? 5 : 6 }
}

// MARK: - The model

@MainActor
final class PersonPickerModel: ObservableObject {
    static let newRow = "\u{0}new"
    static let meRow = "\u{0}me"

    let request: PersonPickerRequest
    let metrics: PickerMetrics
    /// The account's full name, when the role has a That's Me row.
    let meName: String?
    @Published var draft = ""
    @Published var selection: String?
    /// Bumped when an arrow leaves the new-person field, so the list takes the
    /// keyboard back.
    @Published var focusListRequest = 0

    private let onChoose: (String) -> Void
    private let onClose: () -> Void

    init(request: PersonPickerRequest, small: Bool = true, meName: String? = NSFullUserName(),
         onChoose: @escaping (String) -> Void, onClose: @escaping () -> Void) {
        self.request = request
        self.metrics = PickerMetrics(small: small)
        let me = meName?.trimmingCharacters(in: .whitespaces) ?? ""
        self.meName = request.labels.thatsMe != nil && !me.isEmpty ? me : nil
        self.onChoose = onChoose
        self.onClose = onClose
        // The selection opens on the current answer; with no answer, nothing is
        // pre-selected, so a single Return cannot confirm a guess.
        let name = request.slot.name
        self.selection = !name.isEmpty && request.names.contains(name) ? name : nil
    }

    var rows: [String] {
        request.names + [Self.newRow] + (meName == nil ? [] : [Self.meRow])
    }

    var thatsMeLabel: String? {
        guard let meName, let template = request.labels.thatsMe else { return nil }
        return template.replacingOccurrences(of: "{{name}}", with: meName)
    }

    /// As wide as its widest row, the way a Mac menu sizes to its items —
    /// within a floor that fits the role segments and a ceiling past which a
    /// long name is truncated rather than stretching the popover.
    var contentWidth: CGFloat {
        let font = metrics.nameFont
        let texts = request.names + [request.labels.newPrompt] + (thatsMeLabel.map { [$0] } ?? [])
        let widest = texts.map { ($0 as NSString).size(withAttributes: [.font: font]).width }.max() ?? 0
        // Cell inset 8 + check column + badge column + gap + text + trailing 10,
        // inside the source-list capsule's 10 a side, inside the 10 pt padding.
        let row = 8 + metrics.tickColumn + SpeakerBadgeView.width(for: request.slot.code)
            + metrics.gap + ceil(widest) + 10 + 20 + 20
        return min(max(row, metrics.small ? 230 : 260), 380)
    }

    func isAnswer(_ row: String) -> Bool {
        let name = request.slot.name
        guard !name.isEmpty else { return false }
        return row == Self.meRow ? meName == name : row == name
    }

    /// A picked row or a typed name. The web side decides what it means.
    func choose(_ row: String) {
        guard row != Self.newRow else { return }
        let name = (row == Self.meRow ? meName ?? "" : row).trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        onChoose(name)
        onClose()
    }

    func submitDraft() { choose(draft) }

    func close() { onClose() }

    /// An arrow key in the new-person field moves to the row above or below.
    func leaveField(by delta: Int) {
        guard let i = rows.firstIndex(of: Self.newRow), rows.indices.contains(i + delta) else { return }
        selection = rows[i + delta]
        focusListRequest += 1
    }
}

// MARK: - The picker

/// The list is the Sessions switcher's table (`SessionsPopoverList.swift`),
/// because that surface already settled how a list in a popover behaves on
/// this Mac (docs/design-sessions-popover-navigation.md §Interaction): single
/// click commits and dismisses, arrows move the highlight, Return or Space
/// commits, Escape dismisses, hover is the popover family's 6% wash, and the
/// selection is the grey source-list capsule.
struct PersonPickerView: View {
    @ObservedObject var model: PersonPickerModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            PersonPickerRoles(request: model.request, controlSize: model.metrics.controlSize)
                .frame(maxWidth: .infinity)
            PersonPickerList(model: model)
        }
        .padding(10)
        .frame(width: model.contentWidth)
    }
}

/// Moderator | Participant | Observer, with only the speaker's own role
/// enabled: changing a role is the §J recode, not built (owner, 4 Oct 2026).
/// AppKit, because SwiftUI's segmented picker cannot disable one segment.
private struct PersonPickerRoles: NSViewRepresentable {
    let request: PersonPickerRequest
    let controlSize: NSControl.ControlSize

    func makeNSView(context: Context) -> NSSegmentedControl {
        let roles = PersonPickerRequest.Role.allCases
        let control = NSSegmentedControl(labels: roles.map { request.labels.roles[$0] ?? $0.rawValue },
                                         trackingMode: .selectOne, target: nil, action: nil)
        control.controlSize = controlSize
        control.font = NSFont.systemFont(ofSize: NSFont.systemFontSize(for: controlSize))
        control.segmentDistribution = .fillEqually
        for (i, role) in roles.enumerated() {
            control.setEnabled(role == request.slot.role, forSegment: i)
        }
        control.selectedSegment = roles.firstIndex(of: request.slot.role) ?? 0
        control.setAccessibilityLabel(request.labels.roleGroup)
        control.refusesFirstResponder = true
        return control
    }

    func updateNSView(_ control: NSSegmentedControl, context: Context) {}
}

private struct PersonPickerList: NSViewRepresentable {
    @ObservedObject var model: PersonPickerModel

    /// The list is exactly as tall as its rows, read from the table itself,
    /// so a source-list inset can never clip the last one.
    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSScrollView, context: Context) -> CGSize? {
        guard let table = context.coordinator.table, table.numberOfRows > 0 else { return nil }
        let height = table.rect(ofRow: table.numberOfRows - 1).maxY + 2
        return CGSize(width: proposal.width ?? 230, height: height)
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
        table.cancelHandler = { [weak model] in model?.close() }
        table.setAccessibilityLabel(model.request.labels.menu)

        let scroll = NSScrollView()
        scroll.documentView = table
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = false
        scroll.automaticallyAdjustsContentInsets = false
        scroll.contentInsets = NSEdgeInsetsZero
        context.coordinator.table = table
        table.reloadData()
        context.coordinator.syncSelection()
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.syncSelection()
    }

    @MainActor
    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate, NSTextFieldDelegate {
        let model: PersonPickerModel
        weak var table: NSTableView?
        private weak var newField: NSTextField?
        private var focusListRequest = 0

        init(model: PersonPickerModel) { self.model = model }

        private var rows: [String] { model.rows }

        func syncSelection() {
            if model.focusListRequest != focusListRequest {
                focusListRequest = model.focusListRequest
                table?.window?.makeFirstResponder(table)
            }
            guard let table else { return }
            if let id = model.selection, let i = rows.firstIndex(of: id) {
                if table.selectedRow != i {
                    table.selectRowIndexes(IndexSet(integer: i), byExtendingSelection: false)
                    table.scrollRowToVisible(i)
                }
            } else if table.selectedRow >= 0 {
                table.deselectAll(nil)
            }
        }

        func numberOfRows(in tableView: NSTableView) -> Int { rows.count }

        func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? {
            SessionsPopoverHoverRowView()
        }

        func tableView(_ tableView: NSTableView, heightOfRow row: Int) -> CGFloat {
            model.metrics.rowHeight
        }

        /// Every row carries this slot's code — project-wide person codes are
        /// route C Phase 1, not built — so the column is that one badge wide.
        private var badgeColumn: CGFloat { SpeakerBadgeView.width(for: model.request.slot.code) }

        func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
            let id = rows[row]
            let m = model.metrics
            let slot = model.request.slot
            let lead: NSView
            let name: NSTextField
            var label = ""
            switch id {
            case PersonPickerModel.newRow:
                lead = PickerBadge(code: slot.code, proposed: false)
                let field = PickerRowView.nameField(text: model.draft, prompt: model.request.labels.newPrompt)
                field.delegate = self
                newField = field
                name = field
                label = "\(slot.code), \(model.request.labels.newPrompt)"
            case PersonPickerModel.meRow:
                let icon = NSImageView(image: NSImage(systemSymbolName: "person.crop.circle.badge.checkmark",
                                                      accessibilityDescription: nil) ?? NSImage())
                icon.contentTintColor = .controlAccentColor
                icon.symbolConfiguration = .init(pointSize: m.nameFont.pointSize, weight: .regular)
                lead = icon
                name = NSTextField(labelWithString: model.thatsMeLabel ?? "")
                label = model.thatsMeLabel ?? ""
            default:
                let proposed = model.isAnswer(id) && !slot.confirmed
                lead = PickerBadge(code: slot.code, proposed: proposed)
                name = NSTextField(labelWithString: id)
                label = "\(slot.code) \(id)"
            }
            name.font = m.nameFont
            name.textColor = .labelColor
            name.lineBreakMode = .byTruncatingTail
            let ticked = model.isAnswer(id)
            let rowView = PickerRowView(tick: ticked, lead: lead, name: name, column: badgeColumn, metrics: m)
            rowView.translatesAutoresizingMaskIntoConstraints = false
            let cell = NSTableCellView()
            cell.addSubview(rowView)
            NSLayoutConstraint.activate([
                rowView.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 8),
                rowView.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -10),
                rowView.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ])
            cell.setAccessibilityElement(true)
            cell.setAccessibilityLabel(label)
            cell.setAccessibilitySelected(ticked)
            return cell
        }

        func tableViewSelectionDidChange(_ notification: Notification) {
            // Highlight only — choosing happens on click, Return or Space.
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count else { return }
            let id = rows[table.selectedRow]
            if model.selection != id { model.selection = id }
            // Arriving on the new row puts the cursor in its name.
            if id == PersonPickerModel.newRow { focusNewField() }
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

        /// Return names someone new, Escape closes, and the arrows leave the
        /// field — the field editor's own commands, which arrive before it acts.
        func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
            switch selector {
            case #selector(NSResponder.insertNewline(_:)): model.submitDraft(); return true
            case #selector(NSResponder.cancelOperation(_:)): model.close(); return true
            case #selector(NSResponder.moveUp(_:)): model.leaveField(by: -1); return true
            case #selector(NSResponder.moveDown(_:)): model.leaveField(by: 1); return true
            default: return false
            }
        }

        // MARK: Type-select and commit

        func tableView(_ tableView: NSTableView, typeSelectStringFor tableColumn: NSTableColumn?, row: Int) -> String? {
            typeSelectString(rows[row])
        }

        /// Matches the start of any word, so "kerri" and "ng" both land —
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
            switch id {
            case PersonPickerModel.newRow: return ""
            case PersonPickerModel.meRow: return model.thatsMeLabel ?? ""
            default: return id
            }
        }

        @objc func rowClicked(_ sender: Any?) {
            guard let table, table.clickedRow >= 0, table.clickedRow < rows.count else { return }
            let id = rows[table.clickedRow]
            if id == PersonPickerModel.newRow { focusNewField() } else { model.choose(id) }
        }

        func commitSelected() {
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count else { return }
            let id = rows[table.selectedRow]
            if id == PersonPickerModel.newRow { focusNewField() } else { model.choose(id) }
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

// MARK: - Presenting it over the report

/// Opens the picker as a transient `NSPopover` at the badge the researcher
/// clicked, and sends the picked name back to the SPA. One per window's
/// bridge; a new request closes the one before.
@MainActor
final class PersonPickerPresenter: NSObject, NSPopoverDelegate {
    private var popover: NSPopover?

    func present(_ request: PersonPickerRequest, over webView: WKWebView,
                 choose: @escaping (_ action: String, _ payload: [String: Any]) -> Void) {
        popover?.close()
        let popover = NSPopover()
        popover.behavior = .transient
        popover.delegate = self
        let model = PersonPickerModel(
            request: request,
            onChoose: { name in
                let (action, payload) = PersonPickerAction.choose(
                    sessionId: request.sessionId, code: request.slot.code, name: name)
                choose(action, payload)
            },
            onClose: { [weak popover] in popover?.close() }
        )
        let host = NSHostingController(rootView: PersonPickerView(model: model))
        host.sizingOptions = .preferredContentSize
        popover.contentViewController = host
        self.popover = popover
        let rect = Self.viewRect(for: request.anchor, in: webView)
        // Below the badge, as menus and pop-ups open.
        popover.show(relativeTo: rect, of: webView, preferredEdge: webView.isFlipped ? .maxY : .minY)
    }

    /// The badge's CSS-pixel rect in the web view's own coordinates: scaled by
    /// the page zoom, and turned over when the view is not flipped.
    static func viewRect(for anchor: CGRect, in webView: WKWebView) -> NSRect {
        let z = webView.pageZoom * webView.magnification
        let rect = NSRect(x: anchor.minX * z, y: anchor.minY * z,
                          width: max(anchor.width * z, 1), height: max(anchor.height * z, 1))
        guard !webView.isFlipped else { return rect }
        return NSRect(x: rect.minX, y: webView.bounds.height - rect.maxY,
                      width: rect.width, height: rect.height)
    }

    func popoverDidClose(_ notification: Notification) {
        if (notification.object as? NSPopover) === popover { popover = nil }
    }
}
