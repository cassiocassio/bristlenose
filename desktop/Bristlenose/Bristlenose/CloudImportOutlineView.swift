import AppKit
import SwiftUI

// The import grid: an `NSOutlineView` with floating day headers.
//
// **Why AppKit and not SwiftUI `Table`.** The design has three things `Table`
// cannot express at all: group rows, floating group rows, and hierarchy. `Table`
// has no sections; `DisclosureTableRow` gives nesting but still no day header,
// and nothing in SwiftUI pins one to the top of the scroll. This is the
// `desktop/CLAUDE.md` § Native primitives rule read the way it is written — the
// system primitive here is `NSOutlineView`, and composing an approximation out
// of `List` rows would be the departure needing an argument.
//
// HIG, verbatim: "Use an outline view instead of a table view to present
// hierarchical data", and "expose data hierarchy in the first column only."
// The triangle and the indent live in Meeting; every other column stays flat.
//
// What the outline gives us for free, and is the reason not to hand-roll it:
// arrow-key navigation, left/right expand-collapse, type-select, column
// resizing, VoiceOver row and column semantics, and the floating header.
//
// Shape: docs/mockups/cloud-import-recordings-grid.html.

// MARK: - Metrics

/// Every pixel decision in one place, because these are the numbers that get
/// nudged against a real window and nobody wants to hunt them through a file.
private enum Metrics {
    static let rowHeight: CGFloat = 34
    static let dayHeight: CGFloat = 22
    static let indentPerLevel: CGFloat = 14
    /// Leading inset for the day header's label. Group rows sit at level 0, so
    /// AppKit gives them no indent of their own.
    static let dayLabelInset: CGFloat = 10
    static let cellInset: CGFloat = 6
    static let titleSize: CGFloat = 13
    static let subtitleSize: CGFloat = 11
}

private enum Column {
    static let tick = NSUserInterfaceItemIdentifier("tick")
    static let meeting = NSUserInterfaceItemIdentifier("meeting")
    static let scheduled = NSUserInterfaceItemIdentifier("scheduled")
    static let recorded = NSUserInterfaceItemIdentifier("recorded")
    static let size = NSUserInterfaceItemIdentifier("size")
    static let expires = NSUserInterfaceItemIdentifier("expires")
    static let status = NSUserInterfaceItemIdentifier("status")
}

// MARK: - The representable

struct CloudImportOutlineView: NSViewRepresentable {
    @ObservedObject var store: CloudImportStore
    let platform: CloudPlatform

    func makeCoordinator() -> Coordinator { Coordinator(store: store, platform: platform) }

    func makeNSView(context: Context) -> NSScrollView {
        let outline = OutlineView()
        outline.dataSource = context.coordinator
        outline.delegate = context.coordinator
        outline.coordinator = context.coordinator

        // `.custom` or `heightOfRowByItem` is never called at all — the other
        // styles pin a fixed height and ignore the delegate silently. This cost
        // a whole QA round on the project sidebar; see desktop/CLAUDE.md.
        outline.rowSizeStyle = .custom
        outline.style = .inset
        outline.headerView = NSTableHeaderView()
        outline.floatsGroupRows = true
        outline.indentationPerLevel = Metrics.indentPerLevel
        outline.autoresizesOutlineColumn = false
        outline.usesAlternatingRowBackgroundColors = false
        // Separators, not stripes — the mockup's decision, and it means there
        // is no `NSTableRowView` subclass to write.
        outline.gridStyleMask = [.solidHorizontalGridLineMask]
        outline.gridColor = .separatorColor
        outline.allowsMultipleSelection = false
        outline.allowsEmptySelection = true
        // Slack goes to Meeting: it is the only column left resizable below.
        outline.columnAutoresizingStyle = .uniformColumnAutoresizingStyle

        addColumns(to: outline)
        outline.outlineTableColumn = outline.tableColumns.first { $0.identifier == Column.meeting }

        let scrollView = NSScrollView()
        scrollView.documentView = outline
        scrollView.hasVerticalScroller = true
        scrollView.autohidesScrollers = true
        scrollView.drawsBackground = false
        context.coordinator.outline = outline
        context.coordinator.reload(force: true)
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        context.coordinator.store = store
        context.coordinator.platform = platform
        context.coordinator.syncExpiresColumn()
        context.coordinator.reload(force: false)
    }

