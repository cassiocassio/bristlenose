import CryptoKit
import Foundation

/// The rules of the daily news check and its anonymous counts, with no
/// networking and no `UserDefaults`: every decision the check makes is a pure
/// function here, so each one is testable on its own. `NewsFetcher` is the
/// thin shell that does the I/O and calls these.
///
/// Spec: `docs/private/design-news-and-counts.md` (v3) §3 (the request), §4
/// (the file), §7 (settings) and §9 (keys). v1 is **text only**: images,
/// video and tints in a file are not read.
///
/// Three things this file guarantees, each pinned by `NewsCheckTests`:
/// 1. **No counts without a yes.** `query(…)` adds `v`, `ch`, `first`,
///    `month`, `w`, `days` and `sub` only when the person said yes
///    (`CountsConsent.yes`). Unanswered and no both send the bare `s=1`.
/// 2. **Nothing in the file is parsed before its signature passes**, and an
///    old, validly signed file cannot be replayed (`verify(…)`).
/// 3. **A failing item drops the item, never the screen** (`item(…)`), and
///    the text it carries is returned verbatim for `Text(verbatim:)`.
enum NewsCheck {

    // MARK: - Constants

    /// `s` in the query: the query's own schema version.
    static let querySchema = 1
    /// `schema` in the payload. Any other value rejects the file.
    static let payloadSchema = 1
    /// Domain-separation prefix: the signature covers these bytes, then the
    /// payload's. Mirrors `CONTEXT` in `scripts/sign-news.py`.
    static let signingContext = Data("bristlenose-news-v1\n".utf8)
    /// Byte cap on the whole envelope, counted as bytes arrive.
    static let maxEnvelopeBytes = 64 * 1024
    /// A file may be issued at most this far ahead of the (server) clock.
    static let maxFutureIssue: TimeInterval = 2 * 86_400
    /// `expires` may be at most this long after `issued`.
    static let maxLifetime: TimeInterval = 45 * 86_400
    /// `w` is sent capped to 0–99; the rest waits for the next check.
    static let maxWelcomeSent = 99
    /// Views kept locally between checks; past this they stop counting up.
    static let maxWelcomeStored = 10_000
    static let maxItems = 20
    static let maxLocalesPerItem = 30
    /// `news.seen` keeps the most recent ids, at most this many.
    static let maxSeenIDs = 200
    /// `days` is sent capped to 0–31.
    static let maxDaysSent = 31
    /// `news.daysOpened` keeps the most recent local dates, at most this many:
    /// a full report's 31, plus the check's own day, which belongs to the
    /// next report (`query(…)`), so a month opened every day reports 31.
    static let maxDaysStored = maxDaysSent + 1
    /// A response's `Date` further than this from the Mac's clock is not
    /// believed: whoever terminates TLS can write that header, and a far-off
    /// one would revive an expired file or flip the month on every check. The
    /// Mac's clock is used instead.
    static let maxClockSkew: TimeInterval = 3 * 86_400

    /// The only place the check ever asks. Validated through
    /// `FeedbackEndpoint.validate` by `NewsFetcher`, the same single gate the
    /// feedback sheet uses.
    static let productionEndpoint = URL(string: "https://bristlenose.app/app/news")!

    /// A card's link must be on this host, exactly.
    static let linkHost = "bristlenose.app"
    /// The paths a card may link to. **Lives in the app, never in the file.**
    /// An entry ending in `/` is a prefix (`/docs/…`); any other entry matches
    /// itself, with or without a trailing slash (`/community` and
    /// `/community/`). Office hours link to `/community/#office-hours` (UX
    /// review, 16 Nov 2026), so there is no `/office-hours` entry. Nothing here
    /// is about price, the `.dmg` or buying (Guideline 3.1.1/3.1.3, spec §4).
    static let linkPathAllowlist = ["/community", "/docs/", "/news/", "/sample"]

    /// `env` a Release build requires. Debug builds require `staging`.
    static let productionEnv = "prod"
    static let stagingEnv = "staging"

    // MARK: - Channel and consent

    /// `ch` on the wire. TestFlight reports as `store`.
    enum Channel: String, CaseIterable, Sendable {
        case store, dmg

