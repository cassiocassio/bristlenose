import CryptoKit
import Foundation
import Testing

@testable import Bristlenose

// The news check's pure rules (spec docs/private/design-news-and-counts.md §3,
// §4, §9 and the "Tests that matter" in §10). Every key here is made by the
// test; nothing touches the production keys, which are empty placeholders.

/// Shared builders for the news suites.
enum NewsTestKit {
    static let utc: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }()

    static func date(_ y: Int, _ m: Int, _ d: Int, _ h: Int = 12, _ min: Int = 0,
                     _ s: Int = 0) -> Date {
        utc.date(from: DateComponents(year: y, month: m, day: d, hour: h, minute: min, second: s))!
    }

    static func iso(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }

    static func httpDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "GMT")
        formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss zzz"
        return formatter.string(from: date)
    }

    static func item(
        id: String = "office-hours-2026-12-15",
        tone: String? = "community",
        channels: [String] = ["store", "dmg"],
        minVersion: String? = nil,
        from: Date = date(2026, 12, 11, 0),
        until: Date = date(2026, 12, 15, 18, 30),
        locales: [String] = ["en"],
        text: [String: [String: String]]? = nil,
        href: String = "https://bristlenose.app/community/?ref=app-news&id=office-hours-2026-12-15#office-hours"
    ) -> [String: Any] {
        var item: [String: Any] = [
            "id": id, "channels": channels, "from": iso(from), "until": iso(until),
            "locales": locales, "href": href,
            "text": text ?? ["en": [
                "title": "Office hours",
                "text": "Drop in with Martin Storey, author of Bristlenose, on Tuesday 15 December, 5.30 to 6.30pm UK time.",
                "more": "Bring a question, or something that needs fixing, improving or adding.",
                "link": "Office hours details",
            ]],
        ]
        if let tone { item["tone"] = tone }
        if let minVersion { item["minVersion"] = minVersion }
        return item
    }

    static func payload(
        env: String = "prod", schema: Int = 1,
        issued: Date = date(2026, 11, 20, 9), expires: Date = date(2026, 12, 31, 0),
        items: [[String: Any]] = [item()], revoke: [String]? = nil
    ) -> Data {
        var object: [String: Any] = [
            "schema": schema, "env": env, "issued": iso(issued), "expires": iso(expires),
            "items": items,
        ]
        if let revoke { object["revoke"] = revoke }
        return try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    }

    static func envelope(_ payload: Data, key: Curve25519.Signing.PrivateKey,
                         kid: String = "k1", context: Data = NewsCheck.signingContext) -> Data {
        let signature = try! key.signature(for: context + payload)
        return try! JSONSerialization.data(withJSONObject: [
            "kid": kid,
            "payload": payload.base64EncodedString(),
            "sig": signature.base64EncodedString(),
        ])
    }

    static func keyring(_ keys: [String: Curve25519.Signing.PrivateKey],
                        backup: String? = "k0") -> NewsCheck.Keyring {
        NewsCheck.Keyring(
            base64Keys: keys.mapValues { $0.publicKey.rawRepresentation.base64EncodedString() },
            backupKID: backup)
    }

    static func context(_ now: Date = date(2026, 12, 12), language: String = "en",
                        channel: NewsCheck.Channel? = .store, version: String = "0.47.0",
                        hidden: Set<String> = []) -> NewsCheck.DisplayContext {
        .init(channel: channel, appVersion: version, interfaceLanguage: language, now: now,
              hiddenIDs: hidden)
    }
}

/// The parent suite, so `-only-testing:BristlenoseTests/NewsCheckTests` runs all three.
@Suite("NewsCheck")
struct NewsCheckTests {}

// MARK: - The request and the counting state

extension NewsCheckTests {
@Suite("NewsCheck: query and state")
struct QueryAndState {
    typealias K = NewsTestKit

    private func url(_ query: NewsCheck.Query) -> String {
        query.url(base: NewsCheck.productionEndpoint)!.absoluteString
    }

    @Test("First ever check with a yes sends every flag, in the spec's order")
    func firstEverCheck() {
        var state = NewsCheck.State()
        state.welcomeSinceCheck = 3
        let query = NewsCheck.query(state: state, consent: .yes, appVersion: "0.47.0",
                                    channel: .store, serverNow: K.date(2026, 12, 1))
        #expect(url(query) == "https://bristlenose.app/app/news?s=1&v=0.47.0&ch=store&first=1&month=1&w=3")
    }

