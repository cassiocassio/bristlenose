import Foundation
import Network
import Testing
@testable import Bristlenose

/// A loopback server that accepts a connection, reads the request and never answers, so a
/// status check against it is still in flight when the test cancels it.
///
/// The tests wait on its signals, not on a clock: under a full suite the main queue, where the
/// listener runs, is shared with every other main-actor test, and a 10 s poll ran out there
/// before the request had been read (24 Oct 2026). The bound is the test's `.timeLimit`.
private final class SilentServe: @unchecked Sendable {
    private let listener: NWListener
    /// Held so the accepted connections stay open; main queue only, where the listener runs.
    private var connections: [NWConnection] = []
    /// Set once a request has arrived; main queue only.
    private(set) var requestArrived = false
    /// Fires once the listener is ready, or has failed (which leaves `port` at 0).
    let listening = MainSignal()
    /// Fires once a request has arrived, or `giveUp()` was called first.
    let requested = MainSignal()

    init() throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 0)
        listener = try NWListener(using: params)
        let listening = self.listening
        listener.stateUpdateHandler = { state in
            switch state {
            case .ready, .failed, .cancelled: MainActor.assumeIsolated { listening.fire() }
            default: break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else { connection.cancel(); return }
            self.connections.append(connection)
            connection.start(queue: .main)
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { data, _, _, _ in
                guard data != nil else { return }
                self.requestArrived = true
                MainActor.assumeIsolated { self.requested.fire() }
            }
        }
        listener.start(queue: .main)
    }

    var port: UInt16 { listener.port?.rawValue ?? 0 }

    @MainActor func ready() async { await listening.wait() }

    @MainActor func request() async { await requested.wait() }

    /// Stop `request()` waiting: what it was waiting alongside ended without a request.
    @MainActor func giveUp() { requested.fire() }

    func stop() {
        connections.forEach { $0.cancel() }
        listener.cancel()
    }
}

/// A status check that fails is not "signed out" (R78): the sheet keeps the Connect step and its
/// error line says why, rather than offering Connect as if no token were stored.
@MainActor
@Suite("Miro sheet status check")
struct MiroSheetStatusTests {

    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("bristlenose/locales")

    private func english() -> I18n {
        let i = I18n()
        i.configure(localesDirectory: Self.localesURL)
        i.setLocale("en")
        return i
    }

    @Test("a server that cannot be reached says so on the Connect step")
    func unreachableSaysSo() async {
        let i18n = english()
        let key = "common.miro.serverUnreachable"
        #expect(i18n.t(key) != key)  // the sentence resolves, so the check below is about copy
        // Port 0 refuses at once: the transport fails, as it does when the sidecar is gone.
        let m = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: i18n)
        await m.load()
        #expect(m.step == .connect)
        #expect(m.error == i18n.t(key))
    }

    @Test("closing the sheet mid-load is a cancel, not an unreachable server", .timeLimit(.minutes(1)))
    func cancelledLoadLeavesNoError() async throws {
        let serve = try SilentServe()
        defer { serve.stop() }
        await serve.ready()
        try #require(serve.port != 0, "precondition: the loopback server is listening")

        let m = MiroSheetModel(port: Int(serve.port), token: nil, projectName: "p", i18n: english())
        let load = Task { await m.load() }
        // A load that ends without asking the server wakes the wait, and fails the check below.
        Task { await load.value; serve.giveUp() }
        // Wait on the request reaching the server, so the cancel lands on a check in flight.
        await serve.request()
        try #require(serve.requestArrived, "precondition: the status check is in flight")

        load.cancel()
        await load.value

        #expect(m.error == nil, "a cancelled load wrote an error nobody sees")
        #expect(m.step == .loading, "a cancelled load moved the sheet off its loading step")
    }

    @Test("connecting while the server is down says so, not 'check the token'")
    func connectUnreachableSaysSo() async {
        let i18n = english()
        let key = "common.miro.serverUnreachable"
        #expect(i18n.t(key) != key)
        #expect(i18n.t(key) != i18n.t("common.miro.connectError"), "precondition: the two lines differ")
        // Port 0 refuses at once, as a gone sidecar does; the token is never the question.
        let m = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: i18n)
        m.token = "pasted-token"
        await m.connect()
        #expect(m.error == i18n.t(key))
        #expect(m.busy == false)
    }

    @Test("cancelling a board build mid-request is a cancel, not an error", .timeLimit(.minutes(1)))
    func cancelledBuildLeavesNoError() async throws {
        let serve = try SilentServe()
        defer { serve.stop() }
        await serve.ready()
        try #require(serve.port != 0, "precondition: the loopback server is listening")

        let m = MiroSheetModel(port: Int(serve.port), token: nil, projectName: "p", i18n: english())
        m.createBoard()
        #expect(m.step == .creating)
        // A build that ends without asking the server wakes the wait, and fails the check below.
        let build = try #require(m.exportTask, "precondition: the build started")
        Task { await build.value; serve.giveUp() }
        // Wait on the start request reaching the server, so the cancel lands on a call in flight.
        await serve.request()
        try #require(serve.requestArrived, "precondition: the start request is in flight")

        m.cancelExport()
        await build.value

        #expect(m.error == nil, "a cancelled build wrote an error nobody sees")
        #expect(m.step == .creating, "a cancelled build moved the dismissed sheet back to its form")
    }
}
