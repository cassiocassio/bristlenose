import Testing
import Foundation
@testable import Bristlenose

/// The rule that keeps a provider key's two copies agreeing — the app's synced
/// copy and the login-keychain copy the CLI reads. In-memory keychains only: the
/// rule under test decides *when a real read would raise a dialog*, which is
/// exactly what a test must never do on a developer's machine, so the fakes
/// count dialogs and the tests assert the count. The first live run of this
/// suite proved the point the other way: the host app read a CLI-written key at
/// launch, the dialog came up, and the runner hung for six minutes.
@Suite("SharedKeychainItem")
struct SharedKeychainItemTests {

    private let service = "Bristlenose Google Gemini API Key"
    private let account = "bristlenose"

    /// A clock both fakes share, advanced by hand so "newer" is decidable and
    /// "same second" is reachable.
    private final class Clock {
        var now = Date(timeIntervalSince1970: 1_700_000_000)
        func tick(_ seconds: TimeInterval = 10) { now = now.addingTimeInterval(seconds) }
    }

    private struct World {
        let synced: InMemoryRawKeychain
        let login: InMemoryRawKeychain
        let clock: Clock
        let defaults: UserDefaults
    }

    private func withWorld(_ body: (World) -> Void) {
        let name = "SharedKeychainItemTests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defer { defaults.removePersistentDomain(forName: name) }
        let clock = Clock()
        let synced = InMemoryRawKeychain()
        synced.now = { clock.now }
        let login = InMemoryRawKeychain()
        login.now = { clock.now }
        body(World(synced: synced, login: login, clock: clock, defaults: defaults))
    }

    /// The default: what a spawn path or a launch-time model does.
    private func quietRead(_ w: World) -> String? {
        SharedKeychainItem.read(service: service, account: account,
                                synced: w.synced, login: w.login,
                                interaction: .quiet, defaults: w.defaults)
    }

    /// What Settings ▸ LLM Provider does.
    private func askingRead(_ w: World) -> String? {
        SharedKeychainItem.read(service: service, account: account,
                                synced: w.synced, login: w.login,
                                interaction: .allowed, defaults: w.defaults)
    }

    @discardableResult
    private func write(_ w: World, _ value: String) -> Bool {
        SharedKeychainItem.write(service: service, account: account, value: value,
                                 synced: w.synced, login: w.login, defaults: w.defaults)
    }

    /// The app on another Mac wrote the synced copy — ours, never a dialog.
    private func plantSynced(_ w: World, _ value: String) {
        w.synced.plant(service: service, account: account, value: value, at: w.clock.now, foreign: false)
    }

    /// `bristlenose configure` wrote the login copy — another tool's item.
    private func plantLogin(_ w: World, _ value: String) {
        w.login.plant(service: service, account: account, value: value, at: w.clock.now, foreign: true)
    }

    private func loginValue(_ w: World) -> String? {
        w.login.read(service: service, account: account, interaction: .allowed).value
    }

    private func syncedValue(_ w: World) -> String? {
        w.synced.read(service: service, account: account, interaction: .allowed).value
    }

    // MARK: - Nothing may ask at launch

    /// Whatever the keychains hold, a quiet read shows no dialog. This is the
    /// test the hung runner was missing.
    @Test func quietReads_neverRaiseADialog() {
        withWorld { w in
            plantLogin(w, "sk-cli")
            _ = quietRead(w)
            #expect(w.login.prompts == 0)
        }
        withWorld { w in
            write(w, "sk-old")
            w.clock.tick()
            plantLogin(w, "sk-newer-cli")
            _ = quietRead(w)
            #expect(w.login.prompts == 0)
        }
        withWorld { w in
            plantLogin(w, "sk-stale-cli")
            w.clock.tick()
            plantSynced(w, "sk-app")
            _ = quietRead(w)
            #expect(w.login.prompts == 0)
        }
    }

    // MARK: - One copy exists

    @Test func nothingAnywhere_readsNil_andDecryptsNothing() {
        withWorld { w in
            #expect(quietRead(w) == nil)
            #expect(w.synced.reads == 0)
            #expect(w.login.reads == 0)
        }
    }

    /// Set up in the app → the CLI sees it. The synced copy is the only one, so
    /// the login copy is made from it on the first read — quietly, since the
    /// item written is the app's own.
    @Test func appOnlyKey_isCopiedToTheLoginKeychain() {
        withWorld { w in
            plantSynced(w, "sk-app")
            #expect(quietRead(w) == "sk-app")
            #expect(loginValue(w) == "sk-app")
            #expect(w.login.prompts == 0)
        }
    }

