import Foundation
import Testing
@testable import Bristlenose

/// What the native "Send to Miro" sheet starts from: flat colour (owner, 19 Oct 2026), and no
/// clip links while they are parked (`BristlenoseFlags.boardClipLinks`).
@MainActor
@Suite("Miro sheet defaults")
struct MiroSheetDefaultsTests {

    @Test("colours flat until the researcher picks sentiment")
    func flatByDefault() {
        let m = MiroSheetModel(port: 0, token: nil, projectName: "Talismanic", i18n: I18n())
        #expect(m.colourBySentiment == false)
    }

    @Test("the clip-links choice follows the parked flag it is handed")
    func clipLinksFollowTheFlag() {
        let off = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: I18n(),
                                 clipLinksOffered: false)
        let on = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: I18n(),
                                clipLinksOffered: true)
        #expect(!off.clipLinksOffered && on.clipLinksOffered)
    }
}
