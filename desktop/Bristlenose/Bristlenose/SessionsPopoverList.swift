import AppKit
import SwiftUI

// MARK: - Table configuration

/// Configure a table as the sessions popover's source list. Extracted so the
/// postconditions are unit-testable on a bare `NSTableView` — the failure modes
/// here are SILENTLY INERT, not wrong: any `rowSizeStyle` other than `.custom`
/// pins a fixed height and **never calls** the height delegate (no error — the
/// height work is simply dead, a documented trap that already cost a QA round
/// on the sidebar), and without the source-list pair the capsule isn't drawn.
func configureSourceListTable(_ table: NSTableView) {
    table.style = .sourceList
    // `style = .sourceList` alone renders the *emphasized* vivid-blue selection;
    // the deprecated-but-functional property is what yields the unemphasized
    // capsule — same pairing, same reason, as ProjectSidebarOutline.
    table.selectionHighlightStyle = .sourceList
    table.rowSizeStyle = .custom
    table.headerView = nil
    table.allowsMultipleSelection = false
    table.allowsEmptySelection = true
    table.focusRingType = .none
    table.backgroundColor = .clear
    table.intercellSpacing = NSSize(width: 0, height: 0)
    if table.tableColumns.isEmpty {
        table.addTableColumn(NSTableColumn(identifier: .init("session")))
    }
}

// MARK: - Row model

/// Everything a row renders, precomputed once per data load so cell configure
/// stays a dumb assignment and the localised strings (title, placeholder,
/// duration, date) arrive from the caller — this file never touches `I18n`.
struct SessionsPopoverRow {
    let session: SessionsPopoverSpec.Session
    let title: String          // localised "Session 6" / "Interview 6"
    let subtitle: String       // "26m · 10 Feb 2026, 09:12"
    let placeholder: String    // localised unnamed-participant word
    let typeSelect: String     // SessionsPopoverSpec.typeSelectString
    let accessibility: String  // SessionsPopoverSpec.accessibilityLabel
}

// MARK: - NSViewRepresentable

/// The popover's session list — a real `NSTableView(style: .sourceList)` inside
/// an `NSScrollView`, because the selection capsule is internal to the table
/// and a hand-placed view cannot draw it (see `SourceListSelectionRowView`).
///
/// Interaction is the CHOOSER model, decided in the design doc §Interaction:
/// single click commits and dismisses; arrows move the selection highlight
/// only; Return/Space commits; Escape dismisses unchanged. **Navigation never
/// happens from `tableViewSelectionDidChange`** — that is the seductive wrong
/// place, and would fire seven WKWebView loads on a keyboard user arrowing to
/// row 8.
struct SessionsPopoverList: NSViewRepresentable {
    let rows: [SessionsPopoverRow]
    let activeSessionID: String?
    let onCommit: (SessionsPopoverSpec.Session) -> Void
    let onCancel: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(rows: rows, onCommit: onCommit, onCancel: onCancel)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let table = SessionsPopoverTableView()
        configureSourceListTable(table)
        table.dataSource = context.coordinator
        table.delegate = context.coordinator
        table.target = context.coordinator
        table.action = #selector(Coordinator.rowClicked(_:))
        table.commitHandler = { [weak coordinator = context.coordinator] in
            coordinator?.commitSelectedRow()
        }
        table.cancelHandler = onCancel

        let scroll = NSScrollView()
        scroll.documentView = table
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.verticalScrollElasticity = .allowed

