import Foundation
import Network
import os

// "This network can't reach Claude": the pill's third condition, drawn in section H of
// docs/mockups/provider-problem-surface.html. Unlike a rejected key or an empty account it
// is a fact about *where the person is*, so it is held in memory only, is never written to
// the key's saved verdict, and clears when the network does. The decisions here are pure;
// `ProviderProblemModel` holds the state and `LiveNetworkProbe` is the only code that
// touches the network.

/// Whether a refused call is worth asking "does the internet work?" about.
enum NetworkBlockCandidate {
    /// - Parameters mirror the fields of the sidecar's refusal line
    ///   (`bristlenose/llm/refusal_report.py`): `kind` is `LLMFailureKind`'s value, `phase`
    ///   where the call died, `providerSignature` whether the reply was the provider's own.
    ///
    /// A candidate is a call that died in connect or TLS, a name that would not resolve, or
    /// a reply that was not the provider's (a proxy's block page). Not a slow read (the
    /// server accepted the call), not an unknown phase, and never a local server, whose
    /// failure is not about this network. An Azure endpoint that does not resolve is
    /// almost certainly a mistyped resource name, since a made-up Azure host fails the
    /// same way (measured 2 Nov 2026), so it is not a candidate either.
    /// A failed run's provider, when only the run's structured cause (category network) is
    /// known and its phase is not. The run cannot say where its call died, so a slow read
    /// may pass; the SDK has retried six times by then, and the look still has to find the
    /// internet working. Still never a local server or Azure, whose failure here may be a
    /// mistyped endpoint.
    static func isRunCandidate(provider: LLMProvider) -> Bool {
        provider != .ollama && provider != .azure
    }

    static func isCandidate(
        provider: LLMProvider, kind: String, phase: String?, providerSignature: Bool?
    ) -> Bool {
        guard provider != .ollama else { return false }
        if providerSignature == false { return true }
        guard kind == "network" else { return false }
        switch phase {
        case "connect", "tls": return true
        case "dns": return provider != .azure
        default: return false
        }
    }
}

/// What the network path said when it was sampled. `signature` changes when the network
/// does (the interfaces, the gateway, whether a route exists), so a change is the cue to
/// drop a finding that was true of another place.
struct PathSnapshot: Equatable, Sendable {
    let satisfied: Bool
    let signature: String
}

/// The answer from Apple's connectivity-check address.
enum ControlResult: Equatable, Sendable {
    /// HTTPS 200 with Apple's "Success" body: the internet works.
    case reached
    /// An answer that was not that (a sign-in page, a redirect): the network is doing
    /// something, and this build does not name a portal, so it says nothing.
    case answeredOtherwise
    /// No answer: offline, internet down, or a TLS failure (a wrong clock, an inspecting
    /// proxy). None of those is "this network blocks Claude".
    case failed
}

/// Whether the provider's own server answered a keyless request from this Mac.
enum ProviderReach: Equatable, Sendable {
    /// A reply in the provider's own JSON shape (a 401 or 403 to a request with no key,
    /// measured 2 Nov 2026): the provider is reachable from here, whatever its status.
    case reached
    /// No reply, or a reply that was not the provider's (a proxy's block page).
    case notReached
}

enum NetworkBlockVerdict {
    /// The network blocks the provider when a route exists, the internet works (Apple
    /// answers) and the provider's own server, asked the same way from this Mac, does not.
    /// The provider check is what separates "this network" from a laptop that slept
    /// mid-run, a slow read, or an endpoint that was never right. A missing path sample
    /// (no update inside the budget) does not veto: the two answers decide.
    static func blocks(path: PathSnapshot?, control: ControlResult, provider: ProviderReach) -> Bool {
        (path?.satisfied ?? true) && control == .reached && provider == .notReached
    }
}

extension ControlResult {
    /// Apple's page: HTTP 200 whose title and body say Success. A portal or a proxy that
    /// merely mentions the word is not it.
    static func from(status: Int?, body: String) -> ControlResult {
        guard let status else { return .failed }
        return status == 200 && body.contains("<TITLE>Success</TITLE>") ? .reached : .answeredOtherwise
    }
}

extension ProviderReach {
    /// A reply counts as the provider's only if its body is JSON (an object). A proxy's page is
    /// HTML. Any status will do: a keyless request is refused by every provider.
    static func from(status: Int?, body: String) -> ProviderReach {
        guard status != nil else { return .notReached }
        let first = body.drop(while: { $0.isWhitespace }).first
        return first == "{" ? .reached : .notReached
    }
}

extension LLMProvider {
    /// A public endpoint that answers a request with no key (measured 2 Nov 2026: 401 or 403
    /// with a JSON error), used only to ask "can this Mac reach the provider at all". Nil for
    /// a provider with no fixed public host (Azure's is the user's, Ollama is local).
    var keylessProbeURL: URL? {
        switch self {
        case .claude: return URL(string: "https://api.anthropic.com/v1/models")
        case .chatGPT: return URL(string: "https://api.openai.com/v1/models")
        case .gemini: return URL(string: "https://generativelanguage.googleapis.com/v1beta/models")
        case .azure, .ollama: return nil
        }
    }
}

