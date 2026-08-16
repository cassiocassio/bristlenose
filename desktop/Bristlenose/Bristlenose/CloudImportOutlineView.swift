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
// arrow-key navigation, left/right expand-collapse, column resizing, VoiceOver
// row and column semantics, and the floating header. (Type-select is
// deliberately declined — see the note where its delegate method would be.)
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
    /// The platform's own two sizes, named rather than spelled 13 and 11, so
    /// they track a system that has moved them before.
    static let titleSize = NSFont.systemFontSize
    static let subtitleSize = NSFont.smallSystemFontSize
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
    /// Passed rather than read from the environment: the cells are AppKit and
    /// live below SwiftUI's reach, so the one object they all need has to be
    /// handed down explicitly.
    @ObservedObject var i18n: I18n

    func makeCoordinator() -> Coordinator {
        Coordinator(store: store, platform: platform, i18n: i18n)
    }

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
        // Every column carries an autoresizing mask by default, so `.uniform`
        // spreads slack across all of them — Meeting simply absorbs it because
        // the others are clamped `min == max`. (An earlier comment here said
        // Meeting was "the only column left resizable", which is the right
        // outcome from the wrong mechanism and would have survived the fix
        // below.)
        outline.columnAutoresizingStyle = .uniformColumnAutoresizingStyle
        // The disclosure triangle and the indent travel with `outlineTableColumn`,
        // so dragging Status in front of Meeting would put the hierarchy in the
        // middle of the grid — the exact thing this design's second HIG quote
        // rules out. Widths stay draggable; order does not.
        outline.allowsColumnReordering = false
        // Column widths are a personalisation and should outlive the window.
        outline.autosaveName = "CloudImportOutline"
        outline.autosaveTableColumns = true

        addColumns(to: outline, i18n)
        outline.outlineTableColumn = outline.tableColumns.first { $0.identifier == Column.meeting }

        let scrollView = NSScrollView()
        scrollView.documentView = outline
        scrollView.hasVerticalScroller = true
        scrollView.autohidesScrollers = true
        // NB: no `drawsBackground = false`. That spelling is the *sidebar*
        // idiom, for letting an `NSVisualEffectView`'s vibrancy through — and
        // this is a plain window with nothing behind it, so it would paint the
        // area below a short list in `windowBackgroundColor` while the rows sat
        // on `controlBackgroundColor`: two greys and a seam, at its worst in
        // the one-or-two-row state that is this window's commonest.
        context.coordinator.outline = outline
        context.coordinator.reload(force: true)
        // The list is what this window is for, so it takes the keyboard rather
        // than leaving it to the toolbar's filter field. Without this the
        // window opened with arrows and space doing nothing until the user
        // clicked a row — and, when a row *was* pre-selected, drew it in the
        // inactive grey that reads as disabled.
        //
        // Deferred a runloop turn because the view is not in a window yet at
        // `makeNSView` time, so `makeFirstResponder` would have nothing to ask.
        DispatchQueue.main.async { outline.window?.makeFirstResponder(outline) }
        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        context.coordinator.store = store
        context.coordinator.platform = platform
        context.coordinator.i18n = i18n
        context.coordinator.syncExpiresColumn()
        context.coordinator.reload(force: false)
    }

    /// Every column but the tick is draggable, and each has a real range.
    ///
    /// They were all clamped `min == max` except Meeting, which meant a user's
    /// reflex on a clipped column — drag its edge — did nothing on six of
    /// seven. Status is the one that mattered: it carries the per-row failure
    /// sentence that §6's terminus argument rests on being legible, and it was
    /// pinned at 150pt on a window that can be 1400 wide.
    private func addColumns(to outline: NSOutlineView, _ i18n: I18n) {
        func column(
            _ id: NSUserInterfaceItemIdentifier,
            _ title: String,
            width: CGFloat,
            min minWidth: CGFloat? = nil,
            max maxWidth: CGFloat = 10_000,
            alignment: NSTextAlignment = .natural
        ) -> NSTableColumn {
            let c = NSTableColumn(identifier: id)
            c.title = title
            c.width = width
            c.minWidth = minWidth ?? width
            c.maxWidth = maxWidth
            c.headerCell.alignment = alignment
            return c
        }

        // Header deliberately blank: a titled checkbox column reads as a filter
        // control rather than as a per-row choice. Fixed, because a checkbox
        // does not get wider.
        outline.addTableColumn(column(Column.tick, "", width: 26, max: 26))
        outline.addTableColumn(column(Column.meeting, i18n.t("desktop.cloudImport.columnMeeting"),
                                      width: 320, min: 200))
        outline.addTableColumn(column(Column.scheduled, i18n.t("desktop.cloudImport.columnScheduled"),
                                      width: 92, min: 72, max: 160))
        outline.addTableColumn(column(Column.recorded, i18n.t("desktop.cloudImport.columnRecorded"),
                                      width: 92, min: 72, max: 160))
        outline.addTableColumn(column(Column.size, i18n.t("desktop.cloudImport.columnSize"),
                                      width: 74, min: 60, max: 120, alignment: .right))
        // Added and removed live by `syncExpiresColumn`, because the platform can
        // change under the same window.
        outline.addTableColumn(column(Column.expires, i18n.t("desktop.cloudImport.columnExpires"),
                                      width: 92, min: 72, max: 160))
        outline.addTableColumn(column(Column.status, i18n.t("desktop.cloudImport.columnStatus"),
                                      width: 150, min: 110))
    }
}

