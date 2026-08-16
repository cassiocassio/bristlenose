import Foundation
import Testing

@testable import Bristlenose

/// The window subtitle's composition rules — the parenthesised half of the
/// Window-menu entry. Options weighed: `docs/mockups/window-menu-naming.html`.
///
/// The run-state precedence *is* covered here now (`WindowSubtitle.body`): it
/// grew a third input on 16 Aug 2026 — only the key window narrates a run — and
/// three interacting rules inside a SwiftUI `body` is exactly what this file's
/// opening note says not to leave untestable. The text for each outcome still
/// lives in the modifier, and `RunProgressSubtitle.compose` has its own suite.
@Suite("Window subtitle composition")
struct WindowSubtitleTests {

    private func project(_ name: String, folder: UUID? = nil) -> Project {
        Project(id: UUID(), name: name, path: "/tmp/\(name)", folderId: folder)
    }

    // MARK: - Folder disambiguator (mockup E5)

    @Test("absent when the name is unique — the normal case")
    func uniqueName_noFolder() {
        let acme = Folder(id: UUID(), name: "Acme")
        let pilot = project("Pilot", folder: acme.id)
        let other = project("IKEA Study", folder: acme.id)

        #expect(WindowSubtitle.folderDisambiguator(
            for: pilot, projects: [pilot, other], folders: [acme]
        ) == nil)
    }

    @Test("appears when another project shares the name")
    func duplicateName_namesTheFolder() {
        let acme = Folder(id: UUID(), name: "Acme")
        let globex = Folder(id: UUID(), name: "Globex")
        let mine = project("Pilot", folder: acme.id)
        let theirs = project("Pilot", folder: globex.id)

        #expect(WindowSubtitle.folderDisambiguator(
            for: mine, projects: [mine, theirs], folders: [acme, globex]
        ) == "Acme")
        #expect(WindowSubtitle.folderDisambiguator(
            for: theirs, projects: [mine, theirs], folders: [acme, globex]
        ) == "Globex")
    }

    @Test("a case-only difference still counts as a clash")
    func caseInsensitiveClash() {
        // The failure being solved is visual: "Pilot" and "pilot" are as
        // ambiguous in a menu as two exact matches.
        let acme = Folder(id: UUID(), name: "Acme")
        let mine = project("Pilot", folder: acme.id)
        let theirs = project("pilot", folder: UUID())

        #expect(WindowSubtitle.folderDisambiguator(
            for: mine, projects: [mine, theirs], folders: [acme]
        ) == "Acme")
    }

    @Test("the project itself never counts as its own duplicate")
    func soleProject_noFolder() {
        let acme = Folder(id: UUID(), name: "Acme")
        let only = project("Pilot", folder: acme.id)

        #expect(WindowSubtitle.folderDisambiguator(
            for: only, projects: [only], folders: [acme]
        ) == nil)
    }

    @Test("a clashing project at the sidebar root stays ambiguous")
    func rootProject_hasNoFolderToName() {
        // Honest: there is no folder, and inventing a label for "no folder"
        // would read as a real one.
        let acme = Folder(id: UUID(), name: "Acme")
        let atRoot = project("Pilot")
        let inFolder = project("Pilot", folder: acme.id)

        #expect(WindowSubtitle.folderDisambiguator(
            for: atRoot, projects: [atRoot, inFolder], folders: [acme]
        ) == nil)
        // …while its counterpart still names its own folder.
        #expect(WindowSubtitle.folderDisambiguator(
            for: inFolder, projects: [atRoot, inFolder], folders: [acme]
        ) == "Acme")
    }

    @Test("a dangling folder id yields nothing rather than an empty separator")
    func missingFolder_isNotHalfComposed() {
        let mine = project("Pilot", folder: UUID())   // folder not in the list
        let theirs = project("Pilot")

        #expect(WindowSubtitle.folderDisambiguator(
            for: mine, projects: [mine, theirs], folders: []
        ) == nil)
    }

    @Test("a blank folder name is treated as no name")
    func whitespaceFolderName_isIgnored() {
        let blank = Folder(id: UUID(), name: "   ")
        let mine = project("Pilot", folder: blank.id)
        let theirs = project("Pilot")

        #expect(WindowSubtitle.folderDisambiguator(
            for: mine, projects: [mine, theirs], folders: [blank]
        ) == nil)
    }

    // MARK: - compose

    @Test("joins folder and body on the shared separator")
    func compose_bothHalves() {
        #expect(WindowSubtitle.compose(folder: "Acme", body: "163 Quotes")
                == "Acme · 163 Quotes")
    }

    @Test("either half alone composes without a stray separator")
    func compose_oneHalf() {
        #expect(WindowSubtitle.compose(folder: nil, body: "163 Quotes") == "163 Quotes")
        #expect(WindowSubtitle.compose(folder: "Acme", body: "") == "Acme")
    }

    @Test("nothing to say composes to empty, not to a separator")
    func compose_empty() {
        // AppKit renders "" as a bare title. A stray " · " would render as
        // visible punctuation with nothing either side of it — which is what a
        // naive join produces at zero, and the reason this case is pinned.
        #expect(WindowSubtitle.compose(folder: nil, body: "") == "")
        #expect(WindowSubtitle.compose(folder: "", body: "") == "")
    }

    // MARK: - Which body wins (mockup E7, multi-window 16 Aug 2026)

    @Test("only the key window narrates a run")
    func nonKeyWindowShowsItsCount() {
        // The case this rule exists for: five windows on one study, one run.
        // Four of them are more useful showing their own lens's count.
        #expect(WindowSubtitle.body(narratesRun: false, isStopping: false, isRunning: true)
                == .count)
        #expect(WindowSubtitle.body(narratesRun: false, isStopping: true, isRunning: true)
                == .count,
                "not even Stopping — a background window narrating is the noise being removed")
    }

    @Test("the key window narrates, and stopping outranks progress")
    func keyWindowPrecedence() {
        #expect(WindowSubtitle.body(narratesRun: true, isStopping: false, isRunning: true)
                == .runProgress)
        // Immediate ack: the pill, the sidebar row and the titlebar flip
        // together on the click, before the run has actually wound down.
        #expect(WindowSubtitle.body(narratesRun: true, isStopping: true, isRunning: true)
                == .stopping)
    }

    @Test("no run means the count, key window or not")
    func idleShowsCount() {
        #expect(WindowSubtitle.body(narratesRun: true, isStopping: false, isRunning: false)
                == .count)
        #expect(WindowSubtitle.body(narratesRun: false, isStopping: false, isRunning: false)
                == .count)
    }
}
