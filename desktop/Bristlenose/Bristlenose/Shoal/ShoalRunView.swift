import SwiftUI

/// Production host for the typographic shoal, shown in the detail pane while a
/// project is analysing — in place of the boot / "drop interviews" screens
/// (there's no report to show yet). Decorative: the real progress signal is the
/// sidebar row's determinate ring + subtitle. Gated in `ContentView` on the
/// analysing state, the "show animation" preference, and Reduce Motion.
///
/// Words come live from the run's shoal-feed (`ShoalFeed`, polled ~1.5 s) once
/// the pipeline emits them, falling back to the canned `WordPool` until then or
/// if the feed is absent. The flock's phase is driven off the run's real
/// progress fraction, so it thickens (early → middle → late) as analysis
/// proceeds. If no fraction is available yet (cold estimator), it stays early.
struct ShoalRunView: View {
    let projectID: UUID
    @ObservedObject var liveData: PipelineLiveData
    let feedURL: URL

    @State private var phase: ShoalPhase = .early
    @State private var feedWords: [WordPool.Word] = []
    @State private var loggedStale = false

    private var ringFraction: Double {
        liveData.progress[projectID]?.ringFraction ?? 0
    }

    var body: some View {
        ShoalView(phase: $phase, failed: .constant(false), liveWords: feedWords)
            .background(Color(nsColor: .windowBackgroundColor))
            .accessibilityHidden(true)  // decorative — progress lives on the sidebar row
            .onAppear { advance(to: ringFraction) }
            .onChange(of: ringFraction) { _, fraction in advance(to: fraction) }
            .task(id: projectID) { await pollFeed() }
    }

    /// Poll the run's shoal-feed ~every 1.5 s while this view is alive, handing
    /// fresh live words to the scene. Auto-cancelled on disappear / project
    /// switch (task keyed on `projectID`).
    private func pollFeed() async {
        loggedStale = false
        while !Task.isCancelled {
            feedWords = ShoalFeed.read(at: feedURL)
            // Feed still empty *past the run's midpoint* → likely a stale bundled
            // sidecar predating the emit; log once so canned-fallback isn't a
            // silent lie. Gated on progress, NOT wall-clock: transcription alone
            // can legitimately run minutes before the first `word` batch fires at
            // transcript-merge, so the feed is correctly empty early on.
            if !loggedStale, feedWords.isEmpty, ringFraction > 0.5,
               FileManager.default.fileExists(atPath: feedURL.path) {
                loggedStale = true
                ShoalFeed.logStaleEmpty(at: feedURL, serverVersion: nil)
            }
            try? await Task.sleep(for: .seconds(1.5))
        }
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
