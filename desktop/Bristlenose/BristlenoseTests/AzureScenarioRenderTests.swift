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

    // MARK: - Proposals (docs/mockups/azure-d4-and-deployment.html)
    //
    // Not shipped: these draw the real views with PROPOSED words, for the owner to
    // decide on. D4 swaps the status label through a patched copy of the locale
    // files; the deployment fix injects the state a fixed categoriser would reach.
    // Opt-in with `TEST_RUNNER_BN_AZURE_PROPOSAL_VISUAL=1`.

    private static let proposalsEnabled =
        ProcessInfo.processInfo.environment["BN_AZURE_PROPOSAL_VISUAL"] == "1"

    /// English, with `desktop.llmSettings.status.invalid` reading `label`.
    private func i18nWithInvalidLabel(_ label: String) throws -> I18n {
        let source = try #require(I18n.findLocalesDirectory())
        let copy = FileManager.default.temporaryDirectory
            .appendingPathComponent("azure-d4-locales-\(UUID().uuidString)")
        try FileManager.default.copyItem(at: source, to: copy)
        let file = copy.appendingPathComponent("en/desktop.json")
        var root = try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as? [String: Any])
        var settings = try #require(root["llmSettings"] as? [String: Any])
        var status = try #require(settings["status"] as? [String: Any])
        #expect(status["invalid"] as? String == "Invalid key")
        status["invalid"] = label
        settings["status"] = status
        root["llmSettings"] = settings
        try JSONSerialization.data(withJSONObject: root).write(to: file)
        let i18n = I18n()
        i18n.configure(localesDirectory: copy)
        i18n.setLocale("en")
        #expect(i18n.t("desktop.llmSettings.status.invalid") == label)
        return i18n
    }

    @Test("D4: the Azure status label reads Not connected", .enabled(if: proposalsEnabled))
    func d4Label() async throws {
        // Today and proposed in one run, so nothing but the label differs between them.
        let today = try englishI18n()
        let proposed = try i18nWithInvalidLabel("Not connected")
        let cases: [AzureScenarioFixture] = [.keyRejected, .deploymentNotFound, .wrongURLPasted,
                                             .noScheme, .unreachable]
        for fixture in cases {
            let verdict = await fixture.verdict()
            for dark in [false, true] {
                for (stage, i18n) in [("today", today), ("d4", proposed)] {
                    let pane = LLMSettingsView(measuring: .azure, scenario: verdict).environmentObject(i18n)
                    try await snapshot(pane, name: "\(stage)-\(fixture.rawValue)-\(dark ? "dark" : "light")",
                                       width: 660, fitHeight: true, dark: dark)
                }
            }
        }
    }

    @Test("Wrong deployment: the run says what is wrong", .enabled(if: proposalsEnabled))
    func wrongDeployment() async throws {
        let i18n = try englishI18n()
        let options: [(String, PipelineState)] = [
            ("deploy-today", AzureRunScenario.refusedDeployment.state),
            // A: the categoriser matches the wrapped preflight line; shipped words only.
            ("deploy-a", .failed(FailureMessage.failure(for: .modelUnavailable, provider: .azure),
                                 category: .modelUnavailable)),
            // B: an Azure leaf at FailureMessage's extension point, sentence S2
            // (docs/design-azure-connection.md §9); a new string in 21 locales.
            ("deploy-b", .failed(.passthrough(
                "No deployment named “research-gpt41mini” on this resource. Key and endpoint are fine; check the name."),
                                 category: .modelUnavailable)),
        ]
        for (name, state) in options {
            let rig = PipelineRunnerQueueTests.Rig()
            defer { rig.cleanUp() }
            let project = rig.project("Checkout study")
            rig.runner._debugSetState(state, for: project.id)
            for dark in [false, true] {
                let label = "\(name)-\(dark ? "dark" : "light")"
                let outline = SidebarOutlineController()
                outline.projectIndex = rig.index
                outline.i18n = i18n
                outline.pipelineRunner = rig.runner
                outline.liveData = rig.runner.liveData
                _ = outline.view
                outline.update(roots: OutlineTree.build(lenses: [], projects: rig.index.projects, folders: []),
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
