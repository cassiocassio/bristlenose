import Foundation
import Testing

@testable import Bristlenose

// The import window's destination popup. Every test here is about one of two
// promises: that the menu reads in the order the researcher arranged their own
// sidebar, and that it never offers a place a recording cannot actually land.

@Suite("Cloud import destinations")
struct CloudImportDestinationsTests {

    private func project(_ name: String, path: String = "/tmp/x",
                         folder: UUID? = nil, position: Int = 0) -> Project {
        Project(id: UUID(), name: name, path: path, folderId: folder, position: position)
    }

    private func folder(_ name: String, position: Int = 0) -> Folder {
        Folder(id: UUID(), name: name, position: position)
    }

    private func groups(
        _ sidebar: [SidebarItem], inFolder: [UUID: [Project]] = [:]
    ) -> [CloudImportDestinations.Group] {
        CloudImportDestinations.groups(sidebar: sidebar,
                                       projectsInFolder: { inFolder[$0] ?? [] })
    }

    /// The arrangement is a thing the researcher made — current study at the
    /// top, last year's below. A popup that re-sorts it makes them read a list
    /// they had already organised so they wouldn't have to.
    @Test("Root projects keep their sidebar order")
    func rootOrderIsPreserved() {
        let a = project("Ward handover", position: 0)
        let b = project("IKEA with uxfriends", position: 1)
        let result = groups([.project(a), .project(b)])

        #expect(result.count == 1, "one unheaded run")
        #expect(result[0].folderName == nil)
        #expect(result[0].projects.map(\.name) == ["Ward handover", "IKEA with uxfriends"])
    }

    /// A folder is not somewhere a recording can land, so it is a heading and
    /// never an entry — `Section` makes that unselectable by construction.
    @Test("A folder becomes a heading over its own projects")
    func folderBecomesAHeading() {
        let clientFolder = folder("Acme", position: 0)
        let inside = [project("Round 1"), project("Round 2")]
        let result = groups([.folder(clientFolder)], inFolder: [clientFolder.id: inside])

        #expect(result.count == 1)
        #expect(result[0].folderName == "Acme")
        #expect(result[0].projects.map(\.name) == ["Round 1", "Round 2"])
    }

    /// Root projects and folders share one position space in the sidebar, so a
    /// project below a folder must stay below it here. The failure this guards
    /// is the tidy-looking one: all loose projects hoisted above all folders.
    @Test("A root project below a folder stays below it")
    func interleavingSurvives() {
        let top = project("Above", position: 0)
        let acme = folder("Acme", position: 1)
        let bottom = project("Below", position: 2)
        let result = groups([.project(top), .folder(acme), .project(bottom)],
                            inFolder: [acme.id: [project("Round 1")]])

        #expect(result.map(\.folderName) == [nil, "Acme", nil])
        #expect(result[0].projects.map(\.name) == ["Above"])
        #expect(result[2].projects.map(\.name) == ["Below"])
    }

    @Test("An empty folder is not a heading over nothing")
    func emptyFolderIsOmitted() {
        let empty = folder("Archive")
        #expect(groups([.folder(empty)]).isEmpty)
    }

    /// A project with no path publishes into the process's working directory —
    /// the sandbox container root. On 16 Aug 2026 that swallowed a verified
    /// recording while the window said "✓ Imported".
    @Test("A project with no location is never offered")
    func unlocatedProjectIsOmitted() {
        let good = project("Located", path: "/tmp/real")
        let bad = project("Never opened", path: "")
        let result = groups([.project(good), .project(bad)])

        #expect(result.count == 1)
        #expect(result[0].projects.map(\.name) == ["Located"])
    }

    @Test("A folder holding only unlocated projects disappears with them")
    func folderOfUnlocatedProjectsIsOmitted() {
        let acme = folder("Acme")
        let result = groups([.folder(acme)],
                            inFolder: [acme.id: [project("Ghost", path: "")]])
        #expect(result.isEmpty)
    }

    // MARK: - What the popup opens on

    /// Importing is nearly always "put these into the study I have open", and
    /// making the researcher re-state that asks a question whose answer is
    /// already on screen.
    @Test("The project you were looking at is preselected")
    func preselectsTheOpenProject() {
        let wanted = project("IKEA with uxfriends")
        let other = project("Ward handover")
        let built = groups([.project(other), .project(wanted)])

        #expect(CloudImportDestinations.initialChoice(preselected: wanted.id, in: built)
                == .project(wanted.id))
    }

    /// **Not the first project in the list.** The welcome screen means the
    /// researcher has said nothing about where this belongs, and the honest
    /// reading of that is "somewhere new" — a silent default is how gigabytes
    /// land in last year's study.
    @Test("Nothing selected opens on New Project, not on whatever is first")
    func welcomeScreenOpensOnNewProject() {
        let built = groups([.project(project("Ward handover"))])
        #expect(CloudImportDestinations.initialChoice(preselected: nil, in: built) == .newProject)
    }

    /// The preselection comes from the sidebar, which shows projects this popup
    /// refuses to offer. Selecting one anyway would leave the popup displaying
    /// a row it does not contain — blank on macOS, and committing to a
    /// destination that cannot receive a file.
    @Test("A preselected project the popup won't offer falls back to New Project")
    func unofferablePreselectionFallsBack() {
        let unlocated = project("Never opened", path: "")
        let built = groups([.project(unlocated), .project(project("Located"))])

        #expect(CloudImportDestinations.initialChoice(preselected: unlocated.id, in: built)
                == .newProject)
    }

    /// A project inside a folder is as preselectable as a root one — the
    /// containment check has to look through the groups, not only at their
    /// first level.
    @Test("A project inside a folder can be preselected")
    func preselectionReachesInsideFolders() {
        let acme = folder("Acme")
        let inside = project("Round 2")
        let built = groups([.folder(acme)], inFolder: [acme.id: [project("Round 1"), inside]])

        #expect(CloudImportDestinations.initialChoice(preselected: inside.id, in: built)
                == .project(inside.id))
    }
}
