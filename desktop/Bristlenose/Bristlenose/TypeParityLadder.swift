#if DEBUG
import AppKit
import CoreText
import Foundation

// MARK: - Type Parity Inspector — data model + pure helpers
//
// DEBUG-only calibration tool. Renders the macOS AppKit/HIG type ladder natively
// (SwiftUI/Core Text) alongside the same text in a WKWebView, so we can eyeball
// and pixel-tune the CSS that the embedded report uses on `[data-platform="desktop"]`.
//
// Why a native column at all: cross-engine font matching is an eyeball problem.
// Core Text (native chrome) and WebKit render the *same* SF Pro differently
// (smoothing, subpixel, tracking). Numbers under-determine the match. This tool
// puts both engines in one window on one display so the calibration is true for
// the machine it runs on — and captures the environment fingerprint so the spec
// is honest about *which* display class it was tuned for.
//
// Everything here is pure / AppKit-only so it can be unit-tested without a window.

/// One rung of the macOS AppKit/HIG type ladder, with metrics resolved live from
/// the system. We do NOT hardcode sizes — `NSFont.preferredFont(forTextStyle:)`
/// is ground truth and shifts by macOS version, which is exactly the drift this
/// tool exists to catch.
struct MacTypeRung: Identifiable, Codable, Equatable {
    let id: String            // stable key, e.g. "body"
    let displayName: String   // "Body"
    let pointSize: Double
    let cssWeight: Int        // approximated CSS numeric weight (400/500/600/700)
    let weightName: String    // "Regular", "Semibold", …
    let ascent: Double
    let descent: Double
    let leading: Double
    let lineHeight: Double     // ascent + descent + leading (native line box)
    let capHeight: Double
    let xHeight: Double
    let sampleWidth: Double    // rendered advance width of the sample string (pt)
}

enum MacTypeLadder {
    /// The 11 macOS AppKit text styles, in descending size order. This is the
    /// ladder a Mac app actually uses (NOT the iOS-flavoured SwiftUI Dynamic
    /// Type ramp) — matches the table in docs/design-type-colour-parity.md.
    static let styles: [(id: String, name: String, style: NSFont.TextStyle)] = [
        ("largeTitle", "Large Title", .largeTitle),
        ("title1", "Title 1", .title1),
        ("title2", "Title 2", .title2),
        ("title3", "Title 3", .title3),
        ("headline", "Headline", .headline),
        ("body", "Body", .body),
        ("callout", "Callout", .callout),
        ("subheadline", "Subheadline", .subheadline),
        ("footnote", "Footnote", .footnote),
        ("caption1", "Caption 1", .caption1),
        ("caption2", "Caption 2", .caption2),
    ]

    /// Resolve every rung's live metrics for the given sample string.
    /// Safe to call on the main thread; uses only Core Text / AppKit reads.
    static func resolve(sample: String) -> [MacTypeRung] {
        styles.map { entry in
            let font = NSFont.preferredFont(forTextStyle: entry.style)
            let ct = font as CTFont
            let weight = fontWeight(font)

            // Rendered advance width of the sample — the honest tracking signal.
            // Apple applies its per-size tracking table automatically here; we
            // surface the *result* (width) rather than trying to read a private
            // tracking value, so the web side can width-match by letter-spacing.
            let attr = NSAttributedString(string: sample, attributes: [.font: font])
            let line = CTLineCreateWithAttributedString(attr)
            let width = CTLineGetTypographicBounds(line, nil, nil, nil)

            let ascent = Double(CTFontGetAscent(ct))
            let descent = Double(CTFontGetDescent(ct))
            let leading = Double(CTFontGetLeading(ct))

            return MacTypeRung(
                id: entry.id,
                displayName: entry.name,
                pointSize: Double(font.pointSize),
                cssWeight: weight.css,
                weightName: weight.name,
                ascent: ascent,
                descent: descent,
                leading: leading,
                lineHeight: ascent + descent + leading,
                capHeight: Double(CTFontGetCapHeight(ct)),
                xHeight: Double(CTFontGetXHeight(ct)),
                sampleWidth: width
            )
        }
    }

    /// Map Core Text's weight trait (-1…1, where Regular ≈ 0) to the nearest CSS
    /// numeric weight. Pure — unit-tested against the standard buckets.
    static func fontWeight(_ font: NSFont) -> (css: Int, name: String) {
        let traits = CTFontCopyTraits(font as CTFont) as NSDictionary
        let w = (traits[kCTFontWeightTrait as String] as? CGFloat) ?? 0
        return weightBucket(Double(w))
    }

    /// Bucketing isolated for testing. Thresholds chosen against SF Pro's axis:
    /// Regular ≈ 0, Medium ≈ 0.23, Semibold ≈ 0.3, Bold ≈ 0.4.
    static func weightBucket(_ w: Double) -> (css: Int, name: String) {
        switch w {
        case ..<(-0.4):      return (200, "Ultralight")
        case ..<(-0.1):      return (300, "Light")
        case ..<0.06:        return (400, "Regular")
        case ..<0.27:        return (500, "Medium")
        case ..<0.35:        return (600, "Semibold")
        case ..<0.5:         return (700, "Bold")
        default:             return (800, "Heavy")
        }
    }
}

// MARK: - Environment fingerprint
//
// The calibrated numbers are only valid for the display they were measured on.
// Smoothing, backing scale (@1x vs @2x), and colour profile all change WebKit's
// rendering. Capture them so the exported spec says which world it's true for.

