import Foundation
import Testing
@testable import Bristlenose

// MARK: - DroppedFolderState.classify truth table

@Suite("Single-folder drop classification")
struct DroppedFolderStateTests {

    @Test func notTracked_isUntracked() {
        #expect(
            DroppedFolderState.classify(isTracked: false, folderLooksAnalysed: false) == .untracked
        )
    }

    @Test func notTracked_butAnalysedOnDisk_isStillUntracked() {
        // Untracked-but-analysed (clone, prior CLI run) is handled downstream
        // by the create-then-adopt path, not here.
        #expect(
            DroppedFolderState.classify(isTracked: false, folderLooksAnalysed: true) == .untracked
        )
    }

    // The regression this guards: a folder already in projects.json but with no
    // output marker (run killed before output, or added-and-never-run) used to
    // route to a dead-end duplicate alert. It must be drag-to-analyse-able.
    @Test func tracked_butNotAnalysed_isTrackedUnanalysed() {
        #expect(
            DroppedFolderState.classify(isTracked: true, folderLooksAnalysed: false)
                == .trackedUnanalysed
        )
    }

    @Test func tracked_andAnalysed_isTrackedAnalysed() {
        #expect(
            DroppedFolderState.classify(isTracked: true, folderLooksAnalysed: true)
                == .trackedAnalysed
        )
    }
}

// MARK: - The "+ New Project" placeholder

/// A folder already in the sidebar, dropped on the empty placeholder, adopted
/// itself anyway: two rows held one folder and a second run started on it
/// (N157). `ContentView.establishEmptyProject` asks this before it adopts.
@MainActor
@Suite("Drop on the New Project placeholder")
struct PlaceholderDropTests {

    @Test func aFolderAnotherRowHoldsIsThatRowsDrop() throws {
        let (index, tempDir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(tempDir) }
        let folder = tempDir.appendingPathComponent("interviews")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let held = index.addProject(name: "Interviews", path: folder.path)
        let placeholder = index.addProject(name: "New Project", path: "")

        #expect(PlaceholderDrop.resolve(folder: folder, placeholder: placeholder.id, in: index)
                == .existing(held.id))
    }

    @Test func anAnalysedFolderAnotherRowHoldsIsStillThatRowsDrop() throws {
        let (index, tempDir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(tempDir) }
        let folder = tempDir.appendingPathComponent("analysed")
        let marker = folder
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
        try FileManager.default.createDirectory(at: marker, withIntermediateDirectories: true)
        try Data().write(to: marker.appendingPathComponent("pipeline-manifest.json"))
        #expect(LocateFlow.folderLooksAnalysed(url: folder))

        let held = index.addProject(name: "Analysed", path: folder.path)
        let placeholder = index.addProject(name: "New Project", path: "")

        #expect(PlaceholderDrop.resolve(folder: folder, placeholder: placeholder.id, in: index)
                == .existing(held.id))
    }

    @Test func theSameFolderUnderAnotherSpellingIsStillHeld() throws {
        let (index, tempDir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(tempDir) }
        let folder = tempDir.appendingPathComponent("interviews")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let link = tempDir.appendingPathComponent("shortcut")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: folder)
        let held = index.addProject(name: "Interviews", path: folder.path)
        let placeholder = index.addProject(name: "New Project", path: "")

        #expect(PlaceholderDrop.resolve(folder: link, placeholder: placeholder.id, in: index)
                == .existing(held.id))
    }

    @Test func aFolderNoRowHoldsIsAdopted() throws {
        let (index, tempDir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(tempDir) }
        let folder = tempDir.appendingPathComponent("fresh")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        index.addProject(name: "Elsewhere", path: tempDir.appendingPathComponent("other").path)
        let placeholder = index.addProject(name: "New Project", path: "")

        #expect(PlaceholderDrop.resolve(folder: folder, placeholder: placeholder.id, in: index) == .adopt)
    }
}
