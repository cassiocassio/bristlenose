import AppKit
import SwiftUI
import os

/// "New Project…" chosen from a destination popup: name it, place it, register
/// it, and hand the caller its id.
///
/// **`NSSavePanel`, not a bespoke sheet, and the reason is not aesthetic** — the
/// panel *is* what grants sandbox write access to the place the user picked. A
/// hand-drawn "name your project" sheet would produce a path this process cannot
/// write to, and the failure would land at the end of a download rather than at
/// the moment of choosing.
///
/// Sibling to `ContentView.createFolderProjectViaSavePanel`, which does the same
/// thing plus a file copy for the drag-and-drop path. Deliberately not shared
/// yet: that one is entangled with `CopyMachinery`, the pipeline runner and the
/// sidebar selection, none of which the import window has or wants.
@MainActor
enum NewProjectDestination {

    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import")

    /// - Parameter completion: the new project's id, or nil if the user
    ///   cancelled or the folder could not be created. Nil must leave the
    ///   caller's selection unchanged — a cancelled panel is not a choice.
    static func present(
        index: ProjectIndex,
        i18n: I18n,
        suggestedName: String,
        message: String,
        completion: @escaping (UUID?) -> Void
    ) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedName
        panel.directoryURL = ProjectFolderDefaults.suggestedDirectory()
        panel.canCreateDirectories = true
        panel.title = i18n.t("desktop.chrome.newProjectSaveTitle")
        panel.prompt = i18n.t("desktop.chrome.newProjectSavePrompt")
        panel.message = message

        // Under App Sandbox the panel is hosted out-of-process by the powerbox —
        // the one place appearance inheritance crosses a process boundary — so
        // it is stated rather than trusted. `PanelHost` also owns the
        // keyWindow-is-nil fallback chain; a bare `NSApp.keyWindow` here would
        // silently downgrade the sheet to a free-floating, system-themed panel.
        let host = PanelHost.window
        panel.adoptHostAppearance(host)

        let handler: (NSApplication.ModalResponse) -> Void = { response in
            Task { @MainActor in
                guard response == .OK, let target = panel.url else {
                    completion(nil)
                    return
                }
                do {
                    try FileManager.default.createDirectory(
                        at: target, withIntermediateDirectories: true)
                    // Only after it exists. Remembering a folder we then failed
                    // to create would send the next panel somewhere that isn't
                    // there.
                    ProjectFolderDefaults.remember(projectFolder: target)
                } catch {
                    // Said out loud rather than swallowed: the popup would
                    // otherwise snap back to its previous value with no
                    // explanation, which reads as the menu item being broken.
                    log.error("""
                        new_project_destination create_failed \
                        \(error.localizedDescription, privacy: .public)
                        """)
                    completion(nil)
                    return
                }
                // Folder-shaped (`inputFiles == nil`), so the CLI rescans it at
                // run time and folds in whatever the import writes there. The
                // project name follows the panel's filename — one source of
                // truth for what the researcher just named.
                let project = index.addProject(
                    name: target.lastPathComponent, path: target.path)
                completion(project.id)
            }
        }

        if let host {
            panel.beginSheetModal(for: host, completionHandler: handler)
        } else {
            panel.begin(completionHandler: handler)
        }
    }
}