    private func addColumns(to outline: NSOutlineView) {
        func column(
            _ id: NSUserInterfaceItemIdentifier,
            _ title: String,
            width: CGFloat,
            resizable: Bool = false,
            alignment: NSTextAlignment = .natural
        ) -> NSTableColumn {
            let c = NSTableColumn(identifier: id)
            c.title = title
            c.width = width
            c.minWidth = resizable ? 200 : width
            c.maxWidth = resizable ? 10_000 : width
            c.headerCell.alignment = alignment
            return c
        }

        // Header deliberately blank: a titled checkbox column reads as a filter
        // control rather than as a per-row choice.
        outline.addTableColumn(column(Column.tick, "", width: 26))
        outline.addTableColumn(column(Column.meeting, "Meeting", width: 320, resizable: true))
        outline.addTableColumn(column(Column.scheduled, "Scheduled", width: 92))
        outline.addTableColumn(column(Column.recorded, "Recorded", width: 92))
        outline.addTableColumn(column(Column.size, "Size", width: 74, alignment: .right))
        // Added and removed live by `syncExpiresColumn`, because the platform can
        // change under the same window.
        outline.addTableColumn(column(Column.expires, "Expires", width: 92))
        outline.addTableColumn(column(Column.status, "Status", width: 150))
    }
}

// MARK: - Coordinator

extension CloudImportOutlineView {

    @MainActor
    final class Coordinator: NSObject, NSOutlineViewDataSource, NSOutlineViewDelegate {
        var store: CloudImportStore
        var platform: CloudPlatform
        weak var outline: NSOutlineView?

        private var result: CloudImportOutline.Result = .empty
        /// The structural fingerprint of what is currently on screen. A full
        /// `reloadData()` is only worth paying when this moves; anything else
        /// (a progress tick, an outcome landing) refreshes cell contents while
        /// leaving the item tree, its expansion and the selection alone.
        private var structure: [String] = []
        /// Guards the selection round trip. Writing the store from
        /// `selectionDidChange` while applying the store's own selection is how
        /// a focus model starts fighting the user.
        private var applyingStoreState = false

        init(store: CloudImportStore, platform: CloudPlatform) {
            self.store = store
            self.platform = platform
        }

        // MARK: Reload

        func reload(force: Bool) {
            guard let outline else { return }
            result = store.outline
            let fingerprint = Self.fingerprint(of: result)

            if force || fingerprint != structure {
                structure = fingerprint
                outline.reloadData()
                expandDays()
                applyCollapsedMeetings()
            } else if outline.numberOfRows > 0 {
                // Same rows, different contents. Reusing the item tree keeps
                // expansion and selection; `reloadData()` here would throw both
                // away on every percent of every download.
                outline.reloadData(
                    forRowIndexes: IndexSet(integersIn: 0..<outline.numberOfRows),
                    columnIndexes: IndexSet(integersIn: 0..<outline.numberOfColumns)
                )
            }
            applySelection()
        }

        private static func fingerprint(of result: CloudImportOutline.Result) -> [String] {
            result.days.flatMap { day in
                [day.id] + day.children.flatMap { [$0.id] + $0.children.map(\.id) }
            }
        }

        private func expandDays() {
            guard let outline else { return }
            for day in result.days { outline.expandItem(day) }
        }

        /// Meetings are expanded by default — the point of nesting is to *show*
        /// that a call produced two files, not to hide it behind a triangle.
        /// A collapse the researcher performs is theirs and survives filtering.
        private func applyCollapsedMeetings() {
            guard let outline else { return }
            for day in result.days {
                for node in day.children where !node.children.isEmpty {
                    if case .meeting(let meeting) = node.kind,
                       store.collapsedMeetings.contains(meeting.id) {
                        outline.collapseItem(node)
                    } else {
                        outline.expandItem(node)
                    }
                }
            }
        }

