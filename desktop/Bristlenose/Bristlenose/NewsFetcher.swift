import CryptoKit
import Foundation
import os

// MARK: - State keys

/// Where the check keeps its state (spec §3, "Local state"). Debug builds use
/// a `news.debug.` prefix so a staging file can never move a Release build's
/// replay floor (`maxIssued`) or its counts.
struct NewsStateKeys {
    let prefix: String

    static let production = NewsStateKeys(prefix: "news.")
    static let debug = NewsStateKeys(prefix: "news.debug.")

    var lastCheck: String { prefix + "lastCheck" }
    var everChecked: String { prefix + "everChecked" }
    var welcomeSinceCheck: String { prefix + "welcomeSinceCheck" }
    /// Local dates the app was opened since the last `month` check (`days`).
    var daysOpened: String { prefix + "daysOpened" }
    /// Server clock minus Mac clock at the last response.
    var clockOffset: String { prefix + "clockOffset" }
    /// The latest believed server `Date`; only moves forward (`month`).
    var latestServerDate: String { prefix + "latestServerDate" }
    /// The last verified envelope, stored as received; re-verified on every load.
    var envelope: String { prefix + "envelope" }
    var maxIssued: String { prefix + "maxIssued" }
    /// SHA-256 of the payload that set `maxIssued` (so a re-fetch of the same
    /// file after the cache was deleted is not mistaken for a replay).
    var maxIssuedDigest: String { prefix + "maxIssuedDigest" }
    /// Ids hidden after a click, capped at `NewsCheck.maxSeenIDs`.
    var seen: String { prefix + "seen" }
    /// Key ids revoked by a backup-key file. Permanent.
    var revoked: String { prefix + "revoked" }
}

// MARK: - Fetcher

/// The daily news check: one bare request a day to bristlenose.app, plus the
/// counting flags when the person said yes. All decisions are in `NewsCheck`;
/// this does the I/O.
///
/// **Ownership.** An app-level object, like `ServeFleet`: a `@StateObject`
/// in `BristlenoseApp`, which calls `checkIfDue()` once the first window is up
/// and again on wake and on activation (never on a timer), `recordAppOpened()`
/// at launch and on every activation, and hands it to the
/// Welcome window, which asks `currentItems()` once per window and calls
/// `recordWelcomeShown()` once per window, and to Settings ▸ General. Two
/// windows must share one instance, because the single-flight guard below is
/// what stops a launch and a wake from both sending `first=1`.
@MainActor
final class NewsFetcher: ObservableObject {

    /// The current displayable items, from the **cached** verified file only.
    /// A fetch refreshes the cache and then this. A welcome window does not
    /// read it: it asks `currentItems()` once when it builds its slides, so
    /// the time window, the file's expiry and clicks are judged at that moment
    /// and a slide never jumps under a reader.
    @Published private(set) var items: [NewsItem] = []

    /// What one `checkIfDue()` did. For tests and logs; nothing is shown.
    enum Outcome: Equatable {
        case newsOff
        case firstRunUnanswered
        /// The build trusts no key, so no file could be accepted: no request.
        case noKeys
        case noEndpoint
        case notDue
        case alreadyInFlight
        /// A recent transport failure: no retry in this process until
        /// `transportBackoff` has passed (activation fires on every Cmd-Tab).
        case backingOff
        case transportFailure
        /// An HTTP response that was not an acceptable file (the flags are spent).
        case notAFile(status: Int)
        case rejected(NewsCheck.Rejection)
        case accepted
    }

    /// Everything the fetcher touches, injectable for tests.
    struct World {
        var defaults: UserDefaults
        var session: URLSession
        /// `nil`: make no request (a debug build without the seed).
        var endpoint: URL?
        var policy: NewsCheck.VerifyPolicy
        var channel: NewsCheck.Channel?
        var appVersion: String
        var keys: NewsStateKeys
        var interfaceLanguage: () -> String
        /// True once the first-run disclosure has been answered.
        var firstRunAnswered: () -> Bool
        var isManaged: (String) -> Bool
        var now: () -> Date
        var timeout: TimeInterval = 10
        /// The Mac's time zone, for the local dates behind `days`.
        var timeZone: () -> TimeZone = { .current }
        /// The app's subscription state, for `sub`. `nil`: no store (a `.dmg`,
        /// a debug build), so `sub` is never sent. Set by the app through
        /// `readSubscription(from:)` once its `SubscriptionGate` exists.
        var subscription: @MainActor () -> SubscriptionAccess.State? = { nil }
        /// How long a `month` check on the store waits for a store that has not
        /// answered yet (`NewsCheck.awaitsSubscription`) before going without `sub`.
        var subscriptionWait: TimeInterval = 20
    }

