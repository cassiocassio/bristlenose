import Foundation
import Testing

@testable import Bristlenose

// The rules behind the paywall. A view test would prove a sheet draws; these
// prove who is let through, which is the part that costs trust if it's wrong.

@Suite("Who may start an analysis")
struct SubscriptionAccessTests {

    private let id = SubscriptionAccess.monthlyProductID
    private let past = Date(timeIntervalSince1970: 1_000_000_000)
    private let future = Date(timeIntervalSince1970: 4_000_000_000)

    @Test("no entitlement, with the product loaded, means not subscribed")
    func noEntitlement() {
        let s = SubscriptionAccess.state(entitledProductIDs: [], expirations: [:], productLoaded: true)
        #expect(s == .notSubscribed)
    }

    @Test("no entitlement and no product: the store is unavailable, and Analyse is held")
    func storeDidNotAnswer() {
        let s = SubscriptionAccess.state(entitledProductIDs: [], expirations: [:], productLoaded: false)
        #expect(s == .storeUnavailable)
        #expect(!SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .developerID))
    }

    @Test("a paid person is subscribed even when the product did not load")
    func paidButOffline() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future], productLoaded: false)
        #expect(s == .subscribed(expires: future))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("an entitlement means subscribed")
    func entitled() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future], productLoaded: true)
        #expect(s == .subscribed(expires: future))
    }

    @Test("an entitlement with no expiry is still subscribed")
    func entitledNoExpiry() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [:], productLoaded: true)
        #expect(s == .subscribed(expires: nil))
    }

    @Test("billing grace: an entitlement whose period end has passed still lets them in")
    func gracePeriod() {
        // StoreKit keeps a grace-period subscription in currentEntitlements
        // while its transaction's expirationDate is already in the past.
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: past], productLoaded: true)
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("a free-trial entitlement is subscribed and marked as a trial")
    func trial() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future],
                                         trialProductIDs: [id], productLoaded: true)
        #expect(s == .subscribed(expires: future, inTrial: true))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("someone else's product does not count")
    func otherProduct() {
        let s = SubscriptionAccess.state(entitledProductIDs: ["something.else"], expirations: [:], productLoaded: true)
        #expect(s == .notSubscribed)
    }

    // MARK: Early adopters (owner, 22 Nov 2026)

    private let subscribed = SubscriptionAccess.State.subscribed(expires: nil)
    private let day: TimeInterval = 24 * 60 * 60
    /// 1 Jan 2027 and the deal's end, 20 Apr 2027, as the owner's example.
    private let jan = Date(timeIntervalSince1970: 1_798_761_600)
    private var dealEnds: Date { jan.addingTimeInterval(109 * day) }

    /// Monthly periods from `from`, back to back.
    private func months(_ n: Int, from: Date) -> [SubscriptionAccess.Period] {
        (0..<n).map { i in
            let start = from.addingTimeInterval(Double(i) * 30 * day)
            return .init(start: start, end: start.addingTimeInterval(30 * day))
        }
    }

    private func since(_ history: [SubscriptionAccess.Period],
                       state: SubscriptionAccess.State? = nil) -> Date? {
        SubscriptionAccess.earlyAdopterSince(state: state ?? subscribed, history: history,
                                             dealEnds: dealEnds)
    }

    @Test("no end date is chosen in this build")
    func noEndDateYet() {
        // Setting this is the act that ends the deal; it should be a
        // deliberate edit that also updates this test.
        #expect(SubscriptionAccess.earlyDealEnds == nil)
    }

    @Test("with no end date, every subscriber is an early adopter, trial included")
    func noDateEveryone() {
        let h = months(1, from: jan.addingTimeInterval(400 * day))
        #expect(SubscriptionAccess.earlyAdopterSince(state: .subscribed(expires: nil, inTrial: true),
                                                     history: h, dealEnds: nil) == h[0].start)
    }

    @Test("before the end date, every subscriber is an early adopter")
    func beforeTheDate() {
        let h = months(2, from: jan.addingTimeInterval(60 * day))
        #expect(since(h) == h[0].start)
    }

    @Test("after the end date, a run that began before it keeps the star, dated from its start")
    func continuousEarlyAdopter() {
        let h = months(12, from: jan)
        #expect(since(h) == jan)
    }

    @Test("after the end date, a newcomer gets no star")
    func newcomer() {
        let h = months(2, from: dealEnds)
        #expect(since(h) == nil)
    }

    @Test("a lapse of up to 60 days does not break the run, as Apple keeps the price")
    func shortLapse() {
        let early = months(3, from: jan)                     // ends 30 Mar
        let back = months(2, from: early.last!.end!.addingTimeInterval(59 * day))
        #expect(since(early + back) == jan)
    }

    @Test("a lapse of more than 60 days breaks the run: they came back at the new price")
    func longLapse() {
        let early = months(3, from: jan)
        let back = months(2, from: early.last!.end!.addingTimeInterval(61 * day))
        #expect(since(early + back) == nil)
    }

    @Test("overlapping periods: the run reaches as far as the furthest expiry, not the last one sorted")
    func overlappingPeriods() {
        // A long period, a short one inside it (a renewal charged early, a
        // replaced transaction), then a return 30 days after the long one.
        let h: [SubscriptionAccess.Period] = [
            .init(start: jan, end: jan.addingTimeInterval(100 * day)),
            .init(start: jan.addingTimeInterval(10 * day), end: jan.addingTimeInterval(20 * day)),
            .init(start: jan.addingTimeInterval(130 * day), end: jan.addingTimeInterval(160 * day)),
        ]
        #expect(since(h) == jan)
    }

    @Test("a period with no expiry counts as a moment, not as forever")
    func noExpiry() {
        let h: [SubscriptionAccess.Period] = [
            .init(start: jan, end: nil),
            .init(start: jan.addingTimeInterval(115 * day), end: jan.addingTimeInterval(145 * day)),
        ]
        #expect(since(h) == nil)
    }

    @Test("history order does not matter")
    func unsortedHistory() {
        let h = months(6, from: jan)
        #expect(since(h.reversed()) == jan)
    }

    @Test("someone not subscribed is never an early adopter, however long their history",
          arguments: [SubscriptionAccess.State.unknown, .notSubscribed, .storeUnavailable])
    func notSubscribedIsNotEarly(state: SubscriptionAccess.State) {
        let h = months(12, from: jan)
        #expect(since(h, state: state) == nil)
    }

    @Test("a subscriber with no history on record gets no date rather than a guess")
    func emptyHistory() {
        #expect(since([]) == nil)
    }

    @Test("on the App Store a lapsed subscriber cannot start an analysis")
    func lapsedBlocked() {
        #expect(!SubscriptionAccess.canStartAnalysis(.notSubscribed, channel: .appStoreOrTestFlight))
    }

    @Test("an unanswered store never locks anyone out")
    func unknownAllowed() {
        #expect(SubscriptionAccess.canStartAnalysis(.unknown, channel: .appStoreOrTestFlight))
    }

    @Test("a subscriber can start an analysis")
    func subscribedAllowed() {
        #expect(SubscriptionAccess.canStartAnalysis(.subscribed(expires: nil), channel: .appStoreOrTestFlight))
    }

    @Test("the dmg and debug builds are never gated, whatever the state")
    func otherChannelsUngated() {
        for state in [SubscriptionAccess.State.unknown, .notSubscribed, .subscribed(expires: nil)] {
            #expect(SubscriptionAccess.canStartAnalysis(state, channel: .developerID))
            #expect(SubscriptionAccess.canStartAnalysis(state, channel: .debug))
        }
    }

    @Test("a lapsed subscriber can still open their own projects")
    func readingAlwaysAllowed() {
        #expect(SubscriptionAccess.canOpenProjects(.notSubscribed, channel: .appStoreOrTestFlight))
    }

    // MARK: - The free trial, as the paywall says it

    @Test("a trial set in days or weeks is said in days; months and years are not")
    func trialDays() {
        #expect(SubscriptionAccess.trialDays(unit: .day, value: 7) == 7)
        #expect(SubscriptionAccess.trialDays(unit: .week, value: 1) == 7)
        #expect(SubscriptionAccess.trialDays(unit: .week, value: 2) == 14)
        #expect(SubscriptionAccess.trialDays(unit: .month, value: 1) == nil)
        #expect(SubscriptionAccess.trialDays(unit: .year, value: 1) == nil)
        #expect(SubscriptionAccess.trialDays(unit: .day, value: 0) == nil)
    }

    @Test("a month-long trial falls back to Foundation's words")
    func trialLengthFallback() {
        #expect(SubscriptionAccess.trialLength(unit: .month, value: 1, localeIdentifier: "en") == "1 month")
        #expect(SubscriptionAccess.trialLength(unit: .month, value: 0, localeIdentifier: "en") == nil)
    }

    /// The paywall's trial words come from the real locale files: in every
    /// language the app ships, a 1-, 3- and 7-day trial resolves to a phrase
    /// with the number in it, and the lines it is dropped into leave no
    /// placeholder behind. A missing key or plural stem falls back to English
    /// and would still pass those checks, so every line must also differ from
    /// its English rendering. Counts 1 and 3 reach the `_one` and `_few` stems.
    @MainActor @Test("every language words the trial and fills the sheet's lines in its own words")
    func trialWordedInEveryLanguage() {
        let locales = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("bristlenose/locales")
        let i18n = I18n()
        i18n.configure(localesDirectory: locales)

        func lines(_ count: Int) -> [String: String] {
            let days = i18n.plural("desktop.subscription.trialDays", count: count)
            var out = ["trialDays": days]
            for key in ["trialLead", "trialTerms"] {
                out[key] = i18n.t("desktop.subscription.\(key)", ["trial": days, "price": "£9.99"])
            }
            out["pricePerMonth"] = i18n.t("desktop.subscription.pricePerMonth", ["price": "£9.99"])
            return out
        }

        for count in [1, 3, 7] {
            i18n.setLocale("en")
            let english = lines(count)
            #expect(english["trialDays"] == (count == 1 ? "1 day" : "\(count) days"))
            for code in I18n.supportedLocales.sorted() {
                i18n.setLocale(code)
                for (key, line) in lines(count) {
                    #expect(line.contains("\(count)") || key == "pricePerMonth", "\(code) \(key): \(line)")
                    #expect(!line.contains("{{") && !line.contains("desktop.subscription"), "\(code) \(key): \(line)")
                    if code != "en" {
                        #expect(line != english[key], "\(code) \(key) fell back to English: \(line)")
                    }
                }
                // The templates too: a fallen-back English line filled with
                // this language's day word ("Free for the first 7 Tage") no
                // longer equals the English rendering, but its template does.
                if code != "en" {
                    for key in ["trialLead", "trialTerms", "pricePerMonth"] {
                        let template = i18n.t("desktop.subscription.\(key)")
                        i18n.setLocale("en")
                        let englishTemplate = i18n.t("desktop.subscription.\(key)")
                        i18n.setLocale(code)
                        #expect(template != englishTemplate, "\(code) \(key) fell back to English")
                    }
                }
            }
        }
    }
}

