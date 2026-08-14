import SwiftUI

/// The session-switcher popover's content: the **All Sessions** row, one
/// separator, then the session list (or its empty / failure state).
///
/// Presentation (which toolbar button shows it, what the callbacks navigate)
/// is the next commit's wiring — this view takes closures and knows nothing
/// about the bridge.
///
/// Two structural rules from the design doc §States:
/// - **All Sessions renders unconditionally.** It is a route change needing no
///   fetch, so it must keep working when the list cannot load — it is the
///   escape hatch that stops a failed fetch stranding the researcher on one
///   session.
/// - **Empty is not failure.** A 200 with zero sessions renders "No sessions
///   yet" — the state a just-imported project is in — never the failure text.
struct SessionsPopoverContent: View {
    @ObservedObject var model: SessionsPopoverModel
    @ObservedObject var i18n: I18n
    let activeSessionID: String?
    let onAllSessions: () -> Void
    let onCommit: (SessionsPopoverSpec.Session) -> Void
    let onDismiss: () -> Void
    let onRetry: () -> Void

    /// Width shared with the export popover (`ExportPopoverContent`) so the two
    /// toolbar popovers read as one family.
    private static let width: CGFloat = 308
    /// List height cap: fits the common case measured from REAL row heights
    /// (the earlier 560pt figure was single-line arithmetic and clipped the
    /// mockup's own default study); past the cap the source list scrolls
    /// natively.
    private static let maxListHeight: CGFloat = 660

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            allSessionsRow
            Divider().padding(.horizontal, 10)
            content
        }
        .frame(width: Self.width)
        .padding(.vertical, 6)
    }

    // MARK: - All Sessions

    private var allSessionsRow: some View {
        SessionsPopoverActionRow(
            systemImage: "square.grid.2x2",   // the glyph ExportPopoverContent already uses
            title: i18n.t("desktop.sessionsPopover.allSessions"),
            subtitle: allSessionsSubtitle
        ) {
            onAllSessions()
        }
    }

    private var allSessionsSubtitle: String? {
        guard case .loaded(let sessions) = model.state else { return nil }
        return i18n.plural("desktop.sessionsPopover.allCount", count: sessions.count)
    }

    // MARK: - States

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .loading:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(i18n.t("common.sessions.loading"))
                    .foregroundStyle(.secondary)
            }
            .padding(12)

        case .empty:
            Text(i18n.t("desktop.sessionsPopover.noSessions"))
                .foregroundStyle(.secondary)
                .padding(12)

        case .unreachable:
            VStack(alignment: .leading, spacing: 8) {
                Text(i18n.t("desktop.sessionsPopover.loadFailed"))
                    .foregroundStyle(.secondary)
                Button(i18n.t("common.buttons.retry")) { onRetry() }
                    .controlSize(.small)
            }
            .padding(12)

        case .loaded(let sessions):
            let rows = buildRows(sessions)
            SessionsPopoverList(
                rows: rows,
                activeSessionID: activeSessionID,
                onCommit: { session in
                    onCommit(session)
                    onDismiss()
                },
                onCancel: onDismiss
            )
            .frame(width: Self.width,
                   height: min(listHeight(rows), Self.maxListHeight))
        }
    }

    // MARK: - Row assembly

    /// Localised strings resolve HERE, once per load — the list and cells stay
    /// i18n-free and testable. Title reuses the reviewed
    /// `common.autocode.sessionLabel` twin ("Session {{id}}" — de
    /// "Interview {{id}}"); the placeholder reuses
    /// `common.sessions.speakerPlaceholder.participant`.
    private func buildRows(_ sessions: [SessionsPopoverSpec.Session]) -> [SessionsPopoverRow] {
        let placeholder = i18n.t("common.sessions.speakerPlaceholder.participant")
        return sessions.map { session in
            let title = i18n.t("common.autocode.sessionLabel", ["id": String(session.number)])
            let duration = DurationFormat.human(seconds: session.durationSeconds)
            let date = SessionsFinderDate.format(session.isoDate, localeCode: i18n.locale)
            return SessionsPopoverRow(
                session: session,
                title: title,
                subtitle: "\(duration) · \(date)",
                placeholder: placeholder,
                typeSelect: SessionsPopoverSpec.typeSelectString(
                    for: session, title: title, placeholder: placeholder),
                accessibility: SessionsPopoverSpec.accessibilityLabel(
                    for: session, title: title, placeholder: placeholder,
                    duration: duration, date: date)
            )
        }
    }

    private func listHeight(_ rows: [SessionsPopoverRow]) -> CGFloat {
        rows.reduce(0) { total, row in
            total + SessionsPopoverSpec.rowHeight(participantCount: row.session.participants.count)
        }
    }
}

