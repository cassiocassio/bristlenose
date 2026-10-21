import Foundation
import Network
import Testing
@testable import Bristlenose

/// A loopback server that accepts a connection, reads the request and never answers, so a
/// status check against it is still in flight when the test cancels it.
private final class SilentServe: @unchecked Sendable {
    private let listener: NWListener
    /// Held so the accepted connections stay open; main queue only, where the listener runs.
    private var connections: [NWConnection] = []
    /// Set once a request has arrived; main queue only.
    private(set) var requestArrived = false

    init() throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 0)
        listener = try NWListener(using: params)
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else { connection.cancel(); return }
            self.connections.append(connection)
            connection.start(queue: .main)
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { data, _, _, _ in
                if data != nil { self.requestArrived = true }
            }
        }
        listener.start(queue: .main)
    }

    var port: UInt16 { listener.port?.rawValue ?? 0 }

    func ready() async {
        let deadline = Date().addingTimeInterval(10)
        while port == 0, Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

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

    @Test("closing the sheet mid-load is a cancel, not an unreachable server")
    func cancelledLoadLeavesNoError() async throws {
        let serve = try SilentServe()
        defer { serve.stop() }
        await serve.ready()
        #expect(serve.port != 0, "precondition: the loopback server is listening")

        let m = MiroSheetModel(port: Int(serve.port), token: nil, projectName: "p", i18n: english())
        let load = Task { await m.load() }
        // Wait on the request reaching the server, so the cancel lands on a check in flight.
        let deadline = Date().addingTimeInterval(10)
        while !serve.requestArrived, Date() < deadline { try await Task.sleep(for: .milliseconds(10)) }
        #expect(serve.requestArrived, "precondition: the status check is in flight")

        load.cancel()
        await load.value

        #expect(m.error == nil, "a cancelled load wrote an error nobody sees")
        #expect(m.step == .loading, "a cancelled load moved the sheet off its loading step")
    }
}
