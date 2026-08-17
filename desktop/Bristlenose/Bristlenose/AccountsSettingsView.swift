import SwiftUI

// Settings ▸ Accounts — where a cloud sign-in is seen and removed.
//
// §9 puts account lifecycle here rather than in the import window: "One place to
// disconnect, not two." What exists today is the *disconnect* half. Sign-in
// still happens in the import window, and the scope disclosure §10 owes is not
// written — so this pane is deliberately a list and a button rather than the
// Mail Accounts sidebar-and-detail the design names. **That shape is right when
// there is a detail worth showing**; with one row per platform, a fixed set of
// three, and a single verb, a sidebar would be chrome around nothing. It grows
// into the full pattern when sign-in and the disclosure move here.
//
// **Why this exists at all, beyond tidiness:** the privacy policy has to say
// what happens to a stored sign-in, and the honest sentence — "signing out
// removes it" — was a promise with nothing behind it. Revocation at the
// provider was the only true answer, and it is not one a researcher thinks to
// go looking for.
//
// English-only, like the rest of the cloud-import surface (§10 records that as
// realised i18n debt for the whole feature, not an oversight here). The copy
// wants settling before 21 locales are asked to carry it.

struct AccountsSettingsView: View {
    @EnvironmentObject private var i18n: I18n

    @State private var connections: [CloudGrantStore.Connection] = []
    /// The platform awaiting confirmation, if any. Held rather than passed so
    /// the alert survives the list reloading underneath it.
    @State private var pendingDisconnect: CloudPlatform?

    var body: some View {
        Form {
            Section {
                if connections.isEmpty {
                    emptyState
                } else {
                    ForEach(connections) { connection in
                        row(connection)
                    }
                }
            } header: {
                Text("Meeting accounts")
            } footer: {
                Text("Connect an account from File ▸ Import to bring recordings "
                     + "in without downloading them by hand.")
                .font(.callout)
                .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onAppear(perform: reload)
        // The sign-in happens in another window, so this pane can be on screen
        // while the set changes underneath it.
        .onReceive(NotificationCenter.default.publisher(
            for: .bristlenoseCloudAccountDisconnected)) { _ in reload() }
        .alert(
            "Disconnect \(pendingDisconnect?.displayName ?? "")?",
            isPresented: Binding(
                get: { pendingDisconnect != nil },
                set: { if !$0 { pendingDisconnect = nil } })
        ) {
            Button("Disconnect", role: .destructive) {
                if let platform = pendingDisconnect { disconnect(platform) }
                pendingDisconnect = nil
            }
            Button("Cancel", role: .cancel) { pendingDisconnect = nil }
        } message: {
            // Says what it does AND what it does not do. Removing our copy is
            // not revocation, and a researcher who believes it is would stop
            // one step short of the thing that actually protects a client.
            Text("Bristlenose will forget this sign-in and stop listing your "
                 + "recordings. Recordings you've already imported stay in your "
                 + "projects.\n\nThis doesn't revoke Bristlenose's access at the "
                 + "provider — do that in your account settings there.")
        }
    }

    private var emptyState: some View {
        // Absence is information: no accounts is the ordinary state for most
        // installs, and it earns a sentence rather than an empty box.
        Text("No accounts connected.")
            .foregroundStyle(.secondary)
    }

    private func row(_ connection: CloudGrantStore.Connection) -> some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 1) {
                Text(connection.platform.displayName)
                if let address = connection.address {
                    Text(address)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                } else {
                    // A grant whose identity never arrived. Still real, still
                    // removable — say so plainly rather than showing a blank.
                    Text("Signed in")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button("Disconnect…") { pendingDisconnect = connection.platform }
        }
    }

    private func reload() {
        connections = CloudGrantStore.connections()
    }

    private func disconnect(_ platform: CloudPlatform) {
        CloudGrantStore.disconnect(platform)
        reload()
    }
}
