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
    let sessionCount: Int
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

    @EnvironmentObject private var i18n: I18n
    @Environment(\.dismiss) private var dismiss
    @State private var client: Client = .claudeDesktop
    @State private var anonymise = true
    @State private var copied = false

    enum Client: String, CaseIterable, Identifiable {
        case claudeDesktop, claudeCode, chatgptCodex
        var id: String { rawValue }

        @MainActor func label(_ i18n: I18n) -> String {
            switch self {
            case .claudeDesktop: return i18n.t("connectAgent.clients.claudeDesktop")
            case .claudeCode: return i18n.t("connectAgent.clients.claudeCode")
            case .chatgptCodex: return i18n.t("connectAgent.clients.chatgptCodex")
            }
        }

        @MainActor func how(_ i18n: I18n) -> String {
            switch self {
            case .claudeDesktop: return i18n.t("connectAgent.claudeDesktopHow")
            case .claudeCode: return i18n.t("connectAgent.claudeCodeHow")
            case .chatgptCodex: return i18n.t("connectAgent.chatgptCodexHow")
            }
        }

        /// Verb-named primary, per the client's dialect.
        @MainActor func actionTitle(_ i18n: I18n) -> String {
            switch self {
            case .claudeCode: return i18n.t("connectAgent.copyCommand")
            default: return i18n.t("connectAgent.copyConfig")
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

    private var scopeLine: String {
        let sessions = sessionCount == 1 ? "1 session" : "\(sessionCount) sessions"
        guard let quoteCount else { return sessions }
        let quotes = quoteCount == 1 ? "1 quote" : "\(quoteCount) quotes"
        return "\(sessions) · \(quotes)"
    }

    private var payloadText: String? {
        guard let endpoint, let token else { return nil }
        return client.payload(endpoint: endpoint, token: token)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(i18n.t("connectAgent.title", ["project": projectName]))
                .font(.system(size: 15, weight: .semibold))
            Text(scopeLine)
                .font(.system(size: 13))
                .foregroundStyle(.secondary)
                .padding(.top, 2)

            // The shipped Export-popover control, verbatim — one word for one
            // concept across Export, clips, Miro, and here.
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(i18n.t("connectAgent.anonymise"))
                        .font(.system(size: 13, weight: .semibold))
                    Text(i18n.t("connectAgent.anonymiseHint"))
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: $anonymise)
                    .toggleStyle(.switch)
                    .labelsHidden()
                    .accessibilityLabel(i18n.t("connectAgent.anonymise"))
            }
            .padding(.top, 14)

            Picker("", selection: $client) {
                ForEach(Client.allCases) { Text($0.label(i18n)).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.top, 14)

            payloadPane
                .padding(.top, 10)

            Text(i18n.t("connectAgent.clients.other"))
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .padding(.top, 8)

            HStack {
                Spacer()
                Button(i18n.t("connectAgent.cancel")) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(copied ? i18n.t("connectAgent.copied") : client.actionTitle(i18n)) {
                    copy()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(payloadText == nil)
            }
            .padding(.top, 16)
        }
        .padding(20)
        .frame(width: 560)
        .onChange(of: client) { copied = false }
    }

    /// Fixed-height so switching clients never reflows the sheet — sized to
    /// the tallest dialect (Claude Desktop's six-line JSON).
    @ViewBuilder
    private var payloadPane: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !mcpAvailable {
                Text(i18n.t("connectAgent.unavailable"))
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            } else if let payloadText {
                Text(client.how(i18n))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(payloadText)
                    .font(.system(size: 11, design: .monospaced))
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
            } else {
                Text(i18n.t("connectAgent.notRunning"))
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .frame(height: 150, alignment: .topLeading)
    }

    private func copy() {
        guard let payloadText else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(payloadText, forType: .string)
        copied = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { copied = false }
    }
}
