import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// What the Claude and ChatGPT tabs of Settings ▸ MCP Agents render, read
/// through the app's own `I18n` from the shipping locale files, pinned to a
/// language: every button key resolves (never the raw key), the longest label
/// fits the pane, and the reinstall how-to contains its button. Which WORD each
/// vendor gets per language is pinned by `tests/test_vendor_plugin_terms.py`
/// against `bristlenose/locales/vendor-terms.json`, not here.
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
            // The how-to is shown in the different-build state, so ask that state which
            // button it offers rather than naming a key here.
            let button = i.t(MCPExtensionState.differentBuild(installed: "0").claudeButtonKey)
            let how = i.t("desktop.mcpAgents.claudeReinstallHow")
            #expect(how.contains(button), "\(locale): how-to does not contain its button \(button)")
        }
    }
}
