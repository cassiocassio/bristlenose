import Foundation

/// Structural classification for Finder material dropped into the project
/// sidebar.  This deliberately knows nothing about a particular sidebar
/// target or pipeline state: those are separate decisions.
///
/// The resolver is used *after* a drop has been admitted.  It has a bounded
/// walk so a wrapper such as Documents cannot turn a sidebar drag into an
/// unbounded filesystem crawl.  Hover validation must use `quicklyMayContain`
/// instead; AppKit calls validation repeatedly on its UI path.
enum SidebarFinderDrop {
    enum Payload: Equatable {
        case projects([URL])
        case source
        case irrelevant
        case indeterminate
    }

    static let maximumDepth = 8
    static let maximumEntries = 1_024

    /// Stat each parent before probing the canonical marker. Probing through
    /// a dataless output directory can itself ask File Provider to fetch it.
    static func locallyLooksAnalysed(_ url: URL) -> Bool {
        LocateFlow.folderLooksAnalysed(url: url)
    }

    /// A cheap, conservative admission check.  It intentionally does not walk
    /// descendants or materialise File Provider content.
    static func quicklyMayContain(_ urls: [URL], acceptedExtensions: Set<String>) -> Bool {
        urls.contains { url in
            url.hasDirectoryPath || acceptedExtensions.contains(url.pathExtension.lowercased())
        }
    }

    /// Hover checks only the direct marker paths. Never enumerate a directory
    /// in AppKit's repeated validation callback; wrapper discovery happens off
    /// the main thread after release.
    static func quicklyContainsProject(
        _ urls: [URL], folderLooksAnalysed: (URL) -> Bool
    ) -> Bool {
        for url in urls where url.hasDirectoryPath {
            guard !CopyMachinery.isDataless(url) else { continue }
            if folderLooksAnalysed(url) { return true }
        }
        return false
    }

    /// Classify a released Finder payload.  BN projects outrank loose source
    /// material in the same wrapper: importing an existing analysis is safer
    /// than silently treating its output as input media.
    static func resolve(
        _ urls: [URL], acceptedExtensions: Set<String>,
        folderLooksAnalysed: (URL) -> Bool,
        isDataless: (URL) -> Bool = CopyMachinery.isDataless
    ) -> Payload {
        var projects: [URL] = []
        var sawSource = false
        var entries = 0
        var exceededLimit = false
        var seen = Set<String>()

        func visit(_ url: URL, depth: Int) {
            guard !exceededLimit else { return }
            // Listing a cloud-only directory can materialise it indefinitely.
            // Refuse the batch before looking inside, including nested folders.
            // A cloud-only *file* is an ordinary leaf: its name and extension
            // are enough to classify it, a stat never fetches it, and the copy
            // or scan reports it honestly later (docs/design-cloud-files.md).
            guard !(url.hasDirectoryPath && isDataless(url)) else { exceededLimit = true; return }
            let canonical = url.resolvingSymlinksInPath().standardizedFileURL.path
            guard seen.insert(canonical).inserted else { return }
            entries += 1
            guard entries <= maximumEntries else { exceededLimit = true; return }

            if url.hasDirectoryPath {
                if folderLooksAnalysed(url) {
                    projects.append(url)
                    return // A project owns its descendants.
                }
                guard depth < maximumDepth else { exceededLimit = true; return }
                let keys: [URLResourceKey] = [.isDirectoryKey, .isPackageKey]
                guard let children = try? FileManager.default.contentsOfDirectory(
                    at: url, includingPropertiesForKeys: keys,
                    options: [.skipsHiddenFiles, .skipsPackageDescendants]
                ) else {
                    exceededLimit = true
                    return
                }
                for child in children { visit(child, depth: depth + 1) }
            // A media-folder acceptance must not promise more than `run` will
            // ingest.  The project scanner's contract is three levels; deeper
            // media-only trees therefore remain indeterminate rather than
            // becoming an apparently successful, empty project.
            } else if depth <= ScanSelection.maxDepth,
                      acceptedExtensions.contains(url.pathExtension.lowercased()) {
                sawSource = true
            }
        }

        for url in urls { visit(url, depth: 0) }
        if exceededLimit { return .indeterminate }
        if !projects.isEmpty {
            // A symlinked wrapper can encounter the same project twice.
            var unique = Set<String>()
            return .projects(projects.filter {
                unique.insert($0.resolvingSymlinksInPath().standardizedFileURL.path).inserted
            })
        }
        return sawSource ? .source : .irrelevant
    }
}
