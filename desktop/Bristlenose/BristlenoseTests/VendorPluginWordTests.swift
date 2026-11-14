import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// The Claude and ChatGPT tabs of Settings ▸ MCP Agents each say what that
/// vendor's own app says, per language (docs/i18n-vendor-terms.md). These read
/// the shipping locale files through the app's own `I18n`, pinned to a
/// language, so a key the tab asks for that resolves to nothing, or a vendor
/// noun that drifts back to one shared word, fails here and not on a user's
/// screen.
@MainActor
@Suite struct VendorPluginWordTests {

    private func i18n(_ locale: String) throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)
        return i18n
    }

    /// Every key a Claude-tab or ChatGPT-tab button asks for.
    private static let claudeKeys = [
        "desktop.mcpAgents.claudeInstall", "desktop.mcpAgents.claudeReinstall",
        "desktop.mcpAgents.claudeUpdate",
    ]
    private static let chatgptKeys = [
        "desktop.mcpAgents.chatgptInstall", "desktop.mcpAgents.chatgptReinstall",
        "desktop.mcpAgents.chatgptUpdate",
    ]

    @Test("every button key resolves to real text in every language, never the raw key")
    func everyButtonKeyResolves() throws {
        for locale in I18n.supportedLocales.sorted() {
            let i = try i18n(locale)
            for key in Self.claudeKeys + Self.chatgptKeys {
                let text = i.t(key)
                #expect(text != key && !text.isEmpty, "\(locale): \(key) resolved to \(text)")
            }
        }
    }

    @Test("Spanish: Plugins on the Claude tab, Complementos on the ChatGPT tab")
    func spanishSplitsTheVendors() throws {
        let es = try i18n("es")
        #expect(es.t("desktop.mcpAgents.claudeInstall") == "Instalar plugin\u{2026}")
        #expect(es.t("desktop.mcpAgents.chatgptInstall") == "Instalar complemento\u{2026}")
    }

    @Test("Catalan ChatGPT tab says Connectors, as the ChatGPT app does")
    func catalanChatGPTSaysConnector() throws {
        let ca = try i18n("ca")
        #expect(ca.t("desktop.mcpAgents.chatgptInstall").contains("connector"))
        #expect(!ca.t("desktop.mcpAgents.claudeInstall").contains("connector"))
    }

    @Test("the longest button label in any language fits the pane with room to spare")
    func longestButtonFitsThePane() throws {
        // The install button is `.fixedSize` and sits in a 660 pt pane beside a
        // name and a build line (docs/design-control-labels.md: a label never
        // truncates). Measure the real strings in the system font at the
        // button's size; 300 pt leaves the name and padding their room.
        let font = NSFont.systemFont(ofSize: NSFont.systemFontSize)
        var widest: (locale: String, key: String, width: CGFloat) = ("", "", 0)
        for locale in I18n.supportedLocales.sorted() {
            let i = try i18n(locale)
            for key in Self.claudeKeys + Self.chatgptKeys {
                let width = (i.t(key) as NSString)
                    .size(withAttributes: [.font: font]).width
                if width > widest.width { widest = (locale, key, width) }
            }
        }
        #expect(widest.width < 300,
                "\(widest.locale) \(widest.key) is \(Int(widest.width)) pt wide")
    }

    @Test("the reinstall how-to names the Claude tab's own reinstall button, in every language")
    func howToQuotesTheButton() throws {
        for locale in I18n.supportedLocales.sorted() {
            let i = try i18n(locale)
            let button = i.t("desktop.mcpAgents.claudeReinstall")
            let how = i.t("desktop.mcpAgents.claudeReinstallHow")
            #expect(how.contains(button), "\(locale): how-to does not contain its button \(button)")
        }
    }
}