    @Test("Counting not answered or no: the bare s=1, whatever the state",
          arguments: [NewsCheck.CountsConsent.unanswered, .no])
    func noFlagsWithoutYes(consent: NewsCheck.CountsConsent) {
        var state = NewsCheck.State()
        state.welcomeSinceCheck = 40
        let query = NewsCheck.query(state: state, consent: consent, appVersion: "0.47.0",
                                    channel: .dmg, serverNow: K.date(2026, 12, 1))
        #expect(!query.carriesCounts)
        #expect(url(query) == "https://bristlenose.app/app/news?s=1")
    }

    @Test("A debug build sends no ch; a malformed version sends no v")
    func debugAndOddVersion() {
        let query = NewsCheck.query(state: .init(), consent: .yes, appVersion: "0.47.0b1",
                                    channel: nil, serverNow: K.date(2026, 12, 1))
        #expect(query.channel == nil && query.version == nil)
        #expect(!url(query).contains("ch=") && !url(query).contains("v="))
        #expect(NewsCheck.Channel.from(.debug) == nil)
        #expect(NewsCheck.Channel.from(.developerID) == .dmg)
        #expect(NewsCheck.Channel.from(.appStoreOrTestFlight) == .store)
    }

    @Test("Same server day: not due. Next day, same month: due, month not set")
    func sameDayAndNextDay() {
        var state = NewsCheck.State(lastCheck: K.date(2026, 12, 3, 8), everChecked: true)
        #expect(!NewsCheck.isDue(state, serverNow: K.date(2026, 12, 3, 23, 59)))
        #expect(NewsCheck.isDue(state, serverNow: K.date(2026, 12, 4, 0, 1)))
        let query = NewsCheck.query(state: state, consent: .yes, appVersion: "0.47.0",
                                    channel: .store, serverNow: K.date(2026, 12, 4, 0, 1))
        #expect(!query.first && !query.month)
        state.welcomeSinceCheck = 0
        #expect(url(query).hasSuffix("s=1&v=0.47.0&ch=store&w=0"))
    }

    @Test("Month change and year change set month")
    func monthAndYearChange() {
        let nov = NewsCheck.State(lastCheck: K.date(2026, 11, 30, 23), everChecked: true)
        #expect(NewsCheck.isFirstThisMonth(nov, serverNow: K.date(2026, 12, 1, 0, 30)))
        let dec = NewsCheck.State(lastCheck: K.date(2026, 12, 31, 23), everChecked: true)
        #expect(NewsCheck.isFirstThisMonth(dec, serverNow: K.date(2027, 1, 1, 0, 5)))
        #expect(NewsCheck.isDue(dec, serverNow: K.date(2027, 1, 1, 0, 5)))
        // Same month a year later is still a new month.
        let lastYear = NewsCheck.State(lastCheck: K.date(2025, 12, 10), everChecked: true)
        #expect(NewsCheck.isFirstThisMonth(lastYear, serverNow: K.date(2026, 12, 10)))
    }

    @Test("A wrong Mac clock: days and months follow the server's clock")
    func wrongMacClock() {
        // The Mac is a year slow. The last response measured the offset.
        let serverLast = K.date(2026, 11, 15)
        let macLast = K.date(2025, 11, 15)
        let state = NewsCheck.afterResponse(.init(), sent: .init(), serverDate: serverLast,
                                            localNow: macLast)
        #expect(state.lastCheck == serverLast)
        // Seventeen days on, by the Mac's (wrong) clock: the server is in December.
        let macNow = K.date(2025, 12, 2)
        let serverNow = NewsCheck.estimatedServerNow(state, localNow: macNow)
        #expect(NewsCheck.utcMonth(serverNow) == DateComponents(year: 2026, month: 12))
        #expect(NewsCheck.isDue(state, serverNow: serverNow))
        #expect(NewsCheck.isFirstThisMonth(state, serverNow: serverNow))
        // Without the offset the Mac's clock would have said "same month, last year".
        #expect(!NewsCheck.isFirstThisMonth(state, serverNow: macNow))
    }

