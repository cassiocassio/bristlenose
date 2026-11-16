import CryptoKit
import Foundation

/// The rules of the daily news check and its anonymous counts, with no
/// networking and no `UserDefaults`: every decision the check makes is a pure
/// function here, so each one is testable on its own. `NewsFetcher` is the
/// thin shell that does the I/O and calls these.
///
/// Spec: `docs/private/design-news-and-counts.md` (v2) §3 (the request), §4
/// (the file), §7 (settings) and §9 (keys). v1 is **text only**: images,
/// video and tints in a file are not read.
///
/// Three things this file guarantees, each pinned by `NewsCheckTests`:
/// 1. **No counts without a yes.** `query(…)` adds `v`, `ch`, `first`,
///    `month` and `w` only when the person said yes (`CountsConsent.yes`).
///    Unanswered and no both send the bare `s=1`.
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
    }

    /// The server's clock, estimated from the Mac's and the last measured offset.
    static func estimatedServerNow(_ state: State, localNow: Date) -> Date {
        localNow.addingTimeInterval(state.clockOffset)
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

        /// True when anything beyond `s` rides along.
        var carriesCounts: Bool {
            version != nil || channel != nil || first || month || welcome != nil
        }

        /// In the spec's order: `s`, `v`, `ch`, `first`, `month`, `w`. Flags
        /// are present only when set (`first=1`), never `first=0`.
        var queryItems: [URLQueryItem] {
            var items = [URLQueryItem(name: "s", value: String(NewsCheck.querySchema))]
            if let version { items.append(.init(name: "v", value: version)) }
            if let channel { items.append(.init(name: "ch", value: channel.rawValue)) }
            if first { items.append(.init(name: "first", value: "1")) }
            if month { items.append(.init(name: "month", value: "1")) }
            if let welcome { items.append(.init(name: "w", value: String(welcome))) }
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
    static func query(state: State, consent: CountsConsent, appVersion: String,
                      channel: Channel?, serverNow: Date) -> Query {
        guard consent == .yes else { return Query() }
        var query = Query()
        query.version = isPlainVersion(appVersion) ? appVersion : nil
        query.channel = channel
        query.first = !state.everChecked
        query.month = isFirstThisMonth(state, serverNow: serverNow)
        query.welcome = min(max(state.welcomeSinceCheck, 0), maxWelcomeSent)
        return query
    }

    /// First check this UTC calendar month by the server's clock. A server
    /// clock that has gone *backwards* past the last check makes no claim.
    static func isFirstThisMonth(_ state: State, serverNow: Date) -> Bool {
        guard let last = state.lastCheck else { return true }
        guard serverNow > last else { return false }
        return utcMonth(last) != utcMonth(serverNow)
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
    ///   - localNow: the Mac's clock when the response arrived.
    static func afterResponse(_ current: State, sent: Query, serverDate: Date?,
                              localNow: Date) -> State {
        var next = current
        if let serverDate {
            next.clockOffset = serverDate.timeIntervalSince(localNow)
            next.lastCheck = serverDate
        } else {
            next.lastCheck = estimatedServerNow(current, localNow: localNow)
        }
        if sent.carriesCounts {
            if sent.first { next.everChecked = true }
            next.welcomeSinceCheck = max(0, current.welcomeSinceCheck - (sent.welcome ?? 0))
        } else {
            // Views from a time the person had not said yes are not kept for later.
            next.welcomeSinceCheck = 0
        }
        return next
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
            guard cleaned.count <= caps.more else { return nil }
            more = cleaned.isEmpty ? nil : cleaned
        }
        guard let href = validateLink(raw.href) else { return nil }

        return NewsItem(id: raw.id, tone: tone, locale: locale, title: title,
                        text: text, more: more, link: link, href: href,
                        from: raw.from, until: raw.until)
    }

    /// A required text field: sanitised, non-empty, within its cap (in
    /// characters). Over the cap drops the item; it is never cut mid-word here.
    private static func field(_ raw: String, cap: Int) -> String? {
        let cleaned = sanitize(raw)
        guard !cleaned.isEmpty, cleaned.count <= cap else { return nil }
        return cleaned
    }

    /// Removes bidirectional controls, zero-width characters and tag
    /// characters, turns line breaks (control characters such as newlines and
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
        case 0x061C,           // Arabic letter mark
             0x180E,           // Mongolian vowel separator
             0x200B...0x200F,  // zero-width space/non-joiner/joiner, LRM, RLM
             0x202A...0x202E,  // LRE, RLE, PDF, LRO, RLO
             0x2060...0x2064,  // word joiner, invisible operators
             0x2066...0x2069,  // LRI, RLI, FSI, PDI
             0xFEFF,           // zero-width no-break space / BOM
             0xE0000...0xE007F: // tag characters (invisible; can carry hidden text)
            return true
        default:
            return false
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
