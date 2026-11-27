import Foundation
import Testing
@testable import Bristlenose

/// The board sheets' words that pixels cannot show or a review keeps missing
/// (docs/mockups/form-layout-v2.html): the Mac's buttons and segments in title case, through
/// `desktop.miro.*` overrides while the browser keeps the shared sentence-case strings (item 2),
/// and the FigJam form's controls named for VoiceOver by their labels (item 3).
@MainActor
@Suite("Board sheets — Mac titles and accessible names")
struct MiroSheetLabelTests {

    private func english() throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        return i18n
    }

    @Test("the Miro sheet's buttons and segments read the desktop overrides")
    func miroTitlesReadTheDesktopKeys() {
        // A bare I18n answers with the key, so this pins which key each title reads.
        let m = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: I18n())
        #expect(m.copyBoardTitle() == "desktop.miro.copyBoard")
        #expect(m.createBoardTitle() == "desktop.miro.createBoard")
        #expect(m.routeTitle(.app) == "desktop.miro.tabApp")
        #expect(m.routeTitle(.token) == "desktop.miro.tabToken")
    }

    @Test("in English the Mac titles are title case")
    func miroTitlesInEnglish() throws {
        let m = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: try english())
        #expect(m.copyBoardTitle() == "Copy Board Data")
        #expect(m.createBoardTitle() == "Create Board")
        #expect(m.routeTitle(.app) == "Miro App")
        #expect(m.routeTitle(.token) == "Developer Access Token")
    }

    @Test("the FigJam name field and shape radios are named by their labels")
    func figJamAccessibleNames() throws {
        let bare = FigJamSheetModel(port: 0, token: nil, projectName: "p", i18n: I18n())
        #expect(bare.boardNameLabel() == "desktop.miro.boardNameLabel")
        #expect(bare.stickyShapeGroupName() == "common.miro.stickyShape")
        let m = FigJamSheetModel(port: 0, token: nil, projectName: "p", i18n: try english())
        #expect(m.boardNameLabel() == "Board name:")
        #expect(m.stickyShapeGroupName() == "Sticky shape")
    }
}
