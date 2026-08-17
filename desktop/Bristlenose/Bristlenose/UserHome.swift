import Foundation

/// The researcher's real home directory, and the `~` abbreviation that depends
/// on knowing it.
///
/// **`NSHomeDirectory()` and `FileManager.homeDirectoryForCurrentUser` both lie
/// under App Sandbox.** They return the app's *container*
/// (`~/Library/Containers/app.bristlenose/Data`), not `/Users/<me>`. Every path
/// a researcher can see in Bristlenose is a real home path — projects live
/// wherever they put them, and the sandbox grants access through the panel — so
/// a comparison against the container home is never true, and it fails
/// **silently**:
///
/// - the undo toast and the location breadcrumb printed
///   `/Users/cassio/Work/Studies` where every Mac app prints `~/Work/Studies`
///   (and VoiceOver read two junk components before the useful ones);
/// - `ProjectFolderDefaults`' Documents floor resolved to a private, usually
///   non-existent folder *inside* the container rather than `~/Documents`.
///
/// The container is not merely a different prefix, either: it symlinks
/// `Desktop`, `Downloads`, `Movies`, `Music` and `Pictures` out to the real
/// folders but keeps **`Documents` private**, so `.documentDirectory` +
/// `.userDomainMask` is the one home-folder lookup the sandbox does not hand
/// back. (Verified against `~/Library/Containers/com.apple.TextEdit/Data/`,
/// where the five are symlinks and `Documents` is a real `drwx------`.) A
/// project created there would live inside the container: invisible in Finder
/// and destroyed by `desktop/scripts/reset-sandbox-state.sh`.
///
/// `getpwuid(getuid())` reads the passwd entry. The sandbox does not rewrite
/// it, so it is the real home on any Mac, sandboxed or not.
enum UserHome {

    /// The real home directory path — `/Users/<me>`, never the container.
    static let path: String = {
        if let pw = getpwuid(getuid()), let dir = pw.pointee.pw_dir {
            let resolved = String(cString: dir)
            if !resolved.isEmpty { return resolved }
        }
        // Unreachable in practice (a process always has a passwd entry). Falling
        // back to the container is wrong but harmless — the same wrong answer
        // the callers had before this type existed.
        return NSHomeDirectory()
    }()

    /// The real home directory.
    static var url: URL { URL(fileURLWithPath: path, isDirectory: true) }

    /// A top-level folder in the real home — `UserHome.folder("Documents")`.
    ///
    /// The on-disk names are invariant; only their *display* names localise
    /// (via `URL.localizedName`), so a literal is correct here.
    static func folder(_ name: String) -> URL {
        url.appendingPathComponent(name, isDirectory: true)
    }

    /// `~/Work/Studies` for a path inside the home; the path unchanged otherwise.
    ///
    /// Finder's own abbreviation, and what a Mac user expects to read in a
    /// tooltip, a breadcrumb or a settings row.
    static func abbreviate(_ rawPath: String) -> String {
        guard !rawPath.isEmpty else { return rawPath }
        let home = path
        guard rawPath == home || rawPath.hasPrefix(home + "/") else { return rawPath }
        return "~" + rawPath.dropFirst(home.count)
    }

    /// `abbreviate(_:)` split for a comma-joined VoiceOver label — the leading
    /// `~` arrives as its own segment so it is spoken, not spelled into a path.
    static func abbreviatedSegments(_ rawPath: String) -> [String] {
        let display = abbreviate(rawPath)
        return display.split(separator: "/").map(String.init)
    }
}
