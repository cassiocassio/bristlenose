import Foundation
import Testing

@testable import Bristlenose

/// BR-11: the sheet shown after switching language must not claim the app
/// will not use the new language. The window changes at once; only the menu
/// bar waits for a relaunch.
@Suite("Relaunch sheet copy")
@MainActor
struct RelaunchSheetCopyTests {
    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("bristlenose/locales")

    private func i18n() -> I18n {
        let i = I18n()
        i.configure(localesDirectory: Self.localesURL)
        i.setLocale("en")
        return i
    }

    @Test func idleSheetKeepsTitleBodyAndBothButtons() {
        let k = RelaunchSheetCopy.keys(busy: false)
        #expect(k.message == "settings.language.relaunchTitle")
        #expect(k.detail == "settings.language.relaunchBody")
        #expect(k.buttons == ["settings.language.relaunchNow", "settings.language.dontRelaunch"])
    }

    @Test func analysingSheetStatesTheConsequenceAndOffersOnlyOK() {
        let k = RelaunchSheetCopy.keys(busy: true)
        #expect(k.message == "settings.language.relaunchBody")
        #expect(k.detail == nil)
        #expect(k.buttons == ["common.buttons.ok"])
    }

    @Test func bodyNamesTheMenusAndDoesNotSayNothingChanges() {
        let body = i18n().t("settings.language.relaunchBody")
        #expect(body == "Menus update after you relaunch.")
        #expect(body.split(separator: " ").count < 8)
        #expect(!body.contains("until"))
    }
}