// MARK: - Coordinator

extension CloudImportOutlineView {

    @MainActor
    final class Coordinator: NSObject, NSOutlineViewDataSource, NSOutlineViewDelegate {
        var store: CloudImportStore
        var platform: CloudPlatform
        var i18n: I18n
        weak var outline: NSOutlineView?

        private var result: CloudImportOutline.Result = .empty
        /// The fingerprint of everything the cells draw from the tree. A full
        /// `reloadData()` is only worth paying when this moves — and is
        /// *required* when it does, because the partial reload cannot swap in a
        /// rebuilt node. See `CloudImportOutline.fingerprint(of:)`.
        private var structure: [String] = []
        /// The store's outline generation last seen. Lets the whole structural
        /// pass — fingerprint, expansion, selection — be skipped on the ~99% of
        /// updates that are a download reporting another percent.
        private var generation = -1
        /// Per-**node** store-derived state, so a refresh can touch only what
        /// moved instead of every row in every column.
        ///
        /// Keyed on the node rather than the row because a meeting header has
        /// no row of its own and still has a checkbox that changes: ticking one
        /// child flips its parent between off, mixed and on. Keyed on rows, the
        /// parent was skipped by the loop entirely and its box never redrew.
        private var cellStates: [String: CellState] = [:]

        private enum CellState: Equatable {
            case row(RowState)
            case meeting(CloudImportOutline.ParentTick)
        }
        /// Guards the selection round trip. Writing the store from
        /// `selectionDidChange` while applying the store's own selection — or
        /// while a programmatic expand/collapse moves it — is how a focus model
        /// starts fighting the user.
        private var applyingStoreState = false

        /// What the two store-driven columns render from. Diffed rather than
        /// re-rendered, because the alternative is ~2,000 `viewFor` calls per
        /// progress tick for the sake of one moving bar.
        private struct RowState: Equatable {
            let ticked: Bool
            let selectable: Bool
            let fraction: Double?
            let inFlight: Bool
            let outcome: String?
            let queued: Bool
        }

        private func state(of row: CloudImportRow) -> RowState {
            let progress = store.progress[row.id]
            let outcome: String? = store.outcomes[row.id].map { outcome in
                switch outcome {
                case .imported:                 return "imported"
                case .failed(let reason, _):    return "failed:\(reason)"
                case .cancelled:                return "cancelled"
                }
            }
            return RowState(
                ticked: store.ticked.contains(row.id),
                selectable: row.isSelectable,
                fraction: progress?.fraction,
                inFlight: progress != nil,
                outcome: outcome,
                queued: store.isFetching && store.ticked.contains(row.id)
            )
        }

        init(store: CloudImportStore, platform: CloudPlatform, i18n: I18n) {
            self.store = store
            self.platform = platform
            self.i18n = i18n
        }

        // MARK: Reload

