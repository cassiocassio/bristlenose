import Foundation
import Testing
@testable import Bristlenose

/// AutoCode landing plan Phase 5b (D51): the report draws no AutoCode pop-up only where the host's
/// sidebar shows AutoCode, which today is the AppKit sidebar alone. The page learns it from one
/// injected flag; this pins that the host sets it exactly when that sidebar is on.
struct SidebarAutoCodeCapabilityTests {

    private func suite() -> UserDefaults {
        let name = "SidebarAutoCodeCapabilityTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    @Test func theAppKitSidebarTellsThePageItShowsAutoCode() {
        let d = suite()
        d.set(true, forKey: BristlenoseFlags.appKitSidebarKey)
        #expect(WebView.sidebarAutoCodeScript(in: d) == "window.__BRISTLENOSE_SIDEBAR_AUTOCODE__ = true;")
    }

    @Test func theSwiftUISidebarSaysNothingSoThePageKeepsItsPopUp() {
        let d = suite()
        #expect(WebView.sidebarAutoCodeScript(in: d) == nil)  // unset: the shipping default
        d.set(false, forKey: BristlenoseFlags.appKitSidebarKey)
        #expect(WebView.sidebarAutoCodeScript(in: d) == nil)
    }

    /// The key is the one the sidebar itself switches on (`ContentView` reads `appKitSidebar`).
    @Test func theFlagIsTheSidebarsOwnSwitch() {
        #expect(BristlenoseFlags.appKitSidebarKey == "BristlenoseAppKitSidebar")
    }
}