        private func applySelection() {
            guard let outline else { return }
            applyingStoreState = true
            defer { applyingStoreState = false }
            guard let focused = store.focusedRowID,
                  let node = node(forRowID: focused)
            else {
                if store.focusedRowID == nil { outline.deselectAll(nil) }
                return
            }
            let row = outline.row(forItem: node)
            guard row >= 0 else { return }
            if outline.selectedRow != row {
                outline.selectRowIndexes(IndexSet(integer: row), byExtendingSelection: false)
            }
        }

        private func node(forRowID id: String) -> CloudImportOutline.Node? {
            for day in result.days {
                for node in day.children {
                    if node.row?.id == id { return node }
                    for child in node.children where child.row?.id == id { return child }
                }
            }
            return nil
        }

        /// Adds or removes the Expires column to match the platform.
        ///
        /// A column of em-dashes pretending to be data is worse than an absent
        /// one — Drive has no per-file expiry at all, so on Meet the column is
        /// not narrow, it is *gone*.
        func syncExpiresColumn() {
            guard let outline else { return }
            let existing = outline.tableColumns.first { $0.identifier == Column.expires }
            switch (platform.hasPerFileExpiry, existing) {
            case (false, .some(let column)):
                outline.removeTableColumn(column)
            case (true, .none):
                let column = NSTableColumn(identifier: Column.expires)
                column.title = "Expires"
                column.width = 92
                column.minWidth = 92
                column.maxWidth = 92
                // Before Status, which is always last.
                outline.addTableColumn(column)
                if let status = outline.tableColumns.firstIndex(where: { $0.identifier == Column.status }),
                   let expires = outline.tableColumns.firstIndex(where: { $0.identifier == Column.expires }) {
                    outline.moveColumn(expires, toColumn: status)
                }
            default:
                break
            }
        }

        // MARK: Data source

        func outlineView(_ outlineView: NSOutlineView, numberOfChildrenOfItem item: Any?) -> Int {
            guard let node = item as? CloudImportOutline.Node else { return result.days.count }
            return node.children.count
        }

        func outlineView(_ outlineView: NSOutlineView, child index: Int, ofItem item: Any?) -> Any {
            guard let node = item as? CloudImportOutline.Node else { return result.days[index] }
            return node.children[index]
        }

        func outlineView(_ outlineView: NSOutlineView, isItemExpandable item: Any) -> Bool {
            (item as? CloudImportOutline.Node).map { !$0.children.isEmpty } ?? false
        }

        // MARK: Delegate — structure

        func outlineView(_ outlineView: NSOutlineView, isGroupItem item: Any) -> Bool {
            guard case .day = (item as? CloudImportOutline.Node)?.kind else { return false }
            return true
        }

        /// Days carry no triangle: they are always open, and a control that
        /// cannot usefully be operated is noise. Meetings keep theirs.
        func outlineView(_ outlineView: NSOutlineView, shouldShowOutlineCellForItem item: Any) -> Bool {
            guard case .day = (item as? CloudImportOutline.Node)?.kind else { return true }
            return false
        }

        func outlineView(_ outlineView: NSOutlineView, shouldSelectItem item: Any) -> Bool {
            // A day is a label and a meeting header has no file behind it.
            // Neither is a destination for the keyboard.
            (item as? CloudImportOutline.Node)?.row != nil
        }

        func outlineView(_ outlineView: NSOutlineView, heightOfRowByItem item: Any) -> CGFloat {
            guard case .day = (item as? CloudImportOutline.Node)?.kind else { return Metrics.rowHeight }
            return Metrics.dayHeight
        }

        func outlineView(_ outlineView: NSOutlineView, shouldCollapseItem item: Any) -> Bool {
            recordCollapse(item, collapsed: true)
            return true
        }

        func outlineView(_ outlineView: NSOutlineView, shouldExpandItem item: Any) -> Bool {
            recordCollapse(item, collapsed: false)
            return true
        }

        private func recordCollapse(_ item: Any, collapsed: Bool) {
            guard let node = item as? CloudImportOutline.Node,
                  case .meeting(let meeting) = node.kind
            else { return }
            if collapsed {
                store.collapsedMeetings.insert(meeting.id)
            } else {
                store.collapsedMeetings.remove(meeting.id)
            }
        }

