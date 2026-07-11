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
///
/// Motion is the **murmuration** tuning (`ShoalTuning.productionDefault()`,
/// Jul 2026) — committed speed, snappy turns, and a global flow the flock banks
/// toward. And the run's three content batches now *drive* the flock: the first
/// time each `ShoalFeed` kind appears (word → theme → sentiment, one per stage)
/// fires a `ShoalDisturbance` — the flock forms, then a startle wave, then the
/// predator swoop. See `docs/design-shoal-motion.md`. Reduce Motion / the
/// show-animation preference gate this whole view upstream in `ContentView`.
struct ShoalRunView: View {
    let projectID: UUID
    @ObservedObject var liveData: PipelineLiveData
    let feedURL: URL

    @State private var phase: ShoalPhase = .early
    @State private var feedWords: [WordPool.Word] = []
    @State private var loggedStale = false

    /// Production motion: the murmuration preset (shared source of truth with the
    /// Debug bench). The pre-murmuration "Floating" motion still exists — it's the
    /// default-init `ShoalTuning()`, reachable from the bench's "Floating" preset.
    @State private var tuning = ShoalTuning.productionDefault()

    /// One-shot flock reaction, set when a new pipeline batch kind first appears.
    @State private var disturbanceRequest: ShoalDisturbance?

    private var ringFraction: Double {
        liveData.progress[projectID]?.ringFraction ?? 0
    }

    var body: some View {
        ShoalView(
            phase: $phase,
            failed: .constant(false),
            liveWords: feedWords,
            tuning: tuning,
            disturbanceRequest: $disturbanceRequest
        )
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
        var seenKinds: Set<String> = []
        while !Task.isCancelled {
            let snapshot = ShoalFeed.read(at: feedURL)
            feedWords = snapshot.words

            // A batch kind appearing for the first time = its pipeline stage just
            // landed → fire the matching flock disturbance (once per kind). If two
            // kinds surface in the same 1.5 s poll (rare — the stages are seconds
            // to minutes apart), the later/bigger moment wins; the earlier join is
            // absorbed into it. The scene clears `disturbanceRequest` after firing.
            let fresh = snapshot.kinds.subtracting(seenKinds)
            if !fresh.isEmpty {
                seenKinds.formUnion(fresh)
                if let disturbance = Self.disturbance(forNewKinds: fresh) {
                    disturbanceRequest = disturbance
                }
            }

            // Feed still empty *past the run's midpoint* → likely a stale bundled
            // sidecar predating the emit; log once so canned-fallback isn't a
            // silent lie. Gated on progress, NOT wall-clock: transcription alone
            // can legitimately run minutes before the first `word` batch fires at
            // transcript-merge, so the feed is correctly empty early on.
            if !loggedStale, snapshot.words.isEmpty, ringFraction > 0.5,
               FileManager.default.fileExists(atPath: feedURL.path) {
                loggedStale = true
                ShoalFeed.logStaleEmpty(at: feedURL, serverVersion: nil)
            }
            try? await Task.sleep(for: .seconds(1.5))
        }
    }

    /// Pick the disturbance for a set of newly-appeared batch kinds, preferring
    /// the later/bigger pipeline moment when several land in one poll window.
    private static func disturbance(forNewKinds kinds: Set<String>) -> ShoalDisturbance? {
        for kind in ["sentiment", "theme", "word"] where kinds.contains(kind) {
            return ShoalDisturbance(feedKind: kind)
        }
        return nil
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