/// One look at the network, taken after a qualifying refusal and never on a timer.
protocol NetworkProbing: Sendable {
    func look(provider: LLMProvider) async
        -> (path: PathSnapshot?, control: ControlResult, provider: ProviderReach)
}

/// Cues the model when the network changes after a finding.
protocol NetworkPathWatching: AnyObject {
    /// `onChange` is called (on any thread) when the path differs from `baseline` (the
    /// signature the look saw), or from the first update when there was none.
    func start(baseline: String?, onChange: @escaping @Sendable () -> Void)
    func stop()
}

/// The only live network code: one HTTPS GET to Apple's check page and one keyless GET to the
/// provider's own public endpoint, with the path sampled beside them, under one budget.
/// Carries no key and no project data; Apple sees an address, a time and the app's
/// user-agent, as for any request. Plain HTTP is deliberately not used here: a portal is
/// not named in this build, so a cleartext request would buy nothing.
struct LiveNetworkProbe: NetworkProbing {
    private static let log = Logger(subsystem: "app.bristlenose", category: "network-probe")
    static let url = URL(string: "https://captive.apple.com/hotspot-detect.html")!
    var budget: TimeInterval = 3

    func look(provider: LLMProvider) async
        -> (path: PathSnapshot?, control: ControlResult, provider: ProviderReach) {
        async let path = LiveNetworkProbe.samplePath(within: min(1, budget))
        async let control = fetch(Self.url)
        async let reach = fetchIfAny(provider.keylessProbeURL)
        let (c, r) = await (control, reach)
        return (await path, ControlResult.from(status: c?.status, body: c?.body ?? ""),
                provider.keylessProbeURL == nil ? .reached
                    : ProviderReach.from(status: r?.status, body: r?.body ?? ""))
    }

    private func fetchIfAny(_ url: URL?) async -> (status: Int, body: String)? {
        guard let url else { return nil }
        return await fetch(url)
    }

    /// One GET, or nil when there was no answer. The error's code is logged: offline, a
    /// timeout, a TLS failure and a cancellation all mean no answer, which is never a
    /// finding by itself.
    private func fetch(_ url: URL) async -> (status: Int, body: String)? {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = budget
        config.timeoutIntervalForResource = budget
        config.waitsForConnectivity = false
        config.httpCookieStorage = nil
        config.urlCache = nil
        let session = URLSession(configuration: config)
        defer { session.finishTasksAndInvalidate() }
        do {
            let (data, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse else { return nil }
            return (http.statusCode, String(decoding: data.prefix(512), as: UTF8.self))
        } catch {
            let e = error as NSError
            Self.log.notice("probe of \(url.host ?? "?", privacy: .public) failed: \(e.domain, privacy: .public) \(e.code, privacy: .public)")
            return nil
        }
    }

    static func samplePath(within seconds: TimeInterval) async -> PathSnapshot? {
        await withCheckedContinuation { (continuation: CheckedContinuation<PathSnapshot?, Never>) in
            let monitor = NWPathMonitor()
            let gate = OSAllocatedUnfairLock(initialState: false)
            let finish: @Sendable (PathSnapshot?) -> Void = { value in
                let first = gate.withLock { done -> Bool in
                    if done { return false }
                    done = true
                    return true
                }
                if first {
                    monitor.cancel()
                    monitor.pathUpdateHandler = nil
                    continuation.resume(returning: value)
                }
            }
            monitor.pathUpdateHandler = { finish(Self.snapshot(of: $0)) }
            let queue = DispatchQueue(label: "app.bristlenose.network-probe.path")
            monitor.start(queue: queue)
            queue.asyncAfter(deadline: .now() + seconds) { finish(nil) }
        }
    }

    static func snapshot(of path: NWPath) -> PathSnapshot {
        return PathSnapshot(satisfied: path.status == .satisfied, signature: signature(of: path))
    }

    /// "The network changed" means a route appearing or going, or another interface taking
    /// over. Not the gateway list or an interface's other fields, which a VPN or a second
    /// update right after the first would shuffle, clearing the finding at once.
    static func signature(of path: NWPath) -> String {
        let names = Set(path.availableInterfaces.map(\.name)).sorted().joined(separator: ",")
        return "\(path.status)|\(names)"
    }
}

/// Watches the path after a finding: an update that differs from the baseline is the network
/// changing. The baseline is the signature the look saw (so a change during the look is not
/// lost), or the first update when there was none. Cancelled when the finding clears.
final class LivePathWatcher: NetworkPathWatching, @unchecked Sendable {
    private var monitor: NWPathMonitor?
    private let lock = OSAllocatedUnfairLock<String?>(initialState: nil)

    func start(baseline: String?, onChange: @escaping @Sendable () -> Void) {
        stop()
        lock.withLock { $0 = baseline }
        let monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [lock] path in
            let signature = LiveNetworkProbe.signature(of: path)
            let changed = lock.withLock { known -> Bool in
                guard let was = known else { known = signature; return false }
                return was != signature
            }
            if changed { onChange() }
        }
        monitor.start(queue: DispatchQueue(label: "app.bristlenose.network-probe.watch"))
        self.monitor = monitor
    }

    func stop() {
        monitor?.cancel()
        monitor?.pathUpdateHandler = nil
        monitor = nil
        lock.withLock { $0 = nil }
    }

    deinit { monitor?.cancel() }
}
