import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// What ⌘Q does with an API key pasted into Settings and never committed
/// (R36/R38 follow-up #5). No window closes on terminate, so no exit of the pane
/// fires and the paste was lost. Quit saves it as closing the window would, off
/// the main thread, and the app waits for the write before it exits.
///
/// Whether `applicationShouldTerminate` is reached from ⌘Q, the Dock and logout,
/// and whether the pane registers its drafts, is not reachable from here; the
/// by-hand walk covers it. Never the real keychain.
@MainActor
@Suite("APIKeyQuitSave")
struct APIKeyQuitSaveTests {
    typealias Spy = APIKeyDraftsTests.SpyKeychain

    /// Holds the off-main write until the test runs it, so "the reply waits for
    /// the write" can be asserted from both sides.
    final class HeldHop {
        private(set) var held: [() -> Void] = []
        func hop(_ work: @escaping () -> Void) { held.append(work) }
        func runAll() { let w = held; held = []; w.forEach { $0() } }
    }

    private func quitSave(_ store: Spy, _ drafts: APIKeyDrafts?, offMain: HeldHop,
                          onMain: HeldHop? = nil) -> APIKeyQuitSave {
        let q = APIKeyQuitSave(store: store, offMain: offMain.hop,
                               onMain: onMain.map { $0.hop } ?? { $0() })
        if let drafts { q.drafts = { drafts } }
        return q
    }

    @Test func aPasteThenQuit_isSaved_andTheQuitWaitsForTheWrite() {
        let store = Spy()
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-pasted")
        let hop = HeldHop()
        let main = HeldHop()
        var replies: [Bool] = []

        let answer = quitSave(store, drafts, offMain: hop, onMain: main)
            .shouldTerminate { replies.append($0) }

        #expect(answer == .terminateLater)
        #expect(replies.isEmpty)
        #expect(store.writes == 0)
        hop.runAll()
        #expect(store.inner.get(provider: "anthropic") == "sk-pasted")
        // AppKit takes the reply on the main thread only.
        #expect(replies.isEmpty)
        main.runAll()
        #expect(replies == [true])
    }

    @Test func anEditOfAStoredKey_isSavedAtQuit() {
        let store = Spy()
        store.inner.set(provider: "openai", value: "sk-old")
        var drafts = APIKeyDrafts()
        drafts.load(.chatGPT, stored: "sk-old")
        drafts.edit(.chatGPT, "sk-new")
        let hop = HeldHop()
        var replies: [Bool] = []

        #expect(quitSave(store, drafts, offMain: hop).shouldTerminate { replies.append($0) }
                == .terminateLater)
        hop.runAll()

        #expect(store.inner.get(provider: "openai") == "sk-new")
        #expect(replies == [true])
    }

    @Test func anUneditedField_quitsNow_andWritesNothing() {
        let store = Spy()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")
        let hop = HeldHop()
        var replies: [Bool] = []

        let answer = quitSave(store, drafts, offMain: hop).shouldTerminate { replies.append($0) }

        #expect(answer == .terminateNow)
        #expect(hop.held.isEmpty)
        #expect(store.writes == 0 && store.deletes == 0)
        #expect(replies.isEmpty)
    }

    @Test func settingsNeverOpened_quitsNow() {
        let hop = HeldHop()
        let answer = quitSave(Spy(), nil, offMain: hop).shouldTerminate { _ in }
        #expect(answer == .terminateNow)
        #expect(hop.held.isEmpty)
    }

    /// Today's rules decide, not the quit: Ollama has no key, and a row never
    /// loaded is not a cleared field.
    @Test func whatACloseWouldNotSave_quitDoesNotSaveEither() {
        let store = Spy()
        store.inner.set(provider: "google", value: "sk-gemini")
        var drafts = APIKeyDrafts()
        drafts.edit(.ollama, "whatever")
        let hop = HeldHop()

        #expect(drafts.pendingRows.isEmpty)
        #expect(quitSave(store, drafts, offMain: hop).shouldTerminate { _ in } == .terminateNow)
        #expect(store.inner.get(provider: "google") == "sk-gemini")
    }

    /// Emptying the field and closing the window deletes the key; so does quit.
    @Test func anEmptiedField_isDeletedAtQuit_asOnClose() {
        let store = Spy()
        store.inner.set(provider: "anthropic", value: "sk-stored")
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: "sk-stored")
        drafts.edit(.claude, "")
        let hop = HeldHop()
        var replies: [Bool] = []

        #expect(quitSave(store, drafts, offMain: hop).shouldTerminate { replies.append($0) }
                == .terminateLater)
        hop.runAll()

        #expect(store.inner.get(provider: "anthropic") == nil)
        #expect(replies == [true])
    }

    /// A refusal is logged and the quit goes on. No alert, no cancelled quit.
    @Test func aRefusedSave_stillQuits() {
        let store = Spy()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-pasted")
        let hop = HeldHop()
        var replies: [Bool] = []

        _ = quitSave(store, drafts, offMain: hop).shouldTerminate { replies.append($0) }
        hop.runAll()

        #expect(store.writes == 1)
        #expect(replies == [true])
    }

    /// A save that failed when the window closed is still a paste on screen, so
    /// quit tries it once more, as closing the window again would.
    @Test func aSaveThatFailedOnClose_isTriedAgainAtQuit() {
        let store = Spy()
        store.mode = .refuse
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-pasted")
        #expect(drafts.commit(.claude, store: store) == .failed)
        store.mode = .normal
        let hop = HeldHop()

        #expect(quitSave(store, drafts, offMain: hop).shouldTerminate { _ in } == .terminateLater)
        hop.runAll()

        #expect(store.inner.get(provider: "anthropic") == "sk-pasted")
    }

    /// Once quitting, the pane's own exits stand down: a Keychain dialog takes
    /// key from the Settings window, and its resign-key commit would write a
    /// second time and restart the serve mid-quit.
    @Test func onceQuitting_thePanesOwnCommitsStandDown() {
        let q = quitSave(Spy(), nil, offMain: HeldHop())
        #expect(q.isTerminating == false)
        _ = q.shouldTerminate { _ in }
        #expect(q.isTerminating)
    }

    /// The quit's save is not a key change for the running serve: the app is
    /// exiting, and the next launch reads the key from the Keychain.
    @Test func theQuitSave_postsNoPrefsChange() {
        let store = Spy()
        var drafts = APIKeyDrafts()
        drafts.load(.claude, stored: nil)
        drafts.edit(.claude, "sk-pasted")
        let hop = HeldHop()
        var posts = 0
        let token = NotificationCenter.default.addObserver(
            forName: .bristlenosePrefsChanged, object: nil, queue: nil) { _ in posts += 1 }
        defer { NotificationCenter.default.removeObserver(token) }

        _ = quitSave(store, drafts, offMain: hop).shouldTerminate { _ in }
        hop.runAll()

        #expect(store.inner.get(provider: "anthropic") == "sk-pasted")
        #expect(posts == 0)
    }
}
