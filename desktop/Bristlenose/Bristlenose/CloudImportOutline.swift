import Foundation

// The import list as a hierarchy: days, meetings, recordings.
//
// Pure values and one pure function. No AppKit, no store, no network — per
// `desktop/CLAUDE.md` § Testing, "if a SwiftUI view is making a decision, the
// decision belongs in a testable helper". Every judgement the grid makes about
// what nests under what, what a day is called, and what the footer may claim is
// made here and asserted in `CloudImportOutlineTests`.
//
// Design: docs/mockups/cloud-import-recordings-grid.html (the settled shape) and
// docs/mockups/cloud-import-three-platforms.html (why the same shape means
// different things on Zoom).
//
// HIG, verbatim, and the reason this is an outline rather than a flat table:
// "Use an outline view instead of a table view to present hierarchical data",
// and "expose data hierarchy in the first column only."

enum CloudImportOutline {

    // MARK: - What a node is

    /// A day header. Floats at the top of the scroll while its rows pass under
    /// it — `NSOutlineView.floatsGroupRows`, which is the whole reason this is
    /// an AppKit outline and not a SwiftUI `Table` (which has no group rows at
    /// all).
    struct Day: Equatable {
        /// Midnight of the day, in the current calendar. The grouping key.
        let start: Date
        /// "Today" / "Yesterday" / "Wed 13 Aug".
        let label: String
    }

    /// A call that owns more than one recording. Context only — it has no file
    /// behind it, so it draws no checkbox and can never be fetched.
    ///
    /// A call with exactly one recording does **not** produce one of these: it
    /// collapses into a single `.recording` node carrying both clocks, which is
    /// the overwhelmingly common case and the one the design refuses to make
    /// people expand a triangle to read.
    struct Meeting: Equatable {
        let id: String
        let title: String
        let attendees: [CloudImportRow.Attendee]
        let organiser: CloudImportRow.Attendee?
        let scheduledAt: Date?
        let scheduledDuration: TimeInterval?
        /// How many recordings hang under it. Always ≥ 2 by construction.
        let recordingCount: Int
    }

    /// One recording — the fetchable unit — or one meeting nobody recorded.
    struct Recording: Equatable {
        let row: CloudImportRow

        /// 1-based position among its meeting's recordings, or nil when this
        /// row *is* the meeting.
        ///
        /// The nil case is doing the real work: it means the row shows the
        /// title, the attendee line and both clocks, because there is no parent
        /// row above it to carry them. A non-nil ordinal means the row is a
        /// child and shows only what distinguishes it from its siblings — which
        /// is when it was recorded, for how long, and how big.
        let ordinal: Int?

        var isChild: Bool { ordinal != nil }

        // NOT here, deliberately: an "ad hoc" badge for a recording with no
        // calendar event behind it.
        //
        // The mockup draws one, and it is the right design — an instant
        // meeting's dash in the Scheduled column should read as "there was
        // never anything scheduled" rather than as data we failed to find. But
        // no adapter can currently tell those two apart. A missing
        // `scheduledAt` means "no event" on Meet *and* "the researcher declined
        // the calendar scope" on Teams, so a badge inferred from it would be a
        // false claim on every row of a scope-declined Teams list — and the
        // researcher's remedy (re-consent) is the opposite of what it implies.
        //
        // It lands with ad-hoc *listing*, which is the same piece of work:
        // Meet's list is event-first, so a call started from the Meet home
        // screen produces a Drive recording this window never shows at all
        // (verified live, 16 Aug 2026). When the adapter can emit such a row it
        // knows for a fact there was no event, and the badge follows from that
        // fact rather than from an absence.
    }

    /// What a row in the outline is.
    ///
    /// An enum, deliberately, and this is the one piece of shape that is here
    /// for a future platform rather than a present one. When Zoom is unparked,
    /// its children are not separate sessions — they are one session rendered
    /// four ways (speaker view, gallery view, shared screen, audio only) — and
    /// a `.rendition` case added here makes the compiler point at every switch
    /// that has to tell "two interviews" from "the same 45 minutes twice".
    /// A protocol or a `kind: String` would let that land silently, which on
    /// this feature means a study analysing four copies of one participant.
    enum Kind: Equatable {
        case day(Day)
        case meeting(Meeting)
        case recording(Recording)
    }

