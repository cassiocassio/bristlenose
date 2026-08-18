import SwiftUI

// Settings ▸ Accounts — the four things Bristlenose talks to, and what state
// each is in.
//
// §9 puts account lifecycle here: "One place to disconnect, not two." A section
// per service rather than one list of connected accounts, because with a fixed
// catalogue the question "what have I connected?" and the question "what could
// I connect?" have the same answer shape — and a permanent Not-connected row
// answers the second without a modal to open. Services that cannot be connected
// at all are not listed; see `AccountService.all`.
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

    @State private var sections: [AccountSection]
    /// The section awaiting confirmation, if any. Held rather than passed so
    /// the alert survives the list reloading underneath it.
    @State private var pendingDisconnect: AccountSection?

    /// **Seeded here, not in `.onAppear`.** The Settings package sizes each
    /// pane to its `fittingSize` at the moment the pane is shown, and does not
    /// re-measure when the content grows underneath it. Filling the Form from
    /// `.onAppear` therefore measured an *empty* one: the window came up a
    /// single header tall and clipped the other three services below the frame,
    /// which reads as a broken pane rather than a short one. Everything the
    /// first render needs is on disk, so there is nothing to wait for.
    init(serveManager: ServeManager) {
        self.serveManager = serveManager
        _sections = State(initialValue: Self.currentSections())
    }

    var body: some View {
        Form {
            ForEach(sections) { section in
                // Header text only. No glyph — see `AccountService` — and no
                // footer: the line under each row explained what the service is
                // for, which is a question the researcher settled before they
                // came here, and four permanent sales lines under four state
                // rows is what the row was competing with.
                Section(section.service.displayName) {
                    row(section)
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
        // **Re-read whenever the window is looked at.** `.onAppear` fires on
        // entering the hierarchy, not on regaining key — so the pane's own
        // primary action (Connect… → sign in → come back) left a row still
        // reading "Not connected", inviting the researcher to click it again.
        // Keying on the window rather than adding a connected-side notification
        // costs no new protocol and covers every writer for free, including the
        // Miro export sheet, which posts nothing at all.
        .onReceive(NotificationCenter.default.publisher(
            for: NSWindow.didBecomeKeyNotification)) { _ in reload() }
        // `presenting:` rather than a bare `isPresented:` — the closures get a
        // non-optional section that survives the dismissal animation, so the
        // title cannot flash "Disconnect ?" on the way out and the message has
        // no nil branch to fall down (which rendered the *cloud* copy for Miro).
        .alert(
            // The address when there is one: with two accounts on a platform
            // the service name alone does not say which is about to go.
            "Disconnect \(pendingDisconnect?.state.identity ?? pendingDisconnect?.service.displayName ?? "")?",
            isPresented: Binding(
                get: { pendingDisconnect != nil },
                set: { if !$0 { pendingDisconnect = nil } }),
            presenting: pendingDisconnect
        ) { section in
            // **No `role: .destructive`.** The researcher clicked Disconnect…;
            // this button performs their original intent, and Apple reserves
            // the destructive style for actions people did *not* deliberately
            // choose — Empty Trash is their own counter-example. Dropping it
            // also restores Return-to-confirm.
            Button("Disconnect") {
                disconnect(section)
                pendingDisconnect = nil
            }
            Button("Cancel", role: .cancel) { pendingDisconnect = nil }
        } message: { section in
            // Says what it does AND what it does not do. Removing our copy is
            // not revocation, and a researcher who believes it is would stop
            // one step short of the thing that actually protects a client.
            Text(disconnectWarning(for: section))
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
        // recedes — via the hierarchical style, never `.opacity`. A manual alpha
        // compounds with the detail line's own `.secondary` (landing near 0.28
        // effective, under the 4.5:1 floor) and, worse, does not respond to
        // Increase Contrast. The system styles carry accessible variants; a
        // hardcoded number cannot.
        .foregroundStyle(isUnavailable(section) ? AnyShapeStyle(.tertiary)
                                                : AnyShapeStyle(.primary))
    }

    private func isUnavailable(_ section: AccountSection) -> Bool {
        if case .unavailable = section.state { return true }
        return false
    }

    private func headline(_ state: AccountSectionState) -> String {
        switch state {
        // No "yet" — user-facing text makes no promises, and a roadmap is not
        // this row's job.
        case .unavailable(let stranded): return stranded ?? "Not available"
        case .notConnected: return "Not connected"
        // The address is the headline once there is one — with a service name
        // already in the header above, repeating it here would say nothing.
        case .connected(let identity):    return identity ?? "Connected"
        case .attention(let identity, _): return identity ?? "Connected"
        }
    }

    private func detail(_ section: AccountSection) -> String? {
        switch section.state {
        case .unavailable(let stranded):
            // A stranded grant gets the fuller sentence: otherwise the row reads
            // as "nothing is stored here", which is the reading that would leave
            // a client's credential on disk untouched.
            return stranded == nil
                ? "Bristlenose can't sign in to \(section.service.displayName)."
                : "Bristlenose can't sign in to \(section.service.displayName) in this "
                  + "build, but this sign-in is still stored."
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
            // No way to connect — nothing the researcher can do about a missing
            // client id, and a disabled Connect would imply there is. But a
            // grant stored here must still be removable, or a client's
            // credential sits on disk with no UI anywhere that can reach it.
            if section.accountKey != nil {
                disconnectButton(section)
            }
        case .notConnected:
            if section.service.connectsFromHere {
                Button("Connect…") { connect(section.service) }
                    .accessibilityLabel("Connect \(section.service.displayName)")
            }
        case .connected:
            disconnectButton(section)
        case .attention(_, let attention):
            // Disconnect stays available on a row that says something is wrong
            // — that is exactly the row a researcher wants rid of — with the
            // recovery trailing it, where the default action belongs.
            disconnectButton(section)
            if attention.isRecoverable, section.service.connectsFromHere {
                Button("Sign In…") { connect(section.service) }
                    .accessibilityLabel("Sign in to \(section.service.displayName)")
            }
        }
    }

    /// The service name rides the accessibility label, not the visible title.
    /// Sighted readers take it from the section header; the VoiceOver rotor and
    /// Voice Control do not, and four identical "Disconnect…" entries in a list
    /// of buttons is unusable.
    private func disconnectButton(_ section: AccountSection) -> some View {
        Button("Disconnect…") { pendingDisconnect = section }
            .accessibilityLabel("Disconnect \(section.service.displayName)")
    }

    // MARK: - Doing things

    private func reload() {
        sections = Self.currentSections()
    }

    /// Everything the pane shows, read off disk. `static` so `init` can call it
    /// before `self` exists.
    private static func currentSections() -> [AccountSection] {
        AccountsSectionModel.sections(
            available: availablePlatforms(),
            connections: CloudGrantStore.connections(),
            miroConnected: MiroConnectionStore.isConnected(),
            miroIdentity: MiroConnectionStore.identity)
    }

    /// A platform is connectable when this build carries an OAuth client for it
    /// and it is not parked. `CloudPlatform.offered` already owns the parking
    /// half; the config resolvers own the other.
    private static func availablePlatforms() -> Set<CloudPlatform> {
        // `shipping`, not a re-derivation — its own doc-comment names "a
        // Settings ▸ Accounts pane" as the caller that should inherit the
        // parking rather than spelling it out a second time.
        Set(CloudPlatform.shipping.filter { platform in
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

    /// Non-optional and exhaustive over `AccountService` — the previous
    /// `default:` arm quietly rendered the *cloud* wording for a nil section,
    /// the shape that stops being unreachable the moment a fifth service lands.
    private func disconnectWarning(for section: AccountSection) -> String {
        let revocation = "\n\nThis doesn't revoke Bristlenose's access at the provider — "
            + "do that in your account settings there."
        switch section.service {
        case .miro:
            return "Bristlenose will forget this token and stop sending quotes to your boards. "
                + "Boards you've already created stay in Miro." + revocation
        case .cloud:
            return "Bristlenose will forget this sign-in and stop listing your recordings. "
                + "Recordings you've already imported stay in your projects." + revocation
        }
    }
}
