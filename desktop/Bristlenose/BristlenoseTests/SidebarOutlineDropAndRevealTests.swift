import AppKit
import Foundation
import Testing
import UniformTypeIdentifiers
@testable import Bristlenose

/// The AppKit sidebar's answers to a drop, and what it does with a row the
/// model selects or reveals, driven through the real `SidebarOutlineController`
/// (20 Oct 2026).
///
/// - R48: a Finder drag of files the pipeline can't ingest got a "+" pointer,
///   was accepted, and then vanished without a word.
/// - R53: a study the model selected (a new one, or a re-dropped known folder)
///   could land scrolled out of sight.
/// - R58: ⌘N's new study lost its icon while its name was typed: the reveal's
///   end skips the reload that rebuilds the cell while a rename is open.
/// - R53 (flash): the drop's 0.4 s acknowledgement never reached this sidebar.
/// - Add Files offered a `.md`: the panel's types match by conformance.
@MainActor
private final class OutlineRig {
    let tempDir: URL
    let index: ProjectIndex
    let controller = SidebarOutlineController()

    init() {
        tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-outline-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        index = ProjectIndex(fileURL: tempDir.appendingPathComponent("projects.json"))
        controller.projectIndex = index
        _ = controller.view
        controller.view.frame = NSRect(x: 0, y: 0, width: 240, height: 600)
    }

    var outlineView: NSOutlineView { controller.outlineView }

    func publish(selection: Set<SidebarSelection> = []) {
        controller.update(
            roots: OutlineTree.build(lenses: LensItem.all,
                                     projects: index.projects,
                                     folders: index.folders),
            selection: selection,
            activeTab: nil,
            lensesEnabled: true
        )
        controller.view.layoutSubtreeIfNeeded()
    }

    func row(of id: UUID) -> Int? {
        for r in 0..<outlineView.numberOfRows {
            if case .project(let pid)? = (outlineView.item(atRow: r) as? OutlineNode)?.kind, pid == id {
                return r
            }
        }
        return nil
    }

    func isVisible(_ id: UUID) -> Bool {
        guard let r = row(of: id) else { return false }
        return outlineView.visibleRect.contains(outlineView.rect(ofRow: r))
    }

    func cleanup() { try? FileManager.default.removeItem(at: tempDir) }
}

/// A Finder drag carrying `urls`, as `validateDrop` sees one.
private final class FakeDrag: NSObject, NSDraggingInfo {
    let pasteboard: NSPasteboard

    init(_ urls: [URL]) {
        pasteboard = NSPasteboard(name: NSPasteboard.Name("bn-test-drag-\(UUID().uuidString)"))
        pasteboard.clearContents()
        pasteboard.writeObjects(urls.map { $0 as NSURL })
    }

    var draggingPasteboard: NSPasteboard { pasteboard }
    var draggingDestinationWindow: NSWindow? { nil }
    var draggingSourceOperationMask: NSDragOperation { .copy }
    var draggingLocation: NSPoint { .zero }
    var draggedImageLocation: NSPoint { .zero }
    var draggedImage: NSImage? { nil }
    var draggingSource: Any? { nil }
    var draggingSequenceNumber: Int { 1 }
    func slideDraggedImage(to screenPoint: NSPoint) {}
    var draggingFormation: NSDraggingFormation = .default
    var animatesToDestination: Bool = false
    var numberOfValidItemsForDrop: Int = 0
    func enumerateDraggingItems(
        options enumOpts: NSDraggingItemEnumerationOptions = [],
        for view: NSView?,
        classes classArray: [AnyClass],
        searchOptions: [NSPasteboard.ReadingOptionKey: Any] = [:],
        using block: (NSDraggingItem, Int, UnsafeMutablePointer<ObjCBool>) -> Void
    ) {}
    var springLoadingHighlight: NSSpringLoadingHighlight { .none }
    func resetSpringLoading() {}

    func release() { pasteboard.releaseGlobally() }
}

@MainActor
@Suite("Sidebar drops and reveals")
struct SidebarOutlineDropAndRevealTests {

    // MARK: - R48: a drop of nothing ingestible is refused during the drag

