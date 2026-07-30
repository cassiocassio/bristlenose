import AppKit
import SwiftUI

/// "Connect Agent…" — hands the researcher the two things any MCP agent needs
/// (the endpoint URL and an Authorization header) in that agent's own dialect.
///
/// Design: `docs/design-mcp-server.md` §6a, mocked and critiqued at
/// `docs/mockups/mcp-spike-ux-walkthrough.html`. Four things and nothing else:
/// the scope restated, the anonymisation control, the client dialects, and one
/// primary action. No wizard, no consent gradient — the alternative this
/// replaces is dragging a raw transcript into a chat window.
///
/// **Native primitives.** A sheet, because this is a committed task the
/// researcher opened deliberately (a popover would light-dismiss while they
/// alt-tab to paste). `Picker(.segmented)` for the client switch — the stock
/// control for a small, flat, mutually-exclusive set inside a sheet body.
/// The payload is a plain selectable `Text` in a bordered box rather than a
/// `TextEditor`: it is read-only, and an editable-looking field would invite
/// edits that do nothing.
///
/// **Geometry is fixed; content bends.** Every client renders into the same
/// frame — the header block never moves and the payload box never resizes as
/// tabs change, so switching clients doesn't make the sheet jump.
struct ConnectAgentSheet: View {

    let projectName: String
    /// Nil when the host doesn't know yet (watcher hasn't published, DB
    /// unreadable) — the scope line omits what it doesn't know rather than
    /// asserting "0 sessions" in a grant sheet.
    let sessionCount: Int?
    /// Nil when the count isn't known to the host (the sidebar's snapshot
    /// carries sessions, not quotes) — the scope line then names sessions only
    /// rather than inventing a number.
    let quoteCount: Int?
    /// Endpoint the sidecar is serving, e.g. `http://127.0.0.1:8150/mcp/`.
    /// Nil when the project isn't running — the sheet says so rather than
    /// handing out a dead address.
    let endpoint: String?
    let token: String?
    /// False when the sidecar was built without the `mcp` extra.
    let mcpAvailable: Bool
    /// Fired after a successful copy — the host uses it to poll agent
    /// activity immediately, so the badge can light while the researcher
    /// is still watching for it instead of on the next 20s tick.
    var onCopied: (() -> Void)? = nil

    @EnvironmentObject private var i18n: I18n
    @Environment(\.dismiss) private var dismiss
    @State private var client: Client = .claudeDesktop
    @State private var copied = false
    /// Cancellable so a re-copy restarts the "Copied" interval instead of
    /// the first timer cutting the second confirmation short.
    @State private var copiedResetTask: Task<Void, Never>?

    enum Client: String, CaseIterable, Identifiable {
        case claudeDesktop, claudeCode, chatgptCodex
        var id: String { rawValue }

        @MainActor func label(_ i18n: I18n) -> String {
            switch self {
            case .claudeDesktop: return i18n.t("desktop.connectAgent.clients.claudeDesktop")
            case .claudeCode: return i18n.t("desktop.connectAgent.clients.claudeCode")
            case .chatgptCodex: return i18n.t("desktop.connectAgent.clients.chatgptCodex")
            }
        }

        @MainActor func how(_ i18n: I18n) -> String {
            switch self {
            case .claudeDesktop: return i18n.t("desktop.connectAgent.claudeDesktopHow")
            case .claudeCode: return i18n.t("desktop.connectAgent.claudeCodeHow")
            case .chatgptCodex: return i18n.t("desktop.connectAgent.chatgptCodexHow")
            }
        }

        /// Verb-named primary, per the client's dialect.
        @MainActor func actionTitle(_ i18n: I18n) -> String {
            switch self {
            case .claudeCode: return i18n.t("desktop.connectAgent.copyCommand")
            default: return i18n.t("desktop.connectAgent.copyConfig")
            }
        }

        /// The two primitives, written the way this client writes them down.
        /// Verified 30 Jul 2026 against the installed `claude` CLI and
        /// learn.chatgpt.com; dialects rot, so the canonical copies live in
        /// the manual (bristlenose.app/docs/connect-an-agent.html) too.
        func payload(endpoint: String, token: String) -> String {
            switch self {
            case .claudeDesktop:
                return """
                "bristlenose": {
                  "url": "\(endpoint)",
                  "headers": {
                    "Authorization": "Bearer \(token)"
                  }
                }
                """
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
            }
        }
    }

