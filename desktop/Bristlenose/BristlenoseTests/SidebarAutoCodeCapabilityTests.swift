import Foundation
import Testing
@testable import Bristlenose

/// AutoCode landing plan Phase 5b (D51): the report draws no AutoCode pop-up only where the host's
/// sidebar shows AutoCode, which today is the AppKit sidebar alone. The page learns it from one
/// injected flag; this pins that the scripts the web view injects (`WebView.reportUserScripts`,
/// the only source `makeNSView` adds) carry it exactly when that sidebar is on.
@MainActor
struct SidebarAutoCodeCapabilityTests {

    private static let capability = "window.__BRISTLENOSE_SIDEBAR_AUTOCODE__ = true;"

    private func suite() -> UserDefaults {
        let name = "SidebarAutoCodeCapabilityTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    @Test func theAppKitSidebarTellsThePageItShowsAutoCode() {
        let d = suite()
        d.set(true, forKey: BristlenoseFlags.appKitSidebarKey)
        let scripts = WebView.reportUserScripts(authToken: nil, in: d)
        #expect(scripts.filter { $0 == Self.capability }.count == 1)
    }

    @Test func theSwiftUISidebarSaysNothingSoThePageKeepsItsPopUp() {
        let d = suite()
        // Unset is the shipping default.
        #expect(!WebView.reportUserScripts(authToken: nil, in: d).contains(Self.capability))
        d.set(false, forKey: BristlenoseFlags.appKitSidebarKey)
        #expect(!WebView.reportUserScripts(authToken: nil, in: d).contains(Self.capability))
    }

    /// The builder still tells the page the rest: it is the only source of the web view's scripts.
    @Test func theOtherHostFactsStillReachThePage() {
        let d = suite()
        let scripts = WebView.reportUserScripts(authToken: "abc_123-X", in: d)
        #expect(scripts.first == "window.__BRISTLENOSE_EMBEDDED__ = true;")
        #expect(scripts.contains("window.__BRISTLENOSE_NATIVE_PERSON_PICKER__ = true;"))
        #expect(scripts.contains("window.__BRISTLENOSE_AUTH_TOKEN__ = 'abc_123-X';"))
        #expect(scripts.contains(BridgeHandler.subtitlePrefsSeedScript(defaults: d)))
        #expect(scripts.contains(BridgeHandler.reportPrefsSeedScript(defaults: d)))
        // A token that could break out of the string literal is never interpolated.
        #expect(!WebView.reportUserScripts(authToken: "x'; alert(1); '", in: d)
            .contains { $0.contains("AUTH_TOKEN") })
    }

    /// The key is the one the sidebar itself switches on (`ContentView` reads `appKitSidebar`).
    @Test func theFlagIsTheSidebarsOwnSwitch() {
        #expect(BristlenoseFlags.appKitSidebarKey == "BristlenoseAppKitSidebar")
    }
}
