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

    @ObservedObject var projectIndex: ProjectIndex
    /// The fleet — the pane's only serve input, deliberately.
    ///
    /// It used to also take a `ServeManager`, resolved by `SettingsWindow` as
    /// `serveFleet?.frontedOrIdle`. That looked like a live read and was a
    /// snapshot: the Settings package's `Pane.init` calls its content builder
    /// eagerly and `controller` is a `private lazy var`, so the builder runs
    /// exactly once per process. Launch to Welcome, ⌘, then open a project and
    /// the connection half stayed wired to the idle stand-in — "Start the
    /// project before connecting an agent" printed directly above "Readable
    /// now: 1 project". One pane, two contradictory claims, on the surface
    /// whose only job is being right about exposure.
    ///
    /// `SettingsView`'s own doc-comment records this bug as fixed by holding
    /// the fleet so panes "resolve the current one when they are built" — the
    /// panes are built once, so that was half a fix. Computing it in `body`
    /// is the other half. `frontedProject` is `@Published` and the fleet
    /// re-publishes every manager's changes, so observing the fleet alone is
    /// enough.
    @ObservedObject var serveFleet: ServeFleet

    /// The fronted serve, resolved per render.
    private var serveManager: ServeManager { serveFleet.frontedOrIdle }
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
                .padding(Spacing.margin)
            Divider()
            projectsSection
        }
        // 660, matching Appearance / LLM Provider / Transcription exactly —
        // the Settings package animates HEIGHT per pane, but width jumps
        // read as a bug. Depth is whatever this content needs (fittingSize).
        // The only fixed vertical left is the register's ceiling, so the
        // window cannot grow with the project count; `payloadPane`'s 170pt
        // pin went in 028d539b and switching client tabs DOES reflow now —
        // see the note above `payloadPane` for why that is the fix and not
        // a regression.
        .frame(width: 660)
        .onChange(of: client) {
            copiedResetTask?.cancel()
            copied = false
            // Each dialect is a different number of lines, and the Claude
            // Desktop tab is shorter than all three. The package only sizes
            // the window when you arrive at a PANE, so an in-pane change has
            // to ask for it.
            refit()
        }
        // The register's height is data — a row arriving or leaving, the
        // empty state resolving into a table, a second group header appearing
        // when the first window opens. `rows.count` and the group count are
        // the two things that move it.
        .onChange(of: registerRows.count) { refit() }
        .onChange(of: windowRoster.shownProjects.count) { refit() }
        // The count moving is already feedback — to eyes only. A sighted
        // researcher sees "2 projects" become "1 project" in the moment they
        // untick; VoiceOver hears the checkbox say "unchecked" and nothing
        // about the aggregate. Speaking it is parity, not chatter.
        //
        // Safe only because the roll-up counts a permission
        // (`design-mcp-extension.md` §5a-ter). It moves when the researcher
        // acts — tick, untick, open or close a window — or when a serve
        // TERMINALLY fails, which is worth hearing. Under the reachability
        // reading it would have moved on every transient beat and announced
        // changes nobody made, which is the anti-pattern.
        .onChange(of: spokenRollup) { _, now in announceRollup(now) }
        // A receipt is about what you just did, so it does not outlive the
        // visit — and the visit is the WINDOW being open, not the pane being
        // on screen.
        //
        // This was `.onAppear`, which is wrong in both directions. Too often:
        // the Settings package's tab transition removes and re-adds pane
        // views, so unticking a row, clicking Appearance and clicking back
        // erased the receipt — and a row that vanishes is exactly the "removed
        // the project" reading the receipt exists to prevent. Too rarely:
        // `show(pane:)` early-returns when the pane is already active and
        // `showWindow` never touches the view hierarchy, so ⌘W then ⌘, may
        // leave a stale one, and `Bristlenose ▸ Connect an Agent…` with the
        // pane already open is a guaranteed no-op.
        //
        // Both failures came from hanging a lifetime on a third-party
        // package's view-lifecycle behaviour. The window closing is an event
        // we own, and it is what "next time the pane opens" already meant.
        .onReceive(NotificationCenter.default.publisher(
            for: NSWindow.willCloseNotification)) { note in
            // Identity, not a title or an identifier string: the Settings
            // window is the one `SettingsWindow` owns, and comparing the
            // object is the only test that cannot be fooled by a localised
            // title or an untitled auxiliary window.
            guard let closing = note.object as? NSWindow,
                  closing === SettingsWindow.shared.window else { return }
            revokedThisSession.removeAll()
        }
    }

    /// The roll-up as VoiceOver should hear it.
    ///
    /// Computed even when `registerHeader` suppresses it — the header stays
    /// silent at zero because a readout of two zeros is not a headline, but
    /// reaching zero is the single transition most worth hearing, and it is
    /// exactly when the text disappears.
    private var spokenRollup: String {
        rollupText(AgentProjectRegister.readable(registerRows,
                                                 gate: serveFleet.readableProjects))
    }

    /// Post the roll-up to VoiceOver.
    ///
    /// `NSApp`, because the SDK says an announcement "should be posted for the
    /// application element". Medium priority so it queues behind the
    /// checkbox's own value change rather than cutting across it — the
    /// control answers for itself first, then the aggregate.
    ///
    /// Gated on the Settings window being key: opening a project window from
    /// the main window also moves the count, and speaking about agent scope
    /// at someone who is not in Settings is the chatter this decision was
    /// weighed against.
    private func announceRollup(_ text: String) {
        guard SettingsWindow.shared.window?.isKeyWindow == true else { return }
        NSAccessibility.post(
            element: NSApp as Any,
            notification: .announcementRequested,
            userInfo: [
                .announcement: text,
                .priority: NSAccessibilityPriorityLevel.medium.rawValue,
            ])
    }

    /// Ask the Settings window to take the height this pane now needs.
    ///
    /// After the change, not during it: SwiftUI has not laid the new content
    /// out when `onChange` fires, so measuring here would measure the old
    /// height. One turn of the main queue is enough and is what the package's
    /// own transition completion effectively waits for.
    private func refit() {
        DispatchQueue.main.async { SettingsWindow.shared.refitToContent() }
    }

    /// Everything above the divider: how an agent connects. Machine-wide, and
    /// unchanged in structure by this addition.
    private var connectionSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Body copy, not a title. It was `.title3.weight(.semibold)` —
            // a headline announcing a rule — which gave the pane two
            // competing headings once the register below grew its own, and
            // made a caveat look like a banner. It is a sentence about how
            // the pane behaves, so it is set like one, and it now says only
            // the surprising half: that a closed project is not visible.
            // The Agent Access half is the register's tick column, three
            // inches below, which is a better place to learn it than a
            // qualifier in a heading.
            //
            // The governance switch rides the same line, trailing —
            // baseline-aligned so "Anonymise" sits on the sentence's
            // baseline rather than the switch's centre. Both facts are about
            // WHAT AN AGENT SEES, which is one thought and now reads as one
            // row instead of two stacked claims.
            HStack(alignment: .firstTextBaseline, spacing: Spacing.group) {
                Text(i18n.t("desktop.mcpAgents.header"))
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: Spacing.group)
                // Global, off by default (= names accompany codes, matching
                // the export surfaces' default). Same strings as Export: one
                // word for one concept. Applies via the prefs-changed serve
                // restart.
                Toggle(isOn: $mcpAnonymise) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(i18n.t("desktop.menu.quotes.anonymise"))
                        Text(i18n.t("desktop.menu.quotes.anonymiseHint"))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.switch)
                .fixedSize()
                .onChange(of: mcpAnonymise) {
                    NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
                }
            }

            Picker("", selection: $client) {
                ForEach(AgentClient.allCases) { Text($0.label(i18n)).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .accessibilityLabel(i18n.t("desktop.connectAgent.clientPicker"))
            .padding(.top, Spacing.group)

            payloadPane
                .padding(.top, Spacing.related)
        }
    }

    // MARK: - Spacing

    /// The pane's vertical rhythm, named once.
    ///
    /// Sibling panes (Appearance, General, Transcription) get theirs free from
    /// `Form` + `.formStyle(.grouped)`. This one is hand-built — a segmented
    /// control and a monospaced dialect box do not sit in a Form — so the
    /// rhythm has to be stated rather than inherited, and stated once rather
    /// than as a scatter of 10s and 14s.
    ///
    /// Three steps, which is what the HIG's layout guidance reduces to for a
    /// stack of controls: things that belong together sit close, separate
    /// concerns sit apart, and the window margin is the largest gap on the
    /// pane so nothing appears to float outside it.
    private enum Spacing {
        /// Window margin — leading, trailing, top, and the gap below the last
        /// thing in the pane. A bottom smaller than the top reads as content
        /// that has been cut off.
        static let margin: CGFloat = 20
        /// Between separate concerns.
        static let group: CGFloat = 20
        /// Between a control and the thing that explains or serves it: a hint
        /// and its box, a section heading and its column header.
        static let related: CGFloat = 8
    }

    // MARK: - The projects register

    /// Geometry. Fixed column widths rather than a `Grid`, because the column
    /// header sits OUTSIDE the scroller — so it stays put when the list scrolls
    /// — and a `Grid` cannot align across that boundary. Fixed widths make the
    /// header and the rows share an edge by construction rather than by eye.
    private enum RegisterLayout {
        /// The window margin, so the section header, the column header and
        /// the row content share one leading edge with the connection half
        /// above the divider. Same number as `Spacing.margin`, named here
        /// because the columns are measured from it.
        static let inset: CGFloat = Spacing.margin
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
                    // `.secondary`, for the reason spelled out on the row
                    // style below: `.tertiary` measures 1.88:1 and does not
                    // improve under Increase Contrast. "Throughout the
                    // register" included this line and it was missed.
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, RegisterLayout.inset)
                    .padding(.top, Spacing.related)
            }
        }
        .padding(.bottom, Spacing.margin)
    }

    /// "Projects", and what an agent can read right now.
    @ViewBuilder
    private func registerHeader(_ rows: [AgentProjectRegister.Row]) -> some View {
        let readable = AgentProjectRegister.readable(rows, gate: serveFleet.readableProjects)
        HStack(alignment: .firstTextBaseline, spacing: RegisterLayout.gap) {
            // The sidebar's own word for the same set — reused rather than
            // reworded, so one concept keeps one noun across two surfaces.
            Text(i18n.t("desktop.chrome.projects"))
                .font(.headline)
            Spacer(minLength: RegisterLayout.gap)
            // Says nothing when there is nothing readable — which covers the
            // empty register AND the ordinary case where every armed project
            // is closed. An earlier version suppressed only the first, so
            // opening Settings from Welcome printed "0 projects · 0
            // sessions" over a full table: a readout, not a headline.
            if readable.projects > 0 {
                Text(rollupText(readable))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }
        }
        .padding(.horizontal, RegisterLayout.inset)
        .padding(.top, Spacing.margin)
        .padding(.bottom, Spacing.related)
    }

    /// The headline, with the sessions clause dropped when any of the readable
    /// projects has not reported a count. A partial sum rendered as a total is
    /// a fabricated number, and the rows already refuse to fabricate one.
    private func rollupText(
        _ readable: (projects: Int, sessions: Int, unknown: Int)
    ) -> String {
        let projects = i18n.plural("desktop.mcpAgents.projects", count: readable.projects)
        guard readable.unknown == 0 else {
            return i18n.t("desktop.mcpAgents.rollupProjectsOnly", ["projects": projects])
        }
        return i18n.t("desktop.mcpAgents.rollup", [
            "projects": projects,
            "sessions": i18n.plural("desktop.connectAgent.sessions", count: readable.sessions),
        ])
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
        // Subheadline (11), not Caption 1 (10). The mockup draws this at
        // 11.5px and its own comments fix px↦pt at 1:1; every element it drew
        // at 12 is right in the build and every element it drew at 11.5 had
        // rounded down two rungs. Caption also has no Bold on its ladder —
        // the HIG gives it Medium as the emphasized weight — so the group
        // header below was asking for a weight that does not exist.
        .font(.subheadline.weight(.semibold))
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
                // The separator rides INSIDE the row rather than following it,
                // which fixes three departures from the drawing at once: no
                // stray hairline under the last row of a group (the mockup
                // says `tr:last-child td{border-bottom:0}`), full bleed rather
                // than leading-inset — matching what the column header and the
                // group header in this same file already do — and a row pitch
                // that really is 32pt, so `RegisterLayout.ceiling` is exact.
                // Inset separators made the ceiling short by a divider per row,
                // which clipped the ninth row: a sliver of a TENTH row is a
                // good scroll cue, a sliver of the row you promised is not.
                ForEach(Array(entry.rows.enumerated()), id: \.element.id) { index, row in
                    registerRow(row, now: now)
                        .overlay(alignment: .bottom) {
                            if index < entry.rows.count - 1 { Divider() }
                        }
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
            .font(.subheadline.weight(.semibold))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, RegisterLayout.inset)
            .frame(height: RegisterLayout.groupHeader)
            // `underPageBackgroundColor` is the backdrop BEHIND a document —
            // Preview's surround — and it measures 0.588 grey at 89.8% alpha,
            // i.e. ≈#A1A1A1 over white. The mockup draws #f0f0f3. Dark was a
            // bullseye and light was off by 43% luminance, which is the
            // fingerprint of a token chosen while running in Dark: exactly the
            // "correct in Automatic, wrong the moment you force Light" class
            // desktop/CLAUDE.md's appearance section names.
            //
            // `tertiarySystemFill` lands on the drawing in BOTH modes (black
            // and white at 4.7%). It is translucent by design, so it needs an
            // opaque backer — which the pinned case needs anyway: a header
            // that floats over scrolling rows must not let them show through.
            .background {
                Color(nsColor: .windowBackgroundColor)
                Color(nsColor: .tertiarySystemFill)
            }
            .overlay(alignment: .bottom) { Divider() }
    }

    private func registerRow(_ row: AgentProjectRegister.Row, now: Date) -> some View {
        let asked = lastAskedString(row.lastAsked, now: now)
        return HStack(spacing: RegisterLayout.gap) {
            // The label is a `Color.clear` sized to the whole cell, because a
            // Toggle's label is part of its hit area on macOS and its bounds
            // are otherwise just the ~14pt tick. `.frame` on the Toggle
            // reserves the column without extending the control, so 38 of the
            // 54 points looked clickable and were not — on a permission
            // control, and against the HIG's 20pt macOS minimum. The mockup
            // had this right (`<label class="cell-hit">` wraps the input) and
            // the first build dropped it.
            Toggle(isOn: accessBinding(row)) {
                Color.clear
                    .frame(width: RegisterLayout.access, height: RegisterLayout.row)
                    .contentShape(Rectangle())
            }
            .toggleStyle(.checkbox)
            // Re-ticking is a GRANT, so it answers to the same policy the
            // sidebar's context menu does — `AgentAccessPolicy.canShare`,
            // locatable and analysed. Without this the register was the one
            // Agent Access writer that skipped it: untick a row, let the
            // project's last session go or unplug the drive, re-tick, and it
            // granted what the sidebar would refuse to offer. Unticking is
            // never disabled; revoking is always allowed.
            .disabled(!row.access && !canGrant(row))
            // The shipped sidebar verb, swapping with what the click will
            // do — one grammar in two renderings. A context menu carries a
            // verb; a table carries a checkbox; neither invents a word.
            .help(i18n.t(row.access ? "desktop.menu.project.turnOffAgentAccess"
                                    : "desktop.menu.project.turnOnAgentAccess"))
            // The whole row, spoken. See `AgentProjectRegister.accessibilityLabel`
            // for why the group repeats and why the separator is a comma.
            // The checked/unchecked value is the platform's, and it already
            // covers the receipt — so "Access turned off" is deliberately NOT
            // in here, or the control would announce its own state twice.
            .accessibilityLabel(AgentProjectRegister.accessibilityLabel(
                name: row.name,
                group: i18n.t(row.group == .windowOpen
                              ? "desktop.mcpAgents.groupActive"
                              : "desktop.mcpAgents.groupAvailable"),
                sessions: row.sessions.map {
                    i18n.plural("desktop.connectAgent.sessions", count: $0)
                },
                lastAsked: "\(i18n.t("desktop.mcpAgents.colLastAsked")) \(asked)"))
            .accessibilityHint(i18n.t(row.access
                                      ? "desktop.menu.project.turnOffAgentAccess"
                                      : "desktop.menu.project.turnOnAgentAccess"))
            .frame(width: RegisterLayout.access, alignment: .leading)

            HStack(spacing: 7) {
                // Hidden: the glyph is a recognition aid, the name is the
                // identity, and `Image(systemName:)` otherwise announces the
                // symbol's own description between the checkbox and the name.
                // `ProjectRow` hides the same glyph for the same reason.
                // Sized explicitly because inheriting `.callout` renders it at
                // 12pt, while the sidebar draws the same symbol at 16 in a
                // 20pt column — a researcher's chosen icon should not shrink
                // between two lists of the same projects.
                Image(systemName: row.icon ?? IconPickerPopover.defaultIcon)
                    .font(.system(size: 15))
                    .frame(width: 17)
                    .accessibilityHidden(true)
                Text(row.name)
                    .lineLimit(1)
                    .truncationMode(.tail)
                if row.isReceipt {
                    // The receipt: what you just did, not what is true. Gone
                    // next time the pane opens. `.fixedSize` so a long project
                    // name squeezes itself rather than truncating the caption —
                    // "Access turned…" is worse than a shortened name.
                    Text(i18n.t("desktop.mcpAgents.receiptOff"))
                        .font(.subheadline)
                        .fixedSize()
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Blank when unknown, never a guess — the count a researcher would
            // check against the sidebar has to be one we actually hold. The
            // roll-up above drops its sessions clause entirely in that case
            // rather than summing to a confident zero.
            Text(row.sessions.map(String.init) ?? "")
                .monospacedDigit()
                .frame(width: RegisterLayout.sessions, alignment: .trailing)

            Text(asked)
                .monospacedDigit()
                .lineLimit(1)
                .frame(width: RegisterLayout.lastAsked, alignment: .leading)
        }
        .font(.callout)
        // Two steps, as the mockup draws them: rows at ink, the receipt one
        // step down. `--faint` (#8e8e93 ≈ 3.2:1) is nearer `.secondary` than
        // anything else on the ladder, so `.secondary` is the faithful rung.
        //
        // The rung that was here is the point. `.tertiary` measures 1.88:1 in
        // light and 2.24:1 in dark — a quarter of the 4.5:1 line, and
        // UNCHANGED under Increase Contrast, so the HIG's "at least offer a
        // higher-contrast scheme" escape hatch does not apply. It is also
        // semantically wrong: tertiary is Apple's disabled-text colour, and a
        // receipt row is reversible, not disabled. It survived the fix that
        // was recorded as having removed it — `.primary` moved one arm left
        // instead — so the failing value sat on the one row whose whole job
        // is naming the project you just revoked.
        //
        // Set here and nowhere else. The cells used to set `.secondary` on
        // themselves and an inner style beats the row's, so a revoked row
        // rendered its name dim and its count and timestamp at full weight —
        // the number louder than the thing it counts.
        //
        // The "Never" cell therefore rides the row at `.primary` rather than
        // receding like the mockup's `.last.dash`. Deliberate: "Never" was
        // chosen over an em dash *so it would be perceivable*, and a colour
        // is the wrong channel to make it recede. Weight, if anything.
        .foregroundStyle(row.isReceipt ? AnyShapeStyle(.secondary)
                                       : AnyShapeStyle(.primary))
        .padding(.horizontal, RegisterLayout.inset)
        .frame(height: RegisterLayout.row)
    }

    /// Past tense, always. MCP is request/response — there is no continuous
    /// reading state to report, and the app's own rule is that we can offer but
    /// cannot observe.
    ///
    /// Returns a string rather than a `Text` because the row's accessibility
    /// label needs the same words the cell shows; two renderings of one fact
    /// is how they drift.
    private func lastAskedString(_ date: Date?, now: Date) -> String {
        guard let date else {
            // A word, not an em dash: VoiceOver announces a dash as nothing at
            // all, and "we have no record" is the fact worth hearing.
            return i18n.t("desktop.mcpAgents.lastAskedNever")
        }
        // Under five minutes reads as "Just now" — the sidebar's own threshold,
        // so two surfaces describing one instant agree. A NEGATIVE elapsed
        // lands here too, deliberately: the timeline entry can lag the stamp by
        // up to a minute, and the guard used to be `elapsed >= 0`, which sent
        // exactly that anticipated case to the formatter and rendered "in 45
        // sec" — future tense, in the column whose whole rule is past tense.
        let elapsed = now.timeIntervalSince(date)
        if elapsed < 5 * 60 {
            return i18n.t("desktop.chrome.dateRelativeJustNow")
        }
        return Self.relativeFormatter(locale: i18n.locale)
            .localizedString(for: date, relativeTo: now)
    }

    /// Cached, per locale. `RelativeDateTimeFormatter`'s initialiser loads CLDR
    /// relative-time data, and this was being constructed per row per tick;
    /// `LLMSettingsView` keeps one in a `static let` for the same reason.
    private static var formatterCache: (locale: String, formatter: RelativeDateTimeFormatter)?

    private static func relativeFormatter(locale: String) -> RelativeDateTimeFormatter {
        if let cached = formatterCache, cached.locale == locale { return cached.formatter }
        let f = RelativeDateTimeFormatter()
        f.locale = Locale(identifier: locale)
        f.unitsStyle = .short
        formatterCache = (locale, f)
        return f
    }

    /// Can this row be re-ticked? The sidebar's rule, read here rather than
    /// re-derived — `canShare` wants locatable AND analysed, and a receipt row
    /// can lose either while the pane is open.
    private func canGrant(_ row: AgentProjectRegister.Row) -> Bool {
        guard let project = projectIndex.projects.first(where: { $0.id == row.id })
        else { return false }
        return AgentAccessPolicy.canShare(
            project, sessionCount: projectIndex.unanalysed[row.id]?.sessionCount)
    }

    /// Revoking is one click and no dialog; granting is a deliberate act in the
    /// sidebar. Asymmetric consequences, asymmetric protection — an accidental
    /// revoke costs a trip to the sidebar, an accidental grant costs exposure.
    private func accessBinding(_ row: AgentProjectRegister.Row) -> Binding<Bool> {
        Binding(
            get: { row.access },
            set: { enabled in
                // The receipt follows the model, not the click. Re-ticking a
                // project the policy now refuses (its last session went, or
                // the drive was unplugged) leaves the row where it was rather
                // than showing a grant that did not happen.
                guard projectIndex.setAgentAccess(id: row.id, enabled: enabled) else { return }
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
            //
            // The command is INTERPOLATED, not re-typed. It is an ordinary
            // runtime lookup — only the menu TITLE is stuck in English, because
            // SwiftUI `CommandMenu` titles cannot take a runtime string — and
            // hardcoding it had already drifted on day one: ca and fr wrote the
            // hint with a typographic apostrophe while the menu item carries an
            // ASCII one, so the pane named a menu item using a spelling the
            // menu does not use. Interpolating makes that impossible, and makes
            // any future reword of the command reach this sentence in all 21.
            Text(i18n.t("desktop.mcpAgents.emptyHint", [
                "command": i18n.t("desktop.menu.project.turnOnAgentAccess"),
            ]))
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

    /// Sized to its content, and the window follows.
    ///
    /// This was pinned at 170pt so switching client tabs could never reflow
    /// the pane. That was free while the payload was the LAST thing in the
    /// window — dead space at the bottom of a window is invisible — and it
    /// stopped being free the moment the register appeared below it: the
    /// Claude Desktop tab needs about 150pt less than the tallest tab, so the
    /// reflow protection rendered as a chasm through the middle of the pane.
    ///
    /// The package's own mechanism replaces it. `setWindowFrame` sizes the
    /// window from `view.fittingSize`, and an honest `fittingSize` is exactly
    /// what an unpinned payload reports — so the window now takes the height
    /// each tab actually needs. It calls that only on tab activation, so
    /// `SettingsWindow.refitToContent()` runs the same arithmetic when the
    /// client picker or the register changes shape underneath it.
    ///
    /// Branch order is load-bearing, inherited from the sheet: not-running
    /// speaks before any build-capability claim.
    @ViewBuilder
    private var payloadPane: some View {
        VStack(alignment: .leading, spacing: Spacing.related) {
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
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
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