struct TypeParityFingerprint: Codable, Equatable {
    let macOS: String
    let scale: Double
    let colorSpace: String

    static func current() -> TypeParityFingerprint {
        let v = ProcessInfo.processInfo.operatingSystemVersion
        let screen = NSScreen.main
        return TypeParityFingerprint(
            macOS: "\(v.majorVersion).\(v.minorVersion).\(v.patchVersion)",
            scale: Double(screen?.backingScaleFactor ?? 1),
            colorSpace: screen?.colorSpace?.localizedName ?? "unknown"
        )
    }
}

// MARK: - bn token rows (the web column — the values we actually ship)
//
// The web column is the bn token ladder; each row gets a pulldown to assign a
// macOS style it should match. "old" = the current tokens-desktop.css value;
// "new" = the assigned native style's measured metrics (my best first guess).

struct BNTokenRow: Codable, Equatable {
    let token: String       // e.g. "body" → --bn-text-body
    let label: String       // "Body — participant voice"
    let oldPx: Double       // current tokens-desktop.css size
    let oldLineHeight: Double // current ratio (unitless)
    let bestMacStyle: String  // pre-filled pulldown default
}

enum BNTokenLadder {
    /// Mirrors `bristlenose/theme/tokens-desktop.css` (the shipped SF Pro scale)
    /// plus the nearest-size mapping to the macOS ladder ("new" seed). Re-trued
    /// from a Type Parity Inspector export (macOS 26.4.1 @2x): every stop is now
    /// width-matched to its measured native style, and the macStyle names are the
    /// correct ones (body = title3, caption = callout — the old "callout" label on
    /// body is fixed). Keep in sync when tokens-desktop.css is retuned.
    static let rows: [BNTokenRow] = [
        BNTokenRow(token: "display", label: "Display — report h1",            oldPx: 26,   oldLineHeight: 1.231, bestMacStyle: "largeTitle"),
        BNTokenRow(token: "title",   label: "Title — page titles, h2",        oldPx: 22,   oldLineHeight: 1.182, bestMacStyle: "title1"),
        BNTokenRow(token: "heading", label: "Heading — section headings, h3", oldPx: 17,   oldLineHeight: 1.294, bestMacStyle: "title2"),
        BNTokenRow(token: "body",    label: "Body — participant voice",       oldPx: 15,   oldLineHeight: 1.333, bestMacStyle: "title3"),
        BNTokenRow(token: "label",   label: "Label — app voice (chrome)",     oldPx: 13,   oldLineHeight: 1.231, bestMacStyle: "body"),
        BNTokenRow(token: "caption", label: "Caption — footnotes, footer",    oldPx: 12,   oldLineHeight: 1.250, bestMacStyle: "callout"),
        BNTokenRow(token: "badge",   label: "Badge — chips, counts",          oldPx: 11,   oldLineHeight: 1.273, bestMacStyle: "subheadline"),
        BNTokenRow(token: "micro",   label: "Micro — delete ×, conf. badges", oldPx: 10,   oldLineHeight: 1.300, bestMacStyle: "caption2"),
    ]
}

// MARK: - Export

/// One row as collected back from the web side after the user has pixel-tuned it.
struct TypeParityExportRow: Codable, Equatable {
    let token: String
    let macStyle: String
    let sizePx: Double
    let lineHeightPx: Double
    let letterSpacingEm: Double
    let weight: Int
    let nativePt: Double
    let nativeWidth: Double
    let webWidth: Double
}

struct TypeParityExport: Codable, Equatable {
    let rows: [TypeParityExportRow]
    let fingerprint: TypeParityFingerprint
}

enum TypeParitySpecBuilder {
    /// Paste-ready CSS for the `[data-platform="desktop"]` block in
    /// tokens-desktop.css. Line-heights as unitless ratios (matching the
    /// existing file), plus a new `--bn-track-*` tracking token per stop.
    static func css(_ export: TypeParityExport) -> String {
        let fp = export.fingerprint
        var out = """
        /* Generated by the Type Parity Inspector (debug tool).
           Tuned on macOS \(fp.macOS), scale @\(trim(fp.scale))x, colour \(fp.colorSpace).
           These values are perceptual matches for that display class — re-true
           on a different scale/colour profile. */

        [data-platform="desktop"] {

        """
        for r in export.rows {
            let ratio = r.sizePx > 0 ? r.lineHeightPx / r.sizePx : 0
            let widthDelta = r.webWidth - r.nativeWidth
            out += """
                /* \(r.token) → macOS \(r.macStyle)  (native \(trim(r.nativePt))pt; \
            width Δ \(signed(widthDelta))px vs native) */
                --bn-text-\(r.token):     \(trim(r.sizePx))px;
                --bn-text-\(r.token)-lh:  \(trim3(ratio));
                --bn-track-\(r.token):    \(trim3(r.letterSpacingEm))em;

            """
        }
        out += "}\n"
        return out
    }

    /// Machine-readable record: every decision + the environment it was made in.
    static func json(_ export: TypeParityExport) -> String {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? enc.encode(export),
              let s = String(data: data, encoding: .utf8) else {
            return "{}"
        }
        return s
    }

    // Number formatting helpers — keep CSS tidy (no 13.000000001px).
    private static func trim(_ v: Double) -> String {
        v.rounded() == v ? String(Int(v)) : String(format: "%.2f", v)
    }
    private static func trim3(_ v: Double) -> String {
        String(format: "%.3f", v)
    }
    private static func signed(_ v: Double) -> String {
        (v >= 0 ? "+" : "") + String(format: "%.1f", v)
    }
}
#endif