    @Test("A server clock behind the last check claims no new month")
    func clockWentBackwards() {
        let state = NewsCheck.State(lastCheck: K.date(2026, 12, 10), everChecked: true)
        #expect(!NewsCheck.isFirstThisMonth(state, serverNow: K.date(2026, 11, 5)))
    }

    @Test("Any response consumes the flags; w drops by the amount sent, not to zero")
    func responseConsumesFlags() {
        var state = NewsCheck.State(welcomeSinceCheck: 5)
        let sent = NewsCheck.query(state: state, consent: .yes, appVersion: "0.47.0",
                                   channel: .store, serverNow: K.date(2026, 12, 1))
        #expect(sent.first && sent.month && sent.welcome == 5)
        state.welcomeSinceCheck = 7  // two more windows during the request
        let after = NewsCheck.afterResponse(state, sent: sent, serverDate: K.date(2026, 12, 1),
                                            localNow: K.date(2026, 12, 1))
        #expect(after.everChecked)
        #expect(after.welcomeSinceCheck == 2)
        #expect(after.lastCheck == K.date(2026, 12, 1))
        let next = NewsCheck.query(state: after, consent: .yes, appVersion: "0.47.0",
                                   channel: .store, serverNow: K.date(2026, 12, 2))
        #expect(!next.first && !next.month && next.welcome == 2)
    }

    @Test("w is capped at 99 on the wire and the rest waits")
    func welcomeCap() {
        let state = NewsCheck.State(welcomeSinceCheck: 150)
        let sent = NewsCheck.query(state: state, consent: .yes, appVersion: "0.47.0",
                                   channel: .store, serverNow: K.date(2026, 12, 1))
        #expect(sent.welcome == 99)
        let after = NewsCheck.afterResponse(state, sent: sent, serverDate: nil,
                                            localNow: K.date(2026, 12, 1))
        #expect(after.welcomeSinceCheck == 51)
    }

    @Test("A response with no flags does not book first, and drops views")
    func bareResponse() {
        let state = NewsCheck.State(welcomeSinceCheck: 4)
        let after = NewsCheck.afterResponse(state, sent: .init(), serverDate: K.date(2026, 12, 1),
                                            localNow: K.date(2026, 12, 1))
        #expect(!after.everChecked && after.welcomeSinceCheck == 0)
    }

    @Test("Welcome views count only with a yes")
    func welcomeCountsOnlyWithYes() {
        #expect(NewsCheck.recordWelcomeShown(.init(), consent: .yes).welcomeSinceCheck == 1)
        #expect(NewsCheck.recordWelcomeShown(.init(), consent: .no).welcomeSinceCheck == 0)
        #expect(NewsCheck.recordWelcomeShown(.init(), consent: .unanswered).welcomeSinceCheck == 0)
    }

    @Test("Seen ids keep the most recent 200")
    func seenCap() {
        var seen: [String] = []
        for n in 0..<250 { seen = NewsCheck.markSeen(seen, id: "n\(n)") }
        #expect(seen.count == 200 && seen.first == "n50" && seen.last == "n249")
        #expect(NewsCheck.markSeen(["a", "b"], id: "a") == ["b", "a"])
    }

    @Test("The HTTP Date header parses as GMT; junk does not")
    func httpDate() {
        #expect(NewsCheck.parseHTTPDate("Tue, 01 Dec 2026 00:30:00 GMT") == K.date(2026, 12, 1, 0, 30))
        #expect(NewsCheck.parseHTTPDate("yesterday") == nil)
        #expect(NewsCheck.parseHTTPDate(nil) == nil)
    }

    @Test("Strict success: 200 and a JSON content type only")
    func strictSuccess() {
        #expect(NewsCheck.isAcceptableResponse(status: 200, contentType: "application/json"))
        #expect(NewsCheck.isAcceptableResponse(status: 200, contentType: "application/json; charset=utf-8"))
        #expect(!NewsCheck.isAcceptableResponse(status: 200, contentType: "text/html"))
        #expect(!NewsCheck.isAcceptableResponse(status: 200, contentType: "application/jsonp"))
        #expect(!NewsCheck.isAcceptableResponse(status: 304, contentType: "application/json"))
        #expect(!NewsCheck.isAcceptableResponse(status: 200, contentType: nil))
    }
}
}