    /// One item in the outline, as `NSOutlineView` wants it: a reference type,
    /// so the view can hold it, with **equality and hash keyed on `id` alone**.
    ///
    /// That last part is load-bearing rather than incidental. The tree is
    /// rebuilt from scratch on every store change — a filter keystroke, a
    /// progress tick — and `NSOutlineView` matches its retained items against
    /// the new ones by `isEqual:`. With default `NSObject` identity every
    /// rebuild produces all-new objects, so **every expansion collapses and the
    /// selection is lost on each keystroke** — which reads as the outline
    /// fighting the user rather than as an identity bug.
    final class Node: NSObject {
        let id: String
        let kind: Kind
        let children: [Node]

        init(id: String, kind: Kind, children: [Node] = []) {
            self.id = id
            self.kind = kind
            self.children = children
        }

        override func isEqual(_ object: Any?) -> Bool {
            guard let other = object as? Node else { return false }
            return other.id == id
        }

        override var hash: Int { id.hashValue }

        /// The row behind this node, when there is one. Days and meeting
        /// headers have none — which is exactly why neither can be ticked.
        var row: CloudImportRow? {
            if case .recording(let recording) = kind { return recording.row }
            return nil
        }
    }

    // MARK: - The result

    /// The tree plus the three numbers the footer is allowed to state.
    ///
    /// They are computed here, from the same pass that builds the tree, so the
    /// footer cannot drift from the list. §6's honest-batch requirement is that
    /// the arithmetic be checkable against what is on screen — a count derived
    /// somewhere else is exactly how it stops being.
    struct Result: Equatable {
        let days: [Node]
        /// Calls shown. An ad-hoc recording counts as one: it *was* a meeting,
        /// it just wasn't in anybody's calendar.
        let meetings: Int
        /// Rows with a file behind them. A meeting nobody recorded contributes
        /// zero.
        let recordings: Int
        /// Rows that can actually be ticked right now.
        let fetchable: Int
        /// Whether some recording the researcher can *see* is one they cannot
        /// *fetch*, for a reason at the other end — the condition that earns
        /// the "About recordings permissions" link, and nothing else does.
        ///
        /// **Not `fetchable < recordings`**, which is the arithmetic that looks
        /// equivalent and is not: it counts an already-imported file, an iCloud
        /// placeholder and an unmounted drive as withholding, so a returning
        /// researcher gets a remote-permissions link because they succeeded
        /// last week. See `CloudImportRow.isWithheld`.
        let withholding: Bool

        static let empty = Result(days: [], meetings: 0, recordings: 0,
                                  fetchable: 0, withholding: false)

        var isEmpty: Bool { days.isEmpty }
    }

    // MARK: - Building it