@Suite("Entitlements as the store reads them")
struct SubscriptionEntitlementTests {

    private let id = SubscriptionAccess.monthlyProductID
    private let now = Date(timeIntervalSince1970: 2_000_000_000)

    private func entitlement(expires: Date?) -> SubscriptionAccess.Entitlement {
        .init(productID: id, start: now.addingTimeInterval(-60), expires: expires, inTrial: false)
    }

    @Test("a verified purchase counts while the store's record does not list it yet")
    func purchaseCountsBeforeTheRecord() {
        let bought = entitlement(expires: now.addingTimeInterval(3600))
        #expect(SubscriptionAccess.including(bought, in: [], now: now) == [bought])
    }

    @Test("once the record lists the product, the purchase is not added twice")
    func recordWins() {
        let bought = entitlement(expires: now.addingTimeInterval(3600))
        let listed = entitlement(expires: now.addingTimeInterval(7200))
        #expect(SubscriptionAccess.including(bought, in: [listed], now: now) == [listed])
    }

    /// Review, 26 Nov 2026: one helper served both the store's record and a
    /// purchase taken ahead of it, and its expiry check dropped rows the store
    /// still lists, a billing grace period's among them, locking out a payer.
    @Test("a row the store's record lists counts whatever its expiry date says")
    func recordRowIsNotSecondGuessed() {
        // Against the real clock: the row's own date is an hour gone.
        let lapsedDate = Date().addingTimeInterval(-3600)
        let row = SubscriptionAccess.entitlement(productID: id, revoked: false, start: lapsedDate.addingTimeInterval(-86_400),
                                                 expires: lapsedDate, inTrial: false)
        #expect(row?.expires == lapsedDate)
        #expect(SubscriptionAccess.state(entitlements: [row].compactMap { $0 }, productLoaded: true)
                == .subscribed(expires: lapsedDate))
        #expect(SubscriptionAccess.entitlement(productID: id, revoked: true, start: now, expires: nil, inTrial: false) == nil)
        #expect(SubscriptionAccess.entitlement(productID: "other", revoked: false, start: now, expires: nil, inTrial: false) == nil)
    }

    @Test("a purchase past its own expiry counts for nothing")
    func expiredPurchase() {
        let old = entitlement(expires: now.addingTimeInterval(-1))
        #expect(SubscriptionAccess.including(old, in: [], now: now).isEmpty)
    }

    @Test("entitlements add up to the same states as before")
    func stateFromEntitlements() {
        let e = SubscriptionAccess.Entitlement(productID: id, start: now, expires: now, inTrial: true)
        #expect(SubscriptionAccess.state(entitlements: [e], productLoaded: false)
                == .subscribed(expires: now, inTrial: true))
        #expect(SubscriptionAccess.state(entitlements: [], productLoaded: true) == .notSubscribed)
        #expect(SubscriptionAccess.state(entitlements: [], productLoaded: false) == .storeUnavailable)
    }

    @Test("entitlements that fail verification are said in one log line, with their products")
    func unverifiedNotice() {
        let e = entitlement(expires: nil)
        let line = SubscriptionAccess.unverifiedNotice([
            .verified(e), .unverified(productID: id), .unverified(productID: "other"),
        ])
        #expect(line == "entitlements ignored, failed verification: count=2 products=\(id),other")
        #expect(SubscriptionAccess.unverifiedNotice([.verified(e)]) == nil)
        #expect(SubscriptionAccess.unverifiedNotice([]) == nil)
    }
}
