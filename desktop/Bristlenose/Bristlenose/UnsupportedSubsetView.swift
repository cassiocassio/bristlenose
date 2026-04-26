import SwiftUI

/// Shown in the project content area when a project was created from
/// individual files (or a mixed file/folder drop) — `inputFiles != nil`.
///
/// The CLI's `discover_files()` only accepts an input directory today; until
/// the `--files` subset API lands, projects of this shape can't be analysed.
/// We capture the files (`Project.inputFiles`) so nothing is lost, but the
/// content area shows this elegant-error state instead of starting serve.
///
/// Plan §Phase 3 point 2 (third branch) and §point 3 (unsupported-subset
/// state). No "coming soon" copy — alpha doesn't promise it.
struct UnsupportedSubsetView: View {
    let project: Project

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Label {
                    Text("Bristlenose analyses folders").font(.title3.weight(.semibold))
                } icon: {
                    Image(systemName: "doc.on.doc")
                        .foregroundStyle(.secondary)
                        .imageScale(.large)
                }
                Text("This project was created from individual files, so it can't be analysed.")
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 4)

            if let files = project.inputFiles, !files.isEmpty {
                Text("Files in this project")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)

                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(files, id: \.self) { path in
                            fileRow(path)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .frame(maxHeight: 360)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(nsColor: .textBackgroundColor))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.secondary.opacity(0.2), lineWidth: 0.5)
                )
            }

            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(maxWidth: 640, maxHeight: .infinity, alignment: .top)
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private func fileRow(_ path: String) -> some View {
        let url = URL(fileURLWithPath: path)
        HStack(spacing: 8) {
            Image(systemName: "doc.text")
                .foregroundStyle(.tertiary)
                .imageScale(.small)
            Text(url.lastPathComponent)
                .font(.callout)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            Button {
                NSWorkspace.shared.activateFileViewerSelecting([url])
            } label: {
                Text("Show in Finder")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .help(path)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
    }
}
