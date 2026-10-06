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
        /// The person a moderator or observer slot points at; nil on `m?` and
        /// on participants.
        var person: String? = nil
    }

    struct Labels: Equatable {
        let roles: [Role: String]
        let roleGroup: String
        let newPrompt: String
        /// "That’s Me ({{name}})", or nil where the role has none (a participant).
        let thatsMe: String?
        let menu: String
        /// "m1, proposed name Sarah" for a proposed slot's own row, or nil:
        /// the ring and the grey name say it only to the eye.
        var proposed: String? = nil
        /// "Not {{name}}": the ✕ on the current row.
        var notThisPerson: String? = nil
    }

    let sessionId: String
    let slot: Slot
    /// The rows' names. Unique within a role (the SPA refuses a second one,
    /// design-people.md §J8.11), so a name is enough to say which was picked.
    let names: [String]
    /// Each row's own code, parallel to `names` (§J8.8).
    let codes: [String]
    /// The code someone new would get.
    let newCode: String
    /// The badge, in CSS pixels from the web view's top-left.
    let anchor: CGRect
    let labels: Labels

    init(sessionId: String, slot: Slot, names: [String], codes: [String]? = nil,
         newCode: String? = nil, anchor: CGRect, labels: Labels) {
        self.sessionId = sessionId
        self.slot = slot
        self.names = names
        self.codes = codes?.count == names.count ? codes! : names.map { _ in slot.code }
        self.newCode = newCode ?? slot.code
        self.anchor = anchor
        self.labels = labels
    }

    /// The code a row's badge shows.
    func code(for name: String) -> String {
        names.firstIndex(of: name).map { codes[$0] } ?? slot.code
    }

    /// Every code the picker draws, for sizing the badge column.
    var allCodes: [String] { [slot.code, newCode] + codes }

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
                         confirmed: s["confirmed"] as? Bool ?? true,
                         person: (s["person"] as? String).flatMap { $0.isEmpty ? nil : $0 })
        self.names = names
        let codes = body["codes"] as? [String]
        self.codes = codes?.count == names.count ? codes! : names.map { _ in code }
        self.newCode = (body["newCode"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? code
        self.anchor = CGRect(x: x, y: y, width: w, height: h)
        var words: [Role: String] = [:]
        for (k, v) in roleWords { if let r = Role(rawValue: k) { words[r] = v } }
        self.labels = Labels(roles: words, roleGroup: l["roleGroup"] as? String ?? "",
                             newPrompt: newPrompt, thatsMe: l["thatsMe"] as? String, menu: menu,
                             proposed: l["proposed"] as? String,
                             notThisPerson: l["notThisPerson"] as? String)
    }
}

/// What was picked: a name, and which row it came from. The SPA decides what
/// it means (a pick, someone new, That's Me) — never this side.
struct PersonPickerPick: Equatable {
    enum Kind: String { case name, new, me, clear }
    let name: String
    let kind: Kind
}

