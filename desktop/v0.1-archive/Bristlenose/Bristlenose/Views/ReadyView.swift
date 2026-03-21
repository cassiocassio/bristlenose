import SwiftUI
import UniformTypeIdentifiers
import AppKit

struct ReadyView: View {
    var onFolderSelected: (URL) -> Void

    @State private var isDropTargeted = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            // Title
            Text("Bristlenose")
                .font(.largeTitle)
                .fontWeight(.semibold)

            Text("User Research Analysis Tool")
                .font(.title3)
                .foregroundStyle(.secondary)

            // Drop zone
            VStack(spacing: 12) {
                Image(systemName: "folder.badge.plus")
                    .font(.system(size: 40))
                    .foregroundStyle(.secondary)

                Text("Choose a folder or drag it here")
                    .foregroundStyle(.secondary)

                Button("Choose Folder\u{2026}") {
                    if let url = pickFolder() {
                        onFolderSelected(url)
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            .frame(maxWidth: .infinity)
            .padding(28)
            .background(
                isDropTargeted
                    ? Color.accentColor.opacity(0.08)
                    : Color(nsColor: .controlBackgroundColor)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(
                        style: StrokeStyle(lineWidth: 2, dash: [8])
                    )
                    .foregroundColor(isDropTargeted ? .accentColor : .gray.opacity(0.3))
            )
            .dropDestination(for: URL.self) { urls, _ in
                guard let url = urls.first else { return false }
                var isDir: ObjCBool = false
                guard FileManager.default.fileExists(
                    atPath: url.path,
                    isDirectory: &isDir
                ), isDir.boolValue else { return false }
                onFolderSelected(url)
                return true
            } isTargeted: { targeted in
                isDropTargeted = targeted
            }

            // Supported formats
            Text(".mp4  .mov  .wav  .mp3  .m4a  .vtt  .srt  .docx")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .monospaced()

            Text("Zoom, Teams & Google Meet recordings")
                .font(.caption)
                .foregroundStyle(.tertiary)

            Spacer()
        }
    }

    // MARK: - Folder picker

    private func pickFolder() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "Choose a folder of interview recordings"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false

        let response = panel.runModal()
        return response == .OK ? panel.url : nil
    }
}