    /// Set up in the CLI → a quiet read must not adopt it, because adopting is
    /// the dialog. It reports nothing, records nothing, and asks nothing.
    @Test func cliOnlyKey_quietRead_doesNotAsk_andReturnsNothing() {
        withWorld { w in
            plantLogin(w, "sk-cli")
            #expect(quietRead(w) == nil)
            #expect(w.login.prompts == 0)
            #expect(syncedValue(w) == nil)
        }
    }

    /// Set up in the CLI → Settings adopts it: one dialog, the synced copy is
    /// made, and every later quiet read serves it without asking.
    @Test func cliOnlyKey_askingRead_adoptsItOnce() {
        withWorld { w in
            plantLogin(w, "sk-cli")
            #expect(askingRead(w) == "sk-cli")
            #expect(syncedValue(w) == "sk-cli")
            #expect(w.login.prompts == 1)
            #expect(quietRead(w) == "sk-cli")
            #expect(quietRead(w) == "sk-cli")
            #expect(w.login.prompts == 1)
        }
    }

    // MARK: - Steady state

    /// Once the copies agree, a read touches the app's own copy and nothing
    /// else: the login keychain is never decrypted again.
    @Test func unchangedCopies_neverDecryptTheLoginCopy() {
        withWorld { w in
            write(w, "sk-1")
            let decryptsAfterWrite = w.login.reads   // the write's own read-back
            #expect(quietRead(w) == "sk-1")
            #expect(quietRead(w) == "sk-1")
            #expect(askingRead(w) == "sk-1")
            #expect(w.login.reads == decryptsAfterWrite)
            #expect(w.synced.reads > 0)
        }
    }

    // MARK: - One copy moved

    /// `bristlenose configure` after the app had a key. A quiet read keeps
    /// serving the app's copy without asking; the next asking read takes the
    /// CLI's newer one and updates the synced copy.
    @Test func cliRewrite_quietReadKeepsTheAppsCopy_askingReadAdopts() {
        withWorld { w in
            write(w, "sk-old")
            w.clock.tick()
            plantLogin(w, "sk-new")            // the CLI: delete + add
            #expect(quietRead(w) == "sk-old")
            #expect(syncedValue(w) == "sk-old")
            #expect(w.login.prompts == 0)

            #expect(askingRead(w) == "sk-new")
            #expect(syncedValue(w) == "sk-new")
            #expect(w.login.prompts == 1)
            #expect(quietRead(w) == "sk-new")
        }
    }

    /// The synced copy moved — this app on another Mac — and the login copy
    /// did not: the synced copy wins and the login copy is refreshed for the
    /// CLI, with no dialog, because the login copy is the app's own.
    @Test func syncedRewrite_refreshesTheLoginCopy() {
        withWorld { w in
            write(w, "sk-old")
            w.clock.tick()
            plantSynced(w, "sk-from-other-mac")
            #expect(quietRead(w) == "sk-from-other-mac")
            #expect(loginValue(w) == "sk-from-other-mac")
            #expect(w.login.prompts == 0)
        }
    }

    // MARK: - First sight of both

    /// Never reconciled, both present, both different — the maintainer's Mac on
    /// 4 Sep 2026: the newer copy wins, whichever side it is on.
    @Test func firstSight_theNewerCopyWins() {
        withWorld { w in
            plantSynced(w, "sk-app-stale")
            w.clock.tick()
            plantLogin(w, "sk-cli-today")
            #expect(askingRead(w) == "sk-cli-today")
            #expect(syncedValue(w) == "sk-cli-today")
        }
        withWorld { w in
            plantLogin(w, "sk-cli-stale")
            w.clock.tick()
            plantSynced(w, "sk-app-today")
            #expect(askingRead(w) == "sk-app-today")
            #expect(loginValue(w) == "sk-app-today")
        }
    }

    /// The same first sight from a spawn path: the app's copy serves, nothing
    /// is rewritten, nothing is asked, nothing is recorded — the asking read
    /// still gets to decide.
    @Test func firstSight_quietRead_defersTheDecision() {
        withWorld { w in
            plantSynced(w, "sk-app-stale")
            w.clock.tick()
            plantLogin(w, "sk-cli-today")
            #expect(quietRead(w) == "sk-app-stale")
            #expect(w.login.prompts == 0)
            #expect(w.synced.writes == 0)
            #expect(w.login.writes == 0)
            #expect(askingRead(w) == "sk-cli-today")
        }
    }

