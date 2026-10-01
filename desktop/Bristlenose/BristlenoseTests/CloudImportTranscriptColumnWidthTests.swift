import AppKit
import Foundation
import Testing

@testable import Bristlenose

// Whether the import grid's Transcript column is wide enough to show a state
// whole — the Status column's rule applied to the new column, with the same
// independent oracle (`NSString.size(withAttributes:)` plus the cell's insets
// by hand) so a measurement that undercounts fails here rather than agreeing
// with itself.
//
// NOT YET RUN ON A MAC — written in a cloud session with no Xcode (1 Oct 2026).
// The glyph widths and the cell's fitting floor (~103 pt, from the hidden stop
// button's constraints) are the parts a Mac has to confirm.

@Suite("Transcript column width")
@MainActor
struct CloudImportTranscriptColumnWidthTests {

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

    private static let inset: CGFloat = 6
    private static let glyphSpacing: CGFloat = 4

    private func textWidth(_ s: String) -> CGFloat {
        let font = NSFont.systemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
        return (s as NSString).size(withAttributes: [.font: font]).width
    }

    private func glyphWidth(_ kind: MessageKind) -> CGFloat {
        NSImage(systemSymbolName: kind.symbolName, accessibilityDescription: nil)?
            .alignmentRect.width ?? 0
    }

    nonisolated private static var locales: [String] {
        let dirs = (try? FileManager.default.contentsOfDirectory(atPath: localesURL.path)) ?? []
        return dirs.filter { I18n.supportedLocales.contains($0) && $0 != "zh-Hant-HK" }.sorted()
    }

    @Test("Every shipped locale is found")
    func localesAreFound() {
        #expect(Self.locales.count == 21)
    }

    @Test("The minimum holds every transcript state, whole, in every locale",
          arguments: CloudImportTranscriptColumnWidthTests.locales)
    func minimumFitsEveryState(locale: String) {
        let i = i18n(locale)
        let minimum = CloudImportTranscriptColumn.minimumWidth(i)
        let widestGlyph = MessageKind.allCases.map(glyphWidth).max() ?? 0

        for key in CloudImportTranscriptColumn.glyphKeys {
            let s = i.t(key)
            let need = ceil(2 * Self.inset + widestGlyph + Self.glyphSpacing + textWidth(s))
            #expect(minimum >= need, "\(locale): “\(s)” needs \(need)pt, column minimum is \(minimum)pt")
        }
        for key in CloudImportTranscriptColumn.glyphlessKeys {
            let s = i.t(key)
            let need = ceil(2 * Self.inset + textWidth(s))
            #expect(minimum >= need, "\(locale): “\(s)” needs \(need)pt, column minimum is \(minimum)pt")
        }
    }

    /// A lookup that missed returns its own key, which measures as a plausible
    /// width and would pass the test above while rendering
    /// "desktop.cloudImport…" in the cell.
    @Test("Every measured key resolves in every locale",
          arguments: CloudImportTranscriptColumnWidthTests.locales)
    func everyKeyResolves(locale: String) {
        let i = i18n(locale)
        for key in CloudImportTranscriptColumn.glyphKeys + CloudImportTranscriptColumn.glyphlessKeys {
            #expect(!i.t(key).hasPrefix("desktop."), "\(locale): \(key) did not resolve")
        }
    }

    /// Every `transcript*` key is measured, and every measured key exists, so a
    /// new state cannot join the column without the column learning its width.
    /// The Status words the column reuses are checked against Status's own
    /// lists — they must be measured *somewhere*.
    @Test("No transcript key escapes the measurement")
    func everyTranscriptKeyIsClassified() throws {
        let url = Self.localesURL.appendingPathComponent("en/desktop.json")
        let json = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        let cloudImport = try #require(json?["cloudImport"] as? [String: Any])
        let onDisk = Set(cloudImport.keys.filter { $0.hasPrefix("transcript") }
                            .map { "desktop.cloudImport.\($0)" })
        let classified = Set(CloudImportTranscriptColumn.glyphKeys + CloudImportTranscriptColumn.glyphlessKeys)
        let own = classified.filter { $0.hasPrefix("desktop.cloudImport.transcript") }
        #expect(onDisk.subtracting(own).isEmpty,
                "unclassified: \(onDisk.subtracting(own).sorted())")
        #expect(own.subtracting(onDisk).isEmpty,
                "classified but not in en/desktop.json: \(own.subtracting(onDisk).sorted())")
        // The reused Status words must be real Status keys.
        let statusKeys = Set([CloudImportStatusColumn.importedKey]
                             + CloudImportStatusColumn.glyphKeys
                             + CloudImportStatusColumn.glyphlessKeys)
        let borrowed = classified.subtracting(own)
        #expect(borrowed.subtracting(statusKeys).isEmpty,
                "borrowed from Status but not a Status key: \(borrowed.subtracting(statusKeys).sorted())")
    }

    /// Every state the enum can take renders through a key the column measures.
    @Test("Every availability and outcome is a measured key")
    func everyStateIsMeasured() {
        let classified = Set(CloudImportTranscriptColumn.glyphKeys + CloudImportTranscriptColumn.glyphlessKeys)
        let states: [TranscriptAvailability] = [.available, .expected, .notProvided, .noSpeakerNames,
                                                .needsAdminApproval, .needsScope("x"), .unavailable,
                                                .notResolved, .noLongerAvailable]
        for state in states {
            #expect(classified.contains(state.cellKey), "\(state) renders an unmeasured key")
            // Glyph or no glyph, the list it sits in must agree with the cell.
            let drawnWithGlyph = CloudImportTranscriptColumn.glyphKeys.contains(state.cellKey)
            #expect(drawnWithGlyph == (state.cellKind != nil), "\(state) is measured in the wrong list")
        }
        let outcomes: [TranscriptOutcome] = [.imported(at: URL(fileURLWithPath: "/tmp/x.vtt")),
                                             .didNotArrive, .notImported]
        for outcome in outcomes {
            #expect(CloudImportTranscriptColumn.glyphKeys.contains(outcome.cellKey),
                    "\(outcome) renders an unmeasured key")
        }
    }
}