        context.coordinator.table = table
        context.coordinator.selectActive(id: activeSessionID)
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        context.coordinator.update(rows: rows,
                                   onCommit: onCommit,
                                   onCancel: onCancel,
                                   activeID: activeSessionID)
    }

    // MARK: Coordinator

    @MainActor
    final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate {
        private(set) var rows: [SessionsPopoverRow]
        private var onCommit: (SessionsPopoverSpec.Session) -> Void
        private var onCancel: () -> Void
        weak var table: NSTableView?

        /// Pinned COLUMN widths, measured across the whole list so badges and
        /// titles align down every row — the decided "pin the column, not the
        /// chip" rule: a 3-digit code widens the shared column rather than
        /// ragging one row's title.
        private(set) var badgeColumnWidth: CGFloat = 0
        private(set) var titleColumnWidth: CGFloat = 0

        init(rows: [SessionsPopoverRow],
             onCommit: @escaping (SessionsPopoverSpec.Session) -> Void,
             onCancel: @escaping () -> Void) {
            self.rows = rows
            self.onCommit = onCommit
            self.onCancel = onCancel
            super.init()
            measureColumns()
        }

        func update(rows: [SessionsPopoverRow],
                    onCommit: @escaping (SessionsPopoverSpec.Session) -> Void,
                    onCancel: @escaping () -> Void,
                    activeID: String?) {
            self.rows = rows
            self.onCommit = onCommit
            self.onCancel = onCancel
            measureColumns()
            table?.reloadData()
            selectActive(id: activeID)
        }

        /// Select the current session and scroll it into view, so the first
        /// arrow press moves relative to where the user IS — the sidebar's
        /// auto-scroll behaviour, which the plan review flagged as easy to lose.
        func selectActive(id: String?) {
            guard let table,
                  let id,
                  let index = rows.firstIndex(where: { $0.session.sessionID == id })
            else { return }
            table.selectRowIndexes(IndexSet(integer: index), byExtendingSelection: false)
            table.scrollRowToVisible(index)
        }

        private func measureColumns() {
            badgeColumnWidth = rows
                .flatMap { $0.session.participants }
                .map { SpeakerBadgeView.width(for: $0.code) }
                .max() ?? SpeakerBadgeView.width(for: "p1")
            let font = SessionRowCellView.titleFont
            titleColumnWidth = rows
                .map { NSAttributedString(string: $0.title, attributes: [.font: font]).size().width }
                .max().map { ceil($0) } ?? 0
        }

        // MARK: Data source / delegate

        func numberOfRows(in tableView: NSTableView) -> Int { rows.count }

        func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? {
            SessionsPopoverHoverRowView()
        }

        func tableView(_ tableView: NSTableView, heightOfRow row: Int) -> CGFloat {
            // NOTE: `heightOfRow`, not the outline's `heightOfRowByItem` — a
            // plain NSTableView never calls the latter (plan-review Finding 4).
            SessionsPopoverSpec.rowHeight(participantCount: rows[row].session.participants.count)
        }

        func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
            let id = NSUserInterfaceItemIdentifier("session-row")
            let cell = tableView.makeView(withIdentifier: id, owner: nil) as? SessionRowCellView
                ?? SessionRowCellView(identifier: id)
            cell.configure(with: rows[row],
                           badgeColumnWidth: badgeColumnWidth,
                           titleColumnWidth: titleColumnWidth)
            return cell
        }

        func tableView(_ tableView: NSTableView, typeSelectStringFor tableColumn: NSTableColumn?, row: Int) -> String? {
            rows[row].typeSelect
        }

        /// Token-level matching: the DEFAULT matcher is anchored-prefix, which
        /// only reaches the leading name. This is what makes "p6" and
        /// "session 6" land (SessionsPopoverSpec.typeSelectMatches, tested).
        func tableView(_ tableView: NSTableView,
                       nextTypeSelectMatchFromRow startRow: Int,
                       toRow endRow: Int,
                       for searchString: String) -> Int {
            // AppKit's contract is [startRow, endRow) *with wrap* — endRow may
            // be less than startRow, and equal bounds mean one full sweep, not
            // an empty range (a plain `while row != endRow` exits immediately
            // on the equal case and type-select silently finds nothing).
            guard !rows.isEmpty,
                  (0..<rows.count).contains(startRow),
                  (0..<rows.count).contains(endRow) else { return -1 }
            var row = startRow
            repeat {
                if SessionsPopoverSpec.typeSelectMatches(search: searchString,
                                                         candidate: rows[row].typeSelect) {
                    return row
                }
                row = (row + 1) % rows.count
            } while row != endRow
            return -1
        }

        // MARK: Commit

        @objc func rowClicked(_ sender: Any?) {
            guard let table, table.clickedRow >= 0, table.clickedRow < rows.count else { return }
            onCommit(rows[table.clickedRow].session)
        }

        func commitSelectedRow() {
            guard let table, table.selectedRow >= 0, table.selectedRow < rows.count else { return }
            onCommit(rows[table.selectedRow].session)
        }
    }
}

