import SwiftUI

/// The project's identity icon, with an optional one-shot "split-flap settle"
/// reveal played once when a project is first created and auto-assigned a random
/// icon.
///
/// Motion is a split-flap board (the train-departure / flip-clock idiom): each
/// step the symbol flips in around a horizontal axis — dropping from edge-on to
/// face-on — cycling through palette symbols at a decelerating cadence (fast →
/// slow), then settling on the assigned symbol with a spring. The flap reads as
/// "deciding" in a way the odometer roll didn't.
///
/// The reveal is suppressed (final symbol rendered immediately) when `reveal` is
/// false, or when the system **Reduce Motion** accessibility setting is on — in
/// the latter case the project still gets its random icon, just without the
/// flip (the accessibility path stays independent of the feature's off switch).
struct TumblingProjectIcon: View {

    /// The settled symbol — the project's assigned (or default) SF Symbol name.
    let symbol: String
    /// Dim the icon (used for unavailable projects), matching the row's name dim.
    var dimmed: Bool = false
    /// True for exactly the just-created project, to play the reveal once.
    let reveal: Bool
    /// Called when the reveal finishes (or immediately when skipped), so the
    /// owner can clear its one-shot trigger.
    let onRevealComplete: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var display: String
    @State private var flipAngle: Double = 0
    @State private var flipOpacity: Double = 1
    @State private var didStart = false

    init(
        symbol: String,
        dimmed: Bool = false,
        reveal: Bool,
        onRevealComplete: @escaping () -> Void
    ) {
        self.symbol = symbol
        self.dimmed = dimmed
        self.reveal = reveal
        self.onRevealComplete = onRevealComplete
        _display = State(initialValue: reveal ? (RandomProjectIcon.pool.first ?? symbol) : symbol)
    }

    var body: some View {
        Image(systemName: display)
            .foregroundStyle(dimmed ? HierarchicalShapeStyle.secondary : HierarchicalShapeStyle.primary)
            // Flip around the horizontal axis — the split-flap drop. Perspective
            // keeps it a flap, not a flat fade.
            .rotation3DEffect(.degrees(flipAngle), axis: (x: 1, y: 0, z: 0), perspective: 0.6)
            .opacity(flipOpacity)
            .task(id: reveal) { await runRevealIfNeeded() }
    }

    private func runRevealIfNeeded() async {
        // `reveal` flipping back to false (after we clear the trigger) re-runs
        // this task — just make sure we're showing the settled symbol upright.
        guard reveal else {
            display = symbol
            flipAngle = 0
            flipOpacity = 1
            return
        }
        guard !didStart else { return }
        didStart = true

        // Reduce Motion: assign the icon, skip the flip.
        guard !reduceMotion else {
            display = symbol
            onRevealComplete()
            return
        }

        // Decelerating flap: ~12 steps, intervals easing from ~60ms to ~260ms
        // (quadratic). Each step: snap the new glyph in edge-on, let SwiftUI
        // paint that frame, THEN flip it down to face-on. The mid-frame yield is
        // load-bearing — without it the instant 90° and the animated 0° coalesce
        // in one render tick and nothing visibly rotates (the icon just snaps).
        let steps = 12
        for i in 0..<steps {
            let isLast = i == steps - 1
            let frac = Double(i) / Double(steps - 1)
            // Mirror SidebarIconFlip: higher floor (legible opening) + ceiling.
            let interval = 0.10 + (0.30 - 0.10) * frac * frac

            display = isLast ? symbol : (RandomProjectIcon.pool.randomElement() ?? symbol)
            flipAngle = 90
            flipOpacity = 0.15
            try? await Task.sleep(for: .milliseconds(20))   // paint the edge-on frame

            withAnimation(
                isLast
                    ? .spring(response: 0.4, dampingFraction: 0.62)
                    : .easeOut(duration: min(0.20, interval))
            ) {
                flipAngle = 0
                flipOpacity = 1
            }
            try? await Task.sleep(for: .seconds(interval))
        }
        // Let the final spring settle before clearing the trigger — otherwise
        // consuming `pendingIconReveal` re-runs the task and snaps the spring.
        try? await Task.sleep(for: .milliseconds(320))
        onRevealComplete()
    }
}
