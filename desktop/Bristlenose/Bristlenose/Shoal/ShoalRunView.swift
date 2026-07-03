import SwiftUI

/// Production host for the typographic shoal, shown in the detail pane while a
/// project is analysing — in place of the boot / "drop interviews" screens
/// (there's no report to show yet). Decorative: the real progress signal is the
/// sidebar row's determinate ring + subtitle. Gated in `ContentView` on the
/// analysing state, the "show animation" preference, and Reduce Motion.
///
/// Words are the canned v0.1 `WordPool` for now; the live transcript-word feed
/// is a later slice. The flock's phase is driven loosely off the run's real
/// progress fraction, so it thickens (early → middle → late) as analysis
/// proceeds rather than sitting static. If no fraction is available yet (cold
/// estimator), it simply stays in the early phase — still flocking.
struct ShoalRunView: View {
    let projectID: UUID
    @ObservedObject var liveData: PipelineLiveData

    @State private var phase: ShoalPhase = .early

    private var ringFraction: Double {
        liveData.progress[projectID]?.ringFraction ?? 0
    }

    var body: some View {
        ShoalView(phase: $phase, failed: .constant(false))
            .background(Color(nsColor: .windowBackgroundColor))
            .accessibilityHidden(true)  // decorative — progress lives on the sidebar row
            .onAppear { advance(to: ringFraction) }
            .onChange(of: ringFraction) { _, fraction in advance(to: fraction) }
    }

    /// Move the flock forward as the run progresses. Monotonic — never regress
    /// (a backward step would trigger a scene reset); mirrors the ring's own
    /// monotonic fill.
    private func advance(to fraction: Double) {
        let target = Self.phase(for: fraction)
        if target > phase { phase = target }
    }

    /// Map the determinate ring fill (0…0.92) onto the three shoal phases.
    static func phase(for fraction: Double) -> ShoalPhase {
        switch fraction {
        case ..<0.34: return .early
        case ..<0.67: return .middle
        default: return .late
        }
    }
}