        func outlineViewSelectionDidChange(_ notification: Notification) {
            guard !applyingStoreState, let outline else { return }
            let selected = outline.selectedRow
            guard selected >= 0,
                  let node = outline.item(atRow: selected) as? CloudImportOutline.Node,
                  let row = node.row
            else { return }
            store.focusedRowID = row.id
        }

        /// Type-select on the meeting title — the only string a person would
        /// type to find a row.
        func outlineView(
            _ outlineView: NSOutlineView,
            typeSelectStringFor tableColumn: NSTableColumn?,
            item: Any
        ) -> String? {
            guard let node = item as? CloudImportOutline.Node else { return nil }
            switch node.kind {
            case .day(let day):             return day.label
            case .meeting(let meeting):     return meeting.title
            case .recording(let recording): return recording.row.title
            }
        }

        // MARK: Delegate — views

        func outlineView(
            _ outlineView: NSOutlineView,
            viewFor tableColumn: NSTableColumn?,
            item: Any
        ) -> NSView? {
            guard let node = item as? CloudImportOutline.Node else { return nil }

            // Group rows are handed a nil column and span the full width.
            guard let tableColumn else {
                guard case .day(let day) = node.kind else { return nil }
                return dayView(for: day, in: outlineView)
            }

            switch tableColumn.identifier {
            case Column.tick:      return tickView(for: node, in: outlineView)
            case Column.meeting:   return meetingView(for: node, in: outlineView)
            case Column.scheduled: return scheduledView(for: node, in: outlineView)
            case Column.recorded:  return recordedView(for: node, in: outlineView)
            case Column.size:      return sizeView(for: node, in: outlineView)
            case Column.expires:   return expiresView(for: node, in: outlineView)
            case Column.status:    return statusView(for: node, in: outlineView)
            default:               return nil
            }
        }

        private func dayView(for day: CloudImportOutline.Day, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.meeting, in: outline)
            view.leadingInset = Metrics.dayLabelInset
            view.configure(
                title: day.label,
                titleFont: .systemFont(ofSize: Metrics.subtitleSize, weight: .semibold),
                subtitle: nil
            )
            return view
        }

        private func tickView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView? {
            let view = reuse(TickCellView.self, Column.tick, in: outline)
            guard let row = node.row, row.showsCheckbox else {
                // No checkbox at all, not a disabled one. There is nothing to
                // fetch and offering a control would be a lie.
                view.configureEmpty()
                return view
            }
            view.configure(
                rowID: row.id,
                // An already-held file reads as ticked-and-disabled: it is here,
                // and re-fetching it would spend an expiry-limited remote read
                // on a purely local problem.
                on: store.ticked.contains(row.id) || !row.localState.isSelectable,
                enabled: row.isSelectable,
                label: row.title,
                target: self,
                action: #selector(tickChanged(_:))
            )
            return view
        }

        @objc private func tickChanged(_ sender: RowCheckbox) {
            guard let rowID = sender.rowID else { return }
            store.toggle(rowID)
            // The store is the truth: a row it refused to tick must not be left
            // drawn as ticked.
            sender.state = store.ticked.contains(rowID) ? .on : .off
        }

