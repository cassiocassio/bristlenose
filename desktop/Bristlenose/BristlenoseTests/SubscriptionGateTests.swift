import Foundation
import Testing
@testable import Bristlenose

@MainActor
@Suite("Subscription wiring")
struct SubscriptionGateTests {

    private func project() -> Project {
        Project(id: UUID(), name: "Study", path: "/tmp/study")
    }

    @Test("a .dmg, a debug build and the CLI channel never get a store")
    func noStoreOffTheAppStore() {
        #expect(SubscriptionStore.make(channel: .developerID) == nil)
        #expect(SubscriptionStore.make(channel: .debug) == nil)
        let g = SubscriptionGate(channel: .developerID)
        #expect(g.store == nil)
        #expect(g.allowsStart(project: project(), clean: false, researcherAsked: true))
        #expect(g.pending == nil)
    }

    /// `purchase()` and `restore()` reach Apple's real store from a test host
    /// and put an Apple Account sign-in window on the developer's screen
    /// (25 Nov 2026). Pinned by the flag, not by calling them: calling them is
    /// the thing that must never happen here.
    @Test("under a test host the store refuses the calls that ask for an Apple Account")
    func testHostNeverPromptsSignIn() {
        #expect(SubscriptionStore.refusesSignInPrompts)
    }

    @Test("the debug seed switches the channel only in a debug build")
    func debugSeed() {
        let on = ["BRISTLENOSE_DEBUG_SUBSCRIPTION": "1"]
        #expect(SubscriptionGate.effectiveChannel(.debug, environment: on) == .appStoreOrTestFlight)
        #expect(SubscriptionGate.effectiveChannel(.debug, environment: [:]) == .debug)
        #expect(SubscriptionGate.effectiveChannel(.developerID, environment: on) == .developerID)
        #expect(SubscriptionGate.effectiveChannel(.appStoreOrTestFlight, environment: [:]) == .appStoreOrTestFlight)
    }

