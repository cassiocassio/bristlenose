import Foundation
import OSLog

/// Miro's half of Settings ▸ Accounts.
///
/// Miro is the odd one in the catalogue and this type is where the oddness is
/// contained. The meeting platforms are an OAuth round trip whose tokens and
/// identity Swift owns end to end; Miro's is a token the researcher pastes into
/// the export sheet, validated and used by the **Python** side, with Swift
/// keeping a durable copy in the Keychain so a sidecar restart does not lose it
/// (`docs/design-miro-bridge.md`, "macOS native entry").
///
/// Two consequences the pane has to live with:
///
/// **The identity is not knowable at rest.** User, team and org come from
/// `MiroAPI.Connection`, which is an HTTP call through a running sidecar to
/// Miro — and Settings can be open with no serve running at all. So the sheet
/// caches the display line where it already has it, and the pane reads the
/// cache. Display strings only, never the token: those are a name and an
/// organisation, not a credential, which is why `UserDefaults` is the right
/// home for them and the Keychain is the right home for the other thing.
///
/// **Disconnecting has two halves, like the cloud accounts.** The durable copy
/// is the Keychain item, but a *running* sidecar also holds
/// `app.state.miro_session_token` in memory — so removing only the Keychain
/// copy leaves a serve that keeps exporting to a board the researcher believes
/// they disconnected from. With no serve running there is nothing to clear and
/// the Keychain delete is the whole job.
enum MiroConnectionStore {

    /// The same provider key `MiroSheet` and `credentials_macos.py` use. Not
    /// per-account: one Miro token, keyed as it always has been.
    static let provider = "miro"

    private static let identityDefaultsKey = "miroConnectionIdentity"
    private static let log = Logger(subsystem: "app.bristlenose", category: "miro")

    /// Whether a token is stored.
    ///
    /// Reads item *attributes*, not the item — existence is the question, and
    /// answering it should not decrypt a credential.
    static func isConnected(store: any KeychainStore = KeychainHelper.liveStore) -> Bool {
        !store.accounts(provider: provider).isEmpty
    }

    /// The cached display line, or nil if one was never resolved.
    static var identity: String? {
        UserDefaults.standard.string(forKey: identityDefaultsKey)
    }

    /// Cache what the sheet just learnt, so the pane can name the account
    /// without a call of its own.
    static func remember(_ connection: MiroAPI.Connection) {
        guard connection.connected, let line = displayLine(connection) else { return }
        UserDefaults.standard.set(line, forKey: identityDefaultsKey)
    }

    static func forgetIdentity() {
        UserDefaults.standard.removeObject(forKey: identityDefaultsKey)
    }

    /// `userName · orgName`, falling back to the team when there is no
    /// organisation — `orgName` is Enterprise-only, so it is nil on the
    /// ordinary account. Nil when Miro gave us nothing, in which case the row
    /// shows the service name alone: "Connected" as a second line says only
    /// what the row's presence already says.
    static func displayLine(_ connection: MiroAPI.Connection) -> String? {
        let parts = [connection.userName, connection.orgName ?? connection.teamName]
            .compactMap { $0 }
            .filter { !$0.isEmpty }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    /// Convenience for callers holding a `ServeManager` rather than a client.
    static func disconnect(servePort: Int?,
                           authToken: String?,
                           store: any KeychainStore = KeychainHelper.liveStore) async {
        await disconnect(api: servePort.map { MiroAPI(port: $0, token: authToken) },
                         store: store)
    }

    /// Forget the token — every copy. The whole sequence, and the only copy of it.
    ///
    /// The running serve first, then the durable copy, matching the order the
    /// export sheet already used. `MiroAPI.disconnect` swallows its own
    /// failures by design (it logs, and the local copy goes regardless), so a
    /// sidecar that has already gone away cannot strand the Keychain item.
    ///
    /// The Send-to-Miro sheet had its own three-step version until 18 Aug 2026
    /// — API, Keychain, identity — missing only the notification below, which
    /// is the step that makes the other three true. Disconnecting from the
    /// sheet therefore left the running sidecar exporting happily to the board
    /// the researcher had just been told they were disconnected from. Two
    /// surfaces performing one irreversible act must not be two sequences.
    static func disconnect(api: MiroAPI?,
                           store: any KeychainStore = KeychainHelper.liveStore) async {
        if let api {
            await api.disconnect()
        } else {
            // Nothing in memory to clear: the next sidecar reads the Keychain,
            // which is about to be empty.
            log.info("miro disconnect with no serve running — Keychain copy is the whole job")
        }
        store.delete(provider: provider, account: KeychainHelper.account)
        forgetIdentity()

        // **Clearing the Keychain and the fronted session is still not enough.**
        // `overlayMiroToken` injects `BRISTLENOSE_MIRO_ACCESS_TOKEN` into every
        // sidecar at spawn, and the server resolves the credential store *first*
        // — which falls through to that env var. So a serve started while the
        // token existed keeps a working copy no HTTP call can unset, and the
        // parked sidecar `ServeManager` holds keeps one too. Until both are
        // respawned the pane's confirmation — "stop sending quotes to your
        // boards" — is simply untrue.
        //
        // `.bristlenosePrefsChanged` is the existing mechanism for exactly this
        // ("the sidecar's baked env is stale"): it drains the parked slot and
        // restarts the fronted serve. The restart cost is the usual one, and it
        // is the right trade here — a deliberate, rare act. It also rotates the
        // kernel-assigned port, so a caller holding a `MiroAPI` built from the
        // old one must not keep using it: the sheet dismisses itself for this
        // reason.
        NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
    }
}