// MARK: - The envelope

extension NewsCheckTests {
@Suite("NewsCheck: envelope")
struct Envelope {
    typealias K = NewsTestKit
    let k1 = Curve25519.Signing.PrivateKey()
    let k0 = Curve25519.Signing.PrivateKey()
    var policy: NewsCheck.VerifyPolicy { .init(keyring: K.keyring(["k1": k1, "k0": k0]), requiredEnv: "prod") }
    let now = NewsTestKit.date(2026, 12, 12)

    private func verify(_ envelope: Data, revoked: Set<String> = [],
                        freshness: NewsCheck.Freshness = .init(),
                        now: Date? = nil) -> NewsCheck.Verification {
        NewsCheck.verify(envelope: envelope, policy: policy, revoked: revoked,
                         freshness: freshness, now: now ?? self.now)
    }

    private func rejection(_ v: NewsCheck.Verification) -> NewsCheck.Rejection? {
        if case .failure(let reason) = v.result { return reason }
        return nil
    }

    @Test("A good file verifies")
    func goodFile() throws {
        let result = try verify(K.envelope(K.payload(), key: k1)).result.get()
        #expect(result.kid == "k1" && result.items.count == 1)
        #expect(result.issued == K.date(2026, 11, 20, 9))
    }

    @Test("Over 64 KB is refused before anything is read")
    func tooLarge() {
        #expect(rejection(verify(Data(count: NewsCheck.maxEnvelopeBytes + 1))) == .tooLarge)
    }

    @Test("Unknown kid, and an unset (empty) key accepts nothing")
    func unknownKey() {
        #expect(rejection(verify(K.envelope(K.payload(), key: k1, kid: "k9"))) == .unknownKey)
        let empty = NewsCheck.Keyring(base64Keys: ["k1": "", "k0": "not base64"], backupKID: "k0")
        #expect(empty.keys.isEmpty)
        let v = NewsCheck.verify(envelope: K.envelope(K.payload(), key: k1),
                                 policy: .init(keyring: empty, requiredEnv: "prod"),
                                 revoked: [], freshness: .init(), now: now)
        #expect(rejection(v) == .unknownKey)
    }

    @Test("A tampered payload, a wrong key and a missing context all fail the signature")
    func badSignature() throws {
        let good = K.envelope(K.payload(), key: k1)
        var object = try #require(try JSONSerialization.jsonObject(with: good) as? [String: String])
        var bytes = try #require(Data(base64Encoded: object["payload"]!))
        bytes[bytes.count - 3] ^= 0x01
        object["payload"] = bytes.base64EncodedString()
        let tampered = try JSONSerialization.data(withJSONObject: object)
        #expect(rejection(verify(tampered)) == .badSignature)
        #expect(rejection(verify(K.envelope(K.payload(), key: Curve25519.Signing.PrivateKey()))) == .badSignature)
        #expect(rejection(verify(K.envelope(K.payload(), key: k1, context: Data()))) == .badSignature)
    }

    @Test("Not an envelope")
    func malformedEnvelope() {
        #expect(rejection(verify(Data("[]".utf8))) == .malformedEnvelope)
        #expect(rejection(verify(Data(#"{"kid":"k1","payload":"!!","sig":"AA=="}"#.utf8))) == .malformedEnvelope)
    }

    @Test("A signed payload that is not the schema, or not JSON, is refused")
    func badPayload() {
        #expect(rejection(verify(K.envelope(K.payload(schema: 2), key: k1))) == .unsupportedSchema)
        #expect(rejection(verify(K.envelope(Data("hello".utf8), key: k1))) == .malformedPayload)
    }

    @Test("A staging file is refused where prod is required")
    func wrongEnv() {
        #expect(rejection(verify(K.envelope(K.payload(env: "staging"), key: k1))) == .wrongEnvironment)
    }