    private func validate(_ rig: OutlineRig, _ urls: [URL], onto item: Any?) -> NSDragOperation {
        let drag = FakeDrag(urls)
        defer { drag.release() }
        return rig.controller.outlineView(
            rig.outlineView, validateDrop: drag,
            proposedItem: item, proposedChildIndex: NSOutlineViewDropOnItemIndex
        )
    }

    @Test func filesNothingCanIngestAreRefusedOnTheSidebar() {
        let rig = OutlineRig(); defer { rig.cleanup() }
        rig.publish()
        let pdf = rig.tempDir.appendingPathComponent("brief.pdf")
        let zip = rig.tempDir.appendingPathComponent("notes.zip")

        #expect(validate(rig, [pdf, zip], onto: nil) == [],
                "a drag the drop would discard showed the '+' pointer")
    }

    @Test func filesNothingCanIngestAreRefusedOnAStudy() {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let study = rig.index.addProject(name: "Study", path: rig.tempDir.path)
        rig.publish()
        let row = try! #require(rig.row(of: study.id))
        let item = rig.outlineView.item(atRow: row)
        let pdf = rig.tempDir.appendingPathComponent("brief.pdf")

        #expect(validate(rig, [pdf], onto: item) == [])
    }

    @Test func aRecordingOrAFolderIsStillTaken() {
        let rig = OutlineRig(); defer { rig.cleanup() }
        rig.publish()
        let video = rig.tempDir.appendingPathComponent("Session 1.MOV")
        let folder = URL(fileURLWithPath: rig.tempDir.appendingPathComponent("Study").path,
                         isDirectory: true)
        let pdf = rig.tempDir.appendingPathComponent("brief.pdf")

        #expect(validate(rig, [video], onto: nil) == .copy)
        #expect(validate(rig, [folder], onto: nil) == .copy)
        // One ingestible file is enough; the drop handlers filter the rest.
        #expect(validate(rig, [pdf, video], onto: nil) == .copy)
    }

    @Test func theAddFilesPanelOffersWhatTheDropAccepts() {
        let types = ContentView.addFilesContentTypes
        #expect(!types.isEmpty)
        for ext in ["mov", "mp4", "m4a", "wav", "vtt", "srt", "docx", "txt"] {
            let t = try! #require(UTType(filenameExtension: ext))
            #expect(types.contains { t.conforms(to: $0) }, "Add Files greys out .\(ext)")
        }
        for ext in ["pdf", "zip", "key", "png"] {
            let t = try! #require(UTType(filenameExtension: ext))
            #expect(!types.contains { t.conforms(to: $0) }, "Add Files offers .\(ext), which is then dropped")
        }
    }

    @Test func theAddFilesPanelGreysOutWhatOnlyConformsToAnAcceptedType() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let delegate = ContentView.AddFilesPanelFilter.shared
        let panel = NSOpenPanel()
        func enabled(_ name: String) -> Bool {
            delegate.panel(panel, shouldEnable: rig.tempDir.appendingPathComponent(name))
        }
        let md = UTType(filenameExtension: "md")
        try #require(ContentView.addFilesContentTypes.contains { md?.conforms(to: $0) == true },
                     "the types alone no longer let a .md through; this test is moot")

        #expect(!enabled("notes.md"), "Add Files offers a .md, which is then dropped")
        #expect(!enabled("notes.markdown"))
        for name in ["interview.txt", "interview.vtt", "call.mov", "call.m4a", "brief.docx"] {
            #expect(enabled(name), "Add Files greys out \(name)")
        }
        let folder = rig.tempDir.appendingPathComponent("Round 2", isDirectory: false)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        #expect(enabled("Round 2"), "a folder can't be opened to pick from")
    }

    // MARK: - R53: the drop's acknowledgement flash

    /// The row as the table shows it: made now if a reload has not laid it out.
    private func targetMarked(_ rig: OutlineRig, _ id: UUID) -> Bool {
        guard let r = rig.row(of: id),
              let rowView = rig.outlineView.rowView(atRow: r, makeIfNecessary: true) else { return false }
        return rowView.isTargetForDropOperation
    }

    @Test func aDropOnAKnownStudyFlashesItsRowThroughAReload() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let a = rig.index.addProject(name: "A", path: ""), b = rig.index.addProject(name: "B", path: "")
        rig.publish()

        rig.controller.setFlash(projectID: a.id)
        #expect(targetMarked(rig, a.id), "the dropped-on study did not flash")
        #expect(!targetMarked(rig, b.id))

        rig.publish(selection: [.project(a.id)])   // a progress tick reloads mid-flash
        #expect(targetMarked(rig, a.id), "a reload during the flash ended it")

        rig.controller.setFlash(projectID: nil)
        #expect(!targetMarked(rig, a.id), "the flash did not end")
    }

    @Test func aFlashedStudyScrolledIntoViewArrivesMarked() throws {
        let rig = scrolledRig(studies: 40); defer { rig.cleanup() }
        let top = try #require(rig.index.projects.first(where: { $0.name == "Study 39" }))
        try #require(!rig.isVisible(top.id))
        rig.controller.setFlash(projectID: top.id)

        rig.publish(selection: [.project(top.id)])   // the reveal scrolls it in

        #expect(rig.isVisible(top.id))
        #expect(targetMarked(rig, top.id))
    }

    // MARK: - R53: a study the model selects is brought into view

    private func scrolledRig(studies n: Int) -> OutlineRig {
        let rig = OutlineRig()
        for i in 0..<n { rig.index.addProject(name: "Study \(i)", path: "") }
        rig.publish()
        rig.outlineView.scrollRowToVisible(rig.outlineView.numberOfRows - 1)
        return rig
    }

    @Test func aNewStudyTheModelSelectsIsScrolledIntoView() throws {
        let rig = scrolledRig(studies: 40); defer { rig.cleanup() }
        // A drop inserts at the top of its scope, as `addProject` does.
        let new = rig.index.addProject(name: "Dropped", path: "")
        rig.index.consumeIconReveal(new.id)
        rig.publish()
        try #require(!rig.isVisible(new.id), "the fixture should start with it out of sight")

        rig.publish(selection: [.project(new.id)])

        #expect(rig.isVisible(new.id), "the new study was selected out of sight")
    }

    @Test func aKnownStudyReselectedByTheModelIsScrolledIntoView() throws {
        let rig = scrolledRig(studies: 40); defer { rig.cleanup() }
        let first = try #require(rig.index.projects.first(where: { $0.name == "Study 39" }))
        try #require(!rig.isVisible(first.id), "the fixture should start with it out of sight")

        rig.publish(selection: [.project(first.id)])

        #expect(rig.isVisible(first.id))
    }

    /// A republish whose selection hasn't changed (a progress tick) must not
    /// pull the list back to the selected row after the researcher scrolled away.
    @Test func anUnchangedSelectionDoesNotMoveTheList() throws {
        let rig = scrolledRig(studies: 40); defer { rig.cleanup() }
        let top = try #require(rig.index.projects.first(where: { $0.name == "Study 39" }))
        rig.publish(selection: [.project(top.id)])
        rig.outlineView.scrollRowToVisible(rig.outlineView.numberOfRows - 1)
        let before = rig.outlineView.visibleRect

        rig.publish(selection: [.project(top.id)])

        #expect(rig.outlineView.visibleRect == before)
    }

    /// The researcher's own click comes back as a republish of the same
    /// selection; it is theirs, so the list stays where they left it.
    @Test func theResearchersOwnSelectionDoesNotMoveTheList() throws {
        let rig = scrolledRig(studies: 40); defer { rig.cleanup() }
        let last = rig.outlineView.numberOfRows - 1
        var echoed: Set<SidebarSelection> = []
        rig.controller.onSelectionChange = { echoed = $0 }
        rig.outlineView.selectRowIndexes(IndexSet(integer: last), byExtendingSelection: false)
        try #require(!echoed.isEmpty)
        rig.outlineView.scrollRowToVisible(0)
        let before = rig.outlineView.visibleRect

        rig.publish(selection: echoed)

        #expect(rig.outlineView.visibleRect == before)
    }

    // MARK: - R58: ⌘N's icon stays visible while the name is typed

    // A disabled trait, not a `#require`: a failed precondition records a
    // failure, and the GitHub macOS runners have Reduce Motion on, so the
    // suite went red there on a test with nothing to test.
    @Test(.disabled(if: NSWorkspace.shared.accessibilityDisplayShouldReduceMotion,
                    "Reduce Motion skips the reveal, so there is nothing to test"))
    func theNewStudysIconIsVisibleWhileItsNameIsTyped() async throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        // The rename needs a window to hold its field editor.
        let window = NSWindow(contentRect: NSRect(x: -20_000, y: -20_000, width: 240, height: 600),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = rig.controller.view
        defer { window.close() }

        let new = rig.index.addProject(name: "Untitled", path: "")
        try #require(rig.index.pendingIconReveal == new.id, "random icons are off in this host")
        rig.index.pendingRename = new.id          // as ⌘N does
        rig.publish(selection: [.project(new.id)])
        let row = try #require(rig.row(of: new.id))
        let cell = try #require(rig.outlineView.view(atColumn: 0, row: row, makeIfNecessary: false)
                                as? NSTableCellView)
        try #require(cell.textField?.currentEditor() != nil, "the rename did not open")
        try #require(cell.imageView?.alphaValue == 0, "the reveal took its static fallback")

        // The flip runs about two seconds; the trigger is consumed when it ends.
        // Each of its steps is a main-actor sleep, so in the full suite on a
        // 4-core guest it took longer than a 6 s ceiling (20 Oct 2026). The
        // loop returns as soon as the flip ends.
        let deadline = Date().addingTimeInterval(30)
        while rig.index.pendingIconReveal != nil, Date() < deadline {
            try await Task.sleep(for: .milliseconds(50))
        }
        try #require(rig.index.pendingIconReveal == nil, "the reveal never finished")
        try #require(cell.textField?.currentEditor() != nil, "the rename closed under the test")

        let shown = try #require(rig.outlineView.view(atColumn: 0, row: row, makeIfNecessary: false)
                                 as? NSTableCellView)
        #expect(shown.imageView?.alphaValue == 1, "the icon slot is empty while the name is typed")
    }

    // MARK: - R47: a study that can't take files refuses the drag here too

    /// The AppKit half of the rule `StudyFinderDropTests` pins for the SwiftUI
    /// row: no highlight, the not-allowed pointer, the files spring back.
    @Test func aBusyStudyRefusesTheDrag() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let runner = PipelineRunner()            // the controller holds it weakly
        rig.controller.pipelineRunner = runner
        let study = rig.index.addProject(name: "Study", path: rig.tempDir.path)
        rig.publish()
        let item = rig.outlineView.item(atRow: try #require(rig.row(of: study.id)))
        let video = rig.tempDir.appendingPathComponent("Session 1.MOV")
        try #require(validate(rig, [video], onto: item) == .copy)

        for state in StudyFinderDropTests.busy {
            runner._debugSetState(state, for: study.id)
            #expect(validate(rig, [video], onto: item) == [], "\(state) took the drag")
        }
    }

    /// Decision #100 (22 Oct 2026): a study being analysed takes the drag,
    /// which 5598bd39 had refused here.
    @Test func aStudyBeingAnalysedTakesTheDrag() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let runner = PipelineRunner()            // the controller holds it weakly
        rig.controller.pipelineRunner = runner
        let study = rig.index.addProject(name: "Study", path: rig.tempDir.path)
        rig.publish()
        let item = rig.outlineView.item(atRow: try #require(rig.row(of: study.id)))
        let video = rig.tempDir.appendingPathComponent("Session 1.MOV")

        for state in StudyFinderDropTests.analysing {
            runner._debugSetState(state, for: study.id)
            #expect(validate(rig, [video], onto: item) == .copy, "\(state) refused the drag")
        }
    }

    /// RE#20 #110 follow-up: a study whose folder `run` refuses by name (the
    /// home folder) refuses the drag, as a failed one does.
    @Test func aStudyInTheHomeFolderRefusesTheDrag() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let runner = PipelineRunner()
        rig.controller.pipelineRunner = runner
        let study = rig.index.addProject(name: "Home", path: UserHome.path)
        rig.publish()
        let item = rig.outlineView.item(atRow: try #require(rig.row(of: study.id)))
        let video = rig.tempDir.appendingPathComponent("Session 1.MOV")

        runner._debugSetState(.idle, for: study.id)
        #expect(validate(rig, [video], onto: item) == [], "the home folder took the drag")
    }

    // MARK: - R56: the other rows keep updating while a name is typed

    private func cell(_ rig: OutlineRig, _ id: UUID) -> NSTableCellView? {
        guard let r = rig.row(of: id) else { return nil }
        return rig.outlineView.view(atColumn: 0, row: r, makeIfNecessary: false) as? NSTableCellView
    }

    /// A rig with study A's name field open and half typed, and study B beside it.
    private func renaming() throws -> (OutlineRig, NSWindow, a: UUID, b: UUID) {
        let rig = OutlineRig()
        let window = NSWindow(contentRect: NSRect(x: -20_000, y: -20_000, width: 240, height: 600),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = rig.controller.view
        let a = rig.index.addProject(name: "A", path: ""), b = rig.index.addProject(name: "B", path: "")
        rig.index.consumeIconReveal(a.id)
        rig.index.consumeIconReveal(b.id)
        rig.index.pendingRename = a.id
        rig.publish(selection: [.project(a.id)])
        let editor = try #require(cell(rig, a.id)?.textField?.currentEditor(), "the rename did not open")
        editor.string = "Half-typ"
        return (rig, window, a.id, b.id)
    }

    @Test func anotherStudyKeepsUpdatingWhileANameIsTyped() throws {
        let (rig, window, a, b) = try renaming()
        defer { window.close(); rig.cleanup() }
        let field = try #require(cell(rig, a))

        rig.index.renameProject(id: b, newName: "B, changed elsewhere")
        rig.publish(selection: [.project(a)])

        #expect(cell(rig, b)?.textField?.stringValue == "B, changed elsewhere",
                "the other study's row froze while a name was typed")
        #expect(cell(rig, a) === field, "the row being named was rebuilt")
        #expect(field.textField?.currentEditor()?.string == "Half-typ", "the typing was lost")
    }

    /// The symptom itself: a study starts its run while another's name is
    /// being typed. Its row gains the run's subtitle and grows to two lines,
    /// and the typing survives.
    @Test func aRunStartingWhileANameIsTypedShowsOnItsRow() throws {
        let rig = OutlineRig(); defer { rig.cleanup() }
        let window = NSWindow(contentRect: NSRect(x: -20_000, y: -20_000, width: 240, height: 600),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = rig.controller.view
        defer { window.close() }
        let runner = PipelineRunner(), live = PipelineLiveData(), i18n = I18n()
        rig.controller.pipelineRunner = runner   // all three are held weakly
        rig.controller.liveData = live
        rig.controller.i18n = i18n
        let a = rig.index.addProject(name: "A", path: "")
        let b = rig.index.addProject(name: "B", path: rig.tempDir.path)
        rig.index.consumeIconReveal(a.id)
        rig.index.consumeIconReveal(b.id)
        rig.index.pendingRename = a.id
        rig.publish(selection: [.project(a.id)])
        let field = try #require(cell(rig, a.id))
        let editor = try #require(field.textField?.currentEditor(), "the rename did not open")
        editor.string = "Half-typ"
        let bRow = try #require(rig.row(of: b.id))
        let before = rig.outlineView.rect(ofRow: bRow).height

        runner._debugSetState(.running, for: b.id)
        defer { runner._debugSetState(.idle, for: b.id) }   // let the sleep assertion go
        rig.publish(selection: [.project(a.id)])

        #expect(rig.outlineView.rect(ofRow: bRow).height > before,
                "the running study's row did not gain its subtitle while a name was typed")
        #expect(cell(rig, a.id) === field, "the row being named was rebuilt")
        #expect(field.textField?.currentEditor()?.string == "Half-typ", "the typing was lost")
    }

    /// Rows that come or go would move under the field, so the list waits for
    /// the name, as it did before.
    @Test func aStudyAddedWhileANameIsTypedWaitsForTheName() throws {
        let (rig, window, a, _) = try renaming()
        defer { window.close(); rig.cleanup() }
        let field = try #require(cell(rig, a))
        let rows = rig.outlineView.numberOfRows

        let c = rig.index.addProject(name: "C", path: "")
        rig.index.consumeIconReveal(c.id)
        rig.publish(selection: [.project(a)])

        #expect(rig.outlineView.numberOfRows == rows)
        #expect(cell(rig, a) === field)
        #expect(field.textField?.currentEditor()?.string == "Half-typ", "the typing was lost")
    }
}
