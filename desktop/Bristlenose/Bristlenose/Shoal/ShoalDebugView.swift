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
///
/// The **Landing** group is a mock of the end-of-run choreography (drain the
/// flock → beat → the report drops in over the fallen fish). It reuses the
/// existing die animation untouched and drops a *placeholder slab*, not a live
/// report — see `MockReportSlab`. Bench-only: nothing here is wired to a run.
struct ShoalDebugView: View {
    @State private var phase: ShoalPhase = .early
    @State private var failed = false
    @State private var population: Double = 120
    @State private var tuning = ShoalTuning()
    @State private var disturbanceRequest: ShoalDisturbance?
    @State private var copied = false

    // Landing choreography — mock only. `drainBeat` is the pause between the
    // flock starting to fall and the slab being released; in production that
    // gap is also where "report painted yet?" is awaited, so the fallen fish
    // double as the loading state.
    @State private var slabVisible = false
    @State private var slabDropped = false
    @State private var drainBeat: CGFloat = 900
    @State private var dropDuration: CGFloat = 0.45
    @State private var dropBounce: CGFloat = 0.35
    @State private var landingTask: Task<Void, Never>?
    @State private var landingCopied = false

    var body: some View {
        @Bindable var tuning = tuning
        HStack(spacing: 0) {
            ZStack {
                ShoalView(
                    phase: $phase,
                    failed: $failed,
                    showsDebugControls: true,
                    debugPopulation: Int(population),
                    tuning: tuning,
                    disturbanceRequest: $disturbanceRequest
                )
                .background(Color(nsColor: .windowBackgroundColor))

                // The slab rides above the flock and occludes it on landing.
                if slabVisible {
                    GeometryReader { geo in
                        MockReportSlab()
                            .offset(y: slabDropped ? 0 : -geo.size.height)
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipped()  // keep the pre-drop slab from painting outside the pane

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
                            Button("Reset flock") { resetLanding() }
                        }
                    }

                    TuningGroup("Landing (report drop — mock)") {
                        HStack {
                            Button("Drop report") { runLanding() }
                            Button("Reset") { resetLanding() }
                        }
                        TuningSlider("Drain beat (ms)", $drainBeat, 0...2000)
                        TuningSlider("Drop duration (s)", $dropDuration, 0.15...1.2, "%.2f")
                        TuningSlider("Bounce", $dropBounce, 0...0.6, "%.2f")
                        Button(landingCopied ? "Copied" : "Copy landing values") {
                            copyLandingValues()
                        }
                    }
                }
                .padding(14)
            }
            .frame(width: 280)
        }
    }

    /// Run the end-of-run choreography: drain the flock (the existing die
    /// animation, untouched), hold a beat, then release the slab.
    private func runLanding() {
        landingTask?.cancel()
        slabVisible = false
        slabDropped = false
        failed = true
        landingTask = Task {
            try? await Task.sleep(for: .milliseconds(Int(drainBeat)))
            guard !Task.isCancelled else { return }
            slabVisible = true
            withAnimation(.spring(duration: Double(dropDuration), bounce: Double(dropBounce))) {
                slabDropped = true
            }
        }
    }

    /// Clear the slab and refloat the flock. Cancels a pending drop so a reset
    /// mid-beat doesn't fire the slab afterwards.
    private func resetLanding() {
        landingTask?.cancel()
        landingTask = nil
        slabVisible = false
        slabDropped = false
        failed = false
    }

    private func copyValues(_ tuning: ShoalTuning) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(tuning.exportValues(), forType: .string)
        copied = true
        Task { try? await Task.sleep(for: .seconds(1.2)); copied = false }
    }

    /// Paste-ready Swift for whatever the landing sliders currently read —
    /// same copy-and-bake loop as the flock's `Copy values`.
    private func copyLandingValues() {
        let snippet = """
        let drainBeat: Duration = .milliseconds(\(Int(drainBeat)))
        let drop: Animation = .spring(
            duration: \(String(format: "%.2f", Double(dropDuration))),
            bounce: \(String(format: "%.2f", Double(dropBounce)))
        )
        """
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(snippet, forType: .string)
        landingCopied = true
        Task { try? await Task.sleep(for: .seconds(1.2)); landingCopied = false }
    }
}

/// Stand-in for the report's first screen: an opaque slab of grey blocks.
///
/// Deliberately NOT a live report — the bench exists to find the *motion*, and
/// a real WKWebView here would drag in a serve, a project, and the SPA for
/// nothing. In production this rectangle is the WebView; both are layer-backed
/// views translated by Core Animation, so the offset spring behaves identically.
/// Opaque is load-bearing: the slab has to occlude the drained flock as it
/// lands — that's the whole "the report buries the tank" beat.
private struct MockReportSlab: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            RoundedRectangle(cornerRadius: 4)
                .fill(.tertiary)
                .frame(width: 220, height: 22)

            HStack(spacing: 12) {
                ForEach(0..<4, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 8).fill(.quaternary).frame(height: 72)
                }
            }

            RoundedRectangle(cornerRadius: 4)
                .fill(.tertiary)
                .frame(width: 140, height: 14)

            VStack(spacing: 8) {
                ForEach(0..<6, id: \.self) { _ in
                    RoundedRectangle(cornerRadius: 6).fill(.quaternary).frame(height: 34)
                }
            }

            Spacer()
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor))
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