    @Test("A replayed older file is refused; the same file again is fine; same date, other bytes is not")
    func replay() throws {
        let current = K.payload(issued: K.date(2026, 12, 1))
        let digest = Data(SHA256.hash(data: current))
        let floor = NewsCheck.Freshness(maxIssued: K.date(2026, 12, 1), maxIssuedDigest: digest)
        let older = K.envelope(K.payload(issued: K.date(2026, 11, 20)), key: k1)
        #expect(rejection(verify(older, freshness: floor)) == .replayed)
        #expect((try? verify(K.envelope(current, key: k1), freshness: floor).result.get()) != nil)
        let sibling = K.payload(issued: K.date(2026, 12, 1), items: [])
        #expect(rejection(verify(K.envelope(sibling, key: k1), freshness: floor)) == .replayed)
        let newer = K.payload(issued: K.date(2026, 12, 2))
        #expect((try? verify(K.envelope(newer, key: k1), freshness: floor).result.get()) != nil)
    }

    @Test("A file issued more than 2 days ahead is refused; exactly 2 days is allowed")
    func futureDated() {
        let ahead = K.payload(issued: now.addingTimeInterval(2 * 86_400 + 1),
                              expires: now.addingTimeInterval(10 * 86_400))
        #expect(rejection(verify(K.envelope(ahead, key: k1))) == .futureDated)
        let edge = K.payload(issued: now.addingTimeInterval(2 * 86_400),
                             expires: now.addingTimeInterval(10 * 86_400))
        #expect((try? verify(K.envelope(edge, key: k1)).result.get()) != nil)
    }

    @Test("Lifetime over 45 days is refused; an expired file is refused")
    func lifetimeAndExpiry() {
        let long = K.payload(issued: K.date(2026, 11, 20), expires: K.date(2027, 1, 4, 12, 0, 1))
        #expect(rejection(verify(K.envelope(long, key: k1))) == .lifetimeTooLong)
        let inverted = K.payload(issued: K.date(2026, 12, 1), expires: K.date(2026, 11, 30))
        #expect(rejection(verify(K.envelope(inverted, key: k1))) == .lifetimeTooLong)
        #expect(rejection(verify(K.envelope(K.payload(), key: k1), now: K.date(2026, 12, 31, 0))) == .expired)
    }

    @Test("A revoked kid is refused")
    func revokedKid() {
        #expect(rejection(verify(K.envelope(K.payload(), key: k1), revoked: ["k1"])) == .revokedKey)
    }

    @Test("The backup key revokes k1, even in a file that is otherwise refused")
    func backupRevokes() {
        let revoke = K.payload(issued: K.date(2026, 12, 12), expires: K.date(2026, 12, 20),
                               items: [], revoke: ["k1", "k0"])
        let v = verify(K.envelope(revoke, key: k0, kid: "k0"))
        #expect(v.newRevocations == ["k1"])  // never itself
        #expect((try? v.result.get()) != nil)
        // A leaked k1 pushed the floor into the future: the revocation still lands.
        let floor = NewsCheck.Freshness(maxIssued: K.date(2026, 12, 14), maxIssuedDigest: Data())
        let blocked = verify(K.envelope(revoke, key: k0, kid: "k0"), freshness: floor)
        #expect(rejection(blocked) == .replayed)
        #expect(blocked.newRevocations == ["k1"])
    }

    @Test("Only the backup key can revoke")
    func activeKeyCannotRevoke() {
        let v = verify(K.envelope(K.payload(revoke: ["k0"]), key: k1))
        #expect(v.newRevocations.isEmpty)
    }

    @Test("At most 20 items are read; a malformed item drops only itself")
    func itemLimits() throws {
        let many = (0..<25).map { K.item(id: "n\($0)") }
        #expect(try verify(K.envelope(K.payload(items: many), key: k1)).result.get().items.count == 20)
        var broken = K.item(id: "broken")
        broken["from"] = "not a date"
        let mixed = K.payload(items: [broken, K.item(id: "fine")])
        #expect(try verify(K.envelope(mixed, key: k1)).result.get().items.map(\.id) == ["fine"])
    }

    // MARK: Seam

    nonisolated private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/news-envelope-contract.json")