    private var world: World
    private var inFlight = false
    /// Set by a transport failure; the next attempt waits until then.
    private var retryNotBefore: Date?
    /// A `Date` header too far from the Mac's clock is logged once a process.
    private var loggedUnbelievedDate = false
    /// How long a transport failure holds the next attempt off. The flags are
    /// kept meanwhile, so nothing is lost by waiting.
    static let transportBackoff: TimeInterval = 30 * 60
    private static let log = Logger(subsystem: "app.bristlenose", category: "news")

    init(world: World) {
        self.world = world
        dropCountsIfOff()
        reloadFromCache()
    }

    /// The real world. In Release: the production endpoint (through the same
    /// `FeedbackEndpoint.validate` gate as the feedback sheet), the production
    /// keys, `env` `prod`. In Debug: no request at all unless
    /// `BRISTLENOSE_DEBUG_NEWS_URL` is set, and then only the staging key and
    /// `env` `staging`.
    static func productionWorld() -> World {
        let endpoint: URL?
        let policy: NewsCheck.VerifyPolicy
        let keys: NewsStateKeys
        #if DEBUG
        endpoint = ProcessInfo.processInfo.environment["BRISTLENOSE_DEBUG_NEWS_URL"]
            .flatMap(debugEndpoint)
        policy = .init(keyring: NewsKeys.stagingKeyring, requiredEnv: NewsCheck.stagingEnv)
        keys = .debug
        #else
        endpoint = FeedbackEndpoint.validate(NewsCheck.productionEndpoint.absoluteString)
        policy = .init(keyring: NewsKeys.productionKeyring, requiredEnv: NewsCheck.productionEnv)
        keys = .production
        #endif
        return World(
            defaults: .standard,
            session: CloudNetworking.makeSession(delegate: LLMValidator.RefuseRedirects()),
            endpoint: endpoint,
            policy: policy,
            channel: NewsCheck.Channel.from(.current),
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "",
            keys: keys,
            interfaceLanguage: { I18n.resolvedLocale },
            // The news notice and the counting choice sit on the AI disclosure
            // (spec D1), so "answered" is that disclosure at its current version.
            firstRunAnswered: {
                UserDefaults.standard.integer(forKey: "aiConsentVersion")
                    >= AIConsentView.currentVersion
            },
            isManaged: NewsPreferences.isManaged,
            now: Date.init)
    }

    #if DEBUG
    /// The debug seed: `https` anywhere, or plain `http` on loopback only.
    static func debugEndpoint(_ raw: String) -> URL? {
        guard let url = URL(string: raw), let host = url.host?.lowercased() else { return nil }
        switch url.scheme?.lowercased() {
        case "https": return url
        case "http" where host == "127.0.0.1" || host == "localhost": return url
        default: return nil
        }
    }
    #endif

    /// Where `sub` is read: the app's `SubscriptionGate`, which the app makes
    /// beside this fetcher, so it is handed over once both exist.
    func readSubscription(from source: @escaping @MainActor () -> SubscriptionAccess.State?) {
        world.subscription = source
    }

    // MARK: Switches

    var newsEnabled: Bool {
        NewsPreferences.newsEnabled(in: world.defaults, isForced: world.isManaged)
    }

    var countsConsent: NewsCheck.CountsConsent {
        NewsPreferences.countsConsent(in: world.defaults, isForced: world.isManaged)
    }

    /// Call when the news switch changes. Off deletes the cached file and the
    /// stored counts at once.
    func newsSwitchChanged() {
        if !newsEnabled { deleteCache() }
        dropCountsIfOff()
        reloadFromCache()
    }

    /// Call when the analytics switch changes. Off deletes the stored counts
    /// (days opened, welcome views) at once, not at the next response.
    func countsSwitchChanged() {
        dropCountsIfOff()
    }

