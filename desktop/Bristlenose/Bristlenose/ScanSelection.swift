import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "scan-selection")

/// `run`'s file selection, for the Mac's count of what a study holds
/// (decision #111, 21 Oct 2026: "match run").
///
/// A line-for-line port of `iter_scanned_files` in
/// `bristlenose/stages/s01_ingest.py`, plus `classify_file`'s extension test.
/// The two languages cannot share code, so they share a case table instead:
/// `tests/fixtures/scan-selection-contract.json`, asserted against
/// `iter_scanned_files` by `tests/test_scan_selection_contract.py` and against
/// this walk by `ScanSelectionContractTests`. **Change the rules on both sides
/// and in the fixture, or one of the two suites fails.**
///
/// Until this existed the watcher listed the top level only, so a study kept in
/// per-participant folders counted zero: "Drag Interviews Here" and no Analyse,
/// over a folder `run` would analyse in full.
///
/// **Lists and stats, never reads.** Names come from `contentsOfDirectory`,
/// types from `lstat`/`stat`; `realpath` runs once per folder and once per
/// link, never per file (a file's identity is its folder's real path plus its
/// name, which is what Python's `resolve()` gives for a non-link). No file is
/// opened, so a dataless iCloud recording is counted without being downloaded
/// (a dataless *folder* is still listed, which fetches its listing, the same
/// as `run`'s own walk). Callers run it off the main thread — the watcher's
/// `scanQueue`.
enum ScanSelection {

    /// `_MAX_SCAN_DEPTH`: files at most this many levels below the folder.
    /// `study/a.mp4` is level 1, `study/week1/zoom1/a.mp4` level 3.
    static let maxDepth = 3

    /// `OUTPUT_DIR_NAME` — never walked, at any depth.
    static let outputDirName = "bristlenose-output"

    /// The extensions `classify_file` reads (`ALL_EXTENSIONS`, without the dot).
    /// The folder watcher's set minus its companions — pinned against
    /// `ALL_EXTENSIONS` by `tests/test_accepted_extension_parity.py`.
    static var readableExtensions: Set<String> {
        ProjectFolderWatcher.eligibleExtensions.subtracting(ProjectFolderWatcher.companionExtensions)
    }

    /// `is_os_metadata`: AppleDouble `._*`, Office owner files `~$*`, `.DS_Store`.
    static func isOSMetadata(_ name: String) -> Bool {
        name.hasPrefix("._") || name.hasPrefix("~$") || name == ".DS_Store"
    }

    /// `is_bristlenose_artefact`: files and folders Bristlenose wrote for itself.
    static func isArtefact(_ name: String) -> Bool {
        if name == ".bristlenose" { return true }
        if artefactNames.contains(name) { return true }
        return name.hasPrefix("bristlenose.db-")
    }

    private static let artefactNames: Set<String> = [
        "pipeline-events.jsonl", "llm-calls.jsonl", "pii_summary.txt", "run.pid",
        "bristlenose.log", "bristlenose.db", "manifest.json", "study.json",
        "bristlenose-study.txt",
    ]

    /// `classify_file(path) is not None` — the extension test alone.
    static func isReadable(_ url: URL) -> Bool {
        readableExtensions.contains(url.pathExtension.lowercased())
    }

    // MARK: - Refusal

    enum Refusal: Equatable {
        case filesystemRoot, homeFolder, systemFolder
    }

    /// `_refuse_reason`: the roots themselves, never a folder inside them.
    ///
    /// `home` is the REAL home (`UserHome.path`); the sandbox's own home is the
    /// container, against which no researcher's folder ever compares equal.
    /// Both sides resolve links first, as Python's `Path.resolve()` does — with
    /// `realpath(3)`, not `resolvingSymlinksInPath`, which strips `/private`
    /// and would disagree with Python about `/var`.
    static func refusal(for root: URL, home: String = UserHome.path) -> Refusal? {
        let resolved = realPath(root.path)
        if resolved == "/" { return .filesystemRoot }
        let realHome = realPath(home)
        if resolved == realHome { return .homeFolder }
        let systemRoots: Set<String> = [
            "/Applications", "/System", "/Library", "/Volumes", "/private", "/usr",
            "/bin", "/sbin", "/etc", "/var", "/opt", "/cores", realHome + "/Library",
        ]
        return systemRoots.contains(resolved) ? .systemFolder : nil
    }

    // MARK: - The walk