/// What this side sends back, as `(action, payload)` for
/// `BridgeHandler.menuAction`. Pure, so the contract test can compare it with
/// the fixture without a web view.
enum PersonPickerAction {
    static func choose(sessionId: String, code: String, pick: PersonPickerPick) -> (String, [String: Any]) {
        // "Not this person" names nobody.
        let choice: [String: Any] = pick.kind == .clear
            ? ["kind": "clear"]
            : ["kind": pick.kind.rawValue, "name": pick.name]
        return ("personPickerChoose", ["sessionId": sessionId, "code": code, "choice": choice])
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

    private let onChoose: (PersonPickerPick) -> Void
    private let onClose: () -> Void

    init(request: PersonPickerRequest, small: Bool = true, meName: String? = NSFullUserName(),
         onChoose: @escaping (PersonPickerPick) -> Void, onClose: @escaping () -> Void) {
        self.request = request
        self.metrics = PickerMetrics(small: small)
        let me = meName?.trimmingCharacters(in: .whitespaces) ?? ""
        self.meName = request.labels.thatsMe != nil && !me.isEmpty ? me : nil
        self.onChoose = onChoose
        self.onClose = onClose
        // The selection opens on the current answer. With no answer there is
        // nothing to confirm, so the cursor starts in the new-person field
        // (design-people.md §J8.10), where an empty Return does nothing.
        let name = request.slot.name
        self.selection = !name.isEmpty && request.names.contains(name) ? name : Self.newRow
    }

    var rows: [String] {
        request.names + [Self.newRow] + (meName == nil ? [] : [Self.meRow])
    }

    var thatsMeLabel: String? {
        guard let meName, let template = request.labels.thatsMe else { return nil }
        return template.replacingOccurrences(of: "{{name}}", with: meName)
    }

    /// The role segments' own width, measured from the control as it is built:
    /// their labels are localised, and in French or Russian they need more
    /// than the floor below gives them.
    private(set) lazy var segmentsWidth: CGFloat =
        PersonPickerRoles.makeControl(request: request, controlSize: metrics.controlSize)
            .fittingSize.width

    /// As wide as its widest row, the way a Mac menu sizes to its items —
    /// within a floor and a ceiling past which a long name is truncated rather
    /// than stretching the popover — and never narrower than the role segments.
    var contentWidth: CGFloat {
        let font = metrics.nameFont
        let texts = request.names + [request.labels.newPrompt] + (thatsMeLabel.map { [$0] } ?? [])
        let widest = texts.map { ($0 as NSString).size(withAttributes: [.font: font]).width }.max() ?? 0
        // Cell inset 8 + check column + badge column + gap + text + trailing 10,
        // inside the source-list capsule's 10 a side, inside the 10 pt padding.
        let badge = request.allCodes.map { SpeakerBadgeView.width(for: $0) }.max() ?? 0
        let row = 8 + metrics.tickColumn + badge
            + metrics.gap + ceil(widest) + 10 + 20 + 20
        // The segments sit inside the 10 pt padding.
        return max(min(max(row, metrics.small ? 230 : 260), 380), ceil(segmentsWidth) + 20)
    }

    /// What VoiceOver hears for a name row: the SPA's proposed wording on the
    /// slot's own unconfirmed name, code and name on every other.
    func accessibilityLabel(for row: String) -> String {
        if isAnswer(row), !request.slot.confirmed, let proposed = request.labels.proposed {
            return proposed
        }
        return "\(request.code(for: row)) \(row)"
    }

    func isAnswer(_ row: String) -> Bool {
        let name = request.slot.name
        guard !name.isEmpty else { return false }
        return row == Self.meRow ? meName == name : row == name
    }

    /// A picked row. The web side decides what it means.
    func choose(_ row: String) {
        guard row != Self.newRow else { return }
        let me = row == Self.meRow
        send((me ? meName ?? "" : row), kind: me ? .me : .name)
    }

    /// The typed name: someone new, unless the web side finds the name taken.
    func submitDraft() { send(draft, kind: .new) }

    /// Whether the current answer can be refused with the ✕: a moderator or
    /// observer the slot points at (design-people.md §J8.8).
    var canClear: Bool {
        request.slot.role != .participant && request.slot.person != nil && !request.slot.name.isEmpty
    }

    /// "Not this person": the slot returns to unknown.
    func clearCurrent() {
        guard canClear else { return }
        onChoose(PersonPickerPick(name: "", kind: .clear))
        onClose()
    }

    private func send(_ raw: String, kind: PersonPickerPick.Kind) {
        let name = raw.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        onChoose(PersonPickerPick(name: name, kind: kind))
        onClose()
    }

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
        Self.makeControl(request: request, controlSize: controlSize)
    }