// MARK: - Hover row view

/// Menu-style pointer tracking for the popover's rows.
///
/// A source-list TABLE doesn't hover (Finder and Mail never do), and the plan
/// originally accepted no-hover on that ground — reversed 14 Aug 2026 on the
/// role argument: **the container's idiom wins over the control's.** This
/// surface behaves as a menu (transient, light-dismiss, click-commits), and
/// Apple's menus and popover choosers track the pointer; the table is an
/// implementation detail chosen for the selection capsule.
///
/// The wash is the popover FAMILY's hover — `labelColor` at 6%, the same value
/// `ExportPopoverRow` and the All Sessions row above hand-roll — deliberately
/// NOT the menu's accent capsule, which would collide with the grey capsule
/// the control draws for the *current* session and fork the hover vocabulary
/// inside one surface. Hovering the current row composites slightly darker.
///
/// A SUBCLASS of the shared row view so the project sidebar — a genuine source
/// list that must not hover — is untouched, and the capsule anti-drift
/// guarantee is inherited rather than duplicated.
final class SessionsPopoverHoverRowView: SourceListSelectionRowView {

    private var hovered = false {
        didSet { if hovered != oldValue { needsDisplay = true } }
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        for area in trackingAreas where area.owner === self {
            removeTrackingArea(area)
        }
        // .activeAlways: a popover's window is key, but tracking must survive
        // the brief non-key moments during presentation.
        addTrackingArea(NSTrackingArea(
            rect: .zero,
            options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
            owner: self
        ))
    }

    override func mouseEntered(with event: NSEvent) { hovered = true }
    override func mouseExited(with event: NSEvent) { hovered = false }

    override func drawBackground(in dirtyRect: NSRect) {
        super.drawBackground(in: dirtyRect)
        guard hovered else { return }
        // Same side inset the source-list capsule uses, so hover and selection
        // read as one shape at two weights (the mockup's decided treatment).
        let wash = bounds.insetBy(dx: 10, dy: 0)
        NSColor.labelColor.withAlphaComponent(0.06).setFill()
        NSBezierPath(roundedRect: wash, xRadius: 6, yRadius: 6).fill()
    }
}

// MARK: - Table subclass

/// Keyboard half of the chooser contract, plus the two responder-chain steps
/// SwiftUI does not perform for hosted AppKit content:
///
/// - **First responder by hand** — `.popover` presents an `NSHostingView` and
///   nothing in that chain hands focus to an embedded table; without this,
///   arrows and type-select silently do nothing while the popover looks
///   correct (precedent: `ProjectSidebarOutline.swift` does the same after
///   inline rename).
/// - **Explicit `cancelOperation`** — Tab cycles *inside* a popover's key-view
///   loop, so Escape is the only exit and must not depend on responder-chain
///   luck surviving somebody's future `keyDown` override.
final class SessionsPopoverTableView: NSTableView {
    var commitHandler: (() -> Void)?
    var cancelHandler: (() -> Void)?

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard window != nil else { return }
        DispatchQueue.main.async { [weak self] in
            guard let self, let window = self.window else { return }
            window.makeFirstResponder(self)
        }
    }

    override func keyDown(with event: NSEvent) {
        switch event.charactersIgnoringModifiers {
        case "\r", "\u{3}", " ":   // Return, keypad Enter, Space — commit
            commitHandler?()
        default:
            super.keyDown(with: event)
        }
    }

    override func cancelOperation(_ sender: Any?) {
        cancelHandler?()
    }
}

// MARK: - Cell

/// One session row: `[badge] [Session N] [name]` on a shared three-column
/// grid, subtitle under the name column. Single and multi-participant rows are
/// structurally the same shape — the multi case has one name line per
/// participant, badges aligned to the NAMES (not the top of the margin, which
/// would put `p6` level with "Session 6" and reintroduce the very
/// session-number/participant-number conflation dropping `#N` removed).
final class SessionRowCellView: NSTableCellView {