    /// Every file `run`'s scan considers, as `iter_scanned_files` yields them.
    /// Empty for a refused folder, and for one that cannot be listed.
    static func scannedFiles(under root: URL, home: String = UserHome.path) -> [URL] {
        if let refused = refusal(for: root, home: home) {
            // `run` refuses it too, so there is nothing it would analyse. No
            // path in the line: folder names can identify participants.
            log.notice("scan: folder refused as \(String(describing: refused), privacy: .public) — counting nothing")
            return []
        }
        var walk = Walk()
        if !walk.scanDir(root, depth: 0) {
            log.notice("scan: the study folder could not be listed — counting nothing")
        }
        // Links after the real tree, so whatever a link and its target both
        // reach keeps the target's own path (R123).
        while !walk.links.isEmpty {
            let (link, depth) = walk.links.removeFirst()
            walk.scanEntries([link], depth: depth, deferLinks: false)
        }
        return walk.files
    }

    /// The selection, narrowed to what `classify_file` accepts.
    static func readableFiles(under root: URL, home: String = UserHome.path) -> [URL] {
        scannedFiles(under: root, home: home).filter(isReadable)
    }

    private struct Walk {
        var files: [URL] = []
        var seen: Set<String> = []
        var links: [(URL, Int)] = []

        @discardableResult
        mutating func scanDir(_ dir: URL, depth: Int) -> Bool {
            // An unreadable folder is stepped over, never fatal. Listed at its
            // resolved path, so a deferred link to a folder is listed through
            // the link the way `iterdir` follows it; children keep the link's
            // spelling, as Python's do.
            guard let names = try? FileManager.default.contentsOfDirectory(
                atPath: ScanSelection.realPath(dir.path)) else {
                return false
            }
            let entries = names.sorted().map { dir.appendingPathComponent($0) }
            scanEntries(entries, depth: depth, deferLinks: true,
                        parentReal: ScanSelection.realPath(dir.path))
            return true
        }

        /// `parentReal` is the listed folder's real path; nil for a deferred
        /// link, which is resolved on its own.
        mutating func scanEntries(_ entries: [URL], depth: Int, deferLinks: Bool,
                                  parentReal: String? = nil) {
            for entry in entries {
                let name = entry.lastPathComponent
                if name.hasPrefix(".") || ScanSelection.isOSMetadata(name) { continue }
                if ScanSelection.isArtefact(name) { continue }
                let isLink = Self.isSymlink(entry.path)
                if deferLinks && isLink {
                    links.append((entry, depth))
                    continue
                }
                // Each folder and file once, however many links reach it.
                let real: String
                if let parentReal, !isLink {
                    real = parentReal == "/" ? "/" + name : parentReal + "/" + name
                } else {
                    real = ScanSelection.realPath(entry.path)
                }
                if seen.contains(real) { continue }
                switch Self.kind(entry.path) {
                case .directory:
                    if name == ScanSelection.outputDirName { continue }
                    // The discussion guide beside the recordings, case-blind,
                    // at the top only — a document about the study.
                    if depth == 0 && name.lowercased() == DiscussionGuide.folderName.lowercased() {
                        continue
                    }
                    if depth + 1 < ScanSelection.maxDepth {
                        seen.insert(real)
                        scanDir(entry, depth: depth + 1)
                    }
                case .file:
                    seen.insert(real)
                    files.append(entry)
                case .other:
                    continue  // unstatable, a socket, a dangling link
                }
            }
        }

        private enum Kind { case directory, file, other }

        /// `Path.is_dir()` / `is_file()`: `stat`, following links.
        private static func kind(_ path: String) -> Kind {
            var st = stat()
            guard stat(path, &st) == 0 else { return .other }
            switch st.st_mode & S_IFMT {
            case S_IFDIR: return .directory
            case S_IFREG: return .file
            default: return .other
            }
        }

        private static func isSymlink(_ path: String) -> Bool {
            var st = stat()
            return lstat(path, &st) == 0 && (st.st_mode & S_IFMT) == S_IFLNK
        }
    }

    /// `Path.resolve()`: links resolved; a path that does not resolve (a loop, a
    /// vanished target) is kept as given, the way `_resolved` falls back.
    static func realPath(_ path: String) -> String {
        guard let resolved = realpath(path, nil) else {
            return (path as NSString).standardizingPath
        }
        defer { free(resolved) }
        return String(cString: resolved)
    }
}