        /// `nil` for a local debug build: it never sends `ch`, and it never
        /// reaches production (it asks only a `BRISTLENOSE_DEBUG_NEWS_URL`).
        static func from(_ channel: DistributionChannel) -> Channel? {
            switch channel {
            case .appStoreOrTestFlight: return .store
            case .developerID: return .dmg
            case .debug: return nil
            }
        }
    }

    /// The person's first-run answer about counting. Only `.yes` sends flags.
    enum CountsConsent: Equatable, Sendable {
        case unanswered, yes, no
    }

    /// `sub` on the wire (spec §3, D7): `1` subscribed and paying, `t` in the
    /// free trial. Lapsed, never subscribed, not yet known, or no store at all
    /// (`dmg`, a debug build) is no value, so `sub` is absent.
    enum SubscriptionFlag: String, Sendable {
        case paying = "1"
        case trial = "t"

        static func from(_ state: SubscriptionAccess.State?) -> SubscriptionFlag? {
            guard case let .subscribed(_, inTrial)? = state else { return nil }
            return inTrial ? .trial : .paying
        }
    }

    // MARK: - Local state

    /// What the check remembers between runs (persisted by `NewsFetcher`).
    struct State: Equatable, Sendable {
        /// The server's `Date` at the last HTTP response.
        var lastCheck: Date?
        /// Whether a check that carried `first=1` has ever reached the server.
        var everChecked = false
        /// Welcome windows shown since the last check, while counting was on.
        var welcomeSinceCheck = 0
        /// Server clock minus Mac clock, measured at the last response. The
        /// Mac's clock is only ever used through this, so a wrong Mac clock
        /// cannot book a check to the wrong day or month.
        var clockOffset: TimeInterval = 0
        /// The distinct **local** calendar dates (`yyyy-MM-dd`, `localDay(…)`)
        /// the app was launched or brought to the front, while counting was
        /// on, since the last check that carried `month`. Sorted, at most
        /// `maxDaysStored`. Only a count of them is ever sent (`days`).
        var daysOpened: [String] = []
        /// The latest believed server `Date` ever seen. Only moves forward, so
        /// a `Date` that steps back a month cannot make the next check a
        /// `month` check again.
        var latestServerDate: Date?
    }

    /// The server's clock, estimated from the Mac's and the last measured
    /// offset. An offset past `maxClockSkew` is never stored; one read back
    /// from older state is ignored.
    static func estimatedServerNow(_ state: State, localNow: Date) -> Date {
        guard abs(state.clockOffset) <= maxClockSkew else { return localNow }
        return localNow.addingTimeInterval(state.clockOffset)
    }

    /// The response's `Date`, if it is within `maxClockSkew` of the Mac's
    /// clock; `nil` (use the Mac's clock) if it is absent or further off.
    static func trustedServerDate(_ header: Date?, localNow: Date) -> Date? {
        guard let header, abs(header.timeIntervalSince(localNow)) <= maxClockSkew
        else { return nil }
        return header
    }

    /// "Now" for judging a verified file's items: never earlier than the
    /// newest verified file's `issued`, so a clock set back (a believed but
    /// early `Date`) cannot bring back an item whose `until` has passed.
    static func notBeforeNewestFile(_ now: Date, _ freshness: Freshness) -> Date {
        max(now, freshness.maxIssued ?? now)
    }

    /// At most one check per UTC day as the server sees it. Never on a timer:
    /// the caller asks at launch or wake.
    static func isDue(_ state: State, serverNow: Date) -> Bool {
        guard let last = state.lastCheck else { return true }
        return utcDay(last) != utcDay(serverNow)
    }

    // MARK: - The query

    struct Query: Equatable, Sendable {
        var version: String?
        var channel: Channel?
        var first = false
        var month = false
        var welcome: Int?
        /// Distinct local days opened since the last `month` check, 0–31.
        /// Only beside `month`, never beside `first`.
        var days: Int?
        /// Only beside `month`, on `ch=store`.
        var subscription: SubscriptionFlag?
        /// Not on the wire. On a `month` check, the local date of this check:
        /// the dates before it are this report's, and a response spends them;
        /// the check's own day stays for the next report, so no day is
        /// counted in two months.
        var daysBefore: String?

