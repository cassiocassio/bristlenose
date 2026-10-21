import Foundation

/// The API-key field's text per provider, held against what the Keychain had
/// when the row was loaded, and the one place that decides what a commit does.
///
/// **A commit acts only on an edit.** Settings ▸ LLM Provider commits on Return,
/// on focus loss, on a row change, on a pane switch and on window close, and
/// SwiftUI does not promise the order of those events. So `commit` must be safe
/// to call any number of times, for any row: an unedited field writes nothing,
/// validates nothing and changes nothing a run reads (R34: tabbing through the
/// field used to rewrite the key, bill a validation and reload the report), and
/// a row that was never loaded is not a cleared field (`nil` is not `""`, or a
/// blur that lands after a row change deletes the new row's key).
///
/// **The read-back decides, never `set`'s return** (R36). `set` reporting false
/// can still leave a key a run will read (an ad-hoc build refuses the synced
/// copy and keeps the login copy), and a clean `set` proves nothing. What
/// `store.get` returns afterwards is what a run gets, so that is the verdict,
/// and that value is the one to validate.
///
/// **A failed save keeps the pasted key on screen**, still dirty, so `load`
/// does not overwrite it and Return retries (R38: a paste used to be replaced
/// by the stored key whenever the row was shown again).
struct APIKeyDrafts {
    private(set) var typed: [LLMProvider: String] = [:]
    private(set) var baseline: [LLMProvider: String] = [:]
    /// Rows whose last commit did not reach the Keychain.
    private(set) var failed: Set<LLMProvider> = []

    enum Outcome: Equatable {
        case unchanged
        /// The value read back from the Keychain.
        case saved(String)
        case deleted
        case failed

        /// Whether the key a run reads has changed, which is the only reason to
        /// restart the serve (and so reload the report).
        var changesWhatRunsUse: Bool {
            switch self {
            case .saved, .deleted: true
            case .unchanged, .failed: false
            }
        }
    }

    func text(_ provider: LLMProvider) -> String { typed[provider, default: ""] }

    mutating func edit(_ provider: LLMProvider, _ text: String) { typed[provider] = text }

    /// A row never loaded reads `""` against a `""` baseline: not an edit.
    func isDirty(_ provider: LLMProvider) -> Bool {
        typed[provider, default: ""] != baseline[provider, default: ""]
    }

    /// Show what the Keychain holds, unless the field holds an edit not yet saved.
    mutating func load(_ provider: LLMProvider, stored: String?) {
        guard !isDirty(provider) else { return }
        typed[provider] = stored ?? ""
        baseline[provider] = stored ?? ""
    }

    /// The Clear button deleted the key itself.
    mutating func cleared(_ provider: LLMProvider) {
        typed[provider] = ""
        baseline[provider] = ""
        failed.remove(provider)
    }

    /// The Clear button: delete the key, then read back what a run would now
    /// get and show that. `true` when nothing is left. A key the Keychain kept
    /// — the app's own copy refused, or a CLI-created login copy on a build
    /// that could not withhold it — comes back into the field rather than an
    /// empty field standing beside a status that still says the key works (R37
    /// review). The ledger side of that case is `SharedKeychainItem.remove`.
    @discardableResult
    mutating func clear(_ provider: LLMProvider, store: any KeychainStore) -> Bool {
        guard let keychainKey = provider.keychainProvider else { return true }
        store.delete(provider: keychainKey)
        cleared(provider)
        let left = store.get(provider: keychainKey)
        load(provider, stored: left)
        return left == nil
    }

    mutating func commit(_ provider: LLMProvider, store: any KeychainStore) -> Outcome {
        guard let keychainKey = provider.keychainProvider, isDirty(provider) else {
            return .unchanged
        }
        let value = typed[provider, default: ""]
        if value.isEmpty {
            store.delete(provider: keychainKey)
            baseline[provider] = ""
            failed.remove(provider)
            return .deleted
        }
        store.set(provider: keychainKey, value: value)
        guard let readBack = store.get(provider: keychainKey), readBack == value else {
            failed.insert(provider)
            return .failed
        }
        baseline[provider] = readBack
        failed.remove(provider)
        return .saved(readBack)
    }
}
