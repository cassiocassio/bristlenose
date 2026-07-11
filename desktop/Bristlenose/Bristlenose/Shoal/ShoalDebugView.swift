#if DEBUG
import AppKit
import SwiftUI

/// DEBUG-only harness for looking at (and now *tuning*) the resurrected
/// typographic shoal in isolation — no pipeline, no live data, just the v0.1
/// canned `WordPool`.
///
/// Launched from Debug ▸ Shoal Screensaver. The right-hand inspector drives a
/// live `ShoalTuning` instance (sliders → the scene reads them each frame), so
/// the "floating vs murmuration" feel can be found by eye on real hardware. The
/// **Floating** / **Murmuration** presets snap all knobs; the sliders free-tune
/// from there. Behaviour picker (Classic / Alive / Alive V2) is inside
/// `ShoalView` top-right; the FPS / node-count counters are the live cost probe
/// for the density experiment.
///
/// NOT the shipping surface — production spawns are phase-driven and capped far
/// lower, and leave the tuning at defaults (= the `ShoalConfig` constants).
struct ShoalDebugView: View {
    @State private var phase: ShoalPhase = .early
    @State private var failed = false
    @State private var population: Double = 120
    @State private var tuning = ShoalTuning()
    @State private var disturbanceRequest: ShoalDisturbance?
    @State private var copied = false

    var body: some View {
        @Bindable var tuning = tuning
        HStack(spacing: 0) {
            ShoalView(
                phase: $phase,
                failed: $failed,
                showsDebugControls: true,
                debugPopulation: Int(population),
                tuning: tuning,
                disturbanceRequest: $disturbanceRequest
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(nsColor: .windowBackgroundColor))

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    // Presets
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Preset").font(.headline)
                        HStack {
                            Button("Floating") { tuning.resetToDefaults() }
                            Button("Murmuration") { tuning.applyMurmurationPreset() }
                        }
                        Button(copied ? "Copied" : "Copy values") { copyValues(tuning) }
                    }

                    TuningGroup("Motion") {
                        TuningSlider("Max force (turn snap)", $tuning.maxForce, 10...400)
                        TuningSlider("Max speed", $tuning.maxSpeed, 20...320)
                        TuningSlider("Min speed", $tuning.minSpeed, 0...200)
                    }

                    TuningGroup("Flocking") {
                        TuningSlider("Separation ×", $tuning.separationScale, 0...3, "%.2f")
                        TuningSlider("Alignment ×", $tuning.alignmentScale, 0...3, "%.2f")
                        TuningSlider("Cohesion ×", $tuning.cohesionScale, 0...3, "%.2f")
                        TuningSlider("Wander ×", $tuning.wanderScale, 0...2, "%.2f")
                    }

                    TuningGroup("Startle (Alive V2)") {
                        TuningSlider("Startle chance", $tuning.cascadeStartleChance, 0...0.02, "%.4f")
                        TuningSlider("Flee force", $tuning.cascadeFleeForce, 0...300)
                    }

                    TuningGroup("Murmuration (global flow)") {
                        TuningSlider("Attractor pull", $tuning.attractorStrength, 0...200)
                        TuningSlider("Drift rate", $tuning.attractorDriftRate, 0.02...1.5, "%.2f")
                        TuningSlider("Retarget every (s)", $tuning.attractorRetargetInterval, 1...15, "%.1f")
                    }

                    TuningGroup("Disturbance (pipeline batches)") {
                        Button("Words arrive") { disturbanceRequest = .wordsArrive }
                        Button("Themes land") { disturbanceRequest = .themesLand }
                        Button("Sentiment arrives") { disturbanceRequest = .sentimentArrives }
                        TuningSlider("Cohort size", $tuning.cohortSize, 0...40)
                        TuningSlider("Startle radius", $tuning.startleSeedRadius, 20...400)
                    }

                    Divider()

                    TuningGroup("Scene") {
                        HStack {
                            Text("Words").font(.caption)
                            Spacer()
                            Text("\(Int(population))")
                                .font(.caption.monospaced()).foregroundStyle(.secondary)
                        }
                        Slider(value: $population, in: 0...600, step: 10).disabled(failed)
                        HStack {
                            Button(failed ? "Failed" : "Fail (die)") { failed = true }
                                .disabled(failed)
                            Button("Reset flock") { failed = false }
                        }
                    }
                }
                .padding(14)
            }
            .frame(width: 280)
        }
    }

    private func copyValues(_ tuning: ShoalTuning) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(tuning.exportValues(), forType: .string)
        copied = true
        Task { try? await Task.sleep(for: .seconds(1.2)); copied = false }
    }
}

/// Labelled section wrapper for the inspector.
private struct TuningGroup<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.headline)
            content
        }
    }
}

/// One label + value-readout + slider row bound to a `CGFloat` tuning knob.
private struct TuningSlider: View {
    let label: String
    @Binding var value: CGFloat
    let range: ClosedRange<CGFloat>
    let format: String

    init(
        _ label: String,
        _ value: Binding<CGFloat>,
        _ range: ClosedRange<CGFloat>,
        _ format: String = "%.0f"
    ) {
        self.label = label
        self._value = value
        self.range = range
        self.format = format
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(label).font(.caption)
                Spacer()
                Text(String(format: format, Double(value)))
                    .font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Slider(value: $value, in: range)
        }
    }
}
#endif
