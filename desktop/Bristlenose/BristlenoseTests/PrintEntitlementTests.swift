#if DEBUG
import AppKit
import Security
import Testing
@testable import Bristlenose

/// File ▸ Print… under the App Sandbox (R69).
///
/// "This application does not support printing. Please contact the
/// application's developer." is not AppKit's answer to an unhandled ⌘P. It is
/// the sandbox refusing the print panel, raised from inside
/// `NSPrintPanel.beginSheet…` when the process lacks `com.apple.security.print`
/// — so it fired on the one path that should print, a report in front. The
/// entitlement is generated from `ENABLE_RESOURCE_ACCESS_PRINTING` in the
/// pbxproj, which was `NO` in both configurations (measured 21 Oct 2026, and
/// with the setting flipped the panel attaches as a sheet).
///
/// Tests run the Debug configuration only; `tests/test_entitlements_split.py`
/// pins the same setting for Release, which is what ships, and the artefact
/// gates (`check-pkg-shippable.sh`, `check-dmg-shippable.sh`) read it off the
/// signed app. **On CI these tests are vacuous:** CI builds unsigned, so the
/// host is not sandboxed and nothing refuses a print. There the Python test is
/// the only pin.
@MainActor
@Suite("Printing under the sandbox")
struct PrintEntitlementTests {

    private static func entitlement(_ key: String) -> Bool {
        guard let task = SecTaskCreateFromSelf(nil),
              let value = SecTaskCopyValueForEntitlement(task, key as CFString, nil)
        else { return false }
        return (value as? Bool) == true
    }

    /// An unsigned host (CI builds with `CODE_SIGNING_ALLOWED=NO`) is not
    /// sandboxed, so nothing refuses its print panel and the question is moot.
    private static var sandboxRefusesPrinting: Bool {
        entitlement("com.apple.security.app-sandbox") && !entitlement("com.apple.security.print")
    }

    @Test func theSandboxedHostMayPrint() {
        #expect(!Self.sandboxRefusesPrinting,
                "sandboxed without com.apple.security.print: every print raises 'does not support printing'")
    }

    /// The outcome itself: a print operation run the way `PrintActions.print`
    /// runs it attaches the print panel to the window. Guarded, because without
    /// the entitlement the refusal is an app-modal alert and the test would hang
    /// on it rather than fail.
    @Test func aPrintAttachesThePrintPanelToTheWindow() async throws {
        try #require(!Self.sandboxRefusesPrinting)
        let view = NSTextView(frame: NSRect(x: 0, y: 0, width: 300, height: 200))
        view.string = "R69"
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 400, height: 300),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView?.addSubview(view)
        window.orderFront(nil)
        defer { window.close() }

        let operation = NSPrintOperation(view: view, printInfo: NSPrintInfo.shared)
        operation.showsPrintPanel = true
        operation.showsProgressPanel = true
        operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)

        var sheet: NSWindow?
        for _ in 0..<40 where sheet == nil {
            try await Task.sleep(nanoseconds: 50_000_000)
            sheet = window.attachedSheet
        }
        #expect(sheet != nil, "no print panel attached to the window")
        if let sheet { window.endSheet(sheet, returnCode: .cancel) }
        try await Task.sleep(nanoseconds: 200_000_000)
    }

    /// The write-up this replaced blamed the dimmed item for letting ⌘P fall
    /// through to a responder. The menu bar takes a dimmed item's key equivalent
    /// instead (AppKit's behaviour, asserted here as the evidence). What this
    /// pins of ours: there is exactly one ⌘P item, so no second one (SwiftUI's
    /// default print group, say) can answer the key while ours is dimmed. The
    /// probe that showed no `print:` reaching a responder is not kept.
    @Test func commandPWithPrintDimmedIsTakenByTheMenuBar() throws {
        let menu = try #require(NSApp.mainMenu)
        func items(_ m: NSMenu) -> [NSMenuItem] {
            m.items.flatMap { [$0] + ($0.submenu.map(items) ?? []) }
        }
        let printItems = items(menu).filter {
            $0.keyEquivalent == "p" && $0.keyEquivalentModifierMask == .command
        }
        #expect(printItems.count == 1, "one ⌘P item in the menu bar")
        let item = try #require(printItems.first)
        // With a report in front the press would really print; only the dimmed
        // state is under test, and the test host has no report open.
        try #require(!item.isEnabled)

        let event = try #require(NSEvent.keyEvent(
            with: .keyDown, location: .zero, modifierFlags: .command,
            timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: 0,
            context: nil, characters: "p", charactersIgnoringModifiers: "p",
            isARepeat: false, keyCode: 35))
        #expect(menu.performKeyEquivalent(with: event))
    }
}
#endif
