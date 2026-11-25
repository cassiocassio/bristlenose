import CryptoKit
import Foundation
import Testing

@testable import Bristlenose

// The fetcher's I/O shell, against a URLProtocol stub through the production
// session shape (`CloudNetworking.makeSession` + `RefuseRedirects`). The stub
// records every request, so "no request" is asserted, not assumed.

@Suite("NewsFetcher", .serialized)
@MainActor
struct NewsFetcherTests {
    typealias K = NewsTestKit

    /// Answers with the armed reply and records what it was asked. Its own
    /// static state (not `StubURLProtocol`'s), and the suite is serialised.
    final class NewsStub: URLProtocol {
        struct Reply {
            var status = 200
            var headers: [String: String] = ["Content-Type": "application/json"]
            var body = Data()
            var location: String?
            var fail = false
            var delay: TimeInterval = 0
        }
        nonisolated(unsafe) static var reply = Reply()
        nonisolated(unsafe) static var requests: [URLRequest] = []
        private static let lock = NSLock()

        static func arm(_ reply: Reply) {
            lock.lock(); defer { lock.unlock() }
            self.reply = reply
        }
        static func reset() {
            lock.lock(); defer { lock.unlock() }
            reply = Reply(); requests = []
        }
        static var seen: [URLRequest] { lock.lock(); defer { lock.unlock() }; return requests }

