import SwiftUI

struct SelectedView: View {
    let folder: URL
    let fileCount: Int
    let hasExistingOutput: Bool
    var onAnalyse: () -> Void
    var onRerender: () -> Void
    var onChangeFolder: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            // Folder info
            HStack(spacing: 8) {
                Image(systemName: "folder.fill")
                    .foregroundStyle(.tint)
                    .font(.title2)
                Text(folder.abbreviatingWithTildeInPath)
                    .font(.headline)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            if fileCount > 0 {
                Text("Found \(fileCount) processable file\(fileCount == 1 ? "" : "s")")
                    .foregroundStyle(.secondary)
            } else {
                Label("No processable files found", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
            }

            // Action buttons
            HStack(spacing: 12) {
                Button(action: onAnalyse) {
                    Label("Analyse", systemImage: "play.fill")
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(fileCount == 0)

                if hasExistingOutput {
                    Button(action: onRerender) {
                        Label("Re-render", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                }
            }

            Button("Choose a different folder\u{2026}", action: onChangeFolder)
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .font(.callout)

            Spacer()
        }
    }
}

// MARK: - Helpers

extension URL {
    /// Replaces the home directory prefix with `~` for display.
    var abbreviatingWithTildeInPath: String {
        (path as NSString).abbreviatingWithTildeInPath
    }
}
