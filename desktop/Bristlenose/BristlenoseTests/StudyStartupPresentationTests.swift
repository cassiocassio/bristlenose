import AppKit
import SwiftUI
import Testing
@testable import Bristlenose

/// Native pixels from the actual product views, using the existing window/
/// bitmap-attachment harness pattern. No study, server or provider is opened.
/// Run separately with TEST_RUNNER_BN_STARTUP_VISUAL=1 and only this suite.
/// TEST_RUNNER_BN_STARTUP_VISUAL_HOLD=1 exposes two real windows for CUA review;
/// use a QA bundle ID and attach only after test-host startup (never launch a
/// second normal app instance). View bitmaps cannot certify vibrant selection.
@MainActor
@Suite("Startup refusal native presentation", .serialized)
struct StudyStartupPresentationTests {
    @Test("Render approved refusal surfaces in light and dark appearances",
          .enabled(if: ProcessInfo.processInfo.environment["BN_STARTUP_VISUAL"] == "1"))
    func nativeSurfaces() async throws {
        let rig = PipelineRunnerQueueTests.Rig()
        defer { rig.cleanUp() }
        let project = rig.project("Checkout study")
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        #expect(i18n.t("desktop.boot.retry") == "Retry")
        #expect(i18n.t("desktop.pipeline.diagnostic.action.copy") == "Copy details")
        let fleet = ServeFleet(makeManager: { ServeManager(resolvedMode: .success(.external(port: 9998))) })
        let cases: [(String, StudyStartupRefusal)] = [
            ("named", .init(reason: .foreign, machineName: "Cassio’s Mac Studio",
                             startedAt: ISO8601DateFormatter().string(from: Date().addingTimeInterval(-3600)))),
            ("missing-facts", .init(reason: .foreign, machineName: nil, startedAt: nil)),
            ("unverified", .unverified),
            ("long-name", .init(reason: .foreign,
                                 machineName: "Cassio’s Mac Studio for research and design at the office", startedAt: nil))
        ]
        for dark in [false, true] {
            for (name, refusal) in cases {
                let label = "\(name)-\(dark ? "dark" : "light")"
                let boot = BootView(phase: .failed(message: refusal.failureMessage,
                                                   retry: {}, sendFeedback: {}))
                    .environmentObject(i18n).environmentObject(fleet)
                try await snapshot(boot, name: label + "-pane", size: .init(width: 720, height: 440), dark: dark)
                let popover = ProjectDiagnosticPopover(project: project,
                    state: .failed(refusal.failureMessage, category: .unknown),
                    liveData: rig.runner.liveData).environmentObject(i18n)
                try await snapshot(popover, name: label + "-popover",
                                   size: .init(width: ProjectDiagnosticPopover.width, height: ProjectDiagnosticPopover.ceiling), dark: dark)
                let row = ProjectRow(project: project, isRenaming: .constant(false),
                    liveData: rig.runner.liveData, startupRefusal: refusal,
                    onRename: { _ in }, onShowInFinder: {}, onDelete: {})
                    .environmentObject(i18n).environmentObject(rig.runner!)
                    .environmentObject(rig.index)
                    .padding(8)
                try await snapshot(row, name: label + "-sidebar", size: .init(width: 290, height: 76), dark: dark)
                let outline = SidebarOutlineController()
                outline.projectIndex = rig.index
                outline.i18n = i18n
                outline.pipelineRunner = rig.runner
                outline.liveData = rig.runner.liveData
                outline.startupRefusals = [project.id: refusal]
                _ = outline.view
                outline.update(roots: OutlineTree.build(lenses: [], projects: rig.index.projects, folders: []),
                               selection: [.project(project.id)], activeTab: nil, lensesEnabled: false)
                try await snapshot(StartupOutlineView(controller: outline), name: label + "-appkit-sidebar",
                                   size: .init(width: 290, height: 180), dark: dark)
            }
        }
        let cover = RunCoverPane(cover: .failed(sentence: StudyStartupRefusal.unverified.failureMessage,
                                               rawCause: nil, category: .unknown, summary: nil),
                                 project: project, liveData: rig.runner.liveData,
                                 onAnalyse: {}, onRetryStartup: {}).environmentObject(i18n)
        try await snapshot(cover, name: "unverified-narrow-run-cover", size: .init(width: 460, height: 440), dark: false)
    }

    private func snapshot<V: View>(_ content: V, name: String, size: NSSize, dark: Bool) async throws {
        let host = NSHostingController(rootView: content
            .background(Color(nsColor: .windowBackgroundColor))
            .preferredColorScheme(dark ? .dark : .light))
        let isPopover = name.hasSuffix("-popover")
        host.sizingOptions = isPopover ? .preferredContentSize : []
        let window = NSWindow(contentRect: .init(origin: .zero, size: size),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.title = "Bristlenose startup QA: " + name
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        window.contentViewController = host
        window.setContentSize(size)
        host.view.frame = NSRect(origin: .zero, size: size)
        window.makeKeyAndOrderFront(nil)
        defer { window.orderOut(nil); window.close() }
        try await Task.sleep(for: .milliseconds(150))
        host.view.layoutSubtreeIfNeeded()
        if isPopover {
            let height = min(size.height, host.view.fittingSize.height)
            #expect(height > 100, "Refusal body must contribute to the popover's intrinsic height")
            window.setContentSize(NSSize(width: size.width, height: height))
            host.view.layoutSubtreeIfNeeded()
        }
        host.view.displayIfNeeded()
        let rep = try #require(host.view.bitmapImageRepForCachingDisplay(in: host.view.bounds))
        host.view.cacheDisplay(in: host.view.bounds, to: rep)
        let png = try #require(rep.representation(using: .png, properties: [:]))
        Attachment.record(png, named: name + ".png")
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("bn-startup-native-visual")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try png.write(to: directory.appendingPathComponent(name + ".png"))
        // AppKit's vibrant selected-row material cannot be certified by a
        // view bitmap. Explicit visual runs may hold these real windows for
        // window-server screenshot inspection; ordinary test runs never wait.
        if ProcessInfo.processInfo.environment["BN_STARTUP_VISUAL_HOLD"] == "1",
           ["named-light-appkit-sidebar", "unverified-dark-appkit-sidebar"].contains(name) {
            try await Task.sleep(for: .seconds(30))
        }
    }
}

private struct StartupOutlineView: NSViewControllerRepresentable {
    let controller: SidebarOutlineController
    func makeNSViewController(context: Context) -> SidebarOutlineController { controller }
    func updateNSViewController(_ controller: SidebarOutlineController, context: Context) {}
}
