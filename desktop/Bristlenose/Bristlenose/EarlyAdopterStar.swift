import AppKit
import SwiftUI

/// The early-adopter mark: a solid star, as tall as the capitals of the text
/// beside it, filled with a shimmering blue gradient and turning slowly in 3D
/// about the line through two of its tips.
///
/// Spec: the owner's mockup (21 Nov 2026), section 0. Great Wave vivid, one turn
/// per 10 s, axis from the top tip to the lower-right tip, cap height, turns
/// for as long as it is on screen.
///
/// Why custom and not a symbol effect: no system symbol effect turns in 3D or
/// carries a gradient. It is built from three stock modifiers on `star.fill`.
///
/// The colours are deliberately outside the Edo palette (owner's ruling): at
/// cap height the palette's blues do not read, and the mark is meant to be
/// special. They are a one-off for this mark, not palette tokens.
///
/// Reduce Motion: no turn and no shimmer; the star sits face-on, gradient at rest.
///
/// This view knows nothing about who is an early adopter. Callers decide
/// whether to show it.
struct EarlyAdopterStar: View {

    /// Point size of the text the star sits beside. The star's ink is sized to
    /// that font's cap height.
    var textSize: CGFloat = NSFont.systemFontSize

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var colorScheme

    /// One full turn.
    static let turn: TimeInterval = 10
    /// One sweep of the shimmer, there or back.
    static let sweep: TimeInterval = 3.5

    /// `star.fill`'s ink is about 1.02× its point size (measured from
    /// `NSImage(systemSymbolName:)` at 52pt: 53px of ink). Dividing the cap
    /// height by it gives a symbol whose ink is as tall as a capital.
    private static let inkPerPoint: CGFloat = 53.0 / 52.0

    private var symbolSize: CGFloat {
        NSFont.systemFont(ofSize: textSize).capHeight / Self.inkPerPoint
    }

    var body: some View {
        if reduceMotion {
            star(angle: 0, shimmer: 0.5)
        } else {
            TimelineView(.animation) { context in
                let t = context.date.timeIntervalSinceReferenceDate
                star(angle: Self.angle(at: t), shimmer: Self.shimmerPhase(at: t))
            }
        }
    }

    private func star(angle: Double, shimmer: Double) -> some View {
        Image(systemName: "star.fill")
            .font(.system(size: symbolSize))
            .foregroundStyle(gradient(phase: shimmer))
            // The axis is the line from the top tip (50%, 0%) to the lower-right
            // tip (82%, 98%) of the ink box; anchoring at the top tip makes the
            // star turn about that line rather than its centre.
            .rotation3DEffect(.degrees(angle),
                              axis: (x: 0.33, y: 0.94, z: 0),
                              anchor: .top,
                              perspective: 0.6)
            // Darken slightly as the face turns away, like the mockup.
            .brightness(-0.11 * (1 - abs(cos(angle * .pi / 180))))
            // Decorative: every surface puts the localised words beside it.
            .accessibilityHidden(true)
    }

    // MARK: - Motion

    /// Degrees, 0..<360, linear, one turn per `turn` seconds.
    static func angle(at t: TimeInterval) -> Double {
        t.truncatingRemainder(dividingBy: turn) / turn * 360
    }

    /// 0...1, eased, there and back: the highlight crosses one way, then back.
    static func shimmerPhase(at t: TimeInterval) -> Double {
        let cycle = t.truncatingRemainder(dividingBy: 2 * sweep) / sweep // 0..<2
        let linear = cycle <= 1 ? cycle : 2 - cycle
        return (1 - cos(linear * .pi)) / 2 // ease-in-out
    }

    // MARK: - Colour

    /// Electric blue → sky, with a near-white band. `phase` slides the band
    /// across the star: the gradient is three times the star's length and the
    /// star shows a third of it, as the CSS stand-in did.
    private func gradient(phase: Double) -> LinearGradient {
        let dark = colorScheme == .dark
        let s1 = dark ? Color(hex: 0x3D94FF) : Color(hex: 0x1F6BFF)
        let s2 = dark ? Color(hex: 0x62B8FF) : Color(hex: 0x2F9BFF)
        let s3 = dark ? Color(hex: 0x8FE6FF) : Color(hex: 0x4CC9FF)
        let glint = dark ? Color(red: 0.91, green: 0.96, blue: 1) : Color(red: 0.88, green: 0.94, blue: 1)

        // 115° as CSS measures it (clockwise from up), in unit space, y down.
        let dx = sin(115 * Double.pi / 180), dy = -cos(115 * Double.pi / 180)
        let startOffset = -0.5 - 2 * phase
        let start = UnitPoint(x: 0.5 + dx * startOffset, y: 0.5 + dy * startOffset)
        let end = UnitPoint(x: start.x + dx * 3, y: start.y + dy * 3)

        return LinearGradient(stops: [
            .init(color: s1, location: 0),
            .init(color: s2, location: 0.30),
            .init(color: glint, location: 0.46),
            .init(color: s2, location: 0.56),
            .init(color: s3, location: 0.80),
            .init(color: s1, location: 1),
        ], startPoint: start, endPoint: end)
    }
}

private extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}

#Preview("Early adopter star · beside 13pt text") {
    VStack(alignment: .leading, spacing: 16) {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            EarlyAdopterStar()
            Text("Early adopter")
        }
        HStack(alignment: .firstTextBaseline, spacing: 3) {
            EarlyAdopterStar(textSize: 11)
            Text("Early adopter since January 2027.").font(.system(size: 11))
        }
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            EarlyAdopterStar(textSize: 104)
            Text("E").font(.system(size: 104))
        }
    }
    .padding(24)
}