        override class func canInit(with request: URLRequest) -> Bool { true }
        override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
        override func stopLoading() {}
        override func startLoading() {
            Self.lock.lock()
            Self.requests.append(request)
            let reply = Self.reply
            Self.lock.unlock()
            // A delay blocks this loader thread only: enough to hold a request in flight.
            if reply.delay > 0 { Thread.sleep(forTimeInterval: reply.delay) }
            do {
                guard let url = request.url else { return }
                if reply.fail {
                    client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
                    return
                }
                var headers = reply.headers
                if let location = reply.location { headers["Location"] = location }
                let response = HTTPURLResponse(url: url, statusCode: reply.status,
                                               httpVersion: "HTTP/1.1", headerFields: headers)!
                if let location = reply.location, let next = URL(string: location) {
                    client?.urlProtocol(self, wasRedirectedTo: URLRequest(url: next),
                                        redirectResponse: response)
                }
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: reply.body)
                client?.urlProtocolDidFinishLoading(self)
            }
        }
    }

    final class Clock: @unchecked Sendable { var now = NewsTestKit.date(2026, 12, 12) }
    /// Every session a test makes, invalidated at clean-up (a session retains
    /// its delegate until then: the `CloudNetworking` convention).
    final class Sessions: @unchecked Sendable { var all: [URLSession] = [] }

    let k1 = Curve25519.Signing.PrivateKey()
    let k0 = Curve25519.Signing.PrivateKey()
    let suite = "news-tests-\(UUID().uuidString)"
    let defaults: UserDefaults
    let clock = Clock()
    let sessions = Sessions()

    init() {
        defaults = UserDefaults(suiteName: suite)!
        NewsStub.reset()
    }

    private func fetcher(answered: Bool = true, managed: Set<String> = [],
                         endpoint: URL? = NewsCheck.productionEndpoint,
                         channel: NewsCheck.Channel? = .store,
                         keyring: NewsCheck.Keyring? = nil,
                         subscription: @escaping @MainActor () -> SubscriptionAccess.State? = { nil },
                         subscriptionWait: TimeInterval = 20) -> NewsFetcher {
        let clock = self.clock
        let session = CloudNetworking.makeSession(delegate: LLMValidator.RefuseRedirects(),
                                                  protocolClasses: [NewsStub.self])
        sessions.all.append(session)
        return NewsFetcher(world: .init(
            defaults: defaults,
            session: session,
            endpoint: endpoint,
            policy: .init(keyring: keyring ?? K.keyring(["k1": k1, "k0": k0]), requiredEnv: "prod"),
            channel: channel,
            appVersion: "0.47.0",
            keys: .production,
            interfaceLanguage: { "en" },
            firstRunAnswered: { answered },
            isManaged: { managed.contains($0) },
            now: { clock.now },
            timeout: 5,
            timeZone: { TimeZone(identifier: "UTC")! },
            subscription: subscription,
            subscriptionWait: subscriptionWait))
    }

    private func armFile(_ payload: Data? = nil, date: Date? = nil, key: Curve25519.Signing.PrivateKey? = nil,
                         kid: String = "k1") {
        NewsStub.arm(.init(
            headers: ["Content-Type": "application/json",
                      "Date": K.httpDate(date ?? clock.now)],
            body: K.envelope(payload ?? K.payload(), key: key ?? k1, kid: kid)))
    }

    private func query(_ index: Int = 0) -> [String: String] {
        let url = NewsStub.seen[index].url!
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        return Dictionary(uniqueKeysWithValues: items.map { ($0.name, $0.value ?? "") })
    }

    private func cleanUp() {
        defaults.removePersistentDomain(forName: suite)
        sessions.all.forEach { $0.invalidateAndCancel() }
        sessions.all = []
    }

    // MARK: Switches and gates

    @Test("News off: zero requests, and the cached file is deleted")
    func newsOffSendsNothing() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        #expect(await f.checkIfDue() == .accepted)
        #expect(!f.items.isEmpty)
        NewsStub.reset()
        defaults.set(false, forKey: NewsPreferences.enabledKey)
        clock.now = K.date(2026, 12, 13)
        #expect(await f.checkIfDue() == .newsOff)
        f.newsSwitchChanged()
        #expect(NewsStub.seen.isEmpty)
        #expect(defaults.data(forKey: NewsStateKeys.production.envelope) == nil)
        #expect(f.items.isEmpty)
        f.recordWelcomeShown()
        #expect(NewsStub.seen.isEmpty)
    }

    @Test("A managed news switch forced off sends nothing; first-run unanswered sends nothing")
    func gates() async {
        defer { cleanUp() }
        defaults.set(false, forKey: NewsPreferences.enabledKey)
        #expect(await fetcher(managed: [NewsPreferences.enabledKey]).checkIfDue() == .newsOff)
        defaults.removeObject(forKey: NewsPreferences.enabledKey)
        #expect(await fetcher(answered: false).checkIfDue() == .firstRunUnanswered)
        #expect(await fetcher(endpoint: nil).checkIfDue() == .noEndpoint)
        #expect(NewsStub.seen.isEmpty)
    }

    @Test("No trusted key: no request at all, with counts on and a file waiting")
    func noKeysNoRequest() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        armFile()
        // The production placeholders today: both keys empty.
        let empty = NewsCheck.Keyring(base64Keys: ["k1": "", "k0": ""], backupKID: "k0")
        let f = fetcher(keyring: empty)
        f.recordWelcomeShown()
        #expect(await f.checkIfDue() == .noKeys)
        // Waited as long as a request that did happen would take to be recorded.
        try? await Task.sleep(nanoseconds: 300_000_000)
        #expect(NewsStub.seen.isEmpty)
        // The flags were not spent: nothing reached a log.
        #expect(defaults.object(forKey: NewsStateKeys.production.lastCheck) == nil)
        #expect(!defaults.bool(forKey: NewsStateKeys.production.everChecked))
    }

    @Test("Counting not answered, or no: the request carries no flags",
          arguments: [nil, false] as [Bool?])
    func countsOffNoFlags(consent: Bool?) async {
        defer { cleanUp() }
        if let consent { defaults.set(consent, forKey: NewsPreferences.countsKey) }
        let f = fetcher()
        f.recordWelcomeShown()
        armFile()
        _ = await f.checkIfDue()
        #expect(NewsStub.seen.count == 1)
        #expect(NewsStub.seen[0].url?.absoluteString == "https://bristlenose.app/app/news?s=1")
    }

    @Test("No yes to counts: no version anywhere in the request, and a plain User-Agent",
          arguments: [nil, false] as [Bool?])
    func noVersionWithoutYes(consent: Bool?) async {
        defer { cleanUp() }
        if let consent { defaults.set(consent, forKey: NewsPreferences.countsKey) }
        armFile()
        _ = await fetcher().checkIfDue()
        #expect(NewsStub.seen.count == 1)
        let request = NewsStub.seen[0]
        #expect(request.value(forHTTPHeaderField: "User-Agent") == "Bristlenose")
        #expect(request.url?.absoluteString.contains("0.47.0") == false)
        for (name, value) in request.allHTTPHeaderFields ?? [:] {
            #expect(!value.contains("0.47"), "header \(name) carries the version")
        }
    }

    @Test("A managed counts key sends no flags, even if it says yes")
    func managedCountsSendNoFlags() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        armFile()
        _ = await fetcher(managed: [NewsPreferences.countsKey]).checkIfDue()
        #expect(query() == ["s": "1"])
    }

    @Test("With a yes: the flags, an explicit User-Agent, an empty Accept-Language, GET")
    func countsYes() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        f.recordWelcomeShown(); f.recordWelcomeShown()
        armFile()
        #expect(await f.checkIfDue() == .accepted)
        let request = NewsStub.seen[0]
        #expect(request.url?.absoluteString
                == "https://bristlenose.app/app/news?s=1&v=0.47.0&ch=store&first=1&month=1&w=2")
        #expect(request.httpMethod == "GET")
        #expect(request.value(forHTTPHeaderField: "User-Agent") == "Bristlenose/0.47.0")
        #expect(request.value(forHTTPHeaderField: "Accept-Language") == "")
        #expect(request.value(forHTTPHeaderField: "Cookie") == nil)
    }

    // MARK: Once a day, single flight, the server's clock

    @Test("At most once per server-UTC day; the next day sends no first or month")
    func oncePerDay() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        armFile()
        _ = await f.checkIfDue()
        clock.now = K.date(2026, 12, 12, 23, 59)
        #expect(await f.checkIfDue() == .notDue)
        #expect(NewsStub.seen.count == 1)
        clock.now = K.date(2026, 12, 13, 0, 1)
        armFile()
        _ = await f.checkIfDue()
        #expect(NewsStub.seen.count == 2)
        #expect(query(1)["first"] == nil && query(1)["month"] == nil && query(1)["w"] == "0")
    }

    @Test("lastCheck comes from the server's Date header, not the Mac's clock")
    func serverClock() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        clock.now = K.date(2025, 12, 12)  // the Mac is a year slow
        let f = fetcher()
        armFile(date: K.date(2026, 12, 12))
        #expect(await f.checkIfDue() == .accepted)  // the file's dates are judged by the server
        #expect(defaults.object(forKey: NewsStateKeys.production.lastCheck) as? Date == K.date(2026, 12, 12))
        clock.now = K.date(2026 - 1, 12, 12, 18)
        #expect(await f.checkIfDue() == .notDue)
    }

    @Test("Two checks at once make one request")
    func singleFlight() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        var reply = NewsStub.reply
        reply.delay = 0.3
        NewsStub.arm(reply)
        async let a = f.checkIfDue()
        async let b = f.checkIfDue()
        let outcomes = await [a, b]
        #expect(outcomes.contains(.alreadyInFlight))
        #expect(outcomes.contains(.accepted))
        #expect(NewsStub.seen.count == 1)
    }

    // MARK: Flags: transport failure keeps them, any response spends them

    @Test("A transport failure keeps the flags for the next try")
    func transportFailureKeepsFlags() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        f.recordWelcomeShown()
        NewsStub.arm(.init(fail: true))
        #expect(await f.checkIfDue() == .transportFailure)
        clock.now = clock.now.addingTimeInterval(NewsFetcher.transportBackoff + 60)
        armFile()
        #expect(await f.checkIfDue() == .accepted)
        #expect(NewsStub.seen.count == 2)
        #expect(query(1)["first"] == "1" && query(1)["month"] == "1" && query(1)["w"] == "1")
    }

    @Test("After a transport failure, no retry in this process for 30 minutes")
    func transportFailureBacksOff() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        NewsStub.arm(.init(fail: true))
        #expect(await f.checkIfDue() == .transportFailure)
        armFile()
        // Activation after activation (Cmd-Tab) while offline: nothing is sent.
        clock.now = clock.now.addingTimeInterval(60)
        #expect(await f.checkIfDue() == .backingOff)
        clock.now = clock.now.addingTimeInterval(NewsFetcher.transportBackoff - 120)
        #expect(await f.checkIfDue() == .backingOff)
        #expect(NewsStub.seen.count == 1)
        // Once the backoff has passed, one try, still carrying the kept flags.
        clock.now = clock.now.addingTimeInterval(120)
        #expect(await f.checkIfDue() == .accepted)
        #expect(NewsStub.seen.count == 2)
        #expect(query(1)["first"] == "1")
    }

    @Test("News switched off while the request is out: nothing is cached, the floor stays")
    func switchedOffInFlight() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        var reply = NewsStub.reply
        reply.delay = 0.3
        NewsStub.arm(reply)
        async let outcome = f.checkIfDue()
        // Let the request leave, then switch news off while it is held.
        let deadline = Date().addingTimeInterval(2)
        while NewsStub.seen.isEmpty && Date() < deadline {
            try? await Task.sleep(nanoseconds: 10_000_000)
        }
        defaults.set(false, forKey: NewsPreferences.enabledKey)
        f.newsSwitchChanged()
        #expect(await outcome == .newsOff)
        #expect(NewsStub.seen.count == 1)
        #expect(defaults.data(forKey: NewsStateKeys.production.envelope) == nil)
        #expect(defaults.object(forKey: NewsStateKeys.production.maxIssued) == nil)
        #expect(defaults.data(forKey: NewsStateKeys.production.maxIssuedDigest) == nil)
        #expect(f.items.isEmpty)
        #expect(f.currentItems().isEmpty)
    }

    @Test("A 404 spends the flags")
    func notFoundSpendsFlags() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        NewsStub.arm(.init(status: 404, headers: ["Date": K.httpDate(clock.now)]))
        #expect(await f.checkIfDue() == .notAFile(status: 404))
        clock.now = K.date(2026, 12, 13)
        armFile()
        _ = await f.checkIfDue()
        #expect(query(1)["first"] == nil)
        #expect(f.items.count == 1)
    }

    // MARK: Days opened and subscription (v3)

    /// A first check on 12 Dec (accepted), so the next month's check is not `first`.
    private func afterFirstCheck(_ f: NewsFetcher) async {
        armFile()
        #expect(await f.checkIfDue() == .accepted)
        #expect(query(0)["first"] == "1" && query(0)["days"] == nil)
    }

    @Test("days: each local day once, sent on the next month's check, then spent")
    func daysEndToEnd() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        f.recordAppOpened()
        await afterFirstCheck(f)
        for (day, hour) in [(12, 18), (14, 9), (14, 20), (20, 12)] {
            clock.now = K.date(2026, 12, day, hour)
            f.recordAppOpened()
        }
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.daysOpened)
                == ["2026-12-12", "2026-12-14", "2026-12-20"])
        clock.now = K.date(2027, 1, 3)
        f.recordAppOpened()
        armFile(K.payload(issued: K.date(2026, 12, 20), expires: K.date(2027, 1, 20)))
        #expect(await f.checkIfDue() == .accepted)
        #expect(query(1)["month"] == "1" && query(1)["days"] == "3")
        #expect(query(1)["sub"] == nil)
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.daysOpened) == ["2027-01-03"])
    }

    @Test("days survive a transport failure and go with the next try")
    func daysKeptOnTransportFailure() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        await afterFirstCheck(f)
        clock.now = K.date(2026, 12, 15); f.recordAppOpened()
        clock.now = K.date(2027, 1, 2); f.recordAppOpened()
        NewsStub.arm(.init(fail: true))
        #expect(await f.checkIfDue() == .transportFailure)
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.daysOpened)
                == ["2026-12-15", "2027-01-02"])
        clock.now = clock.now.addingTimeInterval(NewsFetcher.transportBackoff + 60)
        armFile(K.payload(issued: K.date(2026, 12, 20), expires: K.date(2027, 1, 20)))
        #expect(await f.checkIfDue() == .accepted)
        #expect(query(2)["month"] == "1" && query(2)["days"] == "1")
    }

    @Test("A 404 on the month check spends the days too")
    func daysSpentOnAnyResponse() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        let f = fetcher()
        await afterFirstCheck(f)
        clock.now = K.date(2026, 12, 15); f.recordAppOpened()
        clock.now = K.date(2027, 1, 2)
        NewsStub.arm(.init(status: 404, headers: ["Date": K.httpDate(clock.now)]))
        #expect(await f.checkIfDue() == .notAFile(status: 404))
        #expect(query(1)["days"] == "1")
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.daysOpened) == [])
    }

    @Test("sub on the store's month check: 1 paying, t in the trial, absent when lapsed",
          arguments: [(SubscriptionAccess.State.subscribed(expires: nil, inTrial: false), "1"),
                      (.subscribed(expires: nil, inTrial: true), "t"),
                      (.notSubscribed, nil)] as [(SubscriptionAccess.State, String?)])
    func subOnStore(state: SubscriptionAccess.State, expected: String?) async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        armFile()
        _ = await fetcher(subscription: { state }).checkIfDue()
        #expect(query()["month"] == "1")
        #expect(query()["sub"] == expected)
    }

    @Test("sub is never sent on the dmg, even with a subscribed state to read")
    func subNeverOnDmg() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        armFile()
        _ = await fetcher(channel: .dmg,
                          subscription: { .subscribed(expires: nil, inTrial: false) }).checkIfDue()
        #expect(query()["ch"] == "dmg" && query()["month"] == "1")
        #expect(query()["sub"] == nil)
    }

    @Test("A store not yet known is waited for, and its answer rides")
    func subWaitsForStore() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        final class Box: @unchecked Sendable { var state: SubscriptionAccess.State = .unknown }
        let box = Box()
        armFile()
        let f = fetcher(subscription: { box.state }, subscriptionWait: 5)
        async let outcome = f.checkIfDue()
        try? await Task.sleep(nanoseconds: 400_000_000)
        #expect(NewsStub.seen.isEmpty)  // still waiting for the store
        box.state = .subscribed(expires: nil, inTrial: false)
        #expect(await outcome == .accepted)
        #expect(query()["sub"] == "1")
    }

    @Test("A store that never answers holds the check only as long as the wait, then no sub")
    func subWaitIsBounded() async {
        defer { cleanUp() }
        defaults.set(true, forKey: NewsPreferences.countsKey)
        armFile()
        #expect(await fetcher(subscription: { .unknown }, subscriptionWait: 0.5).checkIfDue()
                == .accepted)
        #expect(query()["month"] == "1" && query()["sub"] == nil)
    }

    @Test("Counting off: no days recorded, no wait, the bare request",
          arguments: [nil, false] as [Bool?])
    func countsOffNoDaysOrSub(consent: Bool?) async {
        defer { cleanUp() }
        if let consent { defaults.set(consent, forKey: NewsPreferences.countsKey) }
        let f = fetcher(subscription: { .unknown }, subscriptionWait: 5)
        f.recordAppOpened()
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.daysOpened) ?? [] == [])
        armFile()
        let started = Date()
        _ = await f.checkIfDue()
        #expect(Date().timeIntervalSince(started) < 4)
        #expect(NewsStub.seen.map { $0.url?.absoluteString } == ["https://bristlenose.app/app/news?s=1"])
    }

    // MARK: Refusals

    @Test("A redirect is refused: the target is never asked, nothing is cached")
    func redirectRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        NewsStub.arm(.init(status: 302, headers: ["Date": K.httpDate(clock.now)],
                           location: "https://evil.example/app/news"))
        #expect(await f.checkIfDue() == .notAFile(status: 302))
        #expect(NewsStub.seen.map { $0.url?.host } == ["bristlenose.app"])
        #expect(f.items.isEmpty)
    }

    @Test("An oversize body is refused, counted as it arrives")
    func oversizeRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        var reply = NewsStub.Reply()
        reply.body = Data(repeating: 0x20, count: NewsCheck.maxEnvelopeBytes + 1)
        NewsStub.arm(reply)
        #expect(await f.checkIfDue() == .notAFile(status: 200))
        #expect(f.items.isEmpty)
    }

    @Test("A 200 that is not JSON is not a file")
    func htmlRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        NewsStub.arm(.init(headers: ["Content-Type": "text/html"], body: Data("<html>".utf8)))
        #expect(await f.checkIfDue() == .notAFile(status: 200))
    }

    @Test("A replayed older file is refused and the newer cache stays")
    func replayRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile(K.payload(issued: K.date(2026, 12, 10)))
        #expect(await f.checkIfDue() == .accepted)
        clock.now = K.date(2026, 12, 13)
        armFile(K.payload(issued: K.date(2026, 11, 20), items: []))
        #expect(await f.checkIfDue() == .rejected(.replayed))
        #expect(f.items.count == 1)
    }

    @Test("A future-dated file is refused")
    func futureRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile(K.payload(issued: K.date(2026, 12, 20), expires: K.date(2027, 1, 10)))
        #expect(await f.checkIfDue() == .rejected(.futureDated))
        #expect(f.items.isEmpty)
    }

    @Test("A backup-key revocation is kept, and the revoked kid is refused from then on")
    func revokedKidRefused() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        #expect(await f.checkIfDue() == .accepted)
        #expect(f.items.count == 1)
        clock.now = K.date(2026, 12, 13)
        armFile(K.payload(issued: K.date(2026, 12, 13), expires: K.date(2026, 12, 30),
                          items: [], revoke: ["k1"]), key: k0, kid: "k0")
        #expect(await f.checkIfDue() == .accepted)
        #expect(defaults.stringArray(forKey: NewsStateKeys.production.revoked) == ["k1"])
        clock.now = K.date(2026, 12, 14)
        armFile(K.payload(issued: K.date(2026, 12, 14)))
        #expect(await f.checkIfDue() == .rejected(.revokedKey))
        #expect(f.items.isEmpty)
    }

    // MARK: The cache

    @Test("The cache is re-verified on every load: a tampered cache shows nothing")
    func cacheReverified() async throws {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        _ = await f.checkIfDue()
        #expect(f.items.count == 1)
        // A second fetcher (a relaunch) reads the cache.
        #expect(fetcher().items.count == 1)
        let key = NewsStateKeys.production.envelope
        var object = try #require(try JSONSerialization.jsonObject(
            with: defaults.data(forKey: key)!) as? [String: String])
        object["kid"] = "k9"
        defaults.set(try JSONSerialization.data(withJSONObject: object), forKey: key)
        #expect(fetcher().items.isEmpty)
    }

    @Test("An expired cache shows nothing")
    func expiredCache() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile()
        _ = await f.checkIfDue()
        clock.now = K.date(2026, 12, 31, 1)
        f.reloadFromCache()
        #expect(f.items.isEmpty)
    }

    @Test("currentItems judges the time window now: an item past its until is gone without a fetch")
    func currentItemsPastUntil() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile(K.payload(items: [K.item(id: "office-hours-2026-12-15",
                                         until: K.date(2026, 12, 15))]))
        #expect(await f.checkIfDue() == .accepted)
        #expect(f.currentItems().map(\.id) == ["office-hours-2026-12-15"])
        NewsStub.reset()
        // No check runs: the item must go on the clock alone.
        clock.now = K.date(2026, 12, 15).addingTimeInterval(60)
        #expect(f.currentItems().isEmpty)
        #expect(NewsStub.seen.isEmpty)
        #expect(f.items.count == 1)  // the published list is untouched until a reload
    }

    @Test("A clicked news item is gone from the next window's currentItems")
    func currentItemsAfterClick() async {
        defer { cleanUp() }
        let f = fetcher()
        armFile(K.payload(items: [K.item(id: "office-hours-2026-12-15"),
                                  K.item(id: "news-0-47", tone: "news")]))
        _ = await f.checkIfDue()
        let firstWindow = f.currentItems()
        #expect(firstWindow.map(\.id) == ["news-0-47", "office-hours-2026-12-15"])
        for item in firstWindow { f.recordClick(on: item) }
        #expect(f.currentItems().map(\.id) == ["office-hours-2026-12-15"])
    }

    @Test("A clicked news item hides from the next load; a community item does not")
    func clicks() async throws {
        defer { cleanUp() }
        let f = fetcher()
        armFile(K.payload(items: [K.item(id: "office-hours-2026-12-15"),
                                  K.item(id: "news-0-47", tone: "news")]))
        _ = await f.checkIfDue()
        #expect(f.items.map(\.id) == ["news-0-47", "office-hours-2026-12-15"])
        for item in f.items { f.recordClick(on: item) }
        #expect(f.items.count == 2)  // nothing jumps under the reader
        f.reloadFromCache()
        #expect(f.items.map(\.id) == ["office-hours-2026-12-15"])
    }
}