        func reload(force: Bool) {
            guard let outline else { return }

            // The structural pass, skipped entirely when the store says the
            // tree has not been rebuilt since we last looked.
            if force || store.outlineGeneration != generation {
                generation = store.outlineGeneration
                result = store.outline
                let fingerprint = CloudImportOutline.fingerprint(of: result, locale: i18n.locale)
                if force || fingerprint != structure {
                    structure = fingerprint
                    // The only path that re-asks the data source, and therefore
                    // the only one that can replace a retained node with its
                    // rebuilt twin. `reloadData(forRowIndexes:)` re-requests
                    // *views* for items AppKit already holds — and since `Node`
                    // equality is id-only, a changed row would otherwise render
                    // its previous values forever.
                    outline.reloadData()
                    applyingStoreState = true
                    expandDays()
                    applyCollapsedMeetings()
                    applyingStoreState = false
                }
                applySelection()
                // Every cell was just rebuilt, so there is nothing to refresh —
                // only a baseline to record, or the next tick would diff
                // against an empty map and reload the whole table once more.
                refreshChangedRows(seedOnly: true)
                return
            }

            // Nothing structural moved: a download reported another percent, or
            // a tick landed. Touch only the rows whose store-derived state
            // actually changed, in the two columns that read the store.
            refreshChangedRows(seedOnly: false)
            applySelection()
        }

        /// Reloads the tick and status cells of rows whose state moved.
        ///
        /// The whole point is what it *doesn't* do. Reloading every row in
        /// every column ran `viewFor` ~2,000 times at 200 rows — each rebuilding
        /// a stack view and re-running a formatter — several times a second,
        /// for the length of a batch that the design budgets at 45 to 90
        /// minutes. Three files are in flight at most, so at most three rows
        /// have anything new to say.
        private func refreshChangedRows(seedOnly: Bool) {
            guard let outline, outline.numberOfRows > 0 else {
                cellStates.removeAll()
                return
            }
            var changed = IndexSet()
            var seen: [String: CellState] = [:]
            for index in 0..<outline.numberOfRows {
                guard let node = outline.item(atRow: index) as? CloudImportOutline.Node
                else { continue }
                let current: CellState
                if let row = node.row {
                    current = .row(state(of: row))
                } else if case .meeting = node.kind {
                    current = .meeting(CloudImportOutline.parentTick(
                        for: node.children.compactMap(\.row), ticked: store.ticked))
                } else {
                    continue   // a day header has nothing store-derived on it
                }
                seen[node.id] = current
                if !seedOnly, cellStates[node.id] != current { changed.insert(index) }
            }
            cellStates = seen
            guard !changed.isEmpty else { return }
            let columns = [Column.tick, Column.status].compactMap {
                outline.column(withIdentifier: $0)
            }.filter { $0 >= 0 }
            guard !columns.isEmpty else { return }
            outline.reloadData(forRowIndexes: changed, columnIndexes: IndexSet(columns))
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
                // Covers both "nothing is focused" and "the focused row is
                // gone" — a filter keystroke, a collapsed parent. The second
                // used to leave a stale id in the store with no selection on
                // screen, and space then ticked an invisible row straight into
                // the fetch queue.
                outline.deselectAll(nil)
                // **Only when it actually changes.** `@Published` fires on every
                // assignment, not on every *difference*, so writing nil over nil
                // still publishes — and this runs inside `updateNSView`, so the
                // publish re-renders the view, which calls `updateNSView`, which
                // lands here again. An unconditional write is an infinite render
                // loop on the main thread.
                //
                // It needed two of my own changes to become reachable: removing
                // the pre-selection (so `focusedRowID` is nil at load, which
                // takes this branch) and adding the clear (so the branch writes).
                // Each was right on its own. Together they froze the window on
                // whatever frame it had last drawn — the loading spinner — which
                // reads as "stuck loading" and sent me looking at the network
                // path, where nothing was wrong.
                if store.focusedRowID != nil { store.focusedRowID = nil }
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
                column.title = i18n.t("desktop.cloudImport.columnExpires")
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
            //
            // **Decided 16 Aug 2026, and reviewed twice — leave it.** Making
            // headers selectable would give the parent tick a keyboard route
            // and cost a selectable row that the primary action cannot act on.
            // The trade was declined: a keyboard-without-VoiceOver user ticks
            // the children instead, which reaches exactly the same place, and
            // VoiceOver reaches the header's checkbox directly because it
            // navigates by element rather than by table selection. The only
            // thing lost is a shortcut, not a capability.
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
            // A programmatic apply is us telling the outline what the store
            // already says. Writing it back would publish from inside
            // `updateNSView` and cost a full refresh per structural rebuild.
            guard !applyingStoreState else { return }
            guard let node = item as? CloudImportOutline.Node,
                  case .meeting(let meeting) = node.kind
            else { return }
            // Conditional for the same reason as the selection writes: a Set
            // insert that changes nothing still publishes, and this is reached
            // from AppKit callbacks that fire during our own apply pass.
            if collapsed, !store.collapsedMeetings.contains(meeting.id) {
                store.collapsedMeetings.insert(meeting.id)
            } else if !collapsed, store.collapsedMeetings.contains(meeting.id) {
                store.collapsedMeetings.remove(meeting.id)
            }
        }

