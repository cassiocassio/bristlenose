import Foundation
import Testing
@testable import Bristlenose

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
}
