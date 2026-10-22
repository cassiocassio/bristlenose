import Foundation
import Testing
@testable import Bristlenose

/// When the API-key field commits, and what a commit is allowed to claim.
///
/// R36 (a key that failed to save looks saved), R38 (a paste not committed with
/// Return is thrown away) and the API-key half of R34 (tabbing through the field
/// rewrites the key, bills a validation and reloads the report). The SwiftUI
/// event order that reaches `commit` is not reachable from here; the by-hand
/// walk covers it. Never the real keychain: `InMemoryKeychain` behind a spy.
@MainActor
@Suite("APIKeyDrafts")
struct APIKeyDraftsTests {

    /// Counts writes and can fail the three ways a keychain write fails.
    final class SpyKeychain: KeychainStore {
        enum WriteMode { case normal, refuse, lie, storesButReportsFalse }
        let inner = InMemoryKeychain()
        var mode: WriteMode = .normal
        private(set) var writes = 0
        private(set) var deletes = 0

        func get(provider: String, account: String) -> String? {
            inner.get(provider: provider, account: account)
        }
        func set(provider: String, account: String, value: String) -> Bool {
            writes += 1
            switch mode {
            case .normal: return inner.set(provider: provider, account: account, value: value)
            case .refuse: return false
            case .lie: return true
            case .storesButReportsFalse:
                inner.set(provider: provider, account: account, value: value)
                return false
            }
        }
        func delete(provider: String, account: String) {
            deletes += 1
            inner.delete(provider: provider, account: account)
        }
        func accounts(provider: String) -> [String] { inner.accounts(provider: provider) }
    }

    // MARK: - R34: an unedited field writes nothing

    @Test func tabbingThroughAnUneditedField_writesAndClaimsNothing() {
        let store = SpyKeychain()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")

        let outcome = drafts.commit(.claude, store: store)

        #expect(outcome == .unchanged)
        #expect(outcome.changesWhatRunsUse == false)
        #expect(store.writes == 0)
    }