        func outlineViewSelectionDidChange(_ notification: Notification) {
            guard !applyingStoreState, let outline else { return }
            let selected = outline.selectedRow
            guard selected >= 0,
                  let node = outline.item(atRow: selected) as? CloudImportOutline.Node,
                  let row = node.row
            else {
                // Deselected — clicking empty space, or the selected row being
                // collapsed away. Leaving the old id in the store meant space
                // kept ticking a row nothing on screen pointed at. Guarded for
                // the same reason as `applySelection`: a no-op write still
                // publishes.
                if store.focusedRowID != nil { store.focusedRowID = nil }
                return
            }
            if store.focusedRowID != row.id { store.focusedRowID = row.id }
        }

        // `typeSelectStringFor` is deliberately NOT implemented, and it was.
        //
        // Removed because it was wrong three ways at once and the window
        // already has the better affordance. (1) Space is a legitimate
        // type-select character and every title here is multi-word — "Weekly
        // sync", "P04 Interview" — but space is also the tick key, so the
        // buffer could never get past the first word. (2) It answered with
        // `row.title` for a child row whose *displayed* title is "Recording 2",
        // so it matched a string nobody could see. (3) It answered for days and
        // meeting headers, which `shouldSelectItem` then refuses — typing
        // "Weekly" matched, the selection was declined, and nothing happened,
        // silently, on some rows and not others.
        //
        // The toolbar's Filter field is the search affordance, it searches
        // people as well as titles, and it does not compete with the keyboard.

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

            // A meeting header has no file of its own, and for a long while
            // that meant it had no checkbox either. But the case this whole
            // outline exists for is one interview that arrived as two files,
            // and wanting both is the ordinary intent — so the header
            // summarises its recordings and can set them all at once.
            if case .meeting = node.kind {
                let children = node.children.compactMap(\.row)
                let tick = CloudImportOutline.parentTick(for: children, ticked: store.ticked)
                guard let draw = tick.draw else {
                    view.configureEmpty()
                    return view
                }
                view.configure(
                    payload: .meeting(children.map(\.id)),
                    state: draw == .on ? .on : (draw == .mixed ? .mixed : .off),
                    enabled: tick.isEnabled,
                    label: meetingAccessibilityName(for: node, children: children),
                    reason: tick.isEnabled ? nil : i18n.t("desktop.cloudImport.allAlreadyHere"),
                    target: self,
                    action: #selector(tickChanged(_:))
                )
                return view
            }

            guard let row = node.row, row.showsCheckbox else {
                // No checkbox at all, not a disabled one. There is nothing to
                // fetch and offering a control would be a lie.
                view.configureEmpty()
                return view
            }
            view.configure(
                payload: .row(row.id),
                // An already-held file reads as ticked-and-disabled: it is here,
                // and re-fetching it would spend an expiry-limited remote read
                // on a purely local problem.
                state: row.drawsTicked(in: store.ticked) ? .on : .off,
                enabled: row.isSelectable,
                label: accessibilityName(for: node),
                // Restored. The SwiftUI cell explained a held row on hover
                // ("Already imported — the file is on Dropbox and needs
                // downloading there") and the port dropped it — leaving a
                // ticked, greyed checkbox beside an empty Status cell with the
                // reason stated nowhere at all, since `.imported` has no status
                // label by design.
                reason: row.isSelectable ? nil : heldReason(row),
                target: self,
                action: #selector(tickChanged(_:))
            )
            return view
        }

        /// What VoiceOver calls a meeting header's checkbox.
        ///
        /// Names the count, because that is the whole difference between this
        /// box and the ones under it — and a keyboard-free "Import P05
        /// Interview" would be indistinguishable from its first child.
        private func meetingAccessibilityName(
            for node: CloudImportOutline.Node,
            children: [CloudImportRow]
        ) -> String {
            guard case .meeting(let meeting) = node.kind else { return "" }
            return i18n.plural("desktop.cloudImport.importAllAccessibility", count: children.count,
                               ["title": meeting.title])
        }

