import Foundation
import Testing
@testable import Bristlenose

/// The Display popover shows what the report has, not a default of its own.
///
/// The SPA owns Layout, Density and Break long paragraphs and posts them
/// (`display-prefs`); native mirrors the last good post. These pin that the
/// mirror follows the SPA, ignores a message carrying a value the SPA could not
/// have sent, and returns to "today's screen" for a new web view, which the SPA
/// then re-syncs on mount.
@MainActor
struct DisplayPrefsMirrorTests {

    private func post(layout: String = "columns", density: Any = 0.5, breaks: String = "off") -> [String: Any] {
        ["type": "display-prefs", "layout": layout, "density": density, "breaks": breaks]
    }

    @Test func aNewReportStartsOnTodaysScreen() {
        let bridge = BridgeHandler()
        #expect(bridge.displayPrefs == DisplayPrefs(layout: "columns", density: 0.5, breaks: "off"))
        #expect(!bridge.displayPrefs.breaksOn)
    }

    @Test func thePopoverFollowsWhatTheReportPosts() {
        let bridge = BridgeHandler()
        bridge.handleMessage(post(layout: "single", density: 0.85, breaks: "on"))
        #expect(bridge.displayPrefs == DisplayPrefs(layout: "single", density: 0.85, breaks: "on"))
        #expect(bridge.displayPrefs.breaksOn)
    }

    @Test func aWholeNumberDensityFromJavaScriptIsStillANumber() {
        // JSON gives 0 and 1 as integers; the slider's ends must parse.
        let bridge = BridgeHandler()
        bridge.handleMessage(post(density: NSNumber(value: 0)))
        #expect(bridge.displayPrefs.density == 0)
        bridge.handleMessage(post(density: NSNumber(value: 1)))
        #expect(bridge.displayPrefs.density == 1)
    }

    @Test(arguments: [
        ("triple", 0.5 as Any, "off"),
        ("columns", 1.5 as Any, "off"),
        ("columns", -0.1 as Any, "off"),
        ("columns", "roomy" as Any, "off"),
        ("columns", Double.nan as Any, "off"),
        ("columns", NSNumber(value: true) as Any, "off"),
        ("columns", 0.5 as Any, "maybe"),
    ])
    func aValueTheReportCouldNotHaveSentChangesNothing(_ layout: String, _ density: Any, _ breaks: String) {
        let bridge = BridgeHandler()
        bridge.handleMessage(post(layout: "single", density: 0.2, breaks: "on"))
        bridge.handleMessage(post(layout: layout, density: density, breaks: breaks))
        #expect(bridge.displayPrefs == DisplayPrefs(layout: "single", density: 0.2, breaks: "on"))
    }

    @Test func aMessageMissingAFieldChangesNothing() {
        let bridge = BridgeHandler()
        bridge.handleMessage(post(layout: "single"))
        bridge.handleMessage(["type": "display-prefs", "layout": "columns"])
        #expect(bridge.displayPrefs.layout == "single")
    }

    @Test func aNewWebViewDropsBackUntilTheReportPostsAgain() {
        let bridge = BridgeHandler()
        bridge.handleMessage(post(layout: "single", density: 0.1, breaks: "on"))
        bridge.reset()
        #expect(bridge.displayPrefs == .standard)
    }

    @Test func theMessageParserAcceptsEveryLayoutAndTheWholeDensityRange() {
        for layout in DisplayPrefs.layouts {
            for density in stride(from: 0.0, through: 1.0, by: 0.05) {
                for breaks in DisplayPrefs.breakValues {
                    let parsed = DisplayPrefs(message: post(layout: layout, density: density, breaks: breaks))
                    #expect(parsed == DisplayPrefs(layout: layout, density: density, breaks: breaks))
                }
            }
        }
    }
}
