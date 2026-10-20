import AppKit
import OSLog

/// ⌘Q with an API key pasted into Settings ▸ LLM Provider and never committed.
///
/// The pane saves a key at every exit it has (Return, Tab, a row change, a pane
/// switch, ⌘W, the window resigning key), and quit is none of them: AppKit
/// closes no window on terminate, so a paste then ⌘Q was lost. This saves it as
/// closing the window would, through the same `APIKeyDrafts.commit`, so what a
/// close would not save (an unedited field, Ollama, a row never shown) quit does
/// not save either, and an emptied field is deleted.
///
/// **What differs is what follows the write.** Nothing is validated and
/// `.bristlenosePrefsChanged` is not posted: the app is exiting, a serve restart
/// would race the quit's own teardown, and the next launch reads the key from
/// the Keychain anyway (the verdict cache is keyed on the key's hash, so the new
/// key is checked then).
///
/// **The write is off the main thread, behind `.terminateLater`.** Rewriting a
/// login-keychain copy `bristlenose configure` made raises the system's "wants
/// to use your confidential information" dialog, and the SecItem call blocks
/// until it is answered. On the main thread that is a hung app; exiting before
/// the answer tears the dialog down. So the app waits for the write and quits
/// after it (`NSApplication.reply(toApplicationShouldTerminate:)`).
///
/// **Once quitting, the pane's own exits stand down** (`isTerminating`). That
/// dialog takes key from the Settings window, and the resign-key commit would
/// write a second time on the main thread and restart the serve mid-quit.
///
/// A save that fails is logged and the quit goes on: no new alert (R36/R38
/// follow-up #5, `docs/design-desktop-settings.md`).
@MainActor
final class APIKeyQuitSave {
    typealias Hop = (@escaping () -> Void) -> Void

    static let shared = APIKeyQuitSave()

    private nonisolated static let logger = Logger(subsystem: "app.bristlenose",
                                                   category: "llm-settings")
    private nonisolated static let writer = DispatchQueue(label: "app.bristlenose.quit-key-save")

    /// The pane's drafts, registered each time it appears and never cleared.
    var drafts: (() -> APIKeyDrafts)?

    /// Set by the first `shouldTerminate`; the pane's commits check it.
    private(set) var isTerminating = false

    private let store: any KeychainStore
    private let offMain: Hop
    private let onMain: Hop

    init(store: any KeychainStore = KeychainHelper.liveStore,
         offMain: @escaping Hop = { APIKeyQuitSave.writer.async(execute: $0) },
         onMain: @escaping Hop = { DispatchQueue.main.async(execute: $0) }) {
        self.store = store
        self.offMain = offMain
        self.onMain = onMain
    }

    /// `applicationShouldTerminate`'s answer. `reply` is called once, on the
    /// main thread, after the write, and only when the answer is `.terminateLater`.
    func shouldTerminate(reply: @escaping (Bool) -> Void) -> NSApplication.TerminateReply {
        // Latched for good: every answer below ends in a quit. A future
        // `.terminateCancel` must reset it, or the pane stops saving keys.
        isTerminating = true
        // The snapshot is taken here, on the main actor: the value written is
        // the one on screen when Quit was chosen.
        guard let snapshot = drafts?(), !snapshot.pendingRows.isEmpty else { return .terminateNow }
        offMain(Self.save(snapshot, store: store, onMain: onMain, reply: reply))
        return .terminateLater
    }

    /// Built outside the main actor, because it runs outside it.
    private nonisolated static func save(_ snapshot: APIKeyDrafts, store: any KeychainStore,
                                         onMain: @escaping Hop,
                                         reply: @escaping (Bool) -> Void) -> () -> Void {
        {
            var drafts = snapshot
            for provider in drafts.pendingRows
            where drafts.commit(provider, store: store) == .failed {
                logger.error(
                    "API key for \(provider.rawValue, privacy: .public) did not reach the Keychain at quit")
            }
            onMain { reply(true) }
        }
    }
}

extension APIKeyDrafts {
    /// The rows a commit would act on now, which are the rows ⌘Q saves.
    var pendingRows: [LLMProvider] {
        LLMProvider.allCases.filter { $0.keychainProvider != nil && isDirty($0) }
    }
}