    @Test func aSecondCommitOfTheSameKey_isUnchanged() {
        let store = SpyKeychain()
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .saved("sk-new"))
        #expect(drafts.commit(.claude, store: store) == .unchanged)
        #expect(store.writes == 1)
    }

    // MARK: - R38: a row that was never loaded is not a cleared field

    @Test func committingARowNeverLoaded_doesNotDeleteItsKey() {
        let store = SpyKeychain()
        store.inner.set(provider: "openai", value: "sk-openai")
        var drafts = APIKeyDrafts()

        let outcome = drafts.commit(.chatGPT, store: store)

        #expect(outcome == .unchanged)
        #expect(store.deletes == 0)
        #expect(store.inner.get(provider: "openai") == "sk-openai")
    }

    @Test func aDirtyField_survivesTheRowBeingShownAgain() {
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-old")
        drafts.edit(.claude, "sk-pasted")

        drafts.load(.claude, stored: "sk-old")

        #expect(drafts.text(.claude) == "sk-pasted")
        #expect(drafts.isDirty(.claude))
    }

    @Test func aCleanField_reloadsWhatTheKeychainNowHolds() {
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-old")

        drafts.load(.claude, stored: "sk-from-terminal")

        #expect(drafts.text(.claude) == "sk-from-terminal")
        #expect(!drafts.isDirty(.claude))
    }

    @Test func emptyingALoadedField_deletesTheKey() {
        let store = SpyKeychain()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")
        drafts.edit(.claude, "")

        let outcome = drafts.commit(.claude, store: store)

        #expect(outcome == .deleted)
        #expect(outcome.changesWhatRunsUse)
        #expect(store.inner.get(provider: "anthropic") == nil)
    }

    // MARK: - R37: Clear reads back, never assumes

    @Test func clear_deletesTheKey_andLeavesTheFieldEmpty() {
        let store = SpyKeychain()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")

        let gone = drafts.clear(.claude, store: store)

        #expect(gone)
        #expect(store.deletes == 1)
        #expect(drafts.text(.claude) == "")
        #expect(!drafts.isDirty(.claude))
    }

    /// The Keychain kept the key (a refused delete): the field shows it again
    /// and reports it, instead of an empty field beside a status that still
    /// says the key works.
    @Test func clear_whenTheKeychainKeepsTheKey_showsItAgain() {
        let store = SpyKeychain()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        store.inner.refuseDeletes = true
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")

        let gone = drafts.clear(.claude, store: store)

        #expect(gone == false)
        #expect(drafts.text(.claude) == "sk-stored")
        #expect(!drafts.isDirty(.claude), "what is shown is what is stored")
    }

    // MARK: - R36: a key that failed to save says so

    @Test func aRefusedWrite_isFailed_andKeepsThePastedKey() {
        let store = SpyKeychain()
        store.inner.set(provider: "anthropic", value: "sk-old")
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-old")
        drafts.edit(.claude, "sk-new")

        let outcome = drafts.commit(.claude, store: store)

        #expect(outcome == .failed)
        #expect(outcome.changesWhatRunsUse == false)
        #expect(drafts.failed.contains(.claude))
        #expect(drafts.text(.claude) == "sk-new")
        #expect(drafts.isDirty(.claude))
    }

    @Test func aWriteThatReportsSuccessButStoresNothing_isFailed() {
        let store = SpyKeychain()
        store.mode = .lie
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .failed)
        #expect(drafts.failed.contains(.claude))
    }

    /// The read-back decides, not `set`'s return: an ad-hoc build refuses the
    /// synced copy and keeps the login copy, which is what a run then reads.
    @Test func aWriteThatReportsFailureButReadsBack_isSaved() {
        let store = SpyKeychain()
        store.mode = .storesButReportsFalse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .saved("sk-new"))
        #expect(!drafts.failed.contains(.claude))
    }

    @Test func returnAfterAFailure_retries_andClearsTheError() {
        let store = SpyKeychain()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")
        #expect(drafts.commit(.claude, store: store) == .failed)

        store.mode = .normal
        let retry = drafts.commit(.claude, store: store)

        #expect(retry == .saved("sk-new"))
        #expect(!drafts.failed.contains(.claude))
        #expect(!drafts.isDirty(.claude))
    }

    // MARK: - Against the real two-keychain reconciler

    /// `KeychainHelper.liveStore`'s shape — quiet read, allowed write — over
    /// `SharedKeychainItem` with in-memory keychains and a throwaway ledger.
    final class ReconciledStore: KeychainStore {
        let synced = InMemoryRawKeychain()
        let login = InMemoryRawKeychain()
        let ledger: UserDefaults
        init() {
            let name = "app.bristlenose.test.apikeydrafts.\(UUID().uuidString)"
            ledger = UserDefaults(suiteName: name)!
            ledger.removePersistentDomain(forName: name)
        }
        private func service(_ provider: String) -> String { KeychainHelper.serviceNames[provider]! }
        func get(provider: String, account: String) -> String? {
            SharedKeychainItem.read(service: service(provider), account: account,
                                    synced: synced, login: login,
                                    interaction: .quiet, defaults: ledger)
        }
        func set(provider: String, account: String, value: String) -> Bool {
            SharedKeychainItem.write(service: service(provider), account: account, value: value,
                                     synced: synced, login: login,
                                     interaction: .allowed, defaults: ledger)
        }
        func delete(provider: String, account: String) {
            SharedKeychainItem.remove(service: service(provider), account: account,
                                      synced: synced, login: login,
                                      interaction: .allowed, defaults: ledger)
        }
        func accounts(provider: String) -> [String] { [] }
    }

    /// An ad-hoc build: the synced write is refused, the login copy is kept,
    /// and that copy is what a run reads — so the key is saved.
    @Test func reconciler_syncedRefused_noOldKey_isSaved() {
        let store = ReconciledStore()
        store.synced.refuseWrites = true
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .saved("sk-new"))
        #expect(store.login.read(service: KeychainHelper.serviceNames["anthropic"]!,
                                 account: KeychainHelper.account,
                                 interaction: .allowed).value == "sk-new")
    }

    /// The synced write is refused over an older synced key: a run still reads
    /// the old one, so the new one was not saved, whatever the login copy holds.
    @Test func reconciler_syncedRefused_overAnOldKey_isFailed() {
        let store = ReconciledStore()
        let service = KeychainHelper.serviceNames["anthropic"]!
        let then = Date(timeIntervalSinceNow: -3600)
        store.synced.plant(service: service, account: KeychainHelper.account,
                           value: "sk-old", at: then, foreign: false)
        store.login.plant(service: service, account: KeychainHelper.account,
                          value: "sk-old", at: then, foreign: false)
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: store.get(provider: "anthropic"))
        #expect(drafts.text(.claude) == "sk-old")
        store.synced.refuseWrites = true
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .failed)
        #expect(store.get(provider: "anthropic") == "sk-old")
        // And the CLI's copy: "isn't being used" is true there too (#11).
        #expect(store.login.read(service: service, account: KeychainHelper.account,
                                 interaction: .allowed).value == "sk-old")
    }

    @Test func reconciler_bothRefused_isFailed() {
        let store = ReconciledStore()
        store.synced.refuseWrites = true
        store.login.refuseWrites = true
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")

        #expect(drafts.commit(.claude, store: store) == .failed)
    }

    // MARK: - #6: the row in the provider list

    /// A key that failed to save on leaving its row says so in the list, not
    /// only under a field that is no longer on screen (decision #6, 22 Oct 2026).
    @Test func aFailedSave_showsKeyNotSaved_inTheRow_whateverTheStatus() {
        let store = SpyKeychain()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-old")
        drafts.edit(.claude, "sk-new")
        #expect(drafts.commit(.claude, store: store) == .failed)

        for status in [ProviderStatus.online, .checking, .invalid, .notSetUp] {
            #expect(drafts.caption(.claude, status: status) == .keyNotSaved)
        }
        #expect(drafts.caption(.chatGPT, status: .online) == .status(.online))
    }

    @Test func aSaveAfterAFailure_putsTheStatusBack() {
        let store = SpyKeychain()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")
        _ = drafts.commit(.claude, store: store)
        store.mode = .normal
        _ = drafts.commit(.claude, store: store)

        #expect(drafts.caption(.claude, status: .checking) == .status(.checking))
    }

    @Test func clearingAfterAFailure_putsTheStatusBack() {
        let store = SpyKeychain()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-new")
        _ = drafts.commit(.claude, store: store)
        store.mode = .normal
        drafts.clear(.claude, store: store)

        #expect(drafts.caption(.claude, status: .notSetUp) == .status(.notSetUp))
    }

    @Test func ollamaHasNoKey_andNeverCommits() {
        let store = SpyKeychain()
        var drafts = APIKeyDrafts()
        drafts.edit(.ollama, "anything")

        #expect(drafts.commit(.ollama, store: store) == .unchanged)
        #expect(store.writes == 0 && store.deletes == 0)
    }
}