        /// What VoiceOver calls this row.
        ///
        /// Built from the **node**, not the row, because two siblings of one
        /// call carry the same `title` — the event's summary — so a row-derived
        /// label announced "Import P05 Interview, checkbox" twice for two
        /// different files, one 32 minutes and one 38. The ordinal is the only
        /// thing that distinguishes them on screen, and it has to be the thing
        /// that distinguishes them in speech.
        private func accessibilityName(for node: CloudImportOutline.Node) -> String {
            guard case .recording(let recording) = node.kind else { return "" }
            guard let ordinal = recording.ordinal else {
                return i18n.t("desktop.cloudImport.importRowAccessibility", ["title": recording.row.title])
            }
            return i18n.t("desktop.cloudImport.importRecordingAccessibility",
                          ["n": String(ordinal), "title": recording.row.title])
        }

        /// Why a held row's checkbox is disabled. The distinction that matters:
        /// a placeholder or an unplugged volume is a *local* problem, and
        /// re-fetching would spend an expiry-limited remote read on it.
        private func heldReason(_ row: CloudImportRow) -> String? {
            switch row.localState {
            case .imported:
                return i18n.t("desktop.cloudImport.heldImported")
            case .notDownloaded(let provider):
                return i18n.t("desktop.cloudImport.heldNotDownloaded", ["provider": provider])
            case .driveNotConnected(let volume):
                return i18n.t("desktop.cloudImport.heldDriveNotConnected", ["volume": volume])
            default:
                return nil
            }
        }

        @objc private func tickChanged(_ sender: RowCheckbox) {
            // The store is the truth in both branches: the button's own state
            // after a click is AppKit's guess, and a row the store refuses must
            // not be left drawn as ticked. Nothing here reads `sender.state`.
            switch sender.payload {
            case .row(let rowID):
                store.toggle(rowID)
                sender.state = store.ticked.contains(rowID) ? .on : .off
            case .meeting(let rowIDs):
                store.toggleMeeting(rowIDs: rowIDs)
                // Redrawing the children is `refreshChangedRows`'s job on the
                // next update — this only settles the box that was clicked,
                // which AppKit has already moved somewhere of its own choosing.
                let children = store.visibleRows.filter { rowIDs.contains($0.id) }
                let tick = CloudImportOutline.parentTick(for: children, ticked: store.ticked)
                sender.allowsMixedState = (tick.draw == .mixed)
                sender.state = tick.draw == .on ? .on : (tick.draw == .mixed ? .mixed : .off)
            case .none:
                return
            }
        }

