#if DEBUG
import AppKit
import SwiftUI

// MARK: - Type Parity Inspector — window
//
// Left: macOS AppKit/HIG ladder rendered natively (Core Text via SwiftUI).
// Right: the same sample in a WKWebView, per-bn-token, pixel-tunable.
// The two engines render on the same display so the comparison is honest.
//
// Eyeball aids: a shared sample across both columns, an optional native-snapshot
// overlay (capture the native column, superimpose over the web column at
// adjustable opacity + nudge, and blink) — because a 0.5px baseline shift is
// invisible side-by-side but jumps when you blink it. Overlay alignment needs a
// nudge on first use (the two columns lay out independently); that's expected.

struct TypeParityView: View {
    @StateObject private var controller = TypeParityController()
    @State private var sampleKey = "quote"
    @State private var mode = "new"          // "old" | "new"
    @State private var smoothing = "auto"    // "auto" | "antialiased"
    @State private var overlayOn = false
    @State private var blink = false
    @State private var overlayOpacity = 0.5
    @State private var nudge = CGSize.zero
    @State private var capturedNative: NSImage?

    private let samples: [(key: String, label: String, text: String)] = [
        ("quote", "Quote", "\u{201C}I just want it to remember where I left off.\u{201D}"),
        ("ui", "UI label", "Sessions · 18h 23m · 4 participants"),
        ("mixed", "Mixed", "Hamburgevons 0123456789 — quick brown fox"),
    ]
    private var sample: String { samples.first { $0.key == sampleKey }?.text ?? "" }
    private var rungs: [MacTypeRung] { MacTypeLadder.resolve(sample: sample) }
    private let fingerprint = TypeParityFingerprint.current()

    var body: some View {
        VStack(spacing: 0) {
            controlBar
            Divider()
            HSplitView {
                ScrollView { NativeLadderColumn(sample: sample) }
                    .frame(minWidth: 380)

                ZStack(alignment: .topLeading) {
                    TypeParityWebView(
                        controller: controller, rungs: rungs,
                        fingerprint: fingerprint, sample: sample,
                        mode: mode, smoothing: smoothing
                    )
                    if overlayOn, let img = capturedNative {
                        Image(nsImage: img)
                            .resizable().interpolation(.high)
                            .scaledToFit()
                            .opacity(blink ? 0 : overlayOpacity)
                            .offset(nudge)
                            .allowsHitTesting(false)
                    }
                }
                .frame(minWidth: 380)
            }
        }
        .frame(minWidth: 900, minHeight: 540)
    }

    // MARK: Controls

    private var controlBar: some View {
        VStack(spacing: 6) {
            HStack(spacing: 14) {
                Picker("Sample", selection: $sampleKey) {
                    ForEach(samples, id: \.key) { Text($0.label).tag($0.key) }
                }.pickerStyle(.segmented).fixedSize()

                Picker("Scale", selection: $mode) {
                    Text("old (current bn)").tag("old")
                    Text("new (HIG attempt)").tag("new")
                }.pickerStyle(.segmented).fixedSize()

                Toggle("antialiased", isOn: Binding(
                    get: { smoothing == "antialiased" },
                    set: { smoothing = $0 ? "antialiased" : "auto" }
                ))
                .help("WebKit font-smoothing. 'auto' matches native; 'antialiased' is the classic too-thin web look.")

                Spacer()

                Button("Export…") { controller.exportSpec() }
                    .keyboardShortcut("e", modifiers: [.command])
            }

            HStack(spacing: 14) {
                Toggle("overlay", isOn: $overlayOn)
                Button("Capture native") { captureNative() }
                    .help("Snapshot the native column to superimpose over the web column.")
                Toggle("blink", isOn: $blink)
                    .keyboardShortcut("b", modifiers: [])
                    .disabled(!overlayOn)
                Slider(value: $overlayOpacity, in: 0...1) { Text("opacity") }
                    .frame(width: 120).disabled(!overlayOn)
                Stepper("x \(Int(nudge.width))", value: $nudge.width, in: -200...200)
                    .disabled(!overlayOn)
                Stepper("y \(Int(nudge.height))", value: $nudge.height, in: -400...400)
                    .disabled(!overlayOn)
                Spacer()
            }
            .font(.caption)
        }
        .padding(10)
    }

    /// Snapshot the native column for the overlay. Render at backing scale so the
    /// superimposed image is device-pixel sharp.
    private func captureNative() {
        let renderer = ImageRenderer(content:
            NativeLadderColumn(sample: sample)
                .frame(width: 380)
                .background(Color(nsColor: .textBackgroundColor))
        )
        renderer.scale = NSScreen.main?.backingScaleFactor ?? 2
        capturedNative = renderer.nsImage
    }
}

// MARK: - Native column

private struct NativeLadderColumn: View {
    let sample: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(MacTypeLadder.styles, id: \.id) { entry in
                let font = NSFont.preferredFont(forTextStyle: entry.style)
                let rung = MacTypeLadder.resolve(sample: sample).first { $0.id == entry.id }
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(entry.name).fontWeight(.semibold)
                        if let r = rung {
                            Text("\(trim(r.pointSize))pt · \(r.weightName) \(r.cssWeight) · lh \(trim(r.lineHeight)) · w \(trim(r.sampleWidth))")
                                .foregroundStyle(.secondary)
                        }
                    }
                    .font(.caption)
                    Text(sample)
                        .font(Font(font as CTFont))
                        .lineLimit(1)
                }
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity, alignment: .leading)
                Divider()
            }
        }
        .padding(.horizontal, 16)
    }

    private func trim(_ v: Double) -> String {
        v.rounded() == v ? String(Int(v)) : String(format: "%.1f", v)
    }
}
#endif
