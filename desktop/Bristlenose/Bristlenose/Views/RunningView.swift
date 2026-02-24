import SwiftUI

// Set to true to demo the shoal animation without a real pipeline.
// Cycles through all phases on a timer. Debug builds only.
#if DEBUG
private let _demoShoal = true
#endif

struct RunningView: View {
    let folder: URL
    let mode: RunMode
    @ObservedObject var runner: ProcessRunner

    @State private var shoalPhase: ShoalPhase = .early
    @State private var shoalFailed = false
    @State private var stageDetector = StageDetector()

    private var statusText: String {
        switch mode {
        case .analyse: "Analysing\u{2026}"
        case .rerender: "Re-rendering\u{2026}"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack(spacing: 8) {
                Image(systemName: "folder.fill")
                    .foregroundStyle(.tint)
                Text(folder.lastPathComponent)
                    .font(.headline)
                Text("— \(statusText)")
                    .foregroundStyle(.secondary)

                Spacer()

                ProgressView()
                    .controlSize(.small)
            }
            .padding(.bottom, 12)

            // Shoal (top ~2/3) + Log (bottom ~1/3)
            GeometryReader { geo in
                VStack(spacing: 0) {
                    // Typographic shoal animation
                    ShoalView(phase: $shoalPhase, failed: $shoalFailed)
                        .frame(height: geo.size.height * 0.64)

                    // Log area
                    ScrollViewReader { proxy in
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 2) {
                                ForEach(
                                    Array(runner.outputLines.enumerated()),
                                    id: \.offset
                                ) { index, line in
                                    Text(line)
                                        .font(.system(.body, design: .monospaced))
                                        .textSelection(.enabled)
                                        .id(index)
                                }
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .background(Color(nsColor: .textBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .strokeBorder(.quaternary)
                        )
                        .onChange(of: runner.outputLines.count) { _, _ in
                            // Feed new lines to the stage detector
                            if let lastLine = runner.outputLines.last {
                                shoalPhase = stageDetector.processLine(lastLine)
                            }

                            // Auto-scroll log
                            if let last = runner.outputLines.indices.last {
                                withAnimation {
                                    proxy.scrollTo(last, anchor: .bottom)
                                }
                            }
                        }
                    }
                    .frame(height: geo.size.height * 0.36)
                }
            }
        }
        .onChange(of: runner.isRunning) { wasRunning, isNowRunning in
            #if DEBUG
            if _demoShoal { return }
            #endif
            if wasRunning && !isNowRunning {
                if runner.exitCode == 0 {
                    shoalPhase = .complete
                } else {
                    shoalFailed = true
                }
            }
        }
        #if DEBUG
        .task {
            guard _demoShoal else { return }
            // Endless demo loop — cycle through all phases for visual tuning
            while !Task.isCancelled {
                // Reset
                shoalPhase = .early
                shoalFailed = false

                try? await Task.sleep(for: .seconds(5))
                shoalPhase = .middle
                try? await Task.sleep(for: .seconds(5))
                shoalPhase = .late
                try? await Task.sleep(for: .seconds(6))
                shoalPhase = .complete  // triggers triumph
                try? await Task.sleep(for: .seconds(4))

                // Show death on alternate cycles
                shoalPhase = .early
                shoalFailed = false
                try? await Task.sleep(for: .seconds(5))
                shoalPhase = .middle
                try? await Task.sleep(for: .seconds(5))
                shoalFailed = true  // death drop
                try? await Task.sleep(for: .seconds(4))
            }
        }
        #endif
    }
}
