import Foundation
import Testing
@testable import Bristlenose

/// The Miro client's reason table: a refusal the server names reaches the sheet in the reader's
/// language, never as the server's English `detail` (docs/i18n-defects.md row 46, R94).
@Suite("Miro API reasons")
struct MiroAPITests {

    @Test("starting a board while not connected has a sentence")
    func notConnectedIsTranslated() {
        #expect(MiroAPI.errorKeys["not_connected"] == "common.miro.errNotConnected")
    }
}
