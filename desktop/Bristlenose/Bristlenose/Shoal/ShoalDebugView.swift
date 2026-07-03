#if DEBUG
import SwiftUI

/// DEBUG-only harness for looking at the resurrected typographic shoal in
/// isolation — no pipeline, no live data, just the v0.1 canned `WordPool`.
///
/// Launched from Debug ▸ Shoal Screensaver. Primary use is the **density +
/// GPU-load experiment**: the Words slider spawns 0–600 flocking words (mixed
/// styles, repeats allowed) so the right on-screen count can be found by eye on
/// a large monitor, while the on-screen FPS / node-count counters show the cost.
/// The flocking-algorithm picker (Classic / Alive / Alive V2) is inside
/// `ShoalView` top-right; "Fail" triggers the death animation.
///
/// NOT the shipping surface — production spawns are phase-driven and capped far
/// lower; this rig just finds the number.
struct ShoalDebugView: View {
    @State private var phase: ShoalPhase = .early
    @State private var failed = false
    @State private var population: Double = 500

    var body: some View {
        VStack(spacing: 0) {
            ShoalView(
                phase: $phase,
                failed: $failed,
                showsDebugControls: true,
                debugPopulation: Int(population)
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(nsColor: .windowBackgroundColor))

            Divider()

            HStack(spacing: 12) {
                Text("Words: \(Int(population))")
                    .font(.system(.body, design: .monospaced))
                    .frame(width: 110, alignment: .leading)
                Slider(value: $population, in: 0...600, step: 10)
                    .disabled(failed)

                Button(failed ? "Failed" : "Fail (die)") { failed = true }
                    .disabled(failed)

                Button("Reset") { failed = false }
            }
            .padding(10)
        }
    }
}
#endif
