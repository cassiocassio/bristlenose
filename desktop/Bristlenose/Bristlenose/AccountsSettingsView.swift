import SwiftUI

// Settings ▸ Accounts — the four things Bristlenose talks to, and what state
// each is in.
//
// §9 puts account lifecycle here: "One place to disconnect, not two." A section
// per service rather than one list of connected accounts, because with a fixed
// catalogue of four the question "what can this thing talk to?" is worth
// answering as plainly as "what have I connected?" — and a permanent
// Not-connected row answers it without a modal to open.
//
// **The pane makes no network calls.** Every state comes off disk; see
// `AccountsSectionModel` for why, and for which state is still owed a writer.
//
// **Connecting still happens at the point of intent.** Connect… opens the
// import window, where sign-in already lives — one flow, one implementation,
// and the researcher lands where the thing they wanted actually happens rather
// than back in Settings holding a token. Miro is the exception and says so: its
// connect is a pasted token inside the export sheet, which needs a running
// serve and an open project.
//
// English-only, like the rest of the cloud-import surface (§10 records that as
// realised i18n debt for the whole feature, not an oversight here). The copy
// wants settling before 21 locales are asked to carry it.

struct AccountsSettingsView: View {
    @ObservedObject var serveManager: ServeManager
    @EnvironmentObject private var i18n: I18n

    @State private var sections: [AccountSection] = []
    /// The section awaiting confirmation, if any. Held rather than passed so
    /// the alert survives the list reloading underneath it.
    @State private var pendingDisconnect: AccountSection?

    var body: some View {
        Form {
            ForEach(sections) { section in
                Section {
                    row(section)
                } header: {
                    Label(section.service.displayName, systemImage: section.service.symbolName)
                } footer: {
                    Text(section.service.purpose)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onAppear(perform: reload)
        // Sign-in happens in another window and disconnect can come from the
        // export sheet, so this pane can be on screen while the set changes
        // underneath it.
        .onReceive(NotificationCenter.default.publisher(
            for: .bristlenoseCloudAccountDisconnected)) { _ in reload() }
        .alert(
            "Disconnect \(pendingDisconnect?.service.displayName ?? "")?",
            isPresented: Binding(
                get: { pendingDisconnect != nil },
                set: { if !$0 { pendingDisconnect = nil } })
        ) {
            Button("Disconnect", role: .destructive) {
                if let section = pendingDisconnect { disconnect(section) }
                pendingDisconnect = nil
            }
            Button("Cancel", role: .cancel) { pendingDisconnect = nil }
        } message: {
            // Says what it does AND what it does not do. Removing our copy is
            // not revocation, and a researcher who believes it is would stop
            // one step short of the thing that actually protects a client.
            Text(disconnectWarning(for: pendingDisconnect))
        }
    }

    // MARK: - The row, one shape per state

    @ViewBuilder
    private func row(_ section: AccountSection) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(headline(section.state))
                if let detail = detail(section) {
                    Text(detail)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 12)
            action(section)
        }
        // Unavailable is not a failure and not the researcher's doing, so it
        // recedes rather than shouting.
        .opacity(section.state == .unavailable ? 0.55 : 1)
    }

    private func headline(_ state: AccountSectionState) -> String {
        switch state {
        case .unavailable:  return "Not available yet"
        case .notConnected: return "Not connected"
        // The address is the headline once there is one — with a service name
        // already in the header above, repeating it here would say nothing.
        case .connected(let identity):    return identity ?? "Connected"
        case .attention(let identity, _): return identity ?? "Connected"
        }
    }

    private func detail(_ section: AccountSection) -> String? {
        switch section.state {
        case .unavailable:
            return "Bristlenose can't sign in to \(section.service.displayName) yet."
        case .notConnected:
            return section.service.connectsFromHere
                ? nil
                : "Connect Miro from Send to Miro, in a project's Export menu."
        case .connected:
            return nil
        case .attention(_, let attention):
            return attention.sentence
        }
    }

    @ViewBuilder
    private func action(_ section: AccountSection) -> some View {
        switch section.state {
        case .unavailable:
            // No verb, deliberately: there is nothing the researcher can do,
            // and a disabled button would imply there is.
            EmptyView()
        case .notConnected:
            if section.service.connectsFromHere {
                Button("Connect…") { connect(section.service) }
            }
        case .connected, .attention:
            Button("Disconnect…") { pendingDisconnect = section }
        }
    }

    // MARK: - Doing things

    private func reload() {
        sections = AccountsSectionModel.sections(
            available: availablePlatforms(),
            connections: CloudGrantStore.connections(),
            miroConnected: MiroConnectionStore.isConnected(),
            miroIdentity: MiroConnectionStore.identity)
    }

    /// A platform is connectable when this build carries an OAuth client for it
    /// and it is not parked. `CloudPlatform.offered` already owns the parking
    /// half; the config resolvers own the other.
    private func availablePlatforms() -> Set<CloudPlatform> {
        Set(CloudPlatform.offered(zoomEnabled: BristlenoseFlags.cloudImportZoom).filter { platform in
            switch platform {
            case .teams: return MicrosoftOAuthConfig.resolve() != nil
            case .meet:  return GoogleOAuthConfig.resolve() != nil
            case .zoom:  return ZoomOAuthConfig.resolve() != nil
            }
        })
    }

    private func connect(_ service: AccountService) {
        guard case .cloud(let platform) = service else { return }
        // The same door the File menu uses, so there is one way in and one
        // sign-in flow to keep working.
        NotificationCenter.default.post(name: .openCloudImport, object: platform)
    }

    private func disconnect(_ section: AccountSection) {
        switch section.service {
        case .cloud(let platform):
            guard let accountKey = section.accountKey else { return }
            CloudGrantStore.disconnect(platform, accountKey: accountKey)
            reload()
        case .miro:
            Task {
                await MiroConnectionStore.disconnect(servePort: serveManager.runningPort,
                                                     authToken: serveManager.authToken)
                reload()
            }
        }
    }

    private func disconnectWarning(for section: AccountSection?) -> String {
        let revocation = "\n\nThis doesn't revoke Bristlenose's access at the provider — "
            + "do that in your account settings there."
        switch section?.service {
        case .miro:
            return "Bristlenose will forget this token and stop sending quotes to your boards. "
                + "Boards you've already created stay in Miro." + revocation
        default:
            return "Bristlenose will forget this sign-in and stop listing your recordings. "
                + "Recordings you've already imported stay in your projects." + revocation
        }
    }
}