    /// Same second, different values: the app's own copy is the truth.
    @Test func firstSightTie_goesToTheAppsOwnCopy() {
        withWorld { w in
            plantSynced(w, "sk-app")
            plantLogin(w, "sk-cli")
            #expect(askingRead(w) == "sk-app")
            #expect(loginValue(w) == "sk-app")
        }
    }

    /// Both copies moved but hold the same key: nothing is rewritten.
    @Test func agreeingCopies_areLeftAlone() {
        withWorld { w in
            plantSynced(w, "sk-same")
            plantLogin(w, "sk-same")
            #expect(askingRead(w) == "sk-same")
            #expect(w.synced.writes == 0)
            #expect(w.login.writes == 0)
        }
    }

    // MARK: - The declined dialog

    /// A declined dialog is asked once, not on every Settings visit — and asked
    /// again when the CLI writes the copy again.
    @Test func declinedDialog_isNotReaskedUntilTheCopyMoves() {
        withWorld { w in
            plantLogin(w, "sk-cli")
            w.login.declinePrompts = true
            #expect(askingRead(w) == nil)
            #expect(w.login.prompts == 1)
            #expect(askingRead(w) == nil)
            #expect(askingRead(w) == nil)
            #expect(w.login.prompts == 1)

            w.clock.tick()
            plantLogin(w, "sk-cli-again")
            w.login.declinePrompts = false
            #expect(askingRead(w) == "sk-cli-again")
            #expect(w.login.prompts == 2)
        }
    }

    /// The CLI's copy is newer but the dialog was declined: the app keeps its
    /// own, and does not throw the synced copy away.
    @Test func declinedNewerLoginCopy_keepsTheSyncedCopy() {
        withWorld { w in
            write(w, "sk-app")
            w.clock.tick()
            plantLogin(w, "sk-cli")
            w.login.declinePrompts = true
            #expect(askingRead(w) == "sk-app")
            #expect(syncedValue(w) == "sk-app")
        }
    }

    // MARK: - Writes

    /// A save goes to both keychains, and both are read back.
    @Test func write_storesBothCopies_andReadsBothBack() {
        withWorld { w in
            #expect(write(w, "sk-both") == true)
            #expect(syncedValue(w) == "sk-both")
            #expect(loginValue(w) == "sk-both")
            #expect(w.synced.reads >= 1)
            #expect(w.login.reads >= 1)
        }
    }

    /// The app's own copy refused — `-34018` on an ad-hoc build — is the app's
    /// failure and the save says so.
    @Test func write_refusedSyncedCopy_isReportedFalse() {
        withWorld { w in
            w.synced.refuseWrites = true
            #expect(write(w, "sk") == false)
        }
    }

    /// The login copy refused is the CLI's loss, not the app's: the save still
    /// succeeds for the app, and the refusal is logged rather than shown as a
    /// key that did not save.
    @Test func write_refusedLoginCopy_stillSucceedsForTheApp() {
        withWorld { w in
            w.login.refuseWrites = true
            #expect(write(w, "sk") == true)
            #expect(syncedValue(w) == "sk")
            #expect(loginValue(w) == nil)
        }
    }

    /// A save the app cannot read back is not a save.
    @Test func write_thatDoesNotReadBack_isReportedFalse() {
        withWorld { w in
            w.synced.refuseReads = true
            #expect(write(w, "sk") == false)
        }
    }

    // MARK: - Delete

    @Test func remove_clearsBothCopies() {
        withWorld { w in
            write(w, "sk")
            SharedKeychainItem.remove(service: service, account: account,
                                      synced: w.synced, login: w.login, defaults: w.defaults)
            #expect(syncedValue(w) == nil)
            #expect(loginValue(w) == nil)
            #expect(quietRead(w) == nil)
        }
    }

    /// Deleting is the one case absence must not be read as: a copy missing on
    /// one side while the other still holds it comes back, by design.
    @Test func aCopyDeletedOnOneSideOnly_comesBack() {
        withWorld { w in
            write(w, "sk")
            w.login.delete(service: service, account: account, interaction: .allowed)
            #expect(quietRead(w) == "sk")
            #expect(loginValue(w) == "sk")
        }
    }
}