    /// Group rows into days → meetings → recordings.
    ///
    /// **Days descend, rows within a day ascend.** Newest day first, because
    /// the researcher opened this to find last week; chronological inside the
    /// day, because that is how a diary reads and how the two interviews that
    /// share a Wednesday relate to each other. Photos does exactly this; Mail
    /// does not, and Mail is the wrong comparable — a mailbox has no inherent
    /// order within a day, a schedule does.
    ///
    /// - Parameter now: injected so day labels are deterministic under test. A
    ///   fixture whose headers drift with the wall clock stops being a fixture.
    static func build(
        rows: [CloudImportRow],
        now: Date = Date(),
        calendar: Calendar = .current
    ) -> Result {
        guard !rows.isEmpty else { return .empty }

        // 1 — gather rows into calls. A row with no `meetingID` is its own
        //     call: an ad-hoc recording is a meeting that nobody scheduled, not
        //     an orphan to be swept into a bucket with other people's orphans.
        var order: [String] = []
        var groups: [String: [CloudImportRow]] = [:]
        for row in rows {
            // Both sides namespaced, so a `meetingID` that happens to read like
            // a synthesised key cannot collide with one. The namespace is free
            // and the alternative is an argument about how unlikely a Graph id
            // is to start with "row:".
            let key = row.meetingID.map { "mtg:\($0)" } ?? "row:\(row.id)"
            if groups[key] == nil { order.append(key) }
            groups[key, default: []].append(row)
        }

        // 2 — one node per call, anchored on the clock the call belongs to.
        struct Entry { let anchor: Date; let node: Node }
        var entries: [Entry] = []

        var meetingCount = 0, recordingCount = 0, fetchableCount = 0, withheld = false

        for key in order {
            guard let members = groups[key], !members.isEmpty else {
                // Unreachable by construction — `order` gains a key only in the
                // branch that immediately appends a row to it. Loud rather than
                // silent because this is the one loop where a dropped key is a
                // dropped meeting, and the whole hazard of this feature is that
                // a shorter list looks exactly like a quieter month.
                assertionFailure("a grouping key with no rows: \(key)")
                continue
            }
            // Chronological within the call: "Recording 1" is the one that
            // happened first, which is the only ordering a person would guess.
            let sorted = members.sorted { $0.startsAt < $1.startsAt }
            let lead = sorted[0]
            // Everything about the call is read from `lead` — never from input
            // order. Identical today, because siblings share one event on both
            // adapters; free to make true, and it removes the question.
            //
            // The call's own moment is when it was *booked* if it was booked at
            // all, so a meeting and its recordings never straddle a day header
            // just because someone hit record after midnight.
            let anchor = lead.scheduledAt ?? lead.startsAt

            // Counted from what is about to be built, not from the input array.
            // The footer's claim is that it is checkable against the list, and
            // a count taken from a different set is exactly how that stops
            // being true — including when a duplicate id means two rows arrive
            // and only one can be drawn.
            meetingCount += 1
            for row in sorted {
                if row.hasRecording { recordingCount += 1 }
                if row.isSelectable { fetchableCount += 1 }
                if row.isWithheld { withheld = true }
            }

            if sorted.count == 1 {
                entries.append(Entry(
                    anchor: anchor,
                    node: Node(id: "rec:\(lead.id)",
                               kind: .recording(Recording(row: lead, ordinal: nil)))
                ))
            } else {
                let children = sorted.enumerated().map { index, row in
                    Node(id: "rec:\(row.id)",
                         // The adapter's own ordinal wins. Position is the
                         // fallback for a source that doesn't set one — and it
                         // is only a fallback because siblings can share an
                         // exact `startsAt`, which makes their sorted order
                         // arbitrary rather than merely unspecified.
                         kind: .recording(Recording(row: row,
                                                    ordinal: row.siblingOrdinal ?? index + 1)))
                }
                let meeting = Meeting(
                    id: key,
                    title: lead.title,
                    attendees: lead.attendees,
                    organiser: lead.organiser,
                    scheduledAt: lead.scheduledAt,
                    scheduledDuration: lead.scheduledDuration,
                    recordingCount: children.count
                )
                entries.append(Entry(
                    anchor: anchor,
                    node: Node(id: "meeting:\(key)", kind: .meeting(meeting), children: children)
                ))
            }
        }

        // 3 — days, newest first; entries inside a day, oldest first.
        var byDay: [Date: [Entry]] = [:]
        for entry in entries {
            byDay[calendar.startOfDay(for: entry.anchor), default: []].append(entry)
        }
        let days = byDay.keys.sorted(by: >).map { dayStart -> Node in
            let sorted = (byDay[dayStart] ?? []).sorted { $0.anchor < $1.anchor }
            return Node(
                id: "day:\(dayStart.timeIntervalSinceReferenceDate)",
                kind: .day(Day(start: dayStart,
                               label: dayLabel(for: dayStart, now: now, calendar: calendar))),
                children: sorted.map(\.node)
            )
        }

        return Result(
            days: days,
            meetings: meetingCount,
            recordings: recordingCount,
            fetchable: fetchableCount,
            withholding: withheld
        )
    }