    static let titleFont = NSFont.systemFont(ofSize: 13)           // SwiftUI .body on macOS
    static let nameFont = NSFont.systemFont(ofSize: 13)
    static let subtitleFont = NSFont.systemFont(ofSize: 10)        // SwiftUI .caption
    /// The system's italic for the unnamed placeholder — the "PowerPoint title"
    /// convention (`person-badge.css .unnamed`): muted colour alone does not
    /// survive palettes where muted is chromatic; the italic is the
    /// palette-independent half of the cue.
    static var placeholderFont: NSFont {
        NSFontManager.shared.convert(nameFont, toHaveTrait: .italicFontMask)
    }

    private var grid: NSGridView?
    /// Fields that take the accent on the selected row — the localised title
    /// and the REAL names. The unnamed placeholder stays secondary italic
    /// (accent italic would claim it's a name), and the subtitle stays
    /// secondary.
    private var selectionTintedTitles: [NSTextField] = []
    private var selectionTintedNames: [NSTextField] = []

    convenience init(identifier: NSUserInterfaceItemIdentifier) {
        self.init(frame: .zero)
        self.identifier = identifier
    }

    /// Selected row → accent title + names, matching the project sidebar's
    /// grey-capsule-plus-accent-content treatment (decision #2 of
    /// `design-native-colour-alignment.md`, and the web `.session-entry.active`).
    /// The sidebar gets this FREE because it wires the `NSTableCellView`
    /// outlets and "the system tints icon + label via `backgroundStyle`
    /// (selected → accent, else label)" — our fields are grid children, so we
    /// respond to the same signal by hand rather than inventing a parallel
    /// selection channel. Accent tracks the user's system accent on Default
    /// (`.controlAccentColor`), Edo's Prussian via `SidebarPalette`.
    override var backgroundStyle: NSView.BackgroundStyle {
        didSet { applySelectionTint() }
    }

    private func applySelectionTint() {
        let selected = backgroundStyle == .emphasized
        let accent = SidebarPalette.accent(fallback: .controlAccentColor) ?? .controlAccentColor
        for field in selectionTintedTitles {
            field.textColor = selected ? accent : .secondaryLabelColor
        }
        for field in selectionTintedNames {
            field.textColor = selected ? accent : .labelColor
        }
    }

    func configure(with row: SessionsPopoverRow,
                   badgeColumnWidth: CGFloat,
                   titleColumnWidth: CGFloat) {
        grid?.removeFromSuperview()
        selectionTintedTitles = []
        selectionTintedNames = []

        let participants = row.session.participants
        var gridRows: [[NSView]] = []

        func empty() -> NSView { NSGridCell.emptyContentView }
        func titleField() -> NSTextField {
            let f = NSTextField(labelWithString: row.title)
            f.font = Self.titleFont
            f.textColor = .secondaryLabelColor
            f.lineBreakMode = .byTruncatingTail
            selectionTintedTitles.append(f)
            return f
        }
        func nameField(_ p: SessionsPopoverSpec.Participant) -> NSTextField {
            let f = NSTextField(labelWithString: p.name ?? row.placeholder)
            f.font = p.name == nil ? Self.placeholderFont : Self.nameFont
            f.textColor = p.name == nil ? .secondaryLabelColor : .labelColor
            f.lineBreakMode = .byTruncatingTail
            if p.name != nil { selectionTintedNames.append(f) }
            return f
        }
        func subtitleField() -> NSTextField {
            let f = NSTextField(labelWithString: row.subtitle)
            f.font = Self.subtitleFont
            f.textColor = .secondaryLabelColor
            f.lineBreakMode = .byTruncatingTail
            return f
        }

        if participants.count <= 1 {
            let badge: NSView = participants.first.map { SpeakerBadgeView(code: $0.code) } ?? empty()
            let name: NSView = participants.first.map { nameField($0) } ?? empty()
            gridRows.append([badge, titleField(), name])
            gridRows.append([empty(), empty(), subtitleField()])
        } else {
            gridRows.append([empty(), titleField(), empty()])
            for p in participants {
                gridRows.append([SpeakerBadgeView(code: p.code), empty(), nameField(p)])
            }
            gridRows.append([empty(), empty(), subtitleField()])
        }

        let g = NSGridView(views: gridRows)
        g.translatesAutoresizingMaskIntoConstraints = false
        g.columnSpacing = 10                                  // ExportPopoverRow's gap
        g.rowSpacing = ProjectCellSpec.titleToSubtitle
        g.column(at: 0).width = badgeColumnWidth
        g.column(at: 1).width = titleColumnWidth
        g.column(at: 0).xPlacement = .leading
        g.column(at: 1).xPlacement = .leading
        g.column(at: 2).xPlacement = .leading
        g.rowAlignment = .firstBaseline

        addSubview(g)
        NSLayoutConstraint.activate([
            g.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 12),
            g.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor, constant: -12),
            g.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        grid = g

        // One composed element per row: left to AppKit, a grid serialises in
        // its own (often column-major) order — "p6 p7 p8 Session 6 Beth …" —
        // destroying the badge↔name pairing the layout exists to convey. The
        // composed label (from the MODEL, so truncation never reaches the
        // spoken form) is the only non-visual carrier of that pairing.
        setAccessibilityElement(true)
        setAccessibilityRole(.staticText)
        setAccessibilityLabel(row.accessibility)
        hideDescendantsFromAccessibility(g)

        // Reused cells arrive with whatever backgroundStyle their previous row
        // had — re-apply against the fresh field arrays.
        applySelectionTint()
    }

