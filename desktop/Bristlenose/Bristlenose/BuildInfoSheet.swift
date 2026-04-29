import AppKit
import SwiftUI

/// "Build Info…" sheet — a copyable provenance block for support pastes.
///
/// Always available (no `#if DEBUG` gate) because the sheet is opt-in via the
/// app menu, not visible chrome. Useful when a tester posts a screenshot of
/// just the About panel rather than the main window with the diagnostic
/// footer in the corner.
struct BuildInfoSheet: View {
    let sidecar: String
    let onDismiss: () -> Void

    private var report: String { BuildInfo.current.detailed(sidecar: sidecar) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Build Info")
                    .font(.headline)
                Spacer()
                Button(action: copyToPasteboard) {
                    Label("Copy", systemImage: "doc.on.doc")
                }
                .keyboardShortcut("c", modifiers: [.command])
            }

            Text(report)
                .font(.system(size: 11, design: .monospaced))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color(nsColor: .textBackgroundColor))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Color(nsColor: .separatorColor))
                )

            HStack {
                Spacer()
                Button("Close", action: onDismiss)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(16)
        .frame(width: 460)
    }

    private func copyToPasteboard() {
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(report, forType: .string)
    }
}