    /// A fingerprint of everything the cells draw *from the tree*.
    ///
    /// Two jobs, and the second is the one that isn't obvious.
    ///
    /// The obvious one: skip a full `reloadData()` when nothing structural
    /// moved, so a download's progress ticks don't collapse every disclosure
    /// triangle several times a second.
    ///
    /// The load-bearing one: `reloadData(forRowIndexes:columnIndexes:)` does
    /// **not** re-ask the data source for items — it re-requests views for the
    /// items AppKit already holds. Since `Node` equality is keyed on id alone,
    /// a rebuilt node with the same id never swaps in, so every cell reading
    /// `node.kind` would render the *previous* listing's values indefinitely.
    /// Making this fingerprint content-sensitive is what forces the full
    /// reload — the only path that re-asks — whenever a rendered value changes.
    /// Store-derived state (progress, outcomes, ticks) is deliberately absent:
    /// those cells read the store directly and are refreshed by the cheap path.
    static func fingerprint(of result: Result) -> [String] {
        result.days.flatMap { day -> [String] in
            var out = [day.id + "|" + label(of: day)]
            for node in day.children {
                out.append(node.id + "|" + signature(of: node))
                out.append(contentsOf: node.children.map { $0.id + "|" + signature(of: $0) })
            }
            return out
        }
    }

    private static func label(of node: Node) -> String {
        if case .day(let day) = node.kind { return day.label }
        return ""
    }

    private static func signature(of node: Node) -> String {
        switch node.kind {
        case .day(let day):
            return day.label
        case .meeting(let meeting):
            return [meeting.title,
                    meeting.scheduledAt.map(String.init(describing:)) ?? "",
                    meeting.scheduledDuration.map(String.init(describing:)) ?? "",
                    String(meeting.recordingCount),
                    meeting.attendees.map(\.listLabel).joined(separator: ",")]
                .joined(separator: "|")
        case .recording(let recording):
            let row = recording.row
            // Built by appending rather than as one literal: the array-literal
            // form of this tripped "unable to type-check this expression in
            // reasonable time", which is SwiftUI's classic complaint arriving
            // in a plain function.
            var parts: [String] = [row.title]
            parts.append(recording.ordinal.map(String.init) ?? "")
            parts.append(row.scheduledAt.map(String.init(describing:)) ?? "")
            parts.append(row.recordedAt.map(String.init(describing:)) ?? "")
            parts.append(row.duration.map(String.init(describing:)) ?? "")
            parts.append(row.sizeBytes.map(String.init) ?? "")
            parts.append(row.expiresAt.map(String.init(describing:)) ?? "")
            parts.append(row.statusLabel ?? "")
            parts.append(String(row.showsCheckbox))
            parts.append(String(row.isSelectable))
            parts.append(row.attendees.map(\.listLabel).joined(separator: ","))
            return parts.joined(separator: "|")
        }
    }

    /// "Today" / "Yesterday" / "Wed 13 Aug" / "Wed 13 Aug 2025".
    ///
    /// The weekday is there because a study is scheduled across a week or two
    /// and *Wednesday* is how a researcher holds that — "the second one, the
    /// Wednesday" is a real sentence people say about their own fieldwork.
    ///
    /// The year appears only when it differs from the current one — Finder and
    /// Mail's rule. Eleven months of the year it is noise; across the New Year
    /// it is essential.
    ///
    /// "Today" and "Yesterday" are English literals rather than a relative
    /// `DateFormatter`, and that is the same debt the rest of this window
    /// carries (see `CloudCount`): cloud import is not localised yet, so the
    /// header would otherwise read "Aujourd'hui" above a window titled "Import
    /// from Google Meet". The dated form goes through the system formatter,
    /// which is free and gets weekday-and-month ordering right per locale
    /// whatever happens to the rest.
    static func dayLabel(for date: Date, now: Date, calendar: Calendar) -> String {
        if calendar.isDate(date, inSameDayAs: now) { return "Today" }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now),
           calendar.isDate(date, inSameDayAs: yesterday) {
            return "Yesterday"
        }
        var style = Date.FormatStyle.dateTime.weekday(.abbreviated).day().month(.abbreviated)
        if calendar.component(.year, from: date) != calendar.component(.year, from: now) {
            style = style.year()
        }
        return date.formatted(style)
    }
}
