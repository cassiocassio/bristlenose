import AppKit
import SwiftUI

/// Settings tab for app-level behaviour — currently just where new projects go.
///
/// **Why a pane of its own.** The other four are chrome (Appearance), the two
/// engines (LLM Provider, Transcription), and who can read your work (MCP
/// Agents). A storage location is none of those, and putting it in Appearance
/// because Appearance is the roomiest is how Appearance stops meaning anything.
/// It is called General, and it is first, because that is the pane a Mac user
/// checks for "where do new things go" — and because it will absorb the next
/// two or three app-level preferences without needing a rename. Deliberately
/// not "Storage": `docs/design-project-storage.md` spent nine rejected models
/// establishing that Bristlenose manages none, and a pane called Storage
/// re-opens every one of those questions.
///
/// **The default state is the whole design.** With nothing configured the popup
/// reads *"Last location used"* — not "None", which would imply the app has no
/// behaviour, which is false and worse than the setting. Documents-then-remember
/// is what Xcode and Final Cut both do (neither offers a preference at all), so
/// this row is an override on a behaviour that is already sufficient for most
/// researchers, and it should say so rather than pretend it is the normal path.
///
/// **A missing folder is not a decision.** An unplugged drive does not mean the
/// researcher changed their mind about where studies live, so the row keeps
/// naming the folder it was pointed at and says why it can't be used, while
/// `ProjectFolderDefaults.suggestedDirectory()` quietly falls to the next rung.
/// Silently clearing the preference — or silently swapping the row to Documents
/// — would be the app second-guessing an absent T7.
struct GeneralSettingsView: View {

    @EnvironmentObject var i18n: I18n

    /// Derived from a bookmark plus a filesystem probe, so it can't be
    /// `@AppStorage`. Only this view writes the preference, so refreshing on
    /// appear and after each action is sufficient.
    @State private var configured: ProjectFolderDefaults.Configured = .notSet

    var body: some View {
        Form {
            Section {
                // In-cell subtitle (title + secondary Text inside the control's
                // label) — the System Settings idiom the other panes use, which
                // drops the row keyline a separate Text row would draw.
                LabeledContent {
                    folderMenu
                } label: {
                    // "Initial default location for new projects" — says
                    // *initial* and *default* rather than naming the folder,
                    // because the panel still lets the researcher go anywhere.
                    // A terser "New project folder" left that implicit and read
                    // as a constraint. No section header above it: with one row
                    // the header only repeated the label.
                    Text(i18n.t("settings.general.projectFolderLegend"))
                    Text(explanation)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .task { refresh() }
    }

    // MARK: - The control

    /// A pop-up button rather than a bare "Choose…" — it shows the current
    /// folder with its real Finder icon, and it gives the reset a home without
    /// a second button competing for the row.
    private var folderMenu: some View {
        Menu {
            Button(i18n.t("settings.general.chooseOther")) { chooseFolder() }
            Divider()
            Button(i18n.t("settings.general.useLastLocation")) {
                ProjectFolderDefaults.clearConfigured()
                refresh()
            }
            .disabled(configured == .notSet)
        } label: {
            menuLabel
        }
        .frame(width: 240)
    }

    @ViewBuilder
    private var menuLabel: some View {
        switch configured {
        case .notSet:
            Text(i18n.t("settings.general.lastLocationUsed"))
        case .resolved(let url):
            HStack(spacing: 5) {
                // The real Finder icon, not an SF Symbol: this is one specific
                // folder, not the concept of a folder — and a custom folder icon
                // is how the researcher recognises it at a glance.
                Image(nsImage: folderIcon(for: url))
                Text(url.lastPathComponent)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        case .unavailable(let name, _):
            HStack(spacing: 5) {
                Image(systemName: "exclamationmark.triangle")
                Text(name)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            .foregroundStyle(.secondary)
        }
    }

    private func folderIcon(for url: URL) -> NSImage {
        let icon = NSWorkspace.shared.icon(forFile: url.path)
        icon.size = NSSize(width: 16, height: 16)
        return icon
    }

    // MARK: - The second line

    /// Whichever fact matters in the current state: what the app will do if you
    /// leave this alone, where the folder is, or why it can't be reached.
    private var explanation: String {
        switch configured {
        case .notSet:
            return i18n.t("settings.general.projectFolderHelp")

        case .resolved(let url):
            // Finder's own abbreviation. `UserHome`, not `NSHomeDirectory()`,
            // which under App Sandbox is the container and never matches.
            let path = UserHome.abbreviate(url.path)
            // Attribution, never a warning: a project folder inside the client's
            // Dropbox or SharePoint tree is the intended setup, and naming the
            // provider is what stops a three-minute dataless fetch reading as
            // Bristlenose being slow (design-project-storage §3).
            guard let provider = ProjectIndex.cloudProviderLabel(for: url.path) else {
                return path
            }
            return "\(path) — \(i18n.t("settings.general.inProvider", ["provider": provider]))"

        case .unavailable(_, let reason):
            let cause: String
            switch reason {
            case .volumeOffline(let volume):
                // Name the volume. "On Iona, which isn't connected" is
                // actionable; "unavailable" sends the researcher hunting.
                cause = i18n.t("settings.general.volumeOffline", ["volume": volume])
            case .missing:
                cause = i18n.t("settings.general.folderDeleted")
            }
            return "\(cause) \(i18n.t("settings.general.fallbackNote"))"
        }
    }

    // MARK: - Actions

    /// The pick is what mints the security-scoped bookmark, which is why this is
    /// an `NSOpenPanel` and not a text field: a typed path grants nothing under
    /// App Sandbox, and a folder we hold no grant for can only ever be
    /// pre-navigated to, never acted on.
    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.prompt = i18n.t("settings.general.choosePrompt")
        panel.message = i18n.t("settings.general.chooseMessage")
        if case .resolved(let current) = configured {
            panel.directoryURL = current
        } else {
            panel.directoryURL = ProjectFolderDefaults.suggestedDirectory()
        }

        // Under App Sandbox the panel is hosted out-of-process by the powerbox —
        // the one place appearance inheritance crosses a process boundary — so
        // it is stated rather than trusted. `PanelHost.window` is the canonical
        // host resolution; bare `NSApp.keyWindow` can be nil here.
        let host = PanelHost.window
        panel.adoptHostAppearance(host)

        let handler: (NSApplication.ModalResponse) -> Void = { response in
            guard response == .OK, let url = panel.url else { return }
            ProjectFolderDefaults.setConfigured(url)
            refresh()
        }
        if let host {
            panel.beginSheetModal(for: host, completionHandler: handler)
        } else {
            panel.begin(completionHandler: handler)
        }
    }

    private func refresh() {
        configured = ProjectFolderDefaults.configured()
    }
}
