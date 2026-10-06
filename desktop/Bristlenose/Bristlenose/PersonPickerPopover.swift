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
        /// "New observer" and the like: the new row's prompt under each role a
        /// recode browses (§J7 R1).
        var newPromptFor: [Role: String] = [:]
        /// "Swap with {{code}}": the swap row (§J7 call 4).
        var swapWith: String? = nil
    }

    /// Another role's rows, browsed to recode the speaker (§J7 R1): the
    /// speaker's own person first, under the code they would carry there.
    struct RoleRows: Equatable {
        let names: [String]
        let codes: [String]
        let newCode: String
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
    /// The other roles the speaker can be recoded to; empty from an SPA older
    /// than the recode.
    let others: [Role: RoleRows]
    /// The code of the speaker this one would swap with (§J7 call 4), when the
    /// session has exactly one participant and one moderator.
    let swap: String?

    init(sessionId: String, slot: Slot, names: [String], codes: [String]? = nil,
         newCode: String? = nil, anchor: CGRect, labels: Labels, others: [Role: RoleRows] = [:],
         swap: String? = nil) {
        self.swap = swap
        self.sessionId = sessionId
        self.slot = slot
        self.names = names
        self.codes = codes?.count == names.count ? codes! : names.map { _ in slot.code }
        self.newCode = newCode ?? slot.code
        self.anchor = anchor
        self.labels = labels
        self.others = others.filter { $0.key != slot.role }
    }

    /// The roles the segments let the researcher move between.
    var openRoles: Set<Role> { Set(others.keys).union([slot.role]) }

    /// A role's rows: the speaker's own, or another's to recode into.
    func rows(for role: Role) -> RoleRows {
        if role != slot.role, let other = others[role] { return other }
        return RoleRows(names: names, codes: codes, newCode: newCode)
    }

    /// The code a row's badge shows.
    func code(for name: String, in role: Role? = nil) -> String {
        let rows = rows(for: role ?? slot.role)
        return rows.names.firstIndex(of: name).map { rows.codes[$0] } ?? slot.code
    }

    /// The new row's prompt under a role.
    func newPrompt(for role: Role) -> String {
        role == slot.role ? labels.newPrompt : labels.newPromptFor[role] ?? labels.newPrompt
    }

    /// Every code the picker draws, under any role, for sizing the badge
    /// column — so browsing a role never moves the names.
    var allCodes: [String] {
        [slot.code, newCode] + codes + others.values.flatMap { [$0.newCode] + $0.codes }
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
                         confirmed: s["confirmed"] as? Bool ?? true,
                         person: (s["person"] as? String).flatMap { $0.isEmpty ? nil : $0 })
        self.names = names
        let codes = body["codes"] as? [String]
        self.codes = codes?.count == names.count ? codes! : names.map { _ in code }
        self.newCode = (body["newCode"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? code
        self.anchor = CGRect(x: x, y: y, width: w, height: h)
        var words: [Role: String] = [:]
        for (k, v) in roleWords { if let r = Role(rawValue: k) { words[r] = v } }
        var prompts: [Role: String] = [:]
        for (k, v) in l["newPromptFor"] as? [String: String] ?? [:] {
            if let r = Role(rawValue: k) { prompts[r] = v }
        }
        self.labels = Labels(roles: words, roleGroup: l["roleGroup"] as? String ?? "",
                             newPrompt: newPrompt, thatsMe: l["thatsMe"] as? String, menu: menu,
                             proposed: l["proposed"] as? String,
                             notThisPerson: l["notThisPerson"] as? String,
                             newPromptFor: prompts,
                             swapWith: l["swapWith"] as? String)
        self.swap = (body["swap"] as? String).flatMap { $0.isEmpty ? nil : $0 }
        // A role whose rows are malformed is left out: its segment stays off.
        var others: [Role: RoleRows] = [:]
        for (k, v) in body["roles"] as? [String: Any] ?? [:] {
            guard let r = Role(rawValue: k), r != role, let o = v as? [String: Any],
                  let names = o["names"] as? [String], let codes = o["codes"] as? [String],
                  codes.count == names.count,
                  let newCode = o["newCode"] as? String, !newCode.isEmpty else { continue }
            others[r] = RoleRows(names: names, codes: codes, newCode: newCode)
        }
        self.others = others
    }
}

/// What was picked: a name, and which row it came from. The SPA decides what
/// it means (a pick, someone new, That's Me) — never this side. `role` is set
/// when the pick was made under another role: a recode (§J7 R1).
struct PersonPickerPick: Equatable {
    enum Kind: String { case name, new, me, clear, rename, swap }
    let name: String
    let kind: Kind
    var role: PersonPickerRequest.Role? = nil
}

/// What this side sends back, as `(action, payload)` for
/// `BridgeHandler.menuAction`. Pure, so the contract test can compare it with
/// the fixture without a web view.
enum PersonPickerAction {
    static func choose(sessionId: String, code: String, pick: PersonPickerPick) -> (String, [String: Any]) {
        // "Not this person" and the swap name nobody.
        var choice: [String: Any] = pick.kind == .clear || pick.kind == .swap
            ? ["kind": pick.kind.rawValue]
            : ["kind": pick.kind.rawValue, "name": pick.name]
        if let role = pick.role { choice["role"] = role.rawValue }
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
    static let swapRow = "\u{0}swap"

    let request: PersonPickerRequest
    let metrics: PickerMetrics
    /// The account's full name, when the role has a That's Me row.
    let meName: String?
    @Published var draft = ""
    /// Rename in place (design-people.md §J8.8): the current, confirmed row's
    /// name as a field, and what has been typed into it.
    @Published var renaming = false
    @Published var renameDraft = ""
    @Published var selection: String?
    /// The role whose rows are shown: the speaker's own, or another the
    /// segments switched to, where a pick recodes them (§J7 R1).
    @Published private(set) var browsing: PersonPickerRequest.Role
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
        self.browsing = request.slot.role
        // The selection opens on the current answer. With no answer there is
        // nothing to confirm, so the cursor starts in the new-person field
        // (design-people.md §J8.10), where an empty Return does nothing.
        let name = request.slot.name
        self.selection = !name.isEmpty && request.names.contains(name) ? name : Self.newRow
        // The picker opens on the current name as a field, selected, so typing
        // replaces it (owner, 6 Oct 2026); Tab or an arrow moves to the list.
        if !name.isEmpty, request.names.contains(name) {
            self.renaming = true
            self.renameDraft = name
        }
    }

    /// The names under the role being browsed.
    var names: [String] { request.rows(for: browsing).names }

    /// Whether the rows shown are another role's: every pick is then a recode.
    var recoding: Bool { browsing != request.slot.role }

    var rows: [String] {
        // The swap is an act on the speaker as they are, so it is offered
        // under their own role only (§J7 call 4).
        names + (swapLabel != nil && !recoding ? [Self.swapRow] : [])
            + (offersNew ? [Self.newRow] : []) + (meName == nil ? [] : [Self.meRow])
    }

    /// Whether the new-person field is shown. A named participant's record
    /// belongs to that one speaker, so typing another name over theirs is the
    /// same act as renaming: no second field (owner, 6 Oct 2026). A moderator or
    /// observer keeps it — renaming Martin changes him everywhere.
    var offersNew: Bool {
        !(browsing == request.slot.role && request.slot.role == .participant
            && !request.slot.name.isEmpty)
    }

    /// "Swap with m1", or nil where the session offers no swap.
    var swapLabel: String? {
        guard let code = request.swap, let template = request.labels.swapWith else { return nil }
        return template.replacingOccurrences(of: "{{code}}", with: code)
    }

    func code(for row: String) -> String { request.code(for: row, in: browsing) }
    var newCode: String { request.rows(for: browsing).newCode }
    var newPrompt: String { request.newPrompt(for: browsing) }

    /// Show another role's rows, or the speaker's own again. The selection
    /// lands on the speaker's own person, who heads every role's list.
    func browse(_ role: PersonPickerRequest.Role) {
        guard role != browsing, request.openRoles.contains(role) else { return }
        renaming = false
        browsing = role
        let name = request.slot.name
        selection = !name.isEmpty && names.contains(name) ? name : Self.newRow
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
        // Every role's rows and prompt, so browsing a role never resizes it.
        let roles = request.openRoles
        let texts = roles.flatMap { request.rows(for: $0).names + [request.newPrompt(for: $0)] }
            + (thatsMeLabel.map { [$0] } ?? []) + (swapLabel.map { [$0] } ?? [])
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
        return "\(code(for: row)) \(row)"
    }

    /// The tick: the speaker's current answer, which exists only in the role
    /// they have — under another, nothing is yet.
    func isAnswer(_ row: String) -> Bool {
        let name = request.slot.name
        guard !name.isEmpty, !recoding else { return false }
        return row == Self.meRow ? meName == name : row == name
    }

    /// Whether a row is renamed in place rather than chosen: the slot's own
    /// answer, proposed or confirmed — a click on the name always edits it
    /// (owner, 6 Oct 2026).
    func canRename(_ row: String) -> Bool {
        !recoding && row != Self.newRow && row != Self.meRow
            && !request.slot.name.isEmpty && row == request.slot.name
    }

    /// The new spelling. Left as it is, a proposed name is a yes (sent as a
    /// pick of its own row, which the SPA reads as a confirm); a confirmed one
    /// changes nothing and the rename ends with the picker open.
    func submitRename() {
        let name = renameDraft.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else {
            cancelRename()
            return
        }
        if name == request.slot.name {
            if request.slot.confirmed { cancelRename() } else { send(name, kind: .name) }
            return
        }
        send(name, kind: .rename)
    }

    /// Tab or an arrow out of the name field: back to the list, on the row
    /// above or below.
    func leaveRename(by delta: Int) {
        renaming = false
        let name = request.slot.name
        if let i = rows.firstIndex(of: name), rows.indices.contains(i + delta) {
            selection = rows[i + delta]
        }
        focusListRequest += 1
    }

    func cancelRename() {
        renaming = false
        focusListRequest += 1
    }

    /// A picked row. The web side decides what it means.
    func choose(_ row: String) {
        guard row != Self.newRow else { return }
        if row == Self.swapRow {
            onChoose(PersonPickerPick(name: "", kind: .swap))
            onClose()
            return
        }
        if canRename(row) {
            if !renaming {
                renameDraft = row
                renaming = true
            }
            return
        }
        let me = row == Self.meRow
        send((me ? meName ?? "" : row), kind: me ? .me : .name)
    }

    /// The typed name: someone new, unless the web side finds the name taken.
    func submitDraft() { send(draft, kind: .new) }

    /// Whether the current answer can be refused with the ✕: a moderator or
    /// observer the slot points at (design-people.md §J8.8).
    var canClear: Bool {
        !recoding && request.slot.role != .participant && request.slot.person != nil
            && !request.slot.name.isEmpty
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
        onChoose(PersonPickerPick(name: name, kind: kind, role: recoding ? browsing : nil))
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
            PersonPickerRoles(model: model)
                .frame(maxWidth: .infinity)
            PersonPickerList(model: model)
        }
        .padding(10)
        .frame(width: model.contentWidth)
    }
}