    @Test("not subscribed on the App Store: a researcher's Analyse raises the paywall")
    func notSubscribedRaisesPaywall() {
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .notSubscribed))
        let p = project()
        #expect(!g.allowsStart(project: p, clean: true, researcherAsked: true))
        #expect(g.pending?.project.id == p.id)
        #expect(g.pending?.clean == true)
    }

    @Test("store unreachable and never subscribed: the paywall opens in its try-again state")
    func unavailableRaisesPaywall() {
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .storeUnavailable))
        #expect(!g.allowsStart(project: project(), clean: false, researcherAsked: true))
        #expect(g.pending != nil)
    }

    @Test("an automatic start is held quietly, with no sheet")
    func automaticStartShowsNothing() {
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .notSubscribed))
        #expect(!g.allowsStart(project: project(), clean: false, researcherAsked: false))
        #expect(g.pending == nil)
    }

    @Test("subscribed, in a trial, or store unanswered: the run starts")
    func passes() {
        for state: SubscriptionAccess.State in [.subscribed(expires: nil), .subscribed(expires: nil, inTrial: true), .unknown] {
            let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: state))
            #expect(g.allowsStart(project: project(), clean: false, researcherAsked: true))
        }
    }

    @Test("subscribing resumes exactly the study that was waiting, once")
    func resumes() {
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .notSubscribed))
        var started: [(UUID, Bool)] = []
        g.resume = { started.append(($0.id, $1)) }
        let p = project()
        _ = g.allowsStart(project: p, clean: false, researcherAsked: true)
        g.resumePending()
        g.resumePending()
        #expect(started.count == 1)
        #expect(started.first?.0 == p.id)
        #expect(g.pending == nil)
    }

    @Test("Not Now drops the request and starts nothing")
    func notNow() {
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .notSubscribed))
        var started = 0
        g.resume = { _, _ in started += 1 }
        _ = g.allowsStart(project: project(), clean: false, researcherAsked: true)
        g.dismissPaywall()
        g.resumePending()
        #expect(started == 0)
    }

    /// Review, 25 Nov 2026: with no product the offer read "/month" with no
    /// price and a Subscribe that could not be pressed.
    @Test("with no product the sheet shows the store-unavailable face, never a blank offer")
    func noProductIsUnavailable() {
        typealias F = PaywallView.Face
        #expect(F.of(.notSubscribed, productLoaded: false) == .unavailable)
        #expect(F.of(.unknown, productLoaded: false) == .unavailable)
        #expect(F.of(.storeUnavailable, productLoaded: true) == .unavailable)
        #expect(F.of(.notSubscribed, productLoaded: true) == .offer)
    }

    @Test("the paywall's legal links are the ones the listing carries")
    func legalLinks() {
        #expect(PaywallView.termsURL.absoluteString == "https://bristlenose.app/terms.html")
        #expect(PaywallView.privacyURL.absoluteString == "https://bristlenose.app/privacy.html")
    }

    @Test("the StoreKit test file carries the product the code asks for")
    func storeKitConfigMatches() throws {
        let file = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Bristlenose.storekit")
        let json = try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as? [String: Any]
        let groups = json?["subscriptionGroups"] as? [[String: Any]] ?? []
        let subs = groups.flatMap { $0["subscriptions"] as? [[String: Any]] ?? [] }
        let sub = try #require(subs.first { $0["productID"] as? String == SubscriptionAccess.monthlyProductID })
        #expect(sub["recurringSubscriptionPeriod"] as? String == "P1M")
        let intro = sub["introductoryOffer"] as? [String: Any]
        #expect(intro?["paymentMode"] as? String == "free")
        #expect(intro?["subscriptionPeriod"] as? String == "P1W")
    }

    @Test("a run that the gate holds never starts: the runner changes no state")
    func runnerHonoursTheGate() {
        let runner = PipelineRunner(
            hasConsent: { true },
            keyReadiness: { .present(provider: "anthropic", key: "k") }
        )
        let g = SubscriptionGate(channel: .appStoreOrTestFlight, store: SubscriptionStore(frozenAt: .notSubscribed))
        runner.subscriptionGate = g
        let p = Project(id: UUID(), name: "Study", path: "/tmp/study")
        runner.start(project: p)
        #expect(g.pending?.project.id == p.id)
        #expect(runner.state[p.id] == nil)
    }

    // MARK: - Which window shows the paywall

    /// 25 Nov 2026: presenting the sheet made it the key window, the parent
    /// reported not-key, and a "show only while I am key" getter dismissed the
    /// sheet it had just shown, again and again.
    @Test("the window showing the sheet keeps it when it stops being key")
    func sheetSurvivesTheParentLosingKey() {
        let g = SubscriptionGate(channel: .developerID)
        let a = UUID()
        g.pending = .init(project: project(), clean: false)
        #expect(g.paywall(for: a, isKey: true) != nil)
        #expect(g.paywall(for: a, isKey: false) != nil)
        #expect(g.paywall(for: a, isKey: true) != nil)
    }

    @Test("a window that is not key does not start showing the sheet")
    func backgroundWindowDoesNotStart() {
        let g = SubscriptionGate(channel: .developerID)
        g.pending = .init(project: project(), clean: false)
        #expect(g.paywall(for: UUID(), isKey: false) == nil)
    }

    @Test("two windows never stack two sheets")
    func secondWindowDoesNotStack() {
        let g = SubscriptionGate(channel: .developerID)
        let a = UUID(), b = UUID()
        g.pending = .init(project: project(), clean: false)
        #expect(g.paywall(for: a, isKey: true) != nil)
        #expect(g.paywall(for: b, isKey: true) == nil)
    }

    @Test("once dismissed, the next paywall goes to whichever window is key")
    func claimReleasedOnDismiss() {
        let g = SubscriptionGate(channel: .developerID)
        let a = UUID(), b = UUID()
        g.pending = .init(project: project(), clean: false)
        _ = g.paywall(for: a, isKey: true)
        g.dismissPaywall()
        #expect(g.paywall(for: a, isKey: true) == nil)
        g.pending = .init(project: project(), clean: false)
        #expect(g.paywall(for: b, isKey: true) != nil)
        #expect(g.paywall(for: a, isKey: true) == nil)
    }
}
