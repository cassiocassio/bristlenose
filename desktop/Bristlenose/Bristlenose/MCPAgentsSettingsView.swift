import AppKit
import SwiftUI

/// Settings ▸ MCP Agents — the global home for connecting agents
/// (design-mcp-extension §3.7, decided 31 Jul 2026). Supersedes the
/// per-project Connect Agent sheet: installing is a once-ever, machine-wide
/// act, and the pane does not change shape with project state.
///
/// Layout, top to bottom (the mockup `docs/mockups/mcp-extension-ux.html`
/// is the spec):
/// - Header, always: "Agents read whichever project is selected in
///   Bristlenose." The behaviour is genuinely surprising; saying it plainly
///   is the v1 answer.
/// - Sub-line only while a project is serving: "Now showing: …". With
///   nothing selected it simply disappears — absence is the information,
///   no placeholder, no "no project selected".
/// - The GLOBAL Anonymise switch, off by default — one switch for the whole
///   MCP surface, not a per-project matrix (decided 1 Aug 2026; the
///   per-project list was retired as over-build — the sidebar's menu +
///   antenna carry the whole per-project exposure story, §5a-bis).
/// - Install row (machine-wide, so ABOVE the client tabs).
/// - Four client tabs: Claude Desktop (the install hint), Claude Code /
///   ChatGPT & Codex (commands in their own dialects), Generic MCP (the raw
///   URL + token — the fallback that makes replacing hand-paste safe).
struct MCPAgentsSettingsView: View {

    @ObservedObject var serveManager: ServeManager
    @ObservedObject var projectIndex: ProjectIndex

    @EnvironmentObject private var i18n: I18n
    @State private var client: AgentClient = .claudeDesktop
    @State private var copied = false
    @State private var copiedResetTask: Task<Void, Never>?
    /// Global Anonymise for agents. Rides the serve env
    /// (`BRISTLENOSE_MCP_ANONYMISE`, injected by `overlayPreferences`) and
    /// applies via the prefs-changed serve restart — the same lifecycle as
    /// every other Settings preference.
    @AppStorage("mcpAnonymise") private var mcpAnonymise = false

    enum AgentClient: String, CaseIterable, Identifiable {
        case claudeDesktop, claudeCode, chatgptCodex, generic
        var id: String { rawValue }

        @MainActor func label(_ i18n: I18n) -> String {
            switch self {
            case .claudeDesktop: return i18n.t("desktop.connectAgent.clients.claudeDesktop")
            case .claudeCode: return i18n.t("desktop.connectAgent.clients.claudeCode")
            case .chatgptCodex: return i18n.t("desktop.connectAgent.clients.chatgptCodex")
            case .generic: return i18n.t("desktop.mcpAgents.clients.generic")
            }
        }

        /// The two primitives in this client's own dialect. Claude Desktop
        /// has no payload — its tab is the install hint; the extension's
        /// handshake file carries the address and token so there is nothing
        /// to copy. Dialects verified 30 Jul 2026; canonical copies in the
        /// website manual (bristlenose.app/docs/connect-an-agent.html).
        func payload(endpoint: String, token: String) -> String? {
            switch self {
            case .claudeDesktop:
                return nil
            case .claudeCode:
                return """
                claude mcp add --transport http bristlenose \(endpoint) \\
                  --header "Authorization: Bearer \(token)"
                """
            case .chatgptCodex:
                return """
                [mcp_servers.bristlenose]
                url = "\(endpoint)"
                http_headers = { "Authorization" = "Bearer \(token)" }
                """
            case .generic:
                return """
                \(endpoint)
                Authorization: Bearer \(token)
                """
            }
        }

        @MainActor func how(_ i18n: I18n) -> String? {
            switch self {
            case .claudeDesktop: return nil
            case .claudeCode: return i18n.t("desktop.connectAgent.claudeCodeHow")
            case .chatgptCodex: return i18n.t("desktop.connectAgent.chatgptCodexHow")
            case .generic: return i18n.t("desktop.mcpAgents.genericHow")
            }
        }

        @MainActor func actionTitle(_ i18n: I18n) -> String {
            switch self {
            case .claudeCode: return i18n.t("desktop.connectAgent.copyCommand")
            default: return i18n.t("desktop.connectAgent.copyConfig")
            }
        }
    }

    // MARK: - Derived serve state

    /// The project currently serving (fronted + running) — the pane's
    /// "Now showing" subject and the only row whose Anonymise is readable.
    private var servingProject: Project? {
        guard serveManager.runningPort != nil,
              let path = serveManager.currentProjectPath else { return nil }
        return projectIndex.projects.first { AgentActivity.samePath($0.path, path) }
    }

