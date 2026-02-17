import SwiftUI
import AppKit

struct DoneView: View {
    let reportPath: String?
    @ObservedObject var runner: ProcessRunner
    var onStartOver: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack(spacing: 8) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                    .font(.title2)
                Text("Analysis complete")
                    .font(.headline)
            }

            // Log area (collapsed, scrollable)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 2) {
                    ForEach(
                        Array(runner.outputLines.enumerated()),
                        id: \.offset
                    ) { _, line in
                        Text(line)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 150)
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(.quaternary)
            )

            // View Report button
            if let path = reportPath {
                HStack(spacing: 12) {
                    Button(action: { openReport(path: path) }) {
                        Label("View Report", systemImage: "safari")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)

                    Text(URL(fileURLWithPath: path).lastPathComponent)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            } else {
                Label(
                    "Report file not found — check the output folder",
                    systemImage: "exclamationmark.triangle"
                )
                .foregroundStyle(.orange)
            }

            // Start over
            Button(action: onStartOver) {
                Label("Start over", systemImage: "arrow.uturn.backward")
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .font(.callout)
        }
    }

    private func openReport(path: String) {
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.open(url)
    }
}
