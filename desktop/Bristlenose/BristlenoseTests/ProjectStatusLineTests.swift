import AppKit
import Foundation
import SwiftUI
import Testing
@testable import Bristlenose

/// Every kind of project status line draws its text from the same place.
///
/// Read off the pixels, not off the frames: a stretched view's frame starts where
/// it was pinned whether or not the text inside it does. On 16 Nov 2026 the
/// shimmering line ("Screens · 2 of 3") sat centred under the project name with
/// a frame that was exactly right.
@MainActor
@Suite struct ProjectStatusLineTests {

    private static let text = "Screens · 2 of 3"
    private static let leading: CGFloat = 12
    private static let width: CGFloat = 240

    /// Each kind, stretched to the full width beside a plain label of the same
    /// text and font: where the status line's ink starts, less where the
    /// label's does, in points.
    private func inkOffset(_ kind: ProjectStatusLine.Kind, named name: String) throws -> CGFloat {
        let reference = NSTextField(labelWithString: Self.text)
        reference.font = ProjectCellSpec.subtitleFont
        reference.textColor = .secondaryLabelColor
        reference.translatesAutoresizingMaskIntoConstraints = false
        let status = ProjectStatusLine.make(text: Self.text, kind: kind)

        let container = NSView(frame: NSRect(x: 0, y: 0, width: Self.width, height: 48))
        container.addSubview(reference)
        container.addSubview(status)
        NSLayoutConstraint.activate([
            reference.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: Self.leading),
            reference.topAnchor.constraint(equalTo: container.topAnchor, constant: 4),
            // The stretching case: pinned at both ends, as a row with nothing in
            // its trailing slot pins it.
            status.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: Self.leading),
            status.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -4),
            status.topAnchor.constraint(equalTo: reference.bottomAnchor, constant: 4),
        ])
        // In a window, with a forced appearance: SwiftUI content in a hosting
        // view does not draw outside one.
        let window = NSWindow(contentRect: container.frame, styleMask: [.borderless],
                              backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .aqua)
        window.contentView = container
        container.layoutSubtreeIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
        container.layoutSubtreeIfNeeded()

        let rep = try #require(container.bitmapImageRepForCachingDisplay(in: container.bounds))
        container.cacheDisplay(in: container.bounds, to: rep)
        if let png = rep.representation(using: .png, properties: [:]) {
            Attachment.record(png, named: "status-line-\(name).png")
        }
        let scale = CGFloat(rep.pixelsWide) / container.bounds.width
        let referenceInk = try #require(firstInkColumn(rep, band: reference.frame, in: container, scale: scale),
                                        "the reference label drew nothing")
        let statusInk = try #require(firstInkColumn(rep, band: status.frame, in: container, scale: scale),
                                     "the \(name) status line drew nothing")
        // The line really was stretched. Without this the check is hollow: a
        // hosting view whose content has a maximum width refuses the stretch
        // (its own required max-size constraint fights the row's trailing pin,
        // and which one loses is not ours to choose), and a view that never
        // stretched has nowhere to centre its text.
        #expect(status.frame.maxX >= Self.width - 4 - 0.5,
                "the \(name) status line did not take the width it was given: \(status.frame)")
        window.close()
        return CGFloat(statusInk - referenceInk) / scale
    }

    /// The leftmost pixel column with any ink in it, within a view's rows (and
    /// from `minX` rightwards, to step over a row's icon).
    private func firstInkColumn(_ rep: NSBitmapImageRep, band: NSRect, in container: NSView,
                                scale: CGFloat, from minX: CGFloat = 0) -> Int? {
        // Bitmap rows run top-down; a non-flipped view's frame runs bottom-up.
        let top = container.isFlipped ? band.minY : container.bounds.height - band.maxY
        let rows = Int((top * scale).rounded(.down))..<Int(((top + band.height) * scale).rounded(.up))
        for x in Int(minX * scale)..<rep.pixelsWide {
            for y in rows where y >= 0 && y < rep.pixelsHigh {
                if let colour = rep.colorAt(x: x, y: y), colour.alphaComponent > 0.25 { return x }
            }
        }
        return nil
    }

    /// The real controller and the real cell, with a row that is running: the
    /// status line's ink starts under the project name's.
    @Test func aRunningRowsStatusStartsUnderTheProjectName() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        let studyDir = dir.appendingPathComponent("Study")
        try FileManager.default.createDirectory(at: studyDir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        index.addProject(name: "again", path: studyDir.path)
        let project = try #require(index.projects.first)

        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")

        let controller = SidebarOutlineController()
        controller.projectIndex = index
        controller.i18n = i18n
        controller.shimmerEnvironment = { (animationOn: true, reduceMotion: false) }
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: Self.width, height: 400),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .aqua)
        window.contentViewController = controller
        window.setContentSize(NSSize(width: Self.width, height: 400))
        controller.preparingSignalsProjectID = project.id
        controller.update(
            roots: OutlineTree.build(lenses: LensItem.all, projects: index.projects, folders: index.folders),
            selection: [],
            activeTab: nil,
            lensesEnabled: true
        )
        let outline = controller.outlineView
        outline.layoutSubtreeIfNeeded()
        let row = try #require((0..<outline.numberOfRows).first { r in
            (outline.item(atRow: r) as? OutlineNode)?.kind == .project(project.id)
        })
        let cell = try #require(outline.view(atColumn: 0, row: row, makeIfNecessary: true) as? NSTableCellView)
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
        cell.layoutSubtreeIfNeeded()
        let name = try #require(cell.textField)
        let status = try #require(cell.subviews.first { $0 is NSHostingView<ShimmerText> },
                                  "the running row hosts no shimmering status line")

        let rep = try #require(cell.bitmapImageRepForCachingDisplay(in: cell.bounds))
        cell.cacheDisplay(in: cell.bounds, to: rep)
        if let png = rep.representation(using: .png, properties: [:]) {
            Attachment.record(png, named: "running-row.png")
        }
        let scale = CGFloat(rep.pixelsWide) / cell.bounds.width
        let nameInk = try #require(firstInkColumn(rep, band: name.frame, in: cell, scale: scale,
                                                  from: name.frame.minX))
        let statusInk = try #require(firstInkColumn(rep, band: status.frame, in: cell, scale: scale,
                                                    from: name.frame.minX))
        withExtendedLifetime(i18n) {}
        window.close()
        // Two fonts and two first letters, so side bearings differ by a point or so.
        // Centred, the line starts tens of points in.
        #expect(abs(CGFloat(statusInk - nameInk) / scale) <= 2,
                "status ink at \(CGFloat(statusInk) / scale)pt, name ink at \(CGFloat(nameInk) / scale)pt")
    }

    @Test func aPlainLineStartsWhereALabelDoes() throws {
        #expect(abs(try inkOffset(.plain, named: "plain")) <= 0.5)
    }

    @Test func aShimmeringLineStartsWhereALabelDoesWhenStretched() throws {
        #expect(abs(try inkOffset(.shimmer, named: "shimmer")) <= 0.5)
    }

    @Test func aButtonLineStartsWhereALabelDoesWhenStretched() throws {
        let button = NSButton(title: Self.text, target: nil, action: nil)
        #expect(abs(try inkOffset(.button(button), named: "button")) <= 0.5)
    }
}
