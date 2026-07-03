#if DEBUG
import SwiftUI

/// DEBUG-only harness for looking at the resurrected typographic shoal in
/// isolation — no pipeline, no live data, just the v0.1 canned `WordPool`.
///
/// Launched from Debug ▸ Shoal Screensaver. Lets you step the animation through
/// its pipeline phases (early → middle → late) and trigger the failure ("die")
/// path, so the flocking, the per-phase word styling, and the death animation
/// can all be judged by eye. The flocking-algorithm picker (Classic / Alive /
/// Alive V2) lives inside `ShoalView` itself, top-right.
///
/// This is a viewing harness for the TF "is it worth looking at?" call — NOT the
/// shipping surface. Wiring the shoal into the detail pane with live transcript
/// words is a separate step.
struct ShoalDebugView: View {
    @State private var phase: ShoalPhase = .early
    @State private var failed = false

    var body: some View {
        VStack(spacing: 0) {
            ShoalView(phase: $phase, failed: $failed, showsDebugControls: true)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(nsColor: .windowBackgroundColor))

            Divider()

            HStack(spacing: 12) {
                Picker("Phase", selection: $phase) {
                    Text("Early").tag(ShoalPhase.early)
                    Text("Middle").tag(ShoalPhase.middle)
                    Text("Late").tag(ShoalPhase.late)
                }
                .pickerStyle(.segmented)
                .fixedSize()
                .disabled(failed)

                Spacer()

                Button(failed ? "Failed" : "Fail (die)") { failed = true }
                    .disabled(failed)

                Button("Reset") {
                    failed = false
                    phase = .early
                }
            }
            .padding(10)
        }
    }
}
#endif
