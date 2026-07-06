#if DEBUG
import AppKit
import SwiftUI

// MARK: - Catalogue tokens — adaptive light/dark (Phase 0 foundation)
//
// Code-only dynamic colours: no asset catalog needed. Each token resolves to its
// light or dark value against the view's effective appearance and re-resolves
// automatically when the appearance flips (the toggle in the catalogue header).
// This is the theming root the whole native rebuild reads from.

enum Tok {
    /// A colour that resolves light/dark by the effective appearance.
    static func dyn(_ light: UInt, _ dark: UInt) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
            return ns(isDark ? dark : light)
        })
    }

    private static func ns(_ v: UInt) -> NSColor {
        NSColor(srgbRed: CGFloat((v >> 16) & 0xFF) / 255.0,
                green: CGFloat((v >> 8) & 0xFF) / 255.0,
                blue: CGFloat(v & 0xFF) / 255.0,
                alpha: 1)
    }

    // Neutrals — bn light → bn dark (tokens.css).
    static let surface  = dyn(0xF9FAFB, 0x232325)   // quote / card fill
    static let codeBg   = dyn(0xF3F4F6, 0x2A2A2C)   // person-badge code half
    static let ink      = dyn(0x1A1A1A, 0xE5E7EB)   // primary text
    static let ink2     = dyn(0x3C3C43, 0xAEAEB2)   // secondary text
    static let hairline = Color.primary.opacity(0.12)

    // Sentiment / codebook light-hex → dark-hex (tokens.css v0.7 taxonomy + tints).
    private static let darkFor: [UInt: UInt] = [
        0xEA580C: 0xFB923C, 0xDC2626: 0xF87171, 0x7C3AED: 0xA78BFA,
        0xD97706: 0xFBBF24, 0x16A34A: 0x4ADE80, 0x059669: 0x34D399,
        0x2563EB: 0x60A5FA, 0xC2410C: 0xFB923C,
        0x8A2F52: 0xF0A6C8, 0x1F4F8A: 0x7FB0EE, 0x1F6A45: 0x6FD08C,
        0x5A3A82: 0xB79AE6, 0x7A5A1F: 0xE2C489
    ]

    /// Adaptive foreground for a sentiment/tag light-hex.
    static func sentiment(_ light: UInt) -> Color { dyn(light, darkFor[light] ?? light) }
    /// Soft, adaptive tag background derived from the sentiment colour — works in
    /// both appearances for free (translucent over the surface).
    static func tagFill(_ light: UInt) -> Color { sentiment(light).opacity(0.16) }
}

/// Light / Dark / Auto choice for the catalogue's appearance toggle.
enum ColorSchemeChoice: String, CaseIterable, Identifiable {
    case light, dark, auto
    var id: String { rawValue }
    var label: String { rawValue.capitalized }
    var colorScheme: ColorScheme? {
        switch self {
        case .light: .light
        case .dark: .dark
        case .auto: nil
        }
    }
}
#endif