        private func meetingView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.meeting, in: outline)
            view.leadingInset = 0
            switch node.kind {
            case .day(let day):
                view.configure(title: day.label, subtitle: nil)

            case .meeting(let meeting):
                view.configure(
                    title: meeting.title,
                    subtitle: Self.attendeeLine(meeting.attendees, organiser: meeting.organiser)
                        ?? CloudCount.noun(meeting.recordingCount, "recording"),
                    badge: nil
                )

            case .recording(let recording):
                if recording.isChild {
                    // A child says only what distinguishes it from its
                    // siblings. Repeating the title and the attendee line on
                    // each one would be three copies of the same sentence.
                    view.configure(
                        title: "Recording \(recording.ordinal ?? 1)",
                        titleFont: .systemFont(ofSize: Metrics.titleSize, weight: .regular),
                        subtitle: nil
                    )
                } else {
                    let row = recording.row
                    view.configure(
                        title: row.title,
                        subtitle: Self.attendeeLine(row.attendees, organiser: row.organiser)
                    )
                }
            }
            return view
        }

        /// Names in the list, emails never — they are a re-identification key
        /// and are also unscannable. They earn their place at the "who is p1?"
        /// promotion step.
        private static func attendeeLine(
            _ attendees: [CloudImportRow.Attendee],
            organiser: CloudImportRow.Attendee?
        ) -> String? {
            let (names, overflow) = AttendeeLine.compose(attendees)
            if names.isEmpty {
                // Someone else's meeting: their name is the workflow — the fix
                // is to ping them — where a count would be dead weight.
                if let organiser { return organiser.listLabel }
                // Nothing, not "0 attendees". A meeting with no invitees is an
                // ordinary meeting, and announcing the zero is chrome for a
                // non-event.
                return attendees.isEmpty ? nil : CloudCount.noun(attendees.count, "attendee")
            }
            let joined = names.joined(separator: " · ")
            // A count, not an ellipsis: "+4" says there are six.
            return overflow > 0 ? "\(joined)  +\(overflow)" : joined
        }

        private func scheduledView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.scheduled, in: outline)
            view.leadingInset = 0
            switch node.kind {
            case .meeting(let meeting):
                view.configureClock(at: meeting.scheduledAt, length: meeting.scheduledDuration)
            case .recording(let recording) where !recording.isChild:
                view.configureClock(at: recording.row.scheduledAt,
                                    length: recording.row.scheduledDuration)
            default:
                // A child's meeting time is on the row above it. Repeating it
                // would say the same thing three times.
                view.configureDash()
            }
            return view
        }

        private func recordedView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.recorded, in: outline)
            view.leadingInset = 0
            // A meeting header has no file, so it has no record button moment.
            guard case .recording(let recording) = node.kind else {
                view.configureDash()
                return view
            }
            view.configureClock(at: recording.row.recordedAt, length: recording.row.duration)
            return view
        }

        private func sizeView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.size, in: outline)
            view.leadingInset = 0
            view.alignment = .right
            guard let bytes = node.row?.sizeBytes else {
                view.configureDash()
                return view
            }
            view.configure(
                title: ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file),
                titleFont: .monospacedDigitSystemFont(ofSize: Metrics.subtitleSize, weight: .regular),
                subtitle: nil,
                titleColour: .secondaryLabelColor
            )
            return view
        }

        private func expiresView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.expires, in: outline)
            view.leadingInset = 0
            view.alignment = .natural
            guard let expires = node.row?.expiresAt else {
                view.configureDash()
                return view
            }
            // Earn the red: a countdown on every row is a wall of countdowns,
            // and then none of them mean anything.
            let urgent = expires.timeIntervalSinceNow < 7 * 24 * 3600
            view.configure(
                title: expires.formatted(.relative(presentation: .named)),
                titleFont: .systemFont(ofSize: Metrics.subtitleSize),
                subtitle: nil,
                titleColour: urgent ? .systemOrange : .secondaryLabelColor
            )
            return view
        }

        private func statusView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(StatusCellView.self, Column.status, in: outline)
            guard let row = node.row else {
                view.configureEmpty()
                return view
            }
            if let progress = store.progress[row.id] {
                view.configureProgress(progress.fraction)
            } else if let outcome = store.outcomes[row.id] {
                switch outcome {
                case .imported:
                    view.configureText("✓ Imported", colour: .systemGreen, bold: true)
                case .failed(let reason, _):
                    view.configureText(reason, colour: .systemRed, bold: false)
                case .cancelled:
                    view.configureText("Stopped", colour: .secondaryLabelColor, bold: false)
                }
            } else if store.isFetching && store.ticked.contains(row.id) {
                view.configureText("Queued", colour: .secondaryLabelColor, bold: false)
            } else if let label = row.statusLabel {
                view.configureText(
                    label,
                    colour: row.localState.isWarning ? .systemOrange : .secondaryLabelColor,
                    bold: false
                )
            } else {
                view.configureEmpty()
            }
            return view
        }

        private func reuse<V: NSView>(
            _ type: V.Type,
            _ identifier: NSUserInterfaceItemIdentifier,
            in outline: NSOutlineView
        ) -> V {
            if let existing = outline.makeView(withIdentifier: identifier, owner: self) as? V {
                return existing
            }
            let view = V()
            view.identifier = identifier
            return view
        }

        // MARK: Keyboard

        /// Space ticks the focused row — the gesture that makes this a list of
        /// options rather than a list of destinations.
        func toggleFocusedRow() {
            store.toggleFocused()
        }
    }
}

