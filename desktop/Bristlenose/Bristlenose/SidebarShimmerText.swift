import SwiftUI

/// Easing for the thinking shimmer. Mirrors the CSS `--bn-shimmer-easing`.
enum ShimmerEasing: String, CaseIterable, Identifiable {
    case linear = "linear"
    case easeInOut = "ease-in-out"
    var id: String { rawValue }
}

/// The native (SwiftUI) rendering of the cross-surface **thinking shimmer**
/// (`docs/design-motion.md` §4.7.1) — a restrained single-hue brightness band
/// travelling across text to signal *indeterminate work in progress, no ETA*.
/// Twin of the web `atoms/shimmer.css` sweep; tuned to read identically in the
/// Debug ▸ Shimmer Tuner. Used by the project-sidebar status line, hosted via
/// `NSHostingView` in `ProjectSidebarOutline` for `.running` rows.
///
/// **Locked spec defaults** (contrast 5%, 1.8 s sweep + 0.9 s gap, band 34 %,
/// 100°, ease-in-out) so the sidebar call site stays terse. The caller gates
/// animation on `showAnalysisAnimation && !accessibilityReduceMotion` before
/// creating this — `animate: false` (or reduced motion) → static resting text.
///
/// Phase is **wall-clock** driven (`TimelineView(.animation)` reads absolute
/// time), so recreating the view — e.g. when the outline reloads a cell mid-run
/// — resumes mid-sweep with no restart flash.
///
/// NB: `ShimmerTunerView.swift` (Debug-only) carries a `private` twin of this
/// view + `ease` used while tuning; de-dup onto this shared type when the tuner
/// graduates or is retired.
struct ShimmerText: View {
    let text: String
    let rest: Color
    let font: Font
    var lineLimit: Int? = nil
    var contrast: Double = 0.05      // fraction of white mixed into the peak (5% — the floor)
    var sweepMs: Double = 1800
    var gapMs: Double = 900
    var bandFrac: Double = 0.34      // band width as a fraction of the text width
    var angleDeg: Double = 100
    var easing: ShimmerEasing = .easeInOut
    var animate: Bool = true

    var body: some View {
        Text(text)
            .font(font)
            .lineLimit(lineLimit)
            .truncationMode(.tail)
            .foregroundStyle(rest)
            .overlay { if animate { movingBand } }
            // Clip [resting text + moving band] to the glyph shapes.
            .mask(Text(text).font(font).lineLimit(lineLimit).truncationMode(.tail))
    }

    private var movingBand: some View {
        GeometryReader { geo in
            TimelineView(.animation) { ctx in
                let period = max(0.001, (sweepMs + gapMs) / 1000)
                let sweep = max(0.001, sweepMs / 1000)
                let t = ctx.date.timeIntervalSinceReferenceDate
                    .truncatingRemainder(dividingBy: period)
                // p: 0→1 across the sweep, then held at 1 (band parked off-right) for the gap.
                let p = ease(t < sweep ? t / sweep : 1.0)

                let w = geo.size.width
                let h = geo.size.height
                let bandW = max(1, bandFrac * w)
                // Centre travels from fully off-left to fully off-right → the gap is dark.
                let x = -bandW + p * (w + 2 * bandW)
                let peak = rest.mix(with: .white, by: contrast)

                LinearGradient(
                    colors: [.clear, peak, .clear],
                    startPoint: .leading, endPoint: .trailing
                )
                .frame(width: bandW, height: max(1, h * 2))   // overscan for the tilt
                .position(x: x, y: h / 2)
                .rotationEffect(.degrees(angleDeg - 90))
            }
        }
    }

    private func ease(_ p: Double) -> Double {
        switch easing {
        case .linear: return p
        case .easeInOut: return p * p * (3 - 2 * p)   // smoothstep
        }
    }
}