    /// Nil when neither count is known — the header then carries the
    /// project name alone rather than an empty grey line.
    private var scopeLine: String? {
        let parts = [
            sessionCount.map { i18n.plural("desktop.connectAgent.sessions", count: $0) },
            quoteCount.map { i18n.plural("desktop.connectAgent.quotes", count: $0) },
        ].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private var payloadText: String? {
        guard let endpoint, let token else { return nil }
        return client.payload(endpoint: endpoint, token: token)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(i18n.t("desktop.connectAgent.title", ["project": projectName]))
                .font(.title3.weight(.semibold))
            if let scopeLine {
                Text(scopeLine)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .padding(.top, 2)
            }

            // A statement, not a switch: the server anonymises always (it
            // never reads the persons table) and there is no opt-in path,
            // so a live toggle here would promise a choice the system
            // cannot make — in the unsafe direction. When a real
            // per-connection names opt-in exists server-side, this row is
            // where its control returns.
            VStack(alignment: .leading, spacing: 1) {
                Text(i18n.t("desktop.connectAgent.namesNote"))
                    .font(.body.weight(.medium))
                Text(i18n.t("desktop.connectAgent.namesNoteHint"))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding(.top, 14)

            Picker("", selection: $client) {
                ForEach(Client.allCases) { Text($0.label(i18n)).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .accessibilityLabel(i18n.t("desktop.connectAgent.clientPicker"))
            .padding(.top, 14)

            payloadPane
                .padding(.top, 10)

            Text(i18n.t("desktop.connectAgent.clients.other"))
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .padding(.top, 8)

            HStack {
                Spacer()
                if payloadText == nil {
                    // Informational states: one enabled default that
                    // dismisses — a sheet with only a message must answer
                    // Return.
                    Button(i18n.t("desktop.connectAgent.ok")) { dismiss() }
                        .keyboardShortcut(.defaultAction)
                } else {
                    Button(i18n.t("desktop.connectAgent.cancel")) { dismiss() }
                        .keyboardShortcut(.cancelAction)
                    Button(action: copy) {
                        // Both labels laid out, one visible — the button
                        // keeps the wider width so "Copied" never shoves
                        // Cancel sideways (geometry is fixed).
                        ZStack {
                            Text(client.actionTitle(i18n)).opacity(copied ? 0 : 1)
                            Text(i18n.t("desktop.connectAgent.copied")).opacity(copied ? 1 : 0)
                        }
                    }
                    .keyboardShortcut(.defaultAction)
                }
            }
            .padding(.top, 16)
        }
        .padding(20)
        .frame(width: 560)
        .onChange(of: client) {
            copiedResetTask?.cancel()
            copied = false
        }
    }

    /// Fixed-height so switching clients never reflows the sheet — sized to
    /// the tallest dialect (Claude Desktop's six-line JSON) plus a wrapped
    /// three-line how-to (translations run 25-35% longer than English).
    ///
    /// Branch order is load-bearing: `mcpAvailable` can only be trusted once
    /// a serve for THIS project has reported, so "start the project" must
    /// speak before any claim about what the build lacks — a cold-launched
    /// app must never tell the researcher their installation is broken.
    @ViewBuilder
    private var payloadPane: some View {
        VStack(alignment: .leading, spacing: 6) {
            if endpoint == nil {
                // Can't claim anything about the build before this
                // project's serve has reported — the one honest sentence
                // is the one that names the fixing action.
                Text(i18n.t("desktop.connectAgent.notRunning"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else if !mcpAvailable {
                Text(i18n.t("desktop.connectAgent.unavailable"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else if let payloadText {
                Text(client.how(i18n))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
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
                // The token is durable; the port is not (kernel-assigned
                // per launch). Saying so here beats a mystery 401-shaped
                // failure in the agent tomorrow.
                Text(i18n.t("desktop.connectAgent.addressNote"))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                // endpoint known but the token line hasn't arrived yet —
                // transient startup state; the same sentence fits.
                Text(i18n.t("desktop.connectAgent.notRunning"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .frame(height: 170, alignment: .topLeading)
    }

    private func copy() {
        guard let payloadText else { return }
        let pb = NSPasteboard.general
        // The payload carries a bearer token: keep it off Universal
        // Clipboard and mark it concealed so clipboard-history managers
        // (Maccy, Raycast, Alfred) skip it — the same declaration Keychain
        // Access and 1Password make.
        pb.prepareForNewContents(with: .currentHostOnly)
        let item = NSPasteboardItem()
        item.setString(payloadText, forType: .string)
        item.setString("", forType: NSPasteboard.PasteboardType("org.nspasteboard.ConcealedType"))
        pb.writeObjects([item])
        copied = true
        onCopied?()
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