    @Test("Seam: the envelope sign-news.py signed verifies here, item and all")
    func pythonSignedFixture() throws {
        let fixture = try #require(try JSONSerialization.jsonObject(
            with: Data(contentsOf: Self.fixtureURL)) as? [String: Any])
        let publicKey = try #require(fixture["public_key"] as? String)
        let kid = try #require(fixture["kid"] as? String)
        let context = try #require(fixture["context"] as? [String: String])
        let expect = try #require(fixture["expect"] as? [String: String])
        let envelope = try JSONSerialization.data(withJSONObject: try #require(fixture["envelope"]))

        let keyring = NewsCheck.Keyring(base64Keys: [kid: publicKey], backupKID: nil)
        let formatter = ISO8601DateFormatter()
        let now = try #require(formatter.date(from: context["now"]!))
        let file = try NewsCheck.verify(envelope: envelope,
                                        policy: .init(keyring: keyring, requiredEnv: "prod"),
                                        revoked: [], freshness: .init(), now: now).result.get()
        let items = NewsCheck.displayableItems(file, context: .init(
            channel: NewsCheck.Channel(rawValue: context["channel"]!),
            appVersion: context["app_version"]!,
            interfaceLanguage: context["interface_language"]!, now: now, hiddenIDs: []))
        let item = try #require(items.first)
        #expect(items.count == 1)
        #expect(item.id == expect["id"])
        #expect(item.tone.rawValue == expect["tone"])
        #expect(item.title == expect["title"])
        #expect(item.text == expect["text"])
        #expect(item.more == expect["more"])
        #expect(item.link == expect["link"])
        #expect(item.href.absoluteString == expect["href"])
        #expect(item.until == formatter.date(from: expect["until"]!))

        // And one flipped byte in the fixture's signature fails here too.
        var object = try #require(fixture["envelope"] as? [String: String])
        var sig = try #require(Data(base64Encoded: object["sig"]!))
        sig[0] ^= 0x01
        object["sig"] = sig.base64EncodedString()
        let bad = NewsCheck.verify(envelope: try JSONSerialization.data(withJSONObject: object),
                                   policy: .init(keyring: keyring, requiredEnv: "prod"),
                                   revoked: [], freshness: .init(), now: now)
        #expect(bad.result == .failure(.badSignature))
    }
}
}

// MARK: - Field rules

extension NewsCheckTests {
@Suite("NewsCheck: field rules")
struct FieldRules {
    typealias K = NewsTestKit

    private func decode(_ item: [String: Any]) throws -> NewsCheck.RawItem {
        let data = try JSONSerialization.data(withJSONObject: item)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(NewsCheck.RawItem.self, from: data)
    }

    private func shown(_ item: [String: Any],
                       _ context: NewsCheck.DisplayContext = NewsTestKit.context()) throws -> NewsItem? {
        NewsCheck.item(try decode(item), context: context)
    }

    @Test("community and news show; alert, unknown and missing tones do not")
    func tones() throws {
        #expect(try shown(K.item(tone: "community"))?.tone == .community)
        #expect(try shown(K.item(tone: "news"))?.tone == .news)
        #expect(try shown(K.item(tone: "alert")) == nil)
        #expect(try shown(K.item(tone: "celebration")) == nil)
        #expect(try shown(K.item(tone: "Community")) == nil)
        #expect(try shown(K.item(tone: nil)) == nil)
    }