/// Moderator | Participant | Observer. The speaker's own role, and each role
/// they can be recoded to (§J7 R1: a moderator and an observer, as each
/// other), is enabled; switching shows that role's rows, where a pick recodes
/// them. Participant stays off for a moderator or observer, and every other
/// segment for a participant, until R2. AppKit, because SwiftUI's segmented
/// picker cannot disable one segment.
private struct PersonPickerRoles: NSViewRepresentable {
    @ObservedObject var model: PersonPickerModel

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeNSView(context: Context) -> NSSegmentedControl {
        let control = Self.makeControl(request: model.request, controlSize: model.metrics.controlSize)
        control.target = context.coordinator
        control.action = #selector(Coordinator.segmentChanged(_:))
        return control
    }

    @MainActor
    final class Coordinator: NSObject {
        let model: PersonPickerModel
        init(model: PersonPickerModel) { self.model = model }

        @objc func segmentChanged(_ sender: NSSegmentedControl) {
            let roles = PersonPickerRequest.Role.allCases
            guard roles.indices.contains(sender.selectedSegment) else { return }
            model.browse(roles[sender.selectedSegment])
        }
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
        let open = request.openRoles
        for (i, role) in roles.enumerated() {
            control.setEnabled(open.contains(role), forSegment: i)
        }
        control.selectedSegment = roles.firstIndex(of: request.slot.role) ?? 0
        control.setAccessibilityLabel(request.labels.roleGroup)
        control.refusesFirstResponder = true
        return control
    }

