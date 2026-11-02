import AppKit
import Foundation
import SwiftUI
import Testing
@testable import Bristlenose

/// The real sidebar controller, the real cell and the shipped locale files, drawing
/// the "Picking up Signals…" row. Not the running app: no window, no sidecar, no
/// bridge. It reads the same cell the outline draws, so what the row says, how tall
/// it is and what it looks like are measured on the native view and not on the
/// pure functions behind it. The picture is attached to the result bundle.
@MainActor
@Suite struct SignalsPreparingRowRenderTests {

    private func texts(in view: NSView) -> [String] {
        var out: [String] = []
        if let field = view as? NSTextField, !field.stringValue.isEmpty { out.append(field.stringValue) }
        // A shimmering status line is the shared SwiftUI ShimmerText in a hosting view.
        if let host = view as? NSHostingView<ShimmerText> { out.append(host.rootView.text) }
        for sub in view.subviews { out += texts(in: sub) }
        return out
    }

    private func hasShimmer(in view: NSView) -> Bool {
        if view is NSHostingView<ShimmerText> { return true }
        return view.subviews.contains { hasShimmer(in: $0) }
    }

    private func draw(preparing: Bool) throws -> (rowTexts: [String], height: CGFloat, png: Data?, hasShimmer: Bool) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        let studyDir = dir.appendingPathComponent("Study")
        try FileManager.default.createDirectory(at: studyDir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        index.addProject(name: "ikea research videos", path: studyDir.path)
        let project = try #require(index.projects.first)

        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")

        let controller = SidebarOutlineController()
        controller.projectIndex = index
        controller.i18n = i18n
        // The shimmer gate is pinned by SignalsPreparingTests; here it is set to the
        // state this test assumes, since the GitHub macOS runners have Reduce Motion
        // on and the real read then (rightly) hosts no ShimmerText.
        controller.shimmerEnvironment = { (animationOn: true, reduceMotion: false) }
        _ = controller.view
        controller.view.frame = NSRect(x: 0, y: 0, width: 240, height: 400)
        controller.preparingSignalsProjectID = preparing ? project.id : nil
        controller.update(
            roots: OutlineTree.build(lenses: LensItem.all, projects: index.projects, folders: index.folders),
            selection: [.project(project.id)],
            activeTab: nil,
            lensesEnabled: true
        )
        let outline = controller.outlineView
        outline.layoutSubtreeIfNeeded()
        let row = try #require((0..<outline.numberOfRows).first { r in
            (outline.item(atRow: r) as? OutlineNode)?.kind == .project(project.id)
        })
        let view = try #require(outline.view(atColumn: 0, row: row, makeIfNecessary: true))
        let height = outline.rect(ofRow: row).height
        view.frame = NSRect(x: 0, y: 0, width: 240, height: height)
        view.layoutSubtreeIfNeeded()
        var png: Data?
        if let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
            view.cacheDisplay(in: view.bounds, to: rep)
            png = rep.representation(using: .png, properties: [:])
        }
        withExtendedLifetime(i18n) {}
        return (texts(in: view), height, png, hasShimmer(in: view))
    }

    @Test func theRowSaysPickingUpSignalsUnderTheProjectNameAndIsTwoLines() throws {
        let preparing = try draw(preparing: true)
        let resting = try draw(preparing: false)
        if let png = preparing.png { Attachment.record(png, named: "row-picking-up-signals.png") }
        if let png = resting.png { Attachment.record(png, named: "row-resting.png") }
        Attachment.record(
            "preparing texts: \(preparing.rowTexts) height \(preparing.height); resting texts: \(resting.rowTexts) height \(resting.height)",
            named: "row-measurements.txt")

        #expect(preparing.rowTexts.contains("ikea research videos"))
        #expect(preparing.rowTexts.contains("Picking up Signals…"),
                "the native row did not say it: \(preparing.rowTexts)")
        #expect(!resting.rowTexts.contains("Picking up Signals…"))
        // The line shimmers: the status text is hosted in the shared ShimmerText, not a plain label.
        #expect(preparing.hasShimmer)
        #expect(!resting.hasShimmer)
        // Two lines, at the height of a row with any subtitle; the resting row with
        // nothing to say is the shorter single line.
        #expect(preparing.height == ProjectCellSpec.rowHeight(twoLine: true))
        #expect(resting.height == ProjectCellSpec.rowHeight(twoLine: false))
    }
}
