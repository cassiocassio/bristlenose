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

        /// Stand-ins for the two live values, used when nothing is serving.
        /// Deliberately NOT localised: the block they sit in is a shell
        /// command / TOML, which isn't localised either.
        static let placeholderEndpoint = "<address>"
        static let placeholderToken = "<token>"

        /// The dialect with its two live values stubbed out. Built through
        /// `payload(endpoint:token:)` rather than written out again, so the
        /// placeholder can never drift from the real thing — and so it has
        /// the same line count, which is what keeps the pane from reflowing
        /// between the two states.
        var placeholderPayload: String? {
            payload(endpoint: Self.placeholderEndpoint, token: Self.placeholderToken)
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
                Button(i18n.t(extensionState.buttonKey)) {
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

    /// What we ship, compared against what called us. Derived, never assumed.
    private var extensionState: MCPExtensionState {
        MCPExtensionState.compare(
            bundled: MCPExtensionInstaller.bundledStamp,
            running: serveManager.agentProxyVersion
        )
    }

    private var installSubtitle: String {
        // Two facts want this one slot, and activity wins while it lasts.
        //
        // "An agent has asked about this project recently" is the visit-two
        // "did it take?" answer (§3.4) and is TRANSIENT — `mcp.active` is a
        // tool call within the last two minutes. The build identity is
        // PERMANENT. A transient fact displacing a permanent one for two
        // minutes loses nothing; the reverse would lose the install
        // confirmation entirely. Decided 20 Aug 2026.
        //
        // The size ("Extension · 8 KB") held this slot until the same pass
        // and was dropped: it answered no question anyone asks, while the
        // build number is something a researcher might act on.
        //
        // We still never claim "Installed" — naming our OWN build is not a
        // claim about Claude Desktop's state.
        if serveManager.agentActiveNow {
            return i18n.t("desktop.mcpAgents.recentActivity")
        }
        let identity = MCPExtensionState.identity(bundled: MCPExtensionInstaller.bundledStamp)
        guard let identity else { return i18n.t("desktop.mcpAgents.extensionUnknownBuild") }
        return i18n.t("desktop.mcpAgents.extensionBuild", ["version": identity])
    }

    /// The comparison line — and ONLY a comparison, never a restatement.
    ///
    /// It appears solely when the running proxy differs from the one we ship,
    /// so its presence is itself the signal and the remedy is the button
    /// directly above it. Naming both versions unconditionally (the first cut)
    /// made the in-sync resting state read as a mismatch, because a
    /// release-only string sits beside a release+hash one. A diagnostic that
    /// cries wolf at rest gets ignored.
    ///
    /// Deliberately NOT a warning and not phrased as one. An older proxy in
    /// the field is the normal resting state, not a fault — `mcp.contract`
    /// decides whether it can still be understood. This reports; it does not
    /// judge, and it never says "older" unless semver actually ordered it.
    private var buildLine: String? {
        guard let key = extensionState.footnoteKey,
              let installed = extensionState.installedDisplay else { return nil }
        return i18n.t(key, ["version": installed])
    }

    // MARK: - Client tabs

    /// Fixed height — switching clients never reflows the pane (geometry is
    /// fixed, content bends). Branch order is load-bearing, inherited from
    /// the sheet: not-running speaks before any build-capability claim.
    @ViewBuilder
    private var payloadPane: some View {
        VStack(alignment: .leading, spacing: 6) {
            if client == .claudeDesktop {
                // The install row IS this tab's payload — the .mcpb is
                // Claude Desktop-only, so it belongs under that tab, in
                // the slot where every other tab shows its dialect. Hint
                // then row, mirroring the other tabs' hint-then-payload
                // (and the mockup's Claude Desktop pane).
                Text(i18n.t("desktop.mcpAgents.claudeDesktopHint"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                installRow
                // Directly under the row it describes, because it is a fact
                // ABOUT the thing that row installs — not a consequence of
                // pressing it (that's the prompt note below, which is
                // deliberately placed by WHEN it happens, not by topic).
                if let buildLine {
                    Text(buildLine)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                }
                // Pre-announce the one-time macOS prompt (§5c, §6.1). A
                // prompt you were told to expect reads as a boundary
                // working; an unannounced one reads as a fault — and this
                // one fires at the exact moment we promised "done".
                //
                // It sits BELOW the row because that is when it happens:
                // the proxy reads the handshake only inside tool calls, so
                // the dialog appears on the first QUESTION, not on install.
                // Same slot the other three tabs give `addressNote`.
                //
                // Info register, never a caution triangle — the HIG
                // reserves warnings for negative consequences and nothing
                // here has gone wrong. Each locale's string quotes macOS's
                // OWN dialog wording and button label (lifted from
                // TCC.framework's Localizable.loctable), so the sentence
                // read here matches the dialog seen a moment later.
                Text(i18n.t("desktop.mcpAgents.claudeDesktopPromptNote"))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            } else if endpoint == nil {
                // Nothing is serving, so there is no address and no token —
                // but the SHAPE of the config is the useful thing to a
                // researcher who opened Settings from Welcome to do setup.
                // Same structure as the live branch (hint, box, footnote +
                // button), stubbed and inert: nothing here can be copied
                // wrong, and the pane doesn't change shape with project
                // state (§3.7's own rule, which this slot used to break).
                if let how = client.how(i18n) {
                    Text(how)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                dialectBox(client.placeholderPayload ?? "", live: false)
                HStack(alignment: .top) {
                    // The footnote carries `notRunning` rather than the live
                    // branch's `addressNote`: it says why everything is grey,
                    // and a caveat about restarts is moot when nothing runs.
                    Text(i18n.t("desktop.connectAgent.notRunning"))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    copyButton(live: false)
                }
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
                dialectBox(payloadText, live: true)
                    .textSelection(.enabled)
                HStack(alignment: .top) {
                    // info-circle / secondary, NOT a caution triangle: the
                    // HIG reserves warnings for negative consequences, and
                    // a permanent warning stops being read (mockup §2).
                    Text(i18n.t("desktop.connectAgent.addressNote"))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    copyButton(live: true)
                }
            }
            Spacer(minLength: 0)
        }
        .frame(height: 170, alignment: .topLeading)
    }

    /// One definition of the dialect box, so the live and placeholder states
    /// are pixel-identical by construction rather than by eye. `live: false`
    /// greys the text; the field's background and border are untouched, so the
    /// footprint doesn't move. `disabledControlTextColor` is the system's own
    /// answer for text in a disabled control, so it tracks appearance and
    /// accessibility for free.
    ///
    /// Selectability is deliberately NOT set here. `TextSelectability`'s two
    /// cases are distinct types, so a ternary can't unify them — and it needs
    /// no ternary: `Text` is unselectable by default, which is what the
    /// placeholder wants, so only the live call site opts in.
    private func dialectBox(_ text: String, live: Bool) -> some View {
        Text(text)
            .font(.subheadline.monospaced())
            .foregroundStyle(live ? Color.primary
                                  : Color(nsColor: .disabledControlTextColor))
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
    }

    /// Shared so the disabled button is the same width as the live one — the
    /// ZStack sizes to the wider of the two labels either way, so the footnote
    /// row doesn't shift when a serve comes up.
    private func copyButton(live: Bool) -> some View {
        Button { if live { copy() } } label: {
            ZStack {
                Text(client.actionTitle(i18n)).opacity(copied ? 0 : 1)
                Text(i18n.t("desktop.connectAgent.copied")).opacity(copied ? 1 : 0)
            }
        }
        .disabled(!live)
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

    /// The packed proxy's stamped `<release>+<hash>`, read from the sibling
    /// file `build-mcpb.sh` writes beside the archive in the same run.
    ///
    /// Why a sibling file rather than the archive itself: the app needs the
    /// HASH to answer "is the copy running inside Claude Desktop the one I
    /// ship?", and it cannot get it from the `.mcpb`. `CFBundleShortVersionString`
    /// is release-only, and reading the zip would mean shelling out to
    /// `unzip`, which App Sandbox blocks. Without the hash, two packs of the
    /// same release are indistinguishable — precisely the case that cost six
    /// reinstall cycles on 20 Aug 2026.
    ///
    /// The "a second artefact goes stale invisibly" objection is answered by
    /// construction, not by promise: `build-mcpb.sh` writes both files on
    /// adjacent lines of one run, `ensure-sidecar.sh` repacks on every Cmd+R
    /// so neither can lag the source, and this accessor requires both to
    /// exist AND to agree on the release half before trusting the hash.
    ///
    /// Falls back to the app's own release when the stamp file is absent —
    /// an older bundle, or a build that predates it — so the pane degrades to
    /// release-only rather than to a confident wrong answer. Returns nil when
    /// no extension is bundled at all (`Bristlenose.mcpb` is gitignored, so a
    /// fresh clone has none), because a pane whose job is telling the truth
    /// about builds must not name a version for a file that isn't there.
    static var bundledStamp: String? {
        guard bundledExtensionExists else { return nil }
        let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        guard let stampURL = Bundle.main.resourceURL?
                .appendingPathComponent("\(filename).version"),
              let raw = try? String(contentsOf: stampURL, encoding: .utf8)
        else { return (appVersion?.isEmpty == false) ? appVersion : nil }

        let stamp = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !stamp.isEmpty else { return (appVersion?.isEmpty == false) ? appVersion : nil }

        // Cross-check the halves. A stamp naming a different release than the
        // app means the two artefacts were assembled apart — exactly the
        // staleness this is meant to expose, so believe neither's hash and
        // fall back to the release we can vouch for.
        if let appVersion, !appVersion.isEmpty,
           MCPExtensionState.release(of: stamp) != appVersion {
            return appVersion
        }
        return stamp
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