    /// Built here and nowhere else, so the width the picker reserves is
    /// measured from the control it draws.
    static func makeControl(request: PersonPickerRequest,
                            controlSize: NSControl.ControlSize) -> NSSegmentedControl {
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
        // Delete or Backspace on the current answer: not this person.
        table.deleteHandler = { [weak coordinator = context.coordinator] in coordinator?.clearIfCurrent() }
        // An unknown speaker opens in the new-person field, not the list.
        table.claimsFocusOnAppear = model.selection != PersonPickerModel.newRow
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

        /// Each row shows its person's own code (§J8.8), so the column is as
        /// wide as the widest badge and the names line up.
        private var badgeColumn: CGFloat {
            model.request.allCodes.map { SpeakerBadgeView.width(for: $0) }.max() ?? 0
        }

        func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
            let id = rows[row]
            let m = model.metrics
            let slot = model.request.slot
            let lead: NSView
            let name: NSTextField
            var label = ""
            switch id {
            case PersonPickerModel.newRow:
                let newCode = model.request.newCode
                lead = PickerBadge(code: newCode, proposed: false)
                let field = PickerRowView.nameField(text: model.draft, prompt: model.request.labels.newPrompt)
                field.delegate = self
                newField = field
                name = field
                label = "\(newCode), \(model.request.labels.newPrompt)"
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
                lead = PickerBadge(code: model.request.code(for: id), proposed: proposed)
                name = NSTextField(labelWithString: id)
                label = model.accessibilityLabel(for: id)
            }
            name.font = m.nameFont
            name.textColor = .labelColor
            name.lineBreakMode = .byTruncatingTail
            let ticked = model.isAnswer(id)
            let rowView = PickerRowView(tick: ticked, lead: lead, name: name, column: badgeColumn, metrics: m)
            rowView.translatesAutoresizingMaskIntoConstraints = false
            let cell = HoverRevealCell()
            cell.addSubview(rowView)
            var constraints = [
                rowView.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 8),
                rowView.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ]
            if ticked, id != PersonPickerModel.meRow, model.canClear {
                // "Not this person", shown while the pointer is on the row.
                let clear = NSButton(image: NSImage(systemSymbolName: "xmark", accessibilityDescription: nil)
                    ?? NSImage(), target: self, action: #selector(clearClicked(_:)))
                clear.isBordered = false
                clear.symbolConfiguration = .init(pointSize: m.nameFont.pointSize - 1, weight: .regular)
                clear.contentTintColor = .secondaryLabelColor
                let label = (model.request.labels.notThisPerson ?? "")
                    .replacingOccurrences(of: "{{name}}", with: id)
                clear.setAccessibilityLabel(label)
                clear.toolTip = label
                clear.translatesAutoresizingMaskIntoConstraints = false
                clear.isHidden = true
                cell.addSubview(clear)
                cell.revealed = clear
                constraints += [
                    clear.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -8),
                    clear.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
                    rowView.trailingAnchor.constraint(lessThanOrEqualTo: clear.leadingAnchor, constant: -4),
                ]
            } else {
                constraints.append(rowView.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -10))
            }
            NSLayoutConstraint.activate(constraints)
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

        @objc func clearClicked(_ sender: Any?) { model.clearCurrent() }

        @objc func rowClicked(_ sender: Any?) {
            guard let table, table.clickedRow >= 0, table.clickedRow < rows.count else { return }
            let id = rows[table.clickedRow]
            if id == PersonPickerModel.newRow { focusNewField() } else { model.choose(id) }
        }

        func clearIfCurrent() {
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count,
                  model.isAnswer(rows[table.selectedRow]) else { return }
            model.clearCurrent()
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
            // The SF Symbol checkmark at the menu font's size and weight, in label
            // colour, as a Mac menu draws its tick. It was the menu's on-state
            // template image, left at the image's own size, which drew larger
            // and thinner than a menu does (owner, 6 Oct 2026; design-people.md
            // §J8.8). Compare against a real NSMenu in Picker Lab.
            let config = NSImage.SymbolConfiguration(pointSize: metrics.nameFont.pointSize, weight: .regular)
            let check = NSImage(systemSymbolName: "checkmark", accessibilityDescription: nil)?
                .withSymbolConfiguration(config) ?? NSImage()
            let image = NSImageView(image: check)
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

// MARK: - A cell that shows one control only while the pointer is over it

/// The current row's ✕ appears on hover, as a Mac list's row actions do, so a
/// picker opened to confirm a name does not lead with a way to remove it.
final class HoverRevealCell: NSTableCellView {
    weak var revealed: NSView?

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        for area in trackingAreas where area.owner === self { removeTrackingArea(area) }
        addTrackingArea(NSTrackingArea(rect: .zero,
                                       options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                                       owner: self))
    }

    override func mouseEntered(with event: NSEvent) { revealed?.isHidden = false }
    override func mouseExited(with event: NSEvent) { revealed?.isHidden = true }
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
            onChoose: { pick in
                let (action, payload) = PersonPickerAction.choose(
                    sessionId: request.sessionId, code: request.slot.code, pick: pick)
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

    /// The badge's CSS-pixel rect in the web view's own coordinates.
    static func viewRect(for anchor: CGRect, in webView: WKWebView) -> NSRect {
        viewRect(for: anchor, zoom: webView.pageZoom * webView.magnification,
                 viewportTop: webView.safeAreaInsets.top,
                 boundsHeight: webView.bounds.height, flipped: webView.isFlipped)
    }

    /// The web view runs up under the toolbar, but its layout viewport starts
    /// below it, at its top safe-area inset (measured, docs/design-lens-template.md
    /// § Native geometry) — and `getBoundingClientRect` counts from the viewport.
    /// So the rect moves down by that inset, is scaled by the page zoom, and is
    /// turned over when the view is not flipped. Without the inset the popover
    /// pointed a toolbar's height above the badge.
    static func viewRect(for anchor: CGRect, zoom z: CGFloat, viewportTop: CGFloat,
                         boundsHeight: CGFloat, flipped: Bool) -> NSRect {
        let rect = NSRect(x: anchor.minX * z, y: viewportTop + anchor.minY * z,
                          width: max(anchor.width * z, 1), height: max(anchor.height * z, 1))
        guard !flipped else { return rect }
        return NSRect(x: rect.minX, y: boundsHeight - rect.maxY,
                      width: rect.width, height: rect.height)
    }

    /// Closes an open picker. A pick names a session and a code but no
    /// project, and codes repeat across projects, so a picker must not outlive
    /// the document it was opened over.
    func close() { popover?.close() }

    func popoverDidClose(_ notification: Notification) {
        if (notification.object as? NSPopover) === popover { popover = nil }
    }
}