    /// With news off or counting anything but a yes (the person's switch or a
    /// managed preference), nothing counted is kept. Also run at launch and at
    /// every check and record, which is how a managed preference that arrives
    /// while the app runs takes effect.
    private func dropCountsIfOff() {
        guard !newsEnabled || countsConsent != .yes else { return }
        world.defaults.removeObject(forKey: world.keys.daysOpened)
        world.defaults.removeObject(forKey: world.keys.welcomeSinceCheck)
    }

    // MARK: The check

    /// At launch or wake. Makes at most one request per server-UTC day.
    @discardableResult
    func checkIfDue() async -> Outcome {
        dropCountsIfOff()
        guard newsEnabled else {
            deleteCache()
            return .newsOff
        }
        guard world.firstRunAnswered() else { return .firstRunUnanswered }
        guard NewsCheck.mayRequest(with: world.policy.keyring) else { return .noKeys }
        guard let endpoint = world.endpoint else { return .noEndpoint }
        guard !inFlight else { return .alreadyInFlight }
        if let retryNotBefore, world.now() < retryNotBefore { return .backingOff }

        var before = loadState()
        var serverNow = NewsCheck.estimatedServerNow(before, localNow: world.now())
        guard NewsCheck.isDue(before, serverNow: serverNow) else { return .notDue }

        inFlight = true
        defer { inFlight = false }

        // A launch check that would carry `sub` waits, bounded, for the store's
        // first answer; past the wait it goes without `sub`.
        var subscription = world.subscription()
        if NewsCheck.awaitsSubscription(state: before, consent: countsConsent,
                                        channel: world.channel, subscription: subscription,
                                        serverNow: serverNow) {
            let step: TimeInterval = 0.25
            var waited: TimeInterval = 0
            while subscription == .unknown, waited < world.subscriptionWait {
                try? await Task.sleep(nanoseconds: UInt64(step * 1_000_000_000))
                waited += step
                subscription = world.subscription()
            }
            // The switches may have changed during the wait: off means no
            // request at all, and nothing counted is kept.
            dropCountsIfOff()
            guard newsEnabled else {
                deleteCache()
                return .newsOff
            }
            before = loadState()
            serverNow = NewsCheck.estimatedServerNow(before, localNow: world.now())
        }

        let consent = countsConsent
        let query = NewsCheck.query(state: before, consent: consent,
                                    appVersion: world.appVersion, channel: world.channel,
                                    subscription: NewsCheck.SubscriptionFlag.from(subscription),
                                    localDay: NewsCheck.localDay(world.now(), in: world.timeZone()),
                                    serverNow: serverNow)
        guard let url = query.url(base: endpoint) else { return .noEndpoint }
        // The version reaches the host's log in the User-Agent too, so it
        // rides there only with the same yes that puts `v` in the query.
        let result = await Self.fetch(
            Self.request(url, appVersion: consent == .yes ? world.appVersion : nil,
                         timeout: world.timeout),
            session: world.session, cap: NewsCheck.maxEnvelopeBytes, deadline: world.timeout)

        guard case let .response(status, contentType, serverDate, body) = result else {
            // No response at all: the flags are kept for the next try, which
            // waits out the backoff rather than following every activation.
            retryNotBefore = world.now().addingTimeInterval(Self.transportBackoff)
            return .transportFailure
        }
        retryNotBefore = nil
        let arrived = world.now()
        if serverDate != nil, NewsCheck.trustedServerDate(serverDate, localNow: arrived) == nil,
           !loggedUnbelievedDate {
            loggedUnbelievedDate = true
            Self.log.info("news response Date is more than 3 days from the Mac's clock; using the Mac's")
        }
        // Any HTTP response reached the log: the flags are spent. Re-read the
        // state so views recorded during the request are kept.
        let after = NewsCheck.afterResponse(loadState(), sent: query, serverDate: serverDate,
                                            localNow: arrived)
        saveState(after)

        // News was switched off while the request was out: the flags are
        // spent (the request reached the log), but nothing it brought is kept,
        // the replay floor does not move, and the cache stays deleted.
        guard newsEnabled else {
            deleteCache()
            return .newsOff
        }

        guard NewsCheck.isAcceptableResponse(status: status, contentType: contentType),
              let body
        else { return .notAFile(status: status) }

        let verification = NewsCheck.verify(
            envelope: body, policy: world.policy, revoked: revoked,
            freshness: freshness,
            // The believed `Date`, or the Mac's clock (`afterResponse`).
            now: NewsCheck.estimatedServerNow(after, localNow: arrived))
        recordRevocations(verification.newRevocations)
        switch verification.result {
        case .failure(let reason):
            Self.log.info("news file refused: \(String(describing: reason), privacy: .public)")
            reloadFromCache()
            return .rejected(reason)
        case .success(let file):
            world.defaults.set(body, forKey: world.keys.envelope)
            world.defaults.set(file.issued, forKey: world.keys.maxIssued)
            world.defaults.set(file.payloadDigest, forKey: world.keys.maxIssuedDigest)
            reloadFromCache()
            return .accepted
        }
    }

