import SwiftUI
import AppKit

// MARK: - Keycap — the shipping primitive (docs/design-keycaps.md §2, step 3)
//
// Graduated out of `KeycapGalleryView.swift`'s `#if DEBUG` harness, which stays
// as the comparison rig against the CSS gallery. Only **Skin A · Flat** ships
// here: it is the doc's named default for *inline prose* — the quiet cap that
// sits in a sentence without shouting. Raised (B) belongs on teaching surfaces
// where the key IS the content, and drawing it mid-paragraph would be loud.
//
// Colours are byte-matched to `colors/palette-default.css` so the native cap and
// the web cap sit on the same seam. Do NOT substitute `NSColor.controlBackground`
// et al. — they won't match (design-keycaps.md §"CSS (web + docs)").
//
// `dark` is passed explicitly rather than read from the environment because the
// inline path renders through `ImageRenderer`, which resolves colours against
// the app's appearance rather than the view's `colorScheme` — an implicit read
// silently produces a light cap on a dark cell.
struct Keycap: View {
    let key: String
    let dark: Bool

    /// `--bn-text-label`, and the CSS's 1.7em box around it.
    static let fontSize: CGFloat = 11
    static var box: CGFloat { fontSize * 1.7 }
    private var box: CGFloat { Self.box }
    private var hPad: CGFloat { Self.fontSize * 0.42 }

    /// Distance from the cap's BOTTOM EDGE up to the baseline of the glyph
    /// inside it — the number that makes an inline cap sit on the sentence's
    /// baseline instead of floating above it.
    ///
    /// `Text` aligns an interpolated image's bottom edge to the text baseline,
    /// so without a correction the cap's glyph rides high by exactly this much
    /// (the cap's own descender space plus half its vertical centring slack).
    /// Derived from real `NSFont` metrics rather than eyeballed, so it stays
    /// correct if `fontSize` moves.
    static var glyphBaselineFromBottom: CGFloat {
        let f = NSFont.monospacedSystemFont(ofSize: fontSize, weight: .medium)
        let lineHeight = f.ascender - f.descender          // descender is negative
        let topInset = (box - lineHeight) / 2              // Text is centred in the box
        let baselineFromTop = topInset + f.ascender
        return box - baselineFromTop
    }

    var body: some View {
        Text(key)
            // Glyph-safe font — NOT the body font (design-keycaps.md §1 font gotcha).
            .font(.system(size: Self.fontSize, weight: .medium, design: .monospaced))
            .foregroundStyle(KeycapPalette.text(dark))
            .padding(.horizontal, hPad)
            .frame(minWidth: box, minHeight: box)
            .background(RoundedRectangle(cornerRadius: 5).fill(KeycapPalette.badgeBg(dark)))
            .overlay(RoundedRectangle(cornerRadius: 5).strokeBorder(KeycapPalette.border(dark)))
            .fixedSize()
    }
}

/// Byte-matched to `colors/palette-default.css`.
enum KeycapPalette {
    static func text(_ dark: Bool) -> Color { rgb(dark ? 0xE5E7EB : 0x1A1A1A) }
    static func badgeBg(_ dark: Bool) -> Color { rgb(dark ? 0x252525 : 0xF3F4F6) }
    static func border(_ dark: Bool) -> Color { rgb(dark ? 0x2D2D2D : 0xE5E7EB) }

    private static func rgb(_ v: UInt) -> Color {
        Color(.sRGB,
              red: Double((v >> 16) & 0xFF) / 255,
              green: Double((v >> 8) & 0xFF) / 255,
              blue: Double(v & 0xFF) / 255)
    }
}

// MARK: - Inline caps inside wrapping prose
//
// The problem this solves is why the welcome cells shipped bare monospaced
// letters instead of caps: a drawn cap is a `View`, and a `View` cannot flow
// inside a wrapping `Text`. Rebuilding the sentence as a flow layout of word
// views would fix that and break everything else — truncation, `lineLimit`, and
// the `ViewThatFits` ladders that pick a shorter reading when a cell is short
// all belong to `Text` and are lost the moment the sentence stops being one.
//
// So the cap is rasterised once and interpolated into the `Text` as an image,
// which flows, wraps and breaks lines natively. The sentence stays one `Text`.
@MainActor
enum KeycapInline {
    private static var cache: [String: Image] = [:]

    /// A cap ready to concatenate into a sentence, already dropped onto the
    /// surrounding text's baseline. Prefer this over `image(_:dark:)` — the
    /// baseline correction is not optional, and returning it pre-applied is the
    /// only way a caller cannot forget it.
    static func run(_ key: String, dark: Bool) -> Text? {
        guard let image = image(key, dark: dark) else { return nil }
        return Text(image).baselineOffset(-Keycap.glyphBaselineFromBottom)
    }

    /// Rendered cap for `key`, or nil if rendering failed (caller falls back to
    /// the bare monospaced glyph — the pre-existing text-only path).
    static func image(_ key: String, dark: Bool) -> Image? {
        let id = "\(key)|\(dark)"
        if let hit = cache[id] { return hit }
        let renderer = ImageRenderer(content: Keycap(key: key, dark: dark))
        renderer.scale = NSScreen.main?.backingScaleFactor ?? 2
        guard let ns = renderer.nsImage else { return nil }
        let image = Image(nsImage: ns)
        cache[id] = image
        return image
    }
}
