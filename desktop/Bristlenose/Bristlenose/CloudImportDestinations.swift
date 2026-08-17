import Foundation

// What the import window's destination popup offers, and in what order.
//
// Pure values and two pure functions — `desktop/CLAUDE.md` § Testing, "if a
// SwiftUI view is making a decision, the decision belongs in a testable
// helper". Three decisions live here, and each would otherwise be a silent
// judgement inside a `Picker`'s body.

enum CloudImportDestinations {

    /// What the popup can be set to. `newProject` is a real choice rather than
    /// a nil-means-nothing sentinel: the window opened from the welcome screen
    /// has no project to offer, and "you must go and make one first" is a
    /// dead end where a menu item is a route.
    enum Choice: Hashable {
        case newProject
        case project(UUID)
    }

    /// A run of projects under one heading — one folder, or a stretch of
    /// root-level projects between folders.
    struct Group: Identifiable, Equatable {
        let id: String
        /// Nil for root-level projects, which sit under no heading.
        let folderName: String?
        let projects: [Project]
    }

    /// The popup's contents, **in the researcher's own sidebar order**.
    ///
    /// Not alphabetical, and not creation order. The sidebar arrangement is a
    /// thing the researcher made — current study at the top, last year's below
    /// — and a popup that re-sorts it makes them read a list they had already
    /// organised so they wouldn't have to.
    ///
    /// Folders become headings rather than entries. A folder is not somewhere
    /// a recording can land, so offering it as a destination would be a choice
    /// that cannot work; as a heading it is exactly what it is on screen, which
    /// is where the researcher's memory of "it's in the client folder" lives.
    ///
    /// - Parameter projectsInFolder: supplied by the caller so this stays free
    ///   of `ProjectIndex` and can be driven from fixtures.
    static func groups(
        sidebar: [SidebarItem],
        projectsInFolder: (UUID) -> [Project]
    ) -> [Group] {
        var groups: [Group] = []
        var loose: [Project] = []

        func flushLoose() {
            guard !loose.isEmpty else { return }
            groups.append(Group(id: "root-\(groups.count)",
                                folderName: nil, projects: loose))
            loose = []
        }

        for item in sidebar {
            switch item {
            case .project(let project):
                if isDeliverable(project) { loose.append(project) }
            case .folder(let folder):
                // Flush first, so a root project that sits *above* a folder in
                // the sidebar stays above it here.
                flushLoose()
                let inside = projectsInFolder(folder.id).filter(isDeliverable)
                // An empty folder is a heading with nothing under it — noise in
                // a menu whose whole job is to be chosen from.
                guard !inside.isEmpty else { continue }
                groups.append(Group(id: folder.id.uuidString,
                                    folderName: folder.name, projects: inside))
            }
        }
        flushLoose()
        return groups
    }

    /// What the popup shows when the window opens.
    ///
    /// The project the researcher is looking at, when there is one — importing
    /// is nearly always "put these into the study I have open", and making them
    /// re-state that is asking a question whose answer is already on screen.
    ///
    /// **New Project when there isn't**, rather than the first project in the
    /// list. A silently-defaulted destination is how gigabytes land in last
    /// year's study: the welcome screen means the researcher has said nothing
    /// about where this belongs, and the honest reading of that is "somewhere
    /// new", not "whichever happens to be at the top".
    static func initialChoice(preselected: UUID?, in groups: [Group]) -> Choice {
        guard let preselected,
              groups.contains(where: { group in
                  group.projects.contains { $0.id == preselected }
              })
        else { return .newProject }
        return .project(preselected)
    }

    /// A project with no path publishes into `URL(fileURLWithPath: "")`, which
    /// resolves to the process's working directory — the sandbox container
    /// root. On 16 Aug 2026 a real recording was fetched, verified byte for
    /// byte, published there, and reported "✓ Imported" with no way for the
    /// researcher to find it. Offering such a project as a destination is
    /// offering a choice that cannot work.
    private static func isDeliverable(_ project: Project) -> Bool {
        !project.path.isEmpty
    }
}
