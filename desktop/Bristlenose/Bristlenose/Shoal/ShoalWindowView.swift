import SwiftUI

/// The shipping Shoal viewer — the murmuration at defaults, no tuning UI.
///
/// Opened from Diagnostics ▸ Shoal Screensaver (Tier U — ships to every
/// channel behind the `showDiagnosticsMenu` preference). Beta-era, not a
/// permanent user feature: the point is tester hardware feedback ("is this
/// smooth on your machine?") — remove/revisit by GA per
/// `docs/design-diagnostics-menu.md`.
///
/// Thin wrapper because `ShoalView` is phase-driven for the embedded run view:
/// this window pins the richest phase (`.late` — sentiment colour) and leaves
/// every knob at the shipping `ShoalConfig` defaults. The tuning harness with
/// sliders/FPS probe is the separate DEBUG-only `ShoalDebugView` ("Shoal
/// Tuner").
struct ShoalWindowView: View {
    @State private var phase: ShoalPhase = .late
    @State private var failed = false

    var body: some View {
        ShoalView(phase: $phase, failed: $failed)
            .background(Color(nsColor: .windowBackgroundColor))
    }
}