    // MARK: Welcome window, app opened, and clicks

    /// Once per welcome window shown. Counted only while counting is on.
    func recordWelcomeShown() {
        dropCountsIfOff()
        guard newsEnabled else { return }
        saveState(NewsCheck.recordWelcomeShown(loadState(), consent: countsConsent))
    }

    /// At launch and on every activation (`days`). One entry per local date,
    /// and only while news is on and counting is a yes.
    func recordAppOpened() {
        dropCountsIfOff()
        guard newsEnabled else { return }
        let day = NewsCheck.localDay(world.now(), in: world.timeZone())
        saveState(NewsCheck.recordAppOpened(loadState(), consent: countsConsent, localDay: day))
    }

    /// After an item's link was clicked. A `news` item then hides for this
    /// install from the next load (not at once, so the open card does not
    /// jump). `community` items never hide: their `until` ends them.
    func recordClick(on item: NewsItem) {
        guard item.tone.hidesAfterClick else { return }
        let seen = world.defaults.stringArray(forKey: world.keys.seen) ?? []
        world.defaults.set(NewsCheck.markSeen(seen, id: item.id), forKey: world.keys.seen)
    }

    // MARK: Cache

    /// Re-verifies the stored envelope and republishes `items` from it.
    func reloadFromCache() {
        items = currentItems()
    }

    /// The items to show if a window were built now: the stored envelope
    /// re-verified (signature, revocation, freshness, expiry, `env`), then
    /// filtered at this moment (each item's `from`/`until`, clicked `news`
    /// items). Publishes nothing, so a view may call it while building.
    func currentItems() -> [NewsItem] {
        guard newsEnabled,
              let envelope = world.defaults.data(forKey: world.keys.envelope)
        else { return [] }
        // Never earlier than the newest verified file's `issued`: a clock set
        // back cannot bring an item past its `until` back.
        let serverNow = NewsCheck.notBeforeNewestFile(
            NewsCheck.estimatedServerNow(loadState(), localNow: world.now()), freshness)
        let verification = NewsCheck.verify(envelope: envelope, policy: world.policy,
                                            revoked: revoked, freshness: freshness,
                                            now: serverNow)
        guard case let .success(file) = verification.result else { return [] }
        let context = NewsCheck.DisplayContext(
            channel: world.channel, appVersion: world.appVersion,
            interfaceLanguage: world.interfaceLanguage(), now: serverNow,
            hiddenIDs: Set(world.defaults.stringArray(forKey: world.keys.seen) ?? []))
        return NewsCheck.displayableItems(file, context: context)
    }

    private func deleteCache() {
        world.defaults.removeObject(forKey: world.keys.envelope)
        items = []
    }

    // MARK: State persistence

    private func loadState() -> NewsCheck.State {
        let d = world.defaults, k = world.keys
        return NewsCheck.State(
            lastCheck: d.object(forKey: k.lastCheck) as? Date,
            everChecked: d.bool(forKey: k.everChecked),
            welcomeSinceCheck: d.integer(forKey: k.welcomeSinceCheck),
            clockOffset: d.double(forKey: k.clockOffset),
            daysOpened: d.stringArray(forKey: k.daysOpened) ?? [],
            latestServerDate: d.object(forKey: k.latestServerDate) as? Date)
    }

