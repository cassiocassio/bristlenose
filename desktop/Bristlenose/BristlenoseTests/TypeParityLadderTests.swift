#if DEBUG
import AppKit
import Testing
@testable import Bristlenose

/// Pure-helper coverage for the Type Parity Inspector. The view/webview aren't
/// unit-tested (they need a window + live WebKit); the decisions that matter —
/// weight bucketing, live metric resolution shape, and spec serialisation — are
/// pulled into helpers exactly so they can be checked here.
@Suite struct TypeParityLadderTests {

    @Test func weightBucket_maps_axis_to_css_weights() {
        #expect(MacTypeLadder.weightBucket(0).css == 400)
        #expect(MacTypeLadder.weightBucket(0).name == "Regular")
        #expect(MacTypeLadder.weightBucket(0.23).css == 500)
        #expect(MacTypeLadder.weightBucket(0.30).css == 600)   // SF semibold (headline)
        #expect(MacTypeLadder.weightBucket(0.40).css == 700)
        #expect(MacTypeLadder.weightBucket(-0.30).css == 300)  // light
    }

    @Test func resolve_returns_full_ladder_with_sane_metrics() {
        let rungs = MacTypeLadder.resolve(sample: "Hamburgevons 0123")
        #expect(rungs.count == MacTypeLadder.styles.count)   // all 11 macOS styles
        for r in rungs {
            #expect(r.pointSize > 0)
            #expect(r.lineHeight >= r.pointSize)             // line box ≥ glyph size
            #expect(r.sampleWidth > 0)
            #expect(r.capHeight > r.xHeight)                 // cap taller than x-height
        }
        // Largest style is largeTitle, smallest is a caption — ladder is ordered.
        let large = rungs.first { $0.id == "largeTitle" }!
        let cap = rungs.first { $0.id == "caption2" }!
        #expect(large.pointSize > cap.pointSize)
    }

    @Test func css_export_is_paste_ready() {
        let export = TypeParityExport(
            rows: [
                TypeParityExportRow(
                    token: "body", macStyle: "title3",
                    sizePx: 15, lineHeightPx: 20, letterSpacingEm: 0.01,
                    weight: 400, nativePt: 15, nativeWidth: 120.0, webWidth: 120.6
                )
            ],
            fingerprint: TypeParityFingerprint(macOS: "26.1.0", scale: 2, colorSpace: "Color LCD")
        )
        let css = TypeParitySpecBuilder.css(export)
        #expect(css.contains("[data-platform=\"desktop\"]"))
        #expect(css.contains("--bn-text-body:     15px;"))
        #expect(css.contains("--bn-text-body-lh:  1.333;"))   // 20/15
        #expect(css.contains("--bn-track-body:    0.010em;"))
        #expect(css.contains("macOS 26.1.0"))                 // fingerprint in header
    }

    @Test func json_export_round_trips() throws {
        let export = TypeParityExport(
            rows: [TypeParityExportRow(
                token: "label", macStyle: "body",
                sizePx: 13, lineHeightPx: 16, letterSpacingEm: 0,
                weight: 400, nativePt: 13, nativeWidth: 90, webWidth: 90
            )],
            fingerprint: TypeParityFingerprint(macOS: "26.1.0", scale: 2, colorSpace: "Color LCD")
        )
        let json = TypeParitySpecBuilder.json(export)
        let data = try #require(json.data(using: .utf8))
        let decoded = try JSONDecoder().decode(TypeParityExport.self, from: data)
        #expect(decoded == export)
    }
}
#endif
