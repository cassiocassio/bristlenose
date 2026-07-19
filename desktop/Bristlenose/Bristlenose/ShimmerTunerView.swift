#if DEBUG
import SwiftUI
import AppKit

/// Debug ▸ Shimmer Tuner — the **native half** of the "thinking / analysing"
/// shimmer spike (Spike B). Mirrors `docs/mockups/shimmer-tuner.html` parameter
/// for parameter so the SwiftUI render can be compared against the CSS one, and
/// (later) seam-matched inside the real WKWebView window.
///
/// NOT a shipping surface — the whole file is `#if DEBUG`, launched from the
/// Debug menu like Shoal Screensaver / Type Parity Inspector.
///
/// What this proves that the browser can't: the *native* shimmer feel, and — once
/// we put a WKWebView loading the CSS tuner beside it — whether one set of numbers
/// reads the same across the sRGB (web) ↔ device-P3 (SwiftUI) colour-space seam.
///
/// Reduced-motion: honours `accessibilityReduceMotion` (the native twin of the
/// web's `prefers-reduced-motion`) — freezes to static resting text. In the
/// shipping wiring this ALSO gates on the existing `showAnalysisAnimation`
/// AppStorage toggle (Appearance ▸ "Show animation while analysing"); the tuner
/// exposes an equivalent checkbox so both gate states are previewable.
struct ShimmerTunerView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Seeded from the deep-research floor (17 Jul 2026): contrast ~12% (tune DOWN
    // toward 3–5%), sweep 1800 + gap 900 (~2.7s), band 34%, 100°, ease-in-out.
    @State private var contrastPct = 12.0   // % white mixed into the peak — the key knob
    @State private var sweepMs = 1800.0
    @State private var gapMs = 900.0
    @State private var bandPct = 34.0
    @State private var angleDeg = 100.0
    @State private var easing: ShimmerEasing = .easeInOut
    @State private var dark = false
    @State private var animate = true       // proxy for showAnalysisAnimation

    private var effectiveAnimate: Bool { animate && !reduceMotion }

    var body: some View {
        HSplitView {
            controls
                .frame(minWidth: 260, idealWidth: 280, maxWidth: 320)
            stage
                .frame(minWidth: 460, maxWidth: .infinity, maxHeight: .infinity)
                .preferredColorScheme(dark ? .dark : .light)
        }
        .frame(minWidth: 800, minHeight: 540)
    }

    // MARK: Controls

    private var controls: some View {
        Form {
            Section {
                slider("Contrast", value: $contrastPct, range: 0...40, unit: "%")
                Text("% white mixed into the peak. The key knob — shipped libs use ~3%. Tune down until it nearly vanishes, then back off one notch.")
                    .font(.caption2).foregroundStyle(.secondary)
            }
            Section {
                slider("Sweep", value: $sweepMs, range: 600...4000, unit: "ms", step: 50)
                slider("Gap", value: $gapMs, range: 0...3000, unit: "ms", step: 50)
                slider("Band", value: $bandPct, range: 8...70, unit: "%")
                slider("Angle", value: $angleDeg, range: 70...110, unit: "°")
                Picker("Easing", selection: $easing) {
                    ForEach(ShimmerEasing.allCases) { Text($0.rawValue).tag($0) }
                }
            }
            Section {
                Toggle("Dark", isOn: $dark)
                Toggle("Animate (Show animation while analysing)", isOn: $animate)
                if reduceMotion {
                    Label("Reduce Motion is ON — frozen regardless", systemImage: "figure.walk.motion")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Section("Spec") {
                Text(specJSON)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                Button("Copy JSON") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(specJSON, forType: .string)
                }
            }
        }
        .formStyle(.grouped)
    }

    private func slider(_ label: String, value: Binding<Double>, range: ClosedRange<Double>, unit: String, step: Double = 1) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(label)
                Spacer()
                Text("\(Int(value.wrappedValue))\(unit)")
                    .foregroundStyle(.tint).monospacedDigit()
            }
            Slider(value: value, in: range, step: step)
        }
    }

    // MARK: Stage

    private var stage: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 34) {
                sample("Native chrome — project sidebar status line") {
                    HStack(spacing: 10) {
                        Circle().fill(.tint).frame(width: 8, height: 8)
                        shimmer("Identifying speakers", rest: .primary, font: .system(size: 14))
                    }
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(RoundedRectangle(cornerRadius: 8).fill(.quaternary))
                    .frame(width: 320)
                }

                sample("Web — activity chip (single job)") {
                    chipPill { shimmer("Auto-coding “Garrett”", rest: chipText, font: .system(size: 13)) }
                }

                sample("Web — activity chip (summary, 2+ jobs)") {
                    chipPill { shimmer("2 tasks running", rest: chipText, font: .system(size: 13)) }
                }

                sample("Stress — long phrase & large weight") {
                    VStack(alignment: .leading, spacing: 14) {
                        shimmer("Merging transcript, removing personal information, and segmenting topics before extraction begins…",
                                rest: .primary, font: .system(size: 15))
                            .frame(maxWidth: 560, alignment: .leading)
                        shimmer("Analysing", rest: .primary, font: .system(size: 34, weight: .semibold))
                    }
                }
            }
            .padding(40)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color(nsColor: .textBackgroundColor))
    }

    private func sample<Content: View>(_ caption: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(caption.uppercased())
                .font(.caption2).tracking(0.6).foregroundStyle(.secondary)
            content()
        }
    }

    private var chipText: Color { dark ? Color(white: 0.12) : Color(white: 0.96) }

    private func chipPill<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        HStack(spacing: 9) {
            ProgressView().controlSize(.small)
            content()
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .background(Capsule().fill(.primary))
        .shadow(color: .black.opacity(0.22), radius: 10, y: 4)
    }

    private func shimmer(_ text: String, rest: Color, font: Font) -> some View {
        ShimmerText(text: text, rest: rest, font: font,
                    contrast: contrastPct / 100, sweepMs: sweepMs, gapMs: gapMs,
                    bandFrac: bandPct / 100, angleDeg: angleDeg,
                    easing: easing, animate: effectiveAnimate)
    }

    private var specJSON: String {
        """
        {
          "hue": "single",
          "contrastPctWhite": \(Int(contrastPct)),
          "sweepMs": \(Int(sweepMs)),
          "gapMs": \(Int(gapMs)),
          "periodMs": \(Int(sweepMs + gapMs)),
          "bandPct": \(Int(bandPct)),
          "angleDeg": \(Int(angleDeg)),
          "easing": "\(easing.rawValue)"
        }
        """
    }
}

// `ShimmerText` + `ShimmerEasing` now live in the shippable `SidebarShimmerText.swift`
// (shared with the project-sidebar status line); the tuner drives that same view.
#endif