// MARK: - Toolbar button

extension Notification.Name {
    /// Posted to present the session switcher from outside the toolbar — the
    /// menu twin (commit 3 repoints ⌘⌥L here on the Sessions lens) and any
    /// future affordance. Same native-side pattern as `.showMiroSheet`.
    static let showSessionsSwitcher = Notification.Name("showSessionsSwitcher")
}

/// The Sessions-lens toolbar button — presents the session-switcher popover.
///
/// Replaces the `toggleLeftPanel` dispatch on this one lens (the other three
/// lenses keep their web-panel toggle). Carries its OWN accessible name:
/// the shared label resolved to "Sessions" via `common.nav.sessions`, so
/// VoiceOver said "Sessions, button" while sitting on the Sessions lens —
/// no information at all (review finding 28).
struct SessionsSwitcherButton: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var i18n: I18n

    @StateObject private var model = SessionsPopoverModel()
    @State private var isPresented = false

    var body: some View {
        Button {
            present()
        } label: {
            Label(i18n.t("desktop.toolbar.switchSession"), systemImage: "list.bullet")
        }
        .help(i18n.t("desktop.toolbar.switchSession"))
        .popover(isPresented: $isPresented, arrowEdge: .bottom) {
            SessionsPopoverContent(
                model: model,
                i18n: i18n,
                activeSessionID: activeSessionID,
                onAllSessions: {
                    // Plain switchToTab, deliberately NOT activateLens — All
                    // Sessions must reach the grid; the route memory would
                    // bounce an activateLens straight back to the transcript.
                    bridgeHandler.switchToTab(.sessions)
                    isPresented = false
                },
                onCommit: { session in
                    bridgeHandler.navigateToSession(session.sessionID)
                },
                onDismiss: { isPresented = false },
                onRetry: { refresh() }
            )
        }
        .onReceive(NotificationCenter.default.publisher(for: .showSessionsSwitcher)) { _ in
            if !isPresented { present() }
        }
    }

    private func present() {
        isPresented = true
        refresh()   // the decided refresh trigger: every open re-fetches
    }

    private func refresh() {
        // Identity is read through the provider at request-build time and
        // re-read after the await, inside SessionsAPI.load — never snapshot
        // port/token here (the parked-sidecar wrong-project class).
        let manager = serveManager
        Task {
            await model.refresh { [weak manager] in
                guard let manager,
                      let port = manager.runningPort,
                      let token = manager.authToken else { return nil }
                return (port: port, token: token)
            }
        }
    }

    private var activeSessionID: String? {
        if case .session(let id) = SessionsRouteMemory.sessionsRoute(fromPath: bridgeHandler.currentPath) {
            return id
        }
        return nil
    }
}

// MARK: - Action row

/// The All Sessions row — `ExportPopoverRow`'s visual language (same metrics:
/// 12/6 padding inside a 6pt inset, 10pt gap, 6pt radius, hand-rolled hover)
/// without reaching into `ContentView.swift`'s private type.
private struct SessionsPopoverActionRow: View {
    let systemImage: String
    let title: String
    let subtitle: String?
    let action: () -> Void

    @State private var hovered = false

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: systemImage)
                    .font(.body)
                    .foregroundStyle(.tint)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                    if let subtitle {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .background(hovered ? Color.primary.opacity(0.06) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .onHover { hovered = $0 }
        .padding(.horizontal, 6)
    }
}