        private func meetingView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.meeting, in: outline)
            view.leadingInset = 0
            switch node.kind {
            // No `.day` case: group rows are only ever drawn through the
            // nil-column path above, so a branch here would be unreachable.
            case .day:
                view.configureDash(i18n.t("desktop.cloudImport.notApplicable"))

            case .meeting(let meeting):
                view.configure(
                    title: meeting.title,
                    subtitle: AttendeeLine.summary(meeting.attendees, organiser: meeting.organiser)
                        ?? i18n.plural("desktop.cloudImport.meetingRecordingCount", count: meeting.recordingCount)
                )

            case .recording(let recording):
                if let ordinal = recording.ordinal {
                    // A child says only what distinguishes it from its
                    // siblings. Repeating the title and the attendee line on
                    // each one would be three copies of the same sentence —
                    // and the parent row is directly above it.
                    view.configure(
                        title: i18n.t("desktop.cloudImport.recordingOrdinal", ["n": String(ordinal)]),
                        titleFont: .systemFont(ofSize: Metrics.titleSize, weight: .regular),
                        subtitle: nil,
                        // Spatial adjacency carries the meeting's name for
                        // someone looking at the screen. VoiceOver has no
                        // adjacency, so it is said.
                        accessibility: i18n.t("desktop.cloudImport.recordingOrdinalAccessibility",
                                              ["n": String(ordinal), "title": recording.row.title])
                    )
                } else {
                    let row = recording.row
                    view.configure(
                        title: row.title,
                        subtitle: AttendeeLine.summary(row.attendees, organiser: row.organiser)
                    )
                }
            }
            return view
        }

        private func scheduledView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.scheduled, in: outline)
            view.leadingInset = 0
            switch node.kind {
            case .meeting(let meeting):
                view.configureClock(at: meeting.scheduledAt, length: meeting.scheduledDuration,
                                    notApplicable: i18n.t("desktop.cloudImport.notApplicable"))
            case .recording(let recording) where !recording.isChild:
                view.configureClock(at: recording.row.scheduledAt,
                                    length: recording.row.scheduledDuration,
                                    notApplicable: i18n.t("desktop.cloudImport.notApplicable"))
            default:
                // A child's meeting time is on the row above it. Repeating it
                // would say the same thing three times.
                view.configureDash(i18n.t("desktop.cloudImport.notApplicable"))
            }
            return view
        }

        private func recordedView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.recorded, in: outline)
            view.leadingInset = 0
            // A meeting header has no file, so it has no record button moment.
            guard case .recording(let recording) = node.kind else {
                view.configureDash(i18n.t("desktop.cloudImport.notApplicable"))
                return view
            }
            view.configureClock(at: recording.row.recordedAt, length: recording.row.duration,
                                notApplicable: i18n.t("desktop.cloudImport.notApplicable"))
            return view
        }

        private func sizeView(for node: CloudImportOutline.Node, in outline: NSOutlineView) -> NSView {
            let view = reuse(TwoLineCellView.self, Column.size, in: outline)
            view.leadingInset = 0
            view.alignment = .right
            // A meeting header shows a dash, **not the sum of its recordings**.
            // Decided 16 Aug 2026 against the reviewer's suggestion: a total is
            // a number nobody acts on. You do not choose between the two halves
            // of one interview on size — you want both, and the files are what
            // they are — so the sum would restate what the rows below already
            // say and add a figure that informs no decision.
            guard let bytes = node.row?.sizeBytes else {
                view.configureDash(i18n.t("desktop.cloudImport.notApplicable"))
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
                view.configureDash(i18n.t("desktop.cloudImport.notApplicable"))
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
                view.configureProgress(progress.fraction, name: row.title, i18n: i18n)
            } else if let outcome = store.outcomes[row.id] {
                switch outcome {
                case .imported:
                    view.configureText(i18n.t("desktop.cloudImport.statusImported"), colour: .systemGreen, bold: true,
                                       symbol: "checkmark")
                case .failed(let reason, _):
                    view.configureText(reason, colour: .systemRed, bold: false)
                case .cancelled:
                    view.configureText(i18n.t("desktop.cloudImport.statusStopped"), colour: .secondaryLabelColor, bold: false)
                }
            } else if store.isFetching && store.ticked.contains(row.id) {
                view.configureText(i18n.t("desktop.cloudImport.statusQueued"), colour: .secondaryLabelColor, bold: false)
            } else if let label = row.statusLabel(i18n) {
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
        ///
        /// - Returns: false when the row refused, so the caller can beep. A key
        ///   that is understood and declined gets a beep on this platform;
        ///   Finder, Mail and Xcode all do it, and silence reads as the app
        ///   having missed the keystroke.
        @discardableResult
        func toggleFocusedRow() -> Bool { store.toggleFocused() }
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
            MainActor.assumeIsolated {
                if coordinator?.toggleFocusedRow() != true { NSSound.beep() }
            }
            return
        }
        super.keyDown(with: event)
    }
}

// MARK: - Cells

/// A checkbox carrying the row it speaks for. `NSButton.tag` is an `Int` and
/// row ids are strings, so the identity has to ride somewhere.
private final class RowCheckbox: NSButton {
    /// What this box speaks for. An enum rather than two optionals, so the
    /// action cannot read a leaf as a meeting or find both nil.
    enum Payload: Equatable {
        case row(String)
        /// A meeting header, carrying its recordings' row ids.
        case meeting([String])
    }
    var payload: Payload?
}

/// The base every cell here shares, and the one thing `NSTableCellView` is
/// genuinely needed for.
///
/// These cells hand-roll their layout — two labels and a stack is past what
/// `textField`/`imageView` model, and Mail and Xcode hand-roll multi-line rows
/// too. What they cannot hand-roll is the
/// `NSTableRowView.interiorBackgroundStyle → NSTableCellView.backgroundStyle`
/// forwarding chain, and it is load-bearing: every cell re-asserts semantic
/// colours (`.secondaryLabelColor`, `.systemOrange`, `.systemGreen`) on each
/// reload, which during a download fires at `didWriteData` cadence. On a
/// selected row that repaints grey-on-accent-blue — nowhere near 4.5:1 — for
/// the attendee line, both clocks, the size, the expiry and the status at once.
///
/// So colours are stored as *intent* and re-derived whenever the row's
/// emphasis changes, rather than assigned once and forgotten.
private class OutlineCellView: NSTableCellView {
    override var backgroundStyle: NSView.BackgroundStyle {
        didSet { applyBackgroundStyle() }
    }

