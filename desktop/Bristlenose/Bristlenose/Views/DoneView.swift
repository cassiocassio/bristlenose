import SwiftUI
import AppKit

struct DoneView: View {
    let reportURL: String?
    @ObservedObject var runner: ProcessRunner
    var onRunAgain: () -> Void
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

            // Server status
            if runner.isServing {
                HStack(spacing: 6) {
                    Circle()
                        .fill(.green)
                        .frame(width: 8, height: 8)
                    Text("Serving report")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    if let url = reportURL {
                        Text(url)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.tertiary)
                    }
                }
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
            if let urlString = reportURL {
                HStack(spacing: 12) {
                    Button(action: { openReport(urlString: urlString) }) {
                        Label("View Report", systemImage: "safari")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                }
            } else {
                Label(
                    "Report not available — check the output folder",
                    systemImage: "exclamationmark.triangle"
                )
                .foregroundStyle(.orange)
            }

            // Navigation
            HStack(spacing: 16) {
                Button(action: onRunAgain) {
                    Label("Back to folder", systemImage: "arrow.uturn.backward")
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                Button(action: onStartOver) {
                    Label("New folder", systemImage: "folder.badge.plus")
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .font(.callout)
            }
        }
    }

    private func openReport(urlString: String) {
        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}