        /// True when anything beyond `s` rides along.
        var carriesCounts: Bool {
            version != nil || channel != nil || first || month || welcome != nil
                || days != nil || subscription != nil
        }

        /// In the spec's order: `s`, `v`, `ch`, `first`, `month`, `w`, `days`,
        /// `sub`. Flags are present only when set (`first=1`), never `first=0`.
        var queryItems: [URLQueryItem] {
            var items = [URLQueryItem(name: "s", value: String(NewsCheck.querySchema))]
            if let version { items.append(.init(name: "v", value: version)) }
            if let channel { items.append(.init(name: "ch", value: channel.rawValue)) }
            if first { items.append(.init(name: "first", value: "1")) }
            if month { items.append(.init(name: "month", value: "1")) }
            if let welcome { items.append(.init(name: "w", value: String(welcome))) }
            if let days { items.append(.init(name: "days", value: String(days))) }
            if let subscription { items.append(.init(name: "sub", value: subscription.rawValue)) }
            return items
        }

        func url(base: URL) -> URL? {
            guard var components = URLComponents(url: base, resolvingAgainstBaseURL: false)
            else { return nil }
            components.queryItems = queryItems
            return components.url
        }
    }

    /// The query for this check. With consent anything but `.yes`, it is the
    /// bare `s=1`.
    ///
    /// - Parameters:
    ///   - subscription: the app's subscription now (`SubscriptionFlag.from`).
    ///     Sent only on a `month` check on `ch=store`.
    ///   - localDay: today's local date (`localDay(…)`). `days` is sent only
    ///     with it, on a `month` check that is not the install's `first`.
    static func query(state: State, consent: CountsConsent, appVersion: String,
                      channel: Channel?, subscription: SubscriptionFlag? = nil,
                      localDay: String? = nil, serverNow: Date) -> Query {
        guard consent == .yes else { return Query() }
        var query = Query()
        query.version = isPlainVersion(appVersion) ? appVersion : nil
        query.channel = channel
        query.first = !state.everChecked
        query.month = isFirstThisMonth(state, serverNow: serverNow)
        query.welcome = min(max(state.welcomeSinceCheck, 0), maxWelcomeSent)
        if query.month {
            if let localDay {
                query.daysBefore = localDay
                // The install's first check has no earlier month to report.
                if !query.first {
                    let reported = Set(state.daysOpened.filter { $0 < localDay })
                    query.days = min(reported.count, maxDaysSent)
                }
            }
            if channel == .store { query.subscription = subscription }
        }
        return query
    }

    /// Whether the check should wait for the subscription to be known before
    /// it asks: only when it would send `sub` (a yes, `ch=store`, a `month`
    /// check) and the store has not answered yet (`.unknown`, at launch,
    /// before its first refresh). Without the wait, the launch check that
    /// carries `month` would almost always report a paying install as absent.
    static func awaitsSubscription(state: State, consent: CountsConsent, channel: Channel?,
                                   subscription: SubscriptionAccess.State?,
                                   serverNow: Date) -> Bool {
        consent == .yes && channel == .store && subscription == .unknown
            && isFirstThisMonth(state, serverNow: serverNow)
    }

    /// First check this UTC calendar month by the server's clock. A server
    /// clock that has gone *backwards* past the last check, or past the latest
    /// server date ever believed, makes no claim.
    static func isFirstThisMonth(_ state: State, serverNow: Date) -> Bool {
        guard let last = state.lastCheck else { return true }
        let floor = max(last, state.latestServerDate ?? last)
        guard serverNow > floor else { return false }
        return utcMonth(floor) != utcMonth(serverNow)
    }

    // MARK: - State transitions