    /// True when the row is drawn on an emphasised (key-window, selected)
    /// background, where semantic label colours are illegible.
    var isOnEmphasisedBackground: Bool { backgroundStyle == .emphasized }

    /// The colour to actually draw, given what the cell meant.
    func resolved(_ intent: NSColor) -> NSColor {
        guard isOnEmphasisedBackground else { return intent }
        // One colour on the selection pill, at two weights. The system draws
        // selected text this way; a `.systemGreen` tick on accent blue does not
        // become more legible for being green.
        return intent == .labelColor ? .alternateSelectedControlTextColor
                                     : .alternateSelectedControlTextColor.withAlphaComponent(0.75)
    }

    func applyBackgroundStyle() {}
}

private final class TickCellView: OutlineCellView {
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
        payload: RowCheckbox.Payload,
        state: NSControl.StateValue,
        enabled: Bool,
        label: String,
        reason: String?,
        target: AnyObject,
        action: Selector
    ) {
        checkbox.isHidden = false
        checkbox.payload = payload
        // Only a meeting header can be mixed, and only ever because we set it:
        // `allowsMixedState` would otherwise let a *click* cycle into mixed,
        // which is not a thing anyone means. Every state here is computed from
        // the store and written back, never read off the button.
        checkbox.allowsMixedState = (state == .mixed)
        checkbox.state = state
        checkbox.isEnabled = enabled
        checkbox.target = target
        checkbox.action = action
        // VoiceOver reads "Import recording 2, P05 Interview, checkbox" rather
        // than an unnamed control in an unnamed column.
        checkbox.setAccessibilityLabel(label)
        checkbox.toolTip = reason
        // The reason is the whole content for a held row, whose Status cell is
        // empty by design — so it has to reach VoiceOver too, not only hover.
        checkbox.setAccessibilityHelp(reason)
    }

    func configureEmpty() {
        checkbox.isHidden = true
        checkbox.payload = nil
        checkbox.target = nil
        checkbox.action = nil
        checkbox.toolTip = nil
    }
}

/// Title over optional subtitle. Every text column in the grid is this shape —
/// a moment over its length, a meeting over its people, a recording over
/// nothing.
private final class TwoLineCellView: OutlineCellView {
    private let title = NSTextField(labelWithString: "")
    private let subtitle = NSTextField(labelWithString: "")
    private let stack = NSStackView()
    private var leading: NSLayoutConstraint!

    /// What the cell *meant*, so `backgroundStyle` can re-derive what to draw.
    private var titleIntent: NSColor = .labelColor
    private var subtitleIntent: NSColor = .secondaryLabelColor

    var leadingInset: CGFloat = 0 {
        didSet { leading.constant = Metrics.cellInset + leadingInset }
    }