    private func hideDescendantsFromAccessibility(_ view: NSView) {
        for sub in view.subviews {
            sub.setAccessibilityElement(false)
            hideDescendantsFromAccessibility(sub)
        }
    }
}

// MARK: - Badge

/// The speaker-code chip — the SHAPE of the web `.badge` atom (mono, 11pt, 3pt
/// radius, min-width for `pN`), with colours from the SYSTEM, not the CSS
/// palette (`SidebarPalette.Concept.badgeBackground` doc explains why).
/// `quaternaryLabelColor` is translucent, so on the selection capsule the chip
/// composites slightly darker instead of reading as a lighter chip-in-a-chip
/// (light) or a punched hole (dark) — the artefact the review confirmed
/// against opaque ported hexes.
final class SpeakerBadgeView: NSView {

    static let font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
    private static let horizontalInset: CGFloat = 5
    private static let verticalInset: CGFloat = 2
    private static let minTextWidth: CGFloat = 12

    /// Rendered width for a code — used by the coordinator to pin the shared
    /// badge COLUMN to the widest code in the list.
    static func width(for code: String) -> CGFloat {
        let text = NSAttributedString(string: code, attributes: [.font: font]).size().width
        return ceil(max(text, minTextWidth)) + horizontalInset * 2
    }

    private let label: NSTextField

    init(code: String) {
        label = NSTextField(labelWithString: code)
        super.init(frame: .zero)
        label.font = Self.font
        label.textColor = SidebarPalette.nsColor(.badgeText)
        label.alignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: centerXAnchor),
            label.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        wantsLayer = true
        layer?.cornerRadius = 3                               // --bn-radius-sm
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override var intrinsicContentSize: NSSize {
        NSSize(width: Self.width(for: label.stringValue),
               height: ceil(label.intrinsicContentSize.height) + Self.verticalInset * 2)
    }

    /// `NSGridView`'s `.firstBaseline` row alignment consults this, and a plain
    /// `NSView` reports no baseline — so the grid fell back to edge placement
    /// and the chip sat visibly below the text beside it (QA screenshot,
    /// 14 Aug 2026). The label is centred inside `verticalInset`, so its
    /// baseline offset from our top is exact.
    override var firstBaselineOffsetFromTop: CGFloat {
        Self.verticalInset + label.firstBaselineOffsetFromTop
    }

    override var wantsUpdateLayer: Bool { true }

    /// Resolve the dynamic NSColor here, not at init: a CALayer background is a
    /// static CGColor snapshot, and `updateLayer` re-runs with the correct
    /// effective appearance on every light↔dark change (the PaletteTintView
    /// lesson, without needing the manual forwarding — this view draws nothing
    /// else).
    override func updateLayer() {
        layer?.backgroundColor = SidebarPalette.nsColor(.badgeBackground).cgColor
    }
}