    /// After **any** HTTP response, including 404 and 5xx: the request reached
    /// the server's log, so the counter will count it, and the flags are spent.
    /// (A transport failure, with no response at all, changes nothing: the
    /// caller simply does not call this, and the flags go next time.)
    ///
    /// - Parameters:
    ///   - current: the state *now*, re-read after the response, so welcome
    ///     views recorded during the request are kept.
    ///   - sent: the query that went out.
    ///   - serverDate: the response's `Date` header, if it had a usable one.
    ///     Believed only within `maxClockSkew` of `localNow`; further off, the
    ///     Mac's clock is used and the stored offset is reset.
    ///   - localNow: the Mac's clock when the response arrived.
    static func afterResponse(_ current: State, sent: Query, serverDate: Date?,
                              localNow: Date) -> State {
        var next = current
        // The clock this check's query was judged by.
        let estimate = estimatedServerNow(current, localNow: localNow)
        let checked: Date
        if let trusted = trustedServerDate(serverDate, localNow: localNow) {
            next.clockOffset = trusted.timeIntervalSince(localNow)
            checked = trusted
        } else if serverDate != nil {
            next.clockOffset = 0
            checked = localNow
        } else {
            checked = estimate
        }
        next.lastCheck = checked
        // The high-water mark covers the estimate too: a `Date` pinned to a
        // month's last hour would otherwise make every next day's estimate a
        // new month. Each value is within `maxClockSkew` of the Mac's clock,
        // so a mark further ahead than that means the Mac's own clock was set
        // back; it starts again from this check.
        var latest = max(checked, estimate, current.latestServerDate ?? checked)
        if latest > localNow.addingTimeInterval(maxClockSkew) { latest = checked }
        next.latestServerDate = latest
        if sent.carriesCounts {
            if sent.first { next.everChecked = true }
            next.welcomeSinceCheck = max(0, current.welcomeSinceCheck - (sent.welcome ?? 0))
            // A `month` check closes the period, `first` included (it sends no
            // `days`, but the next report starts from it). Days recorded since
            // the query was built are today's or later, so they are kept.
            if sent.month, let bound = sent.daysBefore {
                next.daysOpened = current.daysOpened.filter { $0 >= bound }
            }
        } else {
            // Views and days from a time the person had not said yes are not
            // kept for later.
            next.welcomeSinceCheck = 0
            next.daysOpened = []
        }
        return next
    }

    /// The app was launched or brought to the front on `localDay`. Counted
    /// once per local date, and only while counting is on.
    static func recordAppOpened(_ state: State, consent: CountsConsent,
                                localDay: String) -> State {
        guard consent == .yes, !state.daysOpened.contains(localDay) else { return state }
        var next = state
        next.daysOpened = Array((state.daysOpened + [localDay]).sorted().suffix(maxDaysStored))
        return next
    }

    /// A date as the Mac's own calendar day in `timeZone`, `yyyy-MM-dd`, so
    /// the keys sort as dates. Local, not the server's: `days` is about the
    /// person's days, not UTC ones.
    static func localDay(_ date: Date, in timeZone: TimeZone) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let parts = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// One welcome window shown. Counted only while counting is on.
    static func recordWelcomeShown(_ state: State, consent: CountsConsent) -> State {
        guard consent == .yes else { return state }
        var next = state
        next.welcomeSinceCheck = min(state.welcomeSinceCheck + 1, maxWelcomeStored)
        return next
    }

    /// Hide an item after its link was clicked. Most recent last, capped.
    static func markSeen(_ seen: [String], id: String) -> [String] {
        var next = seen.filter { $0 != id }
        next.append(id)
        return Array(next.suffix(maxSeenIDs))
    }

    // MARK: - Strict success