    private var endpoint: String? {
        serveManager.runningPort.map { "http://127.0.0.1:\($0)/mcp/" }
    }

    /// Payload token: MCP-scoped ONLY — never `authToken`, which opens
    /// /api/* (the handshake writer holds the same invariant).
    private var mcpToken: String? { serveManager.mcpToken }

    private var payloadText: String? {
        guard let endpoint, let token = mcpToken else { return nil }
        return client.payload(endpoint: endpoint, token: token)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(i18n.t("desktop.mcpAgents.header"))
                .font(.title3.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)

            if let project = servingProject {
                nowShowingLine(project)
                    .padding(.top, 2)
            }

            // The one governance control on the pane — global, off by
            // default (= names accompany codes, matching the export
            // surfaces' default). Same strings as Export: one word for one
            // concept. Applies via the prefs-changed serve restart.
            Toggle(isOn: $mcpAnonymise) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(i18n.t("desktop.menu.quotes.anonymise"))
                    Text(i18n.t("desktop.menu.quotes.anonymiseHint"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .toggleStyle(.switch)
            .padding(.top, 14)
            .onChange(of: mcpAnonymise) {
                NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
            }

            installRow
                .padding(.top, 14)

            Picker("", selection: $client) {
                ForEach(AgentClient.allCases) { Text($0.label(i18n)).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .accessibilityLabel(i18n.t("desktop.connectAgent.clientPicker"))
            .padding(.top, 14)

            payloadPane
                .padding(.top, 10)
        }
        .padding(20)
        // 660, matching Appearance / LLM Provider / Transcription exactly —
        // the Settings package animates HEIGHT per pane, but width jumps
        // read as a bug. Depth is whatever this content needs (fittingSize);
        // the only fixed vertical is payloadPane's, which exists so
        // switching CLIENT tabs never reflows within the pane.
        .frame(width: 660)
        .onChange(of: client) {
            copiedResetTask?.cancel()
            copied = false
        }
    }

    // MARK: - Header pieces

    private func nowShowingLine(_ project: Project) -> some View {
        // Sessions only when known — the host's snapshot carries sessions,
        // not quotes; never invent a number (sheet precedent).
        var line = i18n.t("desktop.mcpAgents.nowShowing", ["project": project.name])
        if let sessions = projectIndex.unanalysed[project.id]?.sessionCount {
            line += " · " + i18n.plural("desktop.connectAgent.sessions", count: sessions)
        }
        return Text(line)
            .font(.body)
            .foregroundStyle(.secondary)
    }

    /// The machine-wide install row. Open, don't reveal (§3.4): the Mac
    /// idiom for handing a plug-in to another app is a typed file you
    /// double-click, and LaunchServices runs Claude Desktop's own install
    /// flow — the consent moment belongs to the app being modified.
    private var installRow: some View {
        HStack(spacing: 12) {
            Image(nsImage: NSApp.applicationIconImage)
                .resizable()
                .frame(width: 38, height: 38)
            VStack(alignment: .leading, spacing: 1) {
                Text("Bristlenose")
                    .font(.body.weight(.semibold))
                Text(installSubtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if MCPExtensionInstaller.claudeDesktopCanInstall {
                // The pane's ONE prominent action (HIG: a single filled
                // button per surface; the per-tab Copy stays bordered).
                Button(i18n.t("desktop.mcpAgents.install")) {
                    MCPExtensionInstaller.install()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!MCPExtensionInstaller.bundledExtensionExists)
            } else {
                // No handler registered for .mcpb — Claude Desktop isn't
                // installed. A live button would produce the system's
                // "no application set to open the document" dialog, which
                // reads as our bug; offer the download instead (§3.4).
                Link(i18n.t("desktop.mcpAgents.downloadClaudeDesktop"),
                     destination: URL(string: "https://claude.ai/download")!)
                    .font(.callout)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(nsColor: .textBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color(nsColor: .separatorColor), lineWidth: 1)
        )
    }

    private var installSubtitle: String {
        // "An agent has asked about this project recently" is the better
        // fact when we have it (mcp.active — the visit-two "did it take?"
        // answer, §3.4); the static size line otherwise. We never claim
        // "Installed": we cannot observe the other app.
        if serveManager.agentActiveNow {
            return i18n.t("desktop.mcpAgents.recentActivity")
        }
        return i18n.t(
            "desktop.mcpAgents.extensionSubtitle",
            ["size": MCPExtensionInstaller.bundledSizeDisplay ?? "4 KB"]
        )
    }

    // MARK: - Client tabs

    /// Fixed height — switching clients never reflows the pane (geometry is
    /// fixed, content bends). Branch order is load-bearing, inherited from
    /// the sheet: not-running speaks before any build-capability claim.
    @ViewBuilder
    private var payloadPane: some View {
        VStack(alignment: .leading, spacing: 6) {
            if client == .claudeDesktop {
                Text(i18n.t("desktop.mcpAgents.claudeDesktopHint"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            } else if endpoint == nil {
                Text(i18n.t("desktop.connectAgent.notRunning"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else if !serveManager.mcpMounted {
                Text(i18n.t("desktop.connectAgent.unavailable"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else if let payloadText {
                if let how = client.how(i18n) {
                    Text(how)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text(payloadText)
                    .font(.subheadline.monospaced())
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(8)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color(nsColor: .textBackgroundColor))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color(nsColor: .separatorColor), lineWidth: 1)
                    )
                HStack(alignment: .top) {
                    // info-circle / secondary, NOT a caution triangle: the
                    // HIG reserves warnings for negative consequences, and
                    // a permanent warning stops being read (mockup §2).
                    Text(i18n.t("desktop.connectAgent.addressNote"))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    Button(action: copy) {
                        ZStack {
                            Text(client.actionTitle(i18n)).opacity(copied ? 0 : 1)
                            Text(i18n.t("desktop.connectAgent.copied")).opacity(copied ? 1 : 0)
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .frame(height: 170, alignment: .topLeading)
    }

    private func copy() {
        guard let payloadText else { return }
        let pb = NSPasteboard.general
        // Bearer token on board: keep it off Universal Clipboard and mark
        // it concealed so clipboard-history managers skip it.
        pb.prepareForNewContents(with: .currentHostOnly)
        let item = NSPasteboardItem()
        item.setString(payloadText, forType: .string)
        item.setString("", forType: NSPasteboard.PasteboardType("org.nspasteboard.ConcealedType"))
        pb.writeObjects([item])
        copied = true
        Task { await serveManager.refreshAgentActivity() }
        AccessibilityNotification.Announcement(
            i18n.t("desktop.connectAgent.copied")).post()
        copiedResetTask?.cancel()
        copiedResetTask = Task {
            try? await Task.sleep(for: .seconds(1.6))
            guard !Task.isCancelled else { return }
            copied = false
        }
    }
}

/// The `.mcpb` hand-off to Claude Desktop (design-mcp-extension §3.4).
///
/// Never hand LaunchServices a path inside our bundle — `Contents/Resources`
/// changes on every app update and can be replaced under a running Claude
/// Desktop. Copy the bundled `.mcpb` once into the container beside the
/// handshake file, refresh when the bundled copy is newer, and open THAT.
@MainActor
enum MCPExtensionInstaller {

    static let filename = "Bristlenose.mcpb"

    static var bundledURL: URL? {
        Bundle.main.resourceURL?.appendingPathComponent(filename)
    }

    static var bundledExtensionExists: Bool {
        bundledURL.map { FileManager.default.fileExists(atPath: $0.path) } ?? false
    }

    /// "4 KB"-style size of the bundled extension, for the install row.
    static var bundledSizeDisplay: String? {
        guard let url = bundledURL,
              let size = try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int
        else { return nil }
        return ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file)
    }

    /// Is anything registered to open a `.mcpb`? Answered by LaunchServices
    /// with no entitlement — nil means Claude Desktop (or any handler) is
    /// absent and the UI should offer the download link instead of a live
    /// button that would produce the system's "no application set" dialog.
    static var claudeDesktopCanInstall: Bool {
        guard let url = bundledURL else { return false }
        return NSWorkspace.shared.urlForApplication(toOpen: url) != nil
    }

    /// Copy-then-open. 0644 is fine — the `.mcpb` carries no secret (the
    /// token travels in the handshake, not the extension).
    static func install() {
        guard let bundled = bundledURL,
              let container = MCPHandshake.defaultDirectory() else { return }
        let dest = container.appendingPathComponent(filename)
        let fm = FileManager.default
        do {
            try fm.createDirectory(at: container, withIntermediateDirectories: true)
            if fm.fileExists(atPath: dest.path) {
                // Refresh only when the bundled copy is newer.
                let bundledDate = (try? fm.attributesOfItem(atPath: bundled.path)[.modificationDate] as? Date) ?? .distantPast
                let destDate = (try? fm.attributesOfItem(atPath: dest.path)[.modificationDate] as? Date) ?? .distantPast
                if bundledDate > destDate {
                    try fm.removeItem(at: dest)
                    try fm.copyItem(at: bundled, to: dest)
                }
            } else {
                try fm.copyItem(at: bundled, to: dest)
            }
            NSWorkspace.shared.open(dest)
        } catch {
            // Degraded, not broken: last resort is opening the bundled copy
            // directly — worse (path churns on update) but not wrong.
            NSWorkspace.shared.open(bundled)
        }
    }
}
