import Foundation
import Network
import Testing
@testable import Bristlenose

/// The native Miro sheet against a loopback server standing in for serve's board
/// job, so what the sheet shows is decided by what the wire said (21 Oct 2026).
///
/// - R79: a job that completed without a board link put up "Board ready", and
///   Open in Miro then did nothing with the empty address.

/// A loopback HTTP server answering serve's Miro board job: start, then status.
/// Same shape as `ExportSaveFlowTests`' FakeServe, answering JSON by path.
private final class MiroFakeServe: @unchecked Sendable {
    private let listener: NWListener
    /// The JSON body for each request path. Main queue only, where the listener runs.
    var answer: (String) -> String = { _ in "{}" }

    init() throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 0)
        listener = try NWListener(using: params)
        listener.newConnectionHandler = { [weak self] connection in
            connection.start(queue: .main)
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { data, _, _, _ in
                guard let self else { connection.cancel(); return }
                let request = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                let target = request.components(separatedBy: " ").dropFirst().first ?? "/"
                let path = URL(string: "http://127.0.0.1\(target)")?.path ?? target
                let body = self.answer(path)
                var head = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                head += "Content-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n"
                connection.send(content: Data((head + body).utf8),
                                completion: .contentProcessed { _ in connection.cancel() })
            }
        }
        listener.start(queue: .main)
    }

    var port: UInt16 { listener.port?.rawValue ?? 0 }

    func ready() async {
        let deadline = Date().addingTimeInterval(10)
        while port == 0, Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    func stop() { listener.cancel() }
}

@MainActor
@Suite("Miro sheet against the board job", .serialized)
struct MiroSheetContractTests {

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

    // MARK: R79

    @Test("a board that completes without a link is a failure, not Board ready")
    func completedWithoutALinkIsAnError() async throws {
        let serve = try MiroFakeServe()
        defer { serve.stop() }
        serve.answer = { path in
            path.hasSuffix("/miro/board/status")
                ? #"{"status":"completed","board_url":null,"stickies":3}"#
                : #"{"status":"started"}"#
        }
        await serve.ready()
        #expect(serve.port != 0, "precondition: the loopback server is listening")

        let i18n = english()
        let m = MiroSheetModel(port: Int(serve.port), token: nil, projectName: "p", i18n: i18n)
        m.createBoard()
        let deadline = Date().addingTimeInterval(10)
        while m.step == .creating, Date() < deadline { try await Task.sleep(for: .milliseconds(20)) }

        #expect(m.step == .configure, "a board with no link read as ready")
        #expect(m.error != nil)
        #expect(m.error == i18n.t("common.miro.exportError"))
        #expect(m.boardURL == nil)
    }
}