// MARK: - The outline view itself

/// Exists for one override. Space is the native "operate this row's control"
/// key in a table of choices, and `NSOutlineView` spends it on type-select
/// otherwise — typing a space into a search-as-you-type buffer, which is
/// invisible and does nothing.
private final class OutlineView: NSOutlineView {
    weak var coordinator: CloudImportOutlineView.Coordinator?

    override func keyDown(with event: NSEvent) {
        if event.charactersIgnoringModifiers == " " {
            MainActor.assumeIsolated { coordinator?.toggleFocusedRow() }
            return
        }
        super.keyDown(with: event)
    }
}

// MARK: - Cells

/// A checkbox carrying the row it speaks for. `NSButton.tag` is an `Int` and
/// row ids are strings, so the identity has to ride somewhere.
private final class RowCheckbox: NSButton {
    var rowID: String?
}

private final class TickCellView: NSView {
    private let checkbox = RowCheckbox(checkboxWithTitle: "", target: nil, action: nil)

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        checkbox.translatesAutoresizingMaskIntoConstraints = false
        addSubview(checkbox)
        NSLayoutConstraint.activate([
            checkbox.centerXAnchor.constraint(equalTo: centerXAnchor),
            checkbox.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("not from a nib") }

    func configure(
        rowID: String,
        on: Bool,
        enabled: Bool,
        label: String,
        target: AnyObject,
        action: Selector
    ) {
        checkbox.isHidden = false
        checkbox.rowID = rowID
        checkbox.state = on ? .on : .off
        checkbox.isEnabled = enabled
        checkbox.target = target
        checkbox.action = action
        // VoiceOver reads "Import <meeting>, checkbox" rather than an unnamed
        // control in an unnamed column.
        checkbox.setAccessibilityLabel("Import \(label)")
    }

    func configureEmpty() {
        checkbox.isHidden = true
        checkbox.rowID = nil
        checkbox.target = nil
        checkbox.action = nil
    }
}

/// Title over optional subtitle, with an optional trailing badge on the title
/// line. Every text column in the grid is this shape — a moment over its
/// length, a meeting over its people, a recording over nothing.
private final class TwoLineCellView: NSView {
    private let title = NSTextField(labelWithString: "")
    private let subtitle = NSTextField(labelWithString: "")
    private let badge = NSTextField(labelWithString: "")
    private let titleRow = NSStackView()
    private let stack = NSStackView()
    private var leading: NSLayoutConstraint!

    var leadingInset: CGFloat = 0 {
        didSet { leading.constant = Metrics.cellInset + leadingInset }
    }

    var alignment: NSTextAlignment = .natural {
        didSet {
            title.alignment = alignment
            subtitle.alignment = alignment
            stack.alignment = alignment == .right ? .trailing : .leading
            titleRow.alignment = .firstBaseline
        }
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)

        title.font = .systemFont(ofSize: Metrics.titleSize)
        title.lineBreakMode = .byTruncatingTail
        title.cell?.usesSingleLineMode = true
        subtitle.font = .systemFont(ofSize: Metrics.subtitleSize)
        subtitle.textColor = .secondaryLabelColor
        subtitle.lineBreakMode = .byTruncatingTail
        subtitle.cell?.usesSingleLineMode = true

        badge.font = .systemFont(ofSize: 9, weight: .semibold)
        badge.textColor = .secondaryLabelColor
        badge.wantsLayer = true
        badge.layer?.borderWidth = 0.5
        badge.layer?.cornerRadius = 3
        badge.setContentHuggingPriority(.required, for: .horizontal)
        badge.setContentCompressionResistancePriority(.required, for: .horizontal)

        titleRow.orientation = .horizontal
        titleRow.spacing = 6
        titleRow.alignment = .firstBaseline
        titleRow.addArrangedSubview(title)
        titleRow.addArrangedSubview(badge)

