import AppKit
import Foundation
import Testing

@testable import Bristlenose

/// BR-08: the Delight card's link label ("AI & privacy") used to ellipsise
/// ("Review AI & privacy sett..."), worst in Finnish and German. A control
/// label never truncates, and the spiral geometry is fixed, so the copy bends:
/// every shipped locale's label must wrap to no more lines than the card's text
/// area holds at the natural window (87 x 44 pt of text).
///
/// The oracle is `NSString.boundingRect` at the body font, not the view: a
/// label that needs a longer word than the card is wide breaks mid-word there
/// and shows as extra lines.
@Suite("Welcome privacy card fit")
@MainActor
struct WelcomePrivacyCardFitTests {
    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("bristlenose/locales")

    nonisolated private static var locales: [String] {
        let dirs = (try? FileManager.default.contentsOfDirectory(atPath: localesURL.path)) ?? []
        return dirs.filter {
            var isDir: ObjCBool = false
            let path = localesURL.appendingPathComponent($0).path
            return FileManager.default.fileExists(atPath: path, isDirectory: &isDir) && isDir.boolValue
        }.sorted()
    }

    /// `WelcomeCellStyle` pads 10 on every side.
    private static let padding: CGFloat = 10

    private func linesNeeded(_ s: String, width: CGFloat) -> Int {
        let font = NSFont.preferredFont(forTextStyle: .body)
        let line = ceil(font.ascender - font.descender + font.leading)
        let r = (s as NSString).boundingRect(
            with: NSSize(width: width, height: 10_000), options: [.usesLineFragmentOrigin],
            attributes: [.font: font])
        return Int((r.height / line).rounded())
    }

    private func linesHeld(_ frame: CGRect) -> Int {
        let font = NSFont.preferredFont(forTextStyle: .body)
        let line = ceil(font.ascender - font.descender + font.leading)
        return Int(((frame.height - 2 * Self.padding) / line).rounded(.down))
    }

    private func label(_ locale: String) -> String? {
        let url = Self.localesURL.appendingPathComponent("\(locale)/desktop.json")
        guard let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let welcome = json["welcome"] as? [String: Any]
        else { return nil }
        return welcome["aiPrivacyLink"] as? String
    }

    @Test func localesAreFound() { #expect(Self.locales.count == 22) }

    @Test("label fits the card", arguments: WelcomePrivacyCardFitTests.locales)
    func fits(locale: String) throws {
        // zh-Hant-HK carries only real overrides and falls back to zh-Hant.
        guard let text = label(locale) else {
            #expect(locale == "zh-Hant-HK"); return
        }
        // Natural size only: below it the card shrinks with the window and
        // one line fits and no real label does, in any language (known limit).
        for contentWidth in [WelcomeSpiralLayout.naturalWidth] {
            let delight = WelcomeSpiralLayout.frames(width: contentWidth, stacked: false)[4]
            let held = linesHeld(delight)
            let need = linesNeeded(text, width: delight.width - 2 * Self.padding)
            #expect(held >= 2, "card holds \(held) lines at \(contentWidth)")
            #expect(need <= held, "\(locale) \"\(text)\" needs \(need) lines, card holds \(held) at \(contentWidth)")
        }
    }
}
