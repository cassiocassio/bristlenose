import AppKit
import SwiftUI

/// Accessory view shown inside the NSSavePanel when exporting an HTML report.
///
/// Hosts a single "Remove participant names…" toggle, mirroring the in-modal
/// option from `ExportDialog.tsx`. The download delegate reads the toggle
/// state on the way out and either accepts the destination as-is or restarts
/// the download against the alternate `?anonymise=…` URL.
@MainActor
final class ExportAccessoryController: ObservableObject {
    @Published var anonymise: Bool

    init(initial: Bool) {
        self.anonymise = initial
    }
}

private struct ExportAccessoryContent: View {
    @ObservedObject var controller: ExportAccessoryController
    let label: String
    let hint: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Toggle(isOn: $controller.anonymise) {
                Text(label)
            }
            .toggleStyle(.checkbox)
            Text(hint)
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(EdgeInsets(top: 12, leading: 20, bottom: 12, trailing: 20))
        .frame(width: 380, alignment: .leading)
    }
}

enum ExportAccessory {
    /// Build an NSHostingView wrapping the SwiftUI accessory content.
    /// Caller retains the controller to read the toggle state after `runModal()`.
    @MainActor
    static func makeView(controller: ExportAccessoryController,
                         label: String,
                         hint: String) -> NSView {
        let host = NSHostingView(
            rootView: ExportAccessoryContent(controller: controller, label: label, hint: hint)
        )
        host.translatesAutoresizingMaskIntoConstraints = true
        host.frame = NSRect(x: 0, y: 0, width: 380, height: 70)
        return host
    }
}
