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
    /// The fleet, for the projects register: `lastAgentCallAt` is per-project
    /// and `serveManager` is one instance, so the fronted serve cannot answer
    /// for the study an agent is actually reading.
    @ObservedObject var serveFleet: ServeFleet
    /// The window half of the exposure rule. `shownProjects` is derived from
    /// private state, but every write to it also writes the published
    /// `assignments`, so observing the roster is enough to keep the groups true.
    @ObservedObject private var windowRoster = WindowRoster.shared

    @EnvironmentObject private var i18n: I18n
    @State private var client: AgentClient = .claudeDesktop
    @State private var copied = false
    @State private var copiedResetTask: Task<Void, Never>?
    /// Projects unticked while this pane has been open. They stay on screen as
    /// dimmed receipts and can be re-ticked to undo; cleared on `.onAppear`, so
    /// "gone next time the pane opens" is literal rather than approximately
    /// true. Deliberately not persisted: a receipt is about what you just did.
    @State private var revokedThisSession: Set<UUID> = []
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
            connectionSection
                .padding(20)
            Divider()
            projectsSection
        }
        // 660, matching Appearance / LLM Provider / Transcription exactly —
        // the Settings package animates HEIGHT per pane, but width jumps
        // read as a bug. Depth is whatever this content needs (fittingSize);
        // the fixed verticals are payloadPane's (so switching CLIENT tabs
        // never reflows) and the register's ceiling (so the window cannot
        // grow with the project count).
        .frame(width: 660)
        .onChange(of: client) {
            copiedResetTask?.cancel()
            copied = false
        }
        // A receipt is about what you just did, so it does not outlive the
        // visit. `.onAppear` fires each time the pane is shown, which is what
        // makes "gone next time you open it" literal — the Settings package
        // builds its panes once and keeps them, so relying on the view being
        // recreated would have been relying on something that does not happen.
        .onAppear { revokedThisSession.removeAll() }
    }

    /// Everything above the divider: how an agent connects. Machine-wide, and
    /// unchanged in structure by this addition.
    private var connectionSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(i18n.t("desktop.mcpAgents.header"))
                .font(.title3.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)

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
    }

    // MARK: - The projects register

    /// Geometry. Fixed column widths rather than a `Grid`, because the column
    /// header sits OUTSIDE the scroller — so it stays put when the list scrolls
    /// — and a `Grid` cannot align across that boundary. Fixed widths make the
    /// header and the rows share an edge by construction rather than by eye.
    private enum RegisterLayout {
        /// The pane's own padding, so the section header, the column header and
        /// the row content share one leading edge.
        static let inset: CGFloat = 20
        static let gap: CGFloat = 10
        static let access: CGFloat = 54
        static let sessions: CGFloat = 70
        static let lastAsked: CGFloat = 110
        static let row: CGFloat = 32
        static let groupHeader: CGFloat = 27
        /// Rows before the list starts scrolling. Nine because the common case
        /// should never scroll; past that the pinned group headers finally earn
        /// the pinning.
        static let maxRows = 9

        /// A **maximum**, not a height — and it is derived from the groups that
        /// actually exist so the viewport shows nine rows either way.
        static func ceiling(groups: Int) -> CGFloat {
            CGFloat(maxRows) * row + CGFloat(groups) * groupHeader
        }
    }

    /// The register, derived on every read.
    private var registerRows: [AgentProjectRegister.Row] {
        AgentProjectRegister.rows(
            candidates: projectIndex.projects.map { project in
                AgentProjectRegister.Candidate(
                    id: project.id,
                    name: project.name,
                    icon: project.icon,
                    access: project.agentAccess,
                    sessions: projectIndex.unanalysed[project.id]?.sessionCount,
                    lastAsked: serveFleet.lastAgentCallAt[project.id])
            },
            // The same set `ServeFleet.syncHandshake` derives exposure from, so
            // a group header cannot disagree with what an agent can reach.
            shown: windowRoster.shownProjects,
            receipts: revokedThisSession)
    }

    @ViewBuilder
    private var projectsSection: some View {
        let rows = registerRows
        VStack(alignment: .leading, spacing: 0) {
            registerHeader(rows)
            if rows.isEmpty {
                emptyRegister
            } else {
                columnHeader
                registerBody(rows)
                // The times live in memory per serve, so a project asked about
                // yesterday reads "Never" after a relaunch. Saying so is cheaper
                // than a persistence store, and it is a policy rather than an
                // apology — the same discipline that keeps an activity timeline
                // off the auth-exempt health route.
                Text(i18n.t("desktop.mcpAgents.sessionScopeNote"))
                    .font(.footnote)
                    .foregroundStyle(.tertiary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, RegisterLayout.inset)
                    .padding(.top, 8)
            }
        }
        .padding(.bottom, 16)
    }

    /// "Projects", and what an agent can read right now.
    @ViewBuilder
    private func registerHeader(_ rows: [AgentProjectRegister.Row]) -> some View {
        let readable = AgentProjectRegister.readable(rows)
        HStack(alignment: .firstTextBaseline, spacing: RegisterLayout.gap) {
            // The sidebar's own word for the same set — reused rather than
            // reworded, so one concept keeps one noun across two surfaces.
            Text(i18n.t("desktop.chrome.projects"))
                .font(.callout.weight(.bold))
            Spacer(minLength: RegisterLayout.gap)
            // Suppressed when there is nothing shared: "0 projects · 0 sessions"
            // restates the empty state directly beneath it.
            if !rows.isEmpty {
                Text(i18n.t("desktop.mcpAgents.rollup", [
                    "projects": i18n.plural("desktop.mcpAgents.projects",
                                            count: readable.projects),
                    "sessions": i18n.plural("desktop.connectAgent.sessions",
                                            count: readable.sessions),
                ]))
                .font(.callout)
                .foregroundStyle(.secondary)
                .monospacedDigit()
            }
        }
        .padding(.horizontal, RegisterLayout.inset)
        .padding(.top, 15)
        .padding(.bottom, 8)
    }

    /// Outside the scroller, so it stays put once the list is long enough to
    /// move — which is the whole reason a column header exists.
    private var columnHeader: some View {
        HStack(spacing: RegisterLayout.gap) {
            // Headed, so the column does not read as the cloud-import grid's
            // batch-selection ticks. The full verb lives in each row's tooltip.
            Text(i18n.t("desktop.mcpAgents.colAccess"))
                .frame(width: RegisterLayout.access, alignment: .leading)
            Text(i18n.t("desktop.mcpAgents.colProject"))
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(i18n.t("desktop.mcpAgents.colSessions"))
                .frame(width: RegisterLayout.sessions, alignment: .trailing)
            Text(i18n.t("desktop.mcpAgents.colLastAsked"))
                .frame(width: RegisterLayout.lastAsked, alignment: .leading)
        }
        .font(.caption.weight(.semibold))
        .foregroundStyle(.secondary)
        .padding(.horizontal, RegisterLayout.inset)
        .frame(height: 26)
        .background(Color(nsColor: .windowBackgroundColor))
        .overlay(alignment: .bottom) { Divider() }
    }

    /// Nine rows or fewer render as a plain stack with **no scroller**, so the
    /// pane shrinks to its content and the Settings package animates the window
    /// down — the behaviour that package was adopted for.
    ///
    /// This has to switch on the row count rather than clamp a `ScrollView`:
    /// SwiftUI's `ScrollView` is greedy along its scroll axis, so
    /// `ScrollView { rows }.frame(maxHeight: ceiling)` claims the whole ceiling
    /// for two rows and the shrink never happens. The count is known before
    /// layout, so no measurement is needed — the same reasoning that makes the
    /// Sessions grid container queries rather than JS width-switching.
    @ViewBuilder
    private func registerBody(_ rows: [AgentProjectRegister.Row]) -> some View {
        // A minute is the finest distinction "12 minutes ago" can draw, so the
        // clock that drives it ticks once a minute. `TimelineView` stops when
        // the pane is off screen; a `Timer` publisher would not.
        TimelineView(.periodic(from: .now, by: 60)) { context in
            let groups = Self.grouped(rows)
            if rows.count <= RegisterLayout.maxRows {
                VStack(spacing: 0) { groupedRows(groups, now: context.date) }
            } else {
                ScrollView(.vertical) {
                    LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                        groupedRows(groups, now: context.date)
                    }
                }
                .frame(height: RegisterLayout.ceiling(groups: groups.count))
            }
        }
    }

    /// Rows in group order, each group behind its own pinnable header.
    @ViewBuilder
    private func groupedRows(
        _ groups: [(group: AgentProjectRegister.Group, rows: [AgentProjectRegister.Row])],
        now: Date
    ) -> some View {
        ForEach(groups, id: \.group) { entry in
            Section {
                ForEach(entry.rows) { row in
                    registerRow(row, now: now)
                    Divider().padding(.leading, RegisterLayout.inset)
                }
            } header: {
                groupHeader(entry.group)
            }
        }
    }

    /// Stable group order — window-open first, and only groups that have rows.
    /// An empty "Available when opened" header would be a promise about a set
    /// with nothing in it.
    private static func grouped(
        _ rows: [AgentProjectRegister.Row]
    ) -> [(group: AgentProjectRegister.Group, rows: [AgentProjectRegister.Row])] {
        [AgentProjectRegister.Group.windowOpen, .availableWhenOpened]
            .compactMap { group in
                let members = rows.filter { $0.group == group }
                return members.isEmpty ? nil : (group, members)
            }
    }

    private func groupHeader(_ group: AgentProjectRegister.Group) -> some View {
        Text(i18n.t(group == .windowOpen
                    ? "desktop.mcpAgents.groupActive"
                    : "desktop.mcpAgents.groupAvailable"))
            .font(.caption.weight(.bold))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, RegisterLayout.inset)
            .frame(height: RegisterLayout.groupHeader)
            .background(Color(nsColor: .underPageBackgroundColor))
            .overlay(alignment: .bottom) { Divider() }
    }

    private func registerRow(_ row: AgentProjectRegister.Row, now: Date) -> some View {
        HStack(spacing: RegisterLayout.gap) {
            Toggle(isOn: accessBinding(row)) { EmptyView() }
                .toggleStyle(.checkbox)
                .labelsHidden()
                // The shipped sidebar verb, swapping with what the click will
                // do — one grammar in two renderings. A context menu carries a
                // verb; a table carries a checkbox; neither invents a word.
                .help(i18n.t(row.access ? "desktop.menu.project.turnOffAgentAccess"
                                        : "desktop.menu.project.turnOnAgentAccess"))
                .accessibilityLabel(row.name)
                .accessibilityHint(i18n.t(row.access
                                          ? "desktop.menu.project.turnOffAgentAccess"
                                          : "desktop.menu.project.turnOnAgentAccess"))
                .frame(width: RegisterLayout.access, alignment: .leading)

            HStack(spacing: 7) {
                Image(systemName: row.icon ?? IconPickerPopover.defaultIcon)
                    .frame(width: 17)
                Text(row.name)
                    .lineLimit(1)
                    .truncationMode(.tail)
                if row.isReceipt {
                    // The receipt: what you just did, not what is true. Gone
                    // next time the pane opens.
                    Text(i18n.t("desktop.mcpAgents.receiptOff"))
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Blank when unknown, never a guess — the count a researcher would
            // check against the sidebar has to be one we actually hold.
            Text(row.sessions.map(String.init) ?? "")
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .frame(width: RegisterLayout.sessions, alignment: .trailing)

            lastAskedText(row.lastAsked, now: now)
                .frame(width: RegisterLayout.lastAsked, alignment: .leading)
        }
        .font(.callout)
        .foregroundStyle(row.isReceipt ? AnyShapeStyle(.tertiary) : AnyShapeStyle(.primary))
        .padding(.horizontal, RegisterLayout.inset)
        .frame(height: RegisterLayout.row)
    }

    /// Past tense, always. MCP is request/response — there is no continuous
    /// reading state to report, and the app's own rule is that we can offer but
    /// cannot observe.
    private func lastAskedText(_ date: Date?, now: Date) -> some View {
        let text: String
        if let date {
            // Under five minutes reads as "Just now" — the sidebar's own
            // threshold, so two surfaces describing one instant agree.
            let elapsed = now.timeIntervalSince(date)
            if elapsed >= 0 && elapsed < 5 * 60 {
                text = i18n.t("desktop.chrome.dateRelativeJustNow")
            } else {
                let f = RelativeDateTimeFormatter()
                f.locale = Locale(identifier: i18n.locale)
                f.unitsStyle = .short
                text = f.localizedString(for: date, relativeTo: now)
            }
        } else {
            // A word, not an em dash: VoiceOver announces a dash as nothing at
            // all, and "we have no record" is the fact worth hearing.
            text = i18n.t("desktop.mcpAgents.lastAskedNever")
        }
        return Text(text)
            .foregroundStyle(date == nil ? AnyShapeStyle(.tertiary)
                                         : AnyShapeStyle(.secondary))
            .monospacedDigit()
            .lineLimit(1)
    }

    /// Revoking is one click and no dialog; granting is a deliberate act in the
    /// sidebar. Asymmetric consequences, asymmetric protection — an accidental
    /// revoke costs a trip to the sidebar, an accidental grant costs exposure.
    private func accessBinding(_ row: AgentProjectRegister.Row) -> Binding<Bool> {
        Binding(
            get: { row.access },
            set: { enabled in
                projectIndex.setAgentAccess(id: row.id, enabled: enabled)
                if enabled {
                    revokedThisSession.remove(row.id)
                } else {
                    revokedThisSession.insert(row.id)
                }
            })
    }

    /// The one moment the audit surface points at the management surface —
    /// necessarily, since a researcher who has never granted access has nothing
    /// here to act on.
    private var emptyRegister: some View {
        VStack(spacing: 3) {
            Text(i18n.t("desktop.mcpAgents.emptyTitle"))
                .font(.callout.weight(.semibold))
            // Names the menu-bar path, not a gesture: the HIG calls it
            // Control-click or secondary click, never right-click, and requires
            // every context-menu command to exist in the menu bar anyway.
            Text(i18n.t("desktop.mcpAgents.emptyHint"))
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, RegisterLayout.inset)
        .padding(.vertical, 26)
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
