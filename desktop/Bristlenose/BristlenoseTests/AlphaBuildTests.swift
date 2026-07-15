import Foundation
import Testing
@testable import Bristlenose

/// Covers the pure expiry core (`AlphaBuild.expiry` / `isExpired` /
/// `daysRemaining` taking explicit dates). The channel-aware wrappers read the
/// generated build constant + compilation flag, which aren't controllable from
/// a unit test, so they're exercised via the pure core the wrappers delegate to.
@Suite struct AlphaBuildTests {

    private func day(_ y: Int, _ m: Int, _ d: Int) -> Date {
        var c = DateComponents()
        c.year = y; c.month = m; c.day = d; c.hour = 12
        c.timeZone = TimeZone(identifier: "UTC")
        return Calendar(identifier: .gregorian).date(from: c)!
    }

    @Test func expiryIsBuildDatePlusValidityDays() {
        let built = day(2026, 7, 14)
        let expiry = AlphaBuild.expiry(forBuildDate: built, validityDays: 30)
        #expect(expiry == AlphaBuild.expiry(forBuildDate: built)) // default is 30
        let expected = Calendar.current.date(byAdding: .day, value: 30, to: built)!
        #expect(expiry == expected)
    }

    @Test func notExpiredBeforeTheWindowCloses() {
        let built = day(2026, 7, 14)
        #expect(!AlphaBuild.isExpired(buildDate: built, asOf: built)) // build day
        #expect(!AlphaBuild.isExpired(buildDate: built, asOf: day(2026, 8, 1))) // ~18 days
        #expect(!AlphaBuild.isExpired(buildDate: built, asOf: day(2026, 8, 12))) // day 29
    }

    @Test func expiredOnAndAfterTheThirtiethDay() {
        let built = day(2026, 7, 14)
        let expiry = AlphaBuild.expiry(forBuildDate: built)
        #expect(AlphaBuild.isExpired(buildDate: built, asOf: expiry)) // boundary is inclusive
        #expect(AlphaBuild.isExpired(buildDate: built, asOf: day(2026, 9, 1)))
    }

    @Test func daysRemainingCountsDown() {
        let built = day(2026, 7, 14)
        #expect(AlphaBuild.daysRemaining(buildDate: built, asOf: built) == 30)
        #expect(AlphaBuild.daysRemaining(buildDate: built, asOf: day(2026, 8, 13)) == 0)
        // Past expiry goes negative — callers treat <= 0 as expired.
        #expect(AlphaBuild.daysRemaining(buildDate: built, asOf: day(2026, 8, 20)) < 0)
    }

    @Test func validityDaysIsThirty() {
        #expect(AlphaBuild.validityDays == 30)
    }
}