    /// Status 200 and a JSON content type. Anything else is not a file, and
    /// changes nothing but the flags (which any response consumes).
    static func isAcceptableResponse(status: Int, contentType: String?) -> Bool {
        guard status == 200 else { return false }
        let mime = (contentType ?? "").split(separator: ";").first
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() } ?? ""
        return mime == "application/json"
    }

    /// The HTTP `Date` header (IMF-fixdate, always GMT). `nil` if absent or odd.
    static func parseHTTPDate(_ raw: String?) -> Date? {
        guard let raw else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "GMT")
        formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss zzz"
        return formatter.date(from: raw)
    }

    // MARK: - Keys

    /// The public keys a build trusts, by `kid`. Empty or malformed entries are
    /// dropped, so an unset placeholder accepts nothing.
    struct Keyring: Sendable {
        let keys: [String: Curve25519.Signing.PublicKey]
        /// The cold key whose files may revoke others (`k0` in production).
        let backupKID: String?

        init(base64Keys: [String: String], backupKID: String?) {
            var keys: [String: Curve25519.Signing.PublicKey] = [:]
            for (kid, b64) in base64Keys {
                guard let raw = Data(base64Encoded: b64), raw.count == 32,
                      let key = try? Curve25519.Signing.PublicKey(rawRepresentation: raw)
                else { continue }
                keys[kid] = key
            }
            self.keys = keys
            self.backupKID = backupKID
        }
    }

    /// What a build accepts: its keys and the `env` a file must name.
    struct VerifyPolicy: Sendable {
        let keyring: Keyring
        let requiredEnv: String
    }

    /// **No key, no request.** While a build trusts no key (the production
    /// placeholders in `NewsKeys` are still empty, or a Debug build has no
    /// staging key), every file it could fetch would be refused with
    /// `unknownKey`. A request whose answer can never be shown is collection
    /// for nothing, so the check makes none at all, counts included.
    static func mayRequest(with keyring: Keyring) -> Bool {
        !keyring.keys.isEmpty
    }

    // MARK: - The file

    /// Why a file was refused. Never shown to anyone; tests and logs only.
    enum Rejection: Error, Equatable, Sendable {
        case tooLarge
        case malformedEnvelope
        case unknownKey
        case revokedKey
        case badSignature
        case malformedPayload
        case unsupportedSchema
        case wrongEnvironment
        case replayed
        case futureDated
        case lifetimeTooLong
        case expired
    }

    /// The newest file seen so far: replay protection.
    struct Freshness: Equatable, Sendable {
        var maxIssued: Date?
        /// SHA-256 of the payload bytes that set `maxIssued`.
        var maxIssuedDigest: Data?
    }

    /// A file whose signature, freshness and environment all passed. Its items
    /// are still raw: `displayableItems` applies the field rules.
    struct VerifiedFile: Equatable, Sendable {
        let kid: String
        let issued: Date
        let expires: Date
        let payloadDigest: Data
        let items: [RawItem]
    }

    struct Verification: Equatable, Sendable {
        /// Key ids newly revoked by a file signed with the backup key. Recorded
        /// permanently by the caller even when the rest of the file fails
        /// (a revocation must land even past a leaked key's future-dated file).
        var newRevocations: Set<String> = []
        var result: Result<VerifiedFile, Rejection>
    }

    struct Envelope: Decodable {
        let kid: String
        let payload: String
        let sig: String
    }

    /// Check order (spec §4): byte cap → known `kid` → not revoked →
    /// signature over the raw bytes → decode → schema and `env` → freshness.
    ///
    /// - Parameter now: the server's clock (its `Date` header, or the estimate).
    static func verify(envelope data: Data, policy: VerifyPolicy, revoked: Set<String>,
                       freshness: Freshness, now: Date) -> Verification {
        guard data.count <= maxEnvelopeBytes else { return .init(result: .failure(.tooLarge)) }
        guard let envelope = try? JSONDecoder().decode(Envelope.self, from: data),
              let payload = Data(base64Encoded: envelope.payload),
              let signature = Data(base64Encoded: envelope.sig), signature.count == 64
        else { return .init(result: .failure(.malformedEnvelope)) }
        guard let key = policy.keyring.keys[envelope.kid] else {
            return .init(result: .failure(.unknownKey))
        }
        guard !revoked.contains(envelope.kid) else { return .init(result: .failure(.revokedKey)) }
        guard key.isValidSignature(signature, for: signingContext + payload) else {
            return .init(result: .failure(.badSignature))
        }

        // Signature passed: only now is the payload read.
        var revocations: Set<String> = []
        if let backup = policy.keyring.backupKID, envelope.kid == backup,
           let list = try? decoder().decode(RevocationList.self, from: payload).revoke {
            revocations = Set(list).subtracting(revoked).subtracting([backup])
        }
        func fail(_ reason: Rejection) -> Verification {
            .init(newRevocations: revocations, result: .failure(reason))
        }

        guard let decoded = try? decoder().decode(Payload.self, from: payload) else {
            return fail(.malformedPayload)
        }
        guard decoded.schema == payloadSchema else { return fail(.unsupportedSchema) }
        guard decoded.env == policy.requiredEnv else { return fail(.wrongEnvironment) }

        let digest = Data(SHA256.hash(data: payload))
        if let maxIssued = freshness.maxIssued {
                if decoded.issued < maxIssued { return fail(.replayed) }
            if decoded.issued == maxIssued, digest != freshness.maxIssuedDigest {
                return fail(.replayed)
            }
        }
        guard decoded.issued <= now.addingTimeInterval(maxFutureIssue) else {
            return fail(.futureDated)
        }
        guard decoded.expires > decoded.issued,
              decoded.expires <= decoded.issued.addingTimeInterval(maxLifetime)
        else { return fail(.lifetimeTooLong) }
        // No floor is needed here: a file that passed the replay check has
        // `issued >= maxIssued`, and `expires > issued`, so a `now` raised to
        // `maxIssued` could never change this answer. The floor bites on the
        // items' windows (`NewsFetcher.currentItems`).
        guard decoded.expires > now else { return fail(.expired) }

        let items = (decoded.items ?? []).prefix(maxItems).compactMap(\.item)
        return .init(newRevocations: revocations, result: .success(VerifiedFile(
            kid: envelope.kid, issued: decoded.issued, expires: decoded.expires,
            payloadDigest: digest, items: Array(items))))
    }

    private struct RevocationList: Decodable { let revoke: [String]? }

    private struct Payload: Decodable {
        let schema: Int
        let env: String
        let issued: Date
        let expires: Date
        let items: [LossyItem]?
    }

    /// One malformed item drops that item, not the file.
    private struct LossyItem: Decodable {
        let item: RawItem?
        init(from decoder: Decoder) throws { item = try? RawItem(from: decoder) }
    }

    /// An item as the file states it, before the field rules.
    struct RawItem: Decodable, Equatable, Sendable {
        let id: String
        let channels: [String]
        let minVersion: String?
        let from: Date
        let until: Date
        let locales: [String]
        let text: [String: RawText]
        let href: String
        /// Missing reads as unknown, so the item is not shown.
        let tone: String?
    }

    /// One locale's copy. A `kind` key in the file is not decoded (ignored,
    /// never a failure): the eyebrow is the app's, from `tone`.
    struct RawText: Decodable, Equatable, Sendable {
        let title: String
        let text: String
        let more: String?
        let link: String
    }

    /// RFC 3339 with `Z` or an offset, whole seconds (what `sign-news.py` writes).
    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let raw = try decoder.singleValueContainer().decode(String.self)
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime]
            guard let date = formatter.date(from: raw) else {
                throw DecodingError.dataCorrupted(.init(
                    codingPath: decoder.codingPath, debugDescription: "not an RFC 3339 date"))
            }
            return date
        }
        return decoder
    }

    // MARK: - Field rules

    enum Tone: String, Sendable {
        case community, news, alert

        /// `alert` is reserved: the app knows it, but no file may use it until
        /// its design is approved. Unknown tones never reach this enum.
        var showsInV1: Bool { self != .alert }

        /// Only `news` hides after its link is clicked. `community` ends with
        /// its session; `alert` (when it ships) is never hidden.
        var hidesAfterClick: Bool { self == .news }
    }

    /// Caps in characters. There is no `kind`: the eyebrow comes from the
    /// app-owned `tone` (a localised key), and a `kind` in a file is ignored.
    static let fieldCaps = (title: 80, text: 200, more: 200, link: 40)
    /// Each field is also capped at this many Unicode scalars per character
    /// of its cap, so stacked combining marks (one character, any height)
    /// cannot overflow a card.
    static let scalarsPerCharacter = 4

    /// Within a field's character cap and its scalar cap.
    static func fits(_ text: String, cap: Int) -> Bool {
        text.count <= cap && text.unicodeScalars.count <= cap * scalarsPerCharacter
    }

    /// What decides whether an item shows on this Mac today.
    struct DisplayContext: Sendable {
        /// `nil` (a debug build) matches every channel an item lists.
        var channel: Channel?
        var appVersion: String
        /// The app's interface language (`I18n.resolvedLocale`), e.g. `pt-BR`.
        var interfaceLanguage: String
        /// The server's clock.
        var now: Date
        /// Ids whose link was clicked on this install.
        var hiddenIDs: Set<String>
    }

    /// The items to show, sorted by `from`, then `id`.
    static func displayableItems(_ file: VerifiedFile, context: DisplayContext) -> [NewsItem] {
        file.items.compactMap { item($0, context: context) }
            .sorted { ($0.from, $0.id) < ($1.from, $1.id) }
    }

    /// Every field rule for one item; `nil` drops it.
    static func item(_ raw: RawItem, context: DisplayContext) -> NewsItem? {
        guard isValidID(raw.id) else { return nil }
        guard let toneRaw = raw.tone, let tone = Tone(rawValue: toneRaw), tone.showsInV1
        else { return nil }
        // A clicked `news` item hides for this install. A `community` item never
        // does: its `until` already ends it with the session (UX review).
        if tone.hidesAfterClick, context.hiddenIDs.contains(raw.id) { return nil }

        if let channel = context.channel {
            guard raw.channels.contains(channel.rawValue) else { return nil }
        } else {
            guard raw.channels.contains(where: { Channel(rawValue: $0) != nil }) else { return nil }
        }
        if let minimum = raw.minVersion {
            guard let need = versionParts(minimum), let have = versionParts(context.appVersion),
                  !have.lexicographicallyPrecedes(need)
            else { return nil }
        }
        guard raw.from < raw.until, raw.from <= context.now, context.now < raw.until
        else { return nil }

        guard raw.locales.count <= maxLocalesPerItem, raw.text.count <= maxLocalesPerItem
        else { return nil }
        let offered = raw.locales.filter { raw.text[$0] != nil }
        guard let locale = matchLocale(interface: context.interfaceLanguage, offered: offered),
              let copy = raw.text[locale]
        else { return nil }

        let caps = fieldCaps
        guard let title = field(copy.title, cap: caps.title),
              let text = field(copy.text, cap: caps.text),
              let link = field(copy.link, cap: caps.link)
        else { return nil }
        var more: String?
        if let rawMore = copy.more {
            let cleaned = sanitize(rawMore)
            guard fits(cleaned, cap: caps.more) else { return nil }
            more = cleaned.isEmpty ? nil : cleaned
        }
        guard let href = validateLink(raw.href) else { return nil }

        return NewsItem(id: raw.id, tone: tone, locale: locale, title: title,
                        text: text, more: more, link: link, href: href,
                        from: raw.from, until: raw.until)
    }

    /// A required text field: sanitised, non-empty, within its cap (in
    /// characters, and in scalars: `fits`). Over the cap drops the item; it
    /// is never cut mid-word here.
    private static func field(_ raw: String, cap: Int) -> String? {
        let cleaned = sanitize(raw)
        guard !cleaned.isEmpty, fits(cleaned, cap: cap) else { return nil }
        return cleaned
    }

    /// Removes every format character (Unicode category Cf: bidirectional
    /// controls, zero-width characters, the soft hyphen, interlinear
    /// annotation marks, the deprecated format controls) except the
    /// zero-width joiner, which emoji sequences need, and the tag
    /// characters; turns line breaks (control characters such as newlines and
    /// tabs, and the Unicode line and paragraph separators) into spaces, and
    /// trims. Nothing else changes: Markdown stays literal (the card draws it
    /// with `Text(verbatim:)`).
    static func sanitize(_ raw: String) -> String {
        var scalars = String.UnicodeScalarView()
        for scalar in raw.unicodeScalars {
            if isInvisibleFormatting(scalar) { continue }
            let breaks = scalar.properties.generalCategory == .control
                || scalar.value == 0x2028 || scalar.value == 0x2029
            scalars.append(breaks ? " " : scalar)
        }
        return String(scalars).trimmingCharacters(in: .whitespaces)
    }

    private static func isInvisibleFormatting(_ scalar: Unicode.Scalar) -> Bool {
        switch scalar.value {
        case 0x200D:            // zero-width joiner: kept, emoji sequences need it
            return false
        case 0x180E,            // Mongolian vowel separator (Cf before Unicode 6.3)
             0xE0000...0xE007F: // tag characters, assigned or not (can carry hidden text)
            return true
        default:
            // Cf: U+00AD, U+061C, U+200B-200F, U+202A-202E, U+2060-2064,
            // U+2066-206F, U+FEFF, U+FFF9-FFFB, and the rest of the category.
            return scalar.properties.generalCategory == .format
        }
    }

    /// Lowercase letters, digits and hyphens, at most 64: the id becomes a
    /// stable slide id and a `news.seen` entry, so it stays boring.
    static func isValidID(_ id: String) -> Bool {
        guard (1...64).contains(id.count) else { return false }
        return id.unicodeScalars.allSatisfy {
            ("a"..."z").contains($0) || ("0"..."9").contains($0) || $0 == "-"
        }
    }

    /// `https://bristlenose.app/<allowed path>`, parsed with `URLComponents`:
    /// no user, password or port; no encoded or dot segments in the path.
    static func validateLink(_ raw: String) -> URL? {
        guard let components = URLComponents(string: raw),
              components.scheme == "https",
              components.encodedHost == linkHost,
              components.user == nil, components.password == nil,
              components.port == nil
        else { return nil }
        let path = components.percentEncodedPath
        guard !path.contains("%"), !path.contains("//"), !path.contains("\\"),
              !path.split(separator: "/").contains(where: { $0 == "." || $0 == ".." }),
              isAllowedPath(path),
              let url = components.url, url.host == linkHost
        else { return nil }
        return url
    }

    static func isAllowedPath(_ path: String) -> Bool {
        linkPathAllowlist.contains { entry in
            entry.hasSuffix("/") ? path.hasPrefix(entry) : (path == entry || path == entry + "/")
        }
    }

    /// The interface language, then its bases (`zh-Hant-HK` → `zh-Hant` → `zh`).
    /// No fallback to English: an `en` item reaches only an English interface.
    static func matchLocale(interface: String, offered: [String]) -> String? {
        var candidate = interface.replacingOccurrences(of: "_", with: "-")
        while !candidate.isEmpty {
            if let hit = offered.first(where: {
                $0.replacingOccurrences(of: "_", with: "-")
                    .caseInsensitiveCompare(candidate) == .orderedSame
            }) { return hit }
            guard let cut = candidate.lastIndex(of: "-") else { break }
            candidate = String(candidate[..<cut])
        }
        return nil
    }

    // MARK: - Small helpers

    static func isPlainVersion(_ version: String) -> Bool { versionParts(version) != nil }

    /// `X.Y.Z`, digits only. Anything else is not a version we compare.
    static func versionParts(_ version: String) -> [Int]? {
        let parts = version.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3 else { return nil }
        let numbers = parts.compactMap { part -> Int? in
            guard !part.isEmpty, part.count <= 9,
                  part.unicodeScalars.allSatisfy({ ("0"..."9").contains($0) })
            else { return nil }
            return Int(part)
        }
        return numbers.count == 3 ? numbers : nil
    }

    private static let utc: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }()

    static func utcDay(_ date: Date) -> DateComponents {
        utc.dateComponents([.year, .month, .day], from: date)
    }

    static func utcMonth(_ date: Date) -> DateComponents {
        utc.dateComponents([.year, .month], from: date)
    }
}

/// One card's worth of news, after every rule. Text fields are verbatim: draw
/// them with `Text(verbatim:)`, never through the Markdown path.
struct NewsItem: Equatable, Identifiable, Sendable {
    /// The file's item id: stable across loads, so the rotator can key a slide
    /// (and persist its position) by it, never by index or `UUID()`.
    let id: String
    /// Picks the app-owned colour set per palette and the localised eyebrow.
    let tone: NewsCheck.Tone
    /// The locale whose copy this is.
    let locale: String
    let title: String
    let text: String
    let more: String?
    /// The link's text. A control: never truncated.
    let link: String
    let href: URL
    let from: Date
    let until: Date
}
