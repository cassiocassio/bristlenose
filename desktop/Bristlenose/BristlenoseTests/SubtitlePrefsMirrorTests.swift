import Foundation
import Testing
@testable import Bristlenose

/// The subtitle preferences must outlive the webview.
///
/// The SPA keeps them in localStorage, and on the Mac that storage is
/// `.nonPersistent()` per serve session — so without a saved copy both would
/// be forgotten on every relaunch and project switch, and the Burn Subtitles
/// checkmark would quietly stop meaning anything. These pin the round trip:
/// the SPA's post is saved, and the next webview is seeded with it.
@MainActor
struct SubtitlePrefsMirrorTests {

    @Test func seedScriptCarriesTheSavedValues() throws {
        let suite = "SubtitlePrefsMirrorTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }

        defaults.set(true, forKey: BridgeHandler.playerSubtitlesKey)
        defaults.set(false, forKey: BridgeHandler.burnSubtitlesKey)
        let script = BridgeHandler.subtitlePrefsSeedScript(defaults: defaults)

        // The keys are subtitlePrefs.ts's; a rename on either side breaks the seed.
        #expect(script.contains("localStorage.setItem('bristlenose-player-subtitles', 'true')"))
        #expect(script.contains("localStorage.setItem('bristlenose-burn-subtitles', 'false')"))
    }

    @Test func aPostIsSavedAndSurvivesReset() {
        let standard = UserDefaults.standard
        let saved = (standard.object(forKey: BridgeHandler.playerSubtitlesKey),
                     standard.object(forKey: BridgeHandler.burnSubtitlesKey))
        defer {
            standard.set(saved.0, forKey: BridgeHandler.playerSubtitlesKey)
            standard.set(saved.1, forKey: BridgeHandler.burnSubtitlesKey)
        }

        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "subtitle-prefs", "player": false, "burn": true])
        #expect(standard.bool(forKey: BridgeHandler.burnSubtitlesKey))
        #expect(!standard.bool(forKey: BridgeHandler.playerSubtitlesKey))

        // A project switch remounts the report; the checkmark keeps the saved
        // value rather than dropping to off until the SPA re-posts.
        bridge.reset()
        #expect(bridge.burnSubtitlesInClips)
        #expect(!bridge.playerSubtitlesOn)
    }
}
