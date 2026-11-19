import AppKit
import SwiftUI
import Testing
@testable import Bristlenose

/// Native pixels for every Azure scenario on `docs/mockups/azure-scenarios.html`:
/// the real Settings ▸ LLM Provider pane with a shipped scenario overlaid
/// (`AzureScenarioFixture`, verdict from the real validator against a recorded
/// Azure body), and the real AppKit sidebar row and diagnostic popover for each
/// Azure run failure (`AzureRunScenario`). Same harness as
/// `StudyStartupPresentationTests`. Opt-in: run alone with
/// `TEST_RUNNER_BN_AZURE_VISUAL=1`, then
/// `xcrun xcresulttool export attachments --path <xcresult> --output-path <dir>`.
@MainActor
@Suite("Azure scenarios native presentation", .serialized)
struct AzureScenarioRenderTests {
    private static let enabled = ProcessInfo.processInfo.environment["BN_AZURE_VISUAL"] == "1"

    private func englishI18n() throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        return i18n
    }

    @Test("Settings pane in every Azure scenario", .enabled(if: enabled))
    func settingsPane() async throws {
        let i18n = try englishI18n()
        for fixture in AzureScenarioFixture.allCases {
            let verdict = await fixture.verdict()
            for dark in [false, true] {
                let pane = LLMSettingsView(measuring: .azure, scenario: verdict).environmentObject(i18n)
                try await snapshot(pane, name: "settings-\(fixture.rawValue)-\(dark ? "dark" : "light")",
                                   width: 660, fitHeight: true, dark: dark)
            }
        }
    }

    @Test("Sidebar row and popover for every Azure run failure", .enabled(if: enabled))
    func runFailures() async throws {
        let i18n = try englishI18n()
        for scenario in AzureRunScenario.allCases {
            let rig = PipelineRunnerQueueTests.Rig()
            defer { rig.cleanUp() }
            let project = rig.project("Checkout study")
            let state = scenario.state
            rig.runner._debugSetState(state, for: project.id)
            for dark in [false, true] {
                let label = "\(scenario.rawValue)-\(dark ? "dark" : "light")"
                let outline = SidebarOutlineController()
                outline.projectIndex = rig.index
                outline.i18n = i18n
                outline.pipelineRunner = rig.runner
                outline.liveData = rig.runner.liveData
                _ = outline.view
                outline.update(roots: OutlineTree.build(lenses: [], projects: rig.index.projects, folders: []),
                               // Unselected: a view bitmap cannot draw the vibrant selection
                               // material (it comes out black), so the row is shown at rest.
                               selection: [], activeTab: nil, lensesEnabled: false)
                try await snapshot(OutlineHost(controller: outline), name: label + "-sidebar",
                                   width: 290, height: 120, dark: dark)
                let popover = ProjectDiagnosticPopover(project: project, state: state,
                                                       liveData: rig.runner.liveData).environmentObject(i18n)
                try await snapshot(popover, name: label + "-popover", width: ProjectDiagnosticPopover.width,
                                   height: ProjectDiagnosticPopover.ceiling, fitHeight: true, dark: dark)
            }
            withExtendedLifetime(i18n) {}
        }
    }

    private func snapshot<V: View>(_ content: V, name: String, width: CGFloat, height: CGFloat = 900,
                                   fitHeight: Bool = false, dark: Bool) async throws {
        let host = NSHostingController(rootView: content
            .background(Color(nsColor: .windowBackgroundColor))
            .preferredColorScheme(dark ? .dark : .light))
        host.sizingOptions = fitHeight ? .preferredContentSize : []
        let size = NSSize(width: width, height: height)
        let window = NSWindow(contentRect: .init(origin: .zero, size: size),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.title = "Bristlenose Azure QA: " + name
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        window.contentViewController = host
        window.setContentSize(size)
        host.view.frame = NSRect(origin: .zero, size: size)
        // Off the visible screen: the owner's desktop is not this test's canvas.
        window.setFrameOrigin(NSPoint(x: -20000, y: -20000))
        window.makeKeyAndOrderFront(nil)
        defer { window.orderOut(nil); window.close() }
        try await Task.sleep(for: .milliseconds(150))
        host.view.layoutSubtreeIfNeeded()
        if fitHeight {
            let fitted = min(height, host.view.fittingSize.height)
            window.setContentSize(NSSize(width: width, height: fitted))
            host.view.layoutSubtreeIfNeeded()
        }
        host.view.displayIfNeeded()
        let rep = try #require(host.view.bitmapImageRepForCachingDisplay(in: host.view.bounds))
        host.view.cacheDisplay(in: host.view.bounds, to: rep)
        Attachment.record(try #require(rep.representation(using: .png, properties: [:])), named: name + ".png")
    }
}

private struct OutlineHost: NSViewControllerRepresentable {
    let controller: SidebarOutlineController
    func makeNSViewController(context: Context) -> SidebarOutlineController { controller }
    func updateNSViewController(_ controller: SidebarOutlineController, context: Context) {}
}