        stack.orientation = .vertical
        stack.spacing = 1
        stack.alignment = .leading
        stack.addArrangedSubview(titleRow)
        stack.addArrangedSubview(subtitle)
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)

        leading = stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Metrics.cellInset)
        NSLayoutConstraint.activate([
            leading,
            stack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -Metrics.cellInset),
            stack.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("not from a nib") }

    func configure(
        title text: String,
        titleFont: NSFont = .systemFont(ofSize: Metrics.titleSize, weight: .semibold),
        subtitle detail: String?,
        badge badgeText: String? = nil,
        titleColour: NSColor = .labelColor
    ) {
        title.stringValue = text
        title.font = titleFont
        title.textColor = titleColour
        title.alignment = alignment
        subtitle.stringValue = detail ?? ""
        subtitle.isHidden = (detail ?? "").isEmpty
        badge.stringValue = badgeText.map { " \($0) " } ?? ""
        badge.isHidden = badgeText == nil
        badge.layer?.borderColor = NSColor.tertiaryLabelColor.cgColor
    }

    /// A moment over how long it ran. Monospaced digits so the eye can compare
    /// down the column, which is the only thing anyone does with a time.
    func configureClock(at moment: Date?, length: TimeInterval?) {
        guard let moment else {
            configureDash()
            return
        }
        configure(
            title: moment.formatted(date: .omitted, time: .shortened),
            titleFont: .monospacedDigitSystemFont(ofSize: Metrics.subtitleSize, weight: .regular),
            subtitle: length.map { DurationFormat.human(seconds: $0) }
        )
        subtitle.font = .monospacedDigitSystemFont(ofSize: Metrics.subtitleSize, weight: .regular)
    }

    /// An em-dash, not a blank. "We have no value for this" and "this column
    /// does not apply to this row" both read better as a mark than as a hole.
    func configureDash() {
        configure(
            title: "—",
            titleFont: .systemFont(ofSize: Metrics.subtitleSize),
            subtitle: nil,
            titleColour: .tertiaryLabelColor
        )
    }
}

/// Status is the one column whose content changes shape rather than value: a
/// determinate bar while bytes move, a sentence before and after.
private final class StatusCellView: NSView {
    private let label = NSTextField(labelWithString: "")
    private let bar = NSProgressIndicator()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        label.font = .systemFont(ofSize: Metrics.subtitleSize)
        label.lineBreakMode = .byTruncatingTail
        label.cell?.usesSingleLineMode = true
        label.translatesAutoresizingMaskIntoConstraints = false

        bar.isIndeterminate = false
        bar.style = .bar
        bar.minValue = 0
        bar.maxValue = 1
        bar.controlSize = .small
        bar.translatesAutoresizingMaskIntoConstraints = false

        addSubview(label)
        addSubview(bar)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Metrics.cellInset),
            label.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -Metrics.cellInset),
            label.centerYAnchor.constraint(equalTo: centerYAnchor),
            bar.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Metrics.cellInset),
            bar.widthAnchor.constraint(equalToConstant: 70),
            bar.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("not from a nib") }

    func configureText(_ text: String, colour: NSColor, bold: Bool) {
        bar.isHidden = true
        label.isHidden = false
        label.stringValue = text
        label.textColor = colour
        label.font = .systemFont(ofSize: Metrics.subtitleSize, weight: bold ? .semibold : .regular)
        // The whole sentence on hover, because a failure reason is exactly the
        // string that will not fit.
        label.toolTip = text
    }

    /// An indeterminate bar for the window between "the transfer started" and
    /// "the server told us how big it is" — a bar sitting at 0% for ten seconds
    /// reads as stalled.
    func configureProgress(_ fraction: Double?) {
        label.isHidden = true
        bar.isHidden = false
        bar.toolTip = nil
        if let fraction {
            if bar.isIndeterminate { bar.stopAnimation(nil); bar.isIndeterminate = false }
            bar.doubleValue = fraction
        } else if !bar.isIndeterminate {
            bar.isIndeterminate = true
            bar.startAnimation(nil)
        }
    }

    func configureEmpty() {
        bar.isHidden = true
        label.isHidden = false
        label.stringValue = ""
        label.toolTip = nil
    }
}
