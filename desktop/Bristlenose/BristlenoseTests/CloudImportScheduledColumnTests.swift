import Foundation
import Testing

@testable import Bristlenose

// Whether the import grid draws a Scheduled column at all.
//
// The column is the visible half of a permission. `Calendars.Read` joined
// Microsoft's default app consent policy in Nov 2025, so on an ordinary
// corporate tenant a researcher who signs in gets recordings and no meetings —
// and a Scheduled column ruled down the page with nothing in it reads as a
// broken listing rather than as a scope the tenant declined. Meet reaches the
// same state by a different road (a month of instant meetings), which is why
// the rule is about the data and never about the platform.
//
// Scope: the rule, not the AppKit column set. What the researcher notices is
// "an empty column that should not be there" and "a column that went away while
// it still had something in it" — those are both decided here.

@Suite("Scheduled column")
struct CloudImportScheduledColumnTests {

    private let moment = Date(timeIntervalSince1970: 1_755_000_000)

    private func row(_ id: String, scheduled: Date?) -> CloudImportRow {
        CloudImportRow(
            id: id,
            title: "P0\(id) Interview",
            startsAt: moment,
            duration: 2400,
            sizeBytes: nil,
            expiresAt: nil,
            attendees: [],
            localState: .notImported,
            video: .available,
            roster: .available,
            transcript: .available,
            organiser: nil,
            scheduledAt: scheduled,
            // An unscheduled row is the honest Meet case; the Teams
            // scope-declined case leaves this false and is otherwise identical,
            // which is the point — the rule cannot tell them apart and does not
            // try.
            isUnscheduled: scheduled == nil
        )
    }

    /// The window-B outcome, and the reason this exists.
    ///
    /// A tenant that refused the calendar sends back recordings with no
    /// bookings. Every Scheduled cell would be an em-dash, in a column the same
    /// width as the full one beside it.
    @Test("A listing with no scheduled times drops the column entirely")
    func nothingScheduledDropsIt() {
        let rows = (1...4).map { row("\($0)", scheduled: nil) }
        #expect(!CloudImportOutline.showsScheduledColumn(for: rows))
    }

    /// The failure direction that matters more, because it hides real data
    /// rather than showing empty space: one booked call among the ad-hoc ones
    /// still has a time worth reading, and losing the column loses it.
    @Test("One scheduled row among unscheduled ones keeps the column")
    func oneScheduledRowKeepsIt() {
        var rows = (1...5).map { row("\($0)", scheduled: nil) }
        rows.append(row("6", scheduled: moment.addingTimeInterval(-3600)))
        #expect(CloudImportOutline.showsScheduledColumn(for: rows))
    }

    @Test("An ordinary scheduled listing keeps the column")
    func scheduledListingKeepsIt() {
        let rows = (1...3).map { row("\($0)", scheduled: moment.addingTimeInterval(-3600)) }
        #expect(CloudImportOutline.showsScheduledColumn(for: rows))
    }

    /// Nothing listed is not evidence that nothing was scheduled.
    ///
    /// The window shows its columns before the first listing lands, so dropping
    /// this one on the empty state and restoring it a moment later is jitter
    /// with no information in it — and it would happen on every sign-in.
    @Test("An empty listing keeps the column rather than flickering it")
    func emptyListingKeepsIt() {
        #expect(CloudImportOutline.showsScheduledColumn(for: []))
    }
}
