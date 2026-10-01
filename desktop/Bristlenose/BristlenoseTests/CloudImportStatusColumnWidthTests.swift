import AppKit
import Foundation
import Testing

@testable import Bristlenose

// Whether the import grid's Status column is wide enough to show a status whole.
//
// It was a fixed 110pt minimum. "Imported" needs 125pt in Russian and 119pt in
// Polish, and the paid-plan warning needs ~200pt in Italian, so the column
// clipped the one word that tells the researcher the fetch worked. The minimum
// is now measured per locale; these tests hold it to every shipped translation.
//
// The oracle is deliberately not the code under test: it measures the string
// with `NSString.size(withAttributes:)` and adds the cell's insets by hand, so
// a measurement that silently undercounts (a glyph dropped, a font changed on
// one side only) fails here rather than agreeing with itself.

@Suite("Status column width")
@MainActor
struct CloudImportStatusColumnWidthTests {

    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("bristlenose/locales")

    private func i18n(_ locale: String) -> I18n {
        let i = I18n()
        i.configure(localesDirectory: Self.localesURL)
        i.setLocale(locale)
        return i
    }

    /// Leading and trailing cell inset, glyph-to-text spacing: the values in
    /// `StatusCellView`'s constraints.
    private static let inset: CGFloat = 6
    private static let glyphSpacing: CGFloat = 4

    private func textWidth(_ s: String, semibold: Bool) -> CGFloat {
        let font = NSFont.systemFont(ofSize: NSFont.smallSystemFontSize,
                                     weight: semibold ? .semibold : .regular)
        return (s as NSString).size(withAttributes: [.font: font]).width
    }

    /// Alignment rect, not `size`: an image view lays a symbol out by the former,
    /// and the warning triangle's `size` is half a point wider than it occupies.
    private func glyphWidth(_ kind: MessageKind) -> CGFloat {
        NSImage(systemSymbolName: kind.symbolName, accessibilityDescription: nil)?
            .alignmentRect.width ?? 0
    }

    /// Every full locale on disk. zh-Hant-HK is a thin override fork and
    /// inherits these keys from zh-Hant, so it is covered through that.
    nonisolated private static var locales: [String] {
        let dirs = (try? FileManager.default.contentsOfDirectory(atPath: localesURL.path)) ?? []
        return dirs.filter { I18n.supportedLocales.contains($0) && $0 != "zh-Hant-HK" }.sorted()
    }

    @Test("Every shipped locale is found")
    func localesAreFound() {
        // Guards the test itself: an empty list would pass every loop below.
        #expect(Self.locales.count == 21)
    }

    @Test("The minimum holds every bounded status, whole, in every locale",
          arguments: CloudImportStatusColumnWidthTests.locales)
    func minimumFitsEveryStatus(locale: String) {
        let i = i18n(locale)
        let minimum = CloudImportStatusColumn.minimumWidth(i)
        let widestGlyph = MessageKind.allCases.map(glyphWidth).max() ?? 0

        var needs: [(String, CGFloat)] = []
        let imported = i.t(CloudImportStatusColumn.importedKey)
        needs.append((imported, 2 * Self.inset + glyphWidth(.success) + Self.glyphSpacing
                      + textWidth(imported, semibold: true)))
        for key in CloudImportStatusColumn.glyphKeys {
            let s = i.t(key)
            needs.append((s, 2 * Self.inset + widestGlyph + Self.glyphSpacing
                          + textWidth(s, semibold: false)))
        }
        for key in CloudImportStatusColumn.glyphlessKeys {
            let s = i.t(key)
            needs.append((s, 2 * Self.inset + textWidth(s, semibold: false)))
        }
        for (string, need) in needs.map({ ($0.0, ceil($0.1)) }) {
            #expect(minimum >= need, "\(locale): “\(string)” needs \(need)pt, column minimum is \(minimum)pt")
        }
    }

    /// The bar, the gap and the stop button have to fit too — a status column
    /// sized to the text alone would put the cancel control on top of the bar
    /// in a language with short words.
    @Test("The minimum holds the progress bar and its cancel button")
    func minimumFitsProgress() {
        let i = i18n("zh-Hant")   // the shortest statuses of any locale
        let button = NSImage(systemSymbolName: "xmark.circle.fill",
                             accessibilityDescription: nil)?.alignmentRect.width ?? 0
        let need = Self.inset + 70 + 6 + button + Self.inset
        #expect(CloudImportStatusColumn.minimumWidth(i) >= need)
    }

    /// Every `status*` key is either measured or declared unbounded, so a new
    /// status cannot join the column without the column learning its width.
    @Test("No status key escapes the measurement")
    func everyStatusKeyIsClassified() throws {
        let url = Self.localesURL.appendingPathComponent("en/desktop.json")
        let json = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        let cloudImport = try #require(json?["cloudImport"] as? [String: Any])
        let onDisk = Set(cloudImport.keys.filter { $0.hasPrefix("status") }
                            .map { "desktop.cloudImport.\($0)" })
        let classified = Set([CloudImportStatusColumn.importedKey]
                             + CloudImportStatusColumn.glyphKeys
                             + CloudImportStatusColumn.glyphlessKeys
                             + CloudImportStatusColumn.unboundedKeys)
        #expect(onDisk.subtracting(classified).isEmpty,
                "unclassified: \(onDisk.subtracting(classified).sorted())")
        #expect(classified.subtracting(onDisk).isEmpty,
                "classified but not in en/desktop.json: \(classified.subtracting(onDisk).sorted())")
    }
}
