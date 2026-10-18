import Foundation
import Testing

@testable import Bristlenose

// Whether the import grid draws an Expires column at all.
//
// The Scheduled column's rule, applied to the expiry date: a column appears
// when it would have something in it. Zoom gives a date only when the account
// deletes recordings automatically, so an account with retention off listed a
// column of dashes beside every meeting — a column we could never fill, since
// no scope or extra call yields a date that does not exist (18 Oct 2026, the
// first live Pro listing).

@Suite("Expires column")
struct CloudImportExpiresColumnTests {

    private let moment = Date(timeIntervalSince1970: 1_755_000_000)

    private func row(_ id: String, expires: Date?) -> CloudImportRow {
        CloudImportRow(
            id: id,
            title: "P0\(id) Interview",
            startsAt: moment,
            duration: 2400,
            sizeBytes: nil,
            expiresAt: expires,
            attendees: [],
            localState: .notImported,
            video: .available,
            roster: .available,
            transcript: .available,
            organiser: nil
        )
    }

    @Test("A listing with no expiry dates drops the column")
    func noDatesDropsIt() {
        let rows = (1...3).map { row("\($0)", expires: nil) }
        #expect(!CloudImportOutline.showsExpiresColumn(on: .zoom, for: rows))
    }

    @Test("One dated row keeps the column")
    func oneDateKeepsIt() {
        var rows = (1...3).map { row("\($0)", expires: nil) }
        rows.append(row("4", expires: moment.addingTimeInterval(7 * 86_400)))
        #expect(CloudImportOutline.showsExpiresColumn(on: .zoom, for: rows))
        #expect(CloudImportOutline.showsExpiresColumn(on: .teams, for: rows))
    }

    @Test("A platform with no per-file expiry never shows it")
    func meetNeverShowsIt() {
        let rows = [row("1", expires: moment)]
        #expect(!CloudImportOutline.showsExpiresColumn(on: .meet, for: rows))
    }
}