    var alignment: NSTextAlignment = .natural {
        didSet {
            title.alignment = alignment
            subtitle.alignment = alignment
            stack.alignment = alignment == .right ? .trailing : .leading
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

        stack.orientation = .vertical
        stack.spacing = 1
        stack.alignment = .leading
        stack.addArrangedSubview(title)
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

    override func applyBackgroundStyle() {
        title.textColor = resolved(titleIntent)
        subtitle.textColor = resolved(subtitleIntent)
    }

    func configure(
        title text: String,
        titleFont: NSFont = .systemFont(ofSize: Metrics.titleSize, weight: .semibold),
        subtitle detail: String?,
        titleColour: NSColor = .labelColor,
        accessibility: String? = nil
    ) {
        title.stringValue = text
        title.font = titleFont
        title.alignment = alignment
        subtitle.stringValue = detail ?? ""
        subtitle.isHidden = (detail ?? "").isEmpty
        titleIntent = titleColour
        subtitleIntent = .secondaryLabelColor
        applyBackgroundStyle()
        title.setAccessibilityLabel(accessibility)
    }

    /// A moment over how long it ran. Monospaced digits so the eye can compare
    /// down the column, which is the only thing anyone does with a time.
    func configureClock(at moment: Date?, length: TimeInterval?, notApplicable: String) {
        guard let moment else {
            configureDash(notApplicable)
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
    /// does not apply to this row" both read better as a mark than as a hole —
    /// on screen. In the accessibility tree it is the opposite: a meeting header
    /// announcing four em-dashes is noise, so the mark is named instead.
    func configureDash(_ notApplicable: String) {
        configure(
            title: "\u{2014}",
            titleFont: .systemFont(ofSize: Metrics.subtitleSize),
            subtitle: nil,
            titleColour: .tertiaryLabelColor,
            accessibility: notApplicable
        )
    }
}

/// Status is the one column whose content changes shape rather than value: a
/// determinate bar while bytes move, a sentence before and after.
private final class StatusCellView: OutlineCellView {
    private let label = NSTextField(labelWithString: "")
    private let glyph = NSImageView()
    private let bar = NSProgressIndicator()
    private let row = NSStackView()
    private var labelIntent: NSColor = .secondaryLabelColor

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        label.font = .systemFont(ofSize: Metrics.subtitleSize)
        label.lineBreakMode = .byTruncatingTail
        label.cell?.usesSingleLineMode = true

        glyph.imageScaling = .scaleProportionallyDown
        glyph.setContentHuggingPriority(.required, for: .horizontal)

        row.orientation = .horizontal
        row.spacing = 4
        row.alignment = .centerY
        row.addArrangedSubview(glyph)
        row.addArrangedSubview(label)
        row.translatesAutoresizingMaskIntoConstraints = false

        bar.isIndeterminate = false
        bar.style = .bar
        bar.minValue = 0
        bar.maxValue = 1
        bar.controlSize = .small
        bar.translatesAutoresizingMaskIntoConstraints = false

        addSubview(row)
        addSubview(bar)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Metrics.cellInset),
            row.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor,
                                          constant: -Metrics.cellInset),
            row.centerYAnchor.constraint(equalTo: centerYAnchor),
            bar.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Metrics.cellInset),
            bar.widthAnchor.constraint(equalToConstant: 70),
            bar.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("not from a nib") }

    override func applyBackgroundStyle() {
        label.textColor = resolved(labelIntent)
        glyph.contentTintColor = resolved(labelIntent)
    }

    /// - Parameter symbol: an SF Symbol name, not a character.
    ///
    ///   The success state was the string `"\u{2713} Imported"`, which
    ///   VoiceOver reads out as the name of the character. A glyph belongs in
    ///   an image view where it has a role and can be hidden from the
    ///   accessibility tree — `desktop/CLAUDE.md` § Native primitives first:
    ///   "SF Symbols / real file icons for glyphs".
    func configureText(_ text: String, colour: NSColor, bold: Bool, symbol: String? = nil) {
        bar.isHidden = true
        row.isHidden = false
        label.stringValue = text
        labelIntent = colour
        label.font = .systemFont(ofSize: Metrics.subtitleSize, weight: bold ? .semibold : .regular)
        glyph.image = symbol.flatMap {
            NSImage(systemSymbolName: $0, accessibilityDescription: nil)
        }
        glyph.isHidden = glyph.image == nil
        glyph.setAccessibilityElement(false)
        applyBackgroundStyle()
        // The whole sentence on hover, because a failure reason is exactly the
        // string that will not fit.
        label.toolTip = text
    }

    /// An indeterminate bar for the window between "the transfer started" and
    /// "the server told us how big it is" — a bar sitting at 0% for ten seconds
    /// reads as stalled.
    func configureProgress(_ fraction: Double?, name: String, i18n: I18n) {
        row.isHidden = true
        bar.isHidden = false
        bar.toolTip = nil
        // Without these the one state VoiceOver has least to say about — an
        // unknown-size transfer — is also unnamed.
        bar.setAccessibilityLabel(i18n.t("desktop.cloudImport.downloading", ["title": name]))
        if let fraction {
            if bar.isIndeterminate { bar.stopAnimation(nil); bar.isIndeterminate = false }
            bar.doubleValue = fraction
            bar.setAccessibilityValueDescription(
                i18n.t("desktop.cloudImport.downloadPercent", ["percent": String(Int(fraction * 100))]))
        } else if !bar.isIndeterminate {
            bar.isIndeterminate = true
            bar.setAccessibilityValueDescription(i18n.t("desktop.cloudImport.downloadStarting"))
            bar.startAnimation(nil)
        }
    }

    func configureEmpty() {
        bar.isHidden = true
        row.isHidden = false
        label.stringValue = ""
        label.toolTip = nil
        glyph.image = nil
        glyph.isHidden = true
    }
}