    func updateNSView(_ control: NSSegmentedControl, context: Context) {
        let i = PersonPickerRequest.Role.allCases.firstIndex(of: model.browsing) ?? 0
        if control.selectedSegment != i { control.selectedSegment = i }
    }
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
        // The current name opens as a field, which takes the keyboard itself.
        table.claimsFocusOnAppear = model.selection != PersonPickerModel.newRow && !model.renaming
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
        context.coordinator.syncBrowsing()
        context.coordinator.syncRenaming()
        context.coordinator.syncSelection()
    }

    @MainActor
    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate, NSTextFieldDelegate {
        let model: PersonPickerModel
        weak var table: NSTableView?
        private weak var newField: NSTextField?
        private weak var renameField: NSTextField?
        private var focusListRequest = 0
        private var wasRenaming = false
        private var shownRole: PersonPickerRequest.Role?

        /// Another role's segment redraws the list with that role's rows.
        func syncBrowsing() {
            guard model.browsing != shownRole, let table else { return }
            let first = shownRole == nil
            shownRole = model.browsing
            if !first { table.reloadData() }
        }

        /// Entering or leaving a rename redraws the current row as a field, or
        /// back as a name.
        func syncRenaming() {
            guard model.renaming != wasRenaming, let table else { return }
            wasRenaming = model.renaming
            table.reloadData()
            if model.renaming {
                DispatchQueue.main.async { [weak self] in
                    guard let field = self?.renameField else { return }
                    field.window?.makeFirstResponder(field)
                    field.currentEditor()?.selectAll(nil)
                }
            }
        }

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
                let newCode = model.newCode
                lead = PickerBadge(code: newCode, proposed: false)
                let field = PickerRowView.nameField(text: model.draft, prompt: model.newPrompt)
                field.delegate = self
                newField = field
                name = field
                label = "\(newCode), \(model.newPrompt)"
            case PersonPickerModel.swapRow:
                let icon = NSImageView(image: NSImage(systemSymbolName: "arrow.left.arrow.right",
                                                      accessibilityDescription: nil) ?? NSImage())
                icon.contentTintColor = .secondaryLabelColor
                icon.symbolConfiguration = .init(pointSize: m.nameFont.pointSize, weight: .regular)
                lead = icon
                name = NSTextField(labelWithString: model.swapLabel ?? "")
                label = model.swapLabel ?? ""
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
                lead = PickerBadge(code: model.code(for: id), proposed: proposed)
                if model.renaming, model.canRename(id) {
                    let field = PickerRowView.nameField(text: model.renameDraft, prompt: id)
                    field.setAccessibilityLabel(model.request.labels.menu)
                    field.delegate = self
                    renameField = field
                    name = field
                } else {
                    name = NSTextField(labelWithString: id)
                }
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
            guard let field = notification.object as? NSTextField else { return }
            if field === renameField { model.renameDraft = field.stringValue } else { model.draft = field.stringValue }
        }

        /// Return names someone new, Escape closes, and the arrows leave the
        /// field — the field editor's own commands, which arrive before it acts.
        func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
            // The rename field, where the picker opens: Return renames (or says
            // yes to a proposed name left as it is), Escape abandons the edit
            // and the picker, and Tab or an arrow goes to the list.
            if control === renameField {
                switch selector {
                case #selector(NSResponder.insertNewline(_:)): model.submitRename(); return true
                case #selector(NSResponder.cancelOperation(_:)): model.close(); return true
                case #selector(NSResponder.moveDown(_:)), #selector(NSResponder.insertTab(_:)):
                    model.leaveRename(by: 1); return true
                case #selector(NSResponder.moveUp(_:)), #selector(NSResponder.insertBacktab(_:)):
                    model.leaveRename(by: -1); return true
                default: return false
                }
            }
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
            case PersonPickerModel.swapRow: return model.swapLabel ?? ""
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
