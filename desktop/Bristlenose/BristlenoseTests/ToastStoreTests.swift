import Testing

@testable import Bristlenose

/// A toast takes no focus, so VoiceOver hears it only if the store announces it.
@MainActor
@Suite("ToastStore announces")
struct ToastStoreTests {
    @Test func showAnnouncesTheMessage() {
        var heard: [String] = []
        let store = ToastStore(announce: { heard.append($0) })
        store.show("Copied")
        #expect(store.message == "Copied")
        #expect(heard == ["Copied"])
    }

    @Test func aReplacingToastIsAnnouncedToo() {
        var heard: [String] = []
        let store = ToastStore(announce: { heard.append($0) })
        store.show("Copied")
        store.show("Couldn't copy")
        #expect(heard == ["Copied", "Couldn't copy"])
    }
}