    private func saveState(_ state: NewsCheck.State) {
        let d = world.defaults, k = world.keys
        d.set(state.lastCheck, forKey: k.lastCheck)
        d.set(state.everChecked, forKey: k.everChecked)
        d.set(state.welcomeSinceCheck, forKey: k.welcomeSinceCheck)
        d.set(state.clockOffset, forKey: k.clockOffset)
        d.set(state.daysOpened, forKey: k.daysOpened)
        d.set(state.latestServerDate, forKey: k.latestServerDate)
    }

    private var freshness: NewsCheck.Freshness {
        NewsCheck.Freshness(
            maxIssued: world.defaults.object(forKey: world.keys.maxIssued) as? Date,
            maxIssuedDigest: world.defaults.data(forKey: world.keys.maxIssuedDigest))
    }

    private var revoked: Set<String> {
        Set(world.defaults.stringArray(forKey: world.keys.revoked) ?? [])
    }

    /// Permanent. A new revocation also clears the replay floor, because a
    /// leaked key may have pushed it into the future (up to the 2-day
    /// allowance) to keep the backup key's revocation file out.
    private func recordRevocations(_ new: Set<String>) {
        guard !new.isEmpty else { return }
        world.defaults.set(Array(revoked.union(new)).sorted(), forKey: world.keys.revoked)
        world.defaults.removeObject(forKey: world.keys.maxIssued)
        world.defaults.removeObject(forKey: world.keys.maxIssuedDigest)
        Self.log.notice("news key revoked: \(new.sorted().joined(separator: ","), privacy: .public)")
    }

    // MARK: Transport

    /// `GET`, an explicit `User-Agent`, and an empty `Accept-Language`. Setting
    /// it empty is the only way to stop CFNetwork filling in the weighted
    /// language list (measured 16 Nov 2026: an unset header sent
    /// `en-GB,en;q=0.9`; an empty one sends the header with no value).
    /// `appVersion` nil (no counts yes): the User-Agent is plain `Bristlenose`.
    nonisolated static func request(_ url: URL, appVersion: String?,
                                    timeout: TimeInterval) -> URLRequest {
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData,
                                 timeoutInterval: timeout)
        request.httpMethod = "GET"
        request.httpShouldHandleCookies = false
        let agent = appVersion.map { "Bristlenose/\($0)" } ?? "Bristlenose"
        request.setValue(agent, forHTTPHeaderField: "User-Agent")
        request.setValue("", forHTTPHeaderField: "Accept-Language")
        return request
    }

    enum FetchResult: Equatable, Sendable {
        case transportFailure
        /// `body` is nil when it ran over the cap or broke off mid-way.
        case response(status: Int, contentType: String?, serverDate: Date?, body: Data?)
    }

    /// One attempt. The byte cap is enforced as bytes arrive, never from
    /// `Content-Length`; the deadline covers the whole exchange.
    nonisolated static func fetch(_ request: URLRequest, session: URLSession, cap: Int,
                                  deadline: TimeInterval) async -> FetchResult {
        let work = Task { () -> FetchResult in
            let bytes: URLSession.AsyncBytes
            let response: URLResponse
            do {
                (bytes, response) = try await session.bytes(for: request)
            } catch {
                return .transportFailure
            }
            guard let http = response as? HTTPURLResponse else { return .transportFailure }
            let status = http.statusCode
            let contentType = http.value(forHTTPHeaderField: "Content-Type")
            let serverDate = NewsCheck.parseHTTPDate(http.value(forHTTPHeaderField: "Date"))
            var body = Data()
            do {
                for try await byte in bytes {
                    body.append(byte)
                    if body.count > cap {
                        bytes.task.cancel()
                        return .response(status: status, contentType: contentType,
                                         serverDate: serverDate, body: nil)
                    }
                }
            } catch {
                return .response(status: status, contentType: contentType,
                                 serverDate: serverDate, body: nil)
            }
            return .response(status: status, contentType: contentType,
                             serverDate: serverDate, body: body)
        }
        let watchdog = Task {
            try? await Task.sleep(nanoseconds: UInt64(max(deadline, 0) * 1_000_000_000))
            if !Task.isCancelled { work.cancel() }
        }
        let result = await work.value
        watchdog.cancel()
        return result
    }
}