    @Test("A Markdown link in a field stays literal text, returned verbatim")
    func markdownStaysLiteral() throws {
        let item = try #require(try shown(K.item(text: ["en": [
            "title": "[Click](https://evil.example)",
            "text": "See **this** [here](https://evil.example/x) now",
            "link": "Details",
        ]])))
        #expect(item.title == "[Click](https://evil.example)")
        #expect(item.text == "See **this** [here](https://evil.example/x) now")
        #expect(item.more == nil)
    }

    @Test("Bidi and zero-width characters are stripped; newlines become spaces")
    func invisibleCharacters() throws {
        let item = try #require(try shown(K.item(text: ["en": [
            "title": "Office\u{202E}sruoh\u{202C} hours\u{200B}",
            "text": "Line one\nline\u{2066}two\u{2069}\u{FEFF}",
            "link": "\u{200F}Details",
        ]])))
        #expect(item.title == "Officesruoh hours")
        #expect(item.text == "Line one linetwo")
        #expect(item.link == "Details")
    }

    @Test("Line and paragraph separators become spaces; tag characters are stripped")
    func separatorsAndTags() {
        #expect(NewsCheck.sanitize("Line one\u{2028}two\u{2029}three") == "Line one two three")
        // Tag characters spell hidden text ("hi") and must not survive.
        #expect(NewsCheck.sanitize("Office\u{E0001}\u{E0068}\u{E0069}\u{E007F} hours")
                == "Office hours")
        #expect(NewsCheck.sanitize("\u{E0000}\u{2028}") == "")
    }

    @Test("A kind in the file is ignored, never a failure; the eyebrow is the tone's")
    func kindIgnored() throws {
        let withKind = try shown(K.item(text: ["en": [
            "kind": String(repeating: "x", count: 500),
            "title": "Office hours", "text": "Text", "link": "Details",
        ]]))
        #expect(withKind?.title == "Office hours")
    }

    @Test("Caps: at the cap is shown, one over drops the item; required fields must be present")
    func caps() throws {
        func copy(title: String = "T", text: String = "Body", more: String? = nil,
                  link: String = "Details") -> [String: Any] {
            var fields = ["title": title, "text": text, "link": link]
            if let more { fields["more"] = more }
            return K.item(text: ["en": fields])
        }
        let x = { (n: Int) in String(repeating: "é", count: n) }
        #expect(try shown(copy(title: x(80))) != nil)
        #expect(try shown(copy(title: x(81))) == nil)
        #expect(try shown(copy(text: x(200))) != nil)
        #expect(try shown(copy(text: x(201))) == nil)
        #expect(try shown(copy(more: x(201))) == nil)
        #expect(try shown(copy(link: x(40))) != nil)
        #expect(try shown(copy(link: x(41))) == nil)
        #expect(try shown(copy(title: "\u{200B}")) == nil)
        #expect(throws: (any Error).self) {
            try decode(K.item(text: ["en": ["title": "T", "text": "Body"]]))
        }
    }

    @Test("href tricks are refused", arguments: [
        "https://bristlenose.app.evil.com/community/",
        "https://bristlenose.app@evil.com/community/",
        "https://evil.com@bristlenose.app/community/",
        "https://user:pw@bristlenose.app/community/",
        "https://bristlenose.app:443/community/",
        "http://bristlenose.app/community/",
        "HTTPS://bristlenose.app/community/",
        "https://BRISTLENOSE.APP/community/",
        "https://bristlenose.app/office-hours",
        "https://bristlenose.app/pricing",
        "https://bristlenose.app/download/Bristlenose.dmg",
        "https://bristlenose.app/",
        "https://bristlenose.app/communityx",
        "https://bristlenose.app/docsx/",
        "https://bristlenose.app/docs/../pricing",
        "https://bristlenose.app/docs/%2e%2e/pricing",
        "https://bristlenose.app//evil.com/docs/",
        "https://bristlenose%2Eapp/community/",
        "javascript:alert(1)",
        "/community/",
        "",
    ])
    func hrefTricks(href: String) throws {
        #expect(NewsCheck.validateLink(href) == nil)
        #expect(try shown(K.item(href: href)) == nil)
    }

    @Test("Allowed links", arguments: [
        "https://bristlenose.app/community/?ref=app-news&id=office-hours-2026-12-15#office-hours",
        "https://bristlenose.app/community",
        "https://bristlenose.app/docs/getting-started",
        "https://bristlenose.app/news/0-47",
        "https://bristlenose.app/sample",
        "https://bristlenose.app/sample/",
    ])
    func allowedLinks(href: String) {
        #expect(NewsCheck.validateLink(href)?.absoluteString == href)
    }

    @Test("Locale: the interface language, then its base; no English fallback")
    func locales() throws {
        let en = K.item(locales: ["en"])
        #expect(try shown(en, K.context(language: "en")) != nil)
        #expect(try shown(en, K.context(language: "de")) == nil)
        #expect(try shown(en, K.context(language: "en-GB")) != nil)

        let copy = ["title": "T", "text": "Body", "link": "Mehr"]
        let de = K.item(locales: ["de", "en"], text: ["de": copy, "en": copy.merging(["link": "More"]) { $1 }])
        #expect(try shown(de, K.context(language: "de"))?.link == "Mehr")
        #expect(try shown(de, K.context(language: "en"))?.link == "More")
        #expect(try shown(de, K.context(language: "fr")) == nil)

        let pt = K.item(locales: ["pt"], text: ["pt": copy])
        #expect(try shown(pt, K.context(language: "pt-BR"))?.locale == "pt")
        let zh = K.item(locales: ["zh-Hant"], text: ["zh-Hant": copy])
        #expect(try shown(zh, K.context(language: "zh-Hant-HK"))?.locale == "zh-Hant")
        #expect(try shown(zh, K.context(language: "zh-Hans")) == nil)

        // Listed but no copy, or copy but not listed: not shown.
        #expect(try shown(K.item(locales: ["en", "de"]), K.context(language: "de")) == nil)
        #expect(try shown(K.item(locales: [], text: ["en": copy])) == nil)
        // More than 30 locales drops the item.
        let many = (0..<31).map { "x\($0)" } + ["en"]
        #expect(try shown(K.item(locales: many)) == nil)
    }

    @Test("Channel matching; a debug build matches any listed channel")
    func channels() throws {
        let dmgOnly = K.item(channels: ["dmg"])
        #expect(try shown(dmgOnly, K.context(channel: .store)) == nil)
        #expect(try shown(dmgOnly, K.context(channel: .dmg)) != nil)
        #expect(try shown(dmgOnly, K.context(channel: nil)) != nil)
        #expect(try shown(K.item(channels: ["debug"]), K.context(channel: nil)) == nil)
        #expect(try shown(K.item(channels: []), K.context(channel: .store)) == nil)
    }

    @Test("minVersion compares numerically")
    func minVersion() throws {
        #expect(try shown(K.item(minVersion: "0.47.0"), K.context(version: "0.47.0")) != nil)
        #expect(try shown(K.item(minVersion: "0.47.0"), K.context(version: "0.46.9")) == nil)
        #expect(try shown(K.item(minVersion: "0.9.0"), K.context(version: "0.10.0")) != nil)
        #expect(try shown(K.item(minVersion: "0.47"), K.context(version: "0.47.0")) == nil)
        #expect(try shown(K.item(minVersion: "0.47.0"), K.context(version: "dev")) == nil)
    }

    @Test("from and until bound the item by the server's clock")
    func window() throws {
        let item = K.item()
        #expect(try shown(item, K.context(K.date(2026, 12, 10, 23, 59))) == nil)
        #expect(try shown(item, K.context(K.date(2026, 12, 11, 0))) != nil)
        #expect(try shown(item, K.context(K.date(2026, 12, 15, 18, 29))) != nil)
        #expect(try shown(item, K.context(K.date(2026, 12, 15, 18, 30))) == nil)
    }

    @Test("After a click a news item hides; a community item does not")
    func hiddenAfterClick() throws {
        let hidden = K.context(hidden: ["office-hours-2026-12-15"])
        #expect(try shown(K.item(tone: "news"), hidden) == nil)
        #expect(try shown(K.item(tone: "community"), hidden) != nil)
    }

    @Test("Ids are boring: lowercase, digits, hyphens, at most 64")
    func ids() throws {
        #expect(try shown(K.item(id: "Office Hours")) == nil)
        #expect(try shown(K.item(id: String(repeating: "a", count: 65))) == nil)
        #expect(try shown(K.item(id: "")) == nil)
        #expect(try shown(K.item(id: "news-0-47")) != nil)
    }

    @Test("Displayable items come sorted by from, with stable ids")
    func sorted() throws {
        let k1 = Curve25519.Signing.PrivateKey()
        let payload = K.payload(items: [
            K.item(id: "later", from: K.date(2026, 12, 5)),
            K.item(id: "alert", tone: "alert", from: K.date(2026, 12, 1)),
            K.item(id: "earlier", from: K.date(2026, 12, 2)),
        ])
        let file = try NewsCheck.verify(
            envelope: K.envelope(payload, key: k1),
            policy: .init(keyring: K.keyring(["k1": k1]), requiredEnv: "prod"),
            revoked: [], freshness: .init(), now: K.date(2026, 12, 12)).result.get()
        #expect(NewsCheck.displayableItems(file, context: K.context()).map(\.id) == ["earlier", "later"])
    }
}
}
