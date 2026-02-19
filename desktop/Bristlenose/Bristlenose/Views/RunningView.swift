import SwiftUI

struct RunningView: View {
    let folder: URL
    let mode: RunMode
    @ObservedObject var runner: ProcessRunner

    private var statusText: String {
        switch mode {
        case .analyse: "Analysing\u{2026}"
        case .rerender: "Re-rendering\u{2026}"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
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
                    if let last = runner.outputLines.indices.last {
                        withAnimation {
                            proxy.scrollTo(last, anchor: .bottom)
                        }
                    }
                }
            }
        }
    }
}
