import Foundation
import Testing

@testable import Bristlenose

/// The routing rules that replaced seventeen `NotificationCenter` broadcasts.
///
/// What is worth pinning here is the pair of decisions that a plain
/// "route everything to the key window" refactor gets wrong, and that no
/// compiler catches:
///
/// 1. With **no project window frontmost**, ⌘N must still create a project.
///    Route-to-key-window alone dims it, and the user cannot make a project at
///    all — the failure this taxonomy exists to prevent
///    (`docs/design-workspace.md` §"P1's taxonomy").
/// 2. The staged follow-through is genuinely **one-shot**, so the window opened
///    to receive it doesn't hand the same new project to a second window.
@MainActor
@Suite("Window command routing")
struct WindowCommandTests {

    private static func makeTempIndex() -> (ProjectIndex, URL) {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: tempDir.appendingPathComponent("projects.json"))
        return (index, tempDir)
    }

    private static func cleanup(_ tempDir: URL) {
        try? FileManager.default.removeItem(at: tempDir)
    }

    // MARK: - Enablement

    @Test("New Project and New Folder survive having no window")
    func newItemsNeverDim() {
        #expect(WindowCommand.newProject.isEnabled(hasKeyWindow: false))
        #expect(WindowCommand.newFolder.isEnabled(hasKeyWindow: false))
    }

    @Test("everything that needs a selection dims without one")
    func selectionCommandsDimWithoutAWindow() {
        // Not exhaustive by construction — `hasAppLevelFallback` defaults to
        // false, so a command added later dims unless it opts in. These are the
        // ones a reader is most likely to assume are app-global.
        let needsAWindow: [WindowCommand] = [
            .addFiles, .renameProject, .renameFolder, .deleteFolder,
            .moveProject(toFolder: nil), .revealTranscripts, .locateProject,
            .stopProject, .removeFromSidebar, .showAIConsent, .showMiro,
            .showWelcome, .showSessionsSwitcher,
        ]
        for command in needsAWindow {
            #expect(!command.isEnabled(hasKeyWindow: false), "\(command) should dim")
            #expect(command.isEnabled(hasKeyWindow: true), "\(command) should enable")
        }
    }

    // MARK: - The app-level fallback

    @Test("New Project with no window still creates the project")
    func fallbackCreatesProject() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        NewItemFallback.createProject(in: index, named: "New Project")

        #expect(index.projects.count == 1)
        let created = try! #require(index.projects.first)
        // Both batons, or the window that opens shows the project unselected
        // and un-renamed — which reads as ⌘N having half-worked.
        #expect(index.pendingSelection == .project(created.id))
        #expect(index.pendingRename == created.id)
    }

    @Test("New Folder with no window still creates the folder")
    func fallbackCreatesFolder() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        NewItemFallback.createFolder(in: index, named: "New Folder")

        #expect(index.folders.count == 1)
        let created = try! #require(index.folders.first)
        #expect(index.pendingSelection == .folder(created.id))
        #expect(index.pendingRename == created.id)
    }

    @Test("the staged selection is taken once, not once per window")
    func pendingSelectionIsOneShot() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        NewItemFallback.createProject(in: index, named: "New Project")

        let first = index.consumePendingSelection()
        let second = index.consumePendingSelection()

        #expect(first != nil)
        #expect(second == nil, "a second window must not also claim it")
    }

    // MARK: - The sink

    @Test("sinks compare by window, not by closure")
    func sinkIdentityIsTheWindow() {
        let windowA = UUID()
        let windowB = UUID()

        // Two body passes of the same window build two different closures. The
        // menu must read that as "same window", or every re-render looks like
        // the front window changed.
        #expect(WindowCommandSink(windowID: windowA, role: .master, perform: { _ in })
                == WindowCommandSink(windowID: windowA, role: .master, perform: { _ in }))
        #expect(WindowCommandSink(windowID: windowA, role: .master, perform: { _ in })
                != WindowCommandSink(windowID: windowB, role: .master, perform: { _ in }))
    }

    @Test("a command reaches the sink it was handed to")
    func sinkDeliversTheCommand() {
        var received: [WindowCommand] = []
        let sink = WindowCommandSink(windowID: UUID(), role: .master) { received.append($0) }

        sink.perform(.renameProject)
        sink.perform(.moveProject(toFolder: nil))

        #expect(received == [.renameProject, .moveProject(toFolder: nil)])
    }
}


// MARK: - What a child window may not do

// A child holds a lens, not a project. Every command that acts on *which study*
// dims, which is the same statement the missing project list makes — in the
// place a Mac user looks when a click does nothing.
@Suite("Study-axis commands dim in a child")
struct ChildCommandGateTests {

    @Test("The study-axis commands dim in a child even with the window frontmost")
    func studyAxisDimsInAChild() {
        for command: WindowCommand in [.newProject, .newFolder, .addFiles] {
            #expect(!command.isEnabled(hasKeyWindow: true, role: .child),
                    "\(command) acts on which study — a child has no such axis")
        }
    }

    @Test("The app-level fallback does not rescue them")
    func fallbackDoesNotOverrideTheRole() {
        // newProject and newFolder carry hasAppLevelFallback, so they stay lit
        // with no window frontmost at all. That is for "nothing is focused, so
        // make something" — a different situation from "the focused window is
        // one that deliberately cannot do this". The role is checked first, and
        // this pins that ordering.
        #expect(WindowCommand.newProject.isEnabled(hasKeyWindow: false, role: .master))
        #expect(!WindowCommand.newProject.isEnabled(hasKeyWindow: false, role: .child))
    }

    @Test("Lens and window-targeted commands stay live in a child")
    func theChildKeepsItsOwnAxis() {
        // Switching view is the axis a child owns and the entire reason it
        // exists. If this ever goes red the child has become a read-only pane.
        for command: WindowCommand in [.showSessionsSwitcher, .showMiro, .showWelcome] {
            #expect(command.isEnabled(hasKeyWindow: true, role: .child),
                    "\(command) is not about which study")
        }
    }

    @Test("A master is unaffected — the gate is additive")
    func masterBehaviourIsUnchanged() {
        for command: WindowCommand in [.newProject, .newFolder, .addFiles] {
            #expect(command.isEnabled(hasKeyWindow: true, role: .master))
        }
    }

    @Test("Two windows differing only in role are different menu targets")
    func sinkEqualityIncludesRole() {
        // Without this the menu built against a master would stay enabled when
        // focus moved to a child on the same body pass — the one moment the
        // enablement actually has to change.
        let id = UUID()
        #expect(WindowCommandSink(windowID: id, role: .master, perform: { _ in })
                != WindowCommandSink(windowID: id, role: .child, perform: { _ in }))
    }
}
